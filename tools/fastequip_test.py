"""Tests of fast equip (NOVA-17): the legacy window (assets/root/uifastequip.py,
OLD root/uiFastEquip.py), its NovaUI facade (assets/root/nui_fastequip.py), the
game, Interface and inventory hooks, and the locale keys:
python3 -B -m unittest fastequip_test (from tools/).

The C++ half (the fastEquip module over GC/CG::FAST_EQUIP, the game window's
RefreshFastEquip) is built beside this; here a stand-in fastEquip module keeps
what the server last said and records every Send*. Each flow runs on the legacy
window and on the facade in the Wave 4 test world, and the effects (the Send*
calls, the mouse) must be the same."""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402

support = w4.support
ROOT = w4.ROOT
REPO = os.path.dirname(HERE)
LOCALES = os.path.join(REPO, "assets", "locale", "locale")
EFFECTS = ("fastEquip", "mouse", "mouseModule", "chat")

SLOT_EMPTY, SLOT_KEEP = 0, 255
WEAR_COUNT = 40
INVENTORY, EXTRA = 1, 6
SWORD, HELMET = 11, 12021          # vnums used by the stand-in
ARMOR, RING_A, RING_B, UNIQUE_A, COSTUME_BODY, POTION, NOT_MINE, ROD = 11299, 70001, 70002, 71001, 41001, 27001, 11899, 27400
WEAR_WEAPON, WEAR_HEAD, WEAR_BODY, WEAR_RING1, WEAR_BUFFI_HAIR, WEAR_AURA = 4, 1, 0, 28, 32, 39
WEAR_RING2, WEAR_UNIQUE1, WEAR_UNIQUE2, WEAR_COSTUME_BODY, WEAR_BUFFI_BODY, WEAR_BUFFI_WEAPON = 29, 7, 8, 19, 31, 33
# ItemData.h EWearFlags, the client's item.WEARABLE_* values.
WEARABLE = {"WEARABLE_BODY": 1 << 0, "WEARABLE_HEAD": 1 << 1, "WEARABLE_FOOTS": 1 << 2, "WEARABLE_WRIST": 1 << 3,
            "WEARABLE_WEAPON": 1 << 4, "WEARABLE_NECK": 1 << 5, "WEARABLE_EAR": 1 << 6, "WEARABLE_UNIQUE": 1 << 7,
            "WEARABLE_SHIELD": 1 << 8, "WEARABLE_ARROW": 1 << 9}
ALL_JOBS = (1 << 2) | (1 << 3) | (1 << 4) | (1 << 5)
EQUIPMENT_SLOT_START = w4.P["EQUIPMENT_SLOT_START"]
# OLD's 23 cells NEW can use today, as the server's mask would say.
USABLE_TODAY = set(range(0, 11)) | set(range(19, 23)) | {27, 28, 29, 30, 31, 32, 33, 39}


class Sets(object):
    """What C's CPythonFastEquip holds: the sets as the server last said."""

    def __init__(self):
        self.loaded = True
        self.usable = set(USABLE_TODAY)
        self.sets = {}

    def data(self, index):
        return self.sets.setdefault(index, {"name": "", "color": 0, "slots": [(SLOT_EMPTY, 0)] * WEAR_COUNT})

    def put_slot(self, index, wear, window, cell=0):
        self.data(index)["slots"] = list(self.data(index)["slots"])
        self.data(index)["slots"][wear] = (window, cell)


