"""Tests of the NovaUI aura level window (assets/root/nui_aura.py; Wave 6,
NOVA-23): python3 -B -m unittest nui_aura_test (from tools/).

Each flow runs on legacy's uiaura.AuraWindow and on the NovaUI facade in the
same kind of world (nui_w4_world's, with wave6_support's names from chunk C
and the aura world of aura_test), each made by game.BINARY_AuraPacket through
nui_windows.make() and bound by Interface.BindAuraWindow, and the effects
must be the same: the chat commands and the other recorded calls, the
inventories' lock and unlock calls, the tooltip calls. The NovaUI side also
checks what the board shows (the level, the gauge's fraction, the percentage
and the experience line in each state), the walk-away watch, that no Python
runs per frame, the lifecycle, that the loader binds as legacy's does, and
that every fixture has every model key."""

import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402
import wave6_support as w6  # noqa: E402
import sash_test  # noqa: E402

support = w4.support
KEY = "aura"
AURA_CELL, STONE_CELL, OTHER_CELL = 5, 6, 8
EXTRA_STONE_CELL = 230
INVENTORY, EXTRA = 1, 6
MAIN, CLOSE = w6.C_ITEM["AURA_MODE_MAIN"], w6.C_ITEM["AURA_MODE_CLOSE"]
EMPTY = 0xFFFF
MODULES = ("nui_limits", "nui_proxies", "nui_form_proxies", "nui_facade")
# The fill of 450 of 1000 experience: int(188 * 0.45) of 188 pixels.
MID_FILL = 84 / 188.0


class Holder(object):
    """An inventory as BindAuraWindow and the window see it: the tradable
    icon's lock and unlock calls, in order (sash_test.Inventory's half)."""

    def __init__(self, name):
        self.name = name
        self.calls = []
        self.bound = []
        self.wndAura = None

    def SetCantMouseEventCell(self, cell):
        self.calls.append(("lock", self.name, cell))

    def SetCanMouseEventCell(self, cell):
        self.calls.append(("unlock", self.name, cell))

    def BindWindow(self, wnd):
        self.bound.append(wnd)

    def SetAuraWindow(self, wnd):
        self.wndAura = wnd


def handler_name(event):
    """The name of what a widget's event calls: a ui.__mem_func__'s method,
    a bound method, a lambda (nui_dragon_soul_test's)."""
    if event is None:
        return None
    if isinstance(event, tuple):
        event = event[0]
    fn = getattr(event, "fn", event)
    fn = getattr(fn, "__func__", fn)
    return getattr(getattr(fn, "__wrapped__", fn), "__name__", repr(fn))


def setup(game):
    """wave6_support.World's additions over the Wave 4 world: chunk C's
    names, main's special inventory window and slot type and
    SlotTypeToInvenType; then aura_test's items: the aura in cell 5, a stack
    of five materials in cell 6 (also under (INVENTORY, 6), as
    player.GetItemCount(window, cell) asks), a sword in cell 8 and a stack in
    the special inventory's cell 230."""
    w6.install_c(game)
    player = game.modules["player"]
    player.EXTRA_INVENTORY, player.SLOT_TYPE_EXTRA_INVENTORY = EXTRA, 12
    windows = {player.SLOT_TYPE_INVENTORY: player.INVENTORY, 8: 3, 10: 4, 11: 5, 12: 6}
    support.define(player, "SlotTypeToInvenType", lambda slot_type: windows.get(slot_type, 0))
    game.w4["position"] = [1000.0, 2000.0, 0.0]
    game.give(AURA_CELL, w6.AURA)
    game.give(STONE_CELL, w6.AURA_STONE, 5)
    game.give((INVENTORY, STONE_CELL), w6.AURA_STONE, 5)
    game.give(OTHER_CELL, w6.SWORD)
    game.give((EXTRA, EXTRA_STONE_CELL), w6.AURA_STONE, 3)


