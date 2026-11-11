"""Tests for assets/root/keybindings.py, the key bindings' one table (NOVA-121):
python3 -B -m unittest keybindings_test (from tools/).

- every default binding reaches its action, and only it;
- a rebound key reaches its new action and not its old one;
- conflicts swap, reserved keys and modifiers on hold actions are refused;
- reset, save and load (only changes are written; broken lines are skipped);
- the capture: a key, a combination, a lone modifier, Escape, Backspace;
- the dispatcher releases what a press started;
- the hotkey text of badges and tooltips."""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_test_support as support  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "root"))


def load():
	return support.load_module("keybindings", os.path.join(ROOT, "keybindings.py"))


class Files(object):
	"""An opener over a dict of paths, as the client's open() on config/."""

	def __init__(self, files=None):
		self.files = dict(files or {})

	def __call__(self, path, mode="r"):
		if "w" in mode:
			files = self.files

			class Writer(io.StringIO):
				def close(self_inner):
					files[path] = self_inner.getvalue()
					io.StringIO.close(self_inner)

			return Writer()
		if path not in self.files:
			raise IOError(path)
		return io.StringIO(self.files[path])


class Keyboard(object):
	def __init__(self, *held):
		self.held = set(held)

	def __call__(self, dik):
		return dik in self.held


class Base(unittest.TestCase):
	def setUp(self):
		self.kb = load()
		self.files = Files()
		self.bindings = self.kb.Bindings(path="config/keys.cfg", opener=self.files)
		self.keyboard = Keyboard()
		self.log = []
		press = dict((a.id, (lambda name: (lambda: self.log.append(("press", name))))(a.id)) for a in self.kb.ACTIONS)
		release = dict((a.id, (lambda name: (lambda: self.log.append(("release", name))))(a.id))
		               for a in self.kb.ACTIONS if a.hold)
		self.dispatcher = self.kb.Dispatcher(press, release, self.bindings, self.keyboard)

	def dik(self, token):
		return self.kb.DIK[token]

	def down(self, token, *mods):
		self.keyboard.held = set(self.dik(m) for m in mods)
		self.dispatcher.key_down(self.dik(token))

	def up(self, token):
		self.dispatcher.key_up(self.dik(token))

	def pressed(self):
		return [name for (what, name) in self.log if what == "press"]


