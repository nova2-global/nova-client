import uiScriptLocale

## The search's bookmarks (NOVA-9; OLD uiscript/searchbookmarks.py): ten names, made in code.

BOARD_WIDTH = 230
BOARD_HEIGHT = 255

window = {
	"name" : "SearchBookmarks",

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
						{ "name" : "TitleName", "type" : "text", "x" : 0, "y" : 4, "text" : uiScriptLocale.SEARCH_SHOP_BOOKMARKS, "horizontal_align" : "center", "text_horizontal_align" : "center" },
					),
				},
			),
		},
	),
}
