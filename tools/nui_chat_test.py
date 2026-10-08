"""Tests for the NovaUI chat window and chat log of CHAT CONTENT
(assets/root/nui_chat.py, nui_chat_log.py), the shared Wave 2b pieces
(nui_hud.has_engine_2b and FocusProxy, nui.py's element_box, the components,
tokens and window ids) and the Interface and game window wiring of P10 spec
5.8: python3 -B -m unittest nui_chat_test (from tools/).

Plain CPython over nui_game_support's stand-ins (its Wave 2b chat store,
wndMgr focus stack, paste bridge and legacy widgets). For each window:
- facade: every method the Interface, game.py and the console call on the
  legacy class exists on the NovaUI class with a signature the legacy
  callers can use, and the class constants have the legacy values;
- differential: the legacy class (uichat.py) and the NovaUI facade, each in
  a world of its own with the same stand-in state and driven through the
  same flows (the legacy widgets' events against the board's data events
  and the field's keys), make the same net.*, chat.* state, ime.PasteString
  and Interface.MakeHyperlinkTooltip calls, in order, leave the same text in
  their fields and show the same mark; the per-frame and layout calls legacy
  makes and NovaUI never makes are left out (chat.Update, Render,
  ArrangeShowingChat, SetPosition, SetHeight, SetAlign, GetVisibleLineCount,
  and the getters), as are the legacy edit line's own IME calls;
- fixture: the board, set from each fixture, has every fixture key in its
  model with the same kind, and the feed stand-ins hold line maps as C++
  publishes them (P10 spec 2.3.2);
- no per-frame Python: the modules define no OnUpdate, OnRender or
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
import nui_test_support as base  # noqa: E402

ROOT = support.ROOT
REPO = os.path.normpath(os.path.join(base.HERE, ".."))
NUI = os.path.join(REPO, "assets", "nui", "nui")
WINDOWS = os.path.join(NUI, "windows")
CLASSIC_WINDOWS = os.path.join(NUI, "skins", "classic", "windows")
CHAT_DOC = "nui/windows/chat/chat.rml"
LOG_DOC = "nui/windows/chat-log/chat-log.rml"
CHAT_MODULES = ("nui_text", "nui_chat", "nui_chat_log")
C = support.CHAT_CONSTANTS
A = support.APP_CONSTANTS
ITEM = "item:6979:0:0:0:0"
TAGGED_ITEM = "|cfff1e6c0|Hitem:6979:0:0:0:0|h[Red Potion]|h|r"

CHAT_METHODS = ("SetSize", "SetPosition", "SetHeight", "Refresh", "Show", "Hide", "IsShow", "BindInterface",
                "SetSendWhisperEvent", "SetOpenChatLogEvent", "OpenChat", "CloseChat", "IsEditMode", "SetChatFocus",
                "OnChangeChatMode", "Destroy")
CHAT_CONSTANTS = ("BOARD_START_COLOR", "BOARD_END_COLOR", "BOARD_MIDDLE_COLOR", "CHAT_OUTLINE_COLOR", "EDIT_LINE_HEIGHT",
                  "CHAT_WINDOW_WIDTH")
LOG_METHODS = ("BindInterface", "Show", "Hide", "IsShow", "Open", "Close", "ToggleAllChatMode", "ToggleChatMode", "OnScroll",
               "Destroy", "OnPressEscapeKey")
LOG_CONSTANTS = ("BLOCK_WIDTH", "CHAT_MODE_NAME", "CHAT_MODE_INDEX", "CHAT_LOG_WINDOW_MINIMUM_WIDTH",
                 "CHAT_LOG_WINDOW_MINIMUM_HEIGHT")
# The calls legacy makes per frame or for its own layout, which NovaUI's
# element and C++ feed replace (P10 spec D9, 5.0.5).
LEFT_OUT = {"chat.Update", "chat.Render", "chat.ArrangeShowingChat", "chat.SetPosition", "chat.SetHeight", "chat.SetAlign",
            "chat.GetVisibleLineCount"}


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class Interface(object):
    """What the chat windows reach of the Interface: the hyperlink tooltip, the
    whisper dialog without a target (a legacy edit line that takes wndMgr's
    focus), the log toggle, and ToggleChat and IsOpenChat, which game.py's
    CheckFocus uses."""

    def __init__(self, world):
        self.world = world
        self.wndChat = None
        self.wndChatLog = None
        self.whisper = None

    def MakeHyperlinkTooltip(self, hyperlink):
        self.world.game.log.append(("interface.MakeHyperlinkTooltip", (hyperlink,)))

    def OpenWhisperDialogWithoutTarget(self):
        self.world.game.log.append(("interface.OpenWhisperDialogWithoutTarget", ()))
        ui = self.world.game.modules["ui"]
        self.whisper = ui.EditLine()
        self.whisper.Show()
        self.whisper.SetFocus()

    def CloseWhisper(self):
        """The dialog's close: its edit line gives the focus back (KillFocus)."""
        whisper, self.whisper = self.whisper, None
        whisper.KillFocus()
        whisper.Hide()

    def ToggleChatLogWindow(self):
        self.world.game.log.append(("interface.ToggleChatLogWindow", ()))
        if self.wndChatLog is not None:
            if self.wndChatLog.IsShow():
                self.wndChatLog.Hide()
            else:
                self.wndChatLog.Show()

    def IsOpenChat(self):
        return self.wndChat.IsEditMode()

    def ToggleChat(self):
        if self.wndChat.IsEditMode():
            self.wndChat.CloseChat()
        else:
            self.wndChat.OpenChat()


