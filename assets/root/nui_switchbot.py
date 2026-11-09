"""NovaUI switchbot (nui/windows/switchbot/switchbot.rml; Wave 7, NOVA-43).

While the switchbot flag is on, Interface.__MakeWindows makes SwitchbotWindow
below through nui_windows.make() instead of uiSwitchbot.SwitchbotWindow: a
subclass of the legacy class (nui_facade.Facade) whose uiscript loader puts
proxies where the widgets were: the six item slots (one SlotWindowProxy over
window SWITCHBOT), each tab's state bar, selection box and select button,
the three alternatives, the cost choice and its line, the 6/7 toggle,
start/stop, save, the premium and speed lines, and the seven target rows
(each a legacy SwitchbotAttribute whose own loader puts proxies where its
button, clear button, value field and arrows were). The attribute search
list and the saved configurations are legacy's classes on proxies too,
shown as panels inside the board. So every flow (a drop into a slot, a pick,
a right click that sends an item back, the selection, the targets and their
highest values, the cost, the start and stop packets, the saved sets) is
legacy's code, and the board shows what the proxies were told.

Nothing runs per frame: legacy has no OnUpdate (its premium line follows the
roll speed the server sends), and the board exists only while the window
shows. It draws below the legacy UI layer, as legacy's window lived in it."""

import localeInfo
import player
import ui
import uiSwitchbot

import nui
import nui_facade
import nui_form_proxies
import nui_hud
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/switchbot/switchbot.rml"
KEY = "switchbot"
ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII")
ROW_COUNT = uiSwitchbot.ATTR_SLOT_COUNT + uiSwitchbot.RARE_ATTR_SLOT_COUNT
# A tab's state bar color (uiSwitchbot's COLOR_*) as the board's state.
STATES = {uiSwitchbot.COLOR_INACTIVE: "idle", uiSwitchbot.COLOR_ACTIVE: "active",
          uiSwitchbot.COLOR_FINISHED: "finished"}
PICKER_FILTER = "switchbot-picker-filter"
PRESET_NAME = "switchbot-preset-name"


def _value_field(index):
	return "switchbot-value-%d" % index


def _slot_count():
	import switchbot
	return int(getattr(switchbot, "SLOT_COUNT", 6) or 6)


class _Bar(nui_proxies._Shown):
	"""ui.Bar and ui.Box: shown or hidden, and a color (a tab's state)."""

	def __init__(self, on_change):
		self.shown = False
		self.color = None
		self.on_change = on_change

	def SetColor(self, color):
		self.color = color
		self.on_change()

	def SetSize(self, width, height):
		pass

	def Show(self):
		self.shown = True
		self.on_change()

	def Hide(self):
		self.shown = False
		self.on_change()


class _Image(nui_proxies._Shown):
	"""The value field's well (an ImageBox the board draws itself)."""

	def LoadImage(self, path):
		pass


class _Row(uiSwitchbot.SwitchbotAttribute):
	"""A target row on proxies: legacy's SwitchbotAttribute with its loader
	(__Create) overridden; the row is no legacy window (an invisible one would
	take the pointer where the legacy row was)."""

	def __init__(self, owner):
		self._owner = nui_hud.keep_weakly(owner)
		self.shown = False
		self._SwitchbotAttribute__Initialize()

	def __del__(self):
		pass

	def _changed(self, *args):
		try:
			self._owner._sync()
		except ReferenceError:
			pass

	def _SwitchbotAttribute__Create(self, width):
		self.searchTypeButton = nui_proxies.ButtonProxy(self._changed)
		self.deleteAttributeButton = nui_proxies.ButtonProxy(self._changed)
		self.valueInput = _Image()
		self.valueEditLine = nui_form_proxies.FieldProxy(_value_field(self.index), self._on_field)
		self.leftArrow = nui_proxies.ButtonProxy(self._changed)
		self.rightArrow = nui_proxies.ButtonProxy(self._changed)
		self.LineBar = _Bar(self._changed)

	def _on_field(self, field, what):
		try:
			self._owner._on_field(field, what)
		except ReferenceError:
			pass

	# The legacy window's calls on its row (ui.Window's, which a proxy row
	# answers itself).
	def SetParent(self, parent):
		pass

	def SetSize(self, width, height):
		pass

	def SetPosition(self, x, y):
		pass

	def Show(self):
		self.shown = True
		self._changed()

	def Hide(self):
		self.shown = False
		if self.valueEditLine:
			self.valueEditLine.KillFocus()
		self._changed()

	def IsShow(self):
		return self.shown


