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
            world.dialog = world.interface.ShowWhisperDialog("Alice")
        (legacy, a), (novaui, world) = self.run_both(flow)
        self.assertEqual(a.minimized, {})
        self.assertEqual(world.minimized, {})
        self.assertEqual(a.interface.buttons, [])
        state = world.m("nui_whisper").STATE["Alice"]
        self.assertEqual((state["draft"], state["width"], state["height"], state["pos"]), ("half a sent", 400, 260, 0.4))
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
        self.assertNotIn(DOCUMENT, world.documents())
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
                self.assertNotIn(DOCUMENT, world.documents())

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

    def test_on_demand_and_the_0_by_0_window(self):
        world = self.world(True)
        window = self.make(world)
        with world.game, w4.quiet():
            window.LoadDialog()
        self.assertNotIn(DOCUMENT, world.documents())
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


if __name__ == "__main__":
    unittest.main()
