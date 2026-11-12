"""The NovaUI game options' keyboard page (NOVA-121):
python3 -B -m unittest nui_keyboard_page_test (from tools/).

nui_game_options.OptionDialog over nui_sys_test's NovaUI world, with the real
keybindings module (its table in memory, config/keys.cfg the world's file):
- the model carries the page, the rows of keybindings.Page and the notice;
- the main page's Keyboard row opens the keys page, Back returns;
- a left press on a key cell arms the capture, the next key binds it and
  the rows and the notice follow; a right press does nothing;
- Escape ends a waiting cell before it closes the window, and a hide never
  leaves a capture armed;
- Reset puts every key back; a change made elsewhere (the legacy dialog)
  reaches the open page;
- the document and the classic overlay: the row at legacy's place (label x
  30, y 442; button x 90, y 440; the board 483 tall), the keys page at the
  legacy key bindings dialog's (384 x 472)."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_sys_test as sys_test  # noqa: E402

WINDOWS = sys_test.WINDOWS
DOCUMENT = os.path.join(WINDOWS, "game-options", "game-options.rml")
CLASSIC = sys_test.CLASSIC_GAME_OPTIONS
ENGLISH = os.path.join(sys_test.LOCALES, "en", "locale_interface.txt")


def english_strings(game):
	"""The KEYBIND_ strings of the English locale on the world's
	uiScriptLocale (its stand-in answers an unknown name with the name)."""
	module = game.modules["uiScriptLocale"]
	for line in sys_test.read(ENGLISH).split("\n"):
		if line.startswith("KEYBIND_") and "\t" in line:
			name, text = line.split("\t", 1)
			setattr(module, name, text)


class Page(unittest.TestCase):
	def setUp(self):
		self.world = sys_test.World(True, setup=english_strings)
		self.world.__enter__()
		self.addCleanup(self.world.__exit__)
		self.kb = self.world.m("keybindings")
		self.options = self.world.make_game_options()
		with sys_test.quiet():
			self.options.Show()

	def tearDown(self):
		self.kb.CAPTURE.cancel()

	def board(self):
		return sys_test.board(self.options)

	def fire(self, *args):
		with sys_test.quiet():
			return self.board().fire(*args)

	def row(self, action):
		return next(r for r in self.board().model["key_rows"] if r.get("id") == action and r["kind"] == "action")

	def test_the_model_has_the_page_the_rows_and_the_notice(self):
		model = self.board().model
		self.assertEqual(model["page"], "main")
		rows = model["key_rows"]
		self.assertEqual(len(rows), len(self.kb.ACTIONS) + len(self.kb.SECTIONS))
		self.assertEqual(rows[0]["kind"], "section")
		self.assertEqual((self.row("inventory")["k1"], self.row("inventory")["k2"]), ("I", ""))
		self.assertEqual(model["notice"], self.kb.hint())

	def test_the_keyboard_row_opens_the_keys_page_and_back_returns(self):
		self.fire("keypage", "open", 0)
		self.assertEqual(self.board().model["page"], "keys")
		self.fire("keypage", "back", 1)
		self.assertEqual(self.board().model["page"], "keys", "a right press does nothing")
		self.fire("keypage", "back", 0)
		self.assertEqual(self.board().model["page"], "main")

	def test_a_left_press_arms_the_capture_and_a_key_binds(self):
		self.fire("keypage", "open", 0)
		self.fire("bind", "inventory", 0, 1)
		self.assertFalse(self.kb.CAPTURE.is_armed(), "a right press does nothing")
		self.fire("bind", "inventory", 0, 0)
		self.assertTrue(self.kb.CAPTURE.is_armed())
		self.assertTrue(self.row("inventory")["cap1"])
		self.assertEqual(self.row("inventory")["k1"], self.kb.press_text())
		self.kb.capture_key_down(self.kb.DIK["M"])
		self.assertFalse(self.kb.CAPTURE.is_armed())
		self.assertEqual(self.row("inventory")["k1"], "M")
		self.assertTrue(self.row("inventory")["changed"])
		self.assertEqual(self.row("minimap")["k1"], "I")
		self.assertEqual(self.board().model["notice"], "M was on Minimap, which now has I.")
		self.assertEqual(self.kb.current().actions_for(self.kb.DIK["M"]), ["inventory"])

	def test_escape_ends_a_waiting_cell_before_it_closes_the_window(self):
		self.fire("keypage", "open", 0)
		self.fire("bind", "pet", 1, 0)
		self.assertTrue(self.options.OnPressEscapeKey())
		self.assertFalse(self.kb.CAPTURE.is_armed())
		self.assertTrue(self.options.IsShow(), "the first Escape only ends the wait")
		self.assertFalse(self.row("pet")["cap2"])
		self.assertTrue(self.options.OnPressEscapeKey())
		self.assertFalse(self.options.IsShow())

	def test_a_hide_never_leaves_a_capture_armed(self):
		self.fire("keypage", "open", 0)
		self.fire("bind", "pet", 0, 0)
		with sys_test.quiet():
			self.options.Hide()
		self.assertFalse(self.kb.CAPTURE.is_armed())
		with sys_test.quiet():
			self.options.Show()
		self.assertEqual(self.board().model["page"], "keys", "the page is kept across a hide, as the place")
		self.assertFalse(self.row("pet")["cap1"])

	def test_reset_puts_every_key_back(self):
		self.kb.current().assign("inventory", 0, self.kb.key("K"))
		self.assertEqual(self.row("inventory")["k1"], "K", "the open page follows a change made elsewhere")
		self.fire("reset_keys", 1)
		self.assertEqual(self.row("inventory")["k1"], "K")
		self.fire("reset_keys", 0)
		self.assertEqual(self.row("inventory")["k1"], "I")
		self.assertEqual(self.board().model["notice"], "Every key is back to its default.")


def rule(classic, selector):
	selector = (" " + selector) if selector else ""
	match = re.search(r"body\.skin-classic\.game-options%s\s*\{([^}]*)\}" % re.escape(selector), classic)
	return match.group(1) if match else ""


def px(block, name):
	match = re.search(r"(?<![-\w])%s: (-?\d+)dp;" % name, block)
	return int(match.group(1)) if match else None


class Document(unittest.TestCase):
	def test_the_row_and_the_page_are_in_the_document(self):
		document = sys_test.read(DOCUMENT)
		self.assertIn('<span class="go-label go-label--keys">@ui.KEYBIND_ROW</span>', document)
		button = re.search(r'<button id="go-keys-open"[^>]*>', document).group(0)
		self.assertIn("data-event-mousedown=\"keypage('open', ev.button)\"", button)
		self.assertLess(document.index('id="go-mob-ai-0"'), document.index('id="go-keys-open"'), "the last row")
		for needle in ("bind(row.id, 0, ev.button)", "bind(row.id, 1, ev.button)", "reset_keys(ev.button)",
		               "keypage('back', ev.button)", "@ui.KEYBIND_COLUMN_ACTION", "@ui.KEYBIND_COLUMN_1",
		               "@ui.KEYBIND_COLUMN_2", "@ui.KEYBIND_RESET", "@ui.KEYBIND_BACK", "{{ notice }}",
		               'data-for="row : key_rows"', "data-class-go-keys-page=\"page == 'keys'\""):
			self.assertIn(needle, document)

	def test_classic_places_the_row_at_legacy_s_place(self):
		classic = sys_test.read(CLASSIC)
		self.assertEqual(px(rule(classic, ".go-label--keys"), "top"), 442)
		block = rule(classic, ".go-choice--keys-open")
		self.assertEqual((px(block, "left"), px(block, "top")), (90, 440))
		self.assertEqual(px(rule(classic, ""), "height"), 483, "the board grows by the row")
		self.assertEqual(px(rule(classic, ".game-options__body"), "height"), 483)

	def test_classic_keys_page_is_the_legacy_dialog_s_board(self):
		classic = sys_test.read(CLASSIC)
		block = re.search(r"body\.skin-classic\.game-options\.go-keys-page\s*\{([^}]*)\}", classic).group(1)
		self.assertEqual((px(block, "width"), px(block, "height")), (384, 472))
		cells = [rule(classic, sel) for sel in (".gk-cell--1", ".gk-cell--2")]
		listing = rule(classic, ".gk-list")
		self.assertEqual((px(listing, "left"), px(listing, "top"), px(listing, "height")), (16, 56, 352))
		self.assertEqual([px(c, "left") + 16 for c in cells], [172, 266])
		self.assertEqual([px(c, "width") for c in cells], [88, 88])
		self.assertEqual(px(rule(classic, ".gk-row"), "height"), 22)
		notice = rule(classic, ".gk-notice")
		self.assertEqual((px(notice, "left"), px(notice, "top")), (20, 416))
		for selector, x in ((".gk-reset", 20), (".gk-back", 303)):
			block = rule(classic, selector)
			self.assertEqual((px(block, "left"), px(block, "top")), (x, 440), selector)


if __name__ == "__main__":
	unittest.main()
