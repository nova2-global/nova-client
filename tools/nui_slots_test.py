"""Tests for assets/root/nui_slots.py, the slot model helper, the drag bridge
and the tooltip bridge of the NovaUI slot windows: python3 -B -m unittest
nui_slots_test (from tools/).

Plain CPython over nui_game_support's stand-ins: the real mousemodule.py
(its controller records each attach and detach), and item, skill and
grpImage stand-ins that count the icon instances made and freed."""
import json
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
    def test_owner_of_cells_maps_every_covered_cell(self):
        tall = dict(self.m.empty_slot(1), kind="item", icon="/icon/item/00010.tga", w=1, h=2)
        big = dict(self.m.empty_slot(3), kind="item", icon="/icon/item/00020.tga", w=2, h=3, count="5")
        self.assertFalse(hasattr(self.m, "item_layer"), "the layered grid went with slot grid v2's lean grid (P14 spec D1)")
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


def without_the_legacy_fix(test):
    """mousemodule.py as before P15 item 4's legacy fix: its DeattachObject
    leaves the dragon soul and quick slot icons, which NovaUI frees."""
    module = test.game.loaded["mouseModule"]
    test.assertIs(module.DEATTACH_FREES_EVERY_ICON, True)
    module.DEATTACH_FREES_EVERY_ICON = False
    test.addCleanup(setattr, module, "DEATTACH_FREES_EVERY_ICON", True)


class Attach(SlotsTest):
    def test_attach_detaches_first_and_the_shadow_frees_what_the_class_method_leaves_then_goes(self):
        without_the_legacy_fix(self)
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



FOOTPRINT_CASES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "footprint_cases.json")
DROP_TARGET_CASES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "drop_target_cases.json")


class Cells(SlotsTest):
    """Slot grid v2's item grids (P14 spec 4.2 to 4.4, 4.8)."""

    def test_an_empty_cell_has_every_cell_key(self):
        cell = self.m.empty_cell(4)
        self.assertEqual(tuple(self.m.CELL_KEYS[:len(self.m.SLOT_KEYS)]), tuple(self.m.SLOT_KEYS))
        self.assertEqual(set(cell), set(self.m.CELL_KEYS))
        self.assertEqual((cell["index"], cell["covered"], cell["target"], cell["picked"], cell["unavailable"]),
                         (4, False, "", False, False))

    def test_item_cells_put_an_item_on_its_anchor_and_mark_the_cells_it_covers(self):
        game = self.game
        game.give(0, 10, 1, size=(1, 2))         # a 1x2 sword at the top left
        game.give(2, 3000, 1, size=(1, 3))       # a 1x3 glaive
        game.give(4, 27001, 200)
        game.give(40, 10, 1, size=(1, 2))        # on the last row: its lower cell is outside the grid
        cells = self.m.item_cells(list(range(45)), 5, 9)
        self.assertEqual(len(cells), 45)
        self.assertEqual([set(c) for c in cells], [set(self.m.CELL_KEYS)] * 45)
        self.assertEqual((cells[0]["kind"], cells[0]["h"], cells[0]["ref"], cells[0]["covered"]), ("item", 2, 0, False))
        covered = cells[5]
        self.assertEqual((covered["kind"], covered["icon"], covered["count"], covered["covered"], covered["ref"],
                          covered["type"], covered["h"]), ("", "", "", True, 0, INVENTORY, 1),
                         "the covered cell stays a hit target that names its owner")
        self.assertEqual([i for i, c in enumerate(cells) if c["covered"]], [5, 7, 12], "1x2 and 1x3; the last row's spill dropped")
        self.assertEqual(cells[4]["count"], "200")
        self.assertEqual(cells[40]["h"], 2, "the anchor keeps its size; legacy draws it clipped")
        self.assertEqual([self.m.owner_index(cells, i, 5, 9) for i in (0, 5, 7, 12, 13)], [0, 0, 2, 2, 13])
        # A page boundary: page II shows positions 45 to 89.
        game.give(45, 3000, 1, size=(1, 3))
        page = self.m.item_cells([45 + i for i in range(45)], 5, 9)
        self.assertEqual((page[0]["ref"], page[0]["h"], page[5]["covered"], page[10]["covered"]), (45, 3, True, True))
        self.assertEqual(self.m.item_cells([None, 4], 2, 1)[0], self.m.empty_cell(0), "a cell with no position is empty")

    def test_with_states_sets_each_target_and_the_picked_cell(self):
        cells = [self.m.empty_cell(i) for i in range(4)]
        marked = self.m.with_states(cells, {1: "move", 2: "blocked"}, picked=3)
        self.assertEqual([c["target"] for c in marked], ["", "move", "blocked", ""])
        self.assertEqual([c["picked"] for c in marked], [False, False, False, True])
        self.assertEqual(cells[1]["target"], "", "a new list; the cells are not changed")

    def test_attached_info_answers_what_the_controller_holds_with_its_size(self):
        game = self.game
        self.assertIsNone(self.m.attached_info())
        game.give(3, 10, 1, size=(1, 2))
        self.controller.AttachObject("legacy", INVENTORY, 3, 10, 1)
        self.assertEqual(self.m.attached_info(), (INVENTORY, 3, 10, 1, 1, 2))
        self.controller.DeattachObject()
        game.learn(4, 4, level=1)
        self.controller.AttachObject("legacy", SKILL, 4, 4)
        self.assertEqual(self.m.attached_info()[4:], (1, 1), "a skill is one cell")
        self.controller.DeattachObject()
        game.put_quick(0, INVENTORY, 3)
        self.controller.AttachObject("legacy", QUICK, 0, 0)
        self.assertEqual(self.m.attached_info()[4:], (1, 2), "a quick slot's item has its size")


