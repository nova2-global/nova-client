"""NovaUI server and channel board (nui/windows/server-board/server-board.rml).

While the "server-board" window flag is on (nui_windows), this board replaces
the legacy ServerBoard of introLogin.LoginWindow (uiscript loginwindow.py).
The hidden legacy lists stay the data: win.serverList and win.channelList
keep their items and selection, so the legacy server and channel logic
(__GetServerID, __GetChannelID, __SaveChannelInfo, NotifyChannelState,
ServerStateChecker, __OnClickSelectServerButton) runs unchanged. The board
mirrors the lists and drives them through SelectItem.

The hooks below are what intrologin.py calls. Each takes the LoginWindow and
reads its `nuiServerBoard`; while that is None (flag off, NovaUI
unavailable, a right-to-left locale, a document that did not load) every
hook does nothing, and the legacy board runs as before.

Enter: the legacy board took Enter on key-up; the board sets win.OnKeyUp,
which confirms while the board is shown and no popup is open.
"""

import weakref

import app
import serverInfo

import nui_login
import nui_windows

try:
	import nui
except ImportError:  # a client without assets/root/nui.py
	nui = nui_login.nui


DOCUMENT = "nui/windows/server-board/server-board.rml"
WINDOW_ID = "server-board"

# serverinfo.py STATE_DICT: the state texts ServerStateChecker reports.
STATE_CLASSES = {"....": "down", "NORM": "normal", "BUSY": "busy", "FULL": "full"}


class ServerBoard(nui.Window):
	"""The board's document, model and handlers. intrologin.py reaches it only
	through the hooks below."""

	DOCUMENT = DOCUMENT
	MODEL = "server_board"

	def __init__(self, owner, on_ok, on_exit):
		# Before nui.Window.__init__: the document's load events reach the
		# handlers inside it.
		self._owner = weakref.proxy(owner)
		self._ok_cb = on_ok
		self._exit_cb = on_exit
		self.active = False
		nui.Window.__init__(self)

	def initial_model(self):
		return {"servers": [], "server_line": -1, "channels": [], "channel_line": -1,
			"exit_label": "@ui.LOGIN_SELECT_EXIT"}

	@nui.on("pick_server")
	def on_pick_server(self, line):
		# The legacy list event (__OnSelectServer) asks for the channel states
		# and refreshes the channel list, which reaches refresh_channels.
		server_list = self._owner.serverList
		server_list.SelectItem(line)
		self.set(server_line=server_list.selectedLine)

	@nui.on("pick_channel")
	def on_pick_channel(self, line):
		channel_list = self._owner.channelList
		channel_list.SelectItem(line)
		self.set(channel_line=channel_list.selectedLine)

	@nui.on("confirm")
	def on_confirm(self):
		self._ok_cb()

	@nui.on("leave")
	def on_leave(self):
		self._exit_cb()

	def confirm(self):
		self._ok_cb()


# --- hooks for intrologin.py -------------------------------------------------

def _board(win):
	return getattr(win, "nuiServerBoard", None)


def _key_up_handler(win):
	"""win.OnKeyUp while the board exists: Enter confirms while the board is
	shown and no popup is open (the legacy board's key-up rule). The window
	is held weakly, so the handler makes no cycle with it."""
	owner = weakref.ref(win)

	def on_key_up(key):
		window = owner()
		board = _board(window) if window is not None else None
		if board is None or not board.active or not board.is_visible():
			return False
		popup = getattr(getattr(window, "stream", None), "popupWindow", None)
		if popup is not None and popup.IsShow():
			return False
		if key != app.DIK_RETURN:
			return False
		board.confirm()
		return True

	on_key_up.nui_server_board = True
	return on_key_up


def open_board(win, on_ok, on_exit):
	"""LoginWindow.Open: the board, or None to keep the legacy server board."""
	close_board(win)
	if not nui_windows.use(WINDOW_ID)[0]:
		return None
	try:
		board = ServerBoard(win, on_ok, on_exit)
	except Exception as error:
		nui_windows.note_failure(WINDOW_ID, "the controller could not be made (%s)" % type(error).__name__)
		return None
	if not board._doc:
		board.destroy()
		nui_windows.note_failure(WINDOW_ID, "the document did not load")
		return None
	server_board = getattr(win, "serverBoard", None)
	if server_board:
		server_board.Hide()  # the script loader showed it
	win.OnKeyUp = _key_up_handler(win)
	win.nuiServerBoard = board
	nui_login.place_picker(win)
	return board


def close_board(win):
	"""LoginWindow.Close: destroys the board and takes win.OnKeyUp away."""
	handler = getattr(win, "__dict__", {}).get("OnKeyUp")
	if getattr(handler, "nui_server_board", False):
		del win.OnKeyUp
	board = _board(win)
	if board is None:
		return
	win.nuiServerBoard = None
	board.active = False
	board.destroy()


def enter(win):
	"""LoginWindow.__OpenServerBoard: the legacy board was shown again, so it
	hides; both lists are mirrored, and the board shows."""
	board = _board(win)
	if board is None:
		return
	server_board = getattr(win, "serverBoard", None)
	if server_board:
		server_board.Hide()
	refresh_servers(win)
	refresh_channels(win)
	board.active = True
	board.show()


def leave(win):
	"""LoginWindow.__OpenLoginBoard: the board hides; its Exit is Close from
	now on, as the legacy button was relabeled."""
	board = _board(win)
	if board is None:
		return
	board.active = False
	board.hide()
	board.set(exit_label="@game.UI_CLOSE")


def refresh_servers(win):
	"""End of LoginWindow.__RefreshServerList: the server rows and selection."""
	board = _board(win)
	if board is None:
		return
	server_list = win.serverList
	servers = [{"line": line, "label": nui.plain_text(str(server_list.textDict.get(line, "")).strip())}
		for line in sorted(server_list.keyDict)]
	board.set(servers=servers, server_line=server_list.selectedLine)


def _channel_dict(win):
	region = getattr(win, "_LoginWindow__GetRegionID", lambda: 0)()
	server = win.serverList.GetSelectedItem()
	try:
		return serverInfo.REGION_DICT[region][server]["channel"]
	except (KeyError, TypeError):
		return {}


def refresh_channels(win):
	"""End of LoginWindow.__RefreshServerStateList: the channel rows, in the
	legacy list's order, with their state, and the selection."""
	board = _board(win)
	if board is None:
		return
	channel_list = win.channelList
	channel_dict = _channel_dict(win)
	channels = []
	for line in sorted(channel_list.keyDict):
		data = channel_dict.get(channel_list.keyDict[line], {})
		state = str(data.get("state", ""))
		channels.append({"line": line, "name": nui.plain_text(str(data.get("name", ""))),
			"state": nui.plain_text(state), "state_class": STATE_CLASSES.get(state, "unknown")})
	board.set(channels=channels, channel_line=channel_list.selectedLine)
