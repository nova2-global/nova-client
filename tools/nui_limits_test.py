"""Tests for assets/root/nui_limits.py, the counts and limits of the NovaUI
item windows (P14 spec 3): python3 -B -m unittest nui_limits_test (from
tools/).

Plain CPython: read() over stand-in modules (types.SimpleNamespace), today's
client (no constant beyond what the exe exposes today) and the foundation's
names; the wear tables against the legacy refresh and against every skin's
sheets."""
import glob
import os
import re
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_test_support as support  # noqa: E402

REPO = os.path.normpath(os.path.join(support.HERE, ".."))
NUI = os.path.join(REPO, "assets", "nui", "nui")


def load():
    modules = support.Modules(dbg=support.make_dbg(), localeInfo=support.LocaleInfo(
        NumberToMoneyString=lambda n: "%s Yang" % "{:,}".format(int(n)).replace(",", ".")))
    for name in ("player", "item", "skill", "app", "introselect"):
        modules.put(name, None)
    module = modules.load("nui_limits")
    return modules, module


def today_modules():
    """What today's exe exposes (PythonPlayerModule.cpp, PythonItemModule.cpp,
    PythonSkill), nothing proposed."""
    player = types.SimpleNamespace(INVENTORY_PAGE_SIZE=45, INVENTORY_PAGE_COUNT=2, INVENTORY_SLOT_COUNT=168,
                                   EQUIPMENT_SLOT_START=90, METIN_SOCKET_MAX_NUM=3, ATTRIBUTE_SLOT_MAX_NUM=7,
                                   DRAGON_SOUL_PAGE_SIZE=32, DRAGON_SOUL_PAGE_COUNT=5, DRAGON_SOUL_SLOT_COUNT=960,
                                   DRAGON_SOUL_EQUIPMENT_SLOT_START=122, DRAGON_SOUL_EQUIPMENT_PAGE_COUNT=2,
                                   DRAGON_SOUL_EQUIPMENT_FIRST_SIZE=6, EQUIPMENT_PAGE_COUNT=12,
                                   NEW_EQUIPMENT_SLOT_START=111, NEW_EQUIPMENT_SLOT_COUNT=3)
    item = types.SimpleNamespace(COSTUME_SLOT_START=109, COSTUME_SLOT_COUNT=2, BELT_INVENTORY_SLOT_START=152,
                                 BELT_INVENTORY_SLOT_COUNT=16, ITEM_APPLY_MAX_NUM=3, ITEM_SOCKET_MAX_NUM=3,
                                 LIMIT_MAX_NUM=2)
    skill = types.SimpleNamespace(SKILL_GRADE_COUNT=3)
    return {"player": player, "item": item, "skill": skill, "app": types.SimpleNamespace()}


def foundation_modules(module):
    """Stand-ins holding every name the foundation wave was asked to expose,
    with its targets (P14 spec 3.2, 11)."""
    player = types.SimpleNamespace(INVENTORY_PAGE_SIZE=45, INVENTORY_PAGE_COUNT=5, INVENTORY_PAGE_COLUMNS=5,
                                   INVENTORY_SLOT_COUNT=311, EQUIPMENT_SLOT_START=225, METIN_SOCKET_MAX_NUM=4,
                                   ATTRIBUTE_SLOT_MAX_NUM=7, GOLD_MAX=2000000000000, MONEY_DIGITS=13,
                                   SKILL_MAX_LEVEL=50, SKILL_GRADE_SAGE_MASTER=4, PLAYER_MAX_LEVEL=150,
                                   DRAGON_SOUL_PAGE_SIZE=32, DRAGON_SOUL_PAGE_COUNT=5, DRAGON_SOUL_SLOT_COUNT=960,
                                   DRAGON_SOUL_EQUIPMENT_SLOT_START=265, DRAGON_SOUL_EQUIPMENT_PAGE_COUNT=2,
                                   DRAGON_SOUL_EQUIPMENT_FIRST_SIZE=6)
    item = types.SimpleNamespace(COSTUME_SLOT_START=244, COSTUME_SLOT_COUNT=11, BELT_INVENTORY_SLOT_START=295,
                                 BELT_INVENTORY_SLOT_COUNT=16, BELT_INVENTORY_WIDTH=4, ITEM_APPLY_MAX_NUM=7,
                                 ITEM_SOCKET_MAX_NUM=4, LIMIT_MAX_NUM=2, ITEM_COUNT_MAX=2000, WEAR_MAX_NUM=40)
    for index, (name, _, _, _) in enumerate(module.OLD_WEAR):
        setattr(item, "WEAR_" + name.upper(), index)
    skill = types.SimpleNamespace(SKILL_GRADE_COUNT=4)
    introselect = types.SimpleNamespace(SLOT_COUNT=5)
    return {"player": player, "item": item, "skill": skill, "app": types.SimpleNamespace(), "introselect": introselect}


