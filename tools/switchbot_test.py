"""Tests of the switchbot (NOVA-43): the legacy window (assets/root/uiswitchbot.py,
OLD root/uiSwitchbot.py) and its NovaUI facade (assets/root/nui_switchbot.py),
the game, Interface, inventory and mouse hooks, and the locale keys:
python3 -B -m unittest switchbot_test (from tools/).

The C++ half (the switchbot module over GC/CG::SWITCHBOT, player.SWITCHBOT
and SLOT_TYPE_SWITCHBOT, the RefreshSwitchbotWindow and RefreshSwitchbotItem
calls) is the client fork's (.nui-work/w7/switchbot-contract.md); here a
stand-in switchbot module keeps what the server last said (Switchbot below)
and records every call. Each flow runs on the legacy window and on the
facade in the Wave 4 test world, and the effects (the packets, the
switchbot module's calls, the mouse) must be the same; the NovaUI side also
checks what the board shows."""

import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402

support = w4.support
ROOT = w4.ROOT
REPO = os.path.dirname(HERE)
LOCALES = os.path.join(REPO, "assets", "locale", "locale")

# The client fork's names (switchbot-contract.md): window 10 (EWindows), the
# slot type after the extra inventory's 12, the module's constants.
SWITCHBOT_WINDOW = 10
SLOT_TYPE_SWITCHBOT = 13
COST_ITEM, COST_YANG = 0, 1
SWORD, BLADE, AURA = 11, 19, 149001
HP, INT, CRIT, PIERCE, SKILL_DMG, HIT_DMG = 1, 4, 15, 16, 71, 72
EFFECTS = w4.EFFECT_MODULES + ("switchbot",)
AFFECTS = {HP: "Max. HP +%d", INT: "Intelligence +%d", CRIT: "Critical Hit +%d%%", PIERCE: "Piercing Hit +%d%%",
           SKILL_DMG: "Skill Damage %d%%", HIT_DMG: "Average Damage %d%%"}
MAX = {HP: 2000, INT: 12, CRIT: 10, PIERCE: 10}
RARE_MAX = {SKILL_DMG: 20, HIT_DMG: 60}


class Switchbot(object):
    """What C's CPythonSwitchbot holds: the server's state (active, finished,
    rare, cost per slot, the roll interval and the yang price), the targets
    the window edits, and the bonuses a target may name."""

    def __init__(self):
        self.active = set()
        self.finished = set()
        self.rare = {}
        self.cost = {}
        self.roll_ms = 250
        self.yang_price = 10000
        self.targets = {}
        self.aura_slots = set()

    def get(self, slot, alt, index):
        return self.targets.get((slot, alt, index), (0, 0))

    def put(self, slot, alt, index, kind, value):
        self.targets[(slot, alt, index)] = (kind, value)

    def clear(self, slot):
        for key in [key for key in self.targets if key[0] == slot]:
            del self.targets[key]


