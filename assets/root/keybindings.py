"""The game's key bindings (NOVA-121): one table of actions and default keys
for game.py, both option windows (the legacy key bindings dialog and the
NovaUI game options' keyboard page), both taskbars and both chats.

- ACTIONS: every rebindable game action, in the order the pages list them,
  with two default bindings (primary and alternate) each. A binding is a
  DirectInput scan code (DIK_*) plus at most one modifier (Ctrl, Alt or
  Shift), packed as `mod * 256 + dik`; 0 is no key.
- RESERVED: keys no action can take (Escape, Enter, ...), and the bare keys
  that keep a fixed job (left Ctrl, the mouse mode).
- Bindings: the player's table. `actions_for(dik, mod)` finds the action of
  a key press, falling back to the plain key when the combination has no
  binding (OLD's rule, e4cbb29, and NEW's before the table: Ctrl+W still
  walks, Alt+F1 uses quickslot 5 on the page Alt shows). `assign()` swaps on
  a conflict (CONFLICT), refuses a reserved key or a modifier on a hold
  action, saves at once and tells the listeners.
- Capture: the "press a key" state both pages share; game.py gives it every
  key first.
- Dispatcher: a key-down fires the actions of its key; its key-up releases
  exactly the hold actions that key-down started.

Saved to config/keys.cfg (PATH) in the client folder, as config/mouse.cfg:
only the actions whose keys differ from the defaults, one per line,
`action<TAB>key<TAB>key`, `-` for no key, a key written as `Ctrl+H` with the
token names of KEYS. A line this version does not know is skipped.

The decisions that wait for Eddy (scope NOVA-121.md) are constants here:
CONFLICT, RESERVED, RESERVED_BARE and each action's `modifiers`."""

import weakref

PATH = "config/keys.cfg"
FILE_HEADER = "# NOVA-121 key bindings: action<TAB>key<TAB>key, '-' for none; only keys that differ from the defaults."

# What a conflict does: "swap" (the other action takes this action's old key
# in that column) or "clear" (the other action loses the key, OLD's rule).
CONFLICT = "swap"

MOD_NONE = 0
MOD_CTRL = 1
MOD_ALT = 2
MOD_SHIFT = 3
MOD_NAMES = {MOD_CTRL: "Ctrl", MOD_ALT: "Alt", MOD_SHIFT: "Shift"}

COLUMNS = 2

