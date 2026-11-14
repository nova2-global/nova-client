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
and the give-up are two hidden nui-countdowns (retry_at, timeout_at); a third
(preview_check_at, NOVA-259) runs only while the client makes a preview's
model off the frame, which shows a plain box until the model fades in. The
board is loaded once, at the window's making (the probe, during the phase
change), and kept hidden and emptied between opens (NOVA-263: an open loads
no document); the tabs and their histories stay with the window. NOVA-139's text pages (nui_wiki_pages.py)
are a page kind of their own, KIND_PAGE, whose rows sit in the tree after
the browser's categories.

Round four (after r41): equipment lists filter by class as OLD's did
(CLASSES), every list has all its items and shows one page of
LIST_PAGE_ROWS rows at a time, the item tooltip is the Interface's
(SetItemToolTip), and a press on a page's model preview opens the model
viewer (VIEWER_PREVIEW) over the content area.
"""

import re

import ui

import nui
import nui_facade
import nui_hud
import nui_slots
import nui_wiki_data as data
import nui_wiki_pages as pages

DOCUMENT = "nui/windows/wiki/wiki.rml"
KEY = "wiki"
PREVIEW = "wiki"
HOVER_PREVIEW = "wiki_hover"
# The hover preview makes a model only once the pointer has rested on a row
# this long, and not while the wheel turns (modelpreview.SetDwell): a list
# scrolled under a still pointer changes the row every few frames (r39).
HOVER_DWELL_MS = 180
# NOVA-259: the previews' models are made off the frame (modelpreview.
# SetBackground: the loader thread reads their files, the client parses one a
# step and makes one model a step) and with their race's wait motions only
# (modelpreview.SetWaitOnly), since the wiki plays nothing else. r46: an item
# on a player race other than the player's made the race's every motion in
# one frame, 320 to 340 ms (35 GR2s, its 30 emotions among them); r47: a
# costume on the player's own race cost 21 ms of the frame that opened the
# wiki. A preview whose model is not made yet stays plain (its view clear: no
# text, no icon) and the model fades in once made (wiki.rcss, is-loading: the
# dungeon manager's late boss fade, 0.15 s).
# Each is one flag, for a client without the calls or a test of the old way.
BACKGROUND_PREVIEWS = True
WAIT_ONLY_PREVIEWS = True
# Seconds between two looks at a preview whose model the client still makes
# (the hidden preview_check_at clock, armed only while one does).
PREVIEW_POLL = 0.1
# Where a preview is (_preview_state): its model shows, the client still
# makes it, or there is nothing to show (no model, or its part has no mesh).
READY, LOADING, BLANK = "ready", "loading", "blank"
# NOVA-263: the board is kept, hidden and emptied (nui_hud.KeptBoard), from
# the window's making on: the probe that making runs anyway (during the phase
# change) loads the document once, and no open loads it again (r48: the open
# spent 8.3 to 10.5 ms in wiki.rml). False keeps it from the first open on.
KEEP_BOARD_FROM_PROBE = True
# The lists and clocks a kept hidden board holds none of (RmlUi updates every
# loaded document each frame); the next show sets them again from the state.
_EMPTY_BOARD = {
	"tree": [], "list": [], "quick": [], "recent": [], "tabs": [], "crumbs": [], "menu": [], "classes": [],
	"origins": [], "chest": [], "refine": [], "drops": [], "tp_blocks": [], "tp_decor": [], "tp_view": [],
	"model_view": False, "hover_view": False, "viewer": False,
	"retry_at": 0.0, "timeout_at": 0.0, "preview_check_at": 0.0, "tp_open_at": 0.0,
}

# EWikiKind and EWikiStatus (nova-protocol's wiki_packets.h).
KIND_ITEM, KIND_MOB = 0, 1
# NOVA-139: a text page's place is (KIND_PAGE, path) (nui_wiki_pages).
KIND_PAGE = pages.KIND_PAGE
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
# Every list has all its items (r41: the costume lists stopped at 500 and a
# search at 200). The window lays out one page of LIST_PAGE_ROWS rows at a
# time (Prev and Next under the list), so a list of thousands costs the
# layout of a short one; the rows keep their index in the whole list. A
# search asks the client for up to SEARCH_ROWS_MAX of each kind: all of
# them, in practice.
LIST_PAGE_ROWS = 100
SEARCH_ROWS_MAX = 100000
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

# Equipment by class (NOVA-42 r4), OLD's class buttons (inGameWikiUI.py
# CLASS_BUTTONS) in OLD's order, and All. An item shows under a class when it
# lacks that class's anti-flag (OLD's GameLib/ItemManager.cpp
# IsFilteredAntiflag), so an item several classes use shows under each and
# an item any class uses under every one. NEW has no lycan (the client
# exports no ITEM_ANTIFLAG_WOLFMAN, the tooltip lists four classes), as OLD
# had it off (INGAME_WIKI_WOLFMAN). The filter is part of an equipment
# list's place, ("sub", category, list, class), so a tab, Back and Forward
# and a list link (equipment:weapons:sura) keep it; the class last picked
# stays for the next equipment list, as OLD's button did, and the first is
# the player's own (race % 4: warrior, ninja, sura, shaman).
CLASSES = (
	("warrior", "ITEM_ANTIFLAG_WARRIOR", "TOOLTIP_WARRIOR"),
	("ninja", "ITEM_ANTIFLAG_ASSASSIN", "TOOLTIP_ASSASSIN"),
	("shaman", "ITEM_ANTIFLAG_SHAMAN", "TOOLTIP_SHAMAN"),
	("sura", "ITEM_ANTIFLAG_SURA", "TOOLTIP_SURA"),
)
CLASS_ALL = "all"
CLASS_IDS = tuple(c[0] for c in CLASSES) + (CLASS_ALL,)
JOB_CLASSES = ("warrior", "ninja", "sura", "shaman")

# The model viewer (Eddy after r41): a press on a page's model preview shows
# it over the content area, in a view of its own so the page's small view
# never holds a big target; closing it clears that preview (its target goes,
# its model waits in the client's pool). A drag turns it (VIEWER_TURN
# degrees a dp) and stops its own turn, the wheel zooms by VIEWER_ZOOM_STEP
# a notch between the limits (the client's camera distance,
# modelpreview.SetZoom), a double click resets it.
VIEWER_PREVIEW = "wiki_viewer"
VIEWER_TURN = 0.6
VIEWER_ZOOM_STEP = 1.15
VIEWER_ZOOM_MIN = 0.5
VIEWER_ZOOM_MAX = 4.0


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
	return {"label": label, "kind": "items", "item_type": item_type, "item_sub": item_sub, "by_class": True}


def class_allows(item_module, ident):
	"""The selected item is usable by the class `ident` (OLD's rule: it lacks
	that class's anti-flag); every item is, for All."""
	for name, flag, _ in CLASSES:
		if name == ident:
			value = getattr(item_module, flag, None)
			return value is None or not item_module.IsAntiFlag(value)
	return True


def _by_class(list_key):
	"""The list is an equipment list, which the class filter applies to."""
	return bool(list_key) and list_key[0] == "sub" and bool(TREE[list_key[1]]["subs"][list_key[2]].get("by_class"))


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
) + tuple(data.TEXT_CATEGORIES) + tuple(pages.tree_categories())

