"""Tests for the NovaUI damage count window (assets/root/nui_damage_count.py;
NOVA-27): python3 -B -m unittest nui_damage_count_test (from tools/).

Each flow runs on legacy's uidamagecount.DamageCountWindow and on the NovaUI
subclass, each in a world of its own (boss_windows_support.World), driven
as game.py drives them (its own BINARY_UpdateBossDamageCount,
SetHPTargetBoard and CloseTargetBoard, compiled from game.py), and what each
shows must match: the rows (rank, name, damage text, bar width, own frame,
face), the boss's name, the HP texts and color, whether it shows; the
updated row's flash. The NovaUI side also checks its board, that no Python
runs per frame, the close button, the fixtures and make()'s fallback."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boss_windows_support as bw  # noqa: E402

DOCUMENT = "nui/windows/damage-count/damage-count.rml"
WINDOW_DIR = os.path.join(bw.ASSETS, "nui", "nui", "windows", "damage-count")
BOSS = 500


class Interface(object):
    pass


class Target(object):
    vid = 0

    def GetTargetVID(self):
        return self.vid

    def ResetTargetBoard(self):
        pass

    def SetEnemyVID(self, vid):
        self.vid = vid

    def SetHP(self, hp):
        pass

    def Show(self):
        pass

    def Close(self):
        pass


def game_for(world, window):
    Game = bw.compiled("game.py", "GameWindow", ["BINARY_UpdateBossDamageCount", "SetHPTargetBoard",
                                                 "CloseTargetBoardIfDifferent", "CloseTargetBoard",
                                                 "__CloseDamageCount"], {"getattr": getattr})
    game = Game()
    game.interface = Interface()
    game.interface.wndDamageCount = window
    game.targetBoard = Target()
    return game


def shown(world, window):
    """(shown, target, hp, hp percent, hp color tone, rows)."""
    if world.nui_on:
        board = bw.board_of(window)
        if board is None or not window.IsShow():
            return (False,)
        model = board.model
        rows = [(row["no"], row["name"], row["damage"], row["width"], row["own"], row["face"]) for row in model["rows"]]
        return (True, model["target"], model["hp_text"], model["hp_percent"], model["hp_tone"], rows)
    if not window.IsShow():
        return (False,)
    tone = {window.ui_color(100): "high", window.ui_color(50): "mid"}.get(window.hpPercenttxt.color, "low")
    rows = [(row.noNumber.text, row.NameLabel.text, row.DamageLabel.text, row.size[0], row.topLine.shown,
             row.raceImg.image if row.raceImg.shown else "") for row in window.activeRows if row.shown]
    return (True, window.targetName.text, window.hpValues.text, window.hpPercenttxt.text, tone, rows)


class DamageTest(unittest.TestCase):
    def worlds(self, **kwargs):
        pairs = []
        for nui_on in (False, True):
            world = bw.World(nui_on=nui_on, **kwargs)
            world.instances[BOSS] = ("Green Dragon", 997)
            world.instances.update({11: ("Alpha", 0), 12: ("Me", 1), 13: ("Gamma", 2), 14: ("Wolf", 7)})
            window = world.damage_count()
            window.ui_color = world.uiDamageCount.hp_color
            pairs.append((world, window, game_for(world, window)))
        return pairs

    def both(self, pairs, flow):
        for world, window, game in pairs:
            with world, bw.quiet():
                flow(world, window, game)
        (lw, legacy, _), (nw, novaui, _) = pairs
        self.assertEqual(shown(nw, novaui), shown(lw, legacy))
        return shown(nw, novaui)


class Differential(DamageTest):
    def test_rows_hp_and_target_match_and_the_first_row_opens_it(self):
        pairs = self.worlds()

        def flow(world, window, game):
            game.SetHPTargetBoard(BOSS, 64)
            game.BINARY_UpdateBossDamageCount(11, BOSS, 30000)
            game.BINARY_UpdateBossDamageCount(12, BOSS, 18000)
            game.BINARY_UpdateBossDamageCount(13, BOSS, 12000)
            game.SetHPTargetBoard(BOSS, 20)
        state = self.both(pairs, flow)
        self.assertEqual(state[1:5], ("Green Dragon", "", "20%", "low"))
        self.assertEqual([row[:5] for row in state[5]], [("1.", "Alpha", "Damage: 30.0K(50.0%)", 380, False),
                                                         ("2.", "Me", "Damage: 18.0K(30.0%)", 228, True),
                                                         ("3.", "Gamma", "Damage: 12.0K(20.0%)", 152, False)])

    def test_a_new_target_closes_it_on_both_and_the_next_row_opens_it_again(self):
        pairs = self.worlds()

        def flow(world, window, game):
            game.SetHPTargetBoard(BOSS, 90)
            game.BINARY_UpdateBossDamageCount(11, BOSS, 100)
            game.SetHPTargetBoard(501, 50)
        self.assertEqual(self.both(pairs, flow), (False,))

        def again(world, window, game):
            game.BINARY_UpdateBossDamageCount(14, BOSS, 7)
        state = self.both(pairs, again)
        self.assertEqual(state[5], [("1.", "Wolf", "Damage: 0.0K(100.0%)", 380, False,
                                     "d:/ymir work/ui/game/windows/face_shaman.sub")])

    def test_close_target_board_and_the_close_button_close_both(self):
        pairs = self.worlds()

        def flow(world, window, game):
            game.BINARY_UpdateBossDamageCount(11, BOSS, 100)
            game.CloseTargetBoard()
        self.assertEqual(self.both(pairs, flow), (False,))

        def reopen(world, window, game):
            game.BINARY_UpdateBossDamageCount(11, BOSS, 200)
            if world.nui_on:
                bw.board_of(window).fire("close_press", 0)
            else:
                window.GetChild("exit").click()
        self.assertEqual(self.both(pairs, reopen), (False,))
        for world, window, _ in pairs:
            self.assertEqual(window.playerList, {})

    def test_hp_numbers_show_when_given(self):
        pairs = self.worlds()

        def flow(world, window, game):
            game.BINARY_UpdateBossDamageCount(11, BOSS, 100)
            window.AddHPInfo(BOSS, 45, 1234567, 5000000)
        state = self.both(pairs, flow)
        self.assertEqual(state[2:5], ("1.234.567 / 5.000.000", "45%", "mid"))


class NovaUI(DamageTest):
    def test_the_updated_row_flashes_and_each_update_restarts_it(self):
        world, window, game = self.worlds()[1]
        with world, bw.quiet():
            game.BINARY_UpdateBossDamageCount(11, BOSS, 10)
            game.BINARY_UpdateBossDamageCount(12, BOSS, 5)
        rows = bw.board_of(window).model["rows"]
        self.assertEqual([row["flash"] for row in rows], [0, 1], "only the updated row")
        with world, bw.quiet():
            game.BINARY_UpdateBossDamageCount(12, BOSS, 6)
        self.assertEqual([row["flash"] for row in bw.board_of(window).model["rows"]], [0, 2],
                         "the other class: its animation starts again")

    def test_no_python_per_frame_and_the_legacy_window_stays_0_by_0(self):
        world, window, game = self.worlds()[1]
        self.assertIsNone(window.OnUpdate)
        self.assertIsNone(window.OnRender)
        with world, bw.quiet():
            game.BINARY_UpdateBossDamageCount(11, BOSS, 10)
        self.assertEqual(window.size, (0, 0))
        self.assertEqual(window.nui_size, (392, 65 + 25))

    def test_the_board_is_made_at_show_and_goes_at_hide(self):
        world, window, game = self.worlds()[1]
        self.assertIsNone(bw.board_of(window))
        with world, bw.quiet():
            game.BINARY_UpdateBossDamageCount(11, BOSS, 10)
        board = bw.board_of(window)
        self.assertIsNotNone(board)
        self.assertEqual(window._place, ((1600 - 720) // 2, 100), "legacy's Open place, in dp at scale 1")
        with world:
            board.fire("board_press", 0)
            window.Close()
        self.assertIsNone(bw.board_of(window))

    def test_a_document_that_fails_keeps_the_legacy_window(self):
        world = bw.World(nui_on=True, failing=[DOCUMENT])
        window = world.damage_count()
        self.assertFalse(getattr(window, "NUI_FACADE", False))
        world = bw.World(nui_on=True, windows="+hud,-damage-count")
        self.assertFalse(getattr(world.damage_count(), "NUI_FACADE", False))

    def test_every_fixture_has_every_model_key(self):
        world, window, game = self.worlds()[1]
        keys = set(window.nui_model())
        with world, bw.quiet():
            game.BINARY_UpdateBossDamageCount(11, BOSS, 10)
        row_keys = set(bw.board_of(window).model["rows"][0])
        self.assertEqual(row_keys, {"no", "name", "damage", "face", "own", "width", "color", "flash"})
        for name in sorted(os.listdir(WINDOW_DIR)):
            if not name.endswith(".fixture.json"):
                continue
            with open(os.path.join(WINDOW_DIR, name), encoding="utf-8") as handle:
                model = json.load(handle)["damage_count"]
            self.assertEqual(set(model), keys, name)
            for row in model["rows"]:
                self.assertEqual(set(row), row_keys, name)


if __name__ == "__main__":
    unittest.main()
