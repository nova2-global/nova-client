"""Unit tests for nui_tokens.py: python -B -m unittest nui_tokens_test (from tools/; -B keeps
__pycache__ out of the repository)"""
import copy
import json
import unittest

import nui_tokens as t


def minimal_themes():
    """themes.json as parsed: the default theme first, two skins, three palettes."""
    return [
        ("modern-dark", "Modern dark", ["skin-modern", "theme-dark"]),
        ("modern-light", "Modern light", ["skin-modern", "theme-light"]),
        ("classic", "Classic", ["skin-classic", "theme-classic"]),
    ]


def minimal_themes_json():
    return {"themes": [{"id": i, "label": l, "body": list(b)} for i, l, b in minimal_themes()]}


def minimal_tokens():
    shared = {name: "4dp" for name in t.REQUIRED_SHARED}
    shared.update({"font-family": "Noto Sans", "dur-fast": "0.1s", "dur-med": "0.2s", "dur-slow": "0.3s",
                   "ease-out": "cubic-out", "ease-in-out": "cubic-in-out"})
    # Every required color, and every color a contrast pair names.
    colors = list(t.REQUIRED_COLORS)
    colors += [name for fg, bg, _, _ in t.CONTRAST_PAIRS for name in (fg, bg) if name not in t.REQUIRED_COLORS]
    colors = list(dict.fromkeys(colors))
    dark = {name: "#000000" for name in colors}
    light = {name: "#ffffff" for name in colors}
    classic = {name: "#202020" for name in colors}
    skins = {"classic": {"font-family": "Nova Classic", "font-md": "12dp", "classic-slot-fill": "#000000",
                         "classic-gap": "3dp"}}
    return {"shared": shared, "dark": dark, "light": light, "classic": classic, "skins": skins}


class ContrastMath(unittest.TestCase):
    def test_black_on_white_is_the_wcag_maximum(self):
        ratio = t.contrast_ratio(t.parse_color("#000000"), t.parse_color("#ffffff"))
        self.assertAlmostEqual(ratio, 21.0, places=6)

    def test_the_ratio_is_symmetric_and_one_for_equal_colors(self):
        a, b = t.parse_color("#1a5fc4"), t.parse_color("#f3f4f6")
        self.assertAlmostEqual(t.contrast_ratio(a, b), t.contrast_ratio(b, a), places=9)
        self.assertAlmostEqual(t.contrast_ratio(a, a), 1.0, places=9)

    def test_a_known_pair_matches_the_published_value(self):
        # #767676 on white is the lightest gray that passes AA (4.54:1).
        ratio = t.contrast_ratio(t.parse_color("#767676"), t.parse_color("#ffffff"))
        self.assertAlmostEqual(ratio, 4.54, places=2)

    def test_translucent_text_is_composited_over_its_background(self):
        half_black = t.parse_color("#00000080")
        white = t.parse_color("#ffffff")
        mid_gray = t.parse_color("#7f7f7f")
        self.assertAlmostEqual(t.contrast_ratio(half_black, white), t.contrast_ratio(mid_gray, white), places=2)

    def test_a_translucent_background_is_refused(self):
        with self.assertRaises(t.TokenError):
            t.contrast_ratio(t.parse_color("#000000"), t.parse_color("#ffffff80"))


