"""NovaUI special inventory (nui/windows/extra-inventory/extra-inventory.rml;
wave 4b, NOVA-16).

While the extra-inventory flag is on, Interface.__MakeWindows makes
ExtraInventoryWindow below through nui_windows.make() instead of
uiExtraInventory.ExtraInventoryWindow. It is a subclass of the legacy class
(the Wave 3b pattern, nui_inventory's): its constructor is legacy's, whose
uiscript loader it replaces with proxies standing where the legacy widgets
were (a nui_form_proxies.TypedSlotWindowProxy for the 5 x 9 grid, whose
cells are SLOT_TYPE_EXTRA_INVENTORY items at their extra inventory cell and
show the trade marks; nui_proxies buttons for the twelve page tabs, the five
category tabs and the title bar's close), bound to the legacy handlers as
legacy's loader bound its widgets. So every flow, packet, question and rule
is the legacy class's own code: the categories and pages (SetCategory,
SetInventoryPage, the wheel's OnScrollWheel, GlobalSlotPos), pick, move,
use, a key on a box, split, sell, links, Ctrl + right-click (a transfer to
the inventory, or into the open trade), Shift + right-click into the open
safebox, a bean into the Dragon Soul refine window, the drops from both
inventories, the safebox and the mall, Alt + right-click on a stack of
chests (OpenMultiUseDialog and its count dialog), the marks of the trade
window on top and the cells the trade windows lock (BindWindow,
SetCantMouseEventCell, SetCanMouseEventCell, RefreshMarkSlots,
RefreshItemSlot), IsSafeboxOpen. Legacy marks cells outside RefreshSlot
(OnTop, the trade windows' locks, the Interface's RefreshMarkInventoryBag),
which CSlotWindow draws at once: each such entry point ends with the grid's
flush. Legacy's ScriptWindow stays underneath, a 0 x 0 window in the UI
layer, so IsShow, the Escape chain and SetTop are legacy's.

The board is kept, hidden, after its first open (nui_hud.KeptBoard, as the
inventory's), its cells and tabs emptied while it hides; a refresh while
hidden runs legacy's refresh on the proxies (legacy's RefreshItemSlot
refreshes only while the window shows) and the board takes the proxies'
last state at its next show. At its first show it opens at legacy's place
(the uiscript's: left of the inventory, 10 apart, its top at the
inventory's): beside the NovaUI inventory's board when that has a place,
else at the legacy inventory's place on the screen; then where the player
moved it. Every count comes from nui_limits.current()."""

import ui
import uiExtraInventory
import uiInventory
import uiPickMoney
import wndMgr

import nui
import nui_form_proxies
import nui_hud
import nui_limits
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/extra-inventory/extra-inventory.rml"
KEY = "extra-inventory"

# The categories' names (locale keys), in the server's order
# (EXTRA_INVENTORY_CATEGORY_*: scrolls, materials, stones, chests, costumes),
# as the uiscript's CATEGORY_NAMES.
CATEGORY_KEYS = ("@ui.EXTRA_INVENTORY_CATEGORY_SCROLLS", "@ui.EXTRA_INVENTORY_CATEGORY_MATERIALS",
                 "@ui.EXTRA_INVENTORY_CATEGORY_STONES", "@ui.EXTRA_INVENTORY_CATEGORY_CHESTS",
                 "@ui.EXTRA_INVENTORY_CATEGORY_COSTUMES")
# Legacy's place (uiscript extrainventorywindow.py): the window's right edge
# 10 left of the inventory's left edge, its top at the inventory's top; the
# legacy inventory is 176 wide at the screen's right, its top 37 + 591 above
# the screen's bottom (inventorywindow.py).
GAP_DP = 10.0
INVENTORY_WIDTH_DP = 176.0
INVENTORY_TOP_FROM_BOTTOM_DP = 37.0 + 591.0


def categories(limits):
	"""The category tabs' model: [{"index", "label"}] for the limits'
	EXTRA_INVENTORY_CATEGORY_COUNT categories (a locale key each)."""
	count = min(int(limits.EXTRA_INVENTORY_CATEGORY_COUNT), len(CATEGORY_KEYS))
	return [{"index": index, "label": CATEGORY_KEYS[index]} for index in range(count)]


