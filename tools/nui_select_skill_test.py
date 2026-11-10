"""Tests of the select skill window (NOVA-37): legacy's assets/root/uiselectskill.py and the
NovaUI facade assets/root/nui_select_skill.py on the same stand-in world (nui_w4_world.World).

Each flow runs on both windows and what each does must be the same: the model preview's calls
(the dressed model, the camera, a hover's motion without a new model), the tooltip calls, the
chat command of a pick. The NovaUI side also checks what the board shows and that no Python runs
per frame. Run from tools/: python3 -B -m unittest nui_select_skill_test"""
import json
import os
import re
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
SKILLDESC = os.path.join(ROOT, "assets", "locale", "locale", "en", "skilldesc.txt")
LOCALES = os.path.join(ROOT, "assets", "locale", "locale")
# The design's draft copy (D-orbit.dc.html JOBS), Eddy to edit: the new locale keys.
PLAYS = {
    "SELECT_SKILL_PLAYS_WARRIOR_1": "Fast sword attacks on several enemies, with Berserk and Aura of the Sword for damage.",
    "SELECT_SKILL_PLAYS_WARRIOR_2": "A sturdy front line: splash strikes, knockdowns and Strong Body for defense.",
    "SELECT_SKILL_PLAYS_ASSASSIN_1": "Daggers up close: strike from behind or from stealth, then poison the crowd.",
    "SELECT_SKILL_PLAYS_ASSASSIN_2": "An archer: volleys of fire and poison arrows at range, Feather Walk for speed.",
    "SELECT_SKILL_PLAYS_SURA_1": "A cursed blade up close: Enchanted Blade, dark armor, and Fear to weaken foes.",
    "SELECT_SKILL_PLAYS_SURA_2": "A dark caster: long-range dark and flame spells, with Dark Protection.",
    "SELECT_SKILL_PLAYS_SHAMAN_1": "Dragon spells at range, plus Blessing, Reflect and Dragon's Strength for the party.",
    "SELECT_SKILL_PLAYS_SHAMAN_2": "Lightning at range, plus Cure, Swiftness and Attack Up for the party.",
}
NEW_KEYS = dict(PLAYS, SELECT_SKILL_CHOOSE="Choose %s", SELECT_SKILL_IDLE="Idle",
                SELECT_SKILL_IDLE_HINT="Hover a skill or a side")


