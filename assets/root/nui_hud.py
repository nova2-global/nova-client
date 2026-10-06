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
