"""Tests for the legacy client's advanced pet (NOVA-24, chunk Y; OLD's
ENABLE_PET_ADVANCED): python3 -B -m unittest pet_advanced_test (from tools/).

The C++ half (the pet module of contract 6 over GC/CG::PET_ADVANCED, the
BINARY_Pet* callbacks) is chunk C's; here the legacy Python runs over
nui_game_support's stand-ins with C's names (pet_support):
- uipet.py (OLD root/uiPet.py) and its five uiscripts: the hatch window and
  its rename mode (with decision Q2's wait), the evolution window, the
  attribute refine window, the pet window (own and preview) and the mini
  window;
- game.py's callbacks and keys, the Interface's six windows (contract 8's
  ids and controllers), the pet window toggle and the Tab preview host;
- the inventory's hooks (egg, name changer, destiny orb, summoned glow) and
  every window's Tab preview with contract 6's arguments;
- uitooltip.py: the pet item's lines, the egg's hatch time, the Tab hint
  and PetSkillToolTip; ui.py's SetPetSkillSlot."""
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pet_support as ps  # noqa: E402
import sash_test  # noqa: E402

lf, w6, support = ps.lf, ps.w6, ps.support
compiled = sash_test.compiled
ROOT = support.ROOT
EGG_CELL, SEAL_CELL, REVERT_CELL, ORB_CELL, CHANGER_CELL, BOOK_CELL = 3, 5, 7, 8, 9, 10


def read_root(name):
    return lf.read(os.path.join(ROOT, name))


def popups(world):
    return [args for name, args in world.game.log if name == "uiCommon.PopupDialog.Open"]


def chats(world):
    return [args for name, args in world.game.log if name == "chat.AppendChat"]


class Fixture(unittest.TestCase):
    def setUp(self):
        self.world = ps.World()
        self.state = self.world.state
        self.game = self.world.game
        self.module = self.world.pet_module()
        self.locale = self.game.modules["localeInfo"]
        self.player = self.game.modules["player"]

    def give(self, cell, vnum, **kwargs):
        """An item at a bag cell, by its cell and by (INVENTORY, cell)."""
        self.game.give(cell, vnum, **kwargs)
        self.game.give((self.player.INVENTORY, cell), vnum, **kwargs)

    def make(self, name, *args):
        with self.game, lf.quiet():
            return getattr(self.module, name)(*args)

    def run_with(self, call, *args):
        return ps.run(self.world, call, *args)


# --- the hatch window ----------------------------------------------------------------------------------

class Hatch(Fixture):
    def setUp(self):
        Fixture.setUp(self)
        self.give(EGG_CELL, ps.EGG)
        self.give(SEAL_CELL, ps.SEAL)
        self.window = self.make("PetHatchEggWindow")
        del self.game.log[:]

    def test_open_shows_the_egg_the_pet_and_the_price(self):
        self.run_with(self.window.Open, EGG_CELL)
        slots = self.window.GetChild("HatchingItemSlot").slots
        self.assertEqual((slots[0]["vnum"], slots[1]["vnum"]), (ps.EGG, ps.SEAL))
        self.assertEqual(self.window.GetChild("HatchingMoney").text,
                         self.locale.TOOLTIP_SELLPRICE % self.locale.NumberToMoneyString(1000000))
        self.assertTrue(self.window.IsShow())

    def test_a_short_name_is_refused_with_a_popup(self):
        self.run_with(self.window.Open, EGG_CELL)
        self.window.GetChild("pet_name").SetText("Re")
        self.run_with(self.window._PetHatchEggWindow__OnClickHatch)
        self.assertEqual(ps.sends(self.world), [])
        self.assertEqual(popups(self.world), [(self.locale.PET_HATCH_NAME_TOO_SHORT, "")])

    def test_hatch_sends_the_eggs_window_cell_and_name(self):
        self.run_with(self.window.Open, EGG_CELL)
        self.window.GetChild("pet_name").SetText("Rex")
        self.run_with(self.window._PetHatchEggWindow__OnClickHatch)
        self.assertEqual(ps.sends(self.world), [("UseEgg", (self.player.INVENTORY, EGG_CELL, "Rex"))])
        self.assertFalse(self.window.IsShow())

    def test_rename_mode_changes_the_seals_name(self):
        self.run_with(self.window.Open, EGG_CELL)
        self.run_with(self.window.Close)
        self.run_with(self.window.Open, SEAL_CELL, self.player.INVENTORY, True)
        slots = self.window.GetChild("HatchingItemSlot").slots
        self.assertEqual((slots[0]["vnum"], slots[1]["vnum"]), (ps.SEAL, 0), "OLD bug 11: no stale pet over the seal")
        self.assertEqual(self.window.GetChild("TitleName").text, self.locale.PET_HATCH_RENAME_TITLE)
        self.assertEqual(self.window.GetChild("HatchingButton").text, self.locale.PET_HATCH_RENAME_BUTTON)
        self.assertFalse(self.window.GetChild("HatchingMoney").shown)
        self.window.GetChild("pet_name").SetText("Bruno")
        self.run_with(self.window._PetHatchEggWindow__OnClickHatch)
        self.assertEqual(ps.sends(self.world), [("ChangeName", (self.player.INVENTORY, SEAL_CELL, "Bruno"))])

    def test_an_egg_that_cannot_hatch_yet_says_how_long(self):
        """Decision Q2: socket 1 holds the time it can hatch (OLD's own check,
        commented out, read socket 0 and gave no time)."""
        self.give(EGG_CELL, ps.EGG, sockets=(0, self.game.timestamp + 3600, 0, 0))
        self.run_with(self.window.Open, EGG_CELL)
        self.assertFalse(self.window.IsShow())
        self.assertEqual(chats(self.world), [(self.game.modules["chat"].CHAT_TYPE_INFO,
                                              self.locale.PET_HATCH_NEED_WAIT % self.locale.SecondToDHM(3600))])
        self.give(EGG_CELL, ps.EGG, sockets=(0, self.game.timestamp - 1, 0, 0))
        self.run_with(self.window.Open, EGG_CELL)
        self.assertTrue(self.window.IsShow(), "a time in the past hatches")

    def test_escape_closes(self):
        self.run_with(self.window.Open, EGG_CELL)
        self.assertTrue(self.run_with(self.window.OnPressEscapeKey))
        self.assertFalse(self.window.IsShow())


