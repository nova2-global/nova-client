"""NovaUI private shop builder (nui/windows/private-shop/private-shop.rml;
P16 spec 5.3).

While the private-shop flag is on, Interface.__MakeDialogs makes
PrivateShopBuilder below through nui_windows.make() instead of
uiPrivateShopBuilder.PrivateShopBuilder: a subclass of the legacy class
(nui_facade.Facade) whose uiscript loader puts proxies where the widgets
were: the name line, the 40-cell grid (its cells show the stocked inventory
items, their ref the inventory position), OK, Close and the title bar. So a
drop (the give and my-shop anti flags, the price input with the price
list's price, the stock), a press on a stocked cell (out of the stock), OK
(shop.BuildPrivateShop) and Close are legacy's code. The shop's sign is
Wave 2b's (nui_shop_signs, D24). The builder centers itself at each Open, as
legacy's does; the board exists only while it shows."""

import ui
import uiPrivateShopBuilder

import nui
import nui_facade
import nui_hud
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/private-shop/private-shop.rml"
KEY = "private-shop"


class _PrivateShopBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The builder's document; its events go to its window. A press on it
	raises the window, as legacy's window manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "private_shop"

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

	@nui.on("ok_press")
	def on_ok_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.btnOk.click()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.btnClose.click()


class PrivateShopBuilder(nui_facade.Facade, uiPrivateShopBuilder.PrivateShopBuilder):
	"""uiPrivateShopBuilder.PrivateShopBuilder on NovaUI
	(Interface.privateShopBuilder)."""

	KEY = KEY
	BOARD = _PrivateShopBoard
	PLACE = "center"

	def __init__(self):
		self.nui_begin()
		try:
			uiPrivateShopBuilder.PrivateShopBuilder.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		limits = self._limits
		return {
			"title": "",
			"cells": [nui_slots.empty_cell(i) for i in range(limits.SHOP_SLOT_COUNT)],
			"cols": limits.SHOP_COLUMNS,
			"attaching": False,
		}

	# --- the proxies' callbacks ---------------------------------------------------------

	def _position(self, slot):
		"""A cell's inventory position: its stock entry's (legacy's itemStock)."""
		return getattr(self, "itemStock", {}).get(slot, (0, 0))[1]

	def _on_cells(self, cells):
		events = getattr(self, "_cell_events", None)
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		self.nui_set(cells=nui_slots.with_states(cells, states, picked))

	def _on_states(self, states, picked):
		self.nui_set(cells=nui_slots.with_states(self.itemSlot.cells(), states, picked))

	def _on_attaching(self, flag):
		self.nui_set(attaching=flag)

	def _on_name(self, text):
		self.nui_set(title=nui.plain_text(text))

	# --- the loader (uiprivateshopbuilder.py:132-158, on proxies) ---------------------

	def _PrivateShopBuilder__LoadWindow(self):
		# The uiscript's style (privateshopbuilder.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		limits = self._limits
		count, cols = limits.SHOP_SLOT_COUNT, limits.SHOP_COLUMNS
		self.nameLine = nui_proxies.TextProxy(self._on_name)
		self.itemSlot = nui_slots.SlotWindowProxy(range(count), self._on_cells, cols=cols, rows=count // max(1, cols),
		                                          positions=self._position)
		self.btnOk = nui_proxies.ButtonProxy()
		self.btnClose = nui_proxies.ButtonProxy()
		self.titleBar = nui_proxies.BoardProxy(169, 23)

		self.btnOk.SetEvent(ui.__mem_func__(self.OnOk))
		self.btnClose.SetEvent(ui.__mem_func__(self.OnClose))
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.OnClose))

		self.itemSlot.SetSelectEmptySlotEvent(ui.__mem_func__(self.OnSelectEmptySlot))
		self.itemSlot.SetSelectItemSlotEvent(ui.__mem_func__(self.OnSelectItemSlot))
		self.itemSlot.SetOverInItemEvent(ui.__mem_func__(self.OnOverInItem))
		self.itemSlot.SetOverOutItemEvent(ui.__mem_func__(self.OnOverOutItem))

		self._cell_events = self.nui_events(nui_slots.LegacySlotEvents(
			self.itemSlot, on_states=self._on_states, on_attaching=self._on_attaching))
