"""One-time converter (NOVA-139): OLD's wiki .txt pages to the new page format
(assets/root/nui_wiki_page_format.py, docs/wiki/WRITING.md).

  python3 tools/wiki_convert_old.py [--old <OLD client_pack/source>] [--out docs/wiki/drafts]

Every OLD page becomes <out>/en/<path>.md, a draft that does not ship (it is
outside assets/). A page ships only after someone reads it and copies it to
assets/locale/locale/en/wiki/ and lists it in index.txt. <out>/conversion-log.txt
says what each page lost.

OLD's format (root/inGameWikiUI.py SimpleTextLoader): the first line is
skipped; each line is one text line, optionally led by [TOKEN=value; ...].
What the converter does with it:
  - X, Y, X_PADDING, Y_PADDING, SCALE, CENTER_ALIGN, RIGHT_ALIGN, FONT_NAME:
    dropped. Pixel places are what the new format leaves out on purpose.
  - A line with COLOR and short text, or FONT_SIZE 14 and up: a heading
    (### or ##); BOLD: **bold**; a leading *: a bullet.
  - |~AARRGGBB|H|h<text>|h|r (OLD's highlight): **<text>**; other color and
    link tags are stripped.
  - GOTO=page:<p>, item:<v>, monster:<v>: a link with the line's text;
    GOTO=<number> (a scroll to a place: the table of contents over the
    guide_tabs art) is dropped with its line.
  - IMG with ITEM_TOOLTIP=<vnum>: an [[item:<vnum>]] link (xN with
    ITEM_COUNT); runs of them join into one line.
  - divider_long: --- {style=ornate}; divider_small: ---; guide_tabs: dropped;
    emoji/<key>: **<KEY>**; BANNER_IMG and other images: an image line,
    lowercased (the art is OLD's and NEW lacks it: check reports it).
Titles come from OLD's inGameWikiConfig.py and locale_game.txt, the category
from the folder, the order from the config."""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "assets", "root"))

import nui_wiki_page_format as fmt  # noqa: E402

OLD = "/home/eddy/new-project/old/client_pack/source"
OUT = os.path.join(REPO, "docs", "wiki", "drafts")
CATEGORY_OF_FOLDER = {"dungeons": "dungeons", "systems": "systems", "guides": "guides", "events": "events"}
# OLD's two pages outside a folder.
SPECIAL = {
    "landingpage": ("guides/basic_guide", "The Basic Guide", "guides"),
    "desc": ("guides/old_format_notes", "Notes on OLD's Page Format", "guides"),
}
HIGHLIGHT = re.compile(r"\|~[0-9a-fA-F]{6,8}\|H[^|]*\|h(.*?)\|h\|r")
TAGS = re.compile(r"\|~[0-9a-fA-F]{6,8}|\|c[0-9a-fA-F]{8}|\|H[^|]*\|h|\|h|\|r")
LINE_START = re.compile(r"^(#|-|\+|:|\||!|\*|\d+\.)")


def new_path(rel):
    """dungeons/demontower.txt -> dungeons/demontower."""
    base = rel[:-4] if rel.endswith(".txt") else rel
    if base in SPECIAL:
        return SPECIAL[base][0]
    return re.sub(r"[^a-z0-9_/-]", "_", base.lower())


def old_titles(old):
    """{OLD file: (English title, position in the config)} from OLD's tree."""
    strings = {}
    with open(os.path.join(old, "locale", "en", "locale_game.txt"), "rb") as handle:
        for line in handle.read().decode("utf-8", "replace").splitlines():
            parts = line.split("\t")
            if len(parts) > 1:
                strings[parts[0]] = parts[1]
    out = {}
    pattern = re.compile(r'\[\s*(?:localeInfo\.(\w+)|"([^"]+)")\s*,\s*\("([^"]+)"')
    with open(os.path.join(old, "root", "inGameWikiConfig.py"), encoding="utf-8", errors="replace") as handle:
        for position, line in enumerate(handle):
            match = pattern.search(line)
            if match:
                key, literal, path = match.groups()
                title = literal or strings.get(key, key)
                out.setdefault(path, (title, position))
    return out


def tokens(line):
    """(token dict, text): OLD's ParseToken."""
    if not line.startswith("["):
        return {}, line
    end = line.find("]")
    if end <= 0:
        return {}, line
    found = {}
    for part in line[1:end].split(";"):
        key, eq, value = part.partition("=")
        key = key.strip().lower()
        if key:
            found[key] = value.strip() if eq else True
    return found, line[end + 1:]


def escape(text):
    """OLD text as new text: highlights to bold, tags out, markup escaped."""
    text = text.replace("\\", "\\\\").replace("*", "\\*").replace("[[", "\\[[").replace("`", "\\`")
    text = HIGHLIGHT.sub(lambda m: "**%s**" % m.group(1).strip() if m.group(1).strip() else "", text)
    text = TAGS.sub("", text)
    text = text.replace("|", "\\|")
    return re.sub(" {2,}", " ", text)


def guard_start(text):
    """A converted line never starts a block by accident."""
    stripped = text.lstrip()
    if LINE_START.match(stripped):
        return "\\" + stripped
    return stripped


