"""Tests for snowfall, the FPS counter and tips (NOVA-118): the shared module
assets/root/player_options.py and game.GameWindow's snowfall and tip rules:
python3 -B -m unittest player_options_test (from tools/).

OLD (root/game.py:3362-3383, 2818-2820; uiSystemOption.py:517-571): the
xmas event's snowfall (mode "1") shows only when systemSetting.
IsEnableSnowFall() is on, tips stop while cfg "disable_tip" is "1". NEW
keeps the three flags in CPythonSystem; the option windows set them through
player_options.set_option, which tells game.py and the minimaps.

game.py's methods are compiled from its own source (the compiled() pattern
of game_highlight_test) over recording stand-ins."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_test_support as base  # noqa: E402

PLAYER_OPTIONS = os.path.join(support.ROOT, "player_options.py")


class Setting(types.ModuleType):
    """systemSetting's three NOVA-118 pairs over a dict, every set recorded."""

    def __init__(self, snowfall=False, fps=False, tips=True):
        types.ModuleType.__init__(self, "systemSetting")
        self.flags = {"snow": snowfall, "fps": fps, "tips": tips}
        self.log = []

    def _set(self, key, name, value):
        self.log.append((name, value))
        self.flags[key] = value == 1

    def IsEnableSnowFall(self):
        return int(self.flags["snow"])

    def SetEnableSnowFall(self, value):
        self._set("snow", "SetEnableSnowFall", value)

    def IsShowFPSCounter(self):
        return int(self.flags["fps"])

    def SetShowFPSCounter(self, value):
        self._set("fps", "SetShowFPSCounter", value)

    def IsShowTips(self):
        return int(self.flags["tips"])

    def SetShowTips(self, value):
        self._set("tips", "SetShowTips", value)


def load_player_options(setting):
    saved = sys.modules.get("systemSetting")
    sys.modules["systemSetting"] = setting
    try:
        return base.load_module("player_options", PLAYER_OPTIONS)
    finally:
        if saved is None:
            sys.modules.pop("systemSetting", None)
        else:
            sys.modules["systemSetting"] = saved


class Listener(object):
    def __init__(self):
        self.heard = []

    def OnPlayerOptionChanged(self, name):
        self.heard.append(name)


class SharedModule(unittest.TestCase):
    def test_set_option_sets_oldss_one_or_zero_and_tells_each_listener_once(self):
        setting = Setting()
        module = load_player_options(setting)
        listener = Listener()
        module.listen(listener)
        module.listen(listener)
        module.set_option(module.SNOWFALL, True)
        module.set_option(module.FPS_COUNTER, True)
        module.set_option(module.TIPS, False)
        self.assertEqual(setting.log, [("SetEnableSnowFall", 1), ("SetShowFPSCounter", 1), ("SetShowTips", 0)])
        self.assertEqual(listener.heard, ["snowfall", "fps_counter", "tips"])
        self.assertEqual([module.is_on(name) for name in (module.SNOWFALL, module.FPS_COUNTER, module.TIPS)],
                         [True, True, False])

    def test_a_listener_is_kept_weakly_and_can_be_forgotten(self):
        module = load_player_options(Setting())
        kept, gone = Listener(), Listener()
        module.listen(kept)
        module.listen(gone)
        del gone
        module.set_option(module.TIPS, False)
        self.assertEqual(kept.heard, ["tips"])
        module.forget(kept)
        module.set_option(module.TIPS, True)
        self.assertEqual(kept.heard, ["tips"])

    def test_the_snowfall_shows_only_for_the_event_on_its_map_with_the_player_s_choice(self):
        setting = Setting(snowfall=True)
        module = load_player_options(setting)
        self.assertTrue(module.snowfall_wanted(True, True))
        self.assertFalse(module.snowfall_wanted(False, True))
        self.assertFalse(module.snowfall_wanted(True, False))
        setting.flags["snow"] = False
        self.assertFalse(module.snowfall_wanted(True, True), "the opt-out")

    def test_an_older_exe_without_the_flags_keeps_the_defaults_and_sets_nothing(self):
        module = load_player_options(types.ModuleType("systemSetting"))
        self.assertEqual([module.is_on(name) for name in (module.SNOWFALL, module.FPS_COUNTER, module.TIPS)],
                         [False, False, True])
        listener = Listener()
        module.listen(listener)
        module.set_option(module.SNOWFALL, True)
        self.assertEqual(listener.heard, [])

    def test_the_readout_text_and_interval(self):
        module = load_player_options(Setting())
        self.assertEqual(module.fps_text(59.6), "FPS: 59")
        self.assertEqual(module.FPS_INTERVAL, 1.0)


