"""Tests for tools/check_nui_snapshots.py's case keys: the stand-ins (P10 spec
4.3: "feeds", "views" and "anchors" become nuitool snap's --feed, --view and
--anchor), the player settings and names (P13 spec 7.8) and the skins' own
case files: python3 -B -m unittest check_nui_snapshots_test (from tools/).
Plain CPython; nothing is snapped."""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_nui_snapshots  # noqa: E402

REPO = os.path.normpath(os.path.join(HERE, ".."))


class StandIns(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="nui-snap-keys-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        folder = os.path.join(self.root, "assets", "nui", "nui", "windows", "demo")
        os.makedirs(folder)
        for name in ("demo.lines.json", "demo.view.png"):
            with open(os.path.join(folder, name), "w") as handle:
                handle.write("[]")
        with open(os.path.join(folder, "demo.fixture.json"), "w") as handle:
            handle.write("{}")
        with open(os.path.join(folder, "demo.rml"), "w") as handle:
            handle.write("<rml/>")
        for path in (check_nui_snapshots.GOLDEN_THEMES, check_nui_snapshots.PLAYER_THEMES):
            os.makedirs(os.path.dirname(os.path.join(self.root, path)), exist_ok=True)
            shutil.copy(os.path.join(REPO, path), os.path.join(self.root, path))
        self.folder = folder

    def write_case(self, **keys):
        case = {"page": "demo", "themes": ["dark"], "scales": [["100", "1", "320x200"]], "fixture": True, "roots": [], "time": None}
        case.update(keys)
        with open(os.path.join(self.folder, "demo.snapshots.json"), "w") as handle:
            json.dump({"cases": [case]}, handle)

    def test_feeds_views_and_anchors_become_snap_options(self):
        self.write_case(feeds={"chat.window.lines": "nui/windows/demo/demo.lines.json"},
                        views={"minimap": "nui/windows/demo/demo.view.png"},
                        anchors={"12": [160, 120.5], "3": [10, 20]})
        page = check_nui_snapshots.window_pages(self.root)[0]
        self.assertEqual(page[-1], ("--feed", "chat.window.lines=nui/windows/demo/demo.lines.json",
                                    "--view", "minimap=nui/windows/demo/demo.view.png",
                                    "--anchor", "3=10,20", "--anchor", "12=160,120.5"))
        case = next(c for c in check_nui_snapshots.cases(self.root) if c[0] == "demo-dark-100")
        cmd = check_nui_snapshots.command("nuitool", case, "out.png")
        at = cmd.index("--fixture")
        self.assertEqual(cmd[at + 2:at + 10], ["--feed", "chat.window.lines=nui/windows/demo/demo.lines.json",
                                               "--view", "minimap=nui/windows/demo/demo.view.png",
                                               "--anchor", "3=10,20", "--anchor", "12=160,120.5"])

    def test_a_case_without_them_passes_none(self):
        self.write_case()
        self.assertEqual(check_nui_snapshots.window_pages(self.root)[0][-1], ())
        cmd = check_nui_snapshots.command("nuitool", next(iter(check_nui_snapshots.cases(self.root))), "out.png")
        self.assertFalse({"--feed", "--view", "--anchor"} & set(cmd))

    def test_a_key_out_of_form_or_a_missing_file_stops_the_checker(self):
        bad = [{"feeds": {"chat.window.lines": "nui/windows/demo/missing.json"}},
               {"feeds": {"Bad Name": "nui/windows/demo/demo.lines.json"}},
               {"feeds": ["nui/windows/demo/demo.lines.json"]},
               {"views": {"minimap": 3}},
               {"anchors": {"0": [1, 2]}},
               {"anchors": {"x": [1, 2]}},
               {"anchors": {"5": [1]}},
               {"anchors": {"5": [1, True]}}]
        for keys in bad:
            with self.subTest(keys=keys):
                self.write_case(**keys)
                self.assertRaises(ValueError, check_nui_snapshots.window_pages, self.root)

    def test_the_player_settings_become_snap_options_and_a_name_names_the_goldens(self):
        backdrop = os.path.join(self.root, "back.png")
        with open(backdrop, "wb") as handle:
            handle.write(b"png")
        self.write_case(name="tinted", colors="accent=#c58af9,opacity=80", backdrop="back.png", effects="off",
                        reduced_motion=True, switch_from="light")
        page = check_nui_snapshots.window_pages(self.root)[0]
        self.assertEqual(page[0], "demo-tinted")
        self.assertEqual(page[-1], ("--colors", "accent=#c58af9,opacity=80", "--backdrop", "back.png", "--no-effects",
                                    "--reduced-motion", "--switch-from", "modern-light"))
        self.assertEqual([c[0] for c in check_nui_snapshots.cases(self.root) if c[0].startswith("demo")], ["demo-tinted-dark-100"])
        self.write_case(effects="reduced")
        self.assertEqual(check_nui_snapshots.window_pages(self.root)[0][-1], ("--reduced-effects",))

    def test_a_setting_or_key_out_of_form_stops_the_checker(self):
        bad = [{"colors": "accent=red"}, {"colors": "Accent=#ffffff"}, {"backdrop": "missing.png"}, {"effects": "half"},
               {"reduced_motion": 1}, {"switch_from": "modern-light"}, {"name": "Two Words"}, {"colours": "accent=#ffffff"}]
        for keys in bad:
            with self.subTest(keys=keys):
                self.write_case(**keys)
                self.assertRaises(ValueError, lambda: list(check_nui_snapshots.cases(self.root)))

    def test_a_skin_keeps_cases_of_its_own_for_any_window_and_two_cases_may_not_share_a_golden(self):
        self.write_case()
        skin = os.path.join(self.root, "assets", "nui", "nui", "skins", "demo-skin")
        os.makedirs(skin)
        case = {"page": "demo", "name": "calm", "themes": ["dark"], "scales": [["100", "1", "320x200"]], "fixture": True,
                "roots": [], "time": None, "reduced_motion": True}
        with open(os.path.join(skin, "snapshots.json"), "w") as handle:
            json.dump({"cases": [case]}, handle)
        self.assertEqual([c[0] for c in check_nui_snapshots.cases(self.root) if c[0].startswith("demo")],
                         ["demo-dark-100", "demo-calm-dark-100"])
        del case["name"]
        with open(os.path.join(skin, "snapshots.json"), "w") as handle:
            json.dump({"cases": [case]}, handle)
        self.assertRaises(ValueError, lambda: list(check_nui_snapshots.cases(self.root)))
        case.update(page="nowhere", name="calm")
        with open(os.path.join(skin, "snapshots.json"), "w") as handle:
            json.dump({"cases": [case]}, handle)
        self.assertRaises(ValueError, lambda: list(check_nui_snapshots.cases(self.root)))

    def test_the_shipped_chat_cases_pass_their_feeds(self):
        cases = [c for c in check_nui_snapshots.cases(REPO) if c[0].startswith("chat")]
        self.assertTrue(cases)
        for case in cases:
            cmd = check_nui_snapshots.command("nuitool", case, "out.png")
            feed = cmd[cmd.index("--feed") + 1]
            self.assertTrue(feed.startswith("chat.log.lines=" if case[0].startswith("chat-log") else "chat.window.lines="), case[0])


if __name__ == "__main__":
    unittest.main()
