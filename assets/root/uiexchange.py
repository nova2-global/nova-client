import time

import player
import exchange
import net
import localeInfo
import chat
import item

import ui
import mouseModule
import uiCommon
import uiPickMoney
import wndMgr
import constInfo

## The faces by race (OLD uiExchange.py:28-38; playersettingmodule's RACE_*:
## 0 warrior m, 1 assassin w, 2 sura m, 3 shaman w, 4 warrior w, 5 assassin m,
## 6 sura w, 7 shaman m). NEW has no wolfman.
FACE_IMAGE_DICT = {
	0 : "icon/face/warrior_m.tga",
	1 : "icon/face/assassin_w.tga",
	2 : "icon/face/sura_m.tga",
	3 : "icon/face/shaman_w.tga",
	4 : "icon/face/warrior_w.tga",
	5 : "icon/face/assassin_m.tga",
	6 : "icon/face/sura_w.tga",
	7 : "icon/face/shaman_m.tga",
}
## A side's slots once it accepted: green (OLD uiExchange.py:552-558).
SLOT_BASE_IMAGE = "d:/ymir work/ui/public/slot_base.sub"
ACCEPTED_SLOT_BASE_COLOR = (0.35, 0.85, 0.35, 1.0)
SLOT_BASE_COLOR = (1.0, 1.0, 1.0, 1.0)
## The history's visible lines (OLD showed two in a scrolled list; the last
## three show here, the whole history is exchangeLogs).
EXCHANGE_LOG_LINE_COUNT = 3


def CallIfAny(widget, name, *args):
	"""widget.name(*args) when the widget has it (NovaUI's proxies of the
	legacy widgets do not all have the 24-slot window's calls)."""
	method = getattr(widget, name, None) if widget else None
	if method:
		method(*args)

