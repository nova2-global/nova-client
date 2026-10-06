"""Tests for assets/root/nui_slots.py, the slot model helper, the drag bridge
and the tooltip bridge of the NovaUI slot windows: python3 -B -m unittest
nui_slots_test (from tools/).

Plain CPython over nui_game_support's stand-ins: the real mousemodule.py
(its controller records each attach and detach), and item, skill and
grpImage stand-ins that count the icon instances made and freed."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402

P = support.PLAYER_CONSTANTS
INVENTORY, SKILL, EMOTION, QUICK = P["SLOT_TYPE_INVENTORY"], P["SLOT_TYPE_SKILL"], P["SLOT_TYPE_EMOTION"], P["SLOT_TYPE_QUICK_SLOT"]
SHOP, SAFEBOX, MALL, PRIVATE_SHOP = P["SLOT_TYPE_SHOP"], P["SLOT_TYPE_SAFEBOX"], P["SLOT_TYPE_MALL"], P["SLOT_TYPE_PRIVATE_SHOP"]
DRAGON_SOUL = P["SLOT_TYPE_DRAGON_SOUL_INVENTORY"]
GUILD_SKILL = support.SKILL_CONSTANTS["SKILL_TYPE_GUILD"]


class SlotsTest(unittest.TestCase):
    def setUp(self):
        self.game = support.Game().load_standard()
        self.m = self.game.loaded["nui_slots"]
        self.controller = self.game.loaded["mouseModule"].mouseController
        self.game.__enter__()
        self.addCleanup(self.game.__exit__)
        self.m._forget_press()

    def icons(self, kind=None):
        made = [handle for k, handle in self.game.created if kind in (None, k)]
        freed = [handle for k, handle in self.game.deleted if kind in (None, k)]
        return made, freed


class Model(SlotsTest):
    def test_every_slot_has_every_key_of_the_schema(self):
        game = self.game
        game.give(0, 27001, 200)
        game.learn(3, 3, grade=1, level=1)
        game.emotion_icons[5] = "icon/action/dance1.tga"
        slots = [self.m.empty_slot(0), self.m.item_slot(1, 0), self.m.item_slot(2, 9), self.m.skill_slot(3, 3),
                 self.m.skill_slot(4, 40), self.m.emotion_slot(5, 5)]
        for slot in slots:
            self.assertEqual(set(slot), set(self.m.SLOT_KEYS))
            self.assertEqual(len(slot), len(self.m.SLOT_KEYS))
        self.assertEqual([slot["index"] for slot in slots], [0, 1, 2, 3, 4, 5])
        empty = self.m.empty_slot(7)
        self.assertEqual(empty, {"index": 7, "kind": "", "type": 0, "ref": 0, "icon": "", "count": "", "w": 1, "h": 1,
                                 "cd_start": 0.0, "cd_end": 0.0, "active": False, "cover": False,
                                 "disabled": False, "locked": False})
        self.assertEqual(self.m.item_slot(2, 9), self.m.empty_slot(2), "vnum 0 is an empty cell")
        self.assertEqual(self.m.skill_slot(4, 40), self.m.empty_slot(4), "skill index 0 is an empty cell")

    def test_count_labels_follow_set_slot_count_new(self):
        label = self.m.count_label
        self.assertEqual([label(g, 0) for g in range(4)], ["", "", "", ""], "level 0 or less shows nothing")
        self.assertEqual(label(0, -1), "")
        self.assertEqual([label(0, 20), label(1, 1), label(2, 7), label(3, 1)], ["20", "m1", "g7", "p"])
        self.assertEqual(label(3, 40), "p", "a perfect skill has no number")
        self.assertEqual(label(4, 3), "", "legacy formats nothing for another grade")

    def test_item_skill_and_emotion_slots_follow_refresh_quick_slot(self):
        game = self.game
        game.state.now = 50.0
        game.give(0, 27001, 1)
        game.give(1, 27001, 200)
        game.give(2, 72723, 1, sockets=(1, 0, 0))      # an auto potion that is on
        game.give(3, 72723, 1, sockets=(0, 0, 0))      # one that is off
        game.give(4, 19, 1, size=(1, 2))
        game.learn(1, 1, grade=0, level=0)
        game.learn(2, 2, grade=0, level=17)
        game.learn(3, 3, grade=1, level=4, cool=(10.0, 4.0))
        game.learn(4, 4, grade=2, level=1, active=True)
        game.learn(5, 5, grade=3, level=1, cool=(5.0, 1.0))
        game.learn(6, 6, grade=0, level=0, cool=(5.0, 1.0))
        game.learn(152, 152, grade=2, level=0, skill_type=GUILD_SKILL)
        game.guild_levels[152] = 3
        game.emotion_icons[11] = "icon/action/dance1.tga"

        one = self.m.item_slot(0, 0)
        self.assertEqual((one["kind"], one["type"], one["ref"], one["icon"], one["count"]),
                         ("item", INVENTORY, 0, "/icon/item/27001.tga", ""), "a count of 1 shows none")
        self.assertEqual(self.m.item_slot(1, 1)["count"], "200")
        self.assertTrue(self.m.item_slot(2, 2)["active"], "an auto potion that is on")
        self.assertFalse(self.m.item_slot(3, 3)["active"])
        self.assertEqual((self.m.item_slot(4, 4)["w"], self.m.item_slot(4, 4)["h"]), (1, 2))
        self.assertFalse(self.m.item_slot(1, 1)["cover"], "items have no cover")

        level0 = self.m.skill_slot(0, 1)
        self.assertEqual((level0["kind"], level0["type"], level0["ref"], level0["count"], level0["cover"]),
                         ("skill", SKILL, 1, "", True))
        self.assertEqual(level0["icon"], "d:/ymir work/ui/skill/test/1_01.sub")
        self.assertEqual(self.m.skill_slot(0, 2)["count"], "17")
        cooling = self.m.skill_slot(0, 3)
        self.assertEqual((cooling["count"], cooling["cd_start"], cooling["cd_end"]), ("m4", 46.0, 56.0))
        self.assertEqual(cooling["icon"], "d:/ymir work/ui/skill/test/3_02.sub", "the grade's icon")
        self.assertTrue(self.m.skill_slot(0, 4)["active"])
        self.assertEqual(self.m.skill_slot(0, 4)["count"], "g1")
        self.assertEqual(self.m.skill_slot(0, 5)["count"], "p")
        self.assertEqual((self.m.skill_slot(0, 6)["cd_start"], self.m.skill_slot(0, 6)["cd_end"]), (0.0, 0.0),
                         "no sweep for a skill of level 0")
        guild = self.m.skill_slot(0, 152)
        self.assertEqual((guild["count"], guild["icon"]), ("3", "d:/ymir work/ui/skill/test/152_01.sub"),
                         "a guild skill: grade 0, the guild's level")

        emotion = self.m.emotion_slot(6, 11)
        self.assertEqual((emotion["kind"], emotion["type"], emotion["ref"], emotion["icon"], emotion["cover"], emotion["count"]),
                         ("emotion", EMOTION, 11, "/icon/action/dance1.tga", True, ""))

    def test_icon_sources_get_a_slash_only_for_store_paths(self):
        source = self.m.icon_source
        self.assertEqual(source("icon/item/27001.tga"), "/icon/item/27001.tga")
        self.assertEqual(source("/icon/item/27001.tga"), "/icon/item/27001.tga")
        self.assertEqual(source("d:/ymir work/ui/skill/warrior/jeongwi_03.sub"), "d:/ymir work/ui/skill/warrior/jeongwi_03.sub")
        self.assertEqual(source("D:/Ymir Work/UI/x.sub"), "D:/Ymir Work/UI/x.sub")
        self.assertEqual(source("icon\\item\\1.tga"), "/icon/item/1.tga")
        self.assertEqual(source(""), "")
        self.assertEqual(source(None), "")

    def test_cooldown_span_is_in_nui_now_seconds(self):
        self.game.state.now = 120.5
        self.assertEqual(self.m.cooldown_span(10.0), (120.5, 130.5))
        self.assertEqual(self.m.cooldown_span(10, 4), (116.5, 126.5))
        self.assertEqual(self.m.cooldown_span(0), (0.0, 0.0))
        self.assertEqual(self.m.cooldown_span(-1, 3), (0.0, 0.0))
        self.game.state.available = False
        self.assertEqual(self.m.cooldown_span(2.0), (0.0, 2.0), "nui.now() is 0 without a runtime")


class Layers(SlotsTest):
    def test_the_item_layer_places_and_sizes_items_and_owner_of_cells_maps_every_covered_cell(self):
        tall = dict(self.m.empty_slot(1), kind="item", icon="/icon/item/00010.tga", w=1, h=2)
        big = dict(self.m.empty_slot(3), kind="item", icon="/icon/item/00020.tga", w=2, h=3, count="5")
        small = dict(self.m.empty_slot(9), kind="item", icon="/icon/item/27001.tga")
        outside = dict(self.m.empty_slot(9), kind="item", w=1, h=3)
        items = [(1, tall), (3, big), (9, small), (9, outside)]
        layer = self.m.item_layer(items, 5, 2)
        self.assertEqual([(e["c"], e["r"], e["w"], e["h"]) for e in layer], [(1, 0, 1, 2), (4, 1, 1, 1)],
                         "an item that does not fit from its cell is left out")
        self.assertEqual(layer[0]["icon"], "/icon/item/00010.tga")
        self.assertEqual(set(layer[0]) - set(self.m.SLOT_KEYS), {"c", "r"})
        layer = self.m.item_layer([(1, tall), (2, big)], 5, 3)
        self.assertEqual([(e["c"], e["r"], e["w"], e["h"], e["count"]) for e in layer], [(1, 0, 1, 2, ""), (2, 0, 2, 3, "5")])
        owners = self.m.owner_of_cells([(1, tall), (2, big)], 5, 3)
        self.assertEqual(owners, [-1, 0, 1, 1, -1,
                                  -1, 0, 1, 1, -1,
                                  -1, -1, 1, 1, -1])

    def test_footprint_covers_w_by_h_cells_and_refuses_what_does_not_fit(self):
        footprint = self.m.footprint
        self.assertEqual(footprint(7, 1, 1, 5, 9), [7])
        self.assertEqual(footprint(7, 1, 2, 5, 9), [7, 12], "the hovered row and the one below")
        self.assertEqual(footprint(7, 1, 3, 5, 9), [2, 7, 12], "the rows around the hovered one")
        self.assertEqual(footprint(2, 1, 3, 5, 9), [2, 7, 12], "an area above the grid moves down into it")
        self.assertEqual(footprint(42, 1, 2, 5, 9), [37, 42], "an area below the grid moves up into it")
        self.assertEqual(footprint(43, 1, 3, 5, 9), [33, 38, 43])
        self.assertEqual(footprint(3, 2, 2, 5, 9), [3, 4, 8, 9])
        self.assertEqual(footprint(4, 2, 1, 5, 9), [3, 4], "an area right of the grid moves left into it")
        self.assertEqual(footprint(0, 1, 3, 5, 2), [], "taller than the grid")
        self.assertEqual(footprint(0, 6, 1, 5, 9), [], "wider than the grid")
        self.assertEqual(footprint(45, 1, 1, 5, 9), [], "a cell outside the grid")
        self.assertEqual(footprint(-1, 1, 1, 5, 9), [])


class Attach(SlotsTest):
    def test_attach_detaches_first_and_the_shadow_frees_what_the_class_method_leaves_then_goes(self):
        game = self.game
        game.give(0, 27001, 3)
        game.give((P["DRAGON_SOUL_INVENTORY"], 4), 110000, 1)
        game.learn(3, 3, level=1)
        game.put_quick(0, INVENTORY, 0)
        game.put_quick(1, SKILL, 3)
        game.put_quick(2, EMOTION, 11)
        cases = [  # (slot type, slot number, item index, the kind of icon it makes)
            (QUICK, 0, 0, "item"), (QUICK, 1, 1, "skill"), (QUICK, 2, 2, "emotion"),
            (DRAGON_SOUL, 4, 110000, "item"), (INVENTORY, 0, 27001, "item"), (SKILL, 3, 3, "skill"),
            (EMOTION, 11, 11, "emotion"), (SHOP, 0, 27001, "item"), (SAFEBOX, 0, 27001, "item"),
            (MALL, 0, 27001, "item"), (PRIVATE_SHOP, 0, 27001, "item"),
        ]
        for slot_type, number, index, kind in cases:
            ended = []
            before_made, before_freed = len(game.created), len(game.deleted)
            self.assertTrue(self.m.attach("owner", slot_type, number, index, on_end=lambda: ended.append(1)))
            self.assertIn("DeattachObject", self.controller.__dict__, "the shadow is on the instance")
            made = game.created[before_made:]
            self.assertEqual([k for k, _ in made], [kind], slot_type)
            self.controller.DeattachObject()
            freed = game.deleted[before_freed:]
            self.assertEqual(freed, made, "type %d: the icon instance is freed exactly once" % slot_type)
            self.assertEqual(ended, [1])
            self.assertNotIn("DeattachObject", self.controller.__dict__, "the shadow goes with its attach")
            self.assertFalse(self.controller.isAttached())
            self.controller.DeattachObject()
            self.assertEqual(ended, [1], "a later detach does not reach it")
        # attach() detaches what the controller held first, through that attach's own shadow.
        ended = []
        self.m.attach("owner", QUICK, 0, 0, on_end=lambda: ended.append("first"))
        self.m.attach("owner", QUICK, 1, 1, on_end=lambda: ended.append("second"))
        self.assertEqual(ended, ["first"])
        self.assertEqual(game.attaches[-3:], [("attach", QUICK, 0, 0, 0), ("detach", QUICK), ("attach", QUICK, 1, 1, 0)])
        self.controller.DeattachObject()
        self.assertEqual(ended, ["first", "second"])
        made, freed = self.icons()
        self.assertEqual(sorted(made), sorted(freed), "nothing leaks")

    def test_an_attach_another_one_replaced_is_freed_when_that_one_ends(self):
        game = self.game
        game.give(0, 27001, 1)
        game.put_quick(0, INVENTORY, 0)
        ended = []
        self.m.attach("owner", QUICK, 0, 0, on_end=lambda: ended.append(1))
        # Legacy code attaches without detaching first.
        self.controller.AttachObject("legacy", INVENTORY, 0, 27001)
        self.controller.DeattachObject()
        self.assertEqual(ended, [1])
        made, freed = self.icons()
        self.assertEqual(sorted(made), sorted(freed))

    def test_a_legacy_attach_is_untouched(self):
        game = self.game
        game.give(0, 27001, 1)
        game.put_quick(0, INVENTORY, 0)
        self.controller.AttachObject("legacy", QUICK, 0, 0)
        self.assertNotIn("DeattachObject", self.controller.__dict__)
        self.controller.DeattachObject()
        made, freed = self.icons("item")
        self.assertEqual(len(made), 1)
        self.assertEqual(freed, [], "the legacy quick slot leak stays on legacy paths (decision 3)")
        self.assertTrue(self.m.attached() is False)


class Drag(SlotsTest):
    def drag(self, drops=None, uses=None, picks=None, locked=()):
        drops = [] if drops is None else drops
        uses = [] if uses is None else uses
        self.game.give(0, 27001, 1)
        self.game.put_quick(0, INVENTORY, 0)
        self.game.put_quick(1, INVENTORY, 0)

        def pick(index):
            if index in locked or index > 1:
                return None
            return (QUICK, index, index, 0)
        return self.m.SlotDrag(pick=pick, drop=drops.append, use=uses.append,
                               on_pick=(picks.append if picks is not None else None)), drops, uses

    def test_slot_drag_picks_and_places_and_drops_after_a_drag_only(self):
        picks = []
        drag, drops, uses = self.drag(picks=picks)
        drag.press(0, 0)
        self.assertTrue(self.m.attached())
        self.assertEqual(picks, [0])
        self.assertEqual(self.game.attaches[-1], ("attach", QUICK, 0, 0, 0))
        drag.release(0, 0)
        self.assertEqual(drops, [], "a release on the cell it came from keeps it attached")
        self.assertTrue(self.m.attached())
        drag.press(1, 0)
        self.assertEqual(drops, [1], "pick-and-place: the next press drops")
        self.controller.DeattachObject()
        drag.press(0, 0)
        self.game.dragging = False
        drag.release(1, 0)
        self.assertEqual(drops, [1], "no drop without the drag distance")
        self.assertTrue(self.m.attached())
        self.controller.DeattachObject()
        drag.press(0, 0)
        self.game.dragging = True
        drag.release(1, 0)
        self.assertEqual(drops, [1, 1], "a press dragged onto another cell drops there")
        drag.release(1, 0)
        self.assertEqual(drops, [1, 1], "a release forgets the press")
        self.controller.DeattachObject()
        # One press for all grids: a pick in one NovaUI grid dropped over another.
        other_drops = []
        other = self.m.SlotDrag(pick=lambda index: None, drop=other_drops.append)
        drag.press(0, 0)
        other.release(0, 0)
        self.assertEqual(other_drops, [0])
        self.controller.DeattachObject()
        # An empty or locked cell cannot be picked.
        self.game.attaches[:] = []
        drag, drops, uses = self.drag(locked=(1,))
        drag.press(1, 0)
        drag.press(5, 0)
        self.assertEqual(self.game.attaches, [])
        self.assertFalse(self.m.attached())
        # The end of the attach forgets the press: a legacy drop ends it.
        drag.press(0, 0)
        self.controller.DeattachObject()
        self.assertIsNone(self.m._press)

    def test_slot_drag_uses_on_the_right_button_only_when_nothing_is_attached(self):
        drag, drops, uses = self.drag()
        drag.press(0, 1)
        self.assertEqual(uses, [0])
        drag.press(0, 0)
        drag.press(1, 1)
        self.assertEqual(uses, [0], "the host cancels an attach on a right press; the press uses nothing")
        self.assertTrue(self.m.attached(), "and the helper does not cancel it itself")
        drag.release(1, 1)
        self.assertEqual(drops, [])

    def test_a_nuidrop_drops_what_is_attached(self):
        drag, drops, uses = self.drag()
        drag.legacy_drop(1)
        self.assertEqual(drops, [], "nothing attached, nothing dropped")
        self.controller.AttachObject("legacy inventory", INVENTORY, 0, 27001)
        drag.legacy_drop(1)
        self.assertEqual(drops, [1])


class Tooltips(SlotsTest):
    def test_the_tooltip_bridge_shows_one_tooltip_and_none_while_attached(self):
        tooltips = self.game.modules["uiToolTip"]
        bridge = self.m.TooltipBridge()
        bridge.show_inventory_item(3)
        bridge.hide()
        item, skill = tooltips.ItemToolTip(), tooltips.SkillToolTip()
        bridge.set_item_tooltip(item)
        bridge.set_skill_tooltip(0)
        bridge.show_inventory_item(3)
        self.assertEqual(item.shown, [("SetInventoryItem", 3)], "a tooltip of 0 is skipped")
        bridge.set_skill_tooltip(skill)
        bridge.show_skill(5, 3, 1, 4)
        self.assertEqual(skill.shown, [("SetSkillNew", 5, 3, 1, 4)])
        self.assertTrue(skill.visible)
        self.assertFalse(item.visible, "one tooltip at a time")
        bridge.show_inventory_item(4)
        self.assertTrue(item.visible)
        self.assertFalse(skill.visible)
        bridge.show_skill_index(9)
        self.assertEqual(skill.shown[-1], ("SetSkill", 9))
        self.assertFalse(item.visible)
        bridge.hide()
        self.assertFalse(item.visible or skill.visible)
        self.game.give(0, 27001, 1)
        self.controller.AttachObject("legacy", INVENTORY, 0, 27001)
        bridge.show_inventory_item(0)
        bridge.show_skill(5, 3, 1, 4)
        bridge.show_skill_index(9)
        self.assertFalse(item.visible or skill.visible, "nothing shows while an item is attached")
        self.assertEqual(len(item.shown) + len(skill.shown), 4)


if __name__ == "__main__":
    unittest.main()
