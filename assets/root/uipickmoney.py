import re
import wndMgr
import ui
import ime
import app
import nui_windows

# OLD's amounts with a k, m or b suffix (OLD constInfo.py:574-585, read by
# uiPickMoney.py:122): "5k" is 5000, "3m" and "3kk" 3000000, "2b"
# 2000000000; a suffix's letter repeats its power. Plain digits are the number.
MONEY_SUFFIX_POWERS = {"k": 10 ** 3, "m": 10 ** 6, "b": 10 ** 9}
_MONEY_PATTERN = re.compile(r"(\d+)(%s)?" % "|".join("%s+" % suffix for suffix in MONEY_SUFFIX_POWERS), re.I)

def ConvertTextToMoney(text):
	"""The amount the text names, 0 when it holds no digits. OLD looked the
	suffix up as typed, so an upper-case one ("5K") raised KeyError; any case
	works here."""
	match = _MONEY_PATTERN.search(text)
	if not match:
		return 0
	digits, suffix = match.groups()
	if not suffix:
		return int(digits)
	return int(digits) * MONEY_SUFFIX_POWERS[suffix[0].lower()] ** len(suffix)

class PickMoneyDialog(ui.ScriptWindow):
	def __init__(self):
		ui.ScriptWindow.__init__(self)

		self.unitValue = 1
		self.maxValue = 0
		self.eventAccept = 0

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def LoadDialog(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/PickMoneyDialog.py")
		except:
			import exception
			exception.Abort("MoneyDialog.LoadDialog.LoadScript")

		try:
			self.board = self.GetChild("board")
			self.maxValueTextLine = self.GetChild("max_value")
			self.pickValueEditLine = self.GetChild("money_value")
			self.acceptButton = self.GetChild("accept_button")
			self.cancelButton = self.GetChild("cancel_button")
		except:
			import exception
			exception.Abort("MoneyDialog.LoadDialog.BindObject")

		self.pickValueEditLine.SetReturnEvent(ui.__mem_func__(self.OnAccept))
		self.pickValueEditLine.SetEscapeEvent(ui.__mem_func__(self.Close))
		self.acceptButton.SetEvent(ui.__mem_func__(self.OnAccept))
		self.cancelButton.SetEvent(ui.__mem_func__(self.Close))
		self.board.SetCloseEvent(ui.__mem_func__(self.Close))

	def Destroy(self):
		self.ClearDictionary()
		self.eventAccept = 0
		self.maxValue = 0
		self.pickValueEditLine = 0		
		self.acceptButton = 0
		self.cancelButton = 0
		self.board = None

	def SetTitleName(self, text):
		self.board.SetTitleName(text)

	def SetAcceptEvent(self, event):
		self.eventAccept = event

	def SetMax(self, max):
		self.pickValueEditLine.SetMax(max)

	def Open(self, maxValue, unitValue = 1):
		nui_windows.legacy_dialog_layer(self)
		width = self.GetWidth()
		(mouseX, mouseY) = wndMgr.GetMousePosition()

		if mouseX + width/2 > wndMgr.GetScreenWidth():
			xPos = wndMgr.GetScreenWidth() - width
		elif mouseX - width/2 < 0:
			xPos = 0
		else:
			xPos = mouseX - width/2

		self.SetPosition(xPos, mouseY - self.GetHeight() - 20)

		if app.IsRTL():
			self.maxValueTextLine.SetText("/" + str(maxValue))
		else:
			self.maxValueTextLine.SetText(" / " + str(maxValue))

		self.pickValueEditLine.SetText(str(unitValue))
		self.pickValueEditLine.SetFocus()

		ime.SetCursorPosition(1)

		self.unitValue = unitValue
		self.maxValue = maxValue
		self.Show()
		self.SetTop()

	def Close(self):
		self.pickValueEditLine.KillFocus()
		self.Hide()

	def OnAccept(self):

		text = self.pickValueEditLine.GetText()

		if len(text) > 0:

			money = min(ConvertTextToMoney(text), self.maxValue)

			if money > 0:
				if self.eventAccept:
					self.eventAccept(money)

		self.Close()

# NovaUI dialog kit (nui_pick_money.py, flag "dialogs"): with the flag on this
# name makes the NovaUI dialog; with it off, the legacy class above.
LegacyPickMoneyDialog = PickMoneyDialog
PickMoneyDialog = nui_windows.factory("dialogs", LegacyPickMoneyDialog, "nui_pick_money.PickMoneyDialog")
