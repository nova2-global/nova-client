"""Tests for the NovaUI phase windows (assets/root/nui_loading.py,
nui_empire.py, nui_select.py and nui_create.py): python3 -B -m unittest
nui_phase_test (from tools/).

Plain CPython, no client. Every top-level import of the four legacy phase
modules (introloading.py, introempire.py, introselect.py, introcreate.py)
is a recording stand-in: a unittest.mock.MagicMock with the constants the
code reads, and side effects where the flows need answers (net's slot data,
chr's instances, app's clock and random numbers). `ui` is a small stand-in
with real Window, ScriptWindow, ExpandedImageBox and Bar classes and
__mem_func__; `nui` is the shared stand-in (nui_test_support.py). The real
legacy modules and the real NovaUI modules are then imported from
assets/root over them.

Each differential case builds two worlds with the same stand-in state,
drives the legacy class through its methods (its buttons' events) and the
NovaUI class through its board's data events, and compares what each made
net, chr and the stream do, in order. net's getters (Get*, Is*) are left out
of the comparison: the NovaUI select board reads all four slots for its
slot list; every net call with an effect is compared."""
import ast
import gc
import inspect
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_test_support as support  # noqa: E402

ROOT = support.ROOT
ASSETS = os.path.normpath(os.path.join(support.HERE, "..", "assets"))
LOCALE_EN = os.path.join(ASSETS, "locale", "locale", "en")
WINDOWS = os.path.join(ASSETS, "nui", "nui", "windows")

LEGACY = {  # import name -> file
    "introLoading": "introloading.py",
    "introEmpire": "introempire.py",
    "introSelect": "introselect.py",
    "introCreate": "introcreate.py",
}
NOVAUI = ("nui_loading", "nui_empire", "nui_select", "nui_create")
DOCUMENTS = {
    "nui_loading": "nui/windows/loading/loading.rml",
    "nui_empire": "nui/windows/empire/empire.rml",
    "nui_select": "nui/windows/select/select.rml",
    "nui_create": "nui/windows/create/create.rml",
}

PHASES = {"PHASE_WINDOW_LOAD": 11, "PHASE_WINDOW_EMPIRE": 12, "PHASE_WINDOW_SELECT": 13, "PHASE_WINDOW_CREATE": 14}
SLOT_KEYS = ("ID", "RACE", "FORM", "NAME", "HAIR", "PLAYTIME", "LEVEL", "HTH", "INT", "STR", "DEX",
             "GUILD_ID", "GUILD_NAME", "CHANGE_NAME_FLAG")
MOTIONS = {"MOTION_INTRO_WAIT": 1, "MOTION_INTRO_SELECTED": 2, "MOTION_INTRO_NOT_SELECTED": 3,
           "MOTION_MODE_GENERAL": 4, "PLAYER_NAME_MAX_LEN": 24}
RACES = {"RACE_WARRIOR_M": 0, "RACE_ASSASSIN_W": 1, "RACE_SURA_M": 2, "RACE_SHAMAN_W": 3,
         "RACE_WARRIOR_W": 4, "RACE_ASSASSIN_M": 5, "RACE_SURA_W": 6, "RACE_SHAMAN_M": 7}
CREATE_FIELD = "create-name"
KEYS = {"escape": 1, "1": 2, "2": 3, "3": 4, "4": 5, "enter": 28, "f1": 59, "f2": 60, "left": 203, "right": 205}


def account(*slots):
    """Slot data for net: a dict per slot, or None for an empty slot."""
    data = []
    for slot in slots:
        if slot is None:
            data.append({"ID": 0})
        else:
            values = {"RACE": 0, "FORM": 0, "HAIR": 0, "PLAYTIME": 0, "LEVEL": 1, "HTH": 0, "INT": 0, "STR": 0,
                      "DEX": 0, "GUILD_ID": 0, "GUILD_NAME": "", "CHANGE_NAME_FLAG": 0}
            values.update(slot)
            data.append(values)
    return data


DEFAULT_ACCOUNT = account(
    {"ID": 101, "NAME": "Kalinka", "RACE": 1, "LEVEL": 34, "PLAYTIME": 400, "HTH": 30, "INT": 45, "STR": 20, "DEX": 50,
     "GUILD_NAME": "Nova@ui.LOGIN_ID"},
    {"ID": 102, "NAME": "Borak", "RACE": 0, "LEVEL": 71, "PLAYTIME": 1234, "HTH": 45, "INT": 12, "STR": 60, "DEX": 30},
    None,
    None)


# --- stand-ins ------------------------------------------------------------------

class PhaseWidget(support.Widget):
    """A legacy child the uiscript loader would make: records every call, and
    answers the sizes and positions the legacy Open methods read."""

    def GetGlobalPosition(self):
        return (10, 20)

    def GetWidth(self):
        return 800

    def GetHeight(self):
        return 600


def make_ui():
    """The legacy ui module: real Window, ScriptWindow, ExpandedImageBox and
    Bar classes, PythonScriptLoader and __mem_func__."""
    ui = support.make_legacy_ui()

    class ScriptWindow(ui.ScriptWindow):
        def GetChild(self, name):
            child = self.ElementDictionary.get(name)
            if child is None:
                child = self.ElementDictionary[name] = PhaseWidget(name)
            return child

    class ExpandedImageBox(ui.Window):
        def __init__(self, layer="UI"):
            ui.Window.__init__(self, layer)
            self.image = None
            self.scale = None

        def LoadImage(self, name):
            self.image = name

        def SetScale(self, x, y):
            self.scale = (x, y)

    ui.ScriptWindow = ScriptWindow
    ui.ExpandedImageBox = ExpandedImageBox
    ui.ImageBox = ExpandedImageBox
    ui.Bar = ui.Window
    return ui


class Popup(object):
    """networkModule.PopupDialog as the phase windows use it."""

    def __init__(self, log):
        self.log = log
        self.shown = False
        self.CloseEvent = 0

    def Open(self, message, event=0, button=None):
        self.log.append(("popup.Open", message, button))
        self.shown = True
        self.CloseEvent = event

    def Close(self):
        self.log.append(("popup.Close",))
        if not self.shown:
            self.CloseEvent = 0
            return
        self.shown = False
        event, self.CloseEvent = self.CloseEvent, 0
        if event:
            event()

    def IsShow(self):
        return self.shown


class Stream(object):
    """networkModule.MainStream as the phase windows call it: every call is
    recorded in order."""

    def __init__(self, log, slot=0):
        self.log = log
        self.slot = slot
        self.isAutoSelect = 0
        self.popupWindow = Popup(log)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def record(*args):
            self.log.append(("stream." + name,) + args)
        return record

    def SetCharacterSlot(self, slot):
        self.log.append(("stream.SetCharacterSlot", slot))
        self.slot = slot

    def GetCharacterSlot(self):
        return self.slot


