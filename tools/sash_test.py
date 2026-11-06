"""Tests for the legacy client's sash (wave 6, chunk Y; NOVA-20, OLD's
__SASH_SYSTEM__): python3 -B -m unittest sash_test (from tools/).

The C++ half (the sash module of OLD's PythonSash.cpp over CG/GC::SASH, the
ActSash and AlertSash callbacks, item.COSTUME_TYPE_SASH, the sash part) is
chunk C's; the combination and absorption rules are chunk SS's. Here the
legacy Python runs over nui_game_support's stand-ins with C's names
(wave6_support):
- uisash.CombineWindow and AbsorbWindow and their uiscripts (OLD
  root/uiSash.py): open, a drop on a slot (sash.Add), a press on an item
  (sash.Remove), the server's refresh with the result in the third slot and
  the price, accept (with the combine-all flag), close, the walk away; the
  cells of the items in the window take no mouse event while it shows;
- Interface.ActSash and game.ActSash and AlertSash (OLD interfaceModule.py:
  3270-3303, game.py:3628-3637);
- the inventory: a right-click into the open window (slot 255, OLD
  uiInventory.py:2522-2525), the sash's bonus scroll's refusal and question
  (OLD :2071-2108), the costume window's sash cell (wear 21);
- uitooltip: the absorption rate and the absorbed item's power, applies
  and bonuses at the rate (CalcSashValue, OLD uiToolTip.py:1103-1114,
  1509-1560), the combine and absorb results (OLD :2839-2990);
- playersettingmodule: every race hangs the sash from Bip01 Spine2;
- every key in all 17 locales."""
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import legacy_foundation_test as lf  # noqa: E402
import wave6_support as w6  # noqa: E402

support = w6.support
SASH_CELL = w6.C_ITEM["COSTUME_SLOT_SASH"]
SWORD_CELL, SASH_IN_BAG, SASH2_IN_BAG = 7, 3, 4
SCROLL_CELL, SCROLL = 9, 39046

GAME_KEYS = {
    "SASH_REFINE_COST": "Absorption price: %d",
    "SASH_ABSORB_CHANCE": "Absorption rate: %d%%",
    "SASH_ABSORB_CHANCE2": "Absorption rate: %d%% ~ %d%%",
    "SASH_DO_YOU_CLEAN": "Do you want to remove all available bonuses?",
    "SASH_FAILURE_CLEAN": "No bonuses can be taken away.",
    "SASH_DEL_SERVEITEM": "Sash 2 will be destroyed should the combination fail.",
    "SASH_DEL_ABSORDITEM": "Absorb item, destroying it in the process?",
    "SASH_AUTO_COMBINE": "Combine all from inventory",
}
INTERFACE_KEYS = {"SASH_ABSORB": "Bonus Absorption", "SASH_COMBINE": "Combination", "SASH_MAIN": "Sash 1",
                  "SASH_RESULT": "Result", "SASH_SERVE": "Sash 2"}


class Inventory(object):
    """The inventory's half of the tradable icon."""

    def __init__(self):
        self.locked = set()

    def SetCantMouseEventCell(self, cell):
        self.locked.add(cell)

    def SetCanMouseEventCell(self, cell):
        self.locked.discard(cell)


def sash_world():
    world = w6.World()
    world.game.position = [1000.0, 2000.0, 0.0]
    support.define(world.game.modules["player"], "GetMainCharacterPosition", lambda: tuple(world.game.position))
    world.load("uiSash", "uisash.py")
    return world


def make(world, kind):
    module = world.game.loaded["uiSash"]
    with world.game, lf.quiet():
        window = getattr(module, kind)()
        window.LoadWindow()
        window.inventory = Inventory()
        window.SetInven(window.inventory)
        window.SetItemToolTip(support.ToolTip("item"))
        window.Open()
    return window


def sash_calls(world):
    return [(name[len("sash."):],) + tuple(args) for name, args in world.game.log if name.startswith("sash.")]


