## The aura level window (NOVA-23; OLD root/uiAura.py, ENABLE_AURA_SYSTEM).
##
## C's client hands GC::AURA to game.BINARY_AuraPacket, which makes this
## window and fills it: the aura costume's and the material's inventory cells,
## the aura's level and its experience. The window asks the server with OLD's
## "/aura add|remove|leveling|close" commands; the server refuses them while
## its AURA_SYSTEM_ENABLE is off (the default), so the window never opens then.
## The cells of the two items take no mouse event while it shows (the tradable
## icon, NOVA-13), where OLD painted them green with player.HighlightItem,
## which NEW's client does not have.
import ui
import net
import player
import item
import localeInfo
import mouseModule

EMPTY_CELL = 0xFFFF
LIMIT_RANGE = 1000
EXP_GAUGE_MAX_WIDTH = 188


class AuraWindow(ui.ScriptWindow):

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.isLoaded = 0
		self.PositionOut = 0
		self.PositionStartX = 0
		self.PositionStartY = 0
		self.tooltipItem = None
		self.itemSlots = {}
		self.auraCell = EMPTY_CELL
		self.materialCell = EMPTY_CELL
		self.level = 1
		self.exp = 0
		self.expRequired = 0
		self.titleBar = None
		self.titleName = None
		self.btnAccept = None
		self.btnCancel = None
		self.auraSlot = None
		self.levelText = None
		self.expGaugeBG = None
		self.expGaugeFill = None
		self.expPercentText = None
		self.expText = None
		self.wndInventory = None
		self.wndExtraInventory = None
		self.lockedItems = []
		self.LoadWindow()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def Destroy(self):
		self._UnlockAll()
		self.Hide()
		self.ClearDictionary()
		self.titleBar = None
		self.titleName = None
		self.btnAccept = None
		self.btnCancel = None
		self.auraSlot = None
		self.tooltipItem = None
		self.levelText = None
		self.expGaugeBG = None
		self.expGaugeFill = None
		self.expPercentText = None
		self.expText = None
		self.PositionOut = 0
		self.PositionStartX = 0
		self.PositionStartY = 0
		self.itemSlots = {}

	def LoadWindow(self):
		if self.isLoaded:
			return

		self.isLoaded = 1

		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/aura_levelupwindow.py")
		except:
			import exception
			exception.Abort("AuraWindow.LoadDialog.LoadScript")

		try:
			self.titleBar = self.GetChild("TitleBar")
			self.titleName = self.GetChild("TitleName")
			self.btnAccept = self.GetChild("AcceptButton")
			self.btnCancel = self.GetChild("CancelButton")
			self.auraSlot = self.GetChild("AuraSlot")
			self.levelText = self.GetChild("LevelText")
			self.expGaugeBG = self.GetChild("ExpGaugeBG")
			self.expGaugeFill = self.GetChild("ExpGaugeFill")
			self.expPercentText = self.GetChild("ExpPercentText")
			self.expText = self.GetChild("ExpText")
		except:
			import exception
			exception.Abort("AuraWindow.LoadDialog.BindObject")

		self.auraSlot.SetSelectEmptySlotEvent(ui.__mem_func__(self.OnSelectEmptySlot))
		self.auraSlot.SetUnselectItemSlotEvent(ui.__mem_func__(self.OnSelectItemSlot))
		self.auraSlot.SetUseSlotEvent(ui.__mem_func__(self.OnSelectItemSlot))
		self.auraSlot.SetOverInItemEvent(ui.__mem_func__(self.OnOverInItem))
		self.auraSlot.SetOverOutItemEvent(ui.__mem_func__(self.OnOverOutItem))
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.OnClose))
		self.btnCancel.SetEvent(ui.__mem_func__(self.OnClose))
		self.btnAccept.SetEvent(ui.__mem_func__(self.OnAccept))

		self.Hide()

	def SetItemToolTip(self, itemTooltip):
		self.tooltipItem = itemTooltip

	## The tradable icon (NOVA-13), as the refine dialog does it.
	def SetInven(self, wndInventory, wndExtraInventory=None):
		self.wndInventory = wndInventory
		self.wndExtraInventory = wndExtraInventory

	def __InventoryWindowOf(self, window):
		if window == player.INVENTORY:
			return self.wndInventory
		if window == player.EXTRA_INVENTORY:
			return self.wndExtraInventory
		return None

	def RefreshLockedSlot(self):
		for (window, cell) in self.lockedItems:
			wnd = self.__InventoryWindowOf(window)
			if wnd:
				wnd.SetCantMouseEventCell(cell)

	def SetLevel(self, level):
		self.level = level

	def SetExp(self, exp, expRequired):
		self.exp = exp
		self.expRequired = expRequired

	def _RefreshExpDisplay(self):
		hasAura = self.auraCell != EMPTY_CELL

		if not hasAura:
			if self.levelText:
				self.levelText.SetText("")
			if self.expGaugeBG:
				self.expGaugeBG.Hide()
			if self.expGaugeFill:
				self.expGaugeFill.Hide()
			if self.expPercentText:
				self.expPercentText.SetText("")
			if self.expText:
				self.expText.SetText("")
			return

		if self.levelText:
			self.levelText.SetText(localeInfo.AURA_WINDOW_LEVEL % self.level)

		if self.expGaugeBG:
			self.expGaugeBG.Show()
		if self.expGaugeFill:
			self.expGaugeFill.Show()

		if self.expRequired == 0:
			if self.expGaugeFill:
				self.expGaugeFill.SetSize(EXP_GAUGE_MAX_WIDTH, 12)
			if self.expPercentText:
				self.expPercentText.SetText(localeInfo.AURA_WINDOW_MAX)
			if self.expText:
				self.expText.SetText("")
		else:
			pct = float(self.exp) / float(self.expRequired)
			fillWidth = int(EXP_GAUGE_MAX_WIDTH * pct)
			if self.expGaugeFill:
				self.expGaugeFill.SetSize(max(0, fillWidth), 12)
			if self.expPercentText:
				self.expPercentText.SetText("%d%%" % int(pct * 100))
			if self.expText:
				self.expText.SetText(localeInfo.AURA_WINDOW_EXP % (localeInfo.NumberToString(self.exp), localeInfo.NumberToString(self.expRequired)))

	def SetAuraCell(self, cell):
		self.auraCell = cell
		self._RefreshSlots()

	def SetMaterialCell(self, cell):
		self.materialCell = cell
		self._RefreshSlots()

	def _LockCells(self):
		"""The cells of the two items, in their windows, take no mouse event
		(OLD's _LockCell and _UnlockCell)."""
		self._UnlockAll()
		self.lockedItems = [(self._GetItemWindowType(cell), cell) for cell in self.itemSlots.values()]
		self.RefreshLockedSlot()

	def _UnlockAll(self):
		cells, self.lockedItems = self.lockedItems, []
		for (window, cell) in cells:
			wnd = self.__InventoryWindowOf(window)
			if wnd:
				wnd.SetCanMouseEventCell(cell)

	def _GetItemWindowType(self, cell):
		if player.GetItemIndex(cell):
			return player.INVENTORY
		if player.GetItemIndex(player.EXTRA_INVENTORY, cell):
			return player.EXTRA_INVENTORY
		return player.INVENTORY

	def _GetItemVnum(self, cell):
		itemVnum = player.GetItemIndex(cell)
		if not itemVnum:
			itemVnum = player.GetItemIndex(player.EXTRA_INVENTORY, cell)
		return itemVnum

	def _GetItemCount(self, cell):
		wndType = self._GetItemWindowType(cell)
		return player.GetItemCount(wndType, cell)

	def _RefreshSlots(self):
		if not self.auraSlot:
			return

		self.itemSlots.clear()
		self.auraSlot.ClearSlot(item.AURA_SLOT_MAIN)
		self.auraSlot.ClearSlot(item.AURA_SLOT_MATERIAL)

		if self.auraCell != EMPTY_CELL:
			itemVnum = self._GetItemVnum(self.auraCell)
			if itemVnum:
				self.auraSlot.SetItemSlot(item.AURA_SLOT_MAIN, itemVnum, 0)
			self.itemSlots[item.AURA_SLOT_MAIN] = self.auraCell

		if self.materialCell != EMPTY_CELL:
			itemVnum = self._GetItemVnum(self.materialCell)
			if itemVnum:
				itemCount = self._GetItemCount(self.materialCell)
				if itemCount <= 1:
					itemCount = 0
				self.auraSlot.SetItemSlot(item.AURA_SLOT_MATERIAL, itemVnum, itemCount)
			self.itemSlots[item.AURA_SLOT_MATERIAL] = self.materialCell

		self.auraSlot.RefreshSlot()
		self._LockCells()
		self._RefreshExpDisplay()

	def IsOpened(self):
		if self.IsShow() and self.isLoaded:
			return True
		return False

	def Open(self):
		self.PositionOut = 0
		(self.PositionStartX, self.PositionStartY, z) = player.GetMainCharacterPosition()
		self._RefreshSlots()
		self.Show()

	def Close(self):
		if self.tooltipItem:
			self.tooltipItem.HideToolTip()
		self._UnlockAll()
		self.auraCell = EMPTY_CELL
		self.materialCell = EMPTY_CELL
		self._RefreshSlots()
		self.Hide()

	def OnClose(self):
		net.SendChatPacket("/aura close")
		self.Close()

	def OnPressEscapeKey(self):
		self.OnClose()
		return True

	def OnAccept(self):
		net.SendChatPacket("/aura leveling")

	def OnUpdate(self):
		(x, y, z) = player.GetMainCharacterPosition()
		if abs(x - self.PositionStartX) >= LIMIT_RANGE or abs(y - self.PositionStartY) >= LIMIT_RANGE:
			if not self.PositionOut:
				self.PositionOut += 1
				self.OnClose()

	def OnSelectEmptySlot(self, selectedSlotPos):
		isAttached = mouseModule.mouseController.isAttached()
		if not isAttached:
			return

		attachedSlotType = mouseModule.mouseController.GetAttachedType()
		attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
		attachedInvenType = player.SlotTypeToInvenType(attachedSlotType)
		mouseModule.mouseController.DeattachObject()

		if attachedSlotType == player.SLOT_TYPE_INVENTORY and attachedInvenType == player.INVENTORY:
			net.SendChatPacket("/aura add %d %d %d" % (selectedSlotPos, attachedInvenType, attachedSlotPos))
		elif attachedSlotType == player.SLOT_TYPE_EXTRA_INVENTORY:
			net.SendChatPacket("/aura add %d %d %d" % (selectedSlotPos, attachedInvenType, attachedSlotPos))

	def OnSelectItemSlot(self, selectedSlotPos):
		mouseModule.mouseController.DeattachObject()
		net.SendChatPacket("/aura remove %d" % selectedSlotPos)

	def OnOverInItem(self, selectedSlotPos):
		if self.tooltipItem:
			if selectedSlotPos == item.AURA_SLOT_MAIN and self.auraCell != EMPTY_CELL:
				self.tooltipItem.SetInventoryItem(self.auraCell, self._GetItemWindowType(self.auraCell))
			elif selectedSlotPos == item.AURA_SLOT_MATERIAL and self.materialCell != EMPTY_CELL:
				self.tooltipItem.SetInventoryItem(self.materialCell, self._GetItemWindowType(self.materialCell))

	def OnOverOutItem(self):
		if self.tooltipItem:
			self.tooltipItem.HideToolTip()
