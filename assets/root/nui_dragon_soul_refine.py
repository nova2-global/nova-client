"""NovaUI dragon soul refine window
(nui/windows/dragon-soul-refine/dragon-soul-refine.rml; P15 spec 6).

While the dragon-soul-refine flag is on, Interface.__MakeWindows makes
DragonSoulRefineWindow below through nui_windows.make() instead of
uiDragonSoul.DragonSoulRefineWindow. It is a subclass of the legacy class
(P15 spec D1): its constructor is legacy's, whose uiscript loader it
replaces with proxies standing where the legacy widgets were
(nui_slots.FullSlotWindowProxy for the material and result cells,
nui_proxies for the three mode toggles, the refine button, the fee and the
title bar), bound to the legacy handlers as legacy's loader bound its
widgets. So the three modes, the recipes and their checks, the popups, the
counts legacy lowers and puts back (player.SetItemCount), the refine packet
(player.SendDragonSoulRefine), the result and the close are the legacy
class's own code; the proxies record what it tells them and the board shows
it. It works with either inventory and either dragon soul window, legacy or
NovaUI: each holds it by SetDragonSoulRefineWindow and calls AutoSetItem.
Legacy's ScriptWindow stays underneath, a 0 x 0 window in the UI layer, so
IsShow, the Escape chain and SetTop are legacy's.

No Python runs per frame (legacy has none). The board exists only while the
window shows (nui_hud.OnDemand). Legacy sets the result cell without
RefreshSlot, so every legacy entry point and board event ends with a flush
of the slot proxies it changed, and of the mode, which legacy keeps in an
attribute. Every count comes from nui_limits.current()."""

import item
import localeInfo
import player
import ui
import uiCommon
import uiDragonSoul

import nui
import nui_dragon_soul
import nui_hud
import nui_limits
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/dragon-soul-refine/dragon-soul-refine.rml"
KEY = "dragon-soul-refine"
_LEGACY = uiDragonSoul.DragonSoulRefineWindow
# The three modes: the model's name, legacy's refine type, the label.
MODES = (("grade", _LEGACY.REFINE_TYPE_GRADE, "@ui.GRADE_SELECT"),
         ("step", _LEGACY.REFINE_TYPE_STEP, "@ui.STEP_SELECT"),
         ("strength", _LEGACY.REFINE_TYPE_STRENGTH, "@ui.STRENGTH_SELECT"))


def _slot_type_of(window):
	"""The slot type of an item of an inventory window (an item placed in
	the refine window comes from the inventory or the dragon soul one)."""
	if window == getattr(player, "DRAGON_SOUL_INVENTORY", None):
		return getattr(player, "SLOT_TYPE_DRAGON_SOUL_INVENTORY", player.SLOT_TYPE_INVENTORY)
	return player.SLOT_TYPE_INVENTORY


