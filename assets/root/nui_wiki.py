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

Nothing runs per frame: the search is the field's change event, and the retry
and the give-up are two hidden nui-countdowns (retry_at, timeout_at). The
board exists only while the window shows. NOVA-139's text pages plug in at
nui_wiki_data.TEXT_CATEGORIES; _open_sub dispatches on a row's "kind".
"""

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

# Sessions' answers: {(kind, vnum): answer dict}.
ANSWERS = {}


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
	"""The browser's document; its events go to the window."""

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

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.Close()

	@nui.on("search_change")
	def on_search_change(self, text):
		self._owner.search(text)

	@nui.on("tree_press")
	def on_tree_press(self, category, button):
		self.raise_for(button)
		if button == 0:
			self._owner.toggle_category(int(category))

	@nui.on("sub_press")
	def on_sub_press(self, category, sub, button):
		self.raise_for(button)
		if button == 0:
			self._owner.open_sub(int(category), int(sub))

	@nui.on("row_press")
	def on_row_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.select_row(int(index))

	@nui.on("row_over")
	def on_row_over(self, index):
		self._owner.over_row(int(index))

	@nui.on("row_out")
	def on_row_out(self):
		self._owner.out_row()

	@nui.on("origin_press")
	def on_origin_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner.press_origin(int(index))

	@nui.on("loot_press")
	def on_loot_press(self, kind, vnum, button):
		self.raise_for(button)
		if button == 0:
			self._owner.open_item(int(vnum))

	@nui.on("loot_over")
	def on_loot_over(self, vnum):
		self._owner.over_vnum(int(vnum))

	@nui.on("loot_out")
	def on_loot_out(self):
		self._owner.out_row()

	@nui.on("retry_fire")
	def on_retry_fire(self):
		self._owner.retry_fire()

	@nui.on("timeout_fire")
	def on_timeout_fire(self):
		self._owner.timeout_fire()


class WikiWindow(nui_facade.Facade, ui.Window):
	"""The browser (Interface.wndWiki). Facade's Show and Hide handle the
	board; ui.Window.__init__ calls Hide before this __init__ finishes, so
	everything Hide can reach has a class-level default."""

	KEY = KEY
	BOARD = _WikiBoard
	PLACE = "center"
	tooltip = None
	_current = None
	_preview_shown = False
	_hover_shown = False

	def __init__(self):
		self.nui_begin()
		try:
			ui.Window.__init__(self)
			self.AddFlag("movable")
			self.AddFlag("float")
			self._rows = []          # {"kind", "vnum"} of the shown list
			self._origins = []
			self._sub = None
			self._open = {}          # category index: unfolded
			self._search = ""
			self._retries = 0
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_model(self):
		return {
			"search": "",
			"tree": [],
			"list": [],
			"list_state": "",
			# The page: "", "loading", "failed" or "ready", the kind ("item",
			# "mob") and its head, and the sections its answer brought.
			"page_state": "",
			"page_kind": "",
			"page_vnum": 0,
			"page_name": "",
			"page_sub": "",
			"page_icon": "",
			"page_common": False,
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

	def Open(self):
		self.nui_set(tree=self._tree_model())
		self.Show()
		self.SetTop()

	def Close(self):
		self.Hide()

	def Toggle(self):
		if self.IsShow():
			self.Close()
		else:
			self.Open()

	def OpenItem(self, vnum):
		self.Open()
		self._select(KIND_ITEM, int(vnum))
		return True

	def OpenMob(self, vnum):
		self.Open()
		self._select(KIND_MOB, int(vnum))
		return True

	def Destroy(self):
		self._clear_previews()
		nui_facade.Facade.Destroy(self)

	def Hide(self):
		self._stop_preview(PREVIEW)
		self._stop_preview(HOVER_PREVIEW)
		self._preview_shown = False
		self._hover_shown = False
		nui_facade.Facade.Hide(self)

	# --- the tree and the list ----------------------------------------------------------

	def _tree_model(self):
		rows = []
		for i, category in enumerate(TREE):
			subs = []
			if self._open.get(i):
				subs = [{"cat": i, "sub": j, "label": nui.plain_text(_locale(s["label"]))}
				        for j, s in enumerate(category["subs"])]
			rows.append({"cat": i, "label": nui.plain_text(_locale(category["label"])),
			             "open": bool(self._open.get(i)), "subs": subs})
		return rows

	def toggle_category(self, index):
		self._open[index] = not self._open.get(index)
		self.nui_set(tree=self._tree_model())

	def open_sub(self, category, sub):
		self._open_sub(TREE[category]["subs"][sub])

	def _open_sub(self, sub):
		"""Fills the list from a tree row. A "page" row (NOVA-139's text
		pages, nui_wiki_data.TEXT_CATEGORIES) would dispatch here."""
		self._sub = sub
		self._search = ""
		self.nui_set(search="")
		kind = sub["kind"]
		if kind == "items":
			self._set_rows(KIND_ITEM, self._list_items(sub))
		elif kind == "vnums":
			self._set_rows(KIND_ITEM, self._list_vnums(sub["vnums"]))
		elif kind == "mobs":
			self._set_rows(KIND_MOB, self._list_mobs(sub))

	def _list_items(self, sub):
		import item
		item_type = getattr(item, sub["item_type"])
		item_sub = sub["item_sub"]
		item_sub = getattr(item, item_sub) if isinstance(item_sub, str) else item_sub
		return [v for v in item.ListByType(item_type, item_sub) if v not in data.ITEM_BLACKLIST]

	def _list_vnums(self, vnums):
		"""A hand-kept list holds what exists in this proto."""
		import item
		found = []
		for vnum in sorted(vnums):
			if item.SelectItem(vnum):
				found.append(vnum)
		return found

	def _list_mobs(self, sub):
		import nonplayer
		return [v for v in nonplayer.List(sub["mob_kind"], sub["band"][0], sub["band"][1]) if v not in data.MOB_BLACKLIST]

	def search(self, text):
		text = text.strip()
		self._search = text
		if not text:
			self.nui_set(list=[], list_state="")
			self._rows = []
			return
		import item
		import nonplayer
		rows = [(KIND_ITEM, v) for v in item.Search(text, SEARCH_ROWS_MAX) if v not in data.ITEM_BLACKLIST]
		rows += [(KIND_MOB, v) for v in nonplayer.Search(text, SEARCH_ROWS_MAX) if v not in data.MOB_BLACKLIST]
		self._set_pairs(rows)

	def _set_rows(self, kind, vnums):
		self._set_pairs([(kind, v) for v in vnums])

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

	# --- the page ------------------------------------------------------------------------

	def select_row(self, index):
		if 0 <= index < len(self._rows):
			kind, vnum = self._rows[index]
			self._select(kind, vnum)

	def open_item(self, vnum):
		self._select(KIND_ITEM, vnum)

	def press_origin(self, index):
		"""A mob or chest origin opens its own page; NPCs do not."""
		if not (0 <= index < len(self._origins)):
			return
		origin_type, source = self._origins[index]
		if origin_type == ORIGIN_MOB:
			self._select(KIND_MOB, source)
		elif origin_type == ORIGIN_CHEST:
			self._select(KIND_ITEM, source)

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
			self._hover_shown = shown
			self.nui_set(hover_view=shown)
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

	def over_row(self, index):
		if not (0 <= index < len(self._rows)):
			return
		kind, vnum = self._rows[index]
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
		if self._hover_shown:
			self._hover_shown = False
			self._stop_preview(HOVER_PREVIEW)
			self.nui_set(hover_view=False)
