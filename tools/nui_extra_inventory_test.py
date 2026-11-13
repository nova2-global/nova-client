"""Tests for the NovaUI special inventory (assets/root/nui_extra_inventory.py,
nui/windows/extra-inventory/; wave 4b, NOVA-16) and its wiring in
interfacemodule.py and nui_windows.py: python3 -B -m unittest
nui_extra_inventory_test (from tools/).

Plain CPython over nui_game_support's stand-ins (install_wave3b_ui reads the
real uiscript, so the legacy window is made as the client makes it, and its
slot window fires the events the C++ CSlotWindow sends; install_extra_inventory
adds C1's functions):
- facade: every method the Interface and the trade windows call on the
  legacy class exists on the NovaUI class with the legacy signature, with
  the legacy class's name and constructor, and the loader override is the
  name the legacy constructor calls;
- differential: the legacy window and the NovaUI one, each in a world of its
  own with the same state, driven through the same flows (the legacy slot
  window's C++ events and buttons against the board's data events), make
  the same net, player, mouse, ime, chat, sound, interface and dialog calls
  in order, getters left out, and end with the same attach, category, page,
  shown cells and tooltip;
- model: what the board shows equals what the legacy slot window shows, in
  every category and page, the trade marks too;
- the trade marks: a trade window's lock, the window on top's refusals, a
  page refresh and OnTop show at once; an in-use cell takes no press;
- kept board, placement, fixtures, the lean cell, no per-frame Python, the
  wiring and the golden cases."""
import contextlib
import inspect
import io
import json
import os
import re
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402

ROOT = support.ROOT
NUI = os.path.normpath(os.path.join(support.support.HERE, "..", "assets", "nui", "nui"))
WINDOW = os.path.join(NUI, "windows", "extra-inventory")
FLAGS = "+extra-inventory"
DOCUMENT = "nui/windows/extra-inventory/extra-inventory.rml"
EFFECT_MODULES = ("net", "player", "mouse", "ime", "chat", "snd", "interface", "uiCommon", "uiPickMoney")
LOADED_NOVAUI = ("nui_limits", "nui_proxies", "nui_form_proxies", "nui_extra_inventory")

EXTRA, INVENTORY = 6, 1
SLOT_EXTRA, SLOT_INVENTORY, SLOT_SAFEBOX, SLOT_MALL = 12, 1, 8, 10
SCROLLS, MATERIALS, STONES, CHESTS, COSTUMES = range(5)
RANGES = support.EXTRA_CATEGORY_RANGES
ORE, BEAN, PEARL, WOOD, KEY, BOX, CHEST, COSTUME, SCROLL, POTION = (
    50601, 100300, 27992, 30010, 50008, 50009, 34218, 41001, 71051, 27001)
GACHA = support.W4B_EXTRA_ITEM_CONSTANTS["ITEM_TYPE_GACHA"]


def quiet():
    """The legacy windows print banners."""
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def cell(category, local, page=0):
    """The extra inventory cell of a category's page cell."""
    return RANGES[category][0] + page * 45 + local


def stock(game):
    """The state every flow starts from: the materials' page I with a stack
    of 37 ores at 0, a single pearl at 4 and 54 beans at 5, page II with 5
    woods at 2; the chests' keys (2) at 1, a box at 2 and 7 treasure chests
    (a gacha) at 3; a 1x2 costume at the costumes' 0; 3 scrolls at the
    scrolls' 0; a potion in the main inventory's cell 4."""
    game.give((EXTRA, cell(MATERIALS, 0)), ORE, 37)
    game.give((EXTRA, cell(MATERIALS, 4)), PEARL, 1)
    game.give((EXTRA, cell(MATERIALS, 5)), BEAN, 54)
    game.give((EXTRA, cell(MATERIALS, 2, page=1)), WOOD, 5)
    game.give((EXTRA, cell(CHESTS, 1)), KEY, 2)
    game.give((EXTRA, cell(CHESTS, 2)), BOX, 1)
    game.give((EXTRA, cell(CHESTS, 3)), CHEST, 7)
    game.give((EXTRA, cell(COSTUMES, 0)), COSTUME, 1, size=(1, 2))
    game.give((EXTRA, cell(SCROLLS, 0)), SCROLL, 3)
    game.give(4, POTION, 10)
    game.keys.add(KEY)
    game.item_types[CHEST] = GACHA


def with_state(*changes):
    def setup(game):
        stock(game)
        for change in changes:
            change(game)
    return setup