def install(game, bot):
    """The client fork's names and the stand-in switchbot module."""
    player, item = game.modules["player"], game.modules["item"]
    player.SWITCHBOT = SWITCHBOT_WINDOW
    player.SLOT_TYPE_SWITCHBOT = SLOT_TYPE_SWITCHBOT
    # main's exe (wave 4b): the special inventory's window and slot type.
    for name, value in (("EXTRA_INVENTORY", 6), ("SLOT_TYPE_EXTRA_INVENTORY", 12), ("METIN_SOCKET_MAX_NUM", 4),
                        ("ATTRIBUTE_SLOT_MAX_NUM", 7)):
        if not isinstance(player.__dict__.get(name), int):
            setattr(player, name, value)
    item.APPLY_SKILL_DAMAGE_BONUS = SKILL_DMG
    item.APPLY_NORMAL_HIT_DAMAGE_BONUS = HIT_DMG
    attrs = game.switchbot_attrs = {}
    support.define(player, "GetItemAttribute",
                   lambda *at: attrs.get(tuple(at), (0, 0)) if len(at) == 3 else (0, 0))
    support.define(player, "GetItemLink", lambda *at: "|Hitem:%d|h[item]|h" % game._item_at(*at)["vnum"])
    module = support.Recording("switchbot", game.log, SLOT_COUNT=6, ALTERNATIVE_COUNT=3, ATTRIBUTE_COUNT=7,
                               COST_ITEM=COST_ITEM, COST_YANG=COST_YANG)
    define = lambda name, fn: support.define(module, name, fn)
    define("IsActive", lambda slot: slot in bot.active)
    define("IsFinished", lambda slot: slot in bot.finished)
    define("IsRare", lambda slot: bot.rare.get(slot, 0))
    define("GetCost", lambda slot: bot.cost.get(slot, COST_ITEM))
    define("GetRollMs", lambda: bot.roll_ms)
    define("GetYangPrice", lambda: bot.yang_price)
    define("IsAuraSlot", lambda slot: slot in bot.aura_slots)
    define("GetAttribute", bot.get)
    define("GetRareAttributeByIndex", bot.get)
    define("GetAttributesForSet", lambda slot: sorted(MAX.items()))
    define("GetRareAttributesForSet", lambda slot: sorted(RARE_MAX.items()))
    define("GetAuraAttributesForSet", lambda slot: [(HP, 500)])
    define("GetAttributeMaxValue", lambda slot, kind: MAX.get(kind, 0))
    define("GetRareAttributeMaxValue", lambda slot, kind: RARE_MAX.get(kind, 0))
    define("GetAuraAttributeMaxValue", lambda slot, kind: 500 if kind == HP else 0)
    for name in ("SetAttribute", "SetRareAttribute"):
        module.__dict__[name] = support.recorded(game.log, "switchbot." + name, bot.put)
    module.__dict__["ClearSlot"] = support.recorded(game.log, "switchbot.ClearSlot", bot.clear)
    game.put("switchbot", module)
    tooltip = game.modules["uiToolTip"]
    tooltip.ItemToolTip.AFFECT_DICT = dict((kind, (lambda text: lambda value: text % value)(text))
                                           for kind, text in AFFECTS.items())
    locale = game.modules["localeInfo"]
    if not callable(getattr(locale, "NumberToMoneyString", None)):
        locale.NumberToMoneyString = lambda n: "%d Yang" % n
    return module


def world(nui_on, bot=None, items=((0, SWORD), (2, BLADE))):
    bot = bot or Switchbot()

    def setup(game):
        install(game, bot)
        for entry in items:
            slot, vnum, height = (tuple(entry) + (2,))[:3]
            game.give((SWITCHBOT_WINDOW, slot), vnum, size=(1, height))
            # Five normal bonuses and the two rare ones.
            for i, kind in enumerate((HP, INT, CRIT, PIERCE, 9, SKILL_DMG, HIT_DMG)):
                game.switchbot_attrs[(SWITCHBOT_WINDOW, slot, i)] = (kind, 5)
    game_world = w4.World(nui_on, windows="+switchbot", setup=setup)
    with game_world.game, w4.quiet():
        game_world.game.load("uiSwitchbot", "uiswitchbot.py")
        if nui_on:
            game_world.game.load("nui_switchbot", "nui_switchbot.py")
    window = game_world.make("switchbot", "uiSwitchbot", "SwitchbotWindow", "nui_switchbot.SwitchbotWindow")
    with game_world.game, w4.quiet():
        window.SetItemToolTip(game_world.tooltip)
        window.Open()
    game_world.bot = bot
    return game_world, window


