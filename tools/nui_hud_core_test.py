"""Tests for the NovaUI HUD windows of CORE CONTENT: the taskbar
(assets/root/nui_taskbar.py), the expanded taskbar, the energy bar, the gift
box, the game buttons, the shared facade helpers (nui_hud.py) and the
factory wiring of interfacemodule.py, game.py and uiwhisper.py:
python3 -B -m unittest nui_hud_core_test (from tools/).

Plain CPython over nui_game_support's stand-ins. For every window:
- facade: every method the Interface, game.py and the C++ callbacks call on
  the legacy class exists on the NovaUI class with a signature the legacy
  callers can use, and the class constants the Interface reads have the
  legacy values;
- differential: the legacy class (uitaskbar.py, uigamebutton.py) and the
  NovaUI class, each in a world of its own with the same stand-in state and
  driven through the same flows (the legacy widgets' events against the
  board's data events), make the same player, net, app and mouse
  controller calls, in order, getters left out (nui_game_support.effects);
  the quickslot feed C++ builds is stood in for by nui_slots' builders over
  the same state;
- fixture: the board, made with a stand-in owner and set from its fixture,
  has every key of the fixture in its model with the same kind, and logs
  nothing;
- no per-frame Python: the module defines no OnUpdate, OnRender or
  OnMouseOverIn."""
import ast
import contextlib
import inspect
import io
import json
import os
import re
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402

ROOT = support.ROOT
WINDOWS = os.path.normpath(os.path.join(support.support.HERE, "..", "assets", "nui", "nui", "windows"))
CLASSIC_WINDOWS = os.path.normpath(os.path.join(support.support.HERE, "..", "assets", "nui", "nui", "skins", "classic", "windows"))
P = support.PLAYER_CONSTANTS
INVENTORY, SKILL, EMOTION, QUICK = P["SLOT_TYPE_INVENTORY"], P["SLOT_TYPE_SKILL"], P["SLOT_TYPE_EMOTION"], P["SLOT_TYPE_QUICK_SLOT"]
CORE_MODULES = ("nui_taskbar", "nui_expanded_taskbar", "nui_energy_bar", "nui_gift_box", "nui_game_buttons", "nui_hud", "nui_slots")

TASKBAR_METHODS = ("LoadWindow", "SetToggleButtonEvent", "SetItemToolTip", "SetSkillToolTip", "Show", "Hide", "IsShow",
                   "SetTop", "Destroy", "RefreshStatus", "RefreshStamina", "RefreshQuickSlot", "RefreshSkill", "OnUseSkill",
                   "OnActivateSkill", "OnDeactivateSkill", "SkillClearCoolTime", "OnChangeCurrentSkill",
                   "SelectMouseButtonEvent", "ShowMouseImage", "HideMouseImage", "ShowGift", "HideGift",
                   "AddQuickSlot", "OverInItem", "OverOutItem", "OpenSelectSkill", "CloseSelectSkill",
                   "ToggleLeftMouseButtonModeWindow", "ToggleRightMouseButtonModeWindow", "canAddQuickSlot")
TASKBAR_CONSTANTS = ("BUTTON_CHARACTER", "BUTTON_INVENTORY", "BUTTON_MESSENGER", "BUTTON_SYSTEM", "BUTTON_CHAT",
                     "BUTTON_EXPAND", "MOUSE_BUTTON_LEFT", "MOUSE_BUTTON_RIGHT", "NONE", "EVENT_MOVE", "EVENT_ATTACK",
                     "EVENT_MOVE_AND_ATTACK", "EVENT_CAMERA", "EVENT_SKILL", "EVENT_AUTO", "GAUGE_WIDTH", "GAUGE_HEIGHT",
                     "QUICKPAGE_NUMBER_FILENAME")
EXPANDED_METHODS = ("LoadWindow", "SetToggleButtonEvent", "SetToolTipText", "Show", "Hide", "IsShow", "SetTop", "Close", "Destroy")
ENERGY_METHODS = ("LoadWindow", "RefreshStatus", "SetEnergy", "Show", "Hide", "IsShow", "Destroy")
GIFT_METHODS = ("LoadWindow", "Show", "Hide", "IsShow", "Destroy")
GAME_BUTTON_METHODS = ("SetTop", "Show", "SetButtonEvent", "CheckGameButton", "ShowBuildButton", "HideBuildButton",
                       "SetObserverMode", "Hide", "IsShow", "Destroy")
GAME_BUTTONS = ("STATUS", "SKILL", "QUEST", "HELP", "BUILD", "EXIT_OBSERVER")
GAME_BUTTON_CHILDREN = {"STATUS": "StatusPlusButton", "SKILL": "SkillPlusButton", "QUEST": "QuestButton",
                        "HELP": "HelpButton", "BUILD": "BuildGuildBuilding", "EXIT_OBSERVER": "ExitObserver"}
MODE_ART = {"button_move_and_attack": "attack", "button_auto_attack": "auto", "button_camera": "camera", "button_skill": "skill"}


def quiet():
    """The legacy taskbar prints on its gauge hovers."""
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def quick_feed(game):
    """The quickslot feed as C++ BuildQuickSlots makes it, from nui_slots'
    builders over the same state."""
    slots = game.loaded["nui_slots"]
    cells = []
    for local in range(8):
        slot_type, position = game.quick.get(game.page * 8 + local, (0, 0))
        if slot_type == INVENTORY:
            cells.append(slots.item_slot(local, position))
        elif slot_type == SKILL:
            cells.append(slots.skill_slot(local, position))
        elif slot_type == EMOTION:
            cells.append(slots.emotion_slot(local, position))
        else:
            cells.append(slots.empty_slot(local))
    return cells


class World(object):
    """One world: a Game, the legacy taskbar module and either the legacy or
    the NovaUI window under test."""

    def __init__(self, nui_on, windows="+hud", engine=True, setup=None):
        self.game = support.Game(engine=engine)
        self.game.modules["systemSetting"].GetUINuiWindows = lambda: windows if nui_on else ""
        if setup is not None:
            setup(self.game)
        self.game.load_standard()
        with quiet():
            self.uiTaskBar = self.game.load("uiTaskBar", "uitaskbar.py")
            self.uiGameButton = self.game.load("uiGameButton", "uigamebutton.py")
            for name in ("nui_gift_box", "nui_energy_bar", "nui_expanded_taskbar", "nui_game_buttons", "nui_taskbar"):
                self.game.load(name, name + ".py")
        self.nui_windows = self.game.loaded["nui_windows"]
        self.nui_on = nui_on

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def module(self, name):
        return self.game.loaded[name]

    def publish_quick(self):
        self.game.state.publish("quickslot.slots", quick_feed(self.game))
        self.game.state.publish("quickslot.page", self.game.page)


# --- nui_hud --------------------------------------------------------------------------

