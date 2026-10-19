"""NovaUI quest and whisper edge buttons (nui/windows/edge-buttons/edge-buttons.rml).

While the "edge-buttons" window flag is on, uiWhisper.WhisperButton (a
nui_windows.factory) makes EdgeButton below instead of the legacy flashing
ui.Button. The Interface makes, arranges and destroys these buttons itself
(interfacemodule.py BINARY_RecvQuest, __ArrangeQuestButton,
__MakeWhisperButton, __ArrangeWhisperButton), so its code is unchanged: each
EdgeButton is the facade of one button, and all of them share one document,
made with the first one (spec D25). Quest letters stack on the left, whisper
buttons on the right; a button joins a stack with its first SetPosition,
which also tells its place in the legacy arrangement (its column and row),
so the stacks keep the legacy order whatever the screen size.

Each button's label shows below it at all times, as the legacy button's
tooltip text does (uiWhisper.LegacyWhisperButton.SetToolTipText). A
flashing button's art hides every other half second while the pointer is
not over it (CButton::OnRender), with a visibility animation, so no Python
runs per frame. When the Interface drops a button (it clears its event
first, SetEvent(0), which ends the button's reference to itself), the entry
leaves the document (weakref.finalize)."""

import weakref

import wndMgr

import nui
import nui_hud
import nui_slots

DOCUMENT = "nui/windows/edge-buttons/edge-buttons.rml"
GM_COLOR = 0xffffa200        # the Interface's packed color for a game master's name
ROW_HEIGHT = 63              # the legacy arrangement's numbers (interfacemodule.py)
QUEST_X = 20
QUEST_X_SHIFTED = 130        # while the party window shows
QUEST_COLUMN = 100
WHISPER_RIGHT = 70
WHISPER_COLUMN = 50

_board = None
_entries = weakref.WeakValueDictionary()   # entry id -> its EdgeButton
_next_id = [1]
_quest_shift = [False]


def _screen():
	return wndMgr.GetScreenWidth(), wndMgr.GetScreenHeight()


def _stack_numbers(height):
	"""The legacy arrangement's first row and rows per column."""
	return 170 * height // 600, max(1, (height - 330) // ROW_HEIGHT)


class EdgeBoard(nui.Window):
	"""The edge buttons' one document and model."""

	DOCUMENT = DOCUMENT
	MODEL = "edge_buttons"

	def initial_model(self):
		return {"quests": [], "whispers": [], "quest_shift": False}

	@nui.on("press")
	def on_press(self, side, entry_id, button):
		if button != 0:
			return
		facade = _entries.get(entry_id)
		if facade is not None:
			facade.nui_press()


def _get_board():
	"""The shared document, made with the first button; None when it cannot
	load."""
	global _board
	if _board is not None and _board._doc:
		return _board
	if not nui_hud.has_engine():
		return None
	_board = EdgeBoard()
	if not _board._doc:
		_board = None
		return None
	_board.show()
	return _board


def _sync():
	"""Writes both stacks into the model, each in the legacy order."""
	if _board is None or not _board._doc:
		return
	stacks = {"quest": [], "whisper": []}
	for facade in list(_entries.values()):
		if facade._side is not None and not facade._closed:
			stacks[facade._side].append(facade)
	quests = [facade._entry() for facade in sorted(stacks["quest"], key=lambda f: (f._place, f._id))]
	whispers = [facade._entry() for facade in sorted(stacks["whisper"], key=lambda f: (f._place, f._id))]
	_board.set(quests=quests, whispers=whispers, quest_shift=_quest_shift[0])


def _forget(entry_id):
	"""A button went: it leaves the document."""
	_entries.pop(entry_id, None)
	_sync()


def close_all():
	"""Destroys the document and every button (Interface.Close)."""
	global _board
	for facade in list(_entries.values()):
		facade._closed = True
		facade._event = None
		facade._args = ()
	_entries.clear()
	board, _board = _board, None
	if board is not None:
		board.destroy()


class _Label(object):
	"""The button's label as the Interface reaches it (btn.ToolTipText): its
	alignment, visibility and color act on the entry's label."""

	def __init__(self, facade):
		self._facade = weakref.ref(facade)

	def _set(self, **values):
		facade = self._facade()
		if facade is not None:
			facade._label.update(values)
			facade._changed()

	def SetHorizontalAlignCenter(self):
		self._set(align="center")

	def SetHorizontalAlignLeft(self):
		self._set(align="left")

	def SetHorizontalAlignRight(self):
		self._set(align="right")

	def Show(self):
		self._set(shown=True)

	def Hide(self):
		self._set(shown=False)

	def SetPackedFontColor(self, color):
		self._set(gm=(color & 0xffffffff) == GM_COLOR)

	def SetText(self, text):
		self._set(text=text)


