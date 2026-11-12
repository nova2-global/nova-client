import uiScriptLocale

## The NPC shop's mark board (NOVA-187; OLD uiscript markwindow.py without its
## image hint): the marked items' total and Sell, under the shop.
window = {
	"name" : "MarkWindow",

	"x" : 0,
	"y" : 0,

	"style" : ("float",),

	"width" : 173,
	"height" : 70,

	"children" :
	(
		{
			"name" : "board",
			"type" : "board",
			"style" : ("attach",),

			"x" : 0,
			"y" : 0,

			"width" : 173,
			"height" : 70,

			"children" :
			(
				{
					"name" : "GoldImage",
					"type" : "image",
					"x" : 28,
					"y" : 13,
					"image" : "d:/ymir work/ui/public/parameter_slot_05.sub",

					"children" :
					(
						{
							"name" : "Money",
							"type" : "text",
							"x" : 3,
							"y" : 3,
							"horizontal_align" : "right",
							"text_horizontal_align" : "right",
							"text" : "0 Yang",
						},
					),
				},
				{
					"name" : "GoldIcon",
					"type" : "image",
					"x" : 9,
					"y" : 15,
					"image" : "d:/ymir work/ui/game/windows/money_icon.sub",
				},
				{
					"name" : "SellMarkedButton",
					"type" : "button",
					"x" : 0,
					"y" : 38,
					"text" : uiScriptLocale.SHOP_SELL,
					"horizontal_align" : "center",
					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},
			),
		},
	),
}
