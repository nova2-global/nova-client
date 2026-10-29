#!/usr/bin/env python3
"""Writes the fixtures of the Wave 3b slot windows (P14 spec 6.9): the
inventory, the costume window, the belt and select item, at today's sizes
and the foundation's, from the tables below and nui_limits' counts, as the
controllers build their models (nui_slots' cells, the wear table, the
pages).

    python3 tools/nui_w3b_fixtures.py           write the fixtures
    python3 tools/nui_w3b_fixtures.py --check   write nothing; exit 1 when one is stale

Each window's fixture is <name>.fixture.json (today), with the variants
<name>.foundation.fixture.json and the ones the spec names (inventory
empty, belt collapsed). nui_inventory_test checks that the controllers'
models have the same keys and kinds."""
import argparse
import importlib.util
import json
import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WINDOWS = os.path.join(REPO, "assets", "nui", "nui", "windows")


def load_limits():
    sys.modules.setdefault("dbg", types.SimpleNamespace(Tracen=lambda line: None, TraceError=lambda line: None))
    for name in ("player", "item", "skill", "app", "introselect"):
        sys.modules.setdefault(name, None)
    spec = importlib.util.spec_from_file_location("nui_limits", os.path.join(REPO, "assets", "root", "nui_limits.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LIMITS = load_limits()


def read_attach_right():
    """nui_slots.ATTACH_RIGHT as assets/root/nui_slots.py sets it (P15 F-2's
    switch), so the fixtures carry what the windows' models carry."""
    with open(os.path.join(REPO, "assets", "root", "nui_slots.py"), encoding="utf-8") as handle:
        found = re.search(r"^ATTACH_RIGHT = (True|False)\b", handle.read(), re.M)
    return found is not None and found.group(1) == "True"


ATTACH_RIGHT = read_attach_right()
TODAY = LIMITS.read({})
FOUNDATION = LIMITS.foundation()

CELL_KEYS = ("index", "kind", "type", "ref", "icon", "count", "w", "h", "cd_start", "cd_end", "active", "cover",
             "disabled", "locked", "covered", "target", "picked", "unavailable")
INVENTORY = 1  # player.SLOT_TYPE_INVENTORY

# vnum -> (icon, w, h); icons are store paths the item list names.
ITEMS = {
    10: ("/icon/item/00010.tga", 1, 2), 3000: ("/icon/item/03000.tga", 1, 3), 8000: ("/icon/item/08000.tga", 1, 1),
    11200: ("/icon/item/11200.tga", 1, 2), 12200: ("/icon/item/12200.tga", 1, 1), 13000: ("/icon/item/13000.tga", 1, 1),
    14000: ("/icon/item/14000.tga", 1, 1), 15000: ("/icon/item/15000.tga", 1, 1), 16000: ("/icon/item/16000.tga", 1, 1),
    17000: ("/icon/item/17000.tga", 1, 1), 18000: ("/icon/item/18000.tga", 1, 1), 25040: ("/icon/item/25040.tga", 1, 1),
    27001: ("/icon/item/27001.tga", 1, 1), 27002: ("/icon/item/27002.tga", 1, 1), 27003: ("/icon/item/27003.tga", 1, 1),
    28030: ("/icon/item/28000.tga", 1, 1), 28031: ("/icon/item/28001.tga", 1, 1), 28032: ("/icon/item/28002.tga", 1, 1),
    28033: ("/icon/item/28003.tga", 1, 1), 28034: ("/icon/item/28004.tga", 1, 1), 28035: ("/icon/item/28005.tga", 1, 1),
    28036: ("/icon/item/28006.tga", 1, 1), 28037: ("/icon/item/28007.tga", 1, 1), 28038: ("/icon/item/28008.tga", 1, 1),
    28039: ("/icon/item/28009.tga", 1, 1), 28040: ("/icon/item/28010.tga", 1, 1),
    30329: ("/icon/item/30329.tga", 1, 1), 41001: ("/icon/item/41002.tga", 1, 2), 45001: ("/icon/item/41005.tga", 1, 2),
    70043: ("/icon/item/70043.tga", 1, 1), 71027: ("/icon/item/71027.tga", 1, 1), 72723: ("/icon/item/72723.tga", 1, 1),
    73001: ("/icon/item/73001.tga", 1, 1), 1000: ("/icon/item/01000.tga", 1, 3), 20: ("/icon/item/00020.tga", 1, 2),
}


def empty_cell(index):
    return {"index": index, "kind": "", "type": 0, "ref": 0, "icon": "", "count": "", "w": 1, "h": 1,
            "cd_start": 0.0, "cd_end": 0.0, "active": False, "cover": False, "disabled": False, "locked": False,
            "covered": False, "target": "", "picked": False, "unavailable": False}


def item_cell(index, position, vnum, count=1, one=False, **states):
    """A cell as the proxy makes it from SetItemSlot(slot, vnum, count): the
    label shows every count above 0 (CSlotWindow::SetSlotCount); the
    inventory, wear and select item refreshes pass 0 for a count of 1, the
    belt's passes it (one)."""
    icon, w, h = ITEMS[vnum]
    cell = empty_cell(index)
    shown = count if (count > 1 or one) else 0
    cell.update({"kind": "item", "type": INVENTORY, "ref": position, "icon": icon, "w": w, "h": h,
                 "count": str(shown) if shown > 0 else ""})
    cell.update(states)
    return cell


def grid(cols, rows, start, items, targets=None, unavailable=(), one=False):
    """The cells of a cols x rows lean grid whose cell i shows position
    start + i: items {cell: (vnum, count, states)}, then the covered cells
    (nui_slots.mark_covered), the footprint's targets and the unavailable
    cells."""
    cells = [empty_cell(i) for i in range(cols * rows)]
    for index, (vnum, count, states) in items.items():
        cells[index] = item_cell(index, start + index, vnum, count, one, **states)
    for anchor, cell in enumerate(list(cells)):
        if not cell["kind"]:
            continue
        for dy in range(1, cell["h"]):
            below = anchor + dy * cols
            if below < len(cells) and cells[below]["kind"]:
                raise ValueError("cell %d: the item at %d covers it" % (below, anchor))
            if below < len(cells):
                covered = empty_cell(below)
                covered.update({"type": cell["type"], "ref": cell["ref"], "covered": True})
                cells[below] = covered
    for index, state in (targets or {}).items():
        cells[index]["target"] = state
    for index in unavailable:
        cells[index]["unavailable"] = True
    return cells


def wear_cells(limits, group, filled, targets=None):
    """The wear group's cells in wear order, CELL_KEYS plus name: filled
    {name: vnum}."""
    cells = []
    for index, slot in enumerate(LIMITS.wear_group(group, limits)):
        if slot.name in filled:
            cell = item_cell(index, slot.cell, filled[slot.name], 1)
        else:
            cell = empty_cell(index)
        if targets and slot.name in targets:
            cell["target"] = targets[slot.name]
        cell["name"] = slot.name
        cells.append(cell)
    return cells


def money_text(value):
    """The money slot's text as legacy's RefreshStatus writes it
    (uiinventory.py MoneySlotText, NOVA-96): localeInfo.NumberToMoneyString in
    the en locale, dots every three digits and " Yang", while the unit fits
    the slot (under 10 ** 11), then the amount alone."""
    if value <= 0:
        return "0 Yang"
    text = "{:,}".format(int(value)).replace(",", ".")
    return text + " Yang" if value < 10 ** 11 else text


TODAY_WEAR = {"body": 11200, "head": 12200, "foots": 15000, "wrist": 14000, "weapon": 10, "neck": 16000, "ear": 17000,
              "unique1": 71027, "arrow": 8000, "shield": 13000, "belt": 18000}
# The rings with the belt since NOVA-97 (legacy's equipment window; the
# cut's costume sash is not ported, so no cell shows it).
FOUNDATION_WEAR = dict(TODAY_WEAR, unique2=70043, ring1=72723, ring2=27003)


def inventory(limits, page, wear, bag, money, **rest):
    cols, rows = limits.INVENTORY_COLUMNS, limits.INVENTORY_ROWS
    model = {
        "table": limits.WEAR_TABLE_ID,
        "pages": LIMITS.pages(limits),
        "page": page,
        "bag": bag(cols, rows, page * limits.INVENTORY_PAGE_SIZE),
        "bag_cols": cols,
        "wear": wear_cells(limits, "equipment", wear),
        "money": money_text(money),
        "money_value": money,
        "dss_active": False,
        "has_costume": True,
        "has_dss": True,
        "has_mall": True,
        "placed": False,
        # P14b: nothing attached, so an anchor's box covers its item.
        "bag_attaching": False,
        # P15 F-2: nui_slots.ATTACH_RIGHT.
        "attach_right": ATTACH_RIGHT,
        # P15 V-2: the kept board's lists, shown.
        "wear_on": [1], "tabs_on": [1], "bag_on": [1],
    }
    model.update(rest)
    return {"inventory": model}


def today_bag(cols, rows, start):
    return grid(cols, rows, start, {
        0: (10, 1, {}), 2: (3000, 1, {}), 4: (27001, 200, {}), 9: (72723, 1, {"active": True}),
        18: (13000, 1, {"target": "usable"}), 30: (12200, 1, {}), 35: (27002, 3, {}), 40: (25040, 1, {}),
        44: (70043, 1, {}), 23: (28030, 1, {"picked": True})},
        targets={21: "move", 26: "move"})


def hover_bag(cols, rows, start):
    """P14b's hover goldens: a 1x3 glaive and, beside it, a 1x2 sword at the
    page's bottom edge, with 1x1 items around them."""
    return grid(cols, rows, start, {
        30: (27001, 200, {}), 31: (3000, 1, {}), 32: (72723, 1, {}), 37: (10, 1, {}), 33: (12200, 1, {}),
        43: (25040, 1, {}), 44: (28030, 1, {})})


def foundation_bag(cols, rows, start):
    return grid(cols, rows, start, {
        0: (3000, 1, {}), 1: (10, 1, {}), 3: (27001, 2000, {}), 4: (27002, 1999, {}), 11: (72723, 1, {"active": True}),
        25: (12200, 1, {}), 33: (11200, 1, {}), 42: (25040, 1, {}), 44: (28030, 2, {})})


def costume(limits, filled):
    slots = wear_cells(limits, "costume", filled)
    return {"costume": {"table": limits.WEAR_TABLE_ID, "slots": slots,
                        "has_companion": any(cell["name"].startswith("buffi_") for cell in slots),
                        "attach_right": ATTACH_RIGHT, "wear_on": [1]}}


def belt(limits, available, items, expanded=True):
    cols = limits.BELT_COLUMNS
    rows = limits.BELT_INVENTORY_SLOT_COUNT // cols
    cells = grid(cols, rows, limits.BELT_INVENTORY_SLOT_START, items,
                 unavailable=[i for i in range(cols * rows) if i >= available], one=True)
    return {"belt": {"cells": cells, "cols": cols, "expanded": expanded, "attaching": False, "attach_right": ATTACH_RIGHT,
                     "cells_on": [1]}}


def select_item(limits, stones):
    """Legacy's RefreshSlot (uiselectitem.py:74-129): the stones in cell
    order, the rows by legacy's rule (3 under 15, else 3 + (n - 15) // 5
    and one more for a remainder), at most SELECT_ITEM_MAX."""
    count = min(len(stones), limits.SELECT_ITEM_MAX)
    rows = 3 if count < 15 else 3 + (count - 15) // 5 + (1 if count % 5 else 0)
    cols = limits.SELECT_ITEM_COLUMNS
    cells = [empty_cell(i) for i in range(cols * rows)]
    for index, (position, vnum, number) in enumerate(stones[:count]):
        cells[index] = item_cell(index, position, vnum, number)
    return {"select_item": {"cells": cells, "cols": cols, "attach_right": ATTACH_RIGHT}}


STONES = [28030, 28031, 28032, 28033, 28034, 28035, 28036, 28037, 28038, 28039, 28040]


def fixtures():
    return {
        ("inventory", ""): inventory(TODAY, 0, TODAY_WEAR, today_bag, 1999999999),
        ("inventory", "foundation"): inventory(FOUNDATION, 2, FOUNDATION_WEAR, foundation_bag, 2000000000000),
        ("inventory", "empty"): inventory(TODAY, 0, {}, lambda cols, rows, start: grid(cols, rows, start, {}), 0),
        ("inventory", "hover"): inventory(TODAY, 0, TODAY_WEAR, hover_bag, 1999999999),
        ("costume", ""): costume(TODAY, {"costume_body": 41001, "costume_hair": 73001}),
        # The costume body and hair alone, as legacy's costume window since
        # NOVA-97 (the cut's other costume cells are not ported).
        ("costume", "foundation"): costume(FOUNDATION, {"costume_body": 45001, "costume_hair": 73001}),
        # An auto potion in the belt is never active: legacy activates only the
        # bag's cells (uiinventory.py RefreshBagSlotWindow).
        ("belt-inventory", ""): belt(TODAY, 4, {0: (27001, 5, {}), 1: (27002, 1, {}), 3: (72723, 1, {})}),
        ("belt-inventory", "foundation"): belt(FOUNDATION, 4, {0: (27001, 2000, {}), 1: (27002, 1, {}), 3: (72723, 1, {})}),
        ("belt-inventory", "collapsed"): belt(TODAY, 4, {0: (27001, 5, {}), 1: (27002, 1, {})}, expanded=False),
        ("select-item", ""): select_item(TODAY, [(i * 3, STONES[i % len(STONES)], 1 + i % 3) for i in range(7)]),
        ("select-item", "foundation"): select_item(FOUNDATION, [(i, STONES[i % len(STONES)], 1) for i in range(55)]),
    }


def path_of(window, variant):
    name = "%s.%s.fixture.json" % (window, variant) if variant else "%s.fixture.json" % window
    return os.path.join(WINDOWS, window, name)


def text_of(model):
    return json.dumps(model, indent="\t", ensure_ascii=False) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    stale = []
    for (window, variant), model in sorted(fixtures().items()):
        path = path_of(window, variant)
        text = text_of(model)
        old = None
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                old = handle.read()
        if old == text:
            continue
        if args.check:
            stale.append(os.path.relpath(path, REPO))
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print("wrote %s" % os.path.relpath(path, REPO))
    if stale:
        print("stale: %s" % ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
