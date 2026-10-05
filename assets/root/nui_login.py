"""NovaUI login board (nui/windows/login/login.rml).

While config/metin2.cfg has UI_NUI_LOGIN 1, this board replaces the legacy
connect and login boards of introLogin.LoginWindow. The LoginWindow stays the
phase window and the network handler: the board only takes the input and
calls back into the legacy code (LoginWindow.Connect, the server board and
the exit handler), so a login ends in exactly the legacy code path.

The hooks below are what intrologin.py calls. Each takes the LoginWindow and
reads its `nuiBoard`; while that is None (flag off, an exe without the flag,
NovaUI unavailable, a right-to-left locale, a document that did not load)
every hook does nothing and returns the legacy value, so the legacy board
runs as before.

The board hides while a legacy popup (connecting, failures) is open: NovaUI
draws above the legacy UI and would otherwise cover the popup and keep its
keys. It comes back when the popup closes (after_popup).

The password is never put into the data model, a log line or a message.

With the board comes the intro ambience (nui/windows/intro-ambient): embers
and a light sweep over the logo, drawn under the board and never taking
input. It is shown before the board, so the board stays on top and keeps
the keyboard, hides with the board while a legacy popup is open, and goes
with the board.

The theme picker (nui/windows/theme-picker, nui_theme_picker.py) comes the
same way, as win.nuiPicker: shown after the ambience and before the board,
hidden while a legacy popup is open, gone with the board. It never takes the
focus, so a theme picked there leaves the board's caret and typed text.
"""

import weakref

import dbg
import systemSetting

try:
	import nui
except ImportError:  # a client without assets/root/nui.py
	class nui(object):
		"""Stands in for the nui module: nothing is available, and the class
		below can still be defined (nuitool lint reads its @nui.on lines)."""

		Window = object

		@staticmethod
		def on(event_name):
			return lambda method: method

		@staticmethod
		def is_available():
			return False

		@staticmethod
		def enabled_for_locale():
			return False

try:
	import nui_theme_picker
except ImportError:  # no nui module, or a client without nui_theme_picker.py
	nui_theme_picker = None


DOCUMENT = "nui/windows/login/login.rml"
AMBIENT_DOCUMENT = "nui/windows/intro-ambient/intro-ambient.rml"
ID_FIELD = "login-user"
PASSWORD_FIELD = "login-password"
ID_MAX = 19        # uiscript/loginwindow.py ID_LIMIT_COUNT
PASSWORD_MAX = 16  # uiscript/loginwindow.py PW_LIMIT_COUNT
EXCLUDED = "[]"    # intrologin.py keeps these out of the legacy EditLines

# The last decision open_board() made: "nui", or "legacy: <reason>".
LAST_DECISION = ""


def _as_text(value):
	if isinstance(value, str):
		return value
	if value is None or isinstance(value, bool):
		return ""
	return str(value)


def wanted():
	"""(True, "") when the NovaUI board should be used, else (False, reason)."""
	is_on = getattr(systemSetting, "IsUINuiLogin", None)
	if is_on is None or not is_on():
		return False, "flag off"
	if not nui.is_available():
		return False, "NovaUI unavailable"
	if not nui.enabled_for_locale():
		return False, "right-to-left locale"
	return True, ""


