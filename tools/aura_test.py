"""Tests for the legacy client's aura costume (wave 6, chunk Y; NOVA-23, OLD's
ENABLE_AURA_SYSTEM): python3 -B -m unittest aura_test (from tools/).

The C++ half (GC::AURA to game.BINARY_AuraPacket, the aura part and its
effects, player.GetAuraWingFlags, the item module's aura names) is chunk C's;
the aura's rules and the bonus are chunk SU's, off by the server's
AURA_SYSTEM_ENABLE (the default), which refuses every /aura command, so the
window below never opens then. Here the legacy Python runs over
nui_game_support's stand-ins with C's names (wave6_support):
- uiaura.AuraWindow and its uiscript (OLD root/uiAura.py): made at the
  server's first GC::AURA and filled by it (the aura and the material, the
  level and the experience gauge), closed by its CLOSE; a drop on a slot,
  a press on an item, accept, cancel and the walk away send OLD's
  "/aura add|remove|leveling|close"; the items' cells take no mouse event
  while it shows;
- the Interface's binding and both inventories' right-click of an aura
  material into the open window (OLD uiInventory.py:2527-2531,
  uiExtraInventory.py:926-930);
- the costume window's aura cell (wear 39) and its flag panel (OLD
  uiInventory.py:254-329: "/aura_wing <flags>");
- uitooltip: the tier above the description and the level line (OLD
  uiToolTip.py:1116-1127, 1403-1406, 1563-1578);
- every key in all 17 locales."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import legacy_foundation_test as lf  # noqa: E402
import wave6_support as w6  # noqa: E402
import sash_test  # noqa: E402

support = w6.support
AURA_CELL, STONE_CELL, OTHER_CELL = 5, 6, 8
AURA_WEAR_CELL = w6.C_ITEM["COSTUME_SLOT_AURA"]
INVENTORY, EXTRA = 1, 6
MAIN, CLOSE = w6.C_ITEM["AURA_MODE_MAIN"], w6.C_ITEM["AURA_MODE_CLOSE"]
EMPTY = 0xFFFF

GAME_KEYS = {"AURA_TIER": "Tier %d", "AURA_TOOLTIP_LEVEL_MAX": "Level %d (MAX)",
             "AURA_TOOLTIP_LEVEL_EXP": "Level %d (%s/%s EXP)", "AURA_WINDOW_LEVEL": "Level: %d", "AURA_WINDOW_MAX": "MAX",
             "AURA_WINDOW_EXP": "%s / %s EXP", "AURA_WING_SHOW_WING": "Wings", "AURA_WING_SHOW_AURA": "Aura",
             "AURA_WING_SHOW_EFFECT": "Aura Wing Effect"}
INTERFACE_KEYS = {"AURA_MAIN": "Main", "AURA_SUB": "Material", "AURA_LEVELUP_TITLE": "Aura Leveling",
                  "AURA_LEVELUP_BUTTON": "Level Up"}


class Interface(object):
    """The Interface's half (BindAuraWindow, compiled from interfacemodule.py)."""


def aura_world():
    world = w6.World()
    game = world.game
    game.position = [1000.0, 2000.0, 0.0]
    support.define(game.modules["player"], "GetMainCharacterPosition", lambda: tuple(game.position))
    item = game.modules["item"]
    game.kinds = {w6.AURA_STONE: (14, 12), w6.AURA: (28, 10), w6.SWORD: (1, 0)}
    support.define(item, "GetItemType", lambda: game.kinds.get(item.selected[0], (0, 0))[0])
    support.define(item, "GetItemSubType", lambda: game.kinds.get(item.selected[0], (0, 0))[1])
    game.give(AURA_CELL, w6.AURA)
    game.give(STONE_CELL, w6.AURA_STONE, 4)
    game.give((INVENTORY, STONE_CELL), w6.AURA_STONE, 4)  # player.GetItemCount(window, cell)
    game.give(OTHER_CELL, w6.SWORD)
    world.load("uiAura", "uiaura.py")
    return world


def game_window(world, interface=None):
    # game.py makes the window through nui_windows.make() (Wave 6 NovaUI).
    Game = sash_test.compiled("game.py", "GameWindow", ["BINARY_AuraPacket"],
                              {"item": world.game.modules["item"], "nui_windows": world.game.loaded["nui_windows"]})
    game = Game()
    game.auraWindow = None
    game.interface = interface
    return game


