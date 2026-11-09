"""Tests of the NOVA-40 client (the target board's numbers, element and info
button, the mob info board): python3 -B -m unittest target_info_test (from
tools/). The C++ half (GC::TARGET's new fields, CG::TARGET_INFO_LOAD,
GC::TARGET_INFO, the nonplayer getters, the name star and level) is in
nova-client-src's userinterface_tests.

The cache and stats are checked on uitargetinfo alone; the board flows on the
legacy board (uitarget.py, uitargetinfo.py) and on the NovaUI facades
(nui_target.py, nui_target_info.py) over the same stand-in world, and both
must show the same; the rest of the NovaUI side is the document."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_hud_test as hud  # noqa: E402
import nui_w4_world as w4  # noqa: E402

ASSETS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets"))
WINDOW = os.path.join(ASSETS, "nui", "nui", "windows", "target-info")
RACE = 5001
VID = 300


class _ScrollWindow(object):
    """ui.ScrollWindow as the drop list uses it."""

    THIN = 0

    def __init__(self, width, height, kind=0):
        pass

    def __getattr__(self, name):
        return lambda *args: None


def mob_setup(game, level=20, rows=None):
    hud.target_setup(game)
    game.modules["localeInfo"] = hud.support.locale_info("en")
    # The facades need the Wave 4 engine (nui_hud.has_engine_4).
    nuigame = game.modules["nuigame"]
    for name in ("WatchLeaveRange", "WhisperAttach", "StopLeaveRange"):
        if getattr(nuigame, name, None) is None:
            setattr(nuigame, name, lambda *args: None)
    game.modules["nui"]._nui.LoadDocumentAs = lambda path, model: True
    ui_mod = game.modules["ui"]
    ui_mod.ScrollWindow = _ScrollWindow
    # The legacy board's anchor reads the target board's frame.
    for name, value in (("GetLeft", 0), ("GetBottom", 40), ("GetWidth", 250)):
        setattr(ui_mod.Window, name, lambda self, value=value: value)
    answer = game.answer
    answer("nonplayer", "GetRaceNumByVID", lambda vid: RACE if vid == VID else -1)
    answer("nonplayer", "GetMonsterMaxHP", lambda race: 1234)
    answer("nonplayer", "GetMonsterLevel", lambda race: 10)
    answer("nonplayer", "GetMonsterDamage", lambda race: (10, 20))
    answer("nonplayer", "GetMonsterST", lambda race: 30)
    answer("nonplayer", "GetMonsterDX", lambda race: 25)
    answer("nonplayer", "GetMonsterDamageMultiply", lambda race: 1.0)
    answer("nonplayer", "GetMonsterExp", lambda race: 1000)
    answer("nonplayer", "GetMobGoldMin", lambda race: 11)
    answer("nonplayer", "GetMobGoldMax", lambda race: 22)
    answer("nonplayer", "GetMobRegenPercent", lambda race: 7)
    answer("nonplayer", "GetMobRegenCycle", lambda race: 3)
    answer("nonplayer", "GetMonsterRaceFlag", lambda race: (1 << 4) | (1 << 12))
    answer("nonplayer", "IsMonsterStone", lambda race: False)
    answer("nonplayer", "GetResist", lambda race, kind: 15)
    item = game.modules["item"]
    for name, value in (("ITEM_TYPE_WEAPON", 1), ("ITEM_TYPE_ARMOR", 2), ("ITEM_TYPE_METIN", 10)):
        setattr(item, name, value)
    answer("item", "GetItemType", lambda: {11000: 1, 11002: 1, 11003: 1, 28030: 10, 28031: 10}.get(item.selected[0], 0))
    answer("item", "GetItemName", lambda: {11000: "Sword+0", 11002: "Sword+2", 11003: "Sword+3", 27001: "Red Potion"}.get(item.selected[0], "x"))
    answer("item", "GetIconImageFileName", lambda: "icon/item/%d.tga" % item.selected[0])
    player = game.modules["player"]
    for name, value in (("DX", 201), ("DEF_GRADE", 20), ("DEF_BONUS", 202)):
        setattr(player, name, value)
    game.status.update({player.LEVEL: level, player.DX: 40, player.DEF_GRADE: 5, player.DEF_BONUS: 0})
    game.stats = game.status


def world(nui_on, flags="+hud,+target-info", **kw):
    def setup(game):
        mob_setup(game, **kw)
        game.modules["systemSetting"].GetUINuiWindows = lambda: flags if nui_on else ""
    game_world = hud.HudWorld(nui_on, setup=setup)
    with game_world:
        game_world.board = game_world.make("target", game_world.module("uiTarget").TargetBoard, "nui_target.TargetBoard")
        game_world.board.Hide()
        for widget in (game_world.board, game_world.board.infoBoard):
            if getattr(type(widget), "NUI_FACADE", False) is not True:
                widget.GetLeft = widget.GetBottom = lambda: 0
                widget.GetWidth = lambda: 250
    return game_world


def pair(**kw):
    return world(False, **kw), world(True, **kw)


def targetinfo(w):
    return w.module("uiTargetInfo")


def sent(w, mark=0):
    return [args for name, args in w.game.log[mark:] if name == "net.SendTargetInfoLoad"]


def hide_sets(board):
    return board.infoBoard


def facade_rows(board):
    return board.infoBoard._state["rows"]


def legacy_rows(board):
    return [row.lines[0].GetText() for row in board.infoBoard.itemRows]


def legacy_lines(board):
    return [line.GetText() for line in board.infoBoard.children if hasattr(line, "GetText") and line.GetText()]


def facade_lines(board):
    return [line["text"] for line in board.infoBoard._state["lines"] if not line["sep"]]


class Cache(unittest.TestCase):
    def setUp(self):
        self.w = world(False)
        self.m = targetinfo(self.w)
        self.ci = self.w.game.modules["constInfo"]

    def test_weapons_of_one_base_merge_into_one_row_and_keep_their_vnums(self):
        with self.w:
            self.m.store(RACE, [(11000, 1, 0, 0, 0), (11003, 1, 0, 0, 0), (11002, 1, 0, 0, 0), (27001, 5, 0, 0, 0)])
        items = self.ci.MONSTER_INFO_DATA[RACE]["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(sorted(items[0]["vnum_list"]), [11000, 11002, 11003])
        self.assertEqual(items[1], {"count": 5, "damageRequired": 0, "minAttackers": 0, "maxAttackers": 0, "vnum": 27001})

    def test_a_map_change_forgets_the_rows_and_a_level_up_asks_again(self):
        with self.w:
            self.m.store(RACE, [])
        self.assertTrue(self.m.known(RACE))
        self.w.game.stats[self.w.game.modules["player"].LEVEL] += 1
        with self.w:
            self.assertFalse(self.m.known(RACE))
        self.w.game.stats[self.w.game.modules["player"].LEVEL] -= 1
        with self.w:
            self.assertTrue(self.m.known(RACE))
            self.m.forget()
            self.assertFalse(self.m.known(RACE))


class Stats(unittest.TestCase):
    def test_the_stats_are_olds_formulas(self):
        w = world(False, level=20)
        with w:
            lines = targetinfo(w).stat_lines(RACE)
        # DX 25 lv10 -> AR 90 cap? (25*4+20)/6=20; player DX 40 lv20 -> (160+40)/6=33.
        # fAR=(20+210)/300=.7667 fER=(33*2+5)/(128)*.3=.1664 -> .6003.
        # dmg (10+30)*2*.6003=48 +20=68; (20+30)*2*.6003=60+20=80; minus def 5, x1.0.
        self.assertIn("1,234", lines[0].replace(".", ","))
        # DX 25 lv 10: AR (100+20)//6=20, fAR 0.7667. Player DX 40 lv 20: ER
        # (160+40)//6=33, fER (71/128)*0.3=0.1664. Rate 0.6003. Damage
        # int((10+30)*2*rate)+20=68 and int((20+30)*2*rate)+20=80, minus DEF 5.
        self.assertEqual(lines[1], w.game.modules["localeInfo"].TARGET_INFO_DAMAGE % ("63", "75"))
        # Mob level 10, player 20: idx 5, 50% of 1000.
        self.assertIn("500", lines[2])

    def test_the_exp_uses_olds_delta_table(self):
        w = world(False, level=10)
        with w:
            lines = targetinfo(w).stat_lines(RACE)
        # mob level 10, player 10: idx 15 -> 100%.
        self.assertIn("1,000", lines[2].replace(".", ","))
        w2 = world(False, level=30)
        with w2:
            lines = targetinfo(w2).stat_lines(RACE)
        # 20 levels above the mob: idx 0 -> 1%.
        self.assertIn(" 10", lines[2].replace(".", ","))

    def test_the_race_line_lists_the_main_race_and_subrace(self):
        w = world(False)
        with w:
            lines = targetinfo(w).race_lines(RACE)
        self.assertIn(w.game.modules["localeInfo"].TARGET_INFO_RACE_ORC, lines[0])
        self.assertIn(w.game.modules["localeInfo"].TARGET_INFO_RACE_WIND, lines[1])


class Board(unittest.TestCase):
    def open(self, w):
        with w, hud.quiet():
            w.board.SetEnemyVID(VID)
            w.board.SetHP(62, 1234, 2000)
            w.board.Show()
            w.board.OnPressedInfoButton()

    def test_the_board_asks_for_the_target_once_and_shows_the_answer(self):
        legacy, novaui = pair()
        for w in (legacy, novaui):
            self.open(w)
            self.assertEqual(sent(w), [(VID,)], "the request goes out once per race")
            self.assertTrue(w.board.infoBoard.waiting)
        with legacy:
            targetinfo(legacy).store(RACE, [(11000, 1, 0, 0, 0), (27001, 3, 0, 0, 0)])
            legacy.board.RefreshInfoBoard(RACE)
        with novaui:
            targetinfo(novaui).store(RACE, [(11000, 1, 0, 0, 0), (27001, 3, 0, 0, 0)])
            novaui.board.RefreshInfoBoard(RACE)
        self.assertEqual(legacy_rows(legacy.board), [r["text"] for r in facade_rows(novaui.board)])
        self.assertEqual(legacy_rows(legacy.board), ["item 11000", "3x item 27001"])
        self.assertEqual(legacy_lines(legacy.board), facade_lines(novaui.board))

    def test_a_dropped_request_is_sent_again_and_stops_after_the_answer(self):
        legacy, novaui = pair()
        for w in (legacy, novaui):
            self.open(w)
        with legacy:
            legacy.board.infoBoard.nextRetry = 0.0
            legacy.board.infoBoard.OnUpdate()
        self.assertEqual(len(sent(legacy)), 2)
        with novaui:
            self.assertGreater(novaui.board.infoBoard._state["retry"], 0.0, "the facade arms a nui-countdown, not OnUpdate")
            novaui.board.infoBoard.nui_retry()
        self.assertEqual(len(sent(novaui)), 2)
        for w in (legacy, novaui):
            with w:
                targetinfo(w).store(RACE, [])
                w.board.RefreshInfoBoard(RACE)
                self.assertFalse(w.board.infoBoard.waiting)
                mark = len(w.game.log)
                w.board.infoBoard.RetryRequest()
                self.assertEqual(sent(w, mark), [])

    def test_retries_stop_at_the_cap(self):
        w = world(False)
        self.open(w)
        with w:
            for _ in range(10):
                w.board.infoBoard.RetryRequest()
        self.assertEqual(len(sent(w)), 1 + targetinfo(w).RETRY_MAX)
        self.assertFalse(w.board.infoBoard.waiting)

    def test_a_mob_with_no_drops_shows_the_no_items_line_and_stops_waiting(self):
        legacy, novaui = pair()
        for w in (legacy, novaui):
            self.open(w)
            with w:
                targetinfo(w).store(RACE, [])
                w.board.RefreshInfoBoard(RACE)
            self.assertFalse(w.board.infoBoard.waiting)
        locale = legacy.game.modules["localeInfo"]
        self.assertIn(locale.TARGET_INFO_NO_ITEM_TEXT, legacy_lines(legacy.board))
        self.assertIn(locale.TARGET_INFO_NO_ITEM_TEXT, facade_lines(novaui.board))

    def test_the_attacker_rows_show_in_both(self):
        legacy, novaui = pair()
        for w in (legacy, novaui):
            self.open(w)
            with w:
                targetinfo(w).store(RACE, [(27001, 3, 0, 5, 0)])
                w.board.RefreshInfoBoard(RACE)
        extra = legacy.board.infoBoard.itemRows[0].lines[1:]
        self.assertEqual([line.GetText() for line in extra][:1], [legacy.game.modules["localeInfo"].TARGET_INFO_ATTACKERS_INACTIVE])
        self.assertEqual(len(facade_rows(novaui.board)[0]["lines"]), 2)

    def test_the_info_button_toggles_the_board_and_closes_with_the_target(self):
        legacy, novaui = pair()
        for w in (legacy, novaui):
            self.open(w)
            self.assertTrue(w.board.infoBoard.IsShow())
            with w:
                w.board.OnPressedInfoButton()
            self.assertFalse(w.board.infoBoard.IsShow())
            with w:
                w.board.OnPressedInfoButton()
                self.assertTrue(w.board.infoBoard.IsShow())
                w.board.ResetTargetBoard()
                self.assertFalse(w.board.infoBoard.IsShow(), "the board goes with the target")

    def test_no_info_button_for_a_player(self):
        for w in pair():
            with w, hud.quiet():
                w.board.SetEnemyVID(hud.PEER_VID)
                w.board.OnPressedInfoButton()
            self.assertEqual(sent(w), [])

    def test_the_attacker_count_refreshes_an_open_board(self):
        legacy = world(False)
        self.open(legacy)
        with legacy:
            targetinfo(legacy).store(RACE, [(27001, 3, 0, 0, 0)])
            legacy.board.RefreshInfoBoard(RACE)
            legacy.board.SetAttackers(4)
        self.assertEqual(legacy.game.modules["constInfo"].MONSTER_INFO_DATA[RACE]["currentAttackers"], 4)
        with legacy:
            self.assertFalse(targetinfo(legacy).set_attackers(RACE, 4), "the same count changes nothing")


class BoardHP(unittest.TestCase):
    def test_a_monster_shows_percent_and_numbers(self):
        legacy, novaui = pair()
        for w in (legacy, novaui):
            with w, hud.quiet():
                w.board.SetEnemyVID(VID)
                w.board.SetHP(62, 1234, 2000)
        self.assertEqual(legacy.board.hpPercent.GetText(), "62%")
        self.assertEqual(legacy.board.hpValues.GetText().replace(".", ","), "1,234 / 2,000")
        self.assertEqual(novaui.board.hpValues.replace(".", ","), "1,234 / 2,000")

    def test_no_numbers_without_a_max_hp(self):
        for w in pair():
            with w, hud.quiet():
                w.board.SetEnemyVID(VID)
                w.board.SetHP(10)
        self.assertEqual(w.board.hpValues, "")

    def test_a_player_target_gets_the_gauge_and_percent(self):
        legacy, novaui = pair()
        with legacy, hud.quiet():
            legacy.board.SetPCHP(75)
        self.assertEqual(legacy.board.hpPercent.GetText(), "75%")
        self.assertTrue(legacy.board.hpGauge.IsShow())
        with novaui, hud.quiet():
            novaui.board.SetPCHP(75)
        self.assertAlmostEqual(novaui.board.hp, 0.75)
        self.assertTrue(novaui.board.hpShown)

    def test_the_element_is_set_once_for_a_new_value(self):
        legacy, novaui = pair()
        for w in (legacy, novaui):
            with w, hud.quiet():
                w.board.SetElement(6)
                w.board.SetElement(6)
                w.board.SetElement(0)
        self.assertEqual(legacy.board.elementText.GetText() or "", legacy.game.modules["localeInfo"].TARGET_INFO_RACE_DARK)
        self.assertFalse(legacy.board.elementText.IsShow())
        self.assertEqual(novaui.board.element, 0)


class Wiring(unittest.TestCase):
    def test_game_passes_the_new_fields_to_the_boards(self):
        import boss_windows_support as bw
        with hud.quiet():
            import types
            Game = bw.compiled("game.py", "GameWindow", ["SetHPTargetBoard", "SetPCTargetHP", "BINARY_SetTargetInfo", "__CloseDamageCount"],
                               scope={"uiTargetInfo": types.SimpleNamespace(store=lambda r, rows: store.append((r, rows)))})
        calls = []
        store = []
        class Board(object):
            vid = 7
            def GetTargetVID(self): return self.vid
            def ResetTargetBoard(self): calls.append("reset")
            def SetEnemyVID(self, vid): self.vid = vid
            def SetHP(self, *a): calls.append(("hp",) + a)
            def SetElement(self, e): calls.append(("el", e))
            def SetAttackers(self, n): calls.append(("at", n))
            def SetPCHP(self, p): calls.append(("pc", p))
            def Show(self): pass
            def RefreshInfoBoard(self, r): calls.append(("ref", r))
        game = Game.__new__(Game)
        game.targetBoard = Board()
        game.interface = None
        game.SetHPTargetBoard(7, 50, 500, 1000, 3, 2)
        game.SetPCTargetHP(7, 40)
        game.SetPCTargetHP(99, 40)
        game.BINARY_SetTargetInfo(5001, ((1, 2, 0, 0, 0),))
        self.assertIn(("hp", 50, 500, 1000), calls)
        self.assertIn(("el", 3), calls)
        self.assertIn(("at", 2), calls)
        self.assertEqual([c for c in calls if c[0] == "pc"], [("pc", 40)])
        self.assertEqual(store, [(5001, ((1, 2, 0, 0, 0),))])
        self.assertIn(("ref", 5001), calls)


class Fallback(unittest.TestCase):
    def test_the_legacy_info_board_opens_under_the_novaui_target_board(self):
        # The target-info flag off with the target board on: a real mix.
        w = world(True, flags="+hud")
        self.assertEqual(type(w.board.infoBoard).__module__, "uiTargetInfo")
        with w, hud.quiet():
            w.board.SetEnemyVID(VID)
            w.board.OnPressedInfoButton()
        self.assertTrue(w.board.infoBoard.IsShow())


class MobInfoOptions(unittest.TestCase):
    """OLD's "monster_info" rows (uiGameOption.py:1156, 1189-1191), on legacy
    and NovaUI: the name's level and aggressive star, on by default."""

    def world(self, nui_on):
        import nui_sys_test as sys_test
        world = sys_test.World(nui_on)
        options = world.make_game_options()
        with world.game, sys_test.quiet():
            options.Show()
        return world, options, sys_test

    def test_a_press_flips_the_setting_on_legacy_and_novaui(self):
        world, options, sys_test = self.world(False)
        with world.game, sys_test.quiet():
            options.mobLevelButtonList[1].Click()
            options.mobAIButtonList[1].Click()
        self.assertFalse(world.game.settings["show_mob_level"])
        self.assertFalse(world.game.settings["show_mob_ai"])
        self.assertEqual([b.down for b in options.mobLevelButtonList], [False, True])

        world, options, sys_test = self.world(True)
        board = sys_test.board(options)
        self.assertTrue(board.model["mob_level"])
        with world.game, sys_test.quiet():
            board.fire("choose", "mob_level", 0, 0)
            board.fire("choose", "mob_ai", 0, 0)
        self.assertFalse(world.game.settings["show_mob_level"])
        self.assertFalse(sys_test.board(options).model["mob_ai"])


class Document(unittest.TestCase):
    def test_the_fixtures_hold_every_model_key(self):
        model = {"lines", "rows", "retry"}
        for name in ("target-info.fixture.json", "target-info.empty.fixture.json"):
            with open(os.path.join(WINDOW, name), encoding="utf-8") as handle:
                data = json.load(handle)
            self.assertEqual(set(data["target_info"]), model, name)

    def test_a_facade_stands_on_a_plain_window(self):
        w = world(True)
        self.assertEqual(type(w.board.infoBoard).__module__, "nui_target_info")
        self.assertIsNone(type(w.board.infoBoard).OnUpdate)

    def test_the_target_fixtures_carry_the_new_keys(self):
        for name in ("target.fixture.json", "target.mob.fixture.json", "target.player.fixture.json"):
            with open(os.path.join(os.path.dirname(WINDOW), "target", name), encoding="utf-8") as handle:
                data = json.load(handle)
            for key in ("hp_values", "element", "element_name", "show_info"):
                self.assertIn(key, data["target"], name)