# --- the frame rate limit (NOVA-214) ----------------------------------------------------------

class FrameRateSetting(types.ModuleType):
    """systemSetting's NOVA-214 API: GetMaxFPS, SetMaxFPS (anything not a
    choice becomes 60) and the constants, every set recorded."""

    def __init__(self, value=60, constants=True):
        types.ModuleType.__init__(self, "systemSetting")
        self.value = value
        self.log = []
        if constants:
            self.MAX_FPS_CHOICES, self.MAX_FPS_UNLIMITED, self.MAX_FPS_VSYNC = (60, 120, 144, 165, 240, 0, -1), 0, -1

    def GetMaxFPS(self):
        return self.value

    def SetMaxFPS(self, value):
        self.log.append(value)
        self.value = value if value in (60, 120, 144, 165, 240, 0, -1) else 60


class FrameRate(unittest.TestCase):
    """The shared rules of the Frame rate row in both system option windows:
    the seven choices in the client's display order, a value's label, reading
    and setting through systemSetting, and an older exe without the API."""

    def test_the_choices_are_the_client_s_seven_in_display_order(self):
        module = load_player_options(FrameRateSetting())
        self.assertEqual(module.max_fps_choices(), (60, 120, 144, 165, 240, 0, -1))
        self.assertEqual((module.MAX_FPS_DEFAULT, module.MAX_FPS_UNLIMITED, module.MAX_FPS_VSYNC), (60, 0, -1))
        self.assertTrue(module.has_max_fps())

    def test_a_value_s_label_is_its_number_or_its_word(self):
        module = load_player_options(FrameRateSetting())
        text = lambda key: "<%s>" % key
        self.assertEqual([module.max_fps_label(value, text) for value in module.max_fps_choices()],
                         ["60", "120", "144", "165", "240", "<OPTION_FRAME_RATE_UNLIMITED>", "<OPTION_FRAME_RATE_VSYNC>"])

    def test_the_value_is_the_client_s_and_a_value_that_is_no_choice_reads_as_60(self):
        setting = FrameRateSetting(144)
        module = load_player_options(setting)
        self.assertEqual(module.max_fps(), 144)
        for value in (-1, 0, 240):
            setting.value = value
            self.assertEqual(module.max_fps(), value)
        for value in (75, -2, 1000):
            setting.value = value
            self.assertEqual(module.max_fps(), 60, value)

    def test_set_max_fps_hands_a_choice_to_the_client_and_refuses_the_rest(self):
        setting = FrameRateSetting()
        module = load_player_options(setting)
        self.assertTrue(module.set_max_fps(0))
        self.assertTrue(module.set_max_fps(-1))
        self.assertFalse(module.set_max_fps(75))
        self.assertFalse(module.set_max_fps("144"))
        self.assertEqual(setting.log, [0, -1])
        self.assertEqual(module.max_fps(), -1)

    def test_a_step_moves_one_choice_and_stops_at_the_ends(self):
        module = load_player_options(FrameRateSetting())
        self.assertEqual(module.max_fps_step(60, 1), 120)
        self.assertEqual(module.max_fps_step(240, 1), 0, "Unlimited after 240")
        self.assertEqual(module.max_fps_step(0, 1), -1, "VSync last")
        self.assertEqual(module.max_fps_step(-1, 1), -1, "no wrap")
        self.assertEqual(module.max_fps_step(60, -1), 60, "no wrap")
        self.assertEqual(module.max_fps_step(-1, -1), 0)
        self.assertEqual(module.max_fps_step(75, 1), 120, "a value that is no choice steps from 60")

    def test_the_constants_default_to_the_documented_ones_when_the_exe_has_only_the_pair(self):
        module = load_player_options(FrameRateSetting(constants=False))
        self.assertTrue(module.has_max_fps())
        self.assertEqual(module.max_fps_choices(), (60, 120, 144, 165, 240, 0, -1))

    def test_an_older_exe_without_the_api_reads_60_and_sets_nothing(self):
        module = load_player_options(types.ModuleType("systemSetting"))
        self.assertFalse(module.has_max_fps())
        self.assertEqual(module.max_fps(), 60)
        self.assertFalse(module.set_max_fps(144))
        self.assertEqual(module.max_fps_choices(), (60, 120, 144, 165, 240, 0, -1))


