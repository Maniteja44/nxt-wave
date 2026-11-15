"""Thin, provider-agnostic LLM client.

Every call carries a `task` tag (plan / write / revise / judge:<check> / reflect ...).
The tag is used for logging, cost accounting, and by FakeLLM in tests.
Supported providers: anthropic, openai, gemini, groq, ollama (OpenAI-compatible), bedrock.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from .config import ModelConfig

OPENAI_COMPATIBLE = {
    "openai": (None, "OPENAI_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
}


class LLMError(RuntimeError):
    pass


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    by_task: dict = field(default_factory=dict)

    def add(self, task: str, inp: int, out: int, secs: float) -> None:
        self.calls += 1
        self.input_tokens += inp
        self.output_tokens += out
        self.seconds += secs
        key = task.split(":")[0]
        self.by_task[key] = self.by_task.get(key, 0) + 1


class LLM:
    """One configured model. Thread-safe for parallel judge calls."""

    def __init__(self, cfg: ModelConfig, usage: Usage | None = None):
        self.cfg = cfg
        self.usage = usage or Usage()
        self._lock = threading.Lock()
        self._client = None
        self._send_temperature = True  # some newer models reject a temperature value

    # ---------------------------------------------------------------- providers
    def _get_client(self):
        if self._client is not None:
            return self._client
        p = self.cfg.provider
        if p == "anthropic":
            import anthropic

            if not os.getenv("ANTHROPIC_API_KEY"):
                raise LLMError("ANTHROPIC_API_KEY is not set (provider=anthropic). See .env.example.")
            self._client = anthropic.Anthropic()
        elif p in OPENAI_COMPATIBLE:
            from openai import OpenAI

            base_url, key_env = OPENAI_COMPATIBLE[p]
            base_url = os.getenv(f"{p.upper()}_BASE_URL", base_url)
            api_key = os.getenv(key_env) if key_env else "ollama"
            if key_env and not api_key:
                raise LLMError(f"{key_env} is not set (provider={p}).")
            self._client = OpenAI(api_key=api_key, base_url=base_url)
        elif p == "bedrock":
            import boto3

            self._client = boto3.client(
                "bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1")
            )
        else:
            raise LLMError(f"Unknown provider '{p}'.")
        return self._client

    def _raw(self, system: str, user: str, max_tokens: int) -> tuple[str, int, int]:
        p, client = self.cfg.provider, self._get_client()
        if p == "anthropic":
            kw = {"temperature": self.cfg.temperature} if self._send_temperature else {}
            r = client.messages.create(
                model=self.cfg.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                **kw,
            )
            text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
            return text, r.usage.input_tokens, r.usage.output_tokens
        if p in OPENAI_COMPATIBLE:
            kw = {"temperature": self.cfg.temperature} if self._send_temperature else {}
            r = client.chat.completions.create(
                model=self.cfg.model,
                max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                **kw,
            )
            u = r.usage
            return (
                r.choices[0].message.content or "",
                getattr(u, "prompt_tokens", 0) or 0,
                getattr(u, "completion_tokens", 0) or 0,
            )
        if p == "bedrock":
            r = client.converse(
                modelId=self.cfg.model,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": user}]}],
                inferenceConfig={"maxTokens": max_tokens, "temperature": self.cfg.temperature},
            )
            text = "".join(c.get("text", "") for c in r["output"]["message"]["content"])
            u = r.get("usage", {})
            return text, u.get("inputTokens", 0), u.get("outputTokens", 0)
        raise LLMError(f"Unknown provider '{p}'.")

    # ---------------------------------------------------------------- public API
    def complete(self, task: str, system: str, user: str, max_tokens: int = 6000) -> str:
        last_err: Exception | None = None
        for attempt in range(3):  # transient-error retry with backoff
            try:
                t0 = time.time()
                text, inp, out = self._raw(system, user, max_tokens)
                with self._lock:
                    self.usage.add(task, inp, out, time.time() - t0)
                return text
            except LLMError:
                raise
            except Exception as e:  # network / rate limit / unsupported parameter
                last_err = e
                if "temperature" in str(e).lower() and self._send_temperature:
                    self._send_temperature = False  # retry immediately without it
                    continue
                time.sleep(2 * (attempt + 1))
        raise LLMError(f"[{task}] LLM call failed after retries: {last_err}")

    def complete_json(self, task: str, system: str, user: str, max_tokens: int = 4000) -> dict:
        """Ask for JSON; parse robustly; on parse failure re-ask (max 2 extra tries)."""
        prompt = user
        for _ in range(3):
            text = self.complete(task, system + "\n\nRespond with ONE valid JSON object only. No prose, no markdown fences.", prompt, max_tokens)
            try:
                return parse_json(text)
            except ValueError as e:
                prompt = (
                    user
                    + f"\n\nYour previous reply was not valid JSON ({e}). Reply again with ONE valid JSON object only."
                )
        raise LLMError(f"[{task}] model never returned valid JSON")


def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(str(e)) from e
    if not isinstance(obj, dict):
        raise ValueError("top-level JSON is not an object")
    return obj


class ReplayLLM(LLM):
    """Plays back pre-written responses - "you are the LLM" mode.

    For the k-th call with task T it returns the file  REPLAY_DIR/<T>__<k>.<ext>
    (':' in T becomes '-', e.g. judge-accuracy__2.json). Every prompt it receives is
    saved to REPLAY_DIR/_prompts/<T>__<k>.txt, so you can read exactly what a real
    model would be asked. A missing response file stops the run with the expected
    file name: write it (by hand, or with any chat model) and run again.
    """

    def __init__(self, replay_dir: str | os.PathLike, usage: Usage | None = None):
        super().__init__(ModelConfig("replay", str(replay_dir), 0.0), usage)
        from pathlib import Path

        self.dir = Path(replay_dir)
        self.counts: dict[str, int] = {}

    def _raw(self, system: str, user: str, max_tokens: int):  # pragma: no cover - unused
        raise NotImplementedError

    def complete(self, task: str, system: str, user: str, max_tokens: int = 6000) -> str:
        name = task.replace(":", "-")
        with self._lock:
            k = self.counts[name] = self.counts.get(name, 0) + 1
            self.usage.add(task, len(system + user) // 4, 0, 0.0)  # rough token estimate
        pdir = self.dir / "_prompts"
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / f"{name}__{k}.txt").write_text(f"=== SYSTEM ===\n{system}\n\n=== USER ===\n{user}\n", encoding="utf-8")
        hits = sorted(self.dir.glob(f"{name}__{k}.*"))
        if not hits:
            raise LLMError(f"[replay] no response file for call {k} of task '{task}'. "
                           f"Create {self.dir / (name + '__' + str(k) + '.json|.md')} "
                           f"(the prompt is in {pdir / (name + '__' + str(k) + '.txt')}).")
        text = hits[0].read_text(encoding="utf-8")
        with self._lock:
            self.usage.output_tokens += len(text) // 4
        return text


class FakeLLM(LLM):
    """Deterministic stand-in used by tests. `handler(task, system, user) -> str`."""

    def __init__(self, handler: Callable[[str, str, str], str], usage: Usage | None = None):
        super().__init__(ModelConfig("fake", "fake", 0.0), usage)
        self.handler = handler
        self.calls: list[tuple[str, str]] = []

    def _raw(self, system: str, user: str, max_tokens: int):  # pragma: no cover - unused
        raise NotImplementedError

    def complete(self, task: str, system: str, user: str, max_tokens: int = 6000) -> str:
        with self._lock:
            self.calls.append((task, user))
            self.usage.add(task, 0, 0, 0.0)
        return self.handler(task, system, user)
