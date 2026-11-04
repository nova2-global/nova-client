"""Focused tests for the NovaUI character-select title-bar model."""

import unittest

from nui_phase_test import World


class SelectTitleBadgeTest(unittest.TestCase):
    def test_badge_uses_the_controller_slot_count(self):
        world = World()
        with world:
            owner = type("Owner", (object,), {"SLOT_COUNT": 7})()
            board = world.novaui["nui_select"].SelectBoard(owner)
            self.assertEqual(board.get("slot_badge"), "7 slots")
            self.assertEqual(len(board.get("slots")), 7)
            board.destroy()

    def test_localized_badge_is_protected_as_plain_text(self):
        world = World()
        with world:
            world.modules["uiScriptLocale"].NUI_INTRO_SLOTS = "%d @ui.slots"
            value = world.novaui["nui_select"].slots_badge(5)
            self.assertEqual(value, "5 @\u2060ui.slots")


if __name__ == "__main__":
    unittest.main()
