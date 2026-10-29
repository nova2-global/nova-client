"""Tests for the NovaUI messenger (assets/root/nui_messenger.py, P16 spec
5.7): python3 -B -m unittest nui_messenger_test (from tools/).

The legacy uiMessenger.MessengerWindow (made from its real uiscript by
nui_game_support's stand-ins) and the NovaUI one, each in a world of its own
(nui_w4_world.World with the social windows), driven as the C++ messenger
handler, the game window's lover calls and the Interface drive them (spec
5.7.4): friends and guild members logging in and out, removed one by one or
all at once, the lover, a press on a row (a group opens or closes, a member
is selected), a double click, the whisper, remove, add and guild buttons with
the dialog kit's question and input dialogs, the close button, Escape and the
resize edge. The board's rows are legacy's items (showingItemList) after
every call, and both windows make the same calls in the same order."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402

DOCUMENT = "nui/windows/messenger/messenger.rml"
# The C++ handler's group indices (uimessenger.py): the staff rosters since
# NOVA-30/46, the block list since NOVA-47.
FRIEND, GUILD, HELPER, TEAMLER, BLOCK = 0, 1, 2, 3, 4


def guild_state(game):
    """[GM-TEAM]'s state as the guild module answers it: the tester may
    remove members, Dana is a member, Boss the master."""
    game.w4["guild"].update({"id": 7, "name": "GM-TEAM", "master": "Boss", "my_auth": 2,
                             "members": [{"pid": 11, "name": "Dana", "grade": 2, "job": 0, "level": 50, "offer": 0,
                                          "general": 0, "online": True}]})


class MessengerTest(unittest.TestCase):
    def world(self, nui_on, setup=guild_state, **kwargs):
        world = w4.World(nui_on, setup=setup, social=True, **kwargs)
        window = world.make("messenger", "uiMessenger", "MessengerWindow", "nui_messenger.MessengerWindow")
        world.whispers = []
        world.guild_presses = []
        with world.game, w4.quiet():
            # Interface.__MakeWindows and __MakeDialogs (interfacemodule.py:103-107, :334).
            window.SetWhisperButtonEvent(lambda name: world.whispers.append(name))
            window.SetGuildButtonEvent(lambda: world.guild_presses.append(True))
            window.InitializeHandler()
        return world, window

    def fill(self, world, window):
        """The C++ handler's calls at the login: two friends online, one
        offline, two guild members."""
        with world.game, w4.quiet():
            window.OnLogin(FRIEND, "Alice")
            window.OnLogout(FRIEND, "Bob")
            window.OnLogin(FRIEND, "Carl")
            window.OnLogin(GUILD, "Dana")
            window.OnLogout(GUILD, "Boss")

    def show(self, world, window):
        """Interface.ToggleMessenger (interfacemodule.py:945-949)."""
        with world.game, w4.quiet():
            window.SetTop()
            window.Show()

    def legacy_rows(self, world, window):
        row_of = world.m("nui_messenger").row_of
        return [row_of(item) for item in window.showingItemList]

    def press_row(self, world, window, index):
        """A left press on a row: the item's own press, legacy's
        MessengerItem.OnMouseLeftButtonDown (after the window manager's
        raise)."""
        with world.game, w4.quiet():
            if world.nui_on:
                w4.press(window, "row_press", index, 0)
            else:
                window.SetTop()
                window.showingItemList[index].OnMouseLeftButtonDown()

    def press(self, world, window, name):
        """One of the buttons: the board's event, or the legacy button."""
        with world.game, w4.quiet():
            if world.nui_on:
                w4.press(window, name + "_press", 0)
            else:
                window.SetTop()
                button = {"add": window.addFriendButton, "whisper": window.whisperButton,
                          "remove": window.removeButton, "guild": window.guildButton,
                          "block": window.blockPlayerButton, "unblock": window.unblockPlayerButton}[name]
                if button.event:
                    button.event(*button.eventArgs)

    def run_both(self, flow, setup=guild_state):
        results = []
        for nui_on in (False, True):
            world, window = self.world(nui_on, setup)
            self.fill(world, window)
            self.show(world, window)
            mark = world.mark()
            with world.game, w4.quiet():
                flow(world, window)
            results.append((world.effects_since(mark), world, window))
        return results

    def last_dialog(self, world, kind):
        found = [dialog for dialog in world.game.dialogs if dialog._name == kind]
        return found[-1] if found else None


