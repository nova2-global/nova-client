"""Tests for the NovaUI tooltips (P14 spec 5): the recorder
(assets/root/nui_tooltip.py), the item, skill and link facades
(nui_item_tooltip.py, nui_skill_tooltip.py, nui_link_tooltip.py) and their
documents: python3 -B -m unittest nui_tooltip_test (from tools/).

Plain CPython over nui_game_support's stand-ins, run by the harness of
nui_tooltip_corpus.py: a legacy world (uitooltip.py alone, its widgets the
stand-ins') and a NovaUI world (the recorder and the facades).
- Parity (spec 5.8): for every case of tools/fixtures/tooltip_corpus.json, in
  every context, the published model holds the same lines in the same order
  as the legacy tooltip shows (text, color, alignment, outline; images;
  dividers), a rule that raises raises the same in both, no case publishes
  more than once, and the positional socket rule agrees with the marker.
- The coverage gate: every live rule line of tools/fixtures/tooltip_branches.json
  runs over the corpus.
- The recorder: the proxy module, the widgets' names and bookkeeping, the
  role table, runs, gaps, time lines, transactions, show and hide, placement,
  the phase end, make()'s protocol.
- The documents: the shared block in every document that holds it, the
  roles' rules and tokens, the fixtures against the models."""
import inspect
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_test_support  # noqa: E402
import nui_tooltip_corpus as corpus_tool  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
NUI = os.path.join(REPO, "assets", "nui", "nui")
WINDOWS = os.path.join(NUI, "windows")
TIP_DOCUMENTS = ("item-tooltip", "skill-tooltip", "link-tooltip")
DIALOG_DOCUMENTS = (("refine", ("",)), ("attach-metin", ("old_", "new_")))
FACADES = (("nui_item_tooltip", "ItemToolTip", "ItemToolTip"), ("nui_skill_tooltip", "SkillToolTip", "SkillToolTip"),
           ("nui_link_tooltip", "HyperlinkItemToolTip", "HyperlinkItemToolTip"))
SWORD = {"name": "Sword+0", "type": 1, "subtype": 0, "size": [1, 2], "antiflags": 0, "flags": 0, "wear": 16,
         "limits": [[1, 0], [0, 0]], "applies": [["APPLY_ATT_SPEED", 22]], "values": [0, 0, 15, 19, 13, 15],
         "price": {"buy": 100, "sell": 20}, "desc": "", "summary": "", "icon": "icon/item/00010.tga"}
STONE = {"name": "Stone of Penetration+0", "type": 10, "subtype": 0, "applies": [["APPLY_PENETRATE_PCT", 1]], "wear": 16,
         "icon": "icon/item/28000.tga", "limits": [[0, 0], [0, 0]], "values": [0] * 6}
TIMED = {"name": "Golden Cog Wheel", "type": 18, "subtype": 0, "limits": [[7, 300], [0, 0]], "values": [0] * 6,
         "icon": "icon/item/30329.tga"}
SMALL = {"items": {"10": SWORD, "28030": STONE, "30329": TIMED}, "skills": {}, "mobs": {}}


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


_CORPUS = []


def corpus():
    if not _CORPUS:
        _CORPUS.append(corpus_tool.load_corpus())
    return _CORPUS[0]


