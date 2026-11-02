"""Tests for the NovaUI exchange (assets/root/nui_exchange.py, P16 spec 5.1):
python3 -B -m unittest nui_exchange_test (from tools/).

The legacy uiExchange.ExchangeDialog (made from its real uiscript by
nui_game_support's stand-ins) and the NovaUI one, each in a world of its own
with the same state (nui_w4_world.World), driven through every flow of spec
5.1.4: the legacy slot window's C++ events against the board's data events.
They make the same W4_COMPARED calls in the same order (getters left out),
and the board shows what legacy's widgets show. Legacy's
wndMgr.OnceIgnoreMouseLeftButtonUpEvent() in CloseDialog is the one
difference (spec 2.1).

Wave 4b (NOVA-12, NOVA-13): the 6 x 4 grids and a full 24-slot trade, the
faces, the partner's name and level, the history's last three lines, the
accepted side's green slot base, the give-away question, and the locks of
the source cells in both inventories (game.py's BINARY_AddItemToExchange
and BINARY_DelItemFromExchange through interfacemodule.py's own methods,
released at the close and the END), each compared with legacy's, and shown
at once on a NovaUI bag (nui_slots.flush_marks)."""
import inspect
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import extra_inventory_test as ext  # noqa: E402
import tradable_icon_test as ti  # noqa: E402

P = w4.P
I = support.module_constants()["item"]
DOCUMENT = "nui/windows/exchange/exchange.rml"
IGNORE = "wndMgr.OnceIgnoreMouseLeftButtonUpEvent"
SWORD, GLAIVE, POTION, HELMET, AUTO_HP, SOUL = 10, 3000, 27001, 12200, 72723, 110000


def stock(game):
    """The tester's inventory: a sword at 0, a potion stack at 4, a helmet at
    9, an active auto potion at 12, an untradable ring at 13; 5.000.000 Yang;
    a dragon soul stone at dragon soul 3. The trade: the partner (Partner, a
    sura, level 37) put a glaive at 0 and 30.000 Yang; the tester (an
    assassin) a helmet at 2."""
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
    ex["target_level"] = 37
    ex["self_race"], ex["target_race"] = 5, 2


def full(game):
    """stock, with every one of the 24 display slots of both sides holding
    an item (1x1 stones and potions, counts on the even cells)."""
    stock(game)
    ex = game.w4["exchange"]
    ex["self"] = [{"vnum": POTION, "count": 2 + i} if i % 2 == 0 else {"vnum": 28030 + i % 10, "count": 1}
                  for i in range(24)]
    ex["target"] = [{"vnum": 27002, "count": 3 + i} if i % 2 == 0 else {"vnum": 28030 + i % 10, "count": 1}
                    for i in range(24)]


