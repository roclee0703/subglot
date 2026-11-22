# subglot

[![CI](https://github.com/roclee0703/subglot/actions/workflows/ci.yml/badge.svg)](https://github.com/roclee0703/subglot/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Local-first subtitle transcription and translation.** Whisper runs on your
machine; translation goes through any OpenAI-compatible API (OpenAI, Azure,
self-hosted vLLM, ...). Built and battle-tested on a real production
short-video pipeline.

[中文说明](README.zh-CN.md)

## Why

Most subtitle tools stop at "dump Whisper output into an SRT". subglot adds
the parts that actually matter when the subtitles have to be readable on
screen:

- **CJK-aware line wrapping** — display units (CJK char = 1, Latin char =
  0.5) instead of naive character counts, so one `--max-units` limit works
  for both English and Chinese.
- **Reading-speed QA** — every output file is validated: overlapping cues,
  non-positive durations, empty text, over-long lines, and subtitles no
  human can read in time are flagged with `error`/`warning` levels.
- **Context-carrying translation** — cues are batched, and the last few
  translated lines ride along with every request so terminology stays
  consistent across a whole video.
- **Language-detection guardrails** — see
  [docs/pitfalls.md](docs/pitfalls.md) for why this tool will never force a
  Whisper `language` value just to "check" what language the audio is.

## Install

```bash
pip install "subglot[asr]"       # transcription + translation + QA
pip install subglot              # translation + QA only (no Whisper)
```

## Quickstart

```bash
# 1. Media file -> source-language SRT (Whisper auto-detects language)
subglot transcribe talk.mp4 --model base

# 2. Translate (any OpenAI-compatible endpoint)
export OPENAI_API_KEY=sk-...
subglot translate talk.srt -o talk.zh.srt --target "Chinese (Simplified)"

# 3. QA-check the result (exit code 1 if there are hard errors)
subglot validate talk.zh.srt

# 4. Merge source and translation into bilingual subtitles
subglot merge talk.zh.srt talk.srt -o talk.bilingual.srt
```

Or in one shot (with bilingual track included):

```bash
subglot pipeline talk.mp4 --bilingual --target "Chinese (Simplified)"
```

Using a self-hosted or third-party model? Point `--base-url` at it:

```bash
subglot translate talk.srt -o talk.zh.srt \
  --base-url http://localhost:8000/v1 --model my-model \
  --api-key-env MY_KEY_VAR
```

## Design decisions

| Decision | Rationale |
|---|---|
| faster-whisper (CTranslate2), lazy import | 4x faster than openai-whisper on CPU; importing `subglot.translate` never pulls it in |
| 1 request = N cues + previous context | One request per cue is 20x the cost and loses terminology consistency; the whole file in one request loses quality on long videos |
| Strict JSON array contract + one retry | LLMs occasionally pad/drop lines; a silent mismatch shifts every later subtitle onto the wrong audio |
| Wrap, never truncate | A long subtitle line is a cosmetic problem; missing text is a data-loss bug |
| Units, not characters | `"中文字幕"` and `"Hello"` both fit `--max-units 20` sensibly |

## Roadmap

- **v0.2 — Dubbing placement**: edge-tts synthesis with trailing-silence
  trimming, time-window placement, cross-correlation verification (and the
  convolution-vs-correlation off-by-one that bit us — documented in
  [docs/pitfalls.md](docs/pitfalls.md)).
- **v0.3 — Music handling**: source separation for BGM extraction, gain
  normalization, sidechain ducking, and a preflight check for whether
  center-channel (L-R) cancellation is even viable for a given track.
- **v0.4 — Styled output**: ASS styling and burn-in via ffmpeg.

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

CI runs the test suite on Python 3.10–3.13.

## License

[MIT](LICENSE)
