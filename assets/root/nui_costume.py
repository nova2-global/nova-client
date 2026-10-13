"""NovaUI costume window (nui/windows/costume/costume.rml; P14 spec 6.2).

The NovaUI inventory (nui_inventory) makes CostumeWindow below where the
legacy inventory makes uiInventory.CostumeWindow: a subclass of it whose
uiscript loader puts a nui_slots.SlotWindowProxy over the costume group of
the wear table (nui_limits) where the legacy slot window was, with the
inventory's handlers (OverInItem, OverOutItem, UseItemSlot, SelectEmptySlot,
SelectItemSlot) as legacy binds them, so equipping, unequipping and every
drag is the inventory's legacy code. Legacy refreshes COSTUME_SLOT_COUNT
cells; the cells of the group it never refreshes (today's ring1, P14 spec
2.1) are filled from the inventory at each refresh, a difference nobody can
see today. The board exists only while the window shows; at each open it is
placed beside the inventory's left edge, top in line (legacy's
SCREEN_WIDTH - 175 - 140), and it moves alone after."""

import player
import ui
import uiInventory

import nui
import nui_hud
import nui_limits
import nui_slots

DOCUMENT = "nui/windows/costume/costume.rml"
KEY = "costume"


class _CostumeBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The costume window's document; its events go to its window. A press
	on it raises the window, as legacy's window manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "costume"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("cos_press")
	def on_press(self, index, button):
		self.raise_for(button)
		self._owner._events.press(int(index), button)

	@nui.on("cos_release")
	def on_release(self, index, button):
		self._owner._events.release(int(index), button)

	@nui.on("cos_use")
	def on_use(self, index):
		self._owner._events.use(int(index))

	@nui.on("cos_over")
	def on_over(self, index):
		self._owner._events.over(int(index))

	@nui.on("cos_out")
	def on_out(self, index):
		self._owner._events.out(int(index))

	@nui.on("cos_drop")
	def on_drop(self, index):
		self._owner._events.drop(int(index))

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.Close()


class CostumeWindow(uiInventory.CostumeWindow):
	"""uiInventory.CostumeWindow on NovaUI (the NovaUI inventory's wndCostume)."""

	NUI_FACADE = True

	def __init__(self, wndInventory):
		nui_hud.take_over(KEY, self)
		self._nui_discarded = False
		self._limits = nui_limits.current()
		self._slots = nui_limits.wear_group("costume", self._limits)
		self._events = None
		self._state = {
			"table": self._limits.WEAR_TABLE_ID,
			"slots": [dict(nui_slots.empty_cell(i), name=slot.name) for i, slot in enumerate(self._slots)],
			"has_companion": any(slot.name.startswith("buffi_") for slot in self._slots),
		}
		self.demand = nui_hud.OnDemand(self._make_board, self._restore_board) if nui_hud.has_engine_3b() else None
		uiInventory.CostumeWindow.__init__(self, wndInventory)

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
		return _CostumeBoard(self, self._state)

	def _restore_board(self, board):
		board.set(**self._state)

	def _named(self, cells, states=None):
		marked = nui_slots.with_states(cells, states or {})
		for cell, slot in zip(marked, self._slots):
			cell["name"] = slot.name
		return marked

	def _on_slots(self, cells):
		self._set(slots=self._named(cells, self._events.states if self._events is not None else {}))

	def _on_states(self, states, picked):
		self._set(slots=self._named(self.wndEquip.cells(), states))

	def _place_beside(self):
		"""Beside the inventory's left edge, top in line, as legacy creates its
		window (a pixel over the edge: SCREEN_WIDTH - 175 - 140 against the
		inventory's SCREEN_WIDTH - 176). When both open together (the
		inventory's Show reopens it), the inventory's new board has no layout
		yet and an empty box, so its origin is the place it opens at; docked
		instead when neither is known."""
		board = self.demand.board() if self.demand is not None else None
		other = self.wndInventory.board() if hasattr(self.wndInventory, "board") else None
		if board is None or other is None:
			return
		origin = getattr(self.wndInventory, "board_origin", None)
		origin = origin() if origin is not None else None
		if origin is not None:
			board.set_position(origin[0] + 1.0, origin[1], origin=(1.0, 0.0))
		else:
			board.place_next_to(other, "left", 0)

	# --- the loader (uiinventory.py:56-85, on a proxy) --------------------------------

	def _CostumeWindow__LoadWindow(self):
		if self.isLoaded == 1:
			return
		self.isLoaded = 1
		# The uiscript's style (costumewindow.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		wndEquip = nui_slots.SlotWindowProxy([slot.cell for slot in self._slots], self._on_slots)

		## Equipment
		wndEquip.SetOverInItemEvent(ui.__mem_func__(self.wndInventory.OverInItem))
		wndEquip.SetOverOutItemEvent(ui.__mem_func__(self.wndInventory.OverOutItem))
		wndEquip.SetUnselectItemSlotEvent(ui.__mem_func__(self.wndInventory.UseItemSlot))
		wndEquip.SetUseSlotEvent(ui.__mem_func__(self.wndInventory.UseItemSlot))
		wndEquip.SetSelectEmptySlotEvent(ui.__mem_func__(self.wndInventory.SelectEmptySlot))
		wndEquip.SetSelectItemSlotEvent(ui.__mem_func__(self.wndInventory.SelectItemSlot))

		self.wndEquip = wndEquip
		self._events = nui_slots.LegacySlotEvents(wndEquip, on_states=self._on_states)

	def RefreshCostumeSlot(self):
		"""Legacy's refresh, after the group's cells it never refreshes are
		filled from the inventory (P14 spec 6.2)."""
		refreshed = range(self._limits.COSTUME_SLOT_START, self._limits.COSTUME_SLOT_START + self._limits.COSTUME_SLOT_COUNT)
		for slot in self._slots:
			if slot.cell not in refreshed:
				self.wndEquip.SetItemSlot(slot.cell, player.GetItemIndex(slot.cell), 0)
		uiInventory.CostumeWindow.RefreshCostumeSlot(self)

	def Show(self):
		if self.demand is not None:
			self.demand.show()
		uiInventory.CostumeWindow.Show(self)
		self._place_beside()

	def Hide(self):
		uiInventory.CostumeWindow.Hide(self)
		if self._events is not None:
			self._events.reset()
		if self.demand is not None:
			self.demand.hide()

	def SetTop(self):
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.bring_to_front()
		uiInventory.CostumeWindow.SetTop(self)

	def Destroy(self):
		self.nui_discard()
		uiInventory.CostumeWindow.Destroy(self)
