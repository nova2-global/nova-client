#!/usr/bin/env python3
"""The tooltip parity corpus (P14 spec 5.8): items, skills and cases that run
every live rule of assets/root/uitooltip.py, in every context it builds a
tooltip in, for the parity test (tools/nui_tooltip_test.py) and the kit's
in-client comparison (TP-N, which stages tools/fixtures/tooltip_corpus.json).

    python3 tools/nui_tooltip_corpus.py corpus [--check]     the corpus and the branch list
    python3 tools/nui_tooltip_corpus.py fixtures [--check]   the tooltip and dialog fixtures
    python3 tools/nui_tooltip_corpus.py coverage             the rule lines no case runs
    python3 tools/nui_tooltip_corpus.py report [--out PATH]  the offline parity report (spec 5.8)

The corpus is made from the server's item proto and names (read-only; the
client's packed locale/en/item_proto is the same data) and the client's
item list (icons) and item descriptions, by these rules: for every
(type, subtype) the proto has, its lowest vnum and the lowest of each size;
every vnum the rules name (the money pouch, the skill and forget books, the
polymorph marbles, the warp scrolls, the detectors, the auto potions, one
of each hair range); per type, one item of each limit kind; each anti-flag
combination of jobs, sexes and ANTI_SELL; an item of each apply the proto
uses; a long description and none. Items the rules name that the proto
lacks are made here and marked "synthetic". The instance states (sockets,
attributes, the player, the clock, the shop) and the contexts are the
cases below; the output is deterministic, and its header holds the sha256
of every input.

tools/fixtures/tooltip_branches.json lists the live rule lines of
uitooltip.py (every statement of the live methods of spec 5.1, without the
dead ones of spec 2.1, and the lines excluded with a reason): the parity
test traces uitooltip.py over the whole corpus and fails while a listed
line never runs.

The harness below (TipWorld, run_case, stand_in_rows) is what the test and
the fixture writer share: one stand-in client per side, the legacy rules
alone (uiToolTip's widgets the stand-ins') or with the recorder and the
facades."""
import argparse
import ast
import contextlib
import hashlib
import io
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import nui_game_support as support  # noqa: E402

SERVER = "/home/eddy/new-project/new/nova-server-nui-rt/share/conf"
DEFAULT_PROTO = os.path.join(SERVER, "item_proto.txt")
DEFAULT_NAMES = os.path.join(SERVER, "item_names.txt")
DEFAULT_MOBS = os.path.join(SERVER, "mob_names.txt")
LOCALE = os.path.join(REPO, "assets", "locale", "locale")
ITEM_LIST = os.path.join(LOCALE, "common", "item_list.txt")
ITEM_DESC = os.path.join(LOCALE, "en", "itemdesc.txt")
SKILL_DESC = os.path.join(LOCALE, "en", "skilldesc.txt")
RULES = os.path.join(REPO, "assets", "root", "uitooltip.py")
CORPUS = os.path.join(HERE, "fixtures", "tooltip_corpus.json")
BRANCHES = os.path.join(HERE, "fixtures", "tooltip_branches.json")
WINDOWS = os.path.join(REPO, "assets", "nui", "nui", "windows")

# --- the client's enums the proto's names map onto (src/GameLib/ItemData.h) -------------------

ITEM_TYPES = ("NONE", "WEAPON", "ARMOR", "USE", "AUTOUSE", "MATERIAL", "SPECIAL", "TOOL", "LOTTERY", "ELK", "METIN",
              "CONTAINER", "FISH", "ROD", "RESOURCE", "CAMPFIRE", "UNIQUE", "SKILLBOOK", "QUEST", "POLYMORPH",
              "TREASURE_BOX", "TREASURE_KEY", "SKILLFORGET", "GIFTBOX", "PICK", "HAIR", "TOTEM", "BLEND", "COSTUME",
              "DS", "SPECIAL_DS", "EXTRACT", "SECONDARY_COIN", "RING", "BELT")   # EItemType, ItemData.h:23-61
SUB_TYPES = {
    "WEAPON": ("WEAPON_SWORD", "WEAPON_DAGGER", "WEAPON_BOW", "WEAPON_TWO_HANDED", "WEAPON_BELL", "WEAPON_FAN",
               "WEAPON_ARROW"),                                                      # :64-76
    "MATERIAL": ("MATERIAL_LEATHER", "MATERIAL_BLOOD", "MATERIAL_ROOT", "MATERIAL_NEEDLE", "MATERIAL_JEWEL",
                 "MATERIAL_DS_REFINE_NORMAL", "MATERIAL_DS_REFINE_BLESSED", "MATERIAL_DS_REFINE_HOLLY"),  # :78-88
    "ARMOR": ("ARMOR_BODY", "ARMOR_HEAD", "ARMOR_SHIELD", "ARMOR_WRIST", "ARMOR_FOOTS", "ARMOR_NECK", "ARMOR_EAR"),
    "COSTUME": ("COSTUME_BODY", "COSTUME_HAIR"),
    "USE": ("USE_POTION", "USE_TALISMAN", "USE_TUNING", "USE_MOVE", "USE_TREASURE_BOX", "USE_MONEYBAG", "USE_BAIT",
            "USE_ABILITY_UP", "USE_AFFECT", "USE_CREATE_STONE", "USE_SPECIAL", "USE_POTION_NODELAY", "USE_CLEAR",
            "USE_INVISIBILITY", "USE_DETACHMENT", "USE_BUCKET", "USE_POTION_CONTINUE", "USE_CLEAN_SOCKET",
            "USE_CHANGE_ATTRIBUTE", "USE_ADD_ATTRIBUTE", "USE_ADD_ACCESSORY_SOCKET", "USE_PUT_INTO_ACCESSORY_SOCKET",
            "USE_ADD_ATTRIBUTE2", "USE_RECIPE", "USE_CHANGE_ATTRIBUTE2", "USE_BIND", "USE_UNBIND",
            "USE_TIME_CHARGE_PER", "USE_TIME_CHARGE_FIX", "USE_PUT_INTO_BELT_SOCKET", "USE_PUT_INTO_RING_SOCKET"),
    "DS": ("DS_SLOT1", "DS_SLOT2", "DS_SLOT3", "DS_SLOT4", "DS_SLOT5", "DS_SLOT6"),
    "METIN": ("METIN_NORMAL", "METIN_GOLD"),
}
ANTI_FLAGS = {"ANTI_FEMALE": 1 << 0, "ANTI_MALE": 1 << 1, "ANTI_MUSA": 1 << 2, "ANTI_ASSASSIN": 1 << 3,
              "ANTI_SURA": 1 << 4, "ANTI_MUDANG": 1 << 5, "ANTI_GET": 1 << 6, "ANTI_DROP": 1 << 7, "ANTI_SELL": 1 << 8,
              "ANTI_EMPIRE_A": 1 << 9, "ANTI_EMPIRE_B": 1 << 10, "ANTI_EMPIRE_C": 1 << 11, "ANTI_SAVE": 1 << 12,
              "ANTI_GIVE": 1 << 13, "ANTI_PKDROP": 1 << 14, "ANTI_STACK": 1 << 15, "ANTI_MYSHOP": 1 << 16}  # :187-206
FLAGS = {"ITEM_TUNABLE": 1 << 0, "ITEM_SAVE": 1 << 1, "ITEM_STACKABLE": 1 << 2, "STACKABLE": 1 << 2,
         "COUNT_PER_1GOLD": 1 << 3, "ITEM_SLOW_QUERY": 1 << 4, "ITEM_UNIQUE": 1 << 6, "ITEM_MAKECOUNT": 1 << 7,
         "ITEM_IRREMOVABLE": 1 << 8, "CONFIRM_WHEN_USE": 1 << 9, "QUEST_USE": 1 << 10, "QUEST_USE_MULTIPLE": 1 << 11,
         "LOG": 1 << 13, "ITEM_APPLICABLE": 1 << 14}                                     # :208-225
WEARS = {"WEAR_BODY": 1 << 0, "WEAR_HEAD": 1 << 1, "WEAR_FOOTS": 1 << 2, "WEAR_WRIST": 1 << 3, "WEAR_WEAPON": 1 << 4,
         "WEAR_NECK": 1 << 5, "WEAR_EAR": 1 << 6, "WEAR_UNIQUE": 1 << 7, "WEAR_SHIELD": 1 << 8, "WEAR_ARROW": 1 << 9,
         "WEAR_HAIR": 1 << 10, "WEAR_ABILITY": 1 << 11, "WEAR_COSTUME_BODY": 1 << 12, "WEAR_COSTUME_HAIR": 1 << 13,
         "WEAR_BELT": 1 << 14}                                                           # :259-276
LIMITS = {"LIMIT_NONE": 0, "LEVEL": 1, "STR": 2, "DEX": 3, "INT": 4, "CON": 5, "PC_BANG": 6, "REAL_TIME": 7,
          "REAL_TIME_FIRST_USE": 8, "TIMER_BASED_ON_WEAR": 9}                              # :161-185
# Constants the rules compare with (constinfo.py, uitooltip.py).
ERROR_METIN_STONE = 28960
SILVER, GOLD = 1, 2
CLOCK = 1700000000
DAY = 24 * 3600

# --- reading the inputs ---------------------------------------------------------------------------


