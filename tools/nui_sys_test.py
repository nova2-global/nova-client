"""Tests for the NovaUI Wave 3a system windows (P11 spec 6): the system menu
(assets/root/nui_system_menu.py), the system options and the music list
(nui_system_options.py, nui_music_list.py), the game options
(nui_game_options.py), the restart dialog (nui_restart.py), the help
(nui_help.py), the point reset (nui_point_reset.py) and their wiring in
interfacemodule.py, uisystemoption.py and uigameoption.py:
python3 -B -m unittest nui_sys_test (from tools/).

Plain CPython over nui_game_support's stand-ins (install_wave3a_ui reads the
real uiscript files, so the legacy windows are made and pressed as players
press them). For every window:
- facade: every method the Interface, game.py, another window or C++ calls
  on the legacy class exists on the NovaUI class with a signature the legacy
  callers can use, with the legacy class's name and constructor;
- differential: the legacy class and the NovaUI class, each in a world of its
  own with the same state, driven through the same flows (legacy's widgets
  against the board's data events), make the same net, systemSetting, snd,
  background, app, chrmgr, musicInfo, chat and uiPrivateShopBuilder calls and
  the same Interface calls, in order, getters left out; slider values within
  0.01. The Interface section has no legacy original and is checked apart;
- fixture: each board, made with a stand-in owner and set from its fixture,
  holds every key of the fixture with the same kind, and logs nothing;
- on demand: no document while the window is hidden; the board made at Show
  and gone at Hide;
- no per-frame Python: no NovaUI module defines OnUpdate, OnRender or
  OnMouseOverIn."""
import ast
import contextlib
import gc
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
SYS = "+sys,+dialogs"
P = support.PLAYER_CONSTANTS
NOVAUI_MODULES = ("nui_system_menu", "nui_system_options", "nui_music_list", "nui_game_options", "nui_restart",
                  "nui_help", "nui_point_reset")
# The modules whose calls the differential tests compare (spec 6.0.7), and
# the Interface's own calls ("interface.*", from the events the tests set).
EFFECT_MODULES = ("net", "systemSetting", "snd", "background", "app", "chrmgr", "musicInfo", "chat",
                  "uiPrivateShopBuilder", "interface")
QUESTION = "nui/windows/dialog-question/dialog-question.rml"
LOADED_LEGACY = (("uiSelectMusic", "uiselectmusic.py"), ("uiCommon", "uicommon.py"),
                 ("uiSystemOption", "uisystemoption.py"), ("uiGameOption", "uigameoption.py"),
                 ("uiSystem", "uisystem.py"), ("uiRestart", "uirestart.py"), ("uiHelp", "uihelp.py"),
                 ("uiPointReset", "uipointreset.py"))
LOADED_NOVAUI = ("nui_dialog_kit", "nui_dialog_message", "nui_dialog_question", "nui_theme_picker", "nui_music_list",
                 "nui_system_options", "nui_game_options", "nui_system_menu", "nui_restart", "nui_help",
                 "nui_point_reset")


def quiet():
    """The legacy windows print banners."""
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class World(object):
    """One world: a Game with the legacy Wave 3a modules and the NovaUI ones
    loaded over its stand-ins, the flags of `windows` on when `nui_on`."""

    def __init__(self, nui_on, windows=SYS, engine=True, setup=None):
        game = self.game = support.Game(engine=engine)
        support.install_wave2b_ui(game)
        support.install_wave3a_ui(game)
        game.modules["systemSetting"].GetUINuiWindows = lambda: windows if nui_on else ""
        game.modules["localeInfo"].OPTION_PVPMODE_PROTECT = "Level %d needed"
        game.status[P["LEVEL"]] = 105
        for name in ("uiOption", "networkModule", "interfaceModule"):
            game.put(name, types.ModuleType(name))
        if setup is not None:
            setup(game)
        game.load_standard()
        self.musicInfo = game.load_music_info()
        with quiet():
            for name, file_name in LOADED_LEGACY:
                game.load(name, file_name).print = lambda *args, **kwargs: None  # their NEW and DELETE banners
            for name in LOADED_NOVAUI:
                game.load(name, name + ".py")
        self.nui_windows = game.loaded["nui_windows"]
        self.nui_on = nui_on

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def m(self, name):
        return self.game.loaded[name]

    def interface_event(self, name):
        """An Interface method the window calls back, recorded in the log."""
        log = self.game.log

        def event(*args):
            log.append(("interface." + name, args))
        return event

    def effects(self):
        return [(name, args) for name, args in self.game.log
                if name.split(".", 1)[0] in EFFECT_MODULES and not support.is_getter(name)]

    def mark(self):
        return len(self.game.log)

    def effects_since(self, mark):
        return [(name, args) for name, args in self.game.log[mark:]
                if name.split(".", 1)[0] in EFFECT_MODULES and not support.is_getter(name)]

    # --- the makers, as the Interface and the system menu make them -----------------

    def make(self, window_id, legacy, novaui):
        with self.game, quiet():
            return self.nui_windows.make(window_id, legacy, novaui)

    def make_menu(self):
        with self.game, quiet():
            menu = self.nui_windows.make("system-menu", self.m("uiSystem").SystemDialog, "nui_system_menu.SystemDialog")
            menu.LoadDialog()
            menu.SetOpenHelpWindowEvent(self.interface_event("OpenHelpWindow"))
            menu.Hide()
        return menu

    def make_options(self):
        with self.game, quiet():
            return self.m("uiSystemOption").OptionDialog()

    def make_game_options(self):
        with self.game, quiet():
            return self.m("uiGameOption").OptionDialog()

    def make_restart(self):
        with self.game, quiet():
            dialog = self.nui_windows.make("restart", self.m("uiRestart").RestartDialog, "nui_restart.RestartDialog")
            dialog.LoadDialog()
            dialog.Hide()
        return dialog

    def make_help(self):
        with self.game, quiet():
            window = self.nui_windows.make("help", self.m("uiHelp").HelpWindow, "nui_help.HelpWindow")
            window.LoadDialog()
            window.SetCloseEvent(self.interface_event("CloseHelpWindow"))
            window.Hide()
        return window

    def make_point_reset(self):
        with self.game, quiet():
            dialog = self.nui_windows.make("point-reset", self.m("uiPointReset").PointResetDialog,
                                           "nui_point_reset.PointResetDialog")
            dialog.LoadDialog()
            dialog.Hide()
        return dialog

    def documents(self):
        return [window.DOCUMENT for window in self.game.state.windows if window._doc]

    def kit_window(self):
        for window in self.game.state.windows:
            if window.DOCUMENT == QUESTION and window._doc:
                return window
        raise AssertionError("no kit question window")


def board(facade):
    return facade.demand.board()


def fire(facade, event, *args):
    """A data event from the facade's shown board."""
    with_board = board(facade)
    if with_board is None:
        raise AssertionError("%s has no board" % type(facade).__name__)
    return with_board.fire(event, *args)


def same_calls(test, legacy, novaui, what):
    """Equal lists of calls; floats within 0.01 (the slider values)."""
    test.assertEqual([name for name, _ in legacy], [name for name, _ in novaui], what)
    for (name, a), (_, b) in zip(legacy, novaui):
        test.assertEqual(len(a), len(b), "%s %s" % (what, name))
        for x, y in zip(a, b):
            if isinstance(x, float) or isinstance(y, float):
                test.assertAlmostEqual(float(x), float(y), delta=0.01, msg="%s %s" % (what, name))
            else:
                test.assertEqual(x, y, "%s %s" % (what, name))


class Pair(unittest.TestCase):
    """A legacy and a NovaUI world with the same state."""

    windows = SYS

    def setup_state(self, game):
        pass

    def worlds(self, setup=None):
        def both(game):
            self.setup_state(game)
            if setup is not None:
                setup(game)
        legacy, novaui = World(False, self.windows, setup=both), World(True, self.windows, setup=both)
        for world in (legacy, novaui):
            world.__enter__()
            self.addCleanup(world.__exit__)
        return legacy, novaui

    def same(self, legacy, novaui, legacy_steps, novaui_steps, what=""):
        """Runs each world's steps and compares the calls they made."""
        a, b = legacy.mark(), novaui.mark()
        with quiet():
            legacy_steps()
        with quiet():
            novaui_steps()
        same_calls(self, legacy.effects_since(a), novaui.effects_since(b), what)
        return legacy.effects_since(a)


# --- facades ------------------------------------------------------------------------------

