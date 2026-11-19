"""SRT parsing/writing and CJK-aware line-wrapping utilities.

Subtitle text width is measured in *units*: a full-width (CJK) character
counts as 1.0 unit, a half-width (Latin) character counts as 0.5 units.
This makes one limit (``max_units``) work for both Chinese/Japanese/Korean
and Latin scripts.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_TS_RE = re.compile(
    r"(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})"
)


@dataclass
class Cue:
    """One subtitle cue. ``lines`` is the wrapped display text."""

    index: int
    start: float
    end: float
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def format_ts(seconds: float) -> str:
    """Format seconds as SRT timestamp ``HH:MM:SS,mmm``."""
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_ts(ts: str) -> float:
    """Parse an SRT timestamp (comma or dot milliseconds) into seconds."""
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    if len(parts) != 3:
        raise ValueError(f"bad SRT timestamp: {ts!r}")
    h, m, s = parts
    return int(h) * 3600 + int(m) * 60 + float(s)


def char_units(ch: str) -> float:
    return 1.0 if unicodedata.east_asian_width(ch) in ("W", "F") else 0.5


def display_width(text: str) -> float:
    """Display width in units (CJK = 1.0, Latin = 0.5 per character)."""
    return sum(char_units(c) for c in text)


def _tokens(text: str) -> list[tuple[str, bool]]:
    """Split text into unbreakable tokens.

    Latin: whole words (split on whitespace). CJK: individual characters
    (CJK line breaks may occur between any two characters).

    Returns ``(token, needs_space)`` pairs: ``needs_space`` is True when a
    space existed before this token in the original text (word boundary),
    False for intra-word CJK splits (no space must be re-inserted there).
    """
    tokens: list[tuple[str, bool]] = []
    for word in text.split():
        parts: list[str] = []
        buf = ""
        for ch in word:
            if char_units(ch) >= 1.0:
                if buf:
                    parts.append(buf)
                    buf = ""
                parts.append(ch)
            else:
                buf += ch
        if buf:
            parts.append(buf)
        for j, part in enumerate(parts):
            tokens.append((part, j == 0 and bool(tokens)))
    return tokens


def wrap_text(text: str, max_units: float = 20.0, max_lines: int = 2) -> list[str]:
    """Wrap ``text`` into lines of at most ``max_units`` units.

    Tries to respect ``max_lines``; if the text cannot fit, the last line
    overflows rather than truncating (losing subtitle text is worse than a
    long line).
    """
    text = text.strip()
    if not text:
        return [""]
    tokens = _tokens(text)
    lines: list[str] = []
    cur = ""
    for tok, needs_space in tokens:
        candidate = tok if not cur else cur + (" " if needs_space else "") + tok
        if display_width(candidate) <= max_units + 1e-6:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = tok
    if cur:
        lines.append(cur)
    if len(lines) <= max_lines:
        return lines
    # Too many lines: merge the tail back into the last allowed line.
    head = lines[: max_lines - 1]
    tail = " ".join(lines[max_lines - 1 :])
    head.append(tail)
    return head


def parse_srt(path) -> list[Cue]:
    """Parse an SRT file into cues. Tolerant of blank lines and BOM."""
    raw = path.read_text(encoding="utf-8-sig")
    cues: list[Cue] = []
    blocks = re.split(r"\n\s*\n", raw.strip())
    idx = 0
    for block in blocks:
        lines = [ln for ln in block.strip().splitlines() if ln.strip()]
        if not lines:
            continue
        # Skip a leading numeric counter line if present.
        ts_match = None
        for i, ln in enumerate(lines):
            m = _TS_RE.search(ln)
            if m:
                ts_match = m
                break
        if ts_match is None:
            continue
        idx += 1
        start = parse_ts(ts_match.group(1))
        end = parse_ts(ts_match.group(2))
        # Text is everything after the timestamp line.
        ts_line_idx = next(
            i for i, ln in enumerate(lines) if _TS_RE.search(ln)
        )
        text_lines = lines[ts_line_idx + 1 :]
        cues.append(Cue(idx, start, end, text_lines))
    return cues


def write_srt(cues: list[Cue], path) -> None:
    """Write cues as a standard SRT file (UTF-8, CRLF-free)."""
    out: list[str] = []
    for i, cue in enumerate(cues, start=1):
        out.append(str(i))
        out.append(f"{format_ts(cue.start)} --> {format_ts(cue.end)}")
        out.extend(cue.lines)
        out.append("")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
