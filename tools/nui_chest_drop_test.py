"""Tests of the chest-drop preview (NOVA-18): the legacy window
(assets/root/uichestdrop.py, OLD's uiTimerWindow.ChestItemPopup), its NovaUI
facade (assets/root/nui_chest_drop.py) and the game's answer handler.

OLD's tier rule and the request-once rule are checked on their own; each
window flow runs on the legacy window and on the facade in the Wave 4 test
world, and the effects (the packets, the item module's calls) must be the
same, since the facade only swaps the widgets for proxies. The NovaUI side
also checks what the board shows."""

import ast
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402

ROOT = os.path.join(os.path.dirname(HERE), "assets", "root")

CHEST = 50011
GACHA = 34218
NOT_A_CHEST = 27001
# The client's item types (GameLib/ItemData.h) and USE_TREASURE_BOX.
ITEM_TYPE_USE, ITEM_TYPE_GIFTBOX, ITEM_TYPE_GACHA, USE_TREASURE_BOX = 3, 23, 38, 22
TYPES = {CHEST: ITEM_TYPE_GIFTBOX, GACHA: ITEM_TYPE_GACHA, 50012: ITEM_TYPE_USE}
SUBTYPES = {50012: USE_TREASURE_BOX}
# What GC::CHEST_DROP_INFO brought: material x5 at 30, yang 100000 at 15,
# a potion at 4 (the server's own test group).
ROWS = [(27992, 5, 30), (1, 100000, 15), (71084, 1, 4)]


def items(game):
    item = game.modules["item"]
    for name, value in (("ITEM_TYPE_USE", ITEM_TYPE_USE), ("ITEM_TYPE_GIFTBOX", ITEM_TYPE_GIFTBOX),
                        ("ITEM_TYPE_GACHA", ITEM_TYPE_GACHA), ("USE_TREASURE_BOX", USE_TREASURE_BOX)):
        setattr(item, name, value)
    game.answer("item", "GetItemType", lambda: TYPES.get(item.selected[0], 0))
    game.answer("item", "GetItemSubType", lambda: SUBTYPES.get(item.selected[0], 0))
    game.answer("item", "GetLimit", lambda i: (0, 10) if item.selected[0] == GACHA else (0, 0))
    locale = game.modules["localeInfo"]
    for key, text in (("CHEST_DROP_TITLE", "Chest Items"),
                      ("CHEST_DROP_FOUND_IN", "The following items can be found in %s"),
                      ("CHEST_DROP_OPEN_TIMES", "This chest can be opened %d time(s)"),
                      ("CHEST_DROP_TIER_LOW", "Low Chance Item"),
                      ("CHEST_DROP_TIER_MIDDLE", "Middle Chance Item"),
                      ("CHEST_DROP_TIER_HIGH", "High Chance Item")):
        setattr(locale, key, text)


class _ScrollWindow(object):
    """ui.ScrollWindow as the row list uses it (assets/root/ui.py)."""

    THIN = 0

    def __init__(self, width, height, kind=0):
        self.content = None
        self.size_changes = 0
        self.to_start = 0

    def __getattr__(self, name):
        return lambda *args: None

    def SetContentWindow(self, window):
        self.content = window

    def OnContentWindowSizeChange(self):
        self.size_changes += 1

    def ScrollToStart(self):
        self.to_start += 1


class ChestDropTest(unittest.TestCase):
    def world(self, nui_on):
        world = w4.World(nui_on, windows="+trade,+chest-drop", setup=items)
        with world.game, w4.quiet():
            world.game.modules["ui"].ScrollWindow = _ScrollWindow
            world.game.modules["constInfo"].CHESTS_PREVIEW = {}
            world.game.load("uiChestDrop", "uichestdrop.py")
            if nui_on:
                world.game.load("nui_chest_drop", "nui_chest_drop.py")
        window = world.make("chest-drop", "uiChestDrop", "ChestDropWindow", "nui_chest_drop.ChestDropWindow")
        return world, window

    def module(self, world):
        return world.m("uiChestDrop")

    def legacy_rows(self, window):
        return [(name.GetText(), label.GetText()) for (_, _, name, label) in window.rowList.rows]


