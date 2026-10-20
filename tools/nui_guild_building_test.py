"""Tests for the NovaUI guild building placement window
(assets/root/nui_guild_building.py, nui/windows/guild-building/; P12 spec
6.3): python3 -B -m unittest nui_guild_building_test (from tools/).

Plain CPython over nui_game_support's stand-ins; install_wave5a_ui compiles
the real uiGuild.BuildGuildBuildingWindow from uiguild.py over them, with
its real uiscript and the en guild building list (66 rows), and the
Interface's guild building methods (BUILD_OpenWindow, BUILD_CloseWindow,
BUILD_OnUpdate, BUILD_OnMouseLeftButtonDown and Up, __HideWindows and
__ShowWindows) are compiled from interfacemodule.py, so the wiring under
test is the real one.

- facade: every method of P12 spec 6.3.4 exists on the facade with
  legacy's signature, and the class constants have legacy's values;
- differential: a legacy and a NovaUI world, each opened through the
  Interface and pressed as a player presses it (legacy's widgets, the
  board's data events), make the same chr, background, app, player, net,
  snd and Interface calls in order (rotations within 0.01 of a degree at
  0, 50 and 100%, within 1% of the limit elsewhere), the same popups and
  the same HUD: open, each category and its first two buildings, each
  slider, positioning over three frames and the world press that settles
  it, preview on and off, accept short of money, accept on a test server
  (/build c), cancel, the close button and Escape;
- fixtures: every model key with its kind, in the main fixture and each
  variant;
- on demand: no board until Open, none while positioning (the per-frame
  calls touch no model), none after Close;
- no per-frame Python: no OnUpdate, OnRender or OnMouseOverIn."""
import ast
import contextlib
import inspect
import io
import json
import os
import sys
import unittest
import weakref

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402

ROOT = support.ROOT
WINDOW_DIR = os.path.normpath(os.path.join(support.support.HERE, "..", "assets", "nui", "nui", "windows", "guild-building"))
DOCUMENT = "nui/windows/guild-building/guild-building.rml"
NOVAUI = "nui_guild_building.BuildGuildBuildingWindow"
# The modules whose calls the differential tests compare (P12 spec 6.0), and
# the Interface's own calls ("interface.*").
EFFECT_MODULES = ("chr", "background", "app", "player", "net", "snd", "interface")
HUD = ("wndTaskBar", "wndCharacter", "wndInventory", "wndMiniMap", "wndGuild", "wndMessenger", "wndChat",
       "wndParty", "wndGameButton", "wndEnergyBar", "wndExpandedTaskBar", "wndDragonSoul", "wndDragonSoulRefine")
FACADE_METHODS = ("Open", "Close", "Destroy", "Destory", "SetCloseEvent", "IsPositioningMode", "IsPreviewMode",
                  "SetBuildingPosition", "SettleCurrentPosition", "Build", "OnPressEscapeKey", "Show", "Hide",
                  "IsShow", "SetTop")
CONSTANTS = ("GUILD_CATEGORY_LIST", "MODE_VIEW", "MODE_POSITIONING", "MODE_PREVIEW", "BUILDING_ALPHA",
             "ENABLE_COLOR", "DISABLE_COLOR", "START_INSTANCE_INDEX")


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class HudWindow(object):
    """A HUD window the Interface hides and shows."""

    def __init__(self, name):
        self.name = name
        self.shown = True

    def Show(self):
        self.shown = True

    def Hide(self):
        self.shown = False

    def IsShow(self):
        return self.shown

    def IsEditMode(self):
        return False


class InterfaceBase(object):
    def __init__(self, log):
        self.log = log
        self.wndGuildBuilding = None
        self.questButtonSuppressed = False
        for name in HUD:
            setattr(self, name, HudWindow(name))

    def HideAllQuestButton(self):
        self.log.append(("interface.HideAllQuestButton", ()))

    def ShowAllQuestButton(self):
        self.log.append(("interface.ShowAllQuestButton", ()))

    def HideAllWhisperButton(self):
        self.log.append(("interface.HideAllWhisperButton", ()))

    def ShowAllWhisperButton(self):
        self.log.append(("interface.ShowAllWhisperButton", ()))

    def hud(self):
        return tuple(name for name in HUD if getattr(self, name).IsShow())


