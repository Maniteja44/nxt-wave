"""All prompts in one place, so prompt changes are easy to review in git diffs."""
from __future__ import annotations

from .rubric import CHECKS, LIMITS, SECTIONS


def _bullets(items) -> str:
    return "\n".join(f"- {x}" for x in items)


def template_headings(short: str) -> str:
    return "\n".join(t.format(short=short) for _, _, t in SECTIONS)


def guidance_block(rules: list[dict]) -> str:
    if not rules:
        return ""
    return (
        "\n\nLESSONS LEARNED FROM PAST RUNS (reviewers rejected earlier lessons for these reasons - follow them):\n"
        + _bullets(r["rule"] for r in rules)
    )


# ============================================================================ writer
WRITER_SYSTEM = """You are an expert teacher who writes first lessons on AI topics for Indian students.

YOUR LEARNER: {learner}

WRITING RULES (all are strict - a reviewer checks every one):
1. Simple English. Use common everyday words. If a simpler word exists, use it ("use" not "utilise", "help" not "facilitate", "about" not "approximately").
2. Short sentences. Most sentences under 15 words. Never more than 25 words. One idea per sentence. Paragraphs of 2-4 sentences.
3. No idioms or non-literal phrases ("piece of cake", "under the hood", "in a nutshell", "game-changer", "on the fly"). No references only Western readers know (baseball, Thanksgiving, etc.).
4. Every technical word must be explained in simple words THE FIRST TIME you use it, in the same or the previous sentence - and also listed in the Glossary. Avoid technical words you do not need.
5. Teach by example. Use situations from everyday Indian student life (exam preparation, class notes, a school library, cricket, railway enquiry, a kirana shop, phone contacts, WhatsApp groups). Choose ONE main analogy for the core idea and keep coming back to it.
6. Problem before solution. Each idea builds on the one before. Never use an idea before you have explained it.
7. Be accurate. Rely on the reference facts given. Do not say "always", "never", "guarantee" or "100%" unless a fact says so. Do not add numbers, dates, names, products or tools that are not in the reference facts.
8. Speak to the learner as "you". Warm and encouraging. No programming code.
9. Length: {min_words}-{max_words} words in total."""

PLAN_USER = """Plan a beginner lesson on: {title}

KEY POINTS THAT MUST BE TAUGHT:
{key_points}

REFERENCE FACTS (ground truth):
{facts}

MISCONCEPTIONS TO AVOID (never state these as true; you may correct them):
{misconceptions}
{guidance}

Return JSON:
{{
  "short_name": "short topic name used in headings, e.g. RAG",
  "main_analogy": "one everyday Indian-life analogy for the core idea, and how each part maps to the technical idea",
  "worked_example": {{
     "scenario": "a concrete situation (who is asking what, over which documents)",
     "documents": ["2-4 short example document snippets"],
     "question": "the user's question",
     "retrieved": ["the 1-2 snippets that would be found"],
     "answer": "the final answer the model would give"
  }},
  "sections": [{{"heading": "exact heading", "key_points": ["kp ids taught here"], "bullets": ["what to say, in order"]}}],
  "glossary_terms": ["every technical term the lesson will use"],
  "quiz": [{{"q": "question", "a": "answer"}}]
}}
The sections must be exactly these headings, in this order:
{headings}"""

WRITE_USER = """Write the full lesson in Markdown, following the plan below exactly.

TITLE (use as the only '# ' heading): {title}

PLAN:
{plan}

KEY POINTS THAT MUST BE TAUGHT:
{key_points}

REFERENCE FACTS (ground truth - stay consistent with these):
{facts}

MISCONCEPTIONS (never state as true):
{misconceptions}
{guidance}

FORMAT RULES:
- Use exactly these level-2 headings, in this order:
{headings}
- In "A full example, step by step": number the steps and show the question, the retrieved text, the text that is sent to the model (question + retrieved text together), and the final answer. Show these pieces as quoted blocks (lines starting with "> ").
- "Glossary": one line per term, as "- **term**: simple meaning". Include EVERY technical term you used.
- "Check your understanding": {quiz_min}-{quiz_max} questions written as "**Q1.** question" followed by a line "**Answer:** answer".
- Output ONLY the lesson Markdown. No notes before or after it."""

REVISE_USER = """A reviewer REJECTED the lesson below. Fix every failed check. Keep everything that already works.

FAILED CHECKS (fix all of these):
{failures}

CHECKS THAT ALREADY PASS (do not break them):
{passing}

KEY POINTS THAT MUST STAY TAUGHT:
{key_points}

REFERENCE FACTS:
{facts}

MISCONCEPTIONS (never state as true):
{misconceptions}
{guidance}

Required headings, in order:
{headings}

CURRENT LESSON:
<lesson>
{lesson}
</lesson>

Make targeted edits, not a full rewrite, unless the structure itself failed.
Reply in exactly this format:
<changes>
- one bullet per change you made, naming the failed check it fixes
</changes>
<lesson>
the full corrected lesson in Markdown
</lesson>"""

# ============================================================================= judges
JUDGE_SYSTEM = """You are a strict, fair reviewer of beginner lessons for Indian students with limited English and no AI background.
You check ONE criterion and give a binary verdict: PASS or FAIL. There is no partial credit.
Rules:
- FAIL only for a concrete problem a real beginner would hit. Do not fail for style preferences.
- Every FAIL must quote the exact problem text from the lesson in "evidence" (copy it character for character, one sentence or phrase per item).
- "fix" must be a specific instruction a writer can follow (what to change, and how).
- Judge only the criterion you are given."""

JUDGE_BASE = """CRITERION ({check_id}): {criterion}

{context}
{calibration}
LESSON:
<lesson>
{lesson}
</lesson>

Return JSON:
{schema}"""

