"""Tests of the NovaUI sash windows (assets/root/nui_sash.py; Wave 6, NOVA-20):
python3 -B -m unittest nui_sash_test (from tools/).

Each flow runs on legacy's uisash.CombineWindow or AbsorbWindow and on the
NovaUI window in the same world (nui_w4_world's, with chunk C's names and
the sash module of wave6_support.install_c), and the effects must be the
same: the sash module's calls (Add, Remove, SendRefineRequest,
SendCloseRequest), the mouse controller's, the chat lines, the inventory's
lock and unlock calls and the item tooltip's calls. The NovaUI side drives
the board's events (the cells, the buttons, the check box) where legacy's
side drives the uiscript's widgets as the C++ would; it also checks what the
board shows, the loader's bindings against legacy's, the walk-away watch,
the board on demand and the fixtures."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402
import wave6_support as w6  # noqa: E402

support = w4.support
P = w4.P
FLAGS = "+sash"
SASH_IN_BAG, SASH2_IN_BAG, GLAIVE_CELL = 3, 4, 7
GLAIVE = 3010           # a 1 x 3 weapon (its icon is 32 x 96)
KINDS = {"CombineWindow": "nui_sash.CombineWindow", "AbsorbWindow": "nui_sash.AbsorbWindow"}
KEYS = {"CombineWindow": "sash-combine", "AbsorbWindow": "sash-absorb"}
# The calls a flow's effects are made of: the sash module's (no getters), the
# mouse controller's, the chat's, the network's and the inventory's locks.
EFFECT_MODULES = ("sash", "mouse", "chat", "net", "inventory")
TOOLTIP_CALLS = ("SetSashResultItem", "SetSashResultAbsItem", "SetInventoryItem", "HideToolTip")
VARIANTS = ("", "filled", "absorb", "absorb-result")


class Inventory(object):
    """The inventory's half of the tradable icon (NOVA-13): its lock calls go
    to the world's log."""

    def __init__(self, log):
        self.log = log

    def SetCantMouseEventCell(self, cell):
        self.log.append(("inventory.SetCantMouseEventCell", (cell,)))

    def SetCanMouseEventCell(self, cell):
        self.log.append(("inventory.SetCanMouseEventCell", (cell,)))


def _setup(game):
    """Chunk C's names and the sash module (wave6_support.World does the
    same over the legacy foundation world), ui.CheckBox, and main's
    SlotTypeToInvenType."""
    w6.install_c(game)
    ui = game.modules["ui"]
    if not isinstance(getattr(ui, "CheckBox", None), type):
        ui.CheckBox = w6.CheckBox
    player = game.modules["player"]
    player.EXTRA_INVENTORY, player.SLOT_TYPE_EXTRA_INVENTORY = 6, 12
    windows = {player.SLOT_TYPE_INVENTORY: player.INVENTORY, 8: 3, 10: 4, 11: 5, 12: 6}
    support.define(player, "SlotTypeToInvenType", lambda slot_type: windows.get(slot_type, 0))


class SashWorld(w4.World):
    """nui_w4_world's World with uiSash (and nui_sash) loaded; the sash flag
    on for the NovaUI side."""

    def __init__(self, nui_on):
        w4.World.__init__(self, nui_on, windows=FLAGS, setup=_setup)
        self.game.w4["position"] = (1000.0, 2000.0, 0.0)
        with self.game, w4.quiet():
            self.game.load("uiSash", "uisash.py")
            if nui_on:
                self.game.load("nui_sash", "nui_sash.py")
        self.state = self.game.sash_state
        self.inventory = Inventory(self.game.log)

    def window(self, kind, opened=True):
        """The window as Interface.__MakeSashWindow makes it (the absorb
        window loaded after it is made), its tooltip and inventory set, and
        opened (Interface.ActSash(1, ...))."""
        window = self.make("sash", "uiSash", kind, KINDS[kind])
        with self.game, w4.quiet():
            window.Hide()
            if kind == "AbsorbWindow":
                window.LoadWindow()
            window.SetItemToolTip(support.ToolTip("item"))
            window.SetInven(self.inventory)
            if opened:
                window.Open()
        return window

    def effects_since(self, mark, modules=EFFECT_MODULES):
        return [(name, args) for name, args in self.game.log[mark:]
                if name.split(".", 1)[0] in modules and not support.is_getter(name)]

    def walk(self, dx=0.0, dy=0.0):
        x, y, z = self.game.w4["position"]
        self.game.w4["position"] = (x + dx, y + dy, z)