class CombineWindow(unittest.TestCase):
    def setUp(self):
        self.world = sash_world()
        self.state = self.world.game.sash_state
        self.state.price = 100000
        self.window = make(self.world, "CombineWindow")
        del self.world.game.log[:]

    def run_with(self, call, *args):
        with self.world.game, lf.quiet():
            return call(*args)

    def test_the_uiscript_has_every_child_the_window_binds(self):
        for name in ("TitleBar", "AcceptButton", "CancelButton", "SashSlot", "NeedMoney", "Result"):
            self.assertIn(name, self.window.ElementDictionary)
        self.assertEqual(sorted(self.window.GetChild("SashSlot").slots), [0, 1, 2])

    def test_open_shows_the_price_and_empty_slots(self):
        locale = self.world.game.modules["localeInfo"]
        self.assertEqual(self.window.GetChild("NeedMoney").text, locale.SASH_REFINE_COST % 100000)
        self.assertTrue(self.window.IsOpened())

    def test_a_bag_item_dropped_on_a_slot_is_added_there(self):
        self.world.attach(self.world.game.modules["player"].SLOT_TYPE_INVENTORY, SASH_IN_BAG, w6.SASH)
        self.run_with(self.window.GetChild("SashSlot").fire, "select_empty", 1)
        self.assertEqual(sash_calls(self.world), [("Add", 1, SASH_IN_BAG, 1)])
        self.assertFalse(self.world.mouse.isAttached())

    def test_nothing_is_added_on_the_result_slot_or_from_another_window(self):
        player = self.world.game.modules["player"]
        self.world.attach(player.SLOT_TYPE_INVENTORY, SASH_IN_BAG, w6.SASH)
        self.run_with(self.window.GetChild("SashSlot").fire, "select_empty", 2)
        self.world.attach(player.SLOT_TYPE_SAFEBOX, 5, w6.SASH)
        self.run_with(self.window.GetChild("SashSlot").fire, "select_empty", 0)
        self.assertEqual(sash_calls(self.world), [])

    def test_the_refresh_shows_both_sashes_the_result_and_locks_their_cells(self):
        self.world.game.give(SASH_IN_BAG, w6.SASH)
        self.world.game.give(SASH2_IN_BAG, w6.SASH)
        self.state.attached = {0: (True, SASH_IN_BAG), 1: (True, SASH2_IN_BAG)}
        self.state.result = (w6.SASH_NEXT, 5, 10)
        self.state.price = 250000
        self.run_with(self.window.Refresh, 3)
        slots = self.window.GetChild("SashSlot").slots
        self.assertEqual([slots[i]["vnum"] for i in range(3)], [w6.SASH, w6.SASH, w6.SASH_NEXT])
        locale = self.world.game.modules["localeInfo"]
        self.assertEqual(self.window.GetChild("NeedMoney").text, locale.SASH_REFINE_COST % 250000)
        self.assertEqual(self.window.inventory.locked, {SASH_IN_BAG, SASH2_IN_BAG})
        self.run_with(self.window.Close)
        self.assertEqual(self.window.inventory.locked, set(), "released at the close")

    def test_a_sash_in_bag_cell_0_is_released_too(self):
        """OLD remembered a cell only when it was not a slot number, so a
        sash in bag cell 0 or 1 stayed marked."""
        self.world.game.give(0, w6.SASH)
        self.state.attached = {0: (True, 0)}
        self.run_with(self.window.Refresh, 3)
        self.assertEqual(self.window.inventory.locked, {0})
        self.run_with(self.window.Close)
        self.assertEqual(self.window.inventory.locked, set())

    def test_a_press_on_an_item_takes_it_out(self):
        self.world.game.give(SASH_IN_BAG, w6.SASH)
        self.world.game.give(SASH2_IN_BAG, w6.SASH)
        self.state.attached = {0: (True, SASH_IN_BAG), 1: (True, SASH2_IN_BAG)}
        self.run_with(self.window.Refresh, 3)
        del self.world.game.log[:]
        self.run_with(self.window.GetChild("SashSlot").fire, "use", 1)
        self.assertEqual(sash_calls(self.world), [("Remove", 1)])
        self.assertEqual(self.window.inventory.locked, {SASH_IN_BAG})
        self.run_with(self.window.GetChild("SashSlot").fire, "use", 0)
        self.assertEqual(self.window.inventory.locked, set(), "the first sash takes the second out with it")
        self.run_with(self.window.GetChild("SashSlot").fire, "use", 2)
        self.assertEqual(sash_calls(self.world), [("Remove", 1), ("Remove", 0)])

    def test_accept_sends_the_refine_with_the_combine_all_flag(self):
        constants = self.world.game.modules["constInfo"]
        self.run_with(self.window.OnAccept)
        self.run_with(self.window.checkBox.OnMouseLeftButtonUp)
        self.assertTrue(constants.SASH_AUTO_COMBINE)
        self.run_with(self.window.OnAccept)
        self.run_with(self.window.checkBox.OnMouseLeftButtonUp)
        self.assertFalse(constants.SASH_AUTO_COMBINE)
        self.assertEqual(sash_calls(self.world), [("SendRefineRequest", False), ("SendRefineRequest", True)])

    def test_cancel_and_escape_ask_the_server_to_close(self):
        self.run_with(self.window.OnClose)
        self.assertTrue(self.run_with(self.window.OnPressEscapeKey))
        self.assertEqual(sash_calls(self.world), [("SendCloseRequest",), ("SendCloseRequest",)])

    def test_walking_away_closes_once(self):
        self.run_with(self.window.OnUpdate)
        self.world.game.position[0] += 999
        self.run_with(self.window.OnUpdate)
        self.assertEqual(sash_calls(self.world), [])
        self.world.game.position[0] += 1
        self.run_with(self.window.OnUpdate)
        self.run_with(self.window.OnUpdate)
        self.assertEqual(sash_calls(self.world), [("SendCloseRequest",)])

    def test_the_result_slot_shows_the_result_tooltip(self):
        self.state.attached = {0: (True, SASH_IN_BAG)}
        self.run_with(self.window.OnOverInItem, 2)
        self.run_with(self.window.OnOverInItem, 0)
        calls = [call for call in self.window.tooltipItem.calls if call[0] in ("SetSashResultItem", "SetInventoryItem")]
        self.assertEqual(calls, [("SetSashResultItem", SASH_IN_BAG), ("SetInventoryItem", SASH_IN_BAG)])


