"""Tests of the NovaUI shop signs under Wave 5's rules (assets/root/nui_shop_signs.py;
NOVA-9, o-cli bugs 11, 12 and 23).

The world is offline_shop_test's protocol-6 world (nui_shop_test's
OfflineNuiWorld), where uiprivateshopbuilder has offlineshopconst, so the
signs follow Wave 5's rule: the own, the target's and the hovered one's
always, with the sales texts on also the nearest SIGN_DISPLAY_COUNT within
SIGN_RANGE. Legacy works it out in each sign's OnUpdate; NovaUI at its timer's
end (refresh). The signs that show after each step must be the same.
nui_world_test keeps the rule of a host without offlineshopconst."""

import gc
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_shop_test  # noqa: E402
import nui_w4_world as w4  # noqa: E402

OWN_SHOP, TARGET, HOVERED = 7005, 7003, 7004


class SignWorld(nui_shop_test.OfflineNuiWorld):
    """OfflineNuiWorld with the NovaUI signs loaded when NovaUI is on."""

    def __init__(self, nui_on):
        nui_shop_test.OfflineNuiWorld.__init__(self, nui_on)
        self.builder = self.w4.m("uiPrivateShopBuilder")
        # The live client imports offlineshopconst with the builder module; this
        # world loads it after the Wave 4 modules, so the builder gets it here.
        self.builder.offlineshopconst = self.loaded["offlineshopconst"]
        self.builder.g_privateShopAdvertisementBoardDict.clear()
        self.signs = None
        if nui_on:
            with self.game, w4.quiet():
                self.signs = self.game.load("nui_shop_signs", "nui_shop_signs.py")
                self.signs.close_all()

    def close(self):
        """Interface.Close's close_all: no sign is left for a finalizer to
        refresh after the world (and its game modules) are gone."""
        if self.signs is not None:
            with self.game, w4.quiet():
                self.signs.close_all()

    def appear(self, vid, text, style=0):
        """Interface.AppearPrivateShop's choice of board."""
        builder = self.builder
        board = builder.g_privateShopAdvertisementBoardDict.get(vid)
        if board is not None:
            board.UpdateTitle(text)
            return board
        if self.nui_on:
            board = self.signs.ShopSign(style)
        elif style > 0:
            board = builder.PrivateShopTitleBar(style)
        else:
            board = builder.PrivateShopAdvertisementBoard()
        board.Open(vid, text)
        return board

    def disappear(self, vid):
        self.builder.DeleteADBoard(vid)
        gc.collect()

    def option(self, on):
        self.game.show_sales_text = on
        self.game.state.publish("system.show_sales_text", on)

    def visible(self):
        """{vid: title} of the signs that show now: legacy's after every
        sign's frame (OnUpdate), NovaUI's after its timer's end."""
        boards = self.builder.g_privateShopAdvertisementBoardDict
        if not self.nui_on:
            self.builder.RefreshShopBoards(force=True)
            for board in list(boards.values()):
                board.OnUpdate()
            return {vid: board.title for vid, board in boards.items() if board.IsShow()}
        board = self.signs._board
        if board is None or not board._doc:
            return {}
        self.signs.refresh()
        show_all = board.model["show_all"]
        return {s["vid"]: s["text"] for s in board.model["signs"]
                if s["shown"] and (s["always"] or (show_all and s["near"]))}


class Rule(unittest.TestCase):
    def worlds(self):
        worlds = SignWorld(False), SignWorld(True)
        self.addCleanup(worlds[1].close)
        return worlds

    def flow(self, steps):
        seen = []
        worlds = self.worlds()
        for world in worlds:
            states = []
            for step in steps:
                with world, w4.quiet():
                    step(world)
                    states.append(world.visible())
            seen.append(states)
        self.assertEqual(seen[1], seen[0], "the signs that show after each step")
        return worlds, seen[0]

    def test_only_the_nearest_twenty_within_range_show(self):
        def market(world):
            for vid in range(7101, 7131):
                world.distances[vid] = (vid - 7100) * 50
                world.appear(vid, "shop %d" % vid)
            world.distances[7130] = 5000
            world.distances[7102] = -1.0
        _, seen = self.flow([market])
        self.assertEqual(sorted(seen[0]), [7101] + list(range(7103, 7122)))

    def test_the_own_target_and_hovered_signs_show_whatever_the_rule(self):
        def setup(world):
            world.game.answer("player", "GetOwnOfflineShopVID", OWN_SHOP)
            world.game.answer("player", "GetTargetVID", TARGET)
            world.game.answer("chr", "Pick", HOVERED)
            for vid in (TARGET, HOVERED, OWN_SHOP, 7006):
                world.distances[vid] = 9000
                world.appear(vid, "shop %d" % vid)
        _, seen = self.flow([setup, lambda world: world.option(False), lambda world: world.option(True)])
        self.assertEqual(sorted(seen[0]), [TARGET, HOVERED, OWN_SHOP], "far, but always shown")
        self.assertEqual(sorted(seen[1]), [TARGET, HOVERED, OWN_SHOP], "the sales texts off")

    def test_a_decorated_sign_follows_the_same_rule_and_keeps_its_title(self):
        def setup(world):
            world.distances.update({7201: 100, 7202: 9000})
            world.appear(7201, "Bob's shop", 3)
            world.appear(7202, "far away", 2)
        def rename(world):
            world.appear(7201, "Bob's bargains", 3)
        _, seen = self.flow([setup, rename, lambda world: world.disappear(7201)])
        self.assertEqual(seen[0], {7201: "Bob's shop"})
        self.assertEqual(seen[1], {7201: "Bob's bargains"})
        self.assertEqual(seen[2], {})


