"""Command line interface.

  python -m lessongen run --topic "Introduction to RAG"                    # full loop
  python -m lessongen run --topic "Introduction to RAG" --inject-error misconception
  python -m lessongen evaluate output/lesson.md --inject-error jargon     # evaluator demo
  python -m lessongen evaluate output/lesson.md --code-only               # no API key needed
  python -m lessongen feedback "Students did not understand 'vector'"     # human feedback -> memory
  python -m lessongen memory                                              # what has been learned
  python -m lessongen rubric                                              # print the rubric
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .config import load_settings
from .evaluator import Evaluator, report_to_text
from .graph import Deps, run_pipeline
from .inject import KINDS, inject
from .learn import apply_feedback
from .llm import LLM, LLMError, ReplayLLM, Usage
from .memory import Memory
from .rubric import CHECKS
from .topic_spec import get_spec

console = Console()


def _log(msg: str) -> None:
    style = None
    if "FAIL" in msg[:12] or "REJECT" in msg or "BLOCKED" in msg:
        style = "red"
    elif msg.strip().startswith("PASS") or "SHIP" in msg:
        style = "green"
    elif msg.startswith("[inject]"):
        style = "bold magenta"
    elif msg.startswith("[learn]") or msg.startswith("[memory]"):
        style = "cyan"
    console.print(msg, style=style, highlight=False, markup=False)


def _llms():
    s = load_settings()
    usage = Usage()
    if s.writer.provider == "replay":  # pre-written responses; one shared queue for all roles
        replay = ReplayLLM(os.getenv("REPLAY_DIR", "replay/demo"), usage)
        return s, replay, replay, usage
    return s, LLM(s.writer, usage), LLM(s.judge, usage), usage


def cmd_run(a) -> int:
    s, writer, judge, usage = _llms()
    memory = Memory()
    spec = get_spec(a.topic, writer)
    console.rule(f"[bold]Lesson generator - {spec.title}")
    console.print(f"writer={s.writer.provider}/{s.writer.model}  judge={s.judge.provider}/{s.judge.model}  "
                  f"max_retries={a.max_retries}  spec={Path(spec.path).name} ({'verified' if spec.verified else 'AUTO-GENERATED'})",
                  highlight=False)
    deps = Deps(writer=writer, judge=judge, memory=memory,
                evaluator=Evaluator(spec, memory, judge, workers=s.judge_workers), log=_log, learn=not a.no_learn)
    final = run_pipeline(spec, deps, max_retries=a.max_retries, inject_error=a.inject_error)
    console.rule(f"[bold]{final['status']}")
    console.print(f"{usage.calls} LLM calls · {usage.input_tokens:,} in / {usage.output_tokens:,} out tokens · {usage.seconds:.0f}s",
                  highlight=False)
    return 0 if final["status"] == "SHIPPED" else 2


def cmd_evaluate(a) -> int:
    md = Path(a.file).read_text(encoding="utf-8")
    memory = Memory()
    judge = None
    if not a.code_only:
        _, _, judge, _ = _llms()
    spec = get_spec(a.topic, judge)
    if a.inject_error:
        md, desc = inject(md, a.inject_error)
        console.print(f"[inject] {desc}", style="bold magenta", markup=False)
        if a.save_injected:
            Path(a.save_injected).write_text(md, encoding="utf-8")
    rep = Evaluator(spec, memory, judge).evaluate(md, code_only=a.code_only)
    for line in report_to_text(rep).splitlines():
        _log(line)
    if a.json:
        Path(a.json).write_text(json.dumps(rep.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if rep.passed else 1


def cmd_feedback(a) -> int:
    memory = Memory()
    llm = None
    if a.text and not a.no_llm:
        _, llm, _, _ = _llms()
    actions = apply_feedback(llm, memory, a.text or "", check_id=a.check, run_id=a.run,
                             rule=a.rule, jargon=a.jargon, calibrate=a.calibrate)
    for x in actions or ["(nothing to apply)"]:
        console.print(f"[memory] {x}", style="cyan", markup=False)
    return 0


def cmd_memory(a) -> int:
    m = Memory()
    console.print_json(json.dumps(m.summary()))
    t = Table(title="Per-check failure rates (all runs)")
    for col in ("check", "evaluated", "failed", "1st-attempt fail rate"):
        t.add_column(col)
    for cid, s in sorted(m.data["check_stats"].items(), key=lambda kv: -kv[1]["first_attempt_failed"]):
        rate = s["first_attempt_failed"] / s["first_attempt_evaluated"] if s["first_attempt_evaluated"] else 0
        t.add_row(cid, str(s["evaluated"]), str(s["failed"]), f"{rate:.0%}")
    console.print(t)
    g = Table(title="Learned guidance (injected into the writer's prompt)")
    for col in ("id", "source", "check", "reinforced", "1st-try pass/fail when applied", "active", "rule"):
        g.add_column(col)
    for r in m.data["guidance"]:
        g.add_row(r["id"], r["source"], str(r.get("check_id")), str(r.get("times_reinforced")),
                  f"{r.get('applied_first_pass', 0)}/{r.get('applied_first_fail', 0)}" + (" ⚑" if r.get("flag") else ""),
                  "yes" if r.get("active", True) else "no", r["rule"])
    console.print(g)
    return 0


def cmd_rubric(a) -> int:
    t = Table(title="Rubric - every check is hard pass/fail; the lesson ships only if all pass")
    for col in ("id", "kind", "dimension", "passes when"):
        t.add_column(col)
    for c in CHECKS:
        t.add_row(c.id, c.kind, c.dimension, c.criterion)
    console.print(t)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lessongen", description="Self-evaluating beginner lesson generator")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="generate -> evaluate -> regenerate until it ships (or retries run out)")
    r.add_argument("--topic", default="Introduction to RAG")
    r.add_argument("--max-retries", type=int, default=load_settings().max_retries, choices=[0, 1, 2])
    r.add_argument("--inject-error", choices=KINDS, help="corrupt the first draft to show the evaluator catching it")
    r.add_argument("--no-learn", action="store_true", help="do not update memory from this run")
    r.set_defaults(fn=cmd_run)

    e = sub.add_parser("evaluate", help="evaluate an existing lesson file")
    e.add_argument("file")
    e.add_argument("--topic", default="Introduction to RAG")
    e.add_argument("--code-only", action="store_true", help="only deterministic checks (no API key needed)")
    e.add_argument("--inject-error", choices=KINDS)
    e.add_argument("--save-injected", help="write the corrupted lesson to this path")
    e.add_argument("--json", help="write the full report as JSON to this path")
    e.set_defaults(fn=cmd_evaluate)

    f = sub.add_parser("feedback", help="give human feedback; it is turned into memory updates")
    f.add_argument("text", nargs="?", default="")
    f.add_argument("--check", help="check id the feedback is about")
    f.add_argument("--run", help="run id the feedback is about")
    f.add_argument("--rule", help="add this writing rule directly (no LLM)")
    f.add_argument("--jargon", nargs="*", help="enforce these words as jargon (no LLM)")
    f.add_argument("--calibrate", help="add a calibration note for --check's judge (no LLM)")
    f.add_argument("--no-llm", action="store_true")
    f.set_defaults(fn=cmd_feedback)

    sub.add_parser("memory", help="show what the system has learned").set_defaults(fn=cmd_memory)
    sub.add_parser("rubric", help="print the rubric").set_defaults(fn=cmd_rubric)

    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except LLMError as e:
        console.print(f"LLM error: {e}", style="bold red", markup=False)
        return 3


if __name__ == "__main__":
    sys.exit(main())
