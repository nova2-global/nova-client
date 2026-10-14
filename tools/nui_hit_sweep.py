"""The slot grids' hit map (P14b): reads `nuitool snap --sweep` output and
checks the rule of docs/ui/AUTHORING.md "Slot grids" at every dp of it.

- No dead zones: each cell owns its border box grown by half the gap to each
  neighbor that lies within MAX_GAP_DP of it on that side (in its group: the
  same nui-slot-grid, else the same container), and every point of that
  region must reach a cell.
- Hover per item: a point there must reach the cell's owner, which is the
  cell itself, or, for a cell an item covers (class is-covered) inside an
  anchor's box (the anchor's box reaches over its item at rest), that
  anchor; while the grid is attaching (is-attaching), every cell is its own.

A point that lies in two regions (an exact boundary) may reach either owner.
Points outside every region are not checked (beyond a grid's edge, past a
wide gap such as the taskbar's expand button, an empty wear place).

    python3 tools/nui_hit_sweep.py <sweep.json>...   prints each file's verdict
"""
import json
import sys

# The widest gap that still counts two cells as neighbors, in dp: the
# modern pitch's 4dp and classic's uneven wear places stay under it, a
# control between two cells (the taskbar's expand button) does not.
MAX_GAP_DP = 8.0


def runs(row):
    """A row's [value, count, ...] runs as one value per point."""
    out = []
    for i in range(0, len(row), 2):
        out += [row[i]] * row[i + 1]
    return out


def _inside(box, x, y):
    return box[0] <= x <= box[0] + box[2] and box[1] <= y <= box[1] + box[3]


def _span_overlap(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0) > 0


def regions(sweep):
    """{cell index: [x0, y0, x1, y1]}: each cell's box grown by half the gap
    to its neighbor on each side (none: not grown)."""
    dp = float(sweep["dp"])
    limit = MAX_GAP_DP * dp + 0.01
    cells = sweep["cells"]
    out = {}
    for cell in cells:
        x, y, w, h = cell["box"]
        grow = [0.0, 0.0, 0.0, 0.0]  # left, top, right, bottom
        for other in cells:
            if other is cell or other["group"] != cell["group"]:
                continue
            ox, oy, ow, oh = other["box"]
            if _span_overlap(y, y + h, oy, oy + oh):
                gap = ox - (x + w)
                if 0 < gap <= limit and (grow[2] == 0 or gap / 2 < grow[2]):
                    grow[2] = gap / 2
                gap = x - (ox + ow)
                if 0 < gap <= limit and (grow[0] == 0 or gap / 2 < grow[0]):
                    grow[0] = gap / 2
            if _span_overlap(x, x + w, ox, ox + ow):
                gap = oy - (y + h)
                if 0 < gap <= limit and (grow[3] == 0 or gap / 2 < grow[3]):
                    grow[3] = gap / 2
                gap = y - (oy + oh)
                if 0 < gap <= limit and (grow[1] == 0 or gap / 2 < grow[1]):
                    grow[1] = gap / 2
        out[cell["index"]] = [x - grow[0], y - grow[1], x + w + grow[2], y + h + grow[3]]
    return out


def owners(sweep):
    """{cell index: owner index}: a covered cell inside an anchor's box is
    that anchor's (P14b: at rest the anchor covers its item); any other cell
    its own."""
    cells = sweep["cells"]
    out = {}
    for cell in cells:
        owner = cell["index"]
        if "is-covered" in cell["classes"].split():
            x, y, w, h = cell["box"]
            cx, cy = x + w / 2.0, y + h / 2.0
            for other in cells:
                if other is cell or other["group"] != cell["group"] or "is-covered" in other["classes"].split():
                    continue
                if _inside(other["box"], cx, cy):
                    owner = other["index"]
                    break
        out[cell["index"]] = owner
    return out


