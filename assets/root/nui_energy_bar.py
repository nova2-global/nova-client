"""NovaUI energy bar (nui/windows/energy-bar/energy-bar.rml).

While the "energy-bar" window flag is on, Interface.__MakeTaskBar makes
EnergyBar below through nui_windows.make() instead of uiTaskBar.EnergyBar:
the facade of the legacy class, which the Interface shows, hides and
refreshes as before. The state (full, hungry, empty) and the hint follow
uiTaskBar.EnergyBar.RefreshStatus and SetEnergy; the legacy per-frame hover
check becomes the hint host's mouseover, which refreshes once: the state
can change between status refreshes only with the clock, which legacy also
shows only on a hover or a refresh."""

import weakref

import app
import player

import nui
import nui_hud

DOCUMENT = "nui/windows/energy-bar/energy-bar.rml"
ENERGY_DURATION = 7200   # an energy pill lasts 2 hours (SetEnergy's maxTime)
HUNGRY_PERCENT = 15


def _keep(owner):
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


def energy_state(left_time, max_time=ENERGY_DURATION):
	"""SetEnergy's choice of gauge: "empty" with no time left, "hungry" under
	15% of the duration, else "full"."""
	left_time = max(left_time, 0)
	max_time = max(max_time, 0)
	if left_time == 0:
		return "empty"
	if max_time and (left_time * 100) // max_time < HUNGRY_PERCENT:
		return "hungry"
	return "full"


class EnergyBarBoard(nui.Window):
	DOCUMENT = DOCUMENT
	MODEL = "energy_bar"

	def __init__(self, owner):
		self._owner = _keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"state": "empty", "tip": ""}

	@nui.on("energy_over")
	def on_energy_over(self):
		self._owner.RefreshStatus()


class EnergyBar(object):
	"""uiTaskBar.EnergyBar on NovaUI (the wndEnergyBar facade)."""

	NUI_FACADE = True

	def __init__(self):
		nui_hud.take_over("energy-bar", self)
		self._nui_discarded = False
		self.board = None
		if not nui_hud.has_engine():
			return
		try:
			self.board = EnergyBarBoard(self)
		except Exception:
			self.nui_discard()
			raise

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		board, self.board = self.board, None
		if board is not None:
			board.destroy()
		nui_hud.forget("energy-bar", self)

	def LoadWindow(self):
		"""The document loaded with the facade; nothing is left to do."""
		pass

	def Destroy(self):
		self.nui_discard()

	def Show(self):
		if self.board is not None:
			self.board.show()

	def Hide(self):
		if self.board is not None:
			self.board.hide()

	def IsShow(self):
		return self.board is not None and self.board.is_visible()

	## Gauge
	def RefreshStatus(self):
		pointEnergy = player.GetStatus(player.ENERGY)
		leftTimeEnergy = player.GetStatus(player.ENERGY_END_TIME) - app.GetGlobalTimeStamp()
		self.SetEnergy(pointEnergy, leftTimeEnergy, ENERGY_DURATION)

	def SetEnergy(self, point, leftTime, maxTime):
		if self.board is not None:
			self.board.set(state=energy_state(leftTime, maxTime), tip=nui_hud.locale_text("TOOLTIP_ENERGY", point))
