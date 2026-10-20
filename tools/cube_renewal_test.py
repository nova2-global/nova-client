"""Headless tests of the cube renewal window (assets/root/uicuberenewal.py, NOVA-14).

The client's C++ modules (cube_renewal, player, item, app, grp) and the legacy
widgets (ui) are stood in for by the small fakes below; the window's real
uiscript (assets/uiscript/uiscript/cuberenewalwindow.py) and the real locale
files are used. Run from the repository root or from tools/:

	python3 -B -m unittest cube_renewal_test        (in tools/)
	python3 -B tools/cube_renewal_test.py
"""

import ast
import gc
import importlib.util
import os
import sys
import types
import unittest
import unittest.mock
import warnings

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(REPO, "assets", "root")
UISCRIPT = os.path.join(REPO, "assets", "uiscript")
LOCALES = os.path.join(REPO, "assets", "locale", "locale")


def ReadText(path):
	with open(path, encoding="utf-8") as f:
		return f.read()


def ReadLocaleFile(path):
	keys = {}
	for line in ReadText(path).split("\n"):
		tokens = line.split("\t")
		if len(tokens) >= 2 and tokens[0]:
			keys[tokens[0]] = tokens[1]
	return keys


###############################################################################
## Widgets

class FakeWindow(object):
	def __init__(self, *args):
		self.shown = False
		self.position = (0, 0)
		self.size = (0, 0)
		self.flags = []
		self.parent = None
		self.focused = False
		self.Hide()		# as ui.Window.__init__ does

	def __del__(self):
		pass

	def SetParent(self, parent):
		self.parent = parent

	def AddFlag(self, flag):
		self.flags.append(flag)

	def Show(self):
		self.shown = True

	def Hide(self):
		self.shown = False

	def IsShow(self):
		return self.shown

	def SetTop(self):
		pass

	def SetPosition(self, x, y):
		self.position = (int(x), int(y))

	def GetLocalPosition(self):
		return self.position

	def SetSize(self, width, height):
		self.size = (int(width), int(height))

	def GetWidth(self):
		return self.size[0]

	def GetHeight(self):
		return self.size[1]

	def SetWindowHorizontalAlignRight(self):
		pass

	def SetWindowVerticalAlignCenter(self):
		pass

	def IsFocus(self):
		return self.focused

	def SetFocus(self):
		self.focused = True

	def KillFocus(self):
		self.focused = False

	def Destroy(self):
		pass


class FakeScriptWindow(FakeWindow):
	def __init__(self, *args):
		FakeWindow.__init__(self)
		self.Children = []
		self.ElementDictionary = {}

	def ClearDictionary(self):
		self.Children = []
		self.ElementDictionary = {}

	def InsertChild(self, name, child):
		self.ElementDictionary[name] = child

	def GetChild(self, name):
		return self.ElementDictionary[name]


class FakeTextLine(FakeWindow):
	def __init__(self, *args):
		FakeWindow.__init__(self)
		self.text = ""
		self.color = None

	def SetText(self, text):
		self.text = text

	def GetText(self):
		return self.text

	def SetPackedFontColor(self, color):
		self.color = color

	def GetTextSize(self):
		return (6 * len(self.text), 12)


class FakeEditLine(FakeTextLine):
	def __init__(self, *args):
		FakeTextLine.__init__(self)
		self.eventReturn = None
		self.eventEscape = None
		self.useIME = True

	def SetReturnEvent(self, event):
		self.eventReturn = event

	def SetEscapeEvent(self, event):
		self.eventEscape = event

	def SetIMEFlag(self, flag):
		self.useIME = flag

	def Type(self, text):
		self.focused = True
		self.text = text


class FakeImageBox(FakeWindow):
	def __init__(self, *args):
		FakeWindow.__init__(self)
		self.image = None

	def LoadImage(self, image):
		self.image = image


class FakeBar(FakeWindow):
	def SetColor(self, color):
		self.color = color


class FakeButton(FakeWindow):
	def __init__(self, *args):
		FakeWindow.__init__(self)
		self.event = None
		self.flashes = 0

	def SetEvent(self, event, *args):
		self.event = event

	def Flash(self):
		self.flashes += 1

	def Click(self):
		self.event()


class FakeBoard(FakeWindow):
	def __init__(self, *args):
		FakeWindow.__init__(self)
		self.closeEvent = None

	def SetCloseEvent(self, event):
		self.closeEvent = event


class FakeSlotWindow(FakeWindow):
	def __init__(self, *args):
		FakeWindow.__init__(self)
		self.slots = {}
		self.overIn = None
		self.overOut = None

	def SetItemSlot(self, slotIndex, vnum, count=0):
		if not vnum:
			self.slots.pop(slotIndex, None)
			return
		self.slots[slotIndex] = (vnum, count)

	def ClearSlot(self, slotIndex):
		self.slots.pop(slotIndex, None)

	def SetOverInItemEvent(self, event):
		self.overIn = event

	def SetOverOutItemEvent(self, event):
		self.overOut = event


class FakeScrollBar(FakeWindow):
	def __init__(self, *args):
		FakeWindow.__init__(self)
		self.pos = 0.0
		self.middle = 1.0
		self.event = None

	def SetScrollEvent(self, event):
		self.event = event

	def SetMiddleBarSize(self, scale):
		self.middle = scale

	def SetPos(self, pos):
		self.pos = max(0.0, min(1.0, pos))
		self.event()

	def GetPos(self):
		return self.pos

	def Drag(self, pos):
		self.SetPos(pos)


WIDGET_TYPES = {
	"window" : FakeScriptWindow,
	"board_with_titlebar" : FakeBoard,
	"thinboard" : FakeWindow,
	"image" : FakeImageBox,
	"text" : FakeTextLine,
	"editline" : FakeEditLine,
	"button" : FakeButton,
	"slot" : FakeSlotWindow,
	"scrollbar" : FakeScrollBar,
}

# The keys the real loader needs for each type (ui.PythonScriptLoader).
REQUIRED_KEYS = {
	"board_with_titlebar" : ("width", "height", "title"),
	"thinboard" : ("width", "height"),
	"image" : ("image",),
	"editline" : ("width", "height", "input_limit"),
	"slot" : ("width", "height", "slot"),
	"scrollbar" : ("size",),
}


class FakeScriptLoader(object):
	"""Runs the real uiscript and builds fake widgets from it, as ui.PythonScriptLoader does."""

	def LoadScriptFile(self, window, fileName):
		path = os.path.join(UISCRIPT, fileName.replace("/", os.sep))
		scope = {"SCREEN_WIDTH" : 1920, "SCREEN_HEIGHT" : 1080}
		exec(compile(ReadText(path), path, "exec"), scope)
		self.ScriptDictionary = scope
		body = scope["window"]
		window.ClearDictionary()
		window.SetPosition(body["x"], body["y"])
		window.SetSize(body["width"], body["height"])
		self.LoadChildren(window, body)

	def LoadChildren(self, parent, value):
		for child in value.get("children", ()):
			widgetType = child.get("type", "window")
			for key in ("name", "x", "y") + REQUIRED_KEYS.get(widgetType, ()):
				if key not in child:
					raise KeyError("%s: %s" % (child.get("name"), key))

			widget = WIDGET_TYPES[widgetType]()
			widget.SetParent(parent)
			widget.SetPosition(child["x"], child["y"])
			if widgetType == "scrollbar":
				widget.SetSize(17, child["size"])
			elif "width" in child and "height" in child:
				widget.SetSize(child["width"], child["height"])
			if widgetType == "slot":
				widget.slotRects = dict((s["index"], (s["x"], s["y"], s["width"], s["height"])) for s in child["slot"])
			if widgetType == "editline":
				widget.inputLimit = child["input_limit"]
				widget.onlyNumber = child.get("only_number", 0)
			widget.Show()
			self.root.InsertChild(child["name"], widget)
			self.LoadChildren(widget, child)

	def __init__(self):
		self.root = None
		self.ScriptDictionary = {}


def MakeLoader():
	loader = FakeScriptLoader()
	original = loader.LoadScriptFile

	def LoadScriptFile(window, fileName):
		loader.root = window
		original(window, fileName)

	loader.LoadScriptFile = LoadScriptFile
	return loader


class FakeMemFunc(object):
	def __init__(self, method):
		self.method = method

	def __call__(self, *args):
		return self.method(*args)


