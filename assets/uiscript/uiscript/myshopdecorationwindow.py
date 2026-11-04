import uiScriptLocale

## The offline shop's decoration (NOVA-9; OLD uiscript/myshopdecorationwindow.py): two steps, the
## model and the sign style, each a list of names. No 3D preview (D15, Q8): the right side names
## the model, or shows the style's frame. OLD's art (ui/game/myshop_deco/*) is not in NEW's packs.

BOARD_WIDTH = 380
BOARD_HEIGHT = 330
LIST_X = 14
LIST_Y = 58
LIST_WIDTH = 160
LIST_HEIGHT = 230

window = {
	"name" : "MyShopDecorationWindow",
	"style" : ("movable", "float",),

	"x" : (SCREEN_WIDTH - BOARD_WIDTH) // 2,
	"y" : (SCREEN_HEIGHT - BOARD_HEIGHT) // 2,

	"width" : BOARD_WIDTH,
	"height" : BOARD_HEIGHT,

	"children" :
	(
		{
			"name" : "board",
			"type" : "board",
			"style" : ("attach",),

			"x" : 0,
			"y" : 0,

			"width" : BOARD_WIDTH,
			"height" : BOARD_HEIGHT,

			"children" :
			(
				{
					"name" : "MyShopTitleBar",
					"type" : "titlebar",
					"style" : ("attach",),

					"x" : 8,
					"y" : 7,

					"width" : BOARD_WIDTH - 15,
					"color" : "gray",

					"children" :
					(
						{ "name" : "TitleName", "type" : "text", "x" : 0, "y" : 4, "text" : "", "horizontal_align" : "center", "text_horizontal_align" : "center" },
					),
				},
				{
					"name" : "DescriptionText",
					"type" : "text",

					"x" : 0,
					"y" : 36,

					"text" : uiScriptLocale.MYSHOP_DECO_SELECT_MODEL,

					"horizontal_align" : "center",
					"text_horizontal_align" : "center",
				},

				## The list: the models, then the styles
				{
					"name" : "ListBoard",
					"type" : "thinboard",

					"x" : LIST_X - 4,
					"y" : LIST_Y - 4,

					"width" : LIST_WIDTH + 8 + 17,
					"height" : LIST_HEIGHT + 8,
				},
				{
					"name" : "ItemList",
					"type" : "listbox",

					"x" : LIST_X,
					"y" : LIST_Y,

					"width" : LIST_WIDTH,
					"height" : LIST_HEIGHT,
				},
				{
					"name" : "ScrollBar",
					"type" : "scrollbar",

					"x" : LIST_X + LIST_WIDTH,
					"y" : LIST_Y,

					"size" : LIST_HEIGHT,
				},

				## The preview: the model's name, or the style's frame
				{
					"name" : "PreviewWindow",
					"type" : "thinboard",

					"x" : 200,
					"y" : LIST_Y - 4,

					"width" : 166,
					"height" : 120,

					"children" :
					(
						{
							"name" : "ModelName",
							"type" : "text",

							"x" : 0,
							"y" : 0,

							"text" : "",

							"all_align" : "center",
						},
					),
				},

				## Step 1: Next, Cancel. Step 2: Back, Complete.
				{
					"name" : "NextButton",
					"type" : "button",

					"x" : -45,
					"y" : BOARD_HEIGHT - 34,

					"horizontal_align" : "center",

					"text" : uiScriptLocale.MYSHOP_DECO_NEXT,

					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},
				{
					"name" : "CancelButton",
					"type" : "button",

					"x" : 45,
					"y" : BOARD_HEIGHT - 34,

					"horizontal_align" : "center",

					"text" : uiScriptLocale.MYSHOP_DECO_CANCEL,

					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},
				{
					"name" : "PrevButton",
					"type" : "button",

					"x" : -45,
					"y" : BOARD_HEIGHT - 34,

					"horizontal_align" : "center",

					"text" : uiScriptLocale.MYSHOP_DECO_PREV,

					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},
				{
					"name" : "CompleteButton",
					"type" : "button",

					"x" : 45,
					"y" : BOARD_HEIGHT - 34,

					"horizontal_align" : "center",

					"text" : uiScriptLocale.MYSHOP_DECO_OK,

					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},
			),
		},
	),
}
