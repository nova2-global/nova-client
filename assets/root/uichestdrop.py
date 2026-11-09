"""The chest-drop preview (NOVA-18; OLD's ENABLE_SHOW_CHEST_DROP).

A chest is a box item that opens into a special item group: a gift box, a
gacha chest or a treasure box of the use type (OLD constInfo.py:543-555,
is_previewable below). Shift over one in the inventory, the special
inventory or a shop asks the server for the group's rows once
(net.SendChestDropInfo, CG::CHEST_DROP_INFO) and opens this window; the
answer (GC::CHEST_DROP_INFO) reaches game.BINARY_SetChestDropInfo, which keeps
the rows for the session in constInfo.CHESTS_PREVIEW and shows them here.

The window is OLD's uiTimerWindow.ChestItemPopup (uiTimerWindow.py:
1365-1610): a 320 x 400 board titled "Chest Items", a line that says where the
items are found (and, for a gacha chest, how many times it opens), the chest
under it, then one row per item: its icon, "<count>x <name>" and its chance
tier. The tier is OLD's rule (GET_CHEST_RARITY_BY_PERC, :1441-1452) over the
chest's own rows: below the middle of the lowest and the average chance it is
low, up to the middle of the highest and the average it is middle, above that
high. OLD's dungeon-manager art is not in NEW's client, so the rows are drawn
with bars of OLD's colors.

The legacy window builds its widgets in __LoadWindow, and the rows go through
one widget, the RowList (Clear, AppendRow, Done), so the NovaUI window
(nui_chest_drop.ChestDropWindow) overrides the loader and puts proxies there.
"""

import app
import constInfo
import item
import localeInfo
import net
import ui
import wndMgr

# OLD's CHEST_RARITY (uiTimerWindow.py:1365-1369): the tiers and their colors.
TIER_LOW, TIER_MIDDLE, TIER_HIGH = 1, 2, 3
TIER_COLORS = {
	TIER_LOW: 0xff9830f0,
	TIER_MIDDLE: 0xff30b3f0,
	TIER_HIGH: 0xff30f0b3,
}
# The locale keys of the tier names (OLD wrote them in English in the code).
TIER_KEYS = {
	TIER_LOW: "CHEST_DROP_TIER_LOW",
	TIER_MIDDLE: "CHEST_DROP_TIER_MIDDLE",
	TIER_HIGH: "CHEST_DROP_TIER_HIGH",
}
# OLD's text color of the info line and the item names.
TEXT_COLOR = 0xffe8b478

# The vnum the server sends a yang row as (CSpecialItemGroup::GOLD).
YANG_VNUM = 1


def is_previewable(vnum):
	"""OLD constInfo.IS_CHEST_PREVIEWABLE: a gift box, a gacha chest or a
	treasure box of the use type."""
	return constInfo.IS_CHEST_PREVIEWABLE(vnum)


def tier_of(chance, minimum, average, maximum):
	"""OLD's GET_CHEST_RARITY_BY_PERC (uiTimerWindow.py:1441-1452)."""
	chance = float(chance)
	if chance < float((minimum + average) / 2):
		return TIER_LOW
	if chance <= float((maximum + average) / 2):
		return TIER_MIDDLE
	return TIER_HIGH


