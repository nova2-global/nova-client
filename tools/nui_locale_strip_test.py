"""Tests for the NovaUI locale flag strip (assets/root/nui_locale_strip.py) and
its wiring in uilocaleselector.py: python3 -B -m unittest nui_locale_strip_test
(from tools/).

Plain CPython over the stand-ins of nui_test_support, with the real
uicommon.py, uilocaleselector.py, nui_windows.py and the dialog kit. The
right-to-left path runs LoginWindow.__OnLocaleChanged compiled from
intrologin.py. config/locale.cfg is written in a temporary folder."""
import ast
import inspect
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_test_support as support  # noqa: E402

ROOT = support.ROOT
INTROLOGIN = os.path.join(ROOT, "intrologin.py")
STRIP = "nui/windows/locale-strip/locale-strip.rml"
QUESTION = "nui/windows/dialog-question/dialog-question.rml"
NOVAUI_MODULES = ("nui_dialog_kit", "nui_dialog_message", "nui_dialog_question", "nui_dialog_input",
                  "nui_dialog_money", "nui_pick_money", "nui_locale_strip")


class StripTest(unittest.TestCase):
    flags = "+locale-strip,+dialogs"

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="nui-locale-strip-")
        self.cwd = os.getcwd()
        os.chdir(self.folder)
        os.makedirs("config")
        self.state = support.NuiState()
        self.dbg = support.make_dbg()
        self.setting = support.make_setting(flag=0, windows=self.flags)
        self.rtl = [False]
        self.app = support.stub_module("app", IsRTL=lambda: self.rtl[0], GetTime=lambda: 0.0)
        self.locale = support.LocaleInfo(LOCALE_CHANGE_CONFIRM="Change language to %s and reload the game?",
                                         MONEY_INPUT_DIALOG_SELLPRICE="", NumberToMoneyString=str)
        stub = support.stub_module
        self.modules = support.Modules(
            nui=support.make_nui(self.state), dbg=self.dbg, systemSetting=self.setting,
            wndMgr=support.make_wndmgr(), ui=support.make_legacy_ui(), localeInfo=self.locale, app=self.app,
            ime=stub("ime"), uiScriptLocale=stub("uiScriptLocale", LOCALE_UISCRIPT_PATH=""),
            exception=stub("exception", Abort=self._abort))
        for name in NOVAUI_MODULES:
            self.modules.put(name, None)
            sys.modules.pop(name, None)
        sys.path.insert(0, ROOT)
        self.addCleanup(self._cleanup)
        self.nui_windows = self.modules.load("nui_windows")
        self.uiCommon = self.modules.load("uiCommon", "uicommon.py")
        self.selector = self.modules.load("uilocaleselector")
        self.changed = []

    def _abort(self, message):
        raise AssertionError("exception.Abort(%r)" % message)

    def _cleanup(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.folder, ignore_errors=True)
        sys.path.remove(ROOT)
        for name in NOVAUI_MODULES:
            sys.modules.pop(name, None)
        self.modules.restore()

    def make_strip(self):
        strip = self.selector.LocaleSelector()
        strip.Create(Parent())
        strip.SetLocaleChangedEvent(self.changed.append)
        return strip

    def window(self, document):
        for window in self.state.windows:
            if window.DOCUMENT == document and window._doc:
                return window
        self.fail("no window for %s" % document)


class Parent(object):
    pass


def legacy_methods():
    with open(os.path.join(ROOT, "uilocaleselector.py"), encoding="utf-8") as file:
        tree = ast.parse(file.read())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "LocaleSelector")
    return {node.name: node.args for node in cls.body if isinstance(node, ast.FunctionDef)
            and not (node.name.startswith("__") and node.name.endswith("__"))}


