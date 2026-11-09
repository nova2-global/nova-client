## The damage count window (NOVA-27; OLD root/uiDamageCount.py and
## uiscript/DamageCount.py, __BOSS_DAMAGE_COUNT__): the top 10 attackers of a
## damage-count world boss (mob_proto ON_CLICK 3, ON_DAMAGE_COUNT), with each
## one's damage, share and a bar against the leader, the player's own row
## framed in red, and the boss's HP.
##
## The server sends GC::BOSS_DAMAGE_COUNT rows (attacker, boss, total damage)
## to a player who targets such a boss: when the target is set, then at most
## once a second while its HP changes. game.BINARY_UpdateBossDamageCount
## feeds them here and opens the window; the target board's hooks in game.py
## close it on a new target or when the target board closes, and feed it the
## boss's HP.
##
## NEW's GC::TARGET carries the HP percentage only (the HP numbers wait for
## NOVA-40): the HP line shows "HP / max" only when a caller passes them.
## OLD's art is not in NEW's packs (see uiscript/damagecount.py): the boss's
## name stands where its face was, and an attacker's face is NEW's job face
## (ui/game/windows/face_<job>.sub). OLD's literal "Damage: %s(%2.1f%s)" is
## the locale key DAMAGE_COUNT_DAMAGE.
##
## OLD bugs fixed: the share summed the damage before the update it was
## showing (the newest attacker's new damage was left out and its old one
## kept, so the shares did not add up to 100%); a row's flash timer read
## time.clock() (CPU time, not the client's clock: app.GetTime).

import app
import ui
import wndMgr
import chr
import nonplayer
import player
import localeInfo
import colorInfo

UPDATE_COLOR = 0xff5d5d5d       # the damage text of the row that was just updated
TEXT_COLOR = 0xffffffff
OWN_ROW_COLOR = 0xffc41c1c      # the frame around the player's own row
COLOR_LIST = [0xff61384a, 0xff44542f, 0xff3c3350, 0xff2a5160, 0xff656565, 0xff9f751a, 0xff295684, 0xff6b9618] * 3
MAX_WIDTH = 380                 # the leader's bar
MAX_ROWS = 10
ROW_HEIGHT = 25
BASE_HEIGHT = 65              # OLD: 50, which left the last row 10 px below the board
LIST_BASE_HEIGHT = 15
FLASH_SECONDS = 0.1
FACE_SCALE = 0.5
OPEN_POSITION_Y = 100
OPEN_WIDTH = 720                # OLD centers the window as if it were 720 wide

# NEW's job faces (race % 4: warrior, assassin, sura, shaman), as
# playersettingmodule.FACE_IMAGE_DICT draws them.
JOB_FACES = (
	"d:/ymir work/ui/game/windows/face_warrior.sub",
	"d:/ymir work/ui/game/windows/face_assassin.sub",
	"d:/ymir work/ui/game/windows/face_sura.sub",
	"d:/ymir work/ui/game/windows/face_shaman.sub",
)


def NumberToText(num):
	"""OLD's short damage: thousands with one decimal, millions past 999999."""
	if num > 999999:
		return "%2.1fM" % (float(num) / 1000000.0)
	return "%2.1fK" % (float(num) / 1000.0)


def face_of(race):
	if race is None or race < 0:
		return ""
	return JOB_FACES[race % len(JOB_FACES)] if race < 8 else ""


def hp_color(hpPercentage):
	"""OLD's color of the HP percentage."""
	if hpPercentage > 60:
		r, g, b = colorInfo.CHAT_RGB_SHOUT
	elif hpPercentage > 24:
		r, g, b = colorInfo.CHAT_RGB_NOTICE
	else:
		r, g, b = colorInfo.TITLE_RGB_EVIL_4
	return ui.GenerateColor(r, g, b)


def ranked(playerList, hasInstance):
	"""The rows OLD shows: the attackers by damage, highest first, those not
	in view left out, at most MAX_ROWS; each (vid, damage, bar percentage of
	the leader, share percentage of the total)."""
	data = sorted(playerList.items(), key=lambda entry: entry[1], reverse=True)
	if not data:
		return []
	total = sum(playerList.values())
	leader = data[0][1]
	rows = []
	for vid, damage in data:
		if len(rows) == MAX_ROWS:
			break
		if not hasInstance(vid):
			continue
		share = float(damage) / float(total) * 100.0 if total and len(data) > 1 else 100.0
		bar = float(damage) / float(leader) * 100.0 if leader else 100.0
		rows.append((vid, damage, bar, share))
	return rows


