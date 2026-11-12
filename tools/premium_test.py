"""Tests for the legacy client's premium tiers (wave 5, chunk Y1; NOVA-11):
python3 -B -m unittest premium_test (from tools/).

The C++ half (GC::PREMIUM_STATUS into CPythonPlayer, the player.* getters,
net.SendChatPacket's shout color) is chunk C's, in nova-client-src; the
server's rules are SP's. Here the legacy code of assets/root runs over
nui_game_support's stand-ins, with K's player constants installed from K's
client commit (nova-client-src 9d49ac2b, PythonPlayerModule.cpp:2739-2753)
while the committed module_constants.json does not carry them:
- uiaffectshower.AffectShower: the premium icon per tier (none for tier 0 or
  an unknown tier, PB-C7), first in the row; its tooltip (the tier name and
  the time left, rebuilt at most once a second, PB-C12); a press asks
  PREMIUM_DEACTIVATE_QUESTION and Yes sends /deactivate_premium once;
- game.GameWindow.BINARY_SetPremiumStatus, and the status read once when the
  window is made (spec 2.8);
- uichat: the shout color button (shown with the perk, a press without it
  refused with SHOUT_COLOR_REQUIRES_PERK), the swatch picker from the
  player's palette (D16, defined unconditionally, PB-C4), the pick kept until
  a shout carries it (PB-C5), and the history's [text, index];
- uitooltip: the premium scroll in its three states (fresh, returned,
  expired returned, PB-C8), also as a shop item (X5's tooltip half);
- every premium key in all 17 locales."""
import ast
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import legacy_foundation_test as lf  # noqa: E402
import nui_hud_test as hud  # noqa: E402
import nui_chat_test as chat_test  # noqa: E402

ROOT = support.ROOT
LOCALES = lf.LOCALES
HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixtures", "module_constants.json")

# K's player constants (nova-client-src 9d49ac2b, GameType.h:164-184 through
# PythonPlayerModule.cpp:2739-2753; the protocol's premium_packets.h:58-85).
K_PLAYER = {
    "PREMIUM_TIER_NONE": 0, "PREMIUM_TIER_SILVER": 1, "PREMIUM_TIER_GOLD": 2, "PREMIUM_TIER_PLATINUM": 3,
    "PREMIUM_PERK_AUTO_PICKUP": 0, "PREMIUM_PERK_EMOTES": 1, "PREMIUM_PERK_METIN_QUEUE": 2,
    "PREMIUM_PERK_SHOUT_COLOR": 3, "PREMIUM_PERK_SEARCH_BUY": 4, "PREMIUM_PERK_SWITCHBOT_FAST": 5,
    "PREMIUM_PERK_PULL_RANGE": 6, "PREMIUM_PERK_CHASE_RANGE": 7, "PREMIUM_PERK_COUNT": 8,
}
# The server's default palette (spec 5.1, PREMIUM_SHOUT_COLORS), as ARGB.
PALETTE = (0xFFFF0000, 0xFF00FF00, 0xFF02E8FF, 0xFFFFFF00, 0xFFFF66B2)
SCROLLS = (50208, 50209, 50210)
SCROLL_SECONDS = 7776000          # item_proto value 2 (spec 5.1)
CLOCK = 1700000000                # the corpus cases' clock (app.GetGlobalTimeStamp)
DAY, HOUR = 86400, 3600
SILVER_ART = "d:/ymir work/ui/skill/common/affect/silver_premium.sub"
GOLD_ART = "d:/ymir work/ui/skill/common/affect/premium_gold.sub"

# Spec 2.8's keys (locale_game.txt, plain entries) and their English text.
PREMIUM_KEYS = {
    "PREMIUM_TITLE": "Premium",
    "PREMIUM_TIER_1": "Silver",
    "PREMIUM_TIER_2": "Gold",
    "PREMIUM_TIER_3": "Platinum",
    "PREMIUM_DEACTIVATE_QUESTION": "Do you want to turn your remaining premium time back into a scroll?",
    "PREMIUM_SCROLL_UNUSED": "Unused",
    "PREMIUM_SCROLL_EXPIRED": "The time of this premium scroll has run out.",
    "SHOUT_COLOR_BUTTON": "Color",
    "SHOUT_COLOR_REQUIRES_PERK": "Your premium tier does not include shout colors.",
}


