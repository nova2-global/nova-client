import uiScriptLocale

## OLD's uiscript/petevolutionwindow.py (NOVA-24, the 0.2 pack): the pet's
## evolution (uipet.PetEvolutionWindow). OLD's names and content geometry;
## OLD's "board_new" and "newtitlebar" (its NewUI skin, which NEW lacks) are
## NEW's board and title bar, and OLD's English labels are locale keys
## ("Requirments" spelled right).
EVOLUTION_WINDOW_WIDTH = 260
EVOLUTION_WINDOW_HEIGHT = 330
SLOTBAR_LINE = 0xff513410
SLOTBAR_CENTER = 0xff100708
BUTTON = "d:/ymir work/ui/pattern/NewUI/buttons/big_thin_button_0%d.sub"

window = {
	"name" : "PetEvolutionWindow",
	"style" : ("movable", "float",),
	"x" : SCREEN_WIDTH // 2 - EVOLUTION_WINDOW_WIDTH // 2,
	"y" : SCREEN_HEIGHT // 2 - EVOLUTION_WINDOW_HEIGHT // 2,
	"width" : EVOLUTION_WINDOW_WIDTH,
	"height" : EVOLUTION_WINDOW_HEIGHT,
	"children" :
	(
		{
			"name" : "board",
			"type" : "board",
			"style" : ("attach",),
			"x" : 0,
			"y" : 0,
			"width" : EVOLUTION_WINDOW_WIDTH,
			"height" : EVOLUTION_WINDOW_HEIGHT,
			"children" :
			(
				{
					"name" : "TitleBar",
					"type" : "titlebar",
					"style" : ("attach",),
					"x" : 6,
					"y" : 6,
					"width" : EVOLUTION_WINDOW_WIDTH - 12,
					"color" : "yellow",
					"children" :
					(
						{
							"name" : "TitleName",
							"type" : "text",
							"x" : 0,
							"y" : 0,
							"text" : uiScriptLocale.PET_EVOLUTION_TITLE,
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
							"name" : "item",
							"type" : "image",
							"x" : 15,
							"y" : 10,
							"image" : "d:/ymir work/ui/public/slot_base.sub",
						},
						{
							"name" : "top-line",
							"type" : "line",
							"x" : 28,
							"y" : 37,
							"width" : 150,
							"height" : 0,
							"color" : 0xFF4F3611,
							"horizontal_align" : "center",
						},
						{
							"name" : "pet_name",
							"type" : "text",
							"x" : -30,
							"y" : 15,
							"text" : "",
							"fontname" : "Tahoma:16",
							"horizontal_align" : "center",
							"text_horizontal_align" : "center",
						},
						{
							"name" : "evolve_current_txt",
							"type" : "text",
							"x" : -30,
							"y" : 55,
							"text" : uiScriptLocale.PET_UI_CURRENT,
							"horizontal_align" : "center",
							"text_horizontal_align" : "right",
						},
						{
							"name" : "evolve_current",
							"type" : "text",
							"x" : -30,
							"y" : 75,
							"text" : "",
							"horizontal_align" : "center",
							"text_horizontal_align" : "right",
						},
						{
							"name" : "arrow",
							"type" : "image",
							"x" : 0,
							"y" : 70,
							"image" : "d:/ymir work/ui/pet/arrow.png",
							"horizontal_align" : "center",
						},
						{
							"name" : "evolve_next_txt",
							"type" : "text",
							"x" : 30,
							"y" : 55,
							"text" : uiScriptLocale.PET_UI_NEXT_EVOLUTION,
							"horizontal_align" : "center",
							"text_horizontal_align" : "left",
						},
						{
							"name" : "evolve_next",
							"type" : "text",
							"x" : 30,
							"y" : 75,
							"text" : "",
							"horizontal_align" : "center",
							"text_horizontal_align" : "left",
						},
						{
							"name" : "active_skill_count_current",
							"type" : "text",
							"x" : -30,
							"y" : 105,
							"text" : "",
							"horizontal_align" : "center",
							"text_horizontal_align" : "right",
						},
						{
							"name" : "passive_skill_count_current",
							"type" : "text",
							"x" : -30,
							"y" : 125,
							"text" : "",
							"horizontal_align" : "center",
							"text_horizontal_align" : "right",
						},
						{
							"name" : "active_skill_count_next",
							"type" : "text",
							"x" : 30,
							"y" : 105,
							"text" : "",
							"horizontal_align" : "center",
							"text_horizontal_align" : "left",
						},
						{
							"name" : "passive_skill_count_next",
							"type" : "text",
							"x" : 30,
							"y" : 125,
							"text" : "",
							"horizontal_align" : "center",
							"text_horizontal_align" : "left",
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
					"name" : "evolve",
					"type" : "button",
					"x" : -54,
					"y" : 285,
					"horizontal_align" : "center",
					"text" : uiScriptLocale.PET_EVOLVE_BUTTON,
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