###################################################################################################
## Exchange (NOVA-12: OLD's 24-slot window, faces, level and history; NOVA-13:
## the source cells of the items put in are locked in the inventories)
class ExchangeDialog(ui.ScriptWindow):

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.TitleName = 0
		self.tooltipItem = 0
		self.xStart = 0
		self.yStart = 0
		self.interface = None
		self.wndInventory = None
		self.wndExtraInventory = None
		# {display slot: (window, cell)}: the cells the items put in came from.
		self.lockedItems = {}
		self.FaceOwnerImage = None
		self.FaceTargetImage = None
		self.TargetName = None
		self.TargetLevel = None
		self.ExchangeLogLines = []
		self.exchangeLogs = []
		self.questionDialog = None
		self.isOwnerAccepted = False
		self.isTargetAccepted = False

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def LoadDialog(self):
		PythonScriptLoader = ui.PythonScriptLoader()
		PythonScriptLoader.LoadScriptFile(self, "UIScript/exchangedialog.py")

		## Owner
		self.OwnerSlot = self.GetChild("Owner_Slot")
		self.OwnerSlot.SetSelectEmptySlotEvent(ui.__mem_func__(self.SelectOwnerEmptySlot))
		self.OwnerSlot.SetSelectItemSlotEvent(ui.__mem_func__(self.SelectOwnerItemSlot))
		self.OwnerSlot.SetOverInItemEvent(ui.__mem_func__(self.OverInOwnerItem))
		self.OwnerSlot.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		self.OwnerMoney = self.GetChild("Owner_Money_Value")
		self.OwnerAcceptLight = self.GetChild("Owner_Accept_Light")
		self.OwnerAcceptLight.Disable()
		self.OwnerMoneyButton = self.GetChild("Owner_Money")
		self.OwnerMoneyButton.SetEvent(ui.__mem_func__(self.OpenPickMoneyDialog))

		## Target
		self.TargetSlot = self.GetChild("Target_Slot")
		self.TargetSlot.SetOverInItemEvent(ui.__mem_func__(self.OverInTargetItem))
		self.TargetSlot.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		self.TargetMoney = self.GetChild("Target_Money_Value")
		self.TargetAcceptLight = self.GetChild("Target_Accept_Light")
		self.TargetAcceptLight.Disable()

		## PickMoneyDialog
		dlgPickMoney = uiPickMoney.PickMoneyDialog()
		dlgPickMoney.LoadDialog()
		dlgPickMoney.SetAcceptEvent(ui.__mem_func__(self.OnPickMoney))
		dlgPickMoney.SetTitleName(localeInfo.EXCHANGE_MONEY)
		# OLD's 12 digits for the exchange's money (OLD uiExchange.py:114-116; Q13: decided 2026-10-25).
		dlgPickMoney.SetMax(player.EXCHANGE_MONEY_DIGITS)
		dlgPickMoney.Hide()
		self.dlgPickMoney = dlgPickMoney

		## Button
		self.AcceptButton = self.GetChild("Owner_Accept_Button")
		self.AcceptButton.SetToggleDownEvent(ui.__mem_func__(self.AcceptExchange))

		self.TitleName = self.GetChild("TitleName")
		self.GetChild("TitleBar").SetCloseEvent(net.SendExchangeExitPacket)

		## The faces, the partner's name and level and the history (OLD uiExchange.py:118-142).
		self.FaceOwnerImage = self.GetChild("FaceOwner_Image")
		self.FaceTargetImage = self.GetChild("FaceTarget_Image")
		self.TargetName = self.GetChild("target_NameText")
		self.TargetLevel = self.GetChild("target_LvText")
		self.ExchangeLogLines = [self.GetChild("ExchangeLog_%d" % i) for i in range(EXCHANGE_LOG_LINE_COUNT)]

	def Destroy(self):
		print("---------------------------------------------------------------------------- DESTROY EXCHANGE")
		self.ClearDictionary()
		self.dlgPickMoney.Destroy()
		self.dlgPickMoney = 0
		self.OwnerSlot = 0
		self.OwnerMoney = 0
		self.OwnerAcceptLight = 0
		self.OwnerMoneyButton = 0
		self.TargetSlot = 0
		self.TargetMoney = 0
		self.TargetAcceptLight = 0
		self.TitleName = 0
		self.AcceptButton = 0
		self.tooltipItem = 0
		self.FaceOwnerImage = None
		self.FaceTargetImage = None
		self.TargetName = None
		self.TargetLevel = None
		self.ExchangeLogLines = []
		self.questionDialog = None
		self.interface = None
		self.wndInventory = None
		self.wndExtraInventory = None
		self.lockedItems = {}

	def OpenDialog(self):
		self.TitleName.SetText(localeInfo.EXCHANGE_TITLE % (exchange.GetNameFromTarget()))
		self.AcceptButton.Enable()
		self.AcceptButton.SetUp()

		## OLD uiExchange.py:206-215: both faces, the partner's name and level,
		## and a history that starts with "ready".
		if self.FaceOwnerImage:
			self.FaceOwnerImage.LoadImage(FACE_IMAGE_DICT.get(exchange.GetRaceFromSelf(), FACE_IMAGE_DICT[0]))
		if self.FaceTargetImage:
			self.FaceTargetImage.LoadImage(FACE_IMAGE_DICT.get(exchange.GetRaceFromTarget(), FACE_IMAGE_DICT[0]))
		if self.TargetName:
			self.TargetName.SetText(exchange.GetNameFromTarget())
		if self.TargetLevel:
			self.TargetLevel.SetText(localeInfo.NEW_EXCHANGE_LEVEL % (exchange.GetLevelFromTarget()))

		self.isOwnerAccepted = False
		self.isTargetAccepted = False
		self.exchangeLogs = []
		self.AppendExchangeLog(localeInfo.NEW_EXCHANGE_YOU_READY % (self.__LogTime()))

		self.lockedItems = {}
		self.Show()

		(self.xStart, self.yStart, z) = player.GetMainCharacterPosition()

		self.__SetOnTopWindow(player.ON_TOP_WND_EXCHANGE)

	def CloseDialog(self):
		wndMgr.OnceIgnoreMouseLeftButtonUpEvent()

		if 0 != self.tooltipItem:
			self.tooltipItem.HideToolTip()

		self.dlgPickMoney.Close()
		self.OnCloseQuestionDialog()
		self.Hide()

		## The trade ended (completed, canceled or out of range): every source
		## cell takes the mouse again.
		self.ReleaseLockedItems()
		self.__SetOnTopWindow(player.ON_TOP_WND_NONE)

	## The tradable icon (NOVA-13; OLD uiExchange.py:599-631)
	def BindInterface(self, interface):
		self.interface = interface

	def SetInven(self, wndInventory, wndExtraInventory=None):
		self.wndInventory = wndInventory
		self.wndExtraInventory = wndExtraInventory

	def __SetOnTopWindow(self, onTopWnd):
		if not self.interface:
			return
		self.interface.SetOnTopWindow(onTopWnd)
		self.interface.RefreshMarkInventoryBag()

	def __InventoryWindowOf(self, window):
		if window == player.INVENTORY:
			return self.wndInventory
		if window == player.EXTRA_INVENTORY:
			return self.wndExtraInventory
		return None

	def CantTradableItem(self, destSlotIndex, srcSlotIndex, srcWindow=player.INVENTORY):
		"""The server put the item of (srcWindow, srcSlotIndex) at the
		display slot destSlotIndex (GC ITEM_ADD's arg4, game.py
		BINARY_AddItemToExchange): its cell takes no mouse event until the
		trade ends or the item leaves it. OLD's early return once the
		partner accepted is left out: the server sends no ITEM_ADD then."""
		self.lockedItems[destSlotIndex] = (srcWindow, srcSlotIndex)
		wnd = self.__InventoryWindowOf(srcWindow)
		if wnd and self.IsShow():
			wnd.SetCantMouseEventCell(srcSlotIndex)

	def ReleaseTradableItem(self, destSlotIndex):
		"""GC ITEM_DEL of a display slot (game.py BINARY_DelItemFromExchange):
		past OLD, its source cell takes the mouse again."""
		if destSlotIndex not in self.lockedItems:
			return
		(srcWindow, srcSlotIndex) = self.lockedItems.pop(destSlotIndex)
		wnd = self.__InventoryWindowOf(srcWindow)
		if wnd:
			wnd.SetCanMouseEventCell(srcSlotIndex)

	def ReleaseLockedItems(self):
		for destSlotIndex in list(self.lockedItems.keys()):
			self.ReleaseTradableItem(destSlotIndex)

	def RefreshLockedSlot(self):
		"""Locks the source cells again (an inventory's page was refreshed)."""
		for (srcWindow, srcSlotIndex) in list(self.lockedItems.values()):
			wnd = self.__InventoryWindowOf(srcWindow)
			if wnd:
				wnd.SetCantMouseEventCell(srcSlotIndex)

	## The history (OLD uiExchange.py:213-216, 545-575)
	def __LogTime(self):
		return time.strftime("[%H:%M:%S]")

	def AppendExchangeLog(self, text):
		self.exchangeLogs.append(text)
		shown = self.exchangeLogs[-len(self.ExchangeLogLines):] if self.ExchangeLogLines else []
		for index, line in enumerate(self.ExchangeLogLines):
			line.SetText(shown[index] if index < len(shown) else "")

	def SetItemToolTip(self, tooltipItem):
		self.tooltipItem = tooltipItem

	def OpenPickMoneyDialog(self):

		if exchange.GetElkFromSelf() > 0:
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.EXCHANGE_CANT_EDIT_MONEY)
			return

		self.dlgPickMoney.Open(player.GetElk())

	def OnPickMoney(self, money):
		net.SendExchangeElkAddPacket(money)

	def AcceptExchange(self):
		## OLD uiExchange.py:254-293: giving something for nothing asks first.
		## The partner offers an item or yang: accept. Else, if you offer one:
		## the warning. Else (an empty trade): accept.
		if self.__OffersSomething("Target"):
			self.__SendAccept()
		elif self.__OffersSomething("Self"):
			self.OnCloseQuestionDialog()
			questionDialog = uiCommon.QuestionDialog2()
			questionDialog.SetText1(localeInfo.NEW_EXCHANGE_ALERT1)
			questionDialog.SetText2(localeInfo.NEW_EXCHANGE_ALERT2)
			questionDialog.SetAcceptEvent(ui.__mem_func__(self.AcceptQuestion))
			questionDialog.SetCancelEvent(ui.__mem_func__(self.CancelQuestion))
			questionDialog.Open()
			self.questionDialog = questionDialog
		else:
			self.__SendAccept()

	def __OffersSomething(self, side):
		getItemCount = getattr(exchange, "GetItemCountFrom" + side)
		for i in range(exchange.EXCHANGE_ITEM_MAX_NUM):
			if getItemCount(i) >= 1:
				return True
		return getattr(exchange, "GetElkFrom" + side)() >= 1

	def __SendAccept(self):
		net.SendExchangeAcceptPacket()
		self.AcceptButton.Disable()

	def AcceptQuestion(self):
		self.OnCloseQuestionDialog()
		self.__SendAccept()

	def CancelQuestion(self):
		self.OnCloseQuestionDialog()
		self.AcceptButton.Enable()
		self.AcceptButton.SetUp()

	def OnCloseQuestionDialog(self):
		if self.questionDialog:
			self.questionDialog.Close()
		self.questionDialog = None

	def SelectOwnerEmptySlot(self, SlotIndex):

		if False == mouseModule.mouseController.isAttached():
			return

		if mouseModule.mouseController.IsAttachedMoney():
			net.SendExchangeElkAddPacket(mouseModule.mouseController.GetAttachedMoneyAmount())
		else:
			attachedSlotType = mouseModule.mouseController.GetAttachedType()
			# The special inventory's items too (NOVA-16; OLD uiExchange.py:325-338).
			if (player.SLOT_TYPE_INVENTORY == attachedSlotType
				or player.SLOT_TYPE_DRAGON_SOUL_INVENTORY == attachedSlotType
				or player.SLOT_TYPE_EXTRA_INVENTORY == attachedSlotType):

				attachedInvenType = player.SlotTypeToInvenType(attachedSlotType)
				SrcSlotNumber = mouseModule.mouseController.GetAttachedSlotNumber()
				DstSlotNumber = SlotIndex

				itemID = player.GetItemIndex(attachedInvenType, SrcSlotNumber)

				# MR-3: Auto-deactivate auto potions before moving out
				if attachedSlotType == player.SLOT_TYPE_INVENTORY:
					itemVnum = player.GetItemIndex(attachedInvenType, SrcSlotNumber)

					if constInfo.IS_AUTO_POTION(itemVnum):
						metinSocket = [player.GetItemMetinSocket(attachedInvenType, SrcSlotNumber, j) for j in range(player.METIN_SOCKET_MAX_NUM)]
						isActivated = (0 != int(metinSocket[0]))

						if isActivated:
							net.SendItemUsePacket(SrcSlotNumber)
				# MR-3: -- END OF -- Auto-deactivate auto potions before moving out
				item.SelectItem(itemID)

				if item.IsAntiFlag(item.ANTIFLAG_GIVE):
					chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.EXCHANGE_CANNOT_GIVE)
					mouseModule.mouseController.DeattachObject()
					return

				net.SendExchangeItemAddPacket(attachedInvenType, SrcSlotNumber, DstSlotNumber)

		mouseModule.mouseController.DeattachObject()

	def SelectOwnerItemSlot(self, SlotIndex):

		if player.ITEM_MONEY == mouseModule.mouseController.GetAttachedItemIndex():

			money = mouseModule.mouseController.GetAttachedItemCount()
			net.SendExchangeElkAddPacket(money)

	def RefreshOwnerSlot(self):
		for i in range(exchange.EXCHANGE_ITEM_MAX_NUM):
			itemIndex = exchange.GetItemVnumFromSelf(i)
			itemCount = exchange.GetItemCountFromSelf(i)
			if 1 == itemCount:
				itemCount = 0
			self.OwnerSlot.SetItemSlot(i, itemIndex, itemCount)
		self.OwnerSlot.RefreshSlot()

	def RefreshTargetSlot(self):
		for i in range(exchange.EXCHANGE_ITEM_MAX_NUM):
			itemIndex = exchange.GetItemVnumFromTarget(i)
			itemCount = exchange.GetItemCountFromTarget(i)
			if 1 == itemCount:
				itemCount = 0
			self.TargetSlot.SetItemSlot(i, itemIndex, itemCount)
		self.TargetSlot.RefreshSlot()

	def Refresh(self):

		self.RefreshOwnerSlot()
		self.RefreshTargetSlot()

		# self.OwnerMoney.SetText(str(exchange.GetElkFromSelf()))
		# self.TargetMoney.SetText(str(exchange.GetElkFromTarget()))
		
		self.OwnerMoney.SetText(str(('.'.join([ i-3<0 and str(exchange.GetElkFromSelf())[:i] or str(exchange.GetElkFromSelf())[i-3:i] for i in range(len(str(exchange.GetElkFromSelf()))%3, len(str(exchange.GetElkFromSelf()))+1, 3) if i ]))))
		self.TargetMoney.SetText(str(('.'.join([ i-3<0 and str(exchange.GetElkFromTarget())[:i] or str(exchange.GetElkFromTarget())[i-3:i] for i in range(len(str(exchange.GetElkFromTarget()))%3, len(str(exchange.GetElkFromTarget()))+1, 3) if i ]))))

		if True == exchange.GetAcceptFromSelf():
			self.OwnerAcceptLight.Down()
		else:
			self.AcceptButton.Enable()
			self.AcceptButton.SetUp()
			self.OwnerAcceptLight.SetUp()

		if True == exchange.GetAcceptFromTarget():
			self.TargetAcceptLight.Down()
		else:
			self.TargetAcceptLight.SetUp()

		## OLD uiExchange.py:552-575: an accepted side's slots are green, and
		## the history says who accepted or took it back. Past OLD, a line is
		## written when a side's accept changes, not on every refresh.
		isOwnerAccepted = (True == exchange.GetAcceptFromSelf())
		isTargetAccepted = (True == exchange.GetAcceptFromTarget())
		self.__SetSlotBase(self.OwnerSlot, isOwnerAccepted)
		self.__SetSlotBase(self.TargetSlot, isTargetAccepted)

		if isOwnerAccepted != self.isOwnerAccepted:
			text = localeInfo.NEW_EXCHANGE_YOU_ACCEPT if isOwnerAccepted else localeInfo.NEW_EXCHANGE_YOU_ABORT
			self.AppendExchangeLog(text % (self.__LogTime()))
		if isTargetAccepted != self.isTargetAccepted:
			text = localeInfo.NEW_EXCHANGE_ACCEPT if isTargetAccepted else localeInfo.NEW_EXCHANGE_ABORT
			self.AppendExchangeLog(text % (self.__LogTime(), exchange.GetNameFromTarget()))
		self.isOwnerAccepted = isOwnerAccepted
		self.isTargetAccepted = isTargetAccepted

		self.RefreshLockedSlot()

	def __SetSlotBase(self, slotWindow, isAccepted):
		color = ACCEPTED_SLOT_BASE_COLOR if isAccepted else SLOT_BASE_COLOR
		CallIfAny(slotWindow, "SetSlotBaseImage", SLOT_BASE_IMAGE, *color)

	def OverInOwnerItem(self, slotIndex):

		if 0 != self.tooltipItem:
			self.tooltipItem.SetExchangeOwnerItem(slotIndex)

	def OverInTargetItem(self, slotIndex):

		if 0 != self.tooltipItem:
			self.tooltipItem.SetExchangeTargetItem(slotIndex)

	def OverOutItem(self):

		if 0 != self.tooltipItem:
			self.tooltipItem.HideToolTip()

	def OnTop(self):
		self.tooltipItem.SetTop()
		self.__SetOnTopWindow(player.ON_TOP_WND_EXCHANGE)

	def OnUpdate(self):

		USE_EXCHANGE_LIMIT_RANGE = 1000

		(x, y, z) = player.GetMainCharacterPosition()
		if abs(x - self.xStart) > USE_EXCHANGE_LIMIT_RANGE or abs(y - self.yStart) > USE_EXCHANGE_LIMIT_RANGE:
			(self.xStart, self.yStart, z) = player.GetMainCharacterPosition()
			net.SendExchangeExitPacket()
