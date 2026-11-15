"""Topic specs: the ground truth a lesson is generated from and graded against.

For RAG we ship a human-curated spec (topics/rag.yaml). For any other topic the agent
drafts a spec with the LLM, saves it under topics/generated/, and marks it
`verified: false` so the output clearly says a human should review the facts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import TOPICS_DIR
from .llm import LLM


@dataclass
class TopicSpec:
    slug: str
    title: str
    learner_profile: str
    key_points: list[dict]
    reference_facts: list[str]
    misconceptions: list[str]
    jargon: dict[str, str]  # term -> regex
    verified: bool = False
    aliases: list[str] = field(default_factory=list)
    path: str = ""

    def jargon_patterns(self, extra: dict[str, str] | None = None) -> dict[str, re.Pattern]:
        merged = {**self.jargon, **(extra or {})}
        return {t: re.compile(p, re.IGNORECASE) for t, p in merged.items()}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "topic"


def _load(path: Path) -> TopicSpec:
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    return TopicSpec(
        slug=d["slug"],
        title=d["title"],
        learner_profile=d.get("learner_profile", ""),
        key_points=d["key_points"],
        reference_facts=d.get("reference_facts", []),
        misconceptions=d.get("misconceptions", []),
        jargon=d.get("jargon", {}),
        verified=bool(d.get("verified", False)),
        aliases=d.get("aliases", []),
        path=str(path),
    )


def find_spec(topic: str, topics_dir: Path = TOPICS_DIR) -> TopicSpec | None:
    norm = " " + re.sub(r"[^a-z0-9]+", " ", topic.lower()) + " "
    for path in sorted(topics_dir.rglob("*.yaml")):
        spec = _load(path)
        for alias in [spec.slug, *spec.aliases]:
            a = " " + re.sub(r"[^a-z0-9]+", " ", alias.lower()).strip() + " "
            if a.strip() and a in norm:
                return spec
    return None


DEFAULT_LEARNER = (
    "A 12th-grade graduate from India who studied in a non-English-medium school, has "
    "limited English vocabulary, no programming or AI background, and wants to start an AI career."
)

SPEC_SYSTEM = """You are a senior curriculum designer and subject-matter expert in AI.
You write precise, conservative topic specifications that a lesson writer and a lesson
reviewer will both use as ground truth. Only include facts you are certain are correct."""

SPEC_USER = """Draft a topic spec for a beginner lesson on: "{topic}".
Learner: {learner}

Return JSON with keys:
  "title": string,
  "key_points": list of 6-9 objects {{"id": "kp1_short_name", "text": "what must be taught"}}
      covering what it is, why it matters, how it works step by step, limitations, real uses,
  "reference_facts": list of 8-12 precise, uncontroversial facts,
  "misconceptions": list of 4-8 common beginner misconceptions (stated as the wrong belief),
  "jargon": object mapping each technical term a beginner would not know to a
      case-insensitive Python regex that matches it (e.g. "embedding": "\\\\bembeddings?\\\\b").
"""


def draft_spec(topic: str, llm: LLM, topics_dir: Path = TOPICS_DIR) -> TopicSpec:
    d = llm.complete_json("spec", SPEC_SYSTEM, SPEC_USER.format(topic=topic, learner=DEFAULT_LEARNER))
    slug = slugify(topic)
    data = {
        "slug": slug,
        "title": d.get("title", topic),
        "verified": False,
        "aliases": [topic.lower()],
        "learner_profile": DEFAULT_LEARNER,
        "key_points": d["key_points"],
        "reference_facts": d.get("reference_facts", []),
        "misconceptions": d.get("misconceptions", []),
        "jargon": {k: v for k, v in d.get("jargon", {}).items() if _valid_regex(v)},
    }
    out = topics_dir / "generated" / f"{slug}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return _load(out)


def _valid_regex(p: str) -> bool:
    try:
        re.compile(p)
        return True
    except re.error:
        return False


def get_spec(topic: str, llm: LLM | None, topics_dir: Path = TOPICS_DIR) -> TopicSpec:
    spec = find_spec(topic, topics_dir)
    if spec:
        return spec
    if llm is None:
        raise ValueError(f"No spec found for topic '{topic}' and no LLM to draft one.")
    return draft_spec(topic, llm, topics_dir)