class Dialog(object):
    """uiCommon's dialogs (the kit or the legacy class, both answer this
    surface): records calls, keeps the events and the typed text."""

    def __init__(self, registry):
        registry.append(self)
        self.calls = []
        self.accept = None
        self.cancel = None
        self.text = ""
        self.shown = False

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def record(*args):
            self.calls.append((name,) + args)
        return record

    def SetAcceptEvent(self, event):
        self.accept = event

    def SetCancelEvent(self, event):
        self.cancel = event

    def Open(self):
        self.calls.append(("Open",))
        self.shown = True

    def Close(self):
        self.calls.append(("Close",))
        self.shown = False

    def Show(self):
        self.calls.append(("Show",))
        self.shown = True

    def Hide(self):
        self.calls.append(("Hide",))
        self.shown = False

    def IsShow(self):
        return self.shown

    def GetText(self):
        return self.text


class Chr(object):
    """chr's state: instances, the selected one and their races."""

    def __init__(self):
        self.instances = {}
        self.selected = None

    def create(self, index):
        self.instances[index] = 0

    def delete(self, index):
        self.instances.pop(index, None)

    def select(self, index):
        self.selected = index

    def set_race(self, race):
        if self.selected in self.instances:
            self.instances[self.selected] = race

    def get_race(self):
        return self.instances.get(self.selected, 0)

    def has(self, index):
        return index in self.instances


def locale_module(name, **values):
    module = support.LocaleInfo(**values)
    module.__name__ = name
    return module


class World(object):
    """One set of stand-ins, the legacy modules and the NovaUI modules loaded
    over them. `with world:` puts its modules into sys.modules (the phase
    code imports some inside its methods)."""

    def __init__(self, slots=DEFAULT_ACCOUNT, stream_slot=1, load_failures=(), randoms=None, nui_on=True):
        self.log = []          # the stream's calls
        self.phase_calls = []  # net.SetPhaseWindow: (phase, "<window>" or 0, id)
        self.time = 100.0
        self.randoms = list(randoms or [])
        self.random_calls = []
        self.dialogs = []
        self.slots = slots
        self.chr_state = Chr()
        self.state = support.NuiState()
        self.state.available = nui_on
        self.state.field_events[(DOCUMENTS["nui_create"], CREATE_FIELD)] = "name_edit"
        self.state.maxlength[(DOCUMENTS["nui_create"], CREATE_FIELD)] = 12
        self.dbg = support.make_dbg()
        self.stream = Stream(self.log, stream_slot)
        self.load_failures = set(load_failures)
        self.modules = self._stand_ins()
        self._saved = {}
        with self:
            self.legacy = {name: self._load(name, file_name) for name, file_name in LEGACY.items()}
            self.nui_windows = self._load("nui_windows", "nui_windows.py")
            self._load("nui_desc_text", "nui_desc_text.py")
            self.novaui = {name: self._load(name, name + ".py") for name in NOVAUI}

    # --- stand-ins ------------------------------------------------------------------

    def _stand_ins(self):
        modules = {}
        for file_name in LEGACY.values():
            tree = ast.parse(open(os.path.join(ROOT, file_name), encoding="utf-8").read())
            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        modules.setdefault(alias.name, None)
        for name in ("math", "_weakref", "ui", "nui", "dbg"):
            modules.pop(name, None)
        for name in list(modules) + ["player", "chat", "exception", "background", "chrmgr"]:
            modules[name] = mock.MagicMock(name=name)

        net = modules["net"]
        for key, value in PHASES.items():
            setattr(net, key, value)
        for index, key in enumerate(SLOT_KEYS):
            setattr(net, "ACCOUNT_CHARACTER_SLOT_" + key, 1000 + index)
        net.EMPIRE_A, net.EMPIRE_B, net.EMPIRE_C = 1, 2, 3
        net.GetAccountCharacterSlotDataInteger.side_effect = self._slot_value
        net.GetAccountCharacterSlotDataString.side_effect = self._slot_value
        net.GetEmpireID.return_value = 2
        net.GetMainActorRace.return_value = 0
        net.GetMainActorSkillGroup.return_value = 1
        net.GetMainActorEmpire.return_value = 2
        net.IsInsultIn.side_effect = lambda name: "fool" in name
        # Not a mock: a recorded call would keep the window alive, and the
        # discard cases need it collected.
        net.SetPhaseWindow = self._set_phase_window

        chr_ = modules["chr"]
        for key, value in MOTIONS.items():
            setattr(chr_, key, value)
        chr_.CreateInstance.side_effect = self.chr_state.create
        chr_.DeleteInstance.side_effect = self.chr_state.delete
        chr_.SelectInstance.side_effect = self.chr_state.select
        chr_.SetRace.side_effect = self.chr_state.set_race
        chr_.GetRace.side_effect = self.chr_state.get_race
        chr_.HasInstance.side_effect = self.chr_state.has
        chr_.RaceToJob.side_effect = lambda race: race % 4

        app = modules["app"]
        app.IsRTL.return_value = False
        app.GetTime.side_effect = lambda: self.time
        app.GetRandom.side_effect = self._random
        app.DEGREE_DIRECTION_RIGHT, app.DEGREE_DIRECTION_LEFT = 1, 2
        app.GetRotatingDirection.return_value = 1
        app.GetDegreeDifference.return_value = 10.0
        app.loggined = 0

        wndmgr = modules["wndMgr"]
        wndmgr.GetScreenWidth.return_value = 1600
        wndmgr.GetScreenHeight.return_value = 900

        settings = modules["playerSettingModule"]
        for key, value in RACES.items():
            setattr(settings, key, value)
        settings.LoadGameData.side_effect = self._load_game_data
        modules["musicInfo"].selectMusic = ""
        modules["musicInfo"].createMusic = ""
        modules["systemSetting"].GetMusicVolume.return_value = 1.0

        dialogs = self.dialogs
        common = modules["uiCommon"]
        common.QuestionDialog.side_effect = lambda: Dialog(dialogs)
        common.InputDialogWithDescription.side_effect = lambda: Dialog(dialogs)

        modules["localeInfo"] = locale_module(
            "localeInfo", RegisterReloadCallback=lambda fn: None, LoadLocaleData=lambda: None,
            TITLE_NAME_LIST=["t0", "t1"], CREATE_GM_NAME="[")
        modules["uiScriptLocale"] = locale_module(
            "uiScriptLocale",
            EMPIRE_PATH="locale/en/ui/empire/", SELECT_PATH="locale/en/ui/select/", LOCALE_UISCRIPT_PATH="locale/en/ui/",
            EMPIREDESC_A=os.path.join(LOCALE_EN, "empiredesc_a.txt"),
            EMPIREDESC_B=os.path.join(LOCALE_EN, "empiredesc_b.txt"),
            EMPIREDESC_C=os.path.join(LOCALE_EN, "empiredesc_c.txt"),
            JOBDESC_WARRIOR_PATH=os.path.join(LOCALE_EN, "jobdesc_warrior.txt"),
            JOBDESC_ASSASSIN_PATH=os.path.join(LOCALE_EN, "jobdesc_assassin.txt"),
            JOBDESC_SURA_PATH=os.path.join(LOCALE_EN, "jobdesc_sura.txt"),
            JOBDESC_SHAMAN_PATH=os.path.join(LOCALE_EN, "jobdesc_shaman.txt"))
        modules["ui"] = make_ui()
        modules["nui"] = support.make_nui(self.state)
        modules["dbg"] = self.dbg
        modules["systemSetting"].GetUINuiWindows = lambda: "+loading,+empire,+select,+create"
        modules["systemSetting"].IsUINuiLogin = lambda: 0
        return modules

    def _set_phase_window(self, phase, window):
        self.phase_calls.append((phase, 0 if window == 0 else "<window>", id(window)))

    def _slot_value(self, index, key):
        name = SLOT_KEYS[key - 1000]
        slot = self.slots[index] if 0 <= index < len(self.slots) else {"ID": 0}
        if not slot.get("ID"):
            return "" if name in ("NAME", "GUILD_NAME") else 0
        return slot.get(name, "" if name in ("NAME", "GUILD_NAME") else 0)

    def _random(self, low, high):
        self.random_calls.append((low, high))
        value = self.randoms.pop(0) if self.randoms else high
        return min(max(value, low), high)

    def _load_game_data(self, name):
        if name in self.load_failures:
            raise RuntimeError("stand-in: %s does not load" % name)

    # --- sys.modules ----------------------------------------------------------------

    def __enter__(self):
        for name, module in self.modules.items():
            self._saved.setdefault(name, sys.modules.get(name, support.MISSING))
            sys.modules[name] = module
        return self

    def __exit__(self, *exc):
        for name, value in self._saved.items():
            if value is support.MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
        self._saved = {}
        return False

    def _load(self, name, file_name):
        module = support.load_module(name, os.path.join(ROOT, file_name))
        if name in LEGACY:
            module.print = lambda *args, **kwargs: None  # the legacy phase windows print their life cycle
        self.modules[name] = module
        sys.modules[name] = module
        self._saved.setdefault(name, support.MISSING)
        return module

    # --- what the comparison reads -------------------------------------------------

    def net_calls(self):
        """Every net call with an effect, in order (getters left out); a phase
        window passed to net reads as "<window>"."""
        window_class = self.modules["ui"].Window
        calls = []
        for name, args, kwargs in self.modules["net"].mock_calls:
            if name.split(".")[-1].startswith(("Get", "Is")):
                continue
            args = tuple("<window>" if isinstance(arg, window_class) else arg for arg in args)
            calls.append(getattr(mock.call, name)(*args, **kwargs))
        return calls

    def chr_calls(self):
        return list(self.modules["chr"].mock_calls)

    def effects(self):
        phases = [mock.call.SetPhaseWindow(phase, window) for phase, window, _ in self.phase_calls]
        return {"net": phases + self.net_calls(), "chr": self.chr_calls(), "stream": list(self.log)}

    def board(self, window):
        return window.board

    def mark(self):
        """Forgets what was recorded so far (after Open, for example)."""
        self.modules["net"].reset_mock(return_value=False, side_effect=False)
        self.modules["chr"].reset_mock(return_value=False, side_effect=False)
        del self.log[:]
        del self.phase_calls[:]