def install(game, sets):
    player = game.modules["player"]
    for name, value in (("EXTRA_INVENTORY", EXTRA), ("SLOT_TYPE_EXTRA_INVENTORY", 12)):
        if not isinstance(player.__dict__.get(name), int):
            setattr(player, name, value)
    item = game.modules["item"]
    for name, value in (("ITEM_TYPE_RING", 33), ("ITEM_TYPE_UNIQUE", 16), ("ARMOR_HEAD", 1), ("ARMOR_FOOTS", 2),
                        ("ARMOR_SHIELD", 4), ("WEAPON_SWORD", 0), ("WEAPON_DAGGER", 1), ("WEAPON_BOW", 2),
                        ("WEAPON_TWO_HANDED", 3), ("WEAPON_BELL", 4), ("WEAPON_FAN", 5), ("WEAPON_ARROW", 6),
                        ("WEAPON_CLAW", 8), ("WEAPON_UNLIMITED_ARROW", 9), ("ITEM_ANTIFLAG_WARRIOR", 1 << 2),
                        ("ITEM_ANTIFLAG_ASSASSIN", 1 << 3), ("ITEM_ANTIFLAG_SURA", 1 << 4), ("ITEM_ANTIFLAG_SHAMAN", 1 << 5),
                        ("ITEM_ANTIFLAG_MALE", 1 << 0), ("ITEM_ANTIFLAG_FEMALE", 1 << 1),
                        ("COSTUME_TYPE_BODY", 0), ("COSTUME_TYPE_HAIR", 1), ("COSTUME_TYPE_WEAPON", 3),
                        ("COSTUME_TYPE_SASH", 2), ("COSTUME_TYPE_SASH2", 7), ("COSTUME_TYPE_AURA", 4)):
        if not isinstance(item.__dict__.get(name), int):
            setattr(item, name, value)
    for name, value in WEARABLE.items():
        if not isinstance(item.__dict__.get(name), int):
            setattr(item, name, value)
    if not isinstance(item.__dict__.get("ITEM_TYPE_USE"), int):
        item.ITEM_TYPE_USE = 3
    # vnum: (type, subtype, wear flags, anti flags), as the item proto says.
    kinds = {SWORD: (item.ITEM_TYPE_WEAPON, item.WEAPON_SWORD, item.WEARABLE_WEAPON, 0),
             ARMOR: (item.ITEM_TYPE_ARMOR, item.ARMOR_BODY, item.WEARABLE_BODY, 0),
             HELMET: (item.ITEM_TYPE_ARMOR, item.ARMOR_HEAD, item.WEARABLE_HEAD, 0),
             RING_A: (item.ITEM_TYPE_RING, 0, 0, 0), RING_B: (item.ITEM_TYPE_RING, 0, 0, 0),
             UNIQUE_A: (item.ITEM_TYPE_UNIQUE, 0, item.WEARABLE_UNIQUE, 0),
             COSTUME_BODY: (item.ITEM_TYPE_COSTUME, item.COSTUME_TYPE_BODY, 0, 0),
             POTION: (item.ITEM_TYPE_USE, 0, 0, 0),
             NOT_MINE: (item.ITEM_TYPE_ARMOR, item.ARMOR_BODY, item.WEARABLE_BODY, ALL_JOBS),
             # A fishing rod: worn on the weapon's cell, but no weapon.
             ROD: (31, 0, item.WEARABLE_WEAPON, 0)}
    kind = lambda: kinds.get(item.selected[0], (0, 0, 0, 0))
    support.define(item, "IsAntiFlag", lambda flag: bool(kind()[3] & flag))
    support.define(item, "IsWearableFlag", lambda flag: bool(kind()[2] & flag))
    support.define(item, "GetItemType", lambda: kind()[0])
    support.define(item, "GetItemSubType", lambda: kind()[1])
    module = support.Recording("fastEquip", game.log, SET_COUNT=10, WEAR_COUNT=WEAR_COUNT, NAME_MAX_CHARS=15, COLOR_COUNT=13,
                               SLOT_EMPTY=SLOT_EMPTY, SLOT_KEEP=SLOT_KEEP)
    define = lambda name, fn: support.define(module, name, fn)
    define("IsLoaded", lambda: sets.loaded)
    define("GetName", lambda index: sets.data(index)["name"])
    define("GetColor", lambda index: sets.data(index)["color"])
    define("GetSlot", lambda index, wear: sets.data(index)["slots"][wear])
    define("IsUsableCell", lambda wear: wear in sets.usable)
    for name in ("SendSave", "SendSwitch", "SendClear", "SendRefresh"):
        module.__dict__[name] = support.recorded(game.log, "fastEquip." + name, lambda *args: None)
    game.put("fastEquip", module)
    app = game.modules["app"]
    app.ENABLE_FAST_EQUIP = 1
    app.DIK_LSHIFT = 42
    app.DIK_F10 = 68
    return module


def world(nui_on, sets=None):
    sets = sets or Sets()

    def setup(game):
        install(game, sets)
        game.give((INVENTORY, 7), SWORD)
        for cell, vnum in ((8, ARMOR), (9, RING_A), (10, RING_B), (11, COSTUME_BODY), (12, POTION), (13, NOT_MINE),
                           (14, UNIQUE_A), (15, ROD), (20, RING_B), (21, RING_B)):
            game.give((INVENTORY, cell), vnum)
        game.give((INVENTORY, EQUIPMENT_SLOT_START + WEAR_RING2), RING_A)

    game_world = w4.World(nui_on, windows="+fastequip", setup=setup)
    with game_world.game, w4.quiet():
        game_world.game.load("uiFastEquip", "uifastequip.py")
        if nui_on:
            game_world.game.load("nui_fastequip", "nui_fastequip.py")
    window = game_world.make("fastequip", "uiFastEquip", "FastEquipWindow", "nui_fastequip.FastEquipWindow")
    with game_world.game, w4.quiet():
        window.SetItemToolTip(game_world.tooltip)
        window.Open()
    game_world.sets = sets
    return game_world, window


def saves(effects):
    return [args for name, args in effects if name == "fastEquip.SendSave"]


class FastEquipTest(unittest.TestCase):
    def run_both(self, flow, sets_setup=None):
        results = []
        for nui_on in (False, True):
            sets = Sets()
            if sets_setup:
                sets_setup(sets)
            game_world, window = world(nui_on, sets)
            mark = game_world.mark()
            with game_world.game, w4.quiet():
                flow(game_world, window)
            results.append(game_world.effects_since(mark, EFFECTS))
        legacy, novaui = results
        self.assertEqual(novaui, legacy)
        return legacy

    # --- the same press on either side -----------------------------------------------

    @staticmethod
    def wear(game_world, window, wear, button=0):
        """A press on the wear cell's slot. In NovaUI the press and the
        release bubble from the cell to the canvas (the set's slot area)."""
        if game_world.nui_on:
            w4.fire(window, "slot_press", wear, button)
            w4.press(window, "canvas_press", button)
            if button == 0:
                w4.fire(window, "slot_release", wear, button)
                w4.fire(window, "canvas_release", button)
            return
        slots = window.itemSlot.windows[wear]
        filled = bool(slots.slots.get(wear, {}).get("vnum"))
        if button == 1:
            slots.events["unselect_item"](wear)
        elif filled:
            slots.events["select_item"](wear)
        else:
            slots.events["select_empty"](wear)

    @staticmethod
    def gap(game_world, window, how="press"):
        """A left press (or a drag's release, "release") on the set's slot
        area between the cells: NovaUI's canvas, legacy's drop catchers."""
        if game_world.nui_on:
            if how == "press":
                w4.press(window, "canvas_press", 0)
                w4.fire(window, "canvas_release", 0)
            else:
                w4.fire(window, "canvas_drop")
            return
        catcher = window.dropCatchers[0]
        if how == "press":
            catcher.OnMouseLeftButtonDown()
            catcher.OnMouseLeftButtonUp()
        else:
            catcher.OnMouseLeftButtonUp()

    @staticmethod
    def select_set(game_world, window, index, shift=False):
        if shift:
            game_world.game.pressed.add(game_world.game.modules["app"].DIK_LSHIFT)
        if game_world.nui_on:
            w4.press(window, "set_press", index, 0)
        else:
            window.SelectSet(index)
        game_world.game.pressed.discard(game_world.game.modules["app"].DIK_LSHIFT)