class Validation(unittest.TestCase):
    def assertRejected(self, tokens, fragment, themes=None):
        with self.assertRaises(t.TokenError) as caught:
            t.validate(tokens, themes or minimal_themes())
        self.assertIn(fragment, str(caught.exception))

    def test_a_complete_token_set_passes(self):
        t.validate(minimal_tokens(), minimal_themes())

    def test_skins_are_optional(self):
        tokens = minimal_tokens()
        del tokens["skins"]
        t.validate(tokens, minimal_themes())

    def test_px_lengths_are_refused(self):
        tokens = minimal_tokens()
        tokens["shared"]["space-1"] = "4px"
        self.assertRejected(tokens, "lengths are in dp")

    def test_millisecond_durations_are_refused_because_rmlui_reads_seconds(self):
        tokens = minimal_tokens()
        tokens["shared"]["dur-fast"] = "120ms"
        self.assertRejected(tokens, "seconds")

    def test_css_easing_names_are_refused(self):
        tokens = minimal_tokens()
        tokens["shared"]["ease-out"] = "ease-out"
        self.assertRejected(tokens, "RmlUi tween")

    def test_font_family_lists_are_refused(self):
        tokens = minimal_tokens()
        tokens["shared"]["font-family"] = "Noto Sans, sans-serif"
        self.assertRejected(tokens, "one family")

    def test_a_missing_color_is_named(self):
        tokens = minimal_tokens()
        del tokens["light"]["focus-ring"]
        self.assertRejected(tokens, "focus-ring")

    def test_every_palette_must_define_the_same_colors(self):
        tokens = minimal_tokens()
        tokens["classic"]["only-classic"] = "#123456"
        self.assertRejected(tokens, "only-classic")

    def test_colors_must_be_six_or_eight_digit_hex(self):
        tokens = minimal_tokens()
        tokens["dark"]["text"] = "rgb(1, 2, 3)"
        self.assertRejected(tokens, "#rrggbb")

    def test_colors_do_not_belong_in_shared(self):
        tokens = minimal_tokens()
        tokens["shared"]["brand"] = "#ff0000"
        self.assertRejected(tokens, "palettes")

    def test_a_palette_may_not_shadow_a_shared_token(self):
        tokens = minimal_tokens()
        for palette in ("dark", "light", "classic"):
            tokens[palette]["space-1"] = "#000000"
        self.assertRejected(tokens, "also a shared token")

    def test_token_names_are_lowercase_words(self):
        tokens = minimal_tokens()
        tokens["dark"]["Surface"] = "#000000"
        self.assertRejected(tokens, "lowercase")

    def test_a_palette_no_theme_uses_is_refused(self):
        tokens = minimal_tokens()
        tokens["sepia"] = dict(tokens["dark"])
        self.assertRejected(tokens, "no theme in themes.json uses palette sepia")

    def test_a_palette_class_without_a_palette_is_refused(self):
        tokens = minimal_tokens()
        del tokens["classic"]
        self.assertRejected(tokens, "no palette 'classic'")

    def test_a_skin_no_theme_uses_is_refused(self):
        tokens = minimal_tokens()
        tokens["skins"]["retro"] = {"font-md": "12dp"}
        self.assertRejected(tokens, "skin-retro")

    def test_a_skin_override_of_a_shared_token_follows_the_shared_rules(self):
        tokens = minimal_tokens()
        tokens["skins"]["classic"]["font-md"] = "12px"
        self.assertRejected(tokens, "skins.classic.font-md: lengths are in dp")

    def test_a_skin_token_of_its_own_carries_the_skin_name(self):
        tokens = minimal_tokens()
        tokens["skins"]["classic"]["slot-fill"] = "#000000"
        self.assertRejected(tokens, "named classic-...")

    def test_a_skin_token_of_its_own_is_a_color_or_a_dp_length(self):
        tokens = minimal_tokens()
        tokens["skins"]["classic"]["classic-ease"] = "cubic-out"
        self.assertRejected(tokens, "color or a dp length")

    def test_a_skin_token_may_not_reuse_a_palette_token_name(self):
        tokens = minimal_tokens()
        for palette in ("dark", "light", "classic"):
            tokens[palette]["classic-glow"] = "#123456"
        tokens["skins"]["classic"]["classic-glow"] = "#654321"
        self.assertRejected(tokens, "reuses a palette token name")


class ThemesJson(unittest.TestCase):
    def assertRejected(self, document, fragment):
        with self.assertRaises(t.TokenError) as caught:
            t.validate_themes(document)
        self.assertIn(fragment, str(caught.exception))

    def test_the_minimal_table_parses_in_menu_order(self):
        self.assertEqual(t.validate_themes(minimal_themes_json()), minimal_themes())

    def test_the_first_theme_must_be_the_default_id(self):
        document = minimal_themes_json()
        document["themes"].reverse()
        self.assertRejected(document, "must be 'modern-dark'")

    def test_each_theme_needs_one_skin_and_one_palette_class(self):
        for body in (["theme-dark"], ["skin-modern"], ["skin-modern", "skin-classic", "theme-dark"],
                     ["skin-modern", "theme-dark", "theme-light"]):
            document = minimal_themes_json()
            document["themes"][1]["body"] = body
            self.assertRejected(document, "exactly one skin-* and one theme-*")

    def test_ids_classes_and_labels_follow_the_runtime_rules(self):
        cases = [
            (("id", "Modern-Light"), "id is 1 to 31"),
            (("id", "x" * 32), "id is 1 to 31"),
            (("id", "modern-dark"), "appears twice"),
            (("label", ""), "label is 1 to 64"),
            (("label", "tab\there"), "label is 1 to 64"),
            (("body", ["skin-modern", "theme-dark", "nui-shown"]), "not a theme class"),
            (("body", ["skin-modern", "Theme-Dark"]), "not a theme class"),
            (("body", ["skin-modern", "theme-dark", "skin-modern"]), "appears twice"),
            (("body", []), "1 to 8"),
        ]
        for (key, value), fragment in cases:
            document = minimal_themes_json()
            document["themes"][1][key] = value
            self.assertRejected(document, fragment)

    def test_a_table_needs_one_to_sixteen_themes(self):
        self.assertRejected({"themes": []}, "1 to 16")
        self.assertRejected({"other": []}, "'themes' array")

    def test_palettes_and_skins_follow_menu_order_once_each(self):
        self.assertEqual(t.palette_order(minimal_themes()), ["dark", "light", "classic"])
        self.assertEqual(t.skin_order(minimal_themes()), ["modern", "classic"])


