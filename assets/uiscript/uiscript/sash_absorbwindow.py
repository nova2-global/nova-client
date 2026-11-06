import uiScriptLocale

## OLD's uiscript/sash_absorbwindow.py (NOVA-20), its geometry and names.
## OLD's background (locale/common/ui/acce/Acce_absorb.tga) is not in NEW's
## packs: each slot stands on the public slot base, its name under it.
SLOT_BASE = "d:/ymir work/ui/public/Slot_Base.sub"

window = {
	"name" : "Sash_AbsorbtionWindow",
	"x" : (SCREEN_WIDTH - 205) // 2,
	"y" : (SCREEN_HEIGHT - 270) // 2,
	"style" : ("movable", "float",),
	"width" : 205,
	"height" : 270,
	"children" :
	(
		{
			"name" : "board",
			"type" : "board",
			"style" : ("attach",),
			"x" : 0,
			"y" : 0,
			"width" : 205,
			"height" : 270,
			"children" :
			(
				{
					"name" : "TitleBar",
					"type" : "titlebar",
					"style" : ("attach",),
					"x" : 6,
					"y" : 6,
					"width" : 190,
					"color" : "yellow",
					"children" :
					(
						{
							"name":"TitleName",
							"type":"text",
							"x":95,
							"y":3,
							"text":uiScriptLocale.SASH_ABSORB,
							"text_horizontal_align":"center"
						},
					),
				},
				{
					"name" : "Sash_Combine",
					"type" : "window",
					"x" : 9,
					"y" : 35,
					"width" : 190,
					"height" : 205,
					"children" :
					(
						{ "name" : "SlotBase0", "type" : "image", "x" : 29, "y" : 44, "image" : SLOT_BASE },
						{ "name" : "SlotBase1", "type" : "image", "x" : 128, "y" : 11, "image" : SLOT_BASE },
						{ "name" : "SlotBase1b", "type" : "image", "x" : 128, "y" : 43, "image" : SLOT_BASE },
						{ "name" : "SlotBase1c", "type" : "image", "x" : 128, "y" : 75, "image" : SLOT_BASE },
						{ "name" : "SlotBase2", "type" : "image", "x" : 78, "y" : 129, "image" : SLOT_BASE },
						{
							"name" : "SashSlot",
							"type" : "slot",
							"x" : 3,
							"y" : 3,
							"width" : 190,
							"height" : 200,
							"slot" : (
										{"index":0, "x":26, "y":41, "width":31, "height":31},
										{"index":1, "x":125, "y":8, "width":31, "height":96},
										{"index":2, "x":75, "y":126, "width":31, "height":31},
							),
						},
						{
							"name" : "Main",
							"type" : "text",
							"text" : uiScriptLocale.SASH_MAIN,
							"text_horizontal_align" : "center",
							"x" : 42,
							"y" : 78,
						},
						{
							"name" : "Result",
							"type" : "text",
							"text" : uiScriptLocale.SASH_RESULT,
							"text_horizontal_align" : "center",
							"x" : 91,
							"y" : 163,
						},
					),
				},
				{
					"name" : "AcceptButton",
					"type" : "button",
					"x" : 40,
					"y" : 235,
					"text" : uiScriptLocale.OK,
					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},
				{
					"name" : "CancelButton",
					"type" : "button",
					"x" : 114,
					"y" : 235,
					"text" : uiScriptLocale.CANCEL,
					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},
			),
		},
	),
}
