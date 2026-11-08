"""Tests for the costume window's Wave 6 parts on NovaUI (NOVA-20, 21, 22, 23):
the sash, weapon costume, sash costume and aura cells, the five show and
hide switches and the aura panel of assets/root/nui_costume.py, against
legacy's uiinventory.CostumeWindow: python3 -B -m unittest nui_costume_test
(from tools/).

Plain CPython over nui_game_support's stand-ins, in nui_inventory_test's
worlds (the committed module constants are the foundation client's, so
both windows use the foundation's 40-slot wear table) with chunk C's names
from wave6_support (the aura wing flags, player.IsShow*,
GetAuraWingFlags), as hide_costume_test builds its legacy world. The
legacy window is made from the real uiscript (install_wave3b_ui), so a
cell or a switch the uiscript gains shows here. Each flow runs on the
legacy window and on the NovaUI one in the same state; the net, player,
mouse, chat and dialog calls must match, and the NovaUI board must show
what the legacy widgets show:
- the loader binds every switch, the slot window and the aura panel's
  boxes as legacy does (LoaderBindsAsLegacy);
- every switch press: the chat line and the down state;
- ResetSlider after a refusal (game.py's ResetCostumeSlider command), and
  Show putting the switches back from the player's state;
- the aura panel opening and closing by its switch, each box's
  "/aura_wing", Close hiding it and setting the switch up;
- the refresh filling every cell of the group, the empty cells' marks;
- a drop on each Wave 6 cell running the inventory's legacy handler;
- the lifecycle: Hide on a bare object, no per-frame Python, no walk-away
  rule (legacy's window has none), every fixture with every model key."""
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_inventory_test as inv  # noqa: E402
import wave6_support as w6  # noqa: E402
import hide_costume_test  # noqa: E402

I = inv.I
COSTUME_START = I["COSTUME_SLOT_START"]
CELLS = {"costume_body": COSTUME_START, "costume_hair": COSTUME_START + 1, "costume_sash": COSTUME_START + 2,
         "costume_weapon": COSTUME_START + 3, "costume_sash2": COSTUME_START + 8, "costume_aura": COSTUME_START + 20}
WAVE6_CELLS = ("costume_sash", "costume_weapon", "costume_sash2", "costume_aura")
# The switches: (board part, legacy list, model key, player getter, command).
SWITCHES = (("body", "costumeButtonList", "show_body", "IsShowCostumes", "set_is_show_costumes"),
            ("hair", "hairButtonList", "show_hair", "IsShowHair", "set_is_show_hair"),
            ("weapon", "weaponButtonList", "show_weapon", "IsShowWeapon", "set_is_show_weapon"),
            ("sash", "sashButtonList", "show_sash", "IsShowSash", "set_is_show_sash"))
FLAGS = w6.C_PLAYER
# Items a flow wears or drops (wave6_support's vnums).
BAG_SASH, BAG_WEAPON, BAG_AURA, BAG_WINGS = 20, 21, 22, 23
WINGS = 48000


def wave6(game):
    """nui_inventory_test's stock, chunk C's names (wave6_support.install_c)
    and a sash, a weapon costume, an aura and a sash costume in the bag."""
    inv.stock(game)
    w6.install_c(game)
    game.give(BAG_SASH, w6.SASH)
    game.give(BAG_WEAPON, w6.WEAPON_COSTUME, size=(1, 2))
    game.give(BAG_AURA, w6.AURA)
    game.give(BAG_WINGS, WINGS)
    for vnum in (w6.SASH, w6.WEAPON_COSTUME, w6.AURA, WINGS):
        game.equipment.add(vnum)


def make_world(nui_on, setup=wave6):
    world = inv.World(nui_on, setup=setup)
    ui = world.game.modules["ui"]
    if not isinstance(getattr(ui, "CheckBox", None), type):
        ui.CheckBox = w6.CheckBox
    return world


