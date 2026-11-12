## Fast equip (NOVA-17): OLD's root/uiFastEquip.py (__NEW_FAST_EQUIP__, live
## through game.py:506, 2496-2498, interfaceModule.py:93, 186, 520-524, 1564,
## 1763, uiInventory.py:1176, 2653, 2725) on NEW's data. The server keeps each
## set by item id, per wear cell; C's fastEquip module holds what
## GC::FAST_EQUIP last said. This window shows the 10 sets on the left and the
## selected set's wear cells on OLD's positions, and saves through
## fastEquip.SendSave.
##
## Kept from OLD: the 10 named and colored sets, the 12-color edit popup with
## its 15-character name, Switch, Clear, the equipped indicator, the cell
## layout and the slot filter by item type.
## Changed:
## - A set is keyed by wear index (OLD's 26 named columns), so all 40 cells
##   fit; a cell the server cannot use today is not drawn, driven by
##   fastEquip.IsUsableCell, so it appears when its feature ships.
## - A save sends SLOT_KEEP for every cell but the one that changed, and a
##   rename all SLOT_KEEP: a stale (window, cell) of an item the player moved
##   can never overwrite a set (OLD resent every cell it last knew).
## - Items are named by (window, cell), so the extra inventory resolves right
##   (OLD sent a bare main-inventory cell).
## - Shift-click switches the clicked set (OLD switched the previously
##   selected one, SelectSet).
## - A refresh is asked once per 500 ms at most, while the window shows, with
##   a trailing one for what changed in between (OLD asked on every inventory
##   refresh and the server answered with a blocking SELECT).
## - OLD's art under d:/ymir work/ui/fastequip is not shipped: NEW's public
##   board, slots and buttons stand in.
## - Eddy (r41): a drop anywhere on the set's cells goes to the cell the item
##   is worn on (FindSetCell, the server's CItem::FindEquipCell), and an item
##   that cannot be worn there is refused with a chat line (OLD dropped it
##   silently). Each cell is its own slot window, so a press between two
##   cells reaches the drop catchers under them (a slot window drops the
##   icon on a press off its slots). The buffi's body and weapon cells are
##   as tall as the costume window's.
import ui
import player
import item
import app
import chr
import chat
import mouseModule
import localeInfo
import uiCommon
import fastEquip

## OLD's COLORS, in order: fastEquip's color 1..12. Color 0 is "none picked".
COLORS = (0xffC41814, 0xff1E5ABA, 0xff32B011, 0xffBC8216, 0xffBC1A43, 0xff0719BB,
          0xff583BB9, 0xff327005, 0xffAD1E90, 0xffB06637, 0xff032473, 0xff7AAE1E)
DEFAULT_SET_COLOR = 0xff181f1a

REFRESH_INTERVAL = 0.5

## Where the slot window sits on the board (OLD's itembg at 108, 63 plus its
## slot window at 3, 3) and its size, tall enough for the added row.
SLOT_X = 111
SLOT_Y = 66
SLOT_WIDTH = 336
SLOT_HEIGHT = 360
SLOT_BASE = "d:/ymir work/ui/public/Slot_Base.sub"
ROW_Y = 256		## the buffi and aura row, under OLD's cells
## The drop catchers' rows of the slot area (top, bottom): OLD's cells, and
## the buffi and aura row; Switch and Clear (the board's 290 to 311) between.
CATCHER_ROWS = ((0, 218), (250, SLOT_HEIGHT))

## wear index: (x, y, width, height), OLD's NewFastEquipWindow positions; the
## buffi and aura cells are NEW's, in their own row under OLD's cells.
CELLS = {
	4: (168, 19, 32, 96),	## weapon
	0: (210, 52, 32, 64),	## armor
	2: (210, 170, 32, 32),	## shoes
	3: (252, 86, 32, 32),	## wrist
	1: (210, 12, 32, 32),	## head
	10: (252, 52, 32, 32),	## shield
	6: (293, 52, 32, 32),	## earrings
	5: (293, 87, 32, 32),	## necklace
	9: (293, 12, 32, 32),	## arrows
	30: (211, 129, 32, 32),	## belt
	28: (168, 129, 32, 32),	## ring 1
	29: (252, 129, 32, 32),	## ring 2
	21: (252, 12, 32, 32),	## sash
	7: (170, 170, 32, 32),	## unique 1
	8: (254, 170, 32, 32),	## unique 2
	19: (53, 54, 32, 64),	## costume body
	20: (53, 5, 32, 32),	## costume hair
	22: (11, 21, 32, 96),	## costume weapon
	27: (97, 54, 32, 32),	## wing (the sash costume)
	36: (95, 5, 32, 32),	## facial
	23: (53, 133, 32, 32),	## mount
	26: (12, 133, 32, 32),	## pet
	24: (2, 181, 32, 32),	## weapon effect 1
	37: (36, 181, 32, 32),	## weapon effect 2
	25: (75, 181, 32, 32),	## body effect 1
	38: (109, 181, 32, 32),	## body effect 2
	## The buffi's three cells as the costume window lays them out (its
	## uiscript's buffi panel): the weapon, then the hair over the body.
	33: (55, ROW_Y + 4, 32, 96),	## buffi weapon
	32: (97, ROW_Y, 32, 32),	## buffi hair
	31: (97, ROW_Y + 36, 32, 64),	## buffi body
	39: (235, ROW_Y, 32, 32),	## aura
}
ROW_CELLS = (31, 32, 33, 39)
BUFFI_CELLS = (31, 32, 33)


