import net
import player
import item
import snd
import shop
import net
import wndMgr
import app
import chat

import ui
import uiCommon
import mouseModule
import localeInfo
import constInfo

###################################################################################################
## Shop
class ShopDialog(ui.ScriptWindow):

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.tooltipItem = 0
		self.xShopStart = 0
		self.yShopStart = 0
		self.questionDialog = None
		self.popup = None
		self.itemBuyQuestionDialog = None
		self.interface = None

		## The offline shop (NOVA-9): a view of a shop NPC or its owner's panel, in pages of
		## 10 x 8. Its widgets are None until the legacy loader binds them (a NovaUI facade's
		## loader binds its own), and the offline view needs them.
		self.isOfflineShop = False
		self.offlineShopVid = 0
		self.offlineIsOwner = False
		self.offlineFromNpc = False
		self.offlinePage = 0
		self.board = None
		self.titleName = None
		self.pageButtons = []
		self.pageButtonGroup = None
		self.lockOverlays = []
		self.offlineShopWnd = None
		self.dlgPickMoney = None
		self.priceInputBoard = None
		self.expandQuestionDialog = None
		self.resultPopup = None
		self.hoveredSlot = -1
		self.goldAmount = 0
		self.offlineLayout = False

	def __del__(self):
		ui.ScriptWindow.__del__(self)
	
	def __GetRealIndex(self, i):
		return self.tabIdx * shop.SHOP_SLOT_COUNT + i
	
	def Refresh(self):
		if self.isOfflineShop:
			## A visitor's view the client cleared (VIEW_END: no page left) closes, whether VIEW_END
			## reaches EndShop or RefreshShop (k-report.md 5.2 lists it under RefreshShop).
			if self.IsShow() and not self.offlineIsOwner and shop.GetOfflineShopPageCount() < 1:
				self.Close()
				return
			self.RefreshOfflineShop()
			return

		getItemID=shop.GetItemID
		getItemCount=shop.GetItemCount
		setItemID=self.itemSlotWindow.SetItemSlot
		for i in range(shop.SHOP_SLOT_COUNT):
			idx = self.__GetRealIndex(i)
			itemCount = getItemCount(idx)
			if itemCount <= 1:
				itemCount = 0
			setItemID(i, getItemID(idx), itemCount)

		wndMgr.RefreshSlot(self.itemSlotWindow.GetWindowHandle())

	def SetItemData(self, pos, itemID, itemCount, itemPrice):
		shop.SetItemData(pos, itemID, itemCount, itemPrice)

	def LoadDialog(self):
		try:
			PythonScriptLoader = ui.PythonScriptLoader()
			PythonScriptLoader.LoadScriptFile(self, "UIScript/shopdialognew.py")
		except:
			import exception
			exception.Abort("ShopDialog.LoadDialog.LoadObject")

		smallTab1 = None
		smallTab2 = None
		smallTab3 = None
		middleTab1 = None
		middleTab2 = None
		
		try:
			GetObject = self.GetChild
			self.itemSlotWindow = GetObject("ItemSlot")
			self.btnBuy = GetObject("BuyButton")
			self.btnSell = GetObject("SellButton")
			self.btnClose = GetObject("CloseButton")
			self.titleBar = GetObject("TitleBar")
			middleTab1 = GetObject("MiddleTab1")
			middleTab2 = GetObject("MiddleTab2")
			smallTab1 = GetObject("SmallTab1")
			smallTab2 = GetObject("SmallTab2")
			smallTab3 = GetObject("SmallTab3")
			self.board = GetObject("board")
			self.titleName = GetObject("TitleName")
			self.pageButtons = [GetObject("PageButton%d" % i) for i in range(3)]
		except:
			import exception
			exception.Abort("ShopDialog.LoadDialog.BindObject")

		for (i, button) in enumerate(self.pageButtons):
			button.SetEvent(ui.__mem_func__(self.SelectOfflinePage), i)
			button.Hide()

		self.itemSlotWindow.SetSlotStyle(wndMgr.SLOT_STYLE_NONE)
		self.itemSlotWindow.SAFE_SetButtonEvent("LEFT", "EMPTY", self.SelectEmptySlot)
		self.itemSlotWindow.SAFE_SetButtonEvent("LEFT", "EXIST", self.SelectItemSlot)
		self.itemSlotWindow.SAFE_SetButtonEvent("RIGHT", "EXIST", self.UnselectItemSlot)

		self.itemSlotWindow.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		self.itemSlotWindow.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))

		self.btnBuy.SetToggleUpEvent(ui.__mem_func__(self.CancelShopping))
		self.btnBuy.SetToggleDownEvent(ui.__mem_func__(self.OnBuy))

		self.btnSell.SetToggleUpEvent(ui.__mem_func__(self.CancelShopping))
		self.btnSell.SetToggleDownEvent(ui.__mem_func__(self.OnSell))

		self.btnClose.SetEvent(ui.__mem_func__(self.AskClosePrivateShop))

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))

		self.smallRadioButtonGroup = ui.RadioButtonGroup.Create([[smallTab1, lambda : self.OnClickTabButton(0), None], [smallTab2, lambda : self.OnClickTabButton(1), None], [smallTab3, lambda : self.OnClickTabButton(2), None]])
		self.middleRadioButtonGroup = ui.RadioButtonGroup.Create([[middleTab1, lambda : self.OnClickTabButton(0), None], [middleTab2, lambda : self.OnClickTabButton(1), None]])

		self.__HideMiddleTabs()
		self.__HideSmallTabs()
		
		self.tabIdx = 0
		self.coinType = shop.SHOP_COIN_TYPE_GOLD
		
		self.Refresh()
	
	def __ShowBuySellButton(self):
		self.btnBuy.Show()
		self.btnSell.Show()
		
	def __ShowMiddleTabs(self):
		self.middleRadioButtonGroup.Show()
	
	def __ShowSmallTabs(self):
		self.smallRadioButtonGroup.Show()
	
	def __HideBuySellButton(self):
		self.btnBuy.Hide()
		self.btnSell.Hide()
	
	def __HideMiddleTabs(self):
		self.middleRadioButtonGroup.Hide()
	
	def __HideSmallTabs(self):
		self.smallRadioButtonGroup.Hide()
		
	def __SetTabNames(self):
		if shop.GetTabCount() == 2:
			self.middleRadioButtonGroup.SetText(0, shop.GetTabName(0))
			self.middleRadioButtonGroup.SetText(1, shop.GetTabName(1))
		elif shop.GetTabCount() == 3:
			self.smallRadioButtonGroup.SetText(0, shop.GetTabName(0))
			self.smallRadioButtonGroup.SetText(1, shop.GetTabName(1))
			self.smallRadioButtonGroup.SetText(2, shop.GetTabName(2))
	 
 
	def Destroy(self):
		self.Close()
		self.ClearDictionary()

		self.tooltipItem = 0
		self.itemSlotWindow = 0
		self.btnBuy = 0
		self.btnSell = 0
		self.btnClose = 0
		self.titleBar = 0
		self.questionDialog = None
		self.popup = None

		if self.offlineShopWnd:
			self.offlineShopWnd.Destroy()
		if self.dlgPickMoney:
			self.dlgPickMoney.Destroy()
		self.offlineShopWnd = None
		self.dlgPickMoney = None
		self.board = None
		self.titleName = None
		self.pageButtons = []
		self.lockOverlays = []
		self.priceInputBoard = None
		self.expandQuestionDialog = None
		self.resultPopup = None

	def Open(self, vid, multiPage=False):
		"""multiPage: the offline shop of the NPC `vid` (GC VIEW; Interface.OpenOfflineShopDialog),
		in pages of 10 x 8; else NEW's NPC or private shop."""
		if multiPage:
			self.OpenOfflineShopView(vid, True)
			return

		## The owner's panel from the inventory (MANAGE) is no server view, so the server lets an
		## NPC shop or a stall open over it: the panel ends first, with its one LEAVE.
		if self.isOfflineShop:
			self.__EndOfflineSession()
		self.__LeaveOfflineMode()

		isPrivateShop = False
		isMainPlayerPrivateShop = False

		import chr
		if chr.IsNPC(vid):
			isPrivateShop = False
		else:
			isPrivateShop = True

		if player.IsMainCharacterIndex(vid):

			isMainPlayerPrivateShop = True

			self.btnBuy.Hide()
			self.btnSell.Hide()
			self.btnClose.Show()

		else:

			isMainPlayerPrivateShop = False

			self.btnBuy.Show()
			self.btnSell.Show()
			self.btnClose.Hide()

		shop.Open(isPrivateShop, isMainPlayerPrivateShop)

		self.tabIdx = 0

		if isPrivateShop:
			self.__HideMiddleTabs()
			self.__HideSmallTabs()
		else:
			if shop.GetTabCount() == 1:
				self.__ShowBuySellButton()
				self.__HideMiddleTabs()
				self.__HideSmallTabs()
			elif shop.GetTabCount() == 2:
				self.__HideBuySellButton()
				self.__ShowMiddleTabs()
				self.__HideSmallTabs()
				self.__SetTabNames()
				self.middleRadioButtonGroup.OnClick(0)
			elif shop.GetTabCount() == 3:
				self.__HideBuySellButton()
				self.__HideMiddleTabs()
				self.__ShowSmallTabs()
				self.__SetTabNames()
				self.middleRadioButtonGroup.OnClick(1)

		self.Refresh()
		self.SetTop()
		
		self.Show()

		(self.xShopStart, self.yShopStart, z) = player.GetMainCharacterPosition()

		## An NPC shop marks the items it does not buy (NOVA-13; OLD uiShop.py:670-673).
		if not isPrivateShop:
			self.__SetOnTopWindow(player.ON_TOP_WND_SHOP)

	## The tradable icon (NOVA-13; OLD uiShop.py:1365-1370)
	def BindInterface(self, interface):
		self.interface = interface

	def __SetOnTopWindow(self, onTopWnd):
		if not self.interface:
			return
		self.interface.SetOnTopWindow(onTopWnd)
		self.interface.RefreshMarkInventoryBag()

	def OnTop(self):
		if self.IsShow() and not shop.IsPrivateShop():
			self.__SetOnTopWindow(player.ON_TOP_WND_SHOP)

	def Close(self):
		if self.itemBuyQuestionDialog:
			self.itemBuyQuestionDialog.Close()
			self.itemBuyQuestionDialog = None		
			constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(0)
		if self.questionDialog:
			self.OnCloseQuestionDialog()
		shop.Close()
		if self.isOfflineShop:
			## An offline shop's view or panel ends with LEAVE (spec 1.1 sub 16), never the NPC
			## shop's END.
			self.__EndOfflineSession()
		elif not self.offlineLayout:
			## The offline layout stays until an NPC shop opens, so an offline view the client
			## already closed (VIEW_END: RefreshShop, then EndShop) sends nothing more.
			net.SendShopEndPacket()
		self.CancelShopping()
		self.tooltipItem.HideToolTip()
		self.Hide()
		self.__SetOnTopWindow(player.ON_TOP_WND_NONE)

	def GetIndexFromSlotPos(self, slotPos):
		return self.tabIdx * shop.SHOP_SLOT_COUNT + slotPos
		
	def OnClickTabButton(self, idx):
		self.tabIdx = idx
		self.Refresh()
		
	def AskClosePrivateShop(self):
		questionDialog = uiCommon.QuestionDialog()
		questionDialog.SetText(localeInfo.PRIVATE_SHOP_CLOSE_QUESTION)
		questionDialog.SetAcceptEvent(ui.__mem_func__(self.OnClosePrivateShop))
		questionDialog.SetCancelEvent(ui.__mem_func__(self.OnCloseQuestionDialog))
		questionDialog.Open()
		self.questionDialog = questionDialog

		constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(1)

		return True

	def OnClosePrivateShop(self):
		net.SendChatPacket("/close_shop")
		self.OnCloseQuestionDialog()
		return True

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def OnPressExitKey(self):
		self.Close()
		return True

	def OnBuy(self):
		chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.SHOP_BUY_INFO)
		app.SetCursor(app.BUY)
		self.btnSell.SetUp()

	def OnSell(self):
		chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.SHOP_SELL_INFO)
		app.SetCursor(app.SELL)
		self.btnBuy.SetUp()

	def CancelShopping(self):
		self.btnBuy.SetUp()
		self.btnSell.SetUp()
		app.SetCursor(app.NORMAL)

	def __OnClosePopupDialog(self):
		self.pop = None
		constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(0)

	## 용혼석 팔리는 기능 추가.
	def SellAttachedItem(self):

		if shop.IsPrivateShop():
			mouseModule.mouseController.DeattachObject()
			return

		attachedSlotType = mouseModule.mouseController.GetAttachedType()
		attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
		attachedCount = mouseModule.mouseController.GetAttachedItemCount()
		attachedItemIndex = mouseModule.mouseController.GetAttachedItemIndex()
		
		# if player.SLOT_TYPE_INVENTORY == attachedSlotType or player.SLOT_TYPE_DRAGON_SOUL_INVENTORY == attachedSlotType:
		if player.SLOT_TYPE_INVENTORY == attachedSlotType:
			itemIndex = player.GetItemIndex(attachedSlotPos)
			item.SelectItem(itemIndex)

			if item.IsAntiFlag(item.ANTIFLAG_SELL):
				popup = uiCommon.PopupDialog()
				popup.SetText(localeInfo.SHOP_CANNOT_SELL_ITEM)
				popup.SetAcceptEvent(self.__OnClosePopupDialog)
				popup.Open()
				self.popup = popup
				return
				
			itemtype = player.INVENTORY

			if player.SLOT_TYPE_DRAGON_SOUL_INVENTORY == attachedSlotType:
				itemtype = player.DRAGON_SOUL_INVENTORY
			
			# if player.IsValuableItem(itemtype, attachedSlotPos):
			if player.IsValuableItem(attachedSlotPos):

				itemPrice = item.GetISellItemPrice()

				if item.Is1GoldItem():
					itemPrice = attachedCount // itemPrice // 5
				else:
					itemPrice = itemPrice * max(1, attachedCount) // 5

				itemName = item.GetItemName()

				questionDialog = uiCommon.QuestionDialog()
				questionDialog.SetText(localeInfo.DO_YOU_SELL_ITEM(itemName, attachedCount, itemPrice))

				questionDialog.SetAcceptEvent(lambda arg1=attachedSlotPos, arg2=attachedCount, arg3 = itemtype: self.OnSellItem(arg1, arg2, arg3))
				questionDialog.SetCancelEvent(ui.__mem_func__(self.OnCloseQuestionDialog))
				questionDialog.Open()
				self.questionDialog = questionDialog
		
				constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(1)

			else:
				self.OnSellItem(attachedSlotPos, attachedCount, itemtype)

		## An extra inventory item (NOVA-16; OLD uiShop.py:811-831), always
		## asked as OLD asks: player.IsValuableItem reads an inventory cell.
		elif player.SLOT_TYPE_EXTRA_INVENTORY == attachedSlotType:
			itemIndex = player.GetItemIndex(player.EXTRA_INVENTORY, attachedSlotPos)
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
				itemPrice = attachedCount // itemPrice // 5
			else:
				itemPrice = itemPrice * max(1, attachedCount) // 5

			itemName = item.GetItemName()

			questionDialog = uiCommon.QuestionDialog()
			questionDialog.SetText(localeInfo.DO_YOU_SELL_ITEM(itemName, attachedCount, itemPrice))
			questionDialog.SetAcceptEvent(lambda arg1=attachedSlotPos, arg2=attachedCount, arg3=player.EXTRA_INVENTORY: self.OnSellItem(arg1, arg2, arg3))
			questionDialog.SetCancelEvent(ui.__mem_func__(self.OnCloseQuestionDialog))
			questionDialog.Open()
			self.questionDialog = questionDialog

			constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(1)

		else:
			snd.PlaySound("sound/ui/loginfail.wav")

		mouseModule.mouseController.DeattachObject()

	def OnSellItem(self, slotPos, count, itemtype):
		net.SendShopSellPacketNew(slotPos, count, itemtype)
		snd.PlaySound("sound/ui/money.wav")
		self.OnCloseQuestionDialog()

	def OnCloseQuestionDialog(self):
		if not self.questionDialog:
			return
			
		self.questionDialog.Close()
		self.questionDialog = None
		constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(0)

	def SelectEmptySlot(self, selectedSlotPos):
		if self.isOfflineShop:
			self.__OfflineSelectEmptySlot(selectedSlotPos)
			return

		isAttached = mouseModule.mouseController.isAttached()
		if isAttached:
			self.SellAttachedItem()

	def UnselectItemSlot(self, selectedSlotPos):
		if constInfo.GET_ITEM_QUESTION_DIALOG_STATUS() == 1:
			return
		if self.isOfflineShop:
			self.__OfflineUnselectItemSlot(selectedSlotPos)
			return
		if shop.IsPrivateShop():
			self.AskBuyItem(selectedSlotPos)
		else:
			net.SendShopBuyPacket(self.__GetRealIndex(selectedSlotPos))

	def SelectItemSlot(self, selectedSlotPos):
		if constInfo.GET_ITEM_QUESTION_DIALOG_STATUS() == 1:
			return
		if self.isOfflineShop:
			self.__OfflineSelectItemSlot(selectedSlotPos)
			return

		isAttached = mouseModule.mouseController.isAttached()
		selectedSlotPos = self.__GetRealIndex(selectedSlotPos)
		if isAttached:
			self.SellAttachedItem()

		else:

			if True == shop.IsMainPlayerPrivateShop():
				return

			curCursorNum = app.GetCursor()
			if app.BUY == curCursorNum:
				self.AskBuyItem(selectedSlotPos)

			elif app.SELL == curCursorNum:
				chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.SHOP_SELL_INFO)

			else:
				selectedItemID = shop.GetItemID(selectedSlotPos)
				itemCount = shop.GetItemCount(selectedSlotPos)

				type = player.SLOT_TYPE_SHOP
				if shop.IsPrivateShop():
					type = player.SLOT_TYPE_PRIVATE_SHOP

				mouseModule.mouseController.AttachObject(self, type, selectedSlotPos, selectedItemID, itemCount)
				mouseModule.mouseController.SetCallBack("INVENTORY", ui.__mem_func__(self.DropToInventory))
				snd.PlaySound("sound/ui/pick.wav")

	def DropToInventory(self):
		attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
		if self.isOfflineShop:
			self.__OfflineDropToInventory(attachedSlotPos)
			return
		self.AskBuyItem(attachedSlotPos)

	def AskBuyItem(self, slotPos):
		slotPos = self.__GetRealIndex(slotPos)
		
		itemIndex = shop.GetItemID(slotPos)
		itemPrice = shop.GetItemPrice(slotPos)
		itemCount = shop.GetItemCount(slotPos)

		item.SelectItem(itemIndex)
		itemName = item.GetItemName()

		itemBuyQuestionDialog = uiCommon.QuestionDialog()
		itemBuyQuestionDialog.SetText(localeInfo.DO_YOU_BUY_ITEM(itemName, itemCount, localeInfo.NumberToMoneyString(itemPrice)))
		itemBuyQuestionDialog.SetAcceptEvent(lambda arg=True: self.AnswerBuyItem(arg))
		itemBuyQuestionDialog.SetCancelEvent(lambda arg=False: self.AnswerBuyItem(arg))
		itemBuyQuestionDialog.Open()
		itemBuyQuestionDialog.pos = slotPos
		self.itemBuyQuestionDialog = itemBuyQuestionDialog
		
		constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(1)

	def AnswerBuyItem(self, flag):

		if flag:
			pos = self.itemBuyQuestionDialog.pos
			net.SendShopBuyPacket(pos)

		self.itemBuyQuestionDialog.Close()
		self.itemBuyQuestionDialog = None
		
		constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(0)

	def SetItemToolTip(self, tooltipItem):
		self.tooltipItem = tooltipItem

	def OverInItem(self, slotIndex):
		if self.isOfflineShop:
			self.__OfflineOverInItem(slotIndex)
			return
		slotIndex = self.__GetRealIndex(slotIndex)
		## OLD uiShop.py:1131-1140: Shift over a chest shows its contents
		## (NOVA-18).
		constInfo.SET_HOVERED_CHEST(shop.GetItemID(slotIndex))
		if mouseModule.mouseController.isAttached():
			return

		if 0 != self.tooltipItem:
			if shop.SHOP_COIN_TYPE_GOLD == shop.GetTabCoinType(self.tabIdx):
				self.tooltipItem.SetShopItem(slotIndex)
			else: 
				self.tooltipItem.SetShopItemBySecondaryCoin(slotIndex)
	def OverOutItem(self):
		self.hoveredSlot = -1
		constInfo.SET_HOVERED_CHEST(0)
		if 0 != self.tooltipItem:
			self.tooltipItem.HideToolTip()

	def OnUpdate(self):

		USE_SHOP_LIMIT_RANGE = 1000

		(x, y, z) = player.GetMainCharacterPosition()
		if abs(x - self.xShopStart) > USE_SHOP_LIMIT_RANGE or abs(y - self.yShopStart) > USE_SHOP_LIMIT_RANGE:
			self.Close()
			return

		## The owner panel's time, once a second (o-cli bug 23).
		if self.isOfflineShop and self.offlineShopWnd and self.offlineShopWnd.IsShow():
			self.offlineShopWnd.UpdateTime()

	###############################################################################################
	## The offline shop (NOVA-9; OLD uiShop.py:243-479, 923-1100, 1371-1559; spec 3.8). Its rules
	## are offlineshopconst's; this is the view: pages of 10 x 8 cells (the shop module's
	## geometry), the lock overlays, the owner's drops, price, remove, move, withdraw and expand,
	## the buyer's buy, and the owner panel (OfflineShopWindow) under the grid.

	PENDING_COLOR = (0.45, 0.45, 0.45, 1.0)
	NEXT_ROW_COLOR = 0x99003300
	LOCKED_ROW_COLOR = 0xCC000000
	NPC_GEOMETRY = (184, 328, 169, 5)
	GRID_POSITION = (12, 34)
	OFFLINE_WIDTH = 345
	OFFLINE_BUYER_HEIGHT = 328
	OFFLINE_PANEL_Y = 322
	PAGE_BUTTON_Y = 296
	PAGE_BUTTON_WIDTH = 43
	PAGE_BUTTON_GAP = 10

	def OpenOfflineShopView(self, vid, fromNpc):
		"""Shows the offline shop the shop module holds: a visitor's view of the NPC `vid`, or
		its owner's panel (shop.IsOwner()). fromNpc: opened at the NPC, so the owner may
		close the shop there (OLD uiShop.py:1651-1655)."""
		if not self.board:
			return
		import offlineshopconst

		self.isOfflineShop = True
		self.offlineShopVid = vid
		self.offlineFromNpc = bool(fromNpc)
		self.offlineIsOwner = bool(shop.IsOwner())
		shop.Open(True, False)
		self.tabIdx = 0

		self.__HideBuySellButton()
		self.__HideMiddleTabs()
		self.__HideSmallTabs()
		self.btnClose.Hide()
		self.__EnsureOfflineWidgets()
		self.__ArrangeOffline(self.offlineIsOwner)
		self.__SetOfflineTitle(vid)

		(_, _, pageCount, _, _) = offlineshopconst.geometry()
		if self.offlineIsOwner:
			self.itemSlotWindow.SetSlotStyle(wndMgr.SLOT_STYLE_PICK_UP)
			shownPages = pageCount
			self.goldAmount = shop.GetGoldAmount()
			self.offlineShopWnd.Open(self.offlineFromNpc)
			self.offlineShopWnd.SetShopInfo(offlineshopconst.owner_panel())
		else:
			self.itemSlotWindow.SetSlotStyle(wndMgr.SLOT_STYLE_NONE)
			shownPages = max(1, min(pageCount, shop.GetOfflineShopPageCount()))
			self.offlineShopWnd.Close()
			self.offlinePage = 0
		if self.offlinePage >= shownPages:
			self.offlinePage = 0
		self.__ShowPageButtons(shownPages if (self.offlineIsOwner or shownPages > 1) else 0)

		self.Refresh()
		self.SetTop()
		self.Show()
		(self.xShopStart, self.yShopStart, z) = player.GetMainCharacterPosition()

	def OpenOfflineShop(self, open=1):
		"""MANAGE (Interface.OpenOfflineShop): open 1 shows the owner panel from the shop
		module; open 0 refreshes a shown panel only. A panel shown at the NPC stays there."""
		showing = self.IsShow() and self.isOfflineShop and self.offlineIsOwner
		if not open and not showing:
			return
		if showing:
			self.OpenOfflineShopView(self.offlineShopVid, self.offlineFromNpc)
		else:
			self.OpenOfflineShopView(0, False)

	def IsOfflineShopOpen(self):
		return self.IsShow() and self.isOfflineShop

	def GetOfflinePage(self):
		return self.offlinePage

	def SelectOfflinePage(self, page):
		if not self.isOfflineShop:
			return
		self.offlinePage = page
		for (i, button) in enumerate(self.pageButtons):
			if i == page:
				button.Down()
			else:
				button.SetUp()
		self.Refresh()

	def GetOfflineSlot(self, localSlot):
		import offlineshopconst
		return offlineshopconst.global_slot(self.offlinePage, localSlot)

	def GetSelectedItemVnum(self):
		"""The hovered item, page-aware (o-cli bug 5): the offline getter on every page."""
		if self.hoveredSlot < 0:
			return 0
		if self.isOfflineShop:
			return shop.GetOfflineShopItemID(self.hoveredSlot)
		return shop.GetItemID(self.hoveredSlot)

	def RefreshOfflineShop(self):
		import offlineshopconst
		(_, _, _, perPage, _) = offlineshopconst.geometry()
		for localSlot in range(perPage):
			slot = self.GetOfflineSlot(localSlot)
			vnum = shop.GetOfflineShopItemID(slot)
			count = shop.GetOfflineShopItemCount(slot)
			if count <= 1:
				count = 0
			if vnum and self.offlineIsOwner and offlineshopconst.is_slot_pending(slot):
				self.itemSlotWindow.SetItemSlot(localSlot, vnum, count, self.PENDING_COLOR)
			else:
				self.itemSlotWindow.SetItemSlot(localSlot, vnum, count)
		self.itemSlotWindow.RefreshSlot()
		self.__UpdateLockOverlays()

	def IsOfflineSlotInert(self, slot):
		"""A slot held for a transfer takes no action (spec 3.8)."""
		import offlineshopconst
		return self.offlineIsOwner and offlineshopconst.is_slot_pending(slot)

	## The callbacks (Interface: UpdateShopLock, UpdateShopTime, UpdateShopSign, UpdateShopGold).
	def UpdateLock(self, locked):
		if self.offlineShopWnd:
			self.offlineShopWnd.UpdateLock(locked)

	def UpdateTime(self, secondsLeft):
		if self.offlineShopWnd:
			self.offlineShopWnd.SetTime(secondsLeft)

	def UpdateSign(self, sign):
		if self.offlineShopWnd:
			self.offlineShopWnd.UpdateSign(sign)

	def UpdateGold(self, gold):
		self.goldAmount = gold
		if self.offlineShopWnd:
			self.offlineShopWnd.UpdateGold(gold)

	def OnOfflineShopResult(self, op, code, arg):
		"""GC RESULT of an operation: its OFFLINE_SHOP_RESULT_<NAME> text with `arg`; a lost
		transfer (TRANSFER_LOST) also in a dialog, with its delivery id for support. A refused
		LOGS goes to the log window first, which asks again quietly after a RATE_LIMITED."""
		import offlineshopconst
		if offlineshopconst.op_name(op) == "LOGS":
			logWindow = getattr(self.interface, "wndOfflineShopLog", None) if self.interface else None
			onLogsResult = getattr(logWindow, "OnLogsResult", None)
			if onLogsResult and onLogsResult(code):
				return
		text = offlineshopconst.result_text(code, arg)
		if not text:
			return
		chat.AppendChat(chat.CHAT_TYPE_INFO, text)
		if offlineshopconst.result_name(code) == "TRANSFER_LOST":
			popup = uiCommon.PopupDialog()
			popup.SetText(text)
			popup.Open()
			self.resultPopup = popup

	## Withdrawing the held yang (OLD uiShop.py:1378-1388).
	def OpenPickMoneyDialog(self):
		if self.goldAmount < 1:
			import uiScriptLocale
			chat.AppendChat(chat.CHAT_TYPE_INFO, uiScriptLocale.OFFLINE_SHOP_NO_YANG)
			return
		if not self.dlgPickMoney:
			return
		self.dlgPickMoney.SetTitleName(localeInfo.PICK_MONEY_TITLE)
		self.dlgPickMoney.Open(self.goldAmount)

	def OnPickMoney(self, gold):
		net.SendShopWithdrawGoldPacket(gold)

	def OpenShopLog(self):
		if self.interface:
			self.interface.OpenOfflineShopLog()

	def __EnsureOfflineWidgets(self):
		if not self.offlineShopWnd:
			self.offlineShopWnd = OfflineShopWindow(self)
		if not self.dlgPickMoney:
			import uiPickMoney
			import offlineshopconst
			dialog = uiPickMoney.PickMoneyDialog()
			dialog.LoadDialog()
			dialog.SetMax(offlineshopconst.WITHDRAW_DIGITS)
			dialog.SetAcceptEvent(ui.__mem_func__(self.OnPickMoney))
			dialog.Hide()
			self.dlgPickMoney = dialog

	def __ArrangeOffline(self, isOwner):
		import offlineshopconst
		(cols, rows, _, _, _) = offlineshopconst.geometry()
		height = self.OFFLINE_PANEL_Y + OfflineShopWindow.HEIGHT if isOwner else self.OFFLINE_BUYER_HEIGHT
		self.SetSize(self.OFFLINE_WIDTH, height)
		self.board.SetSize(self.OFFLINE_WIDTH, height)
		self.titleBar.SetWidth(self.OFFLINE_WIDTH - 15)
		self.itemSlotWindow.ArrangeSlot(0, cols, rows, 32, 32, 0, 0)
		self.itemSlotWindow.SetSlotBaseImage("d:/ymir work/ui/public/Slot_Base.sub", 1.0, 1.0, 1.0, 1.0)
		self.offlineShopWnd.SetPosition(0, self.OFFLINE_PANEL_Y)
		self.offlineLayout = True

	def __LeaveOfflineMode(self):
		"""Back to NEW's NPC shop layout after an offline view (the last open was offline)."""
		if not self.offlineLayout:
			return
		self.offlineLayout = False
		(width, height, titleWidth, cols) = self.NPC_GEOMETRY
		self.__HideOfflineWidgets()
		self.SetSize(width, height)
		self.board.SetSize(width, height)
		self.titleBar.SetWidth(titleWidth)
		self.itemSlotWindow.ArrangeSlot(0, cols, shop.SHOP_SLOT_COUNT // cols, 32, 32, 0, 0)
		self.itemSlotWindow.SetSlotBaseImage("d:/ymir work/ui/public/Slot_Base.sub", 1.0, 1.0, 1.0, 1.0)
		self.itemSlotWindow.SetSlotStyle(wndMgr.SLOT_STYLE_NONE)
		if self.titleName:
			import uiScriptLocale
			self.titleName.SetText(uiScriptLocale.SHOP_TITLE)

	def __HideOfflineWidgets(self):
		for button in self.pageButtons:
			button.Hide()
		for bar in self.lockOverlays:
			bar.Hide()
		if self.offlineShopWnd:
			self.offlineShopWnd.Close()

	def __EndOfflineSession(self):
		"""The offline view or panel ends: its dialogs close and LEAVE goes, once."""
		self.__CloseOfflineDialogs()
		net.SendOfflineShopLeavePacket()
		self.isOfflineShop = False
		self.offlineIsOwner = False
		self.offlineFromNpc = False
		self.offlineShopVid = 0

	def __CloseOfflineDialogs(self):
		if self.dlgPickMoney:
			self.dlgPickMoney.Close()
		if self.offlineShopWnd:
			self.offlineShopWnd.Close()
		self.__CancelExpandRow()
		if self.priceInputBoard:
			self.priceInputBoard.Close()
			self.priceInputBoard = None
		self.hoveredSlot = -1

	def __SetOfflineTitle(self, vid):
		"""The shop's sign from its board (OLD uiShop.py:586-601), which turns "seen"."""
		import uiScriptLocale
		import offlineshopconst
		title = ""
		boards = getattr(self.interface, "privateShopAdvertisementBoardDict", {}) if self.interface else {}
		board = boards.get(vid) if vid else None
		if board:
			title = getattr(board, "title", "")
			markSeen = getattr(board, "MarkSeen", None)
			if markSeen:
				markSeen()
		if not title and self.offlineIsOwner:
			title = offlineshopconst.owner_panel()["sign"]
		self.titleName.SetText(offlineshopconst.cut(title, offlineshopconst.SHOP_TITLE_MAX) if title else uiScriptLocale.SHOP_TITLE)

	def __ShowPageButtons(self, count):
		import uiScriptLocale
		width = count * self.PAGE_BUTTON_WIDTH + max(0, count - 1) * self.PAGE_BUTTON_GAP
		startX = (self.OFFLINE_WIDTH - width) // 2
		for (i, button) in enumerate(self.pageButtons):
			if i < count:
				try:
					button.SetText(uiScriptLocale.OFFLINE_SHOP_PAGE_BUTTON % (i + 1))
				except TypeError:
					button.SetText(str(i + 1))
				button.SetPosition(startX + i * (self.PAGE_BUTTON_WIDTH + self.PAGE_BUTTON_GAP), self.PAGE_BUTTON_Y)
				if i == self.offlinePage:
					button.Down()
				else:
					button.SetUp()
				button.Show()
			else:
				button.Hide()

	## The lock overlays (OLD uiShop.py:413-479): rows past the unlocked slots; the first one
	## is green and asks for a kit, the others are dark. offlineshopconst.lock_rows has the math.
	def __UpdateLockOverlays(self):
		import offlineshopconst
		(cols, rows, _, _, _) = offlineshopconst.geometry()
		if not self.board:
			return
		while len(self.lockOverlays) < rows:
			bar = ui.Bar()
			bar.SetParent(self.board)
			bar.SetSize(cols * 32, 32)
			bar.Hide()
			self.lockOverlays.append(bar)
		unlocked = shop.GetOfflineShopSlotCount()
		expandable = self.offlineIsOwner and offlineshopconst.can_expand(shop.GetOfflineShopExpandCount())
		locked = offlineshopconst.lock_rows(self.offlinePage, unlocked, expandable)
		(gridX, gridY) = self.GRID_POSITION
		for (row, bar) in enumerate(self.lockOverlays):
			state = locked.get(row)
			if not state:
				bar.Hide()
				continue
			bar.SetPosition(gridX, gridY + row * 32)
			if state == "next":
				bar.SetColor(self.NEXT_ROW_COLOR)
				bar.SetOnMouseLeftButtonUpEvent(ui.__mem_func__(self.OnClickLockOverlay))
				bar.OnMouseOverIn = ui.__mem_func__(self.__ShowKitToolTip)
				bar.OnMouseOverOut = ui.__mem_func__(self.OverOutItem)
			else:
				bar.SetColor(self.LOCKED_ROW_COLOR)
				bar.SetOnMouseLeftButtonUpEvent(None)
				bar.OnMouseOverIn = None
				bar.OnMouseOverOut = None
			bar.Show()

	def GetLockOverlayStates(self):
		"""{row: "next" | "locked"} of the overlays shown on this page."""
		import offlineshopconst
		unlocked = shop.GetOfflineShopSlotCount()
		expandable = self.offlineIsOwner and offlineshopconst.can_expand(shop.GetOfflineShopExpandCount())
		return offlineshopconst.lock_rows(self.offlinePage, unlocked, expandable)

	def __ShowKitToolTip(self):
		import offlineshopconst
		if 0 != self.tooltipItem:
			self.tooltipItem.SetItemToolTip(offlineshopconst.config()["kit_vnum"])

	def OnClickLockOverlay(self):
		"""The next row: a kit expands the shop (OLD uiShop.py:333-364), after a question."""
		import offlineshopconst
		import uiScriptLocale
		if not self.offlineIsOwner:
			return
		kitVnum = offlineshopconst.config()["kit_vnum"]
		if player.GetItemCountByVnum(kitVnum) < 1:
			popup = uiCommon.PopupDialog()
			popup.SetText(uiScriptLocale.OFFLINE_SHOP_EXPAND_NO_ITEM)
			popup.Open()
			self.popup = popup
			return
		item.SelectItem(kitVnum)
		questionDialog = uiCommon.QuestionDialog()
		try:
			questionDialog.SetText(uiScriptLocale.OFFLINE_SHOP_EXPAND_ROW_CONFIRM % item.GetItemName())
		except TypeError:
			questionDialog.SetText(uiScriptLocale.OFFLINE_SHOP_EXPAND_ROW_CONFIRM)
		questionDialog.SetAcceptEvent(ui.__mem_func__(self.__AcceptExpandRow))
		questionDialog.SetCancelEvent(ui.__mem_func__(self.__CancelExpandRow))
		questionDialog.Open()
		self.expandQuestionDialog = questionDialog
		constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(1)

	def __AcceptExpandRow(self):
		net.SendShopExpandPacket()
		self.__CancelExpandRow()

	def __CancelExpandRow(self):
		if self.expandQuestionDialog:
			self.expandQuestionDialog.Close()
			self.expandQuestionDialog = None
			constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(0)

	## The grid's events in an offline shop.
	def __OfflineOverInItem(self, localSlot):
		import offlineshopconst
		slot = self.GetOfflineSlot(localSlot)
		self.hoveredSlot = slot
		if mouseModule.mouseController.isAttached() or 0 == self.tooltipItem:
			return
		if self.IsOfflineSlotInert(slot):
			self.tooltipItem.ClearToolTip()
			self.tooltipItem.AppendTextLine(localeInfo.OFFLINE_SHOP_SLOT_PENDING)
			self.tooltipItem.ShowToolTip()
			return
		## Y1's uiToolTip.ItemToolTip.SetOfflineShopItem (o-cli bug 2): the view's or the panel's
		## item, with the owner's key hints.
		setOfflineShopItem = getattr(self.tooltipItem, "SetOfflineShopItem", None)
		if setOfflineShopItem:
			setOfflineShopItem(slot)
		else:
			self.tooltipItem.HideToolTip()

	def __OfflineSelectEmptySlot(self, localSlot):
		if not mouseModule.mouseController.isAttached():
			return
		if not self.offlineIsOwner:
			mouseModule.mouseController.DeattachObject()
			return

		attachedSlotType = mouseModule.mouseController.GetAttachedType()
		attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
		mouseModule.mouseController.DeattachObject()
		targetSlot = self.GetOfflineSlot(localSlot)

		## A listed item dropped on another cell moves (OLD uiShop.py:928-934).
		if attachedSlotType == player.SLOT_TYPE_PRIVATE_SHOP:
			if not self.IsOfflineSlotInert(attachedSlotPos):
				net.SendShopMoveItemPacket(attachedSlotPos, targetSlot)
			return

		if attachedSlotType not in (player.SLOT_TYPE_INVENTORY, player.SLOT_TYPE_DRAGON_SOUL_INVENTORY, player.SLOT_TYPE_EXTRA_INVENTORY):
			return

		attachedInvenType = player.SlotTypeToInvenType(attachedSlotType)
		itemVNum = player.GetItemIndex(attachedInvenType, attachedSlotPos)
		item.SelectItem(itemVNum)
		if item.IsAntiFlag(item.ANTIFLAG_GIVE) or item.IsAntiFlag(item.ANTIFLAG_MYSHOP):
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.PRIVATE_SHOP_CANNOT_SELL_ITEM)
			return

		## The price, with the "bulk add" box and the remembered price (OLD uiShop.py:952-975).
		import itemPrices
		priceInputBoard = uiCommon.BulkMoneyInputDialog()
		priceInputBoard.SetTitle(localeInfo.PRIVATE_SHOP_INPUT_PRICE_DIALOG_TITLE)
		priceInputBoard.SetAcceptEvent(ui.__mem_func__(self.AcceptInputPrice))
		priceInputBoard.SetCancelEvent(ui.__mem_func__(self.CancelInputPrice))
		priceInputBoard.Open()
		priceInputBoard.SetBulkMode()
		if itemPrices.get_price(itemVNum) > 0:
			priceInputBoard.SetValue(itemPrices.get_price(itemVNum))
		priceInputBoard.itemVNum = itemVNum
		priceInputBoard.sourceWindowType = attachedInvenType
		priceInputBoard.sourceSlotPos = attachedSlotPos
		priceInputBoard.targetSlotPos = targetSlot
		self.priceInputBoard = priceInputBoard

	def AcceptInputPrice(self):
		import itemPrices
		import uiPickMoney
		board = self.priceInputBoard
		if not board:
			return True
		price = uiPickMoney.ConvertTextToMoney(board.GetText())
		if price <= 0:
			return True
		net.SendShopAddItemPacket(board.sourceWindowType, board.sourceSlotPos, board.targetSlotPos, price, board.IsBulkMode())
		itemPrices.set_price(board.itemVNum, price)
		board.Close()
		self.priceInputBoard = None
		return True

	def CancelInputPrice(self):
		if self.priceInputBoard:
			self.priceInputBoard.Close()
		self.priceInputBoard = None
		return True

	def __OfflineUnselectItemSlot(self, localSlot):
		"""A right press (OLD uiShop.py:977-989): the owner withdraws the item, or with Alt
		changes its price, with Ctrl removes it; a visitor buys it. One item at a time for a
		player's shop: no count dialog (o-cli bug 6)."""
		slot = self.GetOfflineSlot(localSlot)
		if not shop.GetOfflineShopItemID(slot):
			return
		if self.offlineIsOwner:
			if self.IsOfflineSlotInert(slot):
				return
			if app.IsPressed(app.DIK_LALT):
				self.OpenChangePriceDialog(slot)
			elif app.IsPressed(app.DIK_LCONTROL):
				self.OpenRemoveItemDialog(slot)
			else:
				net.SendShopWithdrawItemPacket(slot)
			return
		self.AskBuyOfflineItem(slot)

	def __OfflineSelectItemSlot(self, localSlot):
		slot = self.GetOfflineSlot(localSlot)
		if mouseModule.mouseController.isAttached():
			attachedSlotType = mouseModule.mouseController.GetAttachedType()
			attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
			mouseModule.mouseController.DeattachObject()
			if self.offlineIsOwner and attachedSlotType == player.SLOT_TYPE_PRIVATE_SHOP:
				if not self.IsOfflineSlotInert(attachedSlotPos) and not self.IsOfflineSlotInert(slot):
					net.SendShopMoveItemPacket(attachedSlotPos, slot)
			return

		if self.IsOfflineSlotInert(slot):
			return
		vnum = shop.GetOfflineShopItemID(slot)
		if not vnum:
			return
		mouseModule.mouseController.AttachObject(self, player.SLOT_TYPE_PRIVATE_SHOP, slot, vnum, shop.GetOfflineShopItemCount(slot))
		mouseModule.mouseController.SetCallBack("INVENTORY", ui.__mem_func__(self.DropToInventory))
		snd.PlaySound("sound/ui/pick.wav")

	def __OfflineDropToInventory(self, slot):
		"""A shop item dropped on the inventory: the owner takes it back, a visitor buys it."""
		if self.offlineIsOwner:
			if not self.IsOfflineSlotInert(slot):
				net.SendShopWithdrawItemPacket(slot)
			return
		self.AskBuyOfflineItem(slot)

	def AskBuyOfflineItem(self, slot):
		"""BUY with the expected item id and price (spec 1.1 sub 15); a question only from
		BUY_CONFIRM_MIN_PRICE on (OLD uiShop.py:1095-1099)."""
		import offlineshopconst
		vnum = shop.GetOfflineShopItemID(slot)
		if not vnum:
			return
		price = shop.GetOfflineShopItemPrice(slot)
		if not offlineshopconst.needs_buy_confirm(price):
			self.__SendOfflineBuy(slot)
			return

		item.SelectItem(vnum)
		itemBuyQuestionDialog = uiCommon.QuestionDialog()
		itemBuyQuestionDialog.SetText(localeInfo.DO_YOU_BUY_ITEM(item.GetItemName(), shop.GetOfflineShopItemCount(slot), localeInfo.NumberToMoneyString(price)))
		itemBuyQuestionDialog.SetAcceptEvent(lambda arg=True: self.AnswerOfflineBuyItem(arg))
		itemBuyQuestionDialog.SetCancelEvent(lambda arg=False: self.AnswerOfflineBuyItem(arg))
		itemBuyQuestionDialog.Open()
		itemBuyQuestionDialog.pos = slot
		self.itemBuyQuestionDialog = itemBuyQuestionDialog
		constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(1)

	def AnswerOfflineBuyItem(self, flag):
		if not self.itemBuyQuestionDialog:
			return
		if flag:
			self.__SendOfflineBuy(self.itemBuyQuestionDialog.pos)
		self.itemBuyQuestionDialog.Close()
		self.itemBuyQuestionDialog = None
		constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(0)

	def __SendOfflineBuy(self, slot):
		import offlineshopconst
		net.SendOfflineShopBuyPacket(self.offlineShopVid, slot, offlineshopconst.slot_item_id(slot), shop.GetOfflineShopItemPrice(slot))

	## Price and remove (OLD uiShop.py:1442-1559): both need the shop locked.
	def OpenChangePriceDialog(self, slot):
		import uiScriptLocale
		import itemPrices
		if not (self.offlineShopWnd and self.offlineShopWnd.isLocked):
			chat.AppendChat(chat.CHAT_TYPE_INFO, uiScriptLocale.OFFLINE_SHOP_CHANGE_PRICE_LOCKED)
			return
		vnum = shop.GetOfflineShopItemID(slot)
		if not vnum:
			return
		priceInputBoard = uiCommon.BulkMoneyInputDialog()
		priceInputBoard.SetTitle(uiScriptLocale.OFFLINE_SHOP_CHANGE_PRICE_TITLE)
		priceInputBoard.SetAcceptEvent(ui.__mem_func__(self.AcceptChangePrice))
		priceInputBoard.SetCancelEvent(ui.__mem_func__(self.CancelInputPrice))
		priceInputBoard.Open()
		priceInputBoard.SetBulkMode(uiScriptLocale.OFFLINE_SHOP_CHANGE_PRICE_ALL)
		currentPrice = shop.GetOfflineShopItemPrice(slot)
		if currentPrice > 0:
			priceInputBoard.SetValue(currentPrice)
		priceInputBoard.displayPos = slot
		priceInputBoard.itemVNum = vnum
		self.priceInputBoard = priceInputBoard

	def AcceptChangePrice(self):
		import itemPrices
		import uiPickMoney
		board = self.priceInputBoard
		if not board:
			return True
		price = uiPickMoney.ConvertTextToMoney(board.GetText())
		if price <= 0:
			return True
		net.SendShopUpdatePricePacket(board.displayPos, price, board.IsBulkMode())
		itemPrices.set_price(board.itemVNum, price)
		board.Close()
		self.priceInputBoard = None
		return True

	def OpenRemoveItemDialog(self, slot):
		import uiScriptLocale
		if not (self.offlineShopWnd and self.offlineShopWnd.isLocked):
			chat.AppendChat(chat.CHAT_TYPE_INFO, uiScriptLocale.OFFLINE_SHOP_REMOVE_ITEM_LOCKED)
			return
		vnum = shop.GetOfflineShopItemID(slot)
		if not vnum:
			return
		item.SelectItem(vnum)
		questionDialog = uiCommon.CheckQuestionDialog()
		try:
			questionDialog.SetText(uiScriptLocale.OFFLINE_SHOP_REMOVE_ITEM_CONFIRM % item.GetItemName())
		except TypeError:
			questionDialog.SetText(uiScriptLocale.OFFLINE_SHOP_REMOVE_ITEM_CONFIRM)
		questionDialog.SetCheckBox(uiScriptLocale.OFFLINE_SHOP_REMOVE_ITEM_ALL, True)
		questionDialog.SetAcceptEvent(ui.__mem_func__(self.AcceptRemoveItem))
		questionDialog.SetCancelEvent(ui.__mem_func__(self.OnCloseQuestionDialog))
		questionDialog.Open()
		questionDialog.displayPos = slot
		self.questionDialog = questionDialog
		constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(1)

	def AcceptRemoveItem(self):
		if not self.questionDialog:
			return
		net.SendShopRemoveItemPacket(self.questionDialog.displayPos, self.questionDialog.IsChecked())
		self.OnCloseQuestionDialog()

