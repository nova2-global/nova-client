"""Tests for the social client's legacy windows (foundation wave, chunk C3):
python3 -B -m unittest social_test (from tools/).

The C++ half (the packets, CPythonMessenger, the net/messenger/chat names) is
tested in nova-client-src's userinterface_tests. Here the legacy windows are
made from their real uiscripts by nui_game_support's stand-ins (nui_w4_world's
World with the social windows), once with every NovaUI flag off (the legacy
windows) and once with the social flags on (NovaUI's facades over the same
legacy classes), and driven as the C++ handlers drive them:
- the messenger's staff rosters (NOVA-30, NOVA-46): the Helper and Team
  groups at the C++ indices 2 and 3, their rows, the language flags, a list
  that empties a group, and the indices a NovaUI window has no group for;
- the block list (NOVA-47): the messenger's Blocked Players group, its block
  and unblock buttons and dialogs, the whisper dialog's block button, the
  target board's Block/Unblock, and game.py's answer to whisper type 7;
- whisper details (NOVA-48): the whisper dialog's online icon and flag,
  AcceptTarget's request, game.py's poll (every two seconds per open dialog
  with a target) and its BINARY_WhisperDetails;
- the guild war's member cap and end score (NOVA-90): the declare dialog's
  two inputs and the commands it sends (4 and 2 arguments), the accept
  dialog's two lines, game.py's 4-argument callback;
- every new locale key in all 17 locales, OLD's text where OLD's locale has
  it and English otherwise."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_hud_test as hud  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import nui_whisper_test as whisper_test  # noqa: E402
import nui_guild_dialogs_test as guild_test  # noqa: E402

ROOT = support.ROOT
ASSETS = os.path.normpath(os.path.join(ROOT, ".."))
LOCALES = os.path.join(ASSETS, "locale", "locale")
OLD_LOCALES = os.path.normpath(os.path.join(ROOT, "..", "..", "..", "..", "..", "old", "client_pack", "source",
                                            "locale"))
FLAGS = os.path.join(LOCALES, "common", "ui", "flag", "32")
FRIEND, GUILD, HELPER, TEAMLER, BLOCK = 0, 1, 2, 3, 4
UISCRIPTS = os.path.join(ASSETS, "uiscript", "uiscript")

# The keys each feature adds, with the English text (OLD's where OLD has the
# key): {file: {key: English}}.
ROSTER_KEYS = {"game": {"MESSENGER_HELPER": "Helper", "MESSENGER_TEAMLER": "Team"}}
BLOCK_KEYS = {"game": {"TARGET_BUTTON_BLOCK": "Block", "TARGET_BUTTON_UNBLOCK": "Unblock",
                       "BLOCK_PLAYER_TITLE": "Block Player", "UNBLOCK_PLAYER_DIALOG": "Do you want to unblock %s?",
                       "BLOCKED_PLAYERS_TITLE": "Blocked Players",
                       "WHISPER_ERROR_BLOCK_YOU": "You can't write to %s because they blocked you."},
              "interface": {"BLOCK_PLAYER": "Block Player", "UNBLOCK_PLAYER": "Unblock Player"}}
WAR_KEYS = {"game": {"GUILD_WAR_MAX_MEMBERS": "Players Limit from your guild: %d.",
                     "GUILD_WAR_MAX_SCORE": "The war will end at %d Kills."},
            "interface": {"GUILD_WAR_ENEMY_NUMBER": "Max. Members", "GUILD_WAR_MAX_SCORE": "End Score"}}
# OLD texts not taken, English instead: ro's GUILD_WAR_MAX_SCORE "Scorul
# final" has no %d, and OLD's accept dialog formatted a score into it (a
# TypeError).
NOT_OLD = {("ro", "game", "GUILD_WAR_MAX_SCORE")}


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def last_call(widget, *names):
    """The last of a stand-in widget's recorded calls named one of `names`."""
    for call in reversed(widget.calls):
        if call[0] in names:
            return call
    return None


def enabled(button):
    """A legacy button's state: its last Enable or Disable (enabled when it
    had neither, as a fresh button is)."""
    call = last_call(button, "Enable", "Disable")
    return call is None or call[0] == "Enable"


def position(widget):
    call = last_call(widget, "SetPosition")
    return call[1:] if call else (0, 0)


def compiled(file_name, class_name, names, namespace=None):
    """A class with the methods `names` of a root module's class, compiled
    from its own source (the legacy code, unchanged) over `namespace`
    (pickup_filter_test's helper)."""
    source = support.source_of(file_name, names, inside=class_name)
    body = "\n".join("\t" + line if line else line for line in source.split("\n"))
    namespace = dict(namespace or {})
    exec(compile("class %s(object):\n%s\n" % (class_name, body), file_name, "exec"), namespace)
    return namespace[class_name]


def uiscript(name):
    """A uiscript's window dictionary, its strings their keys. The declare
    dialog's uiscript imports guild for the enemy name's length (the client's
    guild.GUILD_NAME_MAX_LEN, 24 since the foundation cut)."""
    names = {"SCREEN_WIDTH": 1600, "SCREEN_HEIGHT": 900, "PLAYER_NAME_MAX_LEN": 12, "LOCALE_PATH": "locale/en",
             "LOCALE_PATH_COMMON": "locale/common"}
    from unittest import mock
    with mock.patch.dict(sys.modules, {"uiScriptLocale": support.support.LocaleInfo(),
                                       "localeInfo": support.support.LocaleInfo(),
                                       "guild": types.SimpleNamespace(GUILD_NAME_MAX_LEN=24)}):
        path = os.path.join(UISCRIPTS, name)
        exec(compile(read(path), path, "exec"), names)
    return names["window"]


def children(window, *path):
    """{name: child} of the window's children (or a child's, by names)."""
    node = window
    for name in path:
        node = dict((child["name"], child) for child in node["children"])[name]
    return dict((child["name"], child) for child in node.get("children", ()))


def locale_entries(path):
    """{key: text} of a locale file, the last line of a key winning, as the
    client's loader reads it."""
    entries = {}
    for line in read(path).split("\n"):
        if "\t" in line:
            tokens = line.split("\t")
            entries[tokens[0]] = tokens[1].rstrip()
    return entries


