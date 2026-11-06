"""Tests for the legacy client's weapon costume (wave 6, chunk Y; NOVA-21,
OLD's __WEAPON_COSTUME_SYSTEM__): python3 -B -m unittest weapon_costume_test
(from tools/).

The C++ half (the weapon part from the costume, item.COSTUME_TYPE_WEAPON and
item.COSTUME_SLOT_WEAPON) is chunk C's, the equip rules chunk SA's. Here the
legacy costume window (uiinventory.CostumeWindow and uiscript
costumewindow.py) runs over nui_game_support's stand-ins with C's names
(wave6_support):
- the window has OLD's weapon costume cell, wear 22 (OLD
  uiscript/costumewindow.py: COSTUME_START_INDEX+3, 32 x 96), and refreshes
  it with the body and the hair (COSTUME_SLOT_COUNT runs over it);
- its cell is the inventory's: a drop, a use and a hover go to the
  inventory's legacy handlers, which move, unequip and show it;
- its tooltip is the costumes' (the weapon costume has no rule of its own in
  OLD's uiToolTip.py)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import legacy_foundation_test as lf  # noqa: E402
import wave6_support as w6  # noqa: E402

WEAPON_CELL = w6.EQUIPMENT_START + 22


class WeaponCell(unittest.TestCase):
    def test_the_uiscript_has_the_weapon_costume_cell_of_three_rows(self):
        world = w6.World()
        with world.game:
            window = lf.read_uiscript(os.path.join(w6.UISCRIPT, "costumewindow.py"))["window"]
        slots = dict((slot["index"], slot) for slot in lf.child(window, "CostumeSlot")["slot"])
        self.assertIn(WEAPON_CELL, slots)
        self.assertEqual((slots[WEAPON_CELL]["width"], slots[WEAPON_CELL]["height"]), (32, 96))
        self.assertEqual(WEAPON_CELL, w6.C_ITEM["COSTUME_SLOT_WEAPON"], "OLD's item.COSTUME_SLOT_WEAPON")

    def test_the_window_shows_the_worn_weapon_costume(self):
        world = w6.World()
        world.game.give(WEAPON_CELL, w6.WEAPON_COSTUME)
        world.game.give(w6.COSTUME_START, w6.BODY_COSTUME)
        _, window = w6.costume_window(world)
        shown = dict((index, slot["vnum"]) for index, slot in window.wndEquip.slots.items() if slot["vnum"])
        self.assertEqual({WEAPON_CELL: w6.WEAPON_COSTUME, w6.COSTUME_START: w6.BODY_COSTUME}, shown)

    def test_a_refresh_takes_it_off_the_window(self):
        world = w6.World()
        world.game.give(WEAPON_CELL, w6.WEAPON_COSTUME)
        inventory, window = w6.costume_window(world)
        world.game.items.pop(WEAPON_CELL)
        with world.game, lf.quiet():
            inventory.RefreshEquipSlotWindow()
        self.assertEqual(window.wndEquip.slots[WEAPON_CELL]["vnum"], 0)

    def test_a_use_of_the_cell_is_the_inventorys_unequip(self):
        world = w6.World()
        world.game.give(WEAPON_CELL, w6.WEAPON_COSTUME)
        inventory, window = w6.costume_window(world)
        del world.game.log[:]
        with world.game, lf.quiet():
            window.wndEquip.fire("use", WEAPON_CELL)
        sent = [args for name, args in world.game.log if name.startswith("net.SendItemUse")]
        self.assertEqual(len(sent), 1)
        self.assertIn(WEAPON_CELL, sent[0])

    def test_a_hover_shows_the_inventorys_tooltip_of_the_cell(self):
        world = w6.World()
        world.game.give(WEAPON_CELL, w6.WEAPON_COSTUME)
        inventory, window = w6.costume_window(world)
        with world.game, lf.quiet():
            window.wndEquip.fire("over_in", WEAPON_CELL)
        calls = [call for call in inventory.tooltipItem.calls if call[0] == "SetInventoryItem"]
        self.assertEqual(calls[-1][1], WEAPON_CELL)


class ToolTip(unittest.TestCase):
    COSTUME = dict(lf.ITEM_BASE, name="Riptooth Blade+", type=28, subtype=2, size=[1, 2],
                   values=[0, 0, 0, 0, 6666, 0], icon="icon/item/40108.tga", applies=[["APPLY_STR", 5]])

    def test_a_weapon_costume_shows_the_costume_lines(self):
        corpus_tool, world = w6.tooltip_world({w6.WEAPON_COSTUME: self.COSTUME})
        texts, error = w6.tooltip_texts(corpus_tool, world, {"context": "AddItemData", "vnum": w6.WEAPON_COSTUME})
        self.assertIsNone(error)
        locale = world.game.modules["localeInfo"]
        self.assertIn(locale.TOOLTIP_STR(5), texts)


if __name__ == "__main__":
    unittest.main()
