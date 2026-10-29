"""Tests for the legacy client's special inventory (wave 4b, chunk C2;
NOVA-16): python3 -B -m unittest extra_inventory_test (from tools/).

The C++ half (the EXTRA window's storage, player.GetExtraInventoryCategoryRange,
net.SendItemTransferPacket, the window-aware sends) is tested in
nova-client-src's userinterface_tests, and the server's rules in
nova-server-src. Here the legacy windows of assets/root run over
nui_game_support's stand-ins (legacy_foundation_test's LegacyWorld: the cut's
slot constants, every NovaUI window off), with K's constants and C1's
functions stood in, and are driven as the C++ slot windows drive them:
- uiextrainventory.ExtraInventoryWindow: its uiscript, the local to global
  cell of every category and page (costume pages I-XII), the refresh of the
  visible page, Ctrl + right-click (a transfer, or into the open trade),
  Shift + right-click into the open safebox, a right-click into the open
  Dragon Soul refine window, a key dropped on a box, the drops on an empty
  cell (from both inventories, the safebox and the mall), the sell cursor;
- uiinventory.InventoryWindow: its new button, Ctrl + right-click on a
  costume or a scroll, and an extra item dropped on an empty cell, on an
  item (a stone opens the attach dialog with its window, a scroll is used,
  EXTRA 10 on INVENTORY 10 is a real drop), the use mode over a target;
- uiattachmetin: the stone's window, read and sent;
- game.py: an extra item dropped on an NPC, a player and the ground;
- the shop, the private shop builder, the exchange and the safebox take an
  extra item, the Dragon Soul refine window an extra bean, the mouse an
  extra item's icon;
- uitooltip: the four hint lines;
- every new key in all 17 locales."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import legacy_foundation_test as lf  # noqa: E402

ROOT = support.ROOT
REPO = lf.REPO
UISCRIPT = lf.UISCRIPT
LOCALES = lf.LOCALES

# K's values (nova-client-src 1a5a6ba: GameType.h, PythonPlayerModule.cpp;
# nova-protocol inventory_packets.h), as tools/fixtures/module_constants.json
# holds them once it is made from K's tip (Constants checks that).
K_PLAYER = {
    "EXTRA_INVENTORY": 6, "SLOT_TYPE_EXTRA_INVENTORY": 12,
    "EXTRA_INVENTORY_PAGE_COLUMN": 5, "EXTRA_INVENTORY_PAGE_ROW": 9, "EXTRA_INVENTORY_PAGE_SIZE": 45,
    "EXTRA_INVENTORY_PAGE_COUNT": 32, "EXTRA_INVENTORY_SLOT_COUNT": 1440, "EXTRA_INVENTORY_CATEGORY_COUNT": 5,
    "EXTRA_INVENTORY_COSTUME_PAGE_COUNT": 12,
    "ON_TOP_WND_NONE": 0, "ON_TOP_WND_SHOP": 1, "ON_TOP_WND_EXCHANGE": 2, "ON_TOP_WND_SAFEBOX": 3,
    "ON_TOP_WND_PRIVATE_SHOP": 4,
}
# The categories' cells (C1's player.GetExtraInventoryCategoryRange: scrolls,
# materials, stones, chests with 5 pages each, costumes with 12).
CATEGORY_RANGES = ((0, 225), (225, 450), (450, 675), (675, 900), (900, 1440))
SCROLLS, MATERIALS, STONES, CHESTS, COSTUMES = range(5)
INVENTORY, SAFEBOX, MALL, DS, EXTRA = 1, 3, 4, 5, 6
SLOT_INVENTORY, SLOT_SAFEBOX, SLOT_MALL, SLOT_DS, SLOT_EXTRA = 1, 8, 10, 11, 12
# PythonPlayerModule.cpp's SlotTypeToInvenType (GameType.cpp's table, K's EXTRA row).
SLOT_TO_WINDOW = {SLOT_INVENTORY: INVENTORY, SLOT_SAFEBOX: SAFEBOX, SLOT_MALL: MALL, SLOT_DS: DS, SLOT_EXTRA: EXTRA}

BEWITCH, BLESS = 71051, 71052  # category 0 (spec 3.2), shared with the main inventory
STONE = 28030
KEY, BOX = 50008, 50009
BEAN = 100300
ORE = 50601
COSTUME = 41001
POTION = 27001
SWORD = 10
ITEM_FLAG_APPLICABLE = 1 << 14
ITEM_TYPE_COSTUME = 28

# The new keys, with their English text: {file: {key: English}}.
NEW_KEYS = {
    "interface": {"KEYCHANGE_EXTRA_INVENTORY": "Special Inventory", "EXTRA_INVENTORY_BUTTON": "Inventory+",
                  "EXTRA_INVENTORY_CATEGORY_SCROLLS": "Scrolls", "EXTRA_INVENTORY_CATEGORY_MATERIALS": "Materials",
                  "EXTRA_INVENTORY_CATEGORY_STONES": "Stones", "EXTRA_INVENTORY_CATEGORY_CHESTS": "Chests",
                  "EXTRA_INVENTORY_CATEGORY_COSTUMES": "Costumes"},
    "game": {"MOVE_TO_BANK": "Shift + right-click: Move to Bank",
             "MOVE_TO_TRADE_WINDOW": "Ctrl + right-click: Move to trade window",
             "MOVE_TO_INVENTORY_PLUS": "Ctrl + right-click: Move to Inventory+",
             "MOVE_TO_INVENTORY": "Ctrl + right-click: Move to Inventory"},
}


def compiled(file_name, class_name, names, namespace=None, base=object):
    """A class with the methods `names` of a root module's class, compiled
    from its own source (the legacy code, unchanged) over `namespace`."""
    source = support.source_of(file_name, names, inside=class_name)
    body = "\n".join("\t" + line if line else line for line in source.split("\n"))
    namespace = dict(namespace or {})
    namespace["_Base"] = base
    exec(compile("class %s(_Base):\n%s\n" % (class_name, body), file_name, "exec"), namespace)
    return namespace[class_name]


def locale_entries(path):
    entries = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle.read().split("\n"):
            if "\t" in line:
                tokens = line.split("\t")
                entries[tokens[0]] = tokens[1]
    return entries


class DialogToolTip(support.ToolTip):
    """The stand-in item tooltip, with what the attach dialog's two tooltips
    are asked besides Set* (uiattachmetin.py Open, UpdateDialog)."""

    def __init__(self, *args):
        support.ToolTip.__init__(self, "item")

    def Show(self):
        pass

    def ClearToolTip(self):
        pass

    def AddItemData(self, *args):
        self.calls.append(("AddItemData",) + args)

    def ResizeToolTipWidth(self, width):
        pass

    def GetWidth(self):
        return 190

    def GetHeight(self):
        return 100


class World(lf.LegacyWorld):
    """LegacyWorld with K's constants on the player module, C1's functions
    stood in (the category ranges, the window-aware getters), an exchange
    module (Game.trading), the Interface's IsSafeboxOpen (Game.safebox), a
    safebox module and item tooltips the attach dialog can use."""

    def __init__(self):
        lf.LegacyWorld.__init__(self)
        game = self.game
        game.trading = False
        game.safebox = False
        game.flags_at = {}
        player = game.modules["player"]
        for name, value in K_PLAYER.items():
            setattr(player, name, value)
        ok = player.ATTACH_METIN_OK

        def item_key(at):
            return at[0] if len(at) == 1 else tuple(at)
        support.define(player, "GetExtraInventoryCategoryRange",
                       lambda category: CATEGORY_RANGES[category] if 0 <= category < 5 else (1440, 1440))
        support.define(player, "GetItemFlags", lambda *at: game.flags_at.get(item_key(at), 0))
        support.define(player, "CanUnlock", lambda vnum, *at: True)
        support.define(player, "CanAttachMetin", lambda vnum, *at: ok)
        support.define(player, "GetItemLink", lambda *at: "link%s" % (at,))
        support.define(player, "SlotTypeToInvenType", lambda slot_type: SLOT_TO_WINDOW.get(slot_type, 0))
        support.define(player, "GetISellItemPrice", lambda *at: 10)
        exchange = support.Recording("exchange", game.log, EXCHANGE_ITEM_MAX_NUM=12)
        support.define(exchange, "isTrading", lambda: game.trading)
        game.put("exchange", exchange)
        game.interface.IsSafeboxOpen = lambda: game.safebox
        game.interface.ToggleExtraInventoryWindow = lambda: game.log.append(("interface.ToggleExtraInventoryWindow", ()))
        game.metins.add(STONE)
        game.keys.add(KEY)
        item = game.modules["item"]
        known = support.module_constants()["item"]
        # Only names K's exe exports (no ANTIFLAG_SAFEBOX), so that a missing
        # export fails a test rather than being stood in.
        for name, value in (("ANTIFLAG_GIVE", 1 << 13), ("ITEM_ANTIFLAG_MYSHOP", 1 << 16), ("ANTIFLAG_MYSHOP", 1 << 16)):
            setattr(item, name, known.get(name, value))
        # The open safebox's module (PythonSafeBox.cpp: pages of 5 x 9 cells,
        # GetCurrentSafeboxSize counts the cells): Game.safebox_items
        # {cell: vnum}, Game.safebox_cells.
        game.safebox_items = {}
        game.safebox_cells = 2 * 45
        safebox = support.Recording("safebox", game.log, SAFEBOX_SLOT_X_COUNT=5, SAFEBOX_SLOT_Y_COUNT=9,
                                    SAFEBOX_PAGE_SIZE=45, SAFEBOX_PAGE_COUNT_MAX=5)
        support.define(safebox, "GetItemID", lambda cell: game.safebox_items.get(cell, 0))
        support.define(safebox, "GetCurrentSafeboxSize", lambda: game.safebox_cells)
        game.put("safebox", safebox)
        tooltips = types.ModuleType("uiToolTip")
        tooltips.ItemToolTip = DialogToolTip
        game.put("uiToolTip", tooltips)

    @property
    def mouse(self):
        return self.game.modules["mouseModule"].mouseController

    def attach(self, slot_type, slot, vnum, count=1):
        with self, lf.quiet():
            self.mouse.AttachObject(object(), slot_type, slot, vnum, count)

    def sent(self, prefix="net."):
        return self.game.calls(prefix)

    def press(self, *names):
        app = self.game.modules["app"]
        self.game.pressed = set(getattr(app, name) for name in names)


def make_extra(world):
    """The special inventory as Interface.__MakeWindows makes it, shown."""
    if "uiInventory" not in world.game.loaded:
        world.load("uiInventory", "uiinventory.py")
    module = world.load("uiExtraInventory", "uiextrainventory.py")
    with world, lf.quiet():
        window = module.ExtraInventoryWindow()
        window.BindInterfaceClass(world.game.interface)
        window.SetItemToolTip(world.game.modules["uiToolTip"].ItemToolTip())
        window.SetDragonSoulRefineWindow(world.game.dragon_soul_refine)
        window.Show()
    return window


def make_inventory(world):
    """The inventory with the real attach dialog (uiattachmetin.py)."""
    world.load("uiAttachMetin", "uiattachmetin.py")
    window = lf.make_inventory(world)
    window.SetDragonSoulRefineWindow(world.game.dragon_soul_refine)
    return window


class Constants(unittest.TestCase):
    def test_the_pinned_values_are_ks(self):
        known = support.module_constants()["player"]
        if "EXTRA_INVENTORY" not in known:
            self.skipTest("tools/fixtures/module_constants.json predates K's client tip")
        self.assertEqual(dict((name, known.get(name)) for name in K_PLAYER), K_PLAYER)

    def test_the_categories_cover_the_window_page_by_page(self):
        self.assertEqual(CATEGORY_RANGES[0][0], 0)
        self.assertEqual(CATEGORY_RANGES[-1][1], K_PLAYER["EXTRA_INVENTORY_SLOT_COUNT"])
        pages = [(end - first) // K_PLAYER["EXTRA_INVENTORY_PAGE_SIZE"] for first, end in CATEGORY_RANGES]
        self.assertEqual(pages, [5, 5, 5, 5, K_PLAYER["EXTRA_INVENTORY_COSTUME_PAGE_COUNT"]])
        self.assertEqual(sum(pages), K_PLAYER["EXTRA_INVENTORY_PAGE_COUNT"])


class ExtraWindowScript(unittest.TestCase):
    def script(self):
        world = World()
        with world:
            return lf.read_uiscript(os.path.join(UISCRIPT, "extrainventorywindow.py"))["window"]

    def test_a_5_by_9_grid_twelve_page_tabs_and_five_category_tabs_inside_the_board(self):
        window = self.script()
        board = lf.child(window, "board")
        grid = lf.child(window, "ItemSlot")
        self.assertEqual(("grid_table", 5, 9), (grid["type"], grid["x_count"], grid["y_count"]))
        tabs = [lf.child(window, "Inventory_Tab_%02d" % (page + 1)) for page in range(12)]
        self.assertEqual([lf.child(tab, "Inventory_Tab_%02d_Print" % (page + 1))["text"] for page, tab in enumerate(tabs)],
                         ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"])
        categories = [lf.child(window, "Cat_%02d" % index) for index in range(5)]
        self.assertEqual([tab["text"] for tab in categories],
                         ["EXTRA_INVENTORY_CATEGORY_SCROLLS", "EXTRA_INVENTORY_CATEGORY_MATERIALS",
                          "EXTRA_INVENTORY_CATEGORY_STONES", "EXTRA_INVENTORY_CATEGORY_CHESTS",
                          "EXTRA_INVENTORY_CATEGORY_COSTUMES"])
        self.assertEqual(lf.child(window, "TitleName")["text"], "KEYCHANGE_EXTRA_INVENTORY")
        for widget, width, height in [(tab, 32, 21) for tab in tabs] + [(tab, 88, 21) for tab in categories] + \
                [(grid, 160, 288)]:
            self.assertLessEqual(widget["x"] + width, board["width"] - 8, widget["name"])
            self.assertLessEqual(widget["y"] + height, board["height"] - 8, widget["name"])
        # The tabs sit over the grid, the categories beside it.
        self.assertLess(max(tab["y"] for tab in tabs) + 21, grid["y"] + 1)
        self.assertGreaterEqual(min(tab["x"] for tab in categories), grid["x"] + 160)

    def test_the_inventory_has_the_button_between_the_bag_and_the_money(self):
        for path in (os.path.join(UISCRIPT, "inventorywindow.py"), os.path.join(LOCALES, "ae", "ui", "inventorywindow.py")):
            with self.subTest(path=path):
                world = World()
                with world:
                    window = lf.read_uiscript(path)["window"]
                board = lf.child(window, "board")
                bag = lf.child(window, "ItemSlot")
                button = lf.child(window, "ExtraInventoryButton")
                money = lf.child(window, "Money_Slot")
                self.assertEqual(window["height"], board["height"])
                self.assertEqual(button["text"], "EXTRA_INVENTORY_BUTTON")
                self.assertEqual(button["tooltip_text"], "KEYCHANGE_EXTRA_INVENTORY")
                self.assertGreaterEqual(button["y"], bag["y"] + 32 * 9)
                # The money slot is aligned to the bottom: its top is height - y.
                self.assertLessEqual(button["y"] + 21, board["height"] - money["y"])


class ExtraWindow(unittest.TestCase):
    def world(self):
        world = World()
        return world, make_extra(world)

    def test_the_window_binds_its_twelve_page_tabs_and_five_categories_and_opens_on_materials(self):
        world, window = self.world()
        self.assertEqual(len(window.inventoryTab), 12)
        self.assertEqual(len(window.categoryTab), 5)
        self.assertEqual((MATERIALS, 0), (window.GetCategory(), window.GetInventoryPageIndex()))
        self.assertEqual([tab.down for tab in window.categoryTab], [False, True, False, False, False])

    def test_a_page_cell_is_its_category_s_first_cell_plus_the_page_plus_the_cell(self):
        world, window = self.world()
        for category, (first, end) in enumerate(CATEGORY_RANGES):
            with world, lf.quiet():
                window.categoryTab[category].click()
            pages = [tab.shown for tab in window.inventoryTab]
            count = 12 if category == COSTUMES else 5
            self.assertEqual(pages, [True] * count + [False] * (12 - count), category)
            for page in range(count):
                with world, lf.quiet():
                    window.SetInventoryPage(page)
                for local in (0, 44):
                    self.assertEqual(window.GlobalSlotPos(local), first + page * 45 + local)
        self.assertEqual(window.GlobalSlotPos(44), 1439, "the last costume page ends at the window's end")

    def test_only_the_visible_page_shows_the_extra_items(self):
        world, window = self.world()
        world.game.give((EXTRA, 225 + 45 + 3), BEAN, 7)
        world.game.give((EXTRA, 225 + 3), ORE, 2)
        world.game.give(225 + 45 + 3, POTION, 5)  # the main inventory's cell of the same number
        with world, lf.quiet():
            window.inventoryTab[1].click()
        self.assertEqual(window.wndItem.shown(), {3: (BEAN, "7", False)})
        with world, lf.quiet():
            window.inventoryTab[0].click()
        self.assertEqual(window.wndItem.shown(), {3: (ORE, "2", False)})

    def test_a_hidden_window_refreshes_nothing(self):
        world, window = self.world()
        world.game.give((EXTRA, 225), BEAN, 7)
        with world, lf.quiet():
            window.Hide()
            window.RefreshItemSlot()
        self.assertEqual(window.wndItem.shown(), {})

    def right_click(self, world, window, local, *keys):
        world.press(*keys)
        mark = len(world.game.log)
        with world, lf.quiet():
            window.UseItemSlot(local)
        world.game.pressed = set()
        return [call for call in world.game.log[mark:] if call[0].startswith(("net.", "interface."))]

    def test_ctrl_right_click_moves_the_item_to_the_inventory(self):
        world, window = self.world()
        world.game.give((EXTRA, 225 + 4), BEAN, 3)
        self.assertEqual(self.right_click(world, window, 4, "DIK_LCONTROL"),
                         [("net.SendItemTransferPacket", (EXTRA, 225 + 4, INVENTORY))])

    def test_ctrl_right_click_while_trading_adds_the_item_to_the_trade(self):
        world, window = self.world()
        world.game.trading = True
        world.game.give((EXTRA, 225 + 4), BEAN, 3)
        self.assertEqual(self.right_click(world, window, 4, "DIK_LCONTROL"),
                         [("net.SendExchangeItemAddPacket", (EXTRA, 225 + 4, 0))])

    def test_shift_right_click_puts_the_item_into_the_open_safebox(self):
        world, window = self.world()
        world.game.safebox = True
        world.game.give((EXTRA, 225 + 4), BEAN, 3)
        self.assertEqual(self.right_click(world, window, 4, "DIK_LSHIFT"),
                         [("net.SendSafeboxCheckinPacket", (EXTRA, 225 + 4, 0))])

    def test_shift_right_click_sends_the_first_safebox_cell_the_item_fits(self):
        """OLD's client sent cell 0 and OLD's server searched on from it
        (input_main.cpp:3015-3030); NEW's server refuses a taken cell, so the
        client sends the first free one: here past a 1 x 2 item at 3 (3, 8)."""
        world, window = self.world()
        world.game.item_sizes[SWORD] = (1, 2)
        world.game.safebox_items.update({0: POTION, 1: POTION, 2: POTION, 3: SWORD})
        world.game.safebox = True
        world.game.give((EXTRA, 225 + 4), BEAN, 3)
        self.assertEqual(self.right_click(world, window, 4, "DIK_LSHIFT"),
                         [("net.SendSafeboxCheckinPacket", (EXTRA, 225 + 4, 4))])

    def test_a_right_click_uses_the_item_in_its_window(self):
        world, window = self.world()
        world.game.give((EXTRA, 225 + 4), BEAN, 3)
        self.assertEqual(self.right_click(world, window, 4), [("net.SendItemUsePacket", (EXTRA, 225 + 4))])

    def test_a_right_click_with_the_dragon_soul_refine_window_open_puts_the_bean_into_it(self):
        world, window = self.world()
        world.game.dragon_soul_refine.shown = True
        world.game.give((EXTRA, 225 + 4), BEAN, 3)
        self.assertEqual(self.right_click(world, window, 4), [("interface.AutoSetItem", ((EXTRA, 225 + 4), 1))])

    def test_a_key_dropped_on_a_box_opens_it_and_anything_else_moves(self):
        world, window = self.world()
        with world, lf.quiet():
            window.categoryTab[CHESTS].click()
        world.game.give((EXTRA, 675 + 1), KEY, 2)
        world.game.give((EXTRA, 675 + 2), BOX, 1)
        world.game.give((EXTRA, 675 + 3), BOX, 1)
        world.attach(SLOT_EXTRA, 675 + 1, KEY, 2)
        with world, lf.quiet():
            window.SelectItemSlot(2)
        world.attach(SLOT_EXTRA, 675 + 3, BOX, 1)
        with world, lf.quiet():
            window.SelectItemSlot(2)
        self.assertEqual(world.sent(), [("net.SendItemUseToItemPacket", (EXTRA, 675 + 1, EXTRA, 675 + 2)),
                                        ("net.SendItemMovePacket", (EXTRA, 675 + 3, EXTRA, 675 + 2, 0))])
        self.assertFalse(world.mouse.isAttached())

    def test_the_drops_on_an_empty_cell(self):
        world, window = self.world()
        cell = 225 + 9
        drops = [((SLOT_EXTRA, 225 + 1, BEAN, 4), ("net.SendItemMovePacket", (EXTRA, 225 + 1, EXTRA, cell, 4))),
                 ((SLOT_INVENTORY, 17, BEAN, 2), ("net.SendItemMovePacket", (INVENTORY, 17, EXTRA, cell, 2))),
                 ((SLOT_SAFEBOX, 30, BEAN, 1), ("net.SendSafeboxCheckoutPacket", (30, EXTRA, cell))),
                 ((SLOT_MALL, 2, BEAN, 1), ("net.SendMallCheckoutPacket", (2, EXTRA, cell)))]
        for attached, expected in drops:
            with self.subTest(attached=attached):
                mark = len(world.sent())
                world.attach(*attached)
                with world, lf.quiet():
                    window.SelectEmptySlot(9)
                self.assertEqual(world.sent()[mark:], [expected])
                self.assertFalse(world.mouse.isAttached())

    def test_the_sell_cursor_sells_from_the_window(self):
        world, window = self.world()
        world.game.give((EXTRA, 225 + 4), BEAN, 3)
        world.game.cursor = world.game.modules["app"].SELL
        with world, lf.quiet():
            window.SelectItemSlot(4)
            world.game.dialogs[-1].accept()
        self.assertIn(("net.SendShopSellPacketNew", (225 + 4, 3, EXTRA)), world.sent())

    def test_alt_links_and_shift_splits(self):
        world, window = self.world()
        world.game.give((EXTRA, 225 + 4), BEAN, 3)
        world.press("DIK_LALT")
        with world, lf.quiet():
            window.SelectItemSlot(4)
        self.assertIn(("ime.PasteString", ("link(%d, %d)" % (EXTRA, 225 + 4),)), world.game.calls("ime."))
        world.press("DIK_LSHIFT")
        with world, lf.quiet():
            window.SelectItemSlot(4)
            window.dlgPickMoney.accept(2)
        self.assertEqual(world.game.attaches[-1], ("attach", SLOT_EXTRA, 225 + 4, BEAN, 2))

    def test_the_tooltip_reads_the_extra_window(self):
        world, window = self.world()
        world.game.give((EXTRA, 225 + 4), BEAN, 3)
        with world, lf.quiet():
            window.OverInItem(4)
        tip = window.tooltipItem
        self.assertIn(("SetInventoryItem", 225 + 4, EXTRA), tip.calls)


class InventoryWithExtra(unittest.TestCase):
    def world(self):
        world = World()
        return world, make_inventory(world)

    def test_the_button_toggles_the_special_inventory(self):
        world, window = self.world()
        self.assertIsNotNone(window.extraInventoryButton)
        with world, lf.quiet():
            window.extraInventoryButton.click()
        self.assertIn(("interface.ToggleExtraInventoryWindow", ()), world.game.log)

    def use(self, world, window, cell, *keys):
        world.press(*keys)
        mark = len(world.sent())
        with world, lf.quiet():
            window.UseItemSlot(cell)
        world.game.pressed = set()
        return world.sent()[mark:]

    def test_ctrl_right_click_moves_a_costume_and_a_scroll_and_uses_anything_else(self):
        world, window = self.world()
        item = world.game.modules["item"]
        support.define(item, "GetItemType", lambda: ITEM_TYPE_COSTUME if item.selected[0] == COSTUME else 0)
        world.game.give(3, COSTUME)
        world.game.give(4, BEWITCH, 5)
        world.game.give(5, POTION, 5)
        self.assertEqual(self.use(world, window, 3, "DIK_LCONTROL"), [("net.SendItemTransferPacket", (INVENTORY, 3, EXTRA))])
        self.assertEqual(self.use(world, window, 4, "DIK_LCONTROL"), [("net.SendItemTransferPacket", (INVENTORY, 4, EXTRA))])
        self.assertEqual(self.use(world, window, 5, "DIK_LCONTROL"), [("net.SendItemUsePacket", (5,))])

    def test_ctrl_right_click_while_trading_and_shift_with_the_safebox_open(self):
        world, window = self.world()
        world.game.give(5, POTION, 5)
        world.game.trading = True
        self.assertEqual(self.use(world, window, 5, "DIK_LCONTROL"), [("net.SendExchangeItemAddPacket", (INVENTORY, 5, 0))])
        world.game.trading = False
        world.game.safebox = True
        self.assertEqual(self.use(world, window, 5, "DIK_LSHIFT"), [("net.SendSafeboxCheckinPacket", (INVENTORY, 5, 0))])
        world.game.safebox = False
        self.assertEqual(self.use(world, window, 5, "DIK_LSHIFT"), [("net.SendItemUsePacket", (5,))])

    def test_shift_right_click_sends_the_first_safebox_cell_the_item_fits_inside_a_page(self):
        """The first free cell from 0 where the item's cells are free and on
        one page (OLD's server moved a tall item off a page's last rows,
        input_main.cpp:3020-3024); where none fits, cell 0, which the server
        refuses with OLD's message."""
        world, window = self.world()
        world.game.give(5, SWORD, size=(1, 2))
        world.game.give(6, POTION, 5)
        page = dict((cell, POTION) for cell in range(40) if cell != 35)
        page[35] = SWORD  # cells 35 and 40
        world.game.safebox_items.update(page)
        world.game.safebox = True
        self.assertEqual(self.use(world, window, 6, "DIK_LSHIFT"), [("net.SendSafeboxCheckinPacket", (INVENTORY, 6, 41))])
        self.assertEqual(self.use(world, window, 5, "DIK_LSHIFT"), [("net.SendSafeboxCheckinPacket", (INVENTORY, 5, 45))],
                         "not 41: its second cell would be the next page's first")
        world.game.safebox_cells = 45
        self.assertEqual(self.use(world, window, 5, "DIK_LSHIFT"), [("net.SendSafeboxCheckinPacket", (INVENTORY, 5, 0))])
        world.game.safebox_items.update(dict((cell, POTION) for cell in range(41, 45)))
        self.assertEqual(self.use(world, window, 6, "DIK_LSHIFT"), [("net.SendSafeboxCheckinPacket", (INVENTORY, 6, 0))])

    def drop(self, world, window, attached, cell, empty=False):
        world.attach(*attached)
        mark = len(world.sent())
        with world, lf.quiet():
            if empty:
                window.SelectEmptySlot(cell)
            else:
                window.SelectItemSlot(cell)
        return world.sent()[mark:]

    def test_an_extra_item_dropped_on_an_empty_cell_moves_to_the_inventory(self):
        world, window = self.world()
        self.assertEqual(self.drop(world, window, (SLOT_EXTRA, 900 + 2, COSTUME, 1), 6, empty=True),
                         [("net.SendItemMovePacket", (EXTRA, 900 + 2, INVENTORY, 6, 1))])

    def test_extra_10_on_inventory_10_is_a_real_drop(self):
        world, window = self.world()
        world.game.give(10, SWORD)
        world.game.give((EXTRA, 10), BEWITCH, 5)
        world.game.flags_at[(EXTRA, 10)] = ITEM_FLAG_APPLICABLE
        self.assertEqual(self.drop(world, window, (SLOT_EXTRA, 10, BEWITCH, 5), 10),
                         [("net.SendItemUseToItemPacket", (EXTRA, 10, INVENTORY, 10))])

    def test_a_stone_opens_the_attach_dialog_with_its_window_and_accept_sends_it(self):
        world, window = self.world()
        world.game.give(7, SWORD)
        world.game.give((EXTRA, 450 + 3), STONE)
        self.assertEqual(self.drop(world, window, (SLOT_EXTRA, 450 + 3, STONE, 1), 7), [])
        dialog = window.attachMetinDialog
        self.assertEqual((dialog.metinItemPos, dialog.targetItemPos, dialog.metinWindow), (450 + 3, 7, EXTRA))
        self.assertIn(("LoadImage", "icon/item/%05d.tga" % STONE), dialog.metinImage.calls)
        with world, lf.quiet():
            dialog.Accept()
        self.assertEqual(world.sent()[-1], ("net.SendItemUseToItemPacket", (EXTRA, 450 + 3, INVENTORY, 7)))

    def test_an_inventory_stone_still_opens_and_sends_as_before(self):
        world, window = self.world()
        world.game.give(7, SWORD)
        world.game.give(8, STONE)
        self.assertEqual(self.drop(world, window, (SLOT_INVENTORY, 8, STONE, 1), 7), [])
        dialog = window.attachMetinDialog
        self.assertEqual((dialog.metinItemPos, dialog.targetItemPos, dialog.metinWindow), (8, 7, INVENTORY))
        with world, lf.quiet():
            dialog.Accept()
        self.assertEqual(world.sent()[-1], ("net.SendItemUseToItemPacket", (8, 7)))

    def test_a_key_is_used_and_anything_else_moves(self):
        world, window = self.world()
        world.game.give(7, POTION, 3)
        world.game.give((EXTRA, 675), KEY)
        world.game.give((EXTRA, 225), BEAN, 2)
        self.assertEqual(self.drop(world, window, (SLOT_EXTRA, 675, KEY, 1), 7),
                         [("net.SendItemUseToItemPacket", (EXTRA, 675, INVENTORY, 7))])
        self.assertEqual(self.drop(world, window, (SLOT_EXTRA, 225, BEAN, 2), 7),
                         [("net.SendItemMovePacket", (EXTRA, 225, INVENTORY, 7, 0))])

    def test_an_extra_stone_over_a_weapon_shows_the_use_mode(self):
        world, window = self.world()
        world.game.give(7, SWORD)
        world.game.give((EXTRA, 450), STONE)
        world.attach(SLOT_EXTRA, 450, STONE, 1)
        with world, lf.quiet():
            window.OverInItem(7)
        self.assertTrue(window.wndItem.use_mode)
        self.assertTrue(window.wndItem.usable)


