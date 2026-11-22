"""Command-line interface for subglot."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .subtitles import parse_srt, write_srt
from .validate import report, validate


def _add_asr_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--model", default="base", help="Whisper model size (tiny/base/small/medium/large-v3)")
    p.add_argument(
        "--language",
        default="auto",
        help="source language code (en, ja, ...) or 'auto' to detect (recommended)",
    )
    p.add_argument("--device", default="auto", help="cpu / cuda / auto")
    p.add_argument("--compute-type", default="auto", help="faster-whisper compute type")


def cmd_transcribe(args: argparse.Namespace) -> int:
    try:
        from .transcribe import transcribe
    except ImportError as exc:  # faster-whisper not installed
        print(f"error: transcription needs the 'asr' extra: pip install 'subglot[asr]' ({exc})", file=sys.stderr)
        return 2
    language = None if args.language == "auto" else args.language
    cues, info = transcribe(
        Path(args.media),
        model_size=args.model,
        language=language,
        device=args.device,
        compute_type=args.compute_type,
    )
    out = Path(args.output) if args.output else Path(args.media).with_suffix(".srt")
    write_srt(cues, out)
    print(f"detected language: {info.language} (p={info.language_probability:.2f})")
    print(f"wrote {len(cues)} cues -> {out}")
    return 0


def cmd_translate(args: argparse.Namespace) -> int:
    from .translate import TranslateConfig, translate_cues

    cues = parse_srt(Path(args.input))
    cfg = TranslateConfig(
        base_url=args.base_url,
        api_key=os.environ.get(args.api_key_env, ""),
        model=args.model,
        target_lang=args.target,
        src_lang=None if args.src in (None, "auto") else args.src,
        batch_size=args.batch,
        max_units=args.max_units,
    )
    if not cfg.api_key:
        print(f"error: set the API key in the {args.api_key_env} environment variable", file=sys.stderr)
        return 2
    out_cues = translate_cues(cues, cfg)
    out = Path(args.output) if args.output else Path(args.input).with_name(
        Path(args.input).stem + f".{args.target.split('(')[0].strip().lower()}.srt"
    )
    write_srt(out_cues, out)
    print(f"translated {len(cues)} cues -> {out}")
    issues = validate(out_cues, max_units=args.max_units)
    print(report(issues))
    return 1 if any(i.level == "error" for i in issues) else 0


def cmd_validate(args: argparse.Namespace) -> int:
    cues = parse_srt(Path(args.input))
    issues = validate(cues, max_cps=args.max_cps, max_units=args.max_units, max_lines=args.max_lines)
    print(report(issues))
    return 1 if any(i.level == "error" for i in issues) else 0


def cmd_merge(args: argparse.Namespace) -> int:
    from .merge import merge_cues

    primary = parse_srt(Path(args.primary))
    secondary = parse_srt(Path(args.secondary))
    merged = merge_cues(primary, secondary, layout=args.layout)
    out = Path(args.output) if args.output else Path(args.primary).with_name(
        Path(args.primary).stem + ".bilingual.srt"
    )
    write_srt(merged, out)
    print(f"merged {len(merged)} bilingual cues -> {out}")
    return 0


def cmd_pipeline(args: argparse.Namespace) -> int:
    """transcribe -> translate -> validate in one shot."""
    try:
        from .transcribe import transcribe
    except ImportError as exc:
        print(f"error: transcription needs the 'asr' extra: pip install 'subglot[asr]' ({exc})", file=sys.stderr)
        return 2
    from .translate import TranslateConfig, translate_cues

    language = None if args.language == "auto" else args.language
    cues, info = transcribe(
        Path(args.media),
        model_size=args.asr_model,
        language=language,
        device=args.device,
        compute_type=args.compute_type,
    )
    print(f"detected language: {info.language} (p={info.language_probability:.2f})")
    src_srt = Path(args.src_srt) if args.src_srt else Path(args.media).with_suffix(".srt")
    write_srt(cues, src_srt)
    print(f"wrote {len(cues)} source cues -> {src_srt}")

    cfg = TranslateConfig(
        base_url=args.base_url,
        api_key=os.environ.get(args.api_key_env, ""),
        model=args.model,
        target_lang=args.target,
        batch_size=args.batch,
        max_units=args.max_units,
    )
    if not cfg.api_key:
        print(f"error: set the API key in the {args.api_key_env} environment variable", file=sys.stderr)
        return 2
    out_cues = translate_cues(cues, cfg)
    out = Path(args.output) if args.output else Path(args.media).with_suffix(".translated.srt")
    write_srt(out_cues, out)
    print(f"translated {len(cues)} cues -> {out}")

    if getattr(args, "bilingual", False):
        from .merge import merge_cues

        bilingual_cues = merge_cues(out_cues, cues, layout=args.bilingual_layout)
        bilingual_out = (
            Path(args.bilingual_output)
            if args.bilingual_output
            else Path(args.media).with_suffix(".bilingual.srt")
        )
        write_srt(bilingual_cues, bilingual_out)
        print(f"wrote {len(bilingual_cues)} bilingual cues -> {bilingual_out}")

    issues = validate(out_cues, max_units=args.max_units)
    print(report(issues))
    return 1 if any(i.level == "error" for i in issues) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subglot",
        description="Subtitle transcription and translation pipeline (Whisper + any OpenAI-compatible LLM).",
    )
    parser.add_argument("--version", action="version", version=f"subglot {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("transcribe", help="media file -> SRT (source language)")
    p.add_argument("media", help="video or audio file")
    p.add_argument("-o", "--output", help="output SRT path (default: same name, .srt)")
    _add_asr_args(p)
    p.set_defaults(func=cmd_transcribe)

    p = sub.add_parser("translate", help="SRT -> translated SRT")
    p.add_argument("input", help="source-language SRT")
    p.add_argument("-o", "--output", help="output SRT path")
    p.add_argument("--target", default="Chinese (Simplified)", help="target language")
    p.add_argument("--src", default="auto", help="source language hint (default: auto)")
    p.add_argument("--base-url", default="https://api.openai.com/v1", help="OpenAI-compatible API base URL")
    p.add_argument("--model", default="gpt-4o-mini")
    p.add_argument("--api-key-env", default="OPENAI_API_KEY", help="env var holding the API key")
    p.add_argument("--batch", type=int, default=20, help="cues per LLM request")
    p.add_argument("--max-units", type=float, default=20.0, help="max display units per line")
    p.set_defaults(func=cmd_translate)

    p = sub.add_parser("validate", help="QA-check an SRT file")
    p.add_argument("input", help="SRT file")
    p.add_argument("--max-cps", type=float, default=20.0, help="max reading speed (units/s)")
    p.add_argument("--max-units", type=float, default=20.0, help="max display units per line")
    p.add_argument("--max-lines", type=int, default=2)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("merge", help="merge two SRT files into a bilingual subtitle track")
    p.add_argument("primary", help="primary subtitle track (e.g. translated SRT)")
    p.add_argument("secondary", help="secondary subtitle track (e.g. source SRT)")
    p.add_argument("-o", "--output", help="output bilingual SRT path")
    p.add_argument(
        "--layout",
        choices=["primary-first", "secondary-first"],
        default="primary-first",
        help="order of lines: primary-first (target on top) or secondary-first (source on top)",
    )
    p.set_defaults(func=cmd_merge)

    p = sub.add_parser("pipeline", help="media -> transcribe -> translate -> validate")
    p.add_argument("media", help="video or audio file")
    p.add_argument("-o", "--output", help="translated SRT path")
    p.add_argument("--src-srt", help="where to keep the source-language SRT")
    p.add_argument("--asr-model", default="base", help="Whisper model size (tiny/base/small/medium/large-v3)")
    p.add_argument(
        "--language",
        default="auto",
        help="source language code (en, ja, ...) or 'auto' to detect (recommended)",
    )
    p.add_argument("--device", default="auto", help="cpu / cuda / auto")
    p.add_argument("--compute-type", default="auto", help="faster-whisper compute type")
    p.add_argument("--target", default="Chinese (Simplified)")
    p.add_argument("--base-url", default="https://api.openai.com/v1")
    p.add_argument("--model", default="gpt-4o-mini", help="LLM model for translation")
    p.add_argument("--api-key-env", default="OPENAI_API_KEY")
    p.add_argument("--batch", type=int, default=20)
    p.add_argument("--max-units", type=float, default=20.0)
    p.add_argument("--bilingual", action="store_true", help="also generate a merged bilingual SRT file")
    p.add_argument(
        "--bilingual-layout",
        choices=["primary-first", "secondary-first"],
        default="primary-first",
        help="order of bilingual lines (default: primary-first)",
    )
    p.add_argument("--bilingual-output", help="custom output path for the bilingual SRT file")
    p.set_defaults(func=cmd_pipeline)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
