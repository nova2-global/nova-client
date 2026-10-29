"""NovaUI inventory (nui/windows/inventory/inventory.rml; P14 spec 6.1).

While the inventory flag is on, Interface.__MakeWindows makes InventoryWindow
below through nui_windows.make() instead of uiInventory.InventoryWindow. It
is a subclass of the legacy class (P14 spec D25): its constructor is
legacy's, whose uiscript loader it replaces with proxies standing where the
legacy widgets were (nui_slots.SlotWindowProxy for the bag and the wear
cells, nui_proxies for the money, the buttons and the tabs), bound to the
legacy handlers as legacy's loader bound its widgets. So every flow, packet,
question and rule (pick and place, use, move, split, sell, buy, links, the
quickslot, refine, attach, detach, money, the dragon soul refine window) is
the legacy class's own code; the proxies record what it tells them and the
board shows it. Legacy's ScriptWindow stays underneath, a 0 x 0 window in
the UI layer, so IsShow, the Escape chain and SetTop are legacy's.

The board exists only while the inventory shows (nui_hud.OnDemand); a
refresh while hidden runs legacy's refresh on the proxies (its auto potion
calls included, D15) and the board takes the proxies' last state at its next
show. The cell events reach the legacy handlers through
nui_slots.LegacySlotEvents, with CSlotWindow's and CGridSlotWindow's rules
(the owner of a covered cell, the drop target, the footprint's states). The
costume and belt windows are nui_costume and nui_belt_inventory. Every count
comes from nui_limits.current().

The modern skin's paper doll shows a figure, an image whose path the model
carries (figure_for_race: the race's figure, today the knight for every
race), and a stats row (attack, defence, magic attack, as the character
window sums them, refreshed with legacy's RefreshStatus). The shortcut rail
on the window's left edge shows the entries features register here
(register_shortcut): an id, a glyph, a tooltip key, an enabled flag, a
"soon" flag (a feature still to come) and a badge each; a press on one
calls its callback. With none registered there is no rail. When the game's
interface binds the window (BindInterfaceClass), the reviewed board's five
entries are registered (register_board_shortcuts): the offline shop,
ranking, events and achievements as features to come, and the guide, which
opens the help window. The rail's fold button hides its entries for the
rest of the session."""

import app
import constInfo
import player
import ui
import uiAttachMetin
import uiInventory
import uiPickMoney
import uiRefine
import wndMgr

import nui
import nui_hud
import nui_limits
import nui_proxies
import nui_slots
import nui_windows

DOCUMENT = "nui/windows/inventory/inventory.rml"
KEY = "inventory"

# The paper doll's figures (content images, nui/figures/; the controller
# passes the path, so no markup names it).
FIGURE_KNIGHT = "/nui/figures/knight.png"


def figure_for_race(race):
	"""The paper doll's figure for a race (playerSettingModule's RACE_*, 0 to
	7). Every race shows the knight today; a race's own figure (a female
	one) goes here when it exists."""
	return FIGURE_KNIGHT


# --- The shortcut rail ------------------------------------------------------------
# Entries in registration order ({"id", "glyph", "tip", "enabled"}, the
# board's rail model) and their callbacks. Module state, so a feature may
# register before the inventory exists; the shown inventory follows each
# change.

# The glyph names components/glyph.rcss draws.
GLYPHS = ("close", "plus", "minus", "chevron-up", "chevron-down", "chevron-left", "chevron-right", "send", "log",
          "chat", "whisper", "character", "inventory", "community", "system", "map", "gift", "gem", "shop", "heal",
          "leave", "mouse-move", "mouse-attack", "mouse-auto", "mouse-camera", "mouse-skill", "home", "coin", "lock",
          "stall", "ranking", "events", "achievements", "guide")
# The rail's reach left of the window, in dp (its board and the gap to the
# window), which the costume window keeps clear while the rail shows.
RAIL_REACH_DP = 56.0

_shortcuts = []
_shortcut_callbacks = {}
# The fold button's state, kept for the session (a list, so the module's
# functions change it in place).
_rail_folded = [False]