class MessengerWorld(unittest.TestCase):
    def world(self, nui_on):
        world = w4.World(nui_on, social=True)
        window = world.make("messenger", "uiMessenger", "MessengerWindow", "nui_messenger.MessengerWindow")
        with world.game, w4.quiet():
            window.SetWhisperButtonEvent(lambda name: None)
            window.SetGuildButtonEvent(lambda: None)
            window.InitializeHandler()
        return world, window

    def call(self, world, window, name, *args):
        with world.game, w4.quiet():
            return getattr(window, name)(*args)

    @staticmethod
    def names(group):
        return [member.GetName() for member in group.memberList]


class Rosters(MessengerWorld):
    def test_the_legacy_window_has_olds_groups_in_olds_order(self):
        world, window = self.world(False)
        locale = world.m("localeInfo")
        messenger = world.m("uiMessenger")
        self.assertEqual((messenger.FRIEND, messenger.GUILD, messenger.HELPER, messenger.TEAMLER), (0, 1, 2, 3))
        self.assertEqual([group.GetName() for group in window.groupList[:4]],
                         [locale.MESSENGER_FRIEND, locale.MESSENGER_GUILD, "Helper", "Team"])
        self.assertIsInstance(window.groupList[HELPER], messenger.MessengerHelperGroup)
        self.assertIsInstance(window.groupList[TEAMLER], messenger.MessengerTeamlerGroup)

    def test_a_staff_member_logs_in_and_out_and_can_never_be_removed(self):
        world, window = self.world(False)
        messenger = world.m("uiMessenger")
        self.call(world, window, "OnLogin", HELPER, "[SM]Lucius")
        self.call(world, window, "OnLogout", TEAMLER, "[GM]Nova")

        helper = window.groupList[HELPER].FindMember("[SM]Lucius")
        teamler = window.groupList[TEAMLER].FindMember("[GM]Nova")
        self.assertIsInstance(helper, messenger.MessengerHelperItem)
        self.assertIsInstance(teamler, messenger.MessengerTeamlerItem)
        self.assertTrue(helper.IsOnline())
        self.assertFalse(teamler.IsOnline())
        self.assertFalse(helper.CanRemove())
        self.assertFalse(teamler.CanRemove())
        self.assertTrue(helper.CanWhisper(), "an online staff member can be whispered")

        # A logout keeps the name, offline, as the friends' does.
        self.call(world, window, "OnLogout", HELPER, "[SM]Lucius")
        self.assertIs(window.groupList[HELPER].FindMember("[SM]Lucius"), helper)
        self.assertFalse(helper.IsOnline())

        self.call(world, window, "OnSelectItem", helper)
        self.assertFalse(enabled(window.removeButton))

    def test_the_rows_show_each_language_flag_after_the_name(self):
        world, window = self.world(False)
        self.call(world, window, "OnLogin", HELPER, "[SM]Lucius")
        self.call(world, window, "SetLanguagesFlags", HELPER, "[SM]Lucius", "en pt xx")

        member = window.groupList[HELPER].FindMember("[SM]Lucius")
        self.assertEqual(member.GetLanguages(), "en pt xx")
        self.assertEqual([flag.image for flag in member.flagImageList],
                         ["locale/common/ui/flag/32/en.tga", "locale/common/ui/flag/32/pt.tga"],
                         "a code with no flag file shows none")
        start = 20 + 6 * len("[SM]Lucius") + 4
        self.assertEqual([position(flag) for flag in member.flagImageList], [(start, 0), (start + 18, 0)])

        # A later login keeps the flags after the name; new languages replace them.
        self.call(world, window, "OnLogin", HELPER, "[SM]Lucius")
        self.assertEqual(len(member.flagImageList), 2)
        old_flags = list(member.flagImageList)
        self.call(world, window, "SetLanguagesFlags", HELPER, "[SM]Lucius", "")
        self.assertEqual(member.flagImageList, [])
        self.assertTrue(all(not flag.IsShow() for flag in old_flags))

    def test_languages_for_a_name_the_group_lacks_change_nothing(self):
        world, window = self.world(False)
        self.call(world, window, "SetLanguagesFlags", TEAMLER, "Nobody", "en")
        self.assertEqual(window.groupList[TEAMLER].memberList, [])

    def test_a_list_empties_its_group_first_and_takes_a_selected_row_with_it(self):
        world, window = self.world(False)
        self.call(world, window, "OnLogin", HELPER, "Old")
        self.call(world, window, "OnLogin", FRIEND, "Alice")
        old = window.groupList[HELPER].FindMember("Old")
        self.call(world, window, "OnSelectItem", old)

        self.call(world, window, "OnRemoveAllList", HELPER)

        self.assertEqual(window.groupList[HELPER].memberList, [])
        self.assertIsNone(window.selectedItem)
        self.assertFalse(old.IsShow(), "the removed row leaves the screen")
        self.assertEqual(self.names(window.groupList[FRIEND]), ["Alice"], "other groups are untouched")

    def test_the_helper_and_team_rows_follow_the_guild_rows(self):
        world, window = self.world(False)
        self.call(world, window, "OnLogin", HELPER, "[SM]Lucius")
        self.call(world, window, "OnLogin", TEAMLER, "[GM]Nova")
        names = [item.GetName() for item in window.showingItemList]
        self.assertLess(names.index("Helper"), names.index("[SM]Lucius"))
        self.assertLess(names.index("[SM]Lucius"), names.index("Team"))
        self.assertLess(names.index("Team"), names.index("[GM]Nova"))

    def test_under_novaui_the_roster_calls_find_no_group_and_change_nothing(self):
        world, window = self.world(True)
        self.assertEqual(len(window.groupList), 2, "NovaUI's window holds Friend and Guild")
        for name, args in (("OnLogin", (HELPER, "[SM]Lucius")), ("OnLogout", (TEAMLER, "[GM]Nova")),
                           ("SetLanguagesFlags", (HELPER, "[SM]Lucius", "en")), ("OnRemoveAllList", (TEAMLER,)),
                           ("OnRemoveList", (HELPER, "[SM]Lucius")), ("OnLogin", (4, "Pest"))):
            with self.subTest(call=name, args=args):
                self.call(world, window, name, *args)
        self.assertEqual([len(group.memberList) for group in window.groupList], [0, 0])


