"""Tests for the NovaUI dialog kit (assets/root/nui_dialog_*.py, nui_pick_money.py)
and its wiring in uicommon.py, uipickmoney.py and networkmodule.py:
python3 -B -m unittest nui_dialogs_test (from tools/).

Plain CPython. nui, dbg, systemSetting, wndMgr, ui, localeInfo and the game
modules are stand-ins (nui_test_support); the legacy modules and the kit are
the real files from assets/root, so the class-level wiring, the G5 hooks and
the busy fallback run as in the client."""
import ast
import gc
import inspect
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_test_support as support  # noqa: E402

ROOT = support.ROOT
KIT_MODULES = ("nui_dialog_kit", "nui_dialog_message", "nui_dialog_question", "nui_dialog_input",
               "nui_dialog_money", "nui_pick_money")

MESSAGE = "nui/windows/dialog-message/dialog-message.rml"
QUESTION = "nui/windows/dialog-question/dialog-question.rml"
INPUT = "nui/windows/dialog-input/dialog-input.rml"
MONEY = "nui/windows/dialog-money/dialog-money.rml"
PICK = "nui/windows/pick-money/pick-money.rml"

# (legacy file, legacy class, facade module, facade class)
FACADES = [
    ("uicommon.py", "PopupDialog", "nui_dialog_message", "PopupDialog"),
    ("networkmodule.py", "PopupDialog", "nui_dialog_message", "PhasePopupDialog"),
    ("uicommon.py", "QuestionDialog", "nui_dialog_question", "QuestionDialog"),
    ("uicommon.py", "QuestionDialog2", "nui_dialog_question", "QuestionDialog2"),
    ("uicommon.py", "InputDialog", "nui_dialog_input", "InputDialog"),
    ("uicommon.py", "InputDialogWithDescription", "nui_dialog_input", "InputDialogWithDescription"),
    ("uicommon.py", "InputDialogWithDescription2", "nui_dialog_input", "InputDialogWithDescription2"),
    ("uicommon.py", "MoneyInputDialog", "nui_dialog_money", "MoneyInputDialog"),
    ("uipickmoney.py", "PickMoneyDialog", "nui_pick_money", "PickMoneyDialog"),
]
SHIMS = ["Show", "Hide", "IsShow", "SetTop", "SetCenterPosition", "SetPosition", "ClearDictionary", "Lock",
         "Unlock", "SetSize", "UpdateRect", "GetWidth", "GetHeight", "KillFocus"]


class Events(object):
    """Recording events, as callers pass them."""

    def __init__(self):
        self.seen = []

    def __call__(self, name):
        def event(*args):
            self.seen.append((name,) + args)
        return event


class KitTest(unittest.TestCase):
    flags = "+dialogs"

    def setUp(self):
        self.state = support.NuiState()
        for document, field in ((INPUT, "dialog-input-field"), (INPUT, "dialog-input-secret"), (MONEY, "dialog-money-field"),
                                (PICK, "pick-money-field")):
            self.state.field_events[(document, field)] = "edit"
        self.nui = support.make_nui(self.state)
        self.dbg = support.make_dbg()
        self.wndmgr = support.make_wndmgr(mouse=(800, 600))
        self.setting = support.make_setting(flag=0, windows=self.flags)
        self.ui = support.make_legacy_ui()
        self.locale = support.LocaleInfo(MONEY_INPUT_DIALOG_SELLPRICE="Sales Price: ", UI_CANCEL="Cancel",
                                         NumberToMoneyString=support.number_to_money)
        self.app = support.stub_module("app", IsRTL=lambda: False, GetTime=lambda: 0.0)
        stub = support.stub_module
        self.modules = support.Modules(
            nui=self.nui, dbg=self.dbg, systemSetting=self.setting, wndMgr=self.wndmgr, ui=self.ui,
            localeInfo=self.locale, app=self.app, ime=stub("ime", SetCursorPosition=lambda n: None),
            uiScriptLocale=stub("uiScriptLocale", LOCALE_UISCRIPT_PATH="locale/"),
            exception=stub("exception", Abort=self._abort), net=stub("net"), snd=stub("snd"), chr=stub("chr"),
            chrmgr=stub("chrmgr"), background=stub("background"), player=stub("player"),
            playerSettingModule=stub("playerSettingModule"),
            uiPhaseCurtain=stub("uiPhaseCurtain", PhaseCurtain=object))
        for name in KIT_MODULES:
            self.modules.put(name, None)
            sys.modules.pop(name, None)
        sys.path.insert(0, ROOT)
        self.addCleanup(self._cleanup)
        self.nui_windows = self.modules.load("nui_windows")
        self.uiCommon = self.modules.load("uiCommon", "uicommon.py")
        self.uiPickMoney = self.modules.load("uiPickMoney", "uipickmoney.py")
        self.networkModule = self.modules.load("networkModule", "networkmodule.py")
        self.networkModule.print = lambda *args, **kwargs: None  # its NEW and DELETE banners
        self.events = Events()

    def _abort(self, message):
        raise AssertionError("exception.Abort(%r)" % message)

    def _cleanup(self):
        sys.path.remove(ROOT)
        for name in KIT_MODULES:
            sys.modules.pop(name, None)
        self.modules.restore()

    def kit_window(self, document):
        for window in self.state.windows:
            if window.DOCUMENT == document and window._doc:
                return window
        self.fail("no window for %s" % document)

    def legacy_layers(self):
        return dict(self.wndmgr.layers)


