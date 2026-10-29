"""NovaUI login screen, one page (nui/windows/login/login.rml).

While the "login" window flag is on (nui_windows: UI_NUI_LOGIN 1, or +login
in UI_NUI_WINDOWS), this screen replaces the legacy connect, server and
login boards of introLogin.LoginWindow, as the reviewed Login and Register
boards draw it: the saved accounts (nui_accounts.py; names, the characters
seen at the last log in and their levels, never a password), the account
card with its Log in and Create account tabs, Remember me, the server's
state and player count, the server and channel menu (Channel: Auto picks a
channel at each log in, pick_channel), and the links (nui_links.py; a link
without an address is not drawn). The LoginWindow stays the phase window
and the network handler: the screen only takes the input and calls back
into it (LoginWindow.NuiLogin, NuiChooseServer, NuiCreateAccount, the exit
handler), so a log in ends in exactly the legacy code path. The Create
account tab shows only on a client that can create accounts
(net.CreateAccount, protocol version 4); its rules are the auth core's
(check_registration).

The hooks below are what intrologin.py calls. Each takes the LoginWindow and
reads its `nuiBoard`; while that is None (flag off, an exe without the flag,
NovaUI unavailable, a right-to-left locale, a document that did not load)
every hook does nothing and returns the legacy value, so the legacy boards
run as before.

The screen hides while a legacy popup (connecting, failures) is open:
NovaUI draws above the legacy UI and would otherwise cover the popup and
keep its keys. It comes back when the popup closes (after_popup).

The passwords are never put into the data model, a log line or a message:
the show-password eye copies the text between two fields (set_value).

With the board comes the intro ambience (nui/windows/intro-ambient): embers
and a light sweep over the logo, drawn under the board and never taking
input. It is shown before the board, so the board stays on top and keeps
the keyboard, hides with the board while a legacy popup is open, and goes
with the board.

The theme picker (nui/windows/theme-picker, nui_theme_picker.py) comes the
same way, as win.nuiPicker: shown after the ambience and before the board,
hidden while a legacy popup is open, gone with the board. It never takes the
focus, so a theme picked there leaves the board's caret and typed text. It
sits below the NovaUI locale strip when there is one, and keeps clear of the
boards and the keyboard: while it overlaps one of them that is shown, its
sheet hides it (place_picker).

The NovaUI virtual keyboard (nui/windows/virtual-keyboard,
nui_virtual_keyboard.py) comes with the board while the "virtual-keyboard"
flag is on, as win.nuiKeyboard: shown right before the board each time the
board shows, hidden with it and while a popup is open, gone with it. It
types into the board's last focused field (LoginBoard.type_text), and the
board rises above it (the model's keyboard key).
"""

import time
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

try:
	import nui_virtual_keyboard
except ImportError:  # no nui module, or a client without nui_virtual_keyboard.py
	nui_virtual_keyboard = None

import nui_accounts
import nui_links
import nui_windows


DOCUMENT = "nui/windows/login/login.rml"
AMBIENT_DOCUMENT = "nui/windows/intro-ambient/intro-ambient.rml"
WINDOW_ID = "login"
KEYBOARD_ID = "virtual-keyboard"
ID_FIELD = "login-user"
PASSWORD_FIELD = "login-password"
PASSWORD_SHOWN = "login-password-shown"  # the same field as text, while the eye is on
ID_MAX = 19        # uiscript/loginwindow.py ID_LIMIT_COUNT
PASSWORD_MAX = 16  # uiscript/loginwindow.py PW_LIMIT_COUNT
EXCLUDED = "[]"    # intrologin.py keeps these out of the legacy EditLines
# The Create account tab's fields, in their Enter order.
REG_FIELDS = ("reg-user", "reg-email", "reg-password", "reg-confirm", "reg-code")

# The last decision open_board() made: "nui", or "legacy: <reason>".
LAST_DECISION = ""


def _as_text(value):
	if isinstance(value, str):
		return value
	if value is None or isinstance(value, bool):
		return ""
	return str(value)


def _can_register():
	"""Whether this client can create accounts (net.CreateAccount, protocol
	version 4): without it the card has no Create account tab."""
	try:
		import net
	except ImportError:
		return False
	return callable(getattr(net, "CreateAccount", None))


