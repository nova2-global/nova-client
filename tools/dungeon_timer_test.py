"""Tests for the legacy client's dungeon manager, drops panel and dungeon ranking (NOVA-25;
OLD root/uiTimerWindow.py, uiDungeonRank.py, ENABLE_TIMER_WINDOW, ENABLE_DUNGEON_RANKING and
_DUNGEON_DROP_INFO_): python3 -B -m unittest dungeon_timer_test (from tools/).

The legacy Python runs over nui_game_support's stand-ins with C's names (dungeon_timer_support):
- locale/common/dungeon_info.txt lists NEW's six dungeons (Q2 a) with OLD's levels, bosses and
  cooldowns, and every one has an English description;
- the server's "SetQuestTime <index> <seconds>" and "QuestTimeReady" drive the rows' clocks,
  rounded up to minutes; a checked dungeon announces itself when its clock ends; hiding a
  dungeon keeps the other rows' clocks (an OLD bug) and "Show Hidden" brings it back;
- the buttons send OLD's "/warp_dungeon <index>" and "/rank_dungeon <type> <index>", and the
  drops button asks for a dungeon's drops once (net.RequestDungeonDrop);
- GC::DUNGEON_DROP rows (game.BINARY_UpdateDungeonDrop) fill the drops panel, mob by mob;
- the ranking: loading, the server's rows, the personal row (the "/"-packed chat command),
  the time ranking's H:MM:SS, the walk away;
- the game window's and the Interface's wiring, and every key in all 17 locales."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dungeon_timer_support as dts  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import sash_test  # noqa: E402
import wave6_support as w6  # noqa: E402

support = dts.support
ROOT = support.ROOT
NEW_DUNGEONS = [0, 1, 2, 3, 5, 6]

INTERFACE_KEYS = {
    "DUNGEON_RANK_TITLE1": "Time Ranking", "DUNGEON_RANK_TITLE2": "Overall Ranking", "DUNGEON_RANK_TITLE3": "Damage Ranking",
    "KILL_COUNT_NAME": "Name", "KILL_COUNT_COUNT": "Count", "DUNGEON_MANAGER_TITLE": "Dungeon Manager",
    "DUNGEON_MANAGER_CHOOSE_DUNGEON": "Choose a dungeon", "DUNGEON_MANAGER_LEVEL": "Level",
    "DUNGEON_MANAGER_GROUP_REQUESTED": "Group Requested", "DUNGEON_MANAGER_COOLDOWN": "Cooldown",
    "DUNGEON_MANAGER_REQUIRED_ITEM": "Required Item", "DUNGEON_MANAGER_UNKNOWN": "Unknown",
    "DUNGEON_MANAGER_TELEPORT": "Teleport", "DUNGEON_MANAGER_DROPS": "Dungeon Drops",
    "DUNGEON_MANAGER_TIME_RANK": "Time Ranking", "DUNGEON_MANAGER_OVERALL_RANK": "Overall Ranking",
    "DUNGEON_MANAGER_DAMAGE_RANK": "Damage Ranking", "DUNGEON_MANAGER_SHOW_HIDDEN": "Show Hidden",
    "DUNGEON_MANAGER_NOTICE": "Notify me when ready", "DUNGEON_RANK_LOADING": "Loading...",
}
GAME_KEYS = {
    "TIMERWINDOW_AVAILABLE": "Available", "TIMERWINDOW_READY_TO_FIGHT": "Ready To Fight!",
    "TIMERWINDOW_REQUIRED_LEVEL": "Min. Level %d \\nMax. Level %d", "TIMERWINDOW_GROUP_REQUEST": "Group Request",
    "TIMERWINDOW_ENTRY_TICKET": "Entry Ticket", "TIMERWINDOW_COOLDOWN": "Cooldown",
    "TIMERWINDOW_DROP_TITLE": "Dungeon Drops", "TIMERWINDOW_DROP_LIST": "The following mobs are located in %s",
    "TIMERWINDOW_MINUTE": "%d Min", "TIMERWINDOW_MINUTES": "%d Mins", "TIMERWINDOW_GROUP_NO": "No",
    "TIMERWINDOW_GROUP_YES": "Yes", "TIMERWINDOW_EMPTY": "No dungeons found.",
    "TIMERWINDOW_ALL_HIDDEN": "All dungeons are hidden for your level. Press Show Hidden to see them.",
    "TIMERWINDOW_LOAD_ERROR": "Load error: %s", "TIMERWINDOW_DROP_RARE": "Rare Drop",
    "TIMERWINDOW_DROP_COMMON": "Common Drop", "TIMERWINDOW_DROP_GUARANTEED": "Guaranteed Drop",
}


def legacy_world():
    return dts.World(False)


def opened_timer(world):
    window = world.timer()
    with world.game, w4.quiet():
        window.Open()
    return window


def row_texts(window):
    return dict((board.index, board.textLine3.text) for board in window.boards)


class Data(unittest.TestCase):
    def test_dungeon_info_lists_news_six_dungeons_with_olds_values(self):
        world = legacy_world()
        world.timer()
        module = world.timer_module
        self.assertEqual(sorted(module.DESCRIPTION), NEW_DUNGEONS)
        expected = {0: (1095, 75, 105, 0), 1: (2092, 75, 105, 300), 2: (2598, 75, 105, 600),
                    3: (2493, 75, 105, 300), 5: (6191, 90, 120, 600), 6: (6091, 90, 120, 600)}
        for idx, (boss, low, high, cooldown) in expected.items():
            row = module.DESCRIPTION[idx]
            self.assertEqual((row[0][0], row[1], row[2], row[4], row[5]), (boss, low, high, cooldown, 0), idx)
            self.assertTrue(row[6], "dungeon %d has a description" % idx)

    def test_the_parsers_take_olds_forms(self):
        module = legacy_world().timer_module
        self.assertEqual(module.parse_cooldown_to_seconds("5 Mins"), 300)
        self.assertEqual(module.parse_cooldown_to_seconds("2h"), 7200)
        self.assertEqual(module.parse_cooldown_to_seconds("45 secs"), 45)
        self.assertRaises(ValueError, module.parse_cooldown_to_seconds, "soon")
        self.assertEqual(module.parse_boss_field("8:41715:40037:514:48000:0"), [8, 41715, 40037, 514, 48000, 0])
        self.assertEqual(module.parse_boss_field("1095"), [1095, 0, 0, 0, 0, 0])
        rows, errors = module.parse_dungeon_info(["#c", "4\t961\t75\t105\tx\t10 Mins\t0", "bad", "961\t1\t2\tx\t0\t0"])
        self.assertEqual((sorted(rows), errors), ([1, 4], 1))
        self.assertEqual(module.desc_line("#Stage 1:"), ("Stage 1:", module.DESC_COLORS["#"], None))
        self.assertEqual(module.extract_font_tag("@Trajan Pro 3:15b Title"), ("Title", "Trajan Pro 3:15b"))
        self.assertEqual(module.extract_font_tag("@@x"), ("@x", None))

    def test_titles_come_from_the_title_list(self):
        module = legacy_world().timer_module
        self.assertEqual([module.get_title(i) for i in NEW_DUNGEONS],
                         ["Demon Tower", "Spider Baroness", "Devil`s Catacomb", "Aqua Dragon", "Nemeres", "Razador"])
        self.assertEqual(module.get_title(99), "Dungeon 99")

    def test_the_group_rule_and_the_level_band_read_as_words(self):
        world = legacy_world()
        module = world.timer_module
        with world.game:
            self.assertEqual(module.group_text("|E~/xmark.tga|e"), "No")
            self.assertEqual(module.group_text("|E~/checkmark.tga|e"), "Yes")
            self.assertEqual(module.level_band(75, 105), "Min. Level 75 Max. Level 105")

    def test_rarity_bands_include_their_edges(self):
        module = legacy_world().timer_module
        self.assertEqual([module.rarity_of(c) for c in (0, 299999, 300000, 700000, 700001, 1000000)], [1, 1, 2, 2, 3, 3])


class Timer(unittest.TestCase):
    def test_hide_works_before_init_has_run(self):
        """ui.Window.__init__ calls Hide before the subclass sets its attributes,
        which the stand-in ui does not: r34 crashed entering the game on this."""
        world = legacy_world()
        cls = world.timer_module.TimerWindow
        bare = cls.__new__(cls)
        bare._TimerWindow__HideBossModel()
        self.assertIsNone(bare.bossView)

    def test_open_lists_every_dungeon_ready_and_shows_the_first(self):
        world = legacy_world()
        window = opened_timer(world)
        self.assertEqual(window.visible_indices, NEW_DUNGEONS)
        self.assertEqual(window.index, 0)
        self.assertTrue(window.IsShow())
        self.assertEqual(set(row_texts(window).values()), {"Ready To Fight!"})
        self.assertEqual(window.text3.text, "Cooldown:  0 Mins")
        self.assertEqual(window.BossName.text, "mob 1095")
        self.assertEqual(window.textLine.text, "Demon Tower")
        self.assertFalse(window.showHiddenBtn.shown)

    def test_a_row_press_shows_its_dungeon(self):
        world = legacy_world()
        window = opened_timer(world)
        board = [b for b in window.boards if b.index == 5][0]
        with world.game:
            board.OnMouseLeftButtonDown()
        self.assertEqual(window.index, 5)
        self.assertEqual(window.text1.text, "Min. Level 90 Max. Level 120")
        self.assertEqual(window.text2.text, "Group Request:  No")
        self.assertEqual(window.text3.text, "Cooldown:  10 Mins")
        self.assertEqual(window.descLines[0].text, "Stage 1:")

    def test_quest_times_count_after_quest_time_ready(self):
        world = legacy_world()
        window = opened_timer(world)
        with world.game:
            window.SetTimeLeft(2, 61)
            window.UpdateTime()
            self.assertEqual(row_texts(window)[2], "Ready To Fight!", "nothing counts before QuestTimeReady")
            window.QuestTimeReady()
            self.assertEqual(row_texts(window)[2], "2 Mins")
            world.game.timestamp += 2
            window.UpdateTime()
            self.assertEqual(row_texts(window)[2], "1 Min")
            world.game.timestamp += 60
            window.UpdateTime()
            self.assertEqual(row_texts(window)[2], "Ready To Fight!")
            window.SetTimeLeft(42, 100)  # not a dungeon of the file: ignored
        self.assertNotIn(42, window.endTimes)

    def test_hiding_a_dungeon_keeps_the_other_clocks(self):
        """OLD rebuilt every row without its clock and cleared the loaded flag: after a hide no
        clock ran until the next login."""
        world = legacy_world()
        window = opened_timer(world)
        with world.game:
            world.timer_module.TIMER_STATE["loaded"] = True
            window.SetTimeLeft(5, 600)
            window.HideDungeon(1)
            window.UpdateTime()
        self.assertNotIn(1, window.visible_indices)
        self.assertEqual(row_texts(window)[5], "10 Mins")
        self.assertTrue(window.showHiddenBtn.shown)
        with world.game:
            window.SetTimeLeft(1, 300)
            window.UnhideAll()
            window.UpdateTime()
        self.assertEqual(window.visible_indices, NEW_DUNGEONS)
        self.assertEqual(row_texts(window)[1], "5 Mins", "a hidden row keeps the clock it was sent")
        self.assertFalse(window.showHiddenBtn.shown)

    def test_a_hidden_dungeon_comes_back_below_the_level_it_was_hidden_at(self):
        world = legacy_world()
        window = opened_timer(world)
        module = world.timer_module
        with world.game:
            window.HideDungeon(0)
            module.SESSION_HIDDEN[0] = 0
            self.assertTrue(module.is_hidden_for_current_view(0), "hidden from level 100 on")
            world.game.status[world.game.modules["player"].LEVEL] = 99
            self.assertFalse(module.is_hidden_for_current_view(0))

    def test_hiding_every_dungeon_shows_the_hint(self):
        world = legacy_world()
        window = opened_timer(world)
        with world.game:
            for idx in NEW_DUNGEONS:
                window.HideDungeon(idx)
        self.assertEqual(window.boards, [])
        self.assertTrue(window.emptyLabel.shown)
        self.assertEqual(window.emptyLabel.text, GAME_KEYS["TIMERWINDOW_ALL_HIDDEN"])

    def test_a_checked_dungeon_announces_itself_once(self):
        world = legacy_world()
        window = opened_timer(world)
        with world.game:
            world.timer_module.TIMER_STATE["loaded"] = True
            window.SetDescription(2)
            window.noticeBtn.OnMouseLeftButtonUp()
            window.SetTimeLeft(2, 30)
            window.SetTimeLeft(3, 30)
            window.UpdateTime()
            self.assertEqual(window.notices, {})
            world.game.timestamp += 30
            window.UpdateTime()
            window.UpdateTime()
        self.assertEqual(list(window.notices), [2], "only the checked dungeon")
        self.assertEqual(world.timer_module.OPEN_NOTICE_COUNT[0], 1)
        self.assertEqual(world.timer_module.ALLOW_NOTICE[2], 1)

    def test_the_buttons_send_olds_commands(self):
        world = legacy_world()
        rank = world.rank()
        window = opened_timer(world)
        with world.game, w4.quiet():
            window.SetDescription(6)
            window.onClickTimeRank()
            window.onClickOverAllRank()
            window.onClickDamageRank()
            window.Teleport()
        self.assertEqual(world.chat_commands(), ["/rank_dungeon 0 6", "/rank_dungeon 1 6", "/rank_dungeon 2 6",
                                                 "/warp_dungeon 6"])
        self.assertFalse(window.IsShow(), "the teleport closes the window")
        self.assertTrue(rank.IsShow())

    def test_the_entry_ticket_shows_its_item_and_tooltip(self):
        world = legacy_world()
        window = opened_timer(world)
        module = world.timer_module
        module.DESCRIPTION[1][5] = 30750
        window.itemSlot.AppendSlot(0)  # the uiscript's one cell
        with world.game:
            window.SetDescription(1)
        self.assertEqual(window.itemSlot.slots[0].get("vnum"), 30750)
        self.assertIsNotNone(window.itemSlot.events["over_in"])
        with world.game:
            window.SetDescription(0)
        self.assertFalse(window.itemSlot.slots[0].get("vnum"))
        self.assertIsNone(window.itemSlot.events["over_in"])


class Drops(unittest.TestCase):
    def test_the_drops_button_asks_once_and_rows_fill_the_panel(self):
        world = legacy_world()
        window = opened_timer(world)
        Game = sash_test.compiled("game.py", "GameWindow", ["BINARY_UpdateDungeonDrop"],
                                  {"uiTimerWindow": world.timer_module})
        game_window = Game()
        game_window.interface = type("I", (), {"RefreshDungeonDrops": lambda self: window.refreshMobList()})()
        with world.game, w4.quiet():
            window.SetDescription(2)
            window.openDungeonDrops()
            game_window.BINARY_UpdateDungeonDrop(2, 2598, 1, 50070, 1, 1000000)
            game_window.BINARY_UpdateDungeonDrop(2, 2598, 1, 27992, 3, 250000)
            game_window.BINARY_UpdateDungeonDrop(2, 2591, 0, 27001, 5, 400000)
            window.openDungeonDrops()
        self.assertEqual(world.drop_requests(), [(2,)], "asked once")
        drops = window.wndDrops
        self.assertTrue(drops.IsShow())
        self.assertEqual([row.vnum for row in drops.mobRows], [2598, 2591])
        self.assertEqual(drops.infoLabel.text, "The following mobs are located in Devil`s Catacomb")
        with world.game:
            drops.RefreshItemList(2598)
        self.assertEqual([(row.vnum, row.itemName.text, row.rarityLabel.text) for row in drops.itemRows],
                         [(50070, "1x item 50070", "Guaranteed Drop"), (27992, "3x item 27992", "Rare Drop")])
        self.assertTrue(drops.header.shown)
        with world.game:
            drops.RefreshMobList()
        self.assertFalse(drops.header.shown)


class Rank(unittest.TestCase):
    def test_loading_then_rows_then_personal_row(self):
        world = legacy_world()
        rank = world.rank()
        world.game.dungeon_rank[:] = [[1, "Alice", 3725], [2, "Bob", 4000]]
        with world.game:
            world.interface.OpenDungeonRank()
            self.assertTrue(rank.loadingText.shown)
            rank.SetPersonalDungeonRank("2", "Bob", "4000", "0")
            rank.RefreshDungeonRank(0, 5)
        self.assertFalse(rank.loadingText.shown)
        self.assertEqual(rank.title.text, "Nemeres Time Ranking")
        rows = [(image.rank.text, image.name.text, image.count.text) for image in rank.rankImages]
        self.assertEqual(rows[0], ("1", "Alice", "1:02:05"))
        self.assertEqual(rows[1], ("2", "Bob", "1:06:40"))
        self.assertEqual(rows[2], ("-", "-", "-"))
        self.assertEqual(rows[10], ("2", "Bob", "1:06:40"))
        self.assertEqual(world.game.dungeon_rank, [], "the rows are cleared once shown")

    def test_counts_are_dotted_and_an_unranked_player_shows_a_dash(self):
        world = legacy_world()
        rank = world.rank()
        world.game.dungeon_rank[:] = [[1, "Alice", 1234567]]
        with world.game:
            rank.SetPersonalDungeonRank("0", "Carol", "0", "2")
            rank.RefreshDungeonRank(2, 0)
        self.assertEqual(rank.rankImages[0].count.text, "1.234.567")
        self.assertEqual((rank.rankImages[10].rank.text, rank.rankImages[10].count.text), ("-", "0"))
        self.assertEqual(rank.title.text, "Demon Tower Damage Ranking")

    def test_walking_away_closes_it(self):
        world = legacy_world()
        rank = world.rank()
        with world.game:
            rank.Open(1, 0)
            world.game.position[0] += 1500
            rank.OnUpdate()
            self.assertTrue(rank.IsShow(), "1500 is still in range (OLD's >)")
            world.game.position[1] += 1501
            rank.OnUpdate()
        self.assertFalse(rank.IsShow())


class Wiring(unittest.TestCase):
    def source(self, name):
        with open(os.path.join(ROOT, name), encoding="utf-8") as handle:
            return handle.read()

    def test_game_registers_olds_server_commands_and_f6(self):
        text = self.source("game.py")
        for line in ('"SetQuestTime"			: self.SetQuestTime', '"QuestTimeReady"		: self.QuestTimeReady',
                     '"RefreshDungeonRank"	: self.RefreshDungeonRank',
                     '"SetPersonalDungeonRank"	: self.__SetPersonalDungeonRankPacked',
                     "onPressKeyDict[app.DIK_F6]	= lambda: self.OpenTimerWindow()",
                     "self.interface.UpdateTimer()"):
            self.assertIn(line, text)

    def test_the_packed_personal_rank_reaches_the_interface(self):
        seen = []
        Game = sash_test.compiled("game.py", "GameWindow", ["SetPersonalDungeonRank", "__SetPersonalDungeonRankPacked",
                                                            "QuestTimeReady"])
        game_window = Game()
        game_window.interface = type("I", (), {"SetPersonalDungeonRank": lambda self, *a: seen.append(a)})()
        game_window._GameWindow__SetPersonalDungeonRankPacked("/3/Alice/125/0")
        game_window._GameWindow__SetPersonalDungeonRankPacked("broken")
        self.assertEqual(seen, [("3", "Alice", "125", "0")])

    def test_the_interface_makes_the_windows_through_the_factory(self):
        text = self.source("interfacemodule.py")
        for line in ('self.wndTimer = nui_windows.make("dungeon-timer", uiTimerWindow.TimerWindow, "nui_dungeon_timer.TimerWindow")',
                     'self.wndDungeonRank = nui_windows.make("dungeon-rank", uiDungeonRank.DungeonRankWindow, "nui_dungeon_rank.DungeonRankWindow")',
                     "self.wndTimer.SetToolTip(self.tooltipItem)", "self.__MakeDungeonWindows()"):
            self.assertIn(line, text)
        self.assertIn('nui_windows.make("dungeon-drops", MobDropPopup, "nui_dungeon_drops.MobDropPopup", self.interface)',
                      self.source("uitimerwindow.py"))

    def test_the_uiscripts_name_the_children_the_loaders_get(self):
        world = legacy_world()
        for script, loader in (("timerwindow.py", "uitimerwindow.py"), ("dungeonrankwindow.py", "uidungeonrank.py")):
            with world.game:
                window = support.read_uiscript("uiscript/" + script)
            names = set()

            def walk(element):
                names.add(element.get("name"))
                for child in element.get("children", ()):
                    walk(child)
            walk(window)
            for name in re.findall(r'GetChild\("(\w+)"\)|getObject\("(\w+)"\)', self.source(loader)):
                name = name[0] or name[1]
                self.assertIn(name, names, "%s: %s" % (script, name))


class Locales(unittest.TestCase):
    def test_every_key_in_every_locale(self):
        w6.check_keys(self, GAME_KEYS)
        w6.check_keys(self, INTERFACE_KEYS, "locale_interface.txt")

    def test_every_locale_has_the_title_list(self):
        for locale, entries in w6.locale_keys().items():
            self.assertGreaterEqual(len(entries["TIMERWINDOW_DUNGEON_TITLES"][0].split(",")), 7, locale)


if __name__ == "__main__":
    unittest.main()
