"""Tests of assets/root/npclist.txt at the foundation cut (NOVA-98): NEW's
lines as they were, but OLD's name for the mobs the cut brings that NEW named
for another model where the client ships OLD's, then OLD's folder and name
lines for the cut's mobs NEW names none for. Run from tools/:

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
		cls.head = "".join(line + "\n" for line in lines[:cls.want["new_lines"]])
		try:
			cls.new_text = old_content.npclist_news(cls.text, cls.want)
		except ValueError:
			# A renamed line does not name OLD's mob: the tests below say which.
			cls.new_text = cls.head
		cls.added = lines[cls.want["new_lines"]:-1]
		cls.files = old_content.published_files()

	def test_every_line_reads_as_the_game_reads_it(self):
		"""__LoadGameNPC aborts the client on a line whose first column is not
		a number or that lacks its name or folder, and cuts the last letter of
		a last line without a break."""
		self.assertNotIn("\r", self.text)
		names, folders = old_content.npclist_entries(self.text)
		self.assertGreater(len(names), 3000)
		self.assertGreater(len(folders), 700)

	def test_news_lines_are_as_they_were_but_the_renamed_names(self):
		"""Only the name of a renamed mob's first line differs from NEW's."""
		self.assertEqual(hashlib.sha1(self.new_text.encode("ascii")).hexdigest(), self.want["new_sha1"])
		changed = [(old, new) for old, new in zip(self.new_text.split("\n"), self.head.split("\n")) if old != new]
		self.assertEqual(len(changed), len(self.want["renamed"]))
		for (old, new), (vnum, was, name) in zip(changed, self.want["renamed"]):
			self.assertEqual(old.split("\t")[:2], [str(vnum), was])
			self.assertEqual(new.split("\t")[:2], [str(vnum), name])
			self.assertEqual(old.split("\t")[2:], new.split("\t")[2:])

	def test_the_cuts_mobs_new_named_for_another_model_take_olds_name(self):
		"""The mobs the cut brings that NEW named otherwise than OLD read OLD's
		name where the client ships OLD's model: 16 that found no model by
		NEW's name, and 7 that found another mob's."""
		names, folders = old_content.npclist_entries(self.text)
		new_names, new_folders = old_content.npclist_entries(self.new_text)
		renamed = [vnum for vnum, _, _ in self.want["renamed"]]
		self.assertEqual(old_content.ranges(renamed),
			"2600-2603, 2620, 2630-2633, 2650, 2660-2663, 2680, 7113-7119, 20396")
		for vnum, was, name in self.want["renamed"]:
			self.assertEqual((new_names[vnum], names[vnum]), (was, name))
			self.assertTrue(old_content.mob_shows(vnum, names, folders, self.files), vnum)
		unseen = [vnum for vnum in renamed if not old_content.mob_shows(vnum, new_names, new_folders, self.files)]
		self.assertEqual(old_content.ranges(unseen), "2600-2603, 2620, 2630-2633, 2650, 2660-2663, 2680, 20396")

	def test_the_cuts_new_mobs_the_client_creates(self):
		"""Of the 2,083 mobs the cut brings, NEW's own list made 51 (8 of them
		through a '#' path); OLD's lines make 164 more."""
		new_mobs = old_content.parse_ranges(self.want["cut_new_mobs"])
		self.assertEqual(len(new_mobs), 2083)

		def shown(text):
			names, folders = old_content.npclist_entries(text)
			return sum(1 for vnum in new_mobs if old_content.mob_shows(vnum, names, folders, self.files))
		self.assertEqual(shown(self.new_text), 51)
		self.assertEqual(shown(self.text), self.want["cut_new_mobs_shown"])
		self.assertEqual(shown(self.text), 215)

	def test_a_hash_name_is_a_path_to_its_shape_file(self):
		"""CRaceManager::__LoadRaceData (LOAD_LOCAL_RESOURCE): '#<path>' loads
		<path>shape.msm."""
		files = {"season1/npc/goldenfrog/shape.msm"}
		self.assertTrue(old_content.mob_shows(7101, {7101: "#season1/npc/goldenfrog/"}, {}, files))
		self.assertFalse(old_content.mob_shows(7101, {7101: "#season1/npc/frog/"}, {}, files))

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
		shown = [vnum for vnum in old_content.parse_ranges(self.want["names"])
			if old_content.mob_shows(vnum, names, folders, self.files)]
		self.assertEqual(len(shown), self.want["shown"])
		self.assertEqual(len(shown), 148)


if __name__ == "__main__":
	unittest.main()
