"""Tests for the legacy client's gaya (wave 5, chunk Y1; NOVA-10):
python3 -B -m unittest gem_shop_test (from tools/).

The C++ half (GC::GAYA_MARKET into CPythonPlayer, the player.GetGem* getters,
the net.SendGemShop* senders, [SELECT_ITEM_EX max_grade;n]) is chunk C's;
the server's rules are SG's. Here the legacy code of assets/root runs over
nui_game_support's stand-ins (extra_inventory_test's world: the cut's
constants and K's EXTRA window), with K's player constants (GEM 163,
GAYA_MARKET_SLOT_COUNT 9, nova-client-src 9d49ac2b) and C's getters stood in:
- uigemshop.GemShopWindow and its uiscript gemshopwindow.py: a locked slot
  asks the unlock question with the server's cost (not OLD's literals); an
  open slot asks to buy; the local "not enough" checks stop the send; the
  refresh asks; the countdown is clamped at 00:00 (GB13); walking 500 units
  away, ESC and the title's X send CLOSE, the server's close sends nothing;
- uiselectitem.SelectItemWindow.Open(maxGrade, stayOpen): the stone picker
  for the cut, grades up to the server's maximum, open between cuts;
- the Interface's gaya glue and the game window's three callbacks;
- uicuberenewal.HasEnoughGem with the real balance, an exact one included
  (GB14);
- the inventory's gaya balance under the yang, in both uiscripts;
- every gaya key in all 17 locales."""
import ast
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import legacy_foundation_test as lf  # noqa: E402
import extra_inventory_test as xinv  # noqa: E402
import cube_renewal_test as cube  # noqa: E402

ROOT = support.ROOT
UISCRIPT = lf.UISCRIPT
LOCALES = lf.LOCALES

# K's values (nova-client-src 9d49ac2b: GameType.h:164-184 through
# PythonPlayerModule.cpp:2739-2753; the protocol's gaya_packets.h:48).
K_PLAYER = {"GEM": 163, "GAYA_MARKET_SLOT_COUNT": 9}
# gaya.txt's refresh and unlock items (spec 5.4; OLD uiGemShop.py:15-16).
REFRESH_ITEM, UNLOCK_ITEM = 39063, 39064
NAMES = {REFRESH_ITEM: "Gaya Market Refresh", UNLOCK_ITEM: "Gaya Market Key"}
GAYA_CAP = 999999                  # the highest balance (spec 4.2: refused at 1,000,000)

# OLD's keys (Ol:en/locale_game.txt:1772-1781, locale_interface.txt:561-562),
# GEMSHOP_TITLA renamed GEMSHOP_TITLE (spec 4.8), and the one-line question
# without OLD's "\n" escape (NEW's QuestionDialog shows one line).
GAYA_GAME_KEYS = {
    "GEM_SYSTEM_ADD_SLOT": "Item required: %s. Do you want use %d of them to unlock an additional slot?",
    "GEM_SYSTEM_BUY_ITEM": "Do you want to purchase this item?",
    "GEM_SYSTEM_NAME": "Gaya",
    "GEM_SYSTEM_NOT_ENOUGHT_REFRESHITEM": "[Gaya] You don't have enough Refresh Gaya Market items.",
    "GEM_SYSTEM_NOT_ENOUGH_HP_GEM": "[Gaya] You don't have enough Gaya.",
    "GEM_SYSTEM_NO_MORE_ADDSLOT": "[Gaya] No more slots can be unlocked.",
    "GEM_SYSTEM_OPEN_GEMSHOP": "[Gaya] Open the Gaya Market first.",
    "GEM_SYSTEM_PICK_GEM": "[Gaya] Amount of Gaya: %d",
    "GEM_SYSTEM_REFRESH_SHOP_ITEMS": "Do you want to refresh the shop?",
    "GEM_SYSTEM_NOT_ENOUGHT_ADDITEM": "[Gaya] Not Enough %s, %dx more is required",
}
GAYA_INTERFACE_KEYS = {"GEMSHOP_LEFTTIME": "Time remaining", "GEMSHOP_TITLE": "GAYA MARKET"}