def locked_after(effects):
    """The inventory cells left locked by the lock and unlock calls."""
    locked = set()
    for name, args in effects:
        if name == "inventory.SetCantMouseEventCell":
            locked.add(args[0])
        elif name == "inventory.SetCanMouseEventCell":
            locked.discard(args[0])
    return locked


def tooltip_calls(window):
    return [call for call in window.tooltipItem.calls if call[0] in TOOLTIP_CALLS]


def cell_vnums(world, window):
    """What each of the three slots shows: the legacy slot window's vnums, or
    the proxy's records."""
    if world.nui_on:
        return [window.sashSlot._slots.get(i, {}).get("vnum", 0) for i in range(3)]
    slots = window.GetChild("SashSlot").slots
    return [slots[i]["vnum"] for i in range(3)]


class SashTest(unittest.TestCase):
    KIND = "CombineWindow"

    def opened(self, nui_on, setup=None, kind=None):
        world = SashWorld(nui_on)
        world.state.price = 100000
        if setup is not None:
            setup(world)
        window = world.window(kind or self.KIND)
        return world, window

    def run_both(self, flow, setup=None, kind=None):
        """The flow on legacy's window, then on NovaUI's, from the same state:
        their effects, tooltip calls, shown slots, open state and auto combine
        flag must match. NovaUI's (outcome, world, window)."""
        outcomes = []
        for nui_on in (False, True):
            world, window = self.opened(nui_on, setup, kind)
            constants = world.game.modules["constInfo"]
            constants.SASH_AUTO_COMBINE = False
            mark, tips = world.mark(), len(tooltip_calls(window))
            with world.game, w4.quiet():
                flow(world, window)
            outcomes.append(((world.effects_since(mark), tooltip_calls(window)[tips:], cell_vnums(world, window),
                              bool(window.IsShow()), bool(constants.SASH_AUTO_COMBINE)), world, window))
        (legacy, _, _), (novaui, world, window) = outcomes
        self.assertEqual(novaui, legacy)
        return novaui, world, window

    # --- the two sides' inputs ---------------------------------------------------------

    @staticmethod
    def drop(world, window, slot):
        """A press on an empty slot while a bag item is attached."""
        if world.nui_on:
            w4.press(window, "cell_press", slot, 0)
        else:
            window.GetChild("SashSlot").fire("select_empty", slot)

    @staticmethod
    def legacy_drop(world, window, slot):
        """A drag from a legacy grid released on the slot (NovaUI: nuidrop)."""
        if world.nui_on:
            w4.fire(window, "cell_drop", slot)
        else:
            window.GetChild("SashSlot").fire("select_empty", slot)

    @staticmethod
    def right_press(world, window, slot):
        if world.nui_on:
            w4.press(window, "cell_press", slot, 1)
        else:
            slots = window.GetChild("SashSlot")
            slots.fire("unselect_item" if slots.slots[slot]["vnum"] else "unselect_empty", slot)

    @staticmethod
    def double_click(world, window, slot):
        if world.nui_on:
            w4.fire(window, "cell_use", slot)
        else:
            window.GetChild("SashSlot").fire("use", slot)

    @staticmethod
    def hover(world, window, slot):
        """The pointer enters a slot that holds an item, then leaves it."""
        if world.nui_on:
            w4.fire(window, "cell_over", slot)
            w4.fire(window, "cell_out", slot)
        else:
            slots = window.GetChild("SashSlot")
            slots.fire("over_in", slot)
            slots.fire("over_out")

    @staticmethod
    def button(world, window, name):
        if world.nui_on:
            w4.press(window, name + "_press", 0)
        elif name == "close":
            window.titleBar.close()
        elif name == "auto":
            window.checkBox.OnMouseLeftButtonUp()
        else:
            getattr(window, {"accept": "btnAccept", "cancel": "btnCancel"}[name]).click()

    @staticmethod
    def server_refresh(world, window, attached, result=(0, 0, 0), price=None):
        """GC::SASH's refresh: what the module holds, then Interface.ActSash(3, ...)."""
        world.state.attached = dict(attached)
        world.state.result = result
        if price is not None:
            world.state.price = price
        window.Refresh(3)


