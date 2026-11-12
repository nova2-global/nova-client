## The switchbot (NOVA-43): OLD's root/uiSwitchbot.py (ENABLE_SWITCHBOT, live
## through interfaceModule.py:417, 934, 3099-3111 and game.py:491, 2972,
## 3286-3287, 3935-3941) on NEW's data. The server rolls the bonuses (C's
## switchbot module holds what GC::SWITCHBOT last said); this window shows the
## six items of window SWITCHBOT, edits each slot's three target sets in the
## switchbot module, and starts or stops a slot with the cost the player
## chose (NOVA-43 Q3 c: a switch item per roll, as OLD, or the server's yang
## price).
##
## Kept from OLD: the six item tabs (an item placed or taken by a drag, used
## with a right click to send it back to the inventory), the three
## alternatives, the 5 + 2 target rows with their attribute search list and
## value field, the 6/7 (rare) toggle, start/stop, the saved configurations
## (switchbot.pkl beside the client) and the premium line.
## Changed (OLD bugs and NEW's rules):
## - No per-frame Python: OLD polled the premium status in OnUpdate and pulsed
##   the selected tab's box there; the premium line now follows the roll
##   speed the server sends (switchbot.GetRollMs(), NOVA-43 Q2), written at
##   each refresh, and the selected tab's box is still.
## - The value field's arrows changed only the text, never the target (OLD
##   :486-494): they now set the value as typing does, kept between 0 and
##   the bonus's highest value; an empty field no longer raises.
## - The rare rows (6 and 7) read and clamp with the rare getters (OLD read
##   them as normal bonuses in the value field and the saved configurations).
## - Costumes take the normal rows in NEW (their bonuses are the body and
##   head sets), so OLD's forced rare mode for costumes is gone; an aura still
##   hides the 6/7 toggle.
## - OLD's art under d:/ymir work/ui/switchbot/ is not shipped: NEW's public
##   board, slots and buttons stand in.
import ui
import player
import item
import net
import app
import ime
import link_tokens
import mouseModule
import localeInfo
import constInfo
import wndMgr
import switchbot

try:
	import cPickle as pickle
except ImportError:
	import pickle

COLOR_INACTIVE = 0x33FF0000		## OLD grp.GenerateColor(1.0, 0.0, 0.0, 0.2)
COLOR_ACTIVE = 0x33FF9919		## OLD (1.0, 0.6, 0.1, 0.2)
COLOR_FINISHED = 0x3300FF00		## OLD (0.0, 1.0, 0.0, 0.2)
NULL_BAR = 0x99800000			## OLD (0.5, 0.0, 0.0, 0.6)

## OLD's addon bonuses (the weapons whose first bonus is one of them).
SKILL_DAMAGE_BONUS_MAX = 20
NORMAL_HIT_DAMAGE_BONUS_MAX = 60

ATTR_SLOT_COUNT = 5
RARE_ATTR_SLOT_COUNT = 2
INPUT_HEIGHT = 27
ATTR_ROW_X = 92
ATTR_ROW_Y = 285
ATTR_ROW_WIDTH = 369

## OLD's roll interval without the premium perk (switchbot.cpp c_fSpeed).
NORMAL_ROLL_MS = 250

BORDER_SPACE = 45
BORDER_SPACE_TOP = 30
CONFIG_FILE = "switchbot.pkl"


def AddonTypes():
	"""OLD's ADDON_TYPES: {apply: highest value}."""
	addons = {}
	for name, maximum in (("APPLY_SKILL_DAMAGE_BONUS", SKILL_DAMAGE_BONUS_MAX),
	                      ("APPLY_NORMAL_HIT_DAMAGE_BONUS", NORMAL_HIT_DAMAGE_BONUS_MAX)):
		value = getattr(item, name, None)
		if isinstance(value, int):
			addons[value] = maximum
	return addons


def GetAffectString(affectType, affectValue):
	"""OLD's GetAffectString over NEW's tooltip texts (uiToolTip.ItemToolTip's
	AFFECT_DICT; OLD's lived in localeInfo)."""
	if not affectType:
		return None

	try:
		import uiToolTip
		affects = uiToolTip.ItemToolTip.AFFECT_DICT
	except (ImportError, AttributeError):
		affects = {}

	try:
		return affects[affectType](affectValue)
	except TypeError:
		return "UNKNOWN_VALUE[%s] %s" % (affectType, affectValue)
	except KeyError:
		return "UNKNOWN_TYPE[%s] %s" % (affectType, affectValue)


def IsRareIndex(index):
	return index >= ATTR_SLOT_COUNT


def GetTarget(slot, alternative, index):
	"""The target (type, value) of a row: the rare getter for rows 5 and 6."""
	if IsRareIndex(index):
		return switchbot.GetRareAttributeByIndex(slot, alternative, index)
	return switchbot.GetAttribute(slot, alternative, index)


def SetTarget(slot, alternative, index, attrType, attrValue):
	if IsRareIndex(index):
		switchbot.SetRareAttribute(slot, alternative, index, attrType, attrValue)
	else:
		switchbot.SetAttribute(slot, alternative, index, attrType, attrValue)


def GetMaxValue(slot, index, attrType):
	"""The highest value a target of this row may ask (OLD's three getters;
	the addon bonuses have their own)."""
	addons = AddonTypes()
	if attrType in addons:
		return addons[attrType]
	if IsRareIndex(index):
		return switchbot.GetRareAttributeMaxValue(slot, attrType)
	if switchbot.IsAuraSlot(slot):
		return switchbot.GetAuraAttributeMaxValue(slot, attrType)
	return switchbot.GetAttributeMaxValue(slot, attrType)


