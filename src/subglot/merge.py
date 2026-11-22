"""Bilingual and multi-track subtitle merging utilities."""
from __future__ import annotations

from .subtitles import Cue


def merge_cues(
    primary: list[Cue],
    secondary: list[Cue],
    *,
    layout: str = "primary-first",
) -> list[Cue]:
    """Merge two sets of subtitle cues into a single bilingual track.

    Args:
        primary: The primary subtitle track (e.g. translated target text).
        secondary: The secondary subtitle track (e.g. original source text).
        layout: Placement order:
            - ``"primary-first"``: primary text on top line(s), secondary below.
            - ``"secondary-first"``: secondary text on top line(s), primary below.

    Returns:
        A new list of merged Cue instances.
    """
    if layout not in ("primary-first", "secondary-first"):
        raise ValueError(
            f"unknown layout: {layout!r}, expected 'primary-first' or 'secondary-first'"
        )

    merged: list[Cue] = []

    # If cue counts match exactly (typical for 1-to-1 translations), pair by index.
    if len(primary) == len(secondary):
        for idx, (p, s) in enumerate(zip(primary, secondary), start=1):
            p_lines = [ln for ln in p.lines if ln.strip()]
            s_lines = [ln for ln in s.lines if ln.strip()]

            if layout == "primary-first":
                combined = p_lines + s_lines
            else:
                combined = s_lines + p_lines

            merged.append(Cue(index=idx, start=p.start, end=p.end, lines=combined))
        return merged

    # Fallback for mismatched cue counts: align by timestamp overlap.
    for idx, p in enumerate(primary, start=1):
        p_lines = [ln for ln in p.lines if ln.strip()]
        matching_s = [
            s for s in secondary
            if not (s.end <= p.start or s.start >= p.end)
        ]

        s_lines: list[str] = []
        for s in matching_s:
            s_lines.extend(ln for ln in s.lines if ln.strip())

        if layout == "primary-first":
            combined = p_lines + s_lines
        else:
            combined = s_lines + p_lines

        merged.append(Cue(index=idx, start=p.start, end=p.end, lines=combined))

    return merged
