"""Tests for the NovaUI exchange (assets/root/nui_exchange.py, P16 spec 5.1):
python3 -B -m unittest nui_exchange_test (from tools/).

The legacy uiExchange.ExchangeDialog (made from its real uiscript by
nui_game_support's stand-ins) and the NovaUI one, each in a world of its own
with the same state (nui_w4_world.World), driven through every flow of spec
5.1.4: the legacy slot window's C++ events against the board's data events.
They make the same W4_COMPARED calls in the same order (getters left out),
and the board shows what legacy's widgets show. Legacy's
wndMgr.OnceIgnoreMouseLeftButtonUpEvent() in CloseDialog is the one
difference (spec 2.1)."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402

P = w4.P
I = support.module_constants()["item"]
DOCUMENT = "nui/windows/exchange/exchange.rml"
IGNORE = "wndMgr.OnceIgnoreMouseLeftButtonUpEvent"
SWORD, GLAIVE, POTION, HELMET, AUTO_HP, SOUL = 10, 3000, 27001, 12200, 72723, 110000


def stock(game):
    """The tester's inventory: a sword at 0, a potion stack at 4, a helmet at
    9, an active auto potion at 12, an untradable ring at 13; 5.000.000 Yang;
    a dragon soul stone at dragon soul 3. The trade: the partner (Partner)
    put a glaive at 0 and 30.000 Yang; the tester a helmet at 2."""
    game.give(0, SWORD, size=(1, 2))
    game.give(4, POTION, 50)
    game.give(9, HELMET)
    game.give(12, AUTO_HP, 1, sockets=(1, 200, 1000))
    game.give(13, 70043)
    game.give((P["DRAGON_SOUL_INVENTORY"], 3), SOUL)
    game.item_sizes[GLAIVE] = (1, 3)
    game.antiflags[70043] = I["ANTIFLAG_GIVE"]
    game.elk = 5000000
    w4.mirror_inventory(game)
    ex = game.w4["exchange"]
    ex["target"][0] = {"vnum": GLAIVE, "count": 1}
    ex["target_elk"] = 30000
    ex["self"][2] = {"vnum": HELMET, "count": 1}
    ex["target_name"] = "Partner"


class ExchangeTest(unittest.TestCase):
    def world(self, nui_on, setup=stock, **kwargs):
        world = w4.World(nui_on, setup=setup, **kwargs)
        window = world.make("exchange", "uiExchange", "ExchangeDialog", "nui_exchange.ExchangeDialog")
        with world.game, w4.quiet():
            window.LoadDialog()
            window.SetCenterPosition()
            window.Hide()
            window.SetItemToolTip(world.tooltip)
        return world, window

    def worlds(self, setup=stock):
        return self.world(False, setup), self.world(True, setup)

    def open(self, world, window):
        """Interface.StartExchange (interfacemodule.py:714-716)."""
        with world.game, w4.quiet():
            window.OpenDialog()
            window.Refresh()

    def legacy_cells(self, slots):
        """{cell: (vnum, count label)} of a legacy slot window."""
        return dict((index, (vnum, count)) for index, (vnum, count, _) in slots.shown().items())

    def board_cells(self, window, key):
        board = w4.board(window)
        model = board.model if board is not None else window._state
        vnums = (window.OwnerSlot if key == "owner_cells" else window.TargetSlot).vnums()
        return dict((cell["index"], (vnums[cell["index"]], cell["count"])) for cell in model[key] if cell["kind"] == "item")

    def run_both(self, flow, setup=stock, opened=True):
        results = []
        for world, window in self.worlds(setup):
            if opened:
                self.open(world, window)
            mark = world.mark()
            with world.game, w4.quiet():
                flow(world, window)
            results.append((world.effects_since(mark), world, window))
        return results


class Model(ExchangeTest):
    def test_the_board_shows_what_legacy_s_widgets_show(self):
        (legacy, a), (novaui, b) = self.worlds()
        self.open(legacy, a)
        self.open(novaui, b)
        model = w4.board(b).model
        self.assertEqual(self.board_cells(b, "owner_cells"), self.legacy_cells(a.OwnerSlot))
        self.assertEqual(self.board_cells(b, "target_cells"), self.legacy_cells(a.TargetSlot))
        self.assertEqual(model["title"], a.TitleName.GetText())
        self.assertEqual(model["title"], "Trade with Partner")
        self.assertEqual((model["owner_money"], model["target_money"]), (a.OwnerMoney.GetText(), a.TargetMoney.GetText()))
        self.assertEqual(model["target_money"], "30.000")
        self.assertEqual(model["target_money_value"], 30000)
        self.assertEqual(model["cols"], 4)
        self.assertEqual(len(model["owner_cells"]), 12)
        covered = [cell["index"] for cell in model["target_cells"] if cell["covered"]]
        self.assertEqual(covered, [4, 8], "the glaive's 1x3 from cell 0")
        self.assertEqual(model["target_cells"][0]["type"], P["SLOT_TYPE_EXCHANGE_TARGET"])
        self.assertEqual(model["owner_cells"][2]["type"], P["SLOT_TYPE_EXCHANGE_OWNER"])
        self.assertEqual((model["accept_down"], model["accept_enabled"], model["owner_accept"], model["target_accept"]),
                         (False, True, False, False))

    def test_the_accept_states_follow_legacy_s_refresh(self):
        def flow(world, window):
            world.game.w4["exchange"]["target_accept"] = True
            window.Refresh()
        (_, _, a), (_, _, b) = self.run_both(flow)
        model = w4.board(b).model
        self.assertTrue(model["target_accept"])
        self.assertFalse(model["owner_accept"])
        self.assertEqual(a.TargetAcceptLight.calls[-1:], [("Down",)])

    def test_the_money_is_formatted_as_legacy_s_inline_rule(self):
        def setup(game):
            stock(game)
            game.w4["exchange"]["self_elk"] = 1999999999999
        (_, _, a), (_, _, b) = self.run_both(lambda world, window: None, setup)
        self.assertEqual(w4.board(b).model["owner_money"], a.OwnerMoney.GetText())
        self.assertEqual(w4.board(b).model["owner_money"], "1.999.999.999.999", "64-bit money, 13 digits")


class Flows(ExchangeTest):
    def drop(self, world, window, cell):
        """A drop on an owner cell: the C++ slot window's select event (a press
        while something is attached), the board's owner_press."""
        if world.nui_on:
            w4.press(window, "owner_press", cell, 0)
            return
        window.SetTop()
        slots = window.OwnerSlot
        slot = slots.slots.get(cell)
        slots.fire("select_item" if slot and slot["vnum"] else "select_empty", cell)

    def test_an_inventory_item_on_an_empty_cell_sends_the_item_add_packet(self):
        def flow(world, window):
            world.attach(P["SLOT_TYPE_INVENTORY"], 0, SWORD)
            self.drop(world, window, 7)
        (legacy, _, _), (novaui, world, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertIn(("net.SendExchangeItemAddPacket", (P["INVENTORY"], 0, 7)), novaui)
        self.assertFalse(world.mouse.isAttached())

    def test_the_server_s_cell_wins_over_the_drop_target(self):
        """NOVA-84 (D7): the drop at cell 7 is answered at cell 0; only cell 0
        shows the sword."""
        def flow(world, window):
            world.attach(P["SLOT_TYPE_INVENTORY"], 0, SWORD)
            self.drop(world, window, 7)
            self.assertEqual(self.board_cells(window, "owner_cells") if world.nui_on else self.legacy_cells(window.OwnerSlot),
                             {2: (HELMET, "")}, "nothing at the drop cell before the server answers")
            world.game.w4["exchange"]["self"][0] = {"vnum": SWORD, "count": 1}
            window.Refresh()
        (_, _, a), (_, _, b) = self.run_both(flow)
        self.assertEqual(self.board_cells(b, "owner_cells"), {0: (SWORD, ""), 2: (HELMET, "")})
        self.assertEqual(self.board_cells(b, "owner_cells"), self.legacy_cells(a.OwnerSlot))
        self.assertTrue(w4.board(b).model["owner_cells"][4]["covered"])
        self.assertFalse(w4.board(b).model["owner_cells"][7]["kind"])

    def test_an_active_auto_potion_is_used_first(self):
        def flow(world, window):
            world.attach(P["SLOT_TYPE_INVENTORY"], 12, AUTO_HP)
            self.drop(world, window, 5)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        sends = [call for call in novaui if call[0].startswith("net.")]
        self.assertEqual(sends, [("net.SendItemUsePacket", (12,)), ("net.SendExchangeItemAddPacket", (P["INVENTORY"], 12, 5))])

    def test_an_item_that_cannot_be_given_is_refused(self):
        def flow(world, window):
            world.attach(P["SLOT_TYPE_INVENTORY"], 13, 70043)
            self.drop(world, window, 5)
        (legacy, _, _), (novaui, world, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertNotIn("net.SendExchangeItemAddPacket", [name for name, _ in novaui])
        self.assertIn("chat.AppendChat", [name for name, _ in novaui])
        self.assertFalse(world.mouse.isAttached())

    def test_a_dragon_soul_stone_is_sent_from_its_window(self):
        def flow(world, window):
            world.attach(P["SLOT_TYPE_DRAGON_SOUL_INVENTORY"], 3, SOUL)
            self.drop(world, window, 6)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertIn(("net.SendExchangeItemAddPacket", (P["DRAGON_SOUL_INVENTORY"], 3, 6)), novaui)

    def test_money_on_an_empty_cell_and_on_an_item(self):
        def flow(world, window):
            world.attach_money(4000)
            self.drop(world, window, 8)
            world.attach_money(7000)
            self.drop(world, window, 2)
        (legacy, _, _), (novaui, world, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        sends = [call for call in novaui if call[0].startswith("net.")]
        self.assertEqual(sends, [("net.SendExchangeElkAddPacket", (4000,)), ("net.SendExchangeElkAddPacket", (7000,))])
        self.assertTrue(world.mouse.isAttached(), "money dropped on an item stays attached (legacy sends, no deattach)")

    def test_an_item_on_an_occupied_cell_does_nothing_and_stays_attached(self):
        def flow(world, window):
            world.attach(P["SLOT_TYPE_INVENTORY"], 9, HELMET)
            self.drop(world, window, 2)
        (legacy, _, _), (novaui, world, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual([call for call in novaui if call[0].startswith("net.")], [])
        self.assertTrue(world.mouse.isAttached())

    def test_the_money_button_opens_the_pick_dialog_and_its_accept_sends(self):
        def flow(world, window):
            if world.nui_on:
                w4.press(window, "money_press", 0)
            else:
                window.OwnerMoneyButton.Click()
            window.dlgPickMoney.accept(25000)
        (legacy, _, a), (novaui, _, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertIn(("uiPickMoney.PickMoneyDialog.Open", (5000000,)), [(n, args[-1:]) for n, args in novaui])
        self.assertIn(("net.SendExchangeElkAddPacket", (25000,)), novaui)
        self.assertEqual(b.dlgPickMoney.max, 7, "today's EXCHANGE_MONEY_DIGITS, legacy's SetMax(7)")

    def test_the_money_button_refuses_once_money_is_set(self):
        def setup(game):
            stock(game)
            game.w4["exchange"]["self_elk"] = 100
        def flow(world, window):
            if world.nui_on:
                w4.press(window, "money_press", 0)
            else:
                window.OwnerMoneyButton.Click()
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, setup)
        self.assertEqual(novaui, legacy)
        self.assertEqual([name for name, _ in novaui], ["chat.AppendChat"])

    def test_accept_sends_and_disables_the_toggle(self):
        def flow(world, window):
            if world.nui_on:
                w4.press(window, "accept_press", 0)
            else:
                window.AcceptButton.click()
        (legacy, _, a), (novaui, _, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual([call for call in novaui if call[0].startswith("net.")], [("net.SendExchangeAcceptPacket", ())])
        model = w4.board(b).model
        self.assertEqual((model["accept_down"], model["accept_enabled"]), (True, False))
        w4.press(b, "accept_press", 0)
        self.assertEqual(w4.board(b).model["accept_down"], True, "a disabled toggle takes no press")

    def test_the_close_button_sends_the_exit_packet(self):
        def flow(world, window):
            if world.nui_on:
                w4.press(window, "close_press", 0)
            else:
                window.GetChild("TitleBar").close()
        (legacy, _, _), (novaui, _, _) = self.run_both(flow)
        self.assertEqual(novaui, [("net.SendExchangeExitPacket", ())])
        self.assertEqual(novaui, [call for call in legacy if call[0].startswith("net.")])

    def test_moving_away_sends_the_exit_packet_once_and_rearms(self):
        def flow(world, window):
            world.game.w4["position"] = (1001.0, 0.0, 0.0)
            if world.nui_on:
                support.leave_range(world.game, "exchange")
            else:
                window.OnUpdate()
                window.OnUpdate()
        (legacy, _, a), (novaui, world, b) = self.run_both(flow)
        self.assertEqual(novaui, [("net.SendExchangeExitPacket", ())])
        self.assertEqual(legacy, novaui, "legacy resets its start, so its next frame sends nothing")
        self.assertEqual((b.xStart, b.yStart), (a.xStart, a.yStart))
        state = world.game.modules["nuigame"].LeaveRangeState("exchange")
        self.assertEqual((state["range"], state["rearm"], state["start"]), (1000.0, True, [1001.0, 0.0]))

    def test_open_arms_the_watch_and_the_server_s_end_stops_it_without_the_ignore_call(self):
        world, window = self.world(True)
        mark = world.mark()
        self.open(world, window)
        self.assertEqual(world.calls_since(mark, "nuigame.WatchLeaveRange")[0][1][:2], ("exchange", 1000))
        self.assertIn(DOCUMENT, world.documents())
        mark = world.mark()
        with world.game, w4.quiet():
            window.CloseDialog()
        self.assertEqual(world.calls_since(mark, "nuigame.StopLeaveRange"), [("nuigame.StopLeaveRange", ("exchange",))])
        self.assertEqual(world.calls_since(mark, IGNORE), [])
        self.assertNotIn(DOCUMENT, world.documents())
        legacy, legacy_window = self.world(False)
        self.open(legacy, legacy_window)
        mark = legacy.mark()
        with legacy.game, w4.quiet():
            legacy_window.CloseDialog()
        self.assertEqual(legacy.calls_since(mark, IGNORE), [(IGNORE, ())], "legacy's own call, left out by NovaUI")

    def test_hover_shows_each_side_s_tooltip_and_a_covered_cell_its_anchor_s(self):
        def flow(world, window):
            if world.nui_on:
                for event, index in (("target_over", 0), ("target_over", 4), ("target_over", 8), ("target_out", 8),
                                     ("owner_over", 2), ("owner_out", 2)):
                    w4.fire(window, event, index)
            else:
                window.TargetSlot.fire("over_in", 0)
                window.TargetSlot.fire("over_out")
                window.OwnerSlot.fire("over_in", 2)
                window.OwnerSlot.fire("over_out")
        (_, _, a), (_, _, b) = self.run_both(flow)
        self.assertEqual(b.tooltipItem.shown, a.tooltipItem.shown)
        self.assertEqual(b.tooltipItem.shown, [("SetExchangeTargetItem", 0), ("SetExchangeOwnerItem", 2)])
        self.assertEqual([call[0] for call in b.tooltipItem.calls],
                         ["SetExchangeTargetItem", "HideToolTip", "SetExchangeOwnerItem", "HideToolTip"],
                         "no hide while the pointer crosses the glaive's cells (P14b)")

    def test_a_drag_marks_the_owner_grid_attaching_and_its_footprint(self):
        world, window = self.world(True)
        self.open(world, window)
        world.attach(P["SLOT_TYPE_INVENTORY"], 0, SWORD)
        with world.game:
            w4.fire(window, "owner_over", 5)
        model = w4.board(window).model
        self.assertTrue(model["owner_attaching"])
        self.assertEqual([cell["target"] for cell in model["owner_cells"] if cell["target"]], ["move", "move"],
                         "the sword's 1x2 footprint over cells 5 and 9")
        with world.game:
            world.mouse.DeattachObject()
        self.assertFalse(w4.board(window).model["owner_attaching"])


class Facade(ExchangeTest):
    def test_the_class_and_every_method_the_interface_calls(self):
        world, window = self.world(True)
        legacy_class = world.m("uiExchange").ExchangeDialog
        self.assertIsInstance(window, legacy_class)
        self.assertTrue(window.NUI_FACADE)
        for name in ("LoadDialog", "SetCenterPosition", "Hide", "Destroy", "SetItemToolTip", "OpenDialog", "Refresh",
                     "CloseDialog"):
            self.assertTrue(callable(getattr(window, name)), name)
        for name, member in inspect.getmembers(legacy_class, inspect.isfunction):
            if name in ("OnUpdate", "OnRender"):
                continue
            ours = getattr(type(window), name)
            self.assertEqual(len(inspect.signature(ours).parameters), len(inspect.signature(member).parameters), name)

    def test_no_per_frame_python(self):
        world, window = self.world(True)
        self.assertIsNone(type(window).OnUpdate)
        self.assertIsNone(type(window).OnRender)
        module = world.m("nui_exchange")
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ == "nui_exchange":
                for attr in ("OnUpdate", "OnRender"):
                    self.assertFalse(callable(getattr(cls, attr, None)), "%s.%s" % (name, attr))

    def test_make_builds_legacy_with_the_flag_off_or_an_older_exe(self):
        world, window = self.world(False)
        self.assertIs(type(window), world.m("uiExchange").ExchangeDialog)
        world, window = self.world(True, engine_4=False)
        self.assertIs(type(window), world.m("uiExchange").ExchangeDialog, "no WatchLeaveRange: the legacy window")

    def test_the_interface_makes_it_through_make(self):
        text = w4.read(os.path.join(w4.ROOT, "interfacemodule.py"))
        self.assertIn('self.dlgExchange = nui_windows.make("exchange", uiExchange.ExchangeDialog, "nui_exchange.ExchangeDialog")',
                      text)

    def test_the_legacy_window_underneath_stays_0_by_0_with_the_uiscript_s_flags(self):
        (legacy, a), (novaui, b) = self.worlds()
        self.assertEqual((b.GetWidth(), b.GetHeight()), (0, 0))
        self.assertIn("float", b.flags)
        self.assertEqual(b.flags, a.flags)

    def test_a_press_raises_the_window(self):
        world, window = self.world(True)
        self.open(world, window)
        raised = []
        original = window.SetTop
        window.SetTop = lambda: (raised.append(True), original())
        w4.press(window, "target_press", 11, 0)
        self.assertEqual(raised, [True])


class OnDemand(ExchangeTest):
    def test_no_document_until_open_and_none_after_close(self):
        world, window = self.world(True)
        self.assertNotIn(DOCUMENT, world.documents())
        self.open(world, window)
        self.assertIn(DOCUMENT, world.documents())
        with world.game, w4.quiet():
            window.CloseDialog()
        self.assertNotIn(DOCUMENT, world.documents())

    def test_a_refresh_while_hidden_reaches_the_next_board(self):
        world, window = self.world(True)
        world.game.w4["exchange"]["self"][5] = {"vnum": POTION, "count": 7}
        with world.game, w4.quiet():
            window.Refresh()
        self.open(world, window)
        self.assertEqual(self.board_cells(window, "owner_cells")[5], (POTION, "7"))

    def test_the_place_is_centered_then_kept(self):
        world, window = self.world(True)
        self.open(world, window)
        self.assertEqual(w4.board(window).placement, ("center",))


class Fixtures(ExchangeTest):
    def test_every_fixture_has_the_model_s_keys_and_kinds(self):
        world, window = self.world(True)
        kinds = w4.model_kinds(window.nui_model())
        for variant in ("", "foundation", "empty", "accepted"):
            self.assertEqual(w4.fixture_keys(window, "exchange", variant), kinds, variant)


if __name__ == "__main__":
    unittest.main()
