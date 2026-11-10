"""What the NOVA-25 client tests share (the dungeon manager, its drops panel and the dungeon
ranking; assets/root/uitimerwindow.py and uidungeonrank.py, their NovaUI facades): the names
fork C's client exports for them (OLD's: player.GetDungeonRank and ClearDungeonRank,
net.RequestDungeonDrop), the legacy widgets the stand-in ui lacks (ui.ScrollWindow,
ui.CheckBox, ui.MakeTextLine), the locale files the window reads (pack_open over the real asset
tree), and a world of each kind: the legacy one (nui_w4_world.World with every flag off) and the
NovaUI one (the dungeon windows on)."""
import builtins
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import wave6_support as w6  # noqa: E402

ASSETS = os.path.normpath(os.path.join(HERE, "..", "assets"))
FLAGS = "+dungeon-timer,+dungeon-rank,+dungeon-drops"
DUNGEON_MODULES = ("nui_limits", "nui_proxies", "nui_form_proxies", "nui_facade", "nui_dungeon_drops",
                   "nui_dungeon_notice", "nui_dungeon_timer", "nui_dungeon_rank")
NOW = 1700000000
POSITION = [1000.0, 2000.0, 0.0]


def store_path(path):
    """A pack path ("locale/en/dungeon_desc/0.txt") in the asset tree."""
    path = path.replace("\\", "/").lstrip("/")
    if path.startswith("locale/"):
        return os.path.join(ASSETS, "locale", path)
    return os.path.join(ASSETS, path)


def pack_open(path, mode="r"):
    with open(store_path(path), encoding="utf-8") as handle:
        return io.StringIO(handle.read())


class ScrollWindow(object):
    """ui.ScrollWindow (ui.py ScrollWindow): its content, size and wheel; it records what the
    windows ask of it."""

    THIN, MIDDLE, THICK = 0, 1, 2

    def __init__(self, width, height, kind=0, layer="UI"):
        self.size = (width, height)
        self.position = (0, 0)
        self.content = None
        self.shown = False
        self.calls = []

    def SetParent(self, parent):
        pass

    def SetPosition(self, x, y):
        self.position = (x, y)

    def SetContentWindow(self, window):
        self.content = window

    def FitWidth(self, width):
        self.size = (width, self.size[1])

    def OnContentWindowSizeChange(self):
        self.calls.append("size")

    def ScrollToStart(self):
        self.calls.append("start")

    def OnRunMouseWheel(self, length):
        self.calls.append(("wheel", length))
        return True

    def Show(self):
        self.shown = True

    def Hide(self):
        self.shown = False

    def IsShow(self):
        return self.shown


def interface_keys(locale="en"):
    """locale_interface.txt's keys (uiScriptLocale's)."""
    values = {}
    with open(os.path.join(ASSETS, "locale", "locale", locale, "locale_interface.txt"), encoding="utf-8") as handle:
        for line in handle.read().split("\n"):
            fields = line.rstrip("\r").split("\t")
            if len(fields) >= 2:
                values.setdefault(fields[0], fields[1])
    return values


class ModelPreview(object):
    """The client's modelpreview module (PythonModelPreviewModule.cpp), recording its calls."""

    def __init__(self):
        self.calls = []

    def Select(self, name, race):
        self.calls.append(("Select", name, race))
        return 1

    def Show(self, name, show):
        self.calls.append(("Show", name, bool(show)))

    def Clear(self, name):
        self.calls.append(("Clear", name))

    def SetStill(self, name, still):
        self.calls.append(("SetStill", name, bool(still)))

    def GetState(self, name):
        return {"shown": 0, "race": 0, "has_model": 0, "renders": 0, "texels": (0, 0)}


class RenderTarget(object):
    """ui.RenderTarget (the client's render target widget)."""

    def __init__(self):
        self.name = ""
        self.shown = False

    @staticmethod
    def IsAvailable():
        return True

    def SetParent(self, parent):
        pass

    def AddFlag(self, flag):
        pass

    def SetPosition(self, x, y):
        pass

    def SetSize(self, width, height):
        pass

    def SetRenderTarget(self, name):
        self.name = name

    def Show(self):
        self.shown = True

    def Hide(self):
        self.shown = False


