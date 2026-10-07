"""Tests for the NovaUI HUD windows of HUD CONTENT: the affect icons
(assets/root/nui_affects.py), the target board (nui_target.py), the party
(nui_party.py), the quest and whisper edge buttons (nui_edge_buttons.py),
the tip and big notice boards (nui_tip_board.py, nui_big_board.py) and the
map name splash (nui_map_name.py): python3 -B -m unittest nui_hud_test
(from tools/).

Plain CPython over nui_game_support's stand-ins, extended here (as its
docstring allows) with the legacy widgets these windows make, recording
tooltips and the constants the legacy modules read. For every window:
- facade: every method game.py, the Interface and the C++ callbacks call on
  the legacy class exists on the NovaUI class with a signature the legacy
  callers can use, and the class constants have the legacy values;
- differential: the legacy class and the NovaUI class, each in a world of
  its own with the same stand-in state and driven through the same flows,
  make the same player, net, app and mouse controller calls in order
  (getters left out), and show the same thing: the same icons and tooltip
  texts, buttons, members, stacks, notices or splash at the same times;
- fixture: the board, set from each fixture, has every fixture key in its
  model with the same kind, and the list entries have the keys the facade
  writes;
- no per-frame Python: the module defines no OnUpdate, OnRender or
  OnMouseOverIn."""
import ast
import contextlib
import gc
import inspect
import io
import json
import os
import re
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402

ROOT = support.ROOT
WINDOWS = os.path.normpath(os.path.join(support.support.HERE, "..", "assets", "nui", "nui", "windows"))
CLASSIC_WINDOWS = os.path.normpath(os.path.join(support.support.HERE, "..", "assets", "nui", "nui", "skins", "classic", "windows"))
HUD_MODULES = ("nui_affects", "nui_target", "nui_party", "nui_edge_buttons", "nui_tip_board", "nui_big_board", "nui_map_name")
LEGACY_MODULES = (("uiAffectShower", "uiaffectshower.py"), ("uiTarget", "uitarget.py"), ("uiParty", "uiparty.py"),
                  ("uiTip", "uitip.py"), ("uiMapNameShower", "uimapnameshower.py"), ("uiWhisper", "uiwhisper.py"))

# --- the constants the legacy modules read (the client's values where it matters) --------

CHR = {
    "AFFECT_POISON": 3, "AFFECT_SLOW": 4, "AFFECT_STUN": 5, "AFFECT_MOV_SPEED_POTION": 11, "AFFECT_ATT_SPEED_POTION": 12,
    "AFFECT_FISH_MIND": 13, "AFFECT_JEONGWI": 14, "AFFECT_GEOMGYEONG": 15, "AFFECT_CHEONGEUN": 16, "AFFECT_GYEONGGONG": 17,
    "AFFECT_EUNHYEONG": 18, "AFFECT_GWIGEOM": 19, "AFFECT_GONGPO": 20, "AFFECT_JUMAGAP": 21, "AFFECT_HOSIN": 22,
    "AFFECT_BOHO": 23, "AFFECT_KWAESOK": 24, "AFFECT_HEUKSIN": 25, "AFFECT_MUYEONG": 26, "AFFECT_FIRE": 28,
    "AFFECT_GICHEON": 29, "AFFECT_JEUNGRYEOK": 30, "AFFECT_PABEOP": 32, "AFFECT_FALLEN_CHEONGEUN": 33,
    "AFFECT_CHINA_FIREWORK": 38,
    "NEW_AFFECT_EXP_BONUS": 500, "NEW_AFFECT_ITEM_BONUS": 501, "NEW_AFFECT_SAFEBOX": 502, "NEW_AFFECT_AUTOLOOT": 503,
    "NEW_AFFECT_FISH_MIND": 504, "NEW_AFFECT_MARRIAGE_FAST": 505, "NEW_AFFECT_GOLD_BONUS": 506, "NEW_AFFECT_MALL": 510,
    "NEW_AFFECT_NO_DEATH_PENALTY": 511, "NEW_AFFECT_SKILL_BOOK_BONUS": 512, "NEW_AFFECT_SKILL_BOOK_NO_DELAY": 513,
    "NEW_AFFECT_EXP_BONUS_EURO_FREE": 516, "NEW_AFFECT_EXP_BONUS_EURO_FREE_UNDER_15": 517,
    "NEW_AFFECT_AUTO_HP_RECOVERY": 534, "NEW_AFFECT_AUTO_SP_RECOVERY": 535, "NEW_AFFECT_DRAGON_SOUL_DECK1": 541,
    "NEW_AFFECT_DRAGON_SOUL_DECK2": 542, "INSTANCE_TYPE_BUILDING": 2, "INSTANCE_TYPE_PLAYER": 6,
}
PLAYER = {
    "POINT_MALL_ATTBONUS": 114, "POINT_MALL_DEFBONUS": 115, "POINT_MALL_EXPBONUS": 116, "POINT_MALL_ITEMBONUS": 117,
    "POINT_MALL_GOLDBONUS": 118, "POINT_CRITICAL_PCT": 40, "POINT_PENETRATE_PCT": 41, "POINT_MAX_HP_PCT": 119,
    "POINT_MAX_SP_PCT": 120, "POINT_PC_BANG_EXP_BONUS": 103, "POINT_PC_BANG_DROP_BONUS": 104, "POINT_ATT_SPEED": 17,
    "AUTO_POTION_TYPE_HP": 0, "AUTO_POTION_TYPE_SP": 1, "DRAGON_SOUL_EQUIPMENT_SLOT_START": 180,
    "DRAGON_SOUL_EQUIPMENT_FIRST_SIZE": 6,
    "PARTY_STATE_NORMAL": 0, "PARTY_STATE_LEADER": 1, "PARTY_STATE_ATTACKER": 2, "PARTY_STATE_TANKER": 3,
    "PARTY_STATE_BUFFER": 4, "PARTY_STATE_SKILL_MASTER": 5, "PARTY_STATE_BERSERKER": 6, "PARTY_STATE_DEFENDER": 7,
    "PARTY_EXP_NON_DISTRIBUTION": 0, "PARTY_EXP_DISTRIBUTION_PARITY": 1, "SKILL_INDEX_TONGSOL": 121,
}
ITEM = {"LIMIT_MAX_NUM": 2, "LIMIT_NONE": 0, "LIMIT_REAL_TIME": 7, "LIMIT_REAL_TIME_START_FIRST_USE": 8,
        "LIMIT_TIMER_BASED_ON_WEAR": 9}
GUILD = {"AUTH_ADD_MEMBER": 1, "AUTH_REMOVE_MEMBER": 2}
NONPLAYER = {"PAWN": 0, "S_PAWN": 1, "KNIGHT": 2, "S_KNIGHT": 3, "BOSS": 4, "KING": 5}

# localeInfo entries typed SA or SNA (functions), and the plain ones the windows format.
FUNCTIONS = (
    "TOOLTIP_MALL_EXPBONUS_STATIC", "TOOLTIP_MALL_ITEMBONUS_STATIC", "TOOLTIP_MALL_SAFEBOX", "TOOLTIP_MALL_AUTOLOOT",
    "TOOLTIP_MALL_FISH_MIND", "TOOLTIP_MALL_MARRIAGE_FAST", "TOOLTIP_MALL_GOLDBONUS_STATIC", "TOOLTIP_APPLY_NO_DEATH_PENALTY",
    "TOOLTIP_APPLY_SKILL_BOOK_BONUS", "TOOLTIP_APPLY_SKILL_BOOK_NO_DELAY", "TOOLTIP_MALL_ATTBONUS_STATIC",
    "TOOLTIP_MALL_DEFBONUS_STATIC", "TOOLTIP_MALL_EXPBONUS", "TOOLTIP_MALL_ITEMBONUS", "TOOLTIP_MALL_GOLDBONUS",
    "TOOLTIP_APPLY_CRITICAL_PCT", "TOOLTIP_APPLY_PENETRATE_PCT", "TOOLTIP_MAX_HP_PCT", "TOOLTIP_MAX_SP_PCT",
    "TOOLTIP_MALL_EXPBONUS_P_STATIC", "TOOLTIP_MALL_ITEMBONUS_P_STATIC", "TOOLTIP_MALL_ATT_SPEED",
    "TOOLTIP_DRAGON_SOUL_DECK1", "TOOLTIP_DRAGON_SOUL_DECK2",
    "PARTY_BONUS_EXP", "PARTY_BONUS_ATTACKER", "PARTY_BONUS_TANKER", "PARTY_BONUS_BUFFER", "PARTY_BONUS_SKILL_MASTER",
    "PARTY_BONUS_BERSERKER", "PARTY_BONUS_DEFENDER", "PARTY_INCREASE_AREA_150", "PARTY_INCREASE_AREA_200",
)


def quiet():
    """The legacy modules print."""
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def rt_second_to_dhms(time):
    """localeinfo.py RTSecondToDHMS with the stand-in's unit words."""
    text = ""
    d = time // (24 * 3600)
    time %= (24 * 3600)
    h = time // 3600
    time %= 3600
    m = time // 60
    s = time % 60
    if d:
        text += str(d) + " " + "DAY" + (", " if h or m or s else "")
    if h:
        text += str(h) + " " + "HOUR" + (", " if m or s else "")
    if m:
        text += str(m) + " " + "MINUTE" + (", " if s else "")
    if s:
        text += str(s) + " " + "SECOND"
    return text.strip()


def plain(text):
    """A model string without nui.plain_text's word joiners."""
    return text.replace("⁠", "")


# --- the legacy widgets these windows make --------------------------------------------------

class Box(support.LegacyWidget):
    """A legacy image box, text line, gauge or button: it keeps what the
    windows set on it (position, size, scale, alpha, text, color, alignment,
    art, flashing, the radio button's down state, a gauge's percentage) and
    records every other call."""

    def __init__(self, layer="UI"):
        support.LegacyWidget.__init__(self, type(self).__name__)
        self.layer = layer
        self.position = (0, 0)
        self.size = (0, 0)
        self.scale = (1.0, 1.0)
        self.alpha = 1.0
        self.color = None
        self.align = None
        self.flashing = False
        self.down = False
        self.percentage = None
        self.Children = []

    def __del__(self):
        pass

    def SetPosition(self, x, y):
        self.position = (x, y)

    def GetLocalPosition(self):
        return self.position

    def GetGlobalPosition(self):
        return self.position

    def SetSize(self, width, height):
        self.size = (width, height)

    def GetWidth(self):
        return self.size[0] or 32

    def GetHeight(self):
        return self.size[1] or 32

    def SetScale(self, x, y):
        self.scale = (x, y)

    def SetAlpha(self, alpha):
        self.alpha = alpha

    def GetTextSize(self):
        return (len(self.text) * 6, 12)

    def SetPackedFontColor(self, color):
        self.color = color

    def SetHorizontalAlignCenter(self):
        self.align = "center"

    def SetHorizontalAlignLeft(self):
        self.align = "left"

    def SetHorizontalAlignRight(self):
        self.align = "right"

    def Flash(self):
        self.flashing = True

    def SAFE_SetEvent(self, event, *args):
        self.SetEvent(event, *args)

    def SetToolTipText(self, text, x=0, y=-19):
        if not self.ToolTipText:
            self.ToolTipText = Box()
            self.ToolTipText.position = (x, y)
            self.ToolTipText.align = "center"
        self.ToolTipText.SetText(text)
        self.tooltip = text

    def Down(self):
        self.down = True

    def SetUp(self):
        self.down = False

    def MakeGauge(self, width, color):
        self.size = (width, 7)

    def SetPercentage(self, current, maximum):
        self.percentage = min(1.0, float(current) / float(maximum)) if maximum > 0 else 0.0

    def LoadImage(self, path):
        self.image = path

    def Destroy(self):
        pass


class RecordingToolTip(object):
    """uiToolTip.ToolTip: its title, its lines and whether it shows."""

    def __init__(self, width=0):
        self.title = None
        self.lines = []
        self.visible = False

    def ClearToolTip(self):
        self.title = None
        self.lines = []

    def SetTitle(self, title):
        self.title = title

    def AppendTextLine(self, text, color=None, *args):
        self.lines.append(text)

    def ResizeToolTip(self):
        pass

    def SetToolTipPosition(self, x=-1, y=-1):
        pass

    def ShowToolTip(self):
        self.visible = True

    def HideToolTip(self):
        self.visible = False

    def Hide(self):
        self.visible = False

    def Show(self):
        self.visible = True


class QuestionDialog(object):
    """uiCommon.QuestionDialog: records what it was asked."""

    made = []

    def __init__(self, *args):
        QuestionDialog.made.append(self)
        self.text = ""
        self.accept = self.cancel = None
        self.opened = False

    def SetText(self, text):
        self.text = text

    def SetAcceptEvent(self, event):
        self.accept = event

    def SetCancelEvent(self, event):
        self.cancel = event

    def Open(self):
        self.opened = True

    def Close(self):
        self.opened = False