###############################################################################
## Game modules

class Game(object):
	"""What the client knows: the recipes, the items, the inventory, the gold."""

	def __init__(self):
		self.time = 100.0
		self.recipes = []
		self.handler = "unset"
		self.handlerCalls = []
		self.made = []
		self.closes = 0
		self.protos = {}
		self.inventory = {}
		self.gold = 0
		self.noCopy = set()		# (cell, attribute slot) the reward drops
		self.selected = None
		self.position = (25600.0, -38400.0, 0.0)
		self.inventoryReads = 0		# player.GetItemIndex and GetItemCountByVnum calls


GAME = Game()

ATTRIBUTE_SLOT_MAX_NUM = 7
METIN_SOCKET_MAX_NUM = 3
ITEM_TYPE_WEAPON = 1
ITEM_TYPE_ARMOR = 2
ITEM_TYPE_MATERIAL = 5


def MakeModules():
	modules = {}

	app = types.ModuleType("app")
	app.GetTime = lambda: GAME.time
	modules["app"] = app

	grp = types.ModuleType("grp")
	grp.GenerateColor = lambda r, g, b, a: ("color", r, g, b, a)
	modules["grp"] = grp

	item = types.ModuleType("item")
	item.ITEM_TYPE_WEAPON = ITEM_TYPE_WEAPON
	item.ITEM_TYPE_ARMOR = ITEM_TYPE_ARMOR

	def SelectItem(vnum):
		GAME.selected = GAME.protos.get(vnum)
		return GAME.selected is not None

	def Selected():
		if GAME.selected is None:
			raise RuntimeError("no selected item data")
		return GAME.selected

	item.SelectItem = SelectItem
	item.GetItemName = lambda: Selected()["name"]
	item.GetItemType = lambda: Selected()["type"]
	item.GetItemSubType = lambda: Selected()["subtype"]
	item.HasBonusRestriction = lambda: Selected()["restricted"]
	modules["item"] = item

	player = types.ModuleType("player")
	player.INVENTORY_PAGE_SIZE = 45
	player.INVENTORY_PAGE_COUNT = 2
	player.METIN_SOCKET_MAX_NUM = METIN_SOCKET_MAX_NUM
	player.ATTRIBUTE_SLOT_MAX_NUM = ATTRIBUTE_SLOT_MAX_NUM
	def GetItemCountByVnum(vnum):
		GAME.inventoryReads += 1
		return sum(e["count"] for e in GAME.inventory.values() if e["vnum"] == vnum)

	def GetItemIndex(cell):
		GAME.inventoryReads += 1
		return GAME.inventory.get(cell, {"vnum" : 0})["vnum"]

	player.GetItemCountByVnum = GetItemCountByVnum
	player.GetItemIndex = GetItemIndex
	player.GetItemCount = lambda cell: GAME.inventory.get(cell, {"count" : 0})["count"]
	player.GetMainCharacterPosition = lambda: GAME.position
	player.GetItemMetinSocket = lambda cell, i: GAME.inventory[cell]["sockets"][i] if cell in GAME.inventory else 0
	player.GetItemAttribute = lambda cell, i: GAME.inventory[cell]["attrs"][i] if cell in GAME.inventory else (0, 0)
	player.GetElk = lambda: GAME.gold
	modules["player"] = player

	cube = types.ModuleType("cube_renewal")
	cube.MATERIAL_MAX = 10
	cube.QUANTITY_MAX = 200
	cube.CATEGORY_LEN = 32
	cube.MAX_DISTANCE = 1000
	cube.CountDates = lambda: len(GAME.recipes)

	def GetDates(index):
		if not 0 <= index < len(GAME.recipes):
			return (0,) * 25 + ("", 0, 0, 0)
		return GAME.recipes[index]

	def SetCubeRenewalHandler(handler):
		GAME.handler = handler
		GAME.handlerCalls.append(handler)

	def GetCubeRenewalHandler():
		return None if GAME.handler == "unset" else GAME.handler

	def MakeItem(index, count):
		GAME.made.append((index, count))

	def Close():
		GAME.closes += 1

	def CanCopyAttribute(cell, attrIndex, resultVnum):
		if not 0 <= cell or cell not in GAME.inventory:
			return False
		return (cell, attrIndex) not in GAME.noCopy

	cube.GetDates = GetDates
	cube.SetCubeRenewalHandler = SetCubeRenewalHandler
	cube.GetCubeRenewalHandler = GetCubeRenewalHandler
	cube.CubeRenewalMakeItem = MakeItem
	cube.CubeRenewalClose = Close
	cube.CanCopyAttribute = CanCopyAttribute
	cube.GetNpcVnum = lambda: 20383
	modules["cube_renewal"] = cube

	ui = types.ModuleType("ui")
	ui.Window = FakeWindow
	ui.ScriptWindow = FakeScriptWindow
	ui.TextLine = FakeTextLine
	ui.EditLine = FakeEditLine
	ui.ImageBox = FakeImageBox
	ui.Bar = FakeBar
	ui.Button = FakeButton
	ui.SlotWindow = FakeSlotWindow
	ui.PythonScriptLoader = MakeLoader
	setattr(ui, "__mem_func__", FakeMemFunc)
	ui.SELECT_COLOR = ("color", "select")
	ui.HALF_WHITE_COLOR = ("color", "over")
	modules["ui"] = ui

	localeInfo = types.ModuleType("localeInfo")
	for (key, value) in ReadLocaleFile(os.path.join(LOCALES, "en", "locale_game.txt")).items():
		setattr(localeInfo, key, value)
	localeInfo.NumberToMoneyString = lambda n: "%d Yang" % n
	modules["localeInfo"] = localeInfo

	uiScriptLocale = types.ModuleType("uiScriptLocale")
	for (key, value) in ReadLocaleFile(os.path.join(LOCALES, "en", "locale_interface.txt")).items():
		setattr(uiScriptLocale, key, value)
	modules["uiScriptLocale"] = uiScriptLocale

	uiCommon = types.ModuleType("uiCommon")

	class QuestionDialog(object):
		opened = []

		def __init__(self):
			self.text = None
			self.accept = None
			self.cancel = None
			self.isOpen = False

		def SetText(self, text):
			self.text = text

		def SetAcceptEvent(self, event):
			self.accept = event

		def SetCancelEvent(self, event):
			self.cancel = event

		def Open(self):
			self.isOpen = True
			QuestionDialog.opened.append(self)

		def Close(self):
			self.isOpen = False

	uiCommon.QuestionDialog = QuestionDialog
	modules["uiCommon"] = uiCommon

	uiToolTip = types.ModuleType("uiToolTip")

	class ItemToolTip(object):
		AFFECT_DICT = {72 : lambda value: "Strong against Warriors +%d%%" % value}

	uiToolTip.ItemToolTip = ItemToolTip
	modules["uiToolTip"] = uiToolTip

	exception = types.ModuleType("exception")

	def Abort(message):
		raise RuntimeError(message)

	exception.Abort = Abort
	modules["exception"] = exception

	return modules


class FakeToolTip(object):
	def __init__(self):
		self.shown = None
		self.hidden = 0

	def ClearToolTip(self):
		self.shown = None

	def AddItemData(self, vnum, sockets, attrs):
		self.shown = (vnum, list(sockets), list(attrs))

	def HideToolTip(self):
		self.hidden += 1
		self.shown = None


def IsolateModules(test):
	"""Gives sys.modules back as it was when `test` ends: the fakes put there
	must not reach the other tests of a one-process run of tools/*_test.py."""
	patcher = unittest.mock.patch.dict(sys.modules)
	patcher.start()
	test.addCleanup(patcher.stop)


