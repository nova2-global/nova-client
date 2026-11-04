"""The offline shop's client numbers and rules (NOVA-9, wave 5 spec 5.6).

The legacy windows (uishop, uiprivateshopbuilder, uimyshopdecoration,
uisearchshop, uiofflineshoplog) and the NovaUI facades over them share these
values and helpers, so a rule lives here once and is testable without
widgets: the page and lock-row math, the extend cap, the renew and result
texts, the search rows, the empire flags, the sign rule.

Every game number the server owns comes from CONFIG (shop.GetConfig(), a
dict keyed by TOfflineShopConfigInfo's field names); CONFIG_DEFAULTS are the
server's code defaults (spec 5.2), used only until CONFIG arrives. The grid
geometry is the shop module's (shop.OFFLINE_SHOP_*, read at each call: K's
constants, never retyped). The numbers below are OLD's client constants.
Nothing here imports a C++ module at load time."""

import time as _time

# --- OLD's client numbers (spec 5.6) ------------------------------------------------------------

# A buy from a player's shop asks first only from this price on (OLD uiShop.py:1095-1099).
BUY_CONFIRM_MIN_PRICE = 1000000000
# The shop window closes this far from where it opened (OLD uiShop.py:1301-1305).
SHOP_CLOSE_RANGE = 1000
# Signs show within this range (OLD uiPrivateShopBuilder.py:83-130).
SIGN_RANGE = 3000
# How many of the nearest signs show. OLD's systemSetting.GetNearbyShopsDisplayed()
# (default 20, 5-40); NEW's exe has no such setting yet, so its default.
SIGN_DISPLAY_COUNT = 20
SIGN_DISPLAY_COUNT_MAX = 40
# A visited shop's sign keeps its "seen" color this long (OLD uiPrivateShopBuilder.py:134).
SIGN_SEEN_MINUTES = 30
# The sign rule runs at most this often (o-cli bug 23: OLD sorted every sign every frame).
SIGN_REFRESH_SEC = 1.0
# The owner panel's time text changes once a second (o-cli bug 23).
TIME_REFRESH_SEC = 1.0
# A log page the server refused as too soon (RESULT LOGS RATE_LIMITED: one LOGS a second, D17, OLD
# char.cpp:14676-14677) is asked again this much later.
LOG_RETRY_SEC = 1.0
# The search: autocomplete after 3 characters, 10 suggestions; pages of 25, 50 or
# 100 rows, 5 page buttons; 10 bookmarks (OLD uiSearchShop.py:86, 265, 274-313, 1323-1370).
AUTOCOMPLETE_MIN_CHARS = 3
AUTOCOMPLETE_COUNT = 10
SEARCH_PAGE_SIZES = (25, 50, 100)
SEARCH_PAGE_BUTTONS = 5
SEARCH_BOOKMARK_MAX = 10
BOOKMARK_FILE = "shop/bookmark_list.txt"
# Rename takes 25 characters (OLD uiShop.py:1612); the window title shows 20 (17 + "..."),
# the panel's sign 18 (OLD uiShop.py:593-594, 1680).
SIGN_RENAME_MAX = 25
SHOP_TITLE_MAX = 20
PANEL_SIGN_MAX = 18
# The withdraw dialog's digits (OLD uiShop.py:205).
WITHDRAW_DIGITS = 10
# The day picker's digits (OLD uiShop.py:1622).
DAYS_DIGITS = 2
SECONDS_PER_DAY = 86400

# The maps whose shops show an empire flag in the search (OLD uiSearchShop.py:990-994),
# and their names for the same-map check; any other map has no flag (o-cli bug 7).
MAP_EMPIRE = {1: 1, 21: 2, 41: 3}
MAP_NAME = {1: "metin2_map_a1", 21: "metin2_map_b1", 41: "metin2_map_c1"}
# OLD's flag art (d:/ymir work/ui/flag_empire/empire_<n>_256.dds) is not in NEW's packs (Q9):
# the empire select's flags (128 x 79) stand in, drawn at a quarter.
EMPIRE_FLAG = {1: "d:/ymir work/ui/intro/empire/empireflag_a.sub", 2: "d:/ymir work/ui/intro/empire/empireflag_b.sub",
               3: "d:/ymir work/ui/intro/empire/empireflag_c.sub"}
