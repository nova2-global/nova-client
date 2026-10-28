"""Headless tests of the legacy UI at the foundation cut (protocol 3; NOVA-96,
NOVA-97, NOVA-98): the legacy windows and rules in assets/root and
assets/uiscript, made over nui_game_support's stand-ins with the cut's module
constants (the names and values stageB/common.md lists, which the client
exports from the cut on). Run from tools/:

	python3 -B -m unittest legacy_foundation_test

The NovaUI windows subclass these legacy classes; tools/nui_*_test.py test
those. This file tests what the cut changes in the legacy code itself.
"""
import collections
import contextlib
import io
import itertools
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


# Tahoma at 12 px (UI_DEF_FONT in every locale) as the client lays it out:
# FreeType's hinted advances, which GrpFontTexture.cpp rounds up, and what
# the live frames measure (S3-money: "5.352.360.737 Yang" is 113 px wide,
# "999.999.999.999 Yang" 127 px).
TAHOMA_12 = dict([(digit, 7) for digit in "0123456789"] + [(".", 4), (" ", 4), ("Y", 7), ("a", 6), ("n", 7), ("g", 7)])


def sub_image_width(path):
	"""The width of a .sub image the uiscripts name as "d:/ymir work/...",
	from the file in the asset groups."""
	import glob
	found = glob.glob(os.path.join(REPO, "assets", "*", path.replace("d:/", "", 1)))
	values = dict(line.split(None, 1) for line in read(found[0]).split("\n") if " " in line.strip())
	return int(values["right"]) - int(values["left"])


class MoneySlot(unittest.TestCase):
	"""The legacy inventory's money slot holds the cut's purses (GOLD_MAX
	2,000,000,000,000, NOVA-96). The slot is parameter_slot_05 with the text
	right-aligned 3 px from its right edge; with its unit, a 13-digit purse
	is 138 px wide in the slot's 130, so its first digit ran under the coin
	icon left of the slot (live run RUN-A-D2: "999.999.999.999 Yang" shown
	for 1,999,999,999,999)."""

	GOLD_MAX = 2000000000000

	def slot(self, path):
		"""(the slot's width, the text's offset from its right edge)."""
		world = LegacyWorld()
		with world:
			window = read_uiscript(path)["window"]
		slot, text = child(window, "Money_Slot"), child(window, "Money")
		self.assertEqual("right", text["horizontal_align"])
		self.assertEqual("right", text["text_horizontal_align"])
		return sub_image_width(slot["default_image"]), text["x"]

	def shown(self, amounts):
		"""The money text the legacy inventory shows for each amount."""
		world = LegacyWorld()
		window = make_inventory(world)
		texts = []
		for amount in amounts:
			world.game.elk = amount
			with world, quiet():
				window.RefreshStatus()
			texts.append(window.wndMoney.GetText())
		return texts

	def test_every_purse_fits_the_slot_with_the_right_margin_on_the_left_too(self):
		amounts = [10 ** digits - 1 for digits in range(1, 14)] + [10 ** 11, self.GOLD_MAX]
		texts = self.shown(amounts)
		for path in (os.path.join(UISCRIPT, "inventorywindow.py"), os.path.join(LOCALES, "ae", "ui", "inventorywindow.py")):
			width, margin = self.slot(path)
			self.assertEqual((130, 3), (width, margin))
			for amount, text in zip(amounts, texts):
				with self.subTest(path=path, amount=amount):
					self.assertLessEqual(margin + sum(TAHOMA_12[c] for c in text) + margin, width, text)
					self.assertEqual(str(amount), text.split(" ")[0].replace(".", ""), "the whole amount")

	def test_the_unit_stays_while_it_fits(self):
		locale = support.locale_info("en")
		amounts = [0, 7, 1234567, 4300000000, 99999999999]
		self.assertEqual([locale.NumberToMoneyString(amount) for amount in amounts], self.shown(amounts))
		self.assertEqual(["100.000.000.000", "1.999.999.999.999", "2.000.000.000.000"],
		                 self.shown([10 ** 11, 1999999999999, self.GOLD_MAX]))


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


def load_real_ui(test, **modules):
	"""assets/root/ui.py itself, over do-nothing C++ modules (AnyCall) but
	`modules`, for the length of `test`."""
	import builtins
	import importlib.util
	from unittest import mock
	patcher = mock.patch.dict(sys.modules)
	patcher.start()
	test.addCleanup(patcher.stop)
	for name in ("app", "grp", "snd", "wndMgr", "item", "skill", "localeInfo", "dbg", "guild", "uiScriptLocale", "ime"):
		sys.modules[name] = modules.get(name) or AnyCall(name)
	for name, value in (("TRUE", True), ("FALSE", False)):
		if not hasattr(builtins, name):
			setattr(builtins, name, value)
			test.addCleanup(delattr, builtins, name)
	spec = importlib.util.spec_from_file_location("ui", os.path.join(ROOT, "ui.py"))
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class MoneyMode(unittest.TestCase):
	"""The pick money dialog's edit line takes OLD's k/m/b amounts: the
	uiscript's "only_number" 2 is OLD's money mode, which the client's own
	ui.py turns into ime.SetMoneyMode on focus (OLD ui.py:1842-1843,
	1890-1893, 9507-9511), and a client without that export keeps today's
	digits."""

	def real_ui(self, ime):
		"""assets/root/ui.py itself, over do-nothing C++ modules and `ime`."""
		return load_real_ui(self, ime=ime)

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


class LaidOutText(AnyCall):
	"""wndMgr's text lines as CTextLine and CGraphicTextInstance keep them
	(PythonWindow.cpp, GrpTextInstance.cpp): SetFontName only changes the
	font; SetText lays the text out in the font set then, but only a text
	that differs from the one the line holds (SetValue keeps an equal one);
	GetTextSize is the laid-out width. A digit is 7 px in Tahoma 12 and 8 px
	in Tahoma 14, as the client lays them out (frame S4-exp 023: the
	11-digit "40000000000" is 88 px wide in the LARGE font)."""

	DIGIT = {"Tahoma:12": 7, "Tahoma:14": 8}

	def __init__(self):
		AnyCall.__init__(self, "wndMgr")
		self.lines = {}

	def RegisterTextLine(self, window, layer):
		handle = len(self.lines) + 1
		self.lines[handle] = {"font": None, "text": "", "laid_font": None, "width": 0}
		return handle

	def SetFontName(self, handle, name):
		self.lines[handle]["font"] = name

	def SetText(self, handle, text):
		line = self.lines[handle]
		if text != line["text"]:
			line.update(text=text, laid_font=line["font"], width=self.DIGIT[line["font"]] * len(text))

	def GetText(self, handle):
		return self.lines[handle]["text"]

	def GetTextSize(self, handle):
		return (self.lines[handle]["width"], 14)


class ExpLabels(unittest.TestCase):
	"""The character window's EXP and Necessary EXP values (NOVA-96): a
	LARGE-font text centred on a 90-px label, sized for the uiscript's
	11-digit placeholder. Levels 140-150 need 100,000,000,000 to
	200,000,000,000 exp, 12 digits, 96 px in the LARGE font: they ran past
	their labels into each other (live run RUN-A-D3)."""

	LABELS = (("Exp_Value", "Exp_Slot"), ("RestExp_Value", "RestExp_Slot"))
	FONTS = {"UI_DEF_FONT": "Tahoma:12", "UI_DEF_FONT_LARGE": "Tahoma:14"}

	def labels(self, path):
		"""[(the value's uiscript dict, the label art's width)]."""
		world = LegacyWorld()
		world.game.modules["uiScriptLocale"].WINDOWS_PATH = "d:/locale/en/ui/windows/"
		with world:
			window = read_uiscript(path)["window"]
		return [(child(window, value), sub_image_width(child(window, art)["image"])) for value, art in self.LABELS]

	def loaded(self, value):
		"""(the wndMgr stand-in, the line) of a value loaded by the real
		ui.py's PythonScriptLoader, as the legacy window loads it."""
		wnd = LaidOutText()
		locale = AnyCall("localeInfo")
		for name, font in self.FONTS.items():
			setattr(locale, name, font)
		ui = load_real_ui(self, wndMgr=wnd, localeInfo=locale)
		line = ui.TextLine()
		with quiet():
			self.assertTrue(ui.PythonScriptLoader().LoadElementText(line, value, ui.Window()))
		return wnd, line

	def test_a_value_stays_inside_its_label(self):
		for path in (os.path.join(UISCRIPT, "characterwindow.py"), os.path.join(LOCALES, "ae", "ui", "characterwindow.py")):
			for value, art_width in self.labels(path):
				wnd, line = self.loaded(value)
				for text in ("12345678901", "99999999999", "100000000000", "199999999999", "200000000000"):
					with self.subTest(path=path, value=value["name"], text=text):
						line.SetText(text)
						laid = wnd.lines[line.hWnd]
						self.assertEqual((text, laid["font"]), (laid["text"], laid["laid_font"]), "laid out in its font")
						self.assertGreaterEqual(value["x"] - laid["width"] / 2, 0)
						self.assertLessEqual(value["x"] + laid["width"] / 2, art_width)

	def test_up_to_eleven_digits_keep_the_large_font(self):
		value, _ = self.labels(os.path.join(UISCRIPT, "characterwindow.py"))[0]
		wnd, line = self.loaded(value)
		for text, font in (("12345678901", "Tahoma:14"), ("150000000000", "Tahoma:12"), ("150000000000", "Tahoma:12"),
		                   ("40000000000", "Tahoma:14"), ("", "Tahoma:14"), ("199999999999", "Tahoma:12")):
			with self.subTest(text=text):
				line.SetText(text)
				laid = wnd.lines[line.hWnd]
				self.assertEqual((text, font), (laid["text"], laid["laid_font"]))
				self.assertEqual(font, laid["font"])
		self.assertEqual("Tahoma:14", line.fontName, "the line's own font stays the LARGE one")


