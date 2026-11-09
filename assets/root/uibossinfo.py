## The boss info panel (NOVA-27; OLD root/uiBossInfo.py, BOSS_INFO): the
## bosses of the current map at the left edge of the screen, alive (green) or
## dead (red), with a tooltip of each boss's level, state and respawn clock.
## The server sends the list at login and to every player after a boss dies
## or respawns: "ClearBossInfo", one "AddBossInfo <vnum> <alive> <respawn
## time>" per boss (the respawn time is a unix time; 0 or past means none) and
## "BossInfoLoadComplete", which game.py hands to the Interface. A map with no
## boss sends nothing, and an empty list closes the panel.
##
## The panel slides out of the screen and back with its arrow button; whether
## it is open is systemSetting's BOSS_INFO flag (metin2.cfg), as in OLD.
##
## OLD's art (ui/notifications/new_ui/*_arrow_*.png, ui/boss_info/bg_*.png,
## alive.gif, dead.gif) is not in NEW's packs: the board is the thin board,
## the arrows are the public xsmall buttons with "<" and ">", a row is a dark
## bar and its state a dot in the icon's place; positions and sizes are OLD's.
## OLD's literal "Level %d", "Alive", "Dead" and "Respawning in %s" are locale
## keys (BOSS_INFO_*), and the clock is NEW's RTSecondToDHMS.
##
## OLD bugs fixed: ShowAllWindows showed the empty panel on a map without
## bosses (Interface.ShowAllWindows asks HasBossInfo); ClearBossInfo dropped
## the rows' references but left them on the board until collected (they
## are hidden first); one tooltip per row, rebuilt every frame for each
## (one tooltip, refreshed only while a row is hovered).

import app
import ui
import nonplayer
import systemSetting
import localeInfo
import uiToolTip

PUBLIC_PATH = "d:/ymir work/ui/public/"
GREEN_COLOR = 0xffc3d4c4
RED_COLOR = 0xFFe57875
ROW_COLOR = 0xB0000000

# OLD uiBossInfo.py's geometry.
POSITION_Y = 250
BOARD_X = 10
NARROW_WIDTH = 120 + 18
WIDE_WIDTH = 167 + 18
NARROW_ROW_WIDTH = 118          # OLD's bg_small.png
WIDE_ROW_WIDTH = 165            # OLD's bg_middle.png
ROW_HEIGHT = 32
ROW_TOP = 16
ROW_STEP = 40
SINGLE_ROW_Y = 46
WIDE_NAME_LENGTH = 14           # a longer name takes the wide rows
NAME_X = 40
DOT_SIZE = 8
DOT_POSITION = (14, 12)         # in the 36 px of OLD's state icon
BUTTON_HEIGHT = 32
BUTTON_Y = 35
SLIDE_STEP = 4


def window_height(count):
	"""OLD's height for `count` rows: two rows at least, 53 px each, less a
	little for three to six rows (OLD's own table)."""
	height = max(2, count) * 53
	return height - {3: 8, 4: 15, 5: 22, 6: 29}.get(count, 0)


def row_position(count, index):
	if count == 1:
		return (BOARD_X, SINGLE_ROW_Y)
	return (BOARD_X, ROW_TOP + index * ROW_STEP)


def monster_level(vnum):
	"""nonplayer.GetMonsterLevel (OLD's export); 0 where the client has none."""
	get = getattr(nonplayer, "GetMonsterLevel", None)
	return int(get(vnum)) if get is not None else 0


def describe(boss, now):
	"""The tooltip's lines for `boss` at the unix time `now`: its level, its
	state and, while one is ahead, the time until it respawns."""
	lines = []
	level = boss.GetLevel()
	if level > 0:
		lines.append(localeInfo.BOSS_INFO_LEVEL % level)
	lines.append(localeInfo.BOSS_INFO_ALIVE if boss.IsAlive() else localeInfo.BOSS_INFO_DEAD)
	left = boss.GetTimeUntilSpawn() - now
	if left > 0:
		lines.append(localeInfo.BOSS_INFO_RESPAWN % localeInfo.RTSecondToDHMS(left))
	return lines


