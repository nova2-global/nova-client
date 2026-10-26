"""Tests of the eight race files (assets/root/msm/<race>.msm) at the
foundation cut (protocol 3; NOVA-98). Run from tools/:

	python3 -B -m unittest race_msm_test

The cut's item_proto carries OLD's value3 for armour and costume bodies (a
shape index) and costume hairs (a hair index), so the race files have to
know OLD's indexes. race_msm.py reads a race file the way NEW's client does;
fixtures/race_msm_cut.json (made by ``race_msm.py fixture``) holds what each
pre-cut item showed before the cut and what OLD's entries give NEW's reader.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import race_msm  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MSM = os.path.join(HERE, "..", "assets", "root", "msm")
KIND = {"shape": "shapedata", "hair": "hairdata"}


def fixture():
	with open(os.path.join(HERE, "fixtures", "race_msm_cut.json"), encoding="utf-8") as handle:
		return json.load(handle)


def race_files():
	return dict((race, race_msm.load_file(os.path.join(MSM, race + ".msm"))) for race in race_msm.RACES)


def full(look):
	"""A fixture look back in race_msm.look's form."""
	if look is None:
		return None

	def path(text):
		return text if text.startswith("d:/") else race_msm.PREFIX + text
	return (path(look[0]), tuple((path(src), path(dst)) for src, dst in look[1]))


class Reader(unittest.TestCase):
	"""race_msm.load keeps the client's rules (src/EterLib/TextFileLoader.cpp,
	src/EterBase/FileLoader.cpp, src/GameLib/RaceDataFile.cpp)."""

	HEAD = b'ScriptType RaceDataScript\nBaseModelFileName "base.gr2"\n'

	def shapes(self, body, count=None):
		entries = b"".join(body)
		count = len(body) if count is None else count
		return self.HEAD + b'Group ShapeData\n{\n\tPathName "p/"\n\tShapeDataCount %d\n' % count + entries + b"}\n"

	def entry(self, number, index, extra=b""):
		return (b'\tGroup ShapeData%02d\n\t{\n\t\tShapeIndex %d\n\t\tModel "m%d.gr2"\n\t\tSourceSkin "s.dds"\n'
			b'\t\tTargetSkin "t%d.dds"\n' % (number, index, index, index) + extra + b"\t}\n")

	def test_an_entry_gives_its_model_and_skin_under_the_path(self):
		race = race_msm.load(self.shapes([self.entry(0, 7)]))
		self.assertTrue(race.loaded)
		self.assertEqual(race_msm.resolve(race, "shapedata", 7), ("p/m7.gr2", (("p/s.dds", "p/t7.dds"),)))

	def test_the_count_bounds_the_entries_read(self):
		race = race_msm.load(self.shapes([self.entry(0, 7), self.entry(1, 8)], count=1))
		self.assertEqual(sorted(race.shapes), [7])

	def test_a_key_without_a_value_fails_the_whole_load(self):
		race = race_msm.load(self.shapes([self.entry(0, 7, b"\t\tCustomOpacity\n")]))
		self.assertFalse(race.loaded)
		self.assertEqual(race.shapes, {})

	def test_an_entry_without_its_index_loses_every_later_entry_and_the_hair(self):
		lost = b"\tGroup ShapeData01\n\t{\n\t\tModel \"x.gr2\"\n\t}\n"
		hair = b'Group HairData\n{\n\tPathName "h/"\n\tHairDataCount 1\n\tGroup HairData00\n\t{\n\t\tHairIndex 1\n' \
			b'\t\tModel "h.gr2"\n\t\tSourceSkin "s.dds"\n\t\tTargetSkin "t.dds"\n\t}\n}\n'
		race = race_msm.load(self.shapes([self.entry(0, 7), lost, self.entry(2, 9)]) + hair)
		self.assertEqual(sorted(race.shapes), [7])
		self.assertEqual(race.hairs, {})
		self.assertEqual(sorted(race_msm.load(self.shapes([self.entry(0, 7)]) + hair).hairs), [1])

	def test_a_special_path_carries_into_the_entries_after_it(self):
		race = race_msm.load(self.shapes([self.entry(0, 7, b'\t\tSpecialPath "q/"\n'), self.entry(1, 8)]))
		self.assertEqual(race_msm.resolve(race, "shapedata", 8)[0], "q/m8.gr2")

	def test_a_high_byte_takes_the_next_byte_with_it_even_a_line_break(self):
		self.assertEqual(race_msm.split_lines(b"a\xc3\xa9\nb"), [b"a\xc3\xa9", b"b"])
		self.assertEqual(race_msm.split_lines(b"a\xbd\nb"), [b"a\xbd\nb"])

	def test_a_hair_needs_its_model_and_both_skins(self):
		hair = b'Group HairData\n{\n\tPathName "h/"\n\tHairDataCount 2\n\tGroup HairData00\n\t{\n\t\tHairIndex 1\n' \
			b'\t\tModel "h.gr2"\n\t\tSourceSkin "s.dds"\n\t\tCommonTargetSkin "d:/c.dds"\n\t}\n\tGroup HairData01\n\t{\n' \
			b'\t\tHairIndex 2\n\t\tModel "h.gr2"\n\t\tSourceSkin "s.dds"\n\t\tTargetSkin "t.dds"\n\t}\n}\n'
		self.assertEqual(sorted(race_msm.load(self.HEAD + hair).hairs), [2])
		self.assertEqual(sorted(race_msm.load(self.HEAD + hair, old_reader=True).hairs), [1, 2])


