"""Tests for the NovaUI web window (assets/root/nui_web.py, nui/windows/web/;
P12 spec 6.4): python3 -B -m unittest nui_web_test (from tools/).

Plain CPython over nui_game_support's stand-ins; install_wave5a_ui loads
the real uiweb.py with its uiscript, and the Interface's web methods
(__MakeWebWindow, OpenWebWindow, CloseWbWindow) are compiled from
interfacemodule.py, so the wiring under test is the real one.

- facade: every method of P12 spec 6.4.3 exists with legacy's signature;
- differential: the legacy and the NovaUI window, made and opened as the
  Interface makes and opens them, make the same app calls in order (the
  page's address compared, its rectangle recorded: the NovaUI page sits on
  the frame's page area, which differs from legacy's frame in modern):
  open, close, Escape, destroy, and IsShow while open (game.py's key
  rule); the NovaUI window then has the client follow the page area
  (nuigame.WebPageFollow with the document and web-page) and stops it at
  close;
- the page rectangle: the page area's box once laid out, else legacy's
  rectangle of a centered frame at the scale in use;
- on demand: no board until Open, none after Close; the Wave 5a engine is
  needed;
- no per-frame Python: no OnUpdate (legacy moves the page every frame)."""
import ast
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
WINDOW_DIR = os.path.normpath(os.path.join(support.support.HERE, "..", "assets", "nui", "nui", "windows", "web"))
DOCUMENT = "nui/windows/web/web.rml"
URL = "http://example.com/ishop?pid=1&c=0&sid=1&sas=0123456789abcdef"
FACADE_METHODS = ("LoadWindow", "Destroy", "Open", "Close", "Clear", "Refresh", "OnPressEscapeKey", "Show", "Hide",
                  "IsShow", "SetTop")


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class Chat(object):
    def __init__(self, log):
        self.log = log

    def CloseChat(self):
        self.log.append(("interface.wndChat.CloseChat", ()))


class InterfaceBase(object):
    def __init__(self, log):
        self.wndWeb = None
        self.wndChat = Chat(log)


def interface_class(namespace):
    methods = support.source_of("interfacemodule.py", ("__MakeWebWindow", "OpenWebWindow", "CloseWbWindow"),
                                inside="Interface")
    body = "\n".join("\t" + line if line else line for line in methods.split("\n"))
    exec(compile("class Interface(InterfaceBase):\n" + body + "\n", "interfacemodule.py", "exec"), namespace)
    return namespace["Interface"]


class World(object):
    def __init__(self, nui_on, engine=True, windows="+rest", screen=(1600, 900), scale=1.0, lack=()):
        game = self.game = support.Game(engine=engine)
        support.install_wave5a_ui(game)
        game.modules["systemSetting"].GetUINuiWindows = lambda: windows if nui_on else ""
        wndmgr = game.modules["wndMgr"]
        wndmgr.GetScreenWidth = lambda: screen[0]
        wndmgr.GetScreenHeight = lambda: screen[1]
        game.state.scale = scale
        if lack:
            game.modules["nuigame"].lack(*lack)
        game.load_standard()
        with quiet():
            self.module = game.load("nui_web", "nui_web.py")
        self.uiWeb = game.modules["uiWeb"]
        self.nui_windows = game.loaded["nui_windows"]
        self.nui_on = nui_on
        namespace = {"ui": game.modules["ui"], "uiWeb": self.uiWeb, "nui_windows": self.nui_windows,
                     "InterfaceBase": InterfaceBase}
        self.interface = interface_class(namespace)(game.log)
        with game, quiet():
            self.interface._Interface__MakeWebWindow()

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    @property
    def window(self):
        return self.interface.wndWeb

    def board(self):
        demand = getattr(self.window, "demand", None)
        return demand.board() if demand is not None else None

    def calls_since(self, mark, prefixes=("app.", "interface.")):
        return [(name, args) for name, args in self.game.log[mark:] if name.startswith(prefixes)]

    def run(self, step):
        mark = len(self.game.log)
        with self.game, quiet():
            step(self)
        return self.calls_since(mark)


def comparable(calls):
    """The calls with ShowWebPage's rectangle left out (recorded, not compared)."""
    return [(name, args[:1]) if name == "app.ShowWebPage" else (name, args) for name, args in calls]


