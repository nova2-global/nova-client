"""Tests for the legacy shop search and the offline shop's log (wave 5, chunk Y2; NOVA-9):
python3 -B -m unittest search_shop_test (from tools/).

The windows run over offline_shop_test's World (the Wave 4 stand-ins, install_wave5);
searchShop is a recording stand-in whose Find, AutoComplete and GetPage answer from
World.index and World.results (C's index is tested in nova-client-src's
search_shop_test.cpp). Spec: 5-spec-v2.md 3.8, 3.10 "Python" (the flag default; the
premium label and the buy gate from the same perk; the log's empty and last states),
2.9 PB-C6, o-cli bugs 7, 8, 14, 21, 22."""
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_w4_world as w4  # noqa: E402
import offline_shop_test as shop_test  # noqa: E402

World = shop_test.World
K_RESULTS = shop_test.K_RESULTS
K_OPS = shop_test.K_OPS
GAME = shop_test.WAVE5_GAME_KEYS
INTERFACE = shop_test.WAVE5_INTERFACE_KEYS
PERK = shop_test.K_PERK_SEARCH_BUY
ASSETS = os.path.dirname(shop_test.ROOT)
SWORD = shop_test.SWORD


def row(owner_pid=10, slot=3, vnum=SWORD, price=1000, count=1, id=None, map_index=1, channel=1, name="Alice"):
    """A searchShop.GetPage row, keyed by TShopSearchRow's and TOfflineShopItem's names."""
    return {"owner_pid": owner_pid, "owner_name": name, "channel": channel, "map": map_index, "slot": slot,
            "id": id or owner_pid * 1000 + slot, "vnum": vnum, "count": count, "price": price,
            "sockets": [0, 0, 0, 0], "attrs": [(0, 0)] * 7}


def search_window(world, open_it=True):
    with world, w4.quiet():
        window = world.m("uiSearchShop").SearchShopWindow()
        window.BindInterface(world.interface)
        window.SetItemToolTip(world.tooltip)
        if open_it:
            window.Open()
    return window


def text_color(text):
    """The last packed color a legacy text line took."""
    colors = [call[1] for call in text.calls if call[0] == "SetPackedFontColor"]
    return colors[-1] if colors else None


def queries(world, mark=0):
    return [args for name, args in world.since(mark) if name == "net.SendSearchShopPacket"]


class Flags(unittest.TestCase):
    """o-cli bug 7: a shop on a map with no empire flag shows none (OLD raised KeyError)."""

    def test_a_map_without_a_flag_shows_none(self):
        world = World()
        with world:
            const = world.m("offlineshopconst")
            self.assertEqual(const.map_empire(99), 0)
            self.assertEqual(const.flag_image(99), "")

    def test_the_village_maps_show_their_empire(self):
        world = World()
        with world:
            const = world.m("offlineshopconst")
            self.assertEqual([const.map_empire(m) for m in (1, 21, 41)], [1, 2, 3])
            for map_index in (1, 21, 41):
                path = const.flag_image(map_index)
                relative = path.replace("d:/ymir work/", "", 1)
                self.assertTrue(os.path.isfile(os.path.join(ASSETS, "ETC", "ymir work", relative)), path)

    def test_a_row_of_another_map_draws_without_a_flag(self):
        world = World()
        world.results = [row(map_index=99), row(slot=4, map_index=21)]
        window = search_window(world)
        with world, w4.quiet():
            window.RefreshItems()
            self.assertEqual(window.GetRowWidget(0).GetFlagImage(), "")
            self.assertFalse(window.GetRowWidget(0).flag.shown)
            self.assertTrue(window.GetRowWidget(1).flag.shown)