class DamageCountWindow(ui.ScriptWindow):
	class Row(ui.Bar):
		def __init__(self, x):
			ui.Bar.__init__(self)
			self.x = x
			self.Color = COLOR_LIST[x]
			self.SetSize(300, 60)
			self.LastTimeUpdated = app.GetTime()
			self.SetColor(self.Color)

			self.noNumber = ui.TextLine()
			self.noNumber.SetParent(self)
			self.noNumber.SetWindowVerticalAlignCenter()
			self.noNumber.SetVerticalAlignCenter()
			self.noNumber.SetPosition(10, 0)
			self.noNumber.SetFontName("Tahoma:12b")
			self.noNumber.SetText("")
			self.noNumber.Show()

			# NEW's job faces are 43 x 43: half size fits the 25 px row.
			self.raceImg = ui.ExpandedImageBox()
			self.raceImg.SetParent(self)
			self.raceImg.SetWindowVerticalAlignCenter()
			self.raceImg.SetPosition(25, 0)
			self.raceImg.Show()

			self.NameLabel = ui.TextLine()
			self.NameLabel.SetParent(self)
			self.NameLabel.SetWindowVerticalAlignCenter()
			self.NameLabel.SetVerticalAlignCenter()
			self.NameLabel.SetPosition(55, 0)
			self.NameLabel.SetFontName("Tahoma:12b")
			self.NameLabel.SetText("")
			self.NameLabel.Show()

			self.DamageLabel = ui.TextLine()
			self.DamageLabel.SetParent(self)
			self.DamageLabel.SetWindowVerticalAlignCenter()
			self.DamageLabel.SetVerticalAlignCenter()
			self.DamageLabel.SetPosition(240, 0)
			self.DamageLabel.SetFontName("Tahoma:10b")
			self.DamageLabel.SetText("")
			self.DamageLabel.Show()

			self.leftLine = self.__MakeLine(0, 0, 1, ROW_HEIGHT)
			self.rightLine = self.__MakeLine(MAX_WIDTH - 1, 0, 1, ROW_HEIGHT)
			self.topLine = self.__MakeLine(0, 0, MAX_WIDTH, 1)
			self.bottomLine = self.__MakeLine(0, ROW_HEIGHT - 1, MAX_WIDTH, 1)

			self.Show()

		def __del__(self):
			ui.Bar.__del__(self)

		def __MakeLine(self, x, y, width, height):
			line = ui.Bar()
			line.SetParent(self)
			line.SetPosition(x, y)
			line.SetSize(width, height)
			line.SetColor(OWN_ROW_COLOR)
			line.Hide()
			return line

		def OnUpdate(self):
			if self.Color == UPDATE_COLOR and self.LastTimeUpdated < app.GetTime():
				self.Color = TEXT_COLOR
				self.DamageLabel.SetPackedFontColor(self.Color)

		def SetData(self, no, vid, damage, update=False, perc=100.0):
			name = chr.GetNameByVID(vid)
			self.noNumber.SetText("%d." % no)
			self.NameLabel.SetText(name)

			face = face_of(chr.GetVirtualNumber(vid))
			if face:
				self.raceImg.LoadImage(face)
				self.raceImg.SetScale(FACE_SCALE, FACE_SCALE)
				self.raceImg.Show()
			else:
				self.raceImg.Hide()

			self.DamageLabel.SetText(localeInfo.DAMAGE_COUNT_DAMAGE % (NumberToText(damage), "%2.1f%%" % perc))

			if update:
				self.DamageLabel.SetPackedFontColor(UPDATE_COLOR)
				self.Color = UPDATE_COLOR
				self.LastTimeUpdated = app.GetTime() + FLASH_SECONDS
			elif self.Color == UPDATE_COLOR:
				self.Color = TEXT_COLOR
				self.DamageLabel.SetPackedFontColor(TEXT_COLOR)

			own = name == player.GetName()
			for line in (self.leftLine, self.rightLine, self.topLine, self.bottomLine):
				if own:
					line.Show()
				else:
					line.Hide()

	def __init__(self):
		self.totalDamage = 0
		self.victim = 0
		self.playerList = {}
		self.rowPool = []
		self.activeRows = []
		ui.ScriptWindow.__init__(self)

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def Destroy(self):
		self.Reset()
		self.totalDamage = 0
		self.victim = 0
		self.playerList = {}
		self.rowPool = []
		self.activeRows = []

	def LoadWindow(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/damagecount.py")
		except:
			import exception
			exception.Abort("DamageCountWindow.LoadWindow - LoadScript")

		try:
			getObject = self.GetChild
			self.board = getObject("board")
			self.targetName = getObject("targetName")
			self.wndList = getObject("list")
			self.hpValues = getObject("hp")
			self.hpPercenttxt = getObject("hp_perc")
			self.hpGauge = getObject("gaugeImage")
			getObject("exit").SetEvent(ui.__mem_func__(self.Close))
		except:
			import exception
			exception.Abort("DamageCountWindow.LoadWindow - BindObject")

		self.CreateRowPool()
		self.Reset()

	def CreateRowPool(self):
		for index in range(MAX_ROWS):
			row = self.MakeRow(index)
			row.Hide()
			self.rowPool.append(row)

	def MakeRow(self, index):
		return self.Row(index)

	def GetRowFromPool(self, index):
		if index < len(self.rowPool):
			return self.rowPool[index]
		row = self.MakeRow(index)
		self.rowPool.append(row)
		return row

	def Close(self):
		self.totalDamage = 0
		self.playerList = {}
		self.Reset()
		self.Hide()

	def AddHPInfo(self, vid, hpPercentage, HP=0, MaxHP=0):
		"""The boss's HP (game.SetHPTargetBoard): the percentage in OLD's
		colors and the gauge; "HP / max" when the numbers are known."""
		self.hpPercenttxt.SetText("%d%%" % hpPercentage)
		self.hpPercenttxt.SetPackedFontColor(hp_color(hpPercentage))
		if MaxHP > 0:
			self.hpValues.SetText(localeInfo.NumberToString(max(HP, 0)) + " / " + localeInfo.NumberToString(MaxHP))
		else:
			self.hpValues.SetText("")
		self.hpGauge.SetPercentage(hpPercentage, 100)

	def AddData(self, attackerVID, victimVID, damage):
		if self.victim != victimVID:
			self.victim = victimVID
			self.Reset()
			self.playerList = {}
		self.playerList[attackerVID] = damage
		self.totalDamage = sum(self.playerList.values())
		self.Update(attackerVID)
		self.targetName.SetText(nonplayer.GetMonsterName(chr.GetVirtualNumber(victimVID)))

	def Update(self, vid):
		self.Reset()
		for index, (attacker, damage, bar, share) in enumerate(ranked(self.playerList, chr.HasInstance)):
			row = self.GetRowFromPool(index)
			self.wndList.AppendItem(row)
			item = self.wndList.GetItem(index)
			item.SetSize(int(float(MAX_WIDTH) / 100.0 * bar), ROW_HEIGHT)
			item.SetData(index + 1, attacker, damage, vid == attacker, share)
			item.Show()
			self.activeRows.append(row)

			self.SetSize(self.GetWidth(), self.GetHeight() + ROW_HEIGHT)
			self.board.SetSize(self.board.GetWidth(), self.GetHeight())
			self.wndList.SetSize(self.wndList.GetWidth(), self.wndList.GetHeight() + ROW_HEIGHT)

	def Reset(self):
		for row in self.activeRows:
			row.Hide()
		self.activeRows = []

		self.wndList.RemoveAllItems()
		self.SetSize(self.GetWidth(), BASE_HEIGHT)
		self.board.SetSize(self.board.GetWidth(), self.GetHeight())
		self.wndList.SetSize(self.wndList.GetWidth(), LIST_BASE_HEIGHT)

	def Open(self):
		self.SetPosition((wndMgr.GetScreenWidth() - OPEN_WIDTH) // 2, OPEN_POSITION_Y)
		self.Show()
		self.SetTop()
