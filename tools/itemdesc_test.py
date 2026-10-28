"""Tests of the 17 assets/locale/locale/<locale>/itemdesc.txt at the
foundation cut (NOVA-98): NEW's lines as they were, then OLD's lines for the
cut's items each file has none for (br from OLD's pt; OLD has no br). Run
from tools/:

	python3 -B -m unittest itemdesc_test

tools/old_content.py writes the lines and the fixture entry
(tools/fixtures/old_content.json, "itemdesc").
"""
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import old_content  # noqa: E402

ADDED = {
	"ae": 25, "br": 1231, "cz": 1109, "de": 1382, "dk": 1024, "en": 4768, "es": 1205, "fr": 1348, "gr": 1219,
	"hu": 1210, "it": 1226, "nl": 1217, "pl": 1140, "pt": 1229, "ro": 1242, "ru": 1205, "tr": 1198,
}


class ItemDesc(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		cls.want = old_content.load_fixture()["itemdesc"]
		cls.files = {}
		for locale in old_content.itemdesc_locales():
			with open(old_content.itemdesc_path(locale), "rb") as handle:
				data = handle.read()
			lines = data.split(b"\n")
			count = cls.want[locale]["new_lines"]
			cls.files[locale] = (data, b"".join(line + b"\n" for line in lines[:count]), lines[count:-1])

	def test_every_locale_has_its_entry(self):
		self.assertEqual(sorted(self.files), sorted(ADDED))
		self.assertEqual(sorted(self.want), sorted(ADDED))

	def test_every_file_keeps_its_encoding_and_line_breaks(self):
		"""UTF-8 without a BOM, LF breaks and a final one, as every NEW file
		was; the loader (Bind, with its DBCS rule) reads each added line as
		one line."""
		for locale, (data, new, added) in sorted(self.files.items()):
			data.decode("utf-8")
			self.assertFalse(data.startswith(b"\xef\xbb\xbf"), locale)
			self.assertNotIn(b"\r", data, locale)
			self.assertTrue(data.endswith(b"\n"), locale)
			self.assertEqual(old_content.bind_lines(data), old_content.bind_lines(new)[:-1] + added + [b""], locale)

	def test_news_lines_are_as_they_were(self):
		for locale, (_, new, _) in sorted(self.files.items()):
			self.assertEqual(hashlib.sha1(new).hexdigest(), self.want[locale]["new_sha1"], locale)

	def test_olds_lines_for_the_cuts_items_follow_once_each(self):
		counts = {}
		for locale, (_, new, added) in sorted(self.files.items()):
			new_vnums = set(old_content.atoi(line.split(b"\t")[0].decode("latin-1")) for line in new.split(b"\n") if line)
			vnums = [old_content.atoi(line.split(b"\t")[0].decode("latin-1")) for line in added]
			self.assertEqual(vnums, old_content.parse_ranges(self.want[locale]["added"]), locale)
			self.assertEqual(new_vnums & set(vnums), set(), locale)
			self.assertEqual(len(set(vnums)), len(vnums), locale)
			counts[locale] = len(vnums)
		self.assertEqual(counts, ADDED)

	def test_br_takes_pts_lines(self):
		"""For an item both lacked, br's added line is pt's."""
		pt = dict((line.split(b"\t")[0], line) for line in self.files["pt"][2])
		br = dict((line.split(b"\t")[0], line) for line in self.files["br"][2])
		shared = set(pt) & set(br)
		self.assertEqual(len(shared), 1229)
		self.assertEqual([vnum for vnum in shared if pt[vnum] != br[vnum]], [])

	def test_the_loader_describes_the_added_items(self):
		"""LoadItemDesc reads each added line as the item's line."""
		for locale, (data, _, added) in sorted(self.files.items()):
			lines = old_content.itemdesc_lines(data)
			for line in added:
				self.assertEqual(lines[old_content.atoi(line.split(b"\t")[0].decode("latin-1"))], line, locale)


if __name__ == "__main__":
	unittest.main()
