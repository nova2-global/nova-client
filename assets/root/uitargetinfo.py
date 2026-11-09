## The mob info board (NOVA-40; OLD root/uiTarget.py:249-756,
## __SEND_TARGET_INFO__): under a monster's target board, opened by its info
## button. Stats read from the client's mob_proto (nonplayer): the HP, the
## damage the mob does to you, exp, gold, regen, race and sub-race, resists.
## The drops come from the server: net.SendTargetInfoLoad asks for the target,
## GC::TARGET_INFO answers (game.BINARY_SetTargetInfo) and a row can name
## several vnums (weapons and armors of the same base, metin stones of the
## same type, merged by SetRows as OLD's BINARY_AddTargetMonsterDropInfo did).
##
## The answer is kept per race in constInfo.MONSTER_INFO_DATA with the level it
## was asked at; it is thrown away on map change (game.py Open) and asked again
## after a level up, since the server's list depends on both. OLD only kept it.
##
## The server answers once a second for the player's current target; a request
## inside that second is dropped, so an open board retries while it waits
## (RETRY_DELAY, up to RETRY_MAX). A mob with no drops answers with no rows.
##
## OLD's art (seperator.tga, the NewUI tile) is not in NEW's packs: the
## separator is a code-drawn line and the board the plain thin board. The
## attacker texts come from fields the server sends as 0 until the drop rule
## ships (NOVA-40 Q1), so they do not show yet.
##
## OLD bugs fixed: the scrolling list was rebuilt per HP packet refresh (only
## on open and on an answer here); SetElementImage made a new image per packet
## (uitarget.py SetElement sets one text on change).

import app
import constInfo
import item
import localeInfo
import net
import nonplayer
import player
import ui
import uiToolTip
import wndMgr

import nui_numbers

STONE_START_VNUM = 28030
STONE_LAST_VNUM = 28042
VALENTINE_LETTER_START_VNUM = 30887
VALENTINE_LETTER_LAST_VNUM = 30913
RETRY_DELAY = 1.2
RETRY_MAX = 5

# OLD uiTarget.py:311-343: the race flags by name.
RACE_FLAG_TO_NAME = {
	1 << 0: "TARGET_INFO_RACE_ANIMAL",
	1 << 1: "TARGET_INFO_RACE_UNDEAD",
	1 << 2: "TARGET_INFO_RACE_DEVIL",
	1 << 3: "TARGET_INFO_RACE_HUMAN",
	1 << 4: "TARGET_INFO_RACE_ORC",
	1 << 5: "TARGET_INFO_RACE_MILGYO",
	1 << 6: "TARGET_INFO_RACE_INSECT",
	1 << 9: "TARGET_INFO_RACE_DESERT",
	1 << 10: "TARGET_INFO_RACE_TREE",
	1 << 21: "TARGET_INFO_RACE_FLAG_ELEMENTAL",
}

SUB_RACE_FLAG_TO_NAME = {
	1 << 11: "TARGET_INFO_RACE_ELEC",
	1 << 7: "TARGET_INFO_RACE_FIRE",
	1 << 8: "TARGET_INFO_RACE_ICE",
	1 << 12: "TARGET_INFO_RACE_WIND",
	1 << 13: "TARGET_INFO_RACE_EARTH",
	1 << 14: "TARGET_INFO_RACE_DARK",
	1 << 15: "TARGET_INFO_RACE_FLAG_ATT_ELEC",
	1 << 16: "TARGET_INFO_RACE_FLAG_ATT_FIRE",
	1 << 17: "TARGET_INFO_RACE_FLAG_ATT_ICE",
	1 << 18: "TARGET_INFO_RACE_FLAG_ATT_WIND",
	1 << 19: "TARGET_INFO_RACE_FLAG_ATT_EARTH",
	1 << 20: "TARGET_INFO_RACE_FLAG_ATT_DARK",
}

# OLD's EXP_BASE_LVDELTA, from a mob 15 levels below to 15 above.
EXP_BASE_LVDELTA = [1, 5, 10, 20, 30, 50, 70, 80, 85, 90, 92, 94, 96, 98, 100, 100, 105, 110, 115, 120, 125,
                    130, 135, 140, 145, 150, 155, 160, 165, 170, 180]


def dotted(value):
	"""OLD's DottedNumber, grouped by the locale's separator."""
	return nui_numbers.group(int(value))


def text_of(key, default=""):
	return getattr(localeInfo, key, default)