class GameDrops(unittest.TestCase):
    GAME_DROP = ("OnMouseLeftButtonUp", "__PutItem", "__PutMoney", "__DropMoney", "__DropItem", "RequestDropItem",
                 "__SendDropItemPacket")

    def window(self, world, vid=0):
        namespace = dict(world.game.modules)
        cls = compiled("game.py", "GameWindow", self.GAME_DROP, namespace)
        window = cls()
        window.interface = types.SimpleNamespace(BUILD_OnMouseLeftButtonUp=lambda: False)
        window.PickingCharacterIndex = vid
        window.itemDropQuestionDialog = None
        return window

    def drop(self, vid, npc):
        world = World()
        world.game.give((EXTRA, 225 + 6), BEAN, 4)
        world.game.answer("chr", "HasInstance", lambda v: bool(vid) and v == vid)
        world.game.answer("chr", "IsNPC", lambda v: npc)
        world.game.answer("player", "GetMainCharacterIndex", 1)
        window = self.window(world, vid)
        world.attach(SLOT_EXTRA, 225 + 6, BEAN, 4)
        with world, lf.quiet():
            window.OnMouseLeftButtonUp()
            if world.game.dialogs:
                world.game.dialogs[-1].accept()
        return world.sent()

    def test_on_an_npc_it_is_given_with_its_window(self):
        self.assertEqual(self.drop(77, True), [("net.SendGiveItemPacket", (77, EXTRA, 225 + 6, 4))])

    def test_on_a_player_a_trade_starts_with_it(self):
        self.assertEqual(self.drop(77, False), [("net.SendExchangeStartPacket", (77,)),
                                                ("net.SendExchangeItemAddPacket", (EXTRA, 225 + 6, 0))])

    def test_on_the_ground_it_is_asked_and_dropped_with_its_window(self):
        self.assertEqual(self.drop(0, False), [("net.SendItemDropPacketNew", (EXTRA, 225 + 6, 4))])

    def test_u_toggles_the_special_inventory(self):
        source = lf.read(os.path.join(ROOT, "game.py"))
        self.assertRegex(source, r"onPressKeyDict\[app\.DIK_U\]\s*=\s*lambda: self\.interface\.ToggleExtraInventoryWindow\(\)")
        interface = lf.read(os.path.join(ROOT, "interfacemodule.py"))
        self.assertIn("def ToggleExtraInventoryWindow(self):", interface)
        self.assertIn("self.wndExtraInventory.RefreshItemSlot()", interface)
        self.assertIn("self.wndExtraInventory.SetDragonSoulRefineWindow(self.wndDragonSoulRefine)", interface)


