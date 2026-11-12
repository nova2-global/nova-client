"""NOVA-183: OLD's toggle items (ITEM_TOGGLE, type 37). The server sets an
item's socket 3 while it is on: a summoned pet or mount, a worn effect tag, an
active buff (game/src/toggle_item.cpp). The inventory marks such an item
active, as OLD's uiInventory.py:1461-1467 did, in the legacy window and in
NovaUI's (which takes the legacy window's ActivateSlot through its slot
proxy). NOVA-188 colors the glows later; here every one is the slot's active
look.

    cd tools && python3 -B -m unittest toggle_items_test
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nui_game_support as support  # noqa: E402
import nui_inventory_test as inv  # noqa: E402

TOGGLE_TYPE = 37
# NEW's item_proto: a pet, a mount, a tag and the third hand (subtypes
# TOGGLE_PET, TOGGLE_MOUNT, TOGGLE_EFFECT, TOGGLE_BUFF).
PET, MOUNT, TAG, HAND = 53024, 71177, 49500, 70002
SUBTYPES = {PET: 0, MOUNT: 1, TAG: 2, HAND: 3}
CELLS = {PET: 30, MOUNT: 31, TAG: 32, HAND: 33}


def install(game):
    """item.GetItemType and GetItemSubType answer type 37 and the subtype for
    the toggle vnums, and what the world answered for the rest."""
    item = game.modules["item"]
    selected = item.selected
    old_type = item.__dict__.get("GetItemType")
    old_sub = item.__dict__.get("GetItemSubType")

    def kind(*vnum):
        v = vnum[0] if vnum else selected[0]
        if v in SUBTYPES:
            return TOGGLE_TYPE
        return old_type(*vnum) if callable(old_type) else 0

    def sub(*vnum):
        v = vnum[0] if vnum else selected[0]
        if v in SUBTYPES:
            return SUBTYPES[v]
        return old_sub(*vnum) if callable(old_sub) else 0

    support.define(item, "GetItemType", kind)
    support.define(item, "GetItemSubType", sub)


def toggles(on):
    """stock() plus the four toggle items, `on` the vnums whose socket 3 is set."""
    def change(game):
        install(game)
        for vnum, cell in CELLS.items():
            game.give(cell, vnum, sockets=(0, 0, 0, 1 if vnum in on else 0))
    return inv.with_state(change)


class Inventory(inv.Pair):
    def shown(self, setup):
        legacy, novaui = self.worlds(setup)
        a, b = legacy.make_inventory(), novaui.make_inventory()
        return legacy, novaui, a, b

    def test_a_toggle_item_that_is_on_is_active_and_one_that_is_off_is_not(self):
        legacy, novaui, a, b = self.shown(toggles({PET, TAG, HAND}))
        bag = a.wndItem.shown()
        self.assertTrue(bag[CELLS[PET]][2], "the summoned pet")
        self.assertFalse(bag[CELLS[MOUNT]][2], "the mount that is off")
        self.assertTrue(bag[CELLS[TAG]][2], "the worn tag")
        self.assertTrue(bag[CELLS[HAND]][2], "the active buff")
        # NovaUI shows what legacy shows.
        self.assertEqual(inv.Model.shown_bag(self, novaui, b), bag)

    def test_turning_it_off_takes_the_active_look_away_on_the_next_refresh(self):
        legacy, novaui, a, b = self.shown(toggles({MOUNT}))
        self.assertTrue(a.wndItem.shown()[CELLS[MOUNT]][2])
        for world, window in ((legacy, a), (novaui, b)):
            world.game.items[CELLS[MOUNT]]["sockets"][3] = 0
            with world.game, inv.quiet():
                window.RefreshBagSlotWindow()
        self.assertFalse(a.wndItem.shown()[CELLS[MOUNT]][2])
        self.assertEqual(inv.Model.shown_bag(self, novaui, b), a.wndItem.shown())

    def test_another_item_with_socket_three_set_is_not_marked(self):
        """Socket 3 means "on" only for a toggle item."""
        def other(game):
            install(game)
            game.give(34, 27001, sockets=(0, 0, 0, 1))
        legacy, novaui, a, b = self.shown(inv.with_state(other))
        self.assertFalse(a.wndItem.shown()[34][2])


if __name__ == "__main__":
    unittest.main()
