"""Tests of tools/old_art.py (OLD's art for wave 6, NOVA-19 to 23) and of the
files it took (tools/fixtures/old_art.tsv). Run from tools/:

	python3 -B -m unittest old_art_test
"""
import os
import shutil
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import old_art  # noqa: E402
import old_content  # noqa: E402


class StorePath(unittest.TestCase):

	def test_an_absolute_name_is_lowercased_with_forward_slashes(self):
		self.assertEqual(old_art.store_path(r"D:\Ymir Work\item\wing\Acce_85_001-008.dds", "x"),
			"d:/ymir work/item/wing/acce_85_001-008.dds")

	def test_any_drive_before_ymir_work_reads_as_d(self):
		self.assertEqual(old_art.store_path(r"C:\ymir work\item\weapon\a.dds", "x"), "d:/ymir work/item/weapon/a.dds")

	def test_an_artists_desktop_path_stays_as_it_is(self):
		self.assertEqual(old_art.store_path(r"C:\Users\Mark\Desktop\a.dds", "x"), "c:/users/mark/desktop/a.dds")

	def test_a_relative_name_is_in_its_referrers_folder(self):
		self.assertEqual(old_art.store_path("tex/Sword.dds", "d:/ymir work/effect/mehok/22/sword.mse"),
			"d:/ymir work/effect/mehok/22/tex/sword.dds")

	def test_store_roots_without_a_drive_are_kept(self):
		self.assertEqual(old_art.store_path("icon/item/79501.tga", "d:/ymir work/a/b.mse"), "icon/item/79501.tga")
		self.assertEqual(old_art.store_path("ymir work/a/b.dds", "x"), "d:/ymir work/a/b.dds")


class References(unittest.TestCase):

	def test_an_effect_scripts_quoted_files_absolute_and_relative(self):
		script = (b'Group Particle\n{\n\tList TextureFiles\n\t{\n\t\t"d:/ymir work/effect/etc/buff/wing1.dds"\n'
			b'\t}\n}\nGroup Mesh\n{\n\tMeshFileName\t"wing_lv06.mde"\n\tSoundFileName "d:\\ymir work\\sound\\x.wav"\n}\n')
		self.assertEqual(old_art.references(script, "d:/ymir work/pc/common/effect/aura/a.mse"), [
			"d:/ymir work/effect/etc/buff/wing1.dds",
			"d:/ymir work/pc/common/effect/aura/wing_lv06.mde",
			"d:/ymir work/sound/x.wav"])

	def test_a_motion_names_its_animation(self):
		motion = b'ScriptType MotionData\nMotionFileName "D:\\Ymir Work\\pc\\assassin\\bow\\attack_special.gr2"\n'
		self.assertEqual(old_art.references(motion, "d:/ymir work/pc/assassin/bow/attack_special.msa"),
			["d:/ymir work/pc/assassin/bow/attack_special.gr2"])


class Seeds(unittest.TestCase):

	PROTO = ("ITEM_VNUM~RANGE\tITEM_NAME(K)\tITEM_TYPE\tSUB_TYPE\n"
		"79501\tQuiver\tITEM_WEAPON\tWEAPON_UNLIMITED_ARROW\n"
		"85001\tSash\tITEM_COSTUME\tCOSTUME_SASH\n"
		"86001\tWing\tITEM_COSTUME\tCOSTUME_SASH2\n"
		"149006\tAura\tITEM_COSTUME\tCOSTUME_AURA\n"
		"40101\tBlade\tITEM_COSTUME\tCOSTUME_WEAPON\n")
	OLD = (b"79501\tWEAPON\ticon/item/79501.tga\n"
		b"85001\tCOSTUME\ticon/item/85001.tga\td:/ymir work/item/wing/acce_01.gr2\n"
		b"86001\tCOSTUME\ticon/item/86001.tga\td:/ymir work/item/wing/wing_01.gr2\n"
		b"149006\tAURA\ticon/item/149006.tga\td:/ymir work/a/aura.mse\td:/ymir work/a/wing.mse\n"
		b"40101\tWEAPON\ticon/item/40101.tga\td:/ymir work/item/weapon/40101.gr2\n")

	def test_only_the_waves_sub_types_that_new_lacks_then_extra(self):
		new = b"40101\tWEAPON\ticon/item/40101.tga\td:/ymir work/item/weapon/40101.gr2\n"
		files = {"icon/item/85001.tga", old_art.EXTRA[0]}
		self.assertEqual(old_art.seeds(self.OLD, self.PROTO, new, files), [
			"icon/item/79501.tga",
			"d:/ymir work/item/wing/acce_01.gr2",
			"icon/item/149006.tga", "d:/ymir work/a/aura.mse", "d:/ymir work/a/wing.mse"] + list(old_art.EXTRA[1:]))


