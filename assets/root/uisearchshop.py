"""The shop search (NOVA-9; OLD uiSearchShop.py, spec 3.8): every offline shop's listings, by an
item's name or by a category, on every core.

The Interface makes it (wndSearchShop) and opens it from the inventory's
Search button or with an item (Ctrl + click: Open(vnum)). A search sends
CG SHOP_SEARCH QUERY; the client gathers the RESULTS frames and, on the last
one, calls RefreshSearchShop, which reaches RefreshItems(): the rows go into
the C++ index (searchShop.LoadResults), sorted by price, shown a page at a
time. A row buys (CG BUY, with the expected item id and price; its answer is
OnBuyResult), goes to the shop (GOTO), or whispers its owner.

What changed from OLD (o-cli bugs fixed):
- the name lookup is searchShop.Find(name), the C++ index, which knows every
  vnum of a name (bug 21: OLD copied the item map into a dict at import, one
  vnum per name);
- a shop on a map with no empire flag shows none (bug 7: OLD raised KeyError);
- the premium label and the buy gate both read the SEARCH_BUY perk, through
  OLD's own SEARCH_SHOP_PREMIMUM_ACTIVE / _INACTIVE keys (bug 8, PB-C6: OLD
  showed "Active" for Silver and refused its buy);
- no app.ENABLE_* gate and no C++ call at import: the index is built when the
  window opens first.
OLD's 3D preview (Alt) and pet preview (Tab) have no host in NEW (D15) and are
not ported, nor is OLD's "Buy VIP" button (/in_game_mall has no host)."""

import ui
import net
import app
import chat
import item
import skill
import player
import localeInfo
import uiScriptLocale
import uiCommon
import offlineshopconst

ROW_WIDTH = 531
ROW_HEIGHT = 36
ROW_COLORS = (0xff131313, 0xff0c0c0c)
ROW_OVER_COLOR = 0xff272727
ROW_SOLD_COLOR = 0xff400703
ROW_PENDING_COLOR = 0xff2b2b10
NAME_COLOR = 0xffb3977c
# A row's item without the SEARCH_BUY perk (spec 3.8: the buy grayed by the perk, PB-C6).
NO_BUY_COLOR = 0xff6a6a6a
RESULTS_POSITION = (190, 64)
RESULTS_SIZE = (556, 420)
CATEGORY_POSITION = (16, 70)
CATEGORY_SIZE = (162, 408)
SUGGESTION_POSITION = (14, 56)
SUGGESTION_WIDTH = 200
SUGGESTION_STEP = 17
BOOKMARK_STEP = 21

# A category list entry's key: the category (1..13) and its subcategory (0: none).
def _category_key(index, sub):
	return index * 100 + sub


def _split_category_key(key):
	return key // 100, key % 100