def tooltip_world(items, sizes="foundation"):
	"""nui_tooltip_corpus's legacy side: uitooltip.py alone over the corpus
	stand-ins, with `items` as the corpus rows; "foundation" gives the rules
	the cut's 4 sockets and 7 applies."""
	import nui_tooltip_corpus as corpus_tool
	data = {"items": dict((str(vnum), row) for vnum, row in items.items()), "skills": {}, "mobs": {}}
	return corpus_tool, corpus_tool.TipWorld(data, recorder=False, sizes=sizes)


def tooltip_texts(corpus_tool, world, case):
	"""The text rows the legacy tooltip shows for a case (its tips' stand-in
	rows), and the error a rule raised (None)."""
	base = {"sockets": [0, 0, 0, 0], "attrs": [], "player": {"level": 150, "race": 0}, "clock": 1700000000}
	base.update(case)
	with world:
		tips, error = corpus_tool.run_case(world, base)
		rows = [row for tip in tips for row in corpus_tool.stand_in_rows(tip)]
	return [row[1] for row in rows if row[0] == "text"], error


ITEM_BASE = {"size": [1, 1], "antiflags": 0, "flags": 0, "wear": 0, "limits": [[1, 0], [0, 0]],
             "values": [0] * 6, "price": {"buy": 100, "sell": 20}, "desc": "", "summary": ""}


class TooltipSockets(unittest.TestCase):
	"""Four sockets in the legacy tooltips (NOVA-97): an accessory's jewels
	raise all of its applies (OLD's seven), and item links carry four
	socket tokens before the attributes."""

	BRACELET = dict(ITEM_BASE, name="Bracelet", type=2, subtype=3, wear=8,
	                applies=[["APPLY_MAX_HP", 1000], ["APPLY_ATT_SPEED", 10], ["APPLY_MOV_SPEED", 20],
	                         ["APPLY_CRITICAL_PCT", 5]], icon="icon/item/14000.tga")
	SWORD = dict(ITEM_BASE, name="Sword+0", type=1, subtype=0, size=[1, 2], wear=16,
	             applies=[["APPLY_ATT_SPEED", 22]], values=[0, 0, 15, 19, 13, 15], icon="icon/item/00010.tga")
	STONE = dict(ITEM_BASE, name="Stone of Penetration+0", type=10, subtype=0, wear=16,
	             applies=[["APPLY_PENETRATE_PCT", 1]], icon="icon/item/28000.tga")

	def test_an_accessory_jewel_raises_every_apply(self):
		corpus_tool, world = tooltip_world({14000: self.BRACELET})
		locale = world.game.modules["localeInfo"]
		# Two jewels of three: the first and second jewel's share of each apply
		# (10 % and 20 % - 10 %, at least 1, 2 - 1).
		texts, error = tooltip_texts(corpus_tool, world, {"context": "AddItemData", "vnum": 14000,
		                                                    "sockets": [2, 3, 0, 0]})
		self.assertIsNone(error)
		for jewel in ((100, 1, 2, 1), (100, 1, 2, 1)):
			for line in (locale.TOOLTIP_MAX_HP(jewel[0]), locale.TOOLTIP_ATT_SPEED(jewel[1]),
			             locale.TOOLTIP_MOV_SPEED(jewel[2]), locale.TOOLTIP_APPLY_CRITICAL_PCT(jewel[3])):
				self.assertIn(line, texts)
		self.assertEqual(2, texts.count(locale.TOOLTIP_APPLY_CRITICAL_PCT(1)), "both jewels' lines")
		self.assertEqual(2, texts.count(locale.TOOLTIP_MOV_SPEED(2)))

	def test_an_accessory_of_two_applies_keeps_its_two_lines(self):
		bracelet = dict(self.BRACELET, applies=[["APPLY_MAX_HP", 1000], ["APPLY_ATT_SPEED", 10]])
		corpus_tool, world = tooltip_world({14000: bracelet}, sizes="today")
		locale = world.game.modules["localeInfo"]
		texts, error = tooltip_texts(corpus_tool, world, {"context": "AddItemData", "vnum": 14000,
		                                                    "sockets": [1, 3, 0]})
		self.assertIsNone(error)
		self.assertEqual(1, texts.count(locale.TOOLTIP_MAX_HP(100)))
		self.assertEqual(1, texts.count(locale.TOOLTIP_ATT_SPEED(1)))

	def test_a_link_reads_four_sockets_then_the_attributes(self):
		corpus_tool, world = tooltip_world({10: self.SWORD, 28030: self.STONE})
		locale = world.game.modules["localeInfo"]
		# item:vnum:flag:socket0..socket3:attribute type:value (hex but the value).
		link = "item:a:1:%x:1:1:1:1:1500" % 28030
		texts, error = tooltip_texts(corpus_tool, world, {"context": "SetHyperlinkItem", "vnum": 10, "link": link})
		self.assertIsNone(error)
		self.assertIn("Stone of Penetration+0", texts)
		self.assertEqual(3, texts.count(locale.TOOLTIP_SOCKET_EMPTY), "three silver sockets after the stone")
		self.assertIn(locale.TOOLTIP_MAX_HP(1500), texts, "the attribute after the fourth socket")


class TooltipSocketValues(unittest.TestCase):
	"""An item tooltip with no description widens itself for the stone lines
	its sockets hold (uitooltip.py __CalculateToolTipWidth). Only a weapon's
	and an armour's sockets hold stones, as __AppendMetinSlotInfo shows them;
	1 and 2 are empty sockets, an accessory's sockets count its jewels, a dew
	keeps its apply, value and time there and a timed costume its end time.
	The client logs "Cannot find item by <value>" for item.SelectItem of a
	value that is no item (PythonItemModule.cpp itemSelectItem), and a value
	that happens to be one measured that item's apply instead (live run
	RUN-B-D2: a dew 50821 with 15 12 600, OLD's costume 41324 with its end
	time 1793672524)."""

	SWORD = TooltipSockets.SWORD
	STONE = TooltipSockets.STONE
	# Values the dew's sockets hold that are items too: they must not count.
	OTHER = dict(ITEM_BASE, name="Sword+5", type=1, subtype=0, wear=16, applies=[["APPLY_ATT_SPEED", 22]])
	DEW = dict(ITEM_BASE, name="Red Dew", type=27, subtype=0, icon="icon/item/50821.tga")
	COSTUME = dict(ITEM_BASE, name="Crescent Warrior", type=28, subtype=0, wear=1,
	               limits=[[8, 604800], [0, 0]], icon="icon/item/41324.tga")
	BRACELET = dict(TooltipSockets.BRACELET, applies=[["APPLY_MAX_HP", 1000]])
	ITEMS = {10: SWORD, 12: OTHER, 15: OTHER, 28030: STONE, 50821: DEW, 41324: COSTUME, 14000: BRACELET}

	def run_tooltip(self, vnum, sockets, items=None):
		"""(the item.SelectItem vnums of one AddItemData, the tooltip)."""
		corpus_tool, world = tooltip_world(self.ITEMS if items is None else items)
		mark = len(world.game.log)
		base = {"context": "AddItemData", "vnum": vnum, "sockets": sockets, "attrs": [],
		        "player": {"level": 150, "race": 0}, "clock": 1700000000}
		with world:
			tips, error = corpus_tool.run_case(world, base)
		self.assertIsNone(error)
		return [args[0] for name, args in world.game.log[mark:] if name == "item.SelectItem"], tips[0]

	def test_no_socket_value_of_an_item_without_stones_is_selected(self):
		for vnum, sockets in ((50821, [15, 12, 600, 0]), (50821, [17, 5, 7, 0]), (41324, [1793672524, 2, 0, 0]),
		                      (14000, [2, 3, 0, 0])):
			with self.subTest(vnum=vnum, sockets=sockets):
				selected, tip = self.run_tooltip(vnum, sockets)
				self.assertEqual([], [value for value in selected if value in sockets], selected)
				# The same tooltip where no socket value is an item.
				items = dict((key, row) for key, row in self.ITEMS.items() if key not in sockets or key == vnum)
				_, alone = self.run_tooltip(vnum, sockets, items)
				self.assertEqual(alone.toolTipWidth, tip.toolTipWidth, "no other item's apply widened it")

	def test_a_weapon_counts_its_stone_and_not_its_empty_sockets(self):
		selected, tip = self.run_tooltip(10, [28030, 1, 2, 0])
		self.assertIn(28030, selected)
		self.assertNotIn(1, selected)
		self.assertNotIn(2, selected)
		self.assertGreater(tip.toolTipWidth, tip.TOOL_TIP_WIDTH, "the stone's line widens it")
		_, alone = self.run_tooltip(10, [28030, 0, 0, 0])
		self.assertEqual(alone.toolTipWidth, tip.toolTipWidth, "by the stone alone")



