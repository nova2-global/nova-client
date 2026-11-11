"""The hotkeys the taskbars and the chats show follow the key bindings
(NOVA-121): python3 -B -m unittest keybindings_hotkeys_test (from tools/).

- the NovaUI taskbar: each quickslot cell's key (quick_keys), whether its
  classic cell keeps the legacy key art (quick_key_art), the window buttons'
  badges and every tooltip that names keys, refreshed on a change;
- the legacy taskbar: the slot_1..slot_8 key art stays while its slot has
  its default key; a text line shows the new key once it changes; the
  buttons' tooltips follow;
- both chats: the chat log button's tooltip ("[L]") follows.

The worlds are nui_hud_core_test's and nui_chat_test's (nui_game_support's
stand-ins); the table is the real keybindings module over an in-memory file."""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_hud_core_test as hud  # noqa: E402
import nui_chat_test as chat_test  # noqa: E402

DEFAULT_KEYS = ["1", "2", "3", "4", "F1", "F2", "F3", "F4"]


class Files(object):
	def __init__(self):
		self.files = {}

	def __call__(self, path, mode="r"):
		files = self.files
		if "w" in mode:
			class Writer(io.StringIO):
				def close(self_inner):
					files[path] = self_inner.getvalue()
					io.StringIO.close(self_inner)
			return Writer()
		if path not in files:
			raise IOError(path)
		return io.StringIO(files[path])


def table(world):
	"""The world's keybindings module with a fresh table over memory."""
	kb = world.game.loaded["keybindings"]
	bindings = kb.Bindings(opener=Files())
	kb.set_current(bindings)
	return kb, bindings


class NovaUITaskbar(unittest.TestCase):
	def setUp(self):
		self.world = hud.World(True)
		self.world.__enter__()
		self.addCleanup(self.world.__exit__)
		self.kb, self.bindings = table(self.world)
		with hud.quiet():
			self.bar = self.world.nui_windows.make("taskbar", self.world.uiTaskBar.TaskBar, "nui_taskbar.TaskBar")
			self.bar.LoadWindow()

	def get(self, key):
		return self.bar.board.get(key)

	def test_the_defaults(self):
		self.assertEqual(self.get("quick_keys"), DEFAULT_KEYS)
		self.assertEqual(self.get("quick_key_art"), [True] * 8)
		self.assertEqual((self.get("hotkey_character"), self.get("hotkey_inventory"), self.get("hotkey_messenger")),
		                 ("C", "I", "Alt+M"))
		self.assertEqual(self.get("tip_character"), "TASKBAR_CHARACTER [C/V/B/N]")
		self.assertEqual(self.get("tip_inventory"), "TASKBAR_INVENTORY [I]")
		self.assertEqual(self.get("tip_messenger"), "TASKBAR_MESSENGER [Alt+M]")
		self.assertEqual(self.get("tip_prev_page"), "TASKBAR_PREV_QUICKSLOT")
		self.assertEqual(self.get("tip_next_page"), "TASKBAR_NEXT_QUICKSLOT")

	def test_a_rebound_slot_and_window_follow_and_reset_brings_them_back(self):
		self.bindings.assign("quickslot_1", 0, self.kb.key("K"))
		self.bindings.assign("inventory", 0, self.kb.alt("NUMPAD6"))
		self.bindings.assign("quickslot_6", 0, 0)
		self.assertEqual(self.get("quick_keys"), ["K", "2", "3", "4", "F1", "", "F3", "F4"])
		self.assertEqual(self.get("quick_key_art"), [False, True, True, True, True, False, True, True])
		self.assertEqual(self.get("hotkey_inventory"), "Alt+Num 6")
		self.assertEqual(self.get("tip_inventory"), "TASKBAR_INVENTORY [Alt+Num 6]")
		self.bindings.reset()
		self.assertEqual(self.get("quick_keys"), DEFAULT_KEYS)
		self.assertEqual(self.get("quick_key_art"), [True] * 8)
		self.assertEqual(self.get("hotkey_inventory"), "I")

	def test_the_quick_page_tooltips_follow_their_mode_keys(self):
		self.bindings.assign("quick_page_mode", 0, self.kb.key("Y"))
		self.assertEqual(self.get("tip_prev_page"), "TASKBAR_PREV_QUICKSLOT [Y+1-4]")
		self.assertEqual(self.get("tip_next_page"), "TASKBAR_NEXT_QUICKSLOT [Y+1-4, Left Alt]")

	def test_a_discarded_bar_hears_nothing(self):
		self.bar.Destroy()
		self.bindings.assign("quickslot_1", 0, self.kb.key("K"))


class LegacyTaskbar(unittest.TestCase):
	def setUp(self):
		self.world = hud.World(False)
		self.world.__enter__()
		self.addCleanup(self.world.__exit__)
		self.kb, self.bindings = table(self.world)
		with hud.quiet():
			self.bar = self.world.nui_windows.make("taskbar", self.world.uiTaskBar.TaskBar, "nui_taskbar.TaskBar")
			self.bar.LoadWindow()
		self.assertIsInstance(self.bar, self.world.uiTaskBar.TaskBar)

	def art(self, n):
		return self.bar.GetChild("slot_%d" % n)

	def text(self, n):
		return self.bar.quickKeyTextList[n - 1]

	def test_the_default_keys_keep_the_art(self):
		for n in range(1, 9):
			self.assertTrue(self.art(n).IsShow(), n)
			self.assertFalse(self.text(n).IsShow(), n)
		self.assertEqual(self.bar.GetChild("CharacterButton").tooltip, "TASKBAR_CHARACTER [C/V/B/N]")
		self.assertEqual(self.bar.GetChild("MessengerButton").tooltip, "TASKBAR_MESSENGER [Alt+M]")

	def test_a_rebound_slot_shows_its_key_as_text_and_reset_brings_the_art_back(self):
		self.bindings.assign("quickslot_1", 0, self.kb.key("K"))
		self.assertFalse(self.art(1).IsShow())
		self.assertTrue(self.text(1).IsShow())
		self.assertEqual(self.text(1).text, "K")
		self.assertTrue(self.art(2).IsShow())
		self.bindings.assign("messenger", 0, self.kb.key("J"))
		self.assertEqual(self.bar.GetChild("MessengerButton").tooltip, "TASKBAR_MESSENGER [J]")
		self.bindings.reset()
		self.assertTrue(self.art(1).IsShow())
		self.assertFalse(self.text(1).IsShow())
		self.assertEqual(self.bar.GetChild("MessengerButton").tooltip, "TASKBAR_MESSENGER [Alt+M]")


class ChatLogTooltip(unittest.TestCase):
	def worlds(self):
		legacy, novaui = chat_test.pair()
		tables = [table(world) for world in (legacy, novaui)]
		for world in (legacy, novaui):
			world.enter_game()
		return legacy, novaui, tables

	def test_both_chats_follow_the_chat_log_key(self):
		legacy, novaui, tables = self.worlds()
		self.assertEqual(legacy.chat.btnChatLog.tooltip, "CHAT_LOG [L]")
		self.assertEqual(novaui.chat.board.get("tip_log"), "CHAT_LOG [L]")
		for (kb, bindings) in tables:
			bindings.assign("chat_log", 0, kb.ctrl("L"))
		self.assertEqual(legacy.chat.btnChatLog.tooltip, "CHAT_LOG [Ctrl+L]")
		self.assertEqual(novaui.chat.board.get("tip_log"), "CHAT_LOG [Ctrl+L]")


if __name__ == "__main__":
	unittest.main()