class FootprintVectors(SlotsTest):
    """footprint_states and the CheckMoving rule against every case of
    tools/fixtures/footprint_cases.json, ENGINE's vectors recorded from the
    real CGridSlotWindow (P14 spec 4.9.2: eterpythonlib_tests
    GridFootprintVectors), and drop_target against the hand cases of
    tools/fixtures/drop_target_cases.json, which the recorder does not cover."""

    def load(self, path):
        with open(path, encoding="utf-8") as handle:
            vectors = json.load(handle)
        game = self.game
        game.items.clear()
        cols, rows = vectors["grid"]
        for entry in vectors["items"]:
            game.give(entry["cell"], entry["vnum"], 1, size=(entry["w"], entry["h"]))
        cells = self.m.item_cells(list(range(cols * rows)), cols, rows)
        vnums = dict((entry["cell"], entry["vnum"]) for entry in vectors["items"])
        return vectors, cols, rows, cells, vnums

    def test_the_files_have_the_schema_of_the_contract(self):
        vectors = self.load(FOOTPRINT_CASES)[0]
        self.assertEqual(vectors["source"], "CGridSlotWindow")
        self.assertEqual(vectors["grid"], [5, 9])
        for case in vectors["cases"]:
            self.assertTrue({"hovered", "slot", "w", "h", "vnum", "pick_up", "use_mode", "usable", "cells", "moving",
                             "state", "marked"} <= set(case), case)
            self.assertIn(case["state"], self.m.TARGET_STATES)
        hand = self.load(DROP_TARGET_CASES)[0]
        self.assertEqual(hand["source"], "hand")
        for case in hand["cases"]:
            self.assertTrue({"hovered", "slot", "w", "h", "vnum", "use_mode", "usable", "cells", "target"} <= set(case), case)

    def test_every_recorded_case_matches(self):
        vectors, cols, rows, cells, vnums = self.load(FOOTPRINT_CASES)
        for number, case in enumerate(vectors["cases"]):
            # 9999 is no cell of the grid: the icon came from elsewhere.
            attached = (INVENTORY, case["slot"], case["vnum"], 1, case["w"], case["h"])
            where = "case %d %r" % (number, case)
            found = self.m._picked_list(cells, case["hovered"], case["w"], case["h"], cols, rows, case["use_mode"])
            self.assertEqual(found, case["cells"], where + ": GetPickedSlotList's cells in its order")
            if not case["pick_up"]:
                # SLOT_STYLE_NONE: CheckMoving answers TRUE and nothing draws.
                self.assertTrue(case["moving"], where)
                self.assertEqual(self.m.footprint_states(cells, case["hovered"], attached, cols, rows, case["use_mode"],
                                                         case["usable"], pick_up=False, vnums=vnums), {}, where)
                continue
            self.assertEqual(self.m._check_moving(cells, found, attached, cols, rows, vnums=vnums), case["moving"], where)
            states = self.m.footprint_states(cells, case["hovered"], attached, cols, rows, case["use_mode"],
                                             case["usable"], vnums=vnums)
            self.assertEqual(set(states.values()), {case["state"]}, where)
            self.assertEqual(sorted(states), case["marked"], where)
            # Without the vnum map, the player's inventory answers the same.
            self.assertEqual(self.m.footprint_states(cells, case["hovered"], attached, cols, rows, case["use_mode"],
                                                     case["usable"]), states, where)

    def test_every_drop_target_matches(self):
        vectors, cols, rows, cells, vnums = self.load(DROP_TARGET_CASES)
        for number, case in enumerate(vectors["cases"]):
            attached = (INVENTORY, case["slot"], case["vnum"], 1, case["w"], case["h"])
            where = "case %d %r" % (number, case)
            found = self.m._picked_list(cells, case["hovered"], case["w"], case["h"], cols, rows, case["use_mode"])
            self.assertEqual(sorted(found), sorted(case["cells"]), where)
            self.assertEqual(self.m.drop_target(cells, case["hovered"], attached, cols, rows, case["use_mode"]),
                             case["target"], where)
            states = self.m.footprint_states(cells, case["hovered"], attached, cols, rows, case["use_mode"],
                                             case["usable"], vnums=vnums)
            self.assertEqual(set(states.values()), {case["state"]}, where)

    def test_the_usable_state_covers_the_target_items_area(self):
        cells = self.load(DROP_TARGET_CASES)[3]
        attached = (INVENTORY, -1, 25040, 1, 1, 1)
        states = self.m.footprint_states(cells, 9, attached, 5, 9, True, True)
        self.assertEqual(states, {4: "usable", 9: "usable", 14: "usable"}, "the glaive's three cells")

    def test_no_pick_up_style_draws_no_footprint(self):
        cells = self.load(DROP_TARGET_CASES)[3]
        attached = (INVENTORY, -1, 12200, 1, 1, 1)
        self.assertEqual(self.m.footprint_states(cells, 1, attached, 5, 9, False, False, pick_up=False), {})
        self.assertEqual(self.m.footprint_states(cells, 1, None, 5, 9, False, False), {})


class Proxy(SlotsTest):
    """SlotWindowProxy (P14 spec 6.0)."""

    def refreshed(self):
        seen = []
        return seen, seen.append

    def test_legacy_calls_become_cells_at_refresh(self):
        game = self.game
        game.give(45, 10, 1, size=(1, 2))
        game.give(47, 72723, 1)
        seen, keep = self.refreshed()
        page = [1]
        proxy = self.m.SlotWindowProxy(range(45), keep, cols=5, rows=9, positions=lambda local: page[0] * 45 + local)
        proxy.SetItemSlot(0, 10, 0)
        proxy.SetItemSlot(2, 72723, 0)
        proxy.ActivateSlot(2)
        proxy.SetItemSlot(3, 27001, 200)
        proxy.SetItemSlot(99, 27001, 5)
        self.assertEqual(seen, [], "nothing is handed over before RefreshSlot")
        proxy.RefreshSlot()
        cells = seen[-1]
        self.assertEqual(len(cells), 45)
        self.assertEqual((cells[0]["kind"], cells[0]["ref"], cells[0]["h"], cells[0]["icon"]), ("item", 45, 2, "/icon/item/00010.tga"))
        self.assertTrue(cells[5]["covered"])
        self.assertEqual((cells[2]["active"], cells[3]["count"]), (True, "200"))
        self.assertEqual(cells[0]["count"], "", "legacy passes 0 for a single item")
        self.assertEqual(proxy.owner(5), 0)
        self.assertEqual(proxy.vnums(), {0: 10, 2: 72723, 3: 27001})
        # The same vnum again keeps the active state; another one, or a clear, ends it.
        proxy.SetItemSlot(2, 72723, 0)
        proxy.RefreshSlot()
        self.assertTrue(seen[-1][2]["active"])
        proxy.SetItemSlot(2, 27002, 0)
        proxy.RefreshSlot()
        self.assertFalse(seen[-1][2]["active"])
        proxy.SetItemSlot(3, 0, 0)
        proxy.RefreshSlot()
        self.assertEqual(seen[-1][3], self.m.empty_cell(3), "vnum 0 clears the slot")
        self.assertEqual(proxy.cells(), seen[-1])

    def test_a_count_shows_whenever_legacy_passes_one_above_zero(self):
        seen, keep = self.refreshed()
        proxy = self.m.SlotWindowProxy([152, 153], keep, cols=2, rows=1)
        proxy.SetItemSlot(152, 27001, 1)
        proxy.SetItemSlot(153, 27001, 0)
        proxy.RefreshSlot()
        self.assertEqual([c["count"] for c in seen[-1]], ["1", ""], "CSlotWindow::SetSlotCount draws any count above 0")

    def test_cover_buttons_unavailable_and_the_states(self):
        seen, keep = self.refreshed()
        proxy = self.m.SlotWindowProxy([152, 153, 154], keep, cols=3, rows=1)
        for slot in (152, 153, 154):
            proxy.SetCoverButton(slot, "d:/ymir work/ui/game/quest/slot_button_01.sub", "", "", "d:/ymir work/ui/game/belt_inventory/slot_disabled.tga")
            proxy.SetAlwaysRenderCoverButton(slot, True)
        proxy.EnableCoverButton(152)
        proxy.DisableCoverButton(153)
        proxy.DisableCoverButton(154)
        proxy.SetItemSlot(152, 27001, 3)
        proxy.LockSlot(152)
        proxy.RefreshSlot()
        cells = seen[-1]
        self.assertEqual([c["unavailable"] for c in cells], [False, True, True], "an empty cell shows its cover too")
        self.assertEqual([c["cover"] for c in cells], [False, False, False], "the belt's art is no skill cover")
        self.assertTrue(cells[0]["locked"])
        skills = self.m.SlotWindowProxy([0, 1], keep)
        skills.SetCoverButton(0)
        skills.SetCoverButton(1)
        self.game.learn(0, 7, level=3)
        skills.SetSkillSlotNew(0, 7, 0, 3)
        skills.SetSlotCountNew(0, 0, 3)
        skills.RefreshSlot()
        self.assertEqual([(c["kind"], c["cover"], c["count"]) for c in seen[-1]], [("skill", True, "3"), ("", False, "")],
                         "the skill cover shows on a skill, not on an empty slot")

    def test_events_styles_and_the_grid_size(self):
        proxy = self.m.SlotWindowProxy(range(15), None, cols=5, rows=3)
        picked = []
        proxy.SetSelectItemSlotEvent(picked.append)
        proxy.SAFE_SetButtonEvent("RIGHT", "ALWAYS", picked.append)
        handlers = proxy.handlers()
        self.assertEqual(handlers["select_item"], picked.append)
        self.assertIsNotNone(handlers["unselect_item"])
        self.assertIsNotNone(handlers["unselect_empty"])
        self.assertIsNone(handlers["select_empty"])
        proxy.SetSlotStyle(self.game.modules["wndMgr"].SLOT_STYLE_NONE)
        self.assertFalse(proxy.pick_up)
        proxy.SetUseMode(True)
        proxy.SetUsableItem(True)
        self.assertEqual((proxy.use_mode, proxy.usable), (True, True))
        proxy.ArrangeSlot(0, 5, 7, 32, 32, 0, 0)
        self.assertEqual((proxy.cols, proxy.rows, proxy.GetSlotCount()), (5, 7, 35))
        proxy.SetSlotBaseImage("d:/ymir work/ui/public/slot_base.sub", 1.0, 1.0, 1.0, 1.0)
        with self.assertRaises(AttributeError):
            proxy.SetSlotDiffuseColor(0, 1)


