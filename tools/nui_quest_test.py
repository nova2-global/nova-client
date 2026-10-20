"""Tests for the NovaUI quest dialog and curtain (assets/root/nui_quest.py,
nui_quest_curtain.py, nui/windows/quest/, nui/windows/quest-curtain/) and the
Wave 5a wiring of interfacemodule.py and game.py (P12 spec 6.1, 6.2, 6.6):
python3 -B -m unittest nui_quest_test (from tools/).

Plain CPython over nui_game_support's stand-ins; install_wave5a_ui loads the
real legacy uiquest.py with its uiscript. The Interface's quest methods
(OpenQuestWindow, RemoveQuestDialog, __HideWindows, __ShowWindows) are
compiled from interfacemodule.py, so the wiring under test is the real one.

- facade: every method of P12 spec 6.1.7 exists on nui_quest.QuestDialog
  with legacy's signature, and the class constants have legacy's values;
- differential: the legacy and the NovaUI dialog, each in a world of its own,
  are made as the Interface makes them and driven by the same interpreter
  callbacks (those the engine's replay recorded, tools/fixtures/quest_cases.json,
  a copy of the client's tests/fixtures/nui/quest/cases.json; the sequences of
  6.1.9 without it), then the same keys and presses. They
  make the same event and net calls in order (the interpreter's layout calls,
  which only place legacy's widgets, left out: UpdateEventSet,
  RenderEventSet, SetEventSetWidth, Add/GetEventSetLocalYPosition,
  GetLineCount, InsertText, InsertTextInline), leave uiQuest's three module
  globals the same, write the same curtain modes, and leave the same done
  events and HUD windows; legacy's curtain is updated until it rests;
- fixtures: every fixture holds every model key with its kind, every feed
  file follows the shape of quest.<index>.lines (P12 spec 3.2);
- on demand: no board for skin 0, the board made at construction and gone
  at CloseSelf, nui_discard leaves the event set alone;
- the curtain: the bars and their board at 4:3 and 16:9, the done events,
  the fades and their duration classes, reduced motion, phase end;
- the HUD: the windows a skinned dialog hides are legacy's, and they show
  again at the curtain's Close;
- wiring and no per-frame Python."""
import ast
import contextlib
import gc
import inspect
import io
import json
import os
import sys
import types
import unittest
import weakref
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402

ROOT = support.ROOT
WINDOWS = os.path.normpath(os.path.join(support.support.HERE, "..", "assets", "nui", "nui", "windows"))
QUEST_DIR = os.path.join(WINDOWS, "quest")
CURTAIN_DIR = os.path.join(WINDOWS, "quest-curtain")
DOCUMENT = "nui/windows/quest/quest.rml"
CURTAIN_DOCUMENT = "nui/windows/quest-curtain/quest-curtain.rml"
KEY_ESCAPE, KEY_RETURN, KEY_NUMPADENTER, KEY_TAB = 81, 72, 61, 70
KEY_UP, KEY_DOWN = 91, 93

# The event functions that only lay legacy's widgets out (P12 spec 6.1.9).
LAYOUT = ("UpdateEventSet", "RenderEventSet", "SetEventSetWidth", "AddEventSetLocalYPosition",
          "GetEventSetLocalYPosition", "GetLineCount", "InsertText", "InsertTextInline",
          "RegisterEventSetFromString")

CASES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "quest_cases.json")

# The interpreter's callbacks for the replay fixtures (P12 spec 6.1.9), as the
# spec gives them; the copy of the engine's cases.json replaces them.
SPEC_SEQUENCES = {
    "npc-menu": (1, [("MakeQuestion", 2), ("AppendQuestion", "OX contest", 0), ("AppendQuestion", "Close", 1)]),
    "ox-page-1": (1, [("MakeNextButton", 0)]),
    "ox-page-2": (1, [("MakeNextButton", 1), ("DoneEvent",)]),
    "warp-question": (1, [("MakeQuestion", 2), ("AppendQuestion", "Yes", 0), ("AppendQuestion", "No", 1)]),
    "name-input": (1, [("OnInput",)]),
    "name-too-long": (1, [("MakeNextButton", 1), ("DoneEvent",)]),
    "done-only": (0, [("MakeNextButton", 1), ("DoneEvent",)]),
    "letter-button": (0, [("MakeNextButton", 1), ("DoneEvent",)]),
    "icons": (1, [("OnInsertItemIcon", "item", 27001, "Red Potion (S)", "", 0, 3),
                  ("OnInsertItemIcon", "item", 27002, "Red Potion (M)", "", 1, 3),
                  ("OnInsertItemIcon", "item", 27003, "Red Potion (L)", "", 2, 3),
                  ("OnInsertItemIcon", "item", 50001, "", "", 0, 1), ("MakeNextButton", 1), ("DoneEvent",)]),
    "confirm": (1, [("MakeNextButton", 2)]),
    "cinema": (5, [("MakeNextButton", 0)]),
    "many-choices": (1, [("MakeQuestion", 10)] + [("AppendQuestion", name, i) for i, name in enumerate(
        ("One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Close"))]),
}



def recorded_sequences():
    """{fixture: (skin, [callback, ...])} from the copy of the engine's replay
    cases (tools/fixtures/quest_cases.json, byte-identical to the client's
    tests/fixtures/nui/quest/cases.json): the handler's calls of each case in
    order. A case's other entries (the Interface's RecvQuest, the replay's
    EndEventProcess at a fade's end) are not the dialog's."""
    with open(CASES, encoding="utf-8") as handle:
        cases = json.load(handle)
    found = {}
    for case in cases:
        if case.get("refused"):
            continue
        calls = [tuple(call[1:]) for call in case["final"]["calls"] if call[0] == "handler"]
        found[case["name"]] = (case["skin"], calls)
    return found


SEQUENCES = recorded_sequences() if os.path.exists(CASES) else dict(SPEC_SEQUENCES)
# The confirm wait ends from the second set (END_CONFIRM_WAIT calls CloseSelf);
# the input flows run before it.
CONFIRM_END = ("CloseSelf",)
if SEQUENCES.get("confirm", (1, []))[1][-1:] == [CONFIRM_END]:
    SEQUENCES["confirm"] = (SEQUENCES["confirm"][0], SEQUENCES["confirm"][1][:-1])

HUD = ("wndTaskBar", "wndCharacter", "wndInventory", "wndMiniMap", "wndGuild", "wndMessenger", "wndChat",
       "wndParty", "wndGameButton", "wndEnergyBar", "wndExpandedTaskBar", "wndDragonSoul", "wndDragonSoulRefine")


def quiet():
    """The legacy curtain prints banners."""
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class HudWindow(object):
    """A HUD window the Interface hides and shows (a facade or a legacy one)."""

    def __init__(self, name, shown=True):
        self.name = name
        self.shown = shown

    def Show(self):
        self.shown = True

    def Hide(self):
        self.shown = False

    def IsShow(self):
        return self.shown

    def IsEditMode(self):
        return False

    def CloseChat(self):
        pass


def interface_class(namespace):
    """The Interface's quest methods, compiled from interfacemodule.py into a
    class of the same name, so their private names mangle as they do there."""
    methods = support.source_of("interfacemodule.py", ("OpenQuestWindow", "RemoveQuestDialog", "__HideWindows",
                                                       "__ShowWindows"), inside="Interface")
    body = "\n".join("\t" + line if line else line for line in methods.split("\n"))
    source = ("class Interface(InterfaceBase):\n" + body + "\n")
    exec(compile(source, "interfacemodule.py", "exec"), namespace)
    return namespace["Interface"]


class InterfaceBase(object):
    def __init__(self, hidden=()):
        self.wndQuestWindow = {}
        self.wndQuestWindowNewKey = 0
        self.questButtonSuppressed = False
        self.quest_buttons = True
        self.whisper_buttons = True
        for name in HUD:
            setattr(self, name, HudWindow(name, name not in hidden))

    def HideAllQuestButton(self):
        self.quest_buttons = False

    def ShowAllQuestButton(self):
        self.quest_buttons = True

    def HideAllWhisperButton(self):
        self.whisper_buttons = False

    def ShowAllWhisperButton(self):
        self.whisper_buttons = True

    def hud(self):
        """The HUD windows shown, and the edge buttons."""
        return (tuple(name for name in HUD if getattr(self, name).IsShow()), self.quest_buttons, self.whisper_buttons)