def install_k_player(player):
    for name, value in K_PLAYER.items():
        setattr(player, name, value)


def real_locale():
    return support.locale_info("en")


# --- the affect shower ---------------------------------------------------------------------------

class CountingToolTip(hud.RecordingToolTip):
    """The HUD tests' tooltip, counting its rebuilds."""

    def __init__(self, width=0):
        hud.RecordingToolTip.__init__(self, width)
        self.clears = 0

    def ClearToolTip(self):
        self.clears += 1
        hud.RecordingToolTip.ClearToolTip(self)


class SizedQuestionDialog(hud.QuestionDialog):
    """uiCommon.QuestionDialog with its SetWidth (uicommon.py)."""

    def SetWidth(self, width):
        self.width = width


def shower_world():
    world = hud.HudWorld(False)
    game = world.game
    install_k_player(game.modules["player"])
    game.modules["uiToolTip"].ToolTip = CountingToolTip
    game.modules["uiCommon"].QuestionDialog = SizedQuestionDialog
    hud.QuestionDialog.made = []
    locale = game.modules["localeInfo"]
    real = real_locale()
    for name in ("SecondToDHM", "DAY", "HOUR", "MINUTE", "LEFT_TIME"):
        setattr(locale, name, getattr(real, name))
    return world


def make_shower(world):
    with world, hud.quiet():
        return world.module("uiAffectShower").AffectShower()


class AffectShowerPremium(unittest.TestCase):
    def setUp(self):
        self.world = shower_world()
        self.shower = make_shower(self.world)

    def status(self, tier, seconds):
        with self.world, hud.quiet():
            self.shower.SetPremiumStatus(tier, seconds)
        return getattr(self.shower, "premiumImage", None)

    def test_each_tier_shows_its_icon_and_tier_zero_none(self):
        self.assertEqual(self.status(1, HOUR).image, SILVER_ART)
        self.assertEqual(self.status(2, HOUR).image, GOLD_ART)
        self.assertEqual(self.status(3, HOUR).image, GOLD_ART, "Platinum shows Gold's art until Q9")
        self.assertIsNone(self.status(0, 0))

    def test_an_unknown_tier_shows_nothing_and_raises_nothing(self):
        self.status(2, HOUR)
        self.assertIsNone(self.status(9, HOUR), "PB-C7")
        self.assertIsNone(self.status(-1, HOUR))

    def test_the_icon_is_first_in_the_row(self):
        with self.world, hud.quiet():
            self.shower.SetHorseState(10, 3, 3)
        image = self.status(1, HOUR)
        self.assertEqual(image.position, (0, 0))
        self.assertEqual(self.shower.horseImage.position, (self.shower.IMAGE_STEP, 0))

    def test_the_tooltip_names_the_tier_and_the_time_left(self):
        image = self.status(2, 2 * DAY + 3 * HOUR)
        tip = image.toolTip
        real = real_locale()
        self.assertEqual(tip.title, "PREMIUM_TITLE")
        self.assertEqual(tip.lines, ["PREMIUM_TIER_2", real.SecondToDHM(2 * DAY + 3 * HOUR)])
        self.assertEqual(real.SecondToDHM(2 * DAY + 3 * HOUR), "2Days 3Hours ")

    def test_the_tooltip_is_rebuilt_at_most_once_a_second(self):
        image = self.status(1, DAY)
        tip = image.toolTip
        clears = tip.clears
        with self.world:
            for _ in range(5):
                self.shower.OnUpdate()
        self.assertEqual(tip.clears, clears, "the same second: no rebuild")
        self.world.game.timestamp += 1
        with self.world:
            self.shower.OnUpdate()
            self.shower.OnUpdate()
        self.assertEqual(tip.clears, clears + 1)
        self.assertEqual(tip.lines[-1], real_locale().SecondToDHM(DAY - 1))

    def test_the_countdown_stops_at_zero(self):
        image = self.status(1, 30)
        self.world.game.timestamp += 3600
        with self.world:
            self.shower.OnUpdate()
        self.assertEqual(image.toolTip.lines[-1], real_locale().SecondToDHM(0))

    def test_a_press_asks_and_yes_sends_the_command_once(self):
        image = self.status(3, DAY)
        with self.world:
            image.OnMouseLeftButtonDown()
        dialog = hud.QuestionDialog.made[-1]
        self.assertTrue(dialog.opened)
        self.assertEqual(dialog.text, "PREMIUM_DEACTIVATE_QUESTION")
        mark = len(self.world.game.log)
        with self.world:
            dialog.accept()
            dialog.accept()
        self.assertFalse(dialog.opened)
        self.assertEqual(self.world.game.calls("net.SendChatPacket")[-1:], [("net.SendChatPacket", ("/deactivate_premium",))])
        self.assertEqual([c for c in self.world.game.log[mark:] if c[0] == "net.SendChatPacket"],
                         [("net.SendChatPacket", ("/deactivate_premium",))], "once")

    def test_no_sends_nothing(self):
        image = self.status(1, DAY)
        with self.world:
            image.OnMouseLeftButtonDown()
            hud.QuestionDialog.made[-1].cancel()
        self.assertFalse(hud.QuestionDialog.made[-1].opened)
        self.assertEqual(self.world.game.calls("net.SendChatPacket"), [])


