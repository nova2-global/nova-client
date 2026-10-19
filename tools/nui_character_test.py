"""Tests for the NovaUI character window (assets/root/nui_character.py, P15
spec 4.8): python3 -B -m unittest nui_character_test (from tools/).

Plain CPython over nui_game_support's stand-ins: install_wave3c_ui makes the
legacy uicharacter.CharacterWindow from its real uiscript, its slot windows a
model of CSlotWindow (LegacySkillSlotWindow: SetSlot's rule, the cooldown
store, the plus buttons), and loads the real playerSettingModule and emotion
modules over the skill, quest and emotion stand-ins. Each test drives a
legacy world and a NovaUI world with the same state through the same input
(the legacy slot windows' C++ events and buttons against the board's data
events) and compares:
- facade: the legacy class's methods with signatures its callers can use,
  make()'s protocol (the 3c engine, a load error falls back with one syserr
  line and no exception.Abort), the wiring line;
- model: every status text, every skill, support, emotion and quest cell
  (icon, label, cover, disabled cover, cooldown span, active state, plus
  button) equals what the legacy widgets show, today and at the
  foundation's limits;
- flows: P15 spec 4.5's rows, the same net, player, mouse controller, event,
  chat and tooltip calls in the same order;
- the cooldown store against CSlotWindow's rules, the quest clocks against
  legacy's text, one panel at a time, no per-frame Python, on demand, the
  fixtures."""
import contextlib
import inspect
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402

ROOT = support.ROOT
WINDOWS = os.path.normpath(os.path.join(support.support.HERE, "..", "assets", "nui", "nui", "windows"))
DOCUMENT = "nui/windows/character/character.rml"
NUITOOL = os.environ.get("NUITOOL") or shutil.which("nuitool")
P = dict(support.PLAYER_CONSTANTS)
P.update(support._client_values(support.WAVE3C_PLAYER_CONSTANTS, "player"))
SKILL_TYPE = support._client_values(support.WAVE3C_SKILL_CONSTANTS, "skill")
EFFECT_MODULES = ("net", "player", "mouse", "chat", "event", "snd", "ime")
# The facade (P15 spec 4.4, migration inventory 2.6 wndCharacter).
FACADE = ("ActEmotion", "Destroy", "GetState", "Hide", "IsShow", "OnActivateSkill", "OnDeactivateSkill", "OnUseSkill",
          "OverOutItem", "RefreshAlignment", "RefreshCharacter", "RefreshQuest", "RefreshSkill", "RefreshStatus",
          "SetSkillToolTip", "SetState", "SetTop", "Show", "SkillClearCoolTime", "Close", "OnPressEscapeKey",
          "SelectSkillGroup")
STATUS = (("Level_Value", "level"), ("Exp_Value", "exp"), ("RestExp_Value", "exp_rest"), ("HP_Value", "hp"),
          ("SP_Value", "sp"), ("STR_Value", "st"), ("DEX_Value", "dx"), ("HTH_Value", "ht"), ("INT_Value", "iq"),
          ("ATT_Value", "att"), ("DEF_Value", "def"), ("MATT_Value", "matt"), ("MDEF_Value", "mdef"),
          ("ASPD_Value", "aspd"), ("MSPD_Value", "mspd"), ("CSPD_Value", "cspd"), ("ER_Value", "er"))


def quiet():
    """The legacy window prints on every emotion."""
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def warrior(game, group=1, riding=None):
    """A level 99 warrior of a skill group: the server's skills by index
    (playerSettingModule.RegisterSkill puts them in their slots): grade 0
    level 1 and 17, a master (grade 1) toggle, a grand master (2), a perfect
    (3); the support skills; the riding skill when given (grade, level)."""
    game.race, game.skill_group, game.empire = 0, group, 1
    game.name, game.guild_name = "Kalinka", "Nova Riders"
    game.exp = 2147483647
    game.alignment = (1200, 2)
    game.skill_by_index = {
        1: {"grade": 0, "level": 1}, 2: {"grade": 0, "level": 17}, 3: {"grade": 1, "level": 5},
        4: {"grade": 2, "level": 9}, 5: {"grade": 3, "level": 1},
        16: {"grade": 1, "level": 3}, 17: {"grade": 0, "level": 7},
        122: {"grade": 0, "level": 2}, 124: {"grade": 0, "level": 7}, 121: {"grade": 0, "level": 0}}
    for index in (1, 2, 3, 4, 5, 16, 17, 18, 19, 20):
        game.skill_types[index] = SKILL_TYPE["SKILL_TYPE_ACTIVE"]
    for index in (121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131):
        game.skill_types[index] = SKILL_TYPE["SKILL_TYPE_SUPPORT"]
    for index in (137, 138, 139, 140):
        game.skill_types[index] = SKILL_TYPE["SKILL_TYPE_HORSE"]
    game.toggle_skills.add(3)
    if riding is not None:
        grade, level = riding
        game.skill_by_index[130] = {"grade": grade, "level": level}
        game.skill_by_index[137] = {"grade": 0, "level": 5}
    game.usable_skills.update((1, 2, 3, 4, 5, 16, 17, 122, 137, 138, 139))
    game.level_up.update({1: True, 2: True, 3: False, 4: False, 5: False, 16: True, 17: True})
    game.status.update({P["LEVEL"]: 99, P["NEXT_EXP"]: 3500000000, P["EXP"]: 2147483647, P["HP"]: 9876, P["MAX_HP"]: 99999,
                        P["SP"]: 1234, P["MAX_SP"]: 5555, P["ST"]: 90, P["DX"]: 61, P["HT"]: 75, P["IQ"]: 12,
                        P["ATT_MIN"]: 120, P["ATT_MAX"]: 180, P["ATT_BONUS"]: 5, P["ATTACKER_BONUS"]: 0, P["MAG_ATT"]: 40,
                        P["MIN_MAGIC_WEP"]: 2, P["MAX_MAGIC_WEP"]: 9, P["DEF_GRADE"]: 300, P["DEF_BONUS"]: 4, P["MAG_DEF"]: 77,
                        P["ATT_SPEED"]: 104, P["MOVING_SPEED"]: 150, P["CASTING_SPEED"]: 110, P["EVADE_RATE"]: 3,
                        P["STAT"]: 3, P["SKILL_ACTIVE"]: 2, P["SKILL_SUPPORT"]: 1, P["SKILL_HORSE"]: 0, 112: 1})
    game.quests = [
        {"name": "Biologist", "icon": "d:/ymir work/ui/game/quest/questicon/level_24.sub", "counter_name": "Teeth",
         "counter": 3, "clock_name": "Time left", "clock_end": 125.0, "index": 11},
        {"name": "Ring", "icon": "season1/icon/scroll_open.tga", "clock_name": "Time left", "clock_end": -5.0, "index": 12},
        {"name": "Letter", "icon": "", "index": 13}]
    game.emotion_icons.update(dict((index, "icon/action/e%d.tga" % index) for index in list(range(1, 19)) + [51, 52, 53]))