class LegacyMemFunc(object):
    """ui.__mem_func__ as legacy has it (ui.py:58-84): a method that takes
    only self is called with no argument, whatever the caller passes (the
    list boxes pass the row's number and text to __OnSelectCategory)."""

    def __init__(self, method):
        self.obj = weakref.proxy(method.__self__)
        self.func = method.__func__
        self.takes_args = method.__func__.__code__.co_argcount > 1

    def __call__(self, *args):
        if self.takes_args:
            return self.func(self.obj, *args)
        return self.func(self.obj)


def interface_class(namespace):
    """The Interface's guild building methods, compiled from
    interfacemodule.py into a class of the same name."""
    methods = support.source_of("interfacemodule.py", (
        "BUILD_OpenWindow", "BUILD_CloseWindow", "BUILD_OnUpdate", "BUILD_OnMouseLeftButtonDown",
        "BUILD_OnMouseLeftButtonUp", "__HideWindows", "__ShowWindows"), inside="Interface")
    body = "\n".join("\t" + line if line else line for line in methods.split("\n"))
    exec(compile("class Interface(InterfaceBase):\n" + body + "\n", "interfacemodule.py", "exec"), namespace)
    return namespace["Interface"]


class World(object):
    """One world: a Game with the legacy guild building window and the NovaUI
    one over its stand-ins, the flag on when `nui_on`, and the Interface's
    guild building methods."""

    def __init__(self, nui_on, engine=True, windows="+rest", setup=None, limits=None):
        game = self.game = support.Game(engine=engine)
        support.install_wave5a_ui(game)
        game.modules["ui"].__mem_func__ = LegacyMemFunc
        locale = game.modules["localeInfo"]
        locale.NumberToMoneyString = support.support.number_to_money
        locale.THING_COUNT = " pcs"
        game.modules["systemSetting"].GetUINuiWindows = lambda: windows if nui_on else ""
        game.load_standard()
        self.uiGuild = game.modules["uiGuild"]
        if limits is not None:
            for row in self.uiGuild.BUILDING_DATA_LIST:
                row["X_ROT_LIMIT"], row["Y_ROT_LIMIT"], row["Z_ROT_LIMIT"] = limits
        if setup is not None:
            setup(game)
        with quiet():
            self.module = game.load("nui_guild_building", "nui_guild_building.py")
        self.nui_windows = game.loaded["nui_windows"]
        self.nui_on = nui_on
        namespace = {"ui": game.modules["ui"], "uiGuild": self.uiGuild, "nui_windows": self.nui_windows,
                     "app": game.modules["app"], "IsQBHide": False, "InterfaceBase": InterfaceBase}
        self.interface = interface_class(namespace)(game.log)

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def effects_since(self, mark):
        return [(name, args) for name, args in self.game.log[mark:]
                if name.split(".", 1)[0] in EFFECT_MODULES and not support.is_getter(name)]

    def open(self):
        with self.game, quiet():
            self.interface.BUILD_OpenWindow()
        return self.window

    @property
    def window(self):
        return self.interface.wndGuildBuilding

    def board(self):
        window = self.window
        return window.demand.board() if getattr(window, "demand", None) is not None else None

    def frame(self):
        """One frame of game.py's loop (OnUpdate -> Interface.BUILD_OnUpdate)."""
        with self.game:
            self.interface.BUILD_OnUpdate()

    def world_press(self):
        with self.game:
            down = self.interface.BUILD_OnMouseLeftButtonDown()
            up = self.interface.BUILD_OnMouseLeftButtonUp()
        return down, up

    # --- the player's presses, on each side's widgets ----------------------------------

    def pick_category(self, line):
        with self.game, quiet():
            if self.nui_on:
                self.board().fire("pick_category", line, 0)
            else:
                self.window.categoryList.select(line)

    def pick_building(self, line):
        with self.game, quiet():
            if self.nui_on:
                self.board().fire("pick_building", line, 0)
            else:
                self.window.buildingList.select(line)

    def slide(self, axis, percent):
        with self.game, quiet():
            if self.nui_on:
                self.board().fire("rotate", axis, percent)
            else:
                getattr(self.window, "ctrlRotation" + axis.upper()).drag_to(percent / 100.0)

    def press(self, what):
        legacy_names = {"position": "PositionButton", "preview": "PreviewButton", "accept": "AcceptButton",
                        "cancel": "CancelButton"}
        with self.game, quiet():
            if self.nui_on:
                self.board().fire("act", what, 0)
            elif what == "close":
                self.window.board.close()
            else:
                self.window.GetChild(legacy_names[what]).click()

    def escape(self):
        with self.game, quiet():
            if self.nui_on:
                return self.window.escapeProxy._window.OnPressEscapeKey()
            return self.window.OnPressEscapeKey()


