"""NOVA-176: NEW's locale/common/shiningtable.txt (OLD's ENABLE_SHINING_SYSTEM)
and the art it names. Run from tools/:

	python3 -B -m unittest shining_table_test

The table holds the wings' rows (NOVA-20) and OLD's body armor and body
costume rows whose art OLD ships in full. OLD's weapon costume rows wait for
their art (Eddy, 2026-11-11); the rows of OLD's effect costumes and effect
tags belong to systems NEW lacks.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import old_art  # noqa: E402

# CItemData::ITEM_SHINING_MAX_COUNT.
MAX_COLUMNS = 6
# The item kinds the client shines (CInstanceBase: the sash costume's part,
# __AttachArmorShiningEffects) that the table holds rows for today.
KINDS = ("COSTUME_SASH2", "ARMOR_BODY", "COSTUME_BODY")
# NEW's runtime item_proto, when this machine has it.
PROTO = os.environ.get("NOVA_ITEM_PROTO", "/home/eddy/new-project/new/nova-server-nui-rt/share/conf/item_proto.txt")


def table_rows():
	with open(old_art.SHINING_TABLE, "rb") as handle:
		data = handle.read()
	return data, [line for line in data.decode("latin-1").split("\n") if line.strip()]


def vnums(key):
	if "~" in key:
		first, last = key.split("~")
		return range(int(first), int(last) + 1)
	return [int(key)]


class ShiningTable(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		cls.data, cls.rows = table_rows()

	def test_lf_endings_as_the_wings_rows_had(self):
		self.assertNotIn(b"\r", self.data)

	def test_every_row_is_a_vnum_or_range_and_up_to_six_effects(self):
		for row in self.rows:
			with self.subTest(row=row[:60]):
				cells = row.split("\t")
				self.assertTrue(cells[0].replace("~", "").isdigit())
				filled = [cell for cell in cells[1:] if cell.strip()]
				self.assertTrue(1 <= len(filled) <= MAX_COLUMNS)
				# SplitLine skips runs of tabs: an empty column before a filled
				# one would move the ones after it.
				self.assertEqual(cells[1:1 + len(filled)], filled)
				for cell in filled:
					self.assertTrue(cell.strip('"').split("#")[0].lower().endswith(".mse"), cell)

	def test_each_vnum_has_one_row(self):
		seen = {}
		for row in self.rows:
			for vnum in vnums(row.split("\t")[0]):
				self.assertNotIn(vnum, seen, row)
				seen[vnum] = row

	def test_the_rows_of_the_wings_and_the_bodies(self):
		count = sum(len(vnums(row.split("\t")[0])) for row in self.rows)
		self.assertEqual((len(self.rows), count), (287, 672))

	def test_every_effect_is_published(self):
		groups = old_art._groups()
		files = old_art.tree_published(old_art.tree_files(), groups)
		missing = [path for path in old_art.shining_seeds(self.data) if path not in files]
		self.assertEqual(missing, [])

	@unittest.skipUnless(os.path.exists(PROTO), "no runtime item_proto here")
	def test_every_vnum_the_proto_knows_is_a_kind_the_client_shines(self):
		kinds = {}
		with open(PROTO, encoding="latin-1") as handle:
			for line in handle:
				cells = line.rstrip("\n").split("\t")
				if cells[0][:1].isdigit() and len(cells) > 3:
					for vnum in vnums(cells[0]):
						kinds[vnum] = cells[3]
		for row in self.rows:
			for vnum in vnums(row.split("\t")[0]):
				if vnum in kinds:
					self.assertIn(kinds[vnum], KINDS, row[:60])