class Output(unittest.TestCase):
    def test_the_style_sheet_puts_shared_values_on_body_and_colors_on_the_palette_classes(self):
        rcss = t.render_rcss(minimal_tokens(), minimal_themes())
        self.assertIn("body\n{\n\t--font-family: Noto Sans;", rcss)
        self.assertIn("body, body.theme-dark\n{\n\t--surface: #000000;", rcss)
        self.assertIn("\nbody.theme-light\n{\n\t--surface: #ffffff;", rcss)
        self.assertIn("\nbody.theme-classic\n{\n\t--surface: #202020;", rcss)
        self.assertIn(t.COMMAND, rcss.splitlines()[1])

    def test_skin_tokens_follow_the_palettes_under_their_skin_class(self):
        rcss = t.render_rcss(minimal_tokens(), minimal_themes())
        self.assertIn("body.skin-classic\n{\n\t--font-family: Nova Classic;\n\t--font-md: 12dp;\n"
                      "\t--classic-slot-fill: #000000;\n\t--classic-gap: 3dp;\n}", rcss)
        self.assertLess(rcss.index("body.theme-classic"), rcss.index("body.skin-classic"))
        self.assertNotIn("skin-modern", rcss, "a skin without tokens gets no block")

    def test_the_default_palette_is_the_first_themes_even_when_listed_later(self):
        tokens = minimal_tokens()
        reordered = {"shared": tokens["shared"], "classic": tokens["classic"], "light": tokens["light"],
                     "dark": tokens["dark"], "skins": tokens["skins"]}
        rcss = t.render_rcss(reordered, minimal_themes())
        self.assertIn("body, body.theme-dark\n", rcss)
        self.assertLess(rcss.index("body.theme-light"), rcss.index("body.theme-classic"))

    def test_the_token_table_replaces_only_the_text_between_the_markers(self):
        markdown = "intro\n%s\nold rows\n%s\noutro\n" % (t.TABLE_BEGIN, t.TABLE_END)
        table = t.render_table(minimal_tokens(), minimal_themes())
        spliced = t.splice_table(markdown, table)
        self.assertTrue(spliced.startswith("intro\n"))
        self.assertTrue(spliced.endswith("\noutro\n"))
        self.assertNotIn("old rows", spliced)
        self.assertIn("| Token | Dark | Light | Classic |\n|---|---|---|---|", spliced)
        self.assertIn("| `--surface` | `#000000` | `#ffffff` | `#202020` |", spliced)
        self.assertIn("| Token | Skin | Value |", spliced)
        self.assertIn("| `--classic-slot-fill` | classic | `#000000` |", spliced)
        self.assertEqual(spliced, t.splice_table(spliced, table))

    def test_a_document_without_markers_is_an_error(self):
        with self.assertRaises(t.TokenError):
            t.splice_table("no markers here", "table")

    def test_a_failing_pair_is_reported_for_each_palette(self):
        report = t.contrast_report(minimal_tokens(), minimal_themes())
        failing = [row for row in report if row[1] == "text" and row[2] == "surface"]
        self.assertEqual([row[0] for row in failing], ["dark", "light", "classic"])
        self.assertTrue(all(row[3] < row[4] for row in failing))
        self.assertEqual(len(report), 3 * len(t.CONTRAST_PAIRS))

    def test_the_report_names_each_palette_in_a_column_seven_wide(self):
        line = t.format_report(t.contrast_report(minimal_tokens(), minimal_themes())[:1])
        self.assertTrue(line.startswith("FAIL dark    text "), line)