# OLD's applies 92-108 by OLD's Python names (OLD PythonItemModule.cpp), as
# the client exports them from the cut on (stageB/contract.md: APPLY 92-108).
OLD_APPLIES = {
	"APPLY_BLEEDING_REDUCE": 92, "APPLY_BLEEDING_PCT": 93, "APPLY_ATTBONUS_WOLFMAN": 94, "APPLY_RESIST_WOLFMAN": 95,
	"APPLY_RESIST_CLAW": 96, "APPLY_ANTI_RESIST_MAGIC": 97, "APPLY_ATTBONUS_BOSS": 98, "APPLY_ATTBONUS_METIN_STONE": 99,
	"APPLY_ENCHANT_ELECT": 100, "APPLY_ENCHANT_FIRE": 101, "APPLY_ENCHANT_ICE": 102, "APPLY_ENCHANT_WIND": 103,
	"APPLY_ENCHANT_EARTH": 104, "APPLY_ENCHANT_DARK": 105, "APPLY_ATTBONUS_ELEMENTAL": 106, "APPLY_ANTI_HUMAN": 107,
	"APPLY_ATTBONUS_UNDEAD_DEVIL": 108,
}
APPLY_TEXTS = {
	92: "TOOLTIP_APPLY_BLEEDING_REDUCE", 93: "TOOLTIP_APPLY_BLEEDING_PCT", 94: "TOOLTIP_APPLY_ATTBONUS_WOLFMAN",
	95: "TOOLTIP_APPLY_RESIST_WOLFMAN", 96: "TOOLTIP_APPLY_RESIST_CLAW", 97: "TOOLTIP_ANTI_RESIST_MAGIC",
	98: "TOOLTIP_APPLY_ATTBONUS_BOSS", 99: "TOOLTIP_APPLY_ATTBONUS_METIN_STONE", 100: "TOOLTIP_APPLY_ENCHANT_ELECT",
	101: "TOOLTIP_APPLY_ENCHANT_FIRE", 102: "TOOLTIP_APPLY_ENCHANT_ICE", 103: "TOOLTIP_APPLY_ENCHANT_WIND",
	104: "TOOLTIP_APPLY_ENCHANT_EARTH", 105: "TOOLTIP_APPLY_ENCHANT_DARK", 106: "TOOLTIP_APPLY_ATTBONUS_ELEMENTAL",
	107: "TOOLTIP_APPLY_RESIST_HUMAN",
}


def read_locale(locale, name="locale_game.txt"):
	"""{key: (text, type)} of a locale file."""
	keys = {}
	for line in read(os.path.join(LOCALES, locale, name)).split("\n"):
		tokens = line.split("\t")
		if len(tokens) >= 2 and tokens[0]:
			keys[tokens[0]] = (tokens[1], tokens[2].strip() if len(tokens) > 2 else "")
	return keys


def locales():
	return sorted(name for name in os.listdir(LOCALES) if os.path.isfile(os.path.join(LOCALES, name, "locale_game.txt")))


class TooltipApplies(unittest.TestCase):
	"""OLD's applies 92-108 in the legacy tooltip's affect table (NOVA-98)
	and their texts in every locale."""

	SWORD = TooltipSockets.SWORD

	def world(self, names):
		corpus_tool, world = tooltip_world({10: self.SWORD})
		item = world.game.modules["item"]
		for name, value in names.items():
			setattr(item, name, value)
		with quiet():
			world.game.load("uiToolTip", "uitooltip.py")
		return corpus_tool, world

	def test_every_apply_from_92_to_107_shows_olds_text(self):
		corpus_tool, world = self.world(OLD_APPLIES)
		locale = world.game.modules["localeInfo"]
		with world:
			table = world.m("uiToolTip").ItemToolTip.AFFECT_DICT
		for apply, key in APPLY_TEXTS.items():
			self.assertEqual(getattr(locale, key)(12), table[apply](12), key)

	def test_a_name_that_is_no_number_adds_no_apply(self):
		"""The stand-in item module answers a function for a name it does not
		define, as no client does: only an int constant makes an entry."""
		corpus_tool, world = self.world({})
		with world:
			table = world.m("uiToolTip").ItemToolTip.AFFECT_DICT
		self.assertEqual([], [key for key in table if not isinstance(key, int)])
		self.assertNotIn(98, table)
		self.assertNotIn(108, table)

	def test_an_apply_the_client_does_not_export_keeps_the_unknown_line(self):
		corpus_tool, world = self.world({})
		world.game.modules["item"].lack(*OLD_APPLIES)
		with quiet():
			world.game.load("uiToolTip", "uitooltip.py")
		sword = dict(self.SWORD, applies=[[98, 10]])
		world.data.items[10] = sword
		texts, error = tooltip_texts(corpus_tool, world, {"context": "AddItemData", "vnum": 10})
		self.assertIsNone(error)
		self.assertIn("UNKNOWN_TYPE[98] 10", texts)

	def test_a_tooltip_shows_the_new_applies_and_the_fused_undead_and_devil(self):
		corpus_tool, world = self.world(OLD_APPLIES)
		world.data.items[10] = dict(self.SWORD, applies=[[98, 10], [108, 15], [93, 4]])
		texts, error = tooltip_texts(corpus_tool, world, {"context": "AddItemData", "vnum": 10})
		self.assertIsNone(error)
		self.assertIn("Strong against Bosses +10%", texts)
		self.assertIn("Strong against Undead & Devils +15%", texts)
		self.assertIn("Chance to bleed +4%", texts)

	def test_the_fused_text_follows_olds_rule(self):
		corpus_tool, world = tooltip_world({10: self.SWORD})
		fuse = world.m("uiToolTip").FuseAffectTexts
		fmt = lambda text: (lambda value: text % value)
		self.assertEqual("Stark gegen Untote & Teufel +7%",
		                 fuse((fmt("Stark gegen Untote +%d%%"), fmt("Stark gegen Teufel +%d%%")))(7))
		self.assertEqual("Ölülere & Şeytanlara karşı güçlü +%7",
		                 fuse((fmt("Ölülere karşı güçlü +%%%d"), fmt("Şeytanlara karşı güçlü +%%%d")))(7))
		# Different values, or a line without one: the lines joined.
		self.assertEqual("A +1 / B +2", fuse((lambda v: "A +1", lambda v: "B +2"))(0))
		self.assertEqual("A / B", fuse((lambda v: "A", lambda v: "B"))(0))
		# One line, or none.
		self.assertEqual("A +3", fuse((lambda v: "A +%d" % v, lambda v: ""))(3))
		self.assertEqual("", fuse((lambda v: "",))(3))
		# Equal texts come out once (OLD doubled them).
		self.assertEqual("Same +5", fuse((fmt("Same +%d"), fmt("Same +%d")))(5))
		# Two bare values: the value alone, as OLD's strip gives it.
		self.assertEqual("+5", fuse((fmt("+%d"), fmt("+%d")))(5))

	def test_every_locale_has_every_new_apply_text_formatting_one_value(self):
		for locale in locales():
			keys = read_locale(locale)
			for key in APPLY_TEXTS.values():
				with self.subTest(locale=locale, key=key):
					self.assertIn(key, keys)
					text, kind = keys[key]
					self.assertEqual("SA", kind)
					self.assertIn("10", text % 10)
					# OLD's it and pt typed the type into the text ("+%d%% SA").
					self.assertFalse(text.endswith(" SA"))
		self.assertEqual("Strong against Bosses +%d%%", read_locale("en")["TOOLTIP_APPLY_ATTBONUS_BOSS"][0])
		self.assertEqual("Stark gegen Bosse +%d%%", read_locale("de")["TOOLTIP_APPLY_ATTBONUS_BOSS"][0], "OLD's de")
		# OLD has no br: Brazil takes OLD's Portuguese.
		self.assertEqual("Forte contra Bosses +%d%%", read_locale("br")["TOOLTIP_APPLY_ATTBONUS_BOSS"][0])
		self.assertEqual("Resistenza Anti Magic +%d%%", read_locale("it")["TOOLTIP_ANTI_RESIST_MAGIC"][0])



def sage_warrior(game):
	"""nui_character_test's warrior at the cut: OLD's five skill grades
	(skill.SKILL_GRADE_COUNT 4 and player.SKILL_GRADE_SAGE_MASTER, C1's),
	skill 2 a sage, 5 a perfect master at P7."""
	import nui_character_test as character
	character.warrior(game)
	game.modules["skill"].SKILL_GRADE_COUNT = 4
	player = game.modules["player"]
	for grade, name in enumerate(("NORMAL", "MASTER", "GRAND_MASTER", "PERFECT_MASTER", "SAGE_MASTER")):
		setattr(player, "SKILL_GRADE_" + name, grade)
	game.skill_by_index[2] = {"grade": 4, "level": 1}
	game.skill_by_index[5] = {"grade": 3, "level": 7}


class RecordingSkillToolTip(object):
	"""A skill tooltip that records the calls the character window makes."""

	def __init__(self):
		self.calls = []

	def __getattr__(self, name):
		return lambda *args: self.calls.append((name,) + args)


