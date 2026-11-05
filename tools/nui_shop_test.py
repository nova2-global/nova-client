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
import nui_inventory_test as inventory  # noqa: E402
import offline_shop_test as offline  # noqa: E402
import nui_w4_world as w4  # noqa: E402

P = w4.P
I = support.module_constants()["item"]
A = support.APP_CONSTANTS
SHOP_DOCUMENT = "nui/windows/shop/shop.rml"
BUILDER_DOCUMENT = "nui/windows/private-shop/private-shop.rml"
SWORD, GLAIVE, POTION, HELMET, SHIELD, RING = 10, 3000, 27001, 12200, 13000, 70043
NPC, PLAYER_SHOP, ME = 9003, 5000, 1


class OfflineNuiWorld(offline.World):
    """offline_shop_test's protocol-6 state over either legacy or the
    NovaUI factory. The real offlineshopconst is loaded after the Wave 4
    modules, as the live client loads it."""

    def __init__(self, nui_on):
        self.w4 = w4.World(nui_on)
        game = self.game = self.w4.game
        self.shop = {"items": {}, "owner": False, "locked": False, "gold": 0, "pages": 1, "kits": 0,
                     "unlocked": 80, "config": dict(offline.CONFIG),
                     "info": {"sign": "Bob's shop", "channel": 1, "map": 1, "x": 469300, "y": 964200,
                              "seconds_left": 4 * offline.DAY, "kits": 0, "model_vnum": 30000, "style": 0,
                              "gold": 0, "locked": 0, "unlocked_slots": 80}}
        self.perks, self.counts, self.distances = set(), {}, {}
        self.elk, self.map_name = 0, "metin2_map_a1"
        self.selected, self.index, self.results = [0], {}, []
        offline.install_wave5(self)
        self.loaded = {"uiShop": self.w4.m("uiShop")}
        with game, w4.quiet():
            for name, file_name in (("offlineshopconst", "offlineshopconst.py"), ("itemPrices", "itemprices.py")):
                self.loaded[name] = game.load(name, file_name)
        self.tooltip = self.w4.tooltip
        self.interface = offline.FakeInterface(self)
        self.nui_on = nui_on

    def shop_dialog(self):
        with self, w4.quiet():
            dialog = self.w4.make("shop", "uiShop", "ShopDialog", "nui_shop.ShopDialog")
            dialog.LoadDialog()
            dialog.Hide()
            dialog.SetItemToolTip(self.tooltip)
            dialog.BindInterface(self.interface)
        return dialog

    def documents(self):
        return self.w4.documents()


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

    def test_teardown_sends_end_only_when_an_npc_shop_was_the_last(self):
        """Legacy's one window keeps offlineLayout from an offline view until
        the next NPC shop: its Destroy then sends no END."""
        for npc_last in (False, True):
            with self.subTest(npc_last=npc_last):
                world = OfflineNuiWorld(True)
                window = world.shop_dialog()
                with world, w4.quiet():
                    window.Open(77, multiPage=True)
                    window.Close()
                if npc_last:
                    world.game.w4["npcs"].add(NPC)
                    with world, w4.quiet():
                        window.Open(NPC)
                        window.Close()
                mark = world.mark()
                with world, w4.quiet():
                    window.Destroy()
                ends = [call for call in world.game.log[mark:] if call[0] == "net.SendShopEndPacket"]
                self.assertEqual(len(ends), 1 if npc_last else 0)

    def test_the_multi_page_and_owner_views_are_the_subclass_board(self):
        world = OfflineNuiWorld(True)
        world.list_item(3, SWORD, count=2, price=70, pending=True)
        window = world.shop_dialog()
        with world, w4.quiet():
            window.Open(77, multiPage=True)
            board = w4.board(window)
            self.assertTrue(board.model["offline"])
            self.assertEqual((board.model["cols"], len(board.model["cells"])), (10, 80))
            self.assertFalse(hasattr(window, "_offline_dialog"))
            world.shop.update(owner=True, locked=True, gold=123456, pages=3)
            world.shop["info"].update(sign="Night market", locked=1, gold=123456, seconds_left=3600)
            window.OpenOfflineShop(1)
            window.UpdateLock(1)
            window.UpdateTime(3600)
            window.UpdateSign("Night market")
            window.UpdateGold(123456)
            window.OnOfflineShopResult(3, 0, 7)
            self.assertTrue(window.IsOfflineShopOpen())
            model = w4.board(window).model
            self.assertTrue(model["owner"] and model["owner_panel_shown"])
            self.assertEqual((model["owner_sign"], model["owner_gold"]),
                             ("Night market", world.game.modules["localeInfo"].NumberToMoneyString(123456)))
            window.Close()
        self.assertNotIn(SHOP_DOCUMENT, world.documents())

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
        for variant in ("", "foundation", "tabs2", "tabs3", "mine", "attaching", "offline", "offline-owner"):
            self.assertEqual(w4.fixture_keys(window, "shop", variant), kinds, variant)