class OtherWindows(unittest.TestCase):
    def namespace(self, world):
        return dict(world.game.modules)

    def test_the_shop_buys_an_extra_item_after_asking(self):
        world = World()
        world.game.give((EXTRA, 225 + 6), BEAN, 4)
        world.game.answer("shop", "IsPrivateShop", False)
        names = ("SellAttachedItem", "OnSellItem", "OnCloseQuestionDialog", "__OnClosePopupDialog")
        window = compiled("uishop.py", "ShopDialog", names, self.namespace(world))()
        window.questionDialog = None
        world.attach(SLOT_EXTRA, 225 + 6, BEAN, 4)
        with world, lf.quiet():
            window.SellAttachedItem()
            world.game.dialogs[-1].accept()
        self.assertEqual(world.sent(), [("net.SendShopSellPacketNew", (225 + 6, 4, EXTRA))])

    def test_the_private_shop_builder_prices_an_extra_item(self):
        world = World()
        world.game.give((EXTRA, 225 + 6), BEAN, 4)
        prices = []

        class MoneyInputDialog(object):
            def __getattr__(self, name):
                return lambda *args: None

            def Open(self):
                prices.append(self)
        namespace = self.namespace(world)
        namespace["uiCommon"] = types.SimpleNamespace(MoneyInputDialog=MoneyInputDialog)
        namespace["GetPrivateShopItemPrice"] = lambda vnum: 0
        window = compiled("uiprivateshopbuilder.py", "PrivateShopBuilder", ("OnSelectEmptySlot",), namespace)()
        window.AcceptInputPrice = window.CancelInputPrice = lambda *args: None
        world.attach(SLOT_EXTRA, 225 + 6, BEAN, 4)
        with world, lf.quiet():
            window.OnSelectEmptySlot(3)
        self.assertEqual(len(prices), 1)
        self.assertEqual((prices[0].sourceWindowType, prices[0].sourceSlotPos, prices[0].targetSlotPos), (EXTRA, 225 + 6, 3))

    def test_the_exchange_takes_an_extra_item(self):
        world = World()
        world.game.give((EXTRA, 225 + 6), BEAN, 4)
        window = compiled("uiexchange.py", "ExchangeDialog", ("SelectOwnerEmptySlot",), self.namespace(world))()
        world.attach(SLOT_EXTRA, 225 + 6, BEAN, 4)
        with world, lf.quiet():
            window.SelectOwnerEmptySlot(5)
        self.assertEqual(world.sent(), [("net.SendExchangeItemAddPacket", (EXTRA, 225 + 6, 5))])

    def test_the_safebox_takes_an_extra_item(self):
        world = World()
        world.game.give((EXTRA, 225 + 6), BEAN, 4)
        namespace = self.namespace(world)
        namespace["safebox"] = types.SimpleNamespace(SAFEBOX_PAGE_SIZE=45)
        window = compiled("uisafebox.py", "SafeboxWindow", ("SelectEmptySlot", "__LocalPosToGlobalPos"), namespace)()
        window.curPageIndex = 1
        world.attach(SLOT_EXTRA, 225 + 6, BEAN, 4)
        with world, lf.quiet():
            window.SelectEmptySlot(2)
        self.assertEqual(world.sent(), [("net.SendSafeboxCheckinPacket", (EXTRA, 225 + 6, 45 + 2))])

    def refine_window(self, world):
        set_items = []

        class Base(object):
            refineSlotLockStartIndex = 2
            refineItemInfo = {}

            def _DragonSoulRefineWindow__SetItem(self, inven, slot, count):
                set_items.append(("SetItem", inven, slot, count))
                return True

            def AutoSetItem(self, inven, count):
                set_items.append(("AutoSetItem", inven, count))

            def Refresh(self):
                pass
        names = ("__SelectRefineEmptySlot", "__SelectRefineItemSlot")
        cls = compiled("uidragonsoul.py", "DragonSoulRefineWindow", names, self.namespace(world), base=Base)
        return cls(), set_items

    def test_the_dragon_soul_refine_window_takes_an_extra_bean(self):
        world = World()
        world.game.give((EXTRA, 225 + 6), BEAN, 4)
        window, set_items = self.refine_window(world)
        world.attach(SLOT_EXTRA, 225 + 6, BEAN, 4)
        with world, lf.quiet():
            window._DragonSoulRefineWindow__SelectRefineEmptySlot(0)
        world.attach(SLOT_EXTRA, 225 + 6, BEAN, 1)
        with world, lf.quiet():
            window._DragonSoulRefineWindow__SelectRefineItemSlot(1)
        self.assertEqual(set_items, [("SetItem", (EXTRA, 225 + 6), 0, 4), ("AutoSetItem", (EXTRA, 225 + 6), 1)])

    def test_the_mouse_makes_and_frees_an_extra_item_s_icon(self):
        world = World()
        world.attach(SLOT_EXTRA, 225 + 6, BEAN, 4)
        self.assertTrue(world.mouse.isAttached())
        with world, lf.quiet():
            world.mouse.DeattachObject()
        made = [handle for kind, handle in world.game.created if kind == "item"]
        self.assertEqual(len(made), 1)
        self.assertIn(("item", made[0]), world.game.deleted)