class DefaultsReachTheirActions(Base):
	MOD_KEYS = {1: "LCONTROL", 2: "LALT", 3: "LSHIFT"}

	def test_each_default_binding_fires_its_action_and_only_it(self):
		count = 0
		for a in self.kb.ACTIONS:
			for binding in a.defaults:
				if not binding:
					continue
				dik, mod = self.kb.unpack(binding)
				self.log = []
				self.keyboard.held = set([self.dik(self.MOD_KEYS[mod])]) if mod else set()
				fired = self.dispatcher.key_down(dik)
				self.dispatcher.key_up(dik)
				self.assertEqual(fired, [a.id], self.kb.key_name(binding))
				self.assertEqual(self.pressed(), [a.id])
				count += 1
		self.assertGreater(count, 60)

	def test_no_two_actions_share_a_default_and_none_is_reserved(self):
		seen = {}
		for a in self.kb.ACTIONS:
			for binding in a.defaults:
				if binding:
					self.assertNotIn(binding, seen, "%s and %s" % (a.id, seen.get(binding)))
					self.assertFalse(self.kb.is_reserved(binding), a.id)
					seen[binding] = a.id

	def test_the_table_is_todays_key_for_key(self):
		"""The keys game.py's __BuildKeyDict fixed before NOVA-121."""
		expect = {"W": "move_up", "UP": "move_up", "S": "move_down", "DOWN": "move_down", "A": "move_left",
		          "LEFT": "move_left", "D": "move_right", "RIGHT": "move_right", "E": "camera_rotate_cw",
		          "NUMPAD6": "camera_rotate_cw", "Q": "camera_rotate_ccw", "NUMPAD4": "camera_rotate_ccw",
		          "R": "camera_zoom_out", "PGUP": "camera_zoom_out", "F": "camera_zoom_in", "PGDN": "camera_zoom_in",
		          "T": "camera_pitch_down", "NUMPAD8": "camera_pitch_down", "G": "camera_pitch_up",
		          "NUMPAD2": "camera_pitch_up", "SPACE": "attack", "GRAVE": "pickup", "Z": "pickup",
		          "TAB": "next_target", "LALT": "show_names", "LSHIFT": "quick_page_mode", "X": "channel_switch",
		          "1": "quickslot_1", "2": "quickslot_2", "3": "quickslot_3", "4": "quickslot_4",
		          "F1": "quickslot_5", "F2": "quickslot_6", "F3": "quickslot_7", "F4": "quickslot_8",
		          "C": "character", "V": "skills", "B": "emotions", "N": "quests", "I": "inventory",
		          "U": "special_inventory", "O": "dragon_soul", "M": "minimap", "L": "chat_log", "H": "help",
		          "P": "pet", "F5": "switchbot", "F6": "dungeon_manager", "F10": "fast_equip",
		          "ADD": "minimap_zoom_in", "SUBTRACT": "minimap_zoom_out"}
		for token, action in sorted(expect.items()):
			self.assertEqual(self.bindings.actions_for(self.dik(token)), [action], token)
		combos = {("LCONTROL", "Q"): "quest_buttons", ("LCONTROL", "C"): "ds_deck_1", ("LCONTROL", "D"): "ds_deck_2",
		          ("LCONTROL", "H"): "horse_summon", ("LCONTROL", "F"): "horse_feed", ("LCONTROL", "B"): "horse_back",
		          ("LCONTROL", "G"): "horse_ride", ("LCONTROL", "J"): "mount", ("LALT", "M"): "messenger",
		          ("LALT", "G"): "guild"}
		for n in range(1, 10):
			combos[("LCONTROL", str(n))] = "emotion_%d" % n
		for (mod, token), action in sorted(combos.items()):
			self.log = []
			self.down(token, mod)
			self.assertEqual(self.pressed(), [action], (mod, token))

	def test_a_combination_without_a_binding_falls_back_to_the_plain_key(self):
		self.down("F1", "LALT")
		self.down("W", "LCONTROL")
		self.down("1", "LSHIFT")
		self.down("I", "RCONTROL")
		self.assertEqual(self.pressed(), ["quickslot_5", "move_up", "quickslot_1", "inventory"])

	def test_a_combination_with_a_binding_does_not_also_fire_the_plain_key(self):
		self.down("1", "LCONTROL")
		self.down("D", "LCONTROL")
		self.down("M", "LALT")
		self.assertEqual(self.pressed(), ["emotion_1", "ds_deck_2", "messenger"])

	def test_ctrl_wins_over_alt_and_shift_as_in_old(self):
		self.down("G", "LALT", "LCONTROL")
		self.assertEqual(self.pressed(), ["horse_ride"])

	def test_a_modifier_key_itself_ignores_its_own_family(self):
		self.keyboard.held = set([self.dik("LALT")])
		self.dispatcher.key_down(self.dik("LALT"))
		self.assertEqual(self.pressed(), ["show_names"])

	def test_an_unbound_key_fires_nothing(self):
		self.assertEqual(self.dispatcher.key_down(self.dik("K")), [])
		self.assertEqual(self.log, [])


class Releases(Base):
	def test_a_hold_action_ends_at_its_keys_release_whatever_the_modifiers_did(self):
		self.down("W")
		self.keyboard.held = set([self.dik("LCONTROL")])
		self.up("W")
		self.assertEqual(self.log, [("press", "move_up"), ("release", "move_up")])

	def test_a_combination_releases_nothing_it_did_not_start(self):
		self.down("D", "LCONTROL")
		self.up("D")
		self.assertEqual(self.log, [("press", "ds_deck_2")])

	def test_a_release_follows_the_press_even_after_a_rebind(self):
		self.down("W")
		self.bindings.assign("move_up", 0, self.kb.key("K"))
		self.up("W")
		self.assertEqual(self.log, [("press", "move_up"), ("release", "move_up")])

	def test_release_all_ends_every_held_action(self):
		self.down("W")
		self.down("SPACE")
		self.dispatcher.release_all()
		self.assertEqual(sorted(self.log[2:]), [("release", "attack"), ("release", "move_up")])


