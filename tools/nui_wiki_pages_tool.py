"""The wiki's text pages (NOVA-139) without the game: check every page, and
preview one with nuitool. Run from the asset repository root, or anywhere:
paths are found from this file. docs/wiki/WRITING.md explains it for authors.

  python3 tools/nui_wiki_pages_tool.py check [--data <rt/share/conf>]
      Every page in assets/locale/locale/*/wiki/ (a .txt file; any other
      file there is a problem, the client cannot read it): its front matter and
      markup, index.txt (every English page listed once, every line a page),
      the categories, the links (item and mob numbers against item_names.txt
      and mob_names.txt when --data names the server's conf folder; page
      links against index.txt) and the images (each must be a file in the
      asset folders). Prints one line a problem; exit 1 when there is one.

  python3 tools/nui_wiki_pages_tool.py preview <page.txt> [--theme classic] [--scale 1.5]
          [--locale en] [--skip N] [--out preview.png] [--data <rt/share/conf>]
      The page as the wiki window shows it, as a PNG, through nuitool
      ($NUITOOL or nuitool on PATH). Themes: modern-dark, modern-light,
      cyberpunk, classic. Any page file works, inside the pack or not.
      nuitool does not scroll: --skip N leaves out the page's first N
      blocks, to see what is further down.

  python3 tools/nui_wiki_pages_tool.py fixture <page.txt> --out <fixture.json>
      The wiki window's model showing that page (what preview snaps).

  python3 tools/nui_wiki_pages_tool.py goldens
      Writes the golden fixtures wiki.page.fixture.json and
      wiki.page-end.fixture.json (docs/wiki/examples/every-feature.txt, its
      top and its second half) and wiki.landing.fixture.json (guides/basic_guide).
"""

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ASSETS = os.path.join(REPO, "assets")
ROOT = os.path.join(ASSETS, "root")
LOCALES = os.path.join(ASSETS, "locale", "locale")
WIKI_DIR = os.path.join(ASSETS, "nui", "nui", "windows", "wiki")
EXAMPLE = os.path.join(REPO, "docs", "wiki", "examples", "every-feature.txt")
EXAMPLE_END = 11  # every-feature.txt's blocks up to its map
DEFAULT_DATA = "/home/eddy/new-project/new/port-w7/chest-drop/rt/share/conf"
sys.path.insert(0, ROOT)

import nui_wiki_page_format as fmt  # noqa: E402
import nui_wiki_pages as pages  # noqa: E402


def read_file(path):
    with open(path, "rb") as handle:
        return handle.read()


def folder_reader(path):
    """READER over assets/locale/locale: store path locale/<lang>/... ."""
    if not path.startswith("locale/"):
        return None
    full = os.path.join(LOCALES, *path[len("locale/"):].split("/"))
    return read_file(full) if os.path.isfile(full) else None


def use_folder(locale="locale/en", extra=None):
    """nui_wiki_pages reads the checkout's files (and extra {store path: bytes})."""
    extra = extra or {}
    pages.READER = lambda path: extra[path] if path in extra else folder_reader(path)
    pages.LOCALE = lambda: locale
    pages.reset()


def names(data_dir, kind):
    """{vnum: name} from the server's item_names.txt or mob_names.txt."""
    path = os.path.join(data_dir or "", "%s_names.txt" % kind)
    out = {}
    if not data_dir or not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            vnum, _, name = line.rstrip("\r\n").partition("\t")
            if vnum.isdigit():
                out[int(vnum)] = name
    return out


def asset_file(store_path):
    """The file a store path names in the checked-out asset groups, or None."""
    rel = store_path[len(fmt.LEGACY_DRIVE):] if store_path.startswith(fmt.LEGACY_DRIVE) else store_path
    rel = ("ymir work/" + rel) if store_path.startswith(fmt.LEGACY_DRIVE) else rel
    for group in sorted(os.listdir(ASSETS)):
        candidate = os.path.join(ASSETS, group, *rel.split("/"))
        if os.path.isfile(candidate):
            return candidate
    return None


def page_files():
    """{(lang, path): file} of every page in the checkout."""
    out = {}
    for lang in sorted(os.listdir(LOCALES)):
        top = os.path.join(LOCALES, lang, "wiki")
        for folder, _, files in os.walk(top):
            for name in files:
                rel = os.path.relpath(os.path.join(folder, name), top).replace(os.sep, "/")
                if name.endswith(".txt") and rel != pages.RESERVED + ".txt":
                    out[(lang, rel[:-4])] = os.path.join(folder, name)
    return out


def unreadable_files():
    """Files under a wiki folder the client's pack.Get will not give Python
    (anything but .py, .pyc and .txt): such a page never shows in the game."""
    out = []
    for lang in sorted(os.listdir(LOCALES)):
        top = os.path.join(LOCALES, lang, "wiki")
        for folder, _, files in os.walk(top):
            for name in files:
                if os.path.splitext(name)[1].lower() not in (".txt", ".py", ".pyc"):
                    out.append("locale/%s/wiki/%s" % (lang, os.path.relpath(os.path.join(folder, name), top).replace(os.sep, "/")))
    return out