class World(object):
    """One world: a Game with the Wave 2b widgets, the legacy chat module, the
    NovaUI chat modules, an Interface stand-in and the game window's focus
    logic (game.py CheckFocus)."""

    def __init__(self, nui_on, windows="+hud2", engine=True, setup=None):
        self.game = support.Game(engine=engine)
        self.game.modules["systemSetting"].GetUINuiWindows = lambda: windows if nui_on else ""
        self.game.item_names = {0x6979: "Red Potion"}
        support.install_wave2b_ui(self.game)
        state = self.game.state
        state.text_fields.update({(CHAT_DOC, "chat-input"), (LOG_DOC, "chat-log-input")})
        state.field_events[(CHAT_DOC, "chat-input")] = "changed"
        state.field_events[(LOG_DOC, "chat-log-input")] = "changed"
        state.maxlength[(CHAT_DOC, "chat-input")] = 512
        state.maxlength[(LOG_DOC, "chat-log-input")] = 512
        if setup is not None:
            setup(self.game)
        self.game.load_standard()
        with quiet():
            self.game.load("colorInfo", "colorinfo.py")
            self.game.load("uiChat", "uichat.py")
            for name in CHAT_MODULES:
                self.game.load(name, name + ".py")
        self.nui_windows = self.game.loaded["nui_windows"]
        self.nui_on = nui_on
        self.interface = Interface(self)
        self.chat = None
        self.log = None
        ui = self.game.modules["ui"]
        world = self

        class GameWindow(ui.Window):
            def CheckFocus(self):
                """game.py:1112-1117."""
                if False == self.IsFocus():
                    if True == world.interface.IsOpenChat():
                        world.interface.ToggleChat()
                    self.SetFocus()

        self.gameWindow = GameWindow()

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def module(self, name):
        return self.game.loaded[name]

    # --- making the windows as the Interface does ------------------------------------

    def make_chat(self):
        """interfacemodule.py __MakeChatWindow."""
        with self, quiet():
            legacy = self.module("uiChat").ChatWindow
            chat = (self.module("nui_chat").ChatWindow if self.nui_on else legacy)()
            chat.SetSize(chat.CHAT_WINDOW_WIDTH, 0)
            chat.SetPosition(1600 // 2 - chat.CHAT_WINDOW_WIDTH // 2, 900 - chat.EDIT_LINE_HEIGHT - 37)
            chat.SetHeight(200)
            chat.Refresh()
            chat.Show()
            chat.BindInterface(self.interface)
            chat.SetSendWhisperEvent(self.interface.OpenWhisperDialogWithoutTarget)
            chat.SetOpenChatLogEvent(self.interface.ToggleChatLogWindow)
        self.chat = self.interface.wndChat = chat
        return chat

    def make_log(self):
        """interfacemodule.py __MakeWindows."""
        with self, quiet():
            legacy = self.module("uiChat").ChatLogWindow
            log = (self.module("nui_chat_log").ChatLogWindow if self.nui_on else legacy)()
            log.BindInterface(self.interface)
        self.log = self.interface.wndChatLog = log
        return log

    def enter_game(self):
        """game.py: the Interface is made, then the game window takes the focus."""
        self.make_chat()
        self.make_log()
        with self:
            self.gameWindow.SetFocus()

    # --- the chat window's input, either way -------------------------------------------

    def line(self, which="chat"):
        window = self.chat if which == "chat" else self.log
        return window.chatInputSet.chatLine

    def board(self, which="chat"):
        return (self.chat if which == "chat" else self.log).board

    def field(self, which="chat"):
        return "chat-input" if which == "chat" else "chat-log-input"

    def type(self, text, which="chat"):
        with self:
            if self.nui_on:
                self.board(which).insert_text(self.field(which), text)
            else:
                self.line(which).type(text)

    def text(self, which="chat"):
        """The field's text; a hidden NovaUI document's field shows the text
        set meanwhile when it shows again (ChatInput.pending)."""
        if self.nui_on:
            return (self.chat if which == "chat" else self.log).input.GetText()
        return self.line(which).GetText()

    def mark(self, which="chat"):
        if self.nui_on:
            return self.board(which).get("mark")
        over = self.line(which).overTextLine
        return over.text if over.shown else ""

    def enter(self, which="chat"):
        with self, quiet():
            if self.nui_on:
                self.board(which).insert_text(self.field(which), "\n")
            else:
                self.line(which).OnIMEReturn()

    def key(self, name, which="chat"):
        """Escape, Up, Down or Tab in the field."""
        with self, quiet():
            if self.nui_on:
                nui_chat = self.module("nui_chat")
                code = {"escape": 81, "up": nui_chat.KEY_UP, "down": nui_chat.KEY_DOWN, "tab": 70}[name]
                return self.board(which).key(self.field(which), code)
            line = self.line(which)
            if name == "escape":
                return line.OnPressEscapeKey()
            if name == "tab":
                return line.OnIMETab()
            return line.OnIMEKeyDown(A["VK_UP"] if name == "up" else A["VK_DOWN"])

    def mode(self, which="chat"):
        with self, quiet():
            if self.nui_on:
                self.board(which).fire("mode", 0)
            else:
                (self.chat if which == "chat" else self.log).chatInputSet.chatModeButton.OnMouseLeftButtonUp()

    def send(self, which="chat"):
        with self, quiet():
            if self.nui_on:
                self.board(which).fire("send", 0)
            else:
                (self.chat if which == "chat" else self.log).chatInputSet.btnSend.click()

    def link(self, hyperlink, alt=False, which="chat"):
        """A press on a link in the lines: legacy's text renderer reports it
        under the pointer (ui.GetHyperlink) to the window pressed."""
        with self, quiet():
            if alt:
                self.game.pressed.add(A["DIK_LALT"])
            try:
                if self.nui_on:
                    self.board(which).fire("link", hyperlink)
                else:
                    self.game.hyperlink = hyperlink
                    target = self.line("chat") if which == "chat" else self.log
                    target.OnMouseLeftButtonDown()
                    self.game.hyperlink = ""
            finally:
                self.game.pressed.discard(A["DIK_LALT"])

    def effects(self, since=0):
        found = []
        for name, args in self.game.log[since:]:
            module = name.split(".", 1)[0]
            if module not in ("net", "chat", "ime", "interface"):
                continue
            if module == "ime" and name != "ime.PasteString":
                continue
            if name in LEFT_OUT or support.is_getter(name):
                continue
            found.append((name, args))
        return found

    def mark_log(self):
        return len(self.game.log)


def pair(**kwargs):
    return World(False, **kwargs), World(True, **kwargs)


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


# --- facades -----------------------------------------------------------------------------------

class Facades(unittest.TestCase):
    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)

    def check(self, legacy_class, novaui_class, methods, constants):
        for name in methods:
            self.assertTrue(hasattr(novaui_class, name), "%s.%s" % (novaui_class.__name__, name))
            legacy_method = getattr(legacy_class, name, None)
            if legacy_method is None:
                continue
            assert_callable_like(self, getattr(object.__new__(legacy_class), name),
                                 getattr(object.__new__(novaui_class), name), "%s.%s" % (novaui_class.__name__, name))
        for name in constants:
            self.assertEqual(getattr(novaui_class, name), getattr(legacy_class, name), name)
        self.assertIs(novaui_class.NUI_FACADE, True)
        self.assertEqual(novaui_class.__name__, legacy_class.__name__)
        self.assertEqual(len(inspect.signature(novaui_class.__init__).parameters),
                         len(inspect.signature(legacy_class.__init__).parameters), "the legacy constructor arguments")

    def test_the_chat_facade_keeps_the_legacy_surface(self):
        self.check(self.world.module("uiChat").ChatWindow, self.world.module("nui_chat").ChatWindow, CHAT_METHODS,
                   CHAT_CONSTANTS)
        self.assertEqual(self.world.module("nui_chat").ChatWindow.EDIT_LINE_HEIGHT, 25)
        self.assertEqual(self.world.module("nui_chat").ChatWindow.CHAT_WINDOW_WIDTH, 600)

    def test_the_chat_log_facade_keeps_the_legacy_surface(self):
        self.check(self.world.module("uiChat").ChatLogWindow, self.world.module("nui_chat_log").ChatLogWindow,
                   LOG_METHODS, LOG_CONSTANTS)

    def test_every_facade_answers_the_make_protocol_and_needs_the_wave2b_engine(self):
        hud = self.world.module("nui_hud")
        for module, name, key in (("nui_chat", "ChatWindow", "chat"), ("nui_chat_log", "ChatLogWindow", "chat-log")):
            with self.world, quiet():
                facade = getattr(self.world.module(module), name)()
                self.assertTrue(facade.nui_ready(), name)
                self.assertIs(hud.current(key), facade, name)
                again = getattr(self.world.module(module), name)()
                self.assertFalse(facade.nui_ready(), "%s: a new facade discards the previous one" % name)
                again.Destroy()
                self.assertFalse(again.nui_ready(), name)
                self.assertIsNone(hud.current(key), "%s: Destroy drops the record" % name)
        for engine in (False, "2a"):
            world = World(True, engine=bool(engine))
            if engine == "2a":
                # A Wave 2a exe: nuigame without the Wave 2b functions.
                world.game.put("nuigame", base.stub_module("nuigame", RefreshQuickSlots=lambda: None))
            with world, quiet():
                self.assertFalse(world.module("nui_hud").has_engine_2b(), engine)
                for module, name, key in (("nui_chat", "ChatWindow", "chat"), ("nui_chat_log", "ChatLogWindow", "chat-log")):
                    self.assertFalse(getattr(world.module(module), name)().nui_ready(), "%s on %s" % (name, engine))
                    made = world.nui_windows.make(key, getattr(world.module("uiChat"), name), "%s.%s" % (module, name))
                    self.assertEqual(type(made).__module__, "uiChat", "an older exe keeps the legacy %s" % name)


# --- the chat window, legacy against NovaUI ----------------------------------------------------------

