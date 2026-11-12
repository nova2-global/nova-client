import ui
import player
import mouseModule
import net
import app
import snd
import item
import player
import chat
import grp
import uiScriptLocale
import uiRefine
import uiAttachMetin
import uiPickMoney
import uiCommon
import uiPrivateShopBuilder # Prevent ItemMove while private shop is open
import localeInfo
import constInfo
import ime
import link_tokens
import wndMgr
import nui_windows

ITEM_FLAG_APPLICABLE = 1 << 14

# The sash's bonus scrolls (NOVA-20): an item whose value 0 is one of these
# takes the absorbed bonuses out of a sash (OLD's sash.CLEAN_ATTR_VALUE0 and
# sash.TAKE_ATTR_VALUE0, Packet.h SASH_CLEAN_ATTR_VALUE0 and
# SASH_TAKE_OUT_ATTR_VALUE0). Named here so that this module, which NovaUI's
# windows also run, needs no sash module.
SASH_CLEAN_ATTR_VALUE0 = 7
SASH_TAKE_ATTR_VALUE0 = 9

# The advanced pet's items (NOVA-24; contract 6, NEW's ItemData.h): their
# type and subtypes, the seal's summoned flag (socket 3) and the preview's
# inventory mode. Named here, as the sash's, so that this module, which
# NovaUI's windows and every test world also run, needs no pet module.
PET_ITEM_TYPE = 39
PET_EGG = 0
PET_SUMMON = 1
PET_NAME_CHANGE = 6
PET_DESTINY_ORB = 7
PET_SUMMONED_SOCKET = 3
PET_PREVIEW_INVENTORY = 3


def GetPetItemSubType(vnum):
	"""The advanced pet subtype of an item, or -1 for any other item."""
	item.SelectItem(vnum)
	if item.GetItemType() != PET_ITEM_TYPE:
		return -1
	return item.GetItemSubType()

# The money slot (uiscript Money_Slot: parameter_slot_05, 130 px, the text
# right-aligned 3 px from its right edge) holds a purse of up to 11 digits
# with its unit, "99.999.999.999 Yang" (120 px in Tahoma 12). 12 digits with
# the unit reach the slot's left edge and the cut's GOLD_MAX (2e12) runs 11 px
# past it, under the coin icon; from 12 digits the slot shows the amount alone
# (2.000.000.000.000 is 107 px), and the coin icon says it is yang.
MONEY_SLOT_UNIT_LIMIT = 10 ** 11


# The items that may sit in either inventory (NOVA-16, the server's
# IsExtraShared, spec 3.2): every costume, and the four scrolls of the
# special inventory's first category (71051, 71052, 71651, 71652). Ctrl +
# right-click moves them between the two.
EXTRA_SHARED_SCROLLS = (71051, 71052, 71651, 71652)
# The most treasure chests one Alt + right-click opens (NOVA-81; OLD's client
# cap, the server's GACHA_MULTI_OPEN_MAX in nova-protocol inventory_packets.h).
GACHA_MULTI_OPEN_MAX = 1000


def IsMultiOpenItem(itemVnum):
	"""A stack Alt + right-click opens several of (NOVA-81, default G-D2:
	the treasure chests, ITEM_GACHA, only)."""
	if not itemVnum:
		return False
	item.SelectItem(itemVnum)
	return item.GetItemType() == item.ITEM_TYPE_GACHA


def IsExtraSharedItem(itemVnum):
	if not itemVnum:
		return False
	if itemVnum in EXTRA_SHARED_SCROLLS:
		return True
	item.SelectItem(itemVnum)
	return item.GetItemType() == item.ITEM_TYPE_COSTUME


def SafeboxCheckinCell(itemVnum):
	"""The open safebox's cell for Shift + right-click (NOVA-16): the first
	cell from 0 where the item's cells are free and on one page. OLD's client
	sent cell 0 and OLD's server searched on from it (input_main.cpp:
	3015-3030, moving a tall item off a page's last rows); NEW's server
	refuses a taken cell, so the client searches. 0 when the item fits
	nowhere: the server then refuses it with OLD's message."""
	import safebox # the client's; imported here, as the item windows' stand-ins have none
	columns = safebox.SAFEBOX_SLOT_X_COUNT
	pageSize = safebox.SAFEBOX_PAGE_SIZE
	cellCount = safebox.GetCurrentSafeboxSize()

	taken = set()
	for cell in range(cellCount):
		vnum = safebox.GetItemID(cell)
		if vnum:
			item.SelectItem(vnum)
			for row in range(item.GetItemSize()[1]):
				taken.add(cell + row * columns)

	item.SelectItem(itemVnum)
	height = item.GetItemSize()[1]
	for cell in range(cellCount):
		last = cell + (height - 1) * columns
		if last >= cellCount or last // pageSize != cell // pageSize:
			continue
		if not taken.intersection(range(cell, last + 1, columns)):
			return cell
	return 0


# The server's ITEM_ANTIFLAG_SAFEBOX (OLD's, and ItemData.h's in NEW's client).
# OLD's item module exported it as ANTIFLAG_SAFEBOX (PythonItemModule.cpp:
# 1337-1338); NEW's does not yet, so OnTopAntiFlag falls back to the value.
ITEM_ANTIFLAG_SAFEBOX = 1 << 17


def OnTopAntiFlag(onTopWnd):
	"""The anti flag of the trade window on top (NOVA-13; OLD
	uiInventory.py:1326-1400): an item that has it cannot go there."""
	if onTopWnd == player.ON_TOP_WND_SHOP:
		return item.ANTIFLAG_SELL
	if onTopWnd == player.ON_TOP_WND_EXCHANGE:
		return item.ANTIFLAG_GIVE
	if onTopWnd == player.ON_TOP_WND_PRIVATE_SHOP:
		return item.ITEM_ANTIFLAG_MYSHOP
	if onTopWnd == player.ON_TOP_WND_SAFEBOX:
		flag = getattr(item, "ANTIFLAG_SAFEBOX", None)
		return flag if isinstance(flag, int) else ITEM_ANTIFLAG_SAFEBOX
	return 0


def SetSlotState(slotWindow, name, slotIndex):
	"""A tradable icon state of a slot window's cell (ui.SlotWindow's
	wrappers of wndMgr; a slot window without them shows none)."""
	setState = getattr(slotWindow, name, None)
	if setState:
		setState(slotIndex)


## NOVA-187: the NPC shop's sell marks (uiShop's store; a client without it has none).
def _SellMarks():
	try:
		import uiShop
	except ImportError:
		return None
	return uiShop if hasattr(uiShop, "ToggleSellMark") else None

def SellMarkColor(window, cell):
	"""The icon's diffuse color of (window, cell): OLD's mark gold while marked."""
	marks = _SellMarks()
	return marks.GetSellMarkColor(window, cell) if marks else (1.0, 1.0, 1.0, 1.0)

def IsSellMarked(window, cell):
	marks = _SellMarks()
	return bool(marks) and marks.IsSellMarked(window, cell)

def SellMarkPress(window, cell, refresh):
	"""A left press on the item at (window, cell), as the sell marks take it first: with the
	mark key down at an NPC shop and nothing attached, it marks or unmarks the item; on a marked
	item it does nothing more (no pick, no drop of what is attached, which goes back). True when
	the press is taken. Worn cells are never marked."""
	marks = _SellMarks()
	if not marks:
		return False
	if window == player.INVENTORY and (player.IsEquipmentSlot(cell) or player.IsCostumeSlot(cell)):
		return False
	attached = mouseModule.mouseController.isAttached()
	if not attached and marks.IsSellMarkKeyPressed():
		marks.ToggleSellMark(window, cell, refresh)
		return True
	if marks.IsSellMarked(window, cell):
		if attached:
			mouseModule.mouseController.DeattachObject()
		return True
	return False


def SellMarkCells(cells, window, position, refresh_board=False):
	"""NovaUI's grids: the cells with their "sell" key (NOVA-187), an item the NPC shop's sell
	marks hold, on its anchor (legacy tints the icon gold; the board draws the cell's mark).
	position(index) is the cell's item position in `window`. refresh_board: the cells were set
	anew from the items, so the shop's board shows the marks' current total."""
	marked = False
	for cell in cells:
		cell["sell"] = bool(cell["kind"] == "item" and not cell.get("covered")
		                    and IsSellMarked(window, position(cell["index"])))
		marked = marked or cell["sell"]
	if marked and refresh_board:
		marks = _SellMarks()
		if marks:
			marks.RefreshSellMarkBoard()
	return cells


def SendSplitAll(dlgPickMoney, window, cell, count):
	"""NOVA-190: a split accepted with "Split all" ticked (OLD uiInventory.py:
	1307-1315) cuts the stack at (window, cell) into piles of `count` on the
	server, all or none, instead of attaching `count`: True when it did. A
	count of the whole stack has nothing to split, so the pick attaches it as
	the plain split does."""
	isSplitAll = getattr(dlgPickMoney, "IsSplitAll", None)
	if not (isSplitAll and isSplitAll()):
		return False

	if window == player.INVENTORY:
		itemVnum, itemCount = player.GetItemIndex(cell), player.GetItemCount(cell)
	else:
		itemVnum, itemCount = player.GetItemIndex(window, cell), player.GetItemCount(window, cell)
	if count <= 0 or count >= itemCount:
		return False

	if uiPrivateShopBuilder.IsBuildingPrivateShop():
		chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.MOVE_ITEM_FAILURE_PRIVATE_SHOP)
		return True

	net.SendItemSplitPacket(window, cell, itemVnum, count)
	return True


def MoneySlotText(money):
	"""The money slot's text: localeInfo.NumberToMoneyString while the unit
	fits, then the amount with the same points and no unit."""
	if money < MONEY_SLOT_UNIT_LIMIT:
		return localeInfo.NumberToMoneyString(money)
	return "{:,}".format(money).replace(",", ".")


