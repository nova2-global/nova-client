"""Tests for the legacy client's tradable icon (wave 4b, chunk C2; NOVA-13):
python3 -B -m unittest tradable_icon_test (from tools/).

The C++ half (the slot states CANT_MOUSE_EVENT and UNUSABLE, wndMgr's four
calls, player.IsAntiFlagBySlot, GC ITEM_ADD's arg4 and the two game
callbacks) is tested in nova-client-src's userinterface_tests; the server's
arg4 in nova-server-src. Here the legacy windows run over the Wave 4
stand-ins (nui_w4_world's World, every NovaUI window off) with K's constants
and C1's functions (extra_inventory_test.install_k), the Interface's own
methods compiled from interfacemodule.py, and every slot window's cell
states recorded:
- the window on top (none, a shop, the exchange, the safebox, a private
  shop being built) marks the inventory's and the special inventory's
  cells whose items it refuses, by their own windows; cell 0 alone;
- the exchange locks the source cell of each item the server put in (an
  inventory or a special inventory cell), again after a page or category
  change, and releases it on GC ITEM_DEL, on close and on the trade's end;
- the private shop builder, the attach dialog and the refine dialog lock
  the cells of the items they hold and release them;
- the shop, the safebox, the private shop builder and the exchange set and
  clear the window on top;
- ui.py's four wrappers of wndMgr."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import extra_inventory_test as ext  # noqa: E402

ROOT = support.ROOT
INVENTORY, EXTRA = ext.INVENTORY, ext.EXTRA
NONE, SHOP, EXCHANGE, SAFEBOX, PRIVATE_SHOP = 0, 1, 2, 3, 4
NO_SELL, NO_GIVE, NO_SAFEBOX, NO_MYSHOP = 70001, 70002, 70003, 70004
# The item anti flags K's and C1's exe export (PythonItemModule.cpp at
# nova-client-src 1a5a6ba and 4fc5ae0): no ANTIFLAG_SAFEBOX, which OLD's
# exported (its PythonItemModule.cpp:1337-1338). The safebox's flag is the
# server's ITEM_ANTIFLAG_SAFEBOX, 1 << 17 (ItemData.h:243 at K's tip).
EXE_ITEM_ANTIFLAGS = {"ITEM_ANTIFLAG_SELL": 1 << 8, "ITEM_ANTIFLAG_GIVE": 1 << 13, "ITEM_ANTIFLAG_MYSHOP": 1 << 16,
                      "ANTIFLAG_SELL": 1 << 8, "ANTIFLAG_GIVE": 1 << 13, "ANTIFLAG_MYSHOP": 1 << 16}
ITEM_ANTIFLAG_SAFEBOX = 1 << 17
POTION, BEAN, STONE, SWORD = ext.POTION, ext.BEAN, ext.STONE, ext.SWORD
INTERFACE = ("SetOnTopWindow", "GetOnTopWindow", "RefreshMarkInventoryBag", "__BindTradableWindows",
             "CantTradableItemExchange", "ReleaseTradableItemExchange", "StartExchange", "EndExchange", "IsSafeboxOpen")


def track(slot_window):
    """Records a slot window's tradable icon states: marks {cell: usable or
    unusable}, locks {cell: True while it takes no mouse event}, and the
    cells each mark call touched. SetItemSlot and ClearSlot reset a cell's
    states, as C1's CSlotWindow::SetSlot and ClearSlot do."""
    slot_window.marks = {}
    slot_window.locks = {}
    slot_window.touched = []
    set_item, clear = slot_window.SetItemSlot, slot_window.ClearSlot

    def reset(cell):
        slot_window.marks.pop(cell, None)
        slot_window.locks.pop(cell, None)

    def set_item_slot(cell, *args):
        reset(cell)
        set_item(cell, *args)

    def clear_slot(cell):
        reset(cell)
        clear(cell)
    slot_window.SetItemSlot = set_item_slot
    slot_window.ClearSlot = clear_slot

    def mark(state):
        def call(cell):
            slot_window.marks[cell] = state
            slot_window.touched.append(cell)
        return call

    def lock(state):
        def call(cell):
            slot_window.locks[cell] = state
        return call
    slot_window.SetUsableSlotOnTopWnd = mark("usable")
    slot_window.SetUnusableSlotOnTopWnd = mark("unusable")
    slot_window.SetCantMouseEventSlot = lock(True)
    slot_window.SetCanMouseEventSlot = lock(False)
    return slot_window


