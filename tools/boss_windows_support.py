"""The world the boss info and damage count tests run in (NOVA-27): one
stand-in client (nui_game_support.Game) whose `ui` is a geometry-keeping
legacy ui (positions, sizes, parents, colors, texts, images, events, the
uiscript loader that builds a window's children from its uiscript), with
the game module functions the two windows read (nonplayer, chr, player,
app, systemSetting), localeInfo over the real English locale_game.txt plus
localeinfo.py's own formatting functions, and the legacy modules loaded:
uibossinfo.py and uidamagecount.py, and the NovaUI ones when asked.

Used by boss_windows_test.py (the legacy flows and wiring),
nui_boss_info_test.py and nui_damage_count_test.py (NovaUI against legacy)."""
import ast
import contextlib
import io
import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nui_game_support as gs  # noqa: E402

ROOT = gs.ROOT
ASSETS = os.path.normpath(os.path.join(ROOT, ".."))
LOCALES = os.path.join(ASSETS, "locale", "locale")
UISCRIPTS = os.path.join(ASSETS, "uiscript", "uiscript")
SCREEN = (1600, 900)

# A boss table: vnum -> (name, level), the client's mob_proto as
# nonplayer reads it.
MONSTERS = {
    997: ("Green Dragon", 120),
    998: ("Abomination", 120),
    999: ("Arachne", 120),
    2091: ("Queen Spider", 50),
    56007: ("Aquadragonis", 125),
    1093: ("Death Reaper of the Ancient Temple", 75),  # longer than 14 characters
}


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


def read_locale(path):
    """KEY<TAB>value lines of a locale file, as the client reads them."""
    values = {}
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle.read().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0]:
                values[parts[0]] = parts[1]
    return values


def locale_files():
    """Every locale folder's locale_game.txt and locale_interface.txt."""
    found = []
    for name in sorted(os.listdir(LOCALES)):
        folder = os.path.join(LOCALES, name)
        game = os.path.join(folder, "locale_game.txt")
        if os.path.isfile(game):
            found.append((name, game, os.path.join(folder, "locale_interface.txt")))
    return found