# --- the facade surface (AST of the legacy files) --------------------------------------

def legacy_methods(file_name, class_name):
    """{name: ast.arguments} of a legacy class and its bases defined in the
    same file, the subclass winning; private (mangled) names left out."""
    with open(os.path.join(ROOT, file_name), encoding="utf-8") as file:
        tree = ast.parse(file.read())
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    found = {}
    chain = []
    name = class_name
    while name in classes:
        chain.append(classes[name])
        bases = [base.id for base in classes[name].bases if isinstance(base, ast.Name)]
        name = bases[0] if bases else None
    for node in reversed(chain):
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name.startswith("__") and not item.name.endswith("__"):
                    continue
                if item.name in ("__init__", "__del__"):
                    continue
                found[item.name] = item.args
    return found


class FacadeSurface(KitTest):
    def test_every_legacy_method_exists_on_its_facade_with_a_compatible_signature(self):
        for legacy_file, legacy_class, module_name, facade_name in FACADES:
            facade = getattr(__import__(module_name), facade_name)
            for name, args in legacy_methods(legacy_file, legacy_class).items():
                where = "%s.%s for %s %s" % (facade_name, name, legacy_file, legacy_class)
                self.assertTrue(hasattr(facade, name), where)
                legacy_params = [arg.arg for arg in args.args][1:]
                legacy_required = len(legacy_params) - len(args.defaults)
                signature = inspect.signature(getattr(facade, name))
                params = list(signature.parameters.values())[1:]
                if any(p.kind == p.VAR_POSITIONAL for p in params):
                    continue
                positional = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
                required = [p for p in positional if p.default is p.empty]
                self.assertLessEqual(len(required), legacy_required, where)
                self.assertGreaterEqual(len(positional), len(legacy_params), where)
            for name in SHIMS:
                self.assertTrue(callable(getattr(facade, name, None)), "%s.%s" % (facade_name, name))

    def test_the_constructors_take_no_arguments_as_the_legacy_ones(self):
        for _, _, module_name, facade_name in FACADES:
            facade = getattr(__import__(module_name), facade_name)
            params = list(inspect.signature(facade.__init__).parameters)[1:]
            self.assertEqual(params, [], facade_name)


# --- the wiring ----------------------------------------------------------------------------

def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def open_method(file_name, class_name, method="Open"):
    with open(os.path.join(ROOT, file_name), encoding="utf-8") as file:
        tree = ast.parse(file.read())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    return next(item for item in cls.body if isinstance(item, ast.FunctionDef) and item.name == method)


class WiringFlagOff(KitTest):
    flags = ""

    def test_with_the_flag_off_the_names_make_the_legacy_classes_and_import_nothing_novaui(self):
        for name in ("PopupDialog", "InputDialog", "InputDialogWithDescription", "InputDialogWithDescription2",
                     "QuestionDialog", "QuestionDialog2", "MoneyInputDialog"):
            made = getattr(self.uiCommon, name)()
            self.assertIsInstance(made, getattr(self.uiCommon, "Legacy" + name), name)
        self.assertIsInstance(self.uiPickMoney.PickMoneyDialog(), self.uiPickMoney.LegacyPickMoneyDialog)
        self.assertIsInstance(self.networkModule.PopupDialog(), self.networkModule.LegacyPopupDialog)
        for name in KIT_MODULES:
            self.assertIsNone(sys.modules.get(name), name)
        self.assertEqual(self.dbg.errors, [])
        self.assertEqual(self.nui_windows.DECISIONS["dialogs"], "legacy: flag off")

    def test_the_legacy_subclasses_still_reach_their_bases(self):
        # QuestionDialog2.__init__ and the __del__ chains call their bases by
        # name; the plain names are factories now, so they use the Legacy ones.
        dialogs = [self.uiCommon.QuestionDialog2(), self.uiCommon.InputDialogWithDescription(),
                   self.uiCommon.InputDialogWithDescription2(), self.uiCommon.QuestionDialogWithTimeLimit()]
        loaded = self.ui.PythonScriptLoader.loaded
        self.assertIn("uiscript/questiondialog2.py", loaded)
        for dialog in dialogs:
            dialog.__del__()
        del dialogs
        gc.collect()

    def test_a_legacy_dialog_opens_in_the_ui_layer_while_no_novaui_window_is_shown(self):
        dialog = self.uiCommon.QuestionDialog()
        dialog.Open()
        self.assertEqual(self.wndmgr.layers[dialog.hWnd], "UI")


