"""Tests for the NovaUI server and channel board (assets/root/nui_server_board.py)
and its hooks in assets/root/intrologin.py: python3 -B -m unittest
nui_server_board_test (from tools/).

Plain CPython. The LoginWindow server methods, hooks included, are compiled
from intrologin.py onto a stand-in window whose lists behave like the legacy
ui.ListBox; serverinfo.py is the real one. channel.inf is written in a
temporary folder."""
import ast
import os
import shutil
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_test_support as support  # noqa: E402
from nui_login_test import Popup, Widget, dotted  # noqa: E402

ROOT = support.ROOT
INTROLOGIN = os.path.join(ROOT, "intrologin.py")
DOCUMENT = "nui/windows/server-board/server-board.rml"
DIK_RETURN = 28


class ListBox(object):
    """ui.ListBox's data: keyDict, textDict, selectedLine and SelectItem."""

    def __init__(self):
        self.keyDict = {}
        self.textDict = {}
        self.selectedLine = -1
        self.event = lambda *arg: None

    def ClearItem(self):
        self.keyDict = {}
        self.textDict = {}
        self.selectedLine = -1

    def InsertItem(self, number, text):
        line = len(self.keyDict)
        self.keyDict[line] = number
        self.textDict[line] = text

    def SetEvent(self, event):
        self.event = event

    def SelectItem(self, line):
        if line not in self.keyDict:
            return
        if line == self.selectedLine:
            return
        self.selectedLine = line
        self.event(self.keyDict.get(line, 0), self.textDict.get(line, "None"))

    def GetSelectedItem(self):
        return self.keyDict.get(self.selectedLine, 0)


class Stream(object):
    def __init__(self):
        self.popupWindow = Popup()
        self.isAutoLogin = 0
        self.connect_info = []

    def SetConnectInfo(self, *args):
        self.connect_info.append(args)

    def GetConnectAddr(self):
        return ""


class Checker(object):
    def __init__(self):
        self.requests = []
        self.channels = []

    def Initialize(self, *args):
        self.channels = []

    def AddChannel(self, key, ip, port):
        self.channels.append(key)

    def Request(self):
        self.requests.append(list(self.channels))


class WindowBase(object):
    def __init__(self, stream):
        self.stream = stream
        self.nuiBoard = None
        self.nuiServerBoard = None
        self.serverBoard = Widget(shown=True)
        self.connectBoard = Widget()
        self.loginBoard = Widget()
        self.virtualKeyboard = Widget()
        self.serverList = ListBox()
        self.channelList = ListBox()
        self.serverExitButton = Widget()
        self.serverInfo = Widget()
        self.idEditLine = Widget()
        self.pwdEditLine = Widget()
        self.xServerBoard = 0
        self.yServerBoard = 0
        self.inputDialog = None
        self.loginInfo = None
        self.exited = 0

    def _LoginWindow__OnClickExitButton(self):
        self.exited += 1


COMPILED = ("_LoginWindow__RefreshServerList", "_LoginWindow__OnSelectServer", "_LoginWindow__RequestServerStateList",
            "_LoginWindow__RefreshServerStateList", "_LoginWindow__OpenServerBoard", "_LoginWindow__OpenLoginBoard",
            "_LoginWindow__OnClickSelectServerButton", "_LoginWindow__SaveChannelInfo", "_LoginWindow__LoadChannelInfo",
            "_LoginWindow__GetServerID", "_LoginWindow__GetChannelID", "_LoginWindow__GetRegionID",
            "_LoginWindow__ServerIDToServerIndex", "_LoginWindow__ChannelIDToChannelIndex", "_LoginWindow__SetServerInfo",
            "NotifyChannelState", "PopupNotifyMessage", "_LoginWindow__OnCloseInputDialog", "EmptyFunc",
            "_LoginWindow__ServerBoard_OnKeyUp")