class TooltipHints(unittest.TestCase):
    """uitooltip.py's hint lines (OLD uiToolTip.py:1985-2000) through
    SetInventoryItem, over nui_tooltip_corpus's legacy TipWorld."""

    ITEMS = {
        str(COSTUME): {"name": "Costume", "type": "COSTUME", "subtype": "COSTUME_BODY", "size": [1, 2]},
        str(BEWITCH): {"name": "Bewitch Item", "type": "USE", "subtype": "USE_CHANGE_ATTRIBUTE"},
        str(POTION): {"name": "Red Potion", "type": "USE", "subtype": "USE_POTION"},
        str(BEAN): {"name": "Dragon Bean", "type": "MATERIAL", "subtype": 5},
    }

    def test_the_private_shop_builder_reads_the_item_s_own_window(self):
        """SetPrivateShopBuilderItem(window, cell, slot) reads the sockets and
        bonuses of the item in `window`, not those of the inventory's cell of
        the same number: the builder takes extra items since NOVA-16."""
        import nui_tooltip_corpus as corpus_tool
        rows = {"items": dict((k, dict(v, icon="icon/item/%s.tga" % k, desc="", summary="")) for k, v in self.ITEMS.items()),
                "skills": {}, "mobs": {}}
        world = corpus_tool.TipWorld(rows, recorder=False)
        player = world.game.modules["player"]
        for name, value in K_PLAYER.items():
            setattr(player, name, value)
        asked = []

        def socket(*args):
            asked.append(("GetItemMetinSocket",) + args[:-1])
            return 0

        def attribute(*args):
            asked.append(("GetItemAttribute",) + args[:-1])
            return (0, 0)
        support.define(player, "GetItemMetinSocket", socket)
        support.define(player, "GetItemAttribute", attribute)
        with world, lf.quiet():
            support.apply_case(world.game, {"vnum": COSTUME, "pos": 903})
            tip = world.tooltip("item")
            tip.SetPrivateShopBuilderItem(EXTRA, 903, 3)
        texts = [row[1] for row in corpus_tool.stand_in_rows(tip) if row[0] == "text"]
        self.assertIn("Costume", texts)
        self.assertEqual(set(asked), {("GetItemMetinSocket", EXTRA, 903), ("GetItemAttribute", EXTRA, 903)})

    def lines(self, vnum, window, cell, safebox=False, trading=False, shop_item=False):
        import nui_tooltip_corpus as corpus_tool
        rows = {"items": dict((k, dict(v, icon="icon/item/%s.tga" % k, desc="", summary="")) for k, v in self.ITEMS.items()),
                "skills": {}, "mobs": {}}
        world = corpus_tool.TipWorld(rows, recorder=False)
        player = world.game.modules["player"]
        for name, value in K_PLAYER.items():
            setattr(player, name, value)
        exchange = world.game.modules["exchange"]
        support.define(exchange, "isTrading", lambda: trading)
        with world, lf.quiet():
            tooltip_module = world.m("uiToolTip")
            tooltip_module.SetSafeboxOpen(safebox)
            support.apply_case(world.game, {"vnum": vnum, "pos": cell, "count": 2})
            tip = world.tooltip("item")
            tip.SetInventoryItem(cell, window)
            if shop_item:
                tip.isShopItem = True
                tip.AddItemData(vnum, [0, 0, 0])
            tooltip_module.SetSafeboxOpen(False)
        locale = support.locale_info("en")
        texts = [row[1] for row in corpus_tool.stand_in_rows(tip) if row[0] == "text"]
        keys = ("MOVE_TO_BANK", "MOVE_TO_TRADE_WINDOW", "MOVE_TO_INVENTORY_PLUS", "MOVE_TO_INVENTORY")
        return [key for key in keys if getattr(locale, key, None) in texts]

    def test_a_costume_and_a_scroll_say_ctrl_moves_them(self):
        self.assertEqual(self.lines(COSTUME, INVENTORY, 3), ["MOVE_TO_INVENTORY_PLUS"])
        self.assertEqual(self.lines(BEWITCH, INVENTORY, 3), ["MOVE_TO_INVENTORY_PLUS"])
        self.assertEqual(self.lines(COSTUME, EXTRA, 903), ["MOVE_TO_INVENTORY"])
        self.assertEqual(self.lines(BEWITCH, EXTRA, 3), ["MOVE_TO_INVENTORY"])

    def test_other_items_have_no_move_hint(self):
        self.assertEqual(self.lines(POTION, INVENTORY, 3), [])
        self.assertEqual(self.lines(BEAN, EXTRA, 228), [])

    def test_the_safebox_and_the_trade(self):
        self.assertEqual(self.lines(POTION, INVENTORY, 3, safebox=True), ["MOVE_TO_BANK"])
        self.assertEqual(self.lines(COSTUME, EXTRA, 903, safebox=True), ["MOVE_TO_BANK", "MOVE_TO_INVENTORY"])
        self.assertEqual(self.lines(COSTUME, INVENTORY, 3, trading=True), ["MOVE_TO_TRADE_WINDOW"])
        self.assertEqual(self.lines(BEAN, EXTRA, 228, safebox=True, trading=True), ["MOVE_TO_BANK", "MOVE_TO_TRADE_WINDOW"])

    def test_the_game_phase_s_end_forgets_the_open_safebox(self):
        """The tooltip module outlives the Interface: a phase that ends with the
        safebox open (a warp, a logout) gets no CloseSafebox command, so
        Interface.Close clears the flag, or the next phase shows MOVE_TO_BANK."""
        close = support.source_of("interfacemodule.py", ("Close",), inside="Interface")
        self.assertIn("uiToolTip.SetSafeboxOpen(False)", close)

    def test_no_hint_for_a_worn_item_or_another_window(self):
        self.assertEqual(self.lines(COSTUME, INVENTORY, 109), [], "a worn cell (the stand-in's 90-121)")
        self.assertEqual(self.lines(COSTUME, DS, 3, safebox=True), [])


class Locales(unittest.TestCase):
    def test_every_new_key_is_in_all_17_locales_and_english_is_the_spec_s(self):
        locales = [name for name in sorted(os.listdir(LOCALES))
                   if os.path.isfile(os.path.join(LOCALES, name, "locale_game.txt"))]
        self.assertEqual(len(locales), 17)
        for locale in locales:
            for kind, keys in NEW_KEYS.items():
                path = os.path.join(LOCALES, locale, "locale_%s.txt" % kind)
                with open(path, encoding="utf-8") as handle:
                    self.assertTrue(handle.read().endswith("\n"), path)
                entries = locale_entries(path)
                for key, english in keys.items():
                    with self.subTest(locale=locale, key=key):
                        self.assertTrue(entries.get(key, "").strip())
                        if locale == "en":
                            self.assertEqual(entries[key], english)
                        if kind == "game":
                            self.assertNotIn("|E", entries[key], "NEW has no key icons")
                            self.assertTrue(entries[key].startswith(("Shift + right-click: ", "Ctrl + right-click: ")))


if __name__ == "__main__":
    unittest.main()