# --- game.py --------------------------------------------------------------------------------

GAME_METHODS = ("__XMasSnow_Enable", "__RefreshSnow", "__IsXMasMap", "OnPlayerOptionChanged", "BINARY_SetTipMessage")


def compiled_game(namespace):
    source = support.source_of("game.py", GAME_METHODS, inside="GameWindow")
    body = "\n".join("\t" + line if line else line for line in source.split("\n"))
    exec(compile("class GameWindow(object):\n%s\n" % body, "game.py", "exec"), namespace)
    return namespace["GameWindow"]


class Game(unittest.TestCase):
    def window(self, snowfall=False, tips=True, map_name="metin2_map_a1"):
        self.setting = Setting(snowfall=snowfall, tips=tips)
        self.module = load_player_options(self.setting)
        self.snow = []
        self.tips = []
        background = types.SimpleNamespace(EnableSnow=self.snow.append, GetCurrentMapName=lambda: map_name)
        cls = compiled_game({"background": background, "player_options": self.module, "print": lambda *a: None})
        cls._GameWindow__XMasSong_Enable = lambda self, mode: None
        window = cls()
        window.interface = types.SimpleNamespace(tipBoard=types.SimpleNamespace(SetTip=self.tips.append))
        return window

    def test_the_event_s_snowfall_follows_the_player_s_choice(self):
        window = self.window(snowfall=True)
        window._GameWindow__XMasSnow_Enable("1")
        self.assertEqual(self.snow, [1])
        window = self.window(snowfall=False)
        window._GameWindow__XMasSnow_Enable("1")
        self.assertEqual(self.snow, [0], "opted out: as OLD, the snowfall stops")

    def test_the_event_s_end_stops_the_snowfall_whatever_the_choice(self):
        window = self.window(snowfall=True)
        window._GameWindow__XMasSnow_Enable("1")
        window._GameWindow__XMasSnow_Enable("0")
        self.assertEqual(self.snow, [1, 0])

    def test_a_map_without_the_event_shows_none(self):
        window = self.window(snowfall=True, map_name="metin2_map_spiderdungeon")
        window._GameWindow__XMasSnow_Enable("1")
        self.assertEqual(self.snow, [])

    def test_flipping_the_option_during_the_event_starts_and_stops_the_snowfall(self):
        window = self.window(snowfall=False)
        self.module.listen(window)
        window._GameWindow__XMasSnow_Enable("1")
        self.module.set_option(self.module.SNOWFALL, True)
        self.module.set_option(self.module.SNOWFALL, False)
        self.assertEqual(self.snow, [0, 1, 0])

    def test_turning_the_option_on_without_the_event_starts_no_snowfall(self):
        """OLD's option called background.EnableSnow(1) whatever the event."""
        window = self.window(snowfall=False)
        self.module.listen(window)
        self.module.set_option(self.module.SNOWFALL, True)
        window._GameWindow__XMasSnow_Enable("0")
        self.module.set_option(self.module.SNOWFALL, True)
        self.assertNotIn(1, self.snow)

    def test_the_other_options_leave_the_snowfall_alone(self):
        window = self.window(snowfall=True)
        self.module.listen(window)
        window._GameWindow__XMasSnow_Enable("1")
        self.module.set_option(self.module.FPS_COUNTER, True)
        self.module.set_option(self.module.TIPS, False)
        self.assertEqual(self.snow, [1])

    def test_tips_stop_while_the_option_is_off(self):
        window = self.window(tips=True)
        window.BINARY_SetTipMessage("Server restart at 18:00")
        self.module.set_option(self.module.TIPS, False)
        window.BINARY_SetTipMessage("Double drop this weekend")
        self.module.set_option(self.module.TIPS, True)
        window.BINARY_SetTipMessage("Welcome")
        self.assertEqual(self.tips, ["Server restart at 18:00", "Welcome"])

    def test_the_game_window_listens_from_its_constructor(self):
        init = support.source_of("game.py", ("__init__",), inside="GameWindow")
        self.assertIn("player_options.listen(self)", init)
        with open(os.path.join(support.ROOT, "game.py"), encoding="utf-8") as handle:
            self.assertIn("\nimport player_options\n", handle.read())


if __name__ == "__main__":
    unittest.main()
