"""Tests for the NovaUI select item window (assets/root/nui_select_item.py,
P14 spec 6.6): python3 -B -m unittest nui_select_item_test (from tools/).

The legacy uiselectitem.SelectItemWindow (made from its real uiscript by
nui_game_support.install_wave3b_ui) and the NovaUI one, each in a world of
its own with the same inventory (nui_inventory_test.World), opened as
interface.BINARY_OpenSelectItemWindow opens it: the same cells (legacy's
scan of the inventory's pages and, since wave 4b, of the extra inventory's
stone category, its grade rule, its cap of 55 and its rows), and the same
net calls for a press on a stone (its window and cell), a press on an empty
cell, a hover and the close buttons. Legacy calls wndMgr.OnceIgnoreMouseLeftButtonUpEvent() before
each packet; NovaUI does not (NovaUI acts on the press, so the call would
swallow the next legacy release; spec 6.6), and that call is the only
difference. The window's facade is checked in nui_inventory_test.Facade."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_inventory_test as inventory  # noqa: E402

quiet = inventory.quiet
board = inventory.board
fire = inventory.fire
DOCUMENT = "nui/windows/select-item/select-item.rml"
STONES = (28030, 28031, 28032, 28033, 28034, 28035, 28036)
IGNORE = "wndMgr.OnceIgnoreMouseLeftButtonUpEvent"
INVENTORY = 1
# Wave 4b (NOVA-16): main's exe's extra inventory (player.EXTRA_INVENTORY,
# GetExtraInventoryCategoryRange: the stones are category 2, cells 450 to 675).
EXTRA = 6
STONE_RANGE = (450, 675)


def stones(count, grade=0, start=0, skip=()):
    """count spirit stones from inventory position start (positions in skip
    left empty), each of the grade, and a sword and a potion between them."""
    def setup(game):
        game.give(1, 10, size=(1, 2))
        game.give(3, 27001, 5)
        position = start
        for index in range(count):
            while position in skip or position in (1, 3, 6):
                position += 1
            vnum = STONES[index % len(STONES)]
            game.give(position, vnum, 1 + index % 3)
            game.metins.add(vnum)
            game.item_grades[position] = grade
            position += 1
    return setup


def extra_stones(inventory_count, extra_count, grade=0):
    """stones(inventory_count), the extra inventory of main's exe (C1's
    window-aware getters), and extra_count stones in its stone category from
    its first cell, each of the grade (one of grade 3 among them, left out)."""
    inventory_stones = stones(inventory_count, grade)

    def setup(game):
        inventory_stones(game)
        player = game.modules["player"]
        player.EXTRA_INVENTORY = EXTRA
        player.GetExtraInventoryCategoryRange = lambda category: STONE_RANGE if category == 2 else (1440, 1440)
        player.GetItemGrade = lambda *at: game.item_grades.get(at[0] if len(at) == 1 else tuple(at), 0)
        cell = STONE_RANGE[0]
        for index in range(extra_count + 1):
            vnum = STONES[(index + 3) % len(STONES)]
            game.give((EXTRA, cell), vnum, 2 + index % 2)
            game.metins.add(vnum)
            game.item_grades[(EXTRA, cell)] = 3 if index == 1 else grade
            cell += 2
    return setup


class SelectItemTest(unittest.TestCase):
    def worlds(self, setup):
        return inventory.World(False, setup=setup), inventory.World(True, setup=setup)

    def open(self, world):
        window = world.make_select_item()
        with world.game, quiet():
            window.Open()
        return window

    def shown(self, window):
        """{cell: (vnum, count label)} from the board."""
        vnums = window.itemSlot.vnums()
        return dict((cell["index"], (vnums[cell["index"]], cell["count"]))
                    for cell in board(window).model["cells"] if cell["kind"] == "item")

    def legacy_shown(self, window):
        return dict((slot, (vnum, count)) for slot, (vnum, count, _) in window.itemSlot.shown().items())

    def calls(self, world, mark):
        return [(name, args) for name, args in world.game.log[mark:]
                if name.split(".", 1)[0] in ("net", "wndMgr") and name.startswith(("net.Send", IGNORE))]

    def run_both(self, flow, setup=stones(7)):
        results = []
        for world in self.worlds(setup):
            window = self.open(world)
            mark = len(world.game.log)
            with world.game, quiet():
                flow(world, window)
            results.append((self.calls(world, mark), window, world))
        return results

    def without_ignore(self, calls):
        return [call for call in calls if call[0] != IGNORE]


class Cells(SelectItemTest):
    def test_the_cells_equal_legacy_s_scan(self):
        for count, rows in ((7, 3), (15, 3), (16, 4), (20, 4), (21, 5)):
            legacy, novaui = self.worlds(stones(count))
            a, b = self.open(legacy), self.open(novaui)
            with self.subTest(count=count):
                self.assertEqual(self.shown(b), self.legacy_shown(a))
                self.assertEqual(len(board(b).model["cells"]), 5 * rows)
                self.assertEqual(board(b).model["cols"], 5)
                self.assertEqual(b.inventorySlotPosDict, a.inventorySlotPosDict)
                self.assertEqual(a.board.GetHeight(), 76 + 32 * rows, "legacy's rows")

    def test_the_cap_of_55_and_the_second_page(self):
        legacy, novaui = self.worlds(stones(60))
        a, b = self.open(legacy), self.open(novaui)
        self.assertEqual(len(b.inventorySlotPosDict), 55)
        self.assertEqual(len(board(b).model["cells"]), 55)
        self.assertEqual(self.shown(b), self.legacy_shown(a))

    def test_stones_above_grade_2_are_left_out(self):
        legacy, novaui = self.worlds(stones(5, grade=3))
        a, b = self.open(legacy), self.open(novaui)
        self.assertEqual(self.shown(b), {})
        self.assertEqual(self.legacy_shown(a), {})
        self.assertEqual(len(board(b).model["cells"]), 15)

    def test_a_longer_list_makes_the_board_again(self):
        world = inventory.World(True, setup=stones(7))
        window = self.open(world)
        first = board(window)
        with world.game, quiet():
            for position in range(50, 60):
                world.game.give(position, STONES[0])
            window.Open()
        self.assertIsNot(board(window), first)
        self.assertEqual(len(board(window).model["cells"]), 20)
        self.assertEqual(len(self.shown(window)), 17)

    def test_the_legacy_window_underneath_has_the_uiscript_s_flags_and_a_press_raises_it(self):
        legacy, novaui = self.worlds(stones(7))
        a, b = self.open(legacy), self.open(novaui)
        self.assertEqual(b.flags, a.flags)
        self.assertIn("float", b.flags)
        raised = []
        original = b.SetTop
        b.SetTop = lambda: (raised.append(True), original())
        with novaui.game, quiet():
            inventory.press(b, "cell_press", 12, 0)  # an empty cell: nothing else happens
        self.assertEqual(raised, [True])

    def test_the_legacy_window_underneath_stays_0_by_0(self):
        world = inventory.World(True, setup=stones(20))
        window = self.open(world)
        self.assertEqual((window.GetWidth(), window.GetHeight()), (0, 0))


class Flows(SelectItemTest):
    def test_a_press_on_a_stone_sends_its_position_and_hides(self):
        def flow(world, window):
            if world.nui_on:
                fire(window, "cell_press", 2, 0)
            else:
                window.itemSlot.fire("select_item", 2)
        (legacy, a, _), (novaui, b, _) = self.run_both(flow)
        self.assertEqual(self.without_ignore(legacy), novaui)
        self.assertEqual(novaui, [("net.SendSelectItemPacket", (INVENTORY, a.inventorySlotPosDict[2]))],
                         "the stone's window and cell (decision c)")
        self.assertIn((IGNORE, ()), legacy, "legacy ignores the next release")
        self.assertFalse(a.IsShow())
        self.assertFalse(b.IsShow())

    def test_the_gaya_picker_stays_open_after_a_stone_as_legacy_s(self):
        """Wave 5 (NOVA-10): BINARY_OpenSelectItemWindowEx opens the picker with
        stayOpen=True; a pick sends the stone and the picker stays, as legacy's."""
        results = []
        for world in self.worlds(stones(7)):
            window = world.make_select_item()
            with world.game, quiet():
                window.Open(maxGrade=4, stayOpen=True)
            mark = len(world.game.log)
            with world.game, quiet():
                if world.nui_on:
                    fire(window, "cell_press", 2, 0)
                else:
                    window.itemSlot.fire("select_item", 2)
            results.append((self.calls(world, mark), window))
        (legacy, a), (novaui, b) = results
        self.assertEqual(self.without_ignore(legacy), novaui)
        self.assertEqual(novaui, [("net.SendSelectItemPacket", (INVENTORY, a.inventorySlotPosDict[2]))])
        self.assertTrue(a.IsShow())
        self.assertTrue(b.IsShow(), "the next cut asks again: the picker stays open")

    def test_a_right_press_and_a_press_on_an_empty_cell_do_nothing(self):
        def flow(world, window):
            if world.nui_on:
                fire(window, "cell_press", 2, 1)
                fire(window, "cell_press", 12, 0)
            else:
                window.itemSlot.fire("unselect_item", 2)
                window.itemSlot.fire("select_empty", 12)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow)
        self.assertEqual(legacy, [])
        self.assertEqual(novaui, [])

    def test_the_close_buttons_send_0_and_hide(self):
        for button in ("close", "title"):
            def flow(world, window, button=button):
                if world.nui_on:
                    fire(window, "close_press", 0)
                elif button == "close":
                    window.btnExit.Click()
                else:
                    window.Close()
            (legacy, a, _), (novaui, b, world) = self.run_both(flow)
            with self.subTest(button=button):
                self.assertEqual(self.without_ignore(legacy), novaui)
                self.assertEqual(novaui, [("net.SendSelectItemPacket", (0,))])
                self.assertFalse(a.IsShow())
                self.assertFalse(b.IsShow())
                self.assertNotIn(DOCUMENT, world.game.loaded_documents())

    def test_a_hover_shows_the_stone_s_tooltip(self):
        def flow(world, window):
            if world.nui_on:
                fire(window, "cell_over", 1)
                fire(window, "cell_out", 1)
            else:
                window.itemSlot.fire("over_in", 1)
                window.itemSlot.fire("over_out")
        (_, a, _), (_, b, _) = self.run_both(flow)
        self.assertEqual(b.tooltipItem.shown, a.tooltipItem.shown)
        self.assertEqual(b.tooltipItem.shown, [("SetInventoryItem", a.inventorySlotPosDict[1])])
        self.assertFalse(b.tooltipItem.visible)

    def test_a_press_on_the_hovered_stone_hides_its_tooltip_and_the_next_open_shows_none(self):
        """The press hides the board under the pointer, which then hears no
        mouseout: legacy's next mouse move hides the tooltip, and its next
        open re-shows nothing while the pointer is elsewhere."""
        def flow(world, window):
            if world.nui_on:
                fire(window, "cell_over", 1)
                fire(window, "cell_press", 1, 0)
            else:
                window.itemSlot.fire("over_in", 1)
                window.itemSlot.fire("select_item", 1)
                window.itemSlot.fire("over_out")
            window.tooltipItem.shown[:] = []
            window.Open()
        (legacy, a, _), (novaui, b, _) = self.run_both(flow)
        self.assertEqual(self.without_ignore(legacy), novaui)
        self.assertEqual(b.tooltipItem.shown, a.tooltipItem.shown)
        self.assertEqual(b.tooltipItem.shown, [])
        self.assertFalse(b.tooltipItem.visible)

    def test_no_ignore_call_in_the_novaui_window(self):
        import ast
        tree = ast.parse(inventory.read(os.path.join(inventory.ROOT, "nui_select_item.py")))
        called = {node.func.attr for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertNotIn("OnceIgnoreMouseLeftButtonUpEvent", called)


class ExtraInventory(SelectItemTest):
    """Wave 4b (NOVA-16, decision c): the extra inventory's stones after the
    inventory's, each sent and shown by its window."""

    def test_its_stones_follow_the_inventory_s_and_the_cap_holds(self):
        legacy, novaui = self.worlds(extra_stones(4, 5))
        a, b = self.open(legacy), self.open(novaui)
        self.assertEqual(self.shown(b), self.legacy_shown(a))
        self.assertEqual(b.inventorySlotWindowDict, a.inventorySlotWindowDict)
        self.assertEqual([b.inventorySlotWindowDict[i] for i in range(9)], [INVENTORY] * 4 + [EXTRA] * 5)
        self.assertEqual([b.inventorySlotPosDict[i] for i in range(4, 9)], [450, 454, 456, 458, 460],
                         "after the inventory's, in cell order, the grade-3 stone at 452 left out")
        legacy, novaui = self.worlds(extra_stones(50, 10))
        a, b = self.open(legacy), self.open(novaui)
        self.assertEqual(len(b.inventorySlotPosDict), 55)
        self.assertEqual(self.shown(b), self.legacy_shown(a))
        self.assertEqual(list(b.inventorySlotWindowDict.values()).count(EXTRA), 5)

    def test_a_press_on_an_extra_stone_sends_its_window_and_cell(self):
        def flow(world, window):
            if world.nui_on:
                fire(window, "cell_press", 5, 0)
            else:
                window.itemSlot.fire("select_item", 5)
        (legacy, a, _), (novaui, b, _) = self.run_both(flow, extra_stones(4, 3))
        self.assertEqual(self.without_ignore(legacy), novaui)
        self.assertEqual(novaui, [("net.SendSelectItemPacket", (EXTRA, 454))])
        self.assertFalse(b.IsShow())

    def test_an_extra_stone_s_tooltip_reads_its_window(self):
        def flow(world, window):
            if world.nui_on:
                fire(window, "cell_over", 4)
                fire(window, "cell_out", 4)
            else:
                window.itemSlot.fire("over_in", 4)
                window.itemSlot.fire("over_out")
        (_, a, _), (_, b, _) = self.run_both(flow, extra_stones(4, 3))
        self.assertEqual(b.tooltipItem.shown, a.tooltipItem.shown)
        self.assertEqual(b.tooltipItem.shown, [("SetInventoryItem", 450, EXTRA)])


class OnDemand(SelectItemTest):
    def test_no_document_until_open_and_none_after_close(self):
        world = inventory.World(True, setup=stones(7))
        window = world.make_select_item()
        self.assertNotIn(DOCUMENT, world.game.loaded_documents())
        with world.game, quiet():
            window.Open()
        self.assertIn(DOCUMENT, world.game.loaded_documents())
        with world.game, quiet():
            window.Close()
        self.assertNotIn(DOCUMENT, world.game.loaded_documents())

    def test_destroy_unloads_the_board(self):
        world = inventory.World(True, setup=stones(7))
        window = self.open(world)
        with world.game, quiet():
            window.Destroy()
        self.assertEqual(world.game.loaded_documents(), [])


if __name__ == "__main__":
    unittest.main()
