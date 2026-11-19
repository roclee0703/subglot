"""Translation logic tests -- no network, _chat is monkeypatched."""
import json

import pytest

from subglot.subtitles import parse_srt, write_srt
from subglot.translate import TranslateConfig, _parse_json_array, translate_cues


class FakeChat:
    """Records calls, replies with a deterministic 'translation'."""

    def __init__(self, reply_map=None):
        self.calls = []
        self.reply_map = reply_map or {}

    def __call__(self, cfg, messages):
        self.calls.append(messages)
        user = messages[-1]["content"]
        payload = json.loads(user)
        reply = [self.reply_map.get(ln, f"[{ln}]") for ln in payload["lines"]]
        return json.dumps(reply, ensure_ascii=False)


def test_parse_json_array_tolerates_fences():
    assert _parse_json_array('```json\n["a","b"]\n```') == ["a", "b"]
    assert _parse_json_array('Sure! ["x"] hope that helps') == ["x"]
    with pytest.raises(ValueError):
        _parse_json_array("no array here")


def test_translate_cues_batches_and_wraps(tmp_path, monkeypatch):
    src = tmp_path / "en.srt"
    src.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nHello there.\n\n"
        "2\n00:00:02,000 --> 00:00:04,000\nSecond line.\n",
        encoding="utf-8",
    )
    cues = parse_srt(src)
    cfg = TranslateConfig(api_key="test", batch_size=1, max_units=20.0)

    fake = FakeChat()
    monkeypatch.setattr("subglot.translate._chat", fake)
    out = translate_cues(cues, cfg)

    assert len(out) == 2
    assert len(fake.calls) == 2  # batch_size=1 -> one request per cue
    # First call has empty context, second carries the previous translation.
    first_payload = json.loads(fake.calls[0][-1]["content"])
    second_payload = json.loads(fake.calls[1][-1]["content"])
    assert first_payload["context"] == []
    assert second_payload["context"] == ["[Hello there.]"]
    # Timing preserved, text translated.
    assert out[0].start == 0.0 and out[1].end == 4.0
    assert out[0].text == "[Hello there.]"


def test_translate_retries_on_count_mismatch(tmp_path, monkeypatch):
    src = tmp_path / "en.srt"
    src.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nAlpha.\n\n"
        "2\n00:00:02,000 --> 00:00:04,000\nBeta.\n",
        encoding="utf-8",
    )
    cues = parse_srt(src)
    cfg = TranslateConfig(api_key="test", batch_size=2)

    replies = iter(
        [
            json.dumps(["只有一条"]),  # wrong count on first try
            json.dumps(["甲。", "乙。"]),  # corrected on retry
        ]
    )

    def flaky_chat(cfg, messages):
        return next(replies)

    monkeypatch.setattr("subglot.translate._chat", flaky_chat)
    out = translate_cues(cues, cfg)
    assert [c.text for c in out] == ["甲。", "乙。"]


def test_translate_gives_up_after_retry(tmp_path, monkeypatch):
    src = tmp_path / "en.srt"
    src.write_text("1\n00:00:00,000 --> 00:00:02,000\nAlpha.\n", encoding="utf-8")
    cues = parse_srt(src)
    cfg = TranslateConfig(api_key="test", batch_size=1)

    monkeypatch.setattr(
        "subglot.translate._chat", lambda cfg, m: json.dumps(["一", "二"])
    )
    with pytest.raises(ValueError):
        translate_cues(cues, cfg)
