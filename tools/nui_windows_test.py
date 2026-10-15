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
WAVE3B = ["inventory", "tooltips", "refine", "attach-metin", "select-item"]
# Documents a later stage writes, listed for the prewarm already: the test
# below fails while a document named here exists, or one not named here is
# missing. TOOLTIPS AND DIALOGS (P14 spec 9.1, 9.4) wrote the last Wave 3b ones.
PENDING_DOCUMENTS = set()
# Wave 4 (P16 spec 6.1, 11.3): the documents its TRADE and SOCIAL stages
# write, each taken out as it lands.
WAVE4_PENDING = {"shop", "private-shop", "safebox", "safebox-password", "change-password", "mall",
                 "equipment-view", "messenger", "whisper", "guild", "guild-grade-name", "guild-war-declare",
                 "guild-war-accept", "guild-mark"}
PENDING_DOCUMENTS = PENDING_DOCUMENTS | WAVE4_PENDING


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
        self.assertEqual([window_id for window_id, _ in self.m.WINDOWS][:len(WAVE1 + WAVE2A + WAVE2B + WAVE3A + WAVE5A)],
                         WAVE1 + WAVE2A + WAVE2B + WAVE3A + WAVE5A, "appended in this order")
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

    def test_every_wave3b_window_defaults_to_legacy(self):
        self.assertEqual([window_id for window_id, _ in self.m.WINDOWS][:len(WAVE1 + WAVE2A + WAVE2B + WAVE3A + WAVE5A + WAVE3B)],
                         WAVE1 + WAVE2A + WAVE2B + WAVE3A + WAVE5A + WAVE3B, "appended after console, in this order")
        for window_id, default in self.m.WINDOWS[len(WAVE1 + WAVE2A + WAVE2B + WAVE3A + WAVE5A):]:
            self.assertIs(default, False, window_id)
            self.assertEqual(self.m.use(window_id), (False, "flag off"))
            self.assertEqual(self.m.DECISIONS[window_id], "legacy: flag off")

    def test_items_names_the_five_wave3b_windows_and_rest_keeps_its_four(self):
        self.assertEqual(self.m.GROUPS["items"], tuple(WAVE3B))
        self.assertEqual(self.m.GROUPS["rest"], tuple(WAVE5A), "+rest keeps meaning the Wave 5a windows")
        self.setting.windows = "+rest"
        self.assertFalse(any(self.m.is_on(window_id) for window_id in WAVE3B), "+rest turns no Wave 3b window on")
        self.setting.windows = "+items,-tooltips"
        self.assertEqual(self.m.overrides(), dict((window_id, window_id != "tooltips") for window_id in WAVE3B))
        self.assertFalse(any(self.m.is_on(window_id) for window_id in WAVE1 + WAVE2A + WAVE2B + WAVE3A + WAVE5A),
                         "+items turns no earlier window on")
        self.assertEqual(self.m.use("inventory"), (True, ""))
        self.assertEqual(self.m.use("tooltips"), (False, "flag off"))
        self.assertEqual(self.m.use("items"), (False, "flag off"), "a group is not a window")
        self.assertRaises(ValueError, self.m.set_override, "items", True)

    def test_the_wave3b_demo_string_fits_ui_nui_windows(self):
        demo = "+wave1,+hud,+hud2,+sys,+rest,+items"
        self.assertLessEqual(len(demo), 200)
        self.assertEqual(len(demo), 35)
        self.setting.windows = demo
        self.assertEqual(sorted(window_id for window_id, on in self.m.overrides().items() if on),
                         sorted(WAVE1[1:] + WAVE2A + WAVE2B + WAVE3A + WAVE5A + WAVE3B))

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
        self.assertEqual(self.m.PHASE_SCOPED[:3], ("nui_dialog_kit", "nui_quest", "nui_tooltip"))
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
        self.modules.put("nui_tooltip", None)
        lines = list(self.dbg.lines)
        self.assertEqual(self.m.end_phase(), 0)
        self.assertIsNone(sys.modules["nui_dialog_kit"])
        self.assertIsNone(sys.modules["nui_quest"])
        self.assertIsNone(sys.modules["nui_tooltip"])
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


class GameWindow(object):
    """Stands in for game.GameWindow, the game phase's window (by class name)."""


class SelectWindow(object):
    pass


