"""Writes run artefacts: every attempt, every evaluation, the final lesson, the rejection log."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .rubric import CHECKS


def _cell(passed: bool) -> str:
    return "✅" if passed else "❌"


def _words(report) -> str:
    r = next((r for r in report.results if r.id == "length"), None)
    return str(r.details.get("words", "?")) if r else "?"


def render_rejection_log(state: dict) -> str:
    spec, attempts = state["spec"], state["attempts"]
    best = attempts[state["best_index"]]
    L: list[str] = []
    L.append(f"# Rejection log - {spec.title}\n")
    L.append(f"- **Run:** `{state['run_id']}`")
    L.append(f"- **Writer model:** {state['writer_model']}  |  **Judge model:** {state['judge_model']}")
    L.append(f"- **Topic spec:** `{Path(spec.path).name}` ({'human-verified' if spec.verified else 'AUTO-GENERATED - facts not human-verified'})")
    L.append(f"- **Outcome:** **{state['status']}** after {len(attempts)} attempt(s) (max {state['max_retries'] + 1}). "
             f"Final lesson = attempt {best['n']}.")
    if state.get("injected"):
        L.append(f"- **Deliberate error injected into attempt 1:** {state['injected']}")
    u = state.get("usage")
    if u:
        L.append(f"- **LLM usage:** {u.calls} calls, {u.input_tokens:,} input / {u.output_tokens:,} output tokens, {u.seconds:.0f}s")
    if state.get("guidance"):
        L.append(f"- **Rules from memory applied to the writer:** {len(state['guidance'])} "
                 f"({', '.join(g['id'] for g in state['guidance'])})")
    L.append("")

    # Scoreboard
    L.append("## Scoreboard (every check, every attempt)\n")
    L.append("| Check | Kind | Dimension | " + " | ".join(f"Attempt {a['n']}" for a in attempts) + " |")
    L.append("|---|---|---|" + "---|" * len(attempts))
    for c in CHECKS:
        row = [_cell(a["report"].as_map().get(c.id, False)) for a in attempts]
        L.append(f"| `{c.id}` | {c.kind} | {c.dimension} | " + " | ".join(row) + " |")
    L.append("| **Verdict** | | | " + " | ".join("**SHIP**" if a["report"].passed else "REJECT" for a in attempts) + " |")
    L.append("| Words / FK grade | | | " + " | ".join(
        f"{_words(a['report'])} / {a['report'].stats.get('fk_grade', '?')}" for a in attempts) + " |")
    L.append("")

    # Per attempt detail
    for i, a in enumerate(attempts):
        rep = a["report"]
        L.append(f"## Attempt {a['n']} - {'PASSED' if rep.passed else 'REJECTED'}\n")
        if a.get("injected"):
            L.append(f"> Deliberate error injected before evaluation: {a['injected']}\n")
        if a.get("changes"):
            L.append("**What the reviser changed to get here (from the previous attempt's failures):**\n")
            L.extend(f"- {c}" for c in a["changes"])
            L.append("")
        if rep.failed:
            L.append("**What failed and why:**\n")
            for r in rep.failed:
                L.append(f"- ❌ **`{r.id}`** ({r.kind} · {r.dimension}) - {r.reason}")
                for e in r.evidence[:4]:
                    L.append(f"  - evidence: \"{e.strip()[:240]}\"")
                if r.fix:
                    L.append(f"  - fix requested: {r.fix[:400]}")
            L.append("")
            if i + 1 < len(attempts):
                fixed = {r.id for r in rep.failed} - {r.id for r in attempts[i + 1]["report"].failed}
                broke = {r.id for r in attempts[i + 1]["report"].failed} - {r.id for r in rep.failed}
                L.append(f"**Result of the retry:** fixed {', '.join(sorted(fixed)) or 'nothing'}"
                         + (f"; newly broke {', '.join(sorted(broke))}" if broke else "") + ".\n")
        else:
            L.append("All checks passed.\n")

    if state.get("memory_notes"):
        L.append("## What the system learned from this run (memory updates)\n")
        L.extend(f"- {n}" for n in state["memory_notes"])
        L.append("")
    return "\n".join(L)


def write_run(state: dict, run_dir: Path, output_dir: Path) -> dict[str, Path]:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "plan.json").write_text(json.dumps(state.get("plan", {}), indent=2, ensure_ascii=False), encoding="utf-8")
    for a in state["attempts"]:
        (run_dir / f"attempt_{a['n']}.md").write_text(a["lesson"], encoding="utf-8")
        (run_dir / f"eval_attempt_{a['n']}.json").write_text(
            json.dumps({"changes": a.get("changes"), "injected": a.get("injected"), **a["report"].to_dict()},
                       indent=2, ensure_ascii=False), encoding="utf-8")
    best = state["attempts"][state["best_index"]]
    lesson = best["lesson"]
    if state["status"] != "SHIPPED":
        lesson = ("> ⚠️ **NOT SHIPPED - needs human review.** This is the best attempt but it still fails: "
                  + ", ".join(r.id for r in best["report"].failed) + ". See rejection_log.md.\n\n" + lesson)
    lesson_name = "lesson.md" if state["status"] == "SHIPPED" else "lesson_NEEDS_REVIEW.md"
    log = render_rejection_log(state)
    (run_dir / lesson_name).write_text(lesson, encoding="utf-8")
    (run_dir / "rejection_log.md").write_text(log, encoding="utf-8")
    (run_dir / "rejection_log.json").write_text(json.dumps({
        "run_id": state["run_id"], "topic": state["spec"].title, "status": state["status"],
        "final_attempt": best["n"], "injected": state.get("injected"),
        "attempts": [{"n": a["n"], "changes": a.get("changes"), **a["report"].to_dict()} for a in state["attempts"]],
        "memory_notes": state.get("memory_notes", []),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in ("lesson.md", "lesson_NEEDS_REVIEW.md"):
        (output_dir / stale).unlink(missing_ok=True)
    shutil.copy(run_dir / lesson_name, output_dir / lesson_name)
    shutil.copy(run_dir / "rejection_log.md", output_dir / "rejection_log.md")
    return {"lesson": output_dir / lesson_name, "log": output_dir / "rejection_log.md", "run_dir": run_dir}
