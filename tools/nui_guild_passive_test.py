"""Tests for the guild passive skills on the guild window's skill page
(NOVA-34): python3 -B -m unittest nui_guild_passive_test (from tools/).

OLD's three passives (Dragon Hunt, Dragon Apex, Dragon Shatter, guild skills
158-160) sit in the passive row (slots 200-202, guild skill indexes 7-9).
Their "+" opens the donation dialog while a next level is left; the server's
progress (GC::GUILD_PASSIVE, game.RecvGuildSkillContribution) reaches the
window and the slot's tooltip. The legacy uiGuild.GuildWindow and the NovaUI
one are driven the same way and must make the same calls."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402
from nui_guild_test import EFFECTS, GuildTest  # noqa: E402

# (skillIndex, currentAmount, requiredAmount, itemVnum, personalContribution)
PROGRESS = [(7, 640, 1500, 34246, 40), (8, 0, 1500, 34244, 0), (9, 0, 0, 0, 0)]


def feed(window):
    for row in PROGRESS:
        window.RefreshSkillContribution(*row)


class PassiveRow(GuildTest):
    def test_the_row_shows_the_three_passives_with_their_levels(self):
        (a_world, a), (b_world, b) = [self.world(nui_on) for nui_on in (False, True)]
        for world, window in ((a_world, a), (b_world, b)):
            self.open(world, window)
            self.tab(world, window, "SKILL")
        model = w4.board(b).model
        passive = a.pageWindow["SKILL"].passiveSlot
        self.assertEqual([cell["kind"] for cell in model["passive_cells"]], ["skill"] * 3 + [""] * 6)
        self.assertTrue(all(cell["icon"].endswith("yongan.sub") for cell in model["passive_cells"][:3]))
        self.assertEqual([cell["count"] for cell in model["passive_cells"][:3]], ["4", "", "12"])
        # The "+" while a level is left: not on the passive at its maximum 12.
        self.assertEqual(model["passive_plus"][:3], [True, True, False])
        self.assertEqual(model["passive_plus"], [s in getattr(passive, "buttons", set()) for s in range(200, 209)])

    def test_each_slot_maps_to_its_guild_skill_index(self):
        world, window = self.world(False)
        self.open(world, window)
        indexes = dict((args[0], args[1]) for name, args in world.game.log if name == "guild.SetSkillIndex")
        self.assertEqual([indexes[s] for s in (200, 201, 202)], [7, 8, 9])
        self.assertEqual([indexes[s] for s in range(210, 216)], [1, 2, 3, 4, 5, 6])


class Donation(GuildTest):
    def test_the_plus_opens_the_donation_and_its_accept_sends_the_amount(self):
        def flow(world, window):
            feed(window)
            if world.nui_on:
                w4.press(window, "passive_plus_press", 0, 0)
            else:
                window.pageWindow["SKILL"].passiveSlot.events["pressed_button"](200)
            dialog = window.contributionInputDialog
            world.dialog_texts = list(dialog.texts) if dialog else None
            dialog.text = "300"
            dialog.accept()
        (legacy, a_world, a), (novaui, b_world, b) = self.run_both(flow, page="SKILL")
        self.assertEqual(novaui, legacy)
        self.assertIn(("net.SendGuildContributePacket", (7, 300)), novaui)
        self.assertNotIn("net.SendChatPacket", [name for name, _ in novaui], "no /gskillup for a passive")
        self.assertEqual(b_world.dialog_texts, a_world.dialog_texts)
        self.assertEqual(len(a_world.dialog_texts), 2, "the level line and the need line")
        self.assertIsNone(b.contributionInputDialog)

    def test_nothing_goes_out_for_a_bad_amount_or_without_progress(self):
        def flow(world, window):
            # No progress yet: the "+" does nothing.
            if world.nui_on:
                w4.press(window, "passive_plus_press", 1, 0)
            else:
                window.pageWindow["SKILL"].passiveSlot.events["pressed_button"](201)
            world.opened_without_progress = window.contributionInputDialog is not None
            feed(window)
            window.OpenContributionDialog(201)
            window.contributionInputDialog.text = "0"
            window.contributionInputDialog.accept()
        results = self.run_both(flow, page="SKILL")
        (legacy, a_world, _), (novaui, b_world, _) = results
        self.assertEqual(novaui, legacy)
        self.assertEqual((a_world.opened_without_progress, b_world.opened_without_progress), (False, False))
        self.assertNotIn("net.SendGuildContributePacket", [name for name, _ in novaui])

    def test_the_tooltip_shows_the_progress(self):
        def flow(world, window):
            feed(window)
            if world.nui_on:
                w4.fire(window, "passive_over", 0)
                w4.fire(window, "passive_out", 0)
            else:
                slots = window.pageWindow["SKILL"].passiveSlot
                slots.fire("over_in", 200)
                slots.fire("over_out")
            world.tips = list(world.tooltip_skill.calls)
        (legacy, a_world, _), (novaui, b_world, _) = self.run_both(flow, page="SKILL")
        self.assertEqual(b_world.tips, a_world.tips)
        self.assertEqual(a_world.tips[0], ("SetSkill", 158, 4))
        lines = [c[1] for c in a_world.tips if c[0] == "AppendTextLine"]
        self.assertTrue(any("640 / 1500" in str(line) for line in lines), lines)
        self.assertTrue(any("40" in str(line) for line in lines[-1:]), lines)


class GameWindow(unittest.TestCase):
    def test_the_progress_reaches_the_guild_window(self):
        """game.py's RecvGuildSkillContribution hands each tuple to the window."""
        calls = []

        class Window(object):
            def RefreshSkillContribution(self, *args):
                calls.append(args)

        source = open(os.path.join(support.ROOT, "game.py"), encoding="utf-8").read()
        start = source.index("	def RecvGuildSkillContribution(self, contributionList):")
        body = source[start:source.index("\n\n", start)]
        namespace = {}
        exec("class G:\n" + body, namespace)
        game = namespace["G"]()
        game.interface = type("I", (), {"wndGuild": Window()})()
        game.RecvGuildSkillContribution(PROGRESS)
        self.assertEqual(calls, PROGRESS)


if __name__ == "__main__":
    unittest.main()
