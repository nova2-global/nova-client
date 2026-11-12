"""Wave 10's item conveniences on the client (story NOVA-184; scope
.nui-work/w10/scopes/qol-items-client.md), in the legacy windows and in
NovaUI's:

- NOVA-185: the wheel over the inventory turns its bag page;
- NOVA-186: the wheel reaches legacy windows (the C++ half is
  eterpythonlib_tests' WindowManager wheel cases; the cube's list is in
  cube_renewal_test);
- NOVA-188: a newly received item glows until hovered, an active item glows
  by its kind (item_glow.py), the option turns the "new" glow off;
- NOVA-192: the tooltip names Ctrl + click (shop search), Shift + right-click
  (the wiki) and a safebox item's right-click only where they work;
- NOVA-193: Ctrl + click and Shift + right-click in the special inventory;
- NOVA-194: an NPC's cheap gold-only buy asks nothing;
- NOVA-202: Alt over a costume previews it on the player (costume_preview.py,
  the two popups).

    cd tools && python3 -B -m unittest qol_items_client_test
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nui_game_support as support  # noqa: E402
import nui_test_support  # noqa: E402
import nui_inventory_test as inv  # noqa: E402
import nui_extra_inventory_test as xinv  # noqa: E402
import nui_shop_test as shops  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import toggle_items_test as toggles  # noqa: E402

ROOT = support.ROOT
NUI = os.path.normpath(os.path.join(ROOT, "..", "nui", "nui"))
INVENTORY, EXTRA = 1, 6


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


# --- NOVA-185: the wheel turns the inventory's page ---------------------------------

class InventoryWheel(inv.Pair):
    def test_a_notch_down_shows_the_next_page_and_up_the_previous_in_both_uis(self):
        legacy, novaui = self.worlds()
        a, b = legacy.make_inventory(), novaui.make_inventory()
        with legacy.game, inv.quiet():
            self.assertTrue(a.OnScrollWheel(-120), "the window takes the turn: no camera zoom")
        with novaui.game, inv.quiet():
            inv.fire(b, "wheel", 1.0)
        self.assertEqual((a.inventoryPageIndex, b.inventoryPageIndex), (1, 1))
        self.assertEqual(inv.board(b).model["page"], 1)
        self.assertEqual(inv.Model.shown_bag(self, novaui, b), a.wndItem.shown())

        with legacy.game, inv.quiet():
            a.OnScrollWheel(120)
        with novaui.game, inv.quiet():
            inv.fire(b, "wheel", -1.0)
        self.assertEqual((a.inventoryPageIndex, b.inventoryPageIndex), (0, 0))

    def test_the_first_and_the_last_page_stop_it(self):
        world = inv.World(False)
        window = world.make_inventory()
        with world.game, inv.quiet():
            self.assertTrue(window.OnScrollWheel(120))
            self.assertEqual(window.inventoryPageIndex, 0)
            for _ in range(10):
                window.OnScrollWheel(-120)
        self.assertEqual(window.inventoryPageIndex, len(window.inventoryTab) - 1)

    def test_the_document_sends_the_wheel(self):
        text = read(os.path.join(NUI, "windows", "inventory", "inventory.rml"))
        self.assertIn('data-event-mousescroll="wheel(ev.wheel_delta_y)"', text)


# --- NOVA-188: glows -------------------------------------------------------------------

class Glows(inv.Pair):
    def shown(self, setup):
        legacy, novaui = self.worlds(setup)
        return legacy, novaui, legacy.make_inventory(), novaui.make_inventory()

    @staticmethod
    def board_glows(window):
        return dict((cell["index"], cell["glow"]) for cell in inv.board(window).model["bag"]
                    if cell["kind"] == "item" and cell["active"])

    def test_an_active_item_glows_by_its_kind(self):
        legacy, novaui, a, b = self.shown(toggles.toggles({toggles.PET, toggles.MOUNT, toggles.TAG, toggles.HAND}))
        glow = legacy.m("item_glow")
        expected = {9: glow.RED, toggles.CELLS[toggles.PET]: glow.CYAN, toggles.CELLS[toggles.MOUNT]: glow.YELLOW,
                    toggles.CELLS[toggles.TAG]: glow.VIOLET, toggles.CELLS[toggles.HAND]: glow.RED}
        self.assertEqual(a.wndItem.glows(), expected)
        self.assertEqual(self.board_glows(b), dict((cell, glow.glow_name(color)) for cell, color in expected.items()))

    def test_an_sp_potion_glows_blue(self):
        def sp(game):
            game.give(10, 72727, 1, sockets=(1, 0, 1000))
        legacy, novaui, a, b = self.shown(inv.with_state(sp))
        self.assertEqual(a.wndItem.glows()[10], legacy.m("item_glow").BLUE)
        self.assertEqual(self.board_glows(b)[10], "blue")

    def mark(self, world, window, cell):
        with world.game, inv.quiet():
            self.assertTrue(world.m("item_glow").mark_new(INVENTORY, cell))
            window.RefreshBagSlotWindow()

    def test_a_new_item_glows_until_it_is_hovered(self):
        legacy, novaui, a, b = self.shown(inv.stock)
        for world, window in ((legacy, a), (novaui, b)):
            self.mark(world, window, 4)
        self.assertEqual(a.wndItem.glows()[4], 0, "the untinted glow")
        self.assertEqual(self.board_glows(b)[4], "")

        for world, window in ((legacy, a), (novaui, b)):
            with world.game, inv.quiet():
                inv.Input(world, window).over("bag", 4)
        self.assertNotIn(4, a.wndItem.glows())
        self.assertNotIn(4, self.board_glows(b))

    def test_an_active_kind_wins_over_new(self):
        legacy, _, a, _ = self.shown(inv.stock)
        self.mark(legacy, a, 9)
        self.assertEqual(a.wndItem.glows()[9], legacy.m("item_glow").RED)

    def test_with_the_option_off_nothing_is_marked_and_the_kinds_keep_their_colors(self):
        legacy, _, a, _ = self.shown(inv.stock)
        legacy.game.modules["systemSetting"].IsShowNewItemHighlight = lambda: 0
        with legacy.game, inv.quiet():
            self.assertFalse(legacy.m("item_glow").mark_new(INVENTORY, 4))
            a.RefreshBagSlotWindow()
        self.assertEqual(a.wndItem.glows(), {9: legacy.m("item_glow").RED})

    def test_a_cell_that_empties_forgets_it_was_new(self):
        legacy, _, a, _ = self.shown(inv.stock)
        self.mark(legacy, a, 4)
        del legacy.game.items[4]
        with legacy.game, inv.quiet():
            a.RefreshBagSlotWindow()
        self.assertFalse(legacy.m("item_glow").is_new(INVENTORY, 4))

    def test_the_documents_bind_the_tints(self):
        for name in ("inventory", "extra-inventory"):
            text = read(os.path.join(NUI, "windows", name, name + ".rml"))
            for color in ("red", "blue", "yellow", "cyan", "violet"):
                self.assertIn("data-class-is-glow-%s=\"c.glow == '%s'\"" % (color, color), text, name)
        sheet = read(os.path.join(NUI, "components", "slot-grid.rcss"))
        self.assertIn(".nui-slot-grid--lean > .nui-slot.is-active.is-glow-cyan", sheet)
        classic = read(os.path.join(NUI, "skins", "classic", "classic.rcss"))
        self.assertIn(".skin-classic .nui-slot.is-glow-cyan .nui-slot__active img", classic)


class ExtraNewItems(xinv.Pair):
    def test_a_new_item_of_the_special_inventory_glows_until_hovered(self):
        legacy, novaui = self.worlds()
        a, b = legacy.make_extra(), novaui.make_extra()
        cell = xinv.cell(xinv.MATERIALS, 5)
        for world, window in ((legacy, a), (novaui, b)):
            with world.game, xinv.quiet():
                world.m("item_glow").mark_new(EXTRA, cell)
                window.RefreshItemSlot()
        self.assertEqual(a.wndItem.glows(), {5: 0})
        board = [c for c in xinv.board(b).model["cells"] if c["active"]]
        self.assertEqual([c["index"] for c in board], [5])

        for world, window in ((legacy, a), (novaui, b)):
            with world.game, xinv.quiet():
                xinv.Input(world, window).over(5)
        self.assertEqual(a.wndItem.glows(), {})
        self.assertEqual([c for c in xinv.board(b).model["cells"] if c["active"]], [])


# --- NOVA-193: shop search and wiki in the special inventory ----------------------------

class ExtraShortcuts(xinv.Pair):
    def turn_on(self, search=True):
        def before(world, window):
            world.m("item_shortcuts").set_shop_search(search)
        return before

    def test_ctrl_click_searches_the_shops_for_the_item(self):
        def flow(w, win, i):
            i.keys("DIK_LCONTROL")
            i.press(0)
        legacy, _, _ = self.same(flow, before=self.turn_on())
        self.assertIn(("interface.OpenSearchShop", (xinv.ORE,)), legacy)
        self.assertNotIn("mouse.AttachObject", [name for name, _ in legacy])

    def test_without_the_shop_search_ctrl_click_picks_the_item_up(self):
        def flow(w, win, i):
            i.keys("DIK_LCONTROL")
            i.press(0)
        legacy, _, _ = self.same(flow, before=self.turn_on(False))
        self.assertNotIn("interface.OpenSearchShop", [name for name, _ in legacy])
        self.assertIn("mouse.AttachObject", [name for name, _ in legacy])

    def test_shift_right_click_opens_the_wiki(self):
        def flow(w, win, i):
            w.game.wiki_opens = True
            i.keys("DIK_LSHIFT")
            i.press(5, 1)
        legacy, _, _ = self.same(flow)
        self.assertIn(("interface.OpenWikiItem", (xinv.BEAN,)), legacy)
        self.assertNotIn("net.SendItemUsePacket", [name for name, _ in legacy])

    def test_where_the_wiki_cannot_open_the_item_is_used(self):
        def flow(w, win, i):
            w.game.wiki_opens = False
            i.keys("DIK_LSHIFT")
            i.press(5, 1)
        legacy, _, _ = self.same(flow)
        self.assertIn(("net.SendItemUsePacket", (EXTRA, xinv.cell(xinv.MATERIALS, 5))), legacy)


# --- NOVA-192: tooltip hints ---------------------------------------------------------------

class TooltipHints(unittest.TestCase):
    ITEMS = {
        "27001": {"name": "Red Potion", "type": "USE", "subtype": "USE_POTION"},
        "41001": {"name": "Costume", "type": "COSTUME", "subtype": "COSTUME_BODY", "size": [1, 2]},
    }

    def texts(self, window, cell, search=False, wiki=False, safebox=False, safebox_item=False, any_cell=True):
        import nui_tooltip_corpus as corpus_tool
        rows = {"items": dict((k, dict(v, icon="icon/item/%s.tga" % k, desc="", summary=""))
                              for k, v in self.ITEMS.items()), "skills": {}, "mobs": {}}
        world = corpus_tool.TipWorld(rows, recorder=False)
        world.game.modules["player"].EXTRA_INVENTORY = EXTRA
        world.game.modules["net"].SAFEBOX_CHECKOUT_ANY_CELL = 0xFFFF
        safebox_module = world.game.modules["safebox"]
        support.define(safebox_module, "GetItemID", lambda slot: 27001)
        support.define(safebox_module, "GetItemMetinSocket", lambda slot, i: 0)
        support.define(safebox_module, "GetItemAttribute", lambda slot, i: (0, 0))
        support.define(safebox_module, "GetItemFlags", lambda slot: 0)
        with world, inv.quiet():
            world.m("item_shortcuts").set_shop_search(search)
            world.m("item_shortcuts").set_wiki(wiki)
            tooltip_module = world.m("uiToolTip")
            tooltip_module.SAFEBOX_ANY_CELL_HINT = any_cell
            tooltip_module.SetSafeboxOpen(safebox)
            support.apply_case(world.game, {"vnum": 27001, "pos": cell, "count": 2})
            tip = world.tooltip("item")
            if safebox_item:
                tip.SetSafeBoxItem(cell)
            else:
                tip.SetInventoryItem(cell, window)
            tooltip_module.SetSafeboxOpen(False)
        return [row[1] for row in corpus_tool.stand_in_rows(tip) if row[0] == "text"]

    def setUp(self):
        self.locale = support.locale_info("en")

    def test_ctrl_click_and_shift_right_click_are_named_where_they_work(self):
        texts = self.texts(INVENTORY, 3, search=True, wiki=True)
        self.assertIn(self.locale.SEARCH_IN_SHOPS, texts)
        self.assertIn(self.locale.SEARCH_IN_WIKI, texts)
        texts = self.texts(EXTRA, 230, search=True, wiki=True)
        self.assertIn(self.locale.SEARCH_IN_SHOPS, texts)
        self.assertIn(self.locale.SEARCH_IN_WIKI, texts)

    def test_a_shortcut_that_does_not_work_is_not_named(self):
        texts = self.texts(INVENTORY, 3)
        self.assertNotIn(self.locale.SEARCH_IN_SHOPS, texts, "no shop search")
        self.assertNotIn(self.locale.SEARCH_IN_WIKI, texts, "no wiki")
        texts = self.texts(INVENTORY, 3, search=True, wiki=True, safebox=True)
        self.assertNotIn(self.locale.SEARCH_IN_SHOPS, texts, "the safebox takes Ctrl and Shift")
        self.assertNotIn(self.locale.SEARCH_IN_WIKI, texts)

    def test_a_safebox_item_says_a_right_click_takes_it_out(self):
        self.assertIn(self.locale.MOVE_FROM_SAFEBOX_TO_INVENTORY, self.texts(None, 2, safebox=True, safebox_item=True))
        self.assertNotIn(self.locale.MOVE_FROM_SAFEBOX_TO_INVENTORY,
                         self.texts(None, 2, safebox=True, safebox_item=True, any_cell=False),
                         "only with NOVA-191's any-cell checkout")
        self.assertNotIn(self.locale.MOVE_FROM_SAFEBOX_TO_INVENTORY, self.texts(INVENTORY, 3, safebox=True))


# --- NOVA-194: no question for a cheap NPC buy ----------------------------------------------

class CheapBuys(shops.ShopTest):
    def setup(self, price=1000, barter=False, coin=0):
        base = shops.shop_stock(tabs=2)

        def setup(game):
            base(game)
            row = game.w4["shop"]["tabs"][0]["items"][3]
            row["price"] = price
            game.w4["shop"]["tabs"][1]["coin"] = coin
            if barter:
                game.w4["shop"]["tabs"][0]["items"][1]["costs"] = [(27001, 2)]
        return setup

    def buy(self, world, window, cell):
        self.toggle(world, window, "buy")
        self.press(world, window, cell)

    def packets(self, effects):
        return [c for c in effects if c[0].startswith("net.SendShopBuy")]

    def test_a_gold_buy_under_a_billion_asks_nothing(self):
        (legacy, _, a), (novaui, _, b) = self.run_both(lambda w, win: self.buy(w, win, 3), self.setup(999999999))
        self.assertEqual(novaui, legacy)
        self.assertEqual(self.packets(novaui), [("net.SendShopBuyPacket", (3,))])
        self.assertNotIn("uiCommon.QuestionDialog.Open", [name for name, _ in novaui])

    def test_a_billion_and_more_still_asks(self):
        def flow(w, win):
            self.buy(w, win, 3)
            win.itemBuyQuestionDialog.accept()
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, self.setup(1000000000))
        self.assertEqual(novaui, legacy)
        self.assertIn("uiCommon.QuestionDialog.Open", [name for name, _ in novaui])
        self.assertEqual(self.packets(novaui), [("net.SendShopBuyPacket", (3,))])

    def test_a_player_s_shop_still_asks(self):
        def flow(w, win):
            self.press(w, win, 2, 1)
            win.itemBuyQuestionDialog.accept()
        (_, _, _), (novaui, _, _) = self.run_both(flow, vid=shops.PLAYER_SHOP)
        self.assertIn("uiCommon.QuestionDialog.Open", [name for name, _ in novaui])

    def test_the_rule_reads_the_row_s_tab_coin_and_costs(self):
        world, window = self.world(True, self.setup())
        self.open(world, window)
        with world.game, w4.quiet():
            self.assertTrue(window.BuysWithoutQuestion(3))
            self.assertFalse(window.BuysWithoutQuestion(3, count=2), "a multi-buy asks")
        world, window = self.world(True, self.setup(coin=1))
        self.open(world, window)
        with world.game, w4.quiet():
            self.assertFalse(window.BuysWithoutQuestion(40), "a secondary coin tab asks")


# --- NOVA-202: the costume preview ------------------------------------------------------------

class FakeItems(object):
    """item and player stand-ins for costume_preview alone."""

    def __init__(self):
        self.item = types.ModuleType("item")
        self.player = types.ModuleType("player")
        it = self.item
        it.ITEM_TYPE_COSTUME, it.ITEM_TYPE_ARMOR = 28, 2
        it.COSTUME_TYPE_BODY, it.COSTUME_TYPE_HAIR, it.COSTUME_TYPE_WEAPON = 0, 1, 4
        it.COSTUME_TYPE_SASH, it.COSTUME_TYPE_SASH2 = 6, 7
        it.ITEM_ANTIFLAG_FEMALE, it.ITEM_ANTIFLAG_MALE = 1, 2
        it.ITEM_ANTIFLAG_WARRIOR, it.ITEM_ANTIFLAG_ASSASSIN, it.ITEM_ANTIFLAG_SURA, it.ITEM_ANTIFLAG_SHAMAN = 4, 8, 16, 32
        it.EQUIPMENT_BODY, it.EQUIPMENT_WEAPON = 90, 94
        it.COSTUME_SLOT_BODY, it.COSTUME_SLOT_HAIR, it.COSTUME_SLOT_WEAPON = 100, 101, 104
        it.COSTUME_SLOT_SASH, it.COSTUME_SLOT_SASH2 = 106, 107
        self.rows = {
            41001: (28, 0, 0, 0),           # a body costume
            45001: (28, 1, 0, 5),           # a hair costume, hair part 5
            40101: (28, 4, 0, 0),           # a weapon costume
            86001: (28, 7, 0, 0),           # a sash costume
            41002: (28, 0, 1 | 4, 0),       # a body costume for men... not warriors
            11299: (2, 0, 0, 0),            # an armor
        }
        selected = [0]

        def select(vnum):
            selected[0] = vnum
        it.SelectItem = select
        it.GetItemType = lambda: self.rows[selected[0]][0]
        it.GetItemSubType = lambda: self.rows[selected[0]][1]
        it.IsAntiFlag = lambda flag: bool(self.rows[selected[0]][2] & flag)
        it.GetValue = lambda index: self.rows[selected[0]][3] if index == 3 else 0
        it.GetItemName = lambda: "item %d" % selected[0]
        self.worn = {90: 11299, 94: 19, 100: 0, 101: 0, 104: 0, 106: 0, 107: 0}
        self.player.GetItemIndex = lambda cell: self.worn.get(cell, 0)
        self.player.GetRace = lambda: 0
        self.player.IsShowCostumes = lambda: True
        self.player.IsShowWeapon = lambda: True


class Popup(object):
    def __init__(self):
        self.calls = []

    def ShowPreview(self, vnum, look):
        self.calls.append(("show", vnum, look))
        return True

    def HidePreview(self):
        self.calls.append(("hide",))


class CostumePreview(unittest.TestCase):
    def setUp(self):
        self.fake = FakeItems()
        self.modules = nui_test_support.Modules(item=self.fake.item, player=self.fake.player)
        self.addCleanup(self.modules.restore)
        self.cp = self.modules.load("costume_preview", "costume_preview.py")
        self.popup = Popup()
        self.cp.set_popup(self.popup)

    def test_the_plan_dresses_the_player_s_look_with_the_hovered_costume(self):
        self.assertEqual(self.cp.plan(41001), (0, 41001, 19, 0, 0), "the body; the worn weapon")
        self.assertEqual(self.cp.plan(45001), (0, 11299, 19, 5, 0), "the hair costume's part")
        self.assertEqual(self.cp.plan(40101), (0, 11299, 40101, 0, 0))
        self.assertEqual(self.cp.plan(86001), (0, 11299, 19, 0, 86001))

    def test_the_worn_costumes_are_part_of_the_look_while_they_show(self):
        self.fake.worn.update({100: 41001, 101: 45001})
        self.assertEqual(self.cp.plan(40101), (0, 41001, 40101, 5, 0))
        self.fake.player.IsShowCostumes = lambda: False
        self.assertEqual(self.cp.plan(40101), (0, 11299, 40101, 0, 0))

    def test_an_item_that_is_no_costume_or_that_the_player_cannot_wear_has_no_plan(self):
        self.assertIsNone(self.cp.plan(11299), "an armor")
        self.assertIsNone(self.cp.plan(41002), "a warrior cannot wear it")
        self.assertIsNone(self.cp.plan(0))

    def test_the_popup_shows_while_the_key_is_held_over_a_costume(self):
        self.cp.hover(41001)
        self.assertEqual(self.popup.calls, [], "no key, no popup")
        self.cp.key(True)
        self.assertEqual(self.popup.calls, [("show", 41001, (0, 41001, 19, 0, 0))])
        self.cp.leave()
        self.assertEqual(self.popup.calls[-1], ("hide",))
        self.cp.hover(41001)
        self.assertEqual(self.popup.calls[-1][0], "show", "a hover with the key held shows at once")
        self.cp.key(False)
        self.assertEqual(self.popup.calls[-1], ("hide",))
        self.assertFalse(self.cp.is_shown())

    def test_a_hover_on_another_item_hides_it(self):
        self.cp.key(True)
        self.cp.hover(41001)
        self.cp.hover(11299)
        self.assertEqual(self.popup.calls[-1], ("hide",))

    def test_the_popup_stands_left_of_the_tooltip_or_right_where_the_left_has_no_room(self):
        width, half = self.cp.POPUP_WIDTH, self.cp.TOOLTIP_HALF
        self.assertEqual(self.cp.popup_origin(800, 300, 1600), (800 - half - width, 300 + self.cp.POPUP_TOP))
        self.assertEqual(self.cp.popup_origin(100, 300, 1600), (100 + half, 300 + self.cp.POPUP_TOP))
        self.assertEqual(self.cp.popup_origin(1590, 10, 1600)[0], 1590 - half - width)


class CostumePreviewWiring(unittest.TestCase):
    """The windows hand their hovers to costume_preview, game.py the key."""

    def test_each_window_hands_its_hover_and_its_leave(self):
        for name, hovers in (("uishop.py", 2), ("uiexchange.py", 2), ("uicuberenewal.py", 1), ("uisearchshop.py", 1)):
            text = read(os.path.join(ROOT, name))
            self.assertEqual(text.count("costume_preview.hover("), hovers, name)
            self.assertEqual(text.count("costume_preview.leave()"), 1, name)
        game = read(os.path.join(ROOT, "game.py"))
        self.assertIn("costume_preview.key(True)", game)
        self.assertIn("costume_preview.key(False)", game)

    def test_the_interface_makes_the_popup_through_the_factory(self):
        text = read(os.path.join(ROOT, "interfacemodule.py"))
        self.assertIn('nui_windows.make("costume-preview", uiCostumePreview.CostumePreview,', text)
        self.assertIn("costume_preview.set_popup(self.wndCostumePreview)", text)
        self.assertIn("costume_preview.set_popup(None)", text)


class Popups(unittest.TestCase):
    """The two popups put the look into the model preview "costume" and show
    or hide it; NovaUI's names the costume in its board."""

    def world(self):
        world = inv.World(True)
        self.calls = calls = []
        preview = types.ModuleType("modelpreview")
        preview.Select = lambda name, race: calls.append(("Select", name, race)) or 1
        preview.SetParts = lambda name, *parts: calls.append(("SetParts", name) + parts) or 1
        preview.Show = lambda name, shown: calls.append(("Show", name, shown))
        world.game.modules["modelpreview"] = preview
        return world

    def test_the_novaui_popup_shows_the_look_and_the_name_then_hides(self):
        world = self.world()
        with world.game, inv.quiet():
            world.game.load("uiCostumePreview", "uicostumepreview.py")
            module = world.game.load("nui_costume_preview", "nui_costume_preview.py")
            popup = module.CostumePreview()
            self.assertTrue(popup.ShowPreview(41001, (0, 41001, 19, 0, 0)))
            self.assertTrue(popup.IsShow())
            popup.HidePreview()
            self.assertFalse(popup.IsShow())
        self.assertEqual(self.calls, [("Select", "costume", 0), ("SetParts", "costume", 41001, 19, 0, 0),
                                      ("Show", "costume", True), ("Show", "costume", False)])

    def test_the_legacy_popup_without_render_targets_shows_nothing(self):
        world = self.world()
        with world.game, inv.quiet():
            module = world.game.load("uiCostumePreview", "uicostumepreview.py")
            popup = module.CostumePreview()
            self.assertIsNone(popup.view, "this ui stand-in has no RenderTarget")
            self.assertFalse(popup.ShowPreview(41001, (0, 41001, 19, 0, 0)))


if __name__ == "__main__":
    unittest.main()
