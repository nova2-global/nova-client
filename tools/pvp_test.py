"""Tests for wave 7's PvP client (NOVA-28 duel rules, NOVA-29 kill ranking and
guild war top killers): python3 -B -m unittest pvp_test (from tools/).

The C++ half (GC::KILL_RANK and GC::GUILD_WAR_TOP, player.GetKillRank and
ClearKillRank, the game window calls RefreshKillRank, SetPersonalKillRank
and BINARY_WarTop) is tested in nova-client-src's userinterface_tests. Here
each window runs as legacy's class and as its NovaUI facade over the same
stand-in world (nui_w4_world's, social), and both must do the same:
- the duel rules (uiduel.py, nui_duel_rules.py): the nine rules in OLD's
  order, the ticked ones sent as "/pvp <vid> <rules>", Cancel sending
  nothing, the rules kept between opens; game.py's reading of the rules'
  whisper "<<~N~>>" (OLD game.py:1435-1446);
- the target board's Deny and Pardon ("/cancel_pvp <vid>") and Fight
  opening the rules (legacy uitarget.py and nui_target.py);
- the kill ranking (uikillrank.py, nui_kill_rank.py): "/kill_rank 0" at the
  open, a tab's "/kill_rank N", the rows from player.GetKillRank, the
  player's own row (a dash without a place), the rows a shorter ranking
  empties, the walk-away rule;
- the top killers (uiguild.py TopWarPlayersDialog, nui_guild_war_top.py):
  the two sides, OLD's order, the MVP, the score, a line of a third guild
  ignored (OLD raised a KeyError), no show outside a war;
- the ranking's entry: the inventory's (legacy's button, as OLD's, and the
  NovaUI rail's), no system menu's;
- every new key in all 17 locales, OLD's text where OLD's locale has it."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import social_test  # noqa: E402
import legacy_foundation_test as lf  # noqa: E402
import extra_inventory_test as xinv  # noqa: E402

FLAGS = "+social,+duel-rules,+kill-rank,+guild-war-top"
MODULES = w4.SOCIAL_MODULES + ("nui_duel_rules", "nui_kill_rank", "nui_guild_war_top")
PEER_VID = 4242

GAME_KEYS = {
	"DUEL_ANTI_MOUNT": "No Mount", "DUEL_ANTI_PET": "No Pet", "DUEL_ANTI_POTION": "No Potions",
	"DUEL_ANTI_CRITICAL": "No Critical", "DUEL_ANTI_PIERCE": "No Pierce", "DUEL_ANTI_POISON": "No Poison",
	"DUEL_ANTI_FIRE": "No Fire", "DUEL_ANTI_CHANGE_EQUIP": "No Equipment Change", "DUEL_ANTI_PARTY": "No Party",
	"DUEL_ANTI_PET_ADVANCED": "No Advanced Pet",
	"TARGET_BUTTON_DENY_FIGHT": "Deny", "TARGET_BUTTON_CANCEL_AVENGE": "Pardon", "BATTLE_RULES": "Battle Rules:",
	"GUILD_WAR_TOP_MVP": "MVP: %s",
}
INTERFACE_KEYS = {
	"DUEL_RULES_TITLE": "Duel Rules", "DUEL_RULES_ACCEPT": "Duel",
	"KILL_COUNT_TITLE0": "Stone Rank", "KILL_COUNT_TITLE1": "Boss Rank", "KILL_COUNT_TITLE2": "Player Rank",
	"KILL_COUNT_TITLE3": "Top Killed Monsters", "KILL_COUNT_TITLE4": "Top Completed Dungeons",
	"KILL_COUNT_TITLE5": "Top Killed Players in PvP Arena", "KILL_COUNT_TITLE6": "Top Items Upgraded",
	"KILL_COUNT_TITLE7": "Most Timeplayed",
	"KILL_RANK_TAB0": "Stones", "KILL_RANK_TAB1": "Bosses", "KILL_RANK_TAB2": "Players", "KILL_RANK_TAB3": "Monsters",
	"KILL_RANK_TAB4": "Dungeons", "KILL_RANK_TAB5": "PvP Arena", "KILL_RANK_TAB6": "Upgrades",
	"KILL_RANK_TAB7": "Time Played",
	"KILL_RANK_COLUMN_RANK": "Rank", "KILL_RANK_COLUMN_NAME": "Name", "KILL_RANK_COLUMN_GUILD": "Guild",
	"KILL_RANK_COLUMN_COUNT": "Count", "KILL_RANK_OWN": "You", "SYSTEM_KILL_RANK": "Ranking",
	"GUILD_WAR_TOP_TITLE": "Top Killers", "GUILD_WAR_TOP_NAME": "Name", "GUILD_WAR_TOP_KILLS": "Kills",
	"GUILD_WAR_TOP_DEATHS": "Deaths", "GUILD_WAR_TOP_DAMAGE": "Damage", "GUILD_WAR_TOP_PING": "Ping",
}


class PvpWorld(object):
	"""nui_w4_world's social world with wave 7's modules, legacy or NovaUI."""

	def __init__(self, nui_on):
		self.ranks = []
		self.position = [1000.0, 2000.0, 0.0]
		self.guild_names = {71: "Lions", 72: "Wolves", 73: "Bears"}

		def setup(game):
			locale = game.modules["localeInfo"]
			for key, text in GAME_KEYS.items():
				setattr(locale, key, text)
			script_locale = game.modules.get("uiScriptLocale")
			if script_locale is not None:
				for key, text in INTERFACE_KEYS.items():
					setattr(script_locale, key, text)
			player = game.modules["player"]
			support.define(player, "GetKillRank", lambda: list(self.ranks))
			support.define(player, "ClearKillRank", lambda: None)
			support.define(player, "GetMainCharacterPosition", lambda: tuple(self.position))
			support.define(game.modules["guild"], "GetGuildName", lambda gid: self.guild_names.get(gid, "Noname"))

		self.w4 = w4.World(nui_on, windows=FLAGS, setup=setup, social=True, modules=())
		game = self.game = self.w4.game
		# ui.CheckBox (the duel rules' boxes), as wave 6's world stands it in.
		import wave6_support
		game.modules["ui"].CheckBox = wave6_support.CheckBox
		with game, w4.quiet():
			for name in ("uiScriptLocale",):
				module = game.modules.get(name) or game.loaded.get(name)
				if module is not None:
					for key, text in INTERFACE_KEYS.items():
						setattr(module, key, text)
			for key, text in GAME_KEYS.items():
				setattr(game.modules["localeInfo"], key, text)
			# The shared NovaUI modules first (uikillrank.py groups digits with
			# nui_numbers), then the legacy modules, then their facades.
			for name in w4.SOCIAL_MODULES:
				game.load(name, name + ".py")
			game.load("uiDuel", "uiduel.py")
			game.load("uiKillRank", "uikillrank.py")
			for name in MODULES[len(w4.SOCIAL_MODULES):]:
				game.load(name, name + ".py")
		self.nui_on = nui_on

	def __enter__(self):
		self.game.__enter__()
		return self

	def __exit__(self, *exc):
		return self.game.__exit__(*exc)

	def mark(self):
		return len(self.game.log)

	def chat_since(self, mark):
		return [args[0] for name, args in self.game.log[mark:] if name == "net.SendChatPacket"]

	def make(self, window_id, legacy_module, legacy_class, novaui):
		return self.w4.make(window_id, legacy_module, legacy_class, novaui)


def model(window):
	board = w4.board(window)
	return dict(board.model) if board is not None and hasattr(board, "model") else dict(window._state)


# --- the duel rules (NOVA-28) ---------------------------------------------------------------

class DuelRules(unittest.TestCase):
	def opened(self, nui_on):
		world = PvpWorld(nui_on)
		window = world.make("duel-rules", "uiDuel", "DuelRulesDialog", "nui_duel_rules.DuelRulesDialog")
		with world, w4.quiet():
			window.Open(PEER_VID)
		self.assertEqual(type(window).__module__ == "nui_duel_rules", nui_on)
		return world, window

	def tick(self, world, window, index):
		if world.nui_on:
			w4.press(window, "rule_press", index, 0)
		else:
			window.checkBoxList[index].OnMouseLeftButtonUp()

	def button(self, world, window, name):
		if world.nui_on:
			w4.press(window, "button_press", name, 0)
		else:
			getattr(window, name + "Button").Click()

	def both(self, flow):
		results = []
		for nui_on in (False, True):
			world, window = self.opened(nui_on)
			mark = world.mark()
			with world, w4.quiet():
				flow(world, window)
			results.append((world.chat_since(mark), bool(window.IsShow()), window.GetFlags()))
		self.assertEqual(results[1], results[0])
		return results[0]

	def test_the_rules_are_olds_ten_in_olds_order(self):
		world = PvpWorld(False)
		module = world.game.loaded["uiDuel"]
		self.assertEqual([bit for bit, _ in module.DUEL_FLAGS], [1 << i for i in range(10)])
		self.assertEqual([key for _, key in module.DUEL_FLAGS][:3], ["DUEL_ANTI_MOUNT", "DUEL_ANTI_PET", "DUEL_ANTI_POTION"])
		# NOVA-71: OLD's tenth (uiTarget.py:46), now the advanced pet is in.
		self.assertEqual(module.DUEL_FLAGS[9], (1 << 9, "DUEL_ANTI_PET_ADVANCED"))

	def test_the_tenth_rule_fits_legacy_s_board_above_the_buttons(self):
		world = PvpWorld(False)
		module = world.game.loaded["uiDuel"]
		last_y = max(module.RULE_POSITION(i)[1] for i in range(len(module.DUEL_FLAGS)))
		self.assertLessEqual(last_y + module.ROW_HEIGHT, 140, "the buttons sit 40 above the 180 board's bottom")

	def test_fight_sends_the_advanced_pet_rule(self):
		def flow(world, window):
			self.tick(world, window, 9)
			self.button(world, window, "accept")
		chat, shown, flags = self.both(flow)
		self.assertEqual(chat, ["/pvp %d 512" % PEER_VID])

	def test_fight_sends_the_ticked_rules(self):
		def flow(world, window):
			self.tick(world, window, 0)
			self.tick(world, window, 2)
			self.tick(world, window, 6)
			self.button(world, window, "accept")
		chat, shown, flags = self.both(flow)
		self.assertEqual(chat, ["/pvp %d 69" % PEER_VID])
		self.assertFalse(shown)

	def test_a_second_tick_takes_a_rule_back_and_cancel_sends_nothing(self):
		def flow(world, window):
			self.tick(world, window, 3)
			self.tick(world, window, 3)
			self.tick(world, window, 8)
			self.button(world, window, "cancel")
		chat, shown, flags = self.both(flow)
		self.assertEqual(chat, [])
		self.assertEqual(flags, 1 << 8, "the board keeps the ticked rules, as OLD's")
		self.assertFalse(shown)

	def test_the_board_shows_each_rule_and_its_state(self):
		world, window = self.opened(True)
		with world, w4.quiet():
			self.tick(world, window, 1)
		rules = model(window)["rules"]
		self.assertEqual([r["label"] for r in rules][:2], ["No Mount", "No Pet"])
		self.assertEqual([r["checked"] for r in rules], [i == 1 for i in range(10)])
		self.assertEqual(rules[9]["label"], "No Advanced Pet")
		self.assertIsNone(type(window).OnUpdate)

	def test_every_fixture_has_every_model_key(self):
		world, window = self.opened(True)
		keys = set(window.nui_model())
		for variant in ("", "none"):
			self.assertEqual(set(w4.fixture_model("duel-rules", variant)), keys)


class RulesWhisper(unittest.TestCase):
	def window(self):
		log = []
		chat = support.Recording("chat", log, WHISPER_TYPE_SYSTEM=255)
		interface = support.Recording("interface", log)
		locale = support.locale_info("en")
		for key, text in GAME_KEYS.items():
			setattr(locale, key, text)
		world = PvpWorld(False)
		cls = social_test.compiled("game.py", "GameWindow", ("OnRecvWhisperSystemMessage",),
		                           {"chat": chat, "uiDuel": world.game.loaded["uiDuel"]})
		window = cls()
		window.interface = interface
		world.game.loaded["uiDuel"].localeInfo = locale
		return window, log

	def test_the_rules_line_becomes_olds_title_and_one_line_per_rule(self):
		window, log = self.window()
		window.OnRecvWhisperSystemMessage(0, "Rival", "<<~68~>>")
		self.assertEqual(log, [("chat.AppendWhisper", (255, "Rival", "Battle Rules:")),
		                       ("chat.AppendWhisper", (255, "Rival", "|E~/xmark.tga|e No Potions")),
		                       ("chat.AppendWhisper", (255, "Rival", "|E~/xmark.tga|e No Fire")),
		                       ("interface.RecvWhisper", ("Rival",))])

	def test_the_challenged_side_reads_the_advanced_pet_rule(self):
		window, log = self.window()
		window.OnRecvWhisperSystemMessage(0, "Rival", "<<~514~>>")
		self.assertEqual(log, [("chat.AppendWhisper", (255, "Rival", "Battle Rules:")),
		                       ("chat.AppendWhisper", (255, "Rival", "|E~/xmark.tga|e No Pet")),
		                       ("chat.AppendWhisper", (255, "Rival", "|E~/xmark.tga|e No Advanced Pet")),
		                       ("interface.RecvWhisper", ("Rival",))])

	def test_another_system_line_is_said_as_it_is(self):
		window, log = self.window()
		window.OnRecvWhisperSystemMessage(0, "Rival", "Rival wants to fight you.")
		self.assertEqual(log[0], ("chat.AppendWhisper", (255, "Rival", "Rival wants to fight you.")))


# --- the target board's buttons -----------------------------------------------------------------

class TargetDuelButtons(unittest.TestCase):
	def board(self, setup_extra=None, nui=False):
		import nui_hud_test as hud

		def setup(game):
			hud.target_setup(game)
			if setup_extra:
				setup_extra(game)
		legacy, novaui = hud.pair(setup)
		world = novaui if nui else legacy
		with world:
			world.board = world.make("target", world.module("uiTarget").TargetBoard, "nui_target.TargetBoard")
			world.board.Hide()
			world.board.Open(hud.PEER_VID, "Rival")
		return world, hud

	def test_a_challenge_shows_accept_and_deny_and_a_revenge_avenge_and_pardon(self):
		for nui in (False, True):
			world, hud = self.board(lambda game: game.answer("player", "IsChallengeInstance", lambda vid: True), nui=nui)
			T = world.module("uiTarget").TargetBoard
			shown = hud.TargetWorlds.legacy_view(world)["buttons"] if not nui else sorted(world.board.shownButtons)
			self.assertIn(T.BTN_ACCEPT_FIGHT, shown)
			self.assertIn(T.BTN_DENY_FIGHT, shown)
			self.assertNotIn(T.BTN_FIGHT, shown)
			world, hud = self.board(lambda game: game.answer("player", "IsRevengeInstance", lambda vid: True), nui=nui)
			shown = hud.TargetWorlds.legacy_view(world)["buttons"] if not nui else sorted(world.board.shownButtons)
			self.assertIn(T.BTN_AVENGE, shown)
			self.assertIn(T.BTN_CANCEL_AVENGE, shown)

	def test_deny_sends_cancel_pvp_in_both(self):
		for nui in (False, True):
			world, hud = self.board(lambda game: game.answer("player", "IsChallengeInstance", lambda vid: True), nui=nui)
			T = world.module("uiTarget").TargetBoard
			mark = len(world.game.log)
			with world, hud.quiet():
				if nui:
					world.board.nui_press(T.BTN_DENY_FIGHT)
				else:
					world.board.buttonDict[T.BTN_DENY_FIGHT].Click()
			self.assertEqual(world.effects(mark), [("net.SendChatPacket", ("/cancel_pvp %d" % hud.PEER_VID,))])

	def test_the_button_ids_and_texts_are_olds_keys(self):
		world, hud = self.board()
		T = world.module("uiTarget").TargetBoard
		config = dict(T.BUTTON_CONFIG)
		self.assertEqual((T.BTN_DENY_FIGHT, T.BTN_CANCEL_AVENGE), (20, 21))
		self.assertEqual((config[T.BTN_DENY_FIGHT], config[T.BTN_CANCEL_AVENGE]),
		                 ("TARGET_BUTTON_DENY_FIGHT", "TARGET_BUTTON_CANCEL_AVENGE"))


# --- the kill ranking (NOVA-29) -----------------------------------------------------------------

class KillRank(unittest.TestCase):
	ROWS = [(1, "Alex", "Nova", 27007), (2, "Sara", "-", 9), (3, "Kai", "Nova", 3)]

	def opened(self, nui_on):
		world = PvpWorld(nui_on)
		window = world.make("kill-rank", "uiKillRank", "KillRankWindow", "nui_kill_rank.KillRankWindow")
		mark = world.mark()
		with world, w4.quiet():
			window.LoadWindow()
			window.Open(-1)
		self.assertEqual(world.chat_since(mark), ["/kill_rank 0"])
		return world, window

	def answer(self, world, window, type, rows, own=("7", "Lucas", "-", "112")):
		world.ranks = list(rows)
		with world, w4.quiet():
			window.SetPersonalKillRank(*own)
			window.RefreshKillRank(type)

	def texts(self, window):
		return [row.GetTexts() for row in window.rankRows]

	def test_the_answer_fills_the_rows_and_the_players_own_row_in_both(self):
		results = []
		for nui_on in (False, True):
			world, window = self.opened(nui_on)
			self.answer(world, window, 3, self.ROWS)
			results.append(self.texts(window))
		self.assertEqual(results[1], results[0])
		self.assertEqual(results[0][0], ["1", "Alex", "Nova", "27,007"])
		self.assertEqual(results[0][3], ["", "", "", ""])
		self.assertEqual(results[0][10], ["7", "Lucas", "-", "112"])

	def test_a_shorter_ranking_empties_the_rows_after_its_last(self):
		for nui_on in (False, True):
			world, window = self.opened(nui_on)
			self.answer(world, window, 3, self.ROWS)
			self.answer(world, window, 1, self.ROWS[:1])
			self.assertEqual(self.texts(window)[1], ["", "", "", ""], "OLD kept the last ranking's text")

	def test_a_player_without_a_place_shows_a_dash(self):
		for nui_on in (False, True):
			world, window = self.opened(nui_on)
			self.answer(world, window, 4, [], own=("0", "Lucas", "-", "0"))
			self.assertEqual(self.texts(window)[10], ["-", "Lucas", "-", "0"])

	def test_a_tab_asks_for_its_ranking(self):
		for nui_on in (False, True):
			world, window = self.opened(nui_on)
			mark = world.mark()
			with world, w4.quiet():
				if nui_on:
					w4.press(window, "tab_press", 5, 0)
				else:
					window.rankingTab[5].Click()
			self.assertEqual(world.chat_since(mark), ["/kill_rank 5"])

	def test_the_board_shows_the_title_the_tab_and_the_rows(self):
		world, window = self.opened(True)
		self.answer(world, window, 3, self.ROWS)
		state = model(window)
		self.assertEqual(state["title"], "Top Killed Monsters")
		self.assertEqual(state["tab"], 3)
		self.assertEqual([r["name"] for r in state["rows"]], ["Alex", "Sara", "Kai"])
		self.assertEqual(state["own"]["rank"], "7")

	def test_no_python_per_frame_and_the_walk_away_watch(self):
		world, window = self.opened(True)
		self.assertIsNone(type(window).OnUpdate)
		watch = world.game.modules["nuigame"].LeaveRangeState("kill-rank")
		self.assertIsNotNone(watch)
		self.assertEqual(watch.get("range"), 1500)
		with world, w4.quiet():
			window.Close()
		self.assertIsNone(world.game.modules["nuigame"].LeaveRangeState("kill-rank"))

	def test_legacy_closes_past_1500_away(self):
		world, window = self.opened(False)
		world.position[0] += 1501
		with world, w4.quiet():
			window.OnUpdate()
		self.assertFalse(window.IsShow())

	def test_every_fixture_has_every_model_key(self):
		world, window = self.opened(True)
		keys = set(window.nui_model())
		for variant in ("", "empty"):
			self.assertEqual(set(w4.fixture_model("kill-rank", variant)), keys)


# --- the guild war top killers (NOVA-29) ------------------------------------------------------

class TopKillers(unittest.TestCase):
	def made(self, nui_on):
		world = PvpWorld(nui_on)
		window = world.make("guild-war-top", "uiGuild", "TopWarPlayersDialog", "nui_guild_war_top.TopWarPlayersDialog")
		with world, w4.quiet():
			window.BeginWar(71, 72)
		return world, window

	def texts(self, window, side):
		return [[text.GetText() for text in row] for row in window.rows[side]]

	def feed(self, world, window):
		with world, w4.quiet():
			window.Update(71, "Alex", 0, 1234567, 3, 1, 40)
			window.Update(71, "Sara", 1, 900, 5, 0, 55)
			window.Update(72, "Kai", 3, 12, 0, 2, 70)
			window.Update(73, "Bear", 2, 5, 9, 0, 10)
			window.SetScore(71, 12)

	def test_both_sides_in_olds_order_and_a_third_guild_ignored(self):
		results = []
		for nui_on in (False, True):
			world, window = self.made(nui_on)
			self.feed(world, window)
			results.append((self.texts(window, 1), self.texts(window, 2), window.GetChild("guild1_name").GetText(),
			                window.GetChild("guild1_mvp").GetText()))
		self.assertEqual(results[1], results[0])
		left, right, name, mvp = results[0]
		self.assertEqual(left[0], ["Sara", "5", "0", "900", "55"])
		self.assertEqual(left[1], ["Alex", "3", "1", "1.23M", "40"])
		self.assertEqual(right[0], ["Kai", "0", "2", "12", "70"])
		self.assertEqual(name, "Lions (12)")
		self.assertEqual(mvp, "MVP: Sara")

	def test_it_shows_only_during_a_war(self):
		for nui_on in (False, True):
			world, window = self.made(nui_on)
			with world, w4.quiet():
				window.EndWar()
				window.Open()
			self.assertFalse(window.IsShow())
			with world, w4.quiet():
				window.BeginWar(71, 72)
				window.Open()
			self.assertTrue(window.IsShow())

	def test_the_board_shows_both_sides_with_portraits(self):
		world, window = self.made(True)
		self.feed(world, window)
		with world, w4.quiet():
			window.Open()
		state = model(window)
		self.assertEqual(state["left"]["name"], "Lions (12)")
		self.assertEqual([r["name"] for r in state["left"]["rows"]], ["Sara", "Alex"])
		self.assertEqual(state["left"]["rows"][1]["portrait"], "/icon/face/warrior_m.tga")
		self.assertEqual(state["right"]["rows"][0]["portrait"], "/icon/face/shaman_w.tga")

	def test_every_fixture_has_every_model_key(self):
		world, window = self.made(True)
		keys = set(window.nui_model())
		for variant in ("", "start"):
			self.assertEqual(set(w4.fixture_model("guild-war-top", variant)), keys)


# --- the wiring ---------------------------------------------------------------------------------

class Wiring(unittest.TestCase):
	def read(self, name):
		with open(os.path.join(support.ROOT, name), encoding="utf-8") as handle:
			return handle.read()

	def test_game_py_routes_the_frames_and_holds_tab_for_the_board(self):
		source = self.read("game.py")
		for line in ("self.interface.RefreshKillRank(int(type))",
		             "self.interface.SetPersonalKillRank(rank, name, guildName, count)",
		             "self.interface.UpdateTopKillers(guildId, pName, pRace, totalDamage, kills, deads, ping)",
		             "onPressKeyDict[app.DIK_TAB]\t\t\t= lambda: self.interface.OpenTopKillers()",
		             "onClickKeyDict[app.DIK_TAB] = lambda : self.interface.CloseTopKillers()"):
			self.assertIn(line, source)

	def read_nui(self, *parts):
		with open(os.path.join(support.ROOT, "..", "nui", "nui", *parts), encoding="utf-8") as handle:
			return handle.read()

	def test_no_system_menu_has_a_ranking_button(self):
		"""OLD's system dialog has no Ranking: the menus are back to their
		layout before wave 7 (318 high, the change channel at 147)."""
		window = social_test.uiscript("systemdialog.py")
		buttons = social_test.children(window, "board")
		self.assertNotIn("killrank_button", buttons)
		self.assertEqual(buttons["movechannel_button"]["y"], 147)
		self.assertEqual(buttons["cancel_button"]["y"], 277)
		self.assertEqual(window["height"], 318)
		for name in ("uisystem.py", "nui_system_menu.py"):
			source = self.read(name)
			self.assertNotIn("KillRank", source, name)
			self.assertNotIn("kill_rank", source, name)
		self.assertNotIn("SetOpenKillRankEvent", self.read("interfacemodule.py"))
		self.assertNotIn("kill-rank", self.read_nui("windows", "system-menu", "system-menu.rml"))
		self.assertNotIn("kill_rank", self.read_nui("windows", "system-menu", "system-menu.rml"))
		classic = self.read_nui("skins", "classic", "windows", "system-menu.rcss")
		self.assertNotIn("kill-rank", classic)
		self.assertIn("height: 318dp;", classic)

	def test_both_inventory_uiscripts_have_olds_ranking_button(self):
		"""OLD's extra inventory strip had the Ranking (uiscript
		extrainventorywindow.py:93-104, art NEW's packs lack): a stock text
		button beside the special inventory's, inside the board."""
		for path in (os.path.join(lf.UISCRIPT, "inventorywindow.py"),
		             os.path.join(lf.LOCALES, "ae", "ui", "inventorywindow.py")):
			with self.subTest(path=path):
				world = xinv.World()
				with world:
					window = lf.read_uiscript(path)["window"]
				board = lf.child(window, "board")
				extra = lf.child(window, "ExtraInventoryButton")
				ranking = lf.child(window, "RankingButton")
				self.assertEqual(ranking["text"], "SYSTEM_KILL_RANK")
				self.assertEqual(ranking["default_image"], "d:/ymir work/ui/public/middle_button_01.sub")
				self.assertEqual(ranking["y"], extra["y"], "one row with the special inventory's button")
				self.assertNotIn("horizontal_align", extra)
				left, right = sorted((extra, ranking), key=lambda b: b["x"])
				width = lambda b: 88 if b is extra else 61
				self.assertGreaterEqual(right["x"], left["x"] + width(left), "side by side")
				self.assertGreaterEqual(left["x"], 8)
				self.assertLessEqual(right["x"] + width(right), board["width"] - 8)

	def test_the_legacy_inventory_s_button_opens_the_ranking(self):
		world = xinv.World()
		world.game.interface.OpenKillRank = lambda: world.game.log.append(("interface.OpenKillRank", ()))
		window = lf.make_inventory(world)
		with world, lf.quiet():
			window.rankingButton.Click()
		self.assertEqual(world.game.calls("interface.OpenKillRank"), [("interface.OpenKillRank", ())])
		self.assertIn("self.interface.OpenKillRank()", self.read("uiinventory.py"))

	def test_the_novaui_rail_s_ranking_is_live(self):
		source = self.read("nui_inventory.py")
		self.assertIn('("ranking", "ranking", "@ui.NUI_RAIL_RANKING", _open_kill_rank, False),', source)
		self.assertIn("interface.OpenKillRank()", source)


class Locales(unittest.TestCase):
	def test_every_locale_has_every_new_key_olds_text_or_english(self):
		locales = [name for name in sorted(os.listdir(social_test.LOCALES))
		           if os.path.isfile(os.path.join(social_test.LOCALES, name, "locale_game.txt"))]
		self.assertEqual(len(locales), 17)
		for locale in locales:
			for kind, keys in (("game", GAME_KEYS), ("interface", INTERFACE_KEYS)):
				path = os.path.join(social_test.LOCALES, locale, "locale_%s.txt" % kind)
				entries = social_test.locale_entries(path)
				old_path = os.path.join(social_test.OLD_LOCALES, locale, "locale_%s.txt" % kind)
				old = social_test.locale_entries(old_path) if os.path.isfile(old_path) else {}
				for key, english in keys.items():
					with self.subTest(locale=locale, key=key):
						self.assertTrue(entries.get(key, "").strip())
						if os.path.isdir(social_test.OLD_LOCALES):
							self.assertEqual(entries[key], old.get(key) or english)
						if key == "GUILD_WAR_TOP_MVP":
							self.assertEqual(entries[key].count("%s"), 1)


if __name__ == "__main__":
	unittest.main()