# Call IsolateModules first: this puts the fakes in sys.modules.
def LoadWindowModule():
	sys.modules.update(MakeModules())
	path = os.path.join(ROOT, "uicuberenewal.py")
	spec = importlib.util.spec_from_file_location("uiCubeRenewal", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


###############################################################################
## Recipe data

def Recipe(reward, count=1, materials=(), gold=0, percent=100, category="", gem=0, allowCopy=0, ranged=False, stackable=None):
	if stackable is None:
		stackable = count > 1 or GAME.protos.get(reward, {}).get("stackable", False)
	flat = []
	for i in range(10):
		if i < len(materials):
			flat.extend(materials[i])
		else:
			flat.extend((0, 0))
	return (reward, count, 1 if stackable else 0) + tuple(flat) + (gold, percent, category, gem, allowCopy, 1 if ranged else 0)


def Proto(vnum, name, itemType=ITEM_TYPE_MATERIAL, subtype=0, restricted=False, stackable=False):
	GAME.protos[vnum] = {"name" : name, "type" : itemType, "subtype" : subtype, "restricted" : restricted, "stackable" : stackable}


def Own(cell, vnum, count=1, sockets=None, attrs=None):
	GAME.inventory[cell] = {
		"vnum" : vnum,
		"count" : count,
		"sockets" : sockets or [0] * METIN_SOCKET_MAX_NUM,
		"attrs" : attrs or [(0, 0)] * ATTRIBUTE_SLOT_MAX_NUM,
	}


SWORD5, SWORD6, SWORD9 = 15, 16, 19
ARMOR5, ARMOR6 = 11205, 11206
SHIELD = 13009
ORE, BLESS, DEW, PEARL = 30010, 25040, 30000, 27992
GEM = 50601


class CubeRenewalTest(unittest.TestCase):

	def setUp(self):
		global GAME
		GAME = Game()
		IsolateModules(self)
		self.cube = LoadWindowModule()
		sys.modules["uiCommon"].QuestionDialog.opened = []

		Proto(SWORD5, "Sword+5", ITEM_TYPE_WEAPON, 0)
		Proto(SWORD6, "Sword+6", ITEM_TYPE_WEAPON, 0)
		Proto(SWORD9, "Sword+9", ITEM_TYPE_WEAPON, 0, restricted=True)
		Proto(ARMOR5, "Armour+5", ITEM_TYPE_ARMOR, 0)
		Proto(ARMOR6, "Armour+6", ITEM_TYPE_ARMOR, 0)
		Proto(SHIELD, "Shield", ITEM_TYPE_ARMOR, 2)
		Proto(ORE, "Ore", stackable=True)
		Proto(BLESS, "Blessing Scroll", stackable=True)
		Proto(DEW, "Dew", stackable=True)
		Proto(PEARL, "Pearl", stackable=True)
		Proto(GEM, "Gem", stackable=True)
		for vnum in range(GEM + 1, GEM + 10):
			Proto(vnum, "Gem %d" % vnum, stackable=True)

		GAME.gold = 1000000

	def Open(self, recipes):
		GAME.recipes = recipes
		window = self.cube.CubeRenewalWindow()
		window.LoadWindow()
		window.SetItemToolTip(FakeToolTip())
		window.BINARY_CUBE_RENEWAL_LOADING()
		window.Open()
		self.window = window
		return window

	def Row(self, level, key):
		return self.window.rows[(level, key)]

	def ShownRowKeys(self):
		rows = [(row.position[1], rowKey) for (rowKey, row) in self.window.rows.items() if row.shown]
		return [rowKey for (y, rowKey) in sorted(rows)]

	def Child(self, name):
		return self.window.GetChild(name)

	def Texts(self):
		return [(t.text if t.shown else None) for t in self.window.materialTexts]

	## Registration and the uiscript

	def test_the_window_registers_itself_as_the_handler_and_destroy_clears_it(self):
		window = self.cube.CubeRenewalWindow()
		self.assertIs(window, GAME.handler)
		window.LoadWindow()
		window.Destroy()
		self.assertIsNone(GAME.handler)

	def test_destroy_lets_the_handler_go_only_while_it_is_this_window(self):
		# game.py makes the next game phase's interface (and its window) before
		# the last one's goes when the curtain has not finished fading.
		old = self.cube.CubeRenewalWindow()
		old.LoadWindow()
		new = self.cube.CubeRenewalWindow()
		new.LoadWindow()
		self.assertIs(new, GAME.handler)

		old.Destroy()
		self.assertIs(new, GAME.handler)
		self.assertEqual([old, new], GAME.handlerCalls)

		new.Destroy()
		self.assertIsNone(GAME.handler)

		# cube_renewal let go when the game phase ended: nothing to clear.
		window = self.cube.CubeRenewalWindow()
		window.LoadWindow()
		GAME.handler = None
		calls = len(GAME.handlerCalls)
		window.Destroy()
		self.assertEqual(calls, len(GAME.handlerCalls))

	def test_the_uiscript_must_lay_out_a_page_of_material_slots(self):
		self.cube.SLOTS_PER_PAGE = 4
		window = self.cube.CubeRenewalWindow()
		with self.assertRaisesRegex(RuntimeError, "MaterialSlotCount"):
			window.LoadWindow()

	def test_the_rows_and_the_slots_fit_their_boards(self):
		window = self.Open([])
		listBoard = self.Child("item_list_board")
		rowBottom = lambda row: self.cube.ROW_TOP + self.cube.ROW_STEP * row + self.cube.ROW_HEIGHT
		self.assertLessEqual(rowBottom(window.visibleRowCount - 1), listBoard.GetHeight())
		self.assertGreater(rowBottom(window.visibleRowCount), listBoard.GetHeight(), "one row more would fit")

		scope = {"SCREEN_WIDTH" : 1920, "SCREEN_HEIGHT" : 1080}
		path = os.path.join(UISCRIPT, "uiscript", "cuberenewalwindow.py")
		exec(compile(ReadText(path), path, "exec"), scope)
		self.assertEqual(self.cube.SLOTS_PER_PAGE, scope["MATERIAL_SLOT_COUNT"])
		icons = self.Child("icons_items")
		for (x, y, width, height) in icons.slotRects.values():
			self.assertLessEqual(x + width, icons.GetWidth())
			self.assertLessEqual(y + height, icons.GetHeight())
		itemSlot = self.Child("item_slot")
		self.assertLessEqual(icons.GetLocalPosition()[0] + icons.GetWidth(), itemSlot.GetWidth())
		self.assertLessEqual(self.Child("next_button").GetLocalPosition()[0] + scope["PAGE_BUTTON_WIDTH"], itemSlot.GetWidth())
		self.assertEqual(self.Child("board").GetWidth(), itemSlot.GetLocalPosition()[0] * 2 + itemSlot.GetWidth())

	def test_read_recipe_documents_every_key_it_returns(self):
		window = self.Open([])
		recipe = window.ReadRecipe(3, Recipe(PEARL, materials=[(ORE, 2), (0, 0), (DEW, 1)]))
		self.assertEqual([(ORE, 2), (DEW, 1)], recipe["materials"], "an unused material is dropped")
		doc = self.cube.CubeRenewalWindow.ReadRecipe.__doc__
		for key in recipe:
			self.assertIn('"%s"' % key, doc)

	def test_the_uiscript_has_every_widget_the_window_binds_and_its_slots(self):
		window = self.Open([])
		slots = self.Child("icons_items").slotRects
		self.assertEqual(sorted(slots), list(range(1 + self.cube.SLOTS_PER_PAGE)))
		for (index, rect) in slots.items():
			self.assertEqual((32, 96), rect[2:])
		self.assertEqual(self.Child("board").GetWidth(), self.Child("board").parent.GetWidth())
		self.assertEqual(4, self.Child("result_qty").inputLimit)
		self.assertEqual(12, window.visibleRowCount)
		self.assertIsNotNone(self.Child("board").closeEvent)

	## The tree

	def test_categories_rewards_and_recipes_in_first_appearance_order(self):
		recipes = [
			Recipe(ARMOR6, materials=[(ARMOR5, 1)], category="ARMOR"),
			Recipe(SWORD6, materials=[(SWORD5, 1)], category="WEAPON"),
			Recipe(GEM, materials=[(ORE, 2)], category="NO_SUCH_CATEGORY"),
			Recipe(ARMOR6, materials=[(ARMOR5, 1), (ORE, 1)], category="ARMOR"),
			Recipe(SWORD9, materials=[(SWORD5, 1)], category="WEAPON"),
			Recipe(PEARL, materials=[(ORE, 1)]),
		]
		window = self.Open(recipes)
		self.assertEqual([
			{"category" : "ARMOR", "rewards" : [{"vnum" : ARMOR6, "recipes" : [0, 3]}]},
			{"category" : "WEAPON", "rewards" : [{"vnum" : SWORD6, "recipes" : [1]}, {"vnum" : SWORD9, "recipes" : [4]}]},
			{"category" : "OTHERS", "rewards" : [{"vnum" : GEM, "recipes" : [2]}, {"vnum" : PEARL, "recipes" : [5]}]},
		], window.tree)

		self.assertEqual("Armors", self.Row(0, "ARMOR").text.text)
		self.assertEqual("Others", self.Row(0, "OTHERS").text.text)
		self.assertEqual([(0, "ARMOR"), (0, "WEAPON"), (0, "OTHERS")], self.ShownRowKeys())

		self.Row(0, "WEAPON").OnMouseLeftButtonDown()
		self.assertEqual([(0, "ARMOR"), (0, "WEAPON"), (1, ("WEAPON", SWORD6)), (1, ("WEAPON", SWORD9)), (0, "OTHERS")], self.ShownRowKeys())
		self.assertEqual(self.cube.ROW_ICON_OPEN, self.Row(0, "WEAPON").icon.image)
		self.assertEqual(self.cube.ROW_ICON_CLOSED, self.Row(1, ("WEAPON", SWORD9)).icon.image)
		self.assertEqual("Sword+9", self.Row(1, ("WEAPON", SWORD9)).text.text)

		self.Row(1, ("WEAPON", SWORD9)).OnMouseLeftButtonDown()
		self.assertIn((2, 4), self.ShownRowKeys())
		self.assertEqual("Sword+9 (100%)", self.Row(2, 4).text.text)
		self.assertEqual((6 + 35, 8 + 20 * 4), self.Row(2, 4).position)
		self.assertEqual((6 + 15, 8 + 20 * 3), self.Row(1, ("WEAPON", SWORD9)).position)

		# Closing a category keeps what was open under it (OLD toggled every reward row).
		self.Row(0, "WEAPON").OnMouseLeftButtonDown()
		self.assertEqual([(0, "ARMOR"), (0, "WEAPON"), (0, "OTHERS")], self.ShownRowKeys())
		self.Row(0, "WEAPON").OnMouseLeftButtonDown()
		self.assertIn((2, 4), self.ShownRowKeys())

	def test_a_long_list_scrolls(self):
		recipes = [Recipe(GEM + i % 10, materials=[(ORE, 1)], category="GEMS") for i in range(30)]
		window = self.Open(recipes)
		scrollBar = self.Child("list_scroll_bar")
		self.assertFalse(scrollBar.shown)

		window.ToggleCategory("GEMS")
		for i in range(10):
			window.ToggleReward(("GEMS", GEM + i))
		self.assertEqual(41, len(window.visibleRows))
		self.assertTrue(scrollBar.shown)
		self.assertAlmostEqual(12.0 / 41, scrollBar.middle)
		self.assertEqual(12, len(self.ShownRowKeys()))
		self.assertEqual((0, "GEMS"), self.ShownRowKeys()[0])

		scrollBar.Drag(1.0)
		self.assertEqual(29, window.startLine)
		self.assertEqual(window.visibleRows[29:], self.ShownRowKeys())
		self.assertEqual(8, self.Row(*window.visibleRows[29]).position[1])

		# Closing the category leaves one row: no scroll bar, back to the top.
		window.ToggleCategory("GEMS")
		self.assertFalse(scrollBar.shown)
		self.assertEqual(0, window.startLine)
		self.assertEqual([(0, "GEMS")], self.ShownRowKeys())

	## Counts

	def test_craftable_count_and_the_recipe_rows_n(self):
		window = self.Open([
			Recipe(GEM, count=2, materials=[(ORE, 3), (DEW, 1)]),
			Recipe(PEARL, materials=[(ORE, 1)]),
			Recipe(SWORD6, materials=[]),
		])
		Own(0, ORE, 10)
		Own(1, DEW, 2)
		Own(2, ORE, 1)
		window.Refresh()
		self.assertEqual(2, window.GetCraftableCount(window.recipes[0]))
		self.assertEqual("[4]", self.Row(2, 0).countText.text)
		self.assertTrue(self.Row(2, 0).countText.shown)
		self.assertEqual("[11]", self.Row(2, 1).countText.text)
		self.assertEqual(0, window.GetCraftableCount(window.recipes[2]))
		self.assertFalse(self.Row(2, 2).countText.shown)

		# The name moves after the count, and back when the count goes.
		self.assertEqual(16 + 6 * len("[4]") + 4, self.Row(2, 0).text.position[0])
		del GAME.inventory[1]
		window.Refresh()
		self.assertFalse(self.Row(2, 0).countText.shown)
		self.assertEqual(17, self.Row(2, 0).text.position[0])

	def test_refresh_does_nothing_while_hidden(self):
		window = self.Open([Recipe(PEARL, materials=[(ORE, 1)])])
		window.Close()
		Own(0, ORE, 5)
		window.Refresh()
		self.assertFalse(self.Row(2, 0).countText.shown)
		window.Open()
		self.assertEqual("[5]", self.Row(2, 0).countText.text)

	## Selection, slots, costs

	def test_selecting_a_recipe_shows_its_result_materials_counts_and_cost(self):
		window = self.Open([Recipe(GEM, count=2, materials=[(ORE, 3), (DEW, 1)], gold=5000)])
		Own(0, ORE, 2)
		Own(1, DEW, 4)
		GAME.gold = 5000
		window.SelectObject(0)

		slots = self.Child("icons_items").slots
		self.assertEqual({0 : (GEM, 2), 1 : (ORE, 3), 2 : (DEW, 1)}, slots)
		self.assertEqual(["2/3", "4/1", None, None, None], self.Texts())
		self.assertEqual(self.cube.MISSING_COLOR, window.materialTexts[0].color)
		self.assertEqual(self.cube.ENOUGH_COLOR, window.materialTexts[1].color)
		self.assertEqual("5000 Yang", self.Child("yang_text").text)
		# Exactly the gold needed is enough (OLD showed it red).
		self.assertEqual(self.cube.COST_COLOR, self.Child("yang_text").color)
		GAME.gold = 4999
		window.Refresh()
		self.assertEqual(self.cube.MISSING_COLOR, self.Child("yang_text").color)

		self.assertEqual("2", self.Child("result_qty").text)
		self.assertTrue(self.Child("result_qty").shown)
		self.assertFalse(self.Child("next_button").shown)
		self.assertFalse(self.Child("back_button").shown)
		self.assertTrue(self.Row(2, 0).selectBar.shown)

		# Inventory changes reach the counts through Refresh.
		Own(2, ORE, 1)
		window.Refresh()
		self.assertEqual(["3/3", "4/1", None, None, None], self.Texts())

	def test_gaya_is_hidden_unless_a_recipe_costs_gaya(self):
		window = self.Open([Recipe(GEM, materials=[(ORE, 1)])])
		self.assertFalse(self.Child("gem_icon").shown)
		self.assertFalse(self.Child("gem_textbg").shown)

		window = self.Open([Recipe(GEM, materials=[(ORE, 1)], gem=5)])
		self.assertTrue(self.Child("gem_icon").shown)
		window.SelectObject(0)
		self.assertEqual("5", self.Child("gem_text").text)
		self.assertEqual(self.cube.MISSING_COLOR, self.Child("gem_text").color)

	def test_materials_six_to_ten_are_on_the_second_page(self):
		materials = [(GEM + i, i + 1) for i in range(7)]
		window = self.Open([Recipe(PEARL, materials=materials)])
		window.SelectObject(0)
		nextButton = self.Child("next_button")
		backButton = self.Child("back_button")
		self.assertTrue(nextButton.shown)
		self.assertEqual(1, nextButton.flashes)
		self.assertFalse(backButton.shown)

		nextButton.Click()
		self.assertEqual({0 : (PEARL, 1), 1 : (GEM + 5, 6), 2 : (GEM + 6, 7)}, self.Child("icons_items").slots)
		self.assertEqual(["0/6", "0/7", None, None, None], self.Texts())
		self.assertFalse(nextButton.shown)
		self.assertTrue(backButton.shown)
		self.assertEqual(GEM + 6, window.GetSlotVnum(window.recipes[0], 2))

		backButton.Click()
		self.assertEqual((GEM, 1), self.Child("icons_items").slots[1])
		window.UpdateMaterialSlots(5)
		self.assertEqual(1, window.pageIndex)

	## Quantity

	def test_quantity_is_clamped_to_multiples_of_the_reward_count_up_to_200(self):
		window = self.Open([
			Recipe(GEM, count=3, materials=[(ORE, 2)]),
			Recipe(SWORD6, materials=[(SWORD5, 1)]),
		])
		stackable = window.recipes[0]
		self.assertEqual(3, window.ClampQuantity(stackable, 0))
		self.assertEqual(3, window.ClampQuantity(stackable, 4))
		self.assertEqual(48, window.ClampQuantity(stackable, 50))
		# OLD let 200 through, which is no multiple of 3.
		self.assertEqual(198, window.ClampQuantity(stackable, 200))
		self.assertEqual(198, window.ClampQuantity(stackable, 9999))
		self.assertEqual(1, window.ClampQuantity(window.recipes[1], 5))

		Own(0, ORE, 9)
		window.SelectObject(0)
		qty = self.Child("result_qty")
		qty.Type("7")
		qty.eventReturn()
		self.assertEqual("6", qty.text)
		self.assertFalse(qty.focused)
		self.assertEqual({0 : (GEM, 6), 1 : (ORE, 4)}, self.Child("icons_items").slots)
		self.assertEqual("9/4", window.materialTexts[0].text)

		self.Child("qty_add_button").Click()
		self.assertEqual("12", qty.text)
		self.Child("qty_sub_button").Click()
		self.assertEqual("3", qty.text)

		qty.Type("")
		qty.eventReturn()
		self.assertEqual("3", qty.text)

	## Crafting

	def test_ok_sends_the_recipe_index_and_the_multiplier(self):
		window = self.Open([Recipe(PEARL, materials=[(ORE, 1)]), Recipe(GEM, count=2, materials=[(ORE, 1)])])
		self.Child("button_ok").Click()
		self.assertEqual([], GAME.made)

		window.SelectObject(1)
		qty = self.Child("result_qty")
		qty.Type("10")
		qty.eventReturn()
		self.Child("button_ok").Click()
		self.assertEqual([(1, 5)], GAME.made)

		# A quantity typed but not confirmed is taken as Enter would (OLD crafted the minimum).
		qty.Type("21")
		self.Child("button_ok").Click()
		self.assertEqual([(1, 5), (1, 10)], GAME.made)
		self.assertEqual("20", qty.text)

	def test_a_bonus_the_reward_drops_asks_first(self):
		window = self.Open([Recipe(SWORD9, materials=[(SWORD5, 1), (BLESS, 1)], allowCopy=SWORD5)])
		attrs = [(1, 500), (72, 10), (0, 0), (0, 0), (0, 0), (72, 5), (0, 0)]
		Own(3, SWORD5, 1, sockets=[28030, 0, 1], attrs=attrs)
		GAME.noCopy.add((3, 5))
		window.SelectObject(0)

		self.assertEqual((72, 5), window.GetRestrictedBonus(window.recipes[0]))
		self.Child("button_ok").Click()
		self.assertEqual([], GAME.made)
		dialog = sys.modules["uiCommon"].QuestionDialog.opened[-1]
		self.assertEqual("Attention! Strong against Warriors +5% cannot be copied!\\nWould you like to continue?", dialog.text)

		dialog.cancel()
		self.assertFalse(dialog.isOpen)
		self.assertEqual([], GAME.made)

		self.Child("button_ok").Click()
		dialog = sys.modules["uiCommon"].QuestionDialog.opened[-1]
		dialog.accept()
		self.assertFalse(dialog.isOpen)
		self.assertEqual([(0, 1)], GAME.made)

		# A reward with no restricted apply never asks.
		GAME.protos[SWORD9]["restricted"] = False
		self.Child("button_ok").Click()
		self.assertEqual([(0, 1), (0, 1)], GAME.made)

	def test_the_result_tooltip_previews_what_the_reward_copies(self):
		window = self.Open([
			Recipe(SWORD6, materials=[(SWORD5, 1), (BLESS, 1)], allowCopy=SWORD5),
			Recipe(ARMOR6, materials=[(BLESS, 1), (ARMOR5, 1)], allowCopy=1),
			Recipe(SHIELD, materials=[(SWORD5, 1)], allowCopy=SWORD5),
			Recipe(SWORD6, materials=[(BLESS, 1)], allowCopy=BLESS),
		])
		tooltip = window.tooltipItem
		attrs = [(1, 500), (2, 10), (0, 0), (0, 0), (0, 0), (72, 5), (0, 0)]
		Own(7, SWORD5, 1, sockets=[28030, 1, 0], attrs=attrs)
		Own(9, ARMOR5, 1, sockets=[1, 2, 3], attrs=[(3, 3)] + [(0, 0)] * 6)
		Own(4, BLESS, 3)
		GAME.noCopy.add((7, 5))

		window.SelectObject(0)
		self.Child("icons_items").overIn(0)
		self.assertEqual((SWORD6, [28030, 1, 0], [(1, 500), (2, 10), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0)]), tooltip.shown)

		# allow_copy 1: the first material the player owns, in recipe order (OLD looked for vnum 1).
		window.SelectObject(1)
		self.assertEqual(4, window.FindCopySourceCell(window.recipes[1]))
		del GAME.inventory[4]
		self.assertEqual(9, window.FindCopySourceCell(window.recipes[1]))
		self.Child("icons_items").overIn(0)
		self.assertEqual((ARMOR6, [1, 2, 3], [(3, 3)] + [(0, 0)] * 6), tooltip.shown)

		# allow_copy <vnum> needs a weapon or armour of the reward's subtype.
		self.assertEqual(-1, window.FindCopySourceCell(window.recipes[2]))
		Own(4, BLESS, 3)
		self.assertEqual(-1, window.FindCopySourceCell(window.recipes[3]))
		window.SelectObject(2)
		self.Child("icons_items").overIn(0)
		self.assertEqual((SHIELD, [0, 0, 0], [(0, 0)] * 7), tooltip.shown)

		# No copy source: the bare reward.
		del GAME.inventory[7]
		window.SelectObject(0)
		self.Child("icons_items").overIn(0)
		self.assertEqual((SWORD6, [0, 0, 0], [(0, 0)] * 7), tooltip.shown)

		self.Child("icons_items").overOut()
		self.assertIsNone(tooltip.shown)

	def test_a_material_tooltip_shows_the_first_one_owned(self):
		window = self.Open([Recipe(SWORD6, materials=[(SWORD5, 1), (BLESS, 1)])])
		tooltip = window.tooltipItem
		Own(12, SWORD5, 1, sockets=[1, 1, 1], attrs=[(5, 5)] + [(0, 0)] * 6)
		Own(20, SWORD5, 1, sockets=[2, 2, 2])
		window.SelectObject(0)
		self.Child("icons_items").overIn(1)
		self.assertEqual((SWORD5, [1, 1, 1], [(5, 5)] + [(0, 0)] * 6), tooltip.shown)
		self.Child("icons_items").overIn(2)
		self.assertEqual((BLESS, [0, 0, 0], [(0, 0)] * 7), tooltip.shown)
		tooltip.shown = None
		self.Child("icons_items").overIn(4)
		self.assertIsNone(tooltip.shown)

	def test_a_ranged_recipe(self):
		window = self.Open([Recipe(PEARL, count=2, materials=[(GEM, 3), (GEM + 7, 2)], ranged=True)])
		recipe = window.recipes[0]
		self.assertEqual(5, window.GetRangedLength(recipe))
		self.assertEqual([GEM, GEM + 1, GEM + 2, GEM + 7, GEM + 8, 0], [window.GetRangedVnum(recipe, i) for i in range(6)])
		window.SelectObject(0)
		self.assertEqual({0 : (PEARL, 2), 1 : (GEM, 1)}, self.Child("icons_items").slots)
		self.assertEqual(["0/1", None, None, None, None], self.Texts())
		self.assertEqual(self.cube.MISSING_COLOR, window.materialTexts[0].color)

		# No item of the ranges: the server answers (OLD's OK did nothing).
		self.Child("button_ok").Click()
		self.assertEqual([(0, 1)], GAME.made)

		Own(5, GEM + 8, 2)
		Own(6, GEM + 2, 1)
		window.Refresh()
		self.assertEqual(3, window.GetCraftableCount(recipe))
		self.assertEqual("1/1", window.materialTexts[0].text)
		self.assertEqual(GEM + 2, window.GetRangedOwnedVnum(recipe))

		# One at a time: the server takes one item of the ranges whatever the multiplier.
		self.assertEqual(2, window.ClampQuantity(recipe, 10))
		self.Child("qty_add_button").Click()
		self.assertEqual("2", self.Child("result_qty").text)

		self.Child("button_ok").Click()
		dialog = sys.modules["uiCommon"].QuestionDialog.opened[-1]
		self.assertEqual("Do you want to create Pearl using Gem %d?" % (GEM + 2), dialog.text)
		dialog.accept()
		self.assertEqual([(0, 1), (0, 1)], GAME.made)

		# The slot shows the ranges' items in turn, every 1.5 s.
		tooltip = window.tooltipItem
		self.Child("icons_items").overIn(1)
		window.OnUpdate()
		self.assertEqual((GEM, 1), self.Child("icons_items").slots[1])
		GAME.time += 1.5
		window.OnUpdate()
		self.assertEqual((GEM + 1, 1), self.Child("icons_items").slots[1])
		self.assertEqual(GEM + 1, tooltip.shown[0])
		for i in range(4):
			GAME.time += 1.5
			window.OnUpdate()
		self.assertEqual((GEM, 1), self.Child("icons_items").slots[1])

	def test_the_copy_source_is_the_lowest_cell_holding_the_vnum(self):
		window = self.Open([
			Recipe(SWORD6, materials=[(SWORD5, 1), (BLESS, 1)], allowCopy=SWORD5),
			Recipe(ARMOR6, materials=[(ARMOR5, 1), (BLESS, 1)], allowCopy=1),
		])
		Own(30, SWORD5)
		Own(4, SWORD5)
		Own(17, SWORD5)
		Own(21, ARMOR5)
		Own(8, ARMOR5)
		self.assertEqual(4, window.FindCopySourceCell(window.recipes[0]))
		self.assertEqual(8, window.FindCopySourceCell(window.recipes[1]))

	def test_a_ranged_recipe_copies_from_the_item_it_takes(self):
		# The server's TakeCopy: from the item of the ranges the craft takes (the
		# first one owned in the ranges' order), and only when allow_copy is 1 or
		# that item's vnum; OLD's client looked for allow_copy's vnum in the
		# inventory whatever the craft took.
		ranges = [(SWORD5, 2), (ARMOR5, 2)]
		window = self.Open([
			Recipe(SWORD9, materials=ranges, ranged=True, allowCopy=1),
			Recipe(SWORD9, materials=ranges, ranged=True, allowCopy=SWORD6),
			Recipe(SWORD9, materials=ranges, ranged=True, allowCopy=ARMOR5),
			Recipe(SHIELD, materials=ranges, ranged=True, allowCopy=SWORD6),
			Recipe(PEARL, materials=[(GEM, 3)], ranged=True, allowCopy=1),
		])
		(fromTaken, fromSword6, fromArmour5, otherSubtype, anyKind) = window.recipes
		for recipe in window.recipes:
			self.assertEqual(-1, window.FindCopySourceCell(recipe), "nothing of the ranges")

		Own(3, ARMOR5, sockets=[3, 3, 3])
		Own(12, SWORD6, sockets=[12, 12, 12])
		Own(9, SWORD6, sockets=[9, 9, 9])
		self.assertEqual(SWORD6, window.GetRangedOwnedVnum(fromTaken), "the first range's item, not the lowest cell's")
		self.assertEqual(9, window.FindCopySourceCell(fromTaken))
		self.assertEqual(9, window.FindCopySourceCell(fromSword6))
		self.assertEqual(-1, window.FindCopySourceCell(fromArmour5), "owned, but not what the craft takes")
		self.assertEqual(-1, window.FindCopySourceCell(otherSubtype), "a weapon onto a shield")

		window.SelectObject(0)
		self.Child("icons_items").overIn(0)
		self.assertEqual((SWORD9, [9, 9, 9], [(0, 0)] * 7), window.tooltipItem.shown)

		del GAME.inventory[9]
		del GAME.inventory[12]
		self.assertEqual(3, window.FindCopySourceCell(fromTaken))
		self.assertEqual(-1, window.FindCopySourceCell(fromSword6))
		self.assertEqual(3, window.FindCopySourceCell(fromArmour5))

		# allow_copy 1 takes whatever the craft takes, a gem too.
		Own(5, GEM + 1)
		self.assertEqual(5, window.FindCopySourceCell(anyKind))

	def test_ok_asks_about_a_dropped_bonus_and_then_about_the_ranged_item(self):
		window = self.Open([Recipe(SWORD9, materials=[(SWORD5, 2)], ranged=True, allowCopy=1)])
		Own(2, SWORD6, attrs=[(72, 10), (0, 0), (0, 0), (0, 0), (0, 0), (72, 5), (0, 0)])
		GAME.noCopy.add((2, 5))
		window.SelectObject(0)
		dropped = "Attention! Strong against Warriors +5% cannot be copied!\\nWould you like to continue?"
		taken = "Do you want to create Sword+9 using Sword+6?"
		self.assertEqual([dropped, taken], window.GetAcceptQuestions(window.recipes[0]))

		opened = sys.modules["uiCommon"].QuestionDialog.opened
		self.Child("button_ok").Click()
		first = opened[-1]
		self.assertEqual(dropped, first.text)
		first.accept()
		self.assertFalse(first.isOpen)
		self.assertEqual([], GAME.made, "OLD crafted here, without naming the item it takes")
		second = opened[-1]
		self.assertEqual(taken, second.text)
		self.assertTrue(second.isOpen)
		second.accept()
		self.assertFalse(second.isOpen)
		self.assertEqual([(0, 1)], GAME.made)

		# A no to either question crafts nothing, and the next OK starts over.
		self.Child("button_ok").Click()
		opened[-1].accept()
		opened[-1].cancel()
		self.assertEqual([(0, 1)], GAME.made)
		self.assertEqual([], window.pendingQuestions)
		self.Child("button_ok").Click()
		self.assertEqual(dropped, opened[-1].text)
		opened[-1].cancel()
		self.assertEqual([(0, 1)], GAME.made)

		# The ranged question alone when the reward keeps every bonus.
		GAME.noCopy.clear()
		self.assertEqual([taken], window.GetAcceptQuestions(window.recipes[0]))

	def test_a_gold_change_refreshes_only_the_cost(self):
		window = self.Open([Recipe(GEM, count=2, materials=[(ORE, 3)], gold=5000)])
		Own(0, ORE, 3)
		GAME.gold = 5000
		window.SelectObject(0)
		self.assertEqual("5000 Yang", self.Child("yang_text").text)
		self.assertEqual(self.cube.COST_COLOR, self.Child("yang_text").color)
		self.assertEqual("[2]", self.Row(2, 0).countText.text)

		Own(1, ORE, 3)
		GAME.gold = 4999
		GAME.inventoryReads = 0
		window.RefreshCost()
		self.assertEqual(self.cube.MISSING_COLOR, self.Child("yang_text").color)
		self.assertEqual(0, GAME.inventoryReads, "the inventory is not read")
		self.assertEqual("3/3", window.materialTexts[0].text)
		self.assertEqual("[2]", self.Row(2, 0).countText.text)

		window.quantity = 4
		GAME.gold = 10000
		window.RefreshCost()
		self.assertEqual("10000 Yang", self.Child("yang_text").text)
		self.assertEqual(self.cube.COST_COLOR, self.Child("yang_text").color)

		# Nothing selected, or the window hidden: nothing to show.
		window.Close()
		window.RefreshCost()
		self.assertFalse(self.Child("yang_text").shown)
		window.Open()
		window.RefreshCost()
		self.assertFalse(self.Child("yang_text").shown)

	def test_a_ranged_recipe_s_ranges_are_never_listed(self):
		# Two ranges of 65535 items, the most one holds, overlapping.
		window = self.Open([Recipe(PEARL, materials=[(100000, 65535), (130000, 65535)], ranged=True)])
		recipe = window.recipes[0]
		self.assertEqual(131070, window.GetRangedLength(recipe))
		self.assertEqual(100000, window.GetRangedVnum(recipe, 0))
		self.assertEqual(165534, window.GetRangedVnum(recipe, 65534))
		self.assertEqual(130000, window.GetRangedVnum(recipe, 65535))
		self.assertEqual(0, window.GetRangedVnum(recipe, 131070))
		self.assertEqual(40000, window.GetRangedPosition(recipe, 140000), "its place in the first range")
		self.assertEqual(65535 + 60000, window.GetRangedPosition(recipe, 190000))
		self.assertEqual(-1, window.GetRangedPosition(recipe, 99999))
		self.assertEqual(-1, window.GetRangedPosition(recipe, 195535))

		Own(7, 140000, 2)		# in both ranges: one item, counted once
		Own(3, 190000, 1)		# the lowest cell, the last place
		Own(9, 150000, 4)
		player = sys.modules["player"]
		cells = player.INVENTORY_PAGE_SIZE * player.INVENTORY_PAGE_COUNT
		GAME.inventoryReads = 0
		self.assertEqual(140000, window.GetRangedOwnedVnum(recipe))
		self.assertEqual(7, window.GetCraftableCount(recipe))
		self.assertEqual(2 * cells, GAME.inventoryReads, "one pass over the inventory each")

		window.SelectObject(0)
		GAME.inventoryReads = 0
		window.Refresh()
		self.assertLessEqual(GAME.inventoryReads, 2 * cells)
		self.assertEqual("[7]", self.Row(2, 0).countText.text)
		self.assertEqual("1/1", window.materialTexts[0].text)

	## Walking away

	def test_walking_away_from_where_the_cube_opened_closes_it_and_tells_the_server(self):
		self.assertEqual(1000, self.cube.MAX_DISTANCE)
		window = self.Open([Recipe(PEARL, materials=[(ORE, 1)])])
		(x, y, z) = GAME.position
		self.assertFalse(window.IsOutOfRange())

		GAME.position = (x + 1000, y - 1000, z)
		self.assertFalse(window.IsOutOfRange())
		window.OnUpdate()
		self.assertTrue(window.shown)
		self.assertEqual(0, GAME.closes)

		GAME.position = (x - 1001, y, z)
		self.assertTrue(window.IsOutOfRange())
		window.OnUpdate()
		self.assertFalse(window.shown)
		self.assertEqual(1, GAME.closes)
		self.assertFalse(window.IsOutOfRange(), "a closed window is in no range")

		# Opened again, it measures from there.
		window.Open()
		self.assertFalse(window.IsOutOfRange())
		GAME.position = (x - 1001, y + 1001, z)
		window.OnUpdate()
		self.assertFalse(window.shown)
		self.assertEqual(2, GAME.closes)

		# The server closing it ends the watch too.
		window.Open()
		window.BINARY_CUBE_RENEWAL_CLOSE()
		GAME.position = (x, y, z)
		self.assertFalse(window.IsOutOfRange())

	## Closing

	def test_the_player_closing_tells_the_server_and_the_server_closing_does_not(self):
		window = self.Open([Recipe(PEARL, materials=[(ORE, 1)])])
		window.SelectObject(0)
		self.Child("button_cancel").Click()
		self.assertEqual(1, GAME.closes)
		self.assertFalse(window.shown)
		self.assertIsNone(window.GetSelectedRecipe())
		self.assertEqual({}, self.Child("icons_items").slots)
		self.assertFalse(self.Child("result_qty").shown)
		self.assertFalse(self.Row(2, 0).selectBar.shown)

		window.Open()
		self.assertTrue(window.OnPressEscapeKey())
		self.assertEqual(2, GAME.closes)

		window.Open()
		self.Child("board").closeEvent()
		self.assertEqual(3, GAME.closes)

		window.Open()
		self.Child("result_qty").eventEscape()
		self.assertEqual(4, GAME.closes)

		window.Open()
		window.SelectObject(0)
		self.Child("button_ok").Click()
		window.BINARY_CUBE_RENEWAL_CLOSE()
		self.assertEqual(4, GAME.closes)
		self.assertFalse(window.shown)
		self.assertIsNone(window.GetSelectedRecipe())

	def test_closing_closes_an_open_question(self):
		window = self.Open([Recipe(PEARL, materials=[(GEM, 2)], ranged=True)])
		Own(0, GEM + 1, 1)
		window.SelectObject(0)
		self.Child("button_ok").Click()
		dialog = sys.modules["uiCommon"].QuestionDialog.opened[-1]
		self.assertTrue(dialog.isOpen)
		window.BINARY_CUBE_RENEWAL_CLOSE()
		self.assertFalse(dialog.isOpen)

	def test_a_new_list_resets_the_tree_and_the_selection(self):
		window = self.Open([Recipe(PEARL, materials=[(ORE, 1)], category="UPMATS")])
		window.ToggleCategory("UPMATS")
		window.SelectObject(0)
		GAME.recipes = [Recipe(GEM, materials=[(ORE, 1)], category="GEMS")]
		window.BINARY_CUBE_RENEWAL_LOADING()
		self.assertIsNone(window.GetSelectedRecipe())
		self.assertEqual([(0, "GEMS")], self.ShownRowKeys())
		self.assertEqual("Temporary Gems", self.Row(0, "GEMS").text.text)
		self.assertNotIn((0, "UPMATS"), window.rows)


