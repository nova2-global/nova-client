"""Tests of assets/locale/locale/common/item_list.txt at the foundation cut
(NOVA-98): NEW's lines as they were, then OLD's lines for the cut's items
NEW's list lacks whose files the client has (wave 6's quivers, sashes,
weapon costumes and auras since tools/old_art.py took their files from OLD's
client). Run from tools/:

	python3 -B -m unittest item_list_test

tools/old_content.py writes the lines and the fixture entry
(tools/fixtures/old_content.json, "item_list").
"""
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import old_content  # noqa: E402


def read_list():
	with open(old_content.ITEM_LIST, "rb") as handle:
		return handle.read()


class ItemList(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		cls.data = read_list()
		cls.want = old_content.load_fixture()["item_list"]
		cls.lines = cls.data.decode("ascii").split("\n")
		cls.added = cls.lines[cls.want["new_lines"]:-1]

	def test_every_line_is_one_the_loader_takes(self):
		"""LoadItemList takes 3, 4 or 5 tab columns (5 only on OLD's aura
		lines) and logs anything else as a StrangeLine; the file is ASCII
		with LF breaks and ends with one."""
		self.assertTrue(self.data.endswith(b"\n"))
		self.assertNotIn(b"\r", self.data)
		taken, strange = old_content.item_list_lines(self.data)
		self.assertEqual(strange, [])
		for line in self.lines[:-1]:
			tokens = old_content.split_tab(line)
			if tokens is None:
				continue
			self.assertTrue(tokens[0].isdigit(), line)
			self.assertTrue(len(tokens) < 5 or tokens[1] == "AURA", line)
		self.assertGreater(len(taken), 6400)

	def test_news_lines_are_as_they_were(self):
		head = "".join(line + "\n" for line in self.lines[:self.want["new_lines"]])
		self.assertEqual(hashlib.sha1(head.encode("ascii")).hexdigest(), self.want["new_sha1"])

	def test_olds_lines_for_the_cuts_items_follow_once_each(self):
		new_vnums = set(old_content.item_list_lines("".join(
			line + "\n" for line in self.lines[:self.want["new_lines"]]).encode("ascii"))[0])
		vnums = [old_content.atoi(old_content.split_tab(line)[0]) for line in self.added]
		self.assertEqual(vnums, self.want["added"])
		# 2222 at the cut and wave 6; the sash costumes (OLD's wings) and the
		# glowing sashes' model vnums (851xx, 861xx; NOVA-20) since.
		# The 45 advanced pet items (NOVA-24: OLD live, the 0.2 pack's rows).
		self.assertEqual(len(vnums), 3064)
		self.assertEqual(len(set(vnums)), len(vnums))
		self.assertEqual(new_vnums & set(vnums), set())

	def test_an_aura_line_keeps_olds_aura_and_wing_effects(self):
		"""CItemManager::LoadItemList reads an AURA line's fourth column as
		the aura's effect and a fifth as the wings' (NOVA-23, OLD's)."""
		self.assertEqual(old_content.old_item_line(
			"149006\tAURA\ticon/item/149006.tga\td:/a/only_aura.mse\td:/a/only_wing.mse"),
			"149006\tAURA\ticon/item/149006.tga\td:/a/only_aura.mse\td:/a/only_wing.mse")
		with self.assertRaises(ValueError):
			old_content.old_item_line("1\tWEAPON\ticon/item/1.tga\ta.gr2\tb.gr2")
		auras = [old_content.split_tab(line) for line in self.added if old_content.split_tab(line)[1] == "AURA"]
		self.assertEqual([tokens[0] for tokens in auras], ["149001", "149002", "149003", "149004", "149005", "149006"])
		self.assertEqual(len(auras[-1]), 5)

	def test_every_added_line_names_files_the_client_ships(self):
		"""A listed icon the store lacks shows no icon at all, where an
		unlisted item falls back to the empty bowl."""
		files = old_content.published_files()
		missing = []
		for line in self.added:
			for path in old_content.split_tab(line)[2:]:
				if old_content.store_name(path) not in files:
					missing.append(line)
		self.assertEqual(missing, [])
		self.assertTrue(self.added)


if __name__ == "__main__":
	unittest.main()