class Flows(FastEquipTest):
    def test_a_drop_saves_that_cell_and_keeps_every_other(self):
        def flow(game_world, window):
            P = game_world.game.modules["player"]
            game_world.attach(P.SLOT_TYPE_INVENTORY, 7, SWORD)
            self.wear(game_world, window, WEAR_WEAPON)
        effects = self.run_both(flow)
        (index, name, color, slots), = saves(effects)
        self.assertEqual((index, name, color), (0, "", 0))
        self.assertEqual(slots[WEAR_WEAPON], (INVENTORY, 7))
        for wear in range(WEAR_COUNT):
            if wear != WEAR_WEAPON:
                self.assertEqual(slots[wear][0], SLOT_KEEP, wear)

    def test_an_extra_inventory_item_sends_its_window(self):
        def flow(game_world, window):
            P = game_world.game.modules["player"]
            game_world.game.give((EXTRA, 40), SWORD)
            game_world.attach(P.SLOT_TYPE_EXTRA_INVENTORY, 40, SWORD)
            self.wear(game_world, window, WEAR_WEAPON)
        (_, _, _, slots), = saves(self.run_both(flow))
        self.assertEqual(slots[WEAR_WEAPON], (EXTRA, 40))

    def test_a_sword_dropped_on_the_head_goes_to_the_weapon_s_cell(self):
        """OLD's filter refused it silently (Eddy, r41: "nothing happens")."""
        def flow(game_world, window):
            P = game_world.game.modules["player"]
            game_world.attach(P.SLOT_TYPE_INVENTORY, 7, SWORD)
            self.wear(game_world, window, WEAR_HEAD)
        (_, _, _, slots), = saves(self.run_both(flow))
        self.assertEqual(slots[WEAR_WEAPON], (INVENTORY, 7))
        self.assertEqual(slots[WEAR_HEAD][0], SLOT_KEEP)

    def test_a_right_click_empties_the_cell_and_keeps_the_rest(self):
        def setup(sets):
            sets.put_slot(0, WEAR_WEAPON, INVENTORY, 7)

        def flow(game_world, window):
            self.wear(game_world, window, WEAR_WEAPON, button=1)
        (_, _, _, slots), = saves(self.run_both(flow, setup))
        self.assertEqual(slots[WEAR_WEAPON][0], SLOT_EMPTY)
        self.assertEqual([s[0] for i, s in enumerate(slots) if i != WEAR_WEAPON], [SLOT_KEEP] * (WEAR_COUNT - 1))

    def test_a_click_on_a_held_elsewhere_cell_clears_it(self):
        def setup(sets):
            sets.put_slot(0, WEAR_BODY, SLOT_KEEP)

        def flow(game_world, window):
            self.wear(game_world, window, WEAR_BODY)
        (_, _, _, slots), = saves(self.run_both(flow, setup))
        self.assertEqual(slots[WEAR_BODY][0], SLOT_EMPTY)

    def test_a_click_on_a_plain_empty_cell_does_nothing(self):
        self.assertEqual(saves(self.run_both(lambda g, w: self.wear(g, w, WEAR_WEAPON))), [])

    def test_a_rename_sends_every_cell_keep(self):
        def flow(game_world, window):
            if game_world.nui_on:
                w4.press(window, "edit_press", 3, 0)
                w4.board(window).set_value(NAME_FIELD, "PvP")
                w4.press(window, "color_press", 5, 0)
                w4.press(window, "edit_ok", 0)
            else:
                window.OpenEditPopup(3)
                popup = window.wndPopUpEdit
                popup.nameEditLine.SetText("PvP")
                popup.ClickColor(5)
                popup.UpdateButton()
        (index, name, color, slots), = saves(self.run_both(flow))
        self.assertEqual((index, name, color), (3, "PvP", 5))
        self.assertEqual({s[0] for s in slots}, {SLOT_KEEP})

    def test_shift_click_switches_the_clicked_set_not_the_selected(self):
        """OLD's SelectSet called Switch() for the previously selected set."""
        effects = self.run_both(lambda g, w: self.select_set(g, w, 5, shift=True))
        self.assertEqual([args for name, args in effects if name == "fastEquip.SendSwitch"], [(5,)])

    def test_a_plain_click_selects_and_asks_for_the_set(self):
        effects = self.run_both(lambda g, w: self.select_set(g, w, 2))
        self.assertEqual([args for name, args in effects if name == "fastEquip.SendRefresh"], [(2,)])
        self.assertFalse([e for e in effects if e[0] == "fastEquip.SendSwitch"])

    def test_the_switch_button_switches_the_selected_set(self):
        def flow(game_world, window):
            self.select_set(game_world, window, 4)
            if game_world.nui_on:
                w4.press(window, "switch_press", 0)
            else:
                window.switchButton.event()
        effects = self.run_both(flow)
        self.assertEqual([args for name, args in effects if name == "fastEquip.SendSwitch"], [(4,)])

    def test_clear_asks_first_then_deletes_the_set(self):
        def flow(game_world, window):
            if game_world.nui_on:
                w4.press(window, "clear_press", 0)
            else:
                window.clearButton.event()
            window.questionDialog.accept_event()
        effects = self.run_both(flow)
        self.assertEqual([args for name, args in effects if name == "fastEquip.SendClear"], [(0,)])