# The answers: {(kind, vnum): answer dict}, kept by the data cache (on disk per
# server and data version).
import datacache
ANSWERS = datacache.Table("wiki")


def _locale(key):
	if isinstance(key, tuple):  # NOVA-139: a text page's row, ("page", path)
		return pages.label(key)
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


# NOVA-177: the part of a preview's model a page is about, as
# modelpreview.GetState's meshes orders them. A model is made even when the
# file its part names is not in the pack (tools/model_gaps.py), and draws
# nothing there; the page then shows the icon, with no zoom mark and no
# viewer. A preview that waits (the hover's dwell, a background request) has
# no meshes yet: it is judged once its model is made (NOVA-259: the
# preview_check_at clock), and an item or mob found empty is not hovered
# again.
MESH_BODY, MESH_WEAPON, MESH_HAIR, MESH_SASH = 0, 1, 2, 3
_NO_MESH = set()  # (kind, vnum, race) whose part draws nothing


def _plan_part(plan):
	"""The meshes index of the part preview_of's plan is about: the body for
	a pet or mount, else the one part it sets."""
	if plan[0] != "parts":
		return MESH_BODY
	parts = plan[2]
	for index in (MESH_WEAPON, MESH_HAIR, MESH_SASH):
		if parts[index]:
			return index
	return MESH_BODY


def _preview_state(preview, name, part, key):
	"""Where the preview `name` is: LOADING while its request waits (the
	client makes the model over its next steps), BLANK when the request
	ended with no model or its model has no mesh in `part` (that key goes in
	_NO_MESH), else READY; READY too when the client cannot say (an exe
	before NOVA-177)."""
	get_state = getattr(preview, "GetState", None)
	if get_state is None:
		return READY
	try:
		state = get_state(name)
	except Exception:
		return READY
	if not isinstance(state, dict):
		return READY
	if state.get("pending"):
		return LOADING
	if "has_model" in state and not state.get("has_model"):
		return BLANK
	meshes = state.get("meshes")
	if meshes is None or meshes[part]:
		return READY
	_NO_MESH.add(key)
	return BLANK