class Converter(object):
    def __init__(self, rel, title, order):
        self.rel = rel
        self.out = []
        self.log = []
        self.items = []      # a run of item icons, waiting for its line
        self.title = title
        self.order = order

    def note(self, line_no, message):
        self.log.append("%s:%d: %s" % (self.rel, line_no, message))

    def flush_items(self):
        if self.items:
            self.out.append(", ".join(self.items))
            self.items = []

    def blank(self):
        self.flush_items()
        if self.out and self.out[-1] != "":
            self.out.append("")

    def block(self, text):
        """A line that is a block of its own (a heading, a separator, an image)."""
        self.blank()
        self.out.append(text)
        self.out.append("")

    def image(self, found, line_no):
        path = str(found.pop("img")).strip().replace("\\", "/")
        lower = path.lower()
        if "item_tooltip" in found:
            vnum = str(found["item_tooltip"]).split(":")[0].strip()
            if vnum.isdigit() and int(vnum) > 0:
                count = found.get("item_count")
                self.items.append("[[item:%d]]%s" % (int(vnum), " x%s" % count if count not in (None, True) else ""))
                return
        if "divider_long" in lower:
            self.block("--- {style=ornate}")
        elif "divider" in lower:
            self.block("---")
        elif "guide_tabs" in lower:
            self.note(line_no, "dropped the table of contents art %s" % path)
        elif "/emoji/" in lower:
            key = os.path.splitext(os.path.basename(path))[0].upper()
            self.items.append("**%s**" % key)
        elif fmt.valid_image_path(lower):
            self.block("![](%s)" % lower)
            self.note(line_no, "kept the image %s (OLD's art: check whether NEW has it)" % lower)
        else:
            self.note(line_no, "dropped the image %s (not a path the new format takes)" % path)

    def convert(self, lines):
        for line_no, raw in enumerate(lines[1:], 2):
            raw = raw.rstrip("\r\n")
            found, text = tokens(raw.strip())
            if "banner_img" in found:
                banner = str(found.pop("banner_img")).strip().lower()
                if fmt.valid_image_path(banner):
                    self.block("![](%s){align=center width=100%%}" % banner)
                    self.note(line_no, "the banner %s is OLD's art" % banner)
            if "img" in found:
                self.image(found, line_no)
            goto = found.get("goto")
            if goto not in (None, True) and str(goto).strip().lstrip("-").isdigit():
                self.note(line_no, "dropped a table of contents line: %s" % text.strip())
                continue
            text = text.strip()
            if not text:
                if not found:
                    self.blank()
                continue
            self.flush_items()
            bullet = text.startswith("*")
            if bullet:
                text = text[1:].strip()
            body = escape(text)
            if goto not in (None, True):
                body = self.link(str(goto).strip(), body, line_no)
            if found.get("bold") and body:
                body = "**%s**" % body
            size = found.get("font_size")
            size = int(size) if isinstance(size, str) and size.isdigit() else 12
            heading = (found.get("color") not in (None, True) and len(text) < 60) or size >= 14
            if heading and body:
                self.block("%s %s" % ("##" if size >= 14 else "###", body.strip("*").strip() or body))
            elif bullet:
                if self.out and self.out[-1] != "" and not self.out[-1].startswith("- "):
                    self.blank()
                self.out.append("- " + body)
            elif self.out and (self.out[-1].startswith("- ") or self.out[-1].startswith("  ")):
                # OLD wrapped a bullet's text by hand: the next line goes on.
                self.out.append("  " + body)
            else:
                self.out.append(guard_start(body))
        self.flush_items()
        while self.out and self.out[-1] == "":
            self.out.pop()
        category = self.category()
        head = ["---", "title: %s" % self.title, "category: %s" % category]
        if self.order is not None:
            head.append("order: %d" % self.order)
        head.append("---")
        return "\n".join(head + self.out) + "\n"

    def link(self, goto, body, line_no):
        kind, _, ident = goto.partition(":")
        kind = kind.strip().lower()
        ident = ident.strip()
        label = body.replace("]]", "").strip() or ident
        if kind == "page":
            return "[[page:%s|%s]]" % (new_path(ident.lower()), label)
        if kind in ("item", "monster") and ident.isdigit():
            return "[[%s:%s|%s]]" % ("item" if kind == "item" else "mob", ident, label)
        self.note(line_no, "dropped a link GOTO=%s" % goto)
        return body

    def category(self):
        base = self.rel[:-4]
        if base in SPECIAL:
            return SPECIAL[base][2]
        return CATEGORY_OF_FOLDER.get(base.split("/")[0], "guides")


def main(argv):
    old = OLD
    out = OUT
    if "--old" in argv:
        old = argv[argv.index("--old") + 1]
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
    source = os.path.join(old, "locale", "en", "wiki")
    titles = old_titles(old)
    log, made = [], []
    for folder, _, files in sorted(os.walk(source)):
        for name in sorted(files):
            if not name.endswith(".txt"):
                continue
            rel = os.path.relpath(os.path.join(folder, name), source).replace(os.sep, "/")
            base = rel[:-4]
            if base in SPECIAL:
                title, order = SPECIAL[base][1], None
            else:
                title, position = titles.get(rel, (None, None))
                order = position
                if title is None:
                    title = base.split("/")[-1].replace("_", " ").title()
                    log.append("%s: not in OLD's tree (inGameWikiConfig.py): titled from its file name" % rel)
            with open(os.path.join(folder, name), "rb") as handle:
                lines = handle.read().decode("utf-8", "replace").splitlines()
            converter = Converter(rel, title.replace(":", " -").strip(), order)
            text = converter.convert(lines)
            path = new_path(rel)
            target = os.path.join(out, "en", *path.split("/")) + ".md"
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            page = fmt.parse(text)
            for line, message in page.problems:
                converter.log.append("%s -> %s.md:%d: %s" % (rel, path, line, message))
            log.extend(converter.log)
            made.append((rel, path))
    with open(os.path.join(out, "conversion-log.txt"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("# wiki_convert_old.py: what each OLD page lost or kept from OLD's art\n")
        for rel, path in made:
            handle.write("%s -> %s.md\n" % (rel, path))
        handle.write("\n")
        handle.write("\n".join(log) + "\n")
    print("converted %d pages into %s" % (len(made), out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