class World(object):
    """One world: a Game with the legacy uiquest.py and the NovaUI quest
    modules over its stand-ins, the quest flag on when `nui_on`, a screen of
    `screen` pixels, and the Interface's quest methods."""

    def __init__(self, nui_on, engine=True, screen=(1600, 900), windows="+rest", reduced=False):
        game = self.game = support.Game(engine=engine)
        support.install_wave5a_ui(game)
        game.modules["systemSetting"].GetUINuiWindows = lambda: windows if nui_on else ""
        wndmgr = game.modules["wndMgr"]
        wndmgr.GetScreenWidth = lambda: screen[0]
        wndmgr.GetScreenHeight = lambda: screen[1]
        game.state.reduced_motion = reduced
        game.state.field_events[(DOCUMENT, "quest-input")] = "field"
        game.state.maxlength[(DOCUMENT, "quest-input")] = 30
        game.load_standard()
        with quiet():
            self.uiQuest = game.load("uiQuest", "uiquest.py")
            self.uiQuest.print = lambda *args, **kwargs: None
            game.load("nui_quest_curtain", "nui_quest_curtain.py")
            self.nui_quest = game.load("nui_quest", "nui_quest.py")
        self.nui_windows = game.loaded["nui_windows"]
        self.nui_on = nui_on
        self.curtain_modes = []
        # Legacy's curtain moves by the time between its updates.
        self.clock = [0.0]
        self.uiQuest.time = types.SimpleNamespace(perf_counter=lambda: self.clock[0])
        namespace = {"ui": game.modules["ui"], "uiQuest": self.uiQuest, "nui_windows": self.nui_windows,
                     "app": game.modules["app"], "IsQBHide": False, "InterfaceBase": InterfaceBase}
        self.Interface = interface_class(namespace)
        self.interface = self.Interface()
        self._install_recording_curtain()
        # Set 0 is taken, so the dialogs under test get sets legacy clears.
        game.modules["event"].RegisterEventSetFromString("[DONE]")

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def _install_recording_curtain(self):
        """A curtain that records the modes the dialogs write (not its own)."""
        modes = self.curtain_modes
        if self.nui_on:
            base = self.nui_quest.QuestCurtain

            class Curtain(base):
                @property
                def CurtainMode(self):
                    return self._mode

                @CurtainMode.setter
                def CurtainMode(self, mode):
                    modes.append(mode)
                    self._set_mode(mode)

            curtain = Curtain()
            self.nui_quest._curtain[0] = curtain
        else:
            base = self.uiQuest.QuestCurtain

            class Curtain(base):
                _own = 0

                def __init__(self):
                    self._own = 1
                    base.__init__(self)
                    self._own = 0

                def __setattr__(self, name, value):
                    if name == "CurtainMode" and not self._own:
                        modes.append(value)
                    object.__setattr__(self, name, value)

                def Close(self):
                    self._own += 1
                    try:
                        base.Close(self)
                    finally:
                        self._own -= 1

                def OnUpdate(self):
                    self._own += 1
                    try:
                        base.OnUpdate(self)
                    finally:
                        self._own -= 1

            with self.game, quiet():
                self.uiQuest.QuestCurtain.BarHeight = self.bar_height()
                curtain = Curtain()
        self.uiQuest.QuestDialog.QuestCurtain = curtain
        self.uiQuest.QuestCurtain.OnDoneEventList = []

    def bar_height(self):
        wndmgr = self.game.modules["wndMgr"]
        height = (wndmgr.GetScreenHeight() - wndmgr.GetScreenWidth() * 9 // 16) // 2
        return height if height >= 0 else 50

    @property
    def curtain(self):
        return self.uiQuest.QuestDialog.QuestCurtain

    # --- dialogs ---------------------------------------------------------------------

    def open(self, skin, script="[DONE]"):
        """A script packet: the set registered, the Interface's OpenQuestWindow.
        Returns (index, the dialog the Interface keeps, its event handler)."""
        with self.game, quiet():
            index = self.game.modules["event"].RegisterEventSetFromString(script)
            key = self.interface.wndQuestWindowNewKey
            self.interface.OpenQuestWindow(skin, index)
        dialog = self.interface.wndQuestWindow[key]
        return index, dialog, self.handler(index)

    def handler(self, index):
        """The object the interpreter calls back for set `index` (the last
        SetEventHandler)."""
        for name, args in reversed(self.game.log):
            if name == "event.SetEventHandler" and args[0] == index:
                return args[1]
        return None

    def call(self, handler, *callback):
        """An interpreter callback, as C++ calls it."""
        with self.game, quiet():
            return getattr(handler, callback[0])(*callback[1:])

    def settle(self):
        """Legacy's curtain and fades move on its OnUpdate; run it until they
        rest. The NovaUI curtain needs nothing at 16:9."""
        if self.nui_on:
            return
        with self.game, quiet():
            for _ in range(20):
                self.clock[0] += 0.05
                self.curtain.OnUpdate()

    def board(self, dialog):
        board = dialog._board() if hasattr(dialog, "_board") else None
        return board

    def effects(self):
        """The event and net calls with an effect, in order: the layout calls,
        the getters and the handler's identity left out."""
        found = []
        for name, args in self.game.log:
            module, _, function = name.partition(".")
            if module == "event" and function not in LAYOUT and not support.is_getter(name):
                if function == "SetEventHandler":
                    args = args[:1]
                found.append((name, args))
            elif module == "net":
                found.append((name, args))
        return found

    def globals(self):
        q = self.uiQuest
        return (q.cur_questpage_number, q.entire_questbutton_number, q.entire_questpage_number)

    def done_events(self):
        return len(self.uiQuest.QuestCurtain.OnDoneEventList)

    def snapshot(self):
        """What the differential tests compare after each step."""
        return {"effects": self.effects(), "globals": self.globals(), "modes": list(self.curtain_modes),
                "done_events": self.done_events(), "hud": self.interface.hud(),
                "dialogs": sorted(self.interface.wndQuestWindow)}


# --- the inputs, legacy and NovaUI ------------------------------------------------------------------

def press_key(world, dialog, key):
    """A key while the dialog shows: legacy's lock window gives it OnKeyDown
    (Enter, Up, Down) or OnPressEscapeKey; NovaUI's board its keydown."""
    app = world.game.modules["app"]
    with world.game, quiet():
        if world.nui_on and world.board(dialog) is not None:
            identifier = {"escape": KEY_ESCAPE, "enter": KEY_RETURN, "up": KEY_UP, "down": KEY_DOWN,
                          "numpad-enter": KEY_NUMPADENTER, "tab": KEY_TAB}[key]
            return world.board(dialog).key("", identifier)
        if key == "escape":
            return dialog.OnPressEscapeKey()
        if key == "numpad-enter":
            return True
        return dialog.OnKeyDown({"enter": app.DIK_RETURN, "up": app.DIK_UP, "down": app.DIK_DOWN, "tab": 0x0F}[key])


def press_choice(world, dialog, index):
    with world.game, quiet():
        if world.nui_on and world.board(dialog) is not None:
            world.board(dialog).fire("choose", index, 0)
        else:
            dialog.btnAnswer[index].Click()


def press_next(world, dialog):
    with world.game, quiet():
        if world.nui_on and world.board(dialog) is not None:
            world.board(dialog).fire("next", 0)
        else:
            dialog.btnNext.Click()


def press_page(world, dialog, step):
    with world.game, quiet():
        if world.nui_on and world.board(dialog) is not None:
            world.board(dialog).fire("pager", step, 0)
        elif step > 0:
            dialog.nextbutton.Click()
        else:
            dialog.prevbutton.Click()


def type_text(world, dialog, text):
    with world.game, quiet():
        if world.nui_on and world.board(dialog) is not None:
            world.board(dialog).insert_text("quest-input", text)
        else:
            dialog.editLine.type(text)


def enter_field(world, dialog):
    with world.game, quiet():
        if world.nui_on and world.board(dialog) is not None:
            world.board(dialog).insert_text("quest-input", "\n")
        else:
            dialog.OnIMEReturn()


def escape_field(world, dialog):
    with world.game, quiet():
        if world.nui_on and world.board(dialog) is not None:
            return world.board(dialog).key("quest-input", KEY_ESCAPE)
        return dialog.OnPressEscapeKey()


# --- the facade ---------------------------------------------------------------------------------------

FACADE_METHODS = (
    "__init__", "LoadDialog", "OnCancel", "CloseSelf", "Destroy", "AddOnCloseEvent", "AddOnDoneEvent",
    "SetOnCloseEvent", "SetEventSetPosition", "AdjustEventSetPosition", "MakeNextButton", "MakeQuestion",
    "MakeEachButton", "MakeNextPrevPageButton", "RefreshQuestPage", "NextQuestPageEvent", "PrevQuestPageEvent",
    "ClickAnswerEvent", "AppendQuestion", "FadeOut", "FadeIn", "WhiteOut", "WhiteIn", "DoneEvent", "OnKeyDown",
    "OnPressEscapeKey", "OnIMEReturn", "OnIMEUpdate", "OnInput", "OnImage", "OnInsertItemIcon", "OnInsertImage",
    "OnSize", "OnTitleImage", "OnLeftImage", "OnTopImage", "OnBackgroundImage")
# The ui.ScriptWindow calls callers make (P12 spec 6.0), and the protocol of make().
SCRIPT_WINDOW_CALLS = (("Show", ()), ("Hide", ()), ("IsShow", ()), ("SetTop", ()), ("SetCenterPosition", ()),
                       ("GetWidth", ()), ("GetHeight", ()), ("Lock", ()), ("Unlock", ()),
                       ("SetWindowName", ("QuestWindow1",)))


def parameters(function):
    return [(p.name, p.kind, p.default) for p in inspect.signature(function).parameters.values()]


class ReplayCases(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(CASES), "no copy of the engine's cases.json")
    def test_the_recorded_callbacks_are_the_specs_but_the_item_icons_desc(self):
        recorded = recorded_sequences()
        for name, (skin, calls) in SPEC_SEQUENCES.items():
            self.assertIn(name, recorded)
            self.assertEqual(recorded[name][0], skin, name)
            got = list(recorded[name][1])
            if name == "confirm":
                self.assertEqual(got[-1:], [CONFIRM_END], "END_CONFIRM_WAIT closes the first set's dialog")
                got = got[:-1]
            if name == "icons":
                # The interpreter reads title and desc through one argument
                # buffer, so an item icon's desc arrives as its title.
                got = [call[:4] + ("",) + call[5:] if call[0] == "OnInsertItemIcon" and call[3] else call for call in got]
            self.assertEqual(got, [tuple(call) for call in calls], name)

    @unittest.skipUnless(os.path.exists(CASES), "no copy of the engine's cases.json")
    def test_every_recorded_callback_is_a_facade_method(self):
        world = World(True)
        for name, (skin, calls) in recorded_sequences().items():
            for call in calls:
                self.assertTrue(callable(getattr(world.nui_quest.QuestDialog, call[0], None)), "%s: %s" % (name, call[0]))


class Facade(unittest.TestCase):
    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)
        self.legacy = self.world.uiQuest.QuestDialog
        self.novaui = self.world.nui_quest.QuestDialog

    def test_every_method_of_the_legacy_dialog_exists_with_its_signature(self):
        for name in FACADE_METHODS:
            self.assertTrue(callable(getattr(self.legacy, name, None)), "legacy has %s" % name)
            self.assertTrue(callable(getattr(self.novaui, name, None)), "NovaUI has %s" % name)
            self.assertEqual(parameters(getattr(self.novaui, name)), parameters(getattr(self.legacy, name)), name)

    def test_the_class_constants_are_legacys(self):
        for name in ("TITLE_STATE_NONE", "TITLE_STATE_APPEAR", "TITLE_STATE_SHOW", "TITLE_STATE_DISAPPEAR",
                     "SKIN_NONE", "SKIN_CINEMA", "QUEST_BUTTON_MAX_NUM"):
            self.assertEqual(getattr(self.novaui, name), getattr(self.legacy, name), name)
        self.assertIs(self.novaui.NUI_FACADE, True)

    def test_the_facade_answers_the_script_window_calls_and_keeps_legacys_attributes(self):
        index, dialog, handler = self.world.open(1)
        self.assertIs(handler, dialog)
        self.assertIsInstance(dialog, self.novaui)
        for name, args in SCRIPT_WINDOW_CALLS:
            getattr(dialog, name)(*args)
        dialog.Show()
        self.assertTrue(dialog.IsShow())
        for name, value in (("skin", 1), ("descIndex", index), ("focusIndex", 0), ("sx", 0), ("sy", 0),
                            ("nextCurtainMode", 0), ("needInputString", False), ("bCancelled", False),
                            ("btnAnswer", None), ("btnNext", None)):
            self.assertEqual(getattr(dialog, name), value, name)
        self.assertTrue(callable(dialog.OnCloseEvent), "the Interface's close events")

    def test_legacys_per_frame_driver_is_not_on_the_facade(self):
        self.assertTrue(hasattr(self.legacy, "OnUpdate"))
        self.assertFalse(hasattr(self.novaui, "OnUpdate"))
        self.assertFalse(hasattr(self.novaui, "OnRender"))