def compile_login_window(namespace):
    with open(INTROLOGIN, encoding="utf-8") as file:
        source = file.read()
    tree = ast.parse(source)
    window = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "LoginWindow")
    methods = {node.name: node for node in window.body if isinstance(node, ast.FunctionDef)}
    lines = source.splitlines()
    body = []
    for name in COMPILED:
        node = methods[name.replace("_LoginWindow__", "__")]
        body.extend(lines[node.lineno - 1:node.end_lineno])
        body.append("")
    namespace["WindowBase"] = WindowBase
    exec(compile("class LoginWindow(WindowBase):\n" + "\n".join(body) + "\n", INTROLOGIN, "exec"), namespace)
    return namespace["LoginWindow"]


class ServerBoardTest(unittest.TestCase):
    flags = "+server-board"

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="nui-server-board-")
        self.cwd = os.getcwd()
        os.chdir(self.folder)
        os.makedirs("config")
        self.addCleanup(self._cleanup)
        with open("config/channel.inf", "w") as file:
            file.write("2 1 0")
        self.state = support.NuiState()
        self.dbg = support.make_dbg()
        self.setting = support.make_setting(flag=0, windows=self.flags)
        self.placed = []
        self.nui_login = support.stub_module(
            "nui_login", place_picker=self.placed.append, enter_login_board=lambda win: False,
            leave_login_board=lambda win: None, before_popup=lambda win: None, after_popup=lambda win, cb: cb,
            set_server=lambda win, text: None)
        self.app = support.stub_module("app", DIK_RETURN=DIK_RETURN, loggined=False,
                                       SetGuildMarkPath=lambda path: None, SetGuildSymbolPath=lambda path: None)
        self.modules = support.Modules(nui=support.make_nui(self.state), dbg=self.dbg, systemSetting=self.setting,
                                       wndMgr=support.make_wndmgr(), app=self.app, nui_login=self.nui_login)
        self.server_info = self.modules.load("serverInfo", "serverinfo.py")
        self.modules.load("nui_windows")
        self.m = self.modules.load("nui_server_board")
        self.modules.restore()
        self.checker = Checker()
        self.net = support.stub_module("net", SetServerInfo=lambda text: None, SetMarkServer=lambda ip, port: None)
        namespace = {"nui_server_board": self.m, "nui_login": self.nui_login, "serverInfo": self.server_info,
                     "ServerStateChecker": self.checker, "net": self.net, "app": self.app,
                     "localeInfo": support.LocaleInfo(), "wndMgr": support.make_wndmgr(),
                     "exception": support.stub_module("exception", Abort=self._abort),
                     "SKIP_LOGIN_PHASE": False, "SKIP_LOGIN_PHASE_SUPPORT_CHANNEL": False}
        self.Window = compile_login_window(namespace)
        self.ok = []

    def _abort(self, message):
        raise AssertionError("exception.Abort(%r)" % message)

    def _cleanup(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.folder, ignore_errors=True)
        self.modules.restore()

    def open_window(self):
        """LoginWindow.Open as far as the server board goes."""
        win = self.Window(Stream())
        win.serverList.SetEvent(lambda *args: win._LoginWindow__OnSelectServer())  # ui.__mem_func__ drops the arguments
        win.serverBoard.OnKeyUp = win._LoginWindow__ServerBoard_OnKeyUp
        win.nuiServerBoard = self.m.open_board(win, win._LoginWindow__OnClickSelectServerButton, win._LoginWindow__OnClickExitButton)
        win._LoginWindow__RefreshServerList()
        win._LoginWindow__OpenServerBoard()
        return win

    def board(self, win):
        self.assertIsNotNone(win.nuiServerBoard, self.m.nui_windows.DECISIONS)
        return win.nuiServerBoard


