"""NovaUI virtual keyboard (nui/windows/virtual-keyboard/virtual-keyboard.rml).

The legacy login screen's on-screen keyboard (uiscript loginwindow.py,
intrologin.py's __VirtualKeyboard_* methods) for the NovaUI login board:
nui_login.py makes it with the board while the "virtual-keyboard" flag is
on, and it types into the board's last focused field (LoginBoard.type_text,
which uses nui.Window.insert_text).

- The key sets are the legacy ones (localeInfo.VIRTUAL_KEY_*), shuffled once
  per login window with app.GetRandom exactly as intrologin.Suffle does; the
  lower case set follows the shuffled upper case one.
- Shift and the symbols key are toggles with the legacy mode logic: each
  press flips its key, and the key's down or up call sets the labels
  (__VirtualKeyboard_SetUpperMode, SetLowerMode, SetSymbolMode,
  SetAlphabetMode). The model's `upper` and `mode` are those two keys, which
  the document shows selected.
- Keys act on a left mousedown: the document never takes the focus, so the
  field keeps its caret, and RmlUi sends no click there. Space types " ",
  Enter "\\n" (the ID field moves on to the password field, which submits)
  and Backspace "\\b".
- Sounds: the key's click comes from the host's UI sounds (G11); the typing
  sound plays here after each key that typed, as the legacy edit line played
  it (Enter plays the click the legacy edit line played on Return).
"""

import weakref

import app
import localeInfo
import snd

import nui

DOCUMENT = "nui/windows/virtual-keyboard/virtual-keyboard.rml"
ROW_SIZES = (12, 12, 11, 11)
NUM_KEYS = 46               # intrologin.py VIRTUAL_KEYBOARD_NUM_KEYS
RANDOM_KEYS = True          # intrologin.py VIRTUAL_KEYBOARD_RAND_KEY
SOUND_TYPE = "sound/ui/type.wav"
SOUND_CLICK = "sound/ui/click.wav"


def shuffle(src):
	"""intrologin.Suffle: the same app.GetRandom calls in the same order."""
	if not RANDOM_KEYS:
		return src
	items = [item for item in src]
	count = len(items)
	for old in range(count):
		new = app.GetRandom(0, count - 1)
		items[new], items[old] = items[old], items[new]
	return "".join(items)


def key_rows(keys):
	"""The model's rows: keys 1 to 46 with their labels, unused keys " "."""
	labels = [keys[index] if index < len(keys) else " " for index in range(NUM_KEYS)]
	rows = []
	start = 0
	for size in ROW_SIZES:
		rows.append([{"index": start + i + 1, "label": nui.plain_text(labels[start + i])} for i in range(size)])
		start += size
	return rows


class VirtualKeyboard(nui.Window):
	DOCUMENT = DOCUMENT
	MODEL = "virtual_keyboard"

	def __init__(self, owner):
		# Before nui.Window.__init__, which builds the model from these.
		self._owner = weakref.proxy(owner)
		uppers = localeInfo.VIRTUAL_KEY_ALPHABET_UPPERS
		lowers = localeInfo.VIRTUAL_KEY_ALPHABET_LOWERS
		self._uppers = shuffle(uppers)
		self._lowers = "".join([lowers[uppers.index(key)] for key in self._uppers])
		self._symbols = shuffle(localeInfo.VIRTUAL_KEY_SYMBOLS)
		self._numbers = shuffle(localeInfo.VIRTUAL_KEY_NUMBERS)
		# The legacy state: the mode and the case, and the two toggle keys.
		self._mode = "ALPHABET"
		self._upper = False
		self._shift_down = False
		self._symbols_down = False
		self._keys = self._lowers
		nui.Window.__init__(self)

	def initial_model(self):
		return {"rows": key_rows(self._keys), "mode": "alphabet", "upper": False}

	# --- the legacy mode logic (intrologin.py __VirtualKeyboard_*) -------------------

	def _set_keys(self, keys):
		self._keys = keys
		self.set(rows=key_rows(keys))

	def _set_upper_mode(self):
		self._upper = True
		if self._mode == "ALPHABET":
			self._set_keys(self._uppers)
		elif self._mode == "NUMBER":
			self._set_keys(self._symbols)
		else:
			self._set_keys(self._numbers)

	def _set_lower_mode(self):
		self._upper = False
		if self._mode == "ALPHABET":
			self._set_keys(self._lowers)
		elif self._mode == "NUMBER":
			self._set_keys(self._numbers)
		else:
			self._set_keys(self._symbols)

	def _set_alphabet_mode(self):
		self._upper = False
		self._mode = "ALPHABET"
		self._set_keys(self._lowers)

	def _set_symbol_mode(self):
		self._upper = False
		self._mode = "SYMBOL"
		self._set_keys(self._symbols)

	def labels(self):
		"""The 46 key labels, in key order."""
		return [key["label"] for row in key_rows(self._keys) for key in row]

	# --- typing ----------------------------------------------------------------------

	def _type(self, text, sound=SOUND_TYPE):
		if self._owner.type_text(text):
			snd.PlaySound(sound)

	@nui.on("press")
	def on_press(self, index, button):
		if button != 0 or not isinstance(index, int) or not 1 <= index <= NUM_KEYS:
			return
		self._type(self._keys[index - 1] if index <= len(self._keys) else " ")

	@nui.on("special")
	def on_special(self, name, button):
		if button != 0:
			return
		if name == "shift":
			self._shift_down = not self._shift_down
			if self._shift_down:
				self._set_upper_mode()
			else:
				self._set_lower_mode()
			self.set(upper=self._shift_down)
		elif name == "symbols":
			self._symbols_down = not self._symbols_down
			if self._symbols_down:
				self._set_symbol_mode()
			else:
				self._set_alphabet_mode()
			self.set(mode="symbol" if self._symbols_down else "alphabet")
		elif name == "space":
			self._type(" ")
		elif name == "enter":
			self._type("\n", SOUND_CLICK)
		elif name == "backspace":
			self._type("\b")
