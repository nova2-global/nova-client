"""Tests for the legacy boss info panel and damage count window (NOVA-27;
OLD root/uiBossInfo.py, uiDamageCount.py, uiscript/DamageCount.py, BOSS_INFO
and __BOSS_DAMAGE_COUNT__): python3 -B -m unittest boss_windows_test (from
tools/).

The server's half (the boss list of a map at login and at each boss death or
respawn, the "ClearBossInfo", "AddBossInfo <vnum> <alive> <respawn time>"
and "BossInfoLoadComplete" commands, GC::BOSS_DAMAGE_COUNT rows to a player
who targets a damage-count boss) is fork S's; the C++ half (the packet to
game.BINARY_UpdateBossDamageCount, systemSetting's BOSS_INFO flag) is fork
C's. Here the legacy Python runs over boss_windows_support's stand-ins:
- uibossinfo.BossInfoWindow: the rows OLD lays out (OLD
  uiBossInfo.py:131-226), alive in green and dead in red, the expanded flag
  read and written through systemSetting, the slide, the tooltip with the
  level, the state and the respawn clock;
- uidamagecount.DamageCountWindow: the top 10 attackers by damage, their
  share and bar, the own row's frame, the flash of an updated row, the
  target's HP;
- game.py's server commands and callbacks and the target board's hooks,
  the Interface's methods and its show and hide rules, compiled from the
  files themselves;
- every new key in all 17 locales."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boss_windows_support as bw  # noqa: E402

GAME_KEYS = ("BOSS_INFO_LEVEL", "BOSS_INFO_ALIVE", "BOSS_INFO_DEAD", "BOSS_INFO_RESPAWN", "BOSS_INFO_EXPAND",
             "BOSS_INFO_COLLAPSE", "DAMAGE_COUNT_DAMAGE")
GREEN, RED = 0xFFC3D4C4, 0xFFE57875
NOW = 1700000000


def loaded(world, bosses, expanded=None):
    window = world.boss_info()
    if expanded is not None:
        world.expanded[0] = expanded
    with world, bw.quiet():
        window.ClearBossInfo()
        for vnum, alive, respawn in bosses:
            window.AddBossInfo(vnum, alive, respawn)
        window.BossInfoLoadComplete()
    return window


def row_texts(window):
    return [(row.nameText.text, row.nameText.color) for row in window.rows if row.visible()]


class BossInfo(unittest.TestCase):
    def test_three_bosses_are_rows_of_oldss_layout_alive_in_green_dead_in_red(self):
        world = bw.World()
        window = loaded(world, [(997, 1, 0), (998, 0, NOW + 300), (2091, 1, 0)])
        self.assertTrue(window.IsShow())
        self.assertEqual(row_texts(window), [("Green Dragon", GREEN), ("Abomination", RED),
                                             ("Queen Spider", GREEN)])
        self.assertEqual([row.position for row in window.rows], [(10, 16), (10, 56), (10, 96)])
        # OLD: max(2, n) * 53, minus 8 for three rows; the board 138 wide at (10, 0).
        self.assertEqual(window.board.size, (138, 151))
        self.assertEqual(window.size, (163, 151))
        self.assertEqual(window.minimizeButton.position, (129, 151 // 2 - 16))
        self.assertTrue(window.minimizeButton.shown)
        self.assertFalse(window.expandButton.shown)
        self.assertEqual(window.position, (-10, 250))

    def test_one_boss_sits_lower_and_the_board_keeps_two_rows_of_height(self):
        world = bw.World()
        window = loaded(world, [(999, 1, 0)])
        self.assertEqual(window.rows[0].position, (10, 46))
        self.assertEqual(window.board.size, (138, 106))
        self.assertEqual(window.minimizeButton.position, (129, 16))

    def test_a_name_longer_than_14_characters_widens_every_row(self):
        world = bw.World()
        window = loaded(world, [(1093, 1, 0), (997, 1, 0)])
        self.assertEqual(window.board.size[0], 185)
        self.assertEqual([row.size[0] for row in window.rows], [165, 165])

    def test_no_boss_closes_the_panel(self):
        world = bw.World()
        window = loaded(world, [(997, 1, 0)])
        with world:
            window.ClearBossInfo()
            window.BossInfoLoadComplete()
        self.assertFalse(window.IsShow())
        self.assertFalse(window.HasBossInfo())
        self.assertEqual(row_texts(window), [])

    def test_a_collapsed_panel_shows_only_its_edge_and_the_expand_button(self):
        world = bw.World(expanded=0)
        window = loaded(world, [(997, 1, 0), (998, 1, 0)])
        self.assertEqual(window.position, (-(138 - 10), 250))
        self.assertTrue(window.expandButton.shown)
        self.assertFalse(window.minimizeButton.shown)

    def test_the_toggle_writes_the_flag_and_slides_four_pixels_a_frame(self):
        world = bw.World()
        window = loaded(world, [(997, 1, 0), (998, 1, 0)])
        with world:
            window.minimizeButton.click()
            self.assertEqual(world.expanded[0], 0)
            self.assertTrue(window.expandButton.shown)
            for _ in range(200):
                window.OnUpdate()
            # OLD stops once x is no longer above -(width - 20).
            self.assertEqual(window.position, (-118, 250))
            window.expandButton.click()
            self.assertEqual(world.expanded[0], 1)
            for _ in range(200):
                window.OnUpdate()
            self.assertEqual(window.position, (2, 250))
        self.assertTrue(window.minimizeButton.shown)

    def test_the_tooltip_shows_the_level_the_state_and_the_respawn_clock(self):
        world = bw.World()
        world.game.timestamp = NOW
        window = loaded(world, [(997, 1, 0), (998, 0, NOW + 125)])
        with world:
            window.rows[1].OnMouseOverIn()
            tip = window.toolTip
            self.assertTrue(tip.shown)
            self.assertEqual(tip.title, "Abomination")
            self.assertEqual(tip.lines, ["Level 120", "Dead", "Respawning in 2 Minutes, 5 Sec"])
            world.clock(65)
            window.OnUpdate()
            self.assertEqual(tip.lines[-1], "Respawning in 1 Minutes")
            world.clock(60)
            window.OnUpdate()
            self.assertEqual(tip.lines, ["Level 120", "Dead"])
            window.rows[1].OnMouseOverOut()
            self.assertFalse(tip.shown)
            window.rows[0].OnMouseOverIn()
            self.assertEqual(tip.lines, ["Level 120", "Alive"])

    def test_a_new_list_replaces_the_old_rows(self):
        world = bw.World()
        window = loaded(world, [(997, 1, 0), (998, 1, 0), (999, 1, 0)])
        old_rows = list(window.rows)
        with world:
            window.ClearBossInfo()
            window.AddBossInfo(56007, 0, NOW)
            window.BossInfoLoadComplete()
        self.assertTrue(all(not row.shown for row in old_rows))
        self.assertEqual(row_texts(window), [("Aquadragonis", RED)])
        self.assertTrue(window.HasBossInfo())


def attackers(world, vids):
    for vid, (name, race) in vids.items():
        world.instances[vid] = (name, race)


def damage_rows(window):
    return [(row.noNumber.text, row.NameLabel.text, row.DamageLabel.text, row.size[0])
            for row in window.activeRows if row.shown]


class DamageCount(unittest.TestCase):
    def setUp(self):
        self.world = bw.World()
        self.world.instances[500] = ("Green Dragon", 997)
        attackers(self.world, {11: ("Alpha", 0), 12: ("Me", 1), 13: ("Gamma", 2)})
        self.window = self.world.damage_count()

    def feed(self, *rows):
        with self.world, bw.quiet():
            for attacker, damage in rows:
                self.window.AddData(attacker, 500, damage)

    def test_rows_are_sorted_by_damage_with_their_share_and_bar(self):
        self.feed((11, 1500), (12, 3000), (13, 1500))
        self.assertEqual(damage_rows(self.window), [
            ("1.", "Me", "Damage: 3.0K(50.0%)", 380),
            ("2.", "Alpha", "Damage: 1.5K(25.0%)", 190),
            ("3.", "Gamma", "Damage: 1.5K(25.0%)", 190)])
        self.assertEqual(self.window.size[1], 65 + 3 * 25)
        self.assertEqual(self.window.targetName.text, "Green Dragon")

    def test_one_attacker_has_the_whole_share(self):
        self.feed((11, 999))
        self.assertEqual(damage_rows(self.window), [("1.", "Alpha", "Damage: 1.0K(100.0%)", 380)])

    def test_millions_read_as_m(self):
        self.feed((11, 2500000), (12, 2500000))
        self.assertEqual(damage_rows(self.window)[0][2], "Damage: 2.5M(50.0%)")

    def test_ten_rows_at_most_and_attackers_out_of_view_are_left_out(self):
        attackers(self.world, dict((100 + i, ("P%d" % i, i % 8)) for i in range(12)))
        self.feed(*[(100 + i, 1000 * (i + 1)) for i in range(12)])
        self.feed((99, 999999))  # not in view
        rows = damage_rows(self.window)
        self.assertEqual(len(rows), 10)
        self.assertEqual([row[1] for row in rows[:2]], ["P11", "P10"])
        self.assertEqual(rows[0][0], "1.")

    def test_the_own_row_is_framed(self):
        self.feed((11, 10), (12, 5))
        framed = dict((row.NameLabel.text, row.topLine.shown) for row in self.window.activeRows)
        self.assertEqual(framed, {"Alpha": False, "Me": True})

    def test_a_new_victim_starts_a_new_list(self):
        self.feed((11, 10), (12, 5))
        self.world.instances[501] = ("Aquadragonis", 56007)
        with self.world:
            self.window.AddData(13, 501, 7)
        self.assertEqual([row[1] for row in damage_rows(self.window)], ["Gamma"])
        self.assertEqual(self.window.targetName.text, "Aquadragonis")

    def test_the_updated_row_flashes_grey_then_turns_white(self):
        self.feed((11, 10), (12, 5))
        updated = [row for row in self.window.activeRows if row.NameLabel.text == "Me"][0]
        self.assertEqual(updated.DamageLabel.color, 0xFF5D5D5D)
        with self.world:
            updated.OnUpdate()
            self.assertEqual(updated.DamageLabel.color, 0xFF5D5D5D)
            self.world.clock(0.2)
            updated.OnUpdate()
        self.assertEqual(updated.DamageLabel.color, 0xFFFFFFFF)

    def test_the_faces_are_new_s_job_faces(self):
        attackers(self.world, {21: ("Wolf", 7)})
        self.feed((11, 10), (12, 5), (13, 3), (21, 1))
        faces = dict((row.NameLabel.text, row.raceImg.image) for row in self.window.activeRows)
        self.assertEqual(faces["Alpha"], "d:/ymir work/ui/game/windows/face_warrior.sub")
        self.assertEqual(faces["Me"], "d:/ymir work/ui/game/windows/face_assassin.sub")
        self.assertEqual(faces["Gamma"], "d:/ymir work/ui/game/windows/face_sura.sub")
        self.assertEqual(faces["Wolf"], "d:/ymir work/ui/game/windows/face_shaman.sub")

    def test_hp_percent_colors_and_numbers(self):
        with self.world:
            self.window.AddHPInfo(500, 80)
            self.assertEqual(self.window.hpPercenttxt.text, "80%")
            self.assertEqual(self.window.hpPercenttxt.color, self.world.ui.GenerateColor(167, 255, 212))
            self.assertEqual(self.window.hpValues.text, "")
            self.assertEqual(self.window.hpGauge.percent, (80, 100))
            self.window.AddHPInfo(500, 30, 1000, 2000)
            self.assertEqual(self.window.hpPercenttxt.color, self.world.ui.GenerateColor(255, 230, 186))
            self.assertEqual(self.window.hpValues.text, "1.000 / 2.000")
            self.window.AddHPInfo(500, 10)
            self.assertEqual(self.window.hpPercenttxt.color, self.world.ui.GenerateColor(255, 0, 0))

    def test_open_places_it_and_exit_closes_and_empties_it(self):
        self.feed((11, 10))
        with self.world:
            self.window.Open()
            self.assertEqual(self.window.position, ((1600 - 720) // 2, 100))
            self.assertTrue(self.window.IsShow())
            self.window.GetChild("exit").click()
        self.assertFalse(self.window.IsShow())
        self.assertEqual(damage_rows(self.window), [])
        self.assertEqual(self.window.playerList, {})


class Interface(object):
    pass


class GameWiring(unittest.TestCase):
    def test_the_server_commands_reach_the_interface(self):
        source = bw.source("game.py")
        for command, method in (("ClearBossInfo", "__ClearBossInfo"), ("AddBossInfo", "__AddBossInfo"),
                                ("BossInfoLoadComplete", "__BossInfoLoadComplete")):
            self.assertIn('"%s"' % command, source)
            self.assertIn("self.%s" % method, source)
        calls = []

        class Stub(object):
            def __getattr__(self, name):
                return lambda *args: calls.append((name,) + args)
        Game = bw.compiled("game.py", "GameWindow", ["__AddBossInfo", "__ClearBossInfo", "__BossInfoLoadComplete"])
        game = Game()
        game.interface = Stub()
        game._GameWindow__ClearBossInfo()
        game._GameWindow__AddBossInfo("997", "0", "1700000300")
        game._GameWindow__BossInfoLoadComplete()
        self.assertEqual(calls, [("ClearBossInfo",), ("AddBossInfo", 997, 0, 1700000300), ("BossInfoLoadComplete",)])

    def test_the_damage_rows_fill_and_open_the_window(self):
        world = bw.World()
        world.instances[500] = ("Green Dragon", 997)
        world.instances[11] = ("Alpha", 0)
        window = world.damage_count()
        Game = bw.compiled("game.py", "GameWindow", ["BINARY_UpdateBossDamageCount"], {"getattr": getattr})
        game = Game()
        game.interface = Interface()
        game.interface.wndDamageCount = window
        with world, bw.quiet():
            game.BINARY_UpdateBossDamageCount(11, 500, 12345678901)
        self.assertTrue(window.IsShow())
        self.assertEqual(damage_rows(window), [("1.", "Alpha", "Damage: 12345.7M(100.0%)", 380)])

    def test_the_target_board_hooks_close_the_window_and_feed_its_hp(self):
        world = bw.World()
        window = world.damage_count()
        events = []

        class Target(object):
            vid = 0

            def GetTargetVID(self):
                return self.vid

            def ResetTargetBoard(self):
                events.append("reset")

            def SetEnemyVID(self, vid):
                self.vid = vid

            def SetHP(self, hp):
                events.append(("hp", hp))

            def Show(self):
                pass

            def Close(self):
                events.append("close")
        Game = bw.compiled("game.py", "GameWindow", ["SetHPTargetBoard", "CloseTargetBoardIfDifferent",
                                                     "CloseTargetBoard", "__CloseDamageCount"])
        game = Game()
        game.targetBoard = Target()
        game.interface = Interface()
        game.interface.wndDamageCount = window
        with world:
            window.Show()
            game.SetHPTargetBoard(500, 64)
            self.assertFalse(window.IsShow(), "a new target closes the damage window")
            self.assertEqual(window.hpPercenttxt.text, "64%")
            window.Show()
            game.SetHPTargetBoard(500, 60)
            self.assertTrue(window.IsShow(), "the same target keeps it")
            game.CloseTargetBoardIfDifferent(500)
            self.assertTrue(window.IsShow())
            game.CloseTargetBoardIfDifferent(501)
            self.assertFalse(window.IsShow())
            window.Show()
            game.CloseTargetBoard()
            self.assertFalse(window.IsShow())


class InterfaceWiring(unittest.TestCase):
    def test_the_interface_makes_both_windows_through_make(self):
        source = bw.source("interfacemodule.py")
        self.assertIn('nui_windows.make("boss-info", uiBossInfo.BossInfoWindow, "nui_boss_info.BossInfoWindow")', source)
        self.assertIn('nui_windows.make("damage-count", uiDamageCount.DamageCountWindow, '
                      '"nui_damage_count.DamageCountWindow")', source)
        self.assertIn("import uiBossInfo", source)
        self.assertIn("import uiDamageCount", source)

    def test_the_interface_forwards_the_boss_list(self):
        Bound = bw.compiled("interfacemodule.py", "Interface", ["ClearBossInfo", "AddBossInfo", "BossInfoLoadComplete"])
        world = bw.World()
        interface = Bound()
        interface.wndBossInfo = world.boss_info()
        with world, bw.quiet():
            interface.ClearBossInfo()
            interface.AddBossInfo(997, 1, 0)
            interface.BossInfoLoadComplete()
        self.assertEqual(row_texts(interface.wndBossInfo), [("Green Dragon", GREEN)])

    def test_show_all_shows_the_panel_only_with_bosses_and_hide_all_hides_it(self):
        Bound = bw.compiled("interfacemodule.py", "Interface", ["ShowAllWindows", "HideAllWindows"],
                            {"app": type("app", (), {"ENABLE_DRAGON_SOUL_SYSTEM": 0})})

        class Plain(object):
            shown = False

            def Show(self):
                self.shown = True

            def Hide(self):
                self.shown = False

            def IsShow(self):
                return self.shown

            def SetTop(self):
                pass

        world = bw.World()
        interface = Bound()
        for name in ("wndTaskBar", "wndCharacter", "wndInventory", "wndExtraInventory", "wndChat", "wndMiniMap",
                     "wndEnergyBar", "wndExpandedTaskBar", "wndParty", "wndGameButton", "wndMessenger",
                     "wndGuild", "wndChatLog", "wndSafebox", "wndMall", "dlgExchange", "wndMyShopDeco"):
            setattr(interface, name, Plain())
        interface.__dict__.setdefault("wndDamageCount", None)
        interface.wndBossInfo = world.boss_info()
        with world:
            interface.HideAllWindows()
            interface.ShowAllWindows()
            self.assertFalse(interface.wndBossInfo.IsShow(), "no boss list: OLD showed an empty panel")
        interface.wndBossInfo = loaded(world, [(997, 1, 0)])
        with world:
            interface.HideAllWindows()
            self.assertFalse(interface.wndBossInfo.IsShow())
            interface.ShowAllWindows()
            self.assertTrue(interface.wndBossInfo.IsShow())

    def test_the_quest_curtain_hides_the_panel_and_the_close_destroys_both(self):
        source = bw.source("interfacemodule.py")
        hide = source[source.index("def __HideWindows"):]
        hide = hide[:hide.index("\n\tdef ")]
        self.assertIn("self.wndBossInfo", hide)
        close = source[source.index("\tdef Close(self):"):]
        close = close[:close.index("\n\tdef ")]
        self.assertIn("self.wndBossInfo.Destroy()", close)
        self.assertIn("self.wndDamageCount.Destroy()", close)


class Locale(unittest.TestCase):
    def test_every_new_key_is_in_all_17_locales(self):
        files = bw.locale_files()
        self.assertEqual(len(files), 17)
        for name, game, _ in files:
            values = bw.read_locale(game)
            for key in GAME_KEYS:
                self.assertIn(key, values, "%s: %s" % (name, key))
            self.assertEqual(values["BOSS_INFO_RESPAWN"].count("%s"), 1, name)
            self.assertEqual(values["BOSS_INFO_LEVEL"].count("%d"), 1, name)
            self.assertEqual(values["DAMAGE_COUNT_DAMAGE"].count("%s"), 2, name)


if __name__ == "__main__":
    unittest.main()
