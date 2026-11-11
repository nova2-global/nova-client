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
			"icon/item/86001.tga", "d:/ymir work/item/wing/wing_01.gr2",
			"icon/item/149006.tga", "d:/ymir work/a/aura.mse", "d:/ymir work/a/wing.mse"] + list(old_art.EXTRA[1:]))


class WingSeeds(unittest.TestCase):
	"""The wings (COSTUME_SASH2, the NOVA-20 follow-up): besides their
	item_list lines, their shining effects (locale/common/shiningtable.txt)
	and the race shapes the msm files' WingData groups give the wings whose
	value 3 names one (OLD GameLib/RaceDataFile.cpp:653-815)."""

	PROTO = ("ITEM_VNUM~RANGE\tITEM_NAME(K)\tITEM_TYPE\tSUB_TYPE\tVALUE0\tVALUE1\tVALUE2\tVALUE3\n"
		"48000\tLucifer Wings\tITEM_COSTUME\tCOSTUME_SASH2\t4\t0\t0\t8\n"
		"48376\tShiva Coat\tITEM_COSTUME\tCOSTUME_SASH2\t4\t0\t0\t48376\n"
		"48380~48381\tShiva Coat+\tITEM_COSTUME\tCOSTUME_SASH2\t4\t0\t0\t48380\n"
		"85001\tSash\tITEM_COSTUME\tCOSTUME_SASH\t1\t0\t0\t48377\n")

	def test_the_value_3_of_the_wings_names_their_shapes(self):
		self.assertEqual(old_art.wing_shapes(self.PROTO), {8, 48376, 48380})

	def test_a_shining_tables_effects_without_their_bones(self):
		table = (b"48493\td:/ymir work/item/wing/2022_march_shiva1_col1.mse\n"
			b"48500~48502\tD:/ymir work/effect/mehok/22/wing.mse#Bip01\td:/ymir work/item/wing/a.mse\n"
			b"\n48069\tD:\\ymir work\\item\\wing\\space.mse\n"
			b"48070\td:/ymir work/item/wing/a.mse\n")
		self.assertEqual(old_art.shining_seeds(table), [
			"d:/ymir work/item/wing/2022_march_shiva1_col1.mse",
			"d:/ymir work/effect/mehok/22/wing.mse",
			"d:/ymir work/item/wing/a.mse",
			"d:/ymir work/item/wing/space.mse"])

	MSM = (b'Group WingData\n{\n\tPathName\t"d:/ymir Work/pc/warrior/"\n\n\tWingDataCount\t\t\t3\n'
		b'\tGroup WingData00\n\t{\n\t\tWingIndex\t\t\t48376\n\t\tModel\t\t\t\t"wing/2021august_shiva_coat.gr2"\n'
		b'\t\tCustomSpecular\t\t1\n\t\tSourceSkin\t\t\t"d:/ymir work/pc/common/090177_JinM_col1_D.dds"\n'
		b'\t\tCommonTargetSkin\t"d:/ymir work/pc/common/090177_JinM_col1_D_1.dds"\n\t}\n'
		b'\tGroup WingData01\n\t{\n\t\tWingIndex\t\t\t48399\n\t\tModel\t\t\t\t"wing/other.gr2"\n\t}\n'
		b'\tGroup WingData02\n\t{\n\t\tSpecialPath\t\t\t"d:/ymir work/pc2/warrior/"\n\t\tWingIndex\t\t\t48380\n'
		b'\t\tModel\t\t\t\t"Wing/Coat.gr2"\n\t\tSourceSkin2\t\t\t"a.dds"\n\t\tCommonTargetSkin2\t"d:/ymir work/pc2/b.dds"\n\t}\n'
		b'}\nGroup ShapeData\n{\n\tPathName\t"d:/ymir Work/pc/warrior/"\n\tModel\t"x.gr2"\n}\n')

	def test_the_shapes_of_the_cuts_wings_their_models_and_their_skins(self):
		self.assertEqual(old_art.wing_shape_seeds([self.MSM], {48376, 48380, 8}), [
			"d:/ymir work/pc/warrior/wing/2021august_shiva_coat.gr2",
			"d:/ymir work/pc/common/090177_jinm_col1_d_1.dds",
			"d:/ymir work/pc2/warrior/wing/coat.gr2",
			"d:/ymir work/pc2/b.dds"])

	def test_a_special_path_holds_for_the_shapes_after_it_as_olds_loader_reads_it(self):
		msm = self.MSM.replace(b"WingDataCount\t\t\t3", b"WingDataCount\t\t\t4").replace(
			b"\n}\nGroup ShapeData", b'\n\tGroup WingData03\n\t{\n\t\tWingIndex\t8\n\t\tModel\t"wing/late.gr2"\n\t}\n}\nGroup ShapeData')
		self.assertEqual(old_art.wing_shape_seeds([msm], {8}), ["d:/ymir work/pc2/warrior/wing/late.gr2"])


