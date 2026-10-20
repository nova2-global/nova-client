import app
import grp
import item
import player
import ui
import localeInfo
import uiCommon
import uiToolTip
import cube_renewal

## Limits. The wire contract's values come from cube_renewal.
SLOTS_PER_PAGE = 5						# material slots shown at once; materials 6 to 10 are on the next page.
										# The uiscript lays out as many (its MATERIAL_SLOT_COUNT; LoadWindow checks).
MATERIAL_MAX = cube_renewal.MATERIAL_MAX	# materials per recipe
QUANTITY_MAX = cube_renewal.QUANTITY_MAX	# reward count x multiplier, at most (the server checks it too)
MAX_DISTANCE = cube_renewal.MAX_DISTANCE	# the server's CUBE_MAX_DISTANCE: the window closes past it
RESULT_SLOT = 0
FIRST_MATERIAL_SLOT = 1
RANGED_CYCLE_SECONDS = 1.5				# a ranged recipe's material slot shows the range's items in turn
COPY_FROM_FIRST_MATERIAL = 1				# allow_copy 1; any other non-zero value is the vnum to copy from

## The cube_renewal.GetDates(index) tuple (its docstring has the full list).
DATES_REWARD_VNUM = 0
DATES_REWARD_COUNT = 1
DATES_REWARD_STACKABLE = 2
DATES_FIRST_MATERIAL = 3					# then vnum, count for each of the MATERIAL_MAX materials
DATES_MATERIAL_FIELDS = 2
DATES_GOLD = DATES_FIRST_MATERIAL + DATES_MATERIAL_FIELDS * MATERIAL_MAX
DATES_PERCENT = DATES_GOLD + 1
DATES_CATEGORY = DATES_GOLD + 2
DATES_GEM = DATES_GOLD + 3
DATES_ALLOW_COPY = DATES_GOLD + 4
DATES_ITEM_RANGED = DATES_GOLD + 5

## OLD's categories, in OLD's order: the name cube.txt gives a recipe, and the locale key of its label.
## A recipe whose category is not listed goes under OTHERS.
CATEGORY_OTHERS = "OTHERS"
CATEGORIES = (
	("WEAPON", "CUBE_CATEGORY_WEAPONS"),
	("ARMOR", "CUBE_CATEGORY_ARMORS"),
	("HELM", "CUBE_CATEGORY_HELMETS"),
	("EAR", "CUBE_CATEGORY_EARRINGS"),
	("NECK", "CUBE_CATEGORY_NECKLACE"),
	("BRAC", "CUBE_CATEGORY_BRACELET"),
	("SHOES", "CUBE_CATEGORY_SHOES"),
	("SHIELD", "CUBE_CATEGORY_SHIELD"),
	("UPMATS", "CUBE_CATEGORY_UPGRADE_MATERIALS"),
	("CORES", "CUBE_CATEGORY_CRAFTING_CORES"),
	("COSTUME_ARMOR", "CUBE_CATEGORY_BODY_COSTUME"),
	("COSTUME_HAIR", "CUBE_CATEGORY_HAIR_COSTUME"),
	("COSTUME_WEAPON", "CUBE_CATEGORY_WEAPON_COSTUME"),
	("COSTUME_MOUNT", "CUBE_CATEGORY_MOUNT_COSTUME"),
	("COSTUME_PET", "CUBE_CATEGORY_PET_COSTUME"),
	("COSTUME_WING", "CUBE_CATEGORY_WING_COSTUME"),
	("COSTUME_FACIAL", "CUBE_CATEGORY_FACIAL_COSTUME"),
	("COSTUME_BODY_EFFECT", "CUBE_CATEGORY_BODY_EFFECT"),
	("COSTUME_WEAPON_EFFECT", "CUBE_CATEGORY_WEAPON_EFFECT"),
	("DISMANTLE_SPECIAL_1", "CUBE_CATEGORY_DISMANTLE_SPECIAL_COSTUME"),
	("DISMANTLE_SPECIAL_2", "CUBE_CATEGORY_DISMANTLE_SPECIAL_HAIR"),
	("DISMANTLE_SPECIAL_3", "CUBE_CATEGORY_DISMANTLE_SPECIAL_WEAPON"),
	("DISMANTLE_SPECIAL_4", "CUBE_CATEGORY_DISMANTLE_SPECIAL_PET"),
	("DISMANTLE_PLUS_1", "CUBE_CATEGORY_DISMANTLE_PLUS_COSTUME"),
	("DISMANTLE_PLUS_2", "CUBE_CATEGORY_DISMANTLE_PLUS_HAIR"),
	("DISMANTLE_PLUS_3", "CUBE_CATEGORY_DISMANTLE_PLUS_WEAPON"),
	("DISMANTLE_PLUS_4", "CUBE_CATEGORY_DISMANTLE_PLUS_PET"),
	("XMAS_WORKSHOP", "CUBE_CATEGORY_SANTAS_WORKSHOP"),
	("SKIN_CONVERT", "CUBE_CATEGORY_SKIN_CONVERSION_TEMPORARY_OPTION"),
	("SEAL_PET", "CUBE_CATEGORY_PET_SEAL"),
	("SEAL_MOUNT", "CUBE_CATEGORY_MOUNT_SEAL"),
	("PET_ADVANCED", "CUBE_CATEGORY_ADVANCED_PET_ITEMS"),
	("GEMS", "CUBE_CATEGORY_TEMPORARY_GEMS"),
	("PERM_GEMS", "CUBE_CATEGORY_PERMANENT_GEMS"),
	("BELT", "CUBE_CATEGORY_BELT"),
	("AURA_BONUS", "CUBE_CATEGORY_AURA_BONUS"),
	("AURA_LEVEL", "CUBE_CATEGORY_AURA_LEVEL"),
	(CATEGORY_OTHERS, "CUBE_CATEGORY_OTHERS"),
)
CATEGORY_LABEL_KEYS = dict(CATEGORIES)

## The tree's three levels: category > reward > recipe.
LEVEL_CATEGORY = 0
LEVEL_REWARD = 1
LEVEL_RECIPE = 2

