"""NovaUI belt inventory (nui/windows/belt-inventory/belt-inventory.rml;
P14 spec 6.3).

The NovaUI inventory (nui_inventory) makes BeltInventoryWindow below where
the legacy inventory makes uiInventory.BeltInventoryWindow: a subclass of it
whose uiscript loader puts proxies where the legacy widgets were (a
nui_slots.SlotWindowProxy over the belt's BELT_INVENTORY_SLOT_COUNT cells,
the layer and the expand and minimize buttons), bound to the inventory's
handlers as legacy binds them. Legacy's RefreshSlot runs on the proxy: the
cells beyond the belt's grade are the cover buttons it disables, which the
board shows unavailable. The board exists only while the belt shows and is
docked to the inventory (G6): its right edge on the inventory's left edge,
its top at the inventory's inv-belt-dock (legacy's x - 148, y + 241), also
while collapsed (legacy's x - 10), so the inventory's drags move it."""

import item
import ui
import uiInventory

import nui
import nui_hud
import nui_limits
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/belt-inventory/belt-inventory.rml"
KEY = "belt-inventory"
# The legacy cover button art (uiinventory.py:203-206).
COVER_ART = ("d:/ymir work/ui/game/quest/slot_button_01.sub", "d:/ymir work/ui/game/quest/slot_button_01.sub",
             "d:/ymir work/ui/game/quest/slot_button_01.sub", "d:/ymir work/ui/game/belt_inventory/slot_disabled.tga")
# The legacy window's width (uiscript beltinventorywindow.py), ORIGINAL_WIDTH.
WIDTH = 148
HEIGHT = 139


