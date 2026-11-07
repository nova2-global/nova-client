import uiScriptLocale

## OLD's uiscript/aura_levelupwindow.py (NOVA-23), its geometry and names.
## OLD's background (d:/ymir work/ui/aura/aura_levelup_bg.sub) is not in NEW's
## packs: each slot stands on the public slot base. OLD's literal title and
## accept text are locale keys.
SLOT_BASE = "d:/ymir work/ui/public/Slot_Base.sub"

window = {
	"name" : "Aura_RefineWindow",
	"x" : (SCREEN_WIDTH - 248) // 2,
	"y" : (SCREEN_HEIGHT - 230) // 2,
	"style" : ("movable", "float",),
	"width" : 248,
	"height" : 265,
	"children" :
	(
		{
			"name" : "board",
			"type" : "board",
			"style" : ("attach",),
			"x" : 0,
			"y" : 0,
			"width" : 248,
			"height" : 265,

			"children" :
			(
				## Title
				{
					"name" : "TitleBar",
					"type" : "titlebar",
					"style" : ("attach",),
					"x" : 6,
					"y" : 6,
					"width" : 235,
					"color" : "yellow",
					"children" :
					(
						{ "name":"TitleName", "type":"text", "x":117, "y":3, "text":uiScriptLocale.AURA_LEVELUP_TITLE, "text_horizontal_align":"center" },
					),
				},

				## Slots
				{
					"name" : "Aura_Levelup",
					"type" : "window",

					"x" : 13,
					"y" : 35,

					"width" : 222,
					"height" : 80,

					"children" :
					(
						## Main
						{"name" : "Main", "type" : "text", "x" : 66, "y" : 10, "text":uiScriptLocale.AURA_MAIN, "text_horizontal_align" : "center"},
						## Sub
						{"name" : "Sub", "type" : "text", "x" : 158, "y" : 10, "text":uiScriptLocale.AURA_SUB, "text_horizontal_align" : "center"},
						{"name" : "SlotBase0", "type" : "image", "x" : 49, "y" : 31, "image" : SLOT_BASE},
						{"name" : "SlotBase1", "type" : "image", "x" : 141, "y" : 31, "image" : SLOT_BASE},
						## Slot
						{
							"name" : "AuraSlot",
							"type" : "slot",

							"x" : 3,
							"y" : 3,

							"width" : 190,
							"height" : 80,

							"slot" : (
								{"index":0, "x":46, "y":28, "width":31, "height":31},
								{"index":1, "x":138, "y":28, "width":31, "height":31},
							),
						},
					),
				},

				## Level Text
				{"name" : "LevelText", "type" : "text", "x" : 124, "y" : 112, "text" : "", "text_horizontal_align" : "center"},

				## EXP Gauge Background
				{
					"name" : "ExpGaugeBG",
					"type" : "bar",
					"x" : 30,
					"y" : 132,
					"width" : 188,
					"height" : 12,
					"color" : 0xFF333333,
				},

				## EXP Gauge Fill
				{
					"name" : "ExpGaugeFill",
					"type" : "bar",
					"x" : 30,
					"y" : 132,
					"width" : 0,
					"height" : 12,
					"color" : 0xFF44AAFF,
				},

				## EXP Gauge Percentage Text (centered on gauge)
				{"name" : "ExpPercentText", "type" : "text", "x" : 124, "y" : 131, "text" : "", "text_horizontal_align" : "center"},

				## EXP Text
				{"name" : "ExpText", "type" : "text", "x" : 124, "y" : 150, "text" : "", "text_horizontal_align" : "center"},

				## Buttons
				{
					"name" : "AcceptButton",
					"type" : "button",
					"x" : 36,
					"y" : 215,
					"text" : uiScriptLocale.AURA_LEVELUP_BUTTON,
					"default_image" : "d:/ymir work/ui/public/large_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/large_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/large_button_03.sub",
				},
				{
					"name" : "CancelButton",
					"type" : "button",
					"x" : 124,
					"y" : 215,
					"text" : uiScriptLocale.CANCEL,
					"default_image" : "d:/ymir work/ui/public/large_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/large_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/large_button_03.sub",
				},
			),
		},
	),
}