def wanted():
	"""(True, "") when the NovaUI board should be used, else (False, reason):
	the "login" window flag (nui_windows.use), which UI_NUI_LOGIN 1 turns on."""
	return nui_windows.use("login")


# The texts the controller formats itself (uiScriptLocale, the ui locale
# file), with the English text as a fallback for a locale file without them.
_TEXT_FALLBACK = {
	"NUI_LOGIN_LAST_PLAYED": "Last played %s, %s",
	"NUI_LOGIN_NOW": "just now",
	"NUI_LOGIN_MINUTES": "%d min ago",
	"NUI_LOGIN_HOURS": "%dh ago",
	"NUI_LOGIN_YESTERDAY": "yesterday",
	"NUI_LOGIN_DAYS": "%d days ago",
	"NUI_LOGIN_CHANNEL": "Channel: %s",
	"NUI_LOGIN_AUTO": "Auto",
	"NUI_LOGIN_PLAYERS": "%s online",
}


def _text(key):
	try:
		import uiScriptLocale
		value = getattr(uiScriptLocale, key, None)
	except ImportError:
		value = None
	return value if isinstance(value, str) and value else _TEXT_FALLBACK[key]


def _grouped(number):
	"""1284 as "1,284" (the separator the players' count uses everywhere)."""
	return "{:,}".format(int(number))


# The registration rules, the auth core's (CInputAuth): a client check
# first, so a mistake costs no round trip. Square brackets cannot be typed
# into the login fields (intrologin.py keeps them out), so a password with
# one could never log in.
RESERVED_LOGINS = ("admin", "administrator", "gm", "gamemaster", "root", "system", "server", "support", "nova",
                   "moderator", "staff")
REG_LOGIN_MIN = 4
REG_LOGIN_MAX = 30
REG_PASSWORD_MIN = 8
REG_PASSWORD_MAX = PASSWORD_MAX
REG_EMAIL_MAX = 64
REG_CODE_LEN = 7

# GC::ACCOUNT_CREATE_RESULT's codes (account_packets.h) and what the card
# says for each: (the field the error belongs to, the text).
ACCOUNT_CREATE_OK = 0
CREATE_RESULTS = {
	1: ("user", "@ui.NUI_LOGIN_ERR_TAKEN"),
	2: ("user", "@ui.NUI_LOGIN_ERR_LOGIN"),
	3: ("password", "@ui.NUI_LOGIN_ERR_PASSWORD"),
	4: ("email", "@ui.NUI_LOGIN_ERR_EMAIL"),
	5: ("code", "@ui.NUI_LOGIN_ERR_CODE"),
	6: ("rules", "@ui.NUI_LOGIN_ERR_RULES"),
	7: ("", "@ui.NUI_LOGIN_ERR_LIMIT"),
	8: ("", "@ui.NUI_LOGIN_ERR_DISABLED"),
	9: ("", "@ui.NUI_LOGIN_ERR_BUSY"),
	10: ("", "@ui.NUI_LOGIN_ERR_FAILED"),
}


def _is_email(text):
	"""The auth core's email rule: printable ASCII without spaces, one @, a
	local part, and a domain with a dot that neither starts nor ends it."""
	if not text or len(text) > REG_EMAIL_MAX or any(not 33 <= ord(c) <= 126 for c in text):
		return False
	if text.count("@") != 1:
		return False
	local, domain = text.split("@")
	return bool(local) and "." in domain and not domain.startswith(".") and not domain.endswith(".")