class Rebinding(Base):
	def test_a_rebound_key_reaches_its_new_action_and_not_its_old_one(self):
		result = self.bindings.assign("inventory", 0, self.kb.key("K"))
		self.assertEqual(result.status, "bound")
		self.down("K")
		self.down("I")
		self.assertEqual(self.pressed(), ["inventory"])

	def test_the_channel_switch_and_a_quickslot_key_move(self):
		self.bindings.assign("channel_switch", 0, self.kb.key("Y"))
		self.bindings.assign("quickslot_1", 0, self.kb.key("K"))
		self.down("Y")
		self.down("K")
		self.down("X")
		self.down("1")
		self.assertEqual(self.pressed(), ["channel_switch", "quickslot_1"])

	def test_a_conflict_swaps(self):
		result = self.bindings.assign("inventory", 0, self.kb.key("M"))
		self.assertEqual((result.status, result.other, result.other_column), ("swapped", "minimap", 0))
		self.assertEqual(self.kb.key_name(result.other_binding), "I")
		self.assertEqual(self.bindings.keys("minimap"), [self.kb.key("I"), 0])
		self.down("M")
		self.down("I")
		self.assertEqual(self.pressed(), ["inventory", "minimap"])
		self.assertEqual(self.kb.notice(result), "M was on Minimap, which now has I.")

	def test_a_conflict_with_an_empty_column_leaves_the_other_action_without_the_key(self):
		result = self.bindings.assign("inventory", 1, self.kb.key("M"))
		self.assertEqual((result.status, result.other_binding), ("swapped", 0))
		self.assertEqual(self.bindings.keys("minimap"), [0, 0])
		self.assertEqual(self.kb.notice(result), "M was on Minimap, which now has no key.")

	def test_a_swap_never_gives_a_modifier_to_an_action_that_refuses_one(self):
		self.bindings.assign("inventory", 0, self.kb.ctrl("I"))
		result = self.bindings.assign("inventory", 0, self.kb.key("W"))
		self.assertEqual((result.status, result.other), ("swapped", "move_up"))
		self.assertEqual(self.bindings.keys("move_up"), [0, self.kb.key("UP")])

	def test_the_two_columns_of_one_action_swap(self):
		result = self.bindings.assign("move_up", 0, self.kb.key("UP"))
		self.assertEqual(result.status, "swapped")
		self.assertEqual(self.bindings.keys("move_up"), [self.kb.key("UP"), self.kb.key("W")])

	def test_clear_mode_takes_the_key_away_as_old(self):
		self.kb.CONFLICT = "clear"
		self.bindings.assign("inventory", 0, self.kb.key("M"))
		self.assertEqual(self.bindings.keys("minimap"), [0, 0])

	def test_reserved_keys_are_refused(self):
		for token in ("ESCAPE", "RETURN", "NUMPADENTER", "SYSRQ", "BACK", "COMMA", "NUMPAD9"):
			for mod in (0, 1):
				result = self.bindings.assign("inventory", 0, self.kb.pack(self.dik(token), mod))
				self.assertEqual(result.status, "reserved", token)
		self.assertEqual(self.bindings.assign("inventory", 0, self.kb.key("LCONTROL")).status, "reserved")
		self.assertEqual(self.bindings.assign("inventory", 0, self.kb.ctrl("LCONTROL")).status, "reserved",
		                 "Ctrl with Ctrl is no combination")
		self.assertEqual(self.bindings.keys("inventory"), [self.kb.key("I"), 0])
		self.assertEqual(self.kb.notice(self.bindings.assign("inventory", 0, self.kb.key("RETURN"))),
		                 "Enter cannot be bound.")

	def test_hold_actions_refuse_a_modifier(self):
		for action in ("move_up", "camera_zoom_in", "attack", "channel_switch"):
			self.assertEqual(self.bindings.assign(action, 0, self.kb.ctrl("K")).status, "no_modifier", action)
		self.assertEqual(self.bindings.assign("inventory", 0, self.kb.alt("K")).status, "bound")

	def test_clearing_a_key(self):
		result = self.bindings.assign("inventory", 0, 0)
		self.assertEqual(result.status, "cleared")
		self.down("I")
		self.assertEqual(self.log, [])
		self.assertEqual(self.kb.notice(result), "Inventory has no key now.")

	def test_reset(self):
		self.bindings.assign("inventory", 0, self.kb.key("M"))
		self.bindings.reset()
		self.assertEqual(self.bindings.table, self.kb.defaults())
		self.down("I")
		self.assertEqual(self.pressed(), ["inventory"])