class ChatDifferential(unittest.TestCase):
    def worlds(self):
        legacy, novaui = pair()
        for world in (legacy, novaui):
            world.enter_game()
        return legacy, novaui

    def flow(self, steps):
        """Runs `steps(world)` in both worlds; their effects and the field's
        text and mark after each step are equal."""
        legacy, novaui = self.worlds()
        marks = [world.mark_log() for world in (legacy, novaui)]
        seen = []
        for world in (legacy, novaui):
            texts = []
            for step in steps:
                step(world)
                texts.append((world.text(), world.mark()))
            seen.append(texts)
        self.assertEqual(seen[1], seen[0], "the field's text and mark after each step")
        self.assertEqual(novaui.effects(marks[1]), legacy.effects(marks[0]))
        return legacy, novaui

    def test_making_the_windows_makes_legacy_state_calls(self):
        legacy, novaui = pair()
        for world in (legacy, novaui):
            world.enter_game()
        self.assertEqual(novaui.effects(), legacy.effects())
        calls = [name for name, _ in novaui.effects()]
        self.assertEqual(calls[:8], ["chat.SetChatColor"] * 8)
        self.assertEqual(calls[8:11], ["chat.CreateChatSet", "chat.SetBoardState", "net.EnableChatInsultFilter"])
        self.assertIn(("chat.SetEndPos", (1, 1.0)), novaui.effects(), "legacy's log scrolls once as its first SetSize runs")
        self.assertEqual(novaui.game.calls("nuigame.ChatAttach"), [("nuigame.ChatAttach", ())],
                         "one attach for the window and the log")

    def test_open_type_and_enter_sends_and_stays_open(self):
        def opened(world):
            with world:
                world.interface.ToggleChat()
        legacy, novaui = self.flow([opened, lambda w: w.type("nuiw2b says hi"), lambda w: w.enter()])
        for world in (legacy, novaui):
            self.assertTrue(world.chat.IsEditMode())
            self.assertEqual(world.game.calls("net.SendChatPacket"), [("net.SendChatPacket", ("nuiw2b says hi", 0))])

    def test_the_prefixes_send_to_party_guild_and_shout_and_a_lone_prefix_closes(self):
        def opened(world):
            with world:
                world.chat.OpenChat()
        steps = [opened, lambda w: w.type("#party"), lambda w: w.enter(), lambda w: w.type("%guild"), lambda w: w.enter(),
                 lambda w: w.type("!shout"), lambda w: w.enter()]
        legacy, novaui = self.flow(steps)
        self.assertEqual(novaui.game.calls("net.SendChatPacket"), [("net.SendChatPacket", ("party", 3)), ("net.SendChatPacket", ("guild", 4)),
                                                                    ("net.SendChatPacket", ("shout", 6))])
        self.flow([opened, lambda w: w.type("#"), lambda w: w.enter()])
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            with world:
                world.chat.OpenChat()
            world.type("#")
            world.enter()
            self.assertFalse(world.chat.IsEditMode(), "a lone prefix closes")

    def test_a_second_shout_within_fifteen_seconds_gives_the_limit_line(self):
        def opened(world):
            with world:
                world.chat.OpenChat()

        def later(world):
            world.game.time += 14.0
        legacy, novaui = self.flow([opened, lambda w: w.type("!one"), lambda w: w.enter(), later, lambda w: w.type("!two"),
                                    lambda w: w.enter()])
        for world in (legacy, novaui):
            self.assertEqual(world.game.calls("net.SendChatPacket"), [("net.SendChatPacket", ("one", 6))])
            self.assertIn(("chat.AppendChat", (1, "CHAT_SHOUT_LIMIT")), world.effects())

    def test_an_insult_gives_the_info_line_instead_of_a_packet(self):
        def opened(world):
            with world:
                world.chat.OpenChat()
            world.game.answer("net", "IsChatInsultIn", lambda text: "bad" in text)
        legacy, novaui = self.flow([opened, lambda w: w.type("bad word"), lambda w: w.enter()])
        for world in (legacy, novaui):
            self.assertEqual(world.game.calls("net.SendChatPacket"), [])
            self.assertIn(("chat.AppendChat", (1, "CHAT_INSULT_STRING")), world.effects())

    def test_an_empty_enter_closes_and_escape_clears_and_closes(self):
        def opened(world):
            with world:
                world.chat.OpenChat()
        legacy, novaui = self.flow([opened, lambda w: w.type("   "), lambda w: w.enter()])
        for world in (legacy, novaui):
            self.assertFalse(world.chat.IsEditMode(), "an all-space Enter closes")
        legacy, novaui = self.flow([opened, lambda w: w.type("half typed"), lambda w: w.key("escape")])
        for world in (legacy, novaui):
            self.assertFalse(world.chat.IsEditMode())
        self.assertEqual(novaui.text(), "")

    def test_up_and_down_recall_the_history_as_legacy(self):
        def opened(world):
            with world:
                world.chat.OpenChat()
        steps = [opened]
        for text in ("first", "second", "third"):
            steps += [lambda w, t=text: w.type(t), lambda w: w.enter()]
        steps += [lambda w: w.key("up"), lambda w: w.key("up"), lambda w: w.key("down"), lambda w: w.key("up"),
                  lambda w: w.key("up"), lambda w: w.key("up"), lambda w: w.key("down")]
        legacy, novaui = self.flow(steps)
        self.assertEqual(novaui.text(), "second")

    def test_the_history_keeps_thirty_three_lines(self):
        world = World(True)
        world.enter_game()
        with world:
            world.chat.OpenChat()
        for i in range(40):
            world.type("line %d" % i)
            world.enter()
        self.assertEqual(len(world.chat.input.lastSentenceStack), 33, "legacy's > 32 check keeps 33")
        self.assertEqual(world.chat.input.lastSentenceStack[0], "line 7")

    def test_the_mode_button_cycles_party_guild_shout_and_back_with_the_mark(self):
        def opened(world):
            with world:
                world.chat.OpenChat()
        legacy, novaui = self.flow([opened, lambda w: w.mode(), lambda w: w.mode(), lambda w: w.mode(), lambda w: w.mode(),
                                    lambda w: w.mode()])
        self.assertEqual(novaui.text(), "#")
        self.assertEqual(novaui.mark(), "#")
        self.assertEqual(novaui.board().get("chat_mode"), 3)

    def test_the_mode_cycles_the_log_too_and_reopening_keeps_the_mode(self):
        def opened(world):
            with world:
                world.chat.OpenChat()

        def close_and_open(world):
            with world:
                world.chat.CloseChat()
                world.chat.OpenChat()
        legacy, novaui = self.flow([opened, lambda w: w.mode(), lambda w: w.mode(), close_and_open])
        self.assertEqual(novaui.text(), "%")
        for world in (legacy, novaui):
            self.assertEqual(world.text("log"), "%", "uiChat.RefreshChatMode cycles every chat input")
        with novaui:
            novaui.log.Show()
        self.assertEqual(novaui.log.board.get_value("chat-log-input"), "%", "the hidden log's field gets it when it shows")
        self.assertEqual(novaui.log.board.get("mark"), "%")

    def test_the_send_button_is_enter(self):
        def opened(world):
            with world:
                world.chat.OpenChat()
        legacy, novaui = self.flow([opened, lambda w: w.type("by button"), lambda w: w.send()])
        self.assertEqual(novaui.game.calls("net.SendChatPacket"), [("net.SendChatPacket", ("by button", 0))])

    def test_a_link_opens_the_tooltip_and_with_left_alt_pastes_into_the_open_field(self):
        def opened(world):
            with world:
                world.chat.OpenChat()
        legacy, novaui = self.flow([opened, lambda w: w.type("look "), lambda w: w.link(ITEM),
                                    lambda w: w.link(ITEM, alt=True)])
        self.assertEqual(novaui.text(), "look " + TAGGED_ITEM)
        for world in (legacy, novaui):
            self.assertEqual(world.game.calls("interface.MakeHyperlinkTooltip"), [("interface.MakeHyperlinkTooltip", (ITEM,))])
            self.assertEqual(world.game.calls("ime.PasteString"), [("ime.PasteString", (TAGGED_ITEM,))])
        self.assertEqual(novaui.game.legacy_pasted, [], "the paste reached the NovaUI field")

    def test_an_inventory_alt_click_pastes_into_the_focused_novaui_field(self):
        """D7: the legacy inventory's Alt+click calls ime.PasteString itself."""
        world = World(True)
        world.enter_game()
        with world:
            world.chat.OpenChat()
            world.game.modules["ime"].PasteString(TAGGED_ITEM)
        self.assertEqual(world.text(), TAGGED_ITEM)
        with world:
            world.chat.CloseChat()
            world.game.modules["ime"].PasteString(TAGGED_ITEM)
        self.assertEqual(world.game.legacy_pasted, [TAGGED_ITEM], "with no NovaUI field focused the legacy IME gets it")

    def test_tab_does_nothing_in_the_field(self):
        world = World(True)
        world.enter_game()
        with world:
            world.chat.OpenChat()
        world.type("abc")
        self.assertIs(world.key("tab"), True, "the field keeps Tab")
        self.assertEqual(world.text(), "abc")
        self.assertTrue(world.chat.IsEditMode())

    def test_the_visible_length_limit_counts_no_link_metadata(self):
        world = World(True)
        world.enter_game()
        with world:
            world.chat.OpenChat()
        world.type("x" * 76)
        world.type("y")
        self.assertEqual(world.text(), "x" * 76, "a 77th visible character is refused (D26)")
        world2 = World(True)
        world2.enter_game()
        with world2:
            world2.chat.OpenChat()
        world2.type("x" * 60)
        world2.type(TAGGED_ITEM)
        self.assertEqual(world2.text(), "x" * 60 + TAGGED_ITEM, "the link's tags do not count, its 12 shown characters do")
        world2.type("z" * 4)
        self.assertEqual(world2.text(), "x" * 60 + TAGGED_ITEM + "zzzz")
        world2.type("w")
        self.assertEqual(world2.text(), "x" * 60 + TAGGED_ITEM + "zzzz", "60 + 12 + 4 = 76")

    def test_open_focuses_the_field_and_close_gives_wndmgr_its_focus_back(self):
        world = World(True)
        world.enter_game()
        focus = world.game.focus
        self.assertIs(focus.active, world.gameWindow)
        with world:
            world.chat.OpenChat()
        board = world.board()
        self.assertEqual(board.focused, "chat-input")
        self.assertIsNot(focus.active, world.gameWindow, "the focus proxy holds wndMgr's focus, as a legacy edit line")
        self.assertTrue(world.chat.focusProxy.has_focus())
        with world:
            world.chat.CloseChat()
        self.assertIs(focus.active, world.gameWindow)
        self.assertEqual(board.focused, "chat-mode", "the field gave up the focus")

    def test_a_world_press_closes_the_chat_through_check_focus_as_legacy(self):
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            with world:
                world.chat.OpenChat()
                world.gameWindow.CheckFocus()
            self.assertFalse(world.chat.IsEditMode(), world.nui_on)
            self.assertIs(world.game.focus.active, world.gameWindow, world.nui_on)

    def test_a_whisper_dialog_takes_the_keys_and_gives_them_back_while_the_chat_stays_open(self):
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            with world, quiet():
                world.chat.OpenChat()
            world.type("chat text")
            with world, quiet():
                if world.nui_on:
                    world.board().fire("whisper", 0)
                else:
                    world.chat.btnSendWhisper.click()
            whisper = world.interface.whisper
            self.assertIs(world.game.focus.active, whisper, world.nui_on)
            self.assertTrue(world.chat.IsEditMode(), "the chat stays open")
            if world.nui_on:
                self.assertEqual(world.board().focused, "chat-mode", "the field gave up the keys")
            with world:
                world.interface.CloseWhisper()
            if world.nui_on:
                self.assertEqual(world.board().focused, "chat-input", "the field has the keys again")
                self.assertTrue(world.chat.focusProxy.has_focus())
            else:
                self.assertIs(world.game.focus.active, world.line(), "the edit line has the keys again")
            self.assertEqual(world.text(), "chat text")
        self.assertEqual(novaui.game.calls("interface.OpenWhisperDialogWithoutTarget"),
                         legacy.game.calls("interface.OpenWhisperDialogWithoutTarget"))

    def test_a_press_on_the_field_focuses_it_while_open(self):
        world = World(True)
        world.enter_game()
        with world:
            world.chat.OpenChat()
            world.board().focus("chat-mode")
            world.board().nui_field_press({"type": "mousedown", "button": 0, "target_id": "chat-input"})
        self.assertEqual(world.board().focused, "chat-input")
        with world:
            world.chat.CloseChat()
            world.board().nui_field_press({"type": "mousedown", "button": 0, "target_id": "chat-input"})
        self.assertEqual(world.board().focused, "chat-mode", "a closed chat's field takes no focus")

    def test_the_wheel_scrolls_the_open_chat_and_closing_goes_back_to_the_newest(self):
        world = World(True)
        world.enter_game()
        with world:
            for i in range(20):
                world.game.modules["chat"].AppendChat(0, "line %d" % i)
            world.chat.OpenChat()
            mark = world.mark_log()
            world.board().fire("wheel", -1.0)
        end_pos = world.game.chat.sets[0]["end"]
        self.assertAlmostEqual(end_pos, 1.0 - 3.0 / 12.0, msg="wheel up: three lines older (D12; RmlUi's up is negative)")
        with world:
            world.board().fire("wheel", 2.0)
        self.assertEqual(world.game.chat.sets[0]["end"], 1.0, "clamped at the newest")
        with world:
            world.board().fire("wheel", -1.0)
            world.chat.CloseChat()
        self.assertEqual(world.game.chat.sets[0]["end"], 1.0)
        calls = [(name, args) for name, args in world.effects(mark) if name == "chat.SetEndPos"]
        self.assertEqual(calls[-1], ("chat.SetEndPos", (0, 1.0)))
        with world:
            world.board().fire("wheel", -1.0)
        self.assertEqual(world.game.chat.sets[0]["end"], 1.0, "a closed chat does not scroll")

    def test_placement_puts_the_bottom_center_on_the_taskbar_top_at_every_scale(self):
        world = World(True)
        world.make_chat()
        board = world.board()
        self.assertEqual(board.placement, ("position", 800.0, 863.0, (0.5, 1.0)))
        self.assertAlmostEqual(board.get("history_height"), 138.0)
        world.game.state.scale = 1.5
        with world:
            world.chat.SetPosition(500, 900 - 25 - 74)
        self.assertEqual(board.placement, ("position", 800 / 1.5, 826 / 1.5, (0.5, 1.0)))
        with world:
            board.on_scale_changed(1.5)
        self.assertEqual(board.placement, ("position", 800 / 1.5, 826 / 1.5, (0.5, 1.0)))

    def test_the_history_holds_legacys_138_pixels_as_dp_at_every_scale(self):
        """interfacemodule.py's SetHeight(200) over the input line 62 px up:
        138 legacy pixels, 8 rows of 15dp, whatever the scale at login (a
        division by the scale gave 69dp, 3 rows, at 200%)."""
        for scale in (1.0, 1.5, 2.0):
            world = World(True)
            world.game.state.scale = scale
            world.make_chat()
            self.assertEqual(world.board().get("history_height"), 138.0, scale)
            with world:
                world.chat.SetPosition(500, 900 - 25 - 74)
                world.chat.SetHeight(200)
            self.assertEqual(world.board().get("history_height"), 138.0, "the taskbar's place does not change it")
        with world:
            world.chat.SetHeight(40)
        self.assertEqual(world.board().get("history_height"), 25.0, "at least 25, as the sizing bar's minimum")

    def test_the_sizing_bar_drag_sets_the_history_height(self):
        world = World(True)
        world.make_chat()
        with world:
            world.board().fire("resized", 228.0)
        self.assertEqual(world.board().get("history_height"), 228.0)

    def test_show_hide_and_the_whisper_and_log_buttons(self):
        world = World(True)
        world.enter_game()
        self.assertTrue(world.chat.IsShow())
        with world, quiet():
            world.board().fire("open_log", 0)
        self.assertTrue(world.log.IsShow())
        with world, quiet():
            world.board().fire("open_log", 1)
        self.assertTrue(world.log.IsShow(), "a right press does nothing")
        with world:
            world.chat.Hide()
        self.assertFalse(world.chat.IsShow())
        self.assertFalse(world.board().get("shown"))

    def test_destroy_detaches_the_feed_takes_the_mode_shim_out_and_frees_the_document(self):
        world = World(True)
        world.enter_game()
        ui_chat = world.module("uiChat")
        shims = len(ui_chat.chatInputSetList)
        board = world.board()
        with world:
            world.chat.Destroy()
        self.assertEqual(len(ui_chat.chatInputSetList), shims - 1)
        self.assertEqual(board._doc, 0)
        self.assertEqual(world.game.calls("nuigame.ChatDetach"), [], "the log still holds the feed")
        with world:
            world.log.Destroy()
        self.assertEqual(world.game.calls("nuigame.ChatDetach"), [("nuigame.ChatDetach", ())])
        self.assertIs(world.game.focus.active, world.gameWindow, "the game window keeps wndMgr's focus")
        self.assertEqual([w for w in world.game.focus.stack if type(w).__name__ == "_FocusWindow"], [],
                         "no focus proxy is left in wndMgr's list")


