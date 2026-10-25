"""Headless tests of the legacy UI at the foundation cut (protocol 3; NOVA-96,
NOVA-97, NOVA-98): the legacy windows and rules in assets/root and
assets/uiscript, made over nui_game_support's stand-ins with the cut's module
constants (the names and values stageB/common.md lists, which the client
exports from the cut on). Run from tools/:

	python3 -B -m unittest legacy_foundation_test

The NovaUI windows subclass these legacy classes; tools/nui_*_test.py test
those. This file tests what the cut changes in the legacy code itself.
"""
import contextlib
import io
import os
import re
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.join(REPO, "assets", "root")
UISCRIPT = os.path.join(REPO, "assets", "uiscript", "uiscript")
LOCALES = os.path.join(REPO, "assets", "locale", "locale")

# The cut's slot layout (stageB/common.md "Target values"): 5 pages of 45,
# OLD's 40 wear slots from 225 (costume 244-252, rings and belt 253-255),
# the dragon soul equipment from 265 and the belt inventory from 295.
PAGE_SIZE = 45
PAGE_COUNT = 5
EQUIPMENT_START = PAGE_SIZE * PAGE_COUNT
WEAR_RING1, WEAR_RING2, WEAR_BELT = 28, 29, 30
CUT_PLAYER = {
	"INVENTORY_PAGE_SIZE": PAGE_SIZE, "INVENTORY_PAGE_COUNT": PAGE_COUNT, "INVENTORY_SLOT_COUNT": 311,
	"EQUIPMENT_SLOT_START": EQUIPMENT_START, "EQUIPMENT_PAGE_COUNT": 12,
	"NEW_EQUIPMENT_SLOT_START": EQUIPMENT_START + WEAR_RING1, "NEW_EQUIPMENT_SLOT_COUNT": 4,
	"DRAGON_SOUL_EQUIPMENT_SLOT_START": EQUIPMENT_START + 40, "METIN_SOCKET_MAX_NUM": 4,
}
CUT_ITEM = dict(("EQUIPMENT_" + name, EQUIPMENT_START + wear) for wear, name in enumerate(
	("BODY", "HEAD", "SHOES", "WRIST", "WEAPON", "NECK", "EAR", "UNIQUE1", "UNIQUE2", "ARROW")))
CUT_ITEM.update({
	"COSTUME_SLOT_START": EQUIPMENT_START + 19, "COSTUME_SLOT_COUNT": 9,
	"EQUIPMENT_RING1": EQUIPMENT_START + WEAR_RING1, "EQUIPMENT_RING2": EQUIPMENT_START + WEAR_RING2,
	"EQUIPMENT_BELT": EQUIPMENT_START + WEAR_BELT, "BELT_INVENTORY_SLOT_START": 295, "BELT_INVENTORY_SLOT_COUNT": 16,
	"ITEM_SOCKET_MAX_NUM": 4, "ITEM_APPLY_MAX_NUM": 7,
})
ROMAN = ("I", "II", "III", "IV", "V")


def quiet():
	"""The legacy windows print banners."""
	return contextlib.redirect_stdout(io.StringIO())


def read(path):
	with open(path, encoding="utf-8") as handle:
		return handle.read()


def read_uiscript(path, **names):
	"""The window dict of a uiscript file, executed as ui.PythonScriptLoader
	does, with the stand-in modules of the `with game:` around it."""
	namespace = {"SCREEN_WIDTH": 1600, "SCREEN_HEIGHT": 900, "__name__": "uiscript"}
	namespace.update(names)
	exec(compile(read(path), path, "exec"), namespace)
	return namespace


def children(value):
	"""Every child of a uiscript window dict, depth first."""
	for child in value.get("children", ()) or ():
		yield child
		for grandchild in children(child):
			yield grandchild


def child(value, name):
	return next(c for c in children(value) if c.get("name") == name)