class Premium(unittest.TestCase):
    """PB-C6 and o-cli bug 8: the label and the buy gate both read HasPremiumPerk(SEARCH_BUY)
    (OLD showed "Active" for Silver and refused its buy)."""

    def test_without_the_perk_the_label_is_inactive_and_a_buy_is_refused(self):
        world = World()
        world.game.answer("player", "GetPremiumTier", 1)
        world.results = [row()]
        window = search_window(world)
        mark = world.mark()
        with world, w4.quiet():
            window.RefreshItems()
            self.assertEqual(window.premiumText.text, GAME["SEARCH_SHOP_PREMIMUM_INACTIVE"])
            window.GetRowWidget(0).OnMouseLeftButtonUp()
        self.assertEqual([args for name, args in world.since(mark) if name == "net.SendSearchShopBuyPacket"], [])
        self.assertIn(GAME["REQUIRED_PREMIUM_USER"], world.dialogs("PopupDialog")[-1].texts)

    def test_with_the_perk_the_label_is_active_and_a_buy_asks_then_sends(self):
        world = World()
        world.perks.add(PERK)
        world.results = [row(owner_pid=10, slot=3, price=1000, id=777)]
        window = search_window(world)
        mark = world.mark()
        with world, w4.quiet():
            window.RefreshItems()
            self.assertEqual(window.premiumText.text, GAME["SEARCH_SHOP_PREMIMUM_ACTIVE"])
            window.GetRowWidget(0).OnMouseLeftButtonUp()
            question = world.dialogs("QuestionDialog")[-1]
            self.assertEqual(question.texts, [INTERFACE["SEARCH_SHOP_BUY_CONFIGM"]])
            question.accept()
        self.assertEqual([args for name, args in world.since(mark) if name == "net.SendSearchShopBuyPacket"],
                         [(10, 3, 777, 1000)])
        self.assertEqual(window.GetRowState(10, 3), "pending")

    def test_the_label_follows_the_perk_not_the_tier(self):
        world = World()
        window = search_window(world)
        world.game.answer("player", "GetPremiumTier", 3)
        with world, w4.quiet():
            self.assertEqual(window.GetPremiumLabel()[0], GAME["SEARCH_SHOP_PREMIMUM_INACTIVE"])
            self.assertFalse(window.CanBuy())
            world.perks.add(PERK)
            window.OnUpdate()
            self.assertEqual(window.premiumText.text, GAME["SEARCH_SHOP_PREMIMUM_ACTIVE"])
            self.assertTrue(window.CanBuy())

    def test_without_the_perk_the_rows_are_grayed_until_it_arrives(self):
        """Spec 3.8: the buy is grayed without HasPremiumPerk(SEARCH_BUY), by the label's perk (PB-C6); the
        rows follow a perk that changes while they show."""
        world = World()
        world.results = [row(), row(slot=4)]
        window = search_window(world)
        module = world.m("uiSearchShop")
        with world, w4.quiet():
            window.RefreshItems()
            rows = [window.GetRowWidget(0), window.GetRowWidget(1)]
            self.assertEqual([(r.IsBuyable(), text_color(r.nameText), text_color(r.countText)) for r in rows],
                             [(False, module.NO_BUY_COLOR, module.NO_BUY_COLOR)] * 2)
            world.perks.add(PERK)
            window.OnUpdate()
            self.assertEqual([(r.IsBuyable(), text_color(r.nameText), text_color(r.countText)) for r in rows],
                             [(True, module.NAME_COLOR, module.NAME_COLOR)] * 2)
            world.results = [row(slot=5)]
            window.RefreshItems()
            self.assertTrue(window.GetRowWidget(0).IsBuyable())

    def test_the_gold_and_the_label_change_only_when_their_value_does(self):
        """o-cli bug 23 and the wave 2 rule: no text set every frame."""
        world = World()
        window = search_window(world)
        gold = shop_test.Recorder(window.goldText, "SetText")
        label = shop_test.Recorder(window.premiumText, "SetText")
        with world, w4.quiet():
            for _ in range(5):
                window.OnUpdate()
            self.assertEqual((gold.calls, label.calls), ([], []))
            world.elk = 5000
            world.perks.add(PERK)
            window.OnUpdate()
            window.OnUpdate()
        self.assertEqual(len(gold.calls), 1)
        self.assertEqual(label.calls, [(GAME["SEARCH_SHOP_PREMIMUM_ACTIVE"],)])

    def test_an_exe_without_the_perk_binding_cannot_buy(self):
        world = World()
        world.game.modules["player"].lack("HasPremiumPerk")
        window = search_window(world)
        with world, w4.quiet():
            self.assertFalse(window.CanBuy())