class Facade(StripTest):
    def test_the_facade_has_every_legacy_method_with_a_compatible_signature(self):
        import nui_locale_strip
        facade = nui_locale_strip.LocaleStrip
        for name, args in legacy_methods().items():
            self.assertTrue(hasattr(facade, name), name)
            legacy_params = [arg.arg for arg in args.args][1:]
            params = list(inspect.signature(getattr(facade, name)).parameters.values())[1:]
            self.assertEqual(len(params), len(legacy_params), name)
        for name in ("Show", "Hide", "SetTop", "IsShow"):
            self.assertTrue(callable(getattr(facade, name)), name)
        self.assertEqual(list(inspect.signature(facade.__init__).parameters)[1:], [])

    def test_the_flag_on_makes_the_strip_and_shows_every_flag_with_the_saved_locale(self):
        with open("config/locale.cfg", "w") as file:
            file.write("de")
        strip = self.make_strip()
        import nui_locale_strip
        self.assertIsInstance(strip, nui_locale_strip.LocaleStrip)
        window = strip.nui_window
        self.assertTrue(window.is_visible())
        flags = window.model["flags"]
        self.assertEqual(len(flags), 17)
        self.assertEqual(flags[0], {"code": "ae", "name": "Arabic", "image": "d:/ymir work/ui/intro/login/server_flag_ae.sub"})
        self.assertEqual(window.model["current"], "de")
        self.assertEqual(self.nui_windows.DECISIONS["locale-strip"], "nui")

    def test_without_a_locale_file_the_current_locale_is_en(self):
        self.assertEqual(self.make_strip().nui_window.model["current"], "en")

    def test_set_top_raises_it_without_the_focus(self):
        strip = self.make_strip()
        strip.SetTop()
        self.assertEqual(strip.nui_window.front, 1)

    def test_destroy_closes_the_confirm_and_the_window(self):
        strip = self.make_strip()
        window = strip.nui_window
        window.fire("pick", "de", 0)
        question = self.window(QUESTION)
        strip.Destroy()
        self.assertIsNone(strip.nui_window)
        self.assertIn(("destroy",), window.calls)
        self.assertFalse(question.is_visible())


class Confirm(StripTest):
    def test_a_flag_opens_the_kit_question_with_the_legacy_text(self):
        strip = self.make_strip()
        strip.nui_window.fire("pick", "de", 0)
        question = self.window(QUESTION)
        self.assertTrue(question.is_visible())
        self.assertEqual(question.model["lines"], ["Change language to Deutsch and reload the game?"])
        import nui_dialog_question
        self.assertIsInstance(strip.confirmDialog, nui_dialog_question.QuestionDialog)

    def test_accept_calls_the_event_with_the_code_and_cancel_clears_it(self):
        strip = self.make_strip()
        strip.nui_window.fire("pick", "de", 0)
        question = self.window(QUESTION)
        question.fire("accept")
        self.assertEqual(self.changed, ["de"])
        self.assertFalse(question.is_visible())
        strip.nui_window.fire("pick", "fr", 0)
        question.fire("cancel")
        self.assertIsNone(strip.selectedLocaleCode)
        self.assertEqual(self.changed, ["de"])

    def test_escape_on_the_question_changes_nothing(self):
        strip = self.make_strip()
        strip.nui_window.fire("pick", "de", 0)
        question = self.window(QUESTION)
        self.assertTrue(question.key("", support.KEY_ESCAPE))
        self.assertEqual(self.changed, [])

    def test_only_the_left_button_picks(self):
        strip = self.make_strip()
        strip.nui_window.fire("pick", "de", 1)
        self.assertIsNone(strip.confirmDialog)


class LegacyConfirm(StripTest):
    flags = "+locale-strip"

    def test_with_the_dialogs_off_the_confirm_is_the_legacy_question(self):
        strip = self.make_strip()
        strip.nui_window.fire("pick", "de", 0)
        self.assertIsInstance(strip.confirmDialog, self.uiCommon.LegacyQuestionDialog)
        self.assertEqual(strip.confirmDialog.textLine.text, "Change language to Deutsch and reload the game?")