class LimitsTest(unittest.TestCase):
    def setUp(self):
        self.modules, self.m = load()
        self.addCleanup(self.modules.restore)


class Reading(LimitsTest):
    def test_read_with_no_modules_equals_today(self):
        limits = self.m.read({})
        for key, value in self.m.TODAY.items():
            if key != "MONEY_DIGITS":
                self.assertEqual(getattr(limits, key), value, key)
        self.assertEqual(limits.MONEY_DIGITS, 10, "the digits of today's 2,000,000,000")
        self.assertEqual(limits.WEAR_TABLE_ID, "new")
        self.assertEqual(self.m.LIMITS, limits, "outside the client every value falls back")
        self.assertIn("INVENTORY_PAGE_COUNT", limits.fell_back)

    def test_read_of_todays_exe_equals_today_and_names_the_proposed_keys_as_fallbacks(self):
        limits = self.m.read(today_modules())
        self.assertEqual(limits, self.m.read({}))
        self.assertEqual(sorted(limits.fell_back),
                         sorted(["INVENTORY_COLUMNS", "WEAR_SLOT_COUNT", "BELT_COLUMNS", "STACK_MAX", "GOLD_MAX",
                                 "MONEY_DIGITS", "INVENTORY_MONEY_DIGITS", "SKILL_LEVEL_MAX", "SKILL_GRADE_SAGE",
                                 "PLAYER_LEVEL_MAX", "CHARACTER_SLOT_COUNT", "WEAR_TABLE"] + list(WAVE4_PROPOSED)))

    def test_the_foundations_names_give_the_foundation(self):
        limits = self.m.read(foundation_modules(self.m))
        self.assertEqual(limits, self.m.foundation())
        self.assertEqual(limits.fell_back, ())
        self.assertEqual(limits.WEAR_TABLE_ID, "old")
        for key in ("INVENTORY_PAGE_COUNT", "WEAR_SLOT_COUNT", "METIN_SOCKET_MAX_NUM", "ITEM_APPLY_MAX_NUM",
                    "STACK_MAX", "GOLD_MAX", "MONEY_DIGITS", "INVENTORY_MONEY_DIGITS"):
            self.assertEqual(getattr(limits, key), self.m.FOUNDATION[key], key)

    def test_each_key_falls_back_alone(self):
        for key, names in self.m.NAMES.items():
            if key == "WEAR_TABLE":
                continue
            modules = foundation_modules(self.m)
            for module_name, attribute in names:
                if module_name in modules and hasattr(modules[module_name], attribute):
                    delattr(modules[module_name], attribute)
            limits = self.m.read(modules)
            self.assertIn(key, limits.fell_back, key)
            # Keys read from the same names fall back together (MONEY_DIGITS
            # and INVENTORY_MONEY_DIGITS both read player.MONEY_DIGITS).
            sharing = [k for k, n in self.m.NAMES.items() if k != key and set(n) <= set(names)]
            others = [k for k in limits.fell_back if k != key and k not in sharing]
            if key == "MONEY_DIGITS":
                self.assertEqual(limits.MONEY_DIGITS, 13, "derived from GOLD_MAX")
            elif key == "WEAR_SLOT_COUNT":
                self.assertEqual(limits.WEAR_TABLE_ID, "new", "40 names and no count: today's table")
            else:
                self.assertEqual(getattr(limits, key), self.m.TODAY[key], key)
            self.assertEqual(others, [], "only %s fell back (%s)" % (key, others))

    def test_a_value_that_is_not_an_int_or_a_raising_module_falls_back(self):
        class Raising(object):
            def __getattr__(self, name):
                raise RuntimeError(name)
        modules = today_modules()
        modules["player"].INVENTORY_PAGE_COUNT = "5"
        modules["item"] = Raising()
        limits = self.m.read(modules)
        self.assertEqual(limits.INVENTORY_PAGE_COUNT, 2)
        self.assertEqual(limits.COSTUME_SLOT_START, 109)
        modules["player"].INVENTORY_PAGE_COUNT = True
        self.assertEqual(self.m.read(modules).INVENTORY_PAGE_COUNT, 2, "a bool is no count")

    def test_the_limits_are_read_only_and_use_restores_limits(self):
        limits = self.m.foundation()
        with self.assertRaises(AttributeError):
            limits.INVENTORY_PAGE_COUNT = 3
        self.assertIs(self.m.current(), self.m.LIMITS)
        self.m.use(limits)
        self.assertIs(self.m.current(), limits)
        self.m.use(None)
        self.assertIs(self.m.current(), self.m.LIMITS)

    def test_read_logs_once_which_keys_fell_back(self):
        dbg = sys.modules["dbg"]
        self.assertEqual(len(dbg.lines), 1, "the import's read() logged once")
        del dbg.lines[:]
        self.m.read({})
        self.assertEqual(dbg.lines, [], "a test's read() logs nothing")
        self.m.read()
        self.assertEqual(len(dbg.lines), 1)
        self.assertTrue(dbg.lines[0].startswith("nui_limits: today's values for "), dbg.lines[0])


