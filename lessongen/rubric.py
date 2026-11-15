"""The rubric: 13 hard pass/fail checkpoints. No partial credit, no weighted score.

A lesson ships only if EVERY check passes. Two kinds of checks:

* code - deterministic Python. Cheap, reproducible, cannot be talked out of a verdict.
         Used wherever "good" can be measured mechanically.
* llm  - an LLM judge at temperature 0, one judge per check, grounded in the topic
         spec. Must quote evidence from the lesson; quotes are verified in code.
"""
from __future__ import annotations

from dataclasses import dataclass

# Lesson template. The writer must use these headings in this order; the structure
# check matches each heading with the regex below.
SECTIONS = [
    ("learn", r"what you will learn", "## What you will learn"),
    ("why", r"why .*(matter|need)", "## Why does this matter?"),
    ("what", r"^what is", "## What is {short}?"),
    ("how", r"how does .*work|how .* works", "## How does it work?"),
    ("example", r"example", "## A full example, step by step"),
    ("limits", r"go wrong|limit", "## Where can it go wrong?"),
    ("takeaways", r"takeaway|recap|summary", "## Key takeaways"),
    ("glossary", r"glossary", "## Glossary"),
    ("quiz", r"check your understanding|quiz", "## Check your understanding"),
]

# Thresholds for code checks (calibrated on hand-written beginner lessons; see tests).
LIMITS = {
    "min_words": 900,
    "max_words": 2600,
    "max_fk_grade": 8.0,           # Flesch-Kincaid grade level of the prose
    "max_avg_sentence_words": 15.0,
    "max_sentence_words": 30,       # any single sentence longer than this fails
    "quiz_min": 3,
    "quiz_max": 5,
}


@dataclass(frozen=True)
class Check:
    id: str
    dimension: str
    kind: str          # "code" | "llm"
    criterion: str     # the binary pass condition, in one sentence


CHECKS: list[Check] = [
    # ---- deterministic -------------------------------------------------------
    Check("structure", "coherent teaching flow", "code",
          "All 9 template sections are present, as level-2 headings, in the required why -> what -> how -> example -> limits -> recap order, under one H1 title."),
    Check("length", "beginner-friendly language", "code",
          f"Lesson length is between {LIMITS['min_words']} and {LIMITS['max_words']} words (complete, but not overwhelming)."),
    Check("readability", "beginner-friendly language", "code",
          f"Prose has Flesch-Kincaid grade <= {LIMITS['max_fk_grade']} and average sentence length <= {LIMITS['max_avg_sentence_words']} words."),
    Check("sentence_length", "beginner-friendly language", "code",
          f"No sentence is longer than {LIMITS['max_sentence_words']} words."),
    Check("glossary_coverage", "clear, no unexplained jargon", "code",
          "Every technical term used in the lesson body is listed in the Glossary."),
    Check("misconception_tripwire", "accurate & grounded", "code",
          "No sentence states a known dangerous misconception (e.g. RAG retrains the model, RAG removes all hallucinations) without negating it."),
    Check("quiz_format", "covers the key points", "code",
          f"'Check your understanding' has {LIMITS['quiz_min']}-{LIMITS['quiz_max']} questions and every question has an answer."),
    # ---- LLM judges ----------------------------------------------------------
    Check("accuracy", "accurate & grounded", "llm",
          "Every claim (including quiz answers) is correct and consistent with the reference facts; no misconception is stated; no invented numbers, dates, names or tools."),
    Check("key_points", "covers the key points", "llm",
          "Every key point in the topic spec is clearly taught (proved with a quote from the lesson)."),
    Check("jargon_explained", "clear, no unexplained jargon", "llm",
          "Every technical term is explained in simple words at or before its first use, not only in the glossary."),
    Check("plain_language", "beginner-friendly language", "llm",
          "A learner with limited English could read it: no idioms, no rare or formal words where a common word works, no unfamiliar cultural references."),
    Check("examples", "teaches by example", "llm",
          "Has (a) an everyday analogy for the core idea that an Indian student would relate to, and (b) a concrete worked example showing the question, the retrieved information, what is sent to the model, and the answer."),
    Check("flow", "coherent teaching flow", "llm",
          "Ideas are introduced before they are used, each section builds on the last, nothing contradicts anything else, and the worked example follows the steps described in 'How does it work?'."),
]

CHECK_BY_ID = {c.id: c for c in CHECKS}