def extend_ui(ui):
    """The stand-in ui module, with the widgets of these legacy windows."""
    base_window = ui.HudWindow

    class Win(base_window):
        """A legacy window: what HudWindow keeps, and every other call recorded."""

        def __getattr__(self, attr):
            if attr.startswith("__") or not attr[:1].isupper():
                raise AttributeError(attr)
            return lambda *args: None

    script_base = ui.ScriptWindow

    class ScriptWindow(script_base):
        def GetChild(self, name):
            child = self.ElementDictionary.get(name)
            if child is None:
                child = self.ElementDictionary[name] = Box()
                child.name = name
            return child

        def __getattr__(self, attr):
            if attr.startswith("__") or not attr[:1].isupper():
                raise AttributeError(attr)
            return lambda *args: None

    def make_text_line(parent):
        line = Box()
        line.Show()
        return line

    for name in ("ExpandedImageBox", "ImageBox", "AniImageBox", "TextLine", "Button", "Gauge", "ThinBoard",
                 "RadioButton", "ToggleButton", "DragButton", "NumberLine"):
        setattr(ui, name, type(name, (Box,), {}))
    for name in ("EditLine", "ThinScrollBar", "ScrollBar", "SlotBar"):
        setattr(ui, name, Win)
    ui.Window = Win
    ui.Bar = Win
    ui.ScriptWindow = ScriptWindow
    ui.MakeTextLine = make_text_line
    return ui


def extend(game):
    """Constants, widgets, tooltips and locale entries for these windows."""
    modules = game.modules
    for name, value in CHR.items():
        setattr(modules["chr"], name, value)
    for name, value in PLAYER.items():
        setattr(modules["player"], name, value)
    for name, value in ITEM.items():
        setattr(modules["item"], name, value)
    for name, value in GUILD.items():
        setattr(modules["guild"], name, value)
    for name, value in NONPLAYER.items():
        setattr(modules["nonplayer"], name, value)
    modules["chat"].CHAT_TYPE_NOTICE = 1
    modules["app"].IsVisibleNotice = lambda: game.visible_notice
    modules["app"].IsExistFile = lambda path: path not in game.missing_files
    game.visible_notice = True
    game.missing_files = set()
    extend_ui(modules["ui"])
    tooltips = modules["uiToolTip"]
    tooltips.ToolTip = RecordingToolTip
    locale = modules["localeInfo"]
    for name in FUNCTIONS:
        setattr(locale, name, (lambda n: lambda value: "%s(%s)" % (n, value))(name))
    locale.TOOLTIP_AUTO_POTION_REST = "Remainder: %.2f%%"
    locale.TOOLTIP_AUTO_POTION_HP = "Sun Elixir"
    locale.TOOLTIP_AUTO_POTION_SP = "Moon Elixir"
    locale.AFF_LOVE_POINT = "Love points: %d%%"
    locale.LEVEL_LIST = ("", "HORSE_LEVEL1", "HORSE_LEVEL2", "HORSE_LEVEL3")
    locale.HEALTH_LIST = ("HORSE_HEALTH0", "HORSE_HEALTH1", "HORSE_HEALTH2", "HORSE_HEALTH3")
    locale.RTSecondToDHMS = rt_second_to_dhms
    locale.RECEIVE_MESSAGE = "%s sent a message"
    locale.GetLetterImageName = lambda: "season1/icon/scroll_close.tga"
    locale.GetLetterOpenImageName = lambda: "season1/icon/scroll_open.tga"
    locale.GetLetterCloseImageName = lambda: "season1/icon/scroll_close.tga"
    modules["uiScriptLocale"].MAPNAME_PATH = "locale/en/ui/mapname/"
    common = types.ModuleType("uiCommon")
    common.QuestionDialog = QuestionDialog
    modules["uiCommon"] = common
    QuestionDialog.made = []
    game.answer("grp", "TextBarGetTextExtent", lambda handle, text: (len(text) * 9, 18))
    game.answer("skill", "GetSkillName", lambda index: "skill %d" % index)


class HudWorld(object):
    """One world: a Game with these windows' stand-ins, the legacy modules
    and the NovaUI ones loaded over them."""

    def __init__(self, nui_on, setup=None, engine=True):
        self.game = support.Game(engine=engine)
        self.game.modules["systemSetting"].GetUINuiWindows = lambda: "+hud" if nui_on else ""
        extend(self.game)
        if setup is not None:
            setup(self.game)
        self.game.load_standard()
        with quiet():
            for alias, file_name in LEGACY_MODULES:
                self.game.load(alias, file_name)
        # The legacy destructors print when a test's objects are collected.
        for alias, class_name in (("uiTarget", "TargetBoard"), ("uiParty", "PartyWindow"),
                                  ("uiParty", "PartyMemberInfoBoard")):
            setattr(getattr(self.game.loaded[alias], class_name), "__del__", lambda self: None)
        with quiet():
            for name in HUD_MODULES:
                self.game.load(name, name + ".py")
        self.nui_windows = self.game.loaded["nui_windows"]
        self.nui_on = nui_on

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def module(self, name):
        return self.game.loaded[name]

    def make(self, window_id, legacy, novaui):
        with quiet():
            return self.nui_windows.make(window_id, legacy, novaui)

    def effects(self, since=0, extra_getters=()):
        """The calls with an effect since a mark: the getters left out."""
        return [(name, args) for name, args in self.game.log[since:]
                if name.split(".", 1)[0] in support.COMPARED and not support.is_getter(name)
                and name.rsplit(".", 1)[-1] not in extra_getters]


def pair(setup=None):
    return HudWorld(False, setup=setup), HudWorld(True, setup=setup)


# --- facades ----------------------------------------------------------------------------

AFFECT_METHODS = ("ClearAffects", "SetAffect", "ResetAffect", "BINARY_NEW_AddAffect", "BINARY_NEW_RemoveAffect",
                  "SetLoverInfo", "OnUpdateLovePoint", "ShowLoverState", "HideLoverState", "ClearLoverState",
                  "SetHorseState", "ClearAllAffects", "SetPlayTime", "RefreshLocale", "Show", "Hide", "IsShow", "Destroy")
AFFECT_CONSTANTS = ("MALL_DESC_IDX_START", "IMAGE_STEP", "AFFECT_MAX_NUM", "INFINITE_AFFECT_DURATION")
TARGET_METHODS = ("SetWhisperEvent", "Hide", "Open", "RefreshByVID", "RefreshByName", "Refresh", "GetTargetVID",
                  "ResetTargetBoard", "SetEnemyVID", "SetHP", "Show", "Close", "Destroy", "IsShow", "GetTargetName",
                  "SetTargetVID", "SetTargetName", "ShowDefaultButton", "HideAllButton", "RefreshButton", "IsShowButton",
                  "OnPressedCloseButton", "OnPressEscapeKey", "UpdatePosition", "OnWhisper", "OnExchange", "OnPVP",
                  "OnAppendToMessenger", "OnPartyInvite", "OnPartyExit", "OnPartyRemove")
TARGET_CONSTANTS = ("BTN_WHISPER", "BTN_EXCHANGE", "BTN_FIGHT", "BTN_ACCEPT_FIGHT", "BTN_AVENGE", "BTN_FRIEND",
                    "BTN_INVITE_PARTY", "BTN_LEAVE_PARTY", "BTN_EXCLUDE", "BTN_INVITE_GUILD", "BTN_REMOVE_GUILD",
                    "BTN_DISMOUNT", "BTN_EXIT_OBSERVER", "BTN_VIEW_EQUIPMENT", "BTN_REQUEST_ENTER_PARTY",
                    "BTN_BUILDING_DESTROY", "BTN_EMOTION_ALLOW", "BTN_VOTE_BLOCK_CHAT", "BUTTON_CONFIG",
                    "EXCHANGE_LIMIT_RANGE")
PARTY_METHODS = ("AddPartyMember", "UpdatePartyMemberInfo", "RemovePartyMember", "LinkPartyMember", "UnlinkPartyMember",
                 "UnlinkAllPartyMember", "ExitParty", "PartyHealReady", "ChangePartyParameter", "Show", "Hide", "IsShow",
                 "Destroy", "DestroyPartyMemberInfoBoard", "OnTogglePartyMenu")
EDGE_METHODS = ("SetUpVisual", "SetOverVisual", "SetDownVisual", "SetToolTipText", "SetToolTipTextWithColor", "SetEvent",
                "Show", "Hide", "IsShow", "Flash", "SetPosition", "SetTop", "ShowToolTip", "HideToolTip", "Destroy")
NOTICE_METHODS = ("SetTip", "Show", "Hide", "IsShow", "Destroy")
TIP_CONSTANTS = ("SCROLL_WAIT_TIME", "TIP_DURATION", "STEP_HEIGHT")
BIG_CONSTANTS = ("SCROLL_WAIT_TIME", "TIP_DURATION", "FONT_WIDTH", "FONT_HEIGHT", "LINE_WIDTH", "LINE_HEIGHT",
                 "STEP_HEIGHT", "LINE_CHANGE_LIMIT_WIDTH", "FRAME_IMAGE_FILE_NAME_LIST", "FRAME_IMAGE_STEP",
                 "FRAME_BASE_X", "FRAME_BASE_Y")
MAP_METHODS = ("ShowMapName", "IsShow", "Update", "Show", "Hide", "Destroy")
MAP_CONSTANTS = ("STATE_HIDE", "STATE_FADE_IN", "STATE_SHOW", "STATE_FADE_OUT")


