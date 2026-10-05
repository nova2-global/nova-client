#!/usr/bin/env python3
"""Scaffold a new NovaUI player theme (docs/ui/AUTHORING.md, Adding a theme).

    python3 tools/nui_new_theme.py <id> --base <palette> [--label TEXT] [--palette NAME]
                                   [--skin NAME] [--window NAME ...] [--name SHORT]
                                   [--shipped | --pages PAGE,...] [--root DIR] [--dry-run]

The three kinds of theme:
  a palette only     --skin modern (the default) or another skin that exists
  a component skin   --skin <new name>: also the skin folder nui/skins/<skin>/
                     with a README and <skin>.rcss, linked at the end of nui.rtpl
  layout overrides   --window <window>, once per window: an overlay stub
                     nui/skins/<skin>/windows/<window>.rcss for each

It writes, under the repository root (--root, default this repository):
  assets/nui/nui/theme/tokens.json      the palette (default: the id), a copy of
                                        the --base palette, after the others
  assets/nui/nui/theme/themes.json      the theme, last in menu order, with the
                                        classes skin-<skin> and theme-<palette>
  assets/nui/nui/theme/tokens.rcss      regenerated, as tools/nui_tokens.py does
  docs/ui/AUTHORING.md                  its token table, regenerated
  docs/ui/snapshots/golden-themes.json  the golden entry: experimental (the gallery
                                        plus --pages, default login, select and
                                        dialog-question) unless --shipped, which
                                        puts it in the full matrix

It changes no window or component file. Then edit the palette, write the
skin's rules, run lint and write the goldens; it prints the commands.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True  # keep __pycache__ out of tools/
import check_nui_snapshots  # noqa: E402
import nui_tokens  # noqa: E402

REPO = os.path.dirname(HERE)
NUI = os.path.join("assets", "nui", "nui")
TOKENS_JSON = os.path.join(NUI, "theme", "tokens.json")
THEMES_JSON = os.path.join(NUI, "theme", "themes.json")
TOKENS_RCSS = os.path.join(NUI, "theme", "tokens.rcss")
TEMPLATE = os.path.join(NUI, "nui.rtpl")
AUTHORING_MD = os.path.join("docs", "ui", "AUTHORING.md")
GOLDEN_THEMES = os.path.join("docs", "ui", "snapshots", "golden-themes.json")
MODERN = "modern"
REPRESENTATIVE_PAGES = ("login", "select", "dialog-question")
NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
SHORT_RE = re.compile(r"^[a-z][a-z0-9]*$")
WINDOW_RE = re.compile(r"^[a-z][a-z0-9-]*$")


class ScaffoldError(Exception):
    pass


def read(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8", newline="") as handle:
        return handle.read()


def entry_json(entry):
    """One entry in the one-line style of themes.json and golden-themes.json."""
    return json.dumps(entry, ensure_ascii=False, separators=(", ", ": "))


def append_entry(text, entry, where):
    """`text` with `entry` after the last one-line entry of its "themes" array."""
    match = None
    for match in re.finditer(r"\n(\t\t\{[^\n]*\})(?=\n\t\])", text):
        pass
    if match is None:
        raise ScaffoldError("%s: no one-line theme entries before the closing ']' of \"themes\"" % where)
    return text[:match.end()] + ",\n\t\t" + entry_json(entry) + text[match.end():]


def default_label(theme_id):
    words = theme_id.replace("-", " ")
    return words[:1].upper() + words[1:]


def skin_readme(skin):
    return """# The {skin} skin

Body class `skin-{skin}`: the themes in `nui/theme/themes.json` whose `body`
names it put it on every NovaUI document. Made by `tools/nui_new_theme.py`;
`docs/ui/AUTHORING.md` ("Adding a theme" and "Skins") says how to finish it.

| File | What |
|---|---|
| `{skin}.rcss` | The component rules, linked from `nui/nui.rtpl` |
| `windows/<window>.rcss` | A window's own rules for this skin; the runtime and `nuitool` apply it after the window's sheets, `<window>` being the folder name of `nui/windows/<window>/<window>.rml` |

- Every selector starts with `.skin-{skin}` and takes the exact modern selector it
  overrides behind it, so it is one class heavier and never relies on sheet order.
  A component that can be the `<body>` lists both forms (`.skin-{skin}.nui-window,
  .skin-{skin} .nui-window`).
- No `transition` and no `animation`: a skin changes how things look, not how they
  move.
- Colors come from the palette and from skin tokens (`skins.{skin}` in
  `tokens.json`), lengths in `dp`.
- Nothing here may need a change to a window or component file: a window with no
  overlay here shows the skin's components on its modern layout.
""".format(skin=skin)


def skin_sheet(skin):
    return """/* The {skin} skin's component rules (README.md next to this file). Every
   document links this sheet through nui/nui.rtpl; every rule starts with
   .skin-{skin}, so nothing here applies in a theme of another skin. Take the
   exact modern selector a rule overrides and put .skin-{skin} in front of it.
   No transition and no animation. RmlUi refuses a sheet without a rule, so
   the empty one below stays until the first real one. */