def same_calls(test, legacy, novaui, what, rotation_delta=0.01):
    """Equal lists of calls; floats within `rotation_delta`."""
    test.assertEqual([name for name, _ in legacy], [name for name, _ in novaui], what)
    for (name, a), (_, b) in zip(legacy, novaui):
        test.assertEqual(len(a), len(b), "%s %s" % (what, name))
        for x, y in zip(a, b):
            if isinstance(x, float) or isinstance(y, float):
                test.assertAlmostEqual(float(x), float(y), delta=rotation_delta, msg="%s %s %r %r" % (what, name, a, b))
            else:
                test.assertEqual(x, y, "%s %s" % (what, name))


class Pair(unittest.TestCase):
    limits = None

    def setup_state(self, game):
        pass

    def worlds(self, setup=None):
        def both(game):
            self.setup_state(game)
            if setup is not None:
                setup(game)
        legacy, novaui = World(False, setup=both, limits=self.limits), World(True, setup=both, limits=self.limits)
        for world in (legacy, novaui):
            world.__enter__()
            self.addCleanup(world.__exit__)
        return legacy, novaui

    def same(self, legacy, novaui, step, what="", rotation_delta=0.01):
        a, b = len(legacy.game.log), len(novaui.game.log)
        step(legacy)
        step(novaui)
        legacy_calls, novaui_calls = legacy.effects_since(a), novaui.effects_since(b)
        same_calls(self, legacy_calls, novaui_calls, what, rotation_delta)
        return legacy_calls

    def opened(self, setup=None):
        legacy, novaui = self.worlds(setup)
        self.same(legacy, novaui, World.open, "open")
        self.assertIs(type(novaui.window).__name__, "BuildGuildBuildingWindow")
        self.assertTrue(getattr(type(novaui.window), "NUI_FACADE", False))
        self.assertFalse(getattr(type(legacy.window), "NUI_FACADE", False))
        return legacy, novaui


# --- the facade ---------------------------------------------------------------------------------------------