class LegacyWorld(object):
	"""A stand-in client (nui_game_support.Game) with the Wave 3b legacy item
	windows' modules, every NovaUI window off, and the cut's slot constants
	on the player and item modules."""

	def __init__(self, cut=True):
		game = self.game = support.Game()
		support.install_wave2b_ui(game)
		support.install_wave3a_ui(game)
		support.install_wave3b_ui(game)
		game.modules["systemSetting"].GetUINuiWindows = lambda: ""
		game.modules["localeInfo"] = support.locale_info("en")
		for name in ("networkModule", "interfaceModule"):
			game.put(name, types.ModuleType(name))
		if cut:
			player, item = game.modules["player"], game.modules["item"]
			for name, value in CUT_PLAYER.items():
				setattr(player, name, value)
			for name, value in CUT_ITEM.items():
				setattr(item, name, value)
			support.define(player, "IsEquipmentSlot", lambda pos: EQUIPMENT_START <= pos < EQUIPMENT_START + 40)
			support.define(player, "IsCostumeSlot", lambda pos: EQUIPMENT_START + 19 <= pos < EQUIPMENT_START + 28)
			support.define(player, "IsBeltInventorySlot", lambda pos: 295 <= pos < 311)
		game.load_standard()

	def __enter__(self):
		self.game.__enter__()
		return self

	def __exit__(self, *exc):
		return self.game.__exit__(*exc)

	def load(self, name, file_name):
		with quiet():
			return self.game.load(name, file_name)

	def m(self, name):
		return self.game.loaded[name]


def make_inventory(world):
	"""The legacy inventory (Interface.__MakeWindows' wndInventory), shown."""
	module = world.load("uiInventory", "uiinventory.py")
	module.print = lambda *args, **kwargs: None
	with world, quiet():
		window = module.InventoryWindow()
		window.BindInterfaceClass(world.game.interface)
		window.SetItemToolTip(world.game.modules["uiToolTip"].ItemToolTip())
		window.Show()
	return window


class InventoryPages(unittest.TestCase):
	"""Five inventory pages (NOVA-97): one tab per page in the legacy
	inventory (uiinventory.py), the uiscript's five tabs, and the scans that
	cover every page."""

	def test_the_inventory_binds_one_tab_per_page_and_shows_the_pressed_page(self):
		world = LegacyWorld()
		world.game.give(4 * PAGE_SIZE + 3, 27001, 7)
		window = make_inventory(world)
		self.assertEqual(["Inventory_Tab_%02d" % (page + 1) for page in range(PAGE_COUNT)],
		                 [tab.name for tab in window.inventoryTab])
		self.assertTrue(window.inventoryTab[0].down)
		with world, quiet():
			window.inventoryTab[4].click()
		self.assertEqual(4, window.inventoryPageIndex)
		self.assertEqual([False, False, False, False, True], [tab.down for tab in window.inventoryTab])
		self.assertEqual((27001, 7), self.slot_of(window.wndItem, 3))
		with world, quiet():
			window.inventoryTab[2].click()
		self.assertEqual(2, window.inventoryPageIndex)
		self.assertEqual([False, False, True, False, False], [tab.down for tab in window.inventoryTab])
		self.assertEqual(0, self.slot_of(window.wndItem, 3)[0])

	@staticmethod
	def slot_of(slots, index):
		"""(vnum, count) of a legacy slot window's slot."""
		slot = slots.slots[index]
		return (slot["vnum"], slot["count"])

	def test_the_uiscript_has_five_small_tabs_in_a_row_over_the_bag(self):
		for path in (os.path.join(UISCRIPT, "inventorywindow.py"),
		             os.path.join(LOCALES, "ae", "ui", "inventorywindow.py")):
			with self.subTest(path=path):
				world = LegacyWorld()
				with world:
					window = read_uiscript(path)["window"]
				bag = child(window, "ItemSlot")
				board = child(window, "board")
				for page in range(PAGE_COUNT):
					tab = child(window, "Inventory_Tab_%02d" % (page + 1))
					self.assertEqual("radio_button", tab["type"])
					self.assertEqual(bag["x"] + 32 * page, tab["x"])
					self.assertEqual(33 + 191, tab["y"])
					self.assertEqual("d:/ymir work/ui/game/windows/tab_button_small_01.sub", tab["default_image"])
					self.assertEqual("d:/ymir work/ui/game/windows/tab_button_small_03.sub", tab["down_image"])
					self.assertEqual("INVENTORY_PAGE_BUTTON_TOOLTIP_%d" % (page + 1), tab["tooltip_text"])
					self.assertEqual(ROMAN[page], child(tab, "Inventory_Tab_%02d_Print" % (page + 1))["text"])
				# The small tab is 32 px wide: the five end where the bag's
				# five columns do, inside the board.
				self.assertLessEqual(bag["x"] + 32 * PAGE_COUNT, board["width"])
				self.assertEqual(bag["x"] + bag["x_count"] * bag["x_step"], bag["x"] + 32 * PAGE_COUNT)
				self.assertRaises(StopIteration, child, window, "Inventory_Tab_06")

	def test_every_page_tooltip_exists_in_every_locale(self):
		for locale in sorted(os.listdir(LOCALES)):
			path = os.path.join(LOCALES, locale, "locale_interface.txt")
			if not os.path.isfile(path):
				continue
			keys = set(line.split("\t")[0] for line in read(path).split("\n"))
			for page in range(PAGE_COUNT):
				self.assertIn("INVENTORY_PAGE_BUTTON_TOOLTIP_%d" % (page + 1), keys, locale)

	def test_the_equipment_slots_start_at_the_clients_equipment_start(self):
		"""EQUIPMENT_START_INDEX was the literal 90 (2 pages); it is the body's
		cell, wear 0, so the slots follow the client's page count."""
		for path in (os.path.join(UISCRIPT, "inventorywindow.py"),
		             os.path.join(LOCALES, "ae", "ui", "inventorywindow.py")):
			with self.subTest(path=path):
				world = LegacyWorld()
				with world:
					namespace = read_uiscript(path)
				self.assertEqual(EQUIPMENT_START, namespace["EQUIPMENT_START_INDEX"])
				indices = [slot["index"] for slot in child(namespace["window"], "EquipmentSlot")["slot"]]
				self.assertEqual(list(range(EQUIPMENT_START, EQUIPMENT_START + 11)), indices[:11])
				world = LegacyWorld(cut=False)
				with world:
					self.assertEqual(90, read_uiscript(path)["EQUIPMENT_START_INDEX"])

	def test_the_belt_uiscript_has_no_equipment_literal(self):
		self.assertNotIn("EQUIPMENT_START_INDEX", read(os.path.join(UISCRIPT, "beltinventorywindow.py")))

	def test_select_item_lists_the_stones_of_every_page(self):
		"""uiselectitem scanned INVENTORY_PAGE_SIZE * 2 cells (OLD too,
		uiSelectItem.py:89): a stone on page III to V never showed."""
		world = LegacyWorld()
		module = world.load("uiselectitem", "uiselectitem.py")
		stones = (5, PAGE_SIZE * 2 + 1, PAGE_SIZE * PAGE_COUNT - 1)
		for cell in stones:
			world.game.give(cell, 28030)
		world.game.metins.add(28030)
		world.game.give(PAGE_SIZE * PAGE_COUNT, 28030)  # the first equipment cell: not a bag cell
		with world, quiet():
			window = module.SelectItemWindow()
			window.LoadWindow()
			window.RefreshSlot()
		self.assertEqual(dict(enumerate(stones)), window.inventorySlotPosDict)