class _ListLine(object):
	"""A search list line or a saved configuration's line, as data (legacy's
	are ListBoxEx items): its key and text, or its id, name and events."""

	def __init__(self, key=0, value=""):
		self.key = key
		self.value = value
		self.id = 0
		self.name = ""
		self.loadEvent = None
		self.deleteEvent = None

	def GetKey(self):
		return self.key

	def GetValue(self):
		return self.value

	def Load(self, id, name):
		self.id = id
		self.name = name

	def SetLoadEvent(self, event):
		self.loadEvent = event

	def SetDeleteEvent(self, event):
		self.deleteEvent = event

	def load(self):
		if self.loadEvent:
			self.loadEvent(self.id)

	def delete(self):
		if self.deleteEvent:
			self.deleteEvent(self.id)


class _PanelMixin(object):
	"""What legacy calls on the board of its search list and configuration
	window (ui.BoardWithTitleBar), answered by a panel of the switchbot's
	board: shown or hidden, a title, no place of its own."""

	shown = False
	title = ""

	def _changed(self, *args):
		try:
			self._owner._sync()
		except ReferenceError:
			pass

	def SetSize(self, width, height):
		self.size = (width, height)

	def GetWidth(self):
		return getattr(self, "size", (0, 0))[0]

	def SetPosition(self, x, y):
		pass

	def SetTitleName(self, name):
		self.title = "" if name is None else str(name)
		self._changed()

	def SetCloseEvent(self, event):
		self.closeEvent = event

	def AddFlag(self, flag):
		pass

	def SetTop(self):
		pass

	def Show(self):
		self.shown = True
		self._changed()

	def Hide(self):
		self.shown = False
		self._changed()

	def IsShow(self):
		return self.shown


class _SearchList(_PanelMixin, uiSwitchbot.SearchListWindow):
	"""Legacy's SearchListWindow on proxies: its filter field, list, accept
	and cancel are legacy's; MakeWindow (its loader) puts proxies."""

	def __init__(self, owner):
		self._owner = nui_hud.keep_weakly(owner)
		self.listItems = {}
		self.order = []
		self.acceptEvent = None
		self.acceptArgsType = "VALUE"
		self.cancelEvent = None
		self.searchEditLine = None
		self.listBox = None

	def __del__(self):
		pass

	def MakeWindow(self, width, height, maxInput=50):
		self.SetSize(width, height)
		owner = self._owner
		self.searchEditLine = nui_form_proxies.FieldProxy(PICKER_FILTER, owner._on_field)
		self.searchEditLine.SetMax(maxInput)
		self.searchEditLine.SetEscapeEvent(ui.__mem_func__(self.Close))
		self.listBox = nui_form_proxies.ListBoxExProxy(self._changed)

	def MakeItem(self, key, value):
		return _ListLine(key, value)


class _Configurations(_PanelMixin, uiSwitchbot.ConfigurationWindow):
	"""Legacy's ConfigurationWindow on proxies: loading, saving, applying
	and deleting the saved sets are legacy's; its loader puts proxies."""

	def __init__(self, owner, wndSwitchbot):
		self._owner = nui_hud.keep_weakly(owner)
		self.wndSwitchbot = wndSwitchbot
		self.dict = {}
		self._ConfigurationWindow__LoadWindow()

	def __del__(self):
		pass

	def _ConfigurationWindow__LoadWindow(self):
		owner = self._owner
		self.SetTitleName(localeInfo.SWITCHBOT_CONFIGURATION_TITLE)
		self.saveButton = nui_proxies.ButtonProxy(self._changed)
		self.saveButton.SetEvent(ui.__mem_func__(self.Save))
		self.nameEditLine = nui_form_proxies.FieldProxy(PRESET_NAME, owner._on_field)
		self.nameEditLine.SetMax(32)
		self.nameEditLine.reader = lambda: owner._read_field(PRESET_NAME)
		self.nameEditLine.SetEscapeEvent(ui.__mem_func__(self.Close))
		self.listBox = nui_form_proxies.ListBoxExProxy(self._changed)

	def MakeLine(self, width):
		return _ListLine()

	def AdjustPosition(self):
		pass


