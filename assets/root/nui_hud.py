"""What the NovaUI HUD facades share (docs/ui/AUTHORING.md "HUD windows").

A HUD facade is a plain class with the legacy class's name, constructor and
methods (nui_taskbar.TaskBar for uiTaskBar.TaskBar), made by
nui_windows.make() where the Interface and the game window make the legacy
one. Its document is a nui.Window board that loads hidden in the facade's
constructor; the facade answers nui_ready() and nui_discard() for make(),
and carries NUI_FACADE = True, which the Interface and game.py wiring use to
touch only NovaUI objects. No facade runs Python per frame: it acts on the
Interface's calls, the C++ callbacks that reach it and its document's
events, and fed model keys (nui.Window.FEEDS) carry what changes in between."""

import sys
import weakref

import ui

import nui

_facades = {}  # key -> the facade made last under it


def has_engine():
	"""True when the exe has the Wave 2a engine: the nuigame module and
	_nui.BindFeed. A facade's nui_ready() is False without it, so make()
	keeps the legacy window on an older exe."""
	if sys.modules.get("nuigame") is None:
		try:
			import nuigame  # noqa: F401
		except ImportError:
			return False
	return getattr(getattr(nui, "_nui", None), "BindFeed", None) is not None


def has_engine_2b():
	"""True when the exe has the Wave 2b engine as well: nuigame's chat,
	view and anchor functions. A Wave 2b facade's nui_ready() is False
	without it, so make() keeps the legacy window on an older exe."""
	if not has_engine():
		return False
	nuigame = sys.modules.get("nuigame")
	return all(getattr(nuigame, name, None) is not None for name in ("ChatAttach", "ViewState", "AnchorState"))


def has_engine_3a():
	"""True when the exe has the Wave 3a engine as well: nuigame.NuiStats.
	Only the chat's closed view needs it (nui-chat-lines mode="off"); the
	Wave 3a windows need has_engine() alone."""
	if not has_engine_2b():
		return False
	return getattr(sys.modules.get("nuigame"), "NuiStats", None) is not None


def has_engine_5a():
	"""True when the exe has the Wave 5a engine as well: nuigame.QuestAttach,
	QuestState and WebPageFollow (P12 spec 3.4, 6.4). The quest dialog and the
	web window need it; the guild building window and the console need
	has_engine() alone."""
	if not has_engine_3a():
		return False
	nuigame = sys.modules.get("nuigame")
	return all(getattr(nuigame, name, None) is not None for name in ("QuestAttach", "QuestState", "WebPageFollow"))


def has_engine_3b():
	"""True when the exe has the Wave 3b engine as well (P14 spec 4.9.4):
	_nui.FollowPointer (pointer placement, the marker) and the nui-cells
	decorator (nui.has_decorator). Every Wave 3b facade's nui_ready() needs
	it, so make() keeps the legacy window on an older exe."""
	if not has_engine():
		return False
	if getattr(getattr(nui, "_nui", None), "FollowPointer", None) is None:
		return False
	has = getattr(nui, "has_decorator", None)
	return has is not None and bool(has("nui-cells"))


def has_engine_4():
	"""True when the exe has the Wave 4 engine as well (P16 spec 4.3, 7.5):
	nuigame.WatchLeaveRange (the trade windows' distance rule),
	nuigame.WhisperAttach (the whisper lines) and _nui.LoadDocumentAs (the
	instanced documents). Every Wave 4 facade's nui_ready() needs it, so
	make() keeps the legacy window on an older exe."""
	if not has_engine_3b():
		return False
	nuigame = sys.modules.get("nuigame")
	if any(getattr(nuigame, name, None) is None for name in ("WatchLeaveRange", "WhisperAttach")):
		return False
	return getattr(getattr(nui, "_nui", None), "LoadDocumentAs", None) is not None


def take_over(key, facade):
	"""Destroys the NovaUI parts of the previous facade registered under `key`
	if they are still alive (a phase that ended without Destroy, D26), then
	records `facade`. Each module calls it first in its constructor."""
	previous = _facades.get(key)
	if previous is not None and previous is not facade:
		discard = getattr(previous, "nui_discard", None)
		if discard is not None:
			discard()
	_facades[key] = facade


