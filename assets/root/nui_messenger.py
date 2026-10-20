"""NovaUI messenger, the friend list (nui/windows/messenger/messenger.rml;
P16 spec 5.7).

While the messenger flag is on, Interface.__MakeWindows makes
MessengerWindow below through nui_windows.make() instead of
uiMessenger.MessengerWindow: a subclass of the legacy class
(nui_facade.Facade) whose uiscript loader puts proxies where the widgets
were (the board, the scroll bar, the four buttons, the resize button). The
legacy group and member items (MessengerFriendGroup, MessengerGuildItem and
the others) stay the window's data, as legacy makes them, but never show:
the board shows what they hold, in legacy's order (showingItemList). So the
C++ handler's calls (OnLogin, OnLogout, OnRemoveList, OnRemoveAllList,
RefreshGuildMember), the lover's calls, the selection and its rules for the
whisper and remove buttons, add friend (the dialog kit's input dialog),
remove (its question: messenger.RemoveFriend and the remove packet, or a
guild member's kick), whisper (Interface.OpenWhisperDialog) and the guild
button are legacy's code.

What NovaUI changes: the list shows every row and scrolls by pixel (D18;
legacy's 20 px line window drives no flow); the selection bar is a class
and the lover's love points a hint on hover, so nothing runs per frame
(legacy's items draw their selection in OnRender); the height is the
document's resize edge, which reaches legacy's OnResizeDialog through the
resize button's proxy. The board exists only while the window shows and
draws below the legacy UI layer, as legacy's window lived in it."""

import localeInfo
import ui
import uiMessenger
import wndMgr

import nui
import nui_facade
import nui_form_proxies
import nui_hud
import nui_proxies

DOCUMENT = "nui/windows/messenger/messenger.rml"
KEY = "messenger"
# The uiscript's place (messengerwindow.py: W - 200, H - 450) and size.
PLACE_RIGHT, PLACE_BOTTOM = 200, 450
WIDTH, HEIGHT = 170, 300
# The resize button's height (uimessenger.py:395): the window is the
# button's place plus it.
RESIZE_HEIGHT = 10


class _MessengerBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The messenger's document; its events go to its window. A press on it
	raises the window, as legacy's window manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "messenger"

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

	@nui.on("row_dblclick")
	def on_row_dblclick(self, index):
		self._owner._double_click_row(int(index))

	@nui.on("add_press")
	def on_add_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.addFriendButton.click()

	@nui.on("whisper_press")
	def on_whisper_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.whisperButton.click()

	@nui.on("remove_press")
	def on_remove_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.removeButton.click()

	@nui.on("guild_press")
	def on_guild_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.guildButton.click()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.board.close()

	@nui.on("resized")
	def on_resized(self, height):
		self._owner._resized(height)


def row_of(item):
	"""A row of the board from one of legacy's items (spec 5.7.2): its kind
	("group", "member" or "empty", legacy's MESSENGER_EMPTY_LIST line), its
	name, its states, the member step and the lover's love points (-1 for
	none) with their hint."""
	if isinstance(item, uiMessenger.MessengerGroupItem):
		kind = "group"
	elif isinstance(item, uiMessenger.MessengerMemberItem):
		kind = "member"
	else:
		kind = "empty"
	love = int(getattr(item, "lovePoint", -1))
	hint = ""
	if love >= 0:
		try:
			hint = nui.plain_text(localeInfo.AFF_LOVE_POINT % love)
		except (TypeError, ValueError):
			hint = ""
	return {
		"kind": kind,
		"name": item.GetName() or "",
		"online": bool(item.IsOnline()),
		"open": kind == "group" and bool(item.IsOpen()),
		"selected": bool(getattr(item, "isSelected", False)),
		"member": item.GetStepWidth() > 0,
		"love": love,
		"hint": hint,
	}