def assert_callable_like(test, legacy_method, novaui_method, name):
    """Every call shape the legacy signature takes binds to the NovaUI one."""
    legacy = inspect.signature(legacy_method)
    novaui = inspect.signature(novaui_method)
    positional = [p for p in legacy.parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    required = [p for p in positional if p.default is p.empty]
    extra = any(p.kind == p.VAR_POSITIONAL for p in legacy.parameters.values())
    for count in range(len(required), len(positional) + (3 if extra else 1)):
        try:
            novaui.bind(*([None] * count))
        except TypeError as error:
            test.fail("%s: a legacy call with %d arguments does not bind: %s" % (name, count, error))


class Facades(unittest.TestCase):
    def setUp(self):
        self.world = HudWorld(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)

    def check(self, legacy_class, novaui_class, methods, constants=()):
        for name in methods:
            self.assertTrue(hasattr(novaui_class, name), "%s.%s" % (novaui_class.__name__, name))
            legacy_method = getattr(legacy_class, name, None)
            if legacy_method is None or not callable(legacy_method):
                continue
            assert_callable_like(self, getattr(object.__new__(legacy_class), name),
                                 getattr(object.__new__(novaui_class), name), "%s.%s" % (novaui_class.__name__, name))
        for name in constants:
            self.assertEqual(getattr(novaui_class, name), getattr(legacy_class, name), name)
        self.assertIs(novaui_class.NUI_FACADE, True)
        self.assertEqual(novaui_class.__name__, legacy_class.__name__.replace("Legacy", "") if novaui_class.__name__ != "EdgeButton" else "EdgeButton")
        self.assertEqual(len(inspect.signature(novaui_class.__init__).parameters),
                         len(inspect.signature(legacy_class.__init__).parameters), "the legacy constructor arguments")

    def test_the_affects_facade_keeps_the_legacy_surface(self):
        self.check(self.world.module("uiAffectShower").AffectShower, self.world.module("nui_affects").AffectShower,
                   AFFECT_METHODS, AFFECT_CONSTANTS)

    def test_the_target_board_facade_keeps_the_legacy_surface(self):
        self.check(self.world.module("uiTarget").TargetBoard, self.world.module("nui_target").TargetBoard,
                   TARGET_METHODS, TARGET_CONSTANTS)

    def test_the_party_facade_keeps_the_legacy_surface(self):
        self.check(self.world.module("uiParty").PartyWindow, self.world.module("nui_party").PartyWindow, PARTY_METHODS)

    def test_the_edge_button_facade_keeps_the_legacy_surface(self):
        self.check(self.world.module("uiWhisper").LegacyWhisperButton, self.world.module("nui_edge_buttons").EdgeButton,
                   EDGE_METHODS)
        with self.world:
            button = self.world.module("nui_edge_buttons").EdgeButton()
            button.SetToolTipText("x")
            for name in ("SetHorizontalAlignCenter", "SetHorizontalAlignLeft", "Show", "Hide", "SetPackedFontColor"):
                self.assertTrue(callable(getattr(button.ToolTipText, name)), name)

    def test_the_notice_board_facades_keep_the_legacy_surface(self):
        tip = self.world.module("uiTip")
        self.check(tip.TipBoard, self.world.module("nui_tip_board").TipBoard, NOTICE_METHODS, TIP_CONSTANTS)
        self.check(tip.BigBoard, self.world.module("nui_big_board").BigBoard, NOTICE_METHODS, BIG_CONSTANTS)

    def test_the_map_name_facade_keeps_the_legacy_surface(self):
        self.check(self.world.module("uiMapNameShower").MapNameShower, self.world.module("nui_map_name").MapNameShower,
                   MAP_METHODS, MAP_CONSTANTS)

    def test_every_facade_answers_the_make_protocol_and_needs_the_engine(self):
        made = (("nui_affects", "AffectShower", "affects"), ("nui_target", "TargetBoard", "target"),
                ("nui_party", "PartyWindow", "party"), ("nui_tip_board", "TipBoard", "tip-board"),
                ("nui_big_board", "BigBoard", "big-board"), ("nui_map_name", "MapNameShower", "map-name"))
        hud = self.world.module("nui_hud")
        with self.world, quiet():
            for module, name, key in made:
                facade = getattr(self.world.module(module), name)()
                self.assertTrue(facade.nui_ready(), name)
                self.assertIs(hud.current(key), facade, name)
                again = getattr(self.world.module(module), name)()
                self.assertFalse(facade.nui_ready(), "%s: a new facade discards the previous one (D26)" % name)
                again.Destroy()
                self.assertFalse(again.nui_ready(), name)
                self.assertIsNone(hud.current(key), "%s: Destroy drops the record" % name)
            edge = self.world.module("nui_edge_buttons").EdgeButton()
            self.assertTrue(edge.nui_ready())
        world = HudWorld(True, engine=False)
        with world, quiet():
            for module, name, key in made:
                self.assertFalse(getattr(world.module(module), name)().nui_ready(), "%s without the engine" % name)
            self.assertFalse(world.module("nui_edge_buttons").EdgeButton().nui_ready())
            made_board = world.make("target", world.module("uiTarget").TargetBoard, "nui_target.TargetBoard")
            self.assertEqual(type(made_board).__module__, "uiTarget", "an older exe keeps the legacy board")


# --- fixtures and per-frame Python ---------------------------------------------------------------

def fixture(window, variant=None):
    name = window if variant is None else "%s.%s" % (window, variant)
    with open(os.path.join(WINDOWS, window, name + ".fixture.json"), encoding="utf-8") as handle:
        return json.load(handle)


def kind(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "map"
    return "none"


class Fixtures(unittest.TestCase):
    def setUp(self):
        self.world = HudWorld(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)

    def check(self, board_class, window, variants=(), owner=None, entries=None):
        board = board_class(owner) if owner is not None else board_class()
        model = board.initial_model()
        for variant in (None,) + tuple(variants):
            data = fixture(window, variant)
            self.assertEqual(list(data), [board_class.MODEL], window)
            values = data[board_class.MODEL]
            self.assertEqual(set(values), set(model), "%s %s: the fixture holds every model key" % (window, variant))
            for key, value in values.items():
                self.assertEqual(kind(value), kind(model[key]), "%s.%s" % (window, key))
            for key, keys in (entries or {}).items():
                for entry in values[key]:
                    self.assertEqual(set(entry), keys, "%s %s: an entry of %s" % (window, variant, key))
            self.assertTrue(board.set(**values))
        self.assertEqual(self.world.game.dbg.errors, [])
        return board

    def entry_keys(self, facade, key, setup):
        with quiet():
            setup(facade)
        entries = facade.board.get(key)
        self.assertTrue(entries, key)
        return set(entries[0])

    def test_the_affects_fixtures_match_the_model_and_the_entries_the_facade_writes(self):
        module = self.world.module("nui_affects")
        facade = module.AffectShower()
        keys = self.entry_keys(facade, "icons", lambda f: f.SetAffect(CHR["AFFECT_JEONGWI"]))
        self.check(module.AffectBoard, "affects", ("tooltip",), owner=object(), entries={"icons": keys})

    def test_the_target_fixtures_match_the_model_and_the_entries_the_facade_writes(self):
        module = self.world.module("nui_target")
        facade = module.TargetBoard()
        keys = self.entry_keys(facade, "buttons", lambda f: f.ShowDefaultButton())
        self.check(module.TargetBoardBoard, "target", ("mob", "player"), owner=object(), entries={"buttons": keys})
        self.assertEqual(module.TargetBoardBoard.FEEDS, {"in_range": "target.in_range"})

    def test_the_party_fixtures_match_the_model_and_the_entries_the_facade_writes(self):
        module = self.world.module("nui_party")
        facade = module.PartyWindow()
        keys = self.entry_keys(facade, "members", lambda f: f.AddPartyMember(7, "x"))
        self.check(module.PartyBoard, "party", ("menu",), owner=object(), entries={"members": keys})
        for variant in (None, "menu"):
            for member in fixture("party", variant)["party"]["members"]:
                self.assertEqual(len(member["affects"]), 9)
                self.assertEqual(len(member["affect_tips"]), 9)
                for button in member["state_buttons"]:
                    self.assertEqual(set(button), {"state", "art", "tip"})

    def test_the_edge_button_fixture_matches_the_model_and_the_entries_the_facade_writes(self):
        module = self.world.module("nui_edge_buttons")
        button = module.EdgeButton()
        button.SetPosition(20, 255)
        keys = set(module._board.get("quests")[0])
        module.close_all()
        self.check(module.EdgeBoard, "edge-buttons", entries={"quests": keys, "whispers": keys})

    def test_the_notice_board_and_map_name_fixtures_match_their_models(self):
        self.check(self.world.module("nui_tip_board").TipBoardBoard, "tip-board", owner=object())
        self.check(self.world.module("nui_big_board").BigBoardBoard, "big-board", owner=object())
        self.check(self.world.module("nui_map_name").MapNameBoard, "map-name", owner=object())


class NoPerFramePython(unittest.TestCase):
    def test_no_hud_module_defines_a_per_frame_hook(self):
        for name in HUD_MODULES:
            tree = ast.parse(read(os.path.join(ROOT, name + ".py")))
            defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
            self.assertEqual(defined & {"OnUpdate", "OnRender", "OnMouseOverIn"}, set(), name)

    def test_the_map_name_update_that_game_py_skips_does_nothing(self):
        world = HudWorld(True)
        with world:
            shower = world.module("nui_map_name").MapNameShower()
            mark = len(world.game.log)
            shower.Update()
            self.assertEqual(world.game.log[mark:], [])


HUD_DOCUMENTS = ("affects", "target", "party", "edge-buttons", "tip-board", "big-board", "map-name")
TAG = re.compile(r"<[A-Za-z][\w-]*\s([^>]*?\bdata-for=\"[^\"]+\"[^>]*)>", re.S)
ATTRIBUTE = re.compile(r"([\w-]+)=\"([^\"]*)\"")


def repeated_element_reads(markup):
    """(data-for, attribute) of every view on a data-for element that reads
    the loop's item. RmlUi 6.3 sorts the views of a repeated element at the
    same order as the data-for that removes it, so when the list shrinks they
    may read the gone entry first: "list index N is out of range" and "Could
    not get value from data variable" in syserr."""
    found = []
    for match in TAG.finditer(markup):
        attributes = dict(ATTRIBUTE.findall(match.group(1)))
        names = attributes["data-for"].split(":")[0].split(",") if ":" in attributes["data-for"] else ["it"]
        item = re.compile(r"(?<![\w.])%s\b" % re.escape(names[0].strip()))
        for name, value in attributes.items():
            if name.startswith("data-") and name != "data-for" and not name.startswith("data-event-") and item.search(value):
                found.append((attributes["data-for"], name))
    return found


# Each Wave 2a window and the legacy class it stands for (file, class).
LEGACY_CLASSES = {
    "taskbar": ("uitaskbar.py", "TaskBar"), "expanded-taskbar": ("uitaskbar.py", "ExpandedTaskBar"),
    "energy-bar": ("uitaskbar.py", "EnergyBar"), "gift-box": ("uitaskbar.py", "GiftBox"),
    "game-buttons": ("uigamebutton.py", "GameButtonWindow"), "affects": ("uiaffectshower.py", "AffectShower"),
    "target": ("uitarget.py", "TargetBoard"), "party": ("uiparty.py", "PartyWindow"),
    "edge-buttons": ("uiwhisper.py", "LegacyWhisperButton"), "tip-board": ("uitip.py", "TipBoard"),
    "big-board": ("uitip.py", "BigBoard"), "map-name": ("uimapnameshower.py", "MapNameShower"),
}
BELOW_LEGACY_UI = "nui-below-legacy-ui"


def legacy_layer(file_name, class_name):
    """The wndMgr layer the legacy class's own __init__ passes to its base
    class's (ui.Window's default, "UI", when it passes none)."""
    tree = ast.parse(read(os.path.join(ROOT, file_name)))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    for call in ast.walk(item):
                        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "__init__"
                                and len(call.args) >= 2 and isinstance(call.args[1], ast.Constant)):
                            return call.args[1].value
                    return "UI"
    raise AssertionError("%s has no class %s" % (file_name, class_name))


class Layers(unittest.TestCase):
    def test_a_window_whose_legacy_window_lives_in_the_ui_layer_draws_below_that_layer(self):
        layers = {}
        for window, (file_name, class_name) in LEGACY_CLASSES.items():
            layer = legacy_layer(file_name, class_name)
            layers[window] = layer
            body = re.search(r"<body[^>]*\bclass=\"([^\"]*)\"", read(os.path.join(WINDOWS, window, window + ".rml"))).group(1).split()
            self.assertEqual(BELOW_LEGACY_UI in body, layer == "UI", "%s (legacy %s.%s in %s)" % (window, file_name, class_name, layer))
        self.assertEqual(sorted(window for window, layer in layers.items() if layer != "UI"),
                         ["edge-buttons", "map-name", "taskbar"], "the legacy TOP_MOST windows")


REPO = os.path.normpath(os.path.join(support.support.HERE, ".."))
YMIR_UI = os.path.join(REPO, "assets", "ETC", "ymir work", "ui")


def legacy_texel(k):
    """The icon texel legacy's SetScale(0.7) quad shows at pixel k of the
    icon (22.4 px wide, pixel centers at k + 0.5), measured in game against
    the atlas (Wave 2a final stage)."""
    return int((k + 0.5) / 0.7)


def snapped_texel(k):
    """The texel a 22.4dp box laid out at 22 px shows (the copy before the
    fix): another step, other texels."""
    return int((k + 0.5) * 32 / 22)


class ClassicAffectIcons(unittest.TestCase):
    """The classic affect icons at 100%: the nearest copy draws legacy's
    texels (finding P5 of the Wave 2a in-game validation)."""

    def nearest_block(self):
        sheet = read(os.path.join(CLASSIC_WINDOWS, "affects.rcss"))
        media = re.search(r"@media \(max-resolution: 1x\)\s*\{(.*)\}\s*$", sheet, re.S).group(1)
        return re.search(r"\.affect--small \.affect__image\.affect__image--nearest\s*\{([^}]*)\}", media).group(1)

    def test_the_nearest_copy_is_its_32dp_art_scaled_by_70_percent_from_its_top_left_corner(self):
        block = self.nearest_block()
        for declaration in ("position: absolute", "width: 32dp", "height: 32dp", "transform: scale(0.7)",
                            "transform-origin: left top"):
            self.assertIn(declaration, block)
        self.assertNotIn("px", block.replace("32dp", ""), "a layout box in px or a translate would be snapped again")

    def sub_region(self, image):
        path = os.path.join(YMIR_UI, image.lower().split("d:/ymir work/ui/", 1)[1])
        fields = {}
        with io.open(path, "r", encoding="latin-1") as f:
            for line in f:
                parts = line.split(None, 1)
                if len(parts) == 2:
                    fields[parts[0]] = parts[1].strip().strip('"')
        return os.path.join(YMIR_UI, fields["image"].lower()), int(fields["left"]), int(fields["top"])

    def matches(self, golden, atlas, left, top, x0, y0, texel):
        """Opaque texels of the icon whose golden pixel has the texel's
        color (within 4, the DDS decoders' rounding), and all of them."""
        good = total = 0
        for j in range(22):
            for k in range(22):
                tx, ty = texel(k), texel(j)
                if tx > 31 or ty > 31:
                    continue
                r, g, b, a = atlas.getpixel((left + tx, top + ty))
                if a < 255:
                    continue
                total += 1
                pr, pg, pb = golden.getpixel((x0 + k, y0 + j))[:3]
                good += max(abs(pr - r), abs(pg - g), abs(pb - b)) <= 4
        return good, total

    def test_the_golden_draws_the_texels_legacy_draws(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("needs Pillow")
        golden = Image.open(os.path.join(REPO, "docs", "ui", "snapshots", "affects-classic-100.png")).convert("RGBA")
        fixture = json.loads(read(os.path.join(WINDOWS, "affects", "affects.fixture.json")))
        checked = 0
        for index, icon in enumerate(fixture["affects"]["icons"]):
            if not icon["small"] or not icon["image"].lower().endswith(".sub"):
                continue
            atlas_path, left, top = self.sub_region(icon["image"])
            atlas = Image.open(atlas_path).convert("RGBA")
            x0, y0 = 10 + 25 * index, 10  # .affects__row at 10dp, 25dp cells
            good, total = self.matches(golden, atlas, left, top, x0, y0, legacy_texel)
            self.assertGreater(total, 300, icon["image"])
            self.assertEqual(good, total, "%s: legacy's texels" % icon["image"])
            good, total = self.matches(golden, atlas, left, top, x0, y0, snapped_texel)
            self.assertLess(good, 0.9 * total, "%s: the check tells the 22 px step apart" % icon["image"])
            checked += 1
        self.assertGreaterEqual(checked, 4)


class RepeatedElements(unittest.TestCase):
    def test_no_repeated_hud_element_binds_its_own_item(self):
        for window in HUD_DOCUMENTS:
            markup = read(os.path.join(WINDOWS, window, window + ".rml"))
            self.assertEqual(repeated_element_reads(markup), [], window)

    def test_the_check_finds_a_view_that_reads_the_item_and_lets_the_index_pass(self):
        self.assertEqual(repeated_element_reads('<div data-for="b : buttons" data-if="b.shown"></div>'),
                         [("b : buttons", "data-if")])
        self.assertEqual(repeated_element_reads('<div data-for="items" data-attr-id="it.id"></div>'),
                         [("items", "data-attr-id")])
        self.assertEqual(repeated_element_reads('<div data-for="b, i : buttons" data-if="i != at || shown"\n'
                                                ' data-event-click="press(b.id)"><span data-attr-id="b.id"/></div>'), [])


# --- the affect icons: differential ----------------------------------------------------------

AFFECT_GETTERS = ("AffectIndexToSkillIndex",)
DS_SLOT = PLAYER["DRAGON_SOUL_EQUIPMENT_SLOT_START"]


def affect_setup(game):
    game.answer("player", "AffectIndexToSkillIndex", lambda affect: {CHR["AFFECT_JEONGWI"]: 3}.get(affect, 0))
    game.answer("player", "GetAutoPotionInfo", lambda kind: game.auto_potion)
    game.auto_potion = (True, 725, 1000, 5)
    game.give(5, 72723)
    # The deck's item, as GetItemIndex(slot) and GetItemMetinSocket(INVENTORY, slot, n) read it.
    game.give(DS_SLOT, 110000, sockets=(game.timestamp + 5000, 0, 0))
    game.give((support.PLAYER_CONSTANTS["INVENTORY"], DS_SLOT), 110000, sockets=(game.timestamp + 5000, 0, 0))
    game.answer("item", "GetLimit", lambda index: (ITEM["LIMIT_REAL_TIME"], 0) if index == 0 else (ITEM["LIMIT_NONE"], 0))


class AffectWorlds(unittest.TestCase):
    def worlds(self):
        legacy, novaui = pair(affect_setup)
        for world in (legacy, novaui):
            with world:
                world.shower = world.make("affects", world.module("uiAffectShower").AffectShower, "nui_affects.AffectShower")
        self.assertEqual(type(legacy.shower).__module__, "uiAffectShower")
        self.assertEqual(type(novaui.shower).__module__, "nui_affects")
        return legacy, novaui

    @staticmethod
    def advance(legacy, novaui, seconds):
        for world in (legacy, novaui):
            world.game.timestamp += int(seconds)
            world.game.time += seconds
            world.game.state.now += seconds

    def both(self, legacy, novaui, steps):
        for world in (legacy, novaui):
            mark = len(world.game.log)
            with world, quiet():
                steps(world.shower)
            world.result = world.effects(mark, AFFECT_GETTERS)
        self.assertEqual(novaui.result, legacy.result)

    @staticmethod
    def legacy_view(world):
        """The icons legacy shows, left to right: (image, scale, what a hover shows)."""
        shower = world.shower
        images = [image for image in list(shower.affectImageDict.values()) + [shower.horseImage, shower.lovePointImage]
                  if image is not None and image.IsShow()]
        view = []
        with world, quiet():
            for image in sorted(images, key=lambda image: image.position[0]):
                image.OnMouseOverIn()
                tooltip = getattr(image, "toolTip", None)
                text_line = getattr(image, "toolTipText", None)
                if tooltip is not None and tooltip.visible:
                    hover = ("board", tooltip.title or None, list(tooltip.lines))
                elif text_line is not None and text_line.shown:
                    hover = ("label", text_line.text)
                else:
                    hover = None
                image.OnMouseOverOut()
                view.append((image.image, image.scale[0], hover))
        return view

    @staticmethod
    def novaui_view(world):
        board = world.shower.board
        view = []
        with world, quiet():
            for icon in board.get("icons"):
                board.fire("icon_over", icon["key"])
            now = world.game.state.now
            for icon in board.get("icons"):
                if icon["label"]:
                    hover = ("label", plain(icon["title"]))
                elif icon["title"] or icon["line"] or icon["end"] > 0:
                    if icon["clocked"] and icon["end"] > 0:
                        remain = max(0, int(icon["end"] - now + 1e-7))
                        lines = ["(%s : %s)" % ("LEFT_TIME", rt_second_to_dhms(remain))]
                    else:
                        lines = plain(icon["line"]).split("\n") if icon["line"] else []
                    hover = ("board", plain(icon["title"]) or None, lines)
                else:
                    hover = None
                view.append((icon["image"], 0.7 if icon["small"] else 1, hover))
        return view

    def same_view(self, legacy, novaui):
        expected = self.legacy_view(legacy)
        self.assertEqual(self.novaui_view(novaui), expected)
        return expected


class AffectDifferential(AffectWorlds):
    def every_kind(self, shower):
        MALL = CHR["NEW_AFFECT_MALL"]
        # A classic affect's duration before its icon (MR-16), then the icon.
        shower.BINARY_NEW_AddAffect(200, 0, 0, 3725, CHR["AFFECT_MOV_SPEED_POTION"] + 1)
        shower.SetAffect(CHR["AFFECT_MOV_SPEED_POTION"])
        shower.SetAffect(CHR["AFFECT_JEONGWI"])
        shower.BINARY_NEW_AddAffect(CHR["NEW_AFFECT_EXP_BONUS"], 0, 50, shower.INFINITE_AFFECT_DURATION + 1)
        shower.BINARY_NEW_AddAffect(MALL, PLAYER["POINT_MALL_ITEMBONUS"], 50, 3600)
        shower.BINARY_NEW_AddAffect(CHR["NEW_AFFECT_NO_DEATH_PENALTY"], 0, 1, 3600)
        shower.BINARY_NEW_AddAffect(CHR["NEW_AFFECT_AUTO_HP_RECOVERY"], 0, 0, 3600)
        shower.BINARY_NEW_AddAffect(CHR["NEW_AFFECT_DRAGON_SOUL_DECK1"], 0, 0, 0)
        shower.BINARY_NEW_AddAffect(MALL, PLAYER["POINT_MALL_ITEMBONUS"], 50, 3600)  # a second add changes nothing
        shower.BINARY_NEW_AddAffect(999, 0, 0, 10)                                   # not in the table
        shower.SetHorseState(15, 3, 1)
        shower.SetLoverInfo("Partner", 50)

    def test_every_kind_of_icon_shows_as_legacy_shows_it_and_the_times_count_down(self):
        legacy, novaui = self.worlds()
        self.both(legacy, novaui, self.every_kind)
        view = self.same_view(legacy, novaui)
        self.assertEqual([hover[0] if hover else None for _, _, hover in view],
                         ["board", "board", "label", "label", "board", "board", "board", "board"],
                         "the horse, then the affects in the order they came")
        self.assertIn(("d:/ymir work/ui/skill/common/affect/Increase_Move_Speed.sub", 0.7,
                       ("board", "SKILL_INC_MOVSPD", ["(LEFT_TIME : 1 HOUR, 2 MINUTE, 5 SECOND)"])), view)
        self.assertIn(("d:/ymir work/ui/pattern/auto_hpgauge/05.dds", 0.7, ("board", "item 72723", ["Remainder: 72.50%"])), view)
        self.assertIn(("d:/ymir work/ui/dragonsoul/buff_ds_sky1.tga", 1, ("board", "TOOLTIP_DRAGON_SOUL_DECK1(0.0)",
                       ["(LEFT_TIME : 1 HOUR, 23 MINUTE, 20 SECOND)"])), view)
        self.assertIn(("d:/ymir work/ui/skill/common/affect/gold_premium.sub", 0.7,
                       ("board", "item 71004", ["TOOLTIP_APPLY_NO_DEATH_PENALTY(1.0)"])), view)
        self.assertEqual(view[0], ("d:/ymir work/ui/pattern/HorseState/31.dds", 0.7, ("board", None, ["HORSE_LEVEL2", "HORSE_HEALTH3"])))
        self.advance(legacy, novaui, 10)
        view = self.same_view(legacy, novaui)
        self.assertIn(("d:/ymir work/ui/skill/common/affect/Increase_Move_Speed.sub", 0.7,
                       ("board", "SKILL_INC_MOVSPD", ["(LEFT_TIME : 1 HOUR, 1 MINUTE, 55 SECOND)"])), view)
        self.advance(legacy, novaui, 4000)
        self.same_view(legacy, novaui)

    def test_the_heart_follows_show_hide_and_the_love_point(self):
        legacy, novaui = self.worlds()
        self.both(legacy, novaui, lambda shower: (shower.SetAffect(CHR["AFFECT_JEONGWI"]), shower.SetLoverInfo("Partner", 50)))
        self.assertEqual(len(self.same_view(legacy, novaui)), 1, "a new heart starts hidden")
        self.both(legacy, novaui, lambda shower: shower.ShowLoverState())
        view = self.same_view(legacy, novaui)
        self.assertEqual(view[0], ("d:/ymir work/ui/pattern/LovePoint/03.dds", 0.7, ("board", "Partner", ["Love points: 50%"])))
        self.both(legacy, novaui, lambda shower: shower.OnUpdateLovePoint(100))
        self.assertEqual(self.same_view(legacy, novaui)[0][0], "d:/ymir work/ui/pattern/LovePoint/05.dds")
        self.both(legacy, novaui, lambda shower: shower.HideLoverState())
        self.assertEqual(len(self.same_view(legacy, novaui)), 1)
        self.both(legacy, novaui, lambda shower: (shower.ShowLoverState(), shower.ClearLoverState()))
        self.assertEqual(len(self.same_view(legacy, novaui)), 1)

    def test_a_love_point_between_the_grades_takes_its_grades_art_where_legacy_looks_up_a_fraction(self):
        legacy, novaui = self.worlds()
        self.both(legacy, novaui, lambda shower: (shower.SetLoverInfo("Partner", 60), shower.ShowLoverState()))
        self.assertEqual(self.legacy_view(legacy)[0][0], "d:/ymir work/ui/pattern/LovePoint/00.dds",
                         "legacy: 60 / 25 + 1 is 3.4, no key of FILE_DICT (and 00.dds does not exist)")
        self.assertEqual(self.novaui_view(novaui)[0][0], "d:/ymir work/ui/pattern/LovePoint/03.dds")

    def test_removing_clearing_on_death_and_clearing_all_follow_legacy(self):
        legacy, novaui = self.worlds()
        self.both(legacy, novaui, self.every_kind)
        self.both(legacy, novaui, lambda shower: shower.BINARY_NEW_RemoveAffect(CHR["NEW_AFFECT_MALL"], PLAYER["POINT_MALL_ITEMBONUS"]))
        self.same_view(legacy, novaui)
        self.both(legacy, novaui, lambda shower: (shower.ResetAffect(CHR["AFFECT_JEONGWI"]), shower.ResetAffect(77)))
        self.same_view(legacy, novaui)
        self.both(legacy, novaui, lambda shower: shower.SetAffect(CHR["AFFECT_JEONGWI"]))
        view = self.same_view(legacy, novaui)
        self.assertEqual(view[-1][2], ("label", "skill 3"), "an affect added again goes to the end")
        self.both(legacy, novaui, lambda shower: shower.ClearAffects())
        view = self.same_view(legacy, novaui)
        self.assertNotIn(("label", "skill 3"), [hover for _, _, hover in view], "the skill affects go on death")
        self.assertIn("d:/ymir work/ui/pattern/auto_hpgauge/05.dds", [image for image, _, _ in view], "the others stay")
        self.both(legacy, novaui, lambda shower: shower.SetHorseState(0, 0, 0))
        self.same_view(legacy, novaui)
        self.both(legacy, novaui, lambda shower: shower.ClearAllAffects())
        self.assertEqual(self.same_view(legacy, novaui), [])

    def test_a_classic_duration_after_the_icon_makes_it_clocked(self):
        legacy, novaui = self.worlds()

        def steps(shower):
            shower.SetAffect(CHR["AFFECT_JEONGWI"])
            shower.BINARY_NEW_AddAffect(200, 0, 0, 90, CHR["AFFECT_JEONGWI"] + 1)
            shower.BINARY_NEW_AddAffect(200, 0, 0, 90, 0)        # no AFF_* bit
            shower.BINARY_NEW_AddAffect(200, 0, 0, 90, 64)       # a bit not in the table
        self.both(legacy, novaui, steps)
        self.assertEqual(self.same_view(legacy, novaui),
                         [("d:/ymir work/ui/skill/warrior/jeongwi_03.sub", 0.7, ("board", "skill 3", ["(LEFT_TIME : 1 MINUTE, 30 SECOND)"]))])

    def test_a_hover_reads_the_auto_potion_and_the_dragon_soul_time_once(self):
        legacy, novaui = self.worlds()
        self.both(legacy, novaui, lambda shower: (shower.BINARY_NEW_AddAffect(CHR["NEW_AFFECT_AUTO_HP_RECOVERY"], 0, 0, 0),
                                                  shower.BINARY_NEW_AddAffect(CHR["NEW_AFFECT_DRAGON_SOUL_DECK1"], 0, 0, 0)))
        for world in (legacy, novaui):
            world.game.auto_potion = (True, 100, 1000, -1)
        self.advance(legacy, novaui, 1000)
        view = self.same_view(legacy, novaui)
        self.assertEqual(view[0][2], ("board", "Sun Elixir", ["Remainder: 10.00%"]))
        self.assertEqual(view[1][2], ("board", "TOOLTIP_DRAGON_SOUL_DECK1(0.0)", ["(LEFT_TIME : 1 HOUR, 6 MINUTE, 40 SECOND)"]))
        with novaui:
            mark = len(novaui.game.log)
            novaui.shower.board.fire("icon_over", CHR["NEW_AFFECT_AUTO_HP_RECOVERY"])
            calls = [name for name, args in novaui.game.log[mark:]]
        self.assertEqual(calls.count("player.GetAutoPotionInfo"), 1, "once per hover")

    def test_a_locale_change_names_the_affects_again_with_their_values(self):
        legacy, novaui = self.worlds()
        self.both(legacy, novaui, lambda shower: (shower.SetAffect(CHR["AFFECT_JEONGWI"]),
                                                  shower.BINARY_NEW_AddAffect(CHR["NEW_AFFECT_MALL"], PLAYER["POINT_MALL_EXPBONUS"], 20, 600)))
        with novaui:
            novaui.game.modules["skill"].__dict__["_answers"]["GetSkillName"] = lambda index: "Berserk"
            novaui.game.modules["localeInfo"].TOOLTIP_MALL_EXPBONUS = lambda value: "EXP +%d%%" % value
            novaui.shower.RefreshLocale()
        view = self.novaui_view(novaui)
        self.assertEqual(view[0][2], ("label", "Berserk"))
        self.assertEqual(view[1][2][1], "EXP +20%", "formatted with its value, where legacy kept the unformatted entry")

    def test_the_shower_shows_itself_and_hides_and_destroys_its_document(self):
        legacy, novaui = self.worlds()
        self.assertTrue(legacy.shower.IsShow())
        self.assertTrue(novaui.shower.IsShow(), "legacy shows the window when it is made")
        with novaui:
            board = novaui.shower.board
            novaui.shower.Hide()
            self.assertFalse(novaui.shower.IsShow())
            novaui.shower.SetPlayTime(42)
            self.assertEqual(novaui.shower.serverPlayTime, 42)
            novaui.shower.Destroy()
            self.assertEqual(board.calls[-1], ("destroy",))
            novaui.shower.SetAffect(CHR["AFFECT_JEONGWI"])


# --- the target board: differential --------------------------------------------------------

MAIN_VID = 1
PEER_VID = 77


def target_setup(game):
    """A target world: game.target holds the relation the stand-ins answer."""
    t = game.target = {"same_empire": True, "party": set(), "leaders": set(), "pvp": False, "revenge": False,
                       "challenge": False, "cant_fight": False, "distance": 1000, "horse": False, "buildings": set(),
                       "friend": False, "guild_auth": set(), "guild_member": False, "guild_id": 0, "chr_party": False,
                       "names": {PEER_VID: "NuiW2B2", 300: "Wild Dog"}, "levels": {300: 23}, "grades": {300: 4}}
    answer = game.answer
    answer("player", "IsSameEmpire", lambda vid: t["same_empire"])
    answer("player", "IsMainCharacterIndex", lambda vid: vid == MAIN_VID)
    answer("player", "GetMainCharacterIndex", lambda: MAIN_VID)
    answer("player", "IsPVPInstance", lambda vid: t["pvp"])
    answer("player", "IsPartyMember", lambda vid: vid in t["party"])
    answer("player", "IsPartyLeader", lambda vid: vid in t["leaders"])
    answer("player", "IsRevengeInstance", lambda vid: t["revenge"])
    answer("player", "IsChallengeInstance", lambda vid: t["challenge"])
    answer("player", "IsCantFightInstance", lambda vid: t["cant_fight"])
    answer("player", "GetCharacterDistance", lambda vid: t["distance"])
    answer("player", "IsMountingHorse", lambda: t["horse"])
    answer("chr", "GetInstanceType", lambda vid: CHR["INSTANCE_TYPE_BUILDING"] if vid in t["buildings"] else CHR["INSTANCE_TYPE_PLAYER"])
    answer("chr", "GetNameByVID", lambda vid: t["names"].get(vid, ""))
    answer("chr", "GetGuildID", lambda vid: t["guild_id"])
    answer("chr", "IsPartyMember", lambda vid: t["chr_party"])
    answer("nonplayer", "GetLevelByVID", lambda vid: t["levels"].get(vid, -1))
    answer("nonplayer", "GetGradeByVID", lambda vid: t["grades"].get(vid, -1))
    answer("messenger", "IsFriendByName", lambda name: t["friend"])
    answer("guild", "MainPlayerHasAuthority", lambda auth: auth in t["guild_auth"])
    answer("guild", "IsMemberByName", lambda name: t["guild_member"])
    answer("guild", "GetGuildMasterName", lambda: "Master")


class TargetWorlds(unittest.TestCase):
    def worlds(self, **relation):
        def setup(game):
            target_setup(game)
            game.target.update(relation)
        legacy, novaui = pair(setup)
        for world in (legacy, novaui):
            with world:
                world.board = world.make("target", world.module("uiTarget").TargetBoard, "nui_target.TargetBoard")
                world.whispers = []
                world.board.SetWhisperEvent(world.whispers.append)
                world.board.Hide()
        self.assertEqual(type(novaui.board).__module__, "nui_target")
        return legacy, novaui

    def both(self, legacy, novaui, steps, nui_steps=None):
        for world, run in ((legacy, steps), (novaui, nui_steps or steps)):
            mark = len(world.game.log)
            with world, quiet():
                run(world)
            world.result = world.effects(mark)
        self.assertEqual(novaui.result, legacy.result)
        return legacy.result

    @staticmethod
    def legacy_view(world):
        board = world.board
        ids = dict((id(button), key) for key, button in board.buttonDict.items())
        buttons = []
        for button in board.showingButtonList:
            if button.shown and ids[id(button)] not in buttons:
                buttons.append(ids[id(button)])
        return {"shown": bool(board.IsShow()), "name": board.name.text, "buttons": buttons,
                "hp": board.hpGauge.percentage if board.hpGauge.shown else None}

    @staticmethod
    def novaui_view(world):
        board = world.board
        model = board.board.model
        buttons = [b["id"] for i, b in enumerate(model["buttons"]) if i != model["exchange_at"] or model["in_range"]]
        return {"shown": bool(board.IsShow()), "name": plain(model["name"]), "buttons": buttons,
                "hp": model["hp"] if model["show_hp"] else None}

    def same_view(self, legacy, novaui):
        expected = self.legacy_view(legacy)
        self.assertEqual(self.novaui_view(novaui), expected)
        return expected

    @staticmethod
    def press(world, button_id):
        """A button's click: the legacy button's event, the board's press."""
        if world.nui_on:
            world.board.board.fire("press", button_id, 0)
        else:
            world.board.buttonDict[button_id].Click()


B = None  # the button ids, from the legacy class once a world exists


class TargetDifferential(TargetWorlds):
    def ids(self, world):
        return world.module("uiTarget").TargetBoard

    def test_a_player_targets_buttons_follow_refresh_buttons_rules(self):
        cases = [
            ({}, "a stranger"),
            ({"friend": True}, "a friend"),
            ({"party": {PEER_VID, MAIN_VID}, "leaders": {PEER_VID}}, "the party's leader"),
            ({"party": {PEER_VID, MAIN_VID}, "leaders": {MAIN_VID}}, "a member of the player's party"),
            ({"party": {MAIN_VID}, "leaders": {MAIN_VID}}, "the leader invites"),
            ({"party": {MAIN_VID}}, "a member cannot invite"),
            ({"chr_party": True}, "a member of another party"),
            ({"revenge": True}, "revenge"),
            ({"challenge": True}, "a challenge"),
            ({"cant_fight": True}, "cannot fight"),
            ({"same_empire": False}, "another empire"),
            ({"guild_auth": {GUILD["AUTH_ADD_MEMBER"]}}, "a guild invitation"),
            ({"guild_auth": {GUILD["AUTH_REMOVE_MEMBER"]}, "guild_member": True, "guild_id": 3}, "a guild removal"),
            ({"distance": 3001}, "out of the exchange range"),
            ({"pvp": True}, "in a duel"),
        ]
        for relation, label in cases:
            legacy, novaui = self.worlds(**relation)
            self.both(legacy, novaui, lambda world: world.board.Open(PEER_VID, "NuiW2B2"))
            view = self.same_view(legacy, novaui)
            self.assertEqual(view["name"], "NuiW2B2", label)
            if relation == {}:
                T = self.ids(legacy)
                self.assertEqual(view["buttons"], [T.BTN_WHISPER, T.BTN_EXCHANGE, T.BTN_FIGHT, T.BTN_EMOTION_ALLOW,
                                                   T.BTN_FRIEND, T.BTN_INVITE_PARTY])
            self.assertTrue(view["shown"], label)

    def test_every_button_sends_the_legacy_packet(self):
        legacy, novaui = self.worlds(guild_auth={GUILD["AUTH_ADD_MEMBER"]}, party={PEER_VID, MAIN_VID}, leaders={MAIN_VID})
        self.both(legacy, novaui, lambda world: world.board.Open(PEER_VID, "NuiW2B2"))
        buttons = self.same_view(legacy, novaui)["buttons"]
        T = self.ids(legacy)
        self.assertIn(T.BTN_EXCLUDE, buttons)
        self.assertIn(T.BTN_INVITE_GUILD, buttons)

        def steps(world):
            for button_id in buttons:
                self.press(world, button_id)
        result = self.both(legacy, novaui, steps)
        self.assertIn(("net.SendExchangeStartPacket", (PEER_VID,)), result)
        self.assertIn(("net.SendPartyRemovePacket", (PEER_VID,)), result)
        self.assertIn(("net.SendGuildAddMemberPacket", (PEER_VID,)), result)
        self.assertIn(("net.SendChatPacket", ("/emotion_allow %d" % PEER_VID,)), result)
        self.assertEqual(novaui.whispers, legacy.whispers)
        self.assertEqual(novaui.whispers, ["NuiW2B2"])

    def test_the_relation_buttons_without_a_vid_and_the_main_characters_menu(self):
        legacy, novaui = self.worlds(horse=True)
        self.both(legacy, novaui, lambda world: world.board.Open(0, "Somebody"))
        T = self.ids(legacy)
        self.assertEqual(self.same_view(legacy, novaui)["buttons"], [T.BTN_WHISPER, T.BTN_VOTE_BLOCK_CHAT])
        result = self.both(legacy, novaui, lambda world: self.press(world, T.BTN_VOTE_BLOCK_CHAT))
        self.assertEqual(result, [("net.SendChatPacket", ("/vote_block_chat Somebody",))])
        self.both(legacy, novaui, lambda world: world.board.Open(MAIN_VID, "Me"))
        self.assertEqual(self.same_view(legacy, novaui)["buttons"], [T.BTN_DISMOUNT])
        self.assertEqual(self.both(legacy, novaui, lambda world: self.press(world, T.BTN_DISMOUNT)),
                         [("net.SendChatPacket", ("/unmount",))])
        legacy, novaui = self.worlds()
        self.both(legacy, novaui, lambda world: world.board.Open(MAIN_VID, "Me"))
        self.assertFalse(self.same_view(legacy, novaui)["shown"], "nothing to offer: the board hides")

    def test_another_empire_and_a_building_hide_the_board(self):
        legacy, novaui = self.worlds(same_empire=False)
        for world in (legacy, novaui):
            world.module("constInfo").SET_VIEW_OTHER_EMPIRE_PLAYER_TARGET_BOARD(0)
        self.both(legacy, novaui, lambda world: world.board.Open(PEER_VID, "NuiW2B2"))
        self.assertFalse(self.same_view(legacy, novaui)["shown"])
        legacy, novaui = self.worlds(buildings={PEER_VID})
        self.both(legacy, novaui, lambda world: world.board.Open(PEER_VID, "Building"))
        self.assertFalse(self.same_view(legacy, novaui)["shown"])

    def test_a_monster_shows_its_level_grade_and_hp(self):
        legacy, novaui = self.worlds()

        def steps(world):
            # game.py SetHPTargetBoard
            vid = 300
            if vid != world.board.GetTargetVID():
                world.board.ResetTargetBoard()
                world.board.SetEnemyVID(vid)
            world.board.SetHP(62)
            world.board.Show()
        self.both(legacy, novaui, steps)
        view = self.same_view(legacy, novaui)
        self.assertEqual(view, {"shown": True, "name": "Lv.23 (TARGET_LEVEL_BOSS) Wild Dog", "buttons": [], "hp": 0.62})
        self.both(legacy, novaui, lambda world: world.board.SetHP(140))
        self.assertEqual(self.same_view(legacy, novaui)["hp"], 1.0)
        self.assertEqual(novaui.board.GetTargetVID(), 300)
        self.assertEqual(novaui.board.GetTargetName(), "Lv.23 (TARGET_LEVEL_BOSS) Wild Dog")

    def test_the_exchange_button_follows_the_distance_c_plus_plus_watches(self):
        legacy, novaui = self.worlds()
        T = self.ids(legacy)
        self.both(legacy, novaui, lambda world: world.board.Open(PEER_VID, "NuiW2B2"))
        self.assertIn(T.BTN_EXCHANGE, self.same_view(legacy, novaui)["buttons"])
        self.assertIn(("nuigame.WatchTargetRange", (PEER_VID, 3000)), novaui.game.log)
        for distance, in_range in ((3500, False), (2500, True), (-1, True)):
            legacy.game.target["distance"] = distance
            with legacy, quiet():
                legacy.board.OnUpdate()
            # C++ publishes target.in_range; a negative distance keeps the last answer.
            if distance >= 0:
                novaui.game.state.publish("target.in_range", in_range)
            self.assertEqual(self.same_view(legacy, novaui)["buttons"].count(T.BTN_EXCHANGE), 1 if in_range else 0, distance)
        mark = len(novaui.game.log)
        with novaui:
            novaui.board.Close()
        self.assertIn(("nuigame.WatchTargetRange", (0, 0)), novaui.game.log[mark:])

    def test_close_escape_and_refresh_follow_legacy(self):
        legacy, novaui = self.worlds()
        self.both(legacy, novaui, lambda world: world.board.Open(PEER_VID, "NuiW2B2"))
        self.assertTrue(novaui.board.escape.is_shown(), "its Escape proxy shows with it")
        for world in (legacy, novaui):
            world.game.target["friend"] = True
        self.both(legacy, novaui, lambda world: (world.board.RefreshByVID(5), world.board.RefreshByName("x")))
        T = self.ids(legacy)
        self.assertIn(T.BTN_FRIEND, self.same_view(legacy, novaui)["buttons"], "another target refreshes nothing")
        self.both(legacy, novaui, lambda world: world.board.RefreshByVID(PEER_VID))
        self.assertNotIn(T.BTN_FRIEND, self.same_view(legacy, novaui)["buttons"])

        def escape(world):
            if world.nui_on:
                self.assertIs(world.board.escape._window.OnPressEscapeKey(), True)
            else:
                self.assertIs(world.board.OnPressEscapeKey(), True)
        result = self.both(legacy, novaui, escape)
        self.assertEqual(result, [("player.ClearTarget", ())])
        self.assertFalse(self.same_view(legacy, novaui)["shown"])
        self.assertFalse(novaui.board.escape.is_shown())
        self.assertEqual(novaui.board.GetTargetVID(), 0)
        self.both(legacy, novaui, lambda world: (world.board.Open(PEER_VID, "NuiW2B2"), world.board.closeButton.Click()),
                  lambda world: (world.board.Open(PEER_VID, "NuiW2B2"), world.board.board.fire("close", 1),
                                 world.board.board.fire("close", 0)))
        self.assertFalse(novaui.board.IsShow(), "the close button")

    def test_the_guild_removal_asks_first(self):
        legacy, novaui = self.worlds(guild_auth={GUILD["AUTH_REMOVE_MEMBER"]}, guild_member=True, guild_id=3)
        T = self.ids(legacy)
        self.both(legacy, novaui, lambda world: world.board.Open(PEER_VID, "NuiW2B2"))
        self.assertIn(T.BTN_REMOVE_GUILD, self.same_view(legacy, novaui)["buttons"])
        for world in (legacy, novaui):
            QuestionDialog.made = []
            with world:
                self.press(world, T.BTN_REMOVE_GUILD)
            world.dialog = QuestionDialog.made[-1]
            self.assertTrue(world.dialog.opened)
        self.assertEqual(novaui.dialog.text, legacy.dialog.text)
        result = self.both(legacy, novaui, lambda world: world.dialog.accept())
        self.assertEqual(result, [("net.SendGuildRemoveMemberPacket", ("NuiW2B2",))])
        self.assertFalse(novaui.dialog.opened)

    def test_a_press_on_a_button_that_does_not_show_does_nothing_and_destroy_ends_the_watch(self):
        legacy, novaui = self.worlds()
        T = self.ids(legacy)
        with novaui:
            novaui.board.Open(PEER_VID, "NuiW2B2")
            mark = len(novaui.game.log)
            novaui.board.board.fire("press", T.BTN_DISMOUNT, 0)
            novaui.board.board.fire("press", T.BTN_WHISPER, 1)
            self.assertEqual(novaui.effects(mark), [])
            self.assertEqual(novaui.whispers, [], "a right press")
            board = novaui.board.board
            novaui.board.Destroy()
            self.assertEqual(board.calls[-1], ("destroy",))
            self.assertIn(("nuigame.WatchTargetRange", (0, 0)), novaui.game.log[mark:])


# --- the party: differential ---------------------------------------------------------------

LEADER, MEMBER, OFFLINE = 1001, 1002, 1003
P = PLAYER


def party_setup(game):
    """A party world: game.party holds what player.GetPartyMember* answer."""
    party = game.party = {"states": {}, "hp": {}, "affects": {}, "leader": True, "skill": 40}
    answer = game.answer
    answer("player", "GetPartyMemberState", lambda pid: party["states"].get(pid, 0))
    answer("player", "GetPartyMemberHPPercentage", lambda pid: party["hp"].get(pid, 0))
    answer("player", "GetPartyMemberAffects", lambda pid: party["affects"].get(pid, [0] * 9))
    answer("player", "IsMainCharacterIndex", lambda vid: vid == MAIN_VID)
    answer("player", "GetMainCharacterIndex", lambda: MAIN_VID)
    answer("player", "IsPartyLeader", lambda vid: party["leader"])
    answer("player", "GetSkillSlotIndex", lambda index: 121)
    game.learn(121, 121, grade=0, level=0)
    game.skills[121]["level"] = 40


class PartyWorlds(unittest.TestCase):
    def worlds(self, skill_level=40):
        def setup(game):
            party_setup(game)
            game.skills[121]["level"] = skill_level
        legacy, novaui = pair(setup)
        for world in (legacy, novaui):
            with world, quiet():
                world.window = world.make("party", world.module("uiParty").PartyWindow, "nui_party.PartyWindow")
                world.window.Hide()
        self.assertEqual(type(novaui.window).__module__, "nui_party")
        return legacy, novaui

    def both(self, legacy, novaui, steps, nui_steps=None):
        for world, run in ((legacy, steps), (novaui, nui_steps or steps)):
            mark = len(world.game.log)
            with world, quiet():
                run(world)
            world.result = world.effects(mark)
        self.assertEqual(novaui.result, legacy.result)
        return legacy.result

    @staticmethod
    def legacy_view(world):
        window = world.window
        Board = world.module("uiParty").PartyMemberInfoBoard
        members = []
        for board in window.partyMemberInfoBoardList:
            roles = []
            for key, button in sorted(board.stateButtonDict.items(), key=lambda pair: pair[1].position[0]):
                if button.shown:
                    roles.append(-1 if key == Board.MEMBER_BUTTON_NORMAL else "expel" if key == Board.MEMBER_BUTTON_EXPEL else key)
            linked = bool(board.gauge.shown)
            members.append({"pid": board.pid, "name": board.nameTextLine.text, "linked": linked,
                            "hp": board.gauge.percentage if linked else None,
                            "art": board.stateButton.visuals["up"].rsplit("/", 1)[-1][:-len("_01.sub")] or "party_state_normal",
                            "affects": [bool(image.shown) for image in board.partyAffectImageList], "roles": roles})
        menu = window.partyMenu
        buttons = [name for name, key in (("heal", menu.BTN_HEAL_ALL), ("break_up", menu.BTN_BREAK_UP), ("leave", menu.BTN_LEAVE))
                   if menu.buttonDict[key].shown]
        modes = [mode for mode, button in menu.modeButtonList.items() if button.down]
        return {"shown": bool(window.IsShow()), "members": members, "menu": bool(menu.IsShow()), "buttons": buttons,
                "mode": modes[0] if modes else -1}

    @staticmethod
    def novaui_view(world):
        window = world.window
        model = window.board.model
        members = []
        for m in model["members"]:
            roles = [b["state"] for b in m["state_buttons"]] + (["expel"] if m["show_states"] else [])
            members.append({"pid": m["pid"], "name": plain(m["name"]), "linked": m["linked"],
                            "hp": m["hp"] if m["linked"] else None, "art": m["state_art"], "affects": m["affects"],
                            "roles": roles})
        buttons = (["heal"] if model["heal_ready"] else []) + (
            (["break_up"] if model["is_leader"] else ["leave"]) if model["has_role"] else [])
        return {"shown": bool(window.IsShow()), "members": members, "menu": model["menu_open"], "buttons": buttons,
                "mode": model["distribution"]}

    def same_view(self, legacy, novaui):
        expected = self.legacy_view(legacy)
        self.assertEqual(self.novaui_view(novaui), expected)
        return expected

    @staticmethod
    def board(world, pid):
        for board in world.window.partyMemberInfoBoardList:
            if board.pid == pid:
                return board

    def form(self, legacy, novaui):
        """Three members: the player leads, the second is linked, the third offline."""
        for world in (legacy, novaui):
            party = world.game.party
            party["states"].update({LEADER: P["PARTY_STATE_LEADER"], MEMBER: P["PARTY_STATE_ATTACKER"], OFFLINE: 0})
            party["hp"].update({LEADER: 80, MEMBER: 40})
            party["affects"].update({LEADER: [5, 0, 0, 0, 0, 0, 3, 0, 0], MEMBER: [0, 2, 0, 0, 0, 0, 0, 0, 0]})

        def steps(world):
            window = world.window
            window.AddPartyMember(LEADER, "NuiW2A2")
            window.AddPartyMember(MEMBER, "NuiW2B2")
            window.AddPartyMember(OFFLINE, "")
            window.LinkPartyMember(LEADER, MAIN_VID)
            window.LinkPartyMember(MEMBER, PEER_VID)
            for pid in (LEADER, MEMBER, OFFLINE, 4444):
                window.UpdatePartyMemberInfo(pid)
        self.both(legacy, novaui, steps)
        return self.same_view(legacy, novaui)


class PartyDifferential(PartyWorlds):
    def test_members_join_link_and_update_as_legacy_shows_them(self):
        legacy, novaui = self.worlds()
        view = self.form(legacy, novaui)
        self.assertTrue(view["shown"])
        self.assertEqual([m["name"] for m in view["members"]], ["NuiW2A2", "NuiW2B2", "PARTY_MEMBER_OFFLINE"])
        self.assertEqual(view["members"][0]["art"], "party_state_leader")
        self.assertEqual(view["members"][1]["hp"], 0.4)
        self.assertEqual(view["buttons"], ["break_up"], "the player leads")
        tips = novaui.window.board.model["members"][0]["affect_tips"]
        self.assertEqual(tips[0], "PARTY_BONUS_EXP(5)")
        self.assertEqual(tips[6], "PARTY_BONUS_DEFENDER(3)")
        self.both(legacy, novaui, lambda world: world.window.UnlinkPartyMember(MEMBER))
        self.assertEqual(self.same_view(legacy, novaui)["members"][1]["affects"], [False] * 9, "unlinked: no affects")
        self.both(legacy, novaui, lambda world: world.window.UnlinkAllPartyMember())
        self.assertFalse(any(m["linked"] for m in self.same_view(legacy, novaui)["members"]))

    def test_a_leaders_press_opens_the_roles_and_a_role_sends_the_state_packets(self):
        for level, roles in ((40, [-1, P["PARTY_STATE_BERSERKER"], P["PARTY_STATE_TANKER"], P["PARTY_STATE_BUFFER"],
                                    P["PARTY_STATE_SKILL_MASTER"], P["PARTY_STATE_DEFENDER"], "expel"]),
                             (10, [-1, "expel"]), (0, ["expel"])):
            legacy, novaui = self.worlds(skill_level=level)
            self.form(legacy, novaui)
            result = self.both(legacy, novaui, lambda world: self.board(world, MEMBER).OnMouseLeftButtonDown(),
                               lambda world: world.window.board.fire("member_press", MEMBER, 0))
            self.assertEqual(result, [("player.SetTarget", (PEER_VID,)), ("player.OpenCharacterMenu", (PEER_VID,))])
            self.assertEqual(self.same_view(legacy, novaui)["members"][1]["roles"], roles, level)
        # The attacker's own role is "withdraw" (-1); another role replaces it.
        legacy, novaui = self.worlds()
        self.form(legacy, novaui)
        for state, packets in ((-1, [(MEMBER, P["PARTY_STATE_ATTACKER"], False)]),
                               (P["PARTY_STATE_TANKER"], [(MEMBER, P["PARTY_STATE_ATTACKER"], False), (MEMBER, P["PARTY_STATE_TANKER"], True)])):
            def legacy_steps(world, state=state):
                board = self.board(world, MEMBER)
                board.OnMouseLeftButtonDown()
                key = board.MEMBER_BUTTON_NORMAL if state == -1 else state
                board.stateButtonDict[key].Click()

            def nui_steps(world, state=state):
                world.window.board.fire("member_press", MEMBER, 0)
                world.window.board.fire("state_pick", MEMBER, state, 0)
            result = self.both(legacy, novaui, legacy_steps, nui_steps)
            self.assertEqual([args for name, args in result if name == "net.SendPartySetStatePacket"], packets)
            self.assertEqual(self.same_view(legacy, novaui)["members"][1]["roles"], [], "the roles close")
        result = self.both(legacy, novaui, lambda world: (self.board(world, MEMBER).OnMouseLeftButtonDown(),
                                                          self.board(world, MEMBER).stateButtonDict[12].Click()),
                           lambda world: (world.window.board.fire("member_press", MEMBER, 0),
                                          world.window.board.fire("expel", MEMBER, 0)))
        self.assertIn(("net.SendPartyRemovePacket", (MEMBER,)), result)

    def test_a_member_who_does_not_lead_opens_no_roles_and_a_second_press_closes_them(self):
        legacy, novaui = self.worlds()
        self.form(legacy, novaui)
        for world in (legacy, novaui):
            world.game.party["leader"] = False
        self.both(legacy, novaui, lambda world: self.board(world, MEMBER).OnMouseLeftButtonDown(),
                  lambda world: world.window.board.fire("member_press", MEMBER, 0))
        self.assertEqual(self.same_view(legacy, novaui)["members"][1]["roles"], [])
        for world in (legacy, novaui):
            world.game.party["leader"] = True
        self.both(legacy, novaui, lambda world: (self.board(world, MEMBER).OnMouseLeftButtonDown(),
                                                 self.board(world, MEMBER).OnMouseRightButtonDown()),
                  lambda world: (world.window.board.fire("member_press", MEMBER, 0),
                                 world.window.board.fire("member_press", MEMBER, 1)))
        self.assertEqual(self.same_view(legacy, novaui)["members"][1]["roles"], [], "the right button toggles as the left")
        self.both(legacy, novaui, lambda world: self.board(world, LEADER).OnMouseLeftButtonDown(),
                  lambda world: world.window.board.fire("member_press", LEADER, 0))
        self.assertEqual(self.same_view(legacy, novaui)["members"][0]["roles"], [], "never for the leader's own board")

    def test_an_item_attached_over_a_member_starts_an_exchange(self):
        for how in ("press", "release", "drop"):
            legacy, novaui = self.worlds()
            self.form(legacy, novaui)

            def legacy_steps(world, how=how):
                world.game.modules["mouseModule"].mouseController.AttachObject("inventory", support.PLAYER_CONSTANTS["SLOT_TYPE_INVENTORY"], 9, 27001)
                board = self.board(world, MEMBER)
                board.OnMouseLeftButtonDown() if how == "press" else board.OnMouseLeftButtonUp()

            def nui_steps(world, how=how):
                world.game.modules["mouseModule"].mouseController.AttachObject("inventory", support.PLAYER_CONSTANTS["SLOT_TYPE_INVENTORY"], 9, 27001)
                if how == "press":
                    world.window.board.fire("member_press", MEMBER, 0)
                elif how == "release":
                    world.window.board.fire("member_release", MEMBER, 0)
                else:
                    world.window.board.fire("member_drop", MEMBER)
            result = self.both(legacy, novaui, legacy_steps, nui_steps)
            self.assertIn(("net.SendExchangeStartPacket", (PEER_VID,)), result, how)
            self.assertIn(("net.SendExchangeItemAddPacket", (9, 0)), result, how)
            self.assertFalse(novaui.game.modules["mouseModule"].mouseController.isAttached(), how)
        # An offline member (no vid) takes nothing.
        result = self.both(legacy, novaui, lambda world: self.board(world, OFFLINE).OnMouseLeftButtonUp(),
                           lambda world: world.window.board.fire("member_release", OFFLINE, 0))
        self.assertEqual(result, [])

    def test_the_menu_heals_breaks_up_and_sets_the_distribution(self):
        legacy, novaui = self.worlds()
        self.form(legacy, novaui)
        self.both(legacy, novaui, lambda world: world.window.partyMenuButton.Click(),
                  lambda world: world.window.board.fire("toggle_menu", 0))
        self.assertTrue(self.same_view(legacy, novaui)["menu"])
        self.both(legacy, novaui, lambda world: world.window.PartyHealReady())
        self.assertEqual(self.same_view(legacy, novaui)["buttons"], ["heal", "break_up"])
        menu_buttons = lambda world: world.window.partyMenu.buttonDict
        result = self.both(legacy, novaui, lambda world: menu_buttons(world)[world.window.partyMenu.BTN_HEAL_ALL].Click(),
                           lambda world: world.window.board.fire("heal", 0))
        self.assertEqual(result, [("net.SendPartyUseSkillPacket", (1, 0))])
        self.assertEqual(self.same_view(legacy, novaui)["buttons"], ["break_up"])
        result = self.both(legacy, novaui, lambda world: menu_buttons(world)[world.window.partyMenu.BTN_BREAK_UP].Click(),
                           lambda world: world.window.board.fire("break_up", 0))
        self.assertEqual(result, [("net.SendPartyExitPacket", ())])
        modes = lambda world: world.window.partyMenu.modeButtonList
        result = self.both(legacy, novaui, lambda world: modes(world)[1].Click(), lambda world: world.window.board.fire("mode", 1, 0))
        self.assertEqual(result, [("net.SendPartyParameterPacket", (1,))])
        self.assertEqual(self.same_view(legacy, novaui)["mode"], 0, "the mode in force shows until the server changes it")
        self.both(legacy, novaui, lambda world: world.window.ChangePartyParameter(1))
        self.assertEqual(self.same_view(legacy, novaui)["mode"], 1)
        self.both(legacy, novaui, lambda world: world.window.ChangePartyParameter(9))
        self.assertEqual(self.same_view(legacy, novaui)["mode"], -1, "an unknown mode: every button up")
        self.both(legacy, novaui, lambda world: world.window.partyMenuButton.Click(),
                  lambda world: world.window.board.fire("toggle_menu", 0))
        self.assertFalse(self.same_view(legacy, novaui)["menu"])

    def test_a_member_sees_leave_and_no_mode_packet(self):
        legacy, novaui = self.worlds()
        for world in (legacy, novaui):
            world.game.party["states"][MEMBER] = P["PARTY_STATE_ATTACKER"]

        def steps(world):
            world.window.AddPartyMember(MEMBER, "NuiW2A2")
            world.window.LinkPartyMember(MEMBER, MAIN_VID)
            world.window.UpdatePartyMemberInfo(MEMBER)
        self.both(legacy, novaui, steps)
        self.assertEqual(self.same_view(legacy, novaui)["buttons"], ["leave"])
        result = self.both(legacy, novaui, lambda world: world.window.partyMenu.modeButtonList[1].Click(),
                           lambda world: world.window.board.fire("mode", 1, 0))
        self.assertEqual(result, [])
        result = self.both(legacy, novaui, lambda world: world.window.partyMenu.buttonDict[world.window.partyMenu.BTN_LEAVE].Click(),
                           lambda world: world.window.board.fire("leave", 0))
        self.assertEqual(result, [("net.SendPartyExitPacket", ())])

    def test_removing_a_member_and_the_players_own_board_ending_the_party(self):
        legacy, novaui = self.worlds()
        self.form(legacy, novaui)
        result = self.both(legacy, novaui, lambda world: (world.window.RemovePartyMember(MEMBER), world.window.RemovePartyMember(5555)))
        self.assertEqual(result, [("player.RemovePartyMember", (MEMBER,))])
        self.assertEqual([m["pid"] for m in self.same_view(legacy, novaui)["members"]], [LEADER, OFFLINE])
        result = self.both(legacy, novaui, lambda world: world.window.RemovePartyMember(LEADER))
        self.assertEqual(result, [("player.ExitParty", ())])
        view = self.same_view(legacy, novaui)
        self.assertEqual((view["shown"], view["members"], view["menu"]), (False, [], False))

    def test_a_leader_who_becomes_a_member_sees_leave_alone_where_legacy_keeps_break_up(self):
        legacy, novaui = self.worlds()
        self.form(legacy, novaui)
        for world in (legacy, novaui):
            world.game.party["states"][LEADER] = P["PARTY_STATE_ATTACKER"]
        self.both(legacy, novaui, lambda world: world.window.UpdatePartyMemberInfo(LEADER))
        self.assertEqual(self.legacy_view(legacy)["buttons"], ["break_up", "leave"],
                         "legacy clears its list without hiding break up (PartyMenu.__ClearShowingButtons)")
        self.assertEqual(self.novaui_view(novaui)["buttons"], ["leave"])

    def test_a_locale_change_writes_the_affect_tooltips_again(self):
        legacy, novaui = self.worlds()
        self.form(legacy, novaui)
        Board = novaui.module("uiParty").PartyMemberInfoBoard
        with novaui:
            Board.AFFECT_STRING_DICT[0] = lambda value: "Bonus %d" % value
            novaui.module("nui_party")._on_locale_reload()
        self.assertEqual(novaui.window.board.model["members"][0]["affect_tips"][0], "Bonus 5")

    def test_destroy_takes_the_boards_and_the_document(self):
        legacy, novaui = self.worlds()
        self.form(legacy, novaui)
        with novaui:
            board = novaui.window.board
            novaui.window.DestroyPartyMemberInfoBoard()
            self.assertEqual(board.model["members"], [])
            novaui.window.Destroy()
            self.assertEqual(board.calls[-1], ("destroy",))
            novaui.window.AddPartyMember(1, "x")


# --- the edge buttons: differential through the Interface ------------------------------------

KEPT_REAL = {"sys", "nui_windows", "systemSetting", "dbg", "ui", "uiWhisper", "wndMgr", "app", "localeInfo", "event", "chat",
             "item", "player", "constInfo", "uiScriptLocale"}


class WhisperDialog(object):
    """uiWhisper.WhisperDialog, doing nothing."""

    def __init__(self, *args):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *args: None


class Party(object):
    shown = False

    def IsShow(self):
        return Party.shown


class EdgeWorlds(unittest.TestCase):
    def world(self, nui_on):
        world = HudWorld(nui_on)
        game = world.game
        source = read(os.path.join(ROOT, "interfacemodule.py"))
        names = set()
        for node in ast.parse(source).body:
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
        for name in names - KEPT_REAL:
            game.put(name, mock.MagicMock(name=name))
        world.module("uiWhisper").WhisperDialog = WhisperDialog
        with quiet():
            module = game.load("interfaceModule", "interfacemodule.py")
        interface = object.__new__(module.Interface)
        interface.questButtonList = []
        interface.whisperButtonList = []
        interface.questButtonSuppressed = False
        interface.whisperDialogDict = {}
        interface.listGMName = {}
        interface.windowOpenPosition = 0
        interface.dlgWhisperWithoutTarget = None
        interface.wndParty = Party()
        Party.shown = False
        world.interface = interface
        return world

    def worlds(self):
        legacy, novaui = self.world(False), self.world(True)
        return legacy, novaui

    def both(self, legacy, novaui, steps):
        for world in (legacy, novaui):
            with world, quiet():
                steps(world, world.interface)
                gc.collect()

    @staticmethod
    def legacy_view(world):
        def entry(button):
            label = button.ToolTipText
            return {"label": label.text if label else "", "align": label.align if label else None,
                    "gm": bool(label) and label.color == 0xffffa200, "flashing": button.flashing,
                    "shown": bool(button.shown), "up": button.visuals["up"]}
        interface = world.interface
        return {"quests": [entry(b) for b in interface.questButtonList],
                "whispers": [entry(b) for b in interface.whisperButtonList]}

    @staticmethod
    def novaui_view(world):
        board = world.module("nui_edge_buttons")._board
        if board is None or not board._doc:
            return {"quests": [], "whispers": []}

        def entry(e):
            return {"label": plain(e["label"]), "align": e["align"], "gm": e["gm"], "flashing": e["flashing"],
                    "shown": e["shown"], "up": e["up"].lstrip("/")}
        return {"quests": [entry(e) for e in board.get("quests")], "whispers": [entry(e) for e in board.get("whispers")]}

    def same_view(self, legacy, novaui):
        expected = self.legacy_view(legacy)
        self.assertEqual(self.novaui_view(novaui), expected)
        return expected

    @staticmethod
    def click(world, side, label):
        """A left click on the button labelled so: the legacy button's event,
        the board's press."""
        if world.nui_on:
            board = world.module("nui_edge_buttons")._board
            for e in board.get("quests" if side == "quest" else "whispers"):
                if plain(e["label"]) == label:
                    board.fire("press", side, e["id"], 0)
                    return
            raise AssertionError(label)
        buttons = world.interface.questButtonList if side == "quest" else world.interface.whisperButtonList
        for button in buttons:
            if button.ToolTipText.text == label:
                button.Click()
                return
        raise AssertionError(label)


class EdgeDifferential(EdgeWorlds):
    def test_quest_letters_stack_flash_and_start_their_quest(self):
        legacy, novaui = self.worlds()
        with novaui:
            self.assertEqual(type(novaui.module("uiWhisper").WhisperButton()).__module__, "nui_edge_buttons")
        with legacy:
            self.assertEqual(type(legacy.module("uiWhisper").WhisperButton()).__module__, "uiWhisper")

        def steps(world, interface):
            interface.RecvQuest(1, "The Wolf Hunt")
            interface.BINARY_RecvQuest(2, "Item quest", "item", "27001")
            interface.BINARY_RecvQuest(3, "Highlight", "highlight", "")
            interface.RecvQuest(1, "The Wolf Hunt, again")
        self.both(legacy, novaui, steps)
        view = self.same_view(legacy, novaui)
        self.assertEqual([e["label"] for e in view["quests"]], ["The Wolf Hunt, again", "Highlight", "Item quest"],
                         "the newest on top; a letter sent again replaces its button")
        self.assertEqual([e["flashing"] for e in view["quests"]], [True, False, True], "a highlighted letter does not flash")
        self.assertEqual(view["quests"][2]["up"], "season1/icon/scroll_close.tga",
                         "legacy reads an item letter's icon but shows the letter art (BINARY_RecvQuest, MR-7)")
        self.assertEqual(view["quests"][0]["align"], "left")
        Party.shown = True
        self.both(legacy, novaui, lambda world, interface: interface._Interface__ArrangeQuestButton())
        self.same_view(legacy, novaui)
        self.assertTrue(novaui.module("nui_edge_buttons")._board.get("quest_shift"), "the party shows: the letters move right")
        self.assertEqual([button.position[0] for button in legacy.interface.questButtonList], [130, 130, 130])
        self.both(legacy, novaui, lambda world, interface: interface.HideAllQuestButton())
        self.assertEqual([e["shown"] for e in self.same_view(legacy, novaui)["quests"]], [False] * 3)
        self.both(legacy, novaui, lambda world, interface: interface.ShowAllQuestButton())
        self.both(legacy, novaui, lambda world, interface: self.click(world, "quest", "Item quest"))
        self.assertEqual([e["label"] for e in self.same_view(legacy, novaui)["quests"]], ["The Wolf Hunt, again", "Highlight"])
        self.assertEqual(novaui.game.calls("event."), legacy.game.calls("event."))
        self.assertEqual(novaui.game.calls("event."), [("event.QuestButtonClick", (2,))])
        self.both(legacy, novaui, lambda world, interface: interface.BINARY_ClearQuest(1))
        self.assertEqual([e["label"] for e in self.same_view(legacy, novaui)["quests"]], ["Highlight"])

    def test_whispers_stack_flash_again_show_game_masters_and_open_their_dialog(self):
        legacy, novaui = self.worlds()

        def steps(world, interface):
            interface.RegisterGameMasterName("GameMaster")
            interface.RecvWhisper("NuiW2B2")
            interface.RecvWhisper("GameMaster")
            interface.RecvWhisper("NuiW2X1")
            interface.RecvWhisper("NuiW2B2")
            interface.MakeWhisperButton("Quiet")
        self.both(legacy, novaui, steps)
        view = self.same_view(legacy, novaui)
        self.assertEqual([e["label"] for e in view["whispers"]], ["Quiet", "NuiW2X1", "GameMaster", "NuiW2B2"])
        self.assertEqual([e["gm"] for e in view["whispers"]], [False, False, True, False])
        self.assertEqual([e["flashing"] for e in view["whispers"]], [False, True, True, True])
        self.assertEqual([args for name, args in novaui.game.calls("chat.")], [args for name, args in legacy.game.calls("chat.")])
        self.both(legacy, novaui, lambda world, interface: self.click(world, "whisper", "GameMaster"))
        view = self.same_view(legacy, novaui)
        self.assertEqual([e["label"] for e in view["whispers"]], ["Quiet", "NuiW2X1", "NuiW2B2"])
        self.assertIn("GameMaster", legacy.interface.whisperDialogDict)
        self.assertIn("GameMaster", novaui.interface.whisperDialogDict)
        self.both(legacy, novaui, lambda world, interface: (interface.HideAllWhisperButton(), interface.ShowAllWhisperButton()))
        self.same_view(legacy, novaui)

    def test_many_buttons_wrap_into_columns_in_the_legacy_order(self):
        legacy, novaui = self.worlds()

        def steps(world, interface):
            for n in range(12):
                interface.RecvWhisper("Name%d" % n)
            for n in range(11):
                interface.RecvQuest(n, "Quest %d" % n)
        self.both(legacy, novaui, steps)
        view = self.same_view(legacy, novaui)
        self.assertEqual(len(view["whispers"]), 12)
        columns = sorted(set(button.position[0] for button in legacy.interface.whisperButtonList))
        self.assertEqual(columns, [1480, 1530], "two legacy columns of nine rows at 900 lines")
        places = [(f._place, f._side) for f in novaui.module("nui_edge_buttons")._entries.values()]
        self.assertEqual(sorted(p for p, side in places if side == "whisper"), list(range(12)))

    def test_close_all_takes_every_button_and_the_document(self):
        legacy, novaui = self.worlds()
        self.both(legacy, novaui, lambda world, interface: (interface.RecvWhisper("A"), interface.RecvQuest(1, "Q")))
        module = novaui.module("nui_edge_buttons")
        board = module._board
        kept = list(novaui.interface.whisperButtonList)
        with novaui:
            module.close_all()
        self.assertEqual(board.calls[-1], ("destroy",))
        self.assertIsNone(module._board)
        self.assertFalse(kept[0].IsShow())
        kept[0].nui_press()  # its event went with the document
        with novaui:
            fresh = module.EdgeButton()
            self.assertTrue(fresh.nui_ready(), "a new Interface makes the document again")

    def test_a_button_the_interface_drops_leaves_the_document(self):
        world = self.world(True)
        module = world.module("nui_edge_buttons")
        with world:
            button = world.module("uiWhisper").WhisperButton()
            button.SetUpVisual("d:/ymir work/ui/game/windows/btn_mail_up.sub")
            button.SetToolTipText("Gone")
            button.Show()
            button.SetPosition(1530, 255)
            button.SetEvent(lambda b: None, button)
            self.assertEqual(len(module._board.get("whispers")), 1)
            button.SetEvent(0)
            del button
            gc.collect()
            self.assertEqual(module._board.get("whispers"), [])


# --- the notice boards and the map name: legacy per frame against the NovaUI timers ----------

FPS = 60


def run_clock(world, board, seconds, events=(), samples=(), view=None, tick="OnUpdate"):
    """Runs one world's board for `seconds` at 60 frames a second: the legacy
    board's per-frame OnUpdate (or Update) while it shows, or the NovaUI
    countdown's countdownend once the clock passes its end. `events` are
    (time, function) pairs; `samples` the times `view(world, board)` is read
    at. Answers {time: view}."""
    seen = {}
    events = sorted(events, key=lambda event: event[0])
    pending = list(events)
    wanted = sorted(samples)
    for frame in range(int(seconds * FPS) + 1):
        now = frame / float(FPS)
        world.game.time = now
        world.game.state.now = now
        while pending and pending[0][0] <= now + 1e-9:
            pending.pop(0)[1](board)
        if world.nui_on:
            model = board.board.model if board.board is not None else {}
            end = model.get("next_at", model.get("hide_at", 0.0))
            if board.IsShow() and end > 0 and now >= end - 1e-9:
                board.board.fire("advance" if "next_at" in model else "done")
        elif board.IsShow():
            getattr(board, tick)()
        while wanted and wanted[0] <= now + 1e-9:
            seen[wanted.pop(0)] = view(world, board)
    return seen


def tip_view(step):
    def view(world, board):
        if not board.IsShow():
            return "hidden"
        if world.nui_on:
            return board.lines[board.front] or None
        if board.curPos != board.dstPos or board.curPos < 0 or board.curPos % step:
            return None
        index = board.curPos // step
        return board.tipList[index][1] if index < len(board.tipList) else None
    return view


class NoticeDifferential(unittest.TestCase):
    def boards(self, kind):
        legacy, novaui = pair()
        for world in (legacy, novaui):
            with world:
                if kind == "tip":
                    world.board = world.make("tip-board", world.module("uiTip").TipBoard, "nui_tip_board.TipBoard")
                else:
                    world.board = world.make("big-board", world.module("uiTip").BigBoard, "nui_big_board.BigBoard")
                world.board.Hide()
        return legacy, novaui

    def compare(self, kind, step, seconds, events, samples):
        legacy, novaui = self.boards(kind)
        results = []
        for world in (legacy, novaui):
            with world, quiet():
                results.append(run_clock(world, world.board, seconds, events, samples, tip_view(step)))
        self.assertEqual(results[1], results[0])
        return results[0], novaui

    def test_the_tip_board_shows_each_tip_three_seconds_and_hides_after_the_wrap(self):
        events = [(0.0, lambda b: b.SetTip("first")), (0.5, lambda b: b.SetTip("second"))]
        samples = [0.2, 1.0, 2.5, 4.0, 5.5, 7.0, 8.5, 10.0, 11.0]
        seen, novaui = self.compare("tip", 17, 12, events, samples)
        self.assertEqual(seen, {0.2: None, 1.0: None, 2.5: "first", 4.0: "first", 5.5: "second", 7.0: "second",
                                8.5: None, 10.0: None, 11.0: "hidden"})

    def test_a_tip_that_comes_after_the_last_one_went_shows_at_once_and_a_young_one_survives_the_wrap(self):
        events = [(0.0, lambda b: b.SetTip("first")), (5.0, lambda b: b.SetTip("late"))]
        samples = [2.0, 4.5, 5.2, 6.5, 9.5, 12.5, 15.5, 17.0, 18.5]
        seen, novaui = self.compare("tip", 17, 19, events, samples)
        self.assertEqual(seen[4.5], None, "the first went out")
        self.assertEqual(seen[5.2], "late", "the new tip is in the line already in view")
        self.assertEqual(seen[12.5], "late", "the wrap kept the young tip and starts again from it")
        self.assertEqual(seen[18.5], "hidden", "the next wrap drops it")

    def test_no_tip_shows_while_notices_are_off(self):
        legacy, novaui = self.boards("tip")
        for world in (legacy, novaui):
            world.game.visible_notice = False
            with world:
                world.board.SetTip("x")
                self.assertFalse(world.board.IsShow())

    def test_the_big_board_shows_a_batch_once_and_hides(self):
        events = [(0.0, lambda b: b.SetTip("Big notice"))]
        samples = [0.5, 2.0, 5.5, 7.0]
        seen, novaui = self.compare("big", 46, 8, events, samples)
        self.assertEqual(seen, {0.5: None, 2.0: "Big notice", 5.5: "Big notice", 7.0: "hidden"})

    def test_the_boards_step_on_their_countdown_and_run_no_python_in_between(self):
        legacy, novaui = self.boards("tip")
        with novaui:
            novaui.board.SetTip("first")
            model = novaui.board.board.model
            self.assertEqual(model["next_at"], 1.0, "the first step a second after the tip")
            self.assertEqual((model["shown"], model["front"]), (True, "a"))
            novaui.game.state.now = 1.0
            novaui.board.board.fire("advance")
            self.assertEqual((model["line_b"], model["front"], model["next_at"]), ("first", "b", 4.0))
            novaui.board.Hide()
            self.assertEqual(model["next_at"], 0.0, "a hidden board has no timer")
            board = novaui.board.board
            novaui.board.Destroy()
            self.assertEqual(board.calls[-1], ("destroy",))


def map_view(world, shower):
    if not shower.IsShow():
        return "hidden"
    if world.nui_on:
        return "shown" if map_opacity(world.game.state.now - shower.shown_at) > 0.05 else "faint"
    return "shown" if shower.curAlpha > 0.05 else "faint"


def map_opacity(t):
    """The splash's keyframes (map-name.rcss), 6.65 s long."""
    points = [(0.0, 0.0), (1.0, 0.0), (1.3, 0.9), (6.3, 0.9), (6.6, 0.0), (6.65, 0.0)]
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if t0 <= t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return 0.9


class MapNameDifferential(unittest.TestCase):
    def showers(self, setup=None):
        legacy, novaui = pair(setup)
        for world in (legacy, novaui):
            with world:
                world.shower = world.make("map-name", world.module("uiMapNameShower").MapNameShower, "nui_map_name.MapNameShower")
        self.assertEqual(type(novaui.shower).__module__, "nui_map_name")
        return legacy, novaui

    def test_the_splash_waits_fades_in_holds_and_fades_out_as_legacy_does(self):
        legacy, novaui = self.showers()
        samples = [0.5, 1.15, 3.0, 6.0, 6.45, 7.0]
        results = []
        for world in (legacy, novaui):
            def show(shower, world=world):
                shower.ShowMapName("metin2_map_a1", 0, 0)
                shower.shown_at = world.game.state.now
            with world, quiet():
                results.append(run_clock(world, world.shower, 8, [(0.0, show)], samples, map_view, tick="Update"))
        self.assertEqual(results[1], results[0])
        self.assertEqual(results[0], {0.5: "faint", 1.15: "shown", 3.0: "shown", 6.0: "shown", 6.45: "shown", 7.0: "hidden"})
        self.assertEqual(legacy.shower.image, "locale/en/ui/mapname/a1.tga")
        self.assertEqual(novaui.shower.board.get("image"), "/locale/en/ui/mapname/a1.tga")

    def test_each_show_restarts_the_animation_and_the_floors_follow_legacy(self):
        legacy, novaui = self.showers(lambda game: game.missing_files.add("locale/en/ui/mapname/devil1_0f.tga"))
        with novaui, quiet():
            shower = novaui.shower
            shower.ShowMapName("metin2_map_a1", 0, 0)
            first = shower.board.get("run")
            shower.ShowMapName("metin2_map_a1", 0, 0)
            self.assertNotEqual(shower.board.get("run"), first, "the body switches its animation class")
            self.assertEqual(shower.board.get("hide_at"), 6.6)
            shower.ShowMapName("metin2_map_deviltower1", 12000, 60000)
            self.assertEqual((shower.board.get("offset"), shower.board.get("floor_image")),
                             ("tower", "/locale/en/ui/mapname/devil1_1f.tga"))
            shower.ShowMapName("metin2_map_devilsCatacomb", 4000, 5000)
            self.assertEqual((shower.board.get("offset"), shower.board.get("floor_image")),
                             ("catacomb", "/locale/en/ui/mapname/devil1_1f.tga"))
            shower.ShowMapName("metin2_map_deviltower1", 0, 0)
            self.assertEqual((shower.board.get("offset"), shower.board.get("floor_image")), ("none", ""),
                             "no floor there: devil1_0f.tga does not exist, so the name stays centered")
        with legacy, quiet():
            legacy.shower.ShowMapName("metin2_map_deviltower1", 12000, 60000)
            self.assertEqual(legacy.shower.floorImage.image, "locale/en/ui/mapname/devil1_1f.tga")
            self.assertEqual(legacy.shower.position, (-60, 80))

    def test_an_unknown_map_or_missing_art_shows_nothing(self):
        def setup(game):
            game.missing_files.update({"locale/en/ui/mapname/devil1_0f.tga", "locale/en/ui/mapname/snow2.tga"})
        legacy, novaui = self.showers(setup)
        with novaui, quiet():
            novaui.shower.ShowMapName("no_such_map", 0, 0)
            novaui.shower.ShowMapName("season2/map_n_snowm_02", 0, 0)
            self.assertFalse(novaui.shower.IsShow())
            novaui.shower.ShowMapName("metin2_map_a1", 0, 0)
            self.assertTrue(novaui.shower.IsShow())
            novaui.shower.board.fire("done")
            self.assertFalse(novaui.shower.IsShow())
            board = novaui.shower.board
            novaui.shower.Destroy()
            self.assertEqual(board.calls[-1], ("destroy",))
        with legacy, quiet():
            legacy.shower.ShowMapName("no_such_map", 0, 0)
            self.assertFalse(legacy.shower.IsShow())
