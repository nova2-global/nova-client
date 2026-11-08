import uiScriptLocale

## OLD's uiscript/petrefineattrwindow.py (NOVA-24, the 0.2 pack): a pet
## bonus's upgrade (uipet.PetAttrRefineWindow). OLD's names and content geometry;
## OLD's "board_new" and "newtitlebar" (its NewUI skin, which NEW lacks) are
## NEW's board and title bar, and OLD's English labels are locale keys
## ("Requirments" spelled right).
REFINE_WINDOW_WIDTH = 260
REFINE_WINDOW_HEIGHT = 330
SLOTBAR_LINE = 0xff513410
SLOTBAR_CENTER = 0xff100708
BUTTON = "d:/ymir work/ui/pattern/NewUI/buttons/big_thin_button_0%d.sub"

window = {
	"name" : "PetAttrRefineWindow",
	"style" : ("movable", "float",),
	"x" : SCREEN_WIDTH // 2 - REFINE_WINDOW_WIDTH // 2,
	"y" : SCREEN_HEIGHT // 2 - REFINE_WINDOW_HEIGHT // 2,
	"width" : REFINE_WINDOW_WIDTH,
	"height" : REFINE_WINDOW_HEIGHT,
	"children" :
	(
		{
			"name" : "board",
			"type" : "board",
			"style" : ("attach",),
			"x" : 0,
			"y" : 0,
			"width" : REFINE_WINDOW_WIDTH,
			"height" : REFINE_WINDOW_HEIGHT,
			"children" :
			(
				{
					"name" : "TitleBar",
					"type" : "titlebar",
					"style" : ("attach",),
					"x" : 6,
					"y" : 6,
					"width" : REFINE_WINDOW_WIDTH - 12,
					"color" : "yellow",
					"children" :
					(
						{
							"name" : "TitleName",
							"type" : "text",
							"x" : 0,
							"y" : 0,
							"text" : uiScriptLocale.REFINE_TTILE,
							"all_align" : "center",
						},
					),
				},
				{
					"name" : "top_window",
					"type" : "slotbar",
					"x" : 0,
					"y" : 45,
					"horizontal_align" : "center",
					"width" : 230,
					"height" : 150,
					"lcolor" : SLOTBAR_LINE,
					"rcolor" : SLOTBAR_LINE,
					"ccolor" : SLOTBAR_CENTER,
					"children" :
					(
						{
							"name" : "attr_txt",
							"type" : "text",
							"x" : 0,
							"y" : 10,
							"text" : "",
							"fontname" : "Tahoma:18",
							"horizontal_align" : "center",
							"text_horizontal_align" : "center",
						},
						{
							"name" : "current_txt",
							"type" : "text",
							"x" : 30,
							"y" : 40,
							"text" : uiScriptLocale.PET_UI_CURRENT_VALUE,
							"fontname" : "Tahoma:16",
							"horizontal_align" : "left",
							"text_horizontal_align" : "left",
						},
						{
							"name" : "level_current",
							"type" : "text",
							"x" : 30,
							"y" : 40,
							"text" : "",
							"horizontal_align" : "right",
							"text_horizontal_align" : "right",
						},
						{
							"name" : "attr_bonus_current",
							"type" : "text",
							"x" : 30,
							"y" : 65,
							"text" : "",
							"horizontal_align" : "right",
							"text_horizontal_align" : "right",
						},
						{
							"name" : "arrow-line-left",
							"type" : "line",
							"x" : 10,
							"y" : 90,
							"width" : 90,
							"height" : 0,
							"color" : 0xFF4F3611,
							"horizontal_align" : "left",
						},
						{
							"name" : "arrow-line-right",
							"type" : "line",
							"x" : 100,
							"y" : 90,
							"width" : 90,
							"height" : 0,
							"color" : 0xFF4F3611,
							"horizontal_align" : "right",
						},
						{
							"name" : "arrow",
							"type" : "image",
							"x" : 0,
							"y" : 75,
							"image" : "d:/ymir work/ui/pet/arrow_down.png",
							"horizontal_align" : "center",
						},
						{
							"name" : "next_txt",
							"type" : "text",
							"x" : 30,
							"y" : 100,
							"text" : uiScriptLocale.PET_UI_NEXT_VALUE,
							"fontname" : "Tahoma:16",
							"horizontal_align" : "left",
							"text_horizontal_align" : "left",
						},
						{
							"name" : "level_next",
							"type" : "text",
							"x" : 30,
							"y" : 100,
							"text" : "",
							"horizontal_align" : "right",
							"text_horizontal_align" : "right",
						},
						{
							"name" : "attr_bonus_next",
							"type" : "text",
							"x" : 30,
							"y" : 125,
							"text" : "",
							"horizontal_align" : "right",
							"text_horizontal_align" : "right",
						},
					),
				},
				{
					"name" : "material_window",
					"type" : "slotbar",
					"x" : 0,
					"y" : 200,
					"horizontal_align" : "center",
					"width" : 230,
					"height" : 72,
					"lcolor" : SLOTBAR_LINE,
					"rcolor" : SLOTBAR_LINE,
					"ccolor" : SLOTBAR_CENTER,
					"children" :
					(
						{
							"name" : "Requirments",
							"type" : "text",
							"x" : 0,
							"y" : -6,
							"text" : uiScriptLocale.PET_UI_REQUIREMENTS,
							"horizontal_align" : "center",
							"text_horizontal_align" : "center",
						},
						{
							"name" : "cost",
							"type" : "text",
							"x" : 0,
							"y" : 52,
							"text" : "",
							"horizontal_align" : "center",
							"text_horizontal_align" : "center",
						},
					),
				},
				{
					"name" : "upgrade",
					"type" : "button",
					"x" : -54,
					"y" : 285,
					"horizontal_align" : "center",
					"text" : uiScriptLocale.PET_REFINE_BUTTON,
					"default_image" : BUTTON % 1,
					"over_image" : BUTTON % 2,
					"down_image" : BUTTON % 3,
				},
				{
					"name" : "cancel",
					"type" : "button",
					"x" : 54,
					"y" : 285,
					"horizontal_align" : "center",
					"text" : uiScriptLocale.CANCEL,
					"default_image" : BUTTON % 1,
					"over_image" : BUTTON % 2,
					"down_image" : BUTTON % 3,
				},
			),
		},
	),
}
