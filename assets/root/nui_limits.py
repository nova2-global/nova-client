"""Every count and limit the NovaUI item windows use (Wave 3b, 3c), read once
from the client's module constants where the client has them, else today's
values; FOUNDATION holds the foundation wave's targets for fixtures and tests
(P14 spec 3). No window hard-codes a count.

A controller reads current() (never LIMITS directly), so a test can hand it
the foundation's sizes with use(foundation()) and put today's back with
use(None). Pure Python: nothing here runs per frame, and the module imports
outside the client (every game module missing means every value falls
back)."""

import sys

try:
	import dbg
except ImportError:  # plain Python outside the client
	dbg = None


class WearSlot(tuple):
	"""One wear position: (index, name, cell, group, w, h). cell is
	EQUIPMENT_SLOT_START + index, the inventory position the legacy windows
	refresh; group is "equipment", "costume" or "hidden" (the window that
	shows it, P14 spec 3.3); w and h are its span in cells."""

	__slots__ = ()

	def __new__(cls, index, name, cell, group, w=1, h=1):
		return tuple.__new__(cls, (int(index), str(name), int(cell), str(group), int(w), int(h)))

	index = property(lambda self: self[0])
	name = property(lambda self: self[1])
	cell = property(lambda self: self[2])
	group = property(lambda self: self[3])
	w = property(lambda self: self[4])
	h = property(lambda self: self[5])


# The wear tables in wear order: (name, group, w, h). NEW is today's
# (GameLib/ItemData.h EWearPositions, 24), grouped as the legacy windows show
# them (uiscript/inventorywindow.py, costumewindow.py: RING1 is the costume
# window's third slot, RING2 is commented out); OLD is the foundation's (OLD's
# common/length.h, 40 with the aura slot), grouped as OLD's windows show them.
_ABILITIES = tuple(("ability%d" % n, "hidden", 1, 1) for n in range(1, 9))
NEW_WEAR = (
	("body", "equipment", 1, 2), ("head", "equipment", 1, 1), ("foots", "equipment", 1, 1),
	("wrist", "equipment", 1, 1), ("weapon", "equipment", 1, 3), ("neck", "equipment", 1, 1),
	("ear", "equipment", 1, 1), ("unique1", "equipment", 1, 1), ("unique2", "equipment", 1, 1),
	("arrow", "equipment", 1, 1), ("shield", "equipment", 1, 1),
) + _ABILITIES + (
	("costume_body", "costume", 1, 2), ("costume_hair", "costume", 1, 1),
	("ring1", "costume", 1, 1), ("ring2", "hidden", 1, 1), ("belt", "equipment", 1, 1),
)
OLD_WEAR = (
	("body", "equipment", 1, 2), ("head", "equipment", 1, 1), ("foots", "equipment", 1, 1),
	("wrist", "equipment", 1, 1), ("weapon", "equipment", 1, 3), ("neck", "equipment", 1, 1),
	("ear", "equipment", 1, 1), ("unique1", "equipment", 1, 1), ("unique2", "equipment", 1, 1),
	("arrow", "equipment", 1, 1), ("shield", "equipment", 1, 1),
) + _ABILITIES + (
	("costume_body", "costume", 1, 2), ("costume_hair", "costume", 1, 1),
	("costume_sash", "equipment", 1, 1), ("costume_weapon", "costume", 1, 3),
	("costume_mount", "costume", 1, 1), ("effect_weapon", "costume", 1, 1),
	("effect_armor", "costume", 1, 1), ("costume_pet", "costume", 1, 1),
	("costume_sash2", "costume", 1, 1), ("ring1", "equipment", 1, 1), ("ring2", "equipment", 1, 1),
	("belt", "equipment", 1, 1), ("buffi_costume_body", "costume", 1, 2),
	("buffi_costume_hair", "costume", 1, 1), ("buffi_costume_weapon", "costume", 1, 3),
	("buffi_costume_sash2", "costume", 1, 1), ("buffi_costume_facial", "costume", 1, 1),
	("costume_facial", "costume", 1, 1), ("effect_weapon_1", "costume", 1, 1),
	("effect_armor_1", "costume", 1, 1), ("costume_aura", "costume", 1, 1),
)
WEAR_GROUPS = ("equipment", "costume", "hidden")
WEAR_NAMES = tuple(sorted(set(name for name, _, _, _ in NEW_WEAR + OLD_WEAR)))

# The roman numerals of the page tabs, as legacy writes them (literal "I", "II").
ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")