class Permissive(types.ModuleType):
	"""A C++ module stand-in whose every function does nothing and returns 0."""

	def __getattr__(self, name):
		if name.startswith("__"):
			raise AttributeError(name)
		return lambda *args: 0


class FakeWndMgr(Permissive):
	"""wndMgr with just enough state for the real ui.py: handles, sizes, positions, shown, text."""

	def __init__(self):
		Permissive.__init__(self, "wndMgr")
		self.windows = {}

	def __getattr__(self, name):
		if name.startswith("Register"):
			return self.Register
		return Permissive.__getattr__(self, name)

	def Register(self, obj, layer="UI"):
		handle = len(self.windows) + 1
		self.windows[handle] = {"obj" : obj, "shown" : False, "size" : (0, 0), "position" : (0, 0), "text" : ""}
		return handle

	def Show(self, handle):
		self.windows[handle]["shown"] = True

	def Hide(self, handle):
		self.windows[handle]["shown"] = False

	def IsShow(self, handle):
		return self.windows[handle]["shown"]

	def SetWindowSize(self, handle, width, height):
		self.windows[handle]["size"] = (width, height)

	def GetWindowWidth(self, handle):
		return self.windows[handle]["size"][0]

	def GetWindowHeight(self, handle):
		return self.windows[handle]["size"][1]

	def SetWindowPosition(self, handle, x, y):
		self.windows[handle]["position"] = (x, y)

	def GetWindowLocalPosition(self, handle):
		return self.windows[handle]["position"]

	def SetText(self, handle, text):
		self.windows[handle]["text"] = text

	def GetText(self, handle):
		return self.windows[handle]["text"]

	def GetTextSize(self, handle):
		return (6 * len(self.windows[handle]["text"]), 12)

	def GetScreenWidth(self):
		return 1920

	def GetScreenHeight(self):
		return 1080


