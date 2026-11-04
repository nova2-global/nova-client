import uiScriptLocale

## The gaya market (NOVA-10): OLD's uiscript/newgemshopwindow.py, its default
## layout (168 x 244, three rows of three slots, a price under each, the
## refresh button and the "HH:MM" countdown). OLD's art under
## d:/ymir work/ui/gemshop/new/ is not shipped yet (spec Q9, R6): NEW's
## public slot, the guild window's refresh button and the money icon stand in.
SLOT_BASE = "d:/ymir work/ui/public/Slot_Base.sub"
GEM_ICON = "d:/ymir work/ui/game/windows/money_icon.sub"
REFRESH_BUTTON = "d:/ymir work/ui/game/guild/refresh_button_0%d.sub"
BOARD_WIDTH = 168
BOARD_HEIGHT = 244
SLOT_X = (22, 67, 112)
SLOT_Y = (0, 58, 116)
SLOT_TOP = 65


def price_children():
	children = []
	for row in range(3):
		for column in range(3):
			index = row * 3 + column + 1
			x = SLOT_X[column] - 3
			y = SLOT_TOP + SLOT_Y[row] + 38
			children.append({"name" : "slot_%d_price" % index, "type" : "text", "x" : x + 28 + 6, "y" : y,
				"text" : "0", "text_horizontal_align" : "center"})
			children.append({"name" : "slot_%d_Icon" % index, "type" : "image", "x" : x + 6, "y" : y + 2,
				"image" : GEM_ICON})
	return tuple(children)


window = {
	"name" : "GemShopWindow",

	"x" : 0,
	"y" : 0,

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
				## Title
				{
					"name" : "TitleBar",
					"type" : "titlebar",
					"style" : ("attach",),

					"x" : 6,
					"y" : 6,

					"width" : BOARD_WIDTH - 15,
					"color" : "yellow",

					"children" :
					(
						{ "name" : "TitleName", "type" : "text", "x" : BOARD_WIDTH // 2 - 5, "y" : 3, "text" : uiScriptLocale.GEMSHOP_TITLE, "text_horizontal_align" : "center" },
					),
				},

				## The time until the server re-rolls the slots
				{ "name" : "BuyRefreshTimeName", "type" : "text", "x" : BOARD_WIDTH // 2 - 10, "y" : 35 + 3, "text" : uiScriptLocale.GEMSHOP_LEFTTIME, "text_horizontal_align" : "center" },
				{ "name" : "BuyRefreshTime", "type" : "text", "x" : BOARD_WIDTH // 2 + 50, "y" : 35 + 3, "text" : "00:00", "text_horizontal_align" : "center" },

				## The nine slots
				{
					"name" : "SellItemSlot",
					"type" : "slot",

					"x" : 6,
					"y" : SLOT_TOP,

					"width" : 156,
					"height" : 148,

					"slot" : tuple({"index" : row * 3 + column, "x" : SLOT_X[column], "y" : SLOT_Y[row], "width" : 32, "height" : 32}
						for row in range(3) for column in range(3)),
					"image" : SLOT_BASE,
				},

				## Refresh
				{
					"name" : "RefreshButton",
					"type" : "button",

					"x" : 10,
					"y" : 35,

					"default_image" : REFRESH_BUTTON % 1,
					"over_image" : REFRESH_BUTTON % 2,
					"down_image" : REFRESH_BUTTON % 3,
				},
			) + price_children(),
		},
	),
}