def assert_callable_like(test, legacy_method, novaui_method, name):
    legacy = inspect.signature(legacy_method)
    novaui = inspect.signature(novaui_method)
    positional = [p for p in legacy.parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    required = [p for p in positional if p.default is p.empty]
    for count in range(len(required), len(positional) + 1):
        try:
            novaui.bind(*([None] * count))
        except TypeError as error:
            test.fail("%s: a legacy call with %d arguments does not bind: %s" % (name, count, error))


class Facade(unittest.TestCase):
    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)

    def test_the_facade_keeps_the_legacy_surface_and_signatures(self):
        legacy_class = self.world.uiGuild.BuildGuildBuildingWindow
        facade = self.world.module.BuildGuildBuildingWindow
        self.assertEqual(facade.__name__, legacy_class.__name__)
        self.assertIs(facade.NUI_FACADE, True)
        self.assertEqual(len(inspect.signature(facade.__init__).parameters),
                         len(inspect.signature(legacy_class.__init__).parameters))
        for method in FACADE_METHODS:
            self.assertTrue(callable(getattr(facade, method, None)), method)
            legacy_method = getattr(legacy_class, method, None)
            if legacy_method is not None:
                assert_callable_like(self, getattr(object.__new__(legacy_class), method),
                                     getattr(object.__new__(facade), method), method)
        for method in ("SetCenterPosition", "GetWidth", "GetHeight", "Lock", "Unlock"):
            self.assertTrue(callable(getattr(facade, method, None)), method)
        self.assertIsNone(getattr(facade, "OnUpdate", None))

    def test_the_class_constants_are_legacys(self):
        legacy_class = self.world.uiGuild.BuildGuildBuildingWindow
        facade = self.world.module.BuildGuildBuildingWindow
        for name in CONSTANTS:
            self.assertEqual(getattr(facade, name), getattr(legacy_class, name), name)

    def test_the_facade_answers_the_make_protocol_and_needs_the_engine(self):
        hud = self.world.game.loaded["nui_hud"]
        window = self.world.open()
        self.assertTrue(window.nui_ready())
        self.assertIs(hud.current("guild-building"), window)
        window.nui_discard()
        self.assertFalse(window.nui_ready())
        self.assertIsNone(hud.current("guild-building"))
        old = World(True, engine=False)
        with old:
            self.assertFalse(getattr(type(old.open()), "NUI_FACADE", False), "an older exe keeps the legacy window")

    def test_the_legacy_attributes_callers_read_are_kept(self):
        window = self.world.open()
        for name in ("closeEvent", "popup", "mode", "race", "type", "x", "y", "z", "rot_x", "rot_y", "rot_z",
                     "rot_x_limit", "rot_y_limit", "rot_z_limit", "needMoney", "needStoneCount", "needLogCount",
                     "needPlywoodCount", "indexList", "raceList", "posList", "rotList", "wnds"):
            self.assertTrue(hasattr(window, name), name)


# --- the differential flows ---------------------------------------------------------------------------------------

