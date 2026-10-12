#!/usr/bin/env python3
"""Checks or regenerates the NovaUI snapshot goldens in docs/ui/snapshots/.

    python3 tools/check_nui_snapshots.py            # compare every golden (exit 1 on any mismatch)
    python3 tools/check_nui_snapshots.py --write    # regenerate every golden
    python3 tools/check_nui_snapshots.py --only login --tolerance 0
    python3 tools/check_nui_snapshots.py --write --optimize --only dialog-question
    python3 tools/check_nui_snapshots.py --write --optimize --only=-ember-   # one theme's goldens

Run it from anywhere; it works in the asset repository root and passes
nuitool relative paths, so a Windows nuitool.exe started from WSL works too.
nuitool comes from --nuitool, else the NUITOOL environment variable, else
PATH. The goldens are the table PAGES below (the pages that have no window
folder of their own case file) plus the cases each window declares in
assets/nui/nui/windows/<name>/<name>.snapshots.json, which the checker
discovers: their page, themes, scales, frame sizes, fixture, extra roots and
time, an optional variant: a second fixture of the same window,
<name>.<variant>.fixture.json, whose goldens are <name>-<variant>-<theme>-
<percent>.png, and the stand-ins of the engine's C++ side: "feeds" (feed
name to a JSON file, nuitool snap --feed), "views" (view name to a PNG,
--view) and "anchors" (a character vid to [x, y] dp, --anchor); their
paths are store paths under assets/nui, as --doc takes them
(docs/ui/snapshots/README.md explains each). The player's settings of a
case (P13 spec 7.8): "colors" (slot=value,... for the theme of the run,
--colors), "backdrop" (a PNG of this repository the frame starts from,
--backdrop), "effects" ("on", the default, "reduced": --reduced-effects,
"off": --no-effects), "reduced_motion" (true: --reduced-motion) and
"switch_from" (a theme's short name: the page settles there and switches,
--switch-from). A case that differs from another by its settings only
gives itself a "name": its goldens are <page>[-<variant>]-<name>-<theme>-
<percent>.png. Each skin may keep cases of its own, for any window, in
assets/nui/nui/skins/<skin>/snapshots.json, which the checker reads too
(a new skin's extra cases need no window's case file). A golden's file name holds the
theme's short name (dark, light, classic); nuitool gets its id from
nui/theme/themes.json (modern-dark, modern-light, classic), which needs a
nuitool that takes theme ids.

docs/ui/snapshots/golden-themes.json maps the short names to the ids and
sets the golden policy: a case's themes are a list of short names or "all",
every shipped theme; an experimental theme ("experimental": true) is only
in the gallery and the pages it names. Every theme of nui/theme/themes.json
needs an entry there.

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
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOTS = os.path.join("docs", "ui", "snapshots")
BASE_ROOTS = ["assets/nui", "assets/icon"]
LOCALE = ["--locale", "assets/locale/locale/en"]
# Extra --root values a case may add: legacy art under d:/ymir work/ (ETC, and
# the loading screens in uiloading), locale art, item icons, the season1 group
# (season1/interface/...: the big notice board's frame) and the patch groups
# that hold the HUD art under d:/ymir work/ (the energy bar in
# metin2_patch_eu4, the gift icon in metin2_patch_etc, the dragon soul button
# in metin2_patch_ds).
EXTRA_ROOTS = ("assets/ETC", "assets/locale", "assets/uiloading", "assets/icon", "assets/season1",
               "assets/metin2_patch_eu4", "assets/metin2_patch_etc", "assets/metin2_patch_ds")
WINDOWS = os.path.join("assets", "nui", "nui", "windows")
GOLDEN_THEMES = os.path.join("docs", "ui", "snapshots", "golden-themes.json")
PLAYER_THEMES = os.path.join("assets", "nui", "nui", "theme", "themes.json")
SHORT_NAME_RE = re.compile(r"[a-z][a-z0-9]*")
# The pages an experimental theme always gets, before the ones it names.
EXPERIMENTAL_PAGES = ("gallery",)
FULL_SCREEN = [("100", "1", "1920x1080"), ("150", "1.5", "2880x1620"), ("200", "2", "3840x2160")]

# (page, document, fixture or None, theme names, [(percent, --scale, --size)], extra roots, --time or None,
# stand-in arguments: --feed, --view and --anchor). The gallery shows the classic gauge, whose art is under
# d:/ymir work/.
PAGES = [
    ("gallery", "nui/windows/gallery/gallery.rml", "assets/nui/nui/windows/gallery/gallery.fixture.json",
     "all", FULL_SCREEN, ("assets/ETC",), None, ()),
    ("render-test", "nui/windows/render-test/render-test.rml", None,
     ("dark", "light"), [("100", "1", "1280x720"), ("150", "1.5", "1920x1080"), ("200", "2", "2560x1440")], (), None, ()),
    ("login", "nui/windows/login/login.rml", "assets/nui/nui/windows/login/login.fixture.json",
     "all", FULL_SCREEN, (), None, ()),
    ("theme-picker", "nui/windows/theme-picker/theme-picker.rml", "assets/nui/nui/windows/theme-picker/theme-picker.fixture.json",
     "all", [("100", "1", "640x360")], (), None, ()),
    ("skin-proof", "nui/windows/skin-proof/skin-proof.rml", None,
     ("classic",), [("100", "1", "640x360"), ("150", "1.5", "960x540"), ("200", "2", "1280x720")], (), None, ()),
]
STAND_IN_NAME_RE = re.compile(r"[a-z][a-z0-9_.-]*")
SKINS = os.path.join("assets", "nui", "nui", "skins")
CASE_KEYS = {"$comment", "page", "themes", "scales", "fixture", "roots", "time", "variant", "name", "feeds", "views", "anchors",
             "colors", "backdrop", "effects", "reduced_motion", "switch_from"}
CASE_NAME_RE = re.compile(r"[a-z][a-z0-9-]*")
COLOR_SLOT_VALUE = r"[a-z][a-z0-9-]*=(#[0-9a-fA-F]{6}|[0-9]{1,3})"
COLORS_RE = re.compile(r"%s(,%s)*" % (COLOR_SLOT_VALUE, COLOR_SLOT_VALUE))
EFFECTS = {"on": (), "reduced": ("--reduced-effects",), "off": ("--no-effects",)}


def stand_in_args(case, where, root):
    """The --feed, --view and --anchor arguments of a case's "feeds", "views"
    and "anchors"; ValueError for one out of form or a file that is missing."""
    args = []
    for key, option in (("feeds", "--feed"), ("views", "--view")):
        table = case.get(key, {})
        if not isinstance(table, dict):
            raise ValueError("%s: %s maps a name to a store path under assets/nui" % (where, key))
        for name, path in sorted(table.items()):
            if not isinstance(name, str) or not STAND_IN_NAME_RE.fullmatch(name) or not isinstance(path, str) or not path:
                raise ValueError("%s: %s maps a name to a store path under assets/nui, not %r: %r" % (where, key, name, path))
            if not os.path.isfile(os.path.join(root, "assets", "nui", path)):
                raise ValueError("%s: %s %s: no assets/nui/%s" % (where, key, name, path))
            args += [option, "%s=%s" % (name, path)]
    anchors = case.get("anchors", {})
    if not isinstance(anchors, dict):
        raise ValueError("%s: anchors maps a vid to [x, y] dp" % where)
    for vid, point in sorted(anchors.items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else 0):
        if (not isinstance(vid, str) or not vid.isdigit() or int(vid) < 1 or not isinstance(point, list) or len(point) != 2
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in point)):
            raise ValueError("%s: anchors maps a vid (1 or more) to [x, y] dp, not %r: %r" % (where, vid, point))
        args += ["--anchor", "%s=%s,%s" % (vid, format(point[0], "g"), format(point[1], "g"))]
    return tuple(args)


def setting_args(case, where, root, themes):
    """The --colors, --backdrop, --reduced-effects or --no-effects,
    --reduced-motion and --switch-from arguments of a case's player settings;
    ValueError for one out of form or a backdrop that is missing."""
    args = []
    colors = case.get("colors")
    if colors is not None:
        if not isinstance(colors, str) or not COLORS_RE.fullmatch(colors):
            raise ValueError("%s: colors is slot=value,... (#rrggbb or a percent), not %r" % (where, colors))
        args += ["--colors", colors]
    backdrop = case.get("backdrop")
    if backdrop is not None:
        if not isinstance(backdrop, str) or not backdrop.endswith(".png") or not os.path.isfile(os.path.join(root, backdrop)):
            raise ValueError("%s: backdrop is a PNG of this repository, not %r" % (where, backdrop))
        args += ["--backdrop", backdrop]
    effects = case.get("effects", "on")
    if effects not in EFFECTS:
        raise ValueError("%s: effects is on, reduced or off, not %r" % (where, effects))
    args += list(EFFECTS[effects])
    reduced = case.get("reduced_motion", False)
    if not isinstance(reduced, bool):
        raise ValueError("%s: reduced_motion is true or false" % where)
    if reduced:
        args.append("--reduced-motion")
    switch = case.get("switch_from")
    if switch is not None:
        ids = {theme["name"]: theme["id"] for theme in themes}
        if switch not in ids:
            raise ValueError("%s: switch_from is a theme's short name, not %r" % (where, switch))
        args += ["--switch-from", ids[switch]]
    return tuple(args)


def golden_themes(root=None):
    """[{"name", "id", "experimental", "pages"}] from docs/ui/snapshots/golden-themes.json,
    in file order. ValueError for a file that breaks its rules or does not
    cover nui/theme/themes.json exactly."""
    root = root or os.getcwd()
    path = os.path.join(root, GOLDEN_THEMES)
    with open(path, encoding="utf-8") as file:
        entries = json.load(file).get("themes")
    if not isinstance(entries, list) or not entries:
        raise ValueError("%s: themes is a non-empty list" % GOLDEN_THEMES)
    themes, names, ids = [], set(), set()
    for entry in entries:
        where = "%s: %r" % (GOLDEN_THEMES, entry)
        if not isinstance(entry, dict) or set(entry) - {"name", "id", "experimental", "pages"}:
            raise ValueError("%s: an entry has name, id and, for an experimental theme, experimental and pages" % where)
        name, theme_id = entry.get("name"), entry.get("id")
        if not isinstance(name, str) or not SHORT_NAME_RE.fullmatch(name) or name in names:
            raise ValueError("%s: name is a unique word of lowercase letters and digits" % where)
        if not isinstance(theme_id, str) or theme_id in ids:
            raise ValueError("%s: id is a theme id, once" % where)
        experimental = entry.get("experimental", False)
        pages = entry.get("pages", [])
        if not isinstance(experimental, bool) or not isinstance(pages, list) or not all(isinstance(p, str) for p in pages):
            raise ValueError("%s: experimental is true or false, pages a list of page names" % where)
        if pages and not experimental:
            raise ValueError("%s: only an experimental theme names pages; a shipped one is in every \"all\" case" % where)
        names.add(name)
        ids.add(theme_id)
        themes.append({"name": name, "id": theme_id, "experimental": experimental,
                       "pages": list(EXPERIMENTAL_PAGES) + [p for p in pages if p not in EXPERIMENTAL_PAGES] if experimental else []})
    with open(os.path.join(root, PLAYER_THEMES), encoding="utf-8") as file:
        player = [theme.get("id") for theme in json.load(file).get("themes", [])]
    missing = [theme_id for theme_id in player if theme_id not in ids]
    if missing:
        raise ValueError("%s has no entry for theme %s of %s" % (GOLDEN_THEMES, ", ".join(missing), PLAYER_THEMES))
    unknown = [theme_id for theme_id in ids if theme_id not in player]
    if unknown:
        raise ValueError("%s names theme %s, which %s does not hold" % (GOLDEN_THEMES, ", ".join(sorted(unknown)), PLAYER_THEMES))
    return themes


def case_themes(themes, listed, where):
    """The short names a case's `themes` value stands for: "all" (every
    shipped theme) or a list of short names."""
    names = [theme["name"] for theme in themes]
    if listed == "all":
        return tuple(theme["name"] for theme in themes if not theme["experimental"])
    listed = tuple(listed) if isinstance(listed, (list, tuple)) else ()
    if not listed or any(name not in names for name in listed):
        raise ValueError("%s: themes are \"all\" or among %s" % (where, ", ".join(names)))
    return listed


def window_pages(root=None, themes=None):
    """PAGES entries from every assets/nui/nui/windows/<name>/<name>.snapshots.json,
    in folder order, then from every skin's assets/nui/nui/skins/<skin>/snapshots.json.
    ValueError for a case file that breaks its rules: a page other than its
    folder name (a skin's: other than a window folder), an unknown theme,
    root or key, a bad scale row or setting."""
    root = root or os.getcwd()
    themes = themes if themes is not None else golden_themes(root)
    files = []
    for path in sorted(glob.glob(os.path.join(root, WINDOWS, "*", "*.snapshots.json"))):
        folder = os.path.basename(os.path.dirname(path))
        if os.path.basename(path) != folder + ".snapshots.json":
            raise ValueError("%s: a case file is named after its folder" % path)
        files.append((path, folder))
    files += [(path, None) for path in sorted(glob.glob(os.path.join(root, SKINS, "*", "snapshots.json")))]
    pages = []
    for path, own_folder in files:
        with open(path, encoding="utf-8") as file:
            cases = json.load(file).get("cases", [])
        for case in cases:
            where = "%s: %r" % (os.path.relpath(path, root), case.get("page"))
            unknown = sorted(set(case) - CASE_KEYS) if isinstance(case, dict) else ["(not an object)"]
            if unknown:
                raise ValueError("%s: unknown key %s" % (where, ", ".join(unknown)))
            folder = case.get("page")
            if own_folder is not None and folder != own_folder:
                raise ValueError("%s: page must be the folder name %r" % (where, own_folder))
            if own_folder is None and (not isinstance(folder, str) or not os.path.isfile(os.path.join(root, WINDOWS, folder, folder + ".rml"))):
                raise ValueError("%s: a skin's case names a window folder of assets/nui/nui/windows" % where)
            listed = case_themes(themes, case.get("themes"), where)
            scales = [tuple(row) for row in case.get("scales", ())]
            if not scales or any(len(row) != 3 or not all(isinstance(item, str) for item in row) for row in scales):
                raise ValueError("%s: scales are [percent, --scale, --size] rows of strings" % where)
            roots = tuple(case.get("roots", ()))
            if any(extra not in EXTRA_ROOTS for extra in roots):
                raise ValueError("%s: roots are among %s" % (where, ", ".join(EXTRA_ROOTS)))
            time = case.get("time")
            if time is not None and not isinstance(time, (int, float)):
                raise ValueError("%s: time is a number of seconds or null" % where)
            variant = case.get("variant")
            if variant is not None and (not isinstance(variant, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", variant)):
                raise ValueError("%s: variant is a name of lowercase letters, digits and hyphens" % where)
            if variant is not None and not case.get("fixture"):
                raise ValueError("%s: a variant is a fixture of its own; set fixture to true" % where)
            label = case.get("name")
            if label is not None and (not isinstance(label, str) or not CASE_NAME_RE.fullmatch(label)):
                raise ValueError("%s: name is a word of lowercase letters, digits and hyphens" % where)
            document = "nui/windows/%s/%s.rml" % (folder, folder)
            stem = folder if variant is None else "%s.%s" % (folder, variant)
            fixture = ("assets/nui/nui/windows/%s/%s.fixture.json" % (folder, stem)) if case.get("fixture") else None
            if fixture and not os.path.isfile(os.path.join(root, fixture)):
                raise ValueError("%s: no %s" % (where, fixture))
            name = "-".join(part for part in (folder, variant, label) if part)
            pages.append((name, document, fixture, listed, scales, roots, time,
                          stand_in_args(case, where, root) + setting_args(case, where, root, themes)))
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


def cases(root=None):
    """(case name, golden name, document, fixture or None, theme id, --scale, --size, reduced motion,
    extra roots, --time or None, stand-in arguments, --switch-from theme id or None); the goldens
    first, then the switched cases."""
    themes = golden_themes(root)
    theme_ids = {theme["name"]: theme["id"] for theme in themes}
    pages = [(page, document, fixture, case_themes(themes, listed, page), scales, roots, time, extras)
             for page, document, fixture, listed, scales, roots, time, extras in PAGES] + window_pages(root, themes)
    page_names = {page[0] for page in pages}
    for theme in themes:
        unknown = [page for page in theme["pages"] if page not in page_names]
        if unknown:
            raise ValueError("%s: theme %s names page %s, which has no golden case" % (GOLDEN_THEMES, theme["name"], ", ".join(unknown)))
    goldens = []
    for page, document, fixture, listed, scales, roots, time, extras in pages:
        extra = tuple(theme["name"] for theme in themes if page in theme["pages"] and theme["name"] not in listed)
        for theme in listed + extra:
            for percent, scale, size in scales:
                goldens.append((f"{page}-{theme}-{percent}", document, fixture, theme_ids[theme], scale, size, False, roots, time,
                                extras))
    names = [golden[0] for golden in goldens]
    twice = sorted({name for name in names if names.count(name) > 1})
    if twice:
        raise ValueError("two cases make the golden %s; give one a name" % ", ".join(twice))
    # Reduced motion renders the resting state, which at the default --time 1
    # is the settled frame: the board's open animation has finished.
    goldens.append(("login-dark-100-reduced-motion", "nui/windows/login/login.rml", "assets/nui/nui/windows/login/login.fixture.json",
                    "modern-dark", "1", "1920x1080", True, (), None, ()))
    for golden in goldens:
        yield (golden[0],) + golden + (None,)
    by_name = {golden[0]: golden for golden in goldens}
    for name, source in SWITCHED:
        yield (f"{name}-from-{source}",) + by_name[name] + (theme_ids[source],)


def command(nuitool, case, out, compare=None, tolerance=None):
    _, _, document, fixture, theme, scale, size, reduced, roots, time, extras, switch_from = case
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
    cmd += list(extras)
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


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--write", action="store_true", help="regenerate the goldens instead of comparing")
    parser.add_argument("--nuitool", default=os.environ.get("NUITOOL", "nuitool"), help="nuitool to run (default: $NUITOOL or nuitool on PATH)")
    parser.add_argument("--tolerance", type=int, default=1,
                        help="allowed difference per channel when comparing (default 1: builds for other platforms differ by 1 in a few pixels)")
    parser.add_argument("--only", default="",
                        help="only the goldens whose name contains this text; write a text that starts with '-' as --only=-x-")
    parser.add_argument("--optimize", action="store_true",
                        help="with --write: re-save each written PNG with Pillow's optimizer (needs Pillow)")
    return parser


def main(argv=None):
    args = make_parser().parse_args(argv)

    os.chdir(ROOT)
    if shutil.which(args.nuitool) is None and not os.path.isfile(args.nuitool):
        print(f"check_nui_snapshots: nuitool not found: {args.nuitool} (pass --nuitool or set NUITOOL)", file=sys.stderr)
        return 2
    try:
        selected = [c for c in cases() if args.only in c[0]]
    except (ValueError, OSError) as error:
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
