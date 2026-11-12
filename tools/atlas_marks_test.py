"""NOVA-129: the boss and metin stone marks on the atlas, in both atlas
windows (assets/root/uiminimap.py's AtlasWindow and nui_atlas.AtlasWindow).
Run from tools/:

	python3 -B -m unittest atlas_marks_test

C++ draws the marks into the atlas and hits them in miniMap.GetAtlasInfo
(CPythonMiniMap, src/UserInterface/AtlasBossMarks.h); a hit mark's lines
(kind and level, state, respawn time) come from miniMap.GetAtlasMarkHover,
in the strings each atlas window hands C++ at LoadWindow
(miniMap.SetAtlasMarkTexts). The legacy window shows them under its name
line, one text line each; NovaUI's view label gets them from C++
(NuiViews.cpp), so its facade only hands over the strings.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from legacy_foundation_test import locales, run_localeinfo  # noqa: E402
from nui_world_test import MAP_A1, pair, quiet  # noqa: E402

# The strings, by the key C++ reads (PythonMiniMapModule.cpp
# miniMapSetAtlasMarkTexts): the localeInfo stand-in answers each name.
TEXTS = {"boss": "ATLAS_MARK_BOSS", "king": "ATLAS_MARK_KING", "stone": "ATLAS_MARK_STONE", "level": "BOSS_INFO_LEVEL",
         "alive": "BOSS_INFO_ALIVE", "dead": "BOSS_INFO_DEAD", "respawn_in": "BOSS_INFO_RESPAWN",
         "period": "ATLAS_MARK_RESPAWN_TIME"}
NEW_KEYS = ("ATLAS_MARK_BOSS", "ATLAS_MARK_KING", "ATLAS_MARK_STONE", "ATLAS_MARK_RESPAWN_TIME")


def worlds(setup=None):
	def answers(game):
		game.answer("miniMap", "IsAtlas", 1)
		game.answer("miniMap", "GetAtlasSize", (1, 256, 256))
		if setup:
			setup(game)
	legacy, novaui = pair(setup=answers)
	for world in (legacy, novaui):
		with world, quiet():
			minimap = world.module("nui_windows").make("minimap", world.module("uiMiniMap").MiniMap, "nui_minimap.MiniMap")
			minimap.Show()
			minimap.ShowMiniMap()
			minimap.SetMapName(MAP_A1)
		world.minimap = minimap
	return legacy, novaui


class MarkTexts(unittest.TestCase):
	def test_both_atlases_hand_cplusplus_the_mark_strings_once(self):
		for world in worlds():
			calls = [args for name, args in world.game.log if name == "miniMap.SetAtlasMarkTexts"]
			self.assertEqual(calls, [(TEXTS,)], "NovaUI" if world.nui_on else "legacy")

	def test_an_exe_without_marks_loads_both_atlases(self):
		def older(game):
			game.modules["miniMap"].lack("SetAtlasMarkTexts", "GetAtlasMarkHover")
		for world in worlds(older):
			self.assertEqual([name for name, _ in world.game.log if "AtlasMark" in name], [])
			self.assertEqual(type(world.minimap.AtlasWindow).__module__, "nui_atlas" if world.nui_on else "uiMiniMap")

	def test_every_locale_has_the_mark_strings(self):
		for locale in locales():
			namespace, _, errors = run_localeinfo(locale)
			self.assertEqual([], errors, locale)
			for key in set(TEXTS.values()):
				self.assertTrue(namespace.get(key), "%s lacks %s" % (locale, key))
			for key in ("BOSS_INFO_LEVEL",):
				self.assertIn("%d", namespace[key], locale)
			for key in ("BOSS_INFO_RESPAWN", "ATLAS_MARK_RESPAWN_TIME"):
				self.assertEqual(namespace[key].count("%s"), 1, "%s %s" % (locale, key))


def last_position(widget):
	"""The place the widget's last SetPosition gave it."""
	return [call[1:] for call in widget.calls if call[0] == "SetPosition"][-1]


class LegacyHover(unittest.TestCase):
	"""uiMiniMap.AtlasWindow.OnUpdate: the name line, then a mark's lines."""

	def hover(self, detail, older=False):
		def setup(game):
			game.answer("miniMap", "GetAtlasInfo", (1, "Lord Ahn", 64, 128, 0xFFFF4A3D, 0))
			if older:
				game.modules["miniMap"].lack("GetAtlasMarkHover")
			else:
				game.answer("miniMap", "GetAtlasMarkHover", detail)
			game.modules["wndMgr"].GetMousePosition = lambda: (100, 100)
		legacy, _ = worlds(setup)
		atlas = legacy.minimap.AtlasWindow
		atlas.board.IsIn = lambda: True
		with legacy, quiet():
			atlas.OnUpdate()
		tip = atlas.tooltipInfo
		lines = [tip.textLine] + [line for line in tip.extraLines if line.IsShow()]
		return [line.text for line in lines], [last_position(line) for line in lines]

	def test_a_marks_lines_go_under_the_name_line(self):
		texts, places = self.hover("Boss, Level 75\nRespawning in 4:05\nRespawn time: 20:00")
		self.assertEqual(texts, ["Lord Ahn(64, 128)", "Boss, Level 75", "Respawning in 4:05", "Respawn time: 20:00"])
		self.assertEqual([y for _, y in places], [100, 116, 132, 148], "one line under the other, 16 px apart")
		self.assertEqual(len(set(x for x, _ in places)), 1, "right-aligned at the same x")

	def test_anything_else_keeps_one_line(self):
		texts, _ = self.hover("Boss, Level 75\nAlive")
		texts, _ = self.hover("")
		self.assertEqual(texts, ["Lord Ahn(64, 128)"])

	def test_an_exe_without_marks_keeps_one_line(self):
		texts, _ = self.hover("", older=True)
		self.assertEqual(texts, ["Lord Ahn(64, 128)"])

	def test_the_tooltip_hides_lines_a_shorter_text_does_not_use(self):
		tip_cls = None
		legacy, _ = worlds()
		with legacy, quiet():
			tip_cls = legacy.module("uiMiniMap").MapTextToolTip
			tip = tip_cls()
			tip.SetText("a\nb\nc")
			self.assertEqual([line.IsShow() for line in tip.extraLines], [True, True])
			tip.SetText("a\nb")
			self.assertEqual([line.IsShow() for line in tip.extraLines], [True, False])
			self.assertEqual(tip.extraLines[0].text, "b")
			tip.SetTooltipPosition(50, 20)
			self.assertEqual(last_position(tip.textLine), (45, 20))
			self.assertEqual(last_position(tip.extraLines[0]), (45, 36))


if __name__ == "__main__":
	unittest.main()