class World(w4.World):
    """One side of a differential test: the legacy window (nui_on False) or
    the NovaUI one, made by the game window's packet handler and bound by
    the Interface's BindAuraWindow, as the client does."""

    def __init__(self, nui_on):
        w4.World.__init__(self, nui_on, windows="+aura", setup=setup, modules=MODULES)
        game = self.game
        with game, w4.quiet():
            game.load("uiAura", "uiaura.py")
            if nui_on:
                game.load("nui_aura", "nui_aura.py")
        self.inventory, self.extra = Holder("inventory"), Holder("extra")
        Bound = sash_test.compiled("interfacemodule.py", "Interface", ["BindAuraWindow", "__BindItemHolder"])
        self.interface = Bound()
        self.interface.tooltipItem = support.ToolTip("item")
        self.interface.wndInventory = self.inventory
        self.interface.wndExtraInventory = self.extra
        Game = sash_test.compiled("game.py", "GameWindow", ["BINARY_AuraPacket"],
                                  {"item": game.modules["item"], "nui_windows": self.nui_windows})
        self.game_window = Game()
        self.game_window.auraWindow = None
        self.game_window.interface = self.interface

    @property
    def window(self):
        return self.game_window.auraWindow

    @property
    def item_tip(self):
        return self.interface.tooltipItem

    def packet(self, *args):
        with self.game, w4.quiet():
            self.game_window.BINARY_AuraPacket(*args)

    def locks(self):
        return self.inventory.calls + self.extra.calls

    def chat_commands(self):
        return [args[0] for name, args in self.game.log if name == "net.SendChatPacket"]


def model(window):
    return w4.board(window).model


class AuraTest(unittest.TestCase):
    def opened(self, nui_on, *packet):
        world = World(nui_on)
        world.packet(*(packet or (MAIN, 3, AURA_CELL, STONE_CELL, 450, 1000)))
        return world

    def run_both(self, flow, packet=()):
        """flow(world, window) on both sides after the same first packet;
        the effects, the lock calls and the tooltip calls must be equal."""
        results = []
        for nui_on in (False, True):
            world = self.opened(nui_on, *packet)
            mark, locks, tips = world.mark(), len(world.locks()), len(world.item_tip.calls)
            with world.game, w4.quiet():
                flow(world, world.window)
            results.append(((world.effects_since(mark), world.locks()[locks:], world.item_tip.calls[tips:]), world))
        (legacy, _), (novaui, _) = results
        self.assertEqual(novaui, legacy)
        return results

    # --- the board's and legacy's widgets' controls -----------------------------------

    @staticmethod
    def drop(world, window, cell):
        if world.nui_on:
            w4.press(window, "cell_press", cell, 0)
        else:
            window.auraSlot.fire("select_empty", cell)

    @staticmethod
    def right_press(world, window, cell):
        if world.nui_on:
            w4.press(window, "cell_press", cell, 1)
        else:
            window.auraSlot.fire("unselect_item", cell)

    @staticmethod
    def double_click(world, window, cell):
        if world.nui_on:
            w4.fire(window, "cell_use", cell)
        else:
            window.auraSlot.fire("use", cell)

    @staticmethod
    def hover(world, window, cell):
        if world.nui_on:
            w4.fire(window, "cell_over", cell)
        else:
            window.auraSlot.fire("over_in", cell)

    @staticmethod
    def leave(world, window, cell):
        if world.nui_on:
            w4.fire(window, "cell_out", cell)
        else:
            window.auraSlot.fire("over_out")

    @staticmethod
    def accept(world, window):
        if world.nui_on:
            w4.press(window, "accept_press", 0)
        else:
            window.btnAccept.click()

    @staticmethod
    def cancel(world, window):
        if world.nui_on:
            w4.press(window, "cancel_press", 0)
        else:
            window.btnCancel.click()

    @staticmethod
    def close_x(world, window):
        if world.nui_on:
            w4.press(window, "close_press", 0)
        else:
            window.titleBar.close()


