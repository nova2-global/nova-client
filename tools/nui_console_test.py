"""Tests for the NovaUI developer console (assets/root/nui_console.py,
nui/windows/console/; P12 spec 6.5): python3 -B -m unittest nui_console_test
(from tools/).

Plain CPython over nui_game_support's stand-ins; install_wave5a_ui loads the
real consolemodule.py (its os calls on Game.console_os). The client defines
TRUE among Python's builtins (PythonLauncher.cpp), which legacy's edit line
returns; the tests define it too.

- facade: every method of P12 spec 6.5.4 exists with legacy's signature,
  the class constants are legacy's, and the command table is legacy's own
  (InitFunction): the same names and the same functions;
- differential: the legacy and the NovaUI console, made as game.py makes it
  and typed into as a player types (legacy's edit line, the board's field),
  print the same lines and make the same app, snd, net, chrmgr, background,
  chr, player and game window calls in order: open, pwd, perfinfo,
  mvol 0.2 and back, showui, an unknown command, a failing command, a
  /command (one net.SendChatPacket), an empty Enter, Escape; help and ?
  print the command list in NovaUI, where legacy raises UnboundLocalError;
- the 50-line limit, the line ids, and one model set per printed line;
- on demand: no board until OpenWindow, none after CloseWindow; the lines
  stay; Close() forgets the facade;
- no per-frame Python: no OnRender or OnUpdate; game.py's per-frame read of
  Console.collision is an attribute."""
import ast
import builtins
import contextlib
import inspect
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402

ROOT = support.ROOT
WINDOW_DIR = os.path.normpath(os.path.join(support.support.HERE, "..", "assets", "nui", "nui", "windows", "console"))
DOCUMENT = "nui/windows/console/console.rml"
FIELD = "console-field"
NOVAUI = "nui_console.ConsoleWindow"
EFFECT_MODULES = ("app", "snd", "net", "chrmgr", "background", "chr", "player", "game")
FACADE_METHODS = ("BindGameClass", "Close", "SetConsoleSize", "Hide", "Show", "IsShow", "OpenWindow", "CloseWindow",
                  "ProcessCommand", "InitFunction", "AddFunction", "Print", "UpdatePosition")
CONSTANTS = ("BACK_GROUND_COLOR", "EDIT_LINE_COLOR", "BUTTON_COLOR", "HEIGHT", "LINE_STEP", "MAX_LINE_COUNT")
INFO = {"INFO_ACTOR": 0, "INFO_ITEM": 1, "INFO_EFFECT": 2, "INFO_TEXTTAIL": 3}

if not hasattr(builtins, "TRUE"):
    builtins.TRUE = 1


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class Recorder(object):
    """A game window or Interface part the console's commands call."""

    def __init__(self, log, name):
        self._log = log
        self._name = name

    def __getattr__(self, attr):
        if attr.startswith("_"):
            raise AttributeError(attr)
        if attr in ("interface", "wndChat"):
            child = Recorder(self._log, self._name + "." + attr)
            setattr(self, attr, child)
            return child

        def record(*args):
            self._log.append((self._name + "." + attr, args))
        return record


class World(object):
    def __init__(self, nui_on, engine=True, windows="+rest"):
        game = self.game = support.Game(engine=engine)
        support.install_wave5a_ui(game)
        game.modules["systemSetting"].GetUINuiWindows = lambda: windows if nui_on else ""
        app = game.modules["app"]
        for name, value in INFO.items():
            setattr(app, name, value)
        support.define(app, "GetInfo", lambda kind: "info %d: 12 (Visible 9)" % kind)
        game.state.field_events[(DOCUMENT, FIELD)] = "submit"
        game.state.maxlength[(DOCUMENT, FIELD)] = 100
        game.load_standard()
        with quiet():
            self.module = game.load("nui_console", "nui_console.py")
        self.consoleModule = game.modules["consoleModule"]
        self.nui_windows = game.loaded["nui_windows"]
        self.nui_on = nui_on
        self.game_window = Recorder(game.log, "game")
        with game, quiet():
            # game.py:98-101
            self.console = self.nui_windows.make("console", self.consoleModule.ConsoleWindow, NOVAUI)
            self.console.BindGameClass(self.game_window)
            self.console.SetConsoleSize(game.modules["wndMgr"].GetScreenWidth(), 200)
            self.console.Hide()

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def board(self):
        demand = getattr(self.console, "demand", None)
        return demand.board() if demand is not None else None

    def effects_since(self, mark):
        return [(name, args) for name, args in self.game.log[mark:]
                if name.split(".", 1)[0] in EFFECT_MODULES and not support.is_getter(name)]

    def lines(self):
        if self.nui_on:
            return [str(text) for text in self.console.TextList]
        return [str(line.GetText()) for line in self.console.TextList]

    # --- the player's keys -------------------------------------------------------------

    def open(self):
        with self.game, quiet():
            self.console.OpenWindow()

    def enter(self, text):
        with self.game, quiet():
            if self.nui_on:
                board = self.board()
                if text:
                    board.insert_text(FIELD, text)
                board.insert_text(FIELD, "\n")
            else:
                self.console.EditLine.SetText(text)
                self.console.EditLine.OnIMEReturn()

    def escape(self):
        with self.game, quiet():
            if self.nui_on:
                return self.board().key(FIELD, support.support.KEY_ESCAPE)
            return self.console.EditLine.OnPressEscapeKey()