class Derived(LimitsTest):
    def test_the_derived_keys(self):
        today, foundation = self.m.read({}), self.m.foundation()
        self.assertEqual((today.INVENTORY_ROWS, foundation.INVENTORY_ROWS), (9, 9))
        self.assertEqual((today.STACK_DIGITS, foundation.STACK_DIGITS), (3, 4))
        self.assertEqual((today.SELECT_ITEM_SCAN, foundation.SELECT_ITEM_SCAN), (90, 225))
        self.assertEqual((today.MONEY_DIGITS, foundation.MONEY_DIGITS), (10, 13))
        self.assertEqual(len(str(foundation.GOLD_MAX)), 13)

    def test_pages_for_two_and_five(self):
        today, foundation = self.m.read({}), self.m.foundation()
        self.assertEqual(self.m.pages(today), [
            {"index": 0, "label": "I", "hint": "@ui.INVENTORY_PAGE_BUTTON_TOOLTIP_1"},
            {"index": 1, "label": "II", "hint": "@ui.INVENTORY_PAGE_BUTTON_TOOLTIP_2"}])
        self.assertEqual([p["label"] for p in self.m.pages(foundation)], ["I", "II", "III", "IV", "V"])
        self.assertEqual(self.m.pages(foundation)[4]["hint"], "@ui.INVENTORY_PAGE_BUTTON_TOOLTIP_5")
        self.m.use(foundation)
        self.addCleanup(self.m.use, None)
        self.assertEqual(len(self.m.pages()), 5, "current() by default")

    def test_money_text_formats_64_bit_gold(self):
        self.assertEqual(self.m.money_text(1999999999), "1.999.999.999 Yang")
        self.assertEqual(self.m.money_text(2000000000000), "2.000.000.000.000 Yang")
        self.assertEqual(self.m.money_text(2 ** 40 + 0.0), "1.099.511.627.776 Yang")


