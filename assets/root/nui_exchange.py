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
may move it to another cell (NOVA-84, D7). Wave 4b (NOVA-12, NOVA-13) is
legacy's too: the 6 x 4 grids (nui_limits' EXCHANGE_*), the faces, the
partner's name and level, the history (exchangeLogs, its last lines), the
accepted side's green slot base (SetSlotBaseImage on the grids' proxies),
the give-away question (uiCommon.QuestionDialog2, the dialog kit's facade
while dialogs is on) and the locks of the source cells in both inventories
(CantTradableItem from game.py's BINARY_AddItemToExchange through the
Interface, ReleaseTradableItem, released at the close and the END); the
cells legacy marks outside a NovaUI event show through
nui_slots.flush_marks() at the end of each of those entry points. Legacy's
per-frame distance rule is nuigame.WatchLeaveRange's watch (armed in
OpenDialog, stopped in CloseDialog, rearmed after each exit packet as legacy
resets its start); legacy's wndMgr.OnceIgnoreMouseLeftButtonUpEvent() in
CloseDialog is left out (NovaUI acts on the press, so it would swallow the
next legacy release), the rest of it kept. The board loads at the window's
first show and is kept, hidden, after it, both grids emptied
(nui_hud.KeptBoard, P18: WAVE4.md measured 15.5 to 18.2 ms of UI work at its
open, a 60 fps frame in cyberpunk, and a document load of 5.8 to 7.6 ms at
every open); a refresh while hidden reaches the facade's state, which the
next show sets."""

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


class _ExchangeSlots(nui_form_proxies.TypedSlotWindowProxy):
	"""One side's grid: a TypedSlotWindowProxy that also keeps the slot base
	legacy sets at each Refresh (uiexchange.py __SetSlotBase, through
	CallIfAny): an accepted side's base is tinted green
	(ACCEPTED_SLOT_BASE_COLOR), the other white. on_base(accepted) runs
	with True for a tinted base."""

	def __init__(self, slot_numbers, on_refresh, on_base, **kwargs):
		nui_form_proxies.TypedSlotWindowProxy.__init__(self, slot_numbers, on_refresh, **kwargs)
		self.on_base = on_base
		self.base = None

	def SetSlotBaseImage(self, path, r=1.0, g=1.0, b=1.0, a=1.0):
		color = (float(r), float(g), float(b), float(a))
		self.base = (str(path), color)
		self.on_base(color != (1.0, 1.0, 1.0, 1.0))


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
			# P18: both grids, a list of one entry while the board shows,
			# none while it is kept hidden.
			"grids_on": [1],
			# Wave 4b (NOVA-12): the faces (store paths), the partner's name
			# and level line, the history's shown lines (legacy's
			# EXCHANGE_LOG_LINE_COUNT, the last ones) and each side's green
			# slot base.
			"owner_face": "",
			"target_face": "",
			"target_name": "",
			"target_level": "",
			"log_lines": [""] * uiExchange.EXCHANGE_LOG_LINE_COUNT,
			"owner_base_accepted": False,
			"target_base_accepted": False,
		}

	def nui_demand(self):
		"""P18: the board is kept, hidden, after the first open (V-2b's
		pattern): a later open loads nothing."""
		return nui_hud.KeptBoard(self._make_board, self._restore_board, self._keep_board, self._empty_board)

	def _empty_board(self, board):
		"""The kept hidden board holds no cell (RmlUi updates every element
		of a loaded document each frame); _restore_board sets them again."""
		board.set(grids_on=[])

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

	def _on_owner_face(self, path):
		self.nui_set(owner_face=nui_slots.icon_source(path))

	def _on_target_face(self, path):
		self.nui_set(target_face=nui_slots.icon_source(path))

	def _on_target_name(self, text):
		self.nui_set(target_name=nui.plain_text(text))

	def _on_target_level(self, text):
		self.nui_set(target_level=nui.plain_text(text))

	def _on_log(self, text):
		"""A history line's SetText (legacy's AppendExchangeLog sets every
		line): the lines as legacy's text lines hold them."""
		self.nui_set(log_lines=[nui.plain_text(line.GetText()) for line in self.ExchangeLogLines])

	def _on_owner_base(self, accepted):
		self.nui_set(owner_base_accepted=bool(accepted))

	def _on_target_base(self, accepted):
		self.nui_set(target_base_accepted=bool(accepted))

	# --- the loader (uiexchange.py LoadDialog, on proxies) -----------------------------

	def LoadDialog(self):
		# The uiscript's style (exchangedialog.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		limits = self._limits
		count, cols = limits.EXCHANGE_ITEM_MAX_NUM, limits.EXCHANGE_COLUMNS
		rows = count // max(1, cols)

		## Owner
		self.OwnerSlot = _ExchangeSlots(range(count), self._on_owner, self._on_owner_base, cols=cols, rows=rows,
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
		self.TargetSlot = _ExchangeSlots(range(count), self._on_target, self._on_target_base, cols=cols, rows=rows,
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
		# Legacy's SetMax(player.EXCHANGE_MONEY_DIGITS) (NOVA-96, OLD's 12); the
		# limits module reads the same constant (P16 spec 3.3).
		dlgPickMoney.SetMax(limits.EXCHANGE_MONEY_DIGITS)
		dlgPickMoney.Hide()
		self.dlgPickMoney = dlgPickMoney

		## Button
		self.AcceptButton = nui_form_proxies.ToggleProxy(self._on_accept_button)
		self.AcceptButton.SetToggleDownEvent(ui.__mem_func__(self.AcceptExchange))

		self.TitleName = nui_proxies.TextProxy(self._on_title)
		# The uiscript's title bar: the board's width less 16 (442 - 16).
		self.titleBar = nui_proxies.BoardProxy(426, 23)
		self.titleBar.SetCloseEvent(net.SendExchangeExitPacket)

		## The faces, the partner's name and level and the history
		self.FaceOwnerImage = nui_proxies.ImageProxy(self._on_owner_face)
		self.FaceTargetImage = nui_proxies.ImageProxy(self._on_target_face)
		self.TargetName = nui_proxies.TextProxy(self._on_target_name)
		self.TargetLevel = nui_proxies.TextProxy(self._on_target_level)
		self.ExchangeLogLines = [nui_proxies.TextProxy(self._on_log)
		                         for i in range(uiExchange.EXCHANGE_LOG_LINE_COUNT)]

		self._owner_events = self.nui_events(nui_slots.LegacySlotEvents(
			self.OwnerSlot, on_states=self._on_owner_states, on_attaching=self._on_owner_attaching))
		self._target_events = self.nui_events(nui_slots.LegacySlotEvents(
			self.TargetSlot, on_states=self._on_target_states, on_attaching=self._on_target_attaching))

	# --- what NovaUI changes (P16 spec 5.1.3) -----------------------------------------

	def OpenDialog(self):
		uiExchange.ExchangeDialog.OpenDialog(self)
		nuigame.WatchLeaveRange(KEY, LEAVE_RANGE, ui.__mem_func__(self._left_range), True)
		# Legacy's open put the exchange on top, which marked the bags.
		nui_slots.flush_marks()

	def CloseDialog(self):
		# Legacy's, without wndMgr.OnceIgnoreMouseLeftButtonUpEvent(): the
		# tooltip, the money input and the give-away question close, the
		# window hides, every source cell takes the mouse again and nothing
		# is on top.
		if 0 != self.tooltipItem:
			self.tooltipItem.HideToolTip()

		self.dlgPickMoney.Close()
		self.OnCloseQuestionDialog()
		self.Hide()

		self.ReleaseLockedItems()
		uiExchange.ExchangeDialog._ExchangeDialog__SetOnTopWindow(self, player.ON_TOP_WND_NONE)
		nuigame.StopLeaveRange(KEY)
		nui_slots.flush_marks()

	def OnTop(self):
		uiExchange.ExchangeDialog.OnTop(self)
		nui_slots.flush_marks()

	# Wave 4b (NOVA-13): legacy's locks of the source cells, which mark the
	# inventories' cells outside any NovaUI event (game.py
	# BINARY_AddItemToExchange and BINARY_DelItemFromExchange through the
	# Interface, a refresh): each shows at once.

	def CantTradableItem(self, destSlotIndex, srcSlotIndex, srcWindow=player.INVENTORY):
		uiExchange.ExchangeDialog.CantTradableItem(self, destSlotIndex, srcSlotIndex, srcWindow)
		nui_slots.flush_marks()

	def ReleaseTradableItem(self, destSlotIndex):
		uiExchange.ExchangeDialog.ReleaseTradableItem(self, destSlotIndex)
		nui_slots.flush_marks()

	def RefreshLockedSlot(self):
		uiExchange.ExchangeDialog.RefreshLockedSlot(self)
		nui_slots.flush_marks()

	def _left_range(self):
		"""Legacy's OnUpdate body once the watch fires: the start point reset,
		the exit packet."""
		(self.xStart, self.yStart, z) = player.GetMainCharacterPosition()
		net.SendExchangeExitPacket()
