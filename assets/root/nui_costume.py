"""NovaUI costume window (nui/windows/costume/costume.rml; P14 spec 6.2, Wave 6).

The NovaUI inventory (nui_inventory) makes CostumeWindow below where the
legacy inventory makes uiInventory.CostumeWindow: a subclass of it whose
uiscript loader (_CostumeWindow__LoadWindow) puts a nui_slots.SlotWindowProxy
over the costume group of the wear table (nui_limits) where the legacy slot
window was, with the inventory's handlers (OverInItem, OverOutItem,
UseItemSlot, SelectEmptySlot, SelectItemSlot) as legacy binds them, so
equipping, unequipping and every drag is the inventory's legacy code. The
group is the legacy uiscript's cells (uiscript/costumewindow.py
CostumeSlot): the costume body and hair, and in the foundation's table the
costume sash (NOVA-20), the weapon costume (NOVA-21), the sash costume
(OLD's COSTUME_SASH2 wings), the aura costume (NOVA-23) and the buffi's
costume body, hair and weapon costume (NOVA-38: has_companion, the sheet's
companion block, legacy's buffi panel). An empty sash,
weapon, sash costume or aura cell carries its place's mark (COSTUME_MARKS),
as the inventory's wear cells do. Legacy refreshes COSTUME_SLOT_COUNT cells
from the costume body and the aura cell (uiinventory.py RefreshCostumeSlot);
a cell of the group it would not refresh (none in either table today) is
filled from the inventory at each refresh.

Wave 6 (NOVA-22, 23): the loader also puts a nui_proxies.ToggleButtonProxy
in each of legacy's switch lists (costumeButtonList, hairButtonList,
weaponButtonList, sashButtonList, wingButtonList; the uiscript's
Activate*_ON_OFF) and binds them as legacy does, so the show and hide
requests ("/set_is_show_* 0|1"), ResetSlider and the aura panel's toggle
are legacy's code; the board shows each proxy's down state (show_body,
show_hair, show_weapon, show_sash, wing_down) and a left press on a switch
is the proxy's click(). Legacy's aura panel (__CreateAuraWingPanel) is made
on proxies: a nui_proxies.WindowProxy whose shown state is wing_open and a
nui_form_proxies.CheckBoxProxy per aura flag the player module has, bound
to legacy's __SendAuraWingToggle ("/aura_wing <flags>"); the board shows
them as wing_rows and a left press on a row is that box's click().

The board exists only while the window shows (kept hidden after its first
open, nui_hud.KeptBoard); at each open it is placed beside the inventory's
left edge, top in line (legacy's SCREEN_WIDTH - 175 - 216), beyond the
inventory's shortcut rail while it has one, and it moves alone after. The
modern skin stands a figure between the slots: an image whose path the
model carries, the male or the female one by the character's race
(figure_for_race). No Python runs per frame (OnUpdate is None; legacy's
window has none either)."""

import localeInfo
import player
import ui
import uiInventory

import nui
import nui_form_proxies
import nui_hud
import nui_limits
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/costume/costume.rml"
KEY = "costume"

# The figures (content images, nui/figures/; the model carries the path).
FIGURE_MALE = "/nui/figures/costume-male.png"
FIGURE_FEMALE = "/nui/figures/costume-female.png"
# The female races (playerSettingModule: RACE_ASSASSIN_W 1, RACE_SHAMAN_W 3,
# RACE_WARRIOR_W 4, RACE_SURA_W 6; 0, 2, 5 and 7 are male).
FEMALE_RACES = (1, 3, 4, 6)


# Wave 6: the mark an empty costume place shows (a glyph of
# components/glyph.rcss, which classic hides), as nui_inventory.WEAR_MARKS:
# the weapon costume's sword, the costume sash's pentagon and the aura's
# ring (the stage's frames before Wave 6), and the sash costume's wings
# drawn as the closest glyph, chevron-down (no wing glyph exists).
COSTUME_MARKS = {"costume_weapon": "sword", "costume_sash": "pentagon", "costume_aura": "ring",
                 "costume_sash2": "chevron-down"}

# The switches (uiscript costumewindow.py Activate*_ON_OFF): the board's part
# name, legacy's list of the switch and the model key of its down state.
SWITCHES = (("body", "costumeButtonList", "show_body"), ("hair", "hairButtonList", "show_hair"),
            ("weapon", "weaponButtonList", "show_weapon"), ("sash", "sashButtonList", "show_sash"),
            ("wing", "wingButtonList", "wing_down"))

# The aura panel's rows: the key the board picks its label by
# (@game.AURA_WING_SHOW_*) for each of legacy's AURA_WING_FLAGS labels.
WING_KEYS = {"AURA_WING_SHOW_WING": "wing", "AURA_WING_SHOW_AURA": "aura", "AURA_WING_SHOW_EFFECT": "effect"}