class WearOrder(unittest.TestCase):
	"""The equipment, costume and view-equip windows on OLD's 40-slot wear
	order (NOVA-97): the rings and the belt in the equipment window (wear
	28-30), the costume window's body and hair only (the other costume
	cells hold unported features), and the view's 16 entries."""

	CUT_EQUIPMENT = list(range(EQUIPMENT_START, EQUIPMENT_START + 11)) + [
		EQUIPMENT_START + WEAR_RING1, EQUIPMENT_START + WEAR_RING2, EQUIPMENT_START + WEAR_BELT]

	def test_the_equipment_window_holds_the_rings_and_the_belt_and_no_sash(self):
		for path in (os.path.join(UISCRIPT, "inventorywindow.py"),
		             os.path.join(LOCALES, "ae", "ui", "inventorywindow.py")):
			with self.subTest(path=path):
				world = LegacyWorld()
				with world:
					window = read_uiscript(path)["window"]
				base = child(window, "Equipment_Base")
				self.assertEqual("d:/ymir work/ui/equipment_bg_with_ring.tga", base["image"])
				slots = dict((slot["index"], (slot["x"], slot["y"])) for slot in child(window, "EquipmentSlot")["slot"])
				self.assertEqual(sorted(self.CUT_EQUIPMENT), sorted(slots))
				# The ring boxes of the with-ring art, either side of the belt.
				self.assertEqual((2, 106), slots[EQUIPMENT_START + WEAR_RING1])
				self.assertEqual((75, 106), slots[EQUIPMENT_START + WEAR_RING2])
				self.assertEqual((39, 106), slots[EQUIPMENT_START + WEAR_BELT])

	def test_the_with_ring_art_is_packed(self):
		groups = read(os.path.join(REPO, "assets", "groups.txt"))
		self.assertIn("metin2_patch_dss_box", groups.split())
		self.assertTrue(os.path.isfile(os.path.join(REPO, "assets", "metin2_patch_dss_box", "ymir work", "ui",
		                                            "equipment_bg_with_ring.tga")))

	def test_the_costume_window_shows_the_body_and_the_hair_only(self):
		world = LegacyWorld()
		with world:
			window = read_uiscript(os.path.join(UISCRIPT, "costumewindow.py"))["window"]
		indices = [slot["index"] for slot in child(window, "CostumeSlot")["slot"]]
		self.assertEqual([EQUIPMENT_START + 19, EQUIPMENT_START + 20], indices)

	def test_the_inventory_refreshes_the_rings_and_the_belt_and_the_costume_window_its_two(self):
		world = LegacyWorld()
		RING, BELT, BODY, HAIR, SASH = 70001, 18000, 41001, 45001, 85001
		world.game.give(EQUIPMENT_START + WEAR_RING1, RING)
		world.game.give(EQUIPMENT_START + WEAR_RING2, RING)
		world.game.give(EQUIPMENT_START + WEAR_BELT, BELT)
		world.game.give(EQUIPMENT_START + 19, BODY)
		world.game.give(EQUIPMENT_START + 20, HAIR)
		world.game.give(EQUIPMENT_START + 21, SASH)
		window = make_inventory(world)
		equipment = dict((index, slot["vnum"]) for index, slot in window.wndEquip.slots.items() if slot["vnum"])
		self.assertEqual({EQUIPMENT_START + WEAR_RING1: RING, EQUIPMENT_START + WEAR_RING2: RING,
		                  EQUIPMENT_START + WEAR_BELT: BELT}, equipment)
		with world, quiet():
			window.ClickCostumeButton()
		costume = dict((index, slot["vnum"]) for index, slot in window.wndCostume.wndEquip.slots.items() if slot["vnum"])
		self.assertEqual({EQUIPMENT_START + 19: BODY, EQUIPMENT_START + 20: HAIR}, costume)

	def test_the_view_dialog_places_olds_sixteen_entries(self):
		world = LegacyWorld()
		with world:
			window = read_uiscript(os.path.join(UISCRIPT, "equipmentdialog.py"))["window"]
		self.assertEqual("d:/ymir work/ui/equipment_bg_with_ring.tga", child(window, "EquipmentBaseImage")["image"])
		slots = dict((slot["index"], (slot["x"], slot["y"])) for slot in child(window, "EquipmentSlot")["slot"])
		# OLD uiscript/equipmentdialog.py:16-31: 0-10, the rings 13 and 14 and
		# the belt 15 (the costume body and hair, 11 and 12, are not shown).
		self.assertEqual(list(range(11)) + [13, 14, 15], sorted(slots))
		self.assertEqual({13: (2, 106), 14: (75, 106), 15: (39, 106)}, dict((i, slots[i]) for i in (13, 14, 15)))

	def test_the_legacy_view_dialog_shows_the_rings_and_the_belt_by_view_index(self):
		import nui_w4_world as w4
		world = w4.World(False)
		RING, BELT = 70001, 18000
		window = world.make("equipment-view", "uiEquipmentDialog", "EquipmentDialog",
		                    "nui_equipment_view.EquipmentDialog")
		with world.game, quiet():
			window.Open(77)
			for index, vnum in ((13, RING), (14, RING), (15, BELT), (23, BELT)):
				window.SetEquipmentDialogItem(index, vnum, 1)
		shown = dict((index, slot["vnum"]) for index, slot in window.slotWindow.slots.items() if slot["vnum"])
		self.assertEqual({13: RING, 14: RING, 15: BELT}, shown)