def bound_interface(world, inventory=None, extra=None):
    Bound = sash_test.compiled("interfacemodule.py", "Interface", ["BindAuraWindow", "__BindItemHolder"])
    interface = Bound()
    interface.tooltipItem = support.ToolTip("item")
    interface.wndInventory = inventory or sash_test.Inventory()
    interface.wndExtraInventory = extra
    return interface


class Holder(sash_test.Inventory):
    """An inventory as BindAuraWindow sees it."""

    def __init__(self):
        sash_test.Inventory.__init__(self)
        self.bound = []
        self.wndAura = None

    def BindWindow(self, wnd):
        self.bound.append(wnd)

    def SetAuraWindow(self, wnd):
        self.wndAura = wnd


class AuraWindow(unittest.TestCase):
    def setUp(self):
        self.world = aura_world()
        self.inventory, self.extra = Holder(), Holder()
        self.interface = bound_interface(self.world, self.inventory, self.extra)
        self.game = game_window(self.world, self.interface)
        self.packet(MAIN, 3, AURA_CELL, EMPTY, 250, 1000)
        self.window = self.game.auraWindow
        del self.world.game.log[:]

    def packet(self, *args):
        with self.world.game, lf.quiet():
            self.game.BINARY_AuraPacket(*args)

    def run_with(self, call, *args):
        with self.world.game, lf.quiet():
            return call(*args)

    def text(self, name):
        return self.window.GetChild(name).text

    def test_the_uiscript_has_every_child_the_window_binds(self):
        for name in ("TitleBar", "TitleName", "AcceptButton", "CancelButton", "AuraSlot", "LevelText", "ExpGaugeBG",
                     "ExpGaugeFill", "ExpPercentText", "ExpText"):
            self.assertIn(name, self.window.ElementDictionary)
        self.assertEqual(sorted(self.window.GetChild("AuraSlot").slots), [0, 1])

    def test_the_first_packet_makes_binds_and_opens_the_window(self):
        self.assertTrue(self.window.IsOpened())
        self.assertIs(self.inventory.wndAura, self.window)
        self.assertIs(self.extra.wndAura, self.window)
        self.assertEqual(self.inventory.bound, [self.window])
        self.assertIs(self.window.tooltipItem, self.interface.tooltipItem)
        self.packet(MAIN, 3, AURA_CELL, STONE_CELL, 250, 1000)
        self.assertIs(self.game.auraWindow, self.window, "made once")

    def test_the_window_shows_the_aura_its_level_and_its_experience(self):
        locale = self.world.game.modules["localeInfo"]
        slots = self.window.GetChild("AuraSlot").slots
        self.assertEqual((slots[0]["vnum"], slots[1]["vnum"]), (w6.AURA, 0))
        self.assertEqual(self.text("LevelText"), locale.AURA_WINDOW_LEVEL % 3)
        self.assertEqual(self.text("ExpPercentText"), "25%")
        self.assertEqual(self.text("ExpText"), locale.AURA_WINDOW_EXP % ("250", "1.000"))
        self.assertEqual(self.window.GetChild("ExpGaugeFill").size, (47, 12), "a quarter of 188")
        self.assertEqual(self.inventory.locked, {AURA_CELL})

    def test_the_material_shows_its_count(self):
        self.packet(MAIN, 3, AURA_CELL, STONE_CELL, 250, 1000)
        slot = self.window.GetChild("AuraSlot").slots[1]
        self.assertEqual((slot["vnum"], slot["count"]), (w6.AURA_STONE, 4))
        self.assertEqual(self.inventory.locked, {AURA_CELL, STONE_CELL})

    def test_the_last_level_says_max(self):
        locale = self.world.game.modules["localeInfo"]
        self.packet(MAIN, 250, AURA_CELL, EMPTY, 0, 0)
        self.assertEqual(self.text("ExpPercentText"), locale.AURA_WINDOW_MAX)
        self.assertEqual(self.text("ExpText"), "")
        self.assertEqual(self.window.GetChild("ExpGaugeFill").size, (188, 12))

    def test_without_an_aura_the_level_is_blank(self):
        self.packet(MAIN, 1, EMPTY, EMPTY, 0, 0)
        self.assertEqual(self.text("LevelText"), "")
        self.assertFalse(self.window.GetChild("ExpGaugeBG").shown)
        self.assertEqual(self.inventory.locked, set())

    def test_the_close_packet_closes_and_releases(self):
        self.packet(CLOSE, 0, 0, 0, 0, 0)
        self.assertFalse(self.window.IsOpened())
        self.assertEqual(self.inventory.locked, set())
        self.packet(5, 0, AURA_CELL, 0, 0, 0)
        self.assertFalse(self.window.IsOpened(), "an unknown mode is ignored")

    def test_a_drop_from_either_inventory_asks_to_add(self):
        player = self.world.game.modules["player"]
        self.world.attach(player.SLOT_TYPE_INVENTORY, STONE_CELL, w6.AURA_STONE)
        self.run_with(self.window.GetChild("AuraSlot").fire, "select_empty", 1)
        self.world.attach(player.SLOT_TYPE_EXTRA_INVENTORY, 230, w6.AURA_STONE)
        self.run_with(self.window.GetChild("AuraSlot").fire, "select_empty", 1)
        self.world.attach(8, 3, w6.AURA_STONE)
        self.run_with(self.window.GetChild("AuraSlot").fire, "select_empty", 1)
        self.assertEqual(self.world.chat_commands(), ["/aura add 1 %d %d" % (INVENTORY, STONE_CELL),
                                                      "/aura add 1 %d 230" % EXTRA])

    def test_the_buttons_and_a_press_on_an_item(self):
        self.run_with(self.window.GetChild("AuraSlot").fire, "use", 0)
        self.run_with(self.window.OnAccept)
        self.run_with(self.window.OnPressEscapeKey)
        self.assertEqual(self.world.chat_commands(), ["/aura remove 0", "/aura leveling", "/aura close"])
        self.assertFalse(self.window.IsOpened())

    def test_walking_away_closes_once(self):
        self.world.game.position[1] -= 1000
        self.run_with(self.window.OnUpdate)
        self.run_with(self.window.OnUpdate)
        self.assertEqual(self.world.chat_commands(), ["/aura close"])

    def test_a_hover_shows_the_items_tooltip(self):
        self.run_with(self.window.OnOverInItem, 0)
        self.run_with(self.window.OnOverInItem, 1)
        calls = [call for call in self.window.tooltipItem.calls if call[0] == "SetInventoryItem"]
        self.assertEqual(calls, [("SetInventoryItem", AURA_CELL, INVENTORY)], "no material, no tooltip")