class SwitchbotTest(unittest.TestCase):
    def run_both(self, flow, bot_setup=None):
        results = []
        for nui_on in (False, True):
            bot = Switchbot()
            if bot_setup:
                bot_setup(bot)
            game_world, window = world(nui_on, bot)
            mark = game_world.mark()
            with game_world.game, w4.quiet():
                flow(game_world, window)
            results.append(game_world.effects_since(mark, EFFECTS))
        legacy, novaui = results
        self.assertEqual(novaui, legacy)
        return legacy

    # --- the same press on either side ------------------------------------------------

    @staticmethod
    def slot(game_world, window, index, button=0, kind="select"):
        if game_world.nui_on:
            if kind == "use":
                w4.fire(window, "slot_use", index)
            else:
                w4.press(window, "slot_press", index, button)
        else:
            slots = window.itemSlot
            item = bool(game_world.game.modules["player"].GetItemIndex(SWITCHBOT_WINDOW, index))
            if kind == "use":
                slots.events["use"](index)
            elif button == 1:
                slots.events["unselect_item"](index)
            else:
                slots.events["select_item" if item else "select_empty"](index)

    @staticmethod
    def button(game_world, window, name, *args):
        """A press on a button: the board's event, or legacy's widget."""
        if game_world.nui_on:
            w4.press(window, name, *(args + (0,)))
            return
        target = {"tab_press": lambda: window.selectButtons[args[0]],
                  "alt_press": lambda: window.alternativeButtons[args[0]],
                  "cost_press": lambda: window.costButtons[args[0]],
                  "start_press": lambda: window.startstopButton,
                  "save_press": lambda: window.saveButton,
                  "row_pick": lambda: _row_of(window, args[0]).searchTypeButton,
                  "row_clear": lambda: _row_of(window, args[0]).deleteAttributeButton,
                  "row_minus": lambda: _row_of(window, args[0]).leftArrow,
                  "row_plus": lambda: _row_of(window, args[0]).rightArrow}
        if name == "rare_press":
            window.rareButton.click()   # the stand-in's CToggleButton press
            return
        click(target[name]())

    @staticmethod
    def pick(game_world, window, index):
        """A press on the search list's line `index`, then accept."""
        if game_world.nui_on:
            w4.press(window, "picker_item", index, 0)
            w4.press(window, "picker_accept", 0)
        else:
            picker = window.attributeSearchWindow
            key, value = picker.VisibleItems()[index]
            picker.Accept(key, value)

    @staticmethod
    def typed(game_world, window, index, text):
        if game_world.nui_on:
            w4.fire(window, "row_value", index, text)
        else:
            row = _row_of(window, index)
            row.valueEditLine.SetText(text)
            row.ApplyValue(text)


def click(widget):
    """A left click on a legacy button: its event with its arguments, unless
    its last Enable or Disable was Disable (a disabled button takes none)."""
    states = [call[0] for call in getattr(widget, "calls", ()) if call[0] in ("Enable", "Disable")]
    if states and states[-1] == "Disable":
        return
    event = getattr(widget, "event", None)
    if event:
        event(*getattr(widget, "eventArgs", ()))


def _row_of(self, index):
    return self.rareAttrDict[index] if index >= 5 else self.attrDict[index]