class BlockedGroup(MessengerWorld):
    def blocked(self, world, names):
        world.game.answer("messenger", "GetBlockedList", lambda: tuple(names))
        world.game.answer("messenger", "IsBlocked", lambda name: name in names)

    def test_the_blocked_group_comes_last_with_olds_title(self):
        world, window = self.world(False)
        messenger = world.m("uiMessenger")
        self.assertEqual(messenger.BLOCK, 4)
        self.assertEqual(len(window.groupList), 5)
        self.assertIsInstance(window.groupList[BLOCK], messenger.MessengerBlockedGroup)
        self.assertEqual(window.groupList[BLOCK].GetName(), "Blocked Players")

    def test_the_list_fills_the_group_at_every_refresh_and_show(self):
        world, window = self.world(False)
        names = ["Pest", "Troll"]
        self.blocked(world, names)
        self.call(world, window, "OnBlockListRefresh")
        group = window.groupList[BLOCK]
        self.assertEqual(self.names(group), ["Pest", "Troll"])
        self.assertTrue(all(not member.IsOnline() for member in group.memberList))
        self.assertTrue(all(member.CanUnblock() and not member.CanRemove() for member in group.memberList))

        names[:] = ["Troll", "Spam"]
        self.call(world, window, "Show")
        self.assertEqual(sorted(self.names(group)), ["Spam", "Troll"], "Show syncs the group with the list")

        names[:] = []
        self.call(world, window, "OnBlockListRefresh")
        self.assertEqual(group.memberList, [], "count 0 empties it")

    def test_a_block_result_adds_or_removes_one_row(self):
        world, window = self.world(False)
        self.call(world, window, "OnBlockedAct", 1, "Pest")
        self.call(world, window, "OnBlockedAct", 1, "Troll")
        self.assertEqual(self.names(window.groupList[BLOCK]), ["Pest", "Troll"])
        self.call(world, window, "OnBlockedAct", 0, "Pest")
        self.assertEqual(self.names(window.groupList[BLOCK]), ["Troll"])
        self.call(world, window, "OnBlockedAct", 0, "Nobody")
        self.assertEqual(self.names(window.groupList[BLOCK]), ["Troll"])

    def test_the_unblock_button_follows_the_selected_row(self):
        world, window = self.world(False)
        self.call(world, window, "OnBlockedAct", 1, "Pest")
        self.call(world, window, "OnLogin", FRIEND, "Alice")
        self.assertFalse(enabled(window.unblockPlayerButton), "disabled until a blocked row is selected")

        self.call(world, window, "OnSelectItem", window.groupList[BLOCK].FindMember("Pest"))
        self.assertTrue(enabled(window.unblockPlayerButton))
        self.assertFalse(enabled(window.removeButton))
        self.assertFalse(enabled(window.whisperButton))

        self.call(world, window, "OnSelectItem", window.groupList[FRIEND].FindMember("Alice"))
        self.assertFalse(enabled(window.unblockPlayerButton))

        self.call(world, window, "OnSelectItem", window.groupList[BLOCK].FindMember("Pest"))
        self.call(world, window, "OnBlockedAct", 0, "Pest")
        self.assertIsNone(window.selectedItem)
        self.assertFalse(enabled(window.unblockPlayerButton), "the unblocked row took the button with it")

    def test_unblock_asks_with_the_name_and_sends_the_remove(self):
        world, window = self.world(False)
        self.call(world, window, "OnBlockedAct", 1, "Pest")
        self.call(world, window, "OnSelectItem", window.groupList[BLOCK].FindMember("Pest"))
        mark = world.mark()
        with world.game, w4.quiet():
            window.unblockPlayerButton.event(*window.unblockPlayerButton.eventArgs)
        dialog = window.unblockPlayerDialog
        self.assertEqual(dialog._name, "uiCommon.QuestionDialog")
        self.assertEqual(dialog.texts, ["Do you want to unblock Pest?"])
        with world.game, w4.quiet():
            dialog.accept()
        self.assertIn(("net.SendBlockRemovePacket", ("Pest",)), world.effects_since(mark))
        self.assertIsNone(window.unblockPlayerDialog)

    def test_block_asks_for_a_name_and_sends_the_add(self):
        world, window = self.world(False)
        for typed, sent in (("Pest", [("net.SendBlockAddPacket", ("Pest",))]), ("", [])):
            mark = world.mark()
            with world.game, w4.quiet():
                window.blockPlayerButton.event(*window.blockPlayerButton.eventArgs)
            board = window.blockPlayerBoard
            self.assertEqual(board._name, "uiCommon.InputDialog")
            self.assertEqual(board.title, "Block Player")
            board.text = typed
            with world.game, w4.quiet():
                board.accept()
            with self.subTest(typed=typed):
                self.assertEqual([e for e in world.effects_since(mark) if e[0].startswith("net.")], sent)
                self.assertIsNone(window.blockPlayerBoard)

    def test_block_and_unblock_without_their_dialog_or_a_blocked_row_do_nothing(self):
        world, window = self.world(False)
        self.call(world, window, "OnLogin", FRIEND, "Alice")
        mark = world.mark()
        self.assertTrue(self.call(world, window, "OnBlockPlayer"), "an accept after the board closed")
        self.call(world, window, "OnPressUnblockButton")
        self.assertIsNone(window.unblockPlayerDialog, "nothing selected")
        self.call(world, window, "OnSelectItem", window.groupList[FRIEND].FindMember("Alice"))
        self.call(world, window, "OnPressUnblockButton")
        self.assertIsNone(window.unblockPlayerDialog, "a friend's row cannot be unblocked")
        self.assertEqual([e for e in world.effects_since(mark) if e[0].startswith("net.")], [])

    def test_destroy_forgets_the_block_buttons_and_dialogs(self):
        world, window = self.world(False)
        with world.game, w4.quiet():
            window.blockPlayerButton.event(*window.blockPlayerButton.eventArgs)
        self.assertIsNotNone(window.blockPlayerBoard)
        self.call(world, window, "Destroy")
        for name in ("blockPlayerButton", "unblockPlayerButton", "blockPlayerBoard", "unblockPlayerDialog"):
            with self.subTest(attribute=name):
                self.assertIsNone(getattr(window, name))

    def test_the_member_list_ends_above_the_button_row(self):
        world, window = self.world(False)
        x, y = window.resizeButton.GetLocalPosition()
        self.call(world, window, "OnResizeDialog")
        y = window.resizeButton.GetLocalPosition()[1]
        self.assertEqual(window.showingPageSize, y - (window.START_POSITION + 26) - window.BLOCK_BUTTON_ROW_HEIGHT)

    def test_the_uiscript_puts_both_buttons_in_a_row_of_their_own(self):
        window = uiscript("messengerwindow.py")
        kids = children(window)
        block, unblock = kids["BlockPlayerButton"], kids["UnblockPlayerButton"]
        for button, key in ((block, "BLOCK_PLAYER"), (unblock, "UNBLOCK_PLAYER")):
            self.assertEqual(button["text"], key)
            self.assertEqual(button["default_image"], "d:/ymir work/ui/public/small_button_01.sub")
            self.assertEqual((button["horizontal_align"], button["vertical_align"]), ("center", "bottom"))
        # 43 px wide each, centered: apart, inside the 170 px window, above the
        # 18 px tall icons at y 30 from the bottom.
        self.assertGreaterEqual(unblock["x"] - block["x"], 43)
        self.assertLessEqual(abs(block["x"]) + 43 // 2 + 1, window["width"] // 2)
        icons = [kids[name] for name in ("AddFriendButton", "WhisperButton", "RemoveButton", "GuildButton")]
        self.assertTrue(all(block["y"] - 21 >= icon["y"] for icon in icons))
        self.assertEqual(block["y"] - icons[0]["y"], 25)

    def test_under_novaui_the_block_calls_find_no_group_or_button(self):
        world, window = self.world(True)
        self.blocked(world, ["Pest"])
        for name, args in (("OnBlockListRefresh", ()), ("OnBlockedAct", (1, "Pest")), ("OnBlockedAct", (0, "Pest")),
                           ("Show", ()), ("OnSelectItem", (None,)), ("OnResizeDialog", ())):
            with self.subTest(call=name):
                self.call(world, window, name, *args)
        self.assertIsNone(window.blockPlayerButton)
        self.assertIsNone(window.unblockPlayerButton)
        self.assertEqual(len(window.groupList), 2)


class WhisperBlock(unittest.TestCase):
    def open(self, nui_on, name="Pest", blocked=()):
        world = w4.World(nui_on, social=True)
        world.interface = whisper_test.Interface(world)
        blocked = set(blocked)
        world.game.answer("messenger", "IsBlocked", lambda target: target in blocked)
        world.blocked = blocked
        with world.game, w4.quiet():
            dialog = world.interface.OpenWhisperDialog(name)
        return world, dialog

    def test_a_dialog_with_a_target_shows_block_or_unblock_as_the_list_says(self):
        for blocked, text in (((), "BLOCK_PLAYER"), (("Pest",), "UNBLOCK_PLAYER")):
            world, dialog = self.open(False, blocked=blocked)
            with self.subTest(blocked=blocked):
                self.assertTrue(dialog.blockButton.IsShow())
                self.assertEqual(dialog.blockButton.text, text, "the stand-in locale answers keys")

    def test_the_button_sends_the_change_and_flips_at_once(self):
        world, dialog = self.open(False)
        mark = world.mark()
        with world.game, w4.quiet():
            dialog.blockButton.event(*dialog.blockButton.eventArgs)
        self.assertEqual([e for e in world.effects_since(mark) if e[0].startswith("net.")],
                         [("net.SendBlockAddPacket", ("Pest",))])
        unblock_text = dialog.blockButton.text
        world.blocked.add("Pest")
        mark = world.mark()
        with world.game, w4.quiet():
            dialog.BlockPlayer()
        self.assertEqual([e for e in world.effects_since(mark) if e[0].startswith("net.")],
                         [("net.SendBlockRemovePacket", ("Pest",))])
        self.assertNotEqual(dialog.blockButton.text, unblock_text)

    def test_a_dialog_without_a_target_hides_the_button_and_sends_nothing(self):
        world = w4.World(False, social=True)
        world.interface = whisper_test.Interface(world)
        with world.game, w4.quiet():
            dialog = world.interface.OpenWhisperDialogWithoutTarget()
        self.assertFalse(dialog.blockButton.IsShow())
        mark = world.mark()
        with world.game, w4.quiet():
            dialog.BlockPlayer()
            dialog.RefreshBlockButton()
        self.assertEqual([e for e in world.effects_since(mark) if e[0].startswith("net.")], [])
        self.assertFalse(dialog.blockButton.IsShow())

    def test_the_button_sits_left_of_the_minimize_button_at_any_size(self):
        world, dialog = self.open(False)
        for width in (280, 400):
            with world.game, w4.quiet():
                dialog.SetWhisperDialogSize(width, 200)
            self.assertEqual(position(dialog.blockButton), (width - 86, 8))
            self.assertLessEqual(width - 86 + 43, width - 42, "clear of the minimize button")

    def test_right_to_left_the_button_is_placed_from_its_right_edge(self):
        world, dialog = self.open(False)
        world.game.modules["app"].IsRTL = lambda: True
        # SetWhisperDialogSize's own right-to-left branch needs more of the
        # engine than the stand-ins have; the placement it calls is tested alone.
        with world.game, w4.quiet():
            dialog.blockButton.GetWidth = lambda: 43
            dialog._WhisperDialog__PlaceBlockButton(300)
        self.assertEqual(position(dialog.blockButton), (300 - 86 + 43, 8))

    def test_under_novaui_the_dialog_has_no_block_button_and_nothing_raises(self):
        world, dialog = self.open(True)
        self.assertIsNone(dialog.blockButton)
        with world.game, w4.quiet():
            dialog.RefreshBlockButton()
            dialog.BlockPlayer()
            dialog.OpenWithoutTarget(lambda name: None)
            dialog.SetWhisperDialogSize(300, 200)

    def test_the_uiscript_has_the_block_button(self):
        kids = children(uiscript("whisperdialog.py"), "board")
        self.assertEqual(kids["blockbutton"]["type"], "button")
        self.assertEqual(kids["blockbutton"]["text"], "BLOCK_PLAYER")
        self.assertEqual(kids["blockbutton"]["default_image"], "d:/ymir work/ui/public/small_button_01.sub")


class TargetBlock(unittest.TestCase):
    def board(self, name="NuiW2B2", blocked=()):
        def setup(game):
            hud.target_setup(game)
            game.answer("messenger", "IsBlocked", lambda who: who in blocked)
        legacy, _ = hud.pair(setup)
        with legacy:
            legacy.board = legacy.make("target", legacy.module("uiTarget").TargetBoard, "nui_target.TargetBoard")
            legacy.board.Hide()
            legacy.board.Open(hud.PEER_VID, name)
        return legacy

    def buttons(self, world):
        return hud.TargetWorlds.legacy_view(world)["buttons"]

    def test_a_stranger_gets_block_and_a_blocked_player_unblock(self):
        world = self.board()
        T = world.module("uiTarget").TargetBoard
        self.assertEqual((T.BTN_BLOCK, T.BTN_UNBLOCK), (18, 19))
        self.assertEqual(self.buttons(world), [T.BTN_WHISPER, T.BTN_EXCHANGE, T.BTN_FIGHT, T.BTN_EMOTION_ALLOW,
                                               T.BTN_FRIEND, T.BTN_INVITE_PARTY, T.BTN_BLOCK])
        world = self.board(blocked=("NuiW2B2",))
        self.assertIn(T.BTN_UNBLOCK, self.buttons(world))
        self.assertNotIn(T.BTN_BLOCK, self.buttons(world))

    def test_staff_get_neither(self):
        world = self.board(name="[GM]Nova")
        T = world.module("uiTarget").TargetBoard
        self.assertNotIn(T.BTN_BLOCK, self.buttons(world))
        self.assertNotIn(T.BTN_UNBLOCK, self.buttons(world))

    def test_the_buttons_send_and_swap(self):
        world = self.board()
        T = world.module("uiTarget").TargetBoard
        mark = len(world.game.log)
        with world, hud.quiet():
            world.board.buttonDict[T.BTN_BLOCK].Click()
        self.assertEqual(world.effects(mark), [("net.SendBlockAddPacket", ("NuiW2B2",))])
        self.assertIn(T.BTN_UNBLOCK, self.buttons(world))
        self.assertNotIn(T.BTN_BLOCK, self.buttons(world))
        mark = len(world.game.log)
        with world, hud.quiet():
            world.board.buttonDict[T.BTN_UNBLOCK].Click()
        self.assertEqual(world.effects(mark), [("net.SendBlockRemovePacket", ("NuiW2B2",))])
        self.assertIn(T.BTN_BLOCK, self.buttons(world))

    def test_the_button_texts_are_olds_keys(self):
        world = self.board()
        T = world.module("uiTarget").TargetBoard
        config = dict(T.BUTTON_CONFIG)
        self.assertEqual((config[T.BTN_BLOCK], config[T.BTN_UNBLOCK]), ("TARGET_BUTTON_BLOCK", "TARGET_BUTTON_UNBLOCK"))


class WhisperError(unittest.TestCase):
    def window(self):
        log = []
        chat = support.Recording("chat", log, WHISPER_TYPE_SENDER_IS_BLOCKED=7, WHISPER_TYPE_SYSTEM=255)
        interface = support.Recording("interface", log)
        locale = support.locale_info("en")
        locale.WHISPER_ERROR = {1: lambda name: "%s is not online." % name}
        cls = compiled("game.py", "GameWindow", ("OnRecvWhisperError",), {"chat": chat, "localeInfo": locale})
        window = cls()
        window.interface = interface
        return window, log

    def test_type_7_says_the_target_blocked_you_in_the_whisper_and_no_more(self):
        window, log = self.window()
        window.OnRecvWhisperError(7, "Target", "")
        self.assertEqual(log, [("chat.AppendWhisper", (255, "Target", "You can't write to Target because they blocked you."))])

    def test_other_types_keep_their_path(self):
        window, log = self.window()
        window.OnRecvWhisperError(99, "Target", "")
        self.assertEqual(log[0][0], "chat.AppendWhisper")
        self.assertIn("mode=99", log[0][1][2])
        self.assertEqual(log[1], ("interface.RecvWhisper", ("Target",)))


class LanguageFlags(unittest.TestCase):
    def setUp(self):
        game = support.Game()
        game.load_standard()
        self.const = game.loaded["constInfo"]

    def test_every_known_code_has_its_flag_file_from_old(self):
        self.assertEqual(len(self.const.LANGUAGE_FLAG_CODES), 16)
        for code in self.const.LANGUAGE_FLAG_CODES:
            with self.subTest(code=code):
                self.assertTrue(os.path.isfile(os.path.join(FLAGS, code + ".tga")))
        self.assertEqual(sorted(name[:-4] for name in os.listdir(FLAGS)), sorted(self.const.LANGUAGE_FLAG_CODES))

    def test_a_code_maps_to_its_vfs_path_and_an_unknown_one_to_nothing(self):
        flag = self.const.GET_LANGUAGE_FLAG
        self.assertEqual(flag("en"), "locale/common/ui/flag/32/en.tga")
        self.assertEqual(flag(" PT "), "locale/common/ui/flag/32/pt.tga")
        self.assertEqual(flag("br"), "", "OLD shipped no br flag")
        self.assertEqual(flag(""), "")


class Locales(unittest.TestCase):
    KEYS = (ROSTER_KEYS, BLOCK_KEYS, WAR_KEYS)

    def test_every_locale_has_every_new_key_olds_text_or_english(self):
        locales = [name for name in sorted(os.listdir(LOCALES))
                   if os.path.isfile(os.path.join(LOCALES, name, "locale_game.txt"))]
        self.assertEqual(len(locales), 17)
        for locale in locales:
            for keys in self.KEYS:
                for kind, english in keys.items():
                    path = os.path.join(LOCALES, locale, "locale_%s.txt" % kind)
                    self.assertTrue(read(path).endswith("\n"), path)
                    entries = locale_entries(path)
                    old_path = os.path.join(OLD_LOCALES, locale, "locale_%s.txt" % kind)
                    old = locale_entries(old_path) if os.path.isfile(old_path) else {}
                    for key, text in english.items():
                        with self.subTest(locale=locale, key=key):
                            self.assertTrue(entries.get(key, "").strip())
                            if os.path.isdir(OLD_LOCALES):
                                taken = None if (locale, kind, key) in NOT_OLD else old.get(key)
                                self.assertEqual(entries[key], taken or text)
                            if locale == "en":
                                self.assertEqual(entries[key], text)

    def test_the_war_lines_take_one_number_in_every_locale(self):
        for locale in sorted(os.listdir(LOCALES)):
            path = os.path.join(LOCALES, locale, "locale_game.txt")
            if not os.path.isfile(path):
                continue
            entries = locale_entries(path)
            for key in WAR_KEYS["game"]:
                with self.subTest(locale=locale, key=key):
                    self.assertEqual(entries[key].count("%d"), 1)
                    self.assertIn("32", entries[key] % 32)


# --- whisper details (NOVA-48) ---------------------------------------------------------------------

class WhisperDetails(unittest.TestCase):
    ONLINE = "d:/ymir work/ui/game/windows/messenger_list_online.sub"
    OFFLINE = "d:/ymir work/ui/game/windows/messenger_list_offline.sub"

    def open(self, nui_on, name="Pest"):
        world = w4.World(nui_on, social=True)
        world.interface = whisper_test.Interface(world)
        with world.game, w4.quiet():
            dialog = world.interface.OpenWhisperDialog(name)
        return world, dialog

    def details(self, world, dialog, online, language):
        with world.game, w4.quiet():
            dialog.SetTargetDetails(online, language)

    def test_neither_icon_shows_before_the_first_answer(self):
        world, dialog = self.open(False)
        self.assertFalse(dialog.online.IsShow())
        self.assertFalse(dialog.flag.IsShow())

    def test_an_online_target_shows_the_online_icon_and_its_flag(self):
        world, dialog = self.open(False)
        self.details(world, dialog, 1, "pt")
        self.assertEqual(dialog.online.image, self.ONLINE)
        self.assertTrue(dialog.online.IsShow())
        self.assertEqual(dialog.flag.image, "locale/common/ui/flag/32/pt.tga")
        self.assertTrue(dialog.flag.IsShow())
        for language in ("", "xx"):
            with self.subTest(language=language):
                self.details(world, dialog, 1, language)
                self.assertTrue(dialog.online.IsShow())
                self.assertFalse(dialog.flag.IsShow(), "no language (until NOVA-51) or no flag file: no flag")

    def test_an_offline_target_shows_the_offline_icon_and_no_flag(self):
        world, dialog = self.open(False)
        self.details(world, dialog, 1, "en")
        self.details(world, dialog, 0, "en")
        self.assertEqual(dialog.online.image, self.OFFLINE)
        self.assertTrue(dialog.online.IsShow())
        self.assertFalse(dialog.flag.IsShow())

    def test_a_reopened_dialog_forgets_the_last_answer(self):
        world, dialog = self.open(False)
        self.details(world, dialog, 1, "en")
        with world.game, w4.quiet():
            dialog.OpenWithoutTarget(lambda name: None)
        self.assertFalse(dialog.online.IsShow())
        self.assertFalse(dialog.flag.IsShow())
        self.details(world, dialog, 1, "en")
        with world.game, w4.quiet():
            dialog.OpenWithTarget("Other")
        self.assertFalse(dialog.online.IsShow())

    def test_accepting_a_typed_target_asks_for_its_details_once(self):
        world = w4.World(False, social=True)
        world.interface = whisper_test.Interface(world)
        with world.game, w4.quiet():
            dialog = world.interface.OpenWhisperDialogWithoutTarget()
        mark = world.mark()
        with world.game, w4.quiet():
            dialog.titleNameEdit.SetText("Pest")
            dialog.AcceptTarget()
        self.assertEqual([e for e in world.effects_since(mark) if e[0] == "net.SendWhisperDetailsPacket"],
                         [("net.SendWhisperDetailsPacket", ("Pest",))])
        self.assertIs(world.interface.dialogs["Pest"], dialog)

        with world.game, w4.quiet():
            dialog = world.interface.OpenWhisperDialogWithoutTarget()
        mark = world.mark()
        with world.game, w4.quiet():
            dialog.titleNameEdit.SetText("")
            dialog.AcceptTarget()
        self.assertEqual([e for e in world.effects_since(mark) if e[0] == "net.SendWhisperDetailsPacket"], [],
                         "no name: the dialog closes and asks nothing")

    def test_under_novaui_the_dialog_has_neither_icon_and_nothing_raises(self):
        world, dialog = self.open(True)
        self.assertIsNone(dialog.online)
        self.assertIsNone(dialog.flag)
        self.details(world, dialog, 1, "en")
        self.details(world, dialog, 0, "")
        with world.game, w4.quiet():
            dialog.OpenWithoutTarget(lambda name: None)
            dialog.OpenWithTarget("Pest")

    def test_the_uiscript_puts_both_icons_at_olds_places(self):
        kids = children(uiscript("whisperdialog.py"), "board")
        self.assertEqual((kids["online"]["type"], kids["online"]["x"], kids["online"]["y"]), ("image", 142, 12))
        self.assertEqual(kids["online"]["image"], self.ONLINE)
        self.assertEqual((kids["flag"]["type"], kids["flag"]["x"], kids["flag"]["y"]), ("image", 160, 8))
        self.assertLessEqual(kids["flag"]["x"] + 32, kids["blockbutton"]["x"], "the flag ends before the block button")


class GameWhisperDetails(unittest.TestCase):
    NAMES = ("__AskWhisperDetails", "BINARY_WhisperDetails", "WHISPER_DETAILS_INTERVAL")

    def window(self, dialogs):
        self.log = []
        self.now = [10.0]
        net = support.Recording("net", self.log)
        app = support.Recording("app", self.log)
        app.__dict__["_answers"]["GetTime"] = lambda: self.now[0]
        cls = compiled("game.py", "GameWindow", self.NAMES, {"net": net, "app": app})
        window = cls()
        window.interface = types.SimpleNamespace(whisperDialogDict=dialogs)
        window.whisperDetailsAskTime = {}
        return window

    def asked(self):
        names = [args[0] for name, args in self.log if name == "net.SendWhisperDetailsPacket"]
        del self.log[:]
        return names

    def tick(self, window, now):
        self.now[0] = now
        window._GameWindow__AskWhisperDetails()
        return self.asked()

    def test_each_open_dialog_with_a_target_is_asked_at_once_and_every_two_seconds(self):
        dialogs = {"Pest": object(), "Troll": object()}
        window = self.window(dialogs)
        self.assertEqual(window.WHISPER_DETAILS_INTERVAL, 2.0)
        self.assertEqual(sorted(self.tick(window, 10.0)), ["Pest", "Troll"])
        self.assertEqual(self.tick(window, 11.9), [])
        self.assertEqual(sorted(self.tick(window, 12.0)), ["Pest", "Troll"])

        dialogs["New"] = object()
        self.assertEqual(self.tick(window, 12.5), ["New"], "a newly opened dialog is asked at once")

        del dialogs["Troll"]
        self.assertEqual(self.tick(window, 13.0), [])
        self.assertNotIn("Troll", window.whisperDetailsAskTime, "a closed dialog's time is dropped")
        self.assertEqual(self.tick(window, 14.0), ["Pest"])

    def test_target_less_entries_are_skipped_and_no_dialog_asks_nothing(self):
        window = self.window({0: object(), "": object()})
        self.assertEqual(self.tick(window, 10.0), [])
        window = self.window({})
        window.whisperDetailsAskTime["Gone"] = 1.0
        self.assertEqual(self.tick(window, 10.0), [])
        self.assertEqual(window.whisperDetailsAskTime, {})

    def test_the_answer_reaches_the_open_dialog_to_that_name(self):
        seen = []
        dialog = types.SimpleNamespace(SetTargetDetails=lambda online, language: seen.append((online, language)))
        window = self.window({"Pest": dialog})
        window.BINARY_WhisperDetails("Pest", 1, "en")
        window.BINARY_WhisperDetails("Nobody", 1, "en")
        self.assertEqual(seen, [(1, "en")])
        window.interface = None
        window.BINARY_WhisperDetails("Pest", 0, "")
        self.assertEqual(seen, [(1, "en")])

    def test_on_update_runs_the_poll(self):
        source = support.source_of("game.py", ("OnUpdate",), inside="GameWindow")
        self.assertIn("self.__AskWhisperDetails()", source)


# --- the guild war's member cap and end score (NOVA-90) ---------------------------------------------

class DeclareWarLimits(unittest.TestCase):
    def open(self, nui_on):
        world = guild_test.world_of(nui_on)
        dialog = world.make("guild-war-dialogs", "uiGuild", "DeclareGuildWarDialog",
                            "nui_guild_war_declare.DeclareGuildWarDialog")
        with world.game, w4.quiet():
            dialog.Open()
        return world, dialog

    def ok(self, world, dialog, name="Black Wolves", members=None, score=None, war_type=2):
        with world.game, w4.quiet():
            dialog.inputValue.SetText(name)
            dialog.typeButtonList[war_type].click() if not world.nui_on else None
            if members is not None:
                dialog.memberCountInput.SetText(members)
            if score is not None:
                dialog.endScoreInput.SetText(score)
            mark = world.mark()
            dialog.acceptButton.click()
        return [e for e in world.effects_since(mark) if e[0] == "net.SendChatPacket"]

    def test_open_fills_both_number_inputs_with_olds_32(self):
        world, dialog = self.open(False)
        for field in (dialog.memberCountInput, dialog.endScoreInput):
            self.assertEqual(field.GetText(), "32")
        source = support.source_of("uiguild.py", ("Open",), inside="DeclareGuildWarDialog")
        self.assertIn("warLimitInput.SetNumberMode()", source)

    def test_both_numbers_go_with_the_declaration(self):
        world, dialog = self.open(False)
        self.assertEqual(self.ok(world, dialog, members="40", score="100"),
                         [("net.SendChatPacket", ("/war Black Wolves 2 40 100",))])
        self.assertFalse(dialog.IsShow())

    def test_without_both_numbers_the_two_argument_command_goes(self):
        for members, score in (("", "100"), ("40", ""), ("4x", "100")):
            world, dialog = self.open(False)
            with self.subTest(members=members, score=score):
                self.assertEqual(self.ok(world, dialog, members=members, score=score),
                                 [("net.SendChatPacket", ("/war Black Wolves 2",))])

    def test_an_empty_name_still_sends_nothing(self):
        world, dialog = self.open(False)
        self.assertEqual(self.ok(world, dialog, name=""), [])
        self.assertTrue(dialog.IsShow())

    def test_close_forgets_the_inputs(self):
        world, dialog = self.open(False)
        with world.game, w4.quiet():
            dialog.Close()
        self.assertIsNone(dialog.memberCountInput)
        self.assertIsNone(dialog.endScoreInput)
        self.assertEqual(dialog.GetWarLimits(), (None, None))

    def test_under_novaui_there_are_no_inputs_and_the_two_argument_command_goes(self):
        world, dialog = self.open(True)
        self.assertIsNone(dialog.memberCountInput)
        self.assertIsNone(dialog.endScoreInput)
        self.assertEqual(dialog.GetWarLimits(), (None, None))
        with world.game, w4.quiet():
            w4.board(dialog).insert_text(guild_test.FIELD, "Black Wolves")
            w4.press(dialog, "type_press", 2, 0)
            mark = world.mark()
            w4.press(dialog, "accept_press", 0)
        self.assertEqual([e for e in world.effects_since(mark) if e[0] == "net.SendChatPacket"],
                         [("net.SendChatPacket", ("/war Black Wolves 2",))])

    def test_the_uiscript_has_olds_two_rows(self):
        window = uiscript("declareguildwardialog.py")
        self.assertEqual((window["width"], window["height"]), (230, 170))
        board = children(window)["Board"]
        self.assertEqual((board["width"], board["height"]), (230, 170))
        kids = children(window, "Board")
        self.assertEqual(kids["InputMemberCount"]["text"], "GUILD_WAR_ENEMY_NUMBER")
        self.assertEqual(kids["InputScoreCount"]["text"], "GUILD_WAR_MAX_SCORE")
        for slot, field in (("MemberCountInput", "MemberInputValue"), ("EndScoreInput", "EndScoreInputValue")):
            entry = children(window, "Board", slot)[field]
            self.assertEqual((entry["type"], entry["input_limit"]), ("editline", 3))
        # The enemy guild's name keeps the guild name length beside the new rows.
        self.assertEqual(children(window, "Board", "InputSlot")["InputValue"]["input_limit"], 24)
        self.assertEqual((kids["MemberCountInput"]["x"], kids["MemberCountInput"]["y"]), (85, 67))
        self.assertEqual((kids["EndScoreInput"]["x"], kids["EndScoreInput"]["y"]), (180, 67))
        self.assertEqual(kids["GameType"]["y"], 100)
        self.assertEqual((kids["AcceptButton"]["y"], kids["CancelButton"]["y"]), (130, 130))


class AcceptWarLimits(unittest.TestCase):
    def open(self, nui_on, *args):
        world = guild_test.world_of(nui_on)
        dialog = world.make("guild-war-dialogs", "uiGuild", "AcceptGuildWarDialog",
                            "nui_guild_war_accept.AcceptGuildWarDialog")
        with world.game, w4.quiet():
            dialog.Open("Black Wolves", 2, *args)
        return world, dialog

    def test_both_limits_show_each_guilds_half_of_the_cap_and_the_score(self):
        world, dialog = self.open(False, 64, 250)
        self.assertEqual(dialog.membersCountText.GetText(), "Players Limit from your guild: 32.")
        self.assertEqual(dialog.endScoreText.GetText(), "The war will end at 250 Kills.")
        self.assertTrue(dialog.membersCountText.IsShow())
        self.assertTrue(dialog.endScoreText.IsShow())

    def test_without_limits_neither_line_shows(self):
        for args in ((), (0, 0)):
            world, dialog = self.open(False, *args)
            with self.subTest(args=args):
                self.assertFalse(dialog.membersCountText.IsShow())
                self.assertFalse(dialog.endScoreText.IsShow())
        world, dialog = self.open(False, 0, 100)
        self.assertFalse(dialog.membersCountText.IsShow())
        self.assertTrue(dialog.endScoreText.IsShow())

    def test_under_novaui_both_lines_are_missing_and_open_takes_four_arguments(self):
        world, dialog = self.open(True, 64, 250)
        self.assertIsNone(dialog.membersCountText)
        self.assertIsNone(dialog.endScoreText)
        self.assertEqual(dialog.GetGuildName(), "Black Wolves")

    def test_close_forgets_the_lines(self):
        world, dialog = self.open(False, 64, 250)
        with world.game, w4.quiet():
            dialog.Close()
        self.assertIsNone(dialog.membersCountText)
        self.assertIsNone(dialog.endScoreText)

    def test_the_uiscript_grows_as_olds(self):
        window = uiscript("acceptguildwardialog.py")
        self.assertEqual((window["width"], window["height"]), (230, 175))
        kids = children(window, "Board")
        self.assertEqual((kids["MembersCount"]["x"], kids["MembersCount"]["y"]), (15, 65))
        self.assertEqual((kids["EndScore"]["x"], kids["EndScore"]["y"]), (15, 90))
        self.assertEqual(kids["GameType"]["y"], 120)
        self.assertEqual((kids["AcceptButton"]["y"], kids["CancelButton"]["y"]), (150, 150))


class GameWarDeclare(unittest.TestCase):
    def window(self, master=True):
        self.log = []
        self.opened = []
        player = support.Recording("player", self.log)
        player.__dict__["_answers"]["GetMainCharacterName"] = "Boss"
        guild = support.Recording("guild", self.log)
        guild.__dict__["_answers"]["GetGuildMasterName"] = "Boss" if master else "Someone"
        guild.__dict__["_answers"]["GetGuildName"] = lambda guild_id: "Rivals"
        opened = self.opened

        class Dialog(object):
            def SAFE_SetAcceptEvent(self, event):
                pass

            def SAFE_SetCancelEvent(self, event):
                pass

            def Open(self, *args):
                opened.append(args)
        nui_windows = types.SimpleNamespace(make=lambda *args: Dialog())
        ui_guild = types.ModuleType("uiGuild")
        ui_guild.AcceptGuildWarDialog = Dialog
        cls = compiled("game.py", "GameWindow", ("BINARY_GuildWar_OnRecvDeclare", "__GuildWar_OpenAskDialog"),
                       {"player": player, "guild": guild, "nui_windows": nui_windows})
        cls._GameWindow__GuildWar_OnAccept = lambda self: 1
        cls._GameWindow__GuildWar_OnDecline = lambda self: 1
        sys.modules["uiGuild"] = ui_guild
        self.addCleanup(sys.modules.pop, "uiGuild", None)
        return cls()

    def test_the_master_gets_the_dialog_with_the_cap_and_score(self):
        window = self.window()
        window.BINARY_GuildWar_OnRecvDeclare(901, 2, 64, 250)
        self.assertEqual(self.opened, [("Rivals", 2, 64, 250)])

    def test_two_arguments_still_work_with_no_limits(self):
        window = self.window()
        window.BINARY_GuildWar_OnRecvDeclare(901, 1)
        self.assertEqual(self.opened, [("Rivals", 1, 0, 0)])

    def test_others_get_nothing(self):
        window = self.window(master=False)
        window.BINARY_GuildWar_OnRecvDeclare(901, 2, 64, 250)
        self.assertEqual(self.opened, [])



if __name__ == "__main__":
    unittest.main()