class Parity(unittest.TestCase):
    """Spec 5.8: the corpus, every case, both sides."""

    @classmethod
    def setUpClass(cls):
        run = corpus_tool.ParityRun(corpus())
        cls.novaui = run.novaui
        cls.results = [result[:5] for result in run.results]

    def test_the_corpus_covers_every_context_and_kind(self):
        contexts = set(case["context"] for case in corpus()["cases"])
        for context in corpus_tool.ITEM_CONTEXTS + corpus_tool.SKILL_CONTEXTS + ("calls",):
            self.assertIn(context, contexts)
        types = set(row["type_name"] for row in corpus()["items"].values())
        for kind in ("WEAPON", "ARMOR", "USE", "METIN", "COSTUME", "BELT", "DS", "UNIQUE", "QUEST", "RING", "BLEND",
                     "ROD", "PICK", "LOTTERY", "FISH", "SKILLBOOK", "SKILLFORGET", "POLYMORPH"):
            self.assertIn(kind, types)

    def test_every_case_shows_the_same_lines_in_the_same_order_as_legacy(self):
        differences = []
        for case, legacy, novaui, publishes, positional in self.results:
            if legacy != novaui:
                differences.append((case["id"], legacy[1], novaui[1]))
        self.assertEqual(differences, [], "cases differ: %s" % differences[:5])

    def test_the_comparison_is_not_empty(self):
        shown = sum(1 for case, legacy, novaui, publishes, positional in self.results for rows in novaui[0] if rows)
        rows = sum(len(rows) for case, legacy, novaui, publishes, positional in self.results for rows in novaui[0])
        self.assertGreater(shown, 1000)
        self.assertGreater(rows, 6000)

    def test_a_hover_call_publishes_at_most_once(self):
        many = [(case["id"], publishes) for case, legacy, novaui, publishes, positional in self.results if publishes > 1]
        self.assertEqual(many, [])

    def test_the_positional_socket_rule_agrees_with_the_marker(self):
        bad = [case["id"] for case, legacy, novaui, publishes, positional in self.results if not all(positional)]
        self.assertEqual(bad, [])

    def test_a_rule_that_raises_raises_the_same_and_only_where_legacy_does(self):
        """Two legacy bugs, inherited unchanged (both sides raise, and the
        facade shows what the rules built before the raise, as legacy's board
        does): MONETARY_UNIT_JUN is in no locale_game.txt, so every secondary
        coin shop tooltip raises (localeinfo.py NumberToSecondaryCoinString);
        TOOLTIP_NEXT_SKILL_LEVEL_3 is in none either, so the next level of
        skills 141 and 142 raises (uitooltip.py AppendSkillDataNew)."""
        raised = [(case["id"], legacy[1]) for case, legacy, novaui, publishes, positional in self.results if legacy[1]]
        unexplained = [(case_id, error) for case_id, error in raised
                       if not (case_id.startswith("SetShopItemBySecondaryCoin-") and "MONETARY_UNIT_JUN" in error[1])
                       and not (re.match(r"skill-14[12]-", case_id))]
        self.assertEqual(unexplained, [])
        self.assertTrue(any(case_id.startswith("SetShopItemBySecondaryCoin-") for case_id, error in raised))

    def test_no_build_failed_and_every_widget_was_recorded(self):
        stats = self.novaui.m("nui_tooltip").STATS
        self.assertEqual(stats["errors"], 0)
        self.assertEqual(stats["unrecorded"], 0)

    def test_every_gap_is_a_step_of_5_up_to_40(self):
        self.assertEqual(self.novaui.m("nui_tooltip").GAP_VALUES, {})


class CoverageGate(unittest.TestCase):
    """Spec 5.8: every live rule line of uitooltip.py runs over the corpus."""

    def test_the_branch_list_is_current(self):
        branches = json.loads(read(corpus_tool.BRANCHES))
        self.assertEqual(branches["uitooltip_sha256"], corpus_tool.sha256_of(corpus_tool.RULES),
                         "uitooltip.py changed: python3 tools/nui_tooltip_corpus.py corpus")
        self.assertEqual(branches, json.loads(corpus_tool._text(corpus_tool.branch_list())))

    def test_every_exclusion_has_a_reason(self):
        branches = json.loads(read(corpus_tool.BRANCHES))
        for line, why in branches["excluded"].items():
            self.assertRegex(why, r"\w+: \w", line)

    def test_every_live_rule_line_runs(self):
        branches = json.loads(read(corpus_tool.BRANCHES))
        live = set(int(line) for line in branches["lines"])
        hit = corpus_tool.trace_rules(corpus_tool.TipWorld(corpus(), recorder=False), corpus()["cases"])
        missing = sorted(live - hit)
        self.assertEqual(missing, [], "rule lines no case runs: %s" % missing[:20])

    def test_the_corpus_is_current_where_the_server_files_are(self):
        if not os.path.isfile(corpus_tool.DEFAULT_PROTO):
            self.skipTest("the server's item proto is not on this machine")
        self.assertEqual(json.loads(corpus_tool._text(corpus_tool.build_corpus())), corpus())


class World(object):
    """A small world for the recorder's unit tests."""

    def __init__(self, data=SMALL, recorder=True, engine_3b=True):
        self.tip_world = corpus_tool.TipWorld(data, recorder=recorder)
        self.game = self.tip_world.game
        if not engine_3b:
            self.game.engine_3b = False
            self.game.modules["nui"]._nui.FollowPointer = None
            self.game.state.decorators.discard("nui-cells")

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def m(self, name):
        return self.game.loaded[name]

    @property
    def rec(self):
        return self.m("nui_tooltip")

    def item(self):
        return self.m("nui_item_tooltip").ItemToolTip()

    def case(self, **values):
        case = {"vnum": 10, "sockets": [0, 0, 0], "attrs": [], "player": {"level": 120, "race": 0}, "clock": 1700000000}
        case.update(values)
        support.apply_case(self.game, case)

    def board(self, kind="item"):
        return self.rec.board(kind)


def placed(board):
    """A tooltip board's placement without its target: (kind, once, reserve)."""
    p = board.placement
    return (p[0], p[1], p[3]) if p and p[0] == "tooltip" else p