def run_both(test, setup, legacy_flow, novaui_flow, **world_args):
    """The same flow on the legacy class and on the NovaUI class, each in a
    fresh world; returns both worlds' effects and the two windows."""
    legacy_world = World(**world_args)
    with legacy_world:
        legacy_window = setup(legacy_world, False)
        legacy_flow(legacy_world, legacy_window)
        legacy_effects = legacy_world.effects()
    novaui_world = World(**world_args)
    with novaui_world:
        novaui_window = setup(novaui_world, True)
        test.assertTrue(novaui_window.nui_ready())
        novaui_flow(novaui_world, novaui_window)
        novaui_effects = novaui_world.effects()
    test.assertEqual(novaui_effects["net"], legacy_effects["net"])
    test.assertEqual(novaui_effects["chr"], legacy_effects["chr"])
    test.assertEqual(novaui_effects["stream"], legacy_effects["stream"])
    return legacy_world, legacy_window, novaui_world, novaui_window


def fixture(name):
    with open(os.path.join(WINDOWS, name, name + ".fixture.json"), encoding="utf-8") as file:
        return json.load(file)


# --- the facade ---------------------------------------------------------------------

def compatible(legacy_function, novaui_function):
    """True when the NovaUI method takes what the legacy one takes."""
    legacy_params = list(inspect.signature(legacy_function).parameters.values())
    novaui_params = list(inspect.signature(novaui_function).parameters.values())
    if len(legacy_params) != len(novaui_params):
        return False
    for old, new in zip(legacy_params, novaui_params):
        if old.kind != new.kind:
            return False
        if (old.default is inspect.Parameter.empty) != (new.default is inspect.Parameter.empty):
            return False
    return True


