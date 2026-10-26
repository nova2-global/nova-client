import ui
import net
import chat
import player
import app
import localeInfo
import ime
import chr
import messenger
import uiScriptLocale

class LegacyWhisperButton(ui.Button):
	def __init__(self):
		ui.Button.__init__(self, "TOP_MOST")

	def __del__(self):
		ui.Button.__del__(self)

	def SetToolTipText(self, text, x=0, y = 32):
		ui.Button.SetToolTipText(self, text, x, y)
		self.ToolTipText.Show()

	def SetToolTipTextWithColor(self, text, color, x=0, y = 32):
		ui.Button.SetToolTipText(self, text, x, y)
		self.ToolTipText.SetPackedFontColor(color)
		self.ToolTipText.Show()

	def ShowToolTip(self):
		if 0 != self.ToolTipText:
			self.ToolTipText.Show()

	def HideToolTip(self):
		if 0 != self.ToolTipText:
			self.ToolTipText.Show()

class WhisperDialog(ui.ScriptWindow):

	# The target's online state (NOVA-48): NEW's messenger list icons, as
	# OLD's old interface used (OLD's new_ui/online.sub is in neither NEW's
	# assets nor OLD's source tree; the art is open).
	ONLINE_IMAGE = "d:/ymir work/ui/game/windows/messenger_list_online.sub"
	OFFLINE_IMAGE = "d:/ymir work/ui/game/windows/messenger_list_offline.sub"

	class TextRenderer(ui.Window):
		def SetTargetName(self, targetName):
			self.targetName = targetName

		def OnRender(self):
			(x, y) = self.GetGlobalPosition()
			chat.RenderWhisper(self.targetName, x, y)

	class ResizeButton(ui.DragButton):

		def __init__(self):
			ui.DragButton.__init__(self)

		def __del__(self):
			ui.DragButton.__del__(self)

		def OnMouseOverIn(self):
			app.SetCursor(app.HVSIZE)

		def OnMouseOverOut(self):
			app.SetCursor(app.NORMAL)

	def __init__(self, eventMinimize, eventClose):
		print("NEW WHISPER DIALOG  ----------------------------------------------------------------------------")
		ui.ScriptWindow.__init__(self)
		self.targetName = ""
		self.eventMinimize = eventMinimize
		self.eventClose = eventClose
		self.eventAcceptTarget = None
		# Widgets the uiscript adds (NOVA-47, NOVA-48); None until LoadDialog
		# binds them, and under NovaUI, whose loader does not.
		self.blockButton = None
		self.online = None
		self.flag = None
	def __del__(self):
		print("---------------------------------------------------------------------------- DELETE WHISPER DIALOG")
		ui.ScriptWindow.__del__(self)		

	def LoadDialog(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/WhisperDialog.py")
		except:
			import exception
			exception.Abort("WhisperDialog.LoadDialog.LoadScript")

		try:
			GetObject=self.GetChild
			self.titleName = GetObject("titlename")
			self.titleNameEdit = GetObject("titlename_edit")
			self.closeButton = GetObject("closebutton")
			self.scrollBar = GetObject("scrollbar")
			self.chatLine = GetObject("chatline")
			self.minimizeButton = GetObject("minimizebutton")
			self.ignoreButton = GetObject("ignorebutton")
			self.reportViolentWhisperButton = GetObject("reportviolentwhisperbutton")
			self.acceptButton = GetObject("acceptbutton")
			self.sendButton = GetObject("sendbutton")
			self.board = GetObject("board")
			self.editBar = GetObject("editbar")
			self.gamemasterMark = GetObject("gamemastermark")
			self.blockButton = GetObject("blockbutton")
			self.online = GetObject("online")
			self.flag = GetObject("flag")
		except:
			import exception
			exception.Abort("DialogWindow.LoadDialog.BindObject")

		self.gamemasterMark.Hide()
		self.titleName.SetText("")
		self.titleNameEdit.SetText("")
		self.minimizeButton.SetEvent(ui.__mem_func__(self.Minimize))
		self.closeButton.SetEvent(ui.__mem_func__(self.Close))
		self.scrollBar.SetPos(1.0)
		self.scrollBar.SetScrollEvent(ui.__mem_func__(self.OnScroll))
		self.chatLine.SetReturnEvent(ui.__mem_func__(self.SendWhisper))
		self.chatLine.SetEscapeEvent(ui.__mem_func__(self.Minimize))
		self.chatLine.SetMultiLine()
		self.sendButton.SetEvent(ui.__mem_func__(self.SendWhisper))
		self.titleNameEdit.SetReturnEvent(ui.__mem_func__(self.AcceptTarget))
		self.titleNameEdit.SetEscapeEvent(ui.__mem_func__(self.Close))
		self.ignoreButton.SetToggleDownEvent(ui.__mem_func__(self.IgnoreTarget))
		self.ignoreButton.SetToggleUpEvent(ui.__mem_func__(self.IgnoreTarget))
		self.reportViolentWhisperButton.SetEvent(ui.__mem_func__(self.ReportViolentWhisper))
		self.acceptButton.SetEvent(ui.__mem_func__(self.AcceptTarget))
		self.blockButton.SetEvent(ui.__mem_func__(self.BlockPlayer))
		self.blockButton.Hide()
		self.online.Hide()
		self.flag.Hide()

		self.textRenderer = self.TextRenderer()
		self.textRenderer.SetParent(self)
		self.textRenderer.SetPosition(20, 28)
		self.textRenderer.SetTargetName("")
		self.textRenderer.Show()

		self.resizeButton = self.ResizeButton()
		self.resizeButton.SetParent(self)
		self.resizeButton.SetSize(20, 20)
		self.resizeButton.SetPosition(280, 180)
		self.resizeButton.SetMoveEvent(ui.__mem_func__(self.ResizeWhisperDialog))
		self.resizeButton.Show()

		self.ResizeWhisperDialog()

	def Destroy(self):

		self.eventMinimize = None
		self.eventClose = None
		self.eventAcceptTarget = None

		self.ClearDictionary()
		self.scrollBar.Destroy()
		self.titleName = None
		self.titleNameEdit = None
		self.closeButton = None
		self.scrollBar = None
		self.chatLine = None
		self.sendButton = None
		self.ignoreButton = None
		self.reportViolentWhisperButton = None
		self.acceptButton = None
		self.minimizeButton = None
		self.textRenderer = None
		self.board = None
		self.editBar = None
		self.resizeButton = None
		self.blockButton = None
		self.online = None
		self.flag = None

	def ResizeWhisperDialog(self):
		(xPos, yPos) = self.resizeButton.GetLocalPosition()
		if xPos < 280:
			self.resizeButton.SetPosition(280, yPos)
			return
		if yPos < 150:
			self.resizeButton.SetPosition(xPos, 150)
			return
		self.SetWhisperDialogSize(xPos + 20, yPos + 20)

	def SetWhisperDialogSize(self, width, height):
		try:

			max = int((width-90)/6) * 3 - 6

			self.board.SetSize(width, height)
			self.scrollBar.SetPosition(width-25, 35)
			self.scrollBar.SetScrollBarSize(height-100)
			self.scrollBar.SetPos(1.0)
			self.editBar.SetSize(width-18, 50)
			self.chatLine.SetSize(width-90, 40)
			self.chatLine.SetLimitWidth(width-90)
			self.SetSize(width, height)

			if 0 != self.targetName:
				chat.SetWhisperBoxSize(self.targetName, width - 50, height - 90)

			if app.IsRTL():
				self.textRenderer.SetPosition(width-20, 28)
				self.scrollBar.SetPosition(width-25+self.scrollBar.GetWidth(), 35)
				self.editBar.SetPosition(10 + self.editBar.GetWidth(), height-60)
				self.sendButton.SetPosition(width - 80 + self.sendButton.GetWidth(), 10)
				self.minimizeButton.SetPosition(width-42 + self.minimizeButton.GetWidth(), 12)
				self.closeButton.SetPosition(width-24+self.closeButton.GetWidth(), 12)
				self.chatLine.SetPosition(5 + self.chatLine.GetWidth(), 5)
				self.board.SetPosition(self.board.GetWidth(), 0)
			else:
				self.textRenderer.SetPosition(20, 28)
				self.scrollBar.SetPosition(width-25, 35)
				self.editBar.SetPosition(10, height-60)
				self.sendButton.SetPosition(width-80, 10)
				self.minimizeButton.SetPosition(width-42, 12)
				self.closeButton.SetPosition(width-24, 12)

			self.__PlaceBlockButton(width)
			self.SetChatLineMax(max)

		except:
			import exception
			exception.Abort("WhisperDialog.SetWhisperDialogSize.BindObject")

	def SetChatLineMax(self, max):
		self.chatLine.SetMax(max)

		from grpText import GetSplitingTextLine

		text = self.chatLine.GetText()
		if text:
			self.chatLine.SetText(GetSplitingTextLine(text, max, 0))

	def OpenWithTarget(self, targetName):
		chat.CreateWhisper(targetName)
		chat.SetWhisperBoxSize(targetName, self.GetWidth() - 60, self.GetHeight() - 90)
		self.chatLine.SetFocus()
		self.titleName.SetText(targetName)
		self.targetName = targetName
		self.textRenderer.SetTargetName(targetName)
		self.titleNameEdit.Hide()
		self.ignoreButton.Hide()
		self.reportViolentWhisperButton.Hide()
		self.acceptButton.Hide()
		self.gamemasterMark.Hide()
		self.minimizeButton.Show()
		self.RefreshBlockButton()
		self.__HideTargetDetails()

	def OpenWithoutTarget(self, event):
		self.eventAcceptTarget = event
		self.titleName.SetText("")
		self.titleNameEdit.SetText("")
		self.titleNameEdit.SetFocus()
		self.targetName = 0
		self.titleNameEdit.Show()
		self.ignoreButton.Hide()
		self.reportViolentWhisperButton.Hide()
		self.acceptButton.Show()
		self.minimizeButton.Hide()
		self.gamemasterMark.Hide()
		if self.blockButton:
			self.blockButton.Hide()
		self.__HideTargetDetails()

	## Whisper details (NOVA-48, OLD uiWhisper.py:114-122, game.py:3745-3772)
	# The target's state until the server's first answer: unknown, so neither
	# icon shows.
	def __HideTargetDetails(self):
		if self.online:
			self.online.Hide()
		if self.flag:
			self.flag.Hide()

	# The server's answer to net.SendWhisperDetailsPacket (game.py's
	# BINARY_WhisperDetails): the online or offline icon, and the target's
	# language flag while it is online and has a language with a flag file.
	# The language stays empty until the server keeps one (NOVA-51).
	def SetTargetDetails(self, online, language=""):
		if self.online:
			if online:
				self.online.LoadImage(self.ONLINE_IMAGE)
			else:
				self.online.LoadImage(self.OFFLINE_IMAGE)
			self.online.Show()

		if self.flag:
			# Imported here: the windows that load this module do not all have
			# constInfo loaded yet.
			import constInfo
			path = constInfo.GET_LANGUAGE_FLAG(language) if online and language else ""
			if path:
				self.flag.LoadImage(path)
				self.flag.Show()
			else:
				self.flag.Hide()

	## The block list (NOVA-47, OLD uiWhisper.py:343-393)
	# The block button sits left of the minimize button. NEW's small text
	# button is wider than OLD's icon (OLD: width - 68), so it starts further
	# left; the art is open.
	def __PlaceBlockButton(self, width):
		if not self.blockButton:
			return
		if app.IsRTL():
			self.blockButton.SetPosition(width - 86 + self.blockButton.GetWidth(), 8)
		else:
			self.blockButton.SetPosition(width - 86, 8)

	def __HasTarget(self):
		return isinstance(self.targetName, str) and len(self.targetName) > 0

	def __SetBlockButtonText(self, blocked):
		if blocked:
			self.blockButton.SetText(uiScriptLocale.UNBLOCK_PLAYER)
			self.blockButton.SetToolTipText(uiScriptLocale.UNBLOCK_PLAYER)
		else:
			self.blockButton.SetText(uiScriptLocale.BLOCK_PLAYER)
			self.blockButton.SetToolTipText(uiScriptLocale.BLOCK_PLAYER)

	# Block or Unblock, as the client's list says for the target.
	def RefreshBlockButton(self):
		if not self.blockButton:
			return
		if not self.__HasTarget():
			self.blockButton.Hide()
			return
		self.__SetBlockButtonText(messenger.IsBlocked(self.targetName))
		self.blockButton.Show()

	# Sends the change and shows the other button at once, as OLD did; the
	# server's answer updates the messenger's list.
	def BlockPlayer(self):
		if not self.blockButton or not self.__HasTarget():
			return
		if messenger.IsBlocked(self.targetName):
			net.SendBlockRemovePacket(self.targetName)
			self.__SetBlockButtonText(False)
		else:
			net.SendBlockAddPacket(self.targetName)
			self.__SetBlockButtonText(True)

	def SetGameMasterLook(self):
		self.gamemasterMark.Show()
		self.reportViolentWhisperButton.Hide()

	def Minimize(self):
		self.titleNameEdit.KillFocus()
		self.chatLine.KillFocus()
		self.Hide()

		if None != self.eventMinimize:
			self.eventMinimize(self.targetName)

	def Close(self):
		chat.ClearWhisper(self.targetName)
		self.titleNameEdit.KillFocus()
		self.chatLine.KillFocus()
		self.Hide()

		if None != self.eventClose:
			self.eventClose(self.targetName)

	def ReportViolentWhisper(self):
		net.SendChatPacket("/reportviolentwhisper " + self.targetName)

	def IgnoreTarget(self):
		net.SendChatPacket("/ignore " + self.targetName)

	def AcceptTarget(self):
		name = self.titleNameEdit.GetText()
		if len(name) <= 0:
			self.Close()
			return

		if None != self.eventAcceptTarget:
			self.titleNameEdit.KillFocus()
			self.eventAcceptTarget(name)
			# The new target's details at once (OLD); game.py's OnUpdate asks
			# again every two seconds while the dialog is open.
			net.SendWhisperDetailsPacket(name)

	def OnScroll(self):
		chat.SetWhisperPosition(self.targetName, self.scrollBar.GetPos())

	def SendWhisper(self):

		text = self.chatLine.GetText()
		textLength = len(text)

		if textLength > 0:
			if net.IsInsultIn(text):
				chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.CHAT_INSULT_STRING)
				return

			net.SendWhisperPacket(self.targetName, text)
			self.chatLine.SetText("")

			chat.AppendWhisper(chat.WHISPER_TYPE_CHAT, self.targetName, player.GetName() + " : " + text)

	def OnTop(self):
		self.chatLine.SetFocus()
		
	def BindInterface(self, interface):
		self.interface = interface
		
	def OnMouseLeftButtonDown(self):
		hyperlink = ui.GetHyperlink()
		if hyperlink:
			if app.IsPressed(app.DIK_LALT):
				link = chat.GetLinkFromHyperlink(hyperlink)
				ime.PasteString(link)
			else:
				self.interface.MakeHyperlinkTooltip(hyperlink)

# NovaUI edge buttons (nui_edge_buttons.py, flag "edge-buttons"): with the flag
# on this name makes a NovaUI edge button; with it off, the legacy one above.
import nui_windows
WhisperButton = nui_windows.factory("edge-buttons", LegacyWhisperButton, "nui_edge_buttons.EdgeButton")

if "__main__" == __name__:
	import uiTest

	class TestApp(uiTest.App):
		def OnInit(self):
			wnd = WhisperDialog(self.OnMax, self.OnMin)
			wnd.LoadDialog()
			wnd.OpenWithoutTarget(self.OnNew)
			wnd.SetPosition(0, 0)
			wnd.Show()

			self.wnd = wnd

		def OnMax(self):
			pass

		def OnMin(self):
			pass

		def OnNew(self):
			pass

	TestApp().MainLoop()
