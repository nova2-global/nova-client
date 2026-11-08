"""Tests of the NovaUI pet bonus refine window (assets/root/
nui_pet_attr_refine.py; NOVA-24, chunk N): python3 -B -m unittest
nui_pet_attr_refine_test (from tools/).

Each flow runs on legacy's uipet.PetAttrRefineWindow and on the NovaUI
subclass in the same world (nui_pet_test.World), with the same effects: the
money and material popups, pet.RefineAttr with the bonus's index, the close
at the top level. The NovaUI side also checks the board (the bonus, its
current and next level and value, the materials, the cost), the lifecycle,
the loader's bindings and the fixture's keys."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_pet_test as pt  # noqa: E402
import pet_support as ps  # noqa: E402

w4 = pt.w4


def opened(world, money=10 ** 10, have=20):
    world.state.summon()
    world.state.own["attrs"][1] = [ps.APPLY_MAX_HP, 4, 400, 1]
    world.state.refine.update({"cost": 250000, "materials": [(27992, 20), (27993, 20)]})
    player = world.game.modules["player"]
    player.GetMoney = lambda: money
    player.GetItemCountByVnum = lambda vnum: have
    window = world.make("PetAttrRefineWindow", "nui_pet_attr_refine")
    world.run(window.Open, 1, 500)
    return window


def press(world, window, name, event):
    if world.nui_on:
        w4.press(window, event, 0)
    else:
        button = window.main[name]
        button.event(*button.eventArgs)


class Flows(unittest.TestCase):
    def test_upgrade_sends_the_index(self):
        lworld, lwindow, nworld, nwindow = pt.run_both(self, opened, lambda world, window: press(world, window, "upgrade", "upgrade_press"))
        self.assertIn(("pet.RefineAttr", (1,)), nworld.game.log)

    def test_short_of_money_or_material_shows_legacys_popup(self):
        for money, have in ((100, 20), (10 ** 10, 2)):
            with self.subTest(money=money, have=have):
                lworld, lwindow, nworld, nwindow = pt.run_both(
                    self, lambda world: opened(world, money, have),
                    lambda world, window: press(world, window, "upgrade", "upgrade_press"))
                self.assertNotIn("pet.RefineAttr", [name for name, args in nworld.game.log])

    def test_the_top_level_closes_it_and_cancel(self):
        def flow(world, window):
            world.state.own["attrs"][1][1] = 20
            window.Refresh()
        lworld, lwindow, nworld, nwindow = pt.run_both(self, opened, flow)
        self.assertFalse(nwindow.IsShow())
        pt.run_both(self, opened, lambda world, window: press(world, window, "cancel", "cancel_press"))


class Board(unittest.TestCase):
    def test_the_bonus_the_levels_the_materials_and_the_cost(self):
        world = pt.World(True)
        window = opened(world)
        board = pt.model(window)
        locale = world.game.modules["localeInfo"]
        self.assertEqual((board["attribute"], board["current_level"], board["current_value"], board["next_level"],
                          board["next_value"]), ("Max HP", "Lv. 4", "400", "Lv. 5", "500"))
        self.assertEqual([m["count"] for m in board["materials"]], ["20", "20"])
        self.assertEqual(board["cost"], locale.PET_EVOLVE_PRICE % locale.NumberToMoneyString(250000))

    def test_every_fixture_has_every_model_key(self):
        world = pt.World(True)
        window = opened(world)
        self.assertEqual(w4.fixture_keys(window, "pet-attr-refine"), w4.model_kinds(pt.model(window)))


class Lifecycle(unittest.TestCase):
    def test_hide_and_show_before_the_legacy_init_and_no_per_frame_python(self):
        world = pt.World(True)
        window = opened(world)
        self.assertIsNone(type(window).OnUpdate)
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
        self.assertEqual(len(a._materials), len(b._materials))
        for name in ("upgrade", "cancel"):
            self.assertIsNotNone(b.main[name].event, name)


if __name__ == "__main__":
    unittest.main()
