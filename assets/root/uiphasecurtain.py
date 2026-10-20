import grp
import ui
import wndMgr
import app

# The fade follows the clock, not the frame rate.
FRAME_SECONDS = 1.0 / 60.0   # speed is alpha per 1/60 s: 0.1 fades in ten 60 Hz frames, 1/6 s
MAX_STEP_SECONDS = 0.05      # a longer frame (a phase being built) advances the fade by this much at most

class PhaseCurtain(ui.Bar):

	def __init__(self):
		print("NEW CURTAIN  ----------------------------------------------------------------------------")
		ui.Bar.__init__(self, "CURTAIN")
		self.speed = 0.1
		self.curAlpha = 0.0
		self.event = 0
		self.args = -1
		self.FadeInFlag = False
		self.lastTime = 0.0
		self.SetWindowName("PhaseCurtain")
		self.AddFlag("float")

	def __del__(self):
		print("---------------------------------------------------------------------------- DELETE CURTAIN")
		ui.Bar.__del__(self)

	def SAFE_FadeOut(self, event, args = -1):
		self.FadeOut(ui.__mem_func__(event), args)

	def FadeOut(self, event, args = -1):
		self.curAlpha = 0.0
		self.SetAlpha(self.curAlpha)
		#self.SetTop()
		self.Show()
		self.event = event
		self.args = args
		self.lastTime = app.GetTime()

	def FadeIn(self):
		self.event = 0
		self.FadeInFlag = True
		self.lastTime = app.GetTime()

	def SetAlpha(self, alpha):
		self.SetSize(wndMgr.GetScreenWidth(), wndMgr.GetScreenHeight())

		color = grp.GenerateColor(0.0, 0.0, 0.0, alpha)
		self.SetColor(color)

	def OnUpdate(self):

		now = app.GetTime()
		step = self.speed * min(max(now - self.lastTime, 0.0), MAX_STEP_SECONDS) / FRAME_SECONDS
		self.lastTime = now

		if 0 != self.event:

			self.curAlpha += step
			if self.curAlpha >= 1.0:
				self.curAlpha = 1.0

				# Use only this timer when event fade out was added
				event=self.event
				self.event = 0

				#print "Fade out complete event executed"

				if -1 != self.args:
					event(self.args)
				else:
					event()

		elif True == self.FadeInFlag:

			self.curAlpha -= step
			if self.curAlpha <= 0.0:
				self.curAlpha = 0.0
				self.eventFadeIn = 0
				self.FadeInFlag = False
				self.Hide()

		self.SetAlpha(self.curAlpha)