class Events(SlotsTest):
    """LegacySlotEvents: the cells' events as the legacy C++ slot window sends
    them (P14 spec 6.0's table)."""

    def setUp(self):
        SlotsTest.setUp(self)
        game = self.game
        game.give(0, 10, 1, size=(1, 2))
        game.give(2, 27001, 5)
        game.give(3, 12200, 1)
        self.calls = []
        self.seen_states = []
        self.proxy = self.m.SlotWindowProxy(range(15), None, cols=5, rows=3)
        record = self.calls.append
        self.proxy.SetSelectItemSlotEvent(lambda n: (record(("select_item", n)),
                                                     self.controller.AttachObject("legacy", INVENTORY, n, game._item_at(n)["vnum"])))
        self.proxy.SetSelectEmptySlotEvent(lambda n: (record(("select_empty", n)), self.controller.DeattachObject()))
        self.proxy.SetUnselectItemSlotEvent(lambda n: record(("unselect_item", n)))
        self.proxy.SetUnselectEmptySlotEvent(lambda n: record(("unselect_empty", n)))
        self.proxy.SetUseSlotEvent(lambda n: record(("use", n)))
        self.proxy.SetOverInItemEvent(lambda n: record(("over_in", n)))
        self.proxy.SetOverOutItemEvent(lambda: record(("over_out",)))
        for slot in (0, 2, 3):
            self.proxy.SetItemSlot(slot, game._item_at(slot)["vnum"], 0)
        self.proxy.RefreshSlot()
        self.events = self.m.LegacySlotEvents(self.proxy, on_states=lambda states, picked: self.seen_states.append((states, picked)))

    def test_a_press_selects_the_item_or_its_owner_or_the_empty_cell(self):
        self.events.press(5, 0)
        self.assertEqual(self.calls, [("select_item", 0)], "a covered cell stands for its anchor")
        self.assertTrue(self.m.attached())
        self.events.press(9, 0)
        self.assertEqual(self.calls[-1], ("select_empty", 9), "with the sword attached, the empty cell under it")
        self.assertFalse(self.m.attached())
        self.proxy.LockSlot(2)
        self.proxy.RefreshSlot()
        self.events.press(2, 0)
        self.assertEqual(self.calls[-1], ("select_empty", 2), "a locked item counts as empty (OnMouseLeftButtonDown)")

    def test_while_attached_a_press_in_a_grid_goes_to_the_drop_target(self):
        self.controller.AttachObject("legacy", INVENTORY, 30, 10, 1)   # a 1x2 sword from elsewhere
        self.game.item_sizes[10] = (1, 2)
        del self.calls[:]
        self.events.press(12, 0)   # rows 2..3 do not fit: the footprint moves up to 7 and 12
        self.assertEqual(self.calls, [("select_empty", 7)], "the footprint's first cell, as GetPickedSlotPointer")

    def test_the_right_button_and_a_double_click(self):
        self.events.press(2, 1)
        self.events.press(9, 1)
        self.events.press(5, 1)
        self.assertEqual(self.calls, [("unselect_item", 2), ("unselect_empty", 9), ("unselect_item", 0)])
        self.controller.AttachObject("legacy", INVENTORY, 2, 27001, 5)
        self.events.press(3, 1)
        # P15 F-2: CSlotWindow sends the unselect event whatever is attached
        # (with ATTACH_RIGHT off the host cancels the attach and nothing
        # is unselected: AttachRight).
        self.assertEqual(self.calls[3:], [("unselect_item", 3)] if self.m.ATTACH_RIGHT else [])
        self.controller.DeattachObject()
        self.events.use(5)
        self.events.use(9)
        self.assertEqual(self.calls[-1], ("use", 0), "an empty cell has no use event")

    def test_release_drops_after_a_drag_from_another_cell_only(self):
        self.events.press(2, 0)
        self.events.release(2, 0)
        self.assertEqual([c for c in self.calls if c[0].startswith("select")], [("select_item", 2)],
                         "a release on the pressed cell keeps the item attached")
        self.assertTrue(self.m.attached())
        self.controller.DeattachObject()
        self.events.press(2, 0)
        self.events.release(4, 0)
        self.assertEqual(self.calls[-1], ("select_empty", 4))
        self.assertFalse(self.m.attached())
        self.controller.AttachObject("legacy", INVENTORY, 3, 12200, 1)
        self.events.drop(9)
        self.assertEqual(self.calls[-1], ("select_empty", 9), "nuidrop: a legacy press released here")

    def test_over_and_out_send_one_over_in_per_item_and_one_over_out(self):
        self.events.over(0)
        self.events.over(5)
        self.assertEqual(self.calls, [("over_in", 0)], "the same item: m_dwToolTipSlotNumber holds it")
        self.events.over(9)
        self.assertEqual(self.calls[-1], ("over_out",))
        self.events.out(9)
        self.assertEqual(self.calls.count(("over_out",)), 1)
        self.events.over(2)
        self.proxy.SetItemSlot(2, 27001, 4)
        self.proxy.RefreshSlot()
        self.assertEqual(self.calls[-2:], [("over_out",), ("over_in", 2)], "a refresh shows the hovered item again")

    def test_footprint_states_follow_the_hover_while_attached_and_clear_at_the_end(self):
        self.events.over(9)
        self.assertEqual(self.seen_states, [], "nothing attached: no states")
        self.events.press(2, 0)     # pick the stack
        self.assertEqual(self.seen_states[-1], ({2: "move"}, 2), "its own cell, and it is the picked cell")
        self.events.out(2)
        self.events.over(3)
        self.assertEqual(self.seen_states[-1], ({3: "blocked"}, 2), "another item: red")
        self.events.over(5)
        self.assertEqual(self.seen_states[-1], ({5: "blocked"}, 2))
        self.controller.DeattachObject()
        self.assertEqual(self.seen_states[-1], ({}, -1), "the end of the attach clears every grid")
        self.assertNotIn("DeattachObject", self.controller.__dict__, "the watch goes with its attach")

    def test_single_slots_mark_the_hovered_slot_while_attached(self):
        states = []
        wear = self.m.SlotWindowProxy([90, 94], None)
        events = self.m.LegacySlotEvents(wear, on_states=lambda s, p: states.append(s))
        wear.RefreshSlot()
        self.controller.AttachObject("legacy", INVENTORY, 2, 27001, 5)
        events.over(1)
        self.assertEqual(states[-1], {1: "move"})
        events.out(1)
        self.assertEqual(states[-1], {})


