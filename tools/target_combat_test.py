"""Tests for the target board's combat parts (wave 10, qol-social P1):
NOVA-208 (the damage trail and the poison and burn tint of the HP bar),
NOVA-209's UI half (the archer distance gauge) and NOVA-216's UI half (the
metin stone hint), in the legacy board (assets/root/uitarget.py) and the
NovaUI one (nui_target.py, nui/windows/target/): python3 -B -m unittest
target_combat_test (from tools/).

Plain CPython over nui_hud_test's worlds (nui_game_support's stand-ins).
The C++ side (player.GetArrowDistancePercent, chrmgr.HasAffectByVID and
the feeds target.arrow_percent, target.poisoned and target.burning) is
built in parallel, so the stand-ins answer for it here."""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_hud_test as hud  # noqa: E402

ASSETS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets"))
TARGET = os.path.join(hud.WINDOWS, "target")
CLASSIC = os.path.join(ASSETS, "nui", "nui", "skins", "classic", "windows", "target.rcss")
CYBERPUNK = os.path.join(ASSETS, "nui", "nui", "skins", "cyberpunk", "windows", "target.rcss")
PATTERN = os.path.join(ASSETS, "ETC", "ymir work", "ui", "pattern")

MOB_VID = 300
STONE_VID = 301
MOB_RACE = 101
STONE_RACE = 8001
BOW = 2000
SWORD = 10
# The client's values (item module, ItemData.h; GameType.h c_Equipment_Weapon).
ITEM_TYPE_WEAPON = 1
WEAPON_SWORD = 0
WEAPON_BOW = 2
EQUIPMENT_WEAPON = 94
AFFECT_POISON = hud.CHR["AFFECT_POISON"]
AFFECT_FIRE = hud.CHR["AFFECT_FIRE"]