def two_sashes(world):
    world.game.give(SASH_IN_BAG, w6.SASH)
    world.game.give(SASH2_IN_BAG, w6.SASH)


def sash_and_glaive(world):
    world.game.give(SASH_IN_BAG, w6.SASH)
    world.game.give(GLAIVE_CELL, GLAIVE, size=(1, 3))


# --- the flows ---------------------------------------------------------------------------------------------

class CombineFlows(SashTest):
    def test_open_shows_the_price_and_empty_slots(self):
        _, world, window = self.run_both(lambda world, window: None)
        model = w4.board(window).model
        self.assertEqual(model["price"], world.game.modules["localeInfo"].SASH_REFINE_COST % 100000)
        self.assertEqual([c["kind"] for c in model["cells"]], ["", "", ""])
        self.assertEqual(model["mode"], "combine")
        self.assertTrue(model["auto_shown"])

    def test_a_bag_item_dropped_on_a_slot_is_added_there(self):
        def flow(world, window):
            world.attach(P["SLOT_TYPE_INVENTORY"], SASH_IN_BAG, w6.SASH)
            self.drop(world, window, 1)
        (effects, _, _, _, _), _, _ = self.run_both(flow)
        self.assertIn(("sash.Add", (P["INVENTORY"], SASH_IN_BAG, 1)), effects)

    def test_a_drag_released_from_a_legacy_grid_is_added_too(self):
        def flow(world, window):
            world.attach(P["SLOT_TYPE_INVENTORY"], SASH2_IN_BAG, w6.SASH)
            self.legacy_drop(world, window, 0)
        (effects, _, _, _, _), _, _ = self.run_both(flow)
        self.assertIn(("sash.Add", (P["INVENTORY"], SASH2_IN_BAG, 0)), effects)

    def test_nothing_is_added_on_the_result_slot_or_from_another_window(self):
        def flow(world, window):
            world.attach(P["SLOT_TYPE_INVENTORY"], SASH_IN_BAG, w6.SASH)
            self.drop(world, window, 2)
            world.attach(P["SLOT_TYPE_SAFEBOX"], 5, w6.SASH)
            self.drop(world, window, 0)
        (effects, _, _, _, _), _, _ = self.run_both(flow)
        self.assertFalse([e for e in effects if e[0] == "sash.Add"])

    def test_a_right_click_in_the_bag_adds_to_the_server_s_first_free_slot(self):
        (effects, _, _, _, _), _, _ = self.run_both(
            lambda world, window: window.AddItem(P["INVENTORY"], SASH_IN_BAG))
        self.assertEqual(effects, [("sash.Add", (P["INVENTORY"], SASH_IN_BAG, 255))])

    def test_the_server_s_refresh_shows_both_sashes_the_result_and_locks_their_cells(self):
        def flow(world, window):
            self.server_refresh(world, window, {0: (True, SASH_IN_BAG), 1: (True, SASH2_IN_BAG)},
                                (w6.SASH_NEXT, 5, 10), 250000)
        (effects, _, vnums, _, _), world, window = self.run_both(flow, setup=two_sashes)
        self.assertEqual(vnums, [w6.SASH, w6.SASH, w6.SASH_NEXT])
        self.assertEqual([e for e in effects if e[0].startswith("inventory.")],
                         [("inventory.SetCantMouseEventCell", (SASH_IN_BAG,)),
                          ("inventory.SetCantMouseEventCell", (SASH2_IN_BAG,))])
        model = w4.board(window).model
        self.assertEqual([c["kind"] for c in model["cells"]], ["item"] * 3)
        self.assertEqual(model["cells"][2]["icon"], "/icon/item/%05d.tga" % w6.SASH_NEXT)
        self.assertEqual(model["price"], world.game.modules["localeInfo"].SASH_REFINE_COST % 250000)

    def test_a_right_press_or_a_double_click_takes_an_item_out(self):
        def flow(world, window):
            self.server_refresh(world, window, {0: (True, SASH_IN_BAG), 1: (True, SASH2_IN_BAG)})
            self.right_press(world, window, 1)
            self.double_click(world, window, 0)
            self.right_press(world, window, 2)
        (effects, _, _, _, _), _, _ = self.run_both(flow, setup=two_sashes)
        self.assertEqual([e for e in effects if e[0] == "sash.Remove"], [("sash.Remove", (1,)), ("sash.Remove", (0,))])
        self.assertEqual(locked_after(effects), set(), "the first sash takes the second out with it")

    def test_a_right_press_while_an_item_is_attached_takes_the_item_out_and_drops_the_attach(self):
        """P15 F-2: CSlotWindow sends the unselect event whatever is attached."""
        def flow(world, window):
            self.server_refresh(world, window, {0: (True, SASH_IN_BAG)})
            world.attach(P["SLOT_TYPE_INVENTORY"], SASH2_IN_BAG, w6.SASH)
            self.right_press(world, window, 0)
        (effects, _, _, _, _), world, _ = self.run_both(flow, setup=two_sashes)
        self.assertIn(("sash.Remove", (0,)), effects)
        self.assertFalse(world.mouse.isAttached())

    def test_accept_sends_the_refine_with_and_without_auto_combine(self):
        def flow(world, window):
            self.button(world, window, "accept")
            self.button(world, window, "auto")
            self.button(world, window, "accept")
            self.button(world, window, "auto")
            self.button(world, window, "accept")
        (effects, _, _, _, auto), _, window = self.run_both(flow)
        self.assertEqual([e for e in effects if e[0].startswith("sash.")],
                         [("sash.SendRefineRequest", (False,)), ("sash.SendRefineRequest", (True,)),
                          ("sash.SendRefineRequest", (False,))])
        self.assertFalse(auto)

    def test_the_check_box_shows_its_state(self):
        world, window = self.opened(True)
        constants = world.game.modules["constInfo"]
        constants.SASH_AUTO_COMBINE = False
        with world.game, w4.quiet():
            self.button(world, window, "auto")
        self.assertTrue(constants.SASH_AUTO_COMBINE)
        self.assertTrue(w4.board(window).model["auto_combine"])
        with world.game, w4.quiet():
            self.button(world, window, "auto")
        self.assertFalse(w4.board(window).model["auto_combine"])

    def test_close_cancel_and_escape_ask_the_server_to_close_and_release_the_cells(self):
        for leave in ("close", "cancel", "escape"):
            def flow(world, window, leave=leave):
                self.server_refresh(world, window, {0: (True, SASH_IN_BAG)})
                if leave == "escape":
                    self.assertTrue(window.OnPressEscapeKey())
                else:
                    self.button(world, window, leave)
            with self.subTest(leave=leave):
                (effects, _, _, shown, _), _, _ = self.run_both(flow, setup=two_sashes)
                self.assertEqual([e for e in effects if e[0].startswith("sash.")], [("sash.SendCloseRequest", ())])
                self.assertEqual(effects[-1], ("inventory.SetCanMouseEventCell", (SASH_IN_BAG,)))
                self.assertTrue(shown, "the window stays until the server closes it")

    def test_the_server_s_close_hides_the_window_sends_nothing_and_takes_the_board(self):
        def flow(world, window):
            self.server_refresh(world, window, {0: (True, SASH_IN_BAG)})
            self.hover(world, window, 0)
            window.Close()
        (effects, tips, _, shown, _), world, window = self.run_both(flow, setup=two_sashes)
        self.assertFalse([e for e in effects if e[0].startswith("sash.")])
        self.assertFalse(shown)
        self.assertEqual(tips[-1], ("HideToolTip",))
        self.assertIsNone(w4.board(window))
        self.assertIsNone(world.game.modules["nuigame"].LeaveRangeState(KEYS[self.KIND]))

    def test_the_result_and_the_material_tooltips(self):
        def flow(world, window):
            self.server_refresh(world, window, {0: (True, SASH_IN_BAG), 1: (True, SASH2_IN_BAG)}, (w6.SASH_NEXT, 5, 10))
            self.hover(world, window, 2)
            self.hover(world, window, 0)
        (_, tips, _, _, _), _, _ = self.run_both(flow, setup=two_sashes)
        self.assertEqual(tips, [("SetSashResultItem", SASH_IN_BAG), ("HideToolTip",),
                                ("SetInventoryItem", SASH_IN_BAG), ("HideToolTip",)])