# DirectInput scan codes (dinput.h), the values the app module exports as
# app.DIK_*: (code, token, shown name). The token is what keys.cfg stores;
# the shown name is the badge and the page's text. A key outside this list
# cannot be bound (the capture waits for another).
KEYS = (
	(0x01, "ESCAPE", "Esc"),
	(0x02, "1", "1"), (0x03, "2", "2"), (0x04, "3", "3"), (0x05, "4", "4"), (0x06, "5", "5"),
	(0x07, "6", "6"), (0x08, "7", "7"), (0x09, "8", "8"), (0x0A, "9", "9"), (0x0B, "0", "0"),
	(0x0C, "MINUS", "-"), (0x0D, "EQUALS", "="), (0x0E, "BACK", "Backspace"), (0x0F, "TAB", "Tab"),
	(0x10, "Q", "Q"), (0x11, "W", "W"), (0x12, "E", "E"), (0x13, "R", "R"), (0x14, "T", "T"),
	(0x15, "Y", "Y"), (0x16, "U", "U"), (0x17, "I", "I"), (0x18, "O", "O"), (0x19, "P", "P"),
	(0x1A, "LBRACKET", "["), (0x1B, "RBRACKET", "]"), (0x1C, "RETURN", "Enter"),
	(0x1D, "LCONTROL", "Left Ctrl"),
	(0x1E, "A", "A"), (0x1F, "S", "S"), (0x20, "D", "D"), (0x21, "F", "F"), (0x22, "G", "G"),
	(0x23, "H", "H"), (0x24, "J", "J"), (0x25, "K", "K"), (0x26, "L", "L"),
	(0x27, "SEMICOLON", ";"), (0x28, "APOSTROPHE", "'"), (0x29, "GRAVE", "`"),
	(0x2A, "LSHIFT", "Left Shift"), (0x2B, "BACKSLASH", "\\"),
	(0x2C, "Z", "Z"), (0x2D, "X", "X"), (0x2E, "C", "C"), (0x2F, "V", "V"), (0x30, "B", "B"),
	(0x31, "N", "N"), (0x32, "M", "M"), (0x33, "COMMA", ","), (0x34, "PERIOD", "."), (0x35, "SLASH", "/"),
	(0x36, "RSHIFT", "Right Shift"), (0x37, "MULTIPLY", "Num *"), (0x38, "LALT", "Left Alt"),
	(0x39, "SPACE", "Space"), (0x3A, "CAPITAL", "Caps Lock"),
	(0x3B, "F1", "F1"), (0x3C, "F2", "F2"), (0x3D, "F3", "F3"), (0x3E, "F4", "F4"), (0x3F, "F5", "F5"),
	(0x40, "F6", "F6"), (0x41, "F7", "F7"), (0x42, "F8", "F8"), (0x43, "F9", "F9"), (0x44, "F10", "F10"),
	(0x45, "NUMLOCK", "Num Lock"), (0x46, "SCROLL", "Scroll Lock"),
	(0x47, "NUMPAD7", "Num 7"), (0x48, "NUMPAD8", "Num 8"), (0x49, "NUMPAD9", "Num 9"),
	(0x4A, "SUBTRACT", "Num -"), (0x4B, "NUMPAD4", "Num 4"), (0x4C, "NUMPAD5", "Num 5"),
	(0x4D, "NUMPAD6", "Num 6"), (0x4E, "ADD", "Num +"), (0x4F, "NUMPAD1", "Num 1"),
	(0x50, "NUMPAD2", "Num 2"), (0x51, "NUMPAD3", "Num 3"), (0x52, "NUMPAD0", "Num 0"),
	(0x53, "DECIMAL", "Num ."), (0x57, "F11", "F11"), (0x58, "F12", "F12"),
	(0x9C, "NUMPADENTER", "Num Enter"), (0x9D, "RCONTROL", "Right Ctrl"), (0xB5, "DIVIDE", "Num /"),
	(0xB7, "SYSRQ", "Print Screen"), (0xB8, "RALT", "Right Alt"), (0xC5, "PAUSE", "Pause"),
	(0xC7, "HOME", "Home"), (0xC8, "UP", "Up"), (0xC9, "PGUP", "Page Up"), (0xCB, "LEFT", "Left"),
	(0xCD, "RIGHT", "Right"), (0xCF, "END", "End"), (0xD0, "DOWN", "Down"), (0xD1, "PGDN", "Page Down"),
	(0xD2, "INSERT", "Insert"), (0xD3, "DELETE", "Delete"),
)
KEY_TOKEN = dict((code, token) for (code, token, name) in KEYS)
KEY_NAME = dict((code, name) for (code, token, name) in KEYS)
TOKEN_KEY = dict((token, code) for (code, token, name) in KEYS)
# Shorter names for the badges, where a full name does not fit.
SHORT_NAME = {0x1D: "Ctrl", 0x9D: "RCtrl", 0x2A: "Shift", 0x36: "RShift", 0x38: "Alt", 0xB8: "RAlt",
              0x0E: "Bksp", 0x3A: "Caps", 0x45: "NumLk", 0x46: "ScrLk", 0x39: "Spc", 0xB7: "PrtSc",
              0xC9: "PgUp", 0xD1: "PgDn", 0xD2: "Ins", 0xD3: "Del", 0x9C: "NEnt", 0xC5: "Pause",
              0xC8: "Up", 0xD0: "Dn", 0xCB: "Lt", 0xCD: "Rt", 0xC7: "Home", 0xCF: "End"}

DIK = dict((token, code) for (code, token, name) in KEYS)
ESCAPE = DIK["ESCAPE"]
BACKSPACE = DIK["BACK"]

