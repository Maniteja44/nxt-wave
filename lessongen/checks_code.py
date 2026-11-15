"""Deterministic checks. Each returns a CheckResult with an actionable `fix`."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .rubric import CHECK_BY_ID, LIMITS, SECTIONS
from .textutils import find_section, prose_lines, sections, split_sentences, strip_code, words


@dataclass
class CheckResult:
    id: str
    passed: bool
    reason: str
    evidence: list[str] = field(default_factory=list)
    fix: str = ""
    details: dict = field(default_factory=dict)

    @property
    def kind(self) -> str:
        return CHECK_BY_ID[self.id].kind if self.id in CHECK_BY_ID else "code"

    @property
    def dimension(self) -> str:
        return CHECK_BY_ID[self.id].dimension if self.id in CHECK_BY_ID else ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["kind"], d["dimension"] = self.kind, self.dimension
        return d


EXCLUDE_FOR_PROSE = (r"glossary", r"check your understanding|quiz")


# --------------------------------------------------------------------------- structure
def check_structure(md: str) -> CheckResult:
    secs = sections(md)
    h1 = [s for s in secs if s.level == 1]
    h2 = [s.heading for s in secs if s.level == 2]
    positions, missing = [], []
    for key, rx, template in SECTIONS:
        idx = next((i for i, h in enumerate(h2) if re.search(rx, h, re.IGNORECASE)), None)
        if idx is None:
            missing.append(template)
        else:
            positions.append((key, idx))
    out_of_order = [
        f"'{positions[i][0]}' comes before '{positions[i - 1][0]}'"
        for i in range(1, len(positions))
        if positions[i][1] < positions[i - 1][1]
    ]
    problems = []
    if len(h1) != 1:
        problems.append(f"expected exactly one '# Title' line, found {len(h1)}")
    if missing:
        problems.append("missing sections: " + ", ".join(missing))
    if out_of_order:
        problems.append("sections out of order: " + "; ".join(out_of_order))
    if problems:
        return CheckResult(
            "structure", False, "; ".join(problems), evidence=h2,
            fix="Use exactly these level-2 headings in this order: " + " | ".join(t for _, _, t in SECTIONS),
        )
    return CheckResult("structure", True, "All template sections present and in order.")


# ------------------------------------------------------------------------------ length
def check_length(md: str) -> CheckResult:
    n = len(words(strip_code(md)))
    lo, hi = LIMITS["min_words"], LIMITS["max_words"]
    if n < lo:
        return CheckResult("length", False, f"{n} words; minimum is {lo}.", details={"words": n},
                           fix=f"Expand to at least {lo} words: add more explanation and examples in the thinnest sections.")
    if n > hi:
        return CheckResult("length", False, f"{n} words; maximum is {hi}.", details={"words": n},
                           fix=f"Cut to under {hi} words: remove repetition and side topics, keep the key points.")
    return CheckResult("length", True, f"{n} words.", details={"words": n})


# ------------------------------------------------------------------------- readability
def syllables(word: str) -> int:
    """Heuristic English syllable count (no dictionary download needed, deterministic)."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 1  # numbers etc.
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|[^laeiouydt]ed|[^laeiouy]e)$", lambda m: m.group(0)[0], w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]+", w)))


def readability_stats(md: str) -> dict:
    lines = prose_lines(md, exclude_sections=EXCLUDE_FOR_PROSE)
    sents = [s for s in split_sentences(lines) if words(s)]
    all_words = [w for s in sents for w in words(s)]
    if not sents or not all_words:
        return {"fk_grade": 0.0, "flesch_reading_ease": 0.0, "avg_sentence_words": 0.0, "sentences": 0}
    wps = len(all_words) / len(sents)
    spw = sum(syllables(w) for w in all_words) / len(all_words)
    return {
        "fk_grade": round(0.39 * wps + 11.8 * spw - 15.59, 2),           # Flesch-Kincaid grade
        "flesch_reading_ease": round(206.835 - 1.015 * wps - 84.6 * spw, 1),
        "avg_sentence_words": round(wps, 1),
        "sentences": len(sents),
    }


def check_readability(md: str) -> CheckResult:
    st = readability_stats(md)
    bad = []
    if st["fk_grade"] > LIMITS["max_fk_grade"]:
        bad.append(f"Flesch-Kincaid grade {st['fk_grade']} > {LIMITS['max_fk_grade']}")
    if st["avg_sentence_words"] > LIMITS["max_avg_sentence_words"]:
        bad.append(f"average sentence {st['avg_sentence_words']} words > {LIMITS['max_avg_sentence_words']}")
    if bad:
        return CheckResult("readability", False, "; ".join(bad), details=st,
                           fix="Split long sentences into two. Replace long words (4+ syllables) with common short words where possible.")
    return CheckResult("readability", True, f"FK grade {st['fk_grade']}, avg sentence {st['avg_sentence_words']} words.", details=st)


def check_sentence_length(md: str) -> CheckResult:
    lim = LIMITS["max_sentence_words"]
    sents = split_sentences(prose_lines(md))
    long = [s for s in sents if len(words(s)) > lim]
    if long:
        return CheckResult("sentence_length", False, f"{len(long)} sentence(s) over {lim} words.",
                           evidence=long[:5], fix="Rewrite each quoted sentence as two or three sentences of under 20 words.")
    return CheckResult("sentence_length", True, f"No sentence over {lim} words.")


# ---------------------------------------------------------------------------- jargon
def jargon_usage(md: str, patterns: dict[str, re.Pattern]) -> dict[str, str]:
    """term -> first sentence (outside glossary/quiz) where it is used."""
    sents = split_sentences(prose_lines(md, exclude_sections=EXCLUDE_FOR_PROSE))
    # Include headings in the search for first use? No: headings are not explanations.
    used: dict[str, str] = {}
    for term, rx in patterns.items():
        for s in sents:
            if rx.search(s):
                used[term] = s
                break
    return used