class SageGrade(unittest.TestCase):
	"""Skill level 50 with OLD's sage grade (NOVA-97): the character window's
	three grade columns as OLD lays them out with the sage grade (normal,
	master and grand master, perfect master and sage), the skill tooltip's
	P1 to P10 and the sage grade's name in every locale."""

	ICON = "d:/ymir work/ui/skill/test/%d_%02d.sub"

	def character(self, setup):
		import nui_character_test as character
		world = character.World(False, setup=setup)
		window = world.open("SKILL")
		page = window.GetChild("Skill_Active_Slot")
		counts = []
		setSlotCountNew = page.SetSlotCountNew

		def record(index, grade, level):
			counts.append((index, grade, level))
			setSlotCountNew(index, grade, level)
		page.SetSlotCountNew = record
		with world.game, quiet():
			window.RefreshSkill()
		return character, world, window, counts

	def test_the_grades_take_olds_three_columns(self):
		character, world, window, counts = self.character(sage_warrior)
		cells = character.legacy_skill_cells(window, "Skill_Active_Slot")
		shown = dict((slot, (cell[1], cell[2], cell[4])) for slot, cell in cells.items())
		icon = self.ICON
		self.assertEqual({
			# skill 1, normal level 1: the next columns show the grand and perfect master's icons, closed.
			1: (icon % (1, 1), "1", False), 21: (icon % (1, 3), "", True), 41: (icon % (1, 4), "", True),
			# skill 2, the sage grade: the third column.
			2: (icon % (2, 1), "", True), 22: (icon % (2, 3), "", True), 42: (icon % (2, 4), "", False),
			# skill 3, master 5, and skill 4, grand master 9: the second column.
			3: (icon % (3, 1), "", True), 23: (icon % (3, 2), "m5", False), 43: (icon % (3, 4), "", True),
			4: (icon % (4, 1), "", True), 24: (icon % (4, 3), "g9", False), 44: (icon % (4, 4), "", True),
			# skill 5, perfect master 7: the third column.
			5: (icon % (5, 1), "", True), 25: (icon % (5, 3), "", True), 45: (icon % (5, 4), "p", False),
		}, shown)
		self.assertIn((42, 4, 1), counts, "the sage grade's count")
		self.assertIn((45, 3, 7), counts, "P7")
		self.assertIn((24, 2, 9), counts)
		self.assertFalse([index for index, grade, level in counts if index >= 60], "no fourth column")

	def test_the_tooltip_follows_the_columns(self):
		character, world, window, counts = self.character(sage_warrior)
		window.toolTipSkill = tip = RecordingSkillToolTip()
		with world.game, quiet():
			for slot in (1, 21, 41, 2, 22, 42, 23, 43, 24, 44, 25, 45):
				window.OverInItem(slot)
		self.assertEqual([
			("SetSkillNew", 1, 1, 0, 1), ("SetSkillOnlyName", 1, 1, 1), ("SetSkillOnlyName", 1, 1, 3),
			("SetSkillOnlyName", 2, 2, 0), ("SetSkillOnlyName", 2, 2, 1), ("SetSkillNew", 2, 2, 4, 1),
			("SetSkillNew", 3, 3, 1, 5), ("SetSkillOnlyName", 3, 3, 3),
			("SetSkillNew", 4, 4, 2, 9), ("SetSkillOnlyName", 4, 4, 3),
			("SetSkillOnlyName", 5, 5, 1), ("SetSkillNew", 5, 5, 3, 7),
		], tip.calls)

	def test_without_the_sage_grade_the_columns_stay_todays(self):
		import nui_character_test as character
		character_module, world, window, counts = self.character(character.warrior)
		cells = character_module.legacy_skill_cells(window, "Skill_Active_Slot")
		self.assertEqual((self.ICON % (3, 2), "m5"), cells[23][1:3])
		self.assertEqual((self.ICON % (4, 3), "g9"), cells[44][1:3], "the grand master in the third column")
		self.assertEqual((self.ICON % (5, 3), "p"), cells[45][1:3], "the perfect master too")
		window.toolTipSkill = tip = RecordingSkillToolTip()
		with world.game, quiet():
			for slot in (24, 44, 45, 25, 99):
				window.OverInItem(slot)
		self.assertEqual([("SetSkillOnlyName", 4, 4, 1), ("SetSkillNew", 4, 4, 2, 9), ("SetSkillNew", 5, 5, 3, 1),
		                  ("SetSkillOnlyName", 5, 5, 1), ("SetSkillOnlyName", 19, 0, 4)], tip.calls)

	def test_a_grand_masters_cooldown_survives_a_refresh(self):
		"""The grand master shares the master's column: drawing that column for
		the master grade would move the cooldown onto itself and lose it."""
		character, world, window, counts = self.character(sage_warrior)
		page = window.GetChild("Skill_Active_Slot")
		with world.game, quiet():
			world.game.state.now = 10.0
			window.OnUseSkill(4, 30.0)
			world.game.skills[4]["cool"] = (30.0, 0.0)
			world.game.state.now = 12.0
			window.RefreshSkill()
		self.assertIn(24, page.store.get(1, {}))
		self.assertEqual((10.0, 40.0), character.legacy_skill_cells(window, "Skill_Active_Slot")[24][5])

	def riding_icons(self, setup):
		"""The riding skill's icons on the support page."""
		character, world, window, counts = self.character(setup)
		cells = character.legacy_skill_cells(window, "Skill_ETC_Slot")
		return [cell[1] for cell in cells.values() if cell[1] and "/130_" in cell[1]]

	def test_the_riding_icon_follows_the_horse_with_the_sage_grade(self):
		"""The client clamps the riding skill's icon grade (level - 1) to its
		last grade icon, the fourth with the sage grade, which no riding art
		fills (riding_01 to _03): the icon follows OLD's horses instead."""
		for (grade, level), icon in (((0, 1), 1), ((0, 10), 1), ((0, 11), 2), ((0, 19), 2), ((1, 1), 3), ((1, 10), 3),
		                             ((2, 3), 3), ((3, 1), 3)):
			def setup(game, grade=grade, level=level):
				sage_warrior(game)
				game.skill_by_index[130] = {"grade": grade, "level": level}
			with self.subTest(grade=grade, level=level):
				self.assertEqual([self.ICON % (130, icon)], self.riding_icons(setup))

	def test_without_the_sage_grade_the_riding_icon_stays_todays(self):
		import nui_character_test as character
		for (grade, level), icon in (((0, 1), 1), ((0, 2), 2), ((0, 5), 3), ((1, 5), 3)):
			with self.subTest(grade=grade, level=level):
				self.assertEqual([self.ICON % (130, icon)],
				                 self.riding_icons(lambda game: character.warrior(game, riding=(grade, level))))

	def sage_tooltip(self, grade, level, sage=True):
		import json
		import nui_tooltip_corpus as corpus_tool
		corpus = json.loads(read(os.path.join(REPO, "tools", "fixtures", "tooltip_corpus.json")))
		world = corpus_tool.TipWorld({"items": {}, "skills": {"1": corpus["skills"]["1"]}, "mobs": {}},
		                             recorder=False, sizes="foundation")
		if sage:
			world.game.modules["skill"].SKILL_GRADE_COUNT = 4
			world.game.modules["player"].SKILL_GRADE_SAGE_MASTER = 4
		with quiet():
			world.game.load("uiToolTip", "uitooltip.py")
		texts, error = tooltip_texts(corpus_tool, world, {"context": "SetSkillNew", "vnum": 1, "skill": {
			"vnum": 1, "slot": 1, "grade": grade, "level": level, "efficient": 0.5, "next": 0.6}})
		self.assertIsNone(error)
		return world, texts

	def test_the_perfect_master_counts_p1_to_p10(self):
		world, texts = self.sage_tooltip(3, 7)
		locale = world.game.modules["localeInfo"]
		self.assertIn(locale.TOOLTIP_SKILL_LEVEL % 7, texts)
		self.assertIn(locale.TOOLTIP_NEXT_SKILL_LEVEL_1 % (8, 10), texts, "OLD's ten perfect master levels")
		world, texts = self.sage_tooltip(3, 10)
		self.assertIn(locale.TOOLTIP_SKILL_LEVEL_MASTER % 10, texts)
		self.assertFalse([text for text in texts if text.startswith(locale.TOOLTIP_NEXT_SKILL_LEVEL_1.split("%")[0])])

	def test_the_sage_grade_has_its_name_and_no_level(self):
		world, texts = self.sage_tooltip(4, 1)
		locale = world.game.modules["localeInfo"]
		self.assertIn("Three-Way Cut Super Perfect Master", texts)
		self.assertEqual(locale.SKILL_GRADE_NAME_SAGE_MASTER, world.m("uiToolTip").SkillToolTip.SKILL_GRADE_NAME[4])
		self.assertFalse([text for text in texts if text.startswith(locale.TOOLTIP_SKILL_LEVEL.split("%")[0])])
		world, texts = self.sage_tooltip(3, 1, sage=False)
		self.assertNotIn(4, world.m("uiToolTip").SkillToolTip.SKILL_GRADE_NAME, "no sage grade before the cut")

	def test_every_locale_names_the_sage_grade(self):
		for locale in locales():
			with self.subTest(locale=locale):
				text, kind = read_locale(locale)["SKILL_GRADE_NAME_SAGE_MASTER"]
				self.assertEqual("", kind)
				self.assertIn("Skill", text % "Skill")
		self.assertEqual("%s Super Perfect Master", read_locale("en")["SKILL_GRADE_NAME_SAGE_MASTER"][0], "OLD's")
		self.assertEqual("%s Super Perfekcyjny Mistrz", read_locale("pl")["SKILL_GRADE_NAME_SAGE_MASTER"][0], "OLD's")
		self.assertEqual("%s Super mestre perfeito", read_locale("br")["SKILL_GRADE_NAME_SAGE_MASTER"][0], "OLD's pt")