# Left and right: either side of a modifier counts for a combination.
MODIFIER_KEYS = {
	DIK["LCONTROL"]: MOD_CTRL, DIK["RCONTROL"]: MOD_CTRL,
	DIK["LALT"]: MOD_ALT, DIK["RALT"]: MOD_ALT,
	DIK["LSHIFT"]: MOD_SHIFT, DIK["RSHIFT"]: MOD_SHIFT,
}
# Checked in this order; the first one held is the combination's (OLD's).
MODIFIER_ORDER = ((MOD_CTRL, (DIK["LCONTROL"], DIK["RCONTROL"])),
                  (MOD_ALT, (DIK["LALT"], DIK["RALT"])),
                  (MOD_SHIFT, (DIK["LSHIFT"], DIK["RSHIFT"])))

# Keys no action takes, with or without a modifier: Escape (the system menu
# and closing windows), Enter and keypad Enter (the chat), Print Screen (the
# screenshot, which OLD locked), Backspace (clears a key in the capture), the
# debug console's comma and the free camera's keypad 9.
RESERVED = frozenset((DIK["ESCAPE"], DIK["RETURN"], DIK["NUMPADENTER"], DIK["SYSRQ"], DIK["BACK"],
                      DIK["COMMA"], DIK["NUMPAD9"]))
# Keys that keep a fixed job alone; a combination with them is still free:
# left Ctrl shows the taskbar's mouse mode while held.
RESERVED_BARE = frozenset((DIK["LCONTROL"],))


def pack(dik, mod=MOD_NONE):
	return (mod << 8) | dik if dik else 0


def unpack(binding):
	"""(dik, mod) of a binding; (0, 0) for none."""
	return binding & 0xFF, binding >> 8


def ctrl(token):
	return pack(DIK[token], MOD_CTRL)


def alt(token):
	return pack(DIK[token], MOD_ALT)


def key(token):
	return pack(DIK[token])


# --- the table ----------------------------------------------------------------

class Action(object):
	"""One rebindable action: `hold` actions also act on the key's release
	(walking, the camera, Tab's war kills, the modes), and take no modifier
	unless `modifiers`; press actions may take one."""

	__slots__ = ("id", "section", "label", "english", "defaults", "hold", "modifiers")

	def __init__(self, id, section, label, english, defaults, hold=False, modifiers=None):
		self.id = id
		self.section = section
		self.label = label
		self.english = english
		self.defaults = tuple(defaults) + (0,) * (COLUMNS - len(defaults))
		self.hold = hold
		self.modifiers = (not hold) if modifiers is None else modifiers


# (id, locale key, English)
SECTIONS = (
	("movement", "KEYBIND_SECTION_MOVEMENT", "Movement"),
	("camera", "KEYBIND_SECTION_CAMERA", "Camera"),
	("actions", "KEYBIND_SECTION_ACTIONS", "Actions"),
	("quickslots", "KEYBIND_SECTION_QUICKSLOTS", "Quickslots"),
	("windows", "KEYBIND_SECTION_WINDOWS", "Windows"),
	("horse", "KEYBIND_SECTION_HORSE", "Horse"),
	("emotions", "KEYBIND_SECTION_EMOTIONS", "Emotions"),
)


