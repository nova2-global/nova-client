"""Offline hit test: a press on any control of a golden snapshot reaches that
control. For every golden case of tools/check_nui_snapshots.py (each window,
theme and scale, without the switched ones) it runs `nuitool snap --hits`,
which asks RmlUi's own hit test (pointer-events included) about nine points
on a 3 x 3 grid of each control with an id, and fails when another element
takes one of them.

The Wave 3a validation found the case this guards (P11 F2): in classic, a
choice's label overflowing its button by 40dp on both sides took the presses
on the right part of the choice before it, so GPU acted as Apply and the
music list's OK as Cancel. The goldens are pictures and the facade tests call
the handlers directly, so neither saw it. A label that overflows its control
needs pointer-events: none, as legacy's text line takes no pointer.

Needs NUITOOL (or nuitool on PATH) and skips without it.

    cd tools && NUITOOL=<path> python3 -B -m unittest nui_hit_test
"""
import concurrent.futures
import json
import os
import shutil
import subprocess
import tempfile
import unittest

import check_nui_snapshots

NUITOOL = os.environ.get("NUITOOL") or shutil.which("nuitool")
REPO = check_nui_snapshots.ROOT


def hit_cases():
    """The golden cases, without the switched snapshots (the same frames)."""
    return [case for case in check_nui_snapshots.cases(REPO) if not case[-1]]


@unittest.skipUnless(NUITOOL, "set NUITOOL to a nuitool build (or put nuitool on PATH)")
class PressesReachTheirControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.mkdtemp(prefix="nui-hits-")
        cls.results = {}
        cwd = os.getcwd()
        os.chdir(REPO)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(8, os.cpu_count() or 1))) as pool:
                for name, result in pool.map(cls.snap, hit_cases()):
                    cls.results[name] = result
        finally:
            os.chdir(cwd)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, True)

    @classmethod
    def snap(cls, case):
        name = case[0]
        out = os.path.join(cls.work, name + ".png")
        hits = os.path.join(cls.work, name + ".hits.json")
        command = check_nui_snapshots.command(NUITOOL, case, out) + ["--hits", hits]
        process = subprocess.run(command, capture_output=True, text=True)
        if process.returncode != 0:
            return name, (None, process.stdout + process.stderr)
        with open(hits, encoding="utf-8") as handle:
            return name, (json.load(handle), "")

    def test_every_golden_case_was_hit_tested(self):
        self.assertTrue(self.results)
        for name, (hits, output) in sorted(self.results.items()):
            with self.subTest(case=name):
                self.assertIsNotNone(hits, output)

    def test_no_press_on_a_control_reaches_another_element(self):
        for name, (hits, _) in sorted(self.results.items()):
            if hits is None:
                continue
            with self.subTest(case=name):
                taken = {control: entry["taken"] for control, entry in hits.items() if entry["taken"]}
                self.assertEqual(taken, {}, "presses on these controls reach the listed elements instead")

    def test_the_wave_3a_choices_are_covered(self):
        hits, _ = self.results.get("system-options-classic-100", (None, ""))
        self.assertIsNotNone(hits)
        for control in ("so-camera-0", "so-camera-1", "so-fog-0", "so-fog-1", "so-fog-2", "so-tiling-0", "so-tiling-1",
                        "so-tiling-apply"):
            self.assertEqual(hits[control]["own"], hits[control]["points"], control)
        hits, _ = self.results.get("music-list-classic-100", (None, ""))
        self.assertIsNotNone(hits)
        for control in ("music-list-ok", "music-list-cancel", "music-list-refresh"):
            self.assertEqual(hits[control]["own"], hits[control]["points"], control)


@unittest.skipUnless(NUITOOL, "set NUITOOL to a nuitool build (or put nuitool on PATH)")
class TallWindowsKeepToTheScreen(unittest.TestCase):
    """P11 F4: at 200% on a 900 px screen the system options (about 500dp)
    and the help card (about 480dp) were taller than the screen, so a row or
    the help's title and Close were cut. Both keep to the screen now and
    scroll; the classic windows keep legacy's fixed boards."""

    CASES = (("nui/windows/system-options/system-options.rml", "assets/nui/nui/windows/system-options/system-options.fixture.json",
              "", "so-close"),
             ("nui/windows/help/help.rml", None, "help", "help-close"))

    def test_the_system_options_and_the_help_fit_a_short_screen_at_200_percent(self):
        work = tempfile.mkdtemp(prefix="nui-fit-")
        self.addCleanup(shutil.rmtree, work, True)
        for document, fixture, frame_id, close_id in self.CASES:
            for theme in ("modern-dark", "modern-light"):
                for size in ("1600x900", "1280x720"):
                    with self.subTest(document=document, theme=theme, size=size):
                        boxes = os.path.join(work, "boxes.json")
                        command = [NUITOOL, "snap"]
                        for root in check_nui_snapshots.BASE_ROOTS + ["assets/ETC", "assets/locale"]:
                            command += ["--root", root]
                        command += check_nui_snapshots.LOCALE + ["--doc", document, "--theme", theme, "--scale", "2", "--size", size,
                                                                 "--out", os.path.join(work, "out.png"), "--boxes", boxes]
                        if fixture:
                            command += ["--fixture", fixture]
                        process = subprocess.run(command, capture_output=True, text=True, cwd=REPO)
                        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
                        with open(boxes, encoding="utf-8") as handle:
                            box = json.load(handle)
                        height = int(size.split("x")[1])
                        self.assertLessEqual(box[frame_id][3], height, "the window's height")
                        self.assertLessEqual(box[close_id][3], box[frame_id][3])


if __name__ == "__main__":
    unittest.main()
