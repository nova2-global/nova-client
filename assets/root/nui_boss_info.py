"""NovaUI boss info panel (nui/windows/boss-info/boss-info.rml; NOVA-27).

While the boss-info flag is on (the hud group), Interface.__MakeBossWindows
makes BossInfoWindow below through nui_windows.make() instead of
uiBossInfo.BossInfoWindow: a subclass of the legacy class
(nui_facade.Facade) whose widget makers put proxies where the widgets were
(the board, the two arrow buttons, the tooltip, one proxy per boss row), so
the server's list (ClearBossInfo, AddBossInfo, BossInfoLoadComplete through
the Interface), the expanded flag read and written through systemSetting
(BOSS_INFO in metin2.cfg), the empty list closing the panel and the toggle
are legacy's code. The board shows what the proxies were told.

What NovaUI does instead of legacy's per-frame Python (OnUpdate = None):
- the slide (legacy moves the window 4 px a frame) is a transition on the
  panel's place, run by the `collapsed` key (the expand button shown);
- the tooltip (legacy refreshes the hovered row's every frame) is each row's
  hint, shown on :hover, whose respawn clock is a nui-countdown (the end is
  nui.now() plus the seconds until the respawn time); its countdownend
  republishes the rows, so the respawn line goes as legacy's does when the
  time is up.
The legacy window stays 0 x 0 at its place (SetSize and SetPosition only
record); the sheet anchors the panel at the screen's left edge, 250dp down,
legacy's (-10, 250) for its 10 px inset board."""

import app
import localeInfo
import ui
import uiBossInfo

import nui
import nui_facade
import nui_hud
import nui_proxies

DOCUMENT = "nui/windows/boss-info/boss-info.rml"
KEY = "boss-info"


def respawn_parts():
	"""BOSS_INFO_RESPAWN ("Respawning in %s") around its clock: the text
	before and after it, plain."""
	text = localeInfo.BOSS_INFO_RESPAWN
	before, _, after = text.partition("%s")
	return nui.plain_text(before.rstrip()), nui.plain_text(after.lstrip())


class _BossInfoBoard(nui.Window):
	"""The panel's document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "boss_info"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("toggle_press")
	def on_toggle_press(self, button):
		if button == 0:
			self._owner.nui_toggle()

	@nui.on("respawned")
	def on_respawned(self):
		self._owner.nui_publish()


class _RowProxy(nui_proxies._Shown):
	"""uiBossInfo.BossRow: one boss; its size and place are the sheet's."""

	def __init__(self, boss):
		self.boss = boss
		self.shown = False
		self.size = (0, 0)
		self.position = (0, 0)

	def SetSize(self, width, height):
		self.size = (int(width), int(height))

	def SetPosition(self, x, y):
		self.position = (int(x), int(y))


class _ToolTipProxy(nui_proxies._Shown):
	"""uiToolTip.ToolTip as the panel uses it: the rows' hints in the document
	show the same lines on :hover, so it only records."""

	def __init__(self):
		self.shown = False
		self.title = ""
		self.lines = []
		self.follow = False

	def ClearToolTip(self):
		self.title = ""
		self.lines = []

	def SetTitle(self, text):
		self.title = text

	def AppendSpace(self, size):
		pass

	def AutoAppendTextLine(self, text, color=None, centerAlign=True):
		self.lines.append(text)

	def AlignHorizonalCenter(self):
		pass

	def SetFollow(self, flag):
		self.follow = bool(flag)

	def ShowToolTip(self):
		self.Show()

	def HideToolTip(self):
		self.Hide()


class BossInfoWindow(nui_facade.Facade, uiBossInfo.BossInfoWindow):
	"""uiBossInfo.BossInfoWindow on NovaUI (Interface.wndBossInfo)."""

	KEY = KEY
	BOARD = _BossInfoBoard
	OnUpdate = None

	def __init__(self):
		self.nui_begin()
		try:
			uiBossInfo.BossInfoWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		before, after = respawn_parts()
		return {
			"rows": [],
			"count": 0,
			"single": False,
			"wide": False,
			"collapsed": False,
			"height": uiBossInfo.window_height(0),
			"button_top": 0,
			"respawn_before": before,
			"respawn_after": after,
		}

	# --- the widget makers (uibossinfo.py, on proxies) ----------------------------------

	def _BossInfoWindow__CreateBoard(self):
		self.board = nui_proxies.BoardProxy(uiBossInfo.NARROW_WIDTH, 200)

	def _BossInfoWindow__CreateButtons(self):
		self.expandButton = nui_proxies.ButtonProxy(self._publish_toggle)
		self.minimizeButton = nui_proxies.ButtonProxy(self._publish_toggle)
		self.expandButton.SetEvent(ui.__mem_func__(self._BossInfoWindow__ToggleWindow))
		self.minimizeButton.SetEvent(ui.__mem_func__(self._BossInfoWindow__ToggleWindow))
		self.expandButton.Hide()

	def _BossInfoWindow__CreateToolTip(self):
		self.toolTip = _ToolTipProxy()

	def _BossInfoWindow__MakeRow(self, boss):
		return _RowProxy(boss)

	# --- the legacy window stays 0 x 0 at its place ----------------------------------------

	def SetSize(self, width, height):
		self.nui_size = (int(width), int(height))

	def SetPosition(self, x, y):
		self.nui_position = (int(x), int(y))

	def GetLocalPosition(self):
		return getattr(self, "nui_position", (0, 0))

	# --- legacy's entry points, then the board ------------------------------------------

	def ClearBossInfo(self):
		uiBossInfo.BossInfoWindow.ClearBossInfo(self)
		self.nui_publish()

	def BossInfoLoadComplete(self):
		uiBossInfo.BossInfoWindow.BossInfoLoadComplete(self)
		self.nui_publish()

	def nui_toggle(self):
		"""The board's arrow: the shown button's press, as legacy's."""
		button = self.expandButton if self.expandButton.IsShow() else self.minimizeButton
		button.click()

	# --- the board's model ----------------------------------------------------------------

	def _publish_toggle(self, button=None):
		if self.__dict__.get("_state") is None or self.expandButton is None or self.minimizeButton is None:
			return
		self.nui_set(collapsed=bool(self.expandButton.IsShow()))

	def nui_publish(self):
		if self.__dict__.get("_state") is None:
			return
		now = app.GetGlobalTimeStamp()
		start = nui.now()
		rows = []
		for row in self.rows:
			boss = row.boss
			level = boss.GetLevel()
			left = boss.GetTimeUntilSpawn() - now
			rows.append({
				"name": nui.plain_text(boss.GetBossName()),
				"level": nui.plain_text(localeInfo.BOSS_INFO_LEVEL % level) if level > 0 else "",
				"state": nui.plain_text(localeInfo.BOSS_INFO_ALIVE if boss.IsAlive() else localeInfo.BOSS_INFO_DEAD),
				"alive": bool(boss.IsAlive()),
				"respawn": left > 0,
				"respawn_end": float(start + left) if left > 0 else 0.0,
				"top": row.position[1],
			})
		count = len(rows)
		wide = bool(rows) and self.windowWidth == uiBossInfo.WIDE_WIDTH
		height = uiBossInfo.window_height(count)
		button_top = 16 if count == 1 else height // 2 - uiBossInfo.BUTTON_HEIGHT // 2
		self.nui_set(rows=rows, count=count, single=count == 1, wide=wide, height=height, button_top=button_top,
		             collapsed=bool(self.expandButton.IsShow()))
