import uiScriptLocale

## The select skill window (NOVA-37; OLD uiscript/selectskillwindow.py, 250 x 400): the two skill
## groups, each a row of six skills and the button that picks it. The model preview at 20, 225
## (225 x 150) is a ui.RenderTarget that uiSelectSkill makes, since it has no uiscript type here.

BOARD_WIDTH = 250
BOARD_HEIGHT = 400
ICON_SLOT_FILE = "d:/ymir work/ui/public/Slot_Base.sub"

window = {
	"name" : "SelectSkillWindow",
	"style" : ("movable", "float",),

	"x" : (SCREEN_WIDTH - BOARD_WIDTH) // 2,
	"y" : (SCREEN_HEIGHT - BOARD_HEIGHT) // 2,

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
						{ "name" : "TitleName", "type" : "text", "x" : 0, "y" : 4, "text" : uiScriptLocale.SELECT_CLASS, "horizontal_align" : "center", "text_horizontal_align" : "center" },
					),
				},
				{
					"name" : "1stButton",
					"type" : "button",

					"x" : 0,
					"y" : 105,
					"horizontal_align" : "center",

					"default_image" : "d:/ymir work/ui/public/xlarge_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/xlarge_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/xlarge_button_03.sub",

					"text" : "",
				},
				{
					"name" : "2ndButton",
					"type" : "button",

					"x" : 0,
					"y" : 185,
					"horizontal_align" : "center",

					"default_image" : "d:/ymir work/ui/public/xlarge_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/xlarge_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/xlarge_button_03.sub",

					"text" : "",
				},
				{
					"name" : "Skill_group_1",
					"type" : "grid_table",

					"x" : 22,
					"y" : 60,

					"start_index" : 0,
					"x_count" : 6,
					"y_count" : 1,
					"x_step" : 32,
					"y_step" : 32,
					"x_blank" : 5,
					"y_blank" : 4,

					"image" : ICON_SLOT_FILE,
				},
				{
					"name" : "Skill_group_2",
					"type" : "grid_table",

					"x" : 22,
					"y" : 140,

					"start_index" : 0,
					"x_count" : 6,
					"y_count" : 1,
					"x_step" : 32,
					"y_step" : 32,
					"x_blank" : 5,
					"y_blank" : 4,

					"image" : ICON_SLOT_FILE,
				},
			),
		},
	),
}