class AbsorbWindow(unittest.TestCase):
    def setUp(self):
        self.world = sash_world()
        self.state = self.world.game.sash_state
        self.window = make(self.world, "AbsorbWindow")
        del self.world.game.log[:]

    def test_the_uiscript_has_every_child_the_window_binds(self):
        for name in ("TitleBar", "AcceptButton", "CancelButton", "SashSlot"):
            self.assertIn(name, self.window.ElementDictionary)
        self.assertEqual(sorted(self.window.GetChild("SashSlot").slots), [0, 1, 2])

    def test_accept_sends_the_refine(self):
        with self.world.game, lf.quiet():
            self.window.OnAccept()
        self.assertEqual(sash_calls(self.world), [("SendRefineRequest",)])

    def test_the_result_slot_shows_the_absorption_tooltip(self):
        with self.world.game, lf.quiet():
            self.window.OnOverInItem(2)
            self.state.attached = {0: (True, SASH_IN_BAG), 1: (True, SWORD_CELL)}
            self.window.OnOverInItem(2)
        calls = [call for call in self.window.tooltipItem.calls if call[0] == "SetSashResultAbsItem"]
        self.assertEqual(calls, [("SetSashResultAbsItem", SASH_IN_BAG, SWORD_CELL)], "only with both items")


# --- the Interface and the game window -----------------------------------------------------------------

def compiled(file_name, class_name, names, namespace=None):
    source = support.source_of(file_name, names, inside=class_name)
    body = "\n".join("\t" + line if line else line for line in source.split("\n"))
    namespace = dict(namespace or {})
    exec(compile("class %s(object):\n%s\n" % (class_name, body), file_name, "exec"), namespace)
    return namespace[class_name]


