import uiScriptLocale

## The key bindings (NOVA-121), opened from the game options' Keyboard row.
## uikeybindings.KeyBindingsDialog fills it: the section and action rows, 16
## at a time with the scroll bar (ROW_Y, ROW_STEP and ROW_COUNT there), and
## the key cells on the large button art; the notice line and Defaults below.

ROOT_PATH = "d:/ymir work/ui/public/"

BOARD_WIDTH = 384
BOARD_HEIGHT = 472
KEY_1_X = 172
KEY_2_X = 266
KEY_WIDTH = 88

window = {
	"name" : "KeyBindingsDialog",
	"style" : ("movable", "float",),

	"x" : 0,
	"y" : 0,

	"width" : BOARD_WIDTH,
	"height" : BOARD_HEIGHT,

	"children" :
	(
		{
			"name" : "board",
			"type" : "board",

			"x" : 0,
			"y" : 0,

			"width" : BOARD_WIDTH,
			"height" : BOARD_HEIGHT,

			"children" :
			(
				{
					"name" : "titlebar",
					"type" : "titlebar",
					"style" : ("attach",),

					"x" : 8,
					"y" : 8,

					"width" : BOARD_WIDTH - 16,
					"color" : "gray",

					"children" :
					(
						{ "name":"titlename", "type":"text", "x":0, "y":3,
						"text" : uiScriptLocale.KEYBIND_TITLE,
						"horizontal_align":"center", "text_horizontal_align":"center" },
					),
				},

				{ "name" : "column_action", "type" : "text", "x" : 20, "y" : 36, "text" : uiScriptLocale.KEYBIND_COLUMN_ACTION, },
				{ "name" : "column_1", "type" : "text", "x" : KEY_1_X + KEY_WIDTH // 2, "y" : 36,
					"text" : uiScriptLocale.KEYBIND_COLUMN_1, "text_horizontal_align" : "center", },
				{ "name" : "column_2", "type" : "text", "x" : KEY_2_X + KEY_WIDTH // 2, "y" : 36,
					"text" : uiScriptLocale.KEYBIND_COLUMN_2, "text_horizontal_align" : "center", },

				{
					"name" : "scrollbar",
					"type" : "scrollbar",

					"x" : 358,
					"y" : 56,
					"size" : 352,
				},

				{ "name" : "notice", "type" : "text", "x" : 20, "y" : 416, "text" : "", },

				{
					"name" : "reset_button",
					"type" : "button",

					"x" : 20,
					"y" : 440,

					"text" : uiScriptLocale.KEYBIND_RESET,

					"default_image" : ROOT_PATH + "middle_button_01.sub",
					"over_image" : ROOT_PATH + "middle_button_02.sub",
					"down_image" : ROOT_PATH + "middle_button_03.sub",
				},
			),
		},
	),
}
