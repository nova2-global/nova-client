"""The character bonus details (NOVA-207; OLD uiCharacterDetails.py): the one
row table the legacy panel (uicharacterdetails.py) and the NovaUI side panel
of the character window (nui_character.py) both read.

Each row is one line: its label and tooltip keys in locale_game.txt (OLD's
DETAILS_* strings) and the point it shows, by its name in NEW's server
(EPointTypes, srv game/char.h) and its number. The server sends every point
to the client (CHARACTER::PointsPacket), so a row's value is
player.GetStatus(point); NEW's client has no item.GetApplyPoint, so the
numbers are the server's own.

Not shown (OLD comments them out, and NEW's items give none of them):
DETAILS_6 (zodiac), DETAILS_10 (desert) and DETAILS_11 (insects; NEW's
server applies neither point 52 nor 49), DETAILS_40 and DETAILS_45
(wolfman), DETAILS_49 (claw), DETAILS_57 and DETAILS_58 (bleeding), the
weapon break bonuses (DETAILS_ATTBONUS_*) and the fall resistance
(DETAILS_RESIST_MOUNT_FALL)."""

# (category key, ((label key, tooltip key, point name, point), ...)), in OLD's order.
CATEGORIES = (
	("DETAILS_CATE_1", (
		("DETAILS_1", "DETAILS_TOOLTIP_1", "ATTBONUS_HUMAN", 43),
		("DETAILS_2", "DETAILS_TOOLTIP_2", "ANTI_HUMAN", 147),
		("DETAILS_3", "DETAILS_TOOLTIP_3", "ATTBONUS_ORC", 45),
		("DETAILS_4", "DETAILS_TOOLTIP_4", "ATTBONUS_UNDEAD", 47),
		("DETAILS_5", "DETAILS_TOOLTIP_5", "ATTBONUS_MONSTER", 53),
		("DETAILS_ELEMENTAL", "DETAILS_TOOLTIP_ELEMENTAL", "ATTBONUS_ELEMENTAL", 146),
		("DETAILS_BOSS", "DETAILS_TOOLTIP_BOSS", "ATTBONUS_BOSS", 144),
		("DETAILS_STONE", "DETAILS_TOOLTIP_METIN", "ATTBONUS_METIN_STONE", 145),
		("DETAILS_7", "DETAILS_TOOLTIP_7", "ATTBONUS_ANIMAL", 44),
		("DETAILS_8", "DETAILS_TOOLTIP_8", "ATTBONUS_MILGYO", 46),
		("DETAILS_9", "DETAILS_TOOLTIP_9", "ATTBONUS_DEVIL", 48),
		("DETAILS_12", "DETAILS_TOOLTIP_12", "ATT_GRADE_BONUS", 95),
		("DETAILS_13", "DETAILS_TOOLTIP_13", "DEF_GRADE_BONUS", 96),
		("DETAILS_14", "DETAILS_TOOLTIP_14", "NORMAL_HIT_DAMAGE_BONUS", 122),
		("DETAILS_15", "DETAILS_TOOLTIP_15", "NORMAL_HIT_DEFEND_BONUS", 124),
		("DETAILS_16", "DETAILS_TOOLTIP_16", "SKILL_DAMAGE_BONUS", 121),
		("DETAILS_17", "DETAILS_TOOLTIP_17", "SKILL_DEFEND_BONUS", 123),
		("DETAILS_18", "DETAILS_TOOLTIP_18", "MELEE_MAGIC_ATT_BONUS_PER", 132),
		("DETAILS_19", "DETAILS_TOOLTIP_19", "MAGIC_ATT_BONUS_PER", 131),
		("DETAILS_20", "DETAILS_TOOLTIP_20", "CRITICAL_PCT", 40),
		("DETAILS_21", "DETAILS_TOOLTIP_21", "PENETRATE_PCT", 41),
		("DETAILS_22", "DETAILS_TOOLTIP_22", "RESIST_CRITICAL", 136),
		("DETAILS_23", "DETAILS_TOOLTIP_23", "RESIST_PENETRATE", 137),
	)),
	("DETAILS_CATE_2", (
		("DETAILS_76", "DETAILS_TOOLTIP_76", "RESIST_MAGIC", 77),
		("DETAILS_24", "DETAILS_TOOLTIP_24", "RESIST_ELEC", 76),
		("DETAILS_25", "DETAILS_TOOLTIP_25", "RESIST_ICE", 133),
		("DETAILS_26", "DETAILS_TOOLTIP_26", "RESIST_DARK", 135),
		("DETAILS_27", "DETAILS_TOOLTIP_27", "RESIST_FIRE", 75),
		("DETAILS_28", "DETAILS_TOOLTIP_28", "RESIST_WIND", 78),
		("DETAILS_29", "DETAILS_TOOLTIP_29", "RESIST_EARTH", 134),
		("DETAILS_77", "DETAILS_TOOLTIP_77", "ANTI_RESIST_MAGIC", 143),
		("DETAILS_30", "DETAILS_TOOLTIP_30", "ATTBONUS_ELEC", 164),
		("DETAILS_31", "DETAILS_TOOLTIP_31", "ATTBONUS_ICE", 51),
		("DETAILS_32", "DETAILS_TOOLTIP_32", "ATTBONUS_DARK", 167),
		("DETAILS_33", "DETAILS_TOOLTIP_33", "ATTBONUS_FIRE", 50),
		("DETAILS_34", "DETAILS_TOOLTIP_34", "ATTBONUS_WIND", 165),
		("DETAILS_35", "DETAILS_TOOLTIP_35", "ATTBONUS_EARTH", 166),
	)),
	("DETAILS_CATE_3", (
		("DETAILS_36", "DETAILS_TOOLTIP_36", "ATTBONUS_WARRIOR", 54),
		("DETAILS_37", "DETAILS_TOOLTIP_37", "ATTBONUS_ASSASSIN", 55),
		("DETAILS_38", "DETAILS_TOOLTIP_38", "ATTBONUS_SURA", 56),
		("DETAILS_39", "DETAILS_TOOLTIP_39", "ATTBONUS_SHAMAN", 57),
		("DETAILS_41", "DETAILS_TOOLTIP_41", "RESIST_WARRIOR", 59),
		("DETAILS_42", "DETAILS_TOOLTIP_42", "RESIST_ASSASSIN", 60),
		("DETAILS_43", "DETAILS_TOOLTIP_43", "RESIST_SURA", 61),
		("DETAILS_44", "DETAILS_TOOLTIP_44", "RESIST_SHAMAN", 62),
	)),
	("DETAILS_CATE_4", (
		("DETAILS_46", "DETAILS_TOOLTIP_46", "RESIST_SWORD", 69),
		("DETAILS_47", "DETAILS_TOOLTIP_47", "RESIST_TWOHAND", 70),
		("DETAILS_48", "DETAILS_TOOLTIP_48", "RESIST_DAGGER", 71),
		("DETAILS_50", "DETAILS_TOOLTIP_50", "RESIST_BELL", 72),
		("DETAILS_51", "DETAILS_TOOLTIP_51", "RESIST_FAN", 73),
		("DETAILS_52", "DETAILS_TOOLTIP_52", "RESIST_BOW", 74),
	)),
	("DETAILS_CATE_5", (
		("DETAILS_53", "DETAILS_TOOLTIP_53", "STUN_PCT", 38),
		("DETAILS_54", "DETAILS_TOOLTIP_54", "SLOW_PCT", 39),
		("DETAILS_55", "DETAILS_TOOLTIP_55", "POISON_PCT", 37),
		("DETAILS_56", "DETAILS_TOOLTIP_56", "POISON_REDUCE", 81),
		("DETAILS_59", "DETAILS_TOOLTIP_59", "STEAL_HP", 63),
		("DETAILS_60", "DETAILS_TOOLTIP_60", "STEAL_SP", 64),
		("DETAILS_61", "DETAILS_TOOLTIP_61", "HP_REGEN", 32),
		("DETAILS_62", "DETAILS_TOOLTIP_62", "SP_REGEN", 33),
		("DETAILS_63", "DETAILS_TOOLTIP_63", "BLOCK", 67),
		("DETAILS_64", "DETAILS_TOOLTIP_64", "DODGE", 68),
		("DETAILS_65", "DETAILS_TOOLTIP_65", "REFLECT_MELEE", 79),
		("DETAILS_66", "DETAILS_TOOLTIP_66", "KILL_HP_RECOVERY", 87),
		("DETAILS_67", "DETAILS_TOOLTIP_67", "KILL_SP_RECOVER", 82),
		("DETAILS_68", "DETAILS_TOOLTIP_68", "EXP_DOUBLE_BONUS", 83),
		("DETAILS_69", "DETAILS_TOOLTIP_69", "GOLD_DOUBLE_BONUS", 84),
		("DETAILS_70", "DETAILS_TOOLTIP_70", "ITEM_DROP_BONUS", 85),
	)),
	("DETAILS_CATE_6", (
		("DETAILS_71", "DETAILS_TOOLTIP_71", "MALL_ATTBONUS", 114),
		("DETAILS_72", "DETAILS_TOOLTIP_72", "MALL_DEFBONUS", 115),
		("DETAILS_73", "DETAILS_TOOLTIP_73", "MALL_EXPBONUS", 116),
		("DETAILS_74", "DETAILS_TOOLTIP_74", "MALL_ITEMBONUS", 117),
		("DETAILS_75", "DETAILS_TOOLTIP_75", "MALL_GOLDBONUS", 118),
	)),
)


