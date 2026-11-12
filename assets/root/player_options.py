"""Snowfall, the FPS counter and tips (NOVA-118): what both system option
windows, game.py and both minimaps share.

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