def check(data_dir):
    problems = []
    items, mobs = names(data_dir, "item"), names(data_dir, "mob")
    use_folder()
    listed = pages.index()
    index_path = os.path.join(LOCALES, "en", "wiki", "index.txt")
    raw = open(index_path, encoding="utf-8").read().splitlines() if os.path.isfile(index_path) else []
    for number, line in enumerate(raw, 1):
        line = line.strip()
        if line and not line.startswith("#") and not fmt.valid_page_path(line):
            problems.append("locale/en/wiki/index.txt:%d: not a page path: %s" % (number, line))
    files = page_files()
    known = set(path for lang, path in files if lang == "en")
    for path in listed:
        if path not in known:
            problems.append("locale/en/wiki/index.txt: %s has no file locale/en/wiki/%s.txt" % (path, path))
    for name in unreadable_files():
        problems.append("%s: the game reads only .txt pages (pack.Get refuses this extension)" % name)
    categories = set(ident for ident, _ in pages.CATEGORIES)
    for (lang, path), full in sorted(files.items()):
        where = "locale/%s/wiki/%s.txt" % (lang, path)
        if not fmt.valid_page_path(path):
            problems.append("%s: the file's path is not [a-z0-9_/-]" % where)
            continue
        if path not in listed:
            problems.append("%s: not listed in locale/en/wiki/index.txt" % where)
        page = fmt.parse(read_file(full))
        for line, message in page.problems:
            problems.append("%s:%d: %s" % (where, line, message))
        if page.fatal:
            continue
        if page.meta["category"] not in categories:
            problems.append("%s: category '%s' is not one of %s" % (where, page.meta["category"], ", ".join(sorted(categories))))
        english = files.get(("en", path))
        if lang != "en" and english:
            other = fmt.parse(read_file(english))
            if other.meta["category"] != page.meta["category"]:
                problems.append("%s: category differs from the English page's" % where)
        images = [p for _, p in page.meta["decor"]]
        for block in fmt.walk(page.blocks):
            if block["k"] == "img":
                images.append(block["src"][1:] if block["src"].startswith("/") else block["src"])
            runs = list(block["runs"]) + [r for e in block["items"] for r in e["runs"]]
            runs += [r for row in block["rows"] for c in row["cells"] for r in c["runs"]]
            for run in runs:
                if not run["link"]:
                    continue
                kind, ident, _ = run["link"]
                if kind == "page" and ident not in listed:
                    problems.append("%s: a link to a page index.txt does not list: %s" % (where, ident))
                table = items if kind == "item" else mobs if kind == "mob" else None
                if table is not None and int(ident) not in table:
                    problems.append("%s: no %s %s in %s_names.txt" % (where, kind, ident, kind))
        for image in images:
            if asset_file(image) is None:
                problems.append("%s: no image file %s in the asset folders" % (where, image))
    if items is None or mobs is None:
        print("note: item and mob numbers were not checked (no --data folder with item_names.txt, mob_names.txt)")
    for line in problems:
        print(line)
    print("pages: %d, problems: %d" % (len(files), len(problems)))
    return 1 if problems else 0


def base_model():
    with open(os.path.join(WIKI_DIR, "wiki.fixture.json"), encoding="utf-8") as handle:
        return json.load(handle)["wiki"]


def locale_string(locale, key, default):
    """A locale_game.txt string of the checkout (the tool runs without localeInfo)."""
    path = os.path.join(LOCALES, locale.split("/")[-1], "locale_game.txt")
    if os.path.isfile(path):
        with open(path, "rb") as handle:
            for line in handle.read().decode("utf-8", "replace").splitlines():
                parts = line.split("\t")
                if parts[0] == key and len(parts) > 1:
                    return parts[1]
    return default


def category_name(locale, category):
    keys = dict(pages.CATEGORIES)
    return locale_string(locale, keys[category], category) if category in keys else category


