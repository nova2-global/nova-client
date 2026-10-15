#!/usr/bin/env python3
"""Writes the fixtures of the Wave 4 windows (P16 spec 5, 11.3): the
exchange, the NPC shop, the private shop builder, the safebox and its two
password dialogs, the mall and the equipment view (TRADE), at today's sizes
and the foundation's, from nui_limits' counts and the tables below, as the
controllers build their models (nui_slots' cells, the limits module's
safebox pages and view table). SOCIAL adds its windows' rows to FIXTURES.

    python3 tools/nui_w4_fixtures.py           write the fixtures
    python3 tools/nui_w4_fixtures.py --check   write nothing; exit 1 when one is stale

Each window's fixture is <name>.fixture.json (today), with the variants
<name>.foundation.fixture.json and the ones the spec names. The windows'
tests check that the controllers' models have the same keys and kinds."""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nui_w3b_fixtures as w3b  # noqa: E402

REPO = w3b.REPO
WINDOWS = w3b.WINDOWS
LIMITS = w3b.LIMITS
TODAY = w3b.TODAY
FOUNDATION = w3b.FOUNDATION
LOCALE_EN = os.path.join(REPO, "assets", "locale", "locale", "en")

# player.SLOT_TYPE_* (tools/fixtures/module_constants.json).
SLOT_TYPE_INVENTORY, SLOT_TYPE_SHOP, SLOT_TYPE_EXCHANGE_OWNER, SLOT_TYPE_EXCHANGE_TARGET = 1, 4, 5, 6
SLOT_TYPE_SAFEBOX, SLOT_TYPE_PRIVATE_SHOP, SLOT_TYPE_MALL = 8, 9, 10

empty_cell = w3b.empty_cell


def game_text(key):
    """The en locale_game.txt entry of `key`."""
    return _read_table(os.path.join(LOCALE_EN, "locale_game.txt"))[key]


def _read_table(path):
    table = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle.read().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0]:
                table[parts[0]] = parts[1]
    return table


def name_of(length):
    """A character name of `length` characters (today's 12, the
    foundation's 22)."""
    base = "Partner"
    return (base + "abcdefghijklmnopqrstuvwxyz")[:length]


def typed_cell(index, kind_type, ref, vnum, count=1, **states):
    """A cell as a TypedSlotWindowProxy makes it from SetItemSlot(slot, vnum,
    count): its slot type and ref, the count above 0 (legacy passes 0 for a
    count of 1)."""
    icon, w, h = w3b.ITEMS[vnum]
    cell = empty_cell(index)
    cell.update({"kind": "item", "type": kind_type, "ref": ref, "icon": icon, "w": w, "h": h,
                 "count": str(count) if count > 1 else ""})
    cell.update(states)
    return cell


def typed_grid(cols, rows, kind_type, items, ref=lambda index: index, length=None):
    """The cells of a lean grid of cols x rows (or `length`) cells: items
    {cell: (vnum, count)} with the slot type, then the cells they cover
    (nui_slots.mark_covered: the owner's type and ref)."""
    cells = [empty_cell(i) for i in range(length if length is not None else cols * rows)]
    for index, (vnum, count) in items.items():
        cells[index] = typed_cell(index, kind_type, ref(index), vnum, count)
    for anchor, cell in enumerate(list(cells)):
        if not cell["kind"]:
            continue
        for dy in range(1, cell["h"]):
            below = anchor + dy * cols
            if below >= len(cells):
                continue
            if cells[below]["kind"]:
                raise ValueError("cell %d: the item at %d covers it" % (below, anchor))
            covered = empty_cell(below)
            covered.update({"type": cell["type"], "ref": cell["ref"], "covered": True})
            cells[below] = covered
    return cells


def dotted(value):
    """The exchange's inline money format (uiexchange.py:192-193): dots every
    three digits, no unit."""
    text = str(int(value))
    head = len(text) % 3
    parts = ([text[:head]] if head else []) + [text[i:i + 3] for i in range(head, len(text), 3)]
    return ".".join(parts)


# --- the exchange (spec 5.1.7) ---------------------------------------------------------------

def with_targets(cells, targets):
    """The drop footprint's states on cells (nui_slots.with_states)."""
    for index, state in targets.items():
        cells[index]["target"] = state
    return cells


def exchange(limits, owner, target, owner_money, target_money, name_length, owner_accept=False, target_accept=False,
             accept_down=False, accept_enabled=True, attaching=False, owner_targets=None):
    cols = limits.EXCHANGE_COLUMNS
    n = limits.EXCHANGE_ITEM_MAX_NUM
    rows = n // cols
    return {"exchange": {
        "title": game_text("EXCHANGE_TITLE") % name_of(name_length),
        "cols": cols,
        "owner_cells": with_targets(typed_grid(cols, rows, SLOT_TYPE_EXCHANGE_OWNER, owner), owner_targets or {}),
        "target_cells": typed_grid(cols, rows, SLOT_TYPE_EXCHANGE_TARGET, target),
        "owner_money": dotted(owner_money),
        "target_money": dotted(target_money),
        "owner_money_value": owner_money,
        "target_money_value": target_money,
        "owner_accept": owner_accept,
        "target_accept": target_accept,
        "accept_down": accept_down,
        "accept_enabled": accept_enabled,
        "owner_attaching": attaching,
        "target_attaching": attaching,
    }}


EXCHANGE_OWNER = {0: (10, 1), 1: (3000, 1), 2: (27001, 200), 3: (12200, 1), 7: (27002, 3)}
EXCHANGE_TARGET = {0: (3000, 1), 3: (10, 1), 1: (27003, 200), 2: (25040, 1), 6: (13000, 1)}
EXCHANGE_OWNER_FOUNDATION = {0: (10, 1), 1: (3000, 1), 2: (27001, 2000), 3: (12200, 1), 7: (27002, 1999)}
EXCHANGE_TARGET_FOUNDATION = {0: (3000, 1), 3: (10, 1), 1: (27003, 2000), 2: (25040, 1), 6: (13000, 1)}


def fixtures():
    return {
        ("exchange", ""): exchange(TODAY, EXCHANGE_OWNER, EXCHANGE_TARGET, 9999999, 1234, 12, target_accept=True),
        ("exchange", "foundation"): exchange(FOUNDATION, EXCHANGE_OWNER_FOUNDATION, EXCHANGE_TARGET_FOUNDATION,
                                             1999999999999, 1234, 22, target_accept=True),
        ("exchange", "empty"): exchange(TODAY, {}, {}, 0, 0, 12),
        ("exchange", "accepted"): exchange(TODAY, EXCHANGE_OWNER, EXCHANGE_TARGET, 9999999, 1234, 12, owner_accept=True,
                                           target_accept=True, accept_down=True, accept_enabled=False),
        # A 1x2 sword attached over the owner's cell 6: its footprint on 6 and
        # 10, every cell its own target (P14b, the hit test's sweep).
        ("exchange", "attaching"): exchange(TODAY, EXCHANGE_OWNER, EXCHANGE_TARGET, 9999999, 1234, 12, attaching=True,
                                            owner_targets={6: "move", 10: "move"}),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    stale = []
    for (window, variant), model in sorted(fixtures().items()):
        path = w3b.path_of(window, variant)
        text = w3b.text_of(model)
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
