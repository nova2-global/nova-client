import uiScriptLocale

## OLD's uiscript/petwindow.py (NOVA-24, the 0.2 pack): the pet window, 406 x
## 513 (uipet.PetWindow, the own pet and the preview). OLD's names, geometry and
## art (d:/ymir work/ui/pet and pattern/NewUI, imported from OLD's packs); OLD's
## English labels are locale keys and the placeholders the window sets are empty.

window = {
    "name": "PetWindow",
    "style": ("movable", "float",),

    "x": SCREEN_WIDTH // 2 - 203,
    "y": SCREEN_HEIGHT // 2 - 256,

    "width": 406,
    "height": 513,

    "children":
    [
		# Pet Image
		{
			"name": "PetImageBg",
			"type": "image",
			"style" : ("attach",),
			"x": 50,
			"y": 0,
			"image": "d:/ymir work/ui/pet/pet_image.png",
			"children":
			(
				# Pet Image
				{
					"name": "PetImage",
					"type": "expanded_image",
					"x": 0,
					"y": 110,
					"vertical_align":"bottom",
					"horizontal_align":"center",
					"image": "d:/ymir work/ui/pet/disabled_slot.png",
				},

				# Pet Level
                {
                    "name": "PetLevel_bg",
                    "type": "expanded_image",
                    "x": 52-55,
                    "y": 95,
                    "image": "d:/ymir work/ui/pet/rounded-slot.png",
                    "children":
                    (
						{
							"name": "PetLevel",
							"type": "text",
							"x": 0,
							"y": 3,
							"text_horizontal_align":"center",
							"horizontal_align":"center",
							"text": "",
						},
                    ),
                },
				# Pet Evolution
                {
                    "name": "PetEvolution_bg",
                    "type": "expanded_image",
                    "x": 162-55,
                    "y": 95,
                    "image": "d:/ymir work/ui/pet/rounded-slot.png",
                    "children":
                    (
						{
							"name": "PetEvolution",
							"type": "text",
							"x": 0,
							"y": 3,
							"text_horizontal_align":"center",
							"horizontal_align":"center",
							"text": "",
						},
                    ),
                },
				# Pet Name
                {
                    "name": "PetName_bg",
                    "type": "expanded_image",
                    "x": 270-55,
                    "y": 95,
                    "image": "d:/ymir work/ui/pet/rounded-slot.png",
                    "children":
                    (
						{
							"name": "PetName",
							"type": "text",
							"x": 0,
							"y": 3,
							"text_horizontal_align":"center",
							"horizontal_align":"center",
							"text": "",
						},
                    ),
                },
			),
		},
        {
            "name": "bg",
            "type": "image",
			"style" : ("attach",),
            "x": 0,
            "y": 115,
            "image": "d:/ymir work/ui/pet/bg.png",

            "children":
            [
                # CloseBtn
                {
                    "name": "CloseBtn",
                    "type": "button",
                    "x": 360,
                    "y": 136 - 110,
                    "default_image": "d:/ymir work/ui/pattern/NewUI/close_01.sub",
                    "over_image": "d:/ymir work/ui/pattern/NewUI/close_02.sub",
                    "down_image": "d:/ymir work/ui/pattern/NewUI/close_03.sub",
                },
                # Exp Bar
                {
                    "name": "ExpBar",
                    "type": "expanded_image",
                    "x": 49,
                    "y": 116 - 110,
                    "image": "d:/ymir work/ui/pet/expbar.png",
                },

                # Evolution Upgrade Button
                {
                    "name": "evolution_upgrade",
                    "type": "button",
                    "x": 250-191,
                    "y": 180+285 - 110,
                    "text": uiScriptLocale.PET_EVOLVE_BUTTON,
                    "default_image": "d:/ymir work/ui/pattern/NewUI/buttons/big_thin_button_01.sub",
                    "over_image": "d:/ymir work/ui/pattern/NewUI/buttons/big_thin_button_02.sub",
                    "down_image": "d:/ymir work/ui/pattern/NewUI/buttons/big_thin_button_03.sub",
                    "disable_image": "d:/ymir work/ui/pet/btn_disabled.png",
                },

                # Bonus Names
                {
                    "name": "bonus1_name_bg",
                    "type": "expanded_image",
                    "x": 48,
                    "y": 179 - 110,
                    "image": "d:/ymir work/ui/pet/attr_type.png",
                    "children":
                    (
                        {
                            "name": "bonus1_name",
                            "type": "text",
                            "x": 10,
                            "y": 2,
                            "text": "",
							"color" : 0xffFEE3AE,
                        },
                    ),
                },
                {
                    "name": "bonus2_name_bg",
                    "type": "expanded_image",
                    "x": 48,
                    "y": 201 - 110,
                    "image": "d:/ymir work/ui/pet/attr_type.png",
                    "children":
                    (
                        {
                            "name": "bonus2_name",
                            "type": "text",
                            "x": 10,
                            "y": 2,
                            "text": "",
							"color" : 0xffFEE3AE,
                        },
                    ),
                },
                {
                    "name": "bonus3_name_bg",
                    "type": "expanded_image",
                    "x": 48,
                    "y": 223 - 110,
                    "image": "d:/ymir work/ui/pet/attr_type.png",
                    "children":
                    (
                        {
                            "name": "bonus3_name",
                            "type": "text",
                            "x": 10,
                            "y": 2,
                            "text": "",
							"color" : 0xffFEE3AE,
                        },
                    ),
                },


                # Bonus Level Gauges
                {
                    "name": "bonus1_level_bg",
                    "type": "expanded_image",
                    "x": 220,
                    "y": 179 - 110,
                    "image": "d:/ymir work/ui/pet/attr_level.png",
                    "children":
                    (
                        {
                            "name": "bonus1_level",
                            "type": "text",
                            "x": 10,
                            "y": 2,
                            "text": "",
							"color" : 0xffFEE3AE,
                        },
                        {
							"name": "bonus1_plus_btn",
							"type": "button",
							"x": 15,
							"y": 0,
							"horizontal_align" : "right",
							"vertical_align" : "center",
							"default_image": "d:/ymir work/ui/pattern/NewUI/buttons/plus_button_1.sub",
							"over_image": "d:/ymir work/ui/pattern/NewUI/buttons/plus_button_2.sub",
							"down_image": "d:/ymir work/ui/pattern/NewUI/buttons/plus_button_3.sub",
                        },
                    ),
                },
                {
                    "name": "bonus2_level_bg",
                    "type": "expanded_image",
                    "x": 220,
                    "y": 201 - 110,
                    "image": "d:/ymir work/ui/pet/attr_level.png",
                    "children":
                    (
                        {
                            "name": "bonus2_level",
                            "type": "text",
                            "x": 10,
                            "y": 2,
                            "text": "",
							"color" : 0xffFEE3AE,
                        },
                        {
							"name": "bonus2_plus_btn",
							"type": "button",
							"x": 15,
							"y": 0,
							"horizontal_align" : "right",
							"vertical_align" : "center",
							"default_image": "d:/ymir work/ui/pattern/NewUI/buttons/plus_button_1.sub",
							"over_image": "d:/ymir work/ui/pattern/NewUI/buttons/plus_button_2.sub",
							"down_image": "d:/ymir work/ui/pattern/NewUI/buttons/plus_button_3.sub",
                        },
                    ),
                },
                {
                    "name": "bonus3_level_bg",
                    "type": "expanded_image",
                    "x": 220,
                    "y": 223 - 110,
                    "image": "d:/ymir work/ui/pet/attr_level.png",
                    "children":
                    (
                        {
                            "name": "bonus3_level",
                            "type": "text",
                            "x": 10,
                            "y": 2,
                            "text": "",
							"color" : 0xffFEE3AE,
                        },
                        {
							"name": "bonus3_plus_btn",
							"type": "button",
							"x": 15,
							"y": 0,
							"horizontal_align" : "right",
							"vertical_align" : "center",
							"default_image": "d:/ymir work/ui/pattern/NewUI/buttons/plus_button_1.sub",
							"over_image": "d:/ymir work/ui/pattern/NewUI/buttons/plus_button_2.sub",
							"down_image": "d:/ymir work/ui/pattern/NewUI/buttons/plus_button_3.sub",
                        },
                    ),
                },

                {
                    "name": "skill_slots",
                    "type": "expanded_image",
                    "x": 52,
                    "y": 172,
                    "image": "d:/ymir work/ui/pet/skill_slots.png",
                    "children":
                    (
						# Skill Slot
						{

							"name": "skill_slot",
							"type": "slot",
							"x": -3,
							"y": 0,
							"width": 306,
							"height": 167,
							"slot": [
								#Normal skills
								{"index": 0, "x": 4, "y": 0, "width": 37, "height": 37},
								{"index": 1, "x": 68, "y": 0, "width": 37, "height": 37},
								{"index": 2, "x": 132, "y": 0, "width": 37, "height": 37},
								{"index": 3, "x": 200, "y": 0, "width": 37, "height": 37},
								{"index": 4, "x": 268, "y": 0, "width": 37, "height": 37},

								{"index": 5, "x": 4, "y": 38, "width": 37, "height": 37},
								{"index": 6, "x": 68, "y": 38, "width": 37, "height": 37},
								{"index": 7, "x": 132, "y": 38, "width": 37, "height": 37},
								{"index": 8, "x": 200, "y": 38, "width": 37, "height": 37},
								{"index": 9, "x": 268, "y": 38, "width": 37, "height": 37},
								#Heroic Skills
								{"index": 10, "x": 42, "y": 108, "width": 46, "height": 46},
								{"index": 11, "x": 126, "y": 108, "width": 46, "height": 46},
								{"index": 12, "x": 218, "y": 108, "width": 46, "height": 46},
							],
						},
					),
                },
                # Skill Disabled Slots
                {
                    "name": "skill_slot1_disabled",
                    "type": "expanded_image",
                    "x": 52,
                    "y": 173,
                    "image": "d:/ymir work/ui/pet/disabled_slot.png",
                },
                {
                    "name": "skill_slot2_disabled",
                    "type": "expanded_image",
                    "x": 116,
                    "y": 173,
                    "image": "d:/ymir work/ui/pet/disabled_slot.png",
                },
                {
                    "name": "skill_slot3_disabled",
                    "type": "expanded_image",
                    "x": 180,
                    "y": 173,
                    "image": "d:/ymir work/ui/pet/disabled_slot.png",
                },
                {
                    "name": "skill_slot4_disabled",
                    "type": "expanded_image",
                    "x": 248,
                    "y": 173,
                    "image": "d:/ymir work/ui/pet/disabled_slot.png",
                },
                {
                    "name": "skill_slot5_disabled",
                    "type": "expanded_image",
                    "x": 316,
                    "y": 173,
                    "image": "d:/ymir work/ui/pet/disabled_slot.png",
                },

                {
                    "name": "skill_slot6_disabled",
                    "type": "expanded_image",
                    "x": 52,
                    "y": 210 ,
                    "image": "d:/ymir work/ui/pet/disabled_slot.png",
                },
                {
                    "name": "skill_slot7_disabled",
                    "type": "expanded_image",
                    "x": 116,
                    "y": 210,
                    "image": "d:/ymir work/ui/pet/disabled_slot.png",
                },
                {
                    "name": "skill_slot8_disabled",
                    "type": "expanded_image",
                    "x": 180,
                    "y": 210,
                    "image": "d:/ymir work/ui/pet/disabled_slot.png",
                },
                {
                    "name": "skill_slot9_disabled",
                    "type": "expanded_image",
                    "x": 248,
                    "y": 210,
                    "image": "d:/ymir work/ui/pet/disabled_slot.png",
                },
                {
                    "name": "skill_slot10_disabled",
                    "type": "expanded_image",
                    "x": 316,
                    "y": 210,
                    "image": "d:/ymir work/ui/pet/disabled_slot.png",
                },

				#Heroic
                {
                    "name": "skill_slot11_disabled",
                    "type": "expanded_image",
                    "x": 90,
                    "y": 279,
                    "image": "d:/ymir work/ui/pet/disabled_slot_big.png",
                },
                {
                    "name": "skill_slot12_disabled",
                    "type": "expanded_image",
                    "x": 175,
                    "y": 279,
                    "image": "d:/ymir work/ui/pet/disabled_slot_big.png",
                },
                {
                    "name": "skill_slot13_disabled",
                    "type": "expanded_image",
                    "x": 266,
                    "y": 279,
                    "image": "d:/ymir work/ui/pet/disabled_slot_big.png",
                },

				{
					"name": "attr_title",
					"type": "text",
					"x": 0,
					"y": 43,
					"horizontal_align":"center",
					"text_horizontal_align":"center",
					"text": uiScriptLocale.PET_UI_ATTRIBUTES,
					"color" : 0xffFEE3AE,
				},
				{
					"name": "skill_normal_title",
					"type": "text",
					"x": 0,
					"y": 151,
					"horizontal_align":"center",
					"text_horizontal_align":"center",
					"text": uiScriptLocale.PET_UI_BASIC_SKILLS,
					"color" : 0xffFEE3AE,
				},
				{
					"name": "skill_heroic_title",
					"type": "text",
					"x": 0,
					"y": 258,
					"horizontal_align":"center",
					"text_horizontal_align":"center",
					"text": uiScriptLocale.PET_UI_HEROIC_SKILLS,
					"color" : 0xffFEE3AE,
				},


            ],
        },
    ],
}