class GuildNames(unittest.TestCase):
	"""Guild names of 24 characters (NOVA-97): the guild name dialog takes
	the client's guild.GUILD_NAME_MAX_LEN, where the shared input dialog's
	uiscript stops at 12 (uiscript/inputdialog.py; OLD's at 21, its server at
	24)."""

	class Dialog(object):
		def __init__(self):
			self.calls = []

		def __getattr__(self, name):
			return lambda *args: self.calls.append((name,) + args)

	def ask(self, guild_name_max_len):
		source = support.source_of("game.py", ("AskGuildName",), inside="GameWindow")
		body = "\n".join("\t" + line if line else line for line in source.split("\n"))
		dialogs = []

		def make():
			dialogs.append(self.Dialog())
			return dialogs[-1]
		namespace = {
			"uiCommon": types.SimpleNamespace(InputDialog=make),
			"localeInfo": types.SimpleNamespace(GUILD_NAME="Guild name"),
			"guild": types.SimpleNamespace(GUILD_NAME_MAX_LEN=guild_name_max_len),
			"ui": types.SimpleNamespace(__mem_func__=lambda method: method),
		}
		exec(compile("class GameWindow(object):\n%s\n\tConfirmGuildName = CancelGuildName = None\n" % body,
		             "game.py", "exec"), namespace)
		window = namespace["GameWindow"]()
		window.AskGuildName()
		self.assertIs(dialogs[0], window.guildNameBoard)
		return dialogs[0].calls

	def test_the_guild_name_dialog_takes_the_guild_name_length(self):
		calls = self.ask(24)
		self.assertIn(("SetMaxLength", 24), calls)
		self.assertLess(calls.index(("SetMaxLength", 24)), calls.index(("Open",)), "before it opens")
		self.assertEqual([("SetMaxLength", 12)], [call for call in self.ask(12) if call[0] == "SetMaxLength"])

	def test_the_shared_input_dialog_keeps_its_twelve(self):
		world = LegacyWorld()
		with world:
			window = read_uiscript(os.path.join(UISCRIPT, "inputdialog.py"))["window"]
		self.assertEqual(12, child(window, "InputValue")["input_limit"])

	def test_the_war_declaration_takes_the_guild_name_length(self):
		"""The legacy declare-war dialog (the guild window's declare button
		with NovaUI's guild-war-dialogs off) is where the enemy guild's name
		is typed: its uiscript stopped at 12, so no war could be declared on
		a guild named past 12 characters (OLD's dialog takes 32)."""
		import nui_w4_world as w4
		for length in (24, 30):
			with self.subTest(length=length):
				world = w4.World(False, social=True)
				world.game.modules["guild"].GUILD_NAME_MAX_LEN = length
				dialog = world.make("guild-war-dialogs", "uiGuild", "DeclareGuildWarDialog",
				                    "nui_guild_war_declare.DeclareGuildWarDialog")
				self.assertEqual("DeclareGuildWarDialog", type(dialog).__name__)
				self.assertEqual(length, dialog.inputValue.max)
				with world:
					window = read_uiscript(os.path.join(UISCRIPT, "declareguildwardialog.py"))["window"]
				self.assertEqual(length, child(window, "InputValue")["input_limit"])



class FiveCharacters(unittest.TestCase):
	"""Five characters per account (NOVA-97): the select window's fifth place
	on the turntable, its hotkey and its instance (introselect.py, which
	nui_select subclasses), over nui_phase_test's stand-ins."""

	DIK_5 = 6

	def world(self):
		import nui_phase_test as phase
		slots = phase.account({"ID": 101, "NAME": "Kalinka", "RACE": 1}, None, None,
		                      {"ID": 104, "NAME": "Borak"}, {"ID": 105, "NAME": "Fifth", "RACE": 2, "LEVEL": 150})
		world = phase.World(slots=slots, stream_slot=0, nui_on=False)
		with world, quiet():
			window = world.legacy["introSelect"].SelectCharacterWindow(world.stream)
			window.Open()
		return world, window

	def test_five_places_72_degrees_apart_from_the_selected_one(self):
		world, window = self.world()
		self.assertEqual(5, window.SLOT_COUNT)
		self.assertEqual(5, len(window.SLOT_ROTATION))
		self.assertEqual(135.0, window.SLOT_ROTATION[0], "the selected character keeps the turntable's front")
		for first, second in zip(window.SLOT_ROTATION, window.SLOT_ROTATION[1:] + window.SLOT_ROTATION[:1]):
			self.assertEqual(72.0, (second - first) % 360.0)

	def test_the_fifth_character_is_made_and_selected_by_its_key(self):
		world, window = self.world()
		self.assertEqual({0: 1, 3: 0, 4: 2}, world.chr_state.instances, "Refresh makes every slot's character")
		with world, quiet():
			window.OnKeyDown(self.DIK_5)
		self.assertEqual(4, window.GetSlotIndex())
		self.assertEqual(4, world.chr_state.selected)
		self.assertEqual(135.0, window.destRotation[4], "the selected one turns to the front")
		with world, quiet():
			window.OnKeyDown(self.DIK_5 - 1)
		self.assertEqual(3, window.GetSlotIndex(), "key 4 still selects the fourth")
		with world, quiet():
			window.IncreaseSlotIndex()
			window.IncreaseSlotIndex()
		self.assertEqual(0, window.GetSlotIndex(), "right past the fifth comes back to the first")

	def test_close_deletes_all_five_instances(self):
		world, window = self.world()
		with world, quiet():
			window.Close()
		self.assertEqual({}, world.chr_state.instances)



class SafeboxPages(unittest.TestCase):
	"""Five safebox pages (NOVA-97; Q4: decided 2026-10-25): the legacy
	safebox caps its pages at the client's safebox.SAFEBOX_PAGE_COUNT_MAX
	(OLD uiSafebox.py:389 caps at 5), and more page tabs than three take
	OLD's small tabs so they fit the board."""

	MIDDLE = "d:/ymir work/ui/game/windows/tab_button_middle_%02d.sub"
	SMALL = "d:/ymir work/ui/game/windows/tab_button_small_%02d.sub"

	def tabs(self, size, page_count_max=5):
		import nui_w4_world as w4
		world = w4.World(False)
		world.game.modules["safebox"].SAFEBOX_PAGE_COUNT_MAX = page_count_max
		window = world.make("safebox", "uiSafebox", "SafeboxWindow", "nui_safebox.SafeboxWindow")
		with world.game, quiet():
			window.SetTableSize(size)
		return window, [(button.text, button.visuals["up"], button.visuals["down"],
		                 [call[1:] for call in button.calls if call[0] == "SetPosition"][-1])
		                for button in window.pageButtonList]

	def test_five_pages_take_five_small_tabs_that_fit_the_board(self):
		window, tabs = self.tabs(5 * 9)
		self.assertEqual([("I", self.SMALL % 1, self.SMALL % 3, (-64, 85)), ("II", self.SMALL % 1, self.SMALL % 3, (-32, 85)),
		                  ("III", self.SMALL % 1, self.SMALL % 3, (0, 85)), ("IV", self.SMALL % 1, self.SMALL % 3, (32, 85)),
		                  ("V", self.SMALL % 1, self.SMALL % 3, (64, 85))], tabs)
		self.assertLessEqual(32 * 5, window.BOX_WIDTH)

	def test_three_pages_keep_the_middle_tabs(self):
		window, tabs = self.tabs(3 * 9)
		self.assertEqual([("I", self.MIDDLE % 1, self.MIDDLE % 3, (-52, 85)), ("II", self.MIDDLE % 1, self.MIDDLE % 3, (0, 85)),
		                  ("III", self.MIDDLE % 1, self.MIDDLE % 3, (52, 85))], tabs)

	def test_the_pages_stop_at_the_clients_maximum(self):
		self.assertEqual(5, len(self.tabs(6 * 9)[1]), "OLD's six premium pages overran its 225 cells (Q4)")
		self.assertEqual(4, len(self.tabs(6 * 9, page_count_max=4)[1]), "the client's constant, not a literal")
		self.assertEqual(1, len(self.tabs(3)[1]), "the loader's SetTableSize(3) before the server's size")


def run_localeinfo(locale):
	"""The namespace of assets/root/localeinfo.py run whole, as the client
	imports it: locale_game.txt through pack_open, then _RebuildDerivedData.
	`paths["locale"]` is what app.GetLocalePath answers, so a test can switch
	the language and call LoadLocaleData as app.ReloadLocale does."""
	paths = {"locale": os.path.join(LOCALES, locale)}
	errors = []
	app = types.ModuleType("app")
	app.GetLocalePath = lambda: paths["locale"]
	app.GetLocalePathCommon = lambda: os.path.join(LOCALES, "common")
	app.LoadLocaleData = lambda path: True

	def abort():
		raise AssertionError("localeinfo.py called app.Abort: %r" % errors)
	app.Abort = abort
	dbg = types.ModuleType("dbg")
	dbg.LogBox = dbg.TraceError = lambda *args: errors.append(args)
	# pack_open hands back the packed file's text; localeinfo.py never closes it.
	namespace = {"__name__": "localeInfo", "pack_open": lambda name, mode="r": io.StringIO(read(name))}
	saved = dict((name, sys.modules.get(name)) for name in ("app", "dbg"))
	sys.modules.update(app=app, dbg=dbg)
	try:
		exec(compile(read(os.path.join(ROOT, "localeinfo.py")), "localeinfo.py", "exec"), namespace)
	finally:
		for name, module in saved.items():
			if module is None:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = module
	return namespace, paths, errors