class AbsorbFlows(SashTest):
    KIND = "AbsorbWindow"

    def test_open_shows_no_price_and_no_check_box(self):
        _, world, window = self.run_both(lambda world, window: None)
        model = w4.board(window).model
        self.assertEqual((model["mode"], model["price"], model["auto_shown"]), ("absorb", "", False))
        self.assertFalse(hasattr(window, "checkBox"))

    def test_the_sash_and_the_item_and_the_result(self):
        def flow(world, window):
            world.attach(P["SLOT_TYPE_INVENTORY"], SASH_IN_BAG, w6.SASH)
            self.drop(world, window, 0)
            world.attach(P["SLOT_TYPE_INVENTORY"], GLAIVE_CELL, GLAIVE)
            self.drop(world, window, 1)
            self.server_refresh(world, window, {0: (True, SASH_IN_BAG), 1: (True, GLAIVE_CELL)}, (w6.SASH, 0, 0))
            self.hover(world, window, 2)
            self.hover(world, window, 1)
        (effects, tips, vnums, _, _), _, window = self.run_both(flow, setup=sash_and_glaive)
        self.assertEqual([e for e in effects if e[0] == "sash.Add"],
                         [("sash.Add", (P["INVENTORY"], SASH_IN_BAG, 0)), ("sash.Add", (P["INVENTORY"], GLAIVE_CELL, 1))])
        self.assertEqual(vnums, [w6.SASH, GLAIVE, w6.SASH])
        self.assertEqual(tips, [("SetSashResultAbsItem", SASH_IN_BAG, GLAIVE_CELL), ("HideToolTip",),
                                ("SetInventoryItem", GLAIVE_CELL), ("HideToolTip",)])
        cells = w4.board(window).model["cells"]
        self.assertEqual((cells[1]["w"], cells[1]["h"]), (1, 3), "the glaive's icon at its own height")

    def test_accept_sends_the_refine_without_an_argument(self):
        (effects, _, _, _, _), _, _ = self.run_both(lambda world, window: self.button(world, window, "accept"))
        self.assertEqual([e for e in effects if e[0].startswith("sash.")], [("sash.SendRefineRequest", ())])

    def test_cancel_asks_the_server_to_close(self):
        (effects, _, _, _, _), _, _ = self.run_both(lambda world, window: self.button(world, window, "cancel"))
        self.assertEqual([e for e in effects if e[0].startswith("sash.")], [("sash.SendCloseRequest", ())])