class Recorder(unittest.TestCase):
    def test_the_rules_see_the_recording_widgets_and_every_other_name_the_real_ui(self):
        with World() as world:
            rec, tooltip = world.rec, world.m("uiToolTip")
            proxy = tooltip.ItemToolTip.AddItemData.__globals__["ui"]
            self.assertIsInstance(proxy, rec._UiProxy)
            real = proxy._nui_real
            self.assertIs(proxy.ThinBoard, real.ThinBoard)
            for name in ("TextLine", "ImageBox", "Line"):
                cls = getattr(proxy, name)
                self.assertEqual(cls.__name__, name, "the rules compare the class name (MR-10)")
                self.assertTrue(issubclass(cls, getattr(real, name)))
            rec.uninstall()
            self.assertIs(tooltip.ItemToolTip.AddItemData.__globals__["ui"], real)
            rec.install()
            rec.install()
            self.assertIsInstance(tooltip.ItemToolTip.AddItemData.__globals__["ui"], rec._UiProxy)

    def test_a_recording_line_keeps_what_it_was_told_and_its_owner(self):
        with World() as world:
            rec = world.rec
            tip = world.item()
            line = rec._installed[0]["ui"].TextLine()
            line.SetParent(tip)
            version = tip._rec_version
            line.SetText("Sword+0")
            line.SetPackedFontColor(support.generate_color(0.9490, 0.9058, 0.7568, 1.0))
            line.SetOutline()
            line.SetHorizontalAlignCenter()
            line.Show()
            self.assertEqual((line._rec_text, line._rec_color, line._rec_outline, line._rec_align, line._rec_shown),
                             ("Sword+0", 0xFFF1E6C0, True, "center", True))
            self.assertEqual(tip._rec_version, version + 5)
            line.SetText("Sword+0")
            self.assertEqual(tip._rec_version, version + 5, "no change, no new version")
            self.assertEqual(line.text, "Sword+0", "the legacy widget got the call too")

    def test_the_role_table_takes_the_first_name_of_each_value_unsigned(self):
        with World() as world:
            rec, tooltip = world.rec, world.m("uiToolTip")
            self.assertEqual(rec.ROLE_OF_COLOR[tooltip.ToolTip.NORMAL_COLOR & 0xFFFFFFFF], "normal")
            self.assertEqual(rec.ROLE_OF_COLOR[tooltip.ToolTip.DISABLE_COLOR & 0xFFFFFFFF], "negative")
            self.assertEqual(rec.ROLE_OF_COLOR[tooltip.ToolTip.HIGH_PRICE_COLOR & 0xFFFFFFFF], "special")
            self.assertEqual(rec.ROLE_OF_COLOR[0xFFBEB47D], "condition")
            self.assertLess(tooltip.ToolTip.TITLE_COLOR, 0, "GenerateColor answers a signed long")
            self.assertEqual(rec.role_of(tooltip.ToolTip.TITLE_COLOR), ("title", ""))
            self.assertEqual(rec.role_of(0xFFDDDDDD), ("custom", "#ddddddff"))
            self.assertEqual(set(rec.COLOR_OF_ROLE), set(rec.ROLES) - {"custom"})
            self.assertEqual(rec.UNMAPPED_COLORS, [])

    def test_a_constant_the_cut_adds_without_a_role_is_a_custom_run_and_listed(self):
        with World() as world:
            rec, tooltip = world.rec, world.m("uiToolTip")
            tooltip.ToolTip.SOCKET4_COLOR = 0xFF123456
            try:
                by_color, by_role, unmapped = rec.role_table()
            finally:
                del tooltip.ToolTip.SOCKET4_COLOR
            self.assertNotIn(0xFF123456, by_color)
            self.assertEqual(unmapped, ["SOCKET4_COLOR"])

    def test_text_with_legacy_tags_is_one_tags_run_else_plain_text(self):
        with World() as world:
            rec = world.rec
            plain = rec.text_runs("Attack Speed +22% @ui.OK", 0xFFC1C1C1)
            self.assertEqual(plain, [{"k": "text", "text": "Attack Speed +22% @⁠ui.OK", "role": "normal",
                                      "color": "", "end": 0.0}])
            tagged = rec.text_runs("|cffff0000Red|r", 0xFF89B88D)
            self.assertEqual(tagged[0]["k"], "tags")
            self.assertEqual(tagged[0]["text"], "|cffff0000Red|r")
            self.assertEqual(rec.text_runs("a|b", 0xFFC1C1C1)[0]["k"], "text", "a lone | is plain")
            self.assertEqual(rec.text_runs("a||b", 0xFFC1C1C1)[0]["k"], "tags", "|| draws one |")

    def test_gaps_are_steps_of_5_from_0_to_40_and_others_are_noted(self):
        with World() as world:
            rec = world.rec
            self.assertEqual([rec._gap(v) for v in (0, 5, 10, 40)], [0, 5, 10, 40])
            self.assertEqual(rec.GAP_VALUES, {})
            self.assertEqual([rec._gap(v) for v in (7, 8, 55, -3)], [5, 10, 40, 0])
            self.assertEqual(sorted(rec.GAP_VALUES), [-3, 7, 8, 55])

    def test_a_remaining_time_is_a_prefix_and_a_countdown_on_the_novaui_clock(self):
        with World() as world:
            world.game.state.now = 50.0
            world.case(vnum=30329, sockets=[1700000000 + 3661, 0, 0])
            tip = world.item()
            tip.SetInventoryItem(0)
            line = [e for e in world.board().model["lines"] if any(r["k"] == "count" for r in e["runs"])][0]
            text, count = line["runs"]
            self.assertEqual(text["text"], "Time Remaining: ")
            self.assertEqual(count["end"], 50.0 + 3661)
            self.assertEqual(count["role"], text["role"])

    def test_a_shop_items_time_line_stays_empty(self):
        with World() as world:
            world.case(vnum=30329, sockets=[1700000000 + 300, 0, 0], shop={"open": True, "private": False, "price": 5})
            tip = world.item()
            tip.SetShopItem(0)
            lines = world.board().model["lines"]
            self.assertFalse(any(r["k"] == "count" for e in lines for r in e["runs"]))
            self.assertIn([""], [[r["text"] for r in e["runs"]] for e in lines])

    def test_a_socket_row_is_one_entry_with_its_frame_icon_and_lines(self):
        with World() as world:
            world.case(sockets=[28030, 1, 2])
            world.item().SetInventoryItem(0)
            sockets = [e for e in world.board().model["lines"] if e["t"] == "socket"]
            self.assertEqual([(e["frame"], e["icon"]) for e in sockets],
                             [("silver", "/icon/item/28000.tga"), ("silver", ""), ("gold", "")])
            self.assertEqual([[r["text"] for s in e["sub"] for r in s["runs"]] for e in sockets],
                             [["Stone of Penetration+0", "1% Chance for piercing Hits"], ["Empty"], ["Empty"]])
            self.assertTrue(all(s["align"] == "left" for e in sockets for s in e["sub"]))


