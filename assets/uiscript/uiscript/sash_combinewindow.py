import uiScriptLocale

## OLD's uiscript/sash_combinewindow.py (NOVA-20), its geometry and names.
## OLD's background (locale/common/ui/acce/acce_combine.tga) is not in NEW's
## packs: each slot stands on the public slot base, its name under it.
SLOT_BASE = "d:/ymir work/ui/public/Slot_Base.sub"

window = {
	"name" : "Sash_CombineWindow",
	"x" : (SCREEN_WIDTH - 215) // 2,
	"y" : (SCREEN_HEIGHT - 280) // 2,
	"style" : ("movable", "float",),
	"width" : 215,
	"height" : 280,
	"children" :
	(
		{
			"name" : "board",
			"type" : "board",
			"style" : ("attach",),
			"x" : 0,
			"y" : 0,
			"width" : 215,
			"height" : 280,
			"children" :
			(
				{
					"name" : "TitleBar",
					"type" : "titlebar",
					"style" : ("attach",),
					"x" : 6,
					"y" : 6,
					"width" : 200,
					"color" : "yellow",
					"children" :
					(
						{
							"name" : "TitleName",
							"type" : "text",
							"x" : 95,
							"y" : 3,
							"text" : uiScriptLocale.SASH_COMBINE,
							"text_horizontal_align" : "center"
						},
					),
				},
				{
					"name" : "Sash_Combine",
					"type" : "window",
					"x" : 9,
					"y" : 35,
					"width" : 200,
					"height" : 180,
					"children" :
					(
						{ "name" : "SlotBase0", "type" : "image", "x" : 81, "y" : 10, "image" : SLOT_BASE },
						{ "name" : "SlotBase1", "type" : "image", "x" : 81, "y" : 63, "image" : SLOT_BASE },
						{ "name" : "SlotBase2", "type" : "image", "x" : 81, "y" : 118, "image" : SLOT_BASE },
						{
							"name" : "SashSlot",
							"type" : "slot",
							"x" : 3,
							"y" : 3,
							"width" : 200,
							"height" : 150,
							"slot" : (
										{"index":0, "x":78, "y":7, "width":32, "height":32},
										{"index":1, "x":78, "y":60, "width":32, "height":32},
										{"index":2, "x":78, "y":115, "width":32, "height":32},
							),
						},
						{
							"name" : "Main",
							"type" : "text",
							"text" : uiScriptLocale.SASH_MAIN,
							"text_horizontal_align":"center",
							"x" : 85 + 12,
							"y" : 7 + 36,
						},
						{
							"name" : "serve",
							"type" : "text",
							"text" : uiScriptLocale.SASH_SERVE,
							"text_horizontal_align" : "center",
							"x" : 85 + 12,
							"y" : 60 + 38,
						},
						{
							"name" : "Result",
							"type" : "text",
							"text" : uiScriptLocale.SASH_RESULT,
							"text_horizontal_align":"center",
							"x" : 85 + 12,
							"y" : 115 + 40
						},
					),
				},
				{
					"name" : "NeedMoney",
					"type" : "text",
					"text" : "",
					"text_horizontal_align" : "center",
					"x" : 105,
					"y" : 235,
				},
				{
					"name" : "AcceptButton",
					"type" : "button",
					"x" : 40,
					"y" : 255,
					"text" : uiScriptLocale.OK,
					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},
				{
					"name" : "CancelButton",
					"type" : "button",
					"x" : 114,
					"y" : 255,
					"text" : uiScriptLocale.CANCEL,
					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},
			),
		},
	),
}