def open_costume(world):
    window = world.make_inventory()
    with world.game, inv.quiet():
        window.ClickCostumeButton()
    return window, window.wndCostume


def model(costume):
    shown = inv.board(costume)
    return shown.model if shown is not None else None


def chat_commands(world, mark=0):
    return [args[0] for name, args in world.game.log[mark:] if name == "net.SendChatPacket"]


def handler_name(event):
    """The name of what a widget's event calls: a ui.__mem_func__'s method,
    a bound method, a lambda; (event, args) as legacy's stand-ins keep it."""
    if event is None:
        return None
    if isinstance(event, tuple):
        event = event[0]
    fn = getattr(event, "fn", event)
    fn = getattr(fn, "__func__", fn)
    return getattr(getattr(fn, "__wrapped__", fn), "__name__", repr(fn))


def legacy_events(button):
    """The (up, down) events a legacy toggle button was given: the Wave 3b
    stand-in keeps them (eventUp, eventDown), a recording widget logs its
    calls (wave6_support.toggles)."""
    if getattr(button, "eventUp", None) is not None or getattr(button, "eventDown", None) is not None:
        return button.eventUp, button.eventDown
    return w6.toggles(button)


class Both(unittest.TestCase):
    """A legacy world and a NovaUI world, each with the costume window open."""

    def worlds(self, setup=wave6):
        pair = []
        for nui_on in (False, True):
            world = make_world(nui_on, setup)
            window, costume = open_costume(world)
            pair.append((world, window, costume))
        return pair

    def switch(self, world, costume, part):
        """A left press on a switch: the toggle button's (legacy) or the
        board's cos_switch (NovaUI)."""
        attribute = dict((p[0], p[1]) for p in SWITCHES + (("wing", "wingButtonList", None, None, None),))[part]
        with world.game, inv.quiet():
            if world.nui_on:
                inv.press(costume, "cos_switch", part, 0)
            else:
                costume.SetTop()
                getattr(costume, attribute)[0].click()

    def wing_row(self, world, costume, index):
        """A left press on an aura panel row: the check box's release
        (legacy) or the board's cos_wing_row (NovaUI)."""
        with world.game, inv.quiet():
            if world.nui_on:
                inv.press(costume, "cos_wing_row", index, 0)
            else:
                costume.SetTop()
                costume.auraWingChecks[index][1].OnMouseLeftButtonUp()

    def effects(self, world, mark):
        return world.effects_since(mark)


class Grouping(unittest.TestCase):
    def test_the_novaui_window_holds_the_legacy_uiscripts_cells(self):
        """The costume group (nui_limits) is the cells legacy's uiscript
        gives its slot window, in the foundation's table."""
        legacy, novaui = make_world(False), make_world(True)
        _, a = open_costume(legacy)
        _, b = open_costume(novaui)
        self.assertEqual(novaui.m("nui_limits").current().WEAR_TABLE_ID, "old")
        self.assertEqual(sorted(b.wndEquip.slot_numbers), sorted(a.wndEquip.slots))
        self.assertEqual([cell["name"] for cell in model(b)["slots"]],
                         ["costume_body", "costume_hair", "costume_sash", "costume_weapon", "costume_sash2",
                          "costume_aura"])


