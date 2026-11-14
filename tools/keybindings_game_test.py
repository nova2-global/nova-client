"""game.py's keys through the key bindings' table (NOVA-121):
python3 -B -m unittest keybindings_game_test (from tools/).

game.GameWindow's key code is compiled from its own source over recording
stand-ins (the legacy code, unchanged), with the real keybindings module, and
pressed through OnKeyDown/OnKeyUp as the client presses it:
- each default key reaches the call it made before the table (key for key);
- a rebound key reaches its new action and not its old one;
- while the page captures a key, the key fires nothing;
- Tab targets the next monster (C++ no longer does), previews a hovered pet
  seal and shows the war's kills while held;
- a legacy text field passes the game only its seven keys, whatever the
  table says (ui.py EditLine.OnKeyDown); a NovaUI field passes none
  (nova-client-src nui_host_test.cpp, WhileNovaUiHasTextFocus...)."""
import io
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_test_support  # noqa: E402

ROOT = support.ROOT
GAME_METHODS = (
	"__BuildKeyActions", "OnKeyDown", "OnKeyUp", "__KeyDown", "__KeyUp",
	"MoveUp", "MoveDown", "MoveLeft", "MoveRight", "StopUp", "StopDown", "StopLeft", "StopRight",
	"StartAttack", "EndAttack", "PickUpItem", "ShowName", "HideName", "ShowMouseImage", "HideMouseImage",
	"__PressQuickSlotKey", "__PressQuickSlot", "__SelectQuickPage", "__SetQuickSlotMode", "__SetQuickPageMode",
	"__PressLeftShiftKey", "__SetChannelSwitchMode", "__PressEmotion", "__ToggleQuestButtons", "__PressMountKey",
	"__ActivateDeck", "__PressTabKey", "__ReleaseTabKey",
)


def load_keybindings():
	return nui_test_support.load_module("keybindings", os.path.join(ROOT, "keybindings.py"))


class Files(object):
	def __init__(self):
		self.files = {}

	def __call__(self, path, mode="r"):
		files = self.files
		if "w" in mode:
			class Writer(io.StringIO):
				def close(self_inner):
					files[path] = self_inner.getvalue()
					io.StringIO.close(self_inner)
			return Writer()
		if path not in files:
			raise IOError(path)
		return io.StringIO(files[path])


class App(types.ModuleType):
	"""app: the real DirectInput codes (keybindings.KEYS), the held keys, and
	the camera calls recorded."""

	CAMERA_TO_POSITIVE = 1
	CAMERA_TO_NEGATIVE = -1
	CAMERA_STOP = 0

	def __init__(self, kb, log):
		types.ModuleType.__init__(self, "app")
		self.log = log
		self.held = set()
		for (code, token, name) in kb.KEYS:
			setattr(self, "DIK_" + token, code)
		self.DIK_ESC = kb.DIK["ESCAPE"]
		self.DIK_LMENU = kb.DIK["LALT"]
		self.DIK_RMENU = kb.DIK["RALT"]
		for fn in ("RotateCamera", "ZoomCamera", "PitchCamera", "MovieRotateCamera", "MovieZoomCamera",
		           "MoviePitchCamera", "MovieResetCamera"):
			setattr(self, fn, support.recorded(log, "app." + fn, lambda *args: None))

	def IsPressed(self, key):
		return key in self.held

	def IsRTL(self):
		return False


def compiled(namespace):
	source = support.source_of("game.py", GAME_METHODS, inside="GameWindow")
	body = "\n".join("\t" + line if line else line for line in source.split("\n"))
	exec(compile("class GameWindow(object):\n%s\n" % body, "game.py", "exec"), namespace)
	return namespace["GameWindow"]


