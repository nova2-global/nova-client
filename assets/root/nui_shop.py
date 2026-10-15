"""NovaUI shop: the NPC shop and a player's shop view
(nui/windows/shop/shop.rml; P16 spec 5.2).

While the shop flag is on, Interface.__MakeDialogs makes ShopDialog below
through nui_windows.make() instead of uiShop.ShopDialog: a subclass of the
legacy class (nui_facade.Facade) whose LoadDialog puts proxies where the
uiscript's widgets were: the grid (a TypedSlotWindowProxy whose cells carry
the shop's slot type and the real index), the buy and sell toggles, the
close-shop button, the two radio groups of tabs (RadioGroupProxy, legacy's
body). So the buy and sell cursor modes, the buy question, the right press
that buys at an NPC, the attach with its "INVENTORY" callback (the
inventory's drop asks the buy question), selling a dropped item and the
packets are legacy's code. Refresh is legacy's with the proxy's RefreshSlot
for wndMgr.RefreshSlot (the proxy has no window handle). Legacy's per-frame
distance rule is nuigame.WatchLeaveRange's watch, armed in Open and stopped
in Hide; it closes the shop once. The board exists only while the window
shows."""

import nuigame
import player
import shop
import ui
import uiShop
import wndMgr

import nui
import nui_facade
import nui_form_proxies
import nui_hud
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/shop/shop.rml"
KEY = "shop"
# Legacy's USE_SHOP_LIMIT_RANGE (uishop.py:451).
LEAVE_RANGE = 1000
# The uiscript's place (shopdialog.py: SCREEN_WIDTH - 400, 10), in dp.
PLACE_RIGHT, PLACE_TOP = 400, 10


class _ShopBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The shop's document; its events go to its window. A press on it raises
	the window, as legacy's window manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "shop"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("cell_press")
	def on_cell_press(self, index, button):
		self.raise_for(button)
		self._owner._cell_events.press(int(index), button)

	@nui.on("cell_release")
	def on_cell_release(self, index, button):
		self._owner._cell_events.release(int(index), button)

	@nui.on("cell_drop")
	def on_cell_drop(self, index):
		self._owner._cell_events.drop(int(index))

	@nui.on("cell_over")
	def on_cell_over(self, index):
		self._owner._cell_events.over(int(index))

	@nui.on("cell_out")
	def on_cell_out(self, index):
		self._owner._cell_events.out(int(index))

	@nui.on("tab_press")
	def on_tab_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_tab(int(index))

	@nui.on("buy_press")
	def on_buy_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.btnBuy.press()

	@nui.on("sell_press")
	def on_sell_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.btnSell.press()

	@nui.on("close_shop_press")
	def on_close_shop_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.btnClose.click()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.titleBar.close()


