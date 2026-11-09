"""Tests of the select skill window (NOVA-37): legacy's assets/root/uiselectskill.py and the
NovaUI facade assets/root/nui_select_skill.py on the same stand-in world (nui_w4_world.World).

Each flow runs on both windows and what each does must be the same: the model preview's calls
(the dressed model, the camera, a hover's motion without a new model), the tooltip calls, the
chat command of a pick. The NovaUI side also checks what the board shows and that no Python runs
per frame. Run from tools/: python3 -B -m unittest nui_select_skill_test"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dungeon_timer_support as dts  # noqa: E402
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402

ROOT = os.path.dirname(HERE)
WINDOW_DIR = os.path.join(ROOT, "assets", "nui", "nui", "windows", "select-skill")
FLAGS = "+select-skill"
RACE = 3      # any race
JOB_WARRIOR, JOB_ASSASSIN = 0, 1
HAIR_VNUM = 75014
HAIR_PART = 21
SASH_VNUM = 85006


class Preview(object):
    """The client's modelpreview module (PythonModelPreviewModule.cpp), recording its calls."""

    def __init__(self):
        self.calls = []

    def Select(self, name, race, *gear):
        self.calls.append(("Select", name, race) + gear)
        return 1

    def SetEye(self, name, y, z):
        self.calls.append(("SetEye", name, y, z))

    def SetSkillMotion(self, name, motion):
        self.calls.append(("SetSkillMotion", name, motion))

    def Show(self, name, show):
        self.calls.append(("Show", name, bool(show)))

    def Clear(self, name):
        self.calls.append(("Clear", name))


class Tooltip(object):
    def __init__(self, world):
        self.world = world

    def SetSkillOnlyName(self, slot, skill, grade):
        self.world.log(("tooltip", slot, skill, grade))

    def HideToolTip(self):
        self.world.log(("hide_tooltip",))


class World(w4.World):
    def __init__(self, nui_on, job=JOB_WARRIOR, preview=True, costumes=True):
        self.preview = Preview() if preview else None
        self.events = []
        self.job = job

        def setup(game):
            dts.install(game)
            if preview:
                game.modules["modelpreview"] = self.preview
                game.modules["ui"].RenderTarget = dts.RenderTarget
            item = game.modules["item"]
            player = game.modules["player"]
            localeInfo = game.modules["localeInfo"]
            uiScriptLocale = game.modules["uiScriptLocale"]
            uiScriptLocale.SELECT_CLASS = "Choose your class"
            names = ("SKILL_GROUP_WARRIOR_1", "SKILL_GROUP_WARRIOR_2", "SKILL_GROUP_ASSASSIN_1", "SKILL_GROUP_ASSASSIN_2",
                     "SKILL_GROUP_SURA_1", "SKILL_GROUP_SURA_2", "SKILL_GROUP_SHAMAN_1", "SKILL_GROUP_SHAMAN_2")
            for name in names:
                setattr(localeInfo, name, name.rsplit("_", 2)[1].title() + " " + name[-1])
            support.define(player, "GetJob", lambda: self.job)
            support.define(player, "GetRace", lambda: RACE)
            item.COSTUME_SLOT_HAIR, item.COSTUME_SLOT_SASH = 1000, 1001
            worn = {1000: HAIR_VNUM, 1001: SASH_VNUM} if costumes else {}
            support.define(player, "GetItemIndex", lambda slot: worn.get(slot, 0))
            self.selected = []
            def select_item(vnum):
                self.selected.append(vnum)
            item.SelectItem = select_item
            item.GetValue = lambda index: HAIR_PART if index == 3 else 0
            skill = game.modules.setdefault("skill", support.module("skill") if hasattr(support, "module") else game.modules.get("skill"))
            skill.GetIconImageFileNameNew = lambda index, grade: "d:/icon/%d.tga" % index
        w4.World.__init__(self, nui_on, windows=FLAGS, setup=setup, modules=w4.TRADE_MODULES)
        with self.game, w4.quiet():
            self.game.load("uiSelectSkill", "uiselectskill.py")
            if nui_on:
                self.game.load("nui_select_skill", "nui_select_skill.py")
        self.tooltip = Tooltip(self)

    def log(self, entry):
        self.events.append(entry)

    def window(self, load=True):
        window = self.make("select-skill", "uiSelectSkill", "SelectSkillWindow", "nui_select_skill.SelectSkillWindow")
        with self.game, w4.quiet():
            window.LoadWindow()
            window.SetSkillToolTip(self.tooltip)
        return window

    def chat_commands(self):
        return [args[0] for name, args in self.game.log if name == "net.SendChatPacket"]