class ManifestMerge(unittest.TestCase):

	def test_a_run_adds_its_rows_to_the_manifests(self):
		kept = [("d:/b.gr2", "item/b.gr2", "source/b.gr2", "copied")]
		added = [("d:/a.dds", "item/a.dds", "source/a.dds", "copied"),
			("d:/b.gr2", "item/b2.gr2", "source/b2.gr2", "converted")]
		self.assertEqual(old_art.merge_rows(kept, added), [
			("d:/a.dds", "item/a.dds", "source/a.dds", "copied"),
			("d:/b.gr2", "item/b.gr2", "source/b.gr2", "copied")])


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


class ShopSeeds(unittest.TestCase):
	"""The offline shop's decoration (NOVA-170): the NPC models of
	shop_deco.txt's type 1 rows, by the folder NEW's npclist names for each
	vnum, and the eight parts of each type 2 row's sign pattern."""

	DECO = (b"1\tDefault\t30000\n1\tBBQ King\t30003\n"
		b"2\tInferno\td:/ymir work/ui/pattern/myshop/fire/p_fire\t0xFF976D\n")
	NPCLIST = b"30000\tprivateshop\t\n30003\tprivateshop_2\t\n"

	def setUp(self):
		self.packer = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, self.packer)
		folder = os.path.join(self.packer, "source", "npc2", "privateshop_2")
		os.makedirs(folder)
		with open(os.path.join(folder, "privateshop_2.msm"), "wb") as handle:
			handle.write(b'ScriptType RaceDataScript\r\nBaseModelFileName "D:\\Ymir Work\\npc2\\privateshop_2\\privateshop_2.GR2"\r\n'
				b'Group AttachingData\r\n{\r\n    Group AttachingData00\r\n    {\r\n        AttachingDataType    2\r\n'
				b'        EffectScriptName     "D:\\Ymir Work\\effect\\npc2\\p_shop_02.mse"\r\n    }\r\n}\r\n')
		with open(os.path.join(folder, "motlist.txt"), "wb") as handle:
			handle.write(b"GENERAL WAIT wait.msa 100")
		self.index = {
			"d:/ymir work/npc2/privateshop_2/privateshop_2.msm":
				("d:/ymir work/npc2/privateshop_2/privateshop_2.msm", "source/npc2/privateshop_2/privateshop_2.msm"),
			"d:/ymir work/npc2/privateshop_2/motlist.txt":
				("d:/ymir work/npc2/privateshop_2/motlist.txt", "source/npc2/privateshop_2/motlist.txt"),
		}

	def test_each_models_script_base_model_motions_and_each_patterns_parts(self):
		files = {"d:/ymir work/npc2/privateshop/privateshop.msm"}
		got = old_art.shop_seeds(self.DECO, self.NPCLIST, self.index, self.packer, files)
		self.assertEqual(got, [
			"d:/ymir work/npc2/privateshop_2/privateshop_2.msm",
			"d:/ymir work/effect/npc2/p_shop_02.mse",
			"d:/ymir work/npc2/privateshop_2/motlist.txt",
			"d:/ymir work/npc2/privateshop_2/privateshop_2.gr2",
			"d:/ymir work/npc2/privateshop_2/wait.msa"] + [
			"d:/ymir work/ui/pattern/myshop/fire/p_fire_%s.tga" % part for part in old_art.PATTERN_PARTS])

	def test_a_model_new_already_ships_is_left_but_not_its_effects(self):
		"""r31 live: NEW had OLD's shop models but not the effects their msm
		attach (CEffectManager::RegisterEffect p_shop_04.mse Error)."""
		files = {"d:/ymir work/npc2/privateshop_2/privateshop_2.msm"}
		got = old_art.shop_seeds(self.DECO, self.NPCLIST, self.index, self.packer, files)
		self.assertFalse([path for path in got if "/npc2/privateshop" in path])
		self.assertIn("d:/ymir work/effect/npc2/p_shop_02.mse", got)

	def test_an_effect_new_ships_is_left(self):
		files = {"d:/ymir work/npc2/privateshop_2/privateshop_2.msm", "d:/ymir work/effect/npc2/p_shop_02.mse"}
		got = old_art.shop_seeds(self.DECO, self.NPCLIST, self.index, self.packer, files)
		self.assertNotIn("d:/ymir work/effect/npc2/p_shop_02.mse", got)

	def test_a_model_new_ships_in_another_npc_folder_is_left(self):
		"""NEW has 30000's privateshop in npc2, OLD in npc and npc2 both."""
		self.index["d:/ymir work/npc/privateshop/privateshop.msm"] = (
			"d:/ymir work/npc/privateshop/privateshop.msm", "source/npc2/privateshop_2/privateshop_2.msm")
		files = {"d:/ymir work/npc2/privateshop/privateshop.msm"}
		got = old_art.shop_seeds(self.DECO, self.NPCLIST, self.index, self.packer, files)
		self.assertFalse([path for path in got if "/privateshop/" in path])

	def test_a_numbered_model_goes_with_the_group_of_its_base_folder(self):
		folders = {"d:/ymir work/npc2": {"metin2_patch_xmas": 90, "npc2": 40},
			"d:/ymir work/npc2/privateshop": {"npc2": 7}, "d:/ymir work/ui/pattern": {"ETC": 30}}
		self.assertEqual(old_art.shop_group("d:/ymir work/npc2/privateshop_3/wait.gr2", folders), "npc2")
		self.assertEqual(old_art.shop_group("d:/ymir work/ui/pattern/myshop/ice/p_ice_top.tga", folders), "ETC")


