"""Tests of the NovaUI offline shop log (assets/root/nui_offline_shop_log.py;
Wave 5, NOVA-9).

Each flow runs on legacy's uiofflineshoplog.OfflineShopLogWindow and on the
NovaUI facade over offline_shop_test's protocol-6 world (nui_shop_test's
OfflineNuiWorld), and what each sends must be the same: the facade only swaps
the widgets for proxies. Legacy's view is its ui.ScrollWindow, whose end event
runs OnEndScroll; NovaUI's is the board's scroll range and wheel. The NovaUI
side also checks what the board shows, the scroll's end rule (once per reach,
none for a page that arrives or for the program's moves) and the retry timer
that replaces legacy's OnUpdate."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_shop_test  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import offline_shop_test as offline  # noqa: E402

KEY = "offline-shop-log"
VIEW_ROWS = 21


def rows(count, start=0, last_vnum=offline.SWORD):
    """`count` LOGS rows, K's tuples (time, action, other, vnum, count, amount):
    sales of the sword to a buyer, items added, an ADD_TIME."""
    made = []
    for i in range(start, start + count):
        action = (5, 6, 4)[i % 3]
        made.append((1762360000 - i * 600, action, "Buyer%d" % i if action == 5 else "",
                     last_vnum if action != 4 else 0, 7 if action == 4 else 1, 1000 * (i + 1) if action == 5 else 0))
    return made


class LogWorld(nui_shop_test.OfflineNuiWorld):
    """OfflineNuiWorld with the log module (and the NovaUI one) loaded."""

    def __init__(self, nui_on):
        nui_shop_test.OfflineNuiWorld.__init__(self, nui_on)
        with self.game, w4.quiet():
            self.loaded["uiOfflineShopLog"] = self.game.load("uiOfflineShopLog", "uiofflineshoplog.py")
            if nui_on:
                self.game.load("nui_offline_shop_log", "nui_offline_shop_log.py")

    def log_window(self):
        window = self.w4.make(KEY, "uiOfflineShopLog", "OfflineShopLogWindow",
                              "nui_offline_shop_log.OfflineShopLogWindow")
        with self, w4.quiet():
            window.BindInterface(self.interface)
        return window

    def logs_sent(self, mark=0):
        return [args for name, args in self.game.log[mark:] if name == "net.SendOfflineShopLogsPacket"]


class LogTest(unittest.TestCase):
    def opened(self, nui_on):
        world = LogWorld(nui_on)
        window = world.log_window()
        with world, w4.quiet():
            window.Open()
        return world, window

    def run_both(self, flow):
        outcomes = []
        for nui_on in (False, True):
            world, window = self.opened(nui_on)
            mark = world.mark()
            with world, w4.quiet():
                flow(world, window)
            outcomes.append((world.since(mark), world, window))
        (legacy, _, legacy_window), (novaui, _, novaui_window) = outcomes
        self.assertEqual(novaui, legacy)
        self.assertEqual(novaui_window.GetRowTexts(), legacy_window.GetRowTexts())
        self.assertEqual((novaui_window.IsLoading(), novaui_window.IsLast(), novaui_window.IsEmpty()),
                         (legacy_window.IsLoading(), legacy_window.IsLast(), legacy_window.IsEmpty()))
        return outcomes

    @staticmethod
    def scroll_to_end(world, window):
        """The user's scroll to the view's end: the bar on NovaUI's board; on
        legacy the event its ui.ScrollWindow runs then."""
        if world.nui_on:
            w4.fire(window, "scroll", 1.0)
        else:
            window.OnEndScroll()

    @staticmethod
    def rate_limited():
        return offline.K_RESULTS.index("RATE_LIMITED")


class Pages(LogTest):
    def test_open_asks_for_page_0_and_shows_loading(self):
        for nui_on in (False, True):
            world, window = self.opened(nui_on)
            self.assertEqual(world.logs_sent(), [(0,)])
            self.assertTrue(window.IsLoading())
        model = w4.board(window).model
        self.assertTrue(model["loading"])
        self.assertFalse(model["empty"])
        self.assertEqual(model["rows"], [])

    def test_a_page_s_rows_are_legacy_s_texts(self):
        _, (_, world, window) = self.run_both(lambda world, window: window.SetData(rows(30), 0, 0))
        model = w4.board(window).model
        self.assertEqual(len(model["rows"]), VIEW_ROWS, "legacy's view of 21 rows")
        texts = window.GetRowTexts()[:VIEW_ROWS]
        self.assertEqual([[r["action"], r["other"], r["what"], r["amount"], r["date"]] for r in model["rows"]], texts)
        self.assertEqual([r["odd"] for r in model["rows"][:4]], [False, True, False, True])
        self.assertTrue(model["scrollable"])
        self.assertFalse(model["loading"])

    def test_the_end_of_the_view_asks_the_next_page_once(self):
        def flow(world, window):
            window.SetData(rows(30), 0, 0)
            self.scroll_to_end(world, window)
            self.scroll_to_end(world, window)
        (sent, _, _), _ = self.run_both(flow)
        self.assertEqual(sent, [("net.SendOfflineShopLogsPacket", (1,))])

    def test_the_last_page_ends_the_asking(self):
        def flow(world, window):
            window.SetData(rows(30), 0, 0)
            self.scroll_to_end(world, window)
            window.SetData(rows(5, 30), 1, 1)
            self.scroll_to_end(world, window)
        (sent, _, _), (_, _, window) = self.run_both(flow)
        self.assertEqual(sent, [("net.SendOfflineShopLogsPacket", (1,))])
        self.assertTrue(window.IsLast())
        self.assertEqual(len(window.GetRowTexts()), 35)

    def test_a_shop_without_rows_is_empty(self):
        _, (_, _, window) = self.run_both(lambda world, window: window.SetData([], 0, 1))
        model = w4.board(window).model
        self.assertTrue(model["empty"])
        self.assertFalse(model["loading"])
        self.assertFalse(model["scrollable"])

    def test_a_refused_page_ends_the_loading(self):
        code = offline.K_RESULTS.index("DISABLED")
        _, (_, _, window) = self.run_both(lambda world, window: window.OnLogsResult(code))
        self.assertFalse(w4.board(window).model["loading"])
        self.assertEqual(w4.board(window).model["retry_end"], 0.0)

    def test_close_and_escape_are_legacy_s(self):
        def close(world, window):
            if world.nui_on:
                w4.press(window, "close_press", 0)
            else:
                window.titleBar.close()
        (_, _, legacy), (_, _, novaui) = self.run_both(close)
        self.assertFalse(novaui.IsShow())
        self.assertFalse(legacy.IsShow())
        self.run_both(lambda world, window: window.OnPressEscapeKey())


class Scroll(LogTest):
    def test_a_page_that_arrives_at_the_end_asks_nothing(self):
        """SO1 refuses a LOGS within a second, so a page that grows the view
        under a scroll at its end asks nothing (ui.ScrollWindow's rule): the
        user's next reach of the new end asks once."""
        world, window = self.opened(True)
        with world, w4.quiet():
            window.SetData(rows(30), 0, 0)
            w4.fire(window, "scroll", 1.0)
            window.SetData(rows(30, 30), 1, 0)
        self.assertEqual(world.logs_sent(), [(0,), (1,)])
        model = w4.board(window).model
        self.assertEqual(model["rows"][0]["other"], "Buyer9",
                         "the first row shown stays (row 9 of 60)")
        self.assertLess(model["scroll"], 1.0)
        with world, w4.quiet():
            w4.fire(window, "scroll", model["scroll"])     # the range's echo of the program's move
            w4.fire(window, "scroll", 1.0)
        self.assertEqual(world.logs_sent(), [(0,), (1,), (2,)])

    def test_the_wheel_moves_the_view_and_reaches_the_end_once(self):
        world, window = self.opened(True)
        with world, w4.quiet():
            window.SetData(rows(30), 0, 0)
            w4.fire(window, "wheel", 1.0)
        model = w4.board(window).model
        self.assertGreater(model["scroll"], 0.0)
        self.assertEqual(model["rows"][0]["date"], window.GetRowTexts()[1][4], "a tenth of 9 rows: one row")
        with world, w4.quiet():
            for _ in range(12):
                w4.fire(window, "wheel", 1.0)
        self.assertEqual(world.logs_sent(), [(0,), (1,)])
        self.assertEqual(w4.board(window).model["scroll"], 1.0)
        with world, w4.quiet():
            for _ in range(12):
                w4.fire(window, "wheel", -1.0)
        self.assertEqual(w4.board(window).model["scroll"], 0.0)

    def test_a_short_view_has_no_range_and_asks_nothing(self):
        world, window = self.opened(True)
        with world, w4.quiet():
            window.SetData(rows(10), 0, 0)
            w4.fire(window, "wheel", 1.0)
            w4.fire(window, "scroll", 1.0)
        self.assertEqual(world.logs_sent(), [(0,)])
        self.assertFalse(w4.board(window).model["scrollable"])

    def test_a_new_open_starts_at_the_top(self):
        world, window = self.opened(True)
        with world, w4.quiet():
            window.SetData(rows(30), 0, 0)
            w4.fire(window, "scroll", 1.0)
            window.Close()
            window.Open()
        model = w4.board(window).model
        self.assertEqual((model["rows"], model["scroll"], model["loading"]), ([], 0.0, True))
        self.assertEqual(world.logs_sent()[-1], (0,))


class Retry(LogTest):
    def test_a_page_refused_as_too_soon_is_asked_again_by_the_timer(self):
        def flow(world, window):
            window.SetData(rows(30), 0, 0)
            self.scroll_to_end(world, window)
            self.assertTrue(window.OnLogsResult(self.rate_limited()), "the retry is quiet")
            world.game.time += 1.1
            world.game.state.now += 1.1
            if world.nui_on:
                self.assertGreater(w4.board(window).model["retry_end"], 0.0)
                w4.fire(window, "retry")
            else:
                window.OnUpdate()
        (sent, _, _), (_, _, window) = self.run_both(flow)
        self.assertEqual(sent, [("net.SendOfflineShopLogsPacket", (1,)), ("net.SendOfflineShopLogsPacket", (1,))])
        self.assertEqual(w4.board(window).model["retry_end"], 0.0)

    def test_a_hide_stops_the_timer_and_a_show_runs_it_again(self):
        world, window = self.opened(True)
        with world, w4.quiet():
            window.OnLogsResult(self.rate_limited())
            window.Hide()
            self.assertEqual(w4.board(window).model["retry_end"] if w4.board(window) else 0.0, 0.0)
            window.Show()
            self.assertGreater(w4.board(window).model["retry_end"], 0.0)
            world.game.time += 1.1
            world.game.state.now += 1.1
            w4.fire(window, "retry")
        self.assertEqual(world.logs_sent(), [(0,), (0,)])

    def test_close_stops_the_timer(self):
        world, window = self.opened(True)
        with world, w4.quiet():
            window.OnLogsResult(self.rate_limited())
            self.assertGreater(w4.board(window).model["retry_end"], 0.0)
            window.Close()
            window.nui_retry()
        self.assertEqual(world.logs_sent(), [(0,)])


class Lifecycle(LogTest):
    def test_hide_and_show_before_the_init_do_not_raise(self):
        """Live lesson (2026-11-05): ui.Window.__init__ calls Hide before the
        legacy __init__ has set its attributes. The facade's __init__ runs
        nui_begin first, then legacy's, so Hide and Show run on an object
        with the facade's state and none of legacy's."""
        world = LogWorld(True)
        window = world.log_window()
        cls = type(window)
        bare = cls.__new__(cls)
        with world, w4.quiet():
            bare.nui_begin()
            for method in ("Hide", "Show"):
                self.assertIn(method, [name for klass in cls.__mro__[:2] for name in vars(klass)])
                getattr(bare, method)()

    def test_the_facade_runs_no_python_per_frame(self):
        world = LogWorld(True)
        self.assertIsNone(type(world.log_window()).OnUpdate)

    def test_every_fixture_has_every_model_key(self):
        world, window = self.opened(True)
        model = set(w4.board(window).model)
        for variant in ("", "loading", "empty"):
            with self.subTest(variant=variant):
                self.assertEqual(set(w4.fixture_keys(window, KEY, variant)), model)

    def test_destroy_takes_the_board(self):
        world, window = self.opened(True)
        with world, w4.quiet():
            window.Destroy()
        self.assertIsNone(w4.board(window))


if __name__ == "__main__":
    unittest.main()
