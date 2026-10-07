"""Which windows run on NovaUI, and the factory that makes them.

Each window has an id. Its default lives here (every Wave 1, 2a and 2b
window is off: legacy) and config/metin2.cfg overrides it through
UI_NUI_WINDOWS ("+id" on, "-id" off, comma-separated;
systemSetting.GetUINuiWindows). A group id (GROUPS: "wave1", "hud", "hud2")
in that string stands for each of its windows, in its place among the
tokens.
UI_NUI_LOGIN 1 means "+login" unless UI_NUI_WINDOWS names login itself.
A window runs on NovaUI only when its flag is on, NovaUI is available, the
locale is not right-to-left (nui.enabled_for_locale), its document loaded
and its controller was made; otherwise the legacy window runs, unchanged.
Each decision is logged once to log.txt (dbg.Tracen); a failure of a
window that was asked for is also logged once to syserr.txt
(dbg.TraceError). At each phase change, end_phase() unloads the documents
the ended phase shared, so none stays in the frame update of the next."""

import sys

import dbg
import systemSetting

try:
	import nui
except ImportError:  # a client without assets/root/nui.py: every window stays legacy
	class nui(object):
		"""Stands in for the nui module: nothing is available, nothing shown."""

		@staticmethod
		def is_available():
			return False

		@staticmethod
		def enabled_for_locale():
			return False

		@staticmethod
		def any_window_shown():
			return False

try:
	import wndMgr
except ImportError:  # plain Python outside the client
	wndMgr = None


WINDOWS = (            # (id, default) in this order; the defaults stay False in Waves 1, 2a and 2b
	("login", False),
	("dialogs", False),
	("server-board", False),
	("virtual-keyboard", False),
	("locale-strip", False),
	("loading", False),
	("empire", False),
	("select", False),
	("create", False),
	("taskbar", False),            # the taskbar: gauges, quickslots, the mouse-button pickers
	("expanded-taskbar", False),   # the expanded taskbar (the dragon soul button)
	("energy-bar", False),
	("gift-box", False),           # the gift icon; needs the NovaUI taskbar, which makes it
	("game-buttons", False),       # the stat, skill, help, quest, build and observer buttons
	("affects", False),
	("target", False),
	("party", False),
	("edge-buttons", False),       # the quest and whisper edge buttons
	("tip-board", False),
	("big-board", False),
	("map-name", False),
	("chat", False),               # the chat window and its input
	("chat-log", False),           # the chat log
	("minimap", False),            # the minimap: frame, controls and the map view
	("atlas", False),              # the atlas (large map); needs the NovaUI minimap, which makes it
	("player-gauge", False),       # the HP gauge over the player's head
	("shop-signs", False),         # the private shop signs
	("guild-war", False),          # the guild war score boards
)

GROUPS = {             # a group id names several windows in UI_NUI_WINDOWS
	"wave1": ("dialogs", "server-board", "virtual-keyboard", "locale-strip", "loading", "empire", "select", "create"),
	"hud": ("taskbar", "expanded-taskbar", "energy-bar", "gift-box", "game-buttons", "affects", "target", "party",
	        "edge-buttons", "tip-board", "big-board", "map-name"),
	"hud2": ("chat", "chat-log", "minimap", "atlas", "player-gauge", "shop-signs", "guild-war"),
}

DECISIONS = {}         # id -> "nui" or "legacy: <reason>", the last decision

# Modules holding NovaUI documents that no phase window owns (shared between
# windows), each with an end_phase() that unloads them; see end_phase().
PHASE_SCOPED = ("nui_dialog_kit",)

_DEFAULTS = dict(WINDOWS)
_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")
_ID_MAX = 31
_logged = {}           # id -> the decision logged last
_failures = set()      # (id, reason) already written to syserr


def _is_id(window_id):
	return isinstance(window_id, str) and 1 <= len(window_id) <= _ID_MAX and _ID_CHARS.issuperset(window_id)