class LoaderBindsAsLegacy(Both):
    """The loader copies legacy's bindings: each legacy handler is bound to
    the same event of the same widget in both worlds."""

    def test_the_slot_window_and_the_switches(self):
        (_, _, a), (_, _, b) = self.worlds()
        theirs = dict((key, handler_name(value)) for key, value in a.wndEquip.events.items() if value)
        mine = dict((key, handler_name(value)) for key, value in b.wndEquip.handlers().items() if value)
        self.assertEqual(mine, theirs)
        for attribute in ("costumeButtonList", "hairButtonList", "weaponButtonList", "sashButtonList", "wingButtonList"):
            self.assertEqual(len(getattr(b, attribute)), len(getattr(a, attribute)), attribute)
            for legacy_button, proxy in zip(getattr(a, attribute), getattr(b, attribute)):
                up, down = legacy_events(legacy_button)
                self.assertEqual((handler_name(proxy.event_up), handler_name(proxy.event_down)),
                                 (handler_name(up), handler_name(down)), attribute)
                self.assertIsNotNone(handler_name(proxy.event_down), attribute)

    def test_the_aura_panel_s_boxes(self):
        """Legacy's __CreateAuraWingPanel against the replica: the same
        flags in the same order, the same labels, both events on, and each
        event sends what legacy's sends."""
        pair = self.worlds()
        boxes = []
        for world, _, costume in pair:
            self.switch(world, costume, "wing")
            boxes.append(costume.auraWingChecks)
        (a_world, _, a), (b_world, _, b) = pair
        self.assertEqual([flag for flag, _ in boxes[1]], [flag for flag, _ in boxes[0]])
        self.assertEqual([flag for flag, _ in boxes[0]], [FLAGS["AURA_WING_FLAG_WING"], FLAGS["AURA_WING_FLAG_AURA"],
                                                         FLAGS["AURA_WING_FLAG_EFFECT"]])
        self.assertEqual([box.text for _, box in boxes[1]], [box.text for _, box in boxes[0]])
        self.assertEqual([box.text for _, box in boxes[1]], ["Wings", "Aura", "Aura Wing Effect"])
        for (_, legacy_box), (_, proxy) in zip(boxes[0], boxes[1]):
            for kind in ("ON_CHECK", "ON_UNCHECK"):
                self.assertIsNotNone(legacy_box.events[kind])
                self.assertIsNotNone(proxy.events[kind])
                sent = []
                for world, box in ((a_world, legacy_box), (b_world, proxy)):
                    mark = len(world.game.log)
                    with world.game, inv.quiet():
                        box.events[kind]()
                    sent.append(chat_commands(world, mark))
                self.assertEqual(sent[1], sent[0], kind)
        self.assertEqual(b.auraWingPanel.size, (150, 20 + 20 * 3))
        self.assertIn("float", b.auraWingPanel.flags)


class Switches(Both):
    def test_every_switch_press_sends_the_chat_line_and_shows_the_new_state(self):
        for part, attribute, key, getter, command in SWITCHES:
            for state in (1, 0):
                with self.subTest(switch=part, shown=state):
                    results = []
                    for world, _, costume in self.worlds():
                        world.game.shown_costumes[getter] = state
                        with world.game, inv.quiet():
                            costume.ResetSlider()
                        mark = world.mark()
                        self.switch(world, costume, part)
                        results.append((self.effects(world, mark), getattr(costume, attribute)[0].down))
                        if world.nui_on:
                            self.assertEqual(model(costume)[key], getattr(costume, attribute)[0].down)
                    self.assertEqual(results[1], results[0])
                    self.assertIn(("net.SendChatPacket", ("/%s %d" % (command, 1 - state),)), results[0][0])
                    self.assertEqual(results[0][1], not state, "the button shows the new state")

    def test_reset_slider_after_a_refusal_puts_the_server_state_back(self):
        """The server refuses a switch while fighting; its
        ResetCostumeSlider command (game.py __ResetCostumeSlider) calls
        ResetSlider, and the switches show its state again."""
        downs = []
        for world, window, costume in self.worlds():
            self.switch(world, costume, "body")
            self.assertFalse(costume.costumeButtonList[0].down)
            if world.nui_on:
                self.assertFalse(model(costume)["show_body"])
            game = hide_costume_test.game_window(window)
            world.game.shown_costumes["IsShowHair"] = 0
            mark = world.mark()
            with world.game, inv.quiet():
                game._GameWindow__ResetCostumeSlider()
            self.assertEqual(self.effects(world, mark), [])
            downs.append([getattr(costume, p[1])[0].down for p in SWITCHES])
            if world.nui_on:
                self.assertEqual([model(costume)[p[2]] for p in SWITCHES], downs[-1])
        self.assertEqual(downs[1], downs[0])
        self.assertEqual(downs[0], [True, False, True, True])

    def test_show_sets_the_switches_from_the_player_s_state(self):
        downs = []
        for world, window, costume in self.worlds():
            with world.game, inv.quiet():
                window.ClickCostumeButton()
            self.assertFalse(costume.IsShow())
            world.game.shown_costumes.update(IsShowCostumes=0, IsShowHair=1, IsShowWeapon=0, IsShowSash=1)
            with world.game, inv.quiet():
                window.ClickCostumeButton()
            self.assertTrue(costume.IsShow())
            downs.append([getattr(costume, p[1])[0].down for p in SWITCHES])
            if world.nui_on:
                self.assertEqual([model(costume)[p[2]] for p in SWITCHES], downs[-1])
        self.assertEqual(downs[1], downs[0])
        self.assertEqual(downs[0], [False, True, False, True])

    def test_a_press_with_another_button_does_nothing(self):
        world = make_world(True)
        _, costume = open_costume(world)
        mark = world.mark()
        with world.game, inv.quiet():
            inv.press(costume, "cos_switch", "body", 1)
            inv.press(costume, "cos_wing_row", 0, 1)
        self.assertEqual(chat_commands(world, mark), [])
        self.assertTrue(costume.costumeButtonList[0].down)