class Wiring(KitTest):
    def test_with_the_flag_on_the_names_make_the_facades(self):
        import nui_dialog_message
        import nui_dialog_question
        import nui_dialog_input
        import nui_dialog_money
        import nui_pick_money
        pairs = [(self.uiCommon.PopupDialog, nui_dialog_message.PopupDialog),
                 (self.uiCommon.QuestionDialog, nui_dialog_question.QuestionDialog),
                 (self.uiCommon.QuestionDialog2, nui_dialog_question.QuestionDialog2),
                 (self.uiCommon.InputDialog, nui_dialog_input.InputDialog),
                 (self.uiCommon.InputDialogWithDescription, nui_dialog_input.InputDialogWithDescription),
                 (self.uiCommon.InputDialogWithDescription2, nui_dialog_input.InputDialogWithDescription2),
                 (self.uiCommon.MoneyInputDialog, nui_dialog_money.MoneyInputDialog),
                 (self.uiPickMoney.PickMoneyDialog, nui_pick_money.PickMoneyDialog),
                 (self.networkModule.PopupDialog, nui_dialog_message.PhasePopupDialog)]
        for factory, facade in pairs:
            self.assertIsInstance(factory(), facade)
        self.assertEqual(self.nui_windows.DECISIONS["dialogs"], "nui")
        self.assertEqual(self.dbg.errors, [])

    def test_the_time_limited_question_stays_legacy(self):
        self.assertTrue(isinstance(self.uiCommon.QuestionDialogWithTimeLimit, type))

    def test_a_kind_whose_document_did_not_load_gives_the_legacy_dialog_and_says_so_once(self):
        self.state.failing.add(QUESTION)
        first = self.uiCommon.QuestionDialog()
        second = self.uiCommon.QuestionDialog()
        self.assertIsInstance(first, self.uiCommon.LegacyQuestionDialog)
        self.assertIsInstance(second, self.uiCommon.LegacyQuestionDialog)
        self.assertEqual(self.dbg.errors, ["nui_windows: dialogs: the document did not load; using the legacy window"])
        self.assertIsInstance(self.uiCommon.PopupDialog(), sys.modules["nui_dialog_message"].PopupDialog,
                              "another kind still loads")

    def test_the_g5_hook_is_the_first_statement_of_each_legacy_open(self):
        for file_name, class_name in (("uicommon.py", "PopupDialog"), ("uicommon.py", "InputDialog"),
                                      ("uicommon.py", "QuestionDialog"), ("uicommon.py", "QuestionDialogWithTimeLimit"),
                                      ("uicommon.py", "MoneyInputDialog"), ("uipickmoney.py", "PickMoneyDialog")):
            first = open_method(file_name, class_name).body[0]
            self.assertIsInstance(first, ast.Expr, class_name)
            self.assertEqual(dotted(first.value.func), "nui_windows.legacy_dialog_layer", class_name)
        body = open_method("networkmodule.py", "PopupDialog").body
        names = [dotted(stmt.value.func) if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) else
                 ("if" if isinstance(stmt, ast.If) else "") for stmt in body]
        hook = names.index("nui_windows.legacy_dialog_layer")
        self.assertEqual(names[hook - 1], "if", "after the Close of a shown popup")
        self.assertEqual(names[hook + 1], "self.Lock")

    def test_the_stopgap_puts_a_legacy_dialog_above_a_shown_novaui_window(self):
        board = self.nui.Window()
        board.DOCUMENT = "nui/windows/x/x.rml"
        legacy = self.uiCommon.LegacyQuestionDialog()
        legacy.Open()
        self.assertEqual(self.wndmgr.layers[legacy.hWnd], "UI")
        message = self.uiCommon.PopupDialog()
        message.Open()
        legacy.Open()
        self.assertEqual(self.wndmgr.layers[legacy.hWnd], "TOP_MOST")


# --- the kinds: 4.1.3 and 4.1.4 ------------------------------------------------------------

class Popup(KitTest):
    def test_open_shows_the_text_with_the_ok_key_and_focuses_the_button(self):
        dialog = self.uiCommon.PopupDialog()
        dialog.SetText("first\nsecond")
        dialog.Open()
        window = self.kit_window(MESSAGE)
        self.assertTrue(dialog.IsShow())
        self.assertEqual(window.model, {"title": "", "lines": ["first", "second"], "button": "@ui.OK"})
        self.assertEqual(window.focused, "dialog-message-accept")
        self.assertTrue(window.MODAL)

    def test_close_hides_then_calls_the_accept_event_even_when_not_shown(self):
        dialog = self.uiCommon.PopupDialog()
        dialog.SetAcceptEvent(self.events("accept"))
        dialog.Close()
        self.assertEqual(self.events.seen, [("accept",)])
        dialog.Open()
        order = []
        dialog.SetAcceptEvent(lambda: order.append(dialog.IsShow()))
        dialog.Close()
        self.assertEqual(order, [False], "hidden before the event")

    def test_enter_presses_the_button_and_escape_does_the_same(self):
        dialog = self.uiCommon.PopupDialog()
        dialog.SetAcceptEvent(self.events("accept"))
        dialog.SetButtonName("Fine")
        dialog.Open()
        window = self.kit_window(MESSAGE)
        self.assertEqual(window.model["button"], "Fine")
        window.fire("accept")  # Enter on the focused button clicks it
        self.assertFalse(dialog.IsShow())
        dialog.Open()
        self.assertTrue(window.key("", self.nui.KEY_ESCAPE))
        self.assertFalse(dialog.IsShow())
        self.assertEqual(self.events.seen, [("accept",), ("accept",)])
        self.assertFalse(window.key("", self.nui.KEY_ESCAPE), "a hidden dialog keeps no key")

    def test_destroy_is_close_and_the_key_hooks_close(self):
        dialog = self.uiCommon.PopupDialog()
        dialog.SetAcceptEvent(self.events("accept"))
        dialog.Open()
        self.assertTrue(dialog.OnIMEReturn())
        dialog.Open()
        self.assertTrue(dialog.OnPressEscapeKey())
        dialog.Destroy()
        self.assertEqual(len(self.events.seen), 3)