def _locale_functions():
    """localeinfo.py's NumberToString and RTSecondToDHMS, compiled from the
    file itself, over the English DAY/HOUR/MINUTE/SECOND strings."""
    with open(os.path.join(ROOT, "localeinfo.py"), encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    wanted = {"NumberToString", "RTSecondToDHMS"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    return nodes


def make_locale_info():
    values = read_locale(os.path.join(LOCALES, "en", "locale_game.txt"))
    module = types.ModuleType("localeInfo")
    module.__dict__.update(values)
    module.RegisterReloadCallback = lambda fn: None
    code = compile(ast.Module(body=_locale_functions(), type_ignores=[]), "localeinfo.py", "exec")
    exec(code, module.__dict__)
    return module


def make_tooltip_module(log):
    """uiToolTip.ToolTip: a board that records its title, lines, follow and
    shown state."""
    module = types.ModuleType("uiToolTip")

    class ToolTip(object):
        def __init__(self, width=0):
            self.title = ""
            self.lines = []
            self.follow = False
            self.shown = False
            self.centered = False

        def ClearToolTip(self):
            self.title = ""
            self.lines = []

        def SetTitle(self, text):
            self.title = text

        def AppendSpace(self, size):
            pass

        def AutoAppendTextLine(self, text, color=None, centerAlign=True):
            self.lines.append(text)

        def SetFollow(self, flag):
            self.follow = bool(flag)

        def AlignHorizonalCenter(self):
            self.centered = True

        def ShowToolTip(self):
            self.shown = True
            log.append(("tooltip.ShowToolTip", (self.title,)))

        def HideToolTip(self):
            self.shown = False

        def Show(self):
            self.shown = True

        def Hide(self):
            self.shown = False

        def IsShow(self):
            return self.shown

        def SetTop(self):
            pass

    module.ToolTip = ToolTip
    return module


def make_ui(log):
    """A legacy ui that keeps geometry (positions, sizes, parents), colors,
    texts, images, events and shown states, and a uiscript loader that
    builds a window's children from its uiscript file."""
    ui = types.ModuleType("ui")
    made = []

    class Window(object):
        def __init__(self, layer="UI"):
            self.layer = layer
            self.parent = None
            self.children = []
            self.position = (0, 0)
            self.size = (0, 0)
            self.shown = False
            self.flags = set()
            self.name = ""
            self.color = None
            self.text = ""
            self.font = ""
            self.image = ""
            self.event = None
            self.event_args = ()
            self.tooltip = None
            self.destroyed = False
            self.window_align = set()
            made.append(self)

        def __del__(self):
            pass

        def SetParent(self, parent):
            self.parent = parent
            if parent is not None and hasattr(parent, "children"):
                parent.children.append(self)

        def SetPosition(self, x, y):
            self.position = (int(x), int(y))

        def GetLocalPosition(self):
            return self.position

        def GetGlobalPosition(self):
            x, y = self.position
            if self.parent is not None:
                px, py = self.parent.GetGlobalPosition()
                return (x + px, y + py)
            return (x, y)

        def SetSize(self, width, height):
            self.size = (int(width), int(height))

        def GetWidth(self):
            return self.size[0]

        def GetHeight(self):
            return self.size[1]

        def Show(self):
            self.shown = True

        def Hide(self):
            self.shown = False

        def IsShow(self):
            return self.shown

        def AddFlag(self, flag):
            self.flags.add(flag)

        def SetTop(self):
            pass

        def SetWindowName(self, name):
            self.name = name

        def SetWindowHorizontalAlignCenter(self):
            self.window_align.add("hcenter")

        def SetWindowVerticalAlignCenter(self):
            self.window_align.add("vcenter")

        def Destroy(self):
            self.destroyed = True

        def visible(self):
            """Shown, and every parent shown."""
            window = self
            while window is not None:
                if not window.shown:
                    return False
                window = window.parent
            return True

    class ScriptWindow(Window):
        def __init__(self, layer="UI"):
            Window.__init__(self, layer)
            self.ElementDictionary = {}

        def GetChild(self, name):
            return self.ElementDictionary[name]

        def ClearDictionary(self):
            self.ElementDictionary = {}

    class Bar(Window):
        def SetColor(self, color):
            self.color = int(color) & 0xFFFFFFFF

    class TextLine(Window):
        def SetText(self, text):
            self.text = "" if text is None else str(text)

        def GetText(self):
            return self.text

        def SetFontName(self, name):
            self.font = name

        def SetPackedFontColor(self, color):
            self.color = int(color) & 0xFFFFFFFF

        def SetVerticalAlignCenter(self):
            pass

        def SetHorizontalAlignCenter(self):
            pass

        def SetHorizontalAlignLeft(self):
            pass

    class ImageBox(Window):
        scale = (1.0, 1.0)

        def SetScale(self, x, y):
            self.scale = (x, y)

        def LoadImage(self, path):
            self.image = path
            log.append(("ui.LoadImage", (path,)))

    class Button(Window):
        def __init__(self, layer="UI"):
            Window.__init__(self, layer)
            self.visuals = {}

        def SetUpVisual(self, path):
            self.visuals["up"] = path

        def SetOverVisual(self, path):
            self.visuals["over"] = path

        def SetDownVisual(self, path):
            self.visuals["down"] = path

        def SetToolTipText(self, text, x=0, y=-19):
            self.tooltip = text

        def SetText(self, text):
            self.text = "" if text is None else str(text)

        def SetEvent(self, event, *args):
            self.event = event
            self.event_args = args

        def SAFE_SetEvent(self, event, *args):
            self.SetEvent(event, *args)

        def click(self):
            if self.event is not None:
                self.event(*self.event_args)

    class ThinBoard(Window):
        pass

    class Gauge(Window):
        def __init__(self, layer="UI"):
            Window.__init__(self, layer)
            self.percent = (0, 0)
            self.gauge_color = ""

        def MakeGauge(self, width, color):
            self.gauge_color = color
            self.SetSize(width, 7)

        def SetPercentage(self, value, maximum):
            self.percent = (value, maximum)

    class ListBoxEx(Window):
        def __init__(self, layer="UI"):
            Window.__init__(self, layer)
            self.items = []

        def AppendItem(self, item):
            item.SetParent(self)
            self.items.append(item)

        def GetItem(self, index):
            return self.items[index]

        def RemoveAllItems(self):
            self.items = []

    class PythonScriptLoader(object):
        TYPES = {"thinboard": ThinBoard, "text": TextLine, "image": ImageBox, "expanded_image": ImageBox,
                 "button": Button, "listboxex": ListBoxEx, "gauge": Gauge, "bar": Bar, "window": Window}

        def LoadScriptFile(self, window, path):
            log.append(("ui.LoadScriptFile", (path,)))
            file_name = os.path.join(UISCRIPTS, os.path.basename(path).lower())
            scope = {"SCREEN_WIDTH": SCREEN[0], "SCREEN_HEIGHT": SCREEN[1]}
            with open(file_name, encoding="utf-8") as handle:
                exec(compile(handle.read(), file_name, "exec"), scope)
            value = scope["window"]
            window.ClearDictionary()
            window.SetPosition(value.get("x", 0), value.get("y", 0))
            window.SetSize(value.get("width", 0), value.get("height", 0))
            for flag in value.get("style", ()):
                window.AddFlag(flag)
            self._children(window, window, value.get("children", ()))

        def _children(self, root, parent, children):
            for value in children:
                widget = self.TYPES[value["type"]]()
                widget.SetParent(parent)
                widget.SetWindowName(value["name"])
                widget.SetPosition(value.get("x", 0), value.get("y", 0))
                if "width" in value:
                    widget.SetSize(value["width"], value.get("height", 0))
                if "text" in value:
                    widget.SetText(value["text"])
                if "image" in value:
                    widget.LoadImage(value["image"])
                if value["type"] == "button":
                    widget.SetUpVisual(value.get("default_image", ""))
                    widget.SetOverVisual(value.get("over_image", ""))
                    widget.SetDownVisual(value.get("down_image", ""))
                if value["type"] == "gauge":
                    widget.MakeGauge(value["width"], value["color"])
                widget.Show()
                root.ElementDictionary[value["name"]] = widget
                self._children(root, widget, value.get("children", ()))

    def make_button(parent, x, y, tooltip, path, up, over, down):
        button = Button()
        button.SetParent(parent)
        button.SetPosition(x, y)
        button.SetUpVisual(path + up)
        button.SetOverVisual(path + over)
        button.SetDownVisual(path + down)
        button.SetToolTipText(tooltip)
        button.Show()
        return button

    def generate_color(r, g, b):
        return (0xFF << 24) | (int(r) << 16) | (int(g) << 8) | int(b)

    ui.Window = Window
    ui.ScriptWindow = ScriptWindow
    ui.Bar = Bar
    ui.TextLine = TextLine
    ui.ImageBox = ImageBox
    ui.ExpandedImageBox = ImageBox
    ui.Button = Button
    ui.ThinBoard = ThinBoard
    ui.Gauge = Gauge
    ui.ListBoxEx = ListBoxEx
    ui.PythonScriptLoader = PythonScriptLoader
    ui.MakeButton = make_button
    ui.GenerateColor = generate_color
    ui.__mem_func__ = lambda fn: fn
    ui.made = made
    return ui


class World(object):
    """One client: legacy only (nui_on False) or with the NovaUI windows
    `windows` turned on."""

    def __init__(self, nui_on=False, windows="+boss-info,+damage-count", expanded=1, failing=()):
        self.game = gs.Game(engine=True)
        game = self.game
        self.nui_on = nui_on
        modules = game.modules
        log = game.log
        modules["systemSetting"].GetUINuiWindows = lambda: windows if nui_on else ""
        for document in failing:
            game.state.failing.add(document)
        # constInfo, mouseModule and the shared NovaUI modules over Game's
        # own ui (mouseModule's controller needs its NumberLine).
        game.load_standard()
        self.ui = make_ui(log)
        game.put("ui", self.ui)
        game.put("uiToolTip", make_tooltip_module(log))
        game.put("localeInfo", make_locale_info())
        self.expanded = [expanded]

        def set_expanded(flag):
            log.append(("systemSetting.SetIsBossInfoExpandend", (flag,)))
            self.expanded[0] = 1 if flag else 0
        gs.define(modules["systemSetting"], "IsBossInfoExpandend", lambda: self.expanded[0])
        gs.define(modules["systemSetting"], "SetIsBossInfoExpandend", set_expanded)
        nonplayer = modules["nonplayer"]
        gs.define(nonplayer, "GetMonsterName", lambda vnum: MONSTERS.get(vnum, ("", 0))[0])
        gs.define(nonplayer, "GetMonsterLevel", lambda vnum: MONSTERS.get(vnum, ("", 0))[1])
        # The characters in view: vid -> (name, race or mob vnum).
        self.instances = {}
        chr_module = modules["chr"]
        gs.define(chr_module, "GetNameByVID", lambda vid: self.instances.get(vid, ("", 0))[0])
        gs.define(chr_module, "GetVirtualNumber", lambda vid: self.instances.get(vid, ("", 0))[1])
        gs.define(chr_module, "HasInstance", lambda vid: vid in self.instances)
        gs.define(modules["player"], "GetName", lambda: "Me")
        modules["wndMgr"].GetScreenWidth = lambda: SCREEN[0]
        modules["wndMgr"].GetScreenHeight = lambda: SCREEN[1]
        game.state.now = float(game.time)
        # The Wave 4 engine the facades need (nui_hud.has_engine_4).
        gs.define(modules["nuigame"], "WatchLeaveRange", lambda *args: True)
        gs.define(modules["nuigame"], "StopLeaveRange", lambda *args: True)
        gs.define(modules["nuigame"], "WhisperAttach", lambda *args: True)
        modules["nui"]._nui.LoadDocumentAs = lambda path, model: True
        with quiet():
            game.load("nui_text", "nui_text.py")
            self.colorInfo = game.load("colorInfo", "colorinfo.py")
            self.uiBossInfo = game.load("uiBossInfo", "uibossinfo.py")
            self.uiDamageCount = game.load("uiDamageCount", "uidamagecount.py")
            if nui_on:
                game.load("nui_limits", "nui_limits.py")
                game.load("nui_facade", "nui_facade.py")
                game.load("nui_proxies", "nui_proxies.py")
                game.load("nui_form_proxies", "nui_form_proxies.py")
                game.load("nui_boss_info", "nui_boss_info.py")
                game.load("nui_damage_count", "nui_damage_count.py")
        self.nui_windows = game.loaded["nui_windows"]

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def clock(self, seconds):
        """Moves app.GetTime, app.GetGlobalTimeStamp and nui.now together."""
        self.game.time += seconds
        self.game.timestamp += int(seconds)
        self.game.state.now = float(self.game.time)

    def boss_info(self):
        """The Interface's line (checked against interfacemodule.py by the
        wiring test)."""
        with self, quiet():
            return self.nui_windows.make("boss-info", self.uiBossInfo.BossInfoWindow, "nui_boss_info.BossInfoWindow")

    def damage_count(self):
        with self, quiet():
            window = self.nui_windows.make("damage-count", self.uiDamageCount.DamageCountWindow,
                                           "nui_damage_count.DamageCountWindow")
            window.LoadWindow()
            window.Hide()
        return window

    def calls(self, prefix):
        return [entry for entry in self.game.log if entry[0].startswith(prefix)]


def board_of(window):
    demand = getattr(window, "demand", None)
    return demand.board() if demand is not None else None


def compiled(file_name, class_name, methods, scope=None):
    """`methods` of `class_name` in assets/root/<file_name>, compiled into a
    bare class (their own code), with the module's names `scope` gives."""
    with open(os.path.join(ROOT, file_name), encoding="utf-8", errors="replace") as handle:
        tree = ast.parse(handle.read())
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name in methods:
                    found.append(item)
    names = set(item.name for item in found)
    missing = [name for name in methods if name not in names]
    if missing:
        raise AssertionError("%s.%s lacks %s" % (file_name, class_name, ", ".join(missing)))
    klass = ast.ClassDef(name=class_name, bases=[], keywords=[], body=found, decorator_list=[])
    module = ast.Module(body=[klass], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = dict(scope or {})
    exec(compile(module, file_name, "exec"), namespace)
    return namespace[class_name]


def source(file_name):
    with open(os.path.join(ROOT, file_name), encoding="utf-8", errors="replace") as handle:
        return handle.read()


def mangled(name, class_name):
    """A private method's name as Python mangles it in `class_name`."""
    if name.startswith("__") and not name.endswith("__"):
        return "_%s%s" % (class_name.lstrip("_"), name)
    return name


def key_lines(text, keys):
    return [line for line in text.splitlines() if re.split(r"\t", line)[0] in keys]