class Results(unittest.TestCase):
    """RefreshSearchShop (the last RESULTS frame) reaches RefreshItems(): the rows into the index,
    sorted by price, a page at a time (OLD :366-429)."""

    def test_refresh_items_loads_sorts_and_shows_the_first_page(self):
        world = World()
        world.results = [row(slot=i, price=100 + i) for i in range(30)]
        window = search_window(world)
        mark = world.mark()
        with world, w4.quiet():
            window.RefreshItems()
        calls = [name for name, _ in world.since(mark, "searchShop.")]
        self.assertEqual(calls[:2], ["searchShop.LoadResults", "searchShop.SortByPrice"])
        self.assertEqual([args for name, args in world.since(mark, "searchShop.") if name == "searchShop.SortByPrice"],
                         [(1,)])
        self.assertEqual(len(window.GetShownRows()), 25)
        self.assertEqual(window.GetPageCount(), 2)
        self.assertFalse(window.IsLoading())

    def test_pages_of_25_50_and_100(self):
        world = World()
        world.results = [row(slot=i % 240, owner_pid=10 + i // 240) for i in range(120)]
        window = search_window(world)
        with world, w4.quiet():
            window.RefreshItems()
            window.SetResultPerPage(1)
            self.assertEqual((len(window.GetShownRows()), window.GetPageCount()), (50, 3))
            window.SetResultPerPage(2)
            self.assertEqual((len(window.GetShownRows()), window.GetPageCount()), (100, 2))
            window.GoToPage(5)
            self.assertEqual((window.GetCurrentPage(), len(window.GetShownRows())), (1, 20))

    def test_a_row_shows_its_name_stock_price_and_owner(self):
        world = World()
        world.results = [row(vnum=SWORD, count=7, price=6000000000, name="Alice")]
        window = search_window(world)
        with world, w4.quiet():
            window.RefreshItems()
            bar = window.GetRowWidget(0)
            money = world.game.modules["localeInfo"].NumberToMoneyString(6000000000)
        self.assertEqual(bar.countText.text, GAME["SEARCH_SHOP_IN_STOCK"] % "7")
        self.assertEqual(bar.priceText.text, money)
        self.assertEqual(bar.ownerText.text, "Alice")
        self.assertEqual(bar.nameText.text, "item %d" % SWORD)
        self.assertIn(("SetPackedFontColor", 0xffc02221), bar.priceText.calls)

    def test_a_skill_book_is_named_by_its_skill(self):
        world = World()
        world.game.answer("skill", "GetSkillName", lambda index: "Sword Spin")
        world.results = [dict(row(vnum=50300), sockets=[5, 0, 0, 0])]
        window = search_window(world)
        with world, w4.quiet():
            window.RefreshItems()
            name = window.GetRowWidget(0).nameText.text
            book = world.game.modules["localeInfo"].TOOLTIP_SKILLBOOK_NAME
        self.assertEqual(name, "Sword Spin %s" % book)

    def test_the_row_shapes(self):
        world = World()
        with world:
            const = world.m("offlineshopconst")
            flat = const.search_row(row(owner_pid=10, slot=3, id=77, price=5))
            nested = const.search_row({"owner_pid": 10, "owner_name": "Alice", "channel": 2, "map": 41,
                                       "slot": {"slot": 3, "item": {"id": 77, "vnum": SWORD, "count": 1, "price": 5,
                                                                    "sockets": [1, 2, 3, 4], "attrs": []}}})
            old = const.search_row([10, "Alice", SWORD, 5, 1, 3, [1, 2, 3, 4], [], 0, 77, 41, 2])
        for found in (flat, nested, old):
            self.assertEqual((found["owner_pid"], found["slot"], found["id"], found["price"]), (10, 3, 77, 5))
        self.assertEqual((nested["map"], nested["channel"], old["map"], old["channel"]), (41, 2, 41, 2))


class BuyResult(unittest.TestCase):
    """OnSearchShopBuyResult (SHOP_SEARCH BUY_RESULT) reaches OnBuyResult(code, ownerPid, slot)."""

    def test_ok_marks_the_row_sold(self):
        world = World()
        world.perks.add(PERK)
        world.results = [row(owner_pid=10, slot=3)]
        window = search_window(world)
        with world, w4.quiet():
            window.RefreshItems()
            window.OnBuyResult(0, 10, 3)
            self.assertEqual(window.GetRowState(10, 3), "sold")
            window.GetRowWidget(0).OnMouseLeftButtonUp()
        self.assertEqual([d for d in world.dialogs("QuestionDialog")], [])

    def test_a_refusal_shows_its_text_and_frees_the_row(self):
        world = World()
        window = search_window(world)
        with world, w4.quiet():
            window.OnBuyResult(K_RESULTS.index("SOLD_OUT"), 10, 3)
        self.assertEqual(window.GetRowState(10, 3), "")
        self.assertIn(GAME["OFFLINE_SHOP_RESULT_SOLD_OUT"], world.chat())


class Queries(unittest.TestCase):
    """QUERY (spec 1.1): mode 0 by item (a vnum and a book's skill), mode 1 by category; the name
    lookup is searchShop.Find, which knows every vnum of a name (o-cli bug 21)."""

    def test_the_first_open_browses_everything(self):
        world = World()
        mark = world.mark()
        search_window(world)
        self.assertEqual(queries(world, mark), [(1, 0, 0, 0, 1, 0, 0)])
        self.assertIn("searchShop.BuildIndex", [name for name, _ in world.game.log])

    def test_open_with_an_item_searches_its_name(self):
        world = World()
        world.index["item %d" % SWORD] = [SWORD]
        window = search_window(world, open_it=False)
        mark = world.mark()
        with world, w4.quiet():
            window.Open(SWORD)
        self.assertEqual(queries(world, mark), [(0, SWORD, 0, 0, 0, 0, 0)])

    def test_an_unknown_name_sends_nothing(self):
        world = World()
        window = search_window(world)
        world.game.time += 5
        mark = world.mark()
        with world, w4.quiet():
            self.assertFalse(window.SearchByName("no such thing"))
        self.assertEqual(queries(world, mark), [])
        self.assertIn(GAME["SEARCH_SHOP_WRONG_NAME"], world.chat())

    def test_a_name_of_several_items_sends_one_of_them(self):
        world = World()
        world.index["Twin"] = [SWORD, 20]
        window = search_window(world)
        world.game.time += 5
        mark = world.mark()
        with world, w4.quiet():
            window.SearchByName("Twin")
        self.assertEqual(queries(world, mark), [(0, SWORD, 0, 0, 0, 0, 0)])

    def test_a_skill_book_sends_its_skill(self):
        world = World()
        world.index["Sword Spin Book"] = [(50300, 5)]
        window = search_window(world)
        world.game.time += 5
        mark = world.mark()
        with world, w4.quiet():
            window.SearchByName("Sword Spin Book")
        self.assertEqual(queries(world, mark), [(0, 50300, 0, 5, 0, 0, 0)])

    def test_searches_wait_for_the_cooldown(self):
        world = World(dict(shop_test.CONFIG, search_cooldown_ms=1500))
        world.index["Sword"] = [SWORD]
        window = search_window(world)
        mark = world.mark()
        with world, w4.quiet():
            self.assertFalse(window.SearchByName("Sword"))
            world.game.time += 1.0
            self.assertFalse(window.SearchByName("Sword"))
            world.game.time += 0.6
            self.assertTrue(window.SearchByName("Sword"))
        self.assertEqual(queries(world, mark), [(0, SWORD, 0, 0, 0, 0, 0)])
        self.assertEqual(world.chat().count(GAME["SEARCH_SHOP_WAIT"]), 2)

    def test_the_filter_applies_to_the_next_searches(self):
        world = World()
        window = search_window(world)
        world.game.time += 5
        mark = world.mark()
        with world, w4.quiet():
            window.ApplyFilter(1000, True, False)
            world.game.time += 5
            window.SelectCategory(5, 2)
        self.assertEqual(queries(world, mark), [(1, 0, 1000, 0, 1, 0, 1), (1, 0, 1000, 0, 5, 2, 1)])

    def test_the_costumes_open_their_subcategories(self):
        world = World()
        window = search_window(world)
        world.game.time += 5
        with world, w4.quiet():
            self.assertEqual(len(window.GetCategoryKeys()), 13)
            window.SelectCategory(5)
            self.assertEqual(len(window.GetCategoryKeys()), 13 + 8)
            names = window.categoryList.texts
        self.assertIn(GAME["SEARCH_SHOP_CAT_COSTUMES"], names)
        self.assertTrue(any(GAME["SEARCH_SHOP_COSTUME_SASH"] in name for name in names))

    def test_a_search_clears_the_last_results(self):
        world = World()
        mark = world.mark()
        search_window(world)
        self.assertIn("shop.ClearSearchResults", [name for name, _ in world.game.log[mark:]])

    def test_suggestions_start_at_three_characters(self):
        world = World()
        for index in range(15):
            world.index["Sword %02d" % index] = [index + 1]
        window = search_window(world)
        with world, w4.quiet():
            self.assertEqual(window.GetSuggestions("Sw"), [])
            found = window.GetSuggestions("swo")
        self.assertEqual(len(found), 10)


class GoTo(unittest.TestCase):
    """A right press goes to the shop: on the player's map an arrow (GOTO at once), elsewhere a question
    first (OLD :1230-1240)."""

    def test_the_same_map_follows_the_arrow(self):
        world = World()
        world.results = [row(owner_pid=10, map_index=1)]
        window = search_window(world)
        mark = world.mark()
        with world, w4.quiet():
            window.RefreshItems()
            window.GetRowWidget(0).OnMouseRightButtonUp()
        self.assertEqual([args for name, args in world.since(mark) if name == "net.SendSearchShopGotoPacket"], [(10,)])
        self.assertIn(GAME["SEARCH_SHOP_FOLLOW_SIGNAL"], world.dialogs("PopupDialog")[-1].texts)

    def test_another_map_asks_first(self):
        world = World()
        world.results = [row(owner_pid=10, map_index=21)]
        window = search_window(world)
        mark = world.mark()
        with world, w4.quiet():
            window.RefreshItems()
            window.GetRowWidget(0).OnMouseRightButtonUp()
            self.assertEqual([args for name, args in world.since(mark) if name == "net.SendSearchShopGotoPacket"], [])
            question = world.dialogs("QuestionDialog")[-1]
            self.assertEqual(question.texts, [GAME["SEARCH_SHOP_OTHER_MAP"]])
            question.accept()
        self.assertEqual([args for name, args in world.since(mark) if name == "net.SendSearchShopGotoPacket"], [(10,)])

    def test_the_whisper_button_opens_the_owners_whisper(self):
        world = World()
        world.results = [row(name="Alice")]
        window = search_window(world)
        with world, w4.quiet():
            window.RefreshItems()
            window.GetRowWidget(0).OnWhisper()
        self.assertEqual(world.interface.calls, [("OpenWhisperDialog", "Alice")])


class Bookmarks(unittest.TestCase):
    """Ten saved names in shop/bookmark_list.txt (OLD :1258-1382); no I/O error reaches the UI."""

    def test_the_names_round_trip_and_ten_is_the_most(self):
        world = World()
        module = world.m("uiSearchShop")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "shop", "bookmark_list.txt")
            names = ["n%d" % i for i in range(10)]
            self.assertTrue(module.WriteBookmarks(names, path))
            with world:
                self.assertEqual(module.ReadBookmarks(path), names)
                self.assertEqual(module.ReadBookmarks(os.path.join(folder, "none.txt")), [""] * 10)
            self.assertFalse(module.WriteBookmarks(names, folder))

    def test_the_names_round_trip_under_the_clients_open(self):
        """The client's builtins.open is system.py's open(filename, mode) (offline_shop_test.client_open):
        the bookmarks still persist, as UTF-8 whatever the Windows code page."""
        world = World()
        module = world.m("uiSearchShop")
        names = ["\u00c9p\u00e9e+9"] + ["n%d" % i for i in range(1, 10)]
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "shop", "bookmark_list.txt")
            with world, shop_test.client_open():
                self.assertTrue(module.WriteBookmarks(names, path))
                self.assertEqual(module.ReadBookmarks(path), names)
                self.assertEqual(module.ReadBookmarks(12.5), [""] * 10)
            with open(path, "rb") as handle:
                self.assertEqual(handle.read().split(b"\n")[0], names[0].encode("utf-8"))

    def test_save_fills_the_first_empty_line_until_full(self):
        world = World()
        world.index["Sword"] = [SWORD]
        with tempfile.TemporaryDirectory() as folder:
            world.m("offlineshopconst").BOOKMARK_FILE = os.path.join(folder, "shop", "bookmark_list.txt")
            window = search_window(world)
            with world, w4.quiet():
                window.bookmarkWnd.names = ["x"] * 9 + [""]
                window.SetSearchText("Sword")
                self.assertTrue(window.SaveBookmark())
                self.assertEqual(window.bookmarkWnd.GetNames()[-1], "Sword")
                self.assertFalse(window.bookmarkWnd.Save("Other"))
                window.bookmarkWnd.Select(9)
                saved = world.m("uiSearchShop").ReadBookmarks()
        self.assertIn(INTERFACE["SEARCH_SHOP_BOOKMARK_FULL"], world.chat())
        self.assertEqual(saved, ["x"] * 9 + ["Sword"])
        self.assertEqual(window.inputName.text, "Sword")


