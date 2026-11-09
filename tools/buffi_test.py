"""Tests for the legacy client's buffi (NOVA-38, OLD's __FAKE_BUFF__ client
half: ENABLE_FAKE_BUFF in OLD's locale_inc.h): python3 -B -m unittest
buffi_test (from tools/).

The C++ half (item.COSTUME_BUFFI_SLOT_START, COSTUME_BUFFI_SLOT_COUNT 5,
item.ITEM_TYPE_FAKE_BUFF_INT_BOOST 36, item.IsFakeBuffIntBoost,
chr.AFFECT_BUFFI_NAME 553, player.IsHideBuffi and the game window's
BINARY_OnBuffiHide on GC::BUFFI_HIDE) is the client fork's; the equip rules,
the summon, the INT boost and /hide_buffi are the server's. Here the legacy
Python runs over nui_game_support's stand-ins with those names (install_buffi):
- the costume window has OLD's buffi panel (OLD uiscript/costumewindow.py:54,
  74-76): the buffi's costume body, hair and weapon costume cells (wear 31,
  32, 33), which it refreshes (OLD uiInventory.py:193-206) and whose drop,
  use and hover are the inventory's, so a costume dropped on one moves to
  that cell and a use takes it off; the wings and facial cells (wear 34, 35)
  are not shown, as NEW has neither costume;
- an INT booster is used on a buffi item (OLD uiInventory.py:1919-1920,
  2206-2207, 2236-2238), and a summoned buffi item's cell is active (OLD
  uiInventory.py:1476-1479, socket 3);
- a buffi item's tooltip shows its INT (OLD uiToolTip.py:1413-1414);
- the affect shower shows the name scroll's affect (OLD uiAffectShower.py:664);
- the game options' hide-buffi row (OLD uiGameOption.py:1174, 1220-1223)
  sends /hide_buffi and shows the server's state, which GC::BUFFI_HIDE
  refreshes through the game window and the Interface;
- the strings are in every locale."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import legacy_foundation_test as lf  # noqa: E402
import nui_game_support as support  # noqa: E402
import wave6_support as w6  # noqa: E402

BUFFI_START = w6.EQUIPMENT_START + 31
BUFFI_BODY, BUFFI_HAIR, BUFFI_WEAPON = BUFFI_START, BUFFI_START + 1, BUFFI_START + 2
BUFFI_WINGS, BUFFI_FACIAL = BUFFI_START + 3, BUFFI_START + 4
AFFECT_BUFFI_NAME = 553

# NEW's runtime item_proto: a permanent dragon buffi, an INT booster (+20,
# ITEM_FAKE_BUFF_INT_BOOST), the name scroll.
BUFFI = 91010
BOOSTER = 91031
NAME_SCROLL = 91035

C_ITEM = {"COSTUME_BUFFI_SLOT_START": BUFFI_START, "COSTUME_BUFFI_SLOT_COUNT": 5,
          "COSTUME_BUFFI_SLOT_END": BUFFI_START + 5, "ITEM_TYPE_FAKE_BUFF_INT_BOOST": 36}


def install_buffi(game, hidden=None):
    """The client fork's names on the world's modules: the item constants,
    IsFakeBuffIntBoost (the booster's vnum only), chr.AFFECT_BUFFI_NAME and
    player.IsHideBuffi answering from `hidden` (a dict, {"hidden": bool})."""
    item, player, chr_module = game.modules["item"], game.modules["player"], game.modules["chr"]
    for name, value in C_ITEM.items():
        setattr(item, name, value)
    support.define(item, "IsFakeBuffIntBoost", lambda vnum: vnum == BOOSTER)
    chr_module.AFFECT_BUFFI_NAME = AFFECT_BUFFI_NAME
    state = hidden if hidden is not None else {"hidden": False}
    support.define(player, "IsHideBuffi", lambda: state["hidden"])
    return state


class World(w6.World):
    def __init__(self):
        w6.World.__init__(self)
        self.hidden = install_buffi(self.game)


# --- the costume window -------------------------------------------------------------------------------

class CostumePanel(unittest.TestCase):
    def slots(self):
        world = World()
        with world.game:
            window = lf.read_uiscript(os.path.join(w6.UISCRIPT, "costumewindow.py"))["window"]
        return world, window, dict((slot["index"], slot) for slot in lf.child(window, "CostumeSlot")["slot"])

    def test_the_uiscript_has_the_buffi_s_body_hair_and_weapon_cells(self):
        world, window, slots = self.slots()
        sizes = dict((index, (slots[index]["width"], slots[index]["height"])) for index in slots if BUFFI_START <= index < BUFFI_START + 5)
        self.assertEqual(sizes, {BUFFI_BODY: (32, 64), BUFFI_HAIR: (32, 32), BUFFI_WEAPON: (32, 96)})
        self.assertNotIn(BUFFI_WINGS, slots, "NEW has no wings costume")
        self.assertNotIn(BUFFI_FACIAL, slots, "NEW has no facial costume")

    def test_the_cells_keep_olds_places_to_each_other(self):
        """OLD uiscript/costumewindow.py:74-76: the hair 2 left of the body
        and 44 above it, the weapon 41 left of it and 28 above it."""
        world, window, slots = self.slots()
        body, hair, weapon = slots[BUFFI_BODY], slots[BUFFI_HAIR], slots[BUFFI_WEAPON]
        self.assertEqual((hair["x"] - body["x"], hair["y"] - body["y"]), (-2, -44))
        self.assertEqual((weapon["x"] - body["x"], weapon["y"] - body["y"]), (-41, -28))

    def test_the_panel_widens_the_window_and_has_olds_title(self):
        world, window, slots = self.slots()
        self.assertGreater(window["width"], 216, "the buffi panel beside the costume cells")
        board = lf.child(window, "board")
        self.assertEqual(board["width"], window["width"])
        title = lf.child(window, "BuffiTitle")
        locale = world.game.modules["uiScriptLocale"]
        self.assertEqual(title["text"], locale.COSTUME_WINDOW_BUFFICOSTUME)
        slot_window = lf.child(window, "CostumeSlot")
        for index in (BUFFI_BODY, BUFFI_HAIR, BUFFI_WEAPON):
            right = slot_window["x"] + slots[index]["x"] + slots[index]["width"]
            bottom = slot_window["y"] + slots[index]["y"] + slots[index]["height"]
            self.assertLessEqual(right, slot_window["x"] + slot_window["width"])
            self.assertLessEqual(bottom, slot_window["y"] + slot_window["height"])
            self.assertLess(right, window["width"])
            self.assertLess(bottom, window["height"])

    def test_the_window_shows_the_worn_buffi_costumes(self):
        world = World()
        world.game.give(BUFFI_BODY, w6.BODY_COSTUME)
        world.game.give(BUFFI_WEAPON, w6.WEAPON_COSTUME)
        _, window = w6.costume_window(world)
        shown = dict((index, slot["vnum"]) for index, slot in window.wndEquip.slots.items() if slot["vnum"])
        self.assertEqual({BUFFI_BODY: w6.BODY_COSTUME, BUFFI_WEAPON: w6.WEAPON_COSTUME}, shown)

    def test_a_refresh_takes_a_removed_one_off(self):
        world = World()
        world.game.give(BUFFI_HAIR, 45001)
        inventory, window = w6.costume_window(world)
        world.game.items.pop(BUFFI_HAIR)
        with world.game, lf.quiet():
            inventory.RefreshEquipSlotWindow()
        self.assertEqual(window.wndEquip.slots[BUFFI_HAIR]["vnum"], 0)

    def test_a_costume_dropped_on_an_empty_buffi_cell_moves_there(self):
        world = World()
        world.game.give(3, w6.BODY_COSTUME)
        inventory, window = w6.costume_window(world)
        world.attach(world.game.modules["player"].SLOT_TYPE_INVENTORY, 3, w6.BODY_COSTUME)
        del world.game.log[:]
        with world.game, lf.quiet():
            window.wndEquip.fire("select_empty", BUFFI_BODY)
        moves = [args for name, args in world.game.log if name.startswith("net.SendItemMove")]
        self.assertEqual(len(moves), 1)
        self.assertIn(3, moves[0])
        self.assertIn(BUFFI_BODY, moves[0])

    def test_a_use_of_a_buffi_cell_is_the_inventorys_unequip(self):
        world = World()
        world.game.give(BUFFI_HAIR, 45001)
        inventory, window = w6.costume_window(world)
        del world.game.log[:]
        with world.game, lf.quiet():
            window.wndEquip.fire("use", BUFFI_HAIR)
        sent = [args for name, args in world.game.log if name.startswith("net.SendItemUse")]
        self.assertEqual(len(sent), 1)
        self.assertIn(BUFFI_HAIR, sent[0])

    def test_a_hover_shows_the_inventorys_tooltip_of_the_cell(self):
        world = World()
        world.game.give(BUFFI_WEAPON, w6.WEAPON_COSTUME)
        inventory, window = w6.costume_window(world)
        with world.game, lf.quiet():
            window.wndEquip.fire("over_in", BUFFI_WEAPON)
        calls = [call for call in inventory.tooltipItem.calls if call[0] == "SetInventoryItem"]
        self.assertEqual(calls[-1][1], BUFFI_WEAPON)


# --- the INT booster and the summoned item -----------------------------------------------------------

class IntBooster(unittest.TestCase):
    def world(self):
        world = World()
        world.game.give(0, BUFFI)
        world.game.give(1, BOOSTER, count=3)
        world.game.give(2, 27001)
        inventory = w6.make_inventory(world)
        return world, inventory

    def test_a_booster_dropped_on_a_buffi_item_is_used_on_it(self):
        world, inventory = self.world()
        world.attach(world.game.modules["player"].SLOT_TYPE_INVENTORY, 1, BOOSTER)
        del world.game.log[:]
        with world.game, lf.quiet():
            inventory.wndItem.fire("select_item", 0)
        used = [args for name, args in world.game.log if name.startswith("net.SendItemUseToItem")]
        self.assertEqual(len(used), 1)
        self.assertEqual(used[0][:2], (1, 0))

    def test_picking_a_booster_up_turns_the_use_mode_on(self):
        world, inventory = self.world()
        with world.game, lf.quiet():
            inventory.wndItem.fire("select_item", 1)
        self.assertTrue(inventory.wndItem.use_mode)

    def test_a_booster_over_a_buffi_item_marks_it_usable_and_over_another_item_not(self):
        world, inventory = self.world()
        world.attach(world.game.modules["player"].SLOT_TYPE_INVENTORY, 1, BOOSTER)
        with world.game, lf.quiet():
            inventory.wndItem.fire("over_in", 0)
        self.assertTrue(inventory.wndItem.usable)
        with world.game, lf.quiet():
            inventory.wndItem.fire("over_in", 2)
        self.assertFalse(inventory.wndItem.usable)

    def test_a_summoned_buffi_item_is_active(self):
        """OLD uiInventory.py:1476-1479: its socket 3 is set while it is out."""
        world = World()
        world.game.give(0, BUFFI, sockets=(0, 0, 0, 1))
        world.game.give(4, BUFFI + 6)
        inventory = w6.make_inventory(world)
        self.assertTrue(inventory.wndItem.slots[0]["active"])
        self.assertFalse(inventory.wndItem.slots[4]["active"])
        world.game.items[0]["sockets"][3] = 0
        with world.game, lf.quiet():
            inventory.RefreshBagSlotWindow()
        self.assertFalse(inventory.wndItem.slots[0]["active"])


# --- the tooltip --------------------------------------------------------------------------------------

class ToolTip(unittest.TestCase):
    ROW = dict(lf.ITEM_BASE, name="Dragon Buffi (Permanent)", type=3, subtype=6, values=[1, 0, 0, 0, 0, 0],
               icon="icon/item/buffi.tga")

    def test_a_buffi_item_shows_its_int(self):
        corpus_tool, world = w6.tooltip_world({BUFFI: self.ROW})
        install_buffi(world.game)
        attrs = [[0, 0], [0, 0], [0, 0], [0, 0], [0, 140]]
        texts, error = w6.tooltip_texts(corpus_tool, world, {"context": "AddItemData", "vnum": BUFFI, "attrs": attrs})
        self.assertIsNone(error)
        locale = world.game.modules["localeInfo"]
        self.assertIn(locale.TOOLTIP_INT(140), texts)

    def test_another_item_shows_no_int_line(self):
        corpus_tool, world = w6.tooltip_world({27001: dict(self.ROW, name="Red Potion")})
        install_buffi(world.game)
        attrs = [[0, 0], [0, 0], [0, 0], [0, 0], [0, 140]]
        texts, error = w6.tooltip_texts(corpus_tool, world, {"context": "AddItemData", "vnum": 27001, "attrs": attrs})
        self.assertIsNone(error)
        self.assertNotIn(world.game.modules["localeInfo"].TOOLTIP_INT(140), texts)


# --- the affect shower --------------------------------------------------------------------------------

class NameAffect(unittest.TestCase):
    def test_the_name_scroll_s_affect_shows_its_bonus(self):
        """OLD uiAffectShower.py:664: the scroll's +5% against monsters, from
        the affect's value (the server's AddAffect(AFFECT_BUFFI_NAME,
        POINT_ATTBONUS_MONSTER, 5, ...))."""
        import nui_hud_test as hud

        def setup(game):
            hud.affect_setup(game)
            game.modules["chr"].AFFECT_BUFFI_NAME = AFFECT_BUFFI_NAME
            # The real entry is typed SA (a function): the HUD stand-in's form.
            game.modules["localeInfo"].TOOLTIP_APPLY_ATTBONUS_MONSTER = lambda value: "MONSTER(%s)" % value

        world = hud.HudWorld(False, setup=setup)
        with world:
            shower = world.make("affects", world.module("uiAffectShower").AffectShower, "nui_affects.AffectShower")
            with hud.quiet():
                shower.BINARY_NEW_AddAffect(AFFECT_BUFFI_NAME, 0, 5, 1209600)
        self.assertIn(AFFECT_BUFFI_NAME, shower.affectImageDict)
        image = shower.affectImageDict[AFFECT_BUFFI_NAME]
        locale = world.game.modules["localeInfo"]
        self.assertEqual(image.description, locale.TOOLTIP_APPLY_ATTBONUS_MONSTER(5.0))
        # OLD's icon/item/91035.tga is not in NEW's packs (old_content).
        self.assertEqual(image.image, "d:/ymir work/ui/skill/common/affect/att_bonus.sub")

    def test_the_icon_ships(self):
        import old_content
        self.assertNotIn("icon/item/%d.tga" % NAME_SCROLL, old_content.published_files())
        self.assertIn(old_content.store_name("d:/ymir work/ui/skill/common/affect/att_bonus.sub"),
                      old_content.published_files())


# --- the game options ---------------------------------------------------------------------------------

class HideBuffi(unittest.TestCase):
    def world(self, hidden):
        import nui_sys_test as sys_test
        world = sys_test.World(False)
        state = install_buffi(world.game, {"hidden": hidden})
        world.state = state
        world.__enter__()
        self.addCleanup(world.__exit__)
        dialog = world.make_game_options()
        dialog.Show()
        return world, dialog

    @staticmethod
    def buttons(dialog):
        return [button.down for button in dialog.hideBuffiButtonList]

    def test_the_option_shows_the_server_s_state(self):
        world, dialog = self.world(False)
        self.assertEqual(self.buttons(dialog), [True, False], "buffi shown")
        world, dialog = self.world(True)
        self.assertEqual(self.buttons(dialog), [False, True], "buffi hidden")

    def test_a_press_sends_the_command_and_waits_for_the_server(self):
        import nui_sys_test as sys_test
        world, dialog = self.world(False)
        mark = world.mark()
        with sys_test.quiet():
            dialog.hideBuffiButtonList[1].click()
        self.assertEqual(world.effects_since(mark), [("net.SendChatPacket", ("/hide_buffi 1",))])
        self.assertEqual(self.buttons(dialog), [True, False], "no local guess")
        world.state["hidden"] = True
        dialog.RefreshHideBuffi()
        self.assertEqual(self.buttons(dialog), [False, True])
        mark = world.mark()
        with sys_test.quiet():
            dialog.hideBuffiButtonList[0].click()
        self.assertEqual(world.effects_since(mark), [("net.SendChatPacket", ("/hide_buffi 0",))])

    def test_a_press_on_the_state_in_effect_sends_nothing(self):
        import nui_sys_test as sys_test
        world, dialog = self.world(True)
        mark = world.mark()
        with sys_test.quiet():
            dialog.hideBuffiButtonList[1].click()
        self.assertEqual(world.effects_since(mark), [])

    def test_the_row_sits_under_the_sash_row_and_grows_the_board(self):
        world, dialog = self.world(False)
        self.assertEqual(dialog.HIDE_BUFFI_ROW_Y, dialog.SHOW_SASH_ROW_Y + 25)
        self.assertEqual(dialog.HIDE_BUFFI_HEIGHT, dialog.SHOW_SASH_HEIGHT + 25)


class HideBuffiGlue(unittest.TestCase):
    """GC::BUFFI_HIDE: the client calls the game window's BINARY_OnBuffiHide,
    which tells the Interface, which refreshes the game options."""

    def test_the_game_window_tells_the_interface(self):
        import shop_glue_test as glue
        GameWindow = glue.compiled_class("game.py", "GameWindow", ["BINARY_OnBuffiHide"])
        log = glue.Log()
        window = GameWindow()
        window.interface = log.obj("interface")
        window.BINARY_OnBuffiHide(1)
        self.assertEqual([call[:2] for call in log.calls], [("interface.OnBuffiHide", (1,))])

    def test_the_interface_refreshes_the_game_options(self):
        import shop_glue_test as glue
        self.assertIn("OnBuffiHide", glue.class_methods("interfacemodule.py", "Interface"))
        Interface = glue.compiled_class("interfacemodule.py", "Interface", ["OnBuffiHide"])
        calls = []
        interface = Interface()
        interface.dlgSystem = types.SimpleNamespace(
            gameOptionDlg=types.SimpleNamespace(RefreshHideBuffi=lambda: calls.append("refresh")))
        interface.OnBuffiHide(1)
        self.assertEqual(calls, ["refresh"])
        for dialog in (None, object()):
            interface.dlgSystem = types.SimpleNamespace(gameOptionDlg=dialog)
            interface.OnBuffiHide(0)
        self.assertEqual(calls, ["refresh"])


# --- the strings --------------------------------------------------------------------------------------

class Locale(unittest.TestCase):
    KEYS = {"COSTUME_WINDOW_BUFFICOSTUME": "Buffi Costumes", "OPTION_SHOW_COMPANIONS_BUFFI": "Buffi"}

    def test_every_locale_has_the_keys(self):
        for locale in lf.locales():
            entries = lf.read_locale(locale, "locale_interface.txt")
            for key in self.KEYS:
                with self.subTest(locale=locale, key=key):
                    self.assertIn(key, entries)
                    self.assertTrue(entries[key][0].strip())
        english = lf.read_locale("en", "locale_interface.txt")
        for key, text in self.KEYS.items():
            self.assertEqual(english[key][0], text)


if __name__ == "__main__":
    unittest.main()