class AuraPanel(Both):
    def panel_state(self, world, costume):
        panel = costume.auraWingPanel
        state = (bool(panel and panel.IsShow()), costume.wingButtonList[0].down,
                 [bool(box.GetCheckStatus()) for _, box in costume.auraWingChecks])
        if world.nui_on:
            board = model(costume)
            self.assertEqual((board["wing_open"], board["wing_down"],
                              [row["checked"] for row in board["wing_rows"]]), state)
            if board["wing_rows"]:
                self.assertEqual([row["key"] for row in board["wing_rows"]], ["wing", "aura", "effect"])
        return state

    def test_the_switch_opens_and_closes_the_panel(self):
        states = []
        for world, _, costume in self.worlds():
            world.game.shown_costumes["GetAuraWingFlags"] = FLAGS["AURA_WING_FLAG_WING"] | FLAGS["AURA_WING_FLAG_EFFECT"]
            mark = world.mark()
            run = [self.panel_state(world, costume)]
            self.switch(world, costume, "wing")
            run.append(self.panel_state(world, costume))
            self.switch(world, costume, "wing")
            run.append(self.panel_state(world, costume))
            self.switch(world, costume, "wing")
            run.append(self.panel_state(world, costume))
            run.append(self.effects(world, mark))
            states.append(run)
        self.assertEqual(states[1], states[0])
        self.assertEqual(states[0][:4], [(False, False, []), (True, True, [True, False, True]),
                                         (False, False, [True, False, True]), (True, True, [True, False, True])])

    def test_each_box_sends_aura_wing_with_its_flag_flipped(self):
        for index, flag in enumerate((1, 2, 4)):
            with self.subTest(row=index):
                sent = []
                for world, _, costume in self.worlds():
                    self.switch(world, costume, "wing")
                    mark = world.mark()
                    self.wing_row(world, costume, index)
                    sent.append((self.effects(world, mark), self.panel_state(world, costume)))
                self.assertEqual(sent[1], sent[0])
                self.assertIn(("net.SendChatPacket", ("/aura_wing %d" % (7 ^ flag),)), sent[0][0])

    def test_a_row_press_while_the_panel_is_closed_does_nothing(self):
        world = make_world(True)
        _, costume = open_costume(world)
        self.switch(world, costume, "wing")
        self.switch(world, costume, "wing")
        mark = world.mark()
        with world.game, inv.quiet():
            costume.nui_wing_row(0)
            costume.nui_wing_row(7)
        self.assertEqual(chat_commands(world, mark), [])

    def test_close_hides_the_panel_and_sets_the_switch_up(self):
        states = []
        for world, window, costume in self.worlds():
            self.switch(world, costume, "wing")
            with world.game, inv.quiet():
                if world.nui_on:
                    inv.fire(costume, "close_press", 0)
                else:
                    costume.Close()
            states.append((bool(costume.IsShow()), bool(costume.auraWingPanel.IsShow()), costume.wingButtonList[0].down))
            if world.nui_on:
                self.assertFalse(costume._state["wing_open"])
                self.assertFalse(costume._state["wing_down"])
        self.assertEqual(states[1], states[0])
        self.assertEqual(states[0], (False, False, False))

    def test_reset_slider_updates_the_open_panel(self):
        states = []
        for world, window, costume in self.worlds():
            self.switch(world, costume, "wing")
            world.game.shown_costumes["GetAuraWingFlags"] = FLAGS["AURA_WING_FLAG_AURA"]
            with world.game, inv.quiet():
                hide_costume_test.game_window(window)._GameWindow__ResetCostumeSlider()
            states.append(self.panel_state(world, costume))
        self.assertEqual(states[1], states[0])
        self.assertEqual(states[0], (True, True, [False, True, False]))