def locked(slot_window):
    return sorted(cell for cell, state in slot_window.locks.items() if state)


class World(object):
    """A Wave 4 world (every NovaUI window off) with install_k, both
    inventories, the exchange, the shop, the safebox and the private shop
    builder, and an Interface made of interfacemodule.py's own methods."""

    def __init__(self):
        self.w4 = w4.World(False)
        game = self.game = self.w4.game
        ext.install_k(game)
        game.give(3, POTION)
        game.give(4, POTION)
        game.give(0, POTION)
        item = game.modules["item"]
        for vnum, flag in ((NO_SELL, item.ANTIFLAG_SELL), (NO_GIVE, item.ANTIFLAG_GIVE),
                           (NO_SAFEBOX, ITEM_ANTIFLAG_SAFEBOX), (NO_MYSHOP, item.ITEM_ANTIFLAG_MYSHOP)):
            game.antiflags[vnum] = flag
        with game, w4.quiet():
            for name, file_name in (("uiAttachMetin", "uiattachmetin.py"), ("uiInventory", "uiinventory.py"),
                                    ("uiExtraInventory", "uiextrainventory.py")):
                game.load(name, file_name)
        namespace = dict(game.modules)
        namespace.update(game.loaded)
        cls = ext.compiled("interfacemodule.py", "Interface", INTERFACE, namespace)
        interface = self.interface = cls()
        interface.onTopWindow = game.modules["player"].ON_TOP_WND_NONE
        with game, w4.quiet():
            inventory = self.inventory = game.loaded["uiInventory"].InventoryWindow()
            inventory.BindInterfaceClass(interface)
            inventory.SetItemToolTip(ext.DialogToolTip())
            inventory.Show()
            extra = self.extra = game.loaded["uiExtraInventory"].ExtraInventoryWindow()
            extra.BindInterfaceClass(interface)
            extra.Show()
        track(inventory.wndItem)
        track(extra.wndItem)
        # The client's safebox constant the stand-in lacks (PythonSafeBox.cpp; nui_safebox_test fails on it today).
        game.modules["safebox"].SAFEBOX_PAGE_COUNT_MAX = 5
        self.exchange = self.w4.make("exchange", "uiExchange", "ExchangeDialog", "nui_exchange.ExchangeDialog")
        self.shop = self.w4.make("shop", "uiShop", "ShopDialog", "nui_shop.ShopDialog")
        self.safebox = self.w4.make("safebox", "uiSafebox", "SafeboxWindow", "nui_safebox.SafeboxWindow")
        self.builder = self.w4.make("private-shop", "uiPrivateShopBuilder", "PrivateShopBuilder",
                                    "nui_private_shop.PrivateShopBuilder")
        with game, w4.quiet():
            self.exchange.LoadDialog()
            self.exchange.SetItemToolTip(self.w4.tooltip)
            self.shop.LoadDialog()
            self.shop.SetItemToolTip(self.w4.tooltip)
        interface.wndInventory, interface.wndExtraInventory = inventory, extra
        interface.dlgExchange, interface.dlgShop = self.exchange, self.shop
        interface.wndSafebox, interface.privateShopBuilder = self.safebox, self.builder
        interface.dlgRefineNew = None
        with game, w4.quiet():
            interface._Interface__BindTradableWindows()

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def run(self, fn, *args):
        with self, w4.quiet():
            return fn(*args)


