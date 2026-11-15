"""Offline tests: deterministic checks, judge guards, and the full LangGraph loop
driven by a scripted FakeLLM (no API key needed)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lessongen.checks_code import run_code_checks
from lessongen.evaluator import Evaluator
from lessongen.graph import Deps, route_after_eval, run_pipeline
from lessongen.inject import inject
from lessongen.learn import apply_feedback
from lessongen.llm import FakeLLM, LLMError, Usage, parse_json
from lessongen.memory import Memory
from lessongen.textutils import quote_in_text
from lessongen.topic_spec import find_spec

FIX = Path(__file__).parent / "fixtures"
GOOD = (FIX / "good_lesson.md").read_text(encoding="utf-8")
SPEC = find_spec("Introduction to RAG")

KP_QUOTES = {
    "kp1_llm_limits": "This is called hallucination.",
    "kp2_definition": "So, in simple words, RAG means: first find the right information, then add it to the question, then let the LLM write the answer.",
    "kp3_name": "Retrieval means finding.",
    "kp4_prepare": "Each piece is called a chunk.",
    "kp5_answer": "This is called similarity search.",
    "kp6_why": "To update what the system knows, you only update the documents.",
    "kp7_limits": "So RAG reduces hallucination.",
    "kp8_uses": "RAG is used in help chatbots for companies",
}


def lesson_of(user_prompt: str) -> str:
    if "<lesson>" in user_prompt:
        return user_prompt.split("<lesson>", 1)[1].split("</lesson>", 1)[0]
    return user_prompt


def make_handler(reviser_fixes: bool = True, hard_word: str | None = None, fake_kp_quote: bool = False):
    bad, _ = inject(GOOD, "misconception")

    def handler(task: str, system: str, user: str) -> str:
        if task == "plan":
            return json.dumps({"short_name": "RAG", "main_analogy": "open-book exam", "sections": []})
        if task == "write":
            return bad
        if task == "revise":
            fixed = GOOD if reviser_fixes else bad
            return f"<changes>\n- accuracy: removed the false retraining claim\n</changes>\n<lesson>\n{fixed}\n</lesson>"
        if task == "reflect":
            return json.dumps({"new_rules": [{"rule": "Never say RAG retrains or changes the model; it only adds text to the prompt.",
                                              "check_id": "accuracy"}], "reinforce": [], "rewrite": []})
        if task.startswith("judge:"):
            cid = task.split(":")[1]
            lesson = lesson_of(user)
            if cid == "accuracy" and "retrains the AI model" in lesson:
                return json.dumps({"verdict": "FAIL", "reason": "Says RAG retrains the model.",
                                   "evidence": ["RAG retrains the AI model on your documents"], "fix": "Remove it."})
            if cid == "key_points":
                pts = [{"id": k, "covered": True, "quote": ("made-up quote not in lesson" if fake_kp_quote and k == "kp8_uses" else q)}
                       for k, q in KP_QUOTES.items()]
                return json.dumps({"verdict": "PASS", "points": pts, "reason": "ok", "evidence": [], "fix": ""})
            if cid == "plain_language" and hard_word:
                return json.dumps({"verdict": "PASS", "reason": "ok", "evidence": [], "fix": "",
                                   "hard_words": [{"word": hard_word, "simpler": "use"}]})
            return json.dumps({"verdict": "PASS", "reason": "ok", "evidence": [], "fix": ""})
        raise AssertionError(f"unexpected task {task}")

    return handler


def deps_for(tmp_path: Path, handler, memory: Memory | None = None) -> Deps:
    usage = Usage()
    llm = FakeLLM(handler, usage)
    mem = memory or Memory(tmp_path / "memory.json")
    return Deps(writer=llm, judge=llm, memory=mem, evaluator=Evaluator(SPEC, mem, llm, workers=2),
                log=lambda m: None, runs_dir=tmp_path / "runs", output_dir=tmp_path / "out")


# ----------------------------------------------------------------------------- code checks
def test_good_lesson_passes_all_code_checks():
    res = run_code_checks(GOOD, SPEC.jargon_patterns())
    assert all(r.passed for r in res), [(r.id, r.reason) for r in res if not r.passed]


@pytest.mark.parametrize("kind,expected", [
    ("misconception", "misconception_tripwire"),
    ("jargon", "glossary_coverage"),
    ("long_sentence", "sentence_length"),
    ("drop_example", "structure"),
    ("wrong_quiz", "misconception_tripwire"),
])
def test_injected_errors_are_caught_by_code(kind, expected):
    md, _ = inject(GOOD, kind)
    failed = {r.id for r in run_code_checks(md, SPEC.jargon_patterns()) if not r.passed}
    assert expected in failed


def test_tripwire_ignores_negated_and_comparative_sentences():
    md = GOOD.replace("RAG does not change the LLM.", "RAG does not retrain the model. RAG is faster than retraining the model.")
    res = {r.id: r for r in run_code_checks(md, SPEC.jargon_patterns())}
    assert res["misconception_tripwire"].passed


def test_quote_verification():
    assert quote_in_text("Each piece is called a  chunk", GOOD)
    assert quote_in_text("**Retrieval** means finding.", GOOD)
    assert not quote_in_text("RAG fine-tunes the model every night", GOOD)


def test_parse_json_tolerates_fences_and_chatter():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Sure! Here it is: {"a": {"b": 2}} hope this helps') == {"a": {"b": 2}}


# -------------------------------------------------------------------------- judge guards
def test_key_points_judge_cannot_pass_with_fake_quote(tmp_path):
    llm = FakeLLM(make_handler(fake_kp_quote=True))
    rep = Evaluator(SPEC, Memory(tmp_path / "m.json"), llm).evaluate(GOOD)
    kp = next(r for r in rep.results if r.id == "key_points")
    assert not kp.passed and "kp8_uses" in kp.details["unproven"]


def test_judge_error_means_not_shippable(tmp_path):
    def boom(task, system, user):
        if task.startswith("judge:flow"):
            raise LLMError("timeout")
        return make_handler()(task, system, user)

    rep = Evaluator(SPEC, Memory(tmp_path / "m.json"), FakeLLM(boom)).evaluate(GOOD)
    assert not rep.passed and not next(r for r in rep.results if r.id == "flow").passed


# ------------------------------------------------------------------------------ the loop
def test_route_after_eval_terminates():
    class R:
        def __init__(self, ok): self.passed = ok
    for max_r in (0, 1, 2):
        attempts = []
        steps = 0
        while True:
            attempts.append({"report": R(False)})
            steps += 1
            if route_after_eval({"attempts": attempts, "max_retries": max_r}) == "decide":
                break
        assert steps == max_r + 1


def test_loop_catches_injected_error_and_fixes_it(tmp_path):
    d = deps_for(tmp_path, make_handler(reviser_fixes=True))
    final = run_pipeline(SPEC, d, max_retries=2)
    assert final["status"] == "SHIPPED"
    assert len(final["attempts"]) == 2
    a1 = {r.id for r in final["attempts"][0]["report"].failed}
    assert {"accuracy", "misconception_tripwire"} <= a1
    log = Path(final["outputs"]["log"]).read_text()
    assert "Attempt 1 - REJECTED" in log and "Attempt 2 - PASSED" in log
    assert "removed the false retraining claim" in log
    assert Path(final["outputs"]["lesson"]).name == "lesson.md"
    # memory learned a rule from the failure
    assert any("retrains" in g["rule"] for g in d.memory.data["guidance"])


def test_loop_stops_after_max_retries_and_blocks(tmp_path):
    d = deps_for(tmp_path, make_handler(reviser_fixes=False))
    final = run_pipeline(SPEC, d, max_retries=2)
    assert final["status"] == "BLOCKED"
    assert len(final["attempts"]) == 3
    out = Path(final["outputs"]["lesson"])
    assert out.name == "lesson_NEEDS_REVIEW.md" and "NOT SHIPPED" in out.read_text()


def test_learned_rule_is_injected_into_next_run(tmp_path):
    mem = Memory(tmp_path / "memory.json")
    run_pipeline(SPEC, deps_for(tmp_path, make_handler(), mem), max_retries=1)
    seen = {}

    def spy(task, system, user):
        seen.setdefault(task, user)
        return make_handler()(task, system, user)

    run_pipeline(SPEC, deps_for(tmp_path, spy, Memory(tmp_path / "memory.json")), max_retries=1)
    assert "LESSONS LEARNED FROM PAST RUNS" in seen["write"]
    assert "Never say RAG retrains" in seen["write"]


def test_repeated_hard_word_becomes_enforced_jargon(tmp_path):
    for _ in range(2):
        mem = Memory(tmp_path / "memory.json")
        run_pipeline(SPEC, deps_for(tmp_path, make_handler(hard_word="leverage"), mem), max_retries=1)
    mem = Memory(tmp_path / "memory.json")
    assert "leverage" in mem.enforced_jargon()
    # ...and the deterministic glossary check now enforces it
    md = GOOD.replace("RAG is very useful.", "RAG lets you leverage your documents.")
    ev = Evaluator(SPEC, mem, None)
    res = {r.id: r for r in ev.evaluate(md, code_only=True).results}
    assert not res["glossary_coverage"].passed


def test_direct_human_feedback(tmp_path):
    mem = Memory(tmp_path / "memory.json")
    acts = apply_feedback(None, mem, "", check_id="plain_language", rule="Use rupees, not dollars, in money examples.",
                          jargon=["semantic"], calibrate="Do not flag the word 'chatbot'; students know it.")
    assert len(acts) == 3
    mem2 = Memory(tmp_path / "memory.json")
    assert mem2.calibration_for("plain_language")
    assert mem2.active_guidance()[0]["source"] == "human"


def test_replay_demo_runs_end_to_end(tmp_path):
    """The hand-written replay responses drive the real pipeline: reject -> revise -> ship -> learn."""
    import shutil
    from lessongen.llm import ReplayLLM

    root = Path(__file__).parent.parent / "replay"
    mem = Memory(tmp_path / "memory.json")
    for run, inj, attempts in (("run1", "misconception", 2), ("run2", None, 1)):
        rdir = tmp_path / run
        shutil.copytree(root / run, rdir)
        llm = ReplayLLM(rdir)
        d = Deps(writer=llm, judge=llm, memory=mem, evaluator=Evaluator(SPEC, mem, llm, workers=2),
                 log=lambda m: None, runs_dir=tmp_path / "runs", output_dir=tmp_path / "out")
        final = run_pipeline(SPEC, d, max_retries=2, inject_error=inj)
        assert final["status"] == "SHIPPED" and len(final["attempts"]) == attempts
    assert "LESSONS LEARNED" in (tmp_path / "run2" / "_prompts" / "write__1.txt").read_text()
