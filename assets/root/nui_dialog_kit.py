"""The NovaUI dialog kit: what the five dialog windows share (nui_dialog_message,
nui_dialog_question, nui_dialog_input, nui_dialog_money, nui_pick_money).

The legacy common dialogs (uiCommon.PopupDialog, QuestionDialog,
InputDialog, MoneyInputDialog, uiPickMoney.PickMoneyDialog,
networkModule.PopupDialog) are made through nui_windows.factory("dialogs",
...): with the flag on, a caller gets a facade from this kit instead, with
the legacy constructor and method names and meanings, so no caller changes.

- One shared document per kind (KindWindow): RmlUi allows one data model per
  name, and a document binds its model by name, so a kind's document is made
  once, with its first facade, and kept hidden between uses.
- A facade claims its kind's window to show it. While the window is shown
  for another facade, the second facade makes the legacy dialog instead,
  replays its state into it, and routes every call to it until its Close or
  Destroy. The legacy dialog then opens in the TOP_MOST layer, above NovaUI
  (nui_windows.legacy_dialog_layer).
- A facade holds its state in Python attributes (texts, events, modes, the
  last field value), so it survives a claim by another facade and fills
  the model again at each show.
- Every caller string goes through nui.plain_text() before it reaches the
  model, since {{ }} would translate an @ui.KEY inside it. The default labels
  are locale keys on purpose.
- Escape is an element_on("", "keydown") handler on the document and on the
  field; it returns True only when it acted. Enter presses the focused
  default button (RmlUi clicks a focused button), or comes from the field's
  change event with linebreak.

Events are whatever the caller passed: a function, a ui.__mem_func__, 0 or
None. They are called with no arguments, as legacy button events are; a
falsy one is skipped and return values are ignored.
"""

import weakref

import dbg
import nui

# KindWindow subclass -> its one shared window, or False after it failed.
_kinds = {}


def call_event(event, *args):
	"""Calls a caller's event; a falsy one (0, None) is skipped."""
	if event:
		event(*args)


def text_lines(text):
	"""The lines a legacy text line would show: split at "\\n", each made
	safe for {{ }}. None and "" give no line."""
	if text is None:
		return []
	if not isinstance(text, str):
		text = str(text)
	if text == "":
		return []
	return [nui.plain_text(line) for line in text.split("\n")]


def kind_window(cls):
	"""The shared window of a kind, made the first time it is needed; None
	when NovaUI is not running or its document did not load (remembered, so
	the runtime logs the failure once)."""
	window = _kinds.get(cls)
	if window is False:
		return None
	if window is not None and window._doc:
		return window
	if not nui.is_available():
		return None
	try:
		window = cls(None)
	except Exception as error:
		dbg.TraceError("nui_dialog_kit: %s could not be made (%s)" % (cls.__name__, type(error).__name__))
		_kinds[cls] = False
		return None
	if not window._doc:
		window.destroy()
		_kinds[cls] = False
		return None
	_kinds[cls] = window
	return window


class KindWindow(nui.Window):
	"""The document of one dialog kind, shared by every facade of the kind.
	It forwards its events to the facade that holds it (its owner, kept by
	weak reference), wires Escape, and knows its ids. All kinds but pick
	money are modal. Each kind's module declares its @nui.on handlers (lint
	reads them there) and forwards them with forward()."""

	MODAL = True
	BOX = ""          # the element whose box GetWidth and GetHeight give
	DEFAULT = None    # the button focused on each show, for Enter
	FIELD = None      # the text field, if the kind has one

	def __init__(self, owner):
		self._holder = None
		self._holder_id = 0
		self.set_owner(owner)
		nui.Window.__init__(self)
		if self._doc:
			self.element_on("", "keydown", self._on_key)
			if self.FIELD:
				self.element_on(self.FIELD, "keydown", self._on_key)

	def set_owner(self, owner):
		"""The facade the window reports to now; None for none. Kept by weak
		reference (a plain object() that has none, from a fixture check, is
		kept as it is)."""
		if owner is None:
			self._holder, self._holder_id = None, 0
			return
		try:
			self._holder = weakref.ref(owner)
		except TypeError:
			self._holder = lambda: owner
		self._holder_id = id(owner)

	def owner(self):
		"""The facade that holds the window, or None (also once it is gone)."""
		return self._holder() if self._holder is not None else None

	def held_by(self, facade):
		"""Whether `facade` holds the window. A facade collected with a cycle
		loses its weak references before its __del__ runs, so a dead
		reference with the facade's id still counts as that facade."""
		if self._holder is None:
			return False
		current = self._holder()
		return current is facade or (current is None and self._holder_id == id(facade))

	def forward(self, name, *args):
		"""Calls the owner's callback `name`; its result, or None without one."""
		owner = self.owner()
		if owner is None:
			return None
		return getattr(owner, name)(*args)

	def box(self):
		"""(width, height) of the dialog in pixels, (0, 0) while hidden."""
		if not self._doc or not self.is_visible():
			return 0, 0
		get_box = getattr(getattr(nui, "_nui", None), "GetElementBox", None)
		box = get_box(self._doc, self.BOX) if get_box is not None else None
		if not box:
			return 0, 0
		return int(round(box[2])), int(round(box[3]))

	def _on_key(self, event):
		if event.get("key_identifier") != nui.KEY_ESCAPE or not self.is_visible():
			return None
		return True if self.forward("_nui_escape") else None

	def on_reload(self):
		# A locale change re-loaded the document: its field starts empty.
		if self.is_visible():
			self.forward("_nui_reloaded")


