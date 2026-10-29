"""Tests for assets/root/nui_login.py and its hooks in assets/root/intrologin.py:
python3 -B -m unittest nui_login_test (from tools/; -B keeps __pycache__ out of
the repository).

Plain CPython, no client: nui, dbg, systemSetting and the legacy modules are
stand-ins. The hooked LoginWindow methods are compiled from intrologin.py
itself onto a stand-in window, so the flows below run the real hook calls,
with the board and without it (the legacy path)."""
import ast
import os
import shutil
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_test_support as support  # noqa: E402
from nui_test_support import NuiState, make_dbg, make_setting  # noqa: E402,F401 (shared stand-ins)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = support.ROOT
NUI_LOGIN = os.path.join(ROOT, "nui_login.py")
INTROLOGIN = os.path.join(ROOT, "intrologin.py")
LOGIN_DOCUMENT = "nui/windows/login/login.rml"
PICKER_DOCUMENT = "nui/windows/theme-picker/theme-picker.rml"
KEYBOARD_DOCUMENT = "nui/windows/virtual-keyboard/virtual-keyboard.rml"
THEMES = support.THEMES

USER = "novaverify01"
PASSWORD = "Nv-login-42"
ID_FIELD = "login-user"
PASSWORD_FIELD = "login-password"

_MISSING = support.MISSING


# --- stand-ins ------------------------------------------------------------------

def make_nui(state):
    """The shared stand-in nui (nui_test_support.make_nui), with the login
    board's autofocus field and its fields' change events: the first show()
    gives the ID field the focus, hide() takes it off, and a later show()
    leaves it off, as NuiRuntime does."""
    state.autofocus.setdefault(LOGIN_DOCUMENT, ID_FIELD)
    state.field_events.setdefault((LOGIN_DOCUMENT, ID_FIELD), "user_edit")
    state.field_events.setdefault((LOGIN_DOCUMENT, PASSWORD_FIELD), "password_edit")
    return support.make_nui(state)


class Randoms(object):
    """app.GetRandom: a fixed sequence, recorded."""

    def __init__(self):
        self.calls = []

    def __call__(self, low, high):
        self.calls.append((low, high))
        return (len(self.calls) * 7) % (high - low + 1) + low


def keyboard_locale():
    return support.LocaleInfo(
        VIRTUAL_KEY_ALPHABET_LOWERS=r"[1234567890]/qwertyuiop\=asdfghjkl;`'zxcvbnm.,",
        VIRTUAL_KEY_ALPHABET_UPPERS=r"{1234567890}?QWERTYUIOP|+ASDFGHJKL:~'ZXCVBNM<>",
        VIRTUAL_KEY_SYMBOLS="!@#$%^&*()_+|{}:'<>?~",
        VIRTUAL_KEY_NUMBERS="1234567890-=\\[];',./`")


def load_nui_login(nui_module, setting, dbg_module, app=None, snd=None):
    """nui_login.py as a fresh module over the given stand-ins (nui_module
    None: `import nui` fails), with the real nui_windows.py,
    nui_theme_picker.py and nui_virtual_keyboard.py loaded over the same
    stand-ins for its imports."""
    modules = support.Modules(
        dbg=dbg_module, systemSetting=setting, wndMgr=support.make_wndmgr(),
        app=app or support.stub_module("app", GetRandom=Randoms(), IsRTL=lambda: False),
        snd=snd or support.stub_module("snd", PlaySound=lambda name: None),
        localeInfo=keyboard_locale())
    modules.put("nui", nui_module)
    try:
        modules.load("nui_windows")
        for name in ("nui_theme_picker", "nui_virtual_keyboard"):
            try:
                modules.load(name)
            except ImportError:
                pass  # no nui module: nui_login's own imports fail the same way
        # The saved accounts never reach the repository's config/: the tests
        # that keep accounts point PATH at a temporary file of their own.
        modules.load("nui_accounts").PATH = os.devnull
        modules.load("nui_links")
        module = modules.load("nui_login")
    finally:
        modules.restore()
    return module


class Widget(object):
    """A legacy window part: shown or not, focused or not, with a text."""

    def __init__(self, shown=True, text=""):
        self.shown = shown
        self.focused = False
        self.text = text
        self.set_focus_calls = 0

    def Show(self):
        self.shown = True

    def Hide(self):
        self.shown = False

    def IsShow(self):
        return self.shown

    def SetFocus(self):
        self.set_focus_calls += 1
        self.focused = True

    def KillFocus(self):
        self.focused = False

    def IsFocus(self):
        return self.focused

    def SetText(self, text):
        self.text = text

    def GetText(self):
        return self.text

    def SetPosition(self, x, y):
        pass

    def SelectItem(self, index):
        pass


class Popup(object):
    """networkModule.PopupDialog's Open, Close and CloseEvent rules."""

    def __init__(self):
        self.shown = False
        self.CloseEvent = 0
        self.message = None

    def IsShow(self):
        return self.shown

    def Open(self, message, event=0, button_name=None):
        if self.shown:
            self.Close()
        self.CloseEvent = event
        self.message = message
        self.shown = True

    def Close(self):
        if not self.shown:
            self.CloseEvent = 0
            return
        self.shown = False
        if 0 != self.CloseEvent:
            self.CloseEvent()
            self.CloseEvent = 0


class Stream(object):
    """networkModule.MainStream as far as the login window uses it."""

    def __init__(self):
        self.popupWindow = Popup()
        self.isAutoLogin = 0
        self.login_info = []
        self.connects = 0
        self.on_connect = None  # what the network does inside Connect()

    def SetLoginInfo(self, user, password):
        self.login_info.append((user, password))

    def Connect(self):
        self.connects += 1
        if self.on_connect:
            self.on_connect()


class LocaleInfo(object):
    def __getattr__(self, name):
        return name


def _stub_module(name, **members):
    module = types.ModuleType(name)
    for key, value in members.items():
        setattr(module, key, value)
    return module


class WindowBase(object):
    """What the compiled LoginWindow methods need besides themselves."""

    def __init__(self, stream):
        self.stream = stream
        self.nuiBoard = None  # hook H2
        self.timeOutMsg = False
        self.connectBoard = Widget()
        self.loginBoard = Widget()
        self.virtualKeyboard = Widget()
        self.serverBoard = Widget(shown=False)
        self.serverList = Widget()
        self.channelList = Widget()
        self.serverExitButton = Widget()
        self.serverInfo = Widget()
        self.idEditLine = Widget()
        self.pwdEditLine = Widget()
        self.xServerBoard = 0
        self.yServerBoard = 0
        self.loginFailureMsgDict = {"WRONGPWD": "LOGIN_FAILURE_WRONG_PASSWORD"}
        self.loginFailureFuncDict = {"WRONGPWD": self._LoginWindow__DisconnectAndInputPassword}

    def _LoginWindow__LoadChannelInfo(self):
        return -1, -1, -1

    def _LoginWindow__ServerIDToServerIndex(self, region, server):
        return -1

    def _LoginWindow__ChannelIDToChannelIndex(self, channel):
        return channel - 1

    def _LoginWindow__DisconnectAndInputPassword(self):
        self.SetPasswordEditLineFocus()


