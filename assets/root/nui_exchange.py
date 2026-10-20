"""NovaUI exchange (nui/windows/exchange/exchange.rml; P16 spec 5.1).

While the exchange flag is on, Interface.__MakeDialogs makes ExchangeDialog
below through nui_windows.make() instead of uiExchange.ExchangeDialog: a
subclass of the legacy class (nui_facade.Facade) whose LoadDialog puts
proxies where the uiscript's widgets were, bound as legacy binds them. So
the drop on an owner cell (the auto potion's use first, the give anti flag,
the item add packet), the money (the pick money dialog, the money add
packet), the accept, the exit and the server's refreshes are legacy's code.
Both grids show only CPythonExchange's state, through legacy's Refresh: a
drop sends its packet and draws nothing at the drop cell, since the server
may move it to another cell (NOVA-84, D7). Legacy's per-frame distance rule
is nuigame.WatchLeaveRange's watch (armed in OpenDialog, stopped in
CloseDialog, rearmed after each exit packet as legacy resets its start);
legacy's wndMgr.OnceIgnoreMouseLeftButtonUpEvent() in CloseDialog is left
out (NovaUI acts on the press, so it would swallow the next legacy
release). The board exists only while the window shows."""

import exchange
import localeInfo
import net
import nuigame
import player
import ui
import uiExchange
import uiPickMoney

import nui
import nui_facade
import nui_form_proxies
import nui_hud
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/exchange/exchange.rml"
KEY = "exchange"
# Legacy's USE_EXCHANGE_LIMIT_RANGE (uiexchange.py:227).
LEAVE_RANGE = 1000


class _ExchangeBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The exchange's document; its events go to its window. A press on it
	raises the window, as legacy's window manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "exchange"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("owner_press")
	def on_owner_press(self, index, button):
		self.raise_for(button)
		self._owner._owner_events.press(int(index), button)

	@nui.on("owner_release")
	def on_owner_release(self, index, button):
		self._owner._owner_events.release(int(index), button)

	@nui.on("owner_drop")
	def on_owner_drop(self, index):
		self._owner._owner_events.drop(int(index))

	@nui.on("owner_over")
	def on_owner_over(self, index):
		self._owner._owner_events.over(int(index))

	@nui.on("owner_out")
	def on_owner_out(self, index):
		self._owner._owner_events.out(int(index))

	@nui.on("target_press")
	def on_target_press(self, index, button):
		# Legacy's target grid has no select event: a press only raises.
		self.raise_for(button)
		self._owner._target_events.press(int(index), button)

	@nui.on("target_over")
	def on_target_over(self, index):
		self._owner._target_events.over(int(index))

	@nui.on("target_out")
	def on_target_out(self, index):
		self._owner._target_events.out(int(index))

	@nui.on("money_press")
	def on_money_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.OwnerMoneyButton.click()

	@nui.on("accept_press")
	def on_accept_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.AcceptButton.press()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.titleBar.close()


