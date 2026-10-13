"""NovaUI link tooltip (nui/windows/link-tooltip/link-tooltip.rml; P14 spec 5).

While the tooltips flag is on, Interface.__MakeDialogs makes
HyperlinkItemToolTip below through nui_windows.make() instead of
uiToolTip.HyperlinkItemToolTip: a subclass of the legacy class with
nui_tooltip.Facade first. Interface.MakeHyperlinkTooltip (a chat link's
press) calls SetHyperlinkItem, legacy's own code, on recording widgets. The
board is placed at the pointer once and held (legacy's never moves after
its SetHyperlinkItem), takes the pointer as legacy's pickable board does,
and a left press on it hides it (legacy's OnMouseLeftButtonDown)."""

import uiToolTip

import nui
import nui_tooltip

DOCUMENT = "nui/windows/link-tooltip/link-tooltip.rml"
KIND = "link"


class _LinkTooltipBoard(nui.Window):
	"""The link tooltip's document; a left press goes to the facade that
	shows in it."""

	DOCUMENT = DOCUMENT
	MODEL = "link_tooltip"

	def initial_model(self):
		return {"lines": [], "min_w": uiToolTip.ToolTip.TOOL_TIP_WIDTH}

	@nui.on("tip_press")
	def on_tip_press(self, button):
		owner = nui_tooltip._owner(KIND)
		if button == 0 and owner is not None:
			owner.OnMouseLeftButtonDown()


@nui_tooltip.transactional
class HyperlinkItemToolTip(nui_tooltip.Facade, uiToolTip.HyperlinkItemToolTip):
	"""uiToolTip.HyperlinkItemToolTip on NovaUI (Interface.hyperlinkItemTooltip)."""

	LEGACY = uiToolTip.HyperlinkItemToolTip
	KIND = KIND
	FOLLOW_ONCE = True

	def _make_board(self):
		return _LinkTooltipBoard()
