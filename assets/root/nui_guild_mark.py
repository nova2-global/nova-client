"""NovaUI guild mark and symbol lists (nui/windows/guild-mark/guild-mark.rml;
P16 spec 5.11).

While the guild-mark flag is on, the guild window's info page makes
MarkSelectDialog and SymbolSelectDialog below through nui_windows.make()
(uiguild.py's two changed lines) instead of uiUploadMark's: subclasses of
the legacy classes whose loader (__Load) puts proxies where the uiscript's
widgets and legacy's list box were. So Open (an empty folder pops legacy's
message), the files of upload/ (__RefreshFileList, legacy's extensions,
sorted), Refresh, OK's checks (a file chosen, one the client reads, 16 x 12
for a mark, 64 x 128 for a symbol, each failure the dialog kit's message,
D13), the select event (the guild window's net.UploadMark or UploadSymbol),
Cancel, the close button and Escape are legacy's code.

A file is a data entry (UploadEntry: legacy's MarkItem and SymbolItem
without their widgets); its image's size is read with legacy's
app.GetImageInfo only for the rows the list shows (the window of ten, as
legacy's ListBoxEx shows them, moved by the scroll range and the wheel), as
legacy's lazy load intended (its OnRender read it per shown row), so a
large folder costs what is shown and nothing runs per frame. A mark file of
16 x 12 shows its preview (the file itself, /upload/<name>), but for a
.jpeg, which the client's image loaders do not read.

Each list's board is instanced (guild_mark_<n>): the mark and the symbol
list can show together. It exists only while its list shows, a plain
window above the legacy UI layer, centered at each open."""

import app
import localeInfo
import ui
import uiScriptLocale
import uiUploadMark

import nui
import nui_facade
import nui_form_proxies
import nui_hud
import nui_proxies

DOCUMENT = "nui/windows/guild-mark/guild-mark.rml"
# Legacy's ListBoxEx shows ten rows (ui.py ListBoxEx.viewItemCount).
VIEW_ROWS = 10
# The mark list's preview size (uiuploadmark.py MarkItem.LoadImageInfo).
MARK_WIDTH, MARK_HEIGHT = 16, 12
# The files the client's image loaders draw among the mark list's (the
# Direct3D 9 renderer's paths::IsClientImagePath): a .jpeg mark lists
# without a preview, where legacy's image box drew it (spec 14).
PREVIEW_EXTENSIONS = (".bmp", ".tga", ".jpg", ".png")
SCROLL_STEP = 0.01


class UploadEntry(object):
	"""A file of the list: legacy's MarkItem or SymbolItem data (the file's
	name, its path, whether the client reads it and its size, read once by
	LoadImageInfo with legacy's app.GetImageInfo), without the widget."""

	def __init__(self, fileName, kind):
		self.fileName = fileName
		self.fullPath = "upload/" + fileName
		self.kind = kind
		self.imgWidth = 0
		self.imgHeight = 0
		self.canLoad = 0
		self.imageLoaded = False

	def GetText(self):
		return self.fileName

	def LoadImageInfo(self):
		if self.imageLoaded:
			return
		self.imageLoaded = True
		(self.canLoad, self.imgWidth, self.imgHeight) = app.GetImageInfo(self.fullPath)

	def preview(self):
		"""The mark file's preview source: only a readable 16 x 12 file
		(legacy's MarkItem shows no other) of a type the client draws. Its
		size is read either way, as legacy reads it for a shown row."""
		if self.kind != "mark":
			return ""
		self.LoadImageInfo()
		if not self.fileName.lower().endswith(PREVIEW_EXTENSIONS):
			return ""
		if self.canLoad == 1 and self.imgWidth == MARK_WIDTH and self.imgHeight == MARK_HEIGHT:
			return "/" + self.fullPath
		return ""


