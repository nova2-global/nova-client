"""The accounts the NovaUI login screen remembers (nui_login.py).

Saved on this computer, in config/nui_accounts.txt: each account's name, the
server it last played on, when, the character played and the characters the
select screen showed at that log in (name, race, level), with the levels as
of then. The file never holds a password or anything the server did not show
the player. When the client supports it, a remembered password is kept by
Windows Credential Manager. The login screen lists the accounts, most recent
first; a press fills the name, and Forget takes an account and its secret off
this computer.

An account is written when the game starts (networkModule.SetGamePhase calls
note_game_start) and only when the login screen asked to remember it
(remember_login, set at each log in from the Remember me toggle). A pending
password stays in memory until the auth server accepts or refuses the login.
The file also keeps the screen's own choices (the server, the channel or
"auto", the keyboard, and the toggle).

The file is plain text, one record a line, fields split by tabs:
	S	<setting>	<value>
	A	<login>	<server id>	<unix time>	<character played>
	C	<name>	<race>	<level>
each C line belonging to the A line above it. A line that does not parse is
skipped, so a damaged file loses only what it damaged."""

import os
import time

import app

PATH = "config/nui_accounts.txt"
MAX_ACCOUNTS = 5
MAX_CHARACTERS = 5

# The faces of the eight races (playerSettingModule's RACE_*), as the target
# board shows them.
FACES = {0: "/icon/face/warrior_m.tga", 1: "/icon/face/assassin_w.tga", 2: "/icon/face/sura_m.tga",
         3: "/icon/face/shaman_w.tga", 4: "/icon/face/warrior_w.tga", 5: "/icon/face/assassin_m.tga",
         6: "/icon/face/sura_w.tga", 7: "/icon/face/shaman_m.tga"}

# The log in remember_login set, until the game starts or another log in.
_pending = {}


def face_of(race):
	"""The face image of a race, "" for an unknown race."""
	return FACES.get(race, "")


def _clean(text):
	"""A field as the file can hold it: no tab, no line break."""
	return str(text).replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def disk_open(path, mode="r"):
	"""The file on disk itself. The client's open() (system.py) hands back the
	asset store's pack_file for any path the store says exists, and the store
	falls back to the disk, so a config file comes back as a pack_file: a
	copy read once, without close() or a with block. A file the client writes
	and reads again must come through here."""
	import builtins
	return getattr(builtins, "old_open", open)(path, mode)


def _read():
	"""(accounts, settings) from the file; empty when there is none."""
	accounts = []
	settings = {}
	try:
		with disk_open(PATH, "r") as handle:
			lines = handle.readlines()
	except (IOError, OSError):
		return accounts, settings
	current = None
	for line in lines:
		fields = line.rstrip("\r\n").split("\t")
		try:
			if fields[0] == "S" and len(fields) == 3:
				settings[fields[1]] = fields[2]
			elif fields[0] == "A" and len(fields) == 5 and fields[1]:
				current = {"login": fields[1], "server": int(fields[2]), "time": int(fields[3]),
				           "played": fields[4], "characters": []}
				accounts.append(current)
			elif fields[0] == "C" and len(fields) == 4 and current is not None:
				if len(current["characters"]) < MAX_CHARACTERS:
					current["characters"].append({"name": fields[1], "race": int(fields[2]), "level": int(fields[3])})
		except ValueError:
			current = None
	accounts.sort(key=lambda account: -account["time"])
	return accounts[:MAX_ACCOUNTS], settings


def _write(accounts, settings):
	lines = ["# NovaUI saved accounts (nui_accounts.py). No passwords.\n"]
	for key in sorted(settings):
		lines.append("S\t%s\t%s\n" % (_clean(key), _clean(settings[key])))
	for account in accounts[:MAX_ACCOUNTS]:
		lines.append("A\t%s\t%d\t%d\t%s\n" % (_clean(account["login"]), account["server"], account["time"],
		                                       _clean(account["played"])))
		for character in account["characters"][:MAX_CHARACTERS]:
			lines.append("C\t%s\t%d\t%d\n" % (_clean(character["name"]), character["race"], character["level"]))
	try:
		folder = os.path.dirname(PATH)
		if folder and not os.path.exists(folder):
			os.mkdir(folder)
		with disk_open(PATH, "w") as handle:
			handle.write("".join(lines))
		return True
	except (IOError, OSError):
		return False