class Facade(unittest.TestCase):
    def test_the_facade_keeps_the_legacy_surface_and_signatures(self):
        world = World(True)
        legacy_class = world.uiWeb.WebWindow
        facade = world.module.WebWindow
        self.assertEqual(facade.__name__, legacy_class.__name__)
        self.assertIs(facade.NUI_FACADE, True)
        self.assertEqual(len(inspect.signature(facade.__init__).parameters),
                         len(inspect.signature(legacy_class.__init__).parameters))
        for method in FACADE_METHODS:
            self.assertTrue(callable(getattr(facade, method, None)), method)
            legacy = inspect.signature(getattr(object.__new__(legacy_class), method))
            novaui = inspect.signature(getattr(object.__new__(facade), method))
            self.assertEqual(len(legacy.parameters), len(novaui.parameters), method)
        for method in ("SetCenterPosition", "GetWidth", "GetHeight", "Lock", "Unlock"):
            self.assertTrue(callable(getattr(facade, method, None)), method)
        self.assertIsNone(getattr(facade, "OnUpdate", None), "C++ follows the window")

    def test_the_interface_makes_the_facade_with_the_flag_and_the_engine(self):
        self.assertTrue(getattr(type(World(True).window), "NUI_FACADE", False))
        self.assertFalse(getattr(type(World(False).window), "NUI_FACADE", False))
        older = World(True, lack=("WebPageFollow",))
        self.assertFalse(getattr(type(older.window), "NUI_FACADE", False), "the web window needs the Wave 5a engine")
        self.assertIn("nui_windows: web: the document did not load; using the legacy window", older.game.dbg.errors)


class Flows(unittest.TestCase):
    def pair(self):
        return World(False), World(True)

    def test_open_shows_the_page_with_legacys_address_and_follows_the_page_area(self):
        legacy, novaui = self.pair()
        steps = lambda w: w.interface.OpenWebWindow(URL)
        legacy_calls, novaui_calls = legacy.run(steps), novaui.run(steps)
        self.assertEqual(comparable(legacy_calls), comparable(novaui_calls))
        self.assertEqual([name for name, _ in novaui_calls], ["app.ShowWebPage", "interface.wndChat.CloseChat"])
        self.assertEqual(novaui.game.web["follow"], (DOCUMENT, "web-page"))
        follows = [args for name, args in novaui.game.log if name == "nuigame.WebPageFollow"]
        self.assertEqual(follows, [(DOCUMENT, "web-page")])
        show = [i for i, (name, _) in enumerate(novaui.game.log) if name == "app.ShowWebPage"][0]
        follow = [i for i, (name, _) in enumerate(novaui.game.log) if name == "nuigame.WebPageFollow"][0]
        self.assertLess(show, follow, "the page first, then the follow")
        self.assertTrue(legacy.window.IsShow() and novaui.window.IsShow())
        board = novaui.board()
        self.assertEqual(board.calls[-3:], [("show",), ("center",), ("bring_to_front",)])
        self.assertTrue(novaui.window.escapeProxy.is_shown())
        self.assertEqual(novaui.window.escapeProxy._window.layer, "TOP_MOST")

    def test_close_escape_and_destroy_hide_the_page_as_legacy(self):
        for how in ("close", "button", "escape", "interface", "destroy"):
            with self.subTest(how=how):
                legacy, novaui = self.pair()
                for world in (legacy, novaui):
                    world.run(lambda w: w.interface.OpenWebWindow(URL))

                def step(w):
                    if how == "close":
                        w.window.Close()
                    elif how == "button":
                        if w.nui_on:
                            w.board().fire("act", "close", 0)
                        else:
                            w.window.titleBar.close()
                    elif how == "escape":
                        if w.nui_on:
                            self.assertIs(w.window.escapeProxy._window.OnPressEscapeKey(), True)
                        else:
                            self.assertIs(w.window.OnPressEscapeKey(), True)
                    elif how == "interface":
                        w.interface.CloseWbWindow()
                    else:
                        w.window.Destroy()
                self.assertEqual(legacy.run(step), novaui.run(step))
                self.assertFalse(novaui.game.web["mode"])
                self.assertIsNone(novaui.game.web["follow"], "the follow stops")
                self.assertFalse(novaui.window.IsShow())
                self.assertIsNone(novaui.board())

    def test_a_press_with_the_right_button_does_not_close(self):
        world = World(True)
        world.run(lambda w: w.interface.OpenWebWindow(URL))
        with world.game:
            world.board().fire("act", "close", 1)
        self.assertTrue(world.window.IsShow())

    def test_is_show_answers_while_open_for_the_game_windows_key_rule(self):
        world = World(True)
        self.assertFalse(world.window.IsShow())
        world.run(lambda w: w.interface.OpenWebWindow(URL))
        self.assertTrue(world.window.IsShow())
        world.run(lambda w: w.window.Close())
        self.assertFalse(world.window.IsShow())

    def test_a_second_open_shows_the_new_address_on_the_same_window(self):
        world = World(True)
        world.run(lambda w: w.interface.OpenWebWindow(URL))
        calls = world.run(lambda w: w.interface.OpenWebWindow(URL + "&page=2"))
        self.assertEqual(calls[0][1][0], URL + "&page=2")