class CostumeWindow(ui.ScriptWindow):

	## The switches of OLD's costume window (__HIDE_COSTUME, NOVA-22; OLD
	## uiInventory.py:56-366): a toggle button per part, down while the part
	## shows, whose press asks the server to show or hide it
	## ("/set_is_show_costumes|hair|weapon|sash 0|1"); the server's
	## GC::SHOW_COSTUMES then holds the state (player.IsShow*), and its
	## ResetCostumeSlider command (a refusal while fighting) puts the buttons
	## back. OLD's sash switch sat in the inventory's equipment panel, beside
	## its sash slot; here both are in this window. A window whose loader makes
	## none of them (NovaUI's) has empty lists.
	costumeButtonList = ()
	hairButtonList = ()
	weaponButtonList = ()
	sashButtonList = ()
	## The aura's switches (NOVA-23): a toggle button opens a panel with a check
	## box per aura flag (OLD's "/aura_wing <flags>").
	wingButtonList = ()
	auraWingPanel = None
	auraWingChecks = ()

	def __init__(self, wndInventory):
		import exception
		
		if not app.ENABLE_COSTUME_SYSTEM:
			exception.Abort("What do you do?")
			return

		if not wndInventory:
			exception.Abort("wndInventory parameter must be set to InventoryWindow")
			return

		ui.ScriptWindow.__init__(self)

		self.isLoaded = 0
		self.wndInventory = wndInventory
		self.costumeButtonList = []
		self.hairButtonList = []
		self.weaponButtonList = []
		self.sashButtonList = []
		self.wingButtonList = []
		self.auraWingPanel = None
		self.auraWingChecks = []

		self.__LoadWindow()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def Show(self):
		self.__LoadWindow()
		self.ResetSlider()
		self.RefreshCostumeSlot()

		ui.ScriptWindow.Show(self)

	def Close(self):
		if self.auraWingPanel:
			self.auraWingPanel.Hide()
		for button in self.wingButtonList:
			button.SetUp()
		self.Hide()

	def __LoadWindow(self):
		if self.isLoaded == 1:
			return

		self.isLoaded = 1

		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/CostumeWindow.py")
		except:
			import exception
			exception.Abort("CostumeWindow.LoadWindow.LoadObject")

		try:
			GetObject = self.GetChild
			wndEquip = self.GetChild("CostumeSlot")
			self.GetChild("TitleBar").SetCloseEvent(ui.__mem_func__(self.Close))

			self.costumeButtonList.append(GetObject("Activate_ON_OFF"))
			self.hairButtonList.append(GetObject("Activate1_ON_OFF"))
			self.weaponButtonList.append(GetObject("Activate2_ON_OFF"))
			self.wingButtonList.append(GetObject("Activate3_ON_OFF"))
			self.sashButtonList.append(GetObject("Activate5_ON_OFF"))

		except:
			import exception
			exception.Abort("CostumeWindow.LoadWindow.BindObject")

		## Equipment
		wndEquip.SetOverInItemEvent(ui.__mem_func__(self.wndInventory.OverInItem))
		wndEquip.SetOverOutItemEvent(ui.__mem_func__(self.wndInventory.OverOutItem))
		wndEquip.SetUnselectItemSlotEvent(ui.__mem_func__(self.wndInventory.UseItemSlot))
		wndEquip.SetUseSlotEvent(ui.__mem_func__(self.wndInventory.UseItemSlot))						
		wndEquip.SetSelectEmptySlotEvent(ui.__mem_func__(self.wndInventory.SelectEmptySlot))
		wndEquip.SetSelectItemSlotEvent(ui.__mem_func__(self.wndInventory.SelectItemSlot))

		## ActivateButton
		for buttons, event in ((self.costumeButtonList, self.OnCostumeActivateButton),
				(self.hairButtonList, self.OnHairActivateButton),
				(self.weaponButtonList, self.OnWeaponActivateButton),
				(self.sashButtonList, self.OnSashActivateButton),
				(self.wingButtonList, self.__ToggleAuraWingPanel)):
			for button in buttons:
				button.SetToggleUpEvent(ui.__mem_func__(event))
				button.SetToggleDownEvent(ui.__mem_func__(event))

		self.wndEquip = wndEquip

	def RefreshCostumeSlot(self):
		getItemVNum=player.GetItemIndex

		## COSTUME_SLOT_COUNT runs from the costume body (wear 19) over OLD's
		## costume sash (21) and weapon costume (22), NOVA-20 and NOVA-21.
		for i in range(item.COSTUME_SLOT_COUNT):
			slotNumber = item.COSTUME_SLOT_START + i
			self.wndEquip.SetItemSlot(slotNumber, getItemVNum(slotNumber), 0)

		## The aura costume (NOVA-23; OLD uiInventory.py:210-223).
		slotNumber = CostumeAuraSlot()
		self.wndEquip.SetItemSlot(slotNumber, getItemVNum(slotNumber), 0)

		## The buffi's costumes (NOVA-38; OLD uiInventory.py:193-206), the
		## cells the window shows.
		for slotNumber in CostumeBuffiSlots():
			self.wndEquip.SetItemSlot(slotNumber, getItemVNum(slotNumber), 0)

		self.wndEquip.RefreshSlot()

	def __SetShown(self, buttons, isShown):
		for button in buttons:
			if isShown:
				button.Down()
			else:
				button.SetUp()

	def __AskShow(self, buttons, isShown, command):
		"""OLD's On*ActivateButton: the button shows the part's new state and
		the server is asked for it."""
		self.__SetShown(buttons, not isShown)
		net.SendChatPacket("/%s %d" % (command, 0 if isShown else 1))

	def OnCostumeActivateButton(self):
		self.__AskShow(self.costumeButtonList, player.IsShowCostumes(), "set_is_show_costumes")

	def OnHairActivateButton(self):
		self.__AskShow(self.hairButtonList, player.IsShowHair(), "set_is_show_hair")

	def OnWeaponActivateButton(self):
		self.__AskShow(self.weaponButtonList, player.IsShowWeapon(), "set_is_show_weapon")

	def OnSashActivateButton(self):
		self.__AskShow(self.sashButtonList, player.IsShowSash(), "set_is_show_sash")

	## The aura's flags (OLD uiInventory.py:254-329), each a check box: OLD's
	## wings, aura and aura wing effect, those the client's player module has.
	AURA_WING_FLAGS = (("AURA_WING_FLAG_WING", "AURA_WING_SHOW_WING"), ("AURA_WING_FLAG_AURA", "AURA_WING_SHOW_AURA"),
			("AURA_WING_FLAG_EFFECT", "AURA_WING_SHOW_EFFECT"))
	AURA_WING_PANEL_POSITION = (163, 143)

	def __ToggleAuraWingPanel(self):
		if self.auraWingPanel and self.auraWingPanel.IsShow():
			self.auraWingPanel.Hide()
			self.__SetShown(self.wingButtonList, False)
			return

		if not self.auraWingPanel:
			self.__CreateAuraWingPanel()

		self.__UpdateAuraWingCheckboxes(player.GetAuraWingFlags())

		self.auraWingPanel.SetPosition(*self.AURA_WING_PANEL_POSITION)
		self.auraWingPanel.Show()
		self.auraWingPanel.SetTop()
		self.__SetShown(self.wingButtonList, True)

	def __CreateAuraWingPanel(self):
		flags = [(getattr(player, flag), label) for (flag, label) in self.AURA_WING_FLAGS if hasattr(player, flag)]
		panel = ui.Board()
		panel.SetParent(self)
		panel.SetSize(150, 20 + 20 * len(flags))
		panel.AddFlag("float")
		panel.Show()

		checks = []
		for (index, (flag, label)) in enumerate(flags):
			checkBox = ui.CheckBox()
			checkBox.SetParent(panel)
			checkBox.SetPosition(15, 12 + 20 * index)
			checkBox.SetTextInfo(getattr(localeInfo, label))
			event = lambda flag=flag: self.__SendAuraWingToggle(flag)
			checkBox.SetEvent(event, "ON_CHECK")
			checkBox.SetEvent(event, "ON_UNCHECK")
			checkBox.Show()
			checks.append((flag, checkBox))

		self.auraWingChecks = checks
		self.auraWingPanel = panel

	def __SendAuraWingToggle(self, flag):
		flags = player.GetAuraWingFlags()
		flags ^= flag
		net.SendChatPacket("/aura_wing %d" % flags)

	def __UpdateAuraWingCheckboxes(self, flags):
		if not self.auraWingPanel:
			return
		for (flag, checkBox) in self.auraWingChecks:
			checkBox.SetCheckStatus(bool(flags & flag))

	def ResetSlider(self):
		self.__SetShown(self.costumeButtonList, player.IsShowCostumes())
		self.__SetShown(self.hairButtonList, player.IsShowHair())
		self.__SetShown(self.weaponButtonList, player.IsShowWeapon())
		self.__SetShown(self.sashButtonList, player.IsShowSash())
		self.__UpdateAuraWingCheckboxes(player.GetAuraWingFlags())


def IsSashBonusScroll(itemVnum):
	"""Whether an item takes the absorbed bonuses out of a sash (OLD's test of
	its value 0 against sash.CLEAN_ATTR_VALUE0 and sash.TAKE_ATTR_VALUE0)."""
	item.SelectItem(itemVnum)
	return item.GetValue(0) in (SASH_CLEAN_ATTR_VALUE0, SASH_TAKE_ATTR_VALUE0)


def CostumeAuraSlot():
	"""The aura costume's cell (wear 39): OLD's item.COSTUME_SLOT_AURA,
	c_Costume_Slot_Aura (GameType.h), counted from the costume body (wear 19)
	as the costume window's uiscript counts it."""
	return item.COSTUME_SLOT_START + 20


## The buffi's costume cells the costume window shows (NOVA-38): its costume
## body, hair and weapon costume, the first three of OLD's five (wear 31-33 of
## item.COSTUME_BUFFI_SLOT_START, OLD GameType.h:174-181). Its wings and facial
## (wear 34, 35) take NEW's unported sash2 and facial costumes.
BUFFI_COSTUME_SHOWN = 3


def CostumeBuffiSlots():
	"""The buffi's shown costume cells: item.COSTUME_BUFFI_SLOT_START (wear 31)
	onward, counted from the costume body (wear 19) as the costume window's
	uiscript counts it when the client lacks the name."""
	start = getattr(item, "COSTUME_BUFFI_SLOT_START", None)
	if not isinstance(start, int):
		start = item.COSTUME_SLOT_START + 12
	return list(range(start, start + BUFFI_COSTUME_SHOWN))


def IsFakeBuffIntBoost(itemVnum):
	"""Whether an item raises a buffi's INT (OLD's item.IsFakeBuffIntBoost,
	ITEM_FAKE_BUFF_INT_BOOST); an exe without it has none."""
	isIntBoost = getattr(item, "IsFakeBuffIntBoost", None)
	return bool(isIntBoost(itemVnum)) if isIntBoost else False


