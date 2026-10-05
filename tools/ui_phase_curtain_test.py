"""Tests for the time-based fade of assets/root/uiphasecurtain.py:
python3 -B -m unittest ui_phase_curtain_test (from tools/). Plain CPython;
app, grp, ui and wndMgr are stand-ins, and app.GetTime is a clock the test
moves."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_test_support as support  # noqa: E402


class Clock(object):
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def make_ui():
    ui = types.ModuleType("ui")

    class Bar(object):
        def __init__(self, layer="UI"):
            self.layer = layer
            self.shown = False
            self.colors = []

        def __del__(self):
            pass

        def SetWindowName(self, name):
            self.name = name

        def AddFlag(self, flag):
            pass

        def Show(self):
            self.shown = True

        def Hide(self):
            self.shown = False

        def SetSize(self, width, height):
            pass

        def SetColor(self, color):
            self.colors.append(color)

    class mem_func(object):
        def __init__(self, fn):
            self.fn = fn

        def __call__(self, *args):
            return self.fn(*args)

    ui.Bar = Bar
    setattr(ui, "__mem_func__", mem_func)
    return ui


class CurtainTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        app = support.stub_module("app", GetTime=self.clock)
        grp = support.stub_module("grp", GenerateColor=lambda r, g, b, a: (r, g, b, a))
        self.modules = support.Modules(app=app, grp=grp, ui=make_ui(), wndMgr=support.make_wndmgr())
        self.addCleanup(self.modules.restore)
        self.m = self.modules.load("uiPhaseCurtain", "uiphasecurtain.py")
        self.m.print = lambda *args, **kwargs: None  # its NEW and DELETE banners
        self.curtain = self.m.PhaseCurtain()
        self.events = []

    def fade_out(self, hz, limit=1000):
        """Fades out at `hz` updates per second; the seconds until the event."""
        start = self.clock.now
        self.curtain.FadeOut(lambda: self.events.append(self.clock.now))
        for _ in range(limit):
            self.clock.now += 1.0 / hz
            self.curtain.OnUpdate()
            if self.events:
                return self.events[0] - start
        self.fail("the curtain never turned black")

    def test_a_fade_out_takes_a_sixth_of_a_second_at_any_frame_rate(self):
        for hz in (30, 60, 144):
            self.events = []
            seconds = self.fade_out(hz)
            self.assertAlmostEqual(seconds, 1.0 / 6.0, delta=1.0 / hz + 1e-9, msg="%d Hz" % hz)

    def test_the_event_runs_once_when_the_curtain_is_black(self):
        self.fade_out(60)
        self.assertEqual(self.curtain.curAlpha, 1.0)
        for _ in range(20):
            self.clock.now += 1.0 / 60
            self.curtain.OnUpdate()
        self.assertEqual(len(self.events), 1)

    def test_the_event_gets_its_argument(self):
        seen = []
        self.curtain.FadeOut(seen.append, 7)
        for _ in range(30):
            self.clock.now += 1.0 / 60
            self.curtain.OnUpdate()
        self.assertEqual(seen, [7])

    def test_a_long_frame_advances_the_fade_by_at_most_fifty_milliseconds(self):
        self.curtain.FadeOut(lambda: self.events.append(True))
        self.clock.now += 2.0  # a phase being built
        self.curtain.OnUpdate()
        self.assertAlmostEqual(self.curtain.curAlpha, 0.1 * 0.05 * 60, places=9)
        self.assertEqual(self.events, [])
        # The fade-in after a long Open still shows: FadeIn restarts the clock.
        self.curtain.curAlpha = 1.0
        self.curtain.FadeIn()
        self.clock.now += 1.0 / 60
        self.curtain.OnUpdate()
        self.assertAlmostEqual(self.curtain.curAlpha, 0.9, places=9)

    def test_a_fade_in_hides_the_curtain_when_it_is_clear(self):
        self.curtain.Show()
        self.curtain.curAlpha = 1.0
        self.curtain.FadeIn()
        for _ in range(12):
            self.clock.now += 1.0 / 60
            self.curtain.OnUpdate()
        self.assertEqual(self.curtain.curAlpha, 0.0)
        self.assertFalse(self.curtain.shown)
        self.assertFalse(self.curtain.FadeInFlag)

    def test_speed_keeps_its_unit_for_the_day_curtain(self):
        # game.py sets speed = 0.03 for the day/night curtain: alpha per 1/60 s.
        self.curtain.speed = 0.03
        for hz in (30, 60, 144):
            self.events = []
            seconds = self.fade_out(hz)
            self.assertAlmostEqual(seconds, 1.0 / (0.03 * 60), delta=1.0 / hz + 1e-9, msg="%d Hz" % hz)


if __name__ == "__main__":
    unittest.main()
