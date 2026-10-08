"""NovaUI chat window and its input (nui/windows/chat/chat.rml).

While the "chat" window flag is on, Interface.__MakeChatWindow makes
ChatWindow below through nui_windows.make() instead of uiChat.ChatWindow:
the facade of the legacy window, with its name, constructor and the methods
the Interface, game.py and the console call. CPythonChat keeps the lines, as
for legacy; C++ publishes the lines this view shows (the chat.window.lines
feed, from nuigame.ChatAttach() to ChatDetach()), so no Python runs per
frame. The facade makes the legacy state calls on chat set 0 (board state,
end position, colors) and none of the per-frame or layout ones.

ChatInput is legacy's ChatLine (uichat.py:103-369) on a NovaUI text field,
shared with the chat log (nui_chat_log.py): the modes and their prefixes,
the mark, the 33-line history on Up and Down, Enter (send and stay open; an
empty Enter runs the return event), Escape (clear and run the escape
event), Tab (nothing), the shout limit, the insult check, the visible
length limit that leaves link metadata out (nui_text.visible_length), and a
press on a link: the legacy item tooltip, or with left Alt a paste of the
link into the focused field (ime.PasteString reaches a NovaUI field).

The field keeps wndMgr's focus away from the game window while it has
NovaUI's, through a nui_hud.FocusProxy, as a focused legacy edit line
would: a press on the world then closes the chat through game.py's
CheckFocus, and a legacy edit line that takes wndMgr's focus (a whisper
dialog) takes the keys from the field while the chat stays open.

With an exe that has the Wave 3a engine (nui_hud.has_engine_3a), the closed
chat's lines show in a document of their own (nui_chat_view.ChatViewBoard,
P11 spec D4), shown while the chat is closed and shown; the chat's own lines
element is then off while it is closed (lines_mode). With an older exe the
chat keeps one document, its lines in view mode while closed, as before."""

import weakref

import app
import chat
import colorInfo
import ime
import localeInfo
import net
import uiChat
import wndMgr

try:
	import nuigame
except ImportError:  # an exe without the Wave 2b engine: nui_ready() is False
	nuigame = None

import nui
import nui_chat_view
import nui_hud
import nui_text

DOCUMENT = "nui/windows/chat/chat.rml"

# RmlUi's key identifiers for the arrow keys (Include/RmlUi/Core/Input.h,
# KI_UP = 91, KI_DOWN = 93); nui.py names Escape, Return, Tab and Space only.
KEY_UP = 91
KEY_DOWN = 93

# The four modes the mode button cycles, with the prefix each puts in the
# field and the mark it shows (ChatLine.ChangeChatMode, __CheckChatMark).
_PREFIX = {chat.CHAT_TYPE_PARTY: "#", chat.CHAT_TYPE_GUILD: "%", chat.CHAT_TYPE_SHOUT: "!"}
_NEXT_MODE = {
	chat.CHAT_TYPE_TALKING: chat.CHAT_TYPE_PARTY,
	chat.CHAT_TYPE_PARTY: chat.CHAT_TYPE_GUILD,
	chat.CHAT_TYPE_GUILD: chat.CHAT_TYPE_SHOUT,
	chat.CHAT_TYPE_SHOUT: chat.CHAT_TYPE_TALKING,
}
_MARKS = ("#", "%", "!")


_attached = [0]  # facades that hold the chat feed (the chat window, the log)


def attach_feed():
	"""nuigame.ChatAttach() for the first facade that needs the chat feed;
	the window and the log can each be on alone, and C++ keeps one switch."""
	_attached[0] += 1
	if _attached[0] == 1:
		nuigame.ChatAttach()


def detach_feed():
	"""nuigame.ChatDetach() when the last facade that held the feed goes."""
	if _attached[0] <= 0:
		return
	_attached[0] -= 1
	if _attached[0] == 0:
		nuigame.ChatDetach()


def _keep(owner):
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


def weak_event(method):
	"""A bound method held weakly: calling it after its object went does
	nothing."""
	ref = weakref.WeakMethod(method)

	def call(*args):
		target = ref()
		if target is not None:
			return target(*args)
		return None
	return call


def _call(event, *args):
	"""A stored event: a function, a ui.__mem_func__, or 0/None for none."""
	if not event:
		return
	try:
		event(*args)
	except ReferenceError:
		pass