class TooltipsWhileAttached(SlotsTest):
    def test_while_attached_shows_the_hovered_item_and_another_window_type_passes_through(self):
        tooltips = self.game.modules["uiToolTip"]
        bridge = self.m.TooltipBridge(while_attached=True)
        item = tooltips.ItemToolTip()
        bridge.set_item_tooltip(item)
        self.game.give(0, 27001, 1)
        self.controller.AttachObject("legacy", INVENTORY, 0, 27001)
        bridge.show_inventory_item(4)
        bridge.show_inventory_item(5, P["DRAGON_SOUL_INVENTORY"])
        self.assertEqual(item.shown, [("SetInventoryItem", 4), ("SetInventoryItem", 5, P["DRAGON_SOUL_INVENTORY"])])
        self.assertFalse(self.m.TooltipBridge().while_attached, "the default keeps the taskbar's rule")

class Attaching(SlotsTest):
    """P14b: the grids that keep is-attaching hear when an attach starts and
    ends, whichever grid or window made it."""

    def setUp(self):
        SlotsTest.setUp(self)
        self.game.give(0, 10, 1, size=(1, 2))
        self.told = {"bag": [], "belt": []}
        self.grids = {}
        for name in ("bag", "belt"):
            proxy = self.m.SlotWindowProxy(range(15), None, cols=5, rows=3)
            proxy.SetSelectItemSlotEvent(lambda n: self.controller.AttachObject("legacy", INVENTORY, n, 10))
            proxy.SetItemSlot(0, 10, 0)
            proxy.RefreshSlot()
            self.grids[name] = self.m.LegacySlotEvents(proxy, on_attaching=self.told[name].append)
        self.plain = self.m.LegacySlotEvents(self.m.SlotWindowProxy(range(4), None))

    def test_a_pick_in_one_grid_tells_every_grid_and_the_end_tells_them_again(self):
        self.grids["bag"].press(5, 0)
        self.assertTrue(self.m.attached())
        self.assertEqual(self.told, {"bag": [True], "belt": [True]})
        self.controller.DeattachObject()
        self.assertEqual(self.told, {"bag": [True, False], "belt": [True, False]})
        self.assertFalse(self.grids["belt"].attaching)

    def test_an_attach_from_a_legacy_window_is_told_at_the_first_pointer_event_of_any_grid(self):
        self.controller.AttachObject("legacy", SHOP, 3, 27001, 1)
        self.assertEqual(self.told, {"bag": [], "belt": []})
        self.plain.over(1)
        self.assertEqual(self.told, {"bag": [True], "belt": [True]})
        self.grids["bag"].over(7)
        self.assertEqual(self.told["bag"], [True], "told once")
        self.controller.DeattachObject()
        self.assertEqual(self.told, {"bag": [True, False], "belt": [True, False]})


# The markup and sheets that keep every slot grid on the shared hit layout
# (P14b; docs/ui/AUTHORING.md "Slot grids"): nuitool's sweep (nui_hit_test)
# checks the goldens' grids point by point; these catch a new window that
# would opt out of it without a golden that shows it.
NUI = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "nui", "nui"))


def _files(folder, ext):
    for base, _, names in os.walk(os.path.join(NUI, folder)):
        for name in sorted(names):
            if name.endswith(ext):
                yield os.path.join(base, name)


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class SharedHitLayout(unittest.TestCase):
    TAG = __import__("re").compile(r"<([a-zA-Z][\w-]*)((?:\s+[^>]*?)?)\s*/?>", __import__("re").S)
    CLASS = __import__("re").compile(r'\bclass="([^"]*)"')

    def cells(self):
        """(document, tag, attributes) of every element of class nui-slot."""
        for path in _files("windows", ".rml"):
            for tag, attributes in self.TAG.findall(_read(path)):
                classes = self.CLASS.search(attributes)
                if classes and "nui-slot" in classes.group(1).split():
                    yield os.path.relpath(path, NUI), tag, attributes

    def test_every_slot_cell_that_takes_the_pointer_is_a_div(self):
        """nui-hit-outset holds for divs only (Core/ElementHitOutset.h)."""
        found = [(path, tag) for path, tag, attributes in self.cells() if "data-event-mouse" in attributes and tag != "div"]
        self.assertEqual(found, [])
        self.assertGreater(len(list(self.cells())), 10)

    def test_a_lean_grid_that_can_hold_a_tall_item_binds_is_attaching(self):
        """Its anchors cover their items only at rest; without is-attaching a
        drop footprint would follow the anchor, not the cell under the
        pointer."""
        missing = []
        for path in _files("windows", ".rml"):
            text = _read(path)
            if "data-class-nui-slot--h2" not in text and "data-class-nui-slot--h3" not in text:
                continue
            for tag, attributes in self.TAG.findall(text):
                classes = self.CLASS.search(attributes)
                if classes and "nui-slot-grid--lean" in classes.group(1).split() and "data-class-is-attaching=" not in attributes:
                    missing.append(os.path.relpath(path, NUI))
        self.assertEqual(missing, [])

    def test_no_window_sheet_changes_a_slot_cell_s_hit_box(self):
        """The hit outsets are the shared component's and the skins' (classic's
        uneven wear places); a window sheet that set its own, or took the
        pointer from a cell, would leave a dead zone."""
        found = []
        for path in _files("windows", ".rcss"):
            for match in __import__("re").finditer(r"([^{}]*)\{([^}]*)\}", _read(path)):
                selector, body = match.group(1), match.group(2)
                if "nui-hit-outset" in body or ("pointer-events" in body and ("nui-slot" in selector or "-wear" in selector)):
                    found.append((os.path.relpath(path, NUI), selector.strip().splitlines()[-1]))
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()


# --- Wave 3c (P15) ---

class _Limits(object):
    """A stand-in for nui_limits' Limits: the count label rule only."""

    def __init__(self, labels):
        self.SKILL_LABELS = labels


