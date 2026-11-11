"""The legacy key bindings dialog (NOVA-121, root/uikeybindings.py over
uiscript/keybindingsdialog.py), opened from the legacy game options' Keyboard
row: python3 -B -m unittest keybindings_legacy_test (from tools/).

The legacy windows come from their real uiscripts in nui_sys_test's World
(nui_game_support's stand-ins); the table is keybindings' over an in-memory
file."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_sys_test as sys_test  # noqa: E402
import keybindings_test  # noqa: E402


class LegacyDialog(unittest.TestCase):
	def setUp(self):
		world = sys_test.World(False)
		world.__enter__()
		self.addCleanup(world.__exit__)
		self.world = world
		self.kb = world.game.loaded["keybindings"]
		self.files = keybindings_test.Files()
		self.kb.set_current(self.kb.Bindings(opener=self.files))
		self.addCleanup(self.kb.set_current, None)
		self.held = set()
		self.kb._app_pressed = lambda dik: dik in self.held
		options = world.make_game_options()
		with sys_test.quiet():
			options.Show()
			options._OptionDialog__OnClickKeyboardButton()
		self.options = options
		self.dialog = options.keyBindingsDialog

	def texts(self, i):
		label = self.dialog.labels[i]
		return [call[1] for call in label.calls if call[0] == "SetText"][-1]

	def key_text(self, i, column):
		button = self.dialog.keyButtons[i][column]
		return [call[1] for call in button.calls if call[0] == "SetText"][-1]

	def row_of(self, action):
		rows = self.dialog.rows
		index = next(n for n, r in enumerate(rows) if r["id"] == action and r["kind"] == "action")
		self.dialog.offset = max(0, index - 3)
		self.dialog.Refresh()
		return index - self.dialog.offset

	def test_the_row_opens_the_dialog_with_the_table(self):
		self.assertIsNotNone(self.dialog)
		self.assertEqual(type(self.dialog).__module__, "uikeybindings")
		self.assertEqual(self.texts(0), "KEYBIND_SECTION_MOVEMENT")
		self.assertEqual(self.texts(1), "KEYBIND_MOVE_UP")
		self.assertEqual((self.key_text(1, 0), self.key_text(1, 1)), ("W", "Up"))
		self.assertEqual(len(self.dialog.labels), 16)

	def test_a_click_waits_and_a_key_binds_with_the_notice(self):
		i = self.row_of("inventory")
		self.dialog._KeyBindingsDialog__OnClickKey(i, 0)
		self.assertEqual(self.key_text(i, 0), "KEYBIND_PRESS", "the stand-in locale names its keys")
		self.assertTrue(self.kb.capture_key_down(self.kb.DIK["M"]))
		self.assertEqual(self.key_text(i, 0), "M")
		notice = [call[1] for call in self.dialog.notice.calls if call[0] == "SetText"][-1]
		self.assertEqual(notice, "M was on KEYBIND_MINIMAP, which now has I.",
		                 "a locale string without its placeholders: the English sentence")
		self.assertIn("inventory\tM\t-", self.files.files["config/keys.cfg"])

	def test_escape_stops_waiting_before_it_closes(self):
		i = self.row_of("pet")
		self.dialog._KeyBindingsDialog__OnClickKey(i, 1)
		self.assertTrue(self.kb.CAPTURE.is_armed())
		self.assertTrue(self.dialog.OnPressEscapeKey())
		self.assertFalse(self.kb.CAPTURE.is_armed())
		self.assertTrue(self.dialog.IsShow(), "the first Escape only stops waiting")
		self.dialog.OnPressEscapeKey()
		self.assertFalse(self.dialog.IsShow())

	def test_closing_stops_waiting_and_reset_restores(self):
		i = self.row_of("inventory")
		self.dialog._KeyBindingsDialog__OnClickKey(i, 0)
		self.dialog.Close()
		self.assertFalse(self.kb.CAPTURE.is_armed())
		self.kb.current().assign("inventory", 0, self.kb.key("K"))
		self.assertEqual(self.key_text(i, 0), "K", "a change from elsewhere shows at once")
		self.dialog._KeyBindingsDialog__OnClickReset()
		self.assertEqual(self.key_text(i, 0), "I")

	def test_the_wheel_and_the_bar_scroll_the_rows(self):
		self.dialog.offset = 0
		self.dialog.Refresh()
		self.assertTrue(self.dialog.OnRunMouseWheel(-120))
		self.assertEqual(self.texts(0), "KEYBIND_MOVE_UP")
		total = len(self.dialog.rows)
		self.assertEqual(total, len(self.kb.ACTIONS) + len(self.kb.SECTIONS))

	def test_the_options_destroy_the_dialog(self):
		self.options.Destroy()
		self.assertEqual(self.dialog.labels, [])


if __name__ == "__main__":
	unittest.main()