class HudHelpers(unittest.TestCase):
    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)
        self.hud = self.world.module("nui_hud")

    def test_has_engine_needs_the_nuigame_module_and_bind_feed(self):
        self.assertTrue(self.hud.has_engine())
        world = World(True, engine=False)
        with world:
            self.assertFalse(world.module("nui_hud").has_engine(), "no nuigame, no BindFeed")
            world.game.put("nuigame", support.Recording("nuigame", world.game.log))
            self.assertFalse(world.module("nui_hud").has_engine(), "nuigame alone is not enough")

    def test_take_over_discards_the_previous_facades_parts_and_forget_drops_only_its_own(self):
        discarded = []

        class Facade(object):
            def nui_discard(self):
                discarded.append(self)

        first, second = Facade(), Facade()
        self.hud.take_over("x", first)
        self.hud.take_over("x", first)
        self.assertEqual(discarded, [], "the same facade again is not discarded")
        self.hud.take_over("x", second)
        self.assertEqual(discarded, [first])
        self.assertIs(self.hud.current("x"), second)
        self.hud.forget("x", first)
        self.assertIs(self.hud.current("x"), second, "a stale facade does not drop the new one")
        self.hud.forget("x", second)
        self.assertIsNone(self.hud.current("x"))

    def test_moved_place_takes_the_runtime_s_centered_place_as_not_moved(self):
        """P18 review: the runtime's Center placement puts a board wider or
        taller than the screen at 0 on that axis, so such a board left where
        Center put it is not a drag (the guild window, 470dp tall, at 200% on
        1600 x 900)."""
        nui = self.world.game.modules["nui"]
        wnd = self.world.game.modules["wndMgr"]
        wnd.GetScreenWidth = lambda: 1600
        wnd.GetScreenHeight = lambda: 900

        class Board(object):
            def __init__(self, box):
                self.box = box

            def element_box(self, element_id):
                return self.box

        place = self.hud.moved_place
        nui.set_scale_percent(100)
        self.assertIsNone(place(Board((560.0, 215.0, 480.0, 470.0))), "centered")
        self.assertIsNone(place(Board((561.5, 213.0, 480.0, 470.0))), "within 2 px of it")
        self.assertEqual(place(Board((300.0, 120.0, 480.0, 470.0))), (300.0, 120.0), "dragged: its place in dp")
        self.assertIsNone(place(Board(None)), "no box: nothing kept")
        nui.set_scale_percent(200)
        self.assertIsNone(place(Board((320.0, 0.0, 960.0, 940.0))), "taller than the screen: Center's y is 0")
        self.assertIsNone(place(Board((0.0, 0.0, 1700.0, 940.0))), "wider and taller: Center's place is 0, 0")
        self.assertEqual(place(Board((320.0, 40.0, 960.0, 940.0))), (160.0, 20.0), "moved down from it: in dp")
        self.assertEqual(place(Board((100.0, 0.0, 960.0, 940.0))), (50.0, 0.0), "moved left from it")

    def test_an_escape_proxy_is_a_zero_size_ui_window_that_runs_its_action_and_keeps_escape(self):
        ran = []

        class Owner(object):
            def Close(self):
                ran.append("close")

        owner = Owner()
        proxy = self.hud.EscapeProxy(owner.Close)
        window = proxy._window
        self.assertEqual(window.layer, "UI")
        self.assertEqual(window.size, (0, 0), "never picked")
        self.assertFalse(proxy.is_shown())
        proxy.show()
        self.assertTrue(proxy.is_shown())
        self.assertIn(("SetTop",), window.calls, "it takes the window's place in the Escape chain")
        self.assertIs(window.OnPressEscapeKey(), True)
        self.assertEqual(ran, ["close"])
        proxy.hide()
        self.assertFalse(proxy.is_shown())
        proxy.destroy()
        self.assertIsNone(proxy._window)
        proxy.show()
        proxy.destroy()

    def test_has_engine_3a_needs_the_wave2b_engine_and_nui_stats(self):
        self.assertTrue(self.hud.has_engine_3a())
        nuigame = self.world.game.modules["nuigame"]
        nuigame.lack("NuiStats")
        self.assertFalse(self.hud.has_engine_3a(), "a Wave 2b exe")
        self.assertTrue(self.hud.has_engine_2b())
        world = support.Game(engine_3a=False)
        self.assertRaises(AttributeError, getattr, world.modules["nuigame"], "NuiStats")
        world = World(True)
        with world:
            nuigame = world.game.modules["nuigame"]
            nuigame.lack("ChatAttach")
            self.assertFalse(world.module("nui_hud").has_engine_3a(), "NuiStats without the Wave 2b engine is not enough")

    def test_has_engine_5a_needs_the_three_functions_and_the_3a_engine(self):
        self.assertTrue(self.hud.has_engine_5a(), "the recording nuigame answers every name")
        for name in ("QuestAttach", "QuestState", "WebPageFollow"):
            world = World(True)
            with world:
                world.game.modules["nuigame"].lack(name)
                self.assertFalse(world.module("nui_hud").has_engine_5a(), "a Wave 3a exe: no %s" % name)
                self.assertTrue(world.module("nui_hud").has_engine_3a())
        world = World(True)
        with world:
            world.game.modules["nuigame"].lack("NuiStats")
            self.assertFalse(world.module("nui_hud").has_engine_5a(), "the quest functions without the 3a engine")
        world = World(True, engine=False)
        with world:
            self.assertFalse(world.module("nui_hud").has_engine_5a(), "no nuigame at all")

    def test_has_engine_3b_needs_follow_pointer_and_the_cells_decorator(self):
        self.assertTrue(self.hud.has_engine_3b())
        world = World(True)
        with world:
            del world.game.modules["nui"]._nui.FollowPointer
            self.assertFalse(world.module("nui_hud").has_engine_3b(), "an exe without pointer placement")
        world = World(True)
        with world:
            world.game.state.decorators.discard("nui-cells")
            self.assertFalse(world.module("nui_hud").has_engine_3b(), "no nui-cells decorator")
        world = World(True)
        with world:
            del world.game.modules["nui"].has_decorator
            self.assertFalse(world.module("nui_hud").has_engine_3b(), "a nui.py without has_decorator")
        self.assertFalse(support.Game(engine_3b=False).engine_3b)
        world = World(True, engine=False)
        with world:
            self.assertFalse(world.module("nui_hud").has_engine_3b(), "no nuigame at all")

    def on_demand(self, document="nui/windows/test/test.rml"):
        nui = self.world.game.modules["nui"]
        log = []

        class Board(nui.Window):
            DOCUMENT = document
            MODEL = "test"

            def initial_model(self):
                return {"value": 0}

        class Facade(object):
            def __init__(self):
                self.value = 7
                self.place = None
                self.boards = []
                self.demand = hud.OnDemand(self.make, self.restore, self.keep)

            def make(self):
                board = Board()
                self.boards.append(board)
                log.append("make")
                return board

            def restore(self, board):
                log.append("restore")
                board.set(value=self.value)
                if self.place is not None:
                    board.set_position(*self.place)

            def keep(self, board):
                log.append("keep")
                self.value = board.get("value")
                box = board.element_box("")
                if box is not None:
                    self.place = (box[0], box[1])

        hud = self.hud
        return Facade(), log

    def test_on_demand_makes_the_board_at_show_and_destroys_it_at_hide(self):
        facade, log = self.on_demand()
        demand = facade.demand
        self.assertIsNone(demand.board())
        self.assertFalse(demand.is_shown())
        demand.hide()
        self.assertEqual(log, [], "a hide with no board does nothing")
        self.assertTrue(demand.show())
        board = demand.board()
        self.assertIs(board, facade.boards[0])
        self.assertTrue(board.is_visible())
        self.assertTrue(demand.is_shown())
        self.assertEqual(log, ["make", "restore"])
        self.assertTrue(demand.show(), "a second show keeps the same board")
        self.assertIs(demand.board(), board)
        self.assertEqual(log, ["make", "restore"])
        demand.hide()
        self.assertIsNone(demand.board())
        self.assertEqual(board.calls[-1], ("destroy",))
        self.assertFalse(board._doc, "the document went with the hide")
        self.assertEqual(log, ["make", "restore", "keep"])
        demand.show()
        self.assertIsNot(demand.board(), board, "a new board at the next show")
        demand.destroy()
        self.assertIsNone(demand.board())
        self.assertFalse(demand.show(), "forgotten callbacks make nothing")

    def test_on_demand_keeps_and_restores_state_across_a_hide(self):
        facade, log = self.on_demand()
        state = self.world.game.state
        facade.demand.show()
        first = facade.demand.board()
        self.assertEqual(first.model["value"], 7, "restore set the model from the facade")
        first.model["value"] = 9   # the document changed it (a drag, a resize)
        state.boxes[(first.DOCUMENT, "")] = (120, 80, 300, 200)
        facade.demand.hide()
        self.assertEqual((facade.value, facade.place), (9, (120, 80)), "keep read it back before the destroy")
        facade.demand.show()
        second = facade.demand.board()
        self.assertEqual(second.model["value"], 9)
        self.assertEqual(second.placement, ("position", 120, 80, (0.0, 0.0)))

    def test_on_demand_probe_answers_whether_the_document_loads_and_leaves_nothing(self):
        facade, log = self.on_demand()
        state = self.world.game.state
        self.assertTrue(facade.demand.probe())
        self.assertEqual(log, ["make"], "the probe neither restores nor keeps")
        self.assertFalse(facade.boards[0]._doc, "the probe destroyed its board")
        self.assertIsNone(facade.demand.board())
        self.assertFalse(any(window._doc for window in facade.boards))
        state.failing.add(facade.boards[0].DOCUMENT)
        self.assertFalse(facade.demand.probe(), "a document that does not load")
        self.assertFalse(facade.demand.show(), "nor does it show")
        self.assertIsNone(facade.demand.board())
        state.failing.clear()
        facade.demand.show()
        self.assertTrue(facade.demand.probe(), "a shown board answers for itself")
        self.assertTrue(facade.demand.is_shown(), "and stays")

    def test_on_demand_holds_its_callbacks_weakly(self):
        facade, log = self.on_demand()
        demand = facade.demand
        del facade
        import gc
        gc.collect()
        self.assertFalse(demand.show(), "a facade that went makes nothing")
        self.assertEqual(log, [])

    def escape_chain(self, *windows):
        """The windows' OnPressEscapeKey in the order wndMgr walks them: the
        TOP_MOST layer before the UI layer, each layer's children last
        first (CWindow::RunPressEscapeKeyEvent); the first True stops it."""
        order = {"TOP_MOST": 0, "UI": 1}
        ranked = sorted(enumerate(windows), key=lambda pair: (order[pair[1].layer], -pair[0]))
        for _, window in ranked:
            if window.IsShow() and window.OnPressEscapeKey():
                return window
        return None

    def test_an_escape_proxy_in_top_most_comes_first(self):
        ran = []
        ui_proxy = self.hud.EscapeProxy(lambda: ran.append("ui"))
        top_proxy = self.hud.EscapeProxy(lambda: ran.append("top"), layer="TOP_MOST")
        later_ui = self.hud.EscapeProxy(lambda: ran.append("later ui"))
        self.assertEqual(ui_proxy._window.layer, "UI", "the default is today's layer")
        self.assertEqual(top_proxy._window.layer, "TOP_MOST")
        self.assertEqual(top_proxy._window.size, (0, 0))
        for proxy in (ui_proxy, top_proxy, later_ui):
            proxy.show()
        windows = (ui_proxy._window, top_proxy._window, later_ui._window)
        self.assertIs(self.escape_chain(*windows), top_proxy._window)
        self.assertEqual(ran, ["top"], "before every UI-layer window, the later one too")
        top_proxy.hide()
        self.assertIs(self.escape_chain(*windows), later_ui._window)
        none = self.hud.EscapeProxy(None)
        none.show()
        self.assertIs(none._window.OnPressEscapeKey(), True, "no action: the key is kept and nothing runs")
        self.assertEqual(ran, ["top", "later ui"])
        for proxy in (ui_proxy, top_proxy, later_ui, none):
            proxy.destroy()

    def test_an_exit_action_closes_and_answers_true(self):
        ran = []

        class Owner(object):
            def Close(self):
                ran.append("close")

        owner = Owner()
        plain = self.hud.EscapeProxy(owner.Close)
        self.assertIs(plain._window.OnPressExitKey(), False, "without an exit action the exit key goes on")
        self.assertEqual(ran, [])
        proxy = self.hud.EscapeProxy(owner.Close, exit_action=owner.Close)
        proxy.show()
        self.assertIs(proxy._window.OnPressExitKey(), True)
        self.assertEqual(ran, ["close"])
        kept = self.hud.EscapeProxy(None, exit_action=lambda: None)
        self.assertIs(kept._window.OnPressExitKey(), True, "an exit action that does nothing still keeps the key")
        self.assertEqual(ran, ["close"])
        proxy.destroy()
        self.assertIsNone(proxy._window)
        plain.destroy()
        kept.destroy()

    def test_locale_text_calls_typed_entries_and_makes_the_text_plain(self):
        locale = self.world.game.modules["localeInfo"]
        locale.PLAIN_KEY = "Hello @ui.X"
        locale.SA_KEY = lambda value: "Got %s" % (value,)
        locale.SNA_KEY = lambda value: "Always"
        locale.BROKEN_KEY = lambda value: "%d" % value
        text = self.hud.locale_text
        self.assertEqual(text("PLAIN_KEY"), "Hello @⁠ui.X")
        self.assertEqual(text("SA_KEY", 7), "Got 7")
        self.assertEqual(text("SNA_KEY"), "Always", "an SNA entry is called with 0")
        self.assertEqual(text("BROKEN_KEY", "x"), "", "an entry that does not format")
        self.assertEqual(text("TASKBAR_HP"), "TASKBAR_HP", "the stand-in answers its name")
        locale.__dict__["MISSING"] = None
        self.assertEqual(text("MISSING"), "")


# --- facades --------------------------------------------------------------------------

