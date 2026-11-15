"""The agent loop as a LangGraph state machine.

    load_memory -> plan -> write -> evaluate --pass--------------------> decide -> learn -> report
                                       ^   \\--fail & retries left--> revise
                                       |                               |
                                       +-------------------------------+
                                     (fail & no retries left) ---------> decide

The loop always terminates: at most 1 + max_retries evaluations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from . import agents
from .config import OUTPUT_DIR, RUNS_DIR
from .evaluator import Evaluator
from .inject import inject
from .learn import reflect_on_run
from .llm import LLM, Usage
from .memory import Memory, now
from .report import write_run
from .topic_spec import TopicSpec


class RunState(TypedDict, total=False):
    run_id: str
    spec: TopicSpec
    max_retries: int
    inject_error: str | None
    injected: str | None
    guidance: list[dict]
    plan: dict
    lesson: str
    pending_changes: list[str] | None
    attempts: list[dict]
    status: str
    best_index: int
    memory_notes: list[str]
    writer_model: str
    judge_model: str
    usage: Usage
    outputs: dict


@dataclass
class Deps:
    writer: LLM
    judge: LLM
    memory: Memory
    evaluator: Evaluator
    log: Callable[[str], None] = print
    runs_dir: Path = RUNS_DIR
    output_dir: Path = OUTPUT_DIR
    learn: bool = True


def route_after_eval(state: RunState) -> str:
    """Pure function - the loop's termination guarantee lives here."""
    last = state["attempts"][-1]
    if last["report"].passed:
        return "decide"
    if len(state["attempts"]) <= state["max_retries"]:
        return "revise"
    return "decide"


def pick_best(attempts: list[dict]) -> int:
    """Passing attempt if any; else fewest accuracy failures, then fewest failures, then latest."""
    def key(i: int):
        rep = attempts[i]["report"]
        acc_fail = sum(1 for r in rep.failed if r.dimension == "accurate & grounded")
        return (rep.passed, -acc_fail, -len(rep.failed), i)
    return max(range(len(attempts)), key=key)


def build_graph(d: Deps):
    def load_memory(state: RunState) -> dict:
        rules = d.memory.active_guidance()
        d.log(f"[memory] {len(rules)} learned rule(s) applied to the writer; "
              f"{len(d.memory.enforced_jargon())} learned jargon term(s) enforced by the rubric.")
        return {"guidance": rules, "attempts": [], "pending_changes": None}

    def plan(state: RunState) -> dict:
        d.log("[plan] planning lesson structure, analogy and worked example ...")
        p = agents.plan_lesson(d.writer, state["spec"], state["guidance"])
        d.log(f"[plan] analogy: {str(p.get('main_analogy', ''))[:110]}")
        return {"plan": p}

    def write(state: RunState) -> dict:
        d.log("[write] writing first draft ...")
        md = agents.write_lesson(d.writer, state["spec"], state["plan"], state["guidance"])
        injected = None
        if state.get("inject_error"):
            md, injected = inject(md, state["inject_error"])
            d.log(f"[inject] deliberate error added to draft 1: {injected}")
        return {"lesson": md, "injected": injected}

    def evaluate(state: RunState) -> dict:
        n = len(state["attempts"]) + 1
        d.log(f"[evaluate] attempt {n}: running 7 code checks + 6 LLM judges ...")
        rep = d.evaluator.evaluate(state["lesson"])
        for r in rep.results:
            d.log(f"    {'PASS' if r.passed else 'FAIL'}  {r.id:<24} {'' if r.passed else r.reason[:110]}")
        d.log(f"[evaluate] attempt {n}: {'SHIP' if rep.passed else 'REJECT'} "
              f"({sum(r.passed for r in rep.results)}/{len(rep.results)} checks passed)")
        attempt = {
            "n": n, "lesson": state["lesson"], "report": rep,
            "changes": state.get("pending_changes"),
            "injected": state.get("injected") if n == 1 else None,
        }
        return {"attempts": state["attempts"] + [attempt], "pending_changes": None}

    def revise(state: RunState) -> dict:
        last = state["attempts"][-1]
        failed = last["report"].failed
        d.log(f"[revise] feeding {len(failed)} failure(s) back to the writer: {', '.join(r.id for r in failed)}")
        short = state["plan"].get("short_name") or state["spec"].slug.upper()
        md, changes = agents.revise_lesson(
            d.writer, state["spec"], last["lesson"], failed,
            [r.id for r in last["report"].results if r.passed], short, state["guidance"],
        )
        for c in changes[:8]:
            d.log(f"    change: {c[:120]}")
        return {"lesson": md, "pending_changes": changes}

    def decide(state: RunState) -> dict:
        best = pick_best(state["attempts"])
        status = "SHIPPED" if state["attempts"][best]["report"].passed else "BLOCKED"
        d.log(f"[decide] {status} (final = attempt {state['attempts'][best]['n']})")
        return {"best_index": best, "status": status}

    def learn(state: RunState) -> dict:
        if not d.learn:
            return {"memory_notes": ["(learning disabled for this run)"]}
        meta = {
            "run_id": state["run_id"], "topic": state["spec"].title, "status": state["status"],
            "attempts": len(state["attempts"]), "injected": state.get("injected"), "finished": now(),
            "first_attempt_failed": [r.id for r in state["attempts"][0]["report"].failed],
            "final_failed": [r.id for r in state["attempts"][state["best_index"]]["report"].failed],
        }
        notes = reflect_on_run(d.writer, d.memory, state["attempts"], [g["id"] for g in state["guidance"]], meta)
        d.memory.save()
        for n in notes:
            d.log(f"[learn] {n}")
        return {"memory_notes": notes}

    def report(state: RunState) -> dict:
        outs = write_run(dict(state), d.runs_dir / state["run_id"], d.output_dir)
        d.log(f"[report] lesson -> {outs['lesson']}\n[report] rejection log -> {outs['log']}")
        return {"outputs": {k: str(v) for k, v in outs.items()}}

    g = StateGraph(RunState)
    for name, fn in [("load_memory", load_memory), ("plan", plan), ("write", write), ("evaluate", evaluate),
                     ("revise", revise), ("decide", decide), ("learn", learn), ("report", report)]:
        g.add_node(name, fn)
    g.add_edge(START, "load_memory")
    g.add_edge("load_memory", "plan")
    g.add_edge("plan", "write")
    g.add_edge("write", "evaluate")
    g.add_conditional_edges("evaluate", route_after_eval, {"revise": "revise", "decide": "decide"})
    g.add_edge("revise", "evaluate")
    g.add_edge("decide", "learn")
    g.add_edge("learn", "report")
    g.add_edge("report", END)
    return g.compile()


def run_pipeline(spec: TopicSpec, d: Deps, max_retries: int = 2, inject_error: str | None = None) -> dict[str, Any]:
    if not 0 <= max_retries <= 2:
        raise ValueError("max_retries must be 0, 1 or 2 (the loop must terminate quickly)")
    app = build_graph(d)
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{spec.slug}"
    init: RunState = {
        "run_id": run_id, "spec": spec, "max_retries": max_retries, "inject_error": inject_error,
        "writer_model": f"{d.writer.cfg.provider}/{d.writer.cfg.model}",
        "judge_model": f"{d.judge.cfg.provider}/{d.judge.cfg.model}",
        "usage": d.writer.usage,
    }
    return app.invoke(init, {"recursion_limit": 50})