class Transactions(unittest.TestCase):
    def test_a_hover_builds_once_with_the_lines_added_after_the_show(self):
        with World() as world:
            world.case(shop={"open": True, "private": False, "price": 1234})
            rec = world.rec
            tip = world.item()
            builds, publishes = rec.STATS["builds"], rec.STATS["publishes"]
            tip.SetShopItem(0)
            self.assertEqual((rec.STATS["builds"] - builds, rec.STATS["publishes"] - publishes), (1, 1))
            texts = [r["text"] for e in world.board().model["lines"] for r in e["runs"]]
            self.assertEqual(texts[-1], "Price: 1.234 Yang", "AppendPrice after AddItemData's ShowToolTip")

    def test_the_show_runs_legacys_on_update_once_and_shows_the_document_at_the_pointer(self):
        with World() as world:
            world.case()
            tip = world.item()
            calls = []
            on_update = world.m("uiToolTip").ToolTip.OnUpdate
            world.m("uiToolTip").ToolTip.OnUpdate = lambda self: (calls.append(1), on_update(self))
            try:
                tip.SetInventoryItem(0)
            finally:
                world.m("uiToolTip").ToolTip.OnUpdate = on_update
            self.assertEqual(len(calls), 1)
            board = world.board()
            self.assertTrue(board.visible)
            self.assertTrue(tip.IsShow())
            self.assertEqual(placed(board), ("tooltip", False, 37),
                             "legacy's rule in pixels, clear of the legacy taskbar, the one in use without a NovaUI one")
            self.assertIsInstance(board.placement[2], int)
            self.assertNotEqual(board.placement[2], 0, "a target, so a refresh keeps the side (P14c)")
            self.assertGreaterEqual(board.front, 1)
            self.assertFalse(world.m("uiToolTip").ToolTip.IsShow(tip), "the legacy board never shows")

    def test_hide_empties_the_document_and_a_later_show_builds_again(self):
        with World() as world:
            world.case()
            tip = world.item()
            tip.SetInventoryItem(0)
            tip.HideToolTip()
            board = world.board()
            self.assertFalse(board.visible)
            self.assertEqual(board.model["lines"], [])
            self.assertFalse(tip.IsShow())
            tip.Show()
            self.assertTrue(board.visible)
            self.assertEqual(board.model["lines"][0]["runs"][0]["text"], "Sword+0")

    def test_a_change_to_a_shown_tooltip_publishes_and_clear_empties_it(self):
        with World() as world:
            world.case()
            tip = world.item()
            tip.SetInventoryItem(0)
            count = len(world.board().model["lines"])
            tip.AppendTextLine("Keeps bonuses and stones", tip.POSITIVE_COLOR)
            self.assertEqual(len(world.board().model["lines"]), count + 1)
            tip.ClearToolTip()
            self.assertEqual(world.board().model["lines"], [])

    def test_the_tooltips_keep_clear_of_the_legacy_taskbar_only_while_it_is_the_one_in_use(self):
        """The legacy taskbar is a TOP_MOST window of 37 px at the screen's
        bottom and the tooltips draw below that layer (P14 spec 5.5.7); the
        NovaUI taskbar draws below them."""
        for scale, taskbar, reserve in ((1.0, False, 37), (2.0, False, 37), (1.0, True, 0)):
            with World() as world:
                world.case()
                world.game.state.scale = scale
                hud = world.m("nui_hud")
                bar = object()
                if taskbar:
                    hud.take_over("taskbar", bar)
                tip = world.item()
                tip.SetInventoryItem(0)
                with self.subTest(scale=scale, taskbar=taskbar):
                    self.assertEqual(placed(world.board()), ("tooltip", False, reserve), "the bar's pixels at every scale")
                hud.forget("taskbar", bar)

    def test_a_fixed_point_places_the_bottom_center_10_px_below_it(self):
        with World() as world:
            world.case()
            tip = world.item()
            tip.SetToolTipPosition(400, 300)
            tip.SetItemToolTip(10)
            self.assertEqual(world.board().placement, ("position", 400.0, 310.0, (0.5, 1.0)))
            tip.SetToolTipPosition(-1, -1)
            tip.SetItemToolTip(10)
            self.assertEqual(world.board().placement[0], "tooltip")

    def test_the_link_tooltip_is_placed_once_and_a_left_press_hides_it(self):
        with World() as world:
            link = world.m("nui_link_tooltip").HyperlinkItemToolTip()
            link.SetHyperlinkItem("item:a:0:1:0:0".split(":"))
            board = world.board("link")
            self.assertEqual(placed(board), ("tooltip", True, 37))
            self.assertTrue(link.IsShow())
            board.fire("tip_press", 1)
            self.assertTrue(link.IsShow(), "only the left button")
            board.fire("tip_press", 0)
            self.assertFalse(link.IsShow())

    def test_two_facades_of_one_kind_share_its_document(self):
        with World() as world:
            world.case()
            first, second = world.item(), world.item()
            first.SetItemToolTip(10)
            second.SetItemToolTip(30329)
            self.assertFalse(first.IsShow())
            self.assertTrue(second.IsShow())
            first.AppendTextLine("late", first.NORMAL_COLOR)
            self.assertEqual(world.board().model["lines"][0]["runs"][0]["text"], "Golden Cog Wheel",
                             "a facade that lost the document does not write over it")

    def test_the_documents_load_at_the_first_show_and_go_at_the_phase_end(self):
        with World() as world:
            world.case()
            rec = world.rec
            tips = [world.item(), world.m("nui_skill_tooltip").SkillToolTip(), world.m("nui_link_tooltip").HyperlinkItemToolTip()]
            self.assertEqual([rec.board(kind) for kind in ("item", "skill", "link")], [None, None, None])
            tips[0].SetItemToolTip(10)
            tips[2].SetHyperlinkItem("item:a:0:1:0:0".split(":"))
            tips[0].HideToolTip()
            self.assertIsNotNone(rec.board("item"), "kept, hidden and empty (D8)")
            self.assertEqual(rec.end_phase(), 2)
            self.assertEqual([rec.board(kind) for kind in ("item", "skill", "link")], [None, None, None])
            world.m("nui_windows")
            self.assertIn("nui_tooltip", world.m("nui_windows").PHASE_SCOPED)

    def test_no_build_runs_per_frame(self):
        with World() as world:
            for module, cls, legacy in FACADES:
                facade = getattr(world.m(module), cls)
                self.assertFalse(hasattr(facade, "OnRender"))
                source = inspect.getsource(world.rec.Facade.OnUpdate)
                self.assertNotIn("self.", source.split('"""')[-1], "OnUpdate does nothing")
            for name in ("nui_tooltip", "nui_item_tooltip", "nui_skill_tooltip", "nui_link_tooltip"):
                text = read(os.path.join(support.ROOT, name + ".py"))
                self.assertNotIn("def OnRender", text)
                self.assertEqual(text.count("def OnUpdate"), 1 if name == "nui_tooltip" else 0)


