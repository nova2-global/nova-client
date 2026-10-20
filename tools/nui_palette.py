#!/usr/bin/env python3
"""The player color resolve (P13 spec 5.3), the reference implementation of
nova-client-src's src/NovaUI/Core/Palette.{h,cpp}: the two agree to the byte,
which tools/nui_palette_test.py checks on the palette vectors
(tools/fixtures/palette_cases.json).

    python3 tools/nui_palette.py --theme modern-dark accent=#c58af9 opacity=80
    python3 tools/nui_palette.py --check-cases tools/fixtures/palette_cases.json

The data is nui/theme/colors.json and each skin's nui/skins/<skin>/colors.json
(tools/nui_tokens.py writes them; docs/ui/AUTHORING.md "Player colors"):
{"version": 1, "pairs": [[fg, bg, min], ...], "palettes": {<name>: {"tone",
"backdrop" (optional), "tokens", "slots"}}, "themes": {<theme id>: <palette>}}.

A slot: {"slot", "kind": "color"|"percent", "label", "swatches", "min", "max",
"step" (percent), "default" (optional), "backdrop" (percent, optional),
"sets": [<rule>, ...]}. Rules: value (the slot's color), mix (with "with", a
color or a token, by "t"), alpha (a percent slot: the token's color with that
alpha; a color slot with "a": the slot's color with alpha a), delta (the
slot's color plus the palette's token minus its "ref", per channel, clamped,
keeping the token's alpha), pick (of the tokens in "from", the one with the
higher contrast over "on", the first on a tie).

The resolve: colors are four 8-bit channels; mix(a, b, t) = floor(a + (b -
a) * t + 0.5) per channel, alpha included; contrast(fg, bg) is WCAG 2.x's
ratio of fg composited over bg, and a translucent bg is first composited
over black and over white, the lower ratio counting.
  1. O (the overrides) starts empty; base(t) is O[t], else the palette's t.
  2. Each slot in the palette's order whose value is set, well formed and
     not its default writes its rules in order. A percent slot below its max
     also sets panel-backdrop to its "backdrop" (else the palette's).
  3. Each pair (fg, bg, min) in order with fg or bg in O whose contrast is
     below min: fg mixes toward white (a dark tone) or black (a light one)
     by k / 64, k = 1..64; the first that reaches min becomes O[fg] and
     adjusted[fg]; if none does, the pair is failed.
  4. A pair failed and the percent slot "opacity" set below its max: it
     rises by its step (adjusted["opacity"]; at its max it is unset) and the
     resolve runs again from 1.
  5. Each failed fg takes white or black, whichever has the higher ratio
     over its first failed pair's bg (adjusted too); the pairs stay failed.
Results are lowercase #rrggbbaa; panel-backdrop is its filter string.
"""
import argparse
import json
import math
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLORS_JSON = os.path.join(REPO, "assets", "nui", "nui", "theme", "colors.json")
SKINS = os.path.join(REPO, "assets", "nui", "nui", "skins")
THEMES_JSON = os.path.join(REPO, "assets", "nui", "nui", "theme", "themes.json")

PANEL_BACKDROP = "panel-backdrop"
OPACITY = "opacity"
CURATED = ("accent", "panel", "opacity", "highlight")
MAX_OVERRIDES_BYTES = 960
WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
SLOT_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
THEME_ID_RE = re.compile(r"^[a-z0-9-]{1,31}$")


class PaletteError(Exception):
    pass


# --- colors ----------------------------------------------------------------------

def parse_color(text):
    """#rrggbb or #rrggbbaa, either case, as (r, g, b, a); None otherwise."""
    if not isinstance(text, str) or len(text) not in (7, 9) or text[0] != "#":
        return None
    try:
        channels = [int(text[i:i + 2], 16) for i in range(1, len(text), 2)]
    except ValueError:
        return None
    if any(not re.fullmatch(r"[0-9a-fA-F]{2}", text[i:i + 2]) for i in range(1, len(text), 2)):
        return None
    return tuple(channels + [255] * (4 - len(channels)))


def format_color(color):
    return "#" + "".join("%02x" % c for c in color)


def mix_channel(a, b, t):
    return max(0, min(255, int(math.floor(a + (b - a) * t + 0.5))))


def mix(a, b, t):
    return tuple(mix_channel(a[i], b[i], t) for i in range(4))


