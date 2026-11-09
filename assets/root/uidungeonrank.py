## The dungeon ranking (NOVA-25; OLD root/uiDungeonRank.py, ENABLE_DUNGEON_RANKING).
##
## A ranking button of the dungeon manager (uitimerwindow.TimerWindow) opens it empty with its
## loading line (Interface.OpenDungeonRank: Open(-1, -1)) and sends "/rank_dungeon <type> <dungeon>".
## The server answers with up to ten GC::DUNGEON_RANK rows (player.GetDungeonRank()), then the
## chat commands "SetPersonalDungeonRank /<rank>/<name>/<count>/<type>" (the player's own row)
## and "RefreshDungeonRank <type> <dungeon>", which fills the rows (RefreshDungeonRank) and
## titles the window with the dungeon's name and the ranking (the time ranking shows H:MM:SS,
## the others a dotted number). Walking more than 1500 away on either axis from where it opened
## closes it (OnUpdate, as OLD).
##
## OLD's row and header art and its loading animation (ui/dungeon_manager/new/*,
## ui/game/battle_pass/big_loading/*) are not in NEW's packs: each row is a bar with OLD's text
## positions and colors, and the loading state is a line of text.

import datetime

import ui
import player
import localeInfo
import uiScriptLocale

WINDOW_TITLE = {
	0 : uiScriptLocale.DUNGEON_RANK_TITLE1,
	1 : uiScriptLocale.DUNGEON_RANK_TITLE2,
	2 : uiScriptLocale.DUNGEON_RANK_TITLE3,
}

# OLD's row colors: gold, silver and bronze for the first three, blue for the player's own row.
ROW_COLORS = {0: 0xffce9d32, 1: 0xffc5c5c5, 2: 0xff985f50, 10: 0xff408cc3}
ROW_TEXT_COLOR = 0xff919191
ROW_BASE_Y = 67
ROW_STEP = 29
LEAVE_RANGE = 1500


def time_text(seconds):
	"""OLD's str(datetime.timedelta(seconds=...)): H:MM:SS."""
	return str(datetime.timedelta(seconds=int(seconds)))


def count_text(count, rank_type):
	"""A row's count: the time ranking's H:MM:SS, the others' dotted number; "-" stays "-"."""
	if int(rank_type) == 0:
		return count
	try:
		return localeInfo.NumberToString(int(count))
	except (TypeError, ValueError):
		return count