# 3.2's "today" column: the fallbacks. Derived keys are computed by read().
TODAY = {
	"INVENTORY_PAGE_COUNT": 2,
	"INVENTORY_PAGE_SIZE": 45,
	"INVENTORY_COLUMNS": 5,
	"INVENTORY_SLOT_COUNT": 168,
	"EQUIPMENT_SLOT_START": 90,
	"WEAR_SLOT_COUNT": 24,
	"COSTUME_SLOT_START": 109,
	"COSTUME_SLOT_COUNT": 2,
	"BELT_INVENTORY_SLOT_START": 152,
	"BELT_INVENTORY_SLOT_COUNT": 16,
	"BELT_COLUMNS": 4,
	"METIN_SOCKET_MAX_NUM": 3,
	"ATTRIBUTE_SLOT_MAX_NUM": 7,
	"ITEM_APPLY_MAX_NUM": 3,
	"ITEM_LIMIT_MAX_NUM": 2,
	"STACK_MAX": 200,
	"GOLD_MAX": 2000000000,
	"MONEY_DIGITS": 10,
	"INVENTORY_MONEY_DIGITS": 7,
	"SELECT_ITEM_MAX": 55,
	"SELECT_ITEM_COLUMNS": 5,
	"REFINE_ITEM_CELLS_MAX": 3,
	"SKILL_LEVEL_MAX": 40,
	"SKILL_GRADE_COUNT": 3,
	"SKILL_GRADE_SAGE": None,
	"PLAYER_LEVEL_MAX": 120,
	"DRAGON_SOUL_PAGE_SIZE": 32,
	"DRAGON_SOUL_PAGE_COUNT": 5,
	"DRAGON_SOUL_SLOT_COUNT": 960,
	"DRAGON_SOUL_EQUIPMENT_SLOT_START": 122,
	"DRAGON_SOUL_EQUIPMENT_PAGE_COUNT": 2,
	"DRAGON_SOUL_EQUIPMENT_FIRST_SIZE": 6,
	"QUICKSLOT_PAGE_COUNT": 4,
	"QUICKSLOT_PAGE_SIZE": 8,
	"CHARACTER_SLOT_COUNT": 4,
	# Wave 3c (P15 spec 3.1): the character window and the dragon soul windows.
	"SKILL_GRADE_STEP_COUNT": 20,
	"SKILL_ACTIVE_SLOTS": 8,
	"SKILL_SUPPORT_SLOTS": 12,
	"SKILL_SUPPORT_SLOT_START": 101,
	"SKILL_SUPPORT_COLUMNS": 6,
	"EXP_DIGITS": 10,
	"POINT_DIGITS": 3,
	"STAT_DIGITS": 3,
	"HP_DIGITS": 5,
	"QUEST_ROWS": 5,
	"EMOTE_COLUMNS": 6,
	"EMOTE_ROWS": 3,
	"EMOTE_SOLO_START": 1,
	"EMOTE_DUAL_START": 51,
	"DRAGON_SOUL_STEP_COUNT": 5,
	"DRAGON_SOUL_COLUMNS": 8,
	"DRAGON_SOUL_REFINE_CELLS": 15,
	"DRAGON_SOUL_REFINE_COLUMNS": 5,
	"DRAGON_SOUL_RESULT_CELLS": 6,
	"DRAGON_SOUL_RESULT_COLUMNS": 2,
	"DRAGON_SOUL_STRENGTH_MAX": 6,
}

# 3.2's "foundation" column ([PLAN], [RC]); never read at run time.
FOUNDATION = dict(TODAY)
FOUNDATION.update({
	"INVENTORY_PAGE_COUNT": 5,
	"INVENTORY_SLOT_COUNT": 311,
	"EQUIPMENT_SLOT_START": 225,
	"WEAR_SLOT_COUNT": 40,
	"COSTUME_SLOT_START": 244,
	"COSTUME_SLOT_COUNT": 11,
	"BELT_INVENTORY_SLOT_START": 295,
	"METIN_SOCKET_MAX_NUM": 4,
	"ITEM_APPLY_MAX_NUM": 7,
	"STACK_MAX": 2000,
	"GOLD_MAX": 2000000000000,
	"MONEY_DIGITS": 13,
	"INVENTORY_MONEY_DIGITS": 13,
	"SKILL_LEVEL_MAX": 50,
	"SKILL_GRADE_COUNT": 4,
	"SKILL_GRADE_SAGE": 4,
	"PLAYER_LEVEL_MAX": 150,
	"DRAGON_SOUL_EQUIPMENT_SLOT_START": 265,
	"CHARACTER_SLOT_COUNT": 5,
	# Wave 3c (P15 spec 3.1): 64-bit exp at level 150, six-digit HP.
	"EXP_DIGITS": 13,
	"HP_DIGITS": 6,
})