class CountLabelFor(SlotsTest):
    def test_today_s_rule_and_the_sage_grade_s(self):
        today, sage = _Limits("p"), _Limits("over_p")
        label = self.m.count_label_for
        for grade in range(5):
            for level in (-1, 0, 1, 10, 40, 50):
                self.assertEqual(label(grade, level, today), self.m.count_label(grade, level), (grade, level))
        self.assertEqual([label(g, 7, sage) for g in range(5)], ["7", "m7", "g7", "p7", "s"])
        self.assertEqual([label(g, 0, sage) for g in range(5)], [""] * 5, "level 0 shows nothing")
        self.assertEqual(label(3, 50, sage), "p50")

    def test_without_limits_it_takes_the_current_ones_or_today_s_rule(self):
        self.assertNotIn("nui_limits", sys.modules)
        self.assertEqual(self.m.count_label_for(3, 9), "p", "no limits module: today's rule")


class FullProxy(SlotsTest):
    """FullSlotWindowProxy (P15 spec 11.3), rule for rule with CSlotWindow."""

    def setUp(self):
        SlotsTest.setUp(self)
        self.seen = []
        self.game.state.now = 100.0

    def proxy(self, slots=(1, 21, 41, 2, 22, 42), **kwargs):
        kwargs.setdefault("limits", _Limits("p"))
        return self.m.FullSlotWindowProxy(list(slots), self.seen.append, **kwargs)

    def cell(self, proxy, slot):
        proxy.RefreshSlot()
        return self.seen[-1][proxy.index_of(slot)]

    def test_the_same_skill_again_keeps_its_state_and_another_clears_it(self):
        proxy = self.proxy()
        self.game.learn(1, 5, level=3)
        proxy.SetSkillSlotNew(1, 5, 0, 3)
        proxy.SetSlotCountNew(1, 0, 3)
        proxy.SetSlotCoolTime(1, 10.0)
        proxy.ActivateSlot(1)
        proxy.SetSkillSlotNew(1, 5, 1, 3)   # the same skill at another grade: its icon changes
        cell = self.cell(proxy, 1)
        self.assertEqual((cell["kind"], cell["icon"], cell["count"], cell["active"], cell["cd_end"]),
                         ("skill", "d:/ymir work/ui/skill/test/5_02.sub", "3", True, 110.0))
        self.assertEqual((cell["type"], cell["ref"]), (P["SLOT_TYPE_SKILL"], 1))
        proxy.SetSkillSlotNew(1, 6, 0, 3)   # another skill: CSlotWindow::ClearSlot first
        cell = self.cell(proxy, 1)
        self.assertEqual((cell["count"], cell["active"], cell["cd_end"]), ("", False, 0.0))
        proxy.SetSkillSlotNew(1, 0, 0, 3)   # no icon: cleared
        self.assertEqual(self.cell(proxy, 1)["kind"], "")
        proxy.SetSkillSlotNew(99, 5, 0, 3)  # a slot the window does not hold: ignored
        self.assertEqual(proxy.GetSlotCount(), 6)

    def test_set_skill_slot_shows_the_grade_0_icon_and_the_level(self):
        proxy = self.proxy(slots=range(101, 113), cols=6, rows=2)
        proxy.SetSkillSlot(101, 122, 20)
        cell = self.cell(proxy, 101)
        self.assertEqual((cell["kind"], cell["icon"], cell["count"]), ("skill", "d:/ymir work/ui/skill/test/122_01.sub", "20"))
        self.assertEqual(proxy.GetStartIndex(), 101)

    def test_set_slot_takes_its_icon_from_the_window_and_its_alpha(self):
        names = {}
        proxy = self.proxy(slots=range(5), cols=1, rows=5, icon_of=lambda slot, handle: names.get(slot, ""))
        names[0] = "d:/ymir work/ui/game/quest/questicon/scroll.tga"
        proxy.SetSlot(0, 0, 1, 1, 12345)
        proxy.SetSlot(1, 1, 1, 1, 0, (1.0, 1.0, 1.0, 0.5))
        self.seen[:] = []
        proxy.RefreshSlot()
        cells = self.seen[-1]
        self.assertEqual((cells[0]["kind"], cells[0]["icon"], cells[0]["type"], cells[0]["ref"]),
                         ("icon", "d:/ymir work/ui/game/quest/questicon/scroll.tga", 0, 0))
        self.assertEqual((cells[1]["kind"], cells[1]["icon"]), ("icon", ""), "no file: no image, still a set slot")
        extras = proxy.extras()
        self.assertEqual((extras[0]["alpha"], extras[1]["alpha"]), (1.0, 0.5))
        self.assertTrue(proxy.is_item(0), "a set slot takes a press as an item (CSlotWindow isItem)")

    def test_emotions_and_a_missing_icon(self):
        self.game.emotion_icons[3] = "icon/action/clap.tga"
        proxy = self.proxy(slots=range(1, 19), cols=6, rows=3)
        proxy.SetEmotionSlot(3, 3)
        proxy.SetEmotionSlot(4, 4)
        proxy.SetCoverButton(3)
        proxy.SetCoverButton(4)
        proxy.RefreshSlot()
        cells = self.seen[-1]
        self.assertEqual((cells[2]["kind"], cells[2]["icon"], cells[2]["cover"]), ("emotion", "/icon/action/clap.tga", True))
        self.assertEqual((cells[3]["kind"], cells[3]["cover"]), ("", False), "an emotion with no icon is cleared")

    def test_cover_buttons_are_enabled_again_by_set_cover_button(self):
        proxy = self.proxy()
        self.game.learn(1, 5, level=3)
        proxy.SetSkillSlotNew(21, 5, 1, 3)
        proxy.SetCoverButton(21)
        proxy.DisableCoverButton(21)
        self.assertTrue(self.cell(proxy, 21)["unavailable"])
        proxy.SetCoverButton(21)
        self.assertFalse(self.cell(proxy, 21)["unavailable"], "CSlotWindow::SetCoverButton enables it")

    def test_count_labels_follow_the_limits(self):
        proxy = self.proxy(limits=_Limits("over_p"))
        proxy.SetSkillSlotNew(41, 5, 2, 50)
        proxy.SetSlotCountNew(41, 3, 7)
        self.assertEqual(self.cell(proxy, 41)["count"], "p7")
        proxy.SetSlotCountNew(41, 4, 50)
        self.assertEqual(self.cell(proxy, 41)["count"], "s")

    def test_slot_buttons_and_the_base_image(self):
        proxy = self.proxy()
        proxy.ShowSlotButton(1)
        self.assertFalse(proxy.extras()[0]["button"], "no button before AppendSlotButton")
        proxy.AppendSlotButton("up", "over", "down")
        self.assertEqual([e["button"] for e in proxy.extras().values()], [False] * 6, "appended hidden")
        proxy.ShowSlotButton(1)
        proxy.ShowSlotButton(2)
        self.assertEqual([proxy.extras()[i]["button"] for i in range(6)], [True, False, False, True, False, False])
        proxy.ClearSlot(1)
        self.assertFalse(proxy.extras()[0]["button"], "a cleared slot hides its button")
        proxy.HideAllSlotButton()
        self.assertFalse(proxy.extras()[3]["button"])
        self.assertTrue(proxy.extras()[1]["closed"], "the base image shows until hidden")
        proxy.HideSlotBaseImage(21)
        self.assertFalse(proxy.extras()[1]["closed"])
        proxy.ClearSlot(21)
        self.assertTrue(proxy.extras()[1]["closed"], "ClearSlot shows it again")
        proxy.HideSlotBaseImage(21)
        proxy.ShowSlotBaseImage(21)
        self.assertTrue(proxy.extras()[1]["closed"])

    def test_the_cooldown_store_restores_in_slot_order_and_stops_at_a_slot_it_lacks(self):
        proxy = self.proxy()
        for slot in (1, 21, 2):
            proxy.SetSkillSlotNew(slot, 5, 0, 1)
        proxy.StoreSlotCoolTime(1, 21, 10.0)
        self.game.state.now = 102.0
        proxy.StoreSlotCoolTime(1, 2, 8.0, 1.0)
        proxy.ActivateSlot(2)          # marks the stored ACTIVE entry
        proxy.StoreSlotCoolTime(1, 30, 5.0)   # the window lacks 30
        proxy.StoreSlotCoolTime(1, 1, 4.0)
        self.assertEqual(proxy.stored(1)[2], (8.0, 101.0, True))
        proxy.RestoreSlotCoolTime(1)
        proxy.RefreshSlot()
        cells = dict((proxy.slot_number(i), c) for i, c in enumerate(self.seen[-1]))
        self.assertEqual((cells[1]["cd_start"], cells[1]["cd_end"]), (102.0, 106.0))
        self.assertEqual((cells[2]["cd_start"], cells[2]["cd_end"], cells[2]["active"]), (101.0, 109.0, True))
        self.assertEqual((cells[21]["cd_start"], cells[21]["cd_end"], cells[21]["active"]), (100.0, 110.0, False))
        proxy.StoreSlotCoolTime(1, 21, 10.0)   # stored again: not active
        proxy.ActivateSlot(21)
        proxy.StoreSlotCoolTime(1, 21, 12.0)
        self.assertEqual(proxy.stored(1)[21][2], False, "a store resets the entry's active state")

    def test_the_store_survives_a_clear_and_restore_deactivates_a_slot_stored_inactive(self):
        proxy = self.proxy()
        proxy.SetSkillSlotNew(1, 5, 0, 1)
        proxy.StoreSlotCoolTime(1, 1, 10.0)
        proxy.ActivateSlot(1)
        proxy.DeactivateSlot(1)
        proxy.ClearSlot(1)
        proxy.SetSkillSlotNew(1, 5, 0, 1)
        proxy.ActivateSlot(1)
        proxy.StoreSlotCoolTime(1, 1, 10.0)
        proxy.RestoreSlotCoolTime(1)
        cell = self.cell(proxy, 1)
        self.assertEqual((cell["cd_end"], cell["active"]), (110.0, False))

    def test_transfer_moves_the_active_entry_and_shows_it_only_on_a_learned_target(self):
        proxy = self.proxy()
        for slot in (1, 21, 41):
            proxy.SetSkillSlotNew(slot, 5, 0, 1)
        proxy.StoreSlotCoolTime(1, 1, 10.0)
        proxy.ActivateSlot(1)
        proxy.SetSlotCoolTime(1, 10.0)
        proxy.TransferSlotCoolTime(1, 21)    # player.GetSkillLevel(21) is 0: no cooldown shown there
        proxy.RefreshSlot()
        cells = dict((proxy.slot_number(i), c) for i, c in enumerate(self.seen[-1]))
        self.assertEqual((cells[1]["cd_end"], cells[21]["cd_end"], cells[21]["active"]), (0.0, 0.0, True))
        self.assertEqual(list(proxy.stored(1)), [21])
        self.game.learn(41, 9, level=3)
        proxy.TransferSlotCoolTime(21, 41)
        proxy.RefreshSlot()
        cells = dict((proxy.slot_number(i), c) for i, c in enumerate(self.seen[-1]))
        self.assertEqual((cells[41]["cd_start"], cells[41]["cd_end"]), (100.0, 110.0))
        proxy.TransferSlotCoolTime(1, 41)    # no entry: nothing
        proxy.TransferSlotCoolTime(41, 99)   # the window lacks 99: nothing
        self.assertEqual(list(proxy.stored(1)), [41])