def IsBuffiCell(wear):
	return wear in BUFFI_CELLS


def _SubTypes(*names):
	values = []
	for name in names:
		value = getattr(item, name, None)
		if isinstance(value, int):
			values.append(value)
	return tuple(values)


def CellRules():
	"""wear index: (item type, subtypes): OLD's SLOT_TYPES by wear index. A
	subtype of the costume features NEW has not ported is absent, so nothing
	drops on its cell."""
	weapons = _SubTypes("WEAPON_SWORD", "WEAPON_DAGGER", "WEAPON_BOW", "WEAPON_TWO_HANDED",
		"WEAPON_BELL", "WEAPON_FAN", "WEAPON_CLAW")
	arrows = _SubTypes("WEAPON_ARROW", "WEAPON_UNLIMITED_ARROW")
	armor = getattr(item, "ITEM_TYPE_ARMOR", None)
	costume = getattr(item, "ITEM_TYPE_COSTUME", None)
	ring = getattr(item, "ITEM_TYPE_RING", None)
	belt = getattr(item, "ITEM_TYPE_BELT", None)
	unique = getattr(item, "ITEM_TYPE_UNIQUE", None)
	weaponType = getattr(item, "ITEM_TYPE_WEAPON", None)
	costumeBody, costumeHair, costumeWeapon = _SubTypes("COSTUME_TYPE_BODY"), _SubTypes("COSTUME_TYPE_HAIR"), _SubTypes("COSTUME_TYPE_WEAPON")
	return {
		4: (weaponType, weapons), 0: (armor, _SubTypes("ARMOR_BODY")), 2: (armor, _SubTypes("ARMOR_FOOTS")),
		3: (armor, _SubTypes("ARMOR_WRIST")), 1: (armor, _SubTypes("ARMOR_HEAD")), 10: (armor, _SubTypes("ARMOR_SHIELD")),
		6: (armor, _SubTypes("ARMOR_EAR")), 5: (armor, _SubTypes("ARMOR_NECK")), 9: (weaponType, arrows),
		30: (belt, None), 28: (ring, None), 29: (ring, None), 21: (costume, _SubTypes("COSTUME_TYPE_SASH")),
		7: (unique, None), 8: (unique, None), 19: (costume, costumeBody), 20: (costume, costumeHair),
		22: (costume, costumeWeapon), 27: (costume, _SubTypes("COSTUME_TYPE_SASH2")),
		36: (costume, _SubTypes("COSTUME_TYPE_FACIAL")), 23: (costume, _SubTypes("COSTUME_TYPE_MOUNT")),
		26: (costume, _SubTypes("COSTUME_TYPE_PET")), 24: (costume, _SubTypes("COSTUME_TYPE_EFFECT_WEAPON")),
		37: (costume, _SubTypes("COSTUME_TYPE_EFFECT_WEAPON")), 25: (costume, _SubTypes("COSTUME_TYPE_EFFECT_ARMOR")),
		38: (costume, _SubTypes("COSTUME_TYPE_EFFECT_ARMOR")), 31: (costume, costumeBody), 32: (costume, costumeHair),
		33: (costume, costumeWeapon), 39: (costume, _SubTypes("COSTUME_TYPE_AURA")),
	}


def _JobFlags():
	flags = {0: "ITEM_ANTIFLAG_WARRIOR", 1: "ITEM_ANTIFLAG_ASSASSIN", 2: "ITEM_ANTIFLAG_SURA", 3: "ITEM_ANTIFLAG_SHAMAN",
	         4: "ITEM_ANTIFLAG_WOLFMAN"}
	return dict((job, getattr(item, name)) for job, name in flags.items() if isinstance(getattr(item, name, None), int))