class Tiers(unittest.TestCase):
    """OLD's GET_CHEST_RARITY_BY_PERC (uiTimerWindow.py:1441-1452) over the
    chest's own rows."""

    def setUp(self):
        world = w4.World(False, setup=items)
        with world.game, w4.quiet():
            world.game.modules["ui"].ScrollWindow = _ScrollWindow
            world.game.load("uiChestDrop", "uichestdrop.py")
        self.m = world.m("uiChestDrop")

    def test_the_tiers_split_at_the_middles_of_the_average_and_the_ends(self):
        # min 4, average (30 + 15 + 4) // 3 = 16, max 30: low below 10, middle up to 23.
        self.assertEqual(self.m.rows_with_tiers(ROWS),
                         [(27992, 5, self.m.TIER_HIGH), (1, 100000, self.m.TIER_MIDDLE), (71084, 1, self.m.TIER_LOW)])
        self.assertEqual(self.m.tier_of(9, 4.0, 16.0, 30.0), self.m.TIER_LOW)
        self.assertEqual(self.m.tier_of(10, 4.0, 16.0, 30.0), self.m.TIER_MIDDLE)
        self.assertEqual(self.m.tier_of(23, 4.0, 16.0, 30.0), self.m.TIER_MIDDLE)
        self.assertEqual(self.m.tier_of(24, 4.0, 16.0, 30.0), self.m.TIER_HIGH)

    def test_equal_chances_are_all_middle_and_no_rows_none(self):
        self.assertEqual([t for (_, _, t) in self.m.rows_with_tiers([(1, 1, 5), (2, 1, 5)])], [self.m.TIER_MIDDLE] * 2)
        self.assertEqual(self.m.rows_with_tiers([]), [])

    def test_the_average_is_a_whole_number_as_old_s(self):
        # Chances 1, 2, 2: OLD's average is 5 // 3 = 1, so 1 is middle (1 < 1.0 is false).
        self.assertEqual([t for (_, _, t) in self.m.rows_with_tiers([(1, 1, 1), (2, 1, 2), (3, 1, 2)])],
                         [self.m.TIER_MIDDLE, self.m.TIER_HIGH, self.m.TIER_HIGH])


class Request(ChestDropTest):
    def test_a_chest_is_asked_for_once_a_session_and_no_other_item_is(self):
        world, window = self.world(False)
        m = self.module(world)
        mark = world.mark()
        with world.game, w4.quiet():
            self.assertTrue(m.request(CHEST))
            world.m("constInfo").CHESTS_PREVIEW[CHEST] = list(ROWS)
            self.assertTrue(m.request(CHEST))
            self.assertTrue(m.request(GACHA))
            self.assertTrue(m.request(50012))
            self.assertFalse(m.request(NOT_A_CHEST))
            self.assertFalse(m.request(0))
        sent = [args for name, args in world.effects_since(mark) if name == "net.SendChestDropInfo"]
        self.assertEqual(sent, [(CHEST,), (GACHA,), (50012,)])

    def test_the_hovered_chest_is_kept_until_the_pointer_leaves(self):
        world, window = self.world(False)
        m = self.module(world)
        with world.game, w4.quiet():
            m.hover(CHEST)
            self.assertEqual(m.hovered_vnum(), CHEST)
            m.hover(NOT_A_CHEST)
            self.assertEqual(m.hovered_vnum(), 0, "only a chest counts")
            m.hover(GACHA)
            m.unhover()
            self.assertEqual(m.hovered_vnum(), 0)


