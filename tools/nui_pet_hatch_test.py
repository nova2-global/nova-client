"""Tests of the NovaUI pet hatch window (assets/root/nui_pet_hatch.py;
NOVA-24, chunk N): python3 -B -m unittest nui_pet_hatch_test (from tools/).

Each flow runs on legacy's uipet.PetHatchEggWindow and on the NovaUI
subclass in the same world (nui_pet_test.World), with the same effects:
pet.UseEgg and pet.ChangeName with their window, cell and name, the short
name's popup, decision Q2's wait refusal (a chat line with the time left).
The NovaUI side also checks the board (the title and the button in both
modes, the cells, the price, the field's limit), Enter and Escape in the
field (a modal), the lifecycle, the loader's bindings and the fixtures."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_pet_test as pt  # noqa: E402
import pet_support as ps  # noqa: E402

w4 = pt.w4
EGG_CELL, SEAL_CELL = 3, 5
FIELD = "pet-hatch-field"


def give(world, cell, vnum, **kwargs):
    world.game.give(cell, vnum, **kwargs)
    world.game.give((w4.P["INVENTORY"], cell), vnum, **kwargs)


def made(world):
    give(world, EGG_CELL, ps.EGG)
    give(world, SEAL_CELL, ps.SEAL)
    return world.make("PetHatchEggWindow", "nui_pet_hatch")


def opened(world, cell=EGG_CELL, rename=False):
    window = made(world)
    world.run(window.Open, cell, w4.P["INVENTORY"], rename)
    return window


def type_name(world, window, name):
    if world.nui_on:
        w4.board(window).set_value(FIELD, name)
    else:
        window.GetChild("pet_name").SetText(name)


def press_hatch(world, window):
    if world.nui_on:
        w4.press(window, "hatch_press", 0)
    else:
        button = window.main["hatch"]
        button.event(*button.eventArgs)


def enter(world, window):
    if world.nui_on:
        w4.board(window).key(FIELD, world.game.modules["_nui"].KEY_RETURN if hasattr(world.game.modules.get("_nui"), "KEY_RETURN") else 72)
    else:
        window.main["name"].return_event()


class Flows(unittest.TestCase):
    def test_hatch_sends_the_eggs_cell_and_the_name(self):
        lworld, lwindow, nworld, nwindow = pt.run_both(
            self, opened, lambda world, window: (type_name(world, window, "Rex"), press_hatch(world, window)))
        self.assertIn(("pet.UseEgg", (w4.P["INVENTORY"], EGG_CELL, "Rex")), nworld.game.log)
        self.assertFalse(nwindow.IsShow())

    def test_a_short_name_opens_the_popup(self):
        lworld, lwindow, nworld, nwindow = pt.run_both(
            self, opened, lambda world, window: (type_name(world, window, "Re"), press_hatch(world, window)))
        self.assertNotIn("pet.UseEgg", [name for name, args in nworld.game.log])

    def test_rename_mode_changes_the_seals_name(self):
        lworld, lwindow, nworld, nwindow = pt.run_both(
            self, lambda world: opened(world, SEAL_CELL, True),
            lambda world, window: (type_name(world, window, "Bruno"), press_hatch(world, window)))
        self.assertIn(("pet.ChangeName", (w4.P["INVENTORY"], SEAL_CELL, "Bruno")), nworld.game.log)

    def test_an_egg_that_cannot_hatch_yet_says_how_long(self):
        def prepare(world):
            window = made(world)
            give(world, EGG_CELL, ps.EGG, sockets=(0, world.game.timestamp + 3600, 0, 0))
            return window
        lworld, lwindow, nworld, nwindow = pt.run_both(
            self, prepare, lambda world, window: window.Open(EGG_CELL, w4.P["INVENTORY"]))
        self.assertIsNone(w4.board(nwindow))
        self.assertTrue([args for name, args in nworld.game.log if name == "chat.AppendChat"])


class Board(unittest.TestCase):
    def test_both_modes(self):
        world = pt.World(True)
        window = opened(world)
        board = pt.model(window)
        locale = world.game.modules["localeInfo"]
        self.assertEqual(board["title"], ps.locale_module("locale_interface.txt").PET_HATCHING_WINDOW_TITLE)
        self.assertEqual((board["cells"][0]["kind"], board["cells"][1]["kind"]), ("item", "item"))
        self.assertTrue(board["price_shown"])
        self.assertEqual(board["price"], locale.TOOLTIP_SELLPRICE % locale.NumberToMoneyString(1000000))
        self.assertEqual(board["max"], 20)
        world.run(window.Close)
        world.run(window.Open, SEAL_CELL, w4.P["INVENTORY"], True)
        board = pt.model(window)
        self.assertEqual((board["title"], board["button"]), (locale.PET_HATCH_RENAME_TITLE, locale.PET_HATCH_RENAME_BUTTON))
        self.assertFalse(board["price_shown"])
        self.assertEqual(board["cells"][1]["kind"], "")

    def test_enter_hatches_and_escape_closes(self):
        world = pt.World(True)
        window = opened(world)
        board = w4.board(window)
        board.set_value(FIELD, "Rex")
        with world.game, w4.quiet():
            board.key(FIELD, world.game.loaded["nui_pet_hatch"].nui.KEY_RETURN)
        self.assertIn(("pet.UseEgg", (w4.P["INVENTORY"], EGG_CELL, "Rex")), world.game.log)
        window = opened(world)
        with world.game, w4.quiet():
            w4.board(window).key(FIELD, world.game.loaded["nui_pet_hatch"].nui.KEY_ESCAPE)
        self.assertFalse(window.IsShow())

    def test_it_is_a_modal_and_the_name_never_enters_the_model(self):
        world = pt.World(True)
        window = opened(world)
        w4.board(window).set_value(FIELD, "Secret")
        self.assertTrue(type(w4.board(window)).MODAL)
        self.assertNotIn("Secret", repr(pt.model(window)))

    def test_every_fixture_has_every_model_key(self):
        world = pt.World(True)
        window = opened(world)
        keys = w4.model_kinds(pt.model(window))
        for variant in ("", "rename"):
            with self.subTest(variant=variant):
                self.assertEqual(w4.fixture_keys(window, "pet-hatch", variant), keys)


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
        theirs = dict((key, pt.handler_name(value)) for key, value in a.main["item"].events.items() if value)
        mine = dict((key, pt.handler_name(value)) for key, value in b.main["item"].handlers().items() if value)
        self.assertEqual(mine, theirs)
        self.assertIsNotNone(b.main["name"].eventReturn)
        self.assertIsNotNone(b.main["name"].eventEscape)
        self.assertIsNotNone(b.main["hatch"].event)


if __name__ == "__main__":
    unittest.main()