def _linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(r, g, b):
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def _ratio_over(fg, br, bg, bb):
    a = fg[3] / 255.0
    fr = fg[0] / 255.0 * a + br * (1.0 - a)
    fgg = fg[1] / 255.0 * a + bg * (1.0 - a)
    fb = fg[2] / 255.0 * a + bb * (1.0 - a)
    l1, l2 = luminance(fr, fgg, fb), luminance(br, bg, bb)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def contrast_ratio(fg, bg):
    """WCAG 2.x: fg composited over bg; a translucent bg composited over black
    and over white first, the lower ratio counting."""
    if bg[3] == 255:
        return _ratio_over(fg, bg[0] / 255.0, bg[1] / 255.0, bg[2] / 255.0)
    a = bg[3] / 255.0
    r, g, b = bg[0] / 255.0 * a, bg[1] / 255.0 * a, bg[2] / 255.0 * a
    return min(_ratio_over(fg, r, g, b), _ratio_over(fg, r + (1.0 - a), g + (1.0 - a), b + (1.0 - a)))


# --- the data --------------------------------------------------------------------

def normalize_slot_value(slot, value):
    """A slot value as UI_COLORS stores it, or None: a color slot's lowercase
    #rrggbb, a percent slot's whole number within [min, max] on its step."""
    if not isinstance(value, str):
        value = str(value)
    if slot["kind"] == "color":
        color = parse_color(value) if len(value) == 7 else None
        return format_color(color)[:7] if color else None
    if not value or len(value) > 3 or not value.isdigit():
        return None
    number = int(value)
    if number < slot["min"] or number > slot["max"] or (slot["step"] > 0 and (number - slot["min"]) % slot["step"]):
        return None
    return str(number)


def _parse_rule(rule, palette, kind):
    tokens = palette["tokens"]
    if not isinstance(rule, dict) or rule.get("token") not in tokens:
        raise PaletteError("a rule's \"token\" is missing or not a color of its palette")
    name = rule.get("rule")
    out = {"token": rule["token"], "rule": name}
    if name == "value":
        pass
    elif name == "mix":
        t = rule.get("t")
        with_ = rule.get("with")
        if not isinstance(with_, str) or not isinstance(t, (int, float)) or isinstance(t, bool) or not 0.0 <= t <= 1.0:
            raise PaletteError("the mix rule for '%s' needs \"with\" and \"t\" in 0..1" % rule["token"])
        color = parse_color(with_)
        if color is None and with_ not in tokens:
            raise PaletteError("the mix rule for '%s' mixes with '%s', neither a color nor a token" % (rule["token"], with_))
        out.update(t=float(t), with_color=color, with_token=None if color else with_)
    elif name == "alpha":
        a = rule.get("a", -1)
        if "a" in rule and (not isinstance(a, int) or isinstance(a, bool) or not 0 <= a <= 255):
            raise PaletteError("the alpha rule for '%s' has an \"a\" outside 0..255" % rule["token"])
        if kind == "color" and a < 0:
            raise PaletteError("the alpha rule for '%s' of a color slot needs \"a\"" % rule["token"])
        out["a"] = a
    elif name == "delta":
        if rule.get("ref") not in tokens:
            raise PaletteError("the delta rule for '%s' needs a \"ref\" token" % rule["token"])
        out["ref"] = rule["ref"]
    elif name == "pick":
        options = rule.get("from")
        if (not isinstance(options, list) or len(options) < 2 or any(o not in tokens for o in options)
                or rule.get("on") not in tokens):
            raise PaletteError("the pick rule for '%s' needs \"from\" (two or more tokens) and \"on\"" % rule["token"])
        out.update(options=list(options), on=rule["on"])
    else:
        raise PaletteError("the rule for '%s' is not value, mix, alpha, delta or pick" % rule["token"])
    return out


