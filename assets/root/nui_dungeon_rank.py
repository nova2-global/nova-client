"""NovaUI dungeon ranking (nui/windows/dungeon-rank/dungeon-rank.rml; NOVA-25).

While the dungeon-rank flag is on, Interface.__MakeDungeonWindows makes
DungeonRankWindow below through nui_windows.make() instead of
uiDungeonRank.DungeonRankWindow: a subclass of the legacy class
(nui_facade.Facade) whose loader puts proxies where the widgets were (the title
bar and its text, the loading line, the eleven rows), so the loading state, the
server's rows (player.GetDungeonRank, cleared once shown), the personal row, the
title (the dungeon and the ranking) and the time ranking's H:MM:SS are legacy's
code. Legacy's per-frame walk-away (more than 1500 on either axis from where it
opened, uidungeonrank.py OnUpdate) is nuigame.WatchLeaveRange's watch, armed by
Open and stopped by Hide. No Python runs per frame."""

import ui
import uiDungeonRank

import nui
import nui_facade
import nui_hud
import nui_proxies

try:
	import nuigame
except ImportError:  # a client without the NovaUI game module: no watch
	nuigame = None

DOCUMENT = "nui/windows/dungeon-rank/dungeon-rank.rml"
KEY = "dungeon-rank"
ROWS = uiDungeonRank.DungeonRankWindow.MAX_LINE_COUNT
# Legacy's walk-away rule is "more than LEAVE_RANGE", the watch's own rule.
LEAVE_RANGE = uiDungeonRank.LEAVE_RANGE


class _RankBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The ranking's document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "dungeon_rank"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.titleBar.close()


class _RowProxy(nui_proxies._Shown):
	"""uidungeonrank.RankImage: SetRank's three texts, legacy's count rule
	(count_text), for the board."""

	def __init__(self, owner, num):
		self.owner = owner
		self.num = num
		self.rank = ""
		self.name = ""
		self.count = ""
		self.color = None

	def SetTextColor(self, color):
		self.color = int(color) & 0xFFFFFFFF

	def SetRank(self, rank, name, count, type=-1):
		self.rank = str(rank)
		self.name = str(name)
		self.count = str(uiDungeonRank.count_text(count, type))
		self.owner._publish_rows()

	def Destroy(self):
		pass


class DungeonRankWindow(nui_facade.Facade, uiDungeonRank.DungeonRankWindow):
	"""uiDungeonRank.DungeonRankWindow on NovaUI (Interface.wndDungeonRank)."""

	KEY = KEY
	BOARD = _RankBoard
	PLACE = "center"
	LEAVE_RANGE = True
	OnUpdate = None

	def __init__(self):
		self.nui_begin()
		try:
			uiDungeonRank.DungeonRankWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			# The uiscript's title until the first ranking names its dungeon.
			"title": nui.plain_text(uiDungeonRank.WINDOW_TITLE[0]),
			"loading": False,
			"rows": [{"rank": "-", "name": "-", "count": "-"} for _ in range(ROWS)],
			"own": {"rank": "-", "name": "-", "count": "-"},
		}

	# --- the loader (uidungeonrank.py __LoadWindow, on proxies) ------------------------

	def _DungeonRankWindow__LoadWindow(self):
		# The uiscript's style (dungeonrankwindow.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		self.board = nui_proxies.BoardProxy(uiDungeonRank.RankImage.WIDTH + 16, 402)
		self.titleBar = nui_proxies.BoardProxy()
		self.title = nui_proxies.TextProxy(lambda text: self.nui_set(title=nui.plain_text(text)))
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))
		self.rankImages = [_RowProxy(self, x) for x in range(ROWS + 1)]
		self.loadingText = nui_proxies.TextProxy()
		self.loadingText.on_show = lambda shown: self.nui_set(loading=bool(shown))
		self.loadingText.Hide()

	# --- what NovaUI changes -----------------------------------------------------------

	def Open(self, rType, dungeonIndex):
		"""Legacy's, then the walk-away watch from where it opened."""
		uiDungeonRank.DungeonRankWindow.Open(self, rType, dungeonIndex)
		if nuigame is not None:
			nuigame.WatchLeaveRange(KEY, LEAVE_RANGE, ui.__mem_func__(self.Close), False)

	def Hide(self):
		nui_facade.Facade.Hide(self)
		if not self.IsShow() and nuigame is not None:
			nuigame.StopLeaveRange(KEY)

	def Destroy(self):
		self.nui_discard()
		uiDungeonRank.DungeonRankWindow.Destroy(self)

	# --- the board's model -------------------------------------------------------------

	def _publish_rows(self):
		if self.__dict__.get("_state") is None or len(self.rankImages) <= ROWS:
			return
		row = lambda proxy: {"rank": nui.plain_text(proxy.rank), "name": nui.plain_text(proxy.name),
		                     "count": nui.plain_text(proxy.count)}
		self.nui_set(rows=[row(proxy) for proxy in self.rankImages[:ROWS]], own=row(self.rankImages[ROWS]))
