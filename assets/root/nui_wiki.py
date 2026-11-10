"""The ingame wiki's item and mob browser on NovaUI (NOVA-42,
nui/windows/wiki/wiki.rml). There is no legacy window: the browser exists only
where NovaUI runs, and Interface.__MakeWindows leaves wndWiki None otherwise.

The window lists items and mobs from the client's protos (item.ListByType,
item.Search, nonplayer.List, nonplayer.Search) and asks the server for a
page's rows (net.SendWikiRequest, answered by BINARY_WikiAnswer: where an item
comes from, a chest's contents, refine costs, a mob's drops). Answers are kept
per vnum for the session. A server that refuses a request for its rate limit
answers WIKI_STATUS_BUSY; the window asks again a moment later, and a request
that is never answered is sent again until TRIES_MAX, when the page says it
could not load instead of sitting empty.

It browses like a web browser (Eddy's notes after r38): back and forward, a
home page with every category's lists and the pages viewed last, a trail
from Home to the page, and up to TABS_MAX tabs, each with its own history. A
middle press, or a left press with Ctrl held, opens a link in a new tab
behind the shown one; a middle press on a tab closes it. The Link button
puts the page's syswiki link (wiki_link) where the player types, through
Interface.PasteWikiLink.

Nothing runs per frame: the search is the field's change event, and the retry
and the give-up are two hidden nui-countdowns (retry_at, timeout_at). The
board exists only while the window shows; the tabs and their histories stay
with the window. NOVA-139's text pages plug in at
nui_wiki_data.TEXT_CATEGORIES; _open_sub dispatches on a row's "kind".
"""

import re

import ui

import nui
import nui_facade
import nui_hud
import nui_slots
import nui_wiki_data as data

DOCUMENT = "nui/windows/wiki/wiki.rml"
KEY = "wiki"
PREVIEW = "wiki"
HOVER_PREVIEW = "wiki_hover"
# The hover preview makes a model only once the pointer has rested on a row
# this long, and not while the wheel turns (modelpreview.SetDwell): a list
# scrolled under a still pointer changes the row every few frames (r39).
HOVER_DWELL_MS = 180

# EWikiKind and EWikiStatus (nova-protocol's wiki_packets.h).
KIND_ITEM, KIND_MOB = 0, 1
STATUS_OK, STATUS_BUSY = 0, 1
FLAG_COMMON = 0x01
# EWikiOriginType.
ORIGIN_MOB, ORIGIN_CHEST, ORIGIN_CRAFT, ORIGIN_SHOP = 0, 1, 2, 3
ORIGIN_LABELS = {
	ORIGIN_MOB: "WIKI_ORIGIN_MOB", ORIGIN_CHEST: "WIKI_ORIGIN_CHEST",
	ORIGIN_CRAFT: "WIKI_ORIGIN_CRAFT", ORIGIN_SHOP: "WIKI_ORIGIN_SHOP",
}

# OLD's WikiLoadClassMobs kinds.
MOBS_BOSS, MOBS_MONSTER, MOBS_METIN = 0, 1, 2
# The level bands of OLD's categories (inGameWikiConfig.py WIKI_CATEGORIES).
BANDS = ((1, 109), (110, 129), (130, 255))

RETRY_SECONDS = 1.0
ANSWER_WAIT_SECONDS = 2.5
TRIES_MAX = 6
LIST_ROWS_MAX = 500
SEARCH_ROWS_MAX = 200
# The tabs, as in a browser (Eddy's r38 notes), the pages the home page lists,
# and the steps a tab remembers.
TABS_MAX = 8
TAB_LABEL_MAX = 16
RECENT_MAX = 8
HISTORY_MAX = 50
SEARCH_FIELD = "wiki-search"
# Takes the focus off the search field before a link is pasted elsewhere
# (the home button, focus: auto in wiki.rcss).
PARK = "wiki-home-button"
# OLD's syswiki link color (its quests' "|~FF00C0FC").
LINK_COLOR = "ff00c0fc"
# A list's link, syswiki:list:<path> (Eddy's r39 notes: link any page). The
# server takes it as free only for a path of 1 to LIST_PATH_MAX characters of
# [a-z0-9_:] (srv input_main.cpp IsWikiHyperlink), so a path is made of the
# tree's ids, "home", or "search:" and the search's UTF-8 bytes in hex.
LIST_PATH_MAX = 64
HOME_PATH = "home"
SEARCH_PATH = "search:"
NO_LIST = False          # list_of_path's answer for a path that names no list
_PATH_CHARS = re.compile(r"[a-z0-9_:]{1,%d}\Z" % LIST_PATH_MAX)
_HEX = re.compile(r"(?:[0-9a-f]{2})+\Z")
# The menu a right press on a tab or a crumb opens, placed where no box is
# known (an exe without GetElementBox): under the tab strip's start, in dp.
MENU_FALLBACK = (12.0, 76.0)


def _slug(label):
	"""A tree row's id from its locale key: WIKI_SUB_COSTUME_HAIR is
	costume_hair, WIKI_CAT_COSTUMES is costumes. Links keep these, so a
	renamed key keeps its id by giving the row an "id"."""
	text = label.lower()
	for prefix in ("wiki_cat_", "wiki_sub_"):
		if text.startswith(prefix):
			text = text[len(prefix):]
	return re.sub(r"[^a-z0-9_]", "_", text)


def _ident(entry):
	return entry.get("id") or _slug(entry["label"])


def _item_sub(label, item_type, item_sub=-1):
	return {"label": label, "kind": "items", "item_type": item_type, "item_sub": item_sub}


def _mob_subs(kind):
	return [
		{"label": "WIKI_SUB_LV1_109", "kind": "mobs", "mob_kind": kind, "band": BANDS[0]},
		{"label": "WIKI_SUB_LV110_129", "kind": "mobs", "mob_kind": kind, "band": BANDS[1]},
		{"label": "WIKI_SUB_LV130", "kind": "mobs", "mob_kind": kind, "band": BANDS[2]},
	]


def _vnum_sub(label, vnums):
	return {"label": label, "kind": "vnums", "vnums": vnums}


