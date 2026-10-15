"""NovaUI item mall storage (nui/windows/mall/mall.rml; P16 spec 5.5).

While the mall flag is on, Interface.__MakeDialogs makes MallWindow below
through nui_windows.make() instead of uiSafebox.MallWindow: a subclass of the
legacy class (nui_facade.Facade) whose uiscript loader puts proxies where
the widgets were: one 5 x 9 grid (TypedSlotWindowProxy, the mall's slot
type), the title bar and the exit button. So taking an item (the attach;
the inventory's drop sends the check-out), the refusal of any drop on the
mall (MALL_CANNOT_INSERT), the close command and the server's refreshes are
legacy's code, legacy's rules included: one page of 45 cells shows the
first 45 of the mall's cells and the mall has no page buttons (D16). The
password dialog is the safebox's (nui_safebox.PasswordDialog). Legacy's
per-frame distance rule is nuigame.WatchLeaveRange's watch, armed in
ShowWindow and stopped in Hide; it sends the close command once. The board
exists only while the window shows; it draws below the legacy UI layer, as
legacy's window lived in it."""

import nuigame
import player
import ui
import uiSafebox

import nui
import nui_facade
import nui_form_proxies
import nui_hud
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/mall/mall.rml"
KEY = "mall"
# Legacy's USE_SAFEBOX_LIMIT_RANGE (uisafebox.py:678).
LEAVE_RANGE = 1000
# The uiscript's place (mallwindow.py: 100, 20), in dp.
PLACE_LEFT, PLACE_TOP = 100, 20


class _MallBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The mall's document; its events go to its window. A press on it raises
	the window, as legacy's window manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "mall"

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

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.exitButton.click()


class MallWindow(nui_facade.Facade, uiSafebox.MallWindow):
	"""uiSafebox.MallWindow on NovaUI (Interface.wndMall)."""

	KEY = KEY
	BOARD = _MallBoard

	def __init__(self):
		self.nui_begin()
		try:
			uiSafebox.MallWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def PLACE(self):
		"""Legacy's place, (100, 20) in dp."""
		return (PLACE_LEFT, PLACE_TOP)

	def nui_model(self):
		limits = self._limits
		return {
			"cells": [nui_slots.empty_cell(i) for i in range(limits.SAFEBOX_PAGE_SIZE)],
			"cols": limits.SAFEBOX_COLUMNS,
			# P14b: the grid's is-attaching (nui_slots.LegacySlotEvents).
			"attaching": False,
		}

	# --- the proxies' callbacks ---------------------------------------------------------

	def _on_cells(self, cells):
		events = getattr(self, "_cell_events", None)
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		self.nui_set(cells=nui_slots.with_states(cells, states, picked))

	def _on_states(self, states, picked):
		self.nui_set(cells=nui_slots.with_states(self.wndItem.cells(), states, picked))

	def _on_attaching(self, flag):
		self.nui_set(attaching=flag)

	# --- the loader (uisafebox.py:553-584, on proxies) -------------------------------------

	def _MallWindow__LoadWindow(self):
		if self.isLoaded == 1:
			return

		self.isLoaded = 1

		# The uiscript's style (mallwindow.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		limits = self._limits

		## Item
		wndItem = nui_form_proxies.TypedSlotWindowProxy(
			range(limits.SAFEBOX_PAGE_SIZE), self._on_cells, cols=limits.SAFEBOX_COLUMNS, rows=limits.SAFEBOX_PAGE_ROWS,
			slot_type=player.SLOT_TYPE_MALL)
		wndItem.SetSelectEmptySlotEvent(ui.__mem_func__(self.SelectEmptySlot))
		wndItem.SetSelectItemSlotEvent(ui.__mem_func__(self.SelectItemSlot))
		wndItem.SetUnselectItemSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndItem.SetUseSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndItem.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		wndItem.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		wndItem.Show()

		## Close Button
		self.titleBar = nui_proxies.BoardProxy(161, 23)
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))
		self.exitButton = nui_proxies.ButtonProxy()
		self.exitButton.SetEvent(ui.__mem_func__(self.Close))

		self.wndItem = wndItem
		self.wndBoard = nui_proxies.BoardProxy(self.BOX_WIDTH, 327)

		self._cell_events = self.nui_events(nui_slots.LegacySlotEvents(
			wndItem, on_states=self._on_states, on_attaching=self._on_attaching))

		## Initialize
		self.SetTableSize(3)

	# --- what NovaUI changes (P16 spec 5.5.3) -----------------------------------------

	def SetTableSize(self, size):
		"""Legacy's one 5 x 9 page, with no window size: the board lays itself
		out, the legacy window stays 0 x 0."""
		limits = self._limits
		rows = limits.SAFEBOX_PAGE_ROWS

		self.wndItem.ArrangeSlot(0, limits.SAFEBOX_COLUMNS, rows, 32, 32, 0, 0)
		self.wndItem.RefreshSlot()
		self.wndItem.SetSlotBaseImage("d:/ymir work/ui/public/Slot_Base.sub", 1.0, 1.0, 1.0, 1.0)

		self.wndBoard.SetSize(self.BOX_WIDTH, 82 + 32 * rows)

	def ShowWindow(self, size):
		uiSafebox.MallWindow.ShowWindow(self, size)
		nuigame.WatchLeaveRange(KEY, LEAVE_RANGE, ui.__mem_func__(self.Close), False)

	def Hide(self):
		nui_facade.Facade.Hide(self)
		if not self.IsShow():
			nuigame.StopLeaveRange(KEY)
