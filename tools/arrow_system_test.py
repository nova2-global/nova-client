"""Tests for the legacy client's new arrow system (wave 6, chunk Y; NOVA-19,
OLD's __NEW_ARROW_SYSTEM__): python3 -B -m unittest arrow_system_test (from
tools/).

The C++ half (item.WEAPON_UNLIMITED_ARROW, the arrow type part, the bow
motion mode while a quiver is worn, chr.MOTION_MODE_BOW_SPECIAL) is chunk
C's; the quiver's rules are chunk SA's. Here:
- uitooltip: a quiver that counts in real time shows its end under its
  limits (OLD uiToolTip.py:1433-1446); a first-use quiver (NEW's protos)
  shows its time once, through the limits every first-use item shows; an
  ordinary arrow shows no time;
- playersettingmodule: both assassins register OLD's bow-with-a-quiver
  motion mode (OLD playerSettingModule.py:1576-1590) from their bow folder,
  with OLD's attack_special.msa (tools/old_art.py took it, and the
  animation it names, from OLD's client); no other race registers it;
- the inventory's arrow cell (wear 9) takes the quiver as it takes arrows."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import legacy_foundation_test as lf  # noqa: E402
import old_content  # noqa: E402
import wave6_support as w6  # noqa: E402

CLOCK = 1700000000
DAY = 86400
# nui_tooltip_corpus.LIMITS: REAL_TIME 7, REAL_TIME_FIRST_USE 8.
LIMIT_REAL_TIME, LIMIT_FIRST_USE = 7, 8
QUIVER_ROW = dict(lf.ITEM_BASE, name="Arrows Quiver", type=1, subtype=9, wear=1 << 9, values=[0, 0, 0, 25, 0, 0],
                  limits=[[LIMIT_REAL_TIME, DAY], [0, 0]], icon="icon/item/79501.tga")
ARROW = 8000
ARROW_ROW = dict(QUIVER_ROW, name="Wooden Arrow", subtype=6, icon="icon/item/08000.tga")


class ToolTip(unittest.TestCase):
    def texts(self, rows, vnum, socket0):
        corpus_tool, world = w6.tooltip_world(rows)
        texts, error = w6.tooltip_texts(corpus_tool, world, {"context": "AddItemData", "vnum": vnum,
                                                              "sockets": [socket0, 0, 0, 0], "clock": CLOCK})
        self.assertIsNone(error)
        return texts, world.game.modules["localeInfo"]

    def time_lines(self, texts, locale):
        return [text for text in texts if text.startswith(locale.LEFT_TIME)]

    def test_a_real_time_quiver_shows_its_end(self):
        texts, locale = self.texts({w6.QUIVER: QUIVER_ROW}, w6.QUIVER, CLOCK + 2 * DAY + 3600)
        self.assertEqual(self.time_lines(texts, locale), [locale.LEFT_TIME + ": " + locale.RTSecondToDHMS(2 * DAY + 3600)])

    def test_an_arrow_shows_no_time(self):
        texts, locale = self.texts({ARROW: ARROW_ROW}, ARROW, CLOCK + DAY)
        self.assertEqual(self.time_lines(texts, locale), [])

    def test_a_first_use_quiver_shows_its_time_once(self):
        row = dict(QUIVER_ROW, limits=[[LIMIT_FIRST_USE, DAY], [0, 0]])
        texts, locale = self.texts({w6.QUIVER: row}, w6.QUIVER, 0)
        self.assertLessEqual(len(self.time_lines(texts, locale)), 1)
        self.assertNotIn(locale.LEFT_TIME + ": " + locale.RTSecondToDHMS(0), texts)


class Motions(unittest.TestCase):
    @classmethod
    def files(cls):
        if not hasattr(cls, "_files"):
            cls._files = old_content.published_files()
        return cls._files

    OLD_FILES = ["wait.msa", "wait_1.msa", "walk.msa", "run.msa", "damage.msa", "damage_1.msa", "damage_2.msa",
                 "damage_3.msa", "attack_special.msa"]

    def test_both_assassins_register_the_quiver_bow(self):
        motions = lf.RaceMotions(self)
        mode = motions.chr.MOTION_MODE_BOW_SPECIAL
        races = sorted(set(race for (race, at, _) in motions.motions if at == mode))
        self.assertEqual(len(races), 2, "the assassin's two sexes")
        for race in races:
            with self.subTest(race=race):
                folder = motions.folders[race]
                registered = [(index, name[len(folder + "bow/"):], weight) for (r, at, index), files in motions.motions.items()
                              if r == race and at == mode for name, weight in files]
                self.assertEqual(sorted(name for _, name, _ in registered), sorted(self.OLD_FILES))
                self.assertTrue(all(name.startswith(folder + "bow/") for (r, at, _), files in motions.motions.items()
                                    if r == race and at == mode for name, _ in files))
                weights = dict(((index, name), weight) for index, name, weight in registered)
                self.assertEqual(weights[(motions.chr.MOTION_WAIT, "wait.msa")], 70)
                self.assertEqual(weights[(motions.chr.MOTION_WAIT, "wait_1.msa")], 30)
                attack = [name for index, name, _ in registered if index == motions.chr.MOTION_COMBO_ATTACK_1]
                self.assertEqual(attack, ["attack_special.msa"], "OLD's attack")
                self.assertIn(old_content.store_name(folder + "bow/attack_special.msa"), self.files())
                bow = [name for name, _ in motions.motions[(race, motions.chr.MOTION_MODE_BOW,
                                                             motions.chr.MOTION_COMBO_ATTACK_1)]]
                self.assertEqual(len(bow), 1)


class ArrowCell(unittest.TestCase):
    def test_the_inventory_shows_a_worn_quiver_in_the_arrow_cell(self):
        world = w6.World()
        cell = w6.EQUIPMENT_START + 9
        world.game.give(cell, w6.QUIVER)
        window = w6.make_inventory(world)
        self.assertEqual(window.wndEquip.slots[cell]["vnum"], w6.QUIVER)


if __name__ == "__main__":
    unittest.main()