def assert_callable_like(test, legacy_method, novaui_method, name):
    """Every call shape the legacy signature takes binds to the NovaUI one."""
    legacy = inspect.signature(legacy_method)
    novaui = inspect.signature(novaui_method)
    positional = [p for p in legacy.parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    required = [p for p in positional if p.default is p.empty]
    for count in range(len(required), len(positional) + 1):
        args = [None] * count
        try:
            novaui.bind(*args)
        except TypeError as error:
            test.fail("%s: a legacy call with %d arguments does not bind: %s" % (name, count, error))


class Facades(unittest.TestCase):
    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)

    def check(self, legacy_class, novaui_class, methods, constants=()):
        for name in methods:
            self.assertTrue(hasattr(novaui_class, name), "%s.%s" % (novaui_class.__name__, name))
            legacy_method = getattr(legacy_class, name, None)
            if legacy_method is None:
                continue
            bound_legacy = getattr(object.__new__(legacy_class), name)
            bound_novaui = getattr(object.__new__(novaui_class), name)
            assert_callable_like(self, bound_legacy, bound_novaui, "%s.%s" % (novaui_class.__name__, name))
        for name in constants:
            self.assertEqual(getattr(novaui_class, name), getattr(legacy_class, name), name)
        self.assertIs(novaui_class.NUI_FACADE, True)
        self.assertEqual(novaui_class.__name__, legacy_class.__name__)
        self.assertEqual(len(inspect.signature(novaui_class.__init__).parameters),
                         len(inspect.signature(legacy_class.__init__).parameters), "the legacy constructor arguments")

    def test_the_taskbar_facade_keeps_the_legacy_surface(self):
        self.check(self.world.uiTaskBar.TaskBar, self.world.module("nui_taskbar").TaskBar, TASKBAR_METHODS, TASKBAR_CONSTANTS)

    def test_the_expanded_taskbar_facade_keeps_the_legacy_surface(self):
        self.check(self.world.uiTaskBar.ExpandedTaskBar, self.world.module("nui_expanded_taskbar").ExpandedTaskBar,
                   EXPANDED_METHODS, ("BUTTON_DRAGON_SOUL",))

    def test_the_energy_bar_facade_keeps_the_legacy_surface(self):
        self.check(self.world.uiTaskBar.EnergyBar, self.world.module("nui_energy_bar").EnergyBar, ENERGY_METHODS)

    def test_the_gift_box_facade_keeps_the_legacy_surface(self):
        self.check(self.world.uiTaskBar.GiftBox, self.world.module("nui_gift_box").GiftBox, GIFT_METHODS)

    def test_the_game_buttons_facade_keeps_the_legacy_surface(self):
        self.check(self.world.uiGameButton.GameButtonWindow, self.world.module("nui_game_buttons").GameButtonWindow,
                   GAME_BUTTON_METHODS)

    def test_every_facade_answers_the_make_protocol_and_needs_the_engine(self):
        for module, name in (("nui_taskbar", "TaskBar"), ("nui_expanded_taskbar", "ExpandedTaskBar"),
                             ("nui_energy_bar", "EnergyBar"), ("nui_gift_box", "GiftBox"),
                             ("nui_game_buttons", "GameButtonWindow")):
            facade = getattr(self.world.module(module), name)()
            self.assertTrue(facade.nui_ready(), name)
            key = {"TaskBar": "taskbar", "ExpandedTaskBar": "expanded-taskbar", "EnergyBar": "energy-bar",
                   "GiftBox": "gift-box", "GameButtonWindow": "game-buttons"}[name]
            self.assertIs(self.world.module("nui_hud").current(key), facade)
            facade.nui_discard()
            self.assertFalse(facade.nui_ready(), name)
            self.assertIsNone(self.world.module("nui_hud").current(key), "a discarded facade drops its record")
        world = World(True, engine=False)
        with world:
            for module, name in (("nui_taskbar", "TaskBar"), ("nui_game_buttons", "GameButtonWindow")):
                self.assertFalse(getattr(world.module(module), name)().nui_ready(), "%s without the engine" % name)
            made = world.nui_windows.make("taskbar", world.uiTaskBar.TaskBar, "nui_taskbar.TaskBar")
            self.assertIsInstance(made, world.uiTaskBar.TaskBar, "an older exe keeps the legacy taskbar")
            self.assertIn("nui_windows: taskbar: the document did not load; using the legacy window", world.game.dbg.errors)

    def test_a_new_facade_destroys_a_previous_one_that_is_still_alive(self):
        taskbar = self.world.module("nui_taskbar")
        first = taskbar.TaskBar()
        board = first.board
        second = taskbar.TaskBar()
        self.assertEqual(board.calls[-1], ("destroy",), "the phase that ended without Destroy (D26)")
        self.assertTrue(second.nui_ready())
        second.Destroy()
        self.assertIsNone(self.world.module("nui_hud").current("taskbar"))


# --- fixtures and per-frame Python ---------------------------------------------------------

def fixture(window, variant=None):
    name = window if variant is None else "%s.%s" % (window, variant)
    with open(os.path.join(WINDOWS, window, name + ".fixture.json"), encoding="utf-8") as handle:
        return json.load(handle)


def kind(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "map"
    return "none"


class Fixtures(unittest.TestCase):
    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)

    def check(self, board_class, window, variants=(), owner=None):
        board = board_class(owner) if owner is not None else board_class()
        model = board.initial_model() if board_class.MODEL else {}
        for variant in (None,) + tuple(variants):
            data = fixture(window, variant)
            if not board_class.MODEL:
                self.assertEqual(data, {}, window)
                continue
            self.assertEqual(list(data), [board_class.MODEL], window)
            values = data[board_class.MODEL]
            self.assertEqual(set(values), set(model), "%s %s: the fixture holds every model key" % (window, variant))
            for key, value in values.items():
                self.assertEqual(kind(value), kind(model[key]), "%s.%s" % (window, key))
            self.assertTrue(board.set(**values))
        for key, feed in getattr(board_class, "FEEDS", {}).items():
            self.assertIn(key, model, key)
        self.assertEqual(self.world.game.dbg.errors, [])

    def test_the_taskbar_fixtures_match_its_model(self):
        taskbar = self.world.module("nui_taskbar")
        self.check(taskbar.TaskBarBoard, "taskbar", ("menus",), owner=object())
        slot_keys = set(self.world.module("nui_slots").SLOT_KEYS)
        data = fixture("taskbar")["taskbar"]
        for cell in data["quick_slots"] + data["right_skill"]:
            self.assertEqual(set(cell), slot_keys)
        for row in fixture("taskbar", "menus")["taskbar"]["skill_rows"]:
            for cell in row["slots"]:
                self.assertEqual(set(cell), slot_keys)
        self.assertEqual([cell["index"] for cell in data["quick_slots"]], list(range(8)))

    def test_the_small_windows_fixtures_match_their_models(self):
        self.check(self.world.module("nui_expanded_taskbar").ExpandedTaskBarBoard, "expanded-taskbar", owner=object())
        self.check(self.world.module("nui_energy_bar").EnergyBarBoard, "energy-bar", ("hungry", "empty"), owner=object())
        self.check(self.world.module("nui_gift_box").GiftBoxBoard, "gift-box")
        self.check(self.world.module("nui_game_buttons").GameButtonBoard, "game-buttons", owner=object())

    def test_the_taskbar_feeds_are_the_spec_table(self):
        self.assertEqual(self.world.module("nui_taskbar").TaskBarBoard.FEEDS, {
            "hp": "player.hp", "hp_max": "player.hp_max", "hp_ratio": "player.hp_ratio",
            "hp_recovery_ratio": "player.hp_recovery_ratio",
            "sp": "player.sp", "sp_max": "player.sp_max", "sp_ratio": "player.sp_ratio",
            "sp_recovery_ratio": "player.sp_recovery_ratio",
            "stamina": "player.stamina", "stamina_max": "player.stamina_max", "stamina_ratio": "player.stamina_ratio",
            "exp_percent": "player.exp_percent", "exp_orbs": "player.exp_orbs",
            "quick_page": "quickslot.page", "quick_slots": "quickslot.slots",
        })


class NoPerFramePython(unittest.TestCase):
    def test_no_core_module_defines_a_per_frame_hook(self):
        for name in CORE_MODULES:
            tree = ast.parse(read(os.path.join(ROOT, name + ".py")))
            defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
            self.assertEqual(defined & {"OnUpdate", "OnRender", "OnMouseOverIn"}, set(), name)


# --- the taskbar: differential ----------------------------------------------------------------

class TaskbarWorlds(unittest.TestCase):
    """A legacy and a NovaUI world with the same state."""

    def setup_state(self, game):
        game.give(0, 27001, 200)
        game.give(1, 27004, 1)
        game.give(5, 72723, 1, sockets=(1, 0, 0))
        game.give(6, 19, 1, size=(1, 2))
        game.no_quick.add(19)
        game.learn(3, 3, grade=1, level=4)
        game.learn(4, 4, grade=0, level=20)
        game.learn(152, 152, grade=0, level=0, skill_type=support.SKILL_CONSTANTS["SKILL_TYPE_GUILD"])
        game.guild_levels[152] = 2
        game.toggle_skills.add(4)
        game.emotion_icons[11] = "icon/action/cheerup.tga"
        game.put_quick(0, INVENTORY, 0)
        game.put_quick(2, SKILL, 3)
        game.put_quick(3, EMOTION, 11)
        game.put_quick(4, INVENTORY, 5)
        game.put_quick(5, SKILL, 152)
        game.status.update({P["HP"]: 1234, P["MAX_HP"]: 2000})

    def worlds(self, mouse_cfg=None):
        def setup(game):
            self.setup_state(game)
            if mouse_cfg is not None:
                game.files["config/mouse.cfg"] = mouse_cfg
        legacy = World(False, setup=setup)
        novaui = World(True, setup=setup)
        tooltips = []
        for world in (legacy, novaui):
            with world, quiet():
                bar = world.nui_windows.make("taskbar", world.uiTaskBar.TaskBar, "nui_taskbar.TaskBar")
                bar.LoadWindow()
                item, skill = world.game.modules["uiToolTip"].ItemToolTip(), world.game.modules["uiToolTip"].SkillToolTip()
                bar.SetItemToolTip(item)
                bar.SetSkillToolTip(skill)
                world.bar, world.tooltip_item, world.tooltip_skill = bar, item, skill
                world.events = []
                for button in range(5):
                    bar.SetToggleButtonEvent(button, (lambda w, b: lambda: w.events.append(b))(world, button))
                if world.nui_on:
                    world.publish_quick()
                tooltips.append((item, skill))
        self.assertIsInstance(legacy.bar, legacy.uiTaskBar.TaskBar)
        self.assertEqual(type(novaui.bar).__module__, "nui_taskbar")
        return legacy, novaui

    def same(self, legacy, novaui, legacy_steps, novaui_steps):
        """Runs each world's steps and compares what each made happen."""
        for world, steps in ((legacy, legacy_steps), (novaui, novaui_steps)):
            mark = len(world.game.log)
            with world, quiet():
                steps(world)
            world.result = [(name, args) for name, args in world.game.log[mark:]
                            if name.split(".", 1)[0] in support.COMPARED and not support.is_getter(name)]
        self.assertEqual(novaui.result, legacy.result)
        return legacy.result

    # The legacy slot windows' events, as CSlotWindow raises them.
    @staticmethod
    def legacy_window(world, index):
        return world.bar.quickslot[0 if index < 4 else 1]

    @classmethod
    def legacy_press(cls, world, index, button=0):
        slots = cls.legacy_window(world, index)
        if button == 0:
            slots.events["select_item" if slots.is_item(index) else "select_empty"](index)
        else:
            event = slots.events.get("unselect_item" if slots.is_item(index) else "unselect_empty")
            if event:
                event(index)

    @classmethod
    def legacy_release_after_drag(cls, world, index):
        """CSlotWindow::OnMouseLeftButtonUp after a drag: the slot under the
        pointer gets its select event."""
        if world.game.modules["mouseModule"].mouseController.isAttached():
            cls.legacy_press(world, index)

    @staticmethod
    def nui(world, event, *args):
        world.bar.board.fire(event, *args)