# --- the differential flows ---------------------------------------------------------------------------

def key(name):
    return lambda world, dialog: press_key(world, dialog, name)


def choice(index):
    return lambda world, dialog: press_choice(world, dialog, index)


def page(step):
    return lambda world, dialog: press_page(world, dialog, step)


def next_button(world, dialog):
    press_next(world, dialog)


def typed(text):
    return lambda world, dialog: type_text(world, dialog, text)


class Differential(unittest.TestCase):
    """Each flow runs in a legacy and a NovaUI world; after the dialog is made,
    after each callback and after each input the snapshots must agree."""

    maxDiff = None

    def flow(self, fixture, inputs=(), skin=None, before=None):
        sequence_skin, callbacks = SEQUENCES[fixture] if isinstance(fixture, str) else fixture
        skin = sequence_skin if skin is None else skin
        results = []
        for nui_on in (False, True):
            world = World(nui_on)
            with world:
                if before is not None:
                    before(world)
                index, dialog, handler = world.open(skin)
                self.assertEqual(type(dialog).__module__, "nui_quest" if nui_on else "uiQuest")
                world.settle()
                snapshots = [world.snapshot()]
                for callback in callbacks:
                    world.call(handler, *callback)
                    world.settle()
                    snapshots.append(world.snapshot())
                for step in inputs:
                    step(world, dialog)
                    world.settle()
                    snapshots.append(world.snapshot())
            results.append((world, snapshots))
        (legacy, legacy_snaps), (novaui, novaui_snaps) = results
        for step, (a, b) in enumerate(zip(legacy_snaps, novaui_snaps)):
            self.assertEqual(b, a, "%s, step %d" % (fixture if isinstance(fixture, str) else "custom", step))
        return legacy, novaui, legacy_snaps[-1]

    def sent(self, snapshot):
        return [entry for entry in snapshot["effects"] if entry[0] in ("event.SelectAnswer", "net.SendQuestCancelPacket",
                                                                    "net.SendQuestInputStringPacket", "event.ClearEventSet")]

    def test_the_npc_menu_answers_the_choice_pressed(self):
        legacy, novaui, last = self.flow("npc-menu", [choice(0)])
        self.assertEqual(self.sent(last), [("event.SelectAnswer", (1, 0)), ("event.ClearEventSet", (1,))])
        self.assertEqual(last["dialogs"], [])

    def test_enter_answers_the_first_answer_without_an_arrow(self):
        legacy, novaui, last = self.flow("npc-menu", [key("enter")])
        self.assertEqual(self.sent(last)[0], ("event.SelectAnswer", (1, 0)))

    def test_down_then_enter_answers_the_second_and_up_wraps_to_the_last(self):
        legacy, novaui, last = self.flow("npc-menu", [key("down"), key("enter")])
        self.assertEqual(self.sent(last)[0], ("event.SelectAnswer", (1, 1)))
        legacy, novaui, last = self.flow("npc-menu", [key("up"), key("enter")])
        self.assertEqual(self.sent(last)[0], ("event.SelectAnswer", (1, 1)))

    def test_escape_on_the_menu_answers_the_last_choice_and_cancels(self):
        legacy, novaui, last = self.flow("npc-menu", [key("escape")])
        self.assertEqual(self.sent(last), [("event.SelectAnswer", (1, 1)), ("net.SendQuestCancelPacket", ()),
                                           ("event.ClearEventSet", (1,))])

    def test_a_next_page_goes_on_by_enter_escape_or_its_button(self):
        for step in (key("enter"), key("escape"), next_button):
            legacy, novaui, last = self.flow("ox-page-1", [step])
            self.assertEqual(self.sent(last), [("event.SelectAnswer", (1, 254)), ("event.ClearEventSet", (1,))])
            self.assertEqual(last["modes"], [1, 1, 0], "the bars stay for the next page")

    def test_the_arrows_without_answers_change_nothing_but_the_hover(self):
        legacy, novaui, last = self.flow("ox-page-1", [key("up"), key("down"), key("numpad-enter"), key("tab")])
        self.assertEqual(self.sent(last), [])
        board = novaui.board(novaui.interface.wndQuestWindow[0])
        self.assertTrue(board.model["next_hover"])
        board.fire("next_out")
        self.assertFalse(board.model["next_hover"], "until the pointer leaves the button")

    def test_a_done_page_closes_and_the_curtain_runs_the_done_events(self):
        for step in (key("enter"), key("escape"), next_button):
            legacy, novaui, last = self.flow("ox-page-2", [step])
            self.assertEqual(self.sent(last), [("event.ClearEventSet", (1,))], "OK sends nothing")
            self.assertEqual(last["modes"], [1, 1, -1])
            self.assertEqual(last["done_events"], 0)
            self.assertEqual(last["hud"][0], HUD, "the HUD is back")

    def test_the_teleporter_question_follows_the_arrows(self):
        legacy, novaui, last = self.flow("warp-question", [key("down"), key("down"), key("up"), key("enter")])
        self.assertEqual(self.sent(last)[0], ("event.SelectAnswer", (1, 1)), "No")
        board_focus = []
        world = World(True)
        with world:
            index, dialog, handler = world.open(1)
            for callback in SEQUENCES["warp-question"][1]:
                world.call(handler, *callback)
            board = world.board(dialog)
            self.assertEqual(board.model["focus_index"], -1, "no focus shown before an arrow")
            for name in ("down", "down", "up"):
                press_key(world, dialog, name)
                board_focus.append(board.model["focus_index"])
        self.assertEqual(board_focus, [1, 0, 1])

    def test_input_sends_the_typed_name_on_enter(self):
        legacy, novaui, last = self.flow("name-input", [typed("nuiw5atoolongname"), enter_field])
        self.assertEqual(self.sent(last), [("net.SendQuestInputStringPacket", ("nuiw5atoolongname",)),
                                           ("event.ClearEventSet", (1,))])

    def test_input_sends_the_text_typed_so_far_on_escape(self):
        legacy, novaui, last = self.flow("name-input", [typed("nuiw5aescapecase1"), escape_field])
        self.assertEqual(self.sent(last)[0], ("net.SendQuestInputStringPacket", ("nuiw5aescapecase1",)))

    def test_the_input_field_takes_the_focus_and_keeps_thirty_characters(self):
        world = World(True)
        with world:
            index, dialog, handler = world.open(1)
            world.call(handler, "OnInput")
            board = world.board(dialog)
            self.assertEqual(board.focused, "quest-input")
            type_text(world, dialog, "x" * 40)
            self.assertEqual(board.fields["quest-input"], "x" * 30)

    def test_the_too_long_page_and_the_icons_close_on_ok(self):
        for fixture in ("name-too-long", "icons"):
            legacy, novaui, last = self.flow(fixture, [next_button])
            self.assertEqual(self.sent(last), [("event.ClearEventSet", (1,))], fixture)

    def test_a_skin_0_dialog_closes_at_its_done_and_takes_the_bars_out(self):
        for fixture in ("done-only", "letter-button"):
            legacy, novaui, last = self.flow(fixture)
            self.assertEqual(last["dialogs"], [], fixture)
            self.assertEqual(last["modes"], [1, -1, -1], "1 then -1 at construction, -1 at its close")
            self.assertEqual(self.sent(last), [("event.ClearEventSet", (1,))])

    def test_a_skin_0_dialog_after_an_answer_brings_the_hud_back(self):
        def answered(world):
            index, dialog, handler = world.open(1)
            for callback in SEQUENCES["npc-menu"][1]:
                world.call(handler, *callback)
            press_choice(world, dialog, 0)
            world.settle()
            self.assertEqual(world.interface.hud()[0], (), "hidden while the bars stay in")
        legacy, novaui, last = self.flow("done-only", before=answered)
        self.assertEqual(last["hud"][0], HUD)
        self.assertEqual(last["done_events"], 0)

    def test_the_confirm_wait_cancels_on_escape_and_on_its_button(self):
        for step in (key("escape"), next_button):
            legacy, novaui, last = self.flow("confirm", [step])
            self.assertEqual(self.sent(last), [("event.SelectAnswer", (1, 254)), ("net.SendQuestCancelPacket", ()),
                                               ("event.ClearEventSet", (1,))])

    def test_the_confirm_wait_closes_when_the_other_set_ends_it(self):
        def end_confirm(world, dialog):
            with world.game, quiet():
                dialog.CloseSelf()
        legacy, novaui, last = self.flow("confirm", [end_confirm])
        self.assertEqual(self.sent(last), [("event.ClearEventSet", (1,))])

    def test_cinema_goes_on_with_enter(self):
        legacy, novaui, last = self.flow("cinema", [key("enter")])
        self.assertEqual(self.sent(last), [("event.SelectAnswer", (1, 254)), ("event.ClearEventSet", (1,))])

    def test_ten_answers_page_and_the_arrows_wrap_over_all_of_them(self):
        legacy, novaui, last = self.flow("many-choices", [page(1), page(-1), key("up"), key("enter")])
        self.assertEqual(self.sent(last)[0], ("event.SelectAnswer", (1, 9)))
        world = World(True)
        with world:
            index, dialog, handler = world.open(1)
            for callback in SEQUENCES["many-choices"][1]:
                world.call(handler, *callback)
            board = world.board(dialog)
            press_page(world, dialog, 1)
            self.assertEqual((board.model["choice_page"], world.uiQuest.cur_questpage_number), (1, 2))
            press_page(world, dialog, 1)
            self.assertEqual(board.model["choice_page"], 1, "no page after the last")
            press_key(world, dialog, "up")
            self.assertEqual(board.model["focus_index"], 9)
            self.assertEqual(board.model["choice_page"], 1, "the focus does not move the page")

    def test_escape_while_a_page_types_answers_the_last_question_any_dialog_made(self):
        def five_answers(world):
            index, dialog, handler = world.open(1)
            world.call(handler, "MakeQuestion", 5)
            for i in range(5):
                world.call(handler, "AppendQuestion", "answer %d" % i, i)
            press_choice(world, dialog, 0)
            world.settle()
        legacy, novaui, last = self.flow("ox-page-1", [key("escape")], before=five_answers)
        # A dialog of its own, typing (no callback yet): the escape below.
        for nui_on in (False, True):
            world = World(nui_on)
            with world:
                five_answers(world)
                index, dialog, handler = world.open(1)
                press_key(world, dialog, "escape")
                selects = [args for name, args in world.effects() if name == "event.SelectAnswer"]
                self.assertEqual(selects[-1], (index, 4), "the module global, as legacy (D11)")

    def test_up_and_down_over_three_answers_wrap_both_ways(self):
        three = (1, [("MakeQuestion", 3)] + [("AppendQuestion", name, i) for i, name in enumerate(("A", "B", "C"))])
        for keys, answer in (([key("down")] * 3, 0), ([key("up")] * 2, 1), ([key("down"), key("up"), key("up")], 2)):
            legacy, novaui, last = self.flow(three, keys + [key("enter")])
            self.assertEqual(self.sent(last)[0], ("event.SelectAnswer", (1, answer)))

    def test_every_recorded_case_then_escape_matches_legacy(self):
        for fixture in sorted(SEQUENCES):
            legacy, novaui, last = self.flow(fixture, [key("escape")])
            self.assertEqual(last["dialogs"], [], fixture)

    def test_escape_on_a_typing_page_answers_255_without_a_question_before(self):
        for nui_on in (False, True):
            world = World(nui_on)
            with world:
                index, dialog, handler = world.open(1)
                press_key(world, dialog, "escape")
                selects = [args for name, args in world.effects() if name == "event.SelectAnswer"]
                self.assertEqual(selects, [(index, -1)], "entire_questbutton_number - 1, sent as 255 by C++")