# --- the evolution and refine windows ----------------------------------------------------------------------

class Evolution(Fixture):
    def setUp(self):
        Fixture.setUp(self)
        self.state.summon(level=15, exp=0)
        self.state.evolve.update({"cost": 500000, "materials": [(55003, 2), (55004, 1)], "prob": 80})
        self.window = self.make("PetEvolutionWindow")
        self.run_with(self.window.Open)
        del self.game.log[:]

    def test_open_shows_the_current_and_next_grade(self):
        self.assertEqual(self.window.GetChild("evolve_current").text, self.locale.PET_EVOLVE_GRADE_JUNIOR)
        self.assertEqual(self.window.GetChild("evolve_next").text, self.locale.PET_EVOLVE_GRADE_APPRENTICE)
        self.assertEqual(self.window.GetChild("active_skill_count_next").text,
                         self.locale.PET_EVOLVE_ACTIVE_SKILL_COUNT % "1")
        self.assertEqual(self.window.GetChild("cost").text,
                         self.locale.PET_EVOLVE_PRICE % self.locale.NumberToMoneyString(500000))
        self.assertEqual(len(self.window._materials), 2)

    def test_not_enough_money_or_material_is_refused(self):
        self.game.material_counts = {55003: 2, 55004: 0}
        self.player.GetMoney = lambda: 100
        self.run_with(self.window._PetEvolutionWindow__OnClickEvolve)
        self.player.GetMoney = lambda: 10 ** 9
        self.player.GetItemCountByVnum = lambda vnum: self.game.material_counts.get(vnum, 0)
        self.run_with(self.window._PetEvolutionWindow__OnClickEvolve)
        self.assertEqual(ps.sends(self.world), [])
        self.assertEqual([texts[0] for texts in popups(self.world)],
                         [self.locale.PET_EVOLVE_ERROR_NOT_ENOUGH_GOLD,
                          self.locale.PET_EVOLVE_ERROR_NOT_ENOUGH_ITEM % (1, "item 55004")])

    def test_evolve_sends_and_the_result_texts(self):
        self.player.GetMoney = lambda: 10 ** 9
        self.player.GetItemCountByVnum = lambda vnum: 5
        self.run_with(self.window._PetEvolutionWindow__OnClickEvolve)
        self.assertEqual(ps.sends(self.world), [("Evolve", ())])
        self.run_with(self.window.OnEvolveFailure)
        self.assertTrue(self.window.IsShow())
        self.run_with(self.window.OnEvolveSuccess)
        self.assertFalse(self.window.IsShow())
        self.assertEqual([texts[0] for texts in popups(self.world)],
                         [self.locale.PET_EVOLVE_FAILURE, self.locale.PET_EVOLVE_SUCCESS])


class AttrRefine(Fixture):
    def setUp(self):
        Fixture.setUp(self)
        self.state.summon()
        self.state.own["attrs"][1] = [ps.APPLY_MAX_HP, 4, 400, 1]
        self.state.refine.update({"cost": 250000, "materials": [(55003, 3)]})
        self.window = self.make("PetAttrRefineWindow")
        self.run_with(self.window.Open, 1, 500)
        del self.game.log[:]

    def test_open_shows_the_bonus_now_and_next(self):
        self.assertEqual(self.window.GetChild("attr_txt").text, "Max HP")
        self.assertEqual(self.window.GetChild("level_current").text, "Lv. 4")
        self.assertEqual(self.window.GetChild("attr_bonus_current").text, "400")
        self.assertEqual(self.window.GetChild("level_next").text, "Lv. 5")
        self.assertEqual(self.window.GetChild("attr_bonus_next").text, "500")
        self.assertEqual(self.window.GetChild("cost").text,
                         self.locale.PET_EVOLVE_PRICE % self.locale.NumberToMoneyString(250000))

    def test_upgrade_checks_then_sends_the_index(self):
        self.player.GetMoney = lambda: 10 ** 9
        self.player.GetItemCountByVnum = lambda vnum: 1
        self.run_with(self.window._PetAttrRefineWindow__OnClickUpgrade)
        self.player.GetItemCountByVnum = lambda vnum: 3
        self.run_with(self.window._PetAttrRefineWindow__OnClickUpgrade)
        self.assertEqual(ps.sends(self.world), [("RefineAttr", (1,))])
        self.assertEqual([texts[0] for texts in popups(self.world)],
                         [self.locale.PET_EVOLVE_ERROR_NOT_ENOUGH_ITEM % (2, "item 55003")])

    def test_it_closes_at_the_top_level(self):
        self.state.own["attrs"][1][1] = self.module.PET_ATTR_MAX_LEVEL
        self.run_with(self.window.Refresh)
        self.assertFalse(self.window.IsShow())

    def test_the_result_texts_say_what_happened(self):
        """OLD bug 5: OLD's two texts were swapped."""
        english = lf.read_locale("en")
        self.assertEqual(english["PET_ATTR_REFINE_SUCCESS"][0], "Bonus upgraded successfully!")
        self.assertEqual(english["PET_ATTR_REFINE_FAILURE"][0], "Failed to upgrade bonus!")
        self.assertEqual(lf.read_locale("de")["PET_ATTR_REFINE_SUCCESS"][0], "Bonus erfolgreich verbessert!")