class RingSeeds(unittest.TestCase):
	"""NOVA-127: OLD's select and target rings (OLD playerSettingModule.py:
	295-302), each of the three empires and the monsters'."""

	def test_the_eight_rings_of_olds_registrations(self):
		self.assertEqual(sorted(old_art.RINGS), sorted(
			"d:/ymir work/effect/world/%s_%sselect.mse" % (who, glow)
			for who in ("shinsoo", "chunjo", "jinnos", "mob") for glow in ("", "glow_")))

	def test_a_ring_new_ships_is_left(self):
		files = {"d:/ymir work/effect/world/mob_select.mse"}
		got = old_art.ring_seeds(files)
		self.assertNotIn("d:/ymir work/effect/world/mob_select.mse", got)
		self.assertEqual(len(got), 7)

	def test_a_blob_is_read_from_gits_tree(self):
		"""The rings' scripts are read where the sparse worktree has no file."""
		data = old_art.git_blob("assets/groups.txt")
		self.assertIn(b"root", data)


class TreeGroups(unittest.TestCase):
	"""A sparse worktree has only some groups on disk: the shop's art takes
	its groups and NEW's files from git's tree (old_art.tree_files)."""

	def test_the_tree_decides_the_group_where_the_disk_has_no_folder(self):
		paths = ["assets/npc2/ymir work/npc2/privateshop/privateshop.msm",
			"assets/ETC/ymir work/ui/pattern/board_base.tga", "assets/icon/icon/item/1.tga"]
		folders = old_art.tree_group_folders(paths, ["npc2", "ETC", "icon"])
		self.assertEqual(old_art.choose_group("d:/ymir work/npc2/privateshop_1/wait.gr2", folders), "npc2")
		self.assertEqual(old_art.choose_group("d:/ymir work/ui/pattern/myshop/fire/p_fire_top.tga", folders), "ETC")
		self.assertEqual(old_art.tree_published(paths, ["npc2", "ETC", "icon"]), {
			"d:/ymir work/npc2/privateshop/privateshop.msm", "d:/ymir work/ui/pattern/board_base.tga", "icon/item/1.tga"})


