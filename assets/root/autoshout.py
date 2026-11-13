"""The auto-shout's client half (NOVA-204; OLD uiChat.py:1571-1840).

The server owns the repeat (a crafted client can never shout faster):
"/auto_shout on <text>" stores the text and starts its repeat, one interval
after the start; "/auto_shout off" stops it; after every change and every
repeat the server sends the chat command "AutoShoutState <0|1> <seconds>"
(the interval in force, 30 or 16 for premium; 0 when off), which the game
window's server command table hands to Interface.AutoShoutState, which calls
server_state() here. Every repeat goes through the server's shout filters.

The client keeps:
- the switch (is_on), the player's intent, and whether the server confirmed
  it (is_confirmed);
- each character's message (message()): the last shout the player sent
  (remember_shout, from the chat's send path) or the text the window started
  with, saved in config/auto_shout.txt as "<character>\t<message>" lines, so
  the window opens prefilled after a restart;
- the countdown to the next repeat (seconds_left, next_in): from the last
  state message, then on by the interval if no new one came;
- the lifetime (on_phase, from networkModule at each phase change): a warp
  (a new game phase on the same character and channel) sends "on <text>"
  again once, since the server ends the repeat with the character; a channel
  change, a return to the character select, a new login and another
  character switch it off. A new client process starts off with the saved
  message ready (default, Eddy to confirm). The server's own stop (its "0")
  switches it off.

The windows (uiautoshout.py, nui_auto_shout.py) listen() for changes and get
OnAutoShoutChanged(); they are held weakly."""

import weakref

import app
import chat
import localeInfo
import net
import player

PATH = "config/auto_shout.txt"
FILE_HEADER = "# NOVA-204: each character's auto-shout message (<character>\\t<message>)"
COMMAND_ON = "/auto_shout on "
COMMAND_OFF = "/auto_shout off"
# The chat packet's text is at most CHAT_MAX_LEN (512) bytes with its end; the
# command takes its prefix of that. The server cuts the text to a shout's length.
MESSAGE_MAX_BYTES = 511 - len(COMMAND_ON)
# The phase windows that keep the switch as it is: the loading between two game
# phases (a warp, a channel change). Every other phase but the game's switches it off.
KEEP_PHASES = ("LoadingWindow",)
GAME_PHASE = "GameWindow"


def _disk_open(path, mode="r"):
	"""The file on disk: the client's open() (system.py) answers a name the
	asset store also has with a pack file."""
	import builtins
	return getattr(builtins, "old_open", open)(path, mode)


OPENER = _disk_open

_state = {
	"on": False,           # the switch
	"confirmed": False,    # the server's last state was 1
	"interval": 0,         # seconds, from the server
	"next_at": 0.0,        # app.GetTime() of the next repeat
	"character": "",       # the character the switch was armed for
	"channel": 0,          # and its channel
}
_messages = None           # {character: message}, read at the first use
_listeners = []            # weak references to the windows


# --- the messages ----------------------------------------------------------------------

def _clean(text):
	text = "" if text is None else str(text)
	for mark in ("\t", "\r\n", "\n", "\r"):
		text = text.replace(mark, " ")
	text = text.strip()
	data = text.encode("utf-8")
	if len(data) > MESSAGE_MAX_BYTES:
		text = data[:MESSAGE_MAX_BYTES].decode("utf-8", "ignore")
	return text


def _load():
	global _messages
	if _messages is not None:
		return _messages
	_messages = {}
	try:
		with OPENER(PATH, "r") as handle:
			text = handle.read()
	except Exception:
		return _messages
	for line in text.split("\n"):
		line = line.rstrip("\r")
		if not line or line.startswith("#") or "\t" not in line:
			continue
		name, message = line.split("\t", 1)
		if name and message:
			_messages[name] = message
	return _messages


