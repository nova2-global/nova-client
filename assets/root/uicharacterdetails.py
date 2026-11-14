"""The character bonus details panel (NOVA-207; OLD uiCharacterDetails.py and
uiscript CharacterDetailsWindow.py): a board beside the character window with
every bonus point the server sends, by category, in a scroll window. The
character window makes it at its first expand, places it, refreshes it from
its RefreshStatus (the client's point refresh) and hides it with itself.

Its rows come from characterdetails.py, which the NovaUI side panel reads
too: a category is a horizontal bar with its name, a row its label, its value
(player.GetStatus of its point) and, under the pointer, its tooltip.

OLD showed 13 recycled rows moved by a scroll bar; NEW's ui.ScrollWindow
clips one content window with every row, so the wheel and the bar scroll it
by pixels."""

import ui
import player
import localeInfo
import uiToolTip

import characterdetails

# OLD's board (CharacterDetailsWindow.py: 200 x 364) beside the 253 wide
# character window, 3 pixels over its right edge (OLD AdjustPosition).
WIDTH = 200
HEIGHT = 364
OWNER_OFFSET = 253 - 3
LINE_HEIGHT = 24
VALUE_WIDTH = 50
VALUE_HEIGHT = 17
TOOLTIP_WIDTH = 220
SCROLLBAR_WIDTH = 17	# ui.ScrollBar.SCROLLBAR_WIDTH, the bar ui.ScrollWindow puts on its right


class _RowArea(ui.Window):
	"""A line's hover area: the window manager's over in and out reach the
	panel with the line's index."""

	def __init__(self, owner, index):
		ui.Window.__init__(self)
		self.owner = ui.__mem_func__(owner.ShowLineToolTip)
		self.ownerOut = ui.__mem_func__(owner.HideLineToolTip)
		self.index = index

	def __del__(self):
		ui.Window.__del__(self)

	def OnMouseOverIn(self):
		self.owner(self.index)

	def OnMouseOverOut(self):
		self.ownerOut()


class CharacterDetailsWindow(ui.Window):
	"""The panel (Interface's wndCharacter.detailsWindow)."""

	def __init__(self):
		ui.Window.__init__(self)
		self.AddFlag("float")
		self.SetSize(WIDTH, HEIGHT)

		self.lines = characterdetails.lines(localeInfo)
		self.toolTip = uiToolTip.ToolTip(TOOLTIP_WIDTH)
		self.toolTip.HideToolTip()
		self.valueTexts = []
		self.rowAreas = []
		self.children = []
		self.closeEvent = None

		self.__MakeBoard()

	def __del__(self):
		ui.Window.__del__(self)

	def __Keep(self, child):
		self.children.append(child)
		return child

	def __MakeBoard(self):
		board = self.__Keep(ui.Board())
		board.SetParent(self)
		board.SetSize(WIDTH, HEIGHT)
		board.Show()

		titleBar = self.__Keep(ui.TitleBar())
		titleBar.SetParent(board)
		titleBar.MakeTitleBar(WIDTH - 13, "yellow")
		titleBar.SetPosition(6, 7)
		titleBar.SetCloseEvent(ui.__mem_func__(self.__OnClose))
		titleBar.Show()

		title = self.__Keep(ui.TextLine())
		title.SetParent(titleBar)
		title.SetPosition(0, 4)
		title.SetWindowHorizontalAlignCenter()
		title.SetHorizontalAlignCenter()
		title.SetText(localeInfo.DETAILS_TITLE)
		title.Show()

		scrollWindow = self.__Keep(ui.ScrollWindow(WIDTH - 20, HEIGHT - 45))
		scrollWindow.SetParent(board)
		scrollWindow.SetPosition(10, 34)
		scrollWindow.Show()
		self.scrollWindow = scrollWindow

		contentWidth = WIDTH - 20 - SCROLLBAR_WIDTH - 4
		content = self.__Keep(ui.Window())
		content.SetSize(contentWidth, len(self.lines) * LINE_HEIGHT)
		content.Show()

		for (index, line) in enumerate(self.lines):
			y = index * LINE_HEIGHT
			area = self.__Keep(_RowArea(self, index))
			area.SetParent(content)
			area.SetPosition(0, y)
			area.SetSize(contentWidth, LINE_HEIGHT)
			area.Show()
			self.rowAreas.append(area)

			if line["head"]:
				self.valueTexts.append(None)
				bar = self.__Keep(ui.HorizontalBar())
				bar.Create(contentWidth)
				bar.SetParent(area)
				bar.SetPosition(0, 3)
				bar.AddFlag("not_pick")
				bar.Show()
				name = self.__Keep(ui.TextLine())
				name.SetParent(bar)
				name.SetPosition(0, 1)
				name.SetWindowHorizontalAlignCenter()
				name.SetHorizontalAlignCenter()
				name.SetText(line["label"])
				name.AddFlag("not_pick")
				name.Show()
				continue

			label = self.__Keep(ui.TextLine())
			label.SetParent(area)
			label.SetPosition(4, 5)
			label.SetText(line["label"])
			label.AddFlag("not_pick")
			label.Show()

			valueBar = self.__Keep(ui.SlotBar())
			valueBar.SetParent(area)
			valueBar.SetSize(VALUE_WIDTH, VALUE_HEIGHT)
			valueBar.SetPosition(contentWidth - VALUE_WIDTH - 2, 3)
			valueBar.AddFlag("not_pick")
			valueBar.Show()

			value = self.__Keep(ui.TextLine())
			value.SetParent(valueBar)
			value.SetPosition(0, 2)
			value.SetWindowHorizontalAlignCenter()
			value.SetHorizontalAlignCenter()
			value.AddFlag("not_pick")
			value.Show()
			self.valueTexts.append(value)

		scrollWindow.SetContentWindow(content)

	def Destroy(self):
		self.Hide()
		self.closeEvent = None
		if self.scrollWindow:
			self.scrollWindow.Destroy()
		self.scrollWindow = None
		self.toolTip = None
		self.valueTexts = []
		self.rowAreas = []
		self.children = []

	def SetCloseEvent(self, event):
		"""The title bar's close: the character window's minimize."""
		self.closeEvent = event

	def __OnClose(self):
		if self.closeEvent:
			self.closeEvent()

	def AdjustPosition(self, x, y):
		"""Beside the character window at (x, y), as OLD."""
		self.SetPosition(x + OWNER_OFFSET, y)

	def Refresh(self):
		for (line, value) in zip(self.lines, self.valueTexts):
			if value is not None:
				value.SetText(characterdetails.value_text(line, player.GetStatus))

	def Hide(self):
		# ui.Window.__init__ hides the window before the tooltip exists.
		toolTip = getattr(self, "toolTip", None)
		if toolTip:
			toolTip.HideToolTip()
		ui.Window.Hide(self)

	def ShowLineToolTip(self, index):
		if self.toolTip and 0 <= index < len(self.lines):
			characterdetails.show_tooltip(self.toolTip, self.lines[index])

	def HideLineToolTip(self):
		if self.toolTip:
			self.toolTip.HideToolTip()

	def OnRunMouseWheel(self, length):
		if self.scrollWindow:
			return self.scrollWindow.OnRunMouseWheel(length)
		return False
