"""NovaUI skill tooltip (nui/windows/skill-tooltip/skill-tooltip.rml; P14 spec 5).

While the tooltips flag is on, Interface.__MakeDialogs makes SkillToolTip
below through nui_windows.make() instead of uiToolTip.SkillToolTip: a
subclass of the legacy class with nui_tooltip.Facade first, so SetSkill,
SetSkillNew, SetSkillOnlyName and every rule they run are legacy's own code,
on recording widgets, and its board shows what they recorded (the party
skill's lines too, which AutoAppendTextLine makes). The character window,
the guild window and the taskbar show it."""

import uiToolTip

import nui
import nui_tooltip

DOCUMENT = "nui/windows/skill-tooltip/skill-tooltip.rml"


class _SkillTooltipBoard(nui.Window):
	"""The skill tooltip's document, shared by every SkillToolTip facade."""

	DOCUMENT = DOCUMENT
	MODEL = "skill_tooltip"

	def initial_model(self):
		return {"lines": [], "min_w": uiToolTip.SkillToolTip.SKILL_TOOL_TIP_WIDTH}


@nui_tooltip.transactional
class SkillToolTip(nui_tooltip.Facade, uiToolTip.SkillToolTip):
	"""uiToolTip.SkillToolTip on NovaUI (Interface.tooltipSkill)."""

	LEGACY = uiToolTip.SkillToolTip
	KIND = "skill"

	def _make_board(self):
		return _SkillTooltipBoard()
