"""Tests of tools/model_gaps.py (NOVA-177): the offline lookup of what a wiki
preview's model is made of, and why a part draws nothing. Run from tools/:

	python3 -B -m unittest model_gaps_test
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_gaps  # noqa: E402
import race_msm  # noqa: E402

RACE_FILE = (b'ScriptType RaceDataScript\nBaseModelFileName "d:/ymir work/pc/warrior/base.gr2"\n'
	b'Group ShapeData\n{\n\tPathName "d:/ymir work/pc/warrior/"\n\tShapeDataCount 2\n'
	b'\tGroup ShapeData00\n\t{\n\t\tShapeIndex 127\n\t\tModel "event1.gr2"\n\t\tSourceSkin "a.dds"\n\t\tTargetSkin "a.dds"\n\t}\n'
	b'\tGroup ShapeData01\n\t{\n\t\tShapeIndex 5\n\t\tModel "nahan.gr2"\n\t\tSourceSkin "a.dds"\n\t\tTargetSkin "a.dds"\n\t}\n'
	b'}\nGroup HairData\n{\n\tPathName "d:/ymir work/pc/warrior/"\n\tHairDataCount 2\n'
	b'\tGroup HairData00\n\t{\n\t\tHairIndex 1\n\t\tModel "hair/h1.gr2"\n\t\tSourceSkin "h.dds"\n\t\tTargetSkin "h.dds"\n\t}\n'
	b'\tGroup HairData01\n\t{\n\t\tHairIndex 1573\n\t\tModel "hair/april.gr2"\n\t}\n}\n')


class FakePack(object):
	def __init__(self, files, custom=()):
		self.files = dict((path, path) for path in files)
		self.custom = set(custom)

	def has(self, store):
		return store.lower() in self.files

	def tag(self, store):
		return model_gaps.CUSTOM_TAG if store.lower() in self.custom else 0


LISTS = types.SimpleNamespace(COSTUME_PETS={53032}, COSTUME_MOUNTS=set(), COSTUME_WINGS={48000}, COSTUME_MASKS=set(),
	COSTUME_EFFECTS=set(), COSTUME_WEAPONS=set(), COSTUME_ARMOR={11918}, COSTUME_HAIR={45663}, ITEM_BLACKLIST={10},
	MOB_BLACKLIST=set())


class Plans(unittest.TestCase):
	def test_preview_of_on_the_proto(self):
		item = lambda kind, sub, value3=0: ("x", kind, sub, value3, frozenset())  # noqa: E731
		self.assertEqual(model_gaps.item_plan(11918, item("ITEM_COSTUME", "COSTUME_BODY", 127), LISTS), ("costume_armor", "shape", 127))
		self.assertEqual(model_gaps.item_plan(312, item("ITEM_WEAPON", "WEAPON_SWORD"), LISTS), ("weapon", "weapon", 312))
		self.assertEqual(model_gaps.item_plan(45663, item("ITEM_COSTUME", "COSTUME_HAIR", 1573), LISTS), ("costume_hair", "hair", 1573))
		self.assertEqual(model_gaps.item_plan(53032, item("ITEM_UNIQUE", "", 34197), LISTS), ("pet", "mob", 34197))
		self.assertIsNone(model_gaps.item_plan(48000, item("ITEM_COSTUME", "COSTUME_SASH2", 1), LISTS))
		self.assertIsNone(model_gaps.item_plan(12000, item("ITEM_ARMOR", "ARMOR_HEAD"), LISTS))

	def test_allowed_races_follow_the_anti_flags(self):
		self.assertEqual(model_gaps.allowed_races(frozenset()), list(range(8)))
		self.assertEqual(model_gaps.allowed_races(frozenset(("ANTI_MUSA", "ANTI_FEMALE"))), [2, 5, 7])


class Causes(unittest.TestCase):
	def setUp(self):
		data = race_msm.load(RACE_FILE)
		self.races = dict((race, data) for race in race_msm.RACES)
		self.pack = FakePack(["d:/ymir work/pc/warrior/nahan.gr2", "d:/ymir work/item/weapon/00110.gr2",
			"d:/ymir work/item/weapon/custom.gr2"], custom=["d:/ymir work/item/weapon/custom.gr2"])
		self.models = {110: "d:/ymir work/item/weapon/00110.gr2", 40031: "", 999: "d:/ymir work/item/weapon/custom.gr2"}

	def cause(self, plan):
		return model_gaps.part_cause(plan, 0, self.pack, self.races, self.models, None)[0]

	def test_each_cause(self):
		self.assertEqual(self.cause(("armor", "shape", 5)), "ok")
		self.assertEqual(self.cause(("costume_armor", "shape", 127)), "model_missing")
		self.assertEqual(self.cause(("armor", "shape", 22)), "shape_missing")
		# A model-only hair registers (NOVA-177, as OLD's reader); its GR2 is not in the pack.
		self.assertEqual(self.cause(("costume_hair", "hair", 1573)), "model_missing")
		self.assertEqual(self.cause(("costume_hair", "hair", 99)), "hair_missing")
		self.assertEqual(self.cause(("weapon", "weapon", 110)), "ok")
		self.assertEqual(self.cause(("weapon", "weapon", 312)), "no_item_list")
		self.assertEqual(self.cause(("costume_weapon", "weapon", 40031)), "no_model_path")
		self.assertEqual(self.cause(("weapon", "weapon", 999)), "model_unreadable")


if __name__ == "__main__":
	unittest.main()
