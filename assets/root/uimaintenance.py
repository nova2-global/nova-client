import math

import app
import ui
import localeInfo

# The label in red and the time left in gold, as the old maintenance window had them.
LABEL_COLOR = 0xFFF35637
TIME_COLOR = 0xFFDBAD7B

class MaintenanceWindow(ui.ThinBoard):
	"""The countdown to a scheduled server shutdown, at the top left of the screen.

	game.py opens it with the seconds left (server command shutdown_schedule) and
	closes it on a cancel (shutdown_cancel). It keeps the end time on the client's
	clock, redraws the time only when the whole second changes and hides itself
	when the time is up. The player may close it; the next schedule opens it again.
	The reason for the shutdown is in the server's chat notices.
	"""

	POSITION = (10, 70)
	HEIGHT = 36
	PADDING = 12
	GAP = 4

	def __init__(self):
		ui.ThinBoard.__init__(self)
		self.AddFlag("float")

		self.endTime = 0.0
		self.shownSeconds = 0
		self.boardWidth = 0

		# The height is fixed, so the lines centred on it are placed from the start.
		self.SetSize(0, self.HEIGHT)

		self.label = self.__MakeTextLine(LABEL_COLOR)
		self.timeLeft = self.__MakeTextLine(TIME_COLOR)

		self.closeButton = ui.Button()
		self.closeButton.SetParent(self)
		self.closeButton.SetUpVisual("d:/ymir work/ui/public/close_button_01.sub")
		self.closeButton.SetOverVisual("d:/ymir work/ui/public/close_button_02.sub")
		self.closeButton.SetDownVisual("d:/ymir work/ui/public/close_button_03.sub")
		self.closeButton.SetToolTipText(localeInfo.UI_CLOSE)
		self.closeButton.SetEvent(ui.__mem_func__(self.Close))
		self.closeButton.Show()

		(x, y) = self.POSITION
		self.SetPosition(x, y)
		self.Hide()

	def __del__(self):
		ui.ThinBoard.__del__(self)

	def __MakeTextLine(self, color):
		textLine = ui.TextLine()
		textLine.SetParent(self)
		textLine.SetWindowVerticalAlignCenter()
		textLine.SetVerticalAlignCenter()
		textLine.SetPackedFontColor(color)
		textLine.Show()
		return textLine

	def Open(self, secondsLeft):
		self.endTime = app.GetTime() + secondsLeft
		self.shownSeconds = 0
		self.boardWidth = 0

		# Set on every open, so a language change shows from the next schedule on.
		self.label.SetText(localeInfo.MAINTENANCE_TIME_LEFT)
		self.label.SetPosition(self.PADDING, 0)

		if self.__Refresh():
			self.Show()
			self.SetTop()

	def Close(self):
		self.Hide()

	# Shows the whole seconds still left. False, and hidden, once there are none.
	# Rounded to the millisecond first: the clock's float noise must not show as
	# a second more than the server sent.
	def __Refresh(self):
		seconds = int(math.ceil(round(self.endTime - app.GetTime(), 3)))

		if seconds <= 0:
			self.Hide()
			return False

		if seconds != self.shownSeconds:
			self.shownSeconds = seconds
			self.timeLeft.SetText(localeInfo.RTSecondToDHMS(seconds))
			self.__FitWidth()

		return True

	# Puts the time after the label and widens the board to fit it. It never
	# narrows while open, so it does not jitter as the text gets shorter.
	def __FitWidth(self):
		timeX = self.PADDING + self.label.GetTextSize()[0] + self.GAP
		self.timeLeft.SetPosition(timeX, 0)

		buttonWidth = self.closeButton.GetWidth()
		width = timeX + self.timeLeft.GetTextSize()[0] + self.GAP + buttonWidth + self.PADDING
		if width <= self.boardWidth:
			return

		self.boardWidth = width
		self.SetSize(width, self.HEIGHT)
		self.closeButton.SetPosition(width - self.PADDING - buttonWidth, (self.HEIGHT - self.closeButton.GetHeight()) // 2)

	def OnUpdate(self):
		self.__Refresh()