SCRIPT_WINDOW_CALLS = ("Show", "Hide", "IsShow", "SetTop", "SetCenterPosition", "GetWidth", "GetHeight", "Lock", "Unlock")
SURFACES = {
    # (legacy module, class, NovaUI module, class): the methods callers reach (spec 6.1 to 6.7).
    ("uiSystem", "SystemDialog", "nui_system_menu", "SystemDialog"):
        ("LoadDialog", "Destroy", "SetOpenHelpWindowEvent", "OpenDialog", "Close", "OnBlockMode", "OnChangePKMode",
         "OnPressExitKey", "OnPressEscapeKey"),
    ("uiSystemOption", "LegacyOptionDialog", "nui_system_options", "OptionDialog"):
        ("Destroy", "Close", "OnPressEscapeKey", "OnChangeMusicVolume", "OnChangeSoundVolume", "OnChangeShadowQuality",
         "OnCloseInputDialog", "OnCloseQuestionDialog"),
    ("uiSelectMusic", "FileListDialog", "nui_system_options", "FileListDialog"):
        ("Open", "Close", "SAFE_SetSelectEvent", "OnPressEscapeKey"),
    ("uiGameOption", "LegacyOptionDialog", "nui_game_options", "OptionDialog"):
        ("Destroy", "Close", "OnPressEscapeKey", "OnBlockMode", "OnChangePKMode", "RefreshBlock", "RefreshViewChat",
         "RefreshAlwaysShowName", "RefreshShowDamage", "RefreshShowSalesText"),
    ("uiRestart", "RestartDialog", "nui_restart", "RestartDialog"):
        ("LoadDialog", "Destroy", "OpenDialog", "Close", "RestartHere", "RestartTown", "OnPressExitKey", "OnPressEscapeKey"),
    ("uiHelp", "HelpWindow", "nui_help", "HelpWindow"):
        ("LoadDialog", "Destroy", "SetCloseEvent", "Open", "Close", "OnKeyDown", "OnIMEReturn", "OnPressEscapeKey",
         "OnPressExitKey"),
    ("uiPointReset", "PointResetDialog", "nui_point_reset", "PointResetDialog"):
        ("LoadDialog", "Destroy", "OpenDialog", "OpenConfirmDialog", "ResetPoint", "Close", "OnPressEscapeKey"),
}


def assert_callable_like(test, legacy_method, novaui_method, name):
    """Every call shape the legacy signature takes binds to the NovaUI one."""
    legacy = inspect.signature(legacy_method)
    novaui = inspect.signature(novaui_method)
    positional = [p for p in legacy.parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    required = [p for p in positional if p.default is p.empty]
    for count in range(len(required), len(positional) + 1):
        try:
            novaui.bind(*([None] * count))
        except TypeError as error:
            test.fail("%s: a legacy call with %d arguments does not bind: %s" % (name, count, error))


class Facades(unittest.TestCase):
    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)

    def test_every_facade_keeps_the_legacy_surface(self):
        for (legacy_module, legacy_name, module, name), methods in SURFACES.items():
            legacy_class = getattr(self.world.m(legacy_module), legacy_name)
            novaui_class = getattr(self.world.m(module), name)
            with self.subTest(window=name, module=module):
                for method in methods + SCRIPT_WINDOW_CALLS:
                    self.assertTrue(callable(getattr(novaui_class, method, None)), "%s.%s.%s" % (module, name, method))
                    legacy_method = getattr(legacy_class, method, None)
                    if legacy_method is None or method in SCRIPT_WINDOW_CALLS and not hasattr(legacy_class, "__dict__"):
                        continue
                    assert_callable_like(self, getattr(object.__new__(legacy_class), method),
                                         getattr(object.__new__(novaui_class), method), "%s.%s" % (name, method))
                self.assertIs(novaui_class.NUI_FACADE, True)
                self.assertEqual(novaui_class.__name__, legacy_class.__name__)
                self.assertEqual(len(inspect.signature(novaui_class.__init__).parameters),
                                 len(inspect.signature(legacy_class.__init__).parameters), "the legacy constructor arguments")

    @staticmethod
    def makers(world):
        return (("system-menu", world.make_menu), ("system-options", world.make_options),
                ("game-options", world.make_game_options), ("restart", world.make_restart),
                ("help", world.make_help), ("point-reset", world.make_point_reset))

    def test_every_facade_answers_the_make_protocol_and_needs_the_engine(self):
        hud = self.world.m("nui_hud")
        for key, maker in self.makers(self.world):
            facade = maker()
            with self.subTest(window=key):
                self.assertIs(getattr(type(facade), "NUI_FACADE", False), True, "the NovaUI class was made")
                self.assertTrue(facade.nui_ready())
                self.assertIs(hud.current(key), facade)
                facade.nui_discard()
                self.assertFalse(facade.nui_ready())
                self.assertIsNone(hud.current(key), "a discarded facade drops its record")
        world = World(True, engine=False)
        with world:
            for key, maker in self.makers(world)[:-1]:
                facade = maker()
                with self.subTest(window=key, engine=False):
                    self.assertFalse(getattr(type(facade), "NUI_FACADE", False), "an older exe keeps the legacy window")
            self.assertIn("nui_windows: restart: the document did not load; using the legacy window", world.game.dbg.errors)

    def test_a_new_facade_destroys_a_previous_one_that_is_still_alive(self):
        first = self.world.make_menu()
        with self.world.game:
            first.Show()
        old = board(first)
        second = self.world.make_menu()
        self.assertEqual(old.calls[-1], ("destroy",), "the phase that ended without Destroy")
        self.assertTrue(second.nui_ready())
        second.Destroy()
        self.assertIsNone(self.world.m("nui_hud").current("system-menu"))

    def test_the_music_list_facade_answers_its_documents_load(self):
        state = self.world.game.state
        state.failing.add("nui/windows/music-list/music-list.rml")
        options = self.world.make_options()
        self.assertFalse(getattr(type(options), "NUI_FACADE", False), "a list that does not load keeps the legacy options")
        self.assertIn("nui_windows: system-options: the document did not load; using the legacy window",
                      self.world.game.dbg.errors)


# --- the system menu (spec 6.1) ------------------------------------------------------------

MENU_BUTTONS = (("help_button", "help"), ("mall_button", "mall"), ("change_button", "change"),
                ("logout_button", "logout"), ("exit_button", "exit"), ("cancel_button", "cancel"))


