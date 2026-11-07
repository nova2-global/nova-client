"""NovaUI offline shop log (nui/windows/offline-shop-log/offline-shop-log.rml;
Wave 5, NOVA-9).

While the offline-shop-log flag is on, Interface.__MakeWindows makes
OfflineShopLogWindow below through nui_windows.make() instead of
uiOfflineShopLog.OfflineShopLogWindow: a subclass of the legacy class
(nui_facade.Facade) whose loader puts proxies where the widgets were (the
title bar, the rows' window, the loading and empty texts, the scroll window)
and whose row maker (__MakeRow) makes a row of proxies. So the pages asked
(CG LOGS), the answers appended (SetData, offlineshopconst.log_row's texts),
the end of the view asking for the next page once, a refused page
(OnLogsResult) and the states (loading, empty, last) are legacy's code.

The scroll is the board's: the rows show VIEW_ROWS at a time (legacy's 425
pixel view of 20 pixel rows), moved by the bar and the wheel; a user's scroll
that reaches the end runs legacy's OnEndScroll once, a content that grows
keeps its first row, and ScrollToStart runs no event, as ui.ScrollWindow.

No Python per frame: legacy's retry of a page refused as too soon (OnUpdate,
LOG_RETRY_SEC later) is a nui-countdown timer's countdownend, which runs
legacy's OnUpdate once. The board exists only while the window shows."""

import app
import ui
import uiOfflineShopLog
import wndMgr

import nui
import nui_facade
import nui_hud
import nui_proxies

DOCUMENT = "nui/windows/offline-shop-log/offline-shop-log.rml"
KEY = "offline-shop-log"
ROW_HEIGHT = uiOfflineShopLog.ROW_HEIGHT
# Legacy's view: SCROLL_SIZE's 425 pixels of 20 pixel rows.
VIEW_ROWS = uiOfflineShopLog.SCROLL_SIZE[1] // ROW_HEIGHT
# ui.ScrollWindow.WHEEL_STEP: a wheel turn moves the bar by a tenth.
WHEEL_STEP = 0.10
# Half again the scroll range's step (step="0.001" in the document): a value
# this close to the shown place is the range answering the model.
ECHO = 0.0015
# Legacy's place (offlineshoplogwindow.py: SCREEN_WIDTH - 540 for a 520 wide
# board): the right edge 20 from the screen's, the top 60 down.
RIGHT_GAP_DP = 20
TOP_DP = 60


class _LogBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The log's document; its events go to its window. A press on it raises
	the window, as legacy's window manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "offline_shop_log"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.titleBar.close()

	@nui.on("scroll")
	def on_scroll(self, value):
		self._owner.scrollWindow.user_scroll(value)

	@nui.on("wheel")
	def on_wheel(self, delta):
		# RmlUi's sign: positive is down; legacy's OnScrollWheel: negative is down.
		if delta:
			self._owner.OnScrollWheel(-1 if delta > 0 else 1)

	@nui.on("retry")
	def on_retry(self):
		self._owner.nui_retry()


class _LogRow(uiOfflineShopLog.LogRow):
	"""Legacy's row (SetInfo, GetTexts) on five text proxies."""

	def __init__(self, index):
		self.index = index
		self.shown = False
		self.texts = [nui_proxies.TextProxy() for _ in uiOfflineShopLog.COLUMNS]

	def __del__(self):
		pass

	def SetParent(self, parent):
		pass

	def SetPosition(self, x, y):
		pass

	def Show(self):
		self.shown = True

	def Hide(self):
		self.shown = False

	def model(self):
		action, other, what, amount, date = [nui.plain_text(text.GetText()) for text in self.texts]
		return {"action": action, "other": other, "what": what, "amount": amount, "date": date,
		        "odd": bool(self.index % 2)}


