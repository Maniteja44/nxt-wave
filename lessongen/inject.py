"""Deliberate-error injection, to prove the evaluator catches real problems.

Used two ways:
  * `run --inject-error X`      corrupts the FIRST draft only; the loop must catch it
                                 and the reviser must fix it.
  * `evaluate FILE --inject-error X`  corrupts a lesson file and just shows the verdict.
"""
from __future__ import annotations

import re

from .textutils import words

MISCONCEPTION = (
    "Here is the secret: RAG retrains the AI model on your documents, so the model permanently learns them. "
    "Because of this, RAG removes all hallucinations."
)
JARGON = (
    "Inside, the retriever runs cosine similarity over dense vectors in an HNSW index to pick the top-k chunks."
)
LONG = (
    "This is important because when a company has thousands of documents that keep changing every week and "
    "employees want quick answers to their questions without reading everything themselves, a system like this "
    "can find the right pages and write a helpful reply that saves a lot of time for everyone involved in the work."
)
WRONG_QUIZ_ANSWER = "**Answer:** RAG works by retraining the model every night on the new documents."


def _insert_after_first_paragraph(md: str, heading_rx: str, text: str) -> str:
    lines = md.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^##\s+", line) and re.search(heading_rx, line, re.IGNORECASE):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            while j < len(lines) and lines[j].strip() and not lines[j].startswith("#"):
                j += 1
            return "\n".join(lines[:j] + ["", text] + lines[j:]) + "\n"
    return md.rstrip() + "\n\n" + text + "\n"


def _drop_section(md: str, heading_rx: str) -> str:
    out, skip = [], False
    for line in md.splitlines():
        if re.match(r"^##\s+", line):
            skip = bool(re.search(heading_rx, line, re.IGNORECASE))
        if not skip:
            out.append(line)
    return "\n".join(out) + "\n"


def inject(md: str, kind: str) -> tuple[str, str]:
    """Return (corrupted_markdown, human description of what was injected)."""
    if kind == "misconception":
        return _insert_after_first_paragraph(md, r"what is", MISCONCEPTION), f'Inserted false claims: "{MISCONCEPTION}"'
    if kind == "jargon":
        return _insert_after_first_paragraph(md, r"how does .*work|how .* works", JARGON), f'Inserted unexplained jargon: "{JARGON}"'
    if kind == "long_sentence":
        return _insert_after_first_paragraph(md, r"why", LONG), f"Inserted a {len(words(LONG))}-word sentence."
    if kind == "drop_example":
        return _drop_section(md, r"example"), "Deleted the whole worked-example section."
    if kind == "wrong_quiz":
        new, n = re.subn(r"\*\*Answer:\*\*[^\n]*|Answer:[^\n]*", WRONG_QUIZ_ANSWER, md, count=1)
        return (new if n else md), f'Replaced the first quiz answer with a wrong one: "{WRONG_QUIZ_ANSWER}"'
    if kind == "all":
        out, descs = md, []
        for k in ("misconception", "jargon", "long_sentence"):
            out, d = inject(out, k)
            descs.append(d)
        return out, " | ".join(descs)
    raise ValueError(f"unknown error kind: {kind}")


KINDS = ["misconception", "jargon", "long_sentence", "drop_example", "wrong_quiz", "all"]