class Flows(Pair):
    def test_open_makes_legacys_calls_and_hides_the_same_hud(self):
        legacy, novaui = self.opened()
        self.assertEqual(legacy.interface.hud(), novaui.interface.hud())
        self.assertEqual(legacy.interface.hud(), (), "every HUD window hidden")
        self.assertTrue(novaui.window.IsShow())
        board = novaui.board()
        self.assertEqual(board.get("category"), 0)
        self.assertEqual(board.get("building"), 0)
        self.assertEqual([row["label"] for row in board.get("buildings")], legacy.window.buildingList.texts())
        self.assertEqual(board.get("price"), legacy.window.buildingPriceValue.GetText())
        self.assertEqual(board.get("stone"), legacy.window.buildingMaterialStoneValue.GetText())
        self.assertEqual(board.get("pos_x"), legacy.window.posValueX.GetText())

    def test_open_in_debug_mode_picks_the_objects_as_legacy(self):
        def debug(game):
            game.debug_mode = True
        legacy, novaui = self.opened(debug)
        self.assertEqual(novaui.board().get("category"), 2)
        self.assertEqual([row["label"] for row in novaui.board().get("buildings")], legacy.window.buildingList.texts())

    def test_each_category_and_its_first_two_buildings_make_legacys_calls(self):
        legacy, novaui = self.opened()
        for category in (1, 2, 0):
            self.same(legacy, novaui, lambda w: w.pick_category(category), "category %d" % category)
            self.assertEqual([row["label"] for row in novaui.board().get("buildings")],
                             legacy.window.buildingList.texts())
            for line in (1, 0):
                self.same(legacy, novaui, lambda w: w.pick_building(line), "category %d building %d" % (category, line))
                self.assertEqual(novaui.board().get("price"), legacy.window.buildingPriceValue.GetText())
                self.assertEqual(novaui.window.race, legacy.window.race)

    def test_a_press_on_the_selected_row_does_nothing(self):
        legacy, novaui = self.opened()
        self.assertEqual(self.same(legacy, novaui, lambda w: w.pick_category(0), "the category in effect"), [])
        self.assertEqual(self.same(legacy, novaui, lambda w: w.pick_building(0), "the building in effect"), [])

    def test_the_hidden_rows_keep_legacys_indexes(self):
        legacy, novaui = self.opened()
        self.same(legacy, novaui, lambda w: w.pick_category(2), "objects")
        # The first shown object follows twelve hidden walls and gates.
        self.assertEqual(novaui.window.buildingRows[0][0], legacy.window.buildingList.keyDict[0])
        self.assertGreater(novaui.window.buildingRows[0][0], 0)
        self.assertEqual(novaui.window.race, legacy.window.race)

    def test_the_cost_colors_follow_the_money_and_the_materials(self):
        def poor(game):
            game.money = 1000
            game.material_counts = {90010: 100, 90011: 1, 90012: 100}
        legacy, novaui = self.opened(poor)
        board = novaui.board()
        self.assertTrue(board.get("price_short"))
        self.assertFalse(board.get("stone_short"))
        self.assertTrue(board.get("log_short"))
        self.assertFalse(board.get("plywood_short"))
        self.assertEqual(legacy.window.buildingPriceValue.calls[-1][1], legacy.window.DISABLE_COLOR)

    def test_position_follows_the_picking_point_and_a_world_press_settles_it(self):
        legacy, novaui = self.opened()
        self.same(legacy, novaui, lambda w: w.press("position"), "position")
        self.assertTrue(novaui.window.IsPositioningMode())
        self.assertIsNone(novaui.board(), "the window hides to position")
        self.assertFalse(legacy.window.IsShow())
        for point in ((12100.0, 34100.0, 120.0), (12200.0, 34050.0, 130.0), (12300.0, 34000.0, 140.0)):
            def frame(world):
                world.game.picking_point = point
                world.frame()
            self.same(legacy, novaui, frame, "a frame at %r" % (point,))
        self.assertEqual((novaui.window.x, novaui.window.y), (12300.0, 34000.0))
        calls = self.same(legacy, novaui, World.world_press, "the press that settles")
        self.assertIn(("app.SetCameraSetting", (12300, -34000, 140, 3000, 0, 30)), calls)
        self.assertFalse(novaui.window.IsPositioningMode())
        board = novaui.board()
        self.assertIsNotNone(board, "shown again")
        self.assertEqual((board.get("pos_x"), board.get("pos_y")), ("12300", "34000"))
        self.assertEqual((legacy.window.posValueX.GetText(), legacy.window.posValueY.GetText()), ("12300", "34000"))

    def test_preview_on_and_off_make_legacys_camera_and_blocker_calls(self):
        legacy, novaui = self.opened()
        on = self.same(legacy, novaui, lambda w: w.press("preview"), "preview on")
        self.assertIn(("app.SetDefaultCamera", ()), on)
        self.assertTrue(novaui.window.IsPreviewMode())
        self.assertTrue(novaui.board().get("preview"))
        self.assertEqual(self.same(legacy, novaui, lambda w: w.press("position"), "position in preview"), [],
                         "Change does nothing in preview, as legacy's radio button pops up again")
        self.assertTrue(novaui.window.IsPreviewMode())
        self.assertEqual(self.same(legacy, novaui, World.world_press, "a world press in preview"), [])
        off = self.same(legacy, novaui, lambda w: w.press("preview"), "preview off")
        self.assertIn(("chr.SetInstanceType", (10,)), off)
        self.assertFalse(novaui.window.IsPreviewMode())
        self.assertFalse(novaui.board().get("preview"))

    def test_accept_short_of_money_shows_the_popup_and_sends_nothing(self):
        legacy, novaui = self.opened()
        calls = self.same(legacy, novaui, lambda w: w.press("accept"), "accept short")
        self.assertFalse([call for call in calls if call[0] == "net.SendChatPacket"])
        self.assertEqual(legacy.game.popups, novaui.game.popups)
        self.assertEqual(len(novaui.game.popups), 1)
        self.assertTrue(novaui.window.IsShow(), "the window stays")

    def test_accept_on_a_test_server_sends_legacys_build_command_and_closes(self):
        def test_server(game):
            game.test_server = True
        legacy, novaui = self.opened(test_server)
        calls = self.same(legacy, novaui, lambda w: w.press("accept"), "accept")
        sent = [call for call in calls if call[0] == "net.SendChatPacket"]
        self.assertEqual(len(sent), 1)
        self.assertTrue(sent[0][1][0].startswith("/build c 14100 12000 34000 "), sent)
        self.assertIn(("interface.ShowAllWhisperButton", ()), calls, "the close event shows the HUD again")
        self.assertIsNone(novaui.interface.wndGuildBuilding, "the Interface drops the window")
        self.assertEqual(legacy.interface.hud(), novaui.interface.hud())

    def test_cancel_the_close_button_and_escape_close_as_legacy(self):
        for how in ("cancel", "close", "escape"):
            with self.subTest(how=how):
                legacy, novaui = self.opened()
                window = novaui.window
                step = (lambda w: w.escape()) if how == "escape" else (lambda w: w.press(how))
                calls = self.same(legacy, novaui, step, how)
                self.assertIn(("background.DisableGuildArea", ()), calls)
                self.assertIn(("app.SetDefaultCamera", ()), calls)
                self.assertIsNone(window.demand.board(), "the board goes")
                self.assertFalse(window.escapeProxy.is_shown())
                self.assertEqual(legacy.interface.hud(), novaui.interface.hud())
                self.assertEqual(len(novaui.interface.hud()), len(HUD), "every HUD window back")


