"""Tests of the NovaUI pet window (assets/root/nui_pet.py; NOVA-24, chunk N):
python3 -B -m unittest nui_pet_test (from tools/).

Each flow runs on legacy's uipet.PetWindow and on the NovaUI subclass in the
same kind of world (nui_w4_world's, with chunk C's pet module from Y's
pet_support), and the effects must be the same: the pet module's requests
and their arguments, the chat lines, the dialogs, the skill tooltip's calls.
The NovaUI side also checks what the board shows (the lines, the grade's
color, the bonus rows, the evolve button at and between gates, the skill
cells and their locks, the hint), the two instances (own and preview) with
their own models, that no Python runs per frame, the lifecycle, that the
loader binds as legacy's does, and that every fixture has every model key.

World and the helpers here serve the other pet window tests too
(nui_pet_mini_test, nui_pet_hatch_test, nui_pet_evolution_test,
nui_pet_attr_refine_test)."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402
import pet_support as ps  # noqa: E402

support = w4.support
# The tooltips stay legacy's stand-ins here ("tooltips" is off): the pet skill
# tooltip's facade is tested over the real uitooltip.py (PetSkillTooltip).
NUI_MODULES = ("nui_limits", "nui_proxies", "nui_form_proxies", "nui_facade", "nui_text", "nui_pet", "nui_pet_mini",
               "nui_pet_hatch", "nui_pet_evolution", "nui_pet_attr_refine")
REVERT_CELL, ORB_CELL = 7, 8
COMPARED = ("pet.", "chat.AppendChat", "uiCommon.", "PetSkillToolTip.", "net.")


def setup(game):
    """Chunk C's pet module and names, ui.py's SetPetSkillSlot and the pet
    skill tooltip on the stand-ins, the revert and the orb in the bag."""
    ps.install(game)
    ps.install_ui(game)
    game.put("uiScriptLocale", ps.locale_module("locale_interface.txt"))
    game.give(REVERT_CELL, ps.REVERT)
    game.give(ORB_CELL, ps.ORB)


class World(w4.World):
    """One side: legacy's uipet classes (nui_on False) or the NovaUI ones."""

    def __init__(self, nui_on):
        w4.World.__init__(self, nui_on, windows="+pet,+pet-mini,+pet-hatch,+pet-evolution,+pet-attr-refine",
                          setup=setup, modules=())
        self.state = self.game.pet_state
        with self.game, w4.quiet():
            self.game.load("uiPet", "uipet.py")
            if nui_on:
                for name in NUI_MODULES:
                    if os.path.isfile(os.path.join(w4.ROOT, name + ".py")):
                        self.game.load(name, name + ".py")

    def make(self, legacy_name, nui_module=None):
        """The window the Interface makes: legacy's class, or the NovaUI
        subclass (contract 8's controllers)."""
        with self.game, w4.quiet():
            if self.nui_on and nui_module:
                return getattr(self.game.loaded[nui_module], legacy_name)()
            return getattr(self.game.loaded["uiPet"], legacy_name)()

    def run(self, call, *args):
        with self.game, w4.quiet():
            return call(*args)

    def effects_since(self, mark):
        return [(name, args) for name, args in self.game.log[mark:]
                if name.startswith(COMPARED) and not support.is_getter(name)]


def model(window):
    return w4.board(window).model


def run_both(test, prepare, flow):
    """prepare(world) then flow(world, window) on both sides; the effects
    must be equal. Returns (legacy world, its window, novaui world, its
    window)."""
    results = []
    for nui_on in (False, True):
        world = World(nui_on)
        window = prepare(world)
        mark = world.mark()
        with world.game, w4.quiet():
            flow(world, window)
        results.append((world.effects_since(mark), world, window))
    (legacy, lworld, lwindow), (novaui, nworld, nwindow) = results
    test.assertEqual(novaui, legacy)
    return lworld, lwindow, nworld, nwindow


def handler_name(event):
    if event is None:
        return None
    fn = getattr(event, "call", event)
    fn = getattr(fn, "func", fn)
    fn = getattr(fn, "__func__", fn)
    try:
        fn = fn.__repr__.__self__ if False else fn
        return getattr(fn, "__name__", repr(type(fn)))
    except ReferenceError:
        return "dead"