def _tokens():
	"""[(id, on)] from UI_NUI_WINDOWS in its order, or [] with an exe that has
	no binding. The client normalizes the value; tokens out of form are
	skipped here anyway, so a hand-edited line cannot raise."""
	get = getattr(systemSetting, "GetUINuiWindows", None)
	if get is None:
		return []
	value = get() or ""
	found = []
	for token in value.lower().split(","):
		token = token.strip()
		if len(token) > 1 and token[0] in "+-" and _is_id(token[1:]):
			found.append((token[1:], token[0] == "+"))
	return found


def overrides():
	"""{id: bool} from UI_NUI_WINDOWS, plus the UI_NUI_LOGIN mapping. A group
	token stands for each of its windows in its place ("+hud,-target" is
	every HUD window but the target board; "-target,+hud" has it on), so a
	later token wins per id. A group id itself is no key. Ids this table
	does not know are kept (content from a newer release)."""
	result = {}
	for window_id, on in _tokens():
		for member in GROUPS.get(window_id, (window_id,)):
			result[member] = on
	if "login" not in result:
		is_login = getattr(systemSetting, "IsUINuiLogin", None)
		if is_login is not None and is_login():
			result["login"] = True
	return result


def is_on(window_id):
	"""The flag alone: the override, else the default (False for an id this
	table does not know, and for a group id, which is not a window)."""
	return bool(overrides().get(window_id, _DEFAULTS.get(window_id, False)))


def _record(window_id, decision):
	DECISIONS[window_id] = decision
	if _logged.get(window_id) != decision:
		_logged[window_id] = decision
		dbg.Tracen("nui_windows: %s -> %s" % (window_id, decision))


def use(window_id):
	"""(True, "") when the window should run on NovaUI, else (False, reason)
	with the first check that failed: "flag off", "NovaUI unavailable" or
	"right-to-left locale". Records the decision in DECISIONS and logs it
	when it changed. Whether the document loads and the controller can be
	made is make()'s part."""
	if not is_on(window_id):
		reason = "flag off"
	elif not nui.is_available():
		reason = "NovaUI unavailable"
	elif not nui.enabled_for_locale():
		reason = "right-to-left locale"
	else:
		reason = ""
	_record(window_id, "legacy: " + reason if reason else "nui")
	return not reason, reason


def refuse(window_id, reason):
	"""Records "legacy: <reason>" for a window that use() allowed but that
	cannot run for a reason of its own (the virtual keyboard without the
	NovaUI login board). Logged as use() logs, to log.txt only."""
	_record(window_id, "legacy: " + reason)


def note_failure(window_id, reason):
	"""A window that was asked for falls back: records "legacy: <reason>" and
	writes it to syserr.txt once per (id, reason)."""
	_record(window_id, "legacy: " + reason)
	if (window_id, reason) not in _failures:
		_failures.add((window_id, reason))
		dbg.TraceError("nui_windows: %s: %s; using the legacy window" % (window_id, reason))


def _novaui_class(novaui):
	"""The class itself, or the class a "module.Class" string names, imported
	now (at the first use, never while the flag is off)."""
	if not isinstance(novaui, str):
		return novaui
	module_name, _, class_name = novaui.rpartition(".")
	module = __import__(module_name, fromlist=[class_name])
	return getattr(module, class_name)


def make(window_id, legacy, novaui, *args, **kwargs):
	"""An instance of novaui when use() allows it and the instance is ready,
	else of legacy, made with the same arguments.

	`novaui` is a class or a "module.Class" string. When its module cannot
	be imported or its constructor raises, the legacy class is made, and the
	failure goes to syserr once. An instance with nui_ready() that answers
	False (its document did not load) is discarded (nui_discard()) and
	dropped before the legacy one is made: a legacy phase window clears its
	net slot when it is collected, which must not hit the one made in its
	place."""
	if not use(window_id)[0]:
		return legacy(*args, **kwargs)
	instance = None
	try:
		instance = _novaui_class(novaui)(*args, **kwargs)
		ready = getattr(instance, "nui_ready", None) is None or bool(instance.nui_ready())
	except Exception as error:
		_discard(instance)
		instance = None
		note_failure(window_id, "the controller could not be made (%s)" % type(error).__name__)
		return legacy(*args, **kwargs)
	if ready:
		return instance
	_discard(instance)
	instance = None
	note_failure(window_id, "the document did not load")
	return legacy(*args, **kwargs)