def forget(key, facade):
	"""Destroy() and nui_discard() call it: drops the record when it is this
	facade's."""
	if _facades.get(key) is facade:
		del _facades[key]


def current(key):
	"""The facade registered under `key`, or None."""
	return _facades.get(key)


class _EscapeWindow(ui.Window):
	"""The legacy window behind an EscapeProxy: 0 x 0, so never picked."""

	def __init__(self, action, layer="UI", exit_action=None):
		ui.Window.__init__(self, layer)
		self.SetWindowName("NuiEscapeProxy")
		self._action = action
		self._exit_action = exit_action

	def __del__(self):
		ui.Window.__del__(self)

	def OnPressEscapeKey(self):
		action = self._action
		if action is not None:
			action()
		return True

	def OnPressExitKey(self):
		action = self._exit_action
		if action is None:
			return False
		action()
		return True


def _mem_func(action):
	"""A bound method as a weak ui.__mem_func__, so a proxy keeps no facade
	alive; anything else as given."""
	mem_func = getattr(ui, "__mem_func__", None)
	if mem_func is not None and hasattr(action, "__self__"):
		return mem_func(action)
	return action


class EscapeProxy(object):
	"""A 0 x 0 legacy ui.Window, shown while its NovaUI window is shown, whose
	OnPressEscapeKey runs `action` (None: nothing) and returns True. It keeps
	the window's place in the legacy Escape chain
	(CWindow::RunPressEscapeKeyEvent, PythonWindow.cpp:643-659), so Escape
	acts in the legacy order whatever NovaUI document has the focus. It is
	never picked (no area).

	`layer` is the proxy's legacy layer, "UI" (the default) or "TOP_MOST":
	the chain walks each layer's children last first, and the TOP_MOST
	layer before the UI layer, so a TOP_MOST proxy comes before every
	UI-layer window, as a legacy TOP_MOST window would. `exit_action`, when
	given, is run by the proxy's OnPressExitKey, which then returns True
	(the window's close button and WM_CLOSE reach it through
	CWindowManager::RunPressExitKey, PythonWindowManager.cpp:1486-1500);
	without it the proxy returns False there and the exit key goes on.
	`action` and `exit_action` are held as weak methods (ui.__mem_func__)
	when they are bound methods."""

	def __init__(self, action, layer="UI", exit_action=None):
		self._window = _EscapeWindow(_mem_func(action), layer, _mem_func(exit_action))
		self._window.SetSize(0, 0)
		self._window.Hide()

	def show(self):
		if self._window is not None:
			self._window.Show()
			self._window.SetTop()

	def hide(self):
		if self._window is not None:
			self._window.Hide()

	def is_shown(self):
		return self._window is not None and bool(self._window.IsShow())

	def destroy(self):
		window, self._window = self._window, None
		if window is not None:
			window.Hide()
			window._action = None
			window._exit_action = None
			window.Destroy()


class RaisesOnPress(object):
	"""For the board (a nui.Window) of a legacy window whose uiscript makes it
	"float": legacy's window manager raises the UI-layer window under the
	pointer on every left and right press, before the press reaches it
	(CWindowManager::RunMouseLeftButtonDown and RunMouseRightButtonDown call
	SetTopUIWindow, PythonWindowManager.cpp:704-719). The raise puts the window
	first in the Escape chain and above the windows it overlaps, and runs its
	OnTop. A NovaUI board takes the press, so it raises its window itself:
	every mousedown handler of the board calls raise_for(button) before it
	acts, and the body's own mousedown (board_press, which RmlUi runs last as
	the press bubbles; each board's @nui.on("board_press") calls
	body_pressed(button)) raises only when no handler did, so a press that
	opens a dialog leaves that dialog above. The board's `_owner` is the
	window, whose SetTop raises the board and the legacy window (the window
	adds the "float" flag its uiscript gave legacy's, P14 V-1)."""

	_raised = False

	def raise_for(self, button):
		if button not in (0, 1) or self._raised:
			return
		self._raised = True
		self._owner.SetTop()

	def body_pressed(self, button):
		if self._raised:
			self._raised = False
			return
		if button in (0, 1):
			self._owner.SetTop()