def sha256_of(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _is_vnum(cell):
    cell = cell.strip()
    if "~" in cell:
        low, _, high = cell.partition("~")
        return low.strip().isdigit() and high.strip().isdigit()
    return cell.isdigit()


def read_table(path):
    """Tab-separated rows, the header and blank lines left out (a vnum may be
    a range, "110000~110099", as the proto's dragon soul rows are)."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        rows = [line.rstrip("\r\n").split("\t") for line in handle]
    return [row for row in rows if row and _is_vnum(row[0])]


def _tokens(text):
    return [token.strip() for token in (text or "").split("|") if token.strip() and token.strip() != "NONE"]


def _bits(text, table):
    value = 0
    for token in _tokens(text):
        value |= table.get(token, 0)
    return value


def _subtype(kind, name):
    names = SUB_TYPES.get(kind, ())
    if name in names:
        return names.index(name)
    if name.isdigit():
        return int(name)
    return len(names)   # a subtype only the server knows (WEAPON_MOUNT_SPEAR): no rule compares it


def proto_rows(path):
    """{vnum: row} of the item proto in the corpus row schema (P14 spec 9.6)."""
    rows = {}
    for cells in read_table(path):
        if len(cells) < 32:
            continue
        low, _, high = cells[0].strip().partition("~")
        vnum = int(low)
        kind = cells[2].strip()
        kind = kind[5:] if kind.startswith("ITEM_") else kind
        limits = [[LIMITS.get(cells[14].strip(), 0), int(cells[15] or 0)],
                  [LIMITS.get(cells[16].strip(), 0), int(cells[17] or 0)]]
        applies = [[cells[18].strip(), int(cells[19] or 0)], [cells[20].strip(), int(cells[21] or 0)],
                   [cells[22].strip(), int(cells[23] or 0)]]
        row = {
            "name": cells[1].strip(),
            "type": ITEM_TYPES.index(kind) if kind in ITEM_TYPES else 0,
            "type_name": kind,
            "subtype": _subtype(kind, cells[3].strip()),
            "subtype_name": cells[3].strip(),
            "size": [1, int(cells[4] or 1)],
            "antiflags": _bits(cells[5], ANTI_FLAGS),
            "flags": _bits(cells[6], FLAGS),
            "wear": _bits(cells[7], WEARS),
            "limits": limits,
            "applies": [a for a in applies if a[0] != "APPLY_NONE"],
            "values": [int(v or 0) for v in cells[24:30]],
            "sockets": int(cells[31] or 0),
            "price": {"buy": int(cells[9] or 0), "sell": int(cells[10] or 0)},
            "refine": int(cells[11] or 0),
        }
        if kind == "USE":
            row["use_type"] = cells[3].strip()
        if high:
            row["range"] = [vnum, int(high)]
        rows[vnum] = row
    return rows


# Dragon soul stones in their vnum ranges (the client finds a range's row for
# any vnum in it): the step digit (vnum // 100 % 10) 0 to 4 with a refine digit
# (vnum // 10 % 10) each, as __DragonSoulInfoString reads them.
DS_VNUMS = (110000, 110130, 110250, 110370, 110490)


def expand_ranges(rows):
    """The rows with a row for every DS_VNUMS vnum inside a range."""
    for vnum in DS_VNUMS:
        if vnum in rows:
            continue
        for start, row in sorted(rows.items()):
            span = row.get("range")
            if span and span[0] <= vnum <= span[1]:
                rows[vnum] = dict(row, range=None)
                break
    return rows


def _first_vnum(cell):
    return int(cell.strip().partition("~")[0])


def _spread(table, rows):
    """A ranged row's value for each DS_VNUMS vnum in its range."""
    for (low, high), value in rows:
        for vnum in DS_VNUMS:
            if low <= vnum <= high:
                table.setdefault(vnum, value)
    return table


def _ranged(path, column):
    plain, ranged = {}, []
    for cells in read_table(path):
        if len(cells) <= column:
            continue
        low, _, high = cells[0].strip().partition("~")
        plain[int(low)] = cells[column].strip()
        if high:
            ranged.append(((int(low), int(high)), cells[column].strip()))
    return _spread(plain, ranged)


def names_of(path):
    return _ranged(path, 1)


def icons_of(path):
    return _ranged(path, 2)


def descriptions_of(path):
    found = {}
    for cells in read_table(path):
        if len(cells) >= 3:
            found[_first_vnum(cells[0])] = (cells[2].strip(), cells[3].strip() if len(cells) >= 4 else "")
    return found


def skill_names_of(path):
    found = {}
    for cells in read_table(path):
        if len(cells) >= 6:
            names = [name.strip() for name in cells[2:5] if name.strip()]
            conditions = [text.strip() for text in cells[6:9] if text.strip()]
            found[int(cells[0])] = {"names": names or [cells[2].strip()], "desc": cells[5].strip(),
                                    "conditions": conditions}
    return found


# --- choosing the items (spec 5.8) -------------------------------------------------------------

NAMED_VNUMS = (50026, 50300, 70037, 70055, 70103, 70104, 70105, 70106, 22000, 22010, 22011, 27989, 76006, 50004,
               72723, 72724, 72725, 72726, 72727, 72728, 72729, 72730, 76004, 76005, 76021, 76022)
# The kit's items (spec 2.4), which the in-game checks hover.
KIT_VNUMS = (10, 3000, 11200, 12200, 18000, 27001, 28030, 25040, 30329, 73001, 73002, 73003, 73004, 73005)
# The socket materials the accessory and belt rules look up (constinfo.py
# ACCESSORY_MATERIAL_LIST, JewelAccessoryInfos, GET_BELT_MATERIAL_VNUM).
MATERIAL_VNUMS = tuple(range(50623, 50639)) + (18900,)
# One of each hair range (uitooltip.py __IsHair, :1414-1439): old, new, new 2, new 3 (both
# kinds of range), costume hair (new 3 + 100000).
HAIR_PICKS = ((73001, 73999), (74001, 74011), (75001, 75999), (74013, 74021), (45001, 46999), (174013, 174021),
              (145001, 146999))


def choose_items(rows):
    """The vnums of spec 5.8's item rules, each with the reasons it was chosen."""
    chosen = {}

    def pick(vnum, why):
        chosen.setdefault(vnum, []).append(why)

    by_kind = {}
    for vnum in sorted(rows):
        row = rows[vnum]
        key = (row["type_name"], row["subtype_name"])
        by_kind.setdefault(key, []).append(vnum)
    for key, vnums in sorted(by_kind.items()):
        pick(vnums[0], "lowest of %s/%s" % key)
        sizes = {}
        for vnum in vnums:
            sizes.setdefault(rows[vnum]["size"][1], vnum)
        for size, vnum in sorted(sizes.items()):
            pick(vnum, "lowest of %s/%s size %d" % (key + (size,)))
    for vnum in NAMED_VNUMS:
        pick(vnum, "named by the rules")
    for vnum in KIT_VNUMS:
        if vnum in rows:
            pick(vnum, "one of the kit's items (spec 2.4)")
    for vnum in MATERIAL_VNUMS:
        if vnum in rows:
            pick(vnum, "a socket material the rules look up")
    for vnum in DS_VNUMS:
        if vnum in rows:
            pick(vnum, "a dragon soul step and refine digit")
    for low, high in HAIR_PICKS:
        in_range = [v for v in sorted(rows) if low <= v <= high]
        pick(in_range[0] if in_range else low, "hair range %d-%d" % (low, high))
    limit_kinds = {}
    for vnum in sorted(rows):
        for kind, value in rows[vnum]["limits"]:
            if kind:
                limit_kinds.setdefault((rows[vnum]["type_name"], kind), vnum)
    for (type_name, kind), vnum in sorted(limit_kinds.items()):
        pick(vnum, "%s with limit %d" % (type_name, kind))
    masks = {}
    relevant = ANTI_FLAGS["ANTI_FEMALE"] | ANTI_FLAGS["ANTI_MALE"] | ANTI_FLAGS["ANTI_MUSA"] | \
        ANTI_FLAGS["ANTI_ASSASSIN"] | ANTI_FLAGS["ANTI_SURA"] | ANTI_FLAGS["ANTI_MUDANG"] | ANTI_FLAGS["ANTI_SELL"]
    for vnum in sorted(rows):
        masks.setdefault(rows[vnum]["antiflags"] & relevant, vnum)
    for mask, vnum in sorted(masks.items()):
        pick(vnum, "anti-flags 0x%x" % mask)
    applies = {}
    for vnum in sorted(rows):
        for kind, value in rows[vnum]["applies"]:
            applies.setdefault(kind, vnum)
    for kind, vnum in sorted(applies.items()):
        pick(vnum, "apply %s" % kind)
    return chosen


def item_rows(rows, names, icons, descriptions, chosen):
    """The corpus's item rows: the chosen proto rows with their names, icons
    and descriptions; a vnum the proto lacks is made (synthetic)."""
    items = {}
    for vnum in sorted(chosen):
        row = dict(rows.get(vnum) or _synthetic(vnum))
        row["name"] = names.get(vnum, row["name"])
        row["icon"] = icons.get(vnum, "icon/item/%05d.tga" % vnum)
        desc, summary = descriptions.get(vnum, ("", ""))
        row["desc"], row["summary"] = desc, summary
        row["why"] = chosen[vnum]
        items[str(vnum)] = row
    return items


def _synthetic(vnum):
    """A row for a vnum the rules name that the proto lacks: the kind the
    rule expects (70055 a forget book, hair a costume hair, an auto potion a
    use item)."""
    kind, subtype = "QUEST", 0
    if vnum == 70055:
        kind = "SKILLFORGET"
    elif 73000 < vnum < 76000 or 45000 < vnum < 47000 or vnum > 100000:
        kind, subtype = "COSTUME", 1
    elif 72723 <= vnum <= 72730 or 76004 <= vnum <= 76022:
        kind, subtype = "USE", SUB_TYPES["USE"].index("USE_SPECIAL")
    row = {"name": "item %d" % vnum, "type": ITEM_TYPES.index(kind), "type_name": kind, "subtype": subtype,
           "subtype_name": str(subtype), "size": [1, 1], "antiflags": 0, "flags": 0, "wear": 0,
           "limits": [[0, 0], [0, 0]], "applies": [], "values": [0, 0, 0, 0, 0, 0], "sockets": 0,
           "price": {"buy": 0, "sell": 0}, "refine": 0, "synthetic": True}
    if kind == "USE":
        row["use_type"] = "USE_SPECIAL"
    return row


# The synthetic items the rules need and the proto has no example of: a ring
# (ITEM_RING, the ring slot's branch), a ring and a belt socket stone, a
# blend potion with no data, a gold metin stone and the error stone.
SYNTHETIC = {
    900001: {"name": "Ring of Trials", "type": ITEM_TYPES.index("RING"), "type_name": "RING", "subtype": 0,
             "subtype_name": "0", "size": [1, 1], "antiflags": 0, "flags": 0, "wear": 0,
             "limits": [[LIMITS["REAL_TIME"], 3600], [LIMITS["LEVEL"], 30]], "applies": [["APPLY_MAX_HP", 100]],
             "values": [0, 0, 0, 0, 0, 0], "sockets": 0, "price": {"buy": 0, "sell": 0}, "refine": 0},
    900002: {"name": "Ring of Days", "type": ITEM_TYPES.index("RING"), "type_name": "RING", "subtype": 0,
             "subtype_name": "0", "size": [1, 1], "antiflags": 0, "flags": 0, "wear": 0,
             "limits": [[LIMITS["LEVEL"], 30], [LIMITS["REAL_TIME"], 3600]], "applies": [],
             "values": [0, 0, 0, 0, 0, 0], "sockets": 0, "price": {"buy": 0, "sell": 0}, "refine": 0},
    900003: {"name": "Ring Gem", "type": ITEM_TYPES.index("USE"), "type_name": "USE",
             "subtype": SUB_TYPES["USE"].index("USE_PUT_INTO_RING_SOCKET"), "subtype_name": "USE_PUT_INTO_RING_SOCKET",
             "use_type": "USE_PUT_INTO_RING_SOCKET", "size": [1, 1], "antiflags": 0, "flags": 0, "wear": 0,
             "limits": [[0, 0], [0, 0]], "applies": [["APPLY_MAX_HP", 50]], "values": [0, 0, 0, 0, 0, 0],
             "sockets": 0, "price": {"buy": 0, "sell": 0}, "refine": 0},
    900004: {"name": "Stone of the Gold Socket", "type": ITEM_TYPES.index("METIN"), "type_name": "METIN",
             "subtype": SUB_TYPES["METIN"].index("METIN_GOLD"), "subtype_name": "METIN_GOLD", "size": [1, 1],
             "antiflags": 0, "flags": 0, "wear": WEARS["WEAR_WEAPON"], "limits": [[0, 0], [0, 0]],
             "applies": [["APPLY_CRITICAL_PCT", 2]], "values": [0, 0, 0, 0, 0, 0], "sockets": 0,
             "price": {"buy": 0, "sell": 0}, "refine": 0},
    900005: {"name": "Stone of the Unknown", "type": ITEM_TYPES.index("USE"), "type_name": "USE",
             "subtype": SUB_TYPES["USE"].index("USE_TUNING"), "subtype_name": "USE_TUNING", "use_type": "USE_TUNING",
             "size": [1, 1], "antiflags": 0, "flags": 0, "wear": 0, "limits": [[0, 0], [0, 0]], "applies": [],
             "values": [0, 0, 0, 0, 0, 0], "sockets": 0, "price": {"buy": 0, "sell": 0}, "refine": 0},
}



def _made(name, kind, subtype=0, limits=((0, 0), (0, 0)), values=(0, 0, 0, 0, 0, 0), applies=(), use_type=None, **rest):
    row = {"name": name, "type": ITEM_TYPES.index(kind), "type_name": kind, "subtype": subtype,
           "subtype_name": use_type or str(subtype), "size": [1, 1], "antiflags": 0, "flags": 0, "wear": 0,
           "limits": [list(limit) for limit in limits], "applies": [list(a) for a in applies], "values": list(values),
           "sockets": 0, "price": {"buy": 0, "sell": 0}, "refine": 0}
    if use_type:
        row["use_type"] = use_type
    row.update(rest)
    return row


_USE = SUB_TYPES["USE"].index
SYNTHETIC.update({
    # A real time limit in the second limit slot, for each kind whose rule reads GetLimitValue(1).
    900010: _made("Costume of the Second Limit", "COSTUME", 0, ((LIMITS["LEVEL"], 10), (LIMITS["REAL_TIME"], 86400))),
    900011: _made("Ring of the Second Limit", "UNIQUE", 0, ((LIMITS["LEVEL"], 1), (LIMITS["REAL_TIME"], 3600))),
    900012: _made("Charm of First Use", "UNIQUE", 0, ((LIMITS["REAL_TIME_FIRST_USE"], 600), (0, 0)), (0, 0, 1, 0, 0, 0)),
    900013: _made("Charm of Worn Time", "UNIQUE", 0, ((LIMITS["LEVEL"], 1), (0, 0)), (0, 0, 1, 0, 0, 0)),
    900014: _made("Scroll of the Second Limit", "USE", _USE("USE_SPECIAL"), ((LIMITS["LEVEL"], 1), (LIMITS["REAL_TIME"], 600)),
                  use_type="USE_SPECIAL"),
    900015: _made("Scroll of First Use", "USE", _USE("USE_SPECIAL"), ((LIMITS["REAL_TIME_FIRST_USE"], 600), (0, 0)),
                  (0, 0, 1, 0, 0, 0), use_type="USE_SPECIAL"),
    900016: _made("Scroll of Worn Time", "USE", _USE("USE_SPECIAL"), ((LIMITS["LEVEL"], 1), (0, 0)), (0, 0, 1, 0, 0, 0),
                  use_type="USE_SPECIAL"),
    900017: _made("Charger of Time", "USE", _USE("USE_TIME_CHARGE_PER"), ((LIMITS["REAL_TIME"], 600), (0, 0)), (10, 0, 0, 0, 0, 0),
                  use_type="USE_TIME_CHARGE_PER"),
    900018: _made("Charger of the Second Limit", "USE", _USE("USE_TIME_CHARGE_PER"), ((LIMITS["LEVEL"], 1), (LIMITS["REAL_TIME"], 600)),
                  (10, 0, 0, 0, 0, 0), use_type="USE_TIME_CHARGE_PER"),
    900019: _made("Fixed Charger of Time", "USE", _USE("USE_TIME_CHARGE_FIX"), ((LIMITS["REAL_TIME"], 600), (0, 0)),
                  (600, 0, 0, 0, 0, 0), use_type="USE_TIME_CHARGE_FIX"),
    900020: _made("Fixed Charger of the Second Limit", "USE", _USE("USE_TIME_CHARGE_FIX"),
                  ((LIMITS["LEVEL"], 1), (LIMITS["REAL_TIME"], 600)), (600, 0, 0, 0, 0, 0), use_type="USE_TIME_CHARGE_FIX"),
    900021: _made("Letter of the Second Limit", "QUEST", 0, ((LIMITS["LEVEL"], 1), (LIMITS["REAL_TIME"], 300))),
    900022: _made("Robe of Magic Defence", "ARMOR", SUB_TYPES["ARMOR"].index("ARMOR_BODY"), ((LIMITS["LEVEL"], 1), (0, 0)),
                  (15, 20, 0, 0, 0, 2), wear=WEARS["WEAR_BODY"]),
    900023: _made("Potion of Cure", "USE", _USE("USE_POTION"), values=(0, 0, 1, 10, 10, 0), use_type="USE_POTION"),
    900024: _made("Potion of Haste", "USE", _USE("USE_ABILITY_UP"), values=(7, 90, 10, 0, 0, 0), use_type="USE_ABILITY_UP"),
    900025: _made("Talisman of Worn Time", "UNIQUE", 0, ((LIMITS["TIMER_BASED_ON_WEAR"], 3600), (0, 0))),
    900026: _made("Pebble of Few Words", "QUEST", 0, desc="|"),
    900027: _made("Pebble of Gaps", "QUEST", 0, desc="First line.||Third line."),
    900028: _made("Stone of the Lost Icon", "METIN", 0, applies=(("APPLY_STR", 3),), wear=WEARS["WEAR_WEAPON"],
                  icon="icon/item/missing_stone.tga"),
    110500: dict(_made("Dragon Stone of the Sixth Step", "DS", 0, ((LIMITS["TIMER_BASED_ON_WEAR"], 86400), (0, 0))),
                 applies=[["APPLY_MAX_HP", 100]]),
})

# --- the skills (spec 5.8's skill cases; the numbers are the cases', the names the client's) ------

SKILL_TYPES = {"ACTIVE": 1, "SUPPORT": 2, "GUILD": 3, "HORSE": 4}   # module constants (PythonSkill.h)


def skill_rows(names):
    """Rows for the skill stand-in (nui_game_support.install_item_data): the
    client's names and descriptions, the numbers each branch needs."""
    def named(index, **values):
        found = names.get(index, {"names": ["skill %d" % index], "desc": "", "conditions": []})
        row = {"name": list(found["names"]), "desc": found["desc"], "conditions": list(found["conditions"]),
               "type": SKILL_TYPES["ACTIVE"], "max_level": 40, "level_limit": 0, "affects": [], "need_sp": 0,
               "continuation_sp": 0, "cool_time": 0, "duration": 0, "use_hp": False, "requirement": None,
               "require_stats": [], "requirement_met": True, "new_affects": []}
        row.update(values)
        return row

    level, iq = support.module_constants()["player"].get("LEVEL", 1), support.module_constants()["player"].get("IQ", 7)
    return {
        "1": named(1, affects=["Attack Power 50-60"], need_sp=40, cool_time=8, level_limit=5,
                   requirement=["Sword Spin", 20], requirement_met=False, require_stats=[[level, 5], [iq, 30], [99, 1]]),
        "3": named(3, new_affects=[["ATT_SPEED", 20.0, 20.0], ["MOV_SPEED", 10.0, 15.0], ["UNKNOWN", 1.0, 1.0]],
                   need_sp=-1, continuation_sp=5, duration=60, cool_time=30, requirement=["Berserk", 20],
                   requirement_met=True, require_stats=[[level, 1]]),
        "4": named(4, new_affects=[["HP", -100.0, -120.0], ["HP", 30.0, 30.0]], need_sp=50, use_hp=True,
                   continuation_sp=3),
        "5": named(5, new_affects=[["HP", -10.0, 5.0]], use_hp=True, need_sp=20),
        "19": named(19, cool_time=0, need_sp=0, max_level=40),
        "94": named(94, need_sp=30, conditions=["Usable on a party member"], require_stats=[[level, 30]]),
        "141": named(141, affects=["Max HP +10%"], need_sp=0, cool_time=0, max_level=40),
        "142": named(142, affects=["Evasion +5%"], max_level=40),
        "121": named(121, type=SKILL_TYPES["SUPPORT"]),
        "130": named(130, type=SKILL_TYPES["SUPPORT"]),
        "131": named(131, type=SKILL_TYPES["SUPPORT"], desc="Summon a horse."),
        "137": named(137, type=SKILL_TYPES["HORSE"], affects=["Riding Skill"], need_sp=20),
        "151": named(151, type=SKILL_TYPES["GUILD"], affects=["Max. Dragon Ghost +1400"], cool_time=0, need_sp=0),
        "152": named(152, type=SKILL_TYPES["GUILD"], affects=["Max. HP Increase +20%"], cool_time=120, need_sp=300,
                     level_limit=30),
        "153": named(153, type=SKILL_TYPES["GUILD"], cool_time=0, need_sp=0),
        "999": dict(named(999), name=[""]),
    }


# --- the cases (spec 5.8: instance states and contexts) ---------------------------------------------

ITEM_CONTEXTS = ("SetInventoryItem", "SetShopItem", "SetShopItemBySecondaryCoin", "SetExchangeOwnerItem",
                 "SetExchangeTargetItem", "SetPrivateShopBuilderItem", "SetSafeBoxItem", "SetMallItem",
                 "SetHyperlinkItem", "SetItemToolTip", "AddItemData", "AddRefineItemData", "attach")
SKILL_CONTEXTS = ("SetSkill", "SetSkillNew", "SetSkillOnlyName")
PLAYER = {"level": 120, "race": 0}
ATTRS_NORMAL = [[1, 500], [2, 50], [5, 8], [7, 10], [9, 10]]
ATTRS_RARE = ATTRS_NORMAL + [[15, 5], [16, 4]]


def _empty_sockets(row):
    count = min(int(row.get("sockets", 0) or 0), 3)
    return [SILVER] * count + [0] * (3 - count)


def _link(vnum, sockets, attrs, flag=0):
    """The link tokens player.GetItemLink makes (the hex vnum, flags and
    sockets, then attribute pairs: hex type, decimal value)."""
    tokens = ["item", "%x" % vnum, "%x" % flag] + ["%x" % s for s in sockets]
    for kind, value in attrs:
        tokens += ["%x" % kind, "%d" % value]
    return ":".join(tokens)


def item_cases(items):
    """The cases over the item rows, in a fixed order."""
    cases = []

    def add(case_id, context, vnum, **values):
        case = {"id": case_id, "context": context, "vnum": int(vnum)}
        case.update(values)
        cases.append(case)

    vnums = sorted(int(v) for v in items)
    by_type = {}
    for vnum in vnums:
        by_type.setdefault(items[str(vnum)]["type_name"], []).append(vnum)

    # Every item: its tooltip by vnum (player-free), and in the bag of a level 120 warrior.
    for vnum in vnums:
        row = items[str(vnum)]
        add("vnum-%d" % vnum, "SetItemToolTip", vnum)
        add("bag-%d" % vnum, "SetInventoryItem", vnum, sockets=_empty_sockets(row), attrs=[],
            player=dict(PLAYER), clock=CLOCK)

    # The representative items in every context.
    representatives = [v for v in (10, 3000, 7000, 11200, 12200, 13000, 14000, 16000, 17000, 18000, 27001, 27100, 28030,
                                    30329, 41001, 50300, 71027, 72723, 73001, 900001) if str(v) in items]
    for vnum in representatives:
        row = items[str(vnum)]
        sockets = _empty_sockets(row)
        for context in ITEM_CONTEXTS:
            values = {"sockets": sockets, "attrs": ATTRS_NORMAL, "player": dict(PLAYER), "clock": CLOCK}
            if context == "SetShopItem" or context == "SetShopItemBySecondaryCoin":
                values["shop"] = {"open": True, "private": False, "price": 1234567}
            if context == "SetPrivateShopBuilderItem":
                values["shop"] = {"open": True, "private": True, "price": 98765}
            if context == "SetSafeBoxItem":
                values["flags"] = 1
            if context == "SetHyperlinkItem":
                values = {"link": _link(vnum, sockets, ATTRS_NORMAL)}
            if context == "SetItemToolTip":
                values = {}
            if context == "attach":
                values["metin"] = 28030
            add("%s-%d" % (context, vnum), context, vnum, **values)
        add("SetInventoryItem-shop-%d" % vnum, "SetInventoryItem", vnum, sockets=sockets, attrs=[],
            player=dict(PLAYER), clock=CLOCK, shop={"open": True, "private": False, "price": 0}, sell_price=5000)
        add("SetInventoryItem-private-%d" % vnum, "SetInventoryItem", vnum, sockets=sockets, attrs=[],
            player=dict(PLAYER), clock=CLOCK, shop={"open": True, "private": True, "price": 0})
    return cases


def _first(items, type_name, test=lambda row: True):
    for vnum in sorted(int(v) for v in items):
        row = items[str(vnum)]
        if row["type_name"] == type_name and test(row):
            return vnum
    return None


def _has_limit(kind):
    return lambda row: any(limit[0] == LIMITS[kind] for limit in row["limits"])


def state_cases(items):
    """The instance states of spec 5.8 (sockets, attributes, the player, the
    clock, the auto potion, use counts, lottery and pick values) on the items
    whose rules read them."""
    cases = []
    bag = {"player": dict(PLAYER), "clock": CLOCK}

    def add(case_id, context, vnum, **values):
        if vnum is None:
            return
        case = {"id": case_id, "context": context, "vnum": int(vnum)}
        merged = dict(bag)
        merged.update(values)
        case.update(merged)
        cases.append(case)

    sword = 10
    for name, sockets in (("none", [0, 0, 0]), ("silver", [SILVER, 0, 0]), ("gold", [GOLD, 0, 0]),
                          ("stone", [28030, SILVER, SILVER]), ("error", [ERROR_METIN_STONE, SILVER, 0]),
                          ("gold-stone", [900004, GOLD, 0]), ("mixed", [GOLD, 28030, SILVER])):
        add("sockets-%s" % name, "SetInventoryItem", sword, sockets=sockets, attrs=[])
        add("refine-sockets-%s" % name, "AddRefineItemData", sword, sockets=sockets, attrs=ATTRS_NORMAL)
    add("sockets-stone-rtl", "SetInventoryItem", sword, sockets=[28030, GOLD, 0], attrs=[], rtl=True)
    for name, attrs in (("normal", ATTRS_NORMAL), ("rare", ATTRS_RARE), ("negative", [[1, -50], [5, 0]]),
                        ("unknown-type", [[200, 5]]), ("zero", [[1, 0]])):
        add("attrs-%s" % name, "SetInventoryItem", sword, sockets=[0, 0, 0], attrs=attrs)
    for race in range(8):
        add("race-%d" % race, "SetInventoryItem", sword, sockets=[0, 0, 0], attrs=[], player={"level": 120, "race": race})
        add("race-%d-armor" % race, "SetInventoryItem", 11200, sockets=[0, 0, 0], attrs=[],
            player={"level": 120, "race": race})
    add("level-low", "SetInventoryItem", 3000, sockets=[0, 0, 0], attrs=[], player={"level": 1, "race": 0})
    add("level-low-unforced", "SetInventoryItem", 3000, sockets=[0, 0, 0], attrs=[], player={"level": 1, "race": 0},
        force_color=False)
    for gender, test in (("male", lambda r: r["antiflags"] & ANTI_FLAGS["ANTI_FEMALE"] and r["wear"]),
                         ("female", lambda r: r["antiflags"] & ANTI_FLAGS["ANTI_MALE"] and r["wear"])):
        vnum = next((int(v) for v in sorted(items, key=int) if test(items[v])), None)
        for race in (0, 1):
            add("sex-%s-%d" % (gender, race), "SetInventoryItem", vnum, sockets=[0, 0, 0], attrs=[],
                player={"level": 120, "race": race})
    fan = _first(items, "WEAPON", lambda r: r["subtype_name"] == "WEAPON_FAN")
    add("fan", "SetInventoryItem", fan, sockets=[0, 0, 0], attrs=[])
    shield = _first(items, "ARMOR", lambda r: r["subtype_name"] == "ARMOR_SHIELD")
    add("armor-shield", "SetInventoryItem", shield, sockets=[SILVER, 0, 0], attrs=[])

    # Accessories (bracelet, necklace, earrings) and belts: sockets [filled, opened, time].
    for vnum in (14000, 16000, 17000):
        for name, sockets in (("closed", [0, 0, 0]), ("open", [0, 3, 0]), ("one", [1, 3, 3600]), ("two", [2, 3, 0]),
                              ("full", [3, 3, 7200])):
            add("accessory-%d-%s" % (vnum, name), "SetInventoryItem", vnum, sockets=sockets, attrs=[])
        add("accessory-%d-worn" % vnum, "SetInventoryItem", vnum, sockets=[2, 3, 1800], attrs=[], pos=93)
        add("accessory-%d-worn-again" % vnum, "SetInventoryItem", vnum, sockets=[2, 3, 1800], attrs=[], pos=93)
        add("accessory-%d-shop" % vnum, "SetShopItem", vnum, sockets=[1, 3, 600], attrs=[],
            shop={"open": True, "private": False, "price": 100})
    two_affects = next((int(v) for v in sorted(items, key=int)
                        if items[v]["type_name"] == "ARMOR" and items[v]["subtype_name"] in ("ARMOR_WRIST", "ARMOR_NECK", "ARMOR_EAR")
                        and len(items[v]["applies"]) >= 2), None)
    add("accessory-two-affects", "SetInventoryItem", two_affects, sockets=[2, 3, 900], attrs=[], pos=94)
    add("accessory-two-affects-bag", "SetInventoryItem", two_affects, sockets=[2, 3, 900], attrs=[])
    for name, sockets in (("closed", [0, 0, 0]), ("one", [1, 2, 600]), ("two", [2, 2, 0])):
        add("belt-%s" % name, "SetInventoryItem", 18000, sockets=sockets, attrs=[])
    add("belt-worn", "SetInventoryItem", 18000, sockets=[1, 2, 600], attrs=[], pos=113)

    # Remaining times: 0, 59 s, 1 h 1 min, 2 days; a shop item's empty time line.
    timed = 30329
    for name, left in (("0", 0), ("59", 59), ("3660", 3660), ("2d", 2 * DAY)):
        add("time-%s" % name, "SetInventoryItem", timed, sockets=[CLOCK + left, 0, 0], attrs=[])
    add("time-shop", "SetShopItem", timed, sockets=[CLOCK + 300, 0, 0], attrs=[],
        shop={"open": True, "private": False, "price": 10})
    add("time-past", "SetInventoryItem", timed, sockets=[CLOCK - 10, 0, 0], attrs=[])
    add("time-none", "SetInventoryItem", timed, sockets=[0, 0, 0], attrs=[])
    for type_name in ("COSTUME", "UNIQUE", "USE", "RING", "QUEST"):
        for limit in ("REAL_TIME", "REAL_TIME_FIRST_USE"):
            for first in (True, False):
                vnum = _first(items, type_name, lambda r, l=limit, f=first: (r["limits"][0 if f else 1][0] == LIMITS[l]))
                add("limit-%s-%s-%s" % (type_name.lower(), limit.lower(), "first" if first else "second"),
                    "SetInventoryItem", vnum, sockets=[CLOCK + 3660, 0, 0], attrs=[])
    first_use = _first(items, "USE", _has_limit("REAL_TIME_FIRST_USE")) or _first(items, "COSTUME", _has_limit("REAL_TIME_FIRST_USE"))
    for name, sockets in (("unused-empty", [0, 0, 0]), ("unused-seconds", [600, 0, 0]), ("used", [CLOCK + 1200, 1, 0])):
        add("first-use-%s" % name, "SetInventoryItem", first_use, sockets=sockets, attrs=[])
    for vnum in [v for v in (int(x) for x in sorted(items, key=int)) if items[str(v)]["type_name"] == "UNIQUE"][:6]:
        for name, sockets in (("rest", [0, 0, 90]), ("none", [0, 0, 0]), ("end", [CLOCK + 120, 0, CLOCK + 120])):
            add("unique-%d-%s" % (vnum, name), "SetInventoryItem", vnum, sockets=sockets, attrs=[])
    for name in ("USE_TIME_CHARGE_PER", "USE_TIME_CHARGE_FIX"):
        vnum = _first(items, "USE", lambda r, n=name: r.get("use_type") == n)
        add("charge-%s-socket" % name.lower(), "SetInventoryItem", vnum, sockets=[CLOCK + 600, 0, 5], attrs=[])
        add("charge-%s-value" % name.lower(), "SetInventoryItem", vnum, sockets=[0, 0, 0], attrs=[])
    special = [int(v) for v in sorted(items, key=int) if items[v].get("use_type") == "USE_SPECIAL"]
    for vnum in special[:8]:
        add("special-%d" % vnum, "SetInventoryItem", vnum, sockets=[CLOCK + 600, 0, CLOCK + 900], attrs=[])

    # Dragon soul stones: timer based on wear, by the deck's state.
    ds = _first(items, "DS", _has_limit("TIMER_BASED_ON_WEAR")) or _first(items, "DS")
    add("ds-spent", "SetInventoryItem", ds, sockets=[0, 0, 0], attrs=[[1, 100]])
    add("ds-idle", "SetInventoryItem", ds, sockets=[3600, 0, 0], attrs=[[1, 100]], ds_active=False)
    add("ds-active", "SetInventoryItem", ds, sockets=[3600, 0, 0], attrs=[[1, 100]], ds_active=True)
    add("ds-active-again", "SetInventoryItem", ds, sockets=[3600, 0, 0], attrs=[[1, 100]], ds_active=True)
    add("ds-other-window", "SetShopItem", ds, sockets=[3600, 0, 0], attrs=[], shop={"open": True, "private": False, "price": 1})
    for vnum in [int(v) for v in sorted(items, key=int) if items[v]["type_name"] == "DS"][:6]:
        add("ds-step-%d" % vnum, "SetItemToolTip", vnum)
    add("ds-step-6", "SetItemToolTip", _synthetic_ds(items))

    # Use items the rules read sockets of.
    add("autopotion-on", "SetInventoryItem", 72723, sockets=[1, 200, 1000], attrs=[])
    add("autopotion-off", "SetInventoryItem", 72727, sockets=[0, 0, 0], attrs=[])
    for vnum, count in ((27989, 2), (76006, 4), (50004, 3)):
        add("detector-%d" % vnum, "SetInventoryItem", vnum, sockets=[count, 0, 0], attrs=[])
    for vnum in (22010, 22011):
        add("warp-%d-known" % vnum, "SetInventoryItem", vnum, sockets=[469300, 964200, 0], attrs=[], zone=True)
        add("warp-%d-unknown" % vnum, "SetInventoryItem", vnum, sockets=[469300, 964200, 0], attrs=[])
        add("warp-%d-empty" % vnum, "SetInventoryItem", vnum, sockets=[0, 0, 0], attrs=[])
    potion = _first(items, "USE", lambda r: r.get("use_type") == "USE_POTION" and r["values"][2])
    add("potion-cure", "SetInventoryItem", potion, sockets=[0, 0, 0], attrs=[])
    for vnum in [int(v) for v in sorted(items, key=int) if items[v].get("use_type") == "USE_ABILITY_UP"]:
        add("ability-%d" % vnum, "SetInventoryItem", vnum, sockets=[0, 0, 0], attrs=[])
    blend = _first(items, "BLEND")
    add("blend-timed", "SetInventoryItem", blend, sockets=[1, 500, 125], attrs=[])
    add("blend-minutes", "SetInventoryItem", blend, sockets=[1, 500, 120], attrs=[])
    add("blend-seconds", "SetInventoryItem", blend, sockets=[1, 500, 30], attrs=[])
    add("blend-no-time", "SetInventoryItem", blend, sockets=[1, 500, 0], attrs=[])
    add("blend-no-data", "AddItemData", blend, sockets=[0, 0, 0], attrs=[], call_sockets=[], call_attrs=0)
    add("direct-no-sockets", "AddItemData", 10, sockets=[0, 0, 0], attrs=[], call_sockets=0, call_attrs=0)
    for type_name in ("LOTTERY", "PICK", "ROD", "FISH"):
        for vnum in [int(v) for v in sorted(items, key=int) if items[v]["type_name"] == type_name][:2]:
            maximum = items[str(vnum)]["values"][2]
            add("%s-%d-some" % (type_name.lower(), vnum), "SetInventoryItem", vnum, sockets=[12, 4, 0], attrs=[])
            add("%s-%d-full" % (type_name.lower(), vnum), "SetInventoryItem", vnum, sockets=[maximum, 4, 0], attrs=[])
            add("%s-%d-zero" % (type_name.lower(), vnum), "SetInventoryItem", vnum, sockets=[0, 0, 0], attrs=[])
            add("%s-%d-direct" % (type_name.lower(), vnum), "AddItemData", vnum, sockets=[0, 0, 0], attrs=[], call_sockets=0, call_attrs=0)

    # The items the rules name by vnum.
    add("pouch-empty", "SetInventoryItem", 50026, sockets=[0, 0, 0], attrs=[])
    add("pouch-money", "SetInventoryItem", 50026, sockets=[2000000000, 0, 0], attrs=[])
    add("pouch-direct", "AddItemData", 50026, sockets=[0, 0, 0], attrs=[], call_sockets=0, call_attrs=0)
    for vnum in (50300, 70037, 70055):
        add("book-%d" % vnum, "SetInventoryItem", vnum, sockets=[1, 0, 0], attrs=[])
        add("book-%d-unknown" % vnum, "SetInventoryItem", vnum, sockets=[999, 0, 0], attrs=[])
        add("book-%d-direct" % vnum, "AddItemData", vnum, sockets=[0, 0, 0], attrs=[], call_sockets=0, call_attrs=0)
    for vnum in (70103, 70104, 70105, 70106):
        add("polymorph-%d" % vnum, "SetInventoryItem", vnum, sockets=[101, 0, 0], attrs=[])
    for vnum in sorted(int(v) for v in items if "hair range" in " ".join(items[v].get("why", ()))):
        add("hair-%d" % vnum, "SetInventoryItem", vnum, sockets=[CLOCK + 60, 0, 0], attrs=[])
    long_desc = next((int(v) for v in sorted(items, key=int) if len(items[v].get("desc", "")) > 120), None)
    add("description-long", "SetInventoryItem", long_desc, sockets=[0, 0, 0], attrs=[])
    add("description-long-direct", "AddItemData", long_desc, sockets=[0, 0, 0], attrs=ATTRS_NORMAL)
    for vnum in (900002, 900003, 900005):
        add("synthetic-%d" % vnum, "SetInventoryItem", vnum, sockets=[CLOCK + 600, 0, 0], attrs=[])
    add("ring-gem-in-ring", "SetInventoryItem", 900001, sockets=[900003, 0, 0], attrs=[])
    add("unknown-stone", "AddItemData", 10, sockets=[900005, 0, 0], attrs=[])
    add("lost-icon-stone", "AddItemData", 10, sockets=[900028, 0, 0], attrs=[])
    add("gem-socket", "AddItemData", 10, sockets=[_first(items, "USE", lambda r: r.get("use_type") == "USE_PUT_INTO_ACCESSORY_SOCKET"),
                                                  _first(items, "USE", lambda r: r.get("use_type") == "USE_PUT_INTO_BELT_SOCKET"), 900003],
        attrs=[])
    return [case for case in cases if case["vnum"] is not None]


def api_cases(items):
    """Calls other windows make on the shared tooltips (spec 5.6) and the
    plain ToolTips other modules build (uiguild's war dialogs, uiparty's),
    in sequence: {"context": "calls", "kind", "calls": [[method, args]]};
    and every context with nothing in the slot."""
    cases = []
    bag = {"player": dict(PLAYER), "clock": CLOCK}

    def add(case_id, kind, calls, vnum=0, **values):
        case = {"id": case_id, "context": "calls", "kind": kind, "vnum": int(vnum), "calls": calls}
        merged = dict(bag)
        merged.update(values)
        case.update(merged)
        cases.append(case)

    for context in ("SetInventoryItem", "SetShopItem", "SetShopItemBySecondaryCoin", "SetExchangeOwnerItem",
                    "SetExchangeTargetItem", "SetPrivateShopBuilderItem", "SetSafeBoxItem", "SetMallItem"):
        cases.append({"id": "empty-%s" % context, "context": context, "vnum": 0, "sockets": [0, 0, 0], "attrs": [],
                      "player": dict(PLAYER), "clock": CLOCK})
    cases.append({"id": "link-no-attributes", "context": "SetHyperlinkItem", "vnum": 10, "link": _link(10, [1, 0, 0], [])})
    cases.append({"id": "link-short", "context": "SetHyperlinkItem", "vnum": 10, "link": "item:a:0"})
    add("fixed-point", "item", [["SetToolTipPosition", [400, 300]], ["SetItemToolTip", [10]]])
    add("fixed-point-off", "item", [["SetToolTipPosition", [-1, -1]], ["SetItemToolTip", [10]]])
    add("pointer-low", "item", [["SetItemToolTip", [3000]]], mouse=[800, 850])
    add("pointer-high", "item", [["SetItemToolTip", [3000]]], mouse=[30, 40])
    add("hide", "item", [["SetItemToolTip", [10]], ["HideToolTip", []]])
    add("show-again", "item", [["SetItemToolTip", [11200]], ["Hide", []], ["Show", []]])
    add("cube-appends", "item", [["ClearToolTip", []], ["AddItemData", [27001, [0, 0, 0], [[0, 0]] * 7]],
                                 ["AppendTextLine", ["Keeps bonuses and stones", 0xFF89B88D]]])
    add("cube-unforced", "item", [["SetCannotUseItemForceSetDisableColor", [False]], ["ClearToolTip", []],
                                  ["AddItemData", [3000, [0, 0, 0], [[0, 0]] * 7]], ["Show", []]], player={"level": 1, "race": 0})
    ds = 110000
    add("ds-warm", "item", [["WarmDragonSoulTimeCache", [[0, 1]]], ["SetInventoryItem", [0]]], vnum=ds,
        sockets=[3600, 0, 0], attrs=[[1, 100]], ds_active=True)
    add("ds-warm-spent", "item", [["WarmDragonSoulTimeCache", [[0]]]], vnum=ds, sockets=[0, 0, 0], attrs=[])
    add("ds-warm-plain", "item", [["WarmDragonSoulTimeCache", [[0]]]], vnum=10, sockets=[0, 0, 0], attrs=[])
    add("ds-warm-none", "item", [["WarmDragonSoulTimeCache", [[]]], ["ClearDragonSoulTimeCache", []]], vnum=ds)
    add("link-press", "link", [["SetHyperlinkItem", [_link(10, [1, 0, 0], ATTRS_NORMAL).split(":")]], ["OnMouseLeftButtonDown", []]])
    add("skill-width-reset", "skill", [["SetSkillNew", [1, 121, 3, 40]], ["SetSkill", [152]]],
        skill={"vnum": 121, "slot": 1, "grade": 3, "level": 40, "efficient": 0.5, "next": 0.6})
    add("skill-width-reset-normal", "skill", [["SetSkillNew", [1, 121, 3, 40]], ["SetSkill", [1]]],
        skill={"vnum": 121, "slot": 1, "grade": 3, "level": 40, "efficient": 0.5, "next": 0.6})
    add("skill-only-name-none", "skill", [["SetSkillOnlyName", [1, 0, 0]]])
    add("guild-war-type", "plain", [["_parent", [300, 200]], ["ClearToolTip", []], ["AutoAppendTextLine", ["Normal war", 0xFFF1E6C0]],
                                    ["AutoAppendTextLine", ["Kill the enemy guild's members."]], ["AlignHorizonalCenter", []],
                                    ["ShowToolTip", []]])
    add("party-affect", "plain", [["ClearToolTip", []], ["SetToolTipPosition", [120, 40]], ["AppendTextLine", ["Party bonus", 0xFF89B88D]],
                                  ["ShowToolTip", []]])
    for vnum in sorted(v for v in SYNTHETIC if str(v) in items):
        cases.append({"id": "synthetic-time-%d" % vnum, "context": "SetInventoryItem", "vnum": vnum,
                      "sockets": [CLOCK + 600, 0, CLOCK + 900], "attrs": [], "player": dict(PLAYER), "clock": CLOCK})
    cases.append({"id": "timer-not-ds", "context": "SetInventoryItem", "vnum": 900025, "sockets": [1800, 0, 0], "attrs": [],
                  "player": dict(PLAYER), "clock": CLOCK})
    return cases


def _synthetic_ds(items):
    """A dragon soul stone of step 5 (vnum digit 5), which no rule names."""
    return 110500 if "110500" in items else None


def skill_cases():
    cases = []

    def add(case_id, context, index, slot=1, grade=0, level=1, player=None, **values):
        case = {"id": case_id, "context": context, "vnum": int(index),
                "skill": {"vnum": int(index), "slot": slot, "grade": grade, "level": level, "efficient": 0.5, "next": 0.6}}
        if player is not None:
            case["player"] = player
        case.update(values)
        cases.append(case)

    add("skill-none", "SetSkillNew", 0)
    add("skill-none-old", "SetSkill", 0)
    for grade in range(4):
        for level in (0, 5, 10, 20, 25, 35, 40):
            add("tongsol-g%d-l%d" % (grade, level), "SetSkillNew", 121, grade=grade, level=level)
    for grade in range(4):
        add("riding-g%d" % grade, "SetSkillNew", 130, grade=grade, level=5)
    for level in (0, 1, 5, 10):
        add("summon-l%d" % level, "SetSkillNew", 131, level=level)
    for index in (151, 152, 153):
        for level in range(8):
            add("guild-%d-l%d" % (index, level), "SetSkillNew", index, level=level, player={"level": 20 if level % 2 else 120})
        add("guild-%d-old" % index, "SetSkill", index)
        add("guild-%d-old-level" % index, "SetSkill", index, level=3, skill_level=3)
    for index in (1, 3, 4, 5, 19, 94, 137, 141, 142):
        for grade in range(4):
            for level in (1, 17, 20, 40):
                add("skill-%d-g%d-l%d" % (index, grade, level), "SetSkillNew", index, grade=grade, level=level,
                    player={"level": 1 if level == 1 else 120, "iq": 40 if grade % 2 else 1})
        add("skill-%d-old" % index, "SetSkill", index, grade=1, level=7, player={"level": 120, "iq": 40})
        add("skill-%d-name" % index, "SetSkillOnlyName", index, grade=2, level=0)
    add("skill-1-real-grade", "SetSkillNew", 1, grade=1, level=5, real_grade=2)
    add("skill-1-real-grade-3", "SetSkillNew", 1, grade=3, level=5, real_grade=3)
    return cases


def build_corpus(proto=DEFAULT_PROTO, names=DEFAULT_NAMES, mobs=DEFAULT_MOBS):
    """The corpus (spec 5.8, 9.6's schema)."""
    rows = expand_ranges(proto_rows(proto))
    chosen = choose_items(rows)
    items = item_rows(rows, names_of(names), icons_of(ITEM_LIST), descriptions_of(ITEM_DESC), chosen)
    for vnum, row in sorted(SYNTHETIC.items()):
        row = dict(row, synthetic=True, why=["a rule branch the proto has no item for"],
                   icon=row.get("icon", "icon/item/%05d.tga" % 27001), desc=row.get("desc", ""), summary=row.get("summary", ""))
        items[str(vnum)] = row
    mob_names = names_of(mobs)
    cases = item_cases(items) + state_cases(items) + skill_cases() + api_cases(items)
    seen = set()
    for case in cases:
        if case["id"] in seen:
            raise ValueError("two cases are named %s" % case["id"])
        seen.add(case["id"])
    inputs = {}
    for label, path in (("item_proto", proto), ("item_names", names), ("mob_names", mobs), ("item_list", ITEM_LIST),
                        ("itemdesc", ITEM_DESC), ("skilldesc", SKILL_DESC), ("uitooltip", RULES)):
        inputs[label] = {"path": _shown_path(path), "sha256": sha256_of(path)}
    return {
        "$comment": "The tooltip parity corpus (P14 spec 5.8), written by tools/nui_tooltip_corpus.py corpus; "
                    "do not edit. items: the corpus row schema of P14 spec 9.6, the numbers the client's item "
                    "module answers; cases: {id, context, vnum, sockets, attrs, player, clock, shop, link, skill, "
                    "pos, flags, ...}; a case with player, clock or shop needs player state (the kit's TP-N skips it).",
        "inputs": inputs,
        "items": items,
        "skills": skill_rows(skill_names_of(SKILL_DESC)),
        "mobs": dict((str(v), mob_names[v]) for v in (101, 102, 103, 104, 105) if v in mob_names),
        "cases": cases,
    }


def _shown_path(path):
    path = os.path.abspath(path)
    if path.startswith(REPO + os.sep):
        return os.path.relpath(path, REPO)
    return path


def load_corpus(path=CORPUS):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# --- the harness (shared by tools/nui_tooltip_test.py and the fixture writer) -------------------------------

FOUNDATION_SIZES = {"METIN_SOCKET_MAX_NUM": 4, "ITEM_APPLY_MAX_NUM": 7}


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


class _DragonSoulWindow(object):
    isActivated = False


class TipWorld(object):
    """One stand-in client running uitooltip.py over a corpus (nui_game_support's
    Game, its tooltip ui and item data): `recorder` False is the legacy side
    (the rules alone, their widgets the stand-ins'), True the NovaUI side (the
    recorder and the three facades loaded). `sizes` "foundation" gives the
    rules 4 sockets and 7 applies, as the foundation wave's C2 will."""

    def __init__(self, corpus, recorder, sizes="today", locale="en", wave3b=False):
        self.corpus = corpus
        self.recorder = recorder
        game = self.game = support.Game()
        support.install_wave2b_ui(game)
        support.install_wave3a_ui(game)
        if wave3b:
            support.install_wave3b_ui(game)
        support.install_tooltip_ui(game, locale)
        self.data = support.install_item_data(game, corpus)
        modules = game.modules
        cache = {}
        modules["app"]._accessorySocketTimeCache = cache
        modules["player"]._accessorySocketTimeCache = cache
        self.rtl = [False]
        modules["app"].IsRTL = lambda: self.rtl[0]
        if sizes == "foundation":
            modules["player"].METIN_SOCKET_MAX_NUM = FOUNDATION_SIZES["METIN_SOCKET_MAX_NUM"]
            modules["item"].ITEM_APPLY_MAX_NUM = FOUNDATION_SIZES["ITEM_APPLY_MAX_NUM"]
            affect = modules["item"].GetAffect
            modules["item"].GetAffect = lambda i: (list(_padded(affect, 7)) + [(0, 0)] * 7)[i]
        game.load_standard()
        game.load("nui_text", "nui_text.py")
        with quiet():
            game.load("uiToolTip", "uitooltip.py")
            if recorder:
                for name in ("nui_tooltip", "nui_item_tooltip", "nui_skill_tooltip", "nui_link_tooltip"):
                    game.load(name, name + ".py")
        image = modules["ui"].ImageBox
        load = image.LoadImage

        def load_image(widget, path):
            if "missing" in (path or ""):
                raise RuntimeError("Failed to load image (filename: %s)" % path)  # wndImageLoadImage
            load(widget, path)
        image.LoadImage = load_image
        self.dragon_soul = _DragonSoulWindow()
        self.tips = {}

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def m(self, name):
        return self.game.loaded[name]

    def tooltip(self, kind):
        """The world's tooltip of a kind, made once (the Interface's are
        reused too): "item", "skill", "link", "embedded" (inside a dialog)."""
        tip = self.tips.get(kind)
        if tip is None:
            with quiet():
                if not self.recorder:
                    legacy = self.m("uiToolTip")
                    cls = {"item": legacy.ItemToolTip, "skill": legacy.SkillToolTip, "link": legacy.HyperlinkItemToolTip,
                           "embedded": legacy.ItemToolTip, "embedded2": legacy.ItemToolTip, "plain": legacy.ToolTip}[kind]
                    tip = cls()
                else:
                    cls = {"item": self.m("nui_item_tooltip").ItemToolTip, "skill": self.m("nui_skill_tooltip").SkillToolTip,
                           "link": self.m("nui_link_tooltip").HyperlinkItemToolTip,
                           "embedded": self.m("nui_tooltip").EmbeddedItemToolTip,
                           "embedded2": self.m("nui_tooltip").EmbeddedItemToolTip,
                           # A plain ToolTip stays legacy (spec 5.6), made with the recorder installed.
                           "plain": self.m("uiToolTip").ToolTip}[kind]
                    tip = cls()
                    if kind.startswith("embedded"):
                        tip.on_model = lambda model, t=tip: setattr(t, "_test_published", model)
                if kind.startswith("embedded"):
                    tip.SetFollow(False)
                    tip.Show()
                tip.SetDragonSoulWindow(self.dragon_soul) if hasattr(tip, "SetDragonSoulWindow") else None
            self.tips[kind] = tip
        return tip


class DialogWorld(TipWorld):
    """The refine and attach dialogs over a corpus (spec 6.4, 6.5): recorder
    False is the legacy side (uirefine.py and uiattachmetin.py, their
    windows from their real uiscripts, their tooltips the legacy ones), True
    the NovaUI side (nui_refine, nui_attach_metin and the recorder)."""

    FLAGS = "+refine,+attach-metin"

    def __init__(self, corpus, recorder, sizes="today", locale="en"):
        TipWorld.__init__(self, corpus, recorder, sizes, locale, wave3b=True)
        game = self.game
        strings = game.modules["uiScriptLocale"]
        with open(os.path.join(LOCALE, locale, "locale_interface.txt"), encoding="utf-8", errors="replace") as handle:
            for line in handle.read().split("\n"):
                fields = line.split("\t")
                if len(fields) >= 2 and fields[0]:
                    strings.__dict__[fields[0]] = fields[1]
        game.modules["systemSetting"].GetUINuiWindows = lambda: self.FLAGS if recorder else ""
        # The legacy materials' text lines (uirefine.py AppendMaterial) align
        # vertically; the tooltip ui's stand-in TextLine has no such call.
        text_line = game.modules["ui"].TextLine
        for name, value in (("SetVerticalAlignCenter", "center"), ("SetVerticalAlignBottom", "bottom")):
            if name not in dir(text_line):
                setattr(text_line, name, lambda widget, value=value: setattr(widget, "valign", value))
        with quiet():
            for name, file_name in (("nui_limits", "nui_limits.py"), ("nui_proxies", "nui_proxies.py"),
                                    ("uiRefine", "uirefine.py"), ("uiAttachMetin", "uiattachmetin.py")):
                game.load(name, file_name)
            if recorder:
                for name in ("nui_refine", "nui_attach_metin"):
                    game.load(name, name + ".py")

    def make(self, which):
        """The Interface's or the inventory's dialog, as they make it (6.7's
        lines): "new" (Interface.dlgRefineNew), "old" (refineDialog),
        "attach" (attachMetinDialog), hidden."""
        windows = self.m("nui_windows")
        refine, attach = self.m("uiRefine"), self.m("uiAttachMetin")
        with quiet():
            if which == "new":
                dialog = windows.make("refine", refine.RefineDialogNew, "nui_refine.RefineDialogNew")
            elif which == "old":
                dialog = windows.make("refine", refine.RefineDialog, "nui_refine.RefineDialog")
            else:
                dialog = windows.make("attach-metin", attach.AttachMetinDialog, "nui_attach_metin.AttachMetinDialog")
            dialog.Hide()
        return dialog


def place_items(world, case, items):
    """apply_case's state, with several items: [{pos, vnum, sockets, attrs, count}]."""
    support.apply_case(world.game, case)
    held = world.data.case["items"]
    for row in items:
        held[int(row["pos"])] = {"vnum": int(row["vnum"]), "count": int(row.get("count", 1)),
                                 "sockets": list(row.get("sockets", ())), "attrs": [tuple(a) for a in row.get("attrs", ())],
                                 "flags": 0, "sell_price": 0}


def _padded(affect, count):
    for i in range(count):
        try:
            yield affect(i)
        except IndexError:
            yield (0, 0)


def kind_of(case):
    context = case["context"]
    if context == "calls":
        return case.get("kind", "item")
    if context in SKILL_CONTEXTS:
        return "skill"
    if context == "SetHyperlinkItem":
        return "link"
    if context in ("AddRefineItemData", "attach"):
        return "embedded"
    return "item"


def run_case(world, case):
    """Runs one case's call on the world's tooltip of its kind: (the tooltips
    it filled, two for attach: the new one, then the old one; the exception
    the legacy code raised, as (type name, message), or None)."""
    try:
        return _run_case(world, case), None
    except Exception as error:
        return [world.tooltip(kind_of(case))], (type(error).__name__, str(error))


def _main_call(world):
    """The case's own call starts now (the publishes the parity test counts)."""
    if world.recorder:
        world.main_call_publishes = world.m("nui_tooltip").STATS["publishes"]


def _run_case(world, case):
    game = world.game
    world.main_call_publishes = world.m("nui_tooltip").STATS["publishes"] if world.recorder else 0
    support.apply_case(game, case)
    world.rtl[0] = bool(case.get("rtl"))
    game.modules["localeInfo"].MINIMAP_ZONE_NAME_DICT = {"metin2_map_a1": "Yongan"} if case.get("zone") else {}
    world.dragon_soul.isActivated = bool(case.get("ds_active"))
    game.modules["wndMgr"].mouse = tuple(case.get("mouse", (0, 0)))
    if case.get("skill") and "real_grade" in case:
        world.data.case["skill"] = dict(case["skill"], grade=case["real_grade"])
    player = game.modules["player"]
    context = case["context"]
    kind = kind_of(case)
    tip = world.tooltip(kind)
    pos = int(case.get("pos", 0))
    sockets = case.get("sockets", [0, 0, 0])
    attrs = case.get("attrs", [])
    attr_slot = attrs if attrs == 0 else [tuple(a) for a in attrs] + [(0, 0)] * (7 - len(attrs))
    socket_slot = case["call_sockets"] if "call_sockets" in case else list(sockets)
    if "call_attrs" in case:
        attr_slot = case["call_attrs"]
    if hasattr(tip, "SetCannotUseItemForceSetDisableColor"):
        tip.SetCannotUseItemForceSetDisableColor(case.get("force_color", True))
    with quiet():
        if context == "SetInventoryItem":
            tip.SetInventoryItem(pos)
        elif context in ("SetShopItem", "SetShopItemBySecondaryCoin", "SetExchangeOwnerItem", "SetExchangeTargetItem",
                         "SetSafeBoxItem", "SetMallItem"):
            getattr(tip, context)(pos)
        elif context == "SetPrivateShopBuilderItem":
            tip.SetPrivateShopBuilderItem(player.INVENTORY, pos, 0)
        elif context == "SetHyperlinkItem":
            tip.SetHyperlinkItem(case["link"].split(":"))
        elif context == "SetItemToolTip":
            tip.SetItemToolTip(case["vnum"])
        elif context == "AddItemData":
            tip.ClearToolTip()
            _main_call(world)
            tip.AddItemData(case["vnum"], socket_slot, attr_slot)
        elif context == "AddRefineItemData":
            tip.ClearToolTip()
            _main_call(world)
            tip.AddRefineItemData(case["vnum"], socket_slot, attr_slot)
        elif context == "attach":
            return _attach(world, case, socket_slot, attr_slot)
        elif context == "calls":
            for name, args in case["calls"]:
                _main_call(world)
                if name == "_parent":
                    window = types.SimpleNamespace(GetGlobalPosition=lambda xy=tuple(args): xy)
                    tip.GetParentProxy = lambda w=window: w
                    continue
                getattr(tip, name)(*[_slot_arg(a) for a in args])
        elif context == "SetSkill":
            skill = case["skill"]
            if "skill_level" in case:
                tip.SetSkill(case["vnum"], case["skill_level"])
            else:
                tip.SetSkill(case["vnum"])
        elif context == "SetSkillNew":
            skill = case["skill"]
            tip.SetSkillNew(skill["slot"], case["vnum"], skill["grade"], skill["level"])
        elif context == "SetSkillOnlyName":
            skill = case["skill"]
            tip.SetSkillOnlyName(skill["slot"], case["vnum"], skill["grade"])
        else:
            raise ValueError("no context %r" % context)
        if not world.recorder:
            # Spec 5.8 A: then its OnUpdate (a legacy board shown follows and
            # rewrites its time lines every frame; an embedded one does not).
            if tip.IsShow():
                tip.OnUpdate()
    return [tip]


def _slot_arg(value):
    """A call argument from JSON: attribute pairs as tuples."""
    if isinstance(value, list) and value and all(isinstance(v, list) and len(v) == 2 for v in value):
        return [tuple(v) for v in value]
    return value


def _attach(world, case, sockets, attrs):
    """uiAttachMetin.AttachMetinDialog.Open's pair (uiattachmetin.py:77-129):
    the new tooltip with the stone in the first fitting socket, then the old
    one at the new one's width."""
    item = world.game.modules["item"]
    player = world.game.modules["player"]
    new, old = world.tooltip("embedded"), world.tooltip("embedded2")
    metin = int(case.get("metin", 28030))
    old.ClearToolTip()
    new.ClearToolTip()
    _main_call(world)
    item.SelectItem(metin)
    metin_subtype = item.GetItemSubType()
    substituted = list(sockets)
    for i, data in enumerate(substituted):
        if (item.METIN_NORMAL == metin_subtype and data in (SILVER, GOLD)) or (item.METIN_GOLD == metin_subtype and data == GOLD):
            substituted[i] = metin
            break
    new.AddItemData(case["vnum"], substituted, attrs)
    item.SelectItem(metin)
    old.ResizeToolTipWidth(new.GetWidth())
    old.AddItemData(case["vnum"], list(sockets), attrs)
    return [new, old]


def stand_in_rows(tip):
    """Spec 5.8 A over the stand-in widgets (nui_game_support.install_tooltip_ui):
    the shown widgets of childrenList, then the lines of timeInfoList not
    already there, sorted by (y, x): ("text", text, color, align, outline),
    ("image", path) for an image that loaded one, ("line", color)."""
    seen = set()
    widgets = []
    for widget in list(tip.childrenList) + [info["line"] for info in tip.timeInfoList if info.get("line")]:
        if id(widget) not in seen:
            seen.add(id(widget))
            widgets.append(widget)
    rows = []
    for widget in widgets:
        if not widget.shown:
            continue
        x, y = widget.GetLocalPosition()
        kind = type(widget).__name__
        if kind == "TextLine":
            row = ("text", widget.text or "", widget.color if widget.color is not None else 0xFFFFFFFF,
                   widget.align, bool(widget.outline))
        elif kind == "ImageBox":
            if not widget.image:
                continue
            row = ("image", widget.image.replace("\\", "/").lstrip("/").lower())
        else:
            row = ("line", widget.color)
        rows.append((y, x, widget.seq, row))
    rows.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in rows]


