"""Evaluator: runs all 13 checks and returns a binary ship / don't-ship verdict.

Design notes
* Every check runs on every attempt (passes are never cached) so a revision that breaks
  something that used to pass is caught.
* All failures are collected in one pass, so one revision can fix all of them - this
  matters because we only allow 1-2 retries.
* LLM judges must prove their verdicts: evidence quotes are verified against the lesson
  in code. A coverage judge that "finds" a key point with a quote that does not exist
  is overruled. A judge that crashes counts as FAIL (we never ship unverified content).
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import prompts as P
from .checks_code import CheckResult, jargon_usage, readability_stats, run_code_checks
from .llm import LLM, LLMError
from .memory import Memory
from .rubric import CHECK_BY_ID, CHECKS
from .textutils import quote_in_text
from .topic_spec import TopicSpec


@dataclass
class EvalReport:
    results: list[CheckResult]
    stats: dict = field(default_factory=dict)
    hard_words: list[dict] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failed(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed]

    def as_map(self) -> dict[str, bool]:
        return {r.id: r.passed for r in self.results}

    def to_dict(self) -> dict:
        return {"passed": self.passed, "stats": self.stats, "results": [r.to_dict() for r in self.results]}


def _bul(items) -> str:
    return "\n".join(f"- {x}" for x in items)


class Evaluator:
    def __init__(self, spec: TopicSpec, memory: Memory | None, judge: LLM | None, workers: int = 4):
        self.spec = spec
        self.memory = memory
        self.judge = judge
        self.workers = workers
        extra = memory.enforced_jargon() if memory else {}
        self.patterns = spec.jargon_patterns(extra)

    # ------------------------------------------------------------------ public
    def evaluate(self, md: str, code_only: bool = False) -> EvalReport:
        results = run_code_checks(md, self.patterns)
        hard_words: list[dict] = []
        if not code_only:
            if self.judge is None:
                raise ValueError("LLM judge required unless code_only=True")
            llm_checks = [c.id for c in CHECKS if c.kind == "llm"]
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                outs = list(pool.map(lambda cid: self._judge(cid, md), llm_checks))
            for res in outs:
                results.append(res)
                hard_words.extend(res.details.get("hard_words", []) or [])
        order = {c.id: i for i, c in enumerate(CHECKS)}
        results.sort(key=lambda r: order.get(r.id, 99))
        return EvalReport(results=results, stats=readability_stats(md), hard_words=hard_words)

    # ------------------------------------------------------------------ judges
    def _context(self, cid: str, md: str) -> str:
        s = self.spec
        if cid == "jargon_explained":
            uses = jargon_usage(md, self.patterns)
            first = _bul(f'{t}: "{sent}"' for t, sent in uses.items()) or "- (none found by scanner)"
            return P.JUDGE_CONTEXT[cid].format(first_uses=first)
        return P.JUDGE_CONTEXT[cid].format(
            facts=_bul(s.reference_facts),
            misconceptions=_bul(s.misconceptions),
            key_points=_bul(f"{k['id']}: {k['text'].strip()}" for k in s.key_points),
        )

    def _prompt(self, cid: str, md: str, extra_note: str = "") -> str:
        calib = self.memory.calibration_for(cid) if self.memory else []
        calib_txt = ("\nCALIBRATION NOTES FROM HUMAN REVIEWERS (follow these):\n" + _bul(calib) + "\n") if calib else ""
        return P.JUDGE_BASE.format(
            check_id=cid,
            criterion=CHECK_BY_ID[cid].criterion,
            context=self._context(cid, md),
            calibration=calib_txt,
            lesson=md,
            schema=P.JUDGE_SCHEMA.get(cid, P.BASE_SCHEMA),
        ) + extra_note

    def _ask(self, cid: str, md: str, extra_note: str = "") -> dict:
        return self.judge.complete_json(f"judge:{cid}", P.JUDGE_SYSTEM, self._prompt(cid, md, extra_note))

    def _judge(self, cid: str, md: str) -> CheckResult:
        try:
            d = self._ask(cid, md)
            verdict_pass = str(d.get("verdict", "")).strip().upper().startswith("PASS")
            evidence = [e for e in (d.get("evidence") or []) if isinstance(e, str) and e.strip()]
            verified = [e for e in evidence if quote_in_text(e, md)]
            if not verdict_pass and evidence and not verified:
                # The judge quoted text that is not in the lesson: ask once more.
                d = self._ask(cid, md, "\n\nNOTE: In your previous answer, none of your evidence quotes appear in the lesson. "
                                       "Re-read the lesson and quote it exactly, or change your verdict if the problem is not really there.")
                verdict_pass = str(d.get("verdict", "")).strip().upper().startswith("PASS")
                evidence = [e for e in (d.get("evidence") or []) if isinstance(e, str) and e.strip()]
                verified = [e for e in evidence if quote_in_text(e, md)]
        except LLMError as e:
            return CheckResult(cid, False, f"Judge error - cannot verify, so not shippable: {e}",
                               fix="(no content fix - judge failed)", details={"judge_error": True})

        details: dict = {"raw_verdict": "PASS" if verdict_pass else "FAIL",
                         "evidence_verified": bool(verified) or not evidence,
                         "unverified_quotes": [e for e in evidence if e not in verified]}
        reason = str(d.get("reason", "")).strip()
        fix = str(d.get("fix", "")).strip()
        passed = verdict_pass

        # ---- code-enforced consistency for structured judges -----------------
        if cid == "key_points":
            ids = [k["id"] for k in self.spec.key_points]
            got = {str(p.get("id")): p for p in (d.get("points") or []) if isinstance(p, dict)}
            uncovered, fake = [], []
            for kid in ids:
                p = got.get(kid)
                if not p or not p.get("covered"):
                    uncovered.append(kid)
                elif not p.get("quote") or not quote_in_text(str(p["quote"]), md):
                    fake.append(kid)  # judge claims coverage but cannot show it
            details["uncovered"], details["unproven"] = uncovered, fake
            if uncovered or fake:
                passed = False
                missing_txt = {k["id"]: k["text"].strip() for k in self.spec.key_points}
                if fake and not uncovered and verdict_pass:
                    reason = f"Judge said PASS but could not quote where these are taught: {', '.join(fake)}. {reason}"
                if not fix or verdict_pass:
                    fix = "Teach these key points clearly and explicitly: " + " | ".join(
                        f"{k}: {missing_txt.get(k, '')}" for k in uncovered + fake)
        if cid == "jargon_explained":
            bad_terms = [t.get("term") for t in (d.get("terms") or []) if isinstance(t, dict) and t.get("explained_at_first_use") is False]
            others = [w for w in (d.get("unexplained_other_words") or []) if isinstance(w, str) and w.strip()]
            details["unexplained"], details["unexplained_other_words"] = bad_terms, others
            if bad_terms and passed:
                passed = False
                reason = f"Terms used before they are explained: {', '.join(bad_terms)}. {reason}"
            if not passed:
                details["hard_words"] = [{"word": w, "simpler": ""} for w in bad_terms + others]
        if cid == "plain_language":
            hw = [h for h in (d.get("hard_words") or []) if isinstance(h, dict) and h.get("word")]
            details["hard_words"] = hw
            if hw and not fix:
                fix = "Replace: " + "; ".join(f"'{h['word']}' -> '{h.get('simpler', '')}'" for h in hw)

        return CheckResult(cid, passed, reason or ("Passed." if passed else "Failed."),
                           evidence=verified if not passed else [], fix="" if passed else fix, details=details)


def report_to_text(report: EvalReport) -> str:
    lines = []
    for r in report.results:
        mark = "PASS" if r.passed else "FAIL"
        lines.append(f"[{mark}] {r.id} ({r.kind}) - {r.reason}")
        for e in r.evidence[:3]:
            lines.append(f'        evidence: "{e[:160]}"')
        if not r.passed and r.fix:
            lines.append(f"        fix: {r.fix[:300]}")
    lines.append(f"\nVERDICT: {'SHIP' if report.passed else 'REJECT'}  stats={json.dumps(report.stats)}")
    return "\n".join(lines)