class Money64(unittest.TestCase):
	"""64-bit gold and exp in the legacy UI (NOVA-96): the 32-bit exp masks
	gone, OLD's k/m/b amounts, OLD's digits per money input (Q13: decided
	2026-10-25) from the client's constants."""

	EXP = 2 ** 40 + 12345          # past 32 bits, as level 150's exp is
	NEXT_EXP = 2 ** 41

	def test_the_character_window_shows_the_whole_exp(self):
		import nui_character_test as character
		world = character.World(False)
		P = character.P
		world.game.status.update({P["EXP"]: self.EXP, P["NEXT_EXP"]: self.NEXT_EXP})
		world.game.exp = self.EXP
		window = world.open()
		self.assertEqual(str(self.EXP), window.GetChild("Exp_Value").GetText())
		self.assertEqual(str(self.NEXT_EXP - self.EXP), window.GetChild("RestExp_Value").GetText())

	def test_the_taskbar_gauge_gets_the_whole_exp(self):
		game = support.Game()
		game.modules["systemSetting"].GetUINuiWindows = lambda: ""
		game.load_standard()
		with quiet():
			module = game.load("uiTaskBar", "uitaskbar.py")
		player = game.modules["player"]
		game.status.update({player.EXP: self.EXP, player.NEXT_EXP: self.NEXT_EXP})
		got = []
		bar = types.SimpleNamespace(RefreshStamina=lambda: None, SetHP=lambda *args: None, SetSP=lambda *args: None,
		                            SetExperience=lambda cur, nxt: got.append((cur, nxt)))
		with game:
			module.TaskBar.RefreshStatus(bar)
		self.assertEqual([(self.EXP, self.NEXT_EXP)], got)
		self.assertFalse(hasattr(module, "unsigned32"))

	def test_the_guild_exp_offer_opens_with_the_whole_exp_and_keeps_nine_digits(self):
		import nui_w4_world as w4
		import nui_guild_test as guild_test
		exp = self.EXP

		def setup(game):
			guild_test.guild(game)
			game.modules["player"].GetStatus = lambda kind: exp
		world = w4.World(False, setup=setup, social=True)
		window = world.make("guild", "uiGuild", "GuildWindow", "nui_guild.GuildWindow")
		with world.game, quiet():
			window.SetSkillToolTip(support.ToolTip("skill"))
			if window.CanOpen():
				window.Open()
			window.pageWindow["GUILD_INFO"].GetChild("OfferButton").click()
		offers = [dialog for dialog in world.game.dialogs if dialog._name == "uiPickMoney.PickMoneyDialog" and dialog.is_open]
		self.assertEqual(1, len(offers))
		self.assertEqual((exp, 100), offers[0].opened)
		self.assertEqual(9, offers[0].max, "OLD's 9 digits (Q19: decided 2026-10-25)")
		self.assertNotIn("unsigned32", read(os.path.join(ROOT, "uiguild.py")))

	def test_the_guild_exp_offer_sends_at_most_nine_digits(self):
		"""The offer's 9 digits (Q19) bound the amount too: OLD's k/m/b names
		more in 9 characters ("3b" is 3000000000, under the whole exp the
		dialog opens with), and net.SendGuildOfferPacket reads a 32-bit int,
		so OLD sent 4294967295 for it. The guild window's OnOffer, which the
		NovaUI guild window inherits, sends at most 999999999."""
		import nui_w4_world as w4
		import nui_guild_test as guild_test
		exp = 50 * 10 ** 9

		def setup(game):
			guild_test.guild(game)
			game.modules["player"].GetStatus = lambda kind: exp
		for nui_on in (False, True):
			with self.subTest(nui_on=nui_on):
				world = w4.World(nui_on, setup=setup, social=True)
				window = world.make("guild", "uiGuild", "GuildWindow", "nui_guild.GuildWindow")
				with world.game, quiet():
					window.SetSkillToolTip(support.ToolTip("skill"))
					if window.CanOpen():
						window.Open()
					if nui_on:
						w4.press(window, "offer_press", 0)
					else:
						window.pageWindow["GUILD_INFO"].GetChild("OfferButton").click()
				offers = [dialog for dialog in world.game.dialogs
				          if dialog._name == "uiPickMoney.PickMoneyDialog" and dialog.is_open]
				self.assertEqual((exp, 100), offers[-1].opened)
				mark = world.mark()
				with world.game, quiet():
					for amount in (1234, 10 ** 9 - 1, 10 ** 9, 3 * 10 ** 9, exp):
						offers[-1].accept(amount)
				self.assertEqual([1234] + [10 ** 9 - 1] * 4,
				                 [args[0] for name, args in world.game.log[mark:] if name == "net.SendGuildOfferPacket"])

	def test_a_money_string_holds_thirteen_digits(self):
		locale = support.locale_info("en")
		self.assertEqual("2.000.000.000.000 Yang", locale.NumberToMoneyString(2000000000000))

	def dialog_modules(self, **player):
		"""uicommon.py and uipickmoney.py over the dialog kit's stand-ins
		(nui_dialogs_test's), every NovaUI window off."""
		base = support.support
		stub = base.stub_module
		state = base.NuiState()
		modules = base.Modules(
			nui=base.make_nui(state), dbg=base.make_dbg(), systemSetting=base.make_setting(flag=0, windows=""),
			wndMgr=base.make_wndmgr(mouse=(800, 600)), ui=base.make_legacy_ui(),
			localeInfo=base.LocaleInfo(MONEY_INPUT_DIALOG_SELLPRICE="Sales Price: ", NumberToMoneyString=base.number_to_money),
			app=stub("app", IsRTL=lambda: False, GetTime=lambda: 0.0), ime=stub("ime", SetCursorPosition=lambda n: None),
			uiScriptLocale=stub("uiScriptLocale", LOCALE_UISCRIPT_PATH="locale/"),
			exception=stub("exception", Abort=lambda message: self.fail(message)), player=stub("player", **player))
		self.addCleanup(modules.restore)
		modules.load("nui_windows")
		return modules

	def test_olds_k_m_b_amounts(self):
		module = self.dialog_modules().load("uiPickMoney", "uipickmoney.py")
		convert = module.ConvertTextToMoney
		cases = {"": 0, "abc": 0, "0": 0, "7": 7, "1234567": 1234567, "5k": 5000, "5K": 5000, "3m": 3000000,
		         "3kk": 3000000, "2b": 2000000000, "2B": 2000000000, "2000b": 2000000000000, "1kkk": 1000000000,
		         "12k5": 12000}
		self.assertEqual(cases, dict((text, convert(text)) for text in cases))

	def test_the_pick_money_dialog_accepts_k_m_b_up_to_its_maximum(self):
		module = self.dialog_modules().load("uiPickMoney", "uipickmoney.py")
		for text, maximum, expected in (("5k", 10 ** 6, [5000]), ("2m", 10 ** 6, [10 ** 6]), ("40", 100, [40]),
		                                ("abc", 100, []), ("0", 100, []), ("", 100, [])):
			with self.subTest(text=text):
				got = []
				dialog = module.PickMoneyDialog()
				dialog.LoadDialog()
				dialog.SetAcceptEvent(lambda money: got.append(money))
				dialog.Open(maximum)
				dialog.pickValueEditLine.SetText(text)
				dialog.OnAccept()
				self.assertEqual(expected, got)
				self.assertFalse(dialog.IsShow())
		self.assertIs(module.LegacyPickMoneyDialog, type(dialog), "the factory block makes the legacy class")

	def test_the_money_input_dialog_takes_the_money_digits(self):
		modules = self.dialog_modules(MONEY_DIGITS=13)
		module = modules.load("uiCommon", "uicommon.py")
		dialog = module.MoneyInputDialog()
		self.assertEqual([("SetMax", 13)], [call for call in dialog.inputValue.calls if call[0] == "SetMax"])
		dialog.inputValue.calls[:] = []
		dialog.SetMaxLength(20)
		dialog.SetMaxLength(6)
		self.assertEqual([("SetMax", 13), ("SetMax", 6)], [call for call in dialog.inputValue.calls if call[0] == "SetMax"])
		world = LegacyWorld()
		world.game.modules["player"].MONEY_DIGITS = 13
		with world:
			namespace = read_uiscript(os.path.join(UISCRIPT, "moneyinputdialog.py"))
		self.assertEqual(13, child(namespace["window"], "InputValue")["input_limit"])

	def test_the_inventory_pick_money_takes_the_inventory_digits(self):
		for digits in (7, 9):
			with self.subTest(digits=digits):
				world = LegacyWorld()
				world.game.modules["player"].INVENTORY_MONEY_DIGITS = digits
				world.game.elk = 2000000000000
				window = make_inventory(world)
				with world, quiet():
					window.OpenPickMoneyDialog()
				self.assertEqual((2000000000000,), window.dlgPickMoney.opened)
				self.assertEqual(digits, window.dlgPickMoney.max)

	def test_the_exchange_money_takes_the_exchange_digits(self):
		import nui_w4_world as w4
		world = w4.World(False)
		world.game.modules["player"].EXCHANGE_MONEY_DIGITS = 12
		window = world.make("exchange", "uiExchange", "ExchangeDialog", "nui_exchange.ExchangeDialog")
		with world.game, quiet():
			window.LoadDialog()
		self.assertEqual(12, window.dlgPickMoney.max)