class TooltipSide(unittest.TestCase):
    """P14c: the item tooltip picks its side of the pointer once per hovered
    item, by legacy's rule (below while the pointer is more than 300 px above
    the screen's bottom, in pixels), and keeps it while the pointer stays on
    the item. A board's frame() is the runtime's update (nui_test_support,
    as NuiRuntime's kept side). The pointer path is HVS-Y's live one over the
    Soul Stealing Blade+9 at 62 (1x3; its area y 590 to 702 of a 900 px
    screen, so legacy's line at 600 crosses its top cell)."""

    UP = list(range(699, 591, -1))
    DOWN = list(range(593, 700))

    def world(self):
        world = World()
        world.case(pos=62)
        items = world.game.item_data.case["items"]
        items[63] = dict(items[62])  # its neighbor
        return world

    def test_a_pointer_path_up_over_a_straddling_1x3_item_and_back_keeps_one_side(self):
        with self.world() as world:
            tip = world.item()
            tip.SetInventoryItem(62)  # entered at its bottom, under the line
            board = world.board()
            sides = [board.frame(y) for y in self.UP + self.DOWN]
            self.assertEqual(set(sides), {"above"}, "legacy's rule at the show, then kept across the line at 600")
            self.assertEqual(sum(1 for c in board.calls if c[0] == "follow_pointer_as_tooltip"), 1)

    def test_entered_at_its_top_it_stays_below_all_the_way_down(self):
        with self.world() as world:
            tip = world.item()
            tip.SetInventoryItem(62)
            board = world.board()
            sides = [board.frame(y) for y in self.DOWN + list(reversed(self.DOWN))]
            self.assertEqual(set(sides), {"below"})

    def test_a_refresh_of_the_hovered_item_keeps_the_side(self):
        """The inventory's refresh while an item is hovered (refresh_hover, as
        CSlotWindow::RefreshSlot): its tooltip hidden and shown again within
        one frame, for the same item."""
        with self.world() as world:
            tip = world.item()
            tip.SetInventoryItem(62)
            board = world.board()
            for y in range(699, 640, -1):
                self.assertEqual(board.frame(y), "above")
            tip.HideToolTip()
            tip.SetInventoryItem(62)
            self.assertEqual([board.frame(y) for y in range(640, 591, -1)], ["above"] * 49,
                             "refreshed under the line, then moved over it: still above")

    def test_another_item_or_a_hide_chooses_the_side_again(self):
        with self.world() as world:
            tip = world.item()
            tip.SetInventoryItem(62)
            board = world.board()
            self.assertEqual(board.frame(699), "above")
            # Straight onto its neighbor: one hide and one show in one frame.
            tip.HideToolTip()
            tip.SetInventoryItem(63)
            self.assertEqual(board.frame(595), "below", "another item: legacy's rule at the pointer then")
            self.assertEqual(board.frame(650), "below")
            # Off every item for a frame, then back onto 62 at its top.
            tip.HideToolTip()
            self.assertIsNone(board.frame(580))
            tip.SetInventoryItem(62)
            self.assertEqual(set(board.frame(y) for y in self.DOWN), {"below"}, "the same item again after a hide")
            # A second facade showing the same call is another target.
            other = world.item()
            first = board.placement[2]
            other.SetInventoryItem(62)
            self.assertNotEqual(world.board().placement[2], first)

    def test_nui_py_asks_the_runtime_for_legacy_pixels_and_an_older_exe_gets_the_dp_rule(self):
        """assets/root/nui.py itself over a fake _nui: the nine arguments of
        P14c's FollowPointer (pixels and the kept side on, the target modulo
        2**64), and with an exe whose FollowPointer takes at most six,
        follow_pointer()'s dp rule with the reserve in dp."""
        import types
        calls = []
        fake = types.ModuleType("_nui")
        fake.IsAvailable = lambda: True
        fake.GetScale = lambda: 0.875

        def nine(doc, below, above, flip, once, reserve=0.0, pixels=False, keep=False, target=0):
            calls.append(("nine", doc, below, above, flip, once, reserve, pixels, keep, target))
            return True

        def six(doc, below, above, flip, once, reserve=0.0):
            calls.append(("six", doc, below, above, flip, once, reserve))
            return True
        modules = nui_test_support.Modules(_nui=fake)
        try:
            nui = modules.load("nui")
            window = nui.Window.__new__(nui.Window)
            window._doc = 5
            fake.FollowPointer = nine
            self.assertTrue(window.follow_pointer_as_tooltip(target=-1, bottom_reserve_px=37))
            self.assertTrue(window.follow_pointer_as_tooltip(once=True, target=7))
            fake.FollowPointer = six
            self.assertTrue(window.follow_pointer_as_tooltip(bottom_reserve_px=37))
            window._doc = 0
            self.assertFalse(window.follow_pointer_as_tooltip())
        finally:
            modules.restore()
        self.assertEqual(calls, [("nine", 5, 40.0, 20.0, 300.0, False, 37.0, True, True, 2 ** 64 - 1),
                                 ("nine", 5, 40.0, 20.0, 300.0, True, 0.0, True, True, 7),
                                 ("six", 5, 40.0, 20.0, 300.0, False, 37.0 / 0.875)])