class World(object):
    """One world: a Game with the legacy character window and the NovaUI one
    loaded over its stand-ins, the character flag on when `nui_on`."""

    def __init__(self, nui_on, windows="+character", engine_3c=True, setup=warrior, limits=None):
        game = self.game = support.Game()
        support.install_wave2b_ui(game)
        support.install_wave3a_ui(game)
        support.install_wave3b_ui(game)
        game.modules["localeInfo"] = support.locale_info("en")
        support.install_wave3c_ui(game)
        game.modules["systemSetting"].GetUINuiWindows = lambda: windows if nui_on else ""
        if not engine_3c:
            game.modules["nuigame"].lack("QuestIconFileName")
        for name in ("networkModule", "interfaceModule"):
            game.put(name, types.ModuleType(name))
        game.load_standard()
        if setup is not None:
            setup(game)
        with quiet():
            game.load("uiCharacter", "uicharacter.py")
            for name in ("nui_limits", "nui_proxies", "nui_character"):
                game.load(name, name + ".py")
        if limits is not None:
            game.loaded["nui_limits"].use(limits)
        self.nui_windows = game.loaded["nui_windows"]
        self.nui_on = nui_on

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def m(self, name):
        return self.game.loaded[name]

    @property
    def mouse(self):
        return self.m("mouseModule").mouseController

    def mark(self):
        return len(self.game.log)

    def effects_since(self, mark):
        return [(name, args) for name, args in self.game.log[mark:]
                if name.split(".", 1)[0] in EFFECT_MODULES and not support.is_getter(name)]

    def make(self, refresh=True):
        """Interface.__MakeWindows' character window (interfacemodule.py:186),
        its skill tooltip, and the C++'s refreshes at the game's start."""
        game = self.game
        with game, quiet():
            # The loading phase registers the skills first (introloading.py:257).
            self.m("playerSettingModule").RegisterSkill(game.race, game.skill_group, game.empire)
            window = self.nui_windows.make("character", self.m("uiCharacter").CharacterWindow,
                                           "nui_character.CharacterWindow")
            window.SetSkillToolTip(game.modules["uiToolTip"].SkillToolTip())
            if refresh:
                window.RefreshCharacter()
                window.RefreshStatus()
                window.RefreshSkill()
                window.RefreshQuest()
        return window

    def open(self, state="STATUS", refresh=True):
        """Interface.OpenCharacterWindowWithState (interfacemodule.py:989-993)."""
        window = self.make(refresh)
        with self.game, quiet():
            window.SetState(state)
            window.Show()
            window.SetTop()
        return window


def board(window):
    demand = getattr(window, "demand", None)
    return demand.board() if demand is not None else None


def model(window):
    return board(window).model


def fire(window, event, *args):
    shown = board(window)
    if shown is None:
        raise AssertionError("%s has no board" % type(window).__name__)
    return shown.fire(event, *args)


def press(window, event, *args):
    """A mousedown's data event, then the body's own (board_press), as
    RmlUi bubbles it, unless the press took the board away."""
    shown = board(window)
    result = fire(window, event, *args)
    if board(window) is shown:
        shown.fire("board_press", args[-1])
    return result


class Input(object):
    """One player input on the character window, as the legacy C++ sends it
    (slot window events, button clicks) and as the board sends it."""

    GRIDS = {"skill": ("Skill_Active_Slot", "skill"), "support": ("Skill_ETC_Slot", "support"),
             "solo": ("SoloEmotionSlot", "solo"), "dual": ("DualEmotionSlot", "dual"), "quest": ("Quest_Slot", "quest")}

    def __init__(self, world, window):
        self.world = world
        self.window = window
        self.nui = world.nui_on

    def _slots(self, grid):
        return self.window.GetChild(self.GRIDS[grid][0])

    def _index(self, grid, slot):
        return self._slots(grid).index_of(slot)

    def press(self, grid, slot, button=0):
        """A press on a cell (legacy: the slot window's CSlotWindow event;
        a disabled cover takes it and does nothing)."""
        with self.world.game, quiet():
            if self.nui:
                press(self.window, "%s_press" % self.GRIDS[grid][1], self._index(grid, slot), button)
                return
            self.window.SetTop()
            slots = self._slots(grid)
            cell = slots._slot(slot)
            if cell["cover"] is not None and cell["unavailable"] and cell["kind"]:
                return
            if button == 0:
                slots.fire("select_item" if cell["kind"] else "select_empty", slot)
            else:
                event = "unselect_item" if cell["kind"] else "unselect_empty"
                if slots.events.get(event):
                    slots.fire(event, slot)

    def over(self, grid, slot):
        with self.world.game, quiet():
            if self.nui:
                fire(self.window, "%s_over" % self.GRIDS[grid][1], self._index(grid, slot))
            else:
                self._slots(grid).fire("over_in", slot)

    def out(self, grid, slot):
        with self.world.game, quiet():
            if self.nui:
                fire(self.window, "%s_out" % self.GRIDS[grid][1], self._index(grid, slot))
            else:
                self._slots(grid).fire("over_out")

    def use(self, grid, slot):
        with self.world.game, quiet():
            if self.nui:
                fire(self.window, "%s_use" % self.GRIDS[grid][1], self._index(grid, slot))
            else:
                self._slots(grid).fire("use", slot)

    def plus(self, slot):
        with self.world.game, quiet():
            if self.nui:
                press(self.window, "skill_plus", slot, 0)
            else:
                self.window.SetTop()
                grid = "skill" if slot < 100 else "support"
                self._slots(grid).fire("pressed_button", slot)

    def button(self, name, nui_event, *args):
        """A legacy button (its CallEvent) against the board's event."""
        with self.world.game, quiet():
            if self.nui:
                press(self.window, nui_event, *(args + (0,)))
            else:
                self.window.SetTop()
                self.window.GetChild(name).click()

    def tab(self, name):
        with self.world.game, quiet():
            if self.nui:
                press(self.window, "tab_press", name, 0)
            else:
                self.window.SetTop()
                self.window.GetChild({"STATUS": "Tab_Button_01", "SKILL": "Tab_Button_02", "EMOTICON": "Tab_Button_03",
                                      "QUEST": "Tab_Button_04"}[name]).click()

    def close(self):
        with self.world.game, quiet():
            if self.nui:
                press(self.window, "close_press", 0)
            else:
                self.window.titleBarDict[self.window.state].close()


class CharacterTest(unittest.TestCase):
    def worlds(self, setup=warrior, limits=None):
        return World(False, setup=setup, limits=limits), World(True, setup=setup, limits=limits)

    def run_flow(self, flow, state="SKILL", setup=warrior):
        """The same flow in both worlds: [(effects, window, world)]."""
        results = []
        for world in self.worlds(setup):
            window = world.open(state)
            mark = world.mark()
            with world.game, quiet():
                flow(world, window, Input(world, window))
            results.append((world.effects_since(mark), window, world))
        return results


# --- the facade ----------------------------------------------------------------------------------

