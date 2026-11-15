"""Generation agents: planner, writer, reviser."""
from __future__ import annotations

import json
import re

from . import prompts as P
from .checks_code import CheckResult
from .llm import LLM, LLMError
from .rubric import CHECK_BY_ID, CHECKS
from .topic_spec import TopicSpec


def _bul(items) -> str:
    return "\n".join(f"- {x}" for x in items)


def _spec_blocks(spec: TopicSpec) -> dict:
    return {
        "key_points": _bul(f"{k['id']}: {k['text'].strip()}" for k in spec.key_points),
        "facts": _bul(spec.reference_facts),
        "misconceptions": _bul(spec.misconceptions),
    }


def writer_system(spec: TopicSpec) -> str:
    return P.WRITER_SYSTEM.format(
        learner=spec.learner_profile.strip(), min_words=P.LIMITS["min_words"], max_words=P.LIMITS["max_words"] - 400
    )


def plan_lesson(llm: LLM, spec: TopicSpec, guidance: list[dict]) -> dict:
    short = spec.slug.upper() if len(spec.slug) <= 5 else spec.title.split("(")[0].strip()
    plan = llm.complete_json(
        "plan",
        writer_system(spec),
        P.PLAN_USER.format(
            title=spec.title,
            guidance=P.guidance_block(guidance),
            headings=P.template_headings(short),
            **_spec_blocks(spec),
        ),
    )
    plan.setdefault("short_name", short)
    return plan


def clean_markdown(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    # Drop chatter before the title, if any.
    i = text.find("# ")
    if i > 0 and not text[:i].strip().startswith("#"):
        text = text[i:]
    return text.strip() + "\n"


def write_lesson(llm: LLM, spec: TopicSpec, plan: dict, guidance: list[dict]) -> str:
    short = plan.get("short_name") or spec.slug.upper()
    text = llm.complete(
        "write",
        writer_system(spec),
        P.WRITE_USER.format(
            title=spec.title,
            plan=json.dumps(plan, indent=2, ensure_ascii=False),
            guidance=P.guidance_block(guidance),
            headings=P.template_headings(short),
            quiz_min=P.LIMITS["quiz_min"],
            quiz_max=P.LIMITS["quiz_max"],
            **_spec_blocks(spec),
        ),
        max_tokens=8000,
    )
    return clean_markdown(text)


def _failure_block(failed: list[CheckResult]) -> str:
    parts = []
    for r in failed:
        ev = "".join(f'\n    problem text: "{e}"' for e in r.evidence[:5])
        parts.append(f"- {r.id}: {CHECK_BY_ID[r.id].criterion}\n    why it failed: {r.reason}{ev}\n    how to fix: {r.fix}")
    return "\n".join(parts)


def revise_lesson(llm: LLM, spec: TopicSpec, lesson: str, failed: list[CheckResult],
                  passed_ids: list[str], short: str, guidance: list[dict]) -> tuple[str, list[str]]:
    text = llm.complete(
        "revise",
        writer_system(spec),
        P.REVISE_USER.format(
            failures=_failure_block(failed),
            passing=_bul(f"{c}: {CHECK_BY_ID[c].criterion}" for c in passed_ids) or "- (none)",
            guidance=P.guidance_block(guidance),
            headings=P.template_headings(short),
            lesson=lesson,
            **_spec_blocks(spec),
        ),
        max_tokens=9000,
    )
    m_l = re.search(r"<lesson>\s*(.*?)\s*(?:</lesson>|$)", text, re.DOTALL)
    m_c = re.search(r"<changes>\s*(.*?)\s*</changes>", text, re.DOTALL)
    if not m_l or "# " not in m_l.group(1):
        raise LLMError("reviser did not return a <lesson> block")
    changes = [re.sub(r"^\s*[-*]\s*", "", c).strip() for c in (m_c.group(1).splitlines() if m_c else []) if c.strip()]
    return clean_markdown(m_l.group(1)), changes or ["(reviser did not list its changes)"]


ALL_CHECK_IDS = [c.id for c in CHECKS]
