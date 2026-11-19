"""LLM translation of subtitle cues via any OpenAI-compatible chat API.

Batches cues per request and passes the last few translated lines as
context so terminology stays consistent across a video.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from .subtitles import Cue, wrap_text

SYSTEM_PROMPT_TEMPLATE = """You are a professional subtitle translator. \
Translate each subtitle line from {src} to {dst}.

Rules:
- Reply with ONLY a JSON array of translated strings, same length and same \
order as the input lines. No explanations, no markdown fences.
- Keep each translation concise and readable as an on-screen subtitle: \
ideally no more than {max_chars} full-width characters per line.
- Translate meaning, not words. Use natural, spoken phrasing.
- Do not merge or split lines: output count must equal input count.
- Keep proper nouns, numbers and technical terms accurate; keep code \
switching (brand names, product names) in their original form when that is \
the natural choice."""

UNKNOWN_SRC = "the source language (detect it from the text)"


@dataclass
class TranslateConfig:
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    target_lang: str = "Chinese (Simplified)"
    src_lang: str | None = None  # None = let the model detect
    batch_size: int = 20
    context_lines: int = 3
    max_units: float = 20.0
    temperature: float = 0.2
    timeout: float = 120.0


def _parse_json_array(content: str) -> list[str]:
    """Extract a JSON string array from a model reply, tolerating fences."""
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("model reply contains no JSON array")
    arr = json.loads(text[start : end + 1])
    if not isinstance(arr, list) or not all(isinstance(x, str) for x in arr):
        raise ValueError("model reply is not a JSON array of strings")
    return arr


def _chat(cfg: TranslateConfig, messages: list[dict]) -> str:
    resp = httpx.post(
        f"{cfg.base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {cfg.api_key}"},
        json={
            "model": cfg.model,
            "messages": messages,
            "temperature": cfg.temperature,
        },
        timeout=cfg.timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _translate_batch(
    cfg: TranslateConfig, batch: list[Cue], context: list[str]
) -> list[str]:
    src = cfg.src_lang or UNKNOWN_SRC
    system = SYSTEM_PROMPT_TEMPLATE.format(
        src=src,
        dst=cfg.target_lang,
        max_chars=int(cfg.max_units),
    )
    lines = [c.text.replace("\n", " ") for c in batch]
    user_payload = {
        "context": context,
        "lines": lines,
    }
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=False),
        },
    ]
    out = _parse_json_array(_chat(cfg, messages))
    if len(out) != len(batch):
        # One strict retry: models occasionally pad or drop lines.
        messages.append({"role": "assistant", "content": out and json.dumps(out, ensure_ascii=False) or ""})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Your reply had {len(out)} items but the input had "
                    f"{len(batch)}. Reply again with exactly {len(batch)} "
                    "translated strings in the same JSON array format, "
                    "one per input line, same order."
                ),
            }
        )
        out = _parse_json_array(_chat(cfg, messages))
        if len(out) != len(batch):
            raise ValueError(
                f"translator returned {len(out)} lines for a batch of "
                f"{len(batch)} after retry"
            )
    return out


def translate_cues(cues: list[Cue], cfg: TranslateConfig) -> list[Cue]:
    """Translate cues into ``cfg.target_lang`` and wrap lines for display."""
    translated: list[Cue] = []
    context: list[str] = []
    for start in range(0, len(cues), cfg.batch_size):
        batch = cues[start : start + cfg.batch_size]
        out = _translate_batch(cfg, batch, context)
        for cue, text in zip(batch, out):
            translated.append(
                Cue(cue.index, cue.start, cue.end, wrap_text(text, cfg.max_units))
            )
        context = [t for t in (" ".join(c.lines) for c in translated[-cfg.context_lines :]) if t]
    return translated
