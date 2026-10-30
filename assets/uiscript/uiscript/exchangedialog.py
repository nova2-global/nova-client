import uiScriptLocale

ROOT = "d:/ymir work/ui/game/"

# OLD's 24-slot trade window (NOVA-12; OLD uiscript/exchangedialog_new.py) on
# NEW's art: two 6 x 4 grids (exchange.EXCHANGE_COLUMNS x EXCHANGE_ROWS), the
# faces in their frames, the partner's name and level, "You", the money and
# accept row under each grid (NEW's accept lamps and button; OLD's arrow art
# is not in NEW's assets) and the history under both.
GRID_WIDTH = 32 * 6
GRID_HEIGHT = 32 * 4
SIDE_Y = 92
SIDE_HEIGHT = GRID_HEIGHT + 4 + 21
OWNER_X = 10 + GRID_WIDTH + 38
LOG_Y = SIDE_Y + SIDE_HEIGHT + 5
LOG_LINE_COUNT = 3
WINDOW_WIDTH = OWNER_X + GRID_WIDTH + 10
WINDOW_HEIGHT = LOG_Y + 13 * LOG_LINE_COUNT + 10 + 8


def face(name, x):
	return (
		{
			"name" : name + "_Image",
			"type" : "image",

			"x" : x + 5,
			"y" : 39,

			"image" : ROOT + "windows/face_warrior.sub",
		},
		{
			"name" : name + "_Slot",
			"type" : "image",

			"x" : x,
			"y" : 34,

			"image" : ROOT + "windows/box_face.sub",
		},
	)


def grid(name):
	return {
		"name" : name,
		"type" : "grid_table",

		"start_index" : 0,

		"x" : 0,
		"y" : 0,

		"x_count" : 6,
		"y_count" : 4,
		"x_step" : 32,
		"y_step" : 32,
		"x_blank" : 0,
		"y_blank" : 0,

		"image" : "d:/ymir work/ui/public/slot_base.sub",
	}


def accept_light(name):
	return {
		"name" : name,
		"type" : "button",

		"x" : 119,
		"y" : GRID_HEIGHT + 4,

		"default_image" : ROOT + "windows/accept_button_off.sub",
		"over_image" : ROOT + "windows/accept_button_off.sub",
		"down_image" : ROOT + "windows/accept_button_on.sub",
	}


def money_value(name):
	return {
		"name" : name,
		"type" : "text",

		"x" : 112,
		"y" : 2,

		"text" : "1234567",

		"text_horizontal_align" : "right",
	}


window = {
	"name" : "ExchangeDialog",

	"x" : 0,
	"y" : 0,

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
					"y" : 8,

					"width" : WINDOW_WIDTH - 16,
					"color" : "gray",

					"children" :
					(
						{ "name":"TitleName", "type":"text", "x":(WINDOW_WIDTH - 16) // 2, "y":3, "text":uiScriptLocale.EXCHANGE_TITLE, "text_horizontal_align":"center" },
					),
				},
			) + face("FaceTarget", 10) + face("FaceOwner", OWNER_X) + (
				## The partner's name and level, and "You" (OLD :54-110)
				{
					"name" : "target_NameText",
					"type" : "text",

					"x" : 10 + 53 + 7,
					"y" : 41,

					"text" : "",
				},
				{
					"name" : "target_LvText",
					"type" : "text",

					"x" : 10 + 53 + 7,
					"y" : 59,

					"r" : 0.0,
					"g" : 0.85,
					"b" : 0.0,

					"text" : "",
				},
				{
					"name" : "own_Text",
					"type" : "text",

					"x" : OWNER_X + 53 + 7,
					"y" : 41,

					"r" : 0.85,
					"g" : 0.25,
					"b" : 0.25,

					"text" : uiScriptLocale.NEW_EXCHANGE_YOU,
				},

				## MiddleBar
				{
					"name" : "Middle_Bar",
					"type" : "image",

					"x" : 10 + GRID_WIDTH + 17,
					"y" : SIDE_Y,

					"image" : ROOT + "windows/middlebar.sub",
				},

				## Owner
				{
					"name" : "Owner",
					"type" : "window",

					"x" : OWNER_X,
					"y" : SIDE_Y,

					"width" : GRID_WIDTH,
					"height" : SIDE_HEIGHT,

					"children" :
					(
						grid("Owner_Slot"),
						{
							"name" : "Owner_Money",
							"type" : "button",

							"x" : 0,
							"y" : GRID_HEIGHT + 5,

							"default_image" : "d:/ymir work/ui/public/parameter_slot_04.sub",
							"over_image" : "d:/ymir work/ui/public/parameter_slot_04.sub",
							"down_image" : "d:/ymir work/ui/public/parameter_slot_04.sub",

							"children" :
							(
								money_value("Owner_Money_Value"),
							),
						},
						accept_light("Owner_Accept_Light"),
						{
							"name" : "Owner_Accept_Button",
							"type" : "toggle_button",

							"x" : 147,
							"y" : GRID_HEIGHT + 4,

							"text" : uiScriptLocale.EXCHANGE_ACCEPT,

							"default_image" : "d:/ymir work/ui/public/small_button_01.sub",
							"over_image" : "d:/ymir work/ui/public/small_button_02.sub",
							"down_image" : "d:/ymir work/ui/public/small_button_03.sub",
						},
					),
				},

				## Target
				{
					"name" : "Target",
					"type" : "window",

					"x" : 10,
					"y" : SIDE_Y,

					"width" : GRID_WIDTH,
					"height" : SIDE_HEIGHT,

					"children" :
					(
						grid("Target_Slot"),
						{
							"name" : "Target_Money",
							"type" : "image",

							"x" : 0,
							"y" : GRID_HEIGHT + 5,

							"image" : "d:/ymir work/ui/public/parameter_slot_04.sub",

							"children" :
							(
								money_value("Target_Money_Value"),
							),
						},
						accept_light("Target_Accept_Light"),
					),
				},

				## The history (OLD :17-26: ExchangeLogs, its last lines)
				{
					"name" : "ExchangeLogs",
					"type" : "thinboard",

					"x" : 10,
					"y" : LOG_Y,

					"width" : WINDOW_WIDTH - 20,
					"height" : 13 * LOG_LINE_COUNT + 10,

					"children" : tuple(
						{
							"name" : "ExchangeLog_%d" % index,
							"type" : "text",

							"x" : 8,
							"y" : 5 + 13 * index,

							"text" : "",
						} for index in range(LOG_LINE_COUNT)),
				},
			),
		},
	),
}
