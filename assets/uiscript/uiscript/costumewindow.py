import uiScriptLocale
import item

COSTUME_START_INDEX = item.COSTUME_SLOT_START
## OLD's other costume cells (wear 21-27, OLD uiscript/costumewindow.py) hold
## features that are not ported: their slots stay hidden.

BUTTON_PATH = "d:/ymir work/ui/public/"
WINDOW_WIDTH = 216
WINDOW_HEIGHT = 236


def switch(name, x, y, text):
	"""A switch of OLD's costume window (NOVA-22): down while the part shows.
	OLD's on/off art (locale/common/ui/costume/*.tga) is not in NEW's packs."""
	return {
		"name" : name,
		"type" : "toggle_button",

		"x" : x,
		"y" : y,

		"text" : text,

		"default_image" : BUTTON_PATH + "middle_button_01.sub",
		"over_image" : BUTTON_PATH + "middle_button_02.sub",
		"down_image" : BUTTON_PATH + "middle_button_03.sub",
	}


window = {
	"name" : "CostumeWindow",

	"x" : SCREEN_WIDTH - 175 - WINDOW_WIDTH,
	"y" : SCREEN_HEIGHT - 37 - 565,

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

					"x" : 6,
					"y" : 6,

					"width" : WINDOW_WIDTH - 10,
					"color" : "yellow",

					"children" :
					(
						{ "name":"TitleName", "type":"text", "x":(WINDOW_WIDTH - 10) // 2, "y":3, "text":uiScriptLocale.COSTUME_WINDOW_TITLE, "text_horizontal_align":"center" },
					),
				},

				## Equipment Slot
				{
					"name" : "Costume_Base",
					"type" : "image",

					"x" : 13,
					"y" : 38,

					"image" : "d:/ymir work/ui/costume/costume_bg.jpg",
				},
				{
					"name" : "CostumeSlot",
					"type" : "slot",

					"x" : 16,
					"y" : 41,

					"width" : 190,
					"height" : 145,

					"slot" : (
								{"index":COSTUME_START_INDEX+0, "x":61, "y":45, "width":32, "height":64},
								{"index":COSTUME_START_INDEX+1, "x":61, "y": 8, "width":32, "height":32},
							),
				},

				## The switches (OLD's Activate*_ON_OFF; Activate4 was OLD's mask, not
				## ported, and Activate5 is the sash's, which OLD had in the inventory).
				switch("Activate_ON_OFF", 13, 176, uiScriptLocale.COSTUME_SHOW_BODY),
				switch("Activate1_ON_OFF", 77, 176, uiScriptLocale.COSTUME_SHOW_HAIR),
				switch("Activate2_ON_OFF", 141, 176, uiScriptLocale.COSTUME_SHOW_WEAPON),
				switch("Activate5_ON_OFF", 13, 200, uiScriptLocale.COSTUME_SHOW_SASH),
				switch("Activate3_ON_OFF", 77, 200, uiScriptLocale.COSTUME_SHOW_AURA),
			),
		},
	),
}