class Facade(unittest.TestCase):
    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)

    def test_the_facade_keeps_the_legacy_surface_and_signatures(self):
        legacy_class = self.world.consoleModule.ConsoleWindow
        facade = self.world.module.ConsoleWindow
        self.assertEqual(facade.__name__, legacy_class.__name__)
        self.assertIs(facade.NUI_FACADE, True)
        self.assertEqual(len(inspect.signature(facade.__init__).parameters),
                         len(inspect.signature(legacy_class.__init__).parameters))
        for method in FACADE_METHODS:
            self.assertTrue(callable(getattr(facade, method, None)), method)
            legacy = inspect.signature(getattr(object.__new__(legacy_class), method))
            novaui = inspect.signature(getattr(object.__new__(facade), method))
            self.assertEqual(len(legacy.parameters), len(novaui.parameters), method)
        for name in CONSTANTS:
            self.assertEqual(getattr(facade, name), getattr(legacy_class, name), name)
        self.assertIsNone(getattr(facade, "OnRender", None))
        self.assertIsNone(getattr(facade, "OnUpdate", None))

    def test_the_command_table_is_legacys_own(self):
        legacy = World(False)
        table = self.world.console.functionDict
        self.assertEqual({name: func.__qualname__ for name, func in table.items()},
                         {name: func.__qualname__ for name, func in legacy.console.functionDict.items()})
        for name, func in table.items():
            self.assertIs(func, getattr(self.world.consoleModule.Console, func.__name__), name)
        self.assertGreater(len(table), 60)
        self.assertIsInstance(self.world.console.Console, self.world.consoleModule.Console)
        self.assertIs(self.world.console.Console.output, self.world.console)

    def test_the_game_window_reads_collision_as_an_attribute(self):
        self.assertEqual(self.world.console.Console.collision, 0)
        with self.world.game, quiet():
            self.world.console.ProcessCommand("collision 1")
        self.assertTrue(self.world.console.Console.collision)

    def test_the_facade_answers_the_make_protocol(self):
        hud = self.world.game.loaded["nui_hud"]
        self.assertTrue(self.world.console.nui_ready())
        self.assertIs(hud.current("console"), self.world.console)
        older = World(True, engine=False)
        self.assertFalse(getattr(type(older.console), "NUI_FACADE", False))