class PageRect(unittest.TestCase):
    def test_the_page_sits_on_the_page_areas_box_once_laid_out(self):
        world = World(True)
        world.game.state.boxes[(DOCUMENT, "web-page")] = (433.0, 196.0, 734.0, 541.0)
        calls = world.run(lambda w: w.interface.OpenWebWindow(URL))
        self.assertEqual(calls[0], ("app.ShowWebPage", (URL, (433, 196, 1167, 737))))

    def test_before_a_layout_it_takes_legacys_rectangle_of_a_centered_frame(self):
        for scale, screen, expected in ((1.0, (1600, 900), (430, 185, 1170, 735)),
                                        (1.5, (1920, 1080), (405, 142, 1515, 967)),
                                        (2.0, (1600, 900), (60, 60, 1540, 880))):
            with self.subTest(scale=scale):
                world = World(True, screen=screen, scale=scale)
                calls = world.run(lambda w: w.interface.OpenWebWindow(URL))
                self.assertEqual(calls[0][1][1], expected)

    def test_at_100_percent_the_fallback_is_legacys_rectangle(self):
        novaui = World(True)
        x, y = (1600 - 760) // 2, (900 - 590) // 2
        self.assertEqual(novaui.window.page_rect(), (x + 10, y + 30, x + 750, y + 580))


class OnDemand(unittest.TestCase):
    def test_the_board_exists_only_while_the_window_is_open(self):
        world = World(True)
        boards = [w for w in world.game.state.windows if w.DOCUMENT == DOCUMENT]
        self.assertEqual(len(boards), 1, "the probe made one")
        self.assertFalse(boards[0]._doc, "and destroyed it")
        self.assertIsNone(world.board(), "the Interface's Hide after LoadWindow leaves none")
        world.run(lambda w: w.interface.OpenWebWindow(URL))
        self.assertIsNotNone(world.board())
        world.run(lambda w: w.window.Close())
        self.assertEqual([w for w in world.game.state.windows if w.DOCUMENT == DOCUMENT and w._doc], [])

    def test_destroy_forgets_the_facade(self):
        world = World(True)
        hud = world.game.loaded["nui_hud"]
        self.assertIs(hud.current("web"), world.window)
        world.run(lambda w: w.window.Destroy())
        self.assertIsNone(hud.current("web"))


class NoPerFramePython(unittest.TestCase):
    def test_the_module_defines_no_per_frame_method(self):
        tree = ast.parse(read(os.path.join(ROOT, "nui_web.py")))
        names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        self.assertFalse(names & {"OnUpdate", "OnRender", "OnMouseOverIn"})

    def test_the_fixture_holds_the_empty_model(self):
        world = World(True)
        fixture = json.loads(read(os.path.join(WINDOW_DIR, "web.fixture.json")))
        self.assertEqual(fixture, {"web": world.module.WebBoard.initial_model(None)})

    def test_the_page_area_has_no_border_padding_or_radius(self):
        """The client puts the page on the element's border box."""
        sheet = read(os.path.join(WINDOW_DIR, "web.rcss"))
        rule = sheet[sheet.index(".web__page"):]
        rule = rule[:rule.index("}")]
        for name in ("border", "padding", "radius"):
            self.assertNotIn(name, rule)


if __name__ == "__main__":
    unittest.main()
