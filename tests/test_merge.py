from pathlib import Path
from subglot.merge import merge_cues
from subglot.subtitles import Cue, parse_srt, write_srt


def test_merge_cues_equal_length():
    src = [
        Cue(1, 0.0, 2.0, ["Hello world."]),
        Cue(2, 2.5, 4.5, ["How are you?"]),
    ]
    tgt = [
        Cue(1, 0.0, 2.0, ["你好世界。"]),
        Cue(2, 2.5, 4.5, ["你好吗？"]),
    ]

    merged = merge_cues(tgt, src, layout="primary-first")
    assert len(merged) == 2
    assert merged[0].lines == ["你好世界。", "Hello world."]
    assert merged[1].lines == ["你好吗？", "How are you?"]
    assert merged[0].start == 0.0
    assert merged[1].end == 4.5


def test_merge_cues_secondary_first():
    src = [Cue(1, 1.0, 3.0, ["Source text"])]
    tgt = [Cue(1, 1.0, 3.0, ["Target text"])]

    merged = merge_cues(tgt, src, layout="secondary-first")
    assert len(merged) == 1
    assert merged[0].lines == ["Source text", "Target text"]


def test_merge_cues_timestamp_alignment():
    # Target has 1 cue, source has 2 short cues within the target window
    src = [
        Cue(1, 0.0, 1.5, ["Part one."]),
        Cue(2, 1.5, 3.0, ["Part two."]),
    ]
    tgt = [
        Cue(1, 0.0, 3.0, ["完整翻译。"]),
    ]

    merged = merge_cues(tgt, src, layout="primary-first")
    assert len(merged) == 1
    assert merged[0].lines == ["完整翻译。", "Part one.", "Part two."]


def test_merge_cues_invalid_layout():
    src = [Cue(1, 0.0, 1.0, ["A"])]
    tgt = [Cue(1, 0.0, 1.0, ["B"])]
    try:
        merge_cues(tgt, src, layout="unknown")
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "unknown layout" in str(e)


def test_merge_roundtrip(tmp_path: Path):
    src_file = tmp_path / "src.srt"
    src_file.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nHello.\n\n",
        encoding="utf-8",
    )
    tgt_file = tmp_path / "tgt.srt"
    tgt_file.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\n你好。\n\n",
        encoding="utf-8",
    )

    src_cues = parse_srt(src_file)
    tgt_cues = parse_srt(tgt_file)
    merged = merge_cues(tgt_cues, src_cues)

    out_file = tmp_path / "bilingual.srt"
    write_srt(merged, out_file)

    reparsed = parse_srt(out_file)
    assert len(reparsed) == 1
    assert reparsed[0].lines == ["你好。", "Hello."]
