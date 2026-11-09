"""NovaUI pet skill tooltip (the skill tooltip's document,
nui/windows/skill-tooltip/skill-tooltip.rml; NOVA-24).

The pet window and the pet's mini window make PetSkillToolTip below through
nui_windows.make("tooltips", ...) instead of uiToolTip.PetSkillToolTip: a
subclass of the legacy class with nui_tooltip.Facade first, so SetSkill and
its lines (the skill's name and description from the client's data, the
level, the bonus at the value the server sent) are legacy's own code, on
recording widgets, shown on the skill tooltip's board (kind "skill", which
the character window's skill tooltip shares: one shows at a time)."""

import uiToolTip

import nui_skill_tooltip
import nui_tooltip


@nui_tooltip.transactional
class PetSkillToolTip(nui_tooltip.Facade, uiToolTip.PetSkillToolTip):
	"""uiToolTip.PetSkillToolTip on NovaUI (PetWindow and PetInterfaceWindow's
	skillToolTip)."""

	LEGACY = uiToolTip.PetSkillToolTip
	KIND = "skill"

	def _make_board(self):
		return nui_skill_tooltip._SkillTooltipBoard()
