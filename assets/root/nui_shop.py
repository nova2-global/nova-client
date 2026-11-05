"""NovaUI shop facade: NPC, player and offline shops.

The class stays a subclass of :class:`uiShop.ShopDialog`. Legacy owns every
flow and rule; this module replaces only the widgets and layout with proxies
that publish their state to ``nui/windows/shop/shop.rml``. Offline shops use
legacy's 10 x 8 paged grid, questions, packets and owner panel directly --
there is no second legacy dialog hidden behind the facade.
"""

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
LEAVE_RANGE = 1000
PLACE_RIGHT, PLACE_TOP = 400, 10


def _offline_page_count():
	try:
		return max(0, int(getattr(shop, "OFFLINE_SHOP_PAGE_COUNT", 3)))
	except (TypeError, ValueError):
		return 3


def _offline_row_count():
	try:
		return max(0, int(getattr(shop, "OFFLINE_SHOP_ROWS_PER_PAGE", 8)))
	except (TypeError, ValueError):
		return 8


def _page_models(count=None):
	if count is None:
		count = _offline_page_count()
	return [{"index": i, "name": "", "down": False, "shown": False} for i in range(count)]


def _lock_models(rows=None):
	if rows is None:
		rows = _offline_row_count()
	return [{"row": row, "state": ""} for row in range(rows)]


class _ShopBoard(nui_hud.RaisesOnPress, nui.Window):
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
		if self._owner._cell_lock(int(index))[1]:
			return
		self._owner._cell_events.press(int(index), button)

	@nui.on("cell_release")
	def on_cell_release(self, index, button):
		row, state = self._owner._cell_lock(int(index))
		if state:
			if button == 0:
				self._owner._release_lock(row)
			return
		self._owner._cell_events.release(int(index), button)

	@nui.on("cell_drop")
	def on_cell_drop(self, index):
		if self._owner._cell_lock(int(index))[1]:
			return
		self._owner._cell_events.drop(int(index))

	@nui.on("cell_over")
	def on_cell_over(self, index):
		row, state = self._owner._cell_lock(int(index))
		if state:
			self._owner._over_lock(row)
			return
		self._owner._cell_events.over(int(index))

	@nui.on("cell_out")
	def on_cell_out(self, index):
		row, state = self._owner._cell_lock(int(index))
		if state:
			self._owner._out_lock(row)
			return
		self._owner._cell_events.out(int(index))

	@nui.on("tab_press")
	def on_tab_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_tab(int(index))

	@nui.on("page_press")
	def on_page_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_page(int(index))

	@nui.on("lock_release")
	def on_lock_release(self, row, button):
		if button == 0:
			self._owner._release_lock(int(row))

	@nui.on("lock_over")
	def on_lock_over(self, row):
		self._owner._over_lock(int(row))

	@nui.on("lock_out")
	def on_lock_out(self, row):
		self._owner._out_lock(int(row))

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

	def _owner_button(self, name, button):
		self.raise_for(button)
		if button == 0:
			getattr(self._owner.offlineShopWnd, name).click()

	@nui.on("owner_rename_press")
	def on_owner_rename_press(self, button):
		self._owner_button("renameButton", button)

	@nui.on("owner_warp_press")
	def on_owner_warp_press(self, button):
		self._owner_button("teleportButton", button)

	@nui.on("owner_withdraw_press")
	def on_owner_withdraw_press(self, button):
		self._owner_button("withdrawButton", button)

	@nui.on("owner_time_press")
	def on_owner_time_press(self, button):
		self._owner_button("addTimeButton", button)

	@nui.on("owner_lock_press")
	def on_owner_lock_press(self, button):
		self._owner_button("lockButton", button)

	@nui.on("owner_logs_press")
	def on_owner_logs_press(self, button):
		self._owner_button("viewLogButton", button)

	@nui.on("owner_close_press")
	def on_owner_close_press(self, button):
		self._owner_button("closeButton", button)

	@nui.on("owner_time_end")
	def on_owner_time_end(self):
		self._owner._owner_time_ended()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.titleBar.close()


