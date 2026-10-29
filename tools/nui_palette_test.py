"""Tests for tools/nui_palette.py, the reference of the client's player color
resolve (Core/Palette.cpp; P13 spec 5.3 and 5.7): the palette vectors
(tools/fixtures/palette_cases.json) and the rules one by one, on the shipped
data too. python3 -B -m unittest nui_palette_test (from tools/)."""
import json
import os
import unittest

import nui_palette as p

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, "fixtures", "palette_cases.json")


def tiny(slots, tokens=None, tone=None, pairs=None):
    """A one-palette colors.json for theme "t"."""
    palette = {"tokens": tokens or {"surface": "#202020", "text": "#e0e0e0", "accent": "#4080ff", "accent-text": "#000000"},
               "slots": slots}
    if tone:
        palette["tone"] = tone
    return p.parse_colors({"version": 1, "pairs": pairs or [["text", "surface", 4.5]], "palettes": {"t": palette},
                           "themes": {"t": "t"}})


class Vectors(unittest.TestCase):
    def test_every_vector_resolves_to_its_outputs(self):
        with open(CASES, encoding="utf-8") as handle:
            document = json.load(handle)
        self.assertEqual(len(document["cases"]), 16)
        self.assertEqual(p.check_cases(CASES), [])


class Colors(unittest.TestCase):
    def test_mix_rounds_half_up_per_channel_alpha_included(self):
        self.assertEqual(p.mix((0, 0, 0, 0), (255, 255, 255, 255), 0.5), (128, 128, 128, 128))
        self.assertEqual(p.mix((10, 20, 30, 255), (10, 20, 30, 255), 0.37), (10, 20, 30, 255))

    def test_a_translucent_background_counts_its_lower_ratio_over_black_and_white(self):
        white = (255, 255, 255, 255)
        half_gray = (128, 128, 128, 128)
        over_black = p.contrast_ratio(white, (64, 64, 64, 255))
        self.assertLess(p.contrast_ratio(white, half_gray), over_black)
        self.assertAlmostEqual(p.contrast_ratio((0, 0, 0, 255), (255, 255, 255, 255)), 21.0, places=6)

    def test_colors_parse_and_format_as_the_client_writes_them(self):
        self.assertEqual(p.parse_color("#FfA0b1"), (255, 160, 177, 255))
        self.assertEqual(p.parse_color("#ffa0b180"), (255, 160, 177, 128))
        for bad in ("ffa0b1", "#ffa0b", "#ffa0bz", "#ffa0b1800"):
            self.assertIsNone(p.parse_color(bad), bad)
        self.assertEqual(p.format_color((255, 160, 177, 128)), "#ffa0b180")