# --- the pet window ---------------------------------------------------------------------------------

class PetWindow(Fixture):
    def setUp(self):
        Fixture.setUp(self)
        self.window = self.make("PetWindow")
        self.state.summon(level=15, exp=0, next_exp=2000)
        self.state.own["attrs"] = [[ps.APPLY_MAX_HP, 3, 300, 1], [ps.APPLY_CRITICAL_PCT, 2, 2, 0], [0, 0, 0, 0]]
        self.state.own["skills"][0] = [ps.APPLY_MAX_HP, 5, 250]
        self.state.own["skills"][10] = [86, 1, 1]
        del self.game.log[:]

    def open(self, preview=False):
        self.run_with(self.window.Open, preview)

    def test_it_opens_only_with_a_pet_out(self):
        self.state.summoned = False
        self.open()
        self.assertFalse(self.window.IsShow())
        self.state.summoned = True
        self.open()
        self.assertTrue(self.window.IsShow())

    def test_the_status_lines(self):
        self.open()
        self.assertIn("Rex", self.window.GetChild("PetName").text)
        self.assertIn(self.locale.PET_INFO_NAME, self.window.GetChild("PetName").text)
        self.assertIn("(15)", self.window.GetChild("PetLevel").text)
        self.assertIn(self.locale.PET_EVOLVE_GRADE_JUNIOR, self.window.GetChild("PetEvolution").text)
        self.assertEqual(self.window.GetChild("PetImage").image, "d:/ymir work/ui/pet/panel_info/icon_pets/55701.png")
        self.assertEqual(self.window.GetChild("bonus1_name").text, "Max HP")
        self.assertEqual(self.window.GetChild("bonus1_level").text, "Lv.3 - 300")
        self.assertEqual(self.window.GetChild("bonus2_level").text, "Lv.2 - 2%")
        self.assertTrue(self.window.GetChild("bonus1_plus_btn").shown)
        self.assertFalse(self.window.GetChild("bonus2_plus_btn").shown)

    def test_the_evolve_button_flashes_at_a_gate(self):
        self.open()
        button = self.window.GetChild("evolution_upgrade")
        self.assertIn(("Flash",), button.calls)
        self.assertIn(("Enable",), button.calls)
        del button.calls[:]
        self.state.own.update({"level": 20, "exp": 10})
        self.run_with(self.window.Refresh)
        self.assertIn(("Disable",), button.calls)
        self.assertNotIn(("Flash",), button.calls)
        self.state.own.update({"level": 105, "exp": 5})
        self.run_with(self.window.Refresh)
        self.assertFalse(button.shown, "no next grade at Heroicmax")

    def test_the_skill_cells_and_the_disabled_overlay(self):
        self.open()
        slots = self.window.GetChild("skill_slot").slots
        self.assertEqual((slots[0]["vnum"], slots[0]["count"]), (ps.APPLY_MAX_HP, 5))
        self.assertEqual(slots[10]["vnum"], 86)
        # Junior at 15 with 0 exp: 0 normal and 0 heroic cells open.
        self.assertTrue(all(self.window.GetChild("skill_slot%d_disabled" % (i + 1)).shown for i in range(13)))
        self.state.own["exp"] = 1
        self.run_with(self.window.Refresh)
        self.assertFalse(self.window.GetChild("skill_slot1_disabled").shown, "Apprentice opens one cell")
        self.assertTrue(self.window.GetChild("skill_slot2_disabled").shown)

    def test_a_plus_or_a_click_on_the_level_asks_the_refine_info(self):
        self.open()
        self.run_with(self.window.GetChild("bonus1_plus_btn").event)
        self.run_with(self.window.GetChild("bonus3_level_bg").OnMouseLeftButtonDown)
        self.run_with(self.window.GetChild("evolution_upgrade").event)
        self.assertEqual(ps.sends(self.world), [("RequestAttrRefineInfo", (0,)), ("RequestAttrRefineInfo", (2,)),
                                                ("RequestEvolutionInfo", ())])

    def test_a_revert_dropped_on_a_skill_resets_it(self):
        self.open()
        self.game.give(REVERT_CELL, ps.REVERT)
        self.game.give(ORB_CELL, ps.ORB)
        self.world.attach(self.player.SLOT_TYPE_INVENTORY, ORB_CELL, ps.ORB)
        self.run_with(self.window.GetChild("skill_slot").fire, "select_item", 0)
        self.world.attach(self.player.SLOT_TYPE_INVENTORY, REVERT_CELL, ps.REVERT)
        self.run_with(self.window.GetChild("skill_slot").fire, "select_item", 0)
        self.assertEqual(ps.sends(self.world), [("UseResetSkill", (self.player.INVENTORY, REVERT_CELL, 0))])
        self.assertFalse(self.world.mouse.isAttached())

    def test_the_skill_tooltip(self):
        self.open()
        self.run_with(self.window.GetChild("skill_slot").fire, "over_in", 0)
        self.assertIn(("PetSkillToolTip.SetSkill", (ps.APPLY_MAX_HP, 5, False)), self.game.log)

    def test_the_exp_and_bonus_tooltips_follow_a_refresh(self):
        """OLD re-ran the shown text tooltip every frame; the refresh does."""
        self.state.own.update({"exp": 500})
        self.open()
        self.run_with(self.window.GetChild("ExpBar").OnMouseOverIn)
        tip = self.window.textToolTip
        self.assertEqual(tip.textLine.text, self.locale.TARGET_INFO_EXP % "25.00%")
        self.state.own["exp"] = 1000
        self.run_with(self.window.RefreshStatus)
        self.assertEqual(tip.textLine.text, self.locale.TARGET_INFO_EXP % "50.00%")
        self.run_with(self.window.GetChild("bonus1_level_bg").OnMouseOverIn)
        self.assertEqual(tip.textLine.text, self.locale.TOOLTIP_PET_ATTR_INFO % (3, "Max HP +300"))

    def test_the_preview_reads_the_preview_table(self):
        """OLD bug 4: the preview's gate and exp read the own pet."""
        self.state.preview.update({"item_vnum": 55702, "name": "Spot", "level": 30, "exp": 0, "next_exp": 100})
        self.state.preview["skills"][1] = [ps.APPLY_HP_REGEN, 7, 4]
        self.state.summoned = False
        self.open(True)
        self.assertTrue(self.window.IsShow())
        self.assertEqual(self.window.GetChild("bg").image, "d:/ymir work/ui/pet/bg-preview.png")
        self.assertIn("Spot", self.window.GetChild("PetName").text)
        self.assertIn(self.locale.PET_EVOLVE_GRADE_APPRENTICE, self.window.GetChild("PetEvolution").text)
        self.assertIn(("Flash",), self.window.GetChild("evolution_upgrade").calls, "30 with 0 exp is the Scout gate")
        self.assertEqual(self.window.GetChild("skill_slot").slots[1]["vnum"], ps.APPLY_HP_REGEN)
        self.run_with(self.window.GetChild("skill_slot").fire, "over_in", 1)
        self.assertIn(("PetSkillToolTip.SetSkill", (ps.APPLY_HP_REGEN, 7, True)), self.game.log)

    def test_escape_and_close(self):
        self.open()
        self.assertTrue(self.run_with(self.window.OnPressEscapeKey))
        self.assertFalse(self.window.IsShow())


