from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from SimpMusTex import MusTexParseError, parse_mustex_text, render_score_svg, render_score_text


class TestMusTexParse(unittest.TestCase):
    def test_parse_headers_and_measures(self):
        score = parse_mustex_text(
            "\n".join(
                [
                    "title: Demo",
                    "key: 1=F",
                    "meter: 4/4",
                    "tempo: 88",
                    "",
                    "6, 1 2 3 | 6 6_ 1 2 | 3--- ||",
                ]
            )
        )

        self.assertEqual(score["schema"], "mustex-score/v0.1")
        self.assertEqual(score["global"]["key"]["tonicPitch"], "F")
        self.assertEqual(score["global"]["meter"]["beats"], 4)
        self.assertEqual(score["global"]["tempo"]["bpm"], 88)

        measures = score["sections"][0]["measures"]
        self.assertEqual(len(measures), 3)
        self.assertEqual(measures[0]["elements"][0]["degree"], 6)
        self.assertEqual(measures[0]["elements"][0]["octaveShift"], -1)
        self.assertEqual(measures[1]["elements"][1]["duration"]["underlines"], 1)
        self.assertEqual(measures[2]["elements"][0]["duration"]["extensions"], 3)

    def test_parse_rest_and_accidental(self):
        score = parse_mustex_text("1 0_ 4#'_. |")
        measures = score["sections"][0]["measures"]
        rest = measures[0]["elements"][1]
        note = measures[0]["elements"][2]
        self.assertEqual(rest["type"], "rest")
        self.assertEqual(rest["duration"]["beats"], 0.5)
        self.assertEqual(note["accidental"], "sharp")
        self.assertEqual(note["octaveShift"], 1)
        self.assertEqual(note["duration"]["beats"], 0.75)

    def test_render_roundtrip(self):
        text = "key: 1=F\n\n|: 6, 1 2 3 | 3--- :|"
        rendered = render_score_text(parse_mustex_text(text))
        self.assertIn("key: 1=F", rendered)
        self.assertIn("|: 6, 1 2 3 | 3--- :|", rendered)

    def test_reject_mixed_octave_markers(self):
        with self.assertRaises(MusTexParseError):
            parse_mustex_text("1',")

    def test_parse_tie_and_slur(self):
        score = parse_mustex_text("key: 1=F\n\n6~6 <s 3 2 1 > |")
        section = score["sections"][0]
        curves = section["curves"]
        self.assertEqual(len(curves), 2)
        self.assertEqual(curves[0]["kind"], "tie")
        self.assertEqual(curves[1]["kind"], "slur")
        measures = section["measures"]
        self.assertEqual(len(measures[0]["elements"]), 5)

    def test_parse_cross_measure_tie_and_slur(self):
        tie_score = parse_mustex_text("key: 1=F\n\n6~ | 6 |")
        tie_curves = tie_score["sections"][0]["curves"]
        self.assertEqual(len(tie_curves), 1)
        self.assertEqual(tie_curves[0]["kind"], "tie")

        slur_score = parse_mustex_text("key: 1=F\n\n<s 3 2 | 1 > |")
        slur_curves = slur_score["sections"][0]["curves"]
        self.assertEqual(len(slur_curves), 1)
        self.assertEqual(slur_curves[0]["kind"], "slur")

    def test_render_svg(self):
        score = parse_mustex_text("title: Demo\nkey: 1=F\nmeter: 4/4\ntempo: 88\n\n6,_ 5,_ | 3--- ||")
        svg = render_score_svg(score)
        self.assertIn("<svg", svg)
        self.assertIn("Demo", svg)
        self.assertIn(">6<", svg)
        self.assertIn(">3<", svg)
        self.assertIn("♩ = 88", svg)
        self.assertEqual(svg.count('class="dash"'), 3)

    def test_render_curve_svg(self):
        score = parse_mustex_text("key: 1=F\n\n6~6 <s 3 2 1 > |")
        svg = render_score_svg(score)
        self.assertIn('<path d="M', svg)
        self.assertEqual(svg.count('<path d="M'), 2)
        # Tie and slur now use the same arc height
        self.assertIn(" 108.0", svg)

    def test_render_cross_measure_curve_svg(self):
        tie_svg = render_score_svg(parse_mustex_text("key: 1=F\n\n6~ | 6 |"))
        slur_svg = render_score_svg(parse_mustex_text("key: 1=F\n\n<s 3 2 | 1 > |"))
        self.assertEqual(tie_svg.count('<path d="M'), 1)
        self.assertEqual(slur_svg.count('<path d="M'), 1)

    def test_render_five_measures_per_row(self):
        score = parse_mustex_text("key: 1=F\n\n1 | 2 | 3 | 4 | 5 | 6 |")
        svg = render_score_svg(score)
        self.assertEqual(svg.count('y="138.0"'), 5)
        self.assertEqual(svg.count('y="248.0"'), 1)

    def test_dense_measure_minimum_spacing(self):
        score = parse_mustex_text("key: 1=F\n\n6,_ 5,_ 6,_ 1_ 2_ 3_ 5_ 3__ 2__ |")
        svg = render_score_svg(score)
        xs = [
            float(match.group(1))
            for match in re.finditer(r'<text x="([0-9.]+)" y="138.0" text-anchor="middle" dominant-baseline="middle" class="digit">', svg)
        ]
        self.assertGreaterEqual(min(b - a for a, b in zip(xs, xs[1:])), 10.0)

    def test_underlines_break_by_beat(self):
        score = parse_mustex_text("key: 1=F\n\n1_ 2_. 3__ |")
        svg = render_score_svg(score)
        first_level_lines = re.findall(r'<line x1="([0-9.]+)" y1="158.0" x2="([0-9.]+)" y2="158.0" class="thin" />', svg)
        self.assertEqual(len(first_level_lines), 2)

    def test_same_beat_underline_uses_uniform_endcaps(self):
        score = parse_mustex_text("key: 1=F\n\n1_ 2_ |")
        svg = render_score_svg(score)
        self.assertEqual(svg.count('y1="158.0"'), 1)

    def test_single_underline_tracks_digit_width(self):
        score = parse_mustex_text("key: 1=F\n\n1_ |")
        svg = render_score_svg(score)
        match = re.search(r'<line x1="([0-9.]+)" y1="158.0" x2="([0-9.]+)" y2="158.0" class="thin" />', svg)
        self.assertIsNotNone(match)
        x1 = float(match.group(1))
        x2 = float(match.group(2))
        self.assertAlmostEqual(x2 - x1, 14.0, places=1)

    def test_extensions_consume_layout_slots(self):
        score = parse_mustex_text("key: 1=F\n\n3--- 2 |")
        svg = render_score_svg(score)
        xs = [
            float(match.group(1))
            for match in re.finditer(r'<text x="([0-9.]+)" y="138.0" text-anchor="middle" dominant-baseline="middle" class="digit">', svg)
        ]
        self.assertGreater(xs[1] - xs[0], 150.0)

    def test_parse_phrase_mute_tuplet_and_houses(self):
        score = parse_mustex_text(
            "key: 1=F\n\n<p 6 5 3 2 | 1 > ( 6, 5, 6 1 2 ) [1 6--- :|] [2 6-- 1 2 |] <tuplet 3:2 1_ 2_ 3_>"
        )
        section = score["sections"][0]
        self.assertTrue(any(curve["kind"] == "phrase" for curve in section["curves"]))
        self.assertEqual(section["groups"][0]["kind"], "mute")
        self.assertEqual(section["tuplets"][0]["ratio"], "3:2")
        self.assertEqual(section["houses"][0]["number"], 1)
        self.assertEqual(section["houses"][1]["number"], 2)

    def test_parse_grace_and_ornaments(self):
        score = parse_mustex_text(
            "key: 1=F\n\n{5'}6 {/5'}6 6{>5'} 3@trill 3@mordent 3@slide(up) 3@fermata 3@breath |"
        )
        elements = score["sections"][0]["measures"][0]["elements"]
        self.assertEqual(elements[0]["graceBefore"][0]["degree"], 5)
        self.assertTrue(elements[1]["graceBefore"][0]["slash"])
        self.assertTrue(elements[2]["graceAfter"][0]["accent"])
        self.assertEqual(elements[3]["ornaments"][0]["kind"], "trill")
        self.assertEqual(elements[5]["ornaments"][0]["args"], ["up"])

    def test_grace_duration_is_rejected(self):
        with self.assertRaises(MusTexParseError):
            parse_mustex_text("key: 1=F\n\n{6,__}1-- |")

    def test_render_roundtrip_new_syntax(self):
        text = (
            "key: 1=F\n\n"
            "<p 6 5 3 2 | 1 > "
            "( 6, 5, 6 1 2 ) "
            "{5'}6 {/5'}6 6{>5'} "
            "3@trill 3@mordent 3@slide(up) 3@fermata 3@breath | "
            "[1 6--- :|] [2 6-- 1 2 |] "
            "<tuplet 3:2 1_ 2_ 3_>"
        )
        rendered = render_score_text(parse_mustex_text(text))
        self.assertIn("<p 6 5 3 2 | 1 >", rendered)
        self.assertIn("( 6, 5, 6 1 2 )", rendered)
        self.assertIn("{5'}6", rendered)
        self.assertIn("{/5'}6", rendered)
        self.assertIn("6{>5'}", rendered)
        self.assertIn("3@slide(up)", rendered)
        self.assertIn("[1 6--- :|]", rendered)
        self.assertIn("<tuplet 3:2 1_ 2_ 3_ >", rendered)

    def test_render_svg_new_annotations(self):
        score = parse_mustex_text(
            "key: 1=F\n\n<p 6 5 3 2 | 1 > ( 6, 5, 6 1 2 ) {5'}6 3@trill [1 6--- :|] <tuplet 3:2 1_ 2_ 3_>"
        )
        svg = render_score_svg(score)
        self.assertIn(">tr<", svg)
        self.assertIn(">1<", svg)
        self.assertIn("class=\"dash\"", svg)
        self.assertGreaterEqual(svg.count("<path d=\"M"), 1)
        self.assertGreaterEqual(svg.count('y1="127.5"'), 1)
        self.assertGreaterEqual(svg.count('y1="131.0"'), 1)

    def test_low_octave_dot_avoids_normal_underlines(self):
        svg = render_score_svg(parse_mustex_text("key: 1=F\n\n6,__ |"))
        self.assertIn('cy="171.0"', svg)

    def test_low_octave_dot_avoids_grace_underlines(self):
        svg = render_score_svg(parse_mustex_text("key: 1=F\n\n{6,}1 |"))
        self.assertIn('cy="135.5"', svg)

    def test_extension_dashes_keep_separation(self):
        svg = render_score_svg(parse_mustex_text("key: 1=F\n\n2-- 3_ 2_ |"))
        xs = [
            float(match.group(1))
            for match in re.finditer(r'<line x1="([0-9.]+)" y1="139.0" x2="([0-9.]+)" y2="139.0" class="dash" />', svg)
        ]
        dash_segments = [
            (float(m.group(1)), float(m.group(2)))
            for m in re.finditer(r'<line x1="([0-9.]+)" y1="139.0" x2="([0-9.]+)" y2="139.0" class="dash" />', svg)
        ]
        centers = [(x1 + x2) / 2.0 for x1, x2 in dash_segments]
        if len(centers) >= 2:
            self.assertGreaterEqual(min(b - a for a, b in zip(centers, centers[1:])), 8.0)
        self.assertTrue(dash_segments)
        self.assertGreaterEqual(min(x2 - x1 for x1, x2 in dash_segments), 10.0)
        if len(dash_segments) >= 2:
            self.assertGreaterEqual(
                min(next_x1 - prev_x2 for (_, prev_x2), (next_x1, _) in zip(dash_segments, dash_segments[1:])),
                5.0,
            )

    def test_notehead_is_not_centered_into_extension_area(self):
        svg = render_score_svg(parse_mustex_text("key: 1=F\n\n3--- |"))
        note_match = re.search(r'<text x="([0-9.]+)" y="138.0" text-anchor="middle" dominant-baseline="middle" class="digit">3</text>', svg)
        dash_xs = [
            (float(match.group(1)) + float(match.group(2))) / 2.0
            for match in re.finditer(r'<line x1="([0-9.]+)" y1="139.0" x2="([0-9.]+)" y2="139.0" class="dash" />', svg)
        ]
        self.assertIsNotNone(note_match)
        self.assertGreater(len(dash_xs), 0)
        self.assertLess(float(note_match.group(1)), dash_xs[0] - 8.0)

    def test_wide_digits_keep_clear_gap_before_extension(self):
        for digit in ("3", "6"):
            svg = render_score_svg(parse_mustex_text(f"key: 1=F\n\n{digit}-- |"))
            note_match = re.search(
                rf'<text x="([0-9.]+)" y="138.0" text-anchor="middle" dominant-baseline="middle" class="digit">{digit}</text>',
                svg,
            )
            dash_match = re.search(
                r'<line x1="([0-9.]+)" y1="139.0" x2="([0-9.]+)" y2="139.0" class="dash" />',
                svg,
            )
            self.assertIsNotNone(note_match)
            self.assertIsNotNone(dash_match)
            self.assertGreater(float(dash_match.group(1)) - float(note_match.group(1)), 16.0)

    def test_mute_closing_paren_clears_extension_boxes(self):
        svg = render_score_svg(parse_mustex_text("key: 1=F\n\n( 6-- ) |"))
        dash_match = re.search(
            r'<line x1="([0-9.]+)" y1="139.0" x2="([0-9.]+)" y2="139.0" class="dash" />',
            svg,
        )
        paren_match = re.search(
            r'<text x="([0-9.]+)" y="138.0" text-anchor="middle" dominant-baseline="middle" class="mark">\)</text>',
            svg,
        )
        self.assertIsNotNone(dash_match)
        self.assertIsNotNone(paren_match)
        self.assertGreater(float(paren_match.group(1)) - float(dash_match.group(2)), 6.0)

    def test_house_snaps_to_previous_barline(self):
        svg = render_score_svg(parse_mustex_text("key: 1=F\n\n1 | [1 2 | 3 |]"))
        barlines = [
            float(match.group(1))
            for match in re.finditer(r'<line x1="([0-9.]+)" y1="110.0" x2="\1" y2="180.0" class="thin" />', svg)
        ]
        house_line = re.search(
            r'<line x1="([0-9.]+)" y1="102.0" x2="([0-9.]+)" y2="102.0" class="thin" />',
            svg,
        )
        self.assertIsNotNone(house_line)
        self.assertIn(float(house_line.group(1)), barlines)

    def test_house_draws_closing_vertical(self):
        svg = render_score_svg(parse_mustex_text("key: 1=F\n\n[1 2 | 3 |]"))
        house_line = re.search(
            r'<line x1="([0-9.]+)" y1="102.0" x2="([0-9.]+)" y2="102.0" class="thin" />',
            svg,
        )
        closings = re.findall(
            r'<line x1="([0-9.]+)" y1="102.0" x2="\1" y2="114.0" class="thin" />',
            svg,
        )
        self.assertIsNotNone(house_line)
        self.assertTrue(closings)
        self.assertAlmostEqual(float(house_line.group(2)), float(closings[-1]), places=1)

    def test_sparse_measure_uses_edges_better(self):
        svg = render_score_svg(parse_mustex_text("key: 1=F\n\n1 2 3 |"))
        xs = [
            float(match.group(1))
            for match in re.finditer(r'<text x="([0-9.]+)" y="138.0" text-anchor="middle" dominant-baseline="middle" class="digit">[123]</text>', svg)
        ]
        self.assertEqual(len(xs), 3)
        self.assertLess(xs[0], 110.0)
        self.assertGreater(xs[-1], 940.0)


    def test_parse_lyrics_inline(self):
        score = parse_mustex_text('key: 1=F\n\n1"你" 2"好" 3 4"界" |')
        elements = score["sections"][0]["measures"][0]["elements"]
        self.assertEqual(elements[0]["lyrics"], "你")
        self.assertEqual(elements[1]["lyrics"], "好")
        self.assertNotIn("lyrics", elements[2])  # no lyrics on this note
        self.assertEqual(elements[3]["lyrics"], "界")

    def test_parse_lyrics_attached(self):
        """Lyrics can be written directly attached: 1\"我\" or with space: 1 \"我\"."""
        score = parse_mustex_text('key: 1=F\n\n1"我" |')
        elements = score["sections"][0]["measures"][0]["elements"]
        self.assertEqual(elements[0]["lyrics"], "我")

    def test_render_roundtrip_lyrics(self):
        text = 'key: 1=F\n\n1"春" 2"天" |'
        rendered = render_score_text(parse_mustex_text(text))
        self.assertIn('1"春"', rendered)
        self.assertIn('2"天"', rendered)

    def test_render_svg_lyrics(self):
        score = parse_mustex_text('key: 1=F\n\n1"风" 2"花" |')
        svg = render_score_svg(score)
        self.assertIn('class="lyrics"', svg)
        self.assertIn(">风<", svg)
        self.assertIn(">花<", svg)

    def test_lyrics_without_preceding_note_rejected(self):
        with self.assertRaises(MusTexParseError):
            parse_mustex_text('key: 1=F\n\n"落" 1 2 |')

    def test_parse_tie_span(self):
        score = parse_mustex_text("key: 1=F\n\n<t 6 | 6 > |")
        curves = score["sections"][0]["curves"]
        self.assertEqual(len(curves), 1)
        self.assertEqual(curves[0]["kind"], "tie")

    def test_tie_span_cross_measure(self):
        score = parse_mustex_text("key: 1=F\n\n<t 6--- | 6 > |")
        curves = score["sections"][0]["curves"]
        self.assertEqual(len(curves), 1)
        self.assertEqual(curves[0]["kind"], "tie")

    def test_tie_span_rejects_different_pitch(self):
        with self.assertRaises(MusTexParseError):
            parse_mustex_text("key: 1=F\n\n<t 6 | 5 > |")

    def test_render_roundtrip_tie_span(self):
        text = "key: 1=F\n\n<t 6 | 6 > |"
        rendered = render_score_text(parse_mustex_text(text))
        self.assertIn("<t 6", rendered)
        self.assertIn(">", rendered)


if __name__ == "__main__":
    unittest.main()