def specifiers(text):
    import re
    return re.findall(r"%[-0-9.]*[sdif]", text.replace("%%", ""))


class Market(object):
    """What C's CPythonPlayer holds after a GC::GAYA_MARKET frame: slots 0-2
    open, 3-8 locked (status 1, OLD's), each with gaya.txt's unlock cost."""

    def __init__(self):
        self.slots = [{"vnum": 34185 + i, "count": 50 if i == 2 else 1, "price": 2 + i, "status": int(i >= 3),
                       "unlock": (0, 0, 0, 1, 2, 4, 8, 8, 8)[i]} for i in range(9)]
        self.refresh = 3725        # seconds until the server re-rolls
        self.gem = 100
        self.items = {REFRESH_ITEM: 1, UNLOCK_ITEM: 3}
        self.position = (1000.0, 2000.0, 0.0)


def install_market(world):
    game = world.game
    player, item = game.modules["player"], game.modules["item"]
    for name, value in K_PLAYER.items():
        setattr(player, name, value)
    market = world.market = Market()
    define = support.define
    define(player, "GetGemShopItemVnum", lambda s: market.slots[s]["vnum"])
    define(player, "GetGemShopItemCount", lambda s: market.slots[s]["count"])
    define(player, "GetGemShopItemPrice", lambda s: market.slots[s]["price"])
    define(player, "GetGemShopItemStatus", lambda s: market.slots[s]["status"])
    define(player, "GetGemShopUnlockCost", lambda s: market.slots[s]["unlock"])
    define(player, "GetGemShopRefreshTime", lambda: market.refresh)
    define(player, "GetGemShopRefreshItemVnum", lambda: REFRESH_ITEM)
    define(player, "GetGemShopUnlockItemVnum", lambda: UNLOCK_ITEM)
    define(player, "GetGem", lambda: market.gem)
    define(player, "GetItemCountByVnum", lambda vnum: market.items.get(vnum, 0))
    define(player, "GetMainCharacterPosition", lambda: market.position)
    define(item, "GetItemName", lambda *vnum: NAMES.get(vnum[0] if vnum else item.selected[0], "item"))
    return market


def market_world():
    world = xinv.World()
    install_market(world)
    return world


def make_market(world):
    module = world.load("uiGemShop", "uigemshop.py")
    with world, lf.quiet():
        window = module.GemShopWindow()
        window.disabled = set()
        window.itemSlot.DisableSlot = window.disabled.add
        window.itemSlot.EnableSlot = window.disabled.discard
        window.SetItemToolTip(world.game.modules["uiToolTip"].ItemToolTip())
        window.Open()
    return window


