"""Tests for the wave 10 item conveniences (story NOVA-184): python3 -B -m
unittest nui_qol_items_test (from tools/).

- NOVA-191: a right press or a double click on a safebox item takes it out
  to a cell the server picks (net.SAFEBOX_CHECKOUT_ANY_CELL).

Each flow runs on the legacy window and on the NovaUI one, each in a world
of its own with the same state (nui_w4_world.World), and the two make the
same calls (W4_COMPARED, the sounds and the dialogs) in the same order."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_safebox_test as safebox_test  # noqa: E402
import nui_w4_world as w4  # noqa: E402

P = w4.P
ANY_CELL = 0xFFFF
POTION, HELMET = safebox_test.POTION, safebox_test.HELMET


def stock_any_cell(game):
    """The safebox tester's stock, on an exe with the any-cell constant."""
    safebox_test.stock(game)
    game.modules["net"].SAFEBOX_CHECKOUT_ANY_CELL = ANY_CELL


def stock_older_exe(game):
    """The safebox tester's stock, on an exe without the constant."""
    safebox_test.stock(game)
    game.modules["net"].lack("SAFEBOX_CHECKOUT_ANY_CELL")


def sends(calls):
    return [call for call in calls if call[0].startswith("net.")]


# --- NOVA-191: right-click a safebox item to take it out ---------------------------------------------

class SafeboxRightClick(safebox_test.SafeboxTest):
    def use(self, world, window, cell):
        """A double click on a cell (the slot window's use event)."""
        if world.nui_on:
            w4.fire(window, "cell_use", cell)
        else:
            window.wndItem.fire("use", cell)

    def test_a_right_press_on_an_item_takes_it_out_to_any_cell(self):
        def flow(world, window):
            self.press(world, window, 2, button=1)
        (legacy, world, _), (novaui, _, _) = self.run_both(flow, setup=stock_any_cell)
        self.assertEqual(novaui, legacy)
        self.assertEqual(sends(novaui), [("net.SendSafeboxCheckoutPacket", (2, P["INVENTORY"], ANY_CELL))])
        self.assertFalse(world.mouse.isAttached())

    def test_a_double_click_on_page_two_sends_the_global_cell(self):
        def flow(world, window):
            self.page(world, window, 1)
            self.use(world, window, 0)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, setup=stock_any_cell)
        self.assertEqual(novaui, legacy)
        self.assertEqual(sends(novaui), [("net.SendSafeboxCheckoutPacket", (45, P["INVENTORY"], ANY_CELL))])

    def test_an_older_exe_sends_the_protocol_s_value(self):
        def flow(world, window):
            self.press(world, window, 1, button=1)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, setup=stock_older_exe)
        self.assertEqual(novaui, legacy)
        self.assertEqual(sends(novaui), [("net.SendSafeboxCheckoutPacket", (1, P["INVENTORY"], ANY_CELL))])

    def test_an_empty_cell_sends_nothing(self):
        def flow(world, window):
            self.use(world, window, 20)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, setup=stock_any_cell)
        self.assertEqual(novaui, legacy)
        self.assertEqual(sends(novaui), [])

    def test_with_an_item_attached_it_only_drops_the_attach(self):
        """A double click while something is attached cancels the attach and
        takes nothing out (OLD did both)."""
        def flow(world, window):
            self.press(world, window, 2)
            self.use(world, window, 1)
        (legacy, world, _), (novaui, _, _) = self.run_both(flow, setup=stock_any_cell)
        self.assertEqual(novaui, legacy)
        self.assertIn(("mouse.DeattachObject", ()), novaui)
        self.assertEqual(sends(novaui), [])
        self.assertFalse(world.mouse.isAttached())


if __name__ == "__main__":
    unittest.main()