def pages(count):
	"""The page tabs' model: [{"index", "label"}] for `count` pages, labeled
	as the uiscript's tabs (nui_limits.ROMAN: I to XII)."""
	roman = nui_limits.ROMAN
	return [{"index": index, "label": roman[index] if index < len(roman) else str(index + 1)} for index in range(count)]


class _ExtraInventoryBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The special inventory's document; its events go to its window. A press
	on it raises the window, as legacy's window manager does (RaisesOnPress)."""

	DOCUMENT = DOCUMENT
	MODEL = "extra_inventory"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("wheel")
	def on_wheel(self, delta):
		# RmlUi's sign: positive is down, the next page; legacy's OnScrollWheel
		# takes a notch up as positive.
		delta = float(delta)
		if delta:
			self._owner.OnScrollWheel(-1 if delta > 0 else 1)

	# --- the grid: the legacy slot window's events -----------------------------------

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

	# --- the controls: legacy's buttons, on a left mousedown ---------------------

	@nui.on("page_press")
	def on_page_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_page(int(index))

	@nui.on("category_press")
	def on_category_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_category(int(index))

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner._titleBar.close()


class ExtraInventoryWindow(uiExtraInventory.ExtraInventoryWindow):
	"""uiExtraInventory.ExtraInventoryWindow on NovaUI
	(Interface.wndExtraInventory)."""

	NUI_FACADE = True

	def __init__(self):
		nui_hud.take_over(KEY, self)
		self._nui_discarded = False
		self._limits = nui_limits.current()
		self._state = self._empty_state()
		self._place = None
		self._refreshing = False  # inside RefreshItemSlot: its marks show with its RefreshSlot
		self._cell_events = None
		self.loaded = False
		self.demand = None
		if nui_hud.has_engine_3b():
			self.demand = nui_hud.KeptBoard(self._make_board, self._restore_board, self._keep_board, self._empty_board)
		try:
			uiExtraInventory.ExtraInventoryWindow.__init__(self)
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
		nui_hud.forget(KEY, self)

	# --- the model ------------------------------------------------------------------

	def _empty_state(self):
		limits = self._limits
		return {
			# NOVA-187: each cell with the sell marks' "sell" (uiInventory.SellMarkCells).
			"cells": [dict(cell, sell=False) for cell in
			          nui_slots.with_marks([nui_slots.empty_cell(i) for i in range(limits.EXTRA_INVENTORY_PAGE_SIZE)])],
			"cols": limits.EXTRA_INVENTORY_COLUMNS,
			"pages": pages(1),
			"page": 0,
			"categories": categories(limits),
			"category": 0,
			# P14b: the grid's is-attaching (nui_slots.LegacySlotEvents).
			"attaching": False,
			# P15 F-2: a right press while something is attached uses the
			# cell's item, as legacy's CSlotWindow (nui_slots.ATTACH_RIGHT).
			"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
			# V-2: the grid and the tabs, each a list of one entry while the
			# board shows and none while it is kept hidden.
			"cells_on": [1], "tabs_on": [1],
		}

	def _set(self, **values):
		self._state.update(values)
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.set(**values)

	def _make_board(self):
		return _ExtraInventoryBoard(self, self._state)

	def _restore_board(self, board):
		board.set(**self._state)
		if self._place is not None:
			board.set_position(self._place[0], self._place[1])
		else:
			self._default_place(board)

	def _keep_board(self, board):
		box = board.element_box("")
		if box and box[2] > 0 and box[3] > 0:
			scale = nui.get_scale() or 1.0
			self._place = (box[0] / scale, box[1] / scale)

	def _empty_board(self, board):
		"""V-2: the hidden kept board holds no cell and no tab (RmlUi updates
		every element of a loaded document each frame); _restore_board sets
		the lists again at the next show."""
		board.set(cells_on=[], tabs_on=[])

	def _default_place(self, board):
		"""Legacy's place: the window's right edge GAP_DP left of the
		inventory's left edge, its top at the inventory's top. The NovaUI
		inventory's board where it has a place (board_origin), else the
		legacy inventory's place on the screen."""
		inventory = getattr(getattr(self, "interface", None), "wndInventory", None)
		origin = getattr(inventory, "board_origin", None)
		origin = origin() if origin is not None else None
		if origin is not None:
			board.set_position(origin[0] - GAP_DP, origin[1], origin=(1.0, 0.0))
			return
		scale = nui.get_scale() or 1.0
		board.set_position(wndMgr.GetScreenWidth() / scale - INVENTORY_WIDTH_DP - GAP_DP,
		                   wndMgr.GetScreenHeight() / scale - INVENTORY_TOP_FROM_BOTTOM_DP, origin=(1.0, 0.0))

	def board(self):
		"""The board while shown, else None."""
		return self.demand.board() if self.demand is not None else None

	# --- the proxies' callbacks ---------------------------------------------------------

	def _cell_position(self, local):
		"""A page cell's extra inventory cell (legacy's GlobalSlotPos)."""
		return self.GlobalSlotPos(local)

	def _on_cells(self, cells):
		events = self._cell_events
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		self._set(cells=self._sell_marks(nui_slots.with_states(cells, states, picked), True))

	def _on_states(self, states, picked):
		self._set(cells=self._sell_marks(nui_slots.with_states(self.wndItem.cells(), states, picked)))

	def _sell_marks(self, cells, refresh_board=False):
		"""NOVA-187: the cells' "sell" key (uiInventory.SellMarkCells)."""
		import player
		return uiInventory.SellMarkCells(cells, player.EXTRA_INVENTORY, self._cell_position, refresh_board)

	def _on_attaching(self, flag):
		self._set(attaching=flag)

	def _publish_tabs(self):
		"""The tabs as legacy left them: the page tabs it shows (the first
		GetPageCount of the twelve), the page and the category shown."""
		shown = [tab for tab in self.inventoryTab if tab.IsShow()]
		values = {"pages": pages(len(shown)), "page": int(self.inventoryPageIndex), "category": int(self.category)}
		changed = dict((key, value) for key, value in values.items() if self._state.get(key) != value)
		if changed:
			self._set(**changed)

	def _press_page(self, index):
		"""A page tab: its button, which a press on the page shown does not
		reach (CRadioButton ignores a press on the button that is down), nor
		one on a tab legacy hides."""
		if not (0 <= index < len(self.inventoryTab)) or index == self.inventoryPageIndex:
			return
		tab = self.inventoryTab[index]
		if tab.IsShow():
			tab.click()

	def _press_category(self, index):
		"""A category tab: its button, as a page tab's."""
		if not (0 <= index < len(self.categoryTab)) or index == self.category:
			return
		self.categoryTab[index].click()

	# --- the loader (uiextrainventory.py __LoadWindow, on proxies) ---------------------

	def _ExtraInventoryWindow__LoadWindow(self):
		if self.isLoaded == 1:
			return
		self.isLoaded = 1
		# The uiscript's style (extrainventorywindow.py: "movable", "float"):
		# a float window is the one SetTop raises (CWindow::SetTop).
		self.AddFlag("movable")
		self.AddFlag("float")
		limits = self._limits

		self._titleBar = nui_proxies.BoardProxy(254, 23)
		self._titleBar.SetCloseEvent(ui.__mem_func__(self.Close))
		wndItem = nui_form_proxies.TypedSlotWindowProxy(
			range(limits.EXTRA_INVENTORY_PAGE_SIZE), self._on_cells, cols=limits.EXTRA_INVENTORY_COLUMNS,
			rows=limits.EXTRA_INVENTORY_ROWS, positions=self._cell_position, window=limits.WINDOW_EXTRA_INVENTORY,
			slot_type=limits.SLOT_TYPE_EXTRA_INVENTORY, marks=True, glows=True)

		self.inventoryTab = [nui_proxies.ButtonProxy() for _ in range(limits.EXTRA_INVENTORY_COSTUME_PAGE_COUNT)]
		self.categoryTab = [nui_proxies.ButtonProxy() for _ in range(limits.EXTRA_INVENTORY_CATEGORY_COUNT)]

		wndItem.SetSelectEmptySlotEvent(ui.__mem_func__(self.SelectEmptySlot))
		wndItem.SetSelectItemSlotEvent(ui.__mem_func__(self.SelectItemSlot))
		wndItem.SetUnselectItemSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndItem.SetUseSlotEvent(ui.__mem_func__(self.UseItemSlot))
		wndItem.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		wndItem.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		self.wndItem = wndItem
		self._cell_events = nui_slots.LegacySlotEvents(wndItem, on_states=self._on_states,
		                                               on_attaching=self._on_attaching)

		for page, tab in enumerate(self.inventoryTab):
			tab.SetEvent(lambda arg=page: self.SetInventoryPage(arg))

		for category, tab in enumerate(self.categoryTab):
			tab.SetEvent(lambda arg=category: self.SetCategory(arg))

		## PickMoneyDialog (the split of a stack, the multi-open's count; the
		## dialog kit's facade while the dialogs flag is on)
		dlgPickMoney = uiPickMoney.PickMoneyDialog()
		dlgPickMoney.LoadDialog()
		dlgPickMoney.Hide()
		self.dlgPickMoney = dlgPickMoney

		self.SetCategory(self.category)

	# --- what NovaUI changes ----------------------------------------------------------

	def SetCategory(self, category):
		"""Legacy's (its tabs, the page count's tabs shown, page I), then the
		tabs to the board."""
		uiExtraInventory.ExtraInventoryWindow.SetCategory(self, category)
		self._publish_tabs()

	def SetInventoryPage(self, page):
		"""Legacy's (the page's tab down, every other up, the refresh), then
		the tabs to the board."""
		uiExtraInventory.ExtraInventoryWindow.SetInventoryPage(self, page)
		self._publish_tabs()

	def RefreshItemSlot(self):
		"""Legacy's refresh of the visible page; the marks it sets and the
		locks the trade windows set again after its RefreshSlot show with
		one push."""
		self._refreshing = True
		try:
			uiExtraInventory.ExtraInventoryWindow.RefreshItemSlot(self)
		finally:
			self._refreshing = False
		self._flush()

	def RefreshMarkSlots(self, localIndex=None):
		"""Legacy's marks of the trade window on top; they show at once (the
		Interface's RefreshMarkInventoryBag, OnTop)."""
		uiExtraInventory.ExtraInventoryWindow.RefreshMarkSlots(self, localIndex)
		self._flush()

	def SetCantMouseEventCell(self, globalSlotPos):
		"""A trade window locks the cell (legacy's), shown at once."""
		uiExtraInventory.ExtraInventoryWindow.SetCantMouseEventCell(self, globalSlotPos)
		self._flush()

	def SetCanMouseEventCell(self, globalSlotPos):
		"""A trade window releases the cell (legacy's), shown at once."""
		uiExtraInventory.ExtraInventoryWindow.SetCanMouseEventCell(self, globalSlotPos)
		self._flush()

	def _flush(self):
		if not self._refreshing and self.wndItem is not None:
			self.wndItem.flush()

	def Show(self):
		"""The board first, then legacy's (its refresh of the page)."""
		if self.demand is not None:
			self.demand.show()
		uiExtraInventory.ExtraInventoryWindow.Show(self)

	def Hide(self):
		uiExtraInventory.ExtraInventoryWindow.Hide(self)
		if not self.IsShow():
			# The board's cells hear no mouseout as it goes (nui_slots.LegacySlotEvents.reset).
			if self._cell_events is not None:
				self._cell_events.reset()
			if self.demand is not None:
				self.demand.hide()

	def SetTop(self):
		board = self.board()
		if board is not None:
			board.bring_to_front()
		nui_hud.note_raise(self)
		uiExtraInventory.ExtraInventoryWindow.SetTop(self)

	def Destroy(self):
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		uiExtraInventory.ExtraInventoryWindow.Destroy(self)
		nui_hud.forget(KEY, self)