class World(object):
    """One world: a Game with the legacy special inventory and the NovaUI one
    loaded over its stand-ins, the extra-inventory flag on when `nui_on`."""

    def __init__(self, nui_on, engine_3b=True, setup=stock):
        game = self.game = support.Game(engine_3b=engine_3b)
        support.install_wave2b_ui(game)
        support.install_wave3a_ui(game)
        support.install_wave3b_ui(game)
        game.modules["systemSetting"].GetUINuiWindows = lambda: FLAGS if nui_on else ""
        game.modules["localeInfo"] = support.locale_info("en")
        for name in ("networkModule", "interfaceModule"):
            game.put(name, types.ModuleType(name))
        support.install_extra_inventory(game)
        if setup is not None:
            setup(game)
        game.load_standard()
        with quiet():
            game.load("uiInventory", "uiinventory.py").print = lambda *args, **kwargs: None
            game.load("uiExtraInventory", "uiextrainventory.py")
            for name in LOADED_NOVAUI:
                game.load(name, name + ".py")
        self.nui_windows = game.loaded["nui_windows"]
        self.nui_on = nui_on
        self.interface = game.interface

    def m(self, name):
        return self.game.loaded[name]

    @property
    def mouse(self):
        return self.m("mouseModule").mouseController

    def mark(self):
        return len(self.game.log)

    def effects_since(self, mark):
        return [(name, args) for name, args in self.game.log[mark:]
                if name.split(".", 1)[0] in EFFECT_MODULES and not support.is_getter(name)
                and name not in ("player.GetItemLink",)]

    def make_extra(self, show=True):
        """Interface.__MakeWindows' special inventory (made, bound, hidden),
        the dragon soul refine window and the tooltip it is given later, then
        ToggleExtraInventoryWindow's Open."""
        with self.game, quiet():
            window = self.nui_windows.make("extra-inventory", self.m("uiExtraInventory").ExtraInventoryWindow,
                                           "nui_extra_inventory.ExtraInventoryWindow")
            window.BindInterfaceClass(self.interface)
            window.Hide()
            window.SetDragonSoulRefineWindow(self.game.dragon_soul_refine)
            window.SetItemToolTip(self.game.modules["uiToolTip"].ItemToolTip())
            if show:
                window.Open()
        return window


def board(window):
    demand = getattr(window, "demand", None)
    return demand.board() if demand is not None else None


def fire(window, event, *args):
    shown = board(window)
    if shown is None:
        raise AssertionError("%s has no board" % type(window).__name__)
    return shown.fire(event, *args)


def press(window, event, *args):
    """A mousedown's data event, then the body's own (board_press), which
    RmlUi runs last as the press bubbles. The last argument is the button."""
    shown = board(window)
    result = fire(window, event, *args)
    if board(window) is shown:
        shown.fire("board_press", args[-1])
    return result


class Input(object):
    """One player input, as the legacy slot window's C++ and buttons send it
    and as the board sends it. A cell is its page cell (0 to 44)."""

    def __init__(self, world, window):
        self.world = world
        self.window = window
        self.nui = world.nui_on

    def _select(self, number):
        slot = self.window.wndItem.slots.get(number)
        name = "select_item" if slot is not None and slot["vnum"] and not slot["locked"] else "select_empty"
        self.window.wndItem.fire(name, number)

    def press(self, number, button=0, legacy=None):
        if self.nui:
            press(self.window, "cell_press", number, button)
            return
        self.window.SetTop()
        target = number if legacy is None else legacy
        if button == 0:
            self._select(target)
        else:
            slot = self.window.wndItem.slots.get(target)
            self.window.wndItem.fire("unselect_item" if slot and slot["vnum"] else "unselect_empty", target)

    def release(self, number, legacy=None):
        if self.nui:
            fire(self.window, "cell_release", number, 0)
            return
        self._select(number if legacy is None else legacy)

    def drop(self, number):
        if self.nui:
            fire(self.window, "cell_drop", number)
            return
        self._select(number)

    def use(self, number):
        if self.nui:
            fire(self.window, "cell_use", number)
            return
        self.window.wndItem.fire("use", number)

    def over(self, number):
        if self.nui:
            fire(self.window, "cell_over", number)
            return
        self.window.wndItem.fire("over_in", number)

    def out(self, number):
        if self.nui:
            fire(self.window, "cell_out", number)
            return
        self.window.wndItem.fire("over_out")

    def right_release(self):
        """The window manager cancels what is still attached at the right
        button's release (over NovaUI the host does, nui-attach-right)."""
        if self.world.mouse.isAttached():
            self.world.mouse.DeattachObject()

    def page(self, index):
        if self.nui:
            press(self.window, "page_press", index, 0)
            return
        self.window.SetTop()
        self.window.inventoryTab[index].click()

    def category(self, index):
        if self.nui:
            press(self.window, "category_press", index, 0)
            return
        self.window.SetTop()
        self.window.categoryTab[index].click()

    def wheel(self, notches):
        """Notches down (positive) or up, over the window."""
        if self.nui:
            fire(self.window, "wheel", float(notches))
            return
        self.window.OnScrollWheel(-1 if notches > 0 else 1)

    def close(self):
        if self.nui:
            press(self.window, "close_press", 0)
            return
        self.window.SetTop()
        self.window.GetChild("TitleBar").close()

    def keys(self, *names):
        app = self.world.game.modules["app"]
        self.world.game.pressed = set(getattr(app, name) for name in names)


def accept_last(world, *args):
    world.game.dialogs[-1].accept(*args)


def legacy_cells(window):
    """{page cell: (vnum, count label)} of the legacy slot window."""
    return dict((index, shown[:2]) for index, shown in window.wndItem.shown().items())