class Debounce(FastEquipTest):
    def test_an_inventory_change_refreshes_at_most_once_per_half_second_with_a_trailing_send(self):
        for nui_on in (False, True):
            with self.subTest(nui_on=nui_on):
                game_world, window = world(nui_on)
                game = game_world.game
                refreshes = lambda m: [args for name, args in game_world.game.log[m:] if name == "fastEquip.SendRefresh"]
                with game, w4.quiet():
                    mark = game_world.mark()
                    game.time += 1.0     # past the Open's own refresh
                    window.RefreshInventory()
                    self.assertEqual(refreshes(mark), [(0,)], "the first change sends at once")
                    mark2 = game_world.mark()
                    game.time += 0.1
                    window.RefreshInventory()
                    game.time += 0.1
                    window.RefreshInventory()
                    self.assertEqual(refreshes(mark2), [], "the coalesced changes wait")
                    game.time += 0.4
                    window.CheckRefreshDue()
                    self.assertEqual(refreshes(mark2), [(0,)], "the trailing send, once")
                    game.time += 1.0
                    window.CheckRefreshDue()
                    self.assertEqual(refreshes(mark2), [(0,)], "and only one")


class HiddenCells(FastEquipTest):
    def test_only_usable_cells_become_slots(self):
        def sets_setup(sets):
            sets.usable = {WEAR_WEAPON, WEAR_RING1}
        for nui_on in (False, True):
            with self.subTest(nui_on=nui_on):
                sets = Sets()
                sets_setup(sets)
                game_world, window = world(nui_on, sets)
                if nui_on:
                    shown = [c["index"] for c in w4.board(window).model["cells"] if c["shown"]]
                    self.assertEqual(shown, sorted({WEAR_WEAPON, WEAR_RING1}))
                else:
                    self.assertEqual(sorted(window.UsableCells()), sorted({WEAR_WEAPON, WEAR_RING1}))
                    self.assertEqual(sorted(window.itemSlot.windows), sorted({WEAR_WEAPON, WEAR_RING1}))


class Lifecycle(FastEquipTest):
    def test_the_cells_appear_when_the_mask_arrives_after_the_open(self):
        for nui_on in (False, True):
            with self.subTest(nui_on=nui_on):
                sets = Sets()
                sets.usable = set()
                game_world, window = world(nui_on, sets)
                sets.usable = {WEAR_WEAPON}
                with game_world.game, w4.quiet():
                    window.RefreshFastEquip(3, 0)
                self.assertEqual(window.builtCells, [WEAR_WEAPON])
                if nui_on:
                    self.assertEqual([c["index"] for c in w4.board(window).model["cells"] if c["shown"]], [WEAR_WEAPON])

    def test_the_marks_of_a_switch_survive_the_refresh_its_moves_bring(self):
        for nui_on in (False, True):
            with self.subTest(nui_on=nui_on):
                sets = Sets()
                sets.put_slot(0, WEAR_WEAPON, INVENTORY, 7)
                game_world, window = world(nui_on, sets)
                with game_world.game, w4.quiet():
                    window.RefreshFastEquip(0, 1)
                    window.RefreshFastEquip(0, 0)
                self.assertTrue(window.lastSwitched)
                if nui_on:
                    cell = [c for c in w4.board(window).model["cells"] if c["index"] == WEAR_WEAPON][0]
                    self.assertTrue(cell["disabled"], "the weapon did not move")
                with game_world.game, w4.quiet():
                    window.SelectSet(1)
                self.assertFalse(window.lastSwitched)

    def test_destroy_leaves_nothing_shown(self):
        for nui_on in (False, True):
            with self.subTest(nui_on=nui_on):
                game_world, window = world(nui_on)
                with game_world.game, w4.quiet():
                    window.Destroy()
                self.assertIsNone(window.wndPopUpEdit)


def chat_lines(effects):
    return [args[1] for name, args in effects if name == "chat.AppendChat"]


