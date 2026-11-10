import uiScriptLocale
import localeInfo
import item

# The equipment cells start at the body's, wear 0 (225 since the foundation cut, 90 before).
EQUIPMENT_START_INDEX = item.EQUIPMENT_BODY

window = {
	"name" : "InventoryWindow",

	## 600 - (width + right-side offset of 24 px)
	"x" : SCREEN_WIDTH - 176,
	"y" : SCREEN_HEIGHT - 37 - 635,

	"style" : ("movable", "float",),

	"width" : 176,
	"height" : 635,

	"children" :
	(
		## Inventory, Equipment Slots
		{
			"name" : "board",
			"type" : "board",
			"style" : ("attach",),

			"x" : 0,
			"y" : 0,

			"width" : 176,
			"height" : 635,

			"children" :
			(
				## Title
				{
					"name" : "TitleBar",
					"type" : "titlebar",
					"style" : ("attach",),

					"x" : 8,
					"y" : 7,

					"width" : 161,
					"color" : "yellow",

					"children" :
					(
						{ "name":"TitleName", "type":"text", "x":77, "y":3, "text":uiScriptLocale.INVENTORY_TITLE, "text_horizontal_align":"center" },
					),
				},

				## Equipment Slot
				{
					"name" : "Equipment_Base",
					"type" : "image",

					"x" : 10,
					"y" : 33,

					"image" : "d:/ymir work/ui/equipment_bg_with_ring.tga",

					"children" :
					(

						{
							"name" : "EquipmentSlot",
							"type" : "slot",

							"x" : 3,
							"y" : 3,

							"width" : 150,
							"height" : 182,

							"slot" : (
										{"index":EQUIPMENT_START_INDEX+0, "x":39, "y":37, "width":32, "height":64},
										{"index":EQUIPMENT_START_INDEX+1, "x":39, "y":2, "width":32, "height":32},
										{"index":EQUIPMENT_START_INDEX+2, "x":39, "y":145, "width":32, "height":32},
										{"index":EQUIPMENT_START_INDEX+3, "x":75, "y":67, "width":32, "height":32},
										{"index":EQUIPMENT_START_INDEX+4, "x":3, "y":3, "width":32, "height":96},
										{"index":EQUIPMENT_START_INDEX+5, "x":114, "y":67, "width":32, "height":32},
										{"index":EQUIPMENT_START_INDEX+6, "x":114, "y":35, "width":32, "height":32},
										{"index":EQUIPMENT_START_INDEX+7, "x":2, "y":145, "width":32, "height":32},
										{"index":EQUIPMENT_START_INDEX+8, "x":75, "y":145, "width":32, "height":32},
										{"index":EQUIPMENT_START_INDEX+9, "x":114, "y":2, "width":32, "height":32},
										{"index":EQUIPMENT_START_INDEX+10, "x":75, "y":35, "width":32, "height":32},
										## OLD's rings and belt (wear 28-30; OLD uiscript/newinventorywindow.py:118-121). OLD also shows
										## the costume sash (wear 21) here; the sash is not ported, so its slot stays hidden.
										{"index":item.EQUIPMENT_RING1, "x":2, "y":106, "width":32, "height":32},
										{"index":item.EQUIPMENT_RING2, "x":75, "y":106, "width":32, "height":32},
										{"index":item.EQUIPMENT_BELT, "x":39, "y":106, "width":32, "height":32},
									),
						},
						## Dragon Soul Button
						{
							"name" : "DSSButton",
							"type" : "button",

							"x" : 4,
							"y" : 107,

							"tooltip_text" : uiScriptLocale.TASKBAR_DRAGON_SOUL,

							"default_image" : "d:/ymir work/ui/dragonsoul/dss_inventory_button_01.tga",
							"over_image" : "d:/ymir work/ui/dragonsoul/dss_inventory_button_02.tga",
							"down_image" : "d:/ymir work/ui/dragonsoul/dss_inventory_button_03.tga",
						},
						## MallButton
						{
							"name" : "MallButton",
							"type" : "button",

							"x" : 7,
							"y" : 147,

							"tooltip_text" : uiScriptLocale.MALL_TITLE,

							"default_image" : "d:/ymir work/ui/game/TaskBar/Mall_Button_01.tga",
							"over_image" : "d:/ymir work/ui/game/TaskBar/Mall_Button_02.tga",
							"down_image" : "d:/ymir work/ui/game/TaskBar/Mall_Button_03.tga",
						},
						## CostumeButton
						{
							"name" : "CostumeButton",
							"type" : "button",

							"x" : 45,
							"y" : 5,

							"tooltip_text" : uiScriptLocale.COSTUME_TITLE,

							"default_image" : "d:/ymir work/ui/game/costume_button_01.tga",
							"over_image" : "d:/ymir work/ui/game/costume_button_02.tga",
							"down_image" : "d:/ymir work/ui/game/costume_button_03.tga",
						},
						{
							"name" : "Equipment_Tab_01",
							"type" : "radio_button",

							"x" : 86,
							"y" : 161,

							"default_image" : "d:/ymir work/ui/game/windows/tab_button_small_01.sub",
							"over_image" : "d:/ymir work/ui/game/windows/tab_button_small_02.sub",
							"down_image" : "d:/ymir work/ui/game/windows/tab_button_small_03.sub",

							"children" :
							(
								{
									"name" : "Equipment_Tab_01_Print",
									"type" : "text",

									"x" : 0,
									"y" : 0,

									"all_align" : "center",

									"text" : "I",
								},
							),
						},
						{
							"name" : "Equipment_Tab_02",
							"type" : "radio_button",

							"x" : 86 + 32,
							"y" : 161,

							"default_image" : "d:/ymir work/ui/game/windows/tab_button_small_01.sub",
							"over_image" : "d:/ymir work/ui/game/windows/tab_button_small_02.sub",
							"down_image" : "d:/ymir work/ui/game/windows/tab_button_small_03.sub",

							"children" :
							(
								{
									"name" : "Equipment_Tab_02_Print",
									"type" : "text",

									"x" : 0,
									"y" : 0,

									"all_align" : "center",

									"text" : "II",
								},
							),
						},

					),
				},

				## One tab per inventory page, five as OLD (OLD uiscript/newinventorywindow.py:216-359);
				## OLD's NewUI tab art is not in NEW's assets, so the five use NEW's small tabs.
				{
					"name" : "Inventory_Tab_01",
					"type" : "radio_button",

					"x" : 8 + 32 * 0,
					"y" : 33 + 191,

					"default_image" : "d:/ymir work/ui/game/windows/tab_button_small_01.sub",
					"over_image" : "d:/ymir work/ui/game/windows/tab_button_small_02.sub",
					"down_image" : "d:/ymir work/ui/game/windows/tab_button_small_03.sub",
					"tooltip_text" : uiScriptLocale.INVENTORY_PAGE_BUTTON_TOOLTIP_1,

					"children" :
					(
						{
							"name" : "Inventory_Tab_01_Print",
							"type" : "text",

							"x" : 0,
							"y" : 0,

							"all_align" : "center",

							"text" : "I",
						},
					),
				},
				{
					"name" : "Inventory_Tab_02",
					"type" : "radio_button",

					"x" : 8 + 32 * 1,
					"y" : 33 + 191,

					"default_image" : "d:/ymir work/ui/game/windows/tab_button_small_01.sub",
					"over_image" : "d:/ymir work/ui/game/windows/tab_button_small_02.sub",
					"down_image" : "d:/ymir work/ui/game/windows/tab_button_small_03.sub",
					"tooltip_text" : uiScriptLocale.INVENTORY_PAGE_BUTTON_TOOLTIP_2,

					"children" :
					(
						{
							"name" : "Inventory_Tab_02_Print",
							"type" : "text",

							"x" : 0,
							"y" : 0,

							"all_align" : "center",

							"text" : "II",
						},
					),
				},
				{
					"name" : "Inventory_Tab_03",
					"type" : "radio_button",

					"x" : 8 + 32 * 2,
					"y" : 33 + 191,

					"default_image" : "d:/ymir work/ui/game/windows/tab_button_small_01.sub",
					"over_image" : "d:/ymir work/ui/game/windows/tab_button_small_02.sub",
					"down_image" : "d:/ymir work/ui/game/windows/tab_button_small_03.sub",
					"tooltip_text" : uiScriptLocale.INVENTORY_PAGE_BUTTON_TOOLTIP_3,

					"children" :
					(
						{
							"name" : "Inventory_Tab_03_Print",
							"type" : "text",

							"x" : 0,
							"y" : 0,

							"all_align" : "center",

							"text" : "III",
						},
					),
				},
				{
					"name" : "Inventory_Tab_04",
					"type" : "radio_button",

					"x" : 8 + 32 * 3,
					"y" : 33 + 191,

					"default_image" : "d:/ymir work/ui/game/windows/tab_button_small_01.sub",
					"over_image" : "d:/ymir work/ui/game/windows/tab_button_small_02.sub",
					"down_image" : "d:/ymir work/ui/game/windows/tab_button_small_03.sub",
					"tooltip_text" : uiScriptLocale.INVENTORY_PAGE_BUTTON_TOOLTIP_4,

					"children" :
					(
						{
							"name" : "Inventory_Tab_04_Print",
							"type" : "text",

							"x" : 0,
							"y" : 0,

							"all_align" : "center",

							"text" : "IV",
						},
					),
				},
				{
					"name" : "Inventory_Tab_05",
					"type" : "radio_button",

					"x" : 8 + 32 * 4,
					"y" : 33 + 191,

					"default_image" : "d:/ymir work/ui/game/windows/tab_button_small_01.sub",
					"over_image" : "d:/ymir work/ui/game/windows/tab_button_small_02.sub",
					"down_image" : "d:/ymir work/ui/game/windows/tab_button_small_03.sub",
					"tooltip_text" : uiScriptLocale.INVENTORY_PAGE_BUTTON_TOOLTIP_5,

					"children" :
					(
						{
							"name" : "Inventory_Tab_05_Print",
							"type" : "text",

							"x" : 0,
							"y" : 0,

							"all_align" : "center",

							"text" : "V",
						},
					),
				},

				## Item Slot
				{
					"name" : "ItemSlot",
					"type" : "grid_table",

					"x" : 8,
					"y" : 246,

					"start_index" : 0,
					"x_count" : 5,
					"y_count" : 9,
					"x_step" : 32,
					"y_step" : 32,

					"image" : "d:/ymir work/ui/public/Slot_Base.sub"
				},

				## The special inventory (NOVA-16): a band of 26 px between the bag
				## and the money slot (the board grew from 565 to 591 px for it, to
				## 611 px for the gaya row under the yang, NOVA-10, and to 635 px for
				## the offline shop's buttons under this one, NOVA-9).
				{
					"name" : "ExtraInventoryButton",
					"type" : "button",

					"x" : 77,
					"y" : 246 + 32 * 9 + 3,

					"text" : uiScriptLocale.EXTRA_INVENTORY_BUTTON,
					"tooltip_text" : uiScriptLocale.KEYCHANGE_EXTRA_INVENTORY,

					"default_image" : "d:/ymir work/ui/public/large_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/large_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/large_button_03.sub",
				},

				## The kill ranking (NOVA-29): OLD's extra inventory strip had the
				## Ranking button (OLD uiscript/extrainventorywindow.py:93-104), art
				## NEW's packs lack: a stock text button left of the special
				## inventory's, in its band (the two side by side, centered).
				{
					"name" : "RankingButton",
					"type" : "button",

					"x" : 10,
					"y" : 246 + 32 * 9 + 3,

					"text" : uiScriptLocale.SYSTEM_KILL_RANK,

					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},

				## The offline shop (NOVA-9): MANAGE (the owner's panel, or the
				## builder) and the shop search, side by side under the special
				## inventory's button. OLD's were image buttons (a Q9 asset): text
				## buttons here, hidden until the server's CONFIG says the shop is on.
				{
					"name" : "OfflineShopButton",
					"type" : "button",

					"x" : 24,
					"y" : 246 + 32 * 9 + 3 + 21 + 3,

					"text" : localeInfo.OFFLINE_SHOP_BUTTON,
					"tooltip_text" : localeInfo.OFFLINE_SHOP,

					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},
				{
					"name" : "SearchShopButton",
					"type" : "button",

					"x" : 24 + 61 + 6,
					"y" : 246 + 32 * 9 + 3 + 21 + 3,

					"text" : localeInfo.SEARCH_SHOP_BUTTON,
					"tooltip_text" : uiScriptLocale.SEARCH_SHOP_TITLE,

					"default_image" : "d:/ymir work/ui/public/middle_button_01.sub",
					"over_image" : "d:/ymir work/ui/public/middle_button_02.sub",
					"down_image" : "d:/ymir work/ui/public/middle_button_03.sub",
				},

				## Print
				{
					"name":"Money_Slot",
					"type":"button",

					"x":8,
					"y":48,

					"horizontal_align":"center",
					"vertical_align":"bottom",

					"default_image" : "d:/ymir work/ui/public/parameter_slot_05.sub",
					"over_image" : "d:/ymir work/ui/public/parameter_slot_05.sub",
					"down_image" : "d:/ymir work/ui/public/parameter_slot_05.sub",

					"children" :
					(
						{
							"name":"Money_Icon",
							"type":"image",

							"x":-18,
							"y":2,

							"image":"d:/ymir work/ui/game/windows/money_icon.sub",
						},

						{
							"name" : "Money",
							"type" : "text",

							"x" : 3,
							"y" : 3,

							"horizontal_align" : "right",
							"text_horizontal_align" : "right",

							"text" : "123456789",
						},
					),
				},

				## The gaya balance (NOVA-10), under the yang. OLD's gaya icon is a
				## later asset task (spec Q9): the yang's coin stands in, as in the
				## cube window, and the slot's tooltip names the currency.
				{
					"name":"Gem_Slot",
					"type":"button",

					"x":8,
					"y":28,

					"horizontal_align":"center",
					"vertical_align":"bottom",

					"tooltip_text" : localeInfo.GEM_SYSTEM_NAME,

					"default_image" : "d:/ymir work/ui/public/parameter_slot_05.sub",
					"over_image" : "d:/ymir work/ui/public/parameter_slot_05.sub",
					"down_image" : "d:/ymir work/ui/public/parameter_slot_05.sub",

					"children" :
					(
						{
							"name":"Gem_Icon",
							"type":"image",

							"x":-18,
							"y":2,

							"image":"d:/ymir work/ui/game/windows/money_icon.sub",
						},

						{
							"name" : "Gem",
							"type" : "text",

							"x" : 3,
							"y" : 3,

							"horizontal_align" : "right",
							"text_horizontal_align" : "right",

							"text" : "0",
						},
					),
				},

			),
		},
	),
}