def _prepare(preview, name):
	"""Makes `name` a background, wait-only preview (NOVA-259), as far as the
	client has the calls; before every Select, since Clear forgets both."""
	for call, on in (("SetBackground", BACKGROUND_PREVIEWS), ("SetWaitOnly", WAIT_ONLY_PREVIEWS)):
		function = getattr(preview, call, None)
		if on and function is not None:
			function(name, True)


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

	@nui.on("list_prev_press")
	def on_list_prev_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.list_page_step(-1)

	@nui.on("list_next_press")
	def on_list_next_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.list_page_step(1)

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

	# NOVA-139: a text page's links and its viewport (nui_wiki_pages).
	@nui.on("tp_link")
	def on_tp_link(self, index, button):
		self.raise_for(button)
		self._owner.follow_text_link(int(index), int(button))

	@nui.on("tp_open")
	def on_tp_open(self):
		self._owner.text_page_open()

	# r4: an embedded item's tooltip (![[item:N]], nui_wiki_page_format).
	@nui.on("tp_over")
	def on_tp_over(self, index):
		self._owner.over_text_link(int(index))

	@nui.on("tp_out")
	def on_tp_out(self):
		self._owner.out_text_link()

	# r4: the equipment list's class filter.
	@nui.on("class_press")
	def on_class_press(self, index, button):
		self.raise_for(button)
		self._owner.press_class(int(index), int(button))

	# r4: the model viewer. The stage is the model's view (a drag turns it,
	# the wheel zooms, a double click resets it); the backdrop around it
	# closes the viewer on a press, as the close button does.
	@nui.on("preview_press")
	def on_preview_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.open_viewer()

	@nui.on("viewer_close_press")
	def on_viewer_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.close_viewer()

	@nui.on("viewer_stage_press")
	def on_viewer_stage_press(self, button):
		self.raise_for(button)
		self._owner.viewer_stage_pressed()

	@nui.on("viewer_backdrop_press")
	def on_viewer_backdrop_press(self, button):
		self.raise_for(button)
		self._owner.viewer_backdrop_pressed(int(button))

	@nui.on("viewer_grab")
	def on_viewer_grab(self, x):
		self._owner.viewer_grab(float(x))

	@nui.on("viewer_drag")
	def on_viewer_drag(self, x):
		self._owner.viewer_drag(float(x))

	@nui.on("viewer_drop")
	def on_viewer_drop(self):
		self._owner.viewer_drop()

	@nui.on("viewer_wheel")
	def on_viewer_wheel(self, delta):
		self._owner.viewer_wheel(float(delta))

	@nui.on("viewer_reset")
	def on_viewer_reset(self):
		self._owner.viewer_reset()

	@nui.on("retry_fire")
	def on_retry_fire(self):
		self._owner.retry_fire()

	@nui.on("timeout_fire")
	def on_timeout_fire(self):
		self._owner.timeout_fire()

	# NOVA-259: a model the client makes over its next steps.
	@nui.on("preview_check")
	def on_preview_check(self):
		self._owner.preview_check()


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
	if kind == KIND_PAGE:
		return pages.chat_link(vnum, name, LINK_COLOR)
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


def _text_category(category):
	"""A text category (NOVA-139): its rows are text pages, not lists, and
	its own list is ("pages", index)."""
	return any(sub.get("kind") == "page" for sub in category["subs"])


def list_path(list_key):
	"""A list's link path: "home" for none, "<category id>:<list id>" for a
	tree row's list (and ":<class>" for an equipment list's filter), "<category id>" for a text category's pages,
	"search:<hex>" for a search."""
	if list_key is None:
		return HOME_PATH
	if list_key[0] == "search":
		return SEARCH_PATH + _search_hex(list_key[1])
	category = TREE[list_key[1]]
	if list_key[0] == "pages":
		return _ident(category)
	path = "%s:%s" % (_ident(category), _ident(category["subs"][list_key[2]]))
	return path + ":" + list_key[3] if len(list_key) > 3 else path


def list_of_path(path):
	"""The list a link path names (None: the home page), or NO_LIST for a
	path that names none (a stale link, a tree row that went, bad hex). An
	equipment list's path may end in its class; without one (r3's links)
	the window gives it the class in use (WikiWindow._with_class)."""
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
		if _text_category(category):
			# Its rows are pages (their labels are ("page", path)), not lists.
			if path == _ident(category):
				return ("pages", i)
			continue
		for j, sub in enumerate(category["subs"]):
			own = "%s:%s" % (_ident(category), _ident(sub))
			if path == own:
				return ("sub", i, j)
			if sub.get("by_class") and path.startswith(own + ":") and path[len(own) + 1:] in CLASS_IDS:
				return ("sub", i, j, path[len(own) + 1:])
	return NO_LIST