class Legacy(unittest.TestCase):
    def test_the_uiscript_has_every_child_the_window_binds(self):
        game_world, window = world(False)
        names = ["TitleBar", "ItemSlot", "CostItemButton", "CostYangButton", "CostText", "RareButton",
                 "StartStopButton", "SaveButton", "PremiumStatus", "SpeedText"]
        names += ["StatusBar%d" % i for i in range(6)] + ["SelectBox%d" % i for i in range(6)]
        names += ["SelectButton%d" % i for i in range(6)] + ["AlternativeButton%d" % i for i in range(3)]
        for name in names:
            self.assertIn(name, window.ElementDictionary, name)

    def test_the_uiscript_keeps_old_s_board_and_tab_places(self):
        namespace = {"SCREEN_WIDTH": 1600, "SCREEN_HEIGHT": 900, "__name__": "uiscript"}
        source = w4.read(os.path.join(REPO, "assets", "uiscript", "uiscript", "switchbot.py"))
        exec(compile(source.replace("import uiScriptLocale", "uiScriptLocale = type('L', (), {'__getattr__': lambda s, n: n})()"),
                     "switchbot.py", "exec"), namespace)
        board = namespace["window"]
        self.assertEqual((board["width"], board["height"]), (758, 580))
        children = dict((c["name"], c) for c in board["children"][0]["children"])
        self.assertEqual([(children["StatusBar%d" % i]["x"] - 2, children["StatusBar%d" % i]["y"] - 2) for i in range(6)],
                         [(92 + 100 * i, 84) for i in range(6)], "OLD's tabs at (92 + 100 i, 84)")
        self.assertEqual((children["StartStopButton"]["x"], children["StartStopButton"]["y"]), (668, 422))
        self.assertEqual((children["RareButton"]["x"], children["RareButton"]["y"]), (485, 480))

    def test_the_window_runs_no_python_per_frame(self):
        game_world, window = world(False)
        self.assertFalse(hasattr(type(window), "OnUpdate") and callable(getattr(type(window), "OnUpdate", None))
                         and "OnUpdate" in vars(type(window)), "no OnUpdate of its own (OLD polled the premium)")