class BusyBoard(unittest.TestCase):
    def test_a_second_skinned_dialog_is_legacys_while_a_board_shows(self):
        world = World(True)
        with world:
            first, a, handler_a = world.open(1)
            second, b, handler_b = world.open(1)
            self.assertIsInstance(b, world.nui_quest.QuestDialog)
            self.assertIsInstance(handler_b, world.uiQuest.QuestDialog, "the interpreter calls legacy's dialog")
            self.assertTrue(b.nui_ready())
            b.nextCurtainMode = -1
            self.assertEqual(handler_b.nextCurtainMode, -1, "attributes reach the legacy dialog")
            world.call(handler_b, "MakeNextButton", 0)
            press_key(world, handler_b, "enter")
            self.assertIn(("event.SelectAnswer", (second, 254)), world.effects())
            self.assertIsNotNone(world.board(a), "the first keeps its board")

    def test_a_busy_delegate_that_closes_is_hidden_and_let_go(self):
        world = World(True)
        with world:
            first, a, handler_a = world.open(1)
            second, b, handler_b = world.open(1)
            nui_hud = world.game.loaded["nui_hud"]
            key = "quest-%d" % second
            self.assertIs(nui_hud.current(key), b)
            self.assertTrue(handler_b.IsShow())
            world.call(handler_b, "MakeNextButton", 1)
            press_key(world, handler_b, "escape")
            self.assertNotIn(b, world.interface.wndQuestWindow.values(), "the Interface dropped it")
            self.assertFalse(handler_b.IsShow(), "hidden, so wndMgr updates it no more")
            self.assertIsNone(nui_hud.current(key), "nothing keeps the facade and its legacy dialog")
            facade = weakref.ref(b)
            del b
            gc.collect()
            self.assertIsNone(facade(), "the closed facade is collected")
            self.assertIsNotNone(world.board(a), "the first keeps its board")
            self.assertIs(nui_hud.current("quest-%d" % first), a)

    def test_a_busy_delegate_closed_by_its_own_done_event_is_let_go_too(self):
        world = World(True)
        with world:
            world.open(1)
            second, b, handler_b = world.open(5)
            nui_hud = world.game.loaded["nui_hud"]
            world.call(handler_b, "MakeNextButton", 0)
            world.call(handler_b, "DoneEvent")
            self.assertFalse(handler_b.IsShow())
            self.assertIsNone(nui_hud.current("quest-%d" % second))
            self.assertEqual(sorted(world.interface.wndQuestWindow), [0])

    def test_a_skin_0_dialog_while_a_board_shows_is_novauis(self):
        world = World(True)
        with world:
            world.open(1)
            index, dialog, handler = world.open(0)
            self.assertIs(handler, dialog)
            self.assertIsNone(world.board(dialog))


