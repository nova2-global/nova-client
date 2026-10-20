"""Tests for the NovaUI maintenance countdown (assets/root/nui_maintenance.py,
P18, NOVA-58): python3 -B -m unittest nui_maintenance_test (from tools/).

The legacy uiMaintenance.MaintenanceWindow (over nui_game_support's tooltip
ui stand-ins: ThinBoard, TextLine with its text metric, a Button, and
localeInfo over the real locale_game.txt with localeinfo.py's own
RTSecondToDHMS) and the NovaUI facade, each in a world of its own on the
same clock (app.GetTime and nui.now move together), driven as game.py drives
them: its own OpenShutdownCountdown and CloseShutdownCountdown, read from
game.py and run against each world's window. Legacy redraws from its
OnUpdate, which the client calls every frame while it shows; the NovaUI
countdown is a nui-countdown whose text the test reads by the element's rule
(round="up": the time left to the millisecond, rounded up; format="dhms",
the same RTSecondToDHMS) from the end the facade wrote, and whose
countdownend the test sends where the element sends it (remaining 0). Both
show the same time at every sampled instant, show and hide at the same
calls and instants, and make the same calls."""
import ast
import contextlib
import io
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402

ROOT = support.ROOT
WINDOWS = os.path.normpath(os.path.join(support.support.HERE, "..", "assets", "nui", "nui", "windows"))
DOCUMENT = "nui/windows/maintenance/maintenance.rml"
START = 1000.0


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def install_maintenance_ui(game):
    """What uimaintenance.py builds beyond install_tooltip_ui's widgets: a
    Button that keeps its visuals, tooltip and event (click() is a press),
    and the text line's vertical alignment calls."""
    ui = support.install_tooltip_ui(game)
    Widget = ui.TooltipWidget

    class Button(Widget):
        def __init__(self, layer="UI"):
            Widget.__init__(self, layer)
            self.visuals = {}
            self.tooltip = ""
            self.event = None
            self.size = (15, 15)

        def SetUpVisual(self, path):
            self.visuals["up"] = path

        def SetOverVisual(self, path):
            self.visuals["over"] = path

        def SetDownVisual(self, path):
            self.visuals["down"] = path

        def SetToolTipText(self, text, x=0, y=0):
            self.tooltip = text

        def SetEvent(self, event, *args):
            self.event = event

        def click(self):
            if self.event is not None:
                self.event()

    ui.Button = Button
    ui.TextLine.SetVerticalAlignCenter = lambda self: None
    ui.__mem_func__ = lambda fn: fn
    return ui


class World(object):
    """One side: a Game with the stand-ins, uiMaintenance and the NovaUI
    module, and the clock both read."""

    def __init__(self, nui_on, engine=True, windows="+maintenance", failing=False):
        self.game = support.Game(engine=engine)
        self.game.modules["systemSetting"].GetUINuiWindows = lambda: windows if nui_on else ""
        self.ui = install_maintenance_ui(self.game)
        self.clock = [START]
        self.game.modules["app"].GetTime = lambda: self.clock[0]
        self.game.state.now = START
        if failing:
            self.game.state.failing.add(DOCUMENT)
        self.game.load_standard()
        with quiet():
            # The text line stand-in's metric reads nui_text.
            self.game.load("nui_text", "nui_text.py")
            self.uiMaintenance = self.game.load("uiMaintenance", "uimaintenance.py")
            self.module = self.game.load("nui_maintenance", "nui_maintenance.py")
        self.nui_windows = self.game.loaded["nui_windows"]
        self.nui_on = nui_on
        self.ended = 0
        with self.game, quiet():
            # game.py's line (the wiring test checks it is game.py's).
            self.window = self.nui_windows.make("maintenance", self.uiMaintenance.MaintenanceWindow,
                                                "nui_maintenance.MaintenanceWindow")

    def board(self):
        demand = getattr(self.window, "demand", None)
        return demand.board() if demand is not None else None

    def handlers(self):
        """game.py's OpenShutdownCountdown and CloseShutdownCountdown, its own
        code, bound to an object whose wndMaintenance is this world's."""
        tree = ast.parse(read(os.path.join(ROOT, "game.py")))
        found = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in ("OpenShutdownCountdown", "CloseShutdownCountdown"):
                module = ast.Module(body=[node], type_ignores=[])
                namespace = {}
                exec(compile(module, "game.py", "exec"), namespace)
                found[node.name] = namespace[node.name]
        owner = type("Game", (), {})()
        owner.wndMaintenance = self.window
        return (lambda seconds: found["OpenShutdownCountdown"](owner, seconds),
                lambda: found["CloseShutdownCountdown"](owner))

    def at(self, t):
        """The clock at START + t, then one frame: legacy's OnUpdate while
        its window shows; the NovaUI countdown's end while its board shows."""
        self.clock[0] = START + t
        self.game.state.now = START + t
        with self.game, quiet():
            if not self.nui_on:
                if self.window.IsShow():
                    self.window.OnUpdate()
                return
            board = self.board()
            if board is not None and board.is_visible() and remaining(board.model["end"], self.game.state.now) <= 0:
                self.ended += 1
                board.fire("ended")

    def shown_time(self, locale_info):
        """The time the window shows now, or None while it is hidden."""
        if not self.window.IsShow():
            return None
        if not self.nui_on:
            return self.window.timeLeft.text
        board = self.board()
        return locale_info.RTSecondToDHMS(remaining(board.model["end"], self.game.state.now))