class SearchResultRow(ui.Bar):
	"""One result: the icon, the name (a skill book by its skill), the count in stock, the price
	in its color, the owner, a whisper button and the empire flag of the shop's map."""

	def __init__(self, owner, index):
		ui.Bar.__init__(self)
		from _weakref import proxy
		self.owner = proxy(owner)
		self.index = index
		self.row = None
		self.state = ""        # "", "pending" (a buy was sent) or "sold"
		self.buyable = True
		self.SetSize(ROW_WIDTH, ROW_HEIGHT)

		self.icon = ui.ExpandedImageBox()
		self.icon.SetParent(self)
		self.icon.SetPosition(4, 2)
		self.icon.SAFE_SetStringEvent("MOUSE_OVER_IN", self.OnOverIcon)
		self.icon.SAFE_SetStringEvent("MOUSE_OVER_OUT", self.OnOutIcon)
		self.icon.Show()

		self.nameText = self.__MakeText(44, 4)
		self.countText = self.__MakeText(44, 19)
		self.priceText = self.__MakeText(250, 11)
		self.ownerText = self.__MakeText(370, 11)

		self.whisperButton = ui.Button()
		self.whisperButton.SetParent(self)
		self.whisperButton.SetPosition(470, 8)
		self.whisperButton.SetUpVisual("d:/ymir work/ui/public/xsmall_button_01.sub")
		self.whisperButton.SetOverVisual("d:/ymir work/ui/public/xsmall_button_02.sub")
		self.whisperButton.SetDownVisual("d:/ymir work/ui/public/xsmall_button_03.sub")
		self.whisperButton.SetText("@")
		self.whisperButton.SetEvent(ui.__mem_func__(self.OnWhisper))
		self.whisperButton.Show()

		self.flag = ui.ExpandedImageBox()
		self.flag.SetParent(self)
		self.flag.AddFlag("not_pick")
		self.flag.SetPosition(500, 8)
		self.flag.Hide()

	def __del__(self):
		ui.Bar.__del__(self)

	def __MakeText(self, x, y):
		text = ui.TextLine()
		text.SetParent(self)
		text.SetPosition(x, y)
		text.SetPackedFontColor(NAME_COLOR)
		text.Show()
		return text

	def Destroy(self):
		self.row = None
		self.icon = None
		self.nameText = None
		self.countText = None
		self.priceText = None
		self.ownerText = None
		self.whisperButton = None
		self.flag = None

	def SetRow(self, row, state="", buyable=True):
		"""`row`: offlineshopconst.search_row's dict; `buyable`: the SEARCH_BUY perk (SetBuyable)."""
		self.row = row
		self.state = state
		self.nameText.SetText(ItemName(row["vnum"], row["sockets"]))
		try:
			self.countText.SetText(localeInfo.SEARCH_SHOP_IN_STOCK % str(row["count"]))
		except TypeError:
			self.countText.SetText(str(row["count"]))
		self.priceText.SetText(localeInfo.NumberToMoneyString(row["price"]))
		self.priceText.SetPackedFontColor(PriceColor(row["price"]))
		self.ownerText.SetText(row["owner_name"])
		item.SelectItem(row["vnum"])
		self.icon.LoadImage(item.GetIconImageFileName())
		flag = offlineshopconst.flag_image(row["map"])
		if flag:
			self.flag.LoadImage(flag)
			self.flag.SetScale(offlineshopconst.EMPIRE_FLAG_SCALE, offlineshopconst.EMPIRE_FLAG_SCALE)
			self.flag.Show()
		else:
			self.flag.Hide()
		self.SetBuyable(buyable)
		self.Show()

	def SetBuyable(self, buyable):
		"""Without the SEARCH_BUY perk the item's name and stock are grayed (spec 3.8, PB-C6): a
		left press only says why (AskBuy). The price keeps its color; go-to and whisper work."""
		self.buyable = bool(buyable)
		color = NAME_COLOR if self.buyable else NO_BUY_COLOR
		self.nameText.SetPackedFontColor(color)
		self.countText.SetPackedFontColor(color)
		self.RefreshColor()

	def IsBuyable(self):
		return self.buyable

	def SetState(self, state):
		self.state = state
		self.RefreshColor()

	def GetFlagImage(self):
		return offlineshopconst.flag_image(self.row["map"]) if self.row else ""

	def RefreshColor(self, over=False):
		if self.state == "sold":
			self.SetColor(ROW_SOLD_COLOR)
		elif self.state == "pending":
			self.SetColor(ROW_PENDING_COLOR)
		elif over:
			self.SetColor(ROW_OVER_COLOR)
		else:
			self.SetColor(ROW_COLORS[self.index % 2])

	def OnMouseOverIn(self):
		self.RefreshColor(True)

	def OnMouseOverOut(self):
		self.RefreshColor()

	def OnOverIcon(self):
		self.owner.ShowRowToolTip(self.row)

	def OnOutIcon(self):
		self.owner.HideRowToolTip()

	## Left: buy (OLD :1215-1228). Right: go to the shop (OLD :1230-1240).
	def OnMouseLeftButtonUp(self):
		if self.row:
			self.owner.AskBuy(self.row)
		return True

	def OnMouseRightButtonUp(self):
		if self.row:
			self.owner.AskGoTo(self.row)
		return True

	def OnWhisper(self):
		if self.row:
			self.owner.WhisperOwner(self.row)


def ItemName(vnum, sockets=()):
	"""An item's name; a skill book or a forget book with its skill (OLD :1166-1180)."""
	if vnum in (offlineshopconst.SKILL_BOOK_VNUM, offlineshopconst.FORGET_BOOK_VNUM):
		skillIndex = sockets[0] if sockets else 0
		bookName = localeInfo.TOOLTIP_SKILLBOOK_NAME if vnum == offlineshopconst.SKILL_BOOK_VNUM else localeInfo.TOOLTIP_SKILL_FORGET_BOOK_NAME
		if skillIndex:
			return "%s %s" % (skill.GetSkillName(skillIndex), bookName)
		return bookName
	item.SelectItem(vnum)
	return item.GetItemName()


def PriceColor(price):
	"""The price's color from the C++ index (spec 5.6: > 5e9 red, > 1e9 orange, > 1e8 yellow)."""
	import searchShop
	return searchShop.GetPriceColor(price)


