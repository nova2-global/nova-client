"""NovaUI select item (nui/windows/select-item/select-item.rml; P14 spec 6.6).

While the select-item flag is on, Interface.__MakeItemSelectWindow makes
SelectItemWindow below through nui_windows.make() instead of
uiselectitem.SelectItemWindow: a subclass of the legacy class whose loader
puts proxies where the legacy widgets were (a nui_slots.SlotWindowProxy for
the stone grid, the board, title bar and close button), bound as legacy
binds them. Legacy's RefreshSlot runs on the proxy (the scan, the grade
rule, the cap and the rows), so the window shows legacy's stones in legacy's
cells. A quest's [SELECT_ITEM] opens it (BINARY_OpenSelectItemWindow); a
press on a stone sends its inventory position, the close button 0, as
legacy's. Legacy's wndMgr.OnceIgnoreMouseLeftButtonUpEvent() is not called:
NovaUI acts on the press and its release stays on NovaUI's side, so the call
would swallow the next legacy release (P14 spec 6.6). The board exists only
while the window shows (a list of the rows legacy computes, set once per
load)."""

import net
import ui
import uiselectitem
import wndMgr

import nui
import nui_hud
import nui_limits
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/select-item/select-item.rml"
KEY = "select-item"
# The legacy grid of the uiscript (selectitemwindow.py: 5 x 8 from 0) and its board.
COLUMNS, ROWS = 5, 8
BOARD_WIDTH, BOARD_HEIGHT = 184, 332


class _SelectItemBoard(nui.Window):
	"""Select item's document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "select_item"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("cell_press")
	def on_cell_press(self, index, button):
		self._owner._events.press(int(index), button)

	@nui.on("cell_over")
	def on_cell_over(self, index):
		self._owner._events.over(int(index))

	@nui.on("cell_out")
	def on_cell_out(self, index):
		self._owner._events.out(int(index))

	@nui.on("close_press")
	def on_close_press(self, button):
		if button == 0:
			self._owner.btnExit.click()


class SelectItemWindow(uiselectitem.SelectItemWindow):
	"""uiselectitem.SelectItemWindow on NovaUI (Interface.wndItemSelect)."""

	NUI_FACADE = True

	def __init__(self):
		nui_hud.take_over(KEY, self)
		self._nui_discarded = False
		self._limits = nui_limits.current()
		self._events = None
		self._state = {"cells": [nui_slots.empty_cell(i) for i in range(COLUMNS * 3)],
		               "cols": self._limits.SELECT_ITEM_COLUMNS}
		self.loaded = False
		self.demand = nui_hud.OnDemand(self._make_board, self._restore_board) if nui_hud.has_engine_3b() else None
		uiselectitem.SelectItemWindow.__init__(self)
		if self.demand is not None:
			self.loaded = self.demand.probe()

	def nui_ready(self):
		return self.loaded and self.demand is not None and nui_hud.has_engine_3b()

	def nui_discard(self):
		self._nui_discarded = True
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(KEY, self)

	def _make_board(self):
		return _SelectItemBoard(self, self._state)

	def _restore_board(self, board):
		board.set(**self._state)

	def _on_cells(self, cells):
		"""The cells after legacy's RefreshSlot. A shown board whose list
		would change length is made again, so a list never shrinks under its
		document (docs/ui/AUTHORING.md, the data binding cheatsheet)."""
		length = len(self._state["cells"])
		self._state["cells"] = cells
		board = self.demand.board() if self.demand is not None else None
		if board is None:
			return
		if len(cells) == length:
			board.set(cells=cells)
		else:
			self.demand.hide()
			self.demand.show()

	# --- the loader (uiselectitem.py:20-43, on proxies) -----------------------------

	def LoadWindow(self):
		self.board = nui_proxies.BoardProxy(BOARD_WIDTH, BOARD_HEIGHT)
		self.titleBar = nui_proxies.BoardProxy(169, 23)
		self.itemSlot = nui_slots.SlotWindowProxy(range(COLUMNS * ROWS), self._on_cells, cols=COLUMNS, rows=ROWS,
		                                          positions=self._position)
		self.btnExit = nui_proxies.ButtonProxy()

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))
		self.btnExit.SetEvent(ui.__mem_func__(self.Close))
		self.itemSlot.SetSlotStyle(wndMgr.SLOT_STYLE_NONE)
		self.itemSlot.SAFE_SetButtonEvent("LEFT", "EXIST", self.SelectItemSlot)
		self.itemSlot.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		self.itemSlot.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		self._events = nui_slots.LegacySlotEvents(self.itemSlot)

	def _position(self, slot):
		"""A cell's inventory position: legacy's inventorySlotPosDict."""
		return self.inventorySlotPosDict.get(slot, 0)

	# --- what NovaUI changes (P14 spec 6.6) ---------------------------------------------

	def Show(self):
		if self.demand is not None:
			self.demand.show()
		uiselectitem.SelectItemWindow.Show(self)

	def Hide(self):
		uiselectitem.SelectItemWindow.Hide(self)
		if self.demand is not None:
			self.demand.hide()

	def SetTop(self):
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.bring_to_front()
		uiselectitem.SelectItemWindow.SetTop(self)

	def Destroy(self):
		self.nui_discard()
		uiselectitem.SelectItemWindow.Destroy(self)

	def SetTableSize(self, size):
		"""Legacy's, on the proxies, without legacy's SetSize and UpdateRect of
		the window itself: the legacy window stays 0 x 0, never picked (the
		rows reach the board as the cells' count)."""
		self.itemSlot.ArrangeSlot(0, COLUMNS, size, 32, 32, 0, 0)
		self.itemSlot.RefreshSlot()
		self.itemSlot.SetSlotBaseImage("d:/ymir work/ui/public/Slot_Base.sub", 1.0, 1.0, 1.0, 1.0)
		self.board.SetSize(self.board.GetWidth(), 76 + 32 * size)

	def Close(self):
		# Legacy's, without wndMgr.OnceIgnoreMouseLeftButtonUpEvent().
		net.SendSelectItemPacket(0)
		self.Hide()

	def SelectItemSlot(self, slotPos):
		# Legacy's, without wndMgr.OnceIgnoreMouseLeftButtonUpEvent().
		inventorySlotPos = self.inventorySlotPosDict[slotPos]
		net.SendSelectItemPacket(inventorySlotPos)
		self.Hide()
