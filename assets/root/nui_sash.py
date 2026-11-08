"""NovaUI sash windows (nui/windows/sash/sash.rml; Wave 6, NOVA-20).

While the sash flag is on, Interface.__MakeSashWindow (interfacemodule.py:380)
makes CombineWindow and AbsorbWindow below through nui_windows.make() instead
of uiSash.CombineWindow and uiSash.AbsorbWindow: subclasses of the legacy
classes (nui_facade.Facade) whose LoadWindow is a replica of legacy's
(uisash.py:53-83 and :232-247) with proxies where the uiscript's widgets
were: the title bar, Accept and Cancel, the three slots (a SlotWindowProxy over slots 0 and 1, the materials, and slot 2,
sash.WINDOW_MAX_MATERIALS, the result), and for the combine window the price
line, the result label and the auto combine check box (a CheckBoxProxy whose
state is constInfo.SASH_AUTO_COMBINE). The binding lines are legacy's, line
for line (tools/nui_sash_test.py LoaderBindsAsLegacy compares them), so the
drops (sash.Add), the right-click from the bag (AddItem, slot 255), the
removals (sash.Remove), the server's refresh, the cell locks on the inventory
(SetCantMouseEventCell, SetCanMouseEventCell), the result tooltips
(SetSashResultItem, SetSashResultAbsItem), the refine request and the close
request are legacy's code.

Legacy sets its slots without RefreshSlot (CSlotWindow draws them at once),
so Open and Refresh push the proxy's cells after legacy's code. What legacy
did every frame happens without Python: the walk-away (legacy's OnUpdate,
uisash.py:148-154: 1000 units or more from the open position on either axis runs
OnClose once) is a nuigame.WatchLeaveRange watch, armed in Open and stopped in
Hide (so also at the server's Close, which hides the window). The watch fires
past its range (`>`), legacy at it (`>=`): the range is the largest 32-bit
float under sash.LIMIT_RANGE (below_as_float). The engine parses the range
as a double but keeps it as a float and compares float distances with it
(NuiGameModule.cpp WatchLeaveRange's static_cast<float>, NuiRangeWatch.cpp
TickLeaveRange), so |d| > that float is |d| >= LIMIT_RANGE. The double just
under LIMIT_RANGE (math.nextafter) would round back to LIMIT_RANGE there.

The two windows share one document (the `mode` key picks what differs). Both
exist for the whole phase, and each has its own board, made while it shows
(on demand); the board is instanced (nui.Window.INSTANCED: its model is
"sash_<n>"), so the two never share a model, even if the server opened both
at once. Each window has its own take-over and watch key, since both are made
under the one window id "sash"."""


import constInfo
import localeInfo
import nuigame
import sash
import ui
import uiSash
import uiScriptLocale

import nui
import nui_facade
import nui_form_proxies
import nui_hud
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/sash/sash.rml"
# Slots 0 and 1, the materials, and slot 2 (sash.WINDOW_MAX_MATERIALS), the
# result: the uiscripts' SashSlot.
CELLS = 3


# The walk-away watch's range (module docstring); shared with the aura window.
below_as_float = nui_facade.below_as_float


class _SashBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The sash document; its events go to its window. A press on it raises
	the window, as legacy's window manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "sash"
	INSTANCED = True

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("cell_press")
	def on_cell_press(self, index, button):
		self.raise_for(button)
		self._owner._cell_events.press(int(index), button)

	@nui.on("cell_release")
	def on_cell_release(self, index, button):
		self._owner._cell_events.release(int(index), button)

	@nui.on("cell_drop")
	def on_cell_drop(self, index):
		self._owner._cell_events.drop(int(index))

	@nui.on("cell_use")
	def on_cell_use(self, index):
		self._owner._cell_events.use(int(index))

	@nui.on("cell_over")
	def on_cell_over(self, index):
		self._owner._cell_events.over(int(index))

	@nui.on("cell_out")
	def on_cell_out(self, index):
		self._owner._cell_events.out(int(index))

	@nui.on("auto_press")
	def on_auto_press(self, button):
		self.raise_for(button)
		box = getattr(self._owner, "checkBox", None)
		if button == 0 and box is not None:
			box.click()

	@nui.on("accept_press")
	def on_accept_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.btnAccept.click()

	@nui.on("cancel_press")
	def on_cancel_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.btnCancel.click()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.titleBar.close()


