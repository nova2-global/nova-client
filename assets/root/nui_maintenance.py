"""NovaUI maintenance countdown (nui/windows/maintenance/maintenance.rml;
P18, NOVA-58).

While the maintenance flag is on (the hud group), game.py makes
MaintenanceWindow below through nui_windows.make() instead of
uiMaintenance.MaintenanceWindow: a facade with the legacy class's name, its
constants and the methods game.py and the window manager call (Open, Close,
Show, Hide, IsShow, SetTop, Destroy). game.py opens it with the seconds left
that the server's shutdown_schedule sends (OpenShutdownCountdown) and closes
it on shutdown_cancel (CloseShutdownCountdown) and at the phase's end.

Legacy's window redraws its time from its OnUpdate, every frame, and hides
itself when the time is up. Here the time is a nui-countdown: Open writes
its end once (nui.now() plus the seconds left), and the element shows the
seconds left as legacy counts them (round="up": legacy's
ceil(round(left, 3))), in legacy's format (format="dhms",
localeInfo.RTSecondToDHMS), keeps its widest width while it counts
(hold-width, legacy's __FitWidth), and sends countdownend at the end, where
the facade hides, as legacy's __Refresh does. No Python runs while it
counts. An exe whose countdown has no round="up" counts down whole seconds
instead, one second sooner, and shows no time in the last second.

The board exists only while the countdown shows (nui_hud.OnDemand). It
draws above the legacy UI layer, where legacy's window lived, so that the
NovaUI HUD windows at the top left (the affects, below that layer) never
cover it (the migration inventory's layering note on NOVA-58); each Open
brings it above the other NovaUI windows, as legacy's SetTop. A press on
the board raises it; its close button closes it, which the next schedule
opens again, as legacy's."""

import math

import app

import nui
import nui_hud

DOCUMENT = "nui/windows/maintenance/maintenance.rml"
KEY = "maintenance"


def seconds_left(left):
	"""The whole seconds legacy's window shows for `left` seconds
	(uimaintenance.py __Refresh): rounded to the millisecond, then up, so the
	clock's float noise never shows a second more than the server sent."""
	return int(math.ceil(round(left, 3)))


class _MaintenanceBoard(nui.Window):
	"""The countdown's document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "maintenance"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("ended")
	def on_ended(self):
		self._owner.nui_ended()

	@nui.on("board_press")
	def on_board_press(self, button):
		# Legacy's window is "float": a left or right press raises it.
		if button in (0, 1):
			self._owner.SetTop()

	@nui.on("close_press")
	def on_close_press(self, button):
		if button == 0:
			self._owner.Close()


class MaintenanceWindow(object):
	"""uiMaintenance.MaintenanceWindow on NovaUI (game.py wndMaintenance)."""

	NUI_FACADE = True
	# Legacy's constants (uimaintenance.py), which the sheets follow in dp.
	POSITION = (10, 70)
	HEIGHT = 36
	PADDING = 12
	GAP = 4

	OnUpdate = None
	OnRender = None

	def __init__(self):
		nui_hud.take_over(KEY, self)
		self._nui_discarded = False
		self.endTime = 0.0
		self.shown = False
		self._state = {"end": 0.0}
		self.demand = None
		self.loaded = False
		if nui_hud.has_engine():
			self.demand = nui_hud.OnDemand(self._make_board, self._restore_board)
			self.loaded = self.demand.probe()

	# --- make()'s protocol -----------------------------------------------------------------

	def nui_ready(self):
		return bool(self.loaded) and self.demand is not None and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		self.shown = False
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(KEY, self)

	# --- the board -----------------------------------------------------------------------

	def _make_board(self):
		return _MaintenanceBoard(self, self._state)

	def _restore_board(self, board):
		board.set(**self._state)

	def _board(self):
		return self.demand.board() if self.demand is not None else None

	# --- legacy's methods ----------------------------------------------------------------

	def Open(self, secondsLeft):
		"""Legacy's Open: the end on the clock, then shown and raised while
		some time is left; with none, hidden, as legacy's __Refresh hides it.
		A schedule brought forward moves the end of a shown countdown, whose
		width then starts again from its new text, as legacy's."""
		self.endTime = app.GetTime() + secondsLeft
		if seconds_left(secondsLeft) <= 0:
			self.Hide()
			return
		self._state["end"] = nui.now() + secondsLeft
		board = self._board()
		if board is not None:
			board.set(end=self._state["end"])
		self.Show()
		self.SetTop()

	def Close(self):
		self.Hide()

	def Show(self):
		self.shown = True
		if self.demand is not None:
			self.demand.show()

	def Hide(self):
		self.shown = False
		if self.demand is not None:
			self.demand.hide()

	def IsShow(self):
		return bool(self.shown)

	def SetTop(self):
		"""Above the other NovaUI windows, as legacy's SetTop raises it in
		its layer."""
		board = self._board()
		if board is not None:
			board.bring_to_front()

	def Destroy(self):
		self.Hide()
		self.nui_discard()

	def nui_ended(self):
		"""countdownend: the time is up, and legacy's window hides itself."""
		if self.shown:
			self.Hide()
