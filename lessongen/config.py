"""Runtime configuration, read from environment variables (or a .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent.parent
TOPICS_DIR = ROOT / "topics"
MEMORY_DIR = Path(os.getenv("LESSONGEN_MEMORY_DIR", ROOT / "memory"))
RUNS_DIR = Path(os.getenv("LESSONGEN_RUNS_DIR", ROOT / "runs"))
OUTPUT_DIR = Path(os.getenv("LESSONGEN_OUTPUT_DIR", ROOT / "output"))

# Sensible default model per provider. Override with LLM_MODEL / JUDGE_MODEL.
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-2.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "bedrock": "anthropic.claude-3-5-sonnet-20240620-v1:0",
    "ollama": "llama3.1",
    "fake": "fake",
    "replay": "pre-written responses",
}


@dataclass
class ModelConfig:
    provider: str
    model: str
    temperature: float


@dataclass
class Settings:
    writer: ModelConfig
    judge: ModelConfig
    max_retries: int = 2
    judge_workers: int = 4


def _model_cfg(prefix: str, fallback_provider: str, temperature: float) -> ModelConfig:
    provider = os.getenv(f"{prefix}_PROVIDER", fallback_provider).lower()
    model = os.getenv(f"{prefix}_MODEL") or DEFAULT_MODELS.get(provider, "")
    return ModelConfig(provider=provider, model=model, temperature=temperature)


def load_settings() -> Settings:
    writer_provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    writer = _model_cfg("LLM", writer_provider, float(os.getenv("LLM_TEMPERATURE", "0.7")))
    # The judge defaults to the same provider but always runs at temperature 0 so the
    # same lesson gets the same verdict. A different (ideally stronger) judge model can
    # be set with JUDGE_PROVIDER / JUDGE_MODEL to reduce "grading your own homework".
    judge_provider = os.getenv("JUDGE_PROVIDER", writer.provider).lower()
    judge = ModelConfig(
        provider=judge_provider,
        model=os.getenv("JUDGE_MODEL")
        or (writer.model if judge_provider == writer.provider else DEFAULT_MODELS.get(judge_provider, "")),
        temperature=0.0,
    )
    return Settings(
        writer=writer,
        judge=judge,
        max_retries=int(os.getenv("MAX_RETRIES", "2")),
        judge_workers=int(os.getenv("JUDGE_WORKERS", "4")),
    )