class Recorder(object):
    def __init__(self, log, name, shown=False):
        self.log, self.name, self.shown = log, name, shown

    def IsOpened(self):
        return self.shown

    IsShow = IsOpened

    def Open(self):
        self.shown = True
        self.log.append((self.name, "Open"))

    Show = Open

    def Close(self):
        self.shown = False
        self.log.append((self.name, "Close"))

    def Refresh(self, iAct):
        self.log.append((self.name, "Refresh", iAct))

    def RefreshBagSlotWindow(self):
        self.log.append((self.name, "RefreshBagSlotWindow"))


class Interface(unittest.TestCase):
    def setUp(self):
        Interface = compiled("interfacemodule.py", "Interface", ["ActSash"])
        self.log = []
        self.interface = Interface()
        self.interface.wndSashCombine = Recorder(self.log, "combine")
        self.interface.wndSashAbsorption = Recorder(self.log, "absorb")
        self.interface.wndInventory = Recorder(self.log, "inventory")

    def test_open_opens_the_window_and_the_inventory(self):
        self.interface.ActSash(1, True)
        self.interface.ActSash(1, False)
        self.assertEqual(self.log, [("combine", "Open"), ("inventory", "Open"), ("inventory", "RefreshBagSlotWindow"),
                                    ("absorb", "Open"), ("inventory", "RefreshBagSlotWindow")])

    def test_close_and_refresh_reach_the_open_window_only(self):
        self.interface.wndSashCombine.shown = True
        self.interface.ActSash(3, True)
        self.interface.ActSash(4, False)
        self.interface.ActSash(2, True)
        self.interface.ActSash(2, False)
        self.assertEqual(self.log, [("combine", "Refresh", 3), ("inventory", "RefreshBagSlotWindow"),
                                    ("inventory", "RefreshBagSlotWindow"), ("combine", "Close"),
                                    ("inventory", "RefreshBagSlotWindow"), ("inventory", "RefreshBagSlotWindow")])

    def test_an_unknown_act_changes_nothing(self):
        self.interface.ActSash(0, True)
        self.assertEqual(self.log, [])

    def test_the_windows_are_made_bound_and_destroyed(self):
        source = lf.read(os.path.join(w6.ROOT, "interfacemodule.py"))
        self.assertIn("import uiSash", source.split("\n"))
        for line in ("self.__MakeSashWindow()", "self.wndSashCombine = uiSash.CombineWindow()",
                     "self.wndSashAbsorption = uiSash.AbsorbWindow()", "self.wndSashAbsorption.LoadWindow()",
                     "self.wndInventory.SetSashWindow(self.wndSashCombine, self.wndSashAbsorption)",
                     "self.wndSashCombine.SetItemToolTip(self.tooltipItem)",
                     "self.wndSashAbsorption.SetItemToolTip(self.tooltipItem)",
                     "self.wndSashCombine.Destroy()", "self.wndSashAbsorption.Destroy()"):
            self.assertIn(line, source)


class GameWindow(unittest.TestCase):
    def test_act_sash_reaches_the_interface(self):
        log = []
        Game = compiled("game.py", "GameWindow", ["ActSash"])
        game = Game()
        game.interface = types.SimpleNamespace(ActSash=lambda *args: log.append(args))
        game.ActSash(3, True)
        game.interface = None
        game.ActSash(3, True)
        self.assertEqual(log, [(3, True)])

    def test_the_alert_names_the_item_the_window_destroys(self):
        world = w6.World()
        locale = world.game.modules["localeInfo"]
        log = []
        Game = compiled("game.py", "GameWindow", ["AlertSash"],
                        {"snd": types.SimpleNamespace(PlaySound=lambda path: log.append(("sound", path))),
                         "localeInfo": locale})
        game = Game()
        game.PopupMessage = lambda text: log.append(("popup", text))
        game.AlertSash(True)
        game.AlertSash(False)
        self.assertEqual(log, [("sound", "sound/ui/make_soket.wav"), ("popup", locale.SASH_DEL_SERVEITEM),
                               ("sound", "sound/ui/make_soket.wav"), ("popup", locale.SASH_DEL_ABSORDITEM)])


# --- the inventory -----------------------------------------------------------------------------------------------