class _BeltBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The belt's document; its events go to its window. A press on it raises
	the window, as legacy's window manager does (legacy's constructor makes
	the belt window float)."""

	DOCUMENT = DOCUMENT
	MODEL = "belt"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("belt_press")
	def on_press(self, index, button):
		self.raise_for(button)
		self._owner._events.press(int(index), button)

	@nui.on("belt_release")
	def on_release(self, index, button):
		self._owner._events.release(int(index), button)

	@nui.on("belt_use")
	def on_use(self, index):
		self._owner._events.use(int(index))

	@nui.on("belt_over")
	def on_over(self, index):
		self._owner._events.over(int(index))

	@nui.on("belt_out")
	def on_out(self, index):
		self._owner._events.out(int(index))

	@nui.on("belt_drop")
	def on_drop(self, index):
		self._owner._events.drop(int(index))

	@nui.on("expand_press")
	def on_expand_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.expandBtn.click()

	@nui.on("minimize_press")
	def on_minimize_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.minBtn.click()


class BeltInventoryWindow(uiInventory.BeltInventoryWindow):
	"""uiInventory.BeltInventoryWindow on NovaUI (the NovaUI inventory's wndBelt)."""

	NUI_FACADE = True

	def __init__(self, wndInventory):
		nui_hud.take_over(KEY, self)
		self._nui_discarded = False
		self._limits = nui_limits.current()
		limits = self._limits
		self._cols = limits.BELT_COLUMNS
		self._rows = limits.BELT_INVENTORY_SLOT_COUNT // max(1, self._cols)
		self._events = None
		self._state = {
			"cells": [nui_slots.empty_cell(i) for i in range(self._cols * self._rows)],
			"cols": self._cols,
			"expanded": False,
			# P14b: the grid's is-attaching (nui_slots.LegacySlotEvents).
			"attaching": False,
			# P15 F-2 (nui_slots.ATTACH_RIGHT; the grid's nui-attach-right).
			"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
			# V-2: the grid, none while the board is kept hidden.
			"cells_on": [1],
		}
		# V-2 (P15 spec 8.1): kept, hidden, after its first open.
		self.demand = (nui_hud.KeptBoard(self._make_board, self._restore_board, empty=self._empty_board)
		               if nui_hud.has_engine_3b() else None)
		uiInventory.BeltInventoryWindow.__init__(self, wndInventory)

	def nui_ready(self):
		return self.demand is not None and nui_hud.has_engine_3b()

	def nui_discard(self):
		self._nui_discarded = True
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(KEY, self)

	def _set(self, **values):
		self._state.update(values)
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.set(**values)

	def _make_board(self):
		return _BeltBoard(self, self._state)

	def _empty_board(self, board):
		"""V-2: the hidden kept board holds no cell."""
		board.set(cells_on=[])

	def _restore_board(self, board):
		board.set(**self._state)

	def _on_cells(self, cells):
		events = self._events
		self._set(cells=nui_slots.with_states(cells, events.states if events is not None else {},
		                                      events.picked if events is not None else -1))

	def _on_states(self, states, picked):
		self._set(cells=nui_slots.with_states(self.wndBeltInventorySlot.cells(), states, picked))

	def _dock(self):
		"""The belt beside the inventory: its right edge on the inventory's
		left edge, its top at inv-belt-dock; a width change (collapse) keeps
		the right edge (the runtime places it again)."""
		board = self.demand.board() if self.demand is not None else None
		other = self.wndInventory.board() if hasattr(self.wndInventory, "board") else None
		if board is not None and other is not None:
			board.place_next_to(other, "left", 0, "inv-belt-dock")

	# --- the loader (uiinventory.py:173-220, on proxies) ------------------------------

	def _BeltInventoryWindow__LoadWindow(self):
		if self.isLoaded == 1:
			return
		self.isLoaded = 1
		start = self._limits.BELT_INVENTORY_SLOT_START
		count = self._limits.BELT_INVENTORY_SLOT_COUNT
		self.ORIGINAL_WIDTH = WIDTH
		wndBeltInventorySlot = nui_slots.SlotWindowProxy(range(start, start + count), self._on_cells,
		                                                 cols=self._cols, rows=self._rows)
		self.wndBeltInventoryLayer = nui_proxies.BoardProxy(WIDTH, HEIGHT)
		self.expandBtn = nui_proxies.ButtonProxy()
		self.minBtn = nui_proxies.ButtonProxy()

		self.expandBtn.SetEvent(ui.__mem_func__(self.OpenInventory))
		self.minBtn.SetEvent(ui.__mem_func__(self.CloseInventory))

		for i in range(item.BELT_INVENTORY_SLOT_COUNT):
			slotNumber = item.BELT_INVENTORY_SLOT_START + i
			wndBeltInventorySlot.SetCoverButton(slotNumber, COVER_ART[0], COVER_ART[1], COVER_ART[2], COVER_ART[3],
			                                    False, False)

		## Equipment
		wndBeltInventorySlot.SetOverInItemEvent(ui.__mem_func__(self.wndInventory.OverInItem))
		wndBeltInventorySlot.SetOverOutItemEvent(ui.__mem_func__(self.wndInventory.OverOutItem))
		wndBeltInventorySlot.SetUnselectItemSlotEvent(ui.__mem_func__(self.wndInventory.UseItemSlot))
		wndBeltInventorySlot.SetUseSlotEvent(ui.__mem_func__(self.wndInventory.UseItemSlot))
		wndBeltInventorySlot.SetSelectEmptySlotEvent(ui.__mem_func__(self.wndInventory.SelectEmptySlot))
		wndBeltInventorySlot.SetSelectItemSlotEvent(ui.__mem_func__(self.wndInventory.SelectItemSlot))

		self.wndBeltInventorySlot = wndBeltInventorySlot
		self._events = nui_slots.LegacySlotEvents(wndBeltInventorySlot, on_states=self._on_states,
		                                          on_attaching=lambda flag: self._set(attaching=flag))

	# --- what NovaUI changes (P14 spec 6.3) --------------------------------------------

	def Show(self, openBeltSlot=False):
		if self.demand is not None:
			self.demand.show()
		uiInventory.BeltInventoryWindow.Show(self, openBeltSlot)

	def Hide(self):
		uiInventory.BeltInventoryWindow.Hide(self)
		if self._events is not None:
			self._events.reset()
		if self.demand is not None:
			self.demand.hide()

	def SetTop(self):
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.bring_to_front()
		uiInventory.BeltInventoryWindow.SetTop(self)

	def Destroy(self):
		self.nui_discard()
		uiInventory.BeltInventoryWindow.Destroy(self)

	def OpenInventory(self):
		self.wndBeltInventoryLayer.Show()
		self.expandBtn.Hide()
		self._set(expanded=True)
		self._dock()

	def CloseInventory(self):
		self.wndBeltInventoryLayer.Hide()
		self.expandBtn.Show()
		self._set(expanded=False)
		self._dock()

	def GetBasePosition(self):
		"""The docking replaces legacy's base position: the inventory's box."""
		other = self.wndInventory.board() if hasattr(self.wndInventory, "board") else None
		box = other.element_box("inv-belt-dock") if other is not None else None
		return (int(box[0]), int(box[1])) if box else (0, 0)

	def AdjustPositionAndSize(self):
		self._dock()
