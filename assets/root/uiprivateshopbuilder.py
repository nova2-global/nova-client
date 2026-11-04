import ui
import snd
import shop
import mouseModule
import player
import chr
import net
import uiCommon
import localeInfo
import chat
import item
import systemSetting
import player
import app
import grp

## The offline shop's rules and the remembered prices ship with this module. A host that loads it
## alone (the NovaUI windows' test worlds) keeps NEW's rules: every sign, the 40-cell grid.
try:
	import offlineshopconst
except ImportError:
	offlineshopconst = None
try:
	import itemPrices
except ImportError:
	itemPrices = None

g_isBuildingPrivateShop = False

g_itemPriceDict={}

g_privateShopAdvertisementBoardDict={}

## The offline shop's decoration (NOVA-9): the model vnum (0: CONFIG's first model) and the sign
## style (0-5) the builder sends with CREATE. The shop name dialog sets both to 0 when it opens;
## the decoration window writes them only on Complete (o-cli bug 10).
SHOP_DECO = 0
SHOP_STYLE = 0

## The signs that show (o-cli bugs 12, 23): the player's own, the target and the hovered one,
## and the nearest offlineshopconst.sign_display_count() within SIGN_RANGE, worked out at most
## once a second, or when a sign comes or goes. One rule for every style.
g_nearBoardVids = set()
g_boardsDirty = True
g_nextBoardRefresh = 0.0
g_boardRefresher = None

def Clear():
	global g_itemPriceDict
	global g_isBuildingPrivateShop
	g_itemPriceDict={}
	g_isBuildingPrivateShop = False

def IsPrivateShopItemPriceList():
	global g_itemPriceDict
	if g_itemPriceDict:
		return True
	else:
		return False

def IsBuildingPrivateShop():
	global g_isBuildingPrivateShop
	if player.IsOpenPrivateShop() or g_isBuildingPrivateShop:
		return True
	else:
		return False

def SetPrivateShopItemPrice(itemVNum, itemPrice):
	global g_itemPriceDict
	g_itemPriceDict[int(itemVNum)]=itemPrice
	
def GetPrivateShopItemPrice(itemVNum):
	"""The server's price list's price, else the price the player last asked (itemPrices)."""
	try:
		global g_itemPriceDict
		return g_itemPriceDict[itemVNum]
	except KeyError:
		if itemPrices:
			return itemPrices.get_price(itemVNum)
		return 0
		
def UpdateADBoard():	
	for key in list(g_privateShopAdvertisementBoardDict.keys()):
		g_privateShopAdvertisementBoardDict[key].Show()
		
def DeleteADBoard(vid):
	if vid not in g_privateShopAdvertisementBoardDict:
		return
			
	del g_privateShopAdvertisementBoardDict[vid]
	_MarkBoardsDirty()

def _MarkBoardsDirty():
	global g_boardsDirty
	g_boardsDirty = True

def _EnsureBoardRefresher():
	global g_boardRefresher
	if g_boardRefresher is None:
		g_boardRefresher = _BoardRefresher()
		g_boardRefresher.Show()

def RefreshShopBoards(force=False):
	"""Works out the nearest signs (at most once a second, or at once when a sign came or went),
	shows the hidden signs the rule takes again, and gives a visited sign its own color back
	after SIGN_SEEN_MINUTES."""
	global g_nearBoardVids, g_boardsDirty, g_nextBoardRefresh
	if not offlineshopconst:
		return
	now = app.GetTime()
	if not force and not g_boardsDirty and now < g_nextBoardRefresh:
		return
	g_boardsDirty = False
	g_nextBoardRefresh = now + offlineshopconst.SIGN_REFRESH_SEC
	vids = list(g_privateShopAdvertisementBoardDict.keys())
	g_nearBoardVids = set(offlineshopconst.nearest_signs(vids, player.GetCharacterDistance,
	                                                     offlineshopconst.sign_display_count()))
	for vid in vids:
		board = g_privateShopAdvertisementBoardDict[vid]
		markUnseen = getattr(board, "MarkUnseen", None)
		if markUnseen and getattr(board, "lastSeen", 0) and not offlineshopconst.is_seen(vid, now):
			markUnseen()
		if IsBoardShown(vid) and not board.IsShow():
			board.Show()

