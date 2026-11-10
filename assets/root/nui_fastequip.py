"""NovaUI fast equip (nui/windows/fastequip/fastequip.rml; Wave 8, NOVA-17).

While the fastequip flag is on, Interface.__MakeWindows makes FastEquipWindow
below through nui_windows.make() instead of uiFastEquip.FastEquipWindow: a
subclass of the legacy class (nui_facade.Facade) whose loader puts proxies
where the widgets were: the 10 set lines, the selected set's name and color,
the wear cells (one SlotWindowProxy per usable wear cell, keyed by wear
index), Switch, Clear and the edit popup. So every flow (a drop filtered by
the cell's type, the save that keeps every other cell, a right click that
empties a cell, a click that drops a cell held elsewhere, the trailing
refresh, Clear's question) is legacy's code, and the board shows what the
proxies were told.

Nothing runs per frame: the trailing refresh is a nui-countdown timer whose
countdownend calls legacy's CheckRefreshDue, and the window keeps its board
only while it shows. It draws below the legacy UI layer, as legacy's window
lived in it.

Eddy's r41 notes: a press, a drag's release or a legacy drop anywhere on the
canvas (the set's slot area) goes to legacy's DropAnywhere, which finds the
item's cell; a tall item's icon keeps its size in its cell (the sheet). The
name field takes the focus (the body's focus: none is inherited, so the
field sets focus: auto and focuses itself on a press, and the panel focuses
it once shown), its text never enters the model, and Enter and Escape reach
legacy's edit line events (save, close)."""

import uiFastEquip
import ui
import fastEquip

import nui
import nui_facade
import nui_form_proxies
import nui_hud
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/fastequip/fastequip.rml"
KEY = "fastequip"
WEARS = tuple(sorted(uiFastEquip.CELLS))
NAME_FIELD = "fastequip-name"


def _css(color):
	return "#%06X" % (int(color) & 0xFFFFFF)


class _Bar(nui_proxies._Shown):
	"""ui.Bar: shown or hidden and a color."""

	def __init__(self, on_change):
		self.shown = False
		self.color = None
		self.on_change = on_change

	def SetColor(self, color):
		self.color = color
		self.on_change()

	def Show(self):
		self.shown = True
		self.on_change()

	def Hide(self):
		self.shown = False
		self.on_change()


class _SetRow(object):
	"""A line of the set list (legacy's EquipSet) as data."""

	def __init__(self, index, on_change):
		self.index = index
		self.name = ""
		self.color = uiFastEquip.DEFAULT_SET_COLOR
		self.on_change = on_change

	def SetEntry(self, name, color):
		self.name = name
		self.color = color
		self.on_change()

	def Show(self):
		pass


class _EditPopup(object):
	"""Legacy's EditPopUp as a panel of the board."""

	def __init__(self, owner):
		self._owner = nui_hud.keep_weakly(owner)
		self.index = 0
		self.colorIndex = 0
		self.shown = False
		self.saveEvent = None
		self.nameEditLine = nui_form_proxies.FieldProxy(NAME_FIELD, owner._on_field)
		self.nameEditLine.SetMax(fastEquip.NAME_MAX_CHARS)
		self.nameEditLine.reader = lambda: owner._name_value()
		# As legacy's EditPopUp: Enter saves, Escape closes.
		self.nameEditLine.SetReturnEvent(ui.__mem_func__(self.UpdateButton))
		self.nameEditLine.SetEscapeEvent(ui.__mem_func__(self.Close))

	def _changed(self):
		try:
			self._owner._sync()
		except ReferenceError:
			pass

	def SetPosition(self, x, y):
		pass

	def GetWidth(self):
		return 0

	def ClickColor(self, colorIndex):
		self.colorIndex = colorIndex
		self._changed()

	def UpdateButton(self):
		if self.saveEvent:
			self.saveEvent(self.index, self.nameEditLine.GetText(), self.colorIndex)
		self.Hide()

	def Open(self, index, name, colorIndex):
		self.index = index
		self.colorIndex = colorIndex
		self.nameEditLine.SetText(name)
		self.shown = True
		self._changed()
		self.nameEditLine.SetFocus()

	def Close(self):
		self.Hide()

	def Hide(self):
		self.shown = False
		self._changed()

	def IsShow(self):
		return self.shown


