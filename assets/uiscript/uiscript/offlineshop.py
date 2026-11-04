import uiScriptLocale

## The offline shop's owner panel (NOVA-9; OLD uiscript/offlineshop.py): a child of the shop window,
## under its grid. OLD's art (ui/offline_shop/*.png) is not in NEW's packs (Q9): the public buttons.
## The panel itself takes no mouse ("not_pick"), so the grid's cells stay reachable.

BUTTON_X = 270
LARGE_BUTTON_Y = 112

window = {
	"name" : "OfflineShopWindow",

	"x" : 0,
	"y" : 0,

	"style" : ("not_pick",),

	"width" : 345,
	"height" : 150,

	"children" :
	(
		## The sign and its rename
		{
			"name" : "ShopSignText",
			"type" : "text",

			"x" : 14,
			"y" : 4,

			"text" : "",
		},
		{
			"name" : "RenameButton",
			"type" : "button",

			"x" : BUTTON_X,
			"y" : 0,

			"text" : uiScriptLocale.OFFLINE_SHOP_BUTTON_RENAME,

			"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
			"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
			"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
		},

		## The shop's place and the warp to it
		{
			"name" : "PosInfoText",
			"type" : "text",

			"x" : 14,
			"y" : 30,

			"text" : "",
		},
		{
			"name" : "TeleportButton",
			"type" : "button",

			"x" : BUTTON_X,
			"y" : 26,

			"text" : uiScriptLocale.OFFLINE_SHOP_BUTTON_TELEPORT,

			"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
			"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
			"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
		},

		## The held yang and its withdrawal
		{
			"name" : "GoldSlot",
			"type" : "slotbar",

			"x" : 14,
			"y" : 53,

			"width" : 160,
			"height" : 18,

			"children" :
			(
				{
					"name" : "GoldText",
					"type" : "text",

					"x" : 4,
					"y" : 3,

					"text" : "0",
				},
			),
		},
		{
			"name" : "WithdrawButton",
			"type" : "button",

			"x" : BUTTON_X,
			"y" : 52,

			"text" : uiScriptLocale.OFFLINE_SHOP_BUTTON_WITHDRAW,

			"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
			"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
			"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
		},

		## The time left and the extension
		{
			"name" : "TimeLeftInfoText",
			"type" : "text",

			"x" : 14,
			"y" : 82,

			"text" : uiScriptLocale.OFFLINE_SHOP_TEXT_EXPIRE_IN,
		},
		{
			"name" : "TimeLeftText",
			"type" : "text",

			"x" : 130,
			"y" : 82,

			"text" : "",
		},
		{
			"name" : "AddTimeButton",
			"type" : "button",

			"x" : BUTTON_X,
			"y" : 78,

			"text" : uiScriptLocale.OFFLINE_SHOP_BUTTON_ADD_TIME,

			"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
			"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
			"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
		},

		## Lock (or renew), the logs, and the close at the shop
		{
			"name" : "LockButton",
			"type" : "button",

			"x" : 14,
			"y" : LARGE_BUTTON_Y,

			"text" : uiScriptLocale.OFFLINE_SHOP_BUTTON_LOCK,

			"default_image" : "d:/ymir work/ui/public/large_button_01.sub",
			"over_image" : "d:/ymir work/ui/public/large_button_02.sub",
			"down_image" : "d:/ymir work/ui/public/large_button_03.sub",
		},
		{
			"name" : "ViewLogButton",
			"type" : "button",

			"x" : 128,
			"y" : LARGE_BUTTON_Y,

			"text" : uiScriptLocale.OFFLINE_SHOP_BUTTON_VIEW_LOGS,

			"default_image" : "d:/ymir work/ui/public/large_button_01.sub",
			"over_image" : "d:/ymir work/ui/public/large_button_02.sub",
			"down_image" : "d:/ymir work/ui/public/large_button_03.sub",
		},
		{
			"name" : "CloseButton",
			"type" : "button",

			"x" : 243,
			"y" : LARGE_BUTTON_Y,

			"text" : uiScriptLocale.OFFLINE_SHOP_BUTTON_CLOSE,

			"default_image" : "d:/ymir work/ui/public/large_button_01.sub",
			"over_image" : "d:/ymir work/ui/public/large_button_02.sub",
			"down_image" : "d:/ymir work/ui/public/large_button_03.sub",
		},
	),
}
