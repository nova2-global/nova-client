"""Tests of the NovaUI pet mini window (assets/root/nui_pet_mini.py; NOVA-24,
chunk N): python3 -B -m unittest nui_pet_mini_test (from tools/).

Each flow runs on legacy's uipet.PetInterfaceWindow and on the NovaUI
subclass in the same world (nui_pet_test.World), with the same effects (the
pet module's requests, the skill tooltip's calls). The NovaUI side also
checks the board: folded at the open, opened by a press on the icon with
its 30 seconds as the countdown's end, folded again by a second press or by
the countdown's end (legacy's __StartMinimize), the lines, the gauge, the
cells and their locks; no Python per frame, the lifecycle, the loader's
bindings and the fixtures' keys."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_pet_test as pt  # noqa: E402
import pet_support as ps  # noqa: E402

w4 = pt.w4


def opened(world):
    world.state.summon(level=92, exp=10, next_exp=40)
    for slot in range(6):
        world.state.own["skills"][slot] = [ps.APPLY_MAX_HP, 5, 50]
    window = world.make("PetInterfaceWindow", "nui_pet_mini")
    world.run(window.Open)
    return window


def press_icon(world, window):
    if world.nui_on:
        w4.press(window, "image_press", 0)
    else:
        window.GetChild("image").OnMouseLeftButtonDown()


class Flows(unittest.TestCase):
    def test_a_revert_on_a_small_cell_resets_the_skill(self):
        def flow(world, window):
            world.attach(w4.P["SLOT_TYPE_INVENTORY"], pt.REVERT_CELL, ps.REVERT)
            pt.cell_press(world, window, 3)
        lworld, lwindow, nworld, nwindow = pt.run_both(self, opened, flow)
        self.assertIn(("pet.UseResetSkill", (w4.P["INVENTORY"], pt.REVERT_CELL, 3)), nworld.game.log)

    def test_a_hover_shows_the_skill_tooltip(self):
        lworld, lwindow, nworld, nwindow = pt.run_both(self, opened, lambda world, window: pt.cell_over(world, window, 1))
        self.assertIn(("PetSkillToolTip.SetSkill", (ps.APPLY_MAX_HP, 5, False)), nworld.game.log)


class Fold(unittest.TestCase):
    def test_it_opens_folded_and_a_press_opens_it_for_thirty_seconds(self):
        world = pt.World(True)
        window = opened(world)
        self.assertFalse(pt.model(window)["open"])
        self.assertEqual(pt.model(window)["fold_at"], 0.0)
        press_icon(world, window)
        board = pt.model(window)
        self.assertTrue(board["open"])
        now = world.game.modules["_nui"].Now() if hasattr(world.game.modules.get("_nui"), "Now") else None
        self.assertGreater(board["fold_at"], 0.0)
        if now is not None:
            self.assertAlmostEqual(board["fold_at"] - now, 30.0, places=3)

    def test_a_second_press_or_the_countdowns_end_folds_it(self):
        world = pt.World(True)
        window = opened(world)
        press_icon(world, window)
        press_icon(world, window)
        self.assertFalse(pt.model(window)["open"])
        press_icon(world, window)
        with world.game, w4.quiet():
            w4.fire(window, "fold_due")
        self.assertFalse(pt.model(window)["open"])
        self.assertTrue(window._isMinimized)

    def test_the_fold_hides_the_tooltips(self):
        world = pt.World(True)
        window = opened(world)
        press_icon(world, window)
        pt.cell_over(world, window, 1)
        with world.game, w4.quiet():
            w4.fire(window, "fold_due")
        self.assertFalse(window.skillToolTip.IsShow())


class Board(unittest.TestCase):
    def test_the_lines_the_gauge_and_the_cells(self):
        world = pt.World(True)
        window = opened(world)
        board = pt.model(window)
        locale = world.game.modules["localeInfo"]
        self.assertEqual(board["title"], "Rex [Lv. 92]")
        self.assertIn(locale.PET_EVOLVE_GRADE_MYTHIC, board["evolution"])
        self.assertEqual(board["evolution_color"], "#b9f2ff")
        self.assertEqual(board["exp"], 0.25)
        self.assertEqual(board["icon"], "/icon/item/55701.tga")
        self.assertEqual(board["disabled"], [False] * 6 + [True] * 7, "Mythic: six basic cells, no heroic")
        self.assertEqual(board["cells"][0]["icon"], "d:/ymir work/ui/pet/skill/normal/MAX_HP.png")

    def test_unsummon_closes_it(self):
        world = pt.World(True)
        window = opened(world)
        world.run(window.Close)
        self.assertIsNone(w4.board(window))

    def test_every_fixture_has_every_model_key(self):
        world = pt.World(True)
        window = opened(world)
        keys = w4.model_kinds(pt.model(window))
        for variant in ("", "folded"):
            with self.subTest(variant=variant):
                self.assertEqual(w4.fixture_keys(window, "pet-mini", variant), keys)


class NoPerFramePython(unittest.TestCase):
    def test_no_per_frame_python(self):
        world = pt.World(True)
        window = opened(world)
        self.assertIsNone(type(window).OnUpdate)
        self.assertIsNone(type(window).OnRender)


class Lifecycle(unittest.TestCase):
    def test_hide_and_show_before_the_legacy_init_do_not_raise(self):
        world = pt.World(True)
        window = opened(world)
        cls = type(window)
        bare = cls.__new__(cls)
        with world.game, w4.quiet():
            bare.nui_begin()
            bare.Hide()
            bare.Show()


class LoaderBindsAsLegacy(unittest.TestCase):
    def test_the_bindings(self):
        a, b = opened(pt.World(False)), opened(pt.World(True))
        self.assertEqual(sorted(a.main), sorted(b.main))
        theirs = dict((key, pt.handler_name(value)) for key, value in a.main["skill"].events.items() if value)
        mine = dict((key, pt.handler_name(value)) for key, value in b.main["skill"].handlers().items() if value)
        self.assertEqual(mine, theirs)
        for name in ("OnMouseOverIn", "OnMouseOverOut"):
            self.assertIn(name, vars(b.main["ExpBar"]))
        self.assertIn("OnMouseLeftButtonDown", vars(b.main["image"]))


if __name__ == "__main__":
    unittest.main()