class OfflineShopFacade(unittest.TestCase):
    """The W5-2 differential: the facade and legacy run the same inherited
    offline methods; only the input widget differs."""

    def open(self, nui_on, owner=False, locked=False, gold=0, pages=3, unlocked=80):
        world = OfflineNuiWorld(nui_on)
        world.shop.update(owner=owner, locked=locked, gold=gold, pages=pages, unlocked=unlocked)
        world.shop["info"].update(locked=int(locked), gold=gold, seconds_left=4 * offline.DAY,
                                  unlocked_slots=unlocked)
        window = world.shop_dialog()
        with world, w4.quiet():
            if owner:
                window.OpenOfflineShop(1)
            else:
                window.Open(7001, multiPage=True)
        return world, window

    def effects(self, world, mark):
        return world.w4.effects_since(mark)

    def cell_press(self, world, window, cell, button):
        if world.nui_on:
            w4.press(window, "cell_press", cell, button)
        else:
            if button == 0:
                filled = bool(window.itemSlotWindow.slots[cell]["vnum"])
                window.itemSlotWindow.fire("select_item" if filled else "select_empty", cell)
            else:
                window.itemSlotWindow.fire("unselect_item", cell)

    def test_view_page_buy_question_packet_and_close_are_legacy_s(self):
        results = []
        for nui_on in (False, True):
            world = OfflineNuiWorld(nui_on)
            world.list_item(84, SWORD, count=2, price=1000000000, id=9084)
            world.shop.update(pages=3, unlocked=160)
            window = world.shop_dialog()
            with world, w4.quiet():
                window.Open(7001, multiPage=True)
                mark = world.mark()
                window.SelectOfflinePage(1)
                self.cell_press(world, window, 4, 1)
                world.dialogs("QuestionDialog")[-1].accept()
                window.Close()
            results.append((self.effects(world, mark), world, window))
        self.assertEqual(results[1][0], results[0][0])
        self.assertIn(("net.SendOfflineShopBuyPacket", (7001, 84, 9084, 1000000000)), results[1][0])
        packets = [call for call in results[1][0] if call[0].startswith("net.Send")]
        self.assertEqual(packets[-1], ("net.SendOfflineShopLeavePacket", ()))
        self.assertNotIn("net.SendShopEndPacket", [name for name, _ in packets])
        self.assertEqual(results[2 - 1][2].GetOfflinePage(), 1)

    def test_pending_is_inert_and_the_next_lock_row_asks_then_expands(self):
        results = []
        for nui_on in (False, True):
            world, window = self.open(nui_on, owner=True, locked=True, pages=3, unlocked=80)
            world.list_item(1, SWORD, pending=True)
            world.counts[offline.KIT] = 1
            with world, w4.quiet():
                window.Refresh()
                pending_disabled = w4.board(window).model["cells"][1]["disabled"] if nui_on else True
                mark = world.mark()
                self.cell_press(world, window, 1, 1)
                self.cell_press(world, window, 1, 0)
                window.SelectOfflinePage(1)
                if nui_on:
                    w4.fire(window, "lock_release", 0, 0)
                else:
                    window.lockOverlays[0].OnMouseLeftButtonUp()
                world.dialogs("QuestionDialog")[-1].accept()
            results.append((self.effects(world, mark), world, window, pending_disabled))
        self.assertEqual(results[1][0], results[0][0])
        self.assertEqual([call for call in results[1][0] if call[0].startswith("net.Send")],
                         [("net.SendShopExpandPacket", ())])
        self.assertTrue(results[1][3])

    def test_owner_add_price_remove_withdraw_and_gold_are_legacy_s(self):
        results = []
        for nui_on in (False, True):
            world, window = self.open(nui_on, owner=True, locked=True, gold=123456, unlocked=160)
            world.list_item(3, SWORD, price=70)
            world.game.give((offline.INVENTORY, 5), SWORD)
            with world, w4.quiet():
                window.Refresh()
                mark = world.mark()
                window.SelectOfflinePage(1)
                world.w4.attach(P["SLOT_TYPE_INVENTORY"], 5, SWORD)
                self.cell_press(world, window, 2, 0)
                price = world.dialogs("BulkMoneyInputDialog")[-1]
                price.text, price.checked = "5000", True
                price.accept()
                window.SelectOfflinePage(0)
                self.cell_press(world, window, 3, 1)
                world.game.pressed.add(A["DIK_LALT"])
                self.cell_press(world, window, 3, 1)
                change = world.dialogs("BulkMoneyInputDialog")[-1]
                change.text = "90"
                change.accept()
                world.game.pressed.clear()
                world.game.pressed.add(A["DIK_LCONTROL"])
                self.cell_press(world, window, 3, 1)
                world.dialogs("CheckQuestionDialog")[-1].accept()
                world.game.pressed.clear()
                window.OpenPickMoneyDialog()
                world.dialogs("PickMoneyDialog")[-1].accept(1000)
            results.append(self.effects(world, mark))
        self.assertEqual(results[1], results[0])
        packets = [call for call in results[1] if call[0].startswith("net.Send")]
        self.assertEqual(packets, [
            ("net.SendShopAddItemPacket", (offline.INVENTORY, 5, 82, 5000, True)),
            ("net.SendShopWithdrawItemPacket", (3,)),
            ("net.SendShopUpdatePricePacket", (3, 90, False)),
            ("net.SendShopRemoveItemPacket", (3, True)),
            ("net.SendShopWithdrawGoldPacket", (1000,)),
        ])

    def test_manage_refresh_updates_result_and_npc_over_panel_are_legacy_s(self):
        results = []
        for nui_on in (False, True):
            world, window = self.open(nui_on, owner=True, locked=False, gold=10)
            world.game.w4["npcs"].add(NPC)
            with world, w4.quiet():
                mark = world.mark()
                window.OpenOfflineShop(0)
                window.UpdateLock(1)
                window.UpdateTime(7200)
                window.UpdateSign("Night market")
                window.UpdateGold(987654)
                window.OnOfflineShopResult(offline.K_OPS.index("LOCK"), offline.K_RESULTS.index("NOT_LOCKED"), 0)
                if nui_on:
                    model = w4.board(window).model
                    self.assertEqual((model["owner_sign"], model["owner_lock_text"]), ("Night market", "Unlock"))
                    self.assertEqual(model["owner_gold"],
                                     world.game.modules["localeInfo"].NumberToMoneyString(987654))
                window.Open(NPC)
                window.Close()
            results.append(self.effects(world, mark))
        self.assertEqual(results[1], results[0])
        packets = [call for call in results[1] if call[0].startswith("net.Send")]
        self.assertEqual(packets, [("net.SendOfflineShopLeavePacket", ()), ("net.SendShopEndPacket", ())])


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

    def test_the_board_takes_the_grid_legacy_s_open_arranges(self):
        """Wave 5 (NOVA-9): legacy's Open arranges CONFIG's base rows of 10
        (ArrangeSlot); the board shows that grid, not the NPC shop's 5
        columns (Eddy, 2026-11-05: 5 x 17 and the cells mixed up)."""
        world, window = self.world(True)
        # The client loads offlineshopconst (Wave 5); this world does not, so
        # legacy's module gets the real one (it imports shop when called).
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "offlineshopconst", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "root", "offlineshopconst.py"))
        offlineshopconst = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(offlineshopconst)
        legacy = [c for c in type(window).__mro__ if c.__module__ == "uiPrivateShopBuilder"][0]
        legacy.__init__.__globals__["offlineshopconst"] = offlineshopconst
        shop_module = world.game.modules["shop"].__dict__
        shop_module.update(OFFLINE_SHOP_COLUMNS=10, OFFLINE_SHOP_ROWS_PER_PAGE=8, OFFLINE_SHOP_PAGE_COUNT=8,
                           OFFLINE_SHOP_SLOT_MAX=640)
        with world.game, w4.quiet():
            window.Open("Night market")
        model = w4.board(window).model
        self.assertEqual((model["cols"], len(model["cells"])), (10, 80), "CONFIG's 8 base rows of 10")
        self.assertEqual(model["cols"], window.itemSlot.cols)
        self.assertEqual(len(model["cells"]), len(window.itemSlot.slot_numbers))
        self.assertEqual(len(model["cells"]) % model["cols"], 0, "whole rows")

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
        creates = [args for name, args in novaui if name == "net.SendOfflineShopCreatePacket"]
        self.assertEqual(len(creates), 1)
        title, model_vnum, style, listings = creates[0]
        self.assertEqual((title, style, listings),
                         ("Swords, armour and potions cheap", 0,
                          [(P["INVENTORY"], 4, 0, 1000)]))
        self.assertIsInstance(model_vnum, int)
        self.assertNotIn(("net.SendOfflineShopLeavePacket", ()), novaui, "CREATE closes without a second LEAVE")
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
                self.assertIn(("net.SendOfflineShopLeavePacket", ()), novaui)
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