def install(game):
    """C's names and the missing widgets on a stand-in client's modules."""
    game.modules["uiScriptLocale"].__dict__.update(interface_keys())
    ui = game.modules["ui"]
    game.legacy_boards = []
    base_board = ui.BoardWithTitleBar

    class CountingBoard(base_board):
        """ui.BoardWithTitleBar: a real one draws its corners and lines as soon as it is shown."""

        def __init__(self, *args, **kwargs):
            base_board.__init__(self, *args, **kwargs)
            game.legacy_boards.append(self)
    ui.BoardWithTitleBar = CountingBoard
    ui.ScrollWindow = ScrollWindow
    if not isinstance(getattr(ui, "CheckBox", None), type):
        ui.CheckBox = w6.CheckBox

    def make_text_line(parent):
        line = ui.TextLine()
        line.Show()
        return line
    ui.MakeTextLine = make_text_line

    player = game.modules["player"]
    game.dungeon_rank = []
    game.position = list(POSITION)
    support.define(player, "GetDungeonRank", lambda: [list(row) for row in game.dungeon_rank])

    def clear_rank():
        del game.dungeon_rank[:]
    support.define(player, "ClearDungeonRank", clear_rank)
    support.define(player, "GetMainCharacterPosition", lambda: tuple(game.position))
    game.status[player.LEVEL] = 100
    nonplayer = game.modules["nonplayer"]
    support.define(nonplayer, "GetMonsterName", lambda vnum: "mob %d" % vnum)
    app = game.modules["app"]
    app.GetLocalePath = lambda: "locale/en"
    game.timestamp = NOW
    wnd = game.modules["wndMgr"]
    wnd.GetScreenWidth = lambda: 1600
    wnd.GetScreenHeight = lambda: 900
    builtins.pack_open = pack_open


class World(w4.World):
    """nui_w4_world.World with the dungeon windows: legacy (nui_on False) or NovaUI."""

    def __init__(self, nui_on, preview=False):
        def setup(game):
            install(game)
            if preview:
                game.modules["modelpreview"] = ModelPreview()
                game.modules["ui"].RenderTarget = RenderTarget
        w4.World.__init__(self, nui_on, windows=FLAGS, setup=setup, modules=w4.TRADE_MODULES)
        game = self.game
        with self.game, w4.quiet():
            self.timer_module = game.load("uiTimerWindow", "uitimerwindow.py")
            self.timer_module.pack_open = pack_open
            self.rank_module = game.load("uiDungeonRank", "uidungeonrank.py")
            if nui_on:
                for name in DUNGEON_MODULES:
                    if os.path.isfile(os.path.join(support.ROOT, name + ".py")):
                        game.load(name, name + ".py")
        self.reset()
        self.interface = Interface(self)

    def reset(self):
        """The module state a new client starts with."""
        module = self.timer_module
        module.reset_session()
        for table in (module.ALLOW_NOTICE, module.HIDDEN_DUNGEONS, module.SESSION_HIDDEN):
            table.clear()
        module.OPEN_NOTICE_COUNT[0] = 0

    def timer(self):
        """The dungeon manager as the Interface makes it (__MakeDungeonWindows), hidden."""
        window = self.make("dungeon-timer", "uiTimerWindow", "TimerWindow", "nui_dungeon_timer.TimerWindow")
        with self.game, w4.quiet():
            window.BindInterface(self.interface)
            window.LoadWindow()
            window.SetToolTip(self.tooltip)
            window.Hide()
        self.interface.wndTimer = window
        return window

    def rank(self):
        window = self.make("dungeon-rank", "uiDungeonRank", "DungeonRankWindow", "nui_dungeon_rank.DungeonRankWindow")
        with self.game, w4.quiet():
            window.LoadWindow()
            window.Hide()
        self.interface.wndDungeonRank = window
        return window

    def chat_commands(self):
        return [args[0] for name, args in self.game.log if name == "net.SendChatPacket"]

    def drop_requests(self):
        return [args for name, args in self.game.log if name == "net.RequestDungeonDrop"]


class Interface(object):
    """The Interface's half (interfacemodule.py's NOVA-25 methods, compiled from the file)."""

    def __init__(self, world):
        self.world = world
        self.wndTimer = None
        self.wndDungeonRank = None

    def OpenDungeonRank(self):
        self.wndDungeonRank.Open(-1, -1)

    def RefreshDungeonRank(self, type, dungeonIndex):
        self.wndDungeonRank.RefreshDungeonRank(type, dungeonIndex)

    def SetPersonalDungeonRank(self, rank, name, count, type):
        self.wndDungeonRank.SetPersonalDungeonRank(rank, name, count, type)