def _parse_slot(raw, palette):
    if not isinstance(raw, dict) or not isinstance(raw.get("slot"), str) or not SLOT_NAME_RE.match(raw["slot"]):
        raise PaletteError("a slot has no name of [a-z][a-z0-9-]")
    kind = raw.get("kind")
    if kind not in ("color", "percent"):
        raise PaletteError("slot '%s': kind is color or percent" % raw["slot"])
    slot = {"slot": raw["slot"], "kind": kind, "label": raw.get("label", ""), "swatches": [], "min": 0, "max": 0, "step": 0,
            "backdrop": None}
    if kind == "percent":
        for key in ("min", "max", "step"):
            if not isinstance(raw.get(key), int) or isinstance(raw.get(key), bool):
                raise PaletteError("slot '%s': a percent slot has whole min, max and step" % raw["slot"])
            slot[key] = raw[key]
        if not 0 <= slot["min"] <= slot["max"] or slot["step"] < 1:
            raise PaletteError("slot '%s': min, max and step out of range" % raw["slot"])
        if isinstance(raw.get("backdrop"), str):
            slot["backdrop"] = raw["backdrop"]
    for swatch in raw.get("swatches", []):
        normal = normalize_slot_value(slot, swatch)
        if normal is None:
            raise PaletteError("slot '%s': swatch %r is not a value of the slot" % (raw["slot"], swatch))
        slot["swatches"].append(normal)
    sets = raw.get("sets")
    if not isinstance(sets, list) or not sets:
        raise PaletteError("slot '%s' has no \"sets\"" % raw["slot"])
    slot["sets"] = []
    for rule in sets:
        try:
            slot["sets"].append(_parse_rule(rule, palette, kind))
        except PaletteError as error:
            raise PaletteError("slot '%s': %s" % (raw["slot"], error))
    if "default" in raw:
        default = normalize_slot_value(slot, raw["default"])
        if default is None:
            raise PaletteError("slot '%s': its \"default\" is not a value of the slot" % raw["slot"])
    elif kind == "percent":
        default = str(slot["max"])
    else:
        first = next((r for r in slot["sets"] if r["rule"] == "value"), None)
        if first is None:
            raise PaletteError("slot '%s' has neither a \"default\" nor a value rule to take one from" % raw["slot"])
        default = format_color(palette["tokens"][first["token"]])[:7]
    slot["default"] = default
    return slot


def _parse_palette(raw, pairs):
    if not isinstance(raw, dict) or not isinstance(raw.get("tokens"), dict):
        raise PaletteError("no \"tokens\" object")
    palette = {"tokens": {}, "pairs": pairs, "backdrop": "none", "slots": []}
    for name, value in raw["tokens"].items():
        color = parse_color(value)
        if color is None:
            raise PaletteError("token '%s' is not a #rrggbb or #rrggbbaa color" % name)
        palette["tokens"][name] = color
    tone = raw.get("tone")
    if tone is not None:
        if tone not in ("dark", "light"):
            raise PaletteError("\"tone\" is not dark or light")
        palette["dark"] = tone == "dark"
    else:
        surface = palette["tokens"].get("surface")
        palette["dark"] = surface is None or luminance(*(c / 255.0 for c in surface[:3])) < 0.18
    if isinstance(raw.get("backdrop"), str):
        palette["backdrop"] = raw["backdrop"]
    for slot in raw.get("slots", []):
        palette["slots"].append(_parse_slot(slot, palette))
    return palette


def parse_colors(document, into=None):
    """Adds one colors.json document (text or parsed) to `into` (a new data
    dict without it). PaletteError for a file that breaks a rule, and for a
    palette or theme an earlier file already has (the earlier one stays)."""
    into = into if into is not None else {"palettes": {}, "themes": {}}
    top = json.loads(document) if isinstance(document, str) else document
    if not isinstance(top, dict) or top.get("version") != 1:
        raise PaletteError("\"version\" is not 1")
    pairs = []
    for pair in top.get("pairs", []):
        if (not isinstance(pair, list) or len(pair) != 3 or not all(isinstance(p, str) for p in pair[:2])
                or not isinstance(pair[2], (int, float)) or isinstance(pair[2], bool)):
            raise PaletteError("a pair is not [fg, bg, minimum ratio]")
        pairs.append((pair[0], pair[1], float(pair[2])))
    palettes = {}
    for name, raw in top.get("palettes", {}).items():
        try:
            palettes[name] = _parse_palette(raw, pairs)
        except PaletteError as error:
            raise PaletteError("palette '%s': %s" % (name, error))
    themes = {}
    for theme_id, name in top.get("themes", {}).items():
        if not THEME_ID_RE.match(theme_id) or not isinstance(name, str):
            raise PaletteError("theme '%s' is not a theme id naming a palette" % theme_id)
        if name not in palettes and name not in into["palettes"]:
            raise PaletteError("theme '%s' names palette '%s', which no file has" % (theme_id, name))
        themes[theme_id] = name
    clashes = []
    for name, palette in palettes.items():
        if name in into["palettes"]:
            clashes.append("palette '%s'" % name)
        else:
            into["palettes"][name] = palette
    for theme_id, name in themes.items():
        if theme_id in into["themes"]:
            clashes.append("theme '%s'" % theme_id)
        else:
            into["themes"][theme_id] = name
    if clashes:
        raise PaletteError("%s already came from an earlier file, which stays" % ", ".join(clashes))
    return into