class Mirror(ServerBoardTest):
    def test_the_board_mirrors_the_lists_and_the_saved_choice(self):
        win = self.open_window()
        board = self.board(win)
        self.assertTrue(board.is_visible())
        self.assertFalse(win.serverBoard.IsShow(), "the legacy board stays hidden")
        self.assertEqual(board.model["servers"], [{"line": 0, "label": "01. Metin2"}, {"line": 1, "label": "02. Test"}])
        self.assertEqual(board.model["server_line"], 1, "server 2 from channel.inf")
        self.assertEqual([row["name"] for row in board.model["channels"]], ["CH1", "CH2"])
        self.assertEqual(board.model["channel_line"], 0)
        self.assertEqual(win._LoginWindow__GetServerID(), 2)
        self.assertEqual(self.dbg.errors, [])

    def test_channel_states_reach_the_rows(self):
        win = self.open_window()
        board = self.board(win)
        self.assertEqual(board.model["channels"][0]["state_class"], "unknown", "no answer yet")
        win.NotifyChannelState(21, 0)
        win.NotifyChannelState(22, 1)
        self.assertEqual([(row["state"], row["state_class"]) for row in board.model["channels"]],
                         [("....", "down"), ("NORM", "normal")])
        self.server_info.REGION_DICT[0][2]["channel"][1]["state"] = "BUSY"
        self.server_info.REGION_DICT[0][2]["channel"][2]["state"] = "FULL"
        win._LoginWindow__RefreshServerStateList()
        self.assertEqual([row["state_class"] for row in board.model["channels"]], ["busy", "full"])

    def test_names_go_through_plain_text(self):
        self.server_info.REGION_DICT[0][2]["name"] = "x@ui.LOGIN_ID"
        win = self.open_window()
        self.assertEqual(self.board(win).model["servers"][1]["label"], "02. x@\u2060ui.LOGIN_ID")


class Picking(ServerBoardTest):
    def test_pick_server_drives_the_legacy_list(self):
        win = self.open_window()
        board = self.board(win)
        requests = len(self.checker.requests)
        board.fire("pick_server", 0)
        self.assertEqual(win._LoginWindow__GetServerID(), 1)
        self.assertEqual(board.model["server_line"], 0)
        self.assertEqual(len(self.checker.requests), requests + 1, "the states are asked for")
        self.assertEqual([row["name"] for row in board.model["channels"]], ["CH1", "CH2", "CH3", "CH4"])

    def test_picking_the_selected_server_again_changes_nothing(self):
        win = self.open_window()
        board = self.board(win)
        requests = len(self.checker.requests)
        board.fire("pick_server", 1)
        self.assertEqual(len(self.checker.requests), requests)

    def test_pick_channel_selects_it(self):
        win = self.open_window()
        board = self.board(win)
        board.fire("pick_channel", 1)
        self.assertEqual(win._LoginWindow__GetChannelID(), 2)
        self.assertEqual(board.model["channel_line"], 1)

    def test_confirm_saves_channel_inf_and_opens_the_login_board_through_the_legacy_method(self):
        win = self.open_window()
        board = self.board(win)
        board.fire("pick_channel", 1)
        board.fire("confirm")
        with open("config/channel.inf") as file:
            self.assertEqual(file.read(), "2 2 0")
        self.assertEqual(win.stream.connect_info[-1][:2], ("127.0.0.1", self.server_info.PORT_2))
        self.assertFalse(board.is_visible())
        self.assertFalse(board.active)
        self.assertEqual(board.model["exit_label"], "@game.UI_CLOSE")
        self.assertTrue(win.connectBoard.IsShow(), "the legacy login board in this test")

    def test_exit_calls_the_exit_handler(self):
        win = self.open_window()
        self.board(win).fire("leave")
        self.assertEqual(win.exited, 1)

    def test_a_channel_popup_leaves_the_board_up(self):
        win = self.open_window()
        board = self.board(win)
        self.server_info.REGION_DICT[0][2]["channel"][1]["state"] = "FULL"
        board.fire("confirm")
        self.assertEqual(win.stream.popupWindow.message, "CHANNEL_NOTIFY_FULL")
        self.assertTrue(board.is_visible())

    def test_choose_again_shows_the_board_with_the_close_label(self):
        win = self.open_window()
        board = self.board(win)
        board.fire("confirm")
        win._LoginWindow__RefreshServerList()
        win._LoginWindow__OpenServerBoard()
        self.assertTrue(board.is_visible())
        self.assertEqual(board.model["exit_label"], "@game.UI_CLOSE")
        self.assertFalse(win.serverBoard.IsShow())