# --- the chat log, legacy against NovaUI ------------------------------------------------------------

class LogDifferential(unittest.TestCase):
    def worlds(self):
        legacy, novaui = pair()
        for world in (legacy, novaui):
            world.enter_game()
        return legacy, novaui

    def filter(self, world, index):
        with world, quiet():
            if world.nui_on:
                world.log.board.fire("filter", index, 0)
            else:
                world.log.modeButtonList[index].click()

    def all(self, world):
        with world, quiet():
            if world.nui_on:
                world.log.board.fire("filter_all", 0)
            else:
                world.log.btnAll.click()

    def test_the_filters_follow_legacy_bit_logic(self):
        legacy, novaui = self.worlds()
        marks = [w.mark_log() for w in (legacy, novaui)]
        masks = []
        for world in (legacy, novaui):
            seen = []
            for step in (lambda w: self.filter(w, 1), lambda w: self.filter(w, 4), lambda w: self.filter(w, 1),
                         lambda w: self.all(w), lambda w: self.all(w), lambda w: self.filter(w, 0)):
                step(world)
                seen.append(tuple(world.game.chat.sets[1]["modes"]))
            masks.append(seen)
        self.assertEqual(masks[1], masks[0])
        self.assertEqual(novaui.effects(marks[1]), legacy.effects(marks[0]))
        # After Party: party and the types the six never name.
        self.assertEqual(masks[1][0], (0, 0, 0, 1, 0, 1, 0, 1, 1))
        board = novaui.log.board
        self.assertEqual(board.get("all"), False)
        self.assertEqual(board.get("filters"), [True, False, False, False, False, False])

    def test_the_filter_buttons_show_their_legacy_states(self):
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            self.filter(world, 1)
            self.filter(world, 2)
        legacy_states = [button.down for button in legacy.log.modeButtonList]
        self.assertEqual(novaui.log.board.get("filters"), legacy_states)
        self.assertEqual(novaui.log.board.get("all"), legacy.log.allChatMode)
        for world in (legacy, novaui):
            self.all(world)
        self.assertEqual(novaui.log.board.get("filters"), [button.down for button in legacy.log.modeButtonList])
        self.assertEqual(novaui.log.board.get("all"), True)

    def test_the_scroll_bar_sets_the_end_position(self):
        legacy, novaui = self.worlds()
        marks = [w.mark_log() for w in (legacy, novaui)]
        for world in (legacy, novaui):
            with world, quiet():
                if world.nui_on:
                    world.log.board.fire("scroll", 0.0)
                    world.log.board.fire("scroll", 1.0)
                    world.log.board.fire("scroll", 1.0)
                else:
                    world.log.scrollBar.drag_to(0.0)
                    world.log.scrollBar.drag_to(1.0)
        self.assertEqual(novaui.effects(marks[1]), legacy.effects(marks[0]))
        self.assertEqual(novaui.effects(marks[1]), [("chat.SetEndPos", (1, 0.0)), ("chat.SetEndPos", (1, 1.0))])

    def test_the_wheel_moves_the_end_and_the_slider_follows(self):
        world = World(True)
        world.enter_game()
        with world:
            for i in range(20):
                world.game.modules["chat"].AppendChat(0, "line %d" % i)
            world.log.board.fire("wheel", -2.0)
        self.assertAlmostEqual(world.game.chat.sets[1]["end"], 1.0 - 6.0 / 17.0)
        self.assertAlmostEqual(world.log.board.get("end_pos"), 1.0 - 6.0 / 17.0)
        with world:
            world.log.board.fire("scroll", round(1.0 - 6.0 / 17.0, 2))
        self.assertAlmostEqual(world.game.chat.sets[1]["end"], 1.0 - 6.0 / 17.0, msg="the slider's own echo is not a scroll")

    def test_typing_in_the_log_sends_escape_closes_and_an_empty_enter_does_nothing(self):
        legacy, novaui = self.worlds()
        marks = [w.mark_log() for w in (legacy, novaui)]
        for world in (legacy, novaui):
            with world:
                world.log.Open()
            world.type("nuiw2b log", "log")
            world.enter("log")
            self.assertTrue(world.log.IsShow(), "Enter keeps the log open")
            self.assertEqual(world.text("log"), "")
            world.enter("log")
            self.assertTrue(world.log.IsShow(), "an empty Enter does nothing (ChatLine's default return event)")
            world.key("escape", "log")
            self.assertFalse(world.log.IsShow(), "Escape closes the log")
        self.assertEqual(novaui.effects(marks[1]), legacy.effects(marks[0]))
        self.assertEqual(novaui.game.calls("net.SendChatPacket"), [("net.SendChatPacket", ("nuiw2b log", 0))])

    def test_a_link_in_the_log(self):
        legacy, novaui = self.worlds()
        marks = [w.mark_log() for w in (legacy, novaui)]
        for world in (legacy, novaui):
            world.link(ITEM, which="log")
        self.assertEqual(novaui.effects(marks[1]), legacy.effects(marks[0]))
        self.assertEqual(novaui.effects(marks[1]), [("interface.MakeHyperlinkTooltip", (ITEM,))])

    def test_show_does_not_focus_the_field_open_does_and_escape_reaches_it_in_the_legacy_chain(self):
        world = World(True)
        world.enter_game()
        with world:
            world.log.Show()
        self.assertIsNone(world.log.board.focused)
        self.assertTrue(world.log.escapeProxy.is_shown())
        with world:
            world.log.Hide()
            world.log.Open()
        self.assertEqual(world.log.board.focused, "chat-log-input")
        self.assertTrue(world.log.focusProxy.has_focus())
        with world:
            self.assertIs(world.log.escapeProxy._window.OnPressEscapeKey(), True)
        self.assertFalse(world.log.IsShow())
        self.assertFalse(world.log.escapeProxy.is_shown())
        self.assertIs(world.game.focus.active, world.gameWindow, "the log's field gave wndMgr's focus back")

    def test_the_log_field_keeps_the_focus_it_takes_from_the_open_chat(self):
        """Both facades own a FocusProxy. A press on the log's field moves
        wndMgr's focus from the chat's proxy to the log's; the chat must not
        answer by moving NovaUI's one focus to its mode button, which would
        leave no field focused and send the keys to the game's hotkeys."""
        world = World(True)
        world.enter_game()
        with world, quiet():
            world.chat.OpenChat()
            world.log.Show()
        chat_board, log_board = world.chat.board, world.log.board
        mark = len(chat_board.calls)
        with world:
            log_board.nui_field_press({"type": "mousedown", "button": 0, "target_id": "chat-log-input"})
        self.assertEqual(log_board.focused, "chat-log-input")
        self.assertTrue(world.log.focusProxy.has_focus())
        self.assertNotIn(("focus", "chat-mode"), chat_board.calls[mark:], "the chat left NovaUI's focus on the log's field")
        self.assertTrue(world.chat.IsEditMode(), "the chat stays open")
        # RmlUi keeps one focus: the last focus call across both documents is
        # the one that holds. Closing the log moves its own focus off first,
        # then wndMgr gives the chat's proxy its focus back and the chat's
        # field takes NovaUI's.
        order = []
        for board in (chat_board, log_board):
            def recording(element_id, board=board, focus=board.focus):
                order.append(element_id)
                return focus(element_id)
            board.focus = recording
        with world:
            world.log.Close()
        self.assertTrue(world.chat.focusProxy.has_focus(), "wndMgr gave the chat's proxy its focus back")
        self.assertEqual(order, ["chat-log-mode", "chat-input"], "the chat's field holds NovaUI's focus last")

    def test_the_open_chat_keeps_the_focus_it_takes_from_the_log_field(self):
        world = World(True)
        world.enter_game()
        with world, quiet():
            world.log.Open()
        log_board = world.log.board
        self.assertTrue(world.log.focusProxy.has_focus())
        mark = len(log_board.calls)
        with world:
            world.chat.OpenChat()
        self.assertEqual(world.chat.board.focused, "chat-input")
        self.assertTrue(world.chat.focusProxy.has_focus())
        self.assertNotIn(("focus", "chat-log-mode"), log_board.calls[mark:], "the log left NovaUI's focus on the chat's field")
        self.assertTrue(world.log.IsShow())
        # The log's field lost NovaUI's focus to the chat's (RmlUi's blur);
        # the chat closing gives wndMgr's back to the log's proxy, whose field
        # takes NovaUI's again, and the chat does not move it after.
        with world:
            log_board.handlers[("chat-log-input", "blur")]({"type": "blur", "target_id": "chat-log-input"})
        order = []
        for board in (world.chat.board, log_board):
            def recording(element_id, board=board, focus=board.focus):
                order.append(element_id)
                return focus(element_id)
            board.focus = recording
        with world:
            world.chat.CloseChat()
        self.assertTrue(world.log.focusProxy.has_focus())
        self.assertEqual(order[-1], "chat-log-input", "the log's field holds NovaUI's focus last")

    def test_the_resize_sets_the_size_and_the_field_limit(self):
        world = World(True)
        world.enter_game()
        with world:
            world.log.board.fire("resized", 570.0, 210.0)
        self.assertEqual(world.log.board.get("log_width"), 570.0)
        self.assertEqual(world.log.input.userMax, 570 // 8)
        self.assertEqual(world.log.input.userMax, 71)


# --- nui_hud's Wave 2b helpers ------------------------------------------------------------------------

class FocusProxy(unittest.TestCase):
    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)
        self.events = []
        self.world.gameWindow.SetFocus()

    def lost(self):
        self.events.append("lost")

    def gained(self):
        self.events.append("gained")

    def test_take_and_release_run_no_callback_and_follow_wndmgr(self):
        proxy = self.world.module("nui_hud").FocusProxy(self.lost, self.gained)
        proxy.take()
        proxy.take()
        self.assertTrue(proxy.has_focus())
        self.assertEqual(self.world.game.focus.stack, [self.world.gameWindow])
        proxy.release()
        self.assertFalse(proxy.has_focus())
        self.assertIs(self.world.game.focus.active, self.world.gameWindow)
        proxy.release()
        self.assertEqual(self.events, [])

    def test_another_edit_line_runs_on_lost_and_its_close_runs_on_gained(self):
        proxy = self.world.module("nui_hud").FocusProxy(self.lost, self.gained)
        proxy.take()
        line = self.world.game.modules["ui"].EditLine()
        line.SetFocus()
        self.assertEqual(self.events, ["lost"])
        line.KillFocus()
        self.assertEqual(self.events, ["lost", "gained"])
        self.assertTrue(proxy.has_focus())

    def test_keys_pass_on_the_window_is_never_picked_and_destroy_lets_go(self):
        proxy = self.world.module("nui_hud").FocusProxy(self.lost, self.gained)
        window = proxy._window
        self.assertIs(window.OnKeyDown(0x3B), False)
        self.assertEqual(window.size, (0, 0))
        proxy.take()
        proxy.destroy()
        self.assertIs(self.world.game.focus.active, self.world.gameWindow)
        self.assertEqual(self.events, [])
        proxy.destroy()

    def test_another_proxy_taking_the_focus_runs_no_on_lost(self):
        events = []
        first = self.world.module("nui_hud").FocusProxy(self.lost, self.gained)
        second = self.world.module("nui_hud").FocusProxy(lambda: events.append("second lost"), lambda: events.append("second gained"))
        first.take()
        second.take()
        self.assertTrue(second.has_focus())
        self.assertEqual(self.events, [], "the second proxy's field has NovaUI's focus already")
        second.release()
        self.assertTrue(first.has_focus())
        self.assertEqual(self.events, ["gained"], "wndMgr gave the first its focus back")
        line = self.world.game.modules["ui"].EditLine()
        line.SetFocus()
        self.assertEqual(self.events, ["gained", "lost"], "a legacy edit line still runs on_lost")
        self.assertEqual(events, [])

    def test_the_callbacks_are_held_weakly(self):
        class Owner(object):
            def __init__(self, test):
                self.test = test

            def lost(self):
                self.test.events.append("owner lost")

            def gained(self):
                pass

        owner = Owner(self)
        proxy = self.world.module("nui_hud").FocusProxy(owner.lost, owner.gained)
        proxy.take()
        del owner
        self.world.game.modules["ui"].EditLine().SetFocus()
        self.assertEqual(self.events, [], "a collected owner gets no call")