class MiniWindow(Fixture):
    def setUp(self):
        Fixture.setUp(self)
        self.state.summon(level=15, exp=1)
        self.window = self.make("PetInterfaceWindow")
        self.run_with(self.window.Open)

    def size(self):
        return self.window.GetChild("board").size

    def tick(self, seconds):
        self.game.time += seconds
        self.run_with(self.window.OnUpdate)

    def test_it_opens_folded(self):
        self.assertTrue(self.window.IsShow())
        self.assertEqual(self.size(), (75, 75))
        self.assertFalse(self.window.GetChild("title").shown)
        self.assertEqual(self.window.GetChild("title").text, "Rex [Lv. 15]")

    def test_a_click_opens_it_and_it_folds_after_thirty_seconds(self):
        self.run_with(self.window.GetChild("image").OnMouseLeftButtonDown)
        self.tick(1.0)
        self.assertEqual(self.size(), (245, 135))
        self.assertTrue(self.window.GetChild("title").shown)
        self.tick(28.0)
        self.assertEqual(self.size(), (245, 135))
        self.tick(1.5)
        self.tick(1.0)
        self.assertEqual(self.size(), (75, 75))

    def test_a_second_click_folds_it(self):
        self.run_with(self.window.GetChild("image").OnMouseLeftButtonDown)
        self.tick(1.0)
        self.run_with(self.window.GetChild("image").OnMouseLeftButtonDown)
        self.tick(1.0)
        self.assertEqual(self.size(), (75, 75))

    def test_the_small_skill_cells_and_their_revert_drop(self):
        self.state.own["skills"][2] = [ps.APPLY_MAX_HP, 3, 100]
        self.run_with(self.window.RefreshSkillSlot)
        self.assertIn(("slot.SetPetSkillSlot", (2, ps.APPLY_MAX_HP, 0, 0.55, 0.55)), self.game.log)
        self.game.give(REVERT_CELL, ps.REVERT)
        self.world.attach(self.player.SLOT_TYPE_INVENTORY, REVERT_CELL, ps.REVERT)
        self.run_with(self.window.GetChild("skill_slot").fire, "select_item", 2)
        self.assertEqual(ps.sends(self.world), [("UseResetSkill", (self.player.INVENTORY, REVERT_CELL, 2))])

    def test_no_stamina_or_toggle_methods_are_left(self):
        """OLD bugs 2 and 3: methods that called names no module has."""
        for name in ("_PetInterfaceWindow__OverInStamina", "TogglePetWindow"):
            self.assertNotIn(name, vars(self.module.PetInterfaceWindow))
        self.assertNotIn("_PetWindow__UseSkillSlot", vars(self.module.PetWindow))
        for name in ("GetStamina", "TOOLTIP_PET_STAMINA", "GetSkillCooltime", "UseSkill", "PetInterfaceShow"):
            self.assertNotIn(name, read_root("uipet.py"))


class Helpers(Fixture):
    def test_the_grade_names_strip_olds_trailing_space(self):
        """OLD bug 8: "Mythic " found no key."""
        self.assertEqual(self.run_with(self.module.GetEvolveLocaleName, "Mythic "), self.locale.PET_EVOLVE_GRADE_MYTHIC)
        self.assertEqual(self.run_with(self.module.GetEvolveLocaleName, "Heroicplus"),
                         self.locale.PET_EVOLVE_GRADE_HEROICPLUS)

    def test_the_text_tooltip_has_its_own_name(self):
        """OLD bug 9: OLD's was named "GiftBox"."""
        self.assertNotIn("GiftBox", read_root("uipet.py"))

    def test_the_evolve_index(self):
        self.state.summon(level=15, exp=0)
        self.assertEqual(self.run_with(self.module.GetEvolveLevelIndex), 0)
        self.state.own["exp"] = 1
        self.assertEqual(self.run_with(self.module.GetEvolveLevelIndex), 1)
        self.state.own.update({"level": 105, "exp": 1})
        self.assertEqual(self.run_with(self.module.GetEvolveLevel), 105)


# --- game.py and the Interface ----------------------------------------------------------------------

