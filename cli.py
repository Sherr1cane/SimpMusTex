"""CLI for MusTex manual jianpu input."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from SimpMusTex import MusTexParseError, parse_mustex_text, render_score_svg, render_score_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse or print MusTex jianpu text.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser("parse", help="Parse MusTex text into JSON.")
    parse_parser.add_argument("input", help="Path to a MusTex text file.")
    parse_parser.add_argument("-o", "--output", help="Optional JSON output path.")

    print_parser = subparsers.add_parser("print", help="Print normalized MusTex text.")
    print_parser.add_argument("input", help="Path to a MusTex text file or score JSON.")

    svg_parser = subparsers.add_parser("svg", help="Render MusTex text or score JSON to SVG.")
    svg_parser.add_argument("input", help="Path to a MusTex text file or score JSON.")
    svg_parser.add_argument("-o", "--output", help="Optional SVG output path.")

    args = parser.parse_args()
    try:
        if args.command == "parse":
            return _run_parse(args.input, args.output)
        if args.command == "print":
            return _run_print(args.input)
        if args.command == "svg":
            return _run_svg(args.input, args.output)
    except MusTexParseError as exc:
        print(f"MusTex parse error: {exc}", file=sys.stderr)
        return 2
    return 1


def _run_parse(input_path: str, output_path: str | None) -> int:
    text = Path(input_path).read_text(encoding="utf-8")
    score = parse_mustex_text(text)
    serialized = json.dumps(score, ensure_ascii=False, indent=2)
    if output_path:
        Path(output_path).write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)
    return 0


def _run_print(input_path: str) -> int:
    score = _load_score(input_path)
    print(render_score_text(score), end="")
    return 0


def _run_svg(input_path: str, output_path: str | None) -> int:
    score = _load_score(input_path)
    svg = render_score_svg(score)
    if output_path:
        Path(output_path).write_text(svg, encoding="utf-8")
    else:
        print(svg, end="")
    return 0


def _load_score(input_path: str) -> dict:
    raw = Path(input_path).read_text(encoding="utf-8")
    stripped = raw.lstrip()
    if stripped.startswith("{"):
        return json.loads(raw)
    return parse_mustex_text(raw)


if __name__ == "__main__":
    raise SystemExit(main())
