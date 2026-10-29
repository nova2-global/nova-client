###################################################################################################
# Network

import app
import chr
import dbg
import net
import snd

import chr
import chrmgr
import background
import player
import playerSettingModule

import ui
import uiPhaseCurtain
import nui_windows

import localeInfo

class PopupDialog(ui.ScriptWindow):
	# MR-15: Multiline dialog messages
	BASE_HEIGHT = 105
	BASE_WIDTH = 280
	BUTTON_Y = 63
	LINE_HEIGHT = 12
	# MR-15: -- END OF -- Multiline dialog messages

	def __init__(self):
		print("NEW POPUP DIALOG ----------------------------------------------------------------------------")
		ui.ScriptWindow.__init__(self)
		self.CloseEvent = 0

	def __del__(self):
		print("---------------------------------------------------------------------------- DELETE POPUP DIALOG ")
		ui.ScriptWindow.__del__(self)

	def LoadDialog(self):
		PythonScriptLoader = ui.PythonScriptLoader()
		PythonScriptLoader.LoadScriptFile(self, "UIScript/PopupDialog.py")

	def Open(self, Message, event = 0, ButtonName = None):
		if ButtonName is None:
			ButtonName = localeInfo.UI_CANCEL

		if True == self.IsShow():
			self.Close()

		nui_windows.legacy_dialog_layer(self)
		self.Lock()
		self.SetTop()
		self.CloseEvent = event

		AcceptButton = self.GetChild("accept")
		AcceptButton.SetText(ButtonName)
		AcceptButton.SetEvent(ui.__mem_func__(self.Close))

		# MR-15: Multiline dialog messages
		messageWidget = self.GetChild("message")
		messageWidget.SetText(Message)

		extraH = len(messageWidget.extraLines) * self.LINE_HEIGHT + 2
		newH = self.BASE_HEIGHT + extraH
		self.SetSize(self.BASE_WIDTH, newH)
		self.GetChild("board").SetSize(self.BASE_WIDTH, newH)
		AcceptButton.SetPosition(0, self.BUTTON_Y + extraH)

		self.SetCenterPosition()
		self.UpdateRect()
		# MR-15: -- END OF -- Multiline dialog messages
		self.Show()

	def Close(self):

		if False == self.IsShow():
			self.CloseEvent = 0
			return

		self.Unlock()
		self.Hide()

		if 0 != self.CloseEvent:
			self.CloseEvent()
			self.CloseEvent = 0

	def Destroy(self):
		self.Close()
		self.ClearDictionary()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def OnIMEReturn(self):
		self.Close()
		return True