def _actions():
	a = []
	add = a.append
	# Movement (game.py MoveUp ... StopRight): W A S D and the arrows.
	add(Action("move_up", "movement", "KEYBIND_MOVE_UP", "Forward", (key("W"), key("UP")), hold=True))
	add(Action("move_down", "movement", "KEYBIND_MOVE_DOWN", "Backward", (key("S"), key("DOWN")), hold=True))
	add(Action("move_left", "movement", "KEYBIND_MOVE_LEFT", "Left", (key("A"), key("LEFT")), hold=True))
	add(Action("move_right", "movement", "KEYBIND_MOVE_RIGHT", "Right", (key("D"), key("RIGHT")), hold=True))
	# The camera; the keypad keys were the "movie" camera, which is the same
	# camera outside the developers' free camera.
	add(Action("camera_rotate_cw", "camera", "KEYBIND_CAMERA_ROTATE_CW", "Rotate clockwise",
	           (key("E"), key("NUMPAD6")), hold=True))
	add(Action("camera_rotate_ccw", "camera", "KEYBIND_CAMERA_ROTATE_CCW", "Rotate counterclockwise",
	           (key("Q"), key("NUMPAD4")), hold=True))
	add(Action("camera_zoom_out", "camera", "KEYBIND_CAMERA_ZOOM_OUT", "Zoom out", (key("R"), key("PGUP")), hold=True))
	add(Action("camera_zoom_in", "camera", "KEYBIND_CAMERA_ZOOM_IN", "Zoom in", (key("F"), key("PGDN")), hold=True))
	add(Action("camera_pitch_down", "camera", "KEYBIND_CAMERA_PITCH_DOWN", "Look down",
	           (key("T"), key("NUMPAD8")), hold=True))
	add(Action("camera_pitch_up", "camera", "KEYBIND_CAMERA_PITCH_UP", "Look up", (key("G"), key("NUMPAD2")), hold=True))
	# Actions.
	add(Action("attack", "actions", "KEYBIND_ATTACK", "Attack", (key("SPACE"),), hold=True))
	add(Action("pickup", "actions", "KEYBIND_PICKUP", "Pick up items", (key("GRAVE"), key("Z"))))
	add(Action("next_target", "actions", "KEYBIND_NEXT_TARGET", "Next target, war kills", (key("TAB"),), hold=True))
	add(Action("show_names", "actions", "KEYBIND_SHOW_NAMES", "Show names", (key("LALT"),), hold=True))
	add(Action("quick_page_mode", "actions", "KEYBIND_QUICK_PAGE_MODE", "Quickslot page (hold)",
	           (key("LSHIFT"),), hold=True))
	add(Action("channel_switch", "actions", "KEYBIND_CHANNEL_SWITCH", "Change channel (hold)", (key("X"),), hold=True))
	# Quickslots: 1-4 and F1-F4 (with the quick page mode or the channel
	# switch held, 1-4 pick a page or a channel).
	for n in range(1, 5):
		add(Action("quickslot_%d" % n, "quickslots", "KEYBIND_QUICKSLOT_%d" % n, "Quickslot %d" % n, (key(str(n)),)))
	for n in range(5, 9):
		add(Action("quickslot_%d" % n, "quickslots", "KEYBIND_QUICKSLOT_%d" % n, "Quickslot %d" % n,
		           (key("F%d" % (n - 4)),)))
	# Windows.
	add(Action("character", "windows", "KEYBIND_CHARACTER", "Character", (key("C"),)))
	add(Action("skills", "windows", "KEYBIND_SKILLS", "Skills", (key("V"),)))
	add(Action("emotions", "windows", "KEYBIND_EMOTIONS", "Emotions", (key("B"),)))
	add(Action("quests", "windows", "KEYBIND_QUESTS", "Quests", (key("N"),)))
	add(Action("inventory", "windows", "KEYBIND_INVENTORY", "Inventory", (key("I"),)))
	add(Action("special_inventory", "windows", "KEYBIND_SPECIAL_INVENTORY", "Special inventory", (key("U"),)))
	add(Action("dragon_soul", "windows", "KEYBIND_DRAGON_SOUL", "Dragon stones", (key("O"),)))
	add(Action("minimap", "windows", "KEYBIND_MINIMAP", "Minimap", (key("M"),)))
	add(Action("messenger", "windows", "KEYBIND_MESSENGER", "Friends", (alt("M"),)))
	add(Action("guild", "windows", "KEYBIND_GUILD", "Guild", (alt("G"),)))
	add(Action("chat_log", "windows", "KEYBIND_CHAT_LOG", "Chat log", (key("L"),)))
	add(Action("help", "windows", "KEYBIND_HELP", "Help", (key("H"),)))
	add(Action("pet", "windows", "KEYBIND_PET", "Pet", (key("P"),)))
	add(Action("switchbot", "windows", "KEYBIND_SWITCHBOT", "Switchbot", (key("F5"),)))
	add(Action("dungeon_manager", "windows", "KEYBIND_DUNGEON_MANAGER", "Dungeon manager", (key("F6"),)))
	add(Action("fast_equip", "windows", "KEYBIND_FAST_EQUIP", "Fast equip", (key("F10"),)))
	add(Action("minimap_zoom_in", "windows", "KEYBIND_MINIMAP_ZOOM_IN", "Minimap zoom in", (key("ADD"),)))
	add(Action("minimap_zoom_out", "windows", "KEYBIND_MINIMAP_ZOOM_OUT", "Minimap zoom out", (key("SUBTRACT"),)))
	add(Action("quest_buttons", "windows", "KEYBIND_QUEST_BUTTONS", "Quest buttons", (ctrl("Q"),)))
	add(Action("ds_deck_1", "windows", "KEYBIND_DS_DECK_1", "Alchemy deck 1", (ctrl("C"),)))
	add(Action("ds_deck_2", "windows", "KEYBIND_DS_DECK_2", "Alchemy deck 2", (ctrl("D"),)))
	# The horse.
	add(Action("horse_summon", "horse", "KEYBIND_HORSE_SUMMON", "Summon horse", (ctrl("H"),)))
	add(Action("horse_feed", "horse", "KEYBIND_HORSE_FEED", "Feed horse", (ctrl("F"),)))
	add(Action("horse_back", "horse", "KEYBIND_HORSE_BACK", "Send horse back", (ctrl("B"),)))
	add(Action("horse_ride", "horse", "KEYBIND_HORSE_RIDE", "Ride", (ctrl("G"),)))
	add(Action("mount", "horse", "KEYBIND_MOUNT", "Mount or dismount", (ctrl("J"),)))
	# Emotions: Ctrl+1 to Ctrl+9.
	for n in range(1, 10):
		add(Action("emotion_%d" % n, "emotions", "KEYBIND_EMOTION_%d" % n, "Emotion %d" % n, (ctrl(str(n)),)))
	return tuple(a)