class _NuiSashWindow(nui_facade.Facade):
	"""What the two NovaUI sash windows share (uisash.py _SashWindow): the
	model, the loader on proxies, the cells pushed after legacy's Open and
	Refresh, and the walk-away watch."""

	MODE = ""
	LEAVE_RANGE = True
	BOARD = _SashBoard
	# The uiscripts center the window on the screen.
	PLACE = "center"

	def __init__(self):
		self.nui_begin()
		try:
			super(_NuiSashWindow, self).__init__()
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			"mode": self.MODE,
			"cells": [nui_slots.empty_cell(i) for i in range(CELLS)],
			# The combine window's price line (legacy's SASH_REFINE_COST text).
			"price": "",
			# The combine window's check box: its state and whether it shows.
			"auto_combine": False,
			"auto_shown": False,
			# P15 F-2: nui_slots.ATTACH_RIGHT (the cells' nui-attach-right).
			"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
		}

	# --- the proxies' callbacks ---------------------------------------------------------

	def _on_cells(self, cells):
		events = getattr(self, "_cell_events", None)
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		self.nui_set(cells=nui_slots.with_states(cells, states, picked))

	def _on_states(self, states, picked):
		self.nui_set(cells=nui_slots.with_states(self.sashSlot.cells(), states, picked))

	# --- the loader (uisash.py:53-83 _SashWindow.LoadWindow, on proxies) ------------------

	def LoadWindow(self):
		"""Legacy's loader with proxies where its uiscript's children were;
		the binding lines are legacy's."""
		if self.isLoaded:
			return

		self.isLoaded = 1

		# The uiscript's style (sash_combinewindow.py, sash_absorbwindow.py:
		# "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		self.titleBar = nui_proxies.BoardProxy()
		self.btnAccept = nui_proxies.ButtonProxy()
		self.btnCancel = nui_proxies.ButtonProxy()
		self.sashSlot = nui_slots.SlotWindowProxy(range(CELLS), self._on_cells)
		self._BindChildren()

		self.sashSlot.SetSelectEmptySlotEvent(ui.__mem_func__(self.OnSelectEmptySlot))
		self.sashSlot.SetUnselectItemSlotEvent(ui.__mem_func__(self.OnSelectItemSlot))
		self.sashSlot.SetUseSlotEvent(ui.__mem_func__(self.OnSelectItemSlot))
		self.sashSlot.SetOverInItemEvent(ui.__mem_func__(self.OnOverInItem))
		self.sashSlot.SetOverOutItemEvent(ui.__mem_func__(self.OnOverOutItem))
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.OnClose))
		self.btnCancel.SetEvent(ui.__mem_func__(self.OnClose))
		self.btnAccept.SetEvent(ui.__mem_func__(self.OnAccept))

		self._cell_events = self.nui_events(nui_slots.LegacySlotEvents(self.sashSlot, on_states=self._on_states))

	# --- what NovaUI changes -----------------------------------------------------------

	def Open(self):
		"""Legacy's (uisash.py:123-129, the combine window's price first at
		:255-257: the start position, the cleared slots, the show), then its
		cells on the board and the walk-away watch (legacy's OnUpdate rule),
		whose callback is legacy's OnClose."""
		super(_NuiSashWindow, self).Open()
		self.sashSlot.push()
		nuigame.WatchLeaveRange(self.KEY, below_as_float(sash.LIMIT_RANGE), ui.__mem_func__(self.OnClose), False)

	def Refresh(self, iAct):
		"""Legacy's (uisash.py:190-212, the combine window's price first at
		:273-275: the slots after GC::SASH, the cell locks), then its cells on
		the board."""
		super(_NuiSashWindow, self).Refresh(iAct)
		self.sashSlot.push()

	def Hide(self):
		"""Facade's (legacy's, the slot events' reset, the board), then the
		watch stops: the player's close leaves the window open until the
		server closes it (Close, which hides it), as legacy's."""
		nui_facade.Facade.Hide(self)
		if not self.IsShow():
			nuigame.StopLeaveRange(self.KEY)


class CombineWindow(_NuiSashWindow, uiSash.CombineWindow):
	"""uiSash.CombineWindow on NovaUI (Interface.wndSashCombine)."""

	KEY = "sash-combine"
	MODE = "combine"

	def _on_price(self, text):
		self.nui_set(price=nui.plain_text(text))

	def _on_check(self, box):
		self.nui_set(auto_combine=bool(box.checked), auto_shown=bool(box.shown))

	def _BindChildren(self):
		"""Legacy's (uisash.py:228-230) on proxies: the
		price line and the result slot's label (legacy never changes it; the
		document shows the uiscript's text, @ui.SASH_RESULT)."""
		self.needMoney = nui_proxies.TextProxy(self._on_price)
		self.Result = nui_proxies.TextProxy(text=getattr(uiScriptLocale, "SASH_RESULT", ""))

	def LoadWindow(self):
		"""Legacy's (uisash.py:232-247) with a CheckBoxProxy
		where its ui.CheckBox was; the document shows its label
		(@game.SASH_AUTO_COMBINE, legacy's localeInfo text) under the price."""
		if self.isLoaded:
			return
		_NuiSashWindow.LoadWindow(self)

		self.checkBox = nui_form_proxies.CheckBoxProxy(self._on_check)
		self.checkBox.SetParent(self)
		self.checkBox.SetEvent(ui.__mem_func__(self._OnAutoCombineCheck), "ON_CHECK")
		self.checkBox.SetEvent(ui.__mem_func__(self._OnAutoCombineUncheck), "ON_UNCHECK")
		self.checkBox.SetCheckStatus(constInfo.SASH_AUTO_COMBINE)
		self.checkBox.SetTextInfo(localeInfo.SASH_AUTO_COMBINE)
		self.checkBox.SetPosition(0, self.AUTO_COMBINE_Y)
		self.checkBox.SetWindowHorizontalAlignCenter()
		self.checkBox.Show()


class AbsorbWindow(_NuiSashWindow, uiSash.AbsorbWindow):
	"""uiSash.AbsorbWindow on NovaUI (Interface.wndSashAbsorption): the
	Interface loads it after making it, as legacy's."""

	KEY = "sash-absorb"
	MODE = "absorb"