# --- no Python per frame: the walk-away -------------------------------------------------------------------------

class WalkAway(SashTest):
    """Legacy's OnUpdate runs OnClose once when the character is 1000 units or
    more from the open position on either axis; the watch fires past its
    range, the 32-bit float just under 1000 (the engine keeps the range as a
    float)."""

    def test_the_range_is_the_float_just_under_legacy_s_limit(self):
        import struct
        world = SashWorld(True)
        module = world.game.loaded["nui_sash"]
        as_float = lambda value: struct.unpack("<f", struct.pack("<f", value))[0]
        for limit in (1000, 500, 1):
            below = module.below_as_float(limit)
            with self.subTest(limit=limit):
                self.assertEqual(as_float(below), below, "a float, kept as it is by the engine's cast")
                self.assertLess(below, limit)
                bits = struct.unpack("<I", struct.pack("<f", below))[0]
                self.assertEqual(struct.unpack("<f", struct.pack("<I", bits + 1))[0], float(limit),
                                 "no float between it and the limit: |d| > it is |d| >= the limit")
        import math
        self.assertEqual(as_float(math.nextafter(1000.0, 0.0)), 1000.0,
                         "the double just under 1000 rounds back to 1000 as the engine's float")

    def walk_and_tick(self, world, window, dx, dy=0.0):
        world.walk(dx, dy)
        if not world.nui_on:
            window.OnUpdate()
            return
        # NuiRangeWatch's Tick (NuiRangeWatch.h): |x - x0| > range or |y - y0| > range.
        nuigame = world.game.modules["nuigame"]
        state = nuigame.LeaveRangeState(window.KEY)
        if state is None:
            return
        x, y, _ = world.game.w4["position"]
        if abs(x - state["start"][0]) > state["range"] or abs(y - state["start"][1]) > state["range"]:
            support.leave_range(world.game, window.KEY)

    def test_walking_away_closes_once(self):
        for kind in ("CombineWindow", "AbsorbWindow"):
            def flow(world, window):
                # Each step's mark in the effects: the close comes at exactly
                # 1000 units, once.
                for step, (dx, dy) in enumerate(((999.5, 0), (0.5, 0), (5, 0), (-2000, 1500))):
                    self.walk_and_tick(world, window, dx, dy)
                    world.game.log.append(("chat.step", (step,)))
            with self.subTest(kind=kind):
                (effects, _, _, shown, _), _, _ = self.run_both(flow, kind=kind)
                self.assertEqual(effects, [("chat.step", (0,)), ("sash.SendCloseRequest", ()), ("chat.step", (1,)),
                                           ("chat.step", (2,)), ("chat.step", (3,))])
                self.assertTrue(shown, "the server closes it")

    def test_the_y_axis_counts_too(self):
        def flow(world, window):
            self.walk_and_tick(world, window, 0, -1000)
        (effects, _, _, _, _), _, _ = self.run_both(flow)
        self.assertEqual([e for e in effects if e[0].startswith("sash.")], [("sash.SendCloseRequest", ())])

    def test_open_arms_the_watch_from_the_open_position_and_hide_stops_it(self):
        world, window = self.opened(True)
        nuigame = world.game.modules["nuigame"]
        state = nuigame.LeaveRangeState("sash-combine")
        self.assertEqual(state["start"], [1000.0, 2000.0])
        self.assertEqual(state["range"], 999.99993896484375, "the 32-bit float just under 1000")
        self.assertFalse(state["rearm"], "silent after it fired, as legacy's PositionOut")
        with world.game, w4.quiet():
            window.Close()
        self.assertIsNone(nuigame.LeaveRangeState("sash-combine"))
        world.walk(-500, 0)
        with world.game, w4.quiet():
            window.Open()
        self.assertEqual(nuigame.LeaveRangeState("sash-combine")["start"], [500.0, 2000.0], "armed again where it opens")

    def test_each_window_has_its_own_watch(self):
        world = SashWorld(True)
        combine = world.window("CombineWindow")
        absorb = world.window("AbsorbWindow", opened=False)
        nuigame = world.game.modules["nuigame"]
        self.assertIsNotNone(nuigame.LeaveRangeState("sash-combine"))
        self.assertIsNone(nuigame.LeaveRangeState("sash-absorb"))
        with world.game, w4.quiet():
            absorb.Close()
        self.assertIsNotNone(nuigame.LeaveRangeState("sash-combine"), "the other window's Hide leaves it")
        with world.game, w4.quiet():
            combine.Destroy()
        self.assertIsNone(nuigame.LeaveRangeState("sash-combine"))

    def test_the_windows_run_no_python_per_frame(self):
        world = SashWorld(True)
        for kind in ("CombineWindow", "AbsorbWindow"):
            window = world.window(kind, opened=False)
            self.assertIsNone(type(window).OnUpdate, kind)
            self.assertIsNone(type(window).OnRender, kind)