class PhasePopup(KitTest):
    def make(self):
        dialog = self.networkModule.PopupDialog()
        dialog.LoadDialog()
        dialog.SetCenterPosition()
        dialog.Hide()
        return dialog

    def test_open_takes_the_message_the_event_and_cancel_as_the_default_button(self):
        dialog = self.make()
        dialog.Open("LOGIN_CONNETING", self.events("connect"))
        window = self.kit_window(MESSAGE)
        self.assertEqual(window.model["lines"], ["LOGIN_CONNETING"])
        self.assertEqual(window.model["button"], "Cancel")
        self.assertEqual(dialog.GetText(), "LOGIN_CONNETING")
        dialog.Open("LOGIN_CONNECT_FAILURE", 0, "OK")
        self.assertEqual(window.model["button"], "OK")
        self.assertEqual(self.events.seen, [("connect",)], "an Open while shown closes the previous one first")

    def test_close_event_runs_once_and_a_close_while_hidden_clears_it(self):
        dialog = self.make()
        dialog.Open("x", self.events("close"))
        dialog.Close()
        dialog.Close()
        self.assertEqual(self.events.seen, [("close",)])
        self.assertEqual(dialog.CloseEvent, 0)
        dialog.CloseEvent = self.events("stale")
        dialog.Close()
        self.assertEqual(dialog.CloseEvent, 0, "not shown: the event is dropped, not run")
        self.assertEqual(len(self.events.seen), 1)

    def test_enter_and_escape_close_and_run_the_event(self):
        dialog = self.make()
        dialog.Open("x", self.events("close"), "OK")
        window = self.kit_window(MESSAGE)
        self.assertEqual(window.focused, "dialog-message-accept")
        window.fire("accept")
        dialog.Open("y", self.events("close2"), "OK")
        self.assertTrue(window.key("", self.nui.KEY_ESCAPE))
        self.assertEqual(self.events.seen, [("close",), ("close2",)])

    def test_nui_login_after_popup_wraps_the_close_event_unchanged(self):
        dbg = support.make_dbg()
        nui_login = self.modules.load("nui_login")
        nui_login.dbg = dbg
        resumed = []

        class Win(object):
            nuiBoard = types.SimpleNamespace(resume=lambda: resumed.append(True))

        win = Win()
        dialog = self.make()
        dialog.Open("SAMELOGIN", self.events("callback"))
        dialog.CloseEvent = nui_login.after_popup(win, dialog.CloseEvent)
        dialog.Close()
        self.assertEqual(resumed, [True])
        self.assertEqual(self.events.seen, [("callback",)])


class Question(KitTest):
    def make(self, cls=None):
        dialog = (cls or self.uiCommon.QuestionDialog)()
        dialog.SetText("LOCALE_CHANGE_CONFIRM")
        dialog.SetAcceptEvent(self.events("accept"))
        dialog.SetCancelEvent(self.events("cancel"))
        return dialog

    def test_the_buttons_call_their_events_and_leave_the_dialog_open(self):
        dialog = self.make()
        dialog.Open()
        window = self.kit_window(QUESTION)
        self.assertEqual(window.model, {"lines": ["LOCALE_CHANGE_CONFIRM"], "accept_label": "@ui.YES", "cancel_label": "@ui.NO"})
        self.assertEqual(window.focused, "dialog-question-accept")
        window.fire("accept")
        window.fire("cancel")
        self.assertEqual(self.events.seen, [("accept",), ("cancel",)])
        self.assertTrue(dialog.IsShow())
        dialog.Close()
        self.assertFalse(dialog.IsShow())
        self.assertEqual(len(self.events.seen), 2, "Close runs no event")

    def test_escape_closes_with_no_event(self):
        dialog = self.make()
        dialog.Open()
        window = self.kit_window(QUESTION)
        self.assertTrue(window.key("", self.nui.KEY_ESCAPE))
        self.assertFalse(dialog.IsShow())
        self.assertEqual(self.events.seen, [])

    def test_a_caller_that_replaces_on_press_escape_key_gets_its_own(self):
        # game.py's friend question: OnPressEscapeKey = OnDenyAddFriend.
        dialog = self.make(self.uiCommon.QuestionDialog2)
        dialog.OnPressEscapeKey = self.events("deny")
        dialog.Open()
        self.kit_window(QUESTION).key("", self.nui.KEY_ESCAPE)
        self.assertEqual(self.events.seen, [("deny",)])

    def test_labels_and_safe_events(self):
        dialog = self.uiCommon.QuestionDialog()
        dialog.SetAcceptText("Go")
        dialog.SetCancelText("Stay")
        target = types.SimpleNamespace(seen=[])

        class Owner(object):
            def on_yes(self):
                target.seen.append("yes")

        owner = Owner()
        dialog.SAFE_SetAcceptEvent(owner.on_yes)
        dialog.Open()
        window = self.kit_window(QUESTION)
        self.assertEqual((window.model["accept_label"], window.model["cancel_label"]), ("Go", "Stay"))
        window.fire("accept")
        self.assertEqual(target.seen, ["yes"])
        dialog.SetText("changed while shown")
        self.assertEqual(window.model["lines"], ["changed while shown"])

    def test_question_dialog2_shows_both_messages(self):
        dialog = self.uiCommon.QuestionDialog2()
        dialog.SetText1("Nova added you as a friend.")
        dialog.SetText2("Accept?")
        dialog.Open()
        self.assertEqual(self.kit_window(QUESTION).model["lines"], ["Nova added you as a friend.", "Accept?"])

    def test_callers_may_store_their_own_attributes(self):
        dialog = self.make()
        dialog.dropType = 1
        dialog.slot = 3
        self.assertEqual((dialog.dropType, dialog.slot), (1, 3))

    def test_get_width_and_height_are_the_dialogs_box_while_shown(self):
        self.state.boxes[(QUESTION, "dialog-question")] = (180.0, 120.0, 282.0, 110.4)
        dialog = self.make()
        self.assertEqual((dialog.GetWidth(), dialog.GetHeight()), (0, 0))
        dialog.Open()
        self.assertEqual((dialog.GetWidth(), dialog.GetHeight()), (282, 110))