.skin-{skin}
{{
}}
""".format(skin=skin)


def overlay_sheet(skin, window):
    return """/* The {skin} skin's overlay of nui/windows/{window}/{window}.rml. The runtime
   and nuitool apply it after the window's own sheet, {window}.rcss, in every
   theme; every rule starts with .skin-{skin}, so it acts only while a theme of
   this skin is in use (docs/ui/AUTHORING.md, Skins). RmlUi refuses a sheet
   without a rule, so the empty one below stays until the first real one. */
.skin-{skin}
{{
}}
""".format(skin=skin, window=window)


def link_skin(template, skin):
    """nui.rtpl with the skin's sheet linked after the last skin sheet."""
    href = "skins/%s/%s.rcss" % (skin, skin)
    if href in template:
        return template
    links = list(re.finditer(r'[ \t]*<link type="text/rcss" href="skins/[^"]+"/>\n', template))
    if not links:
        raise ScaffoldError("%s: no skin sheet link to add the new one after" % TEMPLATE)
    end = links[-1].end()
    return template[:end] + '\t<link type="text/rcss" href="%s"/>\n' % href + template[end:]


def plan(root, theme_id, base, label=None, palette=None, skin=MODERN, windows=(), name=None,
         shipped=False, pages=None):
    """{repository-relative path: new text} for the theme; ScaffoldError when
    the request breaks a rule. Writes nothing."""
    palette = palette or theme_id
    label = label if label is not None else default_label(theme_id)
    name = name or theme_id.replace("-", "")
    pages = list(REPRESENTATIVE_PAGES if pages is None else pages)

    if not nui_tokens.THEME_ID_RE.match(theme_id):
        raise ScaffoldError("the id is 1 to 31 of [a-z0-9-], got %r" % theme_id)
    for kind, value in (("palette", palette), ("skin", skin)):
        if not NAME_RE.match(value) or not nui_tokens.THEME_CLASS_RE.match(("theme-" if kind == "palette" else "skin-") + value):
            raise ScaffoldError("the %s name is lowercase words joined by '-', got %r" % (kind, value))
    if not SHORT_RE.match(name):
        raise ScaffoldError("the golden name is lowercase letters and digits, got %r (pass --name)" % name)
    if shipped and pages != list(REPRESENTATIVE_PAGES):
        raise ScaffoldError("--pages is for an experimental theme; a shipped one gets every page")

    tokens = json.loads(read(root, TOKENS_JSON))
    themes_text = read(root, THEMES_JSON)
    themes_doc = json.loads(themes_text)
    golden_text = read(root, GOLDEN_THEMES)
    golden = json.loads(golden_text).get("themes", [])
    known = {page[0] for page in check_nui_snapshots.PAGES}
    for page in pages:
        if page not in known and not os.path.isfile(os.path.join(root, NUI, "windows", page, page + ".snapshots.json")):
            raise ScaffoldError("no golden case for page %r (check_nui_snapshots.PAGES or <page>.snapshots.json)" % page)

    if any(theme.get("id") == theme_id for theme in themes_doc.get("themes", [])):
        raise ScaffoldError("themes.json already has a theme %r" % theme_id)
    palettes = nui_tokens.palettes_of(tokens)
    if base not in palettes:
        raise ScaffoldError("tokens.json has no palette %r to copy (it has %s)" % (base, ", ".join(palettes)))
    if palette in palettes or palette in ("shared", nui_tokens.SKINS):
        raise ScaffoldError("tokens.json already has a section %r; pass --palette" % palette)
    if any(entry.get("name") == name for entry in golden):
        raise ScaffoldError("golden-themes.json already uses the name %r; pass --name" % name)

    skin_dir = os.path.join(NUI, "skins", skin)
    new_skin = skin != MODERN and not os.path.isdir(os.path.join(root, skin_dir))
    if windows and skin == MODERN:
        raise ScaffoldError("the modern skin is the windows' own sheets; layout overrides need another skin")
    for window in windows:
        if not WINDOW_RE.match(window) or not os.path.isfile(os.path.join(root, NUI, "windows", window, window + ".rml")):
            raise ScaffoldError("no window %r (nui/windows/<window>/<window>.rml)" % window)
        if os.path.exists(os.path.join(root, skin_dir, "windows", window + ".rcss")):
            raise ScaffoldError("the %s skin already has an overlay of %s" % (skin, window))

    # tokens.json: the copy goes after the last palette, before "skins".
    copied = {}
    for key, value in tokens.items():
        if key == nui_tokens.SKINS and palette not in copied:
            copied[palette] = dict(tokens[base])
        copied[key] = value
    if palette not in copied:
        copied[palette] = dict(tokens[base])
    tokens_text = json.dumps(copied, indent="\t", ensure_ascii=False) + "\n"

    entry = {"id": theme_id, "label": label, "body": ["skin-" + skin, "theme-" + palette]}
    new_themes_text = append_entry(themes_text, entry, THEMES_JSON)
    golden_entry = {"name": name, "id": theme_id}
    if not shipped:
        golden_entry.update({"experimental": True, "pages": pages})
    new_golden_text = append_entry(golden_text, golden_entry, GOLDEN_THEMES)

    try:
        themes = nui_tokens.validate_themes(json.loads(new_themes_text))
        nui_tokens.validate(copied, themes)
    except nui_tokens.TokenError as error:
        raise ScaffoldError(str(error))

    out = {
        TOKENS_JSON: tokens_text,
        THEMES_JSON: new_themes_text,
        TOKENS_RCSS: nui_tokens.render_rcss(copied, themes),
        GOLDEN_THEMES: new_golden_text,
    }
    if os.path.isfile(os.path.join(root, AUTHORING_MD)):
        out[AUTHORING_MD] = nui_tokens.splice_table(read(root, AUTHORING_MD), nui_tokens.render_table(copied, themes))
    if new_skin:
        out[os.path.join(skin_dir, "README.md")] = skin_readme(skin)
        out[os.path.join(skin_dir, skin + ".rcss")] = skin_sheet(skin)
        out[TEMPLATE] = link_skin(read(root, TEMPLATE), skin)
    for window in windows:
        out[os.path.join(skin_dir, "windows", window + ".rcss")] = overlay_sheet(skin, window)
    return out


