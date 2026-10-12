import app
import ui
import localeInfo
import uiScriptLocale

class HelpWindow(ui.ScriptWindow):
	def __init__(self):
		ui.ScriptWindow.__init__(self, "TOP_MOST")
		self.eventClose = 0
	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def LoadDialog(self):
		self.LoadDialogSinglePage()
	
	def LoadDialogSinglePage(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/HelpWindow.py")
		except:
			import exception
			exception.Abort("HelpWindow.LoadDialogSinglePage.LoadScript")

		try:
			GetObject=self.GetChild
			self.btnClose = GetObject("close_button")
		except:
			import exception
			exception.Abort("DialogWindow.LoadDialogSinglePage.BindObject")


	def Destroy(self):
		self.eventClose = 0
		self.closeButton = 0

	def SetCloseEvent(self, event):
		self.eventClose = event
		self.btnClose.SetEvent(event)

	def Open(self):
		self.Lock()
		self.Show()

	def Close(self):
		self.Unlock()
		self.Hide()

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

if __name__ == "__main__":

	import app
	import wndMgr
	import systemSetting
	import mouseModule
	import grp
	import ui

	app.SetMouseHandler(mouseModule.mouseController)
	app.SetHairColorEnable(True)
	wndMgr.SetMouseHandler(mouseModule.mouseController)
	wndMgr.SetScreenSize(systemSetting.GetWidth(), systemSetting.GetHeight())
	app.Create(localeInfo.APP_TITLE, systemSetting.GetWidth(), systemSetting.GetHeight(), 1)
	mouseModule.mouseController.Create()

	wnd = HelpWindow()
	wnd.LoadDialog()
	wnd.Open()
	app.Loop()
	wnd = None