class WearTables(LimitsTest):
    def test_the_tables_counts_by_group(self):
        def counts(limits):
            return [len(self.m.wear_group(group, limits)) for group in ("equipment", "costume", "hidden")]
        today, foundation = self.m.read({}), self.m.foundation()
        self.assertEqual(len(self.m.wear_table(today)), 24)
        self.assertEqual(len(self.m.wear_table(foundation)), 40)
        self.assertEqual(counts(today), [12, 3, 9])
        self.assertEqual(counts(foundation), [15, 17, 8])
        self.assertRaises(ValueError, self.m.wear_group, "bag", today)

    def test_a_wear_slot_is_its_index_name_cell_group_and_span(self):
        today, foundation = self.m.read({}), self.m.foundation()
        weapon = [slot for slot in self.m.wear_table(today) if slot.name == "weapon"][0]
        self.assertEqual(tuple(weapon), (4, "weapon", 94, "equipment", 1, 3))
        self.assertEqual((weapon.index, weapon.cell, weapon.w, weapon.h), (4, 94, 1, 3))
        belt = [slot for slot in self.m.wear_table(foundation) if slot.name == "belt"][0]
        self.assertEqual(tuple(belt), (30, "belt", 255, "equipment", 1, 1))
        self.assertEqual([slot.index for slot in self.m.wear_table(today)], list(range(24)), "wear order")
        self.assertEqual([slot.index for slot in self.m.wear_table(foundation)], list(range(40)))

    def test_todays_shown_cells_are_the_ones_legacy_refreshes(self):
        """RefreshEquipSlotWindow (uiinventory.py:594-619): EQUIPMENT_PAGE_COUNT
        (12) cells from EQUIPMENT_SLOT_START, wear 0 to 11, of which ability1
        shows nothing (no legacy slot), then NEW_EQUIPMENT_SLOT_COUNT (3) from
        NEW_EQUIPMENT_SLOT_START, wear 21 to 23, of which the equipment window
        holds the belt; RefreshCostumeSlot (:87-94): COSTUME_SLOT_COUNT (2)
        costume cells. The third costume cell, ring1, legacy never refreshes
        (P14 spec 2.1)."""
        today = self.m.read({})
        refreshed = set(range(90, 102)) | set(range(111, 114))
        equipment = [slot.cell for slot in self.m.wear_group("equipment", today)]
        self.assertTrue(set(equipment) <= refreshed)
        self.assertEqual(sorted(refreshed - set(equipment)), [101, 111, 112], "ability1, ring1, ring2")
        costume = [slot.cell for slot in self.m.wear_group("costume", today)]
        self.assertEqual(costume, [109, 110, 111])
        self.assertEqual(costume[:2], list(range(today.COSTUME_SLOT_START, today.COSTUME_SLOT_START + today.COSTUME_SLOT_COUNT)))
        legacy_slots = re.findall(r'"index":EQUIPMENT_START_INDEX\+(\d+)',
                                  open(os.path.join(REPO, "assets", "uiscript", "uiscript", "inventorywindow.py"),
                                       encoding="latin-1").read())
        self.assertEqual(sorted(90 + int(n) for n in legacy_slots) + [113], sorted(equipment),
                         "the legacy equipment slots and the belt")

    def test_the_old_table_follows_the_constants_order_when_every_name_resolves(self):
        modules = foundation_modules(self.m)
        del modules["item"].WEAR_COSTUME_AURA
        self.assertEqual(self.m.read(modules).WEAR_TABLE_ID, "new", "one OLD name missing: today's table")

    def test_every_name_has_a_place_class_in_every_skins_sheets(self):
        """inv-wear--<name> and cos-wear--<name> for every name of both tables
        in the classic sheets (one rule per table class) and in the modern
        window sheets (P14 spec 3.3)."""
        sheets = {"inventory": "inv-wear--", "costume": "cos-wear--"}
        groups = {"inventory": ("equipment",), "costume": ("costume",)}
        today, foundation = self.m.read({}), self.m.foundation()
        for window, prefix in sheets.items():
            if not os.path.isfile(os.path.join(NUI, "windows", window, window + ".rcss")):
                self.skipTest("the %s window is not written yet" % window)
            modern = open(os.path.join(NUI, "windows", window, window + ".rcss"), encoding="utf-8").read()
            classic = open(os.path.join(NUI, "skins", "classic", "windows", window + ".rcss"), encoding="utf-8").read()
            for table_class, limits in (("inv--table-new", today), ("inv--table-old", foundation)):
                names = [slot.name for group in groups[window] for slot in self.m.wear_group(group, limits)]
                for name in names:
                    self.assertIn("." + prefix + name, modern, "%s: %s has no modern place" % (window, name))
                    self.assertRegex(classic, r"\.%s[^{]*\.%s%s\b" % (re.escape(table_class), re.escape(prefix), re.escape(name)),
                                     "%s: %s has no classic place for %s" % (window, name, table_class))


