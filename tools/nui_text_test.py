"""Tests for assets/root/nui_text.py: python3 -B -m unittest nui_text_test
(from tools/). Plain CPython. The cases are tools/fixtures/text_tags_cases.json,
byte-identical to the client's tests/fixtures/nui/text-tags/cases.json, which
Core/TextTags.h passes (P10 spec 2.2.6)."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "assets", "root")))
import nui_text  # noqa: E402

CASES = os.path.join(HERE, "fixtures", "text_tags_cases.json")


def load_cases():
    with open(CASES, encoding="utf-8") as handle:
        return json.load(handle)["cases"]


def escape(text):
    """EscapeRmlText as the spec states it, to check the file's rml field
    against its runs (the client tests RunsToRml itself)."""
    for raw, entity in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ('"', "&quot;"), ("{", "&#123;"), ("}", "&#125;")):
        text = text.replace(raw, entity)
    return text.replace("@", "@⁠")


def runs_to_rml(runs):
    out = []
    for text, color, link in runs:
        attributes = ' class="nui-text__run nui-link" data-link="%s"' % escape(link) if link else ' class="nui-text__run"'
        if color != -1:
            attributes += ' style="color: #%06x%02x;"' % (color & 0xFFFFFF, (color >> 24) & 0xFF)
        out.append("<span%s>%s</span>" % (attributes, escape(text)))
    return "".join(out)


class TextTags(unittest.TestCase):
    def test_every_shared_case(self):
        cases = load_cases()
        self.assertEqual(len(cases), len({case["id"] for case in cases}), "ids are unique")
        for case in cases:
            with self.subTest(case=case["id"]):
                runs = nui_text.parse_runs(case["text"])
                self.assertEqual([list(run) for run in runs], case["runs"])
                self.assertEqual(nui_text.visible_text(case["text"]), case["visible"])
                self.assertEqual(nui_text.visible_length(case["text"]), case["visible_length"])
                self.assertEqual(runs_to_rml(runs), case["rml"], "the file's rml follows its runs")

    def test_the_file_ends_with_one_newline_and_is_indented_with_tabs(self):
        with open(CASES, "rb") as handle:
            data = handle.read()
        self.assertTrue(data.endswith(b"}\n") and not data.endswith(b"\n\n"))
        self.assertIn(b"\n\t\"cases\": [\n\t\t{", data)

    def test_a_long_link_counts_only_its_visible_text(self):
        link = "|cfff1e6c0|Hitem:4e21:0:0:0:0:1:2:3:4:5:6|h[Sword+9]|h|r"
        self.assertEqual(nui_text.visible_length(link), len("[Sword+9]"))
        self.assertEqual(nui_text.visible_length("look " + link + " ok"), len("look [Sword+9] ok"))
        self.assertEqual(nui_text.visible_text("look " + link), "look [Sword+9]")
        self.assertGreater(len(link), 50, "the tags are longer than what shows")
        line = "x" * 70 + link
        self.assertEqual(nui_text.visible_length(line), 79, "a 76-character field limit counts the 9 shown, not the tags")

    def test_link_tokens_split_as_the_tooltip_does(self):
        self.assertEqual(nui_text.link_tokens("item:4e21:0:0:0:0"), ["item", "4e21", "0", "0", "0", "0"])
        self.assertEqual(nui_text.link_tokens(""), [""])
        self.assertEqual(nui_text.link_tokens(None), [""])

    def test_a_color_needs_eight_hex_digits_and_python_int_parsing_is_not_used(self):
        self.assertEqual(nui_text.parse_runs("|cff_ff000x"), [("x", 0xFFFFFFFF, "")], "an underscore is not a hex digit")
        self.assertEqual(nui_text.parse_runs("|c ffffff0x"), [("x", 0xFFFFFFFF, "")], "nor a space")
        self.assertEqual(nui_text.parse_runs("|c12345678"), [], "a color with nothing after it draws nothing")
        self.assertEqual(nui_text.parse_runs(None), [])
        self.assertEqual(nui_text.visible_length(None), 0)


if __name__ == "__main__":
    unittest.main()
