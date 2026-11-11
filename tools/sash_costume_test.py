"""Tests for the legacy client's sash costume, OLD's wings (NOVA-20 follow-up;
ITEM_COSTUME / COSTUME_SASH2, worn at WEAR_COSTUME_SASH2, wear 27):
python3 -B -m unittest sash_costume_test (from tools/).

The look (the server's PART_SASH while the wings are worn and the wing flag is
on) and item.COSTUME_SLOT_SASH2 are the server's and the C++'s. Here the
legacy costume window (uiinventory.CostumeWindow and uiscript
costumewindow.py) runs over nui_game_support's stand-ins (wave6_support):
- the window has OLD's "SASH WING" cell, COSTUME_START_INDEX + 8 (OLD
  uiscript/costumewindow.py:71, c_Costume_Slot_Sash), on a public slot base
  below the aura cell, and refreshes it with the other costumes
  (COSTUME_SLOT_COUNT 9 runs from wear 19 over wear 27);
- its cell is the inventory's: a use and a hover go to the inventory's legacy
  handlers;
- the aura flag panel's wing box is the switch that shows the wings
  (player.AURA_WING_FLAG_WING, "/aura_wing <flags>");
- its tooltip is the costumes' (OLD's uiToolTip.py has no rule of its own for
  COSTUME_SASH2): the applies and the bonuses, not the sash's absorption;
- the data the client's loaders read (locale/common): the wings' shining
  effects (shiningtable.txt, OLD's CItemManager::LoadShiningTable) and the
  costume scales (item_scale.txt, CItemManager::LoadItemScale), OLD's rows for
  the cut's items in OLD's order (a later row wins, and an item_scale row also
  covers the four vnums after it)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import legacy_foundation_test as lf  # noqa: E402
import wave6_support as w6  # noqa: E402

WING_CELL = w6.EQUIPMENT_START + 27
WING = 48000                    # the cut's "Lucifer Wings", COSTUME_SASH2
COSTUME_TYPE_SASH2 = 8          # OLD's and NEW's ItemData.h
SLOT_BASE = "d:/ymir work/ui/public/Slot_Base.sub"


def wing_world():
    """wave6_support's world with the C++'s names for the wings
    (PythonItemModule.cpp: item.COSTUME_TYPE_SASH2, item.COSTUME_SLOT_SASH2)."""
    world = w6.World()
    item = world.game.modules["item"]
    item.COSTUME_TYPE_SASH2 = COSTUME_TYPE_SASH2
    item.COSTUME_SLOT_SASH2 = WING_CELL
    return world


def costume_uiscript():
    world = wing_world()
    with world.game:
        return lf.read_uiscript(os.path.join(w6.UISCRIPT, "costumewindow.py"))["window"]


def box(x, y, width, height):
    return (x, y, x + width, y + height)


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


class WingCell(unittest.TestCase):
    def setUp(self):
        self.window = costume_uiscript()
        self.slot_window = lf.child(self.window, "CostumeSlot")
        self.slots = dict((slot["index"], slot) for slot in self.slot_window["slot"])

    def test_the_uiscript_has_olds_sash_wing_cell(self):
        self.assertEqual(WING_CELL, w6.COSTUME_START + 8, "OLD's COSTUME_START_INDEX + 8")
        self.assertIn(WING_CELL, self.slots)
        cell = self.slots[WING_CELL]
        self.assertEqual((cell["x"], cell["y"], cell["width"], cell["height"]), (156, 88, 32, 32))

    def test_the_cell_sits_below_the_aura_cell_inside_the_slot_window(self):
        cell = self.slots[WING_CELL]
        aura = self.slots[w6.C_ITEM["COSTUME_SLOT_AURA"]]
        self.assertEqual(cell["x"], aura["x"], "the aura's column")
        self.assertGreaterEqual(cell["y"], aura["y"] + aura["height"])
        self.assertLessEqual(cell["x"] + cell["width"], self.slot_window["width"])
        self.assertLessEqual(cell["y"] + cell["height"], self.slot_window["height"])
        mine = box(cell["x"], cell["y"], cell["width"], cell["height"])
        for index, other in self.slots.items():
            if index != WING_CELL:
                self.assertFalse(overlaps(mine, box(other["x"], other["y"], other["width"], other["height"])), index)

    def test_a_slot_base_stands_under_the_cell(self):
        board = lf.child(self.window, "board")
        bases = [image for image in board["children"] if image.get("name") == "Wing_Base"]
        self.assertEqual(len(bases), 1)
        base = bases[0]
        self.assertEqual(base["type"], "image")
        self.assertEqual(base["image"], SLOT_BASE)
        self.assertEqual((base["x"], base["y"]), (172, 129))
        cell = self.slots[WING_CELL]
        self.assertEqual((base["x"], base["y"]), (self.slot_window["x"] + cell["x"], self.slot_window["y"] + cell["y"]),
                         "under the cell, as the aura's base is under the aura cell")

    def test_the_window_holds_the_cell_and_its_base_above_the_switches(self):
        board = lf.child(self.window, "board")
        switches = [widget for widget in board["children"] if widget.get("type") == "toggle_button"]
        self.assertTrue(switches)
        top_of_switches = min(widget["y"] for widget in switches)
        self.assertLessEqual(129 + 32, top_of_switches)
        self.assertLessEqual(172 + 32, self.window["width"])


class WingWindow(unittest.TestCase):
    def test_the_window_shows_the_worn_wings(self):
        world = wing_world()
        world.game.give(WING_CELL, WING)
        world.game.give(w6.COSTUME_START, w6.BODY_COSTUME)
        _, window = w6.costume_window(world)
        shown = dict((index, slot["vnum"]) for index, slot in window.wndEquip.slots.items() if slot["vnum"])
        self.assertEqual({WING_CELL: WING, w6.COSTUME_START: w6.BODY_COSTUME}, shown)

    def test_a_refresh_takes_them_off_the_window(self):
        world = wing_world()
        world.game.give(WING_CELL, WING)
        inventory, window = w6.costume_window(world)
        world.game.items.pop(WING_CELL)
        with world.game, lf.quiet():
            inventory.RefreshEquipSlotWindow()
        self.assertEqual(window.wndEquip.slots[WING_CELL]["vnum"], 0)

    def test_a_use_of_the_cell_is_the_inventorys_unequip(self):
        world = wing_world()
        world.game.give(WING_CELL, WING)
        inventory, window = w6.costume_window(world)
        del world.game.log[:]
        with world.game, lf.quiet():
            window.wndEquip.fire("use", WING_CELL)
        sent = [args for name, args in world.game.log if name.startswith("net.SendItemUse")]
        self.assertEqual(len(sent), 1)
        self.assertIn(WING_CELL, sent[0])

    def test_a_hover_shows_the_inventorys_tooltip_of_the_cell(self):
        world = wing_world()
        world.game.give(WING_CELL, WING)
        inventory, window = w6.costume_window(world)
        with world.game, lf.quiet():
            window.wndEquip.fire("over_in", WING_CELL)
        calls = [call for call in inventory.tooltipItem.calls if call[0] == "SetInventoryItem"]
        self.assertEqual(calls[-1][1], WING_CELL)

    def test_the_flag_panels_wing_box_switches_the_wings(self):
        """OLD uiInventory.py's wing check box: the wings show while
        AURA_WING_FLAG_WING is set."""
        world = wing_world()
        world.game.give(WING_CELL, WING)
        _, window = w6.costume_window(world)
        with world.game, lf.quiet():
            window.GetChild("Activate3_ON_OFF").click()
        flag, check = window.auraWingChecks[0]
        self.assertEqual(flag, w6.C_PLAYER["AURA_WING_FLAG_WING"])
        self.assertTrue(check.checked)
        del world.game.log[:]
        with world.game, lf.quiet():
            check.OnMouseLeftButtonUp()
        self.assertEqual(world.chat_commands(), ["/aura_wing %d" % (w6.C_PLAYER["AURA_WING_FLAG_ALL"] ^ flag)])


WING_ROW = dict(lf.ITEM_BASE, name="Lucifer Wings", type=28, subtype=COSTUME_TYPE_SASH2, icon="icon/item/48000.tga",
                applies=[["APPLY_MAX_HP", 500]])


class ToolTip(unittest.TestCase):
    def texts(self, sockets, attrs=()):
        corpus_tool, world = w6.tooltip_world({WING: WING_ROW})
        world.game.modules["item"].COSTUME_TYPE_SASH2 = COSTUME_TYPE_SASH2
        texts, error = w6.tooltip_texts(corpus_tool, world, {"context": "AddItemData", "vnum": WING,
                                                              "sockets": sockets, "attrs": list(attrs)})
        self.assertIsNone(error)
        return texts, world.game.modules["localeInfo"]

    def test_wings_show_the_costume_lines(self):
        texts, locale = self.texts([0, 0, 0, 0], attrs=[[1, 1000]])
        self.assertIn("Lucifer Wings", texts)
        self.assertIn(locale.TOOLTIP_MAX_HP(500), texts, "its applies")
        self.assertIn(locale.TOOLTIP_MAX_HP(1000), texts, "its bonuses")

    def test_wings_are_no_sash(self):
        """Socket 0 is no absorption rate on the wings (OLD's rule tests
        COSTUME_TYPE_SASH only)."""
        texts, locale = self.texts([11, w6.SWORD, 0, 0])
        self.assertNotIn(locale.SASH_ABSORB_CHANCE % 11, texts)


COMMON = os.path.join(lf.REPO, "assets", "locale", "locale", "common")
OLD_COMMON = "/home/eddy/new-project/old/client_pack/source/locale/common"
CUT_PROTO = "/home/eddy/new-project/new/nova-server-nui-rt/share/conf/item_proto.txt"
JOBS = ("JOB_WARRIOR", "JOB_ASSASSIN", "JOB_SURA", "JOB_SHAMAN", "JOB_WOLFMAN")


def read_rows(name):
    with open(os.path.join(COMMON, name), "rb") as handle:
        data = handle.read()
    return data, [line.split("\t") for line in data.decode("ascii").split("\n")[:-1]]


def first_vnums(token):
    if "~" in token:
        first, last = token.split("~")
        return list(range(int(first), int(last) + 1))
    return [int(token)]


def cut_items():
    """vnum -> (type, subtype) of the cut's item_proto."""
    kinds = {}
    with open(CUT_PROTO, encoding="utf-8", errors="replace") as handle:
        for row in handle.read().split("\n")[1:]:
            cells = row.split("\t")
            if len(cells) > 3 and cells[0].strip():
                for vnum in first_vnums(cells[0].strip()):
                    kinds[vnum] = (cells[2].strip(), cells[3].strip())
    return kinds