class Rules(unittest.TestCase):
    def test_each_rule_writes_its_token(self):
        data = tiny([{"slot": "accent", "kind": "color", "sets": [
            {"token": "accent", "rule": "value"},
            {"token": "text", "rule": "mix", "with": "#000000", "t": 0.5},
            {"token": "accent-text", "rule": "pick", "from": ["accent-text", "text"], "on": "accent"},
            {"token": "surface", "rule": "delta", "ref": "accent"}]}], pairs=[["text", "surface", 1.0]])
        result = p.resolve(data, "t", {"accent": "#ff0000"})
        self.assertEqual(result["tokens"]["accent"], "#ff0000ff")
        self.assertEqual(result["tokens"]["text"], "#800000ff", "mixed with black by half")
        self.assertEqual(result["tokens"]["surface"], "#df0000ff", "#ff0000 + (#202020 - #4080ff), clamped")
        self.assertEqual(result["tokens"]["accent-text"], "#000000ff", "black reads better than #800000 on red")

    def test_a_percent_slot_sets_alpha_and_below_its_max_the_backdrop(self):
        data = tiny([{"slot": "opacity", "kind": "percent", "min": 50, "max": 100, "step": 5, "backdrop": "blur(6dp)",
                      "sets": [{"token": "surface", "rule": "alpha"}]}], pairs=[["text", "surface", 1.0]])
        result = p.resolve(data, "t", {"opacity": "80"})
        self.assertEqual(result["tokens"], {"panel-backdrop": "blur(6dp)", "surface": "#202020cc"})
        self.assertEqual(result["opacity"], 80)
        self.assertEqual(p.resolve(data, "t", {"opacity": "100"})["tokens"], {}, "the default is no override")
        self.assertEqual(p.resolve(data, "t", {"opacity": "82"})["tokens"], {}, "off its step: unset")

    def test_the_contrast_pass_moves_text_toward_the_pole_of_the_palettes_tone(self):
        data = tiny([{"slot": "panel", "kind": "color", "sets": [{"token": "surface", "rule": "value"}]}])
        result = p.resolve(data, "t", {"panel": "#707070"})
        self.assertIn("text", result["adjusted"])
        self.assertEqual(result["failed"], [], "a dark tone's text reaches white")
        light = tiny([{"slot": "panel", "kind": "color", "sets": [{"token": "surface", "rule": "value"}]}],
                     tokens={"surface": "#f0f0f0", "text": "#202020", "accent": "#4080ff", "accent-text": "#ffffff"}, tone="light")
        result = p.resolve(light, "t", {"panel": "#606060"})
        self.assertEqual(result["failed"], [["text", "surface"]], "toward black only: a mid-gray panel fails")
        self.assertEqual(result["tokens"]["text"], "#ffffffff", "then the better of white and black")

    def test_a_failed_pair_raises_the_opacity_until_it_holds(self):
        data = tiny([{"slot": "opacity", "kind": "percent", "min": 50, "max": 100, "step": 5,
                      "sets": [{"token": "surface", "rule": "alpha"}]}],
                    tokens={"surface": "#606060", "text": "#ffffff", "accent": "#4080ff", "accent-text": "#000000"},
                    pairs=[["text", "surface", 3.0]])
        result = p.resolve(data, "t", {"opacity": "50"})
        self.assertEqual(result["failed"], [])
        self.assertGreater(result["opacity"], 50)
        self.assertEqual(result["adjusted"]["opacity"], str(result["opacity"]))

    def test_a_slot_takes_its_default_from_its_first_value_rule_or_its_max(self):
        data = tiny([{"slot": "accent", "kind": "color", "sets": [{"token": "accent", "rule": "value"}]},
                     {"slot": "opacity", "kind": "percent", "min": 50, "max": 90, "step": 10, "sets": [{"token": "surface", "rule": "alpha"}]}])
        slots = p.slots_of_theme(data, "t")
        self.assertEqual([(s["slot"], s["default"]) for s in slots], [("accent", "#4080ff"), ("opacity", "90")])

    def test_an_explicit_percent_default_can_preserve_the_legacy_value(self):
        data = tiny([{"slot": "overlay", "kind": "percent", "min": 30, "max": 100, "step": 1, "default": 51,
                      "sets": [{"token": "surface", "rule": "alpha"}]}])
        slot = p.slots_of_theme(data, "t")[0]
        self.assertEqual(slot["default"], "51")
        self.assertEqual(p.resolve(data, "t", {"overlay": "51"})["tokens"], {})
        self.assertEqual(p.resolve(data, "t", {"overlay": "50"})["tokens"]["surface"], "#20202080")

    def test_a_file_that_breaks_a_rule_is_refused(self):
        for slots in ([{"slot": "x", "kind": "color", "sets": [{"token": "nope", "rule": "value"}]}],
                      [{"slot": "x", "kind": "color", "sets": [{"token": "accent", "rule": "alpha"}]}],
                      [{"slot": "x", "kind": "color", "sets": [{"token": "accent", "rule": "mix", "with": "nope", "t": 0.5}]}],
                      [{"slot": "x", "kind": "hue", "sets": [{"token": "accent", "rule": "value"}]}]):
            with self.subTest(slots=slots):
                self.assertRaises(p.PaletteError, tiny, slots)


class Overrides(unittest.TestCase):
    def test_ui_colors_round_trips_in_theme_then_curated_slot_order(self):
        text = "modern-dark:accent=#C58AF9,opacity=080;newer-theme:zzz=1,accent=#000000"
        parsed, order = p.parse_overrides(text)
        self.assertEqual(order, ["modern-dark", "newer-theme"])
        self.assertEqual(parsed["modern-dark"], {"accent": "#c58af9", "opacity": "80"})
        self.assertEqual(p.format_overrides(parsed, ["classic", "modern-dark"]),
                         "modern-dark:accent=#c58af9,opacity=80;newer-theme:accent=#000000,zzz=1")

    def test_ui_colors_refuses_a_line_out_of_form(self):
        for text in ("x" * 961, "modern-dark", "modern-dark:", "Modern:accent=#ffffff", "modern-dark:accent=red",
                     "modern-dark:accent=#fff", "modern-dark:accent=#ffffff,accent=#000000", "a:b=1;a:b=2"):
            with self.subTest(text=text[:40]):
                self.assertRaises(p.PaletteError, p.parse_overrides, text)
        self.assertEqual(p.parse_overrides(""), ({}, []))


class ShippedData(unittest.TestCase):
    def test_the_modern_themes_offer_five_slots_and_classic_none(self):
        data = p.load()
        for theme in ("modern-dark", "modern-light"):
            self.assertEqual([s["slot"] for s in p.slots_of_theme(data, theme)],
                             ["accent", "panel", "opacity", "overlay", "highlight"], theme)
        self.assertEqual(p.slots_of_theme(data, "classic"), [])

    def test_every_swatch_keeps_every_pair_alone_and_at_the_lowest_opacity(self):
        import nui_tokens
        with open(p.COLORS_JSON, encoding="utf-8") as handle:
            self.assertEqual(nui_tokens.swatch_failures([handle.read()]), [])


if __name__ == "__main__":
    unittest.main()