class RealWidgetsTest(unittest.TestCase):
	"""The window on the client's own ui.py and its uiscript loader (wndMgr and the
	other C++ modules stood in for), so a call to a widget method ui.py lacks fails."""

	def setUp(self):
		global GAME
		GAME = Game()
		IsolateModules(self)
		modules = MakeModules()
		for name in ("ime", "snd", "skill", "dbg", "guild", "chr"):
			modules[name] = Permissive(name)
		modules["chr"].PLAYER_NAME_MAX_LEN = 24
		modules["app"] = Permissive("app")
		modules["app"].GetTime = lambda: GAME.time
		modules["app"].IsRTL = lambda: False
		modules["app"].GetLocalePath = lambda: "locale/en"
		modules["app"].GetLocalePathCommon = lambda: "locale/common"
		modules["player"].DRAGON_SOUL_EQUIPMENT_SLOT_START = 0
		modules["item"].GetIconImage = lambda: 0
		modules["item"].GetItemSize = lambda: (1, 1)
		self.wndMgr = FakeWndMgr()
		modules["wndMgr"] = self.wndMgr
		sys.modules.update(modules)

		# The client's interpreter has these built in; ui.py uses them.
		import builtins
		self.addedBuiltins = [name for name in ("TRUE", "FALSE") if not hasattr(builtins, name)]
		builtins.TRUE = True
		builtins.FALSE = False

		spec = importlib.util.spec_from_file_location("ui", os.path.join(ROOT, "ui.py"))
		ui = importlib.util.module_from_spec(spec)
		sys.modules["ui"] = ui
		spec.loader.exec_module(ui)

		spec = importlib.util.spec_from_file_location("uiCubeRenewal", os.path.join(ROOT, "uicuberenewal.py"))
		self.cube = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(self.cube)

		Proto(SWORD5, "Sword+5", ITEM_TYPE_WEAPON, 0)
		Proto(SWORD6, "Sword+6", ITEM_TYPE_WEAPON, 0, restricted=True)
		Proto(ORE, "Ore", stackable=True)
		Proto(GEM, "Gem", stackable=True)
		for vnum in range(GEM + 1, GEM + 10):
			Proto(vnum, "Gem %d" % vnum, stackable=True)

	def tearDown(self):
		import builtins
		for name in self.addedBuiltins:
			delattr(builtins, name)

	def test_the_window_runs_on_the_real_ui_module(self):
		GAME.recipes = [Recipe(SWORD6, materials=[(SWORD5, 1), (ORE, 2)], gold=100, category="WEAPON", allowCopy=SWORD5)]
		GAME.recipes += [Recipe(GEM + i % 10, count=2, materials=[(GEM + j, 1) for j in range(7)], category="GEMS") for i in range(20)]
		Own(0, SWORD5, 1, attrs=[(72, 5)] * ATTRIBUTE_SLOT_MAX_NUM)
		Own(1, ORE, 9)
		GAME.noCopy.add((0, 5))

		# ui.py's loader opens the uiscript by its relative path and leaves the
		# file to the collector (the client's open reads from the packs).
		cwd = os.getcwd()
		os.chdir(UISCRIPT)
		try:
			with warnings.catch_warnings():
				warnings.simplefilter("ignore", ResourceWarning)
				window = self.cube.CubeRenewalWindow()
				window.LoadWindow()
				gc.collect()
		finally:
			os.chdir(cwd)

		tooltip = FakeToolTip()
		window.SetItemToolTip(tooltip)
		window.BINARY_CUBE_RENEWAL_LOADING()
		window.Open()
		self.assertTrue(window.IsShow())
		self.assertEqual(12, window.visibleRowCount)

		window.ToggleCategory("GEMS")
		for i in range(10):
			window.ToggleReward(("GEMS", GEM + i))
		self.assertTrue(window.scrollBar.IsShow())
		window.OnScroll()

		window.ToggleCategory("WEAPON")
		window.ToggleReward(("WEAPON", SWORD6))
		window.SelectObject(0)
		self.assertEqual("1/1", window.materialTexts[0].GetText())
		self.assertEqual("9/2", window.materialTexts[1].GetText())
		window.OverInItem(0)
		self.assertEqual(SWORD6, tooltip.shown[0])
		window.OverOutItem()

		window.AcceptCube()
		dialog = sys.modules["uiCommon"].QuestionDialog.opened[-1]
		dialog.accept()
		self.assertEqual([(0, 1)], GAME.made)

		window.SelectObject(1)
		window.NextMaterialPage()
		window.result_qty.SetText("9")
		window.AcceptInputItem()
		self.assertEqual("8", window.result_qty.GetText())
		window.QtyAddButton()
		window.QtySubButton()
		window.button_ok.CallEvent()
		self.assertEqual([(0, 1), (1, 1)], GAME.made)

		window.OnPressEscapeKey()
		self.assertEqual(1, GAME.closes)
		self.assertFalse(window.IsShow())
		window.Destroy()
		self.assertIsNone(GAME.handler)


