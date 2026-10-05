"""Tests for assets/root/nui_windows.py: python3 -B -m unittest nui_windows_test
(from tools/). Plain CPython over the stand-ins of nui_test_support."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_test_support as support  # noqa: E402

WAVE1 = ["login", "dialogs", "server-board", "virtual-keyboard", "locale-strip", "loading", "empire", "select", "create"]


class Legacy(object):
    made = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        Legacy.made.append(self)


class NovaUI(object):
    ready = True
    events = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def nui_ready(self):
        return NovaUI.ready

    def nui_discard(self):
        NovaUI.events.append("discard")

    def __del__(self):
        NovaUI.events.append("dropped")


class Raising(object):
    def __init__(self, *args):
        raise KeyError("boom")


class WindowsTest(unittest.TestCase):
    def setUp(self):
        self.state = support.NuiState()
        self.dbg = support.make_dbg()
        self.wndmgr = support.make_wndmgr()
        self.setting = support.make_setting(flag=0, windows="")
        self.modules = support.Modules(nui=support.make_nui(self.state), dbg=self.dbg,
                                       systemSetting=self.setting, wndMgr=self.wndmgr)
        self.addCleanup(self.modules.restore)
        self.m = self.modules.load("nui_windows")
        Legacy.made = []
        NovaUI.ready = True
        NovaUI.events = []

    def reload(self, **modules):
        for name, module in modules.items():
            self.modules.put(name, module)
        self.m = self.modules.load("nui_windows")


class Flags(WindowsTest):
    def test_every_wave1_window_defaults_to_legacy(self):
        self.assertEqual([window_id for window_id, _ in self.m.WINDOWS], WAVE1)
        for window_id, default in self.m.WINDOWS:
            self.assertIs(default, False, window_id)
            self.assertFalse(self.m.is_on(window_id), window_id)
            self.assertEqual(self.m.use(window_id), (False, "flag off"))
            self.assertEqual(self.m.DECISIONS[window_id], "legacy: flag off")

    def test_overrides_turn_windows_on_and_off(self):
        self.setting.windows = "+dialogs,+server-board,-select,+unknown-window"
        self.assertEqual(self.m.overrides(), {"dialogs": True, "server-board": True, "select": False, "unknown-window": True})
        self.assertTrue(self.m.is_on("dialogs"))
        self.assertTrue(self.m.is_on("unknown-window"), "an id from a newer release is kept")
        self.assertFalse(self.m.is_on("select"))
        self.assertFalse(self.m.is_on("loading"), "the default")
        self.assertEqual(self.m.use("server-board"), (True, ""))
        self.assertEqual(self.m.DECISIONS["server-board"], "nui")

    def test_a_hand_edited_value_out_of_form_cannot_raise(self):
        self.setting.windows = "+Dialogs, -bad_id,,login,+"
        self.assertEqual(self.m.overrides(), {"dialogs": True})

    def test_ui_nui_login_means_plus_login_unless_the_string_names_login(self):
        self.reload(systemSetting=support.make_setting(flag=1, windows=""))
        self.assertEqual(self.m.overrides(), {"login": True})
        self.assertEqual(self.m.use("login"), (True, ""))
        self.reload(systemSetting=support.make_setting(flag=1, windows="-login"))
        self.assertEqual(self.m.use("login"), (False, "flag off"))
        self.reload(systemSetting=support.make_setting(flag=0, windows="+login"))
        self.assertEqual(self.m.use("login"), (True, ""))

    def test_an_exe_without_the_bindings_has_no_overrides(self):
        self.reload(systemSetting=support.make_setting(has_binding=False, windows=None))
        self.assertEqual(self.m.overrides(), {})
        for window_id in WAVE1:
            self.assertEqual(self.m.use(window_id), (False, "flag off"))
        self.reload(systemSetting=support.make_setting(flag=1, windows=None))
        self.assertEqual(self.m.overrides(), {"login": True}, "UI_NUI_LOGIN still maps without UI_NUI_WINDOWS")

    def test_use_names_the_first_failing_check(self):
        self.setting.windows = "+dialogs"
        self.assertEqual(self.m.use("loading"), (False, "flag off"))
        self.state.available = False
        self.state.rtl = True
        self.assertEqual(self.m.use("dialogs"), (False, "NovaUI unavailable"))
        self.state.available = True
        self.assertEqual(self.m.use("dialogs"), (False, "right-to-left locale"))
        self.assertEqual(self.m.DECISIONS["dialogs"], "legacy: right-to-left locale")
        self.state.rtl = False
        self.assertEqual(self.m.use("dialogs"), (True, ""))

    def test_without_the_nui_module_every_window_is_legacy(self):
        self.setting.windows = "+dialogs"
        self.reload(nui=None)
        self.assertEqual(self.m.use("dialogs"), (False, "NovaUI unavailable"))
        window = types.SimpleNamespace(hWnd=7)
        self.m.legacy_dialog_layer(window)
        self.assertEqual(self.wndmgr.layers, {7: "UI"})

    def test_each_decision_is_logged_once_and_failures_go_to_syserr_once(self):
        self.setting.windows = "+dialogs"
        for _ in range(3):
            self.m.use("dialogs")
        self.assertEqual(self.dbg.lines, ["nui_windows: dialogs -> nui"])
        self.state.rtl = True
        self.m.use("dialogs")
        self.m.use("dialogs")
        self.assertEqual(self.dbg.lines[1:], ["nui_windows: dialogs -> legacy: right-to-left locale"])
        self.assertEqual(self.dbg.errors, [], "a refusal by the checks is not a failure")
        for _ in range(2):
            self.m.note_failure("dialogs", "the document did not load")
        self.assertEqual(self.dbg.errors, ["nui_windows: dialogs: the document did not load; using the legacy window"])
        self.assertEqual(self.m.DECISIONS["dialogs"], "legacy: the document did not load")
        self.m.note_failure("dialogs", "the controller could not be made (KeyError)")
        self.assertEqual(len(self.dbg.errors), 2, "another reason is logged once too")

    def test_refuse_records_its_reason_without_syserr(self):
        self.m.refuse("virtual-keyboard", "needs the NovaUI login board")
        self.assertEqual(self.m.DECISIONS["virtual-keyboard"], "legacy: needs the NovaUI login board")
        self.assertEqual(self.dbg.lines, ["nui_windows: virtual-keyboard -> legacy: needs the NovaUI login board"])
        self.assertEqual(self.dbg.errors, [])


class Factory(WindowsTest):
    def test_make_returns_the_legacy_class_when_the_flag_is_off_without_importing_novaui(self):
        sys.modules.pop("nui_never_imported", None)
        made = self.m.make("dialogs", Legacy, "nui_never_imported.Window", 1, key="v")
        self.assertIsInstance(made, Legacy)
        self.assertEqual((made.args, made.kwargs), ((1,), {"key": "v"}))
        self.assertNotIn("nui_never_imported", sys.modules)
        self.assertEqual(self.dbg.errors, [])

    def test_make_builds_the_novaui_class_named_by_a_string(self):
        self.setting.windows = "+dialogs"
        module = support.stub_module("nui_stub_window", Window=NovaUI)
        self.modules.put("nui_stub_window", module)
        made = self.m.make("dialogs", Legacy, "nui_stub_window.Window", 1, 2)
        self.assertIsInstance(made, NovaUI)
        self.assertEqual(made.args, (1, 2))
        self.assertEqual(Legacy.made, [])

    def test_make_falls_back_when_the_controller_raises_or_cannot_be_imported(self):
        self.setting.windows = "+dialogs,+select"
        self.modules.put("nui_missing_module", None)
        made = self.m.make("dialogs", Legacy, "nui_missing_module.Window")
        self.assertIsInstance(made, Legacy)
        self.assertEqual(self.m.DECISIONS["dialogs"], "legacy: the controller could not be made (ModuleNotFoundError)")
        made = self.m.make("select", Legacy, Raising, 5)
        self.assertIsInstance(made, Legacy)
        self.assertEqual(made.args, (5,))
        self.assertEqual(self.dbg.errors, [
            "nui_windows: dialogs: the controller could not be made (ModuleNotFoundError); using the legacy window",
            "nui_windows: select: the controller could not be made (KeyError); using the legacy window"])

    def test_make_discards_a_novaui_window_whose_document_did_not_load_before_it_makes_the_legacy_one(self):
        self.setting.windows = "+select"
        NovaUI.ready = False

        class RecordingLegacy(Legacy):
            def __init__(self, *args):
                NovaUI.events.append("legacy made")
                Legacy.__init__(self, *args)

        made = self.m.make("select", RecordingLegacy, NovaUI, "stream")
        self.assertIsInstance(made, RecordingLegacy)
        self.assertEqual(NovaUI.events, ["discard", "dropped", "legacy made"])
        self.assertEqual(self.m.DECISIONS["select"], "legacy: the document did not load")
        self.assertEqual(self.dbg.errors, ["nui_windows: select: the document did not load; using the legacy window"])

    def test_factory_makes_what_make_makes_and_carries_the_legacy_class(self):
        made_one = self.m.factory("dialogs", Legacy, NovaUI)
        self.assertEqual(made_one.__name__, "Legacy")
        self.assertIs(made_one.legacy, Legacy)
        self.assertEqual(made_one.window_id, "dialogs")
        self.assertIsInstance(made_one(1), Legacy)
        self.setting.windows = "+dialogs"
        self.assertIsInstance(made_one(1), NovaUI)

    def test_set_override_saves_the_config(self):
        self.setting.windows = "+dialogs,-select"
        self.assertTrue(self.m.set_override("select", True))
        self.assertEqual(self.setting.windows, "+dialogs,+select")
        self.assertTrue(self.m.set_override("dialogs", None))
        self.assertEqual(self.setting.windows, "+select")
        self.assertTrue(self.m.set_override("create", False))
        self.assertEqual(self.setting.windows, "+select,-create")
        self.assertEqual(self.setting.saved, 3)
        self.assertRaises(ValueError, self.m.set_override, "Bad_Id", True)
        self.reload(systemSetting=support.make_setting(windows=None))
        self.assertFalse(self.m.set_override("select", True), "an exe without the binding")


class LayerStopgap(WindowsTest):
    def test_the_layer_stopgap_moves_a_dialog_to_top_most_only_while_a_window_is_shown(self):
        dialog = types.SimpleNamespace(hWnd=11)
        self.m.legacy_dialog_layer(dialog)
        self.assertEqual(self.wndmgr.layer_calls, [(11, "UI")])
        nui = sys.modules["nui"]

        class Board(nui.Window):
            DOCUMENT = "nui/windows/x/x.rml"

        board = Board()
        board.show()
        self.m.legacy_dialog_layer(dialog)
        self.assertEqual(self.wndmgr.layers[11], "TOP_MOST")
        board.hide()
        self.m.legacy_dialog_layer(dialog)
        self.assertEqual(self.wndmgr.layers[11], "UI", "back where it always was")

    def test_without_set_window_layer_or_a_handle_nothing_happens(self):
        self.m.legacy_dialog_layer(types.SimpleNamespace(hWnd=None))
        self.m.legacy_dialog_layer(object())
        self.assertEqual(self.wndmgr.layer_calls, [])
        self.reload(wndMgr=support.make_wndmgr(with_layers=False))
        self.m.legacy_dialog_layer(types.SimpleNamespace(hWnd=3))


if __name__ == "__main__":
    unittest.main()
