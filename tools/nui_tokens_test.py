"""Unit tests for nui_tokens.py: python -B -m unittest nui_tokens_test (from tools/; -B keeps
__pycache__ out of the repository)"""
import copy
import unittest

import nui_tokens as t


def minimal_tokens():
    shared = {name: "4dp" for name in t.REQUIRED_SHARED}
    shared.update({"font-family": "Noto Sans", "dur-fast": "0.1s", "dur-med": "0.2s", "dur-slow": "0.3s",
                   "ease-out": "cubic-out", "ease-in-out": "cubic-in-out"})
    dark = {name: "#000000" for name in t.REQUIRED_COLORS}
    light = {name: "#ffffff" for name in t.REQUIRED_COLORS}
    return {"shared": shared, "dark": dark, "light": light}


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
    def assertRejected(self, tokens, fragment):
        with self.assertRaises(t.TokenError) as caught:
            t.validate(tokens)
        self.assertIn(fragment, str(caught.exception))

    def test_a_complete_token_set_passes(self):
        t.validate(minimal_tokens())

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

    def test_themes_must_define_the_same_colors(self):
        tokens = minimal_tokens()
        tokens["dark"]["only-dark"] = "#123456"
        self.assertRejected(tokens, "only-dark")

    def test_colors_must_be_six_or_eight_digit_hex(self):
        tokens = minimal_tokens()
        tokens["dark"]["text"] = "rgb(1, 2, 3)"
        self.assertRejected(tokens, "#rrggbb")

    def test_colors_do_not_belong_in_shared(self):
        tokens = minimal_tokens()
        tokens["shared"]["brand"] = "#ff0000"
        self.assertRejected(tokens, "dark and light")

    def test_token_names_are_lowercase_words(self):
        tokens = minimal_tokens()
        tokens["dark"]["Surface"] = "#000000"
        self.assertRejected(tokens, "lowercase")

    def test_unknown_sections_are_refused(self):
        tokens = minimal_tokens()
        tokens["sepia"] = {}
        self.assertRejected(tokens, "unknown sections")


class Output(unittest.TestCase):
    def test_the_style_sheet_puts_shared_values_on_body_and_colors_on_the_theme_classes(self):
        rcss = t.render_rcss(minimal_tokens())
        self.assertIn("body\n{\n\t--font-family: Noto Sans;", rcss)
        self.assertIn("body, body.theme-dark\n{\n\t--surface: #000000;", rcss)
        self.assertIn("body.theme-light\n{\n\t--surface: #ffffff;", rcss)
        self.assertIn(t.COMMAND, rcss.splitlines()[1])

    def test_the_token_table_replaces_only_the_text_between_the_markers(self):
        markdown = "intro\n%s\nold rows\n%s\noutro\n" % (t.TABLE_BEGIN, t.TABLE_END)
        spliced = t.splice_table(markdown, t.render_table(minimal_tokens()))
        self.assertTrue(spliced.startswith("intro\n"))
        self.assertTrue(spliced.endswith("\noutro\n"))
        self.assertNotIn("old rows", spliced)
        self.assertIn("| `--surface` | `#000000` | `#ffffff` |", spliced)
        self.assertEqual(spliced, t.splice_table(spliced, t.render_table(minimal_tokens())))

    def test_a_document_without_markers_is_an_error(self):
        with self.assertRaises(t.TokenError):
            t.splice_table("no markers here", "table")

    def test_a_failing_pair_is_reported(self):
        tokens = minimal_tokens()
        report = t.contrast_report(tokens)
        failing = [row for row in report if row[1] == "text" and row[2] == "surface"]
        self.assertTrue(failing and all(row[3] < row[4] for row in failing))


class CommittedTokens(unittest.TestCase):
    def test_the_committed_tokens_are_valid_and_every_contrast_pair_passes(self):
        tokens = t.load_tokens()
        below = [row for row in t.contrast_report(tokens) if row[3] < row[4]]
        self.assertEqual(below, [], t.format_report(below))

    def test_the_committed_outputs_are_up_to_date(self):
        tokens = t.load_tokens()
        self.assertEqual(t.read_text(t.TOKENS_RCSS), t.render_rcss(tokens), "run python tools/nui_tokens.py")
        markdown = t.read_text(t.AUTHORING_MD)
        self.assertEqual(markdown, t.splice_table(markdown, t.render_table(tokens)), "run python tools/nui_tokens.py")

    def test_the_input_is_not_modified_by_rendering(self):
        tokens = t.load_tokens()
        before = copy.deepcopy(tokens)
        t.render_rcss(tokens)
        t.render_table(tokens)
        self.assertEqual(tokens, before)


if __name__ == "__main__":
    unittest.main()
