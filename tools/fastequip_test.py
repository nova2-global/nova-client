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
EFFECTS = ("fastEquip", "mouse") + ("mouseModule",)

SLOT_EMPTY, SLOT_KEEP = 0, 255
WEAR_COUNT = 40
INVENTORY, EXTRA = 1, 6
SWORD, HELMET = 11, 12021          # vnums used by the stand-in
WEAR_WEAPON, WEAR_HEAD, WEAR_BODY, WEAR_RING1, WEAR_BUFFI_HAIR, WEAR_AURA = 4, 1, 0, 28, 32, 39
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
    support.define(item, "IsAntiFlag", lambda flag: False)
    kinds = {SWORD: (item.ITEM_TYPE_WEAPON, item.WEAPON_SWORD)}
    support.define(item, "GetItemType", lambda: kinds.get(item.selected[0], (0, 0))[0])
    support.define(item, "GetItemSubType", lambda: kinds.get(item.selected[0], (0, 0))[1])
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
        """A press on the wear cell's slot."""
        if game_world.nui_on:
            w4.press(window, "slot_press", wear, button)
            if button == 0:
                w4.fire(window, "slot_release", wear, button)
            return
        slots = window.itemSlot
        filled = bool(slots.slots.get(wear, {}).get("vnum"))
        if button == 1:
            slots.events["unselect_item"](wear)
        elif filled:
            slots.events["select_item"](wear)
        else:
            slots.events["select_empty"](wear)

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

    def test_the_drag_filter_refuses_a_sword_on_the_head(self):
        def flow(game_world, window):
            P = game_world.game.modules["player"]
            game_world.attach(P.SLOT_TYPE_INVENTORY, 7, SWORD)
            self.wear(game_world, window, WEAR_HEAD)
        self.assertEqual(saves(self.run_both(flow)), [])

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
                w4.fire(window, "name_typed", "PvP")
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
                    self.assertEqual(sorted(window.itemSlot.slots), sorted({WEAR_WEAPON, WEAR_RING1}))


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
        self.assertIn("onPressKeyDict[app.DIK_F10]\t= lambda: self.ToggleFastEquip()", game)
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
             "FAST_EQUIP_SET_NAME": "Set %d", "FAST_EQUIP_ALREADY": "This set is already equipped."}
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