def _is_name(text):
	return (bool(text) and text[0].isalpha() and all(c.isalnum() or c == "_" for c in text)
	        and all(ord(c) < 128 for c in text))


def register_shortcut(entry_id, glyph, tip, callback, enabled=True, soon=False):
	"""Adds the rail's entry entry_id (letters, digits and _, starting with a
	letter), or replaces it in place (keeping its badge): a button with the
	glyph (one of GLYPHS) and the tooltip tip (a locale key, "@ui.KEY" or
	"@game.KEY"), pressable while enabled. A left press on it calls
	callback(). A soon entry is a feature still to come: its hint says so,
	it takes no press, and its callback may be None."""
	if not _is_name(entry_id):
		raise ValueError("shortcut id %r: letters, digits and _, starting with a letter" % (entry_id,))
	if glyph not in GLYPHS:
		raise ValueError("shortcut %s: no glyph %r" % (entry_id, glyph))
	if not (tip.startswith("@ui.") or tip.startswith("@game.")) or not _is_name(tip.split(".", 1)[1]):
		raise ValueError("shortcut %s: the tooltip is a locale key (@ui.KEY or @game.KEY), not %r" % (entry_id, tip))
	if not callable(callback) and not (soon and callback is None):
		raise ValueError("shortcut %s: the callback is not callable" % entry_id)
	entry = {"id": entry_id, "glyph": glyph, "tip": tip, "enabled": bool(enabled), "soon": bool(soon), "badge": ""}
	for index, old in enumerate(_shortcuts):
		if old["id"] == entry_id:
			entry["badge"] = old["badge"]
			_shortcuts[index] = entry
			break
	else:
		_shortcuts.append(entry)
	_shortcut_callbacks[entry_id] = callback
	_publish_shortcuts()


def unregister_shortcut(entry_id):
	"""Takes the entry off the rail (nothing when it is not there)."""
	_shortcuts[:] = [entry for entry in _shortcuts if entry["id"] != entry_id]
	_shortcut_callbacks.pop(entry_id, None)
	_publish_shortcuts()


def set_shortcut_enabled(entry_id, enabled):
	"""Enables or disables the entry (a disabled button takes no press)."""
	for entry in _shortcuts:
		if entry["id"] == entry_id:
			entry["enabled"] = bool(enabled)
	_publish_shortcuts()


def set_shortcut_badge(entry_id, count):
	"""Puts a count on the entry's badge (0 or less: no badge; over 99:
	"99+")."""
	count = int(count)
	badge = "" if count <= 0 else ("99+" if count > 99 else "%d" % count)
	for entry in _shortcuts:
		if entry["id"] == entry_id:
			entry["badge"] = badge
	_publish_shortcuts()


def shortcuts():
	"""The registered entries, in rail order (copies)."""
	return [dict(entry) for entry in _shortcuts]


def press_shortcut(entry_id):
	"""What a left press on the entry does: its callback, while it is
	registered, enabled and not to come. True when it ran."""
	for entry in _shortcuts:
		if entry["id"] == entry_id and entry["enabled"] and not entry["soon"]:
			_shortcut_callbacks[entry_id]()
			return True
	return False


def rail_folded():
	"""Whether the fold button has hidden the rail's entries."""
	return _rail_folded[0]


def set_rail_folded(folded):
	"""Hides the rail's entries (True) or shows them (False), for the
	session."""
	_rail_folded[0] = bool(folded)
	_publish_shortcuts()


def _publish_shortcuts():
	window = nui_hud.current(KEY)
	refresh = getattr(window, "_refresh_rail", None)
	if refresh is not None:
		refresh()


# The reviewed inventory board's rail: (id, glyph, tooltip key, soon). The
# offline shop, ranking, events and achievements are features to come; the
# guide opens the help window.
BOARD_SHORTCUTS = (
	("offline_shop", "stall", "@ui.NUI_RAIL_OFFLINE_SHOP", True),
	("ranking", "ranking", "@ui.NUI_RAIL_RANKING", True),
	("events", "events", "@ui.NUI_RAIL_EVENTS", True),
	("achievements", "achievements", "@ui.NUI_RAIL_ACHIEVEMENTS", True),
	("guide", "guide", "@ui.NUI_RAIL_GUIDE", False),
)


