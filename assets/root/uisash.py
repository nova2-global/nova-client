## The sash combine and absorb windows (NOVA-20; OLD root/uiSash.py, __SASH_SYSTEM__).
##
## The server opens them (GC::SASH OPEN, which C's client hands to
## game.ActSash and the Interface's ActSash) and keeps the two slots: the
## windows send the sash module's requests (C's net side of CG::SASH) and show
## what the module holds after each GC::SASH. The cells of the items in the
## window take no mouse event while it shows (the tradable icon, NOVA-13),
## where OLD painted them green with player.HighlightItem, which NEW's client
## does not have.
import ui
import player
import sash
import localeInfo
import mouseModule
import constInfo


class _SashWindow(ui.ScriptWindow):
	"""What OLD's CombineWindow and AbsorbWindow share."""

	SCRIPT = ""

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.isLoaded = 0
		self.PositionOut = 0
		self.PositionStartX = 0
		self.PositionStartY = 0
		self.tooltipItem = None
		self.itemSlots = {}
		self.wndInventory = None
		self.wndExtraInventory = None
		self.lockedItems = []

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def Destroy(self):
		self.__ReleaseCells()
		self.Hide()
		self.ClearDictionary()
		self.titleBar = None
		self.btnAccept = None
		self.btnCancel = None
		self.sashSlot = None
		self.PositionOut = 0
		self.PositionStartX = 0
		self.PositionStartY = 0
		self.tooltipItem = None
		self.itemSlots = {}
		self.isLoaded = 0

	def LoadWindow(self):
		if self.isLoaded:
			return

		self.isLoaded = 1

		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, self.SCRIPT)
		except:
			import exception
			exception.Abort("%s.LoadDialog.LoadScript" % self.__class__.__name__)

		try:
			self.titleBar = self.GetChild("TitleBar")
			self.btnAccept = self.GetChild("AcceptButton")
			self.btnCancel = self.GetChild("CancelButton")
			self.sashSlot = self.GetChild("SashSlot")
			self._BindChildren()
		except:
			import exception
			exception.Abort("%s.LoadDialog.BindObject" % self.__class__.__name__)

		self.sashSlot.SetSelectEmptySlotEvent(ui.__mem_func__(self.OnSelectEmptySlot))
		self.sashSlot.SetUnselectItemSlotEvent(ui.__mem_func__(self.OnSelectItemSlot))
		self.sashSlot.SetUseSlotEvent(ui.__mem_func__(self.OnSelectItemSlot))
		self.sashSlot.SetOverInItemEvent(ui.__mem_func__(self.OnOverInItem))
		self.sashSlot.SetOverOutItemEvent(ui.__mem_func__(self.OnOverOutItem))
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.OnClose))
		self.btnCancel.SetEvent(ui.__mem_func__(self.OnClose))
		self.btnAccept.SetEvent(ui.__mem_func__(self.OnAccept))

	def _BindChildren(self):
		pass

	def SetItemToolTip(self, itemTooltip):
		self.tooltipItem = itemTooltip

	## The tradable icon (NOVA-13), as the refine dialog does it.
	def SetInven(self, wndInventory, wndExtraInventory=None):
		self.wndInventory = wndInventory
		self.wndExtraInventory = wndExtraInventory

	def RefreshLockedSlot(self):
		for cell in self.lockedItems:
			if self.wndInventory:
				self.wndInventory.SetCantMouseEventCell(cell)

	def __LockCells(self):
		self.__ReleaseCells()
		self.lockedItems = list(self.itemSlots.values())
		self.RefreshLockedSlot()

	def __ReleaseCells(self):
		cells, self.lockedItems = self.lockedItems, []
		for cell in cells:
			if self.wndInventory:
				self.wndInventory.SetCanMouseEventCell(cell)

	def _ForgetSlots(self, *slots):
		for slot in slots or list(self.itemSlots):
			self.itemSlots.pop(slot, None)
		self.__LockCells()

	def IsOpened(self):
		if self.IsShow() and self.isLoaded:
			return True

		return False

	def Open(self):
		self.PositionOut = 0
		(self.PositionStartX, self.PositionStartY, z) = player.GetMainCharacterPosition()
		for i in range(sash.WINDOW_MAX_MATERIALS + 1):
			self.sashSlot.ClearSlot(i)

		self.Show()

	def Close(self):
		if self.tooltipItem:
			self.tooltipItem.HideToolTip()

		self.Hide()
		self.itemSlots.clear()
		self.__ReleaseCells()

	def OnClose(self):
		sash.SendCloseRequest()
		self.itemSlots.clear()
		self.__ReleaseCells()

	def OnPressEscapeKey(self):
		self.OnClose()
		return True

	def OnUpdate(self):
		LIMIT_RANGE = sash.LIMIT_RANGE
		(x, y, z) = player.GetMainCharacterPosition()
		if abs(x - self.PositionStartX) >= LIMIT_RANGE or abs(y - self.PositionStartY) >= LIMIT_RANGE:
			if not self.PositionOut:
				self.PositionOut += 1
				self.OnClose()

	def OnSelectEmptySlot(self, selectedSlotPos):
		isAttached = mouseModule.mouseController.isAttached()
		if not isAttached or selectedSlotPos == sash.WINDOW_MAX_MATERIALS:
			return

		attachedSlotType = mouseModule.mouseController.GetAttachedType()
		attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
		attachedInvenType = player.SlotTypeToInvenType(attachedSlotType)
		mouseModule.mouseController.DeattachObject()
		if attachedSlotType == player.SLOT_TYPE_INVENTORY and attachedInvenType == player.INVENTORY:
			sash.Add(attachedInvenType, attachedSlotPos, selectedSlotPos)

	## A right-click on a bag item while the window shows (OLD
	## uiInventory.py:2522-2525): slot 255, the server's first free slot.
	AUTO_SLOT = 255

	def AddItem(self, window, cell):
		sash.Add(window, cell, self.AUTO_SLOT)

	def OnSelectItemSlot(self, selectedSlotPos):
		if selectedSlotPos == sash.WINDOW_MAX_MATERIALS:
			return

		mouseModule.mouseController.DeattachObject()
		sash.Remove(selectedSlotPos)
		if selectedSlotPos == 0:
			self._ForgetSlots()
		else:
			self._ForgetSlots(selectedSlotPos)

	def OnOverOutItem(self):
		if self.tooltipItem:
			self.tooltipItem.HideToolTip()

	def Refresh(self, iAct):
		self.sashSlot.ClearSlot(sash.WINDOW_MAX_MATERIALS)
		for i in range(sash.WINDOW_MAX_MATERIALS):
			self.sashSlot.ClearSlot(i)
			(isHere, iCell) = sash.GetAttachedItem(i)
			if isHere:
				self.sashSlot.SetItemSlot(i, player.GetItemIndex(iCell), 0)
				## OLD tested the cell against the slots ("if iCell not in
				## self.itemSlots"), so a sash in bag cell 0 or 1 was never
				## remembered and stayed marked after the close.
				self.itemSlots[i] = iCell
				if i == int(sash.WINDOW_MAX_MATERIALS - 1):
					(itemVnum, MinAbs, MaxAbs) = sash.GetResultItem()
					if not itemVnum:
						break

					self.sashSlot.SetItemSlot(i + 1, itemVnum, 0)
					break
		self.__LockCells()