class EngineCheck(unittest.TestCase):
    def test_has_engine_2b_needs_the_chat_view_and_anchor_functions(self):
        world = World(True)
        with world:
            hud = world.module("nui_hud")
            self.assertTrue(hud.has_engine_2b())
            for missing in ("ChatAttach", "ViewState", "AnchorState"):
                functions = {name: (lambda *a: None) for name in ("ChatAttach", "ViewState", "AnchorState") if name != missing}
                world.game.put("nuigame", base.stub_module("nuigame", **functions))
                self.assertFalse(hud.has_engine_2b(), missing)


class ElementBox(unittest.TestCase):
    def test_nui_py_element_box_answers_the_box_and_none_without_a_document_or_the_function(self):
        boxes = {(7, "chat-input"): [1.0, 2.0, 3.0, 4.0]}
        fake = types.SimpleNamespace(IsAvailable=lambda: True, GetElementBox=lambda doc, element_id: boxes.get((doc, element_id)))
        modules = base.Modules(_nui=fake)
        self.addCleanup(modules.restore)
        nui = modules.load("nui")
        window = object.__new__(nui.Window)
        window._doc = 7
        self.assertEqual(window.element_box("chat-input"), (1.0, 2.0, 3.0, 4.0))
        self.assertIsNone(window.element_box("missing"))
        window._doc = 0
        self.assertIsNone(window.element_box("chat-input"))
        window._doc = 7
        del fake.GetElementBox
        self.assertIsNone(window.element_box("chat-input"), "an exe whose _nui has no GetElementBox")

    def test_the_stand_in_answers_the_boxes_of_a_shown_window(self):
        state = base.NuiState()
        nui = base.make_nui(state)
        window = type("W", (nui.Window,), {"DOCUMENT": "d.rml", "MODEL": "m"})()
        state.boxes[("d.rml", "x")] = (1, 2, 3, 4)
        self.assertIsNone(window.element_box("x"), "hidden")
        window.show()
        self.assertEqual(window.element_box("x"), (1, 2, 3, 4))


