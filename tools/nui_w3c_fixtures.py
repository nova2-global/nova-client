#!/usr/bin/env python3
"""Writes the fixtures of the Wave 3c windows (P15 spec 4.6.3, 5.6, 6.6): the
character window (one per tab, the foundation's of each, no guild, the hover
cases), the dragon soul inventory and the dragon soul refine, at today's sizes
and the foundation's, from the tables below and nui_limits' counts, as the
controllers build their models (nui_slots' cells, the limits' slot lists).

    python3 tools/nui_w3c_fixtures.py           write the fixtures
    python3 tools/nui_w3c_fixtures.py --check   write nothing; exit 1 when one is stale

Each window's fixture is <name>.fixture.json, with the variants
<name>.<variant>.fixture.json. nui_character_test (and the dragon soul
windows' tests) check that the controllers' models have the same keys and
kinds. Times are seconds of the NovaUI clock at nuitool snap's default
--time 1."""
import argparse
import json
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

INVENTORY, SKILL, EMOTION = 1, 2, 3   # player.SLOT_TYPE_*
DRAGON_SOUL_TYPE = 11                 # player.SLOT_TYPE_DRAGON_SOUL_INVENTORY
ART_FOLDER = "/locale/en/ui/windows/"
ART = (("tab_1", "tab_1.sub"), ("tab_2", "tab_2.sub"), ("tab_3", "tab_3.sub"), ("tab_4", "tab_4.sub"),
       ("level", "label_level.sub"), ("cur_exp", "label_cur_exp.sub"), ("last_exp", "label_last_exp.sub"),
       ("std", "label_std.sub"), ("uppt", "label_uppt.sub"), ("std_item1", "label_std_item1.sub"),
       ("std_item2", "label_std_item2.sub"), ("ext", "label_ext.sub"), ("ext_item1", "label_ext_item1.sub"),
       ("ext_item2", "label_ext_item2.sub"))
SKILL_ICON = "d:/ymir work/ui/skill/warrior/%s_%02d.sub"
SUPPORT_ICON = "d:/ymir work/ui/skill/common/support/%s.sub"
# The warrior's first group (playerSettingModule SKILL_INDEX_DICT, the skill
# table's icon names): slot -> (skill index, icon name).
WARRIOR = {1: (1, "samyeon"), 2: (2, "palbang"), 3: (3, "jeongwi"), 4: (4, "geomgyeong"), 5: (5, "tanhwan")}
# emotion.py ICON_DICT (EMOTION_VERSION 2): 18 solo, 3 mutual.
EMOTION_ICONS = {
    1: "d:/ymir work/ui/game/windows/emotion_clap.sub", 2: "/icon/action/congratulation.tga",
    3: "/icon/action/forgive.tga", 4: "/icon/action/angry.tga", 5: "/icon/action/attractive.tga",
    6: "/icon/action/sad.tga", 7: "/icon/action/shy.tga", 8: "/icon/action/cheerup.tga", 9: "/icon/action/banter.tga",
    10: "/icon/action/joy.tga", 11: "d:/ymir work/ui/game/windows/emotion_cheers_1.sub",
    12: "d:/ymir work/ui/game/windows/emotion_cheers_2.sub", 13: "/icon/action/dance1.tga", 14: "/icon/action/dance2.tga",
    15: "/icon/action/dance3.tga", 16: "/icon/action/dance4.tga", 17: "/icon/action/dance5.tga", 18: "/icon/action/dance6.tga",
    51: "d:/ymir work/ui/game/windows/emotion_kiss.sub", 52: "d:/ymir work/ui/game/windows/emotion_french_kiss.sub",
    53: "d:/ymir work/ui/game/windows/emotion_slap.sub",
}
QUEST_ICON = "d:/ymir work/ui/game/quest/questicon/%s.sub"
QUEST_DEFAULT_ICON = "/season1/icon/scroll_open.tga"
# locale_game.txt (en): the plain entries a fixture shows as legacy's code makes them.
UNLIMITED = "No time limit."
GROUP_NAMES = ("Body", "Mental", "Riding")
JOB_LABEL = "Warrior · Body"


def empty_cell(index):
    return w3b.empty_cell(index)


# --- the character window -----------------------------------------------------------------

def art():
    return dict((key, ART_FOLDER + name) for key, name in ART)