def _save():
	lines = [FILE_HEADER] + ["%s\t%s" % (name, message) for name, message in sorted(_load().items())]
	try:
		with OPENER(PATH, "w") as handle:
			handle.write("\n".join(lines) + "\n")
		return True
	except Exception:
		return False


def _character():
	return str(player.GetName() or "")


def message():
	"""The current character's message, or ""."""
	return _load().get(_character(), "")


def set_message(text):
	"""The current character's message, saved; an empty text changes nothing."""
	text = _clean(text)
	name = _character()
	if not text or not name:
		return False
	messages = _load()
	if messages.get(name) != text:
		messages[name] = text
		_save()
	return True


def remember_shout(text):
	"""A shout the player sent (the chat's send path): the character's message."""
	return set_message(text)


# --- the switch ---------------------------------------------------------------------------

def is_on():
	return bool(_state["on"])


def is_confirmed():
	return bool(_state["on"] and _state["confirmed"])


def interval():
	return int(_state["interval"])


def seconds_left():
	"""Seconds to the next repeat while the server confirmed it, else 0. Past
	the expected repeat with no new state, the count goes on by the interval."""
	if not is_confirmed():
		return 0
	now = app.GetTime()
	next_at = _state["next_at"]
	step = _state["interval"]
	if step > 0 and next_at < now:
		next_at += step * (int((now - next_at) // step) + 1)
		_state["next_at"] = next_at
	return max(0.0, next_at - now)


def _arm():
	_state["character"] = _character()
	_state["channel"] = int(net.GetChannelNum() or 0)


def _send_on(text):
	net.SendChatPacket(COMMAND_ON + text)


def start(text):
	"""Start with `text` (the window's field): saved as the message, then
	"/auto_shout on <text>". Without a text, the player is told and nothing
	is sent."""
	text = _clean(text)
	if not text:
		chat.AppendChat(chat.CHAT_TYPE_INFO, localeInfo.AUTO_SHOUT_NO_MESSAGE)
		return False
	set_message(text)
	_state["on"] = True
	_state["confirmed"] = False
	_arm()
	_send_on(text)
	_notify()
	return True


def stop():
	_state["on"] = False
	_state["confirmed"] = False
	net.SendChatPacket(COMMAND_OFF)
	_notify()


def server_state(on, seconds):
	"""AutoShoutState <0|1> <seconds>: the countdown starts again from now; a
	0 (the server stopped, or refused the start) switches it off."""
	try:
		on, seconds = int(on), int(seconds)
	except (TypeError, ValueError):
		return
	if on:
		_state["on"] = True
		_state["confirmed"] = True
		_state["interval"] = max(0, seconds)
		_state["next_at"] = app.GetTime() + max(0, seconds)
		_arm()
	else:
		_state["on"] = False
		_state["confirmed"] = False
		_state["interval"] = 0
	_notify()


def _switch_off():
	if _state["on"] or _state["confirmed"]:
		_state["on"] = False
		_state["confirmed"] = False
		_notify()


def on_phase(window):
	"""networkModule's phase change, after the new phase window opened."""
	kind = type(window).__name__
	if kind in KEEP_PHASES:
		return
	if kind != GAME_PHASE or not _state["on"]:
		_switch_off()
		return
	channel = int(net.GetChannelNum() or 0)
	text = message()
	if _character() != _state["character"] or channel != _state["channel"] or not text:
		_switch_off()
		return
	# A warp: the new core knows nothing of the repeat; its state message
	# confirms it again.
	_state["confirmed"] = False
	_send_on(text)
	_notify()


# --- the windows ------------------------------------------------------------------------

def listen(window):
	if not any(ref() is window for ref in _listeners):
		_listeners.append(weakref.ref(window))


def forget(window):
	_listeners[:] = [ref for ref in _listeners if ref() is not None and ref() is not window]


def _notify():
	for ref in list(_listeners):
		window = ref()
		if window is None:
			_listeners.remove(ref)
			continue
		changed = getattr(window, "OnAutoShoutChanged", None)
		if changed is not None:
			changed()
