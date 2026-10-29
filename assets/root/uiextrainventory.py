import ui
import player
import mouseModule
import net
import app
import snd
import item
import chat
import exchange
import uiCommon
import uiPickMoney
import uiInventory
import uiPrivateShopBuilder # Prevent ItemMove while private shop is open
import localeInfo
import constInfo
import ime

## The special inventory (NOVA-16; OLD uiExtraInventory.py): the extra
## inventory window (player.EXTRA_INVENTORY, 1440 cells) in five categories
## of 5 x 9 pages, scrolls, materials, stones and chests with five pages each
## and costumes with twelve. A page cell's global cell is the category's first
## cell plus page * 45 plus the local cell (player.GetExtraInventoryCategoryRange).
##
## OLD's search field, sort and group buttons (NOVA-131), mark sell, wiki,
## chest preview, pet preview and aura window are not ported. Every legacy
## method here keeps its arguments, so NovaUI can run it from a subclass.

## The category the window opens on (OLD: materials).
DEFAULT_CATEGORY = 1


class ExtraInventoryWindow(ui.ScriptWindow):

	def __init__(self):
		ui.ScriptWindow.__init__(self)

		self.isLoaded = 0
		self.interface = None
		self.tooltipItem = None
		self.wndDragonSoulRefine = None
		self.questionDialog = None
		self.dlgPickMoney = None
		self.wndItem = None
		self.inventoryTab = []
		self.categoryTab = []
		self.category = DEFAULT_CATEGORY
		self.inventoryPageIndex = 0
		self.sellingSlotNumber = -1
		self.sellingSlotitemIndex = 0
		self.sellingSlotitemCount = 0

		self.__LoadWindow()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		if self.isLoaded == 1:
			return

		self.isLoaded = 1

		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/ExtraInventoryWindow.py")
		except:
			import exception
			exception.Abort("ExtraInventoryWindow.LoadWindow.LoadObject")

		try:
			self.GetChild("TitleBar").SetCloseEvent(ui.__mem_func__(self.Close))
			wndItem = self.GetChild("ItemSlot")

			self.inventoryTab = []
			for page in range(player.EXTRA_INVENTORY_COSTUME_PAGE_COUNT):
				self.inventoryTab.append(self.GetChild("Inventory_Tab_%02d" % (page + 1)))

			self.categoryTab = []
			for category in range(player.EXTRA_INVENTORY_CATEGORY_COUNT):
				self.categoryTab.append(self.GetChild("Cat_%02d" % category))
		except:
			import exception
			exception.Abort("ExtraInventoryWindow.LoadWindow.BindObject")

		wndItem.SetSelectEmptySlotEvent(ui.__mem_func__(self.SelectEmptySlot))
		wndItem.SetSelectItemSlotEvent(ui.__mem_func__(self.SelectItemSlot))
		wndItem.SetUnselectItemSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndItem.SetUseSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndItem.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		wndItem.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		self.wndItem = wndItem

		for page, tab in enumerate(self.inventoryTab):
			tab.SetEvent(lambda arg=page: self.SetInventoryPage(arg))

		for category, tab in enumerate(self.categoryTab):
			tab.SetEvent(lambda arg=category: self.SetCategory(arg))

		## PickMoneyDialog (the split of a stack)
		dlgPickMoney = uiPickMoney.PickMoneyDialog()
		dlgPickMoney.LoadDialog()
		dlgPickMoney.Hide()
		self.dlgPickMoney = dlgPickMoney

		self.SetCategory(self.category)

	def Destroy(self):
		self.ClearDictionary()

		if self.dlgPickMoney:
			self.dlgPickMoney.Destroy()
			self.dlgPickMoney = None

		self.tooltipItem = None
		self.wndItem = None
		self.questionDialog = None
		self.interface = None
		self.wndDragonSoulRefine = None
		self.inventoryTab = []
		self.categoryTab = []

	def BindInterfaceClass(self, interface):
		self.interface = interface

	def SetItemToolTip(self, tooltipItem):
		self.tooltipItem = tooltipItem

	def SetDragonSoulRefineWindow(self, wndDragonSoulRefine):
		self.wndDragonSoulRefine = wndDragonSoulRefine

	def Show(self):
		self.__LoadWindow()
		ui.ScriptWindow.Show(self)
		self.RefreshItemSlot()

	def Open(self):
		self.Show()
		self.SetTop()

	def Close(self):
		if constInfo.GET_ITEM_QUESTION_DIALOG_STATUS():
			self.OnCloseQuestionDialog()
			return

		if None != self.tooltipItem:
			self.tooltipItem.HideToolTip()

		if self.dlgPickMoney:
			self.dlgPickMoney.Close()

		self.Hide()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def OnTop(self):
		if None != self.tooltipItem:
			self.tooltipItem.SetTop()

	## Categories and pages
	def GetCategory(self):
		return self.category

	def GetInventoryPageIndex(self):
		return self.inventoryPageIndex

	def GetCategoryRange(self, category=None):
		"""(first, end): the category's cells (C++ EXTRA_INVENTORY_CATEGORY_*)."""
		if category is None:
			category = self.category
		return player.GetExtraInventoryCategoryRange(category)

	def GetPageCount(self, category=None):
		(first, end) = self.GetCategoryRange(category)
		return max(1, (end - first) // player.EXTRA_INVENTORY_PAGE_SIZE)

	def SetCategory(self, category):
		self.category = category

		for index, tab in enumerate(self.categoryTab):
			if index == category:
				tab.Down()
			else:
				tab.SetUp()

		pageCount = self.GetPageCount(category)
		for page, tab in enumerate(self.inventoryTab):
			if page < pageCount:
				tab.Show()
			else:
				tab.Hide()

		self.SetInventoryPage(0)

	def SetInventoryPage(self, page):
		self.inventoryPageIndex = page

		for index, tab in enumerate(self.inventoryTab):
			if index == page:
				tab.Down()
			else:
				tab.SetUp()

		self.RefreshItemSlot()

	def OnScrollWheel(self, len):
		if len >= 0:
			page = max(0, self.inventoryPageIndex - 1)
		else:
			page = min(self.GetPageCount() - 1, self.inventoryPageIndex + 1)

		self.SetInventoryPage(page)
		return True

	def __InventoryLocalSlotPosToGlobalSlotPos(self, local):
		(first, end) = self.GetCategoryRange()
		return first + self.inventoryPageIndex * player.EXTRA_INVENTORY_PAGE_SIZE + local

	def GlobalSlotPos(self, local):
		"""The extra inventory cell of the visible page's cell `local`."""
		return self.__InventoryLocalSlotPosToGlobalSlotPos(local)

	def RefreshItemSlot(self):
		## Only the visible page, and only while the window shows (OLD).
		if not self.IsShow():
			return

		getItemVNum = player.GetItemIndex
		getItemCount = player.GetItemCount

		for i in range(player.EXTRA_INVENTORY_PAGE_SIZE):
			slotNumber = self.__InventoryLocalSlotPosToGlobalSlotPos(i)

			itemCount = getItemCount(player.EXTRA_INVENTORY, slotNumber)
			if 0 == itemCount:
				self.wndItem.ClearSlot(i)
				continue
			elif 1 == itemCount:
				itemCount = 0

			self.wndItem.SetItemSlot(i, getItemVNum(player.EXTRA_INVENTORY, slotNumber), itemCount)

		self.wndItem.RefreshSlot()

	## Slot events
	def SelectEmptySlot(self, selectedSlotPos):
		if constInfo.GET_ITEM_QUESTION_DIALOG_STATUS() == 1:
			return

		selectedSlotPos = self.__InventoryLocalSlotPosToGlobalSlotPos(selectedSlotPos)

		if mouseModule.mouseController.isAttached():
			attachedSlotType = mouseModule.mouseController.GetAttachedType()
			attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
			attachedCount = mouseModule.mouseController.GetAttachedItemCount()
			attachedItemIndex = mouseModule.mouseController.GetAttachedItemIndex()

			if player.SLOT_TYPE_EXTRA_INVENTORY == attachedSlotType:
				self.__SendMoveItemPacket(player.EXTRA_INVENTORY, attachedSlotPos, selectedSlotPos, attachedCount)

			elif player.SLOT_TYPE_INVENTORY == attachedSlotType:
				if player.ITEM_MONEY != attachedItemIndex:
					self.__SendMoveItemPacket(player.INVENTORY, attachedSlotPos, selectedSlotPos, attachedCount)

			elif player.SLOT_TYPE_SAFEBOX == attachedSlotType:
				if player.ITEM_MONEY != attachedItemIndex:
					net.SendSafeboxCheckoutPacket(attachedSlotPos, player.EXTRA_INVENTORY, selectedSlotPos)

			## Past OLD: the mall too; the server checks the category (spec 3.4.7).
			elif player.SLOT_TYPE_MALL == attachedSlotType:
				net.SendMallCheckoutPacket(attachedSlotPos, player.EXTRA_INVENTORY, selectedSlotPos)

			mouseModule.mouseController.DeattachObject()

	def SelectItemSlot(self, itemSlotIndex):
		if constInfo.GET_ITEM_QUESTION_DIALOG_STATUS() == 1:
			return

		itemSlotIndex = self.__InventoryLocalSlotPosToGlobalSlotPos(itemSlotIndex)

		if mouseModule.mouseController.isAttached():
			attachedSlotType = mouseModule.mouseController.GetAttachedType()
			attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
			attachedItemVID = mouseModule.mouseController.GetAttachedItemIndex()

			if player.SLOT_TYPE_EXTRA_INVENTORY == attachedSlotType:
				self.__DropSrcItemToDestItemInInventory(attachedItemVID, attachedSlotPos, itemSlotIndex)

			mouseModule.mouseController.DeattachObject()

		else:
			curCursorNum = app.GetCursor()
			if app.SELL == curCursorNum:
				self.__SellItem(itemSlotIndex)

			elif app.BUY == curCursorNum:
				chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.SHOP_BUY_INFO)

			elif app.IsPressed(app.DIK_LALT):
				link = player.GetItemLink(player.EXTRA_INVENTORY, itemSlotIndex)
				ime.PasteString(link)

			elif app.IsPressed(app.DIK_LSHIFT):
				itemCount = player.GetItemCount(player.EXTRA_INVENTORY, itemSlotIndex)

				if itemCount > 1:
					self.dlgPickMoney.SetTitleName(localeInfo.PICK_ITEM_TITLE)
					self.dlgPickMoney.SetAcceptEvent(ui.__mem_func__(self.OnPickItem))
					self.dlgPickMoney.Open(itemCount)
					self.dlgPickMoney.itemGlobalSlotIndex = itemSlotIndex

			else:
				selectedItemVNum = player.GetItemIndex(player.EXTRA_INVENTORY, itemSlotIndex)
				itemCount = player.GetItemCount(player.EXTRA_INVENTORY, itemSlotIndex)
				mouseModule.mouseController.AttachObject(self, player.SLOT_TYPE_EXTRA_INVENTORY, itemSlotIndex, selectedItemVNum, itemCount)

				if item.IsKey(selectedItemVNum):
					self.wndItem.SetUseMode(True)
				else:
					self.wndItem.SetUseMode(False)

				snd.PlaySound("sound/ui/pick.wav")

	def OnPickItem(self, count):
		itemSlotIndex = self.dlgPickMoney.itemGlobalSlotIndex
		selectedItemVNum = player.GetItemIndex(player.EXTRA_INVENTORY, itemSlotIndex)
		mouseModule.mouseController.AttachObject(self, player.SLOT_TYPE_EXTRA_INVENTORY, itemSlotIndex, selectedItemVNum, count)

	def __DropSrcItemToDestItemInInventory(self, srcItemVID, srcItemSlotPos, dstItemSlotPos):
		## A key on a box (both are chests, category 3): the key opens it
		## (OLD :795-799). Anything else moves, the whole stack as the
		## inventory's drop on an item does (a stack, a swap).
		if srcItemSlotPos == dstItemSlotPos:
			return

		if item.IsKey(srcItemVID):
			self.__SendUseItemToItemPacket(srcItemSlotPos, dstItemSlotPos)
		else:
			self.__SendMoveItemPacket(player.EXTRA_INVENTORY, srcItemSlotPos, dstItemSlotPos, 0)

	def __SellItem(self, itemSlotPos):
		self.sellingSlotNumber = itemSlotPos

		itemIndex = player.GetItemIndex(player.EXTRA_INVENTORY, itemSlotPos)
		itemCount = player.GetItemCount(player.EXTRA_INVENTORY, itemSlotPos)

		self.sellingSlotitemIndex = itemIndex
		self.sellingSlotitemCount = itemCount

		item.SelectItem(itemIndex)

		if item.IsAntiFlag(item.ANTIFLAG_SELL):
			popup = uiCommon.PopupDialog()
			popup.SetText(localeInfo.SHOP_CANNOT_SELL_ITEM)
			popup.SetAcceptEvent(self.__OnClosePopupDialog)
			popup.Open()
			self.popup = popup
			return

		itemPrice = item.GetISellItemPrice()

		if item.Is1GoldItem():
			itemPrice = itemCount // itemPrice // 5
		else:
			itemPrice = itemPrice * itemCount // 5

		item.GetItemName(itemIndex)
		itemName = item.GetItemName()

		self.questionDialog = uiCommon.QuestionDialog()
		self.questionDialog.SetText(localeInfo.DO_YOU_SELL_ITEM(itemName, itemCount, itemPrice))
		self.questionDialog.SetAcceptEvent(ui.__mem_func__(self.SellItem))
		self.questionDialog.SetCancelEvent(ui.__mem_func__(self.OnCloseQuestionDialog))
		self.questionDialog.Open()
		self.questionDialog.count = itemCount

		constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(1)

	def SellItem(self):
		if self.sellingSlotitemIndex == player.GetItemIndex(player.EXTRA_INVENTORY, self.sellingSlotNumber):
			if self.sellingSlotitemCount == player.GetItemCount(player.EXTRA_INVENTORY, self.sellingSlotNumber):
				net.SendShopSellPacketNew(self.sellingSlotNumber, self.questionDialog.count, player.EXTRA_INVENTORY)
				snd.PlaySound("sound/ui/money.wav")
		self.OnCloseQuestionDialog()

	def __OnClosePopupDialog(self):
		self.popup = None

	def OnCloseQuestionDialog(self):
		if not self.questionDialog:
			return

		self.questionDialog.Close()
		self.questionDialog = None
		constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(0)

	def OverOutItem(self):
		self.wndItem.SetUsableItem(False)
		if None != self.tooltipItem:
			self.tooltipItem.HideToolTip()

	def OverInItem(self, overSlotPos):
		overSlotPos = self.__InventoryLocalSlotPosToGlobalSlotPos(overSlotPos)
		self.wndItem.SetUsableItem(False)

		if mouseModule.mouseController.isAttached():
			attachedItemType = mouseModule.mouseController.GetAttachedType()
			if player.SLOT_TYPE_EXTRA_INVENTORY == attachedItemType:
				attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
				attachedItemVNum = mouseModule.mouseController.GetAttachedItemIndex()

				if self.__CanUseSrcItemToDstItem(attachedItemVNum, attachedSlotPos, overSlotPos):
					self.wndItem.SetUsableItem(True)

		self.ShowToolTip(overSlotPos)

	def __CanUseSrcItemToDstItem(self, srcItemVNum, srcSlotPos, dstSlotPos):
		if srcSlotPos == dstSlotPos:
			return False

		if item.IsKey(srcItemVNum):
			if player.CanUnlock(srcItemVNum, player.EXTRA_INVENTORY, dstSlotPos):
				return True

		return False

	def ShowToolTip(self, slotIndex):
		if None != self.tooltipItem:
			self.tooltipItem.SetInventoryItem(slotIndex, player.EXTRA_INVENTORY)

	def UseItemSlot(self, slotIndex):
		curCursorNum = app.GetCursor()
		if app.SELL == curCursorNum:
			return

		if constInfo.GET_ITEM_QUESTION_DIALOG_STATUS():
			return

		slotIndex = self.__InventoryLocalSlotPosToGlobalSlotPos(slotIndex)

		## A Dragon Bean (a material) into the open Dragon Soul refine window,
		## as the inventory does for its own cells.
		if app.ENABLE_DRAGON_SOUL_SYSTEM:
			if self.wndDragonSoulRefine and self.wndDragonSoulRefine.IsShow():
				self.wndDragonSoulRefine.AutoSetItem((player.EXTRA_INVENTORY, slotIndex), 1)
				return

		self.__UseItem(slotIndex)
		mouseModule.mouseController.DeattachObject()
		self.OverOutItem()

	def IsSafeboxOpen(self):
		"""Whether the safebox window shows (NEW's safebox module has no
		IsOpen, OLD's did)."""
		if not self.interface:
			return False
		isSafeboxOpen = getattr(self.interface, "IsSafeboxOpen", None)
		return bool(isSafeboxOpen and isSafeboxOpen())

	def __UseItem(self, slotIndex):
		## OLD :914-924: Shift + right-click to the open safebox, Ctrl +
		## right-click to the open trade, otherwise Ctrl + right-click moves the
		## item to the main inventory (the server takes costumes and scrolls).
		if app.IsPressed(app.DIK_LSHIFT) and self.IsSafeboxOpen():
			itemVnum = player.GetItemIndex(player.EXTRA_INVENTORY, slotIndex)
			net.SendSafeboxCheckinPacket(player.EXTRA_INVENTORY, slotIndex, uiInventory.SafeboxCheckinCell(itemVnum))
			return
		elif app.IsPressed(app.DIK_LCONTROL) and exchange.isTrading():
			net.SendExchangeItemAddPacket(player.EXTRA_INVENTORY, slotIndex, 0)
			return
		elif app.IsPressed(app.DIK_LCONTROL):
			net.SendItemTransferPacket(player.EXTRA_INVENTORY, slotIndex, player.INVENTORY)
			return

		ItemVNum = player.GetItemIndex(player.EXTRA_INVENTORY, slotIndex)
		item.SelectItem(ItemVNum)
		if item.IsFlag(item.ITEM_FLAG_CONFIRM_WHEN_USE):
			self.questionDialog = uiCommon.QuestionDialog()
			self.questionDialog.SetText(localeInfo.INVENTORY_REALLY_USE_ITEM)
			self.questionDialog.SetAcceptEvent(ui.__mem_func__(self.__UseItemQuestionDialog_OnAccept))
			self.questionDialog.SetCancelEvent(ui.__mem_func__(self.__UseItemQuestionDialog_OnCancel))
			self.questionDialog.Open()
			self.questionDialog.slotIndex = slotIndex

			constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(1)

		else:
			self.__SendUseItemPacket(slotIndex)

	def __UseItemQuestionDialog_OnCancel(self):
		self.OnCloseQuestionDialog()

	def __UseItemQuestionDialog_OnAccept(self):
		self.__SendUseItemPacket(self.questionDialog.slotIndex)
		self.OnCloseQuestionDialog()

	def __SendUseItemPacket(self, slotPos):
		# Prevent item usage while private shop is open
		if uiPrivateShopBuilder.IsBuildingPrivateShop():
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.USE_ITEM_FAILURE_PRIVATE_SHOP)
			return

		net.SendItemUsePacket(player.EXTRA_INVENTORY, slotPos)

	def __SendUseItemToItemPacket(self, srcSlotPos, dstSlotPos):
		# Prevent item usage while private shop is open
		if uiPrivateShopBuilder.IsBuildingPrivateShop():
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.USE_ITEM_FAILURE_PRIVATE_SHOP)
			return

		net.SendItemUseToItemPacket(player.EXTRA_INVENTORY, srcSlotPos, player.EXTRA_INVENTORY, dstSlotPos)

	def __SendMoveItemPacket(self, srcWindow, srcSlotPos, dstSlotPos, srcItemCount):
		# Prevent item movement while private shop is open
		if uiPrivateShopBuilder.IsBuildingPrivateShop():
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.MOVE_ITEM_FAILURE_PRIVATE_SHOP)
			return

		if srcWindow == player.EXTRA_INVENTORY and srcSlotPos == dstSlotPos:
			return

		net.SendItemMovePacket(srcWindow, srcSlotPos, player.EXTRA_INVENTORY, dstSlotPos, srcItemCount)