class SystemMenu(Pair):
    def menus(self):
        legacy, novaui = self.worlds()
        a, b = legacy.make_menu(), novaui.make_menu()
        self.assertEqual(type(a).__module__, "uiSystem")
        self.assertEqual(type(b).__module__, "nui_system_menu")
        return legacy, novaui, a, b

    def test_each_button_closes_the_menu_and_makes_legacys_calls(self):
        legacy, novaui, a, b = self.menus()
        expected = {"help": [("interface.OpenHelpWindow", ())], "mall": [("net.SendChatPacket", ("/in_game_mall",))],
                    "change": [("net.ExitGame", ())], "logout": [("net.LogOutGame", ())],
                    "exit": [("net.ExitApplication", ())], "cancel": []}
        for child, what in MENU_BUTTONS:
            with self.subTest(button=what):
                a.OpenDialog()
                b.OpenDialog()
                self.assertTrue(a.IsShow() and b.IsShow())
                calls = self.same(legacy, novaui, a.GetChild(child).click, lambda: fire(b, "act", what, 0), what)
                self.assertEqual(calls, expected[what])
                self.assertFalse(a.IsShow(), "legacy closes first")
                self.assertFalse(b.IsShow())
                self.assertIsNone(board(b), "the document went with the hide")

    def test_only_the_left_button_acts(self):
        legacy, novaui, a, b = self.menus()
        b.OpenDialog()
        mark = novaui.mark()
        fire(b, "act", "exit", 1)
        self.assertEqual(novaui.effects_since(mark), [])
        self.assertTrue(b.IsShow())

    def test_the_option_buttons_make_each_window_once_through_its_factory_and_show_it(self):
        legacy, novaui, a, b = self.menus()
        for child, what, attribute, module in (("system_option_button", "system_options", "systemOptionDlg", "nui_system_options"),
                                               ("game_option_button", "game_options", "gameOptionDlg", "nui_game_options")):
            with self.subTest(button=what):
                a.OpenDialog()
                b.OpenDialog()
                self.same(legacy, novaui, a.GetChild(child).click, lambda: fire(b, "act", what, 0), what)
                legacy_window, novaui_window = getattr(a, attribute), getattr(b, attribute)
                self.assertEqual(type(legacy_window).__name__, "OptionDialog")
                self.assertNotEqual(type(legacy_window).__module__, module, "flags off: the legacy window")
                self.assertEqual(type(novaui_window).__module__, module, "its own flag on: the NovaUI window")
                self.assertTrue(legacy_window.IsShow() and novaui_window.IsShow())
                self.assertFalse(a.IsShow() or b.IsShow())
                legacy_window.Hide()
                novaui_window.Hide()
                a.OpenDialog()
                b.OpenDialog()
                a.GetChild(child).click()
                fire(b, "act", what, 0)
                self.assertIs(getattr(a, attribute), legacy_window, "made once")
                self.assertIs(getattr(b, attribute), novaui_window)

    def test_the_legacy_and_the_novaui_menu_each_make_what_the_option_flags_ask_for(self):
        for windows, expected in (("+system-menu", ("uiSystemOption", "uiGameOption")),
                                  ("+system-menu,+system-options", ("nui_system_options", "uiGameOption")),
                                  ("+system-options,+game-options", ("nui_system_options", "nui_game_options"))):
            world = World(True, windows)
            with world:
                menu = world.make_menu()
                menu.OpenDialog()
                for child, what in (("system_option_button", "system_options"), ("game_option_button", "game_options")):
                    if getattr(type(menu), "NUI_FACADE", False):
                        fire(menu, "act", what, 0)
                    else:
                        with quiet():
                            menu.GetChild(child).click()
                    menu.OpenDialog()
                made = (type(menu.systemOptionDlg).__module__, type(menu.gameOptionDlg).__module__)
                self.assertEqual(made, expected, windows)

    def test_block_and_pk_callbacks_reach_the_game_options_through_the_menu(self):
        legacy, novaui, a, b = self.menus()
        for world, menu in ((legacy, a), (novaui, b)):
            with self.subTest(world="novaui" if world.nui_on else "legacy"):
                menu.OnBlockMode(9)
                self.assertEqual(world.m("uiGameOption").blockMode, 9, "before the game options exist")
                menu.OpenDialog()
                if world.nui_on:
                    fire(menu, "act", "game_options", 0)
                else:
                    with quiet():
                        menu.GetChild("game_option_button").click()
                options = menu.gameOptionDlg
                menu.OnBlockMode(5)
                self.assertEqual(world.m("uiGameOption").blockMode, 5)
                world.game.pk_mode = P["PK_MODE_FREE"]
                menu.OnChangePKMode()
                if world.nui_on:
                    self.assertEqual((board(options).get("block"), board(options).get("pk_mode")), (5, P["PK_MODE_FREE"]))
                    self.assertEqual(board(options).get("blocked"), [True, False, True, False, False, False])
                else:
                    self.assertTrue(options.pvpModeButtonDict[P["PK_MODE_FREE"]].down)
                    self.assertEqual([button.down for button in options.blockButtonList], [True, False, True, False, False, False])

    def test_escape_and_the_exit_key_close_the_menu_in_its_legacy_place(self):
        legacy, novaui, a, b = self.menus()
        b.OpenDialog()
        proxy = b.escapeProxy._window
        self.assertEqual(proxy.layer, "UI", "the legacy menu's layer")
        self.assertTrue(proxy.IsShow())
        self.assertIs(proxy.OnPressEscapeKey(), True)
        self.assertFalse(b.IsShow())
        self.assertFalse(proxy.IsShow(), "the proxy hides with the menu")
        b.OpenDialog()
        self.assertIs(proxy.OnPressExitKey(), True)
        self.assertFalse(b.IsShow())
        a.OpenDialog()
        self.assertIs(a.OnPressEscapeKey(), True)
        self.assertFalse(a.IsShow())
        for menu in (a, b):
            menu.OpenDialog()
            self.assertIs(menu.OnPressExitKey(), True)
            self.assertFalse(menu.IsShow())

    def test_toggle_opens_and_closes_as_the_interface_does(self):
        legacy, novaui, a, b = self.menus()
        for menu in (a, b):
            for _ in range(2):
                if not menu.IsShow():
                    menu.OpenDialog()
                    menu.SetTop()
                else:
                    menu.Close()
            self.assertFalse(menu.IsShow())
        b.OpenDialog()
        b.SetTop()
        self.assertEqual(board(b).calls.count(("bring_to_front",)), 1)
        self.assertEqual(board(b).placement, ("center",), "centered, as legacy's uiscript")
        self.assertEqual(board(b).get("show_mall"), True)

    def test_destroy_destroys_the_option_windows_it_made_and_its_parts(self):
        legacy, novaui, b = (None, None, None)
        world = World(True)
        with world:
            b = world.make_menu()
            b.OpenDialog()
            fire(b, "act", "system_options", 0)
            b.OpenDialog()
            fire(b, "act", "game_options", 0)
            options, game_options = b.systemOptionDlg, b.gameOptionDlg
            b.Destroy()
            self.assertIsNone(b.systemOptionDlg)
            self.assertIsNone(b.gameOptionDlg)
            self.assertFalse(options.nui_ready() or game_options.nui_ready(), "both destroyed")
            self.assertIsNone(b.escapeProxy)
            self.assertEqual(world.documents(), [], "no document left")
            self.assertIsNone(world.m("nui_hud").current("system-menu"))


# --- the system options and the music list (spec 6.2, 6.3) ---------------------------------------------

class SystemOptions(Pair):
    windows = "+sys,+dialogs"

    def setup_state(self, game):
        game.settings.update({"sound_volume": 0.75, "music_volume": 0.5, "fog_level": 1})
        game.software_tiling = False

    def pair(self):
        legacy, novaui = self.worlds()
        a, b = legacy.make_options(), novaui.make_options()
        self.assertEqual(type(a).__module__, "uiSystemOption")
        self.assertEqual(type(b).__module__, "nui_system_options")
        a.Show()
        b.Show()
        return legacy, novaui, a, b

    def test_each_show_fills_the_model_from_the_getters_as_legacys_controls_show_them(self):
        legacy, novaui, a, b = self.pair()
        model = board(b).model
        self.assertEqual((model["sound_volume"], model["music_volume"]), (75, 50))
        self.assertAlmostEqual(a.ctrlSoundVolume.GetSliderPos(), 0.75)
        self.assertAlmostEqual(a.ctrlMusicVolume.GetSliderPos(), 0.5)
        self.assertEqual(model["fog"], 1)
        self.assertEqual([button.down for button in a.fogModeButtonList], [False, True, False])
        self.assertEqual(model["camera"], 0)
        self.assertEqual([button.down for button in a.cameraModeButtonList], [True, False])
        self.assertEqual(model["tiling"], 1, "GPU: the current tiling")
        self.assertEqual([button.down for button in a.tilingModeButtonList], [False, True])
        self.assertEqual(model["music_file"], "MUSIC_METIN2_DEFAULT_THEMA", "the default theme's name (localeInfo)")
        self.assertEqual(a.selectMusicFile.text, "MUSIC_METIN2_DEFAULT_THEMA")
        self.assertIs(model["interface"], True)
        self.assertEqual(board(b).placement, ("center",))
        novaui.musicInfo.fieldMusic = "another_way_with_a_very_long_name.mp3"
        b.Hide()
        b.Show()
        self.assertEqual(board(b).model["music_file"], "another_way_with_a_very_l", "the first 25 characters")
        self.assertEqual(novaui.game.dbg.errors, [])

    def test_the_sliders_make_legacys_calls_and_opening_the_window_writes_nothing(self):
        legacy, novaui, a, b = self.pair()
        self.assertEqual(novaui.effects(), [], "a show only reads")
        mark = novaui.mark()
        fire(b, "sound", 75)
        fire(b, "music", 50)
        self.assertEqual(novaui.effects_since(mark), [], "the model's own value coming back is no move")
        calls = self.same(legacy, novaui, lambda: a.ctrlSoundVolume.drag_to(0.10), lambda: fire(b, "sound", 10), "sound")
        self.assertEqual([name for name, _ in calls], ["snd.SetSoundVolume", "systemSetting.SetSoundVolume"])
        self.assertAlmostEqual(calls[0][1][0], 0.10, delta=0.01)
        self.assertEqual(board(b).get("sound_volume"), 10)
        calls = self.same(legacy, novaui, lambda: a.ctrlMusicVolume.drag_to(0.20), lambda: fire(b, "music", 20), "music")
        self.assertEqual([name for name, _ in calls], ["snd.SetMusicVolume", "systemSetting.SetMusicVolume"])
        self.assertAlmostEqual(novaui.game.settings["music_volume"], 0.20)
        for world in (legacy, novaui):
            self.assertNotIn(("systemSetting.SaveConfig", ()), world.effects(), "saved at exit, as legacy")

    def test_the_camera_fog_and_tiling_choices_make_legacys_calls(self):
        legacy, novaui, a, b = self.pair()
        steps = ((lambda: a.GetChild("camera_long").click(), ("choose", "camera", 1, 0)),
                 (lambda: a.GetChild("camera_short").click(), ("choose", "camera", 0, 0)),
                 (lambda: a.GetChild("fog_level0").click(), ("choose", "fog", 0, 0)),
                 (lambda: a.GetChild("fog_level1").click(), ("choose", "fog", 1, 0)),
                 (lambda: a.GetChild("fog_level2").click(), ("choose", "fog", 2, 0)),
                 (lambda: a.GetChild("tiling_cpu").click(), ("choose", "tiling", 0, 0)),
                 (lambda: a.GetChild("tiling_gpu").click(), ("choose", "tiling", 1, 0)))
        expected = ([("app.SetCameraMaxDistance", (3500.0,))], [("app.SetCameraMaxDistance", (2500.0,))],
                    [("systemSetting.SetFogLevel", (0,))], [("systemSetting.SetFogLevel", (1,))],
                    [("systemSetting.SetFogLevel", (2,))],
                    [("chat.AppendChat", (1, "SYSTEM_OPTION_CPU_TILING_%d" % i)) for i in (1, 2, 3)],
                    [("chat.AppendChat", (1, "SYSTEM_OPTION_GPU_TILING_%d" % i)) for i in (1, 2, 3)])
        for (legacy_step, event), calls in zip(steps, expected):
            with self.subTest(event=event):
                self.assertEqual(self.same(legacy, novaui, legacy_step, lambda: fire(b, *event), str(event)), calls)
                self.assertEqual(board(b).get(event[1]), event[2], "the choice follows")
        self.assertEqual(legacy.m("constInfo").GET_CAMERA_MAX_DISTANCE_INDEX(),
                         novaui.m("constInfo").GET_CAMERA_MAX_DISTANCE_INDEX())
        self.assertEqual(novaui.game.settings["fog_level"], 2)

    def test_apply_tiling_switches_and_leaves_the_game_and_close_puts_the_choice_back(self):
        for choice, cpu in ((0, 1), (1, 0)):
            with self.subTest(choice=choice):
                legacy, novaui, a, b = self.pair()
                child = ("tiling_cpu", "tiling_gpu")[choice]
                self.same(legacy, novaui, a.GetChild(child).click, lambda: fire(b, "choose", "tiling", choice, 0), "choice")
                calls = self.same(legacy, novaui, a.GetChild("tiling_apply").click,
                                  lambda: fire(b, "act", "tiling_apply", 0), "apply")
                self.assertEqual(calls, [("chat.AppendChat", (1, "SYSTEM_OPTION_TILING_EXIT")),
                                         ("background.EnableSoftwareTiling", (cpu,)), ("net.ExitGame", ())])
        legacy, novaui, a, b = self.pair()
        a.GetChild("tiling_cpu").click()
        fire(b, "choose", "tiling", 0, 0)
        self.same(legacy, novaui, a.Close, b.Close, "close")
        self.assertEqual((a.tilingMode, b.tilingMode), (1, 1), "back to the tiling in effect (GPU)")
        b.Show()
        self.assertEqual(board(b).get("tiling"), 1)
        self.assertFalse(a.IsShow() and False)

    def test_escape_closes_in_its_legacy_place(self):
        legacy, novaui, a, b = self.pair()
        proxy = b.escapeProxy._window
        self.assertTrue(proxy.IsShow())
        self.assertIs(proxy.OnPressEscapeKey(), True)
        self.assertFalse(b.IsShow())
        self.assertIs(proxy.OnPressExitKey(), False, "the exit key goes on, as legacy has no OnPressExitKey")
        self.assertIs(a.OnPressEscapeKey(), True)
        self.assertFalse(a.IsShow())
        b.Show()
        fire(b, "act", "close", 0)
        self.assertFalse(b.IsShow())

    def test_a_moved_window_keeps_its_place_across_a_hide_and_a_centered_one_is_centered_again(self):
        legacy, novaui, a, b = self.pair()
        state = novaui.game.state
        doc = board(b).DOCUMENT
        state.boxes[(doc, "")] = (650.0, 200.0, 300.0, 500.0)   # centered on 1600 x 900
        b.Hide()
        b.Show()
        self.assertEqual(board(b).placement, ("center",))
        state.boxes[(doc, "")] = (40.0, 30.0, 300.0, 500.0)     # dragged
        b.Hide()
        b.Show()
        self.assertEqual(board(b).placement, ("position", 40.0, 30.0, (0.0, 0.0)))
        novaui.game.modules["nui"].set_scale_percent(150)
        self.assertEqual(board(b).placement, ("center",), "a scale change centers it again")

    def test_legacys_slider_events_read_the_boards_value(self):
        legacy, novaui, a, b = self.pair()
        board(b).model["sound_volume"] = 30
        mark = novaui.mark()
        b.OnChangeSoundVolume()
        self.assertEqual([name for name, _ in novaui.effects_since(mark)], ["snd.SetSoundVolume", "systemSetting.SetSoundVolume"])
        self.assertIs(b.OnCloseInputDialog(), True)
        self.assertIs(b.OnCloseQuestionDialog(), True)
        self.assertIsNone(b.OnChangeShadowQuality())


