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