class NamedFiles(unittest.TestCase):
	"""files and files-plan (NOVA-110): store paths named on the command
	line, by default the chat's empire flags."""

	def test_the_names_new_lacks_are_seeds_once_and_in_order(self):
		files = {"d:/ymir work/ui/flags/empire_20x15/empire_2.png"}
		got = old_art.files_seeds(["D:/Ymir Work/UI/flags/empire_20x15/empire_1.png",
			"d:/ymir work/ui/flags/empire_20x15/empire_2.png", "d:/ymir work/ui/flags/empire_20x15/empire_1.png"], files)
		self.assertEqual(got, ["d:/ymir work/ui/flags/empire_20x15/empire_1.png"])

	def test_the_default_names_are_olds_three_shout_flags(self):
		"""OLD PythonChat.cpp:578: empire_<bEmpire>.png for the empires 1 to 3."""
		self.assertEqual(old_art.CHAT_FLAGS, tuple(
			"d:/ymir work/ui/flags/empire_20x15/empire_%d.png" % empire for empire in (1, 2, 3)))

	def test_the_language_flags_are_olds_for_the_seventeen_locales(self):
		"""OLD PythonChat.cpp:574: flags_20x15/<language>.png (NOVA-51), for
		the login screen's 17 locales (language_packets.h's codes)."""
		codes = ("en", "ae", "br", "cz", "de", "dk", "es", "fr", "gr", "hu", "it", "nl", "pl", "pt", "ro", "ru", "tr")
		self.assertEqual(old_art.CHAT_LANGUAGE_FLAGS, tuple(
			"d:/ymir work/ui/flags/flags_20x15/%s.png" % code for code in codes))

	def test_with_no_names_files_takes_both_kinds_of_chat_flag(self):
		self.assertEqual(old_art.default_files(), list(old_art.CHAT_FLAGS + old_art.CHAT_LANGUAGE_FLAGS))


class ShiningSeeds(unittest.TestCase):
	"""shining and shining-plan (NOVA-176): the effects NEW's shining table
	names that NEW does not publish."""

	def test_the_tables_effects_new_lacks_once_without_bones_or_quotes(self):
		table = (b"12010~12049\tD:/ymir work/pc/common/effect/armor/armor-4-2-1.mse\t\t\n"
			b"41971\tD:/ymir work/effect/hallowen_costume/body.mse\tD:/ymir work/effect/hallowen_costume/hand.mse#Bip01 L UpperArm"
			b"\tD:/ymir work/effect/hallowen_costume/hand.mse#Bip01 R UpperArm\n"
			b"42819\t\"d:/ymir work/effect/mehok/dragon_wind/armor.mse\"\n")
		files = {"d:/ymir work/pc/common/effect/armor/armor-4-2-1.mse"}
		self.assertEqual(old_art.shining_table_seeds(table, files), [
			"d:/ymir work/effect/hallowen_costume/body.mse",
			"d:/ymir work/effect/hallowen_costume/hand.mse",
			"d:/ymir work/effect/mehok/dragon_wind/armor.mse"])


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

	def test_the_chat_flags_are_taken(self):
		taken = {row[0] for row in self.rows}
		self.assertEqual([path for path in old_art.CHAT_FLAGS if path not in taken], [])

	def test_the_chat_language_flags_are_taken(self):
		taken = {row[0] for row in self.rows}
		self.assertEqual([path for path in old_art.CHAT_LANGUAGE_FLAGS if path not in taken], [])

	def test_the_shining_tables_effects_are_taken_or_were_shipped(self):
		"""NOVA-176: every effect of NEW's table is in the manifest or was in
		NEW before the wave's art."""
		taken = {row[0] for row in self.rows}
		with open(old_art.SHINING_TABLE, "rb") as handle:
			effects = old_art.shining_seeds(handle.read())
		self.assertIn("d:/ymir work/effect/hallowen_costume/body.mse", taken)
		self.assertEqual([path for path in effects if path.startswith("d:/ymir work/effect/hallowen_costume/") and path not in taken], [])

	def test_the_waves_extra_files_are_taken(self):
		taken = {row[0] for row in self.rows}
		self.assertEqual([path for path in old_art.EXTRA if path not in taken], [])


if __name__ == "__main__":
	unittest.main()
