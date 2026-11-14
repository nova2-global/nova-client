"""NOVA-263: opening the wiki and showing the select skill window's preview each took one 33 ms
frame in r48 (.nui-work/w10/runs/r48/wiki/slowframes.txt):

- the wiki's open loaded wiki.rml (8.3 to 10.5 ms). Its board is now kept, hidden and emptied,
  from the window's making on (nui_hud.KeptBoard with keep_probe: the probe that making runs
  anyway loads it, during the phase change), so no open loads it again;
- the select skill window made its preview's model inside the open (11.2 ms, 10.7 of them loading
  its armor and weapon) and loaded select-skill.rml (6.0 ms). Its model is now made off the frame
  (modelpreview.SetBackground) behind a plain ring that fades the model in, and its board is kept
  from the window's making for a character that has not chosen its skill group yet.

Run from tools/: python3 -B -m unittest nui_wiki_open_frame_test"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_game_support as support  # noqa: E402
import nui_select_skill_test as sst  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import nui_wiki_test as wiki_base  # noqa: E402

ROOT = os.path.dirname(HERE)
SELECT_SKILL_DIR = os.path.join(ROOT, "assets", "nui", "nui", "windows", "select-skill")
PREVIEW = "select_skill"
EYE = ("SetEye", PREVIEW, -1200, 600)


# --- the wiki: its board is kept from the window's making --------------------------------------

class WikiKeptBoard(wiki_base.WikiTest):
	def test_the_window_s_making_keeps_its_board_hidden_and_empty(self):
		world, window = self.world()
		kept = window.demand.kept()
		self.assertIsNotNone(kept, "the probe's board is kept")
		self.assertTrue(kept._doc)
		self.assertFalse(kept.is_visible())
		self.assertIsNone(w4.board(window), "nothing shows before the open")

	def test_the_open_shows_the_kept_board_and_loads_no_document(self):
		world, window = self.world()
		kept = window.demand.kept()
		with world.game, w4.quiet():
			window.Open()
			window.search("sword")
		self.assertIs(w4.board(window), kept, "the open loads no document")
		self.assertTrue(kept.model["list"], "the state is set on it")
		self.assertTrue(kept.model["tabs"])

	def test_a_close_keeps_it_emptied_with_no_clock_and_no_view(self):
		world, window = self.world()
		kept = window.demand.kept()
		with world.game, w4.quiet():
			window.Open()
			window.search("sword")
			window.OpenMob(8002)
			window.Close()
		self.assertIs(window.demand.kept(), kept)
		self.assertFalse(kept.is_visible())
		for key in ("tree", "list", "quick", "recent", "tabs", "crumbs", "menu", "classes", "origins", "chest",
		            "refine", "drops", "tp_blocks", "tp_decor", "tp_view"):
			self.assertEqual(kept.model[key], [], key)
		for key in ("model_view", "hover_view", "viewer"):
			self.assertFalse(kept.model[key], key)
		for key in ("retry_at", "timeout_at", "preview_check_at", "tp_open_at"):
			self.assertEqual(kept.model[key], 0.0, key)

	def test_a_reopen_shows_what_the_window_held(self):
		world, window = self.world()
		with world.game, w4.quiet():
			window.Open()
			window.search("sword")
			window.Close()
			window.Open()
		self.assertEqual([r["vnum"] for r in w4.board(window).model["list"]], [wiki_base.SWORD])

	def test_destroy_unloads_it(self):
		world, window = self.world()
		kept = window.demand.kept()
		with world.game, w4.quiet():
			window.Destroy()
		self.assertFalse(kept._doc)

	def test_without_the_flag_the_first_open_loads_it(self):
		world, window = self.world()
		module = world.m("nui_wiki")
		saved = module.KEEP_BOARD_FROM_PROBE
		module.KEEP_BOARD_FROM_PROBE = False
		try:
			with world.game, w4.quiet():
				other = world.nui_windows.make("wiki", type("Unused", (), {}), "nui_wiki.WikiWindow")
		finally:
			module.KEEP_BOARD_FROM_PROBE = saved
		self.assertIsNone(other.demand.kept())
		self.assertFalse(other.demand.loaded())


# --- the select skill window: its preview made off the frame, its board kept --------------------

class BackgroundPreview(sst.Preview):
	"""modelpreview with background previews (NOVA-256): a background preview's Select answers at
	once and its model waits; step() is one client step that makes it. GetState says pending."""

	def __init__(self):
		sst.Preview.__init__(self)
		self.background = set()
		self.waiting = set()
		self.models = {}

	def SetBackground(self, name, on):
		self.calls.append(("SetBackground", name, bool(on)))
		(self.background.add if on else self.background.discard)(name)

	def Select(self, name, race, *gear):
		sst.Preview.Select(self, name, race, *gear)
		if self.models.get(name) == (race,) + gear:
			self.waiting.discard(name)
		elif name in self.background:
			self.waiting.add(name)
			self.models.pop(name, None)
		else:
			self.models[name] = (race,) + gear
		return 1

	def step(self, name=PREVIEW):
		self.waiting.discard(name)
		self.models[name] = True

	def GetState(self, name):
		return {"pending": int(name in self.waiting), "has_model": int(name in self.models)}


class SelectSkillWorld(sst.World):
	def __init__(self, nui_on, group=0, **kwargs):
		self.group = group
		sst.World.__init__(self, nui_on, **kwargs)
		self.preview = BackgroundPreview()
		self.game.modules["modelpreview"] = self.preview
		support.define(self.game.modules["net"], "GetMainActorSkillGroup", lambda: self.group)


class SelectSkill(unittest.TestCase):
	def opened(self, nui_on=True, **kwargs):
		world = SelectSkillWorld(nui_on, **kwargs)
		window = world.window()
		with world.game, w4.quiet():
			window.Open()
		return world, window

	def model(self, window):
		return w4.board(window).model

	def check(self, world, window):
		with world.game, w4.quiet():
			w4.fire(window, "preview_check")

	def test_the_novaui_window_asks_for_its_model_off_the_frame(self):
		world, window = self.opened()
		calls = world.preview.calls
		self.assertIn(("SetBackground", PREVIEW, True), calls)
		self.assertLess(calls.index(("SetBackground", PREVIEW, True)),
		                [i for i, c in enumerate(calls) if c[0] == "Select"][0], "before its Select")
		self.assertTrue(self.model(window)["model_view"])
		self.assertTrue(self.model(window)["preview_loading"], "a plain ring while the model is made")
		self.assertGreater(self.model(window)["preview_check_at"], 0.0)

	def test_the_legacy_window_makes_it_as_before(self):
		world, window = self.opened(nui_on=False)
		self.assertFalse([c for c in world.preview.calls if c[0] == "SetBackground"])
		self.assertIn(("Select", PREVIEW, sst.RACE, 11289, 189, sst.HAIR_PART, sst.SASH_VNUM), world.preview.calls)

	def test_the_clock_before_the_model_keeps_it_plain(self):
		world, window = self.opened()
		self.check(world, window)
		self.assertTrue(self.model(window)["preview_loading"])
		self.assertGreater(self.model(window)["preview_check_at"], 0.0)

	def test_once_made_it_gets_its_camera_and_fades_in(self):
		world, window = self.opened()
		world.preview.step()
		mark = len(world.preview.calls)
		self.check(world, window)
		self.assertFalse(self.model(window)["preview_loading"])
		self.assertEqual(self.model(window)["preview_check_at"], 0.0)
		self.assertEqual(world.preview.calls[mark:], [EYE], "the request's end put the race's camera back")

	def test_a_skill_hovered_while_it_loads_is_cast_once_made(self):
		world, window = self.opened()
		with world.game, w4.quiet():
			sst.hover(window, True, 1, 2)
		world.preview.step()
		mark = len(world.preview.calls)
		self.check(world, window)
		self.assertEqual(world.preview.calls[mark:], [EYE, ("SetSkillMotion", PREVIEW, 3)])

	def test_a_reopen_with_the_same_gear_shows_the_model_at_once(self):
		world, window = self.opened()
		world.preview.step()
		self.check(world, window)
		with world.game, w4.quiet():
			window.Close()
			window.Open()
		self.assertFalse(self.model(window)["preview_loading"])
		self.assertEqual(self.model(window)["preview_check_at"], 0.0)

	def test_a_close_while_it_loads_and_a_reopen_watch_it_again(self):
		world, window = self.opened()
		with world.game, w4.quiet():
			window.Close()
			window.Open()
		self.assertTrue(self.model(window)["preview_loading"])
		self.assertGreater(self.model(window)["preview_check_at"], 0.0)

	def test_a_character_without_a_skill_group_keeps_the_board_from_the_window_s_making(self):
		world = SelectSkillWorld(True, group=0)
		window = world.window()
		kept = window.demand.kept()
		self.assertIsNotNone(kept)
		self.assertFalse(kept.is_visible())
		with world.game, w4.quiet():
			window.Open()
		self.assertIs(w4.board(window), kept, "the open loads no document")
		self.assertTrue(self.model(window)["groups"][0]["cells"])
		with world.game, w4.quiet():
			window.Close()
		self.assertIs(window.demand.kept(), kept)
		self.assertEqual([g["cells"] for g in kept.model["groups"]], [[], []])
		self.assertFalse(kept.model["model_view"])
		self.assertEqual(kept.model["preview_check_at"], 0.0)

	def test_a_character_with_a_skill_group_keeps_none(self):
		world = SelectSkillWorld(True, group=1)
		window = world.window()
		self.assertIsNone(window.demand.kept())
		self.assertFalse(window.demand.loaded())


class Markup(unittest.TestCase):
	def read(self, name):
		with open(os.path.join(SELECT_SKILL_DIR, name), encoding="utf-8") as handle:
			return handle.read()

	def test_the_view_is_clear_while_loading_and_animates(self):
		rml = self.read("select-skill.rml")
		tag = re.search(r'<nui-view[^>]*name="model-select-skill"[^>]*>', rml, re.S).group(0)
		self.assertIn('data-class-is-loading="preview_loading"', tag)
		self.assertIn("nui-anim", tag)
		self.assertRegex(rml, r'<nui-countdown[^>]*data-if="preview_check_at > 0"[^>]*data-attr-end="preview_check_at"'
		                      r'[^>]*data-event-countdownend="preview_check\(\)"')

	def test_the_fade_is_the_wiki_s(self):
		rcss = self.read("select-skill.rcss")
		self.assertIn("opacity: 0;", re.search(r"\.select-skill__view\.is-loading\s*\{([^}]*)\}", rcss).group(1))
		self.assertIn("transition: opacity 0.15s linear-in-out;",
		              re.search(r"\.select-skill__view\.nui-anim\s*\{([^}]*)\}", rcss).group(1))


if __name__ == "__main__":
	unittest.main()