# The intrologin.py methods the flows run, hooks included.
COMPILED = ("SetIDEditLineFocus", "SetPasswordEditLineFocus", "OnConnectFailure", "OnLoginFailure",
            "Connect", "PopupDisplayMessage", "PopupNotifyMessage", "SameLogin_OpenUI", "EmptyFunc",
            "_LoginWindow__OpenLoginBoard", "_LoginWindow__OpenServerBoard", "_LoginWindow__SetServerInfo",
            "OnExit")


def compile_login_window(nui_login):
    """introLogin.LoginWindow with the methods in COMPILED taken from
    intrologin.py, over WindowBase and stand-in modules."""
    with open(INTROLOGIN, encoding="utf-8") as file:
        source = file.read()
    tree = ast.parse(source)
    window = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "LoginWindow")
    methods = {node.name: node for node in window.body if isinstance(node, ast.FunctionDef)}
    lines = source.splitlines()
    body = []
    for name in COMPILED:
        plain = name.replace("_LoginWindow__", "__")
        node = methods[plain]
        body.extend(lines[node.lineno - 1:node.end_lineno])
        body.append("")
    namespace = {
        "WindowBase": WindowBase,
        "nui_login": nui_login,
        # The server board hooks do nothing here; nui_server_board_test runs them.
        "nui_server_board": _stub_module("nui_server_board", **{name: (lambda *args: None) for name in (
            "open_board", "close_board", "enter", "leave", "refresh_servers", "refresh_channels")}),
        "localeInfo": LocaleInfo(),
        "snd": _stub_module("snd", PlaySound=lambda name: None),
        "app": _stub_module("app", loggined=False, Exit=lambda: None),
        "net": _stub_module("net", SetServerInfo=lambda text: None, Disconnect=lambda: None),
        "wndMgr": _stub_module("wndMgr", GetScreenHeight=lambda: 768),
        "SKIP_LOGIN_PHASE": False,
        "SKIP_LOGIN_PHASE_SUPPORT_CHANNEL": False,
    }
    code = "class LoginWindow(WindowBase):\n" + "\n".join(body) + "\n"
    exec(compile(code, INTROLOGIN, "exec"), namespace)
    return namespace["LoginWindow"]


class Choices(object):
    """The callbacks intrologin.py hands open_board()."""

    def __init__(self):
        self.chosen = 0
        self.exited = 0

    def choose(self):
        self.chosen += 1

    def exit(self):
        self.exited += 1


class ControllerTest(unittest.TestCase):
    """nui_login over the stand-ins, with the flag on unless a test says
    otherwise."""

    def setUp(self):
        self.state = NuiState()
        self.nui = make_nui(self.state)
        self.dbg = make_dbg()
        self.setting = make_setting(1)
        self.load()

    def load(self, nui_module=_MISSING):
        self.m = load_nui_login(self.nui if nui_module is _MISSING else nui_module, self.setting, self.dbg)
        self.Window = compile_login_window(self.m)
        self.choices = Choices()

    def open_window(self):
        """LoginWindow.Open as far as the board goes: H3, then the entry
        decision's __OpenLoginBoard (H13)."""
        win = self.Window(Stream())
        win.nuiBoard = self.m.open_board(win, self.choices.choose, self.choices.exit)
        return win

    def open_board(self):
        win = self.open_window()
        self.assertIsNotNone(win.nuiBoard, self.m.LAST_DECISION)
        win._LoginWindow__OpenLoginBoard()
        return win, win.nuiBoard

    def type_values(self, board, user=USER, password=PASSWORD):
        board.on_user_edit(user, False)
        board.on_password_edit(password, False)


# --- T6: the decision in open_board --------------------------------------------

class TheDecision(ControllerTest):
    def test_with_the_flag_off_the_legacy_board_stays(self):
        self.setting = make_setting(0)
        self.load()
        win = self.open_window()
        self.assertIsNone(win.nuiBoard)
        self.assertEqual(self.m.LAST_DECISION, "legacy: flag off")
        self.assertTrue(win.connectBoard.IsShow() and win.loginBoard.IsShow())

    def test_an_exe_without_the_flag_binding_keeps_the_legacy_board(self):
        self.setting = make_setting(has_binding=False)
        self.load()
        self.assertIsNone(self.open_window().nuiBoard)
        self.assertEqual(self.m.LAST_DECISION, "legacy: flag off")

    def test_without_novaui_the_legacy_board_stays(self):
        self.state.available = False
        self.assertIsNone(self.open_window().nuiBoard)
        self.assertEqual(self.m.LAST_DECISION, "legacy: NovaUI unavailable")

    def test_without_the_nui_module_the_legacy_board_stays(self):
        self.load(nui_module=None)
        self.assertFalse(self.m.nui.is_available(), "a stand-in that offers nothing")
        self.assertIsNone(self.open_window().nuiBoard)
        self.assertEqual(self.m.LAST_DECISION, "legacy: NovaUI unavailable")

    def test_a_right_to_left_locale_keeps_the_legacy_board(self):
        self.state.rtl = True
        self.assertIsNone(self.open_window().nuiBoard)
        self.assertEqual(self.m.LAST_DECISION, "legacy: right-to-left locale")

    def test_a_document_that_did_not_load_keeps_the_legacy_board_and_says_so_once(self):
        self.state.loads = False
        win = self.open_window()
        self.assertIsNone(win.nuiBoard)
        self.assertEqual(self.m.LAST_DECISION, "legacy: the document did not load")
        self.assertEqual(self.dbg.errors, ["nui_windows: login: the document did not load; using the legacy window"])
        self.assertTrue(win.connectBoard.IsShow() and win.loginBoard.IsShow())

    def test_the_board_hides_the_legacy_parts_and_takes_the_focus_from_an_edit_line(self):
        win = self.Window(Stream())
        win.idEditLine.SetFocus()
        board = self.m.open_board(win, self.choices.choose, self.choices.exit)
        self.assertIsNotNone(board)
        self.assertEqual(self.m.LAST_DECISION, "nui")
        self.assertFalse(win.connectBoard.IsShow())
        self.assertFalse(win.loginBoard.IsShow())
        self.assertFalse(win.virtualKeyboard.IsShow())
        self.assertFalse(win.idEditLine.IsFocus())
        self.assertFalse(board.is_visible(), "hidden until the login board opens")
        self.assertEqual(self.dbg.errors, [])