# --- fixtures, documents and per-frame Python -------------------------------------------------------

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

    def check(self, board_class, window, variants):
        board = board_class(object())
        model = board.initial_model()
        for variant in (None,) + tuple(variants):
            values = fixture(window, variant)[board_class.MODEL]
            self.assertEqual(set(values), set(model), "%s %s: the fixture holds every model key" % (window, variant))
            for key, value in values.items():
                self.assertEqual(kind(value), kind(model[key]), "%s.%s" % (window, key))
            self.assertTrue(board.set(**values))
        self.assertEqual(self.world.game.dbg.errors, [])

    def check_lines(self, path, now=1.0):
        nui_text = self.world.module("nui_text")
        with open(path, encoding="utf-8") as handle:
            lines = json.load(handle)
        self.assertTrue(lines, path)
        ids = [line["id"] for line in lines]
        self.assertEqual(ids, sorted(set(ids)), "%s: ids rise, oldest first" % path)
        for line in lines:
            self.assertEqual(set(line), {"id", "type", "t", "runs"}, path)
            self.assertTrue(0 <= line["type"] <= 8, path)
            self.assertTrue(now - 4.0 <= line["t"] <= now, "%s: t within 4 s before the snap clock" % path)
            for run in line["runs"]:
                self.assertEqual(set(run), {"text", "color", "link"}, path)
            text = "".join(("|H%s|h%s|h" % (run["link"], run["text"][:-1])) if run["link"] else run["text"] for run in line["runs"])
            if all(run["color"] == -1 for run in line["runs"]):
                self.assertEqual([list(r) for r in nui_text.parse_runs(text)],
                                 [[run["text"], run["color"], run["link"]] for run in line["runs"]], path)
        return lines

    def test_the_chat_fixtures_match_the_model(self):
        module = self.world.module("nui_chat")
        self.check(module.ChatBoard, "chat", ("open", "no-view-chat"))
        self.assertEqual(module.ChatBoard.FEEDS, {"view_chat": "system.view_chat"})
        open_lines = self.check_lines(os.path.join(WINDOWS, "chat", "chat.open.chat.window.lines.json"))
        self.assertEqual(len(open_lines), 8)
        self.assertTrue(any(run["link"] for line in open_lines for run in line["runs"]), "one line has a link")
        self.assertTrue(any(run["color"] != -1 and not run["link"] for line in open_lines for run in line["runs"]),
                        "one line has a color tag")
        closed = self.check_lines(os.path.join(WINDOWS, "chat", "chat.chat.window.lines.json"))
        self.assertEqual([line["type"] for line in closed], [0, 1, 2])
        self.assertEqual(fixture("chat", "open")["chat"]["mark"], "#")
        self.assertFalse(fixture("chat", "no-view-chat")["chat"]["view_chat"])

    def test_the_chat_log_fixtures_match_the_model(self):
        module = self.world.module("nui_chat_log")
        self.check(module.ChatLogBoard, "chat-log", ("party",))
        lines = self.check_lines(os.path.join(WINDOWS, "chat-log", "chat-log.chat.log.lines.json"))
        self.assertEqual(sorted({line["type"] for line in lines}), list(range(9)), "every type")
        party = self.check_lines(os.path.join(WINDOWS, "chat-log", "chat-log.party.chat.log.lines.json"))
        self.assertTrue(all(line["type"] in (3, 5, 7, 8) for line in party), "party and the types the six never hide")
        self.assertEqual(fixture("chat-log", "party")["chatlog"]["filters"], [False, True, False, False, False, False])

    def test_every_document_id_the_spec_names_exists(self):
        chat = read(os.path.join(WINDOWS, "chat", "chat.rml"))
        for element_id in ("chat", "chat-history", "chat-resize", "chat-lines", "chat-input-row", "chat-mode", "chat-input",
                           "chat-mark", "chat-send", "chat-whisper", "chat-log-open"):
            self.assertIn('id="%s"' % element_id, chat, element_id)
        log = read(os.path.join(WINDOWS, "chat-log", "chat-log.rml"))
        for element_id in ["chat-log", "chat-log-title", "chat-log-close", "chat-log-all", "chat-log-lines", "chat-log-scroll",
                           "chat-log-input-row", "chat-log-resize"] + ["chat-log-filter-%d" % i for i in range(6)]:
            self.assertIn('id="%s"' % element_id, log, element_id)
        self.assertIn('<nui-chat-lines id="chat-lines" class="chat__lines" view="window" step="15"', chat)
        self.assertIn('data-attr-mode="open ? \'edit\' : \'view\'"', chat)
        self.assertIn('view="log" mode="log" step="15"', log)
        self.assertIn('edge="top" target="chat-history"', chat)
        self.assertIn('edge="bottom-right" target="chat-log"', log)
        self.assertIn('maxlength="512"', chat)

    def test_the_bodies_carry_the_typing_classes_and_take_no_focus_but_their_fields(self):
        for window in ("chat", "chat-log"):
            body = re.search(r"<body[^>]*\bclass=\"([^\"]*)\"", read(os.path.join(WINDOWS, window, window + ".rml"))).group(1).split()
            for name in ("nui-below-legacy-ui", "nui-field-passes-hotkeys", "nui-field-keeps-focus"):
                self.assertIn(name, body, window)
            sheet = read(os.path.join(WINDOWS, window, window + ".rcss"))
            self.assertRegex(sheet, r"body\.%s\s*\{[^}]*focus: none;" % window, window)
            self.assertRegex(sheet, r"input\.%s__input\s*\{[^}]*focus: auto;" % window.replace("-log", "-log"), window)


