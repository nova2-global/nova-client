import uiScriptLocale

# The cube (refinement) window, OLD's newcuberenewalwindow.py layout with the same
# widget names. OLD's art (d:/ymir work/ui/game/cube_new/) is not in NEW's assets;
# the stand-ins below are NEW's own art, and NovaUI draws its own window.

PUBLIC_PATH = "d:/ymir work/ui/public/"
WINDOWS_PATH = "d:/ymir work/ui/game/windows/"
BELT_PATH = "d:/ymir work/ui/game/belt_inventory/"

BOARD_WIDTH = 336
BOARD_HEIGHT = 488

# The recipe tree: uiCubeRenewal places its rows in item_list_board and shows as
# many as its height holds, with the scroll bar beside it.
LIST_X = 10
LIST_Y = 34
LIST_WIDTH = 292
LIST_HEIGHT = 252
SCROLL_BAR_X = LIST_X + LIST_WIDTH + 4

# The result slot and five material slots, each three cells high, on one row.
ITEM_SLOT_X = 10
ITEM_SLOT_Y = 294
ITEM_SLOT_WIDTH = 316
ITEM_SLOT_HEIGHT = 136
SLOT_X = 25
SLOT_Y = 13
CELL_SIZE = 32
SLOT_CELLS = 3
RESULT_SLOT_X = 0
MATERIAL_SLOT_X = 62
MATERIAL_SLOT_STEP = 46
MATERIAL_SLOT_COUNT = 5
SLOT_ROW_WIDTH = MATERIAL_SLOT_X + MATERIAL_SLOT_STEP * (MATERIAL_SLOT_COUNT - 1) + CELL_SIZE
COUNT_TEXT_Y = 115
COUNT_TEXT_WIDTH = 45
PAGE_BUTTON_Y = SLOT_Y - 6

# Yang and gaya cost, and the buttons.
COST_Y = 434
BUTTON_Y = 458

SLOT_X_LIST = [RESULT_SLOT_X] + [MATERIAL_SLOT_X + MATERIAL_SLOT_STEP * i for i in range(MATERIAL_SLOT_COUNT)]

def SlotBases():
	return tuple({
		"name" : "slot_base_%d_%d" % (slot, cell),
		"type" : "image",
		"style" : ("not_pick",),
		"x" : SLOT_X + x,
		"y" : SLOT_Y + CELL_SIZE * cell,
		"image" : PUBLIC_PATH + "slot_base.sub",
	} for slot, x in enumerate(SLOT_X_LIST) for cell in range(SLOT_CELLS))

def MaterialCountTexts():
	return tuple({
		"name" : "material_qty_window_%d" % (i + 1),
		"type" : "window",
		"x" : SLOT_X + MATERIAL_SLOT_X + MATERIAL_SLOT_STEP * i + (CELL_SIZE - COUNT_TEXT_WIDTH) // 2,
		"y" : COUNT_TEXT_Y,
		"width" : COUNT_TEXT_WIDTH,
		"height" : 16,
		"children" :
		(
			{
				"name" : "material_qty_text_%d" % (i + 1),
				"type" : "text",
				"x" : 0, "y" : 0,
				"horizontal_align" : "center",
				"text_horizontal_align" : "center",
				"vertical_align" : "center",
				"text_vertical_align" : "center",
				"text" : "",
			},
		),
	} for i in range(MATERIAL_SLOT_COUNT))