class InventorySash(unittest.TestCase):
    def setUp(self):
        self.world = sash_world()
        self.inventory = w6.make_inventory(self.world)
        self.combine = make(self.world, "CombineWindow")
        self.absorb = make(self.world, "AbsorbWindow")
        self.combine.Hide()
        self.absorb.Hide()
        self.inventory.SetSashWindow(self.combine, self.absorb)
        self.world.game.give(SASH_IN_BAG, w6.SASH)
        del self.world.game.log[:]

    def right_click(self, cell):
        with self.world.game, lf.quiet():
            self.inventory.UseItemSlot(cell)

    def test_a_right_click_puts_the_item_into_the_open_window(self):
        for window in (self.combine, self.absorb):
            with self.subTest(window=type(window).__name__):
                del self.world.game.log[:]
                window.Show()
                self.right_click(SASH_IN_BAG)
                window.Hide()
                self.assertEqual(sash_calls(self.world), [("Add", 1, SASH_IN_BAG, 255)])
                self.assertEqual(self.world.sent("net.SendItemUse"), [], "not used")

    def test_without_a_window_the_item_is_used(self):
        self.right_click(SASH_IN_BAG)
        self.assertEqual(sash_calls(self.world), [])
        self.assertEqual(len(self.world.sent("net.SendItemUse")), 1)
        self.assertEqual(self.inventory.isShowSashWindow(), 0)

    def test_the_costume_window_shows_the_worn_sash(self):
        self.world.game.give(SASH_CELL, w6.SASH)
        with self.world.game, lf.quiet():
            self.inventory.ClickCostumeButton()
        self.assertEqual(self.inventory.wndCostume.wndEquip.slots[SASH_CELL]["vnum"], w6.SASH)


class BonusScroll(unittest.TestCase):
    """The sash's bonus scroll (value 0 sash.CLEAN_ATTR_VALUE0 or
    TAKE_ATTR_VALUE0) dropped on an item (OLD uiInventory.py:2071-2108)."""

    def setUp(self):
        self.world = w6.World()
        self.inventory = w6.make_inventory(self.world)
        game = self.world.game
        game.give(SCROLL_CELL, SCROLL)
        game.give(SASH_IN_BAG, w6.SASH)
        game.give(SWORD_CELL, w6.SWORD)
        self.kinds = {SCROLL: (3, 0, [w6.C_SASH["CLEAN_ATTR_VALUE0"]]), w6.SASH: (28, 3, []), w6.SWORD: (1, 0, [])}
        item = game.modules["item"]
        kind = lambda: self.kinds.get(item.selected[0], (0, 0, []))
        support.define(item, "GetItemType", lambda: kind()[0])
        support.define(item, "GetItemSubType", lambda: kind()[1])
        support.define(item, "GetValue", lambda i: (list(kind()[2]) + [0] * 6)[i])
        game.dialogs = []

    def detach(self, can):
        player = self.world.game.modules["player"]
        support.define(player, "CanDetach", lambda vnum, pos: player.DETACH_METIN_OK if can else 0)
        with self.world.game, lf.quiet():
            self.inventory.DetachMetinFromItem(SCROLL_CELL, SASH_IN_BAG)

    def infos(self):
        return [args[1] for name, args in self.world.game.calls("chat.AppendChat")]

    def test_a_refused_bonus_scroll_says_no_bonus_can_be_taken(self):
        locale = self.world.game.modules["localeInfo"]
        for value in (w6.C_SASH["CLEAN_ATTR_VALUE0"], w6.C_SASH["TAKE_ATTR_VALUE0"]):
            with self.subTest(value=value):
                self.kinds[SCROLL] = (3, 0, [value])
                del self.world.game.log[:]
                self.detach(False)
                self.assertEqual(self.infos(), [locale.SASH_FAILURE_CLEAN])

    def test_another_refused_scroll_keeps_its_text(self):
        locale = self.world.game.modules["localeInfo"]
        self.kinds[SCROLL] = (3, 0, [1])
        self.detach(False)
        self.assertEqual(self.infos(), [locale.REFINE_FAILURE_METIN_INSEPARABLE_ITEM])

    def test_the_question_on_a_sash_is_the_cleaning_one(self):
        locale = self.world.game.modules["localeInfo"]
        self.detach(True)
        dialog = self.world.game.dialogs[-1]
        self.assertEqual(dialog.texts, [locale.SASH_DO_YOU_CLEAN])
        self.kinds[SCROLL] = (3, 0, [1])
        self.detach(True)
        self.assertEqual(self.world.game.dialogs[-1].texts, [locale.REFINE_DO_YOU_SEPARATE_METIN])