def untimed(lines):
    """History lines without their time (legacy's [%H:%M:%S])."""
    return [re.sub(r"^\[\d\d:\d\d:\d\d\] ", "", line) for line in lines]


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
        self.assertEqual(model["cols"], 6, "wave 4b: 6 x 4 (nui_limits' EXCHANGE_COLUMNS)")
        self.assertEqual((len(model["owner_cells"]), len(model["target_cells"])), (24, 24))
        covered = [cell["index"] for cell in model["target_cells"] if cell["covered"]]
        self.assertEqual(covered, [6, 12], "the glaive's 1x3 from cell 0")
        self.assertEqual(model["target_cells"][0]["type"], P["SLOT_TYPE_EXCHANGE_TARGET"])
        self.assertEqual(model["owner_cells"][2]["type"], P["SLOT_TYPE_EXCHANGE_OWNER"])
        self.assertEqual((model["accept_down"], model["accept_enabled"], model["owner_accept"], model["target_accept"]),
                         (False, True, False, False))
        self.assertEqual((model["owner_face"], model["target_face"]),
                         ("/" + a.FaceOwnerImage.image, "/" + a.FaceTargetImage.image))
        self.assertEqual((model["owner_face"], model["target_face"]), ("/icon/face/assassin_m.tga", "/icon/face/sura_m.tga"))
        self.assertEqual((model["target_name"], model["target_level"]), (a.TargetName.GetText(), a.TargetLevel.GetText()))
        self.assertEqual((model["target_name"], model["target_level"]), ("Partner", "Lv. 37"))
        self.assertEqual(model["log_lines"], [line.GetText() for line in a.ExchangeLogLines])
        self.assertEqual(untimed(model["log_lines"]), ["You are ready to trade.", "", ""])
        self.assertEqual((model["owner_base_accepted"], model["target_base_accepted"]), (False, False))

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
        self.assertTrue(w4.board(b).model["owner_cells"][6]["covered"])
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
        self.assertEqual(b.dlgPickMoney.max, 12, "legacy's SetMax(player.EXCHANGE_MONEY_DIGITS) since NOVA-96: OLD's 12")
        self.assertEqual(a.dlgPickMoney.max, 12)

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

    def test_the_interface_s_destroy_of_a_shown_exchange_stops_its_watch(self):
        """Review: a trade open at a warp or logout ends on the server with no
        END packet, so the Interface's Close destroys a shown exchange
        (Destroy hides nothing). The watch went on in the next phases and,
        rearmed, called the dead window's _left_range every 1000 units."""
        world, window = self.world(True)
        self.open(world, window)
        nuigame = world.game.modules["nuigame"]
        self.assertIsNotNone(nuigame.LeaveRangeState("exchange"))
        with world.game, w4.quiet():
            window.Destroy()
        self.assertIsNone(nuigame.LeaveRangeState("exchange"))
        mark = world.mark()
        world.game.w4["position"] = (5000.0, 0.0, 0.0)
        with world.game, w4.quiet():
            self.assertFalse(support.leave_range(world.game, "exchange"))
        self.assertEqual(world.calls_since(mark, "net."), [])

    def test_a_newer_exchange_keeps_its_own_watch_when_an_older_one_goes(self):
        world, older = self.world(True)
        self.open(world, older)
        newer = world.make("exchange", "uiExchange", "ExchangeDialog", "nui_exchange.ExchangeDialog")
        nuigame = world.game.modules["nuigame"]
        self.assertIsNone(nuigame.LeaveRangeState("exchange"), "take_over discarded the older one's NovaUI parts")
        with world.game, w4.quiet():
            newer.LoadDialog()
            newer.SetItemToolTip(world.tooltip)
            self.open(world, newer)
            older.Destroy()
        self.assertIsNotNone(nuigame.LeaveRangeState("exchange"), "the older one's Destroy left the newer's watch")

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
        self.assertFalse(window.demand.kept().is_visible(), "P18: kept, hidden")
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
        self.assertEqual([cell["index"] for cell in model["owner_cells"] if cell["target"] == "move"], [5, 11],
                         "the sword's 1x2 footprint over cells 5 and 11 (6 columns)")
        with world.game:
            world.mouse.DeattachObject()
        self.assertFalse(w4.board(window).model["owner_attaching"])


class Wave4b(ExchangeTest):
    """NOVA-12: legacy's 24-slot window's parts, compared with legacy's."""

    def test_a_partner_out_of_view_shows_race_0_s_face_and_level_0(self):
        def setup(game):
            stock(game)
            ex = game.w4["exchange"]
            ex["target_race"], ex["target_level"] = 0, 0
        (_, _, a), (_, _, b) = self.run_both(lambda world, window: None, setup)
        model = w4.board(b).model
        self.assertEqual(model["target_face"], "/" + a.FaceTargetImage.image)
        self.assertEqual((model["target_face"], model["target_level"]), ("/icon/face/warrior_m.tga", "Lv. 0"))

    def test_the_history_writes_each_accept_change_and_shows_the_last_three(self):
        def flow(world, window):
            ex = world.game.w4["exchange"]
            for side, value in (("target_accept", True), ("self_accept", True), ("self_accept", True),
                                ("target_accept", False)):
                ex[side] = value
                window.Refresh()
        (legacy, _, a), (novaui, _, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        model = w4.board(b).model
        self.assertEqual(untimed(model["log_lines"]), untimed(line.GetText() for line in a.ExchangeLogLines))
        self.assertEqual(untimed(model["log_lines"]),
                         ["Partner accept the trade.", "You accept the trade.", "Partner abort the trade."])
        self.assertEqual(len(b.exchangeLogs), 4, "ready, then three changes; a refresh that changes nothing writes nothing")

    def test_a_side_that_accepted_has_the_green_slot_base(self):
        world, window = self.world(True)
        self.open(world, window)
        ex = world.game.w4["exchange"]
        uiexchange = world.m("uiExchange")
        states = []
        for side, value in (("target_accept", True), ("self_accept", True), ("target_accept", False)):
            ex[side] = value
            with world.game, w4.quiet():
                window.Refresh()
            model = w4.board(window).model
            states.append((model["owner_base_accepted"], model["target_base_accepted"]))
        self.assertEqual(states, [(False, True), (True, True), (True, False)])
        self.assertEqual(window.OwnerSlot.base, (uiexchange.SLOT_BASE_IMAGE, uiexchange.ACCEPTED_SLOT_BASE_COLOR))
        self.assertEqual(window.TargetSlot.base, (uiexchange.SLOT_BASE_IMAGE, uiexchange.SLOT_BASE_COLOR))

    def test_a_full_trade_shows_all_24_cells_of_each_side(self):
        (legacy, a), (novaui, b) = self.worlds(full)
        self.open(legacy, a)
        self.open(novaui, b)
        for key, slots in (("owner_cells", "OwnerSlot"), ("target_cells", "TargetSlot")):
            cells = self.board_cells(b, key)
            self.assertEqual(cells, self.legacy_cells(getattr(a, slots)), key)
            self.assertEqual(sorted(cells), list(range(24)), key)
        self.assertEqual(self.board_cells(b, "owner_cells")[22], (POTION, "24"))
        self.assertEqual(self.board_cells(b, "target_cells")[23], (28033, ""))

    def test_a_drop_on_the_last_cell_sends_cell_23(self):
        def setup(game):
            stock(game)
        def flow(world, window):
            world.attach(P["SLOT_TYPE_INVENTORY"], 4, POTION, 50)
            if world.nui_on:
                w4.press(window, "owner_press", 23, 0)
            else:
                window.SetTop()
                window.OwnerSlot.fire("select_empty", 23)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, setup)
        self.assertEqual(novaui, legacy)
        self.assertIn(("net.SendExchangeItemAddPacket", (P["INVENTORY"], 4, 23)), novaui)