class PressedButton(SlotsTest):
    def test_a_plus_button_sends_its_slot_and_nothing_while_attached(self):
        pressed = []
        proxy = self.m.FullSlotWindowProxy([1, 21, 41], None, limits=_Limits("p"))
        proxy.SetPressedSlotButtonEvent(pressed.append)
        events = self.m.LegacySlotEvents(proxy)
        events.pressed_button(1)
        events.pressed_button(7)
        self.assertEqual(pressed, [21])
        self.game.give(0, 27001, 1)
        self.controller.AttachObject("legacy", INVENTORY, 0, 27001)
        events.pressed_button(0)
        self.assertEqual(pressed, [21], "CSlotButton ignores a press while attaching")

    def test_attach_right_is_on_since_f2(self):
        self.assertIs(self.m.ATTACH_RIGHT, True)


class Adopt(SlotsTest):
    """adopt_attach (P15 spec 7): a legacy handler's attach from a NovaUI
    press, of a type DeattachObject leaves unfreed."""

    def setUp(self):
        SlotsTest.setUp(self)
        game = self.game
        self.ds = (P["DRAGON_SOUL_INVENTORY"], 4)
        game.give(self.ds, 110000, 1)
        game.give(0, 27001, 1)
        game.learn(3, 3, level=1)
        game.put_quick(0, INVENTORY, 0)
        game.put_quick(1, SKILL, 3)

    def legacy_attach(self, slot_type, number, index):
        self.controller.AttachObject("legacy", slot_type, number, index)

    # The adoption frees what legacy's DeattachObject leaves on a client
    # without P15 item 4's legacy fix; with it (LeakFree) nothing is adopted.

    def test_a_dragon_soul_or_quick_slot_attach_is_freed_once_at_its_end(self):
        without_the_legacy_fix(self)
        for slot_type, number, index, ends in ((DRAGON_SOUL, 4, 110000, "detach"), (QUICK, 0, 0, "detach"),
                                               (QUICK, 1, 1, "detach"), (DRAGON_SOUL, 4, 110000, "replace")):
            made_before, freed_before = len(self.game.created), len(self.game.deleted)
            self.legacy_attach(slot_type, number, index)
            self.assertTrue(self.m.adopt_attach())
            self.assertFalse(self.m.adopt_attach(), "adopted once")
            if ends == "replace":
                self.legacy_attach(INVENTORY, 0, 27001)   # legacy attaches again without a detach
            self.controller.DeattachObject()
            made = self.game.created[made_before:]
            freed = self.game.deleted[freed_before:]
            self.assertEqual(sorted(freed), sorted(made), (slot_type, number, ends))
            self.assertNotIn("DeattachObject", self.controller.__dict__)
            self.controller.DeattachObject()
            self.assertEqual(self.game.deleted[freed_before:], freed, "never twice")

    def test_types_the_class_method_frees_and_attach_s_own_are_not_adopted(self):
        without_the_legacy_fix(self)
        self.legacy_attach(INVENTORY, 0, 27001)
        self.assertFalse(self.m.adopt_attach())
        self.controller.DeattachObject()
        self.m.attach("owner", QUICK, 0, 0)
        self.assertFalse(self.m.adopt_attach(), "attach()'s own shadow frees it")
        self.controller.DeattachObject()
        made, freed = self.icons()
        self.assertEqual(sorted(made), sorted(freed))
        self.assertFalse(self.m.adopt_attach(), "nothing attached")

    def test_with_the_attach_watch_before_and_after(self):
        without_the_legacy_fix(self)
        cleared = []
        self.m._with_states.add(type("Events", (object,), {"clear_states": lambda self: cleared.append(1)})())
        self.legacy_attach(DRAGON_SOUL, 4, 110000)
        self.m.watch_attach()
        self.assertTrue(self.m.adopt_attach(), "the watch's shadow is adopted around")
        self.assertTrue(self.m.watch_attach(), "watched already, through the adoption")
        self.controller.DeattachObject()
        self.assertEqual(cleared, [1])
        made, freed = self.icons()
        self.assertEqual(sorted(made), sorted(freed))
        self.assertNotIn("DeattachObject", self.controller.__dict__)
        self.m._with_states.clear()