def arrow_rule(distance):
    """bow_distance.h ArrowDistancePercent: 120 up to 500 units, 80 from
    2000, the line between in whole percents rounded toward the bonus."""
    if distance <= 500:
        return 120
    if distance >= 2000:
        return 80
    return 80 + -(-(2000 - distance) * 40 // 1500)


def combat_setup(game):
    """target_setup, the C++ answers of this package and a legacy gauge
    that holds its colored bar (ui.Gauge.imgGauge) as the client's does."""
    hud.target_setup(game)
    t = game.target
    t.update({"affects": {}, "races": {MOB_VID: MOB_RACE, STONE_VID: STONE_RACE}, "stones": {STONE_RACE},
              "weapons": {BOW: WEAPON_BOW, SWORD: WEAPON_SWORD}})
    t["names"][STONE_VID] = "Metin of Sorrow"
    t["levels"][STONE_VID] = 25
    item = game.modules["item"]
    item.ITEM_TYPE_WEAPON = ITEM_TYPE_WEAPON
    item.WEAPON_BOW = WEAPON_BOW
    item.EQUIPMENT_WEAPON = EQUIPMENT_WEAPON
    game.answer("item", "GetItemType", lambda: ITEM_TYPE_WEAPON if item.selected[0] in t["weapons"] else 0)
    game.answer("item", "GetItemSubType", lambda: t["weapons"].get(item.selected[0], -1))
    game.answer("nonplayer", "GetRaceNumByVID", lambda vid: t["races"].get(vid, -1))
    game.answer("nonplayer", "IsMonsterStone", lambda race: 1 if race in t["stones"] else 0)
    game.answer("chrmgr", "HasAffectByVID", lambda vid, affect: affect in t["affects"].get(vid, ()))
    game.answer("player", "GetArrowDistancePercent", arrow_rule)
    game.modules["localeInfo"].TARGET_ARROW_DAMAGE = "%s arrow damage"
    game.modules["localeInfo"].TARGET_METIN_QUEUE_HINT = "Shift + right-click: add to the attack queue"
    ui = game.modules["ui"]
    base = ui.Gauge

    class Gauge(base):
        def MakeGauge(self, width, color):
            base.MakeGauge(self, width, color)
            self.imgGauge = ui.ExpandedImageBox()
            self.imgGauge.LoadImage("d:/ymir work/ui/pattern/gauge_" + color + ".tga")
            self.imgGauge.Show()
    ui.Gauge = Gauge


def wield(world, vnum):
    world.game.items[EQUIPMENT_WEAPON] = {"vnum": vnum, "count": 1, "sockets": [0, 0, 0, 0]}


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class Worlds(hud.TargetWorlds):
    def worlds(self, **relation):
        legacy, novaui = hud.pair(combat_setup)
        for world in (legacy, novaui):
            world.game.target.update(relation)
            with world:
                world.board = world.make("target", world.module("uiTarget").TargetBoard, "nui_target.TargetBoard")
                world.board.Hide()
        self.assertEqual(type(novaui.board).__module__, "nui_target")
        return legacy, novaui

    @staticmethod
    def target_monster(world, vid=MOB_VID, hp=100):
        """game.py SetHPTargetBoard."""
        board = world.board
        if vid != board.GetTargetVID():
            board.ResetTargetBoard()
            board.SetEnemyVID(vid)
        board.SetHP(hp)
        board.Show()

    @staticmethod
    def at(world, seconds):
        world.game.time = seconds


# --- NOVA-208: the damage trail -------------------------------------------------------------

class DamageTrail(Worlds):
    def test_novaui_a_drop_keeps_the_trail_at_the_old_hp_and_a_rise_moves_it_at_once(self):
        """The model: trail is the HP the bar's trail drains to (its right
        edge's class), trail_snap the class that takes its transition away;
        a drop keeps the transition (the sheet drains it over 0.75 s from
        the old HP), a rise or a new target snaps."""
        _, novaui = self.worlds()
        model = novaui.board.board.model
        with novaui, hud.quiet():
            self.target_monster(novaui, hp=100)
        self.assertEqual((model["trail"], model["trail_snap"]), (100, True), "a new target: at once")
        with novaui, hud.quiet():
            novaui.board.SetHP(60)
        self.assertEqual((model["hp"], model["trail"], model["trail_snap"]), (0.6, 60, False), "a drop drains")
        with novaui, hud.quiet():
            novaui.board.SetHP(30)
        self.assertEqual((model["trail"], model["trail_snap"]), (30, False))
        with novaui, hud.quiet():
            novaui.board.SetHP(30)
        self.assertEqual((model["trail"], model["trail_snap"]), (30, False), "the same HP leaves a drain running")
        with novaui, hud.quiet():
            novaui.board.SetHP(80)
        self.assertEqual((model["trail"], model["trail_snap"]), (80, True), "a heal: at once, no orange")
        with novaui, hud.quiet():
            self.target_monster(novaui, vid=STONE_VID, hp=40)
        self.assertEqual((model["trail"], model["trail_snap"]), (40, True), "another target: at once")
        with novaui, hud.quiet():
            novaui.board.ResetTargetBoard()
        self.assertEqual((model["trail"], model["trail_snap"]), (0, True))

    def test_novaui_the_sheet_drains_the_trail_by_a_transition(self):
        """No Python per frame: the trail's right edge is one of 101 classes
        and the window sheet transitions it over 0.75 s, written out in a
        .nui-anim rule (reduced motion: base.rcss takes it away, so the
        trail ends at its width at once); is-snap takes it away too."""
        sheet = read(os.path.join(TARGET, "target.rcss"))
        rule = re.search(r"\.target-board__trail\.nui-anim\s*\{([^}]*)\}", sheet)
        self.assertTrue(rule, "the transition rule")
        self.assertIn("transition: right 0.75s linear-in-out;", rule.group(1))
        snap = re.search(r"\.target-board__trail\.is-snap\.nui-anim\s*\{([^}]*)\}", sheet)
        self.assertTrue(snap and "transition: none;" in snap.group(1), "the snap rule")
        for percent in range(101):
            self.assertRegex(sheet, r"\.target-board__trail--%d \{ right: %d%%; \}" % (percent, 100 - percent))
        self.assertIn("var(--target-hp", sheet, "the trail starts at the HP")
        self.assertIn("var(--gauge-trail)", sheet)
        document = read(os.path.join(TARGET, "target.rml"))
        trails = re.findall(r"<span[^>]*class=\"target-board__trail nui-anim\"[^>]*>", document)
        self.assertEqual(len(trails), 2, "the modern bar's trail and classic's")
        for trail in trails:
            self.assertIn("data-attr-class=\"'target-board__trail nui-anim target-board__trail--' + trail"
                          " + (trail_snap ? ' is-snap' : '')\"", trail)
            self.assertIn("data-style---target-hp=\"(hp * 100) + '%'\"", trail)
        base = read(os.path.join(ASSETS, "nui", "nui", "base.rcss"))
        self.assertRegex(base, r"transition: none", "reduced motion ends every transition at once")
        classic = read(CLASSIC)
        self.assertNotIn("transition:", classic, "a skin moves no content")
        self.assertTrue("gauge_orange.tga" in classic, "classic's trail is the legacy orange gauge")

    def test_legacy_the_trail_drains_from_the_old_hp_over_three_quarters_of_a_second(self):
        legacy, _ = self.worlds()
        T = legacy.module("uiTarget")
        with legacy, hud.quiet():
            self.at(legacy, 10.0)
            self.target_monster(legacy, hp=100)
            gauge = legacy.board.hpGauge
            gauge.OnUpdate()
            self.assertEqual(gauge.GetTrailPercent(), 100)
            self.assertFalse(gauge.trail.shown, "no trail beyond the HP")
            self.at(legacy, 11.0)
            legacy.board.SetHP(60)
            for now, expected in ((11.0, 100), (11.375, 80), (11.75, 60), (12.5, 60)):
                self.at(legacy, now)
                gauge.OnUpdate()
                self.assertAlmostEqual(gauge.GetTrailPercent(), expected, 3, now)
            self.at(legacy, 13.0)
            legacy.board.SetHP(40)
            self.at(legacy, 13.375)
            gauge.OnUpdate()
            self.assertAlmostEqual(gauge.GetTrailPercent(), 50, 3, "a second hit drains from the HP before it")
            self.assertTrue(gauge.trail.shown)
            legacy.board.SetHP(90)
            gauge.OnUpdate()
            self.assertEqual(gauge.GetTrailPercent(), 90, "a heal: at once")
            self.assertFalse(gauge.trail.shown)
            self.target_monster(legacy, vid=STONE_VID, hp=20)
            gauge.OnUpdate()
            self.assertEqual(gauge.GetTrailPercent(), 20, "another target: at once")
        self.assertEqual(T.TRAIL_SECONDS, 0.75)
        self.assertEqual(T.TrailPercent(100, 60, 11.0, 11.375), 80)

    def test_legacy_the_trail_is_drawn_from_the_hp_to_the_trail_in_orange(self):
        legacy, _ = self.worlds()
        with legacy, hud.quiet():
            self.at(legacy, 1.0)
            self.target_monster(legacy, hp=100)
            legacy.board.SetHP(50)
            gauge = legacy.board.hpGauge
            gauge.OnUpdate()
        self.assertEqual(gauge.trail.image, "d:/ymir work/ui/pattern/gauge_orange.tga")
        # ui.Gauge: the bar starts 12 px in and spans width - 24 px; the
        # rendering rect counts 16 px images beyond the first.
        self.assertEqual(gauge.trail.position, (12 + 53, 0))
        self.assertIn(("SetRenderingRect", 0.0, 0.0, 53 / 16.0 - 1.0, 0.0), gauge.trail.calls)


# --- NOVA-208: the poison and burn tint ---------------------------------------------------------

class PoisonAndBurn(Worlds):
    def test_legacy_the_bar_is_green_poisoned_yellow_burning_green_with_both_red_otherwise(self):
        legacy, _ = self.worlds()
        with legacy, hud.quiet():
            self.target_monster(legacy, hp=70)
            gauge = legacy.board.hpGauge
            for affects, color in (((), "red"), ((AFFECT_POISON,), "green"), ((AFFECT_FIRE,), "yellow"),
                                   ((AFFECT_POISON, AFFECT_FIRE), "green"), ((), "red")):
                legacy.game.target["affects"] = {MOB_VID: set(affects)}
                legacy.board.OnUpdate()
                self.assertEqual(gauge.imgGauge.image, "d:/ymir work/ui/pattern/gauge_%s.tga" % color, affects)
            self.assertIn(("chrmgr.HasAffectByVID", (MOB_VID, AFFECT_POISON)), legacy.game.log)
            self.assertIn(("chrmgr.HasAffectByVID", (MOB_VID, AFFECT_FIRE)), legacy.game.log)
            loads = len([c for c in gauge.imgGauge.calls if c[0] == "LoadImage"])
            legacy.board.OnUpdate()
            self.assertEqual(len([c for c in gauge.imgGauge.calls if c[0] == "LoadImage"]), loads,
                             "the art loads only when the state changes")

    def test_legacy_an_exe_without_has_affect_by_vid_keeps_red(self):
        legacy, _ = self.worlds()
        legacy.game.modules["chrmgr"].lack("HasAffectByVID")
        with legacy, hud.quiet():
            self.target_monster(legacy, hp=70)
            legacy.board.OnUpdate()
        self.assertEqual(legacy.board.hpGauge.imgGauge.image, "d:/ymir work/ui/pattern/gauge_red.tga")

    def test_novaui_the_feeds_tint_the_bar_with_no_python(self):
        module = None
        _, novaui = self.worlds()
        module = novaui.module("nui_target")
        self.assertEqual(module.TargetBoardBoard.FEEDS, {
            "in_range": "target.in_range", "arrow_percent": "target.arrow_percent",
            "poisoned": "target.poisoned", "burning": "target.burning"})
        model = novaui.board.board.model
        for name in ("poisoned", "burning"):
            novaui.game.state.publish("target." + name, True)
        self.assertEqual((model["poisoned"], model["burning"]), (True, True))
        document = read(os.path.join(TARGET, "target.rml"))
        gauges = re.findall(r"<progress[^>]*>", document)
        tinted = [g for g in gauges if "target-board__gauge" in g or "target-board__hp" in g]
        self.assertEqual(len(tinted), 2, "the modern bar and classic's gauge")
        for gauge in tinted:
            self.assertIn('data-class-is-poisoned="poisoned"', gauge)
            self.assertIn('data-class-is-burning="burning && !poisoned"', gauge, "poison wins when both")
        sheet = read(os.path.join(TARGET, "target.rcss"))
        for token in ("--gauge-poison", "--gauge-burn"):
            self.assertIn("var(%s)" % token, sheet)
        tokens = json.loads(read(os.path.join(ASSETS, "nui", "nui", "theme", "tokens.json")))
        for palette in ("dark", "light", "classic"):
            for token in ("gauge-trail", "gauge-poison", "gauge-burn"):
                self.assertIn(token, tokens[palette], (palette, token))
        cyber = json.loads(read(os.path.join(ASSETS, "nui", "nui", "skins", "cyberpunk", "tokens.json")))
        for token in ("gauge-trail", "gauge-poison", "gauge-burn"):
            self.assertIn(token, cyber["palettes"]["cyberpunk"], token)
        classic = read(CLASSIC)
        for color in ("green", "yellow", "orange"):
            self.assertTrue("d:/ymir work/ui/pattern/gauge_%s.tga" % color in classic, color)
            self.assertTrue(os.path.isfile(os.path.join(PATTERN, "gauge_%s.tga" % color)), color)
        self.assertRegex(classic, r"progress\.target-board__hp\.is-poisoned fill\s*\{\s*decorator: target-gauge-green;")
        self.assertRegex(classic, r"progress\.target-board__hp\.is-burning fill\s*\{\s*decorator: target-gauge-yellow;")


# --- NOVA-209: the archer distance gauge ------------------------------------------------------

class ArcherGauge(Worlds):
    def test_legacy_the_gauge_shows_with_a_bow_and_follows_the_distance(self):
        legacy, _ = self.worlds()
        T = legacy.module("uiTarget")
        with legacy, hud.quiet():
            self.target_monster(legacy, hp=100)
            archer = legacy.board.archerGauge
            legacy.board.OnUpdate()
            self.assertFalse(archer.IsShow(), "no weapon")
            wield(legacy, SWORD)
            legacy.board.OnUpdate()
            self.assertFalse(archer.IsShow(), "a sword")
            wield(legacy, BOW)
            for distance, percent, fill in ((300, 120, 1.0), (1250, 100, 0.5), (2500, 80, 0.0), (1000, 107, 27 / 40.0)):
                legacy.game.target["distance"] = distance
                legacy.board.OnUpdate()
                self.assertTrue(archer.IsShow(), distance)
                self.assertEqual(archer.percent, percent, distance)
                self.assertAlmostEqual(archer.GetFill(), fill, 3)
            self.assertIn(("player.GetArrowDistancePercent", (1000,)), legacy.game.log)
            legacy.board.Hide()
            self.assertFalse(archer.IsShow(), "it hides with the board")
            legacy.board.Show()
            legacy.board.OnUpdate()
            self.assertTrue(archer.IsShow())
            legacy.board.Close()
            self.assertFalse(archer.IsShow(), "and closes with it")
        self.assertEqual(T.ArcherGauge.LOW, 80)
        self.assertEqual(T.ArcherGauge.HIGH, 120)

    def test_legacy_its_tooltip_says_the_bonus_in_green_white_or_red(self):
        legacy, _ = self.worlds()
        T = legacy.module("uiTarget")
        with legacy, hud.quiet():
            self.target_monster(legacy, hp=100)
            wield(legacy, BOW)
            archer = legacy.board.archerGauge
            legacy.game.target["distance"] = 300
            legacy.board.OnUpdate()
            archer.OnMouseOverIn()
            tip = archer.toolTip
            self.assertTrue(tip.visible)
            self.assertEqual(tip.lines, ["+20% arrow damage"])
            for distance, line in ((2500, "-20% arrow damage"), (1250, "0% arrow damage"), (1000, "+7% arrow damage")):
                legacy.game.target["distance"] = distance
                legacy.board.OnUpdate()
                self.assertEqual(tip.lines, [line], distance)
            archer.OnMouseOverOut()
            self.assertFalse(tip.visible)
        self.assertEqual(T.ArrowDamageText(120), ("+20% arrow damage", T.ARROW_UP))
        self.assertEqual(T.ArrowDamageText(100), ("0% arrow damage", T.ARROW_EVEN))
        self.assertEqual(T.ArrowDamageText(85), ("-15% arrow damage", T.ARROW_DOWN))

    def test_legacy_an_exe_without_the_rule_shows_no_gauge(self):
        legacy, _ = self.worlds()
        legacy.game.modules["player"].lack("GetArrowDistancePercent")
        with legacy, hud.quiet():
            self.target_monster(legacy, hp=100)
            wield(legacy, BOW)
            legacy.board.OnUpdate()
        self.assertFalse(legacy.board.archerGauge.IsShow())

    def test_novaui_the_gauge_follows_the_feed(self):
        _, novaui = self.worlds()
        model = novaui.board.board.model
        self.assertEqual((model["arrow_pre"], model["arrow_post"]), ("", " arrow damage"),
                         "the locale text around its number, read once")
        novaui.game.state.publish("target.arrow_percent", 120)
        self.assertEqual(model["arrow_percent"], 120)
        document = read(os.path.join(TARGET, "target.rml"))
        host = re.search(r"<span id=\"target-arrow\".*?\"><progress", document, re.S)
        self.assertTrue(host)
        self.assertIn('data-if="arrow_percent > 0"', host.group(0), "hidden at 0: no bow, no target")
        self.assertIn("nui-has-tooltip", host.group(0))
        self.assertIn("nui-interactive", host.group(0))
        gauge = re.search(r"<progress\s+id=\"target-arrow-gauge\".*?/>", document, re.S).group(0)
        self.assertIn('direction="top"', gauge)
        self.assertIn('data-attr-value="(arrow_percent - 80) / 40"', gauge, "80 empty, 120 full")
        self.assertIn('data-class-is-up="arrow_percent > 100"', document)
        self.assertIn('data-class-is-down="arrow_percent < 100"', document)


# --- NOVA-216: the metin stone hint -----------------------------------------------------------

class MetinHint(Worlds):
    def test_a_stone_target_shows_the_queue_hint_in_both_boards(self):
        legacy, novaui = self.worlds()
        hint = "Shift + right-click: add to the attack queue"
        self.both(legacy, novaui, lambda world: self.target_monster(world, vid=STONE_VID, hp=100))
        self.assertTrue(legacy.board.metinHint.shown)
        self.assertEqual(legacy.board.metinHint.text, hint)
        self.assertEqual(novaui.board.board.model["hint"], hint)
        self.both(legacy, novaui, lambda world: self.target_monster(world, vid=MOB_VID, hp=100))
        self.assertFalse(legacy.board.metinHint.shown, "a monster")
        self.assertEqual(novaui.board.board.model["hint"], "")
        self.both(legacy, novaui, lambda world: self.target_monster(world, vid=STONE_VID, hp=100))
        self.both(legacy, novaui, lambda world: world.board.ResetTargetBoard())
        self.assertFalse(legacy.board.metinHint.shown)
        self.assertEqual(novaui.board.board.model["hint"], "")

    def test_an_exe_without_is_monster_stone_shows_no_hint(self):
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            world.game.modules["nonplayer"].lack("IsMonsterStone")
        self.both(legacy, novaui, lambda world: self.target_monster(world, vid=STONE_VID, hp=100))
        self.assertFalse(legacy.board.metinHint.shown)
        self.assertEqual(novaui.board.board.model["hint"], "")


# --- the fixtures ------------------------------------------------------------------------------

class Fixtures(unittest.TestCase):
    def test_every_target_fixture_holds_every_model_key_of_its_kind(self):
        world = hud.HudWorld(True, setup=combat_setup)
        with world:
            board_class = world.module("nui_target").TargetBoardBoard
            board = board_class(object())
            model = board.initial_model()
            names = sorted(name for name in os.listdir(TARGET) if name.endswith(".fixture.json"))
            self.assertGreaterEqual(len(names), 10, names)
            for name in names:
                values = json.loads(read(os.path.join(TARGET, name)))["target"]
                self.assertEqual(set(values), set(model), name)
                for key, value in values.items():
                    self.assertEqual(hud.kind(value), hud.kind(model[key]), "%s %s" % (name, key))
                self.assertTrue(board.set(**values))

    def test_the_goldens_stand_in_for_the_feeds_with_their_fixtures(self):
        """nuitool snap runs no controller, so --feed reaches only the
        elements that read a feed themselves (the chat lines), never a fed
        model key: the fixtures carry the fed values of each case."""
        cases = json.loads(read(os.path.join(TARGET, "target.snapshots.json")))["cases"]
        variants = dict((case.get("variant"), case) for case in cases)
        fed = {"trail": {"trail": 75, "trail_snap": False, "hp": 0.45}, "poison": {"poisoned": True, "burning": False},
               "burn": {"poisoned": False, "burning": True}, "both": {"poisoned": True, "burning": True},
               "arrow80": {"arrow_percent": 80}, "arrow100": {"arrow_percent": 100}, "arrow120": {"arrow_percent": 120},
               "stone": {"hint": "Shift + right-click: add to the attack queue"}}
        for variant, values in fed.items():
            self.assertIn(variant, variants)
            model = json.loads(read(os.path.join(TARGET, "target.%s.fixture.json" % variant)))["target"]
            for key, value in values.items():
                self.assertEqual(model[key], value, (variant, key))
            self.assertNotIn("feeds", variants[variant])
        for variant in ("arrow80", "arrow100", "arrow120"):
            self.assertTrue(any(case.get("variant") == variant and case.get("hover") for case in cases),
                            "the tooltip shows: " + variant)

if __name__ == "__main__":
    unittest.main()