# OLD's WIKI_CATEGORIES on NEW's data: equipment by class, the hand-kept chest
# and costume lists, and the mob bands.
TREE = (
	{"label": "WIKI_CAT_EQUIPMENT", "subs": [
		_item_sub("WIKI_SUB_WEAPONS", "ITEM_TYPE_WEAPON"),
		_item_sub("WIKI_SUB_ARMOR", "ITEM_TYPE_ARMOR", "ARMOR_BODY"),
		_item_sub("WIKI_SUB_HELMETS", "ITEM_TYPE_ARMOR", "ARMOR_HEAD"),
		_item_sub("WIKI_SUB_SHIELDS", "ITEM_TYPE_ARMOR", "ARMOR_SHIELD"),
		_item_sub("WIKI_SUB_EARRINGS", "ITEM_TYPE_ARMOR", "ARMOR_EAR"),
		_item_sub("WIKI_SUB_BRACELETS", "ITEM_TYPE_ARMOR", "ARMOR_WRIST"),
		_item_sub("WIKI_SUB_NECKLACES", "ITEM_TYPE_ARMOR", "ARMOR_NECK"),
		_item_sub("WIKI_SUB_SHOES", "ITEM_TYPE_ARMOR", "ARMOR_FOOTS"),
		_item_sub("WIKI_SUB_BELTS", "ITEM_TYPE_BELT"),
		_item_sub("WIKI_SUB_RINGS", "ITEM_TYPE_RING"),
	]},
	{"label": "WIKI_CAT_CHESTS", "subs": [
		_vnum_sub("WIKI_SUB_BOSS_CHESTS", data.CHEST_BOSS),
		_vnum_sub("WIKI_SUB_EVENT_CHESTS", data.CHEST_EVENT),
		_vnum_sub("WIKI_SUB_ALT_CHESTS", data.CHEST_ALT),
	]},
	{"label": "WIKI_CAT_BOSSES", "subs": _mob_subs(MOBS_BOSS)},
	{"label": "WIKI_CAT_MONSTERS", "subs": _mob_subs(MOBS_MONSTER)},
	{"label": "WIKI_CAT_METINS", "subs": _mob_subs(MOBS_METIN)},
	{"label": "WIKI_CAT_COSTUMES", "subs": [
		_vnum_sub("WIKI_SUB_COSTUME_WEAPONS", data.COSTUME_WEAPONS),
		_vnum_sub("WIKI_SUB_COSTUME_ARMOR", data.COSTUME_ARMOR),
		_vnum_sub("WIKI_SUB_COSTUME_HAIR", data.COSTUME_HAIR),
		_vnum_sub("WIKI_SUB_COSTUME_PETS", data.COSTUME_PETS),
		_vnum_sub("WIKI_SUB_COSTUME_MOUNTS", data.COSTUME_MOUNTS),
		_vnum_sub("WIKI_SUB_COSTUME_WINGS", data.COSTUME_WINGS),
		_vnum_sub("WIKI_SUB_COSTUME_MASKS", data.COSTUME_MASKS),
		_vnum_sub("WIKI_SUB_COSTUME_EFFECTS", data.COSTUME_EFFECTS),
	]},
) + tuple(data.TEXT_CATEGORIES)

# The answers: {(kind, vnum): answer dict}, kept by the data cache (on disk per
# server and data version).
import datacache
ANSWERS = datacache.Table("wiki")


def _locale(key):
	import localeInfo
	return getattr(localeInfo, key, key)


def _modelpreview():
	try:
		import modelpreview
	except ImportError:
		return None
	return modelpreview


def _item_name(vnum):
	import item
	item.SelectItem(vnum)
	return item.GetItemName()


def _item_icon(vnum):
	import item
	item.SelectItem(vnum)
	return nui_slots.icon_source(item.GetIconImageFileName())


def preview_of(vnum):
	"""How an item's page shows its model: ("value3", race), ("parts", race,
	(armor, weapon, hair, sash)), or None for an icon-only item (wings,
	facials, effects, anything else: NEW does not draw them). OLD's
	item model preview, on NEW's parts: pets and mounts by item.GetValue(3)
	(scope "What the render target needs"), a costume or equipment piece on
	the player's body."""
	import item
	if vnum in data.COSTUME_PETS or vnum in data.COSTUME_MOUNTS:
		item.SelectItem(vnum)
		race = int(item.GetValue(3))
		return ("value3", race) if race else None
	if vnum in data.COSTUME_WINGS or vnum in data.COSTUME_MASKS or vnum in data.COSTUME_EFFECTS:
		return None
	item.SelectItem(vnum)
	item_type = item.GetItemType()
	sub = item.GetItemSubType()
	parts = None
	if item_type == item.ITEM_TYPE_WEAPON:
		parts = (0, vnum, 0, 0)
	elif item_type == item.ITEM_TYPE_ARMOR and sub == item.ARMOR_BODY:
		parts = (vnum, 0, 0, 0)
	elif item_type == item.ITEM_TYPE_COSTUME:
		if sub == item.COSTUME_TYPE_BODY:
			parts = (vnum, 0, 0, 0)
		elif sub == item.COSTUME_TYPE_WEAPON:
			parts = (0, vnum, 0, 0)
		elif sub == item.COSTUME_TYPE_HAIR:
			parts = (0, 0, int(item.GetValue(3)), 0)
		elif sub in (item.COSTUME_TYPE_SASH, item.COSTUME_TYPE_SASH2):
			parts = (0, 0, 0, vnum)
	if parts is None:
		return None
	race = _wearer_race(item)
	return None if race is None else ("parts", race, parts)


def _wearer_race(item_module):
	"""The race to dress: the player's when the selected item allows it, else
	the first race whose job and sex the item allows, as OLD's preview."""
	import player
	flags = {0: "ITEM_ANTIFLAG_WARRIOR", 1: "ITEM_ANTIFLAG_ASSASSIN", 2: "ITEM_ANTIFLAG_SURA", 3: "ITEM_ANTIFLAG_SHAMAN"}
	male_races = (0, 2, 5, 7)
	def allowed(race):
		if item_module.IsAntiFlag(getattr(item_module, flags[race % 4])):
			return False
		sex_flag = "ITEM_ANTIFLAG_MALE" if race in male_races else "ITEM_ANTIFLAG_FEMALE"
		return not item_module.IsAntiFlag(getattr(item_module, sex_flag))
	own = int(player.GetRace())
	if allowed(own):
		return own
	for race in range(8):
		if allowed(race):
			return race
	return None