class Game(unittest.TestCase):
	def setUp(self):
		self.kb = load_keybindings()
		self.files = Files()
		self.bindings = self.kb.Bindings(opener=self.files)
		self.kb.set_current(self.bindings)
		self.log = []
		log = self.log
		self.app = App(self.kb, log)
		self.player = support.Recording("player", log, INVENTORY_PAGE_SIZE=3)
		self.net = support.Recording("net", log)
		self.chrmgr = support.Recording("chrmgr", log)
		self.chrmgr.__dict__["_answers"]["IsPossibleEmoticon"] = 1
		self.interfaceModule = types.SimpleNamespace(IsQBHide=0)
		modules = nui_test_support.Modules(keybindings=self.kb, app=self.app)
		self.addCleanup(modules.restore)
		namespace = {"app": self.app, "player": self.player, "net": self.net, "chrmgr": self.chrmgr,
		             "keybindings": self.kb, "interfaceModule": self.interfaceModule,
		             "constInfo": types.SimpleNamespace(SET_ITEM_QUESTION_DIALOG_STATUS=lambda value: None),
		             "uiPrivateShopBuilder": types.SimpleNamespace(IsBuildingPrivateShop=lambda: False),
		             "ui": types.SimpleNamespace(__mem_func__=lambda f: f),
		             # NOVA-202: the show names key also holds the costume preview.
		             "costume_preview": types.SimpleNamespace(key=lambda held: None)}
		window = compiled(namespace)()
		window.interface = support.Recording("interface", log, wndWeb=None)
		window.interface.wndDragonSoul = support.Recording("wndDragonSoul", log)
		window.playerGauge = support.Recording("playerGauge", log)
		for name in ("ShowSwitchbot", "OpenTimerWindow", "ToggleFastEquip", "SaveScreen", "ShowConsole",
		             "RequestDropItem"):
			setattr(window, name, support.recorded(log, "game." + name, lambda *args: None))
		window.channelSwitchMode = False
		window.quickSlotPageIndex = 0
		window.ShowNameFlag = False
		window._GameWindow__BuildKeyActions()
		window._GameWindow__SetQuickSlotMode()
		self.window = window

	def tearDown(self):
		self.kb.set_current(None)

	def dik(self, token):
		return self.kb.DIK[token]

	def press(self, token, *mods):
		"""A press and release of `token` with the modifiers held; the log of
		just that press and release."""
		self.app.held = set(self.dik(m) for m in mods)
		start = len(self.log)
		self.window.OnKeyDown(self.dik(token))
		self.window.OnKeyUp(self.dik(token))
		self.app.held = set()
		return self.log[start:]


class EveryActionHasAHandler(Game):
	def test_press_and_release_maps_cover_the_table(self):
		dispatcher = self.window.keyDispatcher
		self.assertEqual(sorted(dispatcher.press), sorted(a.id for a in self.kb.ACTIONS))
		self.assertEqual(sorted(dispatcher.release), sorted(a.id for a in self.kb.ACTIONS if a.hold))


