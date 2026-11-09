import uiScriptLocale

## The dungeon manager (NOVA-25; OLD uiscript/timerwindow.py, ENABLE_TIMER_WINDOW): the dungeon list
## (made in code: uitimerwindow.TimerWindow's boards in a scroll window at 21, 73), the drops and
## ranking buttons, the chosen dungeon's entry item, level band, group rule and cooldown, its
## description and the teleport. OLD's art (ui/dungeon_manager/*) is not in NEW's packs, so the
## parts are NEW's thin boards and buttons at OLD's places; OLD's 3D boss preview (the render
## target, NOVA-137) is left out: its frame shows the boss's name only.

BOARD_WIDTH = 618
BOARD_HEIGHT = 472
BUTTON = "d:/ymir work/ui/public/large_button_0%d.sub"

window = {
	"name" : "DungeonTimerWindow",
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
			"title" : uiScriptLocale.DUNGEON_MANAGER_TITLE,
		},
		{
			"name" : "top_bar",
			"type" : "thinboard",

			"x" : 20,
			"y" : 34,

			"width" : 578,
			"height" : 30,

			"children" :
			(
				{ "name" : "ChooseADungeon", "type" : "text", "x" : 0, "y" : 0, "all_align" : "center",
				  "text" : uiScriptLocale.DUNGEON_MANAGER_CHOOSE_DUNGEON },
			),
		},
		{
			"name" : "ListBoard",
			"type" : "thinboard",

			"x" : 17,
			"y" : 69,

			"width" : 584,
			"height" : 155,
		},
		{
			"name" : "buttonsBG",
			"type" : "thinboard",

			"x" : 20,
			"y" : 227,

			"width" : 578,
			"height" : 32,

			"children" :
			(
				{ "name" : "DungeonDrops", "type" : "button", "x" : 40, "y" : 5, "text" : uiScriptLocale.DUNGEON_MANAGER_DROPS,
				  "default_image" : BUTTON % 1, "over_image" : BUTTON % 2, "down_image" : BUTTON % 3, },
				{ "name" : "TimeRank", "type" : "button", "x" : 180, "y" : 5, "text" : uiScriptLocale.DUNGEON_MANAGER_TIME_RANK,
				  "default_image" : BUTTON % 1, "over_image" : BUTTON % 2, "down_image" : BUTTON % 3, },
				{ "name" : "OverAllRank", "type" : "button", "x" : 320, "y" : 5, "text" : uiScriptLocale.DUNGEON_MANAGER_OVERALL_RANK,
				  "default_image" : BUTTON % 1, "over_image" : BUTTON % 2, "down_image" : BUTTON % 3, },
				{ "name" : "DamageRank", "type" : "button", "x" : 460, "y" : 5, "text" : uiScriptLocale.DUNGEON_MANAGER_DAMAGE_RANK,
				  "default_image" : BUTTON % 1, "over_image" : BUTTON % 2, "down_image" : BUTTON % 3, },
			),
		},
		{
			"name" : "info_bar",
			"type" : "thinboard",

			"x" : 20,
			"y" : 262,

			"width" : 447,
			"height" : 40,

			"children" :
			(
				{ "name" : "text4", "type" : "text", "x" : 10, "y" : 13, "text" : uiScriptLocale.DUNGEON_MANAGER_REQUIRED_ITEM },
				{
					"name" : "ItemSlot",
					"type" : "slot",
					"x" : 85,
					"y" : 4,
					"width" : 32,
					"height" : 32,
					"slot" :
					(
						{ "index" : 0, "x" : 0, "y" : 0, "width" : 32, "height" : 32 },
					),
				},
				{ "name" : "text1", "type" : "text", "x" : 125, "y" : 6, "text" : uiScriptLocale.DUNGEON_MANAGER_LEVEL },
				{ "name" : "text2", "type" : "text", "x" : 220, "y" : 13, "text" : uiScriptLocale.DUNGEON_MANAGER_GROUP_REQUESTED },
				{ "name" : "text3", "type" : "text", "x" : 340, "y" : 13, "text" : uiScriptLocale.DUNGEON_MANAGER_COOLDOWN },
			),
		},
		{
			"name" : "info_bg",
			"type" : "thinboard",

			"x" : 20,
			"y" : 304,

			"width" : 447,
			"height" : 128,
		},
		{
			"name" : "RenderBG",
			"type" : "thinboard",

			"x" : 473,
			"y" : 262,

			"width" : 125,
			"height" : 168,

			"children" :
			(
				{ "name" : "bossname", "type" : "text", "x" : 0, "y" : 0, "all_align" : "center",
				  "text" : uiScriptLocale.DUNGEON_MANAGER_UNKNOWN },
			),
		},
		{
			"name" : "Teleport",
			"type" : "button",
			"x" : 510,
			"y" : 438,
			"text" : uiScriptLocale.DUNGEON_MANAGER_TELEPORT,
			"default_image" : BUTTON % 1,
			"over_image" : BUTTON % 2,
			"down_image" : BUTTON % 3,
		},
	),
}
