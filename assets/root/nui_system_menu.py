"""NovaUI system menu (nui/windows/system-menu/system-menu.rml).

While the "system-menu" window flag is on, Interface.__MakeDialogs makes
SystemDialog below through nui_windows.make() instead of
uiSystem.SystemDialog: the facade of the legacy menu, with its name,
constructor and the methods the Interface, game.py and C++ (through the
Interface: OnBlockMode, OnChangePKMode) call. Escape in game, the taskbar's
system button and the exit key open it; Escape and the exit key close it in
its legacy place (nui_hud.EscapeProxy). Its document exists only while it
shows (nui_hud.OnDemand), since RmlUi updates every loaded document each
frame; the constructor loads it once to answer nui_ready().

Each button closes the menu first and then makes legacy's calls, in
legacy's order (uisystem.py SystemDialog's handlers). The option windows are
made through uiSystemOption.OptionDialog and uiGameOption.OptionDialog, the
factories their own flags decide (P11 spec D7), once each, as legacy's.
Change channel (NOVA-49) opens legacy's uiSystem.MoveChannelDialog, made at
its first press, as legacy's menu does (it has no NovaUI window)."""

import net
import uiGameOption
import uiSystem
import uiSystemOption

import nui
import nui_hud

DOCUMENT = "nui/windows/system-menu/system-menu.rml"


class SystemMenuBoard(nui.Window):
	"""The menu's document and model; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "system_menu"

	def __init__(self, owner):
		self._owner = nui_hud.keep_weakly(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"show_mall": True}

	@nui.on("act")
	def on_act(self, what, button):
		if button == 0:
			self._owner.nui_act(what)


class SystemDialog(nui_hud.LayoutCalls):
	"""uiSystem.SystemDialog on NovaUI (Interface.dlgSystem)."""

	NUI_FACADE = True
	KEY = "system-menu"

	def __init__(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self.eventOpenHelpWindow = None
		self.systemOptionDlg = None
		self.gameOptionDlg = None
		# The change channel dialog (NOVA-49), made on its first open.
		self.moveChannelDlg = None
		self.demand = None
		self.escapeProxy = None
		self.loaded = False
		if not nui_hud.has_engine():
			return
		try:
			self.demand = nui_hud.OnDemand(self._make_board, self._restore_board)
			self.loaded = self.demand.probe()
			self.escapeProxy = nui_hud.EscapeProxy(self.Close, layer="UI", exit_action=self.Close)
		except Exception:
			self.nui_discard()
			raise

	# --- the make() protocol ------------------------------------------------------

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
		return SystemMenuBoard(self)

	def _restore_board(self, board):
		board.set(show_mall=True)
		board.center()

	# --- the Interface's calls -------------------------------------------------------

	def LoadDialog(self):
		"""The document loaded with the facade; nothing is left to do."""
		pass

	def Destroy(self):
		"""As uisystem.py SystemDialog.Destroy: the option windows and the
		change channel dialog it made go first."""
		if self.gameOptionDlg:
			self.gameOptionDlg.Destroy()
		if self.systemOptionDlg:
			self.systemOptionDlg.Destroy()
		if self.moveChannelDlg:
			self.moveChannelDlg.Destroy()
		self.eventOpenHelpWindow = None
		self.systemOptionDlg = None
		self.gameOptionDlg = None
		self.moveChannelDlg = None
		self.nui_discard()

	def SetOpenHelpWindowEvent(self, event):
		self.eventOpenHelpWindow = event

	def OpenDialog(self):
		self.Show()

	def Show(self):
		if self.demand is not None and self.demand.show():
			if self.escapeProxy is not None:
				self.escapeProxy.show()
		nui_hud.tell_taskbar("system", self.IsShow())

	def Hide(self):
		if self.escapeProxy is not None:
			self.escapeProxy.hide()
		if self.demand is not None:
			self.demand.hide()
		nui_hud.tell_taskbar("system", self.IsShow())

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

	def OnBlockMode(self, mode):
		uiGameOption.blockMode = mode
		if self.gameOptionDlg:
			self.gameOptionDlg.OnBlockMode(mode)

	def OnChangePKMode(self):
		if self.gameOptionDlg:
			self.gameOptionDlg.OnChangePKMode()

	def OnPressExitKey(self):
		self.Close()
		return True

	def OnPressEscapeKey(self):
		self.Close()
		return True

	# --- the buttons (uisystem.py SystemDialog's handlers) ------------------------------

	def nui_act(self, what):
		"""A button pressed: the menu closes first, then legacy's calls."""
		self.Close()
		if what == "help":
			if self.eventOpenHelpWindow is not None:
				self.eventOpenHelpWindow()
		elif what == "mall":
			net.SendChatPacket("/in_game_mall")
		elif what == "system_options":
			if not self.systemOptionDlg:
				self.systemOptionDlg = uiSystemOption.OptionDialog()
			self.systemOptionDlg.Show()
		elif what == "game_options":
			if not self.gameOptionDlg:
				self.gameOptionDlg = uiGameOption.OptionDialog()
			self.gameOptionDlg.Show()
		elif what == "move_channel":
			if not self.moveChannelDlg:
				self.moveChannelDlg = uiSystem.MoveChannelDialog()
			self.moveChannelDlg.Open()
		elif what == "change":
			net.ExitGame()
		elif what == "logout":
			net.LogOutGame()
		elif what == "exit":
			net.ExitApplication()