# --- the fades ----------------------------------------------------------------------------------------

FADES = [("FadeOut", 0.05), ("FadeIn", 0.05), ("WhiteOut", 0.0), ("WhiteIn", 0.1)]


class Fades(unittest.TestCase):
    def ends(self, world):
        return [args for name, args in world.game.log if name == "event.EndEventProcess"]

    def run_fades(self, nui_on):
        """Each fade of the fixture `fades`, then its end: legacy's EventCurtain
        updated frame by frame, NovaUI's timer at its end."""
        world = World(nui_on)
        seen = []
        with world:
            index, dialog, handler = world.open(1)
            for name, speed in FADES:
                before = len(self.ends(world))
                self.fade(world, handler, index, name, speed)
                self.assertEqual(len(self.ends(world)), before, "no fade ends inside its callback")
                if nui_on:
                    curtain = world.nui_quest.curtain()
                    board = curtain.board()
                    self.assertIsNotNone(board)
                    self.assertTrue(board.model["timer_on"])
                    world.game.state.now = board.model["timer_end_at"]
                    with world.game, quiet():
                        board.fire("timer_end")
                    seen.append((curtain.fading() or {}).get("color", ""))
                else:
                    with world.game, quiet():
                        for _ in range(200):
                            if len(self.ends(world)) > before:
                                break
                            handler.eventCurtain.OnUpdate()
                    shown = handler.eventCurtain.IsShow()
                    seen.append(("white" if handler.eventCurtain.fadeColor == 1.0 else "black") if shown else "")
                self.assertFalse(world.game.event_waits[index], "%s: the set goes on" % name)
            return self.ends(world), seen, index

    def test_each_fade_ends_the_interpreters_wait_once_as_legacys(self):
        legacy_ends, legacy_seen, index = self.run_fades(False)
        novaui_ends, novaui_seen, _ = self.run_fades(True)
        self.assertEqual(novaui_ends, legacy_ends)
        self.assertEqual(legacy_ends, [(index,)] * 4)
        self.assertEqual(novaui_seen, legacy_seen, "opaque after an out, gone after an in")
        self.assertEqual(novaui_seen, ["black", "", "white", ""])

    def test_the_duration_classes_follow_legacys_per_frame_speed(self):
        world = World(True)
        fade_class = world.nui_quest.fade_class
        self.assertEqual(fade_class(0.05), ("fast", 0.25), "20 frames, 0.33 s at 60 fps")
        self.assertEqual(fade_class(0.1), ("fast", 0.25))
        self.assertEqual(fade_class(0), ("normal", 0.5), "legacy's default speed 0.035")
        self.assertEqual(fade_class(0.02), ("slow", 1.0))
        self.assertEqual(fade_class(0.01), ("slower", 2.0))

    def test_the_fade_layer_comes_in_front_and_the_dialog_after_it(self):
        world = World(True, screen=(1280, 960))
        with world:
            index, dialog, handler = world.open(1)
            board = world.board(dialog)
            world.call(handler, "FadeOut", 0.05)
            curtain_board = world.nui_quest.curtain().board()
            self.assertGreater(curtain_board.front, 0)
            self.assertEqual(curtain_board.model["fade"], "black")
            self.assertEqual((curtain_board.model["fade_dir"], curtain_board.model["fade_class"]), ("out", "fast"))
            fronts = board.front
            world.call(handler, "FadeIn", 0.05)
            world.game.state.now = curtain_board.model["timer_end_at"]
            with world.game, quiet():
                curtain_board.fire("timer_end")
            self.assertGreater(board.front, fronts, "the dialog in front again once the layer is gone")
            self.assertEqual(world.nui_quest.curtain().board().model["fade"], "", "the bars stay")

    def test_a_fade_that_replaces_another_still_ends_its_wait(self):
        world = World(True)
        with world:
            first, a, handler_a = world.open(0)
            second, b, handler_b = world.open(0)
            world.call(handler_a, "FadeOut", 0.05)
            world.call(handler_b, "WhiteOut", 0.05)
            self.assertEqual(self.ends(world), [(first,)])

    def test_a_dialog_that_closes_takes_its_fade_layer_with_it(self):
        world = World(True)
        with world:
            index, dialog, handler = world.open(1)
            world.call(handler, "FadeOut", 0.05)
            press_key(world, dialog, "escape")
            self.assertIsNone(world.nui_quest.curtain().fading())
            self.assertIsNone(world.nui_quest.curtain().board())

    def fade(self, world, handler, index, name, speed):
        """A fade command as the interpreter runs it: the wait flag raised,
        then the callback (Game.run_fade)."""
        with world.game, quiet():
            world.game.run_fade(handler, index, name, speed)

    def test_under_reduced_motion_a_fade_ends_on_the_next_update_not_in_its_callback(self):
        world = World(True, reduced=True)
        with world:
            index, dialog, handler = world.open(1)
            self.fade(world, handler, index, "FadeOut", 0.05)
            self.assertEqual(self.ends(world), [], "never inside the interpreter's callback")
            self.assertTrue(world.game.event_waits[index])
            curtain = world.nui_quest.curtain()
            board = curtain.board()
            self.assertEqual(curtain.fading()["color"], "black", "opaque at once")
            self.assertTrue(board.model["timer_on"])
            self.assertLessEqual(board.model["timer_end_at"], world.game.state.now, "the timer ends it at once")
            with world.game, quiet():
                board.fire("timer_end")
            self.assertEqual(self.ends(world), [(index,)])
            self.assertFalse(world.game.event_waits[index], "the set goes on")

    def test_a_fade_whose_board_does_not_load_ends_at_once_and_the_set_goes_on(self):
        world = World(True)
        with world:
            index, dialog, handler = world.open(1)
            world.game.state.failing.add(CURTAIN_DOCUMENT)
            self.fade(world, handler, index, "WhiteOut", 0.05)
            self.assertIsNone(world.nui_quest.curtain().board())
            self.assertEqual(self.ends(world), [(index,)])
            self.assertFalse(world.game.event_waits[index], "no wait for a timer that does not exist")