def race_of_vid(vid):
	"""The target's vnum, or 0 for a VID without a mob (nonplayer answers -1)."""
	race = nonplayer.GetRaceNumByVID(vid)
	return race if race > 0 else 0


# --- the cache (constInfo.MONSTER_INFO_DATA) --------------------------------------------

def forget():
	"""A map change: the server's list depends on the map."""
	constInfo.MONSTER_INFO_DATA.clear()


def known(race):
	"""Rows are kept for this race and still fit the player's level."""
	data = constInfo.MONSTER_INFO_DATA.get(race)
	return data is not None and data.get("level") == player.GetStatus(player.LEVEL)


def data_of(race):
	return constInfo.MONSTER_INFO_DATA.get(race)


def store(race, rows):
	"""GC::TARGET_INFO's rows (vnum, count, damage, minAttackers, maxAttackers),
	merged as OLD's BINARY_AddTargetMonsterDropInfo (game.py:2501-2544): the
	+0..+9 of one item become one "vnum_list" row."""
	entries = []
	for row in rows:
		_merge_row(entries, *row)
	data = constInfo.MONSTER_INFO_DATA.get(race, {})
	data.update({"items": entries, "level": player.GetStatus(player.LEVEL)})
	constInfo.MONSTER_INFO_DATA[race] = data
	return data


def set_attackers(race, count):
	"""GC::TARGET's live attacker count."""
	data = constInfo.MONSTER_INFO_DATA.get(race)
	if data is None or data.get("currentAttackers") == count:
		return False
	data["currentAttackers"] = count
	return True


def _merge_row(entries, vnum, count, damageRequired, minAttackers, maxAttackers):
	item.SelectItem(vnum)
	itemType = item.GetItemType()
	isUpgradeable = itemType in (item.ITEM_TYPE_WEAPON, item.ITEM_TYPE_ARMOR)
	isMetin = itemType == item.ITEM_TYPE_METIN

	for entry in entries:
		if isUpgradeable:
			if "vnum_list" in entry and entry["vnum_list"][0] // 10 * 10 == vnum // 10 * 10:
				if vnum not in entry["vnum_list"]:
					entry["vnum_list"].append(vnum)
				entry["minAttackers"], entry["maxAttackers"] = minAttackers, maxAttackers
				return
		elif isMetin:
			if "vnum_list" in entry and (entry["vnum_list"][0] - entry["vnum_list"][0] % 1000) == (vnum - vnum % 1000):
				if vnum not in entry["vnum_list"]:
					entry["vnum_list"].append(vnum)
				entry["minAttackers"], entry["maxAttackers"] = minAttackers, maxAttackers
				return
		elif "vnum" in entry and entry["vnum"] == vnum and entry["count"] == count:
			entry["minAttackers"], entry["maxAttackers"] = minAttackers, maxAttackers
			return

	row = {"count": count, "damageRequired": damageRequired, "minAttackers": minAttackers, "maxAttackers": maxAttackers}
	if isUpgradeable or isMetin:
		row["vnum_list"] = [vnum]
	else:
		row["vnum"] = vnum
	entries.append(row)


# --- the texts, shared with the NovaUI board -----------------------------------------------

def stat_lines(race):
	"""The stat block's lines in OLD's order (HP, damage, exp, gold, regen):
	__LoadInformation_Default, uiTarget.py:417-446."""
	level = nonplayer.GetMonsterLevel(race)
	hitRate = _hit_rate(race)
	dmgMin, dmgMax = nonplayer.GetMonsterDamage(race)
	st = nonplayer.GetMonsterST(race)
	dmgMin = int((dmgMin + st) * 2 * hitRate) + level * 2
	dmgMax = int((dmgMax + st) * 2 * hitRate) + level * 2
	defense = player.GetStatus(player.DEF_GRADE) * (100 + player.GetStatus(player.DEF_BONUS)) // 100
	multiply = nonplayer.GetMonsterDamageMultiply(race)
	dmgMin = max(1, int(max(0, dmgMin - defense) * multiply))
	dmgMax = max(5, int(max(0, dmgMax - defense) * multiply))

	idx = min(len(EXP_BASE_LVDELTA) - 1, max(0, (level + 15) - player.GetStatus(player.LEVEL)))
	exp = nonplayer.GetMonsterExp(race) * EXP_BASE_LVDELTA[idx] // 100

	return [
		text_of("TARGET_INFO_MAX_HP") % dotted(nonplayer.GetMonsterMaxHP(race)),
		text_of("TARGET_INFO_DAMAGE") % (str(dmgMin), str(dmgMax)),
		text_of("TARGET_INFO_EXP") % dotted(exp),
		text_of("TARGET_INFO_GOLD_MIN_MAX") % (dotted(nonplayer.GetMobGoldMin(race)), dotted(nonplayer.GetMobGoldMax(race))),
		text_of("TARGET_INFO_REGEN_INFO") % (nonplayer.GetMobRegenPercent(race), nonplayer.GetMobRegenCycle(race)),
	]