class QuickSlotRefusal(unittest.TestCase):
	"""The quick slot refusal (NOVA-97): the client refuses a quick slot for
	an item cell outside the inventory pages (0-224), such as a belt or
	equipment cell, since the slot's one-byte position can't hold it as the
	server reads it (PythonPlayer.cpp CanQuickSlotAddress), and posts
	BINARY_AppendNotifyMessage("QUICKSLOT_REGISTER_DISABLE_ITEM") to the game
	window. game.py shows only the keys localeInfo.NOTIFY_MESSAGE has, so
	without the entry the refusal was silent."""

	# Every key the client posts to BINARY_AppendNotifyMessage
	# (PythonNetworkStreamPhaseGameItem.cpp and PythonPlayer.cpp), with the
	# locale_game.txt entry it shows.
	POSTED = {
		"CANNOT_EQUIP_SHOP": "CANNOT_EQUIP_IN_SHOP",
		"CANNOT_EQUIP_EXCHANGE": "CANNOT_EQUIP_IN_EXCHANGE",
		"QUICKSLOT_REGISTER_DISABLE_ITEM": "QUICKSLOT_REGISTER_DISABLE_ITEM",
	}

	def notify(self, locale_namespace, key):
		"""The chat lines game.py's GameWindow.BINARY_AppendNotifyMessage
		appends for `key`."""
		source = support.source_of("game.py", ("BINARY_AppendNotifyMessage",), inside="GameWindow")
		body = "\n".join("\t" + line if line else line for line in source.split("\n"))
		locale_info = types.ModuleType("localeInfo")
		locale_info.__dict__.update(locale_namespace)
		lines = []
		namespace = {
			"localeInfo": locale_info,
			"chat": types.SimpleNamespace(CHAT_TYPE_INFO=1, AppendChat=lambda kind, text: lines.append((kind, text))),
		}
		exec(compile("class GameWindow(object):\n%s\n" % body, "game.py", "exec"), namespace)
		namespace["GameWindow"]().BINARY_AppendNotifyMessage(key)
		return lines

	def test_every_locale_shows_its_own_refusal_line(self):
		for locale in locales():
			with self.subTest(locale=locale):
				namespace, _, errors = run_localeinfo(locale)
				self.assertEqual([], errors)
				text = read_locale(locale)["QUICKSLOT_REGISTER_DISABLE_ITEM"][0]
				self.assertTrue(text.strip())
				self.assertEqual([(1, text)], self.notify(namespace, "QUICKSLOT_REGISTER_DISABLE_ITEM"))

	def test_every_key_the_client_posts_shows_a_line(self):
		namespace, _, _ = run_localeinfo("en")
		for key, entry in self.POSTED.items():
			with self.subTest(key=key):
				self.assertEqual([(1, read_locale("en")[entry][0])], self.notify(namespace, key))
		self.assertEqual([], self.notify(namespace, "NO_SUCH_NOTIFY"), "legacy's guard for a key it has no line for")

	def test_a_language_change_keeps_the_line(self):
		"""app.ReloadLocale calls localeInfo.LoadLocaleData, which rebuilds
		NOTIFY_MESSAGE from the new locale's strings."""
		namespace, paths, errors = run_localeinfo("en")
		paths["locale"] = os.path.join(LOCALES, "de")
		self.assertTrue(namespace["LoadLocaleData"](), errors)
		self.assertEqual([(1, read_locale("de")["QUICKSLOT_REGISTER_DISABLE_ITEM"][0])],
		                 self.notify(namespace, "QUICKSLOT_REGISTER_DISABLE_ITEM"))


class FourthSocket(unittest.TestCase):
	"""OLD's fourth socket in the legacy inventory (NOVA-97; RUN-B-D1 of the
	stage B live run, where dropping 50501 on a blade only moved it): 50500
	opens an armour's fourth socket, 50501 a weapon's. Dropped on the item,
	it asks first (ADD_4TH_STONE_ADD_QUESTION) and sends the use-to-item
	packet on Yes, or says in the chat why it can't; picked up, it lights the
	items it can open (OLD uiInventory.py:1909, 1935, 2044-2070, 2202,
	2255-2257). The client half (item.IsSocketScroll, player.CanAdd4thStone,
	GetSocketCount and GetItemTypeBySlot, stageB/live/P2-api.md) is stood in
	by its rules: CanAdd4thStone wants a weapon or armour whose socket 3 is
	still 0 and the enhancer made for it (value0 1 armour, 2 weapon), and
	leaves the target's data selected; it counts no stones, the server
	does."""

	USE_4TH_SOCKET = 34
	ARMOUR_ENHANCER, WEAPON_ENHANCER, BLADE, ARMOUR, POTION = 50500, 50501, 300, 12010, 27001
	ODD_ENHANCER = 50599  # this test's: an enhancer whose value0 names neither kind
	SCROLL, WEAPON_CELL, ARMOUR_CELL, POTION_CELL = 0, 1, 2, 3
	STONES = [28030, 28031, 28032, 0]
	KEYS = ("ADD_4TH_STONE_ALREADY_ADDED", "ADD_4TH_STONE_NOT_ENOUGH_STONES", "ADD_4TH_STONE_ONLY_ARMOR",
	        "ADD_4TH_STONE_ONLY_WEAPON", "ADD_4TH_STONE_NOT_POSSIBLE", "ADD_4TH_STONE_ADD_QUESTION")

	def setUp(self):
		world = self.world = LegacyWorld()
		game = self.game = world.game
		item, player = game.modules["item"], game.modules["player"]
		item.USE_4TH_SOCKET = self.USE_4TH_SOCKET
		use, weapon, armour = item.ITEM_TYPE_USE, item.ITEM_TYPE_WEAPON, item.ITEM_TYPE_ARMOR
		# vnum: (type, sub type, value0)
		self.kinds = {self.ARMOUR_ENHANCER: (use, self.USE_4TH_SOCKET, 1), self.WEAPON_ENHANCER: (use, self.USE_4TH_SOCKET, 2),
		              self.ODD_ENHANCER: (use, self.USE_4TH_SOCKET, 0),
		              self.BLADE: (weapon, 0, 0), self.ARMOUR: (armour, 0, 0), self.POTION: (use, 0, 0)}
		kind = lambda vnum: self.kinds.get(vnum, (0, 0, 0))
		at = lambda cell: game._item_at(cell)
		sockets = lambda cell: (at(cell)["sockets"] + [0, 0, 0, 0])[:4]

		def can_add(scroll, *target):
			cell = target[-1]
			item.selected[0] = at(cell)["vnum"]
			scroll_type, sub_type, value0 = kind(scroll)
			target_type = kind(at(cell)["vnum"])[0]
			if (scroll_type, sub_type) != (use, self.USE_4TH_SOCKET) or target_type not in (weapon, armour):
				return player.DETACH_METIN_CANT
			if sockets(cell)[3] != 0:
				return player.DETACH_METIN_CANT
			return player.DETACH_METIN_OK if (value0, target_type) in ((1, armour), (2, weapon)) else player.DETACH_METIN_CANT

		support.define(item, "IsSocketScroll", lambda vnum: kind(vnum)[:2] == (use, self.USE_4TH_SOCKET))
		support.define(item, "GetItemSubType", lambda: kind(item.selected[0])[1])
		support.define(item, "GetValue", lambda index: kind(item.selected[0])[2] if index == 0 else 0)
		support.define(player, "CanAdd4thStone", can_add)
		support.define(player, "GetSocketCount", lambda cell, *window: len([s for s in sockets(cell) if s]))
		support.define(player, "GetItemTypeBySlot", lambda *cell: kind(at(cell[-1])["vnum"])[0])
		support.define(player, "GetItemMetinSocket", lambda *args: sockets(args[-2])[args[-1]])
		game.give(self.SCROLL, self.WEAPON_ENHANCER, 3)
		game.give(self.WEAPON_CELL, self.BLADE, 1, self.STONES)
		game.give(self.ARMOUR_CELL, self.ARMOUR, 1, self.STONES)
		game.give(self.POTION_CELL, self.POTION, 5)
		self.window = make_inventory(world)
		del game.log[:]

	def drop(self, scroll, target):
		"""The enhancer `scroll` (in cell SCROLL) dropped on cell `target`:
		(the dialogs it opened, the chat lines, the packets)."""
		self.game.give(self.SCROLL, scroll, 3)
		opened = len(self.game.dialogs)
		with self.world, quiet():
			self.window._InventoryWindow__DropSrcItemToDestItemInInventory(scroll, self.SCROLL, target)
		chat = [args for name, args in self.game.calls("chat.AppendChat")]
		packets = self.game.calls("net.SendItem")
		return self.game.dialogs[opened:], chat, packets

	def text(self, key):
		return read_locale("en")[key][0]

	def test_dropped_on_its_kind_with_three_stones_it_asks_and_sends_the_use_on_yes(self):
		for scroll, target in ((self.WEAPON_ENHANCER, self.WEAPON_CELL), (self.ARMOUR_ENHANCER, self.ARMOUR_CELL)):
			with self.subTest(scroll=scroll):
				del self.game.log[:]
				dialogs, chat, packets = self.drop(scroll, target)
				self.assertEqual([], chat)
				self.assertEqual([], packets, "nothing goes out before the answer")
				self.assertEqual(1, len(dialogs))
				dialog = dialogs[0]
				self.assertEqual("uiCommon.QuestionDialog", dialog._name)
				self.assertEqual([self.text("ADD_4TH_STONE_ADD_QUESTION")], dialog.texts)
				self.assertTrue(dialog.is_open)
				with self.world, quiet():
					dialog.accept_event()
				self.assertEqual([("net.SendItemUseToItemPacket", (self.SCROLL, target))], self.game.calls("net.SendItem"))
				self.assertFalse(dialog.is_open)
				self.assertIsNone(self.window.questionDialog)

	def test_no_closes_the_question_and_sends_nothing(self):
		dialogs, _, _ = self.drop(self.WEAPON_ENHANCER, self.WEAPON_CELL)
		with self.world, quiet():
			dialogs[0].cancel_event()
		self.assertFalse(dialogs[0].is_open)
		self.assertEqual([], self.game.calls("net.SendItem"))

	def test_a_refusal_names_its_reason_and_sends_nothing(self):
		game = self.game
		chat_type = game.modules["chat"].CHAT_TYPE_INFO
		cases = [
			# the armour's enhancer on a weapon, and the reverse
			("ADD_4TH_STONE_ONLY_ARMOR", self.ARMOUR_ENHANCER, self.WEAPON_CELL, self.STONES),
			("ADD_4TH_STONE_ONLY_WEAPON", self.WEAPON_ENHANCER, self.ARMOUR_CELL, self.STONES),
			# OLD asks for the stones first when the answer is no anyway
			("ADD_4TH_STONE_NOT_ENOUGH_STONES", self.ARMOUR_ENHANCER, self.WEAPON_CELL, [28030, 28031, 0, 0]),
			# open already (the server sets 1), or holding its stone
			("ADD_4TH_STONE_ALREADY_ADDED", self.WEAPON_ENHANCER, self.WEAPON_CELL, [28030, 28031, 28032, 1]),
			("ADD_4TH_STONE_ALREADY_ADDED", self.WEAPON_ENHANCER, self.WEAPON_CELL, [28030, 28031, 28032, 28012]),
			# neither a weapon nor an armour: OLD asks for the stones first
			("ADD_4TH_STONE_NOT_ENOUGH_STONES", self.WEAPON_ENHANCER, self.POTION_CELL, [0, 0, 0, 0]),
			# an enhancer made for neither (value0 0)
			("ADD_4TH_STONE_NOT_POSSIBLE", self.ODD_ENHANCER, self.WEAPON_CELL, self.STONES),
		]
		for key, scroll, target, sockets in cases:
			with self.subTest(key=key, sockets=sockets):
				target_vnum = game._item_at(target)["vnum"]
				game.give(target, target_vnum, 1, sockets)
				del game.log[:]
				dialogs, chat, packets = self.drop(scroll, target)
				self.assertEqual([(chat_type, self.text(key))], chat)
				self.assertEqual([], dialogs)
				self.assertEqual([], packets)

	def test_fewer_stones_are_the_servers_to_refuse(self):
		"""CanAdd4thStone counts no stones (OLD's either): the question opens
		and the server answers MUST_HAVE_3_ATTACHED_STONES, keeping the
		enhancer."""
		self.game.give(self.WEAPON_CELL, self.BLADE, 1, [28030, 0, 0, 0])
		dialogs, chat, _ = self.drop(self.WEAPON_ENHANCER, self.WEAPON_CELL)
		self.assertEqual([], chat)
		self.assertEqual([self.text("ADD_4TH_STONE_ADD_QUESTION")], dialogs[0].texts)

	def test_picked_up_it_lights_only_the_items_it_can_open(self):
		window = self.window
		self.assertTrue(window._InventoryWindow__IsUsableItemToItem(self.WEAPON_ENHANCER, self.SCROLL))
		can_use = window._InventoryWindow__CanUseSrcItemToDstItem
		with self.world:
			self.assertTrue(can_use(self.WEAPON_ENHANCER, self.SCROLL, self.WEAPON_CELL))
			self.assertFalse(can_use(self.WEAPON_ENHANCER, self.SCROLL, self.ARMOUR_CELL))
			self.assertFalse(can_use(self.WEAPON_ENHANCER, self.SCROLL, self.POTION_CELL))
			self.game.give(self.WEAPON_CELL, self.BLADE, 1, [28030, 28031, 28032, 28012])
			self.assertFalse(can_use(self.WEAPON_ENHANCER, self.SCROLL, self.WEAPON_CELL), "open already")
			self.assertFalse(can_use(self.WEAPON_ENHANCER, self.SCROLL, self.SCROLL), "itself")

	def test_another_use_item_still_moves(self):
		_, chat, packets = self.drop(self.POTION, self.WEAPON_CELL)
		self.assertEqual([("net.SendItemMovePacket", (self.SCROLL, self.WEAPON_CELL, 0))], packets)

	def test_every_locale_has_the_strings_olds_text_where_old_has_them(self):
		"""OLD's locale_game.txt where OLD's locale has the key (br from OLD's
		pt; a later line wins, as in OLD's loader: de's second set), English
		otherwise (ae, cz, hu and nl lack them in OLD)."""
		old_root = os.path.join(REPO, "..", "..", "..", "old", "client_pack", "source", "locale")
		for locale in locales():
			with self.subTest(locale=locale):
				keys = read_locale(locale)
				for key in self.KEYS:
					self.assertTrue(keys[key][0].strip(), key)
					self.assertEqual("", keys[key][1], key)
				if not os.path.isdir(old_root):
					continue
				source = "pt" if locale == "br" else locale
				old = {}
				path = os.path.join(old_root, source, "locale_game.txt")
				if os.path.isfile(path):
					for line in read(path).split("\n"):
						tokens = line.rstrip("\r").split("\t")
						if tokens[0] in self.KEYS:
							old[tokens[0]] = tokens[1].strip()
				for key in self.KEYS:
					self.assertEqual(old.get(key, read_locale("en")[key][0]), keys[key][0], key)