###################################################################################################
## The owner panel (NOVA-9; OLD uiShop.py:1561-1776): sign and rename, location and warp, close at
## the shop, held yang and withdraw, time left, extend, lock and renew, logs. A child of the shop
## window, under its grid (uiscript offlineshop.py).

class OfflineShopWindow(ui.ScriptWindow):

	HEIGHT = 150

	def __init__(self, parent):
		ui.ScriptWindow.__init__(self)
		from _weakref import proxy
		self.parent = proxy(parent)
		self.isLocked = False
		self.expireTime = 0.0
		self.lastTimeSecond = -1
		self.sign = ""
		self.questionDialog = None
		self.signInputBoard = None
		self.dlgAddDays = None
		self.LoadWindow()
		self.SetParent(parent)

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def LoadWindow(self):
		try:
			PythonScriptLoader = ui.PythonScriptLoader()
			PythonScriptLoader.LoadScriptFile(self, "UIScript/offlineshop.py")
		except:
			import exception
			exception.Abort("OfflineShopWindow.LoadWindow.LoadObject")

		try:
			GetObject = self.GetChild
			self.signText = GetObject("ShopSignText")
			self.renameButton = GetObject("RenameButton")
			self.posInfoText = GetObject("PosInfoText")
			self.teleportButton = GetObject("TeleportButton")
			self.goldText = GetObject("GoldText")
			self.withdrawButton = GetObject("WithdrawButton")
			self.timeLeftText = GetObject("TimeLeftText")
			self.addTimeButton = GetObject("AddTimeButton")
			self.lockButton = GetObject("LockButton")
			self.viewLogButton = GetObject("ViewLogButton")
			self.closeButton = GetObject("CloseButton")
		except:
			import exception
			exception.Abort("OfflineShopWindow.LoadWindow.BindObject")

		self.renameButton.SetEvent(ui.__mem_func__(self.OnPressChange))
		self.teleportButton.SetEvent(ui.__mem_func__(self.WarpToShop))
		self.withdrawButton.SetEvent(ui.__mem_func__(self.OnPressWithdraw))
		self.addTimeButton.SetEvent(ui.__mem_func__(self.ShopAddTime))
		self.lockButton.SetEvent(ui.__mem_func__(self.SetLock))
		self.viewLogButton.SetEvent(ui.__mem_func__(self.OpenShopLogs))
		self.closeButton.SetEvent(ui.__mem_func__(self.CloseShop))

	def Destroy(self):
		self.OnCloseQuestionDialog()
		if self.signInputBoard:
			self.signInputBoard.Close()
		if self.dlgAddDays:
			self.dlgAddDays.Destroy()
		self.signInputBoard = None
		self.dlgAddDays = None
		self.ClearDictionary()

	def Open(self, fromNpc):
		"""The close button only at the shop (OLD uiShop.py:1651-1655)."""
		if fromNpc:
			self.closeButton.Show()
		else:
			self.closeButton.Hide()
		self.UpdateLock(shop.IsLocked())
		self.Show()

	def Close(self):
		self.OnCloseQuestionDialog()
		if self.signInputBoard:
			self.signInputBoard.Close()
			self.signInputBoard = None
		if self.dlgAddDays:
			self.dlgAddDays.Close()
		self.Hide()

	def SetShopInfo(self, info):
		"""MANAGE's panel (offlineshopconst.owner_panel()): sign, place, time, gold, lock."""
		import uiScriptLocale
		self.UpdateSign(info["sign"])
		self.SetTime(info["seconds_left"])
		self.UpdateGold(info["gold"])
		self.UpdateLock(info["locked"])
		import background
		(mapName, xBase, yBase) = background.GlobalPositionToMapInfo(info["x"], info["y"])
		zoneName = localeInfo.MINIMAP_ZONE_NAME_DICT.get(mapName, mapName)
		self.posInfoText.SetText("%s CH%d, %s (%d, %d)" % (uiScriptLocale.OFFLINE_SHOP_LOCATION, info["channel"], zoneName, (info["x"] - xBase) // 100, (info["y"] - yBase) // 100))

	def IsExpired(self):
		return self.expireTime <= app.GetTime()

	def GetSecondsLeft(self):
		return max(0, int(self.expireTime - app.GetTime()))

	def SetTime(self, secondsLeft):
		self.expireTime = app.GetTime() + max(0, secondsLeft)
		self.lastTimeSecond = -1
		self.UpdateTime()
		self.__RefreshLockText()

	def UpdateTime(self):
		"""The time text, at most once a second (o-cli bug 23)."""
		import offlineshopconst
		secondsLeft = self.GetSecondsLeft()
		if secondsLeft == self.lastTimeSecond:
			return
		expired = secondsLeft <= 0
		self.lastTimeSecond = secondsLeft
		self.timeLeftText.SetText(offlineshopconst.time_left_text(secondsLeft))
		if expired:
			self.__RefreshLockText()

	def UpdateLock(self, locked):
		self.isLocked = bool(locked)
		self.__RefreshLockText()

	def __RefreshLockText(self):
		"""Unlock, Lock, or Renew for a locked shop whose time ran out (OLD uiShop.py:1700-1715)."""
		import uiScriptLocale
		if self.isLocked and self.IsExpired():
			self.lockButton.SetText(uiScriptLocale.OFFLINE_SHOP_BUTTON_RENEW)
		elif self.isLocked:
			self.lockButton.SetText(uiScriptLocale.OFFLINE_SHOP_BUTTON_UNLOCK)
		else:
			self.lockButton.SetText(uiScriptLocale.OFFLINE_SHOP_BUTTON_LOCK)

	def UpdateSign(self, sign):
		import offlineshopconst
		self.sign = sign or ""
		self.signText.SetText(offlineshopconst.cut(self.sign, offlineshopconst.PANEL_SIGN_MAX))

	def UpdateGold(self, gold):
		self.goldText.SetText(localeInfo.NumberToMoneyString(gold))

	def SetLock(self):
		"""Unlocking a shop whose time ran out renews it: a question with CONFIG's renew cost
		first (o-cli bug 4). Locking, or unlocking in time, charges nothing."""
		import offlineshopconst
		if self.isLocked and self.IsExpired():
			questionDialog = uiCommon.QuestionDialog()
			questionDialog.SetText(offlineshopconst.renew_confirm_text())
			questionDialog.SetAcceptEvent(ui.__mem_func__(self.AcceptRenew))
			questionDialog.SetCancelEvent(ui.__mem_func__(self.OnCloseQuestionDialog))
			questionDialog.Open()
			self.questionDialog = questionDialog
			constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(1)
			return
		net.SendShopLockPacket(not self.isLocked)

	def AcceptRenew(self):
		net.SendShopLockPacket(False)
		self.OnCloseQuestionDialog()

	def OnCloseQuestionDialog(self):
		if not self.questionDialog:
			return
		self.questionDialog.Close()
		self.questionDialog = None
		constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(0)

	def CloseShop(self):
		net.SendCloseShopPacket()

	def WarpToShop(self):
		net.SendWarpToShopPacket()

	def OpenShopLogs(self):
		self.parent.OpenShopLog()

	def OnPressWithdraw(self):
		self.parent.OpenPickMoneyDialog()

	def ShopAddTime(self):
		"""EXTEND: 1 to the days the cap leaves (spec 3.4.5), CONFIG's price a day in the
		dialog's title, then the days times that price in a question (spec 3.8; OLD
		uiShop.py:1745-1757 showed no price)."""
		import offlineshopconst
		import uiScriptLocale
		cfg = offlineshopconst.config()
		maxDays = offlineshopconst.extend_days_max(self.GetSecondsLeft(), cfg)
		if maxDays < 1:
			try:
				chat.AppendChat(chat.CHAT_TYPE_INFO, uiScriptLocale.OFFLINE_SHOP_TIME_EXCEED % cfg["extend_cap_days"])
			except TypeError:
				chat.AppendChat(chat.CHAT_TYPE_INFO, uiScriptLocale.OFFLINE_SHOP_TIME_EXCEED)
			return
		if not self.dlgAddDays:
			import uiPickMoney
			dialog = uiPickMoney.PickMoneyDialog()
			dialog.LoadDialog()
			dialog.SetMax(offlineshopconst.DAYS_DIGITS)
			dialog.SetAcceptEvent(ui.__mem_func__(self.OnPickDays))
			self.dlgAddDays = dialog
		self.dlgAddDays.SetTitleName("%s / %s" % (localeInfo.NumberToMoneyString(cfg["extend_price_per_day"]), localeInfo.DAY))
		self.dlgAddDays.Open(maxDays)

	def OnPickDays(self, days):
		"""The picked days and their cost (CONFIG's price a day); EXTEND goes on Yes."""
		import offlineshopconst
		import uiScriptLocale
		days = min(int(days), offlineshopconst.extend_days_max(self.GetSecondsLeft()))
		if days < 1:
			return
		self.OnCloseQuestionDialog()
		questionDialog = uiCommon.QuestionDialog()
		questionDialog.SetText("%s: %d %s, %s" % (uiScriptLocale.OFFLINE_SHOP_BUTTON_ADD_TIME, days, localeInfo.DAY,
		                                          localeInfo.NumberToMoneyString(offlineshopconst.extend_cost(days))))
		questionDialog.SetAcceptEvent(lambda arg=days: self.AcceptExtend(arg))
		questionDialog.SetCancelEvent(ui.__mem_func__(self.OnCloseQuestionDialog))
		questionDialog.Open()
		self.questionDialog = questionDialog
		constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(1)

	def AcceptExtend(self, days):
		net.SendShopExtendTimePacket(days)
		self.OnCloseQuestionDialog()

	def OnPressChange(self):
		import offlineshopconst
		import uiScriptLocale
		signInputBoard = uiCommon.InputDialogWithDescription()
		signInputBoard.SetTitle(uiScriptLocale.OFFLINE_SHOP_INPUT_SIGN_TITLE)
		signInputBoard.SetMaxLength(offlineshopconst.SIGN_RENAME_MAX)
		try:
			signInputBoard.SetDescription(uiScriptLocale.OFFLINE_SHOP_INPUT_SIGN_DESC % self.sign)
		except TypeError:
			signInputBoard.SetDescription(self.sign)
		signInputBoard.SetAcceptEvent(ui.__mem_func__(self.ChangeSign))
		signInputBoard.SetCancelEvent(ui.__mem_func__(self.CloseSignBoard))
		signInputBoard.Open()
		self.signInputBoard = signInputBoard

	def ChangeSign(self):
		if self.signInputBoard:
			text = self.signInputBoard.GetText()
			if text:
				net.SendShopChangeSignPacket(text)
		self.CloseSignBoard()
		return True

	def CloseSignBoard(self):
		if self.signInputBoard:
			self.signInputBoard.Close()
		self.signInputBoard = None
		return True
