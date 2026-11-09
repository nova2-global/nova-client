"""The kill ranking (NOVA-29; OLD ENABLE_KILL_COUNT, uiKillRank.py, game.py:3082 and
3872-3876, interfaceModule.py:780-782 and 4239-4246).

Eight rankings, OLD's numbers: 0 stones, 1 bosses, 2 players, 3 monsters, 4 dungeons
(counts nothing until NOVA-25), 5 players in the PvP arenas, 6 refines, 7 minutes
played. Open(-1) asks for ranking 0 ("/kill_rank 0"); a tab asks for its ranking.
The answer (GC::KILL_RANK) reaches game.py as OLD's two calls: SetPersonalKillRank
(the player's own place, name, guild and count, as text) and RefreshKillRank(type),
which shows the ranking: player.GetKillRank()'s rows, the title and the pressed tab.

What differs from OLD:
- the player's own row is shown (PRODUCT-DECISIONS NOVA-29 Q4): OLD's server sent
  it and OLD's game.py left its handler out;
- a ranking with fewer than ten rows empties the rows after its last (OLD kept the
  previous ranking's text there);
- OLD's art (ui/ranking/*, the loading animation) is not in NEW's packs: a board
  with text tabs (uiscript/killrankwindow.py), the rows as text lines.
As OLD's, the window closes when the player walks more than 1500 away from where it
opened (OnUpdate)."""

import net
import ui
import player
import nui_numbers
import uiScriptLocale

STATIC_RANKING_TYPES = 8
MAX_LINE_COUNT = 10
# The rows: rank, name, guild and count columns (x), the first row's y and the step.
ROW_X = (24, 74, 210, 310)
FIRST_ROW_Y = 112
ROW_HEIGHT = 22
OWN_ROW_GAP = 8
# OLD's colors of the first three places and of the player's row (uiKillRank.py:94-97).
ROW_COLORS = {0: 0xffce9d32, 1: 0xffc5c5c5, 2: 0xff985f50, MAX_LINE_COUNT: 0xff408cc3}
ROW_COLOR = 0xff919191
LEAVE_RANGE = 1500


def window_title(type):
	return getattr(uiScriptLocale, "KILL_COUNT_TITLE%d" % type, "")


def own_rank_text(rank):
	"""OLD's own row shows "-" for a player without a place (rank "0")."""
	return rank if rank != "0" else "-"


def count_text(count):
	"""OLD's DottedNumber, grouped by the locale's separator (nui_numbers.group)."""
	return nui_numbers.group(count)


class RankRow(object):
	"""One row's four texts (OLD's RankImage without its art)."""

	def __init__(self, parent, index):
		self.texts = []
		y = FIRST_ROW_Y + index * ROW_HEIGHT + (OWN_ROW_GAP if index == MAX_LINE_COUNT else 0)
		for x in ROW_X:
			text = ui.TextLine()
			text.SetParent(parent)
			text.SetPosition(x, y)
			text.SetPackedFontColor(ROW_COLORS.get(index, ROW_COLOR))
			text.Show()
			self.texts.append(text)

	def SetRank(self, rank, name, guildName, count):
		for text, value in zip(self.texts, (rank, name, guildName, count_text(count) if count != "" else "")):
			text.SetText(value)

	def Clear(self):
		for text in self.texts:
			text.SetText("")

	def GetTexts(self):
		return [text.GetText() for text in self.texts]


class KillRankWindow(ui.ScriptWindow):

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.xRankOpen = 0
		self.yRankOpen = 0
		self.rankingTab = []
		self.rankRows = []
		self.title = None
		self.titleBar = None
		self.board = None
		self.type = 0

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def LoadWindow(self):
		self.__LoadWindow()

	def __LoadWindow(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "uiscript/killrankwindow.py")
		except:
			import exception
			exception.Abort("KillRankWindow.__LoadWindow.LoadScript")

		try:
			getObject = self.GetChild
			self.board = getObject("board")
			self.titleBar = getObject("TitleBar")
			self.title = getObject("TitleName")
			self.rankingTab = [getObject("Tab_%d" % x) for x in range(STATIC_RANKING_TYPES)]
		except:
			import exception
			exception.Abort("KillRankWindow.__LoadWindow.SetObject")

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))
		for x in range(STATIC_RANKING_TYPES):
			self.rankingTab[x].SAFE_SetEvent(self.SetRankingPage, x)

		self.rankRows = [self.__MakeRow(x) for x in range(MAX_LINE_COUNT + 1)]

	def __MakeRow(self, index):
		return RankRow(self.board, index)

	def RefreshKillRank(self, type):
		self.Open(type)
		ranks = player.GetKillRank()
		for index, row in enumerate(self.rankRows[:MAX_LINE_COUNT]):
			if index < len(ranks):
				rank = ranks[index]
				row.SetRank(str(rank[0]), rank[1], rank[2], rank[3])
			else:
				row.Clear()
		player.ClearKillRank()
		self.RefreshRankingButtons(type)

	def SetPersonalKillRank(self, rank, name, guildName, count):
		self.rankRows[MAX_LINE_COUNT].SetRank(own_rank_text(rank), name, guildName, int(count))

	def Open(self, type):
		if type == -1:
			net.SendChatPacket("/kill_rank 0")
			type = 0
		self.type = type
		self.title.SetText(window_title(type))
		if not self.IsShow():
			self.SetCenterPosition()
			self.SetTop()
		self.Show()
		(self.xRankOpen, self.yRankOpen, z) = player.GetMainCharacterPosition()

	def Destroy(self):
		self.Close()
		self.ClearDictionary()
		self.board = None
		self.titleBar = None
		self.title = None
		self.rankingTab = []
		self.rankRows = []

	def Close(self):
		self.Hide()

	def SetRankingPage(self, page):
		net.SendChatPacket("/kill_rank %d" % page)

	def RefreshRankingButtons(self, page):
		for x in range(STATIC_RANKING_TYPES):
			if x == page:
				self.rankingTab[x].Down()
			else:
				self.rankingTab[x].SetUp()

	def OnUpdate(self):
		(x, y, z) = player.GetMainCharacterPosition()
		if abs(x - self.xRankOpen) > LEAVE_RANGE or abs(y - self.yRankOpen) > LEAVE_RANGE:
			self.Close()

	def OnPressEscapeKey(self):
		self.Close()
		return True
