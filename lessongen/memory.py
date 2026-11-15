"""Persistent memory shared across runs (a single, human-readable JSON file).

What is remembered, and how it is used on the next run:

* guidance        - short rules distilled from past failures / human feedback. Injected
                    into the planner + writer prompts ("prompt evolution"). Each rule
                    tracks whether runs that used it passed its check on the first try,
                    so rules that don't help get flagged and rewritten.
* learned_jargon  - hard words the judges kept flagging. After JARGON_PROMOTE_AT
                    sightings they are added to the deterministic glossary check
                    ("rubric evolution").
* calibration     - human corrections for a judge (e.g. "this was a false positive").
                    Injected into that judge's prompt as calibration notes.
* check_stats     - per-check failure rates, to see which checks fail most and whether
                    first-attempt pass rate improves over runs.
* runs / feedback - audit trail.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from .config import MEMORY_DIR

JARGON_PROMOTE_AT = 2      # sightings before a flagged word becomes an enforced jargon term
MAX_ACTIVE_GUIDANCE = 12   # keep the generator prompt focused
INEFFECTIVE_AFTER = 3      # first-attempt failures (with rule applied, never a pass) => flag


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


EMPTY = {
    "version": 1,
    "runs": [],
    "check_stats": {},
    "guidance": [],
    "learned_jargon": {},
    "calibration": {},
    "feedback": [],
}


class Memory:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else MEMORY_DIR / "memory.json"
        self._lock = threading.Lock()
        self.data = self._read()

    # ------------------------------------------------------------------ io
    def _read(self) -> dict:
        if self.path.exists():
            d = json.loads(self.path.read_text(encoding="utf-8"))
            for k, v in EMPTY.items():
                d.setdefault(k, json.loads(json.dumps(v)))
            return d
        return json.loads(json.dumps(EMPTY))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)  # atomic: a crash never leaves half-written memory

    # ------------------------------------------------------------- guidance
    def active_guidance(self, limit: int = MAX_ACTIVE_GUIDANCE) -> list[dict]:
        rules = [g for g in self.data["guidance"] if g.get("active", True)]
        # Human rules first, then the most reinforced auto rules.
        rules.sort(key=lambda g: (g.get("source") != "human", -g.get("times_reinforced", 1)))
        return rules[:limit]

    def add_guidance(self, rule: str, check_id: str | None, source: str = "auto") -> dict:
        for g in self.data["guidance"]:
            if g["rule"].strip().lower() == rule.strip().lower():
                g["times_reinforced"] = g.get("times_reinforced", 1) + 1
                g["active"] = True
                return g
        g = {
            "id": f"g{len(self.data['guidance']) + 1}",
            "rule": rule.strip(),
            "check_id": check_id,
            "source": source,
            "created": now(),
            "times_reinforced": 1,
            "applied_runs": 0,
            "applied_first_pass": 0,
            "applied_first_fail": 0,
            "active": True,
            "flag": None,
        }
        self.data["guidance"].append(g)
        return g

    def reinforce(self, guidance_id: str) -> None:
        for g in self.data["guidance"]:
            if g["id"] == guidance_id:
                g["times_reinforced"] = g.get("times_reinforced", 1) + 1

    def rewrite_guidance(self, guidance_id: str, new_rule: str) -> None:
        for g in self.data["guidance"]:
            if g["id"] == guidance_id:
                g.setdefault("history", []).append(g["rule"])
                g["rule"] = new_rule.strip()
                g["flag"] = None
                g["applied_first_fail"] = 0
                g["applied_first_pass"] = 0

    def retire_guidance(self, guidance_id: str) -> None:
        for g in self.data["guidance"]:
            if g["id"] == guidance_id:
                g["active"] = False

    def flagged_guidance(self) -> list[dict]:
        return [g for g in self.data["guidance"] if g.get("active", True) and g.get("flag")]

    # --------------------------------------------------------------- jargon
    def note_hard_word(self, term: str, regex: str) -> bool:
        """Record a word a judge flagged. Returns True if it just got promoted."""
        key = term.strip().lower()
        if not key:
            return False
        j = self.data["learned_jargon"].setdefault(
            key, {"regex": regex, "count": 0, "enforced": False, "first_seen": now()}
        )
        j["count"] += 1
        if not j["enforced"] and j["count"] >= JARGON_PROMOTE_AT:
            j["enforced"] = True
            j["promoted"] = now()
            return True
        return False

    def enforced_jargon(self) -> dict[str, str]:
        return {t: j["regex"] for t, j in self.data["learned_jargon"].items() if j.get("enforced")}

    # ---------------------------------------------------------- calibration
    def add_calibration(self, check_id: str, note: str, source: str = "human") -> None:
        self.data["calibration"].setdefault(check_id, []).append(
            {"note": note.strip(), "source": source, "created": now()}
        )

    def calibration_for(self, check_id: str, limit: int = 5) -> list[str]:
        return [c["note"] for c in self.data["calibration"].get(check_id, [])][-limit:]

    # ---------------------------------------------------------------- stats
    def record_run(self, run: dict, attempts_results: list[dict[str, bool]], applied_guidance_ids: list[str]) -> None:
        """attempts_results: one {check_id: passed} dict per attempt."""
        stats = self.data["check_stats"]
        for i, res in enumerate(attempts_results):
            for cid, passed in res.items():
                s = stats.setdefault(cid, {"evaluated": 0, "failed": 0, "first_attempt_evaluated": 0, "first_attempt_failed": 0})
                s["evaluated"] += 1
                s["failed"] += 0 if passed else 1
                if i == 0:
                    s["first_attempt_evaluated"] += 1
                    s["first_attempt_failed"] += 0 if passed else 1
        # Guidance effectiveness: did the check a rule targets pass on the first try?
        first = attempts_results[0] if attempts_results else {}
        for g in self.data["guidance"]:
            if g["id"] not in applied_guidance_ids:
                continue
            g["applied_runs"] += 1
            cid = g.get("check_id")
            if cid in first:
                if first[cid]:
                    g["applied_first_pass"] += 1
                else:
                    g["applied_first_fail"] += 1
                    if g["applied_first_fail"] >= INEFFECTIVE_AFTER and g["applied_first_pass"] == 0:
                        g["flag"] = "ineffective"
        self.data["runs"].append(run)

    def add_feedback(self, entry: dict) -> None:
        entry.setdefault("created", now())
        self.data["feedback"].append(entry)

    def summary(self) -> dict:
        runs = self.data["runs"]
        return {
            "runs": len(runs),
            "shipped": sum(1 for r in runs if r.get("status") == "SHIPPED"),
            "first_attempt_pass_rate": (
                round(sum(1 for r in runs if r.get("attempts") == 1 and r.get("status") == "SHIPPED") / len(runs), 2)
                if runs else None
            ),
            "active_guidance": len(self.active_guidance(limit=10_000)),
            "enforced_learned_jargon": sorted(self.enforced_jargon()),
            "calibrated_checks": sorted(self.data["calibration"]),
        }