class NoPerFramePython(unittest.TestCase):
    def test_no_chat_module_defines_a_per_frame_hook(self):
        for name in CHAT_MODULES:
            tree = ast.parse(read(os.path.join(ROOT, name + ".py")))
            defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
            self.assertEqual(defined & {"OnUpdate", "OnRender", "OnMouseOverIn"}, set(), name)


class Layers(unittest.TestCase):
    def test_the_chat_windows_draw_below_the_legacy_ui_layer_as_their_legacy_windows_live_in_it(self):
        tree = ast.parse(read(os.path.join(ROOT, "uichat.py")))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in ("ChatWindow", "ChatLogWindow"):
                init = next(item for item in node.body if isinstance(item, ast.FunctionDef) and item.name == "__init__")
                layers = [call for call in ast.walk(init) if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                          and call.func.attr == "__init__" and len(call.args) >= 2]
                self.assertEqual(layers, [], "%s: ui.Window's default layer, UI" % node.name)


# --- shared content pieces ------------------------------------------------------------------------

class SharedPieces(unittest.TestCase):
    def test_the_template_links_the_five_components_after_the_digits(self):
        template = read(os.path.join(NUI, "nui.rtpl"))
        links = re.findall(r'href="components/([\w-]+)\.rcss"', template)
        start = links.index("number")
        self.assertEqual(links[start + 1:start + 6], ["text", "chat", "view", "anchor", "resize"])

    def test_every_palette_has_the_chat_tokens_and_the_line_rules_use_them(self):
        tokens = json.loads(read(os.path.join(NUI, "theme", "tokens.json")))
        names = ("chat-talking", "chat-info", "chat-notice", "chat-party", "chat-guild", "chat-command", "chat-shout",
                 "chat-whisper", "chat-big-notice", "chat-view-shade-top", "chat-view-shade-bottom", "chat-edit-shade",
                 "chat-mark", "text-outline")
        for palette in ("dark", "light", "classic"):
            for name in names:
                self.assertIn(name, tokens[palette], "%s %s" % (palette, name))
        legacy = ("#ffffff", "#ffc8c8", "#ffe6ba", "#00ffe4", "#fdff7c", "#a7ffd4", "#a7ffd4", "#4ae14a", "#ffe6ba")
        self.assertEqual(tuple(tokens["classic"][name] for name in names[:9]), legacy, "legacy's colors (colorinfo.py, PythonChat.cpp)")
        self.assertEqual(tokens["classic"]["chat-mark"], "#ffff00")
        sheet = read(os.path.join(NUI, "components", "chat.rcss"))
        for index, name in enumerate(names[:9]):
            self.assertIn(".nui-chat__line--t%d { color: var(--%s); }" % (index, name), sheet)
        # The element steps the fade's opacity; a transition on is-fading would
        # rebuild the line's meshes every frame (WAVE2B F3).
        self.assertNotIn("is-fading\n{", sheet)
        self.assertNotIn("transition: opacity", sheet)

    def test_no_window_or_component_sheet_names_a_skin_class(self):
        for folder in (os.path.join(WINDOWS, "chat"), os.path.join(WINDOWS, "chat-log"), os.path.join(NUI, "components")):
            for name in os.listdir(folder):
                if name.endswith(".rcss") or name.endswith(".rml"):
                    self.assertNotIn("skin-classic", read(os.path.join(folder, name)), name)
        for name in ("chat.rcss", "chat-log.rcss"):
            overlay = read(os.path.join(CLASSIC_WINDOWS, name))
            self.assertNotRegex(overlay, r"#[a-z][\w-]*\s*[{,]", "%s: no ids in classic rules" % name)

    def test_the_vector_file_is_the_shared_one(self):
        path = os.path.join(base.HERE, "fixtures", "text_tags_cases.json")
        self.assertIn("Keep the two copies byte-identical", read(path))


# --- the wiring (P10 spec 5.8) ------------------------------------------------------------------------