# --- game.py ---------------------------------------------------------------------------------------

def game_methods(names):
    source = support.source_of("game.py", names, inside="GameWindow")
    body = "\n".join("\t" + line if line else line for line in source.split("\n"))
    namespace = {}
    exec(compile("class GameWindow(object):\n%s\n" % body, "game.py", "exec"), namespace)
    return namespace["GameWindow"]


class Recorder(object):
    def __init__(self):
        self.calls = []

    def SetPremiumStatus(self, *args):
        self.calls.append(args)


class GameForwards(unittest.TestCase):
    def test_the_status_reaches_the_affect_shower(self):
        window = game_methods(["BINARY_SetPremiumStatus"])()
        window.affectShower = Recorder()
        window.BINARY_SetPremiumStatus(2, 3600)
        self.assertEqual(window.affectShower.calls, [(2, 3600)])

    def test_a_shower_without_the_method_is_left_alone(self):
        window = game_methods(["BINARY_SetPremiumStatus"])()
        for shower in (None, object()):
            window.affectShower = shower
            window.BINARY_SetPremiumStatus(1, 60)

    def test_the_window_reads_the_status_once_after_making_the_shower(self):
        """A status that came before the game window is not lost (spec 2.8):
        GameWindow.__init__ over stand-ins (social_test's way)."""
        from unittest import mock
        names = ("interfaceModule", "uiPhaseCurtain", "uiTarget", "consoleModule", "wndMgr", "uiMapNameShower",
                 "uiAffectShower", "uiPlayerGauge", "uiMaintenance", "net", "datacache", "player_options")
        namespace = dict((name, mock.MagicMock()) for name in names)
        namespace["ui"] = types.SimpleNamespace(ScriptWindow=mock.MagicMock(), __mem_func__=lambda function: function)
        shower = Recorder()
        made = []
        namespace["nui_windows"] = types.SimpleNamespace(
            make=lambda key, *args: (made.append(key), shower if key == "affects" else mock.MagicMock())[1])
        namespace["player"] = types.SimpleNamespace(GetPremiumTier=lambda: 3, GetPremiumSecondsLeft=lambda: 7200,
                                                    SetGameWindow=lambda window: None)
        source = support.source_of("game.py", ("__init__",), inside="GameWindow")
        body = "\n".join("\t" + line if line else line for line in source.split("\n"))
        exec(compile("class GameWindow(object):\n%s\n" % body, "game.py", "exec"), namespace)

        class Window(namespace["GameWindow"]):
            def SetWindowName(self, name):
                pass

            def _GameWindow__SetQuickSlotMode(self):
                pass

            def _GameWindow__ServerCommand_Build(self):
                pass

            def _GameWindow__ProcessPreservedServerCommand(self):
                pass

        Window(stream=None)
        self.assertIn("affects", made)
        self.assertEqual(shower.calls, [(3, 7200)], "once, with C's status")


# --- the chat ----------------------------------------------------------------------------------------

def chat_world(perk=True, colors=PALETTE):
    world = chat_test.World(False)
    game = world.game
    install_k_player(game.modules["player"])
    state = {"perk": perk, "colors": list(colors)}
    game.answer("player", "HasPremiumPerk", lambda p: bool(state["perk"]) and p == K_PLAYER["PREMIUM_PERK_SHOUT_COLOR"])
    game.answer("player", "GetShoutColorCount", lambda: len(state["colors"]))
    game.answer("player", "GetShoutColor", lambda i: state["colors"][i] if 0 <= i < len(state["colors"]) else 0)
    world.state = state
    world.enter_game()
    return world