def summon(world, level=100, exp=0):
    state = world.state
    state.summon(level=level, exp=exp, next_exp=4000)
    state.own["attrs"] = [[ps.APPLY_MAX_HP, 12, 1200, 1], [ps.APPLY_CRITICAL_PCT, 9, 9, 1], [ps.APPLY_BLOCK, 20, 20, 0]]
    for slot in range(8):
        state.own["skills"][slot] = [ps.APPLY_MAX_HP if slot % 2 == 0 else ps.APPLY_HP_REGEN, 20 - slot, 100 + slot]
    state.own["skills"][10] = [86, 4, 3]


def opened(world, preview=False):
    summon(world)
    window = world.make("PetWindow", "nui_pet")
    world.run(window.Open, preview)
    return window


# --- the board's and legacy's controls -------------------------------------------------------------

def press_plus(world, window, index):
    if world.nui_on:
        w4.press(window, "plus_press", index, 0)
    else:
        window.GetChild("bonus%d_plus_btn" % (index + 1)).event()


def press_level(world, window, index):
    if world.nui_on:
        w4.press(window, "level_press", index, 0)
    else:
        window.GetChild("bonus%d_level_bg" % (index + 1)).OnMouseLeftButtonDown()


def press_evolve(world, window):
    if world.nui_on:
        w4.press(window, "evolve_press", 0)
    else:
        window.GetChild("evolution_upgrade").event()


def press_close(world, window):
    if world.nui_on:
        w4.press(window, "close_press", 0)
    else:
        window.GetChild("CloseBtn").event()


def cell_press(world, window, index, slot_name="skill_slot"):
    if world.nui_on:
        w4.press(window, "cell_press", index, 0)
    else:
        window.GetChild(slot_name).fire("select_item", index)


def cell_over(world, window, index, slot_name="skill_slot"):
    if world.nui_on:
        w4.fire(window, "cell_over", index)
    else:
        window.GetChild(slot_name).fire("over_in", index)


def hover(world, window, child, nui_event, *args):
    if world.nui_on:
        w4.fire(window, nui_event, *args)
    else:
        window.GetChild(child).OnMouseOverIn()


class Flows(unittest.TestCase):
    def test_the_plus_and_the_level_ask_the_refine_info(self):
        lworld, lwindow, nworld, nwindow = run_both(
            self, opened, lambda world, window: (press_plus(world, window, 0), press_level(world, window, 1)))
        self.assertEqual([args for name, args in nworld.game.log if name == "pet.RequestAttrRefineInfo"], [(0,), (1,)])

    def test_evolve_asks_the_evolution_info(self):
        lworld, lwindow, nworld, nwindow = run_both(self, opened, press_evolve)
        self.assertIn(("pet.RequestEvolutionInfo", ()), nworld.game.log)

    def test_a_revert_dropped_on_a_skill_resets_it(self):
        def flow(world, window):
            world.attach(w4.P["SLOT_TYPE_INVENTORY"], REVERT_CELL, ps.REVERT)
            cell_press(world, window, 2)
        lworld, lwindow, nworld, nwindow = run_both(self, opened, flow)
        self.assertIn(("pet.UseResetSkill", (w4.P["INVENTORY"], REVERT_CELL, 2)), nworld.game.log)
        self.assertFalse(nworld.mouse.isAttached())

    def test_another_item_dropped_resets_nothing(self):
        def flow(world, window):
            world.attach(w4.P["SLOT_TYPE_INVENTORY"], ORB_CELL, ps.ORB)
            cell_press(world, window, 2)
        lworld, lwindow, nworld, nwindow = run_both(self, opened, flow)
        self.assertNotIn("pet.UseResetSkill", [name for name, args in nworld.game.log])

    def test_a_skill_hover_shows_the_pet_skill_tooltip(self):
        lworld, lwindow, nworld, nwindow = run_both(self, opened, lambda world, window: cell_over(world, window, 10))
        self.assertIn(("PetSkillToolTip.SetSkill", (86, 4, False)), nworld.game.log)

    def test_the_preview_reads_the_preview_table(self):
        def prepare(world):
            world.state.preview.update({"item_vnum": 55705, "name": "Spot", "level": 30, "exp": 0, "next_exp": 100})
            world.state.preview["skills"][1] = [ps.APPLY_HP_REGEN, 7, 4]
            window = world.make("PetWindow", "nui_pet")
            world.run(window.Open, True)
            return window
        lworld, lwindow, nworld, nwindow = run_both(self, prepare, lambda world, window: cell_over(world, window, 1))
        self.assertIn(("PetSkillToolTip.SetSkill", (ps.APPLY_HP_REGEN, 7, True)), nworld.game.log)
        board = model(nwindow)
        self.assertTrue(board["preview"])
        self.assertIn("Spot", board["name"])

    def test_close(self):
        lworld, lwindow, nworld, nwindow = run_both(self, opened, press_close)
        self.assertFalse(nwindow.IsShow())
        self.assertIsNone(w4.board(nwindow))