class RightClick(unittest.TestCase):
    """A right-click on an aura material while the window shows."""

    class Window(object):
        def __init__(self, opened):
            self.opened = opened

        def IsOpened(self):
            return self.opened

    def test_the_inventory_adds_a_material_and_uses_anything_else(self):
        world = aura_world()
        inventory = w6.make_inventory(world)
        inventory.SetAuraWindow(self.Window(True))
        del world.game.log[:]
        with world.game, lf.quiet():
            inventory.UseItemSlot(STONE_CELL)
            inventory.UseItemSlot(OTHER_CELL)
        self.assertEqual(world.chat_commands(), ["/aura add 1 %d %d" % (INVENTORY, STONE_CELL)])
        self.assertEqual(len(world.sent("net.SendItemUse")), 1, "the sword is used")
        inventory.SetAuraWindow(self.Window(False))
        with world.game, lf.quiet():
            inventory.UseItemSlot(STONE_CELL)
        self.assertEqual(len(world.chat_commands()), 1, "a closed window takes nothing")

    def test_the_special_inventory_adds_a_material(self):
        world = aura_world()
        import extra_inventory_test as xinv
        xinv.install_k(world.game)
        world.game.give((EXTRA, 230), w6.AURA_STONE, 4)
        window = xinv.make_extra(world)
        window.SetAuraWindow(self.Window(True))
        del world.game.log[:]
        with world.game, lf.quiet():
            window._ExtraInventoryWindow__UseItem(230)
        self.assertEqual(world.chat_commands(), ["/aura add 1 %d 230" % EXTRA])


