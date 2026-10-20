"""Tests for the NovaUI map and world windows of MAP AND WORLD CONTENT
(assets/root/nui_minimap.py, nui_atlas.py, nui_player_gauge.py,
nui_shop_signs.py, nui_guild_war.py) and their stand-in images
(tools/nui_view_fixtures.py): python3 -B -m unittest nui_world_test (from
tools/).

Plain CPython over nui_game_support's stand-ins, extended here (P10 spec
4.3: in this file only) with a stateful miniMap (Show, Hide, ShowAtlas,
HideAtlas and their getters), a legacy ui.MarkBox that asks the guild module
for the mark as the real one does, the guild name as the client answers it
(a str), and legacy GuildWarScoreBoard and Interface methods taken from
uiguild.py and interfacemodule.py by their syntax trees, since those modules
import half the client. For each window:
- facade: every method the Interface, game.py, the builder module and C++
  call on the legacy class exists on the NovaUI class with a signature the
  legacy callers can use, the class constants are the legacy ones, and the
  constructor takes the legacy arguments;
- differential: the legacy class and the NovaUI facade, each in a world of
  its own with the same stand-in state and driven through the same flows
  (the Interface's and C++'s calls, the legacy widgets' events against the
  board's data events), make the same miniMap.* state calls and net.* calls,
  in order, and show the same state after each step (shown, open, the
  texts); the per-frame calls legacy makes and NovaUI never makes are left
  out (miniMap.Update, Render, UpdateAtlas, RenderAtlas, GetInfo,
  GetAtlasInfo, chr.GetProjectPosition, textTail.GetPosition, IsChat) with
  the getters;
- fixture: each board, set from each fixture, has every fixture key in its
  model with the same kind, and list entries have the keys the document
  binds;
- no per-frame Python: the modules define no OnUpdate, OnRender or
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_test_support as base  # noqa: E402
import nui_view_fixtures  # noqa: E402

ROOT = support.ROOT
REPO = os.path.normpath(os.path.join(base.HERE, ".."))
NUI = os.path.join(REPO, "assets", "nui", "nui")
WINDOWS = os.path.join(NUI, "windows")
CLASSIC_WINDOWS = os.path.join(NUI, "skins", "classic", "windows")
WORLD_MODULES = ("nui_minimap", "nui_atlas", "nui_player_gauge", "nui_shop_signs", "nui_guild_war")
WORLD_WINDOWS = ("minimap", "atlas", "player-gauge", "shop-signs", "guild-war")
MAP_A1 = "metin2_map_a1"
DARK_MAP = "metin2_map_monkeydungeon"   # in MiniMap.CANNOT_SEE_INFO_MAP_DICT
# The per-frame calls legacy makes and NovaUI's engine makes instead (P10 spec 5.0.5).
PER_FRAME = {"miniMap.Update", "miniMap.Render", "miniMap.UpdateAtlas", "miniMap.RenderAtlas", "miniMap.GetInfo",
             "miniMap.GetAtlasInfo", "chr.GetProjectPosition", "textTail.GetPosition", "textTail.IsChat"}
GUILD_NAMES = {1: "Dragons", 2: "Lionheart", 3: "Northwind"}
GUILD_MARKS = {1: 1283, 2: 35}          # guild id -> mark id; guild 3 has none (-1)
MARK_TOTAL = 1280                        # CGuildMarkImage::MARK_TOTAL_COUNT

MINIMAP_METHODS = ("Show", "Hide", "ShowMiniMap", "HideMiniMap", "isShowMiniMap", "SetTop", "ScaleUp", "ScaleDown",
                   "SetMapName", "ShowAtlas", "ToggleAtlasWindow", "UpdateObserverCount", "Close", "SetImprisonmentDuration",
                   "Destroy")
ATLAS_METHODS = ("LoadWindow", "Show", "Hide", "IsShow", "SetMapName", "SetCenterPositionAdjust", "OnPressEscapeKey", "Destroy")
GAUGE_METHODS = ("Show", "Hide", "IsShow", "RefreshGauge", "EnableShowAlways", "DisableShowAlways", "Destroy")
SIGN_METHODS = ("Open", "Show", "Hide", "IsShow", "OnMouseLeftButtonUp", "Destroy")
WAR_METHODS = ("Initialize", "Open", "Show", "Hide", "IsShow", "SetScore", "UpdateMemberCount", "Destroy")
INTERFACE_METHODS = ("OnStartGuildWar", "OnEndGuildWar", "UpdateMemberCount", "OnRecvGuildWarPoint", "AppearPrivateShop",
                     "DisappearPrivateShop")


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def plain(text):
    """Text as shown: nui.plain_text's word joiners taken out."""
    return text.replace("⁠", "")


def source_of(file_name, names, inside=None):
    """The source of the top-level definitions `names` of a root module, or of
    the methods `names` of its class `inside`, dedented to the top level."""
    source = read(os.path.join(ROOT, file_name))
    tree = ast.parse(source)
    body = tree.body
    if inside is not None:
        body = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == inside).body
    parts = []
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            segment = ast.get_source_segment(source, node, padded=True)
            lines = segment.split("\n")
            indent = len(lines[0]) - len(lines[0].lstrip("\t"))
            parts.append("\n".join(line[indent:] if line.startswith("\t" * indent) else line for line in lines))
    return "\n\n".join(parts)


class Interface(object):
    """The Interface methods that make, call and drop the guild war boards and
    the shop signs (interfacemodule.py), taken by their syntax trees."""

    def __init__(self, game):
        self.game = game
        self.guildScoreBoardDict = {}
        self.privateShopAdvertisementBoardDict = {}
        self.wndGuild = types.SimpleNamespace(OnStartGuildWar=lambda *args: None, OnEndGuildWar=lambda *args: None)
        self.wndMiniMap = None