# --- the curtain ----------------------------------------------------------------------------------------

class Curtain(unittest.TestCase):
    def world(self, **kwargs):
        world = World(True, screen=(1280, 960), **kwargs)
        world.__enter__()
        self.addCleanup(world.__exit__)
        return world

    def end_timer(self, world):
        board = world.nui_quest.curtain().board()
        world.game.state.now = board.model["timer_end_at"]
        with world.game, quiet():
            board.fire("timer_end")

    def test_at_4_3_the_bars_slide_in_on_their_board_and_out_at_the_close(self):
        world = self.world()
        index, dialog, handler = world.open(1)
        curtain = world.nui_quest.curtain()
        self.assertEqual(world.uiQuest.QuestCurtain.BarHeight, 120)
        board = curtain.board()
        self.assertIsNotNone(board)
        self.assertEqual((board.model["bars"], board.model["bar_dp"], board.model["timer_on"]), ("in", "120.00", True))
        self.assertEqual(curtain.bars(), "sliding_in")
        self.end_timer(world)
        self.assertEqual((curtain.bars(), curtain.CurtainMode, board.model["timer_on"]), ("in", 0, False))
        self.assertEqual(world.interface.hud()[0], (), "the HUD hidden while the bars are in")
        world.call(handler, "MakeNextButton", 1)
        world.call(handler, "DoneEvent")
        press_next(world, dialog)
        self.assertEqual((curtain.bars(), board.model["bars"]), ("sliding_out", "leaving"))
        self.assertEqual(world.interface.hud()[0], (), "the HUD back only after the bars are out")
        self.end_timer(world)
        self.assertEqual(curtain.bars(), "out")
        self.assertIsNone(curtain.board())
        self.assertEqual(world.interface.hud()[0], HUD)
        self.assertEqual(world.done_events(), 0)

    def test_a_fade_with_the_bars_out_makes_a_board_whose_bars_rest_out(self):
        world = self.world()
        index, dialog, handler = world.open(0)
        curtain = world.nui_quest.curtain()
        self.assertEqual(curtain.bars(), "out")
        with world.game, quiet():
            world.game.run_fade(handler, index, "WhiteOut", 0.05)
        board = curtain.board()
        self.assertEqual((board.model["bars"], board.model["fade"]), ("out", "white"),
                         "out, not leaving: no slide out on a new board")

    def test_the_bars_scale_with_the_ui(self):
        world = self.world()
        world.open(1)
        world.game.modules["nui"].set_scale_percent(150)
        self.assertEqual(world.nui_quest.curtain().board().model["bar_dp"], "80.00")

    def test_at_16_9_no_curtain_board_is_made(self):
        world = World(True)
        with world:
            world.open(1)
            self.assertEqual(world.uiQuest.QuestCurtain.BarHeight, 0)
            self.assertEqual(world.nui_quest.curtain().bars(), "in")
            self.assertIsNone(world.nui_quest.curtain().board())
            self.assertNotIn(CURTAIN_DOCUMENT, world.game.loaded_documents())

    def test_a_skin_0_dialog_at_4_3_loads_no_curtain_document(self):
        world = self.world()
        world.open(0)
        self.assertNotIn(CURTAIN_DOCUMENT, [w.DOCUMENT for w in world.game.state.windows])
        self.assertEqual(world.nui_quest.curtain().bars(), "out")

    def test_mode_0_holds_and_lets_a_slide_finish(self):
        world = self.world()
        index, dialog, handler = world.open(1)
        curtain = world.nui_quest.curtain()
        curtain.CurtainMode = 0
        self.assertEqual(curtain.bars(), "sliding_in")
        self.end_timer(world)
        self.assertEqual(curtain.bars(), "in")

    def test_close_runs_every_done_event_with_the_curtain_and_empties_the_list(self):
        world = self.world()
        index, dialog, handler = world.open(1)
        seen = []
        dialog.AddOnDoneEvent(lambda curtain: seen.append(curtain))
        curtain = world.nui_quest.curtain()
        curtain.Close()
        self.assertEqual(len(seen), 1)
        self.assertIs(seen[0], curtain)
        self.assertEqual(world.uiQuest.QuestCurtain.OnDoneEventList, [])
        self.assertIsNone(curtain.board())

    def test_under_reduced_motion_the_bars_change_at_once(self):
        world = self.world(reduced=True)
        world.open(1)
        curtain = world.nui_quest.curtain()
        self.assertEqual(curtain.bars(), "in")
        self.assertFalse(curtain.board().model["timer_on"])

    def test_the_curtain_object_keeps_legacys_surface(self):
        world = self.world()
        curtain = world.nui_quest.install_curtain()
        self.assertIs(world.uiQuest.QuestDialog.__dict__["QuestCurtain"], curtain)
        for name in ("CURTAIN_TIME", "CURTAIN_SPEED"):
            self.assertEqual(getattr(curtain, name), getattr(world.uiQuest.QuestCurtain, name))
        for name in ("Close", "Show", "Hide"):
            self.assertTrue(callable(getattr(curtain, name)))
        curtain.BarHeight = 33
        self.assertEqual(world.uiQuest.QuestCurtain.BarHeight, 33, "the class attribute every dialog sets")

    def test_a_curtain_already_installed_is_kept(self):
        world = World(True)
        with world:
            legacy = object()
            world.uiQuest.QuestDialog.QuestCurtain = legacy
            self.assertIs(world.nui_quest.install_curtain(), legacy)


# --- the fixtures and the feeds -------------------------------------------------------------------------

