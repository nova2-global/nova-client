"""The options' search index (NOVA-213): one table of every row of the
NovaUI game options and system options, which their search fields read.

OLD kept a keyword list on each entry of its data-driven options window
(settingsData.py) and listed the matches under a search field
(uiGameOption.py:94-234). NEW keeps legacy's two windows, so each entry
names its window and the row it highlights:

- OPTIONS: (id, window, label key, English label, English keywords, where
  key). `id` is the row's class suffix in the window's document
  (`go-row--<id>` in game-options.rml, `so-row--<id>` in system-options.rml,
  hyphens as underscores), so a test checks that every row has an entry and
  every entry a row: a new row without an entry fails the suite. `where` is
  the section shown beside the label in a result (a locale key, or None).
- The label in the player's locale (uiScriptLocale) and in English, the
  English keywords and the locale's own keywords
  (uiScriptLocale.OPTION_KEYWORDS_<ID>, words split by spaces) are searched.
  A missing locale string reads as its English text.
- search(text, window): every word of the text must appear in one of them
  (case folded); labels that start with the text come first, then labels
  that hold it, then keyword matches, each in the table's order; at most
  MAX_RESULTS.

The decisions that wait for Eddy are here as data: each window searches its
own rows (WINDOWS), the key bindings are found as the Keyboard row (not each
action), and FOUND_SECONDS is how long a found row stays highlighted."""

GAME = "game"
SYSTEM = "system"
WINDOWS = (GAME, SYSTEM)

MAX_RESULTS = 30
# How long the row a result opens stays highlighted (a nui-countdown timer).
FOUND_SECONDS = 2.0
# The locale's own keywords for an option: OPTION_KEYWORDS_<ID upper>.
KEYWORDS_KEY = "OPTION_KEYWORDS_%s"


class Option(object):
	__slots__ = ("id", "window", "label", "english", "keywords", "where")

	def __init__(self, id, window, label, english, keywords, where=None):
		self.id = id
		self.window = window
		self.label = label
		self.english = english
		self.keywords = tuple(keywords.split())
		self.where = where


OPTIONS = (
	# The game options, in the document's order (uigameoption.py's rows).
	Option("name_color", GAME, "OPTION_NAME_COLOR", "Name Color", "name color colour empire kingdom"),
	Option("target_board", GAME, "OPTION_TARGET_BOARD", "Target Menu", "target board menu enemy empire"),
	Option("pk", GAME, "OPTION_PVPMODE", "PvP Mode", "pvp pk peace hostile revenge guild free fight"),
	Option("block", GAME, "OPTION_BLOCK", "Block", "block trade exchange party group guild whisper friend request"),
	Option("view_chat", GAME, "OPTION_VIEW_CHAT", "Chat Line", "chat bubble talk speech line"),
	Option("always_name", GAME, "OPTION_ALWAYS_SHOW_NAME", "Name", "name always limited show"),
	Option("damage", GAME, "OPTION_EFFECT", "Hit Info", "damage hit numbers effect"),
	Option("sales", GAME, "OPTION_SALESTEXT", "Shop name", "shop name sign private store sales"),
	Option("pickup", GAME, "OPTION_PICKUP_FILTER", "Pickup Filter",
	       "pickup pick loot filter items equipment special potions others"),
	Option("shops", GAME, "OPTION_SHOW_COMPANIONS_SHOPS", "Shops", "offline shop shops hide npc"),
	Option("sash", GAME, "OPTION_ACCE", "Shoulder Sash", "sash shoulder acce costume"),
	Option("buffi", GAME, "OPTION_SHOW_COMPANIONS_BUFFI", "Buffi", "buffi buff companion support shaman"),
	Option("mob_level", GAME, "OPTION_MOB_INFO_LEVEL", "Level", "monster mob level info", "OPTION_MOB_INFO"),
	Option("mob_ai", GAME, "OPTION_MOB_INFO_AGGR", "Aggressive", "monster mob aggressive star ai info",
	       "OPTION_MOB_INFO"),
	Option("keys", GAME, "KEYBIND_ROW", "Keyboard", "key keys keyboard bind binding hotkey shortcut"),
	Option("new_item", GAME, "OPTION_NEW_ITEM_HIGHLIGHT", "New items", "new item items glow highlight mark received loot"),
	Option("yang", GAME, "OPTION_YANG_TEXT", "Yang Log", "yang gold money pickup chat message log"),
	Option("flags", GAME, "OPTION_COUNTRY_FLAGS", "Country Flags", "flag flags country nation language name"),
	# The system options: legacy's rows, then the Interface section.
	Option("sound", SYSTEM, "OPTION_SOUND", "Sound Effects", "sound effects volume audio sfx"),
	Option("music", SYSTEM, "OPTION_MUSIC", "Music", "music volume audio bgm"),
	Option("bgm", SYSTEM, "OPTION_BGM", "Background Music", "music background bgm song track change"),
	Option("camera", SYSTEM, "OPTION_CAMERA_DISTANCE", "Camera", "camera zoom distance far close view"),
	Option("fog", SYSTEM, "OPTION_FOG", "Fog", "fog view distance dense light"),
	Option("tiling", SYSTEM, "OPTION_TILING", "Graphic", "graphic graphics tiling cpu gpu"),
	Option("fov", SYSTEM, "OPTION_FIELD_OF_VIEW", "Field of View", "field view fov angle camera"),
	Option("snow", SYSTEM, "OPTION_SNOWFALL", "Snowfall", "snow snowfall weather christmas xmas"),
	Option("fps", SYSTEM, "OPTION_FPS_COUNTER", "FPS Counter", "fps frames counter performance"),
	Option("tips", SYSTEM, "OPTION_TIPS", "Tips", "tips tip hint help notice"),
	Option("theme", SYSTEM, "THEME_TITLE", "Theme", "theme skin look style dark light classic cyberpunk",
	       "OPTION_INTERFACE"),
	Option("scale", SYSTEM, "OPTION_UI_SCALE", "Scale", "scale size zoom interface ui", "OPTION_INTERFACE"),
	Option("motion", SYSTEM, "OPTION_UI_REDUCED_MOTION", "Reduced motion", "motion animation reduced",
	       "OPTION_INTERFACE"),
	Option("effects", SYSTEM, "OPTION_UI_REDUCED_EFFECTS", "Reduced effects", "effects blur shadow reduced",
	       "OPTION_INTERFACE"),
	Option("colors", SYSTEM, "OPTION_UI_COLORS", "Colors", "colors colour accent panel opacity highlight",
	       "OPTION_INTERFACE"),
)
OPTION = dict((o.id, o) for o in OPTIONS)