EMPIRE_FLAG_SCALE = 0.25

# The skill book and the forget book the search names by skill (OLD uiSearchShop.py:38-40).
SKILL_BOOK_VNUM = 50300
FORGET_BOOK_VNUM = 70037

# The search's 13 categories and the costume subcategories, in OLD's order (OLD
# uiSearchShop.py:55-80): the locale key of each name. The server numbers them from 1.
SEARCH_CATEGORIES = ("SEARCH_SHOP_CAT_ALL", "SEARCH_SHOP_CAT_WEAPONS", "SEARCH_SHOP_CAT_EQUIPMENTS",
                     "SEARCH_SHOP_CAT_VOUCHERS", "SEARCH_SHOP_CAT_COSTUMES", "SEARCH_SHOP_CAT_CHANGERS",
                     "SEARCH_SHOP_CAT_STONES", "SEARCH_SHOP_CAT_CHESTS", "SEARCH_SHOP_CAT_ITEMS",
                     "SEARCH_SHOP_CAT_MATERIALS", "SEARCH_SHOP_CAT_ORES", "SEARCH_SHOP_CAT_PETS",
                     "SEARCH_SHOP_CAT_MOUNTS")
COSTUME_CATEGORY = 5
SEARCH_COSTUME_SUBCATEGORIES = ("SEARCH_SHOP_COSTUME_BODY", "SEARCH_SHOP_COSTUME_HAIR", "SEARCH_SHOP_COSTUME_WEAPON",
                                "SEARCH_SHOP_COSTUME_WING", "SEARCH_SHOP_COSTUME_FACIAL", "SEARCH_SHOP_COSTUME_SASH",
                                "SEARCH_SHOP_COSTUME_BODY_EFFECT", "SEARCH_SHOP_COSTUME_WEAPON_EFFECT")
# The filter's gender (OLD uiSearchShop.py:858-883): both shown 0, male only 1, female only 2, neither 3.
GENDER_BOTH, GENDER_MALE, GENDER_FEMALE, GENDER_NONE = 0, 1, 2, 3
# The QUERY's mode (protocol EShopSearchMode: SHOP_SEARCH_BY_ITEM 0, SHOP_SEARCH_BY_CATEGORY 1; the
# exe exports no constant for it). It replaces OLD's magic "item index 1" of a category browse.
SEARCH_MODE_ITEM, SEARCH_MODE_CATEGORY = 0, 1

# The 37 operation results (spec 1.1 EOfflineShopResult) by name; a code's value is
# shop.OFFLINE_SHOP_RESULT_<NAME> (K), its text localeInfo.OFFLINE_SHOP_RESULT_<NAME>.
RESULT_NAMES = ("OK", "DISABLED", "MAP_NOT_ALLOWED", "CHANNEL_NOT_ALLOWED", "TOO_CLOSE", "NOT_ENOUGH_GOLD",
                "BAD_PRICE", "GOLD_CAP", "BAD_SIGN", "BAD_DECORATION", "ITEM_RESTRICTED", "BAD_SLOT", "SLOT_TAKEN",
                "SLOT_LOCKED", "ALREADY_OPEN", "NO_SHOP", "BUSY", "QUEST_RUNNING", "NOT_LOCKED", "RATE_LIMITED",
                "INVENTORY_FULL", "OWNER_GOLD_MAX", "EMPTY_SHOP", "EXPIRED", "EXTEND_CAP", "MAX_KITS", "NEED_KIT",
                "NOT_AT_SHOP", "SOLD_OUT", "PREMIUM_REQUIRED", "COOLDOWN", "SEARCH_MAP_DENIED", "TIMEOUT",
                "UNREACHABLE", "NOTHING_HELD", "OTHER_CHANNEL", "TRANSFER_LOST")
# GC RESULT's op: the operations of protocol EOfflineShopCG (k-report.md 5.1, offline_shop_packets.h:146),
# by name in K's order. The exe exports them as shop.OFFLINE_SHOP_OP_<NAME> (C); a shop module
# without them answers by K's numbering, which RESULT carries either way.
OP_NAMES = ("CREATE", "MANAGE", "CLOSE", "LOCK", "SIGN", "WITHDRAW_GOLD", "WITHDRAW_ITEM", "ADD_ITEM", "PRICE",
            "REMOVE", "MOVE", "EXPAND", "EXTEND", "LOGS", "WARP", "BUY", "LEAVE")
