import net
import app
import ui

import uiSystemOption
import uiGameOption
import uiScriptLocale
import networkModule
import constInfo
import localeInfo

###################################################################################################
## System
class SystemDialog(ui.ScriptWindow):

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.__Initialize()
	
	def __Initialize(self):
		self.eventOpenHelpWindow = None
		self.systemOptionDlg = None
		self.gameOptionDlg = None
		# The change channel dialog (NOVA-49), made on its first open.
		self.moveChannelDlg = None
		
		
	def LoadDialog(self):	
		self.__LoadSystemMenu_Default()
			
	def __LoadSystemMenu_Default(self):
		pyScrLoader = ui.PythonScriptLoader()
		pyScrLoader.LoadScriptFile(self, "uiscript/systemdialog.py")

		self.GetChild("system_option_button").SAFE_SetEvent(self.__ClickSystemOptionButton)
		self.GetChild("game_option_button").SAFE_SetEvent(self.__ClickGameOptionButton)
		self.GetChild("change_button").SAFE_SetEvent(self.__ClickChangeCharacterButton)
		self.GetChild("logout_button").SAFE_SetEvent(self.__ClickLogOutButton)
		self.GetChild("exit_button").SAFE_SetEvent(self.__ClickExitButton)
		self.GetChild("help_button").SAFE_SetEvent(self.__ClickHelpButton)
		self.GetChild("cancel_button").SAFE_SetEvent(self.Close)
		self.GetChild("mall_button").SAFE_SetEvent(self.__ClickInGameShopButton)
		self.GetChild("movechannel_button").SAFE_SetEvent(self.__ClickMoveChannelButton)

	def Destroy(self):
		self.ClearDictionary()
		
		if self.gameOptionDlg:
			self.gameOptionDlg.Destroy()
			
		if self.systemOptionDlg:
			self.systemOptionDlg.Destroy()

		if self.moveChannelDlg:
			self.moveChannelDlg.Destroy()
			
		self.__Initialize()

	def SetOpenHelpWindowEvent(self, event):
		self.eventOpenHelpWindow = event

	def OpenDialog(self):
		self.Show()

	def __ClickChangeCharacterButton(self):
		self.Close()

		net.ExitGame()

	def __OnClosePopupDialog(self):
		self.popup = None		

	def __ClickLogOutButton(self):
		self.Close()
		net.LogOutGame()


	def __ClickExitButton(self):
		self.Close()
		net.ExitApplication()
		
	def __ClickSystemOptionButton(self):
		self.Close()

		if not self.systemOptionDlg:
			self.systemOptionDlg = uiSystemOption.OptionDialog()

		self.systemOptionDlg.Show()

	def __ClickGameOptionButton(self):
		self.Close()

		if not self.gameOptionDlg:
			self.gameOptionDlg = uiGameOption.OptionDialog()

		self.gameOptionDlg.Show()

	
	def __ClickHelpButton(self):
		self.Close()

		if None != self.eventOpenHelpWindow:
			self.eventOpenHelpWindow()

	def __ClickInGameShopButton(self):
		self.Close()
		net.SendChatPacket("/in_game_mall")

	# Change channel (NOVA-49, OLD uiSystem.py:185-200).
	def __ClickMoveChannelButton(self):
		self.Close()

		if not self.moveChannelDlg:
			self.moveChannelDlg = MoveChannelDialog()

		self.moveChannelDlg.Open()

	def Close(self):
		self.Hide()
		return True

	def OnBlockMode(self, mode):
		uiGameOption.blockMode = mode
		if self.gameOptionDlg:
			self.gameOptionDlg.OnBlockMode(mode)
		#self.optionDialog.OnBlockMode(mode)

	def OnChangePKMode(self):
		if self.gameOptionDlg:
			self.gameOptionDlg.OnChangePKMode()
		#self.optionDialog.OnChangePKMode()
	
	def OnPressExitKey(self):
		self.Close()
		return True

	def OnPressEscapeKey(self):
		self.Close()
		return True