def _secret_function(name):
	"""One credential function supplied by the executable, or None."""
	function = getattr(app, name, None)
	return function if callable(function) else None


def _secret_key(server, login):
	return "%d/%s" % (int(server), str(login))


def secrets_available():
	"""Whether this executable supplies the complete credential API."""
	return all(_secret_function(name) is not None for name in
	           ("SaveLoginSecret", "LoadLoginSecret", "DeleteLoginSecret"))


def save_secret(server, login, secret):
	"""Saves one password in Windows Credential Manager when available."""
	function = _secret_function("SaveLoginSecret")
	if function is None or not login or not isinstance(secret, str):
		return False
	try:
		return bool(function(_secret_key(server, login), secret))
	except Exception:
		return False


def load_secret(server, login):
	"""Loads one password, or None when unavailable, missing, or refused."""
	function = _secret_function("LoadLoginSecret")
	if function is None or not login:
		return None
	try:
		secret = function(_secret_key(server, login))
	except Exception:
		return None
	return secret if isinstance(secret, str) else None


def forget_secret(server, login):
	"""Deletes one password when the credential API is available."""
	function = _secret_function("DeleteLoginSecret")
	if function is None or not login:
		return False
	try:
		return bool(function(_secret_key(server, login)))
	except Exception:
		return False


def accounts():
	"""The saved accounts, most recent first: dicts of login, server, time
	(unix seconds), played (a character name) and characters (name, race,
	level each)."""
	return _read()[0]


def setting(key, default=""):
	"""One of the login screen's saved choices."""
	return _read()[1].get(key, default)


def set_setting(key, value):
	saved, settings = _read()
	settings[key] = str(value)
	return _write(saved, settings)


def forget(login):
	"""Takes the account and its secret off this computer."""
	saved, settings = _read()
	for account in saved:
		if account["login"] == login:
			forget_secret(account["server"], login)
	kept = [account for account in saved if account["login"] != login]
	if len(kept) == len(saved):
		return False
	_write(kept, settings)
	return True


def remember_login(login, server, remember, secret=""):
	"""Records a login attempt in memory until the auth server answers.

	The password is present only for Remember me and never reaches the account
	file. note_auth_accepted handles the credential, then note_game_start may
	write the account metadata later.
	"""
	_pending.clear()
	if login:
		_pending.update({"login": login, "server": int(server), "remember": bool(remember),
		                 "secret": secret if remember and isinstance(secret, str) else ""})


def note_auth_accepted():
	"""Saves or deletes the pending credential after authentication succeeds."""
	if not _pending:
		return False
	try:
		if _pending.get("remember"):
			return save_secret(_pending["server"], _pending["login"], _pending.get("secret", ""))
		return forget_secret(_pending["server"], _pending["login"])
	finally:
		# The account metadata remains pending until the game starts, but the
		# password does not remain in memory after the auth answer.
		_pending["secret"] = ""


def login_failed():
	"""Drops every pending login value after a refused or failed attempt."""
	_pending.clear()


def note_game_start(login, played, slots):
	"""Writes the account once the game starts: login (the stream's), played
	(the character's name) and slots, the select screen's characters as
	(name, race, level). Nothing when the log in was not to be remembered."""
	if not _pending or _pending.get("login") != login or not _pending.get("remember"):
		_pending.clear()
		return False
	saved, settings = _read()
	saved = [account for account in saved if account["login"] != login]
	characters = [{"name": _clean(name), "race": int(race), "level": int(level)}
	              for name, race, level in slots if name][:MAX_CHARACTERS]
	saved.insert(0, {"login": login, "server": _pending["server"], "time": int(time.time()),
	                 "played": _clean(played), "characters": characters})
	_pending.clear()
	return _write(saved, settings)


def since(seconds, strings):
	"""How long ago, as the login screen words it: strings maps "now",
	"minutes", "hours", "yesterday" and "days" to locale texts, the last
	four with one %d (yesterday with none)."""
	seconds = max(0, int(seconds))
	if seconds < 60:
		return strings["now"]
	if seconds < 3600:
		return strings["minutes"] % (seconds // 60)
	if seconds < 86400:
		return strings["hours"] % (seconds // 3600)
	if seconds < 2 * 86400:
		return strings["yesterday"]
	return strings["days"] % (seconds // 86400)