def published(world, tip):
    """The model the NovaUI side published for `tip`: its board's (the item,
    skill and link tooltips), or an embedded tooltip's last."""
    if getattr(tip, "KIND", None) is None:
        return getattr(tip, "_test_published", None)
    board = world.m("nui_tooltip").board(tip.KIND)
    return {"lines": board.model.get("lines", []), "min_w": board.model.get("min_w", 0)} if board is not None else None


# --- the comparison (spec 5.8), shared by the parity test and the report --------------------------------------

def legacy_shown_rows(tips):
    """Spec 5.8 A: what each legacy tooltip shows ([] while its board is hidden)."""
    return [stand_in_rows(tip) if tip.IsShow() else [] for tip in tips]


def novaui_rows(world, case, tips):
    """Spec 5.8 B: what each facade published, flattened ([] while hidden); a
    plain ToolTip stays legacy (spec 5.6), made with the recorder installed,
    so its stand-in widgets are compared."""
    recorder = world.m("nui_tooltip")
    rows = []
    for tip in tips:
        if kind_of(case) == "plain":
            rows.append(stand_in_rows(tip) if tip.IsShow() else [])
            continue
        model = published(world, tip)
        rows.append(recorder.model_rows(model, now=world.game.state.now) if model is not None and tip.IsShow() else [])
    return rows