# --- wave 4b (NOVA-16, NOVA-13) --------------------------------------------------------------------

EXTRA, SLOT_EXTRA = inventory.EXTRA, inventory.SLOT_EXTRA
ON_TOP = inventory.W4B_PLAYER


def wave4b(stock):
    """`stock`, main's exe's wave 4b names (nui_inventory_test.install_wave4b)
    and three potions at the special inventory's 230."""
    def setup(game):
        stock(game)
        inventory.install_wave4b(game)
        game.give((EXTRA, 230), POTION, 3)
    return setup


def interface_calls(world, mark):
    return world.calls_since(mark, "interface.")


class LockedCells(object):
    """An inventory window as the trade windows see it after the Interface's
    SetInven: its lock calls in the log as <name>.SetCantMouseEventCell and
    <name>.SetCanMouseEventCell."""

    def __init__(self, world, name):
        self._log = world.game.log
        self._name = name

    def SetCantMouseEventCell(self, cell):
        self._log.append((self._name + ".SetCantMouseEventCell", (cell,)))

    def SetCanMouseEventCell(self, cell):
        self._log.append((self._name + ".SetCanMouseEventCell", (cell,)))


class ShopWave4b(ShopTest):
    """The NPC shop puts itself on top (legacy's __SetOnTopWindow in Open,
    OnTop and Close, so the inventories mark what it does not buy) and buys
    an item of the special inventory, all legacy's code; BindInterface and
    OnTop are legacy's."""

    def test_bind_interface_and_on_top_are_legacy_s(self):
        world, window = self.world(True)
        legacy = world.m("uiShop").ShopDialog
        for name in ("BindInterface", "OnTop"):
            self.assertIs(getattr(type(window), name), getattr(legacy, name), name)

    def on_top_flow(self, vid):
        results = []
        for nui_on in (False, True):
            world, window = self.world(nui_on, wave4b(shop_stock()))
            mark = world.mark()
            with world.game, w4.quiet():
                window.BindInterface(world.game.interface)
                window.Open(vid)
                window.SetTop()
                window.Close()
            results.append(interface_calls(world, mark))
        self.assertEqual(results[1], results[0])
        return results[0]

    def test_an_npc_shop_is_on_top_from_open_to_close(self):
        calls = self.on_top_flow(NPC)
        self.assertEqual(calls, [("interface.SetOnTopWindow", (ON_TOP["ON_TOP_WND_SHOP"],)),
                                 ("interface.RefreshMarkInventoryBag", ()),
                                 ("interface.SetOnTopWindow", (ON_TOP["ON_TOP_WND_SHOP"],)),
                                 ("interface.RefreshMarkInventoryBag", ()),
                                 ("interface.SetOnTopWindow", (ON_TOP["ON_TOP_WND_NONE"],)),
                                 ("interface.RefreshMarkInventoryBag", ())])

    def test_a_player_s_shop_is_never_on_top(self):
        calls = self.on_top_flow(PLAYER_SHOP)
        self.assertEqual(calls, [("interface.SetOnTopWindow", (ON_TOP["ON_TOP_WND_NONE"],)),
                                 ("interface.RefreshMarkInventoryBag", ())], "only Close's")

    def test_an_extra_item_dropped_in_is_sold_after_legacy_s_question(self):
        def flow(world, window):
            world.attach(SLOT_EXTRA, 230, POTION, 3)
            self.press(world, window, 20)
            window.questionDialog.accept()
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, wave4b(shop_stock()))
        self.assertEqual(novaui, legacy)
        self.assertIn(("net.SendShopSellPacketNew", (230, 3, EXTRA)), novaui)