class Flows(SwitchbotTest):
    def test_a_bag_item_dropped_on_an_empty_slot_moves_there(self):
        def flow(game_world, window):
            P = game_world.game.modules["player"]
            game_world.attach(P.SLOT_TYPE_INVENTORY, 7, SWORD)
            self.slot(game_world, window, 1)
        effects = self.run_both(flow)
        self.assertIn(("net.SendItemMovePacket", (1, 7, SWITCHBOT_WINDOW, 1, 1)), effects)

    def test_an_extra_inventory_item_drops_too(self):
        def flow(game_world, window):
            P = game_world.game.modules["player"]
            game_world.attach(P.SLOT_TYPE_EXTRA_INVENTORY, 40, SWORD)
            self.slot(game_world, window, 3)
        effects = self.run_both(flow)
        self.assertIn(("net.SendItemMovePacket", (6, 40, SWITCHBOT_WINDOW, 3, 1)), effects)

    def test_a_right_click_sends_the_item_back(self):
        effects = self.run_both(lambda game_world, window: self.slot(game_world, window, 0, kind="use"))
        self.assertIn(("net.SendItemUsePacket", (SWITCHBOT_WINDOW, 0)), effects)

    def test_a_press_picks_the_item_up_unless_it_rolls(self):
        effects = self.run_both(lambda game_world, window: self.slot(game_world, window, 2))
        self.assertIn(("mouse.AttachObject", (SLOT_TYPE_SWITCHBOT, 2, BLADE, 1)), effects)
        effects = self.run_both(lambda game_world, window: self.slot(game_world, window, 2),
                                bot_setup=lambda bot: bot.active.add(2))
        self.assertFalse([e for e in effects if e[0] == "mouse.AttachObject"])

    def test_a_searched_bonus_takes_its_highest_value(self):
        def flow(game_world, window):
            self.button(game_world, window, "row_pick", 0)
            self.pick(game_world, window, 2)   # MAX sorted: HP, INT, CRIT, PIERCE
        effects = self.run_both(flow)
        self.assertIn(("switchbot.SetAttribute", (0, 0, 0, CRIT, 10)), effects)

    def test_a_rare_search_writes_the_rare_target(self):
        def flow(game_world, window):
            self.button(game_world, window, "rare_press")
            self.button(game_world, window, "row_pick", 5)
            self.pick(game_world, window, 0)
        effects = self.run_both(flow)
        self.assertIn(("switchbot.SetRareAttribute", (0, 0, 5, SKILL_DMG, 20)), effects)

    def test_a_typed_value_is_kept_to_the_highest(self):
        def flow(game_world, window):
            game_world.bot.put(0, 0, 1, INT, 3)
            self.typed(game_world, window, 1, "40")
        effects = self.run_both(flow)
        self.assertIn(("switchbot.SetAttribute", (0, 0, 1, INT, 12)), effects)

    def test_the_arrows_change_the_target_not_only_the_text(self):
        """OLD's arrows set the field's text only (uiSwitchbot.py:486-494)."""
        def flow(game_world, window):
            game_world.bot.put(0, 0, 1, INT, 3)
            window.RefreshSwitchbotWindow()
            self.button(game_world, window, "row_plus", 1)
            self.button(game_world, window, "row_minus", 1)
            self.button(game_world, window, "row_minus", 1)
        effects = self.run_both(flow)
        writes = [args for name, args in effects if name == "switchbot.SetAttribute"]
        self.assertEqual(writes, [(0, 0, 1, INT, 4), (0, 0, 1, INT, 3), (0, 0, 1, INT, 2)])

    def test_start_sends_the_chosen_cost(self):
        def setup(bot):
            bot.put(0, 0, 0, HP, 1500)

        def flow(game_world, window):
            self.button(game_world, window, "start_press")
            self.button(game_world, window, "cost_press", COST_YANG)
            self.button(game_world, window, "start_press")
        effects = self.run_both(flow, bot_setup=setup)
        starts = [args for name, args in effects if name == "switchbot.Start"]
        self.assertEqual(starts, [(0, 0, COST_ITEM), (0, 0, COST_YANG)])

    def test_a_rolling_slot_stops(self):
        def setup(bot):
            bot.put(0, 0, 0, HP, 1500)
            bot.active.add(0)
        effects = self.run_both(lambda game_world, window: self.button(game_world, window, "start_press"), bot_setup=setup)
        self.assertEqual([args for name, args in effects if name in ("switchbot.Start", "switchbot.Stop")], [(0,)])

    def test_the_start_needs_an_item_and_a_target(self):
        effects = self.run_both(lambda game_world, window: self.button(game_world, window, "start_press"))
        self.assertFalse([e for e in effects if e[0] == "switchbot.Start"], "no target: start is disabled")

    def test_a_saved_configuration_applies_to_the_selected_slot(self):
        folder = tempfile.mkdtemp()
        cwd = os.getcwd()

        def setup(bot):
            bot.put(0, 0, 0, HP, 1500)
            bot.put(0, 1, 5, SKILL_DMG, 15)

        def flow(game_world, window):
            self.button(game_world, window, "save_press")
            presets = window.configurationSaveWindow
            presets.nameEditLine.SetText("hp")
            if game_world.nui_on:
                w4.fire(window, "preset_name", "hp")
                w4.press(window, "preset_save", 0)
                self.button(game_world, window, "tab_press", 2)
                w4.press(window, "preset_load", 0, 0)
            else:
                presets.Save()
                self.button(game_world, window, "tab_press", 2)
                presets.ApplyConfiguration(presets.Entries()[0][0])
        try:
            os.chdir(folder)
            effects = self.run_both(flow, bot_setup=setup)
            for name in os.listdir(folder):
                os.remove(os.path.join(folder, name))
        finally:
            os.chdir(cwd)
            os.rmdir(folder)
        self.assertIn(("switchbot.SetAttribute", (2, 0, 0, HP, 1500)), effects)
        self.assertIn(("switchbot.SetRareAttribute", (2, 1, 5, SKILL_DMG, 15)), effects)


class Lines(SwitchbotTest):
    def test_the_cost_line_and_the_premium_speed(self):
        bot = Switchbot()
        bot.roll_ms = 80
        game_world, window = world(False, bot)
        locale = game_world.game.modules["localeInfo"]
        self.assertEqual(window.costText.text, locale.SWITCHBOT_COST_ITEM_INFO)
        self.assertEqual(window.premiumStatus.text, locale.SWITCHBOT_PREMIUM_ACTIVE)
        self.assertEqual(window.speedText.text, locale.SWITCHBOT_SPEED % 0.08)
        with game_world.game, w4.quiet():
            window.SelectCost(COST_YANG)
        self.assertEqual(window.costText.text, locale.SWITCHBOT_COST_YANG_INFO % locale.NumberToMoneyString(10000))