class FacadeTest(unittest.TestCase):
    PAIRS = (
        ("introLoading", "LoadingWindow", "nui_loading", "LoadingWindow"),
        ("introEmpire", "SelectEmpireWindow", "nui_empire", "SelectEmpireWindow"),
        ("introEmpire", "ReselectEmpireWindow", "nui_empire", "ReselectEmpireWindow"),
        ("introSelect", "SelectCharacterWindow", "nui_select", "SelectCharacterWindow"),
        ("introCreate", "CreateCharacterWindow", "nui_create", "CreateCharacterWindow"),
    )
    # The names C++ calls (PyCallClassMemberFunc on the phase window).
    CALLBACKS = {
        "LoadingWindow": ("LoadData", "Open", "Close", "OnUpdate", "OnPressEscapeKey"),
        "SelectEmpireWindow": ("Open", "Close", "OnUpdate", "OnPressEscapeKey"),
        "ReselectEmpireWindow": ("Open", "Close", "OnUpdate", "OnPressEscapeKey"),
        "SelectCharacterWindow": ("Open", "Close", "Refresh", "OnCreateFailure", "OnDeleteSuccess",
                                  "OnDeleteFailure", "OnChangeName", "OnKeyDown", "OnUpdate", "OnPressExitKey",
                                  "SameLoginDisconnect"),
        "CreateCharacterWindow": ("Open", "Close", "OnCreateSuccess", "OnCreateFailure", "OnKeyDown", "OnUpdate",
                                  "OnPressExitKey"),
    }

    def setUp(self):
        self.world = World()

    def test_every_legacy_method_is_callable_on_the_novaui_class_with_a_compatible_signature(self):
        for legacy_module, legacy_name, novaui_module, novaui_name in self.PAIRS:
            legacy = getattr(self.world.legacy[legacy_module], legacy_name)
            novaui = getattr(self.world.novaui[novaui_module], novaui_name)
            self.assertEqual(novaui.__name__, legacy.__name__)
            names = set()
            for klass in legacy.__mro__:
                if klass.__module__ == legacy.__module__:
                    names.update(name for name, value in vars(klass).items() if inspect.isfunction(value))
            self.assertTrue(names)
            for name in sorted(names):
                with self.subTest(window=novaui_name, method=name):
                    self.assertTrue(callable(getattr(novaui, name, None)), name)
                    self.assertTrue(compatible(getattr(legacy, name), getattr(novaui, name)), name)

    def test_the_novaui_classes_subclass_their_legacy_classes(self):
        for legacy_module, legacy_name, novaui_module, novaui_name in self.PAIRS:
            legacy = getattr(self.world.legacy[legacy_module], legacy_name)
            novaui = getattr(self.world.novaui[novaui_module], novaui_name)
            if legacy_name == "ReselectEmpireWindow":
                legacy = self.world.legacy[legacy_module].SelectEmpireWindow
            self.assertTrue(issubclass(novaui, legacy), novaui_name)

    def test_the_cpp_callback_names_exist(self):
        for _, _, novaui_module, novaui_name in self.PAIRS:
            novaui = getattr(self.world.novaui[novaui_module], novaui_name)
            for name in self.CALLBACKS[novaui_name]:
                with self.subTest(window=novaui_name, callback=name):
                    self.assertTrue(callable(getattr(novaui, name, None)))

    def test_the_private_pickers_of_create_are_replaced_under_their_mangled_names(self):
        novaui = self.world.novaui["nui_create"].CreateCharacterWindow
        for name in ("_CreateCharacterWindow__SelectGender", "_CreateCharacterWindow__SelectShape",
                     "_CreateCharacterWindow__SelectSlot"):
            self.assertIn(name, vars(novaui))
        self.assertIn("_LoadingWindow__SetProgress", vars(self.world.novaui["nui_loading"].LoadingWindow))

    def test_networkmodule_names_exactly_these_classes(self):
        source = open(os.path.join(ROOT, "networkmodule.py"), encoding="utf-8").read()
        named = set()
        for node in ast.walk(ast.parse(source)):
            if (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "make"
                    and getattr(node.func.value, "id", "") == "nui_windows"):
                named.add((node.args[0].value, node.args[2].value))
        self.assertEqual(named, {
            ("empire", "nui_empire.SelectEmpireWindow"), ("empire", "nui_empire.ReselectEmpireWindow"),
            ("select", "nui_select.SelectCharacterWindow"), ("create", "nui_create.CreateCharacterWindow"),
            ("loading", "nui_loading.LoadingWindow")})
        for _, path in named:
            module_name, _, class_name = path.rpartition(".")
            self.assertTrue(inspect.isclass(getattr(self.world.novaui[module_name], class_name, None)), path)

    def test_every_data_event_of_the_documents_has_a_handler(self):
        boards = {"loading": "LoadingBoard", "empire": "EmpireBoard", "select": "SelectBoard", "create": "CreateBoard"}
        for name, board_name in boards.items():
            source = open(os.path.join(WINDOWS, name, name + ".rml"), encoding="utf-8").read()
            events = set()
            for part in source.split('data-event-')[1:]:
                value = part.split('"')[1]
                for action in value.split(";"):
                    events.add(action.strip().split("(")[0])
            board = getattr(self.world.novaui["nui_" + name], board_name)
            handled = set()
            for klass in board.__mro__:
                for value in vars(klass).values():
                    handled.update(getattr(value, "_nui_events", ()))
            self.assertEqual(handled, events, name)


# --- the fixture rule ---------------------------------------------------------------

class FixtureTest(unittest.TestCase):
    BOARDS = (("loading", "nui_loading", "LoadingBoard"), ("empire", "nui_empire", "EmpireBoard"),
              ("select", "nui_select", "SelectBoard"), ("create", "nui_create", "CreateBoard"))

    def test_a_board_made_with_any_owner_shows_its_fixture_without_an_error_or_a_log_line(self):
        world = World()
        with world:
            for name, module, board_name in self.BOARDS:
                with self.subTest(window=name):
                    data = fixture(name)
                    board_class = getattr(world.novaui[module], board_name)
                    board = board_class(owner=object())
                    self.assertTrue(board._doc)
                    self.assertEqual(set(data), {board_class.MODEL})
                    self.assertEqual(set(data[board_class.MODEL]), set(board.initial_model()))
                    self.assertTrue(board.set(**data[board_class.MODEL]))
                    self.assertTrue(board.show())
                    board.destroy()
        self.assertEqual(world.dbg.errors, [])
        self.assertEqual(world.dbg.lines, [])

    def test_the_fixtures_follow_the_spec(self):
        world = World()
        with world:
            desc = world.modules["nui_desc_text"]
            empire = fixture("empire")["empire"]
            self.assertEqual(empire["paragraphs"], desc.load(os.path.join(LOCALE_EN, "empiredesc_a.txt")))
            self.assertEqual(empire["title_image"], "locale/en/ui/empire/title.sub")
            create = fixture("create")["create"]
            self.assertEqual(create["paragraphs"], desc.load(os.path.join(LOCALE_EN, "jobdesc_warrior.txt")))
        select = fixture("select")["select"]
        self.assertEqual([(s["label"], s["level"]) for s in select["slots"]],
                         [("Kalinka", 34), ("Borak", 71), ("@ui.SELECT_SLOT_EMPTY", 0), ("@ui.SELECT_SLOT_EMPTY", 0)])
        self.assertEqual(fixture("loading")["loading"],
                         {"background": "d:/ymir work/uiloading/base/background_loading_warrior.sub",
                          "progress": 42.0, "error": False})


# --- discard and __del__ ------------------------------------------------------------

def phase_calls(world, phase):
    """(window id or 0) of every net.SetPhaseWindow for this phase, in order."""
    return [window_id if window else 0 for number, window, window_id in world.phase_calls if number == PHASES[phase]]