class MusicList(Pair):
    def pair(self):
        legacy, novaui = self.worlds()
        a, b = legacy.make_options(), novaui.make_options()
        a.Show()
        b.Show()
        a.GetChild("bgm_button").click()
        fire(b, "act", "change_music", 0)
        return legacy, novaui, a, b, a.musicListDlg, b.musicListDlg

    def test_change_opens_the_list_with_the_default_theme_first_then_every_mp3(self):
        legacy, novaui, a, b, la, lb = self.pair()
        self.assertEqual(type(lb).__module__, "nui_system_options")
        self.assertTrue(la.IsShow() and lb.IsShow())
        expected = ["MUSIC_METIN2_DEFAULT_THEMA"] + novaui.game.file_lists["BGM/*.mp3"]
        self.assertEqual(la.fileListBox.texts(), expected)
        self.assertEqual([entry["name"] for entry in board(lb).model["files"]], expected)
        self.assertEqual(board(lb).model["files"][1]["label"], "a_rhapsody_of_war.mp", "the first 20 characters")
        self.assertEqual(board(lb).model["selected"], -1)
        self.assertEqual(board(lb).placement, ("center",))
        self.assertIn(("bring_to_front",), board(lb).calls, "raised at each open")

    def test_ok_plays_the_selected_file_through_the_options_and_saves_it(self):
        legacy, novaui, a, b, la, lb = self.pair()
        for world in (legacy, novaui):
            world.musicInfo.fieldMusic = "M2BG.mp3"
        la.fileListBox.select(2)
        fire(lb, "pick", 2, 0)
        calls = self.same(legacy, novaui, la.okButton.click, lambda: fire(lb, "act", "ok", 0), "ok")
        self.assertEqual(calls, [("snd.FadeOutMusic", ("BGM/M2BG.mp3",)),
                                 ("musicInfo.SaveLastPlayFieldMusic", ("another_way.mp3",)),
                                 ("snd.FadeInMusic", ("BGM/another_way.mp3",))])
        for world in (legacy, novaui):
            self.assertEqual(world.musicInfo.fieldMusic, "another_way.mp3")
            self.assertEqual(world.game.files["BGM/lastplay.inf"], "another_way.mp3")
        self.assertFalse(la.IsShow() or lb.IsShow(), "hidden after OK")
        self.assertEqual(a.selectMusicFile.text, "another_way.mp3")
        self.assertEqual(board(b).get("music_file"), "another_way.mp3")

    def test_the_default_entry_plays_the_default_theme(self):
        legacy, novaui, a, b, la, lb = self.pair()
        for world in (legacy, novaui):
            world.musicInfo.fieldMusic = "blacksea.mp3"
        la.fileListBox.select(0)
        fire(lb, "pick", 0, 0)
        calls = self.same(legacy, novaui, la.okButton.click, lambda: fire(lb, "act", "ok", 0), "default")
        self.assertEqual(calls[-1], ("snd.FadeInMusic", ("BGM/M2BG.mp3",)))
        self.assertEqual(novaui.musicInfo.fieldMusic, "M2BG.mp3")

    def test_ok_without_a_selection_shows_the_popup_and_keeps_the_list(self):
        legacy, novaui, a, b, la, lb = self.pair()
        self.same(legacy, novaui, la.okButton.click, lambda: fire(lb, "act", "ok", 0), "ok without one")
        self.assertTrue(la.IsShow() and lb.IsShow())
        self.assertEqual(la.popupDialog.textLine.text, "MUSIC_NOT_SELECT_MUSIC")
        popup = lb.popupDialog
        self.assertEqual(type(popup).__module__, "nui_dialog_message", "the kit's popup (dialogs on)")
        self.assertTrue(popup.IsShow())
        self.assertEqual(popup._text, "MUSIC_NOT_SELECT_MUSIC")
        lb.Close()
        self.assertFalse(popup.IsShow(), "the popup goes with the list, as legacy's")

    def test_refresh_reads_the_folder_again_and_cancel_hides_with_no_call(self):
        legacy, novaui, a, b, la, lb = self.pair()
        fire(lb, "pick", 3, 0)
        for world in (legacy, novaui):
            world.game.file_lists["BGM/*.mp3"] = ["only.mp3"]
        self.same(legacy, novaui, la.refreshButton.click, lambda: fire(lb, "act", "refresh", 0), "refresh")
        self.assertEqual(la.fileListBox.texts(), ["MUSIC_METIN2_DEFAULT_THEMA", "only.mp3"])
        self.assertEqual([entry["name"] for entry in board(lb).model["files"]], ["MUSIC_METIN2_DEFAULT_THEMA", "only.mp3"])
        self.assertEqual(board(lb).model["selected"], -1)
        calls = self.same(legacy, novaui, la.cancelButton.click, lambda: fire(lb, "act", "cancel", 0), "cancel")
        self.assertEqual(calls, [])
        self.assertFalse(la.IsShow() or lb.IsShow())

    def test_escape_and_the_close_button_hide_the_list(self):
        legacy, novaui, a, b, la, lb = self.pair()
        proxy = lb.escapeProxy._window
        self.assertTrue(proxy.IsShow())
        self.assertIs(proxy.OnPressEscapeKey(), True)
        self.assertFalse(lb.IsShow())
        b.Show()
        fire(b, "act", "change_music", 0)
        self.assertTrue(lb.IsShow())
        board(lb).fire("act", "cancel", 0)
        self.assertFalse(lb.IsShow())
        self.assertIs(la.OnPressEscapeKey(), True)

    def test_the_list_is_made_once_and_keeps_its_files_and_selection_across_opens(self):
        legacy, novaui, a, b, la, lb = self.pair()
        fire(lb, "pick", 4, 0)
        fire(lb, "act", "cancel", 0)
        fire(b, "act", "change_music", 0)
        self.assertIs(b.musicListDlg, lb)
        self.assertEqual(board(lb).model["selected"], 4)
        b.Destroy()
        self.assertFalse(lb.nui_ready(), "the options destroy their list")