def check_registration(user, email, password, confirm, code, rules):
	"""(field, error key) for the first rule the values break, or None. The
	login is checked as the auth core stores it: trimmed and lower-cased."""
	login = user.strip().lower()
	if not (REG_LOGIN_MIN <= len(login) <= REG_LOGIN_MAX) or not all(c.isalnum() and ord(c) < 128 for c in login):
		return ("user", "@ui.NUI_LOGIN_ERR_LOGIN")
	if login in RESERVED_LOGINS:
		return ("user", "@ui.NUI_LOGIN_ERR_TAKEN")
	if not _is_email(email.strip()):
		return ("email", "@ui.NUI_LOGIN_ERR_EMAIL")
	if not (REG_PASSWORD_MIN <= len(password) <= REG_PASSWORD_MAX) \
			or any(not 32 <= ord(c) <= 126 or c in EXCLUDED for c in password):
		return ("password", "@ui.NUI_LOGIN_ERR_PASSWORD")
	if confirm != password:
		return ("confirm", "@ui.NUI_LOGIN_ERR_CONFIRM")
	if len(code) != REG_CODE_LEN or not all("0" <= c <= "9" for c in code):
		return ("code", "@ui.NUI_LOGIN_ERR_CODE")
	if not rules:
		return ("rules", "@ui.NUI_LOGIN_ERR_RULES")
	return None


# A channel's legacy state text (serverInfo.STATE_DICT) as the card names it.
def _state_of(text):
	try:
		import serverInfo
		states = serverInfo.STATE_DICT
	except (ImportError, AttributeError):
		states = {0: "....", 1: "NORM", 2: "BUSY", 3: "FULL"}
	if text == states.get(1):
		return "ok"
	if text == states.get(2):
		return "busy"
	if text == states.get(3):
		return "full"
	if text == states.get(0):
		return "down"
	return "unknown"


def pick_channel(channels, users, last):
	"""Channel: Auto. channels maps a channel id to its state ("ok", "busy",
	"full", "down", "unknown"), users a channel id to its players when the
	server told them (else empty), last is the channel played last. The
	channel with the fewest players among those that take players when the
	counts are known; else an "ok" one before a "busy" one, the last played
	first among equals, then the lowest id. With no channel known to take
	players: the last played, else the lowest id (the server then answers)."""
	open_ids = sorted(cid for cid, state in channels.items() if state in ("ok", "busy"))
	if open_ids:
		if users and all(cid in users for cid in open_ids):
			return min(open_ids, key=lambda cid: (users[cid], cid != last, cid))
		return min(open_ids, key=lambda cid: (channels[cid] != "ok", cid != last, cid))
	if last in channels:
		return last
	return min(channels) if channels else 0


