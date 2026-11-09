import uiScriptLocale

## OLD's uiscript/DamageCount.py (NOVA-27, __BOSS_DAMAGE_COUNT__), its
## geometry and names. OLD's art (ui/game/damage_count/hpbar_empty.sub,
## hpbar_full.sub, x_button*.tga and the boss faces) is not in NEW's packs:
## the board is the thin board, the HP bar the red public gauge, the exit
## button the public close button, and the boss's name stands where its face
## was (targetName).

WINDOW_WIDTH = 392
WINDOW_HEIGHT = 300

window = {
	"name" : "DamageCountWindow",
	"x" : (SCREEN_WIDTH - WINDOW_WIDTH) // 2,
	"y" : 70,

	"style" : ("movable", "float",),

	"width" : WINDOW_WIDTH,
	"height" : WINDOW_HEIGHT,

	"children" :
	(
		{
			"name" : "board",
			"type" : "thinboard",
			"style" : ("attach",),
			"x" : 0,
			"y" : 0,

			"width" : WINDOW_WIDTH,
			"height" : WINDOW_HEIGHT,

			"children" :
			(
				{
					"name" : "targetName",
					"type" : "text",
					"x" : 10, "y" : 10,
					"text" : "",
				},
				{
					"name" : "gaugeImageBack",
					"type" : "window",

					"x" : 106,
					"y" : 25,
					"width" : 180,
					"height" : 20,

					"children" :
					(
						{
							"name" : "gaugeImage",
							"type" : "gauge",

							"x" : 0,
							"y" : 5,
							"width" : 180,
							"color" : "red",
						},
						{
							"name" : "hp",
							"type" : "text",
							"x" : 90, "y" : -15,
							"text_horizontal_align" : "center",

							"text" : "",
						},
						{
							"name" : "hp_perc",
							"type" : "text",
							"x" : 186, "y" : 2,

							"text_horizontal_align" : "left",
							"text" : "",
						},
					),
				},
				{
					"name" : "exit",
					"type" : "button",
					"x" : 370, "y" : 10,
					"default_image" : "d:/ymir work/ui/public/close_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/close_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/close_button_03.sub",
				},
				{
					"type" : "listboxex",
					"name" : "list",
					"width" : 392,
					"height" : 225,
					"itemsize_x" : 392,
					"itemsize_y" : 25,
					"viewcount" : 10,
					"itemstep" : 25,
					"x" : 6,
					"y" : 60,
				},
			),
		},
	),
}