class _FastEquipBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The fast equip document; its events go to its window. A press on it
	raises the window, as legacy's window manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "fastequip"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)
		if self._doc:
			# A focused field stops every key but Tab: the field hears its own.
			self.element_on(NAME_FIELD, "keydown", self._on_name_key)

	def initial_model(self):
		return dict(self._initial)

	def _on_name_key(self, event):
		"""Legacy's edit line: Enter is its OnIMEReturn (save), Escape its
		OnPressEscapeKey (close the panel); each is kept, so Escape does not
		also close the window."""
		if not self.is_visible():
			return None
		popup = self._owner.wndPopUpEdit
		if popup is None or not popup.IsShow():
			return None
		key = event.get("key_identifier")
		if key in (nui.KEY_RETURN, nui.KEY_NUMPADENTER):
			popup.nameEditLine.fire_return()
			return True
		if key == nui.KEY_ESCAPE:
			popup.nameEditLine.fire_escape()
			return True
		return None

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.Close()

	@nui.on("set_press")
	def on_set_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.SelectSet(int(index))

	@nui.on("edit_press")
	def on_edit_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.OpenEditPopup(int(index))

	@nui.on("switch_press")
	def on_switch_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.switchButton.click()

	@nui.on("clear_press")
	def on_clear_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.clearButton.click()

	@nui.on("slot_press")
	def on_slot_press(self, wear, button):
		self.raise_for(button)
		self._owner._cell(wear, "press", button)

	@nui.on("slot_release")
	def on_slot_release(self, wear, button):
		self._owner._cell(wear, "release", button)

	@nui.on("slot_use")
	def on_slot_use(self, wear):
		self._owner._cell(wear, "use")

	@nui.on("slot_over")
	def on_slot_over(self, wear):
		self._owner._cell(wear, "over")

	@nui.on("slot_out")
	def on_slot_out(self, wear):
		self._owner._cell(wear, "out")

	@nui.on("slot_drop")
	def on_slot_drop(self, wear):
		self._owner._cell(wear, "drop")

	@nui.on("name_typed")
	def on_name_typed(self, value):
		self._owner.wndPopUpEdit.nameEditLine.typed(value)

	@nui.on("name_press")
	def on_name_press(self, button):
		self.raise_for(button)
		if button == 0:
			self.focus(NAME_FIELD)

	@nui.on("edit_click")
	def on_edit_click(self, index):
		"""The edit button's click, after the press opened the panel: the
		field is shown now (a data-if field takes no focus in the press's own
		handler), so it gets the caret, as legacy's Open gives it."""
		popup = self._owner.wndPopUpEdit
		if popup is not None and popup.IsShow() and popup.index == int(index):
			self.focus(NAME_FIELD)

	@nui.on("canvas_press")
	def on_canvas_press(self, button):
		if button == 0:
			self._owner.DropAnywhere()

	@nui.on("canvas_release")
	def on_canvas_release(self, button):
		if button == 0 and nui_slots.take_drag_release():
			self._owner.DropAnywhere()

	@nui.on("canvas_drop")
	def on_canvas_drop(self):
		self._owner.DropAnywhere()

	@nui.on("color_press")
	def on_color_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.wndPopUpEdit.ClickColor(int(index))

	@nui.on("edit_ok")
	def on_edit_ok(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.wndPopUpEdit.UpdateButton()

	@nui.on("edit_cancel")
	def on_edit_cancel(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.wndPopUpEdit.Close()

	@nui.on("refresh_due")
	def on_refresh_due(self):
		self._owner.CheckRefreshDue()


class FastEquipWindow(nui_facade.Facade, uiFastEquip.FastEquipWindow):
	"""uiFastEquip.FastEquipWindow on NovaUI (Interface.wndFastEquip)."""

	KEY = KEY
	BOARD = _FastEquipBoard
	PLACE = "center"

	# ui.Window.__init__ calls Hide before this class's __init__ has set
	# anything: Facade's Hide reads these.
	_slot_events = ()
	demand = None
	_syncing = True

	def __init__(self):
		self._syncing = True
		self._cells_by_wear = {}
		self.nui_begin()
		try:
			uiFastEquip.FastEquipWindow.__init__(self)
			self._syncing = False
			self._sync()
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			"sets": [],
			"cells": [self._empty_cell(wear) for wear in WEARS],
			"attaching": False,
			"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
			"title": "",
			"title_css": "#181F1A",
			"equipped": False,
			"buffi_on": False,
			"aura_on": False,
			"edit_on": False,
			"palette": [],
			"refresh_end": 0.0,
		}

	@staticmethod
	def _empty_cell(wear):
		cell = dict(nui_slots.empty_cell(0))
		cell.update({"index": wear, "shown": False, "missing": False})
		return cell

	# --- the loader (uifastequip.py __LoadWindow, on proxies) ---------------------------

	def _FastEquipWindow__LoadWindow(self):
		# The uiscript's style.
		self.AddFlag("movable")
		self.AddFlag("float")
		sync = lambda *args: self._sync()
		self.board = nui_proxies.BoardProxy(460, 435)
		self.titleLabel = nui_proxies.TextProxy(sync)
		self.titleColor = _Bar(sync)
		self.equippedBar = _Bar(sync)
		self.switchButton = nui_proxies.ButtonProxy(sync)
		self.clearButton = nui_proxies.ButtonProxy(sync)
		self.buffiLabel = _Bar(sync)
		self.auraLabel = _Bar(sync)
		for i in range(fastEquip.SET_COUNT):
			self.setRows[i] = _SetRow(i, sync)
		self.wndPopUpEdit = _EditPopup(self)
		self.wndPopUpEdit.saveEvent = ui.__mem_func__(self.SaveEdit)

	def _FastEquipWindow__MakeSlots(self, usable):
		"""A proxy over the usable cells (legacy builds a fresh slot window;
		the board hides the rest in its model)."""
		sync = lambda *args: self._sync()
		slots = nui_slots.SlotWindowProxy(usable, self._on_cells)
		slots.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		slots.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		slots.SetSelectEmptySlotEvent(ui.__mem_func__(self.SelectEmptySlot))
		slots.SetSelectItemSlotEvent(ui.__mem_func__(self.SelectItemSlot))
		slots.SetUnselectItemSlotEvent(ui.__mem_func__(self.UseItemSlot))
		slots.SetUseSlotEvent(ui.__mem_func__(self.UseItemSlot))
		self.itemSlot = slots
		self._cell_events = self.nui_events(nui_slots.LegacySlotEvents(
			slots, on_states=self._on_states, on_attaching=self._on_attaching))
		self.buffiLabel.shown = any(wear in usable for wear in uiFastEquip.BUFFI_CELLS)
		self.auraLabel.shown = 39 in usable
		slots.RefreshSlot()
		sync()

	# --- the proxies' callbacks ---------------------------------------------------------

	def _cell(self, wear, what, button=None):
		slots = self.itemSlot
		if slots is None:
			return
		index = slots.index_of(int(wear))
		if index is None:
			return
		event = getattr(self._cell_events, what)
		if button is None:
			event(index)
		else:
			event(index, button)

	def _on_cells(self, cells):
		self._cells_by_wear = dict(zip(self.itemSlot.slot_numbers, cells))
		self._sync()

	def _on_states(self, states, picked):
		cells = nui_slots.with_states(self.itemSlot.cells(), states, picked)
		self._cells_by_wear = dict(zip(self.itemSlot.slot_numbers, cells))
		self._sync()

	def _on_attaching(self, flag):
		self.nui_set(attaching=flag)

	# --- what the board shows --------------------------------------------------------------

	def RefreshSelected(self):
		uiFastEquip.FastEquipWindow.RefreshSelected(self)
		self._sync()

	def _sync(self):
		if self._syncing or not hasattr(self, "_state"):
			return
		index = self.selectedSet
		values = {"title": nui.plain_text(self.titleLabel.text),
		          "title_css": _css(self.titleColor.color) if self.titleColor.color is not None else "#181F1A",
		          "equipped": self.equippedBar.color == 0xff42f548,
		          "buffi_on": bool(self.buffiLabel.shown), "aura_on": bool(self.auraLabel.shown)}
		values["sets"] = [{"index": i, "name": nui.plain_text(row.name), "css": _css(row.color), "selected": i == index}
		                  for i, row in sorted(self.setRows.items())]
		cells = []
		usable = self.builtCells or ()
		slot_of = {}
		if self.itemSlot is not None and hasattr(self, "itemSlot"):
			slot_of = dict(zip(self.itemSlot.slot_numbers, self.itemSlot.cells()))
		held = self._cells_by_wear
		for wear in WEARS:
			cell = self._empty_cell(wear)
			if wear in usable:
				cell.update(held.get(wear) or slot_of.get(wear, {}))
				cell["index"] = wear
				cell["shown"] = True
				window, _ = fastEquip.GetSlot(index, wear)
				cell["missing"] = window == fastEquip.SLOT_KEEP
			cells.append(cell)
		values["cells"] = cells
		popup = self.wndPopUpEdit
		values["edit_on"] = bool(popup is not None and popup.shown)
		colors = []
		for i, color in enumerate(uiFastEquip.COLORS):
			colors.append({"index": i + 1, "css": _css(color), "selected": popup is not None and popup.colorIndex == i + 1})
		values["palette"] = colors
		changed = dict((key, value) for key, value in values.items() if self._state.get(key) != value)
		if changed:
			self.nui_set(**changed)

	def _on_field(self, field, what):
		self._sync()
		board = self.nui_board()
		if board is None or not board.is_visible():
			return
		if what == "text":
			# The panel may not show yet (its data-if): even_hidden.
			board.set_value(field.field_id, field.text, caret="end", even_hidden=True)
		elif what == "focus":
			board.focus(field.field_id)

	def _name_value(self):
		"""The name field's live text (None without a shown board)."""
		board = self.nui_board()
		return board.get_value(NAME_FIELD) if board is not None and board.is_visible() else None

	def DropAnywhere(self):
		uiFastEquip.FastEquipWindow.DropAnywhere(self)
		nui_slots.flush_marks()

	def _ArmRefreshTimer(self, seconds):
		self.nui_set(refresh_end=nui.now() + seconds)