def check_glossary_coverage(md: str, patterns: dict[str, re.Pattern]) -> CheckResult:
    used = jargon_usage(md, patterns)
    gloss = find_section(md, r"glossary")
    gtext = gloss.body if gloss else ""
    missing = [t for t in used if not patterns[t].search(gtext)]
    if missing:
        return CheckResult("glossary_coverage", False,
                           f"Used but not in Glossary: {', '.join(missing)}",
                           evidence=list(dict.fromkeys(used[t] for t in missing))[:6],
                           details={"used_terms": sorted(used), "missing": missing},
                           fix="Add a one-line simple definition to the Glossary for: " + ", ".join(missing)
                           + ". If a term is not really needed, remove it from the lesson instead.")
    return CheckResult("glossary_coverage", True, f"All {len(used)} technical terms used are in the Glossary.",
                       details={"used_terms": sorted(used)})


# ---------------------------------------------------------------- misconception tripwire
# High-precision patterns for the most harmful misconceptions. A sentence trips only if
# it matches AND contains no negation/contrast word. The LLM accuracy judge is the
# primary accuracy check; this is a cheap, unarguable second line of defence.
NEGATION = re.compile(
    r"\b(not|no|never\s+(retrain|change)|cannot|without|unlike|instead|rather|than|myth|"
    r"mistake|wrong to|false|isn't|doesn't|don't|won't|aren't|does not|do not|is not|no need)\b|n't\b",
    re.IGNORECASE,
)
RAG_CONTEXT = re.compile(r"\bRAG\b|\bretriev\w*", re.IGNORECASE)
TRIPWIRES = [
    ("RAG retrains / fine-tunes the model or changes its weights",
     re.compile(r"\b(re-?train\w*|fine-tunes?\b|fine-tuned\b|(chang|updat|modif)\w*\b[^.]{0,25}\bweights)", re.I), True),
    ("the model permanently learns / remembers the documents",
     re.compile(r"\b(permanently|forever)\b[^.]{0,40}\b(learn|remember|store|know)\w*|\b(learn|remember|memori[sz])\w*\b[^.]{0,30}\b(permanently|forever)\b", re.I), True),
    ("RAG removes all hallucinations",
     re.compile(r"\b(eliminat|remov|get rid of|prevent|stop)\w*\b[^.]{0,30}\b(all\s+)?hallucinat\w*", re.I), False),
    ("RAG guarantees correct answers",
     re.compile(r"\b(always|guarantee\w*|100\s?%)\b[^.]{0,25}\b(correct|accurate|right|true)\b"
                r"|\bnever\b[^.]{0,20}\b(wrong|mistakes?|hallucinat\w*)", re.I), True),
    ("the vector database writes the answer",
     re.compile(r"\bvector (database|db|store)\b[^.]{0,30}\b(writes|generates|creates)\b[^.]{0,20}\banswer", re.I), False),
]


def check_misconception_tripwire(md: str) -> CheckResult:
    hits = []
    for s in split_sentences(prose_lines(md)):
        if s.rstrip().endswith("?"):
            continue  # questions are not claims
        for label, rx, needs_rag_context in TRIPWIRES:
            if not rx.search(s):
                continue
            if needs_rag_context and not RAG_CONTEXT.search(s):
                continue
            if NEGATION.search(s):
                continue
            hits.append((label, s))
    if hits:
        return CheckResult("misconception_tripwire", False,
                           "Possible misconception stated as fact: " + "; ".join(sorted({h[0] for h in hits})),
                           evidence=list(dict.fromkeys(h[1] for h in hits))[:5],
                           fix="Rewrite each quoted sentence so it is correct: RAG does NOT retrain the model or change its weights; "
                               "the model does not keep the information after answering; RAG REDUCES hallucinations but does not remove them.")
    return CheckResult("misconception_tripwire", True, "No known misconception patterns found.")


# --------------------------------------------------------------------------------- quiz
def check_quiz_format(md: str) -> CheckResult:
    quiz = find_section(md, r"check your understanding|quiz")
    if not quiz:
        return CheckResult("quiz_format", False, "No 'Check your understanding' section.",
                           fix="Add '## Check your understanding' with 3-5 numbered questions, each followed by a line starting 'Answer:'.")
    body = quiz.body
    qs = re.findall(r"^\s*(?:\*\*)?(?:Q\s?\d+|\d+[.)])", body, re.MULTILINE)
    ans = re.findall(r"\banswer\s*:", body, re.IGNORECASE)
    lo, hi = LIMITS["quiz_min"], LIMITS["quiz_max"]
    if not (lo <= len(qs) <= hi) or len(ans) < len(qs):
        return CheckResult("quiz_format", False, f"Found {len(qs)} questions and {len(ans)} answers; need {lo}-{hi} questions, each with an answer.",
                           details={"questions": len(qs), "answers": len(ans)},
                           fix=f"Write {lo}-{hi} questions as '**Q1.** ...' each followed by a line starting '**Answer:**'.")
    return CheckResult("quiz_format", True, f"{len(qs)} questions, all answered.", details={"questions": len(qs)})


def run_code_checks(md: str, patterns: dict[str, re.Pattern]) -> list[CheckResult]:
    return [
        check_structure(md),
        check_length(md),
        check_readability(md),
        check_sentence_length(md),
        check_glossary_coverage(md, patterns),
        check_misconception_tripwire(md),
        check_quiz_format(md),
    ]