class BeltInventoryWindow(ui.ScriptWindow):

	def __init__(self, wndInventory):
		import exception
		
		if not app.ENABLE_NEW_EQUIPMENT_SYSTEM:			
			exception.Abort("What do you do?")
			return

		if not wndInventory:
			exception.Abort("wndInventory parameter must be set to InventoryWindow")
			return						
			 	 
		ui.ScriptWindow.__init__(self)

		self.AddFlag("float")

		self.isLoaded = 0
		self.wndInventory = wndInventory
		
		self.wndBeltInventoryLayer = None
		self.wndBeltInventorySlot = None
		self.expandBtn = None
		self.minBtn = None

		self.__LoadWindow()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def Show(self, openBeltSlot = False):
		self.__LoadWindow()
		self.RefreshSlot()

		ui.ScriptWindow.Show(self)
		
		if openBeltSlot:
			self.OpenInventory()
		else:
			self.CloseInventory()

	def Close(self):
		self.Hide()

	def IsOpeningInventory(self):
		return self.wndBeltInventoryLayer.IsShow()
		
	def OpenInventory(self):
		self.wndBeltInventoryLayer.Show()
		self.expandBtn.Hide()

		if app.IsRTL() == 0:
			self.AdjustPositionAndSize()

	def CloseInventory(self):
		self.wndBeltInventoryLayer.Hide()
		self.expandBtn.Show()

		if app.IsRTL() == 0:
			self.AdjustPositionAndSize()

	## Calculate and return BASE position based on current inventory position. Hard-coded numbers are unavoidable.
	def GetBasePosition(self):
		x, y = self.wndInventory.GetGlobalPosition()
		return x - 148, y + 241
		
	def AdjustPositionAndSize(self):
		bx, by = self.GetBasePosition()
		
		if self.IsOpeningInventory():			
			self.SetPosition(bx, by)
			self.SetSize(self.ORIGINAL_WIDTH, self.GetHeight())
			
		else:
			self.SetPosition(bx + 138, by)
			self.SetSize(10, self.GetHeight())

	def __LoadWindow(self):
		if self.isLoaded == 1:
			return

		self.isLoaded = 1

		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/BeltInventoryWindow.py")
		except:
			import exception
			exception.Abort("CostumeWindow.LoadWindow.LoadObject")

		try:
			self.ORIGINAL_WIDTH = self.GetWidth()
			wndBeltInventorySlot = self.GetChild("BeltInventorySlot")
			self.wndBeltInventoryLayer = self.GetChild("BeltInventoryLayer")
			self.expandBtn = self.GetChild("ExpandBtn")
			self.minBtn = self.GetChild("MinimizeBtn")
			
			self.expandBtn.SetEvent(ui.__mem_func__(self.OpenInventory))
			self.minBtn.SetEvent(ui.__mem_func__(self.CloseInventory))

			if app.IsRTL() :
				self.expandBtn.SetPosition(self.expandBtn.GetWidth() - 2, 15)
				self.wndBeltInventoryLayer.SetPosition(self.wndBeltInventoryLayer.GetWidth() - 5, 0)
				self.minBtn.SetPosition(self.minBtn.GetWidth() + 3, 15)

			for i in range(item.BELT_INVENTORY_SLOT_COUNT):
				slotNumber = item.BELT_INVENTORY_SLOT_START + i
				wndBeltInventorySlot.SetCoverButton(slotNumber,	"d:/ymir work/ui/game/quest/slot_button_01.sub",\
											"d:/ymir work/ui/game/quest/slot_button_01.sub",\
											"d:/ymir work/ui/game/quest/slot_button_01.sub",\
											"d:/ymir work/ui/game/belt_inventory/slot_disabled.tga", False, False)
			
		except:
			import exception
			exception.Abort("CostumeWindow.LoadWindow.BindObject")

		## Equipment
		wndBeltInventorySlot.SetOverInItemEvent(ui.__mem_func__(self.wndInventory.OverInItem))
		wndBeltInventorySlot.SetOverOutItemEvent(ui.__mem_func__(self.wndInventory.OverOutItem))
		wndBeltInventorySlot.SetUnselectItemSlotEvent(ui.__mem_func__(self.wndInventory.UseItemSlot))
		wndBeltInventorySlot.SetUseSlotEvent(ui.__mem_func__(self.wndInventory.UseItemSlot))						
		wndBeltInventorySlot.SetSelectEmptySlotEvent(ui.__mem_func__(self.wndInventory.SelectEmptySlot))
		wndBeltInventorySlot.SetSelectItemSlotEvent(ui.__mem_func__(self.wndInventory.SelectItemSlot))

		self.wndBeltInventorySlot = wndBeltInventorySlot

	def RefreshSlot(self):
		getItemVNum=player.GetItemIndex
		
		for i in range(item.BELT_INVENTORY_SLOT_COUNT):
			slotNumber = item.BELT_INVENTORY_SLOT_START + i
			self.wndBeltInventorySlot.SetItemSlot(slotNumber, getItemVNum(slotNumber), player.GetItemCount(slotNumber))
			self.wndBeltInventorySlot.SetAlwaysRenderCoverButton(slotNumber, True)
			
			avail = "0"
			
			if player.IsAvailableBeltInventoryCell(slotNumber):
				self.wndBeltInventorySlot.EnableCoverButton(slotNumber)				
			else:
				self.wndBeltInventorySlot.DisableCoverButton(slotNumber)				

		self.wndBeltInventorySlot.RefreshSlot()

		