class DropAnywhere(FastEquipTest):
    """Eddy (r41): a drop anywhere on the set's slots goes to the cell the
    item is worn on (the server's CItem::FindEquipCell); an item that cannot
    be worn there is refused with a chat line."""

    def drop(self, vnum_cell, where, sets_setup=None, how="press"):
        def flow(game_world, window):
            P = game_world.game.modules["player"]
            game_world.attach(P.SLOT_TYPE_INVENTORY, vnum_cell, game_world.game.items[(INVENTORY, vnum_cell)]["vnum"])
            if where is None:
                self.gap(game_world, window, how)
            else:
                self.wear(game_world, window, where)
            self.assertFalse(game_world.game.modules["mouseModule"].mouseController.isAttached(), "the drop ends the attach")
        return self.run_both(flow, sets_setup)

    def saved(self, effects):
        (index, name, color, slots), = saves(effects)
        return dict((wear, slot) for wear, slot in enumerate(slots) if slot[0] != SLOT_KEEP)

    def test_armor_dropped_on_the_weapon_cell_goes_to_the_body(self):
        self.assertEqual(self.saved(self.drop(8, WEAR_WEAPON)), {WEAR_BODY: (INVENTORY, 8)})

    def test_a_press_between_the_cells_places_the_item_by_its_type(self):
        self.assertEqual(self.saved(self.drop(8, None)), {WEAR_BODY: (INVENTORY, 8)})

    def test_a_drag_released_between_the_cells_places_it_too(self):
        self.assertEqual(self.saved(self.drop(7, None, how="release")), {WEAR_WEAPON: (INVENTORY, 7)})

    def test_a_ring_takes_the_first_ring_cell_while_it_is_free(self):
        self.assertEqual(self.saved(self.drop(9, None)), {WEAR_RING1: (INVENTORY, 9)})

    def test_a_ring_takes_the_second_when_the_first_is_full(self):
        def setup(sets):
            sets.put_slot(0, WEAR_RING1, INVENTORY, 20)
        self.assertEqual(self.saved(self.drop(9, None, setup)), {WEAR_RING2: (INVENTORY, 9)})

    def test_with_both_ring_cells_full_the_second_is_replaced_as_the_server_does(self):
        def setup(sets):
            sets.put_slot(0, WEAR_RING1, INVENTORY, 20)
            sets.put_slot(0, WEAR_RING2, INVENTORY, 21)
        self.assertEqual(self.saved(self.drop(9, WEAR_HEAD, setup)), {WEAR_RING2: (INVENTORY, 9)})

    def test_a_ring_dropped_on_a_ring_cell_stays_there(self):
        self.assertEqual(self.saved(self.drop(9, WEAR_RING2)), {WEAR_RING2: (INVENTORY, 9)})

    def test_a_unique_follows_the_same_order(self):
        def setup(sets):
            sets.put_slot(0, WEAR_UNIQUE1, INVENTORY, 20)
        self.assertEqual(self.saved(self.drop(14, None, setup)), {WEAR_UNIQUE2: (INVENTORY, 14)})

    def test_a_worn_ring_keeps_its_own_cell(self):
        cell = EQUIPMENT_SLOT_START + WEAR_RING2
        self.assertEqual(self.saved(self.drop(cell, None)), {WEAR_RING2: (INVENTORY, cell)})

    def test_an_item_already_in_the_set_moves_and_leaves_its_old_cell(self):
        def setup(sets):
            sets.put_slot(0, WEAR_RING1, INVENTORY, 9)
        self.assertEqual(self.saved(self.drop(9, WEAR_RING2, setup)),
                         {WEAR_RING1: (SLOT_EMPTY, 0), WEAR_RING2: (INVENTORY, 9)})

    def test_a_costume_body_dresses_the_buffi_only_on_the_buffi_s_cell(self):
        self.assertEqual(self.saved(self.drop(11, WEAR_BUFFI_BODY)), {WEAR_BUFFI_BODY: (INVENTORY, 11)})
        self.assertEqual(self.saved(self.drop(11, None)), {WEAR_COSTUME_BODY: (INVENTORY, 11)})
        self.assertEqual(self.saved(self.drop(11, WEAR_BUFFI_HAIR)), {WEAR_COSTUME_BODY: (INVENTORY, 11)})

    def test_a_cell_the_server_cannot_use_today_is_not_chosen(self):
        def setup(sets):
            sets.usable.discard(WEAR_COSTUME_BODY)
        effects = self.drop(11, None, setup)
        self.assertEqual(saves(effects), [])
        self.assertEqual(len(chat_lines(effects)), 1)

    def test_what_is_not_equipment_is_refused_with_a_line(self):
        for cell in (12, 15):
            with self.subTest(cell=cell):
                effects = self.drop(cell, None)
                self.assertEqual(saves(effects), [])
                game_world, window = world(False)
                self.assertEqual(chat_lines(effects), [game_world.m("localeInfo").FAST_EQUIP_NOT_FOR_SET])

    def test_an_item_for_another_class_is_refused_with_a_line(self):
        effects = self.drop(13, WEAR_BODY)
        self.assertEqual(saves(effects), [])
        game_world, window = world(False)
        self.assertEqual(chat_lines(effects), [game_world.m("localeInfo").FAST_EQUIP_WRONG_CHARACTER])

    def test_a_press_between_the_cells_with_nothing_attached_does_nothing(self):
        self.assertEqual(self.run_both(lambda g, w: self.gap(g, w)), [])

    def test_a_novaui_release_drops_only_after_a_drag_from_a_grid(self):
        """The canvas's mouseup: a press in a NovaUI grid that attached the
        item, then a drag of 10 px or more (as a cell's release asks); a
        release without that press, or without the drag, drops nothing."""
        for pressed, dragging, expected in ((True, True, 1), (False, True, 0), (True, False, 0)):
            with self.subTest(pressed=pressed, dragging=dragging):
                game_world, window = world(True)
                slots = game_world.game.loaded["nui_slots"]
                P = game_world.game.modules["player"]
                game_world.attach(P.SLOT_TYPE_INVENTORY, 8, ARMOR)
                mark = game_world.mark()
                with game_world.game, w4.quiet():
                    slots._press = (object(), 3) if pressed else None
                    game_world.game.modules["wndMgr"].IsDragging = lambda: dragging
                    w4.fire(window, "canvas_release", 0)
                effects = game_world.effects_since(mark, EFFECTS)
                self.assertEqual(len(saves(effects)), expected)
                self.assertIsNone(slots._press, "the press is forgotten")

    def test_legacy_s_gaps_are_the_drop_catchers_not_a_slot_window(self):
        """A press on a slot window off its slots drops the icon (C++
        CSlotWindow::OnMouseLeftButtonDown), so each cell is its own slot
        window, and the catchers under them take the rest of the area, but
        not the buttons."""
        game_world, window = world(False)
        F = game_world.m("uiFastEquip")
        for wear in window.builtCells:
            x, y, width, height = F.CELLS[wear]
            slots = window.itemSlot.windows[wear]
            self.assertEqual(slots.size, (width, height), wear)
            self.assertEqual(slots.position, (F.SLOT_X + x, F.SLOT_Y + y), wear)
        self.assertTrue(window.dropCatchers)
        buttons = [(171, 290, 61, 21), (271, 290, 61, 21)]
        for catcher in window.dropCatchers:
            cx, cy = catcher.position
            cw, ch = catcher.size
            for bx, by, bw, bh in buttons:
                self.assertFalse(cx < bx + bw and bx < cx + cw and cy < by + bh and by < cy + ch, "a catcher over a button")
        covered = lambda x, y: any(c.position[0] <= x < c.position[0] + c.size[0] and c.position[1] <= y < c.position[1] + c.size[1]
                                   for c in window.dropCatchers)
        for wear in window.builtCells:
            x, y, width, height = F.CELLS[wear]
            self.assertTrue(covered(F.SLOT_X + x, F.SLOT_Y + y) and covered(F.SLOT_X + x + width - 1, F.SLOT_Y + y + height - 1), wear)


