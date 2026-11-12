"""Snowfall, the FPS counter and tips (NOVA-118): what both system option
windows, game.py and both minimaps share. The frame rate limit (NOVA-214)
has its own block at the end.

OLD kept snowfall in CPythonSystem (SNOW_MODE_ON) and the other two in its
cfg module ("fps_counter", "disable_tip"); NEW keeps all three in
CPythonSystem (config/metin2.cfg, saved at exit with the other options):
systemSetting.IsEnableSnowFall, IsShowFPSCounter and IsShowTips. Their
defaults are CPythonSystem's SNOWFALL_DEFAULT, FPS_COUNTER_DEFAULT and
TIPS_DEFAULT (OLD's: snow off, counter off, tips on).

The option windows set a flag through set_option(), which tells every
listener: game.py (the snowfall follows the xmas event, the map and the
player's choice; tips stop while off) and the minimap, legacy or NovaUI
(the readout under it). A listener is kept weakly and gets
OnPlayerOptionChanged(name)."""

import weakref

import systemSetting

SNOWFALL = "snowfall"
FPS_COUNTER = "fps_counter"
TIPS = "tips"

# The readout: OLD's text (game.py:2395, "FPS:%s "), spaced, and how often it
# reads app.GetRenderFPS(), which the client counts once a second.
FPS_TEXT = "FPS: %d"
FPS_INTERVAL = 1.0

_GETTERS = {SNOWFALL: "IsEnableSnowFall", FPS_COUNTER: "IsShowFPSCounter", TIPS: "IsShowTips"}
_SETTERS = {SNOWFALL: "SetEnableSnowFall", FPS_COUNTER: "SetShowFPSCounter", TIPS: "SetShowTips"}

_listeners = []   # weak references to the listeners


def is_on(name):
	"""Whether the option is on; an older exe without it reads its default."""
	getter = getattr(systemSetting, _GETTERS[name], None)
	if getter is None:
		return name == TIPS
	return bool(getter())


def set_option(name, on):
	"""Sets the option (1 or 0, OLD's rule) and tells every listener."""
	setter = getattr(systemSetting, _SETTERS[name], None)
	if setter is None:
		return
	setter(1 if on else 0)
	notify(name)


def listen(owner):
	"""Keeps `owner` weakly; it gets OnPlayerOptionChanged(name) after each
	change. Listening twice is listening once."""
	for ref in _listeners:
		if ref() is owner:
			return
	_listeners.append(weakref.ref(owner))


def forget(owner):
	_listeners[:] = [ref for ref in _listeners if ref() is not None and ref() is not owner]


def notify(name):
	_listeners[:] = [ref for ref in _listeners if ref() is not None]
	for ref in list(_listeners):
		owner = ref()
		if owner is not None:
			owner.OnPlayerOptionChanged(name)


def snowfall_wanted(event_on, xmas_map):
	"""The xmas event's snowfall shows only while the event is on, the map
	shows it and the player has not turned it off (OLD game.py:3365)."""
	return bool(event_on) and bool(xmas_map) and is_on(SNOWFALL)


def fps_text(fps):
	return FPS_TEXT % int(fps)


# --- The frame rate limit (NOVA-214) --------------------------------------------
# CPythonSystem's MAX_FPS (config/metin2.cfg, saved at exit with the other
# options; OLD's key): systemSetting.GetMaxFPS() answers 60, 120, 144, 165,
# 240, 0 (unlimited) or -1 (VSync), SetMaxFPS(n) takes one of them, and the
# client applies a change at the next frame. MAX_FPS_CHOICES lists them in
# display order. Both system option windows show the value between a previous
# and a next button and step through the choices without wrapping. An older
# exe has none of this: has_max_fps() is False and the windows show no row.

MAX_FPS_CHOICES = (60, 120, 144, 165, 240, 0, -1)
MAX_FPS_UNLIMITED = 0
MAX_FPS_VSYNC = -1
MAX_FPS_DEFAULT = 60
# The locale_interface keys of the choices that are words, not numbers.
MAX_FPS_LABEL_KEYS = {MAX_FPS_UNLIMITED: "OPTION_FRAME_RATE_UNLIMITED", MAX_FPS_VSYNC: "OPTION_FRAME_RATE_VSYNC"}


def has_max_fps():
	"""Whether the exe has the frame rate limit (NOVA-214)."""
	return getattr(systemSetting, "GetMaxFPS", None) is not None and getattr(systemSetting, "SetMaxFPS", None) is not None


def max_fps_choices():
	"""The choices in display order: the client's, else the documented ones."""
	return tuple(int(value) for value in getattr(systemSetting, "MAX_FPS_CHOICES", MAX_FPS_CHOICES))


def max_fps():
	"""The limit in effect; 60 without the API or for a value that is no
	choice (the client reads such a cfg value as 60 too)."""
	getter = getattr(systemSetting, "GetMaxFPS", None)
	if getter is None:
		return MAX_FPS_DEFAULT
	try:
		value = int(getter())
	except (TypeError, ValueError):
		return MAX_FPS_DEFAULT
	return value if value in max_fps_choices() else MAX_FPS_DEFAULT


def max_fps_label(value, text):
	"""A choice as the row shows it: its number, or the text of its word's
	locale key, text(key) (uiScriptLocale's in legacy, "@ui.KEY" in NovaUI)."""
	key = MAX_FPS_LABEL_KEYS.get(value)
	return text(key) if key else str(int(value))


def max_fps_step(value, step):
	"""The choice `step` places after `value` (before it when negative),
	held at the first and the last; a value that is no choice steps from 60."""
	choices = max_fps_choices()
	index = choices.index(value if value in choices else MAX_FPS_DEFAULT)
	return choices[min(len(choices) - 1, max(0, index + int(step)))]


def set_max_fps(value):
	"""Hands a choice to the client; False (and no call) for anything else or
	an exe without the API."""
	setter = getattr(systemSetting, "SetMaxFPS", None)
	if setter is None or isinstance(value, bool) or not isinstance(value, int) or value not in max_fps_choices():
		return False
	setter(value)
	return True
