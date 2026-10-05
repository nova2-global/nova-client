#!/usr/bin/env python3
"""Checks or regenerates the NovaUI snapshot goldens in docs/ui/snapshots/.

    python3 tools/check_nui_snapshots.py            # compare every golden (exit 1 on any mismatch)
    python3 tools/check_nui_snapshots.py --write    # regenerate every golden
    python3 tools/check_nui_snapshots.py --only login --tolerance 0
    python3 tools/check_nui_snapshots.py --write --optimize --only dialog-question

Run it from anywhere; it works in the asset repository root and passes
nuitool relative paths, so a Windows nuitool.exe started from WSL works too.
nuitool comes from --nuitool, else the NUITOOL environment variable, else
PATH. The goldens are the table PAGES below (the pages that have no window
folder of their own case file) plus the cases each window declares in
assets/nui/nui/windows/<name>/<name>.snapshots.json, which the checker
discovers: their page, themes, scales, frame sizes, fixture, extra roots and
time (docs/ui/snapshots/README.md explains each). A golden's file name holds the
theme's short name (dark, light, classic); nuitool gets its id from
nui/theme/themes.json (modern-dark, modern-light, classic), which needs a
nuitool that takes theme ids.

A check runs every case, even after a mismatch, lists every mismatch with
nuitool's own report, and leaves the snapshots and diff images of the
mismatches in a folder it names. RmlUi warnings (nuitool's "rmlui:" lines)
are listed too; a regeneration should print none.

The switched cases (SWITCHED) have no golden of their own: each snaps a
golden's page after a run-time theme switch (nuitool snap --switch-from,
settled in another theme, then one update in the golden's theme) and
compares it with that golden, so a switch must render exactly what a start
in that theme renders. --write writes the goldens first, then checks these.

--optimize re-saves every PNG --write wrote with Pillow's optimizer (when
Pillow is installed); a comparison decodes pixels, so it matches the same.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOTS = os.path.join("docs", "ui", "snapshots")
BASE_ROOTS = ["assets/nui", "assets/icon"]
LOCALE = ["--locale", "assets/locale/locale/en"]
# Extra --root values a case may add: legacy art under d:/ymir work/ (ETC, and
# the loading screens in uiloading), locale art, item icons.
EXTRA_ROOTS = ("assets/ETC", "assets/locale", "assets/uiloading", "assets/icon")
WINDOWS = os.path.join("assets", "nui", "nui", "windows")

# (name in the file name, theme id)
THEMES = (("dark", "modern-dark"), ("light", "modern-light"), ("classic", "classic"))
FULL_SCREEN = [("100", "1", "1920x1080"), ("150", "1.5", "2880x1620"), ("200", "2", "3840x2160")]

# (page, document, fixture or None, theme names, [(percent, --scale, --size)], extra roots, --time or None).
# The gallery shows the classic gauge, whose art is under d:/ymir work/.
PAGES = [
    ("gallery", "nui/windows/gallery/gallery.rml", "assets/nui/nui/windows/gallery/gallery.fixture.json",
     ("dark", "light", "classic"), FULL_SCREEN, ("assets/ETC",), None),
    ("render-test", "nui/windows/render-test/render-test.rml", None,
     ("dark", "light"), [("100", "1", "1280x720"), ("150", "1.5", "1920x1080"), ("200", "2", "2560x1440")], (), None),
    ("login", "nui/windows/login/login.rml", "assets/nui/nui/windows/login/login.fixture.json",
     ("dark", "light", "classic"), FULL_SCREEN, (), None),
    ("theme-picker", "nui/windows/theme-picker/theme-picker.rml", "assets/nui/nui/windows/theme-picker/theme-picker.fixture.json",
     ("dark", "light", "classic"), [("100", "1", "640x360")], (), None),
    ("skin-proof", "nui/windows/skin-proof/skin-proof.rml", None,
     ("classic",), [("100", "1", "640x360"), ("150", "1.5", "960x540"), ("200", "2", "1280x720")], (), None),
]


def window_pages(root=None):
    """PAGES entries from every assets/nui/nui/windows/<name>/<name>.snapshots.json,
    in folder order. ValueError for a case file that breaks its rules: a page
    other than its folder name, an unknown theme or root, a bad scale row."""
    root = root or os.getcwd()
    theme_names = dict(THEMES)
    pages = []
    for path in sorted(glob.glob(os.path.join(root, WINDOWS, "*", "*.snapshots.json"))):
        folder = os.path.basename(os.path.dirname(path))
        if os.path.basename(path) != folder + ".snapshots.json":
            raise ValueError("%s: a case file is named after its folder" % path)
        with open(path, encoding="utf-8") as file:
            cases = json.load(file).get("cases", [])
        for case in cases:
            where = "%s: %r" % (os.path.relpath(path, root), case.get("page"))
            if case.get("page") != folder:
                raise ValueError("%s: page must be the folder name %r" % (where, folder))
            themes = tuple(case.get("themes", ()))
            if not themes or any(theme not in theme_names for theme in themes):
                raise ValueError("%s: themes are among %s" % (where, ", ".join(theme_names)))
            scales = [tuple(row) for row in case.get("scales", ())]
            if not scales or any(len(row) != 3 or not all(isinstance(item, str) for item in row) for row in scales):
                raise ValueError("%s: scales are [percent, --scale, --size] rows of strings" % where)
            roots = tuple(case.get("roots", ()))
            if any(extra not in EXTRA_ROOTS for extra in roots):
                raise ValueError("%s: roots are among %s" % (where, ", ".join(EXTRA_ROOTS)))
            time = case.get("time")
            if time is not None and not isinstance(time, (int, float)):
                raise ValueError("%s: time is a number of seconds or null" % where)
            document = "nui/windows/%s/%s.rml" % (folder, folder)
            fixture = ("assets/nui/nui/windows/%s/%s.fixture.json" % (folder, folder)) if case.get("fixture") else None
            pages.append((folder, document, fixture, themes, scales, roots, time))
    return pages


# (golden, the theme the page settles in before the switch): a skin switch
# onto classic over the login board's transitioning buttons and fields, one
# away from classic, one onto the 2x classic art, a skin switch of the
# gallery and a palette-only switch.
SWITCHED = [
    ("login-classic-100", "dark"),
    ("login-dark-150", "classic"),
    ("skin-proof-classic-200", "light"),
    ("gallery-light-100", "classic"),
    ("gallery-dark-100", "light"),
]


def cases():
    """(case name, golden name, document, fixture or None, theme id, --scale, --size, reduced motion,
    extra roots, --time or None, --switch-from theme id or None); the goldens first, then the
    switched cases."""
    theme_ids = dict(THEMES)
    goldens = []
    for page, document, fixture, themes, scales, roots, time in PAGES + window_pages():
        for theme in themes:
            for percent, scale, size in scales:
                goldens.append((f"{page}-{theme}-{percent}", document, fixture, theme_ids[theme], scale, size, False, roots, time))
    # Reduced motion renders the resting state, which at the default --time 1
    # is the settled frame: the board's open animation has finished.
    goldens.append(("login-dark-100-reduced-motion", "nui/windows/login/login.rml", "assets/nui/nui/windows/login/login.fixture.json",
                    "modern-dark", "1", "1920x1080", True, (), None))
    for golden in goldens:
        yield (golden[0],) + golden + (None,)
    by_name = {golden[0]: golden for golden in goldens}
    for name, source in SWITCHED:
        yield (f"{name}-from-{source}",) + by_name[name] + (theme_ids[source],)


def command(nuitool, case, out, compare=None, tolerance=None):
    _, _, document, fixture, theme, scale, size, reduced, roots, time, switch_from = case
    root_args = []
    for root in BASE_ROOTS + [extra for extra in roots if extra not in BASE_ROOTS]:
        root_args += ["--root", root]
    cmd = [nuitool, "snap"] + root_args + LOCALE + ["--doc", document, "--theme", theme, "--scale", scale, "--size", size, "--out", out]
    if time is not None:
        cmd += ["--time", str(time)]
    if switch_from:
        cmd += ["--switch-from", switch_from]
    if fixture:
        cmd += ["--fixture", fixture]
    if reduced:
        cmd.append("--reduced-motion")
    if compare:
        cmd += ["--compare", compare, "--tolerance", str(tolerance)]
    return cmd


def optimize(path):
    """Re-saves a PNG with Pillow's optimizer; the pixels stay the same."""
    try:
        from PIL import Image
    except ImportError:
        print("check_nui_snapshots: --optimize needs Pillow; left as written", file=sys.stderr)
        return
    with Image.open(path) as image:
        image.load()
        copy = image.copy()
    copy.save(path, optimize=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--write", action="store_true", help="regenerate the goldens instead of comparing")
    parser.add_argument("--nuitool", default=os.environ.get("NUITOOL", "nuitool"), help="nuitool to run (default: $NUITOOL or nuitool on PATH)")
    parser.add_argument("--tolerance", type=int, default=1,
                        help="allowed difference per channel when comparing (default 1: builds for other platforms differ by 1 in a few pixels)")
    parser.add_argument("--only", default="", help="only the goldens whose name contains this text")
    parser.add_argument("--optimize", action="store_true",
                        help="with --write: re-save each written PNG with Pillow's optimizer (needs Pillow)")
    args = parser.parse_args(argv)

    os.chdir(ROOT)
    if shutil.which(args.nuitool) is None and not os.path.isfile(args.nuitool):
        print(f"check_nui_snapshots: nuitool not found: {args.nuitool} (pass --nuitool or set NUITOOL)", file=sys.stderr)
        return 2
    try:
        selected = [c for c in cases() if args.only in c[0]]
    except ValueError as error:
        print(f"check_nui_snapshots: {error}", file=sys.stderr)
        return 2
    if not selected:
        print(f"check_nui_snapshots: no golden matches '{args.only}'", file=sys.stderr)
        return 2

    switched = any(case[-1] for case in selected)
    work = None if args.write and not switched else os.path.relpath(tempfile.mkdtemp(prefix=".snapshot-check-", dir=ROOT), ROOT)
    failed, warned = [], []
    for case in selected:
        name, golden_name = case[0], case[1]
        golden = os.path.join(SNAPSHOTS, golden_name + ".png")
        if args.write and not case[-1]:
            cmd = command(args.nuitool, case, golden)
        else:
            cmd = command(args.nuitool, case, os.path.join(work, name + ".png"), golden, args.tolerance)
        result = subprocess.run(cmd, capture_output=True, text=True)
        warnings = [line for line in result.stderr.splitlines() if line.startswith("rmlui:")]
        if warnings:
            warned.append((name, warnings))
        if result.returncode == 0:
            if args.write and not case[-1] and args.optimize:
                optimize(golden)
            print(f"ok    {name}")
            continue
        failed.append(name)
        print(f"FAIL  {name}")
        for line in (result.stdout + result.stderr).splitlines():
            if line.startswith("nuitool"):
                print(f"      {line}")

    for name, warnings in warned:
        print(f"RmlUi reported problems for {name}:")
        for line in warnings:
            print(f"      {line}")
    if work and not failed:
        shutil.rmtree(work, ignore_errors=True)
    goldens = [case for case in selected if not case[-1]]
    action = "written" if args.write else f"matching within {args.tolerance}"
    summary = f"{len(goldens) - len([g for g in goldens if g[0] in failed])} of {len(goldens)} goldens {action}"
    if switched:
        checks = [case for case in selected if case[-1]]
        summary += f", {len(checks) - len([c for c in checks if c[0] in failed])} of {len(checks)} switched snapshots matching within {args.tolerance}"
    print(summary + (f"; snapshots and diffs in {work}" if work and failed else ""))
    return 1 if failed or (args.write and warned) else 0


if __name__ == "__main__":
    sys.exit(main())