class Recorder(object):
    def __init__(self, log, name, shown=False):
        self.log, self.name, self.shown = log, name, shown

    def __getattr__(self, attr):
        if attr.startswith("__"):
            raise AttributeError(attr)

        def record(*args):
            self.log.append((self.name, attr) + args)
            if attr in ("Open", "Show"):
                self.shown = True
            elif attr in ("Close", "Hide"):
                self.shown = False
        return record

    def IsShow(self):
        return self.shown


CALLBACKS = ["BINARY_PetSummon", "BINARY_PetPreview", "BINARY_PetRefreshStatus", "BINARY_PetRefreshSkill",
             "BINARY_PetAttrRefineInfo", "BINARY_PetEvolutionInfo", "BINARY_PetEvolveResult", "BINARY_PetUnsummon"]
PET_WINDOWS = ("wndPetEggHatch", "wndPetRefineWindow", "wndPetEvolutionWindow", "wndPetInterfaceWindow",
               "wndPetWindow", "wndPetPreviewWindow")


class GameCallbacks(unittest.TestCase):
    def setUp(self):
        self.log = []
        pet = types.SimpleNamespace(UpdateSkillProtoExpr=lambda *args: self.log.append(("pet.UpdateSkillProtoExpr",) + args))
        Game = compiled("game.py", "GameWindow", CALLBACKS, {"pet": pet})
        self.game = Game()
        interface = self.game.interface = types.SimpleNamespace(
            TogglePetWindow=lambda: self.log.append(("interface", "TogglePetWindow")))
        for name in PET_WINDOWS:
            setattr(interface, name, Recorder(self.log, name))

    def test_summon_opens_the_mini_window(self):
        self.game.BINARY_PetSummon()
        self.assertIn(("wndPetInterfaceWindow", "Open"), self.log)
        self.game.interface.wndPetWindow.shown = True
        self.game.BINARY_PetSummon()
        self.assertIn(("interface", "TogglePetWindow"), self.log, "OLD: an open pet window closes")

    def test_each_callback_reaches_its_window(self):
        self.game.BINARY_PetAttrRefineInfo(1, 500)
        self.game.BINARY_PetEvolutionInfo()
        self.game.BINARY_PetEvolveResult(1)
        self.game.BINARY_PetEvolveResult(0)
        self.game.BINARY_PetPreview()
        self.game.BINARY_PetRefreshSkill()
        del self.log[:]
        self.game.interface.wndPetRefineWindow.shown = False
        self.game.BINARY_PetRefreshStatus()
        self.game.interface.wndPetRefineWindow.shown = True
        self.game.BINARY_PetRefreshStatus()
        self.game.BINARY_PetUnsummon()
        self.assertEqual(self.log, [("wndPetWindow", "RefreshStatus"), ("wndPetInterfaceWindow", "RefreshStatus"),
                                    ("wndPetWindow", "RefreshStatus"), ("wndPetInterfaceWindow", "RefreshStatus"),
                                    ("wndPetRefineWindow", "Refresh"),
                                    ("wndPetInterfaceWindow", "Close"), ("wndPetWindow", "Close")])

    def test_the_results_and_the_preview(self):
        self.game.BINARY_PetAttrRefineInfo(1, 500)
        self.game.BINARY_PetEvolutionInfo()
        self.game.BINARY_PetEvolveResult(1)
        self.game.BINARY_PetEvolveResult(0)
        self.game.BINARY_PetPreview()
        self.game.BINARY_PetRefreshSkill()
        self.assertEqual([entry for entry in self.log if entry[0] != "pet.UpdateSkillProtoExpr"], [
            ("wndPetRefineWindow", "Open", 1, 500), ("wndPetEvolutionWindow", "Open"),
            ("wndPetEvolutionWindow", "OnEvolveSuccess"), ("wndPetEvolutionWindow", "OnEvolveFailure"),
            ("wndPetPreviewWindow", "Open", True),
            ("wndPetInterfaceWindow", "RefreshSkillSlot"), ("wndPetWindow", "RefreshSkillSlot")])

    def test_no_interface_no_error(self):
        self.game.interface = None
        for name in CALLBACKS:
            args = {"BINARY_PetAttrRefineInfo": (0, 0), "BINARY_PetEvolveResult": (1,)}.get(name, ())
            getattr(self.game, name)(*args)

    def test_the_keys_and_the_import(self):
        source = read_root("game.py")
        self.assertIn("import pet", source.split("\n"))
        # P and Tab are the defaults of NOVA-121's table (keybindings_game_test
        # presses them).
        self.assertIn('"pet": lambda: interface().TogglePetWindow()', source)
        self.assertIn('"next_target": self.__PressTabKey', source)
        self.assertIn("self.interface.PressTabKey()", source)
        table = read_root("keybindings.py")
        self.assertIn('Action("pet", "windows", "KEYBIND_PET", "Pet", (key("P"),))', table)
        self.assertIn('(key("TAB"),), hold=True)', table)