class Input(KitTest):
    def make(self, cls=None):
        dialog = (cls or self.uiCommon.InputDialogWithDescription)()
        dialog.SetTitle("INPUT_PRIVATE_CODE_DIALOG_TITLE")
        dialog.SetAcceptEvent(self.events("accept"))
        dialog.SetCancelEvent(self.events("cancel"))
        dialog.SetNumberMode()
        dialog.SetSecretMode()
        dialog.SetMaxLength(7)
        dialog.SetBoardWidth(250)
        dialog.SetDescription("INPUT_PRIVATE_CODE_DIALOG_DESCRIPTION")
        return dialog

    def test_open_shows_the_title_the_description_secret_and_max_and_focuses_the_field(self):
        dialog = self.make()
        dialog.Open()
        window = self.kit_window(INPUT)
        self.assertEqual(window.model, {"title": "INPUT_PRIVATE_CODE_DIALOG_TITLE",
                                        "lines": ["INPUT_PRIVATE_CODE_DIALOG_DESCRIPTION"], "secret": True, "max": 7})
        self.assertEqual(window.focused, "dialog-input-secret", "secret mode uses the password field")

    def test_number_mode_keeps_digits_and_enter_accepts_and_escape_cancels(self):
        dialog = self.make()
        dialog.Open()
        window = self.kit_window(INPUT)
        window.insert_text("dialog-input-secret", "12a3")
        self.assertEqual(dialog.GetText(), "123")
        self.assertIn(("set_value", "dialog-input-secret", "123", "end"), window.calls)
        window.insert_text("dialog-input-secret", "\n")
        self.assertEqual(self.events.seen, [("accept",)])
        self.assertTrue(window.key("dialog-input-secret", self.nui.KEY_ESCAPE))
        self.assertEqual(self.events.seen, [("accept",), ("cancel",)])
        self.assertTrue(dialog.IsShow(), "the events close it, not the keys")

    def test_the_buttons_and_the_close_button_call_the_events(self):
        dialog = self.make()
        dialog.Open()
        window = self.kit_window(INPUT)
        window.fire("accept")
        window.fire("cancel")  # the cancel button and the title bar close button
        self.assertEqual(self.events.seen, [("accept",), ("cancel",)])

    def test_close_hides_and_clears_the_field_and_get_text_keeps_the_last_value(self):
        dialog = self.make()
        dialog.Open()
        window = self.kit_window(INPUT)
        window.insert_text("dialog-input-secret", "4242")
        dialog.Close()
        self.assertFalse(window.is_visible())
        self.assertEqual(window.fields["dialog-input-secret"], "", "the code does not stay in the hidden field")
        self.assertEqual(dialog.GetText(), "4242")

    def test_a_new_dialog_starts_with_an_empty_field(self):
        first = self.make()
        first.Open()
        window = self.kit_window(INPUT)
        window.insert_text("dialog-input-secret", "777")
        first.Close()
        second = self.uiCommon.InputDialog()
        second.Open()
        self.assertEqual(window.fields["dialog-input-secret"], "")
        self.assertEqual(window.fields.get("dialog-input-field", ""), "")
        self.assertEqual(second.GetText(), "")
        self.assertEqual(window.model["secret"], False)
        self.assertEqual(window.focused, "dialog-input-field")

    def test_each_mode_uses_its_own_field_so_no_field_changes_type(self):
        # RmlUi rebuilds an input whose type changes, which drops its
        # maxlength, caret and IME: the document has one field per type.
        plain = self.uiCommon.InputDialog()
        plain.SetMaxLength(12)
        plain.Open()
        window = self.kit_window(INPUT)
        window.insert_text("dialog-input-field", "friend")
        self.assertEqual(plain.GetText(), "friend")
        plain.Close()
        code = self.make()
        code.Open()
        self.assertEqual((window.model["secret"], window.model["max"]), (True, 7))
        self.assertEqual(window.focused, "dialog-input-secret")
        window.insert_text("dialog-input-secret", "1234")
        self.assertEqual(code.GetText(), "1234")
        self.assertEqual(window.fields["dialog-input-field"], "", "the text field stays empty")
        code.Close()
        again = self.uiCommon.InputDialog()
        again.Open()
        self.assertEqual((window.model["secret"], window.model["max"]), (False, 12))
        self.assertEqual(window.focused, "dialog-input-field")
        self.assertEqual(window.fields["dialog-input-secret"], "")

    def test_secret_mode_set_while_shown_moves_the_text_and_the_focus(self):
        dialog = self.uiCommon.InputDialog()
        dialog.Open()
        window = self.kit_window(INPUT)
        window.insert_text("dialog-input-field", "ab")
        dialog.SetSecretMode()
        self.assertTrue(window.model["secret"])
        self.assertEqual(window.focused, "dialog-input-secret")
        self.assertEqual(window.fields["dialog-input-secret"], "ab")
        self.assertEqual(window.fields["dialog-input-field"], "")
        self.assertEqual(window.carets["dialog-input-secret"], 2)
        self.assertEqual(dialog.GetText(), "ab")

    def test_the_field_takes_its_text_after_the_focus_so_the_caret_goes_to_the_end(self):
        dialog = self.make()
        dialog.Open()
        window = self.kit_window(INPUT)
        calls = [call[:2] for call in window.calls if call[0] in ("focus", "set_value")]
        self.assertLess(calls.index(("focus", "dialog-input-secret")), calls.index(("set_value", "dialog-input-secret")))

    def test_description2_shows_both_lines(self):
        dialog = self.uiCommon.InputDialogWithDescription2()
        dialog.SetDescription1("one")
        dialog.SetDescription2("two")
        dialog.Open()
        self.assertEqual(self.kit_window(INPUT).model["lines"], ["one", "two"])

    def test_dropping_a_dialog_without_close_hides_it_and_runs_no_event(self):
        dialog = self.make()
        dialog.Open()
        window = self.kit_window(INPUT)
        del dialog
        gc.collect()
        self.assertFalse(window.is_visible())
        self.assertEqual(self.events.seen, [])

    def test_a_dialog_dropped_in_a_cycle_still_hides(self):
        dialog = self.make()
        dialog.cycle = dialog
        dialog.Open()
        window = self.kit_window(INPUT)
        del dialog
        gc.collect()
        self.assertFalse(window.is_visible())