class ParityRun(object):
    """Every case of a corpus on a legacy and a NovaUI world: `results` holds
    (case, (legacy rows, error), (NovaUI rows, error), publishes of the
    case's own call, [positional rule == marker rule per tooltip], [the
    published models]); `novaui` is the NovaUI world (its recorder's STATS
    and GAP_VALUES)."""

    def __init__(self, corpus):
        self.legacy = TipWorld(corpus, recorder=False)
        self.novaui = TipWorld(corpus, recorder=True)
        self.results = []
        for case in corpus["cases"]:
            with self.legacy:
                tips, error = run_case(self.legacy, case)
                legacy = (legacy_shown_rows(tips), error)
            with self.novaui:
                tips, error = run_case(self.novaui, case)
                recorder = self.novaui.m("nui_tooltip")
                publishes = recorder.STATS["publishes"] - self.novaui.main_call_publishes
                positional = [recorder.build_model(tip, positional=True) == recorder.build_model(tip)
                              for tip in tips if kind_of(case) != "plain"]
                models = [published(self.novaui, tip) if tip.IsShow() else None for tip in tips
                          if kind_of(case) != "plain"]
                novaui = (novaui_rows(self.novaui, case, tips), error)
            self.results.append((case, legacy, novaui, publishes, positional, models))