class InterfaceSection(unittest.TestCase):
    """The Interface section has no legacy original: what each choice calls
    (spec 6.2 and D12)."""

    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)
        self.state = self.world.game.state
        self.options = self.world.make_options()
        self.options.Show()

    def model(self):
        return board(self.options).model

    def test_the_section_shows_every_theme_the_scale_choices_and_reduced_motion(self):
        model = self.model()
        self.assertEqual(model["themes"], [{"id": "modern-dark", "label": "@ui.THEME_MODERN_DARK"},
                                           {"id": "modern-light", "label": "@ui.THEME_MODERN_LIGHT"},
                                           {"id": "classic", "label": "@ui.THEME_CLASSIC"}])
        self.assertEqual(model["theme"], "modern-dark")
        self.assertEqual([choice["id"] for choice in model["scales"]], ["auto", "75", "100", "125", "150", "175", "200"])
        self.assertEqual(model["scales"][0], {"id": "auto", "percent": 0, "label": "@ui.OPTION_UI_SCALE_AUTO"})
        self.assertEqual(model["scales"][2]["label"], "100%")
        self.assertEqual((model["scale"], model["auto_percent"]), (0, 88))
        self.assertIs(model["reduced_motion"], False)

    def test_a_theme_choice_applies_it_and_the_choice_follows(self):
        board(self.options).fire("choose_theme", "classic", 0)
        self.assertEqual(self.state.appearance, [("set_theme", "classic")])
        self.assertEqual(self.model()["theme"], "classic")
        board(self.options).fire("choose_theme", "modern-light", 1)
        self.assertEqual(self.state.appearance, [("set_theme", "classic")], "left button only")
        board(self.options).fire("choose_theme", "no-such-theme", 0)
        self.assertEqual(self.world.game.dbg.errors[-1], "nui_system_options: no theme 'no-such-theme'")

    def test_a_scale_choice_applies_it_centers_the_window_and_refreshes_the_choices(self):
        board(self.options).set_position(10, 10)
        board(self.options).fire("choose_scale", 150, 0)
        self.assertEqual(self.state.appearance, [("set_scale_percent", 150)])
        self.assertEqual(self.model()["scale"], 150)
        self.assertEqual(board(self.options).placement, ("center",))
        board(self.options).fire("choose_scale", 0, 0)
        self.assertEqual(self.state.appearance[-1], ("set_scale_percent", 0))
        self.assertEqual(self.model()["scale"], 0, "automatic")

    def test_a_saved_percent_outside_the_choices_is_one_more_choice_until_another_is_chosen(self):
        self.state.scale_percent = 110
        self.options.Hide()
        self.options.Show()
        self.assertEqual(self.model()["scales"][-1], {"id": "custom", "percent": 110, "label": "110%"})
        self.assertEqual(self.model()["scale"], 110)
        board(self.options).fire("choose_scale", 100, 0)
        self.assertEqual([choice["id"] for choice in self.model()["scales"]][-1], "200", "the custom choice went")

    def test_reduced_motion_applies_and_the_toggles_echo_does_nothing(self):
        board(self.options).fire("motion", False)
        self.assertEqual(self.state.appearance, [], "the model's own value coming back")
        board(self.options).fire("motion", True)
        self.assertEqual(self.state.appearance, [("set_reduced_motion", True)])
        self.assertIs(self.model()["reduced_motion"], True)
        self.options.Hide()
        self.options.Show()
        self.assertIs(self.model()["reduced_motion"], True, "read back at the next show")

    def test_a_left_press_on_the_toggle_flips_reduced_motion_and_the_checkbox_echo_does_nothing(self):
        # RmlUi makes no click in a document that takes no focus, so the
        # toggle's label never flips its checkbox: the press flips the setting.
        board(self.options).fire("flip_motion", 1)
        self.assertEqual(self.state.appearance, [], "left button only")
        board(self.options).fire("flip_motion", 0)
        self.assertEqual(self.state.appearance, [("set_reduced_motion", True)])
        self.assertIs(self.model()["reduced_motion"], True)
        board(self.options).fire("motion", True)
        self.assertEqual(self.state.appearance, [("set_reduced_motion", True)], "the checkbox following the model")
        board(self.options).fire("flip_motion", 0)
        self.assertEqual(self.state.appearance[-1], ("set_reduced_motion", False))
        self.assertIs(self.model()["reduced_motion"], False)

    def test_the_interface_section_calls_no_legacy_setter_itself(self):
        mark = self.world.mark()
        for event in (("choose_theme", "classic", 0), ("choose_scale", 125, 0), ("motion", True)):
            board(self.options).fire(*event)
        self.assertEqual(self.world.effects_since(mark), [], "nui.py saves the UI_* keys")


# --- the game options (spec 6.4) ---------------------------------------------------------------

BLOCK_CHILDREN = ("block_exchange_button", "block_party_button", "block_guild_button", "block_whisper_button",
                  "block_friend_button", "block_party_request_button")