def opened(nui_on, **kwargs):
    world = World(nui_on, **kwargs)
    window = world.window()
    with world.game, w4.quiet():
        window.Open()
    return world, window


class Both(unittest.TestCase):
    def run_both(self, flow, **kwargs):
        outcomes = []
        for nui_on in (False, True):
            world, window = opened(nui_on, **kwargs)
            mark = len(world.preview.calls) if world.preview else 0
            ev = len(world.events)
            with world.game, w4.quiet():
                flow(world, window, nui_on)
            outcomes.append((list(world.preview.calls[mark:]) if world.preview else [], world.events[ev:],
                             world.chat_commands(), bool(window.IsShow())))
        self.assertEqual(outcomes[1], outcomes[0])
        return outcomes[0]


def hover(window, nui_on, group, slot):
    if nui_on:
        w4.press(window, "cell_over", group, slot)
    else:
        (window.OverInItem1 if group == 1 else window.OverInItem2)(slot)


def hover_out(window, nui_on, group, slot):
    if nui_on:
        w4.press(window, "cell_out", group, slot)
    else:
        window.OverOutItem()


def pick(window, nui_on, group):
    if nui_on:
        w4.press(window, "pick_press", group, 0)
    else:
        (window.Button1 if group == 1 else window.Button2).event(*(window.Button1 if group == 1 else window.Button2).eventArgs)


class Flows(Both):
    def test_open_dresses_the_model_at_olds_camera_and_starts_idle(self):
        world, window = opened(False)
        self.assertEqual(world.preview.calls, [
            ("Select", "select_skill", RACE, 11289, 189, HAIR_PART, SASH_VNUM),
            ("SetEye", "select_skill", -1200, 600),
            ("SetSkillMotion", "select_skill", 0),
            ("Show", "select_skill", True)])

    def test_open_twice_does_not_make_the_model_again(self):
        def flow(world, window, nui_on):
            mark = sum(1 for c in world.preview.calls if c[0] == "Select")
            window.Open()
            self.assertEqual(sum(1 for c in world.preview.calls if c[0] == "Select"), mark)
        self.run_both(flow)

    def test_hovering_plays_the_warrior_rows_motion_slot_without_a_new_model(self):
        def flow(world, window, nui_on):
            hover(window, nui_on, 2, 0)
            hover_out(window, nui_on, 2, 0)
        calls, events, _, _ = self.run_both(flow)
        self.assertEqual(calls, [("SetSkillMotion", "select_skill", 16), ("Show", "select_skill", True),
                                 ("SetSkillMotion", "select_skill", 0), ("Show", "select_skill", True)])
        self.assertEqual(events, [("tooltip", 0, 16, 0), ("hide_tooltip",)])

    def test_an_assassins_second_group_changes_the_weapon_on_hover(self):
        def flow(world, window, nui_on):
            hover(window, nui_on, 2, 3)
        calls, events, _, _ = self.run_both(flow, job=JOB_ASSASSIN)
        self.assertEqual(calls, [
            ("Select", "select_skill", RACE, 41003, 40103, HAIR_PART, SASH_VNUM),
            ("SetEye", "select_skill", -1200, 600),
            ("SetSkillMotion", "select_skill", 19),
            ("Show", "select_skill", True)])
        self.assertEqual(events[0][2], 49, "the tooltip shows the job's own skill")

    def test_a_pick_sends_the_command_and_closes(self):
        for group in (1, 2):
            def flow(world, window, nui_on):
                pick(window, nui_on, group)
            with self.subTest(group=group):
                calls, _, commands, shown = self.run_both(flow)
                self.assertEqual(commands, ["/select_skill %d" % group])
                self.assertFalse(shown)
                self.assertEqual(calls[-1], ("Show", "select_skill", False))

    def test_escape_closes_without_a_pick(self):
        def flow(world, window, nui_on):
            self.assertTrue(window.OnPressEscapeKey())
        calls, _, commands, shown = self.run_both(flow)
        self.assertEqual(commands, [])
        self.assertFalse(shown)
        self.assertEqual(calls[-1], ("Show", "select_skill", False))

    def test_destroy_clears_the_preview(self):
        world, window = opened(False)
        with world.game, w4.quiet():
            window.Destroy()
        self.assertEqual(world.preview.calls[-1], ("Clear", "select_skill"))

    def test_no_costumes_give_no_hair_or_sash_and_no_stale_item(self):
        world, window = opened(False, costumes=False)
        self.assertEqual(world.preview.calls[0], ("Select", "select_skill", RACE, 11289, 189, 0, 0))
        self.assertNotIn(0, world.selected, "item.SelectItem(0) reads the last selected item")

    def test_a_client_without_previews_still_works(self):
        for nui_on in (False, True):
            with self.subTest(nui_on=nui_on):
                world, window = opened(nui_on, preview=False)
                self.assertTrue(window.IsShow())

    def test_every_job_has_two_rows_of_six_and_gear(self):
        world = World(False)
        table = world.game.modules["uiSelectSkill"].SKILL_INDEX_DICT
        self.assertEqual(sorted(table), [0, 1, 2, 3])
        for job, rows in table.items():
            with self.subTest(job=job):
                self.assertEqual(len(rows[1]), 6)
                self.assertEqual(len(rows[2]), 6)
                self.assertEqual(len(rows[3]), 2)


