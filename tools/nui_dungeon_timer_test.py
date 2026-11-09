"""Tests of the NovaUI dungeon manager, its drops panel, its ready notice and the dungeon ranking
(assets/root/nui_dungeon_timer.py, nui_dungeon_drops.py, nui_dungeon_notice.py,
nui_dungeon_rank.py; NOVA-25).

Each flow runs on the legacy windows (uitimerwindow.py, uidungeonrank.py) and on the NovaUI
facades over the same stand-in world (dungeon_timer_support.World), and what each sends must be
the same: the chat commands ("/warp_dungeon", "/rank_dungeon"), the drop requests, the tooltip
calls, the windows shown. The NovaUI side also checks what the boards show (the rows and their
clocks, the chosen dungeon, the description's tones, the empty hint, the drops, the rankings),
that no Python runs per frame (OnUpdate None; the clocks are nui-countdowns, the notices
nui_dungeon_notice's timers, the ranking's walk-away a leave-range watch), and the wiring."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dungeon_timer_support as dts  # noqa: E402
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402

WINDOWS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "nui", "nui", "windows")
NEW_DUNGEONS = [0, 1, 2, 3, 5, 6]


def opened(nui_on):
    world = dts.World(nui_on)
    rank = world.rank()
    window = world.timer()
    with world.game, w4.quiet():
        window.Open()
    return world, window, rank


def press(world, window, event, *args):
    with world.game, w4.quiet():
        return w4.press(window, event, *args)


class Both(unittest.TestCase):
    """A flow on each side; the effects compared."""

    def run_both(self, nui_flow, legacy_flow):
        effects = []
        sides = []
        for nui_on in (False, True):
            world, window, rank = opened(nui_on)
            mark = world.mark()
            with world.game, w4.quiet():
                (nui_flow if nui_on else legacy_flow)(world, window, rank)
            effects.append((world.chat_commands(), world.drop_requests(), bool(window.IsShow()), bool(rank.IsShow()),
                            [(n, a) for n, a in world.game.log[mark:] if n.startswith("net.")]))
            sides.append((world, window, rank))
        self.assertEqual(effects[1], effects[0])
        return sides


class Flows(Both):
    def test_the_ranking_buttons_and_the_teleport(self):
        def legacy(world, window, rank):
            window.SetDescription(6)
            window.btnTimeRank.event()
            window.btnOverAllRank.event()
            window.btnDamageRank.event()
            window.teleport.event()

        def nui(world, window, rank):
            w4.press(window, "row_press", 6, 0)
            for name in ("time", "overall", "damage", "teleport"):
                if w4.board(window) is not None:
                    w4.press(window, "button_press", name, 0)
        (_, legacy_window, _), (world, window, rank) = self.run_both(nui, legacy)
        self.assertEqual(world.chat_commands(), ["/rank_dungeon 0 6", "/rank_dungeon 1 6", "/rank_dungeon 2 6",
                                                 "/warp_dungeon 6"])
        self.assertIsNone(w4.board(window), "the teleport closes the board")
        self.assertTrue(rank.IsShow())

    def test_the_drops_button_asks_once(self):
        def legacy(world, window, rank):
            window.SetDescription(2)
            window.btnDungeonDrops.event()
            world.timer_module.add_drop(2, 2598, 1, 27001, 1, 500000)
            window.btnDungeonDrops.event()

        def nui(world, window, rank):
            w4.press(window, "row_press", 2, 0)
            w4.press(window, "button_press", "drops", 0)
            world.timer_module.add_drop(2, 2598, 1, 27001, 1, 500000)
            w4.press(window, "button_press", "drops", 0)
        (_, legacy_window, _), (world, window, _) = self.run_both(nui, legacy)
        self.assertEqual(world.drop_requests(), [(2,)])
        self.assertTrue(window.wndDrops.IsShow())
        self.assertTrue(legacy_window.wndDrops.IsShow())

    def test_hiding_and_showing_dungeons(self):
        def legacy(world, window, rank):
            window.HideDungeon(1)
            window.HideDungeon(5)
            window.showHiddenBtn.event()

        def nui(world, window, rank):
            w4.press(window, "hide_press", 1, 0)
            w4.press(window, "hide_press", 5, 0)
            self.assertEqual([r["idx"] for r in w4.board(window).model["rows"]], [0, 2, 3, 6])
            self.assertTrue(w4.board(window).model["show_hidden"])
            w4.press(window, "button_press", "show_hidden", 0)
        (_, legacy_window, _), (world, window, _) = self.run_both(nui, legacy)
        self.assertEqual(window.visible_indices, legacy_window.visible_indices)
        model = w4.board(window).model
        self.assertEqual([r["idx"] for r in model["rows"]], NEW_DUNGEONS)
        self.assertFalse(model["show_hidden"])

    def test_the_ticket_shows_the_item_tooltip_as_legacy(self):
        calls = []
        for nui_on in (False, True):
            world = dts.World(nui_on)
            world.timer_module.DESCRIPTION.clear()
            window = world.timer()
            world.timer_module.DESCRIPTION[1][5] = 30750
            with world.game, w4.quiet():
                window.Open()
                if nui_on:
                    window.SetDescription(1)
                    w4.fire(window, "ticket_over")
                    w4.fire(window, "ticket_out")
                else:
                    window.itemSlot.AppendSlot(0)
                    window.SetDescription(1)
                    window.itemSlot.events["over_in"](0)
                    window.itemSlot.events["over_out"]()
            calls.append(list(world.tooltip.calls))
            if nui_on:
                self.assertEqual(w4.board(window).model["ticket"]["icon"], "/icon/item/30750.tga")
        self.assertEqual(calls[1], calls[0])
        self.assertTrue(calls[0])


class Board(unittest.TestCase):
    def test_open_shows_the_six_dungeons_and_the_first(self):
        world, window, _ = opened(True)
        model = w4.board(window).model
        self.assertEqual([r["idx"] for r in model["rows"]], NEW_DUNGEONS)
        self.assertEqual(model["rows"][3]["title"], "Aqua Dragon")
        self.assertEqual((model["selected"], model["name"], model["boss"]), (0, "Demon Tower", "mob 1095"))
        self.assertEqual((model["level"], model["group"], model["cooldown"]),
                         ("Min. Level 75 Max. Level 105", "Group Request:  No", "Cooldown:  0 Mins"))
        self.assertEqual(model["ticket_label"], "Entry Ticket")
        self.assertEqual(model["desc"][0], {"text": "Ground floor:", "tone": "heading"})
        self.assertEqual(model["empty"], "")

    def test_the_clocks_count_from_quest_time_ready(self):
        world, window, _ = opened(True)
        with world.game:
            window.SetTimeLeft(5, 600)
            self.assertEqual(w4.board(window).model["rows"][4]["end"], 0.0, "nothing counts before QuestTimeReady")
            window.QuestTimeReady()
        self.assertEqual(w4.board(window).model["rows"][4]["end"], 600.0)
        world.game.timestamp += 600
        press(world, window, "row_ready", 5)
        self.assertEqual(w4.board(window).model["rows"][4]["end"], 0.0)

    def test_a_note_keeps_its_tone(self):
        world, window, _ = opened(True)
        press(world, window, "row_press", 1, 0)
        tones = [line["tone"] for line in w4.board(window).model["desc"]]
        self.assertIn("note", tones)
        self.assertIn("heading", tones)

    def test_every_hidden_shows_the_hint(self):
        world, window, _ = opened(True)
        for idx in NEW_DUNGEONS:
            press(world, window, "hide_press", idx, 0)
        model = w4.board(window).model
        self.assertEqual(model["rows"], [])
        self.assertEqual(model["empty"], "All dungeons are hidden for your level. Press Show Hidden to see them.")

    def test_no_python_per_frame(self):
        world, window, rank = opened(True)
        for cls in (type(window), type(rank), type(window.wndDrops)):
            self.assertIsNone(cls.OnUpdate, cls.__name__)
        with world.game:
            window.UpdateTime()  # game.OnUpdate's call does nothing here


class Notices(unittest.TestCase):
    def test_a_checked_dungeon_announces_once_and_the_box_goes(self):
        world, window, _ = opened(True)
        notices = window.nui_notices
        with world.game, w4.quiet():
            window.QuestTimeReady()
            w4.press(window, "row_press", 2, 0)
            w4.press(window, "notice_press", 0)
            self.assertTrue(w4.board(window).model["notice"])
            window.SetTimeLeft(2, 30)
            window.SetTimeLeft(3, 30)
        self.assertEqual([t["idx"] for t in notices.timers], [2], "only the checked dungeon's clock")
        self.assertIsNotNone(notices.board)
        with world.game:
            notices.board.fire("timer_end", 2)
        self.assertEqual([t["title"] for t in notices.toasts], ["Devil`s Catacomb"])
        self.assertTrue(window.announced[2])
        with world.game:
            notices.board.fire("toast_end", notices.toasts[0]["key"])
        self.assertIsNone(notices.board, "the document goes with the last box")

    def test_unchecking_stops_the_watch(self):
        world, window, _ = opened(True)
        with world.game, w4.quiet():
            window.QuestTimeReady()
            w4.press(window, "row_press", 6, 0)
            w4.press(window, "notice_press", 0)
            window.SetTimeLeft(6, 30)
            w4.press(window, "notice_press", 0)
        self.assertEqual(window.nui_notices.timers, [])
        self.assertIsNone(window.nui_notices.board)


class Drops(unittest.TestCase):
    def test_mobs_items_and_back(self):
        world, window, _ = opened(True)
        module = world.timer_module
        with world.game, w4.quiet():
            w4.press(window, "row_press", 2, 0)
            w4.press(window, "button_press", "drops", 0)
            module.add_drop(2, 2598, 1, 27001, 1, 1000000)
            module.add_drop(2, 2598, 1, 27992, 3, 300000)
            module.add_drop(2, 2595, 2, 27001, 5, 1000)
            window.refreshMobList()
        drops = window.wndDrops
        model = w4.board(drops).model
        self.assertEqual(model["mobs"], [{"name": "mob 2598", "type": "boss"}, {"name": "mob 2595", "type": "stone"}])
        self.assertEqual(model["info"], "The following mobs are located in Devil`s Catacomb")
        press(world, drops, "mob_press", 0, 0)
        model = w4.board(drops).model
        self.assertEqual(model["showing"], "items")
        self.assertEqual([(i["text"], i["band"]) for i in model["items"]],
                         [("1x item 27001", "guaranteed"), ("3x item 27992", "common")])
        self.assertEqual(model["header"], {"name": "mob 2598", "type": "boss"})
        press(world, drops, "back_press", 0)
        self.assertEqual(w4.board(drops).model["showing"], "mobs")
        press(world, drops, "close_press", 0)
        self.assertFalse(drops.IsShow())


class Rank(unittest.TestCase):
    def test_rows_own_title_and_loading(self):
        for nui_on in (False, True):
            world = dts.World(nui_on)
            rank = world.rank()
            world.game.dungeon_rank[:] = [[1, "Alice", 3725], [2, "Bob", 4000]]
            with world.game:
                world.interface.OpenDungeonRank()
                if nui_on:
                    self.assertTrue(w4.board(rank).model["loading"])
                rank.SetPersonalDungeonRank("2", "Bob", "4000", "0")
                rank.RefreshDungeonRank(0, 5)
            texts = [(i.rank.text if not nui_on else i.rank, i.name.text if not nui_on else i.name,
                      i.count.text if not nui_on else i.count) for i in rank.rankImages]
            if not nui_on:
                legacy = texts
            else:
                self.assertEqual(texts, legacy)
                model = w4.board(rank).model
                self.assertFalse(model["loading"])
                self.assertEqual(model["title"], "Nemeres Time Ranking")
                self.assertEqual(model["rows"][0], {"rank": "1", "name": "Alice", "count": "1:02:05"})
                self.assertEqual(model["own"], {"rank": "2", "name": "Bob", "count": "1:06:40"})

    def test_walking_away_closes_it_once(self):
        world = dts.World(True)
        rank = world.rank()
        with world.game:
            rank.Open(1, 0)
            self.assertIsNotNone(world.game.w4["leave_range"].get("dungeon-rank"))
            self.assertEqual(world.game.w4["leave_range"]["dungeon-rank"]["range"], 1500)
            self.assertTrue(support.leave_range(world.game, "dungeon-rank"))
        self.assertFalse(rank.IsShow())
        self.assertIsNone(world.game.modules["nuigame"].LeaveRangeState("dungeon-rank"))

    def test_close_x(self):
        world = dts.World(True)
        rank = world.rank()
        with world.game:
            rank.Open(2, 0)
        press(world, rank, "close_press", 0)
        self.assertFalse(rank.IsShow())


class Factory(unittest.TestCase):
    def test_flags_off_make_the_legacy_windows(self):
        world = dts.World(False)
        self.assertEqual(type(world.timer()).__module__, "uiTimerWindow")
        self.assertEqual(type(world.rank()).__module__, "uiDungeonRank")
        self.assertEqual(type(world.interface.wndTimer.wndDrops).__module__, "uiTimerWindow")

    def test_flags_on_make_the_facades(self):
        world = dts.World(True)
        self.assertEqual(type(world.timer()).__module__, "nui_dungeon_timer")
        self.assertEqual(type(world.rank()).__module__, "nui_dungeon_rank")
        self.assertEqual(type(world.interface.wndTimer.wndDrops).__module__, "nui_dungeon_drops")

    def test_every_fixture_has_every_model_key(self):
        world, window, rank = opened(True)
        cases = (("dungeon-timer", window.nui_model()), ("dungeon-rank", rank.nui_model()),
                 ("dungeon-drops", window.wndDrops.nui_model()),
                 ("dungeon-notice", window.nui_notices.model()))
        for name, model in cases:
            for file_name in sorted(os.listdir(os.path.join(WINDOWS, name))):
                if not file_name.endswith(".fixture.json"):
                    continue
                with open(os.path.join(WINDOWS, name, file_name), encoding="utf-8") as handle:
                    (fixture,) = json.load(handle).values()
                with self.subTest(fixture=file_name):
                    self.assertEqual(sorted(fixture), sorted(model))

    def test_the_registration(self):
        world = dts.World(True)
        windows = world.m("nui_windows")
        ids = [window_id for window_id, _ in windows.WINDOWS]
        self.assertEqual(ids[-1], "maintenance")
        for window_id in ("dungeon-timer", "dungeon-drops", "dungeon-rank"):
            self.assertIs(dict(windows.WINDOWS)[window_id], True)
            self.assertIn(window_id, windows.GROUPS["dungeon"])
        self.assertEqual(windows.GROUPS["dungeon"], ("dungeon-timer", "dungeon-drops", "dungeon-rank"))
        self.assertIn(("dungeon-timer", ("dungeon-timer", "dungeon-notice")), windows.ON_DEMAND_DOCUMENTS)
        self.assertIn(("dungeon-drops", ("dungeon-drops",)), windows.ON_DEMAND_DOCUMENTS)
        self.assertIn(("dungeon-rank", ("dungeon-rank",)), windows.ON_DEMAND_DOCUMENTS)
        self.assertIn("dungeon-rank", world.m("nui_facade").LEAVE_RANGE_KEYS)


if __name__ == "__main__":
    unittest.main()
