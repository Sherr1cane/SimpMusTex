"""Parse MusTex text into a jianpu-oriented JSON structure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape


class MusTexParseError(ValueError):
    """Raised when MusTex input is invalid."""


@dataclass
class HeaderBlock:
    metadata: dict[str, Any]
    global_config: dict[str, Any]
    body: str


def parse_mustex_text(text: str) -> dict[str, Any]:
    """Parse MusTex text into a JSON-serialisable score object."""
    header_block = _split_headers(text)
    measures, curves, groups, tuplets, houses = _parse_body(header_block.body)
    return {
        "schema": "mustex-score/v0.1",
        "format": "MusTex",
        "metadata": header_block.metadata,
        "global": header_block.global_config,
        "sections": [
            {
                "id": "section_1",
                "name": "Main",
                "type": "body",
                "measures": measures,
                "curves": curves,
                "groups": groups,
                "tuplets": tuplets,
                "houses": houses,
            }
        ],
        "source": {
            "type": "mustex",
            "lyricsMode": "none",
            "input": text.rstrip(),
        },
    }


def score_to_dict(score: dict[str, Any]) -> dict[str, Any]:
    """Return the score as-is for a stable public surface."""
    return score


def render_score_text(score: dict[str, Any]) -> str:
    """Render score JSON back into normalized MusTex text."""
    metadata = score.get("metadata", {})
    global_config = score.get("global", {})
    lines: list[str] = []

    if metadata.get("title"):
        lines.append(f"title: {metadata['title']}")
    if metadata.get("composer"):
        lines.append(f"composer: {metadata['composer']}")
    if metadata.get("arranger"):
        lines.append(f"arranger: {metadata['arranger']}")

    key = global_config.get("key", {})
    if key.get("tonicDegree") and key.get("tonicPitch"):
        lines.append(f"key: {key['tonicDegree']}={key['tonicPitch']}")

    meter = global_config.get("meter", {})
    if meter.get("beats") and meter.get("beatType"):
        lines.append(f"meter: {meter['beats']}/{meter['beatType']}")

    tempo = global_config.get("tempo", {})
    if tempo.get("bpm") is not None:
        lines.append(f"tempo: {tempo['bpm']}")

    if lines:
        lines.append("")

    sections = score.get("sections") or []
    measures = sections[0].get("measures", []) if sections else []
    curves = sections[0].get("curves", []) if sections else []
    groups = sections[0].get("groups", []) if sections else []
    tuplets = sections[0].get("tuplets", []) if sections else []
    houses = sections[0].get("houses", []) if sections else []
    starts = _annotation_starts(curves, groups, tuplets)
    ends = _annotation_ends(curves, groups, tuplets)
    house_starts = _house_starts(houses)
    house_ends = _house_ends(houses)
    rendered_measures = []
    for index, measure in enumerate(measures):
        prefix_chunks: list[str] = []
        measure_number = index + 1
        if measure_number in house_starts:
            prefix_chunks.append(f"[{house_starts[measure_number]}")
        if measure.get("leftBarline", {}).get("type") == "repeatStart":
            prefix_chunks.append("|:")
        tokens = []
        for element in measure.get("elements", []):
            token = _render_element(element)
            element_id = element.get("id")
            start_markers = starts.get(element_id, [])
            end_markers = ends.get(element_id, [])
            prefix_tokens = []
            suffix_tokens = []
            for marker in start_markers:
                kind = marker["kind"]
                if kind == "slur":
                    prefix_tokens.append("<s")
                elif kind == "phrase":
                    prefix_tokens.append("<p")
                elif kind == "mute":
                    prefix_tokens.append("(")
                elif kind == "tuplet":
                    prefix_tokens.extend(["<tuplet", marker["ratio"]])
                elif kind == "tie":
                    token = f"{token}~"
            for marker in end_markers:
                kind = marker["kind"]
                if kind in {"slur", "phrase", "tuplet"}:
                    suffix_tokens.append(">")
                elif kind == "mute":
                    suffix_tokens.append(")")
            tokens.extend(prefix_tokens)
            tokens.append(token)
            tokens.extend(suffix_tokens)
        body = " ".join(tokens).strip()
        suffix = _render_measure_right_barline(measure, is_last=index == len(measures) - 1)
        measure_tokens = prefix_chunks + ([body] if body else []) + [suffix]
        measure_text = " ".join(part for part in measure_tokens if part).strip()
        if measure_number in house_ends:
            measure_text = f"{measure_text}]"
        rendered_measures.append(measure_text)

    lines.append(" ".join(rendered_measures).strip())
    return "\n".join(line.rstrip() for line in lines if line is not None).rstrip() + "\n"


def render_score_svg(score: dict[str, Any]) -> str:
    """Render score JSON into a simple numbered-notation SVG."""
    metadata = score.get("metadata", {})
    global_config = score.get("global", {})
    sections = score.get("sections") or []
    measures = sections[0].get("measures", []) if sections else []
    curves = sections[0].get("curves", []) if sections else []
    groups = sections[0].get("groups", []) if sections else []
    tuplets = sections[0].get("tuplets", []) if sections else []
    houses = sections[0].get("houses", []) if sections else []

    margin_x = 48
    margin_y = 44
    title_y = 36
    header_y = 70
    tempo_y = 92
    row_top = 138
    row_gap = 110
    measure_gap = 18
    row_width = 980
    beats_unit = 42
    digits_y = 0
    max_rows = 1

    title = metadata.get("title")
    key = global_config.get("key", {})
    meter = global_config.get("meter", {})
    tempo = global_config.get("tempo", {})
    meter_beats = int(meter.get("beats") or 4)
    measures_per_row = 5
    rows: list[list[dict[str, Any]]] = []
    current_row: list[dict[str, Any]] = []
    for measure in measures:
        if len(current_row) >= measures_per_row:
            rows.append(current_row)
            current_row = []
        current_row.append(measure)
    if current_row:
        rows.append(current_row)
    max_rows = max(1, len(rows))

    width = int(margin_x * 2 + row_width)
    height = int(row_top + (max_rows - 1) * row_gap + 90)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        "<style>",
        ".title { font: 700 28px 'Noto Serif CJK SC', 'Songti SC', serif; }",
        ".meta { font: 16px 'Helvetica Neue', Arial, sans-serif; fill: #444; }",
        ".digit { font: 32px 'Helvetica Neue', Arial, sans-serif; font-weight: 600; }",
        ".mark { font: 18px 'Helvetica Neue', Arial, sans-serif; }",
        ".grace { font: 14px 'Helvetica Neue', Arial, sans-serif; }",
        ".dash { font: 16px 'Helvetica Neue', Arial, sans-serif; }",
        ".bar { stroke: #111; stroke-width: 2; }",
        ".thin { stroke: #111; stroke-width: 1.5; }",
        ".dot { fill: #111; }",
        "</style>",
        '<rect width="100%" height="100%" fill="white" />',
    ]

    if title:
        parts.append(
            f'<text x="{width / 2:.1f}" y="{title_y}" text-anchor="middle" class="title">{escape(str(title))}</text>'
        )
    header_chunks = []
    if key.get("tonicDegree") and key.get("tonicPitch"):
        header_chunks.append(f"1={key['tonicPitch']}" if key["tonicDegree"] == 1 else f"{key['tonicDegree']}={key['tonicPitch']}")
    if meter.get("beats") and meter.get("beatType"):
        header_chunks.append(f"{meter['beats']}/{meter['beatType']}")
    if header_chunks:
        parts.append(
            f'<text x="{margin_x}" y="{header_y}" class="meta">{"   ".join(escape(chunk) for chunk in header_chunks)}</text>'
        )
    if tempo.get("bpm") is not None:
        parts.append(
            f'<text x="{margin_x}" y="{tempo_y}" class="meta">{"♩ = " + escape(str(tempo["bpm"]))}</text>'
        )

    placements: dict[str, dict[str, float | int]] = {}
    measure_bounds: dict[str, dict[str, float | int]] = {}
    for row_index, row in enumerate(rows):
        y = row_top + row_index * row_gap
        x = margin_x
        row_measure_widths = _allocate_row_measure_widths(row, row_width, measure_gap)
        for measure_index, (measure, measure_width) in enumerate(zip(row, row_measure_widths)):
            measure_parts, measure_placements = _render_measure_svg(
                measure,
                x=x,
                y=y + digits_y,
                width=measure_width,
                beats_unit=beats_unit,
                meter_beats=meter_beats,
                draw_left_barline=measure_index == 0,
            )
            parts.extend(measure_parts)
            placements.update(measure_placements)
            measure_bounds[measure["id"]] = {
                "left_x": x + 24,
                "right_x": x + measure_width - 16,
                "row_y": y,
                "top_y": y - 28,
            }
            x += measure_width + measure_gap

    parts.extend(_render_curves_svg(curves, placements))
    parts.extend(_render_groups_svg(groups, placements))
    parts.extend(_render_tuplets_svg(tuplets, placements))
    parts.extend(_render_houses_svg(houses, measures, measure_bounds))

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _split_headers(text: str) -> HeaderBlock:
    metadata: dict[str, Any] = {}
    global_config: dict[str, Any] = {
        "key": {
            "tonicDegree": 1,
            "tonicPitch": "C",
            "mode": "major",
        },
        "meter": {
            "beats": 4,
            "beatType": 4,
        },
        "tempo": {
            "beatUnit": "quarter",
            "bpm": None,
        },
    }

    lines = text.splitlines()
    body_start = 0
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            body_start = index + 1
            break
        if ":" not in line:
            body_start = index
            break

        key, value = [part.strip() for part in line.split(":", 1)]
        key_lower = key.lower()
        if key_lower == "title":
            metadata["title"] = value
        elif key_lower == "composer":
            metadata["composer"] = value
        elif key_lower == "arranger":
            metadata["arranger"] = value
        elif key_lower == "key":
            global_config["key"] = _parse_key_header(value)
        elif key_lower == "meter":
            global_config["meter"] = _parse_meter_header(value)
        elif key_lower == "tempo":
            global_config["tempo"] = {
                "beatUnit": "quarter",
                "bpm": _parse_number(value, "tempo"),
            }
        else:
            metadata[key_lower] = value
        body_start = index + 1

    body = "\n".join(lines[body_start:]).strip()
    if not body:
        raise MusTexParseError("MusTex body is empty.")
    return HeaderBlock(metadata=metadata, global_config=global_config, body=body)


def _parse_key_header(value: str) -> dict[str, Any]:
    if "=" not in value:
        raise MusTexParseError(f"Invalid key header: {value!r}")
    degree_text, pitch_text = [part.strip() for part in value.split("=", 1)]
    degree = int(degree_text)
    if degree < 1 or degree > 7:
        raise MusTexParseError(f"Key tonic degree must be 1..7: {value!r}")
    if not pitch_text:
        raise MusTexParseError(f"Key tonic pitch is missing: {value!r}")
    return {
        "tonicDegree": degree,
        "tonicPitch": pitch_text,
        "mode": "major",
    }


def _parse_meter_header(value: str) -> dict[str, int]:
    if "/" not in value:
        raise MusTexParseError(f"Invalid meter header: {value!r}")
    beats_text, beat_type_text = [part.strip() for part in value.split("/", 1)]
    return {
        "beats": int(beats_text),
        "beatType": int(beat_type_text),
    }


def _parse_number(value: str, field_name: str) -> int | float:
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError as exc:
            raise MusTexParseError(f"Invalid numeric value for {field_name}: {value!r}") from exc


def _parse_body(
    body: str,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    raw_tokens = _tokenize_body(body)
    measures: list[dict[str, Any]] = []
    current_elements: list[dict[str, Any]] = []
    next_left_barline = {"type": "normal"}
    curves: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    tuplets: list[dict[str, Any]] = []
    houses: list[dict[str, Any]] = []
    element_counter = 0
    pending_tie_start: str | None = None
    span_stack: list[dict[str, Any]] = []
    current_house: dict[str, Any] | None = None

    def append_element(token: str) -> dict[str, Any]:
        nonlocal element_counter, pending_tie_start
        element_counter += 1
        element = _parse_element(token)
        element["id"] = f"e{element_counter:04d}"
        current_elements.append(element)
        for span_state in span_stack:
            if span_state["startId"] is None:
                span_state["startId"] = element["id"]
            span_state["endId"] = element["id"]
        if pending_tie_start is not None:
            _validate_tie_pair(pending_tie_start, element, measures, current_elements)
            curves.append(
                {
                    "id": f"curve_tie_{len(curves) + 1:03d}",
                    "kind": "tie",
                    "startId": pending_tie_start,
                    "endId": element["id"],
                }
            )
            pending_tie_start = None
        return element

    for token in raw_tokens:
        if token == "<tuplet":
            span_stack.append({"kind": "tuplet", "startId": None, "endId": None, "ratio": None})
            continue
        if span_stack and span_stack[-1]["kind"] == "tuplet" and span_stack[-1]["ratio"] is None:
            span_stack[-1]["ratio"] = _parse_tuplet_ratio(token)
            continue
        if token == "<s":
            span_stack.append({"kind": "slur", "startId": None, "endId": None})
            continue
        if token == "<p":
            span_stack.append({"kind": "phrase", "startId": None, "endId": None})
            continue
        if token == "(":
            span_stack.append({"kind": "mute", "startId": None, "endId": None})
            continue
        if token == ">":
            if not span_stack or span_stack[-1]["kind"] not in {"slur", "phrase", "tuplet"}:
                raise MusTexParseError("Encountered '>' without a matching '<s'.")
            span_state = span_stack.pop()
            if not span_state["startId"] or not span_state["endId"]:
                raise MusTexParseError(f"{span_state['kind']} span must contain at least one note.")
            if span_state["kind"] == "tuplet":
                tuplets.append(
                    {
                        "id": f"tuplet_{len(tuplets) + 1:03d}",
                        "kind": "tuplet",
                        "ratio": span_state["ratio"]["ratio"],
                        "actual": span_state["ratio"]["actual"],
                        "normal": span_state["ratio"]["normal"],
                        "startId": span_state["startId"],
                        "endId": span_state["endId"],
                    }
                )
            else:
                curves.append(
                    {
                        "id": f"curve_{span_state['kind']}_{len(curves) + 1:03d}",
                        "kind": span_state["kind"],
                        "startId": span_state["startId"],
                        "endId": span_state["endId"],
                    }
                )
            continue
        if token == ")":
            if not span_stack or span_stack[-1]["kind"] != "mute":
                raise MusTexParseError("Encountered ')' without a matching '('.")
            span_state = span_stack.pop()
            if not span_state["startId"] or not span_state["endId"]:
                raise MusTexParseError("Mute group '( ... )' must contain at least one note.")
            groups.append(
                {
                    "id": f"group_mute_{len(groups) + 1:03d}",
                    "kind": "mute",
                    "startId": span_state["startId"],
                    "endId": span_state["endId"],
                }
            )
            continue
        if token.startswith("[") and token[1:].isdigit():
            if current_house is not None:
                raise MusTexParseError("Nested house markers are not supported.")
            current_house = {
                "id": f"house_{len(houses) + 1:03d}",
                "number": int(token[1:]),
                "startMeasure": len(measures) + 1,
            }
            continue
        if token == "]":
            if current_house is None:
                raise MusTexParseError("Encountered ']' without a matching house start.")
            current_house["endMeasure"] = len(measures) if not current_elements else len(measures) + 1
            houses.append(current_house)
            current_house = None
            continue
        if token in {"|", "||", "|:", ":|", ":|:"}:
            right_barline, next_left_barline = _handle_barline_token(
                token,
                next_left_barline,
                current_elements,
                is_first_measure=not measures,
            )
            if current_elements:
                measures.append(
                    _make_measure(
                        index=len(measures) + 1,
                        left_barline=next_left_barline.pop("_left_for_current"),
                        elements=current_elements,
                        right_barline=right_barline,
                    )
                )
                current_elements = []
            continue

        if "~" in token:
            left_token, right_token = token.split("~", 1)
            if left_token:
                left_element = append_element(left_token)
                if left_element.get("type") != "note":
                    raise MusTexParseError("Tie start must be a note.")
                pending_tie_start = left_element["id"]
            if right_token:
                right_element = append_element(right_token)
                if right_element.get("type") != "note":
                    raise MusTexParseError("Tie end must be a note.")
            continue

        element = append_element(token)
        if token.endswith("~"):
            if element.get("type") != "note":
                raise MusTexParseError("Tie start must be a note.")
            pending_tie_start = element["id"]

    if current_elements:
        measures.append(
            _make_measure(
                index=len(measures) + 1,
                left_barline=next_left_barline,
                elements=current_elements,
                right_barline={"type": "final"},
            )
        )

    if not measures:
        raise MusTexParseError("MusTex body does not contain any notes or rests.")
    if pending_tie_start is not None:
        raise MusTexParseError("Tie '~' is missing its ending note.")
    if span_stack:
        open_kind = span_stack[-1]["kind"]
        if open_kind == "mute":
            raise MusTexParseError("Mute group '(' is missing closing ')'.")
        raise MusTexParseError(f"{open_kind} span is missing closing '>'.")
    if current_house is not None:
        raise MusTexParseError("House marker '[' is missing closing ']'.")
    return measures, curves, groups, tuplets, houses


def _tokenize_body(body: str) -> list[str]:
    tokens: list[str] = []
    for raw_token in body.replace("\n", " ").split():
        tokens.extend(_split_compound_token(raw_token))
    return [token for token in tokens if token]


def _split_compound_token(raw_token: str) -> list[str]:
    tokens: list[str] = []
    token = raw_token
    if token.startswith("(") and token != "(":
        tokens.append("(")
        token = token[1:]
    while token.startswith((")", "]", ">")) and token not in {")", "]", ">"}:
        tokens.append(token[0])
        token = token[1:]

    trailing: list[str] = []
    while token:
        if token.endswith(")") and "@" in token:
            break
        if token.endswith((">", ")", "]")):
            trailing.append(token[-1])
            token = token[:-1]
            continue
        break

    if token:
        tokens.append(token)
    tokens.extend(reversed(trailing))
    return tokens


def _parse_tuplet_ratio(token: str) -> dict[str, Any]:
    if ":" not in token:
        raise MusTexParseError(f"Invalid tuplet ratio: {token!r}")
    actual_text, normal_text = token.split(":", 1)
    actual = int(actual_text)
    normal = int(normal_text)
    if actual <= 0 or normal <= 0:
        raise MusTexParseError(f"Tuplet ratio must be positive: {token!r}")
    return {
        "ratio": token,
        "actual": actual,
        "normal": normal,
    }


def _handle_barline_token(
    token: str,
    current_left_barline: dict[str, Any],
    current_elements: list[dict[str, Any]],
    *,
    is_first_measure: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not current_elements and token in {"|:", ":|:"} and is_first_measure:
        return {"type": "normal"}, {"type": "repeatStart", "_left_for_current": {"type": "repeatStart"}}

    left_for_current = current_left_barline
    if token == "|":
        return {"type": "normal"}, {"type": "normal", "_left_for_current": left_for_current}
    if token == "||":
        return {"type": "double"}, {"type": "normal", "_left_for_current": left_for_current}
    if token == "|:":
        return {"type": "normal"}, {"type": "repeatStart", "_left_for_current": left_for_current}
    if token == ":|":
        return {"type": "repeatEnd"}, {"type": "normal", "_left_for_current": left_for_current}
    if token == ":|:":
        return {"type": "repeatEnd"}, {"type": "repeatStart", "_left_for_current": left_for_current}
    raise MusTexParseError(f"Unsupported barline token: {token!r}")


def _make_measure(
    *,
    index: int,
    left_barline: dict[str, Any],
    elements: list[dict[str, Any]],
    right_barline: dict[str, Any],
) -> dict[str, Any]:
    clean_left = {k: v for k, v in left_barline.items() if not k.startswith("_")}
    numbered_elements = []
    for element_index, element in enumerate(elements, start=1):
        numbered = dict(element)
        if not numbered.get("id"):
            numbered["id"] = f"m{index:03d}_e{element_index:03d}"
        numbered_elements.append(numbered)
    return {
        "id": f"measure_{index}",
        "index": index,
        "leftBarline": clean_left or {"type": "normal"},
        "rightBarline": right_barline,
        "elements": numbered_elements,
    }


def _parse_element(token: str) -> dict[str, Any]:
    core_token, ornaments = _split_ornaments(token)
    grace_before, core_token = _parse_prefix_graces(core_token)
    core_token, grace_after = _parse_suffix_graces(core_token)

    if core_token.startswith("0"):
        element = _parse_rest(core_token)
    elif core_token and core_token[0] in "1234567":
        element = _parse_note(core_token)
    else:
        raise MusTexParseError(f"Unsupported token: {token!r}")

    if grace_before:
        element["graceBefore"] = grace_before
    if grace_after:
        element["graceAfter"] = grace_after
    if ornaments:
        element["ornaments"] = ornaments
    element["raw"] = token
    return element


def _split_ornaments(token: str) -> tuple[str, list[dict[str, Any]]]:
    if "@" not in token:
        return token, []
    parts = token.split("@")
    base = parts[0]
    ornaments = [_parse_ornament(part) for part in parts[1:] if part]
    return base, ornaments


def _parse_ornament(token: str) -> dict[str, Any]:
    if "(" in token and token.endswith(")"):
        kind, arg_text = token[:-1].split("(", 1)
        args = [item.strip() for item in arg_text.split(",") if item.strip()]
    else:
        kind = token
        args = []
    return {
        "kind": kind,
        "args": args,
    }


def _parse_prefix_graces(token: str) -> tuple[list[dict[str, Any]], str]:
    graces: list[dict[str, Any]] = []
    rest = token
    while rest.startswith("{"):
        close_index = rest.find("}")
        if close_index < 0:
            raise MusTexParseError(f"Grace-note block is missing closing '}}': {token!r}")
        grace_token = rest[1:close_index]
        graces.append(_parse_grace_token(grace_token))
        rest = rest[close_index + 1 :]
    return graces, rest


def _parse_suffix_graces(token: str) -> tuple[str, list[dict[str, Any]]]:
    if "{" not in token:
        return token, []
    open_index = token.find("{")
    close_index = token.find("}", open_index)
    if close_index < 0:
        raise MusTexParseError(f"Grace-note block is missing closing '}}': {token!r}")
    if close_index != len(token) - 1:
        raise MusTexParseError(f"Unexpected content after grace-note block: {token!r}")
    core = token[:open_index]
    grace = _parse_grace_token(token[open_index + 1 : close_index])
    return core, [grace]


def _parse_grace_token(token: str) -> dict[str, Any]:
    slash = False
    accent = False
    rest = token
    if rest.startswith("/"):
        slash = True
        rest = rest[1:]
    if rest.startswith(">"):
        accent = True
        rest = rest[1:]
    if not rest or rest[0] not in "1234567":
        raise MusTexParseError(f"Invalid grace-note token: {token!r}")
    degree = int(rest[0])
    accidental, octave_shift, underlines, dots, extensions = _parse_note_suffix(rest[1:], token)
    if underlines or dots or extensions:
        raise MusTexParseError(f"Grace-note token cannot include duration marks: {token!r}")
    return {
        "degree": degree,
        "accidental": accidental,
        "octaveShift": octave_shift,
        "slash": slash,
        "accent": accent,
    }


def _parse_note(token: str) -> dict[str, Any]:
    degree = int(token[0])
    accidental, octave_shift, underlines, dots, extensions = _parse_note_suffix(token[1:], token)
    duration = _make_duration(underlines=underlines, dots=dots, extensions=extensions)
    return {
        "id": None,
        "type": "note",
        "degree": degree,
        "octaveShift": octave_shift,
        "accidental": accidental,
        "duration": duration,
        "raw": token,
    }


def _parse_rest(token: str) -> dict[str, Any]:
    accidental, octave_shift, underlines, dots, extensions = _parse_note_suffix(token[1:], token)
    if accidental is not None or octave_shift != 0:
        raise MusTexParseError(f"Rest token cannot include accidental or octave markers: {token!r}")
    duration = _make_duration(underlines=underlines, dots=dots, extensions=extensions)
    return {
        "id": None,
        "type": "rest",
        "duration": duration,
        "raw": token,
    }


def _parse_note_suffix(suffix: str, token: str) -> tuple[str | None, int, int, int, int]:
    duration_start = len(suffix)
    for index, char in enumerate(suffix):
        if char in "_.-":
            duration_start = index
            break

    prefix = suffix[:duration_start]
    duration_suffix = suffix[duration_start:]

    accidental: str | None = None
    high_marks = 0
    low_marks = 0
    for char in prefix:
        if char in "#bn":
            if accidental is not None:
                raise MusTexParseError(f"Only one accidental is allowed in {token!r}")
            accidental = {"#": "sharp", "b": "flat", "n": "natural"}[char]
        elif char == "'":
            high_marks += 1
        elif char == ",":
            low_marks += 1
        else:
            raise MusTexParseError(f"Invalid note suffix in {token!r}")

    if high_marks and low_marks:
        raise MusTexParseError(f"Token cannot mix high and low octave markers: {token!r}")
    octave_shift = high_marks if high_marks else -low_marks

    if not duration_suffix:
        return accidental, octave_shift, 0, 0, 0

    if duration_suffix != "_" * duration_suffix.count("_") + "." * duration_suffix.count(".") + "-" * duration_suffix.count("-"):
        raise MusTexParseError(
            f"Duration suffix order must be underlines, then dots, then extensions: {token!r}"
        )

    underlines = duration_suffix.count("_")
    dots = duration_suffix.count(".")
    extensions = duration_suffix.count("-")
    return accidental, octave_shift, underlines, dots, extensions


def _make_duration(*, underlines: int, dots: int, extensions: int) -> dict[str, Any]:
    base_beats = 1 / (2 ** underlines) if underlines >= 0 else 1
    dotted_multiplier = sum(1 / (2**index) for index in range(dots + 1))
    beats = base_beats * dotted_multiplier + extensions
    return {
        "unit": "quarter",
        "underlines": underlines,
        "dots": dots,
        "extensions": extensions,
        "beats": round(beats, 6),
    }


def _render_element(element: dict[str, Any]) -> str:
    base = _render_element_base(element)
    grace_before = "".join(_render_grace_token(grace) for grace in element.get("graceBefore", []))
    grace_after = "".join(_render_grace_token(grace) for grace in element.get("graceAfter", []))
    ornaments = "".join(_render_ornament_token(ornament) for ornament in element.get("ornaments", []))
    return f"{grace_before}{base}{grace_after}{ornaments}"


def _render_element_base(element: dict[str, Any]) -> str:
    duration = element.get("duration", {})
    suffix = (
        "_" * int(duration.get("underlines", 0))
        + "." * int(duration.get("dots", 0))
        + "-" * int(duration.get("extensions", 0))
    )
    if element.get("type") == "rest":
        return f"0{suffix}"

    accidental = {
        None: "",
        "sharp": "#",
        "flat": "b",
        "natural": "n",
    }[element.get("accidental")]
    octave_shift = int(element.get("octaveShift", 0))
    if octave_shift > 0:
        octave = "'" * octave_shift
    elif octave_shift < 0:
        octave = "," * (-octave_shift)
    else:
        octave = ""
    return f"{element['degree']}{accidental}{octave}{suffix}"


def _render_grace_token(grace: dict[str, Any]) -> str:
    prefix = ""
    if grace.get("slash"):
        prefix += "/"
    if grace.get("accent"):
        prefix += ">"
    accidental = {
        None: "",
        "sharp": "#",
        "flat": "b",
        "natural": "n",
    }[grace.get("accidental")]
    octave_shift = int(grace.get("octaveShift", 0))
    octave = "'" * octave_shift if octave_shift > 0 else "," * (-octave_shift)
    return f"{{{prefix}{grace['degree']}{accidental}{octave}}}"


def _render_ornament_token(ornament: dict[str, Any]) -> str:
    args = ornament.get("args") or []
    if args:
        return f"@{ornament['kind']}({','.join(args)})"
    return f"@{ornament['kind']}"


def _render_measure_right_barline(measure: dict[str, Any], *, is_last: bool) -> str:
    right_type = measure.get("rightBarline", {}).get("type", "normal")
    if right_type == "normal":
        return "|"
    if right_type == "double":
        return "||"
    if right_type == "repeatEnd":
        return ":|"
    if right_type == "final":
        return "||" if is_last else "|"
    return "|"


def _render_measure_svg(
    measure: dict[str, Any],
    *,
    x: float,
    y: float,
    width: float,
    beats_unit: float,
    meter_beats: int,
    draw_left_barline: bool,
) -> tuple[list[str], dict[str, dict[str, float | int]]]:
    parts: list[str] = []
    placements: dict[str, dict[str, float | int]] = {}
    top = y - 28
    bottom = y + 42

    cursor = x
    if draw_left_barline:
        left_type = measure.get("leftBarline", {}).get("type", "normal")
        parts.extend(_render_barline_svg(left_type, cursor, top, bottom, is_left=True))
    cursor += 18
    content_left = cursor + 6
    content_right = x + width - 28
    content_width = max(1.0, content_right - content_left)

    positioned_elements: list[dict[str, Any]] = []
    elements = measure.get("elements", [])
    slot_count = max(
        1,
        sum(
            1 + int(element.get("duration", {}).get("extensions", 0))
            for element in elements
        ),
    )
    cell_width = content_width / slot_count
    beat_cursor = 0.0
    slot_index = 0
    for element in elements:
        duration = element.get("duration", {})
        beats = max(0.25, float(duration.get("beats", 1.0)))
        extensions = int(duration.get("extensions", 0))
        span_left = content_left + cell_width * slot_index
        span_right = content_left + cell_width * (slot_index + 1)
        extension_slot_centers = [
            content_left + cell_width * (slot_index + 1 + ext_index) + cell_width / 2
            for ext_index in range(extensions)
        ]
        positioned_elements.append(
            {
                "element": element,
                "span_left": span_left,
                "span_right": span_right,
                "baseline_y": y,
                "start_beat": beat_cursor,
                "end_beat": beat_cursor + beats,
                "slot_index": slot_index,
                "slot_width": cell_width,
                "extension_slot_centers": extension_slot_centers,
            }
        )
        beat_cursor += beats
        slot_index += 1 + extensions

    _apply_minimum_spacing(positioned_elements)

    for item in positioned_elements:
        element = item["element"]
        center_x = item["center_x"]
        placements[element["id"]] = {
            "center_x": center_x,
            "baseline_y": y,
            "row_y": y,
        }
        parts.extend(_render_element_svg(element, center_x, y))

    parts.extend(_render_underlines_svg(positioned_elements, content_left, content_width, meter_beats))
    parts.extend(_render_extensions_svg(positioned_elements, content_left, content_width, meter_beats))

    right_x = x + width - 12
    right_type = measure.get("rightBarline", {}).get("type", "normal")
    parts.extend(_render_barline_svg(right_type, right_x, top, bottom, is_left=False))
    return parts, placements


def _render_barline_svg(barline_type: str, x: float, top: float, bottom: float, *, is_left: bool) -> list[str]:
    parts: list[str] = []
    if barline_type == "repeatStart":
        parts.append(f'<line x1="{x + 4:.1f}" y1="{top:.1f}" x2="{x + 4:.1f}" y2="{bottom:.1f}" class="thin" />')
        parts.append(f'<line x1="{x + 9:.1f}" y1="{top:.1f}" x2="{x + 9:.1f}" y2="{bottom:.1f}" class="bar" />')
        parts.append(f'<circle cx="{x + 14:.1f}" cy="{(top + bottom) / 2 - 8:.1f}" r="1.8" class="dot" />')
        parts.append(f'<circle cx="{x + 14:.1f}" cy="{(top + bottom) / 2 + 8:.1f}" r="1.8" class="dot" />')
        return parts
    if barline_type == "repeatEnd":
        parts.append(f'<circle cx="{x - 5:.1f}" cy="{(top + bottom) / 2 - 8:.1f}" r="1.8" class="dot" />')
        parts.append(f'<circle cx="{x - 5:.1f}" cy="{(top + bottom) / 2 + 8:.1f}" r="1.8" class="dot" />')
        parts.append(f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" y2="{bottom:.1f}" class="bar" />')
        parts.append(f'<line x1="{x + 5:.1f}" y1="{top:.1f}" x2="{x + 5:.1f}" y2="{bottom:.1f}" class="thin" />')
        return parts
    if barline_type in {"double", "final"}:
        parts.append(f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" y2="{bottom:.1f}" class="thin" />')
        parts.append(f'<line x1="{x + 5:.1f}" y1="{top:.1f}" x2="{x + 5:.1f}" y2="{bottom:.1f}" class="bar" />')
        return parts
    parts.append(f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" y2="{bottom:.1f}" class="thin" />')
    return parts


def _render_element_svg(element: dict[str, Any], center_x: float, baseline_y: float) -> list[str]:
    parts: list[str] = []
    element_type = element.get("type")
    digit = "0" if element_type == "rest" else str(element.get("degree", ""))

    parts.extend(_render_grace_svg(element.get("graceBefore", []), center_x - 18, center_x, baseline_y, align="end"))
    parts.append(
        f'<text x="{center_x:.1f}" y="{baseline_y:.1f}" text-anchor="middle" dominant-baseline="middle" class="digit">{escape(digit)}</text>'
    )
    parts.extend(_render_grace_svg(element.get("graceAfter", []), center_x + 18, center_x, baseline_y, align="start"))
    duration = element.get("duration", {})

    if element_type == "note":
        accidental = element.get("accidental")
        accidental_text = {"sharp": "#", "flat": "b", "natural": "n", None: ""}.get(accidental, "")
        if accidental_text:
            parts.append(
                f'<text x="{center_x - 18:.1f}" y="{baseline_y:.1f}" text-anchor="middle" dominant-baseline="middle" class="mark">{escape(accidental_text)}</text>'
            )

        octave_shift = int(element.get("octaveShift", 0))
        if octave_shift > 0:
            parts.extend(_render_octave_dots(center_x, baseline_y - 24, octave_shift))
        elif octave_shift < 0:
            underlines = int(duration.get("underlines", 0))
            parts.extend(_render_octave_dots(center_x, _low_octave_dots_y(baseline_y, underlines), -octave_shift))

    dots = int(duration.get("dots", 0))

    for idx in range(dots):
        cx = center_x + 18 + idx * 6
        cy = baseline_y
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="1.8" class="dot" />')
    parts.extend(_render_ornaments_svg(element.get("ornaments", []), center_x, baseline_y))
    return parts


def _render_octave_dots(center_x: float, cy: float, count: int) -> list[str]:
    parts = []
    if count == 1:
        offsets = [0.0]
    elif count == 2:
        offsets = [-5.0, 5.0]
    else:
        offsets = [-(count - 1) * 3.5 + 7.0 * idx for idx in range(count)]
    for offset in offsets:
        parts.append(f'<circle cx="{center_x + offset:.1f}" cy="{cy:.1f}" r="2" class="dot" />')
    return parts


def _low_octave_dots_y(baseline_y: float, underline_count: int, *, underline_base_y: float = 20.0) -> float:
    if underline_count <= 0:
        return baseline_y + 24.0
    lowest_underline_y = baseline_y + underline_base_y + (underline_count - 1) * 7.0
    return max(baseline_y + 24.0, lowest_underline_y + 6.0)


def _render_underlines_svg(
    positioned_elements: list[dict[str, Any]],
    content_left: float,
    content_width: float,
    meter_beats: int,
) -> list[str]:
    parts: list[str] = []
    if not positioned_elements:
        return parts

    max_underlines = max(
        int(item["element"].get("duration", {}).get("underlines", 0))
        for item in positioned_elements
    )
    if max_underlines <= 0:
        return parts

    for level in range(1, max_underlines + 1):
        beat_groups: dict[int, list[dict[str, Any]]] = {}
        for item in positioned_elements:
            element = item["element"]
            if element.get("type") != "note":
                continue
            underlines = int(element.get("duration", {}).get("underlines", 0))
            if underlines < level:
                continue
            beat_index = int(float(item["start_beat"]))
            beat_groups.setdefault(beat_index, []).append(item)

        sorted_beats = sorted(beat_groups)
        group_ranges: list[tuple[int, float, float]] = []
        for beat_index in sorted_beats:
            group = beat_groups[beat_index]
            if not group:
                continue
            anchors = [_underline_anchor(item, level) for item in group]
            if not anchors:
                continue
            group_ranges.append((beat_index, anchors[0][0], anchors[-1][1]))

        range_by_beat = {beat_index: (x1, x2) for beat_index, x1, x2 in group_ranges}
        for idx, beat_index in enumerate(sorted_beats):
            group = beat_groups[beat_index]
            if not group or beat_index not in range_by_beat:
                continue
            y = group[0]["baseline_y"] + 20 + (level - 1) * 7
            raw_x1, raw_x2 = range_by_beat[beat_index]
            x1, x2 = raw_x1, raw_x2
            if idx > 0:
                prev_beat = sorted_beats[idx - 1]
                if prev_beat in range_by_beat:
                    prev_x2 = range_by_beat[prev_beat][1]
                    x1 = max(x1, (prev_x2 + raw_x1) / 2 + 2.0)
            if idx + 1 < len(sorted_beats):
                next_beat = sorted_beats[idx + 1]
                if next_beat in range_by_beat:
                    next_x1 = range_by_beat[next_beat][0]
                    x2 = min(x2, (raw_x2 + next_x1) / 2 - 2.0)
            if len(group) == 1:
                if x2 <= x1:
                    center_x = float(group[0]["center_x"])
                    x1 = center_x - 6.0
                    x2 = center_x + 6.0
                parts.append(
                    f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" class="thin" />'
                )
                continue
            if x2 <= x1:
                center_x = (x1 + x2) / 2.0
                x1 = center_x - 6.0
                x2 = center_x + 6.0
            parts.append(
                f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" class="thin" />'
            )
    return parts


def _underline_anchor(item: dict[str, Any], level: int) -> tuple[float, float]:
    center_x = float(item["center_x"])
    half_width = 7.0 if level == 1 else 6.5
    return (center_x - half_width, center_x + half_width)


def _render_curves_svg(curves: list[dict[str, Any]], placements: dict[str, dict[str, float | int]]) -> list[str]:
    parts: list[str] = []
    for curve in curves:
        start = placements.get(curve.get("startId"))
        end = placements.get(curve.get("endId"))
        if not start or not end:
            continue
        if start["row_y"] != end["row_y"]:
            continue
        start_x = float(start["center_x"])
        end_x = float(end["center_x"])
        baseline_y = min(float(start["baseline_y"]), float(end["baseline_y"]))
        kind = curve.get("kind")
        span = abs(end_x - start_x)
        if kind == "tie":
            arc_y = baseline_y - 16
            control_lift = min(8.0, max(4.0, span * 0.04))
        elif kind == "phrase":
            arc_y = baseline_y - 46
            control_lift = min(24.0, max(14.0, span * 0.1))
        else:
            arc_y = baseline_y - 34
            control_lift = min(18.0, max(10.0, span * 0.08))
        control_y = arc_y - control_lift
        control_x = (start_x + end_x) / 2
        parts.append(
            f'<path d="M {start_x:.1f} {arc_y:.1f} Q {control_x:.1f} {control_y:.1f} {end_x:.1f} {arc_y:.1f}" '
            f'fill="none" class="thin" />'
        )
    return parts


def _render_groups_svg(groups: list[dict[str, Any]], placements: dict[str, dict[str, float | int]]) -> list[str]:
    parts: list[str] = []
    for group in groups:
        if group.get("kind") != "mute":
            continue
        start = placements.get(group.get("startId"))
        end = placements.get(group.get("endId"))
        if not start or not end:
            continue
        start_baseline_y = float(start["baseline_y"])
        end_baseline_y = float(end["baseline_y"])
        parts.append(
            f'<text x="{float(start["center_x"]) - 14:.1f}" y="{start_baseline_y:.1f}" '
            f'text-anchor="middle" dominant-baseline="middle" class="mark">(</text>'
        )
        parts.append(
            f'<text x="{float(end["center_x"]) + 14:.1f}" y="{end_baseline_y:.1f}" '
            f'text-anchor="middle" dominant-baseline="middle" class="mark">)</text>'
        )
    return parts


def _render_tuplets_svg(tuplets: list[dict[str, Any]], placements: dict[str, dict[str, float | int]]) -> list[str]:
    parts: list[str] = []
    for tuplet in tuplets:
        start = placements.get(tuplet.get("startId"))
        end = placements.get(tuplet.get("endId"))
        if not start or not end or start["row_y"] != end["row_y"]:
            continue
        x1 = float(start["center_x"]) - 8
        x2 = float(end["center_x"]) + 8
        y = min(float(start["baseline_y"]), float(end["baseline_y"])) - 58
        mid_x = (x1 + x2) / 2.0
        parts.append(f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{mid_x - 10:.1f}" y2="{y:.1f}" class="thin" />')
        parts.append(f'<line x1="{mid_x + 10:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" class="thin" />')
        parts.append(
            f'<text x="{mid_x:.1f}" y="{y - 2:.1f}" text-anchor="middle" class="meta">{escape(tuplet["ratio"])}</text>'
        )
    return parts


def _render_houses_svg(
    houses: list[dict[str, Any]],
    measures: list[dict[str, Any]],
    measure_bounds: dict[str, dict[str, float | int]],
) -> list[str]:
    parts: list[str] = []
    measure_by_index = {index + 1: measure for index, measure in enumerate(measures)}
    for house in houses:
        start_measure = measure_by_index.get(int(house["startMeasure"]))
        end_measure = measure_by_index.get(int(house["endMeasure"]))
        if not start_measure or not end_measure:
            continue
        start_bounds = measure_bounds.get(start_measure["id"])
        end_bounds = measure_bounds.get(end_measure["id"])
        if not start_bounds or not end_bounds or start_bounds["row_y"] != end_bounds["row_y"]:
            continue
        y = float(start_bounds["top_y"]) - 18
        x1 = float(start_bounds["left_x"])
        x2 = float(end_bounds["right_x"])
        parts.append(f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" class="thin" />')
        parts.append(f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x1:.1f}" y2="{y + 12:.1f}" class="thin" />')
        parts.append(
            f'<text x="{x1 + 8:.1f}" y="{y - 2:.1f}" class="meta">{escape(str(house["number"]))}</text>'
        )
    return parts


def _render_grace_svg(
    graces: list[dict[str, Any]],
    anchor_x: float,
    main_x: float,
    baseline_y: float,
    *,
    align: str,
) -> list[str]:
    parts: list[str] = []
    if not graces:
        return parts
    step = 14.0
    ordered = graces if align == "start" else list(reversed(graces))
    # 倚音整体上移偏移量（相对主音符 baseline_y）
    grace_lift = 12.0
    grace_baseline = baseline_y - grace_lift
    for index, grace in enumerate(ordered):
        x = anchor_x + index * step if align == "start" else anchor_x - index * step
        grace_y = grace_baseline - 5.0
        underline_y1 = grace_baseline + 1.5
        underline_y2 = grace_baseline + 5.0
        parts.append(
            f'<text x="{x:.1f}" y="{grace_y:.1f}" text-anchor="middle" dominant-baseline="middle" class="grace">{escape(str(grace["degree"]))}</text>'
        )
        parts.append(
            f'<line x1="{x - 4.5:.1f}" y1="{underline_y1:.1f}" x2="{x + 4.5:.1f}" y2="{underline_y1:.1f}" class="thin" />'
        )
        parts.append(
            f'<line x1="{x - 4.5:.1f}" y1="{underline_y2:.1f}" x2="{x + 4.5:.1f}" y2="{underline_y2:.1f}" class="thin" />'
        )
        if grace.get("slash"):
            parts.append(
                f'<line x1="{x - 4.5:.1f}" y1="{grace_baseline - 12:.0f}" x2="{x + 4.5:.1f}" y2="{grace_baseline - 1:.0f}" class="thin" />'
            )
        if grace.get("accent"):
            parts.append(
                f'<text x="{x - 7:.1f}" y="{grace_baseline - 8:.1f}" text-anchor="middle" class="meta">&gt;</text>'
            )
        octave_shift = int(grace.get("octaveShift", 0))
        if octave_shift > 0:
            parts.extend(_render_octave_dots(x, grace_baseline - 16, octave_shift))
        elif octave_shift < 0:
            # 低音点紧贴倚音下划线
            parts.extend(_render_octave_dots(x, underline_y2 + 6.0, -octave_shift))
        if align == "end":
            arc_start_x = x + 2.0
            arc_start_y = grace_baseline + 3.0
            arc_end_x = main_x - 10.0
            arc_end_y = baseline_y + 6.5
            control_x = (arc_start_x + arc_end_x) / 2.0 - 1.0
            control_y = baseline_y + 9.5
        else:
            arc_start_x = main_x + 10.0
            arc_start_y = baseline_y + 6.5
            arc_end_x = x - 2.0
            arc_end_y = grace_baseline + 3.0
            control_x = (arc_start_x + arc_end_x) / 2.0 + 1.0
            control_y = baseline_y + 9.5
        if abs(arc_end_x - arc_start_x) >= 6.0:
            parts.append(
                f'<path d="M {arc_start_x:.1f} {arc_start_y:.1f} Q {control_x:.1f} {control_y:.1f} {arc_end_x:.1f} {arc_end_y:.1f}" '
                f'fill="none" class="thin" />'
            )
    return parts


def _render_ornaments_svg(ornaments: list[dict[str, Any]], center_x: float, baseline_y: float) -> list[str]:
    parts: list[str] = []
    for index, ornament in enumerate(ornaments or []):
        label = _ornament_label(ornament)
        parts.append(
            f'<text x="{center_x:.1f}" y="{baseline_y - 34 - index * 12:.1f}" text-anchor="middle" class="meta">{escape(label)}</text>'
        )
    return parts


def _ornament_label(ornament: dict[str, Any]) -> str:
    kind = ornament.get("kind")
    args = ornament.get("args") or []
    if kind == "trill":
        return "tr"
    if kind == "mordent":
        return "mord"
    if kind == "slide":
        return f"slide {' '.join(args)}".strip()
    if kind == "fermata":
        return "fermata"
    if kind == "breath":
        return "breath"
    return kind if not args else f"{kind}({','.join(args)})"


def _apply_minimum_spacing(positioned_elements: list[dict[str, Any]]) -> None:
    if not positioned_elements:
        return

    for item in positioned_elements:
        left_bound = float(item["span_left"]) + 12.0
        right_bound = max(left_bound, float(item["span_right"]) - 12.0)
        item["min_center_x"] = left_bound
        item["max_center_x"] = right_bound
        item["center_x"] = min(max((left_bound + right_bound) / 2.0, left_bound), right_bound)
        half_width = _note_body_half_width(item["element"])
        item["half_width"] = half_width
        item["body_left_x"] = item["center_x"] - half_width
        item["body_right_x"] = item["center_x"] + half_width
        item["left_x"] = item["body_left_x"]
        item["right_x"] = item["body_right_x"]

    for _ in range(3):
        for index in range(1, len(positioned_elements)):
            prev = positioned_elements[index - 1]
            curr = positioned_elements[index]
            min_gap = _minimum_center_gap(prev, curr)
            curr["center_x"] = max(float(curr["center_x"]), float(prev["center_x"]) + min_gap)
            curr["center_x"] = min(float(curr["center_x"]), float(curr["max_center_x"]))

        for index in range(len(positioned_elements) - 2, -1, -1):
            curr = positioned_elements[index]
            nxt = positioned_elements[index + 1]
            min_gap = _minimum_center_gap(curr, nxt)
            curr["center_x"] = min(float(curr["center_x"]), float(nxt["center_x"]) - min_gap)
            curr["center_x"] = max(float(curr["center_x"]), float(curr["min_center_x"]))

    for item in positioned_elements:
        half_width = float(item["half_width"])
        item["body_left_x"] = float(item["center_x"]) - half_width
        item["body_right_x"] = float(item["center_x"]) + half_width
        item["left_x"] = item["body_left_x"]
        item["right_x"] = item["body_right_x"]


def _minimum_center_gap(left_item: dict[str, Any], right_item: dict[str, Any]) -> float:
    return float(left_item["half_width"]) + float(right_item["half_width"]) + 8.0


def _note_body_half_width(element: dict[str, Any]) -> float:
    if element.get("type") == "rest":
        token = "0"
    else:
        token = str(element.get("degree", ""))
        accidental = element.get("accidental")
        if accidental:
            token += {"sharp": "#", "flat": "b", "natural": "n"}.get(accidental, "")
        octave_shift = int(element.get("octaveShift", 0))
        if octave_shift > 0:
            token += "'" * octave_shift
        elif octave_shift < 0:
            token += "," * (-octave_shift)
    return 8.0 + max(0, len(token) - 1) * 3.2


def _allocate_row_measure_widths(
    row: list[dict[str, Any]],
    row_width: float,
    measure_gap: float,
) -> list[float]:
    if not row:
        return []

    available_width = row_width - measure_gap * max(0, len(row) - 1)
    min_measure_width = 120.0
    weights = [_measure_visual_weight(measure) for measure in row]

    if len(row) * min_measure_width >= available_width:
        return [available_width / len(row)] * len(row)

    remaining_width = available_width - len(row) * min_measure_width
    total_weight = sum(weights) or float(len(row))
    return [
        min_measure_width + remaining_width * (weight / total_weight)
        for weight in weights
    ]


def _measure_visual_weight(measure: dict[str, Any]) -> float:
    weight = 0.0
    for element in measure.get("elements", []):
        duration = element.get("duration", {})
        extensions = int(duration.get("extensions", 0))
        weight += 1.0 + extensions
        if element.get("accidental"):
            weight += 0.35
        octave_shift = abs(int(element.get("octaveShift", 0)))
        if octave_shift:
            weight += min(0.5, octave_shift * 0.2)
        dots = int(duration.get("dots", 0))
        if dots:
            weight += min(0.35, dots * 0.15)
    return max(1.0, weight)


def _annotation_starts(
    curves: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    tuplets: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    starts: dict[str, list[dict[str, Any]]] = {}
    for item in curves + groups + tuplets:
        starts.setdefault(item["startId"], []).append(item)
    return starts


def _annotation_ends(
    curves: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    tuplets: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    ends: dict[str, list[dict[str, Any]]] = {}
    for item in curves + groups + tuplets:
        ends.setdefault(item["endId"], []).append(item)
    return ends


def _house_starts(houses: list[dict[str, Any]]) -> dict[int, int]:
    return {int(house["startMeasure"]): int(house["number"]) for house in houses}


def _house_ends(houses: list[dict[str, Any]]) -> dict[int, int]:
    return {int(house["endMeasure"]): int(house["number"]) for house in houses}


def _validate_tie_pair(
    pending_tie_start: str,
    end_element: dict[str, Any],
    measures: list[dict[str, Any]],
    current_elements: list[dict[str, Any]],
) -> None:
    if end_element.get("type") != "note":
        raise MusTexParseError("Tie end must be a note.")
    all_elements: list[dict[str, Any]] = []
    for measure in measures:
        all_elements.extend(measure.get("elements", []))
    all_elements.extend(current_elements)
    start_element = next((element for element in all_elements if element.get("id") == pending_tie_start), None)
    if start_element is None:
        raise MusTexParseError("Tie start note could not be resolved.")
    if start_element.get("type") != "note":
        raise MusTexParseError("Tie start must be a note.")
    start_signature = (
        start_element.get("degree"),
        start_element.get("octaveShift"),
        start_element.get("accidental"),
    )
    end_signature = (
        end_element.get("degree"),
        end_element.get("octaveShift"),
        end_element.get("accidental"),
    )
    if start_signature != end_signature:
        raise MusTexParseError("Tie '~' must connect two identical notes.")


def _render_extensions_svg(
    positioned_elements: list[dict[str, Any]],
    content_left: float,
    content_width: float,
    meter_beats: int,
) -> list[str]:
    parts: list[str] = []
    for item in positioned_elements:
        element = item["element"]
        if element.get("type") != "note":
            continue
        extensions = int(element.get("duration", {}).get("extensions", 0))
        if extensions <= 0:
            continue
        y = item["baseline_y"] + 1
        dash_text_length = min(10.0, max(6.0, float(item.get("slot_width", 18.0)) * 0.34))
        for x in item.get("extension_slot_centers", []):
            parts.append(
                f'<text x="{float(x):.1f}" y="{y:.1f}" text-anchor="middle" dominant-baseline="middle" '
                f'textLength="{dash_text_length:.1f}" lengthAdjust="spacingAndGlyphs" class="dash">—</text>'
            )
    return parts