class NovaUI(unittest.TestCase):
    def world(self):
        world = SignWorld(True)
        self.addCleanup(world.close)
        return world

    def test_a_decorated_sign_draws_its_style_and_an_unknown_one_draws_zero(self):
        world = self.world()
        with world, w4.quiet():
            world.distances.update({7201: 100, 7202: 100, 7203: 100})
            world.appear(7201, "Bob's shop", 3)
            world.appear(7202, "odd", 9)
            world.appear(7203, "plain")
        signs = {s["vid"]: s for s in world.signs._board.model["signs"]}
        self.assertEqual((signs[7201]["style"], signs[7202]["style"], signs[7203]["style"]), (3, 0, 0))
        self.assertEqual(signs[7201]["legacy_width"], "%ddp" % (len("Bob's shop") * 6 + 40), "PrivateShopTitleBar's width")
        self.assertEqual(signs[7203]["legacy_width"], "%ddp" % (len("plain") * 6 + 20))

    def test_the_shop_window_reads_the_title_and_marks_the_plain_sign_seen(self):
        world = self.world()
        with world, w4.quiet():
            const = world.m("offlineshopconst")
            const.forget_seen()
            sign = world.appear(7301, "Fresh fish")
            self.assertEqual(sign.title, "Fresh fish")
            sign.MarkSeen()
        entry = world.signs._board.model["signs"][0]
        self.assertTrue(entry["seen"])
        self.assertTrue(const.is_seen(7301, world.game.time))
        world.game.time += 30 * 60 + 1
        with world, w4.quiet():
            world.signs.refresh()
        self.assertFalse(world.signs._board.model["signs"][0]["seen"], "its own color back after 30 minutes")
        const.forget_seen()

    def test_a_sign_opened_again_within_thirty_minutes_is_still_seen(self):
        world = self.world()
        with world, w4.quiet():
            const = world.m("offlineshopconst")
            const.forget_seen()
            const.mark_seen(7302, world.game.time - 60)
            world.appear(7302, "Back again")
        self.assertTrue(world.signs._board.model["signs"][0]["seen"])
        const.forget_seen()

    def test_a_decorated_sign_keeps_its_style_when_seen(self):
        world = self.world()
        with world, w4.quiet():
            world.m("offlineshopconst").forget_seen()
            sign = world.appear(7303, "Styled", 4)
            sign.MarkSeen()
        self.assertFalse(world.signs._board.model["signs"][0]["seen"], "legacy's title bar draws no seen color")
        self.assertTrue(sign.lastSeen)
        world.m("offlineshopconst").forget_seen()

    def test_the_timer_runs_the_rule_once_a_second(self):
        world = self.world()
        with world, w4.quiet():
            world.distances[7401] = 100
            world.appear(7401, "a")
        board = world.signs._board
        start = board.model["tick_end"]
        self.assertGreater(start, 0.0)
        world.game.state.now += 1.0
        world.distances[7401] = 9000
        world.game.answer("chr", "Pick", 0)
        with world, w4.quiet():
            board.fire("tick")
        self.assertGreater(board.model["tick_end"], start)
        self.assertFalse(board.model["signs"][0]["near"], "walked away: no longer among the nearest")

    def test_a_tick_that_changes_nothing_writes_only_the_timer(self):
        world = self.world()
        with world, w4.quiet():
            world.distances.update({7501: 100, 7502: 200})
            world.appear(7501, "a")
            world.appear(7502, "b", 2)
        board = world.signs._board
        keys, original = [], board.set
        board.set = lambda **values: (keys.extend(values), original(**values))[1]
        with world, w4.quiet():
            board.fire("tick")
        self.assertEqual(keys, ["tick_end"], "the runtime updates every view of a key it is given, equal or not")


if __name__ == "__main__":
    unittest.main()