class DungeonRankWindow(ui.ScriptWindow):
	MAX_LINE_COUNT = 10

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.xRankOpen = 0
		self.yRankOpen = 0
		self.rankImages = []
		self.loadingText = None
		self.isLoaded = False

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def LoadWindow(self):
		if self.isLoaded:
			return
		self.isLoaded = True
		self.__LoadWindow()
		self.ResetText()
		self.rankImages[0].SetTextColor(ROW_COLORS[0])
		self.rankImages[1].SetTextColor(ROW_COLORS[1])
		self.rankImages[2].SetTextColor(ROW_COLORS[2])
		self.rankImages[10].SetTextColor(ROW_COLORS[10])
		self.rankImages[10].SetRank("-", "-", "-")

	def __LoadWindow(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/dungeonrankwindow.py")
		except:
			import exception
			exception.Abort("DungeonRankWindow.__LoadWindow.LoadScript")

		try:
			getObject = self.GetChild
			self.board = getObject("board")
			self.titleBar = getObject("TitleBar")
			self.title = getObject("TitleName")
		except:
			import exception
			exception.Abort("DungeonRankWindow.__LoadWindow.SetObject")

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))

		self.rankImages = []
		for x in range(self.MAX_LINE_COUNT + 1):
			yPos = ROW_BASE_Y + x * ROW_STEP
			if x == self.MAX_LINE_COUNT:
				yPos += 2
			image = RankImage(self, x)
			image.SetPosition(8, yPos)
			self.rankImages.append(image)

		loadingText = ui.TextLine()
		loadingText.SetParent(self)
		loadingText.SetPosition(0, 80)
		loadingText.SetWindowHorizontalAlignCenter()
		loadingText.SetHorizontalAlignCenter()
		loadingText.SetText(uiScriptLocale.DUNGEON_RANK_LOADING)
		loadingText.Hide()
		self.loadingText = loadingText

	def ResetText(self):
		for x in range(self.MAX_LINE_COUNT):
			self.rankImages[x].SetRank("-", "-", "-")

	def RefreshDungeonRank(self, type, dungeonIndex):
		self.ResetText()
		self.Open(type, dungeonIndex)
		ranks = player.GetDungeonRank()
		for rank, image in zip(ranks, self.rankImages):
			count = str(rank[2])
			if type == 0:
				count = time_text(rank[2])
			image.SetRank(str(rank[0]), rank[1], count, type)
		player.ClearDungeonRank()
		if self.loadingText:
			self.loadingText.Hide()

	def SetPersonalDungeonRank(self, rank, name, count, type):
		textCount = count
		if int(type) == 0:
			textCount = time_text(int(count))
		self.rankImages[10].SetRank(rank if rank != "0" else "-", name, textCount, type)

	def Open(self, rType, dungeonIndex):
		if rType == -1 and dungeonIndex == -1:
			if self.loadingText:
				self.loadingText.Show()
			self.SetTop()
			self.Show()
			(self.xRankOpen, self.yRankOpen, z) = player.GetMainCharacterPosition()
			return
		elif self.loadingText:
			self.loadingText.Hide()

		import uiTimerWindow
		self.title.SetText("%s %s" % (uiTimerWindow.get_title(int(dungeonIndex)), WINDOW_TITLE.get(int(rType), "")))
		if not self.IsShow():
			self.SetTop()
		self.Show()
		(self.xRankOpen, self.yRankOpen, z) = player.GetMainCharacterPosition()

	def Destroy(self):
		self.Close()
		self.ClearDictionary()
		self.board = None
		self.titleBar = None
		self.title = None
		self.loadingText = None
		self.xRankOpen = 0
		self.yRankOpen = 0
		for image in self.rankImages:
			image.Destroy()
		del self.rankImages[:]

	def Close(self):
		self.Hide()

	def OnUpdate(self):
		(x, y, z) = player.GetMainCharacterPosition()
		if abs(x - self.xRankOpen) > LEAVE_RANGE or abs(y - self.yRankOpen) > LEAVE_RANGE:
			self.Close()

	def OnPressEscapeKey(self):
		self.Close()
		return True


class RankImage(ui.Window):
	"""One row (OLD RankImage, an image of the row art): the rank, the name and the count at OLD's
	places, centered on -138, -36 and 102 from the row's middle."""

	WIDTH = 340
	HEIGHT = 27

	def __init__(self, parent, num):
		ui.Window.__init__(self)
		self.SetParent(parent)
		self.num = num
		self.SetSize(self.WIDTH, self.HEIGHT)
		self.__LoadWindow()
		self.Show()

	def __del__(self):
		ui.Window.__del__(self)

	def __LoadWindow(self):
		self.bar = ui.Bar()
		self.bar.SetParent(self)
		self.bar.SetPosition(0, 0)
		self.bar.SetSize(self.WIDTH, self.HEIGHT)
		self.bar.SetColor(0x80203048 if self.num == 10 else 0x80000000)
		self.bar.AddFlag("not_pick")
		self.bar.Show()

		self.rank = ui.MakeTextLine(self)
		self.name = ui.MakeTextLine(self)
		self.count = ui.MakeTextLine(self)
		self.rank.SetPosition(-138, -1)
		self.name.SetPosition(-36, -1)
		self.count.SetPosition(102, -1)
		self.SetTextColor(ROW_TEXT_COLOR)

	def SetTextColor(self, color):
		self.rank.SetPackedFontColor(color)
		self.name.SetPackedFontColor(color)
		self.count.SetPackedFontColor(color)

	def SetRank(self, rank, name, count, type=-1):
		self.rank.SetText(rank)
		self.name.SetText(name)
		self.count.SetText(count_text(count, type))

	def Destroy(self):
		self.bar = None
		self.rank = None
		self.name = None
		self.count = None