## Row layout in the list (item_list_board), as OLD placed its rows.
ROW_LEFT = 6
ROW_TOP = 8
ROW_STEP = 20
ROW_HEIGHT = 17
ROW_INDENT = (0, 15, 35)					# per level
ROW_TEXT_Y = 2
ROW_ICON_POSITION = (7, 1)
ROW_ICON_TEXT_X = 25						# category and reward rows: the text after the open/closed icon
ROW_RECIPE_TEXT_X = 17					# a recipe row's text when it has no "[N]"
ROW_COUNT_TEXT_X = 16					# the "[N]"; the text then starts ROW_COUNT_GAP after it
ROW_COUNT_GAP = 4

ROW_ICON_OPEN = "d:/ymir work/ui/game/windows/messenger_list_open.sub"
ROW_ICON_CLOSED = "d:/ymir work/ui/game/windows/messenger_list_close.sub"

## Colours (OLD's)
ROW_COLORS = (0xffeace96, 0xffa28b5f, 0xff976868)	# per level
ENOUGH_COLOR = grp.GenerateColor(0.5411, 0.7254, 0.5568, 1.0)
MISSING_COLOR = grp.GenerateColor(0.9, 0.4745, 0.4627, 1.0)
COST_COLOR = grp.GenerateColor(0.7607, 0.7607, 0.7607, 1.0)
ROW_SELECT_COLOR = ui.SELECT_COLOR
ROW_OVER_COLOR = ui.HALF_WHITE_COLOR

## Number formats (no words in them; every word comes from the locale files)
CRAFTABLE_FORMAT = "[%d]"
RECIPE_NAME_FORMAT = "%s (%d%%)"
MATERIAL_COUNT_FORMAT = "%d/%d"
NUMBER_FORMAT = "%d"


class CubeRenewalListItem(ui.Window):
	"""One row of the recipe tree: a category, a reward or a recipe.

	A press calls event(level, key). Category and reward rows show whether they
	are open; a recipe row shows the "[N]" the player can craft in green before
	its name.
	"""

	def __init__(self, parent, level, key, event):
		self.overBar = None		# ui.Window.__init__ calls Hide()
		ui.Window.__init__(self)
		self.SetParent(parent)

		self.level = level
		self.key = key
		self.event = event
		self.isOpen = None
		self.craftableText = ""

		self.overBar = self.__MakeBar(ROW_OVER_COLOR)
		self.selectBar = self.__MakeBar(ROW_SELECT_COLOR)

		self.icon = None
		if LEVEL_RECIPE != level:
			self.icon = ui.ImageBox()
			self.icon.SetParent(self)
			self.icon.AddFlag("not_pick")
			self.icon.SetPosition(*ROW_ICON_POSITION)
			self.icon.Show()

		self.countText = None
		if LEVEL_RECIPE == level:
			self.countText = ui.TextLine()
			self.countText.SetParent(self)
			self.countText.AddFlag("not_pick")
			self.countText.SetPosition(ROW_COUNT_TEXT_X, ROW_TEXT_Y)
			self.countText.SetPackedFontColor(ENOUGH_COLOR)
			self.countText.Hide()

		self.text = ui.TextLine()
		self.text.SetParent(self)
		self.text.AddFlag("not_pick")
		self.text.SetPackedFontColor(ROW_COLORS[level])
		self.text.SetPosition(ROW_RECIPE_TEXT_X if LEVEL_RECIPE == level else ROW_ICON_TEXT_X, ROW_TEXT_Y)
		self.text.Show()

		self.SetSize(0, ROW_HEIGHT)

	def __del__(self):
		ui.Window.__del__(self)

	def __MakeBar(self, color):
		bar = ui.Bar()
		bar.SetParent(self)
		bar.AddFlag("not_pick")
		bar.SetColor(color)
		bar.Hide()
		return bar

	# A row scrolled out under the pointer gets no OnMouseOverOut.
	def Hide(self):
		if self.overBar:
			self.overBar.Hide()
		ui.Window.Hide(self)

	def SetWidth(self, width):
		self.SetSize(width, ROW_HEIGHT)
		self.overBar.SetSize(width, ROW_HEIGHT)
		self.selectBar.SetSize(width, ROW_HEIGHT)

	def SetName(self, name):
		self.text.SetText(name)

	def SetOpen(self, isOpen):
		if not self.icon or isOpen == self.isOpen:
			return

		self.isOpen = isOpen
		self.icon.LoadImage(ROW_ICON_OPEN if isOpen else ROW_ICON_CLOSED)

	# The "[N]" before a recipe's name, empty when it cannot be crafted.
	def SetCraftableText(self, text):
		if not self.countText or text == self.craftableText:
			return

		self.craftableText = text
		if not text:
			self.countText.Hide()
			self.text.SetPosition(ROW_RECIPE_TEXT_X, ROW_TEXT_Y)
			return

		self.countText.SetText(text)
		self.countText.Show()
		(width, height) = self.countText.GetTextSize()
		self.text.SetPosition(ROW_COUNT_TEXT_X + width + ROW_COUNT_GAP, ROW_TEXT_Y)

	def SetSelected(self, isSelected):
		if isSelected:
			self.selectBar.Show()
		else:
			self.selectBar.Hide()

	def OnMouseOverIn(self):
		self.overBar.Show()

	def OnMouseOverOut(self):
		self.overBar.Hide()

	def OnMouseLeftButtonDown(self):
		self.event(self.level, self.key)
		return True


