"""Tests for the tooltip rules' stand-ins in nui_game_support.py (P14 spec
5.8, 9.6: install_item_data, apply_case, install_tooltip_ui, locale_info,
module_constants), which the tooltip parity test runs uitooltip.py over:
python3 -B -m unittest nui_item_data_test (from tools/)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402

SWORD = {"name": "Sword+0", "type": "ITEM_TYPE_WEAPON", "subtype": "WEAPON_SWORD", "size": [1, 2],
         "antiflags": ["ITEM_ANTIFLAG_SHAMAN"], "flags": 0, "wear": ["WEARABLE_WEAPON"],
         "limits": [["LIMIT_LEVEL", 0]], "applies": [["APPLY_ATT_SPEED", 22]],
         "values": [0, 0, 15, 19, 13, 15], "price": {"buy": 100, "sell": 20}, "desc": "", "summary": ""}


class ItemData(unittest.TestCase):
    def setUp(self):
        game = self.game = support.Game()
        support.install_wave2b_ui(game)
        support.install_wave3a_ui(game)
        support.install_tooltip_ui(game)
        self.data = support.install_item_data(game, {"items": {"10": SWORD}, "skills": {"3": {"name": ["Aura"], "max_level": 40}}})
        game.load_standard()
        game.load("nui_text", "nui_text.py")
        game.__enter__()
        self.addCleanup(game.__exit__)

    def test_the_constants_are_the_clients(self):
        constants = support.module_constants()
        self.assertEqual(constants["item"]["ITEM_ANTIFLAG_SELL"], 1 << 8)
        self.assertEqual(constants["item"]["ITEM_APPLY_MAX_NUM"], 3)
        self.assertEqual(constants["player"]["METIN_SOCKET_MAX_NUM"], 3)
        self.assertEqual(self.game.modules["item"].ITEM_TYPE_WEAPON, constants["item"]["ITEM_TYPE_WEAPON"])

    def test_generate_color_is_the_clients_signed_packing(self):
        self.assertEqual(support.generate_color(0.7607, 0.7607, 0.7607, 1.0) & 0xFFFFFFFF, 0xFFC1C1C1)
        self.assertLess(support.generate_color(1.0, 0.7843, 0.0, 1.0), 0, "a signed C long")
        self.assertEqual(support.generate_color(0, 0, 0, 0), 0)

    def test_the_locale_has_the_real_strings_and_helpers(self):
        locale = support.locale_info("en")
        self.assertEqual(locale.MONETARY_UNIT0, "Yang")
        self.assertEqual(locale.NumberToMoneyString(2000000000000), "2.000.000.000.000 Yang")
        self.assertIn("1", locale.RTSecondToDHMS(61))
        self.assertTrue(callable(locale.TOOLTIP_ITEM_LIMIT_LEVEL) or "%" in locale.TOOLTIP_ITEM_LIMIT_LEVEL)

    def test_the_legacy_rules_run_over_a_case(self):
        support.apply_case(self.game, {"vnum": 10, "sockets": [1, 0, 0], "attrs": [[1, 500]],
                                       "player": {"level": 10, "race": 0}, "clock": 1700000000})
        tooltip = self.game.load("uiToolTip", "uitooltip.py").ItemToolTip()
        tooltip.SetInventoryItem(0)
        texts = [child.text for child in tooltip.childrenList if hasattr(child, "text")]
        self.assertEqual(texts[0], "Sword+0")
        self.assertIn("Attack Speed +22%", texts)
        self.assertEqual(tooltip.childrenList[0].color, 0xFFFFC700, "the special title color: an attribute is set")
        self.assertEqual(tooltip.GetWidth(), 190)
        self.assertEqual(self.game.timestamp, 1700000000)


if __name__ == "__main__":
    unittest.main()