ACTIONS = _actions()
ACTION = dict((a.id, a) for a in ACTIONS)


def defaults():
	"""{action id: [primary, alternate]} of the shipped table."""
	return dict((a.id, list(a.defaults)) for a in ACTIONS)


# --- names --------------------------------------------------------------------

def key_name(binding, short=False):
	"""The shown name of a binding ("Ctrl+H", "Num 6"); "" for none."""
	if not binding:
		return ""
	dik, mod = unpack(binding)
	name = (short and SHORT_NAME.get(dik)) or KEY_NAME.get(dik, "?")
	if mod:
		return MOD_NAMES[mod] + "+" + name
	return name


def token(binding):
	if not binding:
		return "-"
	dik, mod = unpack(binding)
	text = KEY_TOKEN.get(dik)
	if text is None:
		return "-"
	if mod:
		return MOD_NAMES[mod] + "+" + text
	return text


def parse(text):
	"""A binding from keys.cfg's text; None for text it does not read."""
	text = text.strip()
	if text == "-":
		return 0
	mod = MOD_NONE
	for value, name in MOD_NAMES.items():
		if text.startswith(name + "+") and len(text) > len(name) + 1:
			mod = value
			text = text[len(name) + 1:]
			break
	dik = TOKEN_KEY.get(text)
	if dik is None:
		return None
	return pack(dik, mod)


def _locale(name, english):
	"""A string of the client's locale (uiScriptLocale), English without it."""
	try:
		import uiScriptLocale
	except ImportError:
		return english
	value = getattr(uiScriptLocale, name, None)
	return value if isinstance(value, str) and value else english


def action_label(action_id):
	a = ACTION.get(action_id)
	if a is None:
		return action_id
	return _locale(a.label, a.english)


def section_label(section_id):
	for (sid, name, english) in SECTIONS:
		if sid == section_id:
			return _locale(name, english)
	return section_id


def is_reserved(binding):
	dik, mod = unpack(binding)
	if mod != MOD_NONE and MODIFIER_KEYS.get(dik) == mod:
		return True  # Ctrl with Ctrl is no combination
	return dik in RESERVED or (mod == MOD_NONE and dik in RESERVED_BARE)


