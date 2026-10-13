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
        self.assertEqual(len(self.calls), 3, "the host canceled the attach; nothing is unselected")
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

if __name__ == "__main__":
    unittest.main()