class Cells(Both):
    def worn(self, game):
        wave6(game)
        game.give(CELLS["costume_body"], 41001)
        game.give(CELLS["costume_hair"], 73001)
        game.give(CELLS["costume_sash"], w6.SASH)
        game.give(CELLS["costume_weapon"], w6.WEAPON_COSTUME, size=(1, 2))
        game.give(CELLS["costume_sash2"], WINGS)
        game.give(CELLS["costume_aura"], w6.AURA)

    def test_the_refresh_fills_every_cell(self):
        (legacy, _, a), (novaui, _, b) = self.worlds(self.worn)
        shown = dict((cell, slot["vnum"]) for cell, slot in a.wndEquip.slots.items() if slot["vnum"])
        cells = dict((cell["name"], cell) for cell in model(b)["slots"])
        mine = dict((CELLS[name], cell["ref"]) for name, cell in cells.items() if cell["kind"])
        self.assertEqual(sorted(mine), sorted(shown), "the filled cells")
        player = novaui.game.modules["player"]
        with novaui.game:
            for name, cell in cells.items():
                self.assertEqual(cell["ref"], CELLS[name], name)
                self.assertEqual(cell["marks"], [], name)
                self.assertTrue(cell["icon"], name)
        self.assertEqual(shown[CELLS["costume_aura"]], w6.AURA)
        self.assertEqual(shown[CELLS["costume_weapon"]], w6.WEAPON_COSTUME)

    def test_the_empty_wave6_cells_show_their_marks(self):
        (_, _, b), = self.worlds()[1:]
        marks = dict((cell["name"], cell["marks"]) for cell in model(b)["slots"])
        self.assertEqual(marks, {"costume_body": [], "costume_hair": [], "costume_sash": ["pentagon"],
                                 "costume_weapon": ["sword"], "costume_sash2": ["chevron-down"],
                                 "costume_aura": ["ring"]})

    def test_a_drop_on_each_wave6_cell_is_the_inventory_s_legacy_move(self):
        bag = {"costume_sash": BAG_SASH, "costume_weapon": BAG_WEAPON, "costume_aura": BAG_AURA,
               "costume_sash2": BAG_WINGS}
        vnums = {"costume_sash": w6.SASH, "costume_weapon": w6.WEAPON_COSTUME, "costume_aura": w6.AURA,
                 "costume_sash2": WINGS}
        for name in WAVE6_CELLS:
            with self.subTest(cell=name):
                results = []
                for world, window, costume in self.worlds():
                    with world.game, inv.quiet():
                        inv.attach("SLOT_TYPE_INVENTORY", bag[name], vnums[name])(world, window)
                        mark = world.mark()
                        inv.Input(world, window).drop("costume", CELLS[name])
                    results.append(world.effects_since(mark))
                self.assertEqual(results[1], results[0])
                names = [call for call, _ in results[0]]
                self.assertTrue(any(call.startswith("net.SendItem") for call in names), results[0])

    def test_a_use_and_a_hover_of_each_wave6_cell_are_the_inventory_s(self):
        for name in WAVE6_CELLS:
            with self.subTest(cell=name):
                results = []
                for world, window, costume in self.worlds(self.worn):
                    with world.game, inv.quiet():
                        mark = world.mark()
                        i = inv.Input(world, window)
                        i.use("costume", CELLS[name])
                        i.over("costume", CELLS[name])
                    results.append((world.effects_since(mark), list(window.tooltipItem.shown)))
                self.assertEqual(results[1], results[0])
                self.assertIn("net.SendItemUsePacket", [call for call, _ in results[0][0]])