def skilldesc():
    """{vnum: (name, tag, icon file)} from the en skilldesc.txt, as the client's skill module reads it."""
    table = {}
    with open(SKILLDESC, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            cols = line.rstrip("\n").split("\t")
            if len(cols) > 13 and cols[0].isdigit():
                table[int(cols[0])] = (cols[2], cols[6], "d:/ymir work/ui/skill/%s/%s_01.sub" % (cols[1].lower(), cols[12]))
    return table


SKILLS = skilldesc()


def ring_point(group, count, k):
    """The design's pt(): center 220, 220, radius 192; group 1 from 120 to 240 degrees, group 2 from
    60 to -60, spread evenly (D-orbit.dc.html renderVals)."""
    import math
    step = 120.0 / (count - 1)
    deg = 120 + k * step if group == 1 else 60 - k * step
    rad = deg * math.pi / 180
    return (int(math.floor(220 + 192 * math.cos(rad) + 0.5)), int(math.floor(220 - 192 * math.sin(rad) + 0.5)))
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

    def SetSkillCycle(self, name, entries):
        self.calls.append(("SetSkillCycle", name, list(entries)))

    def Show(self, name, show):
        self.calls.append(("Show", name, bool(show)))

    def Clear(self, name):
        self.calls.append(("Clear", name))


class OldPreview(Preview):
    """A client from before the idle casting: no SetSkillCycle (getattr finds None)."""
    SetSkillCycle = None


def warrior_cycle(body=11289, weapon=189):
    """Every skill of both groups (motion slots 1 to 6, 16 to 21), in the row's gear."""
    return [(motion, body, weapon) for motion in (1, 2, 3, 4, 5, 6, 16, 17, 18, 19, 20, 21)]


class Tooltip(object):
    def __init__(self, world):
        self.world = world

    def SetSkillOnlyName(self, slot, skill, grade):
        self.world.log(("tooltip", slot, skill, grade))

    def HideToolTip(self):
        self.world.log(("hide_tooltip",))


class World(w4.World):
    def __init__(self, nui_on, job=JOB_WARRIOR, preview=True, costumes=True, old_client=False):
        self.preview = (OldPreview() if old_client else Preview()) if preview else None
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
            # The client's skill data: skills 6, 21, 36 and 51 do not exist in NEW (no skilldesc line).
            skill.GetIconImageFileNameNew = lambda index, grade: SKILLS[index][2] if index in SKILLS else ""
            def skill_name(index, grade=-1):
                if index not in SKILLS:
                    raise RuntimeError("skill.GetSkillName - Failed to find skill by %d" % index)
                return SKILLS[index][0]
            def skill_condition(index, condition):
                if index not in SKILLS:
                    raise RuntimeError("skill.GetSkillConditionDescription() - Failed to find skill by %d" % index)
                return SKILLS[index][1] if condition == 0 else None
            skill.GetSkillName = skill_name
            skill.GetSkillConditionDescription = skill_condition
            for key, text in NEW_KEYS.items():
                setattr(uiScriptLocale, key, text)
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
        w4.fire(window, "cell_over", group, slot)
    else:
        (window.OverInItem1 if group == 1 else window.OverInItem2)(slot)


def hover_out(window, nui_on, group, slot):
    if nui_on:
        w4.fire(window, "cell_out", group, slot)
        leave(window)
    else:
        window.OverOutItem()


def leave(window):
    """The pointer leaves the content area: RmlUi's mouseout on the content element itself."""
    board = w4.board(window)
    board.handlers[("select-skill-content", "mouseout")]({"type": "mouseout", "target_id": "select-skill-content"})


def pick(window, nui_on, group):
    if nui_on:
        w4.press(window, "pick_press", group, 0)
    else:
        (window.Button1 if group == 1 else window.Button2).event(*(window.Button1 if group == 1 else window.Button2).eventArgs)


class Flows(Both):
    def test_open_dresses_the_model_at_olds_camera_and_starts_idle(self):
        world, window = opened(False)
        self.assertEqual(world.preview.calls, [
            ("SetSkillCycle", "select_skill", warrior_cycle()),
            ("Select", "select_skill", RACE, 11289, 189, HAIR_PART, SASH_VNUM),
            ("SetEye", "select_skill", -1200, 600),
            ("SetSkillMotion", "select_skill", 0),
            ("Show", "select_skill", True)])

    def test_open_twice_does_not_make_the_model_again(self):
        def flow(world, window, nui_on):
            mark = sum(1 for c in world.preview.calls if c[0] in ("Select", "SetSkillCycle"))
            window.Open()
            self.assertEqual(sum(1 for c in world.preview.calls if c[0] in ("Select", "SetSkillCycle")), mark)
        self.run_both(flow)

    def test_idle_casts_every_skill_of_both_groups_in_its_rows_gear(self):
        # Eddy: with no skill hovered, the preview casts the job's skills, one after another.
        for job, gear in ((JOB_WARRIOR, (11289, 189, 11289, 189)), (JOB_ASSASSIN, (41003, 40102, 41003, 40103))):
            with self.subTest(job=job):
                world, window = opened(False, job=job)
                cycle = world.preview.calls[0]
                self.assertEqual(cycle[:2], ("SetSkillCycle", "select_skill"))
                self.assertEqual(cycle[2], [(m, gear[0], gear[1]) for m in (1, 2, 3, 4, 5, 6)] +
                                 [(m, gear[2], gear[3]) for m in (16, 17, 18, 19, 20, 21)],
                                 "an assassin's second group is the bow's")

    def test_a_reopened_window_starts_its_cycle_again(self):
        def flow(world, window, nui_on):
            window.Close()
            window.Open()
        calls, _, _, shown = self.run_both(flow)
        self.assertTrue(shown)
        self.assertIn(("SetSkillCycle", "select_skill", warrior_cycle()), calls)

    def test_a_race_zero_warrior_gets_the_same_calls(self):
        # r39: bot12, race 0, saw an empty preview; the client took race 0 for "no model".
        world = World(False)
        world.game.modules["player"].GetRace = lambda: 0
        window = world.window()
        with world.game, w4.quiet():
            window.Open()
        self.assertIn(("Select", "select_skill", 0, 11289, 189, HAIR_PART, SASH_VNUM), world.preview.calls)

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
        self.assertEqual(world.preview.calls[1], ("Select", "select_skill", RACE, 11289, 189, 0, 0))
        self.assertNotIn(0, world.selected, "item.SelectItem(0) reads the last selected item")

    def test_a_client_without_previews_still_works(self):
        for nui_on in (False, True):
            with self.subTest(nui_on=nui_on):
                world, window = opened(nui_on, preview=False)
                self.assertTrue(window.IsShow())

    def test_a_client_without_the_cycle_still_shows_the_model(self):
        for nui_on in (False, True):
            with self.subTest(nui_on=nui_on):
                world, window = opened(nui_on, old_client=True)
                self.assertTrue(window.IsShow())
                self.assertEqual(world.preview.calls[0][0], "Select")

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


class Orbit(unittest.TestCase):
    """Direction D, Orbit (NOVA-37, Eddy's pick): the side panels, the ring and the caption."""

    def group(self, model, group):
        return model["groups"][group - 1]

    def test_each_side_lists_only_the_skills_that_exist_with_their_names_and_tags(self):
        for job, rows in ((JOB_WARRIOR, ((1, 2, 3, 4, 5), (16, 17, 18, 19, 20))),
                          (2, ((61, 62, 63, 64, 65, 66), (76, 77, 78, 79, 80, 81)))):
            with self.subTest(job=job):
                world, window = opened(True, job=job)
                model = w4.board(window).model
                for group, vnums in ((1, rows[0]), (2, rows[1])):
                    cells = self.group(model, group)["cells"]
                    self.assertEqual([c["index"] for c in cells], list(range(len(vnums))))
                    self.assertEqual([c["name"] for c in cells], [SKILLS[v][0].strip() for v in vnums])
                    self.assertEqual([c["tag"] for c in cells], [SKILLS[v][1].strip() for v in vnums])
                    self.assertEqual([c["icon"] for c in cells], [SKILLS[v][2] for v in vnums])

    def test_each_side_has_its_plays_like_line_and_choose_label(self):
        world, window = opened(True, job=JOB_ASSASSIN)
        model = w4.board(window).model
        self.assertEqual(self.group(model, 1)["plays"], PLAYS["SELECT_SKILL_PLAYS_ASSASSIN_1"])
        self.assertEqual(self.group(model, 2)["plays"], PLAYS["SELECT_SKILL_PLAYS_ASSASSIN_2"])
        self.assertEqual(self.group(model, 1)["choose"], "Choose Assassin 1")
        self.assertEqual(self.group(model, 2)["choose"], "Choose Assassin 2")

    def test_it_opens_idle(self):
        world, window = opened(True)
        model = w4.board(window).model
        self.assertEqual((model["active_group"], model["hover_group"], model["hover_slot"]), (0, 0, -1))
        self.assertEqual((model["caption_name"], model["caption_tag"]), ("", ""))

    def test_a_skill_hover_lights_it_sets_the_caption_and_its_side_and_casts_it(self):
        world, window = opened(True)
        mark = len(world.preview.calls)
        with world.game, w4.quiet():
            w4.fire(window, "cell_over", 1, 4)
        model = w4.board(window).model
        self.assertEqual((model["active_group"], model["hover_group"], model["hover_slot"]), (1, 1, 4))
        self.assertEqual((model["caption_name"], model["caption_tag"]), ("Dash", "Powerful Splash Attack"))
        self.assertIn(("SetSkillMotion", "select_skill", 5), world.preview.calls[mark:])
        self.assertEqual(world.events[-1], ("tooltip", 4, 5, 0))

    def test_a_side_hover_makes_its_group_active_without_casting(self):
        world, window = opened(True)
        mark = len(world.preview.calls)
        with world.game, w4.quiet():
            w4.fire(window, "side_over", 2)
        model = w4.board(window).model
        self.assertEqual((model["active_group"], model["hover_group"]), (2, 0))
        self.assertEqual(world.preview.calls[mark:], [])

    def test_leaving_a_skill_keeps_it_until_the_pointer_leaves_the_content(self):
        world, window = opened(True)
        with world.game, w4.quiet():
            w4.fire(window, "cell_over", 2, 1)
            mark, events = len(world.preview.calls), len(world.events)
            w4.fire(window, "cell_out", 2, 1)
            self.assertEqual(world.preview.calls[mark:], [], "the preview keeps casting the skill")
            self.assertEqual(world.events[events:], [("hide_tooltip",)])
            self.assertEqual(w4.board(window).model["hover_slot"], 1)
            leave(window)
        model = w4.board(window).model
        self.assertEqual((model["active_group"], model["hover_group"], model["hover_slot"]), (0, 0, -1))
        self.assertEqual((model["caption_name"], model["caption_tag"]), ("", ""))
        self.assertEqual(world.preview.calls[mark:], [("SetSkillMotion", "select_skill", 0), ("Show", "select_skill", True)],
                         "back to the idle cycle")

    def test_a_child_leaving_inside_the_content_is_not_a_leave(self):
        world, window = opened(True)
        with world.game, w4.quiet():
            w4.fire(window, "cell_over", 1, 0)
            mark = len(world.preview.calls)
            w4.board(window).handlers[("select-skill-content", "mouseout")]({"type": "mouseout", "target_id": "select-skill-cell-1-0"})
        self.assertEqual(w4.board(window).model["hover_group"], 1)
        self.assertEqual(world.preview.calls[mark:], [])

    def test_a_closed_window_opens_idle_again(self):
        world, window = opened(True)
        with world.game, w4.quiet():
            w4.fire(window, "cell_over", 1, 0)
            window.Close()
            window.Open()
        model = w4.board(window).model
        self.assertEqual((model["active_group"], model["hover_group"], model["hover_slot"]), (0, 0, -1))

    def test_each_choose_button_picks_its_group(self):
        for group in (1, 2):
            with self.subTest(group=group):
                world, window = opened(True)
                with world.game, w4.quiet():
                    w4.press(window, "pick_press", group, 0)
                self.assertEqual(world.chat_commands(), ["/select_skill %d" % group])

    def test_the_ring_places_every_count_by_the_designs_math(self):
        with open(os.path.join(WINDOW_DIR, "select-skill.rcss"), encoding="utf-8") as handle:
            sheet = handle.read()
        rule = re.compile(r"\.select-skill__ring--(\d)\.select-skill__ring--n(\d) \.select-skill__cell--k(\d)\s*\{\s*left: (-?\d+)dp;\s*top: (-?\d+)dp;\s*\}")
        found = {(int(g), int(n), int(k)): (int(x), int(y)) for g, n, k, x, y in rule.findall(sheet)}
        expected = {(g, n, k): ring_point(g, n, k) for g in (1, 2) for n in range(2, 8) for k in range(n)}
        self.assertEqual(found, expected)

    def test_the_document_binds_two_to_seven_skills_a_side(self):
        with open(os.path.join(WINDOW_DIR, "select-skill.rml"), encoding="utf-8") as handle:
            document = handle.read()
        for group in (1, 2):
            for n in range(2, 8):
                self.assertIn('data-class-select-skill__ring--n%d="groups[%d].cells.size == %d"' % (n, group - 1, n), document)
        for k in range(7):
            self.assertIn('data-class-select-skill__cell--k%d="it_index == %d"' % (k, k), document)


class Copy(unittest.TestCase):
    """The design's draft copy as locale keys, English in all 17 locales (Eddy edits them)."""

    def test_every_locale_has_the_new_keys(self):
        locales = sorted(d for d in os.listdir(LOCALES) if os.path.isfile(os.path.join(LOCALES, d, "locale_interface.txt")))
        self.assertEqual(len(locales), 17)
        for locale in locales:
            with self.subTest(locale=locale):
                with open(os.path.join(LOCALES, locale, "locale_interface.txt"), "rb") as handle:
                    raw = handle.read()
                self.assertNotIn(b"\r\n", raw)
                self.assertTrue(raw.endswith(b"\n"))
                lines = dict(line.split("\t", 1) for line in raw.decode("utf-8").split("\n") if "\t" in line)
                for key, text in NEW_KEYS.items():
                    self.assertEqual(lines.get(key), text, key)


class Fixture(unittest.TestCase):
    """The goldens' warrior: five skills a side (6 and 21 do not exist), each its real icon and name."""

    def test_the_fixtures_show_the_warriors_real_skills(self):
        for name in ("select-skill.fixture.json", "select-skill.noview.fixture.json"):
            with self.subTest(fixture=name):
                with open(os.path.join(WINDOW_DIR, name), encoding="utf-8") as handle:
                    model = json.load(handle)["select_skill"]
                for group, vnums in ((0, (1, 2, 3, 4, 5)), (1, (16, 17, 18, 19, 20))):
                    cells = model["groups"][group]["cells"]
                    self.assertEqual([(c["icon"], c["name"], c["tag"]) for c in cells],
                                     [(SKILLS[v][2], SKILLS[v][0].strip(), SKILLS[v][1].strip()) for v in vnums])


class Board(unittest.TestCase):
    def test_no_python_runs_per_frame(self):
        world, window = opened(True)
        self.assertIsNone(window.OnUpdate)

    def test_the_board_shows_both_groups_and_the_view(self):
        world, window = opened(True)
        model = w4.board(window).model
        self.assertEqual([g["group"] for g in model["groups"]], [1, 2])
        self.assertEqual(model["groups"][0]["name"], "Warrior 1")
        self.assertEqual([c["index"] for c in model["groups"][1]["cells"]], [0, 1, 2, 3, 4],
                         "skill 21 does not exist: the warrior's second group has five")
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
