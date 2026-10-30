import dbg
import app
import player
import item
import net
import snd
import ui
import uiToolTip
import localeInfo

class AttachMetinDialog(ui.ScriptWindow):
	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.__LoadScript()

		self.metinItemPos = 0
		self.targetItemPos = 0
		self.metinWindow = player.INVENTORY
		self.wndInventory = None
		self.wndExtraInventory = None
		# [(window, cell)]: the stone's and the target's cells while the dialog shows.
		self.lockedItems = []

	def __LoadScript(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "uiscript/attachstonedialog.py")

		except:
			import exception
			exception.Abort("AttachStoneDialog.__LoadScript.LoadObject")

		try:
			self.board = self.GetChild("Board")
			self.titleBar = self.GetChild("TitleBar")
			self.metinImage = self.GetChild("MetinImage")
			self.GetChild("AcceptButton").SetEvent(ui.__mem_func__(self.Accept))
			self.GetChild("CancelButton").SetEvent(ui.__mem_func__(self.Close))
		except:
			import exception
			exception.Abort("AttachStoneDialog.__LoadScript.BindObject")

		oldToolTip = uiToolTip.ItemToolTip()

		oldToolTip.SetParent(self)
		oldToolTip.SetPosition(15, 38)
		oldToolTip.SetFollow(False)
		oldToolTip.Show()

		self.oldToolTip = oldToolTip

		newToolTip = uiToolTip.ItemToolTip()

		newToolTip.SetParent(self)
		newToolTip.SetPosition(230 + 20, 38)
		newToolTip.SetFollow(False)
		newToolTip.Show()

		self.newToolTip = newToolTip

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def Destroy(self):
		self.ClearDictionary()
		self.board = 0
		self.titleBar = 0
		self.metinImage = 0
		self.toolTip = 0

	def CanAttachMetin(self, slot, metin):
		if item.METIN_NORMAL == metin:
			if player.METIN_SOCKET_TYPE_SILVER == slot or player.METIN_SOCKET_TYPE_GOLD == slot:
				return True

		elif item.METIN_GOLD == metin:
			if player.METIN_SOCKET_TYPE_GOLD == slot:
				return True

	def Open(self, metinItemPos, targetItemPos, metinWindow=player.INVENTORY):
		## The stone may sit in the special inventory (NOVA-16; OLD
		## uiAttachMetin.py:91-99); the target is always an inventory item.
		self.metinItemPos = metinItemPos
		self.targetItemPos = targetItemPos
		self.metinWindow = metinWindow

		if metinWindow == player.INVENTORY:
			metinIndex = player.GetItemIndex(metinItemPos)
		else:
			metinIndex = player.GetItemIndex(metinWindow, metinItemPos)
		itemIndex = player.GetItemIndex(targetItemPos)

		self.oldToolTip.ClearToolTip()
		self.newToolTip.ClearToolTip()

		item.SelectItem(metinIndex)
		metinSubType = item.GetItemSubType()

		try:
			self.metinImage.LoadImage(item.GetIconImageFileName())
		except:
			dbg.TraceError("AttachMetinDialog.Open.LoadImage - Failed to find item data")

		# MR-12: Fix attribute and metin socket order display in tooltip
		# Get actual item attributes/bonuses for display
		attrSlot = []

		for i in range(player.ATTRIBUTE_SLOT_MAX_NUM):
			attrSlot.append(player.GetItemAttribute(targetItemPos, i))

		metinSlot = []

		for i in range(player.METIN_SOCKET_MAX_NUM):
			metinSlot.append(player.GetItemMetinSocket(targetItemPos, i))

		for i in range(player.METIN_SOCKET_MAX_NUM):
			slotData = metinSlot[i]

			if self.CanAttachMetin(slotData, metinSubType):
				metinSlot[i] = metinIndex

				break

		self.newToolTip.AddItemData(itemIndex, metinSlot, attrSlot)
		item.SelectItem(metinIndex)

		metinSlot = []

		for i in range(player.METIN_SOCKET_MAX_NUM):
			metinSlot.append(player.GetItemMetinSocket(targetItemPos, i))

		self.oldToolTip.ResizeToolTipWidth(self.newToolTip.GetWidth())
		self.oldToolTip.AddItemData(itemIndex, metinSlot, attrSlot)
		# MR-12: -- END OF -- Fix attribute and metin socket order display in tooltip

		self.UpdateDialog()
		self.SetTop()
		self.Show()

		self.__LockCells((metinWindow, metinItemPos), (player.INVENTORY, targetItemPos))

	def UpdateDialog(self):
		newWidth = 15 + self.oldToolTip.GetWidth() + 45 + self.newToolTip.GetWidth() + 15
		newHeight = self.newToolTip.GetHeight() + 98

		self.newToolTip.SetPosition(15 + self.oldToolTip.GetWidth() + 45, 38)

		if app.IsRTL():
			self.board.SetPosition(newWidth, 0)

			(x, y) = self.titleBar.GetLocalPosition()
			self.titleBar.SetPosition(newWidth - 15, y)

		self.board.SetSize(newWidth, newHeight)
		self.titleBar.SetWidth(newWidth-15)
		self.SetSize(newWidth, newHeight)

		(x, y) = self.GetLocalPosition()
		self.SetPosition(x, y)

	def Accept(self):
		## OLD uiAttachMetin.py:156-160: the stone's window to the inventory target.
		if self.metinWindow == player.INVENTORY:
			net.SendItemUseToItemPacket(self.metinItemPos, self.targetItemPos)
		else:
			net.SendItemUseToItemPacket(self.metinWindow, self.metinItemPos, player.INVENTORY, self.targetItemPos)
		snd.PlaySound("sound/ui/metinstone_insert.wav")
		self.Close()

	def Close(self):
		self.Hide()
		self.__ReleaseCells()

	## The tradable icon (NOVA-13; OLD uiAttachMetin.py:135-193): the cells of the items the
	## dialog works on take no mouse event while it shows.
	def SetInven(self, wndInventory, wndExtraInventory=None):
		self.wndInventory = wndInventory
		self.wndExtraInventory = wndExtraInventory

	def __InventoryWindowOf(self, window):
		if window == player.INVENTORY:
			return self.wndInventory
		if window == player.EXTRA_INVENTORY:
			return self.wndExtraInventory
		return None

	def __LockCells(self, *cells):
		self.__ReleaseCells()
		self.lockedItems = list(cells)
		self.RefreshLockedSlot()

	def __ReleaseCells(self):
		cells, self.lockedItems = self.lockedItems, []
		for (window, cell) in cells:
			wnd = self.__InventoryWindowOf(window)
			if wnd:
				wnd.SetCanMouseEventCell(cell)

	def RefreshLockedSlot(self):
		for (window, cell) in self.lockedItems:
			wnd = self.__InventoryWindowOf(window)
			if wnd:
				wnd.SetCantMouseEventCell(cell)