def _open_guide():
	"""The guide entry: the help window, through the interface that bound
	the shown inventory (Interface.OpenHelpWindow)."""
	window = nui_hud.current(KEY)
	interface = getattr(window, "interface", None)
	if interface is not None:
		interface.OpenHelpWindow()


def register_board_shortcuts():
	"""Registers the board's five entries, each one only while no feature
	has registered its id (a feature's own entry stays)."""
	taken = set(entry["id"] for entry in _shortcuts)
	for entry_id, glyph, tip, soon in BOARD_SHORTCUTS:
		if entry_id not in taken:
			register_shortcut(entry_id, glyph, tip, None if soon else _open_guide, soon=soon)


def _span(low, high):
	"""A minimum and a maximum as the character window writes them."""
	return "%d" % low if low == high else "%d-%d" % (low, high)


class _InventoryBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The inventory's document; its events go to its window. A press on it
	raises the window, as legacy's window manager does (RaisesOnPress)."""

	DOCUMENT = DOCUMENT
	MODEL = "inventory"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	# --- the bag and the wear cells: the legacy slot windows' events ---------------

	@nui.on("bag_press")
	def on_bag_press(self, index, button):
		self.raise_for(button)
		self._owner._bag_events.press(int(index), button)

	@nui.on("bag_release")
	def on_bag_release(self, index, button):
		self._owner._bag_events.release(int(index), button)

	@nui.on("bag_use")
	def on_bag_use(self, index):
		self._owner._bag_events.use(int(index))

	@nui.on("bag_over")
	def on_bag_over(self, index):
		self._owner._bag_events.over(int(index))

	@nui.on("bag_out")
	def on_bag_out(self, index):
		self._owner._bag_events.out(int(index))

	@nui.on("bag_drop")
	def on_bag_drop(self, index):
		self._owner._bag_events.drop(int(index))

	@nui.on("wear_press")
	def on_wear_press(self, index, button):
		self.raise_for(button)
		self._owner._wear_events.press(int(index), button)

	@nui.on("wear_release")
	def on_wear_release(self, index, button):
		self._owner._wear_events.release(int(index), button)

	@nui.on("wear_use")
	def on_wear_use(self, index):
		self._owner._wear_events.use(int(index))

	@nui.on("wear_over")
	def on_wear_over(self, index):
		self._owner._wear_events.over(int(index))

	@nui.on("wear_out")
	def on_wear_out(self, index):
		self._owner._wear_events.out(int(index))

	@nui.on("wear_drop")
	def on_wear_drop(self, index):
		self._owner._wear_events.drop(int(index))

	# --- the controls: legacy's buttons, on a left mousedown ---------------------

	@nui.on("page_press")
	def on_page_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_page(int(index))

	@nui.on("money_press")
	def on_money_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.wndMoneySlot.click()

	@nui.on("costume_press")
	def on_costume_press(self, button):
		self.raise_for(button)
		if button == 0 and self._owner.costumeButton:
			self._owner.costumeButton.click()

	@nui.on("dss_press")
	def on_dss_press(self, button):
		self.raise_for(button)
		if button == 0 and self._owner.DSSButton:
			self._owner.DSSButton.click()

	@nui.on("mall_press")
	def on_mall_press(self, button):
		self.raise_for(button)
		if button == 0 and self._owner.mallButton:
			self._owner.mallButton.click()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.Close()

	@nui.on("rail_press")
	def on_rail_press(self, entry_id, button):
		self.raise_for(button)
		if button == 0:
			press_shortcut(str(entry_id))

	@nui.on("rail_fold")
	def on_rail_fold(self, button):
		self.raise_for(button)
		if button == 0:
			set_rail_folded(not rail_folded())