class Facade(CharacterTest):
    def test_a_subclass_of_the_legacy_class_with_every_facade_method(self):
        world = World(True)
        legacy, novaui = world.m("uiCharacter").CharacterWindow, world.m("nui_character").CharacterWindow
        self.assertTrue(issubclass(novaui, legacy))
        self.assertTrue(novaui.NUI_FACADE)
        for name in FACADE:
            ours = getattr(novaui, name)
            wrapped = getattr(ours, "__wrapped__", ours)
            theirs = getattr(legacy, name, None) or getattr(world.m("ui").ScriptWindow, name)
            mine = inspect.signature(wrapped)
            if any(p.kind == p.VAR_POSITIONAL for p in mine.parameters.values()):
                continue
            self.assertEqual(len(mine.parameters), len(inspect.signature(theirs).parameters), name)

    def test_make_builds_novaui_with_the_flag_and_the_3c_engine_and_legacy_otherwise(self):
        for nui_on, engine, expected in ((True, True, "nui_character"), (False, True, "uiCharacter"),
                                         (True, False, "uiCharacter")):
            world = World(nui_on, engine_3c=engine)
            window = world.make()
            with self.subTest(nui_on=nui_on, engine=engine):
                self.assertEqual(type(window).__module__, expected)
                self.assertEqual(world.game.loaded_documents(), [], "no document while the window is closed")

    def test_a_document_that_does_not_load_falls_back_once_to_syserr_and_never_aborts(self):
        world = World(True)
        world.game.state.failing.add(DOCUMENT)
        window = world.make()
        self.assertEqual(type(window).__module__, "uiCharacter")
        self.assertEqual(world.game.dbg.errors, ["nui_windows: character: the document did not load; using the legacy window"])
        self.assertFalse([name for name, args in world.game.log if name.startswith("exception.")], "no exception.Abort")

    def test_a_load_that_raises_falls_back_without_aborting(self):
        world = World(True)
        world.game.state.raising.add(DOCUMENT)
        window = world.make()
        self.assertEqual(type(window).__module__, "uiCharacter")
        self.assertTrue(world.game.dbg.errors[0].startswith("nui_windows: character: the controller could not be made"))
        self.assertFalse([name for name, args in world.game.log if name.startswith("exception.")])

    # The legacy lines of P15 spec 4.7, 5.7 and 6.7, exactly, at their places.
    WIRING = (
        (186, 'wndCharacter = nui_windows.make("character", uiCharacter.CharacterWindow, "nui_character.CharacterWindow")'),
        (190, 'wndDragonSoul = nui_windows.make("dragon-soul", uiDragonSoul.DragonSoulWindow, '
              '"nui_dragon_soul.DragonSoulWindow")'),
        (192, 'wndDragonSoulRefine = nui_windows.make("dragon-soul-refine", uiDragonSoul.DragonSoulRefineWindow, '
              '"nui_dragon_soul_refine.DragonSoulRefineWindow")'),
    )

    def test_the_interface_makes_it_through_make(self):
        text = read(os.path.join(ROOT, "interfacemodule.py")).split("\n")
        for number, line in self.WIRING:
            self.assertEqual(text[number - 1].strip(), line, "interfacemodule.py:%d" % number)

    def test_a_window_whose_module_is_missing_falls_back_to_legacy_with_one_syserr_line(self):
        """The dragon soul lines name their NovaUI modules exactly; until a
        module exists, its flag on makes the legacy window (nui_windows.make)."""
        world = World(True, windows="+character,+dragon-soul")
        legacy = types.SimpleNamespace(made=[])

        class Legacy(object):
            def __init__(self):
                legacy.made.append(self)
        with world.game:
            window = world.nui_windows.make("dragon-soul", Legacy, "nui_missing_3c_module.DragonSoulWindow")
        self.assertIs(type(window), Legacy)
        self.assertEqual(len([e for e in world.game.dbg.errors if e.startswith("nui_windows: dragon-soul:")]), 1)

    def test_the_legacy_window_underneath_has_the_uiscript_s_flags_and_stays_0_by_0(self):
        legacy, novaui = World(False), World(True)
        a, b = legacy.open(), novaui.open()
        self.assertEqual(b.flags, a.flags & {"movable", "float"})
        self.assertIn("float", b.flags)
        self.assertEqual((b.GetWidth(), b.GetHeight()), (0, 0))


# --- the model against the legacy widgets ----------------------------------------------------------------

def legacy_skill_cells(window, page):
    """{slot: (kind, icon, label, cover, disabled cover, cooldown, active,
    plus)} of the legacy slot window, as CSlotWindow draws it."""
    return dict((slot, (kind, icon, label, cover, disabled, cool, active, button))
                for slot, (kind, _, icon, label, cover, disabled, cool, active, button)
                in window.GetChild(page).skill_cells().items())


def novaui_skill_cells(cells):
    """The same of the board's cells; an icon's store path starts at the
    root ("/icon/..."), legacy's pack path does not."""
    found = {}
    for cell in cells:
        if not cell["kind"]:
            continue
        icon = cell["icon"][1:] if cell["icon"].startswith("/") else cell["icon"]
        found[cell["slot"]] = (cell["kind"], icon, cell["count"], cell["cover"], cell["unavailable"],
                               (cell["cd_start"], cell["cd_end"]), cell["active"], cell.get("button", False))
    return found


class Model(CharacterTest):
    def assert_same_status(self, a, b):
        for child, key in STATUS:
            self.assertEqual(model(b)[key], a.GetChild(child).GetText(), key)
        self.assertEqual(model(b)["name"], a.GetChild("Character_Name").GetText())
        self.assertEqual(model(b)["guild"], a.GetChild("Guild_Name").GetText())
        self.assertEqual(model(b)["has_guild"], a.GetChild("Guild_Name_Slot").IsShow())
        self.assertEqual(model(b)["stat_points"], a.GetChild("Status_Plus_Value").GetText())
        self.assertEqual(model(b)["stat_points_shown"], a.GetChild("Status_Plus_Label").IsShow())
        for key, suffix in (("HTH", "ht"), ("INT", "iq"), ("STR", "st"), ("DEX", "dx")):
            self.assertEqual(model(b)["plus_" + suffix], a.GetChild(key + "_Plus").IsShow(), key)
            self.assertEqual(model(b)["minus_" + suffix], a.GetChild(key + "_Minus").IsShow(), key)

    def assert_same_skills(self, a, b):
        self.assertEqual(novaui_skill_cells(model(b)["skills"]), legacy_skill_cells(a, "Skill_Active_Slot"))
        self.assertEqual(novaui_skill_cells(model(b)["support"]), legacy_skill_cells(a, "Skill_ETC_Slot"))
        groups = [(g["label"], g["shown"], g["down"], g["col"]) for g in model(b)["groups"]]
        legacy_groups = [(button.text if hasattr(button, "text") else button.GetText(), button.shown,
                          getattr(button, "down", False), {5: 0, 50: 1, 95: 2}[button.position[0]])
                         for button in a.skillGroupButton]
        self.assertEqual([g for g in groups if g[1]], [g for g in legacy_groups if g[1]])
        name = a.GetChild("Active_Skill_Group_Name")
        self.assertEqual(model(b)["group_name_shown"], name.IsShow())
        if name.IsShow():
            self.assertEqual(model(b)["group_name"], name.GetText())
        self.assertEqual(model(b)["active_points"], a.GetChild("Active_Skill_Point_Value").GetText())
        self.assertEqual(model(b)["support_points_shown"], a.GetChild("Support_Skill_Point_Label").IsShow())

    def test_the_status_texts_equal_legacy_s(self):
        legacy, novaui = self.worlds()
        a, b = legacy.open(), novaui.open()
        self.assert_same_status(a, b)
        self.assertEqual(model(b)["level"], "99")
        self.assertEqual(model(b)["exp_rest"], str(3500000000 - 2147483647))
        self.assertEqual(model(b)["att"], "125-185")
        self.assertEqual(model(b)["face"], "/icon/face/warrior_m.tga")

    def test_the_skill_cells_equal_legacy_s_for_each_group_and_job(self):
        for job, race in (("warrior", 0), ("shaman", 3)):
            for group in (0, 1, 2):
                def setup(game, group=group, race=race):
                    warrior(game, group)
                    game.race = race
                    for index in (91, 92, 93, 94, 95, 96, 106, 107):
                        game.skill_types[index] = SKILL_TYPE["SKILL_TYPE_ACTIVE"]
                        game.skill_by_index[index] = {"grade": index % 4, "level": 10 + index % 7}
                legacy, novaui = self.worlds(setup)
                a, b = legacy.open("SKILL"), novaui.open("SKILL")
                with self.subTest(job=job, group=group):
                    self.assert_same_skills(a, b)

    def test_the_riding_page_and_its_group_button(self):
        legacy, novaui = self.worlds(lambda game: warrior(game, 1, riding=(1, 5)))
        a, b = legacy.open("SKILL"), novaui.open("SKILL")
        self.assert_same_skills(a, b)
        self.assertTrue(model(b)["groups"][2]["shown"], "riding at 24: the riding button")
        self.assertEqual(model(b)["groups"][2]["col"], 1, "beside the group's own button (x 50)")
        Input(legacy, a).button("Skill_Group_Button_3", "group_press", 2)
        Input(novaui, b).button("Skill_Group_Button_3", "group_press", 2)
        self.assertEqual(a.curSelectedSkillGroup, 3)
        self.assertEqual(b.curSelectedSkillGroup, 3)
        self.assert_same_skills(a, b)

    def test_the_emotion_grids_and_the_quest_rows(self):
        legacy, novaui = self.worlds()
        a, b = legacy.open("EMOTICON"), novaui.open("EMOTICON")
        for page, key in (("SoloEmotionSlot", "solo"), ("DualEmotionSlot", "dual")):
            self.assertEqual(novaui_skill_cells(model(b)[key]), legacy_skill_cells(a, page), key)
        self.assertEqual(len([c for c in model(b)["solo"] if c["kind"]]), 18)
        self.assertEqual(len([c for c in model(b)["dual"] if c["kind"]]), 3)
        with legacy.game, novaui.game, quiet():
            a.SetState("QUEST")
            a.OnUpdate()   # legacy writes the clocks each frame on the quest tab
            b.SetState("QUEST")
        rows = model(b)["quests"]
        for row in range(5):
            self.assertEqual(rows[row]["shown"], a.questNameList[row].IsShow(), row)
            if not rows[row]["shown"]:
                continue   # a hidden row's texts are the uiscript's, never shown
            self.assertEqual((rows[row]["name"], rows[row]["counter"]),
                             (a.questNameList[row].GetText(), a.questLastCountList[row].GetText()), row)
            self.assertEqual(b.questLastTimeList[row].GetText(), a.questLastTimeList[row].GetText(), row)
        self.assertEqual(rows[0]["icon"], "d:/ymir work/ui/game/quest/questicon/level_24.sub")
        self.assertEqual(model(b)["quest_cells"][1]["icon"], "/season1/icon/scroll_open.tga")
        self.assertEqual([c["kind"] for c in model(b)["quest_cells"]], ["icon", "icon", "icon", "", ""])

    def test_the_foundation_s_sage_labels(self):
        world = World(True, limits=None)
        limits = world.m("nui_limits").foundation()
        world.m("nui_limits").use(limits)
        with world.game:
            proxy = world.m("nui_slots").FullSlotWindowProxy([41], None, limits=limits)
            proxy.SetSkillSlotNew(41, 5, 3, 7)
            proxy.SetSlotCountNew(41, 3, 7)
            self.assertEqual(proxy.cells()[0]["count"], "", "not refreshed yet")
            proxy.push()
            self.assertEqual(proxy.cells()[0]["count"], "p7")
            proxy.SetSlotCountNew(41, 4, 50)
            proxy.push()
            self.assertEqual(proxy.cells()[0]["count"], "s")
        window = world.open("SKILL")
        self.assertEqual(len(model(window)["skills"]), 24, "three columns at the cut too")


