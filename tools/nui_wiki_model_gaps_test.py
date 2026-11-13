"""NOVA-177: a wiki preview whose model has no mesh to draw shows the item's
icon (or the mob's empty well), with no zoom mark and no viewer.

Many items and mobs build a model the client draws nothing of: the file the
race file, item_list or msm names is not in the pack (tools/model_gaps.py,
.nui-work/w9/reports/model-gaps-audit.md). modelpreview.GetState's meshes
says which parts of the model have a mesh (body, weapon, hair, sash); the
wiki looks at the part the page is about. Run from tools/:

	python3 -B -m unittest nui_wiki_model_gaps_test
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402
import nui_wiki_test as base  # noqa: E402

BODY, WEAPON, HAIR, SASH = 0, 1, 2, 3
KIMONO = 11918  # Shinsoo Kimono+: its shape names warrior_event1.gr2, which the pack lacks


class ModelGaps(base.WikiTest):
	def world(self, meshes=(1, 1, 1, 1), pending=0):
		world, window = base.WikiTest.world(self)
		world.game.answer("player", "GetRace", lambda: 1)  # the stand-in's Select makes no model of race 0
		previews = world.game.modules["modelpreview"]
		self.meshes = list(meshes)
		self.pending = pending

		def get_state(name):
			made = any(c[0] == "Select" and c[1] == name for c in previews.calls)
			return {"has_model": 1 if made else 0, "pending": self.pending, "rotation": 0.0,
			        "meshes": tuple(self.meshes) if made and not self.pending else (0, 0, 0, 0)}
		previews.GetState = get_state
		previews.SetTurn = lambda name, turning: None
		previews.SetZoom = lambda name, zoom: None
		previews.SetRotation = lambda name, degrees: None
		self.previews = previews
		return world, window

	def as_costume_body(self, world):
		item = world.game.modules["item"]
		world.game.answer("item", "GetItemType", lambda: item.ITEM_TYPE_COSTUME)
		world.game.answer("item", "GetItemSubType", lambda: item.COSTUME_TYPE_BODY)

	def model(self, window):
		return w4.board(window).model

	def test_a_costume_whose_body_has_no_mesh_shows_its_icon(self):
		world, window = self.world(meshes=(0, 1, 1, 0))
		self.as_costume_body(world)
		with world.game, w4.quiet():
			window.Open()
			window.open_item(KIMONO)
		self.assertIn(("Select", "wiki", 1, KIMONO, 0, 0, 0), self.previews.calls)
		self.assertFalse(self.model(window)["model_view"])
		self.assertEqual(self.model(window)["page_icon"] != "", True)
		self.assertIn(("Show", "wiki", False), self.previews.calls)

	def test_no_viewer_opens_on_an_item_without_a_mesh(self):
		world, window = self.world(meshes=(0, 1, 1, 0))
		self.as_costume_body(world)
		with world.game, w4.quiet():
			window.Open()
			window.open_item(KIMONO)
			window.open_viewer()
		self.assertFalse(self.model(window)["viewer"])
		self.assertFalse([c for c in self.previews.calls if c[0] == "Select" and c[1] == "wiki_viewer"])

	def test_a_costume_that_draws_keeps_its_model(self):
		world, window = self.world()
		self.as_costume_body(world)
		with world.game, w4.quiet():
			window.Open()
			window.open_item(41029)
		self.assertTrue(self.model(window)["model_view"])

	def test_a_weapon_without_its_own_mesh_shows_its_icon_though_the_body_draws(self):
		world, window = self.world(meshes=(1, 0, 1, 0))
		with world.game, w4.quiet():
			window.Open()
			window.open_item(base.SWORD)
		self.assertFalse(self.model(window)["model_view"])

	def test_a_mob_without_a_mesh_shows_no_model(self):
		world, window = self.world(meshes=(0, 0, 0, 0))
		with world.game, w4.quiet():
			window.Open()
			window.OpenMob(8002)
		self.assertFalse(self.model(window)["model_view"])

	def test_an_exe_without_meshes_keeps_the_model(self):
		world, window = self.world()
		self.previews.GetState = lambda name: {"has_model": 1, "pending": 0}
		with world.game, w4.quiet():
			window.Open()
			window.OpenMob(8002)
		self.assertTrue(self.model(window)["model_view"])

	def test_a_waiting_hover_is_not_judged_but_a_known_blank_item_is_not_hovered(self):
		world, window = self.world(meshes=(1, 1, 1, 1), pending=1)
		with world.game, w4.quiet():
			window.Open()
			window.search("sword")
			window.over_row(0)
		self.assertTrue(self.model(window)["hover_view"])  # still waiting: shown as before
		with world.game, w4.quiet():
			window.out_row()
		# The page finds the sword's weapon part empty...
		self.pending = 0
		self.meshes = [1, 0, 1, 0]
		with world.game, w4.quiet():
			window.open_item(base.SWORD)
		self.assertFalse(self.model(window)["model_view"])
		# ...so its row's hover shows nothing, waiting or not.
		self.pending = 1
		with world.game, w4.quiet():
			window.over_row(0)
		self.assertFalse(self.model(window)["hover_view"])


if __name__ == "__main__":
	unittest.main()