class ListProxy(nui_form_proxies.ListBoxExProxy):
	"""Legacy's ListBoxEx of the lists: its entries, the selection and the
	window of VIEW_ROWS rows from `base`, which its scroll bar moves
	(ListBoxEx.__OnScroll: int(pos x (n - VIEW_ROWS))); RemoveAllItems puts
	the scroll bar back at the top, as legacy's."""

	def __init__(self, on_change=None):
		nui_form_proxies.ListBoxExProxy.__init__(self, on_change)
		self.base = 0

	def SetScrollBar(self, scrollBar):
		scrollBar.SetScrollEvent(self._on_scroll)
		self.scroll_bar = scrollBar

	def _on_scroll(self):
		self.base = int(self.scroll_bar.GetPos() * self.scroll_length())
		self._changed()

	def scroll_length(self):
		return max(0, len(self.entries) - VIEW_ROWS)

	def RemoveAllItems(self):
		nui_form_proxies.ListBoxExProxy.RemoveAllItems(self)
		if self.scroll_bar is not None:
			self.scroll_bar.SetPos(0)

	def rows(self):
		"""(index, entry) of the rows the list shows."""
		return list(enumerate(self.entries))[self.base:self.base + VIEW_ROWS]


class _MarkListBoard(nui_hud.RaisesOnPress, nui.Window):
	"""A mark or symbol list's document; its events go to its dialog."""

	DOCUMENT = DOCUMENT
	MODEL = "guild_mark"
	INSTANCED = True

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("row_press")
	def on_row_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_row(int(index))

	@nui.on("ok_press")
	def on_ok_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.okButton.click()

	@nui.on("cancel_press")
	def on_cancel_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.cancelButton.click()

	@nui.on("refresh_press")
	def on_refresh_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.refreshButton.click()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.board.close()

	@nui.on("scroll")
	def on_scroll(self, value):
		self._owner._scroll(value)

	@nui.on("wheel")
	def on_wheel(self, delta):
		self._owner._wheel(delta)


class _TitleBoardProxy(nui_proxies.BoardProxy):
	"""ui.BoardWithTitleBar: SetTitleName hands the title to the window."""

	def __init__(self, width, height, on_title):
		nui_proxies.BoardProxy.__init__(self, width, height)
		self._on_title = on_title

	def SetTitleName(self, name):
		nui_proxies.BoardProxy.SetTitleName(self, name)
		self._on_title(self.title)


class _ListFacade(nui_facade.Facade):
	"""What the mark and symbol lists share (the module docstring)."""

	# None: the guild window keeps a mark and a symbol list at once.
	KEY = None
	BOARD = _MarkListBoard
	PLACE = "center"
	KIND = "mark"

	def _list(self):
		return None

	def nui_model(self):
		return {"kind": self.KIND, "title": nui.plain_text(uiScriptLocale.MARKLIST_TITLE), "files": [], "selected": -1,
		        "selected_row": -1, "scroll": 0.0}

	def _on_title(self, title):
		self.nui_set(title=nui.plain_text(title))

	def _on_list(self, listbox=None):
		listbox = self._list()
		if listbox is None:
			return
		files = [{"index": index, "name": nui.plain_text(entry.GetText()), "preview": entry.preview()}
		         for index, entry in listbox.rows()]
		scroll = listbox.scroll_bar.GetPos() if listbox.scroll_bar is not None else 0.0
		selected = int(listbox.selected)
		row = selected - listbox.base if 0 <= selected - listbox.base < len(files) else -1
		self.nui_set(files=files, selected=selected, selected_row=row, scroll=float(scroll))

	def _press_row(self, index):
		"""A press on a shown row: legacy's item press (ListBoxEx.SelectItem)."""
		listbox = self._list()
		if listbox is not None:
			listbox.SelectIndex(listbox.base + index)

	def _scroll(self, value):
		try:
			value = min(max(float(value), 0.0), 1.0)
		except (TypeError, ValueError):
			return
		scroll = self.scrollBar
		if abs(value - scroll.GetPos()) < SCROLL_STEP / 2.0:
			return
		scroll.moved(value)

	def _wheel(self, delta):
		"""A wheel notch: one row (RmlUi's sign: positive is down)."""
		listbox = self._list()
		if listbox is None or not delta or listbox.scroll_length() <= 0:
			return
		position = self.scrollBar.GetPos() + float(delta) / float(listbox.scroll_length())
		self.scrollBar.moved(min(max(position, 0.0), 1.0))

	def _load_common(self):
		"""The parts both legacy loaders make the same way (uiuploadmark.py
		:188-220 and :317-350): the popup as the dialog kit's message (D13),
		the uiscript's board, scroll bar and buttons."""
		# The uiscript's style (marklistwindow.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		self.popupDialog = nui_form_proxies.MessageWindowProxy()
		self.scrollBar = nui_form_proxies.ScrollProxy(lambda scroll: self._on_list())
		self.scrollBar.SetScrollBarSize(220)
		self.board = _TitleBoardProxy(170, 300, self._on_title)
		self.okButton = nui_proxies.ButtonProxy()
		self.cancelButton = nui_proxies.ButtonProxy()
		self.refreshButton = nui_proxies.ButtonProxy()