def _weak(method):
	"""A bound method held weakly (its object may go first), else as given."""
	if method is None or not hasattr(method, "__self__"):
		return method
	ref = weakref.WeakMethod(method)

	def call():
		target = ref()
		if target is not None:
			target()
	return call


def _weak_fn(fn):
	"""A bound method held weakly, returning its result (None once its
	object went); anything else as given."""
	if fn is None or not hasattr(fn, "__self__"):
		return fn
	ref = weakref.WeakMethod(fn)

	def call(*args):
		target = ref()
		if target is None:
			return None
		return target(*args)
	return call


class OnDemand(object):
	"""A board (a nui.Window) that exists only while its window is shown:
	made at show(), destroyed at hide(), because RmlUi updates every loaded
	document each frame, shown or not. make() makes a new board; restore(board)
	runs after each make, to set the board's model and place from the
	facade's state; keep(board) runs before each destroy, to read back what
	the document holds (a moved window's place: element_box of its body).
	All three are held weakly when they are bound methods (the facade owns
	the OnDemand)."""

	def __init__(self, make, restore=None, keep=None):
		self._make = _weak_fn(make)
		self._restore = _weak_fn(restore)
		self._keep = _weak_fn(keep)
		self._board = None

	def _new(self):
		make = self._make
		if make is None:
			return None
		return make()

	def probe(self):
		"""Makes one board and destroys it: True when its document loaded. A
		board that is shown now answers for itself and stays."""
		if self._board is not None:
			return bool(self._board._doc)
		board = self._new()
		if board is None:
			return False
		loaded = bool(board._doc)
		board.destroy()
		return loaded

	def board(self):
		"""The board while shown, else None."""
		return self._board

	def show(self):
		"""Makes the board if there is none (then restore(board)), then shows
		it. True when it is shown; a board whose document did not load is
		destroyed again, and nothing shows."""
		board = self._board
		if board is None:
			board = self._new()
			if board is None:
				return False
			if not board._doc:
				board.destroy()
				return False
			self._board = board
			if self._restore is not None:
				self._restore(board)
			if self._board is not board:
				# restore() hid it again (a caller's Hide inside it).
				return False
		return bool(board.show())

	def hide(self):
		"""keep(board), then destroys it; nothing when there is none."""
		board = self._board
		if board is None:
			return
		self._board = None
		if self._keep is not None:
			self._keep(board)
		board.destroy()

	def is_shown(self):
		return self._board is not None and bool(self._board.is_visible())

	def destroy(self):
		"""hide() and forgets the callbacks."""
		self.hide()
		self._make = self._restore = self._keep = None


class LayoutCalls(object):
	"""The ui.ScriptWindow layout calls callers make on a Wave 3a facade
	(P11 spec 6.0.2): CSS places the window, so SetCenterPosition, Lock and
	Unlock do nothing (a modal replaces the lock), and GetWidth and GetHeight
	answer the shown board's box in pixels (0 while hidden). A facade keeps
	its OnDemand in `demand`."""

	demand = None

	def _box(self):
		board = self.demand.board() if self.demand is not None else None
		box = board.element_box("") if board is not None and board.is_visible() else None
		return box or (0, 0, 0, 0)

	def SetCenterPosition(self, x=0, y=0):
		pass

	def Lock(self):
		pass

	def Unlock(self):
		pass

	def GetWidth(self):
		return int(round(self._box()[2]))

	def GetHeight(self):
		return int(round(self._box()[3]))


def moved_place(board):
	"""The board's top left in dp when the player moved it away from the
	screen's center (a handle drag), else None: a window that was centered
	is centered again at its next show. For OnDemand's keep()."""
	box = board.element_box("")
	if not box:
		return None
	import wndMgr
	x, y, width, height = box
	if (abs(x + width / 2.0 - wndMgr.GetScreenWidth() / 2.0) <= 2
	        and abs(y + height / 2.0 - wndMgr.GetScreenHeight() / 2.0) <= 2):
		return None
	s = nui.get_scale() or 1.0
	return (x / s, y / s)


def keep_weakly(owner):
	"""A weak proxy to a board's facade (the owner rule: a board never keeps
	its facade alive); an object that takes no weak reference as it is."""
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