class DiscardTest(unittest.TestCase):
    CASES = (("loading", "introLoading", "LoadingWindow", "nui_loading.LoadingWindow", "PHASE_WINDOW_LOAD"),
             ("empire", "introEmpire", "SelectEmpireWindow", "nui_empire.SelectEmpireWindow", "PHASE_WINDOW_EMPIRE"),
             ("select", "introSelect", "SelectCharacterWindow", "nui_select.SelectCharacterWindow", "PHASE_WINDOW_SELECT"),
             ("create", "introCreate", "CreateCharacterWindow", "nui_create.CreateCharacterWindow", "PHASE_WINDOW_CREATE"))

    def _make(self, world, window_id, legacy_module, class_name, path):
        legacy = getattr(world.legacy[legacy_module], class_name)
        return world.nui_windows.make(window_id, legacy, path, world.stream)

    def test_after_nui_discard_dropping_the_instance_keeps_the_net_phase_slot(self):
        for window_id, legacy_module, class_name, path, phase in self.CASES:
            with self.subTest(window=window_id):
                world = World()
                with world:
                    module_name, _, _ = path.rpartition(".")
                    window = getattr(world.novaui[module_name], class_name)(world.stream)
                    self.assertTrue(window.nui_ready())
                    window.nui_discard()
                    self.assertFalse(window.nui_ready())
                    self.assertTrue(window._nui_discarded)
                    window_id = id(window)
                    del window
                    gc.collect()
                    self.assertEqual(phase_calls(world, phase), [window_id])

    def test_a_window_that_is_not_discarded_clears_its_slot_as_legacy(self):
        world = World()
        with world:
            window = world.novaui["nui_select"].SelectCharacterWindow(world.stream)
            window_id = id(window)
            del window
            gc.collect()
            self.assertEqual(phase_calls(world, "PHASE_WINDOW_SELECT"), [window_id, 0])

    def test_make_discards_a_window_whose_document_did_not_load_before_the_legacy_one_is_made(self):
        for window_id, legacy_module, class_name, path, phase in self.CASES:
            with self.subTest(window=window_id):
                world = World()
                with world:
                    world.state.failing.add(DOCUMENTS[path.split(".")[0]])
                    window = self._make(world, window_id, legacy_module, class_name, path)
                    gc.collect()
                    legacy = getattr(world.legacy[legacy_module], class_name)
                    self.assertIs(type(window), legacy)
                    registered = phase_calls(world, phase)
                    self.assertEqual(len(registered), 2)
                    self.assertEqual(registered[-1], id(window))
                    self.assertNotIn(0, registered)
                    self.assertEqual(world.nui_windows.DECISIONS[window_id], "legacy: the document did not load")
                    self.assertEqual(len(world.dbg.errors), 1)

    def test_make_falls_back_when_the_board_raises_and_the_half_made_window_keeps_the_slot(self):
        world = World()
        with world:
            world.state.raising.add(DOCUMENTS["nui_select"])
            window = self._make(world, "select", "introSelect", "SelectCharacterWindow", "nui_select.SelectCharacterWindow")
            gc.collect()
            self.assertIs(type(window), world.legacy["introSelect"].SelectCharacterWindow)
            registered = phase_calls(world, "PHASE_WINDOW_SELECT")
            self.assertEqual(len(registered), 2)
            self.assertEqual(registered[-1], id(window))
            self.assertNotIn(0, registered)
            self.assertIn("could not be made (RuntimeError)", world.dbg.errors[0])

    def test_make_returns_the_novaui_window_when_its_flag_is_on(self):
        for window_id, legacy_module, class_name, path, phase in self.CASES:
            with self.subTest(window=window_id):
                world = World()
                with world:
                    window = self._make(world, window_id, legacy_module, class_name, path)
                    module_name = path.split(".")[0]
                    self.assertIs(type(window), getattr(world.novaui[module_name], class_name))
                    self.assertEqual(world.nui_windows.DECISIONS[window_id], "nui")
                    self.assertFalse(window.board.is_visible())

    def test_close_destroys_the_board(self):
        world = World()
        with world:
            window = world.novaui["nui_empire"].SelectEmpireWindow(world.stream)
            board = window.board
            window.Open()
            self.assertTrue(board.is_visible())
            window.Close()
            self.assertIsNone(window.board)
            self.assertFalse(board._doc)


# --- loading ------------------------------------------------------------------------

def loading_setup(world, novaui):
    module = world.novaui["nui_loading"] if novaui else world.legacy["introLoading"]
    return module.LoadingWindow(world.stream)


class LoadingTest(unittest.TestCase):
    def _flow(self, world, window):
        window.LoadData(1200, 3400)
        window.Open()
        for _ in range(20):
            window.OnUpdate()

    def test_load_data_then_the_steps_make_the_same_calls(self):
        legacy_world, _, novaui_world, window = run_both(self, loading_setup, self._flow, self._flow, randoms=[3])
        for world in (legacy_world, novaui_world):
            settings = world.modules["playerSettingModule"]
            self.assertEqual([c[1][0] for c in settings.LoadGameData.mock_calls],
                             ["INIT", "SOUND", "EFFECT", "WARRIOR", "ASSASSIN", "SURA", "SHAMAN", "SKILL", "ENEMY", "NPC"])
            self.assertIn(mock.call.StartGame(), world.modules["net"].mock_calls)
            self.assertEqual(world.random_calls, [(0, 22)])
        self.assertEqual(window.board.get("progress"), 100.0)
        self.assertEqual(window.board.get("background"), world_background(novaui_world, 3))
        self.assertTrue(window.board.is_visible())
        self.assertFalse(window.board.get("error"))

    def test_a_failing_step_shows_the_error_and_exits_as_legacy(self):
        def flow(world, window):
            self._flow(world, window)
            world.app_calls = [c for c in world.modules["app"].mock_calls if c[0] in ("Exit", "SetFrameSkip")]

        legacy_world, legacy_window, novaui_world, window = run_both(
            self, loading_setup, flow, flow, load_failures=("SOUND",))
        self.assertEqual(novaui_world.app_calls, legacy_world.app_calls)
        self.assertIn(mock.call.Exit(), novaui_world.app_calls)
        self.assertEqual(novaui_world.dbg.errors, legacy_world.dbg.errors)
        self.assertTrue(window.board.get("error"))
        self.assertEqual(legacy_window.errMsg.shown, True)

    def test_the_progress_follows_each_step_at_once(self):
        world = World()
        with world:
            window = loading_setup(world, True)
            window.LoadData(0, 0)
            window.Open()
            self.assertEqual(window.board.get("progress"), 2.0)
            seen = []
            for _ in range(4):
                window.OnUpdate()
                seen.append(window.board.get("progress"))
            self.assertEqual(seen, [2.0, 2.0 + 98.0 * 10 / 100, 2.0 + 98.0 * 30 / 100, 2.0 + 98.0 * 40 / 100])

    def test_open_sends_the_slot_and_close_ends_the_screen(self):
        world = World(stream_slot=2)
        with world:
            window = loading_setup(world, True)
            board = window.board
            window.Open()
            self.assertIn(mock.call.SendSelectCharacterPacket(2), world.modules["net"].mock_calls)
            self.assertIn(mock.call.SetFrameSkip(0), world.modules["app"].mock_calls)
            window.Close()
            self.assertIn(mock.call.SetFrameSkip(1), world.modules["app"].mock_calls)
            self.assertFalse(board._doc)
            self.assertEqual(window.loadStepList, [])
            self.assertEqual(window.errMsg, 0)

    def test_escape_goes_back_to_the_login_as_legacy(self):
        world = World()
        with world:
            window = loading_setup(world, True)
            window.Open()
            self.assertTrue(window.OnPressEscapeKey())
            self.assertIn(("stream.SetLoginPhase",), world.log)

    def test_the_backgrounds_are_the_legacy_list(self):
        source = open(os.path.join(ROOT, "introloading.py"), encoding="utf-8").read()
        legacy = None
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "imgFileNameDict":
                legacy = [value.value for value in node.value.values]
        world = World()
        self.assertEqual(list(world.novaui["nui_loading"].BACKGROUNDS), legacy)


def world_background(world, index):
    return world.novaui["nui_loading"].BACKGROUNDS[index]


# --- empire -------------------------------------------------------------------------

def empire_setup(class_name):
    def setup(world, novaui):
        module = world.novaui["nui_empire"] if novaui else world.legacy["introEmpire"]
        window = getattr(module, class_name)(world.stream)
        window.Open()
        world.mark()
        return window
    return setup