class BossRow(ui.Bar):
	"""One boss: a dark bar with the state dot and the name; hovering shows
	the panel's tooltip for it."""

	def __init__(self, owner, boss):
		ui.Bar.__init__(self)
		self.owner = owner
		self.boss = boss
		self.SetColor(ROW_COLOR)

		self.dot = ui.Bar()
		self.dot.SetParent(self)
		self.dot.SetSize(DOT_SIZE, DOT_SIZE)
		self.dot.SetPosition(*DOT_POSITION)
		self.dot.SetColor(GREEN_COLOR if boss.IsAlive() else RED_COLOR)
		self.dot.Show()

		self.nameText = ui.TextLine()
		self.nameText.SetParent(self)
		self.nameText.SetPosition(NAME_X, 0)
		self.nameText.SetWindowVerticalAlignCenter()
		self.nameText.SetVerticalAlignCenter()
		self.nameText.SetText(boss.GetBossName())
		self.nameText.SetPackedFontColor(GREEN_COLOR if boss.IsAlive() else RED_COLOR)
		self.nameText.Show()

	def OnMouseOverIn(self):
		self.owner.ShowBossToolTip(self.boss)

	def OnMouseOverOut(self):
		self.owner.HideBossToolTip()


class BossInfoWindow(ui.Window):
	def __init__(self):
		ui.Window.__init__(self)

		self.bossInfo = []
		self.rows = []
		self.expandButton = None
		self.minimizeButton = None
		self.windowWidth = 0
		self.isActiveSlide = False
		self.isActiveSlideOut = False
		self.hoveredBoss = None
		self.toolTip = None
		self.__CreateButtons()
		self.__CreateBoard()
		self.__CreateToolTip()

	def __del__(self):
		ui.Window.__del__(self)

	def Destroy(self):
		self.ClearBossInfo()
		self.HideBossToolTip()
		self.toolTip = None
		self.expandButton = None
		self.minimizeButton = None
		self.board = None

	def __CreateBoard(self):
		self.board = ui.ThinBoard()
		self.board.SetParent(self)
		self.board.SetSize(NARROW_WIDTH, 200)
		self.board.SetPosition(BOARD_X, 0)
		self.board.Show()

	def __CreateButtons(self):
		self.expandButton = ui.MakeButton(self, 0, BUTTON_Y, localeInfo.BOSS_INFO_EXPAND, PUBLIC_PATH,
		                                  "xsmall_button_01.sub", "xsmall_button_02.sub", "xsmall_button_03.sub")
		self.expandButton.SetText(">")
		self.minimizeButton = ui.MakeButton(self, 0, BUTTON_Y, localeInfo.BOSS_INFO_COLLAPSE, PUBLIC_PATH,
		                                    "xsmall_button_01.sub", "xsmall_button_02.sub", "xsmall_button_03.sub")
		self.minimizeButton.SetText("<")

		self.expandButton.SetEvent(ui.__mem_func__(self.__ToggleWindow))
		self.minimizeButton.SetEvent(ui.__mem_func__(self.__ToggleWindow))

		self.expandButton.Hide()

	def __CreateToolTip(self):
		self.toolTip = uiToolTip.ToolTip()
		self.toolTip.SetFollow(True)
		self.toolTip.Hide()

	def __MakeRow(self, boss):
		row = BossRow(self, boss)
		row.SetParent(self.board)
		return row

	def __ToggleWindow(self):
		if systemSetting.IsBossInfoExpandend():
			systemSetting.SetIsBossInfoExpandend(False)
			self.SlideOut()
		else:
			systemSetting.SetIsBossInfoExpandend(True)
			self.SlideIn()

	def SlideIn(self):
		self.Show()

		self.isActiveSlide = True
		self.isActiveSlideOut = False

		self.expandButton.Hide()
		self.minimizeButton.Show()

	def SlideOut(self):
		self.isActiveSlide = False
		self.isActiveSlideOut = True

		self.expandButton.Show()
		self.minimizeButton.Hide()

	def OnUpdate(self):
		if self.isActiveSlide:
			x, y = self.GetLocalPosition()
			if x < 0:
				self.SetPosition(x + SLIDE_STEP, y)

		if self.isActiveSlideOut:
			x, y = self.GetLocalPosition()
			if x > -(self.windowWidth - 20):
				self.SetPosition(x - SLIDE_STEP, y)

		if self.hoveredBoss is not None:
			self.__FillToolTip(self.hoveredBoss)

	def __FillToolTip(self, boss):
		self.toolTip.ClearToolTip()
		self.toolTip.SetTitle(boss.GetBossName())
		self.toolTip.AppendSpace(5)
		for line in describe(boss, app.GetGlobalTimeStamp()):
			self.toolTip.AutoAppendTextLine(line)
		self.toolTip.AlignHorizonalCenter()

	def ShowBossToolTip(self, boss):
		self.hoveredBoss = boss
		self.__FillToolTip(boss)
		self.toolTip.ShowToolTip()

	def HideBossToolTip(self):
		self.hoveredBoss = None
		if self.toolTip:
			self.toolTip.HideToolTip()

	def ClearBossInfo(self):
		for row in self.rows:
			row.Hide()
		self.HideBossToolTip()
		self.bossInfo = []
		self.rows = []

	def AddBossInfo(self, bossVnum, isAlive, timeUntilSpawn):
		self.bossInfo.append(Boss(bossVnum, isAlive, timeUntilSpawn))

	def HasBossInfo(self):
		return len(self.bossInfo) > 0

	def BossInfoLoadComplete(self):
		if len(self.bossInfo) == 0:
			self.Close()
			return

		bossCount = len(self.bossInfo)
		wide = max(boss.GetBossNameLength() for boss in self.bossInfo) > WIDE_NAME_LENGTH
		minWidth = WIDE_WIDTH if wide else NARROW_WIDTH
		rowWidth = WIDE_ROW_WIDTH if wide else NARROW_ROW_WIDTH

		for index, boss in enumerate(self.bossInfo):
			row = self.__MakeRow(boss)
			row.SetSize(rowWidth, ROW_HEIGHT)
			row.SetPosition(*row_position(bossCount, index))
			row.Show()
			self.rows.append(row)

		windowHeight = window_height(bossCount)
		self.windowWidth = minWidth

		self.SetSize(minWidth + 25, windowHeight)
		self.board.SetSize(minWidth, windowHeight)

		if bossCount == 1:
			buttonY = 16
		else:
			buttonY = windowHeight // 2 - BUTTON_HEIGHT // 2
		self.expandButton.SetPosition(self.windowWidth - 9, buttonY)
		self.minimizeButton.SetPosition(self.windowWidth - 9, buttonY)

		self.isActiveSlide = False
		self.isActiveSlideOut = False
		if systemSetting.IsBossInfoExpandend():
			self.minimizeButton.Show()
			self.expandButton.Hide()
			self.SetPosition(-10, POSITION_Y)
		else:
			self.expandButton.Show()
			self.minimizeButton.Hide()
			self.SetPosition(-1 * (self.windowWidth - 10), POSITION_Y)

		self.Show()

	def Close(self):
		self.HideBossToolTip()
		self.Hide()


class Boss(object):
	def __init__(self, bossVnum, isAlive, timeUntilSpawn):
		self.bossVnum = int(bossVnum)
		self.isAlive = int(isAlive)
		self.timeUntilSpawn = int(timeUntilSpawn)

	def GetBossName(self):
		return nonplayer.GetMonsterName(self.bossVnum)

	def GetLevel(self):
		return monster_level(self.bossVnum)

	def GetBossNameLength(self):
		return len(self.GetBossName())

	def IsAlive(self):
		return self.isAlive

	def GetTimeUntilSpawn(self):
		return self.timeUntilSpawn
