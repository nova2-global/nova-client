import uiScriptLocale

BUTTON_START_X_POS = -60
BUTTON_X_STEP = 40

window = {
	"name" : "MessengerWindow",

	"x" : SCREEN_WIDTH - 200,
	"y" : SCREEN_HEIGHT - 400 - 50,

	"style" : ("movable", "float",),

	"width" : 170,
	"height" : 300,

	"children" :
	(

		{
			"name" : "board",
			"type" : "board_with_titlebar",

			"x" : 0,
			"y" : 0,

			"width" : 170,
			"height" : 300,
			"title" : uiScriptLocale.MESSENGER_TITLE,
		},

		{
			"name" : "ScrollBar",
			"type" : "scrollbar",

			"x" : 27,
			"y" : 40,
			"size" : 100,
			"horizontal_align" : "right",
		},

		{
			"name" : "AddFriendButton",
			"type" : "button",

			"x" : BUTTON_START_X_POS + BUTTON_X_STEP*0,
			"y" : 30,
			"horizontal_align" : "center",
			"vertical_align" : "bottom",
			"tooltip_text" : uiScriptLocale.MESSENGER_ADD_FRIEND,
			"tooltip_x" : 0,
			"tooltip_y" : 35,

			"default_image" : "d:/ymir work/ui/game/windows/messenger_add_friend_01.sub",
			"over_image" : "d:/ymir work/ui/game/windows/messenger_add_friend_02.sub",
			"down_image" : "d:/ymir work/ui/game/windows/messenger_add_friend_03.sub",
			"disable_image" : "d:/ymir work/ui/game/windows/messenger_add_friend_04.sub",
		},

		{
			"name" : "WhisperButton",
			"type" : "button",

			"x" : BUTTON_START_X_POS + BUTTON_X_STEP*1,
			"y" : 30,
			"horizontal_align" : "center",
			"vertical_align" : "bottom",
			"tooltip_text" : uiScriptLocale.MESSENGER_WHISPER,
			"tooltip_x" : 0,
			"tooltip_y" : 35,

			"default_image" : "d:/ymir work/ui/game/windows/messenger_whisper_01.sub",
			"over_image" : "d:/ymir work/ui/game/windows/messenger_whisper_02.sub",
			"down_image" : "d:/ymir work/ui/game/windows/messenger_whisper_03.sub",
			"disable_image" : "d:/ymir work/ui/game/windows/messenger_whisper_04.sub",
		},
		{
			"name" : "RemoveButton",
			"type" : "button",

			"x" : BUTTON_START_X_POS + BUTTON_X_STEP*2,
			"y" : 30,
			"horizontal_align" : "center",
			"vertical_align" : "bottom",
			"tooltip_text" : uiScriptLocale.MESSENGER_DELETE_FRIEND,
			"tooltip_x" : 0,
			"tooltip_y" : 35,

			"default_image" : "d:/ymir work/ui/game/windows/messenger_delete_01.sub",
			"over_image" : "d:/ymir work/ui/game/windows/messenger_delete_02.sub",
			"down_image" : "d:/ymir work/ui/game/windows/messenger_delete_03.sub",
			"disable_image" : "d:/ymir work/ui/game/windows/messenger_delete_04.sub",
		},

		## The block list (NOVA-47): OLD's BlockPayerButton/UnblockPayerButton
		## (OLD messengerwindow.py:73-100) were icons between whisper and remove,
		## art that is in neither NEW's assets nor OLD's source tree. NEW's
		## small text buttons are wider than OLD's icons, so they take a row of
		## their own above the icon row (the window's list ends that much
		## higher, uimessenger.py BLOCK_BUTTON_ROW_HEIGHT); the art is open.
		{
			"name" : "BlockPlayerButton",
			"type" : "button",

			"x" : -24,
			"y" : 55,
			"horizontal_align" : "center",
			"vertical_align" : "bottom",
			"tooltip_text" : uiScriptLocale.BLOCK_PLAYER,
			"tooltip_x" : 0,
			"tooltip_y" : 35,

			"text" : uiScriptLocale.BLOCK_PLAYER,

			"default_image" : "d:/ymir work/ui/public/small_button_01.sub",
			"over_image" : "d:/ymir work/ui/public/small_button_02.sub",
			"down_image" : "d:/ymir work/ui/public/small_button_03.sub",
			"disable_image" : "d:/ymir work/ui/public/small_button_03.sub",
		},
		{
			"name" : "UnblockPlayerButton",
			"type" : "button",

			"x" : 24,
			"y" : 55,
			"horizontal_align" : "center",
			"vertical_align" : "bottom",
			"tooltip_text" : uiScriptLocale.UNBLOCK_PLAYER,
			"tooltip_x" : 0,
			"tooltip_y" : 35,

			"text" : uiScriptLocale.UNBLOCK_PLAYER,

			"default_image" : "d:/ymir work/ui/public/small_button_01.sub",
			"over_image" : "d:/ymir work/ui/public/small_button_02.sub",
			"down_image" : "d:/ymir work/ui/public/small_button_03.sub",
			"disable_image" : "d:/ymir work/ui/public/small_button_03.sub",
		},

		{
			"name" : "GuildButton",
			"type" : "button",

			"x" : BUTTON_START_X_POS + BUTTON_X_STEP*3,
			"y" : 30,
			"horizontal_align" : "center",
			"vertical_align" : "bottom",
			"tooltip_text" : uiScriptLocale.MESSENGER_OPEN_GUILD,
			"tooltip_x" : 0,
			"tooltip_y" : 35,

			"default_image" : "d:/ymir work/ui/game/windows/messenger_guild_01.sub",
			"over_image" : "d:/ymir work/ui/game/windows/messenger_guild_02.sub",
			"down_image" : "d:/ymir work/ui/game/windows/messenger_guild_03.sub",
			"disable_image" : "d:/ymir work/ui/game/windows/messenger_guild_04.sub",
		},

	),
}