class Files_(Base):
	def test_nothing_changed_writes_only_the_header(self):
		self.bindings.save()
		self.assertEqual(self.files.files["config/keys.cfg"], self.kb.FILE_HEADER + "\n")

	def test_each_change_is_saved_at_once_and_only_changes_are_written(self):
		self.bindings.assign("inventory", 0, self.kb.key("M"))
		self.bindings.assign("horse_summon", 1, self.kb.alt("NUMPAD6"))
		text = self.files.files["config/keys.cfg"]
		self.assertTrue(text.startswith(self.kb.FILE_HEADER + "\n"))
		self.assertEqual(text.split("\n")[1:], ["inventory\tM\t-", "minimap\tI\t-",
		                                        "horse_summon\tCtrl+H\tAlt+NUMPAD6", ""], "the table's order")

	def test_load_reads_what_save_wrote(self):
		self.bindings.assign("inventory", 0, self.kb.key("M"))
		self.bindings.assign("emotion_3", 1, self.kb.alt("F7"))
		again = self.kb.Bindings(path="config/keys.cfg", opener=self.files)
		self.assertTrue(again.load())
		self.assertEqual(again.table, self.bindings.table)

	def test_a_missing_file_is_the_defaults(self):
		self.assertFalse(self.bindings.load())
		self.assertEqual(self.bindings.table, self.kb.defaults())

	def test_broken_lines_are_skipped(self):
		self.files.files["config/keys.cfg"] = "\n".join([
			"# comment", "inventory\tK\t-", "no_such_action\tK\t-", "pet\tNOPE\t-", "skills\tV", "",
			"help\tESCAPE\t-", "move_up\tCtrl+W\tUP", "quests\tJ\tJ", "minimap\tM\r"])
		self.bindings.load()
		self.assertEqual(self.bindings.keys("inventory"), [self.kb.key("K"), 0])
		self.assertEqual(self.bindings.keys("pet"), [self.kb.key("P"), 0], "an unknown key name: the default")
		self.assertEqual(self.bindings.keys("help"), [0, 0], "a reserved key reads as none")
		self.assertEqual(self.bindings.keys("move_up"), [0, self.kb.key("UP")], "no modifier on a hold action")
		self.assertEqual(self.bindings.keys("quests"), [self.kb.key("J"), 0])
		self.assertEqual(self.bindings.keys("mount"), [self.kb.ctrl("J"), 0])

	def test_a_hand_edited_duplicate_goes_to_the_action_the_file_names(self):
		self.files.files["config/keys.cfg"] = "inventory\tM\t-\n"
		self.bindings.load()
		self.assertEqual(self.bindings.keys("minimap"), [0, 0])
		self.assertEqual(self.bindings.actions_for(self.dik("M")), ["inventory"])

	def test_a_failed_write_keeps_the_change(self):
		def broken(path, mode="r"):
			raise IOError(path)
		bindings = self.kb.Bindings(path="config/keys.cfg", opener=broken)
		self.assertEqual(bindings.assign("inventory", 0, self.kb.key("K")).status, "bound")
		self.assertEqual(bindings.actions_for(self.dik("K")), ["inventory"])