class _OfflineShopWindow(uiShop.OfflineShopWindow):
	"""Legacy's owner panel with only its widget loader replaced."""

	def _shop(self):
		"""The shop dialog this panel reports to; None while ui.Window's
		__init__ runs (it calls Hide before legacy's __init__ sets parent)."""
		return self.__dict__.get("parent")

	def _publish(self, key, text):
		shop = self._shop()
		if shop is not None:
			shop._owner_text(key, text)

	def _buttons_changed(self, button=None):
		shop = self._shop()
		if shop is not None:
			shop._owner_buttons_changed()

	def LoadWindow(self):
		import uiScriptLocale

		self.signText = nui_proxies.TextProxy(lambda text: self._publish("owner_sign", text))
		self.renameButton = nui_proxies.ButtonProxy(self._buttons_changed)
		self.posInfoText = nui_proxies.TextProxy(lambda text: self._publish("owner_location", text))
		self.teleportButton = nui_proxies.ButtonProxy(self._buttons_changed)
		self.goldText = nui_proxies.TextProxy(lambda text: self._publish("owner_gold", text))
		self.withdrawButton = nui_proxies.ButtonProxy(self._buttons_changed)
		self.timeLeftText = nui_proxies.TextProxy(lambda text: self._publish("owner_time_text", text))
		self.addTimeButton = nui_proxies.ButtonProxy(self._buttons_changed)
		self.lockButton = nui_proxies.ButtonProxy(self._buttons_changed)
		self.viewLogButton = nui_proxies.ButtonProxy(self._buttons_changed)
		self.closeButton = nui_proxies.ButtonProxy(self._buttons_changed)
		self.renameButton.SetText(uiScriptLocale.OFFLINE_SHOP_BUTTON_RENAME)
		self.teleportButton.SetText(uiScriptLocale.OFFLINE_SHOP_BUTTON_TELEPORT)
		self.withdrawButton.SetText(uiScriptLocale.OFFLINE_SHOP_BUTTON_WITHDRAW)
		self.addTimeButton.SetText(uiScriptLocale.OFFLINE_SHOP_BUTTON_ADD_TIME)
		self.viewLogButton.SetText(uiScriptLocale.OFFLINE_SHOP_BUTTON_VIEW_LOGS)
		self.closeButton.SetText(uiScriptLocale.OFFLINE_SHOP_BUTTON_CLOSE)

		self.renameButton.SetEvent(ui.__mem_func__(self.OnPressChange))
		self.teleportButton.SetEvent(ui.__mem_func__(self.WarpToShop))
		self.withdrawButton.SetEvent(ui.__mem_func__(self.OnPressWithdraw))
		self.addTimeButton.SetEvent(ui.__mem_func__(self.ShopAddTime))
		self.lockButton.SetEvent(ui.__mem_func__(self.SetLock))
		self.viewLogButton.SetEvent(ui.__mem_func__(self.OpenShopLogs))
		self.closeButton.SetEvent(ui.__mem_func__(self.CloseShop))

	def Show(self):
		ui.ScriptWindow.Show(self)
		shop = self._shop()
		if shop is not None:
			shop._owner_visibility(True)

	def Hide(self):
		ui.ScriptWindow.Hide(self)
		shop = self._shop()
		if shop is not None:
			shop._owner_visibility(False)

	def SetTime(self, secondsLeft):
		uiShop.OfflineShopWindow.SetTime(self, secondsLeft)
		shop = self._shop()
		if shop is not None:
			shop._owner_time(secondsLeft)