def signed(argb):
    return argb - (1 << 32) if argb & 0x80000000 else argb


class ShoutColor(unittest.TestCase):
    def open_chat(self, world):
        with world, chat_test.quiet():
            world.interface.ToggleChat()
        return world.chat.chatInputSet

    def sent(self, world):
        return [args for name, args in world.game.calls("net.SendChatPacket")]

    def pick(self, world, index):
        """A press on the button, then on swatch `index` (0-based)."""
        inputSet = world.chat.chatInputSet
        with world, chat_test.quiet():
            inputSet.btnShoutColor.OnMouseLeftButtonUp()
            board = inputSet.shoutColorBoard
            board.swatches[index].OnMouseLeftButtonUp()

    def test_the_picker_is_defined_unconditionally(self):
        world = chat_world()
        module = world.module("uiChat")
        self.assertTrue(isinstance(getattr(module, "ShoutColorBoard", None), type), "PB-C4")

    def test_the_button_shows_with_the_chat_only_with_the_perk(self):
        world = chat_world(perk=False)
        inputSet = self.open_chat(world)
        self.assertFalse(inputSet.btnShoutColor.IsShow())
        world = chat_world(perk=True)
        inputSet = self.open_chat(world)
        self.assertTrue(inputSet.btnShoutColor.IsShow())
        self.assertEqual(inputSet.btnShoutColor.text, world.game.modules["localeInfo"].SHOUT_COLOR_BUTTON)
        with world, chat_test.quiet():
            world.chat.CloseChat()
        self.assertFalse(inputSet.btnShoutColor.IsShow())

    def test_a_press_without_the_perk_is_refused(self):
        world = chat_world(perk=True)
        inputSet = self.open_chat(world)
        world.state["perk"] = False
        mark = len(world.game.chat.lines)
        with world, chat_test.quiet():
            inputSet.btnShoutColor.OnMouseLeftButtonUp()
        self.assertEqual([line[1:] for line in world.game.chat.lines[mark:]],
                         [[support.CHAT_CONSTANTS["CHAT_TYPE_INFO"], world.game.modules["localeInfo"].SHOUT_COLOR_REQUIRES_PERK]])
        board = getattr(inputSet, "shoutColorBoard", None)
        self.assertTrue(board is None or not board.IsShow())

    def test_the_picker_shows_the_palette(self):
        world = chat_world(colors=PALETTE[:3])
        inputSet = self.open_chat(world)
        with world, chat_test.quiet():
            inputSet.btnShoutColor.OnMouseLeftButtonUp()
        board = inputSet.shoutColorBoard
        self.assertTrue(board.IsShow())
        self.assertEqual([swatch.color for swatch in board.swatches], [signed(c) for c in PALETTE[:3]])
        self.assertEqual([swatch.index for swatch in board.swatches], [1, 2, 3], "1-based, as the server reads it")

    def test_a_pick_rides_the_next_shout_only(self):
        world = chat_world()
        self.open_chat(world)
        self.pick(world, 1)
        self.assertFalse(world.chat.chatInputSet.shoutColorBoard.IsShow(), "a pick closes the picker")
        for text in ("hello", "#party"):
            world.type(text)
            world.enter()
        self.assertEqual(self.sent(world), [("hello", 0), ("party", 3)], "talk and party lines send no color")
        world.type("!shout")
        world.enter()
        world.game.time += 20
        world.type("!again")
        world.enter()
        self.assertEqual(self.sent(world)[2:], [("shout", 6, 2), ("again", 6)], "the pick goes with one shout")

    def test_the_history_keeps_the_index(self):
        world = chat_world()
        self.open_chat(world)
        self.pick(world, 4)
        world.type("!colored")
        world.enter()
        world.game.time += 20
        world.type("!plain")
        world.enter()
        world.key("up")
        world.key("up")
        self.assertEqual(world.text(), "!colored")
        world.game.time += 20
        world.enter()
        self.assertEqual(self.sent(world)[-1], ("colored", 6, 5))


# --- the scroll tooltip ------------------------------------------------------------------------------

SCROLL = dict(lf.ITEM_BASE, name="Premium Scroll (Silver)", type=3, subtype=0, values=[0, 1, SCROLL_SECONDS, 0, 0, 0],
              icon="icon/item/71001.tga")