# --- T6: submit, Enter and errors ------------------------------------------------

class Submitting(ControllerTest):
    def test_an_empty_id_shows_its_error_and_focuses_the_id_field(self):
        win, board = self.open_board()
        board.on_password_edit(PASSWORD, False)
        board.on_submit()
        self.assertEqual(board.model["error"], "@game.LOGIN_INPUT_ID")
        self.assertEqual(board.model["error_on"], "user")
        self.assertEqual(board.focused, ID_FIELD)
        self.assertEqual(win.stream.login_info, [])

    def test_an_empty_password_shows_its_error_and_focuses_the_password_field(self):
        win, board = self.open_board()
        board.on_user_edit(USER, False)
        board.on_submit()
        self.assertEqual(board.model["error"], "@game.LOGIN_INPUT_PASSWORD")
        self.assertEqual(board.model["error_on"], "password")
        self.assertEqual(board.focused, PASSWORD_FIELD)
        self.assertEqual(win.stream.login_info, [])

    def test_valid_values_reach_the_legacy_connect_once(self):
        win, board = self.open_board()
        self.type_values(board)
        board.on_submit()
        self.assertEqual(win.stream.login_info, [(USER, PASSWORD)])
        self.assertEqual(win.stream.connects, 1)
        self.assertEqual(board.model["error"], "")

    def test_square_brackets_are_taken_out_as_the_legacy_lines_did(self):
        win, board = self.open_board()
        self.type_values(board, "ab[c]", "p[w]d")
        board.on_submit()
        self.assertEqual(win.stream.login_info, [("abc", "pwd")])

    def test_values_are_cut_to_the_legacy_limits(self):
        win, board = self.open_board()
        self.type_values(board, "u" * 25, "p" * 20)
        board.on_submit()
        self.assertEqual(win.stream.login_info, [("u" * 19, "p" * 16)])

    def test_a_board_that_is_not_shown_submits_nothing(self):
        win, board = self.open_board()
        self.type_values(board)
        self.m.before_popup(win)
        board.on_submit()
        self.assertEqual(win.stream.login_info, [])

    def test_enter_in_the_id_field_moves_to_the_password_field(self):
        win, board = self.open_board()
        board.on_user_edit(USER, True)
        self.assertEqual(board.focused, PASSWORD_FIELD)
        self.assertEqual(win.stream.login_info, [])

    def test_enter_in_the_password_field_submits(self):
        win, board = self.open_board()
        board.on_user_edit(USER, False)
        board.on_password_edit(PASSWORD, True)
        self.assertEqual(win.stream.login_info, [(USER, PASSWORD)])

    def test_typing_clears_only_its_own_fields_error(self):
        win, board = self.open_board()
        board.on_submit()
        self.assertEqual(board.model["error_on"], "user")
        board.on_password_edit("x", False)
        self.assertEqual(board.model["error_on"], "user", "the password field leaves the ID error")
        board.on_user_edit("a", False)
        self.assertEqual((board.model["error"], board.model["error_on"]), ("", ""))

    def test_the_same_value_twice_changes_nothing(self):
        win, board = self.open_board()
        board.on_user_edit(USER, False)
        board.on_user_edit(USER, False)
        self.assertEqual(board.typed_values(), (USER, ""))

    def test_choose_and_exit_reach_their_legacy_handlers(self):
        win, board = self.open_board()
        board.on_choose_server()
        board.on_exit()
        self.assertEqual((self.choices.chosen, self.choices.exited), (1, 1))

    def test_the_password_never_enters_the_model(self):
        win, board = self.open_board()
        win.stream.on_connect = win.OnConnectFailure
        self.type_values(board)
        board.on_password_edit(PASSWORD, True)
        win.stream.popupWindow.Close()
        board.on_reload()
        for call in board.calls:
            if call[0] == "set":
                self.assertNotIn(PASSWORD, call[1].values())
        self.assertNotIn(PASSWORD, board.model.values())
        self.assertEqual(self.dbg.errors, [])


# --- T6: popups and the legacy callbacks ----------------------------------------