# Where each key comes from: (module, attribute) pairs, tried in order. A key
# without an entry (or whose names all miss) keeps TODAY's value. The names
# marked proposed are the ones the foundation wave's C2 was asked to expose
# (P14 spec 11); until it does they fall back.
NAMES = {
	"INVENTORY_PAGE_COUNT": (("player", "INVENTORY_PAGE_COUNT"),),
	"INVENTORY_PAGE_SIZE": (("player", "INVENTORY_PAGE_SIZE"),),
	"INVENTORY_COLUMNS": (("player", "INVENTORY_PAGE_COLUMNS"),),  # proposed
	"INVENTORY_SLOT_COUNT": (("player", "INVENTORY_SLOT_COUNT"),),
	"EQUIPMENT_SLOT_START": (("player", "EQUIPMENT_SLOT_START"),),
	"WEAR_SLOT_COUNT": (("item", "WEAR_MAX_NUM"), ("player", "WEAR_MAX_NUM")),  # proposed
	"COSTUME_SLOT_START": (("item", "COSTUME_SLOT_START"),),
	"COSTUME_SLOT_COUNT": (("item", "COSTUME_SLOT_COUNT"),),
	"BELT_INVENTORY_SLOT_START": (("item", "BELT_INVENTORY_SLOT_START"),),
	"BELT_INVENTORY_SLOT_COUNT": (("item", "BELT_INVENTORY_SLOT_COUNT"),),
	"BELT_COLUMNS": (("item", "BELT_INVENTORY_WIDTH"),),  # proposed
	"METIN_SOCKET_MAX_NUM": (("player", "METIN_SOCKET_MAX_NUM"), ("item", "ITEM_SOCKET_MAX_NUM")),
	"ATTRIBUTE_SLOT_MAX_NUM": (("player", "ATTRIBUTE_SLOT_MAX_NUM"),),
	"ITEM_APPLY_MAX_NUM": (("item", "ITEM_APPLY_MAX_NUM"),),
	"ITEM_LIMIT_MAX_NUM": (("item", "LIMIT_MAX_NUM"),),
	"STACK_MAX": (("item", "ITEM_COUNT_MAX"), ("player", "ITEM_COUNT_MAX")),  # proposed
	"GOLD_MAX": (("player", "GOLD_MAX"),),  # proposed
	"MONEY_DIGITS": (("player", "MONEY_DIGITS"),),  # C2's named money-digits constant
	"INVENTORY_MONEY_DIGITS": (("player", "MONEY_DIGITS"),),
	"SKILL_LEVEL_MAX": (("player", "SKILL_MAX_LEVEL"),),  # proposed
	"SKILL_GRADE_COUNT": (("skill", "SKILL_GRADE_COUNT"),),
	"SKILL_GRADE_SAGE": (("player", "SKILL_GRADE_SAGE_MASTER"),),
	"PLAYER_LEVEL_MAX": (("player", "PLAYER_MAX_LEVEL"),),  # proposed
	"DRAGON_SOUL_PAGE_SIZE": (("player", "DRAGON_SOUL_PAGE_SIZE"),),
	"DRAGON_SOUL_PAGE_COUNT": (("player", "DRAGON_SOUL_PAGE_COUNT"),),
	"DRAGON_SOUL_SLOT_COUNT": (("player", "DRAGON_SOUL_SLOT_COUNT"),),
	"DRAGON_SOUL_EQUIPMENT_SLOT_START": (("player", "DRAGON_SOUL_EQUIPMENT_SLOT_START"),),
	"DRAGON_SOUL_EQUIPMENT_PAGE_COUNT": (("player", "DRAGON_SOUL_EQUIPMENT_PAGE_COUNT"),),
	"DRAGON_SOUL_EQUIPMENT_FIRST_SIZE": (("player", "DRAGON_SOUL_EQUIPMENT_FIRST_SIZE"),),
	"CHARACTER_SLOT_COUNT": (("introselect", "SLOT_COUNT"),),
	# The wear table: item.WEAR_<NAME> for every name of a table (proposed).
	"WEAR_TABLE": tuple(("item", "WEAR_" + name.upper()) for name in WEAR_NAMES),
	# Wave 3c (P15 spec 3.1). uiCharacter.CharacterWindow is the class, which
	# _modules() lists only when the client loaded uiCharacter already.
	"SKILL_GRADE_STEP_COUNT": (("skill", "SKILL_GRADE_STEP_COUNT"),),
	"SKILL_ACTIVE_SLOTS": (("uiCharacter.CharacterWindow", "ACTIVE_PAGE_SLOT_COUNT"),),
	"SKILL_SUPPORT_SLOTS": (("uiCharacter.CharacterWindow", "SUPPORT_PAGE_SLOT_COUNT"),),
	"EXP_DIGITS": (("player", "EXP_DIGITS"),),  # proposed
	"HP_DIGITS": (("player", "HP_DIGITS"),),  # proposed (the cut's widest HP)
	"QUEST_ROWS": (("quest", "QUEST_MAX_NUM"),),
	"DRAGON_SOUL_STEP_COUNT": (("player", "DRAGON_SOUL_STEP_COUNT"),),  # proposed
}

