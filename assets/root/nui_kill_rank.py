"""NovaUI kill ranking (nui/windows/kill-rank/kill-rank.rml; NOVA-29).

While the kill-rank flag is on, Interface.__MakeWindows makes KillRankWindow
below through nui_windows.make() instead of uiKillRank.KillRankWindow: a
subclass of the legacy class (nui_facade.Facade) whose loader puts proxies
where the widgets were (the title bar and its text, the eight tabs, the ten
rows and the player's own row). So the requests ("/kill_rank N"), the
answer's handling (RefreshKillRank, SetPersonalKillRank), the tabs' states and
the rows' texts are legacy's code (OLD uiKillRank.py).

Legacy closed the window when the player walked more than LEAVE_RANGE away
from where it opened, in its OnUpdate; here a nuigame.WatchLeaveRange watch
(armed at each Open, stopped at Hide) runs legacy's Close, so no Python runs
per frame. The board exists only while the window shows."""

import ui
import uiKillRank

import nui
import nui_facade
import nui_hud
import nui_proxies

try:
	import nuigame
except ImportError:  # an exe without the Wave 2a engine
	nuigame = None

DOCUMENT = "nui/windows/kill-rank/kill-rank.rml"
KEY = "kill-rank"


class _RowProxy(object):
	"""uiKillRank.RankRow: its four texts, for the board."""

	def __init__(self, owner, index):
		self.owner = owner
		self.index = index
		self.values = ["", "", "", ""]

	def SetRank(self, rank, name, guildName, count):
		self.values = [str(rank), str(name), str(guildName),
		               uiKillRank.count_text(count) if count != "" else ""]
		self.owner._publish_rows()

	def Clear(self):
		self.values = ["", "", "", ""]
		self.owner._publish_rows()

	def GetTexts(self):
		return list(self.values)


class _KillRankBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The kill ranking's document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "kill_rank"

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

	@nui.on("tab_press")
	def on_tab_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.nui_tab_press(int(index))


class KillRankWindow(nui_facade.Facade, uiKillRank.KillRankWindow):
	"""uiKillRank.KillRankWindow on NovaUI (Interface.wndKillRank)."""

	KEY = KEY
	BOARD = _KillRankBoard
	PLACE = "center"
	LEAVE_RANGE = True
	OnUpdate = None

	def __init__(self):
		self.nui_begin()
		try:
			uiKillRank.KillRankWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {"title": "", "tab": -1, "rows": [], "own": {"rank": "", "name": "", "guild": "", "count": ""}}

	def _KillRankWindow__LoadWindow(self):
		self.AddFlag("movable")
		self.AddFlag("float")
		self.board = nui_proxies.BoardProxy(390, 380)
		self.titleBar = nui_proxies.BoardProxy(375, 21)
		self.title = nui_proxies.TextProxy(lambda text: self.nui_set(title=nui.plain_text(text)))
		self.rankingTab = [nui_proxies.ButtonProxy(self._publish_tabs) for _ in range(uiKillRank.STATIC_RANKING_TYPES)]
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))
		for x in range(uiKillRank.STATIC_RANKING_TYPES):
			self.rankingTab[x].SAFE_SetEvent(self.SetRankingPage, x)
		self.rankRows = [_RowProxy(self, index) for index in range(uiKillRank.MAX_LINE_COUNT + 1)]
		self._publish_rows()

	def _publish_tabs(self, changed=None):
		tabs = getattr(self, "rankingTab", None) or []
		down = [index for index, tab in enumerate(tabs) if tab.down]
		self.nui_set(tab=down[0] if down else -1)

	def _publish_rows(self):
		rows = getattr(self, "rankRows", None) or []
		shown = []
		for row in rows[:uiKillRank.MAX_LINE_COUNT]:
			rank, name, guild, count = row.values
			if not rank and not name:
				continue
			shown.append({"rank": nui.plain_text(rank), "name": nui.plain_text(name), "guild": nui.plain_text(guild),
			              "count": nui.plain_text(count), "place": row.index + 1})
		own = rows[uiKillRank.MAX_LINE_COUNT].values if len(rows) > uiKillRank.MAX_LINE_COUNT else ["", "", "", ""]
		self.nui_set(rows=shown, own={"rank": nui.plain_text(own[0]), "name": nui.plain_text(own[1]),
		                               "guild": nui.plain_text(own[2]), "count": nui.plain_text(own[3])})

	def nui_tab_press(self, index):
		if 0 <= index < len(self.rankingTab):
			self.rankingTab[index].click()

	def Open(self, type):
		"""Legacy's, then the walk-away watch (legacy's OnUpdate rule: |dx| or
		|dy| above LEAVE_RANGE, the watch's own rule)."""
		uiKillRank.KillRankWindow.Open(self, type)
		if nuigame is not None:
			nuigame.WatchLeaveRange(KEY, uiKillRank.LEAVE_RANGE, ui.__mem_func__(self.Close), False)

	def Hide(self):
		nui_facade.Facade.Hide(self)
		if not self.IsShow() and nuigame is not None:
			nuigame.StopLeaveRange(KEY)