def remaining(end, now):
    """nui-countdown round="up" (ElementCountdown::Remaining): the time left
    to the millisecond, rounded up; 0 at the end and after it."""
    ms = int(round((end - now) * 1000.0))
    return (ms + 999) // 1000 if ms > 0 else 0


class MaintenanceTest(unittest.TestCase):
    def worlds(self, **kwargs):
        return World(False, **kwargs), World(True, **kwargs)

    def locale(self, world):
        return world.game.modules["localeInfo"]

    def follow(self, worlds, times, opens):
        """Runs `opens` (t: seconds or "close") at their times and reads both
        windows at every time; each entry (t, legacy, novaui)."""
        seen = []
        for t in sorted(set(times) | set(opens)):
            for world in worlds:
                world.at(t)
                if t in opens:
                    open_, close = world.handlers()
                    with world.game, quiet():
                        if opens[t] == "close":
                            close()
                        else:
                            open_(opens[t])
            seen.append((t,) + tuple(world.shown_time(self.locale(world)) for world in worlds))
        return seen


class Differential(MaintenanceTest):
    def test_the_countdown_shows_legacy_s_time_at_every_instant_and_hides_at_its_end(self):
        legacy, novaui = worlds = self.worlds()
        times = [0.0, 0.0004, 0.4, 0.9994, 1.0006, 1.5, 5.0, 64.9, 65.0006, 124.0, 124.4, 124.9994, 125.0, 125.2, 130.0]
        seen = self.follow(worlds, times, {0.0: "125"})
        for t, a, b in seen:
            self.assertEqual(b, a, "t=%s" % t)
        self.assertEqual(seen[0][1], "2 Minutes, 5 Sec", "125 seconds until a whole one has passed")
        self.assertEqual(dict((t, a) for t, a, _ in seen)[124.9994], "1 Sec", "1 in the last second, as legacy")
        self.assertIsNone(dict((t, a) for t, a, _ in seen)[125.0], "hidden at the end")
        self.assertEqual(novaui.ended, 1)
        self.assertIsNone(novaui.board(), "the document goes with the countdown")

    def test_hours_and_days_read_as_legacy_s(self):
        for seconds in ("3725", "93784", "86400", "3600", "61", "59"):
            legacy, novaui = worlds = self.worlds()
            seen = self.follow(worlds, [0.0, 0.5, 1.2], {0.0: seconds})
            with self.subTest(seconds=seconds):
                for t, a, b in seen:
                    self.assertEqual(b, a, "t=%s" % t)
        self.assertEqual(self.locale(legacy).RTSecondToDHMS(93784), "1 Days, 2 Hours, 3 Minutes, 4 Sec")

    def test_a_schedule_brought_forward_and_a_cancel_and_a_new_schedule(self):
        worlds = self.worlds()
        seen = self.follow(worlds, [0.0, 10.0, 10.5, 20.0, 30.0, 31.0, 40.0],
                           {0.0: "600", 10.0: "120", 20.0: "close", 30.0: "45"})
        for t, a, b in seen:
            self.assertEqual(b, a, "t=%s" % t)
        by_time = dict((t, a) for t, a, _ in seen)
        self.assertEqual((by_time[10.0], by_time[20.0], by_time[30.0]), ("2 Minutes", None, "45 Sec"))

    def test_no_time_left_and_a_bad_token_show_nothing(self):
        for seconds in ("0", "-5", "abc", "1.5"):
            worlds = self.worlds()
            seen = self.follow(worlds, [0.0, 0.5], {0.0: seconds})
            with self.subTest(seconds=seconds):
                self.assertEqual([(a, b) for _, a, b in seen], [(None, None), (None, None)])

    def test_the_close_button_closes_both_and_the_next_schedule_opens_them_again(self):
        legacy, novaui = self.worlds()
        results = []
        for world in (legacy, novaui):
            world.at(0.0)
            open_, _ = world.handlers()
            with world.game, quiet():
                open_("300")
                mark = len(world.game.log)
                if world.nui_on:
                    world.board().fire("close_press", 0)
                else:
                    world.window.closeButton.click()
                closed = world.window.IsShow()
                open_("90")
            results.append((closed, world.window.IsShow(), world.shown_time(self.locale(world)),
                            [call for call in world.game.log[mark:] if call[0].split(".")[0] in support.COMPARED]))
        self.assertEqual(results[1], results[0])
        self.assertEqual(results[0][:3], (False, True, "1 Minutes, 30 Sec"))