class GameOptions(Pair):
    def setup_state(self, game):
        game.status[P["LEVEL"]] = 105
        game.pk_mode = P["PK_MODE_PEACE"]

    def pair(self, setup=None):
        legacy, novaui = self.worlds(setup)
        a, b = legacy.make_game_options(), novaui.make_game_options()
        self.assertEqual(type(a).__module__, "uiGameOption")
        self.assertEqual(type(b).__module__, "nui_game_options")
        a.Show()
        b.Show()
        return legacy, novaui, a, b

    def test_each_show_fills_the_model_from_legacys_sources(self):
        def setup(game):
            game.view_chat = False
            game.settings["show_damage"] = False
        legacy, novaui, a, b = self.pair(setup)
        model = board(b).model
        self.assertEqual(model, {"name_color": 0, "target_board": 1, "pk_mode": 0, "block": 0, "blocked": [False] * 6,
                                 "view_chat": False, "always_show_name": True, "show_damage": False, "sales_text": True})
        self.assertEqual([button.down for button in a.viewChatButtonList], [False, True])
        self.assertEqual([button.down for button in a.showDamageButtonList], [False, True])
        self.assertTrue(a.pvpModeButtonDict[P["PK_MODE_PEACE"]].down, "peace at the first show, as legacy's load")
        self.assertEqual(novaui.effects(), [])

    def test_the_name_color_and_target_board_choices_set_constinfo_as_legacy(self):
        legacy, novaui, a, b = self.pair()
        calls = self.same(legacy, novaui, a.GetChild("name_color_empire").click,
                          lambda: fire(b, "choose", "name_color", 1, 0), "kingdom color")
        self.assertEqual(calls, [("chrmgr.SetEmpireNameMode", (1,))])
        self.same(legacy, novaui, a.GetChild("name_color_normal").click, lambda: fire(b, "choose", "name_color", 0, 0), "normal")
        # Legacy's handler names are swapped, its values are not: "no view" sets 0.
        self.same(legacy, novaui, a.GetChild("target_board_no_view").click,
                  lambda: fire(b, "choose", "target_board", 0, 0), "target board off")
        for world in (legacy, novaui):
            self.assertEqual(world.m("constInfo").GET_VIEW_OTHER_EMPIRE_PLAYER_TARGET_BOARD(), 0)
            self.assertEqual(world.m("constInfo").GET_CHRNAME_COLOR_INDEX(), 0)
        self.same(legacy, novaui, a.GetChild("target_board_view").click,
                  lambda: fire(b, "choose", "target_board", 1, 0), "target board on")
        self.assertEqual(novaui.m("constInfo").GET_VIEW_OTHER_EMPIRE_PLAYER_TARGET_BOARD(), 1)
        self.assertEqual(board(b).get("target_board"), 1)

    def test_the_pvp_choices_send_pkmode_and_show_the_servers_mode(self):
        legacy, novaui, a, b = self.pair()
        for child, mode in (("pvp_free", 2), ("pvp_revenge", 1), ("pvp_peace", 0)):
            with self.subTest(mode=mode):
                calls = self.same(legacy, novaui, a.GetChild(child).click, lambda: fire(b, "choose", "pk", mode, 0), child)
                self.assertEqual(calls, [("net.SendChatPacket", ("/pkmode %d" % mode, 0))])
                self.assertEqual(board(b).get("pk_mode"), P["PK_MODE_PEACE"], "the server's mode until it answers")
        for world in (legacy, novaui):
            world.game.pk_mode = 2
        a.OnChangePKMode()
        b.OnChangePKMode()
        self.assertEqual(board(b).get("pk_mode"), 2)
        self.assertTrue(a.pvpModeButtonDict[2].down)

    def test_guild_mode_without_a_guild_and_a_protected_level_send_nothing(self):
        legacy, novaui, a, b = self.pair()
        calls = self.same(legacy, novaui, a.GetChild("pvp_guild").click, lambda: fire(b, "choose", "pk", 4, 0), "no guild")
        self.assertEqual(calls, [("chat.AppendChat", (1, "OPTION_PVPMODE_CANNOT_SET_GUILD_MODE"))])
        for world in (legacy, novaui):
            world.game.guild_id = 7
        calls = self.same(legacy, novaui, a.GetChild("pvp_guild").click, lambda: fire(b, "choose", "pk", 4, 0), "guild")
        self.assertEqual(calls, [("net.SendChatPacket", ("/pkmode 4", 0))])
        for world in (legacy, novaui):
            world.game.status[P["LEVEL"]] = 10
            world.game.pk_mode = 2
        calls = self.same(legacy, novaui, a.GetChild("pvp_free").click, lambda: fire(b, "choose", "pk", 2, 0), "protected")
        self.assertEqual(calls, [("chat.AppendChat", (1, "Level 15 needed"))])
        self.assertEqual(board(b).get("pk_mode"), P["PK_MODE_PEACE"])
        self.assertTrue(a.pvpModeButtonDict[P["PK_MODE_PEACE"]].down)

    def test_a_block_toggle_asks_for_its_bit_flipped_and_shows_the_servers_mask(self):
        legacy, novaui, a, b = self.pair()
        for index, child in enumerate(BLOCK_CHILDREN):
            with self.subTest(block=child):
                calls = self.same(legacy, novaui, a.GetChild(child).click, lambda: fire(b, "block", index, 0), child)
                self.assertEqual(calls, [("net.SendChatPacket", ("/setblockmode %d" % (1 << index),))])
                self.assertEqual(board(b).get("blocked"), [False] * 6, "the server's mask until it answers")
        for world, dialog in ((legacy, a), (novaui, b)):
            dialog.OnBlockMode(0b101001)
            self.assertEqual(world.m("uiGameOption").blockMode, 0b101001, "the shared module state")
        self.assertEqual(board(b).get("blocked"), [True, False, False, True, False, True])
        self.assertEqual([button.down for button in a.blockButtonList], [True, False, False, True, False, True])
        calls = self.same(legacy, novaui, a.GetChild(BLOCK_CHILDREN[0]).click, lambda: fire(b, "block", 0, 0), "unblock")
        self.assertEqual(calls, [("net.SendChatPacket", ("/setblockmode %d" % 0b101000,))])

    def test_the_four_flags_call_systemsetting_and_the_shop_names_update_the_signs(self):
        legacy, novaui, a, b = self.pair()
        steps = (("view_chat_off_button", ("view_chat", 0), [("systemSetting.SetViewChatFlag", (0,))]),
                 ("view_chat_on_button", ("view_chat", 1), [("systemSetting.SetViewChatFlag", (1,))]),
                 ("always_show_name_off_button", ("always_show_name", 0), [("systemSetting.SetAlwaysShowNameFlag", (False,))]),
                 ("always_show_name_on_button", ("always_show_name", 1), [("systemSetting.SetAlwaysShowNameFlag", (True,))]),
                 ("show_damage_off_button", ("show_damage", 0), [("systemSetting.SetShowDamageFlag", (False,))]),
                 ("show_damage_on_button", ("show_damage", 1), [("systemSetting.SetShowDamageFlag", (True,))]),
                 ("salestext_off_button", ("sales_text", 0), [("systemSetting.SetShowSalesTextFlag", (False,))]),
                 ("salestext_on_button", ("sales_text", 1), [("systemSetting.SetShowSalesTextFlag", (True,)),
                                                              ("uiPrivateShopBuilder.UpdateADBoard", ())]))
        for child, (what, value), expected in steps:
            with self.subTest(button=child):
                calls = self.same(legacy, novaui, a.GetChild(child).click, lambda: fire(b, "choose", what, value, 0), child)
                self.assertEqual(calls, expected)
                self.assertIs(board(b).get(what), bool(value), "the model follows the setting")
        for world in (legacy, novaui):
            self.assertEqual(world.m("uiGameOption").viewChatMode, 1)

    def test_close_escape_and_a_moved_place(self):
        legacy, novaui, a, b = self.pair()
        proxy = b.escapeProxy._window
        self.assertIs(proxy.OnPressEscapeKey(), True)
        self.assertFalse(b.IsShow())
        b.Show()
        board(b).fire("close", 0)
        self.assertFalse(b.IsShow())
        self.assertIs(a.OnPressEscapeKey(), True)
        self.assertFalse(a.IsShow())
        b.Show()
        novaui.game.state.boxes[(board(b).DOCUMENT, "")] = (20.0, 40.0, 300.0, 283.0)
        b.Hide()
        b.Show()
        self.assertEqual(board(b).placement, ("position", 20.0, 40.0, (0.0, 0.0)))


# --- the restart dialog (spec 6.5) ------------------------------------------------------------------

class Restart(Pair):
    def test_both_buttons_send_legacys_commands_and_leave_the_dialog_open(self):
        legacy, novaui = self.worlds()
        a, b = legacy.make_restart(), novaui.make_restart()
        self.assertEqual(type(b).__module__, "nui_restart")
        self.assertIs(b.LoadDialog(), 1)
        for dialog in (a, b):
            dialog.OpenDialog()
            dialog.SetTop()
        for child, what in (("restart_here_button", "here"), ("restart_town_button", "town")):
            calls = self.same(legacy, novaui, a.GetChild(child).click, lambda: fire(b, "act", what, 0), what)
            self.assertEqual(calls, [("net.SendChatPacket", ("/restart_%s" % what,))])
            self.assertTrue(a.IsShow() and b.IsShow(), "the server closes it")
        self.assertEqual(board(b).placement, None, "legacy's place, from the sheet")
        self.assertIs(b.Close(), True)
        self.assertFalse(b.IsShow())
        self.assertIsNone(board(b))

    def test_escape_and_the_exit_key_are_kept_and_do_nothing(self):
        world = World(True)
        with world:
            dialog = world.make_restart()
            dialog.OpenDialog()
            proxy = dialog.escapeProxy._window
            mark = world.mark()
            self.assertIs(proxy.OnPressEscapeKey(), True)
            self.assertIs(proxy.OnPressExitKey(), True)
            self.assertTrue(dialog.IsShow())
            self.assertEqual(world.effects_since(mark), [])
            self.assertIs(dialog.OnPressEscapeKey(), True)
            self.assertIs(dialog.OnPressExitKey(), True)
            dialog.Destroy()
            self.assertIsNone(dialog.escapeProxy)
            self.assertEqual(world.documents(), [])


# --- the help (spec 6.6) ------------------------------------------------------------------------------

class Help(Pair):
    def test_open_shows_a_modal_and_every_close_runs_the_interfaces_close_event(self):
        legacy, novaui = self.worlds()
        a, b = legacy.make_help(), novaui.make_help()
        self.assertEqual(type(b).__module__, "nui_help")
        nui = novaui.game.modules["nui"]
        closes = (("H", lambda: a.OnKeyDown(legacy.game.modules["app"].DIK_H), lambda: board(b).key("", 19)),
                  ("Escape", a.OnPressEscapeKey, lambda: board(b).key("", nui.KEY_ESCAPE)),
                  ("exit key", a.OnPressExitKey, lambda: b.escapeProxy._window.OnPressExitKey()),
                  ("close button", a.btnClose.Click, lambda: fire(b, "act", "close", 0)))
        for what, legacy_close, novaui_close in closes:
            with self.subTest(close=what):
                a.Open()
                b.Open()
                self.assertTrue(board(b).visible and board(b).modal, "shown as a modal")
                self.assertEqual(b.escapeProxy._window.layer, "TOP_MOST")
                self.assertTrue(b.escapeProxy.is_shown())
                calls = self.same(legacy, novaui, legacy_close, novaui_close, what)
                self.assertEqual(calls, [("interface.CloseHelpWindow", ())])
                a.Close()
                b.Close()
                self.assertFalse(b.IsShow())
                self.assertIsNone(board(b), "the document went with the close")

    def test_the_keydown_handler_keeps_only_escape_and_h_while_shown(self):
        world = World(True)
        with world:
            window = world.make_help()
            window.Open()
            help_board = board(window)
            self.assertFalse(help_board.key("", 73), "another key goes on")
            self.assertTrue(help_board.key("", 19), "H is kept")
            self.assertEqual(window.OnKeyDown(world.game.modules["app"].DIK_H), True)
            window.SetCloseEvent(0)
            self.assertIs(window.OnPressEscapeKey(), True, "no close event: kept anyway, as legacy")
            window.Destroy()
            self.assertEqual(window.eventClose, 0)
            self.assertEqual(world.documents(), [])