def legacy_marks(window):
    """{page cell: (in use, unusable on top)} of the legacy slot window's
    items that have a mark."""
    found = {}
    for index, slot in window.wndItem.slots.items():
        marks = (bool(slot.get("in_use")), bool(slot.get("unusable_ontop")))
        if slot["vnum"] and any(marks):
            found[index] = marks
    return found


def board_cells(window):
    """{page cell: (vnum, count label)} of the board's anchors."""
    vnums = window.wndItem.vnums()
    return dict((c["index"], (vnums[c["index"]], c["count"])) for c in board(window).model["cells"]
                if c["kind"] == "item")


def state_cells(window):
    """board_cells() of the window's state, which a kept board takes at its
    next show."""
    vnums = window.wndItem.vnums()
    return dict((c["index"], (vnums[c["index"]], c["count"])) for c in window._state["cells"] if c["kind"] == "item")


def board_marks(window):
    return dict((c["index"], (c["in_use"], c["unusable_ontop"])) for c in board(window).model["cells"]
                if c["kind"] == "item" and (c["in_use"] or c["unusable_ontop"]))


class Pair(unittest.TestCase):
    """A legacy world and a NovaUI world with the same state."""

    def worlds(self, setup=stock):
        return World(False, setup=setup), World(True, setup=setup)

    def outcome(self, world, window):
        mouse = world.mouse
        attached = ((mouse.GetAttachedType(), mouse.GetAttachedSlotNumber(), mouse.GetAttachedItemIndex(),
                     mouse.GetAttachedItemCount()) if mouse.isAttached() else None)
        shown = legacy_cells(window) if not world.nui_on else state_cells(window)
        return {
            "attached": attached,
            "shown": bool(window.IsShow()),
            "category": window.GetCategory(),
            "page": window.GetInventoryPageIndex(),
            "cells": shown,
            "tooltip": list(window.tooltipItem.shown),
            "dialogs": [(dialog._name, dialog.is_open) for dialog in world.game.dialogs],
        }

    def run_flow(self, flow, setup=stock, before=None):
        results = []
        for world in self.worlds(setup):
            window = world.make_extra()
            with world.game, quiet():
                if before is not None:
                    before(world, window)
                window.tooltipItem.shown[:] = []
                world.game.pressed = set()
                mark = world.mark()
                flow(world, window, Input(world, window))
                world.game.pressed = set()
                results.append((world.effects_since(mark), self.outcome(world, window), world, window))
        return results

    def same(self, flow, setup=stock, before=None, expect=()):
        (legacy, legacy_outcome, _, _), (novaui, novaui_outcome, world, window) = self.run_flow(flow, setup, before)
        self.assertEqual(legacy, novaui)
        self.assertEqual(legacy_outcome, novaui_outcome)
        names = [name for name, _ in legacy]
        for wanted in expect:
            self.assertIn(wanted, names, "the legacy flow makes no %s call: %r" % (wanted, legacy))
        return legacy, world, window


def to_category(category, page=0):
    """A before(): the category and page shown, as the tabs show them."""
    def before(world, window):
        window.categoryTab[category].click() if not world.nui_on else press(window, "category_press", category, 0)
        if page:
            window.inventoryTab[page].click() if not world.nui_on else press(window, "page_press", page, 0)
    return before


def attach(slot_type, slot, vnum, count=1):
    """A before(): another window's item attached, as its window attaches it."""
    def before(world, window):
        world.mouse.AttachObject(object(), slot_type, slot, vnum, count)
    return before


class Construction(Pair):
    def test_the_flag_makes_the_novaui_class_and_without_it_the_legacy_one(self):
        legacy, novaui = self.worlds()
        a, b = legacy.make_extra(), novaui.make_extra()
        self.assertIs(type(a), legacy.m("uiExtraInventory").ExtraInventoryWindow)
        self.assertIs(type(b), novaui.m("nui_extra_inventory").ExtraInventoryWindow)
        self.assertIsNotNone(board(b))
        self.assertEqual(novaui.nui_windows.DECISIONS["extra-inventory"], "nui")

    def test_without_the_3b_engine_or_a_document_the_legacy_class_is_made(self):
        old = World(True, engine_3b=False)
        self.assertIs(type(old.make_extra()), old.m("uiExtraInventory").ExtraInventoryWindow)
        failing = World(True)
        failing.game.state.failing.add(DOCUMENT)
        self.assertIs(type(failing.make_extra()), failing.m("uiExtraInventory").ExtraInventoryWindow)
        self.assertEqual(failing.game.loaded_documents(), [])

    def test_the_legacy_window_underneath_stays_0_by_0_with_the_uiscript_s_flags(self):
        legacy, novaui = self.worlds()
        a, b = legacy.make_extra(), novaui.make_extra()
        self.assertEqual((b.GetWidth(), b.GetHeight()), (0, 0))
        self.assertTrue(b.IsShow())
        self.assertEqual(b.flags, a.flags)
        self.assertIn("float", b.flags)

    def test_the_proxies_count_from_the_limits(self):
        world = World(True)
        window = world.make_extra()
        limits = world.m("nui_limits").current()
        self.assertEqual(len(window.inventoryTab), limits.EXTRA_INVENTORY_COSTUME_PAGE_COUNT)
        self.assertEqual(len(window.categoryTab), limits.EXTRA_INVENTORY_CATEGORY_COUNT)
        self.assertEqual(window.wndItem.GetSlotCount(), limits.EXTRA_INVENTORY_PAGE_SIZE)
        self.assertEqual((window.wndItem.cols, window.wndItem.rows),
                         (limits.EXTRA_INVENTORY_COLUMNS, limits.EXTRA_INVENTORY_ROWS))
        model = board(window).model
        self.assertEqual(model["cols"], limits.EXTRA_INVENTORY_COLUMNS)
        self.assertEqual([k["label"] for k in model["categories"]],
                         list(world.m("nui_extra_inventory").CATEGORY_KEYS))


