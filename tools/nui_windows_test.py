"""Tests for assets/root/nui_windows.py: python3 -B -m unittest nui_windows_test
(from tools/). Plain CPython over the stand-ins of nui_test_support."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_test_support as support  # noqa: E402

WAVE1 = ["login", "dialogs", "server-board", "virtual-keyboard", "locale-strip", "loading", "empire", "select", "create"]
WAVE2A = ["taskbar", "expanded-taskbar", "energy-bar", "gift-box", "game-buttons", "affects", "target", "party",
          "edge-buttons", "tip-board", "big-board", "map-name"]
WAVE2B = ["chat", "chat-log", "minimap", "atlas", "player-gauge", "shop-signs", "guild-war"]
WAVE3A = ["system-menu", "system-options", "game-options", "restart", "help", "point-reset"]
WAVE5A = ["quest", "guild-building", "web", "console"]


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
        self.assertEqual([window_id for window_id, _ in self.m.WINDOWS][:len(WAVE1)], WAVE1)
        for window_id, default in self.m.WINDOWS[:len(WAVE1)]:
            self.assertIs(default, False, window_id)
            self.assertFalse(self.m.is_on(window_id), window_id)
            self.assertEqual(self.m.use(window_id), (False, "flag off"))
            self.assertEqual(self.m.DECISIONS[window_id], "legacy: flag off")

    def test_every_wave2a_window_defaults_to_legacy(self):
        self.assertEqual([window_id for window_id, _ in self.m.WINDOWS][:len(WAVE1 + WAVE2A)], WAVE1 + WAVE2A,
                         "appended in this order")
        for window_id, default in self.m.WINDOWS[len(WAVE1):len(WAVE1 + WAVE2A)]:
            self.assertIs(default, False, window_id)
            self.assertFalse(self.m.is_on(window_id), window_id)
            self.assertEqual(self.m.use(window_id), (False, "flag off"))
            self.assertEqual(self.m.DECISIONS[window_id], "legacy: flag off")

    def test_every_wave2b_window_defaults_to_legacy(self):
        self.assertEqual([window_id for window_id, _ in self.m.WINDOWS][:len(WAVE1 + WAVE2A + WAVE2B)], WAVE1 + WAVE2A + WAVE2B,
                         "appended in this order")
        for window_id, default in self.m.WINDOWS[len(WAVE1 + WAVE2A):len(WAVE1 + WAVE2A + WAVE2B)]:
            self.assertIs(default, False, window_id)
            self.assertFalse(self.m.is_on(window_id), window_id)
            self.assertEqual(self.m.use(window_id), (False, "flag off"))
            self.assertEqual(self.m.DECISIONS[window_id], "legacy: flag off")

    def test_hud2_names_the_seven_wave2b_windows_and_hud_keeps_its_twelve(self):
        self.assertEqual(self.m.GROUPS["hud2"], tuple(WAVE2B))
        self.assertEqual(self.m.GROUPS["hud"], tuple(WAVE2A), "+hud keeps meaning the Wave 2a windows")
        self.assertEqual(len(self.m.GROUPS["hud"]), 12)
        self.setting.windows = "+hud"
        self.assertFalse(any(self.m.is_on(window_id) for window_id in WAVE2B), "+hud turns no Wave 2b window on")
        self.setting.windows = "+hud2,-atlas"
        self.assertEqual(self.m.overrides(), dict((window_id, window_id != "atlas") for window_id in WAVE2B))
        self.assertFalse(any(self.m.is_on(window_id) for window_id in WAVE2A), "+hud2 turns no Wave 2a window on")
        self.assertEqual(self.m.use("chat"), (True, ""))
        self.assertEqual(self.m.use("atlas"), (False, "flag off"))
        self.assertNotIn("hud2", self.m.overrides())
        self.assertRaises(ValueError, self.m.set_override, "hud2", True)

    def test_the_wave2b_demo_string_fits_ui_nui_windows(self):
        demo = "+wave1,+hud,+hud2"
        self.assertLessEqual(len(demo), 200)
        self.assertEqual(len(demo), 17)
        known = [window_id for window_id, _ in self.m.WINDOWS]
        for group in ("wave1", "hud", "hud2"):
            for window_id in self.m.GROUPS[group]:
                self.assertIn(window_id, known)
        self.setting.windows = demo
        self.assertEqual(sorted(window_id for window_id, on in self.m.overrides().items() if on),
                         sorted(WAVE1[1:] + WAVE2A + WAVE2B))

    def test_every_wave3a_window_defaults_to_legacy(self):
        earlier = WAVE1 + WAVE2A + WAVE2B + WAVE3A
        self.assertEqual([window_id for window_id, _ in self.m.WINDOWS][:len(earlier)], earlier,
                         "appended in this order")
        for window_id, default in self.m.WINDOWS[len(WAVE1 + WAVE2A + WAVE2B):len(earlier)]:
            self.assertIs(default, False, window_id)
            self.assertFalse(self.m.is_on(window_id), window_id)
            self.assertEqual(self.m.use(window_id), (False, "flag off"))
            self.assertEqual(self.m.DECISIONS[window_id], "legacy: flag off")

    def test_sys_names_the_six_wave3a_windows_and_hud2_keeps_its_seven(self):
        self.assertEqual(self.m.GROUPS["sys"], tuple(WAVE3A))
        self.assertEqual(self.m.GROUPS["hud2"], tuple(WAVE2B), "+hud2 keeps meaning the Wave 2b windows")
        self.assertEqual(len(self.m.GROUPS["hud2"]), 7)
        self.setting.windows = "+hud2"
        self.assertFalse(any(self.m.is_on(window_id) for window_id in WAVE3A), "+hud2 turns no Wave 3a window on")
        self.setting.windows = "+sys,-help"
        self.assertEqual(self.m.overrides(), dict((window_id, window_id != "help") for window_id in WAVE3A))
        self.assertFalse(any(self.m.is_on(window_id) for window_id in WAVE1 + WAVE2A + WAVE2B),
                         "+sys turns no earlier window on")
        self.assertEqual(self.m.use("system-menu"), (True, ""))
        self.assertEqual(self.m.use("help"), (False, "flag off"))
        self.assertNotIn("sys", self.m.overrides())
        self.assertNotIn("sys", [window_id for window_id, _ in self.m.WINDOWS])
        self.assertEqual(self.m.use("sys"), (False, "flag off"))
        self.assertRaises(ValueError, self.m.set_override, "sys", True)

    def test_the_wave3a_demo_string_fits_ui_nui_windows(self):
        demo = "+wave1,+hud,+hud2,+sys"
        self.assertLessEqual(len(demo), 200)
        self.assertEqual(len(demo), 22)
        known = [window_id for window_id, _ in self.m.WINDOWS]
        for group in ("wave1", "hud", "hud2", "sys"):
            for window_id in self.m.GROUPS[group]:
                self.assertIn(window_id, known)
        self.setting.windows = demo
        self.assertEqual(sorted(window_id for window_id, on in self.m.overrides().items() if on),
                         sorted(WAVE1[1:] + WAVE2A + WAVE2B + WAVE3A))

    def test_every_wave5a_window_defaults_to_legacy(self):
        self.assertEqual([window_id for window_id, _ in self.m.WINDOWS], WAVE1 + WAVE2A + WAVE2B + WAVE3A + WAVE5A,
                         "appended in this order")
        for window_id, default in self.m.WINDOWS[len(WAVE1 + WAVE2A + WAVE2B + WAVE3A):]:
            self.assertIs(default, False, window_id)
            self.assertFalse(self.m.is_on(window_id), window_id)
            self.assertEqual(self.m.use(window_id), (False, "flag off"))
            self.assertEqual(self.m.DECISIONS[window_id], "legacy: flag off")

    def test_rest_names_the_four_wave5a_windows_and_sys_keeps_its_six(self):
        self.assertEqual(self.m.GROUPS["rest"], tuple(WAVE5A))
        self.assertEqual(self.m.GROUPS["sys"], tuple(WAVE3A), "+sys keeps meaning the Wave 3a windows")
        self.assertEqual(len(self.m.GROUPS["sys"]), 6)
        self.setting.windows = "+sys"
        self.assertFalse(any(self.m.is_on(window_id) for window_id in WAVE5A), "+sys turns no Wave 5a window on")
        self.setting.windows = "+rest,-console"
        self.assertEqual(self.m.overrides(), dict((window_id, window_id != "console") for window_id in WAVE5A))
        self.assertFalse(any(self.m.is_on(window_id) for window_id in WAVE1 + WAVE2A + WAVE2B + WAVE3A),
                         "+rest turns no earlier window on")
        self.assertEqual(self.m.use("quest"), (True, ""))
        self.assertEqual(self.m.use("console"), (False, "flag off"))
        self.assertNotIn("rest", self.m.overrides())
        self.assertNotIn("rest", [window_id for window_id, _ in self.m.WINDOWS])
        self.assertEqual(self.m.use("rest"), (False, "flag off"))
        self.assertRaises(ValueError, self.m.set_override, "rest", True)

    def test_the_wave5a_demo_string_fits_ui_nui_windows(self):
        demo = "+wave1,+hud,+hud2,+sys,+rest"
        self.assertLessEqual(len(demo), 200)
        self.assertEqual(len(demo), 28)
        known = [window_id for window_id, _ in self.m.WINDOWS]
        for group in ("wave1", "hud", "hud2", "sys", "rest"):
            for window_id in self.m.GROUPS[group]:
                self.assertIn(window_id, known)
        self.setting.windows = demo
        self.assertEqual(sorted(window_id for window_id, on in self.m.overrides().items() if on),
                         sorted(WAVE1[1:] + WAVE2A + WAVE2B + WAVE3A + WAVE5A))

    def test_a_group_turns_its_members_on_and_off_in_token_order(self):
        self.assertEqual(self.m.GROUPS["hud"], tuple(WAVE2A))
        self.assertEqual(self.m.GROUPS["wave1"], tuple(WAVE1[1:]), "login is in no group")
        self.setting.windows = "+hud,-target"
        on = self.m.overrides()
        self.assertEqual(on, dict([(window_id, window_id != "target") for window_id in WAVE2A]))
        self.assertFalse(self.m.is_on("target"))
        self.assertTrue(self.m.is_on("taskbar"))
        self.assertEqual(self.m.use("taskbar"), (True, ""))
        self.setting.windows = "-target,+hud"
        self.assertTrue(self.m.is_on("target"), "the later token wins")
        self.setting.windows = "+wave1,+hud,-hud"
        self.assertTrue(all(self.m.is_on(window_id) for window_id in WAVE1[1:]))
        self.assertFalse(any(self.m.is_on(window_id) for window_id in WAVE2A))
        self.assertFalse(self.m.is_on("login"))
        self.reload(systemSetting=support.make_setting(flag=1, windows="+wave1"))
        self.assertTrue(self.m.is_on("login"), "UI_NUI_LOGIN 1 still means +login")
        self.reload(systemSetting=support.make_setting(flag=1, windows="+wave1,-login"))
        self.assertFalse(self.m.is_on("login"))

    def test_a_group_id_is_not_a_window(self):
        self.setting.windows = "+hud,+wave1,+hud2"
        for group in ("hud", "wave1", "hud2"):
            self.assertNotIn(group, self.m.overrides())
            self.assertFalse(self.m.is_on(group))
            self.assertEqual(self.m.use(group), (False, "flag off"))
            self.assertNotIn(group, [window_id for window_id, _ in self.m.WINDOWS])

    def test_set_override_refuses_a_group(self):
        self.setting.windows = "+hud"
        for group in ("hud", "wave1"):
            self.assertRaises(ValueError, self.m.set_override, group, True)
            self.assertRaises(ValueError, self.m.set_override, group, None)
        self.assertEqual(self.setting.saved, 0)
        self.assertTrue(self.m.set_override("target", False))
        self.assertEqual(self.setting.windows, "+hud,-target", "the group token stays; the new one after it wins")
        self.assertFalse(self.m.is_on("target"))
        self.assertTrue(self.m.is_on("party"))

    def test_the_demo_string_fits_ui_nui_windows(self):
        demo = "+wave1,+hud"
        self.assertLessEqual(len(demo), 200)
        known = [window_id for window_id, _ in self.m.WINDOWS]
        for members in self.m.GROUPS.values():
            for window_id in members:
                self.assertIn(window_id, known)
        self.setting.windows = demo
        self.assertEqual(sorted(window_id for window_id, on in self.m.overrides().items() if on), sorted(WAVE1[1:] + WAVE2A))

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


class PhaseEnd(WindowsTest):
    def test_end_phase_asks_each_phase_scoped_module_that_is_loaded_and_logs_the_count(self):
        self.assertEqual(self.m.PHASE_SCOPED, ("nui_dialog_kit", "nui_quest"))
        calls = []

        def end_phase():
            calls.append("end")
            return 3

        self.modules.put("nui_dialog_kit", support.stub_module("nui_dialog_kit", end_phase=end_phase))
        self.assertEqual(self.m.end_phase(), 3)
        self.assertEqual(calls, ["end"])
        self.assertEqual(self.dbg.lines[-1], "nui_windows: phase ended, 3 document(s) unloaded")
        self.assertEqual(self.dbg.errors, [])

    def test_end_phase_asks_nui_quest_too(self):
        calls = []

        def kit_end():
            calls.append("kit")
            return 1

        def quest_end():
            calls.append("quest")
            return 2

        self.modules.put("nui_dialog_kit", support.stub_module("nui_dialog_kit", end_phase=kit_end))
        self.modules.put("nui_quest", support.stub_module("nui_quest", end_phase=quest_end))
        self.assertEqual(self.m.end_phase(), 3)
        self.assertEqual(calls, ["kit", "quest"], "in PHASE_SCOPED's order")
        self.assertEqual(self.dbg.lines[-1], "nui_windows: phase ended, 3 document(s) unloaded")
        self.modules.put("nui_dialog_kit", None)
        calls[:] = []
        self.assertEqual(self.m.end_phase(), 2, "a module not imported is skipped, the next one still asked")
        self.assertEqual(calls, ["quest"])

    def test_with_no_phase_scoped_module_imported_end_phase_imports_none_and_logs_nothing(self):
        self.modules.put("nui_dialog_kit", None)  # an import would raise ImportError
        self.modules.put("nui_quest", None)
        lines = list(self.dbg.lines)
        self.assertEqual(self.m.end_phase(), 0)
        self.assertIsNone(sys.modules["nui_dialog_kit"])
        self.assertIsNone(sys.modules["nui_quest"])
        self.assertEqual(self.dbg.lines, lines)
        self.assertEqual(self.dbg.errors, [])

    def test_nothing_unloaded_logs_nothing(self):
        self.modules.put("nui_dialog_kit", support.stub_module("nui_dialog_kit", end_phase=lambda: 0))
        lines = list(self.dbg.lines)
        self.assertEqual(self.m.end_phase(), 0)
        self.assertEqual(self.dbg.lines, lines)

    def test_an_end_phase_that_raises_goes_to_syserr_and_the_phase_change_goes_on(self):
        def end_phase():
            raise KeyError("boom")

        self.modules.put("nui_dialog_kit", support.stub_module("nui_dialog_kit", end_phase=end_phase))
        self.assertEqual(self.m.end_phase(), 0)
        self.assertEqual(self.dbg.errors, ["nui_windows: nui_dialog_kit.end_phase() failed (KeyError)"])


if __name__ == "__main__":
    unittest.main()