def _text(locale, key):
	"""The locale's string, or the key itself when the locale lacks it."""
	text = getattr(locale, key, key)
	return text if isinstance(text, str) else key


def lines(locale):
	"""The panel's lines, in order: each category's header ({"head": True,
	"label", "tooltip": "", "point": None}), then its rows ({"head": False,
	"label", "tooltip", "point"}), the texts from the locale module."""
	found = []
	for category, rows in CATEGORIES:
		found.append({"head": True, "label": _text(locale, category), "tooltip": "", "point": None})
		for label, tooltip, _, point in rows:
			found.append({"head": False, "label": _text(locale, label), "tooltip": _text(locale, tooltip), "point": point})
	return found


def value_text(line, get_status):
	"""What a line shows as its value: the point's value as legacy shows a
	number (get_status is player.GetStatus); "" for a header."""
	if line["point"] is None:
		return ""
	return str(get_status(line["point"]))


def show_tooltip(toolTip, line):
	"""A row's hover, in both windows: its label as the title and its
	tooltip text wrapped under it; a header shows none."""
	if not line["tooltip"]:
		toolTip.HideToolTip()
		return
	toolTip.ClearToolTip()
	toolTip.SetTitle(line["label"])
	toolTip.AppendDescription(line["tooltip"])
	toolTip.ShowToolTip()