class Logs(unittest.TestCase):
    """The log window (o-cli bugs 14, 22): loading until the first answer, empty when the shop has no
    row, the next page once at the end of the view until the last one came; actions from their keys
    with the number as the default; dates in local time."""

    def window(self, world):
        with world, w4.quiet():
            window = world.m("uiOfflineShopLog").OfflineShopLogWindow()
            window.BindInterface(world.interface)
        return window

    def logs(self, world, mark):
        return [args for name, args in world.since(mark) if name == "net.SendOfflineShopLogsPacket"]

    def test_open_asks_page_zero_and_shows_loading(self):
        world = World()
        window = self.window(world)
        mark = world.mark()
        with world, w4.quiet():
            window.Open()
        self.assertEqual(self.logs(world, mark), [(0,)])
        self.assertTrue(window.IsLoading())
        self.assertTrue(window.loadingText.shown)

    def test_an_empty_answer_shows_the_empty_state(self):
        world = World()
        window = self.window(world)
        with world, w4.quiet():
            window.Open()
            window.SetData([], 0, 1)
        self.assertFalse(window.IsLoading())
        self.assertTrue(window.IsEmpty())
        self.assertTrue(window.emptyText.shown)
        self.assertFalse(window.loadingText.shown)

    def test_the_end_of_the_view_asks_the_next_page_once_until_the_last(self):
        world = World()
        window = self.window(world)
        rows = [(1700000000 + i, 5, "Alice", SWORD, 1, 700) for i in range(100)]
        mark = world.mark()
        with world, w4.quiet():
            window.Open()
            window.SetData(rows, 0, 0)
            window.scrollWindow.reach_end()
            window.scrollWindow.reach_end()
            window.SetData(rows[:3], 1, 1)
            window.scrollWindow.reach_end()
        self.assertEqual(self.logs(world, mark), [(0,), (1,)])
        self.assertTrue(window.IsLast())
        self.assertFalse(window.IsEmpty())
        self.assertEqual(len(window.GetRowTexts()), 103)

    def test_a_rate_limited_page_is_asked_again_a_second_later(self):
        """SO1 refuses a LOGS within 1 s with RESULT(LOGS, RATE_LIMITED) and no LOGS frame. The result reaches
        the shop dialog (the contract's row for any op but CREATE), which hands it to the interface's log
        window: it asks again once the second is over, with no chat line."""
        world = World()
        window = self.window(world)
        world.interface.wndOfflineShopLog = window
        dialog = world.shop_dialog()
        rows = [(1700000000 + i, 5, "Alice", SWORD, 1, 700) for i in range(100)]
        mark = world.mark()
        with world, w4.quiet():
            window.Open()
            window.SetData(rows, 0, 0)
            window.scrollWindow.reach_end()
            dialog.OnOfflineShopResult(K_OPS.index("LOGS"), K_RESULTS.index("RATE_LIMITED"), 0)
            self.assertTrue(window.IsLoading())
            window.OnUpdate()
            world.game.time += 1.0
            window.OnUpdate()
            window.OnUpdate()
            window.SetData(rows, 1, 1)
        self.assertEqual(self.logs(world, mark), [(0,), (1,), (1,)])
        self.assertNotIn(GAME["OFFLINE_SHOP_RESULT_RATE_LIMITED"], world.chat())
        self.assertEqual(len(window.GetRowTexts()), 200)

    def test_another_refusal_ends_the_loading_and_the_end_asks_again(self):
        world = World()
        window = self.window(world)
        world.interface.wndOfflineShopLog = window
        dialog = world.shop_dialog()
        mark = world.mark()
        with world, w4.quiet():
            window.Open()
            dialog.OnOfflineShopResult(K_OPS.index("LOGS"), K_RESULTS.index("BUSY"), 0)
            self.assertFalse(window.IsLoading())
            self.assertFalse(window.loadingText.shown)
            world.game.time += 5.0
            window.OnUpdate()
            window.SetData([(1700000000, 5, "Alice", SWORD, 1, 700)] * 30, 0, 0)
            window.scrollWindow.reach_end()
            dialog.OnOfflineShopResult(K_OPS.index("LOCK"), K_RESULTS.index("RATE_LIMITED"), 0)
        self.assertEqual(self.logs(world, mark), [(0,), (1,)])
        self.assertEqual(world.chat(), [GAME["OFFLINE_SHOP_RESULT_BUSY"], GAME["OFFLINE_SHOP_RESULT_RATE_LIMITED"]])

    def test_a_row_reads_its_action_item_amount_and_local_date(self):
        world = World()
        window = self.window(world)
        stamp = 1700000000
        with world, w4.quiet():
            window.Open()
            window.SetData([(stamp, 5, "Alice", SWORD, 2, 700), (stamp, 99, "", 0, 0, 0), (stamp, 4, "", 0, 3, 0)], 0, 1)
            texts = window.GetRowTexts()
            money = world.game.modules["localeInfo"].NumberToMoneyString(700)
            day = world.game.modules["localeInfo"].DAY
        local = time.strftime("%d-%m-%Y %H:%M", time.localtime(stamp))
        self.assertEqual(texts[0], [GAME["OFFLINE_SHOP_LOG_ACTION_5"], "Alice", "item %d (x2)" % SWORD, money, local])
        self.assertEqual(texts[1][0], "99")
        self.assertEqual(texts[2][2], "3 %s" % day)

    def test_an_answer_for_a_closed_window_is_dropped(self):
        world = World()
        window = self.window(world)
        with world, w4.quiet():
            window.SetData([(1700000000, 5, "Alice", SWORD, 1, 700)], 0, 1)
        self.assertEqual(window.GetRowTexts(), [])


if __name__ == "__main__":
    unittest.main()