WAVE2B_SITES = {
    "interfacemodule.py": [("make", "chat", "uiChat.ChatWindow", "nui_chat.ChatWindow"),
                           ("make", "minimap", "uiMiniMap.MiniMap", "nui_minimap.MiniMap"),
                           ("make", "chat-log", "uiChat.ChatLogWindow", "nui_chat_log.ChatLogWindow"),
                           ("make", "guild-war", "uiGuild.GuildWarScoreBoard", "nui_guild_war.GuildWarScoreBoard"),
                           ("make", "shop-signs", "uiPrivateShopBuilder.PrivateShopAdvertisementBoard", "nui_shop_signs.ShopSign")],
    "game.py": [("make", "player-gauge", "uiPlayerGauge.PlayerGauge", "nui_player_gauge.PlayerGauge")],
}
WAVE2B_IDS = ("chat", "chat-log", "minimap", "atlas", "player-gauge", "shop-signs", "guild-war")


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
    NUI_FACADE = False
    made = []

    def __init__(self, *args):
        Recorded.made.append((type(self).__name__, args))
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
    def test_the_wired_files_name_exactly_the_wave2b_windows_and_classes(self):
        for file_name, expected in WAVE2B_SITES.items():
            sites = [site for site in factory_sites(file_name) if site[1] in WAVE2B_IDS]
            self.assertEqual(sites, expected, file_name)

    def interface(self, windows, raising=()):
        """interfacemodule.py over MagicMock modules (but nui_windows, nui, dbg,
        systemSetting and sys), with recording window classes."""
        source = read(os.path.join(ROOT, "interfacemodule.py"))
        names = set()
        for node in ast.parse(source).body:
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
        game = support.Game()
        game.modules["systemSetting"].GetUINuiWindows = lambda: windows
        modules = {name: mock.MagicMock(name=name) for name in names - {"sys", "nui_windows", "systemSetting", "dbg", "ui"}}
        Recorded.made = []
        legacy = {("uiChat", "ChatWindow"), ("uiChat", "ChatLogWindow"), ("uiMiniMap", "MiniMap"),
                  ("uiGuild", "GuildWarScoreBoard"), ("uiPrivateShopBuilder", "PrivateShopAdvertisementBoard")}
        for module, name in legacy:
            setattr(modules[module], name, window_class(name, False))
        modules["uiChat"].ChatWindow.CHAT_WINDOW_WIDTH = 600
        modules["uiChat"].ChatWindow.EDIT_LINE_HEIGHT = 25
        for module_name, class_name in (("nui_chat", "ChatWindow"), ("nui_chat_log", "ChatLogWindow"), ("nui_minimap", "MiniMap"),
                                        ("nui_guild_war", "GuildWarScoreBoard"), ("nui_shop_signs", "ShopSign")):
            module = types.ModuleType(module_name)
            if module_name in raising:
                def boom(*args):
                    raise RuntimeError("boom")
                setattr(module, class_name, boom)
            else:
                setattr(module, class_name, window_class("Nui" + class_name, True))
                if class_name == "ChatWindow":
                    module.ChatWindow.CHAT_WINDOW_WIDTH = 600
                    module.ChatWindow.EDIT_LINE_HEIGHT = 25
            modules[module_name] = module
        for name, module in modules.items():
            game.put(name, module)
        game.load("nui_windows", "nui_windows.py")
        interface_module = game.load("interfaceModule", "interfacemodule.py")
        interface = object.__new__(interface_module.Interface)
        interface.wndGuild = mock.MagicMock()
        interface.guildScoreBoardDict = {}
        interface.privateShopAdvertisementBoardDict = {}
        return game, interface_module, interface

    def make_sites(self, game, interface):
        with game:
            interface._Interface__MakeChatWindow()
            interface._Interface__MakeWindows()
            interface.OnStartGuildWar(1, 2)
            interface.AppearPrivateShop(77, "shop")
        return [type(x).__name__ for x in (interface.wndChat, interface.wndChatLog, interface.wndMiniMap,
                                           interface.guildScoreBoardDict[next(iter(interface.guildScoreBoardDict))],
                                           interface.privateShopAdvertisementBoardDict[77])]

    def test_with_every_flag_off_the_interface_makes_the_legacy_windows(self):
        game, module, interface = self.interface("")
        made = self.make_sites(game, interface)
        self.assertEqual(made, ["ChatWindow", "ChatLogWindow", "MiniMap", "GuildWarScoreBoard", "PrivateShopAdvertisementBoard"])
        self.assertNotIn("atlas", game.loaded["nui_windows"].DECISIONS, "the atlas guard asks nothing then")
        self.assertEqual(game.dbg.errors, [])

    def test_with_each_flag_on_the_interface_makes_exactly_the_named_class(self):
        game, module, interface = self.interface("+hud2")
        made = self.make_sites(game, interface)
        self.assertEqual(made, ["NuiChatWindow", "NuiChatLogWindow", "NuiMiniMap", "NuiGuildWarScoreBoard", "NuiShopSign"])
        self.assertEqual(game.dbg.errors, [])
        for flag, index, name in (("chat", 0, "NuiChatWindow"), ("chat-log", 1, "NuiChatLogWindow"), ("minimap", 2, "NuiMiniMap"),
                                  ("guild-war", 3, "NuiGuildWarScoreBoard"), ("shop-signs", 4, "NuiShopSign")):
            game, module, interface = self.interface("+" + flag)
            made = self.make_sites(game, interface)
            self.assertEqual(made[index], name, flag)
            self.assertEqual(sum(1 for x in made if x.startswith("Nui")), 1, flag)

    def test_the_atlas_on_with_the_legacy_minimap_is_refused(self):
        game, module, interface = self.interface("+atlas")
        self.make_sites(game, interface)
        self.assertEqual(game.loaded["nui_windows"].DECISIONS["atlas"], "legacy: needs the NovaUI minimap")
        game, module, interface = self.interface("+atlas,+minimap")
        self.make_sites(game, interface)
        self.assertNotEqual(game.loaded["nui_windows"].DECISIONS.get("atlas"), "legacy: needs the NovaUI minimap")

    def test_a_novaui_class_that_raises_falls_back_to_the_legacy_one(self):
        game, module, interface = self.interface("+chat,+chat-log", raising=("nui_chat",))
        made = self.make_sites(game, interface)
        self.assertEqual(made[:2], ["ChatWindow", "NuiChatLogWindow"])
        self.assertEqual(game.dbg.errors, ["nui_windows: chat: the controller could not be made (RuntimeError); using the legacy window"])

    def test_interface_close_closes_the_novaui_signs_only_when_their_module_is_loaded(self):
        for loaded in (False, True):
            game, module, interface = self.interface("")
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
            signs = types.ModuleType("nui_shop_signs")
            signs.close_all = lambda: closed.append(1)
            with game:
                game.modules["uiQuest"].QuestDialog.__dict__ = {}
                sys.modules.pop("nui_edge_buttons", None)
                if loaded:
                    sys.modules["nui_shop_signs"] = signs
                else:
                    sys.modules.pop("nui_shop_signs", None)
                try:
                    interface.Close()
                finally:
                    sys.modules.pop("nui_shop_signs", None)
            self.assertEqual(closed, [1] if loaded else [], loaded)
            self.assertEqual(interface.privateShopAdvertisementBoardDict, {})

    def test_game_close_destroys_only_a_novaui_gauge(self):
        source = read(os.path.join(ROOT, "game.py"))
        self.assertIn('\t\tif getattr(self.playerGauge, "NUI_FACADE", False):\n\t\t\tself.playerGauge.Destroy()\n'
                      '\t\tself.playerGauge = None', source)
        self.assertIn('self.playerGauge = nui_windows.make("player-gauge", uiPlayerGauge.PlayerGauge, '
                      '"nui_player_gauge.PlayerGauge", self)', source)

    def test_no_other_legacy_file_changes_its_windows(self):
        for file_name in ("uichat.py", "uiminimap.py", "uiplayergauge.py", "uiprivateshopbuilder.py", "uiguild.py"):
            self.assertNotIn("nui_windows", read(os.path.join(ROOT, file_name)), file_name)


if __name__ == "__main__":
    unittest.main()