def load(colors_path=COLORS_JSON, skins_dir=SKINS):
    """The shipped data, as the runtime reads it: nui/theme/colors.json, then
    every skin's colors.json in the order of themes.json."""
    data = {"palettes": {}, "themes": {}}
    with open(colors_path, encoding="utf-8") as handle:
        parse_colors(handle.read(), data)
    if os.path.isdir(skins_dir):
        for skin in skin_order():
            path = os.path.join(skins_dir, skin, "colors.json")
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as handle:
                    parse_colors(handle.read(), data)
    return data


def skin_order(themes_path=THEMES_JSON):
    order = []
    with open(themes_path, encoding="utf-8") as handle:
        for theme in json.load(handle).get("themes", []):
            for name in theme.get("body", []):
                if name.startswith("skin-") and name[5:] not in order:
                    order.append(name[5:])
    return order


def slots_of_theme(data, theme_id):
    palette = _palette_of(data, theme_id)
    return list(palette["slots"]) if palette else []


def _palette_of(data, theme_id):
    name = data["themes"].get(theme_id)
    return data["palettes"].get(name) if name else None


# --- the resolve -------------------------------------------------------------------

class _Pass:
    def __init__(self, palette):
        self.palette = palette
        self.overrides = {}
        self.backdrop = None
        self.adjusted = {}
        self.failed = []

    def base(self, token):
        if token in self.overrides:
            return self.overrides[token]
        return self.palette["tokens"].get(token, BLACK)

    def apply(self, slot, value):
        color, percent = BLACK, 0
        if slot["kind"] == "color":
            color = parse_color(value)
        else:
            percent = int(value)
        for rule in slot["sets"]:
            kind = rule["rule"]
            if kind == "value":
                out = color
            elif kind == "mix":
                out = mix(color, rule["with_color"] if rule["with_color"] else self.base(rule["with_token"]), rule["t"])
            elif kind == "alpha":
                if slot["kind"] == "percent":
                    base = self.base(rule["token"])
                    out = base[:3] + (max(0, min(255, int(math.floor(255 * percent / 100.0 + 0.5)))),)
                else:
                    out = color[:3] + (rule["a"],)
            elif kind == "delta":
                token, ref = self.palette["tokens"][rule["token"]], self.palette["tokens"][rule["ref"]]
                out = tuple(max(0, min(255, color[i] + token[i] - ref[i])) for i in range(3)) + (token[3],)
            else:
                on = self.base(rule["on"])
                best, out = -1.0, None
                for candidate in rule["options"]:
                    ratio = contrast_ratio(self.base(candidate), on)
                    if ratio > best:
                        best, out = ratio, self.base(candidate)
            self.overrides[rule["token"]] = out
        if slot["kind"] == "percent" and percent < slot["max"]:
            self.backdrop = slot["backdrop"] if slot["backdrop"] is not None else self.palette["backdrop"]

    def contrast(self):
        pole = WHITE if self.palette["dark"] else BLACK
        for fg_name, bg_name, minimum in self.palette["pairs"]:
            if fg_name not in self.overrides and bg_name not in self.overrides:
                continue
            fg, bg = self.base(fg_name), self.base(bg_name)
            if contrast_ratio(fg, bg) >= minimum:
                continue
            for k in range(1, 65):
                c = mix(fg, pole, k / 64.0)
                if contrast_ratio(c, bg) >= minimum:
                    self.overrides[fg_name] = c
                    self.adjusted[fg_name] = format_color(c)
                    break
            else:
                self.failed.append((fg_name, bg_name))


