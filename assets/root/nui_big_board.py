"""NovaUI big notice board (nui/windows/big-board/big-board.rml).

While the "big-board" window flag is on, Interface.__MakeTipBoard makes
BigBoard below through nui_windows.make() instead of uiTip.BigBoard: the
facade of the legacy board, which the C++ callback BINARY_SetBigMessage
(game.py) feeds with SetTip. It works as the tip board does
(nui_tip_board.NoticeFacade: one tip at a time on a nui-countdown timer)
with the big board's numbers: 5 s between steps, the first tip a second
after it shows, the big font.

As players see it, legacy shows a batch of big notices once through and
then hides: its cleanup keeps only the tips made after now plus
TIP_DURATION (uitip.py BigBoard.__CleanOldTip, a condition no tip meets),
and it wraps as the last tip scrolls away. This board keeps that condition
and wraps at the step after the last tip. A long text wraps within the
board's line instead of being split into two tips at the first space past
350 px, as legacy did."""

import nui
import nui_tip_board

DOCUMENT = "nui/windows/big-board/big-board.rml"


class BigBoardBoard(nui_tip_board.NoticeBoard):
	DOCUMENT = DOCUMENT
	MODEL = "big_board"

	@nui.on("advance")
	def on_advance(self):
		self._owner.nui_advance()


class BigBoard(nui_tip_board.NoticeFacade):
	"""uiTip.BigBoard on NovaUI (Interface.bigBoard)."""

	KEY = "big-board"
	BOARD = BigBoardBoard
	SCROLL_WAIT_TIME = 5.0
	TIP_DURATION = 10.0
	OUT_STEP = False
	FONT_WIDTH = 18
	FONT_HEIGHT = 18
	LINE_WIDTH = 500
	LINE_HEIGHT = FONT_HEIGHT + 5
	STEP_HEIGHT = LINE_HEIGHT * 2
	LINE_CHANGE_LIMIT_WIDTH = 350
	FRAME_IMAGE_FILE_NAME_LIST = [
		"season1/interface/oxevent/frame_0.sub",
		"season1/interface/oxevent/frame_1.sub",
		"season1/interface/oxevent/frame_2.sub",
	]
	FRAME_IMAGE_STEP = 256
	FRAME_BASE_X = -20
	FRAME_BASE_Y = -12

	def _keep_tip(self, made, now):
		"""BigBoard.__CleanOldTip's condition, as legacy has it."""
		return now + self.TIP_DURATION <= made
