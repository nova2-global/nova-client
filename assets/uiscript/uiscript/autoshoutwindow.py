## The auto-shout window (NOVA-204; OLD uiChat.py:1571-1840 AutoShoutWindow,
## which built it in code): the message, its state and the countdown, Start
## or Stop. uiautoshout.py AutoShoutWindow loads it.
import localeInfo

WIDTH = 330
HEIGHT = 160

window = {
	"name" : "AutoShoutWindow",
	"style" : ("movable", "float",),

	"x" : 0,
	"y" : 0,

	"width" : WIDTH,
	"height" : HEIGHT,

	"children" :
	(
		{
			"name" : "board",
			"type" : "board_with_titlebar",

			"x" : 0,
			"y" : 0,

			"width" : WIDTH,
			"height" : HEIGHT,

			"title" : localeInfo.AUTO_SHOUT_TITLE,

			"children" :
			(
				{
					"name" : "desc",
					"type" : "text",

					"x" : 15,
					"y" : 34,

					"text" : localeInfo.AUTO_SHOUT_DESC,
				},
				{
					"name" : "message_label",
					"type" : "text",

					"x" : 15,
					"y" : 64,

					"text" : localeInfo.AUTO_SHOUT_MESSAGE,
				},
				{
					"name" : "message_slot",
					"type" : "slotbar",

					"x" : 15,
					"y" : 80,

					"width" : WIDTH - 30,
					"height" : 18,

					"children" :
					(
						{
							"name" : "message",
							"type" : "editline",

							"x" : 3,
							"y" : 3,

							"width" : WIDTH - 36,
							"height" : 15,

							"input_limit" : 255,
						},
					),
				},
				{
					"name" : "status",
					"type" : "text",

					"x" : 15,
					"y" : 104,

					"text" : localeInfo.AUTO_SHOUT_STATUS_OFF,
				},
				{
					"name" : "next",
					"type" : "text",

					"x" : 100,
					"y" : 104,

					"text" : "",
				},
				{
					"name" : "toggle",
					"type" : "button",

					"x" : (WIDTH - 88) // 2,
					"y" : 130,

					"text" : localeInfo.AUTO_SHOUT_START,

					"default_image" : "d:/ymir work/ui/public/large_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/large_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/large_button_03.sub",
				},
			),
		},
	),
}
