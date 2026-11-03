"""NovaUI whisper dialogs, one per partner (nui/windows/whisper/whisper.rml;
P16 spec 5.8).

While the whisper flag is on, the Interface makes WhisperDialog below
through nui_windows.make() instead of uiWhisper.WhisperDialog, for each
partner (OpenWhisperDialog, ShowWhisperDialog) and for the dialog without a
partner (OpenWhisperDialogWithoutTarget): a subclass of the legacy class
(nui_facade.Facade) whose uiscript loader puts proxies where the widgets
were. So sending (the insult check, the whisper packet, the own line in the
store), choosing a partner (and asking for its details at once), minimizing
to an edge button and closing (the Interface's), the GM look, the links, the
scroll and the size rule are legacy's code, and so are the block button
(NOVA-47: Block or Unblock as the client's list says, the packet and the
other label at once) and the partner's details (NOVA-48: the online or
offline mark and the language flag the server's answer shows,
SetTargetDetails; game.py asks every two seconds).

The lines stay in the C++ whisper store (CPythonChat's CWhisper): the
legacy text renderer's place is a proxy whose SetTargetName attaches the
partner's feed (nuigame.WhisperAttach), and the board's nui-chat-lines
element shows the window of lines C++ publishes for it, wrapped, the newest
at the bottom, so nothing runs per line or per frame (legacy draws them in
OnRender every frame).

What NovaUI adds (brief decision 3, spec D8): a minimized dialog keeps its
state in STATE (the draft, the size, the place and the scroll position, by
partner) until a dialog of that partner opens again and takes it, the
dialog is closed (not minimized) or the phase ends (end_phase(), through
nui_windows.PHASE_SCOPED); legacy loses the draft when
the Interface destroys the minimized dialog. Each dialog's board is
instanced (whisper_<n>); it draws below the legacy UI layer, as legacy's
window lived in it. While one of its fields has NovaUI's focus, the dialog
holds wndMgr's focus (nui_hud.FocusProxy), as a focused legacy edit line
would.

The boards are pooled (P18, Eddy: keep the slow-opening windows loaded, with
no memory growth): a dialog the Interface destroys (a close, a minimize)
puts its board in POOL, hidden, its lines and scroll emptied (lines_on), its
feed key 0, its fields empty and no dialog behind it
(nui_hud.PooledBoard, nui_hud.Pooled), and the next dialog takes a waiting
board instead of loading its document. At most POOL_BOUND boards wait; the
phase's end unloads them (nui_facade.end_phase). A dialog's Show writes both
fields from its own proxies, so a board never shows another conversation's
draft; its model (the partner, the feed key, the size, the place) is the
dialog's own at each show."""

import app
import chat
import ime
import nuigame
import ui
import uiScriptLocale
import uiWhisper

import nui
import nui_facade
import nui_form_proxies
import nui_hud
import nui_proxies

DOCUMENT = "nui/windows/whisper/whisper.rml"
INPUT = "whisper-input"
TARGET = "whisper-target"
# The control that parks NovaUI's focus when a legacy edit line takes
# wndMgr's (it takes no keys).
PARK = "whisper-send"
# The resize button's place at the load (uiwhisper.py:123): the first size
# is 20 beyond it, 300 x 200.
RESIZE_X, RESIZE_Y = 280, 180
RESIZE_SIZE = 20
# The chat line's limit in the uiscript (whisperdialog.py:186), until the
# first SetChatLineMax.
CHAT_LINE_LIMIT = 40
# Lines one wheel notch scrolls (the chat windows' three).
WHEEL_LINES = 3
# The scroll range's step: a change within half of it is the model's own
# write coming back, not a drag.
SCROLL_STEP = 0.01

# By partner name: {"draft", "width", "height", "x", "y", "pos"} of a
# minimized dialog (D8); "x" and "y" in dp, or None.
STATE = {}