class Packets(AuraTest):
    def test_the_first_packet_makes_binds_and_opens_the_window(self):
        sides = []
        for nui_on in (False, True):
            world = World(nui_on)
            world.packet(MAIN, 3, AURA_CELL, STONE_CELL, 450, 1000)
            window = world.window
            self.assertEqual(type(window).__module__, "nui_aura" if nui_on else "uiAura")
            self.assertTrue(window.IsOpened())
            self.assertIs(world.inventory.wndAura, window)
            self.assertIs(world.extra.wndAura, window)
            self.assertEqual((world.inventory.bound, world.extra.bound), ([window], [window]))
            self.assertIs(window.tooltipItem, world.item_tip)
            world.packet(MAIN, 3, AURA_CELL, STONE_CELL, 450, 1000)
            self.assertIs(world.window, window, "made once")
            sides.append((world.chat_commands(), world.locks(), world.item_tip.calls,
                          [e for e in world.effects_since(0) if e[0].startswith(("net.", "mouse."))]))
        self.assertEqual(sides[1], sides[0])

    def test_a_refresh_shows_the_new_state_and_relocks(self):
        def flow(world, window):
            world.game_window.BINARY_AuraPacket(MAIN, 4, AURA_CELL, EMPTY, 0, 2000)
        (_, legacy), (effects, novaui) = self.run_both(flow)
        self.assertEqual(effects[1][-1:], [("lock", "inventory", AURA_CELL)])
        board = model(novaui.window)
        self.assertEqual((board["level"], board["percent"], board["exp"]), ("Level: 4", "0%", "0 / 2.000 EXP"))
        self.assertEqual((board["gauge"], board["fill"]), (True, 0.0))
        self.assertEqual(board["cells"][1]["kind"], "", "the material went")

    def test_the_close_packet_closes_and_releases(self):
        def flow(world, window):
            world.game_window.BINARY_AuraPacket(CLOSE, 0, 0, 0, 0, 0)
            world.game_window.BINARY_AuraPacket(5, 0, AURA_CELL, 0, 0, 0)
        (effects, legacy), (_, novaui) = self.run_both(flow)
        self.assertEqual(sorted(effects[1]), [("unlock", "inventory", AURA_CELL), ("unlock", "inventory", STONE_CELL)])
        for world in (legacy, novaui):
            self.assertFalse(world.window.IsOpened(), "closed; an unknown mode is ignored")
        self.assertIsNone(w4.board(novaui.window), "the board goes with the window")
        self.assertEqual(novaui.chat_commands(), [], "the server's close sends nothing")


class Flows(AuraTest):
    def test_a_drop_from_the_main_and_the_extra_inventory_asks_to_add(self):
        def flow(world, window):
            player = world.game.modules["player"]
            world.attach(player.SLOT_TYPE_INVENTORY, STONE_CELL, w6.AURA_STONE)
            self.drop(world, window, 1)
            world.attach(player.SLOT_TYPE_EXTRA_INVENTORY, EXTRA_STONE_CELL, w6.AURA_STONE)
            self.drop(world, window, 1)
            world.attach(8, 3, w6.AURA_STONE)
            self.drop(world, window, 1)
        packet = (MAIN, 3, AURA_CELL, EMPTY, 450, 1000)
        (_, legacy), (_, novaui) = self.run_both(flow, packet)
        self.assertEqual(novaui.chat_commands(), ["/aura add 1 %d %d" % (INVENTORY, STONE_CELL),
                                                  "/aura add 1 %d %d" % (EXTRA, EXTRA_STONE_CELL)])

    def test_a_right_press_or_a_double_click_on_an_item_asks_to_remove(self):
        def flow(world, window):
            self.right_press(world, window, 0)
            self.double_click(world, window, 1)
        (_, _), (_, novaui) = self.run_both(flow)
        self.assertEqual(novaui.chat_commands(), ["/aura remove 0", "/aura remove 1"])

    def test_accept_asks_to_level(self):
        (_, _), (_, novaui) = self.run_both(self.accept)
        self.assertEqual(novaui.chat_commands(), ["/aura leveling"])
        self.assertTrue(novaui.window.IsOpened(), "accept keeps the window")

    def test_x_cancel_and_escape_close_and_tell_the_server(self):
        for close in (self.close_x, self.cancel, lambda world, window: window.OnPressEscapeKey()):
            (effects, legacy), (_, novaui) = self.run_both(close)
            self.assertEqual(novaui.chat_commands(), ["/aura close"])
            self.assertEqual(sorted(effects[1]), [("unlock", "inventory", AURA_CELL),
                                                  ("unlock", "inventory", STONE_CELL)])
            for world in (legacy, novaui):
                self.assertFalse(world.window.IsOpened())
            self.assertIsNone(w4.board(novaui.window))

    def test_a_hover_shows_the_items_tooltip_with_its_window(self):
        def flow(world, window):
            self.hover(world, window, 0)
            self.leave(world, window, 0)
            self.hover(world, window, 1)
            self.leave(world, window, 1)
        (effects, _), (_, _) = self.run_both(flow)
        self.assertEqual(effects[2], [("SetInventoryItem", AURA_CELL, INVENTORY), ("HideToolTip",),
                                      ("SetInventoryItem", STONE_CELL, INVENTORY), ("HideToolTip",)])

    def test_a_hover_over_an_empty_cell_asks_for_no_tooltip(self):
        world = self.opened(True, MAIN, 3, AURA_CELL, EMPTY, 450, 1000)
        before = len(world.item_tip.calls)
        with world.game, w4.quiet():
            w4.fire(world.window, "cell_over", 1)
            w4.fire(world.window, "cell_out", 1)
        self.assertEqual(world.item_tip.calls[before:], [])

    def test_walking_away_closes_once(self):
        legacy, novaui = World(False), World(True)
        for world in (legacy, novaui):
            world.packet(MAIN, 3, AURA_CELL, STONE_CELL, 450, 1000)
            world.game.w4["position"][1] -= 1000
            with world.game, w4.quiet():
                if world.nui_on:
                    support.leave_range(world.game, KEY)
                    support.leave_range(world.game, KEY)
                else:
                    world.window.OnUpdate()
                    world.window.OnUpdate()
        self.assertEqual(novaui.chat_commands(), legacy.chat_commands())
        self.assertEqual(novaui.chat_commands(), ["/aura close"])
        self.assertEqual(novaui.locks(), legacy.locks())
        self.assertFalse(novaui.window.IsOpened())