# --- the tooltips ------------------------------------------------------------------------------------------------

SWORD_ROW = dict(lf.ITEM_BASE, name="Sword+9", type=1, subtype=0, size=[1, 2], wear=16,
                 applies=[["APPLY_ATT_SPEED", 22], ["APPLY_STR", 9]], values=[0, 0, 0, 100, 120, 40],
                 icon="icon/item/00019.tga")
ARMOUR_ROW = dict(lf.ITEM_BASE, name="Armour+9", type=2, subtype=0, size=[1, 2], wear=1,
                  applies=[["APPLY_MAX_HP", 1000]], values=[20, 300, 0, 0, 0, 50], icon="icon/item/11209.tga")
SASH_ROW = dict(lf.ITEM_BASE, name="Lord Sash (basic)", type=28, subtype=3, icon="icon/item/85001.tga")
SASH_NEXT_ROW = dict(lf.ITEM_BASE, name="Lord Sash (fine)", type=28, subtype=3, icon="icon/item/85002.tga")
ARMOUR = 11209


class CalcSashValue(unittest.TestCase):
    def test_olds_rounding(self):
        module = tooltip_module()
        # value * rate / 100, rounded half down, then up by one when above 0;
        # at least 1 of a positive value (OLD's formula, spelled out).
        for (value, rate), want in {(0, 25): 0, (100, 25): 25, (120, 25): 30, (9, 25): 2, (22, 1): 1, (1000, 11): 110,
                                     (3, 10): 1, (-40, 25): -10}.items():
            with self.subTest(value=value, rate=rate):
                self.assertEqual(module.CalcSashValue(value, rate), want)


def tooltip_module():
    corpus_tool, world = w6.tooltip_world({})
    return world.game.loaded["uiToolTip"]


