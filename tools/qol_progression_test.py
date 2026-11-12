"""Tests for the wave 10 progression switches (NOVA-199, NOVA-200):
python3 -B -m unittest qol_progression_test (from tools/).

The server (nova-server-src cmd_progression.cpp) keeps the rules: it holds a
checkpoint level-up and sends "ConfirmLevelUp", and it keeps the anti-EXP
switch and sends "AntiExpState <0|1>". Here:
- uiprogression.LevelUpQuestion: one question at a time; yes sends
  /confirm_level_up once, no turns anti-EXP on (/anti_exp 1) once;
- game.GameWindow's two server commands reach uiprogression and the taskbar;
- the taskbar, legacy and NovaUI alike: a press on the EXP gauge sends
  /anti_exp; SetAntiExp shows the frozen state (the legacy gauge tinted, the
  NovaUI orbs' exp_frozen) and the EXP tooltip says how to switch it;
- the new keys in all 17 locales."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import legacy_foundation_test as lf  # noqa: E402
import nui_hud_test as hud  # noqa: E402
import nui_hud_core_test as core  # noqa: E402

KEYS = ("CONFIRM_LEVEL_UP_QUESTION", "ANTI_EXP_FREEZE_HINT", "ANTI_EXP_FROZEN_HINT")


class SizedQuestionDialog(hud.QuestionDialog):
	def SetWidth(self, width):
		self.width = width

	def SetTop(self):
		self.raised = getattr(self, "raised", 0) + 1


def progression_world(level=105):
	world = hud.HudWorld(False)
	game = world.game
	game.modules["uiCommon"].QuestionDialog = SizedQuestionDialog
	hud.QuestionDialog.made = []
	real = support.locale_info("en")
	for key in KEYS:
		setattr(game.modules["localeInfo"], key, getattr(real, key))
	game.status[game.modules["player"].LEVEL] = level
	with world, hud.quiet():
		game.load("uiprogression", "uiprogression.py")
	return world


def sent(world, mark=0):
	return [args for name, args in world.game.log[mark:] if name == "net.SendChatPacket"]


class LevelUpQuestionTest(unittest.TestCase):
	def setUp(self):
		self.world = progression_world()
		self.module = self.world.module("uiprogression")
		self.question = self.module.LevelUpQuestion()

	def open(self):
		with self.world:
			self.question.Open()
		return hud.QuestionDialog.made[-1]

	def test_the_question_names_the_next_level(self):
		dialog = self.open()
		self.assertTrue(dialog.opened)
		self.assertIn("106", dialog.text)

	def test_yes_confirms_once(self):
		dialog = self.open()
		mark = len(self.world.game.log)
		with self.world:
			dialog.accept()
			dialog.accept()
		self.assertFalse(dialog.opened)
		self.assertEqual(sent(self.world, mark), [("/confirm_level_up",)])

	def test_no_turns_anti_exp_on_once(self):
		dialog = self.open()
		mark = len(self.world.game.log)
		with self.world:
			dialog.cancel()
			dialog.cancel()
		self.assertFalse(dialog.opened)
		self.assertEqual(sent(self.world, mark), [("/anti_exp 1",)])

	def test_no_while_anti_exp_is_already_on_sends_nothing(self):
		with self.world:
			self.module.set_anti_exp(1)
		dialog = self.open()
		mark = len(self.world.game.log)
		with self.world:
			dialog.cancel()
		self.assertEqual(sent(self.world, mark), [])

	def test_a_second_question_only_raises_the_first(self):
		self.open()
		with self.world:
			self.question.Open()
		self.assertEqual(len(hud.QuestionDialog.made), 1)
		self.assertEqual(hud.QuestionDialog.made[-1].raised, 1)


class AntiExpStateTest(unittest.TestCase):
	def setUp(self):
		self.world = progression_world()
		self.module = self.world.module("uiprogression")

	def test_the_state_is_kept_and_reaches_the_taskbar(self):
		calls = []

		class Bar(object):
			def SetAntiExp(self, on):
				calls.append(on)

		with self.world:
			self.module.set_anti_exp("1", Bar())
			self.assertTrue(self.module.is_anti_exp_on())
			self.module.set_anti_exp("0", Bar())
			self.module.set_anti_exp(1, None)
		self.assertEqual(calls, [True, False])
		self.assertTrue(self.module.is_anti_exp_on())


# --- game.py ---------------------------------------------------------------------------------------

def game_methods(names):
	source = support.source_of("game.py", names, inside="GameWindow")
	body = "\n".join("\t" + line if line else line for line in source.split("\n"))
	namespace = {}
	exec(compile("class GameWindow(object):\n%s\n" % body, "game.py", "exec"), namespace)
	return namespace


class GameCommandsTest(unittest.TestCase):
	def test_the_two_commands_are_registered(self):
		source = support.source_of("game.py", ("__ServerCommand_Build",), inside="GameWindow")
		self.assertIn('"ConfirmLevelUp"', source)
		self.assertIn('"AntiExpState"', source)

	def test_the_handlers_reach_uiprogression_and_the_taskbar(self):
		import types
		world = progression_world()
		module = world.module("uiprogression")
		namespace = game_methods(["__ConfirmLevelUp", "__AntiExpState"])
		namespace["uiprogression"] = module
		window = namespace["GameWindow"]()
		calls = []

		class Bar(object):
			def SetAntiExp(self, on):
				calls.append(on)

		window.interface = types.SimpleNamespace(wndTaskBar=Bar())
		with world:
			window._GameWindow__AntiExpState("1")
			window._GameWindow__ConfirmLevelUp()
			window._GameWindow__ConfirmLevelUp()
		self.assertEqual(calls, [True])
		self.assertTrue(module.is_anti_exp_on())
		self.assertEqual(len(hud.QuestionDialog.made), 1, "one question, raised again")
		self.assertTrue(hud.QuestionDialog.made[-1].opened)


# --- the taskbar ------------------------------------------------------------------------------------

class TaskbarAntiExpTest(core.TaskbarWorlds):
	def setUp(self):
		self.legacy, self.novaui = self.worlds()
		real = support.locale_info("en")
		for world in (self.legacy, self.novaui):
			for key in KEYS:
				setattr(world.game.modules["localeInfo"], key, getattr(real, key))

	def test_a_press_on_the_exp_gauge_asks_the_server_in_both(self):
		def legacy(world):
			world.bar.expGaugeBoard.OnMouseLeftButtonUp()

		def novaui(world):
			self.nui(world, "exp_press", 0)
			self.nui(world, "exp_press", 1)
		result = self.same(self.legacy, self.novaui, legacy, novaui)
		self.assertIn(("net.SendChatPacket", ("/anti_exp",)), result)

	def test_frozen_shows_on_the_novaui_orbs_and_their_tooltip(self):
		with self.novaui, core.quiet():
			self.novaui.bar.SetAntiExp(True)
		board = self.novaui.bar.board
		self.assertTrue(board.get("exp_frozen"))
		self.assertEqual(board.get("exp_hint"), "@game.ANTI_EXP_FROZEN_HINT")
		with self.novaui, core.quiet():
			self.novaui.bar.SetAntiExp(False)
		self.assertFalse(board.get("exp_frozen"))
		self.assertEqual(board.get("exp_hint"), "@game.ANTI_EXP_FREEZE_HINT")

	def test_frozen_tints_the_legacy_gauge_and_names_it_in_the_tooltip(self):
		with self.legacy, core.quiet():
			self.legacy.bar.SetAntiExp(True)
			self.legacy.bar.SetExperience(50, 100)
		self.assertTrue(self.legacy.bar.antiExpOn)
		tints = [args for name, args in self.legacy.game.log if name == "wndMgr.SetDiffuseColor"]
		self.assertTrue(tints, "the EXP points are tinted")
		line = self.legacy.bar.tooltipEXP.textLine
		text = line.GetText() if hasattr(line, "GetText") else getattr(line, "text", "")
		self.assertIn(support.locale_info("en").ANTI_EXP_FROZEN_HINT, text)


class LocaleKeys(unittest.TestCase):
	def test_every_key_is_in_every_locale(self):
		locales = sorted(name for name in os.listdir(lf.LOCALES) if name != "common")
		self.assertEqual(len(locales), 17)
		for loc in locales:
			path = os.path.join(lf.LOCALES, loc, "locale_game.txt")
			with open(path, encoding="utf-8") as handle:
				keys = set(line.split("\t", 1)[0] for line in handle)
			for key in KEYS:
				self.assertIn(key, keys, "%s %s" % (loc, key))


if __name__ == "__main__":
	unittest.main()