class _RefineBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The refine window's document; its events go to its window. A press on
	it raises the window, as legacy's window manager does (RaisesOnPress);
	buttons act on a left mousedown."""

	DOCUMENT = DOCUMENT
	MODEL = "ds_refine"

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
			self._owner._close()

	@nui.on("mode_press")
	def on_mode_press(self, name, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_mode(str(name))

	@nui.on("refine_press")
	def on_refine_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.doRefineButton.click()

	# --- the material and result cells: the legacy slot windows' events -------------------

	@nui.on("cell_press")
	def on_cell_press(self, index, button):
		self.raise_for(button)
		self._owner._cell_events.press(int(index), button)

	@nui.on("cell_release")
	def on_cell_release(self, index, button):
		self._owner._cell_events.release(int(index), button)

	@nui.on("cell_use")
	def on_cell_use(self, index):
		self._owner._cell_events.use(int(index))

	@nui.on("cell_over")
	def on_cell_over(self, index):
		self._owner._cell_events.over(int(index))

	@nui.on("cell_out")
	def on_cell_out(self, index):
		self._owner._cell_events.out(int(index))

	@nui.on("cell_drop")
	def on_cell_drop(self, index):
		self._owner._cell_events.drop(int(index))

	@nui.on("result_over")
	def on_result_over(self, index):
		self._owner._result_events.over(int(index))

	@nui.on("result_out")
	def on_result_out(self, index):
		self._owner._result_events.out(int(index))


nui_dragon_soul.flush_board_events(_RefineBoard)


class DragonSoulRefineWindow(uiDragonSoul.DragonSoulRefineWindow):
	"""uiDragonSoul.DragonSoulRefineWindow on NovaUI
	(Interface.wndDragonSoulRefine)."""

	NUI_FACADE = True

	def __init__(self):
		nui_hud.take_over(KEY, self)
		self._nui_discarded = False
		self._limits = nui_limits.current()
		self._flush_depth = 0
		self._flushing = False
		self._cell_events = None
		self._result_events = None
		self._state = self._empty_state()
		self._place = None
		self.loaded = False
		self.demand = None
		if nui_hud.has_engine_3c():
			self.demand = nui_hud.OnDemand(self._make_board, self._restore_board, self._keep_board)
		try:
			uiDragonSoul.DragonSoulRefineWindow.__init__(self)
			if self.demand is not None:
				self.loaded = self.demand.probe()
		except Exception:
			self.nui_discard()
			raise

	# --- make()'s protocol ------------------------------------------------------------

	def nui_ready(self):
		return self.loaded and self.demand is not None and nui_hud.has_engine_3c()

	def nui_discard(self):
		self._nui_discarded = True
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(KEY, self)

	# --- the model ------------------------------------------------------------------

	def _empty_state(self):
		limits = self._limits
		return {
			"placed": False,
			# P15 F-2: the grids take a right press while something is attached.
			"attach_right": bool(nui_slots.ATTACH_RIGHT),
			"mode": MODES[0][0],
			"modes": [{"name": name, "label": label, "down": index == 0} for index, (name, _, label) in enumerate(MODES)],
			"cells": [dict(nui_slots.empty_cell(i), closed=True, ghost=False)
			          for i in range(limits.DRAGON_SOUL_REFINE_CELLS)],
			"cells_cols": limits.DRAGON_SOUL_REFINE_COLUMNS,
			"result": [nui_slots.empty_cell(i) for i in range(limits.DRAGON_SOUL_RESULT_CELLS)],
			"result_cols": limits.DRAGON_SOUL_RESULT_COLUMNS,
			"fee": "",
			"fee_value": 0,
		}

	def _set(self, **values):
		"""The changed keys into the state and the shown board."""
		changed = dict((key, value) for key, value in values.items() if self._state.get(key) != value)
		if not changed:
			return
		self._state.update(changed)
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.set(**changed)

	def _make_board(self):
		return _RefineBoard(self, self._state)

	def _restore_board(self, board):
		self._flush()
		board.set(**self._state)
		if self._place is not None:
			self._state["placed"] = True
			board.set(placed=True)
			board.set_position(self._place[0], self._place[1])

	def _keep_board(self, board):
		"""Legacy's window keeps the place it was dragged to (D10)."""
		box = board.element_box("")
		if box:
			scale = nui.get_scale() or 1.0
			self._place = (box[0] / scale, box[1] / scale)

	def board(self):
		return self.demand.board() if self.demand is not None else None

	# --- the proxies' callbacks -------------------------------------------------------

	def _placed_info(self, info_name, slot):
		info = getattr(self, info_name, None) or {}
		return info.get(slot)

	def _cell_position(self, slot):
		placed = self._placed_info("refineItemInfo", slot)
		return placed[1] if placed is not None else slot

	def _result_position(self, slot):
		placed = self._placed_info("resultItemInfo", slot)
		return placed[1] if placed is not None else slot

	def _reference_icon(self, slot, handle):
		"""The recipe's reference icon (uidragonsoul.py:1446-1449): legacy has
		just selected the item it draws, and passes its image."""
		return item.GetIconImageFileName()

	def _typed(self, cells, info_name):
		"""A placed item's cell takes the slot type of its inventory window
		and its position there (refineItemInfo, resultItemInfo)."""
		for cell in cells:
			placed = self._placed_info(info_name, cell["index"])
			if cell["kind"] == "item" and placed is not None:
				cell["type"] = _slot_type_of(placed[0])
				cell["ref"] = int(placed[1])
		return cells

	def _material_cells(self, cells, states=None, picked=-1):
		marked = self._typed(nui_slots.with_states(cells, states or {}, picked), "refineItemInfo")
		extras = self.wndRefineSlot.extras()
		for cell in marked:
			extra = extras[cell["index"]]
			cell["closed"] = extra["closed"]
			cell["ghost"] = bool(cell["kind"]) and extra["alpha"] < 1.0
		return marked

	def _on_cells(self, cells):
		events = self._cell_events
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		self._set(cells=self._material_cells(cells, states, picked))

	def _on_cell_states(self, states, picked):
		self._set(cells=self._material_cells(self.wndRefineSlot.cells(), states, picked))

	def _on_result(self, cells):
		events = self._result_events
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		self._set(result=self._typed(nui_slots.with_states(cells, states, picked), "resultItemInfo"))

	def _on_result_states(self, states, picked):
		"""The result cells bind only the tooltips (uiscript ResultSlot), but
		their grid draws the footprint of what is attached as any
		CGridSlotWindow does."""
		self._set(result=self._typed(nui_slots.with_states(self.wndResultSlot.cells(), states, picked), "resultItemInfo"))

	def _on_fee(self, text):
		recipe = getattr(self, "currentRecipe", None) or {}
		self._set(fee=nui.plain_text(text), fee_value=int(recipe.get("fee", 0)))

	def _sync_modes(self, *ignored):
		"""The mode legacy keeps (currentRefineType) and its toggles."""
		buttons = getattr(self, "refineChoiceButtonDict", None)
		if not buttons:
			return
		current = getattr(self, "currentRefineType", MODES[0][1])
		modes = [{"name": name, "label": label, "down": bool(buttons[kind].IsDown())} for name, kind, label in MODES]
		mode = dict((kind, name) for name, kind, _ in MODES).get(current, MODES[0][0])
		self._set(modes=modes, mode=mode)

	# --- the loader (uidragonsoul.py:910-976, on proxies) ---------------------------------

	def _DragonSoulRefineWindow__LoadWindow(self):
		"""Legacy's, on proxies (P15 spec 6.4): without its right-to-left
		mirroring and without exception.Abort (make() falls back to the
		legacy window when this raises); every attribute legacy reads, the
		same events bound to the same legacy handlers, the same state at
		the end."""
		if self.isLoaded == 1:
			return
		self.isLoaded = 1
		# The uiscript's style (dragonsoulrefinewindow.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		limits = self._limits
		columns = limits.DRAGON_SOUL_REFINE_COLUMNS
		result_columns = limits.DRAGON_SOUL_RESULT_COLUMNS

		wndRefineSlot = nui_slots.FullSlotWindowProxy(
			range(limits.DRAGON_SOUL_REFINE_CELLS), self._on_cells, cols=columns,
			rows=limits.DRAGON_SOUL_REFINE_CELLS // max(1, columns), positions=self._cell_position,
			icon_of=self._reference_icon, limits=limits)
		wndResultSlot = nui_slots.FullSlotWindowProxy(
			range(limits.DRAGON_SOUL_RESULT_CELLS), self._on_result, cols=result_columns,
			rows=limits.DRAGON_SOUL_RESULT_CELLS // max(1, result_columns), positions=self._result_position,
			limits=limits)
		self._title_bar = nui_proxies.BoardProxy()
		self._title_bar.SetCloseEvent(ui.__mem_func__(self.Close))
		self.refineChoiceButtonDict = dict((kind, nui_proxies.ToggleButtonProxy(self._sync_modes)) for _, kind, _ in MODES)
		self.doRefineButton = nui_proxies.ButtonProxy()
		self.wndMoney = nui_proxies.TextProxy(self._on_fee)

		## Item Slots
		wndRefineSlot.SetOverInItemEvent(ui.__mem_func__(self._DragonSoulRefineWindow__OverInRefineItem))
		wndRefineSlot.SetOverOutItemEvent(ui.__mem_func__(self._DragonSoulRefineWindow__OverOutItem))
		wndRefineSlot.SetSelectEmptySlotEvent(ui.__mem_func__(self._DragonSoulRefineWindow__SelectRefineEmptySlot))
		wndRefineSlot.SetSelectItemSlotEvent(ui.__mem_func__(self._DragonSoulRefineWindow__SelectRefineItemSlot))
		wndRefineSlot.SetUseSlotEvent(ui.__mem_func__(self._DragonSoulRefineWindow__SelectRefineItemSlot))
		wndRefineSlot.SetUnselectItemSlotEvent(ui.__mem_func__(self._DragonSoulRefineWindow__SelectRefineItemSlot))

		wndResultSlot.SetOverInItemEvent(ui.__mem_func__(self._DragonSoulRefineWindow__OverInResultItem))
		wndResultSlot.SetOverOutItemEvent(ui.__mem_func__(self._DragonSoulRefineWindow__OverOutItem))
		self.wndRefineSlot = wndRefineSlot
		self.wndResultSlot = wndResultSlot
		self._cell_events = nui_slots.LegacySlotEvents(wndRefineSlot, on_states=self._on_cell_states)
		self._result_events = nui_slots.LegacySlotEvents(wndResultSlot, on_states=self._on_result_states)

		## Button
		buttons = self.refineChoiceButtonDict
		buttons[self.REFINE_TYPE_GRADE].SetToggleDownEvent(self._DragonSoulRefineWindow__ToggleDownGradeButton)
		buttons[self.REFINE_TYPE_STEP].SetToggleDownEvent(self._DragonSoulRefineWindow__ToggleDownStepButton)
		buttons[self.REFINE_TYPE_STRENGTH].SetToggleDownEvent(self._DragonSoulRefineWindow__ToggleDownStrengthButton)
		buttons[self.REFINE_TYPE_GRADE].SetToggleUpEvent(
			lambda: self._DragonSoulRefineWindow__ToggleUpButton(self.REFINE_TYPE_GRADE))
		buttons[self.REFINE_TYPE_STEP].SetToggleUpEvent(
			lambda: self._DragonSoulRefineWindow__ToggleUpButton(self.REFINE_TYPE_STEP))
		buttons[self.REFINE_TYPE_STRENGTH].SetToggleUpEvent(
			lambda: self._DragonSoulRefineWindow__ToggleUpButton(self.REFINE_TYPE_STRENGTH))
		self.doRefineButton.SetEvent(self._DragonSoulRefineWindow__PressDoRefineButton)

		## Dialog
		self.wndPopupDialog = uiCommon.PopupDialog()

		self.currentRefineType = self.REFINE_TYPE_GRADE
		self.refineItemInfo = {}
		self.resultItemInfo = {}
		self.currentRecipe = {}

		self.wndMoney.SetText(localeInfo.NumberToMoneyString(0))
		self.refineChoiceButtonDict[self.REFINE_TYPE_GRADE].Down()

		self._DragonSoulRefineWindow__Initialize()

	# --- the board's presses -----------------------------------------------------------

	def _close(self):
		self._title_bar.close()

	def _press_mode(self, name):
		"""A mode toggle (CToggleButton): another mode's goes down and runs its
		down event; the shown mode's goes up and its up event presses it
		down again."""
		for mode, kind, _ in MODES:
			if mode == name:
				self.refineChoiceButtonDict[kind].click()
				return

	# --- the flush ------------------------------------------------------------------

	def _flush(self):
		"""What legacy changed without RefreshSlot during the call that ends
		now (the result cell, a cleared cell) and the mode it keeps in an
		attribute reach the model."""
		if self._flushing:
			return
		self._flushing = True
		try:
			for events in (self._cell_events, self._result_events):
				if events is not None and events.proxy.dirty:
					events.proxy.push()
			self._sync_modes()
		finally:
			self._flushing = False

	# --- what NovaUI changes (P15 spec 6.4) --------------------------------------------

	def Show(self):
		# The board first, then legacy's second Show (the grade mode, a fee
		# of 0, the refresh), which reaches it.
		if self.demand is not None:
			self.demand.show()
		uiDragonSoul.DragonSoulRefineWindow.Show(self)

	def Hide(self):
		uiDragonSoul.DragonSoulRefineWindow.Hide(self)
		for events in (self._cell_events, self._result_events):
			if events is not None:
				events.reset()
		if self.demand is not None:
			self.demand.hide()

	def SetTop(self):
		board = self.board()
		if board is not None:
			board.bring_to_front()
		uiDragonSoul.DragonSoulRefineWindow.SetTop(self)

	def Destroy(self):
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		uiDragonSoul.DragonSoulRefineWindow.Destroy(self)
		nui_hud.forget(KEY, self)


# The facade (P15 spec 6.4: what the Interface, the inventories and the C++
# callbacks call) and what changes the cells. Close is bound through
# ui.__mem_func__ and called with no argument; the handlers legacy binds to
# the slot events with their slot stay unwrapped (the board's events flush).
FLUSHED = ("AutoSetItem", "Close", "Hide", "OnPressEscapeKey", "RefineFail", "RefineSucceed", "Refresh", "Show")
for _name in FLUSHED:
	setattr(DragonSoulRefineWindow, _name, nui_dragon_soul.flushes(getattr(DragonSoulRefineWindow, _name)))
del _name