# --- Wave 4 (P16 spec 3) ----------------------------------------------------------------

# The Wave 4 keys whose names the foundation wave's C2 was asked to expose:
# today's exe falls back for them.
WAVE4_PROPOSED = ("EXCHANGE_COLUMNS", "EXCHANGE_MONEY_DIGITS", "SHOP_TAB_COUNT_MAX", "SAFEBOX_PAGE_COUNT_MAX",
                  "SAFEBOX_SLOT_COUNT_MAX", "SAFEBOX_PASSWORD_MAX_LEN", "WINDOW_BELT_INVENTORY", "VIEW_EQUIP_SLOT_NUM",
                  "GUILD_NAME_MAX_LEN", "GUILD_GRADE_NAME_MAX_LEN", "GUILD_GRADE_COUNT", "GUILD_COMMENT_MAX_LEN",
                  "PLAYER_NAME_SHOWN_MAX")
# Every Wave 4 key and its fallback, today's and the foundation's values.
WAVE4_KEYS = ("EXCHANGE_ITEM_MAX_NUM", "EXCHANGE_COLUMNS", "EXCHANGE_MONEY_DIGITS", "SHOP_SLOT_COUNT", "SHOP_COLUMNS",
              "SHOP_TAB_COUNT_MAX", "PRIVATE_SHOP_SIGN_MAX", "SAFEBOX_COLUMNS", "SAFEBOX_PAGE_ROWS", "SAFEBOX_PAGE_SIZE",
              "SAFEBOX_PAGE_COUNT_MAX", "SAFEBOX_SLOT_COUNT_MAX", "SAFEBOX_PASSWORD_MAX_LEN", "MALL_SLOT_COUNT",
              "WINDOW_SAFEBOX", "WINDOW_MALL", "WINDOW_DRAGON_SOUL_INVENTORY", "WINDOW_BELT_INVENTORY", "WINDOW_GROUND",
              "VIEW_EQUIP_SLOT_NUM", "GUILD_NAME_MAX_LEN", "GUILD_GRADE_NAME_MAX_LEN", "GUILD_GRADE_COUNT",
              "GUILD_COMMENT_MAX_LEN", "GUILD_BOARD_LINES", "GUILD_MEMBER_LINES", "GUILD_MEMBER_MAX", "GUILD_ENEMY_SLOTS",
              "GUILD_SKILL_ROW", "GUILD_BUILDING_ROWS", "GUILD_RESOURCE_COLUMNS", "PLAYER_NAME_INPUT_MAX",
              "PLAYER_NAME_SHOWN_MAX")