class LoginBoard(nui.Window):
	"""The login screen's document, model and handlers. intrologin.py reaches
	it only through the hooks below."""

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
		self._reg = {"user": "", "email": "", "password": "", "confirm": "", "code": ""}
		self.active = False       # the login state: between enter and leave
		self._suspended = False   # hidden for a legacy popup
		self._pending_focus = None
		self._active_field = ID_FIELD  # where the virtual keyboard types
		self.before_show = None   # called right before each show (the keyboard)
		# The server and channel: the server id, the channel id or 0 for Auto,
		# and the players per channel the server last reported.
		self._server = 0
		self._channel = 0
		self._users = {}
		self._total = None
		self._states = {}
		self._channel_rows = []
		nui.Window.__init__(self)
		# The last focused field takes the virtual keyboard's keys.
		for element_id in (ID_FIELD, PASSWORD_FIELD, PASSWORD_SHOWN) + REG_FIELDS:
			self.element_on(element_id, "focus", self._on_field_focus)
		self.reload_accounts()

	def initial_model(self):
		return {"server": "@ui.LOGIN_DEFAULT_SERVERADDR", "user": "", "error": "", "error_on": "", "error_ok": False,
		        "keyboard": False,
		        "tab": "login", "accounts": [], "remember": True, "show_password": False,
		        "can_register": _can_register(), "server_name": "", "server_state": "unknown", "online": "",
		        "channel_text": "", "menu_open": False, "servers": [], "channels": [], "auto": True,
		        "reg_error": "", "reg_error_on": "", "rules": False,
		        "has_discord": bool(nui_links.address("discord")), "has_website": bool(nui_links.address("website")),
		        "has_rules": bool(nui_links.address("rules")), "has_forgot": bool(nui_links.address("forgot"))}

	def _on_field_focus(self, event):
		target = event.get("target_id")
		if target in (ID_FIELD, PASSWORD_FIELD, PASSWORD_SHOWN) + REG_FIELDS:
			self._active_field = target

	def _password_field(self):
		"""The password field in use: the text one while the eye is on."""
		return PASSWORD_SHOWN if self.get("show_password") else PASSWORD_FIELD

	# --- saved accounts ---------------------------------------------------------

	def reload_accounts(self):
		"""The saved accounts from nui_accounts, the selected one the account
		in the name field."""
		now = int(time.time())
		strings = {"now": _text("NUI_LOGIN_NOW"), "minutes": _text("NUI_LOGIN_MINUTES"),
		           "hours": _text("NUI_LOGIN_HOURS"), "yesterday": _text("NUI_LOGIN_YESTERDAY"),
		           "days": _text("NUI_LOGIN_DAYS")}
		rows = []
		for account in nui_accounts.accounts():
			played = account["played"]
			last = None
			for character in account["characters"]:
				if character["name"] == played:
					last = character
			sub = _text("NUI_LOGIN_LAST_PLAYED") % (played, nui_accounts.since(now - account["time"], strings)) \
				if played else ""
			rows.append({"name": nui.plain_text(account["login"]), "sub": nui.plain_text(sub),
			             "face": nui_accounts.face_of(last["race"]) if last else "",
			             "selected": account["login"] == self._user,
			             "chars": [{"face": nui_accounts.face_of(c["race"]), "lv": str(c["level"]),
			                        "last": c["name"] == played} for c in account["characters"]]})
		self.set(accounts=rows, remember=nui_accounts.setting("remember", "1") != "0")

	def _select_account(self, login):
		accounts = self.get("accounts") or []
		for row in accounts:
			row["selected"] = row["name"] == login
		self.set(accounts=accounts)

	@nui.on("pick_account")
	def on_pick_account(self, name, button):
		if button != 0:
			return
		name = _as_text(name)
		if not any(account["login"] == name for account in nui_accounts.accounts()):
			return  # its cross forgot it in the same press
		self.set_user(name)
		self._select_account(name)
		self.set(tab="login", error="", error_on="")
		self.focus(self._password_field())

	@nui.on("forget_account")
	def on_forget_account(self, name, button):
		if button != 0:
			return
		nui_accounts.forget(_as_text(name))
		self.reload_accounts()

	@nui.on("add_account")
	def on_add_account(self, button):
		if button != 0:
			return
		self.set_user("")
		self._select_account(None)
		self.set(tab="login", error="", error_on="")
		self.focus(ID_FIELD)

	@nui.on("remember_press")
	def on_remember_press(self, button):
		if button != 0:
			return
		remember = not self.get("remember")
		nui_accounts.set_setting("remember", "1" if remember else "0")
		self.set(remember=remember)

	# --- the card ---------------------------------------------------------------

	@nui.on("tab_press")
	def on_tab_press(self, tab, button):
		if button != 0 or tab not in ("login", "register") or (tab == "register" and not self.get("can_register")):
			return
		self.set(tab=tab, menu_open=False)
		self.focus(ID_FIELD if tab == "login" else "reg-user")

	@nui.on("eye_press")
	def on_eye_press(self, button):
		"""Shows or hides the password: the other field takes its text (never
		through the model) and the focus."""
		if button != 0:
			return
		show = not self.get("show_password")
		target = PASSWORD_SHOWN if show else PASSWORD_FIELD
		self.set_value(target, self._password, even_hidden=True)
		self.set(show_password=show)
		self.focus(target)

	@nui.on("link_press")
	def on_link_press(self, name, button):
		if button == 0:
			nui_links.open_link(_as_text(name))

	# change fires on every edit, with linebreak on Enter. A binding that sets
	# the value can fire it too, so these only store what they get.

	@nui.on("user_edit")
	def on_user_edit(self, value, linebreak):
		self._user = _as_text(value)
		if self.get("error_on") == "user" or self.get("error_ok"):
			self.set(error="", error_on="", error_ok=False)
		if linebreak:
			self.focus(self._password_field())  # legacy: Enter in the ID line

	@nui.on("password_edit")
	def on_password_edit(self, value, linebreak):
		self._password = _as_text(value)
		if self.get("error_on") == "password" or self.get("error_ok"):
			self.set(error="", error_on="", error_ok=False)
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
			self.focus(self._password_field())
			return
		self.set(error="", error_on="", error_ok=False, menu_open=False)
		# The password stays in the field, as legacy kept it in its EditLine,
		# so a retry needs only Enter.
		login = getattr(self._owner, "NuiLogin", None)
		if login is None or not self._server:
			self._owner.Connect(user, password)  # an intrologin.py without the one-page login
			return
		channel = self._channel or self.auto_channel()
		nui_accounts.remember_login(user, self._server, self.get("remember"))
		nui_accounts.set_setting("last_channel", channel)
		login(user, password, self._server, channel)

	# --- the server and channel -------------------------------------------------

	def set_servers(self, servers, server, channel):
		"""servers: (id, name) in the legacy list's order; server the chosen
		one; channel the chosen channel id or 0 for Auto."""
		self._server = server
		self._channel = channel
		self.set(servers=[{"id": sid, "name": nui.plain_text(name), "selected": sid == server} for sid, name in servers],
		         auto=channel == 0)

	def set_channels(self, channels):
		"""channels: (id, name, legacy state text) of the chosen server's
		channels. Refreshes the status well and the menu."""
		self._channel_rows = list(channels)
		self._states = dict((cid, _state_of(state)) for cid, name, state in channels)
		names = dict((cid, name) for cid, name, state in channels)
		self.set(channels=[{"id": cid, "name": nui.plain_text(name), "state": self._states[cid],
		                    "selected": cid == self._channel} for cid, name, state in channels])
		states = set(self._states.values())
		for state in ("ok", "busy", "full", "down"):
			if state in states:
				break
		else:
			state = "unknown"
		if state == "down" and "unknown" in states:
			state = "unknown"
		chosen = names.get(self._channel) if self._channel else _text("NUI_LOGIN_AUTO")
		self.set(server_state=state, channel_text=nui.plain_text(_text("NUI_LOGIN_CHANNEL") % (chosen or "")))

	def set_server_name(self, name):
		self.set(server_name=nui.plain_text(name))

	def set_online(self, total, users):
		"""The server's players: total, and users per channel id. None for
		total when unknown."""
		self._total = total
		self._users = dict(users)
		self.set(online="" if total is None else nui.plain_text(_text("NUI_LOGIN_PLAYERS") % _grouped(total)))

	def auto_channel(self):
		last = int(nui_accounts.setting("last_channel", "0") or 0)
		return pick_channel(self._states, self._users, last)

	@nui.on("menu_press")
	def on_menu_press(self, button):
		if button == 0:
			self.set(menu_open=not self.get("menu_open"))

	@nui.on("server_press")
	def on_server_press(self, server, button):
		if button != 0:
			return
		choose = getattr(self._owner, "NuiChooseServer", None)
		if choose is not None:
			choose(int(server))

	@nui.on("channel_press")
	def on_channel_press(self, channel, button):
		if button != 0:
			return
		channel = int(channel)
		if channel and self._states.get(channel) == "full":
			return
		self._channel = channel
		nui_accounts.set_setting("channel", channel or "auto")
		self.set(auto=channel == 0, menu_open=False)
		self.set_channels(self._channel_rows)

	# --- Create account ---------------------------------------------------------

	@nui.on("reg_edit")
	def on_reg_edit(self, field, value, linebreak):
		field = _as_text(field)
		if field not in self._reg:
			return
		self._reg[field] = _as_text(value)
		if self.get("reg_error_on") == field:
			self.set(reg_error="", reg_error_on="")
		if linebreak:
			order = ("user", "email", "password", "confirm", "code")
			index = order.index(field)
			if index + 1 < len(order):
				self.focus(REG_FIELDS[index + 1])
			else:
				self._create()

	@nui.on("rules_press")
	def on_rules_press(self, button):
		if button != 0:
			return
		self.set(rules=not self.get("rules"))
		if self.get("reg_error_on") == "rules":
			self.set(reg_error="", reg_error_on="")

	@nui.on("create")
	def on_create(self):
		self._create()

	def _create(self):
		if not self.is_visible() or not self.get("can_register"):
			return
		reg = self._reg
		broken = check_registration(reg["user"], reg["email"], reg["password"], reg["confirm"], reg["code"],
		                            self.get("rules"))
		if broken is not None:
			self.show_create_error(*broken)
			return
		self.set(reg_error="", reg_error_on="")
		create = getattr(self._owner, "NuiCreateAccount", None)
		if create is not None:
			create(reg["user"].strip().lower(), reg["password"], reg["email"].strip(), reg["code"], self._server)

	def show_create_error(self, field, error):
		self.set(reg_error=error, reg_error_on=field)
		focus = dict(zip(("user", "email", "password", "confirm", "code"), REG_FIELDS)).get(field)
		if focus:
			self.focus(focus)

	def account_created(self, code):
		"""GC::ACCOUNT_CREATE_RESULT: OK switches to Log in with the new name,
		anything else shows its error on the Create account tab."""
		if code == ACCOUNT_CREATE_OK:
			login = self._reg["user"].strip().lower()
			self._reg.update(password="", confirm="")
			self.set_user(login)
			self._select_account(login)
			self.set(tab="login", error="@ui.NUI_LOGIN_CREATED", error_on="", error_ok=True)
			self._pending_focus = self._password_field()
			return
		self.set(tab="register")
		self.show_create_error(*CREATE_RESULTS.get(code, ("", "@ui.NUI_LOGIN_ERR_FAILED")))

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
		if self.before_show is not None:
			self.before_show()
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
			self._pending_focus = self._password_field() if self._user else ID_FIELD
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

	def type_text(self, text):
		"""The virtual keyboard: types `text` into the last focused field, as
		keys would ("\b" Backspace, "\n" Enter). True when it typed."""
		if not self.is_visible():
			return False
		return self.insert_text(self._active_field, text)

	def on_reload(self):
		# A locale change or hot reload re-loaded the document: its ID field
		# starts from the model and its password field empty.
		self.set(user=self._user, show_password=False)
		self._password = ""
		self._reg.update(password="", confirm="")
		self.reload_accounts()
		if self.is_visible():
			self.focus(self._password_field() if self._user else ID_FIELD)


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