def _call(method):
	"""A weak method whose owner is gone does nothing."""
	if method is None:
		return
	try:
		method()
	except ReferenceError:
		pass


# FocusProxy.take() calls in progress. While another proxy takes wndMgr's
# focus, NovaUI's focus already sits on that proxy's field (RmlUi keeps one
# focus), so the proxy that loses wndMgr's focus must not move NovaUI's.
_taking = [0]


class _FocusWindow(ui.Window):
	"""The legacy window behind a FocusProxy: 0 x 0, so never picked. wndMgr
	calls OnKillFocus when another window takes its focus
	(CWindowManager::ActivateWindow) and OnSetFocus when it gives it back
	(DeactivateWindow); OnKeyDown passes every key on to the root window,
	as a legacy edit line passes the game keys it does not keep. A
	FocusProxy.take() of another proxy runs no `on_lost` here."""

	def __init__(self, on_lost, on_gained):
		ui.Window.__init__(self, "UI")
		self.SetWindowName("NuiFocusProxy")
		self._on_lost = on_lost
		self._on_gained = on_gained
		self._quiet = False

	def __del__(self):
		ui.Window.__del__(self)

	def OnKillFocus(self):
		if not self._quiet and not _taking[0]:
			_call(self._on_lost)

	def OnSetFocus(self):
		if not self._quiet:
			_call(self._on_gained)

	def OnKeyDown(self, key):
		return False


class FocusProxy(object):
	"""A 0 x 0 legacy ui.Window in the UI layer that holds wndMgr's focus
	while a NovaUI text field has NovaUI's, as a focused legacy edit line
	would hold it (ui.EditLine.SetFocus). Legacy code that asks whether the
	game window has the focus (game.py CheckFocus, :1112-1117) then answers
	as it would with the legacy chat: a world press closes the chat. When a
	legacy edit line takes wndMgr's focus, the proxy's OnKillFocus runs
	`on_lost` (the facade moves NovaUI's focus off its field); when wndMgr
	gives the focus back (the window that took it closed,
	PythonWindowManager.cpp:670-689), its OnSetFocus runs `on_gained` (the
	facade focuses its field again). Its OnKeyDown returns False, so the
	keys the host lets through while typing (F1 to F4, left Alt, Print
	Screen, left Ctrl) reach the game window as through a legacy edit line.
	Never picked (no area); `on_lost` and
	`on_gained` are held as weak methods; neither runs for take() and
	release() themselves, and `on_lost` does not run when another proxy
	takes the focus: its field already has NovaUI's (the chat window and
	the chat log each own one)."""

	def __init__(self, on_lost, on_gained):
		self._window = _FocusWindow(_weak(on_lost), _weak(on_gained))
		self._window.SetSize(0, 0)
		self._window.Show()

	def _quietly(self, call):
		window = self._window
		window._quiet = True
		try:
			call()
		finally:
			window._quiet = False

	def take(self):
		"""wndMgr.SetFocus on the proxy, unless it has it."""
		window = self._window
		if window is None or window.IsFocus():
			return
		_taking[0] += 1
		try:
			self._quietly(window.SetFocus)
		finally:
			_taking[0] -= 1

	def release(self):
		"""wndMgr.KillFocus on the proxy, when it has it; on_lost does not run."""
		window = self._window
		if window is None or not window.IsFocus():
			return
		self._quietly(window.KillFocus)

	def has_focus(self):
		return self._window is not None and bool(self._window.IsFocus())

	def destroy(self):
		self.release()
		window, self._window = self._window, None
		if window is not None:
			window._on_lost = None
			window._on_gained = None
			window.Hide()
			window.Destroy()


def locale_text(name, *args):
	"""localeInfo.<name>, called with args when it is a function (an SA or
	SNA entry; with no args it gets 0, which an SNA entry ignores), then
	nui.plain_text(); "" for a missing entry or one that does not format."""
	try:
		import localeInfo
	except ImportError:
		return ""
	value = getattr(localeInfo, name, None)
	if value is None:
		return ""
	if callable(value):
		try:
			value = value(*args) if args else value(0)
		except Exception:
			return ""
	return nui.plain_text(value)
