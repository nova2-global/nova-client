import uiScriptLocale

## The dungeon ranking (NOVA-25; OLD uiscript/newdungeonrankwindow.py, the one OLD's default
## new_interface loads, ENABLE_DUNGEON_RANKING): the title (the dungeon and the ranking), the
## header (name and count) and, made in code (uidungeonrank.RankImage), ten rank rows from y 67,
## 29 apart, and the player's own row under them. OLD's rows and header art
## (ui/dungeon_manager/new/*) are not in NEW's packs: the header is a thin board and each row a bar.

BOARD_WIDTH = 356
BOARD_HEIGHT = 402

window = {
	"name" : "DungeonRankWindow",

	"x" : (SCREEN_WIDTH - BOARD_WIDTH) // 2,
	"y" : (SCREEN_HEIGHT - BOARD_HEIGHT) // 2,

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
			(
				{
					"name" : "TitleBar",
					"type" : "titlebar",
					"style" : ("attach",),

					"x" : 6,
					"y" : 6,

					"width" : BOARD_WIDTH - 10,
					"color" : "yellow",

					"children" :
					(
						{ "name" : "TitleName", "type" : "text", "x" : 0, "y" : 4, "text" : uiScriptLocale.DUNGEON_RANK_TITLE1,
						  "horizontal_align" : "center", "text_horizontal_align" : "center" },
					),
				},
				{
					"name" : "RankTopImg",
					"type" : "thinboard",
					"x" : 13,
					"y" : 34,
					"width" : 330,
					"height" : 30,
					"children" :
					(
						{ "name" : "ResultMemberName", "type" : "text", "x" : 135, "y" : 9, "text" : uiScriptLocale.KILL_COUNT_NAME, "text_horizontal_align" : "center" },
						{ "name" : "ResultMemberCount", "type" : "text", "x" : 272, "y" : 9, "text" : uiScriptLocale.KILL_COUNT_COUNT, "text_horizontal_align" : "center" },
					),
				},
			),
		},
	),
}