class Popups(ControllerTest):
    def test_before_popup_hides_the_board(self):
        win, board = self.open_board()
        self.assertTrue(board.is_visible())
        self.m.before_popup(win)
        self.assertFalse(board.is_visible())

    def test_the_wrapper_brings_the_board_back_then_runs_the_callback(self):
        win, board = self.open_board()
        seen = []
        wrapper = self.m.after_popup(win, lambda: seen.append(board.is_visible()))
        self.m.before_popup(win)
        wrapper()
        self.assertEqual(seen, [True])
        self.assertTrue(board.is_visible())

    def test_without_a_board_the_callback_is_handed_back_as_it_is(self):
        win = self.Window(Stream())
        callback = win.EmptyFunc
        self.assertEqual(self.m.after_popup(win, 0), 0)
        self.assertIs(self.m.after_popup(win, callback), callback)

    def test_the_server_board_stops_the_board_from_coming_back(self):
        win, board = self.open_board()
        wrapper = self.m.after_popup(win, 0)
        self.m.before_popup(win)
        win._LoginWindow__OpenServerBoard()
        wrapper()
        self.assertFalse(board.is_visible())
        self.assertTrue(win.serverBoard.IsShow())

    def test_after_close_board_a_wrapper_does_nothing_but_its_callback(self):
        win, board = self.open_board()
        seen = []
        wrapper = self.m.after_popup(win, lambda: seen.append("callback"))
        self.m.close_board(win)
        self.assertIsNone(win.nuiBoard)
        self.assertIn(("destroy",), board.calls)
        wrapper()
        self.assertEqual(seen, ["callback"])
        self.assertFalse(board.is_visible())

    def test_a_popup_open_before_the_board_holds_it_back_until_it_closes(self):
        win = self.open_window()
        win.stream.popupWindow.Open("LOGIN_FAILURE_SAMELOGIN", 0)
        win._LoginWindow__OpenLoginBoard()
        board = win.nuiBoard
        self.assertFalse(board.is_visible())
        win.stream.popupWindow.Close()
        self.assertTrue(board.is_visible())
        self.assertEqual(board.focused, ID_FIELD)

    def test_auto_login_keeps_the_board_hidden(self):
        win = self.open_window()
        win.stream.isAutoLogin = 1
        win._LoginWindow__OpenLoginBoard()
        self.assertFalse(win.nuiBoard.is_visible())
        self.assertFalse(win.connectBoard.IsShow(), "the legacy boards stay off too")

    def test_a_focus_asked_for_while_hidden_comes_with_the_next_show(self):
        win, board = self.open_board()
        board.on_user_edit(USER, False)
        self.m.before_popup(win)
        self.assertTrue(self.m.focus_field(win, "user"))
        self.assertEqual(board.focused, None)
        board.resume()
        self.assertEqual(board.focused, ID_FIELD, "the request wins over the default")

    def test_a_connect_that_fails_at_once_ends_at_the_legacy_popup_with_the_board_hidden(self):
        # No server and no GNS root key: OnConnectFailure runs inside Connect,
        # inside the submit handler.
        win, board = self.open_board()
        win.stream.on_connect = win.OnConnectFailure
        self.type_values(board)
        board.calls[:] = []
        board.on_password_edit(PASSWORD, True)
        popup = win.stream.popupWindow
        self.assertEqual(win.stream.login_info, [(USER, PASSWORD)])
        self.assertTrue(popup.IsShow())
        self.assertEqual(popup.message, "LOGIN_CONNECT_FAILURE")
        self.assertFalse(board.is_visible())
        self.assertIsNone(board.focused, "nothing takes keys while the popup is up")
        self.assertEqual([call[0] for call in board.calls if call[0] in ("show", "hide")], ["hide", "show", "hide"])
        # Enter closes the popup; SetPasswordEditLineFocus is the legacy callback.
        popup.Close()
        self.assertTrue(board.is_visible())
        self.assertEqual(board.focused, PASSWORD_FIELD)
        self.assertEqual(win.pwdEditLine.set_focus_calls, 0, "the hidden EditLine is never focused")
        self.assertEqual(win.stream.connects, 1, "closing the popup starts no login")

    def test_a_connect_that_fails_later_keeps_the_board_hidden_until_the_failure_closes(self):
        win, board = self.open_board()
        self.type_values(board)
        board.on_submit()
        popup = win.stream.popupWindow
        self.assertEqual(popup.message, "LOGIN_CONNETING")
        self.assertFalse(board.is_visible())
        win.OnConnectFailure()
        self.assertEqual(popup.message, "LOGIN_CONNECT_FAILURE")
        self.assertFalse(board.is_visible())
        popup.Close()
        self.assertTrue(board.is_visible())
        self.assertEqual(board.focused, PASSWORD_FIELD)

    def test_a_wrong_password_brings_the_board_back_on_the_password_field(self):
        win, board = self.open_board()
        self.type_values(board)
        board.on_submit()
        win.OnLoginFailure("WRONGPWD")
        popup = win.stream.popupWindow
        self.assertEqual(popup.message, "LOGIN_FAILURE_WRONG_PASSWORD")
        popup.Close()
        self.assertTrue(board.is_visible())
        self.assertEqual(board.focused, PASSWORD_FIELD)

    def test_a_display_message_hides_the_board_while_it_is_up(self):
        win, board = self.open_board()
        win.PopupDisplayMessage("LOGIN_PROCESSING")
        self.assertFalse(board.is_visible())
        win.OnExit()
        self.assertTrue(board.is_visible())
        self.assertEqual(board.focused, ID_FIELD, "no ID typed yet")

    def test_choose_hands_over_to_the_server_board_and_back(self):
        win, board = self.open_board()
        win._LoginWindow__OpenServerBoard()
        self.assertFalse(board.is_visible())
        self.assertIs(self.m.on_login_board(win), False)
        win._LoginWindow__OpenLoginBoard()
        self.assertTrue(board.is_visible())
        self.assertEqual(board.focused, ID_FIELD)
        self.assertFalse(win.virtualKeyboard.IsShow())
        self.assertEqual(win.idEditLine.set_focus_calls, 0)

    def test_the_server_text_reaches_the_model(self):
        win, board = self.open_board()
        win._LoginWindow__SetServerInfo("Nova, Channel 1 ")
        self.assertEqual(board.model["server"], "Nova, Channel 1 ")
        self.m.set_server(win, "K:127.0.0.1:39001")
        self.assertEqual(board.model["server"], "K:127.0.0.1:39001")


# --- T6: reloads and the locale helpers -------------------------------------------

class ReloadsAndLocales(ControllerTest):
    def test_a_reload_puts_the_id_back_forgets_the_password_and_focuses(self):
        win, board = self.open_board()
        self.type_values(board)
        board.on_reload()
        self.assertEqual(board.model["user"], USER)
        self.assertEqual(board.typed_values(), (USER, ""))
        self.assertEqual(board.focused, PASSWORD_FIELD)

    def test_a_reload_of_an_empty_board_focuses_the_id_field(self):
        win, board = self.open_board()
        board.focus(PASSWORD_FIELD)
        board.on_reload()
        self.assertEqual(board.focused, ID_FIELD)

    def test_the_locale_helpers_carry_the_id(self):
        win, board = self.open_board()
        self.type_values(board)
        self.assertIs(self.m.on_login_board(win), True)
        self.assertEqual(self.m.typed_values(win), (USER, PASSWORD))
        self.assertTrue(self.m.restore_typed(win, "other"))
        self.assertEqual(board.model["user"], "other")
        self.assertEqual(board.typed_values()[0], "other")

    def test_without_a_board_the_locale_helpers_answer_the_legacy_way(self):
        win = self.Window(Stream())
        self.assertIsNone(self.m.on_login_board(win))
        self.assertIsNone(self.m.typed_values(win))
        self.assertFalse(self.m.restore_typed(win, USER))
        self.assertFalse(self.m.focus_field(win, "user"))
        self.assertFalse(self.m.enter_login_board(win))

    def test_a_second_open_replaces_the_first_board(self):
        win, first = self.open_board()
        win.nuiBoard = self.m.open_board(win, self.choices.choose, self.choices.exit)
        self.assertIn(("destroy",), first.calls, "one board per model name")
        self.assertIsNot(win.nuiBoard, first)


# --- T6: the legacy path is unchanged ---------------------------------------------

