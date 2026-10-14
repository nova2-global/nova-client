"""Tests for assets/root/nui_proxies.py, the widget proxies of the Wave 3b
windows (P14 spec 6.0, 6.4): python3 -B -m unittest nui_proxies_test (from
tools/). Plain CPython over nui_game_support's stand-ins."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402


class ProxiesTest(unittest.TestCase):
    def setUp(self):
        self.game = support.Game()
        support.install_wave2b_ui(self.game)
        support.install_wave3a_ui(self.game)
        support.install_wave3b_ui(self.game)
        self.game.load_standard()
        self.m = self.game.load("nui_proxies", "nui_proxies.py")
        self.game.__enter__()
        self.addCleanup(self.game.__exit__)


class Text(ProxiesTest):
    def test_set_text_reaches_the_window_and_get_text_answers_it(self):
        seen = []
        text = self.m.TextProxy(seen.append)
        text.SetText("1.999.999.999 Yang")
        text.SetText(None)
        self.assertEqual(seen, ["1.999.999.999 Yang", ""])
        self.assertEqual(text.GetText(), "")
        text.Hide()
        self.assertFalse(text.IsShow())
        text.SetPackedFontColor(-1)
        self.assertEqual(text.color, 0xFFFFFFFF, "a packed color as an unsigned value")
        with self.assertRaises(AttributeError):
            text.SetOutline(True)


class Button(ProxiesTest):
    def test_a_click_calls_the_stored_event_with_its_arguments_while_enabled(self):
        pressed = []
        changes = []
        button = self.m.ButtonProxy(changes.append)
        button.SetEvent(lambda page: pressed.append(page), 3)
        button.click()
        button.Disable()
        button.click()
        self.assertEqual(pressed, [3], "a disabled button calls nothing")
        button.Enable()
        button.Down()
        self.assertTrue(button.IsDown())
        button.SetUp()
        self.assertFalse(button.IsDown())
        self.assertEqual(len(changes), 4)
        button.SetToolTipText("@ui.MALL_TITLE")
        self.assertEqual(button.tooltip, "@ui.MALL_TITLE")
        button.Destroy()
        button.click()
        self.assertEqual(pressed, [3], "a destroyed button has no event")


class Image(ProxiesTest):
    def test_load_image_is_recorded_and_the_size_comes_from_a_hidden_legacy_image(self):
        seen = []
        image = self.m.ImageProxy(seen.append)
        self.assertEqual((image.GetWidth(), image.GetHeight()), (0, 0), "no image")
        image.LoadImage("icon/item/00010.tga")
        self.assertEqual(seen, ["icon/item/00010.tga"])
        self.assertEqual(image.GetImageFileName(), "icon/item/00010.tga")
        self.assertEqual((image.GetWidth(), image.GetHeight()), (0, 0), "the stand-in image box has no size")


class Board(ProxiesTest):
    def test_sizes_are_kept_for_legacy_code_that_reads_them_and_the_close_event(self):
        closed = []
        board = self.m.BoardProxy(184, 332)
        board.SetSize(board.GetWidth(), 76 + 32 * 3)
        self.assertEqual((board.GetWidth(), board.GetHeight()), (184, 172))
        board.SetWidth(200)
        self.assertEqual(board.GetWidth(), 200)
        board.SetCloseEvent(lambda: closed.append(1))
        board.close()
        self.assertEqual(closed, [1])


class Question(ProxiesTest):
    def test_the_refine_question_window_opens_the_kits_question_with_legacys_texts_and_events(self):
        accepted = []
        question = self.m.QuestionWindowProxy()
        question.GetChild("message1").SetText("REFINE_DESTROY_WARNING")
        question.GetChild("message2").SetText("REFINE_WARNING2")
        question.GetChild("accept").SetEvent(lambda: accepted.append("accept"))
        question.GetChild("cancel").SetEvent(question.Hide)
        self.assertRaises(KeyError, question.GetChild, "board")
        question.SetTop()
        question.Show()
        self.assertTrue(question.IsShow())
        dialog = self.game.dialogs[-1]
        self.assertEqual(dialog.texts, ["REFINE_DESTROY_WARNING", "REFINE_WARNING2"])
        self.assertIn(("uiCommon.QuestionDialog2.Open", ("REFINE_DESTROY_WARNING", "REFINE_WARNING2", "")), self.game.log)
        dialog.accept()
        self.assertEqual(accepted, ["accept"])
        dialog.cancel()
        self.assertFalse(question.IsShow())
        self.assertFalse(dialog.is_open)
        question.Show()
        self.assertIs(self.game.dialogs[-1], dialog, "one dialog, opened again")
        question.Destroy()
        self.assertIsNone(question.dialog)


if __name__ == "__main__":
    unittest.main()


# --- Wave 3c (P15) ---

class WindowAndToggle(ProxiesTest):
    def test_a_window_records_its_place_and_reports_its_shown_state(self):
        seen = []
        window = self.m.WindowProxy(seen.append)
        window.Hide()
        window.Show()
        window.SetPosition(109, 34)
        window.SetSize(10, 20)
        self.assertEqual(seen, [False, True])
        self.assertEqual((window.GetLocalPosition(), window.size, window.IsShow()), ((109, 34), (10, 20), True))
        with self.assertRaises(AttributeError):
            window.LoadImage("x.sub")

    def test_a_toggle_goes_down_and_up_as_ctoggle_button(self):
        events, changes = [], []
        toggle = self.m.ToggleButtonProxy(changes.append)
        toggle.SetToggleDownEvent(lambda: events.append("down"))
        toggle.SetToggleUpEvent(lambda: events.append("up"))
        toggle.click()
        self.assertTrue(toggle.IsDown())
        toggle.click()
        self.assertFalse(toggle.IsDown())
        toggle.Disable()
        toggle.click()
        self.assertEqual(events, ["down", "up"], "a disabled toggle does nothing")
        self.assertEqual(len(changes), 3)


class ScrollBar(ProxiesTest):
    def test_set_pos_clamps_and_runs_the_event_and_a_step_moves_by_the_step(self):
        moves, changes = [], []
        bar = self.m.ScrollBarProxy(changes.append)
        bar.SetScrollEvent(lambda: moves.append(bar.GetPos()))
        self.assertEqual(bar.GetScrollStep(), 0.2, "ui.ScrollBar's default step")
        bar.SetPos(2.0)
        bar.SetScrollStep(0.25)
        bar.step(-1)
        bar.step(-9)
        self.assertEqual(moves, [1.0, 0.75, 0.0])
        bar.Hide()
        self.assertFalse(bar.IsShow())
        self.assertEqual(len(changes), 4)


class SafeEventsAndHover(ProxiesTest):
    def test_safe_set_event_keeps_its_arguments_and_holds_a_method_weakly(self):
        class Owner(object):
            def __init__(self):
                self.pressed = []

            def press(self, key):
                self.pressed.append(key)
        owner = Owner()
        button = self.m.ButtonProxy()
        button.SAFE_SetEvent(owner.press, "HTH")
        button.click()
        self.assertEqual(owner.pressed, ["HTH"])

    def test_over_and_out_call_the_tooltip_functions_a_window_set_on_the_instance(self):
        seen = []
        button = self.m.ButtonProxy()
        button.over()
        button.out()
        button.ShowToolTip = lambda: seen.append("show")
        button.HideToolTip = lambda: seen.append("hide")
        button.over()
        button.out()
        self.assertEqual(seen, ["show", "hide"])

    def test_an_image_s_string_events_fire_by_name(self):
        class Owner(object):
            def __init__(self):
                self.seen = []

            def show(self):
                self.seen.append("in")
        owner = Owner()
        image = self.m.ImageProxy()
        image.fire("MOUSE_OVER_IN")
        image.SAFE_SetStringEvent("MOUSE_OVER_IN", owner.show)
        image.fire("MOUSE_OVER_IN")
        image.fire("MOUSE_OVER_OUT")
        self.assertEqual(owner.seen, ["in"])