# --- the loader --------------------------------------------------------------------------------------------------

def handler_name(event):
    """The name of what a widget's event calls: a ui.__mem_func__'s method,
    a bound method, a lambda."""
    if event is None:
        return None
    if isinstance(event, tuple):
        event = event[0]
    fn = getattr(event, "fn", event)
    fn = getattr(fn, "__func__", fn)
    return getattr(getattr(fn, "__wrapped__", fn), "__name__", repr(fn))


class LoaderBindsAsLegacy(SashTest):
    """LoadWindow is a replica of legacy's: each legacy handler is bound to
    the same event of the same widget in both worlds, so a binding the peer
    changes in uisash.py shows here."""

    def test_both_windows(self):
        for kind in ("CombineWindow", "AbsorbWindow"):
            with self.subTest(kind=kind):
                a = SashWorld(False).window(kind, opened=False)
                b = SashWorld(True).window(kind, opened=False)
                theirs = dict((key, handler_name(value)) for key, value in a.sashSlot.events.items() if value)
                mine = dict((key, handler_name(value)) for key, value in b.sashSlot.handlers().items() if value)
                self.assertEqual(mine, theirs)
                self.assertEqual(handler_name(b.titleBar.close_event), handler_name(a.titleBar.closeEvent))
                self.assertEqual(handler_name(b.btnAccept.event), handler_name(a.btnAccept.event))
                self.assertEqual(handler_name(b.btnCancel.event), handler_name(a.btnCancel.event))
                self.assertEqual(sorted(b.sashSlot.slot_numbers), sorted(a.sashSlot.slots))
                self.assertEqual((b.isLoaded, b.IsOpened()), (a.isLoaded, a.IsOpened()))

    def test_the_combine_window_s_children_and_check_box(self):
        a = SashWorld(False).window("CombineWindow", opened=False)
        b = SashWorld(True).window("CombineWindow", opened=False)
        for name in ("needMoney", "Result", "checkBox"):
            self.assertTrue(hasattr(b, name), name)
        self.assertEqual(b.Result.GetText(), a.Result.text)
        self.assertEqual(dict((k, handler_name(v)) for k, v in b.checkBox.events.items()),
                         dict((k, handler_name(v)) for k, v in a.checkBox.events.items()))
        self.assertEqual((b.checkBox.checked, b.checkBox.text, b.checkBox.shown),
                         (a.checkBox.checked, a.checkBox.text, a.checkBox.shown))

    def test_the_uiscript_style(self):
        """The uiscripts' "movable" and "float" on the 0 x 0 legacy window, so
        its SetTop raises it and the board (RaisesOnPress)."""
        for kind in ("CombineWindow", "AbsorbWindow"):
            a = SashWorld(False).window(kind, opened=False)
            b = SashWorld(True).window(kind, opened=False)
            self.assertEqual(b.flags, a.flags, kind)
            self.assertEqual(b.flags, {"movable", "float"}, kind)