class LoginBoard(nui.Window):
	"""The board's document, model and handlers. intrologin.py reaches it only
	through the hooks below."""

	DOCUMENT = DOCUMENT
	MODEL = "login"
	MODAL = False

	def __init__(self, owner, on_choose, on_exit):
		# All of this before nui.Window.__init__: events the document raises
		# while it loads reach the handlers inside it.
		self._owner = weakref.proxy(owner)
		self._choose_cb = on_choose
		self._exit_cb = on_exit
		self._user = ""
		self._password = ""
		self.active = False       # the login state: between enter and leave
		self._suspended = False   # hidden for a legacy popup
		self._pending_focus = None
		nui.Window.__init__(self)

	def initial_model(self):
		return {"server": "@ui.LOGIN_DEFAULT_SERVERADDR", "user": "", "error": "", "error_on": ""}

	# --- handlers -------------------------------------------------------------
	# change fires on every edit, with linebreak on Enter. A binding that sets
	# the value can fire it too, so these only store what they get.

	@nui.on("user_edit")
	def on_user_edit(self, value, linebreak):
		self._user = _as_text(value)
		if self.get("error_on") == "user":
			self.set(error="", error_on="")
		if linebreak:
			self.focus(PASSWORD_FIELD)  # legacy: Enter in the ID line

	@nui.on("password_edit")
	def on_password_edit(self, value, linebreak):
		self._password = _as_text(value)
		if self.get("error_on") == "password":
			self.set(error="", error_on="")
		if linebreak:
			self._submit()

	@nui.on("submit")
	def on_submit(self):
		self._submit()

	@nui.on("exit")
	def on_exit(self):
		self._exit_cb()

	@nui.on("choose_server")
	def on_choose_server(self):
		self._choose_cb()

	def _submit(self):
		if not self.is_visible():
			return
		# The legacy checks (__OnClickLoginButton); the legacy EditLines could
		# not take [ or ] and stopped at their limits.
		user = "".join(c for c in self._user if c not in EXCLUDED)[:ID_MAX]
		password = "".join(c for c in self._password if c not in EXCLUDED)[:PASSWORD_MAX]
		if not user:
			self.set(error="@game.LOGIN_INPUT_ID", error_on="user")
			self.focus(ID_FIELD)
			return
		if not password:
			self.set(error="@game.LOGIN_INPUT_PASSWORD", error_on="password")
			self.focus(PASSWORD_FIELD)
			return
		self.set(error="", error_on="")
		# The password stays in the field, as legacy kept it in its EditLine,
		# so a retry needs only Enter.
		self._owner.Connect(user, password)

	# --- visibility -----------------------------------------------------------
	# Visible exactly while the login state is on, no legacy popup has it
	# suspended, and the stream does not log in by itself (autoLogin, where
	# legacy leaves its boards alone).

	def _may_show(self):
		if not self.active or self._suspended:
			return False
		stream = getattr(self._owner, "stream", None)
		if getattr(stream, "isAutoLogin", 0):
			return False
		popup = getattr(stream, "popupWindow", None)
		return not (popup is not None and popup.IsShow())

	def show_board(self):
		"""Shows the board when it may be seen, then gives the focus asked for
		while it was hidden. show() after hide() leaves no field focused."""
		if not self._may_show():
			return False
		self.show()
		pending, self._pending_focus = self._pending_focus, None
		if pending:
			self.focus(pending)
		return True

	def suspend(self):
		self._suspended = True
		self.hide()

	def resume(self):
		"""The legacy popup closed. A field asked for while hidden wins; else
		the password field once an ID is typed, as legacy focused it. The
		popup's own callback runs after this and may focus again."""
		self._suspended = False
		if self._pending_focus is None:
			self._pending_focus = PASSWORD_FIELD if self._user else ID_FIELD
		self.show_board()

	def focus_field(self, element_id):
		"""Focuses the field now if the board is visible, else at its next show."""
		if self.is_visible():
			self._pending_focus = None
			return self.focus(element_id)
		self._pending_focus = element_id
		return False

	# --- values ---------------------------------------------------------------

	def set_user(self, user):
		self._user = _as_text(user)
		self.set(user=self._user)

	def typed_values(self):
		return (self._user, self._password)

	def on_reload(self):
		# A locale change or hot reload re-loaded the document: its ID field
		# starts from the model and its password field empty.
		self.set(user=self._user)
		self._password = ""
		if self.is_visible():
			self.focus(PASSWORD_FIELD if self._user else ID_FIELD)


class IntroAmbient(nui.Window):
	"""Embers and the logo sweep under the board. It only draws: its body has
	pointer-events: none. Optional: when it does not load, the board runs
	without it."""

	DOCUMENT = AMBIENT_DOCUMENT


# --- hooks for intrologin.py -------------------------------------------------

def _board(win):
	return getattr(win, "nuiBoard", None)


def _ambient(win):
	return getattr(win, "nuiAmbient", None)


def _open_ambient(win):
	"""Shows the ambience. Called before the board is first shown, so the
	board, shown later, is drawn above it and takes the keyboard."""
	try:
		ambient = IntroAmbient()
	except Exception as error:
		dbg.TraceError("nui_login: the intro ambience could not be made (%s)" % type(error).__name__)
		return
	if not ambient._doc:
		ambient.destroy()
		dbg.TraceError("nui_login: %s did not load; the board runs without it" % AMBIENT_DOCUMENT)
		return
	win.nuiAmbient = ambient
	ambient.show()


def _show_ambient(win):
	"""After a popup: back under the board. A visible one is left alone,
	since a show would also pull it to the front."""
	ambient = _ambient(win)
	if ambient is not None and not ambient.is_visible():
		ambient.show()


def _hide_ambient(win):
	ambient = _ambient(win)
	if ambient is not None and ambient.is_visible():
		ambient.hide()


def _close_ambient(win):
	ambient = _ambient(win)
	if ambient is None:
		return
	win.nuiAmbient = None
	ambient.destroy()


def _picker(win):
	return getattr(win, "nuiPicker", None)