class MarkSelectDialog(_ListFacade, uiUploadMark.MarkSelectDialog):
	"""uiUploadMark.MarkSelectDialog on NovaUI (GuildWindow.markSelectDialog)."""

	KIND = "mark"

	def __init__(self):
		self.nui_begin()
		try:
			uiUploadMark.MarkSelectDialog.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def _list(self):
		return getattr(self, "markListBox", None)

	def _MarkSelectDialog__CreateMarkListBox(self):
		markListBox = ListProxy(self._on_list)
		markListBox.SetParent(self)
		markListBox.SetPosition(15, 50)
		markListBox.Show()
		return markListBox

	def _MarkSelectDialog__AppendFile(self, fileName):
		self.markListBox.AppendItem(UploadEntry(fileName, "mark"))

	def _MarkSelectDialog__Load(self):
		self._load_common()

		self.markListBox = self._MarkSelectDialog__CreateMarkListBox()
		self.markListBox.SetScrollBar(self.scrollBar)

		self.popupText = self.popupDialog.GetChild("message")
		self.popupDialog.GetChild("accept").SetEvent(ui.__mem_func__(self.popupDialog.Hide))

		self.refreshButton.SetEvent(ui.__mem_func__(self._MarkSelectDialog__OnRefresh))
		self.cancelButton.SetEvent(ui.__mem_func__(self._MarkSelectDialog__OnCancel))
		self.okButton.SetEvent(ui.__mem_func__(self._MarkSelectDialog__OnOK))
		self.board.SetCloseEvent(ui.__mem_func__(self._MarkSelectDialog__OnCancel))
		self.UpdateRect()

		self._MarkSelectDialog__RefreshFileList()


class SymbolSelectDialog(_ListFacade, uiUploadMark.SymbolSelectDialog):
	"""uiUploadMark.SymbolSelectDialog on NovaUI (GuildWindow.symbolSelectDialog)."""

	KIND = "symbol"

	def __init__(self):
		self.nui_begin()
		try:
			uiUploadMark.SymbolSelectDialog.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def _list(self):
		return getattr(self, "symbolListBox", None)

	def _SymbolSelectDialog__CreateSymbolListBox(self):
		symbolListBox = ListProxy(self._on_list)
		symbolListBox.SetParent(self)
		symbolListBox.SetPosition(15, 50)
		symbolListBox.Show()
		return symbolListBox

	def _SymbolSelectDialog__AppendFile(self, fileName):
		self.symbolListBox.AppendItem(UploadEntry(fileName, "symbol"))

	def _SymbolSelectDialog__Load(self):
		self._load_common()

		self.symbolListBox = self._SymbolSelectDialog__CreateSymbolListBox()
		self.symbolListBox.SetScrollBar(self.scrollBar)

		self.popupText = self.popupDialog.GetChild("message")
		self.popupDialog.GetChild("accept").SetEvent(ui.__mem_func__(self.popupDialog.Hide))

		self.refreshButton.SetEvent(ui.__mem_func__(self._SymbolSelectDialog__OnRefresh))
		self.cancelButton.SetEvent(ui.__mem_func__(self._SymbolSelectDialog__OnCancel))
		self.okButton.SetEvent(ui.__mem_func__(self._SymbolSelectDialog__OnOK))
		self.board.SetCloseEvent(ui.__mem_func__(self._SymbolSelectDialog__OnCancel))
		self.board.SetTitleName(localeInfo.SYMBOLLIST_TITLE)
		self.UpdateRect()

		self._SymbolSelectDialog__RefreshFileList()
