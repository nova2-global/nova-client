"""NovaUI gaya market (nui/windows/gem-shop/gem-shop.rml; Wave 5, NOVA-10).

While the gem-shop flag is on, Interface.__MakeWindows makes GemShopWindow
below through nui_windows.make() instead of uiGemShop.GemShopWindow: a
subclass of the legacy class (nui_facade.Facade) whose uiscript loader puts
proxies where the widgets were: the 3 x 3 market (a SlotWindowProxy), the
nine prices, the refresh time, the refresh button and the title bar. So
the slots, the prices and the locked ones (the player module's GetGemShop*
getters), the questions before an unlock, a buy or a refresh, the checks
before them (the unlock item, the gaya balance, the refresh item) and the
packets are legacy's code.

What legacy did every frame happens without Python: the 500-unit walk-away
is nuigame.WatchLeaveRange's watch (armed by Open, stopped by Hide), which
calls legacy's CloseShop (the player's close: net.SendGemShopClose); the
"HH:MM" refresh time is legacy's text, written again at each minute's turn
by a nui-countdown timer's countdownend (format "none"), once a minute
instead of every frame. The server's close (Interface.CloseGemShop) is
legacy's Close and sends nothing. The board exists only while the window
shows; it draws below the legacy UI layer, as legacy's window lived in it."""

import app
import nuigame
import player
import ui
import uiGemShop

import nui
import nui_facade
import nui_hud
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/gem-shop/gem-shop.rml"
KEY = "gem-shop"
# Legacy's GEM_SHOP_WINDOW_LIMIT_RANGE (uigemshop.py).
LEAVE_RANGE = uiGemShop.GemShopWindow.GEM_SHOP_WINDOW_LIMIT_RANGE
COLUMNS = 3


def _slot_count():
	return int(getattr(player, "GAYA_MARKET_SLOT_COUNT", 9) or 9)


class _GemShopBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The market's document; its events go to its window. A press on it
	raises the window, as legacy's window manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "gem_shop"

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

	@nui.on("cell_over")
	def on_cell_over(self, index):
		self._owner._cell_events.over(int(index))

	@nui.on("cell_out")
	def on_cell_out(self, index):
		self._owner._cell_events.out(int(index))

	@nui.on("refresh_press")
	def on_refresh_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.refreshButton.click()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.titleBar.close()

	@nui.on("minute")
	def on_minute(self):
		self._owner.nui_minute()


class GemShopWindow(nui_facade.Facade, uiGemShop.GemShopWindow):
	"""uiGemShop.GemShopWindow on NovaUI (Interface.wndGemShop)."""

	KEY = KEY
	LEAVE_RANGE = True
	BOARD = _GemShopBoard
	PLACE = "center"

	def __init__(self):
		self.nui_begin()
		try:
			uiGemShop.GemShopWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		count = _slot_count()
		return {
			"cells": [nui_slots.empty_cell(i) for i in range(count)],
			"cols": COLUMNS,
			"prices": ["0"] * count,
			"refresh_time": "00:00",
			# The clock's next minute turn (nui.now() + seconds; 0: none).
			"minute_end": 0.0,
			"attaching": False,
			# P15 F-2: nui_slots.ATTACH_RIGHT (the market's nui-attach-right).
			"attach_right": bool(getattr(nui_slots, "ATTACH_RIGHT", False)),
		}

	# --- the proxies' callbacks ---------------------------------------------------------

	def _on_cells(self, cells):
		events = getattr(self, "_cell_events", None)
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		self.nui_set(cells=nui_slots.with_states(cells, states, picked))

	def _on_states(self, states, picked):
		self.nui_set(cells=nui_slots.with_states(self.itemSlot.cells(), states, picked))

	def _on_attaching(self, flag):
		self.nui_set(attaching=flag)

	def _on_price(self, index, text):
		prices = list(self._state.get("prices") or [])
		while len(prices) <= index:
			prices.append("0")
		prices[index] = nui.plain_text(text)
		self.nui_set(prices=prices)

	def _on_refresh_time(self, text):
		self.nui_set(refresh_time=nui.plain_text(text))

	# --- the loader (uigemshop.py __LoadWindow, on proxies) ------------------------------

	def _GemShopWindow__LoadWindow(self):
		# The uiscript's style (gemshopwindow.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		count = self.GetSlotCount()
		self.titleBar = nui_proxies.BoardProxy(153, 23)
		self.itemSlot = nui_slots.SlotWindowProxy(range(count), self._on_cells, cols=COLUMNS,
		                                          rows=max(1, count // COLUMNS))
		self.refreshTime = nui_proxies.TextProxy(self._on_refresh_time)
		self.refreshButton = nui_proxies.ButtonProxy()
		self.priceList = [nui_proxies.TextProxy(lambda text, i=i: self._on_price(i, text)) for i in range(count)]

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.CloseShop))
		self.refreshButton.SetEvent(ui.__mem_func__(self.SendRequestRefresh))
		self.itemSlot.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		self.itemSlot.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		self.itemSlot.SetSelectItemSlotEvent(ui.__mem_func__(self.UseItemSlot))

		self._cell_events = self.nui_events(nui_slots.LegacySlotEvents(
			self.itemSlot, on_states=self._on_states, on_attaching=self._on_attaching))

	# --- what NovaUI changes -----------------------------------------------------------

	def Open(self):
		"""Legacy's, then the walk-away watch (legacy's OnUpdate rule)."""
		uiGemShop.GemShopWindow.Open(self)
		nuigame.WatchLeaveRange(KEY, LEAVE_RANGE, ui.__mem_func__(self.CloseShop), False)

	def Hide(self):
		nui_facade.Facade.Hide(self)
		if not self.IsShow():
			nuigame.StopLeaveRange(KEY)
			self.nui_set(minute_end=0.0)

	def _GemShopWindow__StartRefreshClock(self):
		"""Legacy's (the end time and the "HH:MM" text), then the timer that
		writes the text again when its minute turns."""
		uiGemShop.GemShopWindow._GemShopWindow__StartRefreshClock(self)
		self._arm_minute()

	def _arm_minute(self):
		left = (self.refreshEndTime - app.GetGlobalTime()) / 1000.0
		if left <= 0:
			self.nui_set(minute_end=0.0)
			return
		# "HH:MM" changes when the seconds left pass a whole minute.
		turn = left % 60.0 or 60.0
		self.nui_set(minute_end=nui.now() + turn + 0.05)

	def nui_minute(self):
		"""The timer's countdownend: legacy's text update, then the next turn."""
		if not self.IsShow():
			return
		self._GemShopWindow__UpdateRefreshTime()
		self._arm_minute()
