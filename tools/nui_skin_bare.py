#!/usr/bin/env python3
"""The test-only bare theme: a skin with no rules at all, and its palette.

    python3 tools/nui_skin_bare.py --out DIR [--snap] [--nuitool PATH]

writes DIR/nui/..., a copy of assets/nui/nui with the theme of
tools/fixtures/skin-bare/theme.json added (themes.json, the palette in
tokens.json, tokens.rcss regenerated), and prints the nuitool roots to use
with it: DIR first, then the repository's other groups. With --snap it also
snaps the gallery and three representative windows in the bare theme into
DIR/snaps/ to look at.

The bare skin has no folder and no overlay, so every window shows the stock
components on its modern layout: the fallback a new skin starts from. Its
body class is skin-bare; it is never in the shipped themes.json.
nui_skin_bare_test.py lints and snaps every window in it.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True  # keep __pycache__ out of tools/
import check_nui_snapshots  # noqa: E402
import nui_tokens  # noqa: E402

REPO = os.path.dirname(HERE)
FIXTURE = os.path.join(HERE, "fixtures", "skin-bare", "theme.json")
SOURCE = os.path.join(REPO, "assets", "nui", "nui")
# The lint roots of docs/ui/AUTHORING.md (Tools) after the documents.
GROUPS = ("icon", "ETC", "locale", "uiloading", "season1", "metin2_patch_eu4", "metin2_patch_etc", "metin2_patch_ds")
SCRIPTS = os.path.join(REPO, "assets", "root")
LOCALE = os.path.join(REPO, "assets", "locale", "locale", "en")
# The gallery and three representative windows: a board, a phase window and
# a dialog.
LOOK_PAGES = ("gallery", "login", "select", "dialog-question")


def fixture():
    with open(FIXTURE, encoding="utf-8") as handle:
        return json.load(handle)


def make_root(dest):
    """Writes dest/nui/... (the shipped content plus the bare theme) and
    returns the theme id."""
    spec = fixture()
    theme, palette = spec["theme"], spec["palette"]
    nui = os.path.join(dest, "nui")
    if os.path.exists(nui):
        shutil.rmtree(nui)
    shutil.copytree(SOURCE, nui)
    themes_path = os.path.join(nui, "theme", "themes.json")
    tokens_path = os.path.join(nui, "theme", "tokens.json")
    with open(themes_path, encoding="utf-8") as handle:
        themes_doc = json.load(handle)
    with open(tokens_path, encoding="utf-8") as handle:
        tokens = json.load(handle)
    themes_doc["themes"].append(theme)
    colors = dict(tokens[palette["base"]])
    colors.update(palette["colors"])
    ordered = {}
    for key, value in tokens.items():
        if key == nui_tokens.SKINS:
            ordered[palette["name"]] = colors
        ordered[key] = value
    ordered.setdefault(palette["name"], colors)
    tokens = ordered
    themes = nui_tokens.validate_themes(themes_doc)
    nui_tokens.validate(tokens, themes)
    for path, data in ((themes_path, themes_doc), (tokens_path, tokens)):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent="\t", ensure_ascii=False)
            handle.write("\n")
    with open(os.path.join(nui, "theme", "tokens.rcss"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(nui_tokens.render_rcss(tokens, themes))
    return theme["id"]


def roots(dest, extra=GROUPS):
    """nuitool --root arguments: dest first (it holds the documents and the
    theme table), then the repository's groups."""
    args = ["--root", dest]
    for group in extra:
        args += ["--root", os.path.join(REPO, "assets", group)]
    return args


def lint_command(nuitool, dest):
    return [nuitool, "lint"] + roots(dest) + ["--scripts", SCRIPTS, "--locale", LOCALE]


STAND_IN_OPTIONS = ("--feed", "--view", "--anchor")


def stand_ins_only(arguments):
    """A case's stand-in arguments (--feed, --view, --anchor and their values)
    without its player settings (--colors, --backdrop, --switch-from, the
    effects and motion flags): the bare theme offers no color slots, and a
    settings case snaps the page of another case."""
    out, items = [], list(arguments)
    for index, item in enumerate(items):
        if item in STAND_IN_OPTIONS:
            out += [item, items[index + 1]]
    return tuple(out)


def snap_cases():
    """(page, document, fixture path or None, --scale, --size, groups, --time,
    stand-in arguments) for every golden page at its first scale, the
    variants left out."""
    out, seen = [], set()
    for page, document, fixture_path, _themes, scales, extra, time, stand_ins in (
            check_nui_snapshots.PAGES + check_nui_snapshots.window_pages(REPO)):
        if page in seen or not os.path.isfile(os.path.join(REPO, "assets", "nui", document)):
            continue
        seen.add(page)
        groups = tuple(root.split("/", 1)[1] for root in extra)
        _percent, scale, size = scales[0]
        out.append((page, document, os.path.join(REPO, fixture_path) if fixture_path else None, scale, size, groups, time,
                    stand_ins_only(stand_ins)))
    return out


def snap_command(nuitool, dest, case, theme_id, out):
    page, document, fixture_path, scale, size, groups, time, stand_ins = case
    cmd = [nuitool, "snap"] + roots(dest, tuple(dict.fromkeys(("icon",) + groups))) + [
        "--locale", LOCALE, "--doc", document, "--theme", theme_id, "--scale", scale, "--size", size, "--out", out]
    if fixture_path:
        cmd += ["--fixture", fixture_path]
    if time is not None:
        cmd += ["--time", str(time)]
    # The feed and view files are store paths, which the scratch root holds.
    return cmd + list(stand_ins)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True, help="the folder to write the scratch root (and snaps/) into")
    parser.add_argument("--snap", action="store_true", help="also snap the gallery and three windows in the bare theme")
    parser.add_argument("--nuitool", default=os.environ.get("NUITOOL", "nuitool"), help="nuitool for --snap")
    args = parser.parse_args(argv)
    dest = os.path.abspath(args.out)
    theme_id = make_root(dest)
    print("bare theme %r in %s; roots: %s" % (theme_id, os.path.join(dest, "nui"), " ".join(roots(dest))))
    if not args.snap:
        return 0
    snaps = os.path.join(dest, "snaps")
    os.makedirs(snaps, exist_ok=True)
    status = 0
    for case in snap_cases():
        if case[0] not in LOOK_PAGES:
            continue
        out = os.path.join(snaps, "%s-bare-100.png" % case[0])
        result = subprocess.run(snap_command(args.nuitool, dest, case, theme_id, out), capture_output=True, text=True)
        problems = [line for line in result.stderr.splitlines() if line.startswith("rmlui:")]
        print("%s %s%s" % ("ok  " if result.returncode == 0 and not problems else "FAIL", out, "".join("\n      " + p for p in problems)))
        status = status or result.returncode or (1 if problems else 0)
    return status


if __name__ == "__main__":
    sys.exit(main())
