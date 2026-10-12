"""NovaUI help window (nui/windows/help/help.rml).

While the "help" window flag is on, Interface.__MakeHelpWindow makes
HelpWindow below through nui_windows.make() instead of uiHelp.HelpWindow:
the facade of the legacy window, with its name, constructor and methods. H
(game.py __PressHKey), the system menu's Help and the game buttons' Help
open it through Interface.OpenHelpWindow; the close event the Interface sets
(CloseHelpWindow) closes it, run by its close button, H, Escape and the exit
key, as legacy's.

Legacy's window is TOP_MOST and locked (Lock), so it takes every key and
click, behind the Interface's TOP_MOST curtain. The NovaUI help is a modal
(MODAL, body.nui-scrim): it takes every key and click itself, and its scrim
is the curtain, so the Interface shows its legacy curtain only for the
legacy help (a TOP_MOST bar would draw above every NovaUI document). Escape
and H reach its keydown handler; the exit key reaches it through a TOP_MOST
nui_hud.EscapeProxy, before every UI-layer window, as legacy's lock window
had it. Its document exists only while it shows (nui_hud.OnDemand)."""

import app

import nui
import nui_hud

DOCUMENT = "nui/windows/help/help.rml"

# RmlUi's key identifier for H (Include/RmlUi/Core/Input.h, KI_H = 19).
KEY_H = 19


class HelpBoard(nui.Window):
	"""The help's document; its events and keys go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "help"
	MODAL = True

	def __init__(self, owner):
		self._owner = nui_hud.keep_weakly(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {}

	def nui_key(self, event):
		return self._owner.nui_key(event)

	@nui.on("act")
	def on_act(self, what, button):
		if button == 0 and what == "close":
			self._owner.nui_close()


class HelpWindow(nui_hud.LayoutCalls):
	"""uiHelp.HelpWindow on NovaUI (Interface.wndHelp)."""

	NUI_FACADE = True
	KEY = "help"

	def __init__(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self.eventClose = 0
		self.demand = None
		self.escapeProxy = None
		self.loaded = False
		if not nui_hud.has_engine():
			return
		try:
			self.demand = nui_hud.OnDemand(self._make_board, self._restore_board)
			self.loaded = self.demand.probe()
			self.escapeProxy = nui_hud.EscapeProxy(self.nui_close, layer="TOP_MOST", exit_action=self.nui_close)
		except Exception:
			self.nui_discard()
			raise

	def nui_ready(self):
		return self.loaded and self.demand is not None and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		proxy, self.escapeProxy = self.escapeProxy, None
		if proxy is not None:
			proxy.destroy()
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(self.KEY, self)

	def _make_board(self):
		return HelpBoard(self)

	def _restore_board(self, board):
		board.element_on("", "keydown", board.nui_key)

	# --- the Interface's calls (uihelp.py) ---------------------------------------------

	def LoadDialog(self):
		"""The document loaded with the facade; nothing is left to do."""
		pass

	def Destroy(self):
		self.eventClose = 0
		self.nui_discard()

	def SetCloseEvent(self, event):
		self.eventClose = event

	def Open(self):
		"""Shown as a modal (no Lock: the modal takes the keys and clicks)."""
		if self.demand is not None and self.demand.show():
			if self.escapeProxy is not None:
				self.escapeProxy.show()

	def Show(self):
		self.Open()

	def Close(self):
		if self.escapeProxy is not None:
			self.escapeProxy.hide()
		if self.demand is not None:
			self.demand.hide()

	def Hide(self):
		self.Close()

	def IsShow(self):
		return self.demand is not None and self.demand.is_shown()

	def SetTop(self):
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.bring_to_front()

	# Legacy's key events (uihelp.py:48-65), for callers and the facade
	# check: the NovaUI help gets its keys from its own document.
	def OnKeyDown(self, key):
		if app.DIK_H == key and 0 != self.eventClose:
			self.eventClose()
		return True

	def OnIMEReturn(self):
		return True

	def OnPressEscapeKey(self):
		if 0 != self.eventClose:
			self.eventClose()
		return True

	def OnPressExitKey(self):
		if 0 != self.eventClose:
			self.eventClose()
		return True

	# --- the board's events --------------------------------------------------------------

	def nui_close(self):
		"""The close event the Interface set (its CloseHelpWindow closes the
		window), as legacy's close button, H, Escape and the exit key."""
		if self.eventClose:
			self.eventClose()

	def nui_key(self, event):
		"""Escape and H while shown run the close event and keep the key."""
		if not self.IsShow() or event.get("key_identifier") not in (nui.KEY_ESCAPE, KEY_H):
			return None
		self.nui_close()
		return True