class SashToolTip(unittest.TestCase):
    ITEMS = {w6.SASH: SASH_ROW, w6.SASH_NEXT: SASH_NEXT_ROW, w6.SWORD: SWORD_ROW, ARMOUR: ARMOUR_ROW}

    def texts(self, sockets, attrs=()):
        corpus_tool, world = w6.tooltip_world(self.ITEMS)
        texts, error = w6.tooltip_texts(corpus_tool, world, {"context": "AddItemData", "vnum": w6.SASH,
                                                              "sockets": sockets, "attrs": list(attrs)})
        self.assertIsNone(error)
        return texts, world.game.modules["localeInfo"]

    def test_an_empty_sash_shows_its_rate(self):
        texts, locale = self.texts([11, 0, 0, 0])
        self.assertIn(locale.SASH_ABSORB_CHANCE % 11, texts)
        self.assertNotIn(locale.TOOLTIP_ITEM_ATT_POWER % (34, 39), texts)

    def test_an_absorbed_weapon_shows_its_power_and_applies_at_the_rate(self):
        texts, locale = self.texts([25, w6.SWORD, 0, 0], attrs=[[1, 2000]])
        self.assertIn(locale.SASH_ABSORB_CHANCE % 25, texts)
        # attack 100-120 + 40 at 25 %: 25-30 + 10.
        self.assertIn(locale.TOOLTIP_ITEM_ATT_POWER % (35, 40), texts)
        self.assertIn(locale.TOOLTIP_ATT_SPEED(6), texts)
        self.assertIn(locale.TOOLTIP_STR(2), texts)
        self.assertIn(locale.TOOLTIP_MAX_HP(500), texts, "the bonuses at the rate too")

    def test_an_absorbed_armour_shows_its_defence(self):
        texts, locale = self.texts([20, ARMOUR, 0, 0])
        # defence 300 + 2 * 50 at 20 %: 60 + 20; magic defence 20 at 20 %: 4.
        self.assertIn(locale.TOOLTIP_ITEM_DEF_GRADE % 80, texts)
        self.assertIn(locale.TOOLTIP_ITEM_MAGIC_DEF_POWER % 4, texts)
        self.assertIn(locale.TOOLTIP_MAX_HP(200), texts)

    def test_the_combination_result(self):
        corpus_tool, world = w6.tooltip_world(self.ITEMS)
        locale = world.game.modules["localeInfo"]
        world.game.sash_state.result = (w6.SASH_NEXT, 5, 10)
        texts = w6.call_texts(corpus_tool, world, {"vnum": w6.SASH, "sockets": [5, w6.SWORD, 0, 0]},
                              lambda tip: tip.SetSashResultItem(0))
        self.assertIn("Lord Sash (fine)", texts)
        self.assertIn(locale.SASH_ABSORB_CHANCE2 % (5, 10), texts)
        self.assertIn(locale.TOOLTIP_ITEM_ATT_POWER % (14, 16), texts, "at the result's highest rate")
        world.game.sash_state.result = (w6.SASH_NEXT, 10, 10)
        texts = w6.call_texts(corpus_tool, world, {"vnum": w6.SASH, "sockets": [5, 0, 0, 0]},
                              lambda tip: tip.SetSashResultItem(0))
        self.assertIn(locale.SASH_ABSORB_CHANCE % 10, texts)

    def test_no_result_no_tooltip(self):
        corpus_tool, world = w6.tooltip_world(self.ITEMS)
        texts = w6.call_texts(corpus_tool, world, {"vnum": w6.SASH}, lambda tip: tip.SetSashResultItem(0))
        self.assertEqual(texts, [])

    def test_the_absorption_result(self):
        corpus_tool, world = w6.tooltip_world(self.ITEMS)
        locale = world.game.modules["localeInfo"]
        texts = w6.call_texts(corpus_tool, world, {"vnum": w6.SASH, "sockets": [25, 0, 0, 0]},
                              lambda tip: tip.SetSashResultAbsItem(0, 1),
                              {1: {"vnum": w6.SWORD, "attrs": [(1, 2000)]}})
        self.assertIn("Lord Sash (basic)", texts)
        self.assertIn(locale.SASH_ABSORB_CHANCE % 25, texts)
        self.assertIn(locale.TOOLTIP_ITEM_ATT_POWER % (35, 40), texts)
        self.assertIn(locale.TOOLTIP_MAX_HP(500), texts, "the target's bonuses at the sash's rate")

    def test_a_result_that_is_no_sash_shows_nothing(self):
        """OLD's "and" let any costume through; a result is a costume sash."""
        items = dict(self.ITEMS)
        items[w6.BODY_COSTUME] = dict(SASH_ROW, subtype=0)
        corpus_tool, world = w6.tooltip_world(items)
        world.game.sash_state.result = (w6.BODY_COSTUME, 5, 10)
        texts = w6.call_texts(corpus_tool, world, {"vnum": w6.SASH}, lambda tip: tip.SetSashResultItem(0))
        self.assertEqual(texts, [])


# --- the model -------------------------------------------------------------------------------------------------------

class Bone(unittest.TestCase):
    def test_every_race_hangs_the_sash_from_the_spine(self):
        bones = []
        original = lf.AnyCall.__getattr__

        def getattr_(module, name):
            if name == "RegisterAttachingBoneName":
                return lambda part, bone: bones.append((part, bone))
            return original(module, name)
        with mock.patch.object(lf.AnyCall, "__getattr__", getattr_):
            motions = lf.RaceMotions(self)
        sash = [bone for part, bone in bones if part == motions.chr.PART_SASH]
        self.assertEqual(sash, ["Bip01 Spine2"] * 8, "both sexes of the four races")


class Locales(unittest.TestCase):
    def test_every_locale_has_the_sash_keys(self):
        w6.check_keys(self, GAME_KEYS)
        w6.check_keys(self, INTERFACE_KEYS, "locale_interface.txt")


if __name__ == "__main__":
    unittest.main()