# The cut's skill constants (nova-client-src src/UserInterface/PythonSkill.h:145-147,
# 8fbd777): OLD's sage grade is a fifth effect grade, its motions 25 indices above
# the perfect master's. chr.MOTION_SKILL is CRaceMotionData::NAME_SKILL
# (src/GameLib/RaceMotionData.h:98); every other motion name lies below it.
CUT_SKILL = {"SKILL_EFFECT_COUNT": 5, "SKILL_GRADEGAP": 25}
MOTION_SKILL = 50


class Numbered(AnyCall):
	"""A C++ module stand-in whose every upper-case name is a constant of its
	own, numbered from 1 in the order the code asks (the motion modes apart),
	and every other name a function that does nothing."""

	def __init__(self, name):
		AnyCall.__init__(self, name)
		self._numbers = (itertools.count(1), itertools.count(1))

	def __getattr__(self, name):
		if name.isupper() and not name.startswith("__"):
			value = next(self._numbers[name.startswith("MOTION_MODE_")])
			setattr(self, name, value)
			return value
		return AnyCall.__getattr__(self, name)


class RaceMotions(object):
	"""What assets/root/playersettingmodule.py's four race loaders
	(LoadGameData "WARRIOR", "ASSASSIN", "SURA" and "SHAMAN") register, the
	module run whole over stand-ins of the C++ modules with the cut's skill
	constants, for the length of `test`:
	- .motions[(race, mode, index)]: [file, weight] in the order chrmgr got
	  them, the file as chrmgr names it (SetPathName's folder and the name),
	  the weight as RegisterCacheMotionData or SetMotionRandomWeight set it;
	- .folders[race]: the race's folder ("d:/ymir work/pc2/shaman/");
	- .chr: the chr stand-in, with the constants the module used."""

	RACE_LOADERS = ("WARRIOR", "ASSASSIN", "SURA", "SHAMAN")
	C_MODULES = ("chr", "chrmgr", "skill", "net", "item", "player", "effect", "constInfo", "localeInfo", "emotion", "app")

	def __init__(self, test, skill_constants=CUT_SKILL):
		from unittest import mock
		patcher = mock.patch.dict(sys.modules)
		patcher.start()
		test.addCleanup(patcher.stop)
		modules = dict((name, Numbered(name)) for name in self.C_MODULES)
		modules["chr"].MOTION_SKILL = MOTION_SKILL
		for name, value in skill_constants.items():
			setattr(modules["skill"], name, value)
		self.motions = collections.OrderedDict()
		self.folders = {}
		state = {"race": None, "folder": ""}
		chrmgr = modules["chrmgr"]

		def select(race):
			state["race"] = race

		def folder(path):
			state["folder"] = path
			if path.endswith("/skill/"):
				self.folders[state["race"]] = path[:-len("skill/")]

		def register(mode, index, name, weight=0):
			self.motions.setdefault((state["race"], mode, index), []).append([state["folder"] + name, weight])

		def set_weight(mode, index, sub, weight):
			self.motions[(state["race"], mode, index)][sub][1] = weight
		chrmgr.SelectRace, chrmgr.SetPathName = select, folder
		chrmgr.RegisterCacheMotionData = chrmgr.RegisterMotionData = register
		chrmgr.SetMotionRandomWeight = set_weight
		sys.modules.update(modules)
		self.chr = modules["chr"]
		namespace = {"__name__": "playerSettingModule"}
		path = os.path.join(ROOT, "playersettingmodule.py")
		exec(compile(read(path), path, "exec"), namespace)
		with quiet():
			for name in self.RACE_LOADERS:
				namespace["LoadGameData"](name)
		below = dict((name, value) for name, value in vars(self.chr).items()
		             if name.startswith("MOTION_") and not name.startswith("MOTION_MODE_") and name != "MOTION_SKILL")
		test.assertTrue(below and max(below.values()) < MOTION_SKILL, below)

	def general(self, race, index):
		"""The files registered at `index` of `race`'s general motion mode."""
		return [name for name, _ in self.motions.get((race, self.chr.MOTION_MODE_GENERAL, index), ())]