class Board(AuraTest):
    def test_the_mid_level_state(self):
        world = self.opened(True)
        board = model(world.window)
        self.assertEqual((board["level"], board["percent"], board["exp"]), ("Level: 3", "45%", "450 / 1.000 EXP"))
        self.assertTrue(board["gauge"])
        self.assertAlmostEqual(board["fill"], MID_FILL)
        cells = board["cells"]
        self.assertEqual([c["kind"] for c in cells], ["item", "item"])
        self.assertEqual([c["count"] for c in cells], ["", "5"], "the material's count above 1, the aura's none")
        self.assertEqual(world.window.expGaugeFill.size, (84, 12), "legacy's pixels on the proxy")

    def test_the_empty_state(self):
        world = self.opened(True, MAIN, 1, EMPTY, EMPTY, 0, 0)
        board = model(world.window)
        self.assertEqual((board["level"], board["percent"], board["exp"]), ("", "", ""))
        self.assertEqual((board["gauge"], board["fill"]), (False, 0.0), "no aura: no gauge")
        self.assertEqual([c["kind"] for c in board["cells"]], ["", ""])
        self.assertEqual(world.locks(), [])

    def test_the_max_state(self):
        world = self.opened(True, MAIN, 250, AURA_CELL, EMPTY, 0, 0)
        board = model(world.window)
        self.assertEqual((board["level"], board["percent"], board["exp"]), ("Level: 250", "MAX", ""))
        self.assertEqual((board["gauge"], board["fill"]), (True, 1.0))

    def test_a_single_material_shows_no_count(self):
        world = World(True)
        world.game.give(STONE_CELL, w6.AURA_STONE, 1)
        world.game.give((INVENTORY, STONE_CELL), w6.AURA_STONE, 1)
        world.packet(MAIN, 3, AURA_CELL, STONE_CELL, 450, 1000)
        self.assertEqual(model(world.window)["cells"][1]["count"], "")

    def test_the_hidden_window_keeps_the_state_for_its_next_show(self):
        world = self.opened(True)
        with world.game, w4.quiet():
            world.window.Close()
        world.packet(MAIN, 5, AURA_CELL, STONE_CELL, 10, 100)
        board = model(world.window)
        self.assertEqual((board["level"], board["percent"]), ("Level: 5", "10%"))
        self.assertAlmostEqual(board["fill"], 18 / 188.0)

    def test_a_drop_target_shows_while_an_item_is_attached(self):
        world = self.opened(True, MAIN, 3, AURA_CELL, EMPTY, 450, 1000)
        player = world.game.modules["player"]
        world.attach(player.SLOT_TYPE_INVENTORY, STONE_CELL, w6.AURA_STONE)
        with world.game, w4.quiet():
            w4.fire(world.window, "cell_over", 1)
        self.assertEqual(model(world.window)["cells"][1]["target"], "move")

    def test_every_fixture_has_every_model_key(self):
        world = self.opened(True)
        keys = w4.model_kinds(model(world.window))
        for variant in ("", "empty", "max"):
            with self.subTest(variant=variant):
                self.assertEqual(w4.fixture_keys(world.window, KEY, variant), keys)
                cells = w4.fixture_model(KEY, variant)["cells"]
                self.assertEqual([sorted(c) for c in cells], [sorted(c) for c in model(world.window)["cells"]])