class Money(KitTest):
    def test_open_clears_set_value_writes_and_every_edit_updates_the_amount(self):
        dialog = self.uiCommon.MoneyInputDialog()
        dialog.SetTitle("PRIVATE_SHOP_INPUT_PRICE_DIALOG_TITLE")
        dialog.SetAcceptEvent(self.events("accept"))
        dialog.SetCancelEvent(self.events("cancel"))
        dialog.Open()
        window = self.kit_window(MONEY)
        self.assertEqual(window.model["money"], "Sales Price: 0 Yang")
        self.assertEqual(window.model["max"], 9)
        dialog.SetValue(1500)
        window.insert_text("dialog-money-field", "0")
        self.assertEqual(dialog.GetText(), "15000")
        self.assertEqual(window.model["money"], "Sales Price: 15,000 Yang")
        window.insert_text("dialog-money-field", "\n")
        self.assertEqual(self.events.seen, [("accept",)])
        window.insert_text("dialog-money-field", "x")
        self.assertEqual(dialog.GetText(), "15000", "digits only")
        self.assertTrue(window.key("dialog-money-field", self.nui.KEY_ESCAPE))
        self.assertEqual(self.events.seen[-1], ("cancel",))
        dialog.Close()
        dialog.Open()
        self.assertEqual(window.fields["dialog-money-field"], "", "Open clears")

    def test_max_length_stays_at_most_nine_and_the_header_changes(self):
        dialog = self.uiCommon.MoneyInputDialog()
        dialog.SetMaxLength(12)
        dialog.SetMoneyHeaderText("Price: ")
        dialog.Open()
        window = self.kit_window(MONEY)
        self.assertEqual(window.model["max"], 9)
        self.assertEqual(window.model["money"], "Price: 0 Yang")


class PickMoney(KitTest):
    def make(self):
        dialog = self.uiPickMoney.PickMoneyDialog()
        dialog.LoadDialog()
        dialog.SetAcceptEvent(self.events("accept"))
        dialog.SetTitleName("EXCHANGE_MONEY")
        dialog.SetMax(6)
        return dialog

    def test_open_places_it_above_the_mouse_and_puts_the_unit_in_the_field(self):
        self.state.scale = 2.0
        dialog = self.make()
        dialog.Open(250, 1)
        window = self.kit_window(PICK)
        self.assertFalse(window.MODAL)
        self.assertEqual(window.placement, ("position", 400.0, 280.0, (0.5, 1.0)))
        self.assertEqual(window.model, {"title": "EXCHANGE_MONEY", "max": 6, "limit": " / 250"})
        self.assertEqual(window.fields["pick-money-field"], "1")
        self.assertEqual(window.focused, "pick-money-field")

    def test_enter_caps_the_amount_calls_the_event_and_closes(self):
        dialog = self.make()
        dialog.Open(250, 1)
        window = self.kit_window(PICK)
        window.insert_text("pick-money-field", "\b")
        window.insert_text("pick-money-field", "300")
        window.insert_text("pick-money-field", "\n")
        self.assertEqual(self.events.seen, [("accept", 250)])
        self.assertFalse(dialog.IsShow())

    def test_the_caret_follows_the_unit_so_backspace_then_typing_replaces_it(self):
        # The legacy habit: Backspace over the 1, then the amount. A caret
        # left before the 1 would make 50 read 501.
        dialog = self.make()
        dialog.Open(1000, 1)
        window = self.kit_window(PICK)
        self.assertEqual(window.carets["pick-money-field"], 1)
        window.insert_text("pick-money-field", "\b")
        window.insert_text("pick-money-field", "50")
        window.insert_text("pick-money-field", "\n")
        self.assertEqual(self.events.seen, [("accept", 50)])

    def test_a_second_open_after_a_close_puts_the_caret_after_the_unit_again(self):
        dialog = self.make()
        dialog.Open(1000, 1)
        window = self.kit_window(PICK)
        window.insert_text("pick-money-field", "234")
        dialog.Close()
        dialog.Open(1000, 1)
        self.assertEqual(window.fields["pick-money-field"], "1")
        self.assertEqual(window.carets["pick-money-field"], 1)

    def test_escape_cancel_and_close_close_with_no_event(self):
        dialog = self.make()
        dialog.Open(250, 1)
        window = self.kit_window(PICK)
        self.assertTrue(window.key("pick-money-field", self.nui.KEY_ESCAPE))
        self.assertFalse(dialog.IsShow())
        dialog.Open(250, 1)
        window.fire("cancel")
        self.assertFalse(dialog.IsShow())
        self.assertEqual(self.events.seen, [])

    def test_nothing_or_zero_accepts_nothing_but_closes(self):
        dialog = self.make()
        dialog.Open(250, 1)
        window = self.kit_window(PICK)
        window.insert_text("pick-money-field", "\b")
        window.fire("accept")
        self.assertEqual(self.events.seen, [])
        self.assertFalse(dialog.IsShow())

    def test_right_to_left_writes_the_limit_without_spaces(self):
        self.app.IsRTL = lambda: True
        dialog = self.make()
        dialog.Open(90)
        self.assertEqual(self.kit_window(PICK).model["limit"], "/90")

    def test_destroy_keeps_the_legacy_meaning_for_the_state(self):
        dialog = self.make()
        dialog.Open(250)
        dialog.Destroy()
        self.assertEqual((dialog.eventAccept, dialog.maxValue), (0, 0))
        self.assertFalse(dialog.IsShow())