def _keyboard(win):
	return getattr(win, "nuiKeyboard", None)


def _open_keyboard(win, board):
	"""The NovaUI virtual keyboard, when its flag allows it; its decision is
	recorded either way. Optional: when it cannot be made, the board runs
	without it (and without the legacy keyboard, which types into the legacy
	IME only)."""
	if not nui_windows.use(KEYBOARD_ID)[0]:
		return
	try:
		keyboard = nui_virtual_keyboard.VirtualKeyboard(board)
	except Exception as error:
		nui_windows.note_failure(KEYBOARD_ID, "the controller could not be made (%s)" % type(error).__name__)
		return
	if not keyboard._doc:
		keyboard.destroy()
		nui_windows.note_failure(KEYBOARD_ID, "the document did not load")
		return
	win.nuiKeyboard = keyboard
	board.set(keyboard=True)
	owner = weakref.ref(win)
	board.before_show = lambda: _show_keyboard(owner())


def _show_keyboard(win):
	"""Right before the board shows: the keyboard under it, above the
	ambience. The keyboard never takes the focus, so a show does not raise
	it, and RmlUi stacks the documents nothing raised in load order: the
	ambience, made after it, would draw its embers over the keys. A visible
	one is left alone."""
	keyboard = _keyboard(win) if win is not None else None
	if keyboard is not None and not keyboard.is_visible():
		keyboard.show()
		keyboard.bring_to_front()