class Board(unittest.TestCase):
    def test_the_status_lines_and_the_grade_color(self):
        world = World(True)
        window = opened(world)
        board = model(window)
        locale = world.game.modules["localeInfo"]
        self.assertIn("Rex", board["name"])
        self.assertIn("(100)", board["level"])
        self.assertIn(locale.PET_EVOLVE_GRADE_HEROIC, board["evolution"])
        self.assertEqual(board["evolution_color"], "#89d3f9", "OLD's Heroic color")
        self.assertEqual(board["portrait"], "d:/ymir work/ui/pet/panel_info/icon_pets/55701.png")
        self.assertEqual(board["bonuses"][0], {"name": "Max HP", "level": "Lv.12 - 1200", "plus": True})
        self.assertFalse(board["bonuses"][2]["plus"])

    def test_the_evolve_button_blinks_at_a_gate_and_waits_between(self):
        world = World(True)
        window = opened(world)
        board = model(window)
        self.assertEqual((board["evolve_shown"], board["evolve_enabled"], board["evolve_flash"]), (True, True, True))
        world.state.own.update({"level": 101, "exp": 5})
        world.run(window.RefreshStatus)
        board = model(window)
        self.assertEqual((board["evolve_shown"], board["evolve_enabled"], board["evolve_flash"]), (True, False, False))
        world.state.own.update({"level": 105, "exp": 5})
        world.run(window.RefreshStatus)
        self.assertFalse(model(window)["evolve_shown"])

    def test_the_cells_and_their_locks(self):
        world = World(True)
        window = opened(world)
        board = model(window)
        # Heroic (100, 0 exp: not evolved yet): 8 basic cells and 1 heroic open.
        self.assertEqual(board["disabled"], [False] * 8 + [True, True] + [False, True, True])
        self.assertEqual(board["cells"][0]["icon"], "d:/ymir work/ui/pet/skill/normal/MAX_HP.png")
        self.assertEqual(board["cells"][0]["count"], "20")
        self.assertEqual(board["cells"][9]["kind"], "")

    def test_the_hint_follows_a_refresh(self):
        world = World(True)
        window = opened(world)
        world.state.own["exp"] = 1000
        world.run(window.RefreshStatus)
        w4.fire(window, "exp_over")
        locale = world.game.modules["localeInfo"]
        self.assertEqual(model(window)["hint"], locale.TARGET_INFO_EXP % "25.00%")
        world.state.own["exp"] = 2000
        world.run(window.RefreshStatus)
        self.assertEqual(model(window)["hint"], locale.TARGET_INFO_EXP % "50.00%", "legacy's OnUpdate rule, at the refresh")
        w4.fire(window, "exp_out")
        self.assertEqual(model(window)["hint"], "")
        w4.fire(window, "bonus_over", 0)
        self.assertEqual(model(window)["hint"], locale.TOOLTIP_PET_ATTR_INFO % (12, "Max HP +1200"))

    def test_own_and_preview_bind_their_own_models(self):
        world = World(True)
        own = opened(world)
        world.state.preview.update({"item_vnum": 55705, "name": "Spot", "level": 30, "exp": 0, "next_exp": 100})
        preview = world.make("PetWindow", "nui_pet")
        world.run(preview.Open, True)
        self.assertIsNot(w4.board(own), w4.board(preview))
        self.assertIn("Rex", model(own)["name"])
        self.assertIn("Spot", model(preview)["name"])
        self.assertTrue(type(w4.board(own)).INSTANCED)

    def test_every_fixture_has_every_model_key(self):
        world = World(True)
        window = opened(world)
        keys = w4.model_kinds(model(window))
        for variant in ("", "preview", "young"):
            with self.subTest(variant=variant):
                self.assertEqual(w4.fixture_keys(window, "pet", variant), keys)
                cells = w4.fixture_model("pet", variant)["cells"]
                self.assertEqual([sorted(c) for c in cells], [sorted(c) for c in model(window)["cells"]])