class LegacyPath(ControllerTest):
    def setUp(self):
        super(LegacyPath, self).setUp()
        self.setting = make_setting(0)
        self.load()
        self.win = self.open_window()
        self.assertIsNone(self.win.nuiBoard)

    def test_connect_hands_the_popup_the_legacy_callback_itself(self):
        self.win.Connect(USER, PASSWORD)
        popup = self.win.stream.popupWindow
        self.assertEqual(popup.message, "LOGIN_CONNETING")
        self.assertEqual(popup.CloseEvent, self.win.SetPasswordEditLineFocus)

    def test_the_popup_helpers_open_what_they_opened_before(self):
        self.win.PopupDisplayMessage("LOGIN_PROCESSING")
        self.assertEqual(self.win.stream.popupWindow.CloseEvent, 0)
        self.win.PopupNotifyMessage("LOGIN_INPUT_ID", self.win.SetIDEditLineFocus)
        self.assertEqual(self.win.stream.popupWindow.CloseEvent, self.win.SetIDEditLineFocus)
        self.win.SameLogin_OpenUI()
        self.assertEqual(self.win.stream.popupWindow.CloseEvent, 0)

    def test_the_focus_helpers_focus_the_edit_lines(self):
        self.win.SetIDEditLineFocus()
        self.win.SetPasswordEditLineFocus()
        self.assertEqual((self.win.idEditLine.set_focus_calls, self.win.pwdEditLine.set_focus_calls), (1, 1))

    def test_the_login_board_opens_the_legacy_parts(self):
        self.win.connectBoard.Hide()
        self.win.loginBoard.Hide()
        self.win.virtualKeyboard.Hide()
        self.win._LoginWindow__OpenLoginBoard()
        self.assertTrue(self.win.connectBoard.IsShow())
        self.assertTrue(self.win.loginBoard.IsShow())
        self.assertTrue(self.win.virtualKeyboard.IsShow())
        self.assertEqual(self.win.idEditLine.set_focus_calls, 1)

    def test_every_hook_answers_the_legacy_value(self):
        m, win = self.m, self.win
        self.assertIsNone(m.close_board(win))
        self.assertFalse(m.enter_login_board(win))
        self.assertIsNone(m.leave_login_board(win))
        self.assertIsNone(m.set_server(win, "x"))
        self.assertIsNone(m.before_popup(win))
        self.assertEqual(m.after_popup(win, 0), 0)
        self.assertFalse(m.focus_field(win, "password"))
        self.assertIsNone(m.on_login_board(win))
        self.assertIsNone(m.typed_values(win))
        self.assertFalse(m.restore_typed(win, USER))


# --- The intro theme picker ----------------------------------------------------

class ThemePicker(ControllerTest):
    def test_the_picker_opens_after_the_ambience_and_before_the_board_which_keeps_the_focus(self):
        win, board = self.open_board()
        self.assertIsNotNone(win.nuiPicker)
        self.assertTrue(win.nuiPicker.is_visible())
        self.assertEqual([name for name, _ in self.state.shows], ["IntroAmbient", "ThemePicker", "LoginBoard"])
        self.assertEqual(board.focused, ID_FIELD)
        self.assertEqual(self.dbg.errors, [])

    def test_the_picker_lists_the_themes_and_marks_the_one_in_use(self):
        self.state.theme = "classic"
        win, _ = self.open_board()
        self.assertEqual(win.nuiPicker.model, {"themes": [{"id": i, "label": l} for i, l in THEMES], "current": "classic"})

    def test_without_player_themes_there_is_no_picker_and_no_error(self):
        self.state.themes = []
        win, board = self.open_board()
        self.assertIsNone(getattr(win, "nuiPicker", None))
        self.assertTrue(board.is_visible())
        self.assertEqual(self.dbg.errors, [])

    def test_a_picker_that_does_not_load_leaves_the_board_running_and_says_so_once(self):
        self.state.failing.add(PICKER_DOCUMENT)
        win, board = self.open_board()
        self.assertIsNone(getattr(win, "nuiPicker", None))
        self.assertTrue(board.is_visible())
        self.assertEqual(len(self.dbg.errors), 1)
        self.assertIn(PICKER_DOCUMENT, self.dbg.errors[0])
        self.assertEqual(self.m.LAST_DECISION, "nui")

    def test_a_popup_hides_the_picker_and_its_close_brings_it_back(self):
        win, board = self.open_board()
        picker = win.nuiPicker
        wrapper = self.m.after_popup(win, 0)
        self.m.before_popup(win)
        self.assertFalse(picker.is_visible())
        wrapper()
        self.assertTrue(picker.is_visible())
        self.assertTrue(board.is_visible())
        shows = [name for name, _ in self.state.shows]
        self.assertEqual(shows[-3:], ["IntroAmbient", "ThemePicker", "LoginBoard"], "the board comes back on top")

    def test_closing_the_board_destroys_the_picker(self):
        win, board = self.open_board()
        picker = win.nuiPicker
        self.m.close_board(win)
        self.assertIsNone(win.nuiPicker)
        self.assertIn(("destroy",), picker.calls)
        self.assertFalse(picker.is_visible())

    def test_a_left_press_applies_the_theme_and_the_selection_follows(self):
        win, board = self.open_board()
        picker = win.nuiPicker
        picker.on_pick("classic", 0)
        self.assertEqual(self.state.theme, "classic")
        self.assertEqual(picker.model["current"], "classic")
        self.assertTrue(board.is_visible())
        self.assertEqual(board.focused, ID_FIELD, "the press leaves the board's focus where it was")

    def test_other_buttons_do_nothing_and_a_refused_id_is_logged_not_raised(self):
        win, _ = self.open_board()
        picker = win.nuiPicker
        picker.on_pick("classic", 1)
        self.assertEqual(self.state.theme, "modern-dark")
        picker.on_pick("sepia", 0)
        self.assertEqual(self.state.theme, "modern-dark")
        self.assertEqual(len(self.dbg.errors), 1)
        self.assertIn("nui_theme_picker", self.dbg.errors[0])

    def test_without_the_nui_module_there_is_no_picker(self):
        self.load(nui_module=None)
        self.assertIsNone(self.m.nui_theme_picker)
        self.assertIsNone(self.open_window().nuiBoard)


# --- Wave 1: the virtual keyboard, the strip and the picker's place ------------------