# --- the board -------------------------------------------------------------------------------------------------------

class Board(SashTest):
    def test_the_board_exists_only_while_the_window_shows(self):
        world = SashWorld(True)
        window = world.window("CombineWindow", opened=False)
        self.assertIsNone(w4.board(window))
        with world.game, w4.quiet():
            window.Open()
        self.assertIsNotNone(w4.board(window))
        with world.game, w4.quiet():
            window.Close()
        self.assertIsNone(w4.board(window))

    def test_the_two_windows_bind_their_own_models(self):
        world = SashWorld(True)
        combine = world.window("CombineWindow")
        absorb = world.window("AbsorbWindow")
        self.assertNotEqual(w4.board(combine).MODEL, w4.board(absorb).MODEL)
        self.assertEqual((w4.board(combine).model["mode"], w4.board(absorb).model["mode"]), ("combine", "absorb"))

    def test_a_refresh_while_hidden_reaches_the_next_board(self):
        world = SashWorld(True)
        world.game.give(SASH_IN_BAG, w6.SASH)
        window = world.window("CombineWindow", opened=False)
        world.state.attached = {0: (True, SASH_IN_BAG)}
        with world.game, w4.quiet():
            window.Refresh(3)
            window.Show()
        self.assertEqual(w4.board(window).model["cells"][0]["kind"], "item")

    def test_a_hovered_target_while_attached(self):
        world, window = self.opened(True)
        world.attach(P["SLOT_TYPE_INVENTORY"], SASH_IN_BAG, w6.SASH)
        with world.game, w4.quiet():
            w4.fire(window, "cell_over", 1)
        self.assertEqual([c["target"] for c in w4.board(window).model["cells"]], ["", "move", ""])
        with world.game, w4.quiet():
            w4.fire(window, "cell_out", 1)
        self.assertEqual([c["target"] for c in w4.board(window).model["cells"]], ["", "", ""])

    def test_every_fixture_has_every_model_key(self):
        world, window = self.opened(True)
        model = w4.board(window).model
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                self.assertEqual(w4.fixture_keys(window, "sash", variant), w4.model_kinds(model))

    def test_the_fixtures_are_what_the_proxies_give(self):
        """Each fixture's cells, price and check box against the window's own
        model after legacy's Open and Refresh, the icon paths aside."""
        def cells_of(model):
            return [dict((k, v) for k, v in c.items() if k != "icon") for c in model["cells"]]

        def filled(world):
            two_sashes(world)
        world, window = self.opened(True, setup=filled)
        with world.game, w4.quiet():
            window.checkBox.click()
            self.server_refresh(world, window, {0: (True, SASH_IN_BAG), 1: (True, SASH2_IN_BAG)},
                                (w6.SASH_NEXT, 5, 10), 250000)
            window.checkBox.click()
        fixture = w4.fixture_model("sash", "filled")
        model = w4.board(window).model
        self.assertEqual(cells_of(model), cells_of(fixture))
        self.assertEqual(model["price"], fixture["price"])

        world, window = self.opened(True, setup=sash_and_glaive, kind="AbsorbWindow")
        with world.game, w4.quiet():
            self.server_refresh(world, window, {0: (True, SASH_IN_BAG), 1: (True, GLAIVE_CELL)}, (w6.SASH, 0, 0))
        fixture = w4.fixture_model("sash", "absorb-result")
        model = w4.board(window).model
        self.assertEqual(cells_of(model), cells_of(fixture))
        self.assertEqual((model["price"], model["auto_shown"]), (fixture["price"], fixture["auto_shown"]))


