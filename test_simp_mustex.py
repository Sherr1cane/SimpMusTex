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
        self.assertEqual(svg.count(">—<"), 3)

    def test_render_curve_svg(self):
        score = parse_mustex_text("key: 1=F\n\n6~6 <s 3 2 1 > |")
        svg = render_score_svg(score)
        self.assertIn('<path d="M', svg)
        self.assertEqual(svg.count('<path d="M'), 2)
        self.assertIn(" 122.0", svg)
        self.assertIn(" 104.0", svg)

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
        self.assertIn('cy="137.0"', svg)


if __name__ == "__main__":
    unittest.main()