# Keys read() computes after the others.
DERIVED = ("INVENTORY_ROWS", "STACK_DIGITS", "SELECT_ITEM_SCAN", "WEAR_TABLE", "WEAR_TABLE_ID")
# Wave 3c (P15 spec 3.1).
DERIVED += ("SKILL_GRADE_COLUMNS", "SKILL_LABELS", "DRAGON_SOUL_KIND_COUNT", "DRAGON_SOUL_ROWS", "DRAGON_SOUL_FEE_DIGITS")
# The modules read() imports itself (each optional); introselect is only read
# when the client imported it already (a login-phase module).
_IMPORTED = ("player", "item", "skill", "app")


class Limits(object):
	"""Read-only values; see NAMES for where each comes from. Every key of
	TODAY and DERIVED is an attribute; `fell_back` lists the keys that took
	their fallback."""

	def __init__(self, values, fell_back=()):
		object.__setattr__(self, "_values", dict(values))
		object.__setattr__(self, "fell_back", tuple(fell_back))

	def __getattr__(self, name):
		values = object.__getattribute__(self, "_values")
		if name in values:
			return values[name]
		raise AttributeError(name)

	def __setattr__(self, name, value):
		raise AttributeError("nui_limits.Limits is read-only")

	def as_dict(self):
		return dict(object.__getattribute__(self, "_values"))

	def __eq__(self, other):
		return isinstance(other, Limits) and self.as_dict() == other.as_dict()

	def __ne__(self, other):
		return not self == other

	def __hash__(self):
		return id(self)

	def __repr__(self):
		return "Limits(%s)" % self.WEAR_TABLE_ID


def _modules():
	"""The game modules read() looks in: each of _IMPORTED that imports, and
	introselect when it is loaded already."""
	found = {}
	for name in _IMPORTED:
		module = sys.modules.get(name)
		if module is None:
			try:
				module = __import__(name)
			except Exception:
				module = None
		if module is not None:
			found[name] = module
	if sys.modules.get("introselect") is not None:
		found["introselect"] = sys.modules["introselect"]
	# Wave 3c (P15 spec 3.1): these too only when the client loaded them.
	for name in ("quest", "uiCharacter", "dragon_soul_refine_settings"):
		if sys.modules.get(name) is not None:
			found[name] = sys.modules[name]
	character = getattr(found.get("uiCharacter"), "CharacterWindow", None)
	if character is not None:
		found["uiCharacter.CharacterWindow"] = character
	return found


def _int_of(modules, module_name, attribute):
	"""The int constant module.attribute, or None (a missing module or name,
	or a value that is not an int)."""
	module = modules.get(module_name)
	if module is None:
		return None
	try:
		value = getattr(module, attribute)
	except Exception:
		return None
	if isinstance(value, bool) or not isinstance(value, int):
		return None
	return value


def _wear_entries(table, start, constants):
	"""The WearSlots of `table` ((name, group, w, h) in wear order), with each
	index from `constants` (name -> index) where it holds the name, else the
	table's position."""
	slots = []
	for position, (name, group, w, h) in enumerate(table):
		index = constants.get(name, position)
		slots.append(WearSlot(index, name, start + index, group, w, h))
	return tuple(sorted(slots, key=lambda slot: slot.index))