class EdgeButton(object):
	"""uiWhisper.WhisperButton on NovaUI: one quest or whisper edge button."""

	NUI_FACADE = True

	def __init__(self):
		self._nui_discarded = False
		self._closed = False
		self._id = _next_id[0]
		_next_id[0] += 1
		self._side = None
		self._place = 0
		self._shown = False
		self._flashing = False
		self._art = {"up": "", "over": "", "down": ""}
		self._label = {"text": "", "shown": False, "align": "center", "gm": False}
		self._event = None
		self._args = ()
		self.ToolTipText = 0
		self.name = ""
		self.index = 0
		self.board = _get_board()
		if self.board is None:
			return
		_entries[self._id] = self
		weakref.finalize(self, _forget, self._id)

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		self._closed = True
		_forget(self._id)

	def _changed(self):
		if self._side is not None:
			_sync()

	def _entry(self):
		return {"id": self._id, "up": self._art["up"], "over": self._art["over"], "down": self._art["down"],
		        "label": nui.plain_text(self._label["text"]), "label_shown": self._label["shown"],
		        "align": self._label["align"], "gm": self._label["gm"], "flashing": self._flashing,
		        "shown": self._shown}

	# --- ui.Button ----------------------------------------------------------------

	def SetUpVisual(self, path):
		self._art["up"] = nui_slots.icon_source(path)
		self._changed()

	def SetOverVisual(self, path):
		self._art["over"] = nui_slots.icon_source(path)
		self._changed()

	def SetDownVisual(self, path):
		self._art["down"] = nui_slots.icon_source(path)
		self._changed()

	def SetToolTipText(self, text, x=0, y=32):
		"""The label, shown at once (LegacyWhisperButton)."""
		if not self.ToolTipText:
			self.ToolTipText = _Label(self)
		self._label.update(text=text, shown=True)
		self._changed()

	def SetToolTipTextWithColor(self, text, color, x=0, y=32):
		self.SetToolTipText(text, x, y)
		self._label["gm"] = (color & 0xffffffff) == GM_COLOR
		self._changed()

	def ShowToolTip(self):
		# LegacyWhisperButton shows its label in both ShowToolTip and
		# HideToolTip: it is always shown.
		if self.ToolTipText:
			self.ToolTipText.Show()

	def HideToolTip(self):
		if self.ToolTipText:
			self.ToolTipText.Show()

	def SetEvent(self, func, *args):
		"""SetEvent(0) clears it, which ends a SetEvent(fn, button) cycle."""
		self._event = func if func else None
		self._args = args if func else ()

	def Show(self):
		self._shown = True
		self._changed()

	def Hide(self):
		self._shown = False
		self._changed()

	def IsShow(self):
		return self._shown and not self._closed

	def Flash(self):
		self._flashing = True
		self._changed()

	def SetTop(self):
		pass

	def SetPosition(self, x, y):
		"""Joins a stack: left of the screen's middle the quest letters, else
		the whisper buttons; its place is the legacy arrangement's
		column * rows + row."""
		width, height = _screen()
		top, rows = _stack_numbers(height)
		row = max(0, (int(y) - top) // ROW_HEIGHT)
		if int(x) < width // 2:
			x0 = QUEST_X_SHIFTED if int(x) >= QUEST_X_SHIFTED and (int(x) - QUEST_X_SHIFTED) % QUEST_COLUMN == 0 else QUEST_X
			column = max(0, (int(x) - x0) // QUEST_COLUMN)
			self._side = "quest"
			_quest_shift[0] = x0 == QUEST_X_SHIFTED
		else:
			column = max(0, (width - WHISPER_RIGHT - int(x)) // WHISPER_COLUMN)
			self._side = "whisper"
		self._place = column * rows + row
		_sync()

	def Destroy(self):
		self._closed = True
		self._event = None
		self._args = ()
		_forget(self._id)

	def nui_press(self):
		"""A left press: the button's event with its arguments, as
		ui.Button.CallEvent calls it."""
		event, args = self._event, self._args
		if event:
			event(*args)


def quest_stack_right():
	"""The right edge, in screen pixels, of the shown quest buttons' places
	(each its column's 100dp), or 0 with none shown or no document: in the
	modern looks the tiles and labels are opaque, so a window that opens at
	the left edge keeps clear of them (P15 fix stage, I-1: the character
	window)."""
	board = _board
	if board is None or not board._doc:
		return 0
	right = 0
	for facade in list(_entries.values()):
		if facade._side != "quest" or not facade.IsShow():
			continue
		box = board.element_box("edge-quest-%d" % facade._id)
		if box:
			right = max(right, box[0] + box[2])
	return right