def _hide_keyboard(win):
	keyboard = _keyboard(win)
	if keyboard is not None and keyboard.is_visible():
		keyboard.hide()


def _close_keyboard(win):
	keyboard = _keyboard(win)
	if keyboard is None:
		return
	win.nuiKeyboard = None
	keyboard.destroy()


def _refuse_keyboard():
	"""The legacy login board runs: a keyboard asked for cannot come."""
	if nui_windows.use(KEYBOARD_ID)[0]:
		nui_windows.refuse(KEYBOARD_ID, "needs the NovaUI login board")


def place_picker(win):
	"""The picker below the NovaUI locale strip when there is one (else where
	its sheet puts it, under the legacy strip), kept clear of the login
	board, the server board and the keyboard: its sheet hides it while it
	overlaps one of them that is shown. Called when the picker, the server
	board or the strip is made."""
	picker = _picker(win)
	if picker is None:
		return
	strip = _strip(win)
	if strip is not None:
		picker.place_next_to(strip, "below", 4)
	else:
		picker.clear_placement()
	board = _board(win)
	targets = [(board, element_id) for element_id in ("login-card", "login-accounts")] if board is not None else []
	targets += [window for window in (getattr(win, "nuiServerBoard", None), _keyboard(win)) if window is not None]
	picker.keep_clear_of(*targets)
	_raise_strip(win)


