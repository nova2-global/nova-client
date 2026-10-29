"""Tests for the NovaUI whisper dialogs (assets/root/nui_whisper.py, P16
spec 5.8): python3 -B -m unittest nui_whisper_test (from tools/).

The legacy uiWhisper.WhisperDialog (made from its real uiscript by
nui_game_support's stand-ins) and the NovaUI one, each in a world of its own
(nui_w4_world.World with the social windows), driven as the Interface's
whisper code drives them (Interface below: interfacemodule.py:1458-1567):
opening a partner's dialog, sending (Enter and the button, the insult
check), the dialog without a partner (Enter, OK, an empty name, Escape),
minimize (Escape in the input) to an edge button and back, close, the GM
look, a link press (with and without Alt), the scroll, the wheel and the
resize corner. Both make the same chat, net and player calls in the same
order; NovaUI attaches each partner's whisper feed, keeps a minimized
dialog's draft, size, place and scroll (D8), and shows three dialogs at once,
each with its own model."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402

DOCUMENT = "nui/windows/whisper/whisper.rml"
INPUT, TARGET = "whisper-input", "whisper-target"
EFFECTS = support.W4_COMPARED + ("snd", "ime", "uiCommon")


class Interface(object):
    """The Interface's whisper code (interfacemodule.py:1458-1567), with the
    edge buttons as a list of names."""

    def __init__(self, world):
        self.world = world
        self.dialogs = {}
        self.buttons = []
        self.without = None
        self.position = 0
        self.links = []

    def make(self):
        world = self.world
        dialog = world.make("whisper", "uiWhisper", "WhisperDialog", "nui_whisper.WhisperDialog",
                            self.MinimizeWhisperDialog, self.CloseWhisperDialog)
        dialog.BindInterface(self)
        dialog.LoadDialog()
        dialog.SetPosition(self.position * 30, self.position * 30)
        self.position = (self.position + 1) % 5
        return dialog

    def OpenWhisperDialog(self, name):
        if name not in self.dialogs:
            dialog = self.dialogs[name] = self.make()
            dialog.OpenWithTarget(name)
            dialog.chatLine.SetFocus()
            dialog.Show()
            if name in self.buttons:
                self.buttons.remove(name)
        return self.dialogs[name]

    def ShowWhisperDialog(self, name):
        dialog = self.dialogs[name] = self.make()
        dialog.OpenWithTarget(name)
        dialog.Show()
        self.buttons.remove(name)
        return dialog

    def OpenWhisperDialogWithoutTarget(self):
        dialog = self.make()
        dialog.OpenWithoutTarget(self.RegisterTemporaryWhisperDialog)
        dialog.Show()
        self.without = dialog
        return dialog

    def RegisterTemporaryWhisperDialog(self, name):
        if name in self.dialogs:
            self.dialogs.pop(name).Destroy()
        self.dialogs[name] = self.without
        self.without.OpenWithTarget(name)
        self.without = None

    def MinimizeWhisperDialog(self, name):
        if 0 != name:
            self.buttons.append(name)
        self.CloseWhisperDialog(name)

    def CloseWhisperDialog(self, name):
        if 0 == name:
            if self.without:
                self.without.Destroy()
                self.without = None
            return
        self.dialogs.pop(name).Destroy()

    def MakeHyperlinkTooltip(self, link):
        self.links.append(link)


class WhisperTest(unittest.TestCase):
    def world(self, nui_on, **kwargs):
        world = w4.World(nui_on, social=True, **kwargs)
        world.interface = Interface(world)
        return world

    def worlds(self):
        return [self.world(nui_on) for nui_on in (False, True)]

    def type_and(self, world, dialog, text, key):
        """Text typed into the input, then a key: the NovaUI field's keydown,
        or the legacy edit line's events (the IME's return and escape)."""
        if world.nui_on:
            board = w4.board(dialog)
            if text:
                board.insert_text(INPUT, text)
            nui = world.m("nui")
            return board.key(INPUT, {"enter": nui.KEY_RETURN, "escape": nui.KEY_ESCAPE}[key])
        if text:
            dialog.chatLine.SetText(dialog.chatLine.GetText() + text)
        return (dialog.chatLine.eventReturn if key == "enter" else dialog.chatLine.eventEscape)()

    def waiting(self, world):
        """The boards waiting in the whisper pool (P18)."""
        return world.m("nui_whisper").POOL.boards()

    def assert_one_empty_board_waits(self, world):
        """P18: a dialog's board went to the pool, hidden and emptied, and is
        the only document left."""
        (board,) = self.waiting(world)
        self.assertEqual(world.documents(), [DOCUMENT])
        self.assertFalse(board.is_visible())
        self.assertEqual((board.model["feed_key"], board.model["target"], board.model["lines_on"]), (0, "", []))
        self.assertEqual((board.fields.get(INPUT, ""), board.fields.get(TARGET, "")), ("", ""))
        self.assertIs(board._owner, world.m("nui_hud").NO_OWNER)
        return board

    def run_both(self, flow):
        results = []
        for world in self.worlds():
            mark = world.mark()
            with world.game, w4.quiet():
                flow(world)
            results.append((world.effects_since(mark, EFFECTS), world))
        return results


class Flows(WhisperTest):
    def test_opening_a_partner_s_dialog_makes_legacy_s_calls_and_attaches_its_feed(self):
        def flow(world):
            world.dialog = world.interface.OpenWhisperDialog("Alice")
        (legacy, _), (novaui, world) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertIn(("chat.CreateWhisper", ("Alice",)), novaui)
        self.assertIn(("chat.SetWhisperBoxSize", ("Alice", 240, 110)), novaui)
        board = w4.board(world.dialog)
        self.assertEqual((board.model["target"], board.model["feed_key"]), ("Alice", 1))
        self.assertEqual((board.model["width"], board.model["height"], board.model["input_max"]), (300.0, 200.0, 99))
        self.assertEqual(board.placement, ("position", 0.0, 0.0, (0.0, 0.0)), "the Interface's first cascade place")
        self.assertEqual(board.focused, INPUT, "OpenWhisperDialog focuses the input")
        self.assertEqual(world.game.calls("nuigame.WhisperAttach"), [("nuigame.WhisperAttach", ("Alice",))])

    def test_the_block_button_follows_the_block_list_and_switches_its_label(self):
        """NOVA-47 (uiwhisper.py RefreshBlockButton, BlockPlayer): Block for a
        partner, Unblock for one on the client's block list; a press sends
        the change and shows the other label at once; no button without a
        partner."""
        for blocked, packet in ((False, "net.SendBlockAddPacket"), (True, "net.SendBlockRemovePacket")):
            def setup(game, blocked=blocked):
                if blocked:
                    game.w4["messenger"]["blocked"].append("Alice")
            results = []
            for nui_on in (False, True):
                world = self.world(nui_on, setup=setup)
                with world.game, w4.quiet():
                    dialog = world.interface.OpenWhisperDialog("Alice")
                    before = self.block_view(world, dialog)
                    mark = world.mark()
                    if nui_on:
                        w4.press(dialog, "block_press", 0)
                    else:
                        dialog.blockButton.click()
                    results.append((before, world.effects_since(mark, EFFECTS), self.block_view(world, dialog)))
            (legacy_before, legacy, legacy_after), (novaui_before, novaui, novaui_after) = results
            with self.subTest(blocked=blocked):
                self.assertEqual((novaui_before, novaui, novaui_after), (legacy_before, legacy, legacy_after))
                self.assertEqual(novaui_before, (True, blocked))
                self.assertEqual(novaui, [(packet, ("Alice",))])
                self.assertEqual(novaui_after, (True, not blocked))
        world = self.world(True)
        with world.game, w4.quiet():
            dialog = world.interface.OpenWhisperDialogWithoutTarget()
        self.assertFalse(w4.board(dialog).model["block_shown"])

    @staticmethod
    def block_view(world, dialog):
        """(shown, Unblock's label): the board's, or the legacy button's."""
        if world.nui_on:
            model = w4.board(dialog).model
            return (model["block_shown"], model["blocked"])
        unblock = world.m("uiScriptLocale").UNBLOCK_PLAYER
        return (bool(dialog.blockButton.IsShow()), dialog.blockButton.GetText() == unblock)

    def test_the_partner_s_details_show_the_server_s_answer(self):
        """NOVA-48 (uiwhisper.py SetTargetDetails): hidden until the server's
        first answer, then the online or offline mark, and the language's
        flag while online; choosing a partner asks for its details at once."""
        world = self.world(True)
        with world.game, w4.quiet():
            dialog = world.interface.OpenWhisperDialog("Alice")
            model = w4.board(dialog).model
            self.assertEqual((model["online_shown"], model["flag_shown"]), (False, False))
            dialog.SetTargetDetails(1, "en")
            model = w4.board(dialog).model
            self.assertEqual((model["online_shown"], model["online"], model["flag_shown"], model["flag_src"]),
                             (True, True, True, "/locale/common/ui/flag/32/en.tga"))
            dialog.SetTargetDetails(0, "en")
            model = w4.board(dialog).model
            self.assertEqual((model["online_shown"], model["online"], model["flag_shown"]), (True, False, False))
            dialog.SetTargetDetails(1, "xx")
            self.assertFalse(w4.board(dialog).model["flag_shown"], "a language without a flag file shows none")

        def flow(world):
            dialog = world.interface.OpenWhisperDialogWithoutTarget()
            if world.nui_on:
                w4.board(dialog).insert_text(TARGET, "Bob")
                w4.board(dialog).key(TARGET, world.m("nui").KEY_RETURN)
            else:
                dialog.titleNameEdit.SetText("Bob")
                dialog.titleNameEdit.eventReturn()
        (legacy, _), (novaui, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertIn(("net.SendWhisperDetailsPacket", ("Bob",)), novaui)

    def test_enter_and_the_button_send_and_clear_the_input(self):
        def flow(world):
            dialog = world.interface.OpenWhisperDialog("Alice")
            self.type_and(world, dialog, "hello", "enter")
            if world.nui_on:
                w4.board(dialog).insert_text(INPUT, "again")
                w4.press(dialog, "send_press", 0)
            else:
                dialog.chatLine.SetText("again")
                dialog.sendButton.click()
            self.type_and(world, dialog, "", "enter")
            world.dialog = dialog
        (legacy, _), (novaui, world) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual([call for call in novaui if call[0] == "net.SendWhisperPacket"],
                         [("net.SendWhisperPacket", ("Alice", "hello")), ("net.SendWhisperPacket", ("Alice", "again"))])
        self.assertIn(("chat.AppendWhisper", (0, "Alice", "Tester : hello")), novaui)
        self.assertEqual(w4.board(world.dialog).get_value(INPUT), "")

    def test_enter_keeps_the_key_so_no_line_break_is_typed(self):
        world = self.world(True)
        with world.game, w4.quiet():
            dialog = world.interface.OpenWhisperDialog("Alice")
            self.assertTrue(self.type_and(world, dialog, "hi", "enter"))

    @staticmethod
    def textarea_input(board, text):
        """Text input as RmlUi's textarea takes it at its caret (the stand-in
        board's insert_text treats a line break as a single-line field's
        Enter): Windows' WM_CHAR of a kept Enter reaches the field this way,
        after the keydown's send."""
        current = board.fields.get(INPUT, "")
        at = max(0, min(board.carets.get(INPUT, len(current)), len(current)))
        board.fields[INPUT] = current[:at] + text + current[at:]
        board.carets[INPUT] = at + len(text)
        # The document's data-event-change="input_change(ev.value)".
        board.fire("input_change", board.fields[INPUT])

    def test_the_line_break_enter_types_never_stays_in_the_input(self):
        """WH-02-cleared (validation, N, C and Y): the send cleared the
        field, then the key's text input put "\n" in it, and the next
        whisper went out as "\n<text>". The input holds no line break, as
        legacy's edit line; the caret stays after what was typed."""
        def setup(game):
            game.answer("net", "IsInsultIn", lambda text: "bad" in text)
        world = self.world(True, setup=setup)
        with world.game, w4.quiet():
            dialog = world.interface.OpenWhisperDialog("Alice")
            board = w4.board(dialog)
            mark = world.mark()
            self.assertTrue(self.type_and(world, dialog, "first", "enter"))
            self.textarea_input(board, "\n")
            self.assertEqual((board.get_value(INPUT), dialog.chatLine.GetText(), board.carets[INPUT]), ("", "", 0))
            self.assertTrue(self.type_and(world, dialog, "second", "enter"))
            self.textarea_input(board, "\n")
            # Enter on the empty field: nothing to send, and no line break.
            self.assertTrue(self.type_and(world, dialog, "", "enter"))
            self.textarea_input(board, "\n")
            self.assertEqual(board.get_value(INPUT), "")
            # A refused line stays, without the line break, the caret at its end.
            self.assertTrue(self.type_and(world, dialog, "bad word", "enter"))
            self.textarea_input(board, "\n")
            self.assertEqual((board.get_value(INPUT), board.carets[INPUT]), ("bad word", 8))
            # A line break typed inside the text (a paste): the caret after it.
            board.set_value(INPUT, "abcd", caret=2)
            board.fire("input_change", "abcd")
            self.textarea_input(board, "x\ny")
            self.assertEqual((board.get_value(INPUT), board.carets[INPUT], dialog.chatLine.GetText()), ("abxycd", 4, "abxycd"))
        self.assertEqual(world.calls_since(mark, "net.SendWhisperPacket"),
                         [("net.SendWhisperPacket", ("Alice", "first")), ("net.SendWhisperPacket", ("Alice", "second"))])

    def test_a_restored_draft_comes_back_once(self):
        """The kept state goes to the dialog that reopens it: a dialog the
        Interface replaces through the dialog without a partner
        (RegisterTemporaryWhisperDialog destroys it, no minimize) does not
        bring back a draft sent since."""
        world = self.world(True)
        with world.game, w4.quiet():
            dialog = world.interface.OpenWhisperDialog("Alice")
            self.type_and(world, dialog, "hi", "escape")
            dialog = world.interface.ShowWhisperDialog("Alice")
            self.assertEqual(w4.board(dialog).get_value(INPUT), "hi")
            mark = world.mark()
            self.type_and(world, dialog, "", "enter")
            without = world.interface.OpenWhisperDialogWithoutTarget()
            w4.board(without).insert_text(TARGET, "Alice")
            w4.board(without).key(TARGET, world.m("nui").KEY_RETURN)
        self.assertEqual(world.calls_since(mark, "net.SendWhisperPacket"), [("net.SendWhisperPacket", ("Alice", "hi"))])
        self.assertIs(world.interface.dialogs["Alice"], without)
        self.assertEqual(w4.board(without).get_value(INPUT), "")
        self.assertEqual(without.chatLine.GetText(), "")

    def test_an_insult_is_refused_with_legacy_s_line(self):
        def setup(game):
            game.answer("net", "IsInsultIn", lambda text: "bad" in text)
        results = []
        for nui_on in (False, True):
            world = self.world(nui_on, setup=setup)
            with world.game, w4.quiet():
                dialog = world.interface.OpenWhisperDialog("Alice")
                mark = world.mark()
                self.type_and(world, dialog, "bad word", "enter")
            results.append(world.effects_since(mark, EFFECTS))
        legacy, novaui = results
        self.assertEqual(novaui, legacy)
        self.assertFalse([call for call in novaui if call[0] == "net.SendWhisperPacket"])
        self.assertEqual([call[0] for call in novaui if call[0].startswith("chat.")], ["chat.AppendChat"])

    def test_escape_minimizes_to_an_edge_button_and_the_draft_comes_back(self):
        def flow(world):
            dialog = world.interface.OpenWhisperDialog("Alice")
            if world.nui_on:
                w4.fire(dialog, "resized", 400, 260)
                w4.fire(dialog, "scroll", 0.4)
            else:
                dialog.resizeButton.drag_to(380, 240)
                dialog.scrollBar.drag_to(0.4)
            self.type_and(world, dialog, "half a sent", "escape")
            world.minimized = dict(world.interface.dialogs)
            world.kept = dict(world.m("nui_whisper").STATE.get("Alice", {})) if world.nui_on else None
            world.dialog = world.interface.ShowWhisperDialog("Alice")
        (legacy, a), (novaui, world) = self.run_both(flow)
        self.assertEqual(a.minimized, {})
        self.assertEqual(world.minimized, {})
        self.assertEqual(a.interface.buttons, [])
        state = world.kept
        self.assertEqual((state["draft"], state["width"], state["height"], state["pos"]), ("half a sent", 400, 260, 0.4))
        self.assertNotIn("Alice", world.m("nui_whisper").STATE, "the reopened dialog took the kept state")
        board = w4.board(world.dialog)
        self.assertEqual(board.get_value(INPUT), "half a sent", "D8: the draft is kept")
        self.assertEqual((board.model["width"], board.model["height"], board.model["pos"]), (400.0, 260.0, 0.4))
        legacy_calls = [call for call in legacy if call[0] != "chat.SetWhisperPosition"]
        novaui_calls = [call for call in novaui if call[0] != "chat.SetWhisperPosition"]
        self.assertEqual(novaui_calls[:len(legacy_calls) - 2], legacy_calls[:-2],
                         "the same calls up to the reopen, which NovaUI sizes as it was")
        self.assertEqual(novaui[-1], ("chat.SetWhisperPosition", ("Alice", 0.4)), "the kept scroll")

    def test_close_drops_the_kept_state_and_clears_the_store(self):
        def flow(world):
            dialog = world.interface.OpenWhisperDialog("Alice")
            self.type_and(world, dialog, "draft", "escape")
            dialog = world.interface.ShowWhisperDialog("Alice")
            if world.nui_on:
                w4.press(dialog, "close_press", 0)
            else:
                dialog.closeButton.click()
        (legacy, a), (novaui, world) = self.run_both(flow)
        self.assertIn(("chat.ClearWhisper", ("Alice",)), legacy)
        self.assertIn(("chat.ClearWhisper", ("Alice",)), novaui)
        self.assertNotIn("Alice", world.m("nui_whisper").STATE)
        self.assertEqual(world.interface.dialogs, {})
        self.assert_one_empty_board_waits(world)
        self.assertEqual(world.game.calls("nuigame.WhisperDetach")[-1], ("nuigame.WhisperDetach", (1,)))

    def test_the_dialog_without_a_partner_takes_a_name(self):
        for how in ("enter", "ok"):
            def flow(world, how=how):
                dialog = world.interface.OpenWhisperDialogWithoutTarget()
                world.before = dict(w4.board(dialog).model) if world.nui_on else None
                world.focus_before = w4.board(dialog).focused if world.nui_on else None
                if world.nui_on:
                    w4.board(dialog).insert_text(TARGET, "Dana")
                    if how == "enter":
                        w4.board(dialog).key(TARGET, world.m("nui").KEY_RETURN)
                    else:
                        w4.press(dialog, "accept_press", 0)
                else:
                    dialog.titleNameEdit.SetText("Dana")
                    if how == "enter":
                        dialog.titleNameEdit.eventReturn()
                    else:
                        dialog.acceptButton.click()
                world.dialog = dialog
            (legacy, _), (novaui, world) = self.run_both(flow)
            with self.subTest(how=how):
                self.assertEqual(novaui, legacy)
                self.assertEqual((world.before["editing_target"], world.before["accept_shown"],
                                  world.before["minimize_shown"], world.before["feed_key"]), (True, True, False, 0))
                self.assertEqual(world.focus_before, TARGET)
                model = w4.board(world.dialog).model
                self.assertEqual((model["editing_target"], model["accept_shown"], model["minimize_shown"], model["target"]),
                                 (False, False, True, "Dana"))
                self.assertEqual(model["feed_key"], 1)
                self.assertIs(world.interface.dialogs["Dana"], world.dialog)

    def test_an_empty_name_and_escape_close_the_dialog_without_a_partner(self):
        for how in ("empty", "escape"):
            def flow(world, how=how):
                dialog = world.interface.OpenWhisperDialogWithoutTarget()
                if world.nui_on:
                    nui = world.m("nui")
                    w4.board(dialog).key(TARGET, nui.KEY_RETURN if how == "empty" else nui.KEY_ESCAPE)
                elif how == "empty":
                    dialog.titleNameEdit.eventReturn()
                else:
                    dialog.titleNameEdit.eventEscape()
            (legacy, a), (novaui, world) = self.run_both(flow)
            with self.subTest(how=how):
                self.assertEqual(novaui, legacy)
                self.assertIn(("chat.ClearWhisper", (0,)), novaui)
                self.assertIsNone(world.interface.without)
                self.assert_one_empty_board_waits(world)

    def test_the_gm_look_shows_the_mark(self):
        world = self.world(True)
        with world.game, w4.quiet():
            dialog = world.interface.OpenWhisperDialog("[SA]Admin")
            dialog.SetGameMasterLook()
        self.assertTrue(w4.board(dialog).model["gm"])
        self.assertTrue(w4.board(dialog).model["gm_mark_src"].endswith("/effect/ymirred.tga"))

    def test_a_link_press_shows_its_tooltip_or_pastes_it_with_alt(self):
        link = "item:13:0:0:0:0"
        for alt in (False, True):
            def setup(game, alt=alt):
                if alt:
                    game.pressed.add(game.modules["app"].DIK_LALT)
                game.answer("chat", "GetLinkFromHyperlink", lambda found: "|Hitem:13|h[Sword]|h")
                game.hyperlink = link
            results = []
            for nui_on in (False, True):
                world = self.world(nui_on, setup=setup)
                with world.game, w4.quiet():
                    dialog = world.interface.OpenWhisperDialog("Alice")
                    mark = world.mark()
                    if nui_on:
                        w4.fire(dialog, "link", link)
                    else:
                        dialog.OnMouseLeftButtonDown()
                results.append((world.effects_since(mark, EFFECTS), world.interface.links))
            (legacy, a_links), (novaui, b_links) = results
            with self.subTest(alt=alt):
                self.assertEqual(novaui, legacy)
                self.assertEqual(b_links, a_links)
                self.assertEqual(b_links, [] if alt else [link])
                if alt:
                    self.assertIn(("ime.PasteString", ("|Hitem:13|h[Sword]|h",)), novaui)

    def test_the_scroll_and_the_resize_reach_the_store_as_legacy_s(self):
        def flow(world):
            dialog = world.interface.OpenWhisperDialog("Alice")
            if world.nui_on:
                w4.fire(dialog, "scroll", 0.4)
                w4.fire(dialog, "scroll", 0.403)
                w4.fire(dialog, "resized", 400, 260)
            else:
                dialog.scrollBar.drag_to(0.4)
                dialog.resizeButton.drag_to(380, 240)
            world.dialog = dialog
        (legacy, _), (novaui, world) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertIn(("chat.SetWhisperPosition", ("Alice", 0.4)), novaui)
        self.assertIn(("chat.SetWhisperBoxSize", ("Alice", 350, 170)), novaui)
        model = w4.board(world.dialog).model
        self.assertEqual((model["width"], model["height"], model["input_max"], model["pos"]), (400.0, 260.0, 147, 1.0))

    def test_the_board_s_scroll_echo_at_its_load_moves_nothing(self):
        """In the client, the range that data-attr-value="pos" sets to its
        first value dispatches change as the document loads (RmlUi's
        WidgetSlider, pos against the slider's 0), and _nui runs the handler
        as soon as the load returns. That reaches the probe's board too,
        which nui_end() makes in the constructor, before the Interface's
        LoadDialog makes the scroll bar's proxy (the integration smoke's
        SMK-N traceback). Since P18 the range is also made again at each show
        of a pooled board (its data-for wrapper, lines_on), and echoes the
        position the dialog restores. Neither the probe's echo nor a shown
        board's (the kept position of a restored dialog) may raise or
        scroll."""
        runs = []
        for echo in (False, True):
            world = self.world(True)
            echoes, errors = [], []
            if echo:
                module = world.m("nui_whisper")
                board_class = module._WhisperBoard
                board_init = board_class.__init__
                restore = module.WhisperDialog._restore_board

                def fire_echo(board, pos, echoes=echoes, errors=errors):
                    echoes.append(pos)
                    try:
                        board.fire("scroll", pos)
                    except Exception as error:  # _nui logs a handler's error and goes on
                        errors.append(error)

                def init(board, owner, model, board_init=board_init):
                    board_init(board, owner, model)
                    if board._doc:
                        fire_echo(board, model["pos"])

                def restore_board(dialog, board, restore=restore):
                    restore(dialog, board)
                    fire_echo(board, board.model["pos"])
                board_class.__init__ = init
                module.WhisperDialog._restore_board = restore_board
            mark = world.mark()
            with world.game, w4.quiet():
                dialog = world.interface.OpenWhisperDialog("Alice")
                w4.fire(dialog, "scroll", 0.4)
                self.type_and(world, dialog, "", "escape")
                world.interface.ShowWhisperDialog("Alice")
            runs.append((world.effects_since(mark, EFFECTS), echoes, errors))
        (plain, _, _), (echoed, echoes, errors) = runs
        self.assertEqual(errors, [])
        self.assertEqual(echoes, [1.0, 1.0, 0.4], "the probe's load, the first dialog's show, the restored one's show "
                                                  "(one board: the probe's, from the pool)")
        self.assertEqual(echoed, plain)

    def test_the_wheel_scrolls_three_lines_a_notch(self):
        world = self.world(True)
        with world.game, w4.quiet():
            dialog = world.interface.OpenWhisperDialog("Alice")
            world.game.w4["whisper"]["Alice"] = [(0, "line %d" % i) for i in range(20)]
            mark = world.mark()
            w4.fire(dialog, "wheel", -1)
        # 20 lines, 8 rows: the window ends at int(13 * pos) + 6, so a line is 1 / 13.
        calls = world.calls_since(mark, "chat.SetWhisperPosition")
        self.assertEqual(len(calls), 1)
        self.assertAlmostEqual(calls[0][1][1], 1.0 - 3.0 / 13.0)
        self.assertAlmostEqual(w4.board(dialog).model["pos"], 1.0 - 3.0 / 13.0)

    def test_three_partners_show_at_once_each_with_its_own_model_and_feed(self):
        world = self.world(True)
        with world.game, w4.quiet():
            dialogs = [world.interface.OpenWhisperDialog(name) for name in ("Alice", "Bob", "Carl")]
        boards = [w4.board(dialog) for dialog in dialogs]
        self.assertEqual(len(set(board.MODEL for board in boards)), 3)
        self.assertTrue(all(board.MODEL.startswith("whisper_") for board in boards))
        self.assertEqual([board.model["feed_key"] for board in boards], [1, 2, 3])
        self.assertEqual([board.placement[1:3] for board in boards], [(0.0, 0.0), (30.0, 30.0), (60.0, 60.0)])
        with world.game, w4.quiet():
            self.type_and(world, dialogs[1], "", "escape")
        self.assertIsNotNone(w4.board(dialogs[0]))
        self.assertIsNotNone(w4.board(dialogs[2]))
        self.assertEqual(world.interface.buttons, ["Bob"])
        self.assertEqual(world.game.calls("nuigame.WhisperDetach"), [("nuigame.WhisperDetach", (2,))])

    def test_a_field_s_focus_holds_wnd_mgr_s_and_the_minimize_lets_it_go(self):
        world = self.world(True)
        with world.game, w4.quiet():
            dialog = world.interface.OpenWhisperDialog("Alice")
            proxy_window = dialog.focusProxy._window
            self.assertTrue(proxy_window.IsFocus(), "the input's focus takes wndMgr's")
            self.type_and(world, dialog, "", "escape")
        self.assertFalse(proxy_window.IsFocus())


class Facade(WhisperTest):
    def make(self, world):
        with world.game, w4.quiet():
            return world.make("whisper", "uiWhisper", "WhisperDialog", "nui_whisper.WhisperDialog", lambda n: None,
                              lambda n: None)

    def test_the_class_the_methods_and_no_per_frame_python(self):
        world = self.world(True)
        window = self.make(world)
        legacy_class = world.m("uiWhisper").WhisperDialog
        self.assertIsInstance(window, legacy_class)
        self.assertTrue(window.NUI_FACADE)
        self.assertIsNone(type(window).OnUpdate)
        self.assertIsNone(type(window).OnRender)
        for name in ("BindInterface", "LoadDialog", "OpenWithTarget", "OpenWithoutTarget", "SetPosition", "Show", "SetTop",
                     "SetGameMasterLook", "Destroy"):
            self.assertTrue(callable(getattr(window, name)), name)
        for name, member in inspect.getmembers(legacy_class, inspect.isfunction):
            if name in ("OnUpdate", "OnRender"):
                continue
            self.assertEqual(len(inspect.signature(getattr(type(window), name)).parameters),
                             len(inspect.signature(member).parameters), name)
        module = world.m("nui_whisper")
        self.assertTrue(module._WhisperBoard.INSTANCED)
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ == "nui_whisper":
                for attr in ("OnUpdate", "OnRender"):
                    self.assertFalse(callable(getattr(cls, attr, None)), "%s.%s" % (name, attr))

    def test_make_builds_legacy_with_the_flag_off_or_an_older_exe(self):
        world = self.world(False)
        self.assertIs(type(self.make(world)), world.m("uiWhisper").WhisperDialog)
        world = self.world(True, engine_4=False)
        self.assertIs(type(self.make(world)), world.m("uiWhisper").WhisperDialog)

    def test_the_probe_s_board_waits_for_the_first_show_and_the_0_by_0_window(self):
        """P18: the probe's board is not destroyed; it waits, hidden, in the
        pool for the show that follows, so a first open loads once."""
        world = self.world(True)
        window = self.make(world)
        with world.game, w4.quiet():
            window.LoadDialog()
        self.assertIsNone(w4.board(window))
        self.assertEqual(len(self.waiting(world)), 1)
        self.assertFalse(self.waiting(world)[0].is_visible())
        self.assertEqual(world.documents(), [DOCUMENT])
        self.assertEqual(window.GetWidth(), 300, "the dialog's own size, as legacy reads it")
        legacy_width = world.m("ui").ScriptWindow.GetWidth(window)
        self.assertEqual(legacy_width, 0, "the legacy window stays 0 x 0")
        self.assertIn("float", window.flags)

    def test_the_phase_end_drops_the_kept_drafts(self):
        world = self.world(True)
        module = world.m("nui_whisper")
        module.STATE["Alice"] = {"draft": "x"}
        self.assertEqual(module.end_phase(), 0)
        self.assertEqual(module.STATE, {})
        self.assertIn("nui_whisper", world.m("nui_windows").PHASE_SCOPED)

    def test_every_fixture_has_the_model_s_keys_and_kinds(self):
        world = self.world(True)
        window = self.make(world)
        kinds = w4.model_kinds(window.nui_model())
        for variant in ("", "foundation", "without-target", "gm", "small"):
            self.assertEqual(w4.fixture_keys(window, "whisper", variant), kinds, variant)

    def test_the_interface_makes_both_dialogs_through_make(self):
        text = w4.read(os.path.join(w4.ROOT, "interfacemodule.py"))
        line = ('nui_windows.make("whisper", uiWhisper.WhisperDialog, "nui_whisper.WhisperDialog", '
                'self.MinimizeWhisperDialog, self.CloseWhisperDialog)')
        self.assertEqual(text.count(line), 2)


class Pool(WhisperTest):
    """P18 (Eddy: keep the slow-opening windows loaded, with no memory
    growth): the dialogs' boards are pooled. A closed or minimized dialog's
    board waits, hidden and emptied, for the next dialog; at most POOL_BOUND
    wait; a waiting board never shows another conversation's text or draft;
    the phase's end unloads them."""

    def test_the_bound_is_four(self):
        module = self.world(True).m("nui_whisper")
        self.assertEqual(module.POOL_BOUND, 4)
        self.assertEqual(module.POOL.bound, 4)

    def test_a_closed_dialog_s_board_shows_the_next_partner_with_none_of_the_draft(self):
        world = self.world(True)
        with world.game, w4.quiet():
            alice = world.interface.OpenWhisperDialog("Alice")
            board = w4.board(alice)
            board.insert_text(INPUT, "a secret for Alice")
            w4.press(alice, "close_press", 0)
            self.assert_one_empty_board_waits(world)
            loads = world.m("nui_whisper").POOL.loads
            bob = world.interface.OpenWhisperDialog("Bob")
            mark = world.mark()
            self.type_and(world, bob, "hi Bob", "enter")
        self.assertIs(w4.board(bob), board, "the waiting board: no load")
        self.assertEqual(world.m("nui_whisper").POOL.loads, loads)
        self.assertEqual((board.model["target"], board.model["feed_key"], board.model["lines_on"]), ("Bob", 2, [1]))
        self.assertEqual(board.get_value(INPUT), "", "sent; nothing of Alice's draft")
        self.assertEqual(world.calls_since(mark, "net.SendWhisperPacket"), [("net.SendWhisperPacket", ("Bob", "hi Bob"))])
        self.assertEqual(board.focused, INPUT, "Bob's input has the focus, as OpenWhisperDialog asks")

    def test_a_minimized_draft_comes_back_from_the_state_not_from_a_board(self):
        world = self.world(True)
        with world.game, w4.quiet():
            alice = world.interface.OpenWhisperDialog("Alice")
            self.type_and(world, alice, "half for Alice", "escape")
            board = self.assert_one_empty_board_waits(world)
            bob = world.interface.OpenWhisperDialog("Bob")
            self.assertIs(w4.board(bob), board)
            self.assertEqual(board.get_value(INPUT), "", "Bob's dialog: none of Alice's draft")
            alice = world.interface.ShowWhisperDialog("Alice")
        alice_board = w4.board(alice)
        self.assertIsNot(alice_board, board, "the pool was empty: Alice's board loads")
        self.assertEqual(alice_board.get_value(INPUT), "half for Alice", "D8: the draft from the kept state")
        self.assertEqual(board.get_value(INPUT), "")
        self.assertEqual((alice_board.model["target"], board.model["target"]), ("Alice", "Bob"))

    def test_the_partner_field_of_a_dialog_without_a_partner_starts_empty_on_a_pooled_board(self):
        world = self.world(True)
        with world.game, w4.quiet():
            without = world.interface.OpenWhisperDialogWithoutTarget()
            board = w4.board(without)
            board.insert_text(TARGET, "Mallory")
            board.key(TARGET, world.m("nui").KEY_ESCAPE)
            self.assertIsNone(world.interface.without)
            self.assert_one_empty_board_waits(world)
            again = world.interface.OpenWhisperDialogWithoutTarget()
        self.assertIs(w4.board(again), board)
        self.assertEqual(board.get_value(TARGET), "")
        self.assertEqual(board.model["editing_target"], True)

    def test_the_gm_look_and_the_place_are_the_dialog_s_own(self):
        world = self.world(True)
        world.game.w4.setdefault("gm_names", set())
        with world.game, w4.quiet():
            alice = world.interface.OpenWhisperDialog("Alice")
            alice.SetGameMasterLook()
            board = w4.board(alice)
            self.assertTrue(board.model["gm"])
            w4.press(alice, "close_press", 0)
            self.assertFalse(board.model["gm"])
            bob = world.interface.OpenWhisperDialog("Bob")
        self.assertIs(w4.board(bob), board)
        self.assertFalse(board.model["gm"])
        self.assertEqual(board.placement, ("position", 30.0, 30.0, (0.0, 0.0)), "Bob's cascade place")

    def test_never_more_than_the_bound_wait_and_six_names_go_past_it(self):
        """The memory soak's step: six partners at once (six documents), all
        closed: four wait, two unload; then six names one after another, each
        closed: the pool never holds more than four and loads nothing."""
        world = self.world(True)
        module = world.m("nui_whisper")
        names = ["Name%d" % i for i in range(6)]
        with world.game, w4.quiet():
            dialogs = [world.interface.OpenWhisperDialog(name) for name in names]
            self.assertEqual(len(world.documents()), 6)
            for dialog in dialogs:
                w4.press(dialog, "close_press", 0)
            self.assertEqual(len(self.waiting(world)), 4)
            self.assertEqual(len(world.documents()), 4, "the fifth and sixth closed boards unloaded")
            loads = module.POOL.loads
            for name in names:
                dialog = world.interface.OpenWhisperDialog(name)
                self.assertLessEqual(len(self.waiting(world)), 4)
                self.type_and(world, dialog, "", "escape")
        self.assertEqual(module.POOL.loads, loads, "every later open took a waiting board")
        self.assertEqual(module.POOL.most, 4)
        self.assertLessEqual(len(world.documents()), 4)
        stats = world.m("nui_hud").pool_stats()["whisper"]
        self.assertEqual((stats["bound"], stats["most"]), (4, 4))

    def test_the_phase_end_unloads_the_waiting_boards(self):
        world = self.world(True)
        with world.game, w4.quiet():
            for name in ("Alice", "Bob"):
                dialog = world.interface.OpenWhisperDialog(name)
            for name in ("Alice", "Bob"):
                w4.press(world.interface.dialogs[name], "close_press", 0)
            self.assertEqual(len(world.documents()), 2)
            self.assertEqual(world.m("nui_windows").end_phase(), 2)
        self.assertEqual(world.documents(), [])
        self.assertEqual(self.waiting(world), [])

    def test_a_waiting_board_s_events_reach_no_dialog(self):
        world = self.world(True)
        with world.game, w4.quiet():
            alice = world.interface.OpenWhisperDialog("Alice")
            board = w4.board(alice)
            w4.press(alice, "close_press", 0)
            mark = world.mark()
            board.fire("scroll", 0.2)
            board.fire("input_change", "x")
            board.fire("close_press", 0)
            board.fire("board_press", 0)
            board.key(INPUT, world.m("nui").KEY_RETURN)
        self.assertEqual(world.effects_since(mark, EFFECTS), [])


if __name__ == "__main__":
    unittest.main()