WAVE4_FOUNDATION = {"EXCHANGE_MONEY_DIGITS": 13, "SAFEBOX_PAGE_COUNT_MAX": 5, "SAFEBOX_SLOT_COUNT_MAX": 225,
                    "WINDOW_BELT_INVENTORY": 7, "WINDOW_GROUND": 12, "VIEW_EQUIP_SLOT_NUM": 16, "GUILD_NAME_MAX_LEN": 24,
                    "PLAYER_NAME_SHOWN_MAX": 22}

_today_modules_3b, _foundation_modules_3b = today_modules, foundation_modules


def today_modules():
    """What today's exe exposes, the Wave 4 modules' constants included
    (PythonExchangeModule.cpp, PythonShop.cpp, PythonSafeBox.cpp,
    PythonGuild.cpp, PythonCharacterModule.cpp, PythonPlayerModule.cpp's
    window enum), nothing proposed."""
    modules = _today_modules_3b()
    for name, value in (("SAFEBOX", 3), ("MALL", 4), ("DRAGON_SOUL_INVENTORY", 5), ("GROUND", 6)):
        setattr(modules["player"], name, value)
    modules["exchange"] = types.SimpleNamespace(EXCHANGE_ITEM_MAX_NUM=12)
    modules["shop"] = types.SimpleNamespace(SHOP_SLOT_COUNT=40, SHOP_COIN_TYPE_GOLD=0, SHOP_COIN_TYPE_SECONDARY_COIN=1)
    modules["safebox"] = types.SimpleNamespace(SAFEBOX_SLOT_X_COUNT=5, SAFEBOX_SLOT_Y_COUNT=9, SAFEBOX_PAGE_SIZE=45)
    modules["guild"] = types.SimpleNamespace(ENEMY_GUILD_SLOT_MAX_COUNT=6)
    modules["chr"] = types.SimpleNamespace(PLAYER_NAME_MAX_LEN=12)
    return modules


def foundation_modules(module):
    """The foundation's names (P14 spec 3.2, 11) and Wave 4's (P16 spec 3.3,
    13), with their targets."""
    modules = _foundation_modules_3b(module)
    for name, value in (("SAFEBOX", 3), ("MALL", 4), ("DRAGON_SOUL_INVENTORY", 5), ("BELT_INVENTORY", 7),
                        ("GROUND", 12), ("VIEW_EQUIP_SLOT_NUM", 16)):
        setattr(modules["player"], name, value)
    modules["exchange"] = types.SimpleNamespace(EXCHANGE_ITEM_MAX_NUM=12, EXCHANGE_COLUMNS=4)
    modules["shop"] = types.SimpleNamespace(SHOP_SLOT_COUNT=40, SHOP_TAB_COUNT_MAX=3)
    modules["safebox"] = types.SimpleNamespace(SAFEBOX_SLOT_X_COUNT=5, SAFEBOX_SLOT_Y_COUNT=9, SAFEBOX_PAGE_SIZE=45,
                                               SAFEBOX_PAGE_COUNT_MAX=5, SAFEBOX_MAX_NUM=225, SAFEBOX_PASSWORD_MAX_LEN=6)
    modules["guild"] = types.SimpleNamespace(ENEMY_GUILD_SLOT_MAX_COUNT=6, GUILD_NAME_MAX_LEN=24, GUILD_GRADE_NAME_MAX_LEN=8,
                                             GUILD_GRADE_COUNT=15, GUILD_COMMENT_MAX_LEN=50)
    modules["chr"] = types.SimpleNamespace(PLAYER_NAME_MAX_LEN=12, PLAYER_NAME_SHOWN_MAX=22)
    return modules


