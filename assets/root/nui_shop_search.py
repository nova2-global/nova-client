"""NovaUI facade for the offline-shop search (Wave 5, NOVA-9).

The controller remains :class:`uiSearchShop.SearchShopWindow`.  Its uiscript
loader is the only part replaced: proxy fields, lists, buttons, result rows,
the price filter and the bookmark list publish the state consumed by
``nui/windows/shop-search/shop-search.rml``.  Search queries, paging, filters,
premium checks, buy/go-to/whisper actions and bookmark persistence therefore
stay in the legacy controller.

Legacy polled the player's gold and search-buy perk in ``OnUpdate``.  The
facade has no per-frame Python; a hidden ``nui-countdown`` asks legacy's two
refresh methods once a second while the window is visible.
"""

from _weakref import proxy

import offlineshopconst
import ui
import uiScriptLocale
import uiSearchShop

import nui
import nui_facade
import nui_form_proxies
import nui_hud
import nui_proxies
import nui_slots

DOCUMENT = "nui/windows/shop-search/shop-search.rml"
KEY = "shop-search"
SEARCH_FIELD = "shop-search-name"
FILTER_FIELD = "shop-search-max-price"


def _rooted(path):
	return ("/" + str(path).lstrip("/")) if path else ""


def _button_model(button, index=0):
	return {"index": index, "text": nui.plain_text(button.text), "down": bool(button.down),
	        "shown": bool(button.shown), "enabled": bool(button.enabled)}