class GiveAway(ExchangeTest):
    """Legacy's AcceptExchange (OLD uiExchange.py:254-293): giving something
    for nothing asks first (uiCommon.QuestionDialog2, the dialog kit's
    facade while dialogs is on)."""

    @staticmethod
    def nothing_back(game):
        stock(game)
        ex = game.w4["exchange"]
        ex["target"][0] = None
        ex["target_elk"] = 0

    def press_accept(self, world, window):
        if world.nui_on:
            w4.press(window, "accept_press", 0)
        else:
            window.AcceptButton.click()

    def test_the_question_s_yes_sends_the_accept(self):
        def flow(world, window):
            self.press_accept(world, window)
            dialog = world.game.dialogs[-1]
            self.assertEqual((dialog._name, dialog.texts, dialog.is_open),
                             ("uiCommon.QuestionDialog2", ["You are giving things away for nothing in exchange,",
                                                           "and won't be able to get the Yang or items back."], True))
            self.assertEqual(world.calls_since(0, "net."), [])
            dialog.accept()
        (legacy, _, _), (novaui, world, b) = self.run_both(flow, self.nothing_back)
        self.assertEqual(novaui, legacy)
        self.assertEqual([call for call in novaui if call[0].startswith("net.")], [("net.SendExchangeAcceptPacket", ())])
        model = w4.board(b).model
        self.assertEqual((model["accept_down"], model["accept_enabled"]), (True, False))
        self.assertFalse(world.game.dialogs[-1].is_open)

    def test_the_question_s_no_sends_nothing_and_raises_the_toggle(self):
        def flow(world, window):
            self.press_accept(world, window)
            world.game.dialogs[-1].cancel()
        (legacy, _, _), (novaui, _, b) = self.run_both(flow, self.nothing_back)
        self.assertEqual(novaui, legacy)
        self.assertEqual([call for call in novaui if call[0].startswith("net.")], [])
        model = w4.board(b).model
        self.assertEqual((model["accept_down"], model["accept_enabled"]), (False, True))

    def test_the_partner_s_offer_accepts_at_once(self):
        def flow(world, window):
            self.press_accept(world, window)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual([call for call in novaui if call[0].startswith("net.")], [("net.SendExchangeAcceptPacket", ())])
        self.assertNotIn("uiCommon.QuestionDialog2.Open", [name for name, _ in novaui])

    def test_the_trade_s_end_closes_an_open_question(self):
        def flow(world, window):
            self.press_accept(world, window)
            window.CloseDialog()
            self.assertFalse(world.game.dialogs[-1].is_open)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, self.nothing_back)
        self.assertEqual([call for call in novaui if call[0] != IGNORE], [call for call in legacy if call[0] != IGNORE])


class _Bound(object):
    """A trade window the locks test does not look at (the shop, the
    safebox, the private shop builder): what the Interface binds."""

    def BindInterface(self, interface):
        pass

    def SetInven(self, *args):
        pass

    def IsShow(self):
        return False