def _wear_table(values, constants):
	"""(table id, the WearSlots): OLD's 40 when the count is 40 and every OLD
	name resolves, else today's 24."""
	start = values["EQUIPMENT_SLOT_START"]
	old_names = [name for name, _, _, _ in OLD_WEAR]
	if values["WEAR_SLOT_COUNT"] == len(OLD_WEAR) and all(name in constants for name in old_names):
		return "old", _wear_entries(OLD_WEAR, start, constants)
	return "new", _wear_entries(NEW_WEAR, start, constants)


def _derive(values, constants, foundation=False):
	values["INVENTORY_ROWS"] = values["INVENTORY_PAGE_SIZE"] // max(1, values["INVENTORY_COLUMNS"])
	values["STACK_DIGITS"] = len(str(values["STACK_MAX"]))
	values["SELECT_ITEM_SCAN"] = values["INVENTORY_PAGE_SIZE"] * values["INVENTORY_PAGE_COUNT"]
	if foundation:
		table_id, table = "old", _wear_entries(OLD_WEAR, values["EQUIPMENT_SLOT_START"], {})
	else:
		table_id, table = _wear_table(values, constants)
	values["WEAR_TABLE_ID"] = table_id
	values["WEAR_TABLE"] = table
	# Wave 3c (P15 spec 3.1, D19): the sage grade takes no column of its own
	# (OLD's uiscript keeps three), and turns on OLD's over-P count labels.
	sage = values["SKILL_GRADE_SAGE"] is not None
	values["SKILL_GRADE_COLUMNS"] = values["SKILL_GRADE_COUNT"] - (1 if sage else 0)
	values["SKILL_LABELS"] = "over_p" if sage else "p"
	values["DRAGON_SOUL_KIND_COUNT"] = values["DRAGON_SOUL_SLOT_COUNT"] // max(
		1, values["DRAGON_SOUL_PAGE_COUNT"] * values["DRAGON_SOUL_PAGE_SIZE"])
	values["DRAGON_SOUL_ROWS"] = values["DRAGON_SOUL_PAGE_SIZE"] // max(1, values["DRAGON_SOUL_COLUMNS"])
	values["DRAGON_SOUL_FEE_DIGITS"] = values["MONEY_DIGITS"]
	return values


# Wave 3c (P15 spec 3.1): read() calls it at import, so it comes first.
def _strength_max(modules):
	"""The largest entry of dragon_soul_refine_settings.default_strength_max_table
	(a dragon soul's strength by grade and step), or None when the module is
	not in `modules` or its table holds no int."""
	settings = modules.get("dragon_soul_refine_settings")
	try:
		table = getattr(settings, "default_strength_max_table")
		found = [int(value) for row in table for value in row
		         if isinstance(value, int) and not isinstance(value, bool)]
	except Exception:
		return None
	return max(found) if found else None


def read(modules=None):
	"""A Limits from the constants: for each key the first (module, attribute)
	of NAMES that exists and is an int (a tuple of names for WEAR_TABLE, 3.3),
	else TODAY's value. `modules` maps module names to objects (tests); None
	imports player, item, skill and app, each optional. Derived keys
	(INVENTORY_ROWS, STACK_DIGITS, MONEY_DIGITS, the wear table) are computed
	after. Logs once to log.txt which keys fell back (dbg.Tracen). Never
	raises: a module that imports but lacks a name falls back for that key
	alone."""
	log = modules is None
	if modules is None:
		modules = _modules()
	values = {}
	fell_back = []
	for key, fallback in TODAY.items():
		value = None
		for module_name, attribute in NAMES.get(key, ()):
			value = _int_of(modules, module_name, attribute)
			if value is not None:
				break
		if value is None:
			value = fallback
			if key in NAMES:
				fell_back.append(key)
		values[key] = value
	# MONEY_DIGITS without C2's constant: the digits of GOLD_MAX.
	if "MONEY_DIGITS" in fell_back:
		values["MONEY_DIGITS"] = len(str(values["GOLD_MAX"]))
	# Wave 3c: the refine settings' largest strength, when the client loaded them.
	strength = _strength_max(modules)
	if strength is not None:
		values["DRAGON_SOUL_STRENGTH_MAX"] = strength
	constants = {}
	for name in WEAR_NAMES:
		index = _int_of(modules, "item", "WEAR_" + name.upper())
		if index is not None:
			constants[name] = index
	if len(constants) < len(NEW_WEAR):
		fell_back.append("WEAR_TABLE")
	_derive(values, constants)
	limits = Limits(values, fell_back)
	if log and dbg is not None and fell_back:
		dbg.Tracen("nui_limits: today's values for %s" % ", ".join(fell_back))
	return limits