class WikiWindow(nui_facade.Facade, ui.Window, pages.TextPageWindow):
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
	_class = None            # the class filter last picked (None: the player's own)
	_tooltip_item = None     # the Interface's item tooltip (SetItemToolTip)
	_tip_link = None         # the text page link whose item tooltip shows
	_viewer = False          # the model viewer shows
	_viewer_plan = None      # (kind, vnum) it shows
	_viewer_rotation = 0.0
	_viewer_zoom = 1.0
	_viewer_grab_x = None    # the drag's last pointer x, in px
	_viewer_on_stage = False # the press on the model still bubbles to the backdrop
	_waiting = None          # NOVA-259: {preview name: (part, key)} whose model loads

	def __init__(self):
		self.nui_begin()
		try:
			ui.Window.__init__(self)
			self.AddFlag("movable")
			self.AddFlag("float")
			self._rows = []          # (kind, vnum) of the shown list, all of it
			self._list_page = 0      # its page of rows on show
			self._list_key = False   # the list the rows are of (False: none built yet)
			self._origins = []
			self._open = {}          # category index: unfolded
			self._retries = 0
			self._tabs = [_new_tab(_home())]
			self._active = 0
			self._recent = []        # (kind, vnum), the last page shown first
			self._crumbs = []        # the trail's locations, None for a label only
			self._waiting = {}       # the previews whose model the client still makes
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		model = {
			"tree": [],
			"list": [],
			"list_state": "",
			"list_title": "",
			"list_count": "",
			"list_sel": -1,
			# A long list's pager: the rows on show ("1-100 / 1385"; "" for a
			# list of one page) and whether there is a page before and after.
			"list_range": "",
			"list_prev": False,
			"list_next": False,
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
			# NOVA-259: a preview whose model the client still makes shows
			# nothing (its view clear, then the model fades in), and the
			# clock that looks again at it.
			"model_loading": False,
			"hover_loading": False,
			"viewer_loading": False,
			"preview_check_at": 0.0,
			# The equipment list's class filter ({"i", "id", "label", "on"};
			# none: not an equipment list).
			"classes": [],
			# The model viewer, and the name it shows.
			"viewer": False,
			"viewer_name": "",
			"origins": [],
			"chest": [],
			"refine": [],
			"drops": [],
			# The clocks that retry a request and give up on an answer.
			"retry_at": 0.0,
			"timeout_at": 0.0,
		}
		model.update(pages.initial_model())
		return model

	# --- the Interface's calls --------------------------------------------------------

	def SetPasteLinkEvent(self, event):
		"""Interface.PasteWikiLink: puts a page's link where the player types."""
		self._paste_link = event

	def SetItemToolTip(self, tooltip):
		"""The Interface's item tooltip (NovaUI's, nui_item_tooltip, when
		the tooltips flag is on), as the inventory gets it. Without one the
		wiki makes a legacy uiToolTip.ItemToolTip of its own."""
		self._tooltip_item = tooltip

	def OnPressEscapeKey(self):
		"""Escape closes the model viewer and keeps the key; with no viewer
		the key goes on, as it did before the viewer."""
		if self._viewer:
			self.close_viewer()
			return True
		return False

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
		self._go((self._with_class(list_key), None))
		return True

	def OpenPage(self, path):
		"""A text page (NOVA-139; a syswiki:page:<path> link). False for a
		bad path or a page index.txt does not list."""
		if not pages.exists(path):
			return False
		self._show_window()
		self._go(self._page_location(path))
		return True

	def nui_demand(self):
		"""NOVA-263: the board is kept, hidden and emptied, between opens,
		from the window's making on (KEEP_BOARD_FROM_PROBE)."""
		return nui_hud.KeptBoard(self._make_board, self._restore_board, self._keep_board, self._empty_board,
		                         keep_probe=KEEP_BOARD_FROM_PROBE)

	@staticmethod
	def _empty_board(board):
		"""The kept hidden board holds no list, view or clock (_EMPTY_BOARD);
		_restore_board sets the window's state again at the next show."""
		board.set(**_EMPTY_BOARD)

	def Destroy(self):
		self.close_viewer()
		self._clear_previews()
		self._paste_link = None
		self._tooltip_item = None
		nui_facade.Facade.Destroy(self)

	def Hide(self):
		self.close_viewer()
		self._hide_tip()
		self._tip_link = None
		self._stop_preview(PREVIEW)
		self._stop_preview(HOVER_PREVIEW)
		self._preview_shown = False
		self._hover_shown = False
		self._hover_key = None
		if self.__dict__.get("_state") and self._state.get("hover_view"):
			self.nui_set(hover_view=False, hover_loading=False)
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
		if list_key is not None and list_key[0] in ("sub", "pages"):
			self._open[list_key[1]] = True
		home = list_key is None and page is None
		self._page_of_shown()
		values = dict(self._tabs_model())
		values.update(self._list_mark())
		values["classes"] = self._classes_model(list_key)
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
		if list_key[0] == "pages":  # NOVA-139: a text category's pages
			return _locale(TREE[list_key[1]]["label"])
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
		shown, page = self._location()
		rows = []
		for i, category in enumerate(TREE):
			subs = []
			if self._open.get(i):
				subs = [{"cat": i, "sub": j, "label": nui.plain_text(_locale(s["label"])),
				         "selected": (shown is not None and tuple(shown[:3]) == ("sub", i, j))
				                     or page == (KIND_PAGE, s.get("page"))}
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
					self._follow((self._with_class(("sub", i, j)), None), button)
					return

	def _open_text_page(self, sub, button=0):
		"""NOVA-139: a text page opens with its category's pages as its list."""
		self._follow(self._page_location(sub["page"]), button)

	@staticmethod
	def _page_location(path):
		"""A text page's location: its category's pages and the page."""
		for i, category in enumerate(TREE):
			if any(s.get("page") == path for s in category["subs"]):
				return (("pages", i), (KIND_PAGE, path))
		return (None, (KIND_PAGE, path))

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
			pairs = [(KIND_PAGE, p) for p in pages.search(text)]
			pairs += [(KIND_ITEM, v) for v in item.Search(text, SEARCH_ROWS_MAX) if v not in data.ITEM_BLACKLIST]
			pairs += [(KIND_MOB, v) for v in nonplayer.Search(text, SEARCH_ROWS_MAX) if v not in data.MOB_BLACKLIST]
		elif list_key[0] == "pages":
			pairs = [(KIND_PAGE, s["page"]) for s in TREE[list_key[1]]["subs"]]
		else:
			sub = TREE[list_key[1]]["subs"][list_key[2]]
			kind = sub["kind"]
			if kind == "items":
				pairs = [(KIND_ITEM, v) for v in self._list_items(sub, list_key[3] if len(list_key) > 3 else CLASS_ALL)]
			elif kind == "vnums":
				pairs = [(KIND_ITEM, v) for v in self._list_vnums(sub["vnums"])]
			else:
				pairs = [(KIND_MOB, v) for v in self._list_mobs(sub)]
		self._set_pairs(pairs)
		self.nui_set(list_title=nui.plain_text(self._list_title(list_key)), list_count=str(len(self._rows)))

	def _list_items(self, sub, ident=CLASS_ALL):
		"""An equipment list, of the items the class `ident` can use."""
		import item
		item_type = getattr(item, sub["item_type"])
		item_sub = sub["item_sub"]
		item_sub = getattr(item, item_sub) if isinstance(item_sub, str) else item_sub
		out = []
		for v in item.ListByType(item_type, item_sub):
			if v in data.ITEM_BLACKLIST:
				continue
			if ident != CLASS_ALL:
				item.SelectItem(v)
				if not class_allows(item, ident):
					continue
			out.append(v)
		return out

	# --- the class filter ----------------------------------------------------------------

	def _own_class(self):
		import player
		try:
			race = int(player.GetRace())
		except Exception:
			race = 0
		return JOB_CLASSES[race % len(JOB_CLASSES)] if race >= 0 else JOB_CLASSES[0]

	def _picked_class(self):
		return self._class if self._class in CLASS_IDS else self._own_class()

	def _with_class(self, list_key):
		"""An equipment list's place with its class: the one it names, else
		the one last picked (the player's own at first)."""
		if list_key is not None and list_key[0] == "sub" and len(list_key) == 3 and _by_class(list_key):
			return list_key + (self._picked_class(),)
		return list_key

	def _classes_model(self, list_key):
		if not _by_class(list_key) or len(list_key) < 4:
			return []
		labels = [_locale(key) for _, _, key in CLASSES] + [_locale("WIKI_CLASS_ALL")]
		return [{"i": i, "id": ident, "label": nui.plain_text(labels[i]), "on": ident == list_key[3]}
		        for i, ident in enumerate(CLASS_IDS)]

	def press_class(self, index, button=0):
		"""A class of the equipment list's filter: this list (and the page
		beside it) for that class, a step of the tab's history; a middle
		press or Ctrl opens it in a new tab."""
		list_key, page = self._location()
		if not _by_class(list_key) or not (0 <= index < len(CLASS_IDS)):
			return
		ident = CLASS_IDS[index]
		wants_tab = self._wants_new_tab(button)
		if button == 0 and not wants_tab:
			self._class = ident
		self._follow((tuple(list_key[:3]) + (ident,), page), button)

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
		"""A new list: all its rows, shown from its first page."""
		self._rows = list(pairs)
		self._list_page = 0
		self._publish_rows()

	def _list_pages(self):
		return max(1, (len(self._rows) + LIST_PAGE_ROWS - 1) // LIST_PAGE_ROWS)

	def _publish_rows(self):
		"""The rows of the page on show; only those are made and laid out."""
		count = len(self._rows)
		self._list_page = max(0, min(self._list_page, self._list_pages() - 1))
		start = self._list_page * LIST_PAGE_ROWS
		end = min(count, start + LIST_PAGE_ROWS)
		rows = [self._row_model(i, self._rows[i][0], self._rows[i][1]) for i in range(start, end)]
		paged = count > LIST_PAGE_ROWS
		text = ""
		if paged:
			text = _locale("WIKI_LIST_RANGE")
			try:
				text = text % (start + 1, end, count)
			except (TypeError, ValueError):
				text = "%d-%d / %d" % (start + 1, end, count)
		self.nui_set(list=rows, list_state="ready" if count else "empty", list_range=nui.plain_text(text),
		             list_prev=paged and self._list_page > 0, list_next=paged and end < count)

	def list_page_step(self, step):
		"""Prev (-1) and Next (+1) under a long list."""
		page = self._list_page + step
		if 0 <= page < self._list_pages() and page != self._list_page:
			self._list_page = page
			self._publish_rows()

	def _page_of_shown(self):
		"""The list shows the page that holds the shown page's row."""
		page = self._location()[1]
		if page is not None and page in self._rows:
			wanted = self._rows.index(page) // LIST_PAGE_ROWS
			if wanted != self._list_page:
				self._list_page = wanted
				self._publish_rows()

	def _row_model(self, index, kind, vnum):
		if kind == KIND_PAGE:
			return pages.row_model(index, vnum)
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
		"""Any press on the window closes the menu, but the one that opened
		it. The body hears a press last, so a press on the viewer's model has
		bubbled through the backdrop by now."""
		self._viewer_on_stage = False
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
		if kind == KIND_PAGE:
			return pages.title(vnum)
		if kind == KIND_ITEM:
			return _item_name(vnum)
		import nonplayer
		return nonplayer.GetMonsterName(vnum)

	def _page_name(self, kind, vnum):
		return nui.plain_text(self._raw_name(kind, vnum))

	def _clear_page(self):
		self.close_viewer()
		self.out_text_link()
		if self._current is None and not self._state.get("page_state"):
			return
		self._current = None
		self._origins = []
		self._stop_preview(PREVIEW)
		self._preview_shown = False
		self.nui_set(page_state="", page_kind="", page_vnum=0, page_name="", page_sub="", page_icon="",
		             page_common=False, model_view=False, model_loading=False, origins=[], chest=[], refine=[], drops=[],
		             retry_at=0.0, timeout_at=0.0, **pages.initial_model())

	def _select(self, kind, vnum):
		self.close_viewer()
		self.out_text_link()
		if kind == KIND_PAGE:
			self._stop_preview(PREVIEW)
			self._preview_shown = False
			self._select_text_page(vnum)
			return
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
		if self._current is None or self._current[0] == KIND_PAGE:
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
		model, or a race the client cannot make, shows its icon. A model the
		client still makes (NOVA-259) leaves the view clear until it is made
		(preview_check), then fades in."""
		preview = None if kind == KIND_PAGE else _modelpreview()
		where, watch = BLANK, None
		if preview is not None:
			if name == HOVER_PREVIEW and hasattr(preview, "SetDwell"):
				preview.SetDwell(name, HOVER_DWELL_MS)
			where, watch = self._select_model(preview, name, kind, vnum)
			if where != BLANK:
				preview.Show(name, True)
		shown, loading = where != BLANK, where == LOADING
		if name == PREVIEW:
			self._preview_shown = shown
			self.nui_set(model_view=shown, model_loading=loading)
		else:
			self._hover_key = (kind, vnum)
			self._set_hover_view(shown, loading)
		if not shown and preview is not None:
			preview.Show(name, False)
		self._watch(name, watch if loading else None)

	@staticmethod
	def _select_model(preview, name, kind, vnum):
		"""Puts the model of a page in the preview `name`: a mob by its vnum,
		an item by preview_of, its race wearing the item's parts, in one
		Select (NOVA-259: one model, made off the frame; before, a model of
		the bare race and then SetParts). (where, (part, key)): BLANK when
		there is none to show, or when the part the page is about has no mesh
		to draw (NOVA-177: its file is not in the pack), LOADING while the
		client makes it, else READY."""
		if kind == KIND_MOB:
			key, part = (kind, vnum, vnum), MESH_BODY
			if key in _NO_MESH:
				return BLANK, None
			_prepare(preview, name)
			shown = bool(preview.Select(name, vnum))
		else:
			plan = preview_of(vnum)
			if plan is None:
				return BLANK, None
			key, part = (kind, vnum, plan[1]), _plan_part(plan)
			if key in _NO_MESH:
				return BLANK, None
			_prepare(preview, name)
			look = tuple(plan[2]) if plan[0] == "parts" else ()
			shown = bool(preview.Select(name, plan[1], *look))
		if not shown:
			return BLANK, None
		return _preview_state(preview, name, part, key), (part, key)

	def _watch(self, name, watch):
		"""Looks at the preview `name` again at the clock's end while the
		client makes its model (watch: its (part, key)); None stops looking."""
		waiting = self.__dict__.get("_waiting")
		if waiting is None:
			return
		if watch is None:
			waiting.pop(name, None)
		else:
			waiting[name] = watch
		if not self.__dict__.get("_state"):
			return
		armed = self._state.get("preview_check_at", 0.0) > 0
		if waiting and not armed:
			self.nui_set(preview_check_at=nui.now() + PREVIEW_POLL)
		elif not waiting and armed:
			self.nui_set(preview_check_at=0.0)

	def preview_check(self):
		"""The preview_check_at clock's end: each preview whose model was
		being made shows it now (it fades in: its loading flag goes), or, when
		the client made none or its part has no mesh, falls back as it would
		have at once (the page's icon, no hover box, no viewer). The clock
		runs again while one is still being made."""
		waiting = self.__dict__.get("_waiting")
		if not waiting or not self.__dict__.get("_state"):
			return
		preview = _modelpreview()
		for name, (part, key) in list(waiting.items()):
			where = _preview_state(preview, name, part, key) if preview is not None else BLANK
			if where == LOADING:
				continue
			del waiting[name]
			self._settle(preview, name, where)
		self.nui_set(preview_check_at=nui.now() + PREVIEW_POLL if waiting else 0.0)

	def _settle(self, preview, name, where):
		"""A preview whose model the client was making is READY or BLANK."""
		blank = where == BLANK
		if name == PREVIEW:
			if blank:
				self._preview_shown = False
				self.nui_set(model_view=False, model_loading=False)
			else:
				self.nui_set(model_loading=False)
		elif name == HOVER_PREVIEW:
			self._set_hover_view(not blank, False)
		elif name == VIEWER_PREVIEW:
			if blank:
				self.close_viewer()
				return
			self.nui_set(viewer_loading=False)
		if blank and preview is not None:
			preview.Show(name, False)

	# --- the model viewer -------------------------------------------------------------

	def open_viewer(self):
		"""The page's model, larger, over the content area: the same model
		(race, parts, hair, sash) in the viewer's own preview, turning at
		the natural distance. The page's small view rests meanwhile. Not
		while the page's own model is still being made (its view is clear
		then, with no zoom mark). The viewer makes a model of its own from the
		files the page's loaded, a step or two later (NOVA-259: the stage
		stays plain meanwhile, then the model fades in)."""
		if self._viewer or not self._preview_shown or self._current is None or self._current[0] == KIND_PAGE:
			return
		if self._state.get("model_loading"):
			return
		preview = _modelpreview()
		if preview is None:
			return
		kind, vnum = self._current
		where, watch = self._select_model(preview, VIEWER_PREVIEW, kind, vnum)
		if where == BLANK:
			preview.Clear(VIEWER_PREVIEW)
			return
		self._viewer = True
		self._viewer_plan = (kind, vnum)
		self._viewer_rotation = 0.0
		self._viewer_zoom = 1.0
		self._viewer_grab_x = None
		self._viewer_on_stage = False
		self._viewer_call("SetZoom", 1.0)
		self._viewer_call("SetTurn", True)
		preview.Show(VIEWER_PREVIEW, True)
		preview.Show(PREVIEW, False)
		self._hide_tip()
		self.nui_set(viewer=True, viewer_name=self._page_name(kind, vnum), viewer_loading=where == LOADING)
		self._watch(VIEWER_PREVIEW, watch if where == LOADING else None)

	def close_viewer(self):
		"""The close button, Escape, a press outside the model, a new page,
		a hide: the viewer's preview is cleared (its render target goes)."""
		if not self._viewer:
			return
		self._viewer = False
		self._viewer_plan = None
		self._viewer_grab_x = None
		self._viewer_on_stage = False
		self._watch(VIEWER_PREVIEW, None)
		preview = _modelpreview()
		if preview is not None:
			preview.Clear(VIEWER_PREVIEW)
			if self._preview_shown:
				preview.Show(PREVIEW, True)
		if self.__dict__.get("_state"):
			self.nui_set(viewer=False, viewer_name="", viewer_loading=False)

	def _viewer_call(self, call, *args):
		"""A viewer call the client may not have (an exe before r4)."""
		preview = _modelpreview()
		function = getattr(preview, call, None) if preview is not None else None
		if function is not None:
			function(VIEWER_PREVIEW, *args)

	def _viewer_state(self):
		preview = _modelpreview()
		get_state = getattr(preview, "GetState", None) if preview is not None else None
		try:
			return get_state(VIEWER_PREVIEW) if get_state is not None else None
		except Exception:
			return None

	def viewer_stage_pressed(self):
		"""A press on the model: it bubbles to the backdrop next, which must
		not close the viewer for it."""
		self._viewer_on_stage = True

	def viewer_backdrop_pressed(self, button):
		if self._viewer_on_stage:
			self._viewer_on_stage = False
			return
		if button == 0:
			self.close_viewer()

	def viewer_grab(self, x):
		"""A drag begins: the model stops its own turn where it is."""
		if not self._viewer:
			return
		self._viewer_grab_x = x
		state = self._viewer_state()
		if isinstance(state, dict) and "rotation" in state:
			self._viewer_rotation = float(state["rotation"])
		self._viewer_call("SetTurn", False)

	def viewer_drag(self, x):
		"""The pointer moved by dx px: the model turns VIEWER_TURN degrees a dp."""
		if not self._viewer or self._viewer_grab_x is None:
			return
		scale = nui.get_scale() or 1.0
		turn = (x - self._viewer_grab_x) / scale * VIEWER_TURN
		self._viewer_grab_x = x
		rotation = (self._viewer_rotation + turn) % 360.0
		self._viewer_rotation = 0.0 if rotation >= 360.0 else rotation
		self._viewer_call("SetRotation", self._viewer_rotation)

	def viewer_drop(self):
		self._viewer_grab_x = None

	def viewer_wheel(self, delta):
		"""RmlUi's wheel delta is negative upward: up zooms in."""
		if not self._viewer or not delta:
			return
		zoom = self._viewer_zoom * (VIEWER_ZOOM_STEP ** -delta)
		self._viewer_zoom = max(VIEWER_ZOOM_MIN, min(VIEWER_ZOOM_MAX, zoom))
		self._viewer_call("SetZoom", self._viewer_zoom)

	def viewer_reset(self):
		"""A double click: front on, the natural distance, turning again."""
		if not self._viewer:
			return
		self._viewer_rotation = 0.0
		self._viewer_zoom = 1.0
		self._viewer_grab_x = None
		self._viewer_call("SetRotation", 0.0)
		self._viewer_call("SetZoom", 1.0)
		self._viewer_call("SetTurn", True)

	def _stop_preview(self, name):
		if not self.__dict__.get("_state"):
			return
		self._watch(name, None)
		preview = _modelpreview()
		if preview is not None:
			preview.Show(name, False)

	def _clear_previews(self):
		self._watch(PREVIEW, None)
		self._watch(HOVER_PREVIEW, None)
		preview = _modelpreview()
		if preview is not None:
			preview.Clear(PREVIEW)
			preview.Clear(HOVER_PREVIEW)

	def _set_hover_view(self, shown, loading=False):
		"""hover_view only when it changes: each change adds or removes the
		hover nui-view element. hover_loading (NOVA-259) likewise: the box
		shows plain while its model is being made."""
		shown = bool(shown)
		loading = shown and bool(loading)
		self._hover_shown = shown
		changes = {}
		if bool(self._state.get("hover_view")) != shown:
			changes["hover_view"] = shown
		if bool(self._state.get("hover_loading")) != loading:
			changes["hover_loading"] = loading
		if changes:
			self.nui_set(**changes)

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

	def _item_tip(self):
		"""The Interface's item tooltip (SetItemToolTip), else one of the
		wiki's own."""
		if self._tooltip_item is not None:
			return self._tooltip_item
		if self.tooltip is None:
			import uiToolTip
			self.tooltip = uiToolTip.ItemToolTip()
			self.tooltip.HideToolTip()
		return self.tooltip

	def _show_tooltip(self, kind, vnum):
		if kind != KIND_ITEM:
			return
		self._item_tip().SetItemToolTip(int(vnum))

	def _hide_tip(self):
		tip = self._tooltip_item if self._tooltip_item is not None else self.tooltip
		if tip is not None:
			tip.HideToolTip()

	@staticmethod
	def _item_icon_of(vnum):
		return _item_icon(vnum)

	def out_row(self):
		self._hide_tip()
		self._hover_key = None
		if self._hover_shown:
			self._stop_preview(HOVER_PREVIEW)
		self._set_hover_view(False)
