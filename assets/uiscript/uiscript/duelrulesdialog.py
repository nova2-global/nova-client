import uiScriptLocale

ROOT = "d:/ymir work/ui/public/"

## The duel rules board (NOVA-28; OLD uiTarget.py AdvancedDuel, 148-246): the
## challenger ticks the rules and sends the challenge. OLD drew it in code on its
## own art (ui/advanced_duel/*), which is not in NEW's packs; here it is a board
## with a title bar, OLD's 355 wide, the ten rules' check boxes made in code in
## two columns (uiduel.py RULE_POSITION), and OLD's two buttons.

window = {
	"name" : "DuelRulesDialog",
	"style" : ("movable", "float",),

	"x" : (SCREEN_WIDTH - 355) / 2,
	"y" : 80,

	"width" : 355,
	"height" : 180,

	"children" :
	(
		{
			"name" : "board",
			"type" : "board",
			"style" : ("attach",),

			"x" : 0,
			"y" : 0,

			"width" : 355,
			"height" : 180,

			"children" :
			(
				{
					"name" : "TitleBar",
					"type" : "titlebar",
					"style" : ("attach",),

					"x" : 8,
					"y" : 7,

					"width" : 340,
					"color" : "yellow",

					"children" :
					(
						{ "name" : "TitleName", "type" : "text", "x" : 0, "y" : 3, "text" : uiScriptLocale.DUEL_RULES_TITLE, "horizontal_align" : "center", "text_horizontal_align" : "center" },
					),
				},
				{
					"name" : "accept_button",
					"type" : "button",

					"x" : -50,
					"y" : 40,

					"horizontal_align" : "center",
					"vertical_align" : "bottom",

					"text" : uiScriptLocale.DUEL_RULES_ACCEPT,

					"default_image" : ROOT + "Middle_Button_01.sub",
					"over_image" : ROOT + "Middle_Button_02.sub",
					"down_image" : ROOT + "Middle_Button_03.sub",
				},
				{
					"name" : "cancel_button",
					"type" : "button",

					"x" : 50,
					"y" : 40,

					"horizontal_align" : "center",
					"vertical_align" : "bottom",

					"text" : uiScriptLocale.CANCEL,

					"default_image" : ROOT + "Middle_Button_01.sub",
					"over_image" : ROOT + "Middle_Button_02.sub",
					"down_image" : ROOT + "Middle_Button_03.sub",
				},
			),
		},
	),
}
