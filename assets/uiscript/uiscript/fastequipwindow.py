import uiScriptLocale

## Fast equip (NOVA-17): OLD's uiscript/NewFastEquipWindow.py, its 460 px board
## with the 10 sets on the left and the set's name bar over the cells. OLD's
## art under d:/ymir work/ui/fastequip is not shipped, so the cells' slots are
## built in code (uifastequip.CELLS, only the usable ones). The board is 44 px
## taller than OLD's for the row of buffi and aura cells (NEW's) under the
## buttons.
BOARD_WIDTH = 460
BOARD_HEIGHT = 331 + 44
BUTTON = "d:/ymir work/ui/public/middle_button_0%d.sub"


def button(name, x, y, text):
	return {"name" : name, "type" : "button", "x" : x, "y" : y, "text" : text,
		"default_image" : BUTTON % 1, "over_image" : BUTTON % 2, "down_image" : BUTTON % 3}


window = {
	"name" : "FastEquipWindow",

	"x" : (SCREEN_WIDTH - BOARD_WIDTH) / 2,
	"y" : (SCREEN_HEIGHT - BOARD_HEIGHT) / 2,

	"style" : ("movable", "float",),

	"width" : BOARD_WIDTH,
	"height" : BOARD_HEIGHT,

	"children" :
	(
		{
			"name" : "board",
			"type" : "thinboard",
			"style" : ("attach",),

			"x" : 0,
			"y" : 0,

			"width" : BOARD_WIDTH,
			"height" : BOARD_HEIGHT,

			"children" :
			(
				{ "name" : "WindowTitle", "type" : "text", "text" : uiScriptLocale.FAST_EQUIP_TITLE, "x" : 51, "y" : 13,
					"text_horizontal_align" : "center", "horizontal_align" : "center", "color" : 0xffBAAA9B },
				{
					"name" : "CloseButton",
					"type" : "button",
					"x" : 436,
					"y" : 12,
					"default_image" : "d:/ymir work/ui/public/close_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/close_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/close_button_03.sub",
				},
				{
					"name" : "SetsHeader",
					"type" : "bar",
					"x" : 16,
					"y" : 36,
					"width" : 88 + 7,
					"height" : 23,
					"children" :
					(
						{ "name" : "SetsLabel", "type" : "text", "text" : uiScriptLocale.FAST_EQUIP_SETS, "x" : 0, "y" : 0, "all_align" : "center" },
					),
				},
				{
					"name" : "TitleColor",
					"type" : "bar",
					"x" : 115,
					"y" : 36,
					"width" : 327,
					"height" : 23,
					"color" : 0x660084d0,
					"children" :
					(
						{ "name" : "TitleLabel", "type" : "text", "text" : "", "x" : 0, "y" : 0, "all_align" : "center", "color" : 0xff42f548 },
						{ "name" : "EquippedBar", "type" : "bar", "x" : -5, "y" : 0, "width" : 5, "height" : 23, "color" : 0x6600ff49 },
					),
				},
				{ "name" : "BuffiLabel", "type" : "text", "text" : uiScriptLocale.FAST_EQUIP_BUFFI, "x" : 119, "y" : 330, "color" : 0xffBAAA9B },
				{ "name" : "AuraLabel", "type" : "text", "text" : uiScriptLocale.FAST_EQUIP_AURA, "x" : 310, "y" : 330, "color" : 0xffBAAA9B },
				button("SwitchButton", 60 + 111, 290, uiScriptLocale.FAST_EQUIP_SWITCH),
				button("ClearButton", 150 + 121, 290, uiScriptLocale.FAST_EQUIP_CLEAR),
			),
		},
	),
}