class Facade(unittest.TestCase):
    """Every member the Interface (interfacemodule.py), game.py and the trade
    windows (BindWindow, SetInven) call, with the legacy signature."""

    MEMBERS = ("BindInterfaceClass", "SetItemToolTip", "SetDragonSoulRefineWindow", "Show", "Open", "Close", "Hide",
               "IsShow", "SetTop", "OnTop", "OnPressEscapeKey", "Destroy", "RefreshItemSlot", "OverOutItem",
               "OverInItem", "SelectEmptySlot", "SelectItemSlot", "UseItemSlot", "BindWindow", "SetCantMouseEventCell",
               "SetCanMouseEventCell", "RefreshMarkSlots", "RefreshLockedSlots", "GetOnTopWindow", "OpenMultiUseDialog",
               "IsSafeboxOpen", "GlobalSlotPos", "GetLocalSlotPos", "GetCategory", "GetInventoryPageIndex",
               "GetCategoryRange", "GetPageCount", "SetCategory", "SetInventoryPage", "OnScrollWheel")

    def setUp(self):
        self.world = World(True)
        self.legacy = self.world.m("uiExtraInventory").ExtraInventoryWindow
        self.novaui = self.world.m("nui_extra_inventory").ExtraInventoryWindow

    def test_each_member_exists_with_the_legacy_signature(self):
        self.assertTrue(issubclass(self.novaui, self.legacy))
        self.assertEqual(self.novaui.__name__, self.legacy.__name__)
        self.assertTrue(self.novaui.NUI_FACADE)
        self.assertEqual(inspect.signature(self.novaui.__init__), inspect.signature(self.legacy.__init__))
        for member in self.MEMBERS:
            self.assertTrue(callable(getattr(self.novaui, member, None)), member)
            if member in vars(self.legacy):
                self.assertEqual(inspect.signature(getattr(self.novaui, member)),
                                 inspect.signature(getattr(self.legacy, member)), member)

    def test_every_legacy_method_it_overrides_keeps_its_signature(self):
        for member, value in vars(self.novaui).items():
            if callable(value) and member in vars(self.legacy):
                self.assertEqual(inspect.signature(value), inspect.signature(vars(self.legacy)[member]), member)

    def test_the_loader_override_is_the_name_the_legacy_constructor_calls(self):
        self.assertIn("_ExtraInventoryWindow__LoadWindow", vars(self.novaui))
        self.assertIn("_ExtraInventoryWindow__LoadWindow", vars(self.legacy))


class Wiring(unittest.TestCase):
    def test_interfacemodule_makes_it_through_nui_windows(self):
        text = read(os.path.join(ROOT, "interfacemodule.py"))
        lines = ['wndExtraInventory = nui_windows.make("extra-inventory", uiExtraInventory.ExtraInventoryWindow, '
                 '"nui_extra_inventory.ExtraInventoryWindow")',
                 "wndExtraInventory.BindInterfaceClass(self)",
                 "wndExtraInventory.Hide()"]
        self.assertNotIn(None, support.find_lines(text, lines))
        self.assertNotIn("uiExtraInventory.ExtraInventoryWindow()", text)

    def test_the_window_is_on_by_default_in_the_items_group_and_prewarmed(self):
        world = World(True)
        windows = world.nui_windows
        self.assertIs(dict(windows.WINDOWS)["extra-inventory"], True)
        self.assertIn("extra-inventory", windows.GROUPS["items"])
        self.assertIn(("extra-inventory", ("extra-inventory",)), windows.ON_DEMAND_DOCUMENTS)
        self.assertEqual([window_id for window_id, _ in windows.WINDOWS][-1], "maintenance")


