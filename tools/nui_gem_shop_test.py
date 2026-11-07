"""Tests of the NovaUI gaya market (assets/root/nui_gem_shop.py; Wave 5, NOVA-10).

Each flow runs on legacy's uigemshop.GemShopWindow and on the NovaUI
facade in the Wave 4 test world, and the effects (the packets, the dialogs,
the chat lines) must be the same: the facade only swaps the widgets for
proxies. The NovaUI side also checks what the board shows, the walk-away
watch and the minute timer that rewrites legacy's "HH:MM"."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402

VNUMS = (27001, 72723, 28030, 27002, 25040, 71027, 28035, 70043, 13000)
PRICES = (20, 150, 90, 35, 300, 60, 500, 250, 180)
COUNTS = (50, 1, 1, 30, 1, 1, 1, 1, 1)
UNLOCK_VNUM, REFRESH_VNUM = 72350, 72351


def market(gem=1000, unlock_items=2, refresh_items=1, refresh_seconds=342 * 60):
    def setup(game):
        game.modules["player"].__dict__["GAYA_MARKET_SLOT_COUNT"] = 9
        answer = game.answer
        answer("player", "GetGemShopItemCount", lambda i: COUNTS[i])
        answer("player", "GetGemShopItemVnum", lambda i: VNUMS[i])
        answer("player", "GetGemShopItemPrice", lambda i: PRICES[i])
        answer("player", "GetGemShopItemStatus", lambda i: 1 if i >= 6 else 0)
        answer("player", "GetGemShopRefreshTime", lambda: refresh_seconds)
        answer("player", "GetGemShopUnlockItemVnum", lambda: UNLOCK_VNUM)
        answer("player", "GetGemShopUnlockCost", lambda i: 2)
        answer("player", "GetGemShopRefreshItemVnum", lambda: REFRESH_VNUM)
        answer("player", "GetGem", lambda: gem)
        answer("player", "GetItemCountByVnum",
               lambda vnum: unlock_items if vnum == UNLOCK_VNUM else (refresh_items if vnum == REFRESH_VNUM else 0))
    return setup


class GemShopTest(unittest.TestCase):
    def world(self, nui_on, setup=None):
        world = w4.World(nui_on, setup=setup or market())
        with world.game, w4.quiet():
            world.game.load("uiGemShop", "uigemshop.py")
            if nui_on:
                world.game.load("nui_gem_shop", "nui_gem_shop.py")
        window = world.make("gem-shop", "uiGemShop", "GemShopWindow", "nui_gem_shop.GemShopWindow")
        with world.game, w4.quiet():
            window.SetItemToolTip(world.tooltip)
            window.Open()
        return world, window

    def run_both(self, flow, setup=None):
        results = []
        for nui_on in (False, True):
            world, window = self.world(nui_on, setup)
            mark = world.mark()
            with world.game, w4.quiet():
                flow(world, window)
            results.append((world.effects_since(mark), world, window))
        (legacy, _, _), (novaui, _, _) = results
        self.assertEqual(novaui, legacy)
        return results

    @staticmethod
    def select(world, window, cell):
        if world.nui_on:
            w4.press(window, "cell_press", cell, 0)
        else:
            window.itemSlot.fire("select_item", cell)

    @staticmethod
    def close(world, window):
        if world.nui_on:
            w4.press(window, "close_press", 0)
        else:
            window.titleBar.close()


class Board(GemShopTest):
    def test_the_board_shows_the_market_prices_locks_and_time(self):
        world, window = self.world(True)
        model = w4.board(window).model
        self.assertEqual(model["prices"], [str(p) for p in PRICES])
        self.assertEqual(model["refresh_time"], "05:42")
        self.assertEqual([c["disabled"] for c in model["cells"]], [False] * 6 + [True] * 3, "the last three locked")
        self.assertEqual(model["cells"][0]["count"], "50", "a stack shows its count, one item none (legacy)")
        self.assertEqual(model["cells"][1]["count"], "")

    def test_the_fixture_has_every_model_key(self):
        world, window = self.world(True)
        self.assertEqual(set(w4.fixture_keys(window, "gem-shop")), set(w4.board(window).model))


class Flows(GemShopTest):
    def test_a_buy_asks_then_sends_once(self):
        def flow(world, window):
            self.select(world, window, 1)
            window.questionDialog.accept()
        (effects, _, _), _ = self.run_both(flow)
        self.assertIn(("net.SendGemShopBuy", (1,)), effects)

    def test_a_buy_without_enough_gaya_prints_legacy_s_line(self):
        (effects, _, _), _ = self.run_both(lambda world, window: self.select(world, window, 4), setup=market(gem=10))
        self.assertFalse([e for e in effects if e[0].startswith("net.")], "nothing sent")

    def test_a_locked_slot_asks_to_unlock_with_the_server_s_item(self):
        def flow(world, window):
            self.select(world, window, 6)
            window.questionDialog.accept()
        (effects, _, _), _ = self.run_both(flow)
        self.assertIn(("net.SendGemShopAdd", (6,)), effects)

    def test_a_locked_slot_without_the_items_asks_nothing(self):
        (effects, _, _), _ = self.run_both(lambda world, window: self.select(world, window, 7),
                                           setup=market(unlock_items=1))
        self.assertFalse([e for e in effects if e[0].startswith("net.")])

    def test_the_refresh_asks_then_sends_and_needs_its_item(self):
        def flow(world, window):
            if world.nui_on:
                w4.press(window, "refresh_press", 0)
            else:
                window.refreshButton.click()
            window.questionDialog.accept()
        (effects, _, _), _ = self.run_both(flow)
        self.assertIn(("net.SendGemShopRefresh", ()), effects)

        def press_only(world, window):
            if world.nui_on:
                w4.press(window, "refresh_press", 0)
            else:
                window.refreshButton.click()
        (effects, _, _), _ = self.run_both(press_only, setup=market(refresh_items=0))
        self.assertFalse([e for e in effects if e[0].startswith("net.")], "no refresh item: a chat line only")

    def test_the_player_s_close_tells_the_server_and_the_server_s_close_does_not(self):
        (effects, _, b), _ = self.run_both(self.close)
        self.assertEqual([e for e in effects if e[0].startswith("net.")], [("net.SendGemShopClose", ())])
        (effects, _, _), _ = self.run_both(lambda world, window: window.Close())
        self.assertFalse([e for e in effects if e[0].startswith("net.")], "the server's close sends nothing")


class NoPerFramePython(GemShopTest):
    def test_open_arms_the_walk_away_watch_and_hide_stops_it(self):
        world, window = self.world(True)
        nuigame = world.game.modules["nuigame"]
        self.assertIsNotNone(nuigame.LeaveRangeState("gem-shop"))
        mark = world.mark()
        with world.game, w4.quiet():
            window.Close()
        self.assertIsNone(nuigame.LeaveRangeState("gem-shop"))
        self.assertFalse([e for e in world.effects_since(mark) if e[0].startswith("net.")])

    def test_the_minute_timer_rewrites_the_time(self):
        world, window = self.world(True, setup=market(refresh_seconds=342 * 60 + 30))
        board = w4.board(window)
        self.assertEqual(board.model["refresh_time"], "05:42")
        self.assertGreater(board.model["minute_end"], 0.0)
        world.game.global_time += 31 * 1000  # app.GetGlobalTime(), legacy's clock
        world.game.state.now += 31
        with world.game, w4.quiet():
            board.fire("minute")
        self.assertEqual(board.model["refresh_time"], "05:41")

    def test_the_facade_runs_no_python_per_frame(self):
        world, window = self.world(True)
        self.assertIsNone(type(window).OnUpdate)


if __name__ == "__main__":
    unittest.main()