# The 12 log actions (spec 1.1 EOfflineShopLogAction), shop.OFFLINE_SHOP_LOG_ACTION_<NAME>.
LOG_ACTION_NAMES = ("OPEN", "CLOSE", "LOCK", "UNLOCK", "ADD_TIME", "ITEM_SOLD", "ITEM_INPUT", "ITEM_WITHDRAW",
                    "GOLD_WITHDRAW", "PRICE_UPDATE", "ITEM_REMOVE", "ITEM_MOVE")

# The server's code defaults (spec 5.2, OLD's values), until CONFIG arrives.
CONFIG_DEFAULTS = {
	"enabled": 1, "base_rows": 8, "rows_per_kit": 1, "max_kits": 16, "kit_vnum": 72350, "deco_vnum": 69500,
	"open_cost": 10000000, "renew_cost": 10000000, "duration_sec": 345600, "extend_price_per_day": 2500000,
	"extend_cap_days": 15, "tax_permille": 0, "max_gold": 9999999999999, "search_cooldown_ms": 1000,
	"model_count": 8, "models": [30000, 30002, 30003, 30004, 30005, 30006, 30007, 30008], "style_count": 6,
}

# The geometry of the protocol (shop.OFFLINE_SHOP_*), for a client whose shop module
# lacks it; K's exe exports the same values.
_GEOMETRY_NAMES = ("OFFLINE_SHOP_COLUMNS", "OFFLINE_SHOP_ROWS_PER_PAGE", "OFFLINE_SHOP_PAGE_COUNT",
                   "OFFLINE_SHOP_SLOT_MAX", "OFFLINE_SHOP_SIGN_STYLE_MAX")


def _shop():
	import shop
	return shop


def _int(value, default=0):
	try:
		return int(value)
	except (TypeError, ValueError):
		return default


# --- CONFIG and the grid --------------------------------------------------------------------

def config():
	"""CONFIG as a dict: shop.GetConfig()'s keys over CONFIG_DEFAULTS (a missing or
	odd answer leaves the defaults)."""
	values = dict(CONFIG_DEFAULTS)
	values["models"] = list(CONFIG_DEFAULTS["models"])
	getter = getattr(_shop(), "GetConfig", None)
	found = getter() if callable(getter) else None
	if isinstance(found, dict):
		for key, value in found.items():
			if key == "models":
				values["models"] = [_int(vnum) for vnum in (value or ()) if _int(vnum)]
			elif key in values:
				values[key] = _int(value, values[key])
	return values


def is_enabled(cfg=None):
	return bool((cfg or config())["enabled"])


def geometry():
	"""(columns, rows per page, pages, slots per page, slot max): shop.OFFLINE_SHOP_*."""
	shop = _shop()
	cols = _int(getattr(shop, "OFFLINE_SHOP_COLUMNS", 0))
	rows = _int(getattr(shop, "OFFLINE_SHOP_ROWS_PER_PAGE", 0))
	pages = _int(getattr(shop, "OFFLINE_SHOP_PAGE_COUNT", 0))
	slot_max = _int(getattr(shop, "OFFLINE_SHOP_SLOT_MAX", 0))
	return cols, rows, pages, cols * rows, slot_max


def sign_style_max():
	return _int(getattr(_shop(), "OFFLINE_SHOP_SIGN_STYLE_MAX", 0))


def clamp_style(style):
	"""A style the client has no art for is drawn as 0 (L15)."""
	style = _int(style)
	return style if 0 <= style < sign_style_max() else 0


def global_slot(page, local):
	_, _, _, per_page, _ = geometry()
	return page * per_page + local


def page_of(slot):
	_, _, _, per_page, _ = geometry()
	return slot // per_page if per_page else 0


def builder_cell_count(cfg=None):
	"""The builder's cells: CONFIG's base rows of 10, at most one page (spec 3.8)."""
	cfg = cfg or config()
	cols, rows, _, _, _ = geometry()
	return cols * max(1, min(rows, _int(cfg["base_rows"])))


def can_expand(kits, cfg=None):
	"""Another kit is allowed: fewer than CONFIG's max kits (OLD shop.cpp:2333)."""
	cfg = cfg or config()
	return _int(kits) < _int(cfg["max_kits"])