class Flows(unittest.TestCase):
    def pair(self):
        legacy, novaui = World(False), World(True)
        for world in (legacy, novaui):
            world.__enter__()
            self.addCleanup(world.__exit__)
        return legacy, novaui

    def same(self, legacy, novaui, step, what):
        a, b = len(legacy.game.log), len(novaui.game.log)
        la, lb = len(legacy.lines()), len(novaui.lines())
        step(legacy)
        step(novaui)
        self.assertEqual(legacy.effects_since(a), novaui.effects_since(b), what)
        self.assertEqual(legacy.lines()[la:], novaui.lines()[lb:], what)
        self.assertEqual(legacy.console.IsShow(), novaui.console.IsShow(), what)
        return novaui.lines()[lb:]

    def test_the_commands_print_and_call_as_legacy(self):
        legacy, novaui = self.pair()
        printed = self.same(legacy, novaui, World.open, "open")
        self.assertEqual(printed, ["Current path is D:\\Ymir Work\\"])
        self.assertTrue(novaui.console.IsShow())
        self.assertEqual(novaui.board().focused, FIELD, "the field takes the focus")
        steps = (("pwd", 2), ("perfinfo", 5), ("mvol 0.2", 1), ("mvol 1.0", 1), ("showui", 1), ("nuiw5a", 1),
                 ("mvol", 2), ("ls", None), ("cd effect", None), ("up", None))
        for command, count in steps:
            printed = self.same(legacy, novaui, lambda w: w.enter(command), command)
            if count is not None:
                self.assertEqual(len(printed), count, command)
            self.assertEqual(printed[0], ">> " + command)
            self.assertEqual(novaui.board().get_value(FIELD), "", "the field empties")
        self.assertIn(("snd.SetMusicVolume", (0.2,)), novaui.game.log)
        self.assertIn(("game.interface.ShowDefaultWindows", ()), novaui.game.log)

    def test_a_slash_command_goes_to_the_server_and_prints_nothing(self):
        legacy, novaui = self.pair()
        self.same(legacy, novaui, World.open, "open")
        mark = len(novaui.game.log)
        printed = self.same(legacy, novaui, lambda w: w.enter("/nuiw5a"), "/nuiw5a")
        self.assertEqual(printed, [])
        self.assertEqual(novaui.effects_since(mark), [("net.SendChatPacket", ("/nuiw5a",))])

    def test_an_empty_enter_and_escape_close_and_the_lines_stay(self):
        for how in ("enter", "escape"):
            with self.subTest(how=how):
                legacy, novaui = self.pair()
                self.same(legacy, novaui, World.open, "open")
                self.same(legacy, novaui, lambda w: w.enter("pwd"), "pwd")
                kept = list(novaui.console.TextList)
                step = (lambda w: w.enter("")) if how == "enter" else World.escape
                self.same(legacy, novaui, step, how)
                self.assertFalse(novaui.console.IsShow())
                self.assertIsNone(novaui.board())
                self.assertEqual(novaui.console.TextList, kept)
                printed = self.same(legacy, novaui, World.open, "open again")
                self.assertEqual(novaui.board().get("lines")[-len(kept) - 1:-1],
                                 [{"id": i, "text": t} for i, t in zip(novaui.console.lineIds[-len(kept) - 1:-1], kept)])
                self.assertEqual(printed, ["Current path is D:\\Ymir Work\\"])

    def test_escape_is_kept_and_other_keys_go_on(self):
        world = World(True)
        world.open()
        with world.game:
            self.assertIsNone(world.board().handlers[(FIELD, "keydown")]({"key_identifier": 5}))
        self.assertIs(world.escape(), True)

    def test_help_and_the_question_mark_print_the_list_where_legacy_raises(self):
        legacy, novaui = self.pair()
        legacy.open()
        novaui.open()
        novaui.console.MAX_LINE_COUNT = 1000  # every line of the list, for the test
        names = sorted(novaui.console.functionDict)
        for command in ("?", "help", "h", "help pwd", "help nosuch"):
            with self.subTest(command=command):
                with legacy.game, quiet(), self.assertRaises(UnboundLocalError):
                    legacy.console.ProcessCommand(command)
                before = len(novaui.lines())
                with novaui.game, quiet():
                    novaui.console.ProcessCommand(command)
                printed = novaui.lines()[before:]
                self.assertEqual(printed[0], ">> " + command)
                if command == "?":
                    listed = [name for line in printed[1:] for name in line.split()[1::2]]
                    self.assertEqual(listed, names)
                elif command == "help pwd":
                    self.assertEqual(printed[1:], ["pwd : Show current path", ""])
                else:
                    self.assertEqual(len(printed), 1 + len(names) + 3 + 1)
                    self.assertIn("mvol(1) : Set BGM volumn (0 ~ 1.0)", printed)
                    self.assertEqual(printed[-4:], ["? : All commands list", "h : Help for all commands",
                                                    "h blah : Help for blah", ""])

    def test_help_for_a_command_with_arguments_names_them(self):
        world = World(True)
        world.open()
        before = len(world.lines())
        with world.game, quiet():
            world.console.ProcessCommand("help mvol")
        self.assertEqual(world.lines()[before + 1:], ["mvol(1) : Set BGM volumn (0 ~ 1.0)", "   arg : ('arg',)", ""])