class InventoryWindow(uiInventory.InventoryWindow):
	"""uiInventory.InventoryWindow on NovaUI (Interface.wndInventory)."""

	NUI_FACADE = True

	def __init__(self):
		nui_hud.take_over(KEY, self)
		self._nui_discarded = False
		self._limits = nui_limits.current()
		self._state = self._empty_state()
		self._place = None
		self._opening = False  # Show() is making the board (board_origin)
		self._bag_events = None
		self._wear_events = None
		self.loaded = False
		self.demand = None
		if nui_hud.has_engine_3b():
			# V-2 (P15 spec 8.1): the board is kept, hidden, after its first open.
			self.demand = nui_hud.KeptBoard(self._make_board, self._restore_board, self._keep_board, self._empty_board)
		try:
			uiInventory.InventoryWindow.__init__(self)
			if self.demand is not None:
				self.loaded = self.demand.probe()
		except Exception:
			self.nui_discard()
			raise

	# --- make()'s protocol ------------------------------------------------------------

	def nui_ready(self):
		return self.loaded and self.demand is not None and nui_hud.has_engine_3b()

	def nui_discard(self):
		self._nui_discarded = True
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		for name in ("wndBelt", "wndCostume"):
			window = getattr(self, name, None)
			discard = getattr(window, "nui_discard", None)
			if discard is not None:
				discard()
		nui_hud.forget(KEY, self)

	# --- the model ------------------------------------------------------------------

	def _empty_state(self):
		limits = self._limits
		return {
			"table": limits.WEAR_TABLE_ID,
			"pages": nui_limits.pages(limits),
			"page": 0,
			"bag": [nui_slots.empty_cell(i) for i in range(limits.INVENTORY_PAGE_SIZE)],
			"bag_cols": limits.INVENTORY_COLUMNS,
			"wear": [dict(nui_slots.empty_cell(i), name=slot.name)
			         for i, slot in enumerate(nui_limits.wear_group("equipment", limits))],
			"money": "",
			"money_value": 0,
			"dss_active": False,
			"has_costume": False,
			"has_dss": False,
			"has_mall": False,
			# The board is placed from Python (inv--placed: the sheet's
			# right and bottom give way to the placement's left and top).
			"placed": False,
			# P14b: the bag's is-attaching (nui_slots.LegacySlotEvents).
			"bag_attaching": False,
			# P15 F-2: the grids take a right press while something is attached
			# (nui-attach-right) only while nui_slots.ATTACH_RIGHT holds.
			"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
			# V-2: the wear places, the tabs and the bag, each a list of one
			# entry while the board shows and none while it is kept hidden.
			"wear_on": [1], "tabs_on": [1], "bag_on": [1],
			# The paper doll's figure, the stats row (RefreshStatus) and the
			# shortcut rail.
			"figure": figure_for_race(player.GetRace()),
			"stat_attack": "", "stat_defence": "", "stat_magic": "",
			"rail": shortcuts(), "rail_folded": rail_folded(),
		}

	def _set(self, **values):
		self._state.update(values)
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.set(**values)

	def _make_board(self):
		return _InventoryBoard(self, self._state)

	def _restore_board(self, board):
		board.set(**self._state)
		if self._place is not None:
			self._placed(board)
			board.set_position(self._place[0], self._place[1])
		else:
			self._default_place(board)

	def _placed(self, board):
		"""A placement writes only the body's left and top (NuiRuntime.h), so
		the sheet's right: 0 and bottom: 37dp must give way, or the board
		stretches between its placed top and that bottom, and every later
		placement, from the stretched height, moves it higher."""
		self._state["placed"] = True
		board.set(placed=True)

	def _empty_board(self, board):
		"""V-2: the hidden kept board holds no wear place, tab, bag cell or
		rail entry (RmlUi updates every element of a loaded document each
		frame); _restore_board sets the lists again at the next show."""
		board.set(wear_on=[], tabs_on=[], bag_on=[], rail=[])

	def _refresh_rail(self):
		"""The registered shortcuts and the fold, to the board while it shows
		(a kept board takes them at its next show)."""
		self._state["rail"] = shortcuts()
		self._state["rail_folded"] = rail_folded()
		if self.demand is not None and self.demand.is_shown():
			self.demand.board().set(rail=self._state["rail"], rail_folded=self._state["rail_folded"])

	def BindInterfaceClass(self, interface):
		"""Legacy's binding, then the board's rail entries."""
		uiInventory.InventoryWindow.BindInterfaceClass(self, interface)
		register_board_shortcuts()

	def rail_reach(self):
		"""How far the shortcut rail reaches left of the window, in dp (0
		without one): the costume window opens beyond it."""
		return RAIL_REACH_DP if self._state["rail"] else 0.0

	def _keep_board(self, board):
		box = board.element_box("")
		if box:
			scale = nui.get_scale() or 1.0
			self._place = (box[0] / scale, box[1] / scale)

	def _default_place(self, board):
		"""Legacy's place: the screen's right edge, above the taskbar (37 px
		in legacy; the NovaUI taskbar's own height when it is the one shown,
		TaskBar.GetBarHeight). The sheet's right and bottom offsets hold it
		otherwise."""
		interface = getattr(self, "interface", None)
		taskbar = getattr(interface, "wndTaskBar", None)
		height = getattr(taskbar, "GetBarHeight", None) if getattr(taskbar, "NUI_FACADE", False) else None
		if height is None:
			return
		scale = nui.get_scale() or 1.0
		bar = float(height()) / scale
		self._placed(board)
		board.set_position(wndMgr.GetScreenWidth() / scale, wndMgr.GetScreenHeight() / scale - bar, origin=(1.0, 1.0))

	def _show_board(self):
		if self.demand is not None:
			self.demand.show()

	def _hide_board(self):
		# The board's cells hear no mouseout as it goes (nui_slots.LegacySlotEvents.reset).
		for events in (self._bag_events, self._wear_events):
			if events is not None:
				events.reset()
		if self.demand is not None:
			self.demand.hide()

	def board(self):
		"""The board while shown, else None (the belt docks to it)."""
		return self.demand.board() if self.demand is not None else None

	def board_origin(self):
		"""The board's top left in dp. While Show() makes the board (legacy's
		Show reopens the costume window in that call), the placement has not
		resolved yet and the box is the unplaced one, at the screen's corner:
		then the place it opens at, its kept place (None the first time, when
		the costume window cannot be open). Otherwise its laid-out box, or the
		kept place while it has none."""
		if self._opening:
			return self._place
		board = self.board()
		box = board.element_box("") if board is not None else None
		if box and box[2] > 0 and box[3] > 0:
			scale = nui.get_scale() or 1.0
			return box[0] / scale, box[1] / scale
		return self._place

	# --- the proxies' callbacks ---------------------------------------------------------

	def _bag_position(self, local):
		return self._InventoryWindow__InventoryLocalSlotPosToGlobalSlotPos(local)

	def _on_bag(self, cells):
		events = self._bag_events
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		self._set(bag=nui_slots.with_states(cells, states, picked))

	def _on_bag_states(self, states, picked):
		self._set(bag=nui_slots.with_states(self.wndItem.cells(), states, picked))

	def _on_bag_attaching(self, flag):
		self._set(bag_attaching=flag)

	def _named(self, cells, states=None, picked=-1):
		marked = nui_slots.with_states(cells, states or {}, picked)
		for cell, slot in zip(marked, self._wear_slots):
			cell["name"] = slot.name
		return marked

	def _on_wear(self, cells):
		events = self._wear_events
		self._set(wear=self._named(cells, events.states if events is not None else {}))

	def _on_wear_states(self, states, picked):
		self._set(wear=self._named(self.wndEquip.cells(), states))

	def _on_money(self, text):
		self._set(money=nui.plain_text(text), money_value=int(player.GetElk()))

	def _press_page(self, index):
		"""A tab: the page's button, which a press on the page shown does
		not reach (CRadioButton ignores a press on the button that is down)."""
		if not (0 <= index < len(self.inventoryTab)) or index == self.inventoryPageIndex:
			return
		self.inventoryTab[index].click()

	# --- the loader (uiinventory.py:281-396, on proxies) ------------------------------

	def _InventoryWindow__LoadWindow(self):
		if self.isLoaded == 1:
			return
		self.isLoaded = 1
		# The uiscript's style (inventorywindow.py: "movable", "float"): a
		# float window is the one SetTop raises (CWindow::SetTop).
		self.AddFlag("movable")
		self.AddFlag("float")
		limits = self._limits

		wndItem = nui_slots.SlotWindowProxy(range(limits.INVENTORY_PAGE_SIZE), self._on_bag,
		                                    cols=limits.INVENTORY_COLUMNS, rows=limits.INVENTORY_ROWS,
		                                    positions=self._bag_position)
		self._wear_slots = nui_limits.wear_group("equipment", limits)
		wndEquip = nui_slots.SlotWindowProxy([slot.cell for slot in self._wear_slots], self._on_wear)
		self.wndMoney = nui_proxies.TextProxy(self._on_money)
		self.wndMoneySlot = nui_proxies.ButtonProxy()
		self.mallButton = nui_proxies.ButtonProxy()
		self.DSSButton = nui_proxies.ButtonProxy()
		self.costumeButton = nui_proxies.ButtonProxy() if app.ENABLE_COSTUME_SYSTEM else 0
		self.inventoryTab = [nui_proxies.ButtonProxy() for _ in range(limits.INVENTORY_PAGE_COUNT)]
		self.equipmentTab = [nui_proxies.ButtonProxy(), nui_proxies.ButtonProxy()]

		# Belt Inventory Window
		self.wndBelt = None
		if app.ENABLE_NEW_EQUIPMENT_SYSTEM:
			import nui_belt_inventory
			self.wndBelt = nui_belt_inventory.BeltInventoryWindow(self)

		## Item
		wndItem.SetSelectEmptySlotEvent(ui.__mem_func__(self.SelectEmptySlot))
		wndItem.SetSelectItemSlotEvent(ui.__mem_func__(self.SelectItemSlot))
		wndItem.SetUnselectItemSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndItem.SetUseSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndItem.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		wndItem.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))

		## Equipment
		wndEquip.SetSelectEmptySlotEvent(ui.__mem_func__(self.SelectEmptySlot))
		wndEquip.SetSelectItemSlotEvent(ui.__mem_func__(self.SelectItemSlot))
		wndEquip.SetUnselectItemSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndEquip.SetUseSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndEquip.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		wndEquip.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))

		## PickMoneyDialog (the dialog kit's facade while the dialogs flag is on)
		dlgPickMoney = uiPickMoney.PickMoneyDialog()
		dlgPickMoney.LoadDialog()
		dlgPickMoney.Hide()

		## RefineDialog
		self.refineDialog = nui_windows.make("refine", uiRefine.RefineDialog, "nui_refine.RefineDialog")
		self.refineDialog.Hide()

		## AttachMetinDialog
		self.attachMetinDialog = nui_windows.make("attach-metin", uiAttachMetin.AttachMetinDialog,
		                                          "nui_attach_metin.AttachMetinDialog")
		self.attachMetinDialog.Hide()

		## MoneySlot
		self.wndMoneySlot.SetEvent(ui.__mem_func__(self.OpenPickMoneyDialog))

		for page, tab in enumerate(self.inventoryTab):
			tab.SetEvent(lambda arg=page: self.SetInventoryPage(arg))
		self.inventoryTab[0].Down()

		self.equipmentTab[0].SetEvent(lambda arg=0: self.SetEquipmentPage(arg))
		self.equipmentTab[1].SetEvent(lambda arg=1: self.SetEquipmentPage(arg))
		self.equipmentTab[0].Down()
		self.equipmentTab[0].Hide()
		self.equipmentTab[1].Hide()

		self.wndItem = wndItem
		self.wndEquip = wndEquip
		self.dlgPickMoney = dlgPickMoney
		self._bag_events = nui_slots.LegacySlotEvents(wndItem, on_states=self._on_bag_states,
		                                              on_attaching=self._on_bag_attaching)
		self._wear_events = nui_slots.LegacySlotEvents(wndEquip, on_states=self._on_wear_states)

		if self.mallButton:
			self.mallButton.SetEvent(ui.__mem_func__(self.ClickMallButton))
		if self.DSSButton:
			self.DSSButton.SetEvent(ui.__mem_func__(self.ClickDSSButton))
		if self.costumeButton:
			self.costumeButton.SetEvent(ui.__mem_func__(self.ClickCostumeButton))
		self.wndCostume = None
		self._set(has_costume=bool(self.costumeButton), has_dss=bool(self.DSSButton), has_mall=bool(self.mallButton))

		## Refresh
		self.SetInventoryPage(0)
		self.SetEquipmentPage(0)
		self.RefreshItemSlot()
		self.RefreshStatus()

	# --- what NovaUI changes (P14 spec 6.1's table) ------------------------------------

	def Show(self):
		# The figure of the race shown now (the main actor's, set by then).
		figure = figure_for_race(player.GetRace())
		if figure != self._state["figure"]:
			self._set(figure=figure)
		# The board first, so the belt and the costume, which legacy's Show
		# opens again, are placed beside a shown board. A board made here is
		# placed in the next update, so until legacy's Show returns its
		# origin is the place it opens at (board_origin).
		made = self.board() is None
		self._show_board()
		self._opening = made and self.board() is not None
		try:
			uiInventory.InventoryWindow.Show(self)
		finally:
			self._opening = False

	def Hide(self):
		uiInventory.InventoryWindow.Hide(self)
		# Legacy's Hide returns early while an item question is open.
		if not self.IsShow():
			self._hide_board()

	def SetTop(self):
		board = self.board()
		if board is not None:
			board.bring_to_front()
		nui_hud.note_raise(self)
		uiInventory.InventoryWindow.SetTop(self)

	def Destroy(self):
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		uiInventory.InventoryWindow.Destroy(self)
		nui_hud.forget(KEY, self)

	def SetInventoryPage(self, page):
		"""Legacy's rule (every other tab up, since NOVA-97's five pages), the
		page's tab down (a proxy's press does not put it down, as a legacy
		radio button's does) and the board's page."""
		self.inventoryPageIndex = page
		for index, tab in enumerate(self.inventoryTab):
			if index == page:
				tab.Down()
			else:
				tab.SetUp()
		self._set(page=int(page))
		self.RefreshBagSlotWindow()

	def SetEquipmentPage(self, page):
		"""The equipment tabs stay hidden, as legacy hides them."""
		self.equipmentPageIndex = page
		self.RefreshEquipSlotWindow()

	def RefreshStatus(self):
		"""Legacy's (the money), then the stats row: attack, defence and
		magic attack as the character window sums them
		(uicharacter.py __GetTotalAtkText and its neighbors)."""
		uiInventory.InventoryWindow.RefreshStatus(self)
		status = player.GetStatus
		bonus = status(player.ATT_BONUS) + status(player.ATTACKER_BONUS)
		attack = _span(status(player.ATT_MIN) + bonus, status(player.ATT_MAX) + bonus)
		defence = status(player.DEF_GRADE)
		if constInfo.ADD_DEF_BONUS_ENABLE:
			defence += status(player.DEF_BONUS)
		magic = status(player.MAG_ATT)
		magic = _span(magic + status(player.MIN_MAGIC_WEP), magic + status(player.MAX_MAGIC_WEP))
		stats = {"stat_attack": attack, "stat_defence": "%d" % defence, "stat_magic": magic}
		changed = dict((key, value) for key, value in stats.items() if self._state.get(key) != value)
		if changed:
			self._set(**changed)

	def UseDSSButtonEffect(self, enable):
		"""The dragon soul button's active look (legacy lays a slot window
		with the active effect over the button)."""
		self._set(dss_active=bool(enable))

	def ClickCostumeButton(self):
		if self.wndCostume:
			if self.wndCostume.IsShow():
				self.wndCostume.Hide()
			else:
				self.wndCostume.Show()
		else:
			import nui_costume
			self.wndCostume = nui_costume.CostumeWindow(self)
			self.wndCostume.Show()