class Model(Pair):
    """What the board shows equals what the legacy slot window shows."""

    def compare(self, flow=None):
        legacy, novaui = self.worlds()
        a, b = legacy.make_extra(), novaui.make_extra()
        if flow is not None:
            for world, window in ((legacy, a), (novaui, b)):
                with world.game, quiet():
                    flow(Input(world, window))
        self.assertEqual(legacy_cells(a), board_cells(b))
        return a, b

    def test_it_opens_on_the_materials_page_i(self):
        a, b = self.compare()
        self.assertEqual(board_cells(b), {0: (ORE, "37"), 4: (PEARL, ""), 5: (BEAN, "54")})
        model = board(b).model
        self.assertEqual((model["category"], model["page"]), (MATERIALS, 0))
        self.assertEqual([p["label"] for p in model["pages"]], ["I", "II", "III", "IV", "V"])
        self.assertEqual([c["ref"] for c in model["cells"][:6] if c["kind"]], [cell(MATERIALS, 0), cell(MATERIALS, 4),
                                                                               cell(MATERIALS, 5)])
        self.assertEqual(set(c["type"] for c in model["cells"] if c["kind"]), {SLOT_EXTRA})

    def test_every_category_and_page(self):
        for category in range(5):
            for page in (0, 1, 4) + ((11,) if category == COSTUMES else ()):
                def flow(i, category=category, page=page):
                    i.category(category)
                    if page:
                        i.page(page)
                with self.subTest(category=category, page=page):
                    a, b = self.compare(flow)
                    model = board(b).model
                    self.assertEqual((model["category"], model["page"]), (category, page))
                    self.assertEqual(len(model["pages"]), 12 if category == COSTUMES else 5)
                    self.assertEqual([tab.down for tab in a.inventoryTab], [tab.down for tab in b.inventoryTab])
                    self.assertEqual([tab.shown for tab in a.inventoryTab], [tab.shown for tab in b.inventoryTab])

    def test_a_tall_costume_covers_its_cell(self):
        a, b = self.compare(lambda i: i.category(COSTUMES))
        cells = board(b).model["cells"]
        self.assertEqual((cells[0]["h"], cells[5]["covered"], cells[5]["ref"]), (2, True, cell(COSTUMES, 0)))

    def test_a_refresh_while_hidden_reaches_the_next_show(self):
        world = World(True)
        window = world.make_extra()
        with world.game, quiet():
            window.Close()
            world.game.give((EXTRA, cell(MATERIALS, 9)), WOOD, 3)
            window.RefreshItemSlot()
            window.Open()
        self.assertEqual(board_cells(window)[9], (WOOD, "3"))


