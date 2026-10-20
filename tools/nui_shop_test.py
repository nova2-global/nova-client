"""Tests for the NovaUI shop and private shop builder
(assets/root/nui_shop.py, nui_private_shop.py; P16 spec 5.2, 5.3):
python3 -B -m unittest nui_shop_test (from tools/).

The legacy uiShop.ShopDialog and uiPrivateShopBuilder.PrivateShopBuilder
(made from their real uiscripts by nui_game_support's stand-ins) and the
NovaUI ones, each in a world of its own with the same state
(nui_w4_world.World), driven through every flow of spec 5.2.4 and 5.3.4: the
legacy slot window's C++ events and buttons against the board's data events.
They make the same W4_COMPARED calls, sounds and dialogs in the same order
(getters left out), and the board shows what legacy's widgets show. The one
difference is the distance rule: legacy closes the shop on every frame while
out of range, NovaUI once (spec 2.1)."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402

P = w4.P
I = support.module_constants()["item"]
A = support.APP_CONSTANTS
SHOP_DOCUMENT = "nui/windows/shop/shop.rml"
BUILDER_DOCUMENT = "nui/windows/private-shop/private-shop.rml"
SWORD, GLAIVE, POTION, HELMET, SHIELD, RING = 10, 3000, 27001, 12200, 13000, 70043
NPC, PLAYER_SHOP, ME = 9003, 5000, 1


def shop_stock(tabs=1, private=False):
    """An NPC (9003) whose shop holds a sword at 0, a glaive at 1, 200
    potions at 2 and a helmet at 3 on its first tab, a shield at 0 of each
    later tab; the tester's inventory: a sword at 0, 50 potions at 4, a ring
    that cannot be sold at 13, a valuable helmet at 9."""
    def setup(game):
        game.give(0, SWORD, size=(1, 2))
        game.give(4, POTION, 50)
        game.give(9, HELMET)
        game.give(13, RING)
        game.item_sizes[GLAIVE] = (1, 3)
        game.antiflags[RING] = I["ANTIFLAG_SELL"]
        game.w4["valuable"].add(9)
        game.w4["npcs"].add(NPC)
        game.w4["vid"] = ME
        names = ("Weapons", "Armour", "Potions")
        shop = game.w4["shop"]
        shop["tabs"] = [{"name": names[i], "coin": 0, "items": [None] * 40} for i in range(tabs)]
        first = shop["tabs"][0]["items"]
        first[0] = {"vnum": SWORD, "count": 1, "price": 1000}
        first[1] = {"vnum": GLAIVE, "count": 1, "price": 5000}
        first[2] = {"vnum": POTION, "count": 200, "price": 50}
        first[3] = {"vnum": HELMET, "count": 1, "price": 700}
        for tab in shop["tabs"][1:]:
            tab["items"][0] = {"vnum": SHIELD, "count": 1, "price": 900}
        w4.mirror_inventory(game)
    return setup


class ShopTest(unittest.TestCase):
    def world(self, nui_on, setup=None, **kwargs):
        world = w4.World(nui_on, setup=setup or shop_stock(), **kwargs)
        window = world.make("shop", "uiShop", "ShopDialog", "nui_shop.ShopDialog")
        with world.game, w4.quiet():
            window.LoadDialog()
            window.Hide()
            window.SetItemToolTip(world.tooltip)
        return world, window

    def open(self, world, window, vid=NPC):
        """Interface.OpenShopDialog (interfacemodule.py:669-673) without the
        inventory."""
        with world.game, w4.quiet():
            window.Open(vid)
            window.SetTop()

    def run_both(self, flow, setup=None, vid=NPC):
        results = []
        for nui_on in (False, True):
            world, window = self.world(nui_on, setup)
            self.open(world, window, vid)
            mark = world.mark()
            with world.game, w4.quiet():
                flow(world, window)
            results.append((world.effects_since(mark), world, window))
        return results

    def legacy_cells(self, window):
        return dict((index, (vnum, count)) for index, (vnum, count, _) in window.itemSlotWindow.shown().items())

    def board_cells(self, window):
        vnums = window.itemSlotWindow.vnums()
        return dict((cell["index"], (vnums[cell["index"]], cell["count"])) for cell in w4.board(window).model["cells"]
                    if cell["kind"] == "item")

    def press(self, world, window, cell, button=0):
        """A press on a cell: the C++ slot window's event (SAFE_SetButtonEvent:
        left on an empty or a filled cell, right on a filled one), the board's
        cell_press."""
        if world.nui_on:
            w4.press(window, "cell_press", cell, button)
            return
        window.SetTop()
        slots = window.itemSlotWindow
        filled = bool(slots.slots[cell]["vnum"])
        if button == 0:
            slots.fire("select_item" if filled else "select_empty", cell)
        elif filled and not world.mouse.isAttached():
            slots.fire("unselect_item", cell)

    def toggle(self, world, window, name):
        if world.nui_on:
            w4.press(window, name + "_press", 0)
        else:
            window.SetTop()
            getattr(window, "btnBuy" if name == "buy" else "btnSell").click()


class ShopModel(ShopTest):
    def test_an_npc_shop_shows_legacy_s_cells_and_the_buy_and_sell_toggles(self):
        (_, _, a), (_, world, b) = self.run_both(lambda world, window: None)
        self.assertEqual(self.board_cells(b), self.legacy_cells(a))
        self.assertEqual(self.board_cells(b), {0: (SWORD, ""), 1: (GLAIVE, ""), 2: (POTION, "200"), 3: (HELMET, "")})
        model = w4.board(b).model
        self.assertEqual((model["buy_shown"], model["sell_shown"], model["close_shop_shown"], model["tab_group"]),
                         (True, True, False, "none"))
        self.assertEqual(model["cells"][1]["type"], P["SLOT_TYPE_SHOP"])
        self.assertEqual([cell["index"] for cell in model["cells"] if cell["covered"]], [5, 6, 11])

    def test_two_and_three_tabs_show_legacy_s_groups_and_button_states(self):
        for tabs, group, shown in ((2, "middle", 0), (3, "small", 1)):
            (_, _, a), (_, _, b) = self.run_both(lambda world, window: None, shop_stock(tabs))
            model = w4.board(b).model
            legacy_group = a.middleRadioButtonGroup if group == "middle" else a.smallRadioButtonGroup
            downs = [entry[0].down for entry in legacy_group.buttonGroup]
            with self.subTest(tabs=tabs):
                self.assertEqual(model["tab_group"], group)
                self.assertEqual(model["tab"], shown)
                self.assertEqual(a.tabIdx, shown)
                self.assertEqual([t["down"] for t in model["tabs"][:tabs]], downs, "legacy's button states")
                self.assertEqual([t["name"] for t in model["tabs"][:tabs]], ["Weapons", "Armour", "Potions"][:tabs])
                self.assertFalse(model["buy_shown"] or model["sell_shown"], "legacy hides the toggles with tabs")
        self.assertEqual(downs, [True, False, False], "D16: three tabs open on tab 1 with the first button down")

    def test_a_tab_shows_its_items_by_the_real_index(self):
        def flow(world, window):
            if world.nui_on:
                w4.press(window, "tab_press", 1, 0)
            else:
                window.middleRadioButtonGroup.buttonGroup[1][0].click()
        (legacy, _, a), (novaui, _, b) = self.run_both(flow, shop_stock(2))
        self.assertEqual(novaui, legacy)
        self.assertEqual(self.board_cells(b), {0: (SHIELD, "")})
        self.assertEqual(w4.board(b).model["cells"][0]["ref"], 40, "tab 1's real index")
        self.assertEqual(w4.board(b).model["tab"], 1)
        w4.press(b, "tab_press", 1, 0)
        self.assertEqual(w4.board(b).model["tab"], 1, "a press on the tab that is down does nothing")

    def test_a_player_s_shop_and_the_player_s_own(self):
        def setup(game):
            shop_stock()(game)
        (_, _, a), (_, _, b) = self.run_both(lambda world, window: None, setup, vid=PLAYER_SHOP)
        model = w4.board(b).model
        self.assertEqual(model["cells"][0]["type"], P["SLOT_TYPE_PRIVATE_SHOP"])
        self.assertEqual((model["buy_shown"], model["close_shop_shown"]), (True, False))
        (_, _, a), (_, _, b) = self.run_both(lambda world, window: None, setup, vid=ME)
        model = w4.board(b).model
        self.assertEqual((model["buy_shown"], model["sell_shown"], model["close_shop_shown"]), (False, False, True))
        self.assertEqual((a.btnBuy.shown, a.btnClose.shown), (False, True))


class ShopFlows(ShopTest):
    def test_a_right_press_buys_at_an_npc_at_once(self):
        (legacy, _, _), (novaui, _, _) = self.run_both(lambda world, window: self.press(world, window, 2, 1))
        self.assertEqual(novaui, legacy)
        self.assertEqual([c for c in novaui if c[0].startswith("net.")], [("net.SendShopBuyPacket", (2,))])

    def test_a_right_press_on_a_player_s_shop_asks_then_buys(self):
        def flow(world, window):
            self.press(world, window, 2, 1)
            window.itemBuyQuestionDialog.accept()
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, vid=PLAYER_SHOP)
        self.assertEqual(novaui, legacy)
        self.assertEqual([c for c in novaui if c[0].startswith("net.")], [("net.SendShopBuyPacket", (2,))])
        self.assertIn("uiCommon.QuestionDialog.Open", [name for name, _ in novaui])

    def test_buy_mode_asks_on_a_press_and_sell_mode_tells(self):
        def flow(world, window):
            self.toggle(world, window, "buy")
            self.press(world, window, 3)
            window.itemBuyQuestionDialog.accept()
            self.toggle(world, window, "sell")
            self.press(world, window, 3)
            self.toggle(world, window, "sell")
        (legacy, world, a), (novaui, _, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual([c for c in novaui if c[0].startswith("app.SetCursor")],
                         [("app.SetCursor", (A["BUY"],)), ("app.SetCursor", (A["SELL"],)), ("app.SetCursor", (A["NORMAL"],))])
        self.assertIn(("net.SendShopBuyPacket", (3,)), novaui)
        self.assertEqual((w4.board(b).model["buy_down"], w4.board(b).model["sell_down"]), (False, False))

    def test_a_press_with_no_mode_attaches_the_item_and_the_inventory_s_drop_asks(self):
        def flow(world, window):
            self.press(world, window, 1)
            world.mouse.RunCallBack("INVENTORY")
            window.itemBuyQuestionDialog.accept()
        (legacy, world, a), (novaui, _, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertIn(("mouse.AttachObject", (P["SLOT_TYPE_SHOP"], 1, GLAIVE, 1)), novaui)
        self.assertIn(("snd.PlaySound", ("sound/ui/pick.wav",)), novaui)
        self.assertIn(("net.SendShopBuyPacket", (1,)), novaui)

    def test_selling_a_dropped_item(self):
        for position, vnum, expect in ((4, POTION, "now"), (9, HELMET, "asks"), (13, RING, "refused")):
            def flow(world, window, position=position, vnum=vnum, expect=expect):
                world.attach(P["SLOT_TYPE_INVENTORY"], position, vnum, 50 if vnum == POTION else 1)
                self.press(world, window, 20)
                if expect == "asks":
                    window.questionDialog.accept()
            (legacy, world, _), (novaui, _, _) = self.run_both(flow)
            with self.subTest(position=position):
                self.assertEqual(novaui, legacy)
                sells = [c for c in novaui if c[0] == "net.SendShopSellPacketNew"]
                if expect == "refused":
                    self.assertEqual(sells, [])
                    self.assertIn("uiCommon.PopupDialog.Open", [name for name, _ in novaui])
                else:
                    self.assertEqual(sells, [("net.SendShopSellPacketNew", (position, 50 if vnum == POTION else 1, P["INVENTORY"]))])

    def test_another_window_s_item_is_refused_with_legacy_s_sound(self):
        def flow(world, window):
            world.attach(P["SLOT_TYPE_SAFEBOX"], 3, SWORD)
            self.press(world, window, 20)
        (legacy, world, _), (novaui, _, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertIn(("snd.PlaySound", ("sound/ui/loginfail.wav",)), novaui)
        self.assertFalse(world.mouse.isAttached())

    def test_the_own_shop_s_close_asks_then_closes_the_shop(self):
        def flow(world, window):
            if world.nui_on:
                w4.press(window, "close_shop_press", 0)
            else:
                window.btnClose.Click()
            window.questionDialog.accept()
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, vid=ME)
        self.assertEqual(novaui, legacy)
        self.assertIn(("net.SendChatPacket", ("/close_shop",)), novaui)

    def test_the_close_button_and_escape_end_the_shop(self):
        for how in ("close", "escape"):
            def flow(world, window, how=how):
                if how == "close" and world.nui_on:
                    w4.press(window, "close_press", 0)
                elif how == "close":
                    window.titleBar.close()
                else:
                    window.OnPressEscapeKey()
            (legacy, _, a), (novaui, world, b) = self.run_both(flow)
            with self.subTest(how=how):
                self.assertEqual(novaui, legacy)
                self.assertIn(("net.SendShopEndPacket", ()), novaui)
                self.assertFalse(b.IsShow())
                self.assertNotIn(SHOP_DOCUMENT, world.documents())
                self.assertIsNone(world.game.modules["nuigame"].LeaveRangeState("shop"), "Hide stops the watch")

    def test_moving_away_closes_the_shop_once(self):
        def flow(world, window):
            world.game.w4["position"] = (0.0, 1500.0, 0.0)
            if world.nui_on:
                support.leave_range(world.game, "shop")
                support.leave_range(world.game, "shop")
            else:
                window.OnUpdate()
        (legacy, _, _), (novaui, _, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual([c for c in novaui if c[0] == "net.SendShopEndPacket"], [("net.SendShopEndPacket", ())])
        self.assertFalse(b.IsShow())

    def test_hover_shows_the_shop_item_s_tooltip_by_its_real_index(self):
        def flow(world, window):
            if world.nui_on:
                for event, index in (("cell_over", 1), ("cell_over", 6), ("cell_out", 6)):
                    w4.fire(window, event, index)
            else:
                window.itemSlotWindow.fire("over_in", 1)
                window.itemSlotWindow.fire("over_out")
        (_, _, a), (_, _, b) = self.run_both(flow)
        self.assertEqual(b.tooltipItem.shown, a.tooltipItem.shown)
        self.assertEqual(b.tooltipItem.shown, [("SetShopItem", 1)])

    def test_open_arms_the_watch_without_a_rearm(self):
        world, window = self.world(True)
        mark = world.mark()
        self.open(world, window)
        args = world.calls_since(mark, "nuigame.WatchLeaveRange")[0][1]
        self.assertEqual((args[0], args[1], args[3]), ("shop", 1000, False))


class ShopFacade(ShopTest):
    def test_the_class_the_methods_and_no_per_frame_python(self):
        world, window = self.world(True)
        legacy_class = world.m("uiShop").ShopDialog
        self.assertIsInstance(window, legacy_class)
        self.assertIsNone(type(window).OnUpdate)
        self.assertIsNone(type(window).OnRender)
        for name in ("LoadDialog", "Hide", "Destroy", "SetItemToolTip", "Open", "SetTop", "Close", "Refresh"):
            self.assertTrue(callable(getattr(window, name)), name)
        for name, member in inspect.getmembers(legacy_class, inspect.isfunction):
            if name in ("OnUpdate", "OnRender"):
                continue
            self.assertEqual(len(inspect.signature(getattr(type(window), name)).parameters),
                             len(inspect.signature(member).parameters), name)

    def test_make_builds_legacy_with_the_flag_off_or_an_older_exe(self):
        world, window = self.world(False)
        self.assertIs(type(window), world.m("uiShop").ShopDialog)
        world, window = self.world(True, engine_4=False)
        self.assertIs(type(window), world.m("uiShop").ShopDialog)

    def test_on_demand_and_the_place(self):
        world, window = self.world(True)
        self.assertNotIn(SHOP_DOCUMENT, world.documents())
        self.open(world, window)
        self.assertIn(SHOP_DOCUMENT, world.documents())
        self.assertEqual(w4.board(window).placement, ("position", 1600 - 400, 10, (0.0, 0.0)), "legacy's (W - 400, 10)")
        self.assertEqual((window.GetWidth(), window.GetHeight()), (0, 0))

    def test_every_fixture_has_the_model_s_keys_and_kinds(self):
        world, window = self.world(True)
        kinds = w4.model_kinds(window.nui_model())
        for variant in ("", "foundation", "tabs2", "tabs3", "mine", "attaching"):
            self.assertEqual(w4.fixture_keys(window, "shop", variant), kinds, variant)


# --- the private shop builder --------------------------------------------------------------------

def builder_stock(game):
    game.give(4, SWORD, size=(1, 2))
    game.give(7, GLAIVE, size=(1, 3))
    game.give(12, POTION, 200)
    game.give(13, RING)
    game.antiflags[RING] = I["ANTIFLAG_MYSHOP"]
    w4.mirror_inventory(game)


class BuilderTest(unittest.TestCase):
    def world(self, nui_on, **kwargs):
        world = w4.World(nui_on, setup=builder_stock, **kwargs)
        window = world.make("private-shop", "uiPrivateShopBuilder", "PrivateShopBuilder",
                            "nui_private_shop.PrivateShopBuilder")
        with world.game, w4.quiet():
            window.Hide()
            window.SetItemToolTip(world.tooltip)
        return world, window

    def run_both(self, flow, title="Swords, armour and potions cheap"):
        results = []
        for nui_on in (False, True):
            world, window = self.world(nui_on)
            with world.game, w4.quiet():
                window.Open(title)
            mark = world.mark()
            with world.game, w4.quiet():
                flow(world, window)
            results.append((world.effects_since(mark), world, window))
        return results

    def drop(self, world, window, position, vnum, cell, price=None):
        world.attach(P["SLOT_TYPE_INVENTORY"], position, vnum)
        if world.nui_on:
            w4.press(window, "cell_press", cell, 0)
        else:
            window.itemSlot.fire("select_empty", cell)
        board = window.priceInputBoard
        if price is not None and board:
            board.text = str(price)
            board.accept()

    def test_a_drop_asks_the_price_and_stocks_the_item(self):
        def flow(world, window):
            self.drop(world, window, 7, GLAIVE, 3, 5000)
            self.drop(world, window, 12, POTION, 0, 50)
        (legacy, world, a), (novaui, _, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertIn(("shop.AddPrivateShopItemStock", (P["INVENTORY"], 7, 3, 5000)), novaui)
        self.assertEqual(b.itemStock, a.itemStock)
        model = w4.board(b).model
        cells = dict((cell["index"], cell) for cell in model["cells"] if cell["kind"])
        self.assertEqual((cells[3]["ref"], cells[3]["h"], cells[0]["count"]), (7, 3, "200"))
        self.assertEqual(model["title"], "Swords, armour and pot...", "legacy's cut past 25 characters")

    def test_an_item_that_cannot_be_sold_here_is_refused(self):
        (legacy, _, _), (novaui, world, _) = self.run_both(lambda world, window: self.drop(world, window, 13, RING, 5))
        self.assertEqual(novaui, legacy)
        self.assertIn("chat.AppendChat", [name for name, _ in novaui])
        self.assertNotIn("uiCommon.MoneyInputDialog.Open", [name for name, _ in novaui])

    def test_a_press_on_a_stocked_cell_takes_it_out_and_ok_builds(self):
        def flow(world, window):
            self.drop(world, window, 4, SWORD, 0, 1000)
            self.drop(world, window, 12, POTION, 1, 50)
            if world.nui_on:
                w4.press(window, "cell_press", 1, 0)
                w4.press(window, "ok_press", 0)
            else:
                window.itemSlot.fire("select_item", 1)
                window.btnOk.Click()
        (legacy, _, a), (novaui, world, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertIn(("shop.DelPrivateShopItemStock", (P["INVENTORY"], 12)), novaui)
        self.assertIn(("shop.BuildPrivateShop", ("Swords, armour and potions cheap",)), novaui)
        self.assertFalse(b.IsShow())
        self.assertNotIn(BUILDER_DOCUMENT, world.documents())

    def test_close_and_escape_clear_the_stock(self):
        for how in ("close", "x", "escape"):
            def flow(world, window, how=how):
                if how == "escape":
                    window.OnPressEscapeKey()
                elif world.nui_on:
                    w4.press(window, "close_press", 0)
                elif how == "close":
                    window.btnClose.Click()
                else:
                    window.titleBar.close()
            (legacy, _, _), (novaui, _, b) = self.run_both(flow)
            with self.subTest(how=how):
                self.assertEqual(novaui, legacy)
                self.assertIn(("shop.ClearPrivateShopStock", ()), novaui)
                self.assertFalse(b.IsShow())

    def test_hover_shows_the_stocked_item_s_tooltip(self):
        def flow(world, window):
            self.drop(world, window, 7, GLAIVE, 3, 5000)
            if world.nui_on:
                w4.fire(window, "cell_over", 8)
                w4.fire(window, "cell_out", 8)
            else:
                window.itemSlot.fire("over_in", 3)
                window.itemSlot.fire("over_out")
        (_, _, a), (_, _, b) = self.run_both(flow)
        self.assertEqual(b.tooltipItem.shown, a.tooltipItem.shown)
        self.assertEqual(b.tooltipItem.shown, [("SetPrivateShopBuilderItem", P["INVENTORY"], 7, 3)],
                         "a covered cell shows its anchor's (P14b)")

    def test_the_facade_on_demand_the_place_and_the_fixtures(self):
        world, window = self.world(True)
        legacy_class = world.m("uiPrivateShopBuilder").PrivateShopBuilder
        self.assertIsInstance(window, legacy_class)
        self.assertIsNone(type(window).OnUpdate)
        for name in ("Hide", "Destroy", "SetItemToolTip", "Open"):
            self.assertTrue(callable(getattr(window, name)), name)
        self.assertNotIn(BUILDER_DOCUMENT, world.documents())
        with world.game, w4.quiet():
            window.Open("Shop")
        self.assertEqual(w4.board(window).placement, ("center",))
        kinds = w4.model_kinds(window.nui_model())
        for variant in ("", "foundation", "empty", "attaching"):
            self.assertEqual(w4.fixture_keys(window, "private-shop", variant), kinds, variant)
        legacy_world, legacy = self.world(False)
        self.assertIs(type(legacy), legacy_world.m("uiPrivateShopBuilder").PrivateShopBuilder)


if __name__ == "__main__":
    unittest.main()