class Facades(unittest.TestCase):
    """Spec 5.2.4: each facade has every legacy method with a signature the
    legacy callers can use, and make()'s protocol."""

    def test_every_legacy_method_exists_with_a_signature_callers_can_use(self):
        with World() as world:
            tooltip = world.m("uiToolTip")
            for module, cls, legacy_name in FACADES:
                facade, legacy = getattr(world.m(module), cls), getattr(tooltip, legacy_name)
                self.assertTrue(issubclass(facade, legacy))
                self.assertTrue(facade.NUI_FACADE)
                for name, member in inspect.getmembers(legacy, inspect.isfunction):
                    if name.startswith("__"):
                        continue
                    ours = getattr(facade, name)
                    wrapped = getattr(ours, "__wrapped__", ours)
                    theirs = inspect.signature(member)
                    mine = inspect.signature(wrapped)
                    if any(p.kind == p.VAR_POSITIONAL for p in mine.parameters.values()):
                        continue
                    self.assertEqual(len(mine.parameters), len(theirs.parameters), "%s.%s" % (cls, name))

    def test_make_builds_the_facades_with_the_flag_and_legacy_without_it_or_the_engine(self):
        for flags, engine, expected in (("+tooltips", True, True), ("", True, False), ("+tooltips", False, False)):
            with World(engine_3b=engine) as world:
                world.game.modules["systemSetting"].GetUINuiWindows = lambda f=flags: f
                windows, tooltip = world.m("nui_windows"), world.m("uiToolTip")
                made = [windows.make("tooltips", tooltip.HyperlinkItemToolTip, "nui_link_tooltip.HyperlinkItemToolTip"),
                        windows.make("tooltips", tooltip.ItemToolTip, "nui_item_tooltip.ItemToolTip"),
                        windows.make("tooltips", tooltip.SkillToolTip, "nui_skill_tooltip.SkillToolTip")]
                self.assertEqual([getattr(tip, "NUI_FACADE", False) for tip in made], [expected] * 3, flags)
                for tip in made:
                    tip.Hide()

    def test_the_interface_makes_the_three_tooltips_through_make(self):
        text = read(os.path.join(support.ROOT, "interfacemodule.py"))
        for module, cls, legacy in FACADES:
            self.assertIn('nui_windows.make("tooltips", uiToolTip.%s, "%s.%s")' % (legacy, module, cls), text)


