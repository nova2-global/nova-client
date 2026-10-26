import uiScriptLocale
import guild

window = {
	"name" : "InputDialog",

	"x" : 0,
	"y" : 0,

	"style" : ("movable", "float",),

	"width" : 230,
	"height" : 170,

	"children" :
	(
		{
			"name" : "Board",
			"type" : "board_with_titlebar",

			"x" : 0,
			"y" : 0,

			"width" : 230,
			"height" : 170,

			"title" : uiScriptLocale.GUILD_WAR_DECLARE,

			"children" :
			(
				## Input Slot
				{
					"name" : "InputName",
					"type" : "text",

					"x" : 15,
					"y" : 40,

					"text" : uiScriptLocale.GUILD_WAR_ENEMY,
				},
				{
					"name" : "InputSlot",
					"type" : "slotbar",

					"x" : 80,
					"y" : 37,
					"width" : 130,
					"height" : 18,

					"children" :
					(
						{
							"name" : "InputValue",
							"type" : "editline",

							"x" : 3,
							"y" : 3,

							"width" : 90,
							"height" : 18,

							# The enemy guild's name: up to 24 characters since the foundation
							# cut (the client's guild.GUILD_NAME_MAX_LEN, as AskGuildName).
							"input_limit" : guild.GUILD_NAME_MAX_LEN,
						},
					),
				},
				## The war's member cap and end score (NOVA-90), OLD's rows
				## (OLD declareguildwardialog.py:70-133); uiguild sends them with
				## the declaration.
				{
					"name" : "InputMemberCount",
					"type" : "text",

					"x" : 15,
					"y" : 70,

					"text" : uiScriptLocale.GUILD_WAR_ENEMY_NUMBER,
				},
				{
					"name" : "MemberCountInput",
					"type" : "slotbar",

					"x" : 85,
					"y" : 67,
					"width" : 28,
					"height" : 18,

					"children" :
					(
						{
							"name" : "MemberInputValue",
							"type" : "editline",

							"x" : 3,
							"y" : 3,

							"width" : 30,
							"height" : 18,

							"input_limit" : 3,
						},
					),
				},
				{
					"name" : "InputScoreCount",
					"type" : "text",

					"x" : 122,
					"y" : 70,

					"text" : uiScriptLocale.GUILD_WAR_MAX_SCORE,
				},
				{
					"name" : "EndScoreInput",
					"type" : "slotbar",

					"x" : 180,
					"y" : 67,
					"width" : 30,
					"height" : 18,

					"children" :
					(
						{
							"name" : "EndScoreInputValue",
							"type" : "editline",

							"x" : 3,
							"y" : 3,

							"width" : 28,
							"height" : 18,

							"input_limit" : 3,
						},
					),
				},
				## Input Slot
				{
					"name" : "GameType", "x" : 15, "y" : 100, "width" : 65+45*4, "height" : 20,
					
					"children" :
					(
						{"name" : "GameTypeLabel", "type" : "text", "x" : 0, "y" : 3, "text" : uiScriptLocale.GUILD_WAR_BATTLE_TYPE,},
						{
							"name" : "NormalButton",
							"type" : "radio_button",

							"x" : 65,
							"y" : 0,

							"text" : uiScriptLocale.GUILD_WAR_NORMAL,

							"default_image" : "d:/ymir work/ui/public/small_button_01.sub",
							"over_image" : "d:/ymir work/ui/public/small_button_02.sub",
							"down_image" : "d:/ymir work/ui/public/small_button_03.sub",
						},
						{
							"name" : "WarpButton",
							"type" : "radio_button",

							"x" : 65+45*1,
							"y" : 0,

							"text" : uiScriptLocale.GUILD_WAR_WARP,
							
							"default_image" : "d:/ymir work/ui/public/small_button_01.sub",
							"over_image" : "d:/ymir work/ui/public/small_button_02.sub",
							"down_image" : "d:/ymir work/ui/public/small_button_03.sub",
						},
						{
							"name" : "CTFButton",
							"type" : "radio_button",

							"x" : 65+45*2,
							"y" : 0,

							"text" : uiScriptLocale.GUILD_WAR_CTF,

							"default_image" : "d:/ymir work/ui/public/small_button_01.sub",
							"over_image" : "d:/ymir work/ui/public/small_button_02.sub",
							"down_image" : "d:/ymir work/ui/public/small_button_03.sub",
						},
					),
				},
				## Button
				{
					"name" : "AcceptButton",
					"type" : "button",

					"x" : - 61 - 5 + 30,
					"y" : 130,
					"horizontal_align" : "center",

					"text" : uiScriptLocale.OK,

					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},
				{
					"name" : "CancelButton",
					"type" : "button",

					"x" : 5 + 30,
					"y" : 130,
					"horizontal_align" : "center",

					"text" : uiScriptLocale.CANCEL,

					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},
			),
		},
	),
}