class Marks(unittest.TestCase):
    def test_each_window_on_top_marks_what_it_refuses(self):
        world = World()
        cases = ((SHOP, NO_SELL), (EXCHANGE, NO_GIVE), (SAFEBOX, NO_SAFEBOX), (PRIVATE_SHOP, NO_MYSHOP))
        for on_top, refused in cases:
            with self.subTest(on_top=on_top):
                world.game.give(3, refused)
                world.game.give((EXTRA, 225 + 3), refused)
                world.run(world.interface.SetOnTopWindow, on_top)
                world.run(world.interface.RefreshMarkInventoryBag)
                for window in (world.inventory, world.extra):
                    marks = window.wndItem.marks
                    self.assertEqual((marks[3], marks[4]), ("unusable", "usable"), type(window).__name__)
                    self.assertEqual(sum(1 for state in marks.values() if state == "unusable"), 1)
        world.run(world.interface.SetOnTopWindow, NONE)
        world.run(world.interface.RefreshMarkInventoryBag)
        for window in (world.inventory, world.extra):
            self.assertEqual(set(window.wndItem.marks.values()), {"usable"})

    def test_cell_0_is_refreshed_alone(self):
        world = World()
        for window in (world.inventory, world.extra):
            window.wndItem.touched = []
            world.run(window.RefreshMarkSlots, 0)
            self.assertEqual(window.wndItem.touched, [0], type(window).__name__)
            window.wndItem.touched = []
            world.run(window.RefreshMarkSlots)
            self.assertEqual(window.wndItem.touched, list(range(45)))

    def test_the_special_inventory_s_marks_read_its_own_cells(self):
        world = World()
        world.game.give(225, NO_GIVE)            # the inventory's cell 225 (a worn cell) is flagged...
        world.game.give((EXTRA, 226), NO_GIVE)   # ...and the special inventory's 226
        mark = len(world.game.log)
        world.run(world.interface.SetOnTopWindow, EXCHANGE)
        world.run(world.interface.RefreshMarkInventoryBag)
        self.assertEqual((world.extra.wndItem.marks[0], world.extra.wndItem.marks[1]), ("usable", "unusable"))
        asked = [args for name, args in world.game.log[mark:] if name == "player.IsAntiFlagBySlot"]
        self.assertIn((EXTRA, 226, world.game.modules["item"].ANTIFLAG_GIVE), asked)
        self.assertNotIn((226, world.game.modules["item"].ANTIFLAG_GIVE), asked, "never the 2-argument INVENTORY form")

    def test_a_page_refresh_marks_the_page_again(self):
        world = World()
        world.run(world.interface.SetOnTopWindow, SHOP)
        world.game.give(45 + 2, NO_SELL)
        with world, w4.quiet():
            world.inventory.inventoryTab[1].click()
        self.assertEqual(world.inventory.wndItem.marks[2], "unusable")


class OnTopAntiFlags(unittest.TestCase):
    def flags(self, **exported):
        """uiinventory.OnTopAntiFlag of no window, a shop, the exchange, the
        safebox and a private shop being built, over an item module that
        exports EXE_ITEM_ANTIFLAGS and `exported`."""
        world = ext.World()
        module = world.load("uiInventory", "uiinventory.py")
        module.item = types.SimpleNamespace(**dict(EXE_ITEM_ANTIFLAGS, **exported))
        with world, w4.quiet():
            return [module.OnTopAntiFlag(on_top) for on_top in (NONE, SHOP, EXCHANGE, SAFEBOX, PRIVATE_SHOP)]

    def test_each_window_s_flag_over_the_exe_s_item_module(self):
        """Without item.ANTIFLAG_SAFEBOX the safebox's flag is the server's
        (1 << 17), not an AttributeError that stops the safebox's ShowWindow
        and OnTop and every inventory refresh while the safebox is on top."""
        self.assertEqual(self.flags(), [0, 1 << 8, 1 << 13, ITEM_ANTIFLAG_SAFEBOX, 1 << 16])

    def test_an_exported_safebox_flag_is_the_one_used(self):
        self.assertEqual(self.flags(ANTIFLAG_SAFEBOX=1 << 30)[SAFEBOX], 1 << 30)