class Groups(unittest.TestCase):

	FOLDERS = {
		"d:/ymir work/item": {"item": 900, "metin2_patch_eu4": 3},
		"d:/ymir work/item/weapon": {"item": 700},
		"d:/ymir work/effect/etc/buff": {"metin2_patch_eu4": 40, "Effect": 2},
		"d:/ymir work": {"Zone": 50000},
		"icon/item": {"icon": 5000},
	}

	def test_the_nearest_folder_a_group_has_decides(self):
		self.assertEqual(old_art.choose_group("d:/ymir work/item/wing/acce.gr2", self.FOLDERS), "item")
		self.assertEqual(old_art.choose_group("d:/ymir work/effect/etc/buff/buff_item6.mse", self.FOLDERS),
			"metin2_patch_eu4")
		self.assertEqual(old_art.choose_group("icon/item/85001.tga", self.FOLDERS), "icon")

	def test_a_folder_only_old_has_goes_with_the_items(self):
		self.assertEqual(old_art.choose_group("d:/ymir work/shardwork/new_sash/a.gr2", self.FOLDERS), "item")

	def test_an_existing_folder_keeps_its_spelling_a_new_one_takes_olds(self):
		root = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, root)
		os.makedirs(os.path.join(root, "item", "ymir work", "item", "weapon"))
		got = old_art.destination(root, "item", "d:/Ymir Work/Item/Wing/Acce_01.gr2")
		self.assertEqual(os.path.relpath(got, root).replace("\\", "/"), "item/ymir work/item/Wing/Acce_01.gr2")
		got = old_art.destination(root, "icon", "icon/item/85001.tga")
		self.assertEqual(os.path.relpath(got, root).replace("\\", "/"), "icon/icon/item/85001.tga")

	def test_a_granny_files_type_tag(self):
		root = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, root)
		path = os.path.join(root, "a.gr2")
		with open(path, "wb") as handle:
			handle.write(bytes(68) + struct.pack("<I", old_art.CUSTOM_TAG))
		self.assertEqual(old_art.granny_tag(path), old_art.CUSTOM_TAG)


class Manifest(unittest.TestCase):
	"""The files tools/old_art.py took (tools/fixtures/old_art.tsv)."""

	@classmethod
	def setUpClass(cls):
		with open(old_art.MANIFEST, encoding="utf-8") as handle:
			cls.rows = [line.rstrip("\n").split("\t") for line in handle if not line.startswith("#")]

	def test_every_file_is_in_its_group_and_published(self):
		files = old_content.published_files()
		self.assertEqual([row[0] for row in self.rows if row[0] not in files], [])
		self.assertEqual([row[1] for row in self.rows if not os.path.isfile(os.path.join(old_content.ASSETS, row[1]))], [])
		self.assertGreater(len(self.rows), 4000)

	def test_no_model_taken_is_olds_custom_granny_file(self):
		"""NEW's loader reads a custom file (OLD Tools/preproc
		ConvertToCustom) as a model with no mesh."""
		custom = []
		for path, asset, _, how in self.rows:
			if path.endswith(".gr2") and old_art.granny_tag(os.path.join(old_content.ASSETS, asset)) == old_art.CUSTOM_TAG:
				custom.append(path)
		self.assertEqual(custom, [])
		self.assertIn("converted", {row[3] for row in self.rows})

	def test_the_waves_extra_files_are_taken(self):
		taken = {row[0] for row in self.rows}
		self.assertEqual([path for path in old_art.EXTRA if path not in taken], [])


if __name__ == "__main__":
	unittest.main()