class KeyboardWithTheBoard(ControllerTest):
    def setUp(self):
        super(KeyboardWithTheBoard, self).setUp()
        self.setting = make_setting(1, windows="+virtual-keyboard")
        self.load()

    def test_the_keyboard_comes_with_the_board_and_the_board_knows(self):
        win, board = self.open_board()
        keyboard = win.nuiKeyboard
        self.assertIsNotNone(keyboard)
        self.assertTrue(keyboard.is_visible())
        self.assertIs(board.model["keyboard"], True)
        self.assertEqual(self.m.nui_windows.DECISIONS["virtual-keyboard"], "nui")
        self.assertEqual(self.dbg.errors, [])

    def test_the_show_order_is_ambience_picker_keyboard_then_the_board(self):
        win, board = self.open_board()
        self.assertEqual([name for name, _ in self.state.shows], ["IntroAmbient", "ThemePicker", "VirtualKeyboard", "LoginBoard"])
        self.assertEqual(board.focused, ID_FIELD, "the board keeps the focus")

    def test_the_keyboard_is_raised_each_time_it_shows_so_the_embers_stay_under_it(self):
        # It never takes the focus, so a show does not raise it, and RmlUi
        # stacks the documents nothing raised in load order: the ambience,
        # made after the keyboard, would draw its embers over the keys.
        win, board = self.open_board()
        keyboard = win.nuiKeyboard
        steps = lambda: [call[0] for call in keyboard.calls if call[0] in ("show", "bring_to_front")]
        self.assertEqual(steps(), ["show", "bring_to_front"])
        wrapper = self.m.after_popup(win, 0)
        self.m.before_popup(win)
        wrapper()
        self.assertEqual(steps(), ["show", "bring_to_front", "show", "bring_to_front"])

    def test_without_the_flag_there_is_no_keyboard_and_the_model_says_so(self):
        self.setting = make_setting(1)
        self.load()
        win, board = self.open_board()
        self.assertIsNone(getattr(win, "nuiKeyboard", None))
        self.assertIs(board.model["keyboard"], False)
        self.assertEqual(self.m.nui_windows.DECISIONS["virtual-keyboard"], "legacy: flag off")

    def test_the_keyboard_needs_the_novaui_board(self):
        self.setting = make_setting(0, windows="+virtual-keyboard")
        self.load()
        win = self.open_window()
        self.assertIsNone(win.nuiBoard)
        self.assertIsNone(getattr(win, "nuiKeyboard", None))
        self.assertEqual(self.m.nui_windows.DECISIONS["virtual-keyboard"], "legacy: needs the NovaUI login board")
        self.assertEqual(self.dbg.errors, [], "not a failure: the legacy keyboard runs")
        self.state.rtl = True
        self.setting = make_setting(1, windows="+virtual-keyboard")
        self.load()
        self.open_window()
        self.assertEqual(self.m.nui_windows.DECISIONS["virtual-keyboard"], "legacy: right-to-left locale")

    def test_the_keyboard_follows_the_server_board_the_popups_and_close(self):
        win, board = self.open_board()
        keyboard = win.nuiKeyboard
        win._LoginWindow__OpenServerBoard()
        self.assertFalse(keyboard.is_visible())
        win._LoginWindow__OpenLoginBoard()
        self.assertTrue(keyboard.is_visible())
        wrapper = self.m.after_popup(win, 0)
        self.m.before_popup(win)
        self.assertFalse(keyboard.is_visible())
        wrapper()
        self.assertTrue(keyboard.is_visible())
        shows = [name for name, _ in self.state.shows]
        self.assertEqual(shows[-2:], ["VirtualKeyboard", "LoginBoard"], "shown again before the board")
        self.m.close_board(win)
        self.assertIsNone(win.nuiKeyboard)
        self.assertIn(("destroy",), keyboard.calls)

    def test_a_popup_open_before_the_board_holds_the_keyboard_back_too(self):
        win = self.open_window()
        win.stream.popupWindow.Open("LOGIN_FAILURE_SAMELOGIN", 0)
        win._LoginWindow__OpenLoginBoard()
        self.assertFalse(win.nuiKeyboard.is_visible())
        win.stream.popupWindow.Close()
        self.assertTrue(win.nuiKeyboard.is_visible())

    def test_type_text_types_into_the_last_focused_field(self):
        win, board = self.open_board()
        self.assertTrue(board.type_text("nova"))
        self.assertEqual(board.typed_values(), ("nova", ""))
        board.focus(PASSWORD_FIELD)
        board.type_text("pw")
        self.assertEqual(board.typed_values(), ("nova", "pw"))
        board.type_text("\b")
        self.assertEqual(board.typed_values(), ("nova", "p"))

    def test_enter_from_the_keyboard_moves_to_the_password_field_and_then_submits(self):
        win, board = self.open_board()
        board.type_text("nova")
        board.type_text("\n")
        self.assertEqual(board.focused, PASSWORD_FIELD)
        board.type_text("Nv1")
        board.type_text("\n")
        self.assertEqual(win.stream.login_info, [("nova", "Nv1")])

    def test_a_hidden_board_types_nothing(self):
        win, board = self.open_board()
        self.m.before_popup(win)
        self.assertFalse(board.type_text("x"))


class Strip(object):
    """A LocaleStrip facade as far as place_picker sees it."""

    def __init__(self, window):
        self.nui_window = window


class PickerPlace(ControllerTest):
    def strip_window(self):
        window = self.nui.Window()
        window.DOCUMENT = "nui/windows/locale-strip/locale-strip.rml"
        return window

    def test_the_picker_goes_below_a_novaui_strip(self):
        win = self.Window(Stream())
        strip = self.strip_window()
        win.localeSelector = Strip(strip)
        win.nuiBoard = self.m.open_board(win, self.choices.choose, self.choices.exit)
        picker = win.nuiPicker
        self.assertEqual(picker.placement, ("next_to", strip, "below", 4, ""))

    def test_the_strip_goes_above_the_picker_after_each_show_so_its_hints_show(self):
        # The flag hints open below the strip, where the picker is; every
        # document is its own stacking context, so the strip must be the
        # later one.
        win = self.Window(Stream())
        strip = self.strip_window()
        win.localeSelector = Strip(strip)
        win.nuiBoard = self.m.open_board(win, self.choices.choose, self.choices.exit)
        raised = strip.front
        self.assertGreaterEqual(raised, 1)
        wrapper = self.m.after_popup(win, 0)
        self.m.before_popup(win)
        wrapper()
        self.assertGreater(strip.front, raised, "raised again after the picker came back")

    def test_without_a_novaui_strip_the_sheet_places_the_picker(self):
        win, board = self.open_board()
        self.assertIsNone(win.nuiPicker.placement)

    def test_the_picker_keeps_clear_of_every_novaui_board(self):
        self.setting = make_setting(1, windows="+virtual-keyboard")
        self.load()
        win, board = self.open_board()
        picker = win.nuiPicker
        # The one-page login's body covers the screen: the picker keeps clear
        # of its two boards.
        self.assertEqual(picker.keep_clear, [(board, "login-card"), (board, "login-accounts"), win.nuiKeyboard])
        server_board = self.nui.Window()
        win.nuiServerBoard = server_board
        self.m.place_picker(win)
        self.assertEqual(picker.keep_clear, [(board, "login-card"), (board, "login-accounts"), server_board, win.nuiKeyboard])

    def test_place_picker_without_a_picker_does_nothing(self):
        win = self.Window(Stream())
        self.assertIsNone(self.m.place_picker(win))


# --- T7: the hooks are in place in intrologin.py ----------------------------------