class Interface(unittest.TestCase):
    def setUp(self):
        Interface = compiled("interfacemodule.py", "Interface", ["TogglePetWindow", "PressTabKey"])
        self.log = []
        self.interface = Interface()
        for name in PET_WINDOWS:
            setattr(self.interface, name, Recorder(self.log, name))

    def test_toggle_opens_and_closes_the_pet_window(self):
        self.interface.TogglePetWindow()
        self.interface.TogglePetWindow()
        self.assertEqual(self.log, [("wndPetWindow", "Open"), ("wndPetWindow", "Close")])

    def test_tab_asks_the_shown_windows_until_one_takes_it(self):
        class Window(object):
            def __init__(self, shown, takes, log, name):
                self.shown, self.takes, self.log, self.name = shown, takes, log, name

            def IsShow(self):
                return self.shown

            def OnPressTabKey(self):
                self.log.append(self.name)
                return self.takes
        log = self.log
        self.interface.wndInventory = Window(True, False, log, "inventory")
        self.interface.wndExtraInventory = Window(False, True, log, "extra")
        self.interface.dlgExchange = Window(True, True, log, "exchange")
        self.interface.dlgShop = Window(True, True, log, "shop")
        self.interface.wndSearchShop = None
        self.assertTrue(self.interface.PressTabKey())
        self.assertEqual(log, ["inventory", "exchange"])

    def test_the_six_windows_are_made_with_contract_8s_ids(self):
        source = read_root("interfacemodule.py")
        self.assertIn("import uiPet", source.split("\n"))
        for line in ('self.wndPetEggHatch = nui_windows.make("pet-hatch", uiPet.PetHatchEggWindow, "nui_pet_hatch.PetHatchEggWindow")',
                     'self.wndPetRefineWindow = nui_windows.make("pet-attr-refine", uiPet.PetAttrRefineWindow, "nui_pet_attr_refine.PetAttrRefineWindow")',
                     'self.wndPetEvolutionWindow = nui_windows.make("pet-evolution", uiPet.PetEvolutionWindow, "nui_pet_evolution.PetEvolutionWindow")',
                     'self.wndPetInterfaceWindow = nui_windows.make("pet-mini", uiPet.PetInterfaceWindow, "nui_pet_mini.PetInterfaceWindow")',
                     'self.wndPetWindow = nui_windows.make("pet", uiPet.PetWindow, "nui_pet.PetWindow")',
                     'self.wndPetPreviewWindow = nui_windows.make("pet", uiPet.PetWindow, "nui_pet.PetWindow")',
                     "self.__MakePetWindows()"):
            self.assertIn(line, source)
        for name in PET_WINDOWS:
            self.assertIn("self.%s.Destroy()" % name, source)
            self.assertIn("self.%s = None" % name, source)

    def test_hide_all_and_hide_windows_take_the_pet_windows(self):
        Interface = compiled("interfacemodule.py", "Interface", ["HideAllWindows"],
                             {"app": types.SimpleNamespace(ENABLE_DRAGON_SOUL_SYSTEM=0)})
        interface = Interface()
        for name in ("wndMyShopDeco", "wndTaskBar", "wndEnergyBar", "wndCharacter", "wndInventory", "wndExtraInventory", "wndChat",
                     "wndMiniMap", "wndMessenger", "wndGuild", "wndExpandedTaskBar", "wndCubeRenewal"):
            setattr(interface, name, None)
        for name in PET_WINDOWS:
            setattr(interface, name, Recorder(self.log, name, True))
        interface.HideAllWindows()
        self.assertEqual(sorted(entry[0] for entry in self.log if entry[1] == "Hide"), sorted(PET_WINDOWS))
        self.assertIn("hideWindows += self.wndPetInterfaceWindow,", read_root("interfacemodule.py"))


# --- the inventory ------------------------------------------------------------------------------------------------

class Inventory(Fixture):
    def setUp(self):
        Fixture.setUp(self)
        self.inventory = w6.make_inventory(self.world)
        self.hatch = Recorder(self.game.log, "hatch")
        self.game.interface.wndPetEggHatch = self.hatch
        for cell, vnum in ((EGG_CELL, ps.EGG), (SEAL_CELL, ps.SEAL), (ORB_CELL, ps.ORB), (CHANGER_CELL, ps.NAME_CHANGER)):
            self.game.give(cell, vnum)
        del self.game.log[:]

    def entries(self, name):
        return [entry for entry in self.game.log if entry[0] == name]

    def test_using_an_egg_opens_the_hatch_window(self):
        self.run_with(self.inventory.UseItemSlot, EGG_CELL)
        self.assertEqual(self.entries("hatch"), [("hatch", "Open", EGG_CELL, self.player.INVENTORY)])
        self.assertFalse([entry for entry in self.game.log if entry[0].startswith("net.SendItemUse")])

    def test_the_name_changer_on_a_seal_opens_the_rename(self):
        self.world.attach(self.player.SLOT_TYPE_INVENTORY, CHANGER_CELL, ps.NAME_CHANGER)
        self.run_with(self.inventory.SelectItemSlot, SEAL_CELL)
        self.assertEqual(self.entries("hatch"), [("hatch", "Open", SEAL_CELL, self.player.INVENTORY, True)])
        self.assertFalse(self.world.mouse.isAttached())

    def test_the_orb_on_a_seal_asks_first(self):
        self.world.attach(self.player.SLOT_TYPE_INVENTORY, ORB_CELL, ps.ORB)
        self.run_with(self.inventory.SelectItemSlot, SEAL_CELL)
        opens = [args for name, args in self.game.log if name == "uiCommon.QuestionDialog.Open"]
        self.assertEqual(opens, [(self.locale.PET_ADVANCED_ORB_WARNING % ("item %d" % ps.SEAL), "")])
        dialog = [d for d in self.game.dialogs if d._name == "uiCommon.QuestionDialog"][-1]
        del self.game.log[:]
        self.run_with(dialog.accept)
        used = [args for name, args in self.game.log if "UseToItem" in name or "ItemUseToItem" in name]
        self.assertEqual(len(used), 1, self.game.log)
        self.assertIn(ORB_CELL, used[0])
        self.assertIn(SEAL_CELL, used[0])

    def test_the_orb_elsewhere_is_refused(self):
        """OLD's test let an egg or any pet item through (OLD bug 10)."""
        self.world.attach(self.player.SLOT_TYPE_INVENTORY, ORB_CELL, ps.ORB)
        self.run_with(self.inventory.SelectItemSlot, EGG_CELL)
        self.assertEqual(chats(self.world), [(self.game.modules["chat"].CHAT_TYPE_INFO, self.locale.PET_ADVANCED_ORB_ALERT)])

    def test_a_used_orb_is_refused_with_a_popup(self):
        self.player.GetItemAttribute = lambda *args: (63, -100)
        self.world.attach(self.player.SLOT_TYPE_INVENTORY, ORB_CELL, ps.ORB)
        self.run_with(self.inventory.SelectItemSlot, SEAL_CELL)
        self.assertEqual([texts[0] for texts in popups(self.world)], [self.locale.PET_ADVANCED_ORB_ALREADY_USED])

    def test_a_summoned_seal_glows(self):
        self.game.give(SEAL_CELL, ps.SEAL, sockets=(0, 0, 0, 1))
        self.run_with(self.inventory.RefreshBagSlotWindow)
        self.assertTrue(self.inventory.wndItem.slots[SEAL_CELL]["active"])
        self.game.give(SEAL_CELL, ps.SEAL, sockets=(0, 0, 0, 0))
        self.run_with(self.inventory.RefreshBagSlotWindow)
        self.assertFalse(self.inventory.wndItem.slots[SEAL_CELL]["active"])

    def test_tab_over_a_seal_previews_it(self):
        self.run_with(self.inventory.OverInItem, SEAL_CELL)
        self.assertTrue(self.run_with(self.inventory.OnPressTabKey))
        self.run_with(self.inventory.OverInItem, EGG_CELL)
        self.assertFalse(self.run_with(self.inventory.OnPressTabKey))
        self.run_with(self.inventory.OverInItem, SEAL_CELL)
        self.run_with(self.inventory.OverOutItem)
        self.assertFalse(self.run_with(self.inventory.OnPressTabKey))
        self.assertEqual(ps.sends(self.world), [("ReqPetPreview", (3, self.player.INVENTORY, SEAL_CELL))])


