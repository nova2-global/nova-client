import uiScriptLocale

## The offline shop's log (NOVA-9; OLD uiscript/offlineshoplogwindow.py): a window of its own (the
## Interface's wndOfflineShopLog). The rows are made in code inside "LogsWindow", which a
## ui.ScrollWindow scrolls; OLD's art (ui/offline_shop/log/*) is not in NEW's packs (Q9).

window = {
	"name" : "OfflineShopLogWindow",

	"x" : SCREEN_WIDTH - 540,
	"y" : 60,

	"style" : ("movable", "float",),

	"width" : 520,
	"height" : 480,

	"children" :
	(
		{
			"name" : "board",
			"type" : "board",
			"style" : ("attach",),

			"x" : 0,
			"y" : 0,

			"width" : 520,
			"height" : 480,

			"children" :
			(
				{
					"name" : "TitleBar",
					"type" : "titlebar",
					"style" : ("attach",),

					"x" : 8,
					"y" : 7,

					"width" : 505,
					"color" : "gray",

					"children" :
					(
						{ "name" : "TitleName", "type" : "text", "x" : 0, "y" : 4, "text" : uiScriptLocale.OFFLINE_SHOP_BUTTON_VIEW_LOGS, "horizontal_align" : "center", "text_horizontal_align" : "center" },
					),
				},
				## The rows' window; the scroll window takes it as its content.
				{
					"name" : "LogsWindow",
					"type" : "window",

					"x" : 0,
					"y" : 0,

					"width" : 480,
					"height" : 1,
				},
				## The loading and empty states (o-cli bug 14)
				{
					"name" : "LoadingText",
					"type" : "text",

					"x" : 0,
					"y" : 0,

					"text" : "...",

					"horizontal_align" : "center",
					"vertical_align" : "center",
					"text_horizontal_align" : "center",
					"text_vertical_align" : "center",
				},
				{
					"name" : "EmptyText",
					"type" : "text",

					"x" : 0,
					"y" : 0,

					"text" : "-",

					"horizontal_align" : "center",
					"vertical_align" : "center",
					"text_horizontal_align" : "center",
					"text_vertical_align" : "center",
				},
			),
		},
	),
}