class GemShopWindow(unittest.TestCase):
    def setUp(self):
        self.world = market_world()
        self.window = make_market(self.world)
        self.locale = self.world.game.modules["localeInfo"]

    def sent(self):
        return [call for call in self.world.game.log if call[0].startswith("net.SendGemShop")]

    def infos(self):
        return [args[1] for name, args in self.world.game.calls("chat.AppendChat")]

    def press(self, slot):
        with self.world, lf.quiet():
            self.window.itemSlot.fire("select_item", slot)

    def last_dialog(self):
        return self.world.game.dialogs[-1] if self.world.game.dialogs else None

    def test_the_uiscript_has_every_child_the_window_binds(self):
        for name in ["TitleBar", "SellItemSlot", "BuyRefreshTime", "RefreshButton"] + \
                ["slot_%d_price" % i for i in range(1, 10)]:
            self.assertIn(name, self.window.ElementDictionary, name)
        self.assertEqual(self.world.game.modules["ui"].PythonScriptLoader.loaded[-1], "UIScript/gemshopwindow.py")
        with self.world:
            window = lf.read_uiscript(os.path.join(UISCRIPT, "gemshopwindow.py"))["window"]
        slots = lf.child(window, "SellItemSlot")["slot"]
        self.assertEqual(sorted(slot["index"] for slot in slots), list(range(9)))
        self.assertEqual(lf.child(window, "TitleName")["text"], self.locale_interface().GEMSHOP_TITLE)
        board = lf.child(window, "board")
        for child in lf.children(board):
            if "width" in child and child.get("type") != "titlebar":
                self.assertLessEqual(child["x"] + child["width"], board["width"], child["name"])

    def locale_interface(self):
        return self.world.game.modules["uiScriptLocale"]

    def test_the_slots_show_the_server_s_items_with_the_locked_ones_disabled(self):
        shown = self.window.itemSlot.shown()
        self.assertEqual(shown[0], (34185, "", False), "a single item shows no count")
        self.assertEqual(shown[2][:2], (34187, "50"))
        self.assertEqual(sorted(shown), list(range(9)))
        self.assertEqual(self.window.disabled, set(range(3, 9)))
        self.assertEqual(self.window.ElementDictionary["slot_5_price"].GetText(), "6")

    def test_a_locked_slot_asks_the_unlock_question_with_the_server_s_cost(self):
        self.world.market.slots[4]["unlock"] = 2
        self.press(4)
        dialog = self.last_dialog()
        self.assertEqual(dialog.texts, [self.locale.GEM_SYSTEM_ADD_SLOT % (NAMES[UNLOCK_ITEM], 2)])
        self.assertTrue(dialog.is_open)
        self.assertEqual(self.sent(), [])
        with self.world:
            dialog.accept()
        self.assertFalse(dialog.is_open)
        self.assertEqual(self.sent(), [("net.SendGemShopAdd", (4,))])

    def test_too_few_unlock_items_stop_the_send(self):
        self.world.market.items[UNLOCK_ITEM] = 1
        self.press(5)
        self.assertEqual(self.infos(), [self.locale.GEM_SYSTEM_NOT_ENOUGHT_ADDITEM % (NAMES[UNLOCK_ITEM], 3)])
        self.assertEqual(self.world.game.dialogs, [])
        self.assertEqual(self.sent(), [])

    def test_an_open_slot_asks_to_buy(self):
        self.press(1)
        dialog = self.last_dialog()
        self.assertEqual(dialog.texts, [self.locale.GEM_SYSTEM_BUY_ITEM])
        with self.world:
            dialog.accept()
        self.assertEqual(self.sent(), [("net.SendGemShopBuy", (1,))])

    def test_too_little_gaya_stops_the_send_and_an_exact_balance_buys(self):
        self.world.market.gem = 3
        self.press(2)
        self.assertEqual(self.infos(), [self.locale.GEM_SYSTEM_NOT_ENOUGH_HP_GEM])
        self.assertEqual(self.world.game.dialogs, [])
        self.world.market.gem = 4
        self.press(2)
        self.assertEqual(self.last_dialog().texts, [self.locale.GEM_SYSTEM_BUY_ITEM])

    def test_no_closes_the_question_and_sends_nothing(self):
        self.press(0)
        dialog = self.last_dialog()
        with self.world:
            dialog.cancel()
        self.assertFalse(dialog.is_open)
        self.assertEqual(self.sent(), [])

    def test_a_second_question_closes_the_first(self):
        self.press(0)
        first = self.last_dialog()
        self.press(1)
        self.assertFalse(first.is_open)
        with self.world:
            self.last_dialog().accept()
        self.assertEqual(self.sent(), [("net.SendGemShopBuy", (1,))])

    def test_the_refresh_asks_and_needs_the_item(self):
        self.world.market.items[REFRESH_ITEM] = 0
        with self.world, lf.quiet():
            self.window.refreshButton.Click()
        self.assertEqual(self.infos(), [self.locale.GEM_SYSTEM_NOT_ENOUGHT_REFRESHITEM])
        self.assertEqual(self.world.game.dialogs, [])
        self.world.market.items[REFRESH_ITEM] = 1
        with self.world, lf.quiet():
            self.window.SendRequestRefresh()
        dialog = self.last_dialog()
        self.assertEqual(dialog.texts, [self.locale.GEM_SYSTEM_REFRESH_SHOP_ITEMS])
        with self.world:
            dialog.accept()
        self.assertEqual(self.sent(), [("net.SendGemShopRefresh", ())])

    def test_the_countdown_is_hh_mm_and_stops_at_zero(self):
        text = self.window.ElementDictionary["BuyRefreshTime"]
        self.assertEqual(text.GetText(), "01:02")
        self.world.game.global_time += 3000 * 1000
        with self.world:
            self.window.OnUpdate()
        self.assertEqual(text.GetText(), "00:12")
        self.world.game.global_time += 3600 * 1000
        with self.world:
            self.window.OnUpdate()
        self.assertEqual(text.GetText(), "00:00", "GB13")
        self.assertEqual(self.window.TransformTime(-90), "00:00")

    def test_a_refresh_restarts_the_countdown_and_redraws_the_slots(self):
        self.world.market.refresh = 5 * 3600
        self.world.market.slots[3]["status"] = 0
        self.world.market.slots[0]["vnum"] = 71112
        with self.world, lf.quiet():
            self.window.RefreshGemShop()
        self.assertEqual(self.window.ElementDictionary["BuyRefreshTime"].GetText(), "05:00")
        self.assertEqual(self.window.disabled, set(range(4, 9)))
        self.assertEqual(self.window.itemSlot.shown()[0][0], 71112)

    def test_walking_500_units_away_closes_and_sends_close(self):
        x, y, z = self.world.market.position
        self.world.market.position = (x + 500, y - 500, z)
        with self.world:
            self.window.OnUpdate()
        self.assertTrue(self.window.IsShow())
        self.assertEqual(self.sent(), [])
        self.world.market.position = (x + 501, y, z)
        with self.world:
            self.window.OnUpdate()
        self.assertFalse(self.window.IsShow())
        self.assertEqual(self.sent(), [("net.SendGemShopClose", ())])

    def test_escape_and_the_title_close_send_close(self):
        with self.world:
            self.assertTrue(self.window.OnPressEscapeKey())
        self.assertFalse(self.window.IsShow())
        with self.world, lf.quiet():
            self.window.Open()
            self.window.titleBar.close()
        self.assertFalse(self.window.IsShow())
        self.assertEqual(self.sent(), [("net.SendGemShopClose", ()), ("net.SendGemShopClose", ())])

    def test_the_server_s_close_sends_nothing(self):
        self.press(1)
        with self.world:
            self.window.Close()
        self.assertFalse(self.window.IsShow())
        self.assertFalse(self.last_dialog().is_open, "the question goes with it")
        self.assertEqual(self.sent(), [])

    def test_the_tooltip_shows_the_slot_s_item(self):
        with self.world:
            self.window.itemSlot.fire("over_in", 6)
        self.assertEqual(self.window.tooltipItem.shown[-1], ("SetItemToolTip", 34191))
        with self.world:
            self.window.itemSlot.fire("over_out")
        self.assertEqual(self.window.tooltipItem.calls[-1], ("HideToolTip",))


