import uiScriptLocale

## The switchbot (NOVA-43): OLD's uiscript/switchbot.py, its 758 x 580 board,
## with the places OLD's uiSwitchbot.py gives its widgets in code: six item
## tabs of 85 x 153 from (92, 84), 100 apart; the target rows at x 92 from
## y 312, 27 apart (5 normal, then the 2 rare); the alternatives, the 6/7
## toggle, start/stop, save and the premium line on the right. OLD's art
## under d:/ymir work/ui/switchbot/ is not shipped: NEW's public board, slot
## and buttons stand in, as for the sash windows (wave 6). The cost choice
## (switch item or yang, NOVA-43 Q3 c) and the roll speed are new: they sit
## under the alternatives, where OLD's alternative art ended.
BOARD_WIDTH = 758
BOARD_HEIGHT = 580
TAB_X = 92
TAB_Y = 84
TAB_STEP = 100
TAB_WIDTH = 85
TAB_HEIGHT = 153
SLOT_COUNT = 6
SLOT_BASE = "d:/ymir work/ui/public/Slot_Base.sub"
MIDDLE = "d:/ymir work/ui/public/middle_button_0%d.sub"
LARGE = "d:/ymir work/ui/public/large_button_0%d.sub"
ROMAN = ("I", "II", "III", "IV", "V", "VI")
COLOR_INACTIVE = 0x33FF0000


def tab_children():
	children = []
	for i in range(SLOT_COUNT):
		x = TAB_X + TAB_STEP * i
		children.append({"name" : "SelectBox%d" % i, "type" : "box", "x" : x + 1, "y" : TAB_Y + 1,
			"width" : TAB_WIDTH - 2, "height" : TAB_HEIGHT - 2, "color" : 0xFFFFFFFF})
		children.append({"name" : "StatusBar%d" % i, "type" : "bar", "x" : x + 2, "y" : TAB_Y + 2,
			"width" : TAB_WIDTH - 4, "height" : TAB_HEIGHT - 4, "color" : COLOR_INACTIVE})
		children.append({"name" : "SelectButton%d" % i, "type" : "radio_button", "x" : x + 12, "y" : TAB_Y + 126,
			"text" : ROMAN[i], "default_image" : MIDDLE % 1, "over_image" : MIDDLE % 2, "down_image" : MIDDLE % 3})
	return tuple(children)


def button(name, kind, x, y, text, art=LARGE):
	return {"name" : name, "type" : kind, "x" : x, "y" : y, "text" : text,
		"default_image" : art % 1, "over_image" : art % 2, "down_image" : art % 3}


window = {
	"name" : "SwitchbotWindow",

	"x" : (SCREEN_WIDTH - BOARD_WIDTH) / 2,
	"y" : (SCREEN_HEIGHT - BOARD_HEIGHT) / 2,

	"style" : ("movable", "float",),

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
			tab_children() +
			(
				{
					"name" : "TitleBar",
					"type" : "titlebar",
					"style" : ("attach",),

					"x" : 8,
					"y" : 7,

					"width" : BOARD_WIDTH - 15,
					"color" : "yellow",

					"children" :
					(
						{ "name" : "TitleName", "type" : "text", "x" : 0, "y" : 3, "text" : uiScriptLocale.SWITCHBOT_TITLE,
							"horizontal_align" : "center", "text_horizontal_align" : "center" },
					),
				},

				## The six items: one slot per tab, an item up to 3 cells tall.
				{
					"name" : "ItemSlot",
					"type" : "slot",

					"x" : 0,
					"y" : 0,

					"width" : BOARD_WIDTH,
					"height" : BOARD_HEIGHT,

					"image" : SLOT_BASE,

					"slot" : tuple({"index" : i, "x" : TAB_X + TAB_STEP * i + 26, "y" : TAB_Y + 22, "width" : 32, "height" : 96}
						for i in range(SLOT_COUNT)),
				},

				{ "name" : "AlternativeLabel", "type" : "text", "x" : 512, "y" : 262, "text" : uiScriptLocale.SWITCHBOT_ALTERNATIVE },
				button("AlternativeButton0", "radio_button", 495, 282, "I", MIDDLE),
				button("AlternativeButton1", "radio_button", 560, 282, "II", MIDDLE),
				button("AlternativeButton2", "radio_button", 625, 282, "III", MIDDLE),

				{ "name" : "CostLabel", "type" : "text", "x" : 495, "y" : 318, "text" : uiScriptLocale.SWITCHBOT_COST },
				button("CostItemButton", "radio_button", 495, 338, uiScriptLocale.SWITCHBOT_COST_ITEM),
				button("CostYangButton", "radio_button", 590, 338, uiScriptLocale.SWITCHBOT_COST_YANG),
				{ "name" : "CostText", "type" : "text", "x" : 495, "y" : 366, "text" : "" },

				button("StartStopButton", "button", 668, 422, uiScriptLocale.SWITCHBOT_START),
				button("SaveButton", "button", 8, 474, uiScriptLocale.SWITCHBOT_SAVE, MIDDLE),
				button("RareButton", "toggle_button", 485, 480, uiScriptLocale.SWITCHBOT_RARE),

				{ "name" : "PremiumLabel", "type" : "text", "x" : 490, "y" : 520, "text" : uiScriptLocale.SWITCHBOT_PREMIUM_LABEL },
				{ "name" : "PremiumStatus", "type" : "text", "x" : 603, "y" : 520, "text" : "" },
				{ "name" : "SpeedText", "type" : "text", "x" : 490, "y" : 540, "text" : "" },
			),
		},
	),
}