REPORT = os.path.normpath(os.path.join(REPO, "..", ".nui-work", "live", "wave3b", "tooltip-parity", "offline.json"))


def _entries(models):
    for model in models:
        for entry in (model or {}).get("lines", ()):
            yield entry
            for sub in entry.get("sub", ()):
                yield sub


def report(corpus):
    """The offline parity report (spec 5.8): every case with its result, the
    differences (none allowed), the gap values logged, the recorder's
    counters and the coverage gate."""
    run = ParityRun(corpus)
    recorder = run.novaui.m("nui_tooltip")
    cases, contexts, differences, raised = [], {}, [], []
    totals = {"shown": 0, "rows": 0, "sockets": 0, "countdowns": 0, "tags_runs": 0, "custom_runs": 0}
    for case, legacy, novaui, publishes, positional, models in run.results:
        context = case["context"] if case["context"] != "calls" else "calls:" + case.get("kind", "item")
        contexts[context] = contexts.get(context, 0) + 1
        entries = list(_entries(models))
        runs = [r for entry in entries for r in entry.get("runs", ())]
        shown = sum(1 for rows in novaui[0] if rows)
        rows = sum(len(rows) for rows in novaui[0])
        totals["shown"] += shown
        totals["rows"] += rows
        totals["sockets"] += sum(1 for entry in entries if entry.get("t") == "socket")
        totals["countdowns"] += sum(1 for r in runs if r.get("k") == "count")
        totals["tags_runs"] += sum(1 for r in runs if r.get("k") == "tags")
        totals["custom_runs"] += sum(1 for r in runs if r.get("role") == "custom")
        equal = legacy == novaui
        if not equal:
            differences.append({"id": case["id"], "legacy": legacy, "novaui": novaui})
        if legacy[1] or novaui[1]:
            raised.append({"id": case["id"], "legacy": list(legacy[1] or ()), "novaui": list(novaui[1] or ())})
        cases.append({"id": case["id"], "context": context, "kind": kind_of(case), "shown": shown, "rows": rows,
                      "publishes": publishes, "positional_agrees": all(positional), "equal": equal})
    live, excluded = rule_lines()
    hit = trace_rules(TipWorld(corpus, recorder=False), corpus["cases"])
    missing = sorted(line for line in live if line not in hit)
    stats = dict(recorder.STATS)
    stats["build_ms_max"] = round(stats["build_ms_max"], 3)
    stats["build_ms_sum"] = round(stats["build_ms_sum"], 3)
    return {
        "generated_by": "python3 tools/nui_tooltip_corpus.py report (plain CPython over tools/nui_game_support.py's stand-ins; "
                        "the stand-in text metric is 6 px a character)",
        "corpus_sha256": sha256_of(CORPUS),
        "uitooltip_sha256": sha256_of(RULES),
        "cases": len(cases),
        "contexts": dict(sorted(contexts.items())),
        "totals": totals,
        "differences": differences,
        "raised_in_both": raised,
        "publishes_max": max(c["publishes"] for c in cases) if cases else 0,
        "positional_disagreements": [c["id"] for c in cases if not c["positional_agrees"]],
        "gap_values": dict((str(k), v) for k, v in sorted(recorder.GAP_VALUES.items())),
        "stats": stats,
        "coverage": {"live_lines": len(live), "run": len(live) - len(missing), "excluded": len(excluded),
                     "missing": missing},
        "per_case": cases,
    }