# --- the point reset (spec 6.7) --------------------------------------------------------------------------

class PointReset(Pair):
    def pair(self):
        legacy, novaui = self.worlds()
        a, b = legacy.make_point_reset(), novaui.make_point_reset()
        self.assertEqual(type(a).__module__, "uiPointReset")
        self.assertEqual(type(b).__module__, "nui_point_reset")
        return legacy, novaui, a, b

    def test_the_question_then_the_confirmation_then_pointreset(self):
        legacy, novaui, a, b = self.pair()
        a.Show()
        a.SetTop()
        b.Show()
        b.SetTop()
        kit = novaui.kit_window()
        self.assertEqual(kit.model["lines"], ["POINT_RESET_QUESTION_1", "POINT_RESET_QUESTION_2"])
        self.assertEqual(kit.model["warn_line"], -1)
        self.assertTrue(b.IsShow())
        self.same(legacy, novaui, a.GetChild("accept").Click, lambda: kit.fire("accept"), "yes")
        self.assertTrue(a.ConfirmDialog.IsShow())
        self.assertEqual(a.ConfirmText.color, (1.0, 0.3, 0.3), "legacy's red line")
        self.assertEqual(kit.model["lines"], ["POINT_RESET_CONFIRM_1", "POINT_RESET_CONFIRM_2"])
        self.assertEqual(kit.model["warn_line"], 0, "the warning line")
        self.assertTrue(b.ConfirmDialog.IsShow())
        self.assertFalse(b.question.IsShow(), "one question at a time (D13)")
        calls = self.same(legacy, novaui, a.ConfirmAcceptButton.Click, lambda: kit.fire("accept"), "yes again")
        self.assertEqual(calls, [("net.SendChatPacket", ("/pointreset",))])
        self.assertFalse(a.IsShow() or a.ConfirmDialog.IsShow())
        self.assertFalse(b.IsShow())

    def test_no_and_escape_close_with_nothing_sent(self):
        legacy, novaui, a, b = self.pair()
        a.Show()
        b.Show()
        kit = novaui.kit_window()
        calls = self.same(legacy, novaui, a.GetChild("cancel").Click, lambda: kit.fire("cancel"), "no")
        self.assertEqual(calls, [])
        self.assertFalse(a.IsShow() or b.IsShow())
        b.Show()
        kit.fire("accept")
        self.assertTrue(b.ConfirmDialog.IsShow())
        self.assertTrue(kit.key("", novaui.game.modules["nui"].KEY_ESCAPE), "the kit's question closes on Escape")
        self.assertFalse(b.IsShow())
        b.Show()
        self.assertIs(b.OnPressEscapeKey(), True)
        self.assertFalse(b.IsShow())
        self.assertIs(a.OnPressEscapeKey(), True)

    def test_without_the_kits_facades_the_legacy_point_reset_is_made(self):
        world = World(True, "+point-reset")
        with world:
            dialog = world.make_point_reset()
            self.assertEqual(type(dialog).__module__, "uiPointReset", "dialogs off: legacy question dialogs")
            self.assertIn("nui_windows: point-reset: the document did not load; using the legacy window", world.game.dbg.errors)

    def test_destroy_lets_both_questions_go(self):
        world = World(True)
        with world:
            dialog = world.make_point_reset()
            dialog.Show()
            dialog.Destroy()
            self.assertIsNone(dialog.question)
            self.assertFalse(world.kit_window().visible)
            self.assertIsNone(world.m("nui_hud").current("point-reset"))


# --- fixtures, on demand, per-frame Python ---------------------------------------------------------------

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


BOARDS = (("nui_system_menu", "SystemMenuBoard", "system-menu", ()),
          ("nui_system_options", "OptionBoard", "system-options", ("custom-scale",)),
          ("nui_music_list", "MusicListBoard", "music-list", ("empty", "selected")),
          ("nui_game_options", "GameOptionsBoard", "game-options", ("blocked",)),
          ("nui_restart", "RestartBoard", "restart", ()),
          ("nui_help", "HelpBoard", "help", ()))


class Fixtures(unittest.TestCase):
    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)

    def test_each_boards_fixtures_hold_every_model_key_of_its_kind(self):
        for module, name, window, variants in BOARDS:
            board_class = getattr(self.world.m(module), name)
            with self.subTest(window=window):
                made = board_class(object())
                model = made.initial_model()
                for variant in (None,) + variants:
                    data = fixture(window, variant)
                    self.assertEqual(list(data), [board_class.MODEL], "%s %s" % (window, variant))
                    values = data[board_class.MODEL]
                    self.assertEqual(set(values), set(model), "%s %s: the fixture holds every model key" % (window, variant))
                    for key, value in values.items():
                        self.assertEqual(kind(value), kind(model[key]), "%s.%s" % (window, key))
                    self.assertTrue(made.set(**values) or not values)
                made.destroy()
        self.assertEqual(self.world.game.dbg.errors, [])

    def test_the_question_kinds_warning_fixture_matches_its_model(self):
        kit_window = self.world.m("nui_dialog_question").QuestionWindow(None)
        model = kit_window.initial_model()
        for variant in (None, "warning"):
            values = fixture("dialog-question", variant)["dialog_question"]
            self.assertEqual(set(values), set(model), variant)
        self.assertEqual(fixture("dialog-question", "warning")["dialog_question"]["warn_line"], 0)

    def test_the_options_model_keys_are_the_spec_table(self):
        options = self.world.make_options()
        self.assertEqual(set(options.nui_model()), {"sound_volume", "music_volume", "music_file", "camera", "fog", "tiling",
                                                    "interface", "themes", "theme", "scales", "scale", "auto_percent",
                                                    "reduced_motion"})
        game_options = self.world.make_game_options()
        self.assertEqual(set(game_options.nui_model()), {"name_color", "target_board", "pk_mode", "block", "blocked",
                                                         "view_chat", "always_show_name", "show_damage", "sales_text"})


class OnDemand(unittest.TestCase):
    """No document while hidden; the board made at Show and gone at Hide (D5)."""

    def test_every_window_holds_no_document_while_hidden(self):
        world = World(True)
        with world:
            menu = world.make_menu()
            facades = {"system-menu": (menu, menu.OpenDialog, menu.Close),
                       "restart": None, "help": None, "system-options": None, "game-options": None, "music-list": None}
            restart = world.make_restart()
            facades["restart"] = (restart, restart.OpenDialog, restart.Close)
            help_window = world.make_help()
            facades["help"] = (help_window, help_window.Open, help_window.Close)
            options = world.make_options()
            facades["system-options"] = (options, options.Show, options.Close)
            game_options = world.make_game_options()
            facades["game-options"] = (game_options, game_options.Show, game_options.Close)
            options.Show()
            fire(options, "act", "change_music", 0)
            music = options.musicListDlg
            music.Close()
            options.Close()
            facades["music-list"] = (music, music.Open, music.Close)
            self.assertEqual(world.documents(), [], "every constructor's probe left nothing")
            for key, (facade, show, hide) in facades.items():
                with self.subTest(window=key):
                    show()
                    self.assertEqual(len(world.documents()), 1, "one document while shown")
                    self.assertTrue(facade.IsShow())
                    hide()
                    self.assertEqual(world.documents(), [], "gone at the hide")
                    self.assertFalse(facade.IsShow())

    def test_hidden_windows_hold_no_document_in_nui_stats(self):
        world = World(True)
        with world:
            world.make_menu()
            world.make_restart()
            world.make_help()
            stats = world.game.modules["nuigame"].NuiStats()
            self.assertEqual(stats["documents"], [])


class Bands(unittest.TestCase):
    """D10: the system windows draw above the legacy UI layer; the help is a
    modal on a scrim, the others plain windows; D11: no focus but the help's
    body."""

    def test_no_wave3a_document_draws_below_the_legacy_ui_and_only_the_help_is_modal(self):
        world = World(True)
        with world:
            for module, name, window, _ in BOARDS:
                board_class = getattr(world.m(module), name)
                markup = read(os.path.join(WINDOWS, window, window + ".rml"))
                body = markup[markup.index("<body"):markup.index(">", markup.index("<body"))]
                with self.subTest(window=window):
                    self.assertNotIn("nui-below-legacy-ui", body)
                    self.assertEqual("nui-scrim" in body, window == "help")
                    self.assertEqual("nui-window" in body, window != "help")
                    self.assertIs(bool(board_class.MODAL), window == "help")
                    sheet = read(os.path.join(WINDOWS, window, window + ".rcss"))
                    if window == "help":
                        self.assertIn("focus: none", sheet.split(".help button")[1].split("}")[0], "its button")
                    else:
                        body_rule = sheet.split("body.%s" % window)[1].split("}")[0]
                        self.assertIn("focus: none", body_rule, window)
                    self.assertNotIn("data-event-click", markup, "buttons act on mousedown")
                    for label in re.findall(r"<label\b[^>]*>", markup):
                        self.assertIn("data-event-mousedown", label,
                                      "RmlUi makes no click in a document that takes no focus, so a label never forwards one")