def FitsCell(wear, vnum):
	"""OLD's filter (uiFastEquip.py SelectEmptySlot), its first half: the
	item's type and subtype are the cell's."""
	item.SelectItem(vnum)
	rule = CellRules().get(wear)
	if rule is None or rule[0] is None or item.GetItemType() != rule[0]:
		return False
	if rule[1] is not None and item.GetItemSubType() not in rule[1]:
		return False
	return True


def CanSitOn(wear, vnum):
	"""OLD's filter (uiFastEquip.py SelectEmptySlot), per wear cell: the item's
	type and subtype, its job and its sex. The server checks again; this keeps
	a drop that would be refused from being sent."""
	return FitsCell(wear, vnum) and CanWear(wear, vnum)


def CanWear(wear, vnum):
	"""The filter's second half: the character's job and sex (a buffi cell
	dresses the buffi, so it asks neither)."""
	item.SelectItem(vnum)
	if IsBuffiCell(wear):
		return True
	race = player.GetRace()
	job = chr.RaceToJob(race)
	flags = _JobFlags()
	if job not in flags or item.IsAntiFlag(flags[job]):
		return False
	if item.IsAntiFlag(item.ITEM_ANTIFLAG_MALE) and chr.RaceToSex(race) == 1:
		return False
	if item.IsAntiFlag(item.ITEM_ANTIFLAG_FEMALE) and chr.RaceToSex(race) == 0:
		return False
	return True


## Where an item is worn: the server's CItem::FindEquipCell (srv
## src/game/item.cpp:600), which the equipment window's drop goes through.
## Wear flags in its order, then the two-cell kinds.
WEAR_BY_FLAG = (("WEARABLE_BODY", 0), ("WEARABLE_HEAD", 1), ("WEARABLE_FOOTS", 2), ("WEARABLE_WRIST", 3),
	("WEARABLE_WEAPON", 4), ("WEARABLE_SHIELD", 10), ("WEARABLE_NECK", 5), ("WEARABLE_EAR", 6),
	("WEARABLE_ARROW", 9))
RING_CELLS = (28, 29)
UNIQUE_CELLS = (7, 8)
BELT_CELL = 30
COSTUME_CELLS = (("COSTUME_TYPE_BODY", 19), ("COSTUME_TYPE_HAIR", 20), ("COSTUME_TYPE_WEAPON", 22),
	("COSTUME_TYPE_SASH", 21), ("COSTUME_TYPE_SASH2", 27), ("COSTUME_TYPE_AURA", 39))
BUFFI_COSTUME_CELLS = (("COSTUME_TYPE_BODY", 31), ("COSTUME_TYPE_HAIR", 32), ("COSTUME_TYPE_WEAPON", 33))


def _ItemConstant(name):
	value = getattr(item, name, None)
	return value if isinstance(value, int) else None


def WearCells(vnum, target=None):
	"""The wear cells the item is worn on, in the server's order: one, or two
	for a ring or a unique (the first while it is free, else the second), or
	none for what is not worn. A body, hair or weapon costume dropped on the
	buffi's cell of its kind dresses the buffi (the server's candidate cell);
	anywhere else it goes to the owner's cell (the server refuses a costume
	on the buffi's cell of another kind; a drop here finds it its place)."""
	item.SelectItem(vnum)
	itemType = item.GetItemType()
	subType = item.GetItemSubType()
	if itemType == _ItemConstant("ITEM_TYPE_COSTUME"):
		for name, wear in BUFFI_COSTUME_CELLS:
			if wear == target and subType == _ItemConstant(name):
				return (wear,)
		for name, wear in COSTUME_CELLS:
			if subType == _ItemConstant(name):
				return (wear,)
		return ()
	if itemType == _ItemConstant("ITEM_TYPE_RING"):
		return RING_CELLS
	if itemType == _ItemConstant("ITEM_TYPE_BELT"):
		return (BELT_CELL,)
	isWearable = getattr(item, "IsWearableFlag", None)
	if isWearable is None:
		return ()
	for name, wear in WEAR_BY_FLAG:
		flag = _ItemConstant(name)
		if flag is not None and isWearable(flag):
			return (wear,)
	flag = _ItemConstant("WEARABLE_UNIQUE")
	if flag is not None and isWearable(flag):
		return UNIQUE_CELLS
	return ()


def FindSetCell(vnum, target, isFree, isOwnCell):
	"""The set's cell for a drop of the item on `target` (a wear index, or
	None between the cells): its wear cell; of two, the dropped-on one, the
	one the item is worn on or already held in (isOwnCell), else the first
	while it is free (isFree), else the second, as the server equips a ring
	or a unique. None when the item is not worn."""
	cells = WearCells(vnum, target)
	if not cells:
		return None
	if len(cells) == 1:
		return cells[0]
	if target in cells:
		return target
	for wear in cells:
		if isOwnCell(wear):
			return wear
	first, second = cells
	return first if isFree(first) else second