# --- the flows (P15 spec 4.5) ----------------------------------------------------------------------------------

def taskbar_module(world, name, file_name):
    """uiTaskBar, or nui_taskbar after it (it subclasses nothing but reads
    legacy's module), loaded into the world."""
    game = world.game
    with quiet():
        if "uiTaskBar" not in game.loaded:
            game.load("uiTaskBar", "uitaskbar.py")
        if name not in game.loaded:
            game.load(name, file_name)
    return game.loaded[name]


class Flows(CharacterTest):
    def same(self, flow, state="SKILL", setup=warrior):
        (legacy, a, lw), (novaui, b, nw) = self.run_flow(flow, state, setup)
        self.assertEqual(novaui, legacy)
        return legacy, a, b, lw, nw

    def test_c1_c2_open_on_a_tab_and_switch_tabs(self):
        def flow(world, window, input):
            input.tab("QUEST")
            input.tab("QUEST")
            input.tab("EMOTICON")
        calls, a, b, _, _ = self.same(flow, state="STATUS")
        self.assertEqual(calls, [])
        self.assertEqual((a.GetState(), b.GetState()), ("EMOTICON", "EMOTICON"))
        self.assertEqual((model(b)["panel_emoticon"], model(b)["panel_status"], model(b)["panel_quest"]), ([1], [], []))

    def test_c3_c4_a_stat_point_spent_and_taken_back(self):
        def flow(world, window, input):
            for key in ("HTH", "INT", "STR", "DEX"):
                input.button(key + "_Plus", "stat_plus", key)
                input.button(key + "_Minus", "stat_minus", key)
        calls, _, _, _, _ = self.same(flow, state="STATUS")
        self.assertEqual(calls, [("net.SendChatPacket", ("/stat ht",)), ("net.SendChatPacket", ("/stat- ht",)),
                                 ("net.SendChatPacket", ("/stat iq",)), ("net.SendChatPacket", ("/stat- iq",)),
                                 ("net.SendChatPacket", ("/stat st",)), ("net.SendChatPacket", ("/stat- st",)),
                                 ("net.SendChatPacket", ("/stat dx",)), ("net.SendChatPacket", ("/stat- dx",))])

    def test_no_stat_points_hides_the_plus_buttons_and_a_press_sends_nothing(self):
        def setup(game):
            warrior(game)
            game.status[P["STAT"]] = 0
        def flow(world, window, input):
            if world.nui_on:
                press(window, "stat_plus", "HTH", 0)
        calls, a, b, _, _ = self.same(flow, state="STATUS", setup=setup)
        self.assertEqual(calls, [])
        self.assertFalse(model(b)["plus_ht"])
        self.assertFalse(model(b)["stat_points_shown"])

    def test_c5_a_skill_point_spent(self):
        def flow(world, window, input):
            input.plus(1)
            input.plus(2)
        calls, _, b, _, _ = self.same(flow)
        self.assertEqual(calls, [("net.SendChatPacket", ("/skillup 1",)), ("net.SendChatPacket", ("/skillup 2",))])
        self.assertEqual([c["slot"] for c in model(b)["skills"] if c["button"]], [1, 2])

    def test_c6_c9_a_skill_picked_and_dropped_on_an_empty_cell(self):
        def flow(world, window, input):
            input.press("skill", 1)
            input.press("skill", 7)
        calls, _, _, _, _ = self.same(flow)
        self.assertEqual(calls, [("mouse.AttachObject", (P["SLOT_TYPE_SKILL"], 1, 1, 0)), ("mouse.DeattachObject", ())])

    def test_c6_a_press_on_a_disabled_cover_does_nothing(self):
        def flow(world, window, input):
            input.press("skill", 21)   # skill 1's grade 1 column: disabled
            input.press("skill", 21, 1)
        calls, _, _, _, _ = self.same(flow)
        self.assertEqual(calls, [])

    def test_c7_c19_ctrl_and_a_press_add_to_the_first_free_quickslot(self):
        def flow(world, window, input):
            world.game.pressed.add(support.APP_CONSTANTS["DIK_LCONTROL"])
            input.press("skill", 2)
            input.tab("EMOTICON")
            input.press("solo", 1)
        calls, _, _, _, _ = self.same(flow)
        self.assertEqual(calls, [("player.RequestAddToEmptyLocalQuickSlot", (P["SLOT_TYPE_SKILL"], 2)),
                                 ("player.RequestAddToEmptyLocalQuickSlot", (P["SLOT_TYPE_EMOTION"], 1))])

    def test_c8_c20_a_skill_and_an_emotion_dropped_on_a_quickslot_of_either_taskbar(self):
        """The drop is the taskbar's AddQuickSlot (legacy's, and the NovaUI
        taskbar's copy of it with MR-3's swap): what the character window
        attached decides the calls, so both worlds make the same ones."""
        for module_name, file_name in (("uiTaskBar", "uitaskbar.py"), ("nui_taskbar", "nui_taskbar.py")):
            def flow(world, window, input):
                cls = taskbar_module(world, module_name, file_name).TaskBar
                bar = types.SimpleNamespace(RefreshQuickSlot=lambda: None)
                bar.canAddQuickSlot = lambda kind, slot: cls.canAddQuickSlot(bar, kind, slot)
                input.press("skill", 2)
                cls.AddQuickSlot(bar, 3)
                input.tab("EMOTICON")
                input.press("solo", 5)
                cls.AddQuickSlot(bar, 4)
            with self.subTest(taskbar=module_name):
                calls, _, _, _, _ = self.same(flow)
                self.assertEqual([call for call in calls if not call[0].startswith("player.GetLocalQuickSlot")], [
                    ("mouse.AttachObject", (P["SLOT_TYPE_SKILL"], 2, 2, 0)),
                    ("player.RequestAddLocalQuickSlot", (3, P["SLOT_TYPE_SKILL"], 2)),
                    ("mouse.DeattachObject", ()),
                    ("mouse.AttachObject", (P["SLOT_TYPE_EMOTION"], 5, 5, 0)),
                    ("player.RequestAddLocalQuickSlot", (4, P["SLOT_TYPE_EMOTION"], 5)),
                    ("mouse.DeattachObject", ())])

    def test_c8_a_skill_already_in_a_quickslot_is_moved_there_mr3(self):
        def setup(game):
            warrior(game)
            game.quick[6] = (P["SLOT_TYPE_SKILL"], 2)
        def flow(world, window, input):
            module = taskbar_module(world, "nui_taskbar", "nui_taskbar.py")
            bar = types.SimpleNamespace(RefreshQuickSlot=lambda: None, canAddQuickSlot=lambda kind, slot: True)
            input.press("skill", 2)
            module.TaskBar.AddQuickSlot(bar, 1)
        calls, _, _, _, _ = self.same(flow, setup=setup)
        self.assertIn(("player.RequestMoveGlobalQuickSlotToLocalQuickSlot", (6, 1)), calls)

    def test_c10_a_skill_used_by_a_right_press(self):
        def flow(world, window, input):
            input.press("skill", 2, 1)
            input.press("skill", 23, 1)
        calls, _, _, _, _ = self.same(flow)
        self.assertEqual(calls, [("player.ClickSkillSlot", (2,)), ("player.ClickSkillSlot", (3,))])

    def test_c10_a_double_click_on_a_covered_skill_uses_nothing(self):
        def flow(world, window, input):
            if world.nui_on:
                input.use("skill", 2)
        calls, _, _, _, _ = self.same(flow)
        self.assertEqual(calls, [], "the cover button takes the double click as a press (CButton)")

    def test_c10_without_a_skill_group_an_active_skill_does_nothing(self):
        def setup(game):
            warrior(game, group=0)
        def flow(world, window, input):
            input.press("skill", 1, 1)
        calls, _, _, _, _ = self.same(flow, setup=setup)
        self.assertEqual(calls, [])

    def test_c11_c12_c13_cooldowns_toggles_and_their_clear(self):
        def flow(world, window, input):
            with world.game, quiet():
                world.game.state.now = 50.0
                window.OnUseSkill(4, 12.0)
                # A use stores its cooldown inactive (CSlotWindow::StoreSlotCoolTime),
                # so the toggle's activation comes after.
                window.OnUseSkill(3, 6.0)
                window.OnActivateSkill(3)
        (legacy, a, lw), (novaui, b, nw) = self.run_flow(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual(novaui_skill_cells(model(b)["skills"]), legacy_skill_cells(a, "Skill_Active_Slot"))
        cells = dict((c["slot"], c) for c in model(b)["skills"])
        self.assertEqual((cells[44]["cd_start"], cells[44]["cd_end"]), (50.0, 62.0), "skill 4 is grade 2: column 2")
        self.assertTrue(cells[23]["active"], "the toggle is active (OnActivateSkill, no RefreshSlot)")
        with lw.game, nw.game:
            a.SkillClearCoolTime(4)
            b.SkillClearCoolTime(4)
        self.assertEqual(novaui_skill_cells(model(b)["skills"]), legacy_skill_cells(a, "Skill_Active_Slot"))
        self.assertEqual(dict((c["slot"], c) for c in model(b)["skills"])[44]["cd_end"], 0.0)
        with lw.game, nw.game:
            a.OnDeactivateSkill(3)
            b.OnDeactivateSkill(3)
        self.assertFalse(dict((c["slot"], c) for c in model(b)["skills"])[23]["active"])

    def test_c11_a_refresh_after_a_cooldown_transfers_and_restores_it_as_legacy(self):
        def flow(world, window, input):
            with world.game, quiet():
                world.game.state.now = 10.0
                window.OnUseSkill(4, 30.0)
                world.game.skills[4]["cool"] = (30.0, 0.0)
                world.game.state.now = 12.0
                window.RefreshSkill()
                world.game.skill_by_index[4]["grade"] = 3   # it became perfect
                world.game.skills[4]["grade"] = 3
                window.RefreshSkill()
        (legacy, a, _), (novaui, b, _) = self.run_flow(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual(novaui_skill_cells(model(b)["skills"]), legacy_skill_cells(a, "Skill_Active_Slot"))
        self.assertEqual(b.skillPageDict["ACTIVE"].stored(1), dict(
            (slot, tuple(entry)) for slot, entry in a.GetChild("Skill_Active_Slot").store.get(1, {}).items()))

    def test_c14_c15_a_group_chosen_and_the_riding_page(self):
        def setup(game):
            warrior(game, group=0, riding=(2, 3))
        def flow(world, window, input):
            input.button("Skill_Group_Button_2", "group_press", 1)
            input.button("Skill_Group_Button_3", "group_press", 2)
            input.button("Skill_Group_Button_3", "group_press", 2)
        calls, a, b, _, _ = self.same(flow, setup=setup)
        self.assertEqual([call for call in calls if call[0].startswith("net.")], [], "client-side")
        self.assertIn(("player.SetSkill", (2, 17)), calls, "the second group's skills registered")
        self.assertIn(("player.ResetHorseSkillCoolTime", (138, 3)), calls, "the horse page: a skill at level 0")
        self.assertEqual((a.curSelectedSkillGroup, b.curSelectedSkillGroup), (3, 3))
        Model.assert_same_skills(self, a, b)

    def test_c16_riding_under_21_clears_the_horse_skills_from_the_quickslots(self):
        def setup(game):
            warrior(game, group=1, riding=(1, 5))
            game.quick[0 * 8 + 3] = (P["SLOT_TYPE_SKILL"], 9)     # skill 137 on the first page
            game.quick[2 * 8 + 1] = (P["SLOT_TYPE_SKILL"], 9)     # and on the third
            game.quick[1 * 8 + 0] = (P["SLOT_TYPE_SKILL"], 1)     # an active skill stays
        def flow(world, window, input):
            # The riding skill drops to level 10: riding under 21, no horse page.
            world.game.skill_by_index[130] = {"grade": 0, "level": 10}
            world.game.skills[109].update(grade=0, level=10)
            window.RefreshSkill()
        calls, _, b, _, _ = self.same(flow, setup=setup)
        deletes = [args[0] for name, args in calls if name == "player.RequestDeleteGlobalQuickSlot"]
        self.assertEqual(deletes, [3, 17])
        pages = [args[0] for name, args in calls if name == "player.SetQuickPage"]
        self.assertEqual(pages, [0, 1, 2, 3, 0], "every page, then the one shown put back")
        self.assertFalse(model(b)["groups"][2]["shown"])

    def test_c17_the_skill_tooltip_by_the_column(self):
        def flow(world, window, input):
            input.over("skill", 21)
            input.out("skill", 21)
            input.over("skill", 1)
            input.over("skill", 44)
            input.out("skill", 44)
            input.over("skill", 45)
            input.out("skill", 45)
            input.over("support", 101)
            input.out("support", 101)
        (_, a, _), (_, b, _) = self.run_flow(flow)
        self.assertEqual(b.toolTipSkill.calls, a.toolTipSkill.calls)
        self.assertIn(("SetSkillOnlyName", 1, 1, 1), b.toolTipSkill.calls)
        self.assertIn(("SetSkillNew", 5, 5, 3, 1), b.toolTipSkill.calls, "perfect: its grade in the last column")

    def test_c17_nothing_while_attached(self):
        def flow(world, window, input):
            input.press("skill", 2)
            world.toolTipCalls = list(window.toolTipSkill.calls)
            input.over("skill", 4)
        (calls_a, a, wa), (calls_b, b, wb) = self.run_flow(flow)
        self.assertEqual(calls_b, calls_a)
        self.assertEqual(b.toolTipSkill.calls[len(wb.toolTipCalls):], a.toolTipSkill.calls[len(wa.toolTipCalls):])

    def test_c18_c20_an_emotion_picked_and_used(self):
        """A press picks an emotion, a press on another while one is attached
        picks that one (legacy's __SelectEmotion attaches again), a right
        press acts it. The right press while attached is F-2's
        (F2RightPress)."""
        def flow(world, window, input):
            input.press("solo", 1)
            input.press("solo", 5)
            world.mouse.DeattachObject()
            input.press("solo", 5, 1)
        calls, _, _, _, _ = self.same(flow, state="EMOTICON")
        self.assertEqual(calls, [("mouse.AttachObject", (P["SLOT_TYPE_EMOTION"], 1, 1, 0)),
                                 ("mouse.AttachObject", (P["SLOT_TYPE_EMOTION"], 5, 5, 0)),
                                 ("mouse.DeattachObject", ()), ("net.SendChatPacket", ("/attractive",))])

    def test_c21_an_emotion_and_a_mutual_one_without_and_with_a_player_target(self):
        def flow(world, window, input):
            input.press("solo", 1, 1)
            input.press("dual", 51, 1)
            world.game.target_vid = 77
            world.game.vid_names[77] = "Borak"
            input.press("dual", 51, 1)
            world.game.acting = True
            input.press("solo", 1, 1)
        calls, _, _, _, _ = self.same(flow, state="EMOTICON")
        self.assertEqual(calls, [("net.SendChatPacket", ("/clap",)),
                                 ("chat.AppendChat", (support.CHAT_CONSTANTS["CHAT_TYPE_INFO"],
                                                      support.locale_info("en").EMOTION_CHOOSE_ONE)),
                                 ("net.SendChatPacket", ("/kiss Borak",))])

    def test_c22_c23_a_quest_opened_and_the_list_scrolled(self):
        def setup(game):
            warrior(game)
            game.quests = [{"name": "q%d" % i, "index": 30 + i} for i in range(8)]
        def flow(world, window, input):
            input.press("quest", 0)
            if world.nui_on:
                press(window, "quest_scroll_press", 1, 0)
                press(window, "quest_scroll_press", 1, 0)
            else:
                window.questScrollBar.SetPos(1.0 / 3)
                window.questScrollBar.SetPos(2.0 / 3)
            input.press("quest", 0)
        calls, a, b, _, _ = self.same(flow, state="QUEST", setup=setup)
        self.assertEqual(calls, [("event.QuestButtonClick", (-2147483648 + 30,)),
                                 ("event.QuestButtonClick", (-2147483648 + 32,))])
        self.assertEqual((a.questShowingStartIndex, b.questShowingStartIndex), (2, 2))
        self.assertEqual(model(b)["quests"][0]["name"], "q2")
        self.assertTrue(model(b)["quest_scroll_shown"])

    def test_c23_one_line_per_arrow_click_and_wheel_notch_with_fifteen_quests(self):
        """Ten scroll lines: each click moves the start one line, down to the
        last and back up to the first, with no stall or skip (review R-3)."""
        def setup(game):
            warrior(game)
            game.quests = [{"name": "q%d" % i, "index": 30 + i} for i in range(15)]
        world = World(True, setup=setup)
        window = world.open("QUEST")
        down, up, wheel = [], [], []
        with world.game, quiet():
            for _ in range(11):
                press(window, "quest_scroll_press", 1, 0)
                down.append(window.questShowingStartIndex)
            for _ in range(11):
                press(window, "quest_scroll_press", -1, 0)
                up.append(window.questShowingStartIndex)
            for _ in range(4):
                fire(window, "quest_scroll", 120.0)
                wheel.append(window.questShowingStartIndex)
        self.assertEqual(down, list(range(1, 11)) + [10])
        self.assertEqual(up, list(range(9, -1, -1)) + [0])
        self.assertEqual(wheel, [1, 2, 3, 4])
        self.assertEqual(model(window)["quests"][0]["name"], "q4")

    def test_c24_the_alignment_and_stat_tooltips(self):
        def flow(world, window, input):
            if world.nui_on:
                fire(window, "name_over")
                fire(window, "name_out")
                fire(window, "stat_over", "plus", "HTH")
                fire(window, "stat_out", "plus", "HTH")
                fire(window, "stat_over", "minus", "INT")
                fire(window, "stat_out", "minus", "INT")
            else:
                window.characterNameSlot.fire("MOUSE_OVER_IN")
                window.characterNameSlot.fire("MOUSE_OVER_OUT")
                window.GetChild("HTH_Plus").ShowToolTip()
                window.GetChild("HTH_Plus").HideToolTip()
                window.GetChild("INT_Minus").ShowToolTip()
                window.GetChild("INT_Minus").HideToolTip()
        (_, a, _), (_, b, _) = self.run_flow(flow, state="STATUS")
        for name in ("toolTip", "toolTipAlignment"):
            self.assertEqual(getattr(b, name).calls, getattr(a, name).calls, name)
        self.assertIn(("ShowToolTip",), b.toolTipAlignment.calls)

    def test_c24_a_hide_ends_the_stat_and_name_hovers_as_legacy_s_next_mouse_move(self):
        """Legacy's window manager sends the hidden window's stat button and
        name slot OnMouseOverOut at the next mouse move: the plain tooltips
        hide and refreshToolTip is cleared, so RefreshStatus shows nothing
        while the window is closed. The board hears no mouseout as it goes,
        so Hide sends them (review R-1)."""
        for over in (("minus", "INT", "INT_Minus"), ("plus", "HTH", "HTH_Plus")):
            seen = []
            for world in self.worlds():
                window = world.open("STATUS")
                with world.game, quiet():
                    if world.nui_on:
                        fire(window, "stat_over", over[0], over[1])
                        fire(window, "name_over")
                    else:
                        window.GetChild(over[2]).ShowToolTip()
                        window.characterNameSlot.fire("MOUSE_OVER_IN")
                marks = (len(window.toolTip.calls), len(window.toolTipAlignment.calls))
                with world.game, quiet():
                    world.game.press_escape()
                    if not world.nui_on:
                        # The C++'s next mouse move over the closed window.
                        window.GetChild(over[2]).HideToolTip()
                        window.characterNameSlot.fire("MOUSE_OVER_OUT")
                    window.RefreshStatus()
                    window.RefreshStatus()
                seen.append((window.toolTip.calls[marks[0]:], window.toolTipAlignment.calls[marks[1]:],
                             bool(window.refreshToolTip), window.IsShow()))
            self.assertEqual(seen[1], seen[0], over)
            tip, alignment, refresh, shown = seen[1]
            self.assertEqual((tip, refresh, shown), ([("Hide",)], False, False), over)
            # RefreshStatus rebuilds the alignment tooltip's lines (RefreshAlignment) but shows nothing.
            self.assertEqual(alignment[0], ("HideToolTip",), over)
            self.assertFalse([call for call in alignment if call[0] in ("Show", "ShowToolTip")], over)

    def test_c24_a_late_mouseout_after_the_hide_sends_nothing_more(self):
        world = World(True)
        window = world.open("STATUS")
        with world.game, quiet():
            fire(window, "stat_over", "minus", "INT")
            window.Hide()
        mark = len(window.toolTip.calls)
        with world.game, quiet():
            window.Show()
            fire(window, "stat_out", "minus", "INT")
            fire(window, "name_out")
        self.assertEqual(window.toolTip.calls[mark:], [])

    def test_c25_close_by_the_title_bar_and_by_escape(self):
        def flow(world, window, input):
            input.close()
            with world.game, quiet():
                window.SetState("SKILL")
                window.Show()
                world.game.press_escape()
        calls, a, b, _, nw = self.same(flow)
        self.assertEqual(calls, [])
        self.assertFalse(a.IsShow())
        self.assertFalse(b.IsShow())
        self.assertNotIn(DOCUMENT, nw.game.loaded_documents())


class F2RightPress(CharacterTest):
    def test_a_right_press_on_a_skill_while_something_is_attached_follows_attach_right(self):
        """F-2 (P15 spec 8.2): legacy's CSlotWindow sends the unselect event
        whatever is attached; NovaUI does while nui_slots.ATTACH_RIGHT holds,
        else nothing (the host cancels the attach)."""
        def flow(world, window, input):
            input.press("skill", 1)
            input.press("skill", 2, 1)
        (legacy, _, _), (novaui, _, nw) = self.run_flow(flow)
        clicked = [call for call in legacy if call[0] == "player.ClickSkillSlot"]
        self.assertEqual(clicked, [("player.ClickSkillSlot", (2,))], "legacy uses the clicked skill")
        if nw.m("nui_slots").ATTACH_RIGHT:
            self.assertEqual(novaui, legacy)
        else:
            self.assertEqual([call for call in novaui if call[0] == "player.ClickSkillSlot"], [])


# --- the cooldown store, the clocks, the panels ------------------------------------------------------------

class CooldownStore(CharacterTest):
    def test_store_restore_and_transfer_give_cslotwindow_s_spans(self):
        """The proxy against the legacy world's model of CSlotWindow
        (LegacySkillSlotWindow, PythonSlotWindow.cpp:508-599): the early
        return, the stored active state, a transfer to a learned slot and
        to one that is not."""
        legacy, novaui = World(False), World(True)
        a, b = legacy.open("SKILL"), novaui.open("SKILL")
        for world, window in ((legacy, a), (novaui, b)):
            slots = window.GetChild("Skill_Active_Slot")
            with world.game:
                world.game.state.now = 5.0
                slots.StoreSlotCoolTime(1, 44, 20.0)
                slots.StoreSlotCoolTime(1, 99, 3.0)    # a slot it lacks: the restore stops there
                slots.StoreSlotCoolTime(1, 3, 8.0, 2.0)
                slots.ActivateSlot(3)
                slots.RestoreSlotCoolTime(1)
                slots.TransferSlotCoolTime(44, 24)     # skill 4 is not learned at 24 (level 0)
                slots.TransferSlotCoolTime(3, 23)
                slots.RestoreSlotCoolTime(1)
                window._flush() if world.nui_on else None
        self.assertEqual(novaui_skill_cells(model(b)["skills"]), legacy_skill_cells(a, "Skill_Active_Slot"))
        self.assertEqual(b.GetChild("Skill_Active_Slot").stored(1), dict(
            (slot, tuple(entry)) for slot, entry in a.GetChild("Skill_Active_Slot").store[1].items()))


def legacy_minsec(seconds, minute="Min.", second="Sec."):
    """ENGINE's format="minsec" (nui_game_support.minsec_text)."""
    return support.minsec_text(seconds, minute, second)


class Clocks(CharacterTest):
    def test_the_model_s_prefix_and_end_read_as_legacy_s_text(self):
        world = World(True)
        window = world.open("QUEST")
        locale = support.locale_info("en")
        for seconds in (1, 59, 60, 61, 3599, 3600, 3661):
            with world.game, quiet():
                world.game.state.now = 100.0
                world.game.quests[0]["clock_end"] = 100.0 + seconds
                window.RefreshQuest()
            row = model(window)["quests"][0]
            remaining = int(row["clock_end"] - world.game.state.now)
            with self.subTest(seconds=seconds):
                self.assertEqual(row["clock_prefix"] + legacy_minsec(remaining, locale.QUEST_MIN, locale.QUEST_SEC),
                                 window.questLastTimeList[0].GetText())
        for seconds in (0, 1, 59, 60, 61, 3599, 3600):
            with self.subTest(model_of=seconds):
                expected = window._legacy_clock_text("Time left", seconds)
                self.assertEqual(support.minsec_text(seconds, locale.QUEST_MIN, locale.QUEST_SEC, "Time left : ",
                                                     locale.QUEST_TIMEOVER), expected,
                                 "the countdown's text with its prefix and over is legacy's")
        row = model(window)["quests"][1]
        self.assertEqual((row["clock_end"], row["clock_text"]), (0.0, locale.QUEST_TIMEOVER), "a clock run out: legacy's text")
        row = model(window)["quests"][2]
        self.assertEqual((row["clock_end"], row["clock_text"]), (0.0, locale.QUEST_UNLIMITED_TIME))

    def test_the_rows_clocks_follow_legacy_s_index_after_a_scroll(self):
        """D14: legacy writes quest i's clock into row i whatever the scroll."""
        def setup(game):
            warrior(game)
            game.quests = [{"name": "q%d" % i, "index": i, "clock_name": "c%d" % i, "clock_end": 100.0 + i} for i in range(7)]
        legacy, novaui = World(False, setup=setup), World(True, setup=setup)
        a, b = legacy.open("QUEST"), novaui.open("QUEST")
        with legacy.game, novaui.game, quiet():
            a.questScrollBar.SetPos(1.0)
            press(b, "quest_scroll_press", 1, 0)
            press(b, "quest_scroll_press", 1, 0)
        self.assertEqual(a.questShowingStartIndex, b.questShowingStartIndex)
        self.assertEqual([b.questLastTimeList[i].GetText() for i in range(5)],
                         [a.questLastTimeList[i].GetText() for i in range(5)])
        self.assertEqual(model(b)["quests"][0]["clock_prefix"], "c0 : ")
        self.assertEqual(model(b)["quests"][0]["name"], "q2")


class Panels(CharacterTest):
    def test_one_panel_at_a_time(self):
        world = World(True)
        window = world.open("SKILL")
        for state in ("STATUS", "SKILL", "EMOTICON", "QUEST"):
            with world.game, quiet():
                window.SetState(state)
            panels = dict((key, model(window)[key]) for key in ("panel_status", "panel_skill", "panel_emoticon", "panel_quest"))
            self.assertEqual(sorted(key for key, value in panels.items() if value), ["panel_" + state.lower()])
            self.assertEqual(model(window)["tab"], state)

    def test_no_per_frame_python(self):
        world = World(True)
        cls = world.m("nui_character").CharacterWindow
        self.assertIsNone(cls.OnUpdate, "OnUpdate is None (D5): the C++ calls nothing")
        self.assertFalse(hasattr(cls, "OnRender") and cls.OnRender is not None and "OnRender" in vars(cls))
        source = read(os.path.join(ROOT, "nui_character.py"))
        self.assertNotRegex(source, r"def OnUpdate|def OnRender")

    def test_on_demand_and_the_place_kept_across_hides(self):
        world = World(True)
        window = world.make()
        self.assertEqual(world.game.loaded_documents(), [])
        with world.game, quiet():
            window.Show()
        self.assertEqual(world.game.loaded_documents(), [DOCUMENT])
        world.game.state.boxes[(DOCUMENT, "")] = (300.0, 120.0, 298.0, 421.0)
        with world.game, quiet():
            window.Hide()
        self.assertEqual(world.game.loaded_documents(), [])
        with world.game, quiet():
            window.Show()
        self.assertEqual(board(window).placement, ("position", 300.0, 120.0, (0.0, 0.0)))
        self.assertTrue(model(window)["placed"])
        with world.game, quiet():
            window.Destroy()
        self.assertEqual(world.game.loaded_documents(), [])

    def test_a_refresh_while_hidden_reaches_the_next_show(self):
        world = World(True)
        window = world.open("STATUS")
        with world.game, quiet():
            window.Hide()
            world.game.status[P["LEVEL"]] = 100
            window.RefreshStatus()
            window.Show()
        self.assertEqual(model(window)["level"], "100")

    def test_a_press_raises_the_window_once(self):
        world = World(True)
        window = world.open("SKILL")
        raised = []
        original = window.SetTop
        window.SetTop = lambda: (raised.append(1), original())
        with world.game, quiet():
            press(window, "skill_press", 20, 0)
        self.assertEqual(raised, [1])

    def test_the_plain_tooltips_are_novaui_s_while_the_tooltips_flag_is_on(self):
        world = World(True, windows="+character,+tooltips")
        made = []

        class PlainToolTip(support.PlainToolTip):
            def __init__(self, width=190):
                support.PlainToolTip.__init__(self, width)
                made.append(width)
        world.game.put("nui_item_tooltip", types.SimpleNamespace(PlainToolTip=PlainToolTip))
        window = world.make()
        self.assertEqual(made, [190, 190, 130, 190])
        for name in ("toolTip", "toolTipJob", "toolTipAlignment", "emotionToolTip"):
            self.assertIsInstance(getattr(window, name), PlainToolTip, name)
        legacy = World(True).make()
        self.assertIsInstance(legacy.toolTip, support.PlainToolTip, "the flag off: legacy's own")


# --- the fixtures and the markup -----------------------------------------------------------------------------

def kind(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


def fixture(variant=None):
    name = "character.%s.fixture.json" % variant if variant else "character.fixture.json"
    return json.loads(read(os.path.join(WINDOWS, "character", name)))["character"]


class Fixtures(CharacterTest):
    VARIANTS = (None, "skill", "emoticon", "quest", "foundation", "skill-foundation", "emoticon-foundation",
                "quest-foundation", "noguild", "hover")

    def test_every_fixture_holds_the_model_s_keys_with_their_kinds(self):
        world = World(True)
        window = world.open("SKILL")
        live = model(window)
        for variant in self.VARIANTS:
            data = fixture(variant)
            with self.subTest(variant=variant):
                self.assertEqual(sorted(data), sorted(live))
                for key, value in live.items():
                    self.assertEqual(kind(data[key]), kind(value), key)
                for key in ("skills", "support", "solo", "dual", "quests", "quest_cells"):
                    self.assertEqual(len(data[key]), len(live[key]), key)
                    self.assertEqual(sorted(data[key][0]), sorted(live[key][0]), key)

    def test_the_fixtures_are_current(self):
        process = subprocess.run([sys.executable, "-B", os.path.join(support.support.HERE, "nui_w3c_fixtures.py"), "--check",
                                  "--window", "character"], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_every_data_event_has_a_handler_and_every_grid_binds_attach_right(self):
        markup = read(os.path.join(WINDOWS, "character", "character.rml"))
        world = World(True)
        handlers = set()
        for value in vars(world.m("nui_character")._CharacterBoard).values():
            handlers.update(getattr(value, "_nui_events", ()))
        events = set(re.findall(r'data-event-[a-z]+="([a-z_]+)\(', markup))
        self.assertEqual(events - handlers, set())
        grids = re.findall(r'<div id="(char-[a-z-]+)" class="nui-slot-grid[^"]*"([^>]*)>', markup)
        self.assertEqual(sorted(name for name, _ in grids), ["char-dual", "char-quest-cells", "char-skills", "char-solo",
                                                             "char-support"])
        for name, attributes in grids:
            self.assertIn('data-class-nui-attach-right="attach_right"', attributes, name)

    def test_the_board_draws_in_its_legacy_window_s_band(self):
        """Legacy's window lives in the UI layer (ui.ScriptWindow's default),
        so the board draws below that layer, as the Wave 3b item windows'."""
        body = re.search(r"<body[^>]*\bclass=\"([^\"]*)\"", read(os.path.join(WINDOWS, "character", "character.rml")))
        self.assertIn("nui-below-legacy-ui", body.group(1).split())
        source = read(os.path.join(ROOT, "uicharacter.py"))
        self.assertIn("ui.ScriptWindow.__init__(self)\n", source, "no layer argument: the UI layer")


@unittest.skipUnless(NUITOOL, "set NUITOOL to a nuitool build (or put nuitool on PATH)")
class ElementCounts(unittest.TestCase):
    """D3: one panel instanced; nuitool snap --stats counts each tab's elements."""

    def test_each_tab_instances_only_its_panel(self):
        work = tempfile.mkdtemp(prefix="nui-char-")
        self.addCleanup(shutil.rmtree, work, True)
        repo = os.path.normpath(os.path.join(support.support.HERE, ".."))
        counts = {}
        for variant in ("", "skill", "emoticon", "quest"):
            stats = os.path.join(work, "stats.json")
            name = "character.%s.fixture.json" % variant if variant else "character.fixture.json"
            command = [NUITOOL, "snap", "--root", "assets/nui", "--root", "assets/icon", "--root", "assets/ETC", "--root",
                       "assets/locale", "--root", "assets/season1", "--locale", "assets/locale/locale/en", "--doc", DOCUMENT,
                       "--theme", "modern-dark", "--scale", "1", "--size", "340x480", "--fixture",
                       "assets/nui/nui/windows/character/" + name, "--out", os.path.join(work, "out.png"), "--stats", stats]
            process = subprocess.run(command, capture_output=True, text=True, cwd=repo)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            with open(stats, encoding="utf-8") as handle:
                counts[variant or "status"] = json.load(handle)["elements"]
        self.assertLess(counts["quest"], counts["skill"])
        self.assertLess(counts["status"], counts["skill"])
        self.assertLess(counts["skill"], 700, counts)


if __name__ == "__main__":
    unittest.main()
