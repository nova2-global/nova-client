"""Tests for the G15 plain-text subset (assets/root/nui_desc_text.py):
python3 -B -m unittest nui_desc_text_test (from tools/).

Plain CPython: `nui` and `dbg` are the shared stand-ins
(nui_test_support.py). The last case parses every shipped description file
of every left-to-right locale."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_test_support as support  # noqa: E402

LOCALES = os.path.normpath(os.path.join(support.HERE, "..", "assets", "locale", "locale"))
FILES = ("empiredesc_a.txt", "empiredesc_b.txt", "empiredesc_c.txt",
    "jobdesc_warrior.txt", "jobdesc_assassin.txt", "jobdesc_sura.txt", "jobdesc_shaman.txt")
RIGHT_TO_LEFT = ("ae",)
JOINER = "⁠"


def load_desc_text():
    """nui_desc_text.py as a fresh module over the stand-in nui and dbg."""
    state = support.NuiState()
    dbg = support.make_dbg()
    modules = support.Modules(nui=support.make_nui(state), dbg=dbg)
    try:
        module = modules.load("nui_desc_text")
    finally:
        modules.restore()
    return module, dbg


class DescTextTest(unittest.TestCase):
    def setUp(self):
        self.desc, self.dbg = load_desc_text()

    def test_one_enter_is_a_space_and_two_end_a_paragraph(self):
        source = "The Jinno Kingdom is located[ENTER]\nin the east.[ENTER]\n[ENTER]\nSecond one[ENTER]here."
        self.assertEqual(self.desc.parse(source),
            ["The Jinno Kingdom is located in the east.", "Second one here."])
        self.assertEqual(self.desc.parse("a[ENTER][ENTER][ENTER]b"), ["a", "b"])

    def test_wait_and_delay_leave_no_trace_and_wait_between_enters_still_ends_a_paragraph(self):
        source = "[DELAY value;10]\nFirst[ENTER]\n[WAIT]\nline[ENTER]\n[WAIT]\n[ENTER]\n[DELAY value;0]Next[ENTER] [WAIT] [ENTER]Last"
        self.assertEqual(self.desc.parse(source), ["First line", "Next", "Last"])
        self.assertEqual(self.dbg.lines, [])

    def test_raw_line_breaks_are_ignored_as_the_interpreter_ignores_them(self):
        self.assertEqual(self.desc.parse("one\r\ntwo\nthree\rfour"), ["onetwothreefour"])
        self.assertEqual(self.desc.parse("tabs\tand   spaces [ENTER]  here"), ["tabs and spaces here"])

    def test_an_unknown_command_is_dropped_and_logged_once(self):
        self.assertEqual(self.desc.parse("a[COLOR r;1|g;0|b;0]b[COLOR r;1]c[ QUESTION x ]d"), ["abcd"])
        self.assertEqual(self.desc.parse("e[COLOR r;0]f"), ["ef"])
        self.assertEqual(self.dbg.lines, ["nui_desc_text: dropped the command [COLOR]",
            "nui_desc_text: dropped the command [QUESTION]"])
        self.assertEqual(self.dbg.errors, [])

    def test_an_unclosed_bracket_keeps_the_rest_as_text(self):
        self.assertEqual(self.desc.parse("Before[ENTER]after [and the rest"), ["Before after [and the rest"])

    def test_text_goes_through_plain_text(self):
        self.assertEqual(self.desc.parse("Mail me@ui.LOGIN_ID[ENTER][ENTER]@game.EMPIRE_A"),
            ["Mail me@" + JOINER + "ui.LOGIN_ID", "@" + JOINER + "game.EMPIRE_A"])

    def test_bytes_are_utf8_with_the_bom_dropped_and_bad_bytes_replaced(self):
        self.assertEqual(self.desc.parse("﻿König[ENTER]reich".encode("utf-8")), ["König reich"])
        self.assertEqual(self.desc.parse(b"a\xffb"), ["a�b"])

    def test_load_reads_a_file_and_an_unreadable_one_is_empty_and_logged_once(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "desc.txt")
            with open(path, "wb") as file:
                file.write(b"[DELAY value;10]\r\nOne[ENTER]\r\ntwo[ENTER]\r\n[ENTER]\r\nThree")
            self.assertEqual(self.desc.load(path), ["One two", "Three"])
            missing = os.path.join(folder, "missing.txt")
            self.assertEqual(self.desc.load(missing), [])
            self.assertEqual(self.desc.load(missing), [])
        self.assertEqual(len(self.dbg.errors), 1)
        self.assertIn("missing.txt cannot be read", self.dbg.errors[0])

    def test_every_shipped_description_parses_into_non_empty_paragraphs_with_no_bracket_left(self):
        locales = sorted(name for name in os.listdir(LOCALES)
            if os.path.isdir(os.path.join(LOCALES, name)) and name != "common" and name not in RIGHT_TO_LEFT)
        self.assertEqual(len(locales), 16)
        for locale in locales:
            for name in FILES:
                with self.subTest(locale=locale, file=name):
                    paragraphs = self.desc.load(os.path.join(LOCALES, locale, name))
                    self.assertTrue(paragraphs)
                    for paragraph in paragraphs:
                        self.assertTrue(paragraph.strip())
                        self.assertNotIn("[", paragraph)
                        self.assertNotIn("]", paragraph)
                        self.assertEqual(paragraph, " ".join(paragraph.split()))
        self.assertEqual(self.desc.load(os.path.join(LOCALES, "en", "empiredesc_c.txt"))[0], "Jinno Kingdom")
        self.assertEqual(self.dbg.errors, [])
        self.assertEqual(self.dbg.lines, [])


if __name__ == "__main__":
    unittest.main()