def _hit_rate(race):
	"""OLD __LoadInformation_Default_GetHitRate, uiTarget.py:407-420."""
	attacker_dx = nonplayer.GetMonsterDX(race)
	attacker_level = nonplayer.GetMonsterLevel(race)
	self_dx = player.GetStatus(player.DX)
	self_level = player.GetStatus(player.LEVEL)
	iARSrc = min(90, (attacker_dx * 4 + attacker_level * 2) // 6)
	iERSrc = min(90, (self_dx * 4 + self_level * 2) // 6)
	fAR = (float(iARSrc) + 210.0) / 300.0
	fER = (float(iERSrc) * 2 + 5) / (float(iERSrc) + 95) * 3.0 / 10.0
	return fAR - fER


def race_lines(race):
	"""OLD __LoadInformation_Race, uiTarget.py:448-476: race and sub-race."""
	flags = nonplayer.GetMonsterRaceFlag(race)
	mainrace, subrace, hasHuman = [], [], False
	for i in range(22):
		flag = 1 << i
		if (flags & flag) != flag:
			continue
		if i == 3:
			hasHuman = True
		if flag in RACE_FLAG_TO_NAME:
			mainrace.append(text_of(RACE_FLAG_TO_NAME[flag]))
		elif flag in SUB_RACE_FLAG_TO_NAME:
			subrace.append(text_of(SUB_RACE_FLAG_TO_NAME[flag]))
	if nonplayer.IsMonsterStone(race) and not hasHuman:
		mainrace.append(text_of("TARGET_INFO_RACE_METIN"))
	none = text_of("TARGET_INFO_NO_RACE")
	return [text_of("TARGET_INFO_MAINRACE") % (", ".join(mainrace) or none),
	        text_of("TARGET_INFO_SUBRACE") % (", ".join(subrace) or none)]


def resist_lines(race):
	"""OLD __LoadInformation_Resists, uiTarget.py:430-435."""
	return [
		text_of("TARGET_INFO_RESISTS"),
		text_of("TARGET_INFO_RESISTS_LINE0") % (nonplayer.GetResist(race, nonplayer.MOB_RESIST_SWORD),
		                                        nonplayer.GetResist(race, nonplayer.MOB_RESIST_TWOHAND),
		                                        nonplayer.GetResist(race, nonplayer.MOB_RESIST_BELL)),
		text_of("TARGET_INFO_RESISTS_LINE1") % (nonplayer.GetResist(race, nonplayer.MOB_RESIST_DAGGER),
		                                        nonplayer.GetResist(race, nonplayer.MOB_RESIST_FAN),
		                                        nonplayer.GetResist(race, nonplayer.MOB_RESIST_BOW)),
		text_of("TARGET_INFO_RESISTS_LINE2") % (nonplayer.GetResist(race, nonplayer.MOB_RESIST_HITS),
		                                        nonplayer.GetResist(race, nonplayer.MOB_RESIST_SKILLS)),
	]


def item_row(entry, currentAttackers):
	"""What a drop row shows: (vnum shown, icon, name, extra lines, vnums). OLD
	AppendItem, uiTarget.py:530-580 and __UpdateItemAttackerText:600-621."""
	vnums = entry.get("vnum_list", [entry.get("vnum")])
	vnum = vnums[0]
	item.SelectItem(vnum)
	name = item.GetItemName()
	if "vnum_list" in entry and len(vnums) > 1:
		vnums = sorted(vnums)
		realName = name[:name.find("+")]
		if item.GetItemType() == item.ITEM_TYPE_METIN:
			realName = text_of("TARGET_INFO_STONE_NAME")
			name = realName + "+0 - +4"
		else:
			name = realName + "+" + str(vnums[0] % 10) + " - +" + str(vnums[-1] % 10)
		vnum = vnums[-1]
		item.SelectItem(vnum)
	count = entry.get("count", 1)
	text = name if count <= 1 else "%dx %s" % (count, name)
	lines = []
	if entry.get("damageRequired", 0) != 0:
		lines.append(text_of("TARGET_INFO_GUARANTEED_DAMAGE") % entry["damageRequired"])
	minAttackers, maxAttackers = entry.get("minAttackers", 0), entry.get("maxAttackers", 0)
	if minAttackers > 0 and currentAttackers < minAttackers:
		lines.append(text_of("TARGET_INFO_ATTACKERS_INACTIVE"))
		lines.append("[%s%s] %s" % ("I" * int(float(currentAttackers) / float(minAttackers) * 10),
		                            "." * (10 - int(float(currentAttackers) / float(minAttackers) * 10)),
		                            text_of("TARGET_INFO_ATTACKERS_PROGRESS") % (currentAttackers, minAttackers)))
	elif maxAttackers > 0 and currentAttackers >= maxAttackers:
		lines.append(text_of("TARGET_INFO_ATTACKERS_ABOVE_CAP") % (currentAttackers, maxAttackers))
	return vnum, item.GetIconImageFileName(), text, lines


# --- the board ---------------------------------------------------------------------------

class _ItemRow(ui.Window):
	"""A drop row (OLD's ItemListBoxItem): icon and text; hover shows the tooltip."""

	HEIGHT = 37

	def __init__(self, width, vnum, icon, text, lines):
		ui.Window.__init__(self)
		self.SetSize(width, self.HEIGHT + 12 * len(lines))
		self.vnum = vnum
		self.tooltip = None
		image = ui.ExpandedImageBox()
		image.SetParent(self)
		image.AddFlag("not_pick")
		if icon:
			image.LoadImage(icon)
		image.Show()
		name = ui.TextLine()
		name.SetParent(self)
		name.SetPosition(37, 0)
		name.SetText(text)
		name.Show()
		self.image = image
		self.lines = [name]
		for index, line in enumerate(lines):
			extra = ui.TextLine()
			extra.SetParent(self)
			extra.SetPosition(37, 12 * (index + 1))
			extra.SetText(line)
			extra.Show()
			self.lines.append(extra)

	def SetTooltip(self, tooltip):
		self.tooltip = tooltip

	def OnMouseOverIn(self):
		if self.tooltip:
			self.tooltip(self.vnum)

	def OnMouseOverOut(self):
		if self.tooltip:
			self.tooltip(0)


class InfoBoard(ui.ThinBoard):
	"""OLD's uiTarget.InfoBoard: the stats and the drops of the target's race."""

	BOARD_WIDTH = 250
	LINE_STEP = 17
	MAX_ITEM_COUNT = 5
	ROW_HEIGHT = _ItemRow.HEIGHT

	def __init__(self):
		self._InitBoard()
		self.AddFlag("float")
		self.race = 0
		self.vid = 0
		self.itemScrollWnd = None
		self.waiting = False
		self.retries = 0
		self.nextRetry = 0.0
		self.yPos = 0
		self.children = []
		self.itemRows = []
		self.itemTooltip = self._MakeTooltip()
		self.SetSize(self.BOARD_WIDTH, 0)

	def _InitBoard(self):
		ui.ThinBoard.__init__(self)

	def _MakeTooltip(self):
		tooltip = uiToolTip.ItemToolTip()
		tooltip.HideToolTip()
		return tooltip

	def Destroy(self):
		self.itemTooltip = None
		self.itemScrollWnd = None
		self.children = []
		self.itemRows = []
		self.Hide()

	def Open(self, targetBoard, race, vid):
		self.vid = vid
		if not known(race):
			self.retries = 0
			self.__Request()
		self.__Load(race)
		self.__PlaceUnder(targetBoard)
		self.Show()
		self.SetTop()

	def Close(self):
		self.waiting = False
		if self.itemTooltip:
			self.itemTooltip.HideToolTip()
		self.Hide()

	def Refresh(self):
		"""An answer arrived: the rows it brought."""
		self.waiting = False
		if self.IsShow():
			self.__Load(self.race)

	def RefreshAttackerInfo(self):
		if self.IsShow():
			self.__Load(self.race)

	def __Request(self):
		net.SendTargetInfoLoad(self.vid)
		self.waiting = True
		self.ScheduleRetry()

	def ScheduleRetry(self):
		self.nextRetry = app.GetTime() + RETRY_DELAY

	def RetryRequest(self):
		"""The answer did not come (the server's limit dropped the request):
		ask again, a few times, while the board is open."""
		if not self.waiting or not self.IsShow():
			return
		if self.retries >= RETRY_MAX or known(self.race):
			self.waiting = False
			return
		self.retries += 1
		self.__Request()

	def __PlaceUnder(self, targetBoard):
		"""Under the target board; the NovaUI target board has no window frame
		(a legacy info board can sit under it when the target-info flag is off),
		so the board then goes to the same spot at the screen's top center."""
		getLeft = getattr(targetBoard, "GetLeft", None)
		if getLeft is None:
			self.SetPosition((wndMgr.GetScreenWidth() - self.GetWidth()) // 2, 96)
			return
		self.SetPosition(getLeft() + (targetBoard.GetWidth() - self.GetWidth()) // 2, targetBoard.GetBottom() - 17)

	def __Load(self, race):
		self.race = race
		self.yPos = 7
		self.children = []
		self.AppendLines(stat_lines(race))
		self.AppendSeperator()
		self.AppendLines(race_lines(race))
		self.AppendSeperator()
		self.AppendLines(resist_lines(race))
		self.AppendSeperator()
		self.LoadDrops(race)
		self.FinishLoad()

	def FinishLoad(self):
		self.SetSize(self.BOARD_WIDTH, self.yPos + 10)

	def AppendLines(self, lines):
		for text in lines:
			self.AppendTextLine(text)

	def AppendTextLine(self, text):
		textLine = ui.TextLine()
		textLine.SetParent(self)
		textLine.SetWindowHorizontalAlignCenter()
		textLine.SetHorizontalAlignCenter()
		textLine.SetText(text)
		textLine.SetPosition(0, self.yPos)
		textLine.Show()
		self.children.append(textLine)
		self.yPos += self.LINE_STEP

	def AppendSeperator(self):
		line = ui.Bar()
		line.SetParent(self)
		line.SetPosition(10, self.yPos)
		line.SetSize(self.BOARD_WIDTH - 20, 1)
		line.SetColor(0xff6b6352)
		line.Show()
		self.children.append(line)
		self.yPos += 6

	def LoadDrops(self, race):
		"""OLD __LoadInformation_Drops, uiTarget.py:478-510."""
		data = data_of(race)
		if data is None or not data["items"]:
			self.AppendTextLine(text_of("TARGET_INFO_NO_ITEM_TEXT"))
			self.itemScrollWnd = None
			return
		attackers = data.get("currentAttackers", 0)
		rows = [item_row(entry, attackers) for entry in data["items"]]
		self.MakeDropList(rows)

	def MakeDropList(self, rows):
		contentWidth = self.BOARD_WIDTH - 40
		content = ui.Window()
		content.SetSize(contentWidth, 0)
		content.Show()
		yItemPos = 0
		self.itemRows = []
		for vnum, icon, text, lines in rows:
			row = _ItemRow(contentWidth, vnum, icon, text, lines)
			row.SetParent(content)
			row.SetPosition(0, yItemPos)
			row.SetTooltip(ui.__mem_func__(self.OnShowItemTooltip))
			row.Show()
			self.itemRows.append(row)
			yItemPos += row.GetHeight()
		content.SetSize(contentWidth, yItemPos)
		height = min(self.ROW_HEIGHT * self.MAX_ITEM_COUNT, yItemPos)
		scroll = ui.ScrollWindow(contentWidth, height, ui.ScrollWindow.THIN)
		scroll.SetParent(self)
		scroll.SetPosition(15, self.yPos)
		scroll.SetContentWindow(content)
		scroll.FitWidth(contentWidth)
		scroll.OnContentWindowSizeChange()
		scroll.Show()
		self.children.append(content)
		self.children.append(scroll)
		self.itemScrollWnd = scroll
		self.yPos += height + 5

	def OnShowItemTooltip(self, vnum):
		if not self.itemTooltip:
			return
		if not vnum:
			self.itemTooltip.HideToolTip()
			return
		self.itemTooltip.SetItemToolTip(vnum)

	def OnUpdate(self):
		if self.waiting and app.GetTime() >= self.nextRetry:
			self.RetryRequest()

	def OnRunMouseWheel(self, length):
		if self.itemScrollWnd:
			return self.itemScrollWnd.OnRunMouseWheel(length)
		return False

	def OnPressEscapeKey(self):
		self.Close()
		return True