window = {
	"name" : "CubeRenewalWindow",
	"style" : ("movable", "float",),

	"x" : (SCREEN_WIDTH - BOARD_WIDTH) // 2,
	"y" : (SCREEN_HEIGHT - BOARD_HEIGHT) // 2,

	"width" : BOARD_WIDTH,
	"height" : BOARD_HEIGHT,

	"children" :
	(
		{
			"name" : "board",
			"type" : "board_with_titlebar",
			"style" : ("attach",),

			"x" : 0,
			"y" : 0,

			"width" : BOARD_WIDTH,
			"height" : BOARD_HEIGHT,
			"title" : uiScriptLocale.CUBE_RENEWAL_TITLE,

			"children" :
			(
				## The recipe tree
				{
					"name" : "item_list_bg",
					"type" : "thinboard",
					"x" : LIST_X - 2,
					"y" : LIST_Y - 2,
					"width" : LIST_WIDTH + 4,
					"height" : LIST_HEIGHT + 4,
				},
				{
					"name" : "item_list_board",
					"type" : "window",
					"x" : LIST_X,
					"y" : LIST_Y,
					"width" : LIST_WIDTH,
					"height" : LIST_HEIGHT,
				},
				{
					"name" : "list_scroll_bar",
					"type" : "scrollbar",
					"x" : SCROLL_BAR_X,
					"y" : LIST_Y - 2,
					"size" : LIST_HEIGHT + 4,
				},

				## The result and material slots
				{
					"name" : "item_slot",
					"type" : "thinboard",
					"x" : ITEM_SLOT_X,
					"y" : ITEM_SLOT_Y,
					"width" : ITEM_SLOT_WIDTH,
					"height" : ITEM_SLOT_HEIGHT,

					"children" : SlotBases() + MaterialCountTexts() +
					(
						{
							"name" : "icons_items",
							"type" : "slot",
							"x" : SLOT_X,
							"y" : SLOT_Y,
							"width" : SLOT_ROW_WIDTH,
							"height" : CELL_SIZE * SLOT_CELLS,
							"slot" : tuple({"index" : i, "x" : x, "y" : 0, "width" : CELL_SIZE, "height" : CELL_SIZE * SLOT_CELLS} for i, x in enumerate(SLOT_X_LIST)),
						},

						## Material pages: materials 6-10 are on the second page.
						{
							"name" : "back_button",
							"type" : "button",
							"x" : SLOT_X + CELL_SIZE + (MATERIAL_SLOT_X - CELL_SIZE - 10) // 2,
							"y" : PAGE_BUTTON_Y,
							"default_image" : BELT_PATH + "btn_expand_normal.tga",
							"over_image" : BELT_PATH + "btn_expand_over.tga",
							"down_image" : BELT_PATH + "btn_expand_down.tga",
						},
						{
							"name" : "next_button",
							"type" : "button",
							"x" : SLOT_X + SLOT_ROW_WIDTH + 2,
							"y" : PAGE_BUTTON_Y,
							"default_image" : BELT_PATH + "btn_minimize_normal.tga",
							"over_image" : BELT_PATH + "btn_minimize_over.tga",
							"down_image" : BELT_PATH + "btn_minimize_down.tga",
						},

						## Quantity of the result
						{
							"name" : "result_qty_bg",
							"type" : "image",
							"x" : 22,
							"y" : COUNT_TEXT_Y - 1,
							"image" : PUBLIC_PATH + "parameter_slot_00.sub",
						},
						{
							"name" : "result_qty_window",
							"type" : "window",
							"x" : 24,
							"y" : COUNT_TEXT_Y,
							"width" : 36,
							"height" : 16,
							"children" :
							(
								{
									"name" : "result_qty",
									"type" : "editline",
									"x" : 3, "y" : 1,
									"width" : 36,
									"height" : 16,
									"input_limit" : 4,
									"only_number" : 1,
									"text" : "",
								},
							),
						},
						{
							"name" : "qty_sub_button",
							"type" : "button",
							"x" : 7,
							"y" : COUNT_TEXT_Y + 2,
							"default_image" : WINDOWS_PATH + "btn_minus_up.sub",
							"over_image" : WINDOWS_PATH + "btn_minus_over.sub",
							"down_image" : WINDOWS_PATH + "btn_minus_down.sub",
						},
						{
							"name" : "qty_add_button",
							"type" : "button",
							"x" : 62,
							"y" : COUNT_TEXT_Y + 2,
							"default_image" : WINDOWS_PATH + "btn_plus_up.sub",
							"over_image" : WINDOWS_PATH + "btn_plus_over.sub",
							"down_image" : WINDOWS_PATH + "btn_plus_down.sub",
						},
					),
				},

				## Yang
				{
					"name" : "yang_icon",
					"type" : "image",
					"x" : 133,
					"y" : COST_Y + 1,
					"image" : WINDOWS_PATH + "money_icon.sub",
				},
				{
					"name" : "yang_textbg",
					"type" : "image",
					"x" : 153,
					"y" : COST_Y,
					"image" : PUBLIC_PATH + "parameter_slot_04.sub",
					"children" :
					(
						{
							"name" : "yang_text",
							"type" : "text",
							"x" : 7,
							"y" : 3,
							"horizontal_align" : "right",
							"text_horizontal_align" : "right",
							"text" : "",
						},
					),
				},

				## Gaya (hidden until the gem system, NOVA-10, gives a recipe a gaya cost)
				{
					"name" : "gem_icon",
					"type" : "image",
					"x" : 17,
					"y" : COST_Y + 1,
					"image" : WINDOWS_PATH + "money_icon.sub",
				},
				{
					"name" : "gem_textbg",
					"type" : "image",
					"x" : 36,
					"y" : COST_Y,
					"image" : PUBLIC_PATH + "parameter_slot_03.sub",
					"children" :
					(
						{
							"name" : "gem_text",
							"type" : "text",
							"x" : 7,
							"y" : 3,
							"horizontal_align" : "right",
							"text_horizontal_align" : "right",
							"text" : "",
						},
					),
				},

				{
					"name" : "button_ok",
					"type" : "button",
					"x" : 40,
					"y" : BUTTON_Y,
					"text" : uiScriptLocale.OK,
					"default_image" : PUBLIC_PATH + "large_button_01.sub",
					"over_image" : PUBLIC_PATH + "large_button_02.sub",
					"down_image" : PUBLIC_PATH + "large_button_03.sub",
				},
				{
					"name" : "button_cancel",
					"type" : "button",
					"x" : 209,
					"y" : BUTTON_Y,
					"text" : uiScriptLocale.CANCEL,
					"default_image" : PUBLIC_PATH + "large_button_01.sub",
					"over_image" : PUBLIC_PATH + "large_button_02.sub",
					"down_image" : PUBLIC_PATH + "large_button_03.sub",
				},
			),
		},
	),
}
