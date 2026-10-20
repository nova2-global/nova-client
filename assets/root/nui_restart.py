"""NovaUI restart dialog (nui/windows/restart/restart.rml).

While the "restart" window flag is on, Interface.__MakeDialogs makes
RestartDialog below through nui_windows.make() instead of
uiRestart.RestartDialog: the facade of the legacy dialog, with its name,
constructor and methods. game.OnGameOver opens it (Interface.OpenRestartDialog)
when the main character dies outside a duel, and the server's
CloseRestartWindow command closes it (Interface.CloseRestartDialog) when a
restart succeeds. Its buttons send /restart_here and /restart_town and leave
it open; the server refuses them for its first seconds (10 s here, 7 s in
the city) with an info line, as for legacy, and NovaUI shows no countdown
either. Escape and the exit key are kept and do nothing (an EscapeProxy with
no action), as legacy's OnPressEscapeKey and OnPressExitKey. The document
exists only while the dialog shows (nui_hud.OnDemand)."""

import net

import nui
import nui_hud

DOCUMENT = "nui/windows/restart/restart.rml"


class RestartBoard(nui.Window):
	"""The dialog's document; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "restart"

	def __init__(self, owner):
		self._owner = nui_hud.keep_weakly(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {}

	@nui.on("act")
	def on_act(self, what, button):
		if button != 0:
			return
		if what == "here":
			self._owner.RestartHere()
		elif what == "town":
			self._owner.RestartTown()


class RestartDialog(nui_hud.LayoutCalls):
	"""uiRestart.RestartDialog on NovaUI (Interface.dlgRestart)."""

	NUI_FACADE = True
	KEY = "restart"

	def __init__(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self.demand = None
		self.escapeProxy = None
		self.loaded = False
		if not nui_hud.has_engine():
			return
		try:
			self.demand = nui_hud.OnDemand(self._make_board)
			self.loaded = self.demand.probe()
			self.escapeProxy = nui_hud.EscapeProxy(None, exit_action=_keep_key)
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
		return RestartBoard(self)

	# --- the Interface's calls (uirestart.py:17-65) -----------------------------------

	def LoadDialog(self):
		"""The document loaded with the facade; legacy answers 1."""
		return 1

	def Destroy(self):
		self.nui_discard()

	def OpenDialog(self):
		self.Show()

	def Show(self):
		if self.demand is not None and self.demand.show():
			if self.escapeProxy is not None:
				self.escapeProxy.show()

	def Hide(self):
		if self.escapeProxy is not None:
			self.escapeProxy.hide()
		if self.demand is not None:
			self.demand.hide()

	def IsShow(self):
		return self.demand is not None and self.demand.is_shown()

	def SetTop(self):
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.bring_to_front()
		if self.escapeProxy is not None and self.escapeProxy.is_shown():
			self.escapeProxy.show()

	def Close(self):
		self.Hide()
		return True

	def RestartHere(self):
		net.SendChatPacket("/restart_here")

	def RestartTown(self):
		net.SendChatPacket("/restart_town")

	def OnPressExitKey(self):
		return True

	def OnPressEscapeKey(self):
		return True


def _keep_key():
	"""The exit key is kept and does nothing (uirestart.py:61-62)."""
	return None