def ColorOf(index):
	"""OLD's ARGB color of a set's color index (0: none picked)."""
	return COLORS[index - 1] if 1 <= index <= len(COLORS) else DEFAULT_SET_COLOR


def DefaultName(index):
	return localeInfo.FAST_EQUIP_SET_NAME % (index + 1)


def NameOf(index):
	return fastEquip.GetName(index) or DefaultName(index)


def IsAtWearCell(window, cell, wear):
	return window in (player.INVENTORY, player.EQUIPMENT) and cell == player.EQUIPMENT_SLOT_START + wear


def IsEquipped(index):
	"""A set with something in it, every item on its own wear cell (OLD's
	IsEquiped; OLD counted an empty set as equipped)."""
	filled = False
	for wear in range(fastEquip.WEAR_COUNT):
		window, cell = fastEquip.GetSlot(index, wear)
		if window == fastEquip.SLOT_EMPTY:
			continue
		filled = True
		if window == fastEquip.SLOT_KEEP or not IsAtWearCell(window, cell, wear):
			return False
	return filled


class CellSlots(object):
	"""The set's cells, one ui.SlotWindow each (by wear index, `windows`),
	answering the calls the window makes of its one slot window."""

	def __init__(self):
		self.windows = {}

	def SetItemSlot(self, wear, vnum, count):
		self.windows[wear].SetItemSlot(wear, vnum, count)

	def EnableSlot(self, wear):
		self.windows[wear].EnableSlot(wear)

	def DisableSlot(self, wear):
		self.windows[wear].DisableSlot(wear)

	def RefreshSlot(self):
		for slots in self.windows.values():
			slots.RefreshSlot()

	def Show(self):
		for slots in self.windows.values():
			slots.Show()

	def Hide(self):
		for slots in self.windows.values():
			slots.Hide()


class DropArea(ui.Window):
	"""A drop catcher: the set's slot area between the cells. A left press or
	release on it calls dropEvent, which drops only what is attached."""

	def __init__(self):
		ui.Window.__init__(self)
		self.dropEvent = None

	def OnMouseLeftButtonDown(self):
		if self.dropEvent:
			self.dropEvent()
		return True

	def OnMouseLeftButtonUp(self):
		if self.dropEvent:
			self.dropEvent()
		return True


class EquipSet(ui.Bar):
	"""One line of the set list (OLD's EquipSet): a click selects it, the edit
	button opens the popup. OLD's edit art is not shipped: a text mark stands
	in."""

	WIDTH = 88
	HEIGHT = 21

	def __init__(self, index):
		ui.Bar.__init__(self)
		self.index = index
		self.color = DEFAULT_SET_COLOR
		self.clickEvent = None
		self.editEvent = None
		self.over = None
		self.SetColor(self.color)

		self.label = ui.TextLine()
		self.label.SetParent(self)
		self.label.SetPosition(13, 4)
		self.label.AddFlag("not_pick")
		self.label.Show()

		self.editBar = ui.Bar()
		self.editBar.SetParent(self)
		self.editBar.SetSize(11, self.HEIGHT)
		self.editBar.SetPosition(0, 0)
		self.editBar.SetColor(0x33ffffff)
		self.editBar.OnMouseLeftButtonDown = self.OnEditPress
		self.editBar.Show()

		self.editMark = ui.TextLine()
		self.editMark.SetParent(self.editBar)
		self.editMark.SetPosition(2, 3)
		self.editMark.SetText("...")
		self.editMark.AddFlag("not_pick")
		self.editMark.Show()

	def SetEntry(self, name, color):
		self.label.SetText(name)
		self.color = color
		self.SetColor(color)

	def OnEditPress(self):
		if self.editEvent:
			self.editEvent(self.index)

	def OnMouseOverIn(self):
		if not self.over:
			self.over = ui.Bar()
			self.over.SetParent(self)
			self.over.SetSize(5, 20)
			self.over.SetPosition(self.WIDTH - 5, 0)
			self.over.SetColor(0x66ffffff)
		self.over.Show()

	def OnMouseOverOut(self):
		if self.over:
			self.over.Hide()

	def OnMouseLeftButtonDown(self):
		if self.clickEvent:
			self.clickEvent(self.index)


