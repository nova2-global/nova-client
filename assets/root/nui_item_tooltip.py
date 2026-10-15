"""NovaUI item tooltip (nui/windows/item-tooltip/item-tooltip.rml; P14 spec 5).

While the tooltips flag is on, Interface.__MakeDialogs makes ItemToolTip
below through nui_windows.make() instead of uiToolTip.ItemToolTip: a
subclass of the legacy class with nui_tooltip.Facade first, so every rule
(SetInventoryItem, SetShopItem, AddItemData and the rest) is legacy's own
code, on recording widgets, and its board shows what they recorded. The
Interface hands it to every window that shows item tooltips (spec 5.6), so
those that are not ported yet show the NovaUI tooltip too. Its legacy board
stays hidden; the document follows the pointer by legacy's rule
(follow_pointer) and its remaining times count down by themselves."""

import uiToolTip

import nui
import nui_tooltip

DOCUMENT = "nui/windows/item-tooltip/item-tooltip.rml"


class _ItemTooltipBoard(nui.Window):
	"""The item tooltip's document, shared by every ItemToolTip facade (the
	one that showed last fills it)."""

	DOCUMENT = DOCUMENT
	MODEL = "item_tooltip"

	def initial_model(self):
		return {"lines": [], "min_w": uiToolTip.ToolTip.TOOL_TIP_WIDTH}


@nui_tooltip.transactional
class ItemToolTip(nui_tooltip.Facade, uiToolTip.ItemToolTip):
	"""uiToolTip.ItemToolTip on NovaUI (Interface.tooltipItem)."""

	LEGACY = uiToolTip.ItemToolTip
	KIND = "item"

	def _make_board(self):
		return _ItemTooltipBoard()


# --- Wave 3c (P15) ---

@nui_tooltip.transactional
class PlainToolTip(nui_tooltip.Facade, uiToolTip.ToolTip):
	"""uiToolTip.ToolTip on NovaUI (P15 spec D6): a plain tooltip a window
	makes for itself (the character window's stat, job, alignment and
	emotion tooltips), made with the legacy constructor's arguments
	(PlainToolTip(130)). Its lines are legacy's own calls (AppendTextLine,
	AutoAppendTextLine, SetTitle) on recording widgets, shown in the item
	tooltip's document (KIND "item": a plain tooltip and an item tooltip
	never show at once), which follows the pointer with no per-frame
	Python, as the item tooltip does."""

	LEGACY = uiToolTip.ToolTip
	KIND = "item"

	def _make_board(self):
		return _ItemTooltipBoard()