class CubeRenewalWindow(ui.ScriptWindow):
	"""The cube (refinement) window, OLD's uiCubeRenewal (NOVA-14).

	The server sends the recipes of the cube NPC the player talked to; the C++
	module cube_renewal keeps them and calls BINARY_CUBE_RENEWAL_LOADING() on this
	window (registered as its handler) once the list is complete, then game.py's
	BINARY_CUBE_RENEWAL_OPEN() opens it. The tree lists the categories in the
	order they first appear, under each its rewards, under each its recipes with
	"[N]" (how many the player can craft now) and the success chance. A recipe
	shows its result and materials (five per page), what the player has of each,
	the yang (and later gaya) cost and the quantity to craft; OK sends
	cube_renewal.CubeRenewalMakeItem(index, multiplier) once the player said yes
	to every question GetAcceptQuestions() has. The server answers in the chat
	and with item and gold updates, which reach Refresh() through the
	interface's RefreshInventory, and RefreshCost() through its RefreshStatus.

	The methods under "Recipe data" only compute and return data from
	cube_renewal, player and item and the window's state (the list, the
	selection, the page, the open tree nodes, where the cube opened); they touch
	no widget, so a subclass with other widgets can use them as they are.
	Refresh() recomputes what the inventory, the selection, the page and the
	quantity change, RefreshCost() what the gold changes, RefreshList() lays the
	tree's rows out (LIST_ITEM_CLASS makes them). Per frame, OnUpdate runs only
	IsOutOfRange() (the window closes once the player walks away) and the ranged
	recipe's 1.5 s timer.
	"""

	LIST_ITEM_CLASS = CubeRenewalListItem

	def __init__(self):
		ui.ScriptWindow.__init__(self)

		self.tooltipItem = None
		self.questionDialog = None
		self.pendingQuestions = []
		self.openPosition = None

		self.recipes = []
		self.tree = []
		self.showGem = False
		self.openCategories = set()
		self.openRewards = set()

		self.rows = {}
		self.visibleRows = []
		self.shownRows = []
		self.startLine = 0
		self.visibleRowCount = 1
		self.isSettingScroll = False

		self.selectedIndex = -1
		self.pageIndex = 0
		self.quantity = 0
		self.rangedIndex = 0
		self.nextIconChange = 0.0
		self.overSlot = -1

		cube_renewal.SetCubeRenewalHandler(self)

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def LoadWindow(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "uiscript/cuberenewalwindow.py")
		except:
			import exception
			exception.Abort("CubeRenewalWindow.LoadWindow.LoadObject")

		try:
			GetObject = self.GetChild
			self.board = GetObject("item_list_board")
			self.scrollBar = GetObject("list_scroll_bar")
			self.icons_items = GetObject("icons_items")
			self.result_qty = GetObject("result_qty")
			self.qty_sub_button = GetObject("qty_sub_button")
			self.qty_add_button = GetObject("qty_add_button")
			self.nextButton = GetObject("next_button")
			self.backButton = GetObject("back_button")
			self.yang_text = GetObject("yang_text")
			self.gemWidgets = (GetObject("gem_icon"), GetObject("gem_textbg"))
			self.gem_text = GetObject("gem_text")
			self.button_ok = GetObject("button_ok")
			self.button_cancel = GetObject("button_cancel")
			self.materialTexts = [GetObject("material_qty_text_%d" % (i + 1)) for i in range(SLOTS_PER_PAGE)]
			GetObject("board").SetCloseEvent(ui.__mem_func__(self.Close))
		except:
			import exception
			exception.Abort("CubeRenewalWindow.LoadWindow.BindObject")

		# The paging and the data methods count on the uiscript's slots.
		if pyScrLoader.ScriptDictionary.get("MATERIAL_SLOT_COUNT") != SLOTS_PER_PAGE:
			import exception
			exception.Abort("CubeRenewalWindow.LoadWindow.MaterialSlotCount")

		self.button_ok.SetEvent(ui.__mem_func__(self.AcceptCube))
		self.button_cancel.SetEvent(ui.__mem_func__(self.Close))
		self.qty_sub_button.SetEvent(ui.__mem_func__(self.QtySubButton))
		self.qty_add_button.SetEvent(ui.__mem_func__(self.QtyAddButton))
		self.nextButton.SetEvent(ui.__mem_func__(self.NextMaterialPage))
		self.backButton.SetEvent(ui.__mem_func__(self.PrevMaterialPage))
		self.result_qty.SetReturnEvent(ui.__mem_func__(self.AcceptInputItem))
		self.result_qty.SetEscapeEvent(ui.__mem_func__(self.Close))
		self.result_qty.SetIMEFlag(False)
		self.scrollBar.SetScrollEvent(ui.__mem_func__(self.OnScroll))
		self.icons_items.SetOverInItemEvent(ui.__mem_func__(self.OverInItem))
		self.icons_items.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))

		self.visibleRowCount = max(1, (self.board.GetHeight() - ROW_TOP) // ROW_STEP)
		self.scrollBar.Hide()
		self.__ShowGemWidgets()
		self.__ClearSelectionWidgets()

	def SetItemToolTip(self, tooltipItem):
		self.tooltipItem = tooltipItem

	def Destroy(self):
		# Only while it is this window: the next game phase's window may have
		# registered already (cube_renewal also lets go when the phase ends).
		if cube_renewal.GetCubeRenewalHandler() is self:
			cube_renewal.SetCubeRenewalHandler(None)
		self.__CloseQuestionDialog()
		self.__ClearRows()
		self.ClearDictionary()

		self.tooltipItem = None
		self.board = None
		self.scrollBar = None
		self.icons_items = None
		self.result_qty = None
		self.qty_sub_button = None
		self.qty_add_button = None
		self.nextButton = None
		self.backButton = None
		self.yang_text = None
		self.gemWidgets = ()
		self.gem_text = None
		self.button_ok = None
		self.button_cancel = None
		self.materialTexts = []

	###############################################################################
	## Recipe data (no widgets)

	def ReadRecipe(self, index, dates):
		"""Recipe `index` from its cube_renewal.GetDates(index) tuple, as a dict:

			"index"            int   its position in the server's list: what
			                         CubeRenewalMakeItem takes
			"reward_vnum"      int   the item it makes
			"reward_count"     int   items one craft makes
			"reward_stackable" bool  the reward stacks, so one request may craft
			                         it more than once
			"materials"        list  of (vnum, count) tuples, what one craft
			                         takes, in the server's order; a material
			                         whose vnum is 0 (unused) is dropped, so the
			                         list has 0 to MATERIAL_MAX entries. In a
			                         ranged recipe each is (first vnum, length)
			                         instead: any one item of first ..
			                         first + length - 1 (see "item_ranged")
			"gold"             int   yang one craft costs
			"percent"          int   the chance of a craft to succeed, 0-100
			"category"         str   the server's category name, e.g. "ARMOR"
			                         (GetCategoryKey maps the unknown ones)
			"gem"              int   gaya one craft costs (0 until NOVA-10)
			"allow_copy"       int   0 copies nothing; COPY_FROM_FIRST_MATERIAL
			                         copies from the first material owned; any
			                         other value is the vnum copied from (see
			                         FindCopySourceCell)
			"item_ranged"      bool  the materials are ranges, and a craft takes
			                         one item of them: the first one owned
		"""
		materials = []
		for i in range(MATERIAL_MAX):
			field = DATES_FIRST_MATERIAL + DATES_MATERIAL_FIELDS * i
			if dates[field]:
				materials.append((dates[field], dates[field + 1]))

		return {
			"index" : index,
			"reward_vnum" : dates[DATES_REWARD_VNUM],
			"reward_count" : dates[DATES_REWARD_COUNT],
			"reward_stackable" : bool(dates[DATES_REWARD_STACKABLE]),
			"materials" : materials,
			"gold" : dates[DATES_GOLD],
			"percent" : dates[DATES_PERCENT],
			"category" : dates[DATES_CATEGORY],
			"gem" : dates[DATES_GEM],
			"allow_copy" : dates[DATES_ALLOW_COPY],
			"item_ranged" : bool(dates[DATES_ITEM_RANGED]),
		}

	# The recipes in the order the server sent them; a recipe's "index" is what
	# CubeRenewalMakeItem takes. A ranged recipe's materials are (first vnum, range
	# length): owning any one item of a range is enough.
	def LoadRecipes(self):
		return [self.ReadRecipe(index, cube_renewal.GetDates(index)) for index in range(cube_renewal.CountDates())]

	def GetCategoryKey(self, category):
		if category in CATEGORY_LABEL_KEYS:
			return category

		return CATEGORY_OTHERS

	def GetCategoryName(self, category):
		return getattr(localeInfo, CATEGORY_LABEL_KEYS[self.GetCategoryKey(category)], category)

	# [{"category": key, "rewards": [{"vnum": reward, "recipes": [index, ...]}, ...]}, ...]:
	# categories in the order they first appear, in each the rewards in the order
	# they first appear, under each its recipes in list order.
	def BuildTree(self, recipes):
		tree = []
		categoryNodes = {}
		for recipe in recipes:
			category = self.GetCategoryKey(recipe["category"])
			categoryNode = categoryNodes.get(category)
			if categoryNode is None:
				categoryNode = {"category" : category, "rewards" : []}
				categoryNodes[category] = categoryNode
				tree.append(categoryNode)

			rewardNode = None
			for node in categoryNode["rewards"]:
				if node["vnum"] == recipe["reward_vnum"]:
					rewardNode = node
					break

			if rewardNode is None:
				rewardNode = {"vnum" : recipe["reward_vnum"], "recipes" : []}
				categoryNode["rewards"].append(rewardNode)

			rewardNode["recipes"].append(recipe["index"])

		return tree

	# The tree's rows the player sees: (LEVEL_CATEGORY, category),
	# (LEVEL_REWARD, (category, reward vnum)) and (LEVEL_RECIPE, recipe index),
	# under the categories and rewards that are open.
	def GetVisibleRows(self):
		rows = []
		for categoryNode in self.tree:
			category = categoryNode["category"]
			rows.append((LEVEL_CATEGORY, category))
			if category not in self.openCategories:
				continue

			for rewardNode in categoryNode["rewards"]:
				rewardKey = (category, rewardNode["vnum"])
				rows.append((LEVEL_REWARD, rewardKey))
				if rewardKey not in self.openRewards:
					continue

				for index in rewardNode["recipes"]:
					rows.append((LEVEL_RECIPE, index))

		return rows

	def GetSelectedRecipe(self):
		if 0 <= self.selectedIndex < len(self.recipes):
			return self.recipes[self.selectedIndex]

		return None

	def IsGemShown(self, recipes):
		for recipe in recipes:
			if recipe["gem"] > 0:
				return True

		return False

	def GetItemName(self, vnum):
		item.SelectItem(vnum)
		return item.GetItemName()

	def GetRecipeName(self, recipe):
		return RECIPE_NAME_FORMAT % (self.GetItemName(recipe["reward_vnum"]), recipe["percent"])

	# A ranged recipe's items are its ranges one after the other, in recipe
	# order (up to MATERIAL_MAX ranges of up to 65535 items each): they are
	# never listed, only counted, indexed and looked up.

	# How many items a ranged recipe's ranges hold together.
	def GetRangedLength(self, recipe):
		return sum(length for (vnum, length) in recipe["materials"])

	# The item at `position` of a ranged recipe's ranges, or 0 past their end.
	def GetRangedVnum(self, recipe, position):
		for (vnum, length) in recipe["materials"]:
			if 0 <= position < length:
				return vnum + position

			position -= length

		return 0

	# The position of `vnum` in a ranged recipe's ranges (its first one), or -1
	# when it is in none of them.
	def GetRangedPosition(self, recipe, vnum):
		position = 0
		for (first, length) in recipe["materials"]:
			if first <= vnum < first + length:
				return position + vnum - first

			position += length

		return -1

	# (cell, vnum, count) of every item in the inventory, lowest cell first.
	def GetInventoryItems(self):
		items = []
		for cell in range(player.INVENTORY_PAGE_SIZE * player.INVENTORY_PAGE_COUNT):
			vnum = player.GetItemIndex(cell)
			if vnum:
				items.append((cell, vnum, player.GetItemCount(cell)))

		return items

	# The item of a ranged recipe's ranges the server takes: the first one, in
	# the ranges' order, the player owns; or 0.
	def GetRangedOwnedVnum(self, recipe):
		owned = None
		for (cell, vnum, count) in self.GetInventoryItems():
			position = self.GetRangedPosition(recipe, vnum)
			if position >= 0 and (owned is None or position < owned[0]):
				owned = (position, vnum)

		if owned is None:
			return 0

		return owned[1]

	# How many times the player's materials make the recipe (gold aside, as OLD).
	# A ranged recipe takes one item of its ranges each time.
	def GetCraftableCount(self, recipe):
		if recipe["item_ranged"]:
			return sum(count for (cell, vnum, count) in self.GetInventoryItems() if self.GetRangedPosition(recipe, vnum) >= 0)

		counts = [player.GetItemCountByVnum(vnum) // count for (vnum, count) in recipe["materials"] if count > 0]
		if not counts:
			return 0

		return min(counts)

	# "[N]", N the reward items the player can craft now, or "" when none.
	def GetCraftableText(self, recipe):
		count = self.GetCraftableCount(recipe)
		if count <= 0:
			return ""

		return CRAFTABLE_FORMAT % (count * recipe["reward_count"])

	# The quantity box's rule: at least the reward count, at most QUANTITY_MAX,
	# a multiple of the reward count. A reward that does not stack, and a ranged
	# recipe (which takes one item whatever the multiplier), make one at a time.
	def ClampQuantity(self, recipe, quantity):
		step = recipe["reward_count"]
		if step <= 0 or not recipe["reward_stackable"] or recipe["item_ranged"]:
			return step

		ceiling = max(step, QUANTITY_MAX - QUANTITY_MAX % step)
		quantity = max(step, min(quantity, ceiling))
		return quantity - quantity % step

	# The "+" button: as many as the materials make.
	def GetMaxQuantity(self, recipe):
		return self.ClampQuantity(recipe, recipe["reward_count"] * self.GetCraftableCount(recipe))

	def ParseQuantity(self, text):
		try:
			return int(text)
		except ValueError:
			return 0

	# The number of crafts sent to the server.
	def GetMultiplier(self, recipe, quantity):
		if recipe["reward_count"] <= 0:
			return 1

		return max(1, quantity // recipe["reward_count"])

	def GetCost(self, recipe, multiplier):
		return (recipe["gold"] * multiplier, recipe["gem"] * multiplier)

	def HasEnoughGold(self, gold):
		return player.GetElk() >= gold

	# NEW has no gaya yet (NOVA-10): no recipe costs any, and none can be paid.
	def HasEnoughGem(self, gem):
		return gem <= 0

	def GetMaterialPageCount(self, recipe):
		if recipe["item_ranged"]:
			return 1

		return max(1, (len(recipe["materials"]) + SLOTS_PER_PAGE - 1) // SLOTS_PER_PAGE)

	# The item a slot shows: the reward in RESULT_SLOT, the page's materials after
	# it; a ranged recipe shows the items of its ranges in turn in its first slot.
	def GetSlotVnum(self, recipe, slotIndex):
		if RESULT_SLOT == slotIndex:
			return recipe["reward_vnum"]

		position = slotIndex - FIRST_MATERIAL_SLOT
		if position < 0 or position >= SLOTS_PER_PAGE:
			return 0

		if recipe["item_ranged"]:
			length = self.GetRangedLength(recipe)
			if 0 != position or length <= 0:
				return 0

			return self.GetRangedVnum(recipe, self.rangedIndex % length)

		materialIndex = self.pageIndex * SLOTS_PER_PAGE + position
		if materialIndex >= len(recipe["materials"]):
			return 0

		return recipe["materials"][materialIndex][0]

	# (vnum, have, need, enough) for each material slot of the page shown.
	# A ranged recipe has one: whether the player owns any item of its ranges.
	def GetMaterialRows(self, recipe, multiplier):
		if recipe["item_ranged"]:
			found = 1 if self.GetRangedOwnedVnum(recipe) else 0
			return [(self.GetSlotVnum(recipe, FIRST_MATERIAL_SLOT), found, 1, found > 0)]

		rows = []
		start = self.pageIndex * SLOTS_PER_PAGE
		for (vnum, count) in recipe["materials"][start:start + SLOTS_PER_PAGE]:
			need = count * multiplier
			have = player.GetItemCountByVnum(vnum)
			rows.append((vnum, have, need, have >= need))

		return rows

	# The inventory cell the server takes an item of this vnum from first (the
	# lowest one holding it), or -1.
	def FindInventoryCell(self, vnum):
		# Unlike the server's FirstSpent it does not skip what the player's own private shop sells: the cube can't open with a shop up.
		for cell in range(player.INVENTORY_PAGE_SIZE * player.INVENTORY_PAGE_COUNT):
			if player.GetItemIndex(cell) == vnum:
				return cell

		return -1

	# The cell whose bonuses and stones the reward gets, or -1: the server's
	# TakeCopy. A ranged recipe copies from the item it takes
	# (GetRangedOwnedVnum), and only when allow_copy is 1 or that item's vnum.
	# Otherwise allow_copy 1 copies from the first material, in recipe order,
	# the player owns, and allow_copy <vnum> from an item of that vnum. In
	# every case the item is the lowest cell holding its vnum, and unless
	# allow_copy is 1 it must be a weapon or an armour of the reward's subtype.
	def FindCopySourceCell(self, recipe):
		allowCopy = recipe["allow_copy"]
		if not allowCopy:
			return -1

		if recipe["item_ranged"]:
			sourceVnum = self.GetRangedOwnedVnum(recipe)
			if not sourceVnum or allowCopy not in (COPY_FROM_FIRST_MATERIAL, sourceVnum):
				return -1
		elif COPY_FROM_FIRST_MATERIAL == allowCopy:
			for (vnum, count) in recipe["materials"]:
				cell = self.FindInventoryCell(vnum)
				if cell >= 0:
					return cell

			return -1
		else:
			sourceVnum = allowCopy

		cell = self.FindInventoryCell(sourceVnum)
		if cell < 0:
			return -1

		if COPY_FROM_FIRST_MATERIAL != allowCopy and not self.IsCopySourceKind(sourceVnum, recipe["reward_vnum"]):
			return -1

		return cell

	# allow_copy <vnum>'s condition on the item copied from: a weapon or an
	# armour of the reward's subtype.
	def IsCopySourceKind(self, sourceVnum, rewardVnum):
		item.SelectItem(sourceVnum)
		if item.GetItemType() not in (item.ITEM_TYPE_WEAPON, item.ITEM_TYPE_ARMOR):
			return False

		sourceSubType = item.GetItemSubType()
		item.SelectItem(rewardVnum)
		return item.GetItemSubType() == sourceSubType

	def GetBlankItemData(self):
		return ([0] * player.METIN_SOCKET_MAX_NUM, [(0, 0)] * player.ATTRIBUTE_SLOT_MAX_NUM)

	def GetItemData(self, cell):
		sockets = [player.GetItemMetinSocket(cell, i) for i in range(player.METIN_SOCKET_MAX_NUM)]
		attrs = [player.GetItemAttribute(cell, i) for i in range(player.ATTRIBUTE_SLOT_MAX_NUM)]
		return (sockets, attrs)

	# The reward as the server will make it: the copy source's stones, and its
	# bonuses but those cube_renewal.CanCopyAttribute says the reward drops.
	# None when the recipe copies nothing or the player has no copy source.
	def GetCopyPreview(self, recipe):
		cell = self.FindCopySourceCell(recipe)
		if cell < 0:
			return None

		(sockets, attrs) = self.GetItemData(cell)
		for i in range(len(attrs)):
			if not cube_renewal.CanCopyAttribute(cell, i, recipe["reward_vnum"]):
				attrs[i] = (0, 0)

		return (sockets, attrs)

	# The first bonus of the copy source the reward will not keep, as
	# (type, value), or None: OK asks the player first (ITEM_HAS_RESTRICTED_BONUS).
	def GetRestrictedBonus(self, recipe):
		if not recipe["allow_copy"]:
			return None

		item.SelectItem(recipe["reward_vnum"])
		if not item.HasBonusRestriction():
			return None

		cell = self.FindCopySourceCell(recipe)
		if cell < 0:
			return None

		for i in range(player.ATTRIBUTE_SLOT_MAX_NUM):
			(attrType, attrValue) = player.GetItemAttribute(cell, i)
			if attrType and not cube_renewal.CanCopyAttribute(cell, i, recipe["reward_vnum"]):
				return (attrType, attrValue)

		return None

	def GetBonusName(self, attrType, attrValue):
		affect = uiToolTip.ItemToolTip.AFFECT_DICT.get(attrType)
		if not affect:
			return ""

		return affect(attrValue)

	# (vnum, sockets, attrs) for a slot's tooltip, or None for an empty slot: the
	# reward with what it copies, a material as the first one the player owns.
	def GetSlotToolTipData(self, recipe, slotIndex):
		vnum = self.GetSlotVnum(recipe, slotIndex)
		if not vnum:
			return None

		if RESULT_SLOT == slotIndex:
			data = self.GetCopyPreview(recipe)
		else:
			cell = self.FindInventoryCell(vnum)
			data = self.GetItemData(cell) if cell >= 0 else None

		if data is None:
			data = self.GetBlankItemData()

		return (vnum, data[0], data[1])

	# The questions OK asks before it crafts, in order, each needing a yes: a
	# bonus of the copy source the reward drops (ITEM_HAS_RESTRICTED_BONUS),
	# then for a ranged recipe the item it takes (CUBE_RENEWAL_RANGED_CONFIRM).
	# Empty: OK crafts at once.
	def GetAcceptQuestions(self, recipe):
		questions = []

		restriction = self.GetRestrictedBonus(recipe)
		if restriction:
			questions.append(localeInfo.ITEM_HAS_RESTRICTED_BONUS % self.GetBonusName(*restriction))

		if recipe["item_ranged"]:
			ownedVnum = self.GetRangedOwnedVnum(recipe)
			if ownedVnum:
				questions.append(localeInfo.CUBE_RENEWAL_RANGED_CONFIRM % (self.GetItemName(recipe["reward_vnum"]), self.GetItemName(ownedVnum)))

		return questions

	def GetPlayerPosition(self):
		(x, y, z) = player.GetMainCharacterPosition()
		return (x, y)

	# Whether the player walked away from where the cube opened: more than
	# MAX_DISTANCE along either axis, as NEW's legacy cube window measured it. The
	# server keeps the cube open (and the player's items locked) until it is
	# told the window closed, and would refuse a craft from there anyway.
	def IsOutOfRange(self):
		if self.openPosition is None:
			return False

		(x, y) = self.GetPlayerPosition()
		(openX, openY) = self.openPosition
		return abs(x - openX) > MAX_DISTANCE or abs(y - openY) > MAX_DISTANCE

	###############################################################################
	## Server events

	# The recipe list is complete (cube_renewal calls it; game.py opens the window next).
	def BINARY_CUBE_RENEWAL_LOADING(self):
		self.__CloseQuestionDialog()
		self.__HideSlotToolTip()

		self.recipes = self.LoadRecipes()
		self.tree = self.BuildTree(self.recipes)
		self.showGem = self.IsGemShown(self.recipes)
		self.openCategories = set()
		self.openRewards = set()
		self.selectedIndex = -1
		self.startLine = 0

		self.__MakeRows()
		self.__ShowGemWidgets()
		self.__ClearSelectionWidgets()
		self.RefreshList()
		self.Refresh()

	def Open(self):
		self.openPosition = self.GetPlayerPosition()
		self.Show()
		self.SetTop()
		self.Refresh()

	# The player closes the cube (or walked away from it): the server is told.
	def Close(self):
		cube_renewal.CubeRenewalClose()
		self.__Hide()

	# The server closed the cube (death, /reload c, a craft from too far away):
	# nothing to send back.
	def BINARY_CUBE_RENEWAL_CLOSE(self):
		self.__Hide()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def __Hide(self):
		self.__CloseQuestionDialog()
		self.__HideSlotToolTip()
		self.__Unselect()
		self.openPosition = None
		self.Hide()

	###############################################################################
	## The tree

	def __ClearRows(self):
		for row in self.rows.values():
			row.Hide()

		self.rows = {}
		self.visibleRows = []
		self.shownRows = []

	def __MakeRows(self):
		self.__ClearRows()

		event = ui.__mem_func__(self.OnSelectItem)
		for categoryNode in self.tree:
			category = categoryNode["category"]
			self.__AddRow(LEVEL_CATEGORY, category, self.GetCategoryName(category), event)

			for rewardNode in categoryNode["rewards"]:
				rewardKey = (category, rewardNode["vnum"])
				self.__AddRow(LEVEL_REWARD, rewardKey, self.GetItemName(rewardNode["vnum"]), event)

				for index in rewardNode["recipes"]:
					self.__AddRow(LEVEL_RECIPE, index, self.GetRecipeName(self.recipes[index]), event)

	def __AddRow(self, level, key, name, event):
		row = self.LIST_ITEM_CLASS(self.board, level, key, event)
		row.SetName(name)
		self.rows[(level, key)] = row

	# A row was pressed: a category or reward opens or closes, a recipe is selected.
	def OnSelectItem(self, level, key):
		if LEVEL_CATEGORY == level:
			self.ToggleCategory(key)
		elif LEVEL_REWARD == level:
			self.ToggleReward(key)
		else:
			self.SelectObject(key)

	def ToggleCategory(self, category):
		if category in self.openCategories:
			self.openCategories.remove(category)
		else:
			self.openCategories.add(category)

		self.RefreshList()

	def ToggleReward(self, rewardKey):
		if rewardKey in self.openRewards:
			self.openRewards.remove(rewardKey)
		else:
			self.openRewards.add(rewardKey)

		self.RefreshList()

	# Lays the visible rows out again after a category or reward opened or closed.
	def RefreshList(self):
		self.visibleRows = self.GetVisibleRows()

		overflow = len(self.visibleRows) - self.visibleRowCount
		if overflow > 0:
			self.startLine = min(self.startLine, overflow)
			self.isSettingScroll = True
			self.scrollBar.SetMiddleBarSize(float(self.visibleRowCount) / len(self.visibleRows))
			self.scrollBar.SetPos(float(self.startLine) / overflow)
			self.isSettingScroll = False
			self.scrollBar.Show()
		else:
			self.startLine = 0
			self.scrollBar.Hide()

		self.__LayoutRows()

	def OnScroll(self):
		if self.isSettingScroll:
			return

		overflow = len(self.visibleRows) - self.visibleRowCount
		if overflow <= 0:
			return

		startLine = int(round(self.scrollBar.GetPos() * overflow))
		if startLine != self.startLine:
			self.startLine = startLine
			self.__LayoutRows()

	def __LayoutRows(self):
		shownRows = self.visibleRows[self.startLine:self.startLine + self.visibleRowCount]

		for rowKey in self.shownRows:
			if rowKey not in shownRows:
				self.rows[rowKey].Hide()

		listWidth = self.board.GetWidth()
		for (position, rowKey) in enumerate(shownRows):
			(level, key) = rowKey
			row = self.rows[rowKey]
			x = ROW_LEFT + ROW_INDENT[level]
			row.SetPosition(x, ROW_TOP + ROW_STEP * position)
			row.SetWidth(listWidth - x)

			if LEVEL_CATEGORY == level:
				row.SetOpen(key in self.openCategories)
			elif LEVEL_REWARD == level:
				row.SetOpen(key in self.openRewards)

			row.Show()

		self.shownRows = shownRows

	###############################################################################
	## The selected recipe

	# Selects a recipe by its index in the list.
	def SelectObject(self, recipeIndex):
		if not 0 <= recipeIndex < len(self.recipes):
			return

		self.__CloseQuestionDialog()
		self.__SetRowSelected(self.selectedIndex, False)
		self.selectedIndex = recipeIndex
		self.__SetRowSelected(recipeIndex, True)

		recipe = self.recipes[recipeIndex]
		self.pageIndex = 0
		self.rangedIndex = 0
		self.nextIconChange = app.GetTime() + RANGED_CYCLE_SECONDS
		self.quantity = recipe["reward_count"]

		self.result_qty.KillFocus()
		self.result_qty.SetText(NUMBER_FORMAT % self.quantity)
		self.result_qty.Show()

		self.Refresh()
		self.__FlashPageButtons()

	def __SetRowSelected(self, recipeIndex, isSelected):
		row = self.rows.get((LEVEL_RECIPE, recipeIndex))
		if row:
			row.SetSelected(isSelected)

	def __Unselect(self):
		self.__SetRowSelected(self.selectedIndex, False)
		self.selectedIndex = -1
		self.pageIndex = 0
		self.quantity = 0
		self.__ClearSelectionWidgets()

	# Shows another page of materials (OLD: five per page).
	def UpdateMaterialSlots(self, pageIndex):
		recipe = self.GetSelectedRecipe()
		if not recipe:
			return

		self.pageIndex = max(0, min(pageIndex, self.GetMaterialPageCount(recipe) - 1))
		self.Refresh()
		self.__FlashPageButtons()

	def NextMaterialPage(self):
		self.UpdateMaterialSlots(self.pageIndex + 1)

	def PrevMaterialPage(self):
		self.UpdateMaterialSlots(self.pageIndex - 1)

	def __FlashPageButtons(self):
		for button in (self.nextButton, self.backButton):
			if button.IsShow():
				button.Flash()

	# Recomputes everything the inventory, the selection, the page and the
	# quantity change: each recipe's "[N]", the selected recipe's slots,
	# have/need counts and costs. Called on those events only, never per frame.
	def Refresh(self):
		if not self.IsShow():
			return

		for recipe in self.recipes:
			row = self.rows.get((LEVEL_RECIPE, recipe["index"]))
			if row:
				row.SetCraftableText(self.GetCraftableText(recipe))

		recipe = self.GetSelectedRecipe()
		if not recipe:
			return

		multiplier = self.GetMultiplier(recipe, self.quantity)
		self.icons_items.SetItemSlot(RESULT_SLOT, recipe["reward_vnum"], self.quantity)

		materialRows = self.GetMaterialRows(recipe, multiplier)
		for i in range(SLOTS_PER_PAGE):
			slotIndex = FIRST_MATERIAL_SLOT + i
			text = self.materialTexts[i]
			if i >= len(materialRows):
				self.icons_items.ClearSlot(slotIndex)
				text.Hide()
				continue

			(vnum, have, need, enough) = materialRows[i]
			self.icons_items.SetItemSlot(slotIndex, vnum, need)
			text.SetText(MATERIAL_COUNT_FORMAT % (have, need))
			text.SetPackedFontColor(ENOUGH_COLOR if enough else MISSING_COLOR)
			text.Show()

		self.RefreshCost()

		pageCount = self.GetMaterialPageCount(recipe)
		self.__ShowIf(self.backButton, self.pageIndex > 0)
		self.__ShowIf(self.nextButton, self.pageIndex + 1 < pageCount)

	# The selected recipe's yang (and gaya) cost, red when the player cannot pay
	# it: all a gold change touches (the interface's RefreshStatus).
	def RefreshCost(self):
		if not self.IsShow():
			return

		recipe = self.GetSelectedRecipe()
		if not recipe:
			return

		(gold, gem) = self.GetCost(recipe, self.GetMultiplier(recipe, self.quantity))
		self.yang_text.SetText(localeInfo.NumberToMoneyString(gold))
		self.yang_text.SetPackedFontColor(COST_COLOR if self.HasEnoughGold(gold) else MISSING_COLOR)
		self.yang_text.Show()

		if self.showGem:
			self.gem_text.SetText(NUMBER_FORMAT % gem)
			self.gem_text.SetPackedFontColor(COST_COLOR if self.HasEnoughGem(gem) else MISSING_COLOR)
			self.gem_text.Show()

	def __ShowIf(self, widget, isShown):
		if isShown:
			widget.Show()
		else:
			widget.Hide()

	def __ClearSelectionWidgets(self):
		self.icons_items.ClearSlot(RESULT_SLOT)
		for i in range(SLOTS_PER_PAGE):
			self.icons_items.ClearSlot(FIRST_MATERIAL_SLOT + i)
			self.materialTexts[i].Hide()

		self.result_qty.KillFocus()
		self.result_qty.Hide()
		self.yang_text.Hide()
		self.gem_text.Hide()
		self.nextButton.Hide()
		self.backButton.Hide()

	def __ShowGemWidgets(self):
		for widget in self.gemWidgets:
			self.__ShowIf(widget, self.showGem)

	# OLD's 1.5 s timer: a ranged recipe's material slot shows the next item of its ranges.
	def UpdateSelectedItemRange(self):
		recipe = self.GetSelectedRecipe()
		if not recipe or not recipe["item_ranged"] or app.GetTime() < self.nextIconChange:
			return

		self.nextIconChange = app.GetTime() + RANGED_CYCLE_SECONDS
		self.rangedIndex += 1
		self.icons_items.SetItemSlot(FIRST_MATERIAL_SLOT, self.GetSlotVnum(recipe, FIRST_MATERIAL_SLOT), 1)
		if FIRST_MATERIAL_SLOT == self.overSlot:
			self.OverInItem(FIRST_MATERIAL_SLOT)

	def OnUpdate(self):
		if self.IsOutOfRange():
			self.Close()
			return

		self.UpdateSelectedItemRange()

	###############################################################################
	## Quantity

	def __SetQuantity(self, recipe, quantity):
		self.quantity = self.ClampQuantity(recipe, quantity)
		self.result_qty.SetText(NUMBER_FORMAT % self.quantity)
		self.Refresh()

	# Enter in the quantity box.
	def AcceptInputItem(self):
		self.result_qty.KillFocus()

		recipe = self.GetSelectedRecipe()
		if recipe:
			self.__SetQuantity(recipe, self.ParseQuantity(self.result_qty.GetText()))

	def QtyAddButton(self):
		self.result_qty.KillFocus()

		recipe = self.GetSelectedRecipe()
		if recipe:
			self.__SetQuantity(recipe, self.GetMaxQuantity(recipe))

	def QtySubButton(self):
		self.result_qty.KillFocus()

		recipe = self.GetSelectedRecipe()
		if recipe:
			self.__SetQuantity(recipe, recipe["reward_count"])

	# OK while the box still has the typed quantity takes it as Enter would.
	def CheckInputFocus(self):
		if self.result_qty.IsFocus():
			self.AcceptInputItem()

	###############################################################################
	## Crafting

	# OK: asks GetAcceptQuestions() one after the other, and crafts after the
	# last yes (at once when there is none). A no ends it.
	def AcceptCube(self):
		recipe = self.GetSelectedRecipe()
		if not recipe:
			return

		self.CheckInputFocus()

		self.__CloseQuestionDialog()
		self.pendingQuestions = self.GetAcceptQuestions(recipe)
		self.__AskNextQuestion()

	# A yes: the next question, or the craft after the last one.
	def __AskNextQuestion(self):
		if not self.pendingQuestions:
			self.AcceptCubeNoCheck()
			return

		self.__OpenQuestionDialog(self.pendingQuestions.pop(0))

	# Crafts the selected recipe without asking.
	def AcceptCubeNoCheck(self):
		self.__CloseQuestionDialog()

		recipe = self.GetSelectedRecipe()
		if not recipe:
			return

		cube_renewal.CubeRenewalMakeItem(recipe["index"], self.GetMultiplier(recipe, self.quantity))

	def __OpenQuestionDialog(self, text):
		if self.questionDialog:
			self.questionDialog.Close()

		questionDialog = uiCommon.QuestionDialog()
		questionDialog.SetText(text)
		questionDialog.SetAcceptEvent(ui.__mem_func__(self.__AskNextQuestion))
		questionDialog.SetCancelEvent(ui.__mem_func__(self.__CloseQuestionDialog))
		questionDialog.Open()
		self.questionDialog = questionDialog

	# Closes the open question, if any, and drops the ones after it.
	def __CloseQuestionDialog(self):
		self.pendingQuestions = []
		if self.questionDialog:
			self.questionDialog.Close()
			self.questionDialog = None

	###############################################################################
	## Tooltips

	def OverInItem(self, slotIndex):
		self.overSlot = slotIndex

		recipe = self.GetSelectedRecipe()
		if not recipe or not self.tooltipItem:
			return

		data = self.GetSlotToolTipData(recipe, slotIndex)
		if not data:
			return

		(vnum, sockets, attrs) = data
		self.tooltipItem.ClearToolTip()
		self.tooltipItem.AddItemData(vnum, sockets, attrs)

	def OverOutItem(self):
		self.overSlot = -1
		if self.tooltipItem:
			self.tooltipItem.HideToolTip()

	# Hides the tooltip only when it is this window's: it is shared with the other item windows.
	def __HideSlotToolTip(self):
		if -1 != self.overSlot:
			self.OverOutItem()