class ScrollToolTip(unittest.TestCase):
    def texts(self, vnum, socket0, context="AddItemData", **extra):
        corpus_tool, world = lf.tooltip_world({vnum: dict(SCROLL, values=[0, SCROLLS.index(vnum) + 1, SCROLL_SECONDS, 0, 0, 0])})
        case = {"context": context, "vnum": vnum, "sockets": [socket0, 0, 0, 0]}
        case.update(extra)
        texts, error = lf.tooltip_texts(corpus_tool, world, case)
        self.assertIsNone(error)
        return texts, world.game.modules["localeInfo"]

    def test_a_fresh_scroll_says_unused_and_its_duration(self):
        for vnum in SCROLLS:
            texts, locale = self.texts(vnum, 0)
            self.assertIn(PREMIUM_KEYS["PREMIUM_SCROLL_UNUSED"], texts, vnum)
            self.assertIn(locale.LEFT_TIME + " : " + locale.SecondToDHM(SCROLL_SECONDS), texts, vnum)

    def test_a_returned_scroll_shows_its_time_left(self):
        texts, locale = self.texts(50209, CLOCK + 2 * DAY + 3 * HOUR)
        self.assertIn(locale.LEFT_TIME + " : " + locale.SecondToDHM(2 * DAY + 3 * HOUR), texts)
        self.assertNotIn(PREMIUM_KEYS["PREMIUM_SCROLL_UNUSED"], texts)
        self.assertNotIn(PREMIUM_KEYS["PREMIUM_SCROLL_EXPIRED"], texts)

    def test_an_expired_returned_scroll_says_so(self):
        texts, locale = self.texts(50210, CLOCK - 5)
        self.assertIn(PREMIUM_KEYS["PREMIUM_SCROLL_EXPIRED"], texts, "PB-C8")
        self.assertNotIn(locale.LEFT_TIME + " : " + locale.SecondToDHM(0), texts)

    def test_another_item_has_no_scroll_line(self):
        corpus_tool, world = lf.tooltip_world({71001: dict(SCROLL, name="Other")})
        texts, error = lf.tooltip_texts(corpus_tool, world, {"context": "AddItemData", "vnum": 71001, "sockets": [0, 0, 0, 0]})
        self.assertNotIn(PREMIUM_KEYS["PREMIUM_SCROLL_UNUSED"], texts)

    def test_a_returned_scroll_in_a_shop_keeps_its_time_left(self):
        """X5's tooltip half: a listed scroll's socket 0 reaches the rule."""
        texts, locale = self.texts(50208, CLOCK + 3 * DAY, context="SetShopItem",
                                   shop={"open": True, "private": True, "price": 1000})
        self.assertIn(locale.LEFT_TIME + " : " + locale.SecondToDHM(3 * DAY), texts)


# --- the locales ---------------------------------------------------------------------------------------

class Locales(unittest.TestCase):
    def test_every_locale_has_every_premium_key_as_a_plain_entry(self):
        for locale in lf.locales():
            with self.subTest(locale=locale):
                keys = lf.read_locale(locale)
                for key, english in PREMIUM_KEYS.items():
                    self.assertIn(key, keys)
                    self.assertEqual(keys[key][1], "", "%s: no type column" % key)
                    self.assertEqual(keys[key][0].count("%"), english.count("%"), key)
        english = lf.read_locale("en")
        for key, text in PREMIUM_KEYS.items():
            self.assertEqual(english[key][0], text, key)

    def test_the_misspelled_key_is_not_ported(self):
        for locale in lf.locales():
            self.assertNotIn("PREMIMUM_DEACTIVATE", lf.read_locale(locale), locale)


class Constants(unittest.TestCase):
    def test_the_stand_in_values_are_ks(self):
        """Skips until the committed fixture carries K's player constants
        (y1.md step 2: main's fixture is kept, K's file is in the report)."""
        with open(FIXTURE, encoding="utf-8") as handle:
            player = json.load(handle)["modules"]["player"]
        if "PREMIUM_TIER_NONE" not in player:
            self.skipTest("tools/fixtures/module_constants.json is main's (nova-client-src eccdf1c)")
        for name, value in K_PLAYER.items():
            self.assertEqual(player[name], value, name)


if __name__ == "__main__":
    unittest.main()
