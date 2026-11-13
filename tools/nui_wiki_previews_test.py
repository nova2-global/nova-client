"""NOVA-259: the wiki's model previews no longer freeze the game while they
are made.

r46: an item on a player race other than the player's made the race's every
motion in one frame, 320 to 340 ms (35 GR2s, its 30 emotion motions among
them; .nui-work/w10/runs/r46/model-gaps/syserr.txt). r47: a costume on the
player's own race cost 21 ms of the frame that opened the wiki. The wiki's
three previews (the page's, the hover's and the viewer's) are now background
previews (modelpreview.SetBackground: the client reads their files on the
loader thread, parses one a step and makes one model a step) and wait-only
ones (modelpreview.SetWaitOnly: their models register the race's wait
motions only). An item is asked for in one Select with its look.

Eddy's standard (from the dungeon manager's "DT"): no text in place of a
model, ever. A preview whose model is being made stays plain (its view clear:
no text, no icon, no zoom mark), and the model fades in once made. The window
looks again at a hidden clock (preview_check_at), never per frame. Run from
tools/:

	python3 -B -m unittest nui_wiki_previews_test
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402
import nui_wiki_test as base  # noqa: E402

ASSETS = os.path.dirname(HERE)
WIKI_DIR = os.path.join(ASSETS, "assets", "nui", "nui", "windows", "wiki")
WOLF = 8002
KIMONO = 11918   # a costume body
PREVIEWS = ("wiki", "wiki_hover", "wiki_viewer")
LEFT = 0


class BackgroundPreviews(object):
	"""The client's modelpreview module with background and wait-only previews
	(PythonModelPreview.h), recording its calls. A background preview's
	Select answers 1 at once and waits unless its model is the one it has or
	the pool's; step() is one client step, which makes the first waiting
	shown preview's model. A race in `fail` makes no model; meshes says which
	parts of a made model draw."""

	def __init__(self):
		self.calls = []
		self.background = set()
		self.wait_only = set()
		self.models = {}     # name -> (race, look) of its model
		self.pool = []       # (race, look) of the models let go
		self.waiting = []    # names whose model waits, in the order asked
		self.asked = {}      # name -> (race, look) it waits for
		self.shown = {}
		self.fail = set()
		self.meshes = (1, 1, 1, 1)

	def SetBackground(self, name, on):
		self.calls.append(("SetBackground", name, bool(on)))
		(self.background.add if on else self.background.discard)(name)

	def SetWaitOnly(self, name, on):
		self.calls.append(("SetWaitOnly", name, bool(on)))
		(self.wait_only.add if on else self.wait_only.discard)(name)

	def SetDwell(self, name, ms):
		self.calls.append(("SetDwell", name, ms))

	def Select(self, name, race, *look):
		self.calls.append(("Select", name, race) + tuple(look))
		want = (race, tuple(look))
		if self.models.get(name) == want:
			# The model it has: at once, and a request that waited goes.
			if name in self.waiting:
				self.waiting.remove(name)
				self.asked.pop(name, None)
			return 1
		if want in self.pool:
			self.pool.remove(want)
			self._let_go(name)
			self.models[name] = want
			if name in self.waiting:
				self.waiting.remove(name)
			return 1
		if name in self.background:
			if name not in self.waiting:
				self.waiting.append(name)
			self.asked[name] = want
			return 1
		if race in self.fail:
			self.models.pop(name, None)
			return 0
		self._let_go(name)
		self.models[name] = want
		return 1

	def _let_go(self, name):
		if name in self.models:
			self.pool.insert(0, self.models.pop(name))

	def SetParts(self, name, *parts):
		self.calls.append(("SetParts", name) + tuple(parts))
		return 1

	def Show(self, name, show):
		self.calls.append(("Show", name, bool(show)))
		self.shown[name] = bool(show)

	def Clear(self, name):
		self.calls.append(("Clear", name))
		self._let_go(name)
		self.asked.pop(name, None)
		self.shown.pop(name, None)
		self.background.discard(name)
		self.wait_only.discard(name)
		if name in self.waiting:
			self.waiting.remove(name)

	def SetTurn(self, name, turning):
		pass

	def SetZoom(self, name, zoom):
		pass

	def SetRotation(self, name, degrees):
		pass

	def step(self):
		"""One client step: the name whose model was made (or failed), or None."""
		for name in self.waiting:
			if self.shown.get(name):
				self.waiting.remove(name)
				want = self.asked.pop(name)
				self._let_go(name)
				if want[0] not in self.fail:
					self.models[name] = want
				return name
		return None

	def GetState(self, name):
		pending = name in self.waiting
		made = name in self.models and not pending
		return {"shown": int(self.shown.get(name, False)), "has_model": int(made), "pending": int(pending),
		        "meshes": tuple(self.meshes) if made else (0, 0, 0, 0),
		        "wait_only": int(made and name in self.wait_only), "rotation": 0.0}


class WikiPreviews(base.WikiTest):
	def setUp(self):
		self.previews = BackgroundPreviews()

	def world(self):
		world, window = base.WikiTest.world(self)
		world.game.modules["modelpreview"] = self.previews
		world.game.answer("player", "GetRace", lambda: 1)  # the assassin: not race 0, which the base stand-in refused
		return world, window

	def opened(self):
		world, window = self.world()
		with world.game, w4.quiet():
			window.Open()
		return world, window

	def model(self, window):
		return w4.board(window).model

	def check(self, world, window):
		"""The preview_check_at clock's end, as the board's countdown sends it."""
		with world.game, w4.quiet():
			w4.fire(window, "preview_check")

	def as_costume_body(self, world):
		item = world.game.modules["item"]
		world.game.answer("item", "GetItemType", lambda: item.ITEM_TYPE_COSTUME)
		world.game.answer("item", "GetItemSubType", lambda: item.COSTUME_TYPE_BODY)

	def calls(self, name, what=None):
		return [c for c in self.previews.calls if c[1] == name and (what is None or c[0] == what)]


class EveryPreviewLoadsOffTheFrame(WikiPreviews):
	def test_the_page_s_preview_is_a_background_wait_only_one_set_before_its_select(self):
		world, window = self.opened()
		with world.game, w4.quiet():
			window.OpenMob(WOLF)
		names = [c[0] for c in self.calls("wiki")]
		self.assertIn(("SetBackground", "wiki", True), self.previews.calls)
		self.assertIn(("SetWaitOnly", "wiki", True), self.previews.calls)
		self.assertLess(names.index("SetBackground"), names.index("Select"))
		self.assertLess(names.index("SetWaitOnly"), names.index("Select"))

	def test_the_hover_and_the_viewer_are_too(self):
		world, window = self.opened()
		with world.game, w4.quiet():
			window.search("wolf")
			window.over_row(0)
		self.assertIn(("SetBackground", "wiki_hover", True), self.previews.calls)
		self.assertIn(("SetWaitOnly", "wiki_hover", True), self.previews.calls)
		self.assertTrue(self.calls("wiki_hover", "SetDwell"), "the hover keeps its dwell")
		with world.game, w4.quiet():
			window.out_row()
			window.OpenMob(WOLF)
		self.previews.step()
		self.check(world, window)
		with world.game, w4.quiet():
			w4.press(window, "preview_press", LEFT)
		self.assertTrue(self.model(window)["viewer"])
		self.assertIn(("SetBackground", "wiki_viewer", True), self.previews.calls)
		self.assertIn(("SetWaitOnly", "wiki_viewer", True), self.previews.calls)

	def test_an_item_is_asked_for_in_one_select_with_its_look(self):
		world, window = self.opened()
		with world.game, w4.quiet():
			window.open_item(base.SWORD)
		self.assertIn(("Select", "wiki", 1, 0, base.SWORD, 0, 0), self.previews.calls)
		self.assertFalse([c for c in self.previews.calls if c[0] == "SetParts"], "no bare race model, then its parts")

	def test_a_pet_is_its_race_alone(self):
		world, window = self.opened()
		data = world.m("nui_wiki_data")
		pet = sorted(data.COSTUME_PETS)[0]
		world.game.answer("item", "GetValue", lambda i: 34001 if i == 3 else 0)
		with world.game, w4.quiet():
			window.open_item(pet)
		self.assertIn(("Select", "wiki", 34001), self.previews.calls)

	def test_a_client_without_the_calls_makes_its_models_as_before(self):
		self.previews = OldPreviews()
		world, window = self.opened()
		with world.game, w4.quiet():
			window.OpenMob(WOLF)
		self.assertTrue(self.model(window)["model_view"])
		self.assertFalse(self.model(window)["model_loading"], "made inside Select: shown at once")
		self.assertEqual(self.model(window)["preview_check_at"], 0.0)


class OldPreviews(BackgroundPreviews):
	"""A client before NOVA-256 and NOVA-259: every model is made inside Select."""
	SetBackground = None
	SetWaitOnly = None


class APreviewStaysPlainThenFadesIn(WikiPreviews):
	def test_a_page_whose_model_is_being_made_shows_a_plain_box_and_runs_the_clock(self):
		world, window = self.opened()
		with world.game, w4.quiet():
			window.OpenMob(WOLF)
		model = self.model(window)
		self.assertTrue(model["model_view"], "the view is there, clear")
		self.assertTrue(model["model_loading"])
		self.assertGreater(model["preview_check_at"], 0.0, "the window looks again at the clock's end")
		self.assertIn(("Show", "wiki", True), self.previews.calls, "shown: the client makes a shown preview's model")

	def test_the_clock_s_end_before_the_model_keeps_it_plain_and_the_clock_running(self):
		world, window = self.opened()
		with world.game, w4.quiet():
			window.OpenMob(WOLF)
		self.check(world, window)
		self.assertTrue(self.model(window)["model_loading"])
		self.assertGreater(self.model(window)["preview_check_at"], 0.0)

	def test_once_made_the_model_fades_in_and_the_clock_stops(self):
		world, window = self.opened()
		with world.game, w4.quiet():
			window.OpenMob(WOLF)
		self.assertEqual(self.previews.step(), "wiki")
		self.check(world, window)
		model = self.model(window)
		self.assertTrue(model["model_view"])
		self.assertFalse(model["model_loading"])
		self.assertEqual(model["preview_check_at"], 0.0)

	def test_a_model_the_client_has_or_keeps_shows_at_once(self):
		world, window = self.opened()
		with world.game, w4.quiet():
			window.OpenMob(WOLF)
		self.previews.step()
		self.check(world, window)
		with world.game, w4.quiet():
			window.open_item(base.SWORD)
		self.previews.step()
		self.check(world, window)
		self.assertFalse(self.model(window)["model_loading"])
		with world.game, w4.quiet():
			window.OpenMob(WOLF)
		self.assertFalse(self.model(window)["model_loading"], "the pool's model: ready when shown")
		self.assertEqual(self.model(window)["preview_check_at"], 0.0)
		with world.game, w4.quiet():
			window.OpenMob(WOLF + 1)
			window.OpenMob(WOLF)
		self.assertFalse(self.model(window)["model_loading"], "the model it has; the other mob's request dropped")
		self.assertNotIn("wiki", self.previews.waiting)

	def test_no_zoom_and_no_viewer_while_the_model_is_being_made(self):
		world, window = self.opened()
		with world.game, w4.quiet():
			window.OpenMob(WOLF)
			w4.press(window, "preview_press", LEFT)
		self.assertFalse(self.model(window)["viewer"])
		self.assertFalse(self.calls("wiki_viewer", "Select"))

	def test_a_model_made_without_its_part_s_mesh_falls_back_to_the_icon(self):
		world, window = self.opened()
		self.as_costume_body(world)
		self.previews.meshes = (0, 1, 1, 0)
		with world.game, w4.quiet():
			window.open_item(KIMONO)
		self.assertTrue(self.model(window)["model_loading"])
		self.previews.step()
		self.check(world, window)
		model = self.model(window)
		self.assertFalse(model["model_view"], "the icon, as NOVA-177 shows it")
		self.assertFalse(model["model_loading"])
		self.assertNotEqual(model["page_icon"], "")
		self.assertEqual(self.calls("wiki", "Show")[-1], ("Show", "wiki", False))
		self.assertEqual(model["preview_check_at"], 0.0)

	def test_a_race_that_makes_no_model_falls_back_to_the_icon(self):
		world, window = self.opened()
		self.previews.fail.add(WOLF)
		with world.game, w4.quiet():
			window.OpenMob(WOLF)
		self.previews.step()
		self.check(world, window)
		self.assertFalse(self.model(window)["model_view"])

	def test_another_page_while_one_loads_watches_the_new_one_only(self):
		world, window = self.opened()
		with world.game, w4.quiet():
			window.OpenMob(WOLF)
			window.open_item(base.SWORD)
		self.assertTrue(self.model(window)["model_loading"])
		self.assertEqual(self.previews.asked["wiki"], (1, (0, base.SWORD, 0, 0)))
		self.previews.step()
		self.check(world, window)
		self.assertFalse(self.model(window)["model_loading"])
		self.assertEqual(self.model(window)["page_vnum"], base.SWORD)

	def test_a_hide_while_one_loads_stops_the_clock(self):
		world, window = self.opened()
		with world.game, w4.quiet():
			window.OpenMob(WOLF)
			window.Hide()
		self.assertEqual(window._waiting, {})
		with world.game, w4.quiet():
			window.Open()
		self.assertTrue(self.model(window)["model_loading"], "shown again, the page asks again")
		self.previews.step()
		self.check(world, window)
		self.assertFalse(self.model(window)["model_loading"])


class TheHoverAndTheViewer(WikiPreviews):
	def hovered(self):
		world, window = self.opened()
		with world.game, w4.quiet():
			window.search("wolf")
			window.over_row(0)
		return world, window

	def test_a_hover_box_stays_plain_until_its_model_is_made(self):
		world, window = self.hovered()
		self.assertTrue(self.model(window)["hover_view"])
		self.assertTrue(self.model(window)["hover_loading"])
		self.previews.step()
		self.check(world, window)
		self.assertTrue(self.model(window)["hover_view"])
		self.assertFalse(self.model(window)["hover_loading"])
		self.assertEqual(self.model(window)["preview_check_at"], 0.0)

	def test_leaving_the_row_while_it_loads_stops_looking(self):
		world, window = self.hovered()
		with world.game, w4.quiet():
			window.out_row()
		self.assertFalse(self.model(window)["hover_view"])
		self.assertFalse(self.model(window)["hover_loading"])
		self.assertEqual(self.model(window)["preview_check_at"], 0.0)

	def test_a_hovered_model_without_a_mesh_takes_the_box_away(self):
		world, window = self.hovered()
		self.previews.meshes = (0, 0, 0, 0)
		self.previews.step()
		self.check(world, window)
		self.assertFalse(self.model(window)["hover_view"])
		self.assertIn(("Show", "wiki_hover", False), self.previews.calls)

	def viewing(self):
		world, window = self.opened()
		with world.game, w4.quiet():
			window.OpenMob(WOLF)
		self.previews.step()
		self.check(world, window)
		with world.game, w4.quiet():
			w4.press(window, "preview_press", LEFT)
		return world, window

	def test_the_viewer_s_stage_stays_plain_until_its_model_is_made(self):
		world, window = self.viewing()
		self.assertTrue(self.model(window)["viewer"])
		self.assertTrue(self.model(window)["viewer_loading"])
		self.assertEqual(self.previews.step(), "wiki_viewer")
		self.check(world, window)
		self.assertFalse(self.model(window)["viewer_loading"])
		self.assertTrue(self.model(window)["viewer"])

	def test_closing_the_viewer_while_it_loads_stops_looking(self):
		world, window = self.viewing()
		with world.game, w4.quiet():
			window.close_viewer()
		self.assertFalse(self.model(window)["viewer_loading"])
		self.assertEqual(self.model(window)["preview_check_at"], 0.0)

	def test_a_viewer_whose_model_fails_closes(self):
		world, window = self.viewing()
		self.previews.meshes = (0, 0, 0, 0)
		self.previews.step()
		self.check(world, window)
		self.assertFalse(self.model(window)["viewer"])


class TheMarkup(unittest.TestCase):
	"""The preview's box holds no text while it waits, and the view fades."""

	def read(self, name):
		with open(os.path.join(WIKI_DIR, name), encoding="utf-8") as handle:
			return handle.read()

	def test_each_view_is_clear_while_loading_and_animates(self):
		rml = self.read("wiki.rml")
		for view, flag in (("model-wiki", "model_loading"), ("model-wiki-hover", "hover_loading"),
		                   ("model-wiki-viewer", "viewer_loading")):
			tag = re.search(r'<nui-view[^>]*name="%s"[^>]*>' % view, rml, re.S)
			self.assertIsNotNone(tag, view)
			self.assertIn('data-class-is-loading="%s"' % flag, tag.group(0))
			self.assertIn("nui-anim", tag.group(0))

	def test_the_page_s_preview_box_has_no_text_and_no_zoom_mark_while_loading(self):
		rml = self.read("wiki.rml")
		start = rml.index('id="wiki-preview"')
		box = rml[start:rml.index('<div class="wiki__head-text">', start)]
		self.assertNotIn("{{", box, "no text in the preview's box")
		self.assertNotIn("@game.", box)
		mark = re.search(r'<span class="wiki__zoom-mark"[^>]*>', box).group(0)
		self.assertIn("!model_loading", mark)
		self.assertIn('data-class-is-zoomable="model_view &amp;&amp; !model_loading"', box)

	def test_the_clock_calls_preview_check(self):
		rml = self.read("wiki.rml")
		self.assertRegex(rml, r'<nui-countdown[^>]*data-if="preview_check_at > 0"[^>]*data-attr-end="preview_check_at"'
		                      r'[^>]*data-event-countdownend="preview_check\(\)"')

	def test_the_sheet_hides_a_loading_view_and_fades_it_in_in_about_150_ms(self):
		rcss = self.read("wiki.rcss")
		hidden = re.search(r"\.wiki__view\.is-loading, \.wiki__viewer-view\.is-loading\s*\{([^}]*)\}", rcss)
		self.assertIsNotNone(hidden)
		self.assertIn("opacity: 0;", hidden.group(1))
		fade = re.search(r"\.wiki__view\.nui-anim, \.wiki__viewer-view\.nui-anim\s*\{([^}]*)\}", rcss)
		self.assertIsNotNone(fade)
		self.assertIn("transition: opacity 0.15s", fade.group(1))


if __name__ == "__main__":
	unittest.main()