class Wiring(unittest.TestCase):
    """The server command reaches the window (game.py's table, the Interface)."""

    def read(self, name):
        with open(os.path.join(ROOT, "assets", "root", name), encoding="utf-8", errors="replace") as handle:
            return handle.read()

    def test_the_server_command_opens_the_window(self):
        game = self.read("game.py")
        self.assertIn('"OpenSelectSkillWindow"\t: self.OpenSelectSkillWindow,', game)
        self.assertIn("self.interface.OpenSelectSkillWindow()", game)
        interface = self.read("interfacemodule.py")
        self.assertIn("self.wndSelectSkill.Open()", interface)
        self.assertIn('nui_windows.make("select-skill", uiSelectSkill.SelectSkillWindow, "nui_select_skill.SelectSkillWindow")', interface)
        self.assertIn("self.wndSelectSkill.SetSkillToolTip(self.tooltipSkill)", interface)


class Board(unittest.TestCase):
    def test_no_python_runs_per_frame(self):
        world, window = opened(True)
        self.assertIsNone(window.OnUpdate)

    def test_the_board_shows_both_groups_and_the_view(self):
        world, window = opened(True)
        model = w4.board(window).model
        self.assertEqual([g["group"] for g in model["groups"]], [1, 2])
        self.assertEqual(model["groups"][0]["name"], "Warrior 1")
        self.assertEqual([c["icon"] != "" for c in model["groups"][1]["cells"]], [True] * 6)
        self.assertTrue(model["model_view"])
        with world.game, w4.quiet():
            window.Close()
        self.assertFalse(w4.board(window) is not None and w4.board(window).model["model_view"])

    def test_no_preview_means_no_view(self):
        world, window = opened(True, preview=False)
        self.assertFalse(w4.board(window).model["model_view"])

    def test_every_fixture_has_every_model_key(self):
        world, window = opened(True)
        keys = set(w4.board(window).model)
        for name in ("select-skill.fixture.json", "select-skill.noview.fixture.json"):
            with self.subTest(fixture=name):
                with open(os.path.join(WINDOW_DIR, name), encoding="utf-8") as handle:
                    fixture = json.load(handle)["select_skill"]
                self.assertEqual(set(fixture), keys)

    def test_hide_before_the_legacy_init_survives(self):
        world = World(True)
        cls = world.game.modules["nui_select_skill"].SelectSkillWindow
        with world.game, w4.quiet():
            bare = cls.__new__(cls)
            bare.nui_begin()
            bare.Hide()
            bare.nui_discard()


if __name__ == "__main__":
    unittest.main()
