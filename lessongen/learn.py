"""Self-evolution: turn this run's failures (and human feedback) into memory updates."""
from __future__ import annotations

import re

from . import prompts as P
from .llm import LLM, LLMError
from .memory import JARGON_PROMOTE_AT, Memory
from .rubric import CHECK_BY_ID, CHECKS


def _bul(items) -> str:
    return "\n".join(f"- {x}" for x in items) or "- (none)"


def reflect_on_run(llm: LLM | None, memory: Memory, attempts: list[dict], applied_ids: list[str], run_meta: dict) -> list[str]:
    """Update memory from one finished run. Returns human-readable notes for the log."""
    notes: list[str] = []
    results = [a["report"].as_map() for a in attempts]
    memory.record_run(run_meta, results, applied_ids)

    # 1) Rubric evolution: words judges flagged as hard. Promote after repeated sightings.
    seen: set[str] = set()
    for a in attempts:
        for hw in a["report"].hard_words:
            w = str(hw.get("word", "")).strip()
            if not w or w.lower() in seen or len(w) > 40:
                continue
            seen.add(w.lower())
            if memory.note_hard_word(w, r"\b" + re.escape(w) + r"\b"):
                notes.append(f"Rubric updated: '{w}' was flagged in {JARGON_PROMOTE_AT}+ runs and is now an enforced jargon term "
                             "(must be explained and in the Glossary).")
    if seen:
        notes.append("Hard words noted this run: " + ", ".join(sorted(seen)))

    # 2) Prompt evolution: distil failures into general writing rules.
    failures = [(a["n"], r) for a in attempts for r in a["report"].failed]
    if not failures:
        notes.append("No failures this run - no new rules needed.")
        return notes
    first_failed = {r.id for r in attempts[0]["report"].failed}
    last_failed = {r.id for r in attempts[-1]["report"].failed}
    fixed = sorted(first_failed - last_failed)
    existing = memory.active_guidance(limit=50)
    flagged = memory.flagged_guidance()
    try:
        if llm is None:
            raise LLMError("no reflection model")
        d = llm.complete_json(
            "reflect",
            P.REFLECT_SYSTEM,
            P.REFLECT_USER.format(
                failures=_bul(f"attempt {n} | {r.id} | {r.reason[:200]} | fix: {r.fix[:200]}" for n, r in failures),
                fixed=", ".join(fixed) or "none",
                unfixed=", ".join(sorted(last_failed)) or "none",
                existing=_bul(f"{g['id']}: {g['rule']}" for g in existing),
                flagged=_bul(f"{g['id']}: {g['rule']}" for g in flagged),
            ),
        )
        for nr in (d.get("new_rules") or [])[:3]:
            rule, cid = str(nr.get("rule", "")).strip(), nr.get("check_id")
            if rule:
                g = memory.add_guidance(rule, cid if cid in CHECK_BY_ID else None, source="auto")
                notes.append(f"New rule {g['id']} (for {g['check_id']}): {g['rule']}")
        for gid in d.get("reinforce") or []:
            memory.reinforce(str(gid))
            notes.append(f"Reinforced rule {gid}")
        for rw in d.get("rewrite") or []:
            if rw.get("id") and rw.get("rule"):
                memory.rewrite_guidance(str(rw["id"]), str(rw["rule"]))
                notes.append(f"Rewrote ineffective rule {rw['id']}: {rw['rule']}")
    except LLMError as e:
        # Fallback keeps learning even if the reflection call fails: one rule per failed check.
        for cid in sorted(first_failed):
            g = memory.add_guidance(f"Before finishing, re-check: {CHECK_BY_ID[cid].criterion}", cid, source="auto")
            notes.append(f"(fallback, reflection failed: {e}) rule {g['id']}: {g['rule']}")
    return notes


def apply_feedback(llm: LLM | None, memory: Memory, text: str, check_id: str | None = None,
                   run_id: str | None = None, rule: str | None = None, jargon: list[str] | None = None,
                   calibrate: str | None = None) -> list[str]:
    """Human feedback -> guidance rules / enforced jargon / judge calibration notes."""
    actions: list[str] = []
    # Direct, no-LLM paths (precise control).
    if rule:
        g = memory.add_guidance(rule, check_id, source="human")
        actions.append(f"rule {g['id']}: {g['rule']}")
    for term in jargon or []:
        memory.data["learned_jargon"][term.lower()] = {"regex": r"\b" + re.escape(term) + r"\w*", "count": 99,
                                                       "enforced": True, "source": "human"}
        actions.append(f"enforced jargon term: {term}")
    if calibrate and check_id:
        memory.add_calibration(check_id, calibrate, source="human")
        actions.append(f"calibration note for {check_id}: {calibrate}")
    # Free-text path: let the LLM route the feedback.
    if text and llm is not None:
        d = llm.complete_json(
            "feedback",
            P.FEEDBACK_SYSTEM,
            P.FEEDBACK_USER.format(
                text=text,
                check_hint=f"The human says this is about check: {check_id}" if check_id else "",
                check_ids=", ".join(c.id for c in CHECKS),
            ),
        )
        for r in d.get("guidance_rules") or []:
            if r.get("rule"):
                g = memory.add_guidance(r["rule"], r.get("check_id") if r.get("check_id") in CHECK_BY_ID else None, source="human")
                actions.append(f"rule {g['id']}: {g['rule']}")
        for j in d.get("jargon_terms") or []:
            term, rx = str(j.get("term", "")).strip(), str(j.get("regex", "")).strip()
            if term:
                try:
                    re.compile(rx)
                except re.error:
                    rx = r"\b" + re.escape(term) + r"\w*"
                memory.data["learned_jargon"][term.lower()] = {"regex": rx or r"\b" + re.escape(term), "count": 99,
                                                               "enforced": True, "source": "human"}
                actions.append(f"enforced jargon term: {term}")
        for c in d.get("calibration") or []:
            if c.get("check_id") in CHECK_BY_ID and c.get("note"):
                memory.add_calibration(c["check_id"], c["note"], source="human")
                actions.append(f"calibration note for {c['check_id']}: {c['note']}")
    memory.add_feedback({"text": text, "check_id": check_id, "run_id": run_id, "actions": actions})
    memory.save()
    return actions