class Listener(object):
	def __init__(self):
		self.calls = 0

	def OnKeyBindingsChanged(self):
		self.calls += 1


class Listeners(Base):
	def test_listeners_hear_every_change_and_are_held_weakly(self):
		listener = Listener()
		self.bindings.listen(listener)
		self.bindings.assign("inventory", 0, self.kb.key("K"))
		self.bindings.assign("inventory", 0, self.kb.key("K"))
		self.bindings.assign("inventory", 0, self.kb.key("RETURN"))
		self.bindings.reset()
		self.assertEqual(listener.calls, 2, "unchanged and refused tell nobody")
		del listener
		self.bindings.reset()


class Captures(Base):
	def setUp(self):
		Base.setUp(self)
		self.capture = self.kb.Capture()
		self.results = []

	def begin(self, action, column=0):
		self.capture.begin(action, column, self.results.append, self.bindings, self.keyboard)

	def test_the_next_key_binds(self):
		self.begin("inventory")
		self.assertTrue(self.capture.key_down(self.dik("K")))
		self.assertFalse(self.capture.is_armed())
		self.assertEqual(self.bindings.keys("inventory"), [self.kb.key("K"), 0])
		self.assertEqual(self.results[0].status, "bound")
		self.assertFalse(self.capture.key_down(self.dik("K")), "disarmed: the key goes to the game")

	def test_a_combination(self):
		self.begin("inventory", 1)
		self.assertTrue(self.capture.key_down(self.dik("LCONTROL")))
		self.keyboard.held = set([self.dik("LCONTROL")])
		self.capture.key_down(self.dik("K"))
		self.assertTrue(self.capture.key_up(self.dik("LCONTROL")) is False)
		self.assertEqual(self.bindings.keys("inventory"), [self.kb.key("I"), self.kb.ctrl("K")])

	def test_a_lone_modifier_binds_on_its_release(self):
		self.begin("channel_switch")
		self.capture.key_down(self.dik("RSHIFT"))
		self.assertTrue(self.capture.is_armed())
		self.capture.key_up(self.dik("RSHIFT"))
		self.assertEqual(self.bindings.keys("channel_switch"), [self.kb.key("RSHIFT"), 0])

	def test_escape_cancels_and_backspace_clears(self):
		self.begin("inventory")
		self.capture.key_down(self.kb.ESCAPE)
		self.assertEqual(self.results[-1].status, "cancelled")
		self.assertEqual(self.bindings.keys("inventory"), [self.kb.key("I"), 0])
		self.begin("inventory")
		self.capture.key_down(self.kb.BACKSPACE)
		self.assertEqual(self.results[-1].status, "cleared")
		self.assertEqual(self.bindings.keys("inventory"), [0, 0])

	def test_a_refused_key_ends_the_capture_with_its_reason(self):
		self.begin("move_up")
		self.keyboard.held = set([self.dik("LALT")])
		self.capture.key_down(self.dik("K"))
		self.assertEqual(self.results[-1].status, "no_modifier")
		self.assertEqual(self.kb.notice(self.results[-1]), "Forward takes no Ctrl, Alt or Shift.")

	def test_a_key_outside_the_table_waits_for_another(self):
		self.begin("inventory")
		self.assertTrue(self.capture.key_down(0xDB))  # the Windows key
		self.assertTrue(self.capture.is_armed())

	def test_a_capture_takes_the_key_from_the_game(self):
		"""While armed, nothing fires: game.py asks the capture first."""
		self.begin("inventory")
		taken = self.capture.key_down(self.dik("W"))
		self.assertTrue(taken)
		self.assertEqual(self.log, [])