class Lifecycle(SashTest):
    def test_hide_and_show_before_the_legacy_init_do_not_raise(self):
        """ui.Window.__init__ calls Hide before the legacy __init__ sets its
        attributes; the window's __init__ runs nui_begin first."""
        world = SashWorld(True)
        for kind in ("CombineWindow", "AbsorbWindow"):
            window = world.window(kind, opened=False)
            cls = type(window)
            bare = cls.__new__(cls)
            with world.game, w4.quiet():
                bare.nui_begin()
                bare.Hide()
                bare.Show()

    def test_make_gives_the_novaui_windows_with_the_flag_and_legacy_s_without(self):
        on, off = SashWorld(True), SashWorld(False)
        for kind in ("CombineWindow", "AbsorbWindow"):
            self.assertEqual(type(on.window(kind, opened=False)).__module__, "nui_sash")
            self.assertIs(type(off.window(kind, opened=False)), getattr(off.m("uiSash"), kind))

    def test_both_windows_live_side_by_side(self):
        """Both are made under the window id "sash": each keeps its NovaUI
        parts (its own take-over key)."""
        world = SashWorld(True)
        combine = world.window("CombineWindow", opened=False)
        absorb = world.window("AbsorbWindow", opened=False)
        with world.game:
            self.assertTrue(combine.nui_ready() and absorb.nui_ready())
        self.assertFalse(combine._nui_discarded or absorb._nui_discarded)

    def test_destroy_takes_the_board_and_releases_the_cells(self):
        world, window = self.opened(True, setup=two_sashes)
        with world.game, w4.quiet():
            self.server_refresh(world, window, {0: (True, SASH_IN_BAG)})
            mark = world.mark()
            window.Destroy()
        self.assertIsNone(w4.board(window))
        self.assertIn(("inventory.SetCanMouseEventCell", (SASH_IN_BAG,)), world.effects_since(mark))


if __name__ == "__main__":
    unittest.main()