class PetSkillTooltip(unittest.TestCase):
    """nui_pet_skill_tooltip.PetSkillToolTip over the real uitooltip.py: the
    facade's lines are legacy's rows (nui_tooltip_corpus's two worlds)."""

    def lines(self, recorder, preview=False):
        import nui_tooltip_corpus as corpus_tool
        world = corpus_tool.TipWorld({"items": {}, "skills": {}, "mobs": {}}, recorder=recorder)
        state = ps.install(world.game)
        state.summon()
        state.own["skills"][0] = [ps.APPLY_MAX_HP, 5, 250]
        state.preview["skills"][0] = [ps.APPLY_MAX_HP, 2, 90]
        with world, w4.quiet():
            if recorder:
                world.game.load("nui_pet_skill_tooltip", "nui_pet_skill_tooltip.py")
                tip = world.m("nui_pet_skill_tooltip").PetSkillToolTip()
            else:
                tip = world.m("uiToolTip").PetSkillToolTip()
            tip.SetSkill(ps.APPLY_MAX_HP, 5 if not preview else 2, preview)
            if not recorder:
                return [row[1] for row in corpus_tool.stand_in_rows(tip) if row[0] == "text"], tip
            return [" ".join(run["text"] for run in line["runs"]) for line in tip._model["lines"] if line["t"] == "line"], tip

    def test_the_facade_shows_legacys_lines(self):
        for preview in (False, True):
            with self.subTest(preview=preview):
                legacy, _ = self.lines(False, preview)
                novaui, tip = self.lines(True, preview)
                self.assertEqual(novaui, legacy)
                self.assertIn("Max. HP +%d" % (90 if preview else 250), novaui)
                self.assertEqual(tip.KIND, "skill", "the skill tooltip's board")


class NoPerFramePython(unittest.TestCase):
    def test_the_facade_runs_no_python_per_frame(self):
        world = World(True)
        window = opened(world)
        self.assertIsNone(type(window).OnUpdate)
        self.assertIsNone(type(window).OnRender)


class Lifecycle(unittest.TestCase):
    def test_hide_and_show_before_the_legacy_init_do_not_raise(self):
        world = World(True)
        window = opened(world)
        cls = type(window)
        bare = cls.__new__(cls)
        with world.game, w4.quiet():
            bare.nui_begin()
            bare.Hide()
            bare.Show()

    def test_destroy_takes_the_board(self):
        world = World(True)
        window = opened(world)
        world.run(window.Destroy)
        self.assertIsNone(w4.board(window))


class LoaderBindsAsLegacy(unittest.TestCase):
    """The loader replicates legacy's __LoadWindow on proxies: the same
    widgets under the same keys, each handler on the same event."""

    def test_the_bindings(self):
        a, b = opened(World(False)), opened(World(True))
        self.assertEqual(sorted(a.main), sorted(b.main))
        self.assertEqual(len(a.main["skill_disabled"]), len(b.main["skill_disabled"]))
        theirs = dict((key, handler_name(value)) for key, value in a.main["skill"].events.items() if value)
        mine = dict((key, handler_name(value)) for key, value in b.main["skill"].handlers().items() if value)
        self.assertEqual(mine, theirs)
        for i in range(3):
            for name in ("OnMouseOverIn", "OnMouseOverOut", "OnMouseLeftButtonDown"):
                self.assertIn(name, vars(b.main["bg"][i]["level"]))
                self.assertTrue(callable(getattr(a.main["bg"][i]["level"], name)))
            self.assertIsNotNone(b.main["bonus"][i]["plus"].event)
        self.assertEqual(b.main["evolution_upgrade"].event.__name__, "RequestEvolutionInfo")


if __name__ == "__main__":
    unittest.main()