def olds_rows(name, keep):
    with open(os.path.join(OLD_COMMON, name), encoding="latin-1") as handle:
        rows = [[token for token in line.split("\t") if token] for line in handle.read().split("\n")]
    return ["\t".join(row) for row in rows if row and keep(row)]


HAVE_OLD = os.path.isdir(OLD_COMMON) and os.path.isfile(CUT_PROTO)


class ShiningTable(unittest.TestCase):
    """locale/common/shiningtable.txt: the wings' shining effects. Since
    NOVA-176 the table holds the body armors' and body costumes' rows too
    (shining_table_test.py); these tests read the wings' rows."""

    def setUp(self):
        self.data, rows = read_rows("shiningtable.txt")
        self.rows = [row for row in rows if all(48000 <= vnum < 49000 for vnum in first_vnums(row[0]))]

    def test_every_row_is_a_wing_and_its_effects_as_olds_loader_reads_them(self):
        self.assertTrue(self.data.endswith(b"\n"))
        self.assertNotIn(b"\r", self.data)
        self.assertEqual(len(self.rows), 179)
        for row in self.rows:
            self.assertTrue(2 <= len(row) <= 7, row)
            self.assertTrue(all(48000 <= vnum < 49000 for vnum in first_vnums(row[0])), row)
            for effect in row[1:]:
                # OLD writes some with backslashes; the store path takes either.
                self.assertRegex(effect, r"^[Dd]:[/\\]ymir work[/\\][^#]+\.mse(#[A-Za-z0-9 ]+)?$")

    @unittest.skipUnless(HAVE_OLD, "OLD's client pack and the cut's item_proto")
    def test_it_is_olds_rows_for_the_cuts_wings_in_olds_order(self):
        wings = set(vnum for vnum, kind in cut_items().items() if kind == ("ITEM_COSTUME", "COSTUME_SASH2"))
        want = olds_rows("shiningtable.txt", lambda row: any(vnum in wings for vnum in first_vnums(row[0])))
        self.assertEqual(["\t".join(row) for row in self.rows], want)