class Lifecycle(unittest.TestCase):
    def test_hide_on_a_bare_object_does_not_raise(self):
        """ui.Window's __init__ may hide the window before the NovaUI
        __init__ set its attributes."""
        world = make_world(True)
        _, costume = open_costume(world)
        cls = type(costume)
        bare = cls.__new__(cls)
        with world.game, inv.quiet():
            try:
                bare.Hide()
            except AttributeError as error:
                self.assertNotIn("_events", str(error))
                self.assertNotIn("demand", str(error))

    def test_no_python_runs_per_frame(self):
        world = make_world(True)
        _, costume = open_costume(world)
        self.assertIsNone(type(costume).OnUpdate)
        legacy = world.m("uiInventory").CostumeWindow
        self.assertNotIn("OnUpdate", vars(legacy), "legacy's window has no per-frame rule, so no walk-away watch")
        self.assertFalse([name for name, _ in world.game.log if "WatchLeaveRange" in name])

    def test_the_kept_board_holds_no_aura_row_while_hidden(self):
        world = make_world(True)
        window, costume = open_costume(world)
        with world.game, inv.quiet():
            inv.press(costume, "cos_switch", "wing", 0)
            window.ClickCostumeButton()
        kept = costume.demand.kept()
        self.assertEqual((kept.model["wear_on"], kept.model["wing_rows"]), ([], []))
        with world.game, inv.quiet():
            window.ClickCostumeButton()
        self.assertEqual(len(model(costume)["wing_rows"]), 3)


class Fixtures(unittest.TestCase):
    def fixtures(self):
        folder = os.path.join(inv.WINDOWS, "costume")
        for file_name in sorted(os.listdir(folder)):
            if file_name.endswith(".fixture.json"):
                with open(os.path.join(folder, file_name), encoding="utf-8") as handle:
                    yield file_name, json.load(handle)["costume"]

    def test_every_fixture_has_every_model_key(self):
        world = make_world(True)
        _, costume = open_costume(world)
        with world.game, inv.quiet():
            inv.press(costume, "cos_switch", "wing", 0)
        state = costume._state
        cell_keys = sorted(state["slots"][0])
        row_keys = sorted(state["wing_rows"][0])
        names = []
        for file_name, fixture in self.fixtures():
            names.append(file_name)
            self.assertEqual(sorted(fixture), sorted(state), file_name)
            for key, value in state.items():
                self.assertEqual(type(fixture[key]), type(value), "%s %s" % (file_name, key))
            for cell in fixture["slots"]:
                self.assertEqual(sorted(cell), cell_keys, file_name)
            for row in fixture["wing_rows"]:
                self.assertEqual(sorted(row), row_keys, file_name)
        self.assertIn("costume.foundation-full.fixture.json", names)
        self.assertIn("costume.foundation-aura.fixture.json", names)


if __name__ == "__main__":
    unittest.main()
