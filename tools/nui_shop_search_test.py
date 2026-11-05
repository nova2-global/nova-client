"""Tests of the NovaUI shop search (assets/root/nui_shop_search.py; Wave 5, NOVA-9).

Each flow runs on legacy's uisearchshop.SearchShopWindow and on the NovaUI
facade over offline_shop_test's protocol-6 world (nui_shop_test's
OfflineNuiWorld: the Wave 4 world with NovaUI on or off), and what each sends
(the packets, the Interface's calls, the dialogs) must be the same: the
facade only swaps the widgets for proxies."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_shop_test  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import offline_shop_test as offline  # noqa: E402
import search_shop_test as search  # noqa: E402

PERK = offline.K_PERK_SEARCH_BUY


class SearchWorld(nui_shop_test.OfflineNuiWorld):
    """OfflineNuiWorld with Y2's search module (and the NovaUI one) loaded."""

    def __init__(self, nui_on):
        nui_shop_test.OfflineNuiWorld.__init__(self, nui_on)
        with self.game, w4.quiet():
            self.loaded["uiSearchShop"] = self.game.load("uiSearchShop", "uisearchshop.py")
            if nui_on:
                self.game.load("nui_shop_search", "nui_shop_search.py")

    def search_window(self):
        window = self.w4.make("shop-search", "uiSearchShop", "SearchShopWindow", "nui_shop_search.SearchShopWindow")
        with self, w4.quiet():
            window.BindInterface(self.interface)
            window.SetItemToolTip(self.tooltip)
        return window

    def effects(self, mark):
        return [(name, args) for name, args in self.game.log[mark:]
                if name.startswith(("net.", "interface.", "uiCommon.", "chat.AppendChat"))]


def results(count=30):
    return [search.row(owner_pid=10 + i, slot=i % 8, price=1000 * (i + 1), name="Owner%d" % i) for i in range(count)]


class SearchShopTest(unittest.TestCase):
    def run_both(self, flow, perk=True, rows=None):
        outcomes = []
        for nui_on in (False, True):
            world = SearchWorld(nui_on)
            if perk:
                world.perks.add(PERK)
            world.results = list(results() if rows is None else rows)
            window = world.search_window()
            with world, w4.quiet():
                window.Open()
                window.RefreshItems()
            mark = world.mark()
            with world, w4.quiet():
                flow(world, window)
            outcomes.append((world.effects(mark), world, window))
        (legacy, _, _), (novaui, _, _) = outcomes
        self.assertEqual(novaui, legacy)
        return outcomes

    @staticmethod
    def press_row(world, window, index):
        if world.nui_on:
            w4.fire(window, "row_release", index, 0)
        else:
            window.GetRowWidget(index).OnMouseLeftButtonUp()

    @staticmethod
    def whisper(world, window, index):
        if world.nui_on:
            w4.fire(window, "whisper_press", index, 0)
        else:
            window.GetRowWidget(index).OnWhisper()


class Flows(SearchShopTest):
    def test_the_board_shows_the_first_page_of_results(self):
        _, (_, world, window) = self.run_both(lambda world, window: None)
        model = w4.board(window).model
        shown = [row for row in model["rows"] if row["shown"]]
        self.assertEqual(len(shown), len(window.GetShownRows()))
        self.assertGreater(len(shown), 0)

    def test_a_row_press_asks_to_buy_then_sends_with_the_perk(self):
        def flow(world, window):
            self.press_row(world, window, 0)
            question = getattr(window, "questionDialog", None)
            if question is not None:
                question.accept()
        (effects, _, _), _ = self.run_both(flow)
        self.assertTrue([e for e in effects if e[0].startswith("net.")], "the buy goes out after Yes")

    def test_without_the_perk_a_row_press_sends_nothing(self):
        (effects, _, _), _ = self.run_both(lambda world, window: self.press_row(world, window, 0), perk=False)
        self.assertFalse([e for e in effects if e[0].startswith("net.")])

    def test_the_whisper_button_asks_the_interface_for_the_owner(self):
        (_, legacy_world, _), (_, novaui_world, _) = self.run_both(lambda world, window: self.whisper(world, window, 1))
        whispers = [call for call in novaui_world.interface.calls if call[0] == "OpenWhisperDialog"]
        self.assertEqual(len(whispers), 1, "Interface.OpenWhisperDialog(owner)")
        self.assertEqual(whispers, [call for call in legacy_world.interface.calls if call[0] == "OpenWhisperDialog"])

    def test_the_next_page_shows_the_next_rows(self):
        def flow(world, window):
            window.GoToPage(1)
        _, (_, world, window) = self.run_both(flow)
        self.assertEqual(window.GetCurrentPage(), 1)

    def test_close_and_escape_are_legacy_s(self):
        self.run_both(lambda world, window: window.Close())
        self.run_both(lambda world, window: window.OnPressEscapeKey())


class Lifecycle(SearchShopTest):
    def test_hide_and_show_before_the_init_do_not_raise(self):
        """Live lesson (2026-11-05): ui.Window.__init__ calls Hide before the
        subclass's __init__ has set its attributes."""
        world = SearchWorld(True)
        window = world.search_window()
        cls = type(window)
        bare = cls.__new__(cls)
        with world, w4.quiet():
            for method in ("Hide", "Show"):
                if method in cls.__dict__:
                    getattr(cls, method)(bare)

    def test_the_facade_runs_no_python_per_frame(self):
        world = SearchWorld(True)
        window = world.search_window()
        self.assertIsNone(type(window).OnUpdate)

    def test_the_fixture_has_every_model_key(self):
        world = SearchWorld(True)
        window = world.search_window()
        with world, w4.quiet():
            window.Open()
        self.assertEqual(set(w4.fixture_keys(window, "shop-search")), set(w4.board(window).model))


if __name__ == "__main__":
    unittest.main()