class TabPreviews(unittest.TestCase):
    """The other windows' Tab previews, with contract 6's argument forms."""

    def setUp(self):
        self.log = []
        self.item = types.SimpleNamespace(selected=[0], ITEM_TYPE_PET_ADVANCED=39, PET_SUMMON=1)
        self.item.SelectItem = lambda vnum: self.item.selected.__setitem__(0, vnum)
        self.item.GetItemType = lambda: 39 if self.item.selected[0] in ps.PET_ITEMS else 1
        self.item.GetItemSubType = lambda: ps.PET_ITEMS.get(self.item.selected[0], (0,))[0]
        self.pet = types.SimpleNamespace(ReqPetPreview=lambda *args: self.log.append(args), **ps.PET_CONSTANTS)
        patcher = mock.patch.dict(sys.modules, {"pet": self.pet})
        patcher.start()
        self.addCleanup(patcher.stop)

    def namespace(self, **more):
        names = {"item": self.item, "pet": self.pet}
        names.update(more)
        return names

    def test_extra_inventory(self):
        player = types.SimpleNamespace(EXTRA_INVENTORY=6, GetItemIndex=lambda window, cell: ps.SEAL)
        Window = compiled("uiextrainventory.py", "ExtraInventoryWindow", ["OnPressTabKey"],
                          self.namespace(player=player))
        window = Window()
        window.tabPreviewCell = 700
        self.assertTrue(window.OnPressTabKey())
        window.tabPreviewCell = -1
        self.assertFalse(window.OnPressTabKey())
        self.assertEqual(self.log, [(3, 6, 700)])

    def test_exchange_both_sides(self):
        exchange = types.SimpleNamespace(GetItemVnumFromSelf=lambda slot: ps.SEAL,
                                         GetItemVnumFromTarget=lambda slot: ps.SEAL if slot == 2 else 10)
        Window = compiled("uiexchange.py", "ExchangeDialog", ["OnPressTabKey"],
                          self.namespace(exchange=exchange, PET_PREVIEW_EXCHANGE_SELF=1))
        window = Window()
        window.tabPreviewItem = (1, 4)
        self.assertTrue(window.OnPressTabKey())
        window.tabPreviewItem = (2, 2)
        self.assertTrue(window.OnPressTabKey())
        window.tabPreviewItem = (2, 3)
        self.assertFalse(window.OnPressTabKey())
        window.tabPreviewItem = None
        self.assertFalse(window.OnPressTabKey())
        self.assertEqual(self.log, [(1, 4), (2, 2)])

    def test_offline_shop(self):
        shop = types.SimpleNamespace(GetOfflineShopItemID=lambda slot: ps.SEAL)
        Window = compiled("uishop.py", "ShopDialog", ["OnPressTabKey"], self.namespace(shop=shop))
        window = Window()
        window.isOfflineShop, window.hoveredSlot = True, 12
        self.assertTrue(window.OnPressTabKey())
        window.isOfflineShop = False
        self.assertFalse(window.OnPressTabKey(), "an NPC shop has no pet preview")
        self.assertEqual(self.log, [(4, 12)])

    def test_search_shop_passes_the_rows_owner(self):
        Window = compiled("uisearchshop.py", "SearchShopWindow", ["OnPressTabKey"], self.namespace())
        window = Window()
        window.tabPreviewRow = {"vnum": ps.SEAL, "slot": 6, "owner_pid": 1234}
        self.assertTrue(window.OnPressTabKey())
        window.tabPreviewRow = {"vnum": 10, "slot": 6, "owner_pid": 1234}
        self.assertFalse(window.OnPressTabKey())
        self.assertEqual(self.log, [(5, 6, 1234)])

    def test_the_hover_handlers_keep_the_cell(self):
        for file_name, needle in (("uiextrainventory.py", "self.tabPreviewCell = overSlotPos"),
                                  ("uiexchange.py", "self.tabPreviewItem = (PET_PREVIEW_EXCHANGE_SELF, slotIndex)"),
                                  ("uiexchange.py", "self.tabPreviewItem = (PET_PREVIEW_EXCHANGE_OTHER, slotIndex)"),
                                  ("uisearchshop.py", "self.tabPreviewRow = row"),
                                  ("uiinventory.py", "self.tabPreviewCell = overSlotPos")):
            self.assertIn(needle, read_root(file_name), file_name)
        for file_name in ("uisearchshop.py", "uiextrainventory.py"):
            self.assertNotIn("pet preview (Tab) have no host", read_root(file_name))
            self.assertNotIn("pet preview are not ported", read_root(file_name))