def dotted(node):
    """"self.stream.popupWindow.Open" for a call's function, or "" if it is
    not a plain dotted name."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


class IntroLoginHooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INTROLOGIN, encoding="utf-8") as file:
            cls.tree = ast.parse(file.read())
        window = next(node for node in cls.tree.body if isinstance(node, ast.ClassDef) and node.name == "LoginWindow")
        cls.methods = {node.name: node for node in window.body if isinstance(node, ast.FunctionDef)}

    def calls(self, method):
        """(position, dotted name, call node) of every call in a method, in
        source order."""
        found = [((node.lineno, node.col_offset), dotted(node.func), node)
                 for node in ast.walk(self.methods[method]) if isinstance(node, ast.Call)]
        return sorted(found, key=lambda item: item[0])

    def names(self, method):
        return [name for _, name, _ in self.calls(method)]

    def position(self, method, name):
        for where, found, _ in self.calls(method):
            if found == name:
                return where
        self.fail("%s does not call %s" % (method, name))

    def test_the_module_imports_nui_login(self):
        imports = [alias.name for node in self.tree.body if isinstance(node, ast.Import) for alias in node.names]
        self.assertIn("nui_login", imports)

    def test_a_new_window_has_no_board(self):
        assigned = [node for node in ast.walk(self.methods["__init__"]) if isinstance(node, ast.Assign)
                    and any(dotted(target) == "self.nuiBoard" for target in node.targets)]
        self.assertEqual(len(assigned), 1)
        self.assertIsInstance(assigned[0].value, ast.Constant)
        self.assertIsNone(assigned[0].value.value)

    def test_open_makes_the_board_after_the_script_and_before_the_login_info(self):
        opened = self.position("Open", "nui_login.open_board")
        self.assertLess(self.position("Open", "self.__LoadScript"), opened)
        self.assertLess(opened, self.position("Open", "self.__LoadLoginInfo"))
        assigned = [node for node in ast.walk(self.methods["Open"]) if isinstance(node, ast.Assign)
                    and isinstance(node.value, ast.Call) and dotted(node.value.func) == "nui_login.open_board"]
        self.assertEqual([dotted(node.targets[0]) for node in assigned], ["self.nuiBoard"])

    def test_close_drops_the_board_first(self):
        first = self.methods["Close"].body[0]
        self.assertIsInstance(first, ast.Expr)
        self.assertEqual(dotted(first.value.func), "nui_login.close_board")

    def test_every_popup_hides_the_board_before_it_opens_and_brings_it_back(self):
        opening = sorted(name for name in self.methods if "self.stream.popupWindow.Open" in self.names(name))
        self.assertEqual(opening, ["Connect", "NuiCreateAccount", "PopupDisplayMessage", "PopupNotifyMessage",
                                   "SameLogin_OpenUI"])
        for method in opening:
            calls = self.calls(method)
            names = [name for _, name, _ in calls]
            opened = names.index("self.stream.popupWindow.Open")
            hidden = names.index("nui_login.before_popup")
            closed = names.index("self.stream.popupWindow.Close")
            self.assertLess(closed, hidden, method)
            self.assertLess(hidden, opened, method)
            open_call = calls[opened][2]
            wrapped = [arg for arg in open_call.args if isinstance(arg, ast.Call) and dotted(arg.func) == "nui_login.after_popup"]
            self.assertEqual(len(wrapped), 1, method)

    def test_the_boards_follow_the_login_and_server_boards(self):
        self.assertLess(self.position("__OpenLoginBoard", "nui_login.enter_login_board"),
                        self.position("__OpenLoginBoard", "self.virtualKeyboard.Show"))
        self.assertIn("nui_login.leave_login_board", self.names("__OpenServerBoard"))

    def test_the_focus_helpers_ask_the_board_first(self):
        for method, which in (("SetIDEditLineFocus", "user"), ("SetPasswordEditLineFocus", "password")):
            first = self.methods[method].body[0]
            self.assertIsInstance(first, ast.If, method)
            self.assertEqual(dotted(first.test.func), "nui_login.focus_field", method)
            self.assertEqual(first.test.args[1].value, which, method)

    def test_the_server_text_reaches_the_board(self):
        self.assertIn("nui_login.set_server", self.names("__SetServerInfo"))
        self.assertIn("nui_login.set_server", self.names("__LoadLoginInfo"))

    def test_a_direction_change_carries_the_typed_id(self):
        names = self.names("__OnLocaleChanged")
        for hook in ("nui_login.on_login_board", "nui_login.typed_values", "nui_login.restore_typed"):
            self.assertIn(hook, names)
        self.assertLess(names.index("nui_login.typed_values"), names.index("self.Close"))
        self.assertLess(names.index("self.Open"), names.index("nui_login.restore_typed"))

    def test_a_rebuilt_strip_places_the_picker_again(self):
        names = self.names("__RefreshLocaleUI")
        self.assertLess(names.index("self.localeSelector.SetTop"), names.index("nui_login.place_picker"))

    def test_the_login_button_path_is_left_alone(self):
        self.assertFalse([name for name in self.names("__OnClickLoginButton") if name.startswith("nui_login.")])



# --- the one-page login: saved accounts, the card, Create account -------------------

class OnePageTest(ControllerTest):
    """The board with a saved accounts file of its own (a temporary one)."""

    def setUp(self):
        super(OnePageTest, self).setUp()
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        self.store = self.m.nui_accounts
        self.store.PATH = os.path.join(folder, "nui_accounts.txt")

    def save(self, login, played, slots, remember=True):
        self.store.remember_login(login, 2, remember)
        return self.store.note_game_start(login, played, slots)


class SavedAccounts(OnePageTest):
    def test_an_account_is_written_only_when_its_log_in_asked_to_remember_it(self):
        self.assertFalse(self.save("kalinka", "Kalinka", [("Kalinka", 4, 75)], remember=False))
        self.assertEqual(self.store.accounts(), [])
        self.assertFalse(self.store.note_game_start("kalinka", "Kalinka", []), "no log in asked for it")
        self.assertTrue(self.save("kalinka", "Kalinka", [("Kalinka", 4, 75), ("Andrei", 5, 71), ("", 0, 0)]))
        account = self.store.accounts()[0]
        self.assertEqual((account["login"], account["server"], account["played"]), ("kalinka", 2, "Kalinka"))
        self.assertEqual(account["characters"], [{"name": "Kalinka", "race": 4, "level": 75},
                                                 {"name": "Andrei", "race": 5, "level": 71}])
        with open(self.store.PATH) as handle:
            self.assertNotIn(PASSWORD, handle.read())

    def test_the_newest_comes_first_five_are_kept_and_a_damaged_line_is_skipped(self):
        for index in range(7):
            self.save("acc%d" % index, "", [])
            self.store.set_setting("remember", "1")
        with open(self.store.PATH, "a") as handle:
            handle.write("A\tbroken\tnot-a-number\t1\tx\n")
        logins = [account["login"] for account in self.store.accounts()]
        self.assertEqual(len(logins), 5)
        self.assertNotIn("broken", logins)
        self.assertEqual(self.store.setting("remember"), "1")
        self.assertTrue(self.store.forget(logins[0]))
        self.assertFalse(self.store.forget(logins[0]))
        self.assertNotIn(logins[0], [account["login"] for account in self.store.accounts()])

    def test_since_words_the_time_as_the_screen_does(self):
        words = {"now": "now", "minutes": "%dm", "hours": "%dh", "yesterday": "y", "days": "%dd"}
        self.assertEqual([self.store.since(s, words) for s in (5, 600, 7200, 90000, 400000)],
                         ["now", "10m", "2h", "y", "4d"])

    def test_the_board_lists_them_and_a_press_picks_one(self):
        self.save("kalinka", "Kalinka", [("Kalinka", 4, 75)])
        self.save("mirela", "Mirela", [("Mirela", 3, 68)])
        win, board = self.open_board()
        board.reload_accounts()
        rows = board.get("accounts")
        self.assertEqual([row["name"] for row in rows], ["mirela", "kalinka"])
        self.assertEqual(rows[0]["face"], self.store.face_of(3))
        board.on_pick_account("kalinka", 1)
        self.assertEqual(board.get("user"), "", "a right press picks nothing")
        board.on_pick_account("kalinka", 0)
        self.assertEqual(board.get("user"), "kalinka")
        self.assertEqual([row["selected"] for row in board.get("accounts")], [False, True])
        self.assertEqual(board.focused, PASSWORD_FIELD)
        board.on_forget_account("kalinka", 0)
        board.on_pick_account("kalinka", 0)  # the same press reaches the row after its cross
        self.assertEqual([row["name"] for row in board.get("accounts")], ["mirela"])
        board.on_add_account(0)
        self.assertEqual((board.get("user"), board.focused), ("", ID_FIELD))

    def test_remember_me_is_saved_and_reaches_the_log_in(self):
        win, board = self.open_board()
        self.assertTrue(board.get("remember"))
        board.on_remember_press(0)
        self.assertFalse(board.get("remember"))
        self.assertEqual(self.store.setting("remember"), "0")


class TheCard(OnePageTest):
    def test_the_eye_moves_the_password_to_the_text_field_never_through_the_model(self):
        win, board = self.open_board()
        self.type_values(board)
        board.on_eye_press(0)
        self.assertTrue(board.get("show_password"))
        self.assertIn(("set_value", self.m.PASSWORD_SHOWN, PASSWORD, "end"), board.calls)
        self.assertEqual(board.focused, self.m.PASSWORD_SHOWN)
        board.on_eye_press(0)
        self.assertEqual(board.focused, PASSWORD_FIELD)
        self.assertNotIn(PASSWORD, repr(board.model))

    def test_log_in_goes_through_the_chosen_server_and_auto_picks_the_channel(self):
        win, board = self.open_board()
        logins = []
        win.NuiLogin = lambda user, password, server, channel: logins.append((user, password, server, channel))
        board.set_servers([(1, "Nova"), (2, "Test")], 2, 0)
        board.set_channels([(1, "CH1", "BUSY"), (2, "CH2", "NORM"), (3, "CH3", "FULL")])
        self.assertEqual(board.get("server_state"), "ok")
        self.type_values(board)
        board.on_submit()
        self.assertEqual(logins, [(USER, PASSWORD, 2, 2)], "Auto: a NORM channel before a BUSY one")
        board.set_online(40, {1: 3, 2: 30})
        board.on_submit()
        self.assertEqual(logins[-1][3], 1, "with counts, the fewest players")
        board.on_channel_press(3, 0)
        self.assertTrue(board.get("auto"), "a full channel cannot be chosen")
        board.on_channel_press(2, 0)
        board.on_submit()
        self.assertEqual(logins[-1][3], 2)
        self.assertEqual(self.store.setting("channel"), "2")
        self.assertIn("CH2", board.get("channel_text"))

    def test_create_checks_first_and_sends_the_lower_cased_login(self):
        win, board = self.open_board()
        board.set(can_register=True)
        sent = []
        win.NuiCreateAccount = lambda *args: sent.append(args)
        board.on_tab_press("register", 0)
        values = {"user": "DarkBlade", "email": "dark@blade.io", "password": "s3cret-pass", "confirm": "s3cret-pass",
                  "code": "1234567"}
        for field, value in values.items():
            board.on_reg_edit(field, value, False)
        board.on_create()
        self.assertEqual((board.get("reg_error_on"), sent), ("rules", []))
        board.on_rules_press(0)
        board.on_create()
        self.assertEqual(sent, [("darkblade", "s3cret-pass", "dark@blade.io", "1234567", 0)])
        self.assertNotIn("s3cret-pass", repr(board.model))

    def test_the_answer_switches_to_log_in_or_shows_its_error(self):
        win, board = self.open_board()
        board.set(can_register=True)
        board.on_tab_press("register", 0)
        board.on_reg_edit("user", "DarkBlade", False)
        board.account_created(1)
        self.assertEqual((board.get("tab"), board.get("reg_error"), board.get("reg_error_on")),
                         ("register", "@ui.NUI_LOGIN_ERR_TAKEN", "user"))
        board.account_created(0)
        self.assertEqual((board.get("tab"), board.get("user"), board.get("error_ok")), ("login", "darkblade", True))


class RegistrationRules(unittest.TestCase):
    def setUp(self):
        self.check = load_nui_login(make_nui(NuiState()), make_setting(1), make_dbg()).check_registration

    def test_each_rule(self):
        good = dict(user="DarkBlade", email="dark@blade.io", password="s3cret-pass", confirm="s3cret-pass",
                    code="1234567", rules=True)
        self.assertIsNone(self.check(**good))
        for change, field in ((dict(user="abc"), "user"), (dict(user="dark_blade"), "user"), (dict(user="Admin"), "user"),
                              (dict(email="dark.blade.io"), "email"), (dict(email="dark@blade"), "email"),
                              (dict(email="dark@.io"), "email"), (dict(password="short", confirm="short"), "password"),
                              (dict(password="has[bracket", confirm="has[bracket"), "password"),
                              (dict(confirm="other-pass"), "confirm"), (dict(code="12345a7"), "code"),
                              (dict(code="123456"), "code"), (dict(rules=False), "rules")):
            values = dict(good, **change)
            with self.subTest(change=change):
                self.assertEqual(self.check(**values)[0], field)


class AutoChannel(unittest.TestCase):
    def setUp(self):
        self.pick = load_nui_login(make_nui(NuiState()), make_setting(1), make_dbg()).pick_channel

    def test_the_rule(self):
        self.assertEqual(self.pick({1: "busy", 2: "ok", 3: "ok"}, {}, 3), 3, "the last played among the ok ones")
        self.assertEqual(self.pick({1: "busy", 2: "ok"}, {}, 1), 2, "ok before busy, even the last played")
        self.assertEqual(self.pick({1: "ok", 2: "ok"}, {1: 50, 2: 10}, 1), 2, "the fewest players")
        self.assertEqual(self.pick({1: "full", 2: "down"}, {}, 2), 2, "none open: the last played")
        self.assertEqual(self.pick({1: "unknown", 2: "unknown"}, {}, 0), 1, "none known: the lowest")


if __name__ == "__main__":
    unittest.main()