class Wave4Keys(LimitsTest):
    """P16 spec 3.1 and 3.2."""

    def test_every_wave4_key_has_today_s_value_without_the_client(self):
        limits = self.m.read({})
        for key in WAVE4_KEYS:
            self.assertIn(key, self.m.TODAY, key)
            self.assertEqual(getattr(limits, key), self.m.TODAY[key], key)
        self.assertEqual((limits.EXCHANGE_ITEM_MAX_NUM, limits.EXCHANGE_COLUMNS, limits.EXCHANGE_MONEY_DIGITS), (12, 4, 7))
        self.assertEqual((limits.SAFEBOX_PAGE_SIZE, limits.SAFEBOX_PAGE_COUNT_MAX, limits.SAFEBOX_SLOT_COUNT_MAX), (45, 3, 135))
        self.assertEqual((limits.WINDOW_SAFEBOX, limits.WINDOW_MALL, limits.WINDOW_DRAGON_SOUL_INVENTORY,
                          limits.WINDOW_BELT_INVENTORY, limits.WINDOW_GROUND), (3, 4, 5, 7, 6),
                         "the client's EWindows (GameType.h): GROUND 6, BELT_INVENTORY 7")

    def test_the_foundation_s_wave4_values(self):
        foundation = self.m.foundation()
        for key in WAVE4_KEYS:
            self.assertEqual(getattr(foundation, key), WAVE4_FOUNDATION.get(key, self.m.TODAY[key]), key)

    def test_the_stand_ins_with_the_foundation_s_names_give_the_foundation_s_wave4_values(self):
        limits = self.m.read(foundation_modules(self.m))
        for key in WAVE4_KEYS:
            self.assertEqual(getattr(limits, key), getattr(self.m.foundation(), key), key)
        self.assertFalse([key for key in limits.fell_back if key in WAVE4_KEYS])

    def test_every_wave4_key_falls_back_alone(self):
        for key in WAVE4_KEYS:
            names = self.m.NAMES.get(key)
            if names is None:
                continue
            modules = foundation_modules(self.m)
            for module_name, attribute in names:
                if module_name in modules and hasattr(modules[module_name], attribute):
                    delattr(modules[module_name], attribute)
            limits = self.m.read(modules)
            sharing = [k for k, n in self.m.NAMES.items() if k != key and set(n) <= set(names)]
            self.assertIn(key, limits.fell_back, key)
            self.assertEqual([k for k in limits.fell_back if k != key and k not in sharing], [], key)
            self.assertEqual(getattr(limits, key), self.m.TODAY[key], key)

    def test_a_missing_or_raising_wave4_module_falls_back_and_read_imports_them(self):
        class Raising(object):
            def __getattr__(self, name):
                raise RuntimeError(name)
        modules = today_modules()
        modules["safebox"] = Raising()
        del modules["exchange"]
        limits = self.m.read(modules)
        self.assertEqual((limits.SAFEBOX_PAGE_SIZE, limits.EXCHANGE_ITEM_MAX_NUM), (45, 12))
        self.assertIn("SAFEBOX_PAGE_SIZE", limits.fell_back)
        self.assertIn("EXCHANGE_ITEM_MAX_NUM", limits.fell_back)
        self.assertEqual(self.m._IMPORTED_W4, ("exchange", "shop", "safebox", "guild", "chr"))
        sys.modules["safebox"] = types.SimpleNamespace(SAFEBOX_PAGE_COUNT_MAX=5)
        self.addCleanup(sys.modules.pop, "safebox", None)
        self.assertEqual(self.m.read().SAFEBOX_PAGE_COUNT_MAX, 5, "read() finds a loaded Wave 4 module")

    def test_the_window_keys(self):
        self.assertEqual(self.m.WINDOW_KEYS_W4, ("WINDOW_SAFEBOX", "WINDOW_MALL", "WINDOW_DRAGON_SOUL_INVENTORY",
                                                 "WINDOW_BELT_INVENTORY", "WINDOW_GROUND"))
        for key in self.m.WINDOW_KEYS_W4:
            self.assertIn(key, WAVE4_KEYS)