class _WikiBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The browser's document; its events go to the window. Every press that
	follows a link passes its button: the window opens a middle press, or a
	left press with Ctrl held, in a new tab. A right press on a tab or a
	crumb opens their menu; any other press closes it."""

	DOCUMENT = DOCUMENT
	MODEL = "wiki"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)
		self._owner.board_pressed()

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.Close()

	# The body takes no focus (a press on the window keeps another window's
	# caret), so the field asks for its own, as the shop search's does.
	@nui.on("search_press")
	def on_search_press(self, button):
		self.raise_for(button)
		if button == 0:
			self.focus(SEARCH_FIELD)

	@nui.on("search_change")
	def on_search_change(self, text, linebreak=False):
		self._owner.search(text)
		if linebreak:
			self._owner.open_first()

	@nui.on("tree_press")
	def on_tree_press(self, category, button):
		self.raise_for(button)
		if button == 0:
			self._owner.toggle_category(int(category))

	@nui.on("sub_press")
	def on_sub_press(self, category, sub, button):
		self.raise_for(button)
		self._owner.open_sub(int(category), int(sub), int(button))

	@nui.on("quick_press")
	def on_quick_press(self, category, sub, button):
		self.raise_for(button)
		self._owner.open_sub(int(category), int(sub), int(button))

	@nui.on("row_press")
	def on_row_press(self, index, button):
		self.raise_for(button)
		self._owner.select_row(int(index), int(button))

	@nui.on("row_over")
	def on_row_over(self, index):
		self._owner.over_row(int(index))

	@nui.on("row_out")
	def on_row_out(self):
		self._owner.out_row()

	@nui.on("recent_press")
	def on_recent_press(self, index, button):
		self.raise_for(button)
		self._owner.open_recent(int(index), int(button))

	@nui.on("origin_press")
	def on_origin_press(self, index, button):
		self.raise_for(button)
		self._owner.press_origin(int(index), int(button))

	@nui.on("loot_press")
	def on_loot_press(self, kind, vnum, button):
		self.raise_for(button)
		self._owner.open_item(int(vnum), int(button))

	@nui.on("loot_over")
	def on_loot_over(self, vnum):
		self._owner.over_vnum(int(vnum))

	@nui.on("loot_out")
	def on_loot_out(self):
		self._owner.out_row()

	@nui.on("back_press")
	def on_back_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.back()

	@nui.on("forward_press")
	def on_forward_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.forward()

	@nui.on("home_press")
	def on_home_press(self, button):
		self.raise_for(button)
		self._owner.home(int(button))

	@nui.on("crumb_press")
	def on_crumb_press(self, index, button):
		self.raise_for(button)
		if button == 1:
			self._owner.crumb_menu(int(index))
		else:
			self._owner.press_crumb(int(index), int(button))

	@nui.on("tab_press")
	def on_tab_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.switch_tab(int(index))
		elif button == 1:
			self._owner.tab_menu(int(index))
		elif button == 2:
			self._owner.close_tab(int(index))

	@nui.on("tab_close_press")
	def on_tab_close_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.close_tab(int(index))

	@nui.on("new_tab_press")
	def on_new_tab_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.new_tab()

	@nui.on("link_press")
	def on_link_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.link_page()

	@nui.on("menu_press")
	def on_menu_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.press_menu(int(index))

	@nui.on("retry_fire")
	def on_retry_fire(self):
		self._owner.retry_fire()

	@nui.on("timeout_fire")
	def on_timeout_fire(self):
		self._owner.timeout_fire()


def _home():
	return (None, None)


def _new_tab(location):
	return {"stack": [location], "at": 0}


def _shorten(text, limit):
	return text if len(text) <= limit else text[:limit - 3].rstrip() + "..."


def wiki_link(kind, vnum, name):
	"""The chat link of an item's or a mob's page, OLD's syswiki form
	(syswiki:<kind>:<ident>, opened by Interface.__OpenWikiLink) in the
	color OLD's quests gave it. A "|" in the name would end the link's tags,
	so it is left out."""
	ident = "item" if kind == KIND_ITEM else "mob"
	name = (name or "").replace("|", "")
	return "|c%s|Hsyswiki:%s:%d|h[%s]|h|r" % (LINK_COLOR, ident, int(vnum), name)


def wiki_list_link(path, name):
	"""The chat link of a list page (a tree row's list, the home page, a
	search): syswiki:list:<path>, opened by Interface.__OpenWikiLink."""
	name = (name or "").replace("|", "")
	return "|c%s|Hsyswiki:list:%s|h[%s]|h|r" % (LINK_COLOR, path, name)


def _search_hex(text):
	"""The search's UTF-8 bytes in hex, cut at a character so the path keeps
	to LIST_PATH_MAX: a longer search links its first characters, whose
	matches include the longer one's."""
	budget = (LIST_PATH_MAX - len(SEARCH_PATH)) // 2
	data_bytes = b""
	for char in text:
		encoded = char.encode("utf-8")
		if len(data_bytes) + len(encoded) > budget:
			break
		data_bytes += encoded
	return "".join("%02x" % b for b in bytearray(data_bytes))


def list_path(list_key):
	"""A list's link path: "home" for none, "<category id>:<list id>" for a
	tree row's list, "search:<hex>" for a search."""
	if list_key is None:
		return HOME_PATH
	if list_key[0] == "search":
		return SEARCH_PATH + _search_hex(list_key[1])
	category = TREE[list_key[1]]
	return "%s:%s" % (_ident(category), _ident(category["subs"][list_key[2]]))


def list_of_path(path):
	"""The list a link path names (None: the home page), or NO_LIST for a
	path that names none (a stale link, a tree row that went, bad hex)."""
	if not isinstance(path, str) or not _PATH_CHARS.match(path):
		return NO_LIST
	if path == HOME_PATH:
		return None
	if path.startswith(SEARCH_PATH):
		digits = path[len(SEARCH_PATH):]
		if not _HEX.match(digits):
			return NO_LIST
		try:
			text = bytes(bytearray(int(digits[i:i + 2], 16) for i in range(0, len(digits), 2))).decode("utf-8")
		except UnicodeDecodeError:
			return NO_LIST
		text = text.strip()
		return ("search", text) if text else NO_LIST
	for i, category in enumerate(TREE):
		for j, sub in enumerate(category["subs"]):
			if path == "%s:%s" % (_ident(category), _ident(sub)):
				return ("sub", i, j)
	return NO_LIST