def skilldesc_rows(locale):
	"""The tab-separated fields of a locale's skilldesc.txt, a row per line
	with a skill number (CPythonSkill::RegisterSkillDesc keeps the empty
	fields: DESC_TOKEN_TYPE_* index them)."""
	rows = []
	for line in read(os.path.join(LOCALES, locale, "skilldesc.txt")).split("\n"):
		fields = line.split("\t")
		if fields[0].strip().isdigit():
			rows.append(fields)
	return rows


SKILLDESC_JOB, SKILLDESC_MOTION_INDEX, SKILLDESC_MOTION_GRADES = 1, 13, 14


class SkillMotions(unittest.TestCase):
	"""The skill motions playersettingmodule.py registers for the four races
	at the cut's five skill grades (NOVA-97; the sage grade of OLD,
	L1-D1 of the stage B live run)."""

	# The guild skills' motions (playersettingmodule.py GUILD_SKILL_*), by
	# the skill that casts each.
	GUILD_MOTIONS = {152: "guild_yongsinuipi.msa", 153: "guild_yongsinuichukbok.msa", 154: "guild_seonghwigap.msa",
	                 155: "guild_gasokhwa.msa", 156: "guild_yongsinuibunno.msa", 157: "guild_jumunsul.msa"}

	def test_an_index_with_several_motions_shares_them_out(self):
		"""CActorInstance::GetRandomMotionKey shares an index's motions out by
		their weights; with none (RegisterCacheMotionData's default 0) the
		first one registered always plays. The sage grade's slots 1-6 are
		MOTION_SKILL+101..106, where NEW kept the guild skills' motions, so
		once the sage motions load, Blood of Dragon God would cast a warrior's
		Three-Way Cut. OLD moved the guild skills to 107-112
		(playerSettingModule.py:62-67)."""
		race = RaceMotions(self)
		unshared = dict((key, motions) for key, motions in race.motions.items()
		                if len(motions) > 1 and sum(weight for _, weight in motions) != 100)
		self.assertEqual({}, unshared)

	def test_every_locales_guild_skills_cast_the_guild_motions(self):
		"""skilldesc.txt's motion index (CPythonSkill: NAME_SKILL plus it) of
		each guild skill is where every race registers that skill's motion,
		alone."""
		race = RaceMotions(self)
		for locale in locales():
			cast = dict((int(row[0]), row[SKILLDESC_MOTION_INDEX]) for row in skilldesc_rows(locale)
			            if row[SKILLDESC_JOB] == "GUILD" and int(row[0]) in self.GUILD_MOTIONS)
			self.assertEqual(sorted(self.GUILD_MOTIONS), sorted(cast), locale)
			for skill, index in sorted(cast.items()):
				for number, folder in sorted(race.folders.items()):
					with self.subTest(locale=locale, skill=skill, race=number):
						self.assertEqual([folder + "skill/" + self.GUILD_MOTIONS[skill]],
						                 race.general(number, MOTION_SKILL + int(index)))

	def test_every_motion_the_race_loaders_register_is_in_the_content(self):
		"""CRaceData::RegisterMotionData logs an error and registers nothing
		for a file the client can't open. The cut's sage grade asked for 64
		<skill>_5.msa that NEW's content lacked (L1-D1: 64 syserr lines at
		every login, 32 per race model). Until the art import (H5) brings
		OLD's, each is NEW's own effective <skill>_4.msa."""
		import old_content
		files = old_content.published_files()
		race = RaceMotions(self)
		registered = set(name for motions in race.motions.values() for name, _ in motions)
		self.assertGreater(len(registered), 900)
		self.assertEqual([], sorted(name for name in registered if name.lower() not in files))

	def test_every_race_registers_each_skill_at_every_grade(self):
		"""CPythonSkill gives grade g of a skill the motion index
		base + g * SKILL_GRADEGAP (PythonSkill.cpp RegisterSkillDesc), so each
		skill slot a race loads at grade 0 needs one motion at every grade up
		to SKILL_EFFECT_COUNT. OLD's shaman loop takes the sage grade too
		(SHAMY_LIST (1, 2, 3, 4) with ENABLE_SKILLS_LEVEL_OVER_P,
		playerSettingModule.py:1926-1929); NEW's stopped at (1, 2, 3)."""
		race = RaceMotions(self)
		gap, grades = CUT_SKILL["SKILL_GRADEGAP"], CUT_SKILL["SKILL_EFFECT_COUNT"]
		self.assertEqual(8, len(race.folders))
		for number, folder in sorted(race.folders.items()):
			slots = [index - MOTION_SKILL for index in range(MOTION_SKILL + 1, MOTION_SKILL + gap)
			         if race.general(number, index)]
			self.assertGreaterEqual(len(slots), 10, folder)
			for grade in range(grades):
				with self.subTest(race=folder, grade=grade):
					self.assertEqual([], [slot for slot in slots
					                      if len(race.general(number, MOTION_SKILL + grade * gap + slot)) != 1])

	def test_every_grade_of_a_skill_casts_its_own_motion(self):
		"""CPythonSkill::RegisterSkillDesc gives grades 0 to n-1 of a skill
		base + g * SKILL_GRADEGAP, n being skilldesc.txt's motion grade count,
		and every grade from n on the base motion (grade 0's). With NEW's 4,
		the sage grade cast the normal grade's motion, never its _5; OLD's
		skilldesc.txt says 5 for each of these skills."""
		race = RaceMotions(self)
		gap, grades = CUT_SKILL["SKILL_GRADEGAP"], CUT_SKILL["SKILL_EFFECT_COUNT"]
		suffix = [""] + ["_%d" % (grade + 1) for grade in range(1, grades)]
		for locale in locales():
			rows = [row for row in skilldesc_rows(locale) if row[SKILLDESC_JOB] in ("WARRIOR", "ASSASSIN", "SURA", "SHAMAN")
			        and row[SKILLDESC_MOTION_GRADES].strip() not in ("", "1")]
			self.assertEqual(44, len(rows), locale)
			for row in rows:
				count, base = int(row[SKILLDESC_MOTION_GRADES]), int(row[SKILLDESC_MOTION_INDEX])
				for number, folder in sorted(race.folders.items()):
					if "/%s/" % row[SKILLDESC_JOB].lower() not in folder:
						continue
					cast = [base + grade * gap if grade < count else base for grade in range(grades)]
					files = [race.general(number, MOTION_SKILL + index) for index in cast]
					with self.subTest(locale=locale, skill=row[0], race=folder):
						self.assertTrue(all(len(names) == 1 for names in files), files)
						self.assertEqual(suffix, [re.sub(r"^[a-z]+(?:_target)?(_\d)?\.msa$", r"\1", names[0].rsplit("/", 1)[1])
						                          for names in files])


class GuildSkillDesc(unittest.TestCase):
	"""skilldesc.txt's guild skills, 152-157 (NOVA-97; P2-D4 of the stage B
	live run): pl's line 152 (Krew Boga Smoków, Blood of Dragon God) carried
	horse skill 140's columns, so the client read it as a bow attack on
	horseback (ATTACK_SKILL|FAN_RANGE|NEED_TARGET|HORSE_SKILL|
	WEAPON_LIMITATION, BOW, five targets) with the wildattack icon."""

	# The columns CPythonSkill::RegisterSkillDesc reads as data, not text
	# (DESC_TOKEN_TYPE_*, src/UserInterface/PythonSkill.h:54-70). The affect
	# formulas after them drift between locales on their own (P2-D5) and are
	# left out; the motion index is SkillMotions' too.
	DATA_COLUMNS = ((1, "job"), (10, "attribute"), (11, "weapon"), (12, "icon"), (13, "motion index"),
	                (14, "motion grades"), (15, "target count"), (16, "motion loop count"))
	GUILD_SKILLS = range(152, 158)

	def data(self, rows):
		by_skill = dict((int(row[0]), row) for row in rows)
		return dict((skill, dict((name, by_skill[skill][column]) for column, name in self.DATA_COLUMNS))
		            for skill in self.GUILD_SKILLS)

	def test_every_locales_guild_skills_have_ens_data_columns(self):
		"""And OLD's, in every locale OLD has (OLD's pl among them)."""
		en = self.data(skilldesc_rows("en"))
		self.assertEqual({"job": "GUILD", "attribute": "ONLY_FOR_GUILD_WAR", "weapon": "", "icon": "gaho",
		                  "motion index": "107", "motion grades": "1", "target count": "", "motion loop count": ""},
		                 en[152])
		for locale in locales():
			data = self.data(skilldesc_rows(locale))
			for skill in self.GUILD_SKILLS:
				with self.subTest(locale=locale, skill=skill):
					self.assertEqual(en[skill], data[skill])
		old_root = os.path.join(REPO, "..", "..", "..", "old", "client_pack", "source", "locale")
		if not os.path.isdir(old_root):
			return
		for locale in sorted(os.listdir(old_root)):
			path = os.path.join(old_root, locale, "skilldesc.txt")
			if not os.path.isfile(path):
				continue
			with open(path, encoding="utf-8", errors="replace") as handle:
				rows = [line.rstrip("\r").split("\t") for line in handle.read().split("\n")]
			data = self.data(row for row in rows if row[0].strip().isdigit())
			with self.subTest(old=locale):
				self.assertEqual(en, data)


if __name__ == "__main__":
	unittest.main()