class DefaultKeysReachTodaysCalls(Game):
	"""The calls game.py's __BuildKeyDict made for each key before NOVA-121."""

	def check(self, token, mods, expected):
		got = [entry for entry in self.press(token, *mods)]
		self.assertEqual(got, expected, (mods, token))

	def test_movement(self):
		up, down, left, right = (self.dik(t) for t in ("UP", "DOWN", "LEFT", "RIGHT"))
		for token, dik in (("W", up), ("UP", up), ("S", down), ("DOWN", down), ("A", left), ("LEFT", left),
		                   ("D", right), ("RIGHT", right)):
			self.check(token, (), [("player.SetSingleDIKKeyState", (dik, True)),
			                       ("player.SetSingleDIKKeyState", (dik, False))])

	def test_camera(self):
		P, N, S = 1, -1, 0
		for token, fn, direction in (("E", "Rotate", P), ("NUMPAD6", "Rotate", P), ("Q", "Rotate", N),
		                             ("NUMPAD4", "Rotate", N), ("R", "Zoom", N), ("PGUP", "Zoom", N),
		                             ("F", "Zoom", P), ("PGDN", "Zoom", P), ("T", "Pitch", N),
		                             ("NUMPAD8", "Pitch", N), ("G", "Pitch", P), ("NUMPAD2", "Pitch", P)):
			name = "app.Movie%sCamera" % fn
			self.check(token, (), [(name, (direction,)), (name, (S,))])
		self.check("NUMPAD9", (), [("app.MovieResetCamera", ())])

	def test_actions(self):
		self.check("SPACE", (), [("player.SetAttackKeyState", (True,)), ("player.SetAttackKeyState", (False,))])
		self.check("GRAVE", (), [("player.PickAroundItems", ())])
		self.check("Z", (), [("player.PickAroundItems", ())])
		self.check("LALT", (), [("playerGauge.EnableShowAlways", ()), ("player.SetQuickPage", (1,)),
		                        ("playerGauge.DisableShowAlways", ()), ("player.SetQuickPage", (0,))])
		self.check("LCONTROL", (), [("interface.ShowMouseImage", ()), ("interface.HideMouseImage", ())])
		self.check("SYSRQ", (), [("game.SaveScreen", ())])
		self.check("COMMA", (), [("game.ShowConsole", ())])
		self.check("LSHIFT", (), [("interface.OpenHoveredChestDrop", ())])

	def test_quickslots(self):
		for n in range(1, 5):
			self.check(str(n), (), [("player.RequestUseLocalQuickSlot", (n - 1,))])
		# F1 opens Help since NOVA-217: quickslot 5 has no default key.
		for n in range(2, 5):
			self.check("F%d" % n, (), [("player.RequestUseLocalQuickSlot", (n + 3,))])
		self.check("5", (), [])

	def test_windows(self):
		for token, call in (("C", ("interface.ToggleCharacterWindow", ("STATUS",))),
		                    ("V", ("interface.ToggleCharacterWindow", ("SKILL",))),
		                    ("B", ("interface.ToggleCharacterWindow", ("EMOTICON",))),
		                    ("N", ("interface.ToggleCharacterWindow", ("QUEST",))),
		                    ("I", ("interface.ToggleInventoryWindow", ())),
		                    ("U", ("interface.ToggleExtraInventoryWindow", ())),
		                    ("O", ("interface.ToggleDragonSoulWindowWithNoInfo", ())),
		                    ("M", ("interface.ToggleMiniMap", ())),
		                    ("L", ("interface.ToggleChatLogWindow", ())),
		                    # NOVA-217: the wiki on H, Help on F1.
		                    ("H", ("interface.ToggleWiki", ())),
		                    ("F1", ("interface.OpenHelpWindow", ())),
		                    ("P", ("interface.TogglePetWindow", ())),
		                    ("F5", ("game.ShowSwitchbot", ())),
		                    ("F6", ("game.OpenTimerWindow", ())),
		                    ("F10", ("game.ToggleFastEquip", ())),
		                    ("ADD", ("interface.MiniMapScaleUp", ())),
		                    ("SUBTRACT", ("interface.MiniMapScaleDown", ()))):
			self.check(token, (), [call])

	def test_combinations(self):
		self.check("M", ("LALT",), [("interface.ToggleMessenger", ())])
		self.check("G", ("LALT",), [("interface.ToggleGuildWindow", ())])
		self.check("C", ("LCONTROL",), [("wndDragonSoul.ActivateButtonClick", (0,))])
		self.check("D", ("LCONTROL",), [("wndDragonSoul.ActivateButtonClick", (1,))])
		self.check("Q", ("LCONTROL",), [("interface.HideAllQuestButton", ())])
		self.assertEqual(self.interfaceModule.IsQBHide, 1)
		self.check("Q", ("RCONTROL",), [("interface.ShowAllQuestButton", ())])
		self.check("H", ("LCONTROL",), [("net.SendChatPacket", ("/user_horse_ride",))])
		self.check("F", ("LCONTROL",), [("net.SendChatPacket", ("/user_horse_feed",))])
		self.check("B", ("LCONTROL",), [("net.SendChatPacket", ("/user_horse_back",))])
		self.check("G", ("LCONTROL",), [("net.SendChatPacket", ("/ride",))])
		self.check("J", ("LCONTROL",), [("player.IsMountingHorse", ()), ("player.GetItemIndex", (0,)),
		                                ("player.GetItemIndex", (1,)), ("player.GetItemIndex", (2,))])
		self.player.__dict__["_answers"]["IsMountingHorse"] = 1
		self.check("J", ("LCONTROL",), [("player.IsMountingHorse", ()), ("net.SendChatPacket", ("/unmount",))])
		for n in range(1, 10):
			self.check(str(n), ("LCONTROL",), [("chrmgr.IsPossibleEmoticon", (-1,)), ("chrmgr.SetEmoticon", (-1, n - 1)),
			                                   ("net.SendEmoticon", (n - 1,))])

	def test_alt_with_a_quickslot_key_uses_the_slot_alt_shows(self):
		self.window.OnKeyDown(self.dik("LALT"))
		self.app.held = set([self.dik("LALT")])
		start = len(self.log)
		self.window.OnKeyDown(self.dik("F2"))
		self.assertEqual(self.log[start:], [("player.RequestUseLocalQuickSlot", (5,))])

	def test_tab_targets_previews_and_shows_the_war_kills_while_held(self):
		self.check("TAB", (), [("player.SelectTabNextTarget", ()), ("interface.PressTabKey", ()),
		                       ("interface.OpenTopKillers", ()), ("interface.CloseTopKillers", ())])

	def test_an_older_exe_without_the_tab_binding_still_shows_the_kills(self):
		self.player.lack("SelectTabNextTarget")
		self.check("TAB", (), [("interface.PressTabKey", ()), ("interface.OpenTopKillers", ()),
		                       ("interface.CloseTopKillers", ())])