class MessengerWindow(nui_facade.Facade, uiMessenger.MessengerWindow):
	"""uiMessenger.MessengerWindow on NovaUI (Interface.wndMessenger)."""

	KEY = KEY
	BOARD = _MessengerBoard

	def __init__(self):
		self._nui_destroyed = False
		self.nui_begin()
		try:
			uiMessenger.MessengerWindow.__init__(self)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def __del__(self):
		"""Legacy's handler reset, but not for an instance make() discarded
		before use: the legacy window made in its place has set itself as
		the C++ handler since, and this instance's late collection must not
		clear it (the phase windows' rule, AUTHORING "Window flags")."""
		if getattr(self, "_nui_discarded", False) and not getattr(self, "_nui_destroyed", False):
			ui.ScriptWindow.__del__(self)
			return
		uiMessenger.MessengerWindow.__del__(self)

	def PLACE(self):
		"""Legacy's place, (W - 200, H - 450) in dp."""
		scale = nui.get_scale() or 1.0
		return (wndMgr.GetScreenWidth() / scale - PLACE_RIGHT, wndMgr.GetScreenHeight() / scale - PLACE_BOTTOM)

	def nui_model(self):
		return {
			"rows": [],
			"whisper_enabled": False,
			"remove_enabled": False,
			"height": float(HEIGHT),
		}

	def Destroy(self):
		self._nui_destroyed = True
		nui_facade.Facade.Destroy(self)

	# --- the proxies' callbacks ---------------------------------------------------------

	def _on_buttons(self, button=None):
		self.nui_set(whisper_enabled=bool(self.whisperButton.enabled), remove_enabled=bool(self.removeButton.enabled))

	def _rows(self):
		return [row_of(item) for item in self.showingItemList]

	def _press_row(self, index):
		"""A left press on a row: the item's own press (MessengerItem's
		OnMouseLeftButtonDown), then the rows as the selection left them."""
		if 0 <= index < len(self.showingItemList):
			self.OnSelectItem(self.showingItemList[index])
			self.nui_set(rows=self._rows())

	def _double_click_row(self, index):
		if 0 <= index < len(self.showingItemList):
			self.OnDoubleClickItem(self.showingItemList[index])

	def _resized(self, height):
		"""The resize edge's drag: legacy's resize button at the new bottom,
		its move event (OnResizeDialog) sizes the window."""
		try:
			height = int(round(float(height)))
		except (TypeError, ValueError):
			return
		self.resizeButton.dragged(0, height - self.resizeButton.GetHeight())

	# --- the loader (uimessenger.py:366-404, on proxies) -----------------------------------

	def _MessengerWindow__LoadWindow(self):
		# The uiscript's style (messengerwindow.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")

		self.board = nui_proxies.BoardProxy(WIDTH, HEIGHT)
		self.scrollBar = nui_form_proxies.ScrollProxy()
		self.whisperButton = nui_proxies.ButtonProxy(self._on_buttons)
		self.removeButton = nui_proxies.ButtonProxy(self._on_buttons)
		self.addFriendButton = nui_proxies.ButtonProxy()
		self.guildButton = nui_proxies.ButtonProxy()

		self.board.SetCloseEvent(ui.__mem_func__(self.Close))
		self.scrollBar.SetScrollEvent(ui.__mem_func__(self.OnScroll))
		self.whisperButton.SetEvent(ui.__mem_func__(self.OnPressWhisperButton))
		self.removeButton.SetEvent(ui.__mem_func__(self.OnPressRemoveButton))
		self.addFriendButton.SetEvent(ui.__mem_func__(self.OnPressAddFriendButton))
		self.guildButton.SetEvent(ui.__mem_func__(self.OnPressGuildButton))

		self.whisperButton.Disable()
		self.removeButton.Disable()

		resizeButton = nui_form_proxies.ResizeProxy(0, 0, RESIZE_HEIGHT)
		resizeButton.AddFlag("restrict_x")
		resizeButton.SetParent(self)
		resizeButton.SetSize(WIDTH, RESIZE_HEIGHT)
		resizeButton.SetWindowVerticalAlignBottom()
		resizeButton.SetPosition(0, 0)
		resizeButton.Show()
		self.resizeButton = resizeButton
		self.resizeButton.SetMoveEvent(ui.__mem_func__(self.OnResizeDialog))
		self.resizeButton.SetPosition(0, HEIGHT)

	# --- the groups: legacy's, never shown (uimessenger.py:483-499) ------------------------

	def _MessengerWindow__AddGroup(self):
		member = uiMessenger.MessengerFriendGroup(ui.__mem_func__(self.GetSelf))
		member.Open()
		self.groupList.append(member)

		member = uiMessenger.MessengerGuildGroup(ui.__mem_func__(self.GetSelf))
		member.Open()
		self.groupList.append(member)

	def _MessengerWindow__AddFamilyGroup(self):
		member = uiMessenger.MessengerFamilyGroup(ui.__mem_func__(self.GetSelf))
		member.Open()

		self.familyGroup = member

	# --- what NovaUI changes (P16 spec 5.7.3) -----------------------------------------

	def _MessengerWindow__LocateMember(self):
		"""Legacy's scroll bar rule on the proxy (its shown state and middle
		bar), then every row into the model: the document lays them out and
		scrolls them; no legacy item shows."""
		if self.isLoaded == 0:
			return

		if self.showingPageSize / 20 >= len(self.showingItemList):
			self.scrollBar.Hide()
			self.startLine = 0
		else:
			if self.showingItemList:
				self.scrollBar.SetMiddleBarSize(float(self.showingPageSize / 20) / float(len(self.showingItemList)))
			self.scrollBar.Show()

		self.nui_set(rows=self._rows())

	def OnSelectItem(self, item):
		"""Legacy's, then the rows (a group's open state and the selection)."""
		uiMessenger.MessengerWindow.OnSelectItem(self, item)
		self.nui_set(rows=self._rows())

	def OnUpdateLovePoint(self, lovePoint):
		uiMessenger.MessengerWindow.OnUpdateLovePoint(self, lovePoint)
		self.nui_set(rows=self._rows())

	def OnLoginLover(self):
		uiMessenger.MessengerWindow.OnLoginLover(self)
		self.nui_set(rows=self._rows())

	def OnLogoutLover(self):
		uiMessenger.MessengerWindow.OnLogoutLover(self)
		self.nui_set(rows=self._rows())

	def SetSize(self, width, height):
		"""The board's height; the legacy window stays 0 x 0."""
		self.nui_set(height=float(height))
