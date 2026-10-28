"""Headless tests of the legacy minimap's map names (NOVA-90; S8-D2 of the
stage B live run): assets/root/uiminimap.py's MiniMap and its AtlasWindow,
made over nui_game_support's stand-ins with a locale's real
localeInfo.MINIMAP_ZONE_NAME_DICT (localeinfo.py run whole). Run from tools/:

	python3 -B -m unittest legacy_minimap_test

C++ calls game.py's ShowMapName with the name of the atlasinfo.txt entry
whose area holds the warp position (CPythonBackground::Warp and
GlobalPositionToMapInfo), and the Interface passes it on to
MiniMap.SetMapName, which titles the atlas and then shows or hides the
minimap. A name the dict lacked raised KeyError in AtlasWindow.SetMapName
(NEW dropped OLD's try/except, uiMiniMap.py:97-101, in 833c9098): the guild
war map logged a traceback at each entry and revive, and the minimap was
never shown or hidden there.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
from legacy_foundation_test import REPO, ROOT, locales, quiet, read, run_localeinfo  # noqa: E402

RUNTIME_MAPS = os.path.join(REPO, "tools", "fixtures", "runtime_maps.json")
DARK_MAP = "metin2_map_monkeydungeon"   # in MiniMap.CANNOT_SEE_INFO_MAP_DICT
NAMED_MAP = "metin2_map_a1"
# Runtime map 200: no locale names it, OLD's or NEW's.
UNNAMED_MAP = "gm_guild_build"
# CTerrainImpl::TERRAIN_XSIZE and TERRAIN_YSIZE (128 cells of CELLSCALE 200).
TERRAIN_SIZE = 128 * 200


def atlas_areas():
	"""assets/root/atlasinfo.txt as CMapManager::__LoadMapInfoVector reads
	it: (name, x, y, end x, end y) per line of five fields, in file order."""
	areas = []
	for line in read(os.path.join(ROOT, "atlasinfo.txt")).split("\n"):
		fields = line.split()
		if len(fields) < 5:
			continue
		x, y, width, height = (int(field) for field in fields[1:5])
		areas.append((fields[0], x, y, x + width * TERRAIN_SIZE, y + height * TERRAIN_SIZE))
	return areas


def client_map_name(areas, x, y):
	"""The name C++ hands ShowMapName for a warp to (x, y): the first atlas
	area that holds it (FFindWarpMapName), None for none."""
	for name, left, top, right, bottom in areas:
		if left <= x < right and top <= y < bottom:
			return name
	return None


def runtime_maps():
	with open(RUNTIME_MAPS, encoding="utf-8") as handle:
		return json.load(handle)["maps"]


class MapNames(unittest.TestCase):
	"""MiniMap.SetMapName for the map names C++ sends: every map the server
	runs shows the minimap or hides it, and titles the atlas with the map's
	name or keeps the title it has, as OLD did."""

	def setUp(self):
		game = self.game = support.Game()
		game.modules["systemSetting"].GetUINuiWindows = lambda: ""
		support.install_wave2b_ui(game)
		game.load_standard()
		self.use_locale("en")
		with quiet():
			game.load("colorInfo", "colorinfo.py")
			game.load("uiMiniMap", "uiminimap.py")
		game.__enter__()
		self.addCleanup(game.__exit__, None, None, None)
		with quiet():
			minimap = self.minimap = game.loaded["uiMiniMap"].MiniMap()
			# Interface.ShowDefaultWindows, then the map C++ names at login.
			minimap.Show()
			minimap.ShowMiniMap()
			minimap.SetMapName(NAMED_MAP)

	def use_locale(self, locale):
		namespace, _, errors = run_localeinfo(locale)
		self.assertEqual([], errors, locale)
		self.names = namespace["MINIMAP_ZONE_NAME_DICT"]
		self.game.modules["localeInfo"].MINIMAP_ZONE_NAME_DICT = self.names

	def enter(self, map_name):
		"""MiniMap.SetMapName(map_name), as interfaceModule.SetMapName calls
		it: (the miniMap shows and hides it made, the atlas titles it set)."""
		board = self.minimap.AtlasWindow.board
		log, calls = len(self.game.log), len(board.calls)
		self.minimap.SetMapName(map_name)
		return ([name for name, _ in self.game.log[log:] if name in ("miniMap.Show", "miniMap.Hide")],
		        [call[1] for call in board.calls[calls:] if call[0] == "SetTitleName"])

	def state(self):
		minimap = self.minimap
		return {"can_see": minimap.canSeeInfo, "open": minimap.OpenWindow.shown, "closed": minimap.CloseWindow.shown,
		        "tooltip": minimap.tooltipMiniMapOpen.textLine.text}

	def test_a_map_the_dict_lacks_shows_the_minimap_and_keeps_the_title(self):
		"""From a dungeon that hides the minimap to a map no locale names:
		the minimap shows again and the atlas keeps the title it had."""
		locale_info = self.game.modules["localeInfo"]
		self.assertNotIn(UNNAMED_MAP, self.names)
		self.assertEqual((["miniMap.Hide"], [self.names[DARK_MAP]]), self.enter(DARK_MAP))
		self.assertEqual((["miniMap.Show"], []), self.enter(UNNAMED_MAP))
		self.assertEqual({"can_see": True, "open": True, "closed": False, "tooltip": locale_info.MINIMAP}, self.state())
		self.assertEqual(UNNAMED_MAP, self.minimap.mapName)

	def test_a_dark_map_the_dict_lacks_hides_the_minimap(self):
		locale_info = self.game.modules["localeInfo"]
		self.minimap.CANNOT_SEE_INFO_MAP_DICT = dict(self.minimap.CANNOT_SEE_INFO_MAP_DICT, **{UNNAMED_MAP: False})
		self.assertEqual((["miniMap.Hide"], []), self.enter(UNNAMED_MAP))
		self.assertEqual({"can_see": False, "open": False, "closed": True, "tooltip": locale_info.MINIMAP_CANNOT_SEE},
		                 self.state())

	def test_every_runtime_map_shows_its_name_or_keeps_the_title(self):
		"""Each map of the server runtime's map index, by the name the client
		gives its base position, in every locale. OLD's locales name the guild
		war maps (MAP_T1-T4), the kingdom battle maps (MAP_SUNGZI_*) and the
		castle maps (MAP_EMPIREWAR01-03) though OLD's dict left them out; NEW's
		have the same keys. No locale names gm_guild_build, so its atlas keeps
		the title it had, as OLD's did."""
		areas = atlas_areas()
		maps = runtime_maps()
		self.assertEqual(66, len(maps))
		unreachable = sorted(name for _, name, x, y in maps if client_map_name(areas, x, y) is None)
		self.assertEqual(["metin2_map_fielddungeon", "metin2_map_resources_zon"], unreachable,
		                 "no atlas area: the client can't warp there at all (NOT_FOUND_GLOBAL_POSITION)")
		for locale in locales():
			self.use_locale(locale)
			untitled = []
			for index, name, x, y in maps:
				client_name = client_map_name(areas, x, y)
				if client_name is None:
					continue
				with self.subTest(locale=locale, map=index, name=client_name):
					shows, titles = self.enter(client_name)
					self.assertEqual(["miniMap.Hide" if client_name in self.minimap.CANNOT_SEE_INFO_MAP_DICT
					                  else "miniMap.Show"], shows)
					if client_name in self.names:
						self.assertTrue(self.names[client_name].strip())
						self.assertEqual([self.names[client_name]], titles)
					else:
						self.assertEqual([], titles)
						untitled.append(name)
			with self.subTest(locale=locale):
				self.assertEqual([UNNAMED_MAP], untitled)


if __name__ == "__main__":
	unittest.main()