# --- the player's table ----------------------------------------------------------

class Result(object):
	"""What assign() did: `status` is "bound", "swapped", "cleared",
	"unchanged", "reserved", "no_modifier" or "cancelled"."""

	def __init__(self, status, action=None, column=0, binding=0, other=None, other_column=0, other_binding=0):
		self.status = status
		self.action = action
		self.column = column
		self.binding = binding
		self.other = other
		self.other_column = other_column
		self.other_binding = other_binding

	def __repr__(self):
		return "Result(%r, %r, %d, %r, other=%r)" % (self.status, self.action, self.column, key_name(self.binding),
		                                          self.other)


def notice(result):
	"""The page's line after a change, in the client's locale."""
	if result is None:
		return ""
	if result.status == "reserved":
		return _locale("KEYBIND_NOTICE_RESERVED", "%s cannot be bound.") % key_name(result.binding)
	if result.status == "no_modifier":
		return _locale("KEYBIND_NOTICE_NO_MODIFIER", "%s takes no Ctrl, Alt or Shift.") % action_label(result.action)
	if result.status == "cleared":
		return _locale("KEYBIND_NOTICE_CLEARED", "%s has no key now.") % action_label(result.action)
	if result.status == "swapped":
		if result.other_binding:
			return _locale("KEYBIND_NOTICE_SWAPPED", "%s was on %s, which now has %s.") % (
				key_name(result.binding), action_label(result.other), key_name(result.other_binding))
		return _locale("KEYBIND_NOTICE_TAKEN", "%s was on %s, which now has no key.") % (
			key_name(result.binding), action_label(result.other))
	if result.status == "reset":
		return _locale("KEYBIND_NOTICE_RESET", "Every key is back to its default.")
	return ""