def kind(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


LINE_KEYS = {"text": {"id": "number", "kind": "str", "align": "str", "runs": "list", "shown": "number",
                      "total": "number", "wraps": "list"},
             "icons": {"id": "number", "kind": "str", "align": "str", "icons": "list"},
             "countdown": {"id": "number", "kind": "str", "align": "str", "end": "number", "prefix": "str",
                           "suffix": "str"}}
RUN_KEYS = {"text": "str", "role": "str", "color": "number", "name": "str"}
ICON_KEYS = {"vnum": "number", "src": "str", "title": "str", "desc": "list", "caption": "str", "index": "number",
             "total": "number"}


def same_shape(test, value, reference, where):
    test.assertEqual(kind(value), kind(reference), where)
    if isinstance(reference, dict):
        test.assertEqual(sorted(value), sorted(reference), where)
        for key in reference:
            same_shape(test, value[key], reference[key], "%s.%s" % (where, key))


class Fixtures(unittest.TestCase):
    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)

    def test_every_quest_fixture_holds_every_model_key_with_its_kind(self):
        board = self.world.nui_quest.QuestBoard(object(), 1, 1)
        reference = board.initial_model()
        names = sorted(name for name in os.listdir(QUEST_DIR) if name.endswith(".fixture.json"))
        self.assertEqual(len(names), 12)
        for name in names:
            model = json.loads(read(os.path.join(QUEST_DIR, name)))["quest"]
            self.assertEqual(sorted(model), sorted(reference), name)
            for key in reference:
                if key == "page":
                    same_shape(self, model["page"], self.world.nui_quest.empty_page(), name + ":page")
                else:
                    self.assertEqual(kind(model[key]), kind(reference[key]), "%s:%s" % (name, key))

    def test_every_feed_file_follows_the_lines_feed(self):
        names = sorted(name for name in os.listdir(QUEST_DIR) if name.endswith(".quest.0.lines.json"))
        self.assertEqual(len(names), 12)
        for name in names:
            lines = json.loads(read(os.path.join(QUEST_DIR, name)))
            self.assertIsInstance(lines, list, name)
            ids = [line["id"] for line in lines]
            self.assertEqual(ids, sorted(set(ids)), name + ": ids unique and in order")
            for line in lines:
                keys = LINE_KEYS[line["kind"]]
                self.assertEqual({key: kind(line[key]) for key in line}, keys, name)
                self.assertIn(line["align"], ("left", "center"))
                for run in line.get("runs", ()):
                    self.assertEqual({key: kind(run[key]) for key in run}, RUN_KEYS, name)
                    self.assertIn(run["role"], ("text", "body", "title", "reward", "item", "custom"))
                    self.assertIn(run["name"], ("", "item", "mob"))
                if line["kind"] == "text":
                    self.assertEqual(line["total"], sum(len(run["text"]) for run in line["runs"]), name)
                    self.assertLessEqual(line["shown"], line["total"])
                for icon in line.get("icons", ()):
                    self.assertEqual({key: kind(icon[key]) for key in icon}, ICON_KEYS, name)

    def test_the_main_lines_are_the_specs_example(self):
        lines = json.loads(read(os.path.join(QUEST_DIR, "quest.quest.0.lines.json")))
        self.assertEqual(lines[0], {"id": 1, "kind": "text", "align": "left",
                                    "runs": [{"text": "Uriel: ", "role": "title", "color": 4294960826, "name": ""}],
                                    "shown": 7, "total": 7, "wraps": []})
        self.assertEqual(lines[-1], {"id": 6, "kind": "text", "align": "left", "runs": [], "shown": 0, "total": 0,
                                     "wraps": []})

    def test_every_curtain_fixture_holds_every_model_key(self):
        reference = self.world.game.loaded["nui_quest_curtain"].empty_model()
        for name in sorted(os.listdir(CURTAIN_DIR)):
            if name.endswith(".fixture.json"):
                model = json.loads(read(os.path.join(CURTAIN_DIR, name)))["quest_curtain"]
                self.assertEqual({k: kind(v) for k, v in model.items()}, {k: kind(v) for k, v in reference.items()}, name)

    def test_every_golden_case_names_files_that_exist(self):
        for folder, page_name in ((QUEST_DIR, "quest"), (CURTAIN_DIR, "quest-curtain")):
            cases = json.loads(read(os.path.join(folder, page_name + ".snapshots.json")))["cases"]
            for case in cases:
                variant = case.get("variant")
                fixture = "%s.%s.fixture.json" % (page_name, variant) if variant else page_name + ".fixture.json"
                self.assertTrue(os.path.exists(os.path.join(folder, fixture)), fixture)
                for path in case.get("feeds", {}).values():
                    self.assertTrue(os.path.exists(os.path.join(WINDOWS, "..", "..", path)), path)

    def test_the_board_made_from_each_fixture_logs_nothing(self):
        dbg = self.world.game.dbg
        for name in sorted(os.listdir(QUEST_DIR)):
            if name.endswith(".fixture.json"):
                model = json.loads(read(os.path.join(QUEST_DIR, name)))["quest"]
                board = self.world.nui_quest.QuestBoard(object(), model["set_index"], model["skin"])
                self.assertTrue(board.set(**model), name)
                board.destroy()
        self.assertEqual(dbg.errors, [])


# --- on demand, the sink and the phases --------------------------------------------------------------

class OnDemand(unittest.TestCase):
    def boards(self, world):
        return [w for w in world.game.state.windows if w.DOCUMENT == DOCUMENT]

    def test_a_skin_0_dialog_has_no_board(self):
        world = World(True)
        with world:
            index, dialog, handler = world.open(0)
            self.assertEqual(self.boards(world), [])
            self.assertTrue(dialog.nui_ready())

    def test_the_board_is_made_with_the_dialog_and_goes_at_its_close(self):
        world = World(True)
        with world:
            index, dialog, handler = world.open(1)
            [board] = self.boards(world)
            self.assertTrue(board.visible)
            self.assertTrue(board.modal)
            self.assertIn(("QuestBoard", "page", "quest.%d.page" % index), world.game.state.binds)
            self.assertEqual(board.model["set_index"], index)
            press_key(world, dialog, "escape")
            self.assertEqual(board._doc, 0, "destroyed")
            self.assertFalse(world.game.quest_sets[index]["attached"])

    def test_nui_discard_detaches_the_sink_and_leaves_the_event_set(self):
        world = World(True)
        with world:
            index, dialog, handler = world.open(1)
            log = len(world.game.log)
            dialog.nui_discard()
            calls = [name for name, args in world.game.log[log:]]
            self.assertIn("nuigame.QuestDetach", calls)
            self.assertNotIn("event.ClearEventSet", calls)
            self.assertEqual(self.boards(world)[0]._doc, 0)

    def test_set_0_is_not_cleared_as_legacy_but_its_sink_is_detached(self):
        world = World(True)
        with world:
            world.game.modules["event"].ClearEventSet(0)
            index, dialog, handler = world.open(1)
            self.assertEqual(index, 0)
            press_key(world, dialog, "escape")
            calls = [name for name, args in world.game.log]
            self.assertNotIn(("event.ClearEventSet", (0,)), [(n, a) for n, a in world.game.log][-6:])
            self.assertIn("nuigame.QuestDetach", calls)
            self.assertFalse(world.game.quest_sets[0]["attached"])

    def test_without_the_wave5a_engine_the_interface_makes_legacys_dialog(self):
        world = World(True)
        world.game.modules["nuigame"].lack("QuestAttach")
        with world:
            index, dialog, handler = world.open(1)
            self.assertIsInstance(dialog, world.uiQuest.QuestDialog)
            self.assertEqual(world.nui_windows.DECISIONS["quest"], "legacy: the document did not load")

    def test_a_set_the_sink_cannot_attach_falls_back_to_legacy(self):
        world = World(True)
        world.game.answer("nuigame", "QuestAttach", lambda index, skin: False)
        world.game.modules["nuigame"].__dict__.pop("QuestAttach", None)
        with world:
            index, dialog, handler = world.open(1)
            self.assertIsInstance(dialog, world.uiQuest.QuestDialog)
            self.assertIs(handler, dialog)

    def test_with_the_flag_off_the_dialog_is_legacys(self):
        world = World(False)
        with world:
            index, dialog, handler = world.open(1)
            self.assertIsInstance(dialog, world.uiQuest.QuestDialog)
            self.assertEqual(world.nui_windows.DECISIONS["quest"], "legacy: flag off")

    def test_end_phase_unloads_the_curtain_and_any_board_left(self):
        world = World(True, screen=(1280, 960))
        with world:
            index, dialog, handler = world.open(1)
            self.assertEqual(world.nui_windows.end_phase(), 2)
            self.assertIsNone(world.nui_quest.curtain().board())
            self.assertEqual(self.boards(world)[0]._doc, 0)
            self.assertEqual(world.nui_quest.end_phase(), 0)
            self.assertIn("nui_windows: phase ended, 2 document(s) unloaded", world.game.dbg.lines)