class Names(Base):
	def test_names_and_tokens(self):
		self.assertEqual(self.kb.key_name(self.kb.ctrl("H")), "Ctrl+H")
		self.assertEqual(self.kb.key_name(self.kb.key("NUMPAD6")), "Num 6")
		self.assertEqual(self.kb.key_name(self.kb.key("LSHIFT"), short=True), "Shift")
		self.assertEqual(self.kb.key_name(0), "")
		for (code, token, name) in self.kb.KEYS:
			for mod in (0, 1, 2, 3):
				binding = self.kb.pack(code, mod)
				self.assertEqual(self.kb.parse(self.kb.token(binding)), binding, token)

	def test_the_codes_are_directinputs(self):
		"""keybindings.KEYS against the client's app.DIK_* (PythonApplicationModule.cpp)."""
		known = {"ESCAPE": 0x01, "TAB": 0x0F, "RETURN": 0x1C, "LCONTROL": 0x1D, "LSHIFT": 0x2A, "LALT": 0x38,
		         "SPACE": 0x39, "F1": 0x3B, "F10": 0x44, "F11": 0x57, "NUMPAD9": 0x49, "ADD": 0x4E,
		         "SUBTRACT": 0x4A, "SYSRQ": 0xB7, "RALT": 0xB8, "UP": 0xC8, "PGUP": 0xC9, "DOWN": 0xD0,
		         "PGDN": 0xD1, "GRAVE": 0x29, "COMMA": 0x33, "NUMPADENTER": 0x9C, "RCONTROL": 0x9D}
		for token, code in known.items():
			self.assertEqual(self.dik(token), code, token)

	def test_hotkeys_in_tooltips_follow_the_table(self):
		self.assertEqual(self.kb.with_hotkeys("Inventory [I]", ["inventory"], self.bindings), "Inventory [I]")
		self.assertEqual(self.kb.with_hotkeys("Character [C/V/B/N]", ["character", "skills", "emotions", "quests"],
		                                      self.bindings), "Character [C/V/B/N]")
		self.bindings.assign("inventory", 0, self.kb.alt("K"))
		self.assertEqual(self.kb.with_hotkeys("Inventar [I]", ["inventory"], self.bindings), "Inventar [Alt+K]")
		self.bindings.assign("inventory", 0, 0)
		self.assertEqual(self.kb.with_hotkeys("Inventory [I]", ["inventory"], self.bindings), "Inventory")
		self.assertEqual(self.kb.with_hotkeys("Options[ESC]", [], self.bindings), "Options")

	def test_a_badge_shows_the_primary_else_the_alternate(self):
		self.assertEqual(self.kb.badge("move_up", self.bindings), "W")
		self.bindings.assign("move_up", 0, 0)
		self.assertEqual(self.kb.badge("move_up", self.bindings), "Up")
		self.assertEqual(self.kb.badge("show_names", self.bindings), "Alt")


if __name__ == "__main__":
	unittest.main()


class Locales(unittest.TestCase):
	LOCALES = "ae br cz de dk en es fr gr hu it nl pl pt ro ru tr".split()
	PAGE = ("KEYBIND_TITLE", "KEYBIND_ROW", "KEYBIND_OPEN", "KEYBIND_HINT", "KEYBIND_PRESS", "KEYBIND_COLUMN_ACTION",
	        "KEYBIND_COLUMN_1", "KEYBIND_COLUMN_2", "KEYBIND_RESET", "KEYBIND_BACK")
	NOTICES = {"KEYBIND_NOTICE_RESERVED": 1, "KEYBIND_NOTICE_NO_MODIFIER": 1, "KEYBIND_NOTICE_CLEARED": 1,
	           "KEYBIND_NOTICE_SWAPPED": 3, "KEYBIND_NOTICE_TAKEN": 2, "KEYBIND_NOTICE_RESET": 0}

	def test_every_locale_has_every_string_and_its_placeholders(self):
		kb = load()
		keys = [a.label for a in kb.ACTIONS] + [name for (sid, name, english) in kb.SECTIONS] + list(self.PAGE)
		for locale in self.LOCALES:
			path = os.path.join(ROOT, "..", "locale", "locale", locale, "locale_interface.txt")
			with open(path, encoding="utf-8") as handle:
				entries = dict(line.split("\t", 1) for line in handle.read().split("\n") if "\t" in line)
			for name in keys:
				self.assertTrue(entries.get(name, "").strip(), (locale, name))
				self.assertNotIn("%", entries[name], (locale, name))
			for name, count in self.NOTICES.items():
				self.assertEqual(entries[name].count("%s"), count, (locale, name))
				self.assertEqual(entries[name].count("%"), count, (locale, name))

	def test_the_english_strings_are_the_tables(self):
		kb = load()
		path = os.path.join(ROOT, "..", "locale", "locale", "en", "locale_interface.txt")
		with open(path, encoding="utf-8") as handle:
			entries = dict(line.split("\t", 1) for line in handle.read().split("\n") if "\t" in line)
		for a in kb.ACTIONS:
			self.assertEqual(entries[a.label], a.english)
		bindings = kb.Bindings(opener=Files())
		self.assertEqual(kb.notice(bindings.assign("inventory", 0, kb.key("M"))).replace("%s", ""),
		                 (entries["KEYBIND_NOTICE_SWAPPED"] % ("M", "Minimap", "I")).replace("%s", ""))