# --- the branch list (spec 5.8's coverage gate) ---------------------------------------------------------------

# Methods with no rule in them, or none the client runs (spec 2.1's dead code).
DEAD = {
    ("ItemToolTip", "AppendTextLineTime", 634): "shadowed: the class defines AppendTextLineTime again at :2047",
    ("ItemToolTip", "_ItemToolTip__AppendAttackSpeedInfo", None): "no caller",
    ("ItemToolTip", "_ItemToolTip__AppendAttackGradeInfo", None): "no caller",
    ("SkillToolTip", "AppendMasterAffectDescription", None): "no caller",
    ("SkillToolTip", "AppendNextAffectDescription", None): "no caller",
    ("ItemToolTip", "AddItemData_Offline", None): "only the __main__ test calls it",
    ("ToolTip", "__del__", None): "a destructor, not a rule",
    ("ToolTip", "SetDefaultFontName", None): "no caller",
    ("ItemToolTip", "__del__", None): "a destructor, not a rule",
    ("SkillToolTip", "__del__", None): "a destructor, not a rule",
    ("SkillToolTip", "_RebuildLocaleStrings", None): "runs at import and on a locale change, not per tooltip",
}
# Single lines no caller in the client reaches: (method, the line's text) ->
# why. Checked against every root module's calls (grep) and the locale files.
UNREACHABLE = {
    ("SplitDescriptionByPixelWidth", "return []"):
        "both callers return first on an empty description (AppendDescription :263, __AdjustDescMaxWidth :1514)",
    ("ToolTip.AutoAppendTextLine", "textLine.SetPosition(10, self.toolTipHeight)"):
        "no caller passes centerAlign=False to AutoAppendTextLine",
    ("ToolTip.AppendTextLine", "textLine.SetPosition(10, self.toolTipHeight)"):
        "no caller passes centerAlign=False to AppendTextLine",
    ("ToolTip.GetChangeTextLineColor", "return self.SPECIAL_POSITIVE_COLOR"):
        "no caller passes isSpecial",
    ("ToolTip.GetChangeTextLineColor", "return self.NORMAL_COLOR"):
        "every caller passes a value it checked to be above 0 (or an affect string, which is None for 0)",
    ("ItemToolTip.__init__", 'cache = getattr(player, "_accessorySocketTimeCache", None)'):
        "constinfo.py sets app._accessorySocketTimeCache when uitooltip.py imports it, before any tooltip",
    ("ItemToolTip.__init__", "if cache is None:"):
        "constinfo.py sets app._accessorySocketTimeCache when uitooltip.py imports it, before any tooltip",
    ("ItemToolTip.__init__", "cache = constInfo.ACCESSORY_SOCKET_TIME_CACHE"):
        "constinfo.py sets app._accessorySocketTimeCache when uitooltip.py imports it, before any tooltip",
    ("ItemToolTip.__init__", "app._accessorySocketTimeCache = cache"):
        "constinfo.py sets app._accessorySocketTimeCache when uitooltip.py imports it, before any tooltip",
    ("ItemToolTip.__init__", "player._accessorySocketTimeCache = cache"):
        "constinfo.py sets app._accessorySocketTimeCache when uitooltip.py imports it, before any tooltip",
    ("ItemToolTip.CanEquip", "if job not in self.ANTI_FLAG_DICT:"):
        "chr.RaceToJob answers race % 4 (InstanceBase.h RaceToJob), always a key of ANTI_FLAG_DICT",
    ("ItemToolTip._ItemToolTip__GetAttributeColor", "return self.NORMAL_COLOR"):
        "__AppendAttributeInformation skips a value of 0 before it asks (:869-870)",
    ("ItemToolTip.AddRefineItemData", "metinSlot[i] = 0"):
        "newSlots holds every socket (the filled ones, then the empty ones), so the else never runs",
    ("ItemToolTip._ItemToolTip__GetAffectString", 'return "UNKNOWN_VALUE[%s] %s" % (affectType, affectValue)'):
        "every AFFECT_DICT entry is a one-argument SA entry or an SNA entry in every locale, so the call never raises TypeError",
}
# The return after an unreachable test shares its reason.
FOLLOWS = {("ItemToolTip.CanEquip", "return False"): "if job not in self.ANTI_FLAG_DICT:"}