def skill_cell(index, slot, skill_index=0, icon_name="", grade=0, label="", cover=True, unavailable=False,
               cooldown=None, active=False, button=False, step=20):
    """An active grid's cell as nui_character builds it: kind skill, the
    grade's icon, the label, the cover (disabled in the columns that are not
    the skill's grade), a cooldown span, the active state, the plus button."""
    cell = empty_cell(index)
    if skill_index:
        cell.update({"kind": "skill", "type": SKILL, "ref": slot, "icon": SKILL_ICON % (icon_name, min(grade, 2) + 1),
                     "count": label, "cover": cover, "unavailable": cover and unavailable, "active": active})
        if cooldown:
            cell["cd_start"], cell["cd_end"] = cooldown
    cell.update({"slot": slot, "button": bool(button and skill_index), "col": (slot - 1) // step})
    return cell


def skills(limits, rows):
    """The active grid's cells in skill_active_slots() order: rows {slot:
    (grade, label, options)} for the skills of WARRIOR; a skill shows in its
    grade's column (grade 3 in the last), the other columns with count 0 and
    a disabled cover."""
    step = limits.SKILL_GRADE_STEP_COUNT
    columns = limits.SKILL_GRADE_COLUMNS
    cells = []
    for index, slot in enumerate(LIMITS.skill_active_slots(limits)):
        base, column = (slot - 1) % step + 1, (slot - 1) // step
        if base not in WARRIOR or base not in rows:
            cells.append(skill_cell(index, slot, step=step))
            continue
        skill_index, icon = WARRIOR[base]
        grade, label, options = rows[base]
        own = min(grade, columns - 1) == column
        cells.append(skill_cell(index, slot, skill_index, icon, column, label if own else "", True, not own,
                                options.get("cooldown") if own else None, bool(options.get("active")) and own,
                                options.get("button", False) and column == 0, step))
    return cells


def support(limits, rows):
    """The support grid's cells from 101: rows {slot: (icon name, label,
    cover)}."""
    start = limits.SKILL_SUPPORT_SLOT_START
    cells = []
    for index in range(limits.SKILL_SUPPORT_SLOTS):
        slot = start + index
        cell = empty_cell(index)
        if slot in rows:
            name, label, cover = rows[slot]
            cell.update({"kind": "skill", "type": SKILL, "ref": slot, "icon": SUPPORT_ICON % name, "count": label,
                         "cover": cover})
        cell.update({"slot": slot, "button": False})
        cells.append(cell)
    return cells


def emotes(limits, kind, filled=True):
    cells = []
    for index, slot in enumerate(LIMITS.emote_slots(kind, limits)):
        cell = empty_cell(index)
        if filled and slot in EMOTION_ICONS:
            cell.update({"kind": "emotion", "type": EMOTION, "ref": slot, "icon": EMOTION_ICONS[slot], "cover": True})
        cell["slot"] = slot
        cells.append(cell)
    return cells


def quest_rows(limits, quests):
    """The quest rows and their cells: quests [(name, icon, counter, clock)]
    with clock ("run", prefix, end), ("over", prefix, end: a run whose end
    has passed, its clock_over set as the countdown's end sets it) or
    ("text", text)."""
    rows, cells = [], []
    for row in range(limits.QUEST_ROWS):
        entry = {"row": row, "shown": False, "name": "", "icon": "", "counter": "", "clock_text": "", "clock_prefix": "",
                 "clock_end": 0.0, "clock_over": False}
        cell = empty_cell(row)
        cell.update({"slot": row, "base": True})
        if row < len(quests):
            name, icon, counter, clock = quests[row]
            entry.update({"shown": True, "name": name, "icon": icon, "counter": counter})
            if clock[0] == "text":
                entry["clock_text"] = clock[1]
            else:
                entry["clock_prefix"], entry["clock_end"] = clock[1], clock[2]
                entry["clock_over"] = clock[0] == "over"
            cell.update({"kind": "icon", "type": 0, "ref": row, "icon": icon})
        rows.append(entry)
        cells.append(cell)
    return rows, cells


def character(limits, tab, values=None, guild=True, skill_rows=None, support_rows=None, quests=(), scroll=None,
              emotes_filled=True):
    model = {
        "tab": tab,
        "panel_status": [1] if tab == "STATUS" else [],
        "panel_skill": [1] if tab == "SKILL" else [],
        "panel_emoticon": [1] if tab == "EMOTICON" else [],
        "panel_quest": [1] if tab == "QUEST" else [],
        "placed": False,
        "art": art(),
        "attach_right": w3b.ATTACH_RIGHT,
        "face": "/icon/face/warrior_m.tga",
        "name": "Kalinka",
        "guild": "Nova Riders" if guild else "",
        "has_guild": bool(guild),
        # The modern looks' class chip (nui_character.job_label): the warrior, group 1.
        "job": JOB_LABEL,
        "level": "99", "exp": "2147483647", "exp_rest": "1234567890", "hp": "99999/99999", "sp": "99999/99999",
        "st": "90", "dx": "90", "ht": "90", "iq": "90", "att": "999-999", "def": "999", "matt": "999-999", "mdef": "999",
        "aspd": "999", "mspd": "999", "cspd": "999", "er": "999",
        "stat_points": "999", "stat_points_shown": True,
        "groups": [{"index": i, "label": GROUP_NAMES[i], "shown": True, "down": i == 0, "col": i} for i in range(3)],
        "group_name": "", "group_name_shown": False,
        "active_points": "3", "support_points": "0", "support_points_shown": False,
        "skills": skills(limits, skill_rows or {}),
        "support": support(limits, support_rows or {}),
        "support_cols": limits.SKILL_SUPPORT_COLUMNS,
        "emote_cols": limits.EMOTE_COLUMNS,
        "tabs_on": [1],
        "solo": emotes(limits, "solo", emotes_filled),
        "dual": emotes(limits, "dual", emotes_filled),
        "quest_scroll_shown": scroll is not None,
        "quest_scroll_pos": scroll if scroll is not None else 0.0,
    }
    for suffix in ("ht", "iq", "st", "dx"):
        model["plus_" + suffix] = True
        model["minus_" + suffix] = True
    model["quests"], model["quest_cells"] = quest_rows(limits, list(quests))
    model.update(values or {})
    return {"character": model}


# The cooldown runs from -1 to 4, so at snap's --time 1 it shows 60% left, as
# the taskbar's fixture does: a sweep whose edge shows in the goldens.
TODAY_SKILLS = {1: (0, "1", {"button": True}), 2: (0, "17", {"button": True}), 3: (1, "m5", {"active": True}),
                4: (2, "g9", {"cooldown": (-1.0, 4.0)}), 5: (3, "p", {})}
# The foundation's sage grade (D19): grade 3 with its level, grade 4 "s", at level 50.
FOUNDATION_SKILLS = {1: (0, "1", {"button": True}), 2: (0, "17", {"button": True}), 3: (1, "m5", {"active": True}),
                     4: (3, "p7", {"cooldown": (-1.0, 4.0)}), 5: (4, "s", {})}
SUPPORT = {101: ("combo", "2", True), 104: ("mining", "7", False)}
FOUNDATION_STATUS = {"level": "150", "exp": "1234567890123", "exp_rest": "9876543210987", "hp": "999999/999999",
                     "sp": "999999/999999"}
QUESTS = (
    ("Biologist's Request", QUEST_ICON % "level_24", "Wolf teeth : 3", ("run", "Time left : ", 126.0)),
    ("The Lost Ring", QUEST_DEFAULT_ICON, "", ("over", "Time left : ", 0.5)),
    ("A Letter for Mother", QUEST_ICON % "level_14", "Letters : 1", ("text", UNLIMITED)),
    ("Old Friends", QUEST_DEFAULT_ICON, "", ("text", UNLIMITED)),
    ("Training Grounds", QUEST_ICON % "level_25", "", ("text", UNLIMITED)),
)


def character_fixtures():
    found = {}
    for limits, suffix, status, rows in ((TODAY, "", {}, TODAY_SKILLS), (FOUNDATION, "foundation", FOUNDATION_STATUS,
                                                                          FOUNDATION_SKILLS)):
        def name(variant):
            # A golden case's variant is letters, digits and hyphens (check_nui_snapshots).
            return "-".join(part for part in (variant, suffix) if part)
        found[("character", name(""))] = character(limits, "STATUS", status)
        found[("character", name("skill"))] = character(limits, "SKILL", status, skill_rows=rows, support_rows=SUPPORT)
        found[("character", name("emoticon"))] = character(limits, "EMOTICON", status)
        found[("character", name("quest"))] = character(limits, "QUEST", status, quests=QUESTS, scroll=0.5)
    found[("character", "noguild")] = character(TODAY, "STATUS", guild=False)
    found[("character", "hover")] = character(TODAY, "SKILL", skill_rows=TODAY_SKILLS, support_rows=SUPPORT)
    return found


# --- the dragon soul windows (P15 spec 5.3, 6.3; DRAGON SOUL's documents bind them) -------------

def ds_icon(vnum):
    """A dragon soul's icon: one per type, grade and step (the item list)."""
    return "/icon/item/%d.tga" % (vnum // 100 * 100)


def ds_cell(index, vnum, ref, cell_type=DRAGON_SOUL_TYPE, **states):
    cell = empty_cell(index)
    cell.update({"kind": "item", "type": cell_type, "ref": ref, "icon": ds_icon(vnum)})
    cell.update(states)
    return cell


def dragon_soul(limits, deck, activated, bag, equip, kind=0, grade=3, equip_states=None):
    size = limits.DRAGON_SOUL_PAGE_SIZE
    start = limits.DRAGON_SOUL_EQUIPMENT_SLOT_START
    first = limits.DRAGON_SOUL_EQUIPMENT_FIRST_SIZE
    base = kind * limits.DRAGON_SOUL_PAGE_COUNT * size + grade * size
    cells = [empty_cell(i) for i in range(size)]
    for index, (vnum, states) in bag.items():
        cells[index] = ds_cell(index, vnum, base + index, **states)
    equipment = []
    for sub in range(first):
        position = start + deck * first + sub
        if sub in equip:
            vnum, states = equip[sub]
            cell = ds_cell(sub, vnum, position, INVENTORY, **states)
        else:
            cell = empty_cell(sub)
        cell.update((equip_states or {}).get(sub, {}))
        cell["sub"] = sub
        equipment.append(cell)
    return {"dragon_soul": {
        "placed": False, "attach_right": w3b.ATTACH_RIGHT,
        "kinds": [{"index": i, "label": "@ui.DRAGONSOUL_TAP_TITLE_%d" % (i + 1), "down": i == kind}
                  for i in range(limits.DRAGON_SOUL_KIND_COUNT)],
        "kind": kind, "kind_title": "@ui.DRAGONSOUL_TAP_TITLE_%d" % (kind + 1),
        "grades": [{"index": i, "label": "@ui.DRAGONSOUL_PAGE_BUTTON_%d" % (i + 1), "down": i == grade}
                   for i in range(limits.DRAGON_SOUL_PAGE_COUNT)],
        "grade": grade,
        "decks": [{"index": i, "label": LIMITS.ROMAN[i], "down": i == deck}
                  for i in range(limits.DRAGON_SOUL_EQUIPMENT_PAGE_COUNT)],
        "deck": deck, "activated": activated,
        "bag": cells, "bag_cols": limits.DRAGON_SOUL_COLUMNS,
        "equip": equipment,
        # V-2b: the kept board's wrappers, one entry while it shows.
        "deck_on": [1], "kinds_on": [1], "grades_on": [1], "bag_on": [1],
    }}


# Antique dragon souls (grade 3) of kind 0 (type 11), steps 0 to 4 and strengths 0 to 3.
DS_BAG = {0: (113000, {}), 1: (113110, {}), 2: (113220, {}), 3: (113330, {}), 4: (113400, {"disabled": True}),
          8: (113010, {"active": True}), 9: (113120, {}), 16: (113200, {})}
DS_EQUIP = {0: (113300, {"active": True}), 1: (123310, {"active": True}), 2: (133300, {"active": True}),
            3: (143300, {"active": True}), 4: (153300, {"active": True})}


def ds_refine(limits, mode, cells, lock, fee, fee_value, result=None):
    """The refine window: cells {index: (vnum, ghost)}; the cells at or past
    the lock index are closed."""
    material = []
    for index in range(limits.DRAGON_SOUL_REFINE_CELLS):
        cell = empty_cell(index)
        if index in cells:
            vnum, ghost = cells[index]
            # A placed item keeps its inventory window's slot type (a refine
            # stone comes from the inventory) and its position there.
            placed_type = DRAGON_SOUL_TYPE if vnum >= 110000 else INVENTORY
            cell.update({"kind": "icon" if ghost else "item", "type": 0 if ghost else placed_type,
                         "ref": index if ghost else 100 + index, "icon": ds_icon(vnum) if vnum >= 110000 else
                         "/icon/item/%05d.tga" % vnum})
            if not ghost:
                cell["count"] = "1"
        cell.update({"closed": index >= lock, "ghost": bool(index in cells and cells[index][1])})
        material.append(cell)
    results = [empty_cell(i) for i in range(limits.DRAGON_SOUL_RESULT_CELLS)]
    if result is not None:
        results[0] = ds_cell(0, result, 200)
    return {"ds_refine": {
        "placed": False, "attach_right": w3b.ATTACH_RIGHT, "mode": mode,
        "modes": [{"name": name, "label": label, "down": name == mode}
                  for name, label in (("grade", "@ui.GRADE_SELECT"), ("step", "@ui.STEP_SELECT"),
                                      ("strength", "@ui.STRENGTH_SELECT"))],
        "cells": material, "cells_cols": limits.DRAGON_SOUL_REFINE_COLUMNS,
        "result": results, "result_cols": limits.DRAGON_SOUL_RESULT_COLUMNS, "fee": fee, "fee_value": fee_value,
    }}


def _with(table, more):
    found = dict(table)
    found.update(more)
    return found


def dragon_soul_fixtures():
    return {
        ("dragon-soul", ""): dragon_soul(TODAY, 0, True, DS_BAG, DS_EQUIP),
        ("dragon-soul", "deck2"): dragon_soul(TODAY, 1, False, DS_BAG, {}),
        ("dragon-soul", "foundation"): dragon_soul(FOUNDATION, 0, True, DS_BAG, DS_EQUIP),
        ("dragon-soul", "hover"): dragon_soul(TODAY, 0, True, DS_BAG, DS_EQUIP),
        # A dragon soul picked from the bag (cell 9, its own cell marked) over
        # the deck's empty sub 1 cell, where it would go (a single slot's
        # footprint: "move" on the hovered cell).
        ("dragon-soul", "attaching"): dragon_soul(TODAY, 0, False, _with(DS_BAG, {9: (113120, {"picked": True})}),
                                                  {0: (113300, {})}, equip_states={1: {"target": "move"}}),
        ("dragon-soul-refine", ""): ds_refine(TODAY, "grade", {0: (113000, False), 1: (113000, False), 2: (113000, True)},
                                              3, "100.000 Yang", 100000),
        ("dragon-soul-refine", "step"): ds_refine(TODAY, "step", {0: (113300, False)}, 1, "50.000 Yang", 50000),
        ("dragon-soul-refine", "strength"): ds_refine(TODAY, "strength", {0: (100300, False), 1: (113000, False)}, 2,
                                                      "10.000 Yang", 10000),
        # After a refine: legacy's __Initialize (the grade mode's lock at 1)
        # and the result cell from the server's position.
        ("dragon-soul-refine", "result"): ds_refine(TODAY, "grade", {}, 1, "0 Yang", 0, result=114000),
        ("dragon-soul-refine", "foundation"): ds_refine(FOUNDATION, "grade", {0: (113000, False), 1: (113000, False),
                                                                               2: (113000, True)}, 3,
                                                        "1.999.999.999.999 Yang", 1999999999999),
        ("dragon-soul-refine", "hover"): ds_refine(TODAY, "grade", {0: (113000, False), 1: (113000, False),
                                                                     2: (113000, True)}, 3, "100.000 Yang", 100000),
    }


def fixtures(windows=None):
    found = {}
    found.update(character_fixtures())
    found.update(dragon_soul_fixtures())
    if windows is not None:
        found = dict((key, value) for key, value in found.items() if key[0] in windows)
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--window", action="append", help="only this window's fixtures (repeatable)")
    args = parser.parse_args(argv)
    stale = []
    pending = set()
    for (window, variant), model in sorted(fixtures(args.window).items()):
        # A window whose document is not written yet (DRAGON SOUL's, while
        # CHARACTER works) gets its fixtures with its document.
        if not os.path.isfile(os.path.join(WINDOWS, window, window + ".rml")):
            pending.add(window)
            continue
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
    if pending:
        print("pending (no document yet): %s" % ", ".join(sorted(pending)))
    if stale:
        print("stale: %s" % ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