class CombineWindow(_SashWindow):
	"""Two sashes of one grade into one of the next (OLD uiSash.CombineWindow)."""

	SCRIPT = "UIScript/sash_combinewindow.py"
	## OLD's place of the check box under the old interface's slots.
	AUTO_COMBINE_Y = 212

	def __init__(self):
		_SashWindow.__init__(self)
		self.LoadWindow()

	def Destroy(self):
		self.needMoney = None
		self.Result = None
		self.checkBox = None
		_SashWindow.Destroy(self)

	def _BindChildren(self):
		self.needMoney = self.GetChild("NeedMoney")
		self.Result = self.GetChild("Result")

	def LoadWindow(self):
		if self.isLoaded:
			return
		_SashWindow.LoadWindow(self)

		self.checkBox = ui.CheckBox()
		self.checkBox.SetParent(self)
		self.checkBox.SetEvent(ui.__mem_func__(self._OnAutoCombineCheck), "ON_CHECK")
		self.checkBox.SetEvent(ui.__mem_func__(self._OnAutoCombineUncheck), "ON_UNCHECK")
		self.checkBox.SetCheckStatus(constInfo.SASH_AUTO_COMBINE)
		self.checkBox.SetTextInfo(localeInfo.SASH_AUTO_COMBINE)
		self.checkBox.SetPosition(0, self.AUTO_COMBINE_Y)
		self.checkBox.SetWindowHorizontalAlignCenter()
		self.checkBox.Show()

	## OLD's _OnAutoCombineToggle(checkType, flag): NEW's check box calls its
	## events without arguments.
	def _OnAutoCombineCheck(self):
		constInfo.SASH_AUTO_COMBINE = True

	def _OnAutoCombineUncheck(self):
		constInfo.SASH_AUTO_COMBINE = False

	def Open(self):
		self.needMoney.SetText(localeInfo.SASH_REFINE_COST % (sash.GetPrice()))
		_SashWindow.Open(self)

	def OnAccept(self):
		sash.SendRefineRequest(constInfo.SASH_AUTO_COMBINE)

	def OnOverInItem(self, selectedSlotPos):
		if self.tooltipItem:
			if selectedSlotPos == sash.WINDOW_MAX_MATERIALS:
				(isHere, iCell) = sash.GetAttachedItem(0)
				if isHere:
					self.tooltipItem.SetSashResultItem(iCell)
			else:
				(isHere, iCell) = sash.GetAttachedItem(selectedSlotPos)
				if isHere:
					self.tooltipItem.SetInventoryItem(iCell)

	def Refresh(self, iAct):
		self.needMoney.SetText(localeInfo.SASH_REFINE_COST % (sash.GetPrice()))
		_SashWindow.Refresh(self, iAct)


class AbsorbWindow(_SashWindow):
	"""A weapon's or an armour's bonuses into a sash (OLD uiSash.AbsorbWindow):
	the Interface loads it after making it."""

	SCRIPT = "UIScript/sash_absorbwindow.py"

	def OnAccept(self):
		sash.SendRefineRequest()

	def OnOverInItem(self, selectedSlotPos):
		if self.tooltipItem:
			if selectedSlotPos == sash.WINDOW_MAX_MATERIALS:
				(isHere1, iCell1) = sash.GetAttachedItem(0)
				(isHere2, iCell2) = sash.GetAttachedItem(1)
				if isHere1 and isHere2:
					self.tooltipItem.SetSashResultAbsItem(iCell1, iCell2)
			else:
				(isHere, iCell) = sash.GetAttachedItem(selectedSlotPos)
				if isHere:
					self.tooltipItem.SetInventoryItem(iCell)