class ExchangeLocks(unittest.TestCase):
    def open(self, world):
        world.run(world.interface.StartExchange)
        self.assertEqual(world.interface.GetOnTopWindow(), EXCHANGE)

    def add(self, world, display, window, cell):
        """game.py BINARY_AddItemToExchange, compiled from its source."""
        cls = ext.compiled("game.py", "GameWindow", ("BINARY_AddItemToExchange", "BINARY_DelItemFromExchange"))
        game_window = cls()
        game_window.interface = world.interface
        world.run(game_window.BINARY_AddItemToExchange, window, cell, display)
        return game_window

    def test_the_source_cells_of_both_inventories_lock(self):
        world = World()
        self.open(world)
        self.add(world, 0, INVENTORY, 4)
        self.add(world, 1, EXTRA, 225 + 5)
        self.assertEqual(locked(world.inventory.wndItem), [4])
        self.assertEqual(locked(world.extra.wndItem), [5])
        self.assertEqual(world.exchange.lockedItems, {0: (INVENTORY, 4), 1: (EXTRA, 230)})

    def test_the_locks_come_back_after_a_page_or_category_change(self):
        world = World()
        self.open(world)
        self.add(world, 0, INVENTORY, 4)
        self.add(world, 1, EXTRA, 225 + 5)
        world.inventory.wndItem.locks.clear()
        world.extra.wndItem.locks.clear()
        with world, w4.quiet():
            world.inventory.inventoryTab[1].click()
            world.extra.categoryTab[ext.COSTUMES].click()
        self.assertEqual((locked(world.inventory.wndItem), locked(world.extra.wndItem)), ([], []))
        with world, w4.quiet():
            world.inventory.inventoryTab[0].click()
            world.extra.categoryTab[ext.MATERIALS].click()
        self.assertEqual(locked(world.inventory.wndItem), [4])
        self.assertEqual(locked(world.extra.wndItem), [5])

    def test_item_del_releases_its_cell_only(self):
        world = World()
        self.open(world)
        game_window = self.add(world, 0, INVENTORY, 4)
        self.add(world, 1, EXTRA, 225 + 5)
        world.run(game_window.BINARY_DelItemFromExchange, 1)
        self.assertEqual(locked(world.extra.wndItem), [])
        self.assertEqual(locked(world.inventory.wndItem), [4])
        self.assertEqual(world.exchange.lockedItems, {0: (INVENTORY, 4)})

    def test_the_end_and_a_close_release_every_cell_and_clear_the_window_on_top(self):
        for end in ("EndExchange", "CloseDialog"):
            with self.subTest(end=end):
                world = World()
                self.open(world)
                self.add(world, 0, INVENTORY, 4)
                self.add(world, 1, EXTRA, 225 + 5)
                target = world.interface if end == "EndExchange" else world.exchange
                world.run(getattr(target, end))
                self.assertEqual((locked(world.inventory.wndItem), locked(world.extra.wndItem)), ([], []))
                self.assertEqual(world.exchange.lockedItems, {})
                self.assertEqual(world.interface.GetOnTopWindow(), NONE)