class Facade(MaintenanceTest):
    def test_the_class_the_methods_and_no_per_frame_python(self):
        world = World(True)
        window = world.window
        self.assertEqual(type(window).__module__, "nui_maintenance")
        self.assertTrue(window.NUI_FACADE)
        self.assertIsNone(type(window).OnUpdate)
        self.assertIsNone(type(window).OnRender)
        legacy = world.uiMaintenance.MaintenanceWindow
        for name in ("POSITION", "HEIGHT", "PADDING", "GAP"):
            self.assertEqual(getattr(type(window), name), getattr(legacy, name), name)
        for name in ("Open", "Close", "Show", "Hide", "IsShow", "SetTop", "Destroy"):
            self.assertTrue(callable(getattr(window, name)), name)
        source = read(os.path.join(ROOT, "nui_maintenance.py"))
        self.assertNotRegex(source, r"def OnUpdate|def OnRender")

    def test_make_builds_legacy_with_the_flag_off_an_older_exe_or_a_document_that_does_not_load(self):
        for kwargs, reason in (({"windows": ""}, "flag off"), ({"engine": False}, None), ({"failing": True}, None)):
            world = World(True, **kwargs)
            with self.subTest(kwargs=kwargs):
                self.assertIs(type(world.window), world.uiMaintenance.MaintenanceWindow)
                self.assertEqual(world.game.loaded_documents(), [])
        world = World(False)
        self.assertIs(type(world.window), world.uiMaintenance.MaintenanceWindow)

    def test_the_board_exists_only_while_the_countdown_shows(self):
        world = World(True)
        self.assertEqual(world.game.loaded_documents(), [], "nothing until a schedule")
        open_, close = world.handlers()
        with world.game, quiet():
            open_("125")
        self.assertEqual(world.game.loaded_documents(), [DOCUMENT])
        self.assertEqual(world.board().model["end"], START + 125.0, "nui.now() plus the seconds left")
        with world.game, quiet():
            close()
        self.assertEqual(world.game.loaded_documents(), [])
        with world.game, quiet():
            open_("10")
            world.window.Destroy()
        self.assertEqual(world.game.loaded_documents(), [])
        self.assertFalse(world.window.IsShow())

    def test_each_open_raises_it_above_the_other_novaui_windows_and_a_press_raises_it(self):
        world = World(True)
        open_, _ = world.handlers()
        with world.game, quiet():
            open_("125")
            board = world.board()
            self.assertEqual(board.front, 1, "legacy's SetTop at Open")
            board.fire("board_press", 1)
            self.assertEqual(board.front, 2)
            board.fire("board_press", 2)
            self.assertEqual(board.front, 2, "the middle button raises nothing")
            open_("60")
        self.assertIs(world.board(), board, "a shown countdown keeps its board")
        self.assertEqual(board.front, 3)
        self.assertEqual(board.model["end"], START + 60.0)

    def test_it_draws_above_the_legacy_ui_layer_unlike_the_affects(self):
        """The migration inventory (6.1, NOVA-58): the countdown must stay
        visible above the NovaUI HUD windows at the top left, which draw
        below the legacy UI layer (the affects). Its document has no
        nui-below-legacy-ui, so it draws in the band above that layer, as a
        legacy dialog the G5 stopgap raises; the body takes no pointer and
        the board does."""
        markup = read(os.path.join(WINDOWS, "maintenance", "maintenance.rml"))
        body = re.search(r"<body[^>]*\bclass=\"([^\"]*)\"", markup).group(1).split()
        self.assertNotIn("nui-below-legacy-ui", body)
        self.assertIn("nui-overlay", body)
        affects = read(os.path.join(WINDOWS, "affects", "affects.rml"))
        self.assertIn("nui-below-legacy-ui", re.search(r"<body[^>]*\bclass=\"([^\"]*)\"", affects).group(1).split())
        self.assertRegex(markup, r'id="maintenance" class="nui-board nui-fx nui-interactive')
        sheet = read(os.path.join(WINDOWS, "maintenance", "maintenance.rcss"))
        self.assertIn("left: 10dp;\n\ttop: 70dp;", sheet, "legacy's (10, 70)")

    def test_the_countdown_element_is_legacy_s_count_and_format(self):
        markup = read(os.path.join(WINDOWS, "maintenance", "maintenance.rml"))
        element = re.search(r"<nui-countdown[^>]*/>", markup, re.S).group(0)
        for attribute in ('format="dhms"', 'round="up"', 'hold-width=', 'day="@game.DAY"', 'hour="@game.HOUR"',
                          'minute="@game.MINUTE"', 'second="@game.SECOND"', 'data-attr-end="end"',
                          'data-event-countdownend="ended()"'):
            self.assertIn(attribute, element)
        self.assertIn("@game.MAINTENANCE_TIME_LEFT", markup)

    def test_every_fixture_has_the_model_s_keys_and_kinds(self):
        import json
        world = World(True)
        kinds = dict((key, type(value).__name__) for key, value in world.window._state.items())
        for variant in ("", "days", "seconds"):
            name = "maintenance.%s.fixture.json" % variant if variant else "maintenance.fixture.json"
            with open(os.path.join(WINDOWS, "maintenance", name), encoding="utf-8") as handle:
                (model,) = json.load(handle).values()
            self.assertEqual(dict((key, type(value).__name__) for key, value in model.items()), kinds, variant)

    def test_the_wiring_lines(self):
        game = read(os.path.join(ROOT, "game.py"))
        self.assertIn('self.wndMaintenance = nui_windows.make("maintenance", uiMaintenance.MaintenanceWindow, '
                      '"nui_maintenance.MaintenanceWindow")', game)
        self.assertIn('"shutdown_schedule"\t\t: self.OpenShutdownCountdown', game)
        self.assertIn('"shutdown_cancel"\t\t: self.CloseShutdownCountdown', game)
        self.assertIn("\t\tif self.wndMaintenance:\n\t\t\tself.wndMaintenance.Close()\n"
                      "\t\t\t# The NovaUI countdown's parts go with it (P18); legacy only drops the reference.\n"
                      "\t\t\tif getattr(self.wndMaintenance, \"NUI_FACADE\", False):\n"
                      "\t\t\t\tself.wndMaintenance.Destroy()\n\t\t\tself.wndMaintenance = None", game)

    def test_a_new_game_phase_s_window_takes_over_the_last_one(self):
        world = World(True)
        open_, _ = world.handlers()
        with world.game, quiet():
            open_("125")
            newer = world.nui_windows.make("maintenance", world.uiMaintenance.MaintenanceWindow,
                                           "nui_maintenance.MaintenanceWindow")
        self.assertIsNone(world.window.demand, "the earlier window's parts went")
        self.assertEqual(world.game.loaded_documents(), [])
        self.assertIsNotNone(newer.demand)


if __name__ == "__main__":
    unittest.main()