class Model(MessengerTest):
    def test_the_rows_are_legacy_s_items_after_every_handler_call(self):
        calls = (
            ("OnLogin", FRIEND, "Alice"), ("OnLogout", FRIEND, "Bob"), ("OnLogin", GUILD, "Dana"),
            ("OnLogin", FRIEND, "Bob"), ("OnLogout", FRIEND, "Alice"), ("OnRemoveList", FRIEND, "Bob"),
            ("OnAddLover", "Erin", 42), ("OnUpdateLovePoint", 87), ("OnLoginLover",), ("OnLogoutLover",),
            ("OnRemoveAllList", GUILD), ("ClearGuildMember",), ("RefreshMessenger",), ("ClearLoverInfo",),
        )
        worlds = []
        for nui_on in (False, True):
            world, window = self.world(nui_on)
            self.show(world, window)
            worlds.append((world, window))
        (lw, lwin), (nw, nwin) = worlds
        for call in calls:
            for world, window in worlds:
                with world.game, w4.quiet():
                    getattr(window, call[0])(*call[1:])
            with self.subTest(call=call):
                self.assertEqual(w4.board(nwin).model["rows"], self.legacy_rows(lw, lwin))
        # Friend, Guild, then the Helper, Team and Blocked Players groups
        # since NOVA-30/46/47, each showing the empty line.
        self.assertEqual([row["kind"] for row in self.legacy_rows(lw, lwin)],
                         ["group", "member", "group", "empty"] + ["group", "empty"] * 3)

    def test_the_family_group_and_the_lover_come_first_with_the_love_points(self):
        world, window = self.world(True)
        self.fill(world, window)
        with world.game, w4.quiet():
            window.OnAddLover("Erin", 87)
        self.show(world, window)
        rows = w4.board(window).model["rows"]
        self.assertEqual([(row["kind"], row["name"]) for row in rows[:2]],
                         [("group", world.m("localeInfo").MESSENGER_FAMILY), ("member", "Erin")])
        self.assertEqual((rows[1]["love"], rows[1]["hint"]), (87, world.m("localeInfo").AFF_LOVE_POINT % 87))
        self.assertTrue(all(row["love"] == -1 for row in rows[2:]))

    def test_a_press_on_a_group_closes_it_and_a_second_opens_it(self):
        def flow(world, window):
            self.press_row(world, window, 0)
            world.closed = list(self.legacy_rows(world, window))
            self.press_row(world, window, 0)
        (legacy, a_world, a), (novaui, b_world, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual([row["kind"] for row in b_world.closed][:2], ["group", "group"], "the friends' rows went")
        self.assertEqual(w4.board(b).model["rows"], self.legacy_rows(a_world, a))
        self.assertTrue(w4.board(b).model["rows"][0]["open"])

    def test_the_buttons_follow_legacy_s_rules_for_the_selected_row(self):
        # Rows: Friends, Alice (on), Carl (on), Bob (off), Guild, Dana (on), Boss (off); the
        # group last, since a press on it closes it.
        expect = ((1, True, True), (3, False, True), (5, True, True), (6, False, False), (0, False, False))
        world, window = self.world(True)
        self.fill(world, window)
        self.show(world, window)
        for index, whisper, remove in expect:
            self.press_row(world, window, index)
            model = w4.board(window).model
            with self.subTest(row=model["rows"][index]["name"]):
                self.assertTrue(model["rows"][index]["selected"])
                self.assertEqual((model["whisper_enabled"], model["remove_enabled"]), (whisper, remove))
                self.assertEqual((window.whisperButton.enabled, window.removeButton.enabled), (whisper, remove))


class Flows(MessengerTest):
    def test_the_whisper_button_and_a_double_click_whisper_an_online_member(self):
        def flow(world, window):
            self.press_row(world, window, 1)
            self.press(world, window, "whisper")
            if world.nui_on:
                w4.fire(window, "row_dblclick", 2)
            else:
                window.showingItemList[2].OnMouseLeftButtonDoubleClick()
            self.press_row(world, window, 3)
            if world.nui_on:
                w4.fire(window, "row_dblclick", 3)
            else:
                window.showingItemList[3].OnMouseLeftButtonDoubleClick()
        (legacy, a_world, _), (novaui, b_world, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual(b_world.whispers, a_world.whispers)
        self.assertEqual(b_world.whispers, ["Alice", "Alice"], "a double click whispers the selected online member")

    def test_removing_a_friend_asks_then_removes_it(self):
        def flow(world, window):
            self.press_row(world, window, 3)
            self.press(world, window, "remove")
            self.last_dialog(world, "uiCommon.QuestionDialog").accept()
        (legacy, a_world, a), (novaui, b_world, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertIn(("messenger.RemoveFriend", ("Bob",)), novaui)
        self.assertIn(("net.SendMessengerRemovePacket", ("Bob", "Bob")), novaui)
        self.assertNotIn("Bob", [row["name"] for row in w4.board(b).model["rows"]])
        self.assertEqual(w4.board(b).model["rows"], self.legacy_rows(a_world, a))
        self.assertEqual((w4.board(b).model["whisper_enabled"], w4.board(b).model["remove_enabled"]), (False, False))

    def test_removing_a_guild_member_asks_then_sends_the_kick(self):
        def flow(world, window):
            self.press_row(world, window, 5)
            self.press(world, window, "remove")
            dialog = self.last_dialog(world, "uiCommon.QuestionDialog")
            world.question = dialog.texts
            dialog.accept()
        (legacy, a_world, _), (novaui, b_world, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual(b_world.question, [b_world.m("localeInfo").GUILD_REMOVE_MEMBER_QUESTION])
        self.assertIn(("net.SendGuildRemoveMemberPacket", ("Dana",)), novaui)

    def test_cancelling_the_question_removes_nothing(self):
        def flow(world, window):
            self.press_row(world, window, 1)
            self.press(world, window, "remove")
            self.last_dialog(world, "uiCommon.QuestionDialog").cancel()
        (legacy, _, _), (novaui, _, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertFalse([call for call in novaui if call[0].startswith(("net.", "messenger."))])
        self.assertIn("Alice", [row["name"] for row in w4.board(b).model["rows"]])

    def test_add_friend_sends_the_typed_name(self):
        for text in ("Partner", ""):
            def flow(world, window, text=text):
                self.press(world, window, "add")
                dialog = self.last_dialog(world, "uiCommon.InputDialog")
                dialog.text = text
                dialog.accept()
            (legacy, _, _), (novaui, _, _) = self.run_both(flow)
            with self.subTest(text=text):
                self.assertEqual(novaui, legacy)
                sent = [call for call in novaui if call[0] == "net.SendMessengerAddByNamePacket"]
                self.assertEqual(sent, [("net.SendMessengerAddByNamePacket", (text,))] if text else [])

    def test_block_sends_the_typed_name(self):
        """NOVA-47 (uimessenger.py OnPressBlockButton, OnBlockPlayer): the
        dialog kit's input dialog, then the block packet with the name."""
        for text in ("Rival", ""):
            def flow(world, window, text=text):
                self.press(world, window, "block")
                dialog = self.last_dialog(world, "uiCommon.InputDialog")
                dialog.text = text
                dialog.accept()
            (legacy, _, _), (novaui, _, _) = self.run_both(flow)
            with self.subTest(text=text):
                self.assertEqual(novaui, legacy)
                sent = [call for call in novaui if call[0] == "net.SendBlockAddPacket"]
                self.assertEqual(sent, [("net.SendBlockAddPacket", (text,))] if text else [])

    def test_the_blocked_group_follows_the_block_list_and_unblock_asks(self):
        """NOVA-47: the Blocked Players group holds the client's list at each
        show (__RefreshBlockedGroup) and follows the server's answers
        (OnBlockedAct); Unblock is enabled on a blocked player's row and asks
        before the unblock packet."""
        def blocked(game):
            guild_state(game)
            game.w4["messenger"]["blocked"].append("Rival")

        def flow(world, window):
            names = [item.GetName() for item in window.showingItemList]
            world.row = names.index("Rival")
            world.enabled_before = self.unblock_enabled(world, window)
            self.press_row(world, window, world.row)
            world.enabled_after = self.unblock_enabled(world, window)
            self.press(world, window, "unblock")
            dialog = self.last_dialog(world, "uiCommon.QuestionDialog")
            world.question = dialog.texts
            dialog.accept()
            window.OnBlockedAct(0, "Rival")
            window.OnBlockedAct(1, "Sly")
        (legacy, a_world, a), (novaui, b_world, b) = self.run_both(flow, setup=blocked)
        self.assertEqual(novaui, legacy)
        self.assertEqual((b_world.enabled_before, b_world.enabled_after), (False, True))
        self.assertEqual((a_world.enabled_before, a_world.enabled_after), (False, True))
        self.assertEqual(b_world.question, a_world.question)
        self.assertIn(("net.SendBlockRemovePacket", ("Rival",)), novaui)
        rows = w4.board(b).model["rows"]
        self.assertEqual(rows, self.legacy_rows(a_world, a))
        names = [row["name"] for row in rows]
        self.assertNotIn("Rival", names)
        self.assertEqual(names[-2:], [b_world.m("localeInfo").BLOCKED_PLAYERS_TITLE, "Sly"])

    @staticmethod
    def unblock_enabled(world, window):
        if world.nui_on:
            return w4.board(window).model["unblock_enabled"]
        # The legacy button's last Enable or Disable (the stand-in records them).
        states = [call[0] for call in window.unblockPlayerButton.calls if call[0] in ("Enable", "Disable")]
        return bool(states) and states[-1] == "Enable"

    def test_a_roster_member_s_languages_show_as_its_flags(self):
        """NOVA-30/46 (uimessenger.py SetLanguagesFlags): a Helper or Team
        member's languages, a flag each that has a file (constInfo)."""
        def flow(world, window):
            window.OnLogin(HELPER, "Helen")
            window.SetLanguagesFlags(HELPER, "Helen", "en de xx")
            window.OnLogout(TEAMLER, "Tom")
            window.SetLanguagesFlags(TEAMLER, "Tom", "pt")
        (legacy, a_world, a), (novaui, b_world, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        rows = w4.board(b).model["rows"]
        self.assertEqual(rows, self.legacy_rows(a_world, a))
        flags = dict((row["name"], row["flags"]) for row in rows if row["kind"] == "member")
        self.assertEqual(flags["Helen"], ["/locale/common/ui/flag/32/en.tga", "/locale/common/ui/flag/32/de.tga"])
        self.assertEqual(flags["Tom"], ["/locale/common/ui/flag/32/pt.tga"])
        self.assertEqual(flags["Alice"], [])
        legacy_helen = [item for item in a.showingItemList if item.GetName() == "Helen"][0]
        self.assertEqual(len(legacy_helen.flagImageList), 2)

    def test_the_guild_button_calls_the_interface(self):
        def flow(world, window):
            self.press(world, window, "guild")
        (legacy, a_world, _), (novaui, b_world, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual((a_world.guild_presses, b_world.guild_presses), ([True], [True]))

    def test_a_disabled_button_does_nothing(self):
        def flow(world, window):
            self.press_row(world, window, 0)
            self.press(world, window, "whisper")
            self.press(world, window, "remove")
        (legacy, a_world, _), (novaui, b_world, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual(b_world.whispers, [])
        self.assertIsNone(self.last_dialog(b_world, "uiCommon.QuestionDialog"))

    def test_the_close_button_and_escape_hide_it(self):
        for how in ("close", "escape"):
            def flow(world, window, how=how):
                if how == "escape":
                    window.OnPressEscapeKey()
                elif world.nui_on:
                    w4.press(window, "close_press", 0)
                else:
                    window.board.close()
            (legacy, _, a), (novaui, world, b) = self.run_both(flow)
            with self.subTest(how=how):
                self.assertEqual(novaui, legacy)
                self.assertFalse(a.IsShow())
                self.assertFalse(b.IsShow())
                self.assertNotIn(DOCUMENT, world.documents())

    def test_the_resize_edge_sets_legacy_s_height_and_its_least(self):
        world, window = self.world(True)
        self.fill(world, window)
        self.show(world, window)
        self.assertEqual(w4.board(window).model["height"], 310.0, "legacy's first size: the button at 300, plus 10")
        with world.game, w4.quiet():
            w4.fire(window, "resized", 220.4)
        self.assertEqual(w4.board(window).model["height"], 220.0)
        # Less the block buttons' row since NOVA-47 (uimessenger.py OnResizeDialog).
        self.assertEqual(window.showingPageSize, 210 - 66 - window.BLOCK_BUTTON_ROW_HEIGHT)
        with world.game, w4.quiet():
            w4.fire(window, "resized", 90)
        self.assertEqual(window.resizeButton.GetLocalPosition(), (0, 140), "legacy's least: the button at 140")
        self.assertEqual(w4.board(window).model["height"], 220.0, "legacy sizes nothing when it moves the button back")

    def test_the_size_and_the_rows_survive_a_hide(self):
        world, window = self.world(True)
        self.fill(world, window)
        self.show(world, window)
        with world.game, w4.quiet():
            w4.fire(window, "resized", 200)
            window.Hide()
            window.OnLogin(FRIEND, "Zed")
        self.assertIsNone(w4.board(window))
        self.show(world, window)
        model = w4.board(window).model
        self.assertEqual(model["height"], 200.0)
        self.assertIn("Zed", [row["name"] for row in model["rows"]])


class Facade(MessengerTest):
    def test_the_class_the_methods_and_no_per_frame_python(self):
        world, window = self.world(True)
        legacy_class = world.m("uiMessenger").MessengerWindow
        self.assertIsInstance(window, legacy_class)
        self.assertTrue(window.NUI_FACADE)
        self.assertIsNone(type(window).OnUpdate)
        self.assertIsNone(type(window).OnRender)
        for name in ("ClearGuildMember", "ClearLoverInfo", "Destroy", "Hide", "InitializeHandler", "IsShow", "OnAddLover",
                     "OnLoginLover", "OnLogoutLover", "OnUpdateLovePoint", "RefreshMessenger", "SetGuildButtonEvent",
                     "SetTop", "SetWhisperButtonEvent", "Show"):
            self.assertTrue(callable(getattr(window, name)), name)
        for name, member in inspect.getmembers(legacy_class, inspect.isfunction):
            self.assertEqual(len(inspect.signature(getattr(type(window), name)).parameters),
                             len(inspect.signature(member).parameters), name)
        module = world.m("nui_messenger")
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ == "nui_messenger":
                for attr in ("OnUpdate", "OnRender"):
                    self.assertFalse(callable(getattr(cls, attr, None)), "%s.%s" % (name, attr))

    def test_legacy_s_items_never_show(self):
        world, window = self.world(True)
        self.fill(world, window)
        self.show(world, window)
        self.press_row(world, window, 1)
        for item in window.showingItemList + window.groupList:
            self.assertFalse(item.IsShow(), item.GetName())

    def test_make_builds_legacy_with_the_flag_off_or_an_older_exe(self):
        world, window = self.world(False)
        self.assertIs(type(window), world.m("uiMessenger").MessengerWindow)
        world, window = self.world(True, engine_4=False)
        self.assertIs(type(window), world.m("uiMessenger").MessengerWindow)

    def test_on_demand_the_place_and_the_0_by_0_window(self):
        (a_world, a), (world, window) = [self.world(nui_on) for nui_on in (False, True)]
        self.assertNotIn(DOCUMENT, world.documents())
        self.show(world, window)
        self.assertIn(DOCUMENT, world.documents())
        self.assertEqual(w4.board(window).placement, ("position", 1600 - 200, 900 - 450, (0.0, 0.0)),
                         "legacy's (W - 200, H - 450)")
        self.assertEqual((window.GetWidth(), window.GetHeight()), (0, 0))
        self.assertEqual(window.flags, a.flags)
        self.assertIn("float", window.flags)

    def test_a_discarded_instance_keeps_the_legacy_window_s_handler(self):
        world, window = self.world(True)
        mark = world.mark()
        with world.game, w4.quiet():
            window.nui_discard()
            window.__del__()
        self.assertEqual(world.calls_since(mark, "messenger.SetMessengerHandler"), [])
        world, window = self.world(True)
        mark = world.mark()
        with world.game, w4.quiet():
            window.Destroy()
            window.__del__()
        self.assertEqual(world.calls_since(mark, "messenger.SetMessengerHandler"),
                         [("messenger.SetMessengerHandler", (None,))])

    def test_every_fixture_has_the_model_s_keys_and_kinds(self):
        world, window = self.world(True)
        kinds = w4.model_kinds(window.nui_model())
        for variant in ("", "foundation", "empty", "closed-groups"):
            self.assertEqual(w4.fixture_keys(window, "messenger", variant), kinds, variant)
        row_kinds = w4.model_kinds(world.m("nui_messenger").row_of(window.groupList[0]))
        for variant in ("", "foundation", "empty", "closed-groups"):
            data = w4.fixture_model("messenger", variant)
            for row in data["rows"]:
                self.assertEqual(w4.model_kinds(row), row_kinds, variant)

    def test_no_repeated_row_binds_its_own_entry(self):
        from nui_hud_test import repeated_element_reads
        markup = w4.read(os.path.join(w4.WINDOWS_DIR, "messenger", "messenger.rml"))
        self.assertEqual(repeated_element_reads(markup), [], "the list shrinks: a row's views read only its index")

    def test_the_interface_makes_it_through_make(self):
        text = w4.read(os.path.join(w4.ROOT, "interfacemodule.py"))
        self.assertIn('self.wndMessenger = nui_windows.make("messenger", uiMessenger.MessengerWindow, '
                      '"nui_messenger.MessengerWindow")', text)


if __name__ == "__main__":
    unittest.main()
