"""Tests of assets/root/npclist.txt at the foundation cut (NOVA-98): NEW's
lines as they were, then OLD's folder and name lines for the cut's mobs NEW
names none for. Run from tools/:

	python3 -B -m unittest npclist_test

tools/old_content.py writes the lines and the fixture entry
(tools/fixtures/old_content.json, "npclist").
"""
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import old_content  # noqa: E402


class NpcList(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		with open(old_content.NPCLIST, "rb") as handle:
			cls.data = handle.read()
		cls.text = cls.data.decode("ascii")
		cls.want = old_content.load_fixture()["npclist"]
		lines = cls.text.split("\n")
		cls.new_text = "".join(line + "\n" for line in lines[:cls.want["new_lines"]])
		cls.added = lines[cls.want["new_lines"]:-1]

	def test_every_line_reads_as_the_game_reads_it(self):
		"""__LoadGameNPC aborts the client on a line whose first column is not
		a number or that lacks its name or folder, and cuts the last letter of
		a last line without a break."""
		self.assertNotIn("\r", self.text)
		names, folders = old_content.npclist_entries(self.text)
		self.assertGreater(len(names), 3000)
		self.assertGreater(len(folders), 700)

	def test_news_lines_are_as_they_were(self):
		self.assertEqual(hashlib.sha1(self.new_text.encode("ascii")).hexdigest(), self.want["new_sha1"])

	def test_olds_folder_and_name_lines_follow_and_override_nothing(self):
		new_names, new_folders = old_content.npclist_entries(self.new_text)
		folders = [line.split("\t")[1] for line in self.added if line.startswith("0\t")]
		vnums = [int(line.split("\t")[0]) for line in self.added if not line.startswith("0\t")]
		self.assertEqual(folders, self.want["folders"])
		self.assertEqual(vnums, old_content.parse_ranges(self.want["names"]))
		self.assertEqual((len(vnums), len(folders)), (1927, 650))
		self.assertEqual(set(vnums) & set(new_names), set())
		self.assertEqual(set(folders) & set(new_folders), set())
		self.assertEqual(len(set(vnums)), len(vnums))
		self.assertEqual(len(set(folders)), len(folders))

	def test_the_added_mobs_whose_model_the_client_ships(self):
		"""148 of the added mobs find their .msm on CRaceManager's paths, so
		the client creates them; the others stay unseen until their folders
		land."""
		names, folders = old_content.npclist_entries(self.text)
		files = old_content.published_files()
		shown = [vnum for vnum in old_content.parse_ranges(self.want["names"])
			if old_content.mob_shows(vnum, names, folders, files)]
		self.assertEqual(len(shown), self.want["shown"])
		self.assertEqual(len(shown), 148)


if __name__ == "__main__":
	unittest.main()