class Flows(Pair):
    """The legacy window's flows, call for call (uiextrainventory.py)."""

    def test_pick(self):
        self.same(lambda w, win, i: i.press(0), expect=["mouse.AttachObject", "snd.PlaySound"])

    def test_move_by_a_second_press(self):
        def flow(w, win, i):
            i.press(0)
            i.press(7)
        legacy, _, _ = self.same(flow, expect=["net.SendItemMovePacket"])
        self.assertIn(("net.SendItemMovePacket", (EXTRA, cell(MATERIALS, 0), EXTRA, cell(MATERIALS, 7), 37)), legacy)

    def test_move_by_a_drag(self):
        def flow(w, win, i):
            i.press(0)
            i.release(8)
        self.same(flow, expect=["net.SendItemMovePacket"])

    def test_a_stack_onto_another_item(self):
        def flow(w, win, i):
            i.press(0)
            i.press(5)
        legacy, _, _ = self.same(flow)
        self.assertIn(("net.SendItemMovePacket", (EXTRA, cell(MATERIALS, 0), EXTRA, cell(MATERIALS, 5), 0)), legacy)

    def test_use_by_a_right_press_and_a_double_click(self):
        legacy, _, _ = self.same(lambda w, win, i: i.press(5, 1), expect=["net.SendItemUsePacket"])
        self.assertIn(("net.SendItemUsePacket", (EXTRA, cell(MATERIALS, 5))), legacy)
        self.same(lambda w, win, i: i.use(5), expect=["net.SendItemUsePacket"])

    def test_ctrl_right_click_transfers_to_the_inventory(self):
        def flow(w, win, i):
            i.keys("DIK_LCONTROL")
            i.press(5, 1)
        legacy, _, _ = self.same(flow)
        self.assertIn(("net.SendItemTransferPacket", (EXTRA, cell(MATERIALS, 5), INVENTORY)), legacy)

    def test_ctrl_right_click_while_trading_adds_to_the_trade(self):
        def trading(game):
            game.trading = True

        def flow(w, win, i):
            i.keys("DIK_LCONTROL")
            i.press(5, 1)
        legacy, _, _ = self.same(flow, with_state(trading))
        self.assertIn(("net.SendExchangeItemAddPacket", (EXTRA, cell(MATERIALS, 5), 0)), legacy)

    def test_shift_right_click_into_the_open_safebox(self):
        def safebox(game):
            game.safebox_open = True

        def flow(w, win, i):
            i.keys("DIK_LSHIFT")
            i.press(5, 1)
        legacy, _, _ = self.same(flow, with_state(safebox))
        self.assertIn(("net.SendSafeboxCheckinPacket", (EXTRA, cell(MATERIALS, 5), 0)), legacy)

    def test_a_bean_into_the_open_dragon_soul_refine_window(self):
        def refine(world, window):
            world.game.dragon_soul_refine.shown = True
        legacy, _, _ = self.same(lambda w, win, i: i.press(5, 1), before=refine, expect=["interface.AutoSetItem"])
        self.assertIn(("interface.AutoSetItem", ((EXTRA, cell(MATERIALS, 5)), 1)), legacy)

    def test_alt_right_click_on_a_stack_of_chests_asks_how_many_and_opens_them(self):
        def flow(w, win, i):
            i.keys("DIK_LALT")
            i.press(3, 1)
            accept_last(w, 5)
        legacy, _, _ = self.same(flow, before=to_category(CHESTS), expect=["uiPickMoney.PickMoneyDialog.Open"])
        self.assertIn(("net.SendItemMultiUsePacket", (EXTRA, cell(CHESTS, 3), 5)), legacy)
        opens = [args for name, args in legacy if name == "uiPickMoney.PickMoneyDialog.Open"]
        self.assertEqual(opens[-1][-1], 7, "the dialog's maximum: the stack, under 1000")

    def test_alt_press_pastes_a_link_and_shift_press_splits(self):
        def link(w, win, i):
            i.keys("DIK_LALT")
            i.press(0)
        self.same(link, expect=["ime.PasteString"])

        def split(w, win, i):
            i.keys("DIK_LSHIFT")
            i.press(0)
            accept_last(w, 10)
        legacy, world, _ = self.same(split, expect=["uiPickMoney.PickMoneyDialog.Open", "mouse.AttachObject"])
        self.assertIn(("mouse.AttachObject", (SLOT_EXTRA, cell(MATERIALS, 0), ORE, 10)), legacy)

    def test_a_key_on_a_box_opens_it(self):
        def flow(w, win, i):
            i.press(1)
            i.press(2)
        legacy, _, _ = self.same(flow, before=to_category(CHESTS))
        self.assertIn(("net.SendItemUseToItemPacket", (EXTRA, cell(CHESTS, 1), EXTRA, cell(CHESTS, 2))), legacy)

    def test_sell(self):
        def selling(game):
            game.cursor = support.APP_CONSTANTS["SELL"]

        def flow(w, win, i):
            i.press(5)
            accept_last(w)
        legacy, _, _ = self.same(flow, with_state(selling), expect=["uiCommon.QuestionDialog.Open"])
        self.assertIn(("net.SendShopSellPacketNew", (cell(MATERIALS, 5), 54, EXTRA)), legacy)

    def test_drops_from_the_inventory_the_safebox_and_the_mall(self):
        for slot_type, name in ((SLOT_INVENTORY, "net.SendItemMovePacket"), (SLOT_SAFEBOX, "net.SendSafeboxCheckoutPacket"),
                                (SLOT_MALL, "net.SendMallCheckoutPacket")):
            with self.subTest(slot_type=slot_type):
                self.same(lambda w, win, i: i.drop(9), before=attach(slot_type, 4, POTION, 10), expect=[name])

    def test_pages_categories_and_the_wheel(self):
        def flow(w, win, i):
            i.page(2)
            i.page(2)
            i.wheel(1)
            i.wheel(-1)
            i.wheel(-1)
            i.category(COSTUMES)
            i.page(11)
            i.wheel(1)
            i.category(MATERIALS)
            i.category(MATERIALS)
        self.same(flow)

    def test_a_hover_shows_the_item_s_tooltip_with_its_window(self):
        def flow(w, win, i):
            i.over(5)
            i.out(5)
        legacy, world, window = self.same(flow)
        self.assertEqual(window.tooltipItem.shown, [("SetInventoryItem", cell(MATERIALS, 5), EXTRA)])

    def test_escape_and_the_close_button_close_it(self):
        self.same(lambda w, win, i: win.OnPressEscapeKey())
        legacy, world, window = self.same(lambda w, win, i: i.close())
        self.assertFalse(window.IsShow())
        self.assertIsNone(board(window))


