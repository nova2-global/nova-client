"""NovaUI damage count window (nui/windows/damage-count/damage-count.rml;
NOVA-27).

While the damage-count flag is on (the hud group), Interface.__MakeBossWindows
makes DamageCountWindow below through nui_windows.make() instead of
uiDamageCount.DamageCountWindow: a subclass of the legacy class
(nui_facade.Facade) whose uiscript loader (LoadWindow) puts proxies where
the widgets were (the board, the boss's name, the HP gauge and its two
texts, the exit button, the list) and whose row maker (MakeRow) makes a row
proxy that runs legacy's own Row.SetData. So the ranking (the top 10 by
damage, attackers out of view left out, the share and the bar against the
leader, the own row's frame, the new victim's empty list), the HP colors
and the Open, Close and target board rules are legacy's code; the board
shows what the proxies were told.

No Python runs per frame (OnUpdate = None): legacy's Row.OnUpdate turns the
updated row's damage from grey to white after 0.1 s; here each update of a
row flips its `flash` key between 1 and 2, whose two classes run the same
0.1 s keyframes (a changed animation starts again), and reduced motion shows
it white at once. The legacy window stays 0 x 0: its SetSize, GetWidth and
GetHeight keep the sizes legacy computes, which the sheet does not need
(the list grows with its rows); Open's place is the board's (legacy's
pixels in dp)."""

import ui
import uiDamageCount

import nui
import nui_facade
import nui_form_proxies
import nui_hud
import nui_proxies

DOCUMENT = "nui/windows/damage-count/damage-count.rml"
KEY = "damage-count"


def hp_tone(color):
	"""The HP percentage's legacy color as the sheets' tone."""
	if color == uiDamageCount.hp_color(100):
		return "high"
	if color == uiDamageCount.hp_color(50):
		return "mid"
	return "low"


class _DamageBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The window's document; its events go to its window. A press raises
	the window, as legacy's window manager does a "float" window."""

	DOCUMENT = DOCUMENT
	MODEL = "damage_count"

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
			self._owner.exitButton.click()


class _LineProxy(nui_proxies._Shown):
	"""One side of the own row's frame (a ui.Bar)."""

	shown = False


class _RowProxy(nui_proxies._Shown):
	"""uiDamageCount.DamageCountWindow.Row: legacy's SetData and OnUpdate run
	on text, image and line proxies; the bar's width is its SetSize."""

	SetData = uiDamageCount.DamageCountWindow.Row.SetData
	OnUpdate = uiDamageCount.DamageCountWindow.Row.OnUpdate

	def __init__(self, index):
		self.x = index
		self.Color = uiDamageCount.COLOR_LIST[index]
		self.LastTimeUpdated = 0.0
		self.size = (300, 60)
		self.shown = True
		self.flash = 0
		self.noNumber = nui_proxies.TextProxy()
		self.raceImg = nui_proxies.ImageProxy()
		self.NameLabel = nui_proxies.TextProxy()
		self.DamageLabel = nui_proxies.TextProxy(on_text=self._on_damage)
		self.leftLine = _LineProxy()
		self.rightLine = _LineProxy()
		self.topLine = _LineProxy()
		self.bottomLine = _LineProxy()

	def _on_damage(self, text):
		self._flashed = False

	def SetSize(self, width, height):
		self.size = (int(width), int(height))

	def GetWidth(self):
		return self.size[0]

	def GetHeight(self):
		return self.size[1]

	def model(self):
		updated = self.DamageLabel.color == uiDamageCount.UPDATE_COLOR
		if updated and not getattr(self, "_flashed", False):
			self.flash = 2 if self.flash == 1 else 1
			self._flashed = True
		return {
			"no": nui.plain_text(self.noNumber.GetText()),
			"name": nui.plain_text(self.NameLabel.GetText()),
			"damage": nui.plain_text(self.DamageLabel.GetText()),
			"face": self.raceImg.image if self.raceImg.IsShow() else "",
			"own": bool(self.topLine.IsShow()),
			"width": self.size[0],
			"color": self.x % 8,
			"flash": self.flash if updated else 0,
		}


class _ListProxy(nui_proxies._Shown):
	"""ui.ListBoxEx as the window uses it: the rows appended in order."""

	def __init__(self):
		self.items = []
		self.size = (392, 225)

	def AppendItem(self, item):
		self.items.append(item)

	def GetItem(self, index):
		return self.items[index]

	def RemoveAllItems(self):
		self.items = []

	def SetSize(self, width, height):
		self.size = (int(width), int(height))

	def GetWidth(self):
		return self.size[0]

	def GetHeight(self):
		return self.size[1]


class DamageCountWindow(nui_facade.Facade, uiDamageCount.DamageCountWindow):
	"""uiDamageCount.DamageCountWindow on NovaUI (Interface.wndDamageCount)."""

	KEY = KEY
	BOARD = _DamageBoard
	OnUpdate = None

	def __init__(self):
		self.nui_begin()
		try:
			uiDamageCount.DamageCountWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			"target": "",
			"hp_text": "",
			"hp_percent": "",
			"hp_tone": "high",
			"hp_value": 0.0,
			"rows": [],
			"count": 0,
		}

	# --- the loader (uidamagecount.py LoadWindow, on proxies) --------------------------

	def LoadWindow(self):
		# The uiscript's style (damagecount.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		self.nui_size = (392, 300)  # the uiscript's window
		self.board = nui_proxies.BoardProxy(392, 300)
		self.targetName = nui_proxies.TextProxy()
		self.wndList = _ListProxy()
		self.hpValues = nui_proxies.TextProxy()
		self.hpPercenttxt = nui_proxies.TextProxy()
		self.hpGauge = nui_form_proxies.GaugeProxy()
		self.exitButton = nui_proxies.ButtonProxy()
		self.exitButton.SetEvent(ui.__mem_func__(self.Close))

		self.CreateRowPool()
		self.Reset()

	def MakeRow(self, index):
		return _RowProxy(index)

	# --- the legacy window stays 0 x 0 ----------------------------------------------------

	def SetSize(self, width, height):
		self.nui_size = (int(width), int(height))

	def GetWidth(self):
		return getattr(self, "nui_size", (0, 0))[0]

	def GetHeight(self):
		return getattr(self, "nui_size", (0, 0))[1]

	# --- legacy's entry points, then the board -----------------------------------------

	def AddData(self, attackerVID, victimVID, damage):
		uiDamageCount.DamageCountWindow.AddData(self, attackerVID, victimVID, damage)
		self.nui_publish()

	def AddHPInfo(self, vid, hpPercentage, HP=0, MaxHP=0):
		uiDamageCount.DamageCountWindow.AddHPInfo(self, vid, hpPercentage, HP, MaxHP)
		self.nui_set(hp_text=nui.plain_text(self.hpValues.GetText()),
		             hp_percent=nui.plain_text(self.hpPercenttxt.GetText()),
		             hp_tone=hp_tone(self.hpPercenttxt.color),
		             hp_value=float(self.hpGauge.percent))

	def Close(self):
		uiDamageCount.DamageCountWindow.Close(self)
		self.nui_publish()

	def nui_publish(self):
		if self.__dict__.get("_state") is None:
			return
		rows = [row.model() for row in self.activeRows if row.IsShow()]
		self.nui_set(target=nui.plain_text(self.targetName.GetText()), rows=rows, count=len(rows))