class MarkupBlocksMatch(unittest.TestCase):
    """Spec 5.7: the block of item-tip.rcss's header in every document that
    shows tooltip lines, with its key prefix."""

    def test_every_document_holds_the_shared_block(self):
        for name in TIP_DOCUMENTS:
            text = read(os.path.join(WINDOWS, name, name + ".rml"))
            self.assertIn(re.sub(r"\s+", " ", block("", "tip-body")), re.sub(r"\s+", " ", text), name)
        for name, prefixes in DIALOG_DOCUMENTS:
            text = re.sub(r"\s+", " ", read(os.path.join(WINDOWS, name, name + ".rml")))
            ids = {"": "tip-body", "old_": "attach-old", "new_": "attach-new"}
            for prefix in prefixes:
                self.assertIn(re.sub(r"\s+", " ", block(prefix, ids[prefix])), text, "%s %s" % (name, prefix))


class Documents(unittest.TestCase):
    """Spec 5.7: the roles, the overlays, the fixtures."""

    def test_the_component_sheet_styles_every_role_with_its_token(self):
        sheet = read(os.path.join(NUI, "components", "item-tip.rcss"))
        tokens = read(os.path.join(NUI, "theme", "tokens.json"))
        cyber = read(os.path.join(NUI, "skins", "cyberpunk", "tokens.json"))
        for role in corpus_tool_roles():
            if role == "custom":
                self.assertIn(".nui-tip-role--custom { color: var(--tip-color, var(--tip-normal)); }", sheet)
                continue
            self.assertIn(".nui-tip-role--%s { color: var(--tip-%s); }" % (role, role), sheet)
            self.assertGreaterEqual(tokens.count('"tip-%s"' % role), 3, "dark, light and classic")
            self.assertIn('"tip-%s"' % role, cyber)

    def test_the_tooltip_bodies_take_no_pointer_but_the_link(self):
        for name in TIP_DOCUMENTS:
            text = read(os.path.join(WINDOWS, name, name + ".rml"))
            self.assertEqual("nui-tip--pickable" in text, name == "link-tooltip", name)
            self.assertIn("nui-board nui-board--tooltip nui-fx nui-tip", text)
            self.assertNotIn("nui-below-legacy-ui", text, "above the legacy UI layer (spec 5.5.6)")

    def test_every_document_with_the_block_links_the_component_sheet(self):
        for name in TIP_DOCUMENTS + tuple(name for name, prefixes in DIALOG_DOCUMENTS):
            text = read(os.path.join(WINDOWS, name, name + ".rml"))
            self.assertIn('<link type="text/rcss" href="../../components/item-tip.rcss"/>', text, name)

    def test_the_classic_overlays_share_the_tooltip_lines(self):
        start, end = "/* --- the tooltip lines", "/* --- end of the tooltip lines --- */"
        parts = {}
        for name in TIP_DOCUMENTS + tuple(name for name, prefixes in DIALOG_DOCUMENTS):
            text = read(os.path.join(NUI, "skins", "classic", "windows", name + ".rcss"))
            self.assertEqual((text.count(start), text.count(end)), (1, 1), name)
            parts[name] = text[text.index(start):text.index(end) + len(end)]
        self.assertEqual(len(set(parts.values())), 1, "the classic tooltip lines differ between overlays")
        self.assertIn(".skin-classic .nui-tip__socket-frame", parts["item-tooltip"])

    def test_the_tooltip_fixtures_are_current(self):
        with corpus_tool.quiet():
            models = corpus_tool.fixtures()
        written = 0
        for (window, variant), model in sorted(models.items()):
            if window not in TIP_DOCUMENTS:
                continue
            name = "%s.%s.fixture.json" % (window, variant) if variant else "%s.fixture.json" % window
            path = os.path.join(WINDOWS, window, name)
            self.assertEqual(json.loads(read(path)), json.loads(corpus_tool._text(model)),
                             "%s: python3 tools/nui_tooltip_corpus.py fixtures" % name)
            written += 1
        self.assertGreaterEqual(written, 10)