class Sliders(Pair):
    limits = (30, 40, 360)

    def test_each_slider_at_0_50_and_100_rotates_as_legacy(self):
        legacy, novaui = self.opened()
        for axis in ("x", "y", "z"):
            for percent in (0, 50, 100):
                calls = self.same(legacy, novaui, lambda w: w.slide(axis, percent), "%s at %d" % (axis, percent))
                self.assertEqual([name for name, _ in calls], ["chr.SetRotationAll"])
        self.assertAlmostEqual(novaui.window.rot_x, 15.0)
        self.assertAlmostEqual(novaui.window.rot_y, 20.0)
        self.assertAlmostEqual(novaui.window.rot_z, 180.0)

    def test_between_the_stops_a_rotation_is_within_one_percent_of_the_limit(self):
        legacy, novaui = self.opened()
        for axis, percent, delta in (("x", 90, 0.3), ("y", 10, 0.4), ("z", 25, 3.6)):
            self.same(legacy, novaui, lambda w: w.slide(axis, percent), "%s at %d" % (axis, percent), delta)

    def test_the_models_own_value_coming_back_is_not_a_move(self):
        legacy, novaui = self.opened()
        mark = len(novaui.game.log)
        with novaui.game:
            novaui.board().fire("rotate", "x", 50)
            novaui.board().fire("rotate", "z", 50.2)
        self.assertEqual(novaui.effects_since(mark), [])

    def test_a_new_building_puts_the_sliders_back_to_the_middle(self):
        legacy, novaui = self.opened()
        self.same(legacy, novaui, lambda w: w.slide("x", 100), "x")
        self.same(legacy, novaui, lambda w: w.pick_building(1), "building")
        self.assertEqual(novaui.board().get("rot_x"), 50)
        self.assertEqual(legacy.window.ctrlRotationX.GetSliderPos(), 0.5)
        self.assertAlmostEqual(novaui.window.rot_x, legacy.window.rot_x, "the rotation stays until a slider moves")


class StillSliders(Pair):
    def test_a_building_whose_limit_is_0_keeps_its_slider_still(self):
        legacy, novaui = self.opened()
        board = novaui.board()
        self.assertEqual((board.get("rot_x_on"), board.get("rot_y_on"), board.get("rot_z_on")), (False, False, True))
        mark = len(novaui.game.log)
        with novaui.game:
            board.fire("rotate", "x", 90)
        self.assertEqual(novaui.effects_since(mark), [], "legacy hides the cursor (SliderBar.Disable)")


# --- the per-frame calls and on demand ---------------------------------------------------------------------------

