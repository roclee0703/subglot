"""Whisper transcription via faster-whisper.

Design notes (learned the hard way, see docs/pitfalls.md):

* ``language=None`` means auto-detect. Never pass a forced ``language`` to
  Whisper as a way to *check* which language the audio is in -- Whisper will
  happily hallucinate a full transcript in the forced language, with
  timestamps that line up perfectly with the real speech.
* faster-whisper decodes audio with PyAV, so mp4/m4a/mp3/wav inputs work
  without a separate ffmpeg step.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TranscriptInfo:
    language: str
    language_probability: float
    duration: float


def transcribe(
    media_path,
    model_size: str = "base",
    language: str | None = None,
    device: str = "auto",
    compute_type: str = "auto",
    vad_filter: bool = True,
):
    """Transcribe ``media_path`` into subtitle cues.

    Returns ``(cues, TranscriptInfo)``. ``language=None`` (the default and
    the CLI's ``--language auto``) lets Whisper detect the language.
    """
    from faster_whisper import WhisperModel  # lazy: keeps import cheap

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments_iter, info = model.transcribe(
        str(media_path),
        language=language,
        vad_filter=vad_filter,
    )
    from .subtitles import Cue

    cues: list[Cue] = []
    idx = 0
    for seg in segments_iter:
        text = (seg.text or "").strip()
        if not text:
            continue
        idx += 1
        cues.append(Cue(idx, seg.start, seg.end, [text]))
    return cues, TranscriptInfo(
        language=info.language or "unknown",
        language_probability=float(info.language_probability or 0.0),
        duration=float(info.duration or 0.0),
    )