class SearchFilterWindow(ui.ScriptWindow):
	"""The most a row may cost and the items' gender (OLD :784-882)."""

	def __init__(self, owner):
		ui.ScriptWindow.__init__(self)
		from _weakref import proxy
		self.owner = proxy(owner)
		self.male = True
		self.female = True
		self.__LoadWindow()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/searchshopfilter.py")
		except:
			import exception
			exception.Abort("SearchFilterWindow.LoadWindow.LoadObject")

		try:
			GetObject = self.GetChild
			self.titleBar = GetObject("TitleBar")
			self.inputValue = GetObject("InputValue")
			self.maleButton = GetObject("maleButton")
			self.femaleButton = GetObject("femaleButton")
			self.applyButton = GetObject("applybtn")
			self.cancelButton = GetObject("cancelbtn")
		except:
			import exception
			exception.Abort("SearchFilterWindow.LoadWindow.BindObject")

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

	def Destroy(self):
		self.ClearDictionary()
		self.owner = None

	def Open(self):
		self.Show()
		self.SetTop()

	def Close(self):
		self.Hide()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def SetGender(self, male, female):
		self.male = bool(male)
		self.female = bool(female)

	def Apply(self):
		import uiPickMoney
		maxPrice = uiPickMoney.ConvertTextToMoney(self.inputValue.GetText()) if self.inputValue.GetText() else 0
		self.owner.ApplyFilter(maxPrice, self.male, self.female)
		self.Close()


class SearchBookmarkWindow(ui.ScriptWindow):
	"""Ten saved names (OLD :1258-1382) in shop/bookmark_list.txt; a click fills the name field. A
	missing or unwritable file never stops the window."""

	def __init__(self, owner):
		ui.ScriptWindow.__init__(self)
		from _weakref import proxy
		self.owner = proxy(owner)
		self.names = [""] * offlineshopconst.SEARCH_BOOKMARK_MAX
		self.lines = []
		self.__LoadWindow()
		self.names = ReadBookmarks()
		self.Refresh()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/searchbookmarks.py")
		except:
			import exception
			exception.Abort("SearchBookmarkWindow.LoadWindow.LoadObject")

		try:
			self.board = self.GetChild("Board")
			self.titleBar = self.GetChild("TitleBar")
		except:
			import exception
			exception.Abort("SearchBookmarkWindow.LoadWindow.BindObject")

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))
		for index in range(offlineshopconst.SEARCH_BOOKMARK_MAX):
			bar = ui.Bar()
			bar.SetParent(self.board)
			bar.SetPosition(10, 31 + index * BOOKMARK_STEP)
			bar.SetSize(210, 20)
			bar.SetColor(ROW_COLORS[index % 2])
			bar.SetOnMouseLeftButtonUpEvent(lambda arg=index: self.Select(arg))
			bar.Show()
			text = ui.TextLine()
			text.SetParent(bar)
			text.SetPosition(5, 3)
			text.Show()
			removeButton = ui.Button()
			removeButton.SetParent(bar)
			removeButton.SetPosition(190, 2)
			removeButton.SetUpVisual("d:/ymir work/ui/public/close_button_01.sub")
			removeButton.SetOverVisual("d:/ymir work/ui/public/close_button_02.sub")
			removeButton.SetDownVisual("d:/ymir work/ui/public/close_button_03.sub")
			removeButton.SetEvent(lambda arg=index: self.Remove(arg))
			removeButton.Show()
			self.lines.append((bar, text, removeButton))

	def Destroy(self):
		WriteBookmarks(self.names)
		self.lines = []
		self.owner = None
		self.ClearDictionary()

	def Open(self):
		self.Show()
		self.SetTop()

	def Close(self):
		self.Hide()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def Refresh(self):
		for (name, (bar, text, removeButton)) in zip(self.names, self.lines):
			text.SetText(name or uiScriptLocale.SEARCH_SHOP_BOOKMARK_EMPTY)

	def GetNames(self):
		return list(self.names)

	def Save(self, name):
		"""Into the first empty line; SEARCH_SHOP_BOOKMARK_FULL when there is none."""
		if name in self.names:
			return True
		for (index, current) in enumerate(self.names):
			if not current:
				self.names[index] = name
				self.Refresh()
				WriteBookmarks(self.names)
				return True
		chat.AppendChat(chat.CHAT_TYPE_INFO, uiScriptLocale.SEARCH_SHOP_BOOKMARK_FULL)
		return False

	def Remove(self, index):
		if 0 <= index < len(self.names):
			self.names[index] = ""
			self.Refresh()
			WriteBookmarks(self.names)

	def Select(self, index):
		if 0 <= index < len(self.names) and self.names[index]:
			self.owner.SetSearchText(self.names[index])
		return True


def ReadBookmarks(file_name=None):
	"""The saved names, SEARCH_BOOKMARK_MAX of them ("" for an empty line). The file is UTF-8
	through io.open: the client's builtins.open (system.py) takes no encoding."""
	import io
	names = []
	try:
		with io.open(file_name or offlineshopconst.BOOKMARK_FILE, "r", encoding="utf-8", errors="replace") as handle:
			names = [line.rstrip("\r\n") for line in handle.readlines()]
	except Exception:
		names = []
	names = [name for name in names if name != uiScriptLocale.SEARCH_SHOP_BOOKMARK_EMPTY]
	names = (names + [""] * offlineshopconst.SEARCH_BOOKMARK_MAX)[:offlineshopconst.SEARCH_BOOKMARK_MAX]
	return names