def _strip(win):
	"""The NovaUI locale strip's window, or None."""
	strip = getattr(getattr(win, "localeSelector", None), "nui_window", None)
	return strip if strip is not None and getattr(strip, "_doc", 0) else None


def _raise_strip(win):
	"""The strip's flag hints open below it, over the picker: the strip goes
	above the picker after every show of the picker (a show raises it while
	a field has the focus). They never overlap otherwise."""
	strip = _strip(win)
	if strip is not None:
		strip.bring_to_front()


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
	place_picker(win)
	picker.show()
	_raise_strip(win)


def _show_picker(win):
	"""After a popup: back, as the ambience. A visible one is left alone."""
	picker = _picker(win)
	if picker is not None and not picker.is_visible():
		picker.show()
		_raise_strip(win)


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
		_refuse_keyboard()
		return None
	try:
		board = LoginBoard(win, on_choose, on_exit)
	except Exception as error:
		LAST_DECISION = "legacy: the board could not be made"
		nui_windows.note_failure(WINDOW_ID, "the controller could not be made (%s)" % type(error).__name__)
		_refuse_keyboard()
		return None
	if not board._doc:
		board.destroy()
		LAST_DECISION = "legacy: the document did not load"
		nui_windows.note_failure(WINDOW_ID, "the document did not load")
		_refuse_keyboard()
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
	win.nuiBoard = board  # for place_picker; the caller stores it as well
	_open_keyboard(win, board)
	_open_ambient(win)
	_open_picker(win)
	LAST_DECISION = "nui"
	return board


def close_board(win):
	"""LoginWindow.Close, first: the popup callbacks Close runs find no board."""
	_close_ambient(win)
	_close_picker(win)
	_close_keyboard(win)
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
	_hide_keyboard(win)
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
		_hide_keyboard(win)
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
	board.focus_field(ID_FIELD if which == "user" else board._password_field())
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


# --- the one-page login: servers, channels, counts, registration ---------------

def is_one_page(win):
	"""True when the NovaUI login screen runs: the server and channel are
	chosen on its card, so LoginWindow skips its server board step."""
	return _board(win) is not None


def saved_server():
	"""The server id the screen used last (nui_accounts), 0 when none."""
	try:
		return int(nui_accounts.setting("server", "0") or 0)
	except ValueError:
		return 0


def saved_channel():
	"""The channel choice the screen saved: a channel id, or 0 for Auto."""
	value = nui_accounts.setting("channel", "auto")
	return int(value) if value.isdigit() else 0


def show_servers(win, servers, server):
	"""LoginWindow after a server is selected: servers as (id, name) in the
	legacy list's order, server the selected one (saved for the next
	start)."""
	board = _board(win)
	if board is None:
		return
	nui_accounts.set_setting("server", server)
	board.set_servers(servers, server, saved_channel())
	board.set_online(None, {})


def show_channels(win, server_name, channels):
	"""End of LoginWindow.__RefreshServerStateList: the selected server's
	name and channels as (id, name, legacy state text)."""
	board = _board(win)
	if board is None:
		return
	board.set_server_name(server_name)
	board.set_channels(channels)


def show_online(win, total, users):
	"""LoginWindow.NotifyServerStatus (GC::SERVER_STATUS): total players and
	users as (channel id, players) pairs."""
	board = _board(win)
	if board is not None:
		board.set_online(int(total), dict((int(cid), int(count)) for cid, count in users))


def show_create_result(win, code):
	"""LoginWindow.OnAccountCreateResult (GC::ACCOUNT_CREATE_RESULT)."""
	board = _board(win)
	if board is not None:
		board.account_created(int(code))