class _SearchShopBoard(nui_hud.RaisesOnPress, nui.Window):
	DOCUMENT = DOCUMENT
	MODEL = "shop_search"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)
		if self._doc:
			self.element_on(SEARCH_FIELD, "keydown", self._on_key)
			self.element_on(FILTER_FIELD, "keydown", self._on_key)

	def initial_model(self):
		return dict(self._initial)

	def _on_key(self, event):
		return self._owner._field_key(event.get("target_id"), event.get("key_identifier"))

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.titleBar.close()

	@nui.on("search_change")
	def on_search_change(self, value):
		self._owner._search_changed(value)

	@nui.on("search_press")
	def on_search_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.searchButton.click()

	@nui.on("filter_press")
	def on_filter_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.filterButton.click()

	@nui.on("save_press")
	def on_save_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.saveButton.click()

	@nui.on("bookmarks_press")
	def on_bookmarks_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.listButton.click()

	@nui.on("sort_press")
	def on_sort_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.sortButton.click()

	@nui.on("suggestion_press")
	def on_suggestion_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.suggestionList.pick(int(index))

	@nui.on("category_press")
	def on_category_press(self, key, button):
		self.raise_for(button)
		if button == 0:
			self._owner.categoryList.pick_key(int(key))

	@nui.on("row_release")
	def on_row_release(self, index, button):
		self.raise_for(button)
		row = self._owner.GetRowWidget(int(index))
		if row is None:
			return
		if button == 0:
			row.OnMouseLeftButtonUp()
		elif button == 1:
			row.OnMouseRightButtonUp()

	@nui.on("row_over")
	def on_row_over(self, index):
		row = self._owner.GetRowWidget(int(index))
		if row is not None:
			row.OnMouseOverIn()

	@nui.on("row_out")
	def on_row_out(self, index):
		row = self._owner.GetRowWidget(int(index))
		if row is not None:
			row.OnMouseOverOut()

	@nui.on("icon_over")
	def on_icon_over(self, index):
		row = self._owner.GetRowWidget(int(index))
		if row is not None:
			row.OnOverIcon()

	@nui.on("icon_out")
	def on_icon_out(self, index):
		row = self._owner.GetRowWidget(int(index))
		if row is not None:
			row.OnOutIcon()

	@nui.on("whisper_press")
	def on_whisper_press(self, index, button):
		self.raise_for(button)
		row = self._owner.GetRowWidget(int(index))
		if button == 0 and row is not None:
			row.OnWhisper()

	@nui.on("nav_press")
	def on_nav_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			(self._owner.firstButton, self._owner.prevButton, self._owner.nextButton,
			 self._owner.lastButton)[int(index)].click()

	@nui.on("page_press")
	def on_page_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.pageButtons[int(index)].click()

	@nui.on("size_press")
	def on_size_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.sizeButtons[int(index)].click()

	@nui.on("filter_change")
	def on_filter_change(self, value):
		self._owner.filterWnd.inputValue.typed(value)

	@nui.on("gender_press")
	def on_gender_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			(self._owner.filterWnd.maleButton, self._owner.filterWnd.femaleButton)[int(index)].click()

	@nui.on("filter_apply_press")
	def on_filter_apply_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.filterWnd.applyButton.click()

	@nui.on("filter_cancel_press")
	def on_filter_cancel_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.filterWnd.cancelButton.click()

	@nui.on("bookmark_select")
	def on_bookmark_select(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.bookmarkWnd.Select(int(index))

	@nui.on("bookmark_remove")
	def on_bookmark_remove(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.bookmarkWnd.Remove(int(index))

	@nui.on("panel_close")
	def on_panel_close(self, panel, button):
		self.raise_for(button)
		if button != 0:
			return
		if panel == "filter":
			self._owner.filterWnd.Close()
		elif panel == "bookmarks":
			self._owner.bookmarkWnd.Close()

	@nui.on("status_tick")
	def on_status_tick(self):
		self._owner.nui_status_tick()


class _ListProxy(nui_proxies._Shown):
	"""The two legacy ``ui.ListBox`` instances, as document lists."""

	def __init__(self, owner, kind):
		self.owner = proxy(owner)
		self.kind = kind
		self.items = []
		self.event = None
		self.shown = True
		self.size = (0, 0)
		self._selected = -1

	@property
	def selectedLine(self):
		return self._selected

	@selectedLine.setter
	def selectedLine(self, value):
		self._selected = int(value)
		self._publish()

	def _publish(self):
		self.owner._publish_list(self)

	def SetSize(self, width, height):
		self.size = (int(width), int(height))

	def SetTextCenterAlign(self, centered):
		pass

	def SetEvent(self, event):
		self.event = event

	def ClearItem(self):
		self.items = []
		self._selected = -1
		self._publish()

	def InsertItem(self, key, name):
		self.items.append((int(key), nui.plain_text(name)))
		self._publish()

	def LocateItem(self):
		pass

	def Show(self):
		self.shown = True
		self._publish()

	def Hide(self):
		self.shown = False
		self._publish()

	def pick(self, index):
		if 0 <= index < len(self.items) and self.event:
			key, name = self.items[index]
			self.event(key, name)

	def pick_key(self, key):
		for index, entry in enumerate(self.items):
			if entry[0] == key:
				self._selected = index
				self._publish()
				self.pick(index)
				break


class _ContentProxy(nui_proxies.WindowProxy):
	def GetHeight(self):
		return self.size[1]


class _ScrollProxy(nui_proxies._Shown):
	def SetContentWindow(self, content):
		self.content = content

	def FitWidth(self, width):
		pass

	def OnContentWindowSizeChange(self):
		pass

	def ScrollToStart(self):
		pass

	def OnRunMouseWheel(self, length):
		return True

	def Destroy(self):
		self.content = None


class _SearchResultRow(uiSearchShop.SearchResultRow):
	"""Legacy's row behavior with every widget replaced by a proxy."""

	def __init__(self, owner, index):
		self.owner = proxy(owner)
		self.index = index
		self.row = None
		self.state = ""
		self.buyable = True
		self.shown = False
		self.color = 0
		self.position = (0, 0)
		self.size = (uiSearchShop.ROW_WIDTH, uiSearchShop.ROW_HEIGHT)
		self.icon = nui_proxies.ImageProxy()
		self.nameText = nui_proxies.TextProxy()
		self.countText = nui_proxies.TextProxy()
		self.priceText = nui_proxies.TextProxy()
		self.ownerText = nui_proxies.TextProxy()
		self.whisperButton = nui_proxies.ButtonProxy()
		self.flag = nui_proxies.ImageProxy()
		self.flag.Hide()

	def __del__(self):
		pass

	def SetParent(self, parent):
		self.parent = parent

	def SetPosition(self, x, y):
		self.position = (int(x), int(y))

	def SetSize(self, width, height):
		self.size = (int(width), int(height))

	def SetColor(self, color):
		self.color = int(color) & 0xFFFFFFFF
		self._publish()

	def Show(self):
		self.shown = True
		self._publish()

	def Hide(self):
		self.shown = False
		self._publish()

	def SetRow(self, row, state="", buyable=True):
		uiSearchShop.SearchResultRow.SetRow(self, row, state, buyable)
		self._publish()

	def SetBuyable(self, buyable):
		uiSearchShop.SearchResultRow.SetBuyable(self, buyable)
		self._publish()

	def SetState(self, state):
		uiSearchShop.SearchResultRow.SetState(self, state)
		self._publish()

	def _publish(self):
		owner = self.__dict__.get("owner")
		if owner is not None:
			owner._publish_rows()

	def model(self):
		return {
			"index": self.index,
			"shown": bool(self.shown),
			"name": nui.plain_text(self.nameText.GetText()),
			"stock": nui.plain_text(self.countText.GetText()),
			"price": nui.plain_text(self.priceText.GetText()),
			"owner": nui.plain_text(self.ownerText.GetText()),
			"icon": nui_slots.icon_source(self.icon.image),
			"flag": _rooted(self.flag.image),
			"flag_shown": bool(self.flag.shown and self.flag.image),
			"state": str(self.state or ""),
			"buyable": bool(self.buyable),
		}


class _SearchFilterWindow(uiSearchShop.SearchFilterWindow):
	"""Legacy filter logic; its board is a panel in the owner's document."""

	def _main(self):
		return self.__dict__.get("owner")

	def _SearchFilterWindow__LoadWindow(self):
		self.titleBar = nui_proxies.BoardProxy()
		self.inputValue = nui_form_proxies.FieldProxy(FILTER_FIELD, self._field_changed)
		self.inputValue.reader = self._read_field
		self.maleButton = nui_proxies.ToggleButtonProxy(self._changed)
		self.femaleButton = nui_proxies.ToggleButtonProxy(self._changed)
		self.applyButton = nui_proxies.ButtonProxy()
		self.cancelButton = nui_proxies.ButtonProxy()
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))
		self.applyButton.SetEvent(ui.__mem_func__(self.Apply))
		self.cancelButton.SetEvent(ui.__mem_func__(self.Close))
		self.inputValue.SetEscapeEvent(ui.__mem_func__(self.Close))
		self.maleButton.SetToggleDownEvent(lambda: self.SetGender(True, self.female))
		self.maleButton.SetToggleUpEvent(lambda: self.SetGender(False, self.female))
		self.femaleButton.SetToggleDownEvent(lambda: self.SetGender(self.male, True))
		self.femaleButton.SetToggleUpEvent(lambda: self.SetGender(self.male, False))
		self.maleButton.Down()
		self.femaleButton.Down()

	def _read_field(self):
		owner = self._main()
		board = owner.nui_board() if owner is not None else None
		return board.get_value(FILTER_FIELD) if board is not None and board.is_visible() else None

	def _field_changed(self, field, what):
		owner = self._main()
		board = owner.nui_board() if owner is not None else None
		if board is not None and board.is_visible() and what == "text":
			board.set_value(FILTER_FIELD, field.text, caret="end", even_hidden=True)

	def _changed(self, button=None):
		owner = self._main()
		if owner is not None:
			owner._publish_filter()

	def SetGender(self, male, female):
		uiSearchShop.SearchFilterWindow.SetGender(self, male, female)
		self._changed()

	def Show(self):
		self.shown = True
		owner = self._main()
		if owner is not None:
			owner._publish_filter()
			board = owner.nui_board()
			if board is not None:
				board.set_value(FILTER_FIELD, self.inputValue.text or "", caret="end", even_hidden=True)

	def Hide(self):
		self.shown = False
		owner = self._main()
		if owner is not None:
			owner._publish_filter()

	def IsShow(self):
		return bool(self.__dict__.get("shown", False))

	def SetTop(self):
		pass


