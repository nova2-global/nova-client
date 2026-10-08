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

	def __init__(self, action):
		ui.Window.__init__(self, "UI")
		self.SetWindowName("NuiEscapeProxy")
		self._action = action

	def __del__(self):
		ui.Window.__del__(self)

	def OnPressEscapeKey(self):
		action = self._action
		if action is not None:
			action()
		return True


class EscapeProxy(object):
	"""A 0 x 0 legacy ui.Window in the UI layer, shown while its NovaUI
	window is shown, whose OnPressEscapeKey runs `action` and returns True.
	It keeps the window's place in the legacy Escape chain
	(CWindow::RunPressEscapeKeyEvent, PythonWindow.cpp:643-659), so Escape
	acts in the legacy order whatever NovaUI document has the focus. It is
	never picked (no area). `action` is held as a weak method
	(ui.__mem_func__), so the proxy keeps no facade alive."""

	def __init__(self, action):
		mem_func = getattr(ui, "__mem_func__", None)
		if mem_func is not None and hasattr(action, "__self__"):
			action = mem_func(action)
		self._window = _EscapeWindow(action)
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
			window.Destroy()


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