class ClassicTitleBars(unittest.TestCase):
    """RmlUi hit-tests positioned boxes in document order: a classic overlay
    that places its title bar absolutely, ahead of the legacy rows it places
    from the board's corner, must lift the bar (z-index), or the rows' boxes
    take the close button's and the handle's presses."""

    def test_an_absolute_classic_title_bar_comes_above_the_rows(self):
        skins = os.path.join(os.path.dirname(WINDOWS), "skins", "classic", "windows")
        for _, _, window, _ in BOARDS:
            path = os.path.join(skins, window + ".rcss")
            if not os.path.exists(path):
                continue
            sheet = read(path)
            marker = ".%s__titlebar\n{" % window
            if marker not in sheet:
                continue
            rule = sheet.split(marker)[1].split("}")[0]
            with self.subTest(window=window):
                if "position: absolute" in rule:
                    self.assertIn("z-index: 1", rule)


class NoPerFramePython(unittest.TestCase):
    def test_no_wave3a_module_defines_a_per_frame_hook(self):
        for name in NOVAUI_MODULES:
            tree = ast.parse(read(os.path.join(ROOT, name + ".py")))
            defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
            self.assertEqual(defined & {"OnUpdate", "OnRender", "OnMouseOverIn"}, set(), name)


# --- the wiring (spec 6.8) ------------------------------------------------------------------------------

def factory_sites(file_name):
    tree = ast.parse(read(os.path.join(ROOT, file_name)))
    sites = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("make", "factory")
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "nui_windows"):
            sites.append((node.lineno, node.func.attr, ast.literal_eval(node.args[0]), ast.unparse(node.args[1]),
                          ast.literal_eval(node.args[2])))
    return [site[1:] for site in sorted(sites)]


WAVE3A_IDS = ("system-menu", "system-options", "game-options", "restart", "help", "point-reset")
WAVE3A_SITES = {
    "interfacemodule.py": [("make", "point-reset", "uiPointReset.PointResetDialog", "nui_point_reset.PointResetDialog"),
                           ("make", "restart", "uiRestart.RestartDialog", "nui_restart.RestartDialog"),
                           ("make", "system-menu", "uiSystem.SystemDialog", "nui_system_menu.SystemDialog"),
                           ("make", "help", "uiHelp.HelpWindow", "nui_help.HelpWindow")],
    "uisystemoption.py": [("factory", "system-options", "LegacyOptionDialog", "nui_system_options.OptionDialog")],
    "uigameoption.py": [("factory", "game-options", "LegacyOptionDialog", "nui_game_options.OptionDialog")],
}


class Recorded(object):
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
        for file_name, expected in WAVE3A_SITES.items():
            sites = [site for site in factory_sites(file_name) if site[1] in WAVE3A_IDS]
            self.assertEqual(sites, expected, file_name)
        for file_name in ("uisystemoption.py", "uigameoption.py"):
            tree = ast.parse(read(os.path.join(ROOT, file_name)))
            classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
            self.assertEqual(classes, {"OptionDialog"}, "the legacy class keeps its name; the factory rebinds it after")
            assigned = [ast.unparse(node) for node in tree.body if isinstance(node, ast.Assign)]
            self.assertIn("LegacyOptionDialog = OptionDialog", assigned)

    def interface(self, windows):
        """interfacemodule.py over MagicMock modules (but nui_windows, nui,
        dbg, systemSetting and ui), with recording window classes."""
        source = read(os.path.join(ROOT, "interfacemodule.py"))
        names = set()
        for node in ast.parse(source).body:
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
        game = support.Game()
        game.modules["systemSetting"].GetUINuiWindows = lambda: windows
        modules = {name: mock.MagicMock(name=name) for name in names - {"sys", "nui_windows", "systemSetting", "dbg", "ui"}}
        Recorded.made = []
        for module, name in (("uiPointReset", "PointResetDialog"), ("uiRestart", "RestartDialog"),
                             ("uiSystem", "SystemDialog"), ("uiHelp", "HelpWindow")):
            setattr(modules[module], name, window_class(name, False))
        for module_name, class_name in (("nui_point_reset", "PointResetDialog"), ("nui_restart", "RestartDialog"),
                                        ("nui_system_menu", "SystemDialog"), ("nui_help", "HelpWindow")):
            module = types.ModuleType(module_name)
            setattr(module, class_name, window_class("Nui" + class_name, True))
            modules[module_name] = module
        for name, module in modules.items():
            game.put(name, module)
        game.load("nui_windows", "nui_windows.py")
        interface_module = game.load("interfaceModule", "interfacemodule.py")
        interface = object.__new__(interface_module.Interface)
        interface.wndUICurtain = mock.MagicMock(name="wndUICurtain")
        return game, interface_module, interface

    def make_sites(self, game, interface):
        with game:
            interface._Interface__MakeDialogs()
            interface._Interface__MakeHelpWindow()
        return [type(getattr(interface, name)).__name__ for name in ("dlgPointReset", "dlgRestart", "dlgSystem", "wndHelp")]

    def test_with_every_flag_off_the_interface_makes_the_legacy_windows_and_the_curtain_shows_for_the_legacy_help(self):
        game, module, interface = self.interface("")
        self.assertEqual(self.make_sites(game, interface), ["PointResetDialog", "RestartDialog", "SystemDialog", "HelpWindow"])
        with game:
            interface.OpenHelpWindow()
            interface.CloseHelpWindow()
        self.assertEqual([call[0] for call in interface.wndUICurtain.method_calls], ["Show", "Hide"])
        self.assertEqual(game.dbg.errors, [])

    def test_with_each_flag_on_the_interface_makes_exactly_the_named_class_and_no_curtain(self):
        game, module, interface = self.interface("+sys,+dialogs")
        self.assertEqual(self.make_sites(game, interface),
                         ["NuiPointResetDialog", "NuiRestartDialog", "NuiSystemDialog", "NuiHelpWindow"])
        with game:
            interface.OpenHelpWindow()
            interface.CloseHelpWindow()
        self.assertEqual(interface.wndUICurtain.method_calls, [], "the NovaUI help's scrim is its curtain")
        self.assertEqual([call[0] for call in interface.wndHelp.calls if call[0] in ("Open", "Close")], ["Open", "Close"])
        for window_id in ("point-reset", "restart", "system-menu", "help"):
            game, module, interface = self.interface("+" + window_id + ",+dialogs")
            made = self.make_sites(game, interface)
            self.assertEqual(sum(name.startswith("Nui") for name in made), 1, window_id)

    def test_point_reset_without_the_dialog_kit_is_refused_and_legacy(self):
        game, module, interface = self.interface("+sys")
        made = self.make_sites(game, interface)
        self.assertEqual(made[0], "PointResetDialog")
        self.assertEqual(game.loaded["nui_windows"].DECISIONS["point-reset"], "legacy: needs the NovaUI dialog kit")
        self.assertEqual(made[1:], ["NuiRestartDialog", "NuiSystemDialog", "NuiHelpWindow"])
        self.assertEqual(game.dbg.errors, [])

    def test_a_novaui_class_that_raises_falls_back_to_the_legacy_one(self):
        game, module, interface = self.interface("+restart")

        class Raising(object):
            def __init__(self):
                raise RuntimeError("boom")

        game.modules["nui_restart"].RestartDialog = Raising
        with game:
            interface._Interface__MakeDialogs()
        self.assertEqual(type(interface.dlgRestart).__name__, "RestartDialog")
        self.assertEqual(game.dbg.errors, ["nui_windows: restart: the controller could not be made (RuntimeError); using the legacy window"])

    def test_the_option_names_are_the_factories(self):
        world = World(False)
        with world:
            for module in ("uiSystemOption", "uiGameOption"):
                factory = world.m(module).OptionDialog
                self.assertEqual(factory.__name__, "OptionDialog")
                self.assertIs(factory.legacy, world.m(module).LegacyOptionDialog)
            self.assertEqual(world.m("uiSystemOption").OptionDialog.window_id, "system-options")
            self.assertEqual(world.m("uiGameOption").OptionDialog.window_id, "game-options")
            with quiet():
                self.assertIsInstance(world.m("uiSystemOption").OptionDialog(), world.m("uiSystemOption").LegacyOptionDialog)