class _SwitchbotBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The switchbot's document; its events go to its window. A press on it
	raises the window, as legacy's window manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "switchbot"

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
			self._owner.titleBar.close()

	@nui.on("slot_press")
	def on_slot_press(self, index, button):
		self.raise_for(button)
		self._owner._cell_events.press(int(index), button)

	@nui.on("slot_release")
	def on_slot_release(self, index, button):
		self._owner._cell_events.release(int(index), button)

	@nui.on("slot_use")
	def on_slot_use(self, index):
		self._owner._cell_events.use(int(index))

	@nui.on("slot_over")
	def on_slot_over(self, index):
		self._owner._cell_events.over(int(index))

	@nui.on("slot_out")
	def on_slot_out(self, index):
		self._owner._cell_events.out(int(index))

	@nui.on("slot_drop")
	def on_slot_drop(self, index):
		self._owner._cell_events.drop(int(index))

	@nui.on("tab_press")
	def on_tab_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.selectButtons[int(index)].click()

	@nui.on("alt_press")
	def on_alt_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.alternativeButtons[int(index)].click()

	@nui.on("cost_press")
	def on_cost_press(self, cost, button):
		self.raise_for(button)
		if button == 0:
			self._owner.costButtons[int(cost)].click()

	@nui.on("rare_press")
	def on_rare_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.rareButton.press()

	@nui.on("start_press")
	def on_start_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.startstopButton.click()

	@nui.on("save_press")
	def on_save_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.saveButton.click()

	@nui.on("row_pick")
	def on_row_pick(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._row(index).searchTypeButton.click()

	@nui.on("row_clear")
	def on_row_clear(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._row(index).deleteAttributeButton.click()

	@nui.on("row_minus")
	def on_row_minus(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._row(index).leftArrow.click()

	@nui.on("row_plus")
	def on_row_plus(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._row(index).rightArrow.click()

	@nui.on("row_value")
	def on_row_value(self, index, value):
		self._owner._row_typed(int(index), value)

	@nui.on("picker_item")
	def on_picker_item(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._picker_select(int(index))

	@nui.on("picker_accept")
	def on_picker_accept(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner._picker_accept()

	@nui.on("picker_cancel")
	def on_picker_cancel(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner._picker_cancel()

	@nui.on("picker_filter")
	def on_picker_filter(self, value):
		self._owner._picker_filter(value)

	@nui.on("preset_load")
	def on_preset_load(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._preset(int(index), "load")

	@nui.on("preset_delete")
	def on_preset_delete(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._preset(int(index), "delete")

	@nui.on("preset_save")
	def on_preset_save(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner._preset_save()

	@nui.on("preset_close")
	def on_preset_close(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner._preset_close()

	@nui.on("preset_name")
	def on_preset_name(self, value):
		self._owner._preset_typed(value)


def _row_model(index, rare=False):
	return {"index": index, "rare": bool(rare), "shown": False, "line": False, "name": "", "value": "0",
	        "can_pick": True, "can_clear": True, "editing": True}


class SwitchbotWindow(nui_facade.Facade, uiSwitchbot.SwitchbotWindow):
	"""uiSwitchbot.SwitchbotWindow on NovaUI (Interface.wndSwitchbot)."""

	KEY = KEY
	BOARD = _SwitchbotBoard
	PLACE = "center"

	def __init__(self):
		self._syncing = True
		self.nui_begin()
		try:
			uiSwitchbot.SwitchbotWindow.__init__(self)
			self._syncing = False
			self._sync()
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		count = _slot_count()
		cells = []
		for i in range(count):
			cell = dict(nui_slots.empty_cell(i))
			cell.update({"state": "", "selected": i == 0, "label": ROMAN[i] if i < len(ROMAN) else str(i + 1)})
			cells.append(cell)
		return {
			"cells": cells,
			"attaching": False,
			"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
			"filled": False,
			"alt": 0,
			"rows": [_row_model(i, i >= uiSwitchbot.ATTR_SLOT_COUNT) for i in range(ROW_COUNT)],
			"rare_shown": True,
			"rare_on": False,
			"cost": 0,
			"cost_enabled": True,
			"cost_text": "",
			"start_label": "",
			"start_enabled": False,
			"active": False,
			"premium_on": False,
			"premium_text": "",
			"speed_text": "",
			"picker_on": False,
			"picker_title": "",
			"picker_items": [],
			"presets_on": False,
			"presets_title": "",
			"presets": [],
		}

	# --- the loader (uiswitchbot.py __LoadWindow, on proxies) ----------------------------

	def _SwitchbotWindow__LoadWindow(self):
		# The uiscript's style (switchbot.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		import switchbot
		count = _slot_count()
		sync = lambda *args: self._sync()
		self.titleBar = nui_proxies.BoardProxy(742, 23)
		self.itemSlot = nui_slots.SlotWindowProxy(range(count), self._on_cells, window=player.SWITCHBOT)
		for i in range(count):
			self.statusBars[i] = _Bar(sync)
			self.selectBoxes[i] = _Bar(sync)
			self.selectButtons[i] = nui_proxies.ButtonProxy(sync)
		for i in range(switchbot.ALTERNATIVE_COUNT):
			self.alternativeButtons[i] = nui_proxies.ButtonProxy(sync)
		self.costButtons[switchbot.COST_ITEM] = nui_proxies.ButtonProxy(sync)
		self.costButtons[switchbot.COST_YANG] = nui_proxies.ButtonProxy(sync)
		self.costText = nui_proxies.TextProxy(sync)
		self.rareButton = nui_form_proxies.ToggleProxy(sync)
		self.startstopButton = nui_proxies.ButtonProxy(sync)
		self.saveButton = nui_proxies.ButtonProxy(sync)
		self.premiumStatus = nui_proxies.TextProxy(sync)
		self.speedText = nui_proxies.TextProxy(sync)

		for i in range(ROW_COUNT):
			row = self._SwitchbotWindow__MakeAttributeRow()
			row.SetParent(self)
			row.Create(uiSwitchbot.ATTR_ROW_WIDTH, i)
			row.Show()
			if uiSwitchbot.IsRareIndex(i):
				self.rareAttrDict[i] = row
			else:
				self.attrDict[i] = row

		self._cell_events = self.nui_events(nui_slots.LegacySlotEvents(
			self.itemSlot, on_states=self._on_states, on_attaching=self._on_attaching))

	def _SwitchbotWindow__MakeAttributeRow(self):
		return _Row(self)

	def _SwitchbotWindow__MakeSearchList(self):
		"""The list as a panel of the board; the window holds it from now on
		(legacy keeps it after its Open), so the panel shows at that Open."""
		self.attributeSearchWindow = _SearchList(self)
		return self.attributeSearchWindow

	def _SwitchbotWindow__MakeConfigurationWindow(self):
		return _Configurations(self, nui_hud.keep_weakly(self))

	# --- the proxies' callbacks ---------------------------------------------------------

	def _on_cells(self, cells):
		self._cells = cells
		self._sync()

	def _on_states(self, states, picked):
		self._states = (states, picked)
		self._sync()

	def _on_attaching(self, flag):
		self.nui_set(attaching=flag)

	def _row(self, index):
		index = int(index)
		return self.rareAttrDict[index] if uiSwitchbot.IsRareIndex(index) else self.attrDict[index]

	def _sync(self):
		"""What the proxies were told, as the board's model (on events only)."""
		if getattr(self, "_syncing", False) or not hasattr(self, "_state"):
			return
		values = {}
		states, picked = getattr(self, "_states", ({}, -1))
		cells = nui_slots.with_states(getattr(self, "_cells", None) or self.itemSlot.cells(), states, picked)
		merged = []
		for i, cell in enumerate(cells):
			cell = dict(cell)
			bar = self.statusBars.get(i)
			cell["state"] = STATES.get(bar.color, "idle") if bar is not None and bar.shown else ""
			box = self.selectBoxes.get(i)
			cell["selected"] = bool(box is not None and box.shown)
			cell["label"] = ROMAN[i] if i < len(ROMAN) else str(i + 1)
			merged.append(cell)
		values["cells"] = merged
		values["alt"] = next((i for i, b in sorted(self.alternativeButtons.items()) if b.down), 0)
		values["filled"] = any(b.shown for b in self.alternativeButtons.values())
		rows = []
		for index in range(ROW_COUNT):
			row = (self.rareAttrDict if uiSwitchbot.IsRareIndex(index) else self.attrDict).get(index)
			if row is None or row.searchTypeButton is None:
				rows.append(_row_model(index, uiSwitchbot.IsRareIndex(index)))
				continue
			rows.append({"index": index, "rare": uiSwitchbot.IsRareIndex(index), "shown": bool(row.shown),
			             "line": bool(row.LineBar.shown), "name": nui.plain_text(row.searchTypeButton.text),
			             "value": nui.plain_text(row.valueEditLine.text),
			             "can_pick": bool(row.searchTypeButton.enabled and not row.LineBar.shown),
			             "can_clear": bool(row.deleteAttributeButton.enabled),
			             "editing": bool(row.valueEditLine.shown)})
		values["rows"] = rows
		values["rare_shown"] = bool(self.rareButton.shown)
		values["rare_on"] = bool(self.rareButton.down)
		values["cost"] = next((c for c, b in sorted(self.costButtons.items()) if b.down), 0)
		values["cost_enabled"] = all(b.enabled for b in self.costButtons.values())
		values["cost_text"] = nui.plain_text(self.costText.text)
		values["start_label"] = nui.plain_text(self.startstopButton.text)
		values["start_enabled"] = bool(self.startstopButton.enabled)
		values["active"] = bool(self.IsActiveSlot()) if self.statusBars else False
		values["premium_text"] = nui.plain_text(self.premiumStatus.text)
		values["premium_on"] = self.premiumStatus.color == 0xff4ba136
		values["speed_text"] = nui.plain_text(self.speedText.text)
		picker = self.attributeSearchWindow
		values["picker_on"] = bool(picker is not None and picker.shown)
		values["picker_title"] = nui.plain_text(picker.title) if picker is not None else ""
		items = []
		if picker is not None and picker.listBox is not None:
			for i, entry in enumerate(picker.listBox.entries):
				items.append({"text": nui.plain_text(entry.GetValue()), "selected": i == picker.listBox.selected})
		values["picker_items"] = items
		presets = self.configurationSaveWindow
		values["presets_on"] = bool(presets is not None and presets.shown)
		values["presets_title"] = nui.plain_text(presets.title) if presets is not None else ""
		values["presets"] = ([{"name": nui.plain_text(line.name)} for line in presets.listBox.entries]
		                     if presets is not None else [])
		changed = dict((key, value) for key, value in values.items() if self._state.get(key) != value)
		if changed:
			self.nui_set(**changed)

	# --- the fields (the rows' values, the search filter, the preset name) --------------

	def _read_field(self, field_id):
		board = self.nui_board()
		return board.get_value(field_id) if board is not None and board.is_visible() else None

	def _on_field(self, field, what):
		self._sync()
		board = self.nui_board()
		if board is None or not board.is_visible():
			return
		if what == "text":
			board.set_value(field.field_id, field.text, caret="end")
		elif what == "focus":
			board.focus(field.field_id)

	def _row_typed(self, index, value):
		"""A typed value: legacy's value handler (its IME update, after the
		edit line's own typing)."""
		row = self._row(index)
		row.valueEditLine.typed(value)
		row.ApplyValue(row.valueEditLine.text)

	# --- the search list and the saved configurations ---------------------------------

	def _picker_select(self, index):
		picker = self.attributeSearchWindow
		if picker is not None and picker.listBox is not None:
			picker.listBox.SelectIndex(index)

	def _picker_accept(self):
		picker = self.attributeSearchWindow
		if picker is not None and picker.shown:
			picker._SearchListWindow__OnAccept()

	def _picker_cancel(self):
		picker = self.attributeSearchWindow
		if picker is not None and picker.shown:
			picker._SearchListWindow__OnCancel()

	def _picker_filter(self, value):
		picker = self.attributeSearchWindow
		if picker is None or not picker.shown:
			return
		picker.searchEditLine.typed(value)
		picker._SearchListWindow__RefreshListBox()

	def _preset(self, index, action):
		presets = self.configurationSaveWindow
		if presets is None or not 0 <= index < len(presets.listBox.entries):
			return
		line = presets.listBox.entries[index]
		if action == "load":
			line.load()
		else:
			line.delete()

	def _preset_save(self):
		presets = self.configurationSaveWindow
		if presets is not None:
			presets.saveButton.click()

	def _preset_close(self):
		presets = self.configurationSaveWindow
		if presets is not None:
			presets.Close()

	def _preset_typed(self, value):
		presets = self.configurationSaveWindow
		if presets is not None:
			presets.nameEditLine.typed(value)

	# --- what NovaUI changes -----------------------------------------------------------

	def _restore_board(self, board):
		nui_facade.Facade._restore_board(self, board)
		for row in list(self.attrDict.values()) + list(self.rareAttrDict.values()):
			board.set_value(row.valueEditLine.field_id, row.valueEditLine.text, caret="end")