def slot_sizes_of(script, names):
    """wear index: (width, height) of a uiscript's slot table, its index
    expressions turned into wear indexes by `names`."""
    sizes = {}
    for index, width, height in re.findall(r'\{"index":\s*([^,]+),\s*"x":[^,]+,\s*"y":[^,]+,\s*"width":(\d+),\s*"height":(\d+)\}', script):
        sizes[eval(index.strip(), {}, names)] = (int(width), int(height))
    return sizes


class TallCells(unittest.TestCase):
    """Eddy (r41): an item two or three cells tall shows at its size in its
    set cell, as the equipment and costume windows show it."""

    def equipment_sizes(self):
        scripts = os.path.join(REPO, "assets", "uiscript", "uiscript")
        item = type("item", (), {"EQUIPMENT_RING1": 28, "EQUIPMENT_RING2": 29, "EQUIPMENT_BELT": 30})
        sizes = slot_sizes_of(w4.read(os.path.join(scripts, "inventorywindow.py")),
                              {"EQUIPMENT_START_INDEX": 0, "item": item})
        costume = {"COSTUME_START_INDEX": 19, "SASH_SLOT_INDEX": 21, "WEAPON_SLOT_INDEX": 22, "AURA_SLOT_INDEX": 39,
                   "WING_SLOT_INDEX": 27, "BUFFI_START_INDEX": 31, "BUFFI_PANEL_X": 216}
        sizes.update(slot_sizes_of(w4.read(os.path.join(scripts, "costumewindow.py")), costume))
        return sizes

    def test_every_wear_cell_has_its_equipment_window_size(self):
        sizes = self.equipment_sizes()
        self.assertEqual(sizes[WEAR_WEAPON], (32, 96))
        self.assertEqual(sizes[WEAR_BUFFI_WEAPON], (32, 96))
        game_world, window = world(False)
        cells = game_world.m("uiFastEquip").CELLS
        for wear, size in sorted(sizes.items()):
            with self.subTest(wear=wear):
                self.assertEqual(cells[wear][2:], size)

    def test_no_two_cells_overlap(self):
        game_world, window = world(False)
        cells = game_world.m("uiFastEquip").CELLS
        boxes = sorted(cells.items())
        for i, (a, (ax, ay, aw, ah)) in enumerate(boxes):
            for b, (bx, by, bw, bh) in boxes[i + 1:]:
                self.assertFalse(ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah, (a, b))
        F = game_world.m("uiFastEquip")
        for wear, (x, y, width, height) in cells.items():
            self.assertLessEqual(x + width, F.SLOT_WIDTH, wear)
            self.assertLessEqual(y + height, F.SLOT_HEIGHT, wear)

    def rules(self, path):
        text = w4.read(path)
        return dict((int(m.group(1)), m.group(2)) for m in re.finditer(r"fastequip__cell--w(\d+) \{([^}]*)\}", text))

    def test_the_novaui_cells_have_the_same_sizes(self):
        game_world, window = world(False)
        cells = game_world.m("uiFastEquip").CELLS
        px = lambda rule, name: float(re.search(r"(?<![-\w])%s: ([\d.]+)dp" % name, rule).group(1))
        modern = self.rules(os.path.join(w4.WINDOWS_DIR, "fastequip", "fastequip.rcss"))
        classic = self.rules(os.path.join(w4.WINDOWS_DIR, "..", "skins", "classic", "windows", "fastequip.rcss"))
        for wear, (x, y, width, height) in cells.items():
            with self.subTest(wear=wear):
                self.assertEqual((px(classic[wear], "left"), px(classic[wear], "top")), (x, y), "classic is legacy's place")
                self.assertEqual((px(classic[wear], "width"), px(classic[wear], "height")), (width, height))
                # Modern: 40dp per 32 px cell, 4dp between two cells of one item.
                self.assertEqual((px(modern[wear], "width"), px(modern[wear], "height")), (40, {32: 40, 64: 80, 96: 120}[height]))

    def test_the_icon_keeps_its_own_size_in_its_cell(self):
        """slot-grid.rcss draws a cell's icon 32 x 32dp unless the cell has
        nui-slot--h2 or --h3: the set's cells give it its own height, as the
        inventory's wear cells do (.inv-wear .nui-slot__icon)."""
        text = w4.read(os.path.join(w4.WINDOWS_DIR, "fastequip", "fastequip.rcss"))
        rule = re.search(r"\.fastequip__cell \.nui-slot__icon\s*\{([^}]*)\}", text)
        self.assertIsNotNone(rule)
        self.assertIn("height: auto;", rule.group(1))

    def test_legacy_draws_a_base_tile_under_each_lower_row_of_a_tall_cell(self):
        game_world, window = world(False)
        cells = game_world.m("uiFastEquip").CELLS
        expected = sum(cells[wear][3] // 32 - 1 for wear in window.builtCells)
        self.assertEqual(len(window.cellTiles), expected)


NAME_FIELD = "fastequip-name"


class Rename(FastEquipTest):
    """Eddy (r41): typing a set's name did nothing. The window's body sets
    focus: none, which RmlUi inherits, so a press never gave the field the
    caret (Context::FindFocusElement), and the panel opened without focusing
    it. Enter saves, Escape closes the panel, both as legacy's edit line."""

    def open_edit(self, game_world, window, index=3):
        if game_world.nui_on:
            w4.press(window, "edit_press", index, 0)
            w4.fire(window, "edit_click", index)
        else:
            window.OpenEditPopup(index)

    def type_name(self, game_world, window, text):
        if game_world.nui_on:
            w4.board(window).set_value(NAME_FIELD, text)
        else:
            window.wndPopUpEdit.nameEditLine.SetText(text)

    def key(self, game_world, window, which):
        if game_world.nui_on:
            nui = game_world.game.modules["nui"]
            code = nui.KEY_RETURN if which == "enter" else nui.KEY_ESCAPE
            self.assertTrue(w4.board(window).key(NAME_FIELD, code), "the field keeps the key")
        else:
            line = window.wndPopUpEdit.nameEditLine
            (line.eventReturn if which == "enter" else line.eventEscape)()

    def test_the_name_field_can_take_the_focus(self):
        sheet = w4.read(os.path.join(w4.WINDOWS_DIR, "fastequip", "fastequip.rcss"))
        rule = re.search(r"\.fastequip__name-input\s*\{([^}]*)\}", sheet).group(1)
        self.assertIn("focus: auto;", rule)
        classic = w4.read(os.path.join(w4.WINDOWS_DIR, "..", "skins", "classic", "windows", "fastequip.rcss"))
        self.assertNotIn("focus: none", classic)

    def test_opening_the_panel_and_pressing_the_field_give_it_the_caret(self):
        game_world, window = world(True)
        with game_world.game, w4.quiet():
            self.open_edit(game_world, window)
            board = w4.board(window)
            self.assertEqual(board.focused, NAME_FIELD, "the panel opens with the caret in the field")
            board.focused = None
            w4.press(window, "name_press", 0)
            self.assertEqual(board.focused, NAME_FIELD, "a press on the field focuses it")

    def test_the_field_s_text_never_enters_the_model(self):
        rml = w4.read(os.path.join(w4.WINDOWS_DIR, "fastequip", "fastequip.rml"))
        field = re.search(r'<input id="fastequip-name"[^>]*>', rml).group(0)
        self.assertNotIn("data-attr-value", field)
        game_world, window = world(True)
        with game_world.game, w4.quiet():
            self.open_edit(game_world, window)
            board = w4.board(window)
            self.assertEqual(board.fields.get(NAME_FIELD), "Set 4")
            self.type_name(game_world, window, "abc")
            self.key(game_world, window, "escape")
            self.open_edit(game_world, window)
            self.assertEqual(board.fields.get(NAME_FIELD), "Set 4", "a new open shows the set's name again")

    def test_enter_saves_the_typed_name(self):
        def flow(game_world, window):
            self.open_edit(game_world, window)
            self.type_name(game_world, window, "Boss")
            self.key(game_world, window, "enter")
            self.assertFalse(window.wndPopUpEdit.IsShow())
        (index, name, color, slots), = saves(self.run_both(flow))
        self.assertEqual((index, name), (3, "Boss"))
        self.assertEqual({s[0] for s in slots}, {SLOT_KEEP})

    def test_escape_closes_the_panel_without_saving(self):
        def flow(game_world, window):
            self.open_edit(game_world, window)
            self.type_name(game_world, window, "Boss")
            self.key(game_world, window, "escape")
            self.assertFalse(window.wndPopUpEdit.IsShow())
            self.assertTrue(window.IsShow(), "the window stays open")
        self.assertEqual(saves(self.run_both(flow)), [])


class HideBeforeInit(unittest.TestCase):
    """ui.Window.__init__ calls Hide before the subclass's __init__ has set its
    attributes, and the stand-in does not."""

    def test_hide_survives_an_unset_self(self):
        for nui_on, name in ((False, "uiFastEquip"), (True, "nui_fastequip")):
            game_world, window = world(nui_on)
            cls = type(window)
            with game_world.game, w4.quiet():
                blank = cls.__new__(cls)
                cls.Hide(blank)


class Board(FastEquipTest):
    def board(self, sets=None):
        game_world, window = world(True, sets)
        return game_world, window, w4.board(window).model

    def test_the_fixture_has_every_model_key(self):
        game_world, window, model = self.board()
        self.assertEqual(set(w4.fixture_keys(window, "fastequip")), set(model))

    def test_the_facade_runs_no_python_per_frame(self):
        game_world, window = world(True)
        self.assertIsNone(type(window).OnUpdate)

    def test_the_board_exists_only_while_the_window_shows(self):
        game_world, window = world(True)
        self.assertIsNotNone(w4.board(window))
        with game_world.game, w4.quiet():
            window.Close()
        self.assertIsNone(w4.board(window))

    def test_a_held_elsewhere_cell_is_marked(self):
        sets = Sets()
        sets.put_slot(0, WEAR_BODY, SLOT_KEEP)
        game_world, window, model = self.board(sets)
        cell = [c for c in model["cells"] if c["index"] == WEAR_BODY][0]
        self.assertTrue(cell["missing"])

    def test_the_equipped_stripe_needs_every_item_on_its_cell(self):
        sets = Sets()
        sets.put_slot(0, WEAR_WEAPON, INVENTORY, EQUIPMENT_SLOT_START + WEAR_WEAPON)
        sets.put_slot(0, WEAR_HEAD, INVENTORY, EQUIPMENT_SLOT_START + WEAR_HEAD)
        game_world, window, model = self.board(sets)
        self.assertTrue(model["equipped"])
        sets = Sets()
        sets.put_slot(0, WEAR_WEAPON, INVENTORY, 7)
        game_world, window, model = self.board(sets)
        self.assertFalse(model["equipped"])


class Hooks(unittest.TestCase):
    def read(self, name):
        return w4.read(os.path.join(ROOT, name))

    def test_game_toggles_on_f10_and_passes_the_refresh(self):
        game = self.read("game.py")
        self.assertIn('"fast_equip": lambda: self.ToggleFastEquip()', game)
        # F10 is its default key (NOVA-121's table).
        self.assertIn('Action("fast_equip", "windows", "KEYBIND_FAST_EQUIP", "Fast equip", (key("F10"),))',
                      self.read("keybindings.py"))
        self.assertIn("def RefreshFastEquip(self, setIndex, switched):", game)

    def test_the_interface_makes_toggles_refreshes_and_hides_it(self):
        interface = self.read("interfacemodule.py")
        self.assertIn('self.wndFastEquip = nui_windows.make("fastequip", uiFastEquip.FastEquipWindow, '
                      '"nui_fastequip.FastEquipWindow")', interface)
        for text in ("def ToggleFastEquipWindow(self):", "self.wndFastEquip.SetItemToolTip(self.tooltipItem)",
                     "hideWindows += self.wndFastEquip,", "self.wndFastEquip.Destroy()",
                     "self.wndFastEquip.RefreshInventory()"):
            self.assertIn(text, interface)

    def test_the_inventory_has_the_button(self):
        self.assertIn("def ClickFastEquipButton(self):", self.read("uiinventory.py"))

    def test_the_novaui_inventory_has_the_button_too(self):
        self.assertIn('self.fastEquipButton.SetEvent(ui.__mem_func__(self.ClickFastEquipButton))', self.read("nui_inventory.py"))
        self.assertIn('@nui.on("fastequip_press")', self.read("nui_inventory.py"))
        rml = w4.read(os.path.join(w4.WINDOWS_DIR, "inventory", "inventory.rml"))
        self.assertIn('id="inv-fastequip"', rml)
        self.assertIn('data-event-mousedown="fastequip_press(ev.button)"', rml)
        script = w4.read(os.path.join(REPO, "assets", "uiscript", "uiscript", "inventorywindow.py"))
        self.assertIn('"name" : "FastEquipButton"', script)

    def test_the_uiscript_keeps_the_window_size_and_old_s_cells(self):
        namespace = {"SCREEN_WIDTH": 1600, "SCREEN_HEIGHT": 900, "__name__": "uiscript"}
        source = w4.read(os.path.join(REPO, "assets", "uiscript", "uiscript", "fastequipwindow.py"))
        source = source.replace("import uiScriptLocale", "uiScriptLocale = type('L', (), {'__getattr__': lambda s, n: n})()")
        exec(compile(source, "fastequipwindow.py", "exec"), namespace)
        self.assertEqual(namespace["window"]["width"], 460)
        game_world, window = world(False)
        cells = game_world.m("uiFastEquip").CELLS
        self.assertEqual(cells[WEAR_WEAPON], (168, 19, 32, 96), "OLD's weapon cell")
        self.assertEqual(cells[WEAR_RING1], (168, 129, 32, 32), "OLD's ring1")


GAME_KEYS = {"FAST_EQUIP_TITLE": "Fast Equipment", "FAST_EQUIP_CLEAR_CONFIRM": "Are you sure you want to clear this page?",
             "FAST_EQUIP_SET_NAME": "Set %d", "FAST_EQUIP_ALREADY": "This set is already equipped.",
             "FAST_EQUIP_NOT_FOR_SET": "This item cannot be part of a set.",
             "FAST_EQUIP_WRONG_CHARACTER": "Your character cannot wear this item."}
INTERFACE_KEYS = {"FAST_EQUIP_TITLE": "Fast Equipment", "FAST_EQUIP_SWITCH": "Switch", "FAST_EQUIP_CLEAR": "Clear",
                  "FAST_EQUIP_SETS": "Sets", "FAST_EQUIP_BUFFI": "Buffi", "FAST_EQUIP_AURA": "Aura",
                  "FAST_EQUIP_BUTTON": "FE", "FAST_EQUIP_MISSING": "Not on this character"}


def read_locale(locale, name):
    keys = {}
    with open(os.path.join(LOCALES, locale, name), encoding="utf-8", errors="replace", newline="") as handle:
        text = handle.read()
    for line in text.split("\n"):
        tokens = line.split("\t")
        if len(tokens) >= 2 and tokens[0]:
            keys[tokens[0]] = tokens[1:]
    return text, keys


class Locales(unittest.TestCase):
    def test_every_locale_has_every_key_with_english_s_specifiers(self):
        locales = sorted(name for name in os.listdir(LOCALES) if os.path.isfile(os.path.join(LOCALES, name, "locale_game.txt")))
        self.assertEqual(len(locales), 17)
        spec = lambda text: re.findall(r"%[-0-9.]*[sdif]", text.replace("%%", ""))
        for locale in locales:
            for name, keys in (("locale_game.txt", GAME_KEYS), ("locale_interface.txt", INTERFACE_KEYS)):
                text, entries = read_locale(locale, name)
                for key, english in keys.items():
                    with self.subTest(locale=locale, file=name, key=key):
                        self.assertIn(key, entries)
                        self.assertEqual(spec(entries[key][0].strip("\r")), spec(english))


if __name__ == "__main__":
    unittest.main()