class PerFrame(unittest.TestCase):
    def test_the_per_frame_calls_touch_no_model_while_positioning(self):
        world = World(True)
        with world:
            window = world.open()
            world.press("position")
            states = [w for w in world.game.state.windows if w.DOCUMENT == DOCUMENT]
            calls = sum(len(w.calls) for w in states)
            for _ in range(5):
                world.frame()
            self.assertEqual(sum(len(w.calls) for w in states), calls, "no board call per frame")
            self.assertIsNone(window.demand.board())

    def test_in_view_mode_a_frame_asks_only_for_the_mode(self):
        world = World(True)
        with world:
            world.open()
            mark = len(world.game.log)
            for _ in range(3):
                world.frame()
            self.assertEqual(world.effects_since(mark), [])

    def test_the_module_defines_no_per_frame_method(self):
        tree = ast.parse(read(os.path.join(ROOT, "nui_guild_building.py")))
        names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        self.assertFalse(names & {"OnUpdate", "OnRender", "OnMouseOverIn"})

    def test_the_document_binds_no_per_frame_python(self):
        source = read(os.path.join(WINDOW_DIR, "guild-building.rml"))
        self.assertNotIn("data-rml", source)


class OnDemand(unittest.TestCase):
    def test_the_board_exists_only_while_the_window_shows(self):
        world = World(True)
        with world, quiet():
            window = world.nui_windows.make("guild-building", world.uiGuild.BuildGuildBuildingWindow, NOVAUI)
            boards = [w for w in world.game.state.windows if w.DOCUMENT == DOCUMENT]
            self.assertEqual(len(boards), 1, "the probe made one")
            self.assertFalse(boards[0]._doc, "and destroyed it")
            self.assertIsNone(window.demand.board())
            window.Open()
            self.assertIsNotNone(window.demand.board())
            self.assertTrue(window.escapeProxy.is_shown())
            window.Close()
            self.assertIsNone(window.demand.board())
            self.assertEqual([w for w in world.game.state.windows if w.DOCUMENT == DOCUMENT and w._doc], [])

    def test_destroy_keeps_legacys_inherited_destroy(self):
        world = World(True)
        with world, quiet():
            window = world.open()
            mark = len(world.game.log)
            window.Destroy()
            self.assertEqual(world.effects_since(mark), [], "no Close: legacy's Destory is never called")
            self.assertIsNone(window.demand)

    def test_a_dragged_window_keeps_its_place_across_positioning(self):
        world = World(True)
        with world, quiet():
            window = world.open()
            board = window.demand.board()
            world.game.state.boxes[(DOCUMENT, "")] = (300.0, 200.0, 580.0, 300.0)
            world.press("position")
            world.game.state.boxes.clear()
            world.world_press()
            self.assertEqual(window.demand.board().placement, ("position", 300.0, 200.0, (0.0, 0.0)))
            self.assertIsNot(window.demand.board(), board)


# --- fixtures ---------------------------------------------------------------------------------------------------

def kind(value):
    return {bool: "bool", int: "int", float: "float", str: "str", list: "list", dict: "map"}[type(value)]


class Fixtures(unittest.TestCase):
    def test_every_fixture_holds_every_model_key_with_its_kind(self):
        world = World(True)
        with world, quiet():
            window = world.open()
            model = window.nui_model()
        self.assertEqual(set(model), set(world.module.BuildGuildBuildingWindow.empty_model()))
        names = [name for name in os.listdir(WINDOW_DIR) if name.endswith(".fixture.json")]
        self.assertEqual(sorted(names), ["guild-building.fixture.json", "guild-building.preview.fixture.json",
                                         "guild-building.short.fixture.json"])
        for name in names:
            with self.subTest(fixture=name):
                fixture = json.loads(read(os.path.join(WINDOW_DIR, name)))["guild_building"]
                self.assertEqual(set(fixture), set(model))
                for key, value in model.items():
                    self.assertEqual(kind(fixture[key]), kind(value), key)
                for row in fixture["categories"] + fixture["buildings"]:
                    self.assertEqual(set(row), {"label"})

    def test_the_open_model_matches_legacys_widgets(self):
        world = World(True)
        with world, quiet():
            window = world.open()
            model = window.nui_model()
        self.assertEqual(model["categories"], [{"label": "GUILD_HEADQUARTER"}, {"label": "GUILD_FACILITY"},
                                               {"label": "GUILD_OBJECT"}])
        self.assertEqual(model["rot_x"], 50)
        self.assertFalse(model["positioning"])


if __name__ == "__main__":
    unittest.main()