class AnyCall(types.ModuleType):
	"""A C++ module stand-in whose every function does nothing and returns 0."""

	def __getattr__(self, name):
		if name.startswith("__"):
			raise AttributeError(name)
		return lambda *args, **kwargs: 0


class RecordingIme(AnyCall):
	"""ime, recording the input mode calls. Without `money` it lacks
	SetMoneyMode, as the client does until it exports OLD's money mode."""

	MODES = ("SetMoneyMode", "SetNumberMode", "SetStringMode")

	def __init__(self, money):
		AnyCall.__init__(self, "ime")
		self.money = money
		self.modes = []

	def __getattr__(self, name):
		if name == "SetMoneyMode" and not self.money:
			raise AttributeError(name)
		if name in self.MODES:
			return lambda: self.modes.append(name)
		return AnyCall.__getattr__(self, name)


class MoneyMode(unittest.TestCase):
	"""The pick money dialog's edit line takes OLD's k/m/b amounts: the
	uiscript's "only_number" 2 is OLD's money mode, which the client's own
	ui.py turns into ime.SetMoneyMode on focus (OLD ui.py:1842-1843,
	1890-1893, 9507-9511), and a client without that export keeps today's
	digits."""

	def real_ui(self, ime):
		"""assets/root/ui.py itself, over do-nothing C++ modules and `ime`."""
		import builtins
		import importlib.util
		from unittest import mock
		patcher = mock.patch.dict(sys.modules)
		patcher.start()
		self.addCleanup(patcher.stop)
		for name in ("app", "grp", "snd", "wndMgr", "item", "skill", "localeInfo", "dbg", "guild", "uiScriptLocale"):
			sys.modules[name] = AnyCall(name)
		sys.modules["ime"] = ime
		for name, value in (("TRUE", True), ("FALSE", False)):
			if not hasattr(builtins, name):
				setattr(builtins, name, value)
				self.addCleanup(delattr, builtins, name)
		spec = importlib.util.spec_from_file_location("ui", os.path.join(ROOT, "ui.py"))
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)
		return module

	def focused_mode(self, money, only_number):
		"""The ime modes the pick money uiscript's edit line sets on focus,
		with its "only_number" replaced by `only_number` (None: no key)."""
		ime = RecordingIme(money)
		ui = self.real_ui(ime)
		value = dict(child(read_uiscript(os.path.join(UISCRIPT, "pickmoneydialog.py"))["window"], "money_value"))
		if only_number is None:
			del value["only_number"]
		else:
			value["only_number"] = only_number
		window = ui.EditLine()
		with quiet():
			self.assertTrue(ui.PythonScriptLoader().LoadElementEditLine(window, value, ui.Window()))
		window.OnSetFocus()
		return ime.modes

	def test_the_pick_money_uiscript_asks_for_olds_money_mode(self):
		self.real_ui(RecordingIme(True))
		value = child(read_uiscript(os.path.join(UISCRIPT, "pickmoneydialog.py"))["window"], "money_value")
		self.assertEqual(2, value["only_number"])

	def test_the_money_mode_lets_the_amount_letters_through(self):
		self.assertEqual(["SetMoneyMode"], self.focused_mode(True, 2))

	def test_a_client_without_the_money_mode_takes_digits(self):
		self.assertEqual(["SetNumberMode"], self.focused_mode(False, 2))

	def test_the_other_edit_lines_keep_their_modes(self):
		for money in (True, False):
			with self.subTest(money=money):
				self.assertEqual(["SetNumberMode"], self.focused_mode(money, 1))
				self.assertEqual(["SetStringMode"], self.focused_mode(money, 0))
				self.assertEqual(["SetStringMode"], self.focused_mode(money, None))

	def test_the_last_mode_set_is_the_one_used(self):
		ime = RecordingIme(True)
		ui = self.real_ui(ime)
		window = ui.EditLine()
		window.SetMax(7)
		window.SetMoneyMode()
		window.OnSetFocus()
		window.SetNumberMode()
		window.OnSetFocus()
		self.assertEqual(["SetMoneyMode", "SetNumberMode"], ime.modes)


if __name__ == "__main__":
	unittest.main()