# P18: the boards that wait for the next dialog. Four: a player who keeps up
# to four conversations going (Wave 4's busy case, B3W, shows three dialogs
# at once), minimizing and opening them in turn, never loads a document
# again, while a waiting board, emptied, keeps 40 elements (46 in
# cyberpunk), about 5 to 9 us of RmlUi's update a frame at Wave 3c's
# measured rate for hidden elements (0.12 to 0.20 us each), until the
# engine skips hidden documents. A fifth closed dialog's board unloads.
POOL_BOUND = 4
POOL = nui_hud.BoardPool("whisper", POOL_BOUND)
# What a waiting board shows: nothing of any conversation.
EMPTY = {"lines_on": [], "feed_key": 0, "target": "", "gm": False, "editing_target": False, "accept_shown": False,
         "block_shown": False, "blocked": False, "online_shown": False, "online": False, "flag_shown": False,
         "flag_src": ""}


def end_phase():
	"""nui_windows.end_phase(): the kept drafts go with the phase (each
	dialog's document goes with the dialog). No document to unload."""
	STATE.clear()
	return 0


def gm_mark_source():
	"""The GM mark's image (whisperdialog.py: LOCALE_PATH_COMMON +
	"/effect/ymirred.tga"), as a rooted store path."""
	try:
		common = app.GetLocalePathCommon()
	except Exception:
		common = "locale/common"
	return "/" + str(common).strip("/") + "/effect/ymirred.tga"