def lock_rows(page, unlocked, expandable=True):
	"""{row: "next" | "locked"} of the page's rows past the unlocked slots (OLD
	uiShop.py:440-468): the first locked row of the shop is the clickable "next"
	row while another kit is allowed, every later one is dark."""
	cols, rows, _, per_page, _ = geometry()
	unlocked = max(0, _int(unlocked))
	result = {}
	if not cols:
		return result
	first_page, first_row = unlocked // per_page, (unlocked % per_page) // cols
	for row in range(rows):
		start = page * per_page + row * cols
		if start < unlocked:
			continue
		result[row] = "next" if (expandable and page == first_page and row == first_row) else "locked"
	return result


def is_slot_unlocked(slot, unlocked):
	return 0 <= slot < max(0, _int(unlocked))


# --- the owner panel ------------------------------------------------------------------------

def extend_days_max(seconds_left, cfg=None):
	"""The most days EXTEND takes now: the server's cap on the result,
	seconds_left + days x 86400 <= cap days (spec 3.4.5, SB-G2); 0 refuses."""
	cfg = cfg or config()
	room = _int(cfg["extend_cap_days"]) * SECONDS_PER_DAY - max(0, _int(seconds_left))
	return max(0, room // SECONDS_PER_DAY)


def extend_cost(days, cfg=None):
	cfg = cfg or config()
	return _int(days) * _int(cfg["extend_price_per_day"])


def money(amount):
	import localeInfo
	return localeInfo.NumberToMoneyString(_int(amount))


def renew_confirm_text(cfg=None):
	"""OLD's OFFLINE_SHOP_RENEW_CONFIRM with CONFIG's renew cost (o-cli bug 4)."""
	import uiScriptLocale
	cfg = cfg or config()
	return _format(uiScriptLocale.OFFLINE_SHOP_RENEW_CONFIRM, money(cfg["renew_cost"]))


def days_hours_minutes(seconds):
	seconds = max(0, _int(seconds))
	minutes = seconds // 60
	return minutes // (24 * 60), (minutes // 60) % 24, minutes % 60


def time_left_text(seconds):
	"""OLD's OFFLINE_SHOP_TIME_LEFT ("%d Day %02d Hour %02d Min"), 0 when expired."""
	import uiScriptLocale
	return _format(uiScriptLocale.OFFLINE_SHOP_TIME_LEFT, days_hours_minutes(seconds))


def _format(text, args):
	try:
		return text % args
	except (TypeError, ValueError):
		return text


def owner_panel():
	"""The owner panel MANAGE stored (spec 1.1: sign, channel, map, x, y, gold, locked,
	seconds left, kits, model, style, unlocked slots). Neither K nor the spec names
	a getter for the sign, the place and the time: this reads
	shop.GetOfflineShopInfo() (a dict keyed by MANAGE's field names, as GetConfig()
	is keyed by CONFIG's) and K's named getters for the rest."""
	shop = _shop()
	info = {"sign": "", "channel": 0, "map": 0, "x": 0, "y": 0, "seconds_left": 0, "kits": 0, "model_vnum": 0,
	        "style": 0, "gold": 0, "locked": 0, "unlocked_slots": 0}
	getter = getattr(shop, "GetOfflineShopInfo", None)
	found = getter() if callable(getter) else None
	if isinstance(found, dict):
		for key in info:
			if key in found:
				info[key] = found[key] if key == "sign" else _int(found[key])
	info["sign"] = info["sign"] if isinstance(info["sign"], str) else ""
	for key, name in (("gold", "GetGoldAmount"), ("locked", "IsLocked"), ("kits", "GetOfflineShopExpandCount"),
	                  ("unlocked_slots", "GetOfflineShopSlotCount")):
		value = getattr(shop, name, None)
		if callable(value):
			info[key] = _int(value())
	return info


def slot_item_id(slot):
	"""The listed item's own id (TOfflineShopItem.id), which BUY sends with the price so
	a raced edit answers SOLD_OUT. K names no getter for it (GetOfflineShopItemID is
	OLD's vnum getter): shop.GetOfflineShopItemUniqueID(slot), 0 without it."""
	getter = getattr(_shop(), "GetOfflineShopItemUniqueID", None)
	return _int(getter(slot)) if callable(getter) else 0


def is_slot_pending(slot):
	"""A slot held for a transfer (MANAGE flags bit 2), owner only."""
	getter = getattr(_shop(), "IsOfflineShopSlotPending", None)
	return bool(getter(slot)) if callable(getter) else False


def needs_buy_confirm(price):
	return _int(price) >= BUY_CONFIRM_MIN_PRICE


def cut(text, limit):
	"""OLD's title cut: past `limit` characters, limit - 3 and "..."."""
	text = text or ""
	return text if len(text) <= limit else text[:limit - 3] + "..."


# --- the results and the logs ---------------------------------------------------------------

def result_name(code):
	"""The EOfflineShopResult name of a code, by K's shop.OFFLINE_SHOP_RESULT_<NAME>."""
	shop = _shop()
	for name in RESULT_NAMES:
		value = getattr(shop, "OFFLINE_SHOP_RESULT_" + name, None)
		if isinstance(value, int) and value == _int(code, -1):
			return name
	return ""


def op_name(op):
	"""The EOfflineShopCG name of a RESULT's op: shop.OFFLINE_SHOP_OP_<NAME>, else K's numbering."""
	shop = _shop()
	op = _int(op, -1)
	for (index, name) in enumerate(OP_NAMES):
		value = getattr(shop, "OFFLINE_SHOP_OP_" + name, None)
		if (value if isinstance(value, int) else index) == op:
			return name
	return ""


def result_text(code, arg=0):
	"""localeInfo.OFFLINE_SHOP_RESULT_<NAME>; its %s, where it has one, takes str(arg) (a
	channel, days, a cost, TRANSFER_LOST's delivery id). An unknown code: ""."""
	import localeInfo
	name = result_name(code)
	if not name:
		return ""
	text = getattr(localeInfo, "OFFLINE_SHOP_RESULT_" + name, "")
	if not isinstance(text, str):
		return ""
	if "%s" in text:
		return _format(text, (str(arg),))
	return text


def is_result_ok(code):
	return result_name(code) == "OK"


def log_action_text(action):
	"""localeInfo.OFFLINE_SHOP_LOG_ACTION_<n>; an action without a key shows its number
	(o-cli bug 22: OLD raised KeyError)."""
	import localeInfo
	text = getattr(localeInfo, "OFFLINE_SHOP_LOG_ACTION_%d" % _int(action, -1), None)
	return text if isinstance(text, str) else str(action)


def log_date_text(timestamp):
	"""The row's time in the player's local time (OLD showed UTC, o-cli bug 22)."""
	try:
		return _time.strftime("%d-%m-%Y %H:%M", _time.localtime(_int(timestamp)))
	except (OverflowError, ValueError, OSError):
		return ""


def log_row(row):
	"""A LOGS row (time, action, other, vnum, count, amount), K's tuple, as
	{action, other, what, amount, date}: what is the item and its count, or the days of
	an ADD_TIME (OLD uiOfflineShopLog.py:182-197)."""
	row = tuple(row) + (0,) * 6
	stamp, action, other, vnum, count, amount = row[:6]
	what = "-"
	add_time = getattr(_shop(), "OFFLINE_SHOP_LOG_ACTION_ADD_TIME", None)
	if isinstance(add_time, int) and _int(action) == add_time:
		import localeInfo
		what = "%d %s" % (_int(count), localeInfo.DAY)
	elif _int(vnum):
		import item
		item.SelectItem(_int(vnum))
		what = "%s (x%d)" % (item.GetItemName(), _int(count))
	return {"action": log_action_text(action), "other": other if isinstance(other, str) else "", "what": what,
	        "amount": _int(amount), "date": log_date_text(stamp)}


# --- the search -----------------------------------------------------------------------------

def search_cooldown_sec(cfg=None):
	cfg = cfg or config()
	return max(0, _int(cfg["search_cooldown_ms"])) / 1000.0


def can_search_buy():
	"""Buying from the search needs the premium perk (NOVA-9 Q2 a, P4): the same perk
	drives the label and the gate (PB-C6)."""
	import player
	perk = getattr(player, "PREMIUM_PERK_SEARCH_BUY", None)
	has = getattr(player, "HasPremiumPerk", None)
	if not isinstance(perk, int) or not callable(has):
		return False
	return bool(has(perk))


def premium_label():
	"""(text, color) of the search's premium status, from the buy perk: OLD's own
	SEARCH_SHOP_PREMIMUM_ACTIVE / _INACTIVE keys and colors (o-cli bug 8)."""
	import localeInfo
	if can_search_buy():
		return localeInfo.SEARCH_SHOP_PREMIMUM_ACTIVE, 0xff06a94d
	return localeInfo.SEARCH_SHOP_PREMIMUM_INACTIVE, 0xffb53737


def map_empire(map_index):
	"""The empire of a shop's map, 0 for a map with no flag (o-cli bug 7)."""
	return MAP_EMPIRE.get(_int(map_index), 0)


def flag_image(map_index):
	return EMPIRE_FLAG.get(map_empire(map_index), "")


def is_current_map(map_index):
	"""Whether a shop's map is the player's: then GOTO draws the arrow, else it warps."""
	import background
	name = MAP_NAME.get(_int(map_index))
	return bool(name) and name == background.GetCurrentMapName()


def search_row(row):
	"""A search result row as a dict: owner_pid, owner_name, channel, map, slot, id, vnum,
	count, price, sockets, attrs. Neither K nor the spec fixes the shape of
	searchShop.GetPage's rows (Y2's report): this takes a dict keyed by
	TShopSearchRow's field names (owner_pid, owner_name, channel, map, slot), with
	TOfflineShopItem's (id, vnum, count, price, sockets, attrs) flat, under "item", or
	under "slot" as a TOfflineShopSlot dict {"slot", "item"}; or OLD's list order
	[owner, name, vnum, price, count, slot, sockets, attrs, sold, id, map, channel]
	(OLD PythonSearchShopModule.cpp:146-190, with the owner PID for OLD's shop VID and
	the channel appended)."""
	keys = ("owner_pid", "owner_name", "channel", "map", "slot", "id", "vnum", "count", "price", "sockets", "attrs")
	result = dict.fromkeys(keys, 0)
	result.update({"owner_name": "", "sockets": (), "attrs": ()})
	if isinstance(row, dict):
		for key in keys:
			if key in row:
				result[key] = row[key]
		slot = row.get("slot")
		if isinstance(slot, dict):
			# TShopSearchRow.slot as a TOfflineShopSlot dict: {"slot": n, "item": {...}}
			result["slot"] = slot.get("slot", 0)
			row = slot
		item = row.get("item")
		if isinstance(item, dict):
			for key in ("id", "vnum", "count", "price", "sockets", "attrs"):
				if key in item:
					result[key] = item[key]
	elif isinstance(row, (list, tuple)):
		values = list(row) + [0] * 12
		(result["owner_pid"], result["owner_name"], result["vnum"], result["price"], result["count"], result["slot"],
		 result["sockets"], result["attrs"], _, result["id"], result["map"], result["channel"]) = values[:12]
	for key in ("owner_pid", "channel", "map", "slot", "id", "vnum", "count", "price"):
		result[key] = _int(result[key])
	result["owner_name"] = result["owner_name"] if isinstance(result["owner_name"], str) else ""
	result["sockets"] = tuple(result["sockets"] or ())
	result["attrs"] = tuple(result["attrs"] or ())
	return result


def search_target(entry):
	"""(vnum, skill) of an index entry (searchShop.Find, AutoComplete): a vnum, or a
	skill book's (vnum, skill)."""
	if isinstance(entry, (list, tuple)):
		values = list(entry) + [0, 0]
		return _int(values[0]), _int(values[1])
	return _int(entry), 0


def gender_filter(male, female):
	"""The QUERY gender of the filter's two toggles (OLD uiSearchShop.py:869-876)."""
	if male and female:
		return GENDER_BOTH
	if male:
		return GENDER_MALE
	if female:
		return GENDER_FEMALE
	return GENDER_NONE


def page_size(index):
	return SEARCH_PAGE_SIZES[index] if 0 <= index < len(SEARCH_PAGE_SIZES) else SEARCH_PAGE_SIZES[0]


# --- the signs ------------------------------------------------------------------------------

_seen = {}   # vid -> app.GetTime() of the last visit, kept while a sign comes and goes


def mark_seen(vid, now):
	_seen[vid] = now


def seen_at(vid):
	return _seen.get(vid, 0)


def is_seen(vid, now):
	stamp = _seen.get(vid)
	return stamp is not None and stamp + SIGN_SEEN_MINUTES * 60 > now


def forget_seen():
	_seen.clear()


def sign_display_count():
	"""OLD's "shops displayed" option when the exe has it, else its default 20."""
	import systemSetting
	getter = getattr(systemSetting, "GetNearbyShopsDisplayed", None)
	value = getter() if callable(getter) else None
	if isinstance(value, int) and not isinstance(value, bool) and value > 0:
		return min(value, SIGN_DISPLAY_COUNT_MAX)
	return SIGN_DISPLAY_COUNT


def nearest_signs(vids, distance_of, count, always=()):
	"""The signs that show: `always` (the player's own, the target, the hovered one),
	then the `count` nearest within SIGN_RANGE (OLD uiPrivateShopBuilder.py:83-130),
	the same rule for every style (o-cli bug 12)."""
	shown = [vid for vid in always if vid in vids]
	near = []
	for vid in vids:
		distance = distance_of(vid)
		# player.GetCharacterDistance answers -1 for a character that is not in view.
		if distance is None or distance < 0 or distance > SIGN_RANGE:
			continue
		near.append((distance, vid))
	near.sort(key=lambda pair: pair[0])
	for _, vid in near[:max(0, count)]:
		if vid not in shown:
			shown.append(vid)
	return shown


# --- the decoration ---------------------------------------------------------------------------

def read_shop_deco(lines):
	"""shop_deco.txt's rows (OLD playerSettingModule.py:2229-2252): type 1 a model
	"1<TAB>name<TAB>vnum", type 2 a sign style "2<TAB>name<TAB>pattern<TAB>0xRRGGBB",
	styles numbered from 1 in file order. ({vnum: name}, [(name, pattern, color)])."""
	models, styles = {}, []
	for line in lines:
		tokens = line.rstrip("\r\n").split("\t")
		if not tokens or not tokens[0] or tokens[0].startswith("#"):
			continue
		kind = _int(tokens[0], -1)
		if kind == 1 and len(tokens) >= 3 and _int(tokens[2]):
			models[_int(tokens[2])] = tokens[1]
		elif kind == 2 and len(tokens) >= 4:
			try:
				color = int(tokens[3], 16)
			except ValueError:
				color = 0xFFFFFF
			styles.append((tokens[1], tokens[2], color))
	return models, styles


_deco = []


def shop_deco():
	"""The locale's shop_deco.txt, read once ({vnum: name}, styles); a missing or bad
	file gives no names (the window falls back to the vnum)."""
	if _deco:
		return _deco[0]
	lines = []
	try:
		import app
		import builtins
		path = "%s/shop_deco.txt" % app.GetLocalePath()
		handle = (getattr(builtins, "pack_open", None) or open)(path, "r")
		try:
			lines = handle.readlines()
		finally:
			close = getattr(handle, "close", None)
			if callable(close):
				close()
	except Exception:
		lines = []
	_deco.append(read_shop_deco(lines))
	return _deco[0]


def forget_shop_deco():
	del _deco[:]


def deco_models(cfg=None):
	"""[(vnum, name)] of CONFIG's models, in CONFIG's order; a model without a row is
	named by its vnum."""
	cfg = cfg or config()
	names, _ = shop_deco()
	return [(vnum, names.get(vnum, str(vnum))) for vnum in cfg["models"]]


def deco_styles(cfg=None):
	"""[(style, name, pattern, color)] of the styles CONFIG allows: style 0 is the plain
	board (MYSHOP_DECO_DEFAULT), 1.. shop_deco.txt's rows."""
	import uiScriptLocale
	cfg = cfg or config()
	_, rows = shop_deco()
	count = max(1, min(_int(cfg["style_count"]), sign_style_max() or _int(cfg["style_count"])))
	styles = [(0, uiScriptLocale.MYSHOP_DECO_DEFAULT, "", 0xFFFFFF)]
	for index, (name, pattern, color) in enumerate(rows[:count - 1]):
		styles.append((index + 1, name, pattern, color))
	return styles


def style_pattern(style):
	"""(pattern, color) of a sign style (shop_deco.txt), ("", white) for 0 or unknown."""
	_, rows = shop_deco()
	style = clamp_style(style)
	if 1 <= style <= len(rows):
		_, pattern, color = rows[style - 1]
		return pattern, color
	return "", 0xFFFFFF
