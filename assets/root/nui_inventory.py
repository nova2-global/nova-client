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
comes from nui_limits.current()."""

import app
import mouseModule
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
# Legacy's pick money digits (uiinventory.py:529, SetMax(7)).
LEGACY_MONEY_DIGITS = 7


class _InventoryBoard(nui.Window):
	"""The inventory's document; its events go to its window."""

	DOCUMENT = DOCUMENT
	MODEL = "inventory"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	# --- the bag and the wear cells: the legacy slot windows' events ---------------

	@nui.on("bag_press")
	def on_bag_press(self, index, button):
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
		if button == 0:
			self._owner._press_page(int(index))

	@nui.on("money_press")
	def on_money_press(self, button):
		if button == 0:
			self._owner.wndMoneySlot.click()

	@nui.on("costume_press")
	def on_costume_press(self, button):
		if button == 0 and self._owner.costumeButton:
			self._owner.costumeButton.click()

	@nui.on("dss_press")
	def on_dss_press(self, button):
		if button == 0 and self._owner.DSSButton:
			self._owner.DSSButton.click()

	@nui.on("mall_press")
	def on_mall_press(self, button):
		if button == 0 and self._owner.mallButton:
			self._owner.mallButton.click()

	@nui.on("close_press")
	def on_close_press(self, button):
		if button == 0:
			self._owner.Close()


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
			self.demand = nui_hud.OnDemand(self._make_board, self._restore_board, self._keep_board)
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
		self._bag_events = nui_slots.LegacySlotEvents(wndItem, on_states=self._on_bag_states)
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
		uiInventory.InventoryWindow.SetTop(self)

	def Destroy(self):
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		uiInventory.InventoryWindow.Destroy(self)
		nui_hud.forget(KEY, self)

	def SetInventoryPage(self, page):
		"""Legacy's two-tab rule (1 - page) cannot hold more pages: the page's
		tab is down, the others up."""
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

	def OpenPickMoneyDialog(self):
		"""Legacy's, then the money input's digits from the limits module
		when it opened (legacy limits it to 7 digits, uiinventory.py:529)."""
		opens = not mouseModule.mouseController.isAttached() and player.GetElk() > 0
		uiInventory.InventoryWindow.OpenPickMoneyDialog(self)
		digits = self._limits.INVENTORY_MONEY_DIGITS
		if opens and digits != LEGACY_MONEY_DIGITS:
			self.dlgPickMoney.SetMax(digits)