class EmpireTest(unittest.TestCase):
    STEPS = (("pick", 2), ("pick", 2), ("left",), ("right",), ("right",), ("pick", 1), ("hover", 3), ("unhover", 3),
             ("choose",), ("leave",))

    @staticmethod
    def legacy_flow(world, window):
        for step in EmpireTest.STEPS:
            if step[0] == "pick":
                if window.empireID != step[1]:
                    window.OnSelectEmpire(step[1])
            elif step[0] == "hover":
                window.OnOverInEmpire(step[1])
            elif step[0] == "unhover":
                window.OnOverOutEmpire(step[1])
            else:
                {"left": window.ClickLeftButton, "right": window.ClickRightButton,
                 "choose": window.ClickSelectButton, "leave": window.ClickExitButton}[step[0]]()
            world.log.append(("empire", window.empireID))

    @staticmethod
    def novaui_flow(world, window):
        for step in EmpireTest.STEPS:
            window.board.fire(*step)
            world.log.append(("empire", window.empireID))

    def test_pick_left_right_choose_and_exit_make_the_same_calls(self):
        for class_name, phases in (("SelectEmpireWindow", ("SetSelectCharacterPhase", "SetLoginPhase")),
                                   ("ReselectEmpireWindow", ("SetCreateCharacterPhase", "SetSelectCharacterPhase"))):
            with self.subTest(window=class_name):
                legacy_world, _, novaui_world, window = run_both(
                    self, empire_setup(class_name), self.legacy_flow, self.novaui_flow, randoms=[3])
                calls = [c for c in novaui_world.log if c[0].startswith("stream.")]
                self.assertEqual(calls, [("stream." + phases[0],), ("stream." + phases[1],)])
                self.assertEqual(novaui_world.net_calls(), [mock.call.SendSelectEmpirePacket(1)])

    def test_the_model_follows_the_empire_and_the_hover(self):
        world = World(randoms=[2])
        with world:
            window = empire_setup("SelectEmpireWindow")(world, True)
            board = window.board
            self.assertTrue(board.is_visible())
            self.assertEqual(board.get("empire"), 2)
            self.assertEqual(board.get("name"), "@game.EMPIRE_B")
            self.assertEqual(board.get("flag_image"), "d:/ymir work/ui/intro/empire/empireflag_b.sub")
            self.assertEqual(board.get("title_image"), "locale/en/ui/empire/title.sub")
            self.assertEqual(board.get("paragraphs"),
                             world.modules["nui_desc_text"].load(os.path.join(LOCALE_EN, "empiredesc_b.txt")))
            board.fire("hover", 3)
            self.assertEqual(board.get("hover"), 3)
            board.fire("unhover", 1)  # an older out: the newer hover stays
            self.assertEqual(board.get("hover"), 3)
            board.fire("unhover", 3)
            self.assertEqual(board.get("hover"), 0)
            board.fire("right")
            self.assertEqual((window.empireID, board.get("empire"), board.get("name")), (3, 3, "@game.EMPIRE_C"))
            self.assertEqual(board.get("paragraphs")[0], "Jinno Kingdom")

    def test_open_close_and_the_dropped_pages(self):
        world = World()
        with world:
            window = empire_setup("SelectEmpireWindow")(world, True)
            app = world.modules["app"]
            self.assertIn(mock.call.ShowCursor(), app.mock_calls)
            window.PrevDescriptionPage()
            window.NextDescriptionPage()
            window.OnUpdate()
            self.assertEqual(world.modules["event"].mock_calls, [])
            self.assertTrue(window.OnPressEscapeKey())
            self.assertIn(("stream.SetLoginPhase",), world.log)
            window.Close()
            self.assertIn(mock.call.HideCursor(), app.mock_calls)
            self.assertIn(mock.call.Destroy(), world.modules["event"].mock_calls)


# --- select -------------------------------------------------------------------------

def select_setup(world, novaui):
    module = world.novaui["nui_select"] if novaui else world.legacy["introSelect"]
    window = module.SelectCharacterWindow(world.stream)
    window.Open()
    return window


def press(world, window, novaui, name, *args):
    """A select or create board action: the board's data event, or the
    legacy button's method."""
    if novaui:
        return window.board.fire(name, *args)
    return LEGACY_SELECT[name](window, *args)


LEGACY_SELECT = {
    "pick_slot": lambda window, index: window.SelectSlot(index),
    "left": lambda window: window.DecreaseSlotIndex(),
    "right": lambda window: window.IncreaseSlotIndex(),
    "start": lambda window: window.StartGame(),
    "create": lambda window: window.CreateCharacter(),
    "remove": lambda window: (window.PopupDeleteQuestion() if sys.modules["introSelect"].NOT_NEED_DELETE_CODE
                              else window.InputPrivateCode()),
    "leave": lambda window: window.ExitSelect(),
}


