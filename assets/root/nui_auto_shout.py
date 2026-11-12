"""NovaUI auto-shout window (nui/windows/auto-shout/auto-shout.rml; NOVA-204).

While the auto-shout flag is on, the Interface makes AutoShoutWindow below
through nui_windows.make() instead of uiAutoShout.AutoShoutWindow: a
subclass of the legacy class (nui_facade.Facade) whose loader puts proxies
where the widgets were, so Open (the field with the character's message),
Start and Stop (autoshout.start, autoshout.stop), Enter and Escape in the
field and Close are legacy's code. The board exists only while it shows,
centered at its first open (then where the player moved it).

The state comes from autoshout.py (its listener, OnAutoShoutChanged):
`state` is "off", "waiting" (Start sent, no server state yet) or "on"; the
time to the next shout is a nui-countdown (format "ms") whose end is
nui.now() plus the seconds the server's last AutoShoutState gave, set again
at each state message; at its end (countdownend) it goes on by the interval,
in case the next state message is late. No Python runs per frame. While its
field has NovaUI's focus the window holds wndMgr's (nui_hud.FocusProxy), so
game keys stay out of it, as a focused legacy edit line would."""

import ui
import uiAutoShout

import autoshout
import nui
import nui_facade
import nui_form_proxies
import nui_hud
import nui_proxies

DOCUMENT = "nui/windows/auto-shout/auto-shout.rml"
KEY = "auto-shout"
FIELD = "auto-shout-message"
# The control that parks NovaUI's focus when a legacy edit line takes wndMgr's.
PARK = "auto-shout-toggle"
MESSAGE_MAX = 255


class _AutoShoutBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The window's document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "auto_shout"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)
		if self._doc:
			self.element_on(FIELD, "keydown", self._on_key)
			self.element_on(FIELD, "focus", self._on_focus)

	def initial_model(self):
		return dict(self._initial)

	def _on_key(self, event):
		if not self.is_visible():
			return None
		return self._owner.nui_key(event.get("key_identifier"))

	def _on_focus(self, event):
		self._owner.nui_field_focused()

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("field_press")
	def on_field_press(self, button):
		self.raise_for(button)
		if button == 0:
			self.focus(FIELD)

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.board.close()

	@nui.on("toggle_press")
	def on_toggle_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.toggleButton.click()

	@nui.on("countdown_end")
	def on_countdown_end(self):
		self._owner.nui_countdown_end()


class AutoShoutWindow(nui_facade.Facade, uiAutoShout.AutoShoutWindow):
	"""uiAutoShout.AutoShoutWindow on NovaUI (Interface.wndAutoShout)."""

	KEY = KEY
	BOARD = _AutoShoutBoard
	PLACE = "center"
	OnUpdate = None

	def __init__(self):
		self.focusProxy = None
		self.nui_begin()
		try:
			uiAutoShout.AutoShoutWindow.__init__(self)
			if self.demand is not None:
				self.focusProxy = nui_hud.FocusProxy(self._on_focus_lost, self._on_focus_gained)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {"state": "off", "next_end": 0.0, "interval": 0, "message_max": MESSAGE_MAX}

	def nui_discard(self):
		autoshout.forget(self)
		proxy, self.focusProxy = getattr(self, "focusProxy", None), None
		if proxy is not None:
			proxy.destroy()
		nui_facade.Facade.nui_discard(self)

	# --- the loader (uiautoshout.py, on proxies) ---------------------------------------

	def _value(self):
		board = self.nui_board()
		return board.get_value(FIELD) if board is not None and board.is_visible() else None

	def _on_field(self, field, what):
		board = self.nui_board()
		if board is None or not board.is_visible():
			return
		if what == "text":
			board.set_value(FIELD, field.text, caret="end")
		elif what == "focus":
			board.focus(FIELD)
		elif what == "kill_focus":
			board.focus(PARK)

	def _AutoShoutWindow__LoadWindow(self):
		self.AddFlag("movable")
		self.AddFlag("float")
		self.board = nui_proxies.BoardProxy(330, 160)
		self.messageLine = nui_form_proxies.FieldProxy(FIELD, self._on_field)
		self.messageLine.reader = self._value
		self.messageLine.SetMax(MESSAGE_MAX)
		self.statusText = nui_proxies.TextProxy()
		self.nextText = nui_proxies.TextProxy()
		self.toggleButton = nui_proxies.ButtonProxy()

		self.board.SetCloseEvent(ui.__mem_func__(self.Close))
		self.messageLine.SetReturnEvent(ui.__mem_func__(self.OnToggle))
		self.messageLine.SetEscapeEvent(ui.__mem_func__(self.Close))
		self.toggleButton.SetEvent(ui.__mem_func__(self.OnToggle))
		self.isLoaded = True

	# --- what NovaUI changes -----------------------------------------------------------

	def OnAutoShoutChanged(self):
		"""The state and the countdown's end, from autoshout's state."""
		if not self.isLoaded:
			return
		state = self.shownState = self.State()
		values = {"state": state, "interval": autoshout.interval()}
		if state == "on":
			values["next_end"] = nui.now() + float(autoshout.seconds_left())
		else:
			values["next_end"] = 0.0
		self.nui_set(**values)

	def nui_countdown_end(self):
		"""No state message at the expected shout: on by the interval."""
		step = int(self._state.get("interval") or 0)
		if self._state.get("state") == "on" and step > 0:
			self.nui_set(next_end=float(self._state.get("next_end") or nui.now()) + step)

	def Show(self):
		nui_facade.Facade.Show(self)
		board = self.nui_board()
		if board is None:
			return
		board.set_value(FIELD, self.messageLine.text or "", caret="end")
		if self.messageLine.focused:
			board.focus(FIELD)

	def Hide(self):
		nui_facade.Facade.Hide(self)
		if not self.IsShow() and getattr(self, "focusProxy", None) is not None:
			self.focusProxy.release()

	def Close(self):
		"""Legacy's; the field's text stays for the next open's prefill."""
		self.messageLine.GetText()
		uiAutoShout.AutoShoutWindow.Close(self)

	# --- the field's keys and focus ----------------------------------------------------

	def nui_key(self, key):
		if key in (nui.KEY_RETURN, nui.KEY_NUMPADENTER):
			self.messageLine.fire_return()
			return True
		if key == nui.KEY_ESCAPE:
			self.messageLine.fire_escape()
			return True
		return None

	def nui_field_focused(self):
		if self.focusProxy is not None:
			self.focusProxy.take()

	def _on_focus_lost(self):
		board = self.nui_board()
		if board is not None:
			board.focus(PARK)

	def _on_focus_gained(self):
		board = self.nui_board()
		if board is not None and board.is_visible():
			board.focus(FIELD)