class WikiWindow(nui_facade.Facade, ui.Window):
	"""The browser (Interface.wndWiki). Facade's Show and Hide handle the
	board; ui.Window.__init__ calls Hide before this __init__ finishes, so
	everything Hide can reach has a class-level default.

	Where the browser is: a location, (list, page). The list is None, a tree
	row ("sub", category, sub) or a search ("search", text); the page is None
	or (kind, vnum). (None, None) is the home page. Each tab keeps its own
	history of locations (a stack and the place in it), as a browser does;
	the tabs and the recently viewed pages last as long as the window."""

	KEY = KEY
	BOARD = _WikiBoard
	PLACE = "center"
	tooltip = None
	_current = None
	_preview_shown = False
	_hover_shown = False
	_hover_key = None        # (kind, vnum) in the hover preview, None when none
	_paste_link = None
	_menu_actions = ()       # the open menu's actions, one per entry (None: off)
	_menu_fresh = False      # the press that opened the menu is still bubbling

	def __init__(self):
		self.nui_begin()
		try:
			ui.Window.__init__(self)
			self.AddFlag("movable")
			self.AddFlag("float")
			self._rows = []          # (kind, vnum) of the shown list
			self._list_key = False   # the list the rows are of (False: none built yet)
			self._origins = []
			self._open = {}          # category index: unfolded
			self._retries = 0
			self._tabs = [_new_tab(_home())]
			self._active = 0
			self._recent = []        # (kind, vnum), the last page shown first
			self._crumbs = []        # the trail's locations, None for a label only
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			"tree": [],
			"list": [],
			"list_state": "",
			"list_title": "",
			"list_count": "",
			"list_sel": -1,
			# The home page: the quick links (every category and its lists)
			# and the pages viewed last.
			"home": True,
			"quick": [],
			"recent": [],
			# The tabs, back and forward, and the trail.
			"tabs": [],
			"tabs_full": False,
			"can_back": False,
			"can_forward": False,
			"crumbs": [],
			# The page: "", "loading", "failed" or "ready", the kind ("item",
			# "mob") and its head, and the sections its answer brought.
			"page_state": "",
			"page_kind": "",
			"page_vnum": 0,
			"page_name": "",
			"page_sub": "",
			"page_icon": "",
			"page_common": False,
			# Every page links (Eddy's r39 notes); the key stays for the
			# fixtures and the tests.
			"page_link": True,
			# The menu of a right press on a tab or a crumb: its entries
			# ({"i", "label", "off"}; none: closed) and its place in dp.
			"menu": [],
			"menu_x": 0.0,
			"menu_y": 0.0,
			"model_view": False,
			"hover_view": False,
			"origins": [],
			"chest": [],
			"refine": [],
			"drops": [],
			# The clocks that retry a request and give up on an answer.
			"retry_at": 0.0,
			"timeout_at": 0.0,
		}

	# --- the Interface's calls --------------------------------------------------------

	def SetPasteLinkEvent(self, event):
		"""Interface.PasteWikiLink: puts a page's link where the player types."""
		self._paste_link = event

	def Open(self):
		self._show_window()
		self._render(refresh_page=True)

	def _show_window(self):
		self.nui_set(quick=self._quick_model())
		self.Show()
		self.SetTop()

	def Close(self):
		self.Hide()

	def Toggle(self):
		"""The Wiki button (inventory, system menu): opens the wiki, brings a
		wiki that is open but behind another window to the front, and closes
		only a wiki already on top (nui_hud.is_top)."""
		if not self.IsShow():
			self.Open()
		elif nui_hud.is_top(self):
			self.Close()
		else:
			self.SetTop()

	def OpenItem(self, vnum):
		self._show_window()
		self._go(self._at_page(KIND_ITEM, int(vnum)))
		return True

	def OpenMob(self, vnum):
		self._show_window()
		self._go(self._at_page(KIND_MOB, int(vnum)))
		return True

	def OpenLink(self, kind, ident):
		"""A syswiki link, syswiki:<kind>:<ident>: "item" and "mob" (a vnum)
		and "list" (a path) open here; any other kind goes to _open_link.
		False when nothing opened."""
		if kind == "list":
			return self.OpenList(ident)
		if kind in ("item", "mob"):
			try:
				vnum = int(ident)
			except (TypeError, ValueError):
				return False
			return self.OpenItem(vnum) if kind == "item" else self.OpenMob(vnum)
		return self._open_link(kind, ident)

	def _open_link(self, kind, ident):
		"""The hook for link kinds this module does not know; none opens
		yet. NOVA-139's text pages come through Interface.OpenWikiPage, to
		OpenPage (feature/wiki-pages)."""
		return False

	def OpenList(self, path):
		"""A list link (syswiki:list:<path>): that list, or the home page, in
		this tab. False, and nothing opens, for a path that names no list."""
		list_key = list_of_path(path)
		if list_key is NO_LIST:
			return False
		self._show_window()
		self._go((list_key, None))
		return True

	def Destroy(self):
		self._clear_previews()
		self._paste_link = None
		nui_facade.Facade.Destroy(self)

	def Hide(self):
		self._stop_preview(PREVIEW)
		self._stop_preview(HOVER_PREVIEW)
		self._preview_shown = False
		self._hover_shown = False
		self._hover_key = None
		if self.__dict__.get("_state") and self._state.get("hover_view"):
			self.nui_set(hover_view=False)
		self.close_menu()
		nui_facade.Facade.Hide(self)

	# --- locations, history and tabs ----------------------------------------------------

	def _tab(self):
		return self._tabs[self._active]

	def _location(self):
		tab = self._tab()
		return tab["stack"][tab["at"]]

	def _at_page(self, kind, vnum):
		"""The current list with this page."""
		return (self._location()[0], (kind, vnum))

	@staticmethod
	def _wants_new_tab(button):
		"""A middle press, or a left press with Ctrl held, as in a browser."""
		if button == 2:
			return True
		if button != 0:
			return False
		import app
		keys = [getattr(app, name, None) for name in ("DIK_LCONTROL", "DIK_RCONTROL")]
		return any(key is not None and app.IsPressed(key) for key in keys)

	def _follow(self, location, button):
		"""A press on a link: a new tab, the same tab, or nothing (a right press)."""
		if self._wants_new_tab(button):
			self._open_tab(location)
		elif button == 0:
			self._go(location)

	def _go(self, location):
		"""Shows a location in this tab. A new one drops the pages ahead (as
		a browser does after Back); the one already shown shows again (a
		page that could not load asks again)."""
		tab = self._tab()
		if location != self._location():
			del tab["stack"][tab["at"] + 1:]
			tab["stack"].append(location)
			if len(tab["stack"]) > HISTORY_MAX:
				del tab["stack"][0]
			tab["at"] = len(tab["stack"]) - 1
		self._render(refresh_page=True)

	def _replace(self, location):
		tab = self._tab()
		tab["stack"][tab["at"]] = location

	def back(self):
		tab = self._tab()
		if tab["at"] > 0:
			tab["at"] -= 1
			self._render()

	def forward(self):
		tab = self._tab()
		if tab["at"] < len(tab["stack"]) - 1:
			tab["at"] += 1
			self._render()

	def home(self, button=0):
		self._follow(_home(), button)

	def _open_tab(self, location):
		"""A new tab behind this one, as a browser's middle click opens it;
		its page is asked for when the tab shows."""
		if len(self._tabs) >= TABS_MAX:
			self._say_tabs_full()
			return False
		self._tabs.append(_new_tab(location))
		self.nui_set(**self._tabs_model())
		return True

	def _say_tabs_full(self):
		import chat
		text = _locale("WIKI_TABS_FULL")
		try:
			text = text % TABS_MAX
		except (TypeError, ValueError):
			pass
		chat.AppendChat(chat.CHAT_TYPE_INFO, text)

	def new_tab(self):
		if self._open_tab(_home()):
			self.switch_tab(len(self._tabs) - 1)

	def switch_tab(self, index):
		if 0 <= index < len(self._tabs) and index != self._active:
			self._active = index
			self._render()

	def close_tab(self, index):
		"""The tab goes; the one after it shows (the one before, for the last
		tab). The last tab left becomes a home tab."""
		if not (0 <= index < len(self._tabs)):
			return
		if len(self._tabs) == 1:
			self._tabs = [_new_tab(_home())]
			self._active = 0
			self._render()
			return
		del self._tabs[index]
		if index < self._active:
			self._active -= 1
			self.nui_set(**self._tabs_model())
		elif index == self._active:
			self._active = min(index, len(self._tabs) - 1)
			self._render()
		else:
			self.nui_set(**self._tabs_model())

	# --- what a location shows ------------------------------------------------------------

	def _render(self, refresh_page=False, sync_field=True):
		"""Shows the active tab's location: the list (built again only when
		it changed), the page (selected again only when it changed, or on
		refresh_page), the tree's mark, the trail, the tabs and the home page."""
		list_key, page = self._location()
		if list_key != self._list_key:
			self._build_list(list_key)
		if page is None:
			self._clear_page()
		elif refresh_page or page != self._current:
			self._select(page[0], page[1])
			self._remember(page)
		if list_key is not None and list_key[0] == "sub":
			self._open[list_key[1]] = True
		home = list_key is None and page is None
		values = dict(self._tabs_model())
		values.update(self._list_mark())
		self._crumbs, values["crumbs"] = self._crumbs_model(list_key, page)
		values.update(home=home, tree=self._tree_model())
		if home:
			values["recent"] = self._recent_model()
		self.nui_set(**values)
		if sync_field:
			self._sync_field(list_key)

	def _sync_field(self, list_key):
		"""The search field shows the location's search, or nothing. Its text
		is never in the model (docs/ui/AUTHORING.md "Text fields"), and the
		change it causes finds the same search, so it changes nothing."""
		board = self.nui_board()
		if board is None or not board.is_visible():
			return
		text = list_key[1] if list_key is not None and list_key[0] == "search" else ""
		if board.get_value(SEARCH_FIELD) != text:
			board.set_value(SEARCH_FIELD, text, caret="end")

	def _label(self, location):
		list_key, page = location
		if page is not None:
			return self._page_name(page[0], page[1])
		if list_key is not None:
			return self._list_title(list_key)
		return _locale("WIKI_HOME")

	def _tabs_model(self):
		tabs = [{"i": i, "label": nui.plain_text(_shorten(self._label(tab["stack"][tab["at"]]), TAB_LABEL_MAX)),
		         "active": i == self._active} for i, tab in enumerate(self._tabs)]
		tab = self._tab()
		return {"tabs": tabs, "tabs_full": len(self._tabs) >= TABS_MAX,
		        "can_back": tab["at"] > 0, "can_forward": tab["at"] < len(tab["stack"]) - 1}

	def _list_title(self, list_key):
		if list_key[0] == "sub":
			return _locale(TREE[list_key[1]]["subs"][list_key[2]]["label"])
		text = _locale("WIKI_SEARCH_TRAIL")
		try:
			return text % list_key[1]
		except (TypeError, ValueError):
			return "%s %s" % (text, list_key[1])

	def _crumbs_model(self, list_key, page):
		"""The trail: Home, the category and the list (or the search), the
		page. Each but the last goes back up to its place in this tab; the
		category is a label only."""
		trail = [(_locale("WIKI_HOME"), _home())]
		if list_key is not None:
			if list_key[0] == "sub":
				trail.append((_locale(TREE[list_key[1]]["label"]), None))
			trail.append((self._list_title(list_key), (list_key, None)))
		if page is not None:
			trail.append((self._page_name(page[0], page[1]), (list_key, page)))
		last = len(trail) - 1
		model = [{"i": i, "label": nui.plain_text(label), "last": i == last, "link": i != last and target is not None}
		         for i, (label, target) in enumerate(trail)]
		return [target for _, target in trail], model

	def press_crumb(self, index, button=0):
		if 0 <= index < len(self._crumbs) - 1 and self._crumbs[index] is not None:
			self._follow(self._crumbs[index], button)

	def _list_mark(self):
		"""Which row is the shown page."""
		page = self._location()[1]
		sel = self._rows.index(page) if page is not None and page in self._rows else -1
		return {"list_sel": sel}

	# --- the tree, the list and the home page --------------------------------------------

	def _tree_model(self):
		shown = self._location()[0]
		rows = []
		for i, category in enumerate(TREE):
			subs = []
			if self._open.get(i):
				subs = [{"cat": i, "sub": j, "label": nui.plain_text(_locale(s["label"])),
				         "selected": shown == ("sub", i, j)}
				        for j, s in enumerate(category["subs"])]
			rows.append({"cat": i, "label": nui.plain_text(_locale(category["label"])),
			             "open": bool(self._open.get(i)), "subs": subs})
		return rows

	def _quick_model(self):
		return [{"cat": i, "label": nui.plain_text(_locale(category["label"])),
		         "subs": [{"cat": i, "sub": j, "label": nui.plain_text(_locale(s["label"]))}
		                  for j, s in enumerate(category["subs"])]}
		        for i, category in enumerate(TREE)]

	def toggle_category(self, index):
		self._open[index] = not self._open.get(index)
		self.nui_set(tree=self._tree_model())

	def open_sub(self, category, sub, button=0):
		if 0 <= category < len(TREE) and 0 <= sub < len(TREE[category]["subs"]):
			self._open_sub(TREE[category]["subs"][sub], button)

	def _open_sub(self, sub, button=0):
		"""Opens a tree row's list. A "page" row (NOVA-139's text pages,
		nui_wiki_data.TEXT_CATEGORIES) goes to _open_text_page."""
		if sub.get("kind") == "page":
			self._open_text_page(sub, button)
			return
		for i, category in enumerate(TREE):
			for j, candidate in enumerate(category["subs"]):
				if candidate is sub:
					self._follow((("sub", i, j), None), button)
					return

	def _open_text_page(self, sub, button=0):
		"""Where NOVA-139's text pages open: a location whose page is
		("text", sub["page"]) once that ticket brings a page format."""

	def _build_list(self, list_key):
		self._list_key = list_key
		if list_key is None:
			self._rows = []
			self.nui_set(list=[], list_state="", list_title="", list_count="")
			return
		if list_key[0] == "search":
			import item
			import nonplayer
			text = list_key[1]
			pairs = [(KIND_ITEM, v) for v in item.Search(text, SEARCH_ROWS_MAX) if v not in data.ITEM_BLACKLIST]
			pairs += [(KIND_MOB, v) for v in nonplayer.Search(text, SEARCH_ROWS_MAX) if v not in data.MOB_BLACKLIST]
		else:
			sub = TREE[list_key[1]]["subs"][list_key[2]]
			kind = sub["kind"]
			if kind == "items":
				pairs = [(KIND_ITEM, v) for v in self._list_items(sub)]
			elif kind == "vnums":
				pairs = [(KIND_ITEM, v) for v in self._list_vnums(sub["vnums"])]
			else:
				pairs = [(KIND_MOB, v) for v in self._list_mobs(sub)]
		self._set_pairs(pairs)
		self.nui_set(list_title=nui.plain_text(self._list_title(list_key)), list_count=str(len(self._rows)))

	def _list_items(self, sub):
		import item
		item_type = getattr(item, sub["item_type"])
		item_sub = sub["item_sub"]
		item_sub = getattr(item, item_sub) if isinstance(item_sub, str) else item_sub
		return [v for v in item.ListByType(item_type, item_sub) if v not in data.ITEM_BLACKLIST]

	def _list_vnums(self, vnums):
		"""A hand-kept list, in vnum order. nui_wiki_data keeps only vnums in
		NEW's item_proto: item.SelectItem reports a missing vnum to syserr and
		selects another item, so it cannot test for one."""
		return sorted(vnums)

	def _list_mobs(self, sub):
		import nonplayer
		return [v for v in nonplayer.List(sub["mob_kind"], sub["band"][0], sub["band"][1]) if v not in data.MOB_BLACKLIST]

	def search(self, text):
		"""The field's text. Typing on in a search changes it in place, so a
		search is one step of the tab's history; an empty field leaves it."""
		text = text.strip() if isinstance(text, str) else ""
		list_key, page = self._location()
		searching = list_key is not None and list_key[0] == "search"
		if text:
			location = (("search", text), page)
			if list_key == location[0]:
				return
			if searching:
				self._replace(location)
			else:
				tab = self._tab()
				del tab["stack"][tab["at"] + 1:]
				tab["stack"].append(location)
				tab["at"] += 1
		elif searching:
			self._replace((None, page))
		else:
			return
		self._render(sync_field=False)

	def open_first(self):
		"""Enter in the search field: the first match's page."""
		if self._rows:
			self.select_row(0)

	def _set_pairs(self, pairs):
		pairs = pairs[:LIST_ROWS_MAX]
		self._rows = pairs
		rows = [self._row_model(i, kind, vnum) for i, (kind, vnum) in enumerate(pairs)]
		self.nui_set(list=rows, list_state="ready" if rows else "empty")

	def _row_model(self, index, kind, vnum):
		if kind == KIND_ITEM:
			return {"i": index, "vnum": vnum, "mob": False, "icon": _item_icon(vnum),
			        "name": nui.plain_text(_item_name(vnum)), "note": ""}
		import nonplayer
		return {"i": index, "vnum": vnum, "mob": True, "icon": "",
		        "name": nui.plain_text(nonplayer.GetMonsterName(vnum)),
		        "note": nui.plain_text(_locale("WIKI_LEVEL") % int(nonplayer.GetMonsterLevel(vnum)))}

	def _remember(self, page):
		if page in self._recent:
			self._recent.remove(page)
		self._recent.insert(0, page)
		del self._recent[RECENT_MAX:]

	def _recent_model(self):
		return [self._row_model(i, kind, vnum) for i, (kind, vnum) in enumerate(self._recent)]

	def open_recent(self, index, button=0):
		if 0 <= index < len(self._recent):
			self._follow((None, self._recent[index]), button)

	# --- the page ------------------------------------------------------------------------

	def select_row(self, index, button=0):
		if 0 <= index < len(self._rows):
			self._follow(self._at_page(*self._rows[index]), button)

	def open_item(self, vnum, button=0):
		self._follow(self._at_page(KIND_ITEM, int(vnum)), button)

	def press_origin(self, index, button=0):
		"""A mob or chest origin opens its own page; NPCs do not."""
		if not (0 <= index < len(self._origins)):
			return
		origin_type, source = self._origins[index]
		if origin_type == ORIGIN_MOB:
			self._follow(self._at_page(KIND_MOB, source), button)
		elif origin_type == ORIGIN_CHEST:
			self._follow(self._at_page(KIND_ITEM, source), button)

	def link_page(self):
		"""The Link button: the shown place's chat link where the player
		types (the whisper that has the focus, else the chat input)."""
		self._paste(self._link_of(self._location()))

	def _link_of(self, location):
		"""A page links as syswiki:item or syswiki:mob, a list (the home
		page, a tree row's list, a search) as syswiki:list."""
		list_key, page = location
		if page is not None:
			return wiki_link(page[0], page[1], self._raw_name(page[0], page[1]))
		if list_key is None:
			name = _locale("WIKI_TITLE")
		elif list_key[0] == "sub":
			name = "%s > %s" % (_locale(TREE[list_key[1]]["label"]), self._list_title(list_key))
		else:
			name = self._list_title(list_key)
		return wiki_list_link(list_path(list_key), name)

	def _paste(self, link):
		"""The focus leaves the search field first, so the paste does not
		land there."""
		if self._paste_link is None:
			return
		board = self.nui_board()
		if board is not None:
			board.focus(PARK)
		self._paste_link(link)

	# --- the menu of a right press on a tab or a crumb ----------------------------------

	def tab_menu(self, index):
		"""Close, and Close other tabs (off with one tab)."""
		if not (0 <= index < len(self._tabs)):
			return
		others = len(self._tabs) > 1
		self._open_menu("wiki-tab-%d" % index, (
			("WIKI_MENU_CLOSE", lambda: self.close_tab(index)),
			("WIKI_MENU_CLOSE_OTHERS", (lambda: self.close_other_tabs(index)) if others else None),
		))

	def crumb_menu(self, index):
		"""Open in new tab, and Link. The category is a label, with no place
		of its own, so it has no menu."""
		if not (0 <= index < len(self._crumbs)) or self._crumbs[index] is None:
			self.close_menu()
			return
		target = self._crumbs[index]
		self._open_menu("wiki-crumb-%d" % index, (
			("WIKI_MENU_NEW_TAB", lambda: self._open_tab(target)),
			("WIKI_LINK", lambda: self._paste(self._link_of(target))),
		))

	def _open_menu(self, element_id, entries):
		"""The menu under the pressed element (its border box's bottom left,
		in dp from the window's)."""
		x, y = MENU_FALLBACK
		board = self.nui_board()
		box = board.element_box(element_id) if board is not None else None
		body = board.element_box("") if board is not None else None
		if box and body:
			scale = nui.get_scale() or 1.0
			x = (box[0] - body[0]) / scale
			y = (box[1] + box[3] - body[1]) / scale
		self._menu_actions = tuple(action for _, action in entries)
		self._menu_fresh = True
		self.nui_set(menu=[{"i": i, "label": nui.plain_text(_locale(key)), "off": action is None}
		                   for i, (key, action) in enumerate(entries)], menu_x=x, menu_y=y)

	def close_menu(self):
		self._menu_actions = ()
		self._menu_fresh = False
		if self.__dict__.get("_state") and self._state.get("menu"):
			self.nui_set(menu=[])

	def board_pressed(self):
		"""Any press on the window closes the menu, but the one that opened it."""
		if self._menu_fresh:
			self._menu_fresh = False
		elif self._menu_actions:
			self.close_menu()

	def press_menu(self, index):
		"""An entry's action, after the menu closes; an off entry only closes it."""
		actions = self._menu_actions
		self.close_menu()
		if 0 <= index < len(actions) and actions[index] is not None:
			actions[index]()

	def close_other_tabs(self, index):
		"""Only that tab is left, and it shows."""
		if not (0 <= index < len(self._tabs)) or len(self._tabs) == 1:
			return
		self._tabs = [self._tabs[index]]
		self._active = 0
		self._render()

	def _raw_name(self, kind, vnum):
		if kind == KIND_ITEM:
			return _item_name(vnum)
		import nonplayer
		return nonplayer.GetMonsterName(vnum)

	def _page_name(self, kind, vnum):
		return nui.plain_text(self._raw_name(kind, vnum))

	def _clear_page(self):
		if self._current is None and not self._state.get("page_state"):
			return
		self._current = None
		self._origins = []
		self._stop_preview(PREVIEW)
		self._preview_shown = False
		self.nui_set(page_state="", page_kind="", page_vnum=0, page_name="", page_sub="", page_icon="",
		             page_common=False, model_view=False, origins=[], chest=[], refine=[], drops=[],
		             retry_at=0.0, timeout_at=0.0)

	def _select(self, kind, vnum):
		self._current = (kind, vnum)
		self._retries = 0
		head = self._page_head(kind, vnum)
		self._show_preview(kind, vnum)
		answer = ANSWERS.get((kind, vnum))
		if answer is not None:
			self._publish(kind, vnum, head, answer)
			return
		self._send_current()
		self.nui_set(page_state="loading", origins=[], chest=[], refine=[], drops=[], page_common=False, **head)

	def _page_head(self, kind, vnum):
		if kind == KIND_ITEM:
			return {"page_kind": "item", "page_vnum": vnum, "page_icon": _item_icon(vnum),
			        "page_name": nui.plain_text(_item_name(vnum)), "page_sub": ""}
		import nonplayer
		return {"page_kind": "mob", "page_vnum": vnum, "page_icon": "",
		        "page_name": nui.plain_text(nonplayer.GetMonsterName(vnum)),
		        "page_sub": nui.plain_text(_locale("WIKI_LEVEL") % int(nonplayer.GetMonsterLevel(vnum)))}

	def _send_current(self):
		"""Asks the server for the page being shown and arms the give-up
		clock. A request the server refuses or never answers is sent again
		until TRIES_MAX; the window never waits forever."""
		import net
		if self._current is None:
			return
		kind, vnum = self._current
		self._retries += 1
		net.SendWikiRequest(kind, vnum)
		self.nui_set(retry_at=0.0, timeout_at=nui.now() + ANSWER_WAIT_SECONDS)

	def retry_fire(self):
		self.nui_set(retry_at=0.0)
		if self._current is not None and self._current not in ANSWERS and self._retries < TRIES_MAX:
			self._send_current()

	def timeout_fire(self):
		"""No answer in time: ask again, or say it could not load."""
		self.nui_set(timeout_at=0.0)
		if self._current is None or self._current in ANSWERS:
			return
		if self._retries >= TRIES_MAX:
			self.nui_set(page_state="failed", retry_at=0.0)
			return
		self._send_current()

	def WikiAnswer(self, kind, status, vnum, flags, origins, chest, refine, drops):
		"""BINARY_WikiAnswer: a page's rows, or BUSY when the server's limit
		refused the request. A busy answer for the shown page asks again
		after RETRY_SECONDS (a refused request must not leave the page
		empty); other answers are kept for the session."""
		key = (int(kind), int(vnum))
		if status == STATUS_BUSY:
			if key == self._current and self._retries < TRIES_MAX:
				self.nui_set(retry_at=nui.now() + RETRY_SECONDS)
			return
		answer = {"flags": int(flags), "origins": list(origins), "chest": list(chest),
		          "refine": list(refine), "drops": list(drops)}
		ANSWERS[key] = answer
		if key == self._current:
			self.nui_set(timeout_at=0.0, retry_at=0.0)
			self._publish(key[0], key[1], self._page_head(key[0], key[1]), answer)

	def _publish(self, kind, vnum, head, answer):
		self._origins = [(int(t), int(source)) for t, source in answer["origins"]]
		origins = []
		for i, (origin_type, source) in enumerate(self._origins):
			origins.append({"i": i, "label": nui.plain_text(_locale(ORIGIN_LABELS.get(origin_type, ""))),
			                "name": nui.plain_text(self._origin_name(origin_type, source)),
			                "link": origin_type in (ORIGIN_MOB, ORIGIN_CHEST)})
		self.nui_set(page_state="ready", page_common=bool(answer["flags"] & FLAG_COMMON),
		             origins=origins, chest=self._loot_rows(answer["chest"]),
		             refine=self._refine_rows(answer["refine"]),
		             drops=self._loot_rows(answer["drops"]), **head)

	def _origin_name(self, origin_type, source):
		import nonplayer
		if origin_type == ORIGIN_CHEST:
			return _item_name(source)
		return nonplayer.GetMonsterName(source)

	def _loot_rows(self, rows):
		out = []
		for i, (vnum, count) in enumerate(rows):
			out.append({"i": i, "vnum": int(vnum), "icon": _item_icon(int(vnum)),
			            "name": nui.plain_text(_item_name(int(vnum))),
			            "count": str(int(count)) if int(count) > 1 else ""})
		return out

	def _refine_rows(self, rows):
		import localeInfo
		out = []
		for path, step, cost, materials in rows:
			mats = [{"vnum": int(v), "count": str(int(c)), "icon": _item_icon(int(v))} for v, c in materials]
			label = "+%d" % (int(step) + 1)
			if int(path):
				label = "%s (%d)" % (label, int(path) + 1)
			out.append({"label": label, "cost": nui.plain_text(localeInfo.NumberToMoneyString(int(cost))), "mats": mats})
		return out

	# --- the model previews -------------------------------------------------------------

	def _show_preview(self, kind, vnum, name=PREVIEW):
		"""One preview on the page and one on hover (the scope's default):
		mobs by their vnum, items by preview_of. An item with no drawable
		model, or a race the client cannot make, shows its icon."""
		preview = _modelpreview()
		shown = False
		if preview is not None:
			if name == HOVER_PREVIEW and hasattr(preview, "SetDwell"):
				preview.SetDwell(name, HOVER_DWELL_MS)
			if kind == KIND_MOB:
				shown = bool(preview.Select(name, vnum))
			else:
				plan = preview_of(vnum)
				if plan is not None:
					shown = bool(preview.Select(name, plan[1]))
					if shown and plan[0] == "parts":
						shown = bool(preview.SetParts(name, *plan[2]))
			if shown:
				preview.Show(name, True)
		if name == PREVIEW:
			self._preview_shown = shown
			self.nui_set(model_view=shown)
		else:
			self._hover_key = (kind, vnum)
			self._set_hover_view(shown)
		if not shown and preview is not None:
			preview.Show(name, False)

	def _stop_preview(self, name):
		if not self.__dict__.get("_state"):
			return
		preview = _modelpreview()
		if preview is not None:
			preview.Show(name, False)

	def _clear_previews(self):
		preview = _modelpreview()
		if preview is not None:
			preview.Clear(PREVIEW)
			preview.Clear(HOVER_PREVIEW)

	def _set_hover_view(self, shown):
		"""hover_view only when it changes: each change adds or removes the
		hover nui-view element."""
		shown = bool(shown)
		self._hover_shown = shown
		if bool(self._state.get("hover_view")) != shown:
			self.nui_set(hover_view=shown)

	def over_row(self, index):
		"""RmlUi 6.3 bubbles mouseover, so a row can report the pointer more
		than once (its children take no pointer in wiki.rcss as well): the
		row already in the hover preview selects nothing again."""
		if not (0 <= index < len(self._rows)):
			return
		kind, vnum = self._rows[index]
		if self._hover_key == (kind, vnum):
			return
		self._show_tooltip(kind, vnum)
		self._show_preview(kind, vnum, HOVER_PREVIEW)

	def over_vnum(self, vnum):
		self._show_tooltip(KIND_ITEM, vnum)

	def _show_tooltip(self, kind, vnum):
		if kind != KIND_ITEM:
			return
		if self.tooltip is None:
			import uiToolTip
			self.tooltip = uiToolTip.ItemToolTip()
			self.tooltip.HideToolTip()
		self.tooltip.SetItemToolTip(int(vnum))

	def out_row(self):
		if self.tooltip is not None:
			self.tooltip.HideToolTip()
		self._hover_key = None
		if self._hover_shown:
			self._stop_preview(HOVER_PREVIEW)
		self._set_hover_view(False)