class ShopDialog(nui_facade.Facade, uiShop.ShopDialog):
	"""uiShop.ShopDialog on NovaUI (Interface.dlgShop)."""

	KEY = KEY
	BOARD = _ShopBoard

	def __init__(self):
		self.nui_begin()
		try:
			uiShop.ShopDialog.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def PLACE(self):
		"""Legacy's place, (W - 400, 10) in dp."""
		scale = nui.get_scale() or 1.0
		return (wndMgr.GetScreenWidth() / scale - PLACE_RIGHT, PLACE_TOP)

	def nui_model(self):
		limits = self._limits
		tabs = [{"index": i, "name": "", "down": False, "shown": False} for i in range(limits.SHOP_TAB_COUNT_MAX)]
		return {
			"cells": [nui_slots.empty_cell(i) for i in range(limits.SHOP_SLOT_COUNT)],
			"cols": limits.SHOP_COLUMNS,
			"attaching": False,
			"tabs": tabs,
			"tab": 0,
			"tab_group": "none",
			"buy_shown": False,
			"sell_shown": False,
			"close_shop_shown": False,
			"buy_down": False,
			"sell_down": False,
		}

	# --- the proxies' callbacks ---------------------------------------------------------

	def _real_index(self, slot):
		return getattr(self, "tabIdx", 0) * shop.SHOP_SLOT_COUNT + slot

	def _slot_type(self):
		return player.SLOT_TYPE_PRIVATE_SHOP if shop.IsPrivateShop() else player.SLOT_TYPE_SHOP

	def _on_cells(self, cells):
		events = getattr(self, "_cell_events", None)
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		self.nui_set(cells=nui_slots.with_states(cells, states, picked))

	def _on_states(self, states, picked):
		self.nui_set(cells=nui_slots.with_states(self.itemSlotWindow.cells(), states, picked))

	def _on_attaching(self, flag):
		self.nui_set(attaching=flag)

	def _on_buttons(self, button=None):
		"""The toggles' and the close-shop button's shown and down states."""
		found = dict((name, getattr(self, name, None)) for name in ("btnBuy", "btnSell", "btnClose"))
		values = {}
		if found["btnBuy"] is not None:
			values.update(buy_shown=bool(found["btnBuy"].shown), buy_down=bool(found["btnBuy"].down))
		if found["btnSell"] is not None:
			values.update(sell_shown=bool(found["btnSell"].shown), sell_down=bool(found["btnSell"].down))
		if found["btnClose"] is not None:
			values.update(close_shop_shown=bool(found["btnClose"].shown))
		self.nui_set(**values)

	def _on_tabs(self, changed=None):
		"""The tab row: the group legacy shows ("middle", "small" or "none"),
		its buttons' names and down states, the shown tab."""
		groups = [("middle", getattr(self, "middleRadioButtonGroup", None)),
		          ("small", getattr(self, "smallRadioButtonGroup", None))]
		group_name, group = "none", None
		for name, candidate in groups:
			if candidate is not None and candidate.shown:
				group_name, group = name, candidate
				break
		tabs = []
		buttons = group.buttons() if group is not None else []
		for index in range(self._limits.SHOP_TAB_COUNT_MAX):
			button = buttons[index] if index < len(buttons) else None
			tabs.append({"index": index, "name": nui.plain_text(button.text) if button is not None else "",
			             "down": bool(button.down) if button is not None else False, "shown": button is not None})
		self.nui_set(tab_group=group_name, tabs=tabs, tab=int(getattr(self, "tabIdx", 0)))

	def _press_tab(self, index):
		"""A press on a tab: the shown group's button, as CRadioButton takes it."""
		for name in ("middleRadioButtonGroup", "smallRadioButtonGroup"):
			group = getattr(self, name, None)
			if group is not None and group.shown:
				group.press(index)
				return

	# --- the loader (uishop.py:52-109, on proxies) -------------------------------------

	def LoadDialog(self):
		# The uiscript's style (shopdialog.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		limits = self._limits
		count, cols = limits.SHOP_SLOT_COUNT, limits.SHOP_COLUMNS
		self.itemSlotWindow = nui_form_proxies.TypedSlotWindowProxy(
			range(count), self._on_cells, cols=cols, rows=count // max(1, cols), positions=self._real_index,
			slot_type=self._slot_type)
		self.btnBuy = nui_form_proxies.ToggleProxy(self._on_buttons)
		self.btnSell = nui_form_proxies.ToggleProxy(self._on_buttons)
		self.btnClose = nui_proxies.ButtonProxy(self._on_buttons)
		self.titleBar = nui_proxies.BoardProxy(169, 23)
		middleTab1, middleTab2 = nui_proxies.ButtonProxy(self._on_tabs), nui_proxies.ButtonProxy(self._on_tabs)
		smallTab1, smallTab2, smallTab3 = [nui_proxies.ButtonProxy(self._on_tabs) for _ in range(3)]

		self.itemSlotWindow.SetSlotStyle(wndMgr.SLOT_STYLE_NONE)
		self.itemSlotWindow.SAFE_SetButtonEvent("LEFT", "EMPTY", self.SelectEmptySlot)
		self.itemSlotWindow.SAFE_SetButtonEvent("LEFT", "EXIST", self.SelectItemSlot)
		self.itemSlotWindow.SAFE_SetButtonEvent("RIGHT", "EXIST", self.UnselectItemSlot)

		self.itemSlotWindow.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		self.itemSlotWindow.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))

		self.btnBuy.SetToggleUpEvent(ui.__mem_func__(self.CancelShopping))
		self.btnBuy.SetToggleDownEvent(ui.__mem_func__(self.OnBuy))

		self.btnSell.SetToggleUpEvent(ui.__mem_func__(self.CancelShopping))
		self.btnSell.SetToggleDownEvent(ui.__mem_func__(self.OnSell))

		self.btnClose.SetEvent(ui.__mem_func__(self.AskClosePrivateShop))

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))

		self._cell_events = self.nui_events(nui_slots.LegacySlotEvents(
			self.itemSlotWindow, on_states=self._on_states, on_attaching=self._on_attaching))

		self.smallRadioButtonGroup = nui_form_proxies.RadioGroupProxy.Create(
			[[smallTab1, lambda: self.OnClickTabButton(0), None], [smallTab2, lambda: self.OnClickTabButton(1), None],
			 [smallTab3, lambda: self.OnClickTabButton(2), None]], on_change=self._on_tabs)
		self.middleRadioButtonGroup = nui_form_proxies.RadioGroupProxy.Create(
			[[middleTab1, lambda: self.OnClickTabButton(0), None], [middleTab2, lambda: self.OnClickTabButton(1), None]],
			on_change=self._on_tabs)

		self._ShopDialog__HideMiddleTabs()
		self._ShopDialog__HideSmallTabs()

		self.tabIdx = 0
		self.coinType = shop.SHOP_COIN_TYPE_GOLD

		self.Refresh()

	# --- what NovaUI changes (P16 spec 5.2.3) -----------------------------------------

	def Refresh(self):
		"""Legacy's, with the proxy's RefreshSlot for wndMgr.RefreshSlot."""
		getItemID = shop.GetItemID
		getItemCount = shop.GetItemCount
		setItemID = self.itemSlotWindow.SetItemSlot
		for i in range(shop.SHOP_SLOT_COUNT):
			idx = self._ShopDialog__GetRealIndex(i)
			itemCount = getItemCount(idx)
			if itemCount <= 1:
				itemCount = 0
			setItemID(i, getItemID(idx), itemCount)

		self.itemSlotWindow.RefreshSlot()
		self._on_tabs()

	def OnClickTabButton(self, idx):
		uiShop.ShopDialog.OnClickTabButton(self, idx)
		self._on_tabs()

	def Open(self, vid):
		uiShop.ShopDialog.Open(self, vid)
		nuigame.WatchLeaveRange(KEY, LEAVE_RANGE, ui.__mem_func__(self._left_range), False)

	def Hide(self):
		nui_facade.Facade.Hide(self)
		if not self.IsShow():
			nuigame.StopLeaveRange(KEY)

	def _left_range(self):
		"""Legacy's OnUpdate body once the watch fires: Close()."""
		self.Close()