class Modes(Game):
	"""Hold X (the channel switch, NOVA-49) or left Shift (the quick page)
	and the quickslot 1-4 keys pick a channel or a page."""

	def sent(self):
		return [args[0] for (name, args) in self.log if name == "net.SendChatPacket"]

	def test_x_held_turns_1_to_4_into_channel_moves(self):
		self.window.OnKeyDown(self.dik("X"))
		for token in ("1", "4", "5"):
			self.window.OnKeyDown(self.dik(token))
		self.assertEqual(self.sent(), ["/ch 1", "/ch 4"])
		self.assertNotIn("player.RequestUseLocalQuickSlot", [name for (name, args) in self.log])
		self.window.OnKeyUp(self.dik("X"))
		self.window.OnKeyDown(self.dik("2"))
		self.assertEqual(self.log[-1], ("player.RequestUseLocalQuickSlot", (1,)))

	def test_ctrl_keeps_the_emotions_while_x_is_held(self):
		self.window.OnKeyDown(self.dik("X"))
		self.app.held = set([self.dik("LCONTROL")])
		self.window.OnKeyDown(self.dik("3"))
		self.assertEqual(self.sent(), [])
		self.assertEqual(self.log[-1], ("net.SendEmoticon", (2,)))

	def test_shift_does_not_end_the_channel_mode(self):
		self.window.OnKeyDown(self.dik("X"))
		self.window.OnKeyDown(self.dik("LSHIFT"))
		self.window.OnKeyUp(self.dik("LSHIFT"))
		self.window.OnKeyDown(self.dik("2"))
		self.assertEqual(self.sent(), ["/ch 2"])

	def test_shift_held_turns_1_to_4_into_pages(self):
		self.window.OnKeyDown(self.dik("LSHIFT"))
		self.app.held = set([self.dik("LSHIFT")])
		self.window.OnKeyDown(self.dik("3"))
		self.assertEqual(self.log[-1], ("player.SetQuickPage", (2,)))
		self.window.OnKeyUp(self.dik("LSHIFT"))
		self.app.held = set()
		self.window.OnKeyDown(self.dik("3"))
		self.assertEqual(self.log[-1], ("player.RequestUseLocalQuickSlot", (2,)))

	def test_rebound_mode_keys_and_slot_keys(self):
		self.bindings.assign("channel_switch", 0, self.kb.key("Y"))
		self.bindings.assign("quickslot_2", 0, self.kb.key("K"))
		self.window.OnKeyDown(self.dik("Y"))
		self.window.OnKeyDown(self.dik("K"))
		self.window.OnKeyDown(self.dik("2"))
		self.window.OnKeyUp(self.dik("Y"))
		self.assertEqual(self.sent(), ["/ch 2"])
		self.window.OnKeyDown(self.dik("X"))
		self.window.OnKeyDown(self.dik("K"))
		self.assertEqual(self.sent(), ["/ch 2"])
		self.assertEqual(self.log[-1], ("player.RequestUseLocalQuickSlot", (1,)))