# --- the busy fallback ------------------------------------------------------------------------

class Busy(KitTest):
    def test_a_second_question_while_the_first_shows_is_the_legacy_one_with_the_same_state(self):
        first = self.uiCommon.QuestionDialog()
        first.SetText("party")
        first.Open()
        second = self.uiCommon.QuestionDialog()
        second.SetText("guild")
        second.SetAcceptText("Join")
        second.SetAcceptEvent(self.events("accept"))
        second.SetCancelEvent(self.events("cancel"))
        second.Open()
        legacy = second._legacy
        self.assertIsInstance(legacy, self.uiCommon.LegacyQuestionDialog)
        self.assertTrue(second.IsShow())
        self.assertTrue(first.IsShow())
        self.assertEqual(legacy.textLine.text, "guild")
        self.assertEqual(legacy.acceptButton.text, "Join")
        self.assertEqual(second.hWnd, legacy.hWnd)
        self.assertEqual(self.wndmgr.layers[legacy.hWnd], "TOP_MOST")
        legacy.acceptButton.Click()
        legacy.cancelButton.Click()
        self.assertEqual(self.events.seen, [("accept",), ("cancel",)])
        second.Close()
        self.assertFalse(second.IsShow())
        self.assertIsNone(second._legacy)
        self.assertEqual(self.kit_window(QUESTION).model["lines"], ["party"], "the first keeps its window")
        first.Close()
        second.Open()
        self.assertIsNone(second._legacy, "free again: the NovaUI window")
        self.assertEqual(self.kit_window(QUESTION).model["lines"], ["guild"])

    def test_a_busy_input_dialog_routes_get_text_to_the_legacy_one(self):
        first = self.uiCommon.InputDialog()
        first.Open()
        second = self.uiCommon.InputDialog()
        second.SetMaxLength(5)
        second.Open()
        second._legacy.inputValue.SetText("abc")
        self.assertEqual(second.GetText(), "abc")
        second.Close()
        self.assertIsNone(second._legacy)

    def test_a_busy_phase_popup_keeps_its_close_event_on_the_legacy_one(self):
        message = self.uiCommon.PopupDialog()
        message.Open()
        popup = self.networkModule.PopupDialog()
        popup.LoadDialog()
        popup.Open("x", self.events("close"))
        self.assertIsInstance(popup._legacy, self.networkModule.LegacyPopupDialog)
        self.assertEqual(popup.CloseEvent.__class__.__name__, "function")
        popup.Close()
        self.assertEqual(self.events.seen, [("close",)])


