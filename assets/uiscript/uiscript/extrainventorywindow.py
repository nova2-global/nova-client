import uiScriptLocale

# The special inventory (NOVA-16; OLD uiscript/extrainventory.py): a 5 x 9 page
# of the extra inventory, its page tabs above it and its five category tabs
# beside it. OLD's category icons (cat_*.tga) and NewUI art are not in NEW's
# assets, so the categories are text buttons on NEW's large button art and
# the pages NEW's small tabs, seven to a row: I-V for every category, I-XII
# for the costumes (player.EXTRA_INVENTORY_COSTUME_PAGE_COUNT).
TAB_COUNT = 12
TABS_PER_ROW = 7
TAB_WIDTH = 32
TAB_HEIGHT = 21
GRID_X = 8
GRID_Y = 33 + TAB_HEIGHT * 2 + 4
CATEGORY_X = GRID_X + 32 * 5 + 6
CATEGORY_STEP = 24
WINDOW_WIDTH = CATEGORY_X + 88 + 8
WINDOW_HEIGHT = GRID_Y + 32 * 9 + 10
ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")
# Scrolls, materials, stones, chests and costumes: the server's category
# order (nova-protocol inventory_packets.h EXTRA_INVENTORY_CATEGORY_*).
CATEGORY_NAMES = (uiScriptLocale.EXTRA_INVENTORY_CATEGORY_SCROLLS, uiScriptLocale.EXTRA_INVENTORY_CATEGORY_MATERIALS,
                  uiScriptLocale.EXTRA_INVENTORY_CATEGORY_STONES, uiScriptLocale.EXTRA_INVENTORY_CATEGORY_CHESTS,
                  uiScriptLocale.EXTRA_INVENTORY_CATEGORY_COSTUMES)


def page_tab(index):
	return {
		"name" : "Inventory_Tab_%02d" % (index + 1),
		"type" : "radio_button",

		"x" : GRID_X + TAB_WIDTH * (index % TABS_PER_ROW),
		"y" : 33 + TAB_HEIGHT * (index // TABS_PER_ROW),

		"default_image" : "d:/ymir work/ui/game/windows/tab_button_small_01.sub",
		"over_image" : "d:/ymir work/ui/game/windows/tab_button_small_02.sub",
		"down_image" : "d:/ymir work/ui/game/windows/tab_button_small_03.sub",

		"children" :
		(
			{
				"name" : "Inventory_Tab_%02d_Print" % (index + 1),
				"type" : "text",

				"x" : 0,
				"y" : 0,

				"all_align" : "center",

				"text" : ROMAN[index],
			},
		),
	}


def category_tab(index):
	return {
		"name" : "Cat_%02d" % index,
		"type" : "radio_button",

		"x" : CATEGORY_X,
		"y" : GRID_Y + CATEGORY_STEP * index,

		"text" : CATEGORY_NAMES[index],

		"default_image" : "d:/ymir work/ui/public/large_button_01.sub",
		"over_image" : "d:/ymir work/ui/public/large_button_02.sub",
		"down_image" : "d:/ymir work/ui/public/large_button_03.sub",
	}


window = {
	"name" : "ExtraInventoryWindow",

	## Left of the inventory (176 px wide), its top at the inventory's.
	"x" : SCREEN_WIDTH - 176 - WINDOW_WIDTH - 10,
	"y" : SCREEN_HEIGHT - 37 - 591,

	"style" : ("movable", "float",),

	"width" : WINDOW_WIDTH,
	"height" : WINDOW_HEIGHT,

	"children" :
	(
		{
			"name" : "board",
			"type" : "board",
			"style" : ("attach",),

			"x" : 0,
			"y" : 0,

			"width" : WINDOW_WIDTH,
			"height" : WINDOW_HEIGHT,

			"children" :
			(
				## Title
				{
					"name" : "TitleBar",
					"type" : "titlebar",
					"style" : ("attach",),

					"x" : 8,
					"y" : 7,

					"width" : WINDOW_WIDTH - 16,
					"color" : "yellow",

					"children" :
					(
						{ "name":"TitleName", "type":"text", "x":(WINDOW_WIDTH - 16) // 2, "y":3, "text":uiScriptLocale.KEYCHANGE_EXTRA_INVENTORY, "text_horizontal_align":"center" },
					),
				},

				## Item Slot
				{
					"name" : "ItemSlot",
					"type" : "grid_table",

					"x" : GRID_X,
					"y" : GRID_Y,

					"start_index" : 0,
					"x_count" : 5,
					"y_count" : 9,
					"x_step" : 32,
					"y_step" : 32,

					"image" : "d:/ymir work/ui/public/Slot_Base.sub"
				},
			) + tuple(page_tab(index) for index in range(TAB_COUNT)) + tuple(category_tab(index) for index in range(5)),
		},
	),
}
