"""Tests for the whisper dialog's add-friend button (NOVA-203; OLD
uiWhisper.py:106, 126, 329-341): python3 -B -m unittest whisper_friend_test
(from tools/).

The legacy uiWhisper.WhisperDialog (made from its real uiscript by
nui_game_support's stand-ins) and NovaUI's (nui_whisper.WhisperDialog), each
in a world of its own (nui_w4_world.World with the social windows), driven as
the Interface drives them (nui_whisper_test.Interface):
- a partner who is not a friend gets the button; a friend, a GM (the GM look)
  and the dialog without a partner do not;
- a press sends NEW's friend request (net.SendMessengerAddByNamePacket) and
  hides the button at once, as OLD;
- RefreshFriendButton follows the messenger's friend list, so a friend the
  list gains or loses changes the button of an open dialog;
- uiwhisper.MessengerRelay, the messenger handler the Interface sets: every
  call reaches the messenger window as before, and a change of the friend
  group refreshes the open dialogs;
- the uiscript's button: OLD's art at legacy's place, left of NEW's block
  button; the NovaUI document's button and its classic art."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import nui_whisper_test as whisper_test  # noqa: E402
import social_test  # noqa: E402

NUI = os.path.join(support.ROOT, "..", "nui", "nui")
ADD_FRIEND_ART = "d:/ymir work/ui/game/windows/messenger_add_friend_0%d.sub"


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class FriendTest(unittest.TestCase):
    def open(self, nui_on, name="Pest", friends=(), gm=False):
        world = w4.World(nui_on, social=True)
        world.interface = whisper_test.Interface(world)
        world.friends = set(friends)
        world.game.answer("messenger", "IsFriendByName", lambda target: target in world.friends)
        with world.game, w4.quiet():
            dialog = world.interface.OpenWhisperDialog(name)
            if gm:
                dialog.SetGameMasterLook()
        return world, dialog

    def shown(self, world, dialog):
        """The button's state: the board's model under NovaUI, the legacy
        button's otherwise."""
        if world.nui_on:
            return bool(w4.board(dialog).model["friend_shown"])
        return bool(dialog.friendButton.IsShow())

    def press(self, world, dialog):
        with world.game, w4.quiet():
            if world.nui_on:
                w4.press(dialog, "friend_press", 0)
            else:
                dialog.friendButton.event(*dialog.friendButton.eventArgs)

    def net_calls(self, world, mark):
        return [e for e in world.effects_since(mark) if e[0].startswith("net.")]


class Shown(FriendTest):
    def test_a_stranger_gets_the_button_and_a_friend_does_not(self):
        for nui_on in (False, True):
            for friends, expected in (((), True), (("Pest",), False)):
                world, dialog = self.open(nui_on, friends=friends)
                with self.subTest(nui_on=nui_on, friends=friends):
                    self.assertEqual(self.shown(world, dialog), expected)

    def test_a_game_master_gets_no_button(self):
        for nui_on in (False, True):
            world, dialog = self.open(nui_on, gm=True)
            with self.subTest(nui_on=nui_on):
                self.assertFalse(self.shown(world, dialog))

    def test_the_dialog_without_a_partner_has_no_button_and_sends_nothing(self):
        for nui_on in (False, True):
            world = w4.World(nui_on, social=True)
            world.interface = whisper_test.Interface(world)
            with world.game, w4.quiet():
                dialog = world.interface.OpenWhisperDialogWithoutTarget()
            mark = world.mark()
            with world.game, w4.quiet():
                dialog.AddFriend()
                dialog.RefreshFriendButton()
            with self.subTest(nui_on=nui_on):
                self.assertFalse(self.shown(world, dialog))
                self.assertEqual(self.net_calls(world, mark), [])

    def test_a_typed_partner_gets_the_button(self):
        for nui_on in (False, True):
            world = w4.World(nui_on, social=True)
            world.interface = whisper_test.Interface(world)
            world.game.answer("messenger", "IsFriendByName", lambda target: False)
            with world.game, w4.quiet():
                dialog = world.interface.OpenWhisperDialogWithoutTarget()
                world.interface.RegisterTemporaryWhisperDialog("Typed")
            with self.subTest(nui_on=nui_on):
                self.assertTrue(self.shown(world, dialog))


class Press(FriendTest):
    def test_a_press_sends_the_friend_request_and_hides_the_button(self):
        for nui_on in (False, True):
            world, dialog = self.open(nui_on)
            mark = world.mark()
            self.press(world, dialog)
            with self.subTest(nui_on=nui_on):
                self.assertEqual(self.net_calls(world, mark), [("net.SendMessengerAddByNamePacket", ("Pest",))])
                self.assertFalse(self.shown(world, dialog))


class Refresh(FriendTest):
    def test_the_button_follows_the_friend_list(self):
        for nui_on in (False, True):
            world, dialog = self.open(nui_on)
            world.friends.add("Pest")
            with world.game, w4.quiet():
                dialog.RefreshFriendButton()
            after_add = self.shown(world, dialog)
            world.friends.discard("Pest")
            with world.game, w4.quiet():
                dialog.RefreshFriendButton()
            with self.subTest(nui_on=nui_on):
                self.assertFalse(after_add)
                self.assertTrue(self.shown(world, dialog))

    def test_a_game_master_stays_without_the_button_at_a_refresh(self):
        for nui_on in (False, True):
            world, dialog = self.open(nui_on, gm=True)
            with world.game, w4.quiet():
                dialog.RefreshFriendButton()
            with self.subTest(nui_on=nui_on):
                self.assertFalse(self.shown(world, dialog))