# --- the tooltips and the slot ------------------------------------------------------------------------------------

PET_ROW = dict(lf.ITEM_BASE, name="Monkey Seal", type=39, subtype=1, icon="icon/item/55701.tga",
               limits=[[0, 0], [0, 0]])
EGG_ROW = dict(lf.ITEM_BASE, name="Monkey Egg", type=39, subtype=0, icon="icon/item/55401.tga",
               limits=[[7, 604800], [0, 0]])


class ToolTips(unittest.TestCase):
    ITEMS = {ps.SEAL: PET_ROW, ps.EGG: EGG_ROW}

    def texts(self, vnum, sockets=(0, 0, 0, 0), attrs=(), context="SetInventoryItem"):
        corpus_tool, world = w6.tooltip_world(self.ITEMS)
        texts, error = w6.tooltip_texts(corpus_tool, world, {"context": context, "vnum": vnum,
                                                              "sockets": list(sockets), "attrs": list(attrs)})
        self.assertIsNone(error)
        return texts, world.game.modules["localeInfo"]

    def test_a_seal_shows_the_tab_hint_and_its_orb_bonus(self):
        texts, locale = self.texts(ps.SEAL, attrs=[[63, -100]])
        self.assertIn(locale.PET_TOOLTIP_TAB_PREVIEW, texts)
        self.assertTrue([text for text in texts if "-100" in text], texts)

    def test_an_egg_shows_when_it_hatches_and_its_expiry(self):
        texts, locale = self.texts(ps.EGG, sockets=(1700000000 + 86400 * 7, 1700000000 + 7200, 0, 0))
        self.assertIn(locale.PET_EGG_HATCH_IN % locale.SecondToDHM(7200), texts)
        self.assertNotIn(locale.PET_TOOLTIP_TAB_PREVIEW, texts)
        texts, locale = self.texts(ps.EGG, sockets=(1700000000 + 86400 * 7, 0, 0, 0))
        self.assertFalse([text for text in texts if text.startswith(locale.PET_EGG_HATCH_IN.split("%")[0])])

    def test_the_tab_hint_is_a_key_without_emoji(self):
        """OLD bug 7: a hard-coded English line with an emoji NEW lacks."""
        source = read_root("uitooltip.py")
        self.assertNotIn("key_tab.tga", source)
        self.assertIn("localeInfo.PET_TOOLTIP_TAB_PREVIEW", source)

    def test_the_skill_tooltip_reads_the_servers_value(self):
        corpus_tool, world = w6.tooltip_world({})
        state = ps.install(world.game)
        state.summon()
        state.own["skills"][0] = [ps.APPLY_MAX_HP, 5, 250]
        state.preview["skills"][0] = [ps.APPLY_MAX_HP, 2, 90]
        module = world.game.loaded["uiToolTip"]
        locale = world.game.modules["localeInfo"]
        with world.game, lf.quiet():
            tip = module.PetSkillToolTip()
            tip.SetSkill(ps.APPLY_MAX_HP, 5)
            rows = [row[1] for row in corpus_tool.stand_in_rows(tip) if row[0] == "text"]
            tip.SetSkill(ps.APPLY_MAX_HP, 2, True)
            preview_rows = [row[1] for row in corpus_tool.stand_in_rows(tip) if row[0] == "text"]
            tip.SetSkill(0, 0)
        self.assertIn("Heart of the Titan", rows)
        self.assertIn(locale.PET_TOOLTIP_SKILL_CUR_LEVEL % 5, rows)
        self.assertIn(locale.TOOLTIP_MAX_HP(250), rows)
        self.assertIn(locale.TOOLTIP_MAX_HP(90), preview_rows)


    def test_the_skill_description_keeps_the_tooltips_color(self):
        """OLD passed its wrap width (30) where NEW's AppendDescription takes
        the color (OLD bug 12 of the port)."""
        corpus_tool, world = w6.tooltip_world({})
        state = ps.install(world.game)
        state.summon()
        module = world.game.loaded["uiToolTip"]
        with world.game, lf.quiet():
            tip = module.PetSkillToolTip()
            tip.SetSkill(ps.APPLY_MAX_HP, 5)
            rows = corpus_tool.stand_in_rows(tip)
        colors = [row[2] for row in rows if row[0] == "text" and row[1].startswith("Increases")]
        self.assertTrue(colors)
        self.assertNotIn(30, colors)


class SlotWindow(unittest.TestCase):
    def test_set_pet_skill_slot_sets_the_icon_and_the_level(self):
        log = []
        wndmgr = types.SimpleNamespace(SetSlot=lambda *args: log.append(("SetSlot",) + args),
                                       SetSlotCount=lambda *args: log.append(("SetSlotCount",) + args),
                                       ClearSlot=lambda *args: log.append(("ClearSlot",) + args))
        pet = types.SimpleNamespace(GetSkillProtoIconImage=lambda vnum: "image-%d" % vnum if vnum == 1 else 0)
        Slot = compiled("ui.py", "SlotWindow", ["SetPetSkillSlot"], {"wndMgr": wndmgr, "pet": pet})
        slot = Slot()
        slot.hWnd = 77
        with mock.patch.dict(sys.modules, {"pet": pet}):
            slot.SetPetSkillSlot(0, 1, 5)
            slot.SetPetSkillSlot(1, 2, 5, 0.55, 0.55)
        self.assertEqual(log, [("SetSlot", 77, 0, 1, 1, 1, "image-1"), ("SetSlotCount", 77, 0, 5), ("ClearSlot", 77, 1)])


if __name__ == "__main__":
    unittest.main()