def costume_marks(name, kind):
	"""A costume cell's marks: [the place's glyph name] while it is empty
	and has one, else []."""
	mark = COSTUME_MARKS.get(name)
	return [mark] if mark and not kind else []


class _WingPanelProxy(nui_proxies.WindowProxy):
	"""The aura panel (legacy's ui.Board): a WindowProxy that also takes
	legacy's AddFlag (recorded; the document lays itself out)."""

	def __init__(self, on_show=None):
		nui_proxies.WindowProxy.__init__(self, on_show)
		self.shown = False
		self.flags = set()

	def AddFlag(self, flag):
		self.flags.add(str(flag))


def figure_for_race(race):
	"""The costume window's figure for a race: the female one for a female
	race, else the male one."""
	return FIGURE_FEMALE if race in FEMALE_RACES else FIGURE_MALE


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

	@nui.on("cos_switch")
	def on_switch(self, part, button):
		self.raise_for(button)
		if button == 0:
			self._owner.nui_switch(str(part))

	@nui.on("cos_wing_row")
	def on_wing_row(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.nui_wing_row(int(index))


class CostumeWindow(uiInventory.CostumeWindow):
	"""uiInventory.CostumeWindow on NovaUI (the NovaUI inventory's wndCostume)."""

	NUI_FACADE = True
	# No per-frame Python: legacy's window has no OnUpdate either.
	OnUpdate = None

	def __init__(self, wndInventory):
		nui_hud.take_over(KEY, self)
		self._nui_discarded = False
		self._limits = nui_limits.current()
		self._slots = nui_limits.wear_group("costume", self._limits)
		self._events = None
		self._wing_boxes = []
		self._state = {
			"table": self._limits.WEAR_TABLE_ID,
			"slots": [dict(nui_slots.empty_cell(i), name=slot.name, marks=costume_marks(slot.name, ""))
			          for i, slot in enumerate(self._slots)],
			"has_companion": any(slot.name.startswith("buffi_") for slot in self._slots),
			# P15 F-2 (nui_slots.ATTACH_RIGHT; the grid's nui-attach-right).
			"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
			# V-2: the wear grid, none while the board is kept hidden.
			"wear_on": [1],
			# The figure for the character's gender.
			"figure": figure_for_race(player.GetRace()),
			# Wave 6: the switches' down states (the proxies' `down`), the
			# aura panel's shown state and its rows.
			"show_body": False, "show_hair": False, "show_weapon": False, "show_sash": False, "wing_down": False,
			"wing_open": False,
			"wing_rows": [],
		}
		# V-2 (P15 spec 8.1): kept, hidden, after its first open.
		self.demand = (nui_hud.KeptBoard(self._make_board, self._restore_board, empty=self._empty_board)
		               if nui_hud.has_engine_3b() else None)
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

	def _empty_board(self, board):
		"""V-2: the hidden kept board holds no wear cell and no aura row."""
		board.set(wear_on=[], wing_rows=[])

	def _named(self, cells, states=None):
		marked = nui_slots.with_states(cells, states or {})
		for cell, slot in zip(marked, self._slots):
			cell["name"] = slot.name
			cell["marks"] = costume_marks(slot.name, cell.get("kind"))
		return marked

	def _on_slots(self, cells):
		self._set(slots=self._named(cells, self._events.states if self._events is not None else {}))

	def _on_states(self, states, picked):
		self._set(slots=self._named(self.wndEquip.cells(), states))

	def _place_beside(self):
		"""Beside the inventory's left edge, top in line, as legacy creates its
		window (a pixel over the edge: SCREEN_WIDTH - 175 - 216 against the
		inventory's SCREEN_WIDTH - 176). When both open together (the
		inventory's Show reopens it), the inventory's new board has no layout
		yet and an empty box, so its origin is the place it opens at; docked
		instead when neither is known. The inventory's shortcut rail, while
		it has entries, stays clear (rail_reach)."""
		board = self.demand.board() if self.demand is not None else None
		other = self.wndInventory.board() if hasattr(self.wndInventory, "board") else None
		if board is None or other is None:
			return
		origin = getattr(self.wndInventory, "board_origin", None)
		origin = origin() if origin is not None else None
		reach = getattr(self.wndInventory, "rail_reach", None)
		reach = reach() if reach is not None else 0.0
		if origin is not None:
			board.set_position(origin[0] + 1.0 - reach, origin[1], origin=(1.0, 0.0))
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

		## ActivateButton (Wave 6, NOVA-22 and 23): legacy's switches, the
		## uiscript's toggle buttons, are proxies; legacy's binding.
		for part, attribute, key in SWITCHES:
			getattr(self, attribute).append(nui_proxies.ToggleButtonProxy(self._switch_changed(key)))
		for buttons, event in ((self.costumeButtonList, self.OnCostumeActivateButton),
				(self.hairButtonList, self.OnHairActivateButton),
				(self.weaponButtonList, self.OnWeaponActivateButton),
				(self.sashButtonList, self.OnSashActivateButton),
				(self.wingButtonList, self._CostumeWindow__ToggleAuraWingPanel)):
			for button in buttons:
				button.SetToggleUpEvent(ui.__mem_func__(event))
				button.SetToggleDownEvent(ui.__mem_func__(event))

		self.wndEquip = wndEquip
		self._events = nui_slots.LegacySlotEvents(wndEquip, on_states=self._on_states)

	def _switch_changed(self, key):
		"""A switch proxy's on_change: its down state into the model key."""
		def changed(proxy):
			self._set(**{key: bool(proxy.down)})
		return changed

	def nui_switch(self, part):
		"""A left press on a switch: its proxy's click() (CToggleButton's
		press), which runs legacy's handler."""
		for name, attribute, _ in SWITCHES:
			if name == part:
				for button in list(getattr(self, attribute)):
					button.click()

	# --- the aura panel (uiinventory.py __CreateAuraWingPanel, on proxies) -----------

	def _CostumeWindow__CreateAuraWingPanel(self):
		"""Legacy's body on proxies: the board a _WingPanelProxy (its shown
		state is wing_open), a CheckBoxProxy per flag the player module has,
		in legacy's order, with its label and both events on legacy's
		__SendAuraWingToggle; their states are wing_rows."""
		flags = [(getattr(player, flag), label) for (flag, label) in self.AURA_WING_FLAGS if hasattr(player, flag)]
		panel = _WingPanelProxy(self._on_wing_shown)
		panel.SetParent(self)
		panel.SetSize(150, 20 + 20 * len(flags))
		panel.AddFlag("float")
		panel.Show()

		self._wing_boxes = []
		checks = []
		for (index, (flag, label)) in enumerate(flags):
			checkBox = nui_form_proxies.CheckBoxProxy(self._on_wing_check)
			self._wing_boxes.append((WING_KEYS.get(label, label.lower()), checkBox))
			checkBox.SetParent(panel)
			checkBox.SetPosition(15, 12 + 20 * index)
			checkBox.SetTextInfo(getattr(localeInfo, label))
			event = lambda flag=flag: self._CostumeWindow__SendAuraWingToggle(flag)
			checkBox.SetEvent(event, "ON_CHECK")
			checkBox.SetEvent(event, "ON_UNCHECK")
			checkBox.Show()
			checks.append((flag, checkBox))

		self.auraWingChecks = checks
		self.auraWingPanel = panel
		self._on_wing_check(None)

	def _on_wing_shown(self, shown):
		self._set(wing_open=bool(shown))

	def _on_wing_check(self, box):
		self._set(wing_rows=[{"key": key, "checked": bool(box.checked)} for key, box in self._wing_boxes])

	def nui_wing_row(self, index):
		"""A left press on an aura panel row: its check box's click()
		(ui.CheckBox's OnMouseLeftButtonUp), which runs legacy's event."""
		checks = list(self.auraWingChecks)
		if self.auraWingPanel is not None and self.auraWingPanel.IsShow() and 0 <= index < len(checks):
			checks[index][1].click()

	def RefreshCostumeSlot(self):
		"""Legacy's refresh, after the group's cells it never refreshes are
		filled from the inventory (P14 spec 6.2). Legacy refreshes
		COSTUME_SLOT_COUNT cells from the costume body and the aura cell
		(uiinventory.py RefreshCostumeSlot, CostumeAuraSlot()): every cell of
		either table's group, so the fill sets none today."""
		start = self._limits.COSTUME_SLOT_START
		refreshed = set(range(start, start + self._limits.COSTUME_SLOT_COUNT))
		aura = getattr(uiInventory, "CostumeAuraSlot", None)
		if aura is not None:
			refreshed.add(aura())
		for slot in self._slots:
			if slot.cell not in refreshed:
				self.wndEquip.SetItemSlot(slot.cell, player.GetItemIndex(slot.cell), 0)
		uiInventory.CostumeWindow.RefreshCostumeSlot(self)

	def Show(self):
		figure = figure_for_race(player.GetRace())
		if figure != self._state["figure"]:
			self._set(figure=figure)
		if self.demand is not None:
			self.demand.show()
		uiInventory.CostumeWindow.Show(self)
		self._place_beside()

	def Hide(self):
		"""Legacy's Hide, then the board's; ui.Window's __init__ may call it
		before this class's __init__ ran (getattr)."""
		uiInventory.CostumeWindow.Hide(self)
		events = getattr(self, "_events", None)
		if events is not None:
			events.reset()
		demand = getattr(self, "demand", None)
		if demand is not None:
			demand.hide()

	def SetTop(self):
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.bring_to_front()
		nui_hud.note_raise(self)
		uiInventory.CostumeWindow.SetTop(self)

	def Destroy(self):
		self.nui_discard()
		uiInventory.CostumeWindow.Destroy(self)