class EnterKey(ServerBoardTest):
    def test_enter_on_key_up_confirms_only_while_active_and_without_a_popup(self):
        win = self.open_window()
        board = self.board(win)
        board._ok_cb = lambda: self.ok.append(True)
        self.assertFalse(win.OnKeyUp(1), "another key goes on")
        win.stream.popupWindow.Open("CHANNEL_SELECT_CHANNEL", 0)
        self.assertFalse(win.OnKeyUp(DIK_RETURN))
        win.stream.popupWindow.Close()
        self.assertTrue(win.OnKeyUp(DIK_RETURN))
        self.assertEqual(self.ok, [True])
        self.m.leave(win)
        self.assertFalse(win.OnKeyUp(DIK_RETURN))
        self.assertEqual(self.ok, [True])

    def test_close_board_destroys_the_board_and_takes_on_key_up_away(self):
        win = self.open_window()
        board = self.board(win)
        self.assertIn("OnKeyUp", vars(win))
        self.m.close_board(win)
        self.assertIsNone(win.nuiServerBoard)
        self.assertIn(("destroy",), board.calls)
        self.assertNotIn("OnKeyUp", vars(win))

    def test_the_picker_is_placed_again_when_the_board_comes(self):
        win = self.open_window()
        self.assertEqual(self.placed, [win])


class FlagOff(ServerBoardTest):
    flags = ""

    def test_the_flag_off_leaves_every_legacy_part_as_before(self):
        win = self.open_window()
        self.assertIsNone(win.nuiServerBoard)
        self.assertTrue(win.serverBoard.IsShow())
        self.assertNotIn("OnKeyUp", vars(win))
        self.assertEqual(self.m.nui_windows.DECISIONS["server-board"], "legacy: flag off")
        for hook in (self.m.enter, self.m.leave, self.m.refresh_servers, self.m.refresh_channels, self.m.close_board):
            self.assertIsNone(hook(win))
        self.assertEqual(self.placed, [])
        self.assertEqual(self.dbg.errors, [])


class DocumentFails(ServerBoardTest):
    def test_a_document_that_did_not_load_keeps_the_legacy_board_and_logs_once(self):
        self.state.failing.add(DOCUMENT)
        win = self.open_window()
        self.assertIsNone(win.nuiServerBoard)
        self.assertTrue(win.serverBoard.IsShow())
        self.open_window()
        self.assertEqual(self.dbg.errors, ["nui_windows: server-board: the document did not load; using the legacy window"])


class IntroLoginHooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INTROLOGIN, encoding="utf-8") as file:
            cls.tree = ast.parse(file.read())
        window = next(node for node in cls.tree.body if isinstance(node, ast.ClassDef) and node.name == "LoginWindow")
        cls.methods = {node.name: node for node in window.body if isinstance(node, ast.FunctionDef)}

    def names(self, method):
        calls = [((node.lineno, node.col_offset), dotted(node.func)) for node in ast.walk(self.methods[method])
                 if isinstance(node, ast.Call)]
        return [name for _, name in sorted(calls)]

    def test_the_module_imports_nui_server_board(self):
        imports = [alias.name for node in self.tree.body if isinstance(node, ast.Import) for alias in node.names]
        self.assertIn("nui_server_board", imports)

    def test_open_makes_the_board_after_the_login_board(self):
        names = self.names("Open")
        self.assertLess(names.index("nui_login.open_board"), names.index("nui_server_board.open_board"))
        self.assertLess(names.index("nui_server_board.open_board"), names.index("self.__LoadLoginInfo"))

    def test_close_drops_the_board_right_after_the_login_board(self):
        names = self.names("Close")
        self.assertEqual(names[:2], ["nui_login.close_board", "nui_server_board.close_board"])

    def test_the_board_follows_the_server_and_login_boards(self):
        names = self.names("__OpenServerBoard")
        self.assertEqual(names.index("nui_server_board.enter"), names.index("nui_login.leave_login_board") + 1)
        names = self.names("__OpenLoginBoard")
        self.assertEqual(names.index("nui_server_board.leave"), names.index("self.serverBoard.Hide") + 1)
        self.assertLess(names.index("nui_server_board.leave"), names.index("nui_login.enter_login_board"))

    def test_the_refresh_hooks_end_the_list_refreshes(self):
        self.assertEqual(self.names("__RefreshServerList")[-1], "nui_server_board.refresh_servers")
        self.assertEqual(self.names("__RefreshServerStateList")[-1], "nui_server_board.refresh_channels")


if __name__ == "__main__":
    unittest.main()