class FullProxyPush(SlotsTest):
    def test_a_change_without_refresh_slot_marks_it_dirty_and_push_hands_the_cells_over(self):
        seen = []
        proxy = self.m.FullSlotWindowProxy([1, 21], seen.append, limits=_Limits("p"))
        self.assertTrue(proxy.dirty, "the first push gives the window its cells")
        proxy.push()
        self.assertFalse(proxy.dirty)
        self.assertEqual(len(seen), 1)
        proxy.SetSkillSlotNew(1, 5, 0, 1)
        proxy.ActivateSlot(1)
        self.assertTrue(proxy.dirty)
        proxy.push()
        self.assertEqual((seen[-1][0]["kind"], seen[-1][0]["active"]), ("skill", True))
        proxy.StoreSlotCoolTime(1, 1, 5.0)
        self.assertFalse(proxy.dirty, "a store shows nothing until a restore")
        proxy.HideAllSlotButton()
        self.assertTrue(proxy.dirty)
        proxy.RefreshSlot()
        self.assertFalse(proxy.dirty, "RefreshSlot hands the cells over too")


class AttachRightBinding(unittest.TestCase):
    """F-2's preparation (P15 spec 8.2, D16): every window whose cells reach
    legacy handlers through LegacySlotEvents binds
    data-class-nui-attach-right="attach_right" on an ancestor of each cell
    that takes a press, and every fixture of its document carries the
    switch's value, so F-2's one commit (ATTACH_RIGHT) changes every grid
    at once and reverting it restores 3b's behavior."""

    ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "root"))

    # P17 merge: the Wave 4 grids, which do not bind the class (the equipment
    # view's cells take no press at all). F-2 for them is open (P16's merge
    # note: legacy's right press differs per grid), so the host still cancels
    # an attach at their right press, as validated.
    F2_OPEN = ("windows/equipment-view/equipment-view.rml", "windows/exchange/exchange.rml", "windows/guild/guild.rml",
               "windows/mall/mall.rml", "windows/private-shop/private-shop.rml", "windows/safebox/safebox.rml",
               "windows/shop/shop.rml")

    def windows(self, f2_open=False):
        """{document path: controller} of the controllers that make a
        LegacySlotEvents; F2_OPEN's documents only with f2_open."""
        import re
        found = {}
        for name in sorted(os.listdir(self.ROOT)):
            if not (name.startswith("nui_") and name.endswith(".py")) or name == "nui_slots.py":
                continue
            source = _read(os.path.join(self.ROOT, name))
            if "LegacySlotEvents(" not in source:
                continue
            for document in re.findall(r'DOCUMENT = "nui/(windows/[a-z0-9-]+/[a-z0-9-]+\.rml)"', source):
                if (document in self.F2_OPEN) == f2_open:
                    found[os.path.join(NUI, document)] = name
        return found

    def test_the_f2_open_grids_are_legacy_slot_events_windows_without_the_binding(self):
        windows = self.windows(f2_open=True)
        self.assertEqual(sorted(os.path.relpath(document, NUI) for document in windows), sorted(self.F2_OPEN))
        for document, controller in windows.items():
            cells, missing = self.unbound_cells(_read(document))
            with self.subTest(document=os.path.relpath(document, NUI)):
                self.assertEqual(len(missing), cells, "binding one means F-2 was decided: move it out of F2_OPEN")

    @staticmethod
    def unbound_cells(text):
        """The pressable nui-slot cells with no ancestor binding the class."""
        import html.parser

        class Walk(html.parser.HTMLParser):
            VOID = {"img", "input", "br"}

            def __init__(self):
                html.parser.HTMLParser.__init__(self)
                self.stack, self.missing, self.cells = [], [], 0

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                bound = 'attach_right' == attrs.get("data-class-nui-attach-right")
                classes = (attrs.get("class") or "").split()
                if "nui-slot" in classes and attrs.get("data-event-mousedown"):
                    self.cells += 1
                    if not any(self.stack):
                        self.missing.append(attrs.get("data-attr-id") or attrs.get("id") or tag)
                if tag not in self.VOID:
                    self.stack.append(bound)

            def handle_startendtag(self, tag, attrs):
                if tag not in self.VOID:
                    self.handle_starttag(tag, attrs)
                    self.stack.pop()
                else:
                    self.handle_starttag(tag, attrs)

            def handle_endtag(self, tag):
                if tag not in self.VOID and self.stack:
                    self.stack.pop()

        walk = Walk()
        walk.feed(text)
        return walk.cells, walk.missing

    def test_every_legacy_slot_events_cell_lies_inside_the_binding(self):
        windows = self.windows()
        self.assertGreaterEqual(len(windows), 4, windows)
        for document, controller in windows.items():
            cells, missing = self.unbound_cells(_read(document))
            with self.subTest(document=os.path.relpath(document, NUI)):
                self.assertGreater(cells, 0, controller)
                self.assertEqual(missing, [])

    def test_every_fixture_carries_the_switch_s_value(self):
        switch = support.Game().load_standard().loaded["nui_slots"].ATTACH_RIGHT
        for document in self.windows():
            folder = os.path.dirname(document)
            for name in sorted(os.listdir(folder)):
                if not name.endswith(".fixture.json"):
                    continue
                with open(os.path.join(folder, name), encoding="utf-8") as handle:
                    models = json.load(handle)
                for model in models.values():
                    with self.subTest(fixture=name):
                        self.assertIs(model.get("attach_right"), switch)