class EditPopUp(ui.Bar):
	"""OLD's EditPopUp: the set's name (15 characters) and its color."""

	def __init__(self):
		ui.Bar.__init__(self)
		self.index = 0
		self.colorIndex = 0
		self.saveEvent = None
		self.SetColor(0xCC000000)
		self.SetSize(150, 150)

		inputSlot = ui.Bar()
		inputSlot.SetParent(self)
		inputSlot.SetSize(130, 20)
		inputSlot.SetPosition(10, 10)
		inputSlot.SetColor(0xff000000)
		inputSlot.Show()
		self.inputSlot = inputSlot

		edit = ui.EditLine()
		edit.SetParent(inputSlot)
		edit.SetSize(130, 20)
		edit.SetPosition(5, 2)
		edit.SetMax(fastEquip.NAME_MAX_CHARS)
		edit.SetPackedFontColor(0xCCffffff)
		## Enter saves, Escape closes (OLD's edit line had neither).
		edit.SetReturnEvent(ui.__mem_func__(self.UpdateButton))
		edit.SetEscapeEvent(ui.__mem_func__(self.Close))
		edit.Show()
		self.nameEditLine = edit

		self.okButton = self.__MakeButton(8, 120, localeInfo.UI_OK, self.UpdateButton)
		self.cancelButton = self.__MakeButton(80, 120, localeInfo.UI_CANCEL, self.Close)

		self.colorBars = []
		x, y = 7, 35
		for i, color in enumerate(COLORS):
			if i and not i % 6:
				y = 35
				x += 70
			bar = ui.Bar()
			bar.SetParent(self)
			bar.SetPosition(x, y)
			bar.SetColor(color)
			bar.SetSize(65, 10)
			bar.OnMouseLeftButtonDown = lambda index=i + 1: self.ClickColor(index)
			bar.Show()
			self.colorBars.append(bar)
			y += 13

	def __MakeButton(self, x, y, text, event):
		button = ui.Button()
		button.SetParent(self)
		button.SetPosition(x, y)
		button.SetUpVisual("d:/ymir work/ui/public/middle_button_01.sub")
		button.SetOverVisual("d:/ymir work/ui/public/middle_button_02.sub")
		button.SetDownVisual("d:/ymir work/ui/public/middle_button_03.sub")
		button.SetText(text)
		button.SAFE_SetEvent(event)
		button.Show()
		return button

	def ClickColor(self, colorIndex):
		self.colorIndex = colorIndex
		self.inputSlot.SetColor(ColorOf(colorIndex))

	def UpdateButton(self):
		if self.saveEvent:
			self.saveEvent(self.index, self.nameEditLine.GetText(), self.colorIndex)
		self.Close()

	def Close(self):
		self.nameEditLine.KillFocus()
		self.Hide()

	def Open(self, index, name, colorIndex):
		self.index = index
		self.colorIndex = colorIndex
		self.nameEditLine.SetText(name)
		self.inputSlot.SetColor(ColorOf(colorIndex))
		self.Show()
		self.nameEditLine.SetFocus()