class OtherLocks(unittest.TestCase):
    def test_the_private_shop_builder_locks_what_it_holds(self):
        world = World()
        world.game.give((EXTRA, 225 + 7), BEAN, 3)
        builder = world.builder
        world.run(builder.Open, "My shop")
        self.assertEqual(world.interface.GetOnTopWindow(), PRIVATE_SHOP)
        for window, cell, target in ((INVENTORY, 4, 0), (EXTRA, 225 + 7, 1)):
            builder.priceInputBoard = types.SimpleNamespace(GetText=lambda: "100", itemVNum=POTION, sourceWindowType=window,
                                                            sourceSlotPos=cell, targetSlotPos=target)
            world.run(builder.AcceptInputPrice)
        self.assertEqual(locked(world.inventory.wndItem), [4])
        self.assertEqual(locked(world.extra.wndItem), [7])
        world.run(builder.OnSelectItemSlot, 0)
        self.assertEqual(locked(world.inventory.wndItem), [])
        world.run(builder.Close)
        self.assertEqual(locked(world.extra.wndItem), [])
        self.assertEqual(world.interface.GetOnTopWindow(), NONE)

    def test_the_attach_dialog_locks_the_stone_and_the_target(self):
        world = World()
        dialog = world.inventory.attachMetinDialog
        world.game.give(4, SWORD)
        world.game.give((EXTRA, 450 + 2), STONE)
        world.run(world.extra.SetCategory, ext.STONES)
        world.run(dialog.Open, 450 + 2, 4, EXTRA)
        self.assertEqual(locked(world.inventory.wndItem), [4])
        self.assertEqual(locked(world.extra.wndItem), [2])
        world.run(dialog.Close)
        self.assertEqual((locked(world.inventory.wndItem), locked(world.extra.wndItem)), ([], []))

    def test_the_refine_dialog_locks_the_refined_item(self):
        world = World()
        source_names = ("Open", "Close", "__Initialize", "SetInven", "__InventoryWindowOf", "__LockCells", "__ReleaseCells",
                        "RefreshLockedSlot")
        namespace = dict(world.game.modules)

        class Shown(object):
            def __init__(self):
                self.calls = []

            def __getattr__(self, name):
                return lambda *args: self.calls.append((name,) + args)

        class Base(object):
            isLoaded = True

            def __init__(self):
                self.probText, self.costText, self.itemImage = Shown(), Shown(), Shown()
                self.slotList = [Shown(), Shown(), Shown()]
                self.toolTip = ext.DialogToolTip()
                self.toolTip.AddRefineItemData = lambda *args: None
                self.lockedItems = []

            def UpdateDialog(self):
                pass

            def SetTop(self):
                pass

            def Show(self):
                pass

            def Hide(self):
                pass
        dialog = ext.compiled("uirefine.py", "RefineDialogNew", source_names, namespace, base=Base)()
        dialog.SetInven(world.inventory, world.extra)
        world.inventory.BindWindow(dialog)
        world.run(dialog.Open, 4, 11, 1000, 50, 0)
        self.assertEqual(locked(world.inventory.wndItem), [4])
        world.run(dialog.Close)
        self.assertEqual(locked(world.inventory.wndItem), [])


class OnTop(unittest.TestCase):
    def test_an_npc_shop_and_the_safebox_set_and_clear_it_and_a_private_shop_does_not(self):
        world = World()
        npc = 77
        world.game.w4["npcs"].add(npc)
        world.run(world.shop.Open, npc)
        self.assertEqual(world.interface.GetOnTopWindow(), SHOP)
        world.run(world.shop.Close)
        self.assertEqual(world.interface.GetOnTopWindow(), NONE)
        world.run(world.shop.Open, 78)
        self.assertEqual(world.interface.GetOnTopWindow(), NONE, "a player's shop marks nothing")
        world.run(world.shop.Close)
        world.run(world.safebox.ShowWindow, 27)
        self.assertEqual(world.interface.GetOnTopWindow(), SAFEBOX)
        world.run(world.safebox.CommandCloseSafebox)
        self.assertEqual(world.interface.GetOnTopWindow(), NONE)

    def test_the_slot_window_wrappers_call_wndmgr(self):
        calls = []
        wndmgr = types.SimpleNamespace(**dict((name, (lambda name: lambda *args: calls.append((name,) + args))(name))
                                              for name in ("SetCanMouseEventSlot", "SetCantMouseEventSlot",
                                                           "SetUsableSlotOnTopWnd", "SetUnusableSlotOnTopWnd")))
        names = ("SetCanMouseEventSlot", "SetCantMouseEventSlot", "SetUsableSlotOnTopWnd", "SetUnusableSlotOnTopWnd")
        slots = ext.compiled("ui.py", "SlotWindow", names, {"wndMgr": wndmgr})()
        slots.hWnd = 9
        for name in names:
            getattr(slots, name)(5)
        self.assertEqual(calls, [(name, 9, 5) for name in names])


if __name__ == "__main__":
    unittest.main()
