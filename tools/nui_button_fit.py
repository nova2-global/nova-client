#!/usr/bin/env python3
"""Checks that the literal labels of NovaUI buttons fit, in every locale.

    python3 tools/nui_button_fit.py            # from anywhere; exit 1 on an error
    python3 tools/nui_button_fit.py --font /path/to/font.ttf

For every <button> of every assets/nui/nui/windows/*/*.rml whose text is a
locale key (@ui.KEY or @game.KEY, not a {{ }} binding), it prints the
button's size class and its widest label over the 17 locales, measured in
Tahoma 12px (the legacy UI font; /mnt/c/Windows/Fonts/tahoma.ttf, else
Noto Sans from assets/nui/nui/fonts). A classic button keeps 9dp between
its label and each end of its art, so a label wider than the size's legacy
width minus 18dp is listed as information: the button grows, and its caps
keep a gap. The buttons whose label is bound ({{ }}) to a locale key the
controller picks are listed in BOUND and measured the same way, at the
size of their classic art.

Errors (exit 1):
- a --small button with a text label in a window other than the pre-Wave 1
  ones (EXEMPT): new windows use --medium or the default size for text,
  since a label fills the small art to its caps;
- a label key missing in a locale.
"""
import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOWS = os.path.join(ROOT, "assets", "nui", "nui", "windows")
LOCALES = os.path.join(ROOT, "assets", "locale", "locale")
LOCALE_NAMES = ("ae", "br", "cz", "de", "dk", "en", "es", "fr", "gr", "hu", "it", "nl", "pl", "pt", "ro", "ru", "tr")
TAHOMA = "/mnt/c/Windows/Fonts/tahoma.ttf"
NOTO = os.path.join(ROOT, "assets", "nui", "nui", "fonts", "NotoSans-Regular.ttf")

# The windows from before Wave 1, whose small text buttons predate the rule.
EXEMPT = ("gallery", "login", "theme-picker", "render-test", "skin-proof", "intro-ambient")

# Legacy widths in dp: the art of each size, and the keys whose art has a
# width of its own (the virtual keyboard's special keys).
SIZE_WIDTHS = {"small": 43, "medium": 61, "large": 88, "icon": 21}
ID_WIDTHS = {"vkey-symbols": 45, "vkey-shift": 58, "vkey-space": 293, "vkey-enter": 58, "vkey-backspace": 45}
CAP_GAP = 18

# Buttons whose label is a binding the controller fills with a locale key:
# (window, id, classic art size, key kind, the keys). The theme picker's
# labels are @ui.THEME_<ID> (nui_theme_picker.py), on the large classic art.
BOUND = [
    ("theme-picker", "theme-pick-<id>", "large", "ui", ("THEME_MODERN_DARK", "THEME_MODERN_LIGHT", "THEME_CLASSIC")),
]

BUTTON = re.compile(r"<button\b([^>]*)>(.*?)</button>", re.S)
ATTRIBUTE = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')
KEY = re.compile(r"@(ui|game)\.([A-Za-z0-9_]+)")
TAG = re.compile(r"<[^>]*>")


def read_table(path, game):
    """{key: value} of a locale file; locale_game.txt entries with a type
    (SA, SNA, SAA, SAN) are left out, as localeInfo makes them functions."""
    table = {}
    with open(path, encoding="utf-8") as file:
        for line in file.read().split("\n"):
            parts = line.split("\t")
            if len(parts) < 2 or not parts[0]:
                continue
            if game and len(parts) > 2 and parts[2].strip() in ("SA", "SNA", "SAA", "SAN"):
                continue
            table[parts[0]] = parts[1]
    return table


def tables():
    found = {}
    for locale in LOCALE_NAMES:
        folder = os.path.join(LOCALES, locale)
        found[locale] = {"ui": read_table(os.path.join(folder, "locale_interface.txt"), False),
                         "game": read_table(os.path.join(folder, "locale_game.txt"), True)}
    return found


def size_class(classes):
    for name in ("small", "medium", "icon"):
        if "nui-button--" + name in classes:
            return name
    return "large"


def buttons():
    """(window, id, size class, key kind, key name) for each literal-label button."""
    found = []
    for path in sorted(glob.glob(os.path.join(WINDOWS, "*", "*.rml"))):
        window = os.path.basename(os.path.dirname(path))
        if os.path.basename(path) != window + ".rml":
            continue
        with open(path, encoding="utf-8") as file:
            source = file.read()
        for attributes, inner in BUTTON.findall(source):
            text = TAG.sub("", inner).strip()
            if "{{" in text:
                continue
            keys = KEY.findall(text)
            if not keys:
                continue
            attrs = dict(ATTRIBUTE.findall(attributes))
            classes = attrs.get("class", "").split()
            found.append((window, attrs.get("id", ""), size_class(classes), keys[0][0], keys[0][1]))
    for window, element_id, size, kind, keys in BOUND:
        for key in keys:
            found.append((window, element_id, size, kind, key))
    return found


def measure(font, text):
    return font.getlength(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--font", default=None, help="font file to measure with (default: Tahoma, else Noto Sans)")
    args = parser.parse_args(argv)
    from PIL import ImageFont
    font_path = args.font or (TAHOMA if os.path.isfile(TAHOMA) else NOTO)
    font = ImageFont.truetype(font_path, 12)
    print("measured with %s at 12px" % os.path.basename(font_path))
    strings = tables()
    errors, infos = [], []
    for window, element_id, size, kind, key in buttons():
        legacy = ID_WIDTHS.get(element_id, SIZE_WIDTHS[size])
        widest, widest_locale = 0.0, ""
        for locale in LOCALE_NAMES:
            value = strings[locale][kind].get(key)
            if value is None:
                errors.append("error: %s %s: @%s.%s is missing in %s" % (window, element_id or "(no id)", kind, key, locale))
                continue
            width = measure(font, value)
            if width > widest:
                widest, widest_locale = width, locale
            if width > legacy - CAP_GAP:
                infos.append("info: %s %s (%s, %ddp): %s %r is %.0fpx, over %ddp" % (
                    window, element_id or "(no id)", size, legacy, locale, value, width, legacy - CAP_GAP))
        print("%-18s %-22s %-6s @%s.%-22s widest %3.0fpx (%s)" % (
            window, element_id or "(no id)", size, kind, key, widest, widest_locale))
        if size == "small" and window not in EXEMPT:
            errors.append("error: %s %s: a --small button with a text label (use --medium or the default size)" % (
                window, element_id or "(no id)"))
    for line in infos:
        print(line)
    for line in errors:
        print(line)
    print("%d button(s), %d information line(s), %d error(s)" % (len(buttons()), len(infos), len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