class PhaseStart(WindowsTest):
    def prewarm_seen(self, accepted=True):
        seen = []

        def prewarm(paths):
            seen.append(list(paths))
            return accepted
        self.m.nui.prewarm = prewarm
        return seen

    def test_the_game_phase_queues_the_on_demand_documents_of_the_windows_that_are_on(self):
        self.setting.windows = "+sys,+dialogs,+chat-log,-help"
        seen = self.prewarm_seen()
        self.assertEqual(self.m.start_phase(GameWindow()), 11)
        self.assertEqual(seen, [["nui/windows/system-menu/system-menu.rml", "nui/windows/system-options/system-options.rml",
                                 "nui/windows/music-list/music-list.rml", "nui/windows/game-options/game-options.rml",
                                 "nui/windows/restart/restart.rml", "nui/windows/dialog-question/dialog-question.rml",
                                 "nui/windows/dialog-message/dialog-message.rml", "nui/windows/dialog-input/dialog-input.rml",
                                 "nui/windows/dialog-money/dialog-money.rml", "nui/windows/pick-money/pick-money.rml",
                                 "nui/windows/chat-log/chat-log.rml"]],
                         "the windows that are on, in the table's order, each document once (point reset shares the "
                         "question dialog); help is off")
        self.assertEqual(self.dbg.lines[-1], "nui_windows: game phase, 11 document(s) queued for a prewarm")

    def test_another_phase_novaui_off_or_nothing_on_queues_nothing(self):
        self.setting.windows = "+sys"
        seen = self.prewarm_seen()
        self.assertEqual(self.m.start_phase(SelectWindow()), 0, "only the game phase prewarms")
        self.state.available = False
        self.assertEqual(self.m.start_phase(GameWindow()), 0)
        self.state.available = True
        self.setting.windows = ""
        self.assertEqual(self.m.start_phase(GameWindow()), 0, "no on-demand window is on")
        self.assertEqual(seen, [])

    def test_an_exe_or_nui_without_prewarm_queues_nothing(self):
        self.setting.windows = "+sys"
        self.assertFalse(hasattr(self.m.nui, "prewarm"))
        self.assertEqual(self.m.start_phase(GameWindow()), 0)
        self.prewarm_seen(accepted=False)
        self.assertEqual(self.m.start_phase(GameWindow()), 0, "a runtime that refuses the list queued nothing")

    def test_every_prewarm_document_is_an_on_demand_window_document(self):
        ids = [window_id for window_id, _ in self.m.WINDOWS]
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "nui")
        for window_id, names in self.m.ON_DEMAND_DOCUMENTS:
            self.assertIn(window_id, ids)
            for name in names:
                exists = os.path.isfile(os.path.join(root, "nui", "windows", name, name + ".rml"))
                if name in PENDING_DOCUMENTS:
                    self.assertFalse(exists, "%s exists: take it out of PENDING_DOCUMENTS" % name)
                else:
                    self.assertTrue(exists, name)

    def test_the_wave3b_documents_are_prewarmed_with_their_flags(self):
        self.assertIn(("inventory", ("inventory", "costume", "belt-inventory")), self.m.ON_DEMAND_DOCUMENTS)
        self.assertIn(("tooltips", ("item-tooltip", "skill-tooltip", "link-tooltip")), self.m.ON_DEMAND_DOCUMENTS)
        self.setting.windows = "+inventory,+select-item"
        self.assertEqual(self.m.prewarm_documents(),
                         ["nui/windows/inventory/inventory.rml", "nui/windows/costume/costume.rml",
                          "nui/windows/belt-inventory/belt-inventory.rml", "nui/windows/select-item/select-item.rml"])


# --- Wave 4 (P16 spec 6.1) -----------------------------------------------------------------

WAVE4_TRADE = ["exchange", "shop", "private-shop", "safebox", "mall", "equipment-view"]
WAVE4_SOCIAL = ["messenger", "whisper", "guild", "guild-war-dialogs", "guild-mark"]