def mark_of(text):
	"""The prefix mark legacy shows over the field's first character."""
	return text[0] if text and text[0] in _MARKS else ""


class ChatInput(object):
	"""uichat.ChatLine on the NovaUI field `field_id` of `board`: the same
	modes, history, sending and limits. `on_escape` and `on_return` are the
	escape and return events (ChatLine.eventEscape, eventReturn); `mark`
	(the model key of the prefix mark) and `chat_mode` follow the field."""

	LAST_SENTENCE_STACK_SIZE = 32
	SHOUT_INTERVAL = 15

	def __init__(self, board, field_id, user_max, on_escape=None, on_return=None):
		self.board = board
		self.field = field_id
		self.userMax = user_max
		self.eventEscape = on_escape
		self.eventReturn = on_return
		self.interface = None
		self.pending = None      # text set while the document was hidden
		self.chatMode = chat.CHAT_TYPE_TALKING
		self.lastShoutTime = 0
		self.lastSentenceStack = []
		self.lastSentencePos = 0
		self.lastValue = ""

	# --- the field --------------------------------------------------------------

	def GetText(self):
		if self.pending is not None:
			return self.pending
		if self.board is None:
			return ""
		text = self.board.get_value(self.field)
		return text if text is not None else ""

	def SetText(self, text):
		"""ChatLine.SetText with SetEndPosition: the caret at the end. A
		hidden document's field, or a board not made yet (the chat log's
		exists only while it shows), takes no text (the mode buttons cycle
		every chat input, the hidden log's too, as legacy's), so it waits for
		ShowText()."""
		self.lastValue = text
		self.pending = None
		if self.board is None or not self.board.set_value(self.field, text, caret="end"):
			self.pending = text
		self.CheckChatMark()

	def ShowText(self):
		"""After the document shows: the text set while it was hidden."""
		pending, self.pending = self.pending, None
		if pending is not None and self.board is not None:
			self.board.set_value(self.field, pending, caret="end")
			self.board.set(mark=mark_of(pending))

	def CheckChatMark(self):
		if self.board is not None:
			self.board.set(mark=mark_of(self.GetText() if self.pending is None else self.pending))

	def SetUserMax(self, user_max):
		self.userMax = user_max

	# --- modes ------------------------------------------------------------------

	def SetChatMode(self, mode):
		self.chatMode = mode
		if self.board is not None:
			self.board.set(chat_mode=mode)

	def GetChatMode(self):
		return self.chatMode

	def ChangeChatMode(self):
		mode = _NEXT_MODE.get(self.chatMode, chat.CHAT_TYPE_TALKING)
		self.SetChatMode(mode)
		self.SetText(_PREFIX.get(mode, ""))

	def GetCurrentChatModeName(self):
		names = {chat.CHAT_TYPE_TALKING: localeInfo.CHAT_NORMAL, chat.CHAT_TYPE_PARTY: localeInfo.CHAT_PARTY,
		         chat.CHAT_TYPE_GUILD: localeInfo.CHAT_GUILD, chat.CHAT_TYPE_SHOUT: localeInfo.CHAT_SHOUT}
		return names[self.chatMode]

	def ClearChat(self):
		"""ChatLine.__ClearChat."""
		self.SetText("")
		self.lastSentencePos = 0

	def ResetChat(self):
		"""ChatLine.__ResetChat: the mode's prefix, or an empty field."""
		prefix = _PREFIX.get(self.chatMode)
		if prefix:
			self.SetText(prefix)
		else:
			self.ClearChat()
		self.CheckChatMark()

	# --- sending -----------------------------------------------------------------

	def _send(self, text, chat_type):
		if net.IsChatInsultIn(text):
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.CHAT_INSULT_STRING)
		else:
			net.SendChatPacket(text, chat_type)

	def _send_prefixed(self, text, chat_type):
		if 1 == len(text):
			self.RunCloseEvent()
			return
		self._send(text[1:], chat_type)
		self.ResetChat()

	def _send_shout(self, text):
		if 1 == len(text):
			self.RunCloseEvent()
			return
		if app.GetTime() < self.lastShoutTime + self.SHOUT_INTERVAL:
			chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.CHAT_SHOUT_LIMIT)
			self.ResetChat()
			return
		self._send(text[1:], chat.CHAT_TYPE_SHOUT)
		self.ResetChat()
		self.lastShoutTime = app.GetTime()

	def OnIMEReturn(self):
		"""Enter, and the send button: ChatLine.OnIMEReturn."""
		text = self.GetText()
		self._push_sentence(text)
		if len(text) > 0 and len(text) != text.count(" "):
			first = text[0]
			if "#" == first:
				self._send_prefixed(text, chat.CHAT_TYPE_PARTY)
			elif "%" == first:
				self._send_prefixed(text, chat.CHAT_TYPE_GUILD)
			elif "!" == first:
				self._send_shout(text)
			else:
				self._send(text, chat.CHAT_TYPE_TALKING)
				self.ResetChat()
		else:
			self.ClearChat()
			_call(self.eventReturn)
		return True

	def OnPressEscapeKey(self):
		self.ClearChat()
		_call(self.eventEscape)
		return True

	def RunCloseEvent(self):
		_call(self.eventEscape)

	# --- history -------------------------------------------------------------------

	def _push_sentence(self, text):
		if len(text) <= 0:
			return
		if len(self.lastSentenceStack) > self.LAST_SENTENCE_STACK_SIZE:
			self.lastSentenceStack.pop(0)
		self.lastSentenceStack.append(text)

	def PrevLastSentence(self):
		if self.lastSentenceStack and self.lastSentencePos < len(self.lastSentenceStack):
			self.lastSentencePos += 1
			self.SetText(self.lastSentenceStack[-self.lastSentencePos])

	def NextLastSentence(self):
		if self.lastSentenceStack and self.lastSentencePos > 1:
			self.lastSentencePos -= 1
			self.SetText(self.lastSentenceStack[-self.lastSentencePos])

	# --- the field's events ------------------------------------------------------

	def on_changed(self, value, linebreak):
		"""The field's change event: Enter (linebreak), or a keystroke: the
		mark and the visible length limit (P10 spec D26)."""
		value = value if isinstance(value, str) else ""
		if linebreak:
			self.OnIMEReturn()
			return
		if nui_text.visible_length(value) > self.userMax:
			if self.board is not None:
				self.board.set_value(self.field, self.lastValue, caret="end")
			return
		self.lastValue = value
		if self.board is not None:
			self.board.set(mark=mark_of(value))

	def on_key(self, event):
		"""keydown on the field: Up and Down recall the history, Escape clears
		and runs the escape event, Tab does nothing; each is kept."""
		key = event.get("key_identifier")
		if key == KEY_UP:
			self.PrevLastSentence()
			return True
		if key == KEY_DOWN:
			self.NextLastSentence()
			return True
		if key == nui.KEY_ESCAPE:
			self.OnPressEscapeKey()
			return True
		if key == nui.KEY_TAB:
			return True
		return None

	def on_link(self, link):
		"""A press on a link: with the left Alt key down, the link pasted as
		legacy pastes it (into the focused field); else the item tooltip."""
		if not link:
			return
		if app.IsPressed(app.DIK_LALT):
			ime.PasteString(chat.GetLinkFromHyperlink(link))
		elif self.interface is not None:
			try:
				self.interface.MakeHyperlinkTooltip(link)
			except ReferenceError:
				pass

	def BindInterface(self, interface):
		self.interface = _keep(interface)