def IsBoardShown(vid):
	"""Whether the sign of `vid` shows now: the player's own (the stall, NEW's rule, and the
	offline shop, an NPC with its own VID), the target and the hovered one whatever the
	option (OLD uiPrivateShopBuilder.py:110); with the sales texts on, also the nearest. A host
	without the offline shop's rules keeps NEW's: all with the option on, the own stall off."""
	own = player.GetMainCharacterIndex()
	if not offlineshopconst:
		return vid == own or bool(systemSetting.IsShowSalesText())
	ownShop = getattr(player, "GetOwnOfflineShopVID", None)
	if vid == own or (callable(ownShop) and vid == ownShop()):
		return True
	if vid == player.GetTargetVID() or vid == chr.Pick():
		return True
	return bool(systemSetting.IsShowSalesText()) and vid in g_nearBoardVids

def _UpdateBoard(board):
	"""A sign's frame: shown and placed over its character, or hidden by the rule."""
	if not board.vid:
		return
	RefreshShopBoards()
	if not IsBoardShown(board.vid):
		board.Hide()
		return
	board.Show()
	x, y = chr.GetProjectPosition(board.vid, 220)
	board.SetPosition(x - board.GetWidth()//2, y - board.GetHeight()//2)

class _BoardRefresher(ui.Window):
	"""An empty window whose frame runs the sign rule, so a hidden sign shows again."""

	def __init__(self):
		ui.Window.__init__(self, "UI_BOTTOM")
		self.AddFlag("not_pick")
		self.SetSize(0, 0)

	def __del__(self):
		ui.Window.__del__(self)

	def OnUpdate(self):
		RefreshShopBoards()
		

class PrivateShopAdvertisementBoard(ui.ThinBoard):
	# A visited shop's sign (OLD uiPrivateShopBuilder.py:132-198): purple for SIGN_SEEN_MINUTES.
	SEEN_COLOR = (0.30, 0.05, 0.40, 0.70)

	def __init__(self):
		ui.ThinBoard.__init__(self, "UI_BOTTOM")
		self.vid = None
		self.title = ""
		self.lastSeen = 0
		self.__MakeTextLine()

	def __del__(self):
		ui.ThinBoard.__del__(self)

	def __MakeTextLine(self):
		self.textLine = ui.TextLine()
		self.textLine.SetParent(self)
		self.textLine.SetWindowHorizontalAlignCenter()
		self.textLine.SetWindowVerticalAlignCenter()
		self.textLine.SetHorizontalAlignCenter()
		self.textLine.SetVerticalAlignCenter()
		self.textLine.Show()

	def Open(self, vid, text):
		self.vid = vid
		self.title = text

		self.textLine.SetText(text)
		self.textLine.UpdateRect()
		self.SetSize(len(text)*6 + 10*2, 20)
		self.Show() 
				
		g_privateShopAdvertisementBoardDict[vid] = self
		_MarkBoardsDirty()
		_EnsureBoardRefresher()

		if offlineshopconst and offlineshopconst.is_seen(vid, app.GetTime()):
			self.MarkSeen(offlineshopconst.seen_at(vid))

	def UpdateTitle(self, text):
		"""A new sign for a board already shown (GC SHOP_SIGN again)."""
		self.title = text
		self.textLine.SetText(text)
		self.textLine.UpdateRect()
		self.SetSize(len(text)*6 + 10*2, 20)

	def MarkSeen(self, when=None):
		"""The player opened this shop: its sign turns purple for a while."""
		self.lastSeen = app.GetTime() if when is None else when
		if offlineshopconst:
			offlineshopconst.mark_seen(self.vid, self.lastSeen)
		base = getattr(self, "Base", None)
		if base:
			base.SetColor(grp.GenerateColor(*self.SEEN_COLOR))

	def MarkUnseen(self):
		self.lastSeen = 0
		base = getattr(self, "Base", None)
		if base:
			base.SetColor(self.BOARD_COLOR)
		
	def OnMouseLeftButtonUp(self):
		if not self.vid:
			return
		net.SendOnClickPacket(self.vid)
		
		return True
		
	def OnUpdate(self):
		_UpdateBoard(self)

class PrivateShopTitleBar(ui.Window):
	"""A decorated shop's sign (NOVA-9; OLD uiPrivateShopBuilder.py:525-611), style 1 to 5 of
	shop_deco.txt: ui.ShopDecoTitle's frame and the style's font color. It has the board's calls
	(Open, UpdateTitle, MarkSeen, Destroy), stores its title for the shop window (o-cli bug 11),
	and follows the same sign rule (o-cli bug 12). A style without art is drawn as 0 (L15)."""

	HEIGHT = 32

	def __init__(self, style):
		ui.Window.__init__(self, "UI_BOTTOM")
		self.style = offlineshopconst.clamp_style(style) if offlineshopconst else 0
		self.vid = None
		self.title = ""
		self.lastSeen = 0

		self.frame = ui.ShopDecoTitle(self.style)
		self.frame.SetParent(self)
		self.frame.AddFlag("not_pick")
		self.frame.SetPosition(0, 0)
		self.frame.Show()

		self.textLine = ui.TextLine()
		self.textLine.SetParent(self)
		self.textLine.SetWindowHorizontalAlignCenter()
		self.textLine.SetWindowVerticalAlignCenter()
		self.textLine.SetHorizontalAlignCenter()
		self.textLine.SetVerticalAlignCenter()
		self.textLine.SetFontColor(*self.frame.GetFontColor())
		self.textLine.Show()

	def __del__(self):
		ui.Window.__del__(self)

	def __Resize(self, text):
		width = max(32, len(text) * 6 + 20 * 2)
		self.SetSize(width, self.HEIGHT)
		self.frame.SetSize(width, self.HEIGHT)
		self.textLine.UpdateRect()

	def Open(self, vid, text):
		self.vid = vid
		self.title = text
		self.textLine.SetText(text)
		self.__Resize(text)
		self.Show()

		g_privateShopAdvertisementBoardDict[vid] = self
		_MarkBoardsDirty()
		_EnsureBoardRefresher()

	def UpdateTitle(self, text):
		self.title = text
		self.textLine.SetText(text)
		self.__Resize(text)

	def MarkSeen(self, when=None):
		self.lastSeen = app.GetTime() if when is None else when
		if offlineshopconst:
			offlineshopconst.mark_seen(self.vid, self.lastSeen)

	def MarkUnseen(self):
		self.lastSeen = 0

	def OnMouseLeftButtonUp(self):
		if not self.vid:
			return
		net.SendOnClickPacket(self.vid)
		return True

	def OnUpdate(self):
		_UpdateBoard(self)

	def Destroy(self):
		DeleteADBoard(self.vid)

class PrivateShopBuilder(ui.ScriptWindow):

	def __init__(self):
		#print "NEW MAKE_PRIVATE_SHOP_WINDOW ----------------------------------------------------------------"
		ui.ScriptWindow.__init__(self)

		self.__LoadWindow()
		self.itemStock = {}
		self.tooltipItem = None
		self.priceInputBoard = None
		self.interface = None
		self.wndInventory = None
		self.wndExtraInventory = None
		self.title = ""
		self.isOpen = False
		self.created = False

	def __del__(self):
		#print "------------------------------------------------------------- DELETE MAKE_PRIVATE_SHOP_WINDOW"
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/privateshopbuildernew.py")
		except:
			import exception
			exception.Abort("PrivateShopBuilderWindow.LoadWindow.LoadObject")

		try:
			GetObject = self.GetChild
			self.nameLine = GetObject("NameLine")
			self.itemSlot = GetObject("ItemSlot")
			self.btnOk = GetObject("OkButton")
			self.btnClose = GetObject("CloseButton")
			self.titleBar = GetObject("TitleBar")
		except:
			import exception
			exception.Abort("PrivateShopBuilderWindow.LoadWindow.BindObject")

		self.btnOk.SetEvent(ui.__mem_func__(self.OnOk))
		self.btnClose.SetEvent(ui.__mem_func__(self.OnClose))
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.OnClose))

		self.itemSlot.SetSelectEmptySlotEvent(ui.__mem_func__(self.OnSelectEmptySlot))
		self.itemSlot.SetSelectItemSlotEvent(ui.__mem_func__(self.OnSelectItemSlot))
		self.itemSlot.SetOverInItemEvent(ui.__mem_func__(self.OnOverInItem))
		self.itemSlot.SetOverOutItemEvent(ui.__mem_func__(self.OnOverOutItem))

	def Destroy(self):
		self.ClearDictionary()

		self.nameLine = None
		self.itemSlot = None
		self.btnOk = None
		self.btnClose = None
		self.titleBar = None
		self.priceInputBoard = None

	def Open(self, title):

		self.title = title

		if len(title) > 25:
			title = title[:22] + "..."

		self.itemStock = {}
		self.isOpen = True
		self.created = False
		shop.ClearPrivateShopStock()
		self.nameLine.SetText(title)
		self.__ArrangeCells()
		self.SetCenterPosition()
		self.Refresh()
		self.Show()

		global g_isBuildingPrivateShop
		g_isBuildingPrivateShop = True

		self.__SetOnTopWindow(player.ON_TOP_WND_PRIVATE_SHOP)

	def Close(self):
		global g_isBuildingPrivateShop
		g_isBuildingPrivateShop = False

		## A builder closed without OK ends the server's builder session (CG LEAVE, spec 3.4.2).
		if self.isOpen and not self.created:
			net.SendOfflineShopLeavePacket()
		self.isOpen = False

		## Every cell an item came from takes the mouse again (NOVA-13).
		for (invenType, invenPos) in list(self.itemStock.values()):
			self.__SetCellLocked(invenType, invenPos, False)

		self.title = ""
		self.itemStock = {}
		shop.ClearPrivateShopStock()
		self.Hide()

		self.__SetOnTopWindow(player.ON_TOP_WND_NONE)

	## The tradable icon (NOVA-13; OLD uiPrivateShopBuilder.py:210-302): the
	## cell of an item put into the shop takes no mouse event (a red cover)
	## until it leaves the shop or the window closes; the items of the stock
	## ({shop slot: (window, cell)}) are the locks.
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

	def __SetCellLocked(self, invenType, invenPos, isLocked):
		if invenType == player.INVENTORY:
			wnd = self.wndInventory
		elif invenType == player.EXTRA_INVENTORY:
			wnd = self.wndExtraInventory
		else:
			wnd = None
		if not wnd:
			return
		if isLocked:
			wnd.SetCantMouseEventCell(invenPos)
		else:
			wnd.SetCanMouseEventCell(invenPos)

	def RefreshLockedSlot(self):
		for (invenType, invenPos) in list(self.itemStock.values()):
			self.__SetCellLocked(invenType, invenPos, True)

	def SetItemToolTip(self, tooltipItem):
		self.tooltipItem = tooltipItem

	def GetCellCount(self):
		"""The cells a shop opens with: CONFIG's base rows of 10 (spec 3.8)."""
		if offlineshopconst and offlineshopconst.geometry()[0]:
			return offlineshopconst.builder_cell_count()
		return shop.SHOP_SLOT_COUNT

	def __ArrangeCells(self):
		if not offlineshopconst:
			return
		(cols, rows, _, _, _) = offlineshopconst.geometry()
		if cols:
			self.itemSlot.ArrangeSlot(0, cols, self.GetCellCount() // cols, 32, 32, 0, 0)
			self.itemSlot.SetSlotBaseImage("d:/ymir work/ui/public/Slot_Base.sub", 1.0, 1.0, 1.0, 1.0)

	def Refresh(self):
		getitemVNum=player.GetItemIndex
		getItemCount=player.GetItemCount
		setitemVNum=self.itemSlot.SetItemSlot
		delItem=self.itemSlot.ClearSlot

		for i in range(self.GetCellCount()):

			if i not in self.itemStock:
				delItem(i)
				continue

			pos = self.itemStock[i]

			itemCount = getItemCount(*pos)
			if itemCount <= 1:
				itemCount = 0
			setitemVNum(i, getitemVNum(*pos), itemCount)

		self.itemSlot.RefreshSlot()

	def OnSelectEmptySlot(self, selectedSlotPos):

		isAttached = mouseModule.mouseController.isAttached()
		if isAttached:
			attachedSlotType = mouseModule.mouseController.GetAttachedType()
			attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
			mouseModule.mouseController.DeattachObject()

			# The special inventory's items too (NOVA-16; OLD uiPrivateShopBuilder.py:344).
			if player.SLOT_TYPE_INVENTORY != attachedSlotType and player.SLOT_TYPE_DRAGON_SOUL_INVENTORY != attachedSlotType and \
					player.SLOT_TYPE_EXTRA_INVENTORY != attachedSlotType:
				return
			attachedInvenType = player.SlotTypeToInvenType(attachedSlotType)
				
			itemVNum = player.GetItemIndex(attachedInvenType, attachedSlotPos)
			item.SelectItem(itemVNum)

			if item.IsAntiFlag(item.ANTIFLAG_GIVE) or item.IsAntiFlag(item.ANTIFLAG_MYSHOP):
				chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.PRIVATE_SHOP_CANNOT_SELL_ITEM)
				return

			priceInputBoard = uiCommon.MoneyInputDialog()
			priceInputBoard.SetTitle(localeInfo.PRIVATE_SHOP_INPUT_PRICE_DIALOG_TITLE)
			priceInputBoard.SetAcceptEvent(ui.__mem_func__(self.AcceptInputPrice))
			priceInputBoard.SetCancelEvent(ui.__mem_func__(self.CancelInputPrice))
			priceInputBoard.Open()

			itemPrice=GetPrivateShopItemPrice(itemVNum)

			if itemPrice>0:
				priceInputBoard.SetValue(itemPrice)
			
			self.priceInputBoard = priceInputBoard
			self.priceInputBoard.itemVNum = itemVNum
			self.priceInputBoard.sourceWindowType = attachedInvenType
			self.priceInputBoard.sourceSlotPos = attachedSlotPos
			self.priceInputBoard.targetSlotPos = selectedSlotPos

	def OnSelectItemSlot(self, selectedSlotPos):

		isAttached = mouseModule.mouseController.isAttached()
		if isAttached:
			snd.PlaySound("sound/ui/loginfail.wav")
			mouseModule.mouseController.DeattachObject()

		else:
			if not selectedSlotPos in self.itemStock:
				return

			invenType, invenPos = self.itemStock[selectedSlotPos]
			shop.DelPrivateShopItemStock(invenType, invenPos)
			snd.PlaySound("sound/ui/drop.wav")

			del self.itemStock[selectedSlotPos]
			self.__SetCellLocked(invenType, invenPos, False)

			self.Refresh()

	def AcceptInputPrice(self):

		if not self.priceInputBoard:
			return True

		text = self.priceInputBoard.GetText()

		if not text:
			return True

		if not text.isdigit():
			return True

		if int(text) <= 0:
			return True

		attachedInvenType = self.priceInputBoard.sourceWindowType
		sourceSlotPos = self.priceInputBoard.sourceSlotPos
		targetSlotPos = self.priceInputBoard.targetSlotPos

		for privatePos, (itemWindowType, itemSlotIndex) in list(self.itemStock.items()):
			if itemWindowType == attachedInvenType and itemSlotIndex == sourceSlotPos:
				shop.DelPrivateShopItemStock(itemWindowType, itemSlotIndex)
				del self.itemStock[privatePos]

		price = int(self.priceInputBoard.GetText())

		if IsPrivateShopItemPriceList():
			SetPrivateShopItemPrice(self.priceInputBoard.itemVNum, price)
		if itemPrices:
			itemPrices.set_price(self.priceInputBoard.itemVNum, price)

		shop.AddPrivateShopItemStock(attachedInvenType, sourceSlotPos, targetSlotPos, price)
		self.itemStock[targetSlotPos] = (attachedInvenType, sourceSlotPos)
		self.__SetCellLocked(attachedInvenType, sourceSlotPos, True)
		snd.PlaySound("sound/ui/drop.wav")

		self.Refresh()		

		#####

		self.priceInputBoard = None
		return True

	def CancelInputPrice(self):
		self.priceInputBoard = None
		return True

	def OnOk(self):
		"""CREATE (spec 1.1 sub 0, D6): the sign, the model vnum and the style of the decoration
		window (SHOP_DECO 0: CONFIG's first model), and each cell's (window, cell, slot, price).
		Every player shop is an offline shop; the stall's CG::MYSHOP is never sent (Q6)."""

		if not self.title:
			return

		if 0 == len(self.itemStock):
			return

		listings = []
		for slot in sorted(self.itemStock.keys()):
			(invenType, invenPos) = self.itemStock[slot]
			listings.append((invenType, invenPos, slot, shop.GetPrivateShopItemPrice(invenType, invenPos)))

		modelVnum = SHOP_DECO
		if not modelVnum and offlineshopconst:
			models = offlineshopconst.config()["models"]
			modelVnum = models[0] if models else 0

		net.SendOfflineShopCreatePacket(self.title, modelVnum, SHOP_STYLE, listings)
		self.created = True
		self.Close()

	def OnOfflineShopResult(self, op, code, arg):
		"""GC RESULT of CREATE: its text (OK too), as the shop window shows the others."""
		if not offlineshopconst:
			return
		text = offlineshopconst.result_text(code, arg)
		if text:
			chat.AppendChat(chat.CHAT_TYPE_INFO, text)

	def OnClose(self):
		self.Close()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def IsOpen(self):
		return self.isOpen

	def OnOverInItem(self, slotIndex):

		if self.tooltipItem:
			if slotIndex in self.itemStock:
				self.tooltipItem.SetPrivateShopBuilderItem(*self.itemStock[slotIndex] + (slotIndex,))

	def OnOverOutItem(self):

		if self.tooltipItem:
			self.tooltipItem.HideToolTip()
