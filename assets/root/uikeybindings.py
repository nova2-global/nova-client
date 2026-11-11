"""The legacy key bindings dialog (NOVA-121), opened from the game options'
Keyboard row (uigameoption.py). The NovaUI game options show the same table
as their keyboard page (nui_game_options.py); both run keybindings.Page, so
the capture, the conflicts, the notice line and the reset are one code.

The rows (a section's header, then its actions with their two keys) show 16
at a time over the scroll bar and the mouse wheel. A press on a key cell
waits for the next key (the game window gives the capture every key first,
game.py __KeyDown); Escape stops waiting before it closes the dialog, and a
close stops it too. Changes apply and save at once."""

import ui
import keybindings

UISCRIPT = "uiscript/keybindingsdialog.py"
ROW_Y = 56
ROW_STEP = 22
ROW_COUNT = 16
LABEL_X = 20
SECTION_X = 16
KEY_X = (172, 266)
LARGE_BUTTON = ("d:/ymir work/ui/public/large_button_01.sub", "d:/ymir work/ui/public/large_button_02.sub",
                "d:/ymir work/ui/public/large_button_03.sub")
SECTION_COLOR = 0xFFF1E6C0
CHANGED_COLOR = 0xFFFFD27F
LABEL_COLOR = 0xFFC8C8C8


class KeyBindingsDialog(ui.ScriptWindow):
	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.page = keybindings.Page(self.Refresh)
		self.rows = []
		self.labels = []
		self.keyButtons = []
		self.scrollBar = None
		self.notice = None
		self.offset = 0
		self.settingBar = False
		self.__Load()
		keybindings.current().listen(self)

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __Load(self):
		try:
			ui.PythonScriptLoader().LoadScriptFile(self, UISCRIPT)
		except:
			import exception
			exception.Abort("KeyBindingsDialog.__Load")
		board = self.GetChild("board")
		self.GetChild("titlebar").SetCloseEvent(ui.__mem_func__(self.Close))
		self.GetChild("reset_button").SAFE_SetEvent(self.__OnClickReset)
		self.notice = self.GetChild("notice")
		self.scrollBar = self.GetChild("scrollbar")
		self.scrollBar.SetScrollEvent(ui.__mem_func__(self.__OnScroll))
		for i in range(ROW_COUNT):
			y = ROW_Y + ROW_STEP * i
			label = ui.TextLine()
			label.SetParent(board)
			label.SetPosition(LABEL_X, y + 3)
			label.Show()
			self.labels.append(label)
			buttons = []
			for column in range(keybindings.COLUMNS):
				button = ui.Button()
				button.SetParent(board)
				button.SetPosition(KEY_X[column], y)
				button.SetUpVisual(LARGE_BUTTON[0])
				button.SetOverVisual(LARGE_BUTTON[1])
				button.SetDownVisual(LARGE_BUTTON[2])
				button.SAFE_SetEvent(self.__OnClickKey, i, column)
				buttons.append(button)
			self.keyButtons.append(buttons)
		self.SetCenterPosition()
		self.Refresh()

	def Destroy(self):
		self.page.cancel()
		keybindings.current().forget(self)
		self.ClearDictionary()
		self.labels = []
		self.keyButtons = []
		self.rows = []

	# --- the table -------------------------------------------------------------

	def OnKeyBindingsChanged(self):
		self.Refresh()

	def Refresh(self):
		self.rows = self.page.rows()
		scroll = max(0, len(self.rows) - ROW_COUNT)
		self.offset = min(self.offset, scroll)
		if self.scrollBar:
			if scroll:
				self.scrollBar.SetMiddleBarSize(float(ROW_COUNT) / len(self.rows))
				self.scrollBar.Show()
			else:
				self.scrollBar.Hide()
		for i in range(len(self.labels)):
			index = self.offset + i
			row = self.rows[index] if index < len(self.rows) else None
			self.__ShowRow(i, row)
		if self.notice:
			self.notice.SetText(self.page.notice_text())

	def __ShowRow(self, i, row):
		label = self.labels[i]
		buttons = self.keyButtons[i]
		if row is None:
			label.Hide()
			for button in buttons:
				button.Hide()
			return
		label.SetText(row["label"])
		label.Show()
		if row["kind"] == "section":
			label.SetPosition(SECTION_X, ROW_Y + ROW_STEP * i + 3)
			label.SetPackedFontColor(SECTION_COLOR)
			for button in buttons:
				button.Hide()
			return
		label.SetPosition(LABEL_X, ROW_Y + ROW_STEP * i + 3)
		label.SetPackedFontColor(CHANGED_COLOR if row["changed"] else LABEL_COLOR)
		for column, button in enumerate(buttons):
			button.SetText(row["k%d" % (column + 1)])
			if row["cap%d" % (column + 1)]:
				button.Down()
			else:
				button.SetUp()
			button.Show()

	# --- events --------------------------------------------------------------------

	def __OnClickKey(self, i, column):
		index = self.offset + i
		if index < len(self.rows) and self.rows[index]["kind"] == "action":
			self.page.press(self.rows[index]["id"], column)

	def __OnClickReset(self):
		self.page.reset()

	def __OnScroll(self):
		if self.settingBar:
			return
		scroll = max(0, len(self.rows) - ROW_COUNT)
		offset = int(round(self.scrollBar.GetPos() * scroll))
		if offset != self.offset:
			self.offset = offset
			self.Refresh()

	def OnRunMouseWheel(self, length):
		scroll = max(0, len(self.rows) - ROW_COUNT)
		if not scroll:
			return False
		self.offset = max(0, min(scroll, self.offset + (1 if length < 0 else -1)))
		self.settingBar = True
		try:
			self.scrollBar.SetPos(float(self.offset) / scroll)
		finally:
			self.settingBar = False
		self.Refresh()
		return True

	def Open(self):
		self.Refresh()
		self.Show()
		self.SetTop()

	def Close(self):
		self.page.cancel()
		self.Hide()

	def OnPressEscapeKey(self):
		if self.page.cancel():
			return True
		self.Close()
		return True