def _locale(name, english=None):
	"""uiScriptLocale.<name>, or `english` when the client has none (a
	stand-in that answers a name with itself has none either)."""
	try:
		import uiScriptLocale
	except ImportError:
		return english
	value = getattr(uiScriptLocale, name, None)
	if not isinstance(value, str) or not value or value == name:
		return english
	return value


def label(option):
	"""The option's label in the player's locale."""
	return _locale(option.label, option.english)


def where(option):
	"""The section a result names beside its label, or ""."""
	if not option.where:
		return ""
	return _locale(option.where, "") or ""


def locale_keywords(option):
	return tuple((_locale(KEYWORDS_KEY % option.id.upper(), "") or "").split())


def _fold(text):
	return (text or "").casefold()


def options(window, available=None):
	"""The window's entries in the table's order; `available` (ids) leaves
	out rows the window does not show now (the colors in classic)."""
	return [o for o in OPTIONS if o.window == window and (available is None or o.id in available)]


def search(text, window, available=None):
	"""The entries whose labels or keywords hold every word of `text`,
	best first; [] for a text of no words."""
	words = _fold(text).split()
	if not words:
		return []
	query = " ".join(words)
	ranked = []
	for (order, option) in enumerate(options(window, available)):
		labels = [_fold(label(option)), _fold(option.english)]
		haystack = labels + [_fold(w) for w in option.keywords + locale_keywords(option)] + [_fold(where(option))]
		if not all(any(word in hay for hay in haystack) for word in words):
			continue
		if any(name.startswith(query) for name in labels):
			rank = 0
		elif any(query in name for name in labels):
			rank = 1
		else:
			rank = 2
		ranked.append((rank, order, option))
	ranked.sort(key=lambda entry: (entry[0], entry[1]))
	return [option for (rank, order, option) in ranked[:MAX_RESULTS]]


def result_rows(text, window, plain, available=None):
	"""The model's rows of a search: {"id", "label", "where"}, the texts
	passed through `plain` (nui.plain_text)."""
	return [{"id": o.id, "label": plain(label(o)), "where": plain(where(o))}
	        for o in search(text, window, available)]