class LockWorld(object):
    """tradable_icon_test's world with the exchange of either side: legacy's
    inventory and special inventory (their slot windows tracked), the
    exchange (NovaUI's with nui_on), an Interface made of
    interfacemodule.py's own methods, and game.py's two callbacks."""

    def __init__(self, nui_on):
        self.w4 = w4.World(nui_on, setup=stock)
        game = self.game = self.w4.game
        ext.install_k(game)
        with game, w4.quiet():
            for name, file_name in (("uiAttachMetin", "uiattachmetin.py"), ("uiInventory", "uiinventory.py"),
                                    ("uiExtraInventory", "uiextrainventory.py")):
                game.load(name, file_name)
        namespace = dict(game.modules)
        namespace.update(game.loaded)
        interface = self.interface = ext.compiled("interfacemodule.py", "Interface", ti.INTERFACE, namespace)()
        interface.onTopWindow = game.modules["player"].ON_TOP_WND_NONE
        with game, w4.quiet():
            inventory = self.inventory = game.loaded["uiInventory"].InventoryWindow()
            inventory.BindInterfaceClass(interface)
            inventory.SetItemToolTip(ext.DialogToolTip())
            inventory.Show()
            extra = self.extra = game.loaded["uiExtraInventory"].ExtraInventoryWindow()
            extra.BindInterfaceClass(interface)
            extra.Show()
        ti.track(inventory.wndItem)
        ti.track(extra.wndItem)
        self.exchange = self.w4.make("exchange", "uiExchange", "ExchangeDialog", "nui_exchange.ExchangeDialog")
        with game, w4.quiet():
            self.exchange.LoadDialog()
            self.exchange.SetItemToolTip(self.w4.tooltip)
        interface.wndInventory, interface.wndExtraInventory = inventory, extra
        interface.dlgExchange = self.exchange
        interface.dlgShop = interface.wndSafebox = interface.privateShopBuilder = _Bound()
        interface.dlgRefineNew = None
        with game, w4.quiet():
            interface._Interface__BindTradableWindows()
        cls = ext.compiled("game.py", "GameWindow", ("BINARY_AddItemToExchange", "BINARY_DelItemFromExchange"))
        self.game_window = cls()
        self.game_window.interface = interface

    def run(self, fn, *args):
        with self.game, w4.quiet():
            return fn(*args)

    def state(self):
        return (ti.locked(self.inventory.wndItem), ti.locked(self.extra.wndItem), dict(self.exchange.lockedItems),
                self.interface.GetOnTopWindow())


class Locks(unittest.TestCase):
    """NOVA-13: the source cells of the items put in take no mouse event
    until the item leaves or the trade ends, in both inventories, by the
    legacy flows (game.py -> Interface -> CantTradableItem)."""

    def flow(self, world, end):
        states = []
        world.run(world.interface.StartExchange)
        states.append(world.state())
        world.run(world.game_window.BINARY_AddItemToExchange, ext.INVENTORY, 4, 0)
        world.run(world.game_window.BINARY_AddItemToExchange, ext.EXTRA, 225 + 5, 1)
        states.append(world.state())
        world.run(world.game_window.BINARY_DelItemFromExchange, 1)
        states.append(world.state())
        world.run(world.game_window.BINARY_AddItemToExchange, ext.EXTRA, 225 + 6, 2)
        world.run(getattr(world.interface if end == "EndExchange" else world.exchange, end))
        states.append(world.state())
        return states

    def test_the_locks_and_the_window_on_top_follow_legacy_s(self):
        for end in ("EndExchange", "CloseDialog"):
            with self.subTest(end=end):
                legacy, novaui = LockWorld(False), LockWorld(True)
                self.assertTrue(getattr(novaui.exchange, "NUI_FACADE", False))
                expected = self.flow(legacy, end)
                self.assertEqual(self.flow(novaui, end), expected)
                self.assertEqual(expected, [
                    ([], [], {}, 2),
                    ([4], [5], {0: (ext.INVENTORY, 4), 1: (ext.EXTRA, 230)}, 2),
                    ([4], [], {0: (ext.INVENTORY, 4)}, 2),
                    ([], [], {}, 0)])

    def test_a_refresh_locks_the_cells_again(self):
        for nui_on in (False, True):
            with self.subTest(nui_on=nui_on):
                world = LockWorld(nui_on)
                world.run(world.interface.StartExchange)
                world.run(world.game_window.BINARY_AddItemToExchange, ext.INVENTORY, 4, 0)
                world.inventory.wndItem.locks.clear()
                world.run(world.exchange.Refresh)  # Interface.RefreshExchange
                self.assertEqual(ti.locked(world.inventory.wndItem), [4])


