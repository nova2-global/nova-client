"""Tests for the NovaUI safebox, its password dialogs and the item mall
storage (assets/root/nui_safebox.py, nui_safebox_password.py,
nui_change_password.py, nui_mall.py; P16 spec 5.4, 5.5):
python3 -B -m unittest nui_safebox_test (from tools/).

The legacy uiSafebox.SafeboxWindow, PasswordDialog, ChangePasswordDialog
and MallWindow (made from their real uiscripts by nui_game_support's
stand-ins) and the NovaUI ones, each in a world of its own with the same
state (nui_w4_world.World), driven through every flow of spec 5.4.4 and
5.5.4: the legacy slot window's C++ events, buttons and edit lines against
the boards' data events, keys and fields. They make the same W4_COMPARED
calls, sounds and dialogs in the same order (getters left out), and the
boards show what legacy's widgets show. The one difference is the distance
rule: legacy sends the close command every frame while out of range,
NovaUI once (spec 2.1)."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_test_support  # noqa: E402
import nui_w4_world as w4  # noqa: E402

P = w4.P
A = support.APP_CONSTANTS
SAFEBOX_DOCUMENT = "nui/windows/safebox/safebox.rml"
PASSWORD_DOCUMENT = "nui/windows/safebox-password/safebox-password.rml"
CHANGE_DOCUMENT = "nui/windows/change-password/change-password.rml"
MALL_DOCUMENT = "nui/windows/mall/mall.rml"
FIELD = "safebox-password-field"
OLD, NEW, CHECK = "change-password-old", "change-password-new", "change-password-check"
KEY_ESCAPE, KEY_RETURN, KEY_TAB = nui_test_support.KEY_ESCAPE, nui_test_support.KEY_RETURN, nui_test_support.KEY_TAB
SWORD, GLAIVE, POTION, HELMET, AUTO_HP = 10, 3000, 27001, 12200, 72723


def stock(game):
    """The tester's inventory: a sword at 0, 50 potions at 4, a helmet at 9,
    an active auto potion at 12; 5.000.000 Yang. The safebox: a glaive at 1
    and 200 potions at 2 on page I, a helmet at 45 (page II's first cell), a
    sword at 50; the mall: a glaive at 1, 3 potions at 2, a helmet at 50
    (past the 45 legacy shows)."""
    game.give(0, SWORD, size=(1, 2))
    game.give(4, POTION, 50)
    game.give(9, HELMET)
    game.give(12, AUTO_HP, 1, sockets=(1, 200, 1000))
    game.item_sizes[GLAIVE] = (1, 3)
    game.elk = 5000000
    w4.mirror_inventory(game)
    box = game.w4["safebox"]
    box["items"].update({1: {"vnum": GLAIVE, "count": 1}, 2: {"vnum": POTION, "count": 200},
                         45: {"vnum": HELMET, "count": 1}, 50: {"vnum": SWORD, "count": 1}})
    box["mall"].update({1: {"vnum": GLAIVE, "count": 1}, 2: {"vnum": POTION, "count": 3},
                        50: {"vnum": HELMET, "count": 1}})
    box["mall_size"] = 135


def cells_of(window, proxy):
    """{cell: (vnum, count label)} of a NovaUI board's grid."""
    board = w4.board(window)
    model = board.model if board is not None else window._state
    vnums = proxy.vnums()
    return dict((cell["index"], (vnums[cell["index"]], cell["count"])) for cell in model["cells"] if cell["kind"] == "item")


def legacy_cells(slots):
    """{cell: (vnum, count label)} of a legacy slot window (count 0 shows none)."""
    return dict((index, (slot["vnum"], str(slot["count"]) if slot["count"] else ""))
                for index, slot in slots.slots.items() if slot["vnum"])


# --- the safebox -----------------------------------------------------------------------------------

class SafeboxTest(unittest.TestCase):
    def world(self, nui_on, setup=stock, **kwargs):
        world = w4.World(nui_on, setup=setup, **kwargs)
        window = world.make("safebox", "uiSafebox", "SafeboxWindow", "nui_safebox.SafeboxWindow")
        with world.game, w4.quiet():
            window.SetItemToolTip(world.tooltip)
        return world, window

    def open(self, world, window, size=27):
        """Interface.OpenSafeboxWindow, then the server's items
        (RefreshSafebox)."""
        with world.game, w4.quiet():
            window.ShowWindow(size)
            window.RefreshSafebox()

    def run_both(self, flow, setup=stock, size=27):
        results = []
        for nui_on in (False, True):
            world, window = self.world(nui_on, setup)
            self.open(world, window, size)
            mark = world.mark()
            with world.game, w4.quiet():
                flow(world, window)
            results.append((world.effects_since(mark), world, window))
        return results

    def press(self, world, window, cell, button=0):
        """A press on a cell: the C++ slot window's event (left: select empty
        or item, right: unselect item), the board's cell_press."""
        if world.nui_on:
            w4.press(window, "cell_press", cell, button)
            return
        window.SetTop()
        slots = window.wndItem
        filled = bool(slots.slots[cell]["vnum"])
        if button == 0:
            slots.fire("select_item" if filled else "select_empty", cell)
        elif filled and not world.mouse.isAttached():
            slots.fire("unselect_item", cell)

    def page(self, world, window, index):
        if world.nui_on:
            w4.press(window, "page_press", index, 0)
        else:
            window.pageButtonList[index].click()


class SafeboxModel(SafeboxTest):
    def test_the_board_shows_legacy_s_cells_pages_and_the_page_down(self):
        (_, _, a), (_, _, b) = self.run_both(lambda world, window: None)
        self.assertEqual(cells_of(b, b.wndItem), legacy_cells(a.wndItem))
        self.assertEqual(cells_of(b, b.wndItem), {1: (GLAIVE, ""), 2: (POTION, "200")})
        model = w4.board(b).model
        self.assertEqual(model["pages"], [{"index": 0, "label": "I"}, {"index": 1, "label": "II"},
                                          {"index": 2, "label": "III"}])
        self.assertEqual([button.GetText() for button in a.pageButtonList], ["I", "II", "III"])
        self.assertEqual((model["page_count"], model["page"], model["cols"]), (3, 0, 5))
        self.assertEqual(len(model["cells"]), 45)
        self.assertEqual([cell["index"] for cell in model["cells"] if cell["covered"]], [6, 11], "the glaive's 1x3")
        self.assertEqual((model["cells"][1]["type"], model["cells"][1]["ref"]), (P["SLOT_TYPE_SAFEBOX"], 1))

    def test_a_page_shows_its_cells_by_their_global_position(self):
        def flow(world, window):
            self.page(world, window, 1)
        (legacy, _, a), (novaui, _, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual(cells_of(b, b.wndItem), legacy_cells(a.wndItem))
        self.assertEqual(cells_of(b, b.wndItem), {0: (HELMET, ""), 5: (SWORD, "")})
        model = w4.board(b).model
        self.assertEqual((model["page"], model["cells"][0]["ref"]), (1, 45))
        self.assertEqual([button.down for button in a.pageButtonList], [False, True, False])
        w4.press(b, "page_press", 1, 0)
        self.assertEqual(b.curPageIndex, 1, "a press on the page that is down does nothing")

    def test_the_server_s_size_gives_legacy_s_page_count(self):
        # Legacy's cap is the client's SAFEBOX_PAGE_COUNT_MAX since NOVA-97
        # (5; before it, min(3, ...)), its page names "I" to "V".
        for size, count in ((9, 1), (18, 2), (27, 3), (36, 4), (45, 5), (54, 5)):
            (_, _, a), (_, _, b) = self.run_both(lambda world, window: None, size=size)
            with self.subTest(size=size):
                self.assertEqual(w4.board(b).model["page_count"], count)
                self.assertEqual(len(a.pageButtonList), count)
                self.assertEqual([page["label"] for page in w4.board(b).model["pages"]],
                                 [button.GetText() for button in a.pageButtonList])

    def test_the_foundation_s_limit_gives_five_pages(self):
        """SetTableSize reads SAFEBOX_PAGE_COUNT_MAX (spec 3.3): OLD's five
        pages at the foundation, labels I to V (legacy's PAGE_NAMES since
        NOVA-97; before it, one more "I" a page)."""
        def setup(game):
            stock(game)
        world = w4.World(True, setup=setup)
        limits = world.m("nui_limits")
        limits.use(limits.foundation())
        try:
            window = world.make("safebox", "uiSafebox", "SafeboxWindow", "nui_safebox.SafeboxWindow")
            self.open(world, window, 45)
            model = w4.board(window).model
            self.assertEqual([page["label"] for page in model["pages"]], ["I", "II", "III", "IV", "V"])
            self.assertEqual(model["page_count"], 5)
        finally:
            limits.use(None)


class SafeboxFlows(SafeboxTest):
    def test_an_inventory_item_on_an_empty_cell_is_checked_in_at_its_global_position(self):
        def flow(world, window):
            self.page(world, window, 1)
            world.attach(P["SLOT_TYPE_INVENTORY"], 9, HELMET)
            self.press(world, window, 7)
        (legacy, world, _), (novaui, _, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertIn(("net.SendSafeboxCheckinPacket", (P["INVENTORY"], 9, 52)), novaui)
        self.assertFalse(world.mouse.isAttached())

    def test_an_active_auto_potion_is_used_first(self):
        def flow(world, window):
            world.attach(P["SLOT_TYPE_INVENTORY"], 12, AUTO_HP)
            self.press(world, window, 20)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        sends = [call for call in novaui if call[0].startswith("net.")]
        self.assertEqual(sends, [("net.SendItemUsePacket", (12,)), ("net.SendSafeboxCheckinPacket", (P["INVENTORY"], 12, 20))])

    def test_a_safebox_item_is_picked_and_moved(self):
        def flow(world, window):
            self.press(world, window, 2)
            self.press(world, window, 30)
        (legacy, world, _), (novaui, _, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertIn(("mouse.AttachObject", (P["SLOT_TYPE_SAFEBOX"], 2, POTION, 0)), novaui)
        self.assertIn(("snd.PlaySound", ("sound/ui/pick.wav",)), novaui)
        self.assertIn(("net.SendSafeboxItemMovePacket", (2, 30, 0)), novaui)
        self.assertFalse(world.mouse.isAttached())

    def test_money_dropped_on_a_cell_calls_legacy_s_save_money(self):
        """D17: legacy's save money call (which sends nothing in this client)
        and its sound, on an empty cell and on an item."""
        def flow(world, window):
            world.attach_money(1000)
            self.press(world, window, 20)
            world.attach_money(2000)
            self.press(world, window, 2)
        (legacy, world, _), (novaui, _, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual([call for call in novaui if call[0].startswith("net.")],
                         [("net.SendSafeboxSaveMoneyPacket", (1000,)), ("net.SendSafeboxSaveMoneyPacket", (2000,))])
        self.assertEqual(novaui.count(("snd.PlaySound", ("sound/ui/money.wav",))), 2)
        self.assertFalse(world.mouse.isAttached())

    def test_the_cursor_modes_tell_and_attach_nothing(self):
        for cursor, text in (("SELL", "SAFEBOX_SELL_DISABLE_SAFEITEM"), ("BUY", "SHOP_BUY_INFO")):
            def flow(world, window, cursor=cursor):
                world.game.cursor = A[cursor]
                self.press(world, window, 2)
            (legacy, world, _), (novaui, _, _) = self.run_both(flow)
            with self.subTest(cursor=cursor):
                self.assertEqual(novaui, legacy)
                self.assertEqual([name for name, _ in novaui], ["chat.AppendChat"])
                self.assertFalse(world.mouse.isAttached())

    def test_a_right_press_and_a_double_click_drop_the_attach(self):
        def flow(world, window):
            self.press(world, window, 2)
            if world.nui_on:
                w4.fire(window, "cell_use", 1)
            else:
                window.wndItem.fire("use", 1)
        (legacy, world, _), (novaui, _, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertIn(("mouse.DeattachObject", ()), novaui)
        self.assertFalse(world.mouse.isAttached())

    def test_the_change_password_button_opens_its_dialog(self):
        def flow(world, window):
            if world.nui_on:
                w4.press(window, "change_password_press", 0)
            else:
                window.GetChild("ChangePasswordButton").click()
        (legacy, _, a), (novaui, world, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertTrue(b.dlgChangePassword.IsShow())
        self.assertIn(CHANGE_DOCUMENT, world.documents())
        self.assertEqual(type(b.dlgChangePassword).__module__, "nui_safebox")

    def test_the_close_buttons_and_escape_send_the_close_command(self):
        for how in ("exit", "x", "escape"):
            def flow(world, window, how=how):
                if how == "escape":
                    window.OnPressEscapeKey()
                elif world.nui_on:
                    w4.press(window, "close_press", 0)
                elif how == "exit":
                    window.GetChild("ExitButton").click()
                else:
                    window.GetChild("TitleBar").close()
            (legacy, _, _), (novaui, _, b) = self.run_both(flow)
            with self.subTest(how=how):
                self.assertEqual(novaui, legacy)
                self.assertEqual(novaui, [("net.SendChatPacket", ("/safebox_close",))])
                self.assertTrue(b.IsShow(), "the server's command hides it")

    def test_the_server_s_close_hides_it_and_stops_the_watch(self):
        def flow(world, window):
            window.CommandCloseSafebox()
        (legacy, _, a), (novaui, world, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertFalse(b.IsShow())
        self.assertNotIn(SAFEBOX_DOCUMENT, world.documents())
        self.assertIsNone(world.game.modules["nuigame"].LeaveRangeState("safebox"))

    def test_the_interface_s_destroy_of_a_shown_safebox_stops_its_watch(self):
        """Review: the Interface's Close destroys a shown safebox at a warp or
        logout (Destroy hides nothing); the watch fired in the next phase
        without a main actor and sent /safebox_close there."""
        world, window = self.world(True)
        self.open(world, window)
        nuigame = world.game.modules["nuigame"]
        self.assertIsNotNone(nuigame.LeaveRangeState("safebox"))
        with world.game, w4.quiet():
            window.Destroy()
        self.assertIsNone(nuigame.LeaveRangeState("safebox"))
        mark = world.mark()
        world.game.w4["position"] = (5000.0, 0.0, 0.0)
        with world.game, w4.quiet():
            self.assertFalse(support.leave_range(world.game, "safebox"))
        self.assertEqual(world.calls_since(mark, "net."), [])

    def test_the_phase_end_stops_every_watch(self):
        world, window = self.world(True)
        self.open(world, window)
        nuigame = world.game.modules["nuigame"]
        facade = world.m("nui_facade")
        self.assertIn("nui_facade", world.m("nui_windows").PHASE_SCOPED)
        self.assertEqual(facade.LEAVE_RANGE_KEYS, ("exchange", "shop", "safebox", "mall"))
        with world.game, w4.quiet():
            self.assertEqual(facade.end_phase(), 0, "no document to unload")
        self.assertIsNone(nuigame.LeaveRangeState("safebox"))
        for module, name in (("nui_exchange", "ExchangeDialog"), ("nui_shop", "ShopDialog"), ("nui_safebox", "SafeboxWindow"),
                             ("nui_mall", "MallWindow")):
            cls = getattr(world.m(module), name)
            self.assertTrue(cls.LEAVE_RANGE, name)
            self.assertIn(cls.KEY, facade.LEAVE_RANGE_KEYS, name)

    def test_moving_away_sends_the_close_command_once(self):
        """Spec 2.1: legacy sends it every frame until the server answers;
        NovaUI's watch fires once (no rearm)."""
        def flow(world, window):
            world.game.w4["position"] = (1001.0, 0.0, 0.0)
            if world.nui_on:
                support.leave_range(world.game, "safebox")
                support.leave_range(world.game, "safebox")
            else:
                window.OnUpdate()
                window.OnUpdate()
        (legacy, _, _), (novaui, world, _) = self.run_both(flow)
        self.assertEqual(novaui, [("net.SendChatPacket", ("/safebox_close",))])
        self.assertEqual(legacy, novaui * 2, "legacy's two frames")
        state = world.game.modules["nuigame"].LeaveRangeState("safebox")
        self.assertEqual((state["range"], state["rearm"], state["fires"]), (1000.0, False, 1))

    def test_hover_shows_the_item_by_its_global_position_and_a_covered_cell_its_anchor_s(self):
        def flow(world, window):
            self.page(world, window, 1)
            if world.nui_on:
                for event, index in (("cell_over", 0), ("cell_out", 0), ("cell_over", 5), ("cell_over", 10),
                                     ("cell_out", 10)):
                    w4.fire(window, event, index)
            else:
                for event, index in (("over_in", 0), ("over_out", None), ("over_in", 5), ("over_out", None)):
                    window.wndItem.fire(event, *(() if index is None else (index,)))
        (_, _, a), (_, _, b) = self.run_both(flow)
        self.assertEqual(b.tooltipItem.shown, a.tooltipItem.shown)
        self.assertEqual(b.tooltipItem.shown, [("SetSafeBoxItem", 45), ("SetSafeBoxItem", 50)])

    def test_a_drag_marks_the_grid_attaching_and_its_footprint(self):
        world, window = self.world(True)
        self.open(world, window)
        world.attach(P["SLOT_TYPE_INVENTORY"], 0, SWORD)
        with world.game:
            w4.fire(window, "cell_over", 17)
        model = w4.board(window).model
        self.assertTrue(model["attaching"])
        self.assertEqual(sorted(cell["index"] for cell in model["cells"] if cell["target"] == "move"), [17, 22])
        with world.game:
            world.mouse.DeattachObject()
        self.assertFalse(w4.board(window).model["attaching"])


class SafeboxFacade(SafeboxTest):
    def test_the_class_the_methods_and_no_per_frame_python(self):
        world, window = self.world(True)
        legacy_class = world.m("uiSafebox").SafeboxWindow
        self.assertIsInstance(window, legacy_class)
        self.assertTrue(window.NUI_FACADE)
        for name in ("SetItemToolTip", "ShowWindow", "RefreshSafebox", "RefreshSafeboxMoney", "CommandCloseSafebox",
                     "IsShow", "Destroy"):
            self.assertTrue(callable(getattr(window, name)), name)
        for name, member in inspect.getmembers(legacy_class, inspect.isfunction):
            if name in ("OnUpdate", "OnRender"):
                continue
            self.assertEqual(len(inspect.signature(getattr(type(window), name)).parameters),
                             len(inspect.signature(member).parameters), name)
        for module_name in ("nui_safebox", "nui_safebox_password", "nui_change_password", "nui_mall"):
            module = world.m(module_name)
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ == module_name:
                    for attr in ("OnUpdate", "OnRender"):
                        self.assertFalse(callable(getattr(cls, attr, None)), "%s.%s.%s" % (module_name, name, attr))

    def test_make_builds_legacy_with_the_flag_off_or_an_older_exe(self):
        world, window = self.world(False)
        self.assertIs(type(window), world.m("uiSafebox").SafeboxWindow)
        world, window = self.world(True, engine_4=False)
        self.assertIs(type(window), world.m("uiSafebox").SafeboxWindow)
        self.assertIs(type(window.dlgChangePassword), world.m("uiSafebox").ChangePasswordDialog)

    def test_on_demand_the_place_and_the_0_by_0_window(self):
        (legacy, a), (novaui, b) = (self.world(False), self.world(True))
        self.assertNotIn(SAFEBOX_DOCUMENT, novaui.documents())
        self.open(novaui, b)
        self.assertIn(SAFEBOX_DOCUMENT, novaui.documents())
        self.assertEqual(w4.board(b).placement, ("position", 100, 20, (0.0, 0.0)), "legacy's (100, 20)")
        self.assertEqual((b.GetWidth(), b.GetHeight()), (0, 0))
        self.assertEqual(b.flags, a.flags)
        self.assertIn("float", b.flags)

    def test_a_refresh_while_hidden_reaches_the_next_board(self):
        world, window = self.world(True)
        world.game.w4["safebox"]["items"][7] = {"vnum": POTION, "count": 9}
        self.open(world, window)
        self.assertEqual(cells_of(window, window.wndItem)[7], (POTION, "9"))

    def test_open_arms_the_watch_without_a_rearm(self):
        world, window = self.world(True)
        mark = world.mark()
        self.open(world, window)
        args = world.calls_since(mark, "nuigame.WatchLeaveRange")[0][1]
        self.assertEqual((args[0], args[1], args[3]), ("safebox", 1000, False))

    def test_every_fixture_has_the_model_s_keys_and_kinds(self):
        world, window = self.world(True)
        kinds = w4.model_kinds(window.nui_model())
        for variant in ("", "foundation", "one-page", "attaching"):
            self.assertEqual(w4.fixture_keys(window, "safebox", variant), kinds, variant)


# --- the password dialog ---------------------------------------------------------------------------

class PasswordTest(unittest.TestCase):
    def world(self, nui_on, **kwargs):
        world = w4.World(nui_on, setup=stock, **kwargs)
        window = world.make("safebox", "uiSafebox", "PasswordDialog", "nui_safebox.PasswordDialog")
        with world.game, w4.quiet():
            window.Hide()
        return world, window

    def ask(self, world, window, title="PASSWORD_TITLE", command="/safebox_password "):
        """Interface.AskSafeboxPassword (or AskMallPassword)."""
        with world.game, w4.quiet():
            window.SetTitle(getattr(world.m("localeInfo"), title))
            window.SetSendMessage(command)
            window.ShowDialog()

    def type(self, world, window, text):
        if world.nui_on:
            w4.board(window).insert_text(FIELD, text)
        else:
            window.passwordValue.SetText(text)

    def run_both(self, flow, **ask):
        results = []
        for nui_on in (False, True):
            world, window = self.world(nui_on)
            self.ask(world, window, **ask)
            mark = world.mark()
            with world.game, w4.quiet():
                flow(world, window)
            results.append((world.effects_since(mark), world, window))
        return results

    def test_the_dialog_shows_the_title_focuses_the_field_and_is_modal(self):
        world, window = self.world(True)
        self.ask(world, window)
        board = w4.board(window)
        self.assertEqual(board.model["title"], world.m("localeInfo").PASSWORD_TITLE)
        self.assertEqual(board.model["max"], 6)
        self.assertEqual(board.focused, FIELD)
        self.assertTrue(board.modal)
        self.assertEqual(board.placement, None, "the scrim centers it")

    def test_enter_sends_the_password_and_closes(self):
        def flow(world, window):
            self.type(world, window, "000000")
            if world.nui_on:
                self.assertTrue(w4.board(window).key(FIELD, KEY_RETURN), "the field keeps Enter")
            else:
                window.passwordValue.OnIMEReturn()
        (legacy, _, a), (novaui, world, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual(novaui, [("net.SendChatPacket", ("/safebox_password 000000",))])
        self.assertFalse(b.IsShow())
        self.assertNotIn(PASSWORD_DOCUMENT, world.documents())

    def test_ok_sends_the_mall_s_command(self):
        def flow(world, window):
            self.type(world, window, "123456")
            if world.nui_on:
                w4.press(window, "accept_press", 0)
            else:
                window.GetChild("accept_button").click()
        (legacy, _, _), (novaui, _, b) = self.run_both(flow, title="MALL_PASSWORD_TITLE", command="/mall_password ")
        self.assertEqual(novaui, legacy)
        self.assertEqual(novaui, [("net.SendChatPacket", ("/mall_password 123456",))])

    def test_cancel_escape_and_the_close_button_send_nothing(self):
        for how in ("cancel", "escape", "x", "escape-on-dialog"):
            def flow(world, window, how=how):
                self.type(world, window, "999999")
                if not world.nui_on:
                    {"cancel": lambda: window.GetChild("cancel_button").click(),
                     "escape": window.passwordValue.OnPressEscapeKey,
                     "escape-on-dialog": window.passwordValue.OnPressEscapeKey,
                     "x": lambda: window.GetChild("titlebar").close()}[how]()
                elif how == "cancel":
                    w4.press(window, "cancel_press", 0)
                elif how == "x":
                    w4.press(window, "close_press", 0)
                else:
                    self.assertTrue(w4.board(window).key(FIELD if how == "escape" else "", KEY_ESCAPE))
            (legacy, _, _), (novaui, _, b) = self.run_both(flow)
            with self.subTest(how=how):
                self.assertEqual(novaui, legacy)
                self.assertEqual(novaui, [])
                self.assertFalse(b.IsShow())

    def test_the_password_never_enters_a_model(self):
        world, window = self.world(True)
        self.ask(world, window)
        board = w4.board(window)
        board.insert_text(FIELD, "424242")
        self.assertNotIn("424242", repr(board.model))
        self.assertNotIn("424242", repr(window._state))
        with world.game, w4.quiet():
            self.assertTrue(board.key(FIELD, KEY_RETURN))
        self.assertIn(("net.SendChatPacket", ("/safebox_password 424242",)), world.game.log)

    def test_a_second_ask_starts_empty_and_focused(self):
        world, window = self.world(True)
        self.ask(world, window)
        w4.board(window).insert_text(FIELD, "12")
        with world.game, w4.quiet():
            window.CloseDialog()
        self.ask(world, window)
        board = w4.board(window)
        self.assertEqual(board.get_value(FIELD), "")
        self.assertEqual(board.focused, FIELD)

    def test_the_class_make_and_the_fixtures(self):
        world, window = self.world(True)
        legacy_class = world.m("uiSafebox").PasswordDialog
        self.assertIsInstance(window, legacy_class)
        for name in ("Hide", "SetTitle", "SetSendMessage", "ShowDialog", "CloseDialog", "Destroy"):
            self.assertTrue(callable(getattr(window, name)), name)
        for name, member in inspect.getmembers(legacy_class, inspect.isfunction):
            self.assertEqual(len(inspect.signature(getattr(type(window), name)).parameters),
                             len(inspect.signature(member).parameters), name)
        self.assertNotIn(PASSWORD_DOCUMENT, world.documents())
        kinds = w4.model_kinds(window.nui_model())
        for variant in ("", "mall"):
            self.assertEqual(w4.fixture_keys(window, "safebox-password", variant), kinds, variant)
        legacy_world, legacy = self.world(False)
        self.assertIs(type(legacy), legacy_world.m("uiSafebox").PasswordDialog)


# --- the change-password dialog -----------------------------------------------------------------------

class ChangePasswordTest(unittest.TestCase):
    def world(self, nui_on):
        """The dialog as the safebox makes it."""
        world = w4.World(nui_on, setup=stock)
        safebox = world.make("safebox", "uiSafebox", "SafeboxWindow", "nui_safebox.SafeboxWindow")
        return world, safebox, safebox.dlgChangePassword

    def run_both(self, flow):
        results = []
        for nui_on in (False, True):
            world, safebox, dialog = self.world(nui_on)
            with world.game, w4.quiet():
                safebox.OnChangePassword()
            mark = world.mark()
            with world.game, w4.quiet():
                flow(world, dialog)
            results.append((world.effects_since(mark), world, dialog))
        return results

    def fill(self, world, dialog, old, new, check):
        if world.nui_on:
            board = w4.board(dialog)
            for field_id, text in ((OLD, old), (NEW, new), (CHECK, check)):
                board.insert_text(field_id, text)
        else:
            dialog.oldPassword.SetText(old)
            dialog.newPassword.SetText(new)
            dialog.newPasswordCheck.SetText(check)

    def accept(self, world, dialog):
        if world.nui_on:
            w4.press(dialog, "accept_press", 0)
        else:
            dialog.GetChild("accept_button").click()

    def test_open_focuses_the_old_field_and_tab_and_enter_move_on_as_legacy(self):
        world, safebox, dialog = self.world(True)
        with world.game, w4.quiet():
            safebox.OnChangePassword()
        board = w4.board(dialog)
        self.assertTrue(board.modal)
        self.assertEqual(board.focused, OLD)
        seen = []
        with world.game, w4.quiet():
            for field_id, key in ((OLD, KEY_TAB), (NEW, KEY_TAB), (CHECK, KEY_TAB), (OLD, KEY_RETURN), (NEW, KEY_RETURN)):
                self.assertTrue(board.key(field_id, key), "the field keeps the key")
                seen.append(board.focused)
        self.assertEqual(seen, [NEW, CHECK, OLD, NEW, CHECK], "OnNextFocus: old, new, check, old")

    def test_matching_fields_send_the_change_command_and_close(self):
        def flow(world, dialog):
            self.fill(world, dialog, "000000", "135790", "135790")
            self.accept(world, dialog)
        (legacy, _, a), (novaui, world, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual(novaui, [("net.SendChatPacket", ("/safebox_change_password 000000 135790",))])
        self.assertFalse(b.IsShow())
        self.assertNotIn(CHANGE_DOCUMENT, world.documents())

    def test_enter_in_the_check_field_accepts(self):
        def flow(world, dialog):
            self.fill(world, dialog, "000000", "246802", "246802")
            if world.nui_on:
                self.assertTrue(w4.board(dialog).key(CHECK, KEY_RETURN))
            else:
                # ui.EditLine.OnIMEReturn: the click (the host plays it for a
                # NovaUI field), then the return event.
                dialog.newPasswordCheck.eventReturn()
        (legacy, _, _), (novaui, _, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual(novaui, [("net.SendChatPacket", ("/safebox_change_password 000000 246802",))])

    def test_differing_fields_show_the_message_whose_ok_clears_the_new_fields(self):
        """The password check (spec 5.4.4): no packet; the dialog kit's message
        with SAFEBOX_WRONG_PASSWORD (D13); its OK clears the new fields and
        focuses the new one, once, with no recursion."""
        world, safebox, dialog = self.world(True)
        with world.game, w4.quiet():
            safebox.OnChangePassword()
            self.fill(world, dialog, "000000", "111111", "222222")
            mark = world.mark()
            self.accept(world, dialog)
        effects = world.effects_since(mark)
        self.assertEqual([name for name, _ in effects], ["uiCommon.PopupDialog.Open"])
        self.assertIn(world.m("localeInfo").SAFEBOX_WRONG_PASSWORD, effects[0][1])
        self.assertTrue(dialog.IsShow())
        popup = dialog.dlgMessage.dialog
        board = w4.board(dialog)
        self.assertTrue(board.model["covered"], "the message's scrim dims alone (finding 9: no stacked scrims)")
        with world.game, w4.quiet():
            # The kit's and legacy's popup: Close hides, then runs its accept event.
            popup.Close()
            popup.accept()
        self.assertEqual((board.get_value(OLD), board.get_value(NEW), board.get_value(CHECK)), ("000000", "", ""))
        self.assertEqual(board.focused, NEW)
        self.assertFalse(dialog.dlgMessage.IsShow())
        self.assertFalse(board.model["covered"])
        markup = w4.read(os.path.join(w4.WINDOWS_DIR, "change-password", "change-password.rml"))
        self.assertIn('data-class-change-password--covered="covered"', markup)

    def test_the_legacy_message_path_matches(self):
        def flow(world, dialog):
            self.fill(world, dialog, "000000", "111111", "222222")
            self.accept(world, dialog)
        (legacy, _, a), (novaui, _, b) = self.run_both(flow)
        self.assertEqual([call for call in novaui if call[0].startswith("net.")], [])
        self.assertEqual([call for call in legacy if call[0].startswith("net.")], [])
        self.assertTrue(a.dlgMessage.IsShow())
        self.assertTrue(b.dlgMessage.IsShow())

    def test_escape_cancel_and_the_close_button_close_it(self):
        for how in ("escape", "cancel", "x", "escape-on-dialog"):
            def flow(world, dialog, how=how):
                self.fill(world, dialog, "000000", "1", "1")
                if not world.nui_on:
                    {"escape": dialog.newPassword.OnPressEscapeKey,
                     "escape-on-dialog": dialog.oldPassword.OnPressEscapeKey,
                     "cancel": lambda: dialog.GetChild("cancel_button").click(),
                     "x": lambda: dialog.GetChild("titlebar").close()}[how]()
                elif how == "cancel":
                    w4.press(dialog, "cancel_press", 0)
                elif how == "x":
                    w4.press(dialog, "close_press", 0)
                else:
                    self.assertTrue(w4.board(dialog).key(NEW if how == "escape" else "", KEY_ESCAPE))
            (legacy, _, _), (novaui, _, b) = self.run_both(flow)
            with self.subTest(how=how):
                self.assertEqual(novaui, legacy)
                self.assertEqual(novaui, [])
                self.assertFalse(b.IsShow())

    def test_the_safebox_s_close_command_closes_it_too(self):
        world, safebox, dialog = self.world(True)
        with world.game, w4.quiet():
            safebox.ShowWindow(27)
            safebox.OnChangePassword()
            safebox.CommandCloseSafebox()
        self.assertFalse(dialog.IsShow())
        self.assertNotIn(CHANGE_DOCUMENT, world.documents())

    def test_the_class_and_the_fixture(self):
        world, safebox, dialog = self.world(True)
        legacy_class = world.m("uiSafebox").ChangePasswordDialog
        self.assertIsInstance(dialog, legacy_class)
        for name, member in inspect.getmembers(legacy_class, inspect.isfunction):
            self.assertEqual(len(inspect.signature(getattr(type(dialog), name)).parameters),
                             len(inspect.signature(member).parameters), name)
        self.assertEqual(w4.fixture_keys(dialog, "change-password"), w4.model_kinds(dialog.nui_model()))


# --- the mall --------------------------------------------------------------------------------------

class MallTest(unittest.TestCase):
    def world(self, nui_on, **kwargs):
        world = w4.World(nui_on, setup=stock, **kwargs)
        window = world.make("mall", "uiSafebox", "MallWindow", "nui_mall.MallWindow")
        with world.game, w4.quiet():
            window.SetItemToolTip(world.tooltip)
        return world, window

    def open(self, world, window):
        """Interface.OpenMallWindow(135), then the server's items (RefreshMall)."""
        with world.game, w4.quiet():
            window.ShowWindow(135)
            window.RefreshMall()

    def run_both(self, flow):
        results = []
        for nui_on in (False, True):
            world, window = self.world(nui_on)
            self.open(world, window)
            mark = world.mark()
            with world.game, w4.quiet():
                flow(world, window)
            results.append((world.effects_since(mark), world, window))
        return results

    def press(self, world, window, cell):
        if world.nui_on:
            w4.press(window, "cell_press", cell, 0)
            return
        window.SetTop()
        slots = window.wndItem
        slots.fire("select_item" if slots.slots[cell]["vnum"] else "select_empty", cell)

    def test_one_page_of_45_cells_shows_the_first_45_of_the_mall(self):
        (_, _, a), (_, _, b) = self.run_both(lambda world, window: None)
        self.assertEqual(cells_of(b, b.wndItem), legacy_cells(a.wndItem))
        self.assertEqual(cells_of(b, b.wndItem), {1: (GLAIVE, ""), 2: (POTION, "3")}, "D16: cell 50 is not shown")
        model = w4.board(b).model
        self.assertEqual((len(model["cells"]), model["cols"]), (45, 5))
        self.assertEqual((model["cells"][1]["type"], model["cells"][1]["ref"]), (P["SLOT_TYPE_MALL"], 1))

    def test_a_press_on_an_item_attaches_it(self):
        (legacy, world, _), (novaui, _, _) = self.run_both(lambda world, window: self.press(world, window, 2))
        self.assertEqual(novaui, legacy)
        self.assertEqual(novaui, [("mouse.AttachObject", (P["SLOT_TYPE_MALL"], 2, POTION, 0)),
                                  ("snd.PlaySound", ("sound/ui/pick.wav",))])

    def test_any_drop_on_the_mall_is_refused(self):
        for cell in (10, 1):
            def flow(world, window, cell=cell):
                world.attach(P["SLOT_TYPE_INVENTORY"], 9, HELMET)
                self.press(world, window, cell)
            (legacy, world, _), (novaui, _, _) = self.run_both(flow)
            with self.subTest(cell=cell):
                self.assertEqual(novaui, legacy)
                self.assertEqual([name for name, _ in novaui],
                                 ["mouse.AttachObject", "chat.AppendChat", "mouse.DeattachObject"])
                self.assertFalse(world.mouse.isAttached())

    def test_the_close_buttons_and_escape_send_the_close_command(self):
        for how in ("exit", "x", "escape"):
            def flow(world, window, how=how):
                if how == "escape":
                    window.OnPressEscapeKey()
                elif world.nui_on:
                    w4.press(window, "close_press", 0)
                elif how == "exit":
                    window.GetChild("ExitButton").click()
                else:
                    window.GetChild("TitleBar").close()
            (legacy, _, _), (novaui, _, _) = self.run_both(flow)
            with self.subTest(how=how):
                self.assertEqual(novaui, legacy)
                self.assertEqual(novaui, [("net.SendChatPacket", ("/mall_close",))])

    def test_the_interface_s_destroy_of_a_shown_mall_stops_its_watch(self):
        world, window = self.world(True)
        self.open(world, window)
        nuigame = world.game.modules["nuigame"]
        self.assertIsNotNone(nuigame.LeaveRangeState("mall"))
        with world.game, w4.quiet():
            window.Destroy()
        self.assertIsNone(nuigame.LeaveRangeState("mall"))

    def test_the_server_s_close_hides_it_and_moving_away_closes_once(self):
        def flow(world, window):
            world.game.w4["position"] = (0.0, -1500.0, 0.0)
            if world.nui_on:
                support.leave_range(world.game, "mall")
                support.leave_range(world.game, "mall")
            else:
                window.OnUpdate()
            window.CommandCloseMall()
        (legacy, _, a), (novaui, world, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual([call for call in novaui if call[0].startswith("net.")], [("net.SendChatPacket", ("/mall_close",))])
        self.assertFalse(b.IsShow())
        self.assertNotIn(MALL_DOCUMENT, world.documents())
        self.assertIsNone(world.game.modules["nuigame"].LeaveRangeState("mall"))

    def test_hover_shows_the_mall_item_and_a_covered_cell_its_anchor_s(self):
        def flow(world, window):
            if world.nui_on:
                for event, index in (("cell_over", 1), ("cell_over", 6), ("cell_over", 11), ("cell_out", 11)):
                    w4.fire(window, event, index)
            else:
                window.wndItem.fire("over_in", 1)
                window.wndItem.fire("over_out")
        (_, _, a), (_, _, b) = self.run_both(flow)
        self.assertEqual(b.tooltipItem.shown, a.tooltipItem.shown)
        self.assertEqual(b.tooltipItem.shown, [("SetMallItem", 1)])

    def test_the_facade_on_demand_the_place_and_the_fixtures(self):
        world, window = self.world(True)
        legacy_class = world.m("uiSafebox").MallWindow
        self.assertIsInstance(window, legacy_class)
        self.assertIsNone(type(window).OnUpdate)
        for name, member in inspect.getmembers(legacy_class, inspect.isfunction):
            if name in ("OnUpdate", "OnRender"):
                continue
            self.assertEqual(len(inspect.signature(getattr(type(window), name)).parameters),
                             len(inspect.signature(member).parameters), name)
        self.assertNotIn(MALL_DOCUMENT, world.documents())
        self.open(world, window)
        self.assertEqual(w4.board(window).placement, ("position", 100, 20, (0.0, 0.0)))
        self.assertEqual((window.GetWidth(), window.GetHeight()), (0, 0))
        kinds = w4.model_kinds(window.nui_model())
        for variant in ("", "foundation", "empty", "attaching"):
            self.assertEqual(w4.fixture_keys(window, "mall", variant), kinds, variant)
        legacy_world, legacy = self.world(False)
        self.assertIs(type(legacy), legacy_world.m("uiSafebox").MallWindow)
        engine_world, older = self.world(True, engine_4=False)
        self.assertIs(type(older), engine_world.m("uiSafebox").MallWindow)


class Wiring(unittest.TestCase):
    def test_the_interface_makes_them_through_make(self):
        text = w4.read(os.path.join(w4.ROOT, "interfacemodule.py"))
        for line in ('wndSafebox = nui_windows.make("safebox", uiSafebox.SafeboxWindow, "nui_safebox.SafeboxWindow")',
                     'wndMall = nui_windows.make("mall", uiSafebox.MallWindow, "nui_mall.MallWindow")',
                     'self.dlgPassword = nui_windows.make("safebox", uiSafebox.PasswordDialog, "nui_safebox.PasswordDialog")'):
            self.assertIn(line, text)


if __name__ == "__main__":
    unittest.main()