class FlagOff(StripTest):
    flags = ""

    def test_the_flag_off_gives_the_legacy_class(self):
        strip = self.selector.LocaleSelector()
        self.assertIsInstance(strip, self.selector.LegacyLocaleSelector)
        self.assertNotIn("nui_locale_strip", [name for name in sys.modules if sys.modules[name] is not None])
        self.assertEqual(self.nui_windows.DECISIONS["locale-strip"], "legacy: flag off")


class RightToLeft(StripTest):
    def compile_window(self):
        with open(INTROLOGIN, encoding="utf-8") as file:
            source = file.read()
        tree = ast.parse(source)
        window = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "LoginWindow")
        method = next(node for node in window.body if isinstance(node, ast.FunctionDef) and node.name == "__OnLocaleChanged")
        lines = source.splitlines()
        selector = self.selector
        test = self

        class Base(object):
            def __init__(self):
                self.localeSelector = None
                self.connectBoard = None
                self.idEditLine = None
                self.pwdEditLine = None
                self.stream = support.stub_module("stream", popupWindow=support.Widget(), CreatePopupDialog=lambda: None)
                self.Open()

            def Open(self):
                if not self.localeSelector:
                    self.localeSelector = selector.LocaleSelector()
                    self.localeSelector.Create(self)

            def Close(self):
                if self.localeSelector:
                    self.localeSelector.Destroy()
                    self.localeSelector = None

            def _LoginWindow__RefreshServerList(self):
                pass

            def _LoginWindow__OpenServerBoard(self):
                pass

        def reload_locale():
            with open("config/locale.cfg") as file:
                code = file.read()
            test.rtl[0] = code == "ae"
            test.state.rtl = test.rtl[0]
            return True

        self.app.ReloadLocale = reload_locale
        nui_login = support.stub_module("nui_login", on_login_board=lambda win: None, typed_values=lambda win: None,
                                        restore_typed=lambda win, user: False)
        namespace = {"Base": Base, "app": self.app, "nui_login": nui_login}
        code = "class LoginWindow(Base):\n" + "\n".join(lines[method.lineno - 1:method.end_lineno]) + "\n"
        exec(compile(code, INTROLOGIN, "exec"), namespace)
        return namespace["LoginWindow"]

    def test_a_change_to_ae_rebuilds_the_legacy_strip_and_back_again(self):
        Window = self.compile_window()
        win = Window()
        import nui_locale_strip
        novaui = win.localeSelector
        self.assertIsInstance(novaui, nui_locale_strip.LocaleStrip)
        window = novaui.nui_window
        win._LoginWindow__OnLocaleChanged("ae")
        self.assertIsInstance(win.localeSelector, self.selector.LegacyLocaleSelector)
        self.assertIn(("destroy",), window.calls)
        self.assertEqual(self.nui_windows.DECISIONS["locale-strip"], "legacy: right-to-left locale")
        win._LoginWindow__OnLocaleChanged("en")
        self.assertIsInstance(win.localeSelector, nui_locale_strip.LocaleStrip)
        self.assertEqual(self.nui_windows.DECISIONS["locale-strip"], "nui")
        self.assertEqual(win.localeSelector.nui_window.model["current"], "en")

    def test_the_change_runs_inside_the_kit_questions_accept(self):
        Window = self.compile_window()
        win = Window()
        win.localeSelector.SetLocaleChangedEvent(win._LoginWindow__OnLocaleChanged)
        win.localeSelector.nui_window.fire("pick", "ae", 0)
        self.window(QUESTION).fire("accept")
        self.assertIsInstance(win.localeSelector, self.selector.LegacyLocaleSelector)


class Wiring(unittest.TestCase):
    def test_uilocaleselector_rebinds_its_name_to_the_factory(self):
        with open(os.path.join(ROOT, "uilocaleselector.py"), encoding="utf-8") as file:
            source = file.read()
        self.assertIn("import nui_windows\n", source)
        self.assertTrue(source.rstrip().endswith(
            'LocaleSelector = nui_windows.factory("locale-strip", LegacyLocaleSelector, "nui_locale_strip.LocaleStrip")'))


if __name__ == "__main__":
    unittest.main()