class _LogScroll(nui_proxies._Shown):
	"""ui.ScrollWindow over the board's rows, counted in rows: `top` is the
	first row shown. The user's scroll (the bar, the wheel) runs the end
	event once each time it reaches the end; the program's moves
	(OnContentWindowSizeChange, ScrollToStart) run none."""

	def __init__(self, owner):
		self.owner = nui_hud.keep_weakly(owner)
		self.content = None
		self.top = 0
		self.end_event = None
		self.end_reached = False

	def SetContentWindow(self, content):
		self.content = content
		self.OnContentWindowSizeChange()
		self.ScrollToStart()

	def FitWidth(self, width):
		pass

	def SetOnEndScrollEvent(self, event):
		self.end_event = event

	def Destroy(self):
		self.content = None
		self.end_event = None

	def count(self):
		if self.content is None:
			return 0
		return max(0, int(self.content.size[1]) // ROW_HEIGHT)

	def scroll_range(self):
		return max(0, self.count() - VIEW_ROWS)

	def pos(self):
		scroll_range = self.scroll_range()
		return float(self.top) / scroll_range if scroll_range else 0.0

	def OnContentWindowSizeChange(self):
		self._move(self.top)

	def ScrollToStart(self):
		self._move(0)

	def OnRunMouseWheel(self, length):
		if not self.scroll_range():
			return False
		self.user_scroll(self.pos() + (WHEEL_STEP if length < 0 else -WHEEL_STEP))
		return True

	def user_scroll(self, value):
		"""The bar or the wheel (ScrollWindow.__OnScroll)."""
		try:
			pos = max(0.0, min(1.0, float(value)))
		except (TypeError, ValueError):
			return
		scroll_range = self.scroll_range()
		at_end = scroll_range > 0 and pos >= 1.0
		if not at_end and abs(pos - self.pos()) < ECHO:
			# The range's echo of the program's move (its value rounded to its step).
			return
		self.top = int(round(scroll_range * pos))
		self._publish()
		if at_end and not self.end_reached:
			self.end_reached = True
			if self.end_event:
				self.end_event()
		elif not at_end:
			self.end_reached = False

	def _move(self, top):
		scroll_range = self.scroll_range()
		self.top = max(0, min(scroll_range, int(top)))
		self.end_reached = self.top >= scroll_range
		self._publish()

	def _publish(self):
		owner = self.owner
		if owner is not None:
			owner._publish_rows()


class OfflineShopLogWindow(nui_facade.Facade, uiOfflineShopLog.OfflineShopLogWindow):
	"""uiOfflineShopLog.OfflineShopLogWindow on NovaUI (Interface.wndOfflineShopLog)."""

	KEY = KEY
	BOARD = _LogBoard
	OnUpdate = None

	def __init__(self):
		self.nui_begin()
		try:
			uiOfflineShopLog.OfflineShopLogWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			"rows": [],
			"scroll": 0.0,
			"scrollable": False,
			"loading": False,
			"empty": False,
			# Legacy's retry of a page refused as too soon (nui.now() + seconds; 0: none).
			"retry_end": 0.0,
		}

	def _restore_board(self, board):
		"""The kept place, else legacy's: the right edge RIGHT_GAP_DP from the
		screen's, TOP_DP down (the sheet's place frames the snapshots)."""
		nui_facade.Facade._restore_board(self, board)
		if self._place is None:
			scale = nui.get_scale() or 1.0
			board.set_position(wndMgr.GetScreenWidth() / scale - RIGHT_GAP_DP, TOP_DP, origin=(1.0, 0.0))

	# --- the loader (uiofflineshoplog.py __LoadWindow, on proxies) -----------------------

	def _OfflineShopLogWindow__LoadWindow(self):
		if self.isLoaded:
			return
		self.isLoaded = True
		# The uiscript's style (offlineshoplogwindow.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		self.board = nui_proxies.BoardProxy(520, 480)
		self.titleBar = nui_proxies.BoardProxy(505, 21)
		self.logsWindow = nui_proxies.WindowProxy()
		self.logsWindow.SetSize(uiOfflineShopLog.ROW_WIDTH, 1)
		self.loadingText = nui_proxies.TextProxy(text="...")
		self.loadingText.on_show = lambda shown: self._publish_state()
		self.emptyText = nui_proxies.TextProxy(text="-")
		self.emptyText.on_show = lambda shown: self._publish_state()
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))

		self.scrollWindow = _LogScroll(self)
		self.scrollWindow.SetContentWindow(self.logsWindow)
		self.scrollWindow.FitWidth(uiOfflineShopLog.ROW_WIDTH)
		self.scrollWindow.SetOnEndScrollEvent(ui.__mem_func__(self.OnEndScroll))
		self.scrollWindow.Show()

	def _OfflineShopLogWindow__MakeRow(self, index):
		return _LogRow(index)

	# --- what NovaUI changes -----------------------------------------------------------

	def Show(self):
		"""The facade's; a retry legacy's OnUpdate would resume runs again."""
		nui_facade.Facade.Show(self)
		self._arm_retry()

	def Hide(self):
		nui_facade.Facade.Hide(self)
		if not self.IsShow() and self.__dict__.get("_state") is not None:
			self.nui_set(retry_end=0.0)

	def OnLogsResult(self, code):
		"""Legacy's; a retry it set (retryTime) is the timer's end."""
		quiet = uiOfflineShopLog.OfflineShopLogWindow.OnLogsResult(self, code)
		self._arm_retry()
		return quiet

	def SetData(self, rows, page, last):
		uiOfflineShopLog.OfflineShopLogWindow.SetData(self, rows, page, last)
		self._arm_retry()

	def Close(self):
		uiOfflineShopLog.OfflineShopLogWindow.Close(self)
		self._arm_retry()

	def _arm_retry(self):
		if self.__dict__.get("_state") is None:
			return
		retry = self.__dict__.get("retryTime", 0)
		if not retry or not self.IsShow():
			self.nui_set(retry_end=0.0)
			return
		left = max(0.0, retry - app.GetTime())
		self.nui_set(retry_end=nui.now() + left + 0.05)

	def nui_retry(self):
		"""The timer's countdownend: legacy's OnUpdate once (it asks the page
		again when its time came), and the timer again if it did not."""
		if not self.IsShow() or not self.__dict__.get("retryTime", 0):
			return
		uiOfflineShopLog.OfflineShopLogWindow.OnUpdate(self)
		self._arm_retry()

	# --- the board's model -------------------------------------------------------------

	def _publish_rows(self):
		if self.__dict__.get("_state") is None:
			return
		scroll = self.__dict__.get("scrollWindow")
		rows = self.__dict__.get("rows") or []
		top = scroll.top if scroll is not None else 0
		self.nui_set(rows=[row.model() for row in rows[top:top + VIEW_ROWS]],
		             scroll=scroll.pos() if scroll is not None else 0.0,
		             scrollable=bool(scroll is not None and scroll.scroll_range()))

	def _publish_state(self):
		if self.__dict__.get("_state") is None:
			return
		loading = self.__dict__.get("loadingText")
		empty = self.__dict__.get("emptyText")
		self.nui_set(loading=bool(loading is not None and loading.IsShow()),
		             empty=bool(empty is not None and empty.IsShow()))