def _open_picker(win):
	"""Shows the theme picker. Called after the ambience and before the board
	is first shown, so the board keeps the front and the keyboard. Optional:
	without player themes (an exe without nui/theme/themes.json) or when its
	document does not load, the board runs without it."""
	get_themes = getattr(nui, "get_themes", None)
	if nui_theme_picker is None or get_themes is None or not get_themes():
		return
	try:
		picker = nui_theme_picker.ThemePicker()
	except Exception as error:
		dbg.TraceError("nui_login: the theme picker could not be made (%s)" % type(error).__name__)
		return
	if not picker._doc:
		picker.destroy()
		dbg.TraceError("nui_login: %s did not load; the board runs without it" % nui_theme_picker.ThemePicker.DOCUMENT)
		return
	win.nuiPicker = picker
	picker.show()


def _show_picker(win):
	"""After a popup: back, as the ambience. A visible one is left alone."""
	picker = _picker(win)
	if picker is not None and not picker.is_visible():
		picker.show()


def _hide_picker(win):
	picker = _picker(win)
	if picker is not None and picker.is_visible():
		picker.hide()


def _close_picker(win):
	picker = _picker(win)
	if picker is None:
		return
	win.nuiPicker = None
	picker.destroy()


def open_board(win, on_choose, on_exit):
	"""LoginWindow.Open: the board, or None to keep the legacy boards."""
	global LAST_DECISION
	close_board(win)
	use, reason = wanted()
	if not use:
		LAST_DECISION = "legacy: " + reason
		return None
	try:
		board = LoginBoard(win, on_choose, on_exit)
	except Exception as error:
		LAST_DECISION = "legacy: the board could not be made"
		dbg.TraceError("nui_login: the board could not be made (%s); using the legacy board" % type(error).__name__)
		return None
	if not board._doc:
		board.destroy()
		LAST_DECISION = "legacy: the document did not load"
		dbg.TraceError("nui_login: %s did not load; using the legacy board" % DOCUMENT)
		return None
	# The script loader showed every legacy part; the virtual keyboard types
	# into the legacy IME only, so it goes as well.
	for name in ("connectBoard", "loginBoard", "virtualKeyboard"):
		part = getattr(win, name, None)
		if part:
			part.Hide()
	# A focused hidden EditLine would take the typing and the IME.
	for name in ("idEditLine", "pwdEditLine"):
		line = getattr(win, name, None)
		if line and line.IsFocus():
			line.KillFocus()
	_open_ambient(win)
	_open_picker(win)
	LAST_DECISION = "nui"
	return board


def close_board(win):
	"""LoginWindow.Close, first: the popup callbacks Close runs find no board."""
	_close_ambient(win)
	_close_picker(win)
	board = _board(win)
	if board is None:
		return
	win.nuiBoard = None
	board.active = False
	board.destroy()


def enter_login_board(win):
	"""LoginWindow.__OpenLoginBoard: True when the board took over."""
	board = _board(win)
	if board is None:
		return False
	board.active = True
	board.focus_field(ID_FIELD)
	popup = getattr(getattr(win, "stream", None), "popupWindow", None)
	if popup is not None and popup.IsShow():
		# A popup opened before the board existed (same login): the board
		# comes up when it closes.
		board.suspend()
		popup.CloseEvent = after_popup(win, popup.CloseEvent)
		return True
	board.show_board()
	return True


def leave_login_board(win):
	"""LoginWindow.__OpenServerBoard."""
	board = _board(win)
	if board is None:
		return
	board.active = False
	board.hide()


def set_server(win, text):
	"""The connect text: the chosen server and channel, or K:addr:port."""
	board = _board(win)
	if board is not None:
		board.set(server=_as_text(text))


def before_popup(win):
	"""Right before stream.popupWindow.Open, after its Close."""
	board = _board(win)
	if board is not None:
		_hide_ambient(win)
		_hide_picker(win)
		board.suspend()


def after_popup(win, callback):
	"""Wraps a popup's close callback so the board comes back first. Without
	a board the callback is returned as it is (0 stays 0)."""
	if _board(win) is None:
		return callback
	owner = weakref.ref(win)

	def resume_then_call(*args):
		window = owner()
		board = _board(window) if window is not None else None
		if board is not None:
			_show_ambient(window)
			_show_picker(window)
			board.resume()
		if callback:
			return callback(*args)
		return None

	return resume_then_call


def focus_field(win, which):
	"""SetIDEditLineFocus ("user") and SetPasswordEditLineFocus."""
	board = _board(win)
	if board is None:
		return False
	board.focus_field(ID_FIELD if which == "user" else PASSWORD_FIELD)
	return True


def on_login_board(win):
	"""The login state, or None without a board."""
	board = _board(win)
	if board is None:
		return None
	return bool(board.active)


def typed_values(win):
	"""(ID, password) as typed, or None without a board."""
	board = _board(win)
	if board is None:
		return None
	return board.typed_values()


def restore_typed(win, user):
	"""Puts an ID typed before a direction change back. The password is not
	restored: there is no way to put it into a NovaUI field."""
	board = _board(win)
	if board is None:
		return False
	board.set_user(user)
	return True