class TaskbarDifferential(TaskbarWorlds):
    def test_load_window_applies_the_saved_mouse_settings_as_legacy_does(self):
        cases = {None: ("attack", "camera"), "5\t4": ("auto", "skill"), "2\t3": ("attack", "camera"),
                 "0\t3": ("attack", "camera"), "5\t5": ("attack", "camera"), "9\t1": ("attack", "camera"),
                 "garbage": ("attack", "camera")}
        for cfg, (left, right) in cases.items():
            legacy, novaui = self.worlds(mouse_cfg=cfg)
            self.assertEqual(novaui.game.effects(), legacy.game.effects(), cfg)
            board = novaui.bar.board
            self.assertEqual((board.get("left_mode"), board.get("right_mode")), (left, right), cfg)
            for direction, mode in ((0, left), (1, right)):
                art = legacy.bar.curMouseModeButton[direction].visuals["up"].rsplit("_01.sub", 1)[0]
                self.assertEqual(MODE_ART[art], mode, cfg)
                self.assertEqual(legacy.bar.curMouseModeButton[direction].tooltip,
                                 board.get(("left_tip", "right_tip")[direction]), cfg)
            self.assertTrue(legacy.uiTaskBar.TaskBar.IS_EXPANDED and novaui.uiTaskBar.TaskBar.IS_EXPANDED,
                            "the Interface reads the legacy class's IS_EXPANDED")

    def test_pick_and_place_swaps_two_quickslots(self):
        legacy, novaui = self.worlds()

        def legacy_steps(world):
            self.legacy_press(world, 0)
            self.legacy_press(world, 1)

        def novaui_steps(world):
            self.nui(world, "slot_press", "quick", 0, 0)
            self.nui(world, "slot_release", "quick", 0, 0)
            self.nui(world, "slot_press", "quick", 1, 0)
            self.nui(world, "slot_release", "quick", 1, 0)

        result = self.same(legacy, novaui, legacy_steps, novaui_steps)
        self.assertIn(("mouse.AttachObject", (QUICK, 0, 0, 0)), result)
        self.assertIn(("player.RequestMoveGlobalQuickSlotToLocalQuickSlot", (0, 1)), result)
        self.assertEqual(result[-1], ("mouse.DeattachObject", ()))

    def test_a_press_dragged_onto_another_quickslot_drops_there(self):
        legacy, novaui = self.worlds()

        def legacy_steps(world):
            self.legacy_press(world, 2)
            self.legacy_release_after_drag(world, 6)

        def novaui_steps(world):
            self.nui(world, "slot_press", "quick", 2, 0)
            self.nui(world, "slot_release", "quick", 6, 0)

        result = self.same(legacy, novaui, legacy_steps, novaui_steps)
        self.assertIn(("player.RequestMoveGlobalQuickSlotToLocalQuickSlot", (2, 6)), result)

    def test_items_skills_and_emotions_from_legacy_windows_land_in_quickslots(self):
        cases = [
            ("inventory item", (INVENTORY, 1, 27004), ("player.RequestAddLocalQuickSlot", (6, INVENTORY, 1))),
            ("skill", (SKILL, 4, 4), ("player.RequestAddLocalQuickSlot", (6, SKILL, 4))),
            ("emotion", (EMOTION, 12, 12), ("player.RequestAddLocalQuickSlot", (6, EMOTION, 12))),
            ("an item already there swaps (MR-3)", (INVENTORY, 0, 27001),
             ("player.RequestMoveGlobalQuickSlotToLocalQuickSlot", (0, 6))),
            ("a sword the quickslots refuse", (INVENTORY, 6, 19), None),
        ]
        for label, (slot_type, number, index), expected in cases:
            for how in ("click", "drop"):
                legacy, novaui = self.worlds()

                def attach(world):
                    world.game.modules["mouseModule"].mouseController.AttachObject("legacy window", slot_type, number, index)

                def legacy_steps(world):
                    attach(world)
                    self.legacy_press(world, 6)

                def novaui_steps(world):
                    attach(world)
                    if how == "click":
                        self.nui(world, "slot_press", "quick", 6, 0)
                    else:
                        self.nui(world, "slot_drop", "quick", 6)

                result = self.same(legacy, novaui, legacy_steps, novaui_steps)
                requests = [call for call in result if call[0].startswith("player.Request")]
                self.assertEqual(requests, [expected] if expected else [], "%s by %s" % (label, how))
                self.assertFalse(novaui.game.modules["mouseModule"].mouseController.isAttached(), label)

    def test_the_right_button_uses_a_quickslot_with_nothing_attached(self):
        legacy, novaui = self.worlds()

        def legacy_steps(world):
            for index in (0, 1, 2):
                self.legacy_press(world, index, button=1)

        def novaui_steps(world):
            for index in (0, 1, 2):
                self.nui(world, "slot_press", "quick", index, 1)

        result = self.same(legacy, novaui, legacy_steps, novaui_steps)
        self.assertEqual(result, [("player.RequestUseLocalQuickSlot", (0,)), ("player.RequestUseLocalQuickSlot", (2,))],
                         "an empty cell is not used")

    def test_the_page_buttons_turn_the_quick_page(self):
        legacy, novaui = self.worlds()

        def legacy_steps(world):
            world.bar.GetChild("QuickPageDownButton").Click()
            world.bar.GetChild("QuickPageUpButton").Click()
            world.bar.GetChild("QuickPageUpButton").Click()

        def novaui_steps(world):
            self.nui(world, "page_down", 0)
            self.nui(world, "page_up", 0)
            self.nui(world, "page_up", 1)
            self.nui(world, "page_up", 0)

        result = self.same(legacy, novaui, legacy_steps, novaui_steps)
        self.assertEqual(result, [("player.SetQuickPage", (1,)), ("player.SetQuickPage", (0,)), ("player.SetQuickPage", (-1,))])
        self.assertEqual(novaui.game.page, 3)

    def test_the_mode_menus_and_the_skill_picker_set_the_mouse_functions(self):
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            world.game.answer("player", "ChangeCurrentSkillNumberOnly",
                              (lambda w: lambda n: w.bar.OnChangeCurrentSkill(n))(world))

        def legacy_steps(world):
            world.bar.curMouseModeButton[0].Click()
            world.bar.mouseModeButtonList[0].GetChild("button_auto_attack").Click()
            world.bar.curMouseModeButton[1].Click()
            buttons = world.bar.selectSkillButtonList
            self.assertEqual([b.GetSlotIndex() for b in buttons], [3, 4], "level 0 and empty slots are left out")
            buttons[1].OnSelectItemSlot(0)

        def novaui_steps(world):
            self.nui(world, "toggle_mouse", 0, 0)
            self.assertTrue(world.bar.board.get("left_open"))
            self.nui(world, "pick_mode", 0, 5, 0)
            self.assertFalse(world.bar.board.get("left_open"))
            self.nui(world, "toggle_mouse", 1, 0)
            rows = world.bar.board.get("skill_rows")
            self.assertEqual([[slot["ref"] for slot in row["slots"]] for row in rows], [[3, 4]])
            self.nui(world, "pick_skill", 4, 0)

        result = self.same(legacy, novaui, legacy_steps, novaui_steps)
        self.assertEqual(result, [("player.SetMouseFunc", (P["MBT_LEFT"], P["MBF_AUTO"])),
                                  ("player.SetMouseFunc", (P["MBT_RIGHT"], P["MBF_SKILL"])),
                                  ("player.ChangeCurrentSkillNumberOnly", (4,))])
        board = novaui.bar.board
        self.assertEqual((board.get("left_mode"), board.get("right_open"), board.get("skill_rows")), ("auto", False, []))
        self.assertTrue(board.get("right_skill_shown"), "the right button shows the skill (curSkillButton)")
        self.assertEqual(board.get("right_skill")[0]["ref"], 4)
        self.assertTrue(legacy.bar.curSkillButton.shown is not False)
        # Closing the right menu without a pick hides the skill again, as legacy does.
        with novaui, legacy:
            self.nui(novaui, "toggle_mouse", 1, 0)
            self.nui(novaui, "toggle_mouse", 1, 0)
        self.assertFalse(board.get("right_skill_shown"))

    def test_the_window_buttons_the_mall_and_the_camera_image(self):
        legacy, novaui = self.worlds()
        names = ("character", "inventory", "messenger", "system", "expand")

        def legacy_steps(world):
            for button in range(5):
                world.bar.toggleButtonDict[button].Click()
            world.bar._TaskBar__RampageGauge_Click()
            world.bar.HideMouseImage()

        def novaui_steps(world):
            for name in names:
                self.nui(world, "button", name, 0)
                self.nui(world, "button", name, 1)
            self.nui(world, "mall_click", 0)
            world.bar.HideMouseImage()

        result = self.same(legacy, novaui, legacy_steps, novaui_steps)
        self.assertEqual(result, [("net.SendChatPacket", ("/in_game_mall",)), ("player.SetQuickCameraMode", (False,))])
        self.assertEqual(novaui.events, legacy.events)
        self.assertEqual(novaui.events, [0, 1, 2, 3, 4], "a right press triggers nothing")
        with novaui:
            novaui.bar.ShowMouseImage()
            self.assertTrue(novaui.bar.board.get("mouse_image"))

    def test_quickslot_tooltips_show_what_legacy_shows_and_nothing_while_attached(self):
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            with world:
                for index in (0, 2, 5, 1):
                    if world.nui_on:
                        self.nui(world, "slot_over", "quick", index)
                        self.nui(world, "slot_out", "quick", index)
                    else:
                        world.bar.OverInItem(index)
                        world.bar.OverOutItem()
                world.game.modules["mouseModule"].mouseController.AttachObject("x", INVENTORY, 0, 27001)
                if world.nui_on:
                    self.nui(world, "slot_over", "quick", 0)
                else:
                    world.bar.OverInItem(0)
        self.assertEqual(novaui.tooltip_item.shown, legacy.tooltip_item.shown)
        self.assertEqual(novaui.tooltip_skill.shown, legacy.tooltip_skill.shown)
        self.assertEqual(novaui.tooltip_item.shown, [("SetInventoryItem", 0)])
        self.assertEqual(novaui.tooltip_skill.shown, [("SetSkillNew", 3, 3, 1, 4), ("SetSkillNew", 152, 152, 0, 2)],
                         "a guild skill: grade 0 and the guild's level")
        self.assertFalse(novaui.tooltip_item.visible or novaui.tooltip_skill.visible)

    def test_skill_callbacks_rebuild_the_feed_and_follow_the_right_skill(self):
        legacy, novaui = self.worlds()
        novaui.game.state.now = 30.0

        def steps(world):
            world.bar.OnChangeCurrentSkill(4)
            world.bar.OnUseSkill(4, 12.0)
            world.bar.OnActivateSkill(4)
            world.bar.OnDeactivateSkill(4)
            world.bar.SkillClearCoolTime(4)
            world.bar.OnUseSkill(3, 5.0)
            world.bar.RefreshSkill()
            world.bar.RefreshQuickSlot()
            world.bar.RefreshStatus()
            world.bar.RefreshStamina()

        before = len(novaui.game.calls("nuigame.RefreshQuickSlots"))
        self.assertEqual(self.same(legacy, novaui, steps, steps), [], "nothing reaches the server")
        refreshes = len(novaui.game.calls("nuigame.RefreshQuickSlots")) - before
        self.assertEqual(refreshes, 7, "every callback that changes a quickslot asks C++ to rebuild them")
        with novaui:
            novaui.bar.OnChangeCurrentSkill(4)
            novaui.bar.OnUseSkill(4, 12.0)
            right = novaui.bar.board.get("right_skill")[0]
            self.assertEqual((right["cd_start"], right["cd_end"], right["active"]), (30.0, 42.0, True), "a toggle skill")
            novaui.bar.OnActivateSkill(4)
            self.assertFalse(novaui.bar.board.get("right_skill")[0]["active"], "legacy deactivates it here too")
            novaui.bar.OnUseSkill(4, 12.0)
            novaui.bar.SkillClearCoolTime(4)
            right = novaui.bar.board.get("right_skill")[0]
            self.assertEqual((right["cd_start"], right["cd_end"]), (0.0, 0.0))
        self.assertEqual(legacy.bar.curSkillButton.GetSlotIndex(), 4)
        self.assertTrue(legacy.bar.curSkillButton._cell(0)["active"] is False)

    def test_hide_closes_the_menus_and_destroy_saves_the_mouse_settings(self):
        legacy, novaui = self.worlds(mouse_cfg="5\t3")

        def legacy_steps(world):
            world.bar.Show()
            world.bar.Hide()
            world.bar.Destroy()

        def novaui_steps(world):
            world.bar.Show()
            self.assertTrue(world.bar.IsShow())
            self.nui(world, "toggle_mouse", 0, 0)
            self.nui(world, "toggle_mouse", 1, 0)
            world.bar.Hide()
            board = world.bar.board
            self.assertFalse(world.bar.IsShow())
            self.assertEqual((board.get("left_open"), board.get("right_open"), board.get("skill_rows")), (False, False, []))
            world.bar.Destroy()
            self.assertEqual(board.calls[-1], ("destroy",))

        self.same(legacy, novaui, legacy_steps, novaui_steps)
        self.assertEqual(novaui.game.files["config/mouse.cfg"], legacy.game.files["config/mouse.cfg"])
        self.assertEqual(novaui.game.files["config/mouse.cfg"], "5\t3")

    def test_the_gift_box_follows_show_gift_and_hide_gift(self):
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            with world:
                world.bar.ShowGift()
                shown = world.bar.wndGiftBox.IsShow()
                world.bar.HideGift()
                self.assertTrue(shown)
                self.assertFalse(world.bar.wndGiftBox.IsShow())
        self.assertEqual(type(novaui.bar.wndGiftBox).__module__, "nui_gift_box")
        self.assertIs(type(legacy.bar.wndGiftBox), legacy.uiTaskBar.GiftBox)