class _BookmarkBar(nui_proxies.WindowProxy):
	def __init__(self):
		nui_proxies.WindowProxy.__init__(self)
		self.event = None

	def SetColor(self, color):
		pass

	def SetOnMouseLeftButtonUpEvent(self, event):
		self.event = event


class _SearchBookmarkWindow(uiSearchShop.SearchBookmarkWindow):
	"""Legacy bookmark persistence; its list is a panel in the document."""

	def _main(self):
		return self.__dict__.get("owner")

	def _SearchBookmarkWindow__LoadWindow(self):
		self.board = nui_proxies.BoardProxy(230, 255)
		self.titleBar = nui_proxies.BoardProxy()
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))
		for index in range(offlineshopconst.SEARCH_BOOKMARK_MAX):
			bar = _BookmarkBar()
			text = nui_proxies.TextProxy(lambda value, i=index: self._line_changed(i, value))
			remove = nui_proxies.ButtonProxy()
			bar.SetOnMouseLeftButtonUpEvent(lambda arg=index: self.Select(arg))
			remove.SetEvent(lambda arg=index: self.Remove(arg))
			self.lines.append((bar, text, remove))

	def _line_changed(self, index, value):
		owner = self._main()
		if owner is not None:
			owner._publish_bookmarks()

	def Refresh(self):
		uiSearchShop.SearchBookmarkWindow.Refresh(self)
		owner = self._main()
		if owner is not None:
			owner._publish_bookmarks()

	def Show(self):
		self.shown = True
		owner = self._main()
		if owner is not None:
			owner._publish_bookmarks()

	def Hide(self):
		self.shown = False
		owner = self._main()
		if owner is not None:
			owner._publish_bookmarks()

	def IsShow(self):
		return bool(self.__dict__.get("shown", False))

	def SetTop(self):
		pass