class ShopDialog(nui_facade.Facade, uiShop.ShopDialog):
	"""``uiShop.ShopDialog`` on NovaUI, including its offline modes."""

	KEY = KEY
	LEAVE_RANGE = True
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
		scale = nui.get_scale() or 1.0
		return (wndMgr.GetScreenWidth() / scale - PLACE_RIGHT, PLACE_TOP)

	def nui_model(self):
		limits = self._limits
		tabs = [{"index": i, "name": "", "down": False, "shown": False}
		        for i in range(limits.SHOP_TAB_COUNT_MAX)]
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
			"offline": False,
			"owner": False,
			"title": "",
			"page_buttons": _page_models(),
			"page_buttons_shown": False,
			"locks": _lock_models(),
			"owner_panel_shown": False,
			"owner_sign": "",
			"owner_location": "",
			"owner_gold": "",
			"owner_time_text": "",
			"owner_time_end": 0.0,
			"owner_lock_text": "",
			"owner_close_shown": False,
		}

	# --- proxy callbacks ---------------------------------------------------------------

	def _real_index(self, slot):
		if getattr(self, "isOfflineShop", False):
			return self.GetOfflineSlot(slot)
		return getattr(self, "tabIdx", 0) * shop.SHOP_SLOT_COUNT + slot

	def _slot_type(self):
		if getattr(self, "isOfflineShop", False):
			return player.SLOT_TYPE_PRIVATE_SHOP
		return player.SLOT_TYPE_PRIVATE_SHOP if shop.IsPrivateShop() else player.SLOT_TYPE_SHOP

	def _on_cells(self, cells):
		events = getattr(self, "_cell_events", None)
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		cells = nui_slots.with_states(cells, states, picked)
		if getattr(self, "isOfflineShop", False) and getattr(self, "offlineIsOwner", False):
			for cell in cells:
				if cell["kind"] and self.IsOfflineSlotInert(self.GetOfflineSlot(cell["index"])):
					cell["disabled"] = True
		self.nui_set(cells=cells)

	def _on_states(self, states, picked):
		cells = nui_slots.with_states(self.itemSlotWindow.cells(), states, picked)
		if self.isOfflineShop and self.offlineIsOwner:
			for cell in cells:
				if cell["kind"] and self.IsOfflineSlotInert(self.GetOfflineSlot(cell["index"])):
					cell["disabled"] = True
		self.nui_set(cells=cells)

	def _on_attaching(self, flag):
		self.nui_set(attaching=flag)

	def _on_buttons(self, button=None):
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
		groups = [("middle", getattr(self, "middleRadioButtonGroup", None)),
		          ("small", getattr(self, "smallRadioButtonGroup", None))]
		group_name, group = "none", None
		for name, candidate in groups:
			if candidate is not None and candidate.shown:
				group_name, group = name, candidate
				break
		buttons = group.buttons() if group is not None else []
		tabs = []
		for index in range(self._limits.SHOP_TAB_COUNT_MAX):
			button = buttons[index] if index < len(buttons) else None
			tabs.append({"index": index, "name": nui.plain_text(button.text) if button is not None else "",
			             "down": bool(button.down) if button is not None else False,
			             "shown": button is not None})
		self.nui_set(tab_group=group_name, tabs=tabs, tab=int(getattr(self, "tabIdx", 0)))

	def _on_pages(self, changed=None):
		pages = [{"index": index, "name": nui.plain_text(button.text), "down": bool(button.down),
		          "shown": bool(button.shown)} for index, button in enumerate(getattr(self, "pageButtons", ()))]
		self.nui_set(page_buttons=pages, page_buttons_shown=any(page["shown"] for page in pages))

	def _owner_text(self, key, text):
		self.nui_set(**{key: nui.plain_text(text)})

	def _owner_buttons_changed(self):
		panel = getattr(self, "offlineShopWnd", None)
		if panel:
			self.nui_set(owner_lock_text=nui.plain_text(panel.lockButton.text),
			             owner_close_shown=bool(panel.closeButton.shown))

	def _owner_visibility(self, shown):
		self.nui_set(owner_panel_shown=bool(shown))
		self._owner_buttons_changed()

	def _owner_time(self, seconds):
		self.nui_set(owner_time_end=nui.now() + max(0, int(seconds)))

	def _owner_time_ended(self):
		panel = getattr(self, "offlineShopWnd", None)
		if panel and panel.IsShow():
			panel.UpdateTime()

	def _press_tab(self, index):
		for name in ("middleRadioButtonGroup", "smallRadioButtonGroup"):
			group = getattr(self, name, None)
			if group is not None and group.shown:
				group.press(index)
				return

	def _press_page(self, index):
		if 0 <= index < len(self.pageButtons):
			self.pageButtons[index].click()

	def _lock_state(self, row):
		for lock in self._state.get("locks", ()):
			if lock["row"] == row:
				return lock["state"]
		return ""

	def _cell_lock(self, index):
		cols = max(1, int(self._state.get("cols", 1)))
		row = index // cols
		return row, self._lock_state(row)

	def _release_lock(self, row):
		if self._lock_state(row) == "next":
			self.OnClickLockOverlay()

	def _over_lock(self, row):
		if self._lock_state(row) == "next":
			self._ShopDialog__ShowKitToolTip()

	def _out_lock(self, row):
		if self._lock_state(row) == "next":
			self.OverOutItem()

	# --- widget loaders ----------------------------------------------------------------

	def LoadDialog(self):
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
		self.board = nui_proxies.BoardProxy(184, 328)
		self.titleBar = nui_proxies.BoardProxy(169, 23)
		self.titleName = nui_proxies.TextProxy(lambda text: self.nui_set(title=nui.plain_text(text)))
		middleTab1, middleTab2 = nui_proxies.ButtonProxy(self._on_tabs), nui_proxies.ButtonProxy(self._on_tabs)
		smallTab1, smallTab2, smallTab3 = [nui_proxies.ButtonProxy(self._on_tabs) for _ in range(3)]
		self.pageButtons = [nui_proxies.ButtonProxy(self._on_pages) for _ in range(_offline_page_count())]
		for index, button in enumerate(self.pageButtons):
			button.SetEvent(ui.__mem_func__(self.SelectOfflinePage), index)
			button.Hide()

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
			[[middleTab1, lambda: self.OnClickTabButton(0), None],
			 [middleTab2, lambda: self.OnClickTabButton(1), None]], on_change=self._on_tabs)
		self._ShopDialog__HideMiddleTabs()
		self._ShopDialog__HideSmallTabs()
		self.tabIdx = 0
		self.coinType = shop.SHOP_COIN_TYPE_GOLD
		self.Refresh()

	def _ShopDialog__EnsureOfflineWidgets(self):
		if not self.offlineShopWnd:
			self.offlineShopWnd = _OfflineShopWindow(self)
		if not self.dlgPickMoney:
			import offlineshopconst
			import uiPickMoney
			dialog = uiPickMoney.PickMoneyDialog()
			dialog.LoadDialog()
			dialog.SetMax(offlineshopconst.WITHDRAW_DIGITS)
			dialog.SetAcceptEvent(ui.__mem_func__(self.OnPickMoney))
			dialog.Hide()
			self.dlgPickMoney = dialog

	def _ShopDialog__ArrangeOffline(self, isOwner):
		import offlineshopconst
		cols, rows, _, _, _ = offlineshopconst.geometry()
		height = self.OFFLINE_PANEL_Y + uiShop.OfflineShopWindow.HEIGHT if isOwner else self.OFFLINE_BUYER_HEIGHT
		self.board.SetSize(self.OFFLINE_WIDTH, height)
		self.titleBar.SetWidth(self.OFFLINE_WIDTH - 15)
		self.itemSlotWindow.ArrangeSlot(0, cols, rows, 32, 32, 0, 0)
		self.itemSlotWindow.SetSlotBaseImage("d:/ymir work/ui/public/Slot_Base.sub", 1.0, 1.0, 1.0, 1.0)
		self.offlineShopWnd.SetPosition(0, self.OFFLINE_PANEL_Y)
		self.offlineLayout = True
		self.nui_set(offline=True, owner=bool(isOwner), cols=cols, tab_group="none",
		             buy_shown=False, sell_shown=False, close_shop_shown=False)

	def _ShopDialog__LeaveOfflineMode(self):
		if not self.offlineLayout:
			return
		self.offlineLayout = False
		width, height, titleWidth, cols = self.NPC_GEOMETRY
		self._ShopDialog__HideOfflineWidgets()
		self.board.SetSize(width, height)
		self.titleBar.SetWidth(titleWidth)
		self.itemSlotWindow.ArrangeSlot(0, cols, shop.SHOP_SLOT_COUNT // cols, 32, 32, 0, 0)
		self.itemSlotWindow.SetSlotBaseImage("d:/ymir work/ui/public/Slot_Base.sub", 1.0, 1.0, 1.0, 1.0)
		self.itemSlotWindow.SetSlotStyle(wndMgr.SLOT_STYLE_NONE)
		self.nui_set(offline=False, owner=False, cols=cols, locks=_lock_models(), page_buttons=_page_models(),
		             page_buttons_shown=False, owner_panel_shown=False, owner_time_end=0.0)
		if self.titleName:
			import uiScriptLocale
			self.titleName.SetText(uiScriptLocale.SHOP_TITLE)

	def _ShopDialog__HideOfflineWidgets(self):
		for button in self.pageButtons:
			button.Hide()
		if self.offlineShopWnd:
			self.offlineShopWnd.Close()
		self.nui_set(locks=_lock_models(), page_buttons_shown=False, owner_panel_shown=False)

	def _ShopDialog__SetOfflineTitle(self, vid):
		import offlineshopconst
		import uiScriptLocale
		title = ""
		boards = getattr(self.interface, "privateShopAdvertisementBoardDict", {}) if self.interface else {}
		board = boards.get(vid) if vid else None
		if board:
			title = getattr(board, "title", "")
			markSeen = getattr(board, "MarkSeen", None)
			if markSeen:
				markSeen()
		if not title and self.offlineIsOwner:
			title = offlineshopconst.owner_panel()["sign"]
		self.titleName.SetText(offlineshopconst.cut(title, offlineshopconst.SHOP_TITLE_MAX)
		                           if title else uiScriptLocale.SHOP_TITLE)

	def _ShopDialog__ShowPageButtons(self, count):
		import uiScriptLocale
		for index, button in enumerate(self.pageButtons):
			if index < count:
				try:
					button.SetText(uiScriptLocale.OFFLINE_SHOP_PAGE_BUTTON % (index + 1))
				except TypeError:
					button.SetText(str(index + 1))
				if index == self.offlinePage:
					button.Down()
				else:
					button.SetUp()
				button.Show()
			else:
				button.Hide()
		self._on_pages()

	def _ShopDialog__UpdateLockOverlays(self):
		import offlineshopconst
		_, rows, _, _, _ = offlineshopconst.geometry()
		unlocked = shop.GetOfflineShopSlotCount()
		expandable = self.offlineIsOwner and offlineshopconst.can_expand(shop.GetOfflineShopExpandCount())
		states = offlineshopconst.lock_rows(self.offlinePage, unlocked, expandable)
		self.nui_set(locks=[{"row": row, "state": states.get(row, "")} for row in range(rows)])

	# --- legacy entry points -----------------------------------------------------------

	def Refresh(self):
		if self.isOfflineShop:
			if self.IsShow() and not self.offlineIsOwner and shop.GetOfflineShopPageCount() < 1:
				self.Close()
				return
			self.RefreshOfflineShop()
			return
		for index in range(shop.SHOP_SLOT_COUNT):
			real = self._ShopDialog__GetRealIndex(index)
			count = shop.GetItemCount(real)
			self.itemSlotWindow.SetItemSlot(index, shop.GetItemID(real), count if count > 1 else 0)
		self.itemSlotWindow.RefreshSlot()
		self._on_tabs()

	def OnClickTabButton(self, idx):
		uiShop.ShopDialog.OnClickTabButton(self, idx)
		self._on_tabs()

	def SelectOfflinePage(self, page):
		uiShop.ShopDialog.SelectOfflinePage(self, page)
		self._on_pages()

	def Open(self, vid, multiPage=False):
		uiShop.ShopDialog.Open(self, vid, multiPage=multiPage)
		if self.IsShow():
			nuigame.WatchLeaveRange(KEY, LEAVE_RANGE, ui.__mem_func__(self._left_range), False)

	def OpenOfflineShop(self, open=1):
		uiShop.ShopDialog.OpenOfflineShop(self, open)
		if self.IsShow() and self.isOfflineShop:
			nuigame.WatchLeaveRange(KEY, LEAVE_RANGE, ui.__mem_func__(self._left_range), False)

	def Hide(self):
		nui_facade.Facade.Hide(self)
		if not self.IsShow():
			nuigame.StopLeaveRange(KEY)

	def _left_range(self):
		self.Close()