class CostumeWindow(unittest.TestCase):
    def setUp(self):
        self.world = aura_world()
        self.world.game.give(AURA_WEAR_CELL, w6.AURA)
        self.inventory, self.window = w6.costume_window(self.world)

    def press_flags(self):
        with self.world.game, lf.quiet():
            self.window.GetChild("Activate3_ON_OFF").click()

    def test_the_window_shows_the_worn_aura(self):
        self.assertEqual(self.window.wndEquip.slots[AURA_WEAR_CELL]["vnum"], w6.AURA)
        self.assertEqual(AURA_WEAR_CELL, w6.EQUIPMENT_START + 39)

    def test_the_flag_panel_shows_the_flags_and_a_click_sends_them(self):
        shown = self.world.game.shown_costumes
        shown["GetAuraWingFlags"] = w6.C_PLAYER["AURA_WING_FLAG_WING"] | w6.C_PLAYER["AURA_WING_FLAG_EFFECT"]
        self.press_flags()
        checks = self.window.auraWingChecks
        self.assertEqual([check.checked for _, check in checks], [True, False, True])
        locale = self.world.game.modules["localeInfo"]
        self.assertEqual([check.text for _, check in checks], [locale.AURA_WING_SHOW_WING, locale.AURA_WING_SHOW_AURA,
                                                               locale.AURA_WING_SHOW_EFFECT])
        with self.world.game, lf.quiet():
            checks[1][1].OnMouseLeftButtonUp()
            checks[0][1].OnMouseLeftButtonUp()
        self.assertEqual(self.world.chat_commands(), ["/aura_wing 7", "/aura_wing 4"])
        self.assertTrue(self.window.auraWingPanel.IsShow())
        self.press_flags()
        self.assertFalse(self.window.auraWingPanel.IsShow(), "a second press hides it")

    def test_only_the_flags_the_client_has_get_a_box(self):
        """The protocol's flags are the wings and the aura (costume_packets.h);
        a client without OLD's effect flag shows two boxes."""
        self.world.game.modules["player"].lack("AURA_WING_FLAG_EFFECT")
        self.press_flags()
        self.assertEqual([flag for flag, _ in self.window.auraWingChecks],
                         [w6.C_PLAYER["AURA_WING_FLAG_WING"], w6.C_PLAYER["AURA_WING_FLAG_AURA"]])

    def test_the_close_hides_the_panel(self):
        self.press_flags()
        with self.world.game, lf.quiet():
            self.window.Close()
        self.assertFalse(self.window.auraWingPanel.IsShow())
        self.assertFalse(self.window.GetChild("Activate3_ON_OFF").down)


AURA_ROW = dict(lf.ITEM_BASE, name="Ordinary Aura Outfit", type=28, subtype=10, icon="icon/item/149001.tga")


class ToolTip(unittest.TestCase):
    def texts(self, vnum, sockets, attrs=()):
        corpus_tool, world = w6.tooltip_world({w6.AURA: AURA_ROW, w6.AURA_LAST: dict(AURA_ROW, name="Radiant Aura Outfit")})
        texts, error = w6.tooltip_texts(corpus_tool, world, {"context": "AddItemData", "vnum": vnum, "sockets": sockets,
                                                              "attrs": list(attrs)})
        self.assertIsNone(error)
        return texts, world.game.modules["localeInfo"]

    def test_the_tier_and_the_level_with_its_experience(self):
        texts, locale = self.texts(w6.AURA, [3, 1250, 0, 0], attrs=[[1, 250]])
        self.assertEqual(texts.index(locale.AURA_TIER % 1), 1, "under the name, above the description")
        self.assertIn(locale.AURA_TOOLTIP_LEVEL_EXP % (3, "1.250", "1.000"), texts)
        self.assertIn(locale.TOOLTIP_MAX_HP(250), texts, "the aura's bonus")

    def test_the_last_tier_says_max(self):
        texts, locale = self.texts(w6.AURA_LAST, [250, 0, 0, 0])
        self.assertIn(locale.AURA_TIER % 6, texts)
        self.assertIn(locale.AURA_TOOLTIP_LEVEL_MAX % 250, texts)


class Locales(unittest.TestCase):
    def test_every_locale_has_the_aura_keys(self):
        w6.check_keys(self, GAME_KEYS)
        w6.check_keys(self, INTERFACE_KEYS, "locale_interface.txt")


if __name__ == "__main__":
    unittest.main()