class Covered(KitTest):
    """A legacy common dialog above NovaUI (TOP_MOST) covers the kit: the kit
    modals step aside, so the keys go to the dialog the player sees."""

    def open_pair(self):
        first = self.uiCommon.QuestionDialog()
        first.SetText("drop the item?")
        first.SetAcceptEvent(self.events("drop"))
        first.Open()
        second = self.uiCommon.QuestionDialog()
        second.SetText("party invite")
        second.Open()
        return first, second, self.kit_window(QUESTION)

    def test_a_busy_fallback_takes_the_keys_from_the_question_it_covers(self):
        first, second, window = self.open_pair()
        self.assertIsNotNone(second._legacy)
        self.assertTrue(window.is_visible())
        self.assertFalse(window.modal, "not modal: the host sends the keys to the legacy dialog")
        self.assertEqual(window.focused, "", "no focused button for Enter to press")
        self.assertFalse(window.key("", self.nui.KEY_ESCAPE), "the Escape goes on to the legacy dialog")
        self.assertTrue(first.IsShow())
        self.assertEqual(self.events.seen, [])

    def test_the_covered_question_comes_back_when_the_legacy_one_closes(self):
        first, second, window = self.open_pair()
        second._legacy.OnPressEscapeKey()  # the legacy dialog closes itself
        self.assertTrue(window.modal)
        self.assertEqual(window.focused, "dialog-question-accept")
        self.assertTrue(window.key("", self.nui.KEY_ESCAPE))
        self.assertFalse(first.IsShow())

    def test_a_closed_facade_uncovers_too(self):
        first, second, window = self.open_pair()
        second.Close()
        self.assertTrue(window.modal)
        self.assertEqual(window.focused, "dialog-question-accept")

    def test_a_legacy_dialog_dropped_while_shown_uncovers(self):
        first, second, window = self.open_pair()
        legacy = second._legacy
        second._legacy = None
        del second, legacy
        gc.collect()
        self.assertTrue(window.modal)
        self.assertEqual(window.focused, "dialog-question-accept")

    def test_the_time_limited_question_covers_an_input_dialog(self):
        dialog = self.uiCommon.InputDialog()
        dialog.Open()
        window = self.kit_window(INPUT)
        window.insert_text("dialog-input-field", "nov")
        timed = self.uiCommon.QuestionDialogWithTimeLimit()
        timed.Open("accept the duel?", 10)
        self.assertEqual(self.wndmgr.layers[timed.hWnd], "TOP_MOST")
        self.assertFalse(window.modal)
        self.assertEqual(window.focused, "", "typing does not reach the covered field")
        timed.Close()
        self.assertTrue(window.modal)
        self.assertEqual(window.focused, "dialog-input-field")
        self.assertEqual(window.carets["dialog-input-field"], 3, "the caret is where it was")

    def test_a_kit_dialog_that_opens_while_covered_waits_aside(self):
        first, second, window = self.open_pair()
        popup = self.uiCommon.PopupDialog()
        popup.Open()
        message = self.kit_window(MESSAGE)
        self.assertTrue(message.is_visible())
        self.assertFalse(message.modal)
        self.assertEqual(message.focused, "")
        second.Close()
        self.assertTrue(message.modal)
        self.assertEqual(message.focused, "dialog-message-accept")
        self.assertTrue(window.modal)

    def test_a_legacy_dialog_in_the_ui_layer_covers_nothing(self):
        legacy = self.uiCommon.LegacyQuestionDialog()
        legacy.Open()  # no NovaUI window shown: UI layer, under NovaUI
        self.assertEqual(self.wndmgr.layers[legacy.hWnd], "UI")
        question = self.uiCommon.QuestionDialog()
        question.Open()
        window = self.kit_window(QUESTION)
        self.assertTrue(window.modal)
        self.assertEqual(window.focused, "dialog-question-accept")


class PlainText(KitTest):
    def test_every_caller_string_reaches_the_model_through_plain_text(self):
        word_joiner = "\u2060"
        question = self.uiCommon.QuestionDialog()
        question.SetText("x@ui.LOGIN_ID")
        question.SetAcceptText("@game.UI_OK")
        question.Open()
        window = self.kit_window(QUESTION)
        self.assertEqual(window.model["lines"], ["x@" + word_joiner + "ui.LOGIN_ID"])
        self.assertEqual(window.model["accept_label"], "@" + word_joiner + "game.UI_OK")
        popup = self.networkModule.PopupDialog()
        popup.Open("@ui.X", 0, "@ui.Y")
        message = self.kit_window(MESSAGE)
        self.assertEqual((message.model["lines"], message.model["button"]), (["@" + word_joiner + "ui.X"], "@" + word_joiner + "ui.Y"))
        dialog = self.uiCommon.InputDialogWithDescription()
        dialog.SetTitle("@ui.T")
        dialog.SetDescription("@ui.D")
        dialog.Open()
        model = self.kit_window(INPUT).model
        self.assertEqual((model["title"], model["lines"]), ("@" + word_joiner + "ui.T", ["@" + word_joiner + "ui.D"]))


class Fixtures(KitTest):
    def test_each_kind_window_shows_its_fixture_with_any_owner(self):
        import json
        for module_name, class_name, folder in (("nui_dialog_message", "MessageWindow", "dialog-message"),
                                                ("nui_dialog_question", "QuestionWindow", "dialog-question"),
                                                ("nui_dialog_input", "InputWindow", "dialog-input"),
                                                ("nui_dialog_money", "MoneyWindow", "dialog-money"),
                                                ("nui_pick_money", "PickMoneyWindow", "pick-money")):
            cls = getattr(__import__(module_name), class_name)
            path = os.path.join(ROOT, "..", "nui", "nui", "windows", folder, folder + ".fixture.json")
            with open(path, encoding="utf-8") as file:
                fixture = json.load(file)
            window = cls(object())
            self.assertEqual(set(window.initial_model()), set(fixture[cls.MODEL]), folder)
            self.assertTrue(window.set(**fixture[cls.MODEL]))
            window.show()
            window.destroy()
        self.assertEqual(self.dbg.errors, [])


class EscapeKeyDown(unittest.TestCase):
    """Under a legacy dialog without a field, Escape closes it and the legacy
    key handlers still see the key (game.py's OnKeyDown ends the item drop
    question and the inventory lock, live S3, 2026-10-05). Only the question
    asks the host for that; a dialog with a field must not (a legacy edit line
    keeps the key), and the message keeps the key for itself (legacy's phase
    popup would also leave the select screen)."""

    def body_classes(self, folder):
        import re
        path = os.path.join(ROOT, "..", "nui", "nui", "windows", folder, folder + ".rml")
        with open(path, encoding="utf-8") as file:
            body = re.search(r"<body[^>]*\bclass=\"([^\"]*)\"", file.read())
        return body.group(1).split()

    def test_only_the_question_passes_the_escape_key_down_to_the_legacy_ui(self):
        self.assertIn("nui-escape-passes-key-down", self.body_classes("dialog-question"))
        for folder in ("dialog-message", "dialog-input", "dialog-money", "pick-money"):
            self.assertNotIn("nui-escape-passes-key-down", self.body_classes(folder), folder)


if __name__ == "__main__":
    unittest.main()
