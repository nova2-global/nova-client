"""NovaUI character select (nui/windows/select/select.rml).

While the "select" window flag is on, networkModule.MainStream's select
setter makes SelectCharacterWindow below through nui_windows.make() instead
of introSelect.SelectCharacterWindow. It subclasses the legacy class, which
stays the phase window C++ talks to and keeps the 3D characters, the
DirectInput hotkeys (OnKeyDown: Escape, 1 to 4, Enter, the arrows), the
start timer and every packet. Inherited unchanged: the C++ callbacks
OnCreateFailure, OnDeleteSuccess, OnDeleteFailure and Refresh's legacy part;
the private-code and rename dialogs (uiCommon.InputDialogWithDescription,
the dialog kit while "dialogs" is on); MakeCharacter, CreateCharacter, the
slot index methods, SameLoginDisconnect, PopupMessage and OnPressExitKey.

Only the board moves to the document: the legacy background and the
character renderer are made without the uiscript, the board's labels,
gauges and buttons come from the model, and the gauge and name-art easing
is gone (values show at once). The delete question is uiCommon.QuestionDialog
(the kit, or the legacy dialog, whose Open puts it above NovaUI). The board
adds a slot list: one row per slot with its character's name and level.

The document loads hidden in __init__ (nui_ready, nui_discard and __del__
follow nui_windows.make()'s protocol, as nui_loading does)."""

import math
import weakref

import app
import chr
import localeInfo
import musicInfo
import net
import playerSettingModule
import snd
import systemSetting
import ui
import uiCommon
import uiScriptLocale
import wndMgr

import introSelect
import nui

DOCUMENT = "nui/windows/select/select.rml"
BACKGROUND = "d:/ymir work/ui/intro/select/select.sub"
FLAG_IMAGE = "d:/ymir work/ui/intro/empire/empireflag_%s.sub"
JOB_NAMES = ("warrior", "assassin", "sura", "shaman")  # chr.RaceToJob order
EMPIRE_LETTERS = {net.EMPIRE_A: "a", net.EMPIRE_B: "b", net.EMPIRE_C: "c"}
EMPTY_SLOT = "@ui.SELECT_SLOT_EMPTY"
NO_GUILD = "@game.SELECT_NOT_JOIN_GUILD"
GAUGE_FULL = 90.0  # a stat of 90 fills its gauge (introselect.py, SelectSlot)
STATS = ("hth", "int", "str", "dex")


def _keep(owner):
	"""The owner as a weak proxy; an object that takes no weak reference (a
	plain object() from a fixture check) is kept as it is. The board never
	calls it while it is being made."""
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


def gauge_value(stat):
	"""A stat's gauge, from 0 to 1."""
	return min(max(float(stat) / GAUGE_FULL, 0.0), 1.0)


def empty_board():
	"""The model keys of an empty slot (InitCharacterBoard)."""
	values = {"occupied": False, "name": "", "level": "", "playtime": "", "guild": NO_GUILD, "job_image": ""}
	for stat in STATS:
		values["stat_" + stat] = ""
		values["gauge_" + stat] = 0.0
	return values


def job_image(job):
	"""The class-name art of a job, from the current locale, as a store path
	from the root (the document binds it as it is); "" for none."""
	if 0 <= job < len(JOB_NAMES):
		return "/" + uiScriptLocale.SELECT_PATH + "name_%s.sub" % JOB_NAMES[job]
	return ""