class AttachRight(SlotsTest):
    """P15 F-2 (spec 8.2): a right press while something is attached sends
    the unselect event of the slot CSlotWindow picks
    (OnMouseRightButtonDown: GetPickedSlotPointer, a grid's by the attached
    footprint, as for a left press) while nui_slots.ATTACH_RIGHT holds;
    without it nothing (the host canceled the attach). The grid of Events."""

    setUp = Events.setUp

    def test_with_the_switch_off_a_right_press_while_attached_sends_nothing(self):
        self.m.ATTACH_RIGHT = False
        self.addCleanup(setattr, self.m, "ATTACH_RIGHT", True)
        self.controller.AttachObject("legacy", INVENTORY, 30, 27001, 1)
        self.events.press(3, 1)
        self.events.press(9, 1)
        self.assertEqual(self.calls, [])

    def test_the_unselect_event_of_the_item_or_the_empty_cell_under_a_one_cell_attach(self):
        self.controller.AttachObject("legacy", INVENTORY, 30, 27001, 1)
        self.events.press(3, 1)
        self.events.press(9, 1)
        self.events.press(2, 1)
        self.assertEqual(self.calls, [("unselect_item", 3), ("unselect_empty", 9), ("unselect_item", 2)])

    def test_a_grid_picks_by_the_attached_footprint_as_for_a_left_press(self):
        self.controller.AttachObject("legacy", INVENTORY, 30, 10, 1)   # a 1x2 sword from elsewhere
        self.game.item_sizes[10] = (1, 2)
        self.events.press(12, 1)   # rows 2..3 do not fit: the footprint moves up to 7 and 12
        self.assertEqual(self.calls, [("unselect_empty", 7)])

    def test_the_footprint_states_follow_the_attach_the_handler_dropped(self):
        self.proxy.SetUnselectItemSlotEvent(lambda n: (self.calls.append(("unselect_item", n)),
                                                       self.controller.DeattachObject()))
        self.controller.AttachObject("legacy", INVENTORY, 30, 27001, 1)
        self.events.over(2)
        self.assertTrue(self.seen_states[-1][0], "a footprint while attached")
        self.events.press(2, 1)
        self.assertEqual(self.calls[-1], ("unselect_item", 2))
        self.assertEqual(self.seen_states[-1], ({}, -1), "the attach's end cleared it")


class LeakFree(SlotsTest):
    """P15 item 4: with mousemodule.DEATTACH_FREES_EVERY_ICON (the legacy
    fix) DeattachObject frees the dragon soul and quick slot icons
    AttachObject makes, whoever attached them, and NovaUI frees nothing
    more (nui_slots._leaked_kind answers None), so each icon instance is
    freed exactly once. The three free calls are all
    CGraphicImageInstance::Delete, so the handles are compared."""

    def setUp(self):
        SlotsTest.setUp(self)
        game = self.game
        game.give((P["DRAGON_SOUL_INVENTORY"], 4), 110000, 1)
        game.give(0, 27001, 1)
        game.learn(3, 3, level=1)
        game.put_quick(0, INVENTORY, 0)
        game.put_quick(1, SKILL, 3)
        game.put_quick(2, EMOTION, 11)
        self.cases = ((DRAGON_SOUL, 4, 110000), (QUICK, 0, 0), (QUICK, 1, 1), (QUICK, 2, 2))

    def handles(self, since):
        made = [handle for _, handle in self.game.created[since[0]:]]
        freed = [handle for _, handle in self.game.deleted[since[1]:]]
        return made, freed

    def mark(self):
        return len(self.game.created), len(self.game.deleted)

    def test_the_flag_is_set_and_novaui_adopts_nothing(self):
        self.assertIs(self.game.loaded["mouseModule"].DEATTACH_FREES_EVERY_ICON, True)
        for slot_type, number, index in self.cases:
            self.assertIsNone(self.m._leaked_kind(slot_type, number))
            self.controller.AttachObject("legacy", slot_type, number, index)
            self.assertFalse(self.m.adopt_attach(), "the class method frees it")
            self.controller.DeattachObject()

    def test_a_legacy_window_s_own_attach_is_freed_once_by_the_class_method(self):
        for slot_type, number, index in self.cases:
            since = self.mark()
            self.controller.AttachObject("legacy", slot_type, number, index)
            self.controller.DeattachObject()
            self.controller.DeattachObject()
            made, freed = self.handles(since)
            self.assertEqual(len(made), 1, slot_type)
            self.assertEqual(freed, made, "type %d: freed exactly once" % slot_type)

    def test_attach_s_own_and_an_adopted_press_are_freed_once_at_the_end_a_replacing_attach_and_a_cancel(self):
        for slot_type, number, index in self.cases:
            since = self.mark()
            self.assertTrue(self.m.attach("owner", slot_type, number, index))
            self.assertTrue(self.m.attach("owner", slot_type, number, index), "a replacing attach detaches first")
            self.controller.DeattachObject()   # a right-press cancel, Escape, a drop: DeattachObject
            made, freed = self.handles(since)
            self.assertEqual(len(made), 2)
            self.assertEqual(sorted(freed), sorted(made), "type %d: each freed once" % slot_type)
            since = self.mark()
            self.controller.AttachObject("legacy", slot_type, number, index)
            self.m.adopt_attach()
            self.controller.DeattachObject()
            made, freed = self.handles(since)
            self.assertEqual(freed, made, "type %d: a legacy handler's attach from a NovaUI press" % slot_type)

    def test_without_the_legacy_fix_a_second_press_that_keeps_the_attach_adopts_nothing_twice(self):
        """Review R-2: every press that picks runs watch_attach, and the
        dragon soul board runs adopt_attach after each press; a later press
        that keeps the attach (a right press on an empty cell, a refused
        drop) must not adopt it again, or the handle is freed twice."""
        without_the_legacy_fix(self)
        for slot_type, number, index in self.cases:
            since = self.mark()
            self.controller.AttachObject("legacy", slot_type, number, index)
            self.m.watch_attach()
            self.assertTrue(self.m.adopt_attach())
            self.m.watch_attach()
            self.assertFalse(self.m.adopt_attach(), "adopted already")
            self.assertTrue(self.m.watch_attach())
            self.assertFalse(self.m.adopt_attach())
            self.controller.DeattachObject()
            made, freed = self.handles(since)
            self.assertEqual(len(made), 1, slot_type)
            self.assertEqual(freed, made, "type %d: freed exactly once" % slot_type)

    def test_without_the_legacy_fix_attach_s_own_watched_shadow_is_not_adopted(self):
        """Review R-2: a watch over attach()'s freeing shadow carries what
        that shadow frees, so adopt_attach leaves it."""
        without_the_legacy_fix(self)
        for slot_type, number, index in self.cases:
            since = self.mark()
            self.assertTrue(self.m.attach("taskbar", slot_type, number, index))
            self.m.watch_attach()
            self.assertFalse(self.m.adopt_attach(), "attach() frees it")
            self.controller.DeattachObject()
            made, freed = self.handles(since)
            self.assertEqual(freed, made, "type %d: freed exactly once" % slot_type)

    def test_without_the_legacy_fix_an_attach_that_replaced_attach_s_own_is_adopted_and_both_freed_once(self):
        """attach()'s shadow frees its own handle when a later AttachObject
        replaced it without a detach; the new handle is a different one, so
        adopt_attach still takes it."""
        without_the_legacy_fix(self)
        since = self.mark()
        self.assertTrue(self.m.attach("taskbar", QUICK, 0, 0))
        self.controller.AttachObject("legacy", DRAGON_SOUL, 4, 110000)
        self.m.watch_attach()
        self.assertTrue(self.m.adopt_attach())
        self.assertFalse(self.m.adopt_attach())
        self.controller.DeattachObject()
        made, freed = self.handles(since)
        self.assertEqual(len(made), 2)
        self.assertEqual(sorted(freed), sorted(made), "each freed once")

