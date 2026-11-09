"""Tests for the NovaUI boss info panel (assets/root/nui_boss_info.py;
NOVA-27): python3 -B -m unittest nui_boss_info_test (from tools/).

Each flow runs on legacy's uibossinfo.BossInfoWindow and on the NovaUI
subclass, each in a world of its own (boss_windows_support.World, legacy
only or with the boss-info flag on), driven as the Interface drives them,
and what each does must match: the systemSetting calls (the expanded flag),
whether the panel shows, the rows (name, alive or dead, their tops), the
collapsed state and the tooltip's lines at sampled instants (legacy's
tooltip refreshed by its OnUpdate; NovaUI's hint read from the model, its
respawn clock by the nui-countdown's rule from the end the facade wrote).
The NovaUI side also checks its board (made at show, gone at hide), that it
runs no Python per frame, its fixtures against the model and the lifecycle
of make()."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boss_windows_support as bw  # noqa: E402

DOCUMENT = "nui/windows/boss-info/boss-info.rml"
WINDOW_DIR = os.path.join(bw.ASSETS, "nui", "nui", "windows", "boss-info")
NOW = 1700000000


def remaining(end, now):
    """nui-countdown (no round="up"): whole seconds left, 0 at the end."""
    left = int(end - now)
    return left if left > 0 else 0


def legacy_lines(world, window, index):
    with world:
        window.rows[index].OnMouseOverIn()
        lines = list(window.toolTip.lines)
        window.rows[index].OnMouseOverOut()
    return lines


def novaui_lines(world, window, index):
    board = bw.board_of(window)
    row = board.model["rows"][index]
    locale = world.game.modules["localeInfo"]
    lines = []
    if row["level"]:
        lines.append(row["level"])
    lines.append(row["state"])
    if row["respawn"]:
        left = remaining(row["respawn_end"], world.game.state.now)
        if left > 0:
            text = " ".join(part for part in (board.model["respawn_before"], locale.RTSecondToDHMS(left),
                                               board.model["respawn_after"]) if part)
            lines.append(text)
    return lines


def shown(world, window):
    """What the panel shows: (shown, collapsed, [(name, alive, top)])."""
    if world.nui_on:
        board = bw.board_of(window)
        if board is None or not window.IsShow():
            return (False, None, [])
        model = board.model
        return (True, model["collapsed"], [(row["name"], row["alive"], row["top"]) for row in model["rows"]])
    if not window.IsShow():
        return (False, None, [])
    return (True, bool(window.expandButton.shown),
            [(row.boss.GetBossName(), bool(row.boss.IsAlive()), row.position[1]) for row in window.rows])


class BossInfoTest(unittest.TestCase):
    def worlds(self, **kwargs):
        worlds = []
        for nui_on in (False, True):
            world = bw.World(nui_on=nui_on, **kwargs)
            world.game.timestamp = NOW
            worlds.append((world, world.boss_info()))
        return worlds

    def load(self, worlds, bosses):
        for world, window in worlds:
            with world, bw.quiet():
                window.ClearBossInfo()
                for boss in bosses:
                    window.AddBossInfo(*boss)
                window.BossInfoLoadComplete()

    def settings(self, world):
        return world.calls("systemSetting.SetIsBossInfoExpandend")


class Differential(BossInfoTest):
    def test_the_novaui_window_is_the_facade_and_legacy_is_legacy(self):
        (legacy_world, legacy), (nui_world, novaui) = self.worlds()
        self.assertEqual(type(legacy).__name__, "BossInfoWindow")
        self.assertFalse(getattr(legacy, "NUI_FACADE", False))
        self.assertTrue(novaui.NUI_FACADE)
        self.assertIsInstance(novaui, nui_world.uiBossInfo.BossInfoWindow)

    def test_a_list_shows_the_same_rows_and_hides_on_an_empty_one(self):
        worlds = self.worlds()
        self.load(worlds, [(997, 1, 0), (998, 0, NOW + 125), (2091, 1, 0)])
        (legacy_world, legacy), (nui_world, novaui) = worlds
        self.assertEqual(shown(nui_world, novaui), shown(legacy_world, legacy))
        self.assertEqual(shown(nui_world, novaui)[2][1], ("Abomination", False, 56))
        self.load(worlds, [])
        self.assertEqual(shown(nui_world, novaui), shown(legacy_world, legacy))
        self.assertEqual(shown(nui_world, novaui), (False, None, []))
        self.assertIsNone(bw.board_of(novaui), "the document goes with the panel")

    def test_the_toggle_writes_the_same_flag_and_collapses_the_same_way(self):
        worlds = self.worlds()
        self.load(worlds, [(997, 1, 0), (998, 1, 0)])
        (legacy_world, legacy), (nui_world, novaui) = worlds
        with legacy_world:
            legacy.minimizeButton.click()
        with nui_world:
            bw.board_of(novaui).fire("toggle_press", 0)
        self.assertEqual(self.settings(nui_world), self.settings(legacy_world))
        self.assertEqual(shown(nui_world, novaui), shown(legacy_world, legacy))
        self.assertTrue(shown(nui_world, novaui)[1])
        with legacy_world:
            legacy.expandButton.click()
        with nui_world:
            bw.board_of(novaui).fire("toggle_press", 0)
            bw.board_of(novaui).fire("toggle_press", 2)  # a right press does nothing
        self.assertEqual(self.settings(nui_world), self.settings(legacy_world))
        self.assertEqual(shown(nui_world, novaui), shown(legacy_world, legacy))
        self.assertFalse(shown(nui_world, novaui)[1])

    def test_a_collapsed_flag_loads_collapsed_on_both(self):
        worlds = self.worlds(expanded=0)
        self.load(worlds, [(999, 0, 0)])
        (legacy_world, legacy), (nui_world, novaui) = worlds
        self.assertEqual(shown(nui_world, novaui), shown(legacy_world, legacy))
        self.assertTrue(shown(nui_world, novaui)[1])
        self.assertTrue(bw.board_of(novaui).model["single"])

    def test_the_tooltip_lines_match_at_every_sampled_instant(self):
        worlds = self.worlds()
        self.load(worlds, [(997, 1, 0), (998, 0, NOW + 125)])
        (legacy_world, legacy), (nui_world, novaui) = worlds
        for step in (0, 5, 60, 59, 1, 30):
            for world, _ in worlds:
                world.clock(step)
            for index in (0, 1):
                self.assertEqual(novaui_lines(nui_world, novaui, index), legacy_lines(legacy_world, legacy, index),
                                 "row %d at +%d" % (index, nui_world.game.timestamp - NOW))
        self.assertEqual(novaui_lines(nui_world, novaui, 1), ["Level 120", "Dead"])

    def test_the_countdown_end_republishes_the_rows(self):
        worlds = self.worlds()
        self.load(worlds, [(998, 0, NOW + 10)])
        nui_world, novaui = worlds[1]
        self.assertTrue(bw.board_of(novaui).model["rows"][0]["respawn"])
        nui_world.clock(10)
        with nui_world:
            bw.board_of(novaui).fire("respawned")
        self.assertFalse(bw.board_of(novaui).model["rows"][0]["respawn"])

    def test_a_wide_name_widens_both(self):
        worlds = self.worlds()
        self.load(worlds, [(1093, 1, 0), (997, 1, 0)])
        (legacy_world, legacy), (nui_world, novaui) = worlds
        self.assertEqual(legacy.board.size[0], 185)
        self.assertTrue(bw.board_of(novaui).model["wide"])
        self.assertEqual(bw.board_of(novaui).model["height"], legacy.board.size[1])


class NovaUI(BossInfoTest):
    def test_no_python_per_frame_and_the_legacy_window_stays_0_by_0(self):
        world = bw.World(nui_on=True)
        window = world.boss_info()
        self.assertIsNone(window.OnUpdate)
        self.assertIsNone(window.OnRender)
        self.load([(world, window)], [(997, 1, 0), (998, 1, 0), (999, 1, 0)])
        self.assertEqual(window.size, (0, 0), "SetSize only records")
        self.assertEqual(window.nui_size, (163, 151))

    def test_a_document_that_fails_keeps_the_legacy_window(self):
        world = bw.World(nui_on=True, failing=[DOCUMENT])
        window = world.boss_info()
        self.assertFalse(getattr(window, "NUI_FACADE", False))
        self.assertEqual(world.nui_windows.DECISIONS["boss-info"][:6], "legacy")

    def test_the_flag_off_makes_the_legacy_window(self):
        world = bw.World(nui_on=True, windows="+hud,-boss-info")
        self.assertFalse(getattr(world.boss_info(), "NUI_FACADE", False))

    def test_destroy_discards_the_board(self):
        world = bw.World(nui_on=True)
        window = world.boss_info()
        self.load([(world, window)], [(997, 1, 0)])
        self.assertIsNotNone(bw.board_of(window))
        with world:
            window.Destroy()
        self.assertIsNone(window.demand)

    def test_every_fixture_has_every_model_key(self):
        world = bw.World(nui_on=True)
        window = world.boss_info()
        keys = set(window.nui_model())
        row_keys = {"name", "level", "state", "alive", "respawn", "respawn_end", "top"}
        self.load([(world, window)], [(998, 0, NOW + 5)])
        self.assertEqual(set(bw.board_of(window).model["rows"][0]), row_keys)
        for name in sorted(os.listdir(WINDOW_DIR)):
            if not name.endswith(".fixture.json"):
                continue
            with open(os.path.join(WINDOW_DIR, name), encoding="utf-8") as handle:
                model = json.load(handle)["boss_info"]
            self.assertEqual(set(model), keys, name)
            for row in model["rows"]:
                self.assertEqual(set(row), row_keys, name)


if __name__ == "__main__":
    unittest.main()
