"""Stand-ins for the NovaUI HUD tests (nui_slots_test.py, nui_hud_core_test.py,
nui_hud_test.py): plain CPython, no client.

A Game holds the state of one stand-in client and the modules over it:

- `player`, `item`, `skill`, `guild` and `grpImage` answer from the state
  (Game.status, .items, .skills, .quick, .page, ...) and record every call;
- `net`, `chr`, `chrmgr`, `nonplayer`, `messenger`, `textTail` and `nuigame`
  record every call and answer 0 (a test sets an answer with Game.answer());
- `app` has a settable clock (Game.time, .global_time) and
  GetGlobalTimeStamp, `wndMgr` the screen size, the mouse and IsDragging;
- `localeInfo` and `uiScriptLocale` follow nui_test_support.LocaleInfo (an
  unknown name is its own name), with the SA entries the HUD reads as
  functions; `constInfo` is the real assets/root/constinfo.py;
- `mouseModule` is the real assets/root/mousemodule.py, its controller of a
  subclass that records each attach and detach (Game.attaches);
- `uiToolTip` has item and skill tooltips that record what they show;
- `ui` is nui_test_support's legacy ui stand-in, extended with the widgets
  the legacy HUD classes make: slot windows that keep which cells hold
  something, buttons that keep their event, tooltip and art, image boxes,
  text lines and number lines; ScriptWindow.GetChild raises KeyError for
  the names a legacy uiscript does not have (MISSING_CHILDREN);
- `nui` is nui_test_support's stand-in (Game.state).

Game.load(name) imports a module from assets/root over them. Game.log holds
every recorded call as (module.function, args) in order; Game.effects()
leaves out the getters (Get*, Is*, Has*, Can*, the quick slot index
conversions), as the differential tests compare them. HUD CONTENT extends
this in its own test file, not here."""
import contextlib
import io
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_test_support as support  # noqa: E402

ROOT = support.ROOT

GETTER_PREFIXES = ("Get", "Is", "Has", "Can", "LocalQuickSlotIndexTo", "Find")
# Modules whose calls the differential tests compare.
COMPARED = ("player", "net", "mouse", "app")

# Per legacy uiscript, the names it does not hold: GetChild raises KeyError
# for them, as ScriptWindow.GetChild does (taskbar.py has ExpandButton, not
# ChatButton; the left mouse button window has no button_skill, the right one
# no button_auto_attack, and neither a button_move or button_attack).
MISSING_CHILDREN = {
    "uiscript/taskbar.py": {"ChatButton"},
    "uiscript/mousebuttonwindow.py": {"button_skill", "button_move", "button_attack"},
    "uiscript/rightmousebuttonwindow.py": {"button_auto_attack", "button_move", "button_attack"},
}

PLAYER_CONSTANTS = {
    "SLOT_TYPE_NONE": 0, "SLOT_TYPE_INVENTORY": 1, "SLOT_TYPE_SKILL": 2, "SLOT_TYPE_EMOTION": 3,
    "SLOT_TYPE_SHOP": 4, "SLOT_TYPE_EXCHANGE_OWNER": 5, "SLOT_TYPE_EXCHANGE_TARGET": 6,
    "SLOT_TYPE_QUICK_SLOT": 7, "SLOT_TYPE_SAFEBOX": 8, "SLOT_TYPE_PRIVATE_SHOP": 9, "SLOT_TYPE_MALL": 10,
    "SLOT_TYPE_DRAGON_SOUL_INVENTORY": 11,
    "RESERVED_WINDOW": 0, "INVENTORY": 1, "EQUIPMENT": 2, "SAFEBOX": 3, "MALL": 4, "DRAGON_SOUL_INVENTORY": 5,
    "MBT_RIGHT": 0, "MBT_LEFT": 1, "MBT_MIDDLE": 2,
    "MBF_SMART": 0, "MBF_MOVE": 1, "MBF_CAMERA": 2, "MBF_ATTACK": 3, "MBF_SKILL": 4, "MBF_AUTO": 5,
    "MBS_CLICK": 0, "MBS_PRESS": 1,
    "LEVEL": 1, "EXP": 3, "NEXT_EXP": 4, "HP": 5, "MAX_HP": 6, "SP": 7, "MAX_SP": 8, "STAMINA": 9,
    "MAX_STAMINA": 10, "STAT": 28, "SKILL_ACTIVE": 29, "HP_RECOVERY": 32, "SP_RECOVERY": 33,
    "ENERGY": 128, "ENERGY_END_TIME": 129,
    "METIN_SOCKET_MAX_NUM": 3, "ITEM_MONEY": -1, "QUICKSLOT_PER_PAGE": 8, "QUICKSLOT_PAGES": 4,
}
SKILL_CONSTANTS = {"SKILL_TYPE_NONE": 0, "SKILL_TYPE_ACTIVE": 1, "SKILL_TYPE_SUPPORT": 2, "SKILL_TYPE_GUILD": 5}
WNDMGR_CONSTANTS = {"SLOT_STYLE_NONE": 0, "SLOT_STYLE_PICK_UP": 1, "SLOT_STYLE_SELECT": 2,
                    "HORIZONTAL_ALIGN_LEFT": 0, "HORIZONTAL_ALIGN_CENTER": 1, "HORIZONTAL_ALIGN_RIGHT": 2,
                    "VERTICAL_ALIGN_TOP": 0, "VERTICAL_ALIGN_CENTER": 1, "VERTICAL_ALIGN_BOTTOM": 2}