class _ModeShim(object):
	"""What uiChat.RefreshChatMode reaches in uiChat.chatInputSetList: legacy
	cycles every chat input's mode together (the chat window's and the
	log's). It holds its facade weakly."""

	def __init__(self, facade):
		self._facade = weakref.ref(facade)

	def OnRefreshChatMode(self):
		facade = self._facade()
		if facade is not None:
			facade.nui_refresh_chat_mode()


def add_mode_shim(facade):
	shim = _ModeShim(facade)
	uiChat.InsertChatInputSetWindow(shim)
	return shim


def remove_mode_shim(shim):
	if shim is not None and shim in uiChat.chatInputSetList:
		uiChat.chatInputSetList.remove(shim)


class ChatBoard(nui.Window):
	"""The chat's document and model; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "chat"
	FEEDS = {"view_chat": "system.view_chat"}

	def __init__(self, owner):
		self._owner = _keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"open": False, "shown": False, "chat_mode": chat.CHAT_TYPE_TALKING, "mark": "",
		        "history_height": ChatWindow.HISTORY_HEIGHT, "view_chat": True,
		        "lines_mode": "off" if nui_hud.has_engine_3a() else "view", "draft": ""}

	def on_scale_changed(self, scale):
		self._owner.nui_place()

	# Element handlers (element_on), through the board, so the runtime that
	# holds them keeps no facade alive.
	def nui_key(self, event):
		return self._owner.input.on_key(event)

	def nui_field_focus(self, event):
		self._owner.nui_field_focus()

	def nui_field_blur(self, event):
		self._owner.nui_field_blur()

	def nui_field_press(self, event):
		self._owner.nui_field_press(event.get("button", 0))

	@nui.on("changed")
	def on_changed(self, value, linebreak):
		self._owner.input.on_changed(value, bool(linebreak))

	@nui.on("mode")
	def on_mode(self, button):
		if button == 0:
			self._owner.OnChangeChatMode()

	@nui.on("send")
	def on_send(self, button):
		if button == 0:
			self._owner.input.OnIMEReturn()

	@nui.on("whisper")
	def on_whisper(self, button):
		if button == 0:
			_call(self._owner.sendWhisperEvent)

	@nui.on("open_log")
	def on_open_log(self, button):
		if button == 0:
			_call(self._owner.openChatLogEvent)

	@nui.on("resized")
	def on_resized(self, height):
		self._owner.nui_resized(height)

	@nui.on("link")
	def on_link(self, link):
		self._owner.input.on_link(link)

	@nui.on("wheel")
	def on_wheel(self, delta):
		self._owner.nui_wheel(delta)


def wheel_end_pos(view, delta):
	"""The end position after `delta` wheel notches (RmlUi's sign: positive
	is down, toward the newest line) over a view's lines: three lines a
	notch, as nuigame.ChatState reports the view; None when it holds every
	line (P10 spec D12)."""
	if nuigame is None or getattr(nuigame, "ChatState", None) is None:
		return None
	state = nuigame.ChatState(view)
	total, rows = int(state.get("total", 0)), int(state.get("rows", 0))
	if total <= rows or not delta:
		return None
	end = float(state.get("end_pos", 1.0)) + float(delta) * 3.0 / float(total - rows)
	return min(max(end, 0.0), 1.0)


class ChatWindow(object):
	"""uiChat.ChatWindow on NovaUI (Interface.wndChat)."""

	NUI_FACADE = True
	KEY = "chat"

	BOARD_START_COLOR = uiChat.ChatWindow.BOARD_START_COLOR
	BOARD_END_COLOR = uiChat.ChatWindow.BOARD_END_COLOR
	BOARD_MIDDLE_COLOR = uiChat.ChatWindow.BOARD_MIDDLE_COLOR
	CHAT_OUTLINE_COLOR = uiChat.ChatWindow.CHAT_OUTLINE_COLOR
	EDIT_LINE_HEIGHT = 25
	CHAT_WINDOW_WIDTH = 600

	# The history's height until the Interface's SetHeight: legacy's sizing
	# bar 138 px above the input line at 1600 x 900 (interfacemodule.py:119-120).
	HISTORY_HEIGHT = 138.0
	USER_MAX = 76

	def __init__(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self.board = None
		self.viewBoard = None       # the closed lines' board (Wave 3a engine only)
		self.focusProxy = None
		self.fieldFocused = False   # NovaUI's focus on the field, as its focus and blur events said
		self.modeShim = None
		self.attached = False
		self.boardState = chat.BOARD_STATE_VIEW
		self.endPos = 1.0
		self.shown = False
		self.size = (self.CHAT_WINDOW_WIDTH, 0)
		self.position = (0, 0)
		self.yLast = wndMgr.GetScreenHeight() - self.EDIT_LINE_HEIGHT - 37
		self.sendWhisperEvent = None
		self.openChatLogEvent = None
		self.input = ChatInput(None, "chat-input", self.USER_MAX, weak_event(self.CloseChat), weak_event(self.CloseChat))
		# Legacy's state calls (uichat.py:540-544, :616-631) and its mode
		# button's insult filter (ChatModeButton.__init__).
		for chat_type, rgb in ((chat.CHAT_TYPE_TALKING, colorInfo.CHAT_RGB_TALK), (chat.CHAT_TYPE_INFO, colorInfo.CHAT_RGB_INFO),
		                       (chat.CHAT_TYPE_NOTICE, colorInfo.CHAT_RGB_NOTICE), (chat.CHAT_TYPE_PARTY, colorInfo.CHAT_RGB_PARTY),
		                       (chat.CHAT_TYPE_GUILD, colorInfo.CHAT_RGB_GUILD), (chat.CHAT_TYPE_COMMAND, colorInfo.CHAT_RGB_COMMAND),
		                       (chat.CHAT_TYPE_SHOUT, colorInfo.CHAT_RGB_SHOUT), (chat.CHAT_TYPE_WHISPER, colorInfo.CHAT_RGB_WHISPER)):
			chat.SetChatColor(chat_type, rgb[0], rgb[1], rgb[2])
		self.chatID = chat.CreateChatSet(chat.CHAT_SET_CHAT_WINDOW)
		chat.SetBoardState(self.chatID, chat.BOARD_STATE_VIEW)
		net.EnableChatInsultFilter(uiChat.ENABLE_INSULT_CHECK)
		if not nui_hud.has_engine_2b():
			return
		try:
			self.board = ChatBoard(self)
			self.input.board = self.board
			self.board.element_on("chat-input", "keydown", self.board.nui_key)
			self.board.element_on("chat-input", "focus", self.board.nui_field_focus)
			self.board.element_on("chat-input", "blur", self.board.nui_field_blur)
			self.board.element_on("chat-input", "mousedown", self.board.nui_field_press)
			self.focusProxy = nui_hud.FocusProxy(self._on_focus_lost, self._on_focus_gained)
			if nui_hud.has_engine_3a():
				self.viewBoard = nui_chat_view.ChatViewBoard(self)
			self.modeShim = add_mode_shim(self)
			attach_feed()
			self.attached = True
		except Exception:
			self.nui_discard()
			raise

	# --- the make() protocol ------------------------------------------------------

	def nui_ready(self):
		return (self.board is not None and bool(self.board._doc) and nui_hud.has_engine_2b()
		        and (self.viewBoard is None or bool(self.viewBoard._doc)))

	def nui_discard(self):
		self._nui_discarded = True
		remove_mode_shim(self.modeShim)
		self.modeShim = None
		if self.attached:
			self.attached = False
			detach_feed()
		proxy, self.focusProxy = self.focusProxy, None
		if proxy is not None:
			proxy.destroy()
		for name in ("viewBoard", "board"):
			board = getattr(self, name)
			setattr(self, name, None)
			if board is not None:
				board.destroy()
		self.input.board = None
		nui_hud.forget(self.KEY, self)

	def Destroy(self):
		self.nui_discard()
		self.sendWhisperEvent = None
		self.openChatLogEvent = None

	# --- placement ------------------------------------------------------------------

	def SetSize(self, width, height):
		self.size = (width, height)

	def SetPosition(self, x, y):
		"""The legacy input line's top left in screen pixels: the body's bottom
		center goes on the line's bottom center, the taskbar's top."""
		self.position = (x, y)
		self.yLast = y
		self.nui_place()

	def SetHeight(self, height):
		"""The sizing bar at the screen height minus `height` (uichat.py:727-729),
		over the input line the Interface first puts EDIT_LINE_HEIGHT + 37 px
		above the bottom (interfacemodule.py:119): a history of height - 62
		legacy pixels, kept in dp as every classic size is (1dp is a legacy
		pixel), so it holds the same rows at every scale and wherever the
		taskbar later moves the chat."""
		self.nui_set(history_height=max(25.0, float(height - self.EDIT_LINE_HEIGHT - 37)))

	def Refresh(self):
		self.nui_place()

	def nui_place(self):
		"""The chat's body, and the closed lines' with it: the bottom center on
		the input line's bottom center, the taskbar's top."""
		s = nui.get_scale() or 1.0
		x, y = self.position
		for board in (self.board, self.viewBoard):
			if board is not None:
				board.set_position((x + self.CHAT_WINDOW_WIDTH // 2) / s, (y + self.EDIT_LINE_HEIGHT) / s, origin=(0.5, 1.0))

	def nui_sync_lines(self):
		"""Which lines show: open, the chat's own in edit mode; closed, the
		closed lines' board while the chat shows (the chat's element off), or
		with an older exe the chat's own element in view mode."""
		editing = self.boardState == chat.BOARD_STATE_EDIT
		self.nui_set(lines_mode="edit" if editing else ("off" if self.viewBoard is not None else "view"))
		view = self.viewBoard
		if view is None:
			return
		if self.shown and not editing:
			view.show()
		else:
			view.hide()

	def nui_set(self, **values):
		if self.board is not None:
			self.board.set(**values)

	# --- visibility ---------------------------------------------------------------

	def Show(self):
		self.shown = True
		if self.board is not None:
			self.board.show()
		self.input.ShowText()
		self.nui_set(shown=True)
		self.nui_sync_lines()

	def Hide(self):
		self.shown = False
		if self.board is not None:
			self.board.hide()
		self.nui_set(shown=False)
		self.nui_sync_lines()

	def IsShow(self):
		return self.shown and self.board is not None and self.board.is_visible()

	# --- events the Interface binds ---------------------------------------------------

	def BindInterface(self, interface):
		self.input.BindInterface(interface)

	def SetSendWhisperEvent(self, event):
		self.sendWhisperEvent = event

	def SetOpenChatLogEvent(self, event):
		self.openChatLogEvent = event

	# --- open and close -------------------------------------------------------------

	def OpenChat(self):
		"""uichat.py:643-673: the edit board state; the field, focused, reset
		to the mode's prefix with the caret at the end."""
		chat.SetBoardState(self.chatID, chat.BOARD_STATE_EDIT)
		self.boardState = chat.BOARD_STATE_EDIT
		self.nui_set(open=True)
		self.nui_sync_lines()
		if self.board is not None and self.board.focus("chat-input"):
			self.fieldFocused = True
		self.input.ResetChat()

	def CloseChat(self):
		"""uichat.py:675-695: the view board state; the scroll (D12) back at
		the newest line; the field and wndMgr's focus given up."""
		chat.SetBoardState(self.chatID, chat.BOARD_STATE_VIEW)
		self.boardState = chat.BOARD_STATE_VIEW
		if self.endPos != 1.0:
			self.endPos = 1.0
			chat.SetEndPos(self.chatID, 1.0)
		self.nui_set(open=False)
		self.nui_sync_lines()
		# NovaUI's focus off the field (when the field has it: not the log's
		# field's), then wndMgr's: the window wndMgr then activates may focus
		# its own field (FocusProxy on_gained), which must stay.
		if self.board is not None and self.fieldFocused:
			self.board.focus("chat-mode")
		if self.focusProxy is not None:
			self.focusProxy.release()

	def IsEditMode(self):
		return chat.BOARD_STATE_EDIT == self.boardState

	def SetChatFocus(self):
		if self.IsEditMode() and self.board is not None:
			self.board.focus("chat-input")

	def OnChangeChatMode(self):
		uiChat.RefreshChatMode()

	def nui_refresh_chat_mode(self):
		"""ChatInputSet.OnRefreshChatMode: the next mode, its prefix and name."""
		self.input.ChangeChatMode()

	# --- the field's focus (D11 b) ----------------------------------------------------

	def nui_field_focus(self):
		self.fieldFocused = True
		if self.focusProxy is not None:
			self.focusProxy.take()

	def nui_field_blur(self):
		self.fieldFocused = False

	def nui_field_press(self, button):
		"""The document takes no focus from a press (body focus: none), so a
		press on the field focuses it, as a press on a legacy edit line does."""
		if button == 0 and self.IsEditMode() and self.board is not None:
			self.board.focus("chat-input")

	def _on_focus_lost(self):
		"""A legacy edit line took wndMgr's focus: it gets the keys, the chat
		stays open."""
		if self.IsEditMode() and self.board is not None:
			self.board.focus("chat-mode")

	def _on_focus_gained(self):
		"""wndMgr gave the focus back (the window that took it closed)."""
		if self.IsEditMode() and self.board is not None:
			self.board.focus("chat-input")

	# --- the board's events -------------------------------------------------------------

	def nui_resized(self, height):
		self.nui_set(history_height=float(height))

	def nui_wheel(self, delta):
		if not self.IsEditMode():
			return
		end = wheel_end_pos("window", delta)
		if end is None:
			return
		self.endPos = end
		chat.SetEndPos(self.chatID, end)