# --- the stone picker (SELECT_ITEM_EX) ------------------------------------------------------------

class StonePicker(unittest.TestCase):
    def world(self, grades):
        world = xinv.World()
        for cell, grade in grades.items():
            world.game.give(cell, xinv.STONE)
            world.game.item_grades[cell] = grade
        support.define(world.game.modules["player"], "GetItemGrade",
                       lambda *at: world.game.item_grades.get(at[0] if len(at) == 1 else tuple(at), 0))
        module = world.load("uiselectitem", "uiselectitem.py")
        with world, lf.quiet():
            window = module.SelectItemWindow()
            window.SetItemToolTip(world.game.modules["uiToolTip"].ItemToolTip())
        return world, window

    def test_the_ex_picker_lists_grades_up_to_the_server_s_maximum_and_stays_open(self):
        world, window = self.world({0: 0, 1: 3, 2: 4})
        with world, lf.quiet():
            window.Open(maxGrade=3, stayOpen=True)
        self.assertEqual(window.inventorySlotPosDict, {0: 0, 1: 1})
        with world, lf.quiet():
            window.SelectItemSlot(1)
        self.assertTrue(window.IsShow(), "open between cuts")
        self.assertEqual(world.sent("net.SendSelectItemPacket"), [("net.SendSelectItemPacket", (xinv.INVENTORY, 1))])

    def test_a_plain_open_is_the_alchemist_s_picker_again(self):
        world, window = self.world({0: 0, 1: 3})
        with world, lf.quiet():
            window.Open(maxGrade=3, stayOpen=True)
            window.Open()
        self.assertEqual(window.inventorySlotPosDict, {0: 0}, "grade 2 at most")
        with world, lf.quiet():
            window.SelectItemSlot(0)
        self.assertFalse(window.IsShow())

    def test_closing_the_ex_picker_answers_closed(self):
        world, window = self.world({0: 1})
        with world, lf.quiet():
            window.Open(maxGrade=3, stayOpen=True)
            window.Close()
        self.assertFalse(window.IsShow())
        self.assertEqual(world.sent("net.SendSelectItemPacket"), [("net.SendSelectItemPacket", (0,))], "GB10: 0 = closed")