BASE_SCHEMA = '{"verdict": "PASS" or "FAIL", "reason": "one or two sentences", "evidence": ["exact quotes from the lesson"], "fix": "specific instruction, empty if PASS"}'

JUDGE_CONTEXT = {
    "accuracy": """REFERENCE FACTS (ground truth):
{facts}

KNOWN MISCONCEPTIONS (stating any as true = FAIL):
{misconceptions}

Check every claim, including the worked example and the quiz answers. FAIL if any claim is false, contradicts a reference fact, states a misconception, over-claims (e.g. "always correct", "removes all hallucinations"), or adds a specific number, date, name or tool that is not supported by the facts and could be wrong.""",

    "key_points": """KEY POINTS (each must be clearly taught - mentioning a word is not teaching it):
{key_points}

For EVERY key point, decide covered true/false and give the lesson quote that teaches it. FAIL if any key point is not covered.""",

    "jargon_explained": """Technical terms our scanner found, with the sentence where each is FIRST used:
{first_uses}

For each term, decide: is it explained in simple words at its first use (same sentence, or the sentence just before/after)? A definition only in the Glossary does NOT count.
Also look for any OTHER technical or hard word used without explanation.
FAIL if any term is used before it is explained.""",

    "plain_language": """The learner studied in a non-English-medium school in India. They know everyday English but not formal, academic or idiomatic English.
FAIL if the lesson contains: idioms or non-literal phrases; rare/formal words where a common word works (e.g. "leverage", "facilitate", "paramount", "seamless", "robust"); phrasal slang; or references to things outside an Indian student's daily life without explanation.
In "hard_words", list each word/phrase that should be replaced (empty list if none).""",

    "examples": """Required:
(a) an everyday ANALOGY for the core idea that an Indian student would relate to (e.g. an open-book exam, a library, a kirana shop), clearly mapped to the technical idea;
(b) a concrete WORKED EXAMPLE that shows, step by step: a real question, the retrieved information, what is sent to the model (question + retrieved information), and the final answer.
FAIL if either is missing, vague, or does not match the technical idea.""",

    "flow": """Check the teaching order as a learner reading top to bottom:
- every idea is introduced before it is used;
- the lesson starts from the problem, then the idea, then how it works;
- the worked example follows the same steps as "How does it work?";
- nothing contradicts anything said elsewhere (including the quiz and takeaways).
FAIL if a learner would get lost or confused at a specific point - quote that point.""",
}

JUDGE_SCHEMA = {
    "key_points": '{"verdict": "PASS" or "FAIL", "points": [{"id": "kp id", "covered": true/false, "quote": "exact quote that teaches it, or empty"}], "reason": "...", "evidence": ["exact quotes of problem text, if any"], "fix": "..."}',
    "plain_language": '{"verdict": "PASS" or "FAIL", "reason": "...", "evidence": ["exact quotes"], "hard_words": [{"word": "word or phrase", "simpler": "replacement"}], "fix": "..."}',
    "jargon_explained": '{"verdict": "PASS" or "FAIL", "terms": [{"term": "...", "explained_at_first_use": true/false}], "unexplained_other_words": ["..."], "reason": "...", "evidence": ["exact quotes"], "fix": "..."}',
}

# ========================================================================= reflection
REFLECT_SYSTEM = """You improve an AI lesson-writing system by turning reviewer rejections into short, general writing rules.
Rules must be: general (useful for ANY beginner AI topic, not only this lesson), actionable (a writer can follow it), and short (max 25 words).
Do not repeat a rule that already exists - reference it instead."""

REFLECT_USER = """In this run, these checks FAILED (attempt, check, reason, fix requested):
{failures}

Checks that failed on the first attempt AND were fixed by revision: {fixed}
Checks still failing at the end: {unfixed}

EXISTING RULES (id: rule):
{existing}

RULES FLAGGED AS NOT WORKING (their check kept failing even with the rule in the prompt):
{flagged}

Return JSON:
{{
  "new_rules": [{{"rule": "...", "check_id": "the check it prevents"}}],
  "reinforce": ["ids of existing rules that would have prevented a failure in this run"],
  "rewrite": [{{"id": "flagged rule id", "rule": "a clearer, more specific version"}}]
}}
Add at most 3 new rules. If the failures are already covered by existing rules, add none and reinforce them."""

FEEDBACK_SYSTEM = """You turn human feedback about a generated beginner lesson into concrete updates for an AI lesson system."""

FEEDBACK_USER = """Human feedback: "{text}"
{check_hint}
Available check ids: {check_ids}

Return JSON:
{{
  "guidance_rules": [{{"rule": "short general writing rule for future lessons (max 25 words)", "check_id": "related check id or null"}}],
  "jargon_terms": [{{"term": "a word the learner found hard", "regex": "case-insensitive python regex matching it"}}],
  "calibration": [{{"check_id": "id", "note": "note for that check's reviewer, e.g. what should or should not count as a failure"}}]
}}
Use empty lists where nothing applies."""


def checks_table() -> str:
    return _bullets(f"{c.id} [{c.kind}] - {c.criterion}" for c in CHECKS)


__all__ = [
    "WRITER_SYSTEM", "PLAN_USER", "WRITE_USER", "REVISE_USER", "JUDGE_SYSTEM", "JUDGE_BASE",
    "BASE_SCHEMA", "JUDGE_CONTEXT", "JUDGE_SCHEMA", "REFLECT_SYSTEM", "REFLECT_USER",
    "FEEDBACK_SYSTEM", "FEEDBACK_USER", "template_headings", "guidance_block", "checks_table", "LIMITS",
]
