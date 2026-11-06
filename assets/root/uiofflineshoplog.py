"""The offline shop's log (NOVA-9; OLD uiOfflineShopLog.py, spec 3.8): the owner's last actions,
a page of rows at a time, newest first.

The Interface makes it (wndOfflineShopLog) and opens it from the owner panel
(Interface.OpenOfflineShopLog). Open asks for page 0 (CG LOGS); each answer
(BINARY_OfflineShopLog -> Interface.OfflineShopLog -> SetData(rows, page,
last)) appends its rows, and scrolling to the end asks for the next page once,
until an answer says it was the last. A page the server refused (GC RESULT
for LOGS, which the shop dialog hands over: OnLogsResult) ends the loading, or,
refused as too soon, is asked again a second later. Its states (o-cli bug 14): loading
until the first answer, empty when the shop has no row, last when no page
follows. The rows are K's tuples (time, action, other, vnum, count, amount);
offlineshopconst.log_row gives their texts: the action from its locale key or
its number (o-cli bug 22), the date in local time."""

import net
import ui
import app
import localeInfo

ROW_HEIGHT = 20
ROW_WIDTH = 480
ROW_COLORS = (0xff131313, 0xff1e1e1e)
SCROLL_POSITION = (14, 40)
SCROLL_SIZE = (ROW_WIDTH, 425)
# The columns (x) of a row: the action, the other party, the item, the yang, the date.
COLUMNS = (6, 96, 190, 330, 400)


class LogRow(ui.Window):
	"""One row: its five texts over a dark bar."""

	def __init__(self, index):
		ui.Window.__init__(self)
		self.SetSize(ROW_WIDTH, ROW_HEIGHT)
		self.bar = ui.Bar()
		self.bar.SetParent(self)
		self.bar.AddFlag("not_pick")
		self.bar.SetSize(ROW_WIDTH, ROW_HEIGHT)
		self.bar.SetColor(ROW_COLORS[index % 2])
		self.bar.Show()
		self.texts = []
		for x in COLUMNS:
			text = ui.TextLine()
			text.SetParent(self)
			text.SetPosition(x, 3)
			text.Show()
			self.texts.append(text)

	def __del__(self):
		ui.Window.__del__(self)

	def SetInfo(self, info):
		amount = localeInfo.NumberToMoneyString(info["amount"]) if info["amount"] > 0 else "-"
		for text, value in zip(self.texts, (info["action"], info["other"] or "-", info["what"], amount, info["date"])):
			text.SetText(value)

	def GetTexts(self):
		return [text.GetText() for text in self.texts]