# --- the wiring --------------------------------------------------------------------------------------------

WAVE5A_SITES = {
    "interfacemodule.py": [("make", "web", "uiWeb.WebWindow", "nui_web.WebWindow"),
                           ("make", "quest", "uiQuest.QuestDialog", "nui_quest.QuestDialog"),
                           ("make", "guild-building", "uiGuild.BuildGuildBuildingWindow",
                            "nui_guild_building.BuildGuildBuildingWindow")],
    "game.py": [("make", "console", "consoleModule.ConsoleWindow", "nui_console.ConsoleWindow")],
}
WAVE5A_IDS = ("quest", "guild-building", "web", "console")


def factory_sites(file_name):
    tree = ast.parse(read(os.path.join(ROOT, file_name)))
    sites = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("make", "factory")
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "nui_windows"):
            sites.append((node.lineno, node.func.attr, ast.literal_eval(node.args[0]), ast.unparse(node.args[1]),
                          ast.literal_eval(node.args[2])))
    return [site[1:] for site in sorted(sites)]


class Recorded(object):
    NUI_FACADE = False
    made = []

    def __init__(self, *args):
        Recorded.made.append((type(self).__name__, args))
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def record(*args):
            self.calls.append((name,) + args)
            return None
        return record

    def nui_ready(self):
        return True


def window_class(name, facade):
    return type(name, (Recorded,), {"NUI_FACADE": facade})


class Wiring(unittest.TestCase):
    def test_the_wired_files_name_exactly_the_wave5a_windows_and_classes(self):
        for file_name, expected in WAVE5A_SITES.items():
            sites = [site for site in factory_sites(file_name) if site[1] in WAVE5A_IDS]
            self.assertEqual(sites, expected, file_name)

    def test_the_legacy_window_files_do_not_change(self):
        # uiguild.py makes the Wave 4 guild dialogs through make() (P16 spec
        # 6.2): nui_windows_test.Wave4Flags checks it holds nothing else.
        for file_name in ("uiquest.py", "uiweb.py", "consolemodule.py"):
            self.assertNotIn("nui_", read(os.path.join(ROOT, file_name)), file_name)

    def interface(self, windows, raising=()):
        """interfacemodule.py over MagicMock modules (but nui_windows, nui, dbg,
        systemSetting, ui and sys), with recording window classes."""
        source = read(os.path.join(ROOT, "interfacemodule.py"))
        names = set()
        for node in ast.parse(source).body:
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
        game = support.Game()
        game.modules["systemSetting"].GetUINuiWindows = lambda: windows
        modules = {name: mock.MagicMock(name=name) for name in names - {"sys", "nui_windows", "systemSetting", "dbg", "ui"}}
        Recorded.made = []
        modules["uiQuest"].QuestDialog = window_class("QuestDialog", False)
        modules["uiGuild"].BuildGuildBuildingWindow = window_class("BuildGuildBuildingWindow", False)
        modules["uiWeb"] = types.ModuleType("uiWeb")
        modules["uiWeb"].WebWindow = window_class("WebWindow", False)
        for module_name, class_name in (("nui_quest", "QuestDialog"), ("nui_web", "WebWindow"),
                                        ("nui_guild_building", "BuildGuildBuildingWindow")):
            module = types.ModuleType(module_name)
            if module_name in raising:
                def boom(*args):
                    raise RuntimeError("boom")
                setattr(module, class_name, boom)
            else:
                setattr(module, class_name, window_class("Nui" + class_name, True))
            modules[module_name] = module
        for name, module in modules.items():
            game.put(name, module)
        game.load("nui_windows", "nui_windows.py")
        interface_module = game.load("interfaceModule", "interfacemodule.py")
        interface = object.__new__(interface_module.Interface)
        interface.wndQuestWindow = {}
        interface.wndQuestWindowNewKey = 0
        return game, interface_module, interface

    def make_sites(self, game, interface):
        with game:
            interface._Interface__MakeWebWindow()
            interface.OpenQuestWindow(0, 3)
            interface.BUILD_OpenWindow = types.MethodType(
                lambda self: setattr(self, "wndGuildBuilding", game.loaded["nui_windows"].make(
                    "guild-building", sys.modules["uiGuild"].BuildGuildBuildingWindow,
                    "nui_guild_building.BuildGuildBuildingWindow")), interface)
            interface.BUILD_OpenWindow()
        return [type(x).__name__ for x in (interface.wndWeb, interface.wndQuestWindow[0], interface.wndGuildBuilding)]

    def test_with_every_flag_off_the_interface_makes_the_legacy_windows(self):
        game, module, interface = self.interface("")
        self.assertEqual(self.make_sites(game, interface), ["WebWindow", "QuestDialog", "BuildGuildBuildingWindow"])
        self.assertEqual(game.dbg.errors, [])

    def test_with_each_flag_on_the_interface_makes_exactly_the_named_class(self):
        game, module, interface = self.interface("+rest")
        self.assertEqual(self.make_sites(game, interface),
                         ["NuiWebWindow", "NuiQuestDialog", "NuiBuildGuildBuildingWindow"])
        self.assertIn(("NuiQuestDialog", (0, 3)), Recorded.made, "the skin and the index, as legacy's")
        for window_id in ("web", "quest", "guild-building"):
            game, module, interface = self.interface("+" + window_id)
            made = self.make_sites(game, interface)
            self.assertEqual([name.startswith("Nui") for name in made],
                             [window_id == "web", window_id == "quest", window_id == "guild-building"], window_id)

    def test_a_novaui_class_that_raises_falls_back_to_the_legacy_one(self):
        game, module, interface = self.interface("+rest", raising=("nui_quest",))
        self.assertEqual(self.make_sites(game, interface)[1], "QuestDialog")
        self.assertEqual(game.dbg.errors, ["nui_windows: quest: the controller could not be made (RuntimeError); "
                                           "using the legacy window"])

    def test_the_build_window_site_is_the_one_in_build_open_window(self):
        source = inspect.getsource(self.interface("")[1].Interface.BUILD_OpenWindow)
        self.assertIn('nui_windows.make("guild-building", uiGuild.BuildGuildBuildingWindow,', source)
        self.assertIn('"nui_guild_building.BuildGuildBuildingWindow")', source)

    def test_the_game_window_makes_its_console_through_the_factory(self):
        source = read(os.path.join(ROOT, "game.py"))
        self.assertIn('self.console = nui_windows.make("console", consoleModule.ConsoleWindow, "nui_console.ConsoleWindow")\n'
                      '\t\tself.console.BindGameClass(self)', source)


class NoPerFramePython(unittest.TestCase):
    def test_the_quest_modules_define_no_per_frame_method(self):
        for file_name in ("nui_quest.py", "nui_quest_curtain.py"):
            tree = ast.parse(read(os.path.join(ROOT, file_name)))
            names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
            self.assertFalse(names & {"OnUpdate", "OnRender", "OnMouseOverIn"}, file_name)

    def test_the_documents_bind_no_per_frame_python(self):
        for path in (os.path.join(QUEST_DIR, "quest.rml"), os.path.join(CURTAIN_DIR, "quest-curtain.rml")):
            source = read(path)
            self.assertNotIn("data-rml", source)
            self.assertNotIn("{{", source, "no text binding: the quest text is nui-quest-text's, the choices nui-text's")


if __name__ == "__main__":
    unittest.main()
