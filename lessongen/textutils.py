"""Markdown/text helpers used by the deterministic checks."""
from __future__ import annotations

import re
from dataclasses import dataclass

WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-]*")


@dataclass
class Section:
    heading: str
    level: int
    body: str


def strip_code(md: str) -> str:
    return re.sub(r"```.*?```", "", md, flags=re.DOTALL)


def sections(md: str) -> list[Section]:
    """Split on level-1/2 headings. Text before the first '##' belongs to the title section."""
    out: list[Section] = []
    cur = Section(heading="", level=0, body="")
    in_code = False
    for line in md.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else re.match(r"^(#{1,2})\s+(.*?)\s*#*\s*$", line)
        if m:
            out.append(cur)
            cur = Section(heading=m.group(2).strip(), level=len(m.group(1)), body="")
        else:
            cur.body += line + "\n"
    out.append(cur)
    return [s for s in out if s.heading or s.body.strip()]


def find_section(md: str, pattern: str) -> Section | None:
    rx = re.compile(pattern, re.IGNORECASE)
    for s in sections(md):
        if s.level == 2 and rx.search(s.heading):
            return s
    return None


def _clean_line(line: str) -> str:
    line = re.sub(r"^\s*(?:[-*+]|\d+[.)]|>)\s*", "", line)      # list / quote markers
    line = re.sub(r"\*\*|__|`", "", line)                        # bold / code ticks
    line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)         # links
    line = re.sub(r"^\|.*\|$", "", line)                         # table rows
    return line.strip()


def prose_lines(md: str, exclude_sections: tuple[str, ...] = ()) -> list[str]:
    """Body text lines without headings, code blocks, tables or excluded sections."""
    lines: list[str] = []
    rx = [re.compile(p, re.IGNORECASE) for p in exclude_sections]
    for sec in sections(strip_code(md)):
        if sec.heading and any(r.search(sec.heading) for r in rx):
            continue
        for raw in sec.body.splitlines():
            if re.match(r"^\s*\|", raw) or re.match(r"^\s*-{3,}\s*$", raw):
                continue
            c = _clean_line(raw)
            if c:
                lines.append(c)
    return lines


def split_sentences(text_lines: list[str]) -> list[str]:
    sents: list[str] = []
    for line in text_lines:
        # Split after . ! ? when followed by space + capital/quote/digit. Keeps "e.g." mostly intact.
        parts = re.split(r"(?<=[.!?])[\"”’)]?\s+(?=[A-Z0-9\"“‘(])", line)
        sents.extend(p.strip() for p in parts if p.strip())
    return sents


def words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def normalize(s: str) -> str:
    s = s.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[*_`>#]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def quote_in_text(quote: str, text: str, min_ratio: float = 0.85) -> bool:
    """True if `quote` appears in `text` verbatim or near-verbatim (judge anti-hallucination)."""
    q, t = normalize(quote).strip(" .\"'"), normalize(text)
    if not q:
        return False
    if q in t:
        return True
    # Fuzzy: compare against windows of the same word length.
    import difflib

    qw, tw = q.split(), t.split()
    n = len(qw)
    if n == 0 or n > len(tw):
        return False
    best = 0.0
    for i in range(0, len(tw) - n + 1):
        window = " ".join(tw[i : i + n])
        if window[:3] != q[:3] and qw[0] not in window:
            continue
        r = difflib.SequenceMatcher(None, q, window).ratio()
        if r > best:
            best = r
            if best >= min_ratio:
                return True
    return False