class OfflineShopLogWindow(ui.ScriptWindow):

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.isLoaded = False
		self.interface = None
		self.rows = []
		self.nextPage = 0
		self.isLast = False
		self.isLoading = False
		self.retryTime = 0
		self.scrollWindow = None
		self.logsWindow = None
		self.loadingText = None
		self.emptyText = None

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		if self.isLoaded:
			return
		self.isLoaded = True
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/offlineshoplogwindow.py")
		except:
			import exception
			exception.Abort("OfflineShopLogWindow.LoadWindow.LoadObject")

		try:
			GetObject = self.GetChild
			self.board = GetObject("board")
			self.titleBar = GetObject("TitleBar")
			self.logsWindow = GetObject("LogsWindow")
			self.loadingText = GetObject("LoadingText")
			self.emptyText = GetObject("EmptyText")
		except:
			import exception
			exception.Abort("OfflineShopLogWindow.LoadWindow.BindObject")

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))

		self.scrollWindow = ui.ScrollWindow(SCROLL_SIZE[0] + 17, SCROLL_SIZE[1])
		self.scrollWindow.SetParent(self.board)
		self.scrollWindow.SetPosition(*SCROLL_POSITION)
		self.scrollWindow.SetContentWindow(self.logsWindow)
		self.scrollWindow.FitWidth(SCROLL_SIZE[0])
		self.scrollWindow.SetOnEndScrollEvent(ui.__mem_func__(self.OnEndScroll))
		self.scrollWindow.Show()

	def BindInterface(self, interface):
		self.interface = interface

	def Destroy(self):
		self.Close()
		self.__ClearRows()
		if self.scrollWindow:
			self.scrollWindow.Destroy()
		self.scrollWindow = None
		self.interface = None
		self.isLoaded = False
		self.ClearDictionary()

	def Open(self):
		"""Shows the window and asks for page 0."""
		self.__LoadWindow()
		self.__ClearRows()
		self.nextPage = 0
		self.isLast = False
		self.Show()
		self.SetTop()
		self.__RequestNextPage()

	def Close(self):
		self.isLoading = False
		self.retryTime = 0
		self.Hide()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def IsLoading(self):
		return self.isLoading

	def IsLast(self):
		return self.isLast

	def IsEmpty(self):
		return not self.rows and self.isLast

	def GetRowTexts(self):
		return [row.GetTexts() for row in self.rows]

	def __RequestNextPage(self):
		if self.isLoading or self.isLast:
			return
		self.isLoading = True
		self.__RefreshState()
		net.SendOfflineShopLogsPacket(self.nextPage)

	def OnLogsResult(self, code):
		"""GC RESULT for LOGS (ShopDialog.OnOfflineShopResult hands it over): the page asked was
		refused and no LOGS frame follows. RATE_LIMITED (SO1 takes one LOGS a second) asks again
		LOG_RETRY_SEC later; any other code ends the loading, so the end of the view asks again.
		True when the window took the code quietly (the retry: no chat line)."""
		import offlineshopconst
		if not self.isLoading or offlineshopconst.is_result_ok(code):
			return False
		if offlineshopconst.result_name(code) == "RATE_LIMITED" and self.IsShow():
			self.retryTime = app.GetTime() + offlineshopconst.LOG_RETRY_SEC
			return True
		self.isLoading = False
		self.retryTime = 0
		self.__RefreshState()
		return False

	def OnUpdate(self):
		if self.retryTime and app.GetTime() >= self.retryTime:
			self.retryTime = 0
			net.SendOfflineShopLogsPacket(self.nextPage)

	def SetData(self, rows, page, last):
		"""A LOGS answer (Interface.OfflineShopLog): its rows after the shown ones."""
		if not self.isLoaded or not self.IsShow():
			return
		import offlineshopconst
		self.isLoading = False
		self.retryTime = 0
		self.isLast = bool(last)
		self.nextPage = page + 1
		for row in rows:
			logRow = self.__MakeRow(len(self.rows))
			logRow.SetParent(self.logsWindow)
			logRow.SetPosition(0, len(self.rows) * ROW_HEIGHT)
			logRow.SetInfo(offlineshopconst.log_row(row))
			logRow.Show()
			self.rows.append(logRow)
		self.logsWindow.SetSize(ROW_WIDTH, max(1, len(self.rows) * ROW_HEIGHT))
		self.__RefreshState()
		if self.scrollWindow:
			self.scrollWindow.OnContentWindowSizeChange()

	def __MakeRow(self, index):
		"""A row of the view (NovaUI's window makes its own)."""
		return LogRow(index)

	def OnEndScroll(self):
		"""The view reached the last row: the next page, once, until the last one came."""
		if self.rows:
			self.__RequestNextPage()

	def OnScrollWheel(self, length):
		if self.scrollWindow:
			return self.scrollWindow.OnRunMouseWheel(length)
		return False

	def __ClearRows(self):
		for row in self.rows:
			row.Hide()
		self.rows = []
		if self.logsWindow:
			self.logsWindow.SetSize(ROW_WIDTH, 1)
		if self.scrollWindow:
			self.scrollWindow.OnContentWindowSizeChange()
			self.scrollWindow.ScrollToStart()

	def __RefreshState(self):
		if self.loadingText:
			if self.isLoading and not self.rows:
				self.loadingText.Show()
			else:
				self.loadingText.Hide()
		if self.emptyText:
			if self.IsEmpty():
				self.emptyText.Show()
			else:
				self.emptyText.Hide()