def write(root, files):
    for rel, text in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)


def next_steps(theme_id, palette, skin, name, shipped, new_skin):
    key = "THEME_" + theme_id.upper().replace("-", "_")
    steps = [
        "Next:",
        "- Set the colors of palette %r in assets/nui/nui/theme/tokens.json, then run python tools/nui_tokens.py (contrast)." % palette,
    ]
    if new_skin:
        steps.append("- Write the skin's component rules in assets/nui/nui/skins/%s/%s.rcss, every one under .skin-%s." % (skin, skin, skin))
    if skin != MODERN:
        steps.append("- Window overrides, if any, go in assets/nui/nui/skins/%s/windows/<window>.rcss." % skin)
    steps += [
        "- The picker shows @ui.%s when the locale has it, else the label; add it to all 17 locale_interface.txt files"
        " and to tools/nui_button_fit.py for a translated label." % key,
        "- nuitool lint --root assets/nui --root assets/icon --root assets/ETC --root assets/locale --root assets/uiloading"
        " --locale assets/locale/locale/en  (it loads every window in every theme)",
        "- python3 tools/check_nui_snapshots.py --write --optimize --only -%s-   (%s)" % (
            name, "the full matrix" if shipped else "experimental: the gallery and the representative pages"),
    ]
    return "\n".join(steps)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("id", help="the theme id, as UI_THEME stores it: 1 to 31 of [a-z0-9-]")
    parser.add_argument("--base", required=True, help="the palette to copy (a top-level palette of tokens.json: dark, light, classic)")
    parser.add_argument("--label", help="the menu label when the locale has no THEME_<ID> key (default: from the id)")
    parser.add_argument("--palette", help="the new palette's name, its class theme-<palette> (default: the id)")
    parser.add_argument("--skin", default=MODERN, help="the skin, its class skin-<skin> (default: modern); a new name makes the skin folder")
    parser.add_argument("--window", action="append", default=[], help="a window to give an overlay stub in the skin (repeatable)")
    parser.add_argument("--name", help="the short name in golden file names (default: the id without hyphens)")
    parser.add_argument("--shipped", action="store_true", help="give the theme the full golden matrix instead of the experimental set")
    parser.add_argument("--pages", help="an experimental theme's representative pages, comma-separated (default: %s), besides the gallery"
                        % ",".join(REPRESENTATIVE_PAGES))
    parser.add_argument("--root", default=REPO, help="the repository root to write into (default: this repository)")
    parser.add_argument("--dry-run", action="store_true", help="list the files it would write and write nothing")
    args = parser.parse_args(argv)

    pages = [page for page in args.pages.split(",") if page] if args.pages is not None else None
    try:
        files = plan(args.root, args.id, args.base, label=args.label, palette=args.palette, skin=args.skin,
                     windows=args.window, name=args.name, shipped=args.shipped, pages=pages)
    except (ScaffoldError, OSError, ValueError) as error:
        print("nui_new_theme: %s" % error, file=sys.stderr)
        return 1
    new_skin = any(rel.endswith("README.md") for rel in files)
    for rel in sorted(files):
        print(("would write " if args.dry_run else "wrote ") + rel.replace(os.sep, "/"))
    if not args.dry_run:
        write(args.root, files)
        print(next_steps(args.id, args.palette or args.id, args.skin, args.name or args.id.replace("-", ""), args.shipped, new_skin))
    return 0


if __name__ == "__main__":
    sys.exit(main())