class SwitchbotAttribute(ui.Window):
	"""One target row (OLD's SwitchbotAttribute): the bonus's button, which
	opens the search list, the clear button, and the value field with its
	two arrows."""

	VALUE_WIDTH = 50

	## ui.Window.__init__ calls Hide (below) before __Initialize runs, so what
	## Hide reads has a class-level default, as OLD's row had (:309-314).
	searchTypeButton = None
	deleteAttributeButton = None
	valueInput = None
	valueEditLine = None
	leftArrow = None
	rightArrow = None
	LineBar = None

	def __init__(self):
		ui.Window.__init__(self)
		self.__Initialize()

	def __del__(self):
		ui.Window.__del__(self)

	def __Initialize(self):
		self.selectedSlot = -1
		self.alternative = 0
		self.index = -1
		self.searchEvent = None
		self.attributeUpdateEvent = None
		self.escapeEvent = None
		self.searchTypeButton = None
		self.deleteAttributeButton = None
		self.valueInput = None
		self.valueEditLine = None
		self.leftArrow = None
		self.rightArrow = None
		self.LineBar = None

	def Create(self, width, index):
		self.index = index
		self.SetSize(width, INPUT_HEIGHT)
		self.__Create(width)

		self.searchTypeButton.SetText(localeInfo.SWITCHBOT_EMPTY_ATTR)
		self.searchTypeButton.SetEvent(ui.__mem_func__(self.__OnClickSearchButton))
		self.deleteAttributeButton.SetToolTipText(localeInfo.SWITCHBOT_CLEAR_ATTR)
		self.deleteAttributeButton.SetEvent(ui.__mem_func__(self.__OnClickClearButton))
		self.valueEditLine.SetMax(4)
		self.valueEditLine.SetNumberMode()
		self.valueEditLine.SetText("0")
		self.valueEditLine.OnIMEUpdate = ui.__mem_func__(self.__OnEditLineIMEUpdate)
		self.valueEditLine.SetEscapeEvent(ui.__mem_func__(self.__OnEscapeEvent))
		self.leftArrow.SetEvent(ui.__mem_func__(self.__OnClickLeftArrow))
		self.rightArrow.SetEvent(ui.__mem_func__(self.__OnClickRightArrow))

	def __Create(self, width):
		"""The row's widgets (OLD :336-410), on NEW's public art."""
		self.searchTypeButton = ui.Button()
		self.searchTypeButton.SetParent(self)
		self.searchTypeButton.SetUpVisual("d:/ymir work/ui/public/xlarge_thin_button_01.sub")
		self.searchTypeButton.SetOverVisual("d:/ymir work/ui/public/xlarge_thin_button_02.sub")
		self.searchTypeButton.SetDownVisual("d:/ymir work/ui/public/xlarge_thin_button_03.sub")
		self.searchTypeButton.SetWindowVerticalAlignCenter()
		self.searchTypeButton.SetPosition(1, 0)
		self.searchTypeButton.Show()

		self.deleteAttributeButton = ui.Button()
		self.deleteAttributeButton.SetParent(self)
		self.deleteAttributeButton.SetUpVisual("d:/ymir work/ui/public/close_button_01.sub")
		self.deleteAttributeButton.SetOverVisual("d:/ymir work/ui/public/close_button_02.sub")
		self.deleteAttributeButton.SetDownVisual("d:/ymir work/ui/public/close_button_03.sub")
		self.deleteAttributeButton.SetWindowVerticalAlignCenter()
		self.deleteAttributeButton.SetPosition(205, 0)
		self.deleteAttributeButton.Show()

		self.valueInput = ui.ImageBox()
		self.valueInput.SetParent(self)
		self.valueInput.LoadImage("d:/ymir work/ui/public/Parameter_Slot_03.sub")
		self.valueInput.SetPosition(width - self.VALUE_WIDTH - 45, 4)
		self.valueInput.Show()

		self.valueEditLine = ui.EditLine()
		self.valueEditLine.SetParent(self.valueInput)
		self.valueEditLine.SetSize(self.VALUE_WIDTH, 18)
		self.valueEditLine.SetPosition(20, 3)
		self.valueEditLine.Show()

		self.leftArrow = ui.Button()
		self.leftArrow.SetParent(self)
		self.leftArrow.SetUpVisual("d:/ymir work/ui/public/xsmall_button_01.sub")
		self.leftArrow.SetOverVisual("d:/ymir work/ui/public/xsmall_button_02.sub")
		self.leftArrow.SetDownVisual("d:/ymir work/ui/public/xsmall_button_03.sub")
		self.leftArrow.SetText("-")
		self.leftArrow.SetPosition(width - self.VALUE_WIDTH - 70, 4)
		self.leftArrow.Show()

		self.rightArrow = ui.Button()
		self.rightArrow.SetParent(self)
		self.rightArrow.SetUpVisual("d:/ymir work/ui/public/xsmall_button_01.sub")
		self.rightArrow.SetOverVisual("d:/ymir work/ui/public/xsmall_button_02.sub")
		self.rightArrow.SetDownVisual("d:/ymir work/ui/public/xsmall_button_03.sub")
		self.rightArrow.SetText("+")
		self.rightArrow.SetPosition(width - 40, 4)
		self.rightArrow.Show()

		self.LineBar = ui.Bar()
		self.LineBar.SetParent(self)
		self.LineBar.SetSize(width - 8, 2)
		self.LineBar.SetPosition(2, 13)
		self.LineBar.SetColor(NULL_BAR)

	def Destroy(self):
		self.__Initialize()

	def DisableRow(self):
		self.LineBar.Show()
		self.searchTypeButton.Disable()

	def EnableRow(self):
		self.LineBar.Hide()
		self.searchTypeButton.Enable()

	def Hide(self):
		ui.Window.Hide(self)

		if self.valueEditLine:
			self.valueEditLine.KillFocus()

	def RefreshAttributeRow(self, slot_num, alternative, index):
		self.selectedSlot = slot_num
		self.alternative = alternative
		self.index = index

		if switchbot.IsActive(slot_num):
			self.searchTypeButton.Disable()
			self.deleteAttributeButton.Disable()
			self.valueEditLine.Hide()
		else:
			self.searchTypeButton.Enable()
			self.deleteAttributeButton.Enable()
			self.valueEditLine.Show()

		(attrType, attrValue) = GetTarget(slot_num, alternative, index)
		if not attrType:
			self.SetAttribute(localeInfo.SWITCHBOT_EMPTY_ATTR, 0)
			return

		affectString = GetAffectString(attrType, attrValue)
		if not affectString:
			return

		self.SetAttribute(affectString, attrValue)

	def __OnEditLineIMEUpdate(self):
		ui.EditLine.OnIMEUpdate(self.valueEditLine)
		self.ApplyValue(self.valueEditLine.GetText())

	def ApplyValue(self, text):
		"""A typed value (OLD :449-475): kept to the bonus's highest value and
		written to the slot's target."""
		text = str(text)
		if not text or not text.isdigit():
			return

		(curType, curValue) = GetTarget(self.selectedSlot, self.alternative, self.index)
		value = int(text)
		if value == curValue:
			return

		maxValue = GetMaxValue(self.selectedSlot, self.index, curType) if curType else 0
		if maxValue != 0 and value > maxValue:
			value = maxValue
			self.valueEditLine.SetText(str(value))

		SetTarget(self.selectedSlot, self.alternative, self.index, curType, value)
		if curType:
			self.searchTypeButton.SetText(GetAffectString(curType, value))
		self.__OnAttributeUpdate()

	def SetSearchEvent(self, event):
		self.searchEvent = event

	def __OnClickSearchButton(self):
		if self.searchEvent:
			self.searchEvent(self.index)

	def SetAttributeUpdateEvent(self, event):
		self.attributeUpdateEvent = event

	def __OnAttributeUpdate(self):
		if self.attributeUpdateEvent:
			self.attributeUpdateEvent(self.index)

	def SetEscapeEvent(self, event):
		self.escapeEvent = event

	def __OnEscapeEvent(self):
		if self.escapeEvent:
			self.escapeEvent()

	def __OnClickClearButton(self):
		self.SetAttribute(localeInfo.SWITCHBOT_EMPTY_ATTR, 0)
		SetTarget(self.selectedSlot, self.alternative, self.index, 0, 0)
		self.__OnAttributeUpdate()

	def __Step(self, delta):
		text = str(self.valueEditLine.GetText())
		value = int(text) if text.isdigit() else 0
		value = max(0, value + delta)
		self.valueEditLine.SetText(str(value))
		self.ApplyValue(str(value))

	def __OnClickLeftArrow(self):
		self.__Step(-1)

	def __OnClickRightArrow(self):
		self.__Step(1)

	def SetAttribute(self, applyname, maxValue):
		self.searchTypeButton.SetText(applyname)
		self.valueEditLine.SetText(str(maxValue))

	def GetIndex(self):
		return self.index