class BuilderWave4b(BuilderTest):
    """The builder stocks an item of the special inventory with its window
    (legacy's itemStock), locks its cell in that window while it is stocked
    (SetInven), puts itself on top while open; the stocked cell carries the
    window's slot type. BindInterface, SetInven and RefreshLockedSlot are
    legacy's."""

    def world(self, nui_on, **kwargs):
        kwargs.setdefault("setup", wave4b(builder_stock))
        world = w4.World(nui_on, **kwargs)
        window = world.make("private-shop", "uiPrivateShopBuilder", "PrivateShopBuilder",
                            "nui_private_shop.PrivateShopBuilder")
        with world.game, w4.quiet():
            window.Hide()
            window.SetItemToolTip(world.tooltip)
            window.BindInterface(world.game.interface)
            window.SetInven(LockedCells(world, "inventory"), LockedCells(world, "extra"))
        return world, window

    def drop_extra(self, world, window, position, vnum, cell, price):
        world.attach(SLOT_EXTRA, position, vnum)
        if world.nui_on:
            w4.press(window, "cell_press", cell, 0)
        else:
            window.itemSlot.fire("select_empty", cell)
        board = window.priceInputBoard
        board.text = str(price)
        board.accept()

    def test_bind_interface_and_setinven_are_legacy_s(self):
        world, window = self.world(True)
        legacy = world.m("uiPrivateShopBuilder").PrivateShopBuilder
        for name in ("BindInterface", "SetInven", "RefreshLockedSlot"):
            self.assertIs(getattr(type(window), name), getattr(legacy, name), name)

    def test_an_extra_item_is_stocked_with_its_window_locked_and_shown_by_it(self):
        results = []
        for nui_on in (False, True):
            world, window = self.world(nui_on)
            mark = world.mark()
            with world.game, w4.quiet():
                window.Open("Potions")
                self.drop_extra(world, window, 230, POTION, 3, 50)
                self.drop(world, window, 12, POTION, 0, 60)
                # The press on a cell leaves the NovaUI pointer over it, whose
                # tooltip the next refresh shows (as CSlotWindow's would); the
                # hover below is the one compared.
                window.tooltipItem.shown[:] = []
                if nui_on:
                    w4.fire(window, "cell_over", 3)
                    w4.fire(window, "cell_out", 3)
                else:
                    window.itemSlot.fire("over_in", 3)
                    window.itemSlot.fire("over_out")
                window.Close()
            calls = [(name, args) for name, args in world.game.log[mark:]
                     if name.startswith(("shop.", "interface.", "inventory.", "extra.")) and not support.is_getter(name)]
            results.append((calls, world, window))
        (legacy, _, a), (novaui, _, b) = results
        self.assertEqual(novaui, legacy)
        self.assertEqual(b.tooltipItem.shown, a.tooltipItem.shown)
        self.assertEqual(b.tooltipItem.shown, [("SetPrivateShopBuilderItem", EXTRA, 230, 3)])
        self.assertEqual(legacy[:3], [("shop.ClearPrivateShopStock", ()),
                                      ("interface.SetOnTopWindow", (ON_TOP["ON_TOP_WND_PRIVATE_SHOP"],)),
                                      ("interface.RefreshMarkInventoryBag", ())])
        self.assertIn(("shop.AddPrivateShopItemStock", (EXTRA, 230, 3, 50)), legacy)
        self.assertIn(("extra.SetCantMouseEventCell", (230,)), legacy)
        self.assertIn(("inventory.SetCantMouseEventCell", (12,)), legacy)
        last_clear = len(legacy) - 1 - legacy[::-1].index(("shop.ClearPrivateShopStock", ()))
        self.assertEqual(sorted(legacy[last_clear - 2:last_clear]), [("extra.SetCanMouseEventCell", (230,)),
                                                                    ("inventory.SetCanMouseEventCell", (12,))],
                         "Close releases every stocked cell")
        self.assertEqual(legacy[-2:], [("interface.SetOnTopWindow", (ON_TOP["ON_TOP_WND_NONE"],)),
                                       ("interface.RefreshMarkInventoryBag", ())])

    def test_a_stocked_cell_carries_its_item_s_window(self):
        world, window = self.world(True)
        with world.game, w4.quiet():
            window.Open("Potions")
            self.drop_extra(world, window, 230, POTION, 3, 50)
            self.drop(world, window, 7, GLAIVE, 0, 5000)
        cells = w4.board(window).model["cells"]
        self.assertEqual((cells[3]["type"], cells[3]["ref"]), (SLOT_EXTRA, 230))
        self.assertEqual([(cells[i]["type"], cells[i]["ref"], cells[i]["covered"]) for i in (0, 5, 10)],
                         [(P["SLOT_TYPE_INVENTORY"], 7, False), (P["SLOT_TYPE_INVENTORY"], 7, True),
                          (P["SLOT_TYPE_INVENTORY"], 7, True)])
        with world.game, w4.quiet():
            world.attach(SLOT_EXTRA, 230, POTION, 3)
            w4.fire(window, "cell_over", 3)
        self.assertTrue(w4.board(window).model["cells"][3]["picked"], "the attached extra item's cell")


if __name__ == "__main__":
    unittest.main()
