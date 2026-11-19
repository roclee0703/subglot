"""QA checks for subtitle files: timing sanity, line length, reading speed."""
from __future__ import annotations

from dataclasses import dataclass

from .subtitles import Cue, display_width


@dataclass
class Issue:
    index: int
    level: str  # "error" | "warning"
    message: str

    def __str__(self) -> str:
        return f"[{self.level.upper()}] cue #{self.index}: {self.message}"


def validate(
    cues: list[Cue],
    max_cps: float = 20.0,
    max_units: float = 20.0,
    max_lines: int = 2,
    hard_cps: float | None = None,
) -> list[Issue]:
    """Return a list of issues found in ``cues``.

    ``max_cps``: comfortable reading speed in display units per second
    (units, not raw characters -- CJK counts 1, Latin 0.5).
    ``hard_cps``: above this the subtitle is unreadable (error). Defaults to
    ``max_cps * 1.25``.
    """
    if hard_cps is None:
        hard_cps = max_cps * 1.25
    issues: list[Issue] = []
    prev: Cue | None = None
    for cue in cues:
        if cue.end <= cue.start:
            issues.append(Issue(cue.index, "error", "non-positive duration"))
            continue
        duration = cue.end - cue.start
        if not cue.lines or all(not ln.strip() for ln in cue.lines):
            issues.append(Issue(cue.index, "error", "empty subtitle text"))
        for ln in cue.lines:
            w = display_width(ln)
            if w > max_units + 1e-6:
                issues.append(
                    Issue(
                        cue.index,
                        "warning",
                        f"line exceeds {max_units:g} units "
                        f"({w:.1f}): {ln[:30]!r}",
                    )
                )
        if len(cue.lines) > max_lines:
            issues.append(
                Issue(cue.index, "warning", f"{len(cue.lines)} lines (> {max_lines})")
            )
        units = display_width(cue.text)
        cps = units / duration
        if cps > hard_cps:
            issues.append(
                Issue(
                    cue.index,
                    "error",
                    f"reading speed {cps:.1f} units/s > {hard_cps:g} "
                    f"({units:.1f} units in {duration:.2f}s)",
                )
            )
        elif cps > max_cps:
            issues.append(
                Issue(
                    cue.index,
                    "warning",
                    f"reading speed {cps:.1f} units/s > {max_cps:g}",
                )
            )
        if prev is not None and cue.start < prev.end - 1e-3:
            issues.append(
                Issue(
                    cue.index,
                    "error",
                    f"overlaps previous cue (starts {cue.start:.3f}, "
                    f"previous ends {prev.end:.3f})",
                )
            )
        prev = cue
    return issues


def report(issues: list[Issue]) -> str:
    if not issues:
        return "OK: no issues found."
    errors = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warning"]
    lines = [
        f"{len(errors)} error(s), {len(warnings)} warning(s)",
        *[str(i) for i in issues],
    ]
    return "\n".join(lines)
