"""Tests for the auto-shout's client half (NOVA-204; OLD uiChat.py:1042-1046,
1571-1840): python3 -B -m unittest auto_shout_test (from tools/).

The server owns the repeat (group S: "/auto_shout on <text>", "/auto_shout
off", and the chat command "AutoShoutState <0|1> <seconds>" after every
change and every repeat). Here:
- assets/root/autoshout.py, the switch, the per-character message (saved in
  config/auto_shout.txt), the countdown and the lifetime: a warp (a new game
  phase on the same character and channel) sends "on <text>" again once; a
  channel change, a return to the character select and a new login switch it
  off; the server's "0" switches it off;
- the chat's send path (legacy uichat.ChatLine and NovaUI nui_chat.ChatInput)
  records each shout the player sends as the character's message;
- the window, legacy uiautoshout.AutoShoutWindow (made from its uiscript) and
  NovaUI nui_auto_shout.AutoShoutWindow (the facade over it): the message
  field prefilled, Start and Stop, the state and the countdown
  (nui-countdown), Enter and Escape in the field;
- the button by the chat input in both chats, and the wiring (the window id
  "auto-shout", the Interface's make site, AutoShoutState, the phase hook)."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_test_support as base  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import nui_chat_test as chat_test  # noqa: E402
import social_test  # noqa: E402

ROOT = support.ROOT
NUI = os.path.join(ROOT, "..", "nui", "nui")
DOCUMENT = "nui/windows/auto-shout/auto-shout.rml"
FIELD = "auto-shout-message"


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class Recorder(object):
    """A stand-in module whose functions record their calls."""

    def __init__(self, name, log, **answers):
        self._name = name
        self._log = log
        self._answers = answers

    def __getattr__(self, attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        answers, log, name = self._answers, self._log, self._name

        def call(*args):
            log.append(("%s.%s" % (name, attr), args))
            answer = answers.get(attr)
            return answer(*args) if callable(answer) else answer
        return call


class Files(object):
    """config files in memory (the client's disk)."""

    def __init__(self):
        self.files = {}

    def open(self, path, mode="r"):
        import io
        files = self.files

        class File(io.StringIO):
            def __exit__(self, *exc):
                if "w" in mode:
                    files[path] = self.getvalue()
                return io.StringIO.__exit__(self, *exc)

        if "r" in mode and path not in files:
            raise IOError(path)
        return File(files.get(path, "") if "r" in mode else "")


class Logic(unittest.TestCase):
    """autoshout.py over recording stand-ins."""

    def setUp(self):
        self.log = []
        self.time = [100.0]
        self.name = ["Hero"]
        self.channel = [1]
        self.files = Files()
        self.modules = base.Modules(
            app=Recorder("app", self.log, GetTime=lambda: self.time[0]),
            net=Recorder("net", self.log, GetChannelNum=lambda: self.channel[0]),
            player=Recorder("player", self.log, GetName=lambda: self.name[0]),
            chat=Recorder("chat", self.log), localeInfo=types.SimpleNamespace(AUTO_SHOUT_NO_MESSAGE="no message"))
        sys.modules["chat"].CHAT_TYPE_INFO = 1
        self.addCleanup(self.modules.restore)
        self.m = self.modules.load("autoshout")
        self.m.OPENER = self.files.open

    def sent(self):
        return [args[0] for name, args in self.log if name == "net.SendChatPacket"]

    def phase(self, class_name):
        window = type(class_name, (object,), {})()
        self.m.on_phase(window)

    # --- the message ------------------------------------------------------------------

    def test_a_shout_is_the_character_s_message_and_saved(self):
        self.m.remember_shout("selling swords")
        self.assertEqual(self.m.message(), "selling swords")
        self.assertIn("Hero\tselling swords", self.files.files[self.m.PATH])
        self.name[0] = "Other"
        self.assertEqual(self.m.message(), "", "per character")
        self.m.remember_shout("buying shields")
        fresh = self.modules.load("autoshout")
        fresh.OPENER = self.files.open
        self.assertEqual(fresh.message(), "buying shields")
        self.name[0] = "Hero"
        self.assertEqual(fresh.message(), "selling swords", "both characters' messages read back")

    def test_tabs_and_line_breaks_never_reach_the_file(self):
        self.m.remember_shout("a\tb\nc\r")
        self.assertEqual(self.m.message(), "a b c")

    def test_an_empty_shout_changes_nothing(self):
        self.m.remember_shout("keep")
        self.m.remember_shout("   ")
        self.assertEqual(self.m.message(), "keep")

    # --- start, stop and the server's state -----------------------------------------

    def test_start_sends_on_with_the_text_and_saves_it(self):
        self.assertTrue(self.m.start("  wts sword  "))
        self.assertEqual(self.sent(), ["/auto_shout on wts sword"])
        self.assertTrue(self.m.is_on())
        self.assertFalse(self.m.is_confirmed(), "until the server's state")
        self.assertEqual(self.m.message(), "wts sword")

    def test_start_without_a_message_tells_the_player_and_sends_nothing(self):
        self.assertFalse(self.m.start("   "))
        self.assertEqual(self.sent(), [])
        self.assertFalse(self.m.is_on())
        self.assertIn(("chat.AppendChat", (1, "no message")), self.log)

    def test_stop_sends_off(self):
        self.m.start("x")
        self.m.stop()
        self.assertEqual(self.sent(), ["/auto_shout on x", "/auto_shout off"])
        self.assertFalse(self.m.is_on())

    def test_the_server_s_state_sets_the_countdown(self):
        self.m.start("x")
        self.m.server_state("1", "30")
        self.assertTrue(self.m.is_confirmed())
        self.assertEqual(self.m.interval(), 30)
        self.time[0] += 12.0
        self.assertAlmostEqual(self.m.seconds_left(), 18.0)
        self.m.server_state("1", "16")
        self.assertAlmostEqual(self.m.seconds_left(), 16.0, msg="each state message starts it again")

    def test_without_a_new_state_the_count_goes_on_by_the_interval(self):
        self.m.start("x")
        self.m.server_state("1", "30")
        self.time[0] += 35.0
        self.assertAlmostEqual(self.m.seconds_left(), 25.0)

    def test_the_server_s_off_switches_it_off(self):
        self.m.start("x")
        self.m.server_state("1", "30")
        self.m.server_state("0", "0")
        self.assertFalse(self.m.is_on())
        self.assertFalse(self.m.is_confirmed())
        self.assertEqual(self.m.seconds_left(), 0)

    def test_a_state_out_of_form_is_ignored(self):
        self.m.start("x")
        self.m.server_state("yes", "soon")
        self.assertTrue(self.m.is_on())
        self.assertFalse(self.m.is_confirmed())

    def test_listeners_hear_every_change_and_a_gone_one_is_dropped(self):
        heard = []

        class Window(object):
            def OnAutoShoutChanged(self):
                heard.append(1)
        window = Window()
        self.m.listen(window)
        self.m.start("x")
        self.m.server_state("1", "30")
        self.m.stop()
        self.assertEqual(len(heard), 3)
        del window
        import gc
        gc.collect()
        self.m.start("y")
        self.assertEqual(len(heard), 3)

    # --- the lifetime ------------------------------------------------------------------

    def armed(self):
        self.m.start("wts sword")
        self.m.server_state("1", "30")
        del self.log[:]

    def test_a_warp_sends_on_again_once(self):
        self.armed()
        self.phase("LoadingWindow")
        self.phase("GameWindow")
        self.assertEqual(self.sent(), ["/auto_shout on wts sword"])
        self.assertTrue(self.m.is_on())
        self.assertFalse(self.m.is_confirmed(), "until the new core's state")

    def test_a_channel_change_switches_it_off(self):
        self.armed()
        self.phase("LoadingWindow")
        self.channel[0] = 2
        self.phase("GameWindow")
        self.assertEqual(self.sent(), [])
        self.assertFalse(self.m.is_on())

    def test_the_character_select_and_the_login_switch_it_off(self):
        for phase in ("SelectCharacterWindow", "LoginWindow"):
            self.armed()
            self.phase(phase)
            self.phase("LoadingWindow")
            self.phase("GameWindow")
            with self.subTest(phase=phase):
                self.assertEqual(self.sent(), [])
                self.assertFalse(self.m.is_on())

    def test_another_character_starts_off(self):
        self.armed()
        self.name[0] = "Other"
        self.phase("GameWindow")
        self.assertEqual(self.sent(), [])
        self.assertFalse(self.m.is_on())

    def test_a_new_process_starts_off_with_the_saved_message(self):
        self.armed()
        fresh = self.modules.load("autoshout")
        fresh.OPENER = self.files.open
        fresh.on_phase(type("GameWindow", (object,), {})())
        self.assertFalse(fresh.is_on())
        self.assertEqual(fresh.message(), "wts sword")
        self.assertEqual(self.sent(), [])


# --- the chat's send path --------------------------------------------------------------------------

class ChatRecords(unittest.TestCase):
    def test_a_sent_shout_becomes_the_message_in_both_chats(self):
        for world in chat_test.pair():
            with world, chat_test.quiet():
                world.game.load("autoshout", "autoshout.py")
            autoshout = world.module("autoshout")
            autoshout.OPENER = Files().open
            world.game.answer("player", "GetName", lambda: "Hero")
            world.enter_game()
            with world:
                world.chat.OpenChat()
            world.type("!wts sword")
            world.enter()
            world.game.time += 20.0
            world.type("#party only")
            world.enter()
            with world, self.subTest(nui_on=world.nui_on):
                self.assertEqual(autoshout.message(), "wts sword")

    def test_a_refused_shout_is_not_recorded(self):
        for world in chat_test.pair():
            with world, chat_test.quiet():
                world.game.load("autoshout", "autoshout.py")
            autoshout = world.module("autoshout")
            autoshout.OPENER = Files().open
            world.game.answer("player", "GetName", lambda: "Hero")
            world.enter_game()
            world.game.answer("net", "IsChatInsultIn", lambda text: "bad" in text)
            with world:
                world.chat.OpenChat()
            world.type("!bad words")
            world.enter()
            with world, self.subTest(nui_on=world.nui_on):
                self.assertEqual(autoshout.message(), "")


# --- the window --------------------------------------------------------------------------------------

class Window(unittest.TestCase):
    def world(self, nui_on):
        world = w4.World(nui_on, social=True)
        with world.game, w4.quiet():
            world.game.load("autoshout", "autoshout.py")
            world.game.load("uiAutoShout", "uiautoshout.py")
            world.game.load("nui_auto_shout", "nui_auto_shout.py")
        world.autoshout = world.m("autoshout")
        world.autoshout.OPENER = Files().open
        world.game.answer("player", "GetName", lambda: "Hero")
        world.game.answer("net", "GetChannelNum", lambda: 1)
        with world.game, w4.quiet():
            world.window = world.make("auto-shout", "uiAutoShout", "AutoShoutWindow", "nui_auto_shout.AutoShoutWindow")
        return world

    def worlds(self):
        return [self.world(nui_on) for nui_on in (False, True)]

    def sent(self, world, mark):
        return [args[0] for name, args in world.calls_since(mark, "net.SendChatPacket")]

    def field(self, world):
        if world.nui_on:
            return w4.board(world.window).fields.get(FIELD, "")
        return world.window.messageLine.GetText()

    def type(self, world, text):
        if world.nui_on:
            w4.board(world.window).set_value(FIELD, text)
        else:
            world.window.messageLine.SetText(text)

    def toggle(self, world):
        with world.game, w4.quiet():
            if world.nui_on:
                w4.press(world.window, "toggle_press", 0)
            else:
                world.window.toggleButton.click()

    def state(self, world):
        """(the state, the toggle's label key) the window shows."""
        if world.nui_on:
            model = w4.board(world.window).model
            return model["state"]
        return world.window.shownState

    def test_the_novaui_window_is_the_facade(self):
        world = self.world(True)
        self.assertEqual(type(world.window).__module__, "nui_auto_shout")
        self.assertIsNone(type(world.window).OnUpdate)

    def test_open_prefills_the_last_shout(self):
        for world in self.worlds():
            with world.game, w4.quiet():
                world.autoshout.remember_shout("wts sword")
                world.window.Open()
            with self.subTest(nui_on=world.nui_on):
                self.assertTrue(world.window.IsShow())
                self.assertEqual(self.field(world), "wts sword")
                self.assertEqual(self.state(world), "off")

    def test_start_and_stop_send_and_show_the_state(self):
        for world in self.worlds():
            with world.game, w4.quiet():
                world.window.Open()
            self.type(world, "buying shields")
            mark = world.mark()
            self.toggle(world)
            waiting = self.state(world)
            with world.game, w4.quiet():
                world.autoshout.server_state("1", "30")
            on = self.state(world)
            self.toggle(world)
            with self.subTest(nui_on=world.nui_on):
                self.assertEqual(self.sent(world, mark), ["/auto_shout on buying shields", "/auto_shout off"])
                self.assertEqual((waiting, on, self.state(world)), ("waiting", "on", "off"))

    def test_the_countdown_comes_from_the_state_message(self):
        world = self.world(True)
        nui = world.m("nui")
        with world.game, w4.quiet():
            world.window.Open()
            world.autoshout.start("x")
            world.autoshout.server_state("1", "16")
        model = w4.board(world.window).model
        self.assertAlmostEqual(model["next_end"], nui.now() + 16.0, places=3)
        legacy = self.world(False)
        with legacy.game, w4.quiet():
            legacy.window.Open()
            legacy.autoshout.start("x")
            legacy.autoshout.server_state("1", "16")
            legacy.game.time += 4.0
            legacy.window.OnUpdate()
        self.assertIn("0:12", legacy.window.nextText.GetText())

    def test_the_countdown_end_counts_on_by_the_interval(self):
        world = self.world(True)
        nui = world.m("nui")
        with world.game, w4.quiet():
            world.window.Open()
            world.autoshout.start("x")
            world.autoshout.server_state("1", "30")
            first = w4.board(world.window).model["next_end"]
            world.game.time += 30.0
            w4.fire(world.window, "countdown_end")
        self.assertGreater(w4.board(world.window).model["next_end"], first)

    def test_enter_starts_and_escape_closes(self):
        world = self.world(True)
        nui = world.m("nui")
        with world.game, w4.quiet():
            world.window.Open()
        self.type(world, "hello")
        mark = world.mark()
        with world.game, w4.quiet():
            w4.board(world.window).key(FIELD, nui.KEY_RETURN)
        self.assertEqual(self.sent(world, mark), ["/auto_shout on hello"])
        with world.game, w4.quiet():
            w4.board(world.window).key(FIELD, nui.KEY_ESCAPE)
        self.assertFalse(world.window.IsShow())

    def test_legacy_escape_closes(self):
        world = self.world(False)
        with world.game, w4.quiet():
            world.window.Open()
            self.assertTrue(world.window.OnPressEscapeKey())
        self.assertFalse(world.window.IsShow())

    def test_every_fixture_has_the_model_s_keys(self):
        world = self.world(True)
        model = world.window.nui_model()
        folder = os.path.join(NUI, "windows", "auto-shout")
        for name in sorted(os.listdir(folder)):
            if name.endswith(".fixture.json"):
                variant = name[len("auto-shout."):-len(".fixture.json")].strip(".")
                with self.subTest(fixture=name):
                    self.assertEqual(sorted(w4.fixture_keys(None, "auto-shout", variant)), sorted(model))


# --- the chat button -----------------------------------------------------------------------------

class ChatButton(unittest.TestCase):
    def test_the_button_opens_the_window_in_both_chats(self):
        for world in chat_test.pair():
            opened = []
            world.enter_game()
            with world:
                world.chat.SetAutoShoutEvent(lambda: opened.append(1))
                world.chat.OpenChat()
                if world.nui_on:
                    world.board().fire("auto_shout", 0)
                else:
                    world.chat.btnAutoShout.click()
            with self.subTest(nui_on=world.nui_on):
                self.assertEqual(opened, [1])

    def test_the_legacy_button_shows_with_the_open_chat_left_of_the_whisper_button(self):
        legacy, _ = chat_test.pair()
        legacy.enter_game()
        with legacy:
            legacy.chat.OpenChat()
        self.assertTrue(legacy.chat.btnAutoShout.IsShow())
        self.assertEqual(social_test.position(legacy.chat.btnAutoShout), (600 - 100, 2))
        with legacy:
            legacy.chat.CloseChat()
        self.assertFalse(legacy.chat.btnAutoShout.IsShow())

    def test_the_document_has_the_button(self):
        text = read(os.path.join(NUI, "windows", "chat", "chat.rml"))
        self.assertIn('id="chat-auto-shout"', text)
        self.assertIn("auto_shout(ev.button)", text)
        self.assertIn("@game.AUTO_SHOUT_TOOLTIP", text)


# --- the wiring --------------------------------------------------------------------------------

class Wiring(unittest.TestCase):
    def test_the_window_id_is_on_by_default_in_the_social_group_on_demand(self):
        text = read(os.path.join(ROOT, "nui_windows.py"))
        self.assertIn('("auto-shout", True)', text)
        self.assertIn('("auto-shout", ("auto-shout",))', text)

    def test_the_interface_makes_it_and_runs_the_server_s_state(self):
        text = read(os.path.join(ROOT, "interfacemodule.py"))
        self.assertIn('nui_windows.make("auto-shout", uiAutoShout.AutoShoutWindow, "nui_auto_shout.AutoShoutWindow")', text)
        self.assertIn("def AutoShoutState(self, on, seconds):", text)
        self.assertIn("SetAutoShoutEvent(ui.__mem_func__(self.ToggleAutoShoutWindow))", text)

    def test_every_phase_change_reaches_the_switch(self):
        text = support.source_of("networkmodule.py", ["_MainStream__ChangePhaseWindow"], inside="MainStream") \
            if hasattr(support, "source_of") else ""
        whole = read(os.path.join(ROOT, "networkmodule.py"))
        self.assertIn("autoshout.on_phase(newPhaseWindow)", whole)


if __name__ == "__main__":
    unittest.main()