class Board(SwitchbotTest):
    def board(self, bot=None):
        game_world, window = world(True, bot)
        return game_world, window, w4.board(window).model

    def test_the_board_shows_the_slots_their_states_and_the_selection(self):
        bot = Switchbot()
        bot.active.add(2)
        bot.put(0, 0, 0, HP, 1500)
        game_world, window, model = self.board(bot)
        self.assertEqual([c["state"] for c in model["cells"]], ["idle", "", "active", "", "", ""])
        self.assertEqual([c["selected"] for c in model["cells"]], [True] + [False] * 5)
        self.assertEqual(model["cells"][0]["icon"], "/icon/item/%05d.tga" % SWORD)
        self.assertTrue(model["start_enabled"])
        locale = game_world.game.modules["localeInfo"]
        self.assertEqual(model["start_label"], locale.SWITCHBOT_START)
        self.assertEqual(model["rows"][0]["name"], AFFECTS[HP] % 1500)
        self.assertEqual(model["rows"][0]["value"], "1500")
        self.assertTrue(model["rows"][0]["shown"])
        self.assertTrue(model["rows"][5]["line"], "the rare rows are struck through until 6/7 is on")
        self.assertEqual(model["cost"], COST_ITEM)

    def test_the_picker_and_the_presets_show_in_the_board(self):
        game_world, window, model = self.board()
        with game_world.game, w4.quiet():
            w4.press(window, "row_pick", 0, 0)
        model = w4.board(window).model
        self.assertTrue(model["picker_on"])
        self.assertEqual([i["text"] for i in model["picker_items"]], [AFFECTS[k] % v for k, v in sorted(MAX.items())])
        with game_world.game, w4.quiet():
            w4.fire(window, "picker_filter", "int")
        self.assertEqual([i["text"] for i in w4.board(window).model["picker_items"]], [AFFECTS[INT] % 12])
        with game_world.game, w4.quiet():
            w4.press(window, "picker_cancel", 0)
        self.assertFalse(w4.board(window).model["picker_on"])

    def test_the_fixture_has_every_model_key(self):
        game_world, window, model = self.board()
        self.assertEqual(set(w4.fixture_keys(window, "switchbot")), set(model))

    def test_the_facade_runs_no_python_per_frame(self):
        game_world, window = world(True)
        self.assertIsNone(type(window).OnUpdate)

    def test_the_board_exists_only_while_the_window_shows(self):
        game_world, window = world(True)
        self.assertIsNotNone(w4.board(window))
        with game_world.game, w4.quiet():
            window.Close()
        self.assertIsNone(w4.board(window))


class Hooks(unittest.TestCase):
    def read(self, name):
        return w4.read(os.path.join(ROOT, name))

    def test_game_toggles_on_f5_and_the_server_command_and_passes_the_refreshes(self):
        game = self.read("game.py")
        self.assertIn('onPressKeyDict[app.DIK_F5]\t= lambda: self.ShowSwitchbot()', game)
        self.assertIn('"ShowMeSwitchbot"\t\t: self.ShowSwitchbot,', game)
        for name in ("def ShowSwitchbot(self):", "def RefreshSwitchbotWindow(self):", "def RefreshSwitchbotItem(self, slot):"):
            self.assertIn(name, game)

    def test_the_interface_makes_toggles_refreshes_and_hides_it(self):
        interface = self.read("interfacemodule.py")
        self.assertIn('self.wndSwitchbot = nui_windows.make("switchbot", uiSwitchbot.SwitchbotWindow, '
                      '"nui_switchbot.SwitchbotWindow")', interface)
        for text in ("def ToggleSwitchbotWindow(self):", "self.wndSwitchbot.SetItemToolTip(self.tooltipItem)",
                     "hideWindows += self.wndSwitchbot,", "self.wndSwitchbot.Destroy()"):
            self.assertIn(text, interface)

    def test_the_mouse_frees_a_switchbot_item_s_icon(self):
        mouse = self.read("mousemodule.py")
        self.assertEqual(mouse.count("_SwitchbotSlotType()"), 3, "attach and deattach (OLD freed none)")

    def test_a_switchbot_item_drops_back_into_the_inventory(self):
        self.assertIn('elif getattr(player, "SLOT_TYPE_SWITCHBOT", None) == attachedSlotType:', self.read("uiinventory.py"))