class CommittedTokens(unittest.TestCase):
    def test_the_committed_tokens_are_valid_and_every_contrast_pair_passes(self):
        tokens, themes = t.load()
        below = [row for row in t.contrast_report(tokens, themes) if row[3] < row[4]]
        self.assertEqual(below, [], t.format_report(below))

    def test_the_committed_table_starts_with_the_three_base_themes(self):
        # Themes added later (docs/ui/AUTHORING.md, Adding a theme) come after them.
        _, themes = t.load()
        self.assertEqual([theme[0] for theme in themes][:3], ["modern-dark", "modern-light", "classic"])
        self.assertEqual(t.palette_order(themes)[:3], ["dark", "light", "classic"])

    def test_the_committed_outputs_are_up_to_date(self):
        tokens, themes = t.load()
        self.assertEqual(t.read_text(t.TOKENS_RCSS), t.render_rcss(tokens, themes), "run python tools/nui_tokens.py")
        markdown = t.read_text(t.AUTHORING_MD)
        self.assertEqual(markdown, t.splice_table(markdown, t.render_table(tokens, themes)),
                         "run python tools/nui_tokens.py")

    def test_the_input_is_not_modified_by_rendering(self):
        tokens, themes = t.load()
        before = copy.deepcopy((tokens, themes))
        t.render_rcss(tokens, themes)
        t.render_table(tokens, themes)
        self.assertEqual((tokens, themes), before)


class PlayerColors(unittest.TestCase):
    """colors.json and the slot tables (P13 spec 5.2)."""

    def test_the_committed_colors_json_is_up_to_date_and_lists_the_slot_palettes(self):
        tokens, themes = t.load()
        rendered = t.render_colors(tokens, themes)
        self.assertEqual(t.read_text(t.COLORS_JSON), rendered, "run python tools/nui_tokens.py")
        document = json.loads(rendered)
        self.assertEqual(document["version"], 1)
        self.assertEqual(document["themes"], {"modern-dark": "dark", "modern-light": "light"}, "classic offers none")
        self.assertEqual(document["pairs"], [[fg, bg, minimum] for fg, bg, minimum, _ in t.CONTRAST_PAIRS if bg not in t.OVERLAY_PLATES],
                         "every pair but the overlay plates', which the runtime never recolors")
        self.assertEqual((document["palettes"]["dark"]["tone"], document["palettes"]["light"]["tone"]), ("dark", "light"))
        self.assertEqual(set(document["palettes"]["dark"]["tokens"]), set(tokens["dark"]))

    def test_every_swatch_of_the_committed_slots_passes_the_swatch_check(self):
        tokens, themes = t.load()
        self.assertEqual(t.swatch_failures([t.render_colors(tokens, themes)]), [])

    def test_a_swatch_that_leaves_a_pair_failed_is_reported(self):
        tokens, themes = t.load()
        tokens = copy.deepcopy(tokens)
        accent = next(slot for slot in tokens["slots"]["light"] if slot["slot"] == "accent")
        accent["swatches"].append("#ffe680")
        failures = t.swatch_failures([t.render_colors(tokens, themes)])
        self.assertTrue(failures)
        self.assertEqual({(theme, case.get("accent")) for theme, case, _ in failures}, {("modern-light", "#ffe680")})

    def test_slot_tables_name_palettes_and_tokens_they_have(self):
        tokens, themes = t.load()
        for change, fragment in ((lambda s: s.update(nowhere=s["dark"]), "no palette of that name"),
                                 (lambda s: s["dark"][0]["sets"].append({"token": "missing", "rule": "value"}), "not a color of its palette"),
                                 (lambda s: s["dark"].append(dict(s["dark"][0])), "listed twice")):
            broken = copy.deepcopy(tokens)
            change(broken["slots"])
            with self.subTest(fragment=fragment), self.assertRaises(t.TokenError) as caught:
                t.validate(broken, themes)
            self.assertIn(fragment, str(caught.exception))

    def test_the_panel_backdrop_is_a_filter_list_or_none(self):
        for good in ("none", "blur(6dp)", "blur(4dp) brightness(1.1)"):
            t.check_shared_value("panel-backdrop", good)
        for bad in ("6dp", "blur(6dp", "shader(x)", "#ffffff"):
            with self.subTest(value=bad):
                self.assertRaises(t.TokenError, t.check_shared_value, "panel-backdrop", bad)

    def test_every_palette_has_a_highlight_its_quest_title_by_default(self):
        tokens, _ = t.load()
        for palette in ("dark", "light", "classic"):
            self.assertEqual(tokens[palette]["highlight"], tokens[palette]["quest-title"], palette)


if __name__ == "__main__":
    unittest.main()