class SafeboxPages(LimitsTest):
    def test_legacy_s_rule_today_and_at_the_foundation(self):
        today, foundation = self.m.read({}), self.m.foundation()
        self.assertEqual(self.m.safebox_pages(27, today),
                         [{"index": 0, "label": "I"}, {"index": 1, "label": "II"}, {"index": 2, "label": "III"}])
        self.assertEqual([p["label"] for p in self.m.safebox_pages(45, foundation)], ["I", "II", "III", "IIII", "IIIII"])
        self.assertEqual(self.m.safebox_pages(9, today), [{"index": 0, "label": "I"}])
        self.assertEqual(self.m.safebox_pages(3, today), [{"index": 0, "label": "I"}], "at least one page")
        self.assertEqual(len(self.m.safebox_pages(45, today)), 3, "today's cap of 3 (min(3, ...))")
        self.assertEqual(len(self.m.safebox_pages(18, today)), 2)
        self.m.use(foundation)
        self.addCleanup(self.m.use, None)
        self.assertEqual(len(self.m.safebox_pages(45)), 5, "current() by default")


class ViewEquipTable(LimitsTest):
    def test_today_s_eleven_wear_positions(self):
        today = self.m.read({})
        table = self.m.view_equip_table(today)
        self.assertEqual([tuple(slot) for slot in table], [
            (0, "body", "shown"), (1, "head", "shown"), (2, "foots", "shown"), (3, "wrist", "shown"), (4, "weapon", "shown"),
            (5, "neck", "shown"), (6, "ear", "shown"), (7, "unique1", "shown"), (8, "unique2", "shown"),
            (9, "arrow", "shown"), (10, "shield", "shown")])
        self.assertEqual((table[4].index, table[4].name, table[4].group), (4, "weapon", "shown"))
        wear = dict((slot.index, slot.name) for slot in self.m.wear_table(today))
        self.assertEqual([slot.name for slot in table], [wear[i] for i in range(11)], "the wear table's names")
        self.assertEqual(self.m.view_equip_id(today), "new")

    def test_the_foundation_s_sixteen_in_old_s_position_list(self):
        foundation = self.m.foundation()
        table = self.m.view_equip_table(foundation)
        self.assertEqual(len(table), 16)
        self.assertEqual([slot.name for slot in table[:11]], [slot.name for slot in self.m.view_equip_table(self.m.read({}))])
        self.assertEqual([tuple(slot) for slot in table[11:]], [
            (11, "costume_body", "hidden"), (12, "costume_hair", "hidden"), (13, "ring1", "shown"),
            (14, "ring2", "shown"), (15, "belt", "shown")])
        self.assertEqual(self.m.view_equip_id(foundation), "old")
        names = set(slot.name for slot in self.m.wear_table(foundation))
        self.assertTrue(set(slot.name for slot in table) <= names, "every view name is a wear name")

    def test_every_shown_view_name_has_a_place_class_in_every_skin_s_sheets(self):
        """eqv-place--<name> for every shown slot of both tables in the modern
        sheet and in the classic overlay (one rule per table class)."""
        window = "equipment-view"
        sheet = os.path.join(NUI, "windows", window, window + ".rcss")
        if not os.path.isfile(sheet):
            self.skipTest("the equipment view is not written yet")
        modern = open(sheet, encoding="utf-8").read()
        classic = open(os.path.join(NUI, "skins", "classic", "windows", window + ".rcss"), encoding="utf-8").read()
        for table_class, limits in (("eqv--table-new", self.m.read({})), ("eqv--table-old", self.m.foundation())):
            for slot in self.m.view_equip_table(limits):
                if slot.group != "shown":
                    continue
                self.assertIn(".eqv-place--" + slot.name, modern, "%s has no modern place" % slot.name)
                self.assertRegex(classic, r"\.%s[^{]*\.eqv-place--%s\b" % (re.escape(table_class), re.escape(slot.name)),
                                 "%s has no classic place for %s" % (slot.name, table_class))


if __name__ == "__main__":
    unittest.main()
