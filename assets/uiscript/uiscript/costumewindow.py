import uiScriptLocale
import item

COSTUME_START_INDEX = item.COSTUME_SLOT_START
## OLD's other costume cells this window shows (OLD uiscript/costumewindow.py),
## counted from the costume body (wear 19) as OLD's GameType.h counts them:
## the costume sash (wear 21, item.COSTUME_SLOT_SASH; NOVA-20; OLD showed it in
## the inventory's equipment panel), the weapon costume (wear 22,
## item.COSTUME_SLOT_WEAPON; NOVA-21) and the aura costume (wear 39,
## item.COSTUME_SLOT_AURA; NOVA-23). Wear 23-27 (mount, effects, pet, wings)
## hold features that are not ported: their slots stay hidden.
SASH_SLOT_INDEX = COSTUME_START_INDEX + 2
WEAPON_SLOT_INDEX = COSTUME_START_INDEX + 3
AURA_SLOT_INDEX = COSTUME_START_INDEX + 20

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
				## The new cells stand on the public slot base, beside the body.
				{ "name" : "Weapon_Base", "type" : "image", "x" : 134, "y" : 49, "image" : BUTTON_PATH + "Slot_Base.sub" },
				{ "name" : "Weapon_Base2", "type" : "image", "x" : 134, "y" : 81, "image" : BUTTON_PATH + "Slot_Base.sub" },
				{ "name" : "Weapon_Base3", "type" : "image", "x" : 134, "y" : 113, "image" : BUTTON_PATH + "Slot_Base.sub" },
				{ "name" : "Sash_Base", "type" : "image", "x" : 172, "y" : 49, "image" : BUTTON_PATH + "Slot_Base.sub" },
				{ "name" : "Aura_Base", "type" : "image", "x" : 172, "y" : 89, "image" : BUTTON_PATH + "Slot_Base.sub" },
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
								{"index":WEAPON_SLOT_INDEX, "x":118, "y":8, "width":32, "height":96},
								{"index":SASH_SLOT_INDEX, "x":156, "y":8, "width":32, "height":32},
								{"index":AURA_SLOT_INDEX, "x":156, "y":48, "width":32, "height":32},
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