class Pages(Base):
	def setUp(self):
		Base.setUp(self)
		self.refreshes = 0
		self.page = self.kb.Page(self.refresh, self.bindings, self.keyboard)

	def refresh(self):
		self.refreshes += 1

	def row(self, action):
		return next(r for r in self.page.rows() if r["id"] == action and r["kind"] == "action")

	def test_rows_are_sections_then_their_actions(self):
		rows = self.page.rows()
		self.assertEqual(len(rows), len(self.kb.ACTIONS) + len(self.kb.SECTIONS))
		self.assertEqual([r["id"] for r in rows if r["kind"] == "section"], [s[0] for s in self.kb.SECTIONS])
		self.assertEqual(rows[0]["label"], "Movement")
		self.assertEqual(rows[1], {"kind": "action", "id": "move_up", "label": "Forward", "k1": "W", "k2": "Up",
		                           "cap1": False, "cap2": False, "changed": False})

	def test_a_click_waits_a_key_binds_and_the_notice_tells(self):
		self.page.press("inventory", 0)
		self.assertEqual(self.row("inventory")["k1"], "Press a key")
		self.assertTrue(self.row("inventory")["cap1"])
		self.kb.CAPTURE.key_down(self.dik("M"))
		self.assertEqual(self.page.armed, None)
		self.assertEqual(self.row("inventory")["k1"], "M")
		self.assertTrue(self.row("inventory")["changed"])
		self.assertEqual(self.row("minimap")["k1"], "I")
		self.assertEqual(self.page.notice_text(), "M was on Minimap, which now has I.")
		self.assertEqual(self.refreshes, 2)

	def test_a_second_click_or_escape_or_another_cell_stops_waiting(self):
		self.page.press("inventory", 0)
		self.page.press("inventory", 0)
		self.assertFalse(self.kb.CAPTURE.is_armed())
		self.page.press("inventory", 0)
		self.page.press("pet", 1)
		self.assertEqual((self.kb.CAPTURE.action, self.kb.CAPTURE.column), ("pet", 1))
		self.assertEqual(self.page.armed, ("pet", 1))
		self.assertTrue(self.page.cancel())
		self.assertFalse(self.page.cancel())
		self.assertFalse(self.kb.CAPTURE.is_armed())

	def test_reset(self):
		self.bindings.assign("inventory", 0, self.kb.key("K"))
		self.page.reset()
		self.assertEqual(self.row("inventory")["k1"], "I")
		self.assertEqual(self.page.notice_text(), "Every key is back to its default.")

	def test_the_hint_shows_until_something_happens(self):
		self.assertEqual(self.page.notice_text(),
		                 "Click a key, then press the new one. Esc cancels, Backspace clears.")

	def tearDown(self):
		self.kb.CAPTURE.cancel()