class Wave4Flags(WindowsTest):
    def test_every_wave4_window_defaults_to_legacy_appended_after_select_item(self):
        ids = [window_id for window_id, _ in self.m.WINDOWS]
        start = ids.index("select-item") + 1
        self.assertEqual(ids[start:start + 11], WAVE4_TRADE + WAVE4_SOCIAL, "appended after select-item, in this order")
        for window_id in WAVE4_TRADE + WAVE4_SOCIAL:
            self.assertIs(dict(self.m.WINDOWS)[window_id], False, window_id)
            self.assertEqual(self.m.use(window_id), (False, "flag off"))
            self.assertEqual(self.m.DECISIONS[window_id], "legacy: flag off")
        self.assertNotIn("guild-war", WAVE4_SOCIAL, "Wave 2b's score boards keep their id")

    def test_trade_and_social_name_their_windows_and_turn_no_other_on(self):
        self.assertEqual(self.m.GROUPS["trade"], tuple(WAVE4_TRADE))
        self.assertEqual(self.m.GROUPS["social"], tuple(WAVE4_SOCIAL))
        self.assertEqual(self.m.GROUPS["items"], tuple(WAVE3B), "+items keeps meaning the Wave 3b windows")
        self.setting.windows = "+trade,-mall"
        self.assertEqual(self.m.overrides(), dict((window_id, window_id != "mall") for window_id in WAVE4_TRADE))
        self.assertEqual(self.m.use("exchange"), (True, ""))
        self.assertEqual(self.m.use("mall"), (False, "flag off"))
        self.assertFalse(any(self.m.is_on(window_id) for window_id in WAVE4_SOCIAL + WAVE3B))
        self.setting.windows = "+social"
        self.assertTrue(all(self.m.is_on(window_id) for window_id in WAVE4_SOCIAL))
        self.assertFalse(any(self.m.is_on(window_id) for window_id in WAVE4_TRADE))
        for group in ("trade", "social"):
            self.assertNotIn(group, [window_id for window_id, _ in self.m.WINDOWS])
            self.assertEqual(self.m.use(group), (False, "flag off"))
            self.assertRaises(ValueError, self.m.set_override, group, True)

    def test_the_wave4_demo_string_fits_ui_nui_windows(self):
        demo = "+wave1,+hud,+hud2,+sys,+rest,+items,+trade,+social"
        self.assertLessEqual(len(demo), 200)
        self.assertEqual(len(demo), 50)
        self.setting.windows = demo
        self.assertEqual(sorted(window_id for window_id, on in self.m.overrides().items() if on),
                         sorted(WAVE1[1:] + WAVE2A + WAVE2B + WAVE3A + WAVE5A + WAVE3B + WAVE4_TRADE + WAVE4_SOCIAL))

    def test_the_wave4_documents_are_on_demand_and_prewarmed_with_their_flags(self):
        expected = [("exchange", ("exchange",)), ("shop", ("shop",)), ("private-shop", ("private-shop",)),
                    ("safebox", ("safebox", "safebox-password", "change-password")), ("mall", ("mall",)),
                    ("equipment-view", ("equipment-view",)), ("messenger", ("messenger",)), ("whisper", ("whisper",)),
                    ("guild", ("guild", "guild-grade-name")),
                    ("guild-war-dialogs", ("guild-war-declare", "guild-war-accept")), ("guild-mark", ("guild-mark",))]
        for entry in expected:
            self.assertIn(entry, self.m.ON_DEMAND_DOCUMENTS)
        self.setting.windows = "+safebox,+equipment-view"
        self.assertEqual(self.m.prewarm_documents(),
                         ["nui/windows/safebox/safebox.rml", "nui/windows/safebox-password/safebox-password.rml",
                          "nui/windows/change-password/change-password.rml",
                          "nui/windows/equipment-view/equipment-view.rml"])

    def test_end_phase_asks_nui_whisper(self):
        self.assertIn("nui_whisper", self.m.PHASE_SCOPED)
        self.modules.put("nui_whisper", support.stub_module("nui_whisper", end_phase=lambda: 2))
        self.assertEqual(self.m.end_phase(), 2)

    def test_the_wave4_lines_name_importable_modules_and_classes(self):
        """The factory strings of the 16 legacy lines (P16 spec 6.2), each
        made through make(); with the flags off make() builds the legacy
        class with the same arguments."""
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "root")
        texts = dict((name, open(os.path.join(root, name), encoding="utf-8", errors="replace").read())
                     for name in ("interfacemodule.py", "game.py", "uiguild.py"))
        lines = [
            ("interfacemodule.py", 'self.wndMessenger = nui_windows.make("messenger", uiMessenger.MessengerWindow, "nui_messenger.MessengerWindow")'),
            ("interfacemodule.py", 'self.wndGuild = nui_windows.make("guild", uiGuild.GuildWindow, "nui_guild.GuildWindow")'),
            ("interfacemodule.py", 'wndSafebox = nui_windows.make("safebox", uiSafebox.SafeboxWindow, "nui_safebox.SafeboxWindow")'),
            ("interfacemodule.py", 'wndMall = nui_windows.make("mall", uiSafebox.MallWindow, "nui_mall.MallWindow")'),
            ("interfacemodule.py", 'self.dlgExchange = nui_windows.make("exchange", uiExchange.ExchangeDialog, "nui_exchange.ExchangeDialog")'),
            ("interfacemodule.py", 'self.dlgShop = nui_windows.make("shop", uiShop.ShopDialog, "nui_shop.ShopDialog")'),
            ("interfacemodule.py", 'self.dlgPassword = nui_windows.make("safebox", uiSafebox.PasswordDialog, "nui_safebox.PasswordDialog")'),
            ("interfacemodule.py", 'self.privateShopBuilder = nui_windows.make("private-shop", uiPrivateShopBuilder.PrivateShopBuilder, "nui_private_shop.PrivateShopBuilder")'),
            ("interfacemodule.py", 'dlg = nui_windows.make("equipment-view", uiEquipmentDialog.EquipmentDialog, "nui_equipment_view.EquipmentDialog")'),
            ("interfacemodule.py", 'dlgWhisper = nui_windows.make("whisper", uiWhisper.WhisperDialog, "nui_whisper.WhisperDialog", self.MinimizeWhisperDialog, self.CloseWhisperDialog)'),
            ("game.py", 'questionDialog = nui_windows.make("guild-war-dialogs", uiGuild.AcceptGuildWarDialog, "nui_guild_war_accept.AcceptGuildWarDialog")'),
            ("uiguild.py", 'self.markSelectDialog=nui_windows.make("guild-mark", uiUploadMark.MarkSelectDialog, "nui_guild_mark.MarkSelectDialog")'),
            ("uiguild.py", 'self.symbolSelectDialog=nui_windows.make("guild-mark", uiUploadMark.SymbolSelectDialog, "nui_guild_mark.SymbolSelectDialog")'),
            ("uiguild.py", 'inputDialog = nui_windows.make("guild-war-dialogs", DeclareGuildWarDialog, "nui_guild_war_declare.DeclareGuildWarDialog")'),
        ]
        for name, line in lines:
            self.assertIn(line, texts[name], name)
        self.assertEqual(texts["interfacemodule.py"].count(lines[9][1]), 2, "both whisper dialogs")
        self.assertIn("\nimport nui_windows\n", texts["uiguild.py"])
        known = set(window_id for window_id, _ in self.m.WINDOWS)
        for _, line in lines:
            window_id = line.split('make("', 1)[1].split('"', 1)[0]
            self.assertIn(window_id, known, line)

    def test_uiguild_holds_nothing_of_novaui_but_its_four_wave4_lines(self):
        """nui_chat_test and nui_quest_test kept uiguild.py free of NovaUI;
        Wave 4 adds its import and three make() lines, and nothing else."""
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "root")
        lines = open(os.path.join(root, "uiguild.py"), encoding="utf-8").read().split("\n")
        novaui = [line.strip() for line in lines if "nui_" in line]
        self.assertEqual(novaui, [
            "import nui_windows",
            'self.markSelectDialog=nui_windows.make("guild-mark", uiUploadMark.MarkSelectDialog, "nui_guild_mark.MarkSelectDialog")',
            'self.symbolSelectDialog=nui_windows.make("guild-mark", uiUploadMark.SymbolSelectDialog, "nui_guild_mark.SymbolSelectDialog")',
            'inputDialog = nui_windows.make("guild-war-dialogs", DeclareGuildWarDialog, "nui_guild_war_declare.DeclareGuildWarDialog")'])

    def test_with_the_flags_off_make_builds_the_legacy_class_with_the_same_arguments(self):
        for window_id in WAVE4_TRADE + WAVE4_SOCIAL:
            made = self.m.make(window_id, Legacy, "nui_never_imported.Window", 1, kind=window_id)
            self.assertIsInstance(made, Legacy)
            self.assertEqual((made.args, made.kwargs), ((1,), {"kind": window_id}))
        self.assertNotIn("nui_never_imported", sys.modules)


if __name__ == "__main__":
    unittest.main()