def _qualified(node, cls):
    name = node.name
    if name.startswith("__") and not name.endswith("__"):
        name = "_%s%s" % (cls, name)
    return name


def rule_lines(path=RULES):
    """{line: "Class.method"} of every statement of the live rule methods of
    uitooltip.py, and {line: reason} of the lines left out."""
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    tree = ast.parse(source)
    lines = source.split("\n")
    live, excluded = {}, {}
    for top in tree.body:
        units = []
        if isinstance(top, ast.FunctionDef) and top.name in ("chop", "SplitDescriptionByPixelWidth"):
            units.append(("", top.name, top))
        elif isinstance(top, ast.ClassDef) and top.name in ("ToolTip", "ItemToolTip", "HyperlinkItemToolTip", "SkillToolTip"):
            for node in top.body:
                if isinstance(node, ast.FunctionDef):
                    units.append((top.name, _qualified(node, top.name), node))
        for cls, name, node in units:
            label = "%s.%s" % (cls, name) if cls else name
            reason = DEAD.get((cls, name, node.lineno)) or DEAD.get((cls, name, None))
            for statement in ast.walk(node):
                if not isinstance(statement, ast.stmt) or statement is node:
                    continue
                if isinstance(statement, (ast.FunctionDef, ast.ClassDef)):
                    continue
                if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
                    continue  # a docstring or a commented-out block in a string
                line = statement.lineno
                if reason:
                    excluded[line] = "%s: %s" % (label, reason)
                    continue
                text = lines[line - 1].strip()
                why = _unreachable(label, text, lines, line)
                if why:
                    excluded[line] = "%s: %s" % (label, why)
                    continue
                live[line] = label
    return live, excluded


def _unreachable(label, text, lines, line):
    why = UNREACHABLE.get((label, text))
    if why:
        return why
    previous = FOLLOWS.get((label, text))
    if previous is not None and line >= 2 and lines[line - 2].strip() == previous:
        return UNREACHABLE.get((label, previous), "")
    return ""


def branch_list(path=RULES):
    live, excluded = rule_lines(path)
    return {
        "$comment": "The live rule lines of assets/root/uitooltip.py (P14 spec 5.8's coverage gate), written by "
                    "tools/nui_tooltip_corpus.py corpus; tools/nui_tooltip_test.py fails while one of them never "
                    "runs over the corpus. excluded: the lines left out, each with its reason.",
        "uitooltip_sha256": sha256_of(path),
        "lines": dict((str(line), label) for line, label in sorted(live.items())),
        "excluded": dict((str(line), why) for line, why in sorted(excluded.items())),
    }