class FastEquipWindow(ui.ScriptWindow):
	"""OLD's FastEquipWindow (Interface.wndFastEquip)."""

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.__Initialize()
		self.__LoadWindow()
		self.__BindEvents()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __Initialize(self):
		self.selectedSet = 0
		self.tooltipItem = None
		self.questionDialog = None
		self.builtCells = None
		self.itemSlot = None
		self.setRows = {}
		self.wndPopUpEdit = None
		self.titleLabel = None
		self.titleColor = None
		self.equippedBar = None
		self.switchButton = None
		self.clearButton = None
		self.buffiLabel = None
		self.auraLabel = None
		self.lastRefresh = -1000.0
		self.refreshDirty = False
		self.lastSwitched = False
		self.cellTiles = []
		self.dropCatchers = []

	def __LoadWindow(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/fastequipwindow.py")
		except:
			import exception
			exception.Abort("FastEquipWindow.LoadWindow.LoadObject")

		try:
			self.board = self.GetChild("board")
			self.titleLabel = self.GetChild("TitleLabel")
			self.titleColor = self.GetChild("TitleColor")
			self.equippedBar = self.GetChild("EquippedBar")
			self.switchButton = self.GetChild("SwitchButton")
			self.clearButton = self.GetChild("ClearButton")
			self.buffiLabel = self.GetChild("BuffiLabel")
			self.auraLabel = self.GetChild("AuraLabel")
			closeButton = self.GetChild("CloseButton")
		except:
			import exception
			exception.Abort("FastEquipWindow.LoadWindow.BindObject")

		closeButton.SetEvent(ui.__mem_func__(self.Close))

		ypos = 60
		for i in range(fastEquip.SET_COUNT):
			row = self.__MakeSetRow(i)
			row.SetPosition(16, ypos)
			row.Show()
			self.setRows[i] = row
			ypos += 23

		self.wndPopUpEdit = self.__MakeEditPopup()
		self.dropCatchers = self.__MakeDropCatchers()

	def __MakeDropCatchers(self):
		"""The set's slot area under the cells, but Switch and Clear: a press
		or a drag's release there drops what is attached (DropAnywhere).
		Made before the cells' slot windows, so they lie over these."""
		catchers = []
		for top, bottom in CATCHER_ROWS:
			catcher = DropArea()
			catcher.SetParent(self.board)
			catcher.SetPosition(SLOT_X, SLOT_Y + top)
			catcher.SetSize(SLOT_WIDTH, bottom - top)
			catcher.dropEvent = ui.__mem_func__(self.DropAnywhere)
			catcher.Show()
			catchers.append(catcher)
		return catchers

	def __MakeSetRow(self, index):
		"""A line of the set list (a seam: NovaUI's lines are proxies)."""
		row = EquipSet(index)
		row.SetParent(self.board)
		row.SetSize(EquipSet.WIDTH, EquipSet.HEIGHT)
		row.clickEvent = ui.__mem_func__(self.SelectSet)
		row.editEvent = ui.__mem_func__(self.OpenEditPopup)
		return row

	def __MakeEditPopup(self):
		popup = EditPopUp()
		popup.saveEvent = ui.__mem_func__(self.SaveEdit)
		return popup

	def __BindEvents(self):
		self.switchButton.SetEvent(ui.__mem_func__(self.Switch))
		self.clearButton.SetEvent(ui.__mem_func__(self.Clear))

	def Destroy(self):
		self.Close()
		self.setRows = {}
		self.dropCatchers = []
		self.tooltipItem = None
		self.wndPopUpEdit = None
		self.ClearDictionary()

	def SetItemToolTip(self, tooltipItem):
		self.tooltipItem = tooltipItem

	## --- open and close --------------------------------------------------------------

	def Open(self):
		self.Show()
		self.SetTop()
		self.__ApplyUsableCells()
		self.__RefreshSetRows()
		self.__Select(self.selectedSet)

	def Close(self):
		if self.questionDialog:
			self.questionDialog.Close()
			self.questionDialog = None
		if self.wndPopUpEdit:
			self.wndPopUpEdit.Close()
		self.OverOutItem()
		self.Hide()
		return True

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def OnMoveWindow(self, x, y):
		if self.wndPopUpEdit:
			self.wndPopUpEdit.SetPosition(x - self.wndPopUpEdit.GetWidth(), y)

	## --- the slot window, rebuilt only when the usable cells change -----------------

	def UsableCells(self):
		return [wear for wear in sorted(CELLS) if fastEquip.IsUsableCell(wear)]

	def __ApplyUsableCells(self):
		"""True when the cells changed (the window can open before the login's
		first GC::FAST_EQUIP brings the mask)."""
		usable = self.UsableCells()
		if usable == self.builtCells:
			return False
		self.builtCells = usable
		self.__MakeSlots(usable)
		return True

	def __MakeSlots(self, usable):
		"""Fresh slot windows over the usable cells only, one per cell: a slot
		window keeps its slots for good, so a cell that may not show is never
		appended, and a press between two cells reaches the drop catchers
		(a seam: NovaUI hides its cells in the model)."""
		if self.itemSlot:
			self.itemSlot.Hide()
		for tile in self.cellTiles:
			tile.Hide()
		self.cellTiles = []

		## A slot window draws its base image once per slot, at the slot's
		## top: a tall cell's lower tiles are images under it.
		for wear in usable:
			x, y, width, height = CELLS[wear]
			for row in range(1, height // 32):
				tile = ui.ImageBox()
				tile.SetParent(self.board)
				tile.SetPosition(SLOT_X + x, SLOT_Y + y + 32 * row)
				tile.LoadImage(SLOT_BASE)
				tile.AddFlag("not_pick")
				tile.Show()
				self.cellTiles.append(tile)

		cells = CellSlots()
		for wear in usable:
			x, y, width, height = CELLS[wear]
			slots = ui.SlotWindow()
			slots.SetParent(self.board)
			slots.SetPosition(SLOT_X + x, SLOT_Y + y)
			slots.SetSize(width, height)
			slots.SetSlotBaseImage(SLOT_BASE, 1.0, 1.0, 1.0, 1.0)
			slots.AppendSlot(wear, 0, 0, width, height)
			slots.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
			slots.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
			slots.SetSelectEmptySlotEvent(ui.__mem_func__(self.SelectEmptySlot))
			slots.SetSelectItemSlotEvent(ui.__mem_func__(self.SelectItemSlot))
			slots.SetUnselectItemSlotEvent(ui.__mem_func__(self.UseItemSlot))
			slots.SetUseSlotEvent(ui.__mem_func__(self.UseItemSlot))
			slots.Show()
			cells.windows[wear] = slots
		self.itemSlot = cells

		rowShown = any(wear in usable for wear in BUFFI_CELLS)
		self.__ShowText(self.buffiLabel, rowShown)
		self.__ShowText(self.auraLabel, 39 in usable)

	def __ShowText(self, widget, flag):
		if not widget:
			return
		if flag:
			widget.Show()
		else:
			widget.Hide()

	## --- the server's word -----------------------------------------------------------

	def RefreshFastEquip(self, setIndex, switched):
		"""GC::FAST_EQUIP: one set's state (game.py's RefreshFastEquip)."""
		rebuilt = self.__ApplyUsableCells()
		self.__RefreshSetRow(setIndex)
		if setIndex == self.selectedSet:
			## The marks of what did not move stay until another set is picked:
			## the switch's own item moves bring a plain refresh right after it.
			self.lastSwitched = self.lastSwitched or bool(switched)
		if rebuilt or setIndex == self.selectedSet:
			self.RefreshSelected()

	def __RefreshSetRow(self, index):
		row = self.setRows.get(index)
		if row:
			row.SetEntry(NameOf(index), ColorOf(fastEquip.GetColor(index)))

	def __RefreshSetRows(self):
		for index in range(fastEquip.SET_COUNT):
			self.__RefreshSetRow(index)

	def RefreshSelected(self):
		"""The selected set's title, its slots and the equipped indicator."""
		index = self.selectedSet
		self.titleLabel.SetText(NameOf(index))
		self.titleColor.SetColor(ColorOf(fastEquip.GetColor(index)))
		equipped = IsEquipped(index)
		self.equippedBar.SetColor(0xff42f548 if equipped else ColorOf(fastEquip.GetColor(index)))

		for wear in self.builtCells or ():
			window, cell = fastEquip.GetSlot(index, wear)
			if window == fastEquip.SLOT_EMPTY or window == fastEquip.SLOT_KEEP:
				self.itemSlot.SetItemSlot(wear, 0, 0)
				self.itemSlot.EnableSlot(wear)
				continue
			self.itemSlot.SetItemSlot(wear, player.GetItemIndex(window, cell), 0)
			if self.lastSwitched and not IsAtWearCell(window, cell, wear):
				self.itemSlot.DisableSlot(wear)
			else:
				self.itemSlot.EnableSlot(wear)
		self.itemSlot.RefreshSlot()

	## --- the sets --------------------------------------------------------------------

	def SelectSet(self, index):
		"""A press on a set (OLD's SelectSet); Shift switches the clicked set
		(OLD called Switch for the previously selected one)."""
		if app.IsPressed(app.DIK_LSHIFT):
			self.__SwitchSet(index)
			return
		self.__Select(index)

	def __Select(self, index):
		self.selectedSet = index
		self.lastSwitched = False
		self.RefreshSelected()
		self.__SendRefresh()

	def Switch(self):
		self.__SwitchSet(self.selectedSet)

	def __SwitchSet(self, index):
		if IsEquipped(index):
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.FAST_EQUIP_ALREADY)
			return
		fastEquip.SendSwitch(index)

	def Clear(self):
		dialog = uiCommon.QuestionDialog()
		dialog.SetText(localeInfo.FAST_EQUIP_CLEAR_CONFIRM)
		dialog.SetAcceptEvent(ui.__mem_func__(self.OnAcceptClear))
		dialog.SetCancelEvent(ui.__mem_func__(self.OnDenyClear))
		dialog.Open()
		self.questionDialog = dialog

	def OnAcceptClear(self):
		fastEquip.SendClear(self.selectedSet)
		self.OnDenyClear()

	def OnDenyClear(self):
		if self.questionDialog:
			self.questionDialog.Close()
			self.questionDialog = None

	def OpenEditPopup(self, index):
		x, y = self.GetGlobalPosition()
		self.wndPopUpEdit.SetPosition(x - self.wndPopUpEdit.GetWidth(), y)
		self.wndPopUpEdit.Open(index, NameOf(index), fastEquip.GetColor(index))

	def SaveEdit(self, index, name, colorIndex):
		self.__SendSave(index, name, colorIndex, {})

	def __SaveCells(self, changes):
		index = self.selectedSet
		self.__SendSave(index, fastEquip.GetName(index), fastEquip.GetColor(index), changes)

	## --- a save: keep everything but what changed -----------------------------------

	def __SendSave(self, index, name, colorIndex, changes):
		slots = [(fastEquip.SLOT_KEEP, 0)] * fastEquip.WEAR_COUNT
		for wear, target in changes.items():
			slots[wear] = target
		fastEquip.SendSave(index, name, colorIndex, slots)

	def __SaveCell(self, wear, target):
		self.__SaveCells({wear: target})

	## --- the cells --------------------------------------------------------------------

	def OverInItem(self, wear):
		window, cell = fastEquip.GetSlot(self.selectedSet, wear)
		if window in (fastEquip.SLOT_EMPTY, fastEquip.SLOT_KEEP) or not self.tooltipItem:
			return
		self.tooltipItem.SetInventoryItem(cell, window)

	def OverOutItem(self):
		if self.tooltipItem:
			self.tooltipItem.HideToolTip()

	def UseItemSlot(self, wear):
		"""A right click empties the cell (OLD's UseItemSlot)."""
		self.__SaveCell(wear, (fastEquip.SLOT_EMPTY, 0))

	def SelectEmptySlot(self, wear):
		if mouseModule.mouseController.isAttached():
			self.__DropAttached(wear)
			return
		window, cell = fastEquip.GetSlot(self.selectedSet, wear)
		if window == fastEquip.SLOT_KEEP:
			self.__SaveCell(wear, (fastEquip.SLOT_EMPTY, 0))

	def SelectItemSlot(self, wear):
		if mouseModule.mouseController.isAttached():
			self.__DropAttached(wear)

	def DropAnywhere(self):
		"""A press or a drag's release on the set's slot area between the
		cells: what is attached goes to the cell it is worn on."""
		if mouseModule.mouseController.isAttached():
			self.__DropAttached(None)

	def __DropAttached(self, wear):
		"""A drop on the cell `wear` (None: between the cells). OLD saved it
		there or refused it silently; here it goes to the cell the item is
		worn on (FindSetCell), the cell the item left in this set is emptied
		in the same save, and an item no cell can hold, or that this
		character cannot wear, is refused with a chat line."""
		attachedType = mouseModule.mouseController.GetAttachedType()
		attachedPos = mouseModule.mouseController.GetAttachedSlotNumber()
		attachedVnum = mouseModule.mouseController.GetAttachedItemIndex()
		if player.SLOT_TYPE_INVENTORY == attachedType:
			window = player.INVENTORY
		elif player.SLOT_TYPE_EXTRA_INVENTORY == attachedType:
			window = player.EXTRA_INVENTORY
		else:
			return
		held = (window, attachedPos)
		index = self.selectedSet
		heldAt = [other for other in range(fastEquip.WEAR_COUNT) if tuple(fastEquip.GetSlot(index, other)) == held]
		isFree = lambda cell: fastEquip.GetSlot(index, cell)[0] == fastEquip.SLOT_EMPTY
		isOwnCell = lambda cell: cell in heldAt or IsAtWearCell(window, attachedPos, cell)
		target = FindSetCell(attachedVnum, wear, isFree, isOwnCell)
		if target is None or target not in (self.builtCells or ()) or not FitsCell(target, attachedVnum):
			self.__RefuseDrop(localeInfo.FAST_EQUIP_NOT_FOR_SET)
			return
		if not CanWear(target, attachedVnum):
			self.__RefuseDrop(localeInfo.FAST_EQUIP_WRONG_CHARACTER)
			return
		changes = dict((other, (fastEquip.SLOT_EMPTY, 0)) for other in heldAt if other != target)
		changes[target] = held
		self.__SaveCells(changes)
		mouseModule.mouseController.DeattachObject()

	def __RefuseDrop(self, text):
		chat.AppendChat(chat.CHAT_TYPE_INFO, text)
		mouseModule.mouseController.DeattachObject()

	## --- the coalesced refresh ---------------------------------------------------------

	def __SendRefresh(self):
		self.lastRefresh = app.GetTime()
		self.refreshDirty = False
		fastEquip.SendRefresh(self.selectedSet)

	def RefreshInventory(self):
		"""The inventory changed while the window shows (Interface's
		RefreshInventory): at most one request per REFRESH_INTERVAL, and one
		trailing request for what changed in between. Answered from the
		server's memory (OLD's window asked on every refresh)."""
		if not self.IsShow():
			return
		since = app.GetTime() - self.lastRefresh
		if since >= REFRESH_INTERVAL:
			self.__SendRefresh()
			return
		self.refreshDirty = True
		self._ArmRefreshTimer(REFRESH_INTERVAL - since)

	def CheckRefreshDue(self):
		"""The trailing refresh, once its time is up (a frame's OnUpdate here,
		the board's timer in NovaUI)."""
		if not self.refreshDirty:
			return
		remaining = REFRESH_INTERVAL - (app.GetTime() - self.lastRefresh)
		if remaining <= 0:
			self.__SendRefresh()
		else:
			self._ArmRefreshTimer(remaining)

	def _ArmRefreshTimer(self, seconds):
		pass

	def OnUpdate(self):
		if self.refreshDirty:
			self.CheckRefreshDue()