class WiringTest(unittest.TestCase):

	def Functions(self, path, className):
		tree = ast.parse(ReadText(path))
		for node in tree.body:
			if isinstance(node, ast.ClassDef) and node.name == className:
				return dict((f.name, ast.unparse(f)) for f in node.body if isinstance(f, ast.FunctionDef))
		self.fail("%s not in %s" % (className, path))

	def test_game_and_the_interface_forward_the_entry_points(self):
		game = self.Functions(os.path.join(ROOT, "game.py"), "GameWindow")
		self.assertIn("self.interface.BINARY_CUBE_RENEWAL_OPEN()", game["BINARY_CUBE_RENEWAL_OPEN"])
		self.assertIn("self.interface.BINARY_CUBE_RENEWAL_CLOSE()", game["BINARY_CUBE_RENEWAL_CLOSE"])

		interface = self.Functions(os.path.join(ROOT, "interfacemodule.py"), "Interface")
		self.assertIn("self.wndCubeRenewal.Open()", interface["BINARY_CUBE_RENEWAL_OPEN"])
		self.assertIn("self.wndCubeRenewal.BINARY_CUBE_RENEWAL_CLOSE()", interface["BINARY_CUBE_RENEWAL_CLOSE"])
		self.assertIn("self.wndCubeRenewal.Refresh()", interface["RefreshInventory"])
		# A point change touches only the cost.
		self.assertIn("self.wndCubeRenewal.RefreshCost()", interface["RefreshStatus"])
		self.assertNotIn("self.wndCubeRenewal.Refresh()", interface["RefreshStatus"])
		# Nothing in the window reads the interface (OLD's BindInterface fed the chest previewer only).
		self.assertNotIn("wndCubeRenewal.BindInterface", ReadText(os.path.join(ROOT, "interfacemodule.py")))
		self.assertNotIn("BindInterface", ReadText(os.path.join(ROOT, "uicuberenewal.py")))
		self.assertIn("self.wndCubeRenewal.SetItemToolTip(self.tooltipItem)", interface["MakeInterface"])
		self.assertIn("self.wndCubeRenewal.Destroy()", interface["Close"])

	def test_the_legacy_cube_is_gone(self):
		for name in ("uicube.py",):
			self.assertFalse(os.path.exists(os.path.join(ROOT, name)))
		for name in ("cubewindow.py", "cuberesultwindow.py"):
			self.assertFalse(os.path.exists(os.path.join(UISCRIPT, "uiscript", name)))
		for name in ("game.py", "interfacemodule.py"):
			source = ReadText(os.path.join(ROOT, name))
			for legacy in ("uiCube.", "BINARY_Cube_", "cubeInformation", "wndCube.", "wndCubeResult", "/cube "):
				self.assertNotIn(legacy, source, "%s in %s" % (legacy, name))