def trace_rules(world, cases):
    """The uitooltip.py lines run while every case runs on `world`."""
    path = os.path.normcase(os.path.abspath(RULES))
    hit = set()

    def tracer(frame, event, arg):
        if os.path.normcase(frame.f_code.co_filename) != path:
            return None

        def local(frame, event, arg):
            if event == "line":
                hit.add(frame.f_lineno)
            return local
        if event == "call":
            hit.add(frame.f_lineno)
        return local

    old = sys.gettrace()
    sys.settrace(tracer)
    try:
        with world:
            for case in cases:
                run_case(world, case)
    finally:
        sys.settrace(old)
    return hit


# --- the fixtures (spec 6.9): the facades' own models over stand-in items --------------------------------------

FIXTURE_CLOCK_NOW = 1.0   # nui.now() when the models are built: nuitool snap's default --time


def fixture_corpus(sizes="today"):
    """Items and skills for the fixtures: the corpus's rows, changed where a
    fixture needs a state the proto has no item for (a weapon with three
    applies and a first-use time; at the foundation's sizes seven applies)."""
    data = load_corpus()
    items = dict(data["items"])
    weapon = dict(items["10"], name="Sword+9", applies=[["APPLY_ATT_SPEED", 22], ["APPLY_STR", 8], ["APPLY_CRITICAL_PCT", 5]],
                  limits=[[LIMITS["LEVEL"], 30], [0, 0]], values=[0, 0, 15, 109, 113, 45])
    if sizes == "foundation":
        weapon["applies"] = [["APPLY_ATT_SPEED", 22], ["APPLY_STR", 8], ["APPLY_CRITICAL_PCT", 5], ["APPLY_PENETRATE_PCT", 5],
                             ["APPLY_MAX_HP", 1500], ["APPLY_ATTBONUS_MONSTER", 10], ["APPLY_RESIST_WARRIOR", 7]]
    items["90010"] = weapon
    skills = dict(data["skills"])
    skills["1"] = dict(skills["1"], requirement=["Sword Spin", 20], requirement_met=False, require_stats=[], level_limit=5)
    return {"items": items, "skills": skills, "mobs": data["mobs"]}


ATTRS_FIXTURE = [[1, 1500], [5, 12], [7, 10], [15, 8], [16, 6], [43, 10], [44, 10]]


def _model_of(world, kind, calls, case=None):
    """The board's model after `calls` on the world's facade of `kind`."""
    tip = world.tooltip(kind)
    support.apply_case(world.game, case or {"vnum": 0})
    world.game.state.now = FIXTURE_CLOCK_NOW
    for name, args in calls:
        getattr(tip, name)(*args)
    model = published(world, tip)
    return {"lines": model["lines"], "min_w": model["min_w"]}


def fixtures():
    """{(window, variant): fixture} of the three tooltip documents."""
    today = TipWorld(fixture_corpus(), recorder=True)
    found = TipWorld(fixture_corpus("foundation"), recorder=True, sizes="foundation")
    player = {"level": 120, "race": 0}
    out = {}
    with today:
        out[("item-tooltip", "")] = {"item_tooltip": _model_of(today, "item", [["SetInventoryItem", [0]]], {
            "vnum": 90010, "sockets": [28030, SILVER, GOLD], "attrs": ATTRS_FIXTURE, "player": player, "clock": CLOCK})}
        out[("item-tooltip", "costume")] = {"item_tooltip": _model_of(today, "item", [["SetInventoryItem", [0]]], {
            "vnum": 45001, "sockets": [CLOCK + DAY, 0, 0], "attrs": [], "player": player, "clock": CLOCK})}
        out[("item-tooltip", "potion")] = {"item_tooltip": _model_of(today, "item", [["SetInventoryItem", [0]]], {
            "vnum": 27001, "count": 200, "attrs": [], "player": player, "clock": CLOCK})}
        out[("item-tooltip", "accessory")] = {"item_tooltip": _model_of(today, "item", [["SetInventoryItem", [93]]], {
            "vnum": 14000, "pos": 93, "sockets": [2, 3, 5400], "attrs": [], "player": player, "clock": CLOCK})}
        out[("item-tooltip", "shop")] = {"item_tooltip": _model_of(today, "item", [["SetShopItem", [0]]], {
            "vnum": 30329, "sockets": [CLOCK + 300, 0, 0], "attrs": [], "player": player, "clock": CLOCK,
            "shop": {"open": True, "private": False, "price": 1250}})}
        out[("skill-tooltip", "")] = {"skill_tooltip": _model_of(today, "skill", [["SetSkillNew", [1, 1, 2, 5]]], {
            "vnum": 1, "player": {"level": 3, "race": 0},
            "skill": {"vnum": 1, "slot": 1, "grade": 2, "level": 5, "efficient": 0.5, "next": 0.6}})}
        out[("skill-tooltip", "party")] = {"skill_tooltip": _model_of(today, "skill", [["SetSkillNew", [121, 121, 3, 0]]], {
            "vnum": 121, "player": player, "skill": {"vnum": 121, "slot": 121, "grade": 3, "level": 40, "efficient": 1.0, "next": 1.0}})}
        out[("link-tooltip", "")] = {"link_tooltip": _model_of(today, "link", [
            ["SetHyperlinkItem", [_link(90010, [28030, SILVER, 0], ATTRS_FIXTURE[:5]).split(":")]]], {"vnum": 0, "clock": CLOCK, "player": player})}
    with found:
        out[("item-tooltip", "foundation")] = {"item_tooltip": _model_of(found, "item", [["SetInventoryItem", [0]]], {
            "vnum": 90010, "sockets": [28030, SILVER, GOLD, 28030], "attrs": ATTRS_FIXTURE, "player": player, "clock": CLOCK,
            "shop": {"open": True, "private": False, "price": 0}, "sell_price": 2000000000000})}
        # The sage grade (the foundation's fourth grade): C2 adds its name and grade count; the
        # fixture gives the rules both, with the grade's own line.
        tooltip = found.m("uiToolTip")
        found.game.modules["skill"].SKILL_GRADE_COUNT = 4
        tooltip.SkillToolTip.SKILL_GRADE_NAME[4] = "Sage %s"
        out[("skill-tooltip", "foundation")] = {"skill_tooltip": _model_of(found, "skill", [["SetSkillNew", [1, 1, 4, 50]]], {
            "vnum": 1, "player": player, "skill": {"vnum": 1, "slot": 1, "grade": 4, "level": 50, "efficient": 1.0, "next": 1.0}})}
        # A link with four sockets (C2 changes SetHyperlinkItem's tokens[3:6], spec 11): the
        # rules' AddItemData, as the changed SetHyperlinkItem calls it.
        out[("link-tooltip", "foundation")] = {"link_tooltip": _model_of(found, "link", [
            ["ClearToolTip", []], ["AddItemData", [90010, [28030, SILVER, GOLD, 28030], [tuple(a) for a in ATTRS_FIXTURE]]],
            ["ShowToolTip", []]], {"vnum": 0, "clock": CLOCK, "player": player})}
    out.update(dialog_fixtures())
    return out


def _materials(corpus, count=2):
    """Refine materials with icons the asset tree has: the corpus's
    materials, lowest first."""
    found = []
    for vnum in sorted(int(v) for v in corpus["items"]):
        row = corpus["items"][str(vnum)]
        if row["type_name"] in ("MATERIAL", "RESOURCE") and os.path.isfile(
                os.path.join(REPO, "assets", "icon", row.get("icon", "").replace("\\", "/"))):
            found.append(vnum)
        if len(found) == count:
            break
    return found


def dialog_fixtures():
    """{(window, variant): fixture} of the refine and attach dialogs: each
    dialog's own model after legacy's Open (and the materials) on the
    NovaUI side."""
    out = {}
    for sizes in ("today", "foundation"):
        data = fixture_corpus(sizes)
        data["items"]["3001"] = dict(data["items"]["3000"], name="Glaive+1")
        world = DialogWorld(data, recorder=True, sizes=sizes)
        sockets = [28030, SILVER, GOLD] + ([SILVER] if sizes == "foundation" else [])
        materials = _materials(data)
        with world:
            world.game.state.now = FIXTURE_CLOCK_NOW
            dialog = world.make("new")
            place_items(world, {"vnum": 0, "player": {"level": 120, "race": 0}, "clock": CLOCK},
                        [{"pos": 5, "vnum": 3000, "sockets": sockets, "attrs": ATTRS_FIXTURE[:5]}])
            cost = 2000000000000 if sizes == "foundation" else 25000
            with quiet():
                dialog.Open(5, 3001, cost, 90, 0)
                for vnum, count in zip(materials, (2, 1)):
                    dialog.AppendMaterial(vnum, count)
            out[("refine", "" if sizes == "today" else "foundation")] = {"refine": dict(dialog._state)}
            dialog.Close()
            if sizes == "today":
                old = world.make("old")
                place_items(world, {"vnum": 0, "player": {"level": 120, "race": 0}, "clock": CLOCK},
                            [{"pos": 1, "vnum": 25040}, {"pos": 5, "vnum": 10, "sockets": [28030, SILVER, 0]}])
                with quiet():
                    old.Open(1, 5)
                out[("refine", "old")] = {"refine": dict(old._state)}
                old.Close()
            attach = world.make("attach")
            place_items(world, {"vnum": 0, "player": {"level": 120, "race": 0}, "clock": CLOCK},
                        [{"pos": 2, "vnum": 28030}, {"pos": 0, "vnum": 10, "sockets": [SILVER, SILVER, 0] + ([GOLD] if sizes == "foundation" else []),
                                                     "attrs": ATTRS_FIXTURE[:3]}])
            with quiet():
                attach.Open(2, 0)
            out[("attach-metin", "" if sizes == "today" else "foundation")] = {"attach_metin": dict(attach._state)}
            attach.Close()
    return out


# --- the command line ---------------------------------------------------------------------------------------

def _text(value):
    return json.dumps(value, indent="\t", ensure_ascii=False, sort_keys=False) + "\n"


def _write(path, text, check):
    old = None
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            old = handle.read()
    if old == text:
        return False
    if check:
        print("stale: %s" % os.path.relpath(path, REPO))
        return True
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print("wrote %s" % os.path.relpath(path, REPO))
    return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("corpus", "fixtures", "coverage", "report"))
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 when an output is stale")
    parser.add_argument("--out", default=REPORT, help="report: where to write it (default %(default)s)")
    parser.add_argument("--proto", default=DEFAULT_PROTO)
    parser.add_argument("--names", default=DEFAULT_NAMES)
    parser.add_argument("--mobs", default=DEFAULT_MOBS)
    args = parser.parse_args(argv)
    if args.command == "corpus":
        stale = _write(CORPUS, _text(build_corpus(args.proto, args.names, args.mobs)), args.check)
        stale = _write(BRANCHES, _text(branch_list()), args.check) or stale
        return 1 if stale else 0
    if args.command == "report":
        with quiet():
            out = report(load_corpus())
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(_text(out))
        print("%d cases, %d differences, %d of %d live rule lines run, gap values %s; wrote %s" % (
            out["cases"], len(out["differences"]), out["coverage"]["run"], out["coverage"]["live_lines"],
            out["gap_values"] or "none", args.out))
        return 1 if out["differences"] or out["coverage"]["missing"] else 0
    if args.command == "coverage":
        corpus = load_corpus()
        live, excluded = rule_lines()
        hit = trace_rules(TipWorld(corpus, recorder=False), corpus["cases"])
        missing = sorted(line for line in live if line not in hit)
        with open(RULES, encoding="utf-8") as handle:
            source = handle.read().split("\n")
        for line in missing:
            print("%5d  %-55s %s" % (line, live[line], source[line - 1].strip()[:90]))
        print("%d of %d live rule lines run; %d excluded" % (len(live) - len(missing), len(live), len(excluded)))
        return 1 if missing else 0
    stale = False
    for (window, variant), model in sorted(fixtures().items()):
        name = "%s.%s.fixture.json" % (window, variant) if variant else "%s.fixture.json" % window
        stale = _write(os.path.join(WINDOWS, window, name), _text(model), args.check) or stale
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