class RaceFiles(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		cls.fixture = fixture()
		cls.races = race_files()

	def test_every_race_file_is_ascii_and_loads_whole(self):
		for race in race_msm.RACES:
			with open(os.path.join(MSM, race + ".msm"), "rb") as handle:
				data = handle.read()
			self.assertTrue(all(byte < 0x80 for byte in data), race)
			loaded = self.races[race]
			self.assertTrue(loaded.loaded, race)
			for kind in ("shapedata", "hairdata"):
				group = loaded.top.child(kind)
				self.assertEqual(len(loaded.order[kind]), len(group.children), (race, kind))
				self.assertEqual(group.integer(kind + "count"), len(group.children), (race, kind))

	def test_every_item_that_showed_before_the_cut_shows_the_same_files(self):
		"""Each pre-cut body and hair, on each race that wore it before and
		after the cut, shows with the cut's value3 what it showed with NEW's
		pre-cut value3, or the look its listed change gives."""
		races = self.fixture["races"]
		before = self.fixture["before"]
		changes = dict(((vnum, race), full(look)) for vnum, race, look, _ in self.fixture["changes"])
		checked, wrong = 0, []
		for vnum, kind, value3, mask, pre_value3, pre_mask in self.fixture["items"]:
			if pre_value3 is None:
				continue
			for bit, race in enumerate(races):
				if not mask & pre_mask & (1 << bit):
					continue
				was = before.get(race, {}).get("%s:%d" % (kind, pre_value3))
				if was is None:
					continue
				checked += 1
				expected = changes.get((vnum, race), full(was))
				now = race_msm.resolve(self.races[race], KIND[kind], value3)
				if now != expected:
					wrong.append((vnum, race, value3, now))
		self.assertEqual(checked, 3184)
		self.assertEqual([], wrong[:20], "%d of %d pre-cut items look otherwise" % (len(wrong), checked))

	def test_old_only_items_show_olds_entries(self):
		"""An OLD-only item's index reads as OLD's entry does in NEW's reader."""
		for race, want in sorted(self.fixture["old"].items()):
			looks = {}
			for kind in ("shape", "hair"):
				for index in want[kind]:
					looks["%s:%d" % (kind, index)] = race_msm.look_json(
						race_msm.resolve(self.races[race], KIND[kind], index))
			self.assertEqual(race_msm.old_digest(looks), want["digest"], race)

	def test_the_old_only_items_shown(self):
		races = self.fixture["races"]
		vnums = shown_vnums = pairs = shown_pairs = 0
		for _, kind, value3, mask, pre_value3, _ in self.fixture["items"]:
			if pre_value3 is not None:
				continue
			vnums += 1
			shows = False
			for bit, race in enumerate(races):
				if mask & (1 << bit):
					pairs += 1
					if race_msm.resolve(self.races[race], KIND[kind], value3) is not None:
						shown_pairs += 1
						shows = True
			shown_vnums += shows
		counts = {"vnums": vnums, "vnums_shown": shown_vnums, "pairs": pairs, "pairs_shown": shown_pairs}
		self.assertEqual(counts, self.fixture["old_only"])
		self.assertEqual(counts, {"vnums": 3606, "vnums_shown": 2584, "pairs": 15072, "pairs_shown": 11374})


if __name__ == "__main__":
	unittest.main()