class SelectBoard(nui.Window):
	"""The select board's document, model and handlers; it reports to its
	owner, the phase window. Every handler does nothing while a start is
	under way (busy), as the disabled legacy buttons did."""

	DOCUMENT = DOCUMENT
	MODEL = "select"

	def __init__(self, owner):
		self._owner = _keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		values = empty_board()
		values.update({"slot": 0, "busy": False, "empire_name": "", "flag_image": "",
			"slots": [{"index": index, "label": EMPTY_SLOT, "level": 0} for index in range(4)]})
		return values

	def _idle(self):
		return not self.get("busy")

	@nui.on("pick_slot")
	def on_pick_slot(self, index):
		if self._idle():
			self._owner.SelectSlot(index)

	@nui.on("left")
	def on_left(self):
		if self._idle():
			self._owner.DecreaseSlotIndex()

	@nui.on("right")
	def on_right(self):
		if self._idle():
			self._owner.IncreaseSlotIndex()

	@nui.on("start")
	def on_start(self):
		if self._idle():
			self._owner.StartGame()

	@nui.on("create")
	def on_create(self):
		if self._idle():
			self._owner.CreateCharacter()

	@nui.on("remove")
	def on_remove(self):
		if not self._idle():
			return
		if introSelect.NOT_NEED_DELETE_CODE:
			self._owner.PopupDeleteQuestion()
		else:
			self._owner.InputPrivateCode()

	@nui.on("leave")
	def on_leave(self):
		if self._idle():
			self._owner.ExitSelect()