class LocaleTest(unittest.TestCase):

	def setUp(self):
		IsolateModules(self)

	def test_every_locale_has_the_window_s_strings(self):
		module = LoadWindowModule()
		locales = [d for d in sorted(os.listdir(LOCALES)) if os.path.exists(os.path.join(LOCALES, d, "locale_game.txt"))]
		self.assertEqual(17, len(locales))
		for locale in locales:
			game = ReadLocaleFile(os.path.join(LOCALES, locale, "locale_game.txt"))
			interface = ReadLocaleFile(os.path.join(LOCALES, locale, "locale_interface.txt"))
			for (category, key) in module.CATEGORIES:
				self.assertTrue(game.get(key), "%s: %s" % (locale, key))
			self.assertEqual(1, game["ITEM_HAS_RESTRICTED_BONUS"].count("%s"), locale)
			self.assertEqual(2, game["CUBE_RENEWAL_RANGED_CONFIRM"].count("%s"), locale)
			self.assertEqual(2, game["CUBE_RENEWAL_RANGED_CONFIRM"].count("%"), locale)
			# The title is the cube's, translated everywhere.
			self.assertTrue(interface.get("CUBE_TITLE"), locale)
			self.assertNotIn("CUBE_RENEWAL_TITLE", interface, locale)
			self.assertNotIn("TOOLTIP_CUBE_KEEPS_BONUSES_AND_STONES", game, locale)

	def test_old_s_translations_where_old_had_them(self):
		self.assertEqual("Veredelungsfenster", ReadLocaleFile(os.path.join(LOCALES, "de", "locale_interface.txt"))["CUBE_TITLE"])
		self.assertEqual("Waffen", ReadLocaleFile(os.path.join(LOCALES, "de", "locale_game.txt"))["CUBE_CATEGORY_WEAPONS"])
		self.assertEqual("Belt", ReadLocaleFile(os.path.join(LOCALES, "de", "locale_game.txt"))["CUBE_CATEGORY_BELT"])
		self.assertEqual("Weapons", ReadLocaleFile(os.path.join(LOCALES, "fr", "locale_game.txt"))["CUBE_CATEGORY_WEAPONS"])


if __name__ == "__main__":
	unittest.main()