# --- the small windows ----------------------------------------------------------------------------

class TaskbarHeight(unittest.TestCase):
    """GetBarHeight: the drawn bar in pixels, which the legacy chat stays
    above (interfacemodule.py __PlaceChatAboveTaskBar)."""

    def bar(self, screen_width=1600):
        world = World(True)
        world.game.modules["wndMgr"].GetScreenWidth = lambda: screen_width
        with world, quiet():
            bar = world.nui_windows.make("taskbar", world.uiTaskBar.TaskBar, "nui_taskbar.TaskBar")
            bar.LoadWindow()
        self.assertEqual(type(bar).__module__, "nui_taskbar")
        return world, bar

    def test_it_follows_the_theme_and_the_scale_and_says_so_after_each_change(self):
        world, bar = self.bar()
        nui = world.game.modules["nui"]
        heard = []
        with world:
            self.assertEqual(bar.GetBarHeight(), 49, "48dp and its 1dp top border")
            bar.SetBarHeightEvent(lambda: heard.append(bar.GetBarHeight()))
            nui.set_scale_percent(150)
            nui.set_theme("classic")
            nui.set_scale_percent(100)
            nui.set_theme("modern-light")
        self.assertEqual(heard, [74, 56, 37, 49], "73.5 and 55.5 pixels round up")

    def test_on_a_narrow_screen_the_modern_bar_shrinks_with_its_document(self):
        for width, scale, height in ((1600, 100, 49), (1060, 100, 49), (1059, 100, 47), (853, 100, 40), (800, 100, 37),
                                     (600, 100, 30), (1600, 200, 74), (1600, 150, 74)):
            world, bar = self.bar(width)
            with world:
                world.game.modules["nui"].set_scale_percent(scale)
                self.assertEqual(bar.GetBarHeight(), height, (width, scale))
                world.game.modules["nui"].set_theme("classic")
                self.assertEqual(bar.GetBarHeight(), {100: 37, 150: 56, 200: 74}[scale], "classic never shrinks")

    def test_the_heights_are_the_style_sheets(self):
        taskbar = World(True).game.load("nui_taskbar", "nui_taskbar.py")
        sheet = read(os.path.join(WINDOWS, "taskbar", "taskbar.rcss"))
        block = re.search(r"\n\.taskbar-bar\s*\{([^}]*)\}", sheet).group(1)
        height = float(re.search(r"(?<![-\w])height:\s*([\d.]+)dp", block).group(1))
        # The bar is an edge board (the shared chrome): its top border comes
        # from the component's variant, the first of its border widths.
        markup = read(os.path.join(WINDOWS, "taskbar", "taskbar.rml"))
        self.assertRegex(markup, r'class="taskbar-bar nui-board nui-board--edge ')
        frame = read(os.path.join(WINDOWS, os.pardir, "components", "window-frame.rcss"))
        edge = re.search(r"\n\.nui-board--edge\s*\{([^}]*)\}", frame).group(1)
        border = float(re.search(r"border-width:\s*([\d.]+)dp", edge).group(1))
        self.assertEqual(height + border, taskbar.BAR_HEIGHT_DP)
        classic = read(os.path.join(CLASSIC_WINDOWS, "taskbar.rcss"))
        block = re.search(r"body\.skin-classic\.taskbar \.taskbar-bar\s*\{([^}]*)\}", classic).group(1)
        self.assertEqual(float(re.search(r"(?<![-\w])height:\s*([\d.]+)dp", block).group(1)), taskbar.CLASSIC_BAR_HEIGHT_DP)
        self.assertIn("border-width: 0", block)
        steps = re.findall(r"@media \(max-width: (\d+)dp\)\s*\{\s*body\.taskbar \{[^}]*scale\(([\d.]+)\)", sheet)
        self.assertEqual(sorted((int(width), float(factor)) for width, factor in steps), sorted(taskbar.NARROW_STEPS))


class ClassicHints(unittest.TestCase):
    """The classic taskbar hints draw legacy's default text gray (finding P4
    of the Wave 2a in-game validation: legacy's TextToolTip lines peak at
    199, the classic ones at 218 with --text)."""

    def test_the_hints_use_the_legacy_text_gray(self):
        classic = read(os.path.join(CLASSIC_WINDOWS, "taskbar.rcss"))
        block = re.search(r"body\.skin-classic\.taskbar \.nui-tooltip\.taskbar-tip\s*\{([^}]*)\}", classic).group(1)
        self.assertIn("color: var(--classic-button-text)", block)
        self.assertIn("font-effect: outline(1dp var(--classic-text-outline))", block)
        tokens = json.loads(read(os.path.join(WINDOWS, "..", "theme", "tokens.json")))
        self.assertEqual(tokens["skins"]["classic"]["classic-button-text"], "#c7c7c7")


class SmallWindows(unittest.TestCase):
    def pair(self, setup=None):
        legacy, novaui = World(False, setup=setup), World(True, setup=setup)
        return legacy, novaui

    def test_the_energy_bar_shows_the_state_and_hint_legacy_shows(self):
        cases = [(None, "empty"), (7200, "full"), (1081, "full"), (1079, "hungry"), (1, "hungry"), (0, "empty"), (-50, "empty")]
        for left, state in cases:
            def setup(game):
                game.status[P["ENERGY"]] = 37
                if left is not None:
                    game.status[P["ENERGY_END_TIME"]] = game.timestamp + left
            legacy, novaui = self.pair(setup)
            with legacy:
                bar = legacy.nui_windows.make("energy-bar", legacy.uiTaskBar.EnergyBar, "nui_energy_bar.EnergyBar")
                bar.LoadWindow()
                bar.RefreshStatus()
                shown = [name for name in ("empty", "hungry", "full") if getattr(bar, "energy" + name.capitalize()).IsShow()]
                legacy_tip = bar.tooltipEnergy.textLine.text
            with novaui:
                facade = novaui.nui_windows.make("energy-bar", novaui.uiTaskBar.EnergyBar, "nui_energy_bar.EnergyBar")
                facade.LoadWindow()
                self.assertEqual(type(facade).__module__, "nui_energy_bar")
                facade.board.fire("energy_over")
            self.assertEqual(shown, [state], left)
            self.assertEqual((facade.board.get("state"), facade.board.get("tip")), (state, legacy_tip), left)
            self.assertEqual(novaui.game.effects(), legacy.game.effects())

    def test_the_expanded_taskbar_opens_the_dragon_soul_window_and_closes_on_escape(self):
        legacy, novaui = self.pair()
        for world in (legacy, novaui):
            with world:
                bar = world.nui_windows.make("expanded-taskbar", world.uiTaskBar.ExpandedTaskBar,
                                             "nui_expanded_taskbar.ExpandedTaskBar")
                bar.LoadWindow()
                world.events = []
                bar.SetToggleButtonEvent(bar.BUTTON_DRAGON_SOUL, lambda: world.events.append("dragon soul"))
                bar.SetToolTipText(bar.BUTTON_DRAGON_SOUL, "Dragon @Stone")
                bar.Show()
                bar.SetTop()
                if world.nui_on:
                    self.assertEqual(bar.board.get("tip"), "Dragon @⁠Stone")
                    bar.board.fire("dragon_soul", 1)
                    bar.board.fire("dragon_soul", 0)
                    self.assertTrue(bar.escape.is_shown(), "its Escape proxy shows with it")
                    self.assertIs(bar.escape._window.OnPressEscapeKey(), True)
                    self.assertFalse(bar.escape.is_shown())
                else:
                    self.assertEqual(bar.toggleButtonDict[bar.BUTTON_DRAGON_SOUL].tooltip, "Dragon @Stone")
                    bar.toggleButtonDict[bar.BUTTON_DRAGON_SOUL].Click()
                    self.assertIs(bar.OnPressEscapeKey(), True)
                self.assertFalse(bar.IsShow(), "Escape closes it")
                world.window = bar
        self.assertEqual(novaui.events, legacy.events)
        self.assertEqual(novaui.events, ["dragon soul"])
        with novaui:
            board, escape = novaui.window.board, novaui.window.escape
            novaui.window.Destroy()
            self.assertEqual(board.calls[-1], ("destroy",))
            self.assertIsNone(escape._window)
        self.assertEqual(novaui.game.effects(), legacy.game.effects())

    def test_the_game_buttons_show_and_press_as_legacy(self):
        def setup(game):
            game.status[P["STAT"]] = 3
            game.status[P["SKILL_ACTIVE"]] = 0
            game.play_time = 0
            game.observer = True
        legacy, novaui = self.pair(setup)
        for world in (legacy, novaui):
            with world:
                window = world.nui_windows.make("game-buttons", world.uiGameButton.GameButtonWindow,
                                                "nui_game_buttons.GameButtonWindow")
                world.window = window
                world.events = []
                for name in ("STATUS", "SKILL", "QUEST", "HELP", "BUILD"):
                    window.SetButtonEvent(name, (lambda n: lambda: world.events.append(n))(name))
                window.CheckGameButton()
                world.hidden_check = self.shown(world)
                window.SetTop()
                window.Show()
                window.CheckGameButton()
                window.ShowBuildButton()
                world.first = self.shown(world)
                window.HideBuildButton()
                window.SetObserverMode(False)
                world.game.status[P["STAT"]] = 0
                world.game.status[P["SKILL_ACTIVE"]] = 2
                window.CheckGameButton()
                world.second = self.shown(world)
                window.SetObserverMode(True)
                self.press(world, "EXIT_OBSERVER")
                self.press(world, "STATUS")
                self.press(world, "SKILL")
        self.assertEqual(novaui.hidden_check, legacy.hidden_check)
        self.assertEqual(legacy.hidden_check, {"EXIT_OBSERVER"}, "every button starts hidden; the observer follows the mode")
        self.assertEqual(novaui.first, legacy.first)
        self.assertEqual(legacy.first, {"STATUS", "HELP", "BUILD", "EXIT_OBSERVER"})
        self.assertEqual(novaui.second, legacy.second)
        self.assertEqual(legacy.second, {"SKILL", "HELP"}, "the task button never shows")
        self.assertEqual(novaui.events, legacy.events)
        self.assertEqual(novaui.game.effects(), legacy.game.effects())
        self.assertIn(("net.SendChatPacket", ("/observer_exit",)), novaui.game.effects())
        # An unknown button name aborts, as legacy does.
        for world in (legacy, novaui):
            with world, quiet():
                world.window.SetButtonEvent("NO_SUCH_BUTTON", lambda: None)
        self.assertEqual(novaui.game.calls("app.Abort"), legacy.game.calls("app.Abort"))
        self.assertEqual(len(novaui.game.calls("app.Abort")), 1)

    @staticmethod
    def shown(world):
        window = world.window
        if world.nui_on:
            model = window.board.model
            keys = {"STATUS": "show_status", "SKILL": "show_skill", "QUEST": "show_quest", "HELP": "show_help",
                    "BUILD": "show_build", "EXIT_OBSERVER": "show_observer"}
            return {name for name, key in keys.items() if model[key]}
        return {name for name in GAME_BUTTONS if window.gameButtonDict[name].IsShow()}

    @staticmethod
    def press(world, name):
        if world.nui_on:
            if world.window.board.model[{"STATUS": "show_status", "SKILL": "show_skill",
                                          "EXIT_OBSERVER": "show_observer"}[name]]:
                world.window.board.fire("press", name, 0)
        elif world.window.gameButtonDict[name].IsShow():
            world.window.gameButtonDict[name].Click()