class InventoryWindow(ui.ScriptWindow):

	USE_TYPE_TUPLE = ("USE_CLEAN_SOCKET", "USE_CHANGE_ATTRIBUTE", "USE_ADD_ATTRIBUTE", "USE_ADD_ATTRIBUTE2", "USE_ADD_ACCESSORY_SOCKET", "USE_PUT_INTO_ACCESSORY_SOCKET", "USE_PUT_INTO_BELT_SOCKET", "USE_PUT_INTO_RING_SOCKET")

	questionDialog = None
	tooltipItem = None
	wndCostume = None
	wndBelt = None
	dlgPickMoney = None
	# The gaya balance under the yang (NOVA-10); None until the legacy loader
	# binds it, and in a loader that has none (NovaUI's).
	wndGem = None
	# The offline shop's and the search's buttons (NOVA-9), the same way, and
	# whether the server's offline shop is on (CONFIG's "enabled", through
	# Interface.OnOfflineShopConfig): until then neither button shows and
	# Ctrl + click adds a quick slot, as before.
	offlineShopButton = None
	searchShopButton = None
	offlineShopEnabled = False
	# The sash windows (NOVA-20) and the aura window (NOVA-23), set by the
	# Interface and the game window once they exist.
	wndSashCombine = None
	wndSashAbsorption = None
	wndAura = None
	
	sellingSlotNumber = -1
	isLoaded = 0
	isOpenedCostumeWindowWhenClosingInventory = 0		# Whether costume window was open when closing inventory
	isOpenedBeltWindowWhenClosingInventory = 0		# Whether belt inventory was open when closing inventory

	def __init__(self):
		ui.ScriptWindow.__init__(self)

		self.isOpenedBeltWindowWhenClosingInventory = 0		# Whether belt inventory was open when closing inventory
		# The windows whose items lock cells here (the tradable icon, NOVA-13).
		self.bindWnds = []

		self.__LoadWindow()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def Show(self):
		self.__LoadWindow()

		ui.ScriptWindow.Show(self)

		# If costume window was open when closing inventory, open it again when opening inventory.
		if self.isOpenedCostumeWindowWhenClosingInventory and self.wndCostume:
			self.wndCostume.Show() 

		# If belt inventory was open when closing inventory, open it again.
		if self.wndBelt:
			self.wndBelt.Show(self.isOpenedBeltWindowWhenClosingInventory)

	def BindInterfaceClass(self, interface):
		self.interface = interface
		
	def __LoadWindow(self):
		if self.isLoaded == 1:
			return

		self.isLoaded = 1

		try:
			pyScrLoader = ui.PythonScriptLoader()

			if app.IsRTL():
				pyScrLoader.LoadScriptFile(self, uiScriptLocale.LOCALE_UISCRIPT_PATH + "InventoryWindow.py")
			else:
				pyScrLoader.LoadScriptFile(self, "UIScript/InventoryWindow.py")
		except:
			import exception
			exception.Abort("InventoryWindow.LoadWindow.LoadObject")

		try:
			wndItem = self.GetChild("ItemSlot")
			wndEquip = self.GetChild("EquipmentSlot")
			self.GetChild("TitleBar").SetCloseEvent(ui.__mem_func__(self.Close))
			self.wndMoney = self.GetChild("Money")
			self.wndMoneySlot = self.GetChild("Money_Slot")
			# The gaya balance (NOVA-10); an older uiscript has none.
			self.wndGem = self.GetChild2("Gem")
			# The offline shop and its search (NOVA-9); an older uiscript has none.
			self.offlineShopButton = self.GetChild2("OfflineShopButton")
			self.searchShopButton = self.GetChild2("SearchShopButton")
			self.mallButton = self.GetChild2("MallButton")
			self.DSSButton = self.GetChild2("DSSButton")
			self.costumeButton = self.GetChild2("CostumeButton")
			# The special inventory (NOVA-16); an older uiscript has no button.
			self.extraInventoryButton = self.GetChild2("ExtraInventoryButton")
			self.fastEquipButton = self.GetChild2("FastEquipButton")
			# The kill ranking (NOVA-29), OLD's extra inventory button; an older
			# uiscript has none.
			self.rankingButton = self.GetChild2("RankingButton")

			# One tab per inventory page (OLD uiInventory.py:884-889: five).
			self.inventoryTab = []
			for page in range(player.INVENTORY_PAGE_COUNT):
				self.inventoryTab.append(self.GetChild("Inventory_Tab_%02d" % (page + 1)))

			self.equipmentTab = []
			self.equipmentTab.append(self.GetChild("Equipment_Tab_01"))
			self.equipmentTab.append(self.GetChild("Equipment_Tab_02"))

			if self.costumeButton and not app.ENABLE_COSTUME_SYSTEM:
				self.costumeButton.Hide()
				self.costumeButton.Destroy()
				self.costumeButton = 0

			# Belt Inventory Window
			self.wndBelt = None
			
			if app.ENABLE_NEW_EQUIPMENT_SYSTEM:
				self.wndBelt = BeltInventoryWindow(self)
			
		except:
			import exception
			exception.Abort("InventoryWindow.LoadWindow.BindObject")

		## Item
		wndItem.SetSelectEmptySlotEvent(ui.__mem_func__(self.SelectEmptySlot))
		wndItem.SetSelectItemSlotEvent(ui.__mem_func__(self.SelectItemSlot))
		wndItem.SetUnselectItemSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndItem.SetUseSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndItem.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		wndItem.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))

		## Equipment
		wndEquip.SetSelectEmptySlotEvent(ui.__mem_func__(self.SelectEmptySlot))
		wndEquip.SetSelectItemSlotEvent(ui.__mem_func__(self.SelectItemSlot))
		wndEquip.SetUnselectItemSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndEquip.SetUseSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndEquip.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		wndEquip.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))

		## PickMoneyDialog
		dlgPickMoney = uiPickMoney.PickMoneyDialog()
		dlgPickMoney.LoadDialog()
		dlgPickMoney.Hide()

		## RefineDialog
		self.refineDialog = nui_windows.make("refine", uiRefine.RefineDialog, "nui_refine.RefineDialog")
		self.refineDialog.Hide()

		## AttachMetinDialog
		self.attachMetinDialog = nui_windows.make("attach-metin", uiAttachMetin.AttachMetinDialog, "nui_attach_metin.AttachMetinDialog")
		self.attachMetinDialog.Hide()

		## MoneySlot
		self.wndMoneySlot.SetEvent(ui.__mem_func__(self.OpenPickMoneyDialog))

		for page, tab in enumerate(self.inventoryTab):
			tab.SetEvent(lambda arg=page: self.SetInventoryPage(arg))
		self.inventoryTab[0].Down()

		self.equipmentTab[0].SetEvent(lambda arg=0: self.SetEquipmentPage(arg))
		self.equipmentTab[1].SetEvent(lambda arg=1: self.SetEquipmentPage(arg))
		self.equipmentTab[0].Down()
		self.equipmentTab[0].Hide()
		self.equipmentTab[1].Hide()

		self.wndItem = wndItem
		self.wndEquip = wndEquip
		self.dlgPickMoney = dlgPickMoney

		# MallButton
		if self.mallButton:
			self.mallButton.SetEvent(ui.__mem_func__(self.ClickMallButton))

		if self.DSSButton:
			self.DSSButton.SetEvent(ui.__mem_func__(self.ClickDSSButton)) 
		
		# Costume Button
		if self.costumeButton:
			self.costumeButton.SetEvent(ui.__mem_func__(self.ClickCostumeButton))

		if self.extraInventoryButton:
			self.extraInventoryButton.SetEvent(ui.__mem_func__(self.ClickExtraInventoryButton))

		if self.fastEquipButton:
			self.fastEquipButton.SetEvent(ui.__mem_func__(self.ClickFastEquipButton))

		if self.rankingButton:
			self.rankingButton.SetEvent(ui.__mem_func__(self.ClickRankingButton))

		if self.offlineShopButton:
			self.offlineShopButton.SetEvent(ui.__mem_func__(self.ClickOfflineShopButton))

		if self.searchShopButton:
			self.searchShopButton.SetEvent(ui.__mem_func__(self.ClickSearchShopButton))

		self.ShowOfflineShopButtons(self.offlineShopEnabled)

		self.wndCostume = None
		
 		#####

		## Refresh
		self.SetInventoryPage(0)
		self.SetEquipmentPage(0)
		self.RefreshItemSlot()
		self.RefreshStatus()

	def Destroy(self):
		self.ClearDictionary()

		self.dlgPickMoney.Destroy()
		self.dlgPickMoney = 0

		self.refineDialog.Destroy()
		self.refineDialog = 0

		self.attachMetinDialog.Destroy()
		self.attachMetinDialog = 0

		self.tooltipItem = None
		self.wndItem = 0
		self.wndEquip = 0
		self.dlgPickMoney = 0
		self.wndMoney = 0
		self.wndMoneySlot = 0
		self.wndGem = None
		self.offlineShopButton = None
		self.searchShopButton = None
		self.questionDialog = None
		self.mallButton = None
		self.DSSButton = None
		self.extraInventoryButton = None
		self.fastEquipButton = None
		self.rankingButton = None
		self.DSSButtonEffect = None
		self.interface = None

		if self.wndCostume:
			self.wndCostume.Destroy()
			self.wndCostume = 0
			
		if self.wndBelt:
			self.wndBelt.Destroy()
			self.wndBelt = None
			
		self.inventoryTab = []
		self.equipmentTab = []

	def Hide(self):
		if constInfo.GET_ITEM_QUESTION_DIALOG_STATUS():
			self.OnCloseQuestionDialog()
			return
		if None != self.tooltipItem:
			self.tooltipItem.HideToolTip()

		if self.wndCostume:
			self.isOpenedCostumeWindowWhenClosingInventory = self.wndCostume.IsShow()			# Was costume window open when inventory was closed?
			self.wndCostume.Close()
 
		if self.wndBelt:
			self.isOpenedBeltWindowWhenClosingInventory = self.wndBelt.IsOpeningInventory()		# Was belt inventory open when inventory was closed?
			print(("Is Opening Belt Inven?? ", self.isOpenedBeltWindowWhenClosingInventory))
			self.wndBelt.Close()
  
		if self.dlgPickMoney:
			self.dlgPickMoney.Close()
		
		wndMgr.Hide(self.hWnd)
		
	
	def Close(self):
		self.Hide()

	def SetInventoryPage(self, page):
		self.inventoryPageIndex = page
		# The page's tab is down and every other tab up (the two-tab rule
		# "1 - page" cannot hold five pages).
		for index, tab in enumerate(self.inventoryTab):
			if index != page:
				tab.SetUp()
		self.RefreshBagSlotWindow()

	def SetEquipmentPage(self, page):
		self.equipmentPageIndex = page
		self.equipmentTab[1-page].SetUp()
		self.RefreshEquipSlotWindow()

	def ClickMallButton(self):
		self.OpenStorageChoice()

	## NOVA-201: the mall button opens the storage choice (OLD uiInventory.py:
	## 1230-1277): a small board with Item Mall (/click_mall) and Safebox
	## (/click_safebox: the server opens the safebox where the player stands,
	## after its password). A second press closes it. The NovaUI inventory
	## shows the dialog kit's three-button question instead.
	storageChoice = None
	storageMallButton = None
	storageSafeboxButton = None

	def OpenStorageChoice(self):
		if self.storageChoice and self.storageChoice.IsShow():
			self.storageChoice.Hide()
			return

		if not self.storageChoice:
			self.__MakeStorageChoice()

		self.storageChoice.SetCenterPosition()
		self.storageChoice.SetTop()
		self.storageChoice.Show()

	def __MakeStorageChoice(self):
		board = ui.BoardWithTitleBar()
		board.SetSize(210, 80)
		board.AddFlag("float")
		board.AddFlag("movable")
		board.SetTitleName(uiScriptLocale.STORAGE_TITLE)
		board.SetCloseEvent(ui.__mem_func__(board.Hide))

		mallButton = self.__MakeStorageButton(board, uiScriptLocale.SYSTEM_MALL, self.OpenItemMall)
		mallButton.SetPosition(30, 45)
		safeboxButton = self.__MakeStorageButton(board, uiScriptLocale.SAFE_TITLE, self.OpenSafeboxAnywhere)
		safeboxButton.SetPosition(119, 45)

		self.storageChoice = board
		self.storageMallButton = mallButton
		self.storageSafeboxButton = safeboxButton

	def __MakeStorageButton(self, board, text, event):
		button = ui.Button()
		button.SetParent(board)
		button.SetUpVisual("d:/ymir work/ui/public/middle_button_01.sub")
		button.SetOverVisual("d:/ymir work/ui/public/middle_button_02.sub")
		button.SetDownVisual("d:/ymir work/ui/public/middle_button_03.sub")
		button.SetText(text)
		button.SetEvent(ui.__mem_func__(event))
		button.Show()
		return button

	def CloseStorageChoice(self):
		if self.storageChoice:
			self.storageChoice.Hide()

	def OpenItemMall(self):
		self.CloseStorageChoice()
		net.SendChatPacket("/click_mall")

	def OpenSafeboxAnywhere(self):
		self.CloseStorageChoice()
		net.SendChatPacket("/click_safebox")

	# DSSButton
	def ClickDSSButton(self):
		print("click_dss_button")
		self.interface.ToggleDragonSoulWindow()

	def ClickFastEquipButton(self):
		"""Fast equip (NOVA-17; OLD uiInventory.py:1176)."""
		self.interface.ToggleFastEquipWindow()

	def ClickExtraInventoryButton(self):
		self.interface.ToggleExtraInventoryWindow()

	## The offline shop (NOVA-9; OLD uiInventory.py:482-501, the special
	## inventory's side bar there): MANAGE answers with the owner's panel, or
	## opens the builder when the player has no shop.
	# The kill ranking (NOVA-29): OLD's OpenRanking and OpenKillRank
	# (uiInventory.py:491-493, 1178-1179).
	def ClickRankingButton(self):
		if self.interface:
			self.interface.OpenKillRank()

	def ClickOfflineShopButton(self):
		net.SendOfflineShopManagePacket()

	def ClickSearchShopButton(self):
		self.interface.OpenSearchShop()

	def ShowOfflineShopButtons(self, enabled):
		self.offlineShopEnabled = bool(enabled)
		for button in (self.offlineShopButton, self.searchShopButton):
			if not button:
				continue
			if self.offlineShopEnabled:
				button.Show()
			else:
				button.Hide()

	def UseDSSButtonEffect(self, enable):
		if self.DSSButton:
			DSSButtonEffect = ui.SlotWindow()
			DSSButtonEffect.AddFlag("attach")
			DSSButtonEffect.SetParent(self.DSSButton)
			DSSButtonEffect.SetPosition(3.2, 0)

			DSSButtonEffect.AppendSlot(0, 0, 0, 32, 32)
			DSSButtonEffect.SetRenderSlot(0)
			DSSButtonEffect.RefreshSlot()

			if enable == True:
				DSSButtonEffect.ActivateSlot(0)
				DSSButtonEffect.Show()
			else:
				DSSButtonEffect.DeactivateSlot(0)
				DSSButtonEffect.Hide()
			self.DSSButtonEffect = DSSButtonEffect

	def ClickCostumeButton(self):
		print("Click Costume Button")
		if self.wndCostume:
			if self.wndCostume.IsShow(): 
				self.wndCostume.Hide()
			else:
				self.wndCostume.Show()
		else:
			self.wndCostume = CostumeWindow(self)
			self.wndCostume.Show()

	def OpenPickMoneyDialog(self):

		if mouseModule.mouseController.isAttached():

			attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
			if player.SLOT_TYPE_SAFEBOX == mouseModule.mouseController.GetAttachedType():

				if player.ITEM_MONEY == mouseModule.mouseController.GetAttachedItemIndex():
					net.SendSafeboxWithdrawMoneyPacket(mouseModule.mouseController.GetAttachedItemCount())
					snd.PlaySound("sound/ui/money.wav")

			mouseModule.mouseController.DeattachObject()

		else:
			curMoney = player.GetElk()

			if curMoney <= 0:
				return

			self.dlgPickMoney.SetTitleName(localeInfo.PICK_MONEY_TITLE)
			self.dlgPickMoney.SetAcceptEvent(ui.__mem_func__(self.OnPickMoney))
			self.dlgPickMoney.Open(curMoney)
			# Fixed inventory 990000 limit bug; OLD keeps 7 digits here (OLD uiInventory.py:1302;
			# Q13: decided 2026-10-25).
			self.dlgPickMoney.SetMax(player.INVENTORY_MONEY_DIGITS)

	def OnPickMoney(self, money):
		mouseModule.mouseController.AttachMoney(self, player.SLOT_TYPE_INVENTORY, money)

	def OnPickItem(self, count):
		itemSlotIndex = self.dlgPickMoney.itemGlobalSlotIndex
		if SendSplitAll(self.dlgPickMoney, player.INVENTORY, itemSlotIndex, count):
			return
		selectedItemVNum = player.GetItemIndex(itemSlotIndex)
		mouseModule.mouseController.AttachObject(self, player.SLOT_TYPE_INVENTORY, itemSlotIndex, selectedItemVNum, count)

	def __InventoryLocalSlotPosToGlobalSlotPos(self, local):
		if player.IsEquipmentSlot(local) or player.IsCostumeSlot(local) or (app.ENABLE_NEW_EQUIPMENT_SYSTEM and player.IsBeltInventorySlot(local)):
			return local

		return self.inventoryPageIndex*player.INVENTORY_PAGE_SIZE + local

	def RefreshBagSlotWindow(self):
		getItemVNum=player.GetItemIndex
		getItemCount=player.GetItemCount
		setItemVNum=self.wndItem.SetItemSlot
		
		for i in range(player.INVENTORY_PAGE_SIZE):
			slotNumber = self.__InventoryLocalSlotPosToGlobalSlotPos(i)
			
			itemCount = getItemCount(slotNumber)
			# If itemCount == 0, clear the slot.
			if 0 == itemCount:
				self.wndItem.ClearSlot(i)
				continue
			elif 1 == itemCount:
				itemCount = 0
				
			itemVnum = getItemVNum(slotNumber)
			setItemVNum(i, itemVnum, itemCount, SellMarkColor(player.INVENTORY, slotNumber))
			
			## Auto-potion special handling (HP: #72723~#72726, SP: #72727~#72730) - Display activation/deactivation in slot even though it's an item - [hyo]
			if constInfo.IS_AUTO_POTION(itemVnum):
				# metinSocket - [0]: Activation status, [1]: Amount used, [2]: Maximum capacity
				metinSocket = [player.GetItemMetinSocket(slotNumber, j) for j in range(player.METIN_SOCKET_MAX_NUM)]	
				
				if slotNumber >= player.INVENTORY_PAGE_SIZE * self.inventoryPageIndex:
					slotNumber -= player.INVENTORY_PAGE_SIZE * self.inventoryPageIndex
					
				isActivated = 0 != metinSocket[0]
				
				if isActivated:
					self.wndItem.ActivateSlot(slotNumber)
					potionType = 0
					if constInfo.IS_AUTO_POTION_HP(itemVnum):
						potionType = player.AUTO_POTION_TYPE_HP
					elif constInfo.IS_AUTO_POTION_SP(itemVnum):
						potionType = player.AUTO_POTION_TYPE_SP						
					
					usedAmount = int(metinSocket[1])
					totalAmount = int(metinSocket[2])					
					player.SetAutoPotionInfo(potionType, isActivated, (totalAmount - usedAmount), totalAmount, self.__InventoryLocalSlotPosToGlobalSlotPos(i))
					
				else:
					self.wndItem.DeactivateSlot(slotNumber)			

			## A summoned pet's seal glows (NOVA-24; OLD uiInventory.py:1469-1473:
			## socket 3 is set while it is out). OLD tinted the cell; NEW's slot
			## window activates it, as an active auto potion.
			elif GetPetItemSubType(itemVnum) == PET_SUMMON:
				if player.GetItemMetinSocket(slotNumber, PET_SUMMONED_SOCKET) != 0:
					self.wndItem.ActivateSlot(i)
				else:
					self.wndItem.DeactivateSlot(i)

			## A buffi item is active while its buffi is out (NOVA-38; OLD
			## uiInventory.py:1476-1479: the server sets its socket 3).
			elif constInfo.IS_FAKEBUFF_ITEM(itemVnum):
				if player.METIN_SOCKET_MAX_NUM > 3 and 0 != player.GetItemMetinSocket(slotNumber, 3):
					self.wndItem.ActivateSlot(i)
				else:
					self.wndItem.DeactivateSlot(i)
					
		self.RefreshMarkSlots()
		self.wndItem.RefreshSlot()

		if self.wndBelt:
			self.wndBelt.RefreshSlot()

		## The page's cells were set anew: the trade windows lock theirs again.
		self.RefreshLockedSlots()

	def RefreshEquipSlotWindow(self):
		getItemVNum=player.GetItemIndex
		getItemCount=player.GetItemCount
		setItemVNum=self.wndEquip.SetItemSlot
		for i in range(player.EQUIPMENT_PAGE_COUNT):
			slotNumber = player.EQUIPMENT_SLOT_START + i
			itemCount = getItemCount(slotNumber)
			if itemCount <= 1:
				itemCount = 0
			setItemVNum(slotNumber, getItemVNum(slotNumber), itemCount)

		if app.ENABLE_NEW_EQUIPMENT_SYSTEM:
			for i in range(player.NEW_EQUIPMENT_SLOT_COUNT):
				slotNumber = player.NEW_EQUIPMENT_SLOT_START + i
				itemCount = getItemCount(slotNumber)
				if itemCount <= 1:
					itemCount = 0
				setItemVNum(slotNumber, getItemVNum(slotNumber), itemCount)
				print(("ENABLE_NEW_EQUIPMENT_SYSTEM", slotNumber, itemCount, getItemVNum(slotNumber)))
				


		self.wndEquip.RefreshSlot()
		
		if self.wndCostume:
			self.wndCostume.RefreshCostumeSlot()

	def RefreshItemSlot(self):
		self.RefreshBagSlotWindow()
		self.RefreshEquipSlotWindow()

	def RefreshStatus(self):
		money = player.GetElk()
		self.wndMoney.SetText(MoneySlotText(money))

		## The gaya balance (NOVA-10: point 163, player.GetGem; at most
		## 999,999), dotted as the yang is and without a unit.
		if self.wndGem:
			self.wndGem.SetText("{:,}".format(player.GetGem()).replace(",", "."))

	def SetItemToolTip(self, tooltipItem):
		self.tooltipItem = tooltipItem

	## The tradable icon (NOVA-13; OLD uiInventory.py:1326-1400, the item lock
	## branch left out): a window that holds an item of a bag cell locks the
	## cell (no mouse event, a red cover) while the item sits there, and the
	## trade window on top marks the cells whose items it refuses (a white
	## cover). A cell is locked by its global number; only the visible page's
	## cells show it, and a page change locks them again.
	def BindWindow(self, wnd):
		if wnd not in self.bindWnds:
			self.bindWnds.append(wnd)

	def GetInventoryPageIndex(self):
		return self.inventoryPageIndex

	def GetLocalSlotPos(self, globalSlotPos):
		"""The visible page's cell of a bag cell, or None."""
		first = self.inventoryPageIndex * player.INVENTORY_PAGE_SIZE
		if first <= globalSlotPos < first + player.INVENTORY_PAGE_SIZE:
			return globalSlotPos - first
		return None

	def SetCantMouseEventCell(self, globalSlotPos):
		localSlotPos = self.GetLocalSlotPos(globalSlotPos)
		if localSlotPos is not None:
			SetSlotState(self.wndItem, "SetCantMouseEventSlot", localSlotPos)

	def SetCanMouseEventCell(self, globalSlotPos):
		localSlotPos = self.GetLocalSlotPos(globalSlotPos)
		if localSlotPos is not None:
			SetSlotState(self.wndItem, "SetCanMouseEventSlot", localSlotPos)

	def RefreshLockedSlots(self):
		for wnd in list(self.bindWnds):
			if wnd.IsShow():
				wnd.RefreshLockedSlot()

	def GetOnTopWindow(self):
		interface = getattr(self, "interface", None)
		getOnTopWindow = getattr(interface, "GetOnTopWindow", None)
		if getOnTopWindow:
			return getOnTopWindow()
		return player.ON_TOP_WND_NONE

	def RefreshMarkSlots(self, localIndex=None):
		## OLD's "if localIndex:" took cell 0 for the whole page.
		onTopWnd = self.GetOnTopWindow()
		if localIndex is not None:
			localIndices = (localIndex,)
		else:
			localIndices = range(player.INVENTORY_PAGE_SIZE)

		antiFlag = OnTopAntiFlag(onTopWnd)
		for localSlotPos in localIndices:
			globalSlotPos = self.__InventoryLocalSlotPosToGlobalSlotPos(localSlotPos)
			if antiFlag and player.IsAntiFlagBySlot(player.INVENTORY, globalSlotPos, antiFlag):
				SetSlotState(self.wndItem, "SetUnusableSlotOnTopWnd", localSlotPos)
			else:
				SetSlotState(self.wndItem, "SetUsableSlotOnTopWnd", localSlotPos)

	def SellItem(self):
		if self.sellingSlotitemIndex == player.GetItemIndex(self.sellingSlotNumber):
			if self.sellingSlotitemCount == player.GetItemCount(self.sellingSlotNumber):
				## Added type argument to enable selling dragon soul stones
				net.SendShopSellPacketNew(self.sellingSlotNumber, self.questionDialog.count, player.INVENTORY)
				snd.PlaySound("sound/ui/money.wav")
		self.OnCloseQuestionDialog()

	def OnDetachMetinFromItem(self):
		if None == self.questionDialog:
			return
			
		#net.SendItemUseToItemPacket(self.questionDialog.sourcePos, self.questionDialog.targetPos)		
		self.__SendUseItemToItemPacket(self.questionDialog.sourcePos, self.questionDialog.targetPos)
		self.OnCloseQuestionDialog()

	## OLD uiInventory.py:2329-2358 (NOVA-24): the destiny orb maxes a pet and
	## adds a permanent -100% against monsters to its seal (attribute 0), so
	## it asks first. OLD bug 10: OLD's test let any pet item or an egg
	## through; only a seal takes the orb.
	def __CanUsePetItemToDstItem(self, scrollSlotPos, targetSlotPos):
		if GetPetItemSubType(player.GetItemIndex(targetSlotPos)) != PET_SUMMON:
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.PET_ADVANCED_ORB_ALERT)
			return

		if player.GetItemAttribute(targetSlotPos, 0)[0] != 0:
			popup = uiCommon.PopupDialog()
			popup.SetText(localeInfo.PET_ADVANCED_ORB_ALREADY_USED)
			popup.Open()
			self.popup = popup
			return

		item.SelectItem(player.GetItemIndex(targetSlotPos))
		self.questionDialog = uiCommon.QuestionDialog()
		self.questionDialog.SetText(localeInfo.PET_ADVANCED_ORB_WARNING % item.GetItemName())
		self.questionDialog.SetAcceptEvent(ui.__mem_func__(self.OnAcceptPetOrbItem))
		self.questionDialog.SetCancelEvent(ui.__mem_func__(self.OnCloseQuestionDialog))
		self.questionDialog.Open()
		self.questionDialog.sourcePos = scrollSlotPos
		self.questionDialog.targetPos = targetSlotPos

	def OnAcceptPetOrbItem(self):
		if self.questionDialog == None:
			return

		self.__SendUseItemToItemPacket(self.questionDialog.sourcePos, self.questionDialog.targetPos)
		self.OnCloseQuestionDialog()

	def OnCloseQuestionDialog(self):
		if not self.questionDialog:
			return
		
		self.questionDialog.Close()
		self.questionDialog = None
		constInfo.SET_ITEM_QUESTION_DIALOG_STATUS(0)

	## Slot Event
	def SelectEmptySlot(self, selectedSlotPos):
		if constInfo.GET_ITEM_QUESTION_DIALOG_STATUS() == 1:
			return

		selectedSlotPos = self.__InventoryLocalSlotPosToGlobalSlotPos(selectedSlotPos)

		if mouseModule.mouseController.isAttached():

			attachedSlotType = mouseModule.mouseController.GetAttachedType()
			attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
			attachedItemCount = mouseModule.mouseController.GetAttachedItemCount()
			attachedItemIndex = mouseModule.mouseController.GetAttachedItemIndex()

			if player.SLOT_TYPE_INVENTORY == attachedSlotType:
				itemCount = player.GetItemCount(attachedSlotPos)
				attachedCount = mouseModule.mouseController.GetAttachedItemCount()
				self.__SendMoveItemPacket(attachedSlotPos, selectedSlotPos, attachedCount)

				if item.IsRefineScroll(attachedItemIndex):
					self.wndItem.SetUseMode(False)

			elif player.SLOT_TYPE_PRIVATE_SHOP == attachedSlotType:
				mouseModule.mouseController.RunCallBack("INVENTORY")

			elif player.SLOT_TYPE_SHOP == attachedSlotType:
				net.SendShopBuyPacket(attachedSlotPos)

			elif player.SLOT_TYPE_SAFEBOX == attachedSlotType:

				if player.ITEM_MONEY == attachedItemIndex:
					net.SendSafeboxWithdrawMoneyPacket(mouseModule.mouseController.GetAttachedItemCount())
					snd.PlaySound("sound/ui/money.wav")

				else:
					net.SendSafeboxCheckoutPacket(attachedSlotPos, selectedSlotPos)

			elif player.SLOT_TYPE_MALL == attachedSlotType:
				net.SendMallCheckoutPacket(attachedSlotPos, selectedSlotPos)

			## An extra inventory item moves to the main inventory (OLD :1709-1710).
			elif player.SLOT_TYPE_EXTRA_INVENTORY == attachedSlotType:
				self.__SendMoveItemPacket(attachedSlotPos, selectedSlotPos, attachedItemCount, player.EXTRA_INVENTORY)

			## A switchbot item back to the inventory (NOVA-43). OLD dropped it
			## nowhere: only its right click sent it back.
			elif getattr(player, "SLOT_TYPE_SWITCHBOT", None) == attachedSlotType:
				self.__SendMoveItemPacket(attachedSlotPos, selectedSlotPos, attachedItemCount, player.SWITCHBOT)

			mouseModule.mouseController.DeattachObject()

	def SelectItemSlot(self, itemSlotIndex):
		if constInfo.GET_ITEM_QUESTION_DIALOG_STATUS() == 1:
			return

		itemSlotIndex = self.__InventoryLocalSlotPosToGlobalSlotPos(itemSlotIndex)

		## NOVA-187: the NPC shop's sell marks take the press first.
		if SellMarkPress(player.INVENTORY, itemSlotIndex, ui.__mem_func__(self.RefreshBagSlotWindow)):
			return

		## NOVA-9 (OLD uiInventory.py:1758-1761): Ctrl + click on an item
		## searches the shops for it, while the offline shop is on, nothing is
		## attached and no safebox is open; otherwise Ctrl + click adds the
		## item to the quick slots, as before.
		if app.IsPressed(app.DIK_LCONTROL) and self.offlineShopEnabled and \
				not mouseModule.mouseController.isAttached() and not self.IsSafeboxOpen():
			self.interface.OpenSearchShop(player.GetItemIndex(itemSlotIndex))
			return

		if mouseModule.mouseController.isAttached():
			attachedSlotType = mouseModule.mouseController.GetAttachedType()
			attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
			attachedItemVID = mouseModule.mouseController.GetAttachedItemIndex()

			## The Pet Name Changer dropped on a pet seal opens the rename
			## dialog (NOVA-24; OLD uiInventory.py:1768-1773; OLD opened it on
			## any item).
			if player.SLOT_TYPE_INVENTORY == attachedSlotType and \
					GetPetItemSubType(player.GetItemIndex(attachedSlotPos)) == PET_NAME_CHANGE and \
					GetPetItemSubType(player.GetItemIndex(itemSlotIndex)) == PET_SUMMON:
				mouseModule.mouseController.DeattachObject()
				self.interface.wndPetEggHatch.Open(itemSlotIndex, player.INVENTORY, True)
				return

			if player.SLOT_TYPE_INVENTORY == attachedSlotType:
				self.__DropSrcItemToDestItemInInventory(attachedItemVID, attachedSlotPos, itemSlotIndex)

			elif player.SLOT_TYPE_EXTRA_INVENTORY == attachedSlotType:
				self.__DropSrcItemToDestItemInInventory(attachedItemVID, attachedSlotPos, itemSlotIndex, player.EXTRA_INVENTORY)

			mouseModule.mouseController.DeattachObject()

		else:

			curCursorNum = app.GetCursor()
			if app.SELL == curCursorNum:
				self.__SellItem(itemSlotIndex)
				
			elif app.BUY == curCursorNum:
				chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.SHOP_BUY_INFO)

			elif app.IsPressed(app.DIK_LALT):
				link = player.GetItemLink(itemSlotIndex)
				link_tokens.paste(link)

			elif app.IsPressed(app.DIK_LSHIFT):
				itemCount = player.GetItemCount(itemSlotIndex)
				
				if itemCount > 1:
					self.dlgPickMoney.SetTitleName(localeInfo.PICK_ITEM_TITLE)
					self.dlgPickMoney.SetAcceptEvent(ui.__mem_func__(self.OnPickItem))
					self.dlgPickMoney.SetItemMode()
					self.dlgPickMoney.Open(itemCount)
					self.dlgPickMoney.itemGlobalSlotIndex = itemSlotIndex
				#else:
					#selectedItemVNum = player.GetItemIndex(itemSlotIndex)
					#mouseModule.mouseController.AttachObject(self, player.SLOT_TYPE_INVENTORY, itemSlotIndex, selectedItemVNum)

			elif app.IsPressed(app.DIK_LCONTROL):
				itemIndex = player.GetItemIndex(itemSlotIndex)

				if True == item.CanAddToQuickSlotItem(itemIndex):
					player.RequestAddToEmptyLocalQuickSlot(player.SLOT_TYPE_INVENTORY, itemSlotIndex)
				else:
					chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.QUICKSLOT_REGISTER_DISABLE_ITEM)

			else:
				selectedItemVNum = player.GetItemIndex(itemSlotIndex)
				itemCount = player.GetItemCount(itemSlotIndex)
				mouseModule.mouseController.AttachObject(self, player.SLOT_TYPE_INVENTORY, itemSlotIndex, selectedItemVNum, itemCount)
				
				if self.__IsUsableItemToItem(selectedItemVNum, itemSlotIndex):				
					self.wndItem.SetUseMode(True)
				else:					
					self.wndItem.SetUseMode(False)

				snd.PlaySound("sound/ui/pick.wav")

	def __DropSrcItemToDestItemInInventory(self, srcItemVID, srcItemSlotPos, dstItemSlotPos, srcWindow=player.INVENTORY):
		if srcWindow == player.EXTRA_INVENTORY:
			self.__DropExtraItemToDestItem(srcItemVID, srcItemSlotPos, dstItemSlotPos)
			return

		if srcItemSlotPos == dstItemSlotPos:
			return
	         	
		elif item.IsRefineScroll(srcItemVID):
			self.RefineItem(srcItemSlotPos, dstItemSlotPos)
			self.wndItem.SetUseMode(False)

		elif item.IsMetin(srcItemVID):
			self.AttachMetinToItem(srcItemSlotPos, dstItemSlotPos)

		elif item.IsDetachScroll(srcItemVID):
			self.DetachMetinFromItem(srcItemSlotPos, dstItemSlotPos)

		elif item.IsSocketScroll(srcItemVID):
			self.OpenSocketOnItem(srcItemSlotPos, dstItemSlotPos)

		elif item.IsKey(srcItemVID):
			self.__SendUseItemToItemPacket(srcItemSlotPos, dstItemSlotPos)			

		elif (player.GetItemFlags(srcItemSlotPos) & ITEM_FLAG_APPLICABLE) == ITEM_FLAG_APPLICABLE:
			self.__SendUseItemToItemPacket(srcItemSlotPos, dstItemSlotPos)

		elif item.GetUseType(srcItemVID) in self.USE_TYPE_TUPLE:
			self.__SendUseItemToItemPacket(srcItemSlotPos, dstItemSlotPos)			

		## The destiny orb on a pet seal (NOVA-24; OLD uiInventory.py:1917-1918).
		elif GetPetItemSubType(srcItemVID) == PET_DESTINY_ORB:
			self.__CanUsePetItemToDstItem(srcItemSlotPos, dstItemSlotPos)

		## A buffi INT booster is used on the item it is dropped on (NOVA-38;
		## OLD uiInventory.py:1919-1920); the server takes only a buffi item.
		elif IsFakeBuffIntBoost(srcItemVID):
			self.__SendUseItemToItemPacket(srcItemSlotPos, dstItemSlotPos)

		else:
			#snd.PlaySound("sound/ui/drop.wav")

			## If destination is an equipment slot, use item to equip it - [levites]
			if player.IsEquipmentSlot(dstItemSlotPos):

				## Only when holding equipment item
				if item.IsEquipmentVID(srcItemVID):
					self.__UseItem(srcItemSlotPos)

			else:
				self.__SendMoveItemPacket(srcItemSlotPos, dstItemSlotPos, 0)
				#net.SendItemMovePacket(srcItemSlotPos, dstItemSlotPos, 0)

	def __DropExtraItemToDestItem(self, srcItemVID, srcItemSlotPos, dstItemSlotPos):
		## An extra inventory item (NOVA-16) dropped on an item here; never the
		## same cell, EXTRA 10 on INVENTORY 10 is a real drop. A stone opens
		## the attach dialog (OLD :2095-2120); a key, a scroll the server
		## applies (71051/71052, ITEM_APPLICABLE) and the other use-on-item
		## items are used on the target (OLD :1775-1779); an equipment item
		## (a costume) dropped on a worn cell is worn; anything else moves.
		if item.IsMetin(srcItemVID):
			self.AttachMetinToItem(srcItemSlotPos, dstItemSlotPos, player.EXTRA_INVENTORY)

		elif item.IsKey(srcItemVID) or \
				(self.__GetItemFlags(srcItemSlotPos, player.EXTRA_INVENTORY) & ITEM_FLAG_APPLICABLE) == ITEM_FLAG_APPLICABLE or \
				item.GetUseType(srcItemVID) in self.USE_TYPE_TUPLE:
			self.__SendUseItemToItemPacket(srcItemSlotPos, dstItemSlotPos, player.EXTRA_INVENTORY)

		elif player.IsEquipmentSlot(dstItemSlotPos):
			if item.IsEquipmentVID(srcItemVID):
				self.__SendUseItemPacket(srcItemSlotPos, player.EXTRA_INVENTORY)

		else:
			self.__SendMoveItemPacket(srcItemSlotPos, dstItemSlotPos, 0, player.EXTRA_INVENTORY)

	def __SellItem(self, itemSlotPos):
		if not player.IsEquipmentSlot(itemSlotPos):
			self.sellingSlotNumber = itemSlotPos
			itemIndex = player.GetItemIndex(itemSlotPos)
			itemCount = player.GetItemCount(itemSlotPos)
			
			
			self.sellingSlotitemIndex = itemIndex
			self.sellingSlotitemCount = itemCount

			item.SelectItem(itemIndex)
			## Added anti-flag check that was missing
			## 20140220
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

	def __OnClosePopupDialog(self):
		self.pop = None

	def RefineItem(self, scrollSlotPos, targetSlotPos):

		scrollIndex = player.GetItemIndex(scrollSlotPos)
		targetIndex = player.GetItemIndex(targetSlotPos)

		if player.REFINE_OK != player.CanRefine(scrollIndex, targetSlotPos):
			return

		###########################################################
		self.__SendUseItemToItemPacket(scrollSlotPos, targetSlotPos)
		#net.SendItemUseToItemPacket(scrollSlotPos, targetSlotPos)
		return
		###########################################################

		###########################################################
		#net.SendRequestRefineInfoPacket(targetSlotPos)
		#return
		###########################################################

		result = player.CanRefine(scrollIndex, targetSlotPos)

		if player.REFINE_ALREADY_MAX_SOCKET_COUNT == result:
			#snd.PlaySound("sound/ui/jaeryun_fail.wav")
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.REFINE_FAILURE_NO_MORE_SOCKET)

		elif player.REFINE_NEED_MORE_GOOD_SCROLL == result:
			#snd.PlaySound("sound/ui/jaeryun_fail.wav")
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.REFINE_FAILURE_NEED_BETTER_SCROLL)

		elif player.REFINE_CANT_MAKE_SOCKET_ITEM == result:
			#snd.PlaySound("sound/ui/jaeryun_fail.wav")
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.REFINE_FAILURE_SOCKET_DISABLE_ITEM)

		elif player.REFINE_NOT_NEXT_GRADE_ITEM == result:
			#snd.PlaySound("sound/ui/jaeryun_fail.wav")
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.REFINE_FAILURE_UPGRADE_DISABLE_ITEM)

		elif player.REFINE_CANT_REFINE_METIN_TO_EQUIPMENT == result:
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.REFINE_FAILURE_EQUIP_ITEM)

		if player.REFINE_OK != result:
			return

		self.refineDialog.Open(scrollSlotPos, targetSlotPos)

	def OpenSocketOnItem(self, scrollSlotPos, targetSlotPos):
		## OLD's fourth socket (50500 armour, 50501 weapon; OLD uiInventory.py:2044-2070):
		## the server opens it on an item with 3 stones and says why it refuses
		scrollIndex = player.GetItemIndex(scrollSlotPos)
		if not player.CanAdd4thStone(scrollIndex, targetSlotPos):
			item.SelectItem(scrollIndex)
			if item.GetItemSubType() == item.USE_4TH_SOCKET:
				if player.GetSocketCount(targetSlotPos) < 3:
					chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.ADD_4TH_STONE_NOT_ENOUGH_STONES)
				elif item.GetValue(0) == 1 and player.GetItemTypeBySlot(targetSlotPos) != item.ITEM_TYPE_ARMOR:
					chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.ADD_4TH_STONE_ONLY_ARMOR)
				elif item.GetValue(0) == 2 and player.GetItemTypeBySlot(targetSlotPos) != item.ITEM_TYPE_WEAPON:
					chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.ADD_4TH_STONE_ONLY_WEAPON)
				elif player.GetItemMetinSocket(player.INVENTORY, targetSlotPos, 3) != 0:
					chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.ADD_4TH_STONE_ALREADY_ADDED)
				else:
					chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.ADD_4TH_STONE_NOT_POSSIBLE)
				return

		self.questionDialog = uiCommon.QuestionDialog()
		self.questionDialog.SetText(localeInfo.ADD_4TH_STONE_ADD_QUESTION)
		self.questionDialog.SetAcceptEvent(ui.__mem_func__(self.OnDetachMetinFromItem))
		self.questionDialog.SetCancelEvent(ui.__mem_func__(self.OnCloseQuestionDialog))
		self.questionDialog.Open()
		self.questionDialog.sourcePos = scrollSlotPos
		self.questionDialog.targetPos = targetSlotPos

	def DetachMetinFromItem(self, scrollSlotPos, targetSlotPos):
		scrollIndex = player.GetItemIndex(scrollSlotPos)
		targetIndex = player.GetItemIndex(targetSlotPos)

		## OLD uiInventory.py:2071-2108 (NOVA-20): the sash's bonus scrolls
		## have their own refusal and question.
		if not player.CanDetach(scrollIndex, targetSlotPos):
			if IsSashBonusScroll(scrollIndex):
				chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.SASH_FAILURE_CLEAN)
			else:
				chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.REFINE_FAILURE_METIN_INSEPARABLE_ITEM)
			return

		self.questionDialog = uiCommon.QuestionDialog()
		self.questionDialog.SetText(localeInfo.REFINE_DO_YOU_SEPARATE_METIN)
		item.SelectItem(targetIndex)
		if item.GetItemType() in (item.ITEM_TYPE_WEAPON, item.ITEM_TYPE_ARMOR, item.ITEM_TYPE_COSTUME):
			if IsSashBonusScroll(scrollIndex):
				self.questionDialog.SetText(localeInfo.SASH_DO_YOU_CLEAN)
		self.questionDialog.SetAcceptEvent(ui.__mem_func__(self.OnDetachMetinFromItem))
		self.questionDialog.SetCancelEvent(ui.__mem_func__(self.OnCloseQuestionDialog))
		self.questionDialog.Open()
		self.questionDialog.sourcePos = scrollSlotPos
		self.questionDialog.targetPos = targetSlotPos

	def AttachMetinToItem(self, metinSlotPos, targetSlotPos, metinWindow=player.INVENTORY):
		if metinWindow == player.INVENTORY:
			metinIndex = player.GetItemIndex(metinSlotPos)
		else:
			metinIndex = player.GetItemIndex(metinWindow, metinSlotPos)
		targetIndex = player.GetItemIndex(targetSlotPos)

		item.SelectItem(metinIndex)
		itemName = item.GetItemName()

		result = player.CanAttachMetin(metinIndex, targetSlotPos)

		if player.ATTACH_METIN_NOT_MATCHABLE_ITEM == result:
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.REFINE_FAILURE_CAN_NOT_ATTACH(itemName))

		if player.ATTACH_METIN_NO_MATCHABLE_SOCKET == result:
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.REFINE_FAILURE_NO_SOCKET(itemName))

		elif player.ATTACH_METIN_NOT_EXIST_GOLD_SOCKET == result:
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.REFINE_FAILURE_NO_GOLD_SOCKET(itemName))

		elif player.ATTACH_METIN_CANT_ATTACH_TO_EQUIPMENT == result:
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.REFINE_FAILURE_EQUIP_ITEM)

		if player.ATTACH_METIN_OK != result:
			return

		if metinWindow == player.INVENTORY:
			self.attachMetinDialog.Open(metinSlotPos, targetSlotPos)
		else:
			self.attachMetinDialog.Open(metinSlotPos, targetSlotPos, metinWindow=metinWindow)


		
	def OverOutItem(self):
		constInfo.SET_HOVERED_CHEST(0)
		self.tabPreviewCell = -1
		self.wndItem.SetUsableItem(False)
		if None != self.tooltipItem:
			self.tooltipItem.HideToolTip()

	def OverInItem(self, overSlotPos):
		overSlotPos = self.__InventoryLocalSlotPosToGlobalSlotPos(overSlotPos)
		self.tabPreviewCell = overSlotPos
		self.wndItem.SetUsableItem(False)
		## OLD's selectedItem (uiInventory.py:2159): Shift over a chest shows
		## its contents (NOVA-18).
		constInfo.SET_HOVERED_CHEST(player.GetItemIndex(overSlotPos))

		if mouseModule.mouseController.isAttached():
			attachedItemType = mouseModule.mouseController.GetAttachedType()
			if player.SLOT_TYPE_INVENTORY == attachedItemType:

				attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
				attachedItemVNum = mouseModule.mouseController.GetAttachedItemIndex()
				
				if self.__CanUseSrcItemToDstItem(attachedItemVNum, attachedSlotPos, overSlotPos):
					self.wndItem.SetUsableItem(True)
					self.ShowToolTip(overSlotPos)
					return

			## An extra inventory item over a target it can be used on (OLD :2163-2164).
			elif player.SLOT_TYPE_EXTRA_INVENTORY == attachedItemType:
				attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
				attachedItemVNum = mouseModule.mouseController.GetAttachedItemIndex()

				if self.__CanUseSrcItemToDstItem(attachedItemVNum, attachedSlotPos, overSlotPos, player.EXTRA_INVENTORY):
					self.wndItem.SetUseMode(True)
					self.wndItem.SetUsableItem(True)
					self.ShowToolTip(overSlotPos)
					return

		self.ShowToolTip(overSlotPos)


	def __IsUsableItemToItem(self, srcItemVNum, srcSlotPos):
		"Can this item be used on other items?"

		if item.IsRefineScroll(srcItemVNum):
			return True
		elif item.IsMetin(srcItemVNum):
			return True
		elif item.IsDetachScroll(srcItemVNum):
			return True
		elif item.IsSocketScroll(srcItemVNum):
			return True
		elif item.IsKey(srcItemVNum):
			return True
		elif IsFakeBuffIntBoost(srcItemVNum):
			return True
		elif (player.GetItemFlags(srcSlotPos) & ITEM_FLAG_APPLICABLE) == ITEM_FLAG_APPLICABLE:
			return True
		else:
			if item.GetUseType(srcItemVNum) in self.USE_TYPE_TUPLE:
				return True
			
		return False

	def __CanUseSrcItemToDstItem(self, srcItemVNum, srcSlotPos, dstSlotPos, srcWindow=player.INVENTORY):
		"Can this item be used on the target item?"

		if srcWindow == player.INVENTORY and srcSlotPos == dstSlotPos:
			return False

		if item.IsRefineScroll(srcItemVNum):
			if player.REFINE_OK == player.CanRefine(srcItemVNum, dstSlotPos):
				return True
		elif item.IsMetin(srcItemVNum):
			if player.ATTACH_METIN_OK == player.CanAttachMetin(srcItemVNum, dstSlotPos):
				return True
		elif item.IsDetachScroll(srcItemVNum):
			if player.DETACH_METIN_OK == player.CanDetach(srcItemVNum, dstSlotPos):
				return True
		elif item.IsSocketScroll(srcItemVNum):
			if player.DETACH_METIN_OK == player.CanAdd4thStone(srcItemVNum, dstSlotPos):
				return True
		elif item.IsKey(srcItemVNum):
			if player.CanUnlock(srcItemVNum, dstSlotPos):
				return True

		## NOVA-38 (OLD uiInventory.py:2236-2238): a booster on a buffi item.
		elif IsFakeBuffIntBoost(srcItemVNum):
			if constInfo.IS_FAKEBUFF_ITEM(player.GetItemIndex(dstSlotPos)):
				return True

		elif (self.__GetItemFlags(srcSlotPos, srcWindow) & ITEM_FLAG_APPLICABLE) == ITEM_FLAG_APPLICABLE:
			return True

		else:
			useType=item.GetUseType(srcItemVNum)

			if "USE_CLEAN_SOCKET" == useType:
				if self.__CanCleanBrokenMetinStone(dstSlotPos):
					return True
			elif "USE_CHANGE_ATTRIBUTE" == useType:
				if self.__CanChangeItemAttrList(dstSlotPos):
					return True
			elif "USE_ADD_ATTRIBUTE" == useType:
				if self.__CanAddItemAttr(dstSlotPos):
					return True
			elif "USE_ADD_ATTRIBUTE2" == useType:
				if self.__CanAddItemAttr(dstSlotPos):
					return True
			elif "USE_ADD_ACCESSORY_SOCKET" == useType:
				# MR-10: Add belt support for accessory sockets
				if self.__CanAddAccessorySocket(dstSlotPos) or self.__CanAddBeltSocket(dstSlotPos):
					return True
				# MR-10: -- END OF -- Add belt support for accessory sockets
			elif "USE_PUT_INTO_ACCESSORY_SOCKET" == useType:								
				if self.__CanPutAccessorySocket(dstSlotPos, srcItemVNum):
					return True
			elif "USE_PUT_INTO_BELT_SOCKET" == useType:								
				# MR-10: Add belt support for accessory sockets
				if self.__CanPutBeltSocket(dstSlotPos, srcItemVNum):
					return True
				# MR-10: -- END OF -- Add belt support for accessory sockets

		return False

	@staticmethod
	def __GetItemFlags(slotPos, window=player.INVENTORY):
		if window == player.INVENTORY:
			return player.GetItemFlags(slotPos)
		return player.GetItemFlags(window, slotPos)

	def __CanCleanBrokenMetinStone(self, dstSlotPos):
		dstItemVNum = player.GetItemIndex(dstSlotPos)
		if dstItemVNum == 0:
			return False

		item.SelectItem(dstItemVNum)
		
		if item.ITEM_TYPE_WEAPON != item.GetItemType():
			return False

		for i in range(player.METIN_SOCKET_MAX_NUM):
			if player.GetItemMetinSocket(dstSlotPos, i) == constInfo.ERROR_METIN_STONE:
				return True

		return False

	def __CanChangeItemAttrList(self, dstSlotPos):
		dstItemVNum = player.GetItemIndex(dstSlotPos)
		if dstItemVNum == 0:
			return False

		item.SelectItem(dstItemVNum)
		
		if not item.GetItemType() in (item.ITEM_TYPE_WEAPON, item.ITEM_TYPE_ARMOR):	 
			return False

		for i in range(player.METIN_SOCKET_MAX_NUM):
			if player.GetItemAttribute(dstSlotPos, i) != 0:
				return True

		return False

	# MR-10: Add belt support for accessory sockets
	def __CanPutBeltSocket(self, dstSlotPos, mtrlVnum):
		dstItemVNum = player.GetItemIndex(dstSlotPos)

		if dstItemVNum == 0:
			return False

		item.SelectItem(dstItemVNum)

		if item.ITEM_TYPE_BELT != item.GetItemType():
			return False

		if mtrlVnum != constInfo.GET_BELT_MATERIAL_VNUM(dstItemVNum):
			return False

		curCount = player.GetItemMetinSocket(dstSlotPos, 0)
		maxCount = player.GetItemMetinSocket(dstSlotPos, 1)

		if maxCount <= 0:
			return False

		if curCount >= maxCount:
			return False

		return True
	# MR-10: -- END OF -- Add belt support for accessory sockets

	def __CanPutAccessorySocket(self, dstSlotPos, mtrlVnum):
		dstItemVNum = player.GetItemIndex(dstSlotPos)
		if dstItemVNum == 0:
			return False

		item.SelectItem(dstItemVNum)

		if item.GetItemType() != item.ITEM_TYPE_ARMOR:
			return False

		if not item.GetItemSubType() in (item.ARMOR_WRIST, item.ARMOR_NECK, item.ARMOR_EAR):
			return False

		curCount = player.GetItemMetinSocket(dstSlotPos, 0)
		maxCount = player.GetItemMetinSocket(dstSlotPos, 1)

		if mtrlVnum != constInfo.GET_ACCESSORY_MATERIAL_VNUM(dstItemVNum, item.GetItemSubType()):
			return False
		
		if curCount>=maxCount:
			return False

		return True

	def __CanAddAccessorySocket(self, dstSlotPos):
		dstItemVNum = player.GetItemIndex(dstSlotPos)
		if dstItemVNum == 0:
			return False

		item.SelectItem(dstItemVNum)

		if item.GetItemType() != item.ITEM_TYPE_ARMOR:
			return False

		if not item.GetItemSubType() in (item.ARMOR_WRIST, item.ARMOR_NECK, item.ARMOR_EAR):
			return False

		curCount = player.GetItemMetinSocket(dstSlotPos, 0)
		maxCount = player.GetItemMetinSocket(dstSlotPos, 1)
		
		ACCESSORY_SOCKET_MAX_SIZE = 3
		if maxCount >= ACCESSORY_SOCKET_MAX_SIZE:
			return False

		return True

	# MR-10: Add belt support for accessory sockets
	def __CanAddBeltSocket(self, dstSlotPos):
		dstItemVNum = player.GetItemIndex(dstSlotPos)

		if dstItemVNum == 0:
			return False

		item.SelectItem(dstItemVNum)

		if item.ITEM_TYPE_BELT != item.GetItemType():
			return False

		curCount = player.GetItemMetinSocket(dstSlotPos, 0)
		maxCount = player.GetItemMetinSocket(dstSlotPos, 1)

		ACCESSORY_SOCKET_MAX_SIZE = 3

		if maxCount >= ACCESSORY_SOCKET_MAX_SIZE:
			return False

		return True
	# MR-10: -- END OF -- Add belt support for accessory sockets

	def __CanAddItemAttr(self, dstSlotPos):
		dstItemVNum = player.GetItemIndex(dstSlotPos)
		if dstItemVNum == 0:
			return False

		item.SelectItem(dstItemVNum)
		
		if not item.GetItemType() in (item.ITEM_TYPE_WEAPON, item.ITEM_TYPE_ARMOR):	 
			return False
			
		attrCount = 0
		for i in range(player.METIN_SOCKET_MAX_NUM):
			if player.GetItemAttribute(dstSlotPos, i) != 0:
				attrCount += 1

		if attrCount<4:
			return True
								
		return False

	def ShowToolTip(self, slotIndex):
		if None != self.tooltipItem:
			self.tooltipItem.SetInventoryItem(slotIndex)

	def OnTop(self):
		if None != self.tooltipItem:
			self.tooltipItem.SetTop()

		if self.wndBelt:
			self.wndBelt.SetTop()

		## OLD uiInventory.py:2490-2492: the locks and marks again.
		self.RefreshLockedSlots()
		self.RefreshMarkSlots()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	## Tab over a pet seal previews its pet (NOVA-24; OLD uiInventory.py:
	## 1210-1217): the Interface's PressTabKey asks; the cell is the one the
	## pointer is over (OverInItem).
	tabPreviewCell = -1

	def OnPressTabKey(self):
		if self.tabPreviewCell < 0:
			return False
		if GetPetItemSubType(player.GetItemIndex(self.tabPreviewCell)) != PET_SUMMON:
			return False
		import pet
		pet.ReqPetPreview(PET_PREVIEW_INVENTORY, player.INVENTORY, self.tabPreviewCell)
		return True

	def UseItemSlot(self, slotIndex):
		curCursorNum = app.GetCursor()
		if app.SELL == curCursorNum:
			return

		if constInfo.GET_ITEM_QUESTION_DIALOG_STATUS():
			return

		slotIndex = self.__InventoryLocalSlotPosToGlobalSlotPos(slotIndex)

		## NOVA-187: a marked item is not used.
		if IsSellMarked(player.INVENTORY, slotIndex):
			return

		if app.ENABLE_DRAGON_SOUL_SYSTEM:
			if self.wndDragonSoulRefine.IsShow():
				self.wndDragonSoulRefine.AutoSetItem((player.INVENTORY, slotIndex), 1)
				return

		## OLD uiInventory.py:2522-2531: a right-click puts the item into the
		## open sash window (the server picks the slot) or an aura material into
		## the open aura window.
		sashWindow = self.GetShownSashWindow()
		if sashWindow:
			sashWindow.AddItem(player.INVENTORY, slotIndex)
			return

		if self.wndAura and self.wndAura.IsOpened():
			item.SelectItem(player.GetItemIndex(slotIndex))
			if item.GetItemType() == item.ITEM_TYPE_RESOURCE and item.GetItemSubType() == item.RESOURCE_AURA:
				net.SendChatPacket("/aura add %d %d %d" % (item.AURA_SLOT_MATERIAL, player.INVENTORY, slotIndex))
				return

		if self.__UseItemWithModifier(slotIndex):
			mouseModule.mouseController.DeattachObject()
			self.OverOutItem()
			return

		## An egg opens the hatch window (NOVA-24; OLD uiInventory.py:2621-2625).
		if GetPetItemSubType(player.GetItemIndex(slotIndex)) == PET_EGG:
			self.interface.wndPetEggHatch.Open(slotIndex, player.INVENTORY)
			return

		self.__UseItem(slotIndex)
		mouseModule.mouseController.DeattachObject()
		self.OverOutItem()

	def IsSafeboxOpen(self):
		"""Whether the safebox window shows (NEW's safebox module has no
		IsOpen, OLD's did)."""
		interface = getattr(self, "interface", None)
		isSafeboxOpen = getattr(interface, "IsSafeboxOpen", None)
		return bool(isSafeboxOpen and isSafeboxOpen())

	def __UseItemWithModifier(self, slotIndex):
		"""OLD :2605-2620 (NOVA-16) for a bag cell: Shift + right-click puts
		the item into the open safebox, Ctrl + right-click into the open
		trade, otherwise Ctrl + right-click moves a costume or one of the
		four scrolls to the special inventory (the tooltip's hint lines say
		so); any other item is used. True when it sent something."""
		isShift = app.IsPressed(app.DIK_LSHIFT)
		isControl = app.IsPressed(app.DIK_LCONTROL)
		isAlt = app.IsPressed(app.DIK_LALT)
		if not isShift and not isControl and not isAlt:
			return False

		if slotIndex >= player.INVENTORY_PAGE_SIZE * player.INVENTORY_PAGE_COUNT:
			return False

		## Alt + right-click on a stack of chests asks how many to open
		## (NOVA-81; OLD :2533-2565).
		if isAlt and player.GetItemCount(slotIndex) > 1 and IsMultiOpenItem(player.GetItemIndex(slotIndex)):
			self.OpenMultiUseDialog(player.INVENTORY, slotIndex, player.GetItemCount(slotIndex))
			return True

		if isShift and self.IsSafeboxOpen():
			net.SendSafeboxCheckinPacket(player.INVENTORY, slotIndex, SafeboxCheckinCell(player.GetItemIndex(slotIndex)))
			return True

		## Shift + right-click opens the item in the wiki (NOVA-42; OLD :2509);
		## where the wiki cannot open (no NovaUI) the item is used as before.
		if isShift and self.interface and self.interface.OpenWikiItem(player.GetItemIndex(slotIndex)):
			return True

		if isControl:
			import exchange # the client's; imported here, as the item windows' stand-ins have none
			if exchange.isTrading():
				net.SendExchangeItemAddPacket(player.INVENTORY, slotIndex, 0)
				return True

			if IsExtraSharedItem(player.GetItemIndex(slotIndex)):
				net.SendItemTransferPacket(player.INVENTORY, slotIndex, player.EXTRA_INVENTORY)
				return True

		return False

	def ClickWikiButton(self):
		## The inventory's wiki button (NOVA-42; OLD's wikiBtn, :470).
		if self.interface:
			self.interface.ToggleWiki()

	def OpenMultiUseDialog(self, window, slotIndex, itemCount):
		self.dlgPickMoney.SetTitleName(localeInfo.PICK_ITEM_TITLE)
		self.dlgPickMoney.SetAcceptEvent(ui.__mem_func__(self.OnPickMultiUse))
		self.dlgPickMoney.Open(min(itemCount, GACHA_MULTI_OPEN_MAX))
		self.dlgPickMoney.multiUseItemPos = (window, slotIndex)

	def OnPickMultiUse(self, count):
		(window, slotIndex) = self.dlgPickMoney.multiUseItemPos
		# Prevent item usage while private shop is open
		if uiPrivateShopBuilder.IsBuildingPrivateShop():
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.USE_ITEM_FAILURE_PRIVATE_SHOP)
			return

		net.SendItemMultiUsePacket(window, slotIndex, min(count, GACHA_MULTI_OPEN_MAX))

	def __UseItem(self, slotIndex):
		ItemVNum = player.GetItemIndex(slotIndex)
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
			#net.SendItemUsePacket(slotIndex)	

	def __UseItemQuestionDialog_OnCancel(self):
		self.OnCloseQuestionDialog()

	def __UseItemQuestionDialog_OnAccept(self):
		self.__SendUseItemPacket(self.questionDialog.slotIndex)
		self.OnCloseQuestionDialog()		

	## The three senders send a main inventory cell as before, and a cell of
	## another source window (the extra inventory, NOVA-16) with its window.
	def __SendUseItemToItemPacket(self, srcSlotPos, dstSlotPos, srcWindow=player.INVENTORY):
		# Prevent item usage while private shop is open
		if uiPrivateShopBuilder.IsBuildingPrivateShop():
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.USE_ITEM_FAILURE_PRIVATE_SHOP)
			return

		if srcWindow == player.INVENTORY:
			net.SendItemUseToItemPacket(srcSlotPos, dstSlotPos)
		else:
			net.SendItemUseToItemPacket(srcWindow, srcSlotPos, player.INVENTORY, dstSlotPos)

	def __SendUseItemPacket(self, slotPos, srcWindow=player.INVENTORY):
		# Prevent item usage while private shop is open
		if uiPrivateShopBuilder.IsBuildingPrivateShop():
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.USE_ITEM_FAILURE_PRIVATE_SHOP)
			return

		if srcWindow == player.INVENTORY:
			net.SendItemUsePacket(slotPos)
		else:
			net.SendItemUsePacket(srcWindow, slotPos)

	def __SendMoveItemPacket(self, srcSlotPos, dstSlotPos, srcItemCount, srcWindow=player.INVENTORY):
		# Prevent item movement while private shop is open
		if uiPrivateShopBuilder.IsBuildingPrivateShop():
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.MOVE_ITEM_FAILURE_PRIVATE_SHOP)
			return

		if srcWindow == player.INVENTORY:
			net.SendItemMovePacket(srcSlotPos, dstSlotPos, srcItemCount)
		else:
			net.SendItemMovePacket(srcWindow, srcSlotPos, player.INVENTORY, dstSlotPos, srcItemCount)
	
	## OLD uiInventory.py:2729-2747.
	def SetAuraWindow(self, wndAura):
		self.wndAura = wndAura

	def SetSashWindow(self, wndSashCombine, wndSashAbsorption):
		self.wndSashCombine = wndSashCombine
		self.wndSashAbsorption = wndSashAbsorption

	def isShowSashWindow(self):
		if self.GetShownSashWindow():
			return 1
		return 0

	def GetShownSashWindow(self):
		"""The sash window that shows, or None."""
		for wnd in (self.wndSashCombine, self.wndSashAbsorption):
			if wnd and wnd.IsShow():
				return wnd
		return None

	def SetDragonSoulRefineWindow(self, wndDragonSoulRefine):
		if app.ENABLE_DRAGON_SOUL_SYSTEM:
			self.wndDragonSoulRefine = wndDragonSoulRefine
			
	def OnMoveWindow(self, x, y):
#		print "Inventory Global Pos : ", self.GetGlobalPosition()
		if self.wndBelt:
#			print "Belt Global Pos : ", self.wndBelt.GetGlobalPosition()
			self.wndBelt.AdjustPositionAndSize()
						