class Relay(unittest.TestCase):
    """uiwhisper.MessengerRelay: the messenger handler the Interface sets
    over the messenger window (CPythonMessenger calls its handler by name)."""

    class Window(object):
        def __init__(self):
            self.calls = []

        def OnLogin(self, group, key, name=None):
            self.calls.append(("OnLogin", group, key))

        def OnLogout(self, group, key, name=None):
            self.calls.append(("OnLogout", group, key))

        def OnRemoveList(self, group, key):
            self.calls.append(("OnRemoveList", group, key))

        def OnRemoveAllList(self, group):
            self.calls.append(("OnRemoveAllList", group))

        def SetLanguagesFlags(self, group, key, languages):
            self.calls.append(("SetLanguagesFlags", group, key))

    def setUp(self):
        world = w4.World(False, social=True)
        self.module = world.m("uiWhisper")
        self.window = self.Window()
        self.refreshed = []
        self.relay = self.module.MessengerRelay(self.window, lambda: self.refreshed.append(1))

    def test_every_call_reaches_the_window(self):
        self.relay.OnLogin(1, "Guildy")
        self.relay.SetLanguagesFlags(0, "Pal", "de")
        self.assertEqual(self.window.calls, [("OnLogin", 1, "Guildy"), ("SetLanguagesFlags", 0, "Pal")])

    def test_a_friend_group_change_refreshes_the_dialogs(self):
        friend = self.module.MESSENGER_GROUP_FRIEND
        self.relay.OnLogin(friend, "Pal")
        self.relay.OnLogout(friend, "Pal")
        self.relay.OnRemoveList(friend, "Pal")
        self.relay.OnRemoveAllList(friend)
        self.assertEqual(len(self.refreshed), 4)
        self.assertEqual(len(self.window.calls), 4, "the window got each first")

    def test_another_group_refreshes_nothing(self):
        self.relay.OnLogin(1, "Guildy")
        self.relay.OnRemoveList(4, "Pest")
        self.assertEqual(self.refreshed, [])

    def test_a_gone_window_takes_no_call(self):
        del self.window
        import gc
        gc.collect()
        self.relay.OnLogin(self.module.MESSENGER_GROUP_FRIEND, "Pal")
        self.assertFalse(hasattr(self.relay, "Nothing"))
        self.assertEqual(self.refreshed, [1], "the dialogs still hear of the change")


class Interface(unittest.TestCase):
    """interfacemodule.py: the relay set after the messenger window is made,
    and every open dialog refreshed."""

    def source(self):
        return read(os.path.join(support.ROOT, "interfacemodule.py"))

    def test_the_interface_sets_the_relay_and_refreshes_the_dialogs(self):
        text = self.source()
        self.assertIn("uiWhisper.MessengerRelay(self.wndMessenger", text)
        self.assertIn("def RefreshWhisperFriendButtons(self):", text)
        refresh = support.source_of("interfacemodule.py", ["RefreshWhisperFriendButtons"], inside="Interface")
        self.assertIn("\"RefreshFriendButton\"", refresh)

    def test_the_refresh_reaches_every_open_dialog(self):
        cls = social_test.compiled("interfacemodule.py", "Interface", ["RefreshWhisperFriendButtons"])

        class Dialog(object):
            def __init__(self):
                self.refreshed = 0

            def RefreshFriendButton(self):
                self.refreshed += 1

        interface = cls()
        interface.whisperDialogDict = {"A": Dialog(), "B": Dialog()}
        interface.RefreshWhisperFriendButtons()
        self.assertEqual([d.refreshed for d in interface.whisperDialogDict.values()], [1, 1])
        interface.whisperDialogDict = None
        interface.RefreshWhisperFriendButtons()


class Uiscript(unittest.TestCase):
    def test_the_uiscript_has_olds_button_left_of_the_block_button(self):
        kids = social_test.children(social_test.uiscript("whisperdialog.py"), "board")
        button = kids["friendbutton"]
        self.assertEqual(button["type"], "button")
        self.assertEqual(button["tooltip_text"], "MESSENGER_ADD_FRIEND")
        self.assertEqual([button[k] for k in ("default_image", "over_image", "down_image")],
                         [ADD_FRIEND_ART % n for n in (1, 2, 3)])
        self.assertEqual((button["x"], button["y"]), (280 - 108, 10))

    def test_the_button_keeps_its_place_at_any_size(self):
        world = w4.World(False, social=True)
        world.interface = whisper_test.Interface(world)
        with world.game, w4.quiet():
            dialog = world.interface.OpenWhisperDialog("Pest")
            for width in (280, 400):
                dialog.SetWhisperDialogSize(width, 200)
                self.assertEqual(social_test.position(dialog.friendButton), (width - 108, 10))
                self.assertLessEqual(width - 108 + 21, width - 86, "clear of the block button")


class Document(unittest.TestCase):
    def test_the_document_has_the_button_with_its_tooltip(self):
        text = read(os.path.join(NUI, "windows", "whisper", "whisper.rml"))
        self.assertIn('id="whisper-friend"', text)
        self.assertIn('data-if="friend_shown"', text)
        self.assertIn('friend_press(ev.button)', text)
        self.assertIn("@ui.MESSENGER_ADD_FRIEND", text)

    def test_classic_draws_olds_art(self):
        text = read(os.path.join(NUI, "skins", "classic", "windows", "whisper.rcss"))
        for n in (1, 2, 3):
            self.assertIn(ADD_FRIEND_ART % n, text)

    def test_every_fixture_has_the_key(self):
        folder = os.path.join(NUI, "windows", "whisper")
        for name in os.listdir(folder):
            if name.endswith(".fixture.json"):
                with self.subTest(fixture=name):
                    self.assertIn('"friend_shown"', read(os.path.join(folder, name)))


if __name__ == "__main__":
    unittest.main()