class NoPerFramePython(AuraTest):
    def test_the_facade_runs_no_python_per_frame(self):
        world = self.opened(True)
        self.assertIsNone(type(world.window).OnUpdate)

    def test_open_arms_the_walk_away_watch_and_hide_stops_it(self):
        world = self.opened(True)
        nuigame = world.game.modules["nuigame"]
        state = nuigame.LeaveRangeState(KEY)
        self.assertIsNotNone(state)
        # Legacy closes at 1000 or more; the watch fires past its range, so the
        # range is the double just under 1000.
        self.assertEqual((state["range"], state["rearm"], state["start"]),
                         (math.nextafter(1000.0, 0.0), False, [1000.0, 2000.0]))
        self.assertTrue(1000.0 > state["range"] and not 999.9999 > state["range"])
        with world.game, w4.quiet():
            world.window.Close()
        self.assertIsNone(nuigame.LeaveRangeState(KEY))
        world.packet(MAIN, 3, AURA_CELL, STONE_CELL, 450, 1000)
        self.assertIsNotNone(nuigame.LeaveRangeState(KEY), "armed again at the next open")


class Lifecycle(AuraTest):
    def test_hide_and_show_before_the_legacy_init_do_not_raise(self):
        """ui.Window.__init__ calls Hide before the legacy __init__ sets its
        attributes; the facade's __init__ runs nui_begin first."""
        world = self.opened(True)
        cls = type(world.window)
        bare = cls.__new__(cls)
        with world.game, w4.quiet():
            bare.nui_begin()
            bare.Hide()
            bare.Show()

    def test_destroy_takes_the_board_and_the_watch(self):
        world = self.opened(True)
        with world.game, w4.quiet():
            world.window.Destroy()
        self.assertIsNone(w4.board(world.window))
        self.assertIsNone(world.game.modules["nuigame"].LeaveRangeState(KEY))

    def test_a_document_that_does_not_load_keeps_the_legacy_window(self):
        world = World(True)
        world.game.modules["nuigame"].lack("WatchLeaveRange", "StopLeaveRange", "LeaveRangeState")
        world.packet(MAIN, 3, AURA_CELL, STONE_CELL, 450, 1000)
        self.assertEqual(type(world.window).__module__, "uiAura", "no Wave 4 engine: the legacy window")


class LoaderBindsAsLegacy(AuraTest):
    """The loader replicates legacy's LoadWindow on proxies: each legacy
    handler is bound to the same event of the same widget in both worlds (a
    binding the peer's uiaura.py changes shows here)."""

    def test_the_bindings(self):
        a, b = self.opened(False).window, self.opened(True).window
        theirs = dict((key, handler_name(value)) for key, value in a.auraSlot.events.items() if value)
        mine = dict((key, handler_name(value)) for key, value in b.auraSlot.handlers().items() if value)
        self.assertEqual(mine, theirs)
        self.assertEqual(handler_name(b.titleBar.close_event), handler_name(a.titleBar.closeEvent))
        for name in ("btnAccept", "btnCancel"):
            self.assertEqual(handler_name(getattr(b, name).event), handler_name(getattr(a, name).event), name)
        for name in ("titleName", "levelText", "expGaugeBG", "expGaugeFill", "expPercentText", "expText"):
            self.assertIsNotNone(getattr(b, name), name)
        self.assertEqual(sorted(a.auraSlot.slots), list(b.auraSlot.slot_numbers))

    def test_the_load_runs_once(self):
        world = self.opened(True)
        window = world.window
        slot = window.auraSlot
        with world.game, w4.quiet():
            window.LoadWindow()
        self.assertIs(window.auraSlot, slot, "isLoaded guards the second load, as legacy's")


if __name__ == "__main__":
    unittest.main()