class Windows(ChestDropTest):
    def open_both(self, vnum, rows):
        results = []
        for nui_on in (False, True):
            world, window = self.world(nui_on)
            mark = world.mark()
            with world.game, w4.quiet():
                world.m("constInfo").CHESTS_PREVIEW[vnum] = list(rows)
                window.Open(vnum)
            results.append((world.effects_since(mark), world, window))
        (legacy, lw, lwin), (novaui, nw, nwin) = results
        self.assertEqual(novaui, legacy)
        return lwin, nwin

    def test_the_rows_show_the_count_name_and_tier_in_both(self):
        legacy, novaui = self.open_both(CHEST, ROWS)
        self.assertEqual(self.legacy_rows(legacy), [("5x item 27992", "High Chance Item"),
                                                    ("100000x item 1", "Middle Chance Item"),
                                                    ("1x item 71084", "Low Chance Item")])
        self.assertEqual(legacy.infoLabel.GetText(), "The following items can be found in item 50011")
        self.assertEqual(legacy.openLabel.GetText(), "")
        model = w4.board(novaui).model
        self.assertEqual([(r["name"], r["tier"]) for r in model["rows"]],
                         [("5x item 27992", 3), ("100000x item 1", 2), ("1x item 71084", 1)])
        self.assertEqual(model["rows"][0]["icon"], "/icon/item/27992.tga")
        self.assertEqual(model["info"], "The following items can be found in item 50011")
        self.assertEqual(model["chest_name"], "item 50011")
        self.assertEqual(model["chest_icon"], "/icon/item/50011.tga")
        self.assertEqual(model["title"], "Chest Items")

    def test_a_gacha_chest_says_how_many_times_it_opens(self):
        legacy, novaui = self.open_both(GACHA, ROWS)
        self.assertEqual(legacy.openLabel.GetText(), "This chest can be opened 10 time(s)")
        self.assertEqual(w4.board(novaui).model["opens"], "This chest can be opened 10 time(s)")

    def test_a_chest_without_an_answer_yet_opens_empty(self):
        legacy, novaui = self.open_both(CHEST, [])
        self.assertEqual(self.legacy_rows(legacy), [])
        self.assertEqual(w4.board(novaui).model["rows"], [])

    def test_the_close_button_hides_the_window(self):
        world, window = self.world(True)
        with world.game, w4.quiet():
            window.Open(CHEST)
            self.assertTrue(window.IsShow())
            w4.press(window, "close_press", 0)
            self.assertFalse(window.IsShow())

    def test_the_fixture_has_every_model_key(self):
        world, window = self.world(True)
        with world.game, w4.quiet():
            window.Open(CHEST)
        self.assertEqual(set(w4.fixture_keys(window, "chest-drop")), set(w4.board(window).model))

    def test_the_facade_runs_no_python_per_frame(self):
        world, window = self.world(True)
        self.assertIsNone(type(window).OnUpdate)


class Lifecycle(ChestDropTest):
    def test_hide_and_show_before_the_legacy_init(self):
        world, window = self.world(True)
        cls = type(window)
        with world.game, w4.quiet():
            bare = cls.__new__(cls)
            bare.nui_begin()
            bare.Hide()
            bare.Show()
            bare.nui_discard()


class GameAnswer(unittest.TestCase):
    """game.BINARY_SetChestDropInfo: one call with every row replaces the
    known rows (OLD appended each row, so a second answer doubled them), then
    the window opens on the chest."""

    def handler(self):
        source = open(os.path.join(ROOT, "game.py"), encoding="utf-8").read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "BINARY_SetChestDropInfo":
                module = ast.Module(body=[node], type_ignores=[])
                scope = {"constInfo": types.SimpleNamespace(CHESTS_PREVIEW={})}
                exec(compile(module, "game.py", "exec"), scope)
                return scope["BINARY_SetChestDropInfo"], scope["constInfo"]
        self.fail("game.py has no BINARY_SetChestDropInfo")

    def test_a_second_answer_replaces_the_rows_and_each_opens_the_window(self):
        handler, const = self.handler()
        opened = []
        game = types.SimpleNamespace(interface=types.SimpleNamespace(RefreshChestDrop=opened.append))
        handler(game, CHEST, tuple(ROWS))
        handler(game, CHEST, tuple(ROWS))
        self.assertEqual(const.CHESTS_PREVIEW[CHEST], ROWS)
        self.assertEqual(opened, [CHEST, CHEST])


if __name__ == "__main__":
    unittest.main()