##
## Main Stream
##
class MainStream(object):
	isChrData=0	

	def __init__(self):
		print("NEWMAIN STREAM ----------------------------------------------------------------------------")
		net.SetHandler(self)
		net.SetTCPRecvBufferSize(128*1024)
		net.SetTCPSendBufferSize(4096)

		self.id=""
		self.pwd=""
		self.addr=""
		self.port=0
		self.account_addr=0
		self.account_port=0
		self.slot=0
		self.isAutoSelect=0
		self.isAutoLogin=0

		self.curtain = 0
		self.curPhaseWindow = 0
		self.newPhaseWindow = 0

	def __del__(self):
		print("---------------------------------------------------------------------------- DELETE MAIN STREAM ")

	def Destroy(self):
		if self.curPhaseWindow:
			self.curPhaseWindow.Close()
			self.curPhaseWindow = 0

		if self.newPhaseWindow:
			self.newPhaseWindow.Close()
			self.newPhaseWindow = 0

		self.popupWindow.Destroy()
		self.popupWindow = 0

		self.curtain = 0

	def Create(self):
		self.CreatePopupDialog()

		self.curtain = uiPhaseCurtain.PhaseCurtain()

	def SetPhaseWindow(self, newPhaseWindow):
		if self.newPhaseWindow:
			#print "Already in the process of changing to a new phase, skip", newPhaseWindow
			self.__ChangePhaseWindow()

		self.newPhaseWindow=newPhaseWindow

		if self.curPhaseWindow:
			#print "Change after fade out"
			self.curtain.FadeOut(self.__ChangePhaseWindow)
		else:
			#print "Change immediately if there's no current phase"
			self.__ChangePhaseWindow()

	def __ChangePhaseWindow(self):
		oldPhaseWindow=self.curPhaseWindow
		newPhaseWindow=self.newPhaseWindow
		self.curPhaseWindow=0
		self.newPhaseWindow=0

		if oldPhaseWindow:
			oldPhaseWindow.Close()
			# NovaUI: the documents the ended phase shared (the dialog kit's) unload; the next phase loads what it shows.
			nui_windows.end_phase()

		if newPhaseWindow:
			newPhaseWindow.Open()
			# NovaUI: the game phase queues its on-demand documents for a prewarm in calm frames.
			nui_windows.start_phase(newPhaseWindow)

		self.curPhaseWindow=newPhaseWindow
		
		if self.curPhaseWindow:
			self.curtain.FadeIn()
		else:
			app.Exit()

	def CreatePopupDialog(self):
		self.popupWindow = PopupDialog()
		self.popupWindow.LoadDialog()
		self.popupWindow.SetCenterPosition()
		self.popupWindow.Hide()


	## SelectPhase
	##########################################################################################	
	def SetLoginPhase(self):
		net.Disconnect()

		import introLogin
		self.SetPhaseWindow(introLogin.LoginWindow(self))

	def SameLogin_SetLoginPhase(self):
		net.Disconnect()
        
		import introLogin
		introInst = introLogin.LoginWindow(self)
		self.SetPhaseWindow(introInst)
		introInst.SameLogin_OpenUI()
		
	def SetSelectEmpirePhase(self):
		try:
			import introEmpire	
			self.SetPhaseWindow(nui_windows.make("empire", introEmpire.SelectEmpireWindow, "nui_empire.SelectEmpireWindow", self))
		except:
			import exception
			exception.Abort("networkModule.SetSelectEmpirePhase")


	def SetReselectEmpirePhase(self):
		try:
			import introEmpire
			self.SetPhaseWindow(nui_windows.make("empire", introEmpire.ReselectEmpireWindow, "nui_empire.ReselectEmpireWindow", self))
		except:
			import exception
			exception.Abort("networkModule.SetReselectEmpirePhase")

	def SetSelectCharacterPhase(self):
		try:
			localeInfo.LoadLocaleData()
			import introSelect
			self.popupWindow.Close()
			self.SetPhaseWindow(nui_windows.make("select", introSelect.SelectCharacterWindow, "nui_select.SelectCharacterWindow", self))
		except:
			import exception
			exception.Abort("networkModule.SetSelectCharacterPhase")

	def SetCreateCharacterPhase(self):
		try:
			import introCreate
			self.SetPhaseWindow(nui_windows.make("create", introCreate.CreateCharacterWindow, "nui_create.CreateCharacterWindow", self))
		except:
			import exception
			exception.Abort("networkModule.SetCreateCharacterPhase")

	def SetTestGamePhase(self, x, y):
		try:
			import introLoading
			loadingPhaseWindow=nui_windows.make("loading", introLoading.LoadingWindow, "nui_loading.LoadingWindow", self)
			loadingPhaseWindow.LoadData(x, y)
			self.SetPhaseWindow(loadingPhaseWindow)
		except:
			import exception
			exception.Abort("networkModule.SetLoadingPhase")



	def SetLoadingPhase(self):
		try:
			import introLoading
			self.SetPhaseWindow(nui_windows.make("loading", introLoading.LoadingWindow, "nui_loading.LoadingWindow", self))
		except:
			import exception
			exception.Abort("networkModule.SetLoadingPhase")

	def SetGamePhase(self):
		try:
			import game
			self.popupWindow.Close()
			self.SetPhaseWindow(game.GameWindow(self))
		except:
			raise
			import exception
			exception.Abort("networkModule.SetGamePhase")
		self.__NoteSavedAccount()

	def __NoteSavedAccount(self):
		"""NovaUI's login screen remembers the account (nui_accounts.py) when
		it asked to: the select screen's characters with their levels, and
		the one played. Never a password. A failure here never stops the
		game."""
		try:
			import introSelect
			import nui_accounts
			slots = []
			for index in range(introSelect.SelectCharacterWindow.SLOT_COUNT):
				if net.GetAccountCharacterSlotDataInteger(index, net.ACCOUNT_CHARACTER_SLOT_ID):
					slots.append((net.GetAccountCharacterSlotDataString(index, net.ACCOUNT_CHARACTER_SLOT_NAME),
						net.GetAccountCharacterSlotDataInteger(index, net.ACCOUNT_CHARACTER_SLOT_RACE),
						net.GetAccountCharacterSlotDataInteger(index, net.ACCOUNT_CHARACTER_SLOT_LEVEL)))
			nui_accounts.note_game_start(getattr(self, "id", ""), player.GetName(), slots)
		except Exception as error:
			dbg.TraceError("networkModule: the saved account was not written (%s)" % type(error).__name__)

	################################
	# Functions used in python

	## Login
	def Connect(self):		
		import constInfo
		if constInfo.KEEP_ACCOUNT_CONNETION_ENABLE:
			net.ConnectToAccountServer(self.addr, self.port, self.account_addr, self.account_port)
		else:
			net.ConnectTCP(self.addr, self.port)

		#net.ConnectUDP(IP, Port)

	def SetConnectInfo(self, addr, port, account_addr=0, account_port=0):
		self.addr = addr
		self.port = port
		self.account_addr = account_addr
		self.account_port = account_port

	def GetConnectAddr(self):
		return self.addr

	def SetLoginInfo(self, id, pwd):
		self.id = id
		self.pwd = pwd
		net.SetLoginInfo(id, pwd)

	def CancelEnterGame(self):
		pass

	## Select
	def SetCharacterSlot(self, slot):
		self.slot=slot

	def GetCharacterSlot(self):
		return self.slot

	## Empty
	def EmptyFunction(self):
		pass

# NovaUI dialog kit (nui_dialog_message.py, flag "dialogs"): with the flag on
# this name makes the NovaUI phase popup (MainStream.CreatePopupDialog names
# it); with it off, the legacy class above.
LegacyPopupDialog = PopupDialog
PopupDialog = nui_windows.factory("dialogs", LegacyPopupDialog, "nui_dialog_message.PhasePopupDialog")
