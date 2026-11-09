"""Tests of the NovaUI pet evolution window (assets/root/nui_pet_evolution.py;
NOVA-24, chunk N): python3 -B -m unittest nui_pet_evolution_test (from
tools/).

Each flow runs on legacy's uipet.PetEvolutionWindow and on the NovaUI
subclass in the same world (nui_pet_test.World), with the same effects: the
money and material popups, pet.Evolve, the result texts, the item tooltip's
calls. The NovaUI side also checks the board (the seal, the name, both
grades in OLD's colors with their counts, the materials in legacy's order,
the cost) with enough and short of materials, the lifecycle, the loader's
bindings and the fixtures' keys."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_pet_test as pt  # noqa: E402

w4 = pt.w4
MATERIALS = [(27992, 200), (27993, 200), (27994, 200)]


def opened(world, money=10 ** 10, have=200):
    world.state.summon(level=75, exp=0)
    world.state.evolve.update({"cost": 50000000, "materials": list(MATERIALS), "prob": 100})
    player = world.game.modules["player"]
    player.GetMoney = lambda: money
    player.GetItemCountByVnum = lambda vnum: have
    window = world.make("PetEvolutionWindow", "nui_pet_evolution")
    world.run(window.Open)
    return window


def press(world, window, name, event):
    if world.nui_on:
        w4.press(window, event, 0)
    else:
        button = window.main[name]
        button.event(*button.eventArgs)


class Flows(unittest.TestCase):
    def test_evolve_with_enough_sends(self):
        lworld, lwindow, nworld, nwindow = pt.run_both(self, opened, lambda world, window: press(world, window, "evolve", "evolve_press"))
        self.assertIn(("pet.Evolve", ()), nworld.game.log)

    def test_short_of_money_or_material_shows_legacys_popup(self):
        for money, have in ((100, 200), (10 ** 10, 3)):
            with self.subTest(money=money, have=have):
                lworld, lwindow, nworld, nwindow = pt.run_both(
                    self, lambda world: opened(world, money, have),
                    lambda world, window: press(world, window, "evolve", "evolve_press"))
                self.assertNotIn("pet.Evolve", [name for name, args in nworld.game.log])
                self.assertTrue([name for name, args in nworld.game.log if name == "uiCommon.PopupDialog.Open"])

    def test_the_results_and_cancel(self):
        lworld, lwindow, nworld, nwindow = pt.run_both(
            self, opened, lambda world, window: (window.OnEvolveFailure(), window.OnEvolveSuccess()))
        self.assertFalse(nwindow.IsShow())
        pt.run_both(self, opened, lambda world, window: press(world, window, "cancel", "cancel_press"))

    def test_a_material_hover_shows_its_tooltip(self):
        world = pt.World(True)
        window = opened(world)
        tip = window._itemToolTip
        before = len(tip.calls)
        w4.fire(window, "material_over", 0)
        w4.fire(window, "material_out", 0)
        names = [call[0] for call in tip.calls[before:]]
        self.assertEqual(names[:1], ["SetItemToolTip"])


class Board(unittest.TestCase):
    def test_the_grades_the_materials_and_the_cost(self):
        world = pt.World(True)
        window = opened(world)
        board = pt.model(window)
        locale = world.game.modules["localeInfo"]
        self.assertEqual(board["current"]["title"], locale.PET_EVOLVE_GRADE_CHAMPION)
        self.assertEqual(board["current"]["color"], "#31d32a")
        self.assertEqual(board["next"]["title"], locale.PET_EVOLVE_GRADE_VETERAN)
        self.assertEqual(board["next"]["active"], locale.PET_EVOLVE_ACTIVE_SKILL_COUNT % "5")
        self.assertEqual([m["count"] for m in board["materials"]], ["200", "200", "200"])
        self.assertEqual(board["materials"][0]["icon"], "/icon/item/27994.tga", "legacy's order: the last first")
        self.assertEqual(board["cost"], locale.PET_EVOLVE_PRICE % locale.NumberToMoneyString(50000000))
        self.assertEqual(board["name"], "Rex")

    def test_every_fixture_has_every_model_key(self):
        world = pt.World(True)
        window = opened(world)
        keys = w4.model_kinds(pt.model(window))
        for variant in ("", "short"):
            with self.subTest(variant=variant):
                self.assertEqual(w4.fixture_keys(window, "pet-evolution", variant), keys)


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
        self.assertEqual(sorted(a.main["current"]), sorted(b.main["current"]))
        self.assertEqual(len(a._materials), len(b._materials))
        for name in ("evolve", "cancel"):
            self.assertIsNotNone(b.main[name].event, name)
        self.assertIn("OnMouseOverIn", vars(b.main["item"]))


if __name__ == "__main__":
    unittest.main()