class NovaUIBag(ExchangeTest):
    """A lock or a release from game.py reaches a NovaUI bag's proxy at once
    (nui_slots.flush_marks), as CSlotWindow draws its state at once: no
    NovaUI event follows that would push it."""

    def test_the_lock_and_the_release_show_at_once(self):
        world, window = self.world(True)
        slots = world.m("nui_slots")
        pushed = []

        class Bag(object):
            def __init__(self):
                with world.game:
                    self.wndItem = slots.SlotWindowProxy(range(45), lambda cells: pushed.append(cells), cols=5,
                                                         rows=9, marks=True)
                    self.wndItem.SetItemSlot(4, POTION, 50)
                    self.wndItem.RefreshSlot()

            def SetCantMouseEventCell(self, cell):
                self.wndItem.SetCantMouseEventSlot(cell)

            def SetCanMouseEventCell(self, cell):
                self.wndItem.SetCanMouseEventSlot(cell)

        bag = Bag()
        window.SetInven(bag, None)
        self.open(world, window)
        del pushed[:]
        with world.game, w4.quiet():
            window.CantTradableItem(0, 4, P["INVENTORY"])
        self.assertEqual([cells[4]["in_use"] for cells in pushed], [True], "pushed once, at the lock")
        with world.game, w4.quiet():
            window.ReleaseTradableItem(0)
        self.assertEqual([cells[4]["in_use"] for cells in pushed], [True, False])
        with world.game, w4.quiet():
            window.CantTradableItem(0, 4, P["INVENTORY"])
            window.CloseDialog()
        self.assertEqual(pushed[-1][4]["in_use"], False, "the close releases it at once")
        self.assertEqual(window.lockedItems, {})


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
    def test_no_document_until_the_first_open_then_kept_hidden_with_no_cell(self):
        """P18 (V-2b's pattern): nothing loads before the first open; the
        close keeps the board loaded and hidden, both grids emptied; the
        next open shows the same board with no load, at the place it was
        left, with the cells legacy's refresh gave it while hidden."""
        world, window = self.world(True)
        self.assertNotIn(DOCUMENT, world.documents())
        self.open(world, window)
        self.assertIn(DOCUMENT, world.documents())
        board = w4.board(window)
        world.game.state.boxes[(DOCUMENT, "")] = (300.0, 120.0, 520.0, 400.0)
        with world.game, w4.quiet():
            window.CloseDialog()
        self.assertIsNone(w4.board(window))
        self.assertIs(window.demand.kept(), board)
        self.assertFalse(board.is_visible())
        self.assertEqual(world.documents(), [DOCUMENT], "kept loaded")
        self.assertEqual(board.model["grids_on"], [], "no cell while hidden")
        world.game.w4["exchange"]["self"][5] = {"vnum": POTION, "count": 7}
        with world.game, w4.quiet():
            window.Refresh()
        self.open(world, window)
        self.assertIs(w4.board(window), board, "shown again, not made again")
        self.assertEqual(board.model["grids_on"], [1])
        self.assertEqual(self.board_cells(window, "owner_cells")[5], (POTION, "7"))
        self.assertEqual(board.placement, ("position", 300.0, 120.0, (0.0, 0.0)), "the place it was dragged to")
        self.assertEqual(world.documents(), [DOCUMENT])

    def test_destroy_unloads_the_kept_board(self):
        world, window = self.world(True)
        self.open(world, window)
        with world.game, w4.quiet():
            window.CloseDialog()
            window.Destroy()
        self.assertEqual(world.documents(), [])

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
        for variant in ("", "foundation", "empty", "accepted", "full", "attaching"):
            self.assertEqual(w4.fixture_keys(window, "exchange", variant), kinds, variant)

    def test_every_fixture_is_a_6_by_4_trade_with_three_history_lines(self):
        for variant in ("", "foundation", "empty", "accepted", "full", "attaching"):
            model = w4.fixture_model("exchange", variant)
            self.assertEqual((model["cols"], len(model["owner_cells"]), len(model["target_cells"])), (6, 24, 24), variant)
            self.assertEqual(len(model["log_lines"]), 3, variant)
        model = w4.fixture_model("exchange", "full")
        for key in ("owner_cells", "target_cells"):
            self.assertTrue(all(cell["kind"] or cell["covered"] for cell in model[key]), "full: %s" % key)


if __name__ == "__main__":
    unittest.main()