class Rebinding(Game):
	def test_a_rebound_key_reaches_its_new_action_and_not_its_old_one(self):
		self.bindings.assign("inventory", 0, self.kb.key("K"))
		self.assertEqual(self.press("K"), [("interface.ToggleInventoryWindow", ())])
		self.assertEqual(self.press("I"), [])

	def test_a_swapped_key_reaches_the_other_action(self):
		self.bindings.assign("inventory", 0, self.kb.key("M"))
		self.assertEqual(self.press("M"), [("interface.ToggleInventoryWindow", ())])
		self.assertEqual(self.press("I"), [("interface.ToggleMiniMap", ())])

	def test_a_rebound_hold_action_releases_on_its_new_key(self):
		self.bindings.assign("move_up", 0, self.kb.key("K"))
		up = self.dik("UP")
		self.assertEqual(self.press("K"), [("player.SetSingleDIKKeyState", (up, True)),
		                                   ("player.SetSingleDIKKeyState", (up, False))])
		self.assertEqual(self.press("W"), [])

	def test_a_combination_moved_to_a_plain_key(self):
		self.bindings.assign("horse_summon", 0, self.kb.key("K"))
		self.assertEqual(self.press("K"), [("net.SendChatPacket", ("/user_horse_ride",))])
		self.assertEqual(self.press("H", "LCONTROL"), [("interface.ToggleWiki", ())],
		                 "Ctrl+H has no binding now: the plain H's (the wiki, NOVA-217)")


class Capturing(Game):
	def test_a_key_the_page_captures_fires_nothing(self):
		results = []
		self.kb.CAPTURE.begin("inventory", 0, results.append)
		self.assertEqual(self.press("W"), [], "W walks no step")
		self.assertEqual(results[0].status, "swapped")
		self.assertEqual(self.press("W"), [("interface.ToggleInventoryWindow", ())])
		self.kb.CAPTURE.begin("pet", 1, results.append)
		self.assertEqual(self.press("K"), [])
		self.assertEqual(results[1].status, "bound")
		self.assertEqual(self.press("K"), [("interface.TogglePetWindow", ())])

	def test_a_combination_the_page_captures_fires_neither_half(self):
		self.kb.CAPTURE.begin("pet", 1, None)
		self.window.OnKeyDown(self.dik("LALT"))
		self.app.held = set([self.dik("LALT")])
		self.window.OnKeyDown(self.dik("K"))
		self.window.OnKeyUp(self.dik("K"))
		self.window.OnKeyUp(self.dik("LALT"))
		self.assertEqual(self.log, [])
		self.assertEqual(self.bindings.keys("pet"), [self.kb.key("P"), self.kb.alt("K")])

	def test_escape_ends_a_capture_and_still_reaches_the_game(self):
		self.kb.CAPTURE.begin("pet", 0, None)
		self.window.OnKeyDown(self.dik("ESCAPE"))
		self.assertFalse(self.kb.CAPTURE.is_armed())
		self.assertEqual(self.bindings.keys("pet"), [self.kb.key("P"), 0])


class Typing(unittest.TestCase):
	"""A legacy edit line with wndMgr's focus gets every key first (C++
	RunKeyDown asks the active window); it passes the game only these."""

	PASSED = ("F1", "F2", "F3", "F4", "LALT", "SYSRQ", "LCONTROL")

	def edit_line(self, kb):
		app = App(kb, [])
		source = support.source_of("ui.py", ("OnKeyDown",), inside="EditLine")
		body = "\n".join("\t" + line if line else line for line in source.split("\n"))
		namespace = {"app": app}
		exec(compile("class EditLine(object):\n%s\n" % body, "ui.py", "exec"), namespace)
		return namespace["EditLine"]()

	def test_a_key_typed_into_a_legacy_field_never_reaches_a_binding(self):
		kb = load_keybindings()
		modules = nui_test_support.Modules(app=App(kb, []))
		self.addCleanup(modules.restore)
		field = self.edit_line(kb)
		passed = set()
		for (code, token, name) in kb.KEYS:
			if not field.OnKeyDown(code):
				passed.add(token)
		self.assertEqual(passed, set(self.PASSED))
		bindings = kb.Bindings(opener=Files())
		bindings.assign("inventory", 0, kb.key("K"))
		self.assertFalse(field.OnKeyDown(kb.DIK["K"]) is False, "a rebound letter is still the field's")


if __name__ == "__main__":
	unittest.main()
