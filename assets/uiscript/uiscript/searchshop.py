import uiScriptLocale
import localeInfo

## The shop search (NOVA-9; OLD uiscript/searchshop.py): the name field and its buttons, the gold and
## the premium status, the categories (a list made in code), the results (rows made in code inside
## "ItemBarList", which a ui.ScrollWindow scrolls), the pages and the rows per page. OLD's art
## (ui/search_shop/*) is not in NEW's packs (Q9): the public buttons and boards.

BOARD_WIDTH = 760
BOARD_HEIGHT = 540
RESULTS_X = 190
RESULTS_Y = 64
RESULTS_WIDTH = 556
RESULTS_HEIGHT = 420
BOTTOM_Y = BOARD_HEIGHT - 44

def middle_button(name, x, y, text):
	return {
		"name" : name,
		"type" : "button",
		"x" : x,
		"y" : y,
		"text" : text,
		"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
		"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
		"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
	}

def small_button(name, x, y, text, kind="button"):
	return {
		"name" : name,
		"type" : kind,
		"x" : x,
		"y" : y,
		"text" : text,
		"default_image" : "d:/ymir work/ui/public/small_button_01.sub",
		"over_image" : "d:/ymir work/ui/public/small_button_02.sub",
		"down_image" : "d:/ymir work/ui/public/small_button_03.sub",
	}

window = {
	"name" : "SearchShopWindow",

	"x" : (SCREEN_WIDTH - BOARD_WIDTH) // 2,
	"y" : (SCREEN_HEIGHT - BOARD_HEIGHT) // 2,

	"style" : ("movable", "float",),

	"width" : BOARD_WIDTH,
	"height" : BOARD_HEIGHT,

	"children" :
	(
		{
			"name" : "Board",
			"type" : "board",
			"style" : ("attach",),

			"x" : 0,
			"y" : 0,

			"width" : BOARD_WIDTH,
			"height" : BOARD_HEIGHT,

			"children" :
			(
				{
					"name" : "TitleBar",
					"type" : "titlebar",
					"style" : ("attach",),

					"x" : 8,
					"y" : 7,

					"width" : BOARD_WIDTH - 15,
					"color" : "gray",

					"children" :
					(
						{ "name" : "TitleName", "type" : "text", "x" : 0, "y" : 4, "text" : uiScriptLocale.SEARCH_SHOP_TITLE, "horizontal_align" : "center", "text_horizontal_align" : "center" },
					),
				},

				## The name, the search, the filter, the bookmarks and the sort
				{
					"name" : "InputSlot",
					"type" : "slotbar",

					"x" : 14,
					"y" : 37,

					"width" : 200,
					"height" : 18,

					"children" :
					(
						{
							"name" : "InputName",
							"type" : "editline",

							"x" : 3,
							"y" : 3,

							"width" : 194,
							"height" : 15,

							"input_limit" : 64,
						},
					),
				},
				middle_button("SearchButton", 220, 35, uiScriptLocale.OK),
				middle_button("FilterButton", 285, 35, uiScriptLocale.SEARCH_SHOP_FILTER_CATEGORY),
				middle_button("SaveButton", 350, 35, uiScriptLocale.SEARCH_SHOP_FAVOURITES),
				middle_button("ListButton", 415, 35, uiScriptLocale.SEARCH_SHOP_BOOKMARKS),
				{
					"name" : "SortButton",
					"type" : "toggle_button",

					"x" : 480,
					"y" : 35,

					"text" : uiScriptLocale.SEARCH_SHOP_SORT_DOWN,

					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},

				## The gold and the premium status
				{ "name" : "GoldAmountInfo", "type" : "text", "x" : 556, "y" : 32, "text" : localeInfo.SEARCH_SHOP_GOLD, },
				{ "name" : "GoldAmountText", "type" : "text", "x" : 556, "y" : 46, "text" : "", },
				{ "name" : "PremiumStatusInfo", "type" : "text", "x" : 662, "y" : 32, "text" : localeInfo.SEARCH_SHOP_PREMIMUM_STATUS, },
				{ "name" : "PremiumStatusText", "type" : "text", "x" : 662, "y" : 46, "text" : localeInfo.SEARCH_SHOP_PREMIMUM_INACTIVE, },

				## The categories (a list and its scroll bar, made in code over this board)
				{
					"name" : "CategoryBoard",
					"type" : "thinboard",

					"x" : 10,
					"y" : RESULTS_Y,

					"width" : 174,
					"height" : RESULTS_HEIGHT,
				},

				## The results (rows made in code inside ItemBarList)
				{
					"name" : "ResultsBoard",
					"type" : "thinboard",

					"x" : RESULTS_X,
					"y" : RESULTS_Y,

					"width" : RESULTS_WIDTH,
					"height" : RESULTS_HEIGHT,
				},
				{
					"name" : "ItemBarList",
					"type" : "window",

					"x" : 0,
					"y" : 0,

					"width" : RESULTS_WIDTH - 25,
					"height" : 1,
				},
				{
					"name" : "LoadingText",
					"type" : "text",

					"x" : RESULTS_X + RESULTS_WIDTH // 2,
					"y" : RESULTS_Y + RESULTS_HEIGHT // 2,

					"text" : "...",

					"text_horizontal_align" : "center",
				},

				## The pages
				small_button("FirstButton", 250, BOTTOM_Y, "<<"),
				small_button("PrevButton", 296, BOTTOM_Y, "<"),
				small_button("page1_button", 342, BOTTOM_Y, "1", "radio_button"),
				small_button("page2_button", 388, BOTTOM_Y, "2", "radio_button"),
				small_button("page3_button", 434, BOTTOM_Y, "3", "radio_button"),
				small_button("page4_button", 480, BOTTOM_Y, "4", "radio_button"),
				small_button("page5_button", 526, BOTTOM_Y, "5", "radio_button"),
				small_button("NextButton", 572, BOTTOM_Y, ">"),
				small_button("LastButton", 618, BOTTOM_Y, ">>"),

				## The rows per page
				small_button("Result25", 14, BOTTOM_Y, "25", "radio_button"),
				small_button("Result50", 60, BOTTOM_Y, "50", "radio_button"),
				small_button("Result100", 106, BOTTOM_Y, "100", "radio_button"),
			),
		},
	),
}