GAME_KEYS = {
    "SWITCHBOT_START": "Start", "SWITCHBOT_STOP": "Stop", "SWITCHBOT_EMPTY_ATTR": "- Clear -",
    "SWITCHBOT_SELECT_ATTR": "Select Attribute", "SWITCHBOT_CLEAR_ATTR": "Clear Attribute",
    "SWITCHBOT_CONFIGURATION_TITLE": "Switchbot Configuration", "SWITCHBOT_SAVE_BUTTON": "Save Option",
    "SWITCHBOT_SAVE": "Save", "SWITCHBOT_LOAD_CONFIGURATION": "Load", "SWITCHBOT_CLEAR_CONFIGURATION": "Clear",
    "SWITCHBOT_PREMIUM_ACTIVE": "Active", "SWITCHBOT_PREMIUM_INACTIVE": "Inactive",
    "SWITCHBOT_COST_ITEM_INFO": "One switch item per roll", "SWITCHBOT_COST_YANG_INFO": "%s per roll",
    "SWITCHBOT_SPEED": "Roll speed: %.2f s",
}
INTERFACE_KEYS = {
    "SWITCHBOT_TITLE": "Switchbot", "SWITCHBOT_ALTERNATIVE": "Alternative Options:", "SWITCHBOT_COST": "Cost per roll:",
    "SWITCHBOT_COST_ITEM": "Switch item", "SWITCHBOT_COST_YANG": "Yang", "SWITCHBOT_START": "Start",
    "SWITCHBOT_SAVE": "Save Option", "SWITCHBOT_RARE": "6/7 Bonus", "SWITCHBOT_PREMIUM_LABEL": "Premium Switcher:",
    "NUI_SWITCHBOT_TARGETS": "Target bonuses", "NUI_SWITCHBOT_EMPTY": "Drag an item here",
}


def read_locale(locale, name):
    keys = {}
    with open(os.path.join(LOCALES, locale, name), encoding="utf-8", newline="") as handle:
        text = handle.read()
    for line in text.split("\n"):
        tokens = line.split("\t")
        if len(tokens) >= 2 and tokens[0]:
            keys[tokens[0]] = tokens[1:]
    return text, keys


class Locales(unittest.TestCase):
    def test_every_locale_has_every_key_as_a_plain_entry_with_english_s_specifiers(self):
        locales = sorted(name for name in os.listdir(LOCALES) if os.path.isfile(os.path.join(LOCALES, name, "locale_game.txt")))
        self.assertEqual(len(locales), 17)
        spec = lambda text: re.findall(r"%[-0-9.]*[sdif]", text.replace("%%", ""))
        for locale in locales:
            for name, keys in (("locale_game.txt", GAME_KEYS), ("locale_interface.txt", INTERFACE_KEYS)):
                text, entries = read_locale(locale, name)
                self.assertTrue(text.endswith("\n") and "\r" not in text, (locale, name))
                for key, english in keys.items():
                    with self.subTest(locale=locale, file=name, key=key):
                        self.assertIn(key, entries)
                        self.assertEqual(len(entries[key]), 1, "a plain entry")
                        self.assertTrue(entries[key][0])
                        self.assertEqual(spec(entries[key][0]), spec(english))
                        if locale == "en":
                            self.assertEqual(entries[key][0], english)


if __name__ == "__main__":
    unittest.main()