class SelectCharacterWindow(introSelect.SelectCharacterWindow):
	"""introSelect.SelectCharacterWindow with its board on NovaUI."""

	def __init__(self, stream):
		introSelect.SelectCharacterWindow.__init__(self, stream)
		self._nui_discarded = False
		self.board = None
		self.backGround = None
		self.chrRenderer = None
		self.dlgQuestion = None
		self.privateInputBoard = None
		try:
			self.board = SelectBoard(self)
		except Exception:
			self.nui_discard()
			raise

	def __del__(self):
		self._destroy_board()
		if getattr(self, "_nui_discarded", False):
			ui.Window.__del__(self)
			return
		introSelect.SelectCharacterWindow.__del__(self)

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

	def _close_delete_question(self):
		if self.dlgQuestion:
			self.dlgQuestion.Close()

	def _refresh_slots(self):
		"""The slot list from the account's slot data."""
		slots = []
		for index in range(self.SLOT_COUNT):
			if net.GetAccountCharacterSlotDataInteger(index, net.ACCOUNT_CHARACTER_SLOT_ID):
				name = net.GetAccountCharacterSlotDataString(index, net.ACCOUNT_CHARACTER_SLOT_NAME)
				level = net.GetAccountCharacterSlotDataInteger(index, net.ACCOUNT_CHARACTER_SLOT_LEVEL)
				slots.append({"index": index, "label": nui.plain_text(name), "level": int(level)})
			else:
				slots.append({"index": index, "label": EMPTY_SLOT, "level": 0})
		self._set(slots=slots)

	# --- the legacy surface -------------------------------------------------------

	def Open(self):
		# The legacy background and the character renderer under it, without
		# the uiscript (selectcharacterwindow.py, BackGround).
		self.backGround = ui.ExpandedImageBox()
		self.backGround.LoadImage(BACKGROUND)
		self.backGround.SetScale(float(wndMgr.GetScreenWidth()) / 1024.0, float(wndMgr.GetScreenHeight()) / 768.0)
		self.chrRenderer = self.CharacterRenderer()
		self.chrRenderer.SetParent(self.backGround)
		self.chrRenderer.Show()

		self.dlgQuestion = uiCommon.QuestionDialog()
		self.dlgQuestion.SetText(localeInfo.SELECT_DO_YOU_DELETE_REALLY)
		self.dlgQuestion.SetAcceptEvent(ui.__mem_func__(self.RequestDeleteCharacter))
		self.dlgQuestion.SetCancelEvent(ui.__mem_func__(self._close_delete_question))

		playerSettingModule.LoadGameData("INIT")

		self.InitCharacterBoard()
		self._set(busy=False)

		self.backGround.Show()
		if self.board is not None:
			self.board.show()
		self.SetWindowName("SelectCharacterWindow")
		self.Show()

		if self.slot >= 0:
			self.SelectSlot(self.slot)

		if musicInfo.selectMusic != "":
			snd.SetMusicVolume(systemSetting.GetMusicVolume())
			snd.FadeInMusic("BGM/" + musicInfo.selectMusic)

		app.SetCenterPosition(0.0, 0.0, 0.0)
		app.SetCamera(1550.0, 15.0, 180.0, 95.0)

		self.isLoad = 1
		self.Refresh()

		if self.stream.isAutoSelect:
			chrSlot = self.stream.GetCharacterSlot()
			self.SelectSlot(chrSlot)
			self.StartGame()

		self.HideAllFlag()
		self.SetEmpire(net.GetEmpireID())

		app.ShowCursor()

	def Close(self):
		if musicInfo.selectMusic != "":
			snd.FadeOutMusic("BGM/" + musicInfo.selectMusic)

		self.stream.popupWindow.Close()

		self._destroy_board()
		self.flagDict = {}
		if self.backGround:
			self.backGround.Hide()
		self.chrRenderer = None
		self.backGround = None

		self._close_delete_question()
		self.dlgQuestion = None
		self.privateInputBoard = None
		self.nameInputBoard = None

		chr.DeleteInstance(0)
		chr.DeleteInstance(1)
		chr.DeleteInstance(2)
		chr.DeleteInstance(3)

		self.Hide()
		self.KillFocus()

		app.HideCursor()

	def SetEmpire(self, id):
		letter = EMPIRE_LETTERS.get(id)
		if letter is None:
			self._set(empire_name="")
			return
		self._set(empire_name="@game.EMPIRE_" + letter.upper(), flag_image=FLAG_IMAGE % letter)

	def HideAllFlag(self):
		self._set(flag_image="")

	def Refresh(self):
		introSelect.SelectCharacterWindow.Refresh(self)
		self._refresh_slots()

	def SelectSlot(self, index):
		if index < 0:
			return
		if index >= self.SLOT_COUNT:
			return

		self.slot = index

		chr.SelectInstance(self.slot)

		for i in range(self.CHARACTER_TYPE_COUNT):
			self.destNameAlpha[i] = 0.0

		for i in range(self.SLOT_COUNT):
			self.destRotation[(i + self.slot) % self.SLOT_COUNT] = self.SLOT_ROTATION[i]

		self.destGauge = [0.0, 0.0, 0.0, 0.0]

		id = net.GetAccountCharacterSlotDataInteger(self.slot, net.ACCOUNT_CHARACTER_SLOT_ID)
		if 0 == id:
			self.InitCharacterBoard()
			self._set(slot=index)
			return

		playTime = net.GetAccountCharacterSlotDataInteger(self.slot, net.ACCOUNT_CHARACTER_SLOT_PLAYTIME)
		level = net.GetAccountCharacterSlotDataInteger(self.slot, net.ACCOUNT_CHARACTER_SLOT_LEVEL)
		race = net.GetAccountCharacterSlotDataInteger(self.slot, net.ACCOUNT_CHARACTER_SLOT_RACE)
		valueHTH = net.GetAccountCharacterSlotDataInteger(self.slot, net.ACCOUNT_CHARACTER_SLOT_HTH)
		valueINT = net.GetAccountCharacterSlotDataInteger(self.slot, net.ACCOUNT_CHARACTER_SLOT_INT)
		valueSTR = net.GetAccountCharacterSlotDataInteger(self.slot, net.ACCOUNT_CHARACTER_SLOT_STR)
		valueDEX = net.GetAccountCharacterSlotDataInteger(self.slot, net.ACCOUNT_CHARACTER_SLOT_DEX)
		name = net.GetAccountCharacterSlotDataString(self.slot, net.ACCOUNT_CHARACTER_SLOT_NAME)
		net.GetAccountCharacterSlotDataInteger(self.slot, net.ACCOUNT_CHARACTER_SLOT_GUILD_ID)
		guildName = net.GetAccountCharacterSlotDataString(self.slot, net.ACCOUNT_CHARACTER_SLOT_GUILD_NAME)
		self.changeNameFlag = net.GetAccountCharacterSlotDataInteger(self.slot, net.ACCOUNT_CHARACTER_SLOT_CHANGE_NAME_FLAG)

		job = chr.RaceToJob(race)
		if job >= 0 and job < self.CHARACTER_TYPE_COUNT:
			self.destNameAlpha[job] = 1.0

		stats = (valueHTH, valueINT, valueSTR, valueDEX)
		if float(sum(stats)) > 0.0:
			self.destGauge = [gauge_value(value) for value in stats]

		values = {"slot": index, "occupied": True, "name": nui.plain_text(name), "level": str(level),
			"playtime": str(playTime), "guild": nui.plain_text(guildName) if guildName else NO_GUILD,
			"job_image": job_image(job)}
		for stat, value, gauge in zip(STATS, stats, self.destGauge):
			values["stat_" + stat] = str(value)
			values["gauge_" + stat] = gauge
		self._set(**values)

	def InitCharacterBoard(self):
		self._set(**empty_board())

	def StartGame(self):
		if self.sendedChangeNamePacket:
			return

		if self.changeNameFlag:
			self.OpenChangeNameDialog()
			return

		if -1 != self.startIndex:
			return

		if musicInfo.selectMusic != "":
			snd.FadeLimitOutMusic("BGM/" + musicInfo.selectMusic, systemSetting.GetMusicVolume() * 0.05)

		self._set(busy=True)
		self._close_delete_question()

		self.stream.SetCharacterSlot(self.slot)

		self.startIndex = self.slot
		self.startReservingTime = app.GetTime()

		for i in range(self.SLOT_COUNT):

			if False == chr.HasInstance(i):
				continue

			chr.SelectInstance(i)

			if i == self.slot:
				chr.PushOnceMotion(chr.MOTION_INTRO_SELECTED, 0.1)
				continue

			chr.PushOnceMotion(chr.MOTION_INTRO_NOT_SELECTED, 0.1)

	def PopupDeleteQuestion(self):
		id = self.GetCharacterSlotID(self.slot)
		if 0 == id:
			return

		if self.dlgQuestion:
			self.dlgQuestion.Open()

	def RequestDeleteCharacter(self):
		self._close_delete_question()

		id = self.GetCharacterSlotID(self.slot)
		if 0 == id:
			self.PopupMessage(localeInfo.SELECT_EMPTY_SLOT)
			return

		net.SendDestroyCharacterPacket(self.slot, "1234567")
		self.PopupMessage(localeInfo.SELECT_DELEING)

	def DeleteCharacter(self, index):
		introSelect.SelectCharacterWindow.DeleteCharacter(self, index)
		self._refresh_slots()

	def OnChangeName(self, id, name):
		introSelect.SelectCharacterWindow.OnChangeName(self, id, name)
		self._refresh_slots()

	def ExitSelect(self):
		self._close_delete_question()

		if introSelect.LEAVE_BUTTON_FOR_POTAL:
			if app.loggined:
				self.stream.SetPhaseWindow(0)
			else:
				self.stream.SetLoginPhase()
		else:
			self.stream.SetLoginPhase()

		self.Hide()

	def OnUpdate(self):
		# The 3D characters, their rotation and the start timer stay per
		# frame; the gauges and the class-name art show at once (no easing).
		chr.Update()

		for i in range(self.SLOT_COUNT):

			if False == chr.HasInstance(i):
				continue

			chr.SelectInstance(i)

			distance = 50.0
			rotRadian = self.curRotation[i] * (math.pi * 2) / 360.0
			x = distance * math.sin(rotRadian) + distance * math.cos(rotRadian)
			y = distance * math.cos(rotRadian) - distance * math.sin(rotRadian)
			chr.SetPixelPosition(int(x), int(y), 30)

			dir = app.GetRotatingDirection(self.destRotation[i], self.curRotation[i])
			rot = app.GetDegreeDifference(self.destRotation[i], self.curRotation[i])

			if app.DEGREE_DIRECTION_RIGHT == dir:
				self.curRotation[i] += rot / 10.0
			elif app.DEGREE_DIRECTION_LEFT == dir:
				self.curRotation[i] -= rot / 10.0

			self.curRotation[i] = (self.curRotation[i] + 360.0) % 360.0

		if -1 != self.startIndex:
			if app.GetTime() - self.startReservingTime > 3.0:
				if False == self.openLoadingFlag:
					chrSlot = self.stream.GetCharacterSlot()
					net.DirectEnter(chrSlot)
					self.openLoadingFlag = True

					playTime = net.GetAccountCharacterSlotDataInteger(self.slot, net.ACCOUNT_CHARACTER_SLOT_PLAYTIME)

					import player
					player.SetPlayTime(playTime)
					import chat
					chat.Clear()  # the chat starts empty in the game