# --- the wiring (spec 5.13) --------------------------------------------------------------------------------

# Wave 2b's sites (P10 spec 5.8), Wave 3a's (P11 spec 6.8) and Wave 5a's (P12
# spec 6.6) are in their place in the file order; nui_chat_test.Wiring,
# nui_sys_test.Wiring and nui_quest_test.Wiring check them in more detail.
EXPECTED_SITES = {
    # Wave 4's sites (P16 spec 6.2) are in their place too; nui_windows_test.Wave4Flags
    # checks their lines.
    "interfacemodule.py": [("make", "messenger", "uiMessenger.MessengerWindow", "nui_messenger.MessengerWindow"),
                           ("make", "guild", "uiGuild.GuildWindow", "nui_guild.GuildWindow"),
                           ("make", "chat", "uiChat.ChatWindow", "nui_chat.ChatWindow"),
                           ("make", "taskbar", "uiTaskBar.TaskBar", "nui_taskbar.TaskBar"),
                           ("make", "expanded-taskbar", "uiTaskBar.ExpandedTaskBar", "nui_expanded_taskbar.ExpandedTaskBar"),
                           ("make", "energy-bar", "uiTaskBar.EnergyBar", "nui_energy_bar.EnergyBar"),
                           ("make", "party", "uiParty.PartyWindow", "nui_party.PartyWindow"),
                           ("make", "game-buttons", "uiGameButton.GameButtonWindow", "nui_game_buttons.GameButtonWindow"),
                           ("make", "character", "uiCharacter.CharacterWindow", "nui_character.CharacterWindow"),
                           ("make", "inventory", "uiInventory.InventoryWindow", "nui_inventory.InventoryWindow"),
                           ("make", "dragon-soul", "uiDragonSoul.DragonSoulWindow", "nui_dragon_soul.DragonSoulWindow"),
                           ("make", "dragon-soul-refine", "uiDragonSoul.DragonSoulRefineWindow",
                            "nui_dragon_soul_refine.DragonSoulRefineWindow"),
                           ("make", "minimap", "uiMiniMap.MiniMap", "nui_minimap.MiniMap"),
                           ("make", "safebox", "uiSafebox.SafeboxWindow", "nui_safebox.SafeboxWindow"),
                           ("make", "mall", "uiSafebox.MallWindow", "nui_mall.MallWindow"),
                           ("make", "chat-log", "uiChat.ChatLogWindow", "nui_chat_log.ChatLogWindow"),
                           ("make", "exchange", "uiExchange.ExchangeDialog", "nui_exchange.ExchangeDialog"),
                           ("make", "point-reset", "uiPointReset.PointResetDialog", "nui_point_reset.PointResetDialog"),
                           ("make", "shop", "uiShop.ShopDialog", "nui_shop.ShopDialog"),
                           ("make", "restart", "uiRestart.RestartDialog", "nui_restart.RestartDialog"),
                           ("make", "system-menu", "uiSystem.SystemDialog", "nui_system_menu.SystemDialog"),
                           ("make", "safebox", "uiSafebox.PasswordDialog", "nui_safebox.PasswordDialog"),
                           ("make", "tooltips", "uiToolTip.HyperlinkItemToolTip", "nui_link_tooltip.HyperlinkItemToolTip"),
                           ("make", "tooltips", "uiToolTip.ItemToolTip", "nui_item_tooltip.ItemToolTip"),
                           ("make", "tooltips", "uiToolTip.SkillToolTip", "nui_skill_tooltip.SkillToolTip"),
                           ("make", "private-shop", "uiPrivateShopBuilder.PrivateShopBuilder",
                            "nui_private_shop.PrivateShopBuilder"),
                           ("make", "refine", "uiRefine.RefineDialogNew", "nui_refine.RefineDialogNew"),
                           ("make", "help", "uiHelp.HelpWindow", "nui_help.HelpWindow"),
                           ("make", "tip-board", "uiTip.TipBoard", "nui_tip_board.TipBoard"),
                           ("make", "big-board", "uiTip.BigBoard", "nui_big_board.BigBoard"),
                           ("make", "web", "uiWeb.WebWindow", "nui_web.WebWindow"),
                           ("make", "select-item", "uiselectitem.SelectItemWindow", "nui_select_item.SelectItemWindow"),
                           ("make", "quest", "uiQuest.QuestDialog", "nui_quest.QuestDialog"),
                           ("make", "guild-war", "uiGuild.GuildWarScoreBoard", "nui_guild_war.GuildWarScoreBoard"),
                           ("make", "shop-signs", "uiPrivateShopBuilder.PrivateShopAdvertisementBoard", "nui_shop_signs.ShopSign"),
                           ("make", "equipment-view", "uiEquipmentDialog.EquipmentDialog", "nui_equipment_view.EquipmentDialog"),
                           ("make", "whisper", "uiWhisper.WhisperDialog", "nui_whisper.WhisperDialog"),
                           ("make", "whisper", "uiWhisper.WhisperDialog", "nui_whisper.WhisperDialog"),
                           ("make", "guild-building", "uiGuild.BuildGuildBuildingWindow",
                            "nui_guild_building.BuildGuildBuildingWindow")],
    "game.py": [("make", "target", "uiTarget.TargetBoard", "nui_target.TargetBoard"),
                ("make", "console", "consoleModule.ConsoleWindow", "nui_console.ConsoleWindow"),
                ("make", "map-name", "uiMapNameShower.MapNameShower", "nui_map_name.MapNameShower"),
                ("make", "affects", "uiAffectShower.AffectShower", "nui_affects.AffectShower"),
                ("make", "player-gauge", "uiPlayerGauge.PlayerGauge", "nui_player_gauge.PlayerGauge"),
                # P18 (NOVA-58): the maintenance countdown.
                ("make", "maintenance", "uiMaintenance.MaintenanceWindow", "nui_maintenance.MaintenanceWindow"),
                ("make", "guild-war-dialogs", "uiGuild.AcceptGuildWarDialog", "nui_guild_war_accept.AcceptGuildWarDialog")],
    "uiwhisper.py": [("factory", "edge-buttons", "LegacyWhisperButton", "nui_edge_buttons.EdgeButton")],
    "nui_taskbar.py": [("make", "gift-box", "uiTaskBar.GiftBox", "nui_gift_box.GiftBox")],
    # Wave 3b (P14 spec 6.7): the inventory's dialogs, in the legacy class
    # and in the NovaUI loader that stands for its uiscript loader.
    "uiinventory.py": [("make", "refine", "uiRefine.RefineDialog", "nui_refine.RefineDialog"),
                       ("make", "attach-metin", "uiAttachMetin.AttachMetinDialog", "nui_attach_metin.AttachMetinDialog")],
    "nui_inventory.py": [("make", "refine", "uiRefine.RefineDialog", "nui_refine.RefineDialog"),
                         ("make", "attach-metin", "uiAttachMetin.AttachMetinDialog", "nui_attach_metin.AttachMetinDialog")],
    # Wave 4 (P16 spec 6.2): the guild window's mark lists and its declare dialog.
    "uiguild.py": [("make", "guild-mark", "uiUploadMark.MarkSelectDialog", "nui_guild_mark.MarkSelectDialog"),
                   ("make", "guild-mark", "uiUploadMark.SymbolSelectDialog", "nui_guild_mark.SymbolSelectDialog"),
                   ("make", "guild-war-dialogs", "DeclareGuildWarDialog", "nui_guild_war_declare.DeclareGuildWarDialog")],
}


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
    """A window class that records how it was made and what was called."""

    NUI_FACADE = False
    made = []

    def __init__(self, *args):
        Recorded.made.append(type(self).__name__)
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
    def test_the_wired_files_name_exactly_these_windows_and_classes(self):
        for file_name, expected in EXPECTED_SITES.items():
            self.assertEqual(factory_sites(file_name), expected, file_name)
        tree = ast.parse(read(os.path.join(ROOT, "uiwhisper.py")))
        classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
        self.assertIn("LegacyWhisperButton", classes)
        self.assertNotIn("WhisperButton", classes, "the plain name is the factory")

    def interface(self, windows):
        """interfacemodule.py over MagicMock modules (but nui_windows, nui,
        dbg and systemSetting), with recording window classes."""
        source = read(os.path.join(ROOT, "interfacemodule.py"))
        names = set()
        for node in ast.parse(source).body:
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
        game = support.Game()
        game.modules["systemSetting"].GetUINuiWindows = lambda: windows
        modules = {name: mock.MagicMock(name=name) for name in names - {"sys", "nui_windows", "systemSetting", "dbg", "ui"}}
        Recorded.made = []
        modules["uiTaskBar"].TaskBar = window_class("TaskBar", False)
        for constant in ("BUTTON_CHARACTER", "BUTTON_INVENTORY", "BUTTON_MESSENGER", "BUTTON_SYSTEM", "BUTTON_EXPAND", "BUTTON_CHAT"):
            setattr(modules["uiTaskBar"].TaskBar, constant, TASKBAR_CONSTANTS.index(constant))
        modules["uiTaskBar"].TaskBar.IS_EXPANDED = True
        modules["uiTaskBar"].ExpandedTaskBar = window_class("ExpandedTaskBar", False)
        modules["uiTaskBar"].ExpandedTaskBar.BUTTON_DRAGON_SOUL = 0
        modules["uiTaskBar"].EnergyBar = window_class("EnergyBar", False)
        modules["uiParty"].PartyWindow = window_class("PartyWindow", False)
        modules["uiGameButton"].GameButtonWindow = window_class("GameButtonWindow", False)
        modules["uiTip"].TipBoard = window_class("TipBoard", False)
        modules["uiTip"].BigBoard = window_class("BigBoard", False)
        modules["app"].ENABLE_ENERGY_SYSTEM = 1
        for name, cls in (("nui_taskbar", "TaskBar"), ("nui_expanded_taskbar", "ExpandedTaskBar"),
                          ("nui_energy_bar", "EnergyBar"), ("nui_party", "PartyWindow"),
                          ("nui_game_buttons", "GameButtonWindow"), ("nui_tip_board", "TipBoard"),
                          ("nui_big_board", "BigBoard")):
            module = types.ModuleType(name)
            setattr(module, cls, window_class("Nui" + cls, True))
            if cls == "TipBoard":
                module.TipBoard = window_class("NuiTipBoard", True)
            modules[name] = module
        for name, module in modules.items():
            game.put(name, module)
        game.load("nui_windows", "nui_windows.py")
        interface_module = game.load("interfaceModule", "interfacemodule.py")
        interface = object.__new__(interface_module.Interface)
        return game, interface_module, interface

    def make_sites(self, interface):
        interface._Interface__MakeTaskBar()
        interface._Interface__MakeParty()
        interface._Interface__MakeGameButtonWindow()
        interface._Interface__MakeTipBoard()
        return [type(getattr(interface, name)).__name__ for name in
                ("wndTaskBar", "wndExpandedTaskBar", "wndEnergyBar", "wndParty", "wndGameButton", "tipBoard", "bigBoard")]

    def test_with_every_flag_off_the_interface_makes_the_legacy_windows(self):
        game, module, interface = self.interface("")
        with game:
            made = self.make_sites(interface)
        self.assertEqual(made, ["TaskBar", "ExpandedTaskBar", "EnergyBar", "PartyWindow", "GameButtonWindow", "TipBoard", "BigBoard"])
        self.assertEqual(game.loaded["nui_windows"].DECISIONS.get("gift-box"), None, "the gift-box guard asks nothing then")
        self.assertEqual(game.dbg.errors, [])

    def test_with_each_flag_on_the_interface_makes_exactly_the_named_class(self):
        game, module, interface = self.interface("+hud")
        state = game.state
        with game:
            made = self.make_sites(interface)
        self.assertEqual(made, ["NuiTaskBar", "NuiExpandedTaskBar", "NuiEnergyBar", "NuiPartyWindow", "NuiGameButtonWindow",
                                "NuiTipBoard", "NuiBigBoard"])
        self.assertTrue(state.available)
        self.assertEqual(game.dbg.errors, [])
        game, module, interface = self.interface("+hud,-taskbar")
        with game:
            made = self.make_sites(interface)
        self.assertEqual(made[0], "TaskBar")
        self.assertEqual(game.loaded["nui_windows"].DECISIONS["gift-box"], "legacy: needs the NovaUI taskbar")

    def test_a_novaui_class_that_raises_falls_back_to_the_legacy_one(self):
        game, module, interface = self.interface("+taskbar")

        class Raising(object):
            def __init__(self):
                raise RuntimeError("boom")

        game.modules["nui_taskbar"].TaskBar = Raising
        with game:
            interface._Interface__MakeTaskBar()
        self.assertEqual(type(interface.wndTaskBar).__name__, "TaskBar")
        self.assertEqual(game.dbg.errors, ["nui_windows: taskbar: the controller could not be made (RuntimeError); using the legacy window"])

    def test_interface_close_destroys_only_the_novaui_boards_and_closes_the_edge_buttons(self):
        for windows, facades in (("", False), ("+tip-board,+big-board", True)):
            game, module, interface = self.interface(windows)
            source = inspect.getsource(module.Interface.Close)
            attributes = {node.attr for node in ast.walk(ast.parse(source.replace("\n\t", "\n")[source.index("def"):]))
                          if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self"}
            for name in attributes:
                setattr(interface, name, mock.MagicMock(name=name))
            interface.wndQuestWindow = {}
            interface.questButtonList = []
            interface.whisperButtonList = []
            interface.whisperDialogDict = {}
            interface.guildScoreBoardDict = {}
            interface.equipmentDialogDict = {}
            interface.dlgWhisperWithoutTarget = None
            closed = []
            edge = types.ModuleType("nui_edge_buttons")
            edge.close_all = lambda: closed.append(1)
            with game:
                interface._Interface__MakeTipBoard()
                tip, big = interface.tipBoard, interface.bigBoard
                game.modules["uiQuest"].QuestDialog.__dict__ = {}
                sys.modules["nui_edge_buttons"] = edge if facades else None
                if not facades:
                    del sys.modules["nui_edge_buttons"]
                try:
                    interface.Close()
                finally:
                    sys.modules.pop("nui_edge_buttons", None)
            self.assertEqual(("Destroy",) in tip.calls, facades, windows)
            self.assertEqual(("Destroy",) in big.calls, facades, windows)
            self.assertEqual(closed, [1] if facades else [], windows)
            self.assertFalse(hasattr(interface, "tipBoard"))

    def test_the_legacy_chat_sits_above_a_novaui_taskbar_and_follows_its_height(self):
        heights = [49]

        class Bar(Recorded):
            NUI_FACADE = True
            event = None

            def GetBarHeight(self):
                return heights[0]

            def SetBarHeightEvent(self, event):
                Bar.event = event

        class Chat(object):
            CHAT_WINDOW_WIDTH = 600
            EDIT_LINE_HEIGHT = 25

            def __init__(self):
                self.calls = []

            def SetPosition(self, x, y):
                self.calls.append(("SetPosition", x, y))

            def Refresh(self):
                self.calls.append(("Refresh",))

        for windows in ("+taskbar", ""):
            heights[0] = 49
            Bar.event = None
            game, module, interface = self.interface(windows)
            game.modules["nui_taskbar"].TaskBar = Bar
            game.modules["wndMgr"].GetScreenWidth = lambda: 1600
            game.modules["wndMgr"].GetScreenHeight = lambda: 900
            interface.wndChat = Chat()
            with game:
                interface._Interface__MakeTaskBar()
                if not windows:
                    self.assertEqual(interface.wndChat.calls, [], "flags off: legacy's place, untouched")
                    self.assertIsNone(Bar.event)
                    continue
                self.assertEqual(interface.wndChat.calls, [("SetPosition", 500, 900 - 25 - 49), ("Refresh",)])
                heights[0] = 74  # a scale change
                Bar.event()
            self.assertEqual(interface.wndChat.calls[2:], [("SetPosition", 500, 900 - 25 - 74), ("Refresh",)])

    def test_the_whisper_button_name_is_the_edge_button_factory(self):
        game = support.Game()
        game.modules["systemSetting"].GetUINuiWindows = lambda: ""
        ui = game.modules["ui"]
        for name in ("DragButton", "ThinBoard", "EditLine", "ToggleButton", "ThinScrollBar", "ScrollBar", "ExpandedImageBox"):
            setattr(ui, name, ui.HudWindow)
        game.load("nui_windows", "nui_windows.py")
        whisper = game.load("uiWhisper", "uiwhisper.py")
        self.assertEqual(whisper.WhisperButton.window_id, "edge-buttons")
        self.assertIs(whisper.WhisperButton.legacy, whisper.LegacyWhisperButton)
        self.assertEqual(whisper.WhisperButton.__name__, "LegacyWhisperButton")
        with game:
            button = whisper.WhisperButton()
        self.assertIsInstance(button, whisper.LegacyWhisperButton, "flag off: the legacy button")

    def test_game_py_guards_touch_only_novaui_showers(self):
        tree = ast.parse(read(os.path.join(ROOT, "game.py")))
        guards = [ast.unparse(node) for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == "getattr"
                  and len(node.args) == 3 and ast.literal_eval(node.args[1]) == "NUI_FACADE"]
        self.assertEqual(sorted(guards), sorted(["getattr(shower, 'NUI_FACADE', False)", "getattr(self.mapNameShower, 'NUI_FACADE', False)",
                                                 "getattr(self.playerGauge, 'NUI_FACADE', False)",
                                                 "getattr(self.wndMaintenance, 'NUI_FACADE', False)"]))
        source = read(os.path.join(ROOT, "game.py"))
        self.assertIn("if self.mapNameShower.IsShow() and not getattr(self.mapNameShower, \"NUI_FACADE\", False):\n"
                      "\t\t\tself.mapNameShower.Update()", source)
        self.assertIn("for shower in (self.mapNameShower, self.affectShower):\n"
                      "\t\t\tif getattr(shower, \"NUI_FACADE\", False):\n\t\t\t\tshower.Destroy()\n"
                      "\t\tself.mapNameShower = None", source)



# --- Wave 3c (P15) ---

class EngineWave3c(unittest.TestCase):
    def test_has_engine_3c_needs_the_quest_icon_and_the_3b_engine(self):
        world = World(True)
        with world:
            self.assertTrue(world.module("nui_hud").has_engine_3c(), "the recording nuigame answers every name")
            world.game.modules["nuigame"].lack("QuestIconFileName")
            self.assertFalse(world.module("nui_hud").has_engine_3c(), "a Wave 3b exe")
            self.assertTrue(world.module("nui_hud").has_engine_3b())
        world = World(True)
        with world:
            world.game.state.decorators.discard("nui-cells")
            self.assertFalse(world.module("nui_hud").has_engine_3c(), "the quest icon without the 3b engine")
        world = World(True, engine=False)
        with world:
            self.assertFalse(world.module("nui_hud").has_engine_3c(), "no nuigame at all")


class KeptBoardTest(unittest.TestCase):
    """nui_hud.KeptBoard (P15 V-2, spec 8.1): OnDemand that keeps its board
    loaded and hidden after the first show, its lists emptied."""

    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)
        self.hud = self.world.module("nui_hud")

    def kept(self, document="nui/windows/test/test.rml"):
        nui = self.world.game.modules["nui"]
        hud = self.hud
        log = []

        class Board(nui.Window):
            DOCUMENT = document
            MODEL = "test"

            def initial_model(self):
                return {"value": 0, "cells": [], "cells_on": [1]}

        class Facade(object):
            def __init__(self):
                self.value = 7
                self.cells = [1, 2, 3]
                self.place = None
                self.boards = []
                self.demand = hud.KeptBoard(self.make, self.restore, self.keep, self.empty)

            def make(self):
                board = Board()
                self.boards.append(board)
                log.append("make")
                return board

            def restore(self, board):
                log.append("restore")
                board.set(value=self.value, cells=self.cells, cells_on=[1])

            def keep(self, board):
                log.append("keep")
                box = board.element_box("")
                if box is not None:
                    self.place = (box[0], box[1])

            def empty(self, board):
                log.append("empty")
                board.set(cells_on=[])
        return Facade(), log

    def test_the_first_show_loads_a_hide_empties_and_hides_and_a_later_show_loads_nothing(self):
        facade, log = self.kept()
        demand = facade.demand
        self.assertFalse(demand.loaded())
        self.assertTrue(demand.show())
        board = demand.board()
        self.assertEqual(log, ["make", "restore"])
        self.assertTrue(board.is_visible())
        demand.hide()
        self.assertIsNone(demand.board(), "board() answers only while it shows")
        self.assertIs(demand.kept(), board)
        self.assertTrue(demand.loaded())
        self.assertTrue(board._doc, "the document stays loaded")
        self.assertFalse(board.is_visible())
        self.assertEqual(board.model["cells_on"], [], "its lists emptied while hidden")
        self.assertEqual(log, ["make", "restore", "keep", "empty"])
        loaded = list(self.world.game.loaded_documents())
        self.assertTrue(demand.show())
        self.assertIs(demand.board(), board, "the same board")
        self.assertEqual(log, ["make", "restore", "keep", "empty", "restore"], "no make: nothing loads")
        self.assertEqual(self.world.game.loaded_documents(), loaded)
        self.assertEqual(board.model["cells_on"], [1])
        self.assertTrue(board.is_visible())

    def test_writes_while_hidden_reach_the_next_show_and_destroy_unloads(self):
        facade, log = self.kept()
        demand = facade.demand
        demand.show()
        board = demand.board()
        self.world.game.state.boxes[(board.DOCUMENT, "")] = (40, 50, 300, 200)
        demand.hide()
        self.assertEqual(facade.place, (40, 50))
        facade.value = 11
        demand.show()
        self.assertEqual(board.model["value"], 11)
        demand.hide()
        del log[:]
        demand.destroy()
        self.assertEqual(log, [], "a kept board's place was read at its hide")
        self.assertFalse(board._doc)
        self.assertFalse(demand.loaded())
        self.assertFalse(demand.show(), "forgotten callbacks make nothing")
        self.assertEqual(self.world.game.loaded_documents(), [])

    def test_destroy_while_shown_keeps_the_place_first(self):
        facade, log = self.kept()
        facade.demand.show()
        facade.demand.destroy()
        self.assertEqual(log, ["make", "restore", "keep"])
        self.assertFalse(facade.boards[0]._doc)

    def test_the_probe_loads_nothing_until_the_first_open(self):
        facade, log = self.kept()
        self.assertTrue(facade.demand.probe())
        self.assertEqual(log, ["make"])
        self.assertFalse(facade.boards[0]._doc)
        self.assertFalse(facade.demand.loaded())
        self.assertEqual(self.world.game.loaded_documents(), [])
        facade.demand.show()
        facade.demand.hide()
        self.assertTrue(facade.demand.probe(), "a kept board answers for itself")
        self.assertEqual(log.count("make"), 2)