###################################################################################################
## Change channel (NOVA-49, OLD uiSystem.py:221-300)
# One button per channel of the server the player logged in through
# (serverInfo.REGION_DICT, constInfo.GET_LOGIN_SERVER_CHANNELS); the selected
# one, at first the channel the player is on (net.GetChannelNum), is down and
# disabled. MOVE_CHANNEL_SELECT asks the server for the selected channel with
# "/ch N" (the server checks the move and warps the character), and
# MOVE_CHANNEL_CANCEL closes. OLD's select_btn art is in neither NEW's assets
# nor OLD's source tree: NEW's middle buttons stand in.
class MoveChannelDialog(ui.ScriptWindow):

	WIDTH = 190
	BUTTON_PATH = "d:/ymir work/ui/public/"
	CHANNEL_BUTTON_HEIGHT = 23
	CHANNEL_BUTTON_GAP = 5

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.board = None
		self.channelBoard = None
		self.acceptButton = None
		self.cancelButton = None
		self.channelButtonList = []
		self.channelNumberList = []
		self.currentChannel = 0
		self.selectedChannel = 0
		self.__LoadDialog()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadDialog(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "uiscript/movechanneldialog.py")
		except:
			import exception
			exception.Abort("MoveChannelDialog.__LoadDialog.LoadScript")

		try:
			self.board = self.GetChild("MoveChannelBoard")
			self.channelBoard = self.GetChild("BlackBoard")
			self.GetChild("MoveChannelTitle").SetCloseEvent(ui.__mem_func__(self.Close))
		except:
			import exception
			exception.Abort("MoveChannelDialog.__LoadDialog.BindObject")

		self.acceptButton = self.__MakeButton(self.board, 13, 0, localeInfo.MOVE_CHANNEL_SELECT)
		self.acceptButton.SetEvent(ui.__mem_func__(self.Accept))

		self.cancelButton = self.__MakeButton(self.board, self.WIDTH - 73, 0, localeInfo.MOVE_CHANNEL_CANCEL)
		self.cancelButton.SetEvent(ui.__mem_func__(self.Close))

	# A middle button with `text` at (x, y) of `parent`, as OLD's ui.MakeButton
	# calls made them.
	def __MakeButton(self, parent, x, y, text):
		button = ui.Button()
		button.SetParent(parent)
		button.SetPosition(x, y)
		button.SetUpVisual(self.BUTTON_PATH + "middle_button_01.sub")
		button.SetOverVisual(self.BUTTON_PATH + "middle_button_02.sub")
		button.SetDownVisual(self.BUTTON_PATH + "middle_button_03.sub")
		button.SetText(text)
		button.Show()
		return button

	def Destroy(self):
		self.ClearDictionary()
		self.board = None
		self.channelBoard = None
		self.acceptButton = None
		self.cancelButton = None
		self.channelButtonList = []
		self.channelNumberList = []

	# The login server's channels, a button each, and the dialog sized to
	# them (OLD's sizes).
	def __BuildChannelButtons(self):
		channelNumberList = constInfo.GET_LOGIN_SERVER_CHANNELS()
		if channelNumberList == self.channelNumberList and self.channelButtonList:
			return

		for button in self.channelButtonList:
			button.Hide()
		self.channelButtonList = []
		self.channelNumberList = list(channelNumberList)

		step = self.CHANNEL_BUTTON_HEIGHT + self.CHANNEL_BUTTON_GAP
		for index, channel in enumerate(self.channelNumberList):
			button = self.__MakeButton(self.channelBoard, 8, 6 + index * step, "%s %d" % (localeInfo.CHANNEL, channel))
			button.SetEvent(ui.__mem_func__(self.SelectChannel), channel)
			self.channelButtonList.append(button)

		count = max(len(self.channelNumberList), 1)
		channelBoardHeight = self.CHANNEL_BUTTON_HEIGHT * count + self.CHANNEL_BUTTON_GAP * (count - 1) + 13
		height = channelBoardHeight + 75
		self.acceptButton.SetPosition(13, height - 33)
		self.cancelButton.SetPosition(self.WIDTH - 73, height - 33)
		self.board.SetSize(self.WIDTH, height)
		self.channelBoard.SetSize(self.WIDTH - 26, channelBoardHeight)
		self.SetSize(self.WIDTH, height)
		self.UpdateRect()

	def Open(self):
		self.__BuildChannelButtons()
		self.currentChannel = net.GetChannelNum()
		self.SelectChannel(self.currentChannel)
		self.SetCenterPosition()
		self.SetTop()
		self.Show()

	# Selects channel `channel`: its button down and disabled, the others up.
	def SelectChannel(self, channel):
		self.selectedChannel = channel
		for index, button in enumerate(self.channelButtonList):
			if self.channelNumberList[index] == channel:
				button.Down()
				button.Disable()
			else:
				button.SetUp()
				button.Enable()

	# Asks for the selected channel; nothing while it is the current one (OLD).
	def Accept(self):
		if self.selectedChannel <= 0 or self.selectedChannel == self.currentChannel:
			return
		net.SendChatPacket("/ch %d" % self.selectedChannel)
		self.Close()

	def Close(self):
		self.Hide()
		return True

	def OnPressEscapeKey(self):
		self.Close()
		return True

if __name__ == "__main__":

	import app
	import wndMgr
	import systemSetting
	import mouseModule
	import grp
	import ui
	import chr
	import background
	import player

	#wndMgr.SetOutlineFlag(True)

	app.SetMouseHandler(mouseModule.mouseController)
	app.SetHairColorEnable(True)
	wndMgr.SetMouseHandler(mouseModule.mouseController)
	wndMgr.SetScreenSize(systemSetting.GetWidth(), systemSetting.GetHeight())
	app.Create("METIN2 CLOSED BETA", systemSetting.GetWidth(), systemSetting.GetHeight(), 1)
	mouseModule.mouseController.Create()


	wnd = SystemDialog()
	wnd.LoadDialog()
	wnd.Show()

	app.Loop()

