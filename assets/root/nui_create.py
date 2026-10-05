"""NovaUI character create (nui/windows/create/create.rml).

While the "create" window flag is on, networkModule.MainStream's create
setter makes CreateCharacterWindow below through nui_windows.make() instead
of introCreate.CreateCharacterWindow. It subclasses the legacy class, which
stays the phase window C++ talks to and keeps the 3D characters, the name
checks and the create packet. Inherited unchanged: the C++ callbacks
OnCreateSuccess and OnCreateFailure; __CheckCreateCharacter (the
CREATE_INPUT_NAME, CREATE_ERROR_GM_NAME and CREATE_ERROR_INSULT_NAME popups,
with EnableWindow as their callback); CancelCreate, ResetStat, the slot
index methods, __GetSlotChrID, __MakeCharacter, GetSlotIndex, PopupMessage
and OnPressExitKey.

The legacy class names its pickers __SelectGender, __SelectShape and
__SelectSlot, which Python stores as _CreateCharacterWindow__SelectGender
and so on; this subclass has the same name, so its own __Select* methods
replace them for the legacy code too. Only the board moves to the document:
the gender, shape and slot pickers set the model instead of the legacy
radio buttons, the job description is plain paragraphs (nui_desc_text, the
G15 subset), the gauges show at once, and there is no tooltip (the legacy
board shows one only over its hidden + buttons). F1 and F2 select man and
woman (the legacy keys name MAN_PAGE and WOMAN_PAGE, which do not exist).

The document loads hidden in __init__ (nui_ready, nui_discard and __del__
follow nui_windows.make()'s protocol, as nui_loading does)."""

import math
import weakref

import app
import chr
import event
import musicInfo
import net
import playerSettingModule
import snd
import systemSetting
import ui
import uiScriptLocale
import wndMgr

import introCreate
import nui
import nui_desc_text

DOCUMENT = "nui/windows/create/create.rml"
BACKGROUND = "d:/ymir work/ui/intro/select/select.sub"
NAME_FIELD = "create-name"
JOB_NAMES = ("warrior", "assassin", "sura", "shaman")  # the slot order
STATS = ("hth", "int", "str", "dex")
# How many frames a focus of the name field may wait for the field to be
# enabled again (its disabled attribute follows the model at the next update).
FOCUS_TRIES = 10


def _keep(owner):
	"""The owner as a weak proxy; an object that takes no weak reference (a
	plain object() from a fixture check) is kept as it is. The board never
	calls it while it is being made."""
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


def job_image(slot):
	"""The class-name art of a slot's job, from the current locale (the
	legacy board names the cz art in every locale)."""
	if 0 <= slot < len(JOB_NAMES):
		return uiScriptLocale.SELECT_PATH + "name_%s.sub" % JOB_NAMES[slot]
	return ""


class CreateBoard(nui.Window):
	"""The create board's document, model and handlers; it reports to its
	owner, the phase window. The name field's text stays out of the model:
	every edit reaches name_edit, which keeps it. While a create is under
	way (busy) the handlers do nothing, as the disabled legacy buttons."""

	DOCUMENT = DOCUMENT
	MODEL = "create"

	def __init__(self, owner):
		self._owner = _keep(owner)
		self.name = ""   # the name field's text, as name_edit last saw it
		nui.Window.__init__(self)
		if self._doc:
			self.element_on(NAME_FIELD, "keydown", self._on_name_key)

	def initial_model(self):
		values = {"slot": 0, "job_image": "", "paragraphs": [], "gender": 0, "shape": 0, "busy": False}
		for stat in STATS:
			values["stat_" + stat] = ""
			values["gauge_" + stat] = 0.0
		return values

	def _idle(self):
		return not self.get("busy")

	def typed_name(self):
		"""The name field's text: the field's own value while the document
		answers, else the last edit."""
		value = self.get_value(NAME_FIELD)
		return value if isinstance(value, str) else self.name

	def _on_name_key(self, event):
		# Escape in the field cancels, as the legacy edit line's escape event.
		if event.get("key_identifier") != nui.KEY_ESCAPE or not self.is_visible() or not self._idle():
			return None
		self._owner.CancelCreate()
		return True

	@nui.on("left")
	def on_left(self):
		if self._idle():
			self._owner._CreateCharacterWindow__DecreaseSlotIndex()

	@nui.on("right")
	def on_right(self):
		if self._idle():
			self._owner._CreateCharacterWindow__IncreaseSlotIndex()

	@nui.on("gender")
	def on_gender(self, gender):
		if self._idle():
			self._owner._CreateCharacterWindow__SelectGender(gender)

	@nui.on("shape")
	def on_shape(self, shape):
		if self._idle():
			self._owner._CreateCharacterWindow__SelectShape(shape)

	@nui.on("create")
	def on_create(self):
		if self._idle():
			self._owner.CreateCharacter()

	@nui.on("cancel")
	def on_cancel(self):
		if self._idle():
			self._owner.CancelCreate()

	@nui.on("name_edit")
	def on_name_edit(self, value, linebreak):
		self.name = value if isinstance(value, str) else ""
		# Enter in the field creates, as the legacy edit line's return event.
		if linebreak and self._idle():
			self._owner.CreateCharacter()


