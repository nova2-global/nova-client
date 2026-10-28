"""Tests of assets/locale/locale/common/item_list.txt at the foundation cut
(NOVA-98): NEW's lines as they were, then OLD's lines for the cut's items
NEW's list lacks whose files the client has. Run from tools/:

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
		"""LoadItemList takes 3 or 4 tab columns and logs anything else as a
		StrangeLine; the file is ASCII with LF breaks and ends with one."""
		self.assertTrue(self.data.endswith(b"\n"))
		self.assertNotIn(b"\r", self.data)
		taken, strange = old_content.item_list_lines(self.data)
		self.assertEqual(strange, [])
		for line in self.lines[:-1]:
			tokens = old_content.split_tab(line)
			if tokens is None:
				continue
			self.assertTrue(tokens[0].isdigit(), line)
		self.assertGreater(len(taken), 6400)

	def test_news_lines_are_as_they_were(self):
		head = "".join(line + "\n" for line in self.lines[:self.want["new_lines"]])
		self.assertEqual(hashlib.sha1(head.encode("ascii")).hexdigest(), self.want["new_sha1"])

	def test_olds_lines_for_the_cuts_items_follow_once_each(self):
		new_vnums = set(old_content.item_list_lines("".join(
			line + "\n" for line in self.lines[:self.want["new_lines"]]).encode("ascii"))[0])
		vnums = [old_content.atoi(old_content.split_tab(line)[0]) for line in self.added]
		self.assertEqual(vnums, self.want["added"])
		self.assertEqual(len(vnums), 188)
		self.assertEqual(len(set(vnums)), len(vnums))
		self.assertEqual(new_vnums & set(vnums), set())

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
