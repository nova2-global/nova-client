import uiScriptLocale

## OLD's uiscript/petinterfacewindow.py (NOVA-24, the 0.2 pack): the pet's mini
## window, 245 x 135 open and 75 x 75 folded (uipet.PetInterfaceWindow). OLD's
## names, geometry and art; OLD's "target_board_new" (its NewUI skin, which NEW
## lacks) is NEW's thin board.

window = {
    "name": "PetInterfaceWindow",
    "style": ("movable", "float",),

    "x":  260,
    "y": SCREEN_HEIGHT - 280,

    "width": 245,
    "height": 135,

    "children":
    (
        {
            "name": "board",
            "type": "thinboard",
            "style": ("attach",),

            "x": 0,
            "y": 0,
            "width": 245,
            "height": 135,

            "children":
            (


				## Icon Slot
				{
					"name" : "icon_base",
					"type" : "window",
					"style" : ("attach",),

					"x" : 15,
					"y" : 15,

					"width" : 32 + 3,
					"height" : 44,

					"children" :
					(
						## Main Slot Img
						{
							"name" : "main_slot_img",
							"type" : "expanded_image",
							"style" : ("attach",),

							"x" : 3,
							"y" : 3,

							"image" : "d:/ymir work/ui/pet/mini_window/pet_slot_corver.sub",

							"width" : 32,
							"height" : 38,
						},

						## Main Slot
						{
							"name" : "image",
							"type" : "image",
							"style" : ("attach",),

							"x" : 3,
							"y" : 6,

							"image": "d:/ymir work/ui/public/slot_base.sub",
						},

						## Main Slot Effect
						{
							"name" : "pet_icon_slot_ani_img",
							"type" : "ani_image",
							"style" : ("attach",),

							"x" : 3,
							"y" : 3,

							"delay" : 6,

							"images" :
							(
								"D:/Ymir Work/UI/pet/mini_window/main_slot_effect/main_slot_effect1.sub",
								"D:/Ymir Work/UI/pet/mini_window/main_slot_effect/main_slot_effect2.sub",
								"D:/Ymir Work/UI/pet/mini_window/main_slot_effect/main_slot_effect3.sub",
								"D:/Ymir Work/UI/pet/mini_window/main_slot_effect/main_slot_effect4.sub",
								"D:/Ymir Work/UI/pet/mini_window/main_slot_effect/main_slot_effect5.sub",
								"D:/Ymir Work/UI/pet/mini_window/main_slot_effect/main_slot_effect6.sub",
								"D:/Ymir Work/UI/pet/mini_window/main_slot_effect/main_slot_effect6.sub",
								"D:/Ymir Work/UI/pet/mini_window/main_slot_effect/main_slot_effect6.sub",
								"D:/Ymir Work/UI/pet/mini_window/main_slot_effect/main_slot_effect5.sub",
								"D:/Ymir Work/UI/pet/mini_window/main_slot_effect/main_slot_effect4.sub",
								"D:/Ymir Work/UI/pet/mini_window/main_slot_effect/main_slot_effect3.sub",
								"D:/Ymir Work/UI/pet/mini_window/main_slot_effect/main_slot_effect2.sub",
								"D:/Ymir Work/UI/pet/mini_window/main_slot_effect/main_slot_effect1.sub",
							),
						},
					),
				},

                # Pet Name
                {
                    "name": "title",
                    "type": "text",
                    "x": 65,
                    "y": 16,
                    "text": "",
					"color" : 0xffFEE3AE,
                },
                # Pet Evo
                {
                    "name": "evo",
                    "type": "text",
                    "x": 65,
                    "y": 30,
                    "text": "",
					"color" : 0xffFEE3AE,
                },
                {
                    "name": "expBar_bg",
                    "type": "image",
                    "x": 65,
                    "y": 48,
                    "image": "d:/ymir work/ui/pet/expbar_bg_small.png",

					"children" :
					(
						{
							"name": "ExpBar",
							"type": "expanded_image",
							"x": 0,
							"y": 0,
							"image": "d:/ymir work/ui/pet/expbar_small.png",
						},
					),
                },


				# Skill Slot
				{

					"name": "skill_slot",
					"type": "slot",
					"x": 18,
					"y": 72,
					"width": 175,
					"height": 167,
					"image" : "d:/ymir work/ui/pet/slot-small.png",
					"slot": [
						#Normal skills
						{"index": 0, "x": 0, "y": 0, "width": 20, "height": 20},
						{"index": 1, "x": 21, "y": 0, "width": 20, "height": 20},
						{"index": 2, "x": 42, "y": 0, "width": 20, "height": 20},
						{"index": 3, "x": 63, "y": 0, "width": 20, "height": 20},
						{"index": 4, "x": 84, "y": 0, "width": 20, "height": 20},

						{"index": 5, "x": 105, "y": 0, "width": 20, "height": 20},
						{"index": 6, "x": 126, "y": 0, "width": 20, "height": 20},
						{"index": 7, "x": 147, "y": 0, "width": 20, "height": 20},
						{"index": 8, "x": 168, "y": 0, "width": 20, "height": 20},
						{"index": 9, "x": 189, "y": 0, "width": 20, "height": 20},
						#Heroic Skills
						{"index": 10, "x": 0, "y": 22, "width": 25, "height": 25},
						{"index": 11, "x": 21, "y": 22, "width": 25, "height": 25},
						{"index": 12, "x": 42, "y": 22, "width": 25, "height": 25},
					],
					"children" :
					(





						# Disabled Skill Slot overlays
						{
							"name": "skill_slot1_disabled",
							"type": "image",
							"x": 0,
							"y": 0,
							"image": "d:/ymir work/ui/pet/slot_disabled_small.png",
						},
						{
							"name": "skill_slot2_disabled",
							"type": "image",
							"x": 21,
							"y": 0,
							"image": "d:/ymir work/ui/pet/slot_disabled_small.png",
						},
						{
							"name": "skill_slot3_disabled",
							"type": "image",
							"x": 42,
							"y": 0,
							"image": "d:/ymir work/ui/pet/slot_disabled_small.png",
						},
						{
							"name": "skill_slot4_disabled",
							"type": "image",
							"x": 63,
							"y": 0,
							"image": "d:/ymir work/ui/pet/slot_disabled_small.png",
						},
						{
							"name": "skill_slot5_disabled",
							"type": "image",
							"x": 84,
							"y": 0,
							"image": "d:/ymir work/ui/pet/slot_disabled_small.png",
						},
						{
							"name": "skill_slot6_disabled",
							"type": "image",
							"x": 105,
							"y": 0,
							"image": "d:/ymir work/ui/pet/slot_disabled_small.png",
						},
						{
							"name": "skill_slot7_disabled",
							"type": "image",
							"x": 126,
							"y": 0,
							"image": "d:/ymir work/ui/pet/slot_disabled_small.png",
						},
						{
							"name": "skill_slot8_disabled",
							"type": "image",
							"x": 147,
							"y": 0,
							"image": "d:/ymir work/ui/pet/slot_disabled_small.png",
						},
						{
							"name": "skill_slot9_disabled",
							"type": "image",
							"x": 168,
							"y": 0,
							"image": "d:/ymir work/ui/pet/slot_disabled_small.png",
						},
						{
							"name": "skill_slot10_disabled",
							"type": "image",
							"x": 189,
							"y": 0,
							"image": "d:/ymir work/ui/pet/slot_disabled_small.png",
						},
						{
							"name": "skill_slot11_disabled",
							"type": "image",
							"x": 0,
							"y": 22,
							"image": "d:/ymir work/ui/pet/slot_disabled_small.png",
						},
						{
							"name": "skill_slot12_disabled",
							"type": "image",
							"x": 21,
							"y": 22,
							"image": "d:/ymir work/ui/pet/slot_disabled_small.png",
						},
						{
							"name": "skill_slot13_disabled",
							"type": "image",
							"x": 42,
							"y": 22,
							"image": "d:/ymir work/ui/pet/slot_disabled_small.png",
						},
					),
				},
            ),
        },
    ),
}