class Lines(unittest.TestCase):
    def test_the_console_keeps_the_last_50_lines_with_rising_ids(self):
        world = World(True)
        world.open()
        with world.game, quiet():
            for i in range(60):
                world.console.Print("line %d" % i)
        lines = world.board().get("lines")
        self.assertEqual(len(lines), 50)
        self.assertEqual(lines[-1]["text"], "line 59")
        self.assertEqual(lines[0]["text"], "line 10")
        ids = [line["id"] for line in lines]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(set(ids)), 50)
        legacy = World(False)
        with legacy.game, quiet():
            legacy.console.OpenWindow()
            for i in range(60):
                legacy.console.Print("line %d" % i)
        self.assertEqual(len(legacy.console.TextList), 50)
        self.assertEqual(world.lines(), legacy.lines())

    def test_each_print_sets_the_lines_once(self):
        world = World(True)
        world.open()
        board = world.board()
        before = [call for call in board.calls if call[0] == "set"]
        with world.game, quiet():
            world.console.Print("one")
            world.console.Print(7)
        sets = [call for call in board.calls if call[0] == "set"][len(before):]
        self.assertEqual([list(call[1]) for call in sets], [["lines"], ["lines"]])
        self.assertEqual(board.get("lines")[-1]["text"], "7")

    def test_the_band_is_the_screens_width_and_keeps_a_resized_height(self):
        world = World(True)
        world.game.state.scale = 2.0
        world.open()
        board = world.board()
        self.assertEqual((board.get("width"), board.get("height")), ("800.00", "200.00"))
        with world.game:
            board.fire("resized", 800.0, 320.5)
        self.assertEqual(board.get("height"), "320.50")
        with world.game, quiet():
            world.console.CloseWindow()
            world.console.OpenWindow()
        self.assertEqual(world.board().get("height"), "320.50", "a new board keeps it")
        world.game.state.scale = 1.0
        with world.game:
            world.board().on_scale_changed(1.0)
        self.assertEqual(world.board().get("width"), "1600.00")


class OnDemand(unittest.TestCase):
    def test_the_board_exists_only_while_the_console_shows(self):
        world = World(True)
        boards = [w for w in world.game.state.windows if w.DOCUMENT == DOCUMENT]
        self.assertEqual(len(boards), 1, "the probe made one")
        self.assertFalse(boards[0]._doc, "and destroyed it")
        self.assertIsNone(world.board())
        world.open()
        self.assertIsNotNone(world.board())
        with world.game, quiet():
            world.console.CloseWindow()
        self.assertIsNone(world.board())

    def test_close_forgets_the_facade_and_ends_the_command_objects_output(self):
        world = World(True)
        world.open()
        hud = world.game.loaded["nui_hud"]
        with world.game, quiet():
            world.console.BindGameClass(0)
            world.console.Close()
        self.assertIsNone(hud.current("console"))
        self.assertEqual(world.console.Console.output, 0)
        self.assertEqual([w for w in world.game.state.windows if w.DOCUMENT == DOCUMENT and w._doc], [])


class NoPerFramePython(unittest.TestCase):
    def test_the_module_defines_no_per_frame_method(self):
        tree = ast.parse(read(os.path.join(ROOT, "nui_console.py")))
        names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        self.assertFalse(names & {"OnUpdate", "OnRender", "OnMouseOverIn"})

    def test_every_fixture_holds_every_model_key_with_its_kind(self):
        world = World(True)
        model = world.console.nui_model()
        names = sorted(name for name in os.listdir(WINDOW_DIR) if name.endswith(".fixture.json"))
        self.assertEqual(names, ["console.fixture.json", "console.full.fixture.json"])
        for name in names:
            with self.subTest(fixture=name):
                fixture = json.loads(read(os.path.join(WINDOW_DIR, name)))["console"]
                self.assertEqual(set(fixture), set(model))
                for key in ("width", "height"):
                    self.assertIsInstance(fixture[key], str)
                    float(fixture[key])
                for line in fixture["lines"]:
                    self.assertEqual(set(line), {"id", "text"})
                self.assertLessEqual(len(fixture["lines"]), 50)


if __name__ == "__main__":
    unittest.main()