class CreateCharacterWindow(introCreate.CreateCharacterWindow):
	"""introCreate.CreateCharacterWindow with its board on NovaUI."""

	def __init__(self, stream):
		introCreate.CreateCharacterWindow.__init__(self, stream)
		self._nui_discarded = False
		self._focus_tries = 0
		self.board = None
		self.backGround = None
		self.chrRenderer = None
		try:
			self.board = CreateBoard(self)
		except Exception:
			self.nui_discard()
			raise

	def __del__(self):
		self._destroy_board()
		if getattr(self, "_nui_discarded", False):
			ui.Window.__del__(self)
			return
		introCreate.CreateCharacterWindow.__del__(self)

	# --- the nui_windows.make() protocol ------------------------------------------

	def nui_ready(self):
		return getattr(self, "board", None) is not None and bool(self.board._doc)

	def nui_discard(self):
		self._nui_discarded = True
		self._destroy_board()

	def _destroy_board(self):
		board = getattr(self, "board", None)
		self.board = None
		if board is not None:
			board.destroy()

	def _set(self, **values):
		if self.board is not None:
			self.board.set(**values)

	def _typed_name(self):
		return self.board.typed_name() if self.board is not None else ""

	def _focus_name(self):
		"""Gives the name field the focus now, or within the next few frames
		(OnUpdate) while it is still disabled or hidden."""
		self._focus_tries = 0
		if self.board is not None and self.board.focus(NAME_FIELD):
			return
		self._focus_tries = FOCUS_TRIES

	# --- the legacy surface -------------------------------------------------------

	def Open(self):
		playerSettingModule.LoadGameData("INIT")

		self.reservingRaceIndex = -1
		self.reservingShapeIndex = -1
		self.reservingStartTime = 0
		self.stat = [0, 0, 0, 0]

		self.gender = 0
		self.slot = -1
		self.shapeList = [
			[0, 0, 0, 0],
			[0, 0, 0, 0]]

		self.descIndex = 0

		self.curRotation = [] + self.SLOT_ROTATION
		self.destRotation = [] + self.SLOT_ROTATION
		self.curNameAlpha = [0.0, 0.0, 0.0, 0.0, 0.0]
		self.destNameAlpha = [0.0, 0.0, 0.0, 0.0, 0.0]
		self.curGauge = [0.0, 0.0, 0.0, 0.0]
		self.destGauge = [0.0, 0.0, 0.0, 0.0]

		# The legacy background and the character renderer under it, without
		# the uiscript (createcharacterwindow.py, BackGround).
		self.backGround = ui.ExpandedImageBox()
		self.backGround.LoadImage(BACKGROUND)
		self.backGround.SetScale(float(wndMgr.GetScreenWidth()) / 1024.0, float(wndMgr.GetScreenHeight()) / 768.0)
		self.chrRenderer = self.CharacterRenderer()
		self.chrRenderer.SetParent(self.backGround)
		self.chrRenderer.Show()

		if self.board is not None:
			self.board.name = ""

		self.EnableWindow()
		self.__SelectSlot(0)

		app.SetCamera(500.0, 10.0, 180.0, 95.0)

		self._CreateCharacterWindow__MakeCharacter(0, 0, playerSettingModule.RACE_WARRIOR_M)
		self._CreateCharacterWindow__MakeCharacter(0, 1, playerSettingModule.RACE_ASSASSIN_M)
		self._CreateCharacterWindow__MakeCharacter(0, 2, playerSettingModule.RACE_SURA_M)
		self._CreateCharacterWindow__MakeCharacter(0, 3, playerSettingModule.RACE_SHAMAN_M)

		self._CreateCharacterWindow__MakeCharacter(1, 0, playerSettingModule.RACE_WARRIOR_W)
		self._CreateCharacterWindow__MakeCharacter(1, 1, playerSettingModule.RACE_ASSASSIN_W)
		self._CreateCharacterWindow__MakeCharacter(1, 2, playerSettingModule.RACE_SURA_W)
		self._CreateCharacterWindow__MakeCharacter(1, 3, playerSettingModule.RACE_SHAMAN_W)

		self.__SelectGender(app.GetRandom(introCreate.MAN, introCreate.WOMAN))
		self.__SelectShape(0)
		self.__SelectSlot(app.GetRandom(0, 3))

		self.backGround.Show()
		if self.board is not None:
			self.board.show()
		self.Show()
		self._focus_name()

		if musicInfo.createMusic != "":
			snd.SetMusicVolume(systemSetting.GetMusicVolume())
			snd.FadeInMusic("BGM/" + musicInfo.createMusic)

		app.ShowCursor()

	def Close(self):
		self._destroy_board()
		self._focus_tries = 0
		self.stream = 0
		if self.backGround:
			self.backGround.Hide()
		self.chrRenderer = None
		self.backGround = None

		if musicInfo.createMusic != "":
			snd.FadeOutMusic("BGM/" + musicInfo.createMusic)

		for id in range(introCreate.BASE_CHR_ID + introCreate.SLOT_COUNT * introCreate.PAGE_COUNT):
			chr.DeleteInstance(id)

		self.Hide()

		app.HideCursor()
		event.Destroy()

	def EnableWindow(self):
		self.reservingRaceIndex = -1
		self.reservingShapeIndex = -1
		self._set(busy=False)
		self._focus_name()

		for page in range(introCreate.PAGE_COUNT):
			for slot in range(introCreate.SLOT_COUNT):
				chr_id = self._CreateCharacterWindow__GetSlotChrID(page, slot)
				chr.SelectInstance(chr_id)
				chr.BlendLoopMotion(chr.MOTION_INTRO_WAIT, 0.1)

	def DisableWindow(self):
		self._focus_tries = 0
		self._set(busy=True)

	def __SelectGender(self, gender):
		self.gender = gender
		self._set(gender=gender)

		if gender == introCreate.MAN:
			for i in range(introCreate.SLOT_COUNT):
				chr.SelectInstance(self._CreateCharacterWindow__GetSlotChrID(0, i))
				chr.Show()
			for i in range(introCreate.SLOT_COUNT):
				chr.SelectInstance(self._CreateCharacterWindow__GetSlotChrID(1, i))
				chr.Hide()
		else:
			for i in range(introCreate.SLOT_COUNT):
				chr.SelectInstance(self._CreateCharacterWindow__GetSlotChrID(0, i))
				chr.Hide()
			for i in range(introCreate.SLOT_COUNT):
				chr.SelectInstance(self._CreateCharacterWindow__GetSlotChrID(1, i))
				chr.Show()

	def __SelectShape(self, shape):
		self.shapeList[self.gender][self.slot] = shape
		self._set(shape=shape)

		chr_id = self._CreateCharacterWindow__GetSlotChrID(self.gender, self.slot)
		chr.SelectInstance(chr_id)
		chr.ChangeShape(shape)
		chr.SetMotionMode(chr.MOTION_MODE_GENERAL)
		chr.SetLoopMotion(chr.MOTION_INTRO_WAIT)

	def RefreshStat(self):
		statSummary = self.stat[0] + self.stat[1] + self.stat[2] + self.stat[3]
		self.destGauge = (
			float(self.stat[0]) / float(statSummary),
			float(self.stat[1]) / float(statSummary),
			float(self.stat[2]) / float(statSummary),
			float(self.stat[3]) / float(statSummary),
		)

		values = {}
		for i, stat in enumerate(STATS):
			values["stat_" + stat] = str(self.stat[i])
			values["gauge_" + stat] = self.destGauge[i]
		self._set(**values)

	def __SelectSlot(self, slot):
		if slot < 0:
			return

		if slot >= introCreate.SLOT_COUNT:
			return

		if self.slot == slot:
			return

		self.slot = slot
		self.ResetStat()

		for i in range(introCreate.SLOT_COUNT):
			self.destNameAlpha[i] = 0.0

		self.destNameAlpha[slot] = 1.0

		for i in range(introCreate.SLOT_COUNT):
			self.destRotation[(i + self.slot) % introCreate.SLOT_COUNT] = self.SLOT_ROTATION[i]

		if self.IsShow():
			snd.PlaySound("sound/ui/click.wav")

		self._set(slot=slot, job_image=job_image(slot), paragraphs=nui_desc_text.load(self.DESCRIPTION_FILE_NAME[slot]))

		chr_id = self._CreateCharacterWindow__GetSlotChrID(self.gender, slot)
		if chr.HasInstance(chr_id):
			chr.SelectInstance(chr_id)
			self.__SelectShape(self.shapeList[self.gender][slot])

	def CreateCharacter(self):
		if -1 != self.reservingRaceIndex:
			return

		textName = self._typed_name()
		if False == self._CreateCharacterWindow__CheckCreateCharacter(textName):
			return

		if musicInfo.selectMusic != "":
			snd.FadeLimitOutMusic("BGM/" + musicInfo.selectMusic, systemSetting.GetMusicVolume() * 0.05)

		self.DisableWindow()

		chr_id = self._CreateCharacterWindow__GetSlotChrID(self.gender, self.slot)

		chr.SelectInstance(chr_id)

		self.reservingRaceIndex = chr.GetRace()

		self.reservingShapeIndex = self.shapeList[self.gender][self.slot]
		self.reservingStartTime = app.GetTime()

		for eachSlot in range(introCreate.SLOT_COUNT):

			sel_id = self._CreateCharacterWindow__GetSlotChrID(self.gender, eachSlot)

			chr.SelectInstance(sel_id)

			if eachSlot == self.slot:
				chr.PushOnceMotion(chr.MOTION_INTRO_SELECTED)
			else:
				chr.PushOnceMotion(chr.MOTION_INTRO_NOT_SELECTED)

	def PrevDescriptionPage(self):
		pass  # the description scrolls; it has no pages (G15 subset)

	def NextDescriptionPage(self):
		pass

	def OverInStatButton(self, stat):
		pass  # no + buttons, so no tooltip (CREATE_STAT_POINT is 0)

	def OverOutStatButton(self):
		pass

	def OnKeyDown(self, key):
		if key == 2:
			self.__SelectSlot(0)
		if key == 3:
			self.__SelectSlot(1)
		if key == 4:
			self.__SelectSlot(2)
		if key == 5:
			self.__SelectSlot(3)

		if 203 == key:
			self._CreateCharacterWindow__DecreaseSlotIndex()
		if 205 == key:
			self._CreateCharacterWindow__IncreaseSlotIndex()

		# F1 and F2 (legacy: MAN_PAGE and WOMAN_PAGE, names that do not exist).
		if 59 == key:
			self.__SelectGender(introCreate.MAN)
		if 60 == key:
			self.__SelectGender(introCreate.WOMAN)

		return True

	def OnUpdate(self):
		# The 3D characters, their rotation and the create timer stay per
		# frame; the gauges and the class-name art show at once (no easing).
		chr.Update()

		for page in range(introCreate.PAGE_COUNT):
			for i in range(introCreate.SLOT_COUNT):
				chr.SelectInstance(self._CreateCharacterWindow__GetSlotChrID(page, i))

				distance = 50.0
				rotRadian = self.curRotation[i] * (math.pi * 2) / 360.0
				x = distance * math.sin(rotRadian) + distance * math.cos(rotRadian)
				y = distance * math.cos(rotRadian) - distance * math.sin(rotRadian)
				chr.SetPixelPosition(int(x), int(y), 30)

				if abs(self.destRotation[i] - self.curRotation[i]) < 1.0:
					self.curRotation[i] = self.destRotation[i]

				dir = app.GetRotatingDirection(self.destRotation[i], self.curRotation[i])
				rot = app.GetDegreeDifference(self.destRotation[i], self.curRotation[i])

				if app.DEGREE_DIRECTION_RIGHT == dir:
					self.curRotation[i] += rot / 10.0
				elif app.DEGREE_DIRECTION_LEFT == dir:
					self.curRotation[i] -= rot / 10.0

				self.curRotation[i] = (self.curRotation[i] + 360.0) % 360.0

		if -1 != self.reservingRaceIndex:
			if app.GetTime() - self.reservingStartTime >= 1.5:

				chrSlot = self.stream.GetCharacterSlot()
				textName = self._typed_name()
				raceIndex = self.reservingRaceIndex
				shapeIndex = self.reservingShapeIndex

				startStat = self.START_STAT[self.reservingRaceIndex]
				statCon = self.stat[0] - startStat[0]
				statInt = self.stat[1] - startStat[1]
				statStr = self.stat[2] - startStat[2]
				statDex = self.stat[3] - startStat[3]

				net.SendCreateCharacterPacket(chrSlot, textName, raceIndex, shapeIndex, statCon, statInt, statStr, statDex)

				self.reservingRaceIndex = -1

		# A focus EnableWindow asked for while the field was still disabled
		# (its attribute follows the model at the update after set()).
		if self._focus_tries > 0:
			self._focus_tries -= 1
			if self.board is None or self.board.focus(NAME_FIELD):
				self._focus_tries = 0