class SelectTest(unittest.TestCase):
    def both(self, steps, **world_args):
        def flow(novaui):
            def run(world, window):
                for step in steps:
                    if callable(step):
                        step(world, window, novaui)
                    else:
                        press(world, window, novaui, *step)
            return run
        return run_both(self, select_setup, flow(False), flow(True), **world_args)

    def test_open_makes_the_same_calls(self):
        legacy_world, _, novaui_world, window = self.both([])
        self.assertTrue(novaui_world.chr_calls())
        board = window.board
        self.assertTrue(board.is_visible())
        # Legacy Refresh selects each occupied slot from the last to the
        # first, and ends on the first.
        self.assertEqual((window.slot, board.get("slot")), (0, 0))
        board.fire("pick_slot", 1)
        self.assertEqual(board.get("name"), "Borak")
        self.assertEqual((board.get("level"), board.get("playtime")), ("71", "1234"))
        self.assertEqual([board.get("stat_" + s) for s in ("hth", "int", "str", "dex")], ["45", "12", "60", "30"])
        self.assertEqual(board.get("gauge_str"), 60 / 90.0)
        self.assertEqual(board.get("job_image"), "locale/en/ui/select/name_warrior.sub")
        self.assertEqual((board.get("empire_name"), board.get("flag_image")),
                         ("@game.EMPIRE_B", "d:/ymir work/ui/intro/empire/empireflag_b.sub"))
        self.assertEqual([(s["label"], s["level"]) for s in board.get("slots")],
                         [("Kalinka", 34), ("Borak", 71), ("@ui.SELECT_SLOT_EMPTY", 0), ("@ui.SELECT_SLOT_EMPTY", 0)])
        self.assertTrue(board.get("occupied"))
        self.assertFalse(board.get("busy"))
        self.assertEqual(window.backGround.image, "d:/ymir work/ui/intro/select/select.sub")
        self.assertEqual(window.backGround.scale, (1600 / 1024.0, 900 / 768.0))
        self.assertTrue(window.backGround.IsShow())

    def test_player_text_goes_through_plain_text(self):
        world = World()
        with world:
            window = select_setup(world, True)
            window.board.fire("pick_slot", 0)
            self.assertEqual(window.board.get("guild"), "Nova@\u2060ui.LOGIN_ID")
            self.assertEqual(window.board.get("job_image"), "locale/en/ui/select/name_assassin.sub")
            window.board.fire("pick_slot", 2)
            self.assertFalse(window.board.get("occupied"))
            self.assertEqual(window.board.get("guild"), "@game.SELECT_NOT_JOIN_GUILD")
            self.assertEqual((window.board.get("name"), window.board.get("job_image")), ("", ""))

    def test_start_and_the_three_second_timer(self):
        def wait(world, window, novaui):
            world.time += 1.0
            window.OnUpdate()
            world.time += 2.5
            window.OnUpdate()
            window.OnUpdate()

        legacy_world, _, novaui_world, window = self.both([("left",), ("right",), ("right",), ("start",), wait, ("start",)])
        self.assertEqual([c for c in novaui_world.net_calls() if c[0] == "DirectEnter"], [mock.call.DirectEnter(1)])
        self.assertTrue(window.board.get("busy"))
        self.assertIn(("stream.SetCharacterSlot", 1), novaui_world.log)

    def test_the_board_does_nothing_while_busy(self):
        world = World()
        with world:
            window = select_setup(world, True)
            window.board.fire("start")
            world.mark()
            for event in (("pick_slot", 2), ("left",), ("right",), ("start",), ("create",), ("remove",), ("leave",)):
                window.board.fire(*event)
            self.assertEqual((world.net_calls(), world.chr_calls(), world.log), ([], [], []))
            self.assertEqual(window.slot, 0)

    def test_create_goes_to_the_create_or_the_empire_phase(self):
        self.both([("pick_slot", 2), ("create",), ("pick_slot", 0), ("create",)])
        legacy_world, _, novaui_world, _ = self.both([("pick_slot", 3), ("create",)],
                                                     slots=account(None, None, None, None))
        self.assertIn(("stream.SetReselectEmpirePhase",), novaui_world.log)

    def test_delete_with_the_private_code(self):
        def accept(world, window, novaui):
            dialog = world.dialogs[-1]
            dialog.text = "7654321"
            dialog.accept()

        def deleted(world, window, novaui):
            world.slots = account(DEFAULT_ACCOUNT[0], None, None, None)
            window.OnDeleteSuccess(1)

        legacy_world, _, novaui_world, window = self.both([("pick_slot", 1), ("remove",), accept, deleted])
        self.assertIn(mock.call.SendDestroyCharacterPacket(1, "7654321"), novaui_world.net_calls())
        self.assertEqual(novaui_world.dialogs[-1].calls[:4],
                         [("SetTitle", "INPUT_PRIVATE_CODE_DIALOG_TITLE"), ("SetNumberMode",), ("SetSecretMode",),
                          ("SetMaxLength", 7)])
        self.assertEqual(window.board.get("slots")[1]["label"], "@ui.SELECT_SLOT_EMPTY")
        self.assertFalse(window.board.get("occupied"))

    def test_delete_with_the_question_when_no_code_is_needed(self):
        def accept(world, window, novaui):
            if novaui:
                world.dialogs[-1].accept()
            else:
                window.dlgQuestionAcceptButton.Click()

        def no_code(world, window, novaui):
            world.legacy["introSelect"].NOT_NEED_DELETE_CODE = True

        legacy_world, _, novaui_world, window = self.both([no_code, ("pick_slot", 1), ("remove",), accept])
        self.assertIn(mock.call.SendDestroyCharacterPacket(1, "1234567"), novaui_world.net_calls())
        question = novaui_world.dialogs[0]
        self.assertEqual(question.calls[0], ("SetText", "SELECT_DO_YOU_DELETE_REALLY"))
        self.assertIn(("Open",), question.calls)
        self.assertEqual(question.calls[-1], ("Close",))

    def test_rename(self):
        slots = account(DEFAULT_ACCOUNT[0], dict(DEFAULT_ACCOUNT[1], CHANGE_NAME_FLAG=1), None, None)

        def accept(world, window, novaui):
            dialog = world.dialogs[-1]
            dialog.text = "Borak2"
            dialog.accept()

        def renamed(world, window, novaui):
            world.slots = account(DEFAULT_ACCOUNT[0], dict(DEFAULT_ACCOUNT[1], NAME="Borak2"), None, None)
            window.OnChangeName(1, "Borak2")

        legacy_world, _, novaui_world, window = self.both([("pick_slot", 1), ("start",), accept, renamed], slots=slots)
        self.assertIn(mock.call.SendChangeNamePacket(1, "Borak2"), novaui_world.net_calls())
        self.assertEqual(window.board.get("slots")[1]["label"], "Borak2")
        self.assertFalse(window.board.get("busy"))

    def test_exit(self):
        legacy_world, _, novaui_world, window = self.both([("leave",)])
        self.assertIn(("stream.SetLoginPhase",), novaui_world.log)
        self.assertFalse(window.IsShow())

    def test_the_hotkeys_stay_in_the_phase_window(self):
        def keys(world, window, novaui):
            for key in ("3", "right", "right", "left", "1", "4", "enter", "2", "enter"):
                self.assertTrue(window.OnKeyDown(KEYS[key]))

        legacy_world, _, novaui_world, window = self.both([keys])
        self.assertIn(("stream.SetCreateCharacterPhase",), novaui_world.log)
        self.assertIn(("stream.SetCharacterSlot", 1), novaui_world.log)
        self.assertEqual(window.board.get("slot"), 1)

        legacy_world, _, novaui_world, _ = self.both([lambda world, window, novaui: window.OnKeyDown(KEYS["escape"])])
        self.assertIn(("stream.SetLoginPhase",), novaui_world.log)

    def test_close_matches_legacy_and_closes_the_question(self):
        legacy_world, _, novaui_world, window = self.both([lambda world, window, novaui: window.Close()])
        self.assertIsNone(window.board)
        self.assertEqual(novaui_world.dialogs[0].calls[-1], ("Close",))


# --- create -------------------------------------------------------------------------

def create_setup(world, novaui):
    module = world.novaui["nui_create"] if novaui else world.legacy["introCreate"]
    window = module.CreateCharacterWindow(world.stream)
    window.Open()
    return window


def type_name(name):
    def step(world, window, novaui):
        if novaui:
            window.board.set_value(CREATE_FIELD, name)
        else:
            window.editCharacterName.SetText(name)
    return step


LEGACY_CREATE = {
    "left": lambda window: window._CreateCharacterWindow__DecreaseSlotIndex(),
    "right": lambda window: window._CreateCharacterWindow__IncreaseSlotIndex(),
    "gender": lambda window, gender: window._CreateCharacterWindow__SelectGender(gender),
    "shape": lambda window, shape: window._CreateCharacterWindow__SelectShape(shape),
    "create": lambda window: window.CreateCharacter(),
    "cancel": lambda window: window.CancelCreate(),
}


