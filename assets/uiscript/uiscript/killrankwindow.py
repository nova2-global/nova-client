import uiScriptLocale

ROOT = "d:/ymir work/ui/public/"

## The kill ranking (NOVA-29; OLD uiscript/killrankwindow.py and newkillrankwindow.py):
## eight rankings, the first ten places and the player's own row. OLD's art
## (ui/ranking/*) is not in NEW's packs: a board with a title bar, the eight
## rankings as text tabs in two rows, a header and the rows uikillrank.py makes
## in code (ROW_X, FIRST_ROW_Y, ROW_HEIGHT).

window = {
	"name" : "KillRankWindow",
	"style" : ("movable", "float",),

	"x" : (SCREEN_WIDTH - 390) / 2,
	"y" : (SCREEN_HEIGHT - 380) / 2,

	"width" : 390,
	"height" : 380,

	"children" :
	(
		{
			"name" : "board",
			"type" : "board",
			"style" : ("attach",),

			"x" : 0,
			"y" : 0,

			"width" : 390,
			"height" : 380,

			"children" :
			(
				{
					"name" : "TitleBar",
					"type" : "titlebar",
					"style" : ("attach",),

					"x" : 8,
					"y" : 7,

					"width" : 375,
					"color" : "yellow",

					"children" :
					(
						{ "name" : "TitleName", "type" : "text", "x" : 0, "y" : 3, "text" : uiScriptLocale.KILL_COUNT_TITLE0, "horizontal_align" : "center", "text_horizontal_align" : "center" },
					),
				},
				{
					"name" : "Tab_0",
					"type" : "radio_button",

					"x" : 10,
					"y" : 34,

					"text" : uiScriptLocale.KILL_RANK_TAB0,

					"default_image" : ROOT + "Large_Button_01.sub",
					"over_image" : ROOT + "Large_Button_02.sub",
					"down_image" : ROOT + "Large_Button_03.sub",
				},
				{
					"name" : "Tab_1",
					"type" : "radio_button",

					"x" : 102,
					"y" : 34,

					"text" : uiScriptLocale.KILL_RANK_TAB1,

					"default_image" : ROOT + "Large_Button_01.sub",
					"over_image" : ROOT + "Large_Button_02.sub",
					"down_image" : ROOT + "Large_Button_03.sub",
				},
				{
					"name" : "Tab_2",
					"type" : "radio_button",

					"x" : 194,
					"y" : 34,

					"text" : uiScriptLocale.KILL_RANK_TAB2,

					"default_image" : ROOT + "Large_Button_01.sub",
					"over_image" : ROOT + "Large_Button_02.sub",
					"down_image" : ROOT + "Large_Button_03.sub",
				},
				{
					"name" : "Tab_3",
					"type" : "radio_button",

					"x" : 286,
					"y" : 34,

					"text" : uiScriptLocale.KILL_RANK_TAB3,

					"default_image" : ROOT + "Large_Button_01.sub",
					"over_image" : ROOT + "Large_Button_02.sub",
					"down_image" : ROOT + "Large_Button_03.sub",
				},
				{
					"name" : "Tab_4",
					"type" : "radio_button",

					"x" : 10,
					"y" : 58,

					"text" : uiScriptLocale.KILL_RANK_TAB4,

					"default_image" : ROOT + "Large_Button_01.sub",
					"over_image" : ROOT + "Large_Button_02.sub",
					"down_image" : ROOT + "Large_Button_03.sub",
				},
				{
					"name" : "Tab_5",
					"type" : "radio_button",

					"x" : 102,
					"y" : 58,

					"text" : uiScriptLocale.KILL_RANK_TAB5,

					"default_image" : ROOT + "Large_Button_01.sub",
					"over_image" : ROOT + "Large_Button_02.sub",
					"down_image" : ROOT + "Large_Button_03.sub",
				},
				{
					"name" : "Tab_6",
					"type" : "radio_button",

					"x" : 194,
					"y" : 58,

					"text" : uiScriptLocale.KILL_RANK_TAB6,

					"default_image" : ROOT + "Large_Button_01.sub",
					"over_image" : ROOT + "Large_Button_02.sub",
					"down_image" : ROOT + "Large_Button_03.sub",
				},
				{
					"name" : "Tab_7",
					"type" : "radio_button",

					"x" : 286,
					"y" : 58,

					"text" : uiScriptLocale.KILL_RANK_TAB7,

					"default_image" : ROOT + "Large_Button_01.sub",
					"over_image" : ROOT + "Large_Button_02.sub",
					"down_image" : ROOT + "Large_Button_03.sub",
				},
				{ "name" : "HeadRank", "type" : "text", "x" : 24, "y" : 90, "text" : uiScriptLocale.KILL_RANK_COLUMN_RANK },
				{ "name" : "HeadName", "type" : "text", "x" : 74, "y" : 90, "text" : uiScriptLocale.KILL_RANK_COLUMN_NAME },
				{ "name" : "HeadGuild", "type" : "text", "x" : 210, "y" : 90, "text" : uiScriptLocale.KILL_RANK_COLUMN_GUILD },
				{ "name" : "HeadCount", "type" : "text", "x" : 310, "y" : 90, "text" : uiScriptLocale.KILL_RANK_COLUMN_COUNT },
			),
		},
	),
}