class Marks(Pair):
    """The trade marks (wave 4b, NOVA-13): the locks of the trade windows the
    Interface binds (BindWindow) and the refusals of the window on top
    (RefreshMarkSlots), shown at once and re-applied after each refresh and
    on OnTop, as legacy sets them on its slot window."""

    class Trade(object):
        """A trade window that holds extra items (the exchange's
        RefreshLockedSlot)."""

        def __init__(self, extra, cells):
            self.extra = extra
            self.cells = cells

        def IsShow(self):
            return True

        def RefreshLockedSlot(self):
            for global_cell in self.cells:
                self.extra.SetCantMouseEventCell(global_cell)

    def test_a_lock_shows_at_once_and_a_release_clears_it(self):
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            window = world.make_extra()
            with world.game, quiet():
                window.SetCantMouseEventCell(cell(MATERIALS, 5))
                window.SetCantMouseEventCell(cell(MATERIALS, 7, page=1))  # not on the page shown
            if world.nui_on:
                self.assertEqual(board_marks(window), {5: (True, False)})
                self.assertEqual(board_marks(window), legacy_marks(legacy_window))
                with world.game, quiet():
                    window.SetCanMouseEventCell(cell(MATERIALS, 5))
                self.assertEqual(board_marks(window), {})
            else:
                legacy_window = window
                self.assertEqual(legacy_marks(window), {5: (True, False)})

    def test_an_in_use_cell_takes_no_press_no_right_press_and_no_double_click(self):
        world = World(True)
        window = world.make_extra()
        with world.game, quiet():
            window.SetCantMouseEventCell(cell(MATERIALS, 5))
            mark = world.mark()
            press(window, "cell_press", 5, 0)
            press(window, "cell_press", 5, 1)
            fire(window, "cell_use", 5)
            self.assertEqual([call for call in world.effects_since(mark) if not call[0].startswith("snd.")], [])
            self.assertFalse(world.mouse.isAttached())
            press(window, "cell_press", 0, 0)
            self.assertTrue(world.mouse.isAttached(), "the other cells take presses")

    def test_the_window_on_top_s_refusals_and_the_locks_after_a_refresh_and_on_top(self):
        def refused(game):
            game.antiflags[BEAN] = game.modules["item"].ANTIFLAG_GIVE
        found = []
        for world in self.worlds(with_state(refused)):
            window = world.make_extra()
            with world.game, quiet():
                window.BindWindow(self.Trade(window, [cell(MATERIALS, 0)]))
                world.game.on_top = world.game.modules["player"].ON_TOP_WND_EXCHANGE
                window.RefreshMarkSlots()
                first = board_marks(window) if world.nui_on else legacy_marks(window)
                window.RefreshItemSlot()
                second = board_marks(window) if world.nui_on else legacy_marks(window)
                world.game.on_top = world.game.modules["player"].ON_TOP_WND_NONE
                window.SetTop()
                third = board_marks(window) if world.nui_on else legacy_marks(window)
            found.append((first, second, third))
        self.assertEqual(found[0], found[1])
        self.assertEqual(found[1], ({5: (False, True)}, {0: (True, False), 5: (False, True)}, {0: (True, False)}))

    def test_after_the_destroy_the_mark_calls_are_legacy_s(self):
        """A logout refreshes the bags' marks after the Interface destroyed
        them (the shop's Destroy runs last), so each mark call on a destroyed
        window is legacy's: nothing marked, nothing raised."""
        calls = []
        for world in self.worlds():
            window = world.make_extra()
            with world.game, quiet():
                window.Destroy()
                mark = world.mark()
                window.RefreshMarkSlots()
                window.SetCantMouseEventCell(cell(MATERIALS, 0))
                window.SetCanMouseEventCell(cell(MATERIALS, 0))
                calls.append(world.effects_since(mark))
        self.assertEqual(calls[0], calls[1])

    def test_a_page_turn_drops_the_marks_and_sets_the_page_s(self):
        world = World(True)
        window = world.make_extra()
        with world.game, quiet():
            window.BindWindow(self.Trade(window, [cell(MATERIALS, 2, page=1)]))
            window.RefreshItemSlot()
            self.assertEqual(board_marks(window), {})
            press(window, "page_press", 1, 0)
        self.assertEqual(board_marks(window), {2: (True, False)})


class KeptBoard(unittest.TestCase):
    """The board is kept, hidden, after its first open (nui_hud.KeptBoard),
    its cells and tabs emptied while it hides."""

    def test_no_document_before_the_first_open_and_kept_hidden_after(self):
        world = World(True)
        window = world.make_extra(show=False)
        self.assertEqual(world.game.loaded_documents(), [])
        with world.game, quiet():
            window.Open()
            made = window.demand.board()
            window.Close()
        self.assertEqual(world.game.loaded_documents(), [DOCUMENT])
        kept = window.demand.kept()
        self.assertIs(kept, made)
        self.assertEqual((kept.model["cells_on"], kept.model["tabs_on"]), ([], []))
        with world.game, quiet():
            window.Open()
        self.assertIs(window.demand.board(), made)
        self.assertEqual((made.model["cells_on"], made.model["tabs_on"]), ([1], [1]))

    def test_destroy_unloads_it_shown_or_kept(self):
        for close in (False, True):
            world = World(True)
            window = world.make_extra()
            with world.game, quiet():
                if close:
                    window.Close()
                window.Destroy()
            self.assertEqual(world.game.loaded_documents(), [], close)

    def test_a_hidden_board_hears_no_stale_hover(self):
        world = World(True)
        window = world.make_extra()
        with world.game, quiet():
            fire(window, "cell_over", 5)
            window.Close()
            window.tooltipItem.shown[:] = []
            window.RefreshItemSlot()
        self.assertEqual(window.tooltipItem.shown, [])


class Placement(unittest.TestCase):
    """Legacy's place at the first show: left of the inventory, 10 apart, its
    top at the inventory's; then where the player left it."""

    class Inventory(object):
        def board_origin(self):
            return (700.0, 120.0)

    def placement(self, world, window):
        return board(window).placement

    def test_beside_the_novaui_inventory(self):
        world = World(True)
        world.interface.wndInventory = self.Inventory()
        window = world.make_extra()
        self.assertEqual(self.placement(world, window), ("position", 690.0, 120.0, (1.0, 0.0)))

    def test_without_one_at_the_legacy_inventory_s_place(self):
        world = World(True)
        window = world.make_extra()
        wndmgr = world.game.modules["wndMgr"]
        self.assertEqual(self.placement(world, window),
                         ("position", wndmgr.GetScreenWidth() - 186.0, wndmgr.GetScreenHeight() - 628.0, (1.0, 0.0)))

    def test_the_place_it_was_moved_to_is_kept(self):
        world = World(True)
        window = world.make_extra()
        world.game.state.boxes[(DOCUMENT, "")] = (300, 200, 346, 487)
        with world.game, quiet():
            window.Close()
            window.Open()
        self.assertEqual(self.placement(world, window), ("position", 300.0, 200.0, (0.0, 0.0)))