class CreateTest(unittest.TestCase):
    RANDOMS = [1, 2]   # the gender (WOMAN), then the slot (2)

    def both(self, steps, **world_args):
        world_args.setdefault("randoms", list(self.RANDOMS))

        def flow(novaui):
            def run(world, window):
                for step in steps:
                    if callable(step):
                        step(world, window, novaui)
                    elif novaui:
                        window.board.fire(*step)
                    else:
                        LEGACY_CREATE[step[0]](window, *step[1:])
            return run
        return run_both(self, create_setup, flow(False), flow(True), **world_args)

    def test_open_makes_the_same_calls(self):
        legacy_world, _, novaui_world, window = self.both([])
        board = window.board
        self.assertEqual((board.get("gender"), board.get("shape"), board.get("slot")), (1, 0, 2))
        self.assertEqual(board.get("job_image"), "locale/en/ui/select/name_sura.sub")
        self.assertEqual([board.get("stat_" + s) for s in ("hth", "int", "str", "dex")], ["3", "5", "5", "3"])
        self.assertEqual(board.get("gauge_int"), 5 / 16.0)
        self.assertEqual(board.get("paragraphs"),
                         novaui_world.modules["nui_desc_text"].load(os.path.join(LOCALE_EN, "jobdesc_sura.txt")))
        self.assertFalse(board.get("busy"))
        self.assertTrue(board.is_visible())
        self.assertEqual(board.focused, CREATE_FIELD)

    def test_the_gender_shape_and_slot_pickers(self):
        legacy_world, _, novaui_world, window = self.both(
            [("gender", 0), ("shape", 1), ("right",), ("right",), ("shape", 1), ("left",), ("gender", 1), ("shape", 0)])
        self.assertEqual((window.board.get("gender"), window.board.get("shape"), window.board.get("slot")), (1, 0, 3))
        self.assertEqual(window.shapeList, [[1, 0, 1, 0], [0, 0, 0, 0]])

    def test_a_click_on_the_board_gives_the_name_field_the_focus_back(self):
        # The legacy edit line keeps the keyboard while the mouse picks: a
        # name typed after the picks lands in it (live S2L, 2026-10-05).
        world = World(randoms=list(self.RANDOMS))
        with world:
            window = create_setup(world, True)
            board = window.board
            self.assertEqual(board.focused, CREATE_FIELD)
            for element_id, event in (("create-right", ("right",)), ("create-man", ("gender", 0)),
                                      ("create-shape-2", ("shape", 1)), ("create-text", ())):
                board.click(element_id, *event)
                self.assertEqual(board.focused, CREATE_FIELD, element_id)
            self.assertEqual((board.get("slot"), board.get("gender"), board.get("shape")), (3, 0, 1))
            board.set_value(CREATE_FIELD, "Nova")
            board.click("create-create", "create")
            self.assertTrue(board.get("busy"))
            self.assertEqual(board.focused, "create-create")   # busy: the field is disabled

    def test_the_name_checks_open_the_legacy_popups(self):
        legacy_world, _, novaui_world, window = self.both(
            [type_name(""), ("create",), type_name("a[b"), ("create",), type_name("fool"), ("create",)])
        popups = [c[1] for c in novaui_world.log if c[0] == "popup.Open"]
        self.assertEqual(popups, ["CREATE_INPUT_NAME", "CREATE_ERROR_GM_NAME", "CREATE_ERROR_INSULT_NAME"])
        self.assertFalse(window.board.get("busy"))

    def test_create_and_the_timer_send_the_packet_with_the_typed_name(self):
        def wait(world, window, novaui):
            world.time += 1.0
            window.OnUpdate()
            world.time += 0.6
            window.OnUpdate()
            window.OnUpdate()

        legacy_world, _, novaui_world, window = self.both([type_name("Nova"), ("create",), wait])
        packets = [c for c in novaui_world.net_calls() if c[0] == "SendCreateCharacterPacket"]
        self.assertEqual(packets, [mock.call.SendCreateCharacterPacket(1, "Nova", 6, 0, 0, 0, 0, 0)])
        self.assertTrue(window.board.get("busy"))

    def test_enter_in_the_field_creates_and_a_failure_enables_the_board_again(self):
        def enter(world, window, novaui):
            if novaui:
                window.board.insert_text(CREATE_FIELD, "\n")
            else:
                window.CreateCharacter()  # the edit line's return event

        def failure(world, window, novaui):
            world.time += 2.0
            window.OnUpdate()
            window.OnCreateFailure(1)
            window.stream.popupWindow.Close()

        legacy_world, _, novaui_world, window = self.both([type_name("Nova"), enter, failure])
        self.assertIn(("popup.Open", "CREATE_EXIST_SAME_NAME", "UI_OK"), novaui_world.log)
        self.assertFalse(window.board.get("busy"))

    def test_cancel_and_escape_in_the_field(self):
        legacy_world, _, novaui_world, _ = self.both([("cancel",)])
        self.assertEqual([c for c in novaui_world.log if c[0].startswith("stream.")],
                         [("stream.SetSelectCharacterPhase",)])

        def escape(world, window, novaui):
            if novaui:
                self.assertTrue(window.board.key(CREATE_FIELD, support.KEY_ESCAPE))
                self.assertFalse(window.board.key(CREATE_FIELD, support.KEY_RETURN))
            else:
                escape_event = [c[1] for c in window.editCharacterName.calls if c[0] == "SetEscapeEvent"][0]
                escape_event()

        legacy_world, _, novaui_world, _ = self.both([escape])
        self.assertIn(("stream.SetSelectCharacterPhase",), novaui_world.log)

    def test_f1_and_f2_select_man_and_woman(self):
        def keys(world, window, novaui):
            if novaui:
                self.assertTrue(window.OnKeyDown(KEYS["f1"]))
                self.assertTrue(window.OnKeyDown(KEYS["f2"]))
                self.assertTrue(window.OnKeyDown(KEYS["f1"]))
            else:
                # Legacy F1 and F2 name MAN_PAGE and WOMAN_PAGE, which do not
                # exist; what they meant:
                with self.assertRaises(NameError):
                    window.OnKeyDown(KEYS["f1"])
                for gender in (0, 1, 0):
                    window._CreateCharacterWindow__SelectGender(gender)

        legacy_world, _, novaui_world, window = self.both([keys])
        self.assertEqual(window.board.get("gender"), 0)

    def test_the_slot_keys_and_arrows_stay_in_the_phase_window(self):
        def keys(world, window, novaui):
            for key in ("1", "4", "left", "right", "right"):
                self.assertTrue(window.OnKeyDown(KEYS[key]))

        legacy_world, _, novaui_world, window = self.both([keys])
        self.assertEqual(window.board.get("slot"), 0)

    def test_the_board_does_nothing_while_busy_and_focuses_the_field_when_enabled_again(self):
        world = World(randoms=list(self.RANDOMS))
        with world:
            window = create_setup(world, True)
            board = window.board
            board.set_value(CREATE_FIELD, "Nova")
            board.fire("create")
            self.assertTrue(board.get("busy"))
            world.mark()
            for event in (("left",), ("right",), ("gender", 0), ("shape", 1), ("create",), ("cancel",)):
                board.fire(*event)
            self.assertFalse(board.key(CREATE_FIELD, support.KEY_ESCAPE))
            self.assertEqual((world.net_calls(), world.chr_calls(), world.log), ([], [], []))
            board.focused = None
            board.visible = False         # a focus that cannot happen yet
            window.EnableWindow()
            self.assertIsNone(board.focused)
            board.visible = True
            window.OnUpdate()
            self.assertEqual(board.focused, CREATE_FIELD)
            self.assertEqual(window._focus_tries, 0)

    def test_close_matches_legacy(self):
        legacy_world, _, novaui_world, window = self.both([lambda world, window, novaui: window.Close()])
        self.assertIsNone(window.board)
        self.assertEqual(window.stream, 0)


if __name__ == "__main__":
    unittest.main()