class _WhisperBoard(nui_hud.Pooled, nui_hud.RaisesOnPress, nui.Window):
	"""A whisper dialog's document; its events go to its dialog (none while
	it waits in POOL). A press on it raises the dialog, as legacy's window
	manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "whisper"
	INSTANCED = True
	# nui_hud.Pooled: emptied before the board waits, the focus parked.
	FIELDS = (INPUT, TARGET)
	PARK = PARK

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)
		if self._doc:
			for field in (INPUT, TARGET):
				self.element_on(field, "keydown", self._on_key)
				self.element_on(field, "focus", self._on_focus)

	def initial_model(self):
		return dict(self._initial)

	# Element handlers, through the board, so the runtime that holds them
	# keeps no dialog alive.
	def _on_key(self, event):
		if not self.is_visible():
			return None
		return self._owner._key(event.get("target_id"), event.get("key_identifier"))

	def _on_focus(self, event):
		self._owner._field_focused()

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("input_press")
	def on_input_press(self, button):
		self.raise_for(button)
		if button == 0:
			self.focus(INPUT)

	@nui.on("target_press")
	def on_target_press(self, button):
		self.raise_for(button)
		if button == 0:
			self.focus(TARGET)

	@nui.on("accept_press")
	def on_accept_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.acceptButton.click()

	@nui.on("minimize_press")
	def on_minimize_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.minimizeButton.click()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.closeButton.click()

	@nui.on("send_press")
	def on_send_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.sendButton.click()

	@nui.on("block_press")
	def on_block_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.blockButton.click()

	@nui.on("input_change")
	def on_input_change(self, value):
		self._owner._input_changed(value)

	@nui.on("scroll")
	def on_scroll(self, value):
		self._owner._scroll(value)

	@nui.on("wheel")
	def on_wheel(self, delta):
		self._owner._wheel(delta)

	@nui.on("resized")
	def on_resized(self, width, height):
		self._owner._resized(width, height)

	@nui.on("link")
	def on_link(self, link):
		self._owner._link(link)


class _LinesProxy(nui_proxies._Shown):
	"""WhisperDialog.TextRenderer's place: SetTargetName attaches the
	partner's whisper feed (nuigame.WhisperAttach; a second dialog of the
	same partner shares its key), detaching the one it had."""

	def __init__(self, on_key):
		self.targetName = ""
		self.key = 0
		self._on_key = on_key

	def SetTargetName(self, targetName):
		self.targetName = targetName
		name = targetName if isinstance(targetName, str) else ""
		key = int(nuigame.WhisperAttach(name) or 0) if name else 0
		self.detach()
		self.key = key
		self._on_key(key)

	def detach(self):
		key, self.key = self.key, 0
		if key:
			nuigame.WhisperDetach(key)


class WhisperDialog(nui_facade.Facade, uiWhisper.WhisperDialog):
	"""uiWhisper.WhisperDialog on NovaUI (Interface.whisperDialogDict,
	dlgWhisperWithoutTarget)."""

	# None: the Interface keeps one per partner, and none takes over another.
	KEY = None
	BOARD = _WhisperBoard

	def __init__(self, eventMinimize, eventClose):
		self._size = (0, 0)
		self.focusProxy = None
		self.textRenderer = None
		self.nui_begin()
		try:
			uiWhisper.WhisperDialog.__init__(self, eventMinimize, eventClose)
			if self.demand is not None:
				self.focusProxy = nui_hud.FocusProxy(self._on_focus_lost, self._on_focus_gained)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			"target": "",
			"editing_target": False,
			"accept_shown": False,
			"minimize_shown": True,
			"gm": False,
			"gm_mark_src": gm_mark_source(),
			"feed_key": 0,
			"width": float(RESIZE_X + RESIZE_SIZE),
			"height": float(RESIZE_Y + RESIZE_SIZE),
			"pos": 1.0,
			"input_max": CHAT_LINE_LIMIT,
			"target_max": self._limits.PLAYER_NAME_INPUT_MAX,
			# The block button (NOVA-47): shown for a partner, Unblock while
			# the partner is on the block list.
			"block_shown": False,
			"blocked": False,
			# The partner's details (NOVA-48): the online or offline mark and
			# the language flag (a rooted path), once the server answered.
			"online_shown": False,
			"online": False,
			"flag_shown": False,
			"flag_src": "",
			# P18: the scroll, a list of one entry while the board shows, none
			# while it waits in POOL (the lines go with the feed key 0).
			"lines_on": [1],
		}

	def nui_demand(self):
		"""P18: the board comes from POOL and goes back to it."""
		return nui_hud.PooledBoard(POOL, self._make_board, self._restore_board, self._keep_board,
		                           self._empty_board, self._adopt_board)

	def _adopt_board(self, board):
		board.adopt(self)

	def _empty_board(self, board):
		"""Nothing of this conversation stays on a board that waits."""
		board.set(**EMPTY)

	def nui_discard(self):
		lines = getattr(self, "textRenderer", None)
		if isinstance(lines, _LinesProxy):
			lines.detach()
		proxy, self.focusProxy = getattr(self, "focusProxy", None), None
		if proxy is not None:
			proxy.destroy()
		nui_facade.Facade.nui_discard(self)

	# --- the proxies' callbacks ---------------------------------------------------------

	def _on_title(self, text):
		self.nui_set(target=text or "")

	def _on_buttons(self, button=None):
		self.nui_set(accept_shown=bool(self.acceptButton.shown), minimize_shown=bool(self.minimizeButton.shown))

	def _on_gm(self, shown):
		self.nui_set(gm=bool(shown))

	def _on_scroll(self, scroll):
		self.nui_set(pos=float(scroll.pos))

	def _on_feed(self, key):
		self.nui_set(feed_key=int(key))

	def _on_block(self, button=None):
		block = getattr(self, "blockButton", None)
		if block is None:
			return
		self.nui_set(block_shown=bool(block.shown), blocked=block.text == uiScriptLocale.UNBLOCK_PLAYER)

	def _on_online_image(self, path):
		self.nui_set(online=path == uiWhisper.WhisperDialog.ONLINE_IMAGE)

	def _on_online_shown(self, shown):
		self.nui_set(online_shown=bool(shown))

	def _on_flag_image(self, path):
		self.nui_set(flag_src=("/" + path.lstrip("/")) if path else "")

	def _on_flag_shown(self, shown):
		self.nui_set(flag_shown=bool(shown))

	def _value(self, field_id):
		board = self.nui_board()
		return board.get_value(field_id) if board is not None and board.is_visible() else None

	def _field(self, field_id, maximum):
		field = nui_form_proxies.FieldProxy(field_id, self._on_field)
		field.reader = lambda: self._value(field_id)
		field.SetMax(maximum)
		return field

	def _on_field(self, field, what):
		if what == "max":
			if field.field_id == INPUT:
				self.nui_set(input_max=int(field.max))
			else:
				self.nui_set(target_max=int(field.max))
			return
		if what == "shown" and field.field_id == TARGET:
			self.nui_set(editing_target=bool(field.shown))
			return
		board = self.nui_board()
		if board is None or not board.is_visible():
			return
		if what == "text":
			board.set_value(field.field_id, field.text, caret="end")
		elif what == "focus":
			board.focus(field.field_id)
		elif what == "kill_focus":
			board.focus(PARK)

	# --- the loader (uiwhisper.py WhisperDialog.LoadDialog, on proxies) ---------------------

	def LoadDialog(self):
		# The uiscript's style (whisperdialog.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")

		self.titleName = nui_proxies.TextProxy(self._on_title)
		self.titleNameEdit = self._field(TARGET, self._limits.PLAYER_NAME_INPUT_MAX)
		self.closeButton = nui_proxies.ButtonProxy()
		self.scrollBar = nui_form_proxies.ScrollProxy(self._on_scroll)
		self.chatLine = self._field(INPUT, CHAT_LINE_LIMIT)
		self.minimizeButton = nui_proxies.ButtonProxy(self._on_buttons)
		self.ignoreButton = nui_form_proxies.ToggleProxy()
		self.reportViolentWhisperButton = nui_proxies.ButtonProxy()
		self.acceptButton = nui_proxies.ButtonProxy(self._on_buttons)
		self.sendButton = nui_proxies.ButtonProxy()
		self.board = nui_proxies.BoardProxy(RESIZE_X, RESIZE_Y + RESIZE_SIZE)
		self.editBar = nui_proxies.BoardProxy(RESIZE_X - 18, 50)
		self.gamemasterMark = nui_proxies.ImageProxy(image=gm_mark_source())
		self.gamemasterMark.on_show = self._on_gm
		# The block button and the partner's details (NOVA-47, NOVA-48).
		self.blockButton = nui_proxies.ButtonProxy(self._on_block)
		self.online = nui_proxies.ImageProxy(self._on_online_image)
		self.online.on_show = self._on_online_shown
		self.flag = nui_proxies.ImageProxy(self._on_flag_image)
		self.flag.on_show = self._on_flag_shown
		self.scrollBar.SetScrollBarSize(RESIZE_X - 160)

		self.gamemasterMark.Hide()
		self.titleName.SetText("")
		self.titleNameEdit.SetText("")
		self.minimizeButton.SetEvent(ui.__mem_func__(self.Minimize))
		self.closeButton.SetEvent(ui.__mem_func__(self.Close))
		self.scrollBar.SetPos(1.0)
		self.scrollBar.SetScrollEvent(ui.__mem_func__(self.OnScroll))
		self.chatLine.SetReturnEvent(ui.__mem_func__(self.SendWhisper))
		self.chatLine.SetEscapeEvent(ui.__mem_func__(self.Minimize))
		self.chatLine.SetMultiLine()
		self.sendButton.SetEvent(ui.__mem_func__(self.SendWhisper))
		self.titleNameEdit.SetReturnEvent(ui.__mem_func__(self.AcceptTarget))
		self.titleNameEdit.SetEscapeEvent(ui.__mem_func__(self.Close))
		self.ignoreButton.SetToggleDownEvent(ui.__mem_func__(self.IgnoreTarget))
		self.ignoreButton.SetToggleUpEvent(ui.__mem_func__(self.IgnoreTarget))
		self.reportViolentWhisperButton.SetEvent(ui.__mem_func__(self.ReportViolentWhisper))
		self.acceptButton.SetEvent(ui.__mem_func__(self.AcceptTarget))
		self.blockButton.SetEvent(ui.__mem_func__(self.BlockPlayer))
		self.blockButton.Hide()
		self.online.Hide()
		self.flag.Hide()

		self.textRenderer = _LinesProxy(self._on_feed)
		self.textRenderer.SetParent(self)
		self.textRenderer.SetPosition(20, 28)
		self.textRenderer.SetTargetName("")
		self.textRenderer.Show()

		self.resizeButton = nui_form_proxies.ResizeProxy(RESIZE_X, RESIZE_Y, RESIZE_SIZE)
		self.resizeButton.SetParent(self)
		self.resizeButton.SetSize(RESIZE_SIZE, RESIZE_SIZE)
		self.resizeButton.SetPosition(RESIZE_X, RESIZE_Y)
		self.resizeButton.SetMoveEvent(ui.__mem_func__(self.ResizeWhisperDialog))
		self.resizeButton.Show()

		self.ResizeWhisperDialog()

	# --- what NovaUI changes (P16 spec 5.8.3) -----------------------------------------

	def SetSize(self, width, height):
		"""The board's size; the legacy window stays 0 x 0. GetWidth and
		GetHeight answer it, as legacy's own size (OpenWithTarget sizes the
		whisper box from them)."""
		self._size = (int(width), int(height))
		self.nui_set(width=float(width), height=float(height))

	def GetWidth(self):
		return self._size[0]

	def GetHeight(self):
		return self._size[1]

	def OpenWithTarget(self, targetName):
		"""Legacy's (the store's whisper, the box, the focus, the title; the
		text renderer's proxy attaches the feed), then a minimized dialog's
		state: its size, place, draft and scroll position. The state goes
		once applied (Minimize keeps it again): a dialog the Interface
		destroys without a minimize (RegisterTemporaryWhisperDialog replaces
		it) must not bring back a draft that was sent since."""
		uiWhisper.WhisperDialog.OpenWithTarget(self, targetName)
		kept = STATE.pop(targetName, None) if isinstance(targetName, str) else None
		if not kept:
			return
		width, height = int(kept["width"]), int(kept["height"])
		if (width, height) != self._size:
			self.resizeButton.SetPosition(width - RESIZE_SIZE, height - RESIZE_SIZE)
			self.ResizeWhisperDialog()
		if kept.get("x") is not None:
			self._place = (kept["x"], kept["y"])
			board = self.nui_board()
			if board is not None:
				board.set_position(kept["x"], kept["y"])
		if kept.get("draft"):
			self.chatLine.SetText(kept["draft"])
		self.scrollBar.SetPos(kept.get("pos", 1.0))

	def Minimize(self):
		"""The dialog's state into STATE (D8), then legacy's, which hands the
		partner to the Interface's minimize event (an edge button) and gets
		this dialog destroyed."""
		self._keep_state()
		uiWhisper.WhisperDialog.Minimize(self)

	def Close(self):
		"""Legacy's (the store's whisper cleared, the close event); a kept
		state goes with it."""
		if isinstance(self.targetName, str):
			STATE.pop(self.targetName, None)
		uiWhisper.WhisperDialog.Close(self)

	def OnMouseLeftButtonDown(self):
		"""Nothing: the 0 x 0 window takes no press; a link press comes from
		the board (link)."""

	def Show(self):
		nui_facade.Facade.Show(self)
		board = self.nui_board()
		if board is None:
			return
		# The fields as legacy left them (a draft set while hidden), and the
		# focus legacy gave before the show (OpenWithTarget, the Interface).
		# Both are written, empty ones too, also the partner field under its
		# data-if: a board from POOL shows this dialog's text only (P18).
		for field in (self.chatLine, self.titleNameEdit):
			board.set_value(field.field_id, field.text or "", caret="end", even_hidden=True)
		for field in (self.titleNameEdit, self.chatLine):
			if field.focused and field.shown:
				board.focus(field.field_id)
				break

	def Hide(self):
		nui_facade.Facade.Hide(self)
		if not self.IsShow() and self.focusProxy is not None:
			self.focusProxy.release()

	# --- the board's events -------------------------------------------------------------

	def _keep_state(self):
		name = self.targetName
		if not isinstance(name, str) or not name:
			return
		place = None
		board = self.nui_board()
		box = board.element_box("") if board is not None else None
		if box and box[2] > 0 and box[3] > 0:
			scale = nui.get_scale() or 1.0
			place = (box[0] / scale, box[1] / scale)
		elif self._place is not None:
			place = self._place
		width, height = self._size
		STATE[name] = {"draft": self.chatLine.GetText(), "width": width, "height": height,
		               "x": place[0] if place else None, "y": place[1] if place else None,
		               "pos": float(self.scrollBar.GetPos())}

	def _input_changed(self, value):
		"""The input's change: its text, with no line break. Legacy's edit
		line wraps but never holds one. Keeping Enter's keydown does not
		stop the textarea's line break: Windows sends the key's WM_CHAR as
		well, which reaches the field as text input after the send cleared
		it, so the next whisper would start with it. The caret stays after
		what was typed."""
		line = getattr(self, "chatLine", None)
		if line is None:
			return
		value = "" if value is None else str(value)
		if "\n" in value or "\r" in value:
			old = line.text
			start = 0
			while start < min(len(old), len(value)) and old[start] == value[start]:
				start += 1
			end = 0
			while end < min(len(old), len(value)) - start and old[-1 - end] == value[-1 - end]:
				end += 1
			typed_end = len(value) - end
			caret = typed_end - value.count("\n", 0, typed_end) - value.count("\r", 0, typed_end)
			value = value.replace("\r", "").replace("\n", "")
			board = self.nui_board()
			if board is not None and board.is_visible():
				board.set_value(INPUT, value, caret=max(0, min(caret, len(value))))
		line.typed(value)

	def _key(self, element_id, key):
		"""A key in a field: legacy's edit line events. Enter and Escape are
		kept (no legacy Escape chain); the line break Enter's text input
		still types goes in _input_changed."""
		field = self.titleNameEdit if element_id == TARGET else self.chatLine
		if key in (nui.KEY_RETURN, nui.KEY_NUMPADENTER):
			field.fire_return()
			return True
		if key == nui.KEY_ESCAPE:
			field.fire_escape()
			return True
		return None

	def _field_focused(self):
		if self.focusProxy is not None:
			self.focusProxy.take()

	def _on_focus_lost(self):
		"""A legacy edit line took wndMgr's focus: it gets the keys."""
		board = self.nui_board()
		if board is not None:
			board.focus(PARK)

	def _on_focus_gained(self):
		"""wndMgr gave the focus back (the window that took it closed)."""
		board = self.nui_board()
		if board is None or not board.is_visible():
			return
		field = self.titleNameEdit if self.titleNameEdit.shown else self.chatLine
		board.focus(field.field_id)

	def _scroll(self, value):
		# The range echoes the model's position as its document loads (RmlUi
		# dispatches change when a binding sets a slider's value), also in the
		# probe's board, which nui_end() makes before the Interface's
		# LoadDialog: no scroll bar proxy yet (None after Destroy).
		scroll = getattr(self, "scrollBar", None)
		if scroll is None:
			return
		try:
			value = min(max(float(value), 0.0), 1.0)
		except (TypeError, ValueError):
			return
		if abs(value - scroll.GetPos()) < SCROLL_STEP / 2.0:
			return
		scroll.moved(value)

	def _wheel(self, delta):
		"""Three lines a notch (RmlUi's sign: positive is down, toward the
		newest), by the store's rule: the window ends at int((n - v) * pos)
		+ v - 1 for v = rows - 1 (PythonChat.cpp:886-918)."""
		key = int(self.textRenderer.key) if isinstance(self.textRenderer, _LinesProxy) else 0
		state = nuigame.WhisperState(key) if key else None
		if not state or not delta:
			return
		total, rows = int(state.get("total", 0)), int(state.get("rows", 0))
		span = total - max(0, rows - 1)
		if span <= 0:
			return
		pos = float(self.scrollBar.GetPos()) + float(delta) * WHEEL_LINES / float(span)
		self.scrollBar.moved(min(max(pos, 0.0), 1.0))

	def _resized(self, width, height):
		"""The resize corner's drag: legacy's resize button 20 inside the new
		corner, its move event (ResizeWhisperDialog) sizes the dialog."""
		try:
			width, height = int(round(float(width))), int(round(float(height)))
		except (TypeError, ValueError):
			return
		self.resizeButton.dragged(width - RESIZE_SIZE, height - RESIZE_SIZE)

	def _link(self, link):
		"""A press on a link: legacy's OnMouseLeftButtonDown with the link the
		press found (uiwhisper.py:299-306)."""
		if not link:
			return
		if app.IsPressed(app.DIK_LALT):
			ime.PasteString(chat.GetLinkFromHyperlink(link))
		else:
			self.interface.MakeHyperlinkTooltip(link)