class SearchShopWindow(nui_facade.Facade, uiSearchShop.SearchShopWindow):
	"""``uiSearchShop.SearchShopWindow`` on NovaUI."""

	KEY = KEY
	BOARD = _SearchShopBoard
	PLACE = "center"

	def __init__(self):
		self.nui_begin()
		try:
			uiSearchShop.SearchShopWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			"rows": [], "categories": [], "suggestions": [], "suggestions_shown": False,
			"pages": [], "sizes": [], "nav_shown": False, "current_page": 0, "page_count": 0,
			"loading": False, "empty": False, "sort_ascending": True, "sort_text": "",
			"gold": "", "premium": "", "can_buy": False,
			"filter_open": False, "filter_male": True, "filter_female": True,
			"bookmarks_open": False, "bookmarks": [], "status_end": 0.0,
		}

	# --- proxy publication --------------------------------------------------------------

	def _publish_list(self, listing):
		if listing.kind == "suggestions":
			self.nui_set(suggestions=[{"index": i, "name": name} for i, (_, name) in enumerate(listing.items)],
			             suggestions_shown=bool(listing.shown and listing.items))
		else:
			self.nui_set(categories=[{"key": key, "name": name, "selected": i == listing.selectedLine}
			                         for i, (key, name) in enumerate(listing.items)])

	def _publish_rows(self):
		pool = self.__dict__.get("rowPool", ())
		rows = [row.model() for row in pool if row.shown]
		self.nui_set(rows=rows, empty=bool(not rows and not self.__dict__.get("isLoading", False)))

	def _publish_pages(self, button=None):
		pages = [_button_model(value, i) for i, value in enumerate(self.__dict__.get("pageButtons", ()))]
		sizes = [_button_model(value, i) for i, value in enumerate(self.__dict__.get("sizeButtons", ()))]
		nav = self.__dict__.get("firstButton")
		self.nui_set(pages=pages, sizes=sizes, nav_shown=bool(nav and nav.shown),
		             current_page=int(self.__dict__.get("currentPage", 0)),
		             page_count=int(self.__dict__.get("pageCount", 0)))

	def _publish_sort(self, button=None):
		button = self.__dict__.get("sortButton")
		self.nui_set(sort_ascending=bool(self.__dict__.get("ascending", True)),
		             sort_text=nui.plain_text(button.text if button is not None else ""))

	def _publish_loading(self, shown):
		self.nui_set(loading=bool(shown), empty=bool(not shown and not self.__dict__.get("shownRows", ())))

	def _publish_status(self):
		premium = self.__dict__.get("premiumText")
		gold = self.__dict__.get("goldText")
		self.nui_set(premium=nui.plain_text(premium.text if premium else ""),
		             gold=nui.plain_text(gold.text if gold else ""), can_buy=bool(self.CanBuy()))

	def _publish_filter(self):
		window = self.__dict__.get("filterWnd")
		if window is not None:
			self.nui_set(filter_open=window.IsShow(), filter_male=bool(window.male),
			             filter_female=bool(window.female))

	def _publish_bookmarks(self):
		window = self.__dict__.get("bookmarkWnd")
		if window is None:
			return
		values = []
		for index, name in enumerate(window.names):
			values.append({"index": index, "name": nui.plain_text(name or uiScriptLocale.SEARCH_SHOP_BOOKMARK_EMPTY),
			               "empty": not bool(name)})
		self.nui_set(bookmarks_open=window.IsShow(), bookmarks=values)

	def _read_search(self):
		board = self.nui_board()
		return board.get_value(SEARCH_FIELD) if board is not None and board.is_visible() else None

	def _field_changed(self, field, what):
		board = self.nui_board()
		if board is None or not board.is_visible():
			return
		if what == "text":
			board.set_value(SEARCH_FIELD, field.text, caret="end")
		elif what == "focus":
			board.focus(SEARCH_FIELD)

	def _search_changed(self, value):
		self.inputName.typed(value)
		names = self.GetSuggestions(self.inputName.GetText())
		self.suggestionList.ClearItem()
		for index, name in enumerate(names):
			self.suggestionList.InsertItem(index, name)
		if names:
			self.suggestionList.Show()
		else:
			self.suggestionList.Hide()

	def _field_key(self, field_id, key):
		if key in ("RETURN", "NUMPADENTER", "KP_ENTER"):
			if field_id == SEARCH_FIELD:
				return self.inputName.fire_return()
			if field_id == FILTER_FIELD:
				return self.filterWnd.Apply()
		if key == "ESCAPE":
			if field_id == FILTER_FIELD:
				return self.filterWnd.inputValue.fire_escape()
			return self.inputName.fire_escape()
		return None

	# --- legacy loader, with proxies -----------------------------------------------------

	def _SearchShopWindow__LoadWindow(self):
		if self.isLoaded:
			return
		self.isLoaded = True
		self.board = nui_proxies.BoardProxy(760, 540)
		self.titleBar = nui_proxies.BoardProxy(747, 23)
		self.inputName = nui_form_proxies.FieldProxy(SEARCH_FIELD, self._field_changed)
		self.inputName.reader = self._read_search
		self.searchButton = nui_proxies.ButtonProxy()
		self.filterButton = nui_proxies.ButtonProxy()
		self.saveButton = nui_proxies.ButtonProxy()
		self.listButton = nui_proxies.ButtonProxy()
		self.sortButton = nui_proxies.ToggleButtonProxy(self._publish_sort)
		self.goldText = nui_proxies.TextProxy(lambda value: self._publish_status())
		self.premiumText = nui_proxies.TextProxy(lambda value: self._publish_status())
		self.shownCanBuy = None
		self.shownGold = None
		self.itemBarList = _ContentProxy()
		self.loadingText = nui_proxies.TextProxy()
		self.loadingText.on_show = self._publish_loading
		self.firstButton = nui_proxies.ButtonProxy(self._publish_pages)
		self.prevButton = nui_proxies.ButtonProxy(self._publish_pages)
		self.nextButton = nui_proxies.ButtonProxy(self._publish_pages)
		self.lastButton = nui_proxies.ButtonProxy(self._publish_pages)
		self.pageButtons = [nui_proxies.ButtonProxy(self._publish_pages)
		                    for unused in range(offlineshopconst.SEARCH_PAGE_BUTTONS)]
		self.sizeButtons = [nui_proxies.ButtonProxy(self._publish_pages)
		                    for unused in offlineshopconst.SEARCH_PAGE_SIZES]

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))
		self.inputName.SetReturnEvent(ui.__mem_func__(self.Search))
		self.inputName.SetEscapeEvent(ui.__mem_func__(self.Close))
		self.searchButton.SetEvent(ui.__mem_func__(self.Search))
		self.filterButton.SetEvent(ui.__mem_func__(self.OpenFilter))
		self.saveButton.SetEvent(ui.__mem_func__(self.SaveBookmark))
		self.listButton.SetEvent(ui.__mem_func__(self.OpenBookmarks))
		self.sortButton.SetToggleDownEvent(lambda: self.SetSortAscending(False))
		self.sortButton.SetToggleUpEvent(lambda: self.SetSortAscending(True))
		self.firstButton.SetEvent(lambda: self.GoToPage(0))
		self.prevButton.SetEvent(lambda: self.GoToPage(self.currentPage - 1))
		self.nextButton.SetEvent(lambda: self.GoToPage(self.currentPage + 1))
		self.lastButton.SetEvent(lambda: self.GoToPage(self.pageCount - 1))
		for index, button in enumerate(self.pageButtons):
			button.SetEvent(lambda arg=index: self.SelectPageButton(arg))
		for index, button in enumerate(self.sizeButtons):
			button.SetEvent(lambda arg=index: self.SetResultPerPage(arg))

		self.suggestionList = _ListProxy(self, "suggestions")
		self.suggestionList.SetEvent(ui.__mem_func__(self._SearchShopWindow__OnSelectSuggestion))
		self.suggestionList.Hide()
		self.categoryList = _ListProxy(self, "categories")
		self.categoryList.SetEvent(ui.__mem_func__(self._SearchShopWindow__OnSelectCategoryEntry))
		self.scrollWindow = _ScrollProxy()
		self.scrollWindow.SetContentWindow(self.itemBarList)
		self.filterWnd = _SearchFilterWindow(self)
		self.filterWnd.Hide()
		self.bookmarkWnd = _SearchBookmarkWindow(self)
		self.bookmarkWnd.Hide()
		self.loadingText.Hide()
		self._SearchShopWindow__FillCategories()
		self._SearchShopWindow__RefreshPageButtons()

	def _SearchShopWindow__GetRow(self, index):
		while index >= len(self.rowPool):
			self.rowPool.append(_SearchResultRow(self, len(self.rowPool)))
		return self.rowPool[index]

	# --- lifecycle and the replacement for legacy OnUpdate -----------------------------

	def Open(self, vnum=0):
		uiSearchShop.SearchShopWindow.Open(self, vnum)
		self._sync_fields()
		self._publish_rows()
		self._publish_pages()
		self._publish_sort()
		self._publish_filter()
		self._publish_bookmarks()
		self._arm_status()

	def _sync_fields(self):
		board = self.nui_board()
		field = self.__dict__.get("inputName")
		if board is not None and field is not None:
			board.set_value(SEARCH_FIELD, field.text or "", caret="end", even_hidden=True)

	def Show(self):
		# Real ui.Window.__init__ calls Hide before SearchShopWindow.__init__ has
		# made its attributes.  Keep this override safe for that path and for an
		# object made with __new__ (the regression test exercises the latter).
		if "demand" not in self.__dict__:
			return
		nui_facade.Facade.Show(self)
		self._sync_fields()

	def Hide(self):
		if "demand" not in self.__dict__:
			return
		nui_facade.Facade.Hide(self)
		if not self.IsShow():
			self.nui_set(status_end=0.0)

	def _arm_status(self):
		if self.IsShow():
			self.nui_set(status_end=nui.now() + 1.0)

	def nui_status_tick(self):
		if not self.IsShow():
			return
		self.RefreshGold()
		self.RefreshPremium()
		self._publish_status()
		self._publish_rows()
		self._arm_status()