def fixture_for(page_file, data_dir=None, locale="locale/en", skip=0):
    """The wiki model with the page shown, as the window builds it."""
    store = "%s/wiki/__preview__.txt" % locale
    use_folder(locale, {store: read_file(page_file)})
    items, mobs = names(data_dir, "item") or {}, names(data_dir, "mob") or {}
    real = pages.exists
    pages.exists = lambda path: path == "__preview__" or real(path)
    try:
        values, _ = pages.render("__preview__", lambda kind, vnum: (items if kind == "item" else mobs).get(vnum, ""))
        category = (pages.load("__preview__").meta or {}).get("category", "")
        tree = []
        for i, entry in enumerate(pages.tree_categories()):
            open_ = entry["category"] == category
            tree.append({"cat": 10 + i, "label": category_name(locale, entry["category"]), "open": open_,
                         "subs": [{"cat": 10 + i, "sub": j, "label": pages.title(s["page"]), "selected": False}
                                  for j, s in enumerate(entry["subs"])] if open_ else []})
    finally:
        pages.exists = real
    model = base_model()
    for key, value in pages.initial_model().items():
        model[key] = value
    model.update(values)
    model["tp_blocks"] = model["tp_blocks"][skip:]
    title = values["tp_title"]
    model.update({
        "home": False, "list": [], "list_state": "ready", "list_title": "", "list_count": "", "list_sel": -1,
        "page_state": "text", "page_kind": "text", "page_vnum": 0, "page_name": title, "page_sub": "",
        "page_icon": "", "page_common": False, "page_link": True, "model_view": False, "hover_view": False,
        "origins": [], "chest": [], "refine": [], "drops": [], "retry_at": 0.0, "timeout_at": 0.0,
        "tabs": [{"i": 0, "label": title[:16], "active": True}], "tabs_full": False,
        "can_back": True, "can_forward": False,
        "crumbs": [{"i": 0, "label": locale_string(locale, "WIKI_HOME", "Home"), "last": False, "link": True},
                   {"i": 1, "label": category_name(locale, category), "last": False, "link": True},
                   {"i": 2, "label": title, "last": True, "link": False}],
        "tp_view": [{"n": 1}], "tp_open_at": 0.0,
    })
    if tree:
        first = dict(model["tree"][0], subs=[dict(sub, selected=False) for sub in model["tree"][0]["subs"]])
        model["tree"] = [first] + tree
    return {"wiki": model}


def write_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent="\t", ensure_ascii=False)
        handle.write("\n")


def nuitool():
    tool = os.environ.get("NUITOOL") or shutil.which("nuitool")
    if not tool:
        sys.exit("nuitool not found: set NUITOOL or put nuitool on PATH (docs/ui/AUTHORING.md, Tools)")
    return tool


def preview(page_file, theme, scale, lang, out, data_dir, skip=0):
    work = tempfile.mkdtemp(prefix="wiki-preview-")
    try:
        fixture = os.path.join(work, "fixture.json")
        write_json(fixture, fixture_for(page_file, data_dir, "locale/%s" % lang, skip))
        size = "%dx%d" % (round(1000 * scale), round(760 * scale))
        command = [nuitool(), "snap", "--doc", "nui/windows/wiki/wiki.rml", "--fixture", fixture,
                   "--locale", os.path.join(LOCALES, lang), "--theme", theme, "--scale", str(scale),
                   "--size", size, "--out", os.path.abspath(out)]
        for group in ("nui", "ETC", "icon", "locale", "season1", "patch2", "metin2_patch_etc", "metin2_patch_eu4"):
            if os.path.isdir(os.path.join(ASSETS, group)):
                command[2:2] = ["--root", os.path.join(ASSETS, group)]
        result = subprocess.run(command, capture_output=True, text=True)
        for line in result.stderr.splitlines():
            if line.startswith("rmlui:"):
                print(line)
        if result.returncode:
            sys.exit(result.stdout + result.stderr)
        print("wrote %s" % out)
    finally:
        shutil.rmtree(work, True)


def goldens(data_dir):
    write_json(os.path.join(WIKI_DIR, "wiki.page.fixture.json"), fixture_for(EXAMPLE, data_dir))
    # nuitool does not scroll: the page's second half, after its map.
    write_json(os.path.join(WIKI_DIR, "wiki.page-end.fixture.json"), fixture_for(EXAMPLE, data_dir, skip=EXAMPLE_END))
    landing = os.path.join(LOCALES, "en", "wiki", "guides", "basic_guide.txt")
    write_json(os.path.join(WIKI_DIR, "wiki.landing.fixture.json"), fixture_for(landing, data_dir))
    print("wrote wiki.page.fixture.json and wiki.landing.fixture.json")


def option(args, name, default=None):
    if name in args:
        at = args.index(name)
        value = args[at + 1]
        del args[at:at + 2]
        return value
    return default


def main(argv):
    args = list(argv)
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    command = args.pop(0)
    data_dir = option(args, "--data", DEFAULT_DATA if os.path.isdir(DEFAULT_DATA) else None)
    if command == "check":
        return check(data_dir)
    if command == "goldens":
        goldens(data_dir)
        return 0
    if command == "fixture":
        out = option(args, "--out")
        write_json(out, fixture_for(args[0], data_dir))
        return 0
    if command == "preview":
        theme = option(args, "--theme", "modern-dark")
        scale = float(option(args, "--scale", "1"))
        lang = option(args, "--locale", "en")
        out = option(args, "--out", "preview.png")
        skip = int(option(args, "--skip", "0"))
        preview(args[0], theme, scale, lang, out, data_dir, skip)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