APP_CONSTANTS = {name: index for index, name in enumerate((
    "NORMAL", "ATTACK", "TARGET", "TALK", "CANT_GO", "PICK", "DOOR", "CHAIR", "MAGIC", "BUY", "SELL",
    "CAMERA_ROTATE", "HSIZE", "VSIZE", "HVSIZE"))}
APP_CONSTANTS.update({"ENABLE_ENERGY_SYSTEM": 1, "ENABLE_DRAGON_SOUL_SYSTEM": 1})


def is_getter(name):
    """Whether a recorded "module.Function" is a getter the differential tests
    leave out."""
    function = name.rsplit(".", 1)[-1]
    return function.startswith(GETTER_PREFIXES)


class Recording(types.ModuleType):
    """A module that records every call of a function it does not define as
    (module.name, args) in `log` and answers `answers.get(name, 0)` (a
    callable answer is called with the arguments)."""

    def __init__(self, name, log, **members):
        types.ModuleType.__init__(self, name)
        self.__dict__["_log"] = log
        self.__dict__["_answers"] = {}
        for key, value in members.items():
            setattr(self, key, value)

    def __getattr__(self, attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        log, answers, name = self.__dict__["_log"], self.__dict__["_answers"], self.__name__

        def record(*args):
            log.append((name + "." + attr, args))
            answer = answers.get(attr, 0)
            return answer(*args) if callable(answer) else answer
        record.__name__ = attr
        return record


def recorded(log, name, fn):
    """fn, recording (name, args) first."""
    def call(*args):
        log.append((name, args))
        return fn(*args)
    call.__name__ = name.rsplit(".", 1)[-1]
    return call


# --- the legacy ui stand-in, extended for the HUD classes ---------------------------

class LegacyWidget(support.Widget):
    """A legacy child window: records every call it does not define; keeps
    its shown state, event, tooltip text, button art, image and text."""

    def __init__(self, name=""):
        support.Widget.__init__(self, name)
        self.shown = False
        self.tooltip = None
        self.tooltip_color = None
        self.visuals = {"up": "", "over": "", "down": ""}
        self.image = ""
        self.ToolTipText = 0

    def SetToolTipText(self, text, x=0, y=0):
        self.calls.append(("SetToolTipText", text, x, y))
        self.tooltip = text

    def SetUpVisual(self, path):
        self.visuals["up"] = path

    def SetOverVisual(self, path):
        self.visuals["over"] = path

    def SetDownVisual(self, path):
        self.visuals["down"] = path

    def GetUpVisualFileName(self):
        return self.visuals["up"] or "%s_01.sub" % self.name

    def GetOverVisualFileName(self):
        return self.visuals["over"] or "%s_02.sub" % self.name

    def GetDownVisualFileName(self):
        return self.visuals["down"] or "%s_03.sub" % self.name

    def LoadImage(self, path):
        self.calls.append(("LoadImage", path))
        self.image = path

    def SetParent(self, parent):
        pass

    def SetTop(self):
        self.calls.append(("SetTop",))

    def IsIn(self):
        return False

    def GetGlobalPosition(self):
        return (0, 0)

    def GetLocalPosition(self):
        return (0, 0)


class LegacySlots(LegacyWidget):
    """A legacy slot window: keeps which cells hold something (CSlotWindow's
    isItem), their count, cover, cooldown and active state, and its events."""

    def __init__(self, name=""):
        LegacyWidget.__init__(self, name)
        self.cells = {}
        self.events = {}

    def _cell(self, index):
        return self.cells.setdefault(index, {"item": False, "count": "", "cover": False, "cool": None, "active": False})

    def ClearSlot(self, index):
        self.cells[index] = {"item": False, "count": "", "cover": False, "cool": None, "active": False}

    def SetItemSlot(self, index, vnum, count=0, color=None):
        if not vnum:
            self.ClearSlot(index)
            return
        cell = self._cell(index)
        cell.update({"item": True, "vnum": vnum, "count": str(count) if count > 1 else ""})

    def SetSkillSlotNew(self, index, skill_index, grade, level):
        self._cell(index).update({"item": True, "skill": skill_index})

    def SetEmotionSlot(self, index, emotion):
        self._cell(index).update({"item": True, "emotion": emotion})

    def SetSlotCountNew(self, index, grade, level):
        import nui_slots
        self._cell(index)["count"] = nui_slots.count_label(grade, level)

    def SetSlotCount(self, index, count):
        self._cell(index)["count"] = str(count) if count > 1 else ""

    def SetCoverButton(self, index, *args):
        self._cell(index)["cover"] = True

    def SetSlotCoolTime(self, index, cool_time, elapsed=0.0):
        self._cell(index)["cool"] = (cool_time, elapsed) if cool_time else None

    def ActivateSlot(self, index):
        self._cell(index)["active"] = True

    def DeactivateSlot(self, index):
        self._cell(index)["active"] = False

    def RefreshSlot(self):
        pass

    def is_item(self, index):
        return self._cell(index)["item"]

    def __setevent(name):
        def set_event(self, event):
            self.events[name] = event
        return set_event

    SetSelectEmptySlotEvent = __setevent("select_empty")
    SetSelectItemSlotEvent = __setevent("select_item")
    SetUnselectEmptySlotEvent = __setevent("unselect_empty")
    SetUnselectItemSlotEvent = __setevent("unselect_item")
    SetOverInItemEvent = __setevent("over_in")
    SetOverOutItemEvent = __setevent("over_out")
    SetUseSlotEvent = __setevent("use")
    del __setevent


def make_legacy_ui(log):
    """nui_test_support's legacy ui, extended for the HUD classes."""
    ui = support.make_legacy_ui()
    Window = ui.Window

    class HudWindow(Window):
        def __init__(self, layer="UI"):
            Window.__init__(self, layer)
            self.size = (0, 0)
            self.position = (0, 0)
            self.name = ""

        def SetSize(self, width, height):
            self.size = (width, height)

        def SetPosition(self, x, y):
            self.position = (x, y)

        def GetLocalPosition(self):
            return self.position

        def GetGlobalPosition(self):
            return self.position

        def SetWindowName(self, name):
            self.name = name

        def AddFlag(self, flag):
            pass

        def GetWidth(self):
            return self.size[0]

        def GetHeight(self):
            return self.size[1]

    class ScriptWindow(HudWindow):
        def __init__(self, layer="UI"):
            HudWindow.__init__(self, layer)
            self.ElementDictionary = {}
            self.Children = []
            self.scripts = []

        def ClearDictionary(self):
            self.Children = []
            self.ElementDictionary = {}

        def GetChild(self, name):
            for script in getattr(self, "scripts", ()):
                if name in MISSING_CHILDREN.get(script.lower(), ()):
                    raise KeyError(name)
            if not hasattr(self, "ElementDictionary"):
                self.ElementDictionary = {}
            child = self.ElementDictionary.get(name)
            if child is None:
                child = self.ElementDictionary[name] = (LegacySlots if name.startswith("quick_slot") else LegacyWidget)(name)
            return child

        def GetChild2(self, name):
            return self.GetChild(name)

    class PythonScriptLoader(object):
        loaded = []

        def LoadScriptFile(self, window, path):
            """As the legacy loader: it clears the window's dictionary first
            (a class that skips ScriptWindow.__init__ still gets one)."""
            PythonScriptLoader.loaded.append(path)
            clear = getattr(window, "ClearDictionary", None)
            if clear is not None:
                clear()
            if not hasattr(window, "scripts"):
                window.scripts = []
            window.scripts.append(path)

    class TextLine(LegacyWidget):
        def __init__(self, layer="UI"):
            LegacyWidget.__init__(self, "text")

    class ImageBox(LegacyWidget):
        def __init__(self, layer="UI"):
            LegacyWidget.__init__(self, "image")

    class NumberLine(LegacyWidget):
        def __init__(self, layer="UI"):
            LegacyWidget.__init__(self, "number")

        def SetNumber(self, text):
            self.text = text

    class Button(LegacyWidget):
        def __init__(self, layer="UI"):
            LegacyWidget.__init__(self, "button")
            ui.handles[0] += 1
            self.hWnd = ui.handles[0]
            self.layer = layer

        def __del__(self):
            pass

    class SlotWindow(LegacySlots):
        def __init__(self, layer="UI"):
            LegacySlots.__init__(self, "slots")
            ui.handles[0] += 1
            self.hWnd = ui.handles[0]
            self.size = (0, 0)
            self.position = (0, 0)

        def __del__(self):
            pass

        def SetSize(self, width, height):
            self.size = (width, height)

        def SetPosition(self, x, y):
            self.position = (x, y)

        def GetGlobalPosition(self):
            return self.position

        def GetLocalPosition(self):
            return self.position

        def Destroy(self):
            pass

    ui.HudWindow = HudWindow
    ui.Window = HudWindow
    ui.ScriptWindow = ScriptWindow
    ui.PythonScriptLoader = PythonScriptLoader
    ui.TextLine = TextLine
    ui.ImageBox = ImageBox
    ui.ExpandedImageBox = ImageBox
    ui.AniImageBox = ImageBox
    ui.NumberLine = NumberLine
    ui.Button = Button
    ui.SlotWindow = SlotWindow
    ui.GridSlotWindow = SlotWindow
    ui.Bar = HudWindow
    return ui


# --- tooltips ----------------------------------------------------------------------

class ToolTip(object):
    """A legacy tooltip that records what it was asked to show."""

    def __init__(self, kind):
        self.kind = kind
        self.shown = []     # every Set* call, in order
        self.visible = False

    def __getattr__(self, name):
        if name.startswith("__") or not name.startswith("Set"):
            raise AttributeError(name)

        def show(*args):
            self.shown.append((name,) + args)
            self.visible = True
        return show

    def HideToolTip(self):
        self.visible = False

    def ShowToolTip(self):
        self.visible = True

    def Hide(self):
        self.visible = False


def make_tooltips():
    module = types.ModuleType("uiToolTip")
    module.ItemToolTip = lambda *args: ToolTip("item")
    module.SkillToolTip = lambda *args: ToolTip("skill")
    module.HyperlinkItemToolTip = lambda *args: ToolTip("hyperlink")
    module.ToolTip = lambda *args: ToolTip("plain")
    module.TOOLTIP_TYPE = ToolTip
    return module


# --- the game --------------------------------------------------------------------------

class Game(object):
    """One stand-in client: its state, its modules, and the root modules
    loaded over them. `with game:` puts the modules into sys.modules (the
    legacy code imports some inside its functions); load() does it too."""

    def __init__(self, nui_on=True, engine=True):
        self.log = []
        self.attaches = []       # ("attach", type, slot, index, count) and ("detach", type)
        self.created = []        # icon instances made: (kind, handle)
        self.deleted = []        # icon instances freed: (kind, handle)
        self.time = 100.0        # app.GetTime(), seconds
        self.global_time = 100000  # app.GetGlobalTime(), milliseconds
        self.timestamp = 1700000000  # app.GetGlobalTimeStamp()
        self.files = {}          # path -> text, the files the legacy code reads and writes
        self.dragging = True     # wndMgr.IsDragging()
        self.status = {}         # player.GetStatus
        self.items = {}          # inventory position (or (window, position)) -> {"vnum", "count", "sockets"}
        self.item_sizes = {}     # vnum -> (w, h)
        self.quick_items = set()  # vnums item.CanAddToQuickSlotItem accepts (default: all but those in no_quick)
        self.no_quick = set()
        self.skills = {}         # skill slot -> {"index", "grade", "level", "cool", "active"}
        self.skill_types = {}    # skill index -> skill type
        self.toggle_skills = set()
        self.standing_skills = set()
        self.guild_levels = {}   # skill slot -> guild skill level
        self.quick = {}          # global quick slot -> (type, position)
        self.page = 0
        self.play_time = 1
        self.observer = False
        self.emotion_icons = {}  # emotion index -> icon path
        self.handles = [1000]
        self.state = support.NuiState()
        self.state.available = nui_on
        self.engine = engine
        self.dbg = support.make_dbg()
        self.modules = self._modules()
        self._saved = {}
        self.loaded = {}

    # --- state helpers --------------------------------------------------------------

    def give(self, position, vnum, count=1, sockets=(0, 0, 0), size=(1, 1)):
        self.items[position] = {"vnum": vnum, "count": count, "sockets": list(sockets)}
        self.item_sizes[vnum] = size

    def learn(self, slot, index, grade=0, level=1, skill_type=1, cool=None, active=False):
        self.skills[slot] = {"index": index, "grade": grade, "level": level, "cool": cool, "active": active}
        self.skill_types[index] = skill_type

    def put_quick(self, local, slot_type, position, page=None):
        self.quick[(self.page if page is None else page) * 8 + local] = (slot_type, position)

    def answer(self, module, name, value):
        self.modules[module].__dict__["_answers"][name] = value

    def effects(self, modules=COMPARED):
        """The recorded calls with an effect, in order: the getters left out,
        only the modules named."""
        return [(name, args) for name, args in self.log
                if name.split(".", 1)[0] in modules and not is_getter(name)]

    def calls(self, prefix):
        return [(name, args) for name, args in self.log if name.startswith(prefix)]

    def _handle(self, kind):
        self.handles[0] += 1
        self.created.append((kind, self.handles[0]))
        return self.handles[0]

    # --- modules ------------------------------------------------------------------------

    def _item_at(self, *at):
        key = at[0] if len(at) == 1 else tuple(at)
        return self.items.get(key, {"vnum": 0, "count": 0, "sockets": [0, 0, 0]})

    def _modules(self):
        log = self.log
        game = self
        modules = {}

        player = Recording("player", log, **PLAYER_CONSTANTS)
        define = lambda name, fn: setattr(player, name, recorded(log, "player." + name, fn))
        define("GetStatus", lambda kind: game.status.get(kind, 0))
        define("GetItemIndex", lambda *at: game._item_at(*at)["vnum"])
        define("GetItemCount", lambda *at: game._item_at(*at)["count"])
        define("GetItemMetinSocket", lambda *at: (game._item_at(*at[:-1])["sockets"] + [0, 0, 0])[at[-1]])
        define("GetSkillIndex", lambda slot: game.skills.get(slot, {}).get("index", 0))
        define("GetSkillGrade", lambda slot: game.skills.get(slot, {}).get("grade", 0))
        define("GetSkillLevel", lambda slot: game.skills.get(slot, {}).get("level", 0))
        define("IsSkillCoolTime", lambda slot: game.skills.get(slot, {}).get("cool") is not None)
        define("GetSkillCoolTime", lambda slot: game.skills.get(slot, {}).get("cool") or (0.0, 0.0))
        define("IsSkillActive", lambda slot: bool(game.skills.get(slot, {}).get("active")))
        define("GetQuickPage", lambda: game.page)
        define("GetLocalQuickSlot", lambda local: game.quick.get(game.page * 8 + local, (0, 0)))
        define("GetGlobalQuickSlot", lambda index: game.quick.get(index, (0, 0)))
        define("LocalQuickSlotIndexToGlobalQuickSlotIndex", lambda local: game.page * 8 + local)
        define("GetPlayTime", lambda: game.play_time)
        define("IsObserverMode", lambda: game.observer)
        define("GetEmotionIconFileName", lambda index: game.emotion_icons.get(index, ""))
        define("GetEmotionIconImage", lambda index: "emotion-image-%d" % index)

        def set_page(page):
            game.page = page + 4 if page < 0 else page % 4
        define("SetQuickPage", set_page)

        def set_play_time(value):
            game.play_time = value
        define("SetPlayTime", set_play_time)
        modules["player"] = player

        item = Recording("item", log)
        item.selected = [0]

        def select(vnum):
            item.selected[0] = vnum
        item.SelectItem = recorded(log, "item.SelectItem", select)
        item.GetIconImageFileName = recorded(log, "item.GetIconImageFileName",
            lambda: "icon/item/%05d.tga" % item.selected[0])
        item.GetItemSize = recorded(log, "item.GetItemSize", lambda: game.item_sizes.get(item.selected[0], (1, 1)))
        item.GetItemName = recorded(log, "item.GetItemName", lambda: "item %d" % item.selected[0])
        item.GetIconInstance = recorded(log, "item.GetIconInstance", lambda: game._handle("item"))
        item.DeleteIconInstance = recorded(log, "item.DeleteIconInstance", lambda handle: game.deleted.append(("item", handle)))
        item.CanAddToQuickSlotItem = recorded(log, "item.CanAddToQuickSlotItem",
            lambda vnum: vnum not in game.no_quick)
        modules["item"] = item

        skill = Recording("skill", log, **SKILL_CONSTANTS)
        skill.GetSkillType = recorded(log, "skill.GetSkillType", lambda index: game.skill_types.get(index, 1))
        skill.GetIconImageFileNameNew = recorded(log, "skill.GetIconImageFileNameNew",
            lambda index, grade: "d:/ymir work/ui/skill/test/%d_%02d.sub" % (index, min(max(grade, 0), 3) + 1) if index else "")
        skill.GetIconInstanceNew = recorded(log, "skill.GetIconInstanceNew", lambda index, grade: game._handle("skill"))
        skill.DeleteIconInstance = recorded(log, "skill.DeleteIconInstance", lambda handle: game.deleted.append(("skill", handle)))
        skill.IsToggleSkill = recorded(log, "skill.IsToggleSkill", lambda index: index in game.toggle_skills)
        skill.IsStandingSkill = recorded(log, "skill.IsStandingSkill", lambda index: index in game.standing_skills)
        modules["skill"] = skill

        guild = Recording("guild", log)
        guild.GetSkillLevel = recorded(log, "guild.GetSkillLevel", lambda slot: game.guild_levels.get(slot, 0))
        modules["guild"] = guild

        grp_image = Recording("grpImage", log)
        grp_image.Generate = lambda path: 1  # cursor images, not counted
        grp_image.GenerateFromHandle = recorded(log, "grpImage.GenerateFromHandle", lambda image: game._handle("emotion"))
        grp_image.Delete = recorded(log, "grpImage.Delete", lambda handle: game.deleted.append(("emotion", handle)))
        grp_image.GetWidth = lambda handle: 32
        grp_image.GetHeight = lambda handle: 32
        grp_image.SetDiffuseColor = lambda *args: None
        grp_image.SetPosition = lambda *args: None
        grp_image.Render = lambda *args: None
        modules["grpImage"] = grp_image

        app = Recording("app", log, **APP_CONSTANTS)
        app.GetTime = lambda: game.time
        app.GetGlobalTime = lambda: game.global_time
        app.GetGlobalTimeStamp = lambda: game.timestamp
        app.IsExistFile = lambda path: True
        app.IsRTL = lambda: False
        app.SetCursor = lambda *args: None
        app.IsShowCursor = lambda: True
        app.IsLiarCursorOn = lambda: False
        modules["app"] = app

        wndmgr = support.make_wndmgr()
        for key, value in WNDMGR_CONSTANTS.items():
            setattr(wndmgr, key, value)
        wndmgr.IsDragging = lambda: game.dragging
        wndmgr.AttachIcon = recorded(log, "wndMgr.AttachIcon", lambda *args: None)
        wndmgr.SetAttachingFlag = lambda flag: None
        wndmgr.IsAttaching = lambda: bool(game.modules["mouseModule"].mouseController.isAttached())
        for name in ("SetSlotBaseImage", "AppendSlot", "SetCoverButton", "SetSlotStyle", "Register", "Destroy",
                     "Show", "Hide", "SetTop", "SetWindowSize", "SetWindowPosition", "IsShow", "SetParent"):
            if not hasattr(wndmgr, name):
                setattr(wndmgr, name, lambda *args: 0)
        modules["wndMgr"] = wndmgr

        for name in ("net", "chr", "chrmgr", "nonplayer", "messenger", "textTail", "snd", "grp", "grpText",
                     "systemSetting", "background", "quest", "event", "chat", "ime", "exception"):
            modules[name] = Recording(name, log)
        modules["systemSetting"].IsSoftwareCursor = lambda: False
        modules["systemSetting"].GetUINuiWindows = lambda: "+hud"
        modules["systemSetting"].IsUINuiLogin = lambda: 0
        nuigame = Recording("nuigame", log)
        modules["nuigame"] = nuigame if self.engine else None

        modules["localeInfo"] = support.LocaleInfo(
            TOOLTIP_ENERGY=lambda value: "Energy %s" % (value,),
            RegisterReloadCallback=lambda fn: None)
        modules["uiScriptLocale"] = support.LocaleInfo(LOCALE_UISCRIPT_PATH="locale/en/ui/")
        modules["uiToolTip"] = make_tooltips()
        modules["dbg"] = self.dbg
        modules["ui"] = make_legacy_ui(log)
        nui = support.make_nui(self.state)
        if self.engine:
            nui._nui.BindFeed = lambda *args: True
        modules["nui"] = nui
        return modules

    # --- sys.modules ----------------------------------------------------------------

    def __enter__(self):
        for name, module in self.modules.items():
            self._saved.setdefault(name, sys.modules.get(name, support.MISSING))
            sys.modules[name] = module
        return self

    def __exit__(self, *exc):
        for name, value in self._saved.items():
            if value is support.MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
        self._saved = {}
        return False

    def put(self, name, module):
        self.modules[name] = module
        if self._saved:
            self._saved.setdefault(name, sys.modules.get(name, support.MISSING))
            sys.modules[name] = module

    def load(self, name, file_name=None):
        """Imports assets/root/<file_name> as `name` over the stand-ins (and
        keeps it in self.modules, so later loads import it)."""
        with self:
            path = os.path.join(ROOT, file_name or (name.lower() + ".py"))
            sys.modules.pop(name, None)
            with contextlib.redirect_stdout(io.StringIO()):
                module = support.load_module(name, path)
        self.modules[name] = module
        self.loaded[name] = module
        if name == "mouseModule":
            self._record_controller(module)
        if name in ("uiTaskBar", "nui_taskbar"):
            module.open = self._open
        return module

    def load_standard(self):
        """constInfo, mouseModule and the shared NovaUI modules, in that order."""
        self.load("constInfo", "constinfo.py")
        self.load("mouseModule", "mousemodule.py")
        self.load("nui_windows", "nui_windows.py")
        self.load("nui_slots", "nui_slots.py")
        self.load("nui_hud", "nui_hud.py")
        return self

    def _record_controller(self, module):
        game = self
        base = module.CMouseController

        class RecordingController(base):
            def AttachObject(self, owner, slot_type, slot_number, item_index, count=0):
                game.attaches.append(("attach", slot_type, slot_number, item_index, count))
                game.log.append(("mouse.AttachObject", (slot_type, slot_number, item_index, count)))
                return base.AttachObject(self, owner, slot_type, slot_number, item_index, count)

            def DeattachObject(self):
                if getattr(self, "AttachedFlag", False):
                    game.attaches.append(("detach", self.AttachedType))
                    game.log.append(("mouse.DeattachObject", ()))
                return base.DeattachObject(self)

        with self:
            controller = RecordingController()
            controller.Create()
        module.mouseController = controller

    def _open(self, path, mode="r"):
        """The legacy code's config files (config/mouse.cfg), in memory."""
        game = self

        class File(io.StringIO):
            def __exit__(self, *exc):
                if "w" in mode:
                    game.files[path] = self.getvalue()
                return io.StringIO.__exit__(self, *exc)

            def close(self):
                if "w" in mode:
                    game.files[path] = self.getvalue()
                io.StringIO.close(self)

        if "r" in mode and path not in self.files:
            raise IOError("stand-in: no %s" % path)
        return File(self.files.get(path, "") if "r" in mode else "")
