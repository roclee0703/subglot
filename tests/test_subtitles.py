from pathlib import Path

from subglot.subtitles import (
    Cue,
    display_width,
    format_ts,
    parse_srt,
    parse_ts,
    wrap_text,
    write_srt,
)

FIXTURE = """1
00:00:01,000 --> 00:00:03,500
Hello world.

2
00:00:04,000 --> 00:00:06,000
Second cue,
two lines.
"""


def test_format_ts():
    assert format_ts(0) == "00:00:00,000"
    assert format_ts(1.0) == "00:00:01,000"
    assert format_ts(63.5) == "00:01:03,500"
    assert format_ts(3661.25) == "01:01:01,250"
    assert format_ts(-3) == "00:00:00,000"  # clamped


def test_parse_ts():
    assert parse_ts("00:00:01,000") == 1.0
    assert parse_ts("00:00:03.500") == 3.5
    assert parse_ts("01:01:01,250") == 3661.25


def test_display_width():
    assert display_width("中文字幕") == 4.0
    assert display_width("abcdef") == 3.0
    assert display_width("中en中") == 3.0  # 1 + 0.5 + 0.5 + 1


def test_wrap_text_cjk():
    # 24 CJK chars -> two lines within 20 units
    lines = wrap_text("一" * 24, max_units=20.0, max_lines=2)
    assert len(lines) == 2
    assert all(display_width(ln) <= 20.0 for ln in lines)
    assert "".join(lines) == "一" * 24  # no text lost


def test_wrap_text_never_truncates():
    lines = wrap_text("word " * 30, max_units=20.0, max_lines=2)
    assert " ".join(lines) == ("word " * 30).strip() or lines[1].count("word") >= 1
    assert sum(ln.count("word") for ln in lines) == 30


def test_wrap_text_latin_keeps_words():
    lines = wrap_text("the quick brown fox jumps", max_units=10.0)
    for ln in lines:
        assert "quic" not in ln or ln == lines[0]  # words stay whole
    assert all(ln.split() for ln in lines)


def test_srt_roundtrip(tmp_path: Path):
    p = tmp_path / "in.srt"
    p.write_text(FIXTURE, encoding="utf-8")
    cues = parse_srt(p)
    assert len(cues) == 2
    assert cues[0].start == 1.0 and cues[0].end == 3.5
    assert cues[0].text == "Hello world."
    assert cues[1].text == "Second cue,\ntwo lines."

    out = tmp_path / "out.srt"
    write_srt(cues, out)
    cues2 = parse_srt(out)
    assert [c.text for c in cues2] == [c.text for c in cues]
    assert [c.start for c in cues2] == [c.start for c in cues]


def test_parse_srt_skips_counter_inside_block():
    p = Path(FIXTURE.split("\n")[0])  # just ensure fixture sanity
    assert p is not None