def rows_with_tiers(rows):
	"""[(vnum, count, chance)] -> [(vnum, count, tier)], in the server's
	order. OLD's average is a whole number (Python 2 divided the sum of whole
	chances by the count), so it is here too."""
	if not rows:
		return []
	chances = [int(r[2]) for r in rows]
	minimum = float(min(chances))
	average = float(sum(chances) // len(chances))
	maximum = float(max(chances))
	return [(vnum, count, tier_of(chance, minimum, average, maximum)) for (vnum, count, chance) in rows]


def tier_text(tier):
	return getattr(localeInfo, TIER_KEYS.get(tier, TIER_KEYS[TIER_LOW]), "")


def row_name(vnum, count):
	"""OLD's "%dx %s" (uiTimerWindow.py:1418); item.SelectItem first."""
	item.SelectItem(vnum)
	return "%dx %s" % (count, item.GetItemName())


def icon_of(vnum):
	"""The item's icon, or OLD's noexist icon (uiTimerWindow.py:1436-1439)."""
	item.SelectItem(vnum)
	path = item.GetIconImageFileName()
	if path and app.IsExistFile(path):
		return path
	return "icon/item/noexist.tga"


# The chest the pointer is over in a window that shows items (the inventory,
# the special inventory, a shop), as OLD's selectedItem: kept in constInfo,
# which those windows import; the Shift press reads it.
def hover(vnum):
	constInfo.SET_HOVERED_CHEST(vnum)


def unhover():
	constInfo.SET_HOVERED_CHEST(0)


def hovered_vnum():
	return constInfo.GET_HOVERED_CHEST()


def request(vnum):
	"""OLD's press (uiInventory.py:1201-1208): ask the server once a session,
	then open. False when the vnum is no chest."""
	if not is_previewable(vnum):
		return False
	if vnum not in constInfo.CHESTS_PREVIEW:
		net.SendChestDropInfo(vnum)
	return True


class RowList(ui.Window):
	"""The rows in a scroll window (OLD's ListBoxEx in a ScrollWindow,
	uiTimerWindow.py:1505-1535): each OLD's 295 x 65, 66 apart."""

	ROW_WIDTH = 295
	ROW_HEIGHT = 65
	ROW_STEP = 66

	def __init__(self, parent, x, y, width, height):
		ui.Window.__init__(self)
		self.rows = []
		scroll = ui.ScrollWindow(width, height, ui.ScrollWindow.THIN)
		scroll.SetParent(parent)
		scroll.SetPosition(x, y)
		scroll.Show()
		self.SetParent(scroll)
		self.SetSize(self.ROW_WIDTH, 0)
		self.Show()
		scroll.SetContentWindow(self)
		self.scroll = scroll

	def Destroy(self):
		self.rows = []
		if self.scroll:
			self.scroll.Destroy()
		self.scroll = None

	def Clear(self):
		self.rows = []
		self.SetSize(self.ROW_WIDTH, 0)

	def AppendRow(self, vnum, count, tier):
		y = len(self.rows) * self.ROW_STEP
		row = ui.Bar()
		row.SetParent(self)
		row.SetPosition(0, y)
		row.SetSize(self.ROW_WIDTH, self.ROW_HEIGHT)
		row.SetColor(0xff214344)
		row.Show()

		icon = ui.ExpandedImageBox()
		icon.SetParent(row)
		icon.SetPosition(20, 0)
		icon.SetWindowVerticalAlignCenter()
		icon.LoadImage(icon_of(vnum))
		icon.Show()

		name = ui.TextLine()
		name.SetParent(row)
		name.SetPosition(0, 22)
		name.SetWindowHorizontalAlignCenter()
		name.SetHorizontalAlignCenter()
		name.SetPackedFontColor(TEXT_COLOR)
		name.SetText(row_name(vnum, count))
		name.Show()

		label = ui.TextLine()
		label.SetParent(row)
		label.SetPosition(0, 40)
		label.SetWindowHorizontalAlignCenter()
		label.SetHorizontalAlignCenter()
		label.SetPackedFontColor(TIER_COLORS.get(tier, TIER_COLORS[TIER_LOW]))
		label.SetText(tier_text(tier))
		label.Show()

		self.rows.append((row, icon, name, label))

	def Done(self):
		self.SetSize(self.ROW_WIDTH, len(self.rows) * self.ROW_STEP)
		if self.scroll:
			self.scroll.OnContentWindowSizeChange()
			self.scroll.ScrollToStart()

	def OnRunMouseWheel(self, length):
		if self.scroll:
			self.scroll.OnRunMouseWheel(length)


class ChestDropWindow(ui.ScriptWindow):
	"""OLD's ChestItemPopup (Interface.wndChestDrop)."""

	WIDTH = 320
	HEIGHT = 400

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.chestVnum = 0
		self.tooltipItem = None
		self.__LoadWindow()
		# OLD placed it at the screen's center once (:1474).
		self.SetCenterPosition()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		self.SetSize(self.WIDTH, self.HEIGHT)
		self.AddFlag("movable")
		self.AddFlag("float")

		board = ui.BoardWithTitleBar()
		board.SetParent(self)
		board.SetSize(self.WIDTH, self.HEIGHT)
		board.AddFlag("attach")
		board.SetTitleName(localeInfo.CHEST_DROP_TITLE)
		board.SetCloseEvent(ui.__mem_func__(self.Close))
		board.Show()
		self.board = board

		# OLD :1490-1497 (one line at 38; a gacha chest's two lines at 30).
		self.infoLabel = self.__Text(board, 0, 34, True)
		self.openLabel = self.__Text(board, 0, 48, True)

		# OLD's header row (Row.Update, :1428-1439): the chest's icon and name.
		header = ui.Bar()
		header.SetParent(board)
		header.SetPosition(7, 72)
		header.SetSize(306, 60)
		header.SetColor(0xff1e3233)
		header.Show()
		self.header = header
		self.chestIcon = ui.ExpandedImageBox()
		self.chestIcon.SetParent(header)
		self.chestIcon.SetPosition(22, 0)
		self.chestIcon.SetWindowVerticalAlignCenter()
		self.chestIcon.Show()
		self.chestName = self.__Text(header, 0, 30, True)

		self.rowList = RowList(board, 7, 133, 305, 258)

	@staticmethod
	def __Text(parent, x, y, center):
		text = ui.TextLine()
		text.SetParent(parent)
		text.SetPosition(x, y)
		if center:
			text.SetWindowHorizontalAlignCenter()
			text.SetHorizontalAlignCenter()
		text.SetPackedFontColor(TEXT_COLOR)
		text.Show()
		return text

	def Destroy(self):
		if self.rowList:
			self.rowList.Destroy()
		self.rowList = None
		self.board = None
		self.header = None
		self.tooltipItem = None
		self.chestVnum = 0
		self.ClearDictionary()

	def Open(self, vnum):
		"""OLD's Open: show, raise, fill from the rows known so far."""
		self.Show()
		self.SetTop()
		self.RefreshItemList(vnum)

	def Refresh(self, vnum):
		"""The server's answer: the open window shows it if it is this chest's
		(OLD opened the window on every answer, :1178-1179)."""
		self.Open(vnum)

	def Close(self):
		self.Hide()

	def RefreshItemList(self, vnum):
		"""OLD's RefreshItemList (:1556-1588)."""
		self.chestVnum = vnum
		item.SelectItem(vnum)
		name = item.GetItemName()
		self.infoLabel.SetText(localeInfo.CHEST_DROP_FOUND_IN % name)
		if item.GetItemType() == item.ITEM_TYPE_GACHA:
			(limitType, limitValue) = item.GetLimit(1)
			self.openLabel.SetText(localeInfo.CHEST_DROP_OPEN_TIMES % limitValue)
		else:
			self.openLabel.SetText("")
		self.chestIcon.LoadImage(icon_of(vnum))
		self.chestName.SetText(name)

		self.rowList.Clear()
		for (rowVnum, count, tier) in rows_with_tiers(constInfo.CHESTS_PREVIEW.get(vnum, [])):
			self.rowList.AppendRow(rowVnum, count, tier)
		self.rowList.Done()

	def OnRunMouseWheel(self, length):
		if self.rowList:
			self.rowList.OnRunMouseWheel(length)
		return True

	def OnPressEscapeKey(self):
		self.Close()
		return True