def foundation():
	"""A Limits from FOUNDATION, for fixtures, goldens and tests only."""
	return Limits(_derive(dict(FOUNDATION), {}, foundation=True))


LIMITS = read()        # at import, once per client run
_current = [None]


def use(limits):
	"""Hands every controller these limits (tests: foundation(), or a read()
	over stand-ins); use(None) restores LIMITS."""
	_current[0] = limits


def current():
	"""The limits the controllers read: use()'s, else LIMITS."""
	return _current[0] if _current[0] is not None else LIMITS


def table_id(limits=None):
	""""new" (today's 24) or "old" (the foundation's 40): the classic sheets'
	body class (inv--table-new, inv--table-old)."""
	return (limits or current()).WEAR_TABLE_ID


def wear_table(limits=None):
	"""The wear slots in the client's wear order: a tuple of WearSlot
	(index, name, cell, group, w, h), cell = EQUIPMENT_SLOT_START + index;
	group "equipment", "costume" or "hidden" (3.3)."""
	return (limits or current()).WEAR_TABLE


def wear_group(group, limits=None):
	"""The WearSlots of one group, in wear order."""
	if group not in WEAR_GROUPS:
		raise ValueError("nui_limits.wear_group(): group is one of %s, not %r" % (", ".join(WEAR_GROUPS), group))
	return tuple(slot for slot in wear_table(limits) if slot.group == group)


def pages(limits=None):
	"""The page tabs: [{"index": i, "label": "I".."X", "hint":
	"@ui.INVENTORY_PAGE_BUTTON_TOOLTIP_<i+1>"}] for i < INVENTORY_PAGE_COUNT
	(labels are Roman numerals, as legacy writes them)."""
	count = (limits or current()).INVENTORY_PAGE_COUNT
	return [{"index": i, "label": ROMAN[i] if i < len(ROMAN) else str(i + 1),
	         "hint": "@ui.INVENTORY_PAGE_BUTTON_TOOLTIP_%d" % (i + 1)} for i in range(count)]


def money_text(value):
	"""localeInfo.NumberToMoneyString(int(value)): Python ints, so 64-bit gold
	formats."""
	import localeInfo
	return localeInfo.NumberToMoneyString(int(value))


# --- Wave 3c (P15) ---

def skill_active_slots(limits=None):
	"""The active skill grid's legacy slot numbers in the uiscript's order
	(uiscript/characterwindow.py Skill_Active_Slot): two blocks of
	SKILL_ACTIVE_SLOTS // 2 rows, odd slots left and even right, each row the
	slot and its grade columns SKILL_GRADE_STEP_COUNT apart. Today 1, 21, 41,
	3, 23, 43, ... 8, 28, 48."""
	limits = limits or current()
	step = limits.SKILL_GRADE_STEP_COUNT
	slots = []
	for first in (1, 2):
		for row in range(limits.SKILL_ACTIVE_SLOTS // 2):
			slot = first + 2 * row
			slots.extend(slot + column * step for column in range(limits.SKILL_GRADE_COLUMNS))
	return slots


def emote_slots(kind, limits=None):
	"""The emote grid's slot numbers: "solo" from EMOTE_SOLO_START, "dual"
	from EMOTE_DUAL_START, EMOTE_COLUMNS x EMOTE_ROWS each (ValueError for
	another kind)."""
	limits = limits or current()
	starts = {"solo": limits.EMOTE_SOLO_START, "dual": limits.EMOTE_DUAL_START}
	if kind not in starts:
		raise ValueError("nui_limits.emote_slots(): kind is solo or dual, not %r" % (kind,))
	return list(range(starts[kind], starts[kind] + limits.EMOTE_COLUMNS * limits.EMOTE_ROWS))


def dragon_soul_page(vnum):
	"""(kind, grade, step, strength) of a dragon soul from its vnum's digits,
	as the refine window decodes them (uidragonsoul.py
	__GetDragonSoulTypeInfo: the vnum is FEDCBA, FE the type, 11 to 16, D the
	grade, C the step, B the strength), kind being the type less 11 (the
	window's DSKindIndex); None for a vnum under 110000."""
	vnum = int(vnum)
	if vnum < 110000:
		return None
	return (vnum // 10000 - 11, vnum % 10000 // 1000, vnum % 1000 // 100, vnum % 100 // 10)