class Bindings(object):
	"""The player's bindings, {action id: [primary, alternate]}."""

	def __init__(self, path=PATH, opener=None, autosave=True):
		self.path = path
		self.opener = opener or open
		self.autosave = autosave
		self.table = defaults()
		self._index = None
		self._listeners = []

	# --- reading ---

	def get(self, action_id, column=0):
		return self.table.get(action_id, [0] * COLUMNS)[column]

	def keys(self, action_id):
		return list(self.table.get(action_id, [0] * COLUMNS))

	def first(self, action_id):
		"""The key a badge shows: the primary, else the alternate, else 0."""
		for binding in self.table.get(action_id, ()):
			if binding:
				return binding
		return 0

	def is_default(self, action_id):
		return self.table.get(action_id) == list(ACTION[action_id].defaults)

	def index(self):
		if self._index is None:
			index = {}
			for a in ACTIONS:
				for (column, binding) in enumerate(self.table[a.id]):
					if binding:
						index.setdefault(binding, []).append((a.id, column))
			self._index = index
		return self._index

	def owner(self, binding):
		"""(action, column) that has the binding, or None."""
		found = self.index().get(binding)
		return found[0] if found else None

	def actions_for(self, dik, mod=MOD_NONE):
		"""The actions a press of `dik` with modifier `mod` fires: the
		combination's, else (a modifier held) the plain key's."""
		index = self.index()
		found = index.get(pack(dik, mod))
		if not found and mod != MOD_NONE:
			found = index.get(pack(dik))
		return [action for (action, column) in (found or ())]

	# --- changing ---

	def assign(self, action_id, column, binding):
		"""Puts `binding` (0 clears) in the action's column; see Result."""
		a = ACTION.get(action_id)
		if a is None or not 0 <= column < COLUMNS:
			return Result("cancelled", action_id, column, binding)
		if binding == 0:
			if self.table[action_id][column] == 0:
				return Result("unchanged", action_id, column, 0)
			self.table[action_id][column] = 0
			self._changed()
			return Result("cleared", action_id, column, 0)
		dik, mod = unpack(binding)
		if is_reserved(binding):
			return Result("reserved", action_id, column, binding)
		if mod != MOD_NONE and not a.modifiers:
			return Result("no_modifier", action_id, column, binding)
		previous = self.table[action_id][column]
		if previous == binding:
			return Result("unchanged", action_id, column, binding)
		owner = self.owner(binding)
		result = Result("bound", action_id, column, binding)
		if owner is not None:
			other, other_column = owner
			given = previous if CONFLICT == "swap" else 0
			# A modifier the other action refuses stays out of it.
			if given and unpack(given)[1] != MOD_NONE and not ACTION[other].modifiers:
				given = 0
			self.table[other][other_column] = given
			result = Result("swapped", action_id, column, binding, other, other_column, given)
		self.table[action_id][column] = binding
		self._changed()
		return result

	def reset(self):
		self.table = defaults()
		self._changed()
		return Result("reset")

	def _changed(self):
		self._index = None
		if self.autosave:
			self.save()
		self._tell()

	# --- listeners ---

	def listen(self, listener):
		"""`listener.OnKeyBindingsChanged()` after each change; held weakly."""
		self._listeners = [ref for ref in self._listeners if ref() is not None and ref() is not listener]
		self._listeners.append(weakref.ref(listener))

	def forget(self, listener):
		self._listeners = [ref for ref in self._listeners if ref() is not None and ref() is not listener]

	def _tell(self):
		for ref in list(self._listeners):
			listener = ref()
			if listener is None:
				continue
			try:
				listener.OnKeyBindingsChanged()
			except Exception:
				import sys
				sys.excepthook(*sys.exc_info())

	# --- the file ---

	def lines(self):
		out = [FILE_HEADER]
		for a in ACTIONS:
			keys = self.table[a.id]
			if keys != list(a.defaults):
				out.append("\t".join([a.id] + [token(b) for b in keys]))
		return out

	def save(self):
		try:
			with self.opener(self.path, "w") as handle:
				handle.write("\n".join(self.lines()) + "\n")
			return True
		except (IOError, OSError):
			return False

	def load(self):
		"""Reads the file over the defaults; a missing file is the defaults."""
		self.table = defaults()
		self._index = None
		try:
			with self.opener(self.path, "r") as handle:
				text = handle.read()
		except (IOError, OSError):
			return False
		seen = set()
		for line in text.split("\n"):
			line = line.strip("\r")
			if not line or line.startswith("#"):
				continue
			fields = line.split("\t")
			a = ACTION.get(fields[0])
			if a is None or len(fields) != COLUMNS + 1:
				continue
			keys = [parse(field) for field in fields[1:]]
			if any(b is None for b in keys):
				continue
			keys = [b if b and not is_reserved(b) and (unpack(b)[1] == MOD_NONE or a.modifiers) else 0
			        for b in keys]
			if keys[0] and keys[0] == keys[1]:
				keys[1] = 0
			self.table[a.id] = keys
			seen.add(a.id)
		self._drop_duplicates(seen)
		self._index = None
		return True

	def _drop_duplicates(self, loaded):
		"""A hand-edited file can give one key to two actions: the action the
		file names keeps it, a default that clashes with it loses it."""
		owners = {}
		for a in ACTIONS:
			for (column, binding) in enumerate(self.table[a.id]):
				if not binding:
					continue
				if binding in owners:
					first = owners[binding]
					if a.id in loaded and first[0] not in loaded:
						self.table[first[0]][first[1]] = 0
						owners[binding] = (a.id, column)
					else:
						self.table[a.id][column] = 0
				else:
					owners[binding] = (a.id, column)


_current = None


def current():
	"""The client's table, read from PATH at its first use."""
	global _current
	if _current is None:
		_current = Bindings()
		_current.load()
	return _current


def set_current(bindings):
	"""Tests: replace the client's table (None reads it again)."""
	global _current
	_current = bindings
	CAPTURE.cancel()


# --- the state of the keyboard -----------------------------------------------------

def _app_pressed(dik):
	import app
	return bool(app.IsPressed(dik))


def modifier_of(dik, pressed=None):
	"""The modifier held with a press of `dik` (its own family left out)."""
	pressed = pressed or _app_pressed
	own = MODIFIER_KEYS.get(dik)
	for (mod, keys) in MODIFIER_ORDER:
		if mod == own:
			continue
		for k in keys:
			if pressed(k):
				return mod
	return MOD_NONE


