from subglot.subtitles import Cue
from subglot.validate import validate


def make_cue(i, start, end, text):
    return Cue(i, start, end, text.split("\n"))


def test_clean_file_passes():
    cues = [
        make_cue(1, 0.0, 3.0, "正常长度的中文字幕行"),
        make_cue(2, 3.5, 6.0, "第二条字幕"),
    ]
    assert validate(cues) == []


def test_overlap_is_error():
    cues = [
        make_cue(1, 0.0, 3.0, "第一条"),
        make_cue(2, 2.5, 5.0, "第二条"),
    ]
    issues = validate(cues)
    assert any(i.level == "error" and "overlap" in i.message for i in issues)


def test_negative_duration_is_error():
    issues = validate([make_cue(1, 5.0, 2.0, "倒计时")])
    assert any(i.level == "error" and "non-positive" in i.message for i in issues)


def test_empty_text_is_error():
    issues = validate([make_cue(1, 0.0, 2.0, "")])
    assert any(i.level == "error" and "empty" in i.message for i in issues)


def test_long_line_is_warning():
    cues = [make_cue(1, 0.0, 6.0, "这" * 25)]
    issues = validate(cues)
    assert any(i.level == "warning" and "units" in i.message for i in issues)


def test_fast_reading_speed_is_error():
    # 30 CJK units in 1 second = 30 cps > default hard limit (25)
    cues = [make_cue(1, 0.0, 1.0, "字" * 30)]
    issues = validate(cues)
    assert any(i.level == "error" and "reading speed" in i.message for i in issues)


def test_moderate_reading_speed_is_warning():
    # 20 units in 1.4s = ~14.3 cps; with max_cps=10, hard=12.5 -> error band.
    # Pick values landing in warning band instead: 10 units in 0.9s = 11.1 cps,
    # max_cps=10 -> warning (11.1 < 12.5 hard).
    cues = [make_cue(1, 0.0, 0.9, "一二三四五六七八九十")]
    issues = validate(cues, max_cps=10.0)
    assert any(i.level == "warning" and "reading speed" in i.message for i in issues)
    assert not any(i.level == "error" for i in issues)
