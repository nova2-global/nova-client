import localeInfo

## Change channel (NOVA-49): OLD's dialog (OLD uiscript/movechanneldialog.py).
## uisystem.MoveChannelDialog adds a button per channel to BlackBoard and the
## select and cancel buttons, and sizes the boards to them (the sizes here fit
## one channel). OLD's thinboard_circle is a thinboard here, which NEW's
## loader knows.
window = {
	"name" : "MoveChannelDialog",
	"style" : ("movable", "float",),

	"x" : (SCREEN_WIDTH/2) - (190/2),
	"y" : (SCREEN_HEIGHT/2) - 100,

	"width" : 190,
	"height" : 116,

	"children" :
	(
		## MainBoard
		{
			"name" : "MoveChannelBoard",
			"type" : "board",
			"style" : ("attach",),

			"x" : 0,
			"y" : 0,

			"width" : 190,
			"height" : 116,

			"children" :
			(
				## Title Bar
				{
					"name" : "MoveChannelTitle",
					"type" : "titlebar",
					"style" : ("attach",),

					"x" : 6, "y" : 7, "width" : 190 - 13,

					"children" :
					(
						{ "name" : "TitleName", "type" : "text", "x" : 0, "y" : 0, "text": localeInfo.MOVE_CHANNEL_TITLE, "all_align":"center" },
					),
				},

				{
					"name" : "BlackBoard",
					"type" : "thinboard",
					"x" : 13, "y" : 36, "width" : 190 - 26, "height" : 41,
				},
			),
		}, ## MainBoard End
	),
}