def check(sweep):
    """{"points", "dead", "wrong", "examples"}: the points of the cells'
    regions, those that reached no cell, those that reached another cell
    than the owner, and up to ten of each as [x, y, reached, wanted]."""
    region = regions(sweep)
    owner = owners(sweep)
    report = {"cells": len(sweep["cells"]), "points": 0, "dead": 0, "wrong": 0, "examples": []}
    if not sweep["cells"]:
        return report
    ox, oy = sweep["origin"]
    step = float(sweep["step"])
    for j, row in enumerate(sweep["hits"]):
        y = oy + (j + 0.5) * step
        for i, reached in enumerate(runs(row)):
            if reached == -2:
                continue
            x = ox + (i + 0.5) * step
            wanted = set(owner[c] for c, r in region.items() if r[0] <= x <= r[2] and r[1] <= y <= r[3])
            if not wanted:
                continue
            report["points"] += 1
            if reached < 0:
                report["dead"] += 1
            elif owner.get(reached, reached) not in wanted and reached not in wanted:
                report["wrong"] += 1
            else:
                continue
            if len(report["examples"]) < 10:
                report["examples"].append([round(x, 1), round(y, 1), reached, sorted(wanted)])
    return report


def item_areas(sweep):
    """{anchor index: [x0, y0, x1, y1]}: each anchor's box joined with the
    boxes of the covered cells it owns (an item's whole area, gaps
    included)."""
    owner = owners(sweep)
    boxes = dict((cell["index"], cell["box"]) for cell in sweep["cells"])
    out = {}
    for index, anchor in owner.items():
        if index == anchor:
            continue
        a = out.get(anchor) or [boxes[anchor][0], boxes[anchor][1], boxes[anchor][0] + boxes[anchor][2],
                                boxes[anchor][1] + boxes[anchor][3]]
        x, y, w, h = boxes[index]
        out[anchor] = [min(a[0], x), min(a[1], y), max(a[2], x + w), max(a[3], y + h)]
    return out


# P14b's hover fixture (inventory.hover.fixture.json): a 1x3 glaive anchored
# at bag cell 31 over 36 and 41, a 1x2 sword at 37 over 42, a 200 stack at
# 30. Each path is a line between the middles of two cells, (cell, cell),
# swept at one point per dp.
HOVER_PATHS = {
    "glaive-down": (31, 41),      # its anchor, two gaps, its two covered cells
    "sword-down": (37, 42),       # its anchor, one gap, its covered cell
    "across-middle": (36, 37),    # the glaive's middle cell to the sword's anchor
    "across-bottom": (41, 42),    # the glaive's last cell to the sword's covered one
    "stack-to-glaive": (30, 31),  # a 1x1 neighbor to the glaive's anchor
}


def hover_path(sweep, start, end, prefix="inv-bag-"):
    """The cells RmlUi's hit test reaches along the line from the middle of
    cell `prefix + start` to the middle of `prefix + end` (an anchor's middle
    is its first cell's, the size of a covered cell), one entry per change:
    the cell's number after `prefix`, or None for no cell."""
    by_id = dict((cell["id"], cell) for cell in sweep["cells"])
    number = dict((cell["index"], int(cell["id"][len(prefix):])) for cell in sweep["cells"] if cell["id"].startswith(prefix))
    size = min(min(cell["box"][2], cell["box"][3]) for cell in sweep["cells"] if cell["id"].startswith(prefix))

    def middle(n):
        x, y = by_id[prefix + str(n)]["box"][:2]
        return x + size / 2.0, y + size / 2.0

    (ax, ay), (bx, by) = middle(start), middle(end)
    ox, oy = sweep["origin"]
    step = float(sweep["step"])
    rows = [runs(row) for row in sweep["hits"]]
    count = int(max(abs(bx - ax), abs(by - ay)) / step)
    path = []
    for k in range(count + 1):
        x = ax + (bx - ax) * k / max(count, 1)
        y = ay + (by - ay) * k / max(count, 1)
        i, j = int((x - ox) / step), int((y - oy) / step)
        reached = rows[j][i]
        cell = number.get(reached) if reached >= 0 else None
        if not path or path[-1] != cell:
            path.append(cell)
    return path


def hover_paths(sweep):
    return dict((name, hover_path(sweep, a, b)) for name, (a, b) in sorted(HOVER_PATHS.items()))


def main(argv):
    status = 0
    for path in argv[1:]:
        with open(path, encoding="utf-8") as handle:
            report = check(json.load(handle))
        ok = report["dead"] == 0 and report["wrong"] == 0
        status |= 0 if ok else 1
        print("%s %s: %d cells, %d points, %d dead, %d wrong %s" % ("ok" if ok else "FAIL", path, report["cells"], report["points"],
                                                                  report["dead"], report["wrong"], report["examples"][:3]))
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv))
