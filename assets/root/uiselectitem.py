import ui
import player
import item
import wndMgr
import net

# The guild alchemist's stones (decision c, spec 3.10): they sit in the
# special inventory's stone category (nova-protocol inventory_packets.h).
EXTRA_INVENTORY_CATEGORY_STONES = 2
# OLD's cap (uiSelectItem.py: slotPos > 54).
SELECT_ITEM_MAX = 55


def GetExtraStoneCells():
	"""The special inventory's stone cells; none on an exe without the
	special inventory (no category range)."""
	getRange = getattr(player, "GetExtraInventoryCategoryRange", None)
	cells = getRange(EXTRA_INVENTORY_CATEGORY_STONES) if getRange else None
	if not isinstance(cells, tuple) or len(cells) != 2:
		return range(0)
	return range(cells[0], cells[1])


class SelectItemWindow(ui.ScriptWindow):

	def __init__(self):
		ui.ScriptWindow.__init__(self)

		self.tooltipItem = None
		# {select slot: cell} and {select slot: window} (the cell's window).
		self.inventorySlotPosDict = {}
		self.inventorySlotWindowDict = {}

		self.LoadWindow()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def LoadWindow(self):
		try:
			PythonScriptLoader = ui.PythonScriptLoader()
			PythonScriptLoader.LoadScriptFile(self, "UIScript/selectitemwindow.py")
		except:
			import exception
			exception.Abort("ItemSelectWindow.LoadDialog.LoadObject")

		try:
			GetObject = self.GetChild
			self.board = GetObject("board")
			self.titleBar = GetObject("TitleBar")
			self.itemSlot = GetObject("ItemSlot")
			self.btnExit = GetObject("ExitButton")
		except:
			import exception
			exception.Abort("ItemSelectWindow.LoadDialog.BindObject")

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))
		self.btnExit.SetEvent(ui.__mem_func__(self.Close))
		self.itemSlot.SetSlotStyle(wndMgr.SLOT_STYLE_NONE)
		self.itemSlot.SAFE_SetButtonEvent("LEFT", "EXIST", self.SelectItemSlot)
		self.itemSlot.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		self.itemSlot.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))

	def Open(self):
		self.RefreshSlot()
		self.Show()

	def Close(self):
		wndMgr.OnceIgnoreMouseLeftButtonUpEvent()
		net.SendSelectItemPacket(0)
		self.Hide()

	def SetItemToolTip(self, tooltipItem):
		self.tooltipItem = tooltipItem

	def SelectItemSlot(self, slotPos):
		## The stone's window and cell (C1 encodes them, spec 3.10); past OLD,
		## inventory cell 0 is a stone, not "closed".
		wndMgr.OnceIgnoreMouseLeftButtonUpEvent()
		inventorySlotPos = self.inventorySlotPosDict[slotPos]
		window = self.inventorySlotWindowDict.get(slotPos, player.INVENTORY)
		net.SendSelectItemPacket(window, inventorySlotPos)
		self.Hide()

	def SetTableSize(self, size):

		SLOT_X_COUNT = 5
		self.itemSlot.ArrangeSlot(0, SLOT_X_COUNT, size, 32, 32, 0, 0)
		self.itemSlot.RefreshSlot()
		self.itemSlot.SetSlotBaseImage("d:/ymir work/ui/public/Slot_Base.sub", 1.0, 1.0, 1.0, 1.0)

		self.board.SetSize(self.board.GetWidth(), 76 + 32*size)
		self.SetSize(self.board.GetWidth(), 76 + 32*size)
		self.UpdateRect()

	def RefreshSlot(self):

		slotPos = 0
		self.inventorySlotPosDict = {}
		self.inventorySlotWindowDict = {}

		getItemVNum=player.GetItemIndex
		getItemCount=player.GetItemCount
		setItemVNum=self.itemSlot.SetItemSlot

		## The main inventory's stones, then the special inventory's, where
		## every stone is after the cut (decision c; OLD listed two pages of
		## the main inventory only).
		cells = [(player.INVENTORY, i) for i in range(player.INVENTORY_PAGE_SIZE*player.INVENTORY_PAGE_COUNT)]
		cells += [(player.EXTRA_INVENTORY, i) for i in GetExtraStoneCells()]

		for (window, slotNumber) in cells:
			if window == player.INVENTORY:
				itemVNum = getItemVNum(slotNumber)
			else:
				itemVNum = getItemVNum(window, slotNumber)

			if 0 == itemVNum:
				continue

			if not item.IsMetin(itemVNum):
				continue

			if window == player.INVENTORY:
				itemGrade = player.GetItemGrade(slotNumber)
			else:
				itemGrade = player.GetItemGrade(window, slotNumber)

			if itemGrade > 2:
				continue

			self.inventorySlotPosDict[slotPos] = slotNumber
			self.inventorySlotWindowDict[slotPos] = window

			slotPos += 1

			if slotPos >= SELECT_ITEM_MAX:
				break

		itemCount = len(self.inventorySlotPosDict)

		if itemCount < 15:
			self.SetTableSize(3)

		else:
			lineCount = 3
			lineCount += (itemCount - 15) // 5

			if itemCount % 5:
				lineCount += 1

			self.SetTableSize(lineCount)

		for selectWndPos, inventoryPos in list(self.inventorySlotPosDict.items()):
			window = self.inventorySlotWindowDict.get(selectWndPos, player.INVENTORY)
			if window == player.INVENTORY:
				itemVNum = getItemVNum(inventoryPos)
				itemCount = getItemCount(inventoryPos)
			else:
				itemVNum = getItemVNum(window, inventoryPos)
				itemCount = getItemCount(window, inventoryPos)

			if itemCount <= 1:
				itemCount = 0

			setItemVNum(selectWndPos, itemVNum, itemCount)

		self.itemSlot.RefreshSlot()

	def OverOutItem(self):
		if None != self.tooltipItem:
			self.tooltipItem.HideToolTip()

	def OverInItem(self, slotIndex):
		if None != self.tooltipItem:
			inventorySlotPos = self.inventorySlotPosDict[slotIndex]
			window = self.inventorySlotWindowDict.get(slotIndex, player.INVENTORY)
			if window == player.INVENTORY:
				self.tooltipItem.SetInventoryItem(inventorySlotPos)
			else:
				self.tooltipItem.SetInventoryItem(inventorySlotPos, window)