def corpus_tool_roles():
    with World() as world:
        return world.rec.ROLES


# The block every document holds (components/item-tip.rcss's header).
GAPS = range(5, 45, 5)


def _gaps(var):
    return " ".join('data-class-nui-tip--gap-%d="%s.gap == %d"' % (n, var, n) for n in GAPS)


def _runs(var):
    role = """data-attr-class="'nui-tip__run nui-tip-role--' + r.role" data-style---tip-color="r.color\""""
    return " ".join([
        '<span class="nui-tip__runslot" data-for="r : %s.runs">' % var,
        '<span class="nui-tip__run" data-if="r.k == \'text\'" %s>{{ r.text }}</span>' % role,
        '<nui-text class="nui-tip__run" data-if="r.k == \'tags\'" %s data-attr-value="r.text"/>' % role,
        '<nui-countdown class="nui-tip__run" data-if="r.k == \'count\'" %s' % role,
        'data-attr-end="r.end" day="@game.DAY" hour="@game.HOUR" minute="@game.MINUTE" second="@game.SECOND"/>',
        '</span>'])


def block(prefix, body_id):
    """The shared block for one key prefix ("", "old_", "new_") and body id."""
    return " ".join([
        '<div id="%s" class="nui-tip__body">' % body_id,
        '<div class="nui-tip__slot" data-for="l : %slines">' % prefix,
        '<div class="nui-tip__rule" data-if="l.rule"></div>',
        '<div class="nui-tip__line" data-if="l.t == \'line\'"', _gaps("l"),
        'data-class-nui-tip__line--left="l.align == \'left\'" data-class-nui-tip__line--right="l.align == \'right\'"',
        'data-class-nui-tip__line--plain="!l.outline">', _runs("l"), '</div>',
        '<img class="nui-tip__image" data-if="l.t == \'image\'" data-attr-src="l.src"', _gaps("l") + "/>",
        '<div class="nui-tip__socket" data-if="l.t == \'socket\'" data-class-nui-tip__socket--gold="l.frame == \'gold\'"',
        _gaps("l") + ">",
        '<span class="nui-tip__socket-frame"><img class="nui-tip__socket-icon" data-if="l.icon != \'\'" data-attr-src="l.icon"/></span>',
        '<div class="nui-tip__socket-lines">', '<div class="nui-tip__slot" data-for="s : l.sub">',
        '<div class="nui-tip__line nui-tip__line--left" data-class-nui-tip__line--plain="!s.outline">', _runs("s"),
        '</div>', '</div>', '</div>', '</div>', '</div>', '</div>'])


BLOCK = block("", "tip-body")


if __name__ == "__main__":
    unittest.main()