class ExchangeDialog(nui_facade.Facade, uiExchange.ExchangeDialog):
	"""uiExchange.ExchangeDialog on NovaUI (Interface.dlgExchange)."""

	KEY = KEY
	LEAVE_RANGE = True
	BOARD = _ExchangeBoard
	PLACE = "center"

	def __init__(self):
		self.nui_begin()
		try:
			uiExchange.ExchangeDialog.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		limits = self._limits
		count = limits.EXCHANGE_ITEM_MAX_NUM
		return {
			"title": "",
			"cols": limits.EXCHANGE_COLUMNS,
			"owner_cells": [nui_slots.empty_cell(i) for i in range(count)],
			"target_cells": [nui_slots.empty_cell(i) for i in range(count)],
			"owner_money": "",
			"target_money": "",
			"owner_money_value": 0,
			"target_money_value": 0,
			"owner_accept": False,
			"target_accept": False,
			"accept_down": False,
			"accept_enabled": True,
			# P14b: the grids' is-attaching (nui_slots.LegacySlotEvents).
			"owner_attaching": False,
			"target_attaching": False,
		}

	# --- the proxies' callbacks ---------------------------------------------------------

	def _grid(self, key, proxy, events):
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		self.nui_set(**{key: nui_slots.with_states(proxy.cells(), states, picked)})

	def _on_owner(self, cells):
		self._grid("owner_cells", self.OwnerSlot, getattr(self, "_owner_events", None))

	def _on_target(self, cells):
		self._grid("target_cells", self.TargetSlot, getattr(self, "_target_events", None))

	def _on_owner_states(self, states, picked):
		self.nui_set(owner_cells=nui_slots.with_states(self.OwnerSlot.cells(), states, picked))

	def _on_target_states(self, states, picked):
		self.nui_set(target_cells=nui_slots.with_states(self.TargetSlot.cells(), states, picked))

	def _on_owner_attaching(self, flag):
		self.nui_set(owner_attaching=flag)

	def _on_target_attaching(self, flag):
		self.nui_set(target_attaching=flag)

	def _on_title(self, text):
		self.nui_set(title=nui.plain_text(text))

	def _on_owner_money(self, text):
		self.nui_set(owner_money=nui.plain_text(text), owner_money_value=int(exchange.GetElkFromSelf()))

	def _on_target_money(self, text):
		self.nui_set(target_money=nui.plain_text(text), target_money_value=int(exchange.GetElkFromTarget()))

	def _on_lights(self, button):
		"""The lamps' Down and SetUp (legacy's lights are buttons)."""
		lights = [getattr(self, name, None) for name in ("OwnerAcceptLight", "TargetAcceptLight")]
		self.nui_set(owner_accept=bool(getattr(lights[0], "down", False)),
		             target_accept=bool(getattr(lights[1], "down", False)))

	def _on_accept_button(self, button):
		self.nui_set(accept_down=bool(button.down), accept_enabled=bool(button.enabled))

	# --- the loader (uiexchange.py:28-66, on proxies) ---------------------------------

	def LoadDialog(self):
		# The uiscript's style (exchangedialog.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		limits = self._limits
		count, cols = limits.EXCHANGE_ITEM_MAX_NUM, limits.EXCHANGE_COLUMNS
		rows = count // max(1, cols)

		## Owner
		self.OwnerSlot = nui_form_proxies.TypedSlotWindowProxy(range(count), self._on_owner, cols=cols, rows=rows,
		                                                       slot_type=player.SLOT_TYPE_EXCHANGE_OWNER)
		self.OwnerSlot.SetSelectEmptySlotEvent(ui.__mem_func__(self.SelectOwnerEmptySlot))
		self.OwnerSlot.SetSelectItemSlotEvent(ui.__mem_func__(self.SelectOwnerItemSlot))
		self.OwnerSlot.SetOverInItemEvent(ui.__mem_func__(self.OverInOwnerItem))
		self.OwnerSlot.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		self.OwnerMoney = nui_proxies.TextProxy(self._on_owner_money)
		self.OwnerAcceptLight = nui_proxies.ButtonProxy(self._on_lights)
		self.OwnerAcceptLight.Disable()
		self.OwnerMoneyButton = nui_proxies.ButtonProxy()
		self.OwnerMoneyButton.SetEvent(ui.__mem_func__(self.OpenPickMoneyDialog))

		## Target
		self.TargetSlot = nui_form_proxies.TypedSlotWindowProxy(range(count), self._on_target, cols=cols, rows=rows,
		                                                        slot_type=player.SLOT_TYPE_EXCHANGE_TARGET)
		self.TargetSlot.SetOverInItemEvent(ui.__mem_func__(self.OverInTargetItem))
		self.TargetSlot.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		self.TargetMoney = nui_proxies.TextProxy(self._on_target_money)
		self.TargetAcceptLight = nui_proxies.ButtonProxy(self._on_lights)
		self.TargetAcceptLight.Disable()

		## PickMoneyDialog (the dialog kit's facade while the dialogs flag is on)
		dlgPickMoney = uiPickMoney.PickMoneyDialog()
		dlgPickMoney.LoadDialog()
		dlgPickMoney.SetAcceptEvent(ui.__mem_func__(self.OnPickMoney))
		dlgPickMoney.SetTitleName(localeInfo.EXCHANGE_MONEY)
		# Legacy's SetMax(7); the limits module's digits (P16 spec 3.3).
		dlgPickMoney.SetMax(limits.EXCHANGE_MONEY_DIGITS)
		dlgPickMoney.Hide()
		self.dlgPickMoney = dlgPickMoney

		## Button
		self.AcceptButton = nui_form_proxies.ToggleProxy(self._on_accept_button)
		self.AcceptButton.SetToggleDownEvent(ui.__mem_func__(self.AcceptExchange))

		self.TitleName = nui_proxies.TextProxy(self._on_title)
		self.titleBar = nui_proxies.BoardProxy(266, 23)
		self.titleBar.SetCloseEvent(net.SendExchangeExitPacket)

		self._owner_events = self.nui_events(nui_slots.LegacySlotEvents(
			self.OwnerSlot, on_states=self._on_owner_states, on_attaching=self._on_owner_attaching))
		self._target_events = self.nui_events(nui_slots.LegacySlotEvents(
			self.TargetSlot, on_states=self._on_target_states, on_attaching=self._on_target_attaching))

	# --- what NovaUI changes (P16 spec 5.1.3) -----------------------------------------

	def OpenDialog(self):
		uiExchange.ExchangeDialog.OpenDialog(self)
		nuigame.WatchLeaveRange(KEY, LEAVE_RANGE, ui.__mem_func__(self._left_range), True)

	def CloseDialog(self):
		# Legacy's, without wndMgr.OnceIgnoreMouseLeftButtonUpEvent().
		if 0 != self.tooltipItem:
			self.tooltipItem.HideToolTip()

		self.dlgPickMoney.Close()
		self.Hide()
		nuigame.StopLeaveRange(KEY)

	def _left_range(self):
		"""Legacy's OnUpdate body once the watch fires: the start point reset,
		the exit packet."""
		(self.xStart, self.yStart, z) = player.GetMainCharacterPosition()
		net.SendExchangeExitPacket()
