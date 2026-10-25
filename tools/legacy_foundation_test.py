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


class InventoryPages(unittest.TestCase):
	"""Five inventory pages (NOVA-97): one tab per page in the legacy
	inventory (uiinventory.py), the uiscript's five tabs, and the scans that
	cover every page."""

	def make_inventory(self, world):
		module = world.load("uiInventory", "uiinventory.py")
		module.print = lambda *args, **kwargs: None
		with world, quiet():
			window = module.InventoryWindow()
			window.BindInterfaceClass(world.game.interface)
			window.SetItemToolTip(world.game.modules["uiToolTip"].ItemToolTip())
			window.Show()
		return window

	def test_the_inventory_binds_one_tab_per_page_and_shows_the_pressed_page(self):
		world = LegacyWorld()
		world.game.give(4 * PAGE_SIZE + 3, 27001, 7)
		window = self.make_inventory(world)
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


if __name__ == "__main__":
	unittest.main()