class SwitchbotWindow(ui.ScriptWindow):
	"""OLD's SwitchbotWindow (Interface.wndSwitchbot)."""

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.__Initialize()
		self.__LoadWindow()
		self.__BindEvents()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __Initialize(self):
		self.selectedSlot = 0
		self.alternative = 0
		self.isRare = False
		self.cost = getattr(switchbot, "COST_ITEM", 0)

		self.tooltipItem = None
		self.itemSlot = None
		self.statusBars = {}
		self.selectBoxes = {}
		self.selectButtons = {}
		self.alternativeButtons = {}
		self.costButtons = {}
		self.attrDict = {}
		self.rareAttrDict = {}

		self.titleBar = None
		self.rareButton = None
		self.startstopButton = None
		self.saveButton = None
		self.costText = None
		self.premiumStatus = None
		self.speedText = None

		self.attributeSearchWindow = None
		self.attrSearchIdx = -1
		self.configurationSaveWindow = None

	def __LoadWindow(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/switchbot.py")
		except:
			import exception
			exception.Abort("SwitchbotWindow.__LoadWindow.LoadObject")

		try:
			self.titleBar = self.GetChild("TitleBar")
			self.itemSlot = self.GetChild("ItemSlot")
			for i in range(switchbot.SLOT_COUNT):
				self.statusBars[i] = self.GetChild("StatusBar%d" % i)
				self.selectBoxes[i] = self.GetChild("SelectBox%d" % i)
				self.selectButtons[i] = self.GetChild("SelectButton%d" % i)
			for i in range(switchbot.ALTERNATIVE_COUNT):
				self.alternativeButtons[i] = self.GetChild("AlternativeButton%d" % i)
			self.costButtons[switchbot.COST_ITEM] = self.GetChild("CostItemButton")
			self.costButtons[switchbot.COST_YANG] = self.GetChild("CostYangButton")
			self.costText = self.GetChild("CostText")
			self.rareButton = self.GetChild("RareButton")
			self.startstopButton = self.GetChild("StartStopButton")
			self.saveButton = self.GetChild("SaveButton")
			self.premiumStatus = self.GetChild("PremiumStatus")
			self.speedText = self.GetChild("SpeedText")
		except:
			import exception
			exception.Abort("SwitchbotWindow.__LoadWindow.BindObject")

		for i in range(ATTR_SLOT_COUNT + RARE_ATTR_SLOT_COUNT):
			row = self.__MakeAttributeRow()
			row.SetParent(self)
			row.Create(ATTR_ROW_WIDTH, i)
			row.SetPosition(ATTR_ROW_X, INPUT_HEIGHT + INPUT_HEIGHT * i + ATTR_ROW_Y)
			row.Show()
			if IsRareIndex(i):
				self.rareAttrDict[i] = row
			else:
				self.attrDict[i] = row

	def __MakeAttributeRow(self):
		"""A target row (a seam: NovaUI makes rows on proxies)."""
		return SwitchbotAttribute()

	def __MakeSearchList(self):
		"""The attribute search list (a seam: NovaUI shows it in its board)."""
		return SearchListWindow()

	def __MakeConfigurationWindow(self):
		"""The saved configurations (a seam: NovaUI shows them in its board)."""
		return ConfigurationWindow(self)

	def __BindEvents(self):
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))

		self.itemSlot.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		self.itemSlot.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		self.itemSlot.SetSelectEmptySlotEvent(ui.__mem_func__(self.SelectEmptySlot))
		self.itemSlot.SetSelectItemSlotEvent(ui.__mem_func__(self.SelectItemSlot))
		self.itemSlot.SetUnselectItemSlotEvent(ui.__mem_func__(self.UseItemSlot))
		self.itemSlot.SetUseSlotEvent(ui.__mem_func__(self.UseItemSlot))

		for i in range(switchbot.SLOT_COUNT):
			self.selectButtons[i].SetEvent(ui.__mem_func__(self.SelectSlot), i)
		for i in range(switchbot.ALTERNATIVE_COUNT):
			self.alternativeButtons[i].SetEvent(ui.__mem_func__(self.SelectAlternative), i)
		for cost, button in self.costButtons.items():
			button.SetEvent(ui.__mem_func__(self.SelectCost), cost)

		self.rareButton.SetToggleDownEvent(lambda arg=1: self.setIsRare(arg))
		self.rareButton.SetToggleUpEvent(lambda arg=0: self.setIsRare(arg))
		self.startstopButton.SetEvent(ui.__mem_func__(self.SetActive))
		self.saveButton.SetToolTipText(localeInfo.SWITCHBOT_SAVE_BUTTON)
		self.saveButton.SetEvent(ui.__mem_func__(self.OpenSaveConfiguration))

		for row in list(self.attrDict.values()):
			row.SetSearchEvent(ui.__mem_func__(self.__OnSearchAttribute))
			row.SetAttributeUpdateEvent(ui.__mem_func__(self.__OnAttributeUpdate))
			row.SetEscapeEvent(ui.__mem_func__(self.Close))
			row.EnableRow()
		for row in list(self.rareAttrDict.values()):
			row.SetSearchEvent(ui.__mem_func__(self.__OnSearchRareAttribute))
			row.SetAttributeUpdateEvent(ui.__mem_func__(self.__OnAttributeUpdate))
			row.SetEscapeEvent(ui.__mem_func__(self.Close))
			row.EnableRow()

		self.SelectCost(self.cost)
		self.SelectSlot(0)

	def Destroy(self):
		if self.attributeSearchWindow:
			self.attributeSearchWindow.Close()
		if self.configurationSaveWindow:
			self.configurationSaveWindow.Close()
		self.ClearDictionary()
		self.__Initialize()

	def SetItemToolTip(self, tooltipItem):
		self.tooltipItem = tooltipItem

	## --- open and close --------------------------------------------------------------

	def Open(self):
		self.Show()
		self.SetTop()
		self.SetCenterPosition()
		self.RefreshSwitchbotWindow()

	def Close(self):
		if self.attributeSearchWindow:
			self.attributeSearchWindow.Close()

		if self.configurationSaveWindow:
			self.configurationSaveWindow.Close()

		self.OverOutItem()
		self.Hide()
		return True

	def OnPressEscapeKey(self):
		self.Close()
		return True

	## --- the item tabs (OLD's SwitchbotItemTab, one slot window for six) ---------

	def OverInItem(self, slot):
		self.itemSlot.SetUsableItem(True)

		if self.IsEmpty(slot) or not self.tooltipItem:
			return

		## NEW's tooltip reads an item of any window (OLD built it from the
		## item's sockets and bonuses here).
		self.tooltipItem.SetInventoryItem(slot, player.SWITCHBOT)

	def OverOutItem(self):
		if self.itemSlot:
			self.itemSlot.SetUsableItem(False)
		if self.tooltipItem:
			self.tooltipItem.HideToolTip()

	def SelectEmptySlot(self, slot):
		"""A drop on an empty tab moves the attached item there (OLD :174-197;
		the extra inventory is NEW's); a press with nothing attached selects
		the tab."""
		if constInfo.GET_ITEM_QUESTION_DIALOG_STATUS() == 1:
			return

		if mouseModule.mouseController.isAttached():
			attachedSlotType = mouseModule.mouseController.GetAttachedType()
			attachedSlotPos = mouseModule.mouseController.GetAttachedSlotNumber()
			attachedItemCount = mouseModule.mouseController.GetAttachedItemCount()

			if player.SLOT_TYPE_INVENTORY == attachedSlotType:
				net.SendItemMovePacket(player.INVENTORY, attachedSlotPos, player.SWITCHBOT, slot, attachedItemCount)
			elif player.SLOT_TYPE_EXTRA_INVENTORY == attachedSlotType:
				net.SendItemMovePacket(player.EXTRA_INVENTORY, attachedSlotPos, player.SWITCHBOT, slot, attachedItemCount)
			elif player.SLOT_TYPE_SWITCHBOT == attachedSlotType:
				net.SendItemMovePacket(player.SWITCHBOT, attachedSlotPos, player.SWITCHBOT, slot, attachedItemCount)

			mouseModule.mouseController.DeattachObject()

		self.SelectSlot(slot)

	def SelectItemSlot(self, slot):
		"""A press on an item (OLD :199-219): Alt pastes its link, otherwise it
		is picked up unless its slot is rolling; the tab is selected."""
		if constInfo.GET_ITEM_QUESTION_DIALOG_STATUS() == 1:
			return

		self.SelectSlot(slot)

		if switchbot.IsActive(slot):
			return

		if mouseModule.mouseController.isAttached():
			mouseModule.mouseController.DeattachObject()
		elif app.IsPressed(app.DIK_LALT):
			link_tokens.paste(player.GetItemLink(player.SWITCHBOT, slot))
		else:
			itemVnum = player.GetItemIndex(player.SWITCHBOT, slot)
			itemCount = player.GetItemCount(player.SWITCHBOT, slot)
			mouseModule.mouseController.AttachObject(self, player.SLOT_TYPE_SWITCHBOT, slot, itemVnum, itemCount)

	def UseItemSlot(self, slot):
		"""A right click sends the item back to the inventory: the server moves
		an idle switchbot item to the first free cell (OLD :221-231)."""
		if app.SELL == app.GetCursor():
			return

		if constInfo.GET_ITEM_QUESTION_DIALOG_STATUS() == 1:
			return

		net.SendItemUsePacket(player.SWITCHBOT, slot)
		mouseModule.mouseController.DeattachObject()
		self.OverOutItem()

	def IsEmpty(self, slot):
		return not player.GetItemIndex(player.SWITCHBOT, slot)

	def RefreshItemSlot(self, slot):
		"""OLD's SwitchbotItemTab.RefreshItemSlot: the item, its tab's state
		color and the rolling slot's effect."""
		if self.IsEmpty(slot):
			switchbot.ClearSlot(slot)
			self.itemSlot.ClearSlot(slot)
			self.itemSlot.DeactivateSlot(slot)
			self.statusBars[slot].Hide()
			return

		itemCount = player.GetItemCount(player.SWITCHBOT, slot)
		itemVnum = player.GetItemIndex(player.SWITCHBOT, slot)
		if itemCount == 1:
			itemCount = 0
		self.itemSlot.SetItemSlot(slot, itemVnum, itemCount)

		self.statusBars[slot].Show()
		if switchbot.IsActive(slot):
			self.itemSlot.ActivateSlot(slot)
			self.statusBars[slot].SetColor(COLOR_ACTIVE)
		else:
			self.itemSlot.DeactivateSlot(slot)
			if switchbot.IsFinished(slot):
				self.statusBars[slot].SetColor(COLOR_FINISHED)
			else:
				self.statusBars[slot].SetColor(COLOR_INACTIVE)

	## --- selection -------------------------------------------------------------------

	def SelectSlot(self, selectedSlot):
		self.selectButtons[self.selectedSlot].SetUp()
		self.selectBoxes[self.selectedSlot].Hide()
		self.selectedSlot = selectedSlot
		self.selectButtons[self.selectedSlot].Down()
		self.selectBoxes[self.selectedSlot].Show()

		if switchbot.IsAuraSlot(self.selectedSlot):
			self.rareButton.Hide()
			self.setIsRare(0)
		else:
			self.rareButton.Show()
			if switchbot.IsActive(self.selectedSlot):
				self.setIsRare(1 if switchbot.IsRare(self.selectedSlot) else 0)

		self.SelectAlternative(0)

	def GetSelectedSlot(self):
		return self.selectedSlot

	def SelectAlternative(self, alternative):
		self.alternativeButtons[self.alternative].SetUp()
		self.alternative = alternative
		self.alternativeButtons[self.alternative].Down()

		self.RefreshSwitchbotWindow()

	def SelectCost(self, cost):
		"""The cost of a roll (NOVA-43 Q3 c), for the next start."""
		self.cost = cost
		for key, button in self.costButtons.items():
			if key == cost:
				button.Down()
			else:
				button.SetUp()
		self.__RefreshCost()

	def setIsRare(self, arg):
		if arg == 1:
			self.showRare()
		else:
			self.hideRare()

	def showRare(self):
		self.isRare = True
		if not self.rareButton.IsDown():
			self.rareButton.Down()
		for row in self.rareAttrDict.values():
			row.EnableRow()
		for row in self.attrDict.values():
			row.DisableRow()

	def hideRare(self):
		self.isRare = False
		if self.rareButton.IsDown():
			self.rareButton.SetUp()
		for row in self.rareAttrDict.values():
			row.DisableRow()
		for row in self.attrDict.values():
			row.EnableRow()

	## --- start and stop ------------------------------------------------------------

	def SetActive(self):
		if self.selectedSlot >= switchbot.SLOT_COUNT:
			return

		if self.IsActiveSlot():
			switchbot.Stop(self.selectedSlot)
		else:
			switchbot.Start(self.selectedSlot, 1 if self.isRare else 0, self.cost)

	## --- refresh (C's GC::SWITCHBOT and the item packets of window SWITCHBOT) ---

	def RefreshSwitchbotWindow(self):
		for i in range(switchbot.SLOT_COUNT):
			self.RefreshItemSlot(i)
		self.itemSlot.RefreshSlot()
		self.__RefreshAlternatives()
		self.__RefreshAttributeRows()
		self.__RefreshButtons()
		self.__RefreshCost()
		self.__RefreshPremium()
		if self.isRare:
			self.showRare()
		else:
			self.hideRare()

	def RefreshSwitchbotItem(self, slot):
		if slot not in self.statusBars:
			return
		self.RefreshItemSlot(slot)
		self.itemSlot.RefreshSlot()
		if slot == self.selectedSlot:
			self.__RefreshAttributeRows()
			self.__RefreshButtons()

	def __RefreshAlternatives(self):
		for i in range(switchbot.ALTERNATIVE_COUNT):
			if self.IsEmptySlot():
				self.alternativeButtons[i].Hide()
			else:
				self.alternativeButtons[i].Show()

	def __RefreshAttributeRows(self):
		for rows in (self.attrDict, self.rareAttrDict):
			for i, row in rows.items():
				(applyType, applyValue) = player.GetItemAttribute(player.SWITCHBOT, self.selectedSlot, i)
				if applyType and applyValue:
					row.Show()
				else:
					row.Hide()
				row.RefreshAttributeRow(self.selectedSlot, self.alternative, i)

	def __AnyAttributeConfigured(self):
		for alternative in range(switchbot.ALTERNATIVE_COUNT):
			for index in range(ATTR_SLOT_COUNT + RARE_ATTR_SLOT_COUNT):
				(attrType, attrValue) = GetTarget(self.selectedSlot, alternative, index)
				if attrType and attrValue:
					return True
		return False

	def __RefreshButtons(self):
		active = self.IsActiveSlot()
		for button in self.costButtons.values():
			if active:
				button.Disable()
			else:
				button.Enable()
		self.startstopButton.SetText(localeInfo.SWITCHBOT_STOP if active else localeInfo.SWITCHBOT_START)
		if self.IsEmptySlot() or not self.__AnyAttributeConfigured():
			self.startstopButton.Disable()
		else:
			self.startstopButton.Enable()

	def __RefreshCost(self):
		"""The cost line: a rolling slot shows the cost it was started with."""
		if not self.costText:
			return
		cost = self.cost
		if self.IsActiveSlot():
			cost = switchbot.GetCost(self.selectedSlot)
			for key, button in self.costButtons.items():
				if key == cost:
					button.Down()
				else:
					button.SetUp()
		if cost == switchbot.COST_YANG:
			self.costText.SetText(localeInfo.SWITCHBOT_COST_YANG_INFO % localeInfo.NumberToMoneyString(switchbot.GetYangPrice()))
		else:
			self.costText.SetText(localeInfo.SWITCHBOT_COST_ITEM_INFO)

	def __RefreshPremium(self):
		"""OLD's premium line (its OnUpdate polled player.IsPremiumUser()): the
		faster roll is the premium perk (NOVA-43 Q2), and the server says
		which interval this player rolls at."""
		rollMs = switchbot.GetRollMs() or NORMAL_ROLL_MS
		if rollMs < NORMAL_ROLL_MS:
			self.premiumStatus.SetPackedFontColor(0xff4ba136)
			self.premiumStatus.SetText(localeInfo.SWITCHBOT_PREMIUM_ACTIVE)
		else:
			self.premiumStatus.SetPackedFontColor(0xff9c262b)
			self.premiumStatus.SetText(localeInfo.SWITCHBOT_PREMIUM_INACTIVE)
		self.speedText.SetText(localeInfo.SWITCHBOT_SPEED % (rollMs / 1000.0))

	def __OnAttributeUpdate(self, attrIdx):
		self.__RefreshButtons()

	def IsEmptySlot(self):
		return self.IsEmpty(self.selectedSlot)

	def IsActiveSlot(self):
		return bool(switchbot.IsActive(self.selectedSlot))

	## --- the attribute search list (OLD :849-984) -----------------------------------

	def __OpenSearchList(self, attrIdx, attributes, selected, acceptEvent):
		if self.attributeSearchWindow:
			self.attributeSearchWindow.Close()
			self.attributeSearchWindow = None

		self.attrSearchIdx = attrIdx

		wnd = self.__MakeSearchList()
		width = 260
		height = 260
		wnd.MakeWindow(width, height)
		wnd.SetTitleName(localeInfo.SWITCHBOT_SELECT_ATTR)
		wnd.SetAcceptArgsType("KEY_VALUE")

		(mouseX, mouseY) = wndMgr.GetMousePosition()
		xPos = min(max(0, mouseX - width // 2), max(0, wndMgr.GetScreenWidth() - width))
		yPos = min(max(0, mouseY - height // 2), max(0, wndMgr.GetScreenHeight() - height))
		wnd.SetPosition(xPos, yPos)

		addons = AddonTypes()
		firstAttrType = player.GetItemAttribute(player.SWITCHBOT, self.selectedSlot, 0)[0]
		if firstAttrType in addons:
			for addonType in sorted(addons):
				affectString = GetAffectString(addonType, addons[addonType])
				if affectString:
					wnd.AppendItem(addonType, affectString)

		for (attrType, attrValue) in attributes:
			if attrType in selected:
				continue
			affectString = GetAffectString(attrType, attrValue)
			if not affectString:
				continue
			wnd.AppendItem(attrType, affectString)

		wnd.SetAcceptEvent(acceptEvent)
		wnd.SetCancelEvent(ui.__mem_func__(self.__OnCancelSearch))
		wnd.SetTop()
		wnd.Open()

		self.attributeSearchWindow = wnd

	def __OnSearchAttribute(self, attrIdx):
		if switchbot.IsAuraSlot(self.selectedSlot):
			attributes = switchbot.GetAuraAttributesForSet(self.selectedSlot)
		else:
			attributes = switchbot.GetAttributesForSet(self.selectedSlot)
		selected = [switchbot.GetAttribute(self.selectedSlot, self.alternative, i)[0] for i in range(ATTR_SLOT_COUNT)]
		self.__OpenSearchList(attrIdx, attributes, selected, ui.__mem_func__(self.__OnAcceptSearch))

	def __OnSearchRareAttribute(self, attrIdx):
		attributes = switchbot.GetRareAttributesForSet(self.selectedSlot)
		selected = [switchbot.GetRareAttributeByIndex(self.selectedSlot, self.alternative, i)[0]
		            for i in range(ATTR_SLOT_COUNT, ATTR_SLOT_COUNT + RARE_ATTR_SLOT_COUNT)]
		self.__OpenSearchList(attrIdx, attributes, selected, ui.__mem_func__(self.__OnAcceptRareSearch))

	def __AcceptSearch(self, rows, key, value):
		attrRow = rows.get(self.attrSearchIdx, None)
		if not attrRow:
			return

		maxValue = GetMaxValue(self.selectedSlot, self.attrSearchIdx, key)
		attrRow.SetAttribute(value, maxValue)
		SetTarget(self.selectedSlot, self.alternative, self.attrSearchIdx, key, maxValue)
		self.__RefreshButtons()

	def __OnAcceptSearch(self, key, value):
		self.__AcceptSearch(self.attrDict, key, value)

	def __OnAcceptRareSearch(self, key, value):
		self.__AcceptSearch(self.rareAttrDict, key, value)

	def __OnCancelSearch(self):
		pass

	## --- the saved configurations (OLD :1474-1764) ---------------------------------

	def OpenSaveConfiguration(self):
		if not self.configurationSaveWindow:
			self.configurationSaveWindow = self.__MakeConfigurationWindow()

		if self.configurationSaveWindow.IsShow():
			self.configurationSaveWindow.Close()
		else:
			self.configurationSaveWindow.Open()

	def SetSavedAttribute(self, slot, alternative, attrIndex, attrType, attrValue):
		"""A saved target (OLD :1012-1076, both kinds): kept only where the
		item's set has the bonus."""
		if attrIndex < 0 or attrIndex >= ATTR_SLOT_COUNT + RARE_ATTR_SLOT_COUNT:
			return
		if slot >= switchbot.SLOT_COUNT or switchbot.IsActive(slot):
			return

		if IsRareIndex(attrIndex):
			found = switchbot.GetRareAttributesForSet(slot)
		elif switchbot.IsAuraSlot(slot):
			found = switchbot.GetAuraAttributesForSet(slot)
		else:
			found = switchbot.GetAttributesForSet(slot)
		attributes = [entry[0] for entry in found]

		firstAttrType = player.GetItemAttribute(player.SWITCHBOT, slot, 0)[0]
		addons = AddonTypes()
		if firstAttrType in addons:
			attributes.extend(addons)

		if attrType not in attributes:
			SetTarget(slot, alternative, attrIndex, 0, 0)
		else:
			SetTarget(slot, alternative, attrIndex, attrType, attrValue)

		self.RefreshSwitchbotWindow()

	def OnMoveWindow(self, x, y):
		if self.configurationSaveWindow:
			self.configurationSaveWindow.AdjustPosition()


class SearchListWindow(ui.BoardWithTitleBar):
	"""OLD's SearchListWindow: a filter field over a list of bonuses."""

	class SearchListItem(ui.ListBoxEx.Item):
		LIST_ITEM_HEIGHT = 16

		def __init__(self, key, value):
			ui.ListBoxEx.Item.__init__(self)
			self.key = key
			self.value = value
			self.textLine = ui.TextLine()
			self.textLine.AddFlag("not_pick")
			self.textLine.SetParent(self)
			self.textLine.SetPosition(10, 1)
			self.textLine.SetText(str(value))
			self.textLine.Show()

		def __del__(self):
			ui.ListBoxEx.Item.__del__(self)

		def GetKey(self):
			return self.key

		def GetValue(self):
			return self.value

	def __init__(self):
		ui.BoardWithTitleBar.__init__(self)
		self.AddFlag("movable")
		self.AddFlag("float")
		self.listItems = {}
		self.order = []
		self.acceptEvent = None
		self.acceptArgsType = "VALUE"
		self.cancelEvent = None
		self.searchEditLine = None
		self.listBox = None

	def __del__(self):
		ui.BoardWithTitleBar.__del__(self)

	def MakeWindow(self, width, height, maxInput=50):
		self.SetSize(width, height)
		self.SetCloseEvent(ui.__mem_func__(self.Close))

		self.searchInput = ui.ThinBoard()
		self.searchInput.SetParent(self)
		self.searchInput.SetSize(width - 20, INPUT_HEIGHT)
		self.searchInput.SetPosition(10, BORDER_SPACE_TOP)
		self.searchInput.Show()

		self.searchEditLine = ui.EditLine()
		self.searchEditLine.SetParent(self.searchInput)
		self.searchEditLine.SetPosition(10, 8)
		self.searchEditLine.SetSize(width - 40, 14)
		self.searchEditLine.SetMax(maxInput)
		self.searchEditLine.SetReturnEvent(ui.__mem_func__(self.__OnAccept))
		self.searchEditLine.SetEscapeEvent(ui.__mem_func__(self.Close))
		self.searchEditLine.OnIMEUpdate = ui.__mem_func__(self.__OnSearchIMEUpdate)
		self.searchEditLine.Show()

		self.scrollBar = ui.ScrollBar()
		self.scrollBar.SetParent(self)
		self.scrollBar.SetPosition(width - 26, BORDER_SPACE_TOP + INPUT_HEIGHT + 2)
		self.scrollBar.SetScrollBarSize(height - BORDER_SPACE_TOP - INPUT_HEIGHT - 40)

		self.listBox = ui.ListBoxEx()
		self.listBox.SetParent(self)
		self.listBox.SetPosition(12, BORDER_SPACE_TOP + INPUT_HEIGHT + 2)
		self.listBox.SetItemStep(self.SearchListItem.LIST_ITEM_HEIGHT)
		self.listBox.SetItemSize(width - 40, self.SearchListItem.LIST_ITEM_HEIGHT)
		self.listBox.SetViewItemCount((height - BORDER_SPACE_TOP - INPUT_HEIGHT - 40) // self.SearchListItem.LIST_ITEM_HEIGHT)
		self.listBox.SetScrollBar(self.scrollBar)
		self.listBox.Show()

		self.acceptButton = ui.Button()
		self.acceptButton.SetParent(self)
		self.acceptButton.SetUpVisual("d:/ymir work/ui/public/middle_button_01.sub")
		self.acceptButton.SetOverVisual("d:/ymir work/ui/public/middle_button_02.sub")
		self.acceptButton.SetDownVisual("d:/ymir work/ui/public/middle_button_03.sub")
		self.acceptButton.SetPosition(width // 2 - 66, height - 30)
		self.acceptButton.SetText(localeInfo.UI_ACCEPT)
		self.acceptButton.SetEvent(ui.__mem_func__(self.__OnAccept))
		self.acceptButton.Show()

		self.cancelButton = ui.Button()
		self.cancelButton.SetParent(self)
		self.cancelButton.SetUpVisual("d:/ymir work/ui/public/middle_button_01.sub")
		self.cancelButton.SetOverVisual("d:/ymir work/ui/public/middle_button_02.sub")
		self.cancelButton.SetDownVisual("d:/ymir work/ui/public/middle_button_03.sub")
		self.cancelButton.SetPosition(width // 2 + 5, height - 30)
		self.cancelButton.SetText(localeInfo.UI_CANCEL)
		self.cancelButton.SetEvent(ui.__mem_func__(self.__OnCancel))
		self.cancelButton.Show()

	def __OnSearchIMEUpdate(self):
		ui.EditLine.OnIMEUpdate(self.searchEditLine)
		self.__RefreshListBox()

	def AppendItem(self, key, value=""):
		if key in self.listItems:
			return
		self.listItems[key] = value or str(key)
		self.order.append(key)
		self.__RefreshListBox()

	def VisibleItems(self):
		"""(key, value) in list order, filtered by the search text."""
		text = self.searchEditLine.GetText().lower() if self.searchEditLine else ""
		return [(key, self.listItems[key]) for key in self.order if not text or text in self.listItems[key].lower()]

	def __RefreshListBox(self):
		self.listBox.RemoveAllItems()
		for key, value in self.VisibleItems():
			self.listBox.AppendItem(self.MakeItem(key, value))

	def MakeItem(self, key, value):
		"""A list line (a seam: NovaUI's lines are data)."""
		return self.SearchListItem(key, value)

	def SetCancelEvent(self, event):
		self.cancelEvent = event

	def SetAcceptEvent(self, event):
		self.acceptEvent = event

	def SetAcceptArgsType(self, argsType):
		self.acceptArgsType = argsType

	def Accept(self, key, value):
		if self.acceptEvent:
			if self.acceptArgsType == "VALUES":
				self.acceptEvent(value)
			elif self.acceptArgsType == "KEY":
				self.acceptEvent(key)
			elif self.acceptArgsType == "KEY_VALUE":
				self.acceptEvent(key, value)
		self.Close()

	def __OnAccept(self):
		selItem = self.listBox.GetSelectedItem()
		if not selItem:
			visible = self.VisibleItems()
			if len(visible) != 1:
				return
			self.Accept(visible[0][0], visible[0][1])
			return
		self.Accept(selItem.GetKey(), selItem.GetValue())

	def __OnCancel(self):
		if self.cancelEvent:
			self.cancelEvent()
		self.Close()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def Open(self):
		self.Show()
		self.searchEditLine.SetFocus()

	def Close(self):
		if self.searchEditLine:
			self.searchEditLine.SetText("")
			self.searchEditLine.KillFocus()
		self.Hide()


def LoadConfigurations():
	"""The saved configurations, {key: {"name", "alternatives"}} (OLD's
	switchbot.pkl beside the client)."""
	try:
		with open(CONFIG_FILE, "rb") as handle:
			data = pickle.load(handle)
	except Exception:
		return {}
	return data if isinstance(data, dict) else {}


def SaveConfigurations(data):
	try:
		with open(CONFIG_FILE, "wb") as handle:
			pickle.dump(data, handle, 2)
	except Exception:
		pass


class ConfigurationWindow(ui.BoardWithTitleBar):
	"""OLD's ConfigurationWindow: the saved target sets beside the window,
	saved under a name and applied to the selected slot."""

	BOARD_WIDTH = 250
	BOARD_HEIGHT = 400
	LINE_HEIGHT = 26

	class ConfigurationLine(ui.ListBoxEx.Item):
		def __init__(self, width):
			ui.ListBoxEx.Item.__init__(self)
			self.id = 0
			self.name = ""
			self.loadEvent = None
			self.deleteEvent = None
			self.SetSize(width, ConfigurationWindow.LINE_HEIGHT)

			self.nameTextLine = ui.TextLine()
			self.nameTextLine.SetParent(self)
			self.nameTextLine.SetPosition(5, 6)
			self.nameTextLine.Show()

			self.loadButton = ui.Button()
			self.loadButton.SetParent(self)
			self.loadButton.SetUpVisual("d:/ymir work/ui/public/small_button_01.sub")
			self.loadButton.SetOverVisual("d:/ymir work/ui/public/small_button_02.sub")
			self.loadButton.SetDownVisual("d:/ymir work/ui/public/small_button_03.sub")
			self.loadButton.SetPosition(width - 90, 3)
			self.loadButton.SetText(localeInfo.SWITCHBOT_LOAD_CONFIGURATION)
			self.loadButton.SetEvent(ui.__mem_func__(self.__OnClickLoadButton))
			self.loadButton.Show()

			self.deleteButton = ui.Button()
			self.deleteButton.SetParent(self)
			self.deleteButton.SetUpVisual("d:/ymir work/ui/public/small_button_01.sub")
			self.deleteButton.SetOverVisual("d:/ymir work/ui/public/small_button_02.sub")
			self.deleteButton.SetDownVisual("d:/ymir work/ui/public/small_button_03.sub")
			self.deleteButton.SetPosition(width - 46, 3)
			self.deleteButton.SetText(localeInfo.SWITCHBOT_CLEAR_CONFIGURATION)
			self.deleteButton.SetEvent(ui.__mem_func__(self.__OnClickDeleteButton))
			self.deleteButton.Show()

		def __del__(self):
			ui.ListBoxEx.Item.__del__(self)

		def Load(self, id, name):
			self.id = id
			self.name = name
			self.nameTextLine.SetText(name)

		def SetLoadEvent(self, event):
			self.loadEvent = event

		def SetDeleteEvent(self, event):
			self.deleteEvent = event

		def __OnClickLoadButton(self):
			if self.loadEvent:
				self.loadEvent(self.id)

		def __OnClickDeleteButton(self):
			if self.deleteEvent:
				self.deleteEvent(self.id)

	def __init__(self, wndSwitchbot):
		ui.BoardWithTitleBar.__init__(self)
		self.wndSwitchbot = wndSwitchbot
		self.dict = {}
		self.__LoadWindow()

	def __del__(self):
		ui.BoardWithTitleBar.__del__(self)

	def __LoadWindow(self):
		self.SetSize(self.BOARD_WIDTH, self.BOARD_HEIGHT)
		self.SetTitleName(localeInfo.SWITCHBOT_CONFIGURATION_TITLE)
		self.SetCloseEvent(ui.__mem_func__(self.Close))
		self.AddFlag("float")

		self.saveButton = ui.Button()
		self.saveButton.SetParent(self)
		self.saveButton.SetUpVisual("d:/ymir work/ui/public/small_button_01.sub")
		self.saveButton.SetOverVisual("d:/ymir work/ui/public/small_button_02.sub")
		self.saveButton.SetDownVisual("d:/ymir work/ui/public/small_button_03.sub")
		self.saveButton.SetPosition(self.BOARD_WIDTH - 58, BORDER_SPACE_TOP + 3)
		self.saveButton.SetText(localeInfo.SWITCHBOT_SAVE)
		self.saveButton.SetEvent(ui.__mem_func__(self.Save))
		self.saveButton.Show()

		self.nameInput = ui.ThinBoard()
		self.nameInput.SetParent(self)
		self.nameInput.SetSize(self.BOARD_WIDTH - 80, INPUT_HEIGHT)
		self.nameInput.SetPosition(12, BORDER_SPACE_TOP)
		self.nameInput.Show()

		self.nameEditLine = ui.EditLine()
		self.nameEditLine.SetParent(self.nameInput)
		self.nameEditLine.SetSize(self.BOARD_WIDTH - 100, 18)
		self.nameEditLine.SetMax(32)
		self.nameEditLine.SetPosition(10, 7)
		self.nameEditLine.SetEscapeEvent(ui.__mem_func__(self.Close))
		self.nameEditLine.Show()

		self.listBox = ui.ListBoxEx()
		self.listBox.SetParent(self)
		self.listBox.SetPosition(12, BORDER_SPACE_TOP + INPUT_HEIGHT + 4)
		self.listBox.SetItemStep(self.LINE_HEIGHT + 1)
		self.listBox.SetItemSize(self.BOARD_WIDTH - 24, self.LINE_HEIGHT)
		self.listBox.SetViewItemCount((self.BOARD_HEIGHT - BORDER_SPACE_TOP - INPUT_HEIGHT - 20) // (self.LINE_HEIGHT + 1))
		self.listBox.Show()

	def LoadConfigurations(self):
		self.dict = LoadConfigurations()
		self.listBox.RemoveAllItems()
		for key in sorted(self.dict):
			config = self.dict.get(key, None)
			if not config:
				continue
			line = self.MakeLine(self.BOARD_WIDTH - 24)
			line.Load(key, config["name"])
			line.SetLoadEvent(ui.__mem_func__(self.ApplyConfiguration))
			line.SetDeleteEvent(ui.__mem_func__(self.DeleteConfiguration))
			self.listBox.AppendItem(line)

	def MakeLine(self, width):
		"""A saved configuration's line (a seam: NovaUI's lines are data)."""
		return self.ConfigurationLine(width)

	def Entries(self):
		"""(key, name) of every saved configuration, in key order."""
		return [(key, self.dict[key]["name"]) for key in sorted(self.dict) if self.dict.get(key)]

	def ApplyConfiguration(self, key):
		config = self.dict.get(key, None)
		if not config or not self.wndSwitchbot:
			return

		selectedSlot = self.wndSwitchbot.GetSelectedSlot()
		for alternativeIdx, alternative in enumerate(config["alternatives"]):
			for attrIdx, (attrType, attrValue) in enumerate(alternative):
				self.wndSwitchbot.SetSavedAttribute(selectedSlot, alternativeIdx, attrIdx, attrType, attrValue)

	def DeleteConfiguration(self, key):
		if key not in self.dict:
			return
		del self.dict[key]
		SaveConfigurations(self.dict)
		self.LoadConfigurations()

	def Open(self):
		self.Show()
		self.LoadConfigurations()
		self.AdjustPosition()

	def Close(self):
		self.nameEditLine.KillFocus()
		self.Hide()

	def AdjustPosition(self):
		if not self.wndSwitchbot:
			return
		(x, y) = self.wndSwitchbot.GetGlobalPosition()
		self.SetPosition(x - self.GetWidth(), y)

	def __GetNewKey(self):
		key = 0
		while key in self.dict:
			key += 1
		return key

	def Save(self):
		"""Saves the selected slot's three target sets under the typed name."""
		if not self.wndSwitchbot:
			return

		name = self.nameEditLine.GetText()
		if not name:
			return

		slot = self.wndSwitchbot.GetSelectedSlot()
		alternatives = []
		for alternative in range(switchbot.ALTERNATIVE_COUNT):
			alternatives.append([tuple(GetTarget(slot, alternative, i)) for i in range(ATTR_SLOT_COUNT + RARE_ATTR_SLOT_COUNT)])

		self.dict[self.__GetNewKey()] = {"name": name, "alternatives": alternatives}
		self.nameEditLine.SetText("")
		SaveConfigurations(self.dict)
		self.LoadConfigurations()
