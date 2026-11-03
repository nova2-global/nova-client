import ui
import uiCommon
import player
import item
import net
import app
import chat
import wndMgr
import mouseModule
import localeInfo

## The gaya market (NOVA-10): OLD's uiGemShop.py (live through
## interfaceModule.py:112-114, 404-405, with its default layout
## uiscript/newgemshopwindow.py), on NEW's data. The server owns the nine
## slots, the costs and the refresh time (gaya.txt, spec 5.4); this window
## shows them from the player module (C's GetGemShop* getters), asks before
## every action and checks what it can locally first, as OLD did.
## Not ported from OLD: the literal unlock costs and item vnums (the player
## module's now), and the countdown that went below zero (GB13).

class GemShopWindow(ui.ScriptWindow):

	## OLD uiGemShop.py:18, 93-96: the window closes, and tells the server,
	## once the player walks this far from where it opened (spec 5.6).
	GEM_SHOP_WINDOW_LIMIT_RANGE = 500
	## OLD's status 1 (uiGemShop.py:118): a slot that needs unlocking.
	SLOT_STATUS_LOCKED = 1

	def __init__(self):
		ui.ScriptWindow.__init__(self)

		self.tooltipItem = None
		self.xGemShopStart = 0
		self.yGemShopStart = 0
		self.questionDialog = None
		## app.GetGlobalTime() (ms) when the server re-rolls the market.
		self.refreshEndTime = 0
		self.refreshText = None
		self.priceList = []

		self.__LoadWindow()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/gemshopwindow.py")
		except:
			import exception
			exception.Abort("GemShopWindow.__LoadWindow.LoadObject")

		try:
			self.titleBar = self.GetChild("TitleBar")
			self.itemSlot = self.GetChild("SellItemSlot")
			self.refreshTime = self.GetChild("BuyRefreshTime")
			self.refreshButton = self.GetChild("RefreshButton")
			self.priceList = [self.GetChild("slot_%d_price" % (i + 1)) for i in range(self.GetSlotCount())]
		except:
			import exception
			exception.Abort("GemShopWindow.__LoadWindow.BindObject")

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.CloseShop))
		self.refreshButton.SetEvent(ui.__mem_func__(self.SendRequestRefresh))

		self.itemSlot.SetSlotStyle(wndMgr.SLOT_STYLE_NONE)
		self.itemSlot.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		self.itemSlot.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		self.itemSlot.SetSelectItemSlotEvent(ui.__mem_func__(self.UseItemSlot))

	@staticmethod
	def GetSlotCount():
		return player.GAYA_MARKET_SLOT_COUNT

	def Destroy(self):
		self.SlotAddQuestionCancel()
		self.ClearDictionary()
		self.tooltipItem = None
		self.titleBar = None
		self.itemSlot = None
		self.refreshTime = None
		self.refreshButton = None
		self.priceList = []

	def SetItemToolTip(self, tooltip):
		self.tooltipItem = tooltip

	## The server opened the market (game.OpenGemShop).
	def Open(self):
		self.RefreshItemSlot()
		self.__StartRefreshClock()
		self.SetCenterPosition()
		self.SetTop()
		self.Show()

		(self.xGemShopStart, self.yGemShopStart, z) = player.GetMainCharacterPosition()

	## The server closed it (game.CloseGemShop): nothing to tell it.
	def Close(self):
		self.SlotAddQuestionCancel()
		self.OverOutItem()
		self.Hide()

	## The player closes it: the server ends the market session (CLOSE).
	def CloseShop(self):
		net.SendGemShopClose()
		self.Close()

	def OnPressEscapeKey(self):
		self.CloseShop()
		return True

	## The slots changed (game.RefreshGemShop: a buy, an unlock, a re-roll).
	def RefreshGemShop(self):
		self.__StartRefreshClock()
		self.RefreshItemSlot()

	## GetGemShopRefreshTime() is the seconds left when the frame came (OLD
	## uiGemShop.py:79, 128): the clock runs locally from here.
	def __StartRefreshClock(self):
		self.refreshEndTime = app.GetGlobalTime() + max(0, player.GetGemShopRefreshTime()) * 1000
		self.refreshText = None
		self.__UpdateRefreshTime()

	@staticmethod
	def TransformTime(seconds):
		## OLD's "HH:MM", never below 00:00 (GB13).
		seconds = max(0, int(seconds))
		m, s = divmod(seconds, 60)
		h, m = divmod(m, 60)
		return "%02d:%02d" % (h, m)

	def __UpdateRefreshTime(self):
		text = self.TransformTime((self.refreshEndTime - app.GetGlobalTime()) // 1000)
		if text != self.refreshText:
			self.refreshText = text
			self.refreshTime.SetText(text)

	def OnUpdate(self):
		(x, y, z) = player.GetMainCharacterPosition()
		if abs(x - self.xGemShopStart) > self.GEM_SHOP_WINDOW_LIMIT_RANGE or abs(y - self.yGemShopStart) > self.GEM_SHOP_WINDOW_LIMIT_RANGE:
			self.CloseShop()
			return

		self.__UpdateRefreshTime()

	def RefreshItemSlot(self):
		for i in range(self.GetSlotCount()):
			itemCount = player.GetGemShopItemCount(i)
			if itemCount <= 1:
				itemCount = 0

			self.itemSlot.SetItemSlot(i, player.GetGemShopItemVnum(i), itemCount)
			self.priceList[i].SetText(str(player.GetGemShopItemPrice(i)))

			if self.IsSlotLocked(i):
				self.itemSlot.DisableSlot(i)
			else:
				self.itemSlot.EnableSlot(i)

		self.itemSlot.RefreshSlot()

	def IsSlotLocked(self, slotIndex):
		return player.GetGemShopItemStatus(slotIndex) == self.SLOT_STATUS_LOCKED

	def OverInItem(self, slotIndex):
		if mouseModule.mouseController.isAttached():
			return

		if self.tooltipItem:
			self.tooltipItem.SetItemToolTip(player.GetGemShopItemVnum(slotIndex))

	def OverOutItem(self):
		if self.tooltipItem:
			self.tooltipItem.HideToolTip()

	def UseItemSlot(self, slotIndex):
		if self.IsSlotLocked(slotIndex):
			## The unlock costs come from the server (OLD's literal
			## 0, 0, 0, 1, 2, 4, 8, 8, 8, uiGemShop.py:118).
			unlockVnum = player.GetGemShopUnlockItemVnum()
			needCount = player.GetGemShopUnlockCost(slotIndex)
			haveCount = player.GetItemCountByVnum(unlockVnum)
			item.SelectItem(unlockVnum)
			itemName = item.GetItemName()
			if haveCount < needCount:
				chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.GEM_SYSTEM_NOT_ENOUGHT_ADDITEM % (itemName, needCount - haveCount))
			else:
				self.SlotAddQuestion(slotIndex, needCount, itemName)
		else:
			if player.GetGem() < player.GetGemShopItemPrice(slotIndex):
				chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.GEM_SYSTEM_NOT_ENOUGH_HP_GEM)
			else:
				self.GemShopSlotBuy(slotIndex)

	## One question at a time: a new one closes the one before.
	def __OpenQuestion(self, text, acceptEvent):
		self.SlotAddQuestionCancel()
		questionDialog = uiCommon.QuestionDialog()
		questionDialog.SetText(text)
		questionDialog.SetAcceptEvent(acceptEvent)
		questionDialog.SetCancelEvent(ui.__mem_func__(self.SlotAddQuestionCancel))
		questionDialog.Open()
		self.questionDialog = questionDialog

	def SlotAddQuestion(self, slotIndex, needCount, needName):
		self.__OpenQuestion(localeInfo.GEM_SYSTEM_ADD_SLOT % (needName, needCount),
			lambda arg = int(slotIndex): self.SlotAddQuestionAccept(arg))

	def SlotAddQuestionAccept(self, slotIndex):
		self.SlotAddQuestionCancel()
		net.SendGemShopAdd(slotIndex)

	def SlotAddQuestionCancel(self):
		if self.questionDialog:
			self.questionDialog.Close()

		self.questionDialog = None

	def SendRequestRefresh(self):
		if player.GetItemCountByVnum(player.GetGemShopRefreshItemVnum()) < 1:
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.GEM_SYSTEM_NOT_ENOUGHT_REFRESHITEM)
		else:
			self.__OpenQuestion(localeInfo.GEM_SYSTEM_REFRESH_SHOP_ITEMS, ui.__mem_func__(self.RefreshGemAccept))

	def RefreshGemAccept(self):
		self.SlotAddQuestionCancel()
		net.SendGemShopRefresh()

	def GemShopSlotBuy(self, slotIndex):
		self.__OpenQuestion(localeInfo.GEM_SYSTEM_BUY_ITEM, lambda arg = int(slotIndex): self.SendBuyAccept(arg))

	def SendBuyAccept(self, slotIndex):
		self.SlotAddQuestionCancel()
		net.SendGemShopBuy(slotIndex)
