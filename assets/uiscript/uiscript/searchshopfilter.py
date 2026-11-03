import uiScriptLocale
import localeInfo

## The search's filter (NOVA-9; OLD uiscript/searchshopFilter.py): the most yang a row may cost and
## the items' gender. OLD's English labels are NEW's keys; its gender art is not in NEW's packs.

BOARD_WIDTH = 230
BOARD_HEIGHT = 150

window = {
	"name" : "SearchShopFilter",

	"x" : 0,
	"y" : 0,

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
						{ "name" : "TitleName", "type" : "text", "x" : 0, "y" : 4, "text" : uiScriptLocale.SEARCH_SHOP_FILTER_CATEGORY, "horizontal_align" : "center", "text_horizontal_align" : "center" },
					),
				},
				{ "name" : "MaxPriceText", "type" : "text", "x" : 16, "y" : 40, "text" : localeInfo.PRIVATE_SHOP_INPUT_PRICE_DIALOG_TITLE, },
				{
					"name" : "InputSlot",
					"type" : "slotbar",

					"x" : 90,
					"y" : 38,

					"width" : 120,
					"height" : 18,

					"children" :
					(
						{
							"name" : "InputValue",
							"type" : "editline",

							"x" : 3,
							"y" : 3,

							"width" : 114,
							"height" : 15,

							"input_limit" : 13,
							"only_number" : 2,
						},
					),
				},
				{
					"name" : "maleButton",
					"type" : "toggle_button",

					"x" : 16,
					"y" : 70,

					"text" : localeInfo.FOR_MALE,

					"default_image" : "d:/ymir work/ui/public/large_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/large_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/large_button_03.sub",
				},
				{
					"name" : "femaleButton",
					"type" : "toggle_button",

					"x" : 124,
					"y" : 70,

					"text" : localeInfo.FOR_FEMALE,

					"default_image" : "d:/ymir work/ui/public/large_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/large_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/large_button_03.sub",
				},
				{
					"name" : "applybtn",
					"type" : "button",

					"x" : -40,
					"y" : 110,

					"horizontal_align" : "center",

					"text" : uiScriptLocale.OK,

					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},
				{
					"name" : "cancelbtn",
					"type" : "button",

					"x" : 40,
					"y" : 110,

					"horizontal_align" : "center",

					"text" : uiScriptLocale.CANCEL,

					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},
			),
		},
	),
}