# --- the capture ----------------------------------------------------------------

class Capture(object):
	"""The page's "press a key" state. begin() arms it for an action's
	column; the next key press binds (a lone modifier binds on its release
	when no other key came), Escape cancels, Backspace clears. `done(result)`
	gets the Result. While armed it takes every key, so nothing fires."""

	def __init__(self):
		self.action = None
		self.column = 0
		self.done = None
		self.bindings = None
		self.modifier = 0
		self.pressed = None

	def is_armed(self):
		return self.action is not None

	def begin(self, action_id, column, done=None, bindings=None, pressed=None):
		self.action = action_id
		self.column = column
		self.done = done
		self.bindings = bindings
		self.pressed = pressed
		self.modifier = 0

	def cancel(self):
		if self.action is None:
			return
		self._finish(Result("cancelled", self.action, self.column))

	def _finish(self, result):
		done = self.done
		self.action = None
		self.done = None
		self.bindings = None
		self.modifier = 0
		if done is not None:
			done(result)
		return result

	def key_down(self, dik):
		"""True: the capture took the key."""
		if self.action is None:
			return False
		if dik == ESCAPE:
			self.cancel()
			return True
		bindings = self.bindings or current()
		if dik == BACKSPACE:
			self._finish(bindings.assign(self.action, self.column, 0))
			return True
		if dik in MODIFIER_KEYS:
			self.modifier = dik
			return True
		if dik not in KEY_TOKEN:
			return True
		mod = modifier_of(dik, self.pressed)
		self._finish(bindings.assign(self.action, self.column, pack(dik, mod)))
		return True

	def key_up(self, dik):
		"""True: the capture took the release (a lone modifier's binds it)."""
		if self.action is None:
			return False
		if dik in MODIFIER_KEYS and dik == self.modifier:
			bindings = self.bindings or current()
			self._finish(bindings.assign(self.action, self.column, pack(dik)))
		return True


CAPTURE = Capture()


def capture_key_down(dik):
	return CAPTURE.key_down(dik)


def capture_key_up(dik):
	return CAPTURE.key_up(dik)


# --- the dispatcher -----------------------------------------------------------------

class Dispatcher(object):
	"""Fires the actions of game keys. `press` and `release` map action ids to
	callables; a hold action's release runs at the release of the key whose
	press started it, whatever the modifiers and the table are by then."""

	def __init__(self, press, release, bindings=None, pressed=None):
		self.press = press
		self.release = release
		self.bindings = bindings
		self.pressed = pressed
		self.held = {}

	def key_down(self, dik):
		"""The actions fired (a list, empty for none)."""
		bindings = self.bindings or current()
		actions = bindings.actions_for(dik, modifier_of(dik, self.pressed))
		for action in actions:
			fn = self.press.get(action)
			if fn is not None:
				fn()
		held = [action for action in actions if action in self.release]
		if held:
			self.held[dik] = held
		return actions

	def key_up(self, dik):
		actions = self.held.pop(dik, ())
		for action in actions:
			self.release[action]()
		return list(actions)

	def release_all(self):
		for dik in list(self.held):
			self.key_up(dik)


# --- hotkey text for badges and tooltips ---------------------------------------------

def badge(action_id, bindings=None, short=True):
	"""The key a badge shows for the action ("" for none)."""
	return key_name((bindings or current()).first(action_id), short=short)


def with_hotkeys(text, action_ids, bindings=None):
	"""A tooltip's text with its trailing "[...]" hotkey list (the locale
	strings', "Inventory [I]") replaced by the actions' current keys, or
	dropped when none has one."""
	text = text or ""
	stripped = text.rstrip()
	if stripped.endswith("]") and "[" in stripped:
		stripped = stripped[:stripped.rfind("[")].rstrip()
	names = [badge(a, bindings, short=False) for a in action_ids]
	names = [n for n in names if n]
	if not names:
		return stripped
	return "%s [%s]" % (stripped, "/".join(names))