def resolve(data, theme_id, values):
    """{"tokens", "adjusted", "failed", "opacity"} for a theme's slot values
    (slot name to "#rrggbb" or a percent), as ResolveColors returns them."""
    result = {"tokens": {}, "adjusted": {}, "failed": [], "opacity": 100}
    palette = _palette_of(data, theme_id)
    if palette is None:
        return result
    chosen, opacity, opacity_index = [], None, 0
    for slot in palette["slots"]:
        if slot["slot"] not in values:
            continue
        value = normalize_slot_value(slot, values[slot["slot"]])
        if value is None or value == slot["default"]:
            continue
        if slot["slot"] == OPACITY and slot["kind"] == "percent":
            opacity, opacity_index = slot, len(chosen)
            result["opacity"] = int(value)
        chosen.append([slot, value])
    raised = False
    while True:
        work = _Pass(palette)
        for slot, value in chosen:
            work.apply(slot, value)
        work.contrast()
        if work.failed and opacity is not None and result["opacity"] < opacity["max"]:
            result["opacity"] = min(result["opacity"] + opacity["step"], opacity["max"])
            raised = True
            if result["opacity"] >= opacity["max"]:
                del chosen[opacity_index]
                opacity = None
            else:
                chosen[opacity_index][1] = str(result["opacity"])
            continue
        forced = set()
        for fg, bg in work.failed:
            if fg in forced:
                continue
            forced.add(fg)
            back = work.base(bg)
            pick = WHITE if contrast_ratio(WHITE, back) >= contrast_ratio(BLACK, back) else BLACK
            work.overrides[fg] = pick
            work.adjusted[fg] = format_color(pick)
        result["tokens"] = {token: format_color(color) for token, color in sorted(work.overrides.items())}
        if work.backdrop is not None:
            result["tokens"][PANEL_BACKDROP] = work.backdrop
        result["adjusted"] = dict(sorted(work.adjusted.items()))
        result["failed"] = [list(pair) for pair in work.failed]
        break
    if raised:
        result["adjusted"][OPACITY] = str(result["opacity"])
    result["tokens"] = dict(sorted(result["tokens"].items()))
    result["adjusted"] = dict(sorted(result["adjusted"].items()))
    return result


# --- UI_COLORS ---------------------------------------------------------------------

def parse_overrides(text):
    """UI_COLORS -> ({theme: {slot: value}}, [themes in order]). PaletteError
    for text over 960 bytes, a malformed theme, slot or value, or a theme or
    slot named twice. Empty text is no override."""
    if len(text.encode("utf-8")) > MAX_OVERRIDES_BYTES:
        raise PaletteError("UI_COLORS holds %d bytes; at most %d are allowed" % (len(text.encode("utf-8")), MAX_OVERRIDES_BYTES))
    out, order = {}, []
    if not text:
        return out, order
    for part in text.split(";"):
        theme, sep, body = part.partition(":")
        if not sep or not THEME_ID_RE.match(theme) or theme in out or not body:
            raise PaletteError("UI_COLORS: %r is not <theme>:<slot>=<value>,..." % part)
        slots = {}
        for item in body.split(","):
            slot, sep, value = item.partition("=")
            if (not sep or not SLOT_NAME_RE.match(slot) or slot in slots
                    or not (re.fullmatch(r"#[0-9a-fA-F]{6}", value) or re.fullmatch(r"[0-9]{1,3}", value))):
                raise PaletteError("UI_COLORS: %r is not <slot>=<#rrggbb or a percent>" % item)
            slots[slot] = value.lower() if value.startswith("#") else str(int(value))
        out[theme] = slots
        order.append(theme)
    return out, order


def format_overrides(overrides, theme_order):
    """Themes in `theme_order` first, then the others by name; the curated
    slots in their order, then the others by name; a theme without slots is
    left out."""
    themes = [t for t in theme_order if t in overrides] + sorted(t for t in overrides if t not in theme_order)
    parts = []
    for theme in themes:
        slots = overrides[theme]
        if not slots:
            continue
        names = [s for s in CURATED if s in slots] + sorted(s for s in slots if s not in CURATED)
        parts.append("%s:%s" % (theme, ",".join("%s=%s" % (name, slots[name]) for name in names)))
    return ";".join(parts)


# --- the command line ----------------------------------------------------------------

def check_cases(path):
    """Resolves every case of a palette vector file and compares; returns the
    names of the cases that differ."""
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    data = {"palettes": {}, "themes": {}}
    for colors in document["data"]:
        parse_colors(colors, data)
    wrong = []
    for case in document["cases"]:
        got = resolve(data, case["theme"], case["values"])
        expected = {key: case[key] for key in ("tokens", "adjusted", "failed", "opacity")}
        if got != expected:
            wrong.append(case["name"])
    return wrong


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--theme", default="modern-dark")
    parser.add_argument("--check-cases", metavar="FILE", help="compare the resolve with a palette vector file")
    parser.add_argument("values", nargs="*", help="slot=value pairs")
    args = parser.parse_args(argv)
    try:
        if args.check_cases:
            wrong = check_cases(args.check_cases)
            print("nui_palette: %s" % ("every case matches" if not wrong else "differs in " + ", ".join(wrong)))
            return 1 if wrong else 0
        values = dict(item.split("=", 1) for item in args.values)
        print(json.dumps(resolve(load(), args.theme, values), indent=1))
    except (PaletteError, OSError, ValueError, KeyError) as error:
        print("nui_palette: %s" % error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