class DialogFacade(object):
	"""The legacy surface of one dialog. Subclasses name their KIND (a
	KindWindow subclass) and LEGACY ("module.Class" of the legacy class the
	busy fallback makes), keep their state in attributes, and implement
	_fill() (the model from that state), _replay(legacy) (that state through
	the legacy methods) and the _nui_* callbacks."""

	KIND = None
	LEGACY = None

	def __init__(self):
		self._window = kind_window(self.KIND)
		self._legacy = None        # the legacy dialog while the kind was busy
		self._nui_discarded = False

	# --- the nui_windows.make() protocol ------------------------------------------

	def nui_ready(self):
		return self._window is not None and bool(self._window._doc)

	def nui_discard(self):
		self._window = None
		self._nui_discarded = True

	# --- claim, release and the legacy fallback -------------------------------------

	def _held(self):
		window = self._window
		return window is not None and window._doc and window.held_by(self) and window.is_visible()

	def _claim(self):
		"""The kind's window for this facade, or None while it is shown for
		another one (busy) or missing."""
		window = self._window
		if window is None or not window._doc:
			return None
		if window.is_visible() and window.owner() is not None and not window.held_by(self):
			return None
		window.set_owner(self)
		return window

	def _release(self):
		"""Hides the window when this facade holds it; no event."""
		window = self._window
		if window is None or not window.held_by(self):
			return
		if window.FIELD and window.is_visible():
			window.set_owner(None)
			window.set_value(window.FIELD, "")
		window.set_owner(None)
		window.hide()

	def _legacy_class(self):
		module_name, _, class_name = self.LEGACY.rpartition(".")
		module = __import__(module_name, fromlist=[class_name])
		return getattr(module, class_name)

	def _open_legacy(self, *open_args):
		"""The busy fallback: a legacy dialog with this facade's state, opened
		with the same arguments; later calls go to it until its Close."""
		legacy = self._legacy_class()()
		self._replay(legacy)
		self._legacy = legacy
		legacy.Open(*open_args)
		return legacy

	def _show(self, reset=None):
		"""Shows the dialog for this facade: the legacy one while routed; else
		claims the window, fills the model, shows it (a modal centered by its
		scrim), lets `reset` set its fields, and focuses the default button
		or the field. False while the kind is busy."""
		if self._routed():
			self._legacy.Show()
			return True
		window = self._claim()
		if window is None:
			return False
		window.set(**self._fill())
		self._place(window)
		window.show()
		if window.FIELD:
			window.set_value(window.FIELD, self._field_text(), caret="end")
		if reset is not None:
			reset(window)
		window.focus(window.FIELD or window.DEFAULT)
		return True

	def _place(self, window):
		"""Before a show: a modal is centered by its scrim; pick money places
		itself at the mouse."""
		pass

	def _field_text(self):
		return ""

	def _routed(self):
		"""True while calls go to the legacy dialog of a busy open. One that
		closed itself (its own button, Enter or Escape) is dropped here, so
		the next open claims the NovaUI window again; a closed legacy input
		dialog cannot open twice anyway (its Close clears its parts)."""
		legacy = self._legacy
		if legacy is None:
			return False
		if legacy.IsShow():
			return True
		self._legacy = None
		return False

	def _drop_legacy(self):
		legacy, self._legacy = self._legacy, None
		return legacy

	def __del__(self):
		# Callers drop dialogs without Close (introselect.py): hide silently.
		try:
			self._release()
		except Exception:
			pass

	# --- callbacks from the window (overridden per kind) ------------------------------

	def _nui_accept(self):
		pass

	def _nui_cancel(self):
		pass

	def _nui_edit(self, value, linebreak):
		pass

	def _nui_escape(self):
		return False

	def _nui_reloaded(self):
		window = self._window
		if window is not None and window.FIELD:
			window.set_value(window.FIELD, self._field_text(), caret="end")
			window.focus(window.FIELD)

	# --- ui.ScriptWindow shims callers use ------------------------------------------

	@property
	def hWnd(self):
		"""The legacy dialog's handle while routed, else None (a NovaUI dialog
		has no legacy window to move between layers)."""
		return getattr(self._legacy, "hWnd", None)

	def Show(self):
		self._show()

	def Hide(self):
		if self._legacy is not None:
			self._legacy.Hide()
			return
		self._release()

	def IsShow(self):
		if self._legacy is not None:
			return bool(self._legacy.IsShow())
		return bool(self._held())

	def SetTop(self):
		if self._legacy is not None:
			self._legacy.SetTop()
		elif self._held():
			self._window.bring_to_front()

	def SetCenterPosition(self, x=0, y=0):
		if self._legacy is not None:
			self._legacy.SetCenterPosition(x, y)

	def SetPosition(self, x, y):
		if self._legacy is not None:
			self._legacy.SetPosition(x, y)

	def ClearDictionary(self):
		if self._legacy is not None:
			self._legacy.ClearDictionary()

	def Lock(self):
		pass

	def Unlock(self):
		pass

	def SetSize(self, width, height):
		if self._legacy is not None:
			self._legacy.SetSize(width, height)

	def UpdateRect(self):
		if self._legacy is not None:
			self._legacy.UpdateRect()

	def GetWidth(self):
		if self._legacy is not None:
			return self._legacy.GetWidth()
		return self._window.box()[0] if self._held() else 0

	def GetHeight(self):
		if self._legacy is not None:
			return self._legacy.GetHeight()
		return self._window.box()[1] if self._held() else 0

	def KillFocus(self):
		if self._legacy is not None:
			self._legacy.KillFocus()
