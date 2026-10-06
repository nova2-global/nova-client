"""NovaUI expanded taskbar (nui/windows/expanded-taskbar/expanded-taskbar.rml).

While the "expanded-taskbar" window flag is on, Interface.__MakeTaskBar makes
ExpandedTaskBar below through nui_windows.make() instead of
uiTaskBar.ExpandedTaskBar: the facade of the legacy class, with its one
button (the dragon soul window) and its hint. Escape closes it as the
legacy window's OnPressEscapeKey did, in the same place of the legacy
Escape chain (nui_hud.EscapeProxy, shown while the bar shows)."""

import weakref

import nui
import nui_hud

DOCUMENT = "nui/windows/expanded-taskbar/expanded-taskbar.rml"


def _keep(owner):
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


class ExpandedTaskBarBoard(nui.Window):
	DOCUMENT = DOCUMENT
	MODEL = "expanded_taskbar"

	def __init__(self, owner):
		self._owner = _keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"tip": "@ui.TASKBAR_DISABLE"}

	@nui.on("dragon_soul")
	def on_dragon_soul(self, button):
		if button == 0:
			self._owner.nui_press(self._owner.BUTTON_DRAGON_SOUL)


class ExpandedTaskBar(object):
	"""uiTaskBar.ExpandedTaskBar on NovaUI (the wndExpandedTaskBar facade)."""

	NUI_FACADE = True
	BUTTON_DRAGON_SOUL = 0

	def __init__(self):
		nui_hud.take_over("expanded-taskbar", self)
		self._nui_discarded = False
		self.board = None
		self.escape = None
		self.toggleButtonEvents = {}
		if not nui_hud.has_engine():
			return
		try:
			self.board = ExpandedTaskBarBoard(self)
			self.escape = nui_hud.EscapeProxy(self.Close)
		except Exception:
			self.nui_discard()
			raise

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		escape, self.escape = self.escape, None
		if escape is not None:
			escape.destroy()
		board, self.board = self.board, None
		if board is not None:
			board.destroy()
		nui_hud.forget("expanded-taskbar", self)

	def LoadWindow(self):
		"""The document loaded with the facade; nothing is left to do."""
		pass

	def Destroy(self):
		self.nui_discard()

	def Show(self):
		if self.board is not None:
			self.board.show()
			if self.escape is not None:
				self.escape.show()

	def Hide(self):
		if self.board is not None:
			self.board.hide()
		if self.escape is not None:
			self.escape.hide()

	def Close(self):
		self.Hide()

	def IsShow(self):
		return self.board is not None and self.board.is_visible()

	def SetTop(self):
		if self.board is not None:
			self.board.bring_to_front()
		if self.escape is not None and self.escape.is_shown():
			self.escape.show()

	def SetToolTipText(self, eButton, text):
		if eButton == self.BUTTON_DRAGON_SOUL and self.board is not None:
			self.board.set(tip=nui.plain_text(text))

	def SetToggleButtonEvent(self, eButton, kEventFunc):
		self.toggleButtonEvents[eButton] = kEventFunc

	def nui_press(self, eButton):
		event = self.toggleButtonEvents.get(eButton)
		if event:
			event()
