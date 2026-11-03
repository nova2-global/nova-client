"""nui_numbers (assets/root/nui_numbers.py): digit grouping with each locale's
separator. python3 -B -m unittest nui_numbers_test"""

import os
import types
import unittest

import nui_test_support as support

LOCALES = "ae br cz de dk en es fr gr hu it nl pl pt ro ru tr".split()


def load(locale_path="locale/en"):
    stand_in = types.ModuleType("localeInfo")
    stand_in.APP_GET_LOCALE_PATH = locale_path
    modules = support.Modules(localeInfo=stand_in)
    try:
        return modules.load("nui_numbers", "nui_numbers.py")
    finally:
        modules.restore()


class Grouping(unittest.TestCase):
    def test_english_groups_with_commas(self):
        numbers = load()
        self.assertEqual([numbers.group(n) for n in (0, 7, 999, 1000, 1234, 1234500, 5432100)],
                         ["0", "7", "999", "1,000", "1,234", "1,234,500", "5,432,100"])

    def test_text_of_digits_is_grouped_and_other_text_is_left_alone(self):
        numbers = load()
        self.assertEqual(numbers.group("1234500"), "1,234,500")
        self.assertEqual(numbers.group("-12345"), "-12,345")
        for text in ("", "30 / 60", "1.5", "12a", "\u0661\u0662\u0663\u0664"):
            self.assertEqual(numbers.group(text), text)

    def test_each_shipped_locale_has_a_separator_and_the_locale_comes_from_the_loaded_folder(self):
        numbers = load()
        self.assertEqual(sorted(numbers.SEPARATORS), sorted(LOCALES))
        self.assertEqual(load("locale/de").group(1234567), "1.234.567")
        self.assertEqual(load("locale/fr").group(1234567), "1\u00a0234\u00a0567")
        self.assertEqual(load("locale\\ru").group(1234), "1\u00a0234")
        self.assertEqual(load("locale/xx").group(1234), "1,234", "an unknown folder reads as English")
        self.assertEqual(numbers.group(1234, "tr"), "1.234")


if __name__ == "__main__":
    unittest.main()