class World(object):
    """One world: a Game with the Wave 2b widgets and this file's extensions,
    the legacy modules, the NovaUI modules, and the Interface's methods."""

    def __init__(self, nui_on, windows="+hud2", engine=True, setup=None):
        self.game = game = support.Game(engine=engine)
        game.modules["systemSetting"].GetUINuiWindows = lambda: windows if nui_on else ""
        support.install_wave2b_ui(game)
        self.nui_on = nui_on
        self.map_state = {"show": False, "atlas": False}
        self.marks = {}            # MarkBox -> (filename, index), what the legacy mark box was given
        self._extend()
        if setup is not None:
            setup(game)
        game.load_standard()
        with quiet():
            game.load("colorInfo", "colorinfo.py")
            game.load("uiMiniMap", "uiminimap.py")
            game.load("uiPlayerGauge", "uiplayergauge.py")
            game.load("uiPrivateShopBuilder", "uiprivateshopbuilder.py")
            game.put("uiGuild", self._legacy_guild())
            for name in WORLD_MODULES:
                game.load(name, name + ".py")
        self.nui_windows = game.loaded["nui_windows"]
        self.interface = self._interface()

    # --- this file's extensions of the stand-ins ------------------------------------------

    def _extend(self):
        game, modules, world = self.game, self.game.modules, self
        mini_map = modules["miniMap"]
        answers = mini_map.__dict__["_answers"]
        for name in ("isShow", "isShowAtlas"):
            answers.pop(name, None)

        def flag(key, value):
            def apply():
                world.map_state[key] = value
            return apply
        support.define(mini_map, "Show", flag("show", True))
        support.define(mini_map, "Hide", flag("show", False))
        support.define(mini_map, "ShowAtlas", flag("atlas", True))
        support.define(mini_map, "HideAtlas", flag("atlas", False))
        support.define(mini_map, "isShow", lambda: world.map_state["show"])
        support.define(mini_map, "isShowAtlas", lambda: world.map_state["atlas"])

        guild = modules["guild"]
        support.define(guild, "GetGuildName", lambda guild_id: GUILD_NAMES.get(guild_id, "Noname"))
        support.define(guild, "GuildIDToMarkID", lambda guild_id: GUILD_MARKS.get(guild_id, -1))
        support.define(guild, "GetMarkImageFilenameByMarkID", lambda mark_id: "mark/10_%d.tga" % (mark_id // MARK_TOTAL))
        support.define(guild, "GetMarkIndexByMarkID", lambda mark_id: mark_id % MARK_TOTAL)

        locale = modules["localeInfo"]
        locale.MINIMAP_ZONE_NAME_DICT = {MAP_A1: "Yongan Area", DARK_MAP: "Monkey Dungeon"}
        locale.MINIMAP_OBSERVER_COUNT = "%d observers"
        locale.UI_POS_UNKNOWN = "Unknown Place"
        locale.GUILD_EMPTY_AREA = "Empty land"
        locale.SecondToDHM = lambda seconds: "%dm" % (seconds // 60)
        modules["net"].__dict__["_answers"]["GetServerInfo"] = "Nova - CH1"
        game.put("uiCommon", base.stub_module("uiCommon"))

        ui = modules["ui"]

        class MarkBox(ui.Window):
            """ui.MarkBox (ui.py:872-894): SetIndex asks the guild module for
            the mark's atlas and index, as the real one does."""

            def SetIndex(self, guild_id):
                mark_id = guild.GuildIDToMarkID(guild_id)
                world.marks[self] = (guild.GetMarkImageFilenameByMarkID(mark_id), guild.GetMarkIndexByMarkID(mark_id))
        ui.MarkBox = MarkBox

    def _legacy_guild(self):
        """uiGuild's GuildWarScoreBoard and GetGVGKey, compiled from uiguild.py
        over the stand-ins (the module imports half the client)."""
        module = types.ModuleType("uiGuild")
        module.__dict__.update(ui=self.game.modules["ui"], guild=self.game.modules["guild"], wndMgr=self.game.modules["wndMgr"])
        exec(compile(source_of("uiguild.py", ("GetGVGKey", "unsigned32", "GuildWarScoreBoard")), "uiguild.py", "exec"),
             module.__dict__)
        return module

    def _interface(self):
        namespace = {"nui_windows": self.nui_windows, "uiGuild": self.game.modules["uiGuild"],
                     "uiPrivateShopBuilder": self.game.loaded["uiPrivateShopBuilder"]}
        exec(compile(source_of("interfacemodule.py", INTERFACE_METHODS, inside="Interface"), "interfacemodule.py", "exec"),
             namespace)
        interface = Interface(self.game)
        for name in INTERFACE_METHODS:
            setattr(interface, name, types.MethodType(namespace[name], interface))
        return interface

    def __enter__(self):
        self.game.__enter__()
        return self

    def __exit__(self, *exc):
        return self.game.__exit__(*exc)

    def module(self, name):
        return self.game.loaded.get(name) or self.game.modules[name]

    # --- what the differential tests compare -------------------------------------------

    def mark_log(self):
        return len(self.game.log)

    def effects(self, since=0, modules=("miniMap", "net")):
        """The recorded calls with an effect, getters and per-frame calls left
        out; objects stand as their class names, as each world has its own."""
        found = []
        for name, args in self.game.log[since:]:
            module, function = name.split(".", 1)
            if module not in modules or name in PER_FRAME or support.is_getter(name) or function.startswith("is"):
                continue
            found.append((name, tuple(arg if isinstance(arg, (int, float, str, type(None))) else "<object>" for arg in args)))
        return found


def pair(**kwargs):
    return World(False, **kwargs), World(True, **kwargs)


def assert_callable_like(test, legacy_method, novaui_method, name):
    """Every call shape the legacy signature takes binds to the NovaUI one."""
    legacy = inspect.signature(legacy_method)
    novaui = inspect.signature(novaui_method)
    positional = [p for p in legacy.parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    required = [p for p in positional if p.default is p.empty]
    for count in range(len(required), len(positional) + 1):
        try:
            novaui.bind(*([None] * count))
        except TypeError as error:
            test.fail("%s: a legacy call with %d arguments does not bind: %s" % (name, count, error))


# --- facades ----------------------------------------------------------------------------------------

class Facades(unittest.TestCase):
    def setUp(self):
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)

    def check(self, legacy_class, novaui_class, methods, constants=(), same_name=True):
        for name in methods:
            self.assertTrue(hasattr(novaui_class, name), "%s.%s" % (novaui_class.__name__, name))
            legacy_method = getattr(legacy_class, name, None)
            if legacy_method is None:
                continue
            assert_callable_like(self, getattr(object.__new__(legacy_class), name),
                                 getattr(object.__new__(novaui_class), name), "%s.%s" % (novaui_class.__name__, name))
        for name in constants:
            self.assertEqual(getattr(novaui_class, name), getattr(legacy_class, name), name)
        self.assertIs(novaui_class.NUI_FACADE, True)
        if same_name:
            self.assertEqual(novaui_class.__name__, legacy_class.__name__)
        self.assertEqual(len(inspect.signature(novaui_class.__init__).parameters),
                         len(inspect.signature(legacy_class.__init__).parameters), "the legacy constructor arguments")

    def test_the_minimap_facade_keeps_the_legacy_surface(self):
        self.check(self.world.module("uiMiniMap").MiniMap, self.world.module("nui_minimap").MiniMap, MINIMAP_METHODS,
                   ("CANNOT_SEE_INFO_MAP_DICT",))
        self.assertIs(self.world.module("nui_minimap").MiniMap.CANNOT_SEE_INFO_MAP_DICT,
                      self.world.module("uiMiniMap").MiniMap.CANNOT_SEE_INFO_MAP_DICT, "imported, never copied")

    def test_the_atlas_facade_keeps_the_legacy_surface(self):
        self.check(self.world.module("uiMiniMap").AtlasWindow, self.world.module("nui_atlas").AtlasWindow, ATLAS_METHODS)

    def test_the_player_gauge_facade_keeps_the_legacy_surface(self):
        self.check(self.world.module("uiPlayerGauge").PlayerGauge, self.world.module("nui_player_gauge").PlayerGauge,
                   GAUGE_METHODS)

    def test_the_shop_sign_facade_keeps_the_legacy_surface(self):
        self.check(self.world.module("uiPrivateShopBuilder").PrivateShopAdvertisementBoard,
                   self.world.module("nui_shop_signs").ShopSign, SIGN_METHODS, same_name=False)

    def test_the_guild_war_facade_keeps_the_legacy_surface(self):
        self.check(self.world.module("uiGuild").GuildWarScoreBoard, self.world.module("nui_guild_war").GuildWarScoreBoard,
                   WAR_METHODS)

    def test_every_facade_answers_the_make_protocol_and_needs_the_wave2b_engine(self):
        hud = self.world.module("nui_hud")
        makers = (("minimap", "nui_minimap", "MiniMap", ()), ("atlas", "nui_atlas", "AtlasWindow", ()),
                  ("player-gauge", "nui_player_gauge", "PlayerGauge", (object(),)))
        for key, module, name, args in makers:
            with self.world, quiet():
                facade = getattr(self.world.module(module), name)(*args)
                self.assertTrue(facade.nui_ready(), name)
                self.assertIs(hud.current(key), facade, name)
                again = getattr(self.world.module(module), name)(*args)
                self.assertFalse(facade.nui_ready(), "%s: a new facade discards the previous one" % name)
                again.Destroy()
                self.assertFalse(again.nui_ready(), name)
                self.assertIsNone(hud.current(key), "%s: Destroy drops the record" % name)
        with self.world, quiet():
            for module, name in (("nui_shop_signs", "ShopSign"), ("nui_guild_war", "GuildWarScoreBoard")):
                self.assertTrue(getattr(self.world.module(module), name)().nui_ready(), name)
        for engine in (False, "2a"):
            world = World(True, engine=bool(engine))
            if engine == "2a":
                world.game.put("nuigame", base.stub_module("nuigame", RefreshQuickSlots=lambda: None))
            legacy = {"minimap": ("uiMiniMap", "MiniMap", ()), "player-gauge": ("uiPlayerGauge", "PlayerGauge", (object(),)),
                      "shop-signs": ("uiPrivateShopBuilder", "PrivateShopAdvertisementBoard", ()),
                      "guild-war": ("uiGuild", "GuildWarScoreBoard", ())}
            novaui = {"minimap": "nui_minimap.MiniMap", "player-gauge": "nui_player_gauge.PlayerGauge",
                      "shop-signs": "nui_shop_signs.ShopSign", "guild-war": "nui_guild_war.GuildWarScoreBoard"}
            with world, quiet():
                self.assertFalse(world.module("nui_hud").has_engine_2b(), engine)
                start = world.mark_log()
                for key, (module, name, args) in legacy.items():
                    made = world.nui_windows.make(key, getattr(world.module(module), name), novaui[key], *args)
                    self.assertEqual(type(made).__module__, module, "an older exe keeps the legacy %s" % key)
                creates = [call for call, _ in world.game.log[start:] if call == "miniMap.Create"]
                self.assertEqual(creates, ["miniMap.Create"], "the legacy minimap's Create alone: the facade made no call")


# --- the minimap and the atlas, legacy against NovaUI -------------------------------------------------

class MapDifferential(unittest.TestCase):
    def setup(self, game):
        game.answer("miniMap", "IsAtlas", 1)
        game.answer("miniMap", "GetAtlasSize", (1, 256, 256))

    def worlds(self, **kwargs):
        legacy, novaui = pair(setup=self.setup, **kwargs)
        for world in (legacy, novaui):
            with world, quiet():
                minimap = world.module("nui_windows").make("minimap", world.module("uiMiniMap").MiniMap, "nui_minimap.MiniMap")
                # Interface.ShowDefaultWindows, then the map name C++ sends at login.
                minimap.Show()
                minimap.ShowMiniMap()
                minimap.SetMapName(MAP_A1)
            world.minimap = minimap
        return legacy, novaui

    @staticmethod
    def state(world):
        """What shows: the window, the map (open) or the show button, the
        atlas, the observer line."""
        minimap = world.minimap
        atlas = minimap.AtlasWindow
        if world.nui_on:
            model = minimap.board.model
            return {"shown": minimap.IsShow(), "open": model["open"], "map": world.map_state["show"],
                    "atlas": bool(atlas.IsShow()), "atlas_map": world.map_state["atlas"],
                    "observers": model["observer_text"] if model["observers"] > 0 else None}
        observer = minimap.observerCount
        return {"shown": minimap.IsShow(), "open": minimap.OpenWindow.IsShow() and not minimap.CloseWindow.IsShow(),
                "map": world.map_state["show"], "atlas": bool(atlas.IsShow()), "atlas_map": world.map_state["atlas"],
                "observers": observer.GetText() if observer.IsShow() else None}

    def flow(self, steps, **kwargs):
        legacy, novaui = self.worlds(**kwargs)
        marks = [world.mark_log() for world in (legacy, novaui)]
        seen = []
        for world in (legacy, novaui):
            states = []
            for step in steps:
                with world, quiet():
                    step(world)
                states.append(self.state(world))
            seen.append(states)
        self.assertEqual(seen[1], seen[0], "the state after each step")
        self.assertEqual(novaui.effects(marks[1]), legacy.effects(marks[0]))
        return legacy, novaui

    @staticmethod
    def press(name):
        """A press on a minimap button: legacy's button event, NovaUI's data event."""
        legacy_buttons = {"scale_up": "ScaleUpButton", "scale_down": "ScaleDownButton", "hide_map": "MiniMapHideButton",
                          "show_map": "MiniMapShowButton", "atlas": "AtlasShowButton"}

        def step(world):
            if world.nui_on:
                world.minimap.board.fire(name, 0)
            else:
                getattr(world.minimap, legacy_buttons[name]).Click()
        return step

    def test_making_and_showing_the_minimap_makes_the_legacy_calls(self):
        legacy, novaui = self.worlds()
        self.assertEqual(novaui.effects(), legacy.effects())
        calls = [name for name, _ in novaui.effects()]
        self.assertEqual(calls, ["miniMap.Create", "miniMap.SetScale", "miniMap.HideAtlas", "miniMap.RegisterAtlasWindow",
                                 "miniMap.HideAtlas", "miniMap.Show", "miniMap.Show", "miniMap.Show"])
        self.assertEqual(self.state(novaui), self.state(legacy))
        self.assertEqual(novaui.minimap.board.model["server_info"], "Nova - CH1")
        self.assertEqual(type(novaui.minimap.AtlasWindow).__module__, "nui_atlas")

    def test_the_buttons_zoom_hide_and_show_the_map(self):
        self.flow([self.press("scale_up"), self.press("scale_up"), self.press("scale_down"), self.press("hide_map"),
                   self.press("show_map")])

    def test_the_interface_calls_toggle_zoom_and_the_keys(self):
        self.flow([lambda w: w.minimap.ScaleUp(), lambda w: w.minimap.ScaleDown(), lambda w: w.minimap.HideMiniMap(),
                   lambda w: w.minimap.isShowMiniMap() or w.minimap.ShowMiniMap(), lambda w: w.minimap.SetTop(),
                   lambda w: w.minimap.Close(), lambda w: w.minimap.ShowMiniMap()])

    def test_the_atlas_toggles_from_the_key_the_button_and_c_plus_plus(self):
        def c_open(world):
            registered = [args[0] for name, args in world.game.log if name == "miniMap.RegisterAtlasWindow"][-1]
            registered.Show()          # CPythonMiniMap::OpenAtlasWindow calls the handler's Show
        self.flow([lambda w: w.minimap.ToggleAtlasWindow(), lambda w: w.minimap.ToggleAtlasWindow(), self.press("atlas"),
                   lambda w: w.minimap.ShowAtlas(), lambda w: w.minimap.ToggleAtlasWindow(), c_open])

    def test_the_atlas_closes_from_its_button_and_from_escape(self):
        def close(world):
            atlas = world.minimap.AtlasWindow
            if world.nui_on:
                atlas.board.fire("close", 0)
            else:
                event = [call[1] for call in atlas.board.calls if call[0] == "SetCloseEvent"][-1]
                event()

        def escape(world):
            atlas = world.minimap.AtlasWindow
            if world.nui_on:
                self.assertTrue(atlas.escapeProxy.is_shown(), "the escape proxy shows with the atlas")
                self.assertTrue(atlas.escapeProxy._window.OnPressEscapeKey())
                self.assertFalse(atlas.escapeProxy.is_shown())
            else:
                self.assertTrue(atlas.OnPressEscapeKey())
        self.flow([lambda w: w.minimap.ShowAtlas(), close, lambda w: w.minimap.ShowAtlas(), escape])

    def test_a_map_without_an_atlas_shows_none_and_its_button_does_nothing(self):
        def setup(game):
            game.answer("miniMap", "IsAtlas", 0)
        legacy, novaui = pair(setup=setup)
        for world in (legacy, novaui):
            with world, quiet():
                world.minimap = world.module("nui_windows").make("minimap", world.module("uiMiniMap").MiniMap, "nui_minimap.MiniMap")
                world.minimap.Show()
        marks = [world.mark_log() for world in (legacy, novaui)]
        for world in (legacy, novaui):
            with world, quiet():
                world.minimap.ToggleAtlasWindow()
                world.minimap.ShowAtlas()
                if world.nui_on:
                    world.minimap.board.fire("atlas", 0)
                else:
                    world.minimap.AtlasShowButton.Click()
            self.assertFalse(world.minimap.AtlasWindow.IsShow())
        self.assertEqual(novaui.effects(marks[1]), legacy.effects(marks[0]))
        self.assertEqual(novaui.effects(marks[1]), [])
        self.assertFalse(novaui.minimap.board.model["has_atlas"], "the hint says the map has no atlas")

    def test_a_map_that_cannot_be_seen_hides_the_map_and_says_so(self):
        legacy, novaui = self.flow([lambda w: w.minimap.SetMapName(DARK_MAP), lambda w: w.minimap.ShowMiniMap(),
                                    self.press("show_map"), lambda w: w.minimap.SetMapName(MAP_A1)])
        formats = [args for name, args in novaui.game.log if name == "nuigame.SetViewHoverFormat" and args[0] == "minimap"]
        self.assertEqual(formats[-2:], [("minimap", "{name} (Unknown Place)"), ("minimap", "{name} ({x}, {y})")])

    def test_the_observer_count_shows_above_zero(self):
        self.flow([lambda w: w.minimap.UpdateObserverCount(3), lambda w: w.minimap.UpdateObserverCount(0),
                   lambda w: w.minimap.UpdateObserverCount(12)])

    def test_destroy_hides_the_map_lets_go_of_the_atlas_and_collection_destroys_the_map(self):
        legacy, novaui = self.worlds()
        marks = [world.mark_log() for world in (legacy, novaui)]
        for world in (legacy, novaui):
            with world, quiet():
                world.minimap.Destroy()
                world.minimap = None
                gc.collect()
        self.assertEqual(novaui.effects(marks[1]), legacy.effects(marks[0]))
        self.assertEqual([name for name, _ in novaui.effects(marks[1])],
                         ["miniMap.Hide", "miniMap.UnregisterAtlasWindow", "miniMap.Destroy"])
        self.assertIsNone(novaui.module("nui_hud").current("minimap"))
        self.assertIsNone(novaui.module("nui_hud").current("atlas"))


class MapNovaUI(unittest.TestCase):
    """What the NovaUI minimap and atlas do that legacy does per frame or in
    its layout."""

    def world(self, windows="+hud2", **kwargs):
        def setup(game):
            game.answer("miniMap", "IsAtlas", 1)
            game.answer("miniMap", "GetAtlasSize", (1, 256, 256))
        world = World(True, windows=windows, setup=setup, **kwargs)
        world.__enter__()
        self.addCleanup(world.__exit__)
        with quiet():
            world.minimap = world.module("nui_minimap").MiniMap()
        return world

    def test_the_hover_formats_are_set_once_each(self):
        world = self.world()
        formats = [args for name, args in world.game.log if name == "nuigame.SetViewHoverFormat"]
        self.assertEqual(formats, [("atlas", "{name}({x}, {y})", {"empty_guild_area": "Empty land"}),
                                   ("minimap", "{name} ({x}, {y})")])

    def test_the_view_needs_no_python_per_frame(self):
        world = self.world()
        with quiet():
            world.minimap.Show()
        self.assertEqual([name for name, _ in world.game.log if name in PER_FRAME], [])

    def test_the_minimap_makes_the_legacy_atlas_while_the_atlas_flag_is_off(self):
        world = self.world(windows="+minimap")
        self.assertEqual(type(world.minimap.AtlasWindow).__module__, "uiMiniMap")
        self.assertEqual(world.nui_windows.DECISIONS.get("atlas"), "legacy: flag off")
        with quiet():
            world.minimap.ToggleAtlasWindow()
        self.assertTrue(world.minimap.AtlasWindow.IsShow())

    def test_set_top_brings_the_document_to_the_front(self):
        world = self.world()
        world.minimap.SetTop()
        self.assertEqual(world.minimap.board.front, 1)

    def test_a_document_that_does_not_load_leaves_the_legacy_minimap_and_destroys_nothing_late(self):
        world = World(True)
        world.__enter__()
        self.addCleanup(world.__exit__)
        world.game.state.failing.add("nui/windows/minimap/minimap.rml")
        with quiet():
            made = world.nui_windows.make("minimap", world.module("uiMiniMap").MiniMap, "nui_minimap.MiniMap")
            gc.collect()
        self.assertEqual(type(made).__module__, "uiMiniMap")
        self.assertEqual(world.game.dbg.errors, ["nui_windows: minimap: the document did not load; using the legacy window"])
        calls = [name for name, _ in world.game.log if name in ("miniMap.Destroy", "miniMap.UnregisterAtlasWindow")]
        self.assertEqual(calls, ["miniMap.UnregisterAtlasWindow"], "the discarded atlas lets go; no late Destroy")

    def test_set_imprisonment_duration_sets_the_line_once(self):
        world = self.world()
        world.minimap.SetImprisonmentDuration(3600)
        self.assertEqual(world.minimap.board.model["server_info"], "AUTOBAN_QUIZ_REST_TIME: 60m")

    def test_the_atlas_titles_and_places_as_legacy(self):
        world = self.world()
        atlas = world.minimap.AtlasWindow
        self.assertIsNone(atlas.board, "hidden: no document (P11 spec D5)")
        self.assertEqual(atlas.title, "")
        atlas.SetMapName(MAP_A1)
        self.assertEqual(atlas.title, "Yongan Area", "kept for the next board")
        world.game.state.scale = 1.5
        atlas.SetCenterPositionAdjust(30, -20)
        world.game.answer("miniMap", "GetAtlasSize", (1, 256, 256))
        with quiet():
            atlas.Show()
        self.assertEqual(atlas.board.model["title"], "Yongan Area")
        self.assertEqual(atlas.board.placement, ("position", (800 + 30) / 1.5, (450 - 20) / 1.5, (0.5, 0.5)))
        atlas.SetMapName("metin2_map_unknown")
        self.assertEqual(atlas.board.model["title"], "", "a map the dict lacks: the default title (legacy raises)")
        atlas.SetCenterPositionAdjust(10, 10)
        self.assertEqual(atlas.board.placement, ("position", (800 + 10) / 1.5, (450 + 10) / 1.5, (0.5, 0.5)))

    def test_the_hidden_atlas_holds_no_document_and_keeps_its_place(self):
        world = self.world()
        atlas = world.minimap.AtlasWindow
        atlas_doc = "nui/windows/atlas/atlas.rml"
        documents = lambda: [window.DOCUMENT for window in world.game.state.windows if window._doc]
        self.assertNotIn(atlas_doc, documents(), "the constructor's probe left nothing")
        with world.game:
            self.assertTrue(atlas.nui_ready())
        world.game.answer("miniMap", "GetAtlasSize", (1, 256, 256))
        atlas.SetCenterPositionAdjust(-40, 25)
        with quiet():
            atlas.Show()
        self.assertIn(atlas_doc, documents())
        self.assertEqual(atlas.board.placement, ("position", 800 - 40.0, 450 + 25.0, (0.5, 0.5)))
        with quiet():
            atlas.Hide()
        self.assertNotIn(atlas_doc, documents())
        self.assertIsNone(atlas.board)
        self.assertFalse(atlas.escapeProxy.is_shown())
        with quiet():
            atlas.Show()
        self.assertEqual(atlas.board.placement, ("position", 800 - 40.0, 450 + 25.0, (0.5, 0.5)), "the place survives")
        self.assertIs(atlas.board.model["shown"], True)

    def test_the_atlas_shows_only_with_a_size(self):
        world = self.world()
        world.game.answer("miniMap", "GetAtlasSize", (0, 0, 0))
        start = world.mark_log()
        with quiet():
            world.minimap.AtlasWindow.Show()
        self.assertFalse(world.minimap.AtlasWindow.IsShow())
        self.assertFalse(world.minimap.AtlasWindow.escapeProxy.is_shown())
        self.assertEqual(world.effects(start), [])


# --- the player gauge -------------------------------------------------------------------------------

class GaugeDifferential(unittest.TestCase):
    def worlds(self):
        legacy, novaui = pair()
        for world in (legacy, novaui):
            world.game.answer("player", "GetMainCharacterIndex", 7)
            world.game.status.update({5: 1000, 6: 1000})
            with world, quiet():
                world.gauge = world.module("nui_windows").make("player-gauge", world.module("uiPlayerGauge").PlayerGauge,
                                                               "nui_player_gauge.PlayerGauge", object())
                world.gauge.Hide()
        return legacy, novaui

    def test_the_gauge_shows_below_half_while_alt_is_held_and_hides_above_half(self):
        steps = [
            ("RefreshGauge", 1000), ("RefreshGauge", 400), ("RefreshGauge", 499), ("RefreshGauge", 600),
            ("RefreshGauge", 500), ("RefreshGauge", 499), ("RefreshGauge", 501), ("EnableShowAlways", 1000),
            ("RefreshGauge", 1000), ("DisableShowAlways", 1000), ("EnableShowAlways", 300), ("DisableShowAlways", 300),
        ]
        legacy, novaui = self.worlds()
        seen = []
        marks = [world.mark_log() for world in (legacy, novaui)]
        for world in (legacy, novaui):
            shown = []
            for method, hp in steps:
                world.game.status[5] = hp
                with world, quiet():
                    getattr(world.gauge, method)()
                shown.append(bool(world.gauge.IsShow()))
            seen.append(shown)
        self.assertEqual(seen[1], seen[0])
        self.assertEqual(seen[0], [False, True, True, False, False, True, False, True, True, False, True, True])
        self.assertEqual(novaui.effects(marks[1], ("player", "net")), legacy.effects(marks[0], ("player", "net")))
        model = novaui.gauge.board.model
        self.assertEqual((model["shown"], model["vid"]), (True, 7))

    def test_the_novaui_gauge_is_an_anchor_on_the_name_tail_fed_by_the_hp_ratio(self):
        legacy, novaui = self.worlds()
        board = novaui.gauge.board
        self.assertTrue(board.is_visible(), "the board stays shown; the model's shown hides the gauge")
        self.assertFalse(board.model["shown"])
        self.assertEqual(type(board).FEEDS, {"hp_ratio": "player.hp_ratio"})
        self.assertIn(("PlayerGaugeBoard", "hp_ratio", "player.hp_ratio"), novaui.game.state.binds)
        novaui.game.state.publish("player.hp_ratio", 0.25)
        self.assertEqual(board.model["hp_ratio"], 0.25)
        document = read(os.path.join(WINDOWS, "player-gauge", "player-gauge.rml"))
        self.assertIn('<nui-anchor id="player-gauge-anchor" class="player-gauge__anchor" mode="tail" align-x="0.5" '
                      'align-y="0" offset-y="5"\n\t\tchat-offset-y="17" data-attr-vid="vid" data-if="shown">', document)
        self.assertIn('data-attr-value="hp_ratio"', document)
        with novaui, quiet():
            novaui.gauge.Destroy()
        self.assertFalse(board._doc)


# --- the shop signs ---------------------------------------------------------------------------------

class SignDifferential(unittest.TestCase):
    OWN = 13

    def worlds(self):
        legacy, novaui = pair()
        for world in (legacy, novaui):
            world.game.answer("player", "GetMainCharacterIndex", self.OWN)
        return legacy, novaui

    @staticmethod
    def builder(world):
        return world.module("uiPrivateShopBuilder")

    def visible(self, world):
        """{vid: text} of the signs that show. Legacy: the boards the builder
        module keeps that are shown, after a frame of their OnUpdate (the
        option hides the other players' signs there); NovaUI: the entries
        that pass the document's rule (shown and (show_all or own))."""
        if not world.nui_on:
            boards = self.builder(world).g_privateShopAdvertisementBoardDict
            for board in list(boards.values()):
                if board.IsShow():
                    board.OnUpdate()
            return {vid: board.textLine.GetText() for vid, board in boards.items() if board.IsShow()}
        signs = world.module("nui_shop_signs")
        board = signs._board
        if board is None or not board._doc:
            return {}
        show_all = board.model["show_all"]
        return {s["vid"]: s["text"] for s in board.model["signs"] if s["shown"] and (show_all or s["own"])}

    def flow(self, steps):
        legacy, novaui = self.worlds()
        seen = []
        for world in (legacy, novaui):
            states = []
            for step in steps:
                with world, quiet():
                    step(world)
                    gc.collect()
                    states.append(self.visible(world))
            seen.append(states)
        self.assertEqual(seen[1], seen[0], "the signs that show after each step")
        self.assertEqual(novaui.effects(0, ("net",)), legacy.effects(0, ("net",)))
        return legacy, novaui, seen[0]

    @staticmethod
    def option(on):
        def step(world):
            world.game.show_sales_text = on
            world.game.state.publish("system.show_sales_text", on)
        return step

    def option_on_as_the_dialog(self):
        """The game options' Show button (uigameoption.py:236-239): the flag,
        then UpdateADBoard. Legacy's signs hidden by the option stay hidden
        until that call; NovaUI's show again with the flag alone."""
        def step(world):
            self.option(True)(world)
            self.builder(world).UpdateADBoard()
        return step

    @staticmethod
    def click(vid, button=0):
        def step(world):
            if world.nui_on:
                world.module("nui_shop_signs")._board.fire("open", vid, button)
            elif button == 0:
                world.module("uiPrivateShopBuilder").g_privateShopAdvertisementBoardDict[vid].OnMouseLeftButtonUp()
        return step

    def test_the_classic_width_is_legacys_text_length_rule(self):
        """--legacy-width, which the classic skin sizes a sign by, is the
        width legacy's board gets (len * 6 + 20, at least ThinBoard's 32; a
        color tag counts, as legacy counts it)."""
        legacy, novaui = self.worlds()
        names = {11: "Potions and more", 12: "|cffffc700Golden|r Bazaar", 13: "My", 14: ""}
        for world in (legacy, novaui):
            with world, quiet():
                for vid, name in names.items():
                    world.interface.AppearPrivateShop(vid, name)
        boards = self.builder(legacy).g_privateShopAdvertisementBoardDict
        legacy_widths = {vid: "%ddp" % max(32, boards[vid].size[0]) for vid in names}
        novaui_widths = {s["vid"]: s["legacy_width"] for s in novaui.module("nui_shop_signs")._board.model["signs"]}
        self.assertEqual(novaui_widths, legacy_widths)
        self.assertEqual(novaui_widths[11], "116dp")
        self.assertEqual(novaui_widths[14], "32dp")

    def test_signs_appear_hide_with_the_option_and_open_their_shop(self):
        legacy, novaui, seen = self.flow([
            lambda w: w.interface.AppearPrivateShop(11, "Potions and more"),
            lambda w: w.interface.AppearPrivateShop(self.OWN, "My shop"),
            lambda w: w.interface.AppearPrivateShop(12, "|cffffc700Golden|r Bazaar"),
            self.click(11), self.click(12, 1),
            self.option(False), self.click(self.OWN),
            self.option_on_as_the_dialog(),
            lambda w: w.interface.DisappearPrivateShop(11),
            lambda w: w.interface.AppearPrivateShop(12, "Golden Bazaar II"),
            lambda w: w.interface.DisappearPrivateShop(99),
        ])
        self.assertEqual(seen[1], {11: "Potions and more", self.OWN: "My shop"})
        self.assertEqual(seen[5], {self.OWN: "My shop"}, "the option hides the other players' signs")
        self.assertEqual(seen[7], {self.OWN: "My shop", 12: "|cffffc700Golden|r Bazaar", 11: "Potions and more"})
        self.assertEqual(seen[-1], {self.OWN: "My shop", 12: "Golden Bazaar II"})
        self.assertEqual(novaui.effects(0, ("net",)), [("net.SendOnClickPacket", (11,)), ("net.SendOnClickPacket", (self.OWN,))])

    def test_the_signs_share_one_document_that_goes_with_the_last_sign(self):
        legacy, novaui = self.worlds()
        signs = novaui.module("nui_shop_signs")
        with novaui, quiet():
            novaui.interface.AppearPrivateShop(11, "a@ui.OK")
            novaui.interface.AppearPrivateShop(12, "b")
            board = signs._board
            self.assertIs(novaui.interface.privateShopAdvertisementBoardDict[11].board, board)
            self.assertEqual([s["vid"] for s in board.model["signs"]], [11, 12])
            self.assertEqual(board.model["signs"][0]["text"], "a@ui.OK", "names go to nui-text as written")
            self.assertEqual(novaui.game.state.shows.count(("ShopSignBoard", signs.DOCUMENT)), 1)
            novaui.interface.DisappearPrivateShop(11)
            gc.collect()
            self.assertEqual([s["vid"] for s in board.model["signs"]], [12])
            novaui.interface.DisappearPrivateShop(12)
            gc.collect()
            self.assertFalse(board._doc, "the document goes with the last sign")
            self.assertIsNone(signs._board)
            novaui.interface.AppearPrivateShop(14, "c")
            self.assertTrue(signs._board._doc, "and comes back with the next")

    def test_close_all_removes_every_sign_and_the_document(self):
        legacy, novaui = self.worlds()
        signs = novaui.module("nui_shop_signs")
        with novaui, quiet():
            novaui.interface.AppearPrivateShop(11, "a")
            novaui.interface.AppearPrivateShop(12, "b")
            board = signs._board
            signs.close_all()
            self.assertFalse(board._doc)
            # The builder module keeps the old signs (legacy's dict outlives
            # the phase); they act on nothing now.
            self.builder(novaui).UpdateADBoard()
            self.assertIsNone(signs._board)
            self.assertFalse(novaui.interface.privateShopAdvertisementBoardDict[11].IsShow())

    def test_the_document_binds_the_option_and_anchors_each_sign(self):
        self.assertEqual(World(True).module("nui_shop_signs").ShopSignBoard.FEEDS, {"show_all": "system.show_sales_text"})
        document = read(os.path.join(WINDOWS, "shop-signs", "shop-signs.rml"))
        self.assertIn('<nui-anchor class="shop-signs__anchor" mode="project" height="220" data-attr-vid="s.vid"', document)
        self.assertIn('data-attr-id="\'shop-sign-\' + s.vid" data-if="s.shown &amp;&amp; (show_all || s.own)"', document)
        self.assertIn('data-event-mouseup="open(s.vid, ev.button)"', document)
        self.assertIn('links="off" data-attr-value="s.text"', document)
        self.assertIn('<div class="shop-signs__slot" data-for="s : signs">\n\t\t<nui-anchor', document,
                      "the repeated slot binds nothing")


# --- the guild war boards ------------------------------------------------------------------------------

class WarDifferential(unittest.TestCase):
    def texts(self, world):
        """Each board's two texts, the first war first; legacy's widgets
        against NovaUI's entries (whose column lists the newest first)."""
        boards = world.interface.guildScoreBoardDict
        if not world.nui_on:
            return [[board.allyDataDict["TEXT"].GetText(), board.enemyDataDict["TEXT"].GetText()]
                    for board in boards.values() if board.IsShow()]
        module = world.module("nui_guild_war")
        if module._board is None:
            return []
        return [[plain(row["text"]) for row in entry["rows"]] for entry in reversed(module._board.model["boards"])]

    def test_the_boards_follow_the_scores_and_member_counts_as_legacy(self):
        legacy, novaui = pair()
        steps = [
            lambda w: w.interface.OnStartGuildWar(1, 2),
            lambda w: w.interface.OnRecvGuildWarPoint(1, 2, 5),
            lambda w: w.interface.OnRecvGuildWarPoint(2, 1, 3),
            lambda w: w.interface.UpdateMemberCount(1, 3, 2, 4),
            lambda w: w.interface.OnRecvGuildWarPoint(4, 1, 9),
            lambda w: w.interface.OnStartGuildWar(1, 3),
            lambda w: w.interface.UpdateMemberCount(3, 6, 1, 2),
            lambda w: w.interface.OnEndGuildWar(1, 2),
            lambda w: w.interface.OnEndGuildWar(1, 3),
        ]
        seen = []
        for world in (legacy, novaui):
            states = []
            for step in steps:
                with world, quiet():
                    step(world)
                states.append(self.texts(world))
            seen.append(states)
        self.assertEqual(seen[1], seen[0])
        self.assertEqual(seen[0][3], [["Dragons(3) 5", "Lionheart(4) 3"]])
        self.assertEqual(seen[0][6], [["Dragons(3) 5", "Lionheart(4) 3"], ["Dragons(2) 0", "Northwind(6) 0"]])
        self.assertEqual(seen[0][-1], [])
        self.assertIsNone(novaui.module("nui_guild_war")._board, "the document goes with the last war")

    def test_the_classic_width_is_legacys_name_length_rule(self):
        """--legacy-width, which the classic skin sizes a board by: legacy's
        __RefreshName width, 15 wider once both member counts are known."""
        legacy, novaui = pair()
        steps = [
            lambda w: w.interface.OnStartGuildWar(1, 2),
            lambda w: w.interface.UpdateMemberCount(1, 3, 2, 4),
            lambda w: w.interface.OnStartGuildWar(1, 3),
        ]
        seen = []
        for world in (legacy, novaui):
            states = []
            for step in steps:
                with world, quiet():
                    step(world)
                if world.nui_on:
                    entries = reversed(world.module("nui_guild_war")._board.model["boards"])
                    states.append([entry["legacy_width"] for entry in entries])
                else:
                    states.append(["%ddp" % max(32, board.size[0]) for board in world.interface.guildScoreBoardDict.values()
                                   if board.IsShow()])
            seen.append(states)
        self.assertEqual(seen[1], seen[0])
        self.assertEqual(seen[0][1], ["%ddp" % (30 + 9 * 6 + 40 + 15)], "Lionheart, with the counts")

    def test_the_marks_are_the_regions_legacy_mark_box_draws(self):
        legacy, novaui = pair()
        for world in (legacy, novaui):
            with world, quiet():
                world.interface.OnStartGuildWar(1, 2)
                world.interface.OnStartGuildWar(2, 3)
        expected = []
        for box, (filename, index) in legacy.marks.items():
            expected.append(("/" + filename, "%d %d 16 12" % ((index % 32) * 16, (index // 32) * 12)) if filename != "mark/10_-1.tga"
                            else ("", ""))
        module = novaui.module("nui_guild_war")
        entries = list(reversed(module._board.model["boards"]))
        rows = [(row["src"], row["rect"]) for entry in entries for row in entry["rows"]]
        self.assertEqual(rows, [("/mark/10_1.tga", "48 0 16 12"), ("/mark/10_0.tga", "48 12 16 12"),
                                ("/mark/10_0.tga", "48 12 16 12"), ("", "")])
        self.assertEqual(sorted(rows[:3]), sorted(expected[:3]))
        self.assertEqual(module.mark_source(3), ("", ""), "a guild without a mark (-1) shows none")

    def test_wars_stack_newest_on_top_and_legacy_overlaps(self):
        legacy, novaui = pair()
        for world in (legacy, novaui):
            with world, quiet():
                world.interface.OnStartGuildWar(1, 2)
                world.interface.OnStartGuildWar(1, 3)
        positions = {board.position for board in legacy.interface.guildScoreBoardDict.values()}
        self.assertEqual(positions, {(10, 900 - 100)}, "legacy puts every board at one place")
        boards = novaui.module("nui_guild_war")._board.model["boards"]
        self.assertEqual([plain(entry["rows"][1]["text"]) for entry in boards], ["Northwind 0", "Lionheart 0"])
        sheet = read(os.path.join(WINDOWS, "guild-war", "guild-war.rcss"))
        self.assertRegex(sheet, r"\.guild-war__column\s*\{[^}]*gap: 4dp;[^}]*left: 10dp;[^}]*bottom: 50dp;")

    def test_names_are_plain_text_and_hidden_boards_leave_the_column(self):
        world = World(True)
        world.game.modules["guild"].GetGuildName = lambda guild_id: "@ui.OK %d" % guild_id
        with world, quiet():
            world.interface.OnStartGuildWar(1, 2)
            board = world.interface.guildScoreBoardDict[world.module("uiGuild").GetGVGKey(1, 2)]
            self.assertEqual(world.module("nui_guild_war")._board.model["boards"][0]["rows"][0]["text"], "@⁠ui.OK 1 0")
            board.Hide()
            self.assertEqual(world.module("nui_guild_war")._board.model["boards"], [])
            self.assertFalse(board.IsShow())
            board.Show()
            self.assertEqual(len(world.module("nui_guild_war")._board.model["boards"]), 1)


# --- fixtures, documents and rules ---------------------------------------------------------------------

def fixture(window, variant=None):
    name = "%s%s.fixture.json" % (window, "." + variant if variant else "")
    return json.loads(read(os.path.join(WINDOWS, window, name)))


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
        self.world = World(True)
        self.world.__enter__()
        self.addCleanup(self.world.__exit__)

    def check(self, board, window, variants=()):
        model = board.initial_model()
        for variant in (None,) + tuple(variants):
            values = fixture(window, variant)[type(board).MODEL]
            self.assertEqual(set(values), set(model), "%s %s: the fixture holds every model key" % (window, variant))
            for key, value in values.items():
                self.assertEqual(kind(value), kind(model[key]), "%s.%s" % (window, key))
            self.assertTrue(board.set(**values))
        self.assertEqual(self.world.game.dbg.errors, [])
        return board

    def test_the_minimap_and_atlas_fixtures_match_their_models(self):
        self.check(self.world.module("nui_minimap").MiniMapBoard(object()), "minimap", ("closed", "observers"))
        self.check(self.world.module("nui_atlas").AtlasBoard(object()), "atlas")
        self.assertFalse(fixture("minimap", "closed")["minimap"]["open"])
        self.assertEqual(fixture("minimap", "observers")["minimap"]["observers"], 3)

    def test_the_gauge_fixture_matches_its_model(self):
        self.check(self.world.module("nui_player_gauge").PlayerGaugeBoard(), "player-gauge")
        self.assertEqual(fixture("player-gauge")["player_gauge"], {"shown": True, "vid": 1, "hp_ratio": 0.42})

    def test_the_sign_fixtures_hold_four_signs_one_own_one_tagged(self):
        self.check(self.world.module("nui_shop_signs").ShopSignBoard(), "shop-signs", ("own-only",))
        signs = fixture("shop-signs")["shop_signs"]["signs"]
        self.assertEqual(len(signs), 4)
        for sign in signs + fixture("shop-signs", "own-only")["shop_signs"]["signs"]:
            self.assertEqual(set(sign), {"vid", "text", "own", "shown", "legacy_width"})
            self.assertEqual(sign["legacy_width"], self.world.module("nui_shop_signs").legacy_width(sign["text"]))
        self.assertEqual(sum(1 for sign in signs if sign["own"]), 1)
        self.assertTrue(any("|c" in sign["text"] for sign in signs))
        self.assertFalse(fixture("shop-signs", "own-only")["shop_signs"]["show_all"])

    def test_the_war_fixtures_use_the_fixture_mark_atlas(self):
        self.check(self.world.module("nui_guild_war").GuildWarBoard(), "guild-war", ("two",))
        boards = fixture("guild-war")["guild_war"]["boards"]
        self.assertEqual(len(boards), 1)
        self.assertEqual(len(fixture("guild-war", "two")["guild_war"]["boards"]), 2)
        rows = boards[0]["rows"]
        self.assertEqual([(row["src"], row["rect"]) for row in rows],
                         [("/nui/windows/guild-war/fixture/marks.tga", "0 0 16 12"),
                          ("/nui/windows/guild-war/fixture/marks.tga", "16 0 16 12")])
        for board in boards + fixture("guild-war", "two")["guild_war"]["boards"]:
            self.assertEqual(set(board), {"key", "rows", "legacy_width"})
            for row in board["rows"]:
                self.assertEqual(set(row), {"src", "rect", "text"})

    def test_the_golden_cases_name_the_stand_ins(self):
        cases = {window: json.loads(read(os.path.join(WINDOWS, window, window + ".snapshots.json")))["cases"]
                 for window in WORLD_WINDOWS}
        self.assertEqual({c.get("variant") for c in cases["minimap"]}, {None, "closed", "observers"})
        self.assertEqual({c.get("variant") for c in cases["shop-signs"]}, {None, "own-only"})
        self.assertEqual({c.get("variant") for c in cases["guild-war"]}, {None, "two"})
        frames = {"minimap": "320x240", "atlas": "640x400", "player-gauge": "320x200", "shop-signs": "960x320",
                  "guild-war": "480x200"}
        for window, window_cases in cases.items():
            for case in window_cases:
                self.assertEqual(case["themes"], "all", window)
                self.assertEqual([row[:2] for row in case["scales"]], [["100", "1"], ["150", "1.5"], ["200", "2"]], window)
                self.assertEqual(case["scales"][0][2], frames[window], window)
        for case in cases["minimap"]:
            self.assertEqual(case["views"], {"minimap": "nui/windows/minimap/minimap.view.png"})
        self.assertEqual(cases["atlas"][0]["views"], {"atlas": "nui/windows/atlas/atlas.view.png"})
        self.assertEqual(cases["player-gauge"][0]["anchors"], {"1": [160, 120]})
        vids = {str(sign["vid"]) for sign in fixture("shop-signs")["shop_signs"]["signs"]}
        for case in cases["shop-signs"]:
            self.assertEqual(set(case["anchors"]), vids)


class StandIns(unittest.TestCase):
    def test_the_committed_stand_ins_are_what_the_generator_makes(self):
        with quiet():
            self.assertEqual(nui_view_fixtures.main(["--check"]), 0)

    def test_the_minimap_disc_is_opaque_to_radius_55_with_a_two_pixel_edge(self):
        width, height, rows = nui_view_fixtures.png_pixels(read_bytes(nui_view_fixtures.MINIMAP))
        self.assertEqual((width, height), (128, 128))
        self.assertEqual(rows[64][64][3], 255)
        self.assertEqual(rows[63][63 - 54][3], 255, "inside radius 55")
        self.assertEqual(rows[63][63 - 58][3], 0, "outside the soft edge")
        self.assertEqual(rows[0][0], (0, 0, 0, 0))
        self.assertTrue(0 < rows[63][63 - 56][3] < 255, "the soft edge")
        colors = {pixel[:3] for row in rows for pixel in row if pixel[3] == 255}
        self.assertEqual(colors, {nui_view_fixtures.GREEN_DARK, nui_view_fixtures.GREEN_LIGHT, nui_view_fixtures.ROAD})

    def test_the_atlas_is_opaque_and_the_marks_are_two_16_by_12_cells(self):
        width, height, rows = nui_view_fixtures.png_pixels(read_bytes(nui_view_fixtures.ATLAS))
        self.assertEqual((width, height), (256, 256))
        self.assertTrue(all(pixel[3] == 255 for row in rows for pixel in row))
        width, height, rows = nui_view_fixtures.tga_pixels(read_bytes(nui_view_fixtures.MARKS))
        self.assertEqual((width, height), (32, 12))
        self.assertTrue(all(pixel[3] == 255 for row in rows for pixel in row))

    def test_no_stand_in_holds_an_opaque_magenta_texel(self):
        for make in (nui_view_fixtures.minimap_pixels, nui_view_fixtures.atlas_pixels, nui_view_fixtures.marks_pixels):
            self.assertEqual(nui_view_fixtures.magenta_texels(make()[2]), 0, make.__name__)

    def test_the_png_reader_takes_every_row_filter(self):
        import zlib
        import struct
        rows = [[(10, 20, 30, 255), (40, 50, 60, 128)], [(70, 80, 90, 255), (100, 110, 120, 0)]]
        for kind_ in (0, 1, 2, 3, 4):
            raw = b""
            previous = bytearray(8)
            for row in rows:
                line = bytearray(channel for pixel in row for channel in pixel)
                encoded = bytearray(line)
                for i in range(8):
                    a = line[i - 4] if i >= 4 else 0
                    b = previous[i]
                    c = previous[i - 4] if i >= 4 else 0
                    if kind_ == 1:
                        encoded[i] = (line[i] - a) & 0xFF
                    elif kind_ == 2:
                        encoded[i] = (line[i] - b) & 0xFF
                    elif kind_ == 3:
                        encoded[i] = (line[i] - (a + b) // 2) & 0xFF
                    elif kind_ == 4:
                        p = a + b - c
                        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                        encoded[i] = (line[i] - (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
                raw += bytes([kind_]) + bytes(encoded)
                previous = line
            png = nui_view_fixtures.png_bytes(2, 2, rows)
            ihdr_end = 8 + 8 + 13 + 4
            body = zlib.compress(raw)
            chunk = struct.pack(">I", len(body)) + b"IDAT" + body + struct.pack(">I", zlib.crc32(b"IDAT" + body) & 0xFFFFFFFF)
            png = png[:ihdr_end] + chunk + png[-12:]
            self.assertEqual(nui_view_fixtures.png_pixels(png), (2, 2, rows), kind_)


class Documents(unittest.TestCase):
    IDS = {
        "minimap": ("minimap", "minimap-view", "minimap-frame", "minimap-scale-up", "minimap-scale-down", "minimap-hide",
                    "minimap-atlas", "minimap-server", "minimap-observers", "minimap-closed", "minimap-show"),
        "atlas": ("atlas", "atlas-title", "atlas-close", "atlas-view"),
        "player-gauge": ("player-gauge-anchor", "player-gauge"),
        "guild-war": ("guild-war",),
    }

    def test_every_document_id_the_spec_names_exists(self):
        for window, ids in self.IDS.items():
            document = read(os.path.join(WINDOWS, window, window + ".rml"))
            for element_id in ids:
                self.assertIn('id="%s"' % element_id, document, "%s#%s" % (window, element_id))
        self.assertIn('<nui-view id="minimap-view" name="minimap" class="minimap__view nui-fx nui-interactive"/>',
                      read(os.path.join(WINDOWS, "minimap", "minimap.rml")))
        self.assertIn('<nui-view id="atlas-view" name="atlas" class="atlas__view nui-interactive"/>',
                      read(os.path.join(WINDOWS, "atlas", "atlas.rml")))

    def test_every_body_draws_below_the_legacy_ui_layer_and_takes_no_focus(self):
        overlays = ("minimap", "player-gauge", "shop-signs", "guild-war")
        for window in WORLD_WINDOWS:
            body = re.search(r"<body[^>]*\bclass=\"([^\"]*)\"", read(os.path.join(WINDOWS, window, window + ".rml"))).group(1).split()
            self.assertIn("nui-below-legacy-ui", body, window)
            self.assertIn("nui-overlay" if window in overlays else "nui-window", body, window)
            self.assertNotIn("nui-field-passes-hotkeys", body, window)
            self.assertRegex(read(os.path.join(WINDOWS, window, window + ".rcss")), r"body\.%s\s*\{[^}]*focus: none;" % window,
                             window)

    def test_every_data_event_has_a_handler_and_every_bound_key_is_in_the_model(self):
        world = World(True)
        boards = {"minimap": world.module("nui_minimap").MiniMapBoard, "atlas": world.module("nui_atlas").AtlasBoard,
                  "player-gauge": world.module("nui_player_gauge").PlayerGaugeBoard,
                  "shop-signs": world.module("nui_shop_signs").ShopSignBoard,
                  "guild-war": world.module("nui_guild_war").GuildWarBoard}
        for window, board in boards.items():
            document = read(os.path.join(WINDOWS, window, window + ".rml"))
            events = set(re.findall(r'data-event-\w+="(\w+)\(', document))
            handled = {name for attr in vars(board).values() for name in getattr(attr, "_nui_events", ())}
            self.assertEqual(events, handled, window)
            self.assertIn('data-model="%s"' % board.MODEL, document, window)

    def test_each_window_has_its_classic_overlay_and_no_skin_rule_of_its_own(self):
        for window in WORLD_WINDOWS:
            self.assertTrue(os.path.isfile(os.path.join(CLASSIC_WINDOWS, window + ".rcss")), window)
            for name in os.listdir(os.path.join(WINDOWS, window)):
                if name.endswith((".rcss", ".rml")):
                    self.assertNotIn("skin-classic", read(os.path.join(WINDOWS, window, name)), name)
            overlay = read(os.path.join(CLASSIC_WINDOWS, window + ".rcss"))
            self.assertNotRegex(overlay, r"#[a-z][\w-]*\s*[{,]", "%s: no ids in classic rules" % window)
            for selector in re.findall(r"^([^\s/@{}][^{]*)\{", overlay, re.M):
                for part in selector.split(","):
                    self.assertTrue(part.strip().startswith("body.skin-classic.%s" % window), "%s: %s" % (window, part))

    def test_classic_places_the_parts_where_legacy_does(self):
        minimap = read(os.path.join(CLASSIC_WINDOWS, "minimap.rcss"))
        for part, left, top in (("view", 4, 5), ("button--atlas", 12, 12), ("button--hide", 111, 6),
                                ("button--down", 115, 103), ("button--up", 101, 116), ("show", 100, 4)):
            self.assertRegex(minimap, r"\.minimap__%s\s*\{[^}]*left: %ddp;\s*top: %ddp;" % (part, left, top), part)
        self.assertRegex(read(os.path.join(CLASSIC_WINDOWS, "atlas.rcss")), r"margin-left: -402dp;")
        self.assertRegex(read(os.path.join(CLASSIC_WINDOWS, "guild-war.rcss")), r"height: 50dp;")
        self.assertRegex(read(os.path.join(CLASSIC_WINDOWS, "shop-signs.rcss")), r"height: 32dp;")


class NoPerFramePython(unittest.TestCase):
    def test_no_world_module_defines_a_per_frame_hook(self):
        for name in WORLD_MODULES:
            tree = ast.parse(read(os.path.join(ROOT, name + ".py")))
            defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
            self.assertEqual(defined & {"OnUpdate", "OnRender", "OnMouseOverIn"}, set(), name)


class Layers(unittest.TestCase):
    def test_the_legacy_windows_live_in_the_game_ui_bottom_and_ui_layers(self):
        """Each legacy window draws below the legacy UI layer's later windows
        (P10 spec D17): the gauge is a child of the game window, the signs are
        UI_BOTTOM, the minimap, atlas and war boards UI (the default)."""
        self.assertIn('ui.ThinBoard.__init__(self, "UI_BOTTOM")', read(os.path.join(ROOT, "uiprivateshopbuilder.py")))
        self.assertIn("self.SetParent(parent)", read(os.path.join(ROOT, "uiplayergauge.py")))
        for file_name, class_name in (("uiminimap.py", "MiniMap"), ("uiminimap.py", "AtlasWindow"),
                                      ("uiguild.py", "GuildWarScoreBoard")):
            tree = ast.parse(read(os.path.join(ROOT, file_name)))
            node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
            init = next(item for item in node.body if isinstance(item, ast.FunctionDef) and item.name == "__init__")
            layers = [call for call in ast.walk(init) if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                      and call.func.attr == "__init__" and len(call.args) >= 2]
            self.assertEqual(layers, [], "%s: the default layer, UI" % class_name)


if __name__ == "__main__":
    unittest.main()