class ItemScale(unittest.TestCase):
    """locale/common/item_scale.txt: the sashes' and the wings' scale and
    turn per class and sex."""

    def setUp(self):
        self.data, self.rows = read_rows("item_scale.txt")

    def test_every_row_is_one_the_loader_takes(self):
        self.assertTrue(self.data.endswith(b"\n"))
        self.assertNotIn(b"\r", self.data)
        # OLD's rows for the cut's items (1990) and for the glowing sashes'
        # models (234 rows of 851xx and 861xx, NOVA-20).
        self.assertEqual(len(self.rows), 2224)
        for row in self.rows:
            self.assertEqual(len(row), 9, row)
            self.assertIn(row[1], JOBS)
            self.assertIn(row[2], ("M", "F"))
            for number in row[3:]:
                self.assertRegex(number, r"^-?[0-9]+(\.[0-9]+)?$")
            vnum = int(row[0])
            self.assertTrue(48000 <= vnum < 49000 or 85000 <= vnum < 87000, row)

    def test_the_wings_and_the_sashes_have_rows_for_every_class_and_sex(self):
        rows = set((int(row[0]), row[1], row[2]) for row in self.rows)
        for vnum in (WING, w6.SASH):
            for job in JOBS[:4]:
                for sex in ("M", "F"):
                    self.assertIn((vnum, job, sex), rows)

    @unittest.skipUnless(HAVE_OLD, "OLD's client pack and the cut's item_proto")
    def test_it_is_olds_rows_for_the_cuts_items_in_olds_order(self):
        items = cut_items()
        # The glowing sashes' model vnums (851xx, 861xx) are not in the cut's
        # proto: a sash of 19% absorption or more draws them (part + 100).
        glow = set(range(85101, 85200)) | set(range(86101, 86200))
        want = olds_rows("item_scale.txt", lambda row: row[0].isdigit() and (int(row[0]) in items or int(row[0]) in glow))
        self.assertEqual(["\t".join(row) for row in self.rows], want)


if __name__ == "__main__":
    unittest.main()