# --- the Interface and the game window -------------------------------------------------------------

def compiled_class(file_name, class_name, names):
    return xinv.compiled(file_name, class_name, names)


class Calls(object):
    def __init__(self, log, name):
        self._log = log
        self._name = name

    def __getattr__(self, attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        return lambda *args, **kwargs: self._log.append(("%s.%s" % (self._name, attr), args, kwargs))


def class_methods(file_name, class_name):
    tree = ast.parse(lf.read(os.path.join(ROOT, file_name)))
    return {node.name: ast.unparse(node) for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == class_name
            for node in cls.body if isinstance(node, ast.FunctionDef)}


class Glue(unittest.TestCase):
    def test_the_interface_opens_refreshes_and_closes_the_market(self):
        log = []
        Interface = compiled_class("interfacemodule.py", "Interface", ["OpenGemShop", "RefreshGemShop", "CloseGemShop"])
        interface = Interface()
        interface.wndGemShop = Calls(log, "wndGemShop")
        interface.OpenGemShop()
        interface.RefreshGemShop()
        interface.CloseGemShop()
        self.assertEqual([call[0] for call in log], ["wndGemShop.Open", "wndGemShop.RefreshGemShop", "wndGemShop.Close"])

    def test_select_item_ex_opens_the_picker_with_the_grade_and_open_between_picks(self):
        log = []
        Interface = compiled_class("interfacemodule.py", "Interface",
                                   ["BINARY_OpenSelectItemWindowEx", "BINARY_OpenSelectItemWindow"])
        interface = Interface()
        interface.wndItemSelect = Calls(log, "wndItemSelect")
        interface.BINARY_OpenSelectItemWindowEx(3)
        interface.BINARY_OpenSelectItemWindow()
        self.assertEqual(log, [("wndItemSelect.Open", (), {"maxGrade": 3, "stayOpen": True}),
                               ("wndItemSelect.Open", (), {})])

    def test_the_game_window_forwards_the_three_callbacks(self):
        log = []
        GameWindow = compiled_class("game.py", "GameWindow", ["OpenGemShop", "RefreshGemShop", "CloseGemShop"])
        window = GameWindow()
        window.interface = Calls(log, "interface")
        window.OpenGemShop()
        window.RefreshGemShop()
        window.CloseGemShop()
        self.assertEqual([call[0] for call in log], ["interface.OpenGemShop", "interface.RefreshGemShop", "interface.CloseGemShop"])
        window.interface = None
        window.OpenGemShop()
        window.RefreshGemShop()
        window.CloseGemShop()

    def test_the_market_window_is_made_through_the_factory_and_bound(self):
        """Interface.__MakeWindows makes it through nui_windows.make (spec 4.8:
        the UI session's NovaUI market, nui_gem_shop.GemShopWindow, while the
        gem-shop flag is on; legacy's class otherwise); MakeInterface gives it
        the item tooltip and Close destroys it."""
        methods = class_methods("interfacemodule.py", "Interface")
        self.assertIn("self.wndGemShop = nui_windows.make('gem-shop', uiGemShop.GemShopWindow, 'nui_gem_shop.GemShopWindow')",
                      methods["__MakeWindows"])
        self.assertIn("self.wndGemShop.SetItemToolTip(self.tooltipItem)", methods["MakeInterface"])
        self.assertIn("self.wndGemShop.Destroy()", methods["Close"])
        self.assertIn("self.wndGemShop = None", methods["__init__"])
        self.assertIn("import uiGemShop", lf.read(os.path.join(ROOT, "interfacemodule.py")).split("\n"))


# --- the cube's gaya cost ------------------------------------------------------------------------------

class CubeGaya(unittest.TestCase):
    def test_has_enough_gem_reads_the_balance_and_an_exact_one_is_enough(self):
        cube.IsolateModules(self)
        module = cube.LoadWindowModule()
        balance = [5]
        sys.modules["player"].GetGem = lambda: balance[0]
        window = object.__new__(module.CubeRenewalWindow)
        self.assertTrue(window.HasEnoughGem(0))
        self.assertTrue(window.HasEnoughGem(5), "GB14: an exact balance pays")
        self.assertFalse(window.HasEnoughGem(6))
        balance[0] = 0
        self.assertFalse(window.HasEnoughGem(1))
        balance[0] = GAYA_CAP
        self.assertTrue(window.HasEnoughGem(GAYA_CAP))


# --- the inventory's gaya --------------------------------------------------------------------------------

class InventoryGaya(unittest.TestCase):
    def test_both_uiscripts_show_the_gaya_under_the_yang(self):
        for path in (os.path.join(UISCRIPT, "inventorywindow.py"), os.path.join(LOCALES, "ae", "ui", "inventorywindow.py")):
            with self.subTest(path=path):
                world = xinv.World()
                with world:
                    window = lf.read_uiscript(path)["window"]
                board = lf.child(window, "board")
                bag = lf.child(window, "ItemSlot")
                button = lf.child(window, "ExtraInventoryButton")
                money = lf.child(window, "Money_Slot")
                gem = lf.child(window, "Gem_Slot")
                self.assertEqual(window["height"], board["height"])
                for slot in (money, gem):
                    self.assertEqual(slot["vertical_align"], "bottom")
                    self.assertEqual(slot["horizontal_align"], "center")
                    self.assertEqual(slot["x"], money["x"])
                    self.assertEqual(slot["default_image"], "d:/ymir work/ui/public/parameter_slot_05.sub")
                # Bottom-aligned: a top is height - y, and a slot is 18 px tall.
                self.assertGreaterEqual(money["y"] - gem["y"], 18, "the gaya row sits under the yang's")
                self.assertGreaterEqual(gem["y"], 18 + 4, "inside the board's bottom edge")
                self.assertLessEqual(button["y"] + 21, board["height"] - money["y"], "the button stays above the yang")
                self.assertGreaterEqual(button["y"], bag["y"] + 32 * 9)
                self.assertEqual([c["name"] for c in lf.children(gem)], ["Gem_Icon", "Gem"])
                self.assertEqual(gem["tooltip_text"], world.game.modules["localeInfo"].GEM_SYSTEM_NAME)
                text = lf.child(window, "Gem")
                self.assertEqual((text["horizontal_align"], text["text_horizontal_align"]), ("right", "right"))

    def world(self, balance):
        world = xinv.World()
        for name, value in K_PLAYER.items():
            setattr(world.game.modules["player"], name, value)
        support.define(world.game.modules["player"], "GetGem", lambda: balance[0])
        return world

    def test_the_status_refresh_shows_the_balance(self):
        balance = [1234]
        world = self.world(balance)
        window = lf.make_inventory(world)
        self.assertEqual(window.wndGem.GetText(), "1.234")
        balance[0] = GAYA_CAP
        with world, lf.quiet():
            window.RefreshStatus()
        self.assertEqual(window.wndGem.GetText(), "999.999")
        balance[0] = 0
        with world, lf.quiet():
            window.RefreshStatus()
        self.assertEqual(window.wndGem.GetText(), "0")

    def test_a_loader_without_the_gaya_text_still_refreshes(self):
        """The NovaUI inventory binds its own widgets (Wave 3b): the legacy
        attribute stays None there, and the refresh leaves it alone."""
        balance = [7]
        world = self.world(balance)
        module = world.load("uiInventory", "uiinventory.py")
        self.assertIsNone(module.InventoryWindow.wndGem)
        window = lf.make_inventory(world)
        window.wndGem = None
        with world, lf.quiet():
            window.RefreshStatus()


# --- the locales ---------------------------------------------------------------------------------------------

class Locales(unittest.TestCase):
    def test_every_locale_has_every_gaya_key(self):
        for locale in lf.locales():
            with self.subTest(locale=locale):
                game = lf.read_locale(locale)
                interface = lf.read_locale(locale, "locale_interface.txt")
                for key, english in GAYA_GAME_KEYS.items():
                    self.assertIn(key, game)
                    self.assertEqual(game[key][1], "", "%s: no type column" % key)
                    self.assertEqual(specifiers(game[key][0]), specifiers(english), key)
                    self.assertNotIn("\\n", game[key][0], key)
                for key in GAYA_INTERFACE_KEYS:
                    self.assertIn(key, interface)
                    self.assertTrue(interface[key][0], key)
                self.assertNotIn("GEMSHOP_TITLA", interface, "renamed (spec 4.8)")
        english = lf.read_locale("en")
        for key, text in GAYA_GAME_KEYS.items():
            self.assertEqual(english[key][0], text, key)
        english = lf.read_locale("en", "locale_interface.txt")
        for key, text in GAYA_INTERFACE_KEYS.items():
            self.assertEqual(english[key][0], text, key)

    def test_old_s_translation_is_kept_where_its_specifiers_fit(self):
        """OLD's text of the locale (Ol:de: the last line of a key, as OLD's
        localeInfo reads it), English where OLD's drops a specifier."""
        german = lf.read_locale("de")
        self.assertEqual(german["GEM_SYSTEM_BUY_ITEM"][0], "Möchtest du dieses Item kaufen?")
        self.assertEqual(german["GEM_SYSTEM_NOT_ENOUGHT_ADDITEM"][0], GAYA_GAME_KEYS["GEM_SYSTEM_NOT_ENOUGHT_ADDITEM"])
        self.assertEqual(lf.read_locale("de", "locale_interface.txt")["GEMSHOP_TITLE"][0], "GAYAHANDEL")


class Constants(unittest.TestCase):
    def test_the_stand_in_values_are_ks(self):
        """Skips until the committed fixture carries K's player constants
        (y1.md step 2: main's fixture is kept, K's file is in the report)."""
        player = support.module_constants()["player"]
        if "GEM" not in player:
            self.skipTest("tools/fixtures/module_constants.json is main's (nova-client-src eccdf1c)")
        for name, value in K_PLAYER.items():
            self.assertEqual(player[name], value, name)


if __name__ == "__main__":
    unittest.main()
