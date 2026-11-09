"""The duel rules (NOVA-28 and NOVA-71; OLD __ADVANCED_PVP__, uiTarget.py:36-46 and
148-246, game.py:1435-1446).

The target board's Fight button opens DuelRulesDialog (OLD's AdvancedDuel): the
challenger ticks the rules the duel will hold and presses Fight, which sends
"/pvp <vid> <rules>" (OLD's format); Cancel closes it and sends nothing. The
server whispers the rules to the challenged player as a second system line
"<<~<rules>~>>", which game.py turns into OLD's list (rule_lines). The rules are
OLD's numbers; OLD's tenth, no advanced pet, waits for the advanced pet
(NOVA-24) and is not offered.

OLD drew the board on its own art (ui/advanced_duel/*), not in NEW's packs: the
board is uiscript/duelrulesdialog.py, the check boxes ui.CheckBox made in code at
OLD's two-column order. As OLD's, the board keeps the last rules ticked."""

import net
import ui
import localeInfo

# (rule bit, localeInfo key), OLD's DUEL_FLAGS order (uiTarget.py:36-46).
DUEL_FLAGS = (
	(1 << 0, "DUEL_ANTI_MOUNT"),
	(1 << 1, "DUEL_ANTI_PET"),
	(1 << 2, "DUEL_ANTI_POTION"),
	(1 << 3, "DUEL_ANTI_CRITICAL"),
	(1 << 4, "DUEL_ANTI_PIERCE"),
	(1 << 5, "DUEL_ANTI_POISON"),
	(1 << 6, "DUEL_ANTI_FIRE"),
	(1 << 7, "DUEL_ANTI_CHANGE_EQUIP"),
	(1 << 8, "DUEL_ANTI_PARTY"),
)
# The marker the rules' whisper carries (OLD pvp.cpp:428, game.py:1436).
RULES_OPEN = "<<~"
RULES_CLOSE = "~>>"
# The icon OLD put in front of each rule's whisper line (game.py:1442).
RULE_ICON = "|E~/xmark.tga|e "
# Where rule i's box sits on the board: two columns, OLD's order left to right.
COLUMN_X = (20, 190)
FIRST_ROW_Y = 38
ROW_HEIGHT = 20


def HAS_FLAG(value, flag):
	return (value & flag) == flag


def RULE_POSITION(index):
	return (COLUMN_X[index % 2], FIRST_ROW_Y + (index // 2) * ROW_HEIGHT)


def rule_text(key):
	return getattr(localeInfo, key, key)


def parse_rules_whisper(line):
	"""The rules of a "<<~N~>>" whisper line, or None for any other line."""
	if RULES_OPEN not in line or RULES_CLOSE not in line:
		return None
	number = line.replace(RULES_OPEN, "").replace(RULES_CLOSE, "").strip()
	try:
		return int(number)
	except ValueError:
		return None


def rule_lines(flags):
	"""The whisper lines that say the rules: OLD's title, then one line per rule."""
	lines = [localeInfo.BATTLE_RULES]
	for bit, key in DUEL_FLAGS:
		if HAS_FLAG(flags, bit):
			lines.append(RULE_ICON + rule_text(key))
	return lines


class DuelRulesDialog(ui.ScriptWindow):

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.vid = 0
		self.checkBoxList = []
		self.titleBar = None
		self.acceptButton = None
		self.cancelButton = None
		self.__LoadWindow()

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def __LoadWindow(self):
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "uiscript/duelrulesdialog.py")
		except:
			import exception
			exception.Abort("DuelRulesDialog.LoadWindow.LoadScript")

		try:
			board = self.GetChild("board")
			self.titleBar = self.GetChild("TitleBar")
			self.acceptButton = self.GetChild("accept_button")
			self.cancelButton = self.GetChild("cancel_button")
		except:
			import exception
			exception.Abort("DuelRulesDialog.LoadWindow.BindObject")

		self.titleBar.SetCloseEvent(ui.__mem_func__(self.OnCancelDuel))
		self.acceptButton.SetEvent(ui.__mem_func__(self.OnPressAcceptDuel))
		self.cancelButton.SetEvent(ui.__mem_func__(self.OnCancelDuel))

		self.checkBoxList = []
		for index, (bit, key) in enumerate(DUEL_FLAGS):
			checkBox = ui.CheckBox()
			checkBox.SetParent(board)
			checkBox.SetPosition(*RULE_POSITION(index))
			checkBox.SetTextInfo(rule_text(key))
			checkBox.Show()
			self.checkBoxList.append(checkBox)

	def Destroy(self):
		self.ClearDictionary()
		self.checkBoxList = []
		self.titleBar = None
		self.acceptButton = None
		self.cancelButton = None

	def Open(self, vid):
		self.vid = vid
		self.Show()
		self.SetTop()

	def GetFlags(self):
		value = 0
		for checkBox, (bit, key) in zip(self.checkBoxList, DUEL_FLAGS):
			if checkBox.GetCheckStatus():
				value |= bit
		return value

	def OnPressAcceptDuel(self):
		value = self.GetFlags()
		self.Close()
		net.SendChatPacket("/pvp %d %d" % (self.vid, value))

	def OnCancelDuel(self):
		self.Close()

	def Close(self):
		self.Hide()

	def OnPressEscapeKey(self):
		self.Close()
		return True