class PooledBoardTest(unittest.TestCase):
    """nui_hud.BoardPool and PooledBoard (P18): the boards of a window made
    again at each open, or shown several times at once, wait hidden, emptied
    and ownerless in a bounded pool for the next window of their class."""

    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)
        self.hud = self.world.module("nui_hud")
        self.nui = self.world.game.modules["nui"]
        self.log = []

    def window_class(self, pool, document="nui/windows/test/test.rml"):
        nui, hud, log = self.nui, self.hud, self.log
        field = "test-field"
        self.world.game.state.field_events[(document, field)] = "typed"

        class Board(hud.Pooled, hud.RaisesOnPress, nui.Window):
            DOCUMENT = document
            MODEL = "test"
            INSTANCED = True
            FIELDS = (field,)
            PARK = "test-park"

            def __init__(self, owner):
                self._owner = hud.keep_weakly(owner)
                nui.Window.__init__(self)

            def initial_model(self):
                return {"name": "", "cells": [], "cells_on": [1]}

            @nui.on("typed")
            def on_typed(self, value, linebreak=False):
                return self._owner.typed(value)

        class Facade(object):
            def __init__(self, name):
                self.name = name
                self.text = ""
                self.typed_values = []
                self.demand = hud.PooledBoard(pool, self.make, self.restore, self.keep, self.empty, self.adopt)

            def make(self):
                log.append(("make", self.name))
                return Board(self)

            def adopt(self, board):
                log.append(("adopt", self.name))
                board.adopt(self)

            def restore(self, board):
                log.append(("restore", self.name))
                board.set(name=self.name, cells=[1, 2], cells_on=[1])

            def keep(self, board):
                log.append(("keep", self.name))

            def empty(self, board):
                log.append(("empty", self.name))
                board.set(name="", cells_on=[])

            def typed(self, value):
                self.typed_values.append(value)

            def SetTop(self):
                log.append(("SetTop", self.name))

        return Facade, field

    def test_the_probe_s_board_waits_for_the_first_show_and_a_hide_puts_it_back_emptied(self):
        pool = self.hud.BoardPool("test-a", 2)
        Facade, field = self.window_class(pool)
        a = Facade("a")
        self.assertTrue(a.demand.probe())
        self.assertEqual(self.log, [("make", "a")])
        self.assertEqual(len(pool), 1, "the probe's board waits")
        self.assertTrue(a.demand.show())
        self.assertEqual(self.log, [("make", "a"), ("adopt", "a"), ("restore", "a")], "one load for the first open")
        board = a.demand.board()
        self.assertEqual(board.model["name"], "a")
        self.assertEqual(len(pool), 0)
        board.set_value(field, "a's draft")
        self.assertEqual(a.typed_values, ["a's draft"])
        a.demand.hide()
        self.assertIsNone(a.demand.board(), "a hidden window holds no board")
        self.assertEqual(pool.boards(), [board])
        self.assertFalse(board.is_visible())
        self.assertTrue(board._doc, "it stays loaded")
        self.assertEqual((board.model["name"], board.model["cells_on"]), ("", []), "emptied")
        self.assertEqual(board.fields.get(field), "", "no text left in its field")
        self.assertEqual(a.typed_values, ["a's draft"], "the clearing reaches no window")
        self.assertIs(board._owner, self.hud.NO_OWNER)
        self.assertEqual(self.log[-2:], [("keep", "a"), ("empty", "a")])

    def test_the_next_window_of_the_class_takes_the_waiting_board_and_sets_its_own_state(self):
        pool = self.hud.BoardPool("test-b", 2)
        Facade, field = self.window_class(pool)
        a, b = Facade("a"), Facade("b")
        a.demand.show()
        board = a.demand.board()
        board.set_value(field, "secret")
        a.demand.hide()
        del self.log[:]
        self.assertTrue(b.demand.probe(), "a waiting board answers the probe")
        self.assertTrue(b.demand.show())
        self.assertIs(b.demand.board(), board, "no load: the waiting board")
        self.assertEqual(self.log, [("adopt", "b"), ("restore", "b")])
        self.assertEqual(board.model["name"], "b")
        self.assertEqual(board.fields.get(field), "")
        board.fire("typed", "b's", False)
        self.assertEqual((a.typed_values, b.typed_values), (["secret"], ["b's"]), "its events reach b only")
        board.raise_for(0)
        self.assertEqual(self.log[-1], ("SetTop", "b"))
        self.assertEqual(pool.loads, 1)
        self.assertEqual(pool.reuses, 1)

    def test_the_bound_counts_every_hidden_board_and_a_drain_unloads_them(self):
        pool = self.hud.BoardPool("test-c", 2)
        Facade, field = self.window_class(pool)
        windows = [Facade(name) for name in "abcd"]
        for window in windows:
            window.demand.show()
        boards = [window.demand.board() for window in windows]
        self.assertEqual(len(set(map(id, boards))), 4, "four at once: four documents")
        self.assertEqual(len(self.world.game.loaded_documents()), 4)
        for window in windows:
            window.demand.hide()
        self.assertEqual(len(pool), 2, "two wait")
        self.assertEqual(len(self.world.game.loaded_documents()), 2, "the others were destroyed")
        self.assertEqual(self.hud.pool_stats()["test-c"],
                         {"waiting": 2, "bound": 2, "most": 2, "loads": 4, "reuses": 0})
        self.assertEqual(self.hud.drain_pools(), 2)
        self.assertEqual(len(pool), 0)
        self.assertEqual(self.world.game.loaded_documents(), [])

    def test_destroy_of_a_shown_window_puts_its_board_back_and_forgets_the_callbacks(self):
        pool = self.hud.BoardPool("test-d", 1)
        Facade, field = self.window_class(pool)
        a = Facade("a")
        a.demand.show()
        board = a.demand.board()
        a.demand.destroy()
        self.assertEqual(pool.boards(), [board])
        self.assertEqual(self.log[-2:], [("keep", "a"), ("empty", "a")])
        self.assertFalse(a.demand.show(), "forgotten callbacks: a waiting board is not taken without a window")
        b = Facade("b")
        b.demand.show()
        self.assertIs(b.demand.board(), board)

    def test_a_board_that_did_not_load_never_waits(self):
        pool = self.hud.BoardPool("test-e", 2)
        Facade, field = self.window_class(pool, document="nui/windows/broken/broken.rml")
        self.world.game.state.failing.add("nui/windows/broken/broken.rml")
        a = Facade("a")
        self.assertFalse(a.demand.probe())
        self.assertFalse(a.demand.show())
        self.assertEqual(len(pool), 0)
        self.assertEqual(pool.loads, 0)

    def test_release_empties_the_fields_of_a_hidden_board_too(self):
        """A field a hidden board holds (under a data-if, or the board hidden
        by its window first) is emptied as well: set_value's even_hidden."""
        pool = self.hud.BoardPool("test-f", 1)
        Facade, field = self.window_class(pool)
        a = Facade("a")
        a.demand.show()
        board = a.demand.board()
        board.set_value(field, "typed")
        board.hide()
        board.release()
        self.assertEqual(board.fields.get(field), "")
        self.assertEqual(a.typed_values, ["typed"], "the clearing reaches no window")

    def test_no_owner_absorbs_every_call(self):
        none = self.hud.NO_OWNER
        self.assertIsNone(none.board.close())
        self.assertIsNone(none._cell_events.over(3))
        self.assertFalse(none)


if __name__ == "__main__":
    unittest.main()
