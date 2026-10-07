"""NovaUI chat log (nui/windows/chat-log/chat-log.rml).

While the "chat-log" window flag is on, Interface.__MakeWindows makes
ChatLogWindow below through nui_windows.make() instead of
uiChat.ChatLogWindow: the facade of the legacy log, with its name,
constructor and methods. CPythonChat keeps chat set 1 (its board state,
filters and end position, which the facade sets with legacy's calls); C++
publishes the lines the log shows (the chat.log.lines feed) and the lines
element reports how many rows its height holds, so no Python runs per
frame.

The filters follow legacy's bit logic exactly (uichat.py:1024-1044): All
enables the six filtered types; the first filter pressed while All is on
disables the six and enables its own; later presses toggle their type. The
types the six never name (command, whisper, big notice) stay shown, as
legacy leaves them. The log's input is nui_chat.ChatInput with the log's
events: Escape closes the log, an empty Enter does nothing, and the field's
user maximum is the log's width // 8, as legacy's (uichat.py:1096)."""

import chat
import net
import uiChat

import nui
import nui_chat
import nui_hud

DOCUMENT = "nui/windows/chat-log/chat-log.rml"


class ChatLogBoard(nui.Window):
	"""The chat log's document and model; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "chatlog"

	def __init__(self, owner):
		self._owner = nui_chat._keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"shown": False, "all": True, "filters": [False] * len(ChatLogWindow.CHAT_MODE_INDEX), "end_pos": 1.0,
		        "chat_mode": chat.CHAT_TYPE_TALKING, "mark": "",
		        "log_width": float(ChatLogWindow.CHAT_LOG_WINDOW_MINIMUM_WIDTH),
		        "log_height": float(ChatLogWindow.CHAT_LOG_WINDOW_MINIMUM_HEIGHT)}

	# Element handlers (element_on), through the board, so the runtime that
	# holds them keeps no facade alive.
	def nui_key(self, event):
		return self._owner.input.on_key(event)

	def nui_field_focus(self, event):
		self._owner.nui_field_focus()

	def nui_field_press(self, event):
		self._owner.nui_field_press(event.get("button", 0))

	@nui.on("filter_all")
	def on_filter_all(self, button):
		if button == 0:
			self._owner.ToggleAllChatMode()

	@nui.on("filter")
	def on_filter(self, index, button):
		if button == 0:
			self._owner.nui_filter(index)

	@nui.on("scroll")
	def on_scroll(self, value):
		self._owner.nui_scroll(value)

	@nui.on("wheel")
	def on_wheel(self, delta):
		self._owner.nui_wheel(delta)

	@nui.on("close")
	def on_close(self, button):
		if button == 0:
			self._owner.Close()

	@nui.on("resized")
	def on_resized(self, width, height):
		self._owner.nui_resized(width, height)

	@nui.on("changed")
	def on_changed(self, value, linebreak):
		self._owner.input.on_changed(value, bool(linebreak))

	@nui.on("mode")
	def on_mode(self, button):
		if button == 0:
			uiChat.RefreshChatMode()

	@nui.on("send")
	def on_send(self, button):
		if button == 0:
			self._owner.input.OnIMEReturn()

	@nui.on("link")
	def on_link(self, link):
		self._owner.input.on_link(link)


class ChatLogWindow(object):
	"""uiChat.ChatLogWindow on NovaUI (Interface.wndChatLog)."""

	NUI_FACADE = True
	KEY = "chat-log"

	BLOCK_WIDTH = uiChat.ChatLogWindow.BLOCK_WIDTH
	CHAT_MODE_NAME = uiChat.ChatLogWindow.CHAT_MODE_NAME
	CHAT_MODE_INDEX = uiChat.ChatLogWindow.CHAT_MODE_INDEX
	CHAT_LOG_WINDOW_MINIMUM_WIDTH = 450
	CHAT_LOG_WINDOW_MINIMUM_HEIGHT = 120

	# The end position snaps to the slider's step (0.01); a change event the
	# model's own write causes comes back within half a step and is not a
	# scroll.
	SCROLL_STEP = 0.01

	def __init__(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self.board = None
		self.focusProxy = None
		self.escapeProxy = None
		self.modeShim = None
		self.attached = False
		self.shown = False
		self.allChatMode = True
		self.filters = [False] * len(self.CHAT_MODE_INDEX)
		self.scrollBarPos = 1.0
		self.input = nui_chat.ChatInput(None, "chat-log-input", self.CHAT_LOG_WINDOW_MINIMUM_WIDTH // 8,
		                                nui_chat.weak_event(self.Close), None)
		# Legacy's state calls (uichat.py:886-889), its input's insult filter
		# (ChatModeButton.__init__), and the scroll event its first SetSize
		# sends (the scroll bar's SetPos, uichat.py:1023, ui.py ScrollBar).
		net.EnableChatInsultFilter(uiChat.ENABLE_INSULT_CHECK)
		self.chatID = chat.CreateChatSet(chat.CHAT_SET_LOG_WINDOW)
		chat.SetBoardState(self.chatID, chat.BOARD_STATE_LOG)
		for mode in self.CHAT_MODE_INDEX:
			chat.EnableChatMode(self.chatID, mode)
		chat.SetEndPos(self.chatID, self.scrollBarPos)
		if not nui_hud.has_engine_2b():
			return
		try:
			self.board = ChatLogBoard(self)
			self.input.board = self.board
			self.board.element_on("chat-log-input", "keydown", self.board.nui_key)
			self.board.element_on("chat-log-input", "focus", self.board.nui_field_focus)
			self.board.element_on("chat-log-input", "mousedown", self.board.nui_field_press)
			self.focusProxy = nui_hud.FocusProxy(self._on_focus_lost, self._on_focus_gained)
			self.escapeProxy = nui_hud.EscapeProxy(self.OnPressEscapeKey)
			self.modeShim = nui_chat.add_mode_shim(self)
			nui_chat.attach_feed()
			self.attached = True
		except Exception:
			self.nui_discard()
			raise

	# --- the make() protocol ------------------------------------------------------

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine_2b()

	def nui_discard(self):
		self._nui_discarded = True
		nui_chat.remove_mode_shim(self.modeShim)
		self.modeShim = None
		if self.attached:
			self.attached = False
			nui_chat.detach_feed()
		for name in ("focusProxy", "escapeProxy"):
			proxy = getattr(self, name)
			setattr(self, name, None)
			if proxy is not None:
				proxy.destroy()
		board, self.board = self.board, None
		self.input.board = None
		if board is not None:
			board.destroy()
		nui_hud.forget(self.KEY, self)

	def Destroy(self):
		self.nui_discard()

	# --- the Interface's calls -------------------------------------------------------

	def BindInterface(self, interface):
		self.input.BindInterface(interface)

	def Show(self):
		"""Shows the log without focusing its field, as ui.Window.Show."""
		self.shown = True
		if self.board is not None:
			self.board.show()
		self.input.ShowText()
		if self.escapeProxy is not None:
			self.escapeProxy.show()
		self._set(shown=True)

	def Hide(self):
		self.shown = False
		if self.focusProxy is not None:
			self.focusProxy.release()
		if self.escapeProxy is not None:
			self.escapeProxy.hide()
		if self.board is not None:
			self.board.hide()
		self._set(shown=False)

	def IsShow(self):
		return self.shown and self.board is not None and self.board.is_visible()

	def Open(self):
		"""Shows the log and focuses its field (uichat.py:1063-1066)."""
		self.Show()
		if self.board is not None:
			self.board.focus("chat-log-input")

	def Close(self):
		"""The field gives up the focus, then the log hides (uichat.py:1068-1071)."""
		if self.focusProxy is not None:
			self.focusProxy.release()
		if self.board is not None:
			self.board.focus("chat-log-mode")
		self.Hide()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	# --- the filters (uichat.py:1024-1044) --------------------------------------------

	def ToggleAllChatMode(self):
		if self.allChatMode:
			return
		self.allChatMode = True
		for mode in self.CHAT_MODE_INDEX:
			chat.EnableChatMode(self.chatID, mode)
		self.filters = [False] * len(self.CHAT_MODE_INDEX)
		self._set(all=True, filters=list(self.filters))

	def ToggleChatMode(self, mode):
		if self.allChatMode:
			self.allChatMode = False
			for each in self.CHAT_MODE_INDEX:
				chat.DisableChatMode(self.chatID, each)
			chat.EnableChatMode(self.chatID, mode)
			self._set(all=False)
		else:
			chat.ToggleChatMode(self.chatID, mode)

	def nui_filter(self, index):
		"""A filter toggle pressed: its own state flips, as a legacy toggle
		button's does, and both of its events call ToggleChatMode."""
		if not 0 <= index < len(self.CHAT_MODE_INDEX):
			return
		self.filters[index] = not self.filters[index]
		self._set(filters=list(self.filters))
		self.ToggleChatMode(self.CHAT_MODE_INDEX[index])

	# --- scroll and size -----------------------------------------------------------------

	def OnScroll(self):
		chat.SetEndPos(self.chatID, self.scrollBarPos)

	def nui_scroll(self, value):
		try:
			value = min(max(float(value), 0.0), 1.0)
		except (TypeError, ValueError):
			return
		if abs(value - self.scrollBarPos) < self.SCROLL_STEP / 2.0:
			return
		self.scrollBarPos = value
		self.OnScroll()

	def nui_wheel(self, delta):
		end = nui_chat.wheel_end_pos("log", delta)
		if end is None:
			return
		self.scrollBarPos = end
		self._set(end_pos=end)
		self.OnScroll()

	def nui_resized(self, width, height):
		self._set(log_width=float(width), log_height=float(height))
		self.input.SetUserMax(int(width) // 8)

	# --- the field's focus -----------------------------------------------------------------

	def nui_field_focus(self):
		if self.focusProxy is not None:
			self.focusProxy.take()

	def nui_field_press(self, button):
		"""The document takes no focus from a press (body focus: none), so a
		press on the field focuses it, as a press on a legacy edit line does."""
		if button == 0 and self.IsShow():
			self.board.focus("chat-log-input")

	def _on_focus_lost(self):
		if self.board is not None:
			self.board.focus("chat-log-mode")

	def _on_focus_gained(self):
		if self.IsShow():
			self.board.focus("chat-log-input")

	def nui_refresh_chat_mode(self):
		"""ChatInputSet.OnRefreshChatMode, through uiChat.RefreshChatMode."""
		self.input.ChangeChatMode()

	def _set(self, **values):
		if self.board is not None:
			self.board.set(**values)