def WriteBookmarks(names, file_name=None):
	"""True when written, in UTF-8 through io.open (see ReadBookmarks); the folder is made when
	missing. No error leaves it."""
	import io
	import os
	file_name = file_name or offlineshopconst.BOOKMARK_FILE
	try:
		folder = os.path.dirname(file_name)
		if folder and not os.path.isdir(folder):
			os.makedirs(folder)
		with io.open(file_name, "w", encoding="utf-8", newline="\n") as handle:
			for name in names:
				handle.write("%s\n" % name)
	except Exception:
		return False
	return True


class SearchShopWindow(ui.ScriptWindow):

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.isLoaded = False
		self.interface = None
		self.tooltipItem = None
		self.indexBuilt = False
		self.lastSearchTime = -1000.0
		self.lastQuery = None          # ("item", vnum, skill) or ("category", index, sub)
		self.maxPrice = 0
		self.gender = offlineshopconst.GENDER_BOTH
		self.countPerPage = offlineshopconst.SEARCH_PAGE_SIZES[0]
		self.currentPage = 0
		self.pageCount = 0
		self.ascending = True
		self.isLoading = False
		self.category = 0
		self.subCategory = 0
		self.shownRows = []            # the page's rows (search_row dicts)
		self.rowStates = {}            # (owner_pid, slot) -> "pending" | "sold"
		self.rowPool = []
		self.questionDialog = None
		self.popupDialog = None
		self.filterWnd = None
		self.bookmarkWnd = None
		self.suggestionList = None
		self.categoryList = None
		self.scrollWindow = None
		self.premiumText = None
		self.goldText = None
		self.shownCanBuy = None        # the perk and the gold the texts show (set only on a change)
		self.shownGold = None

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		if self.isLoaded:
			return
		self.isLoaded = True
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/searchshop.py")
		except:
			import exception
			exception.Abort("SearchShopWindow.LoadWindow.LoadObject")

		try:
			GetObject = self.GetChild
			self.board = GetObject("Board")
			self.titleBar = GetObject("TitleBar")
			self.inputName = GetObject("InputName")
			self.searchButton = GetObject("SearchButton")
			self.filterButton = GetObject("FilterButton")
			self.saveButton = GetObject("SaveButton")
			self.listButton = GetObject("ListButton")
			self.sortButton = GetObject("SortButton")
			self.goldText = GetObject("GoldAmountText")
			self.premiumText = GetObject("PremiumStatusText")
			self.shownCanBuy = None
			self.shownGold = None
			self.itemBarList = GetObject("ItemBarList")
			self.loadingText = GetObject("LoadingText")
			self.firstButton = GetObject("FirstButton")
			self.prevButton = GetObject("PrevButton")
			self.nextButton = GetObject("NextButton")
			self.lastButton = GetObject("LastButton")
			self.pageButtons = [GetObject("page%d_button" % (i + 1)) for i in range(offlineshopconst.SEARCH_PAGE_BUTTONS)]
			self.sizeButtons = [GetObject("Result%d" % size) for size in offlineshopconst.SEARCH_PAGE_SIZES]
		except:
			import exception
			exception.Abort("SearchShopWindow.LoadWindow.BindObject")

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))
		self.inputName.OnIMEUpdate = ui.__mem_func__(self.__OnNameUpdate)
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
		for (index, button) in enumerate(self.pageButtons):
			button.SetEvent(lambda arg=index: self.SelectPageButton(arg))
		for (index, button) in enumerate(self.sizeButtons):
			button.SetEvent(lambda arg=index: self.SetResultPerPage(arg))

		suggestions = ui.ListBox("TOP_MOST")
		suggestions.SetParent(self)
		suggestions.SetPosition(*SUGGESTION_POSITION)
		suggestions.SetSize(SUGGESTION_WIDTH, SUGGESTION_STEP)
		suggestions.SetTextCenterAlign(False)
		suggestions.SetEvent(ui.__mem_func__(self.__OnSelectSuggestion))
		suggestions.Hide()
		self.suggestionList = suggestions

		categories = ui.ListBox()
		categories.SetParent(self.board)
		categories.SetPosition(*CATEGORY_POSITION)
		categories.SetSize(*CATEGORY_SIZE)
		categories.SetTextCenterAlign(False)
		categories.SetEvent(ui.__mem_func__(self.__OnSelectCategoryEntry))
		categories.Show()
		self.categoryList = categories

		scrollWindow = ui.ScrollWindow(RESULTS_SIZE[0] - 8, RESULTS_SIZE[1] - 8)
		scrollWindow.SetParent(self.board)
		scrollWindow.SetPosition(RESULTS_POSITION[0] + 4, RESULTS_POSITION[1] + 4)
		scrollWindow.SetContentWindow(self.itemBarList)
		scrollWindow.FitWidth(ROW_WIDTH)
		scrollWindow.Show()
		self.scrollWindow = scrollWindow

		self.filterWnd = SearchFilterWindow(self)
		self.filterWnd.Hide()
		self.bookmarkWnd = SearchBookmarkWindow(self)
		self.bookmarkWnd.Hide()

		self.loadingText.Hide()
		self.__FillCategories()
		self.__RefreshPageButtons()

	def BindInterface(self, interface):
		self.interface = interface

	def SetItemToolTip(self, tooltipItem):
		self.tooltipItem = tooltipItem

	SetToolTip = SetItemToolTip

	def Destroy(self):
		self.Close()
		for row in self.rowPool:
			row.Destroy()
		self.rowPool = []
		self.shownRows = []
		if self.filterWnd:
			self.filterWnd.Destroy()
		if self.bookmarkWnd:
			self.bookmarkWnd.Destroy()
		if self.scrollWindow:
			self.scrollWindow.Destroy()
		self.filterWnd = None
		self.bookmarkWnd = None
		self.scrollWindow = None
		self.suggestionList = None
		self.categoryList = None
		self.questionDialog = None
		self.popupDialog = None
		self.tooltipItem = None
		self.interface = None
		self.isLoaded = False
		self.ClearDictionary()

	def Open(self, vnum=0):
		"""Shows the window; with an item's vnum (Ctrl + click), searches that item (OLD :230-246).
		The first open without one browses "All"."""
		self.__LoadWindow()
		self.__BuildIndex()
		self.Show()
		self.SetTop()
		self.RefreshPremium()
		self.RefreshGold()
		if vnum:
			item.SelectItem(vnum)
			self.SetSearchText(item.GetItemName())
			self.Search()
		elif self.lastQuery is None:
			self.SelectCategory(1)
		else:
			self.inputName.SetFocus()

	def Close(self):
		if self.isLoaded:
			self.inputName.KillFocus()
			self.suggestionList.Hide()
			self.filterWnd.Close()
			self.bookmarkWnd.Close()
		self.__CloseQuestion()
		self.HideRowToolTip()
		self.Hide()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def __BuildIndex(self):
		"""The C++ name index, once (OLD built it at import, :53)."""
		if self.indexBuilt:
			return
		import searchShop
		searchShop.BuildIndex(localeInfo.TOOLTIP_SKILLBOOK_NAME, localeInfo.TOOLTIP_SKILL_FORGET_BOOK_NAME)
		self.indexBuilt = True

	## The name field and its suggestions (OLD :258-331)
	def SetSearchText(self, text):
		self.inputName.SetText(text)
		self.inputName.SetEndPosition()
		self.suggestionList.Hide()

	def GetSuggestions(self, query):
		"""The index's names for `query`: from AUTOCOMPLETE_MIN_CHARS characters on, at most
		AUTOCOMPLETE_COUNT."""
		if len(query) < offlineshopconst.AUTOCOMPLETE_MIN_CHARS:
			return []
		import searchShop
		names = []
		for match in searchShop.AutoComplete(query, offlineshopconst.AUTOCOMPLETE_COUNT) or ():
			name = match[0] if isinstance(match, (list, tuple)) else match
			if isinstance(name, str) and name not in names:
				names.append(name)
		return names[:offlineshopconst.AUTOCOMPLETE_COUNT]

	def __OnNameUpdate(self):
		ui.EditLine.OnIMEUpdate(self.inputName)
		names = self.GetSuggestions(self.inputName.GetText())
		self.suggestionList.ClearItem()
		for (index, name) in enumerate(names):
			self.suggestionList.InsertItem(index, name)
		if names:
			self.suggestionList.SetSize(SUGGESTION_WIDTH, SUGGESTION_STEP * len(names))
			self.suggestionList.LocateItem()
			self.suggestionList.Show()
			self.suggestionList.SetTop()
		else:
			self.suggestionList.Hide()

	def __OnSelectSuggestion(self, key, name):
		self.SetSearchText(name)

	## The searches (OLD :333-364, 640-671, 858-883)
	def IsCoolingDown(self):
		"""The client mirrors the server's cooldown (CONFIG search_cooldown_ms, OLD 1 s)."""
		return app.GetTime() < self.lastSearchTime + offlineshopconst.search_cooldown_sec()

	def Search(self):
		"""By the name in the field: it must be an item's (or a book's) name, else
		SEARCH_SHOP_WRONG_NAME."""
		return self.SearchByName(self.inputName.GetText())

	def SearchByName(self, name):
		import searchShop
		name = (name or "").strip()
		found = searchShop.Find(name) if name else None
		if not found:
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.SEARCH_SHOP_WRONG_NAME)
			return False
		(vnum, skillIndex) = offlineshopconst.search_target(found[0])
		if not vnum:
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.SEARCH_SHOP_WRONG_NAME)
			return False
		return self.__SendQuery(("item", vnum, skillIndex))

	def SelectCategory(self, index, sub=0):
		"""A category (1..13) and its subcategory (0: all of it); the costumes open theirs."""
		if not self.__SendQuery(("category", index, sub)):
			return False
		self.category = index
		self.subCategory = sub
		self.__FillCategories()
		return True

	def ApplyFilter(self, maxPrice, male, female):
		"""The filter's price and gender, kept for every later search; the last search runs again."""
		self.maxPrice = max(0, int(maxPrice))
		self.gender = offlineshopconst.gender_filter(male, female)
		if self.lastQuery is not None:
			self.__SendQuery(self.lastQuery)

	def __SendQuery(self, query):
		if self.IsCoolingDown():
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.SEARCH_SHOP_WAIT)
			return False
		import shop
		self.lastSearchTime = app.GetTime()
		self.lastQuery = query
		shop.ClearSearchResults()
		self.rowStates = {}
		self.ascending = True
		if self.isLoaded:
			self.sortButton.SetUp()
			self.suggestionList.Hide()
			self.inputName.KillFocus()
		if query[0] == "item":
			net.SendSearchShopPacket(offlineshopconst.SEARCH_MODE_ITEM, query[1], self.maxPrice, query[2], 0, 0, self.gender)
		else:
			net.SendSearchShopPacket(offlineshopconst.SEARCH_MODE_CATEGORY, 0, self.maxPrice, 0, query[1], query[2], self.gender)
		self.__ShowLoading(True)
		return True

	def GetLastQuery(self):
		return self.lastQuery

	## The categories: a list of names; the costumes' subcategories under their category
	def __FillCategories(self):
		if not self.categoryList:
			return
		self.categoryList.ClearItem()
		selected = -1
		for (position, key) in enumerate(self.GetCategoryKeys()):
			(index, sub) = _split_category_key(key)
			if sub:
				name = "   " + getattr(localeInfo, offlineshopconst.SEARCH_COSTUME_SUBCATEGORIES[sub - 1])
			else:
				name = getattr(localeInfo, offlineshopconst.SEARCH_CATEGORIES[index - 1])
			self.categoryList.InsertItem(key, name)
			if (index, sub) == (self.category, self.subCategory):
				selected = position
		if selected >= 0:
			self.categoryList.selectedLine = selected

	def GetCategoryKeys(self):
		"""The list's entries: every category, and the costumes' subcategories while it is chosen."""
		keys = []
		for index in range(1, len(offlineshopconst.SEARCH_CATEGORIES) + 1):
			keys.append(_category_key(index, 0))
			if index == offlineshopconst.COSTUME_CATEGORY and self.category == index:
				for sub in range(1, len(offlineshopconst.SEARCH_COSTUME_SUBCATEGORIES) + 1):
					keys.append(_category_key(index, sub))
		return keys

	def __OnSelectCategoryEntry(self, key, name):
		(index, sub) = _split_category_key(key)
		if not self.SelectCategory(index, sub):
			self.__FillCategories()

	## The results (OLD :366-429)
	def RefreshItems(self, arg=-1):
		"""RefreshSearchShop (the last RESULTS frame): the rows into the index, sorted by price
		ascending, the first page. Any other `arg` is OLD's paging: 0 first, 1 previous, 2 next,
		3 last, 4 the chosen page."""
		import searchShop
		if arg == -1:
			searchShop.LoadResults()
			searchShop.SortByPrice(1)
			self.ascending = True
			self.currentPage = 0
			if self.isLoaded:
				self.sortButton.SetUp()
		elif arg == 0:
			self.currentPage = 0
		elif arg == 1:
			self.currentPage -= 1
		elif arg == 2:
			self.currentPage += 1
		elif arg == 3:
			self.currentPage = self.pageCount - 1
		self.__ShowPage()

	def GoToPage(self, page):
		self.currentPage = page
		self.__ShowPage()

	def SelectPageButton(self, buttonIndex):
		"""The page buttons show the pages around the current one (OLD showed 1-5)."""
		self.GoToPage(self.__FirstShownPage() + buttonIndex)

	def SetResultPerPage(self, sizeIndex):
		self.countPerPage = offlineshopconst.page_size(sizeIndex)
		self.GoToPage(0)

	def SetSortAscending(self, ascending):
		import searchShop
		self.ascending = bool(ascending)
		searchShop.SortByPrice(1 if self.ascending else 0)
		if self.isLoaded:
			self.sortButton.SetText(uiScriptLocale.SEARCH_SHOP_SORT_DOWN if self.ascending else uiScriptLocale.SEARCH_SHOP_SORT_UP)
		self.GoToPage(0)

	def __ShowPage(self):
		import searchShop
		self.__ShowLoading(False)
		self.currentPage = max(0, self.currentPage)
		answer = searchShop.GetPage(self.currentPage, self.countPerPage)
		(rows, pageCount) = answer if isinstance(answer, (list, tuple)) and len(answer) == 2 else ((), 0)
		self.pageCount = max(0, int(pageCount or 0))
		if self.pageCount and self.currentPage > self.pageCount - 1:
			self.currentPage = self.pageCount - 1
			answer = searchShop.GetPage(self.currentPage, self.countPerPage)
			(rows, _) = answer if isinstance(answer, (list, tuple)) and len(answer) == 2 else ((), 0)
		self.shownRows = [offlineshopconst.search_row(row) for row in (rows or ())]
		if not self.isLoaded:
			return
		for row in self.rowPool:
			row.Hide()
		for (index, row) in enumerate(self.shownRows):
			bar = self.__GetRow(index)
			bar.SetParent(self.itemBarList)
			bar.SetPosition(0, index * ROW_HEIGHT)
			bar.SetRow(row, self.rowStates.get((row["owner_pid"], row["slot"]), ""), self.CanBuy())
		self.itemBarList.SetSize(ROW_WIDTH, max(1, len(self.shownRows) * ROW_HEIGHT))
		self.scrollWindow.OnContentWindowSizeChange()
		self.scrollWindow.ScrollToStart()
		self.__RefreshPageButtons()

	def __GetRow(self, index):
		while index >= len(self.rowPool):
			self.rowPool.append(SearchResultRow(self, len(self.rowPool)))
		return self.rowPool[index]

	def GetShownRows(self):
		return list(self.shownRows)

	def GetRowWidget(self, index):
		return self.rowPool[index] if 0 <= index < len(self.rowPool) else None

	def GetPageCount(self):
		return self.pageCount

	def GetCurrentPage(self):
		return self.currentPage

	def __FirstShownPage(self):
		buttons = offlineshopconst.SEARCH_PAGE_BUTTONS
		first = max(0, self.currentPage - buttons // 2)
		return max(0, min(first, self.pageCount - buttons))

	def __RefreshPageButtons(self):
		if not self.isLoaded:
			return
		shown = self.pageCount > 0
		first = self.__FirstShownPage()
		for (index, button) in enumerate(self.pageButtons):
			page = first + index
			if shown and page < self.pageCount:
				button.SetText(str(page + 1))
				if page == self.currentPage:
					button.Down()
				else:
					button.SetUp()
				button.Show()
			else:
				button.Hide()
		for button in (self.firstButton, self.prevButton, self.nextButton, self.lastButton):
			if shown:
				button.Show()
			else:
				button.Hide()
		for (index, button) in enumerate(self.sizeButtons):
			if offlineshopconst.page_size(index) == self.countPerPage:
				button.Down()
			else:
				button.SetUp()

	def __ShowLoading(self, loading):
		self.isLoading = bool(loading)
		if not self.isLoaded:
			return
		if loading:
			for row in self.rowPool:
				row.Hide()
			self.shownRows = []
			self.pageCount = 0
			self.loadingText.Show()
			self.__RefreshPageButtons()
		else:
			self.loadingText.Hide()

	def IsLoading(self):
		return self.isLoading

	## The tooltip of a row's item
	def ShowRowToolTip(self, row):
		if not self.tooltipItem or not row:
			return
		self.tooltipItem.ClearToolTip()
		self.tooltipItem.AddItemData(row["vnum"], list(row["sockets"]), list(row["attrs"]))
		self.tooltipItem.ShowToolTip()

	def HideRowToolTip(self):
		if self.tooltipItem:
			self.tooltipItem.HideToolTip()

	## The premium status and the gold (OLD :510-534)
	def CanBuy(self):
		"""Buying needs the SEARCH_BUY perk (NOVA-9 Q2 a); the label reads the same perk (PB-C6)."""
		return offlineshopconst.can_search_buy()

	def GetPremiumLabel(self):
		return offlineshopconst.premium_label()

	def RefreshPremium(self):
		"""The label and the rows' buy look, when the perk changed."""
		if not self.premiumText:
			return
		canBuy = self.CanBuy()
		if canBuy == self.shownCanBuy:
			return
		self.shownCanBuy = canBuy
		(text, color) = self.GetPremiumLabel()
		self.premiumText.SetText(text)
		self.premiumText.SetPackedFontColor(color)
		for bar in self.rowPool:
			bar.SetBuyable(canBuy)

	def RefreshGold(self):
		if not self.goldText:
			return
		gold = player.GetElk()
		if gold != self.shownGold:
			self.shownGold = gold
			self.goldText.SetText(localeInfo.NumberToMoneyString(gold))

	def OnUpdate(self):
		"""The gold and the premium label follow their values, set only when one changed (o-cli
		bug 23: no text set every frame)."""
		self.RefreshGold()
		self.RefreshPremium()

	## Buy, go to, whisper (OLD :1182-1240)
	def AskBuy(self, row):
		"""Without the perk: REQUIRED_PREMIUM_USER and nothing sent. Else a question, then BUY
		with the row's owner, slot, item id and price."""
		if not self.CanBuy():
			self.__Popup(localeInfo.REQUIRED_PREMIUM_USER)
			return False
		if self.rowStates.get((row["owner_pid"], row["slot"])):
			return False
		questionDialog = uiCommon.QuestionDialog()
		questionDialog.SetText(uiScriptLocale.SEARCH_SHOP_BUY_CONFIGM)
		questionDialog.SetAcceptEvent(lambda arg=row: self.__AcceptBuy(arg))
		questionDialog.SetCancelEvent(ui.__mem_func__(self.__CloseQuestion))
		questionDialog.Open()
		self.questionDialog = questionDialog
		return True

	def __AcceptBuy(self, row):
		self.__CloseQuestion()
		if not self.CanBuy():
			return
		net.SendSearchShopBuyPacket(row["owner_pid"], row["slot"], row["id"], row["price"])
		self.__SetRowState(row["owner_pid"], row["slot"], "pending")

	def OnBuyResult(self, code, ownerPid, slot):
		"""SHOP_SEARCH BUY_RESULT (Interface.OnSearchShopBuyResult): OK marks the row sold, any
		other code shows its text and frees the row."""
		if offlineshopconst.is_result_ok(code):
			self.__SetRowState(ownerPid, slot, "sold")
			return
		self.__SetRowState(ownerPid, slot, "")
		text = offlineshopconst.result_text(code, 0)
		if text:
			chat.AppendChat(chat.CHAT_TYPE_INFO, text)

	def GetRowState(self, ownerPid, slot):
		return self.rowStates.get((ownerPid, slot), "")

	def __SetRowState(self, ownerPid, slot, state):
		key = (ownerPid, slot)
		if state:
			self.rowStates[key] = state
		else:
			self.rowStates.pop(key, None)
		for (index, row) in enumerate(self.shownRows):
			if (row["owner_pid"], row["slot"]) == key and index < len(self.rowPool):
				self.rowPool[index].SetState(state)

	def AskGoTo(self, row):
		"""The shop's map is the player's: an arrow leads there (GOTO now); another map asks first,
		and GOTO warps (OLD :1230-1240)."""
		if offlineshopconst.is_current_map(row["map"]):
			self.__Popup(localeInfo.SEARCH_SHOP_FOLLOW_SIGNAL)
			net.SendSearchShopGotoPacket(row["owner_pid"])
			return
		questionDialog = uiCommon.QuestionDialog()
		questionDialog.SetText(localeInfo.SEARCH_SHOP_OTHER_MAP)
		questionDialog.SetAcceptEvent(lambda arg=row: self.__AcceptGoTo(arg))
		questionDialog.SetCancelEvent(ui.__mem_func__(self.__CloseQuestion))
		questionDialog.Open()
		self.questionDialog = questionDialog

	def __AcceptGoTo(self, row):
		self.__CloseQuestion()
		net.SendSearchShopGotoPacket(row["owner_pid"])

	def WhisperOwner(self, row):
		if self.interface and row["owner_name"]:
			self.interface.OpenWhisperDialog(row["owner_name"])

	def __Popup(self, text):
		popupDialog = uiCommon.PopupDialog()
		popupDialog.SetText(text)
		popupDialog.Open()
		self.popupDialog = popupDialog

	def __CloseQuestion(self):
		if self.questionDialog:
			self.questionDialog.Close()
		self.questionDialog = None
		return True

	## The filter and the bookmarks
	def OpenFilter(self):
		if self.filterWnd:
			self.filterWnd.Open()

	def OpenBookmarks(self):
		if self.bookmarkWnd:
			self.bookmarkWnd.Open()

	def SaveBookmark(self):
		"""The name in the field, when it is an item's (OLD :373-377)."""
		import searchShop
		name = self.inputName.GetText().strip()
		if not name or not searchShop.Find(name):
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.SEARCH_SHOP_WRONG_NAME)
			return False
		return self.bookmarkWnd.Save(name)

	def OnScrollWheel(self, length):
		if self.scrollWindow:
			return self.scrollWindow.OnRunMouseWheel(length)
		return False