class Fixtures(unittest.TestCase):
    """Each fixture fills the board with every key's kind; the controller's
    model has exactly the fixtures' keys; the cells carry the marks."""

    def fixtures(self):
        for file_name in sorted(os.listdir(WINDOW)):
            if file_name.endswith(".fixture.json"):
                yield file_name, json.loads(read(os.path.join(WINDOW, file_name)))

    def test_every_fixture_fills_its_board_and_has_the_controller_s_keys(self):
        world = World(True)
        window = world.make_extra()
        module = world.m("nui_extra_inventory")
        cell_keys = sorted(world.m("nui_slots").CELL_KEYS + world.m("nui_slots").MARK_KEYS + (world.m("nui_slots").GLOW_KEY,))
        names = []
        for file_name, fixture in self.fixtures():
            names.append(file_name)
            (model_name, model), = fixture.items()
            self.assertEqual(model_name, module._ExtraInventoryBoard.MODEL)
            self.assertEqual(sorted(model), sorted(window._state), file_name)
            for key, value in model.items():
                self.assertEqual(type(value), type(window._state[key]), "%s %s" % (file_name, key))
            for entry in model["cells"]:
                self.assertEqual(sorted(entry), cell_keys, file_name)
            mark = world.mark()
            with world.game:
                shown = module._ExtraInventoryBoard(types.SimpleNamespace(), model)
            self.assertEqual(shown.model["cells"], model["cells"])
            self.assertEqual(world.game.log[mark:], [], file_name)
        self.assertEqual(names, ["extra-inventory.costumes.fixture.json", "extra-inventory.fixture.json",
                                 "extra-inventory.marks.fixture.json", "extra-inventory.new-items.fixture.json"])

    def test_the_marks_fixture_has_both_marks_and_the_main_one_a_stack(self):
        fixtures = dict(self.fixtures())
        marks = fixtures["extra-inventory.marks.fixture.json"]["extra_inventory"]["cells"]
        self.assertTrue(any(c["in_use"] for c in marks) and any(c["unusable_ontop"] for c in marks))
        main = fixtures["extra-inventory.fixture.json"]["extra_inventory"]
        self.assertEqual(main["category"], 1, "the category legacy opens on (DEFAULT_CATEGORY)")
        self.assertEqual(main["cells"][3]["count"], "200")


class Document(unittest.TestCase):
    def setUp(self):
        self.text = read(os.path.join(WINDOW, "extra-inventory.rml"))

    def test_the_lean_cell_is_its_icon_its_wash_and_its_number(self):
        match = re.search(r'<div class="nui-slot[^"]*"[^>]*data-for="c : cells".*?data-attr-value="c.count"/>',
                          self.text, re.S)
        self.assertIsNotNone(match)
        template = match.group(0)
        self.assertEqual(re.findall(r"<([a-z-]+)[\s>/]", template), ["div", "img", "div", "nui-number"])
        self.assertIn('<div class="nui-slot__wash" data-if="c.in_use || c.unusable_ontop"></div>', template)
        self.assertIn('data-class-is-in-use="c.in_use" data-class-is-unusable-ontop="c.unusable_ontop"', template)
        self.assertRegex(self.text, r'id="xinv-grid" class="nui-slot-grid nui-slot-grid--lean[ "]')
        self.assertIn('data-class-is-attaching="attaching" data-class-nui-attach-right="attach_right"', self.text)

    def test_no_novaui_part_runs_per_frame(self):
        import ast
        tree = ast.parse(read(os.path.join(ROOT, "nui_extra_inventory.py")))
        defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        self.assertFalse(defined & {"OnUpdate", "OnRender", "OnMouseOverIn"})

    def test_the_goldens_cover_every_theme_scale_and_case(self):
        cases = json.loads(read(os.path.join(WINDOW, "extra-inventory.snapshots.json")))["cases"]
        main = [case for case in cases if "variant" not in case and "name" not in case]
        self.assertEqual(sorted(tuple(case.get("except", ())) for case in main), [(), ("classic",)])
        for case in main:
            self.assertEqual([scale[1] for scale in case["scales"]], ["1", "1.5", "2"])
        self.assertEqual({case.get("variant") for case in cases}, {None, "costumes", "marks", "new-items"})
        names = {case.get("name") for case in cases}
        self.assertTrue({"reduced-motion", "no-effects", "hover", "hover-covered"} <= names)
        self.assertTrue(any(case.get("reduced_motion") for case in cases))
        self.assertTrue(any(case.get("effects") == "off" for case in cases))
        hovered = [case for case in cases if case.get("name") == "hover"]
        self.assertEqual(sorted(theme for case in hovered for theme in case["themes"]), ["classic", "cyber", "dark", "light"])


if __name__ == "__main__":
    unittest.main()