def _discard(instance):
	"""nui_discard() of a NovaUI instance that will not be used; an error there
	must not keep the legacy window from being made."""
	discard = getattr(instance, "nui_discard", None)
	if discard is None:
		return
	try:
		discard()
	except Exception as error:
		dbg.TraceError("nui_windows: nui_discard() failed (%s)" % type(error).__name__)


def factory(window_id, legacy, novaui):
	"""A function that calls make() with these three, named like the legacy
	class, for wiring at class level: `PopupDialog = factory("dialogs",
	LegacyPopupDialog, "nui_dialog_message.PopupDialog")`. It carries
	`legacy` and `window_id`."""
	def make_one(*args, **kwargs):
		return make(window_id, legacy, novaui, *args, **kwargs)

	make_one.__name__ = legacy.__name__
	make_one.legacy = legacy
	make_one.window_id = window_id
	return make_one


def set_override(window_id, on):
	"""Sets the override of one window: True ("+id"), False ("-id") or None
	(removes it, so the default applies). Saves config/metin2.cfg. True when
	the client took the new value; False with an exe that has no binding or
	refuses it. ValueError for an id out of form, and for a group id: the
	override names single windows only (a group token already in the string
	stays, and the new token after it wins)."""
	if not _is_id(window_id) or window_id in GROUPS:
		raise ValueError("nui_windows.set_override(): %r is not a window id" % (window_id,))
	tokens = [(other, value) for other, value in _tokens() if other != window_id]
	if on is not None:
		tokens.append((window_id, bool(on)))
	value = ",".join(("+" if value else "-") + other for other, value in tokens)
	set_value = getattr(systemSetting, "SetUINuiWindows", None)
	if set_value is None or not set_value(value):
		return False
	save = getattr(systemSetting, "SaveConfig", None)
	if save is not None:
		save()
	return True


def end_phase():
	"""networkModule.MainStream calls this when a phase window has closed,
	before the next one opens. RmlUi updates every loaded document each
	frame, shown or not, so nothing the ended phase loaded may stay: a phase
	window's own documents go with its Close, and the documents no phase
	window owns (PHASE_SCOPED: the dialog kit's shared ones) go here. Each
	loads again when the next phase shows it. Only modules already imported
	are asked (a flag that is off imports none). Returns how many documents
	went, and logs that count to log.txt when it is not 0; an error in a
	module goes to syserr.txt and the phase change goes on."""
	count = 0
	for name in PHASE_SCOPED:
		end = getattr(sys.modules.get(name), "end_phase", None)
		if end is None:
			continue
		try:
			count += int(end() or 0)
		except Exception as error:
			dbg.TraceError("nui_windows: %s.end_phase() failed (%s)" % (name, type(error).__name__))
	if count:
		dbg.Tracen("nui_windows: phase ended, %d document(s) unloaded" % count)
	return count


def legacy_dialog_layer(window):
	"""G5 stopgap, called first in the Open of every legacy common dialog: a
	dialog opened while a NovaUI window is shown goes to the TOP_MOST layer,
	which draws above NovaUI and takes the pointer before it; one opened
	while none is shown goes (back) to the UI layer, where it always was. An
	exe without wndMgr.SetWindowLayer changes nothing.

	A dialog that goes to TOP_MOST also covers the NovaUI dialog kit, when
	the kit is in use (nui_dialog_kit.cover): the kit's modals step aside
	until it hides, so the keys reach the dialog the player sees."""
	set_layer = getattr(wndMgr, "SetWindowLayer", None)
	if set_layer is None or not getattr(window, "hWnd", None):
		return
	top = nui.any_window_shown()
	set_layer(window.hWnd, "TOP_MOST" if top else "UI")
	kit = sys.modules.get("nui_dialog_kit")
	if top and kit is not None:
		kit.cover(window)
