"""The select skill window (NOVA-37; OLD uiSelectSkill.py): while the skill group is 0, the
letter of the skill_group quest opens it through the server command OpenSelectSkillWindow. It
shows the two skill groups, each a row of six skills, a preview of the character turning in a
render target, and the buttons that pick a group with /select_skill.

Hovering a skill plays its motion on the preview: motion NAME_SKILL + n, n being 1 to 6 or 16 to
21 from the warrior's row for every job (OLD's SKILL_INDEX_DICT[0]), since n is a motion slot and
not a skill vnum. The dressed model is made only when its gear changes (a hover keeps it) and the
camera stands at OLD's (0, -1200, 600). While no skill is hovered, the preview casts the job's
skills of both groups at random, one after another, each in its row's gear (Eddy; OLD only looped
the wait): modelpreview.SetSkillCycle, run by the client each frame, so no Python runs per frame.
The skills' effects draw inside the preview only. Without a client's modelpreview module or render
targets, the window shows no preview; a client without SetSkillCycle shows the wait. A server can refuse the pick (the group is no longer 0): a
window that picked closes either way."""

import item
import localeInfo
import mouseModule
import net
import player
import ui

BOARD_WIDTH = 250
BOARD_HEIGHT = 400
MAX_SKILL_NUM = 6
PREVIEW = "select_skill"
PREVIEW_EYE = (-1200, 600)
PREVIEW_VIEW_RECT = (20, 225, 225, 150)

# OLD's SKILL_INDEX_DICT by job (uiSelectSkill.py:25-50, the wolfman's row left out): the
# skill vnums of the two groups, then the body and weapon the preview wears for each.
SKILL_INDEX_DICT = {
	0 : {
		1 : (1, 2, 3, 4, 5, 6,),
		2 : (16, 17, 18, 19, 20, 21,),
		3 : (11289, 189),
		4 : (11289, 189),
	},
	1 : {
		1 : (31, 32, 33, 34, 35, 36,),
		2 : (46, 47, 48, 49, 50, 51,),
		3 : (41003, 40102),
		4 : (41003, 40103),
	},
	2 : {
		1 : (61, 62, 63, 64, 65, 66,),
		2 : (76, 77, 78, 79, 80, 81,),
		3 : (41003, 40101),
		4 : (41003, 40101),
	},
	3 : {
		1 : (91, 92, 93, 94, 95, 96,),
		2 : (106, 107, 108, 109, 110, 111,),
		3 : (41003, 40105),
		4 : (41003, 40105),
	},
}

def skill_group_names(job):
	"""The buttons' two names, localeInfo's as uicharacter's table."""
	return {
		0 : (localeInfo.SKILL_GROUP_WARRIOR_1, localeInfo.SKILL_GROUP_WARRIOR_2),
		1 : (localeInfo.SKILL_GROUP_ASSASSIN_1, localeInfo.SKILL_GROUP_ASSASSIN_2),
		2 : (localeInfo.SKILL_GROUP_SURA_1, localeInfo.SKILL_GROUP_SURA_2),
		3 : (localeInfo.SKILL_GROUP_SHAMAN_1, localeInfo.SKILL_GROUP_SHAMAN_2),
	}[job]

def model_preview():
	"""The client's modelpreview module (NOVA-137), None on a client without render targets."""
	try:
		import modelpreview
	except ImportError:
		return None
	return modelpreview

def hair_part():
	"""The hair costume's part value (item value 3); no costume is 0 (OLD read the value of
	whichever item was selected last)."""
	vnum = player.GetItemIndex(item.COSTUME_SLOT_HAIR)
	if not vnum:
		return 0
	item.SelectItem(vnum)
	return item.GetValue(3)

def sash_part():
	"""The sash costume's part value, 0 without one (OLD's vnum - 85000 went negative)."""
	return player.GetItemIndex(item.COSTUME_SLOT_SASH)

class SelectSkillWindow(ui.ScriptWindow):

	# Class-level: ui.Window.__init__ calls Hide before __init__ has set these.
	previewGear = None
	previewView = None
	previewShown = False

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.toolTipSkill = None
		self.previewView = None
		self.previewGear = None

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def LoadWindow(self):
		self._LoadScript()
		self.Button1.SetEvent(ui.__mem_func__(self.OnSelectSkill), 1)
		self.Button2.SetEvent(ui.__mem_func__(self.OnSelectSkill), 2)

	def _LoadScript(self):
		"""The uiscript's widgets (NovaUI puts proxies here instead)."""
		try:
			pyScrLoader = ui.PythonScriptLoader()
			pyScrLoader.LoadScriptFile(self, "UIScript/selectskillwindow.py")
		except:
			import exception
			exception.Abort("SelectSkillWindow.LoadWindow.LoadObject")
		try:
			self.GetChild("TitleBar").SetCloseEvent(ui.__mem_func__(self.Close))
			self.Button1 = self.GetChild("1stButton")
			self.Button2 = self.GetChild("2ndButton")
			self.SkillGroup1 = self.GetChild("Skill_group_1")
			self.SkillGroup2 = self.GetChild("Skill_group_2")
		except:
			import exception
			exception.Abort("SelectSkillWindow.LoadWindow.BindObject")
		self.previewView = self._MakePreviewView()

	def _MakePreviewView(self):
		"""OLD's render_target at 20, 225 (225 x 150); None on a client without render targets."""
		if model_preview() is None or not hasattr(ui, "RenderTarget") or not ui.RenderTarget.IsAvailable():
			return None
		view = ui.RenderTarget()
		view.SetParent(self.GetChild("Board"))
		view.AddFlag("not_pick")
		(x, y, width, height) = PREVIEW_VIEW_RECT
		view.SetPosition(x, y)
		view.SetSize(width, height)
		view.SetRenderTarget(PREVIEW)
		return view

	def SetSkillToolTip(self, toolTipSkill):
		self.toolTipSkill = toolTipSkill

	def Open(self):
		if not self.IsShow():
			self.__StartCycle()
		self.__ApplyPreview()
		if self.IsShow():
			return
		job = player.GetJob()
		names = skill_group_names(job)
		self.Button1.SetText(names[0])
		self.Button2.SetText(names[1])
		self.__FillSkills(self.SkillGroup1, SKILL_INDEX_DICT[job][1], ui.__mem_func__(self.OverInItem1))
		self.__FillSkills(self.SkillGroup2, SKILL_INDEX_DICT[job][2], ui.__mem_func__(self.OverInItem2))
		if self.previewView:
			self.previewView.Show()
		self.Show()
		self.SetTop()

	def __FillSkills(self, slots, skills, overIn):
		for num in range(MAX_SKILL_NUM):
			slots.SetSkillSlotNew(num, skills[num], 0, 0)
			slots.SetSlotCount(num, 0)
		slots.SetOverInItemEvent(overIn)
		slots.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		slots.RefreshSlot()

	def OverInItem1(self, slotNumber):
		self.__OverInItem(1, slotNumber)

	def OverInItem2(self, slotNumber):
		self.__OverInItem(2, slotNumber)

	def __OverInItem(self, group, slotNumber):
		if mouseModule.mouseController.isAttached():
			return
		if not self.toolTipSkill:
			return
		self.toolTipSkill.SetSkillOnlyName(slotNumber, SKILL_INDEX_DICT[player.GetJob()][group][slotNumber], 0)
		self.__ApplyPreview(SKILL_INDEX_DICT[0][group][slotNumber])

	def OverOutItem(self):
		self.__ApplyPreview()
		if self.toolTipSkill:
			self.toolTipSkill.HideToolTip()

	def __StartCycle(self):
		"""The idle casting: every skill of both groups, each in its row's gear."""
		preview = model_preview()
		set_cycle = getattr(preview, "SetSkillCycle", None) if preview is not None else None
		if set_cycle is None:
			return
		gear = SKILL_INDEX_DICT[player.GetJob()]
		entries = []
		for group, row in ((1, 3), (2, 4)):
			body, weapon = gear[row]
			entries.extend((motion, body, weapon) for motion in SKILL_INDEX_DICT[0][group])
		set_cycle(PREVIEW, entries)

	def __ApplyPreview(self, motion = 0):
		"""OLD's setRenderTarget: the row of gear follows the motion (1 to 6 the first group's
		row); the model is made again only when its gear changes."""
		preview = model_preview()
		if preview is None:
			return
		row = 3 if motion <= 6 else 4
		body, weapon = SKILL_INDEX_DICT[player.GetJob()][row]
		gear = (player.GetRace(), body, weapon, hair_part(), sash_part())
		if gear != self.previewGear:
			preview.Select(PREVIEW, *gear)
			preview.SetEye(PREVIEW, PREVIEW_EYE[0], PREVIEW_EYE[1])
			self.previewGear = gear
		preview.SetSkillMotion(PREVIEW, motion)
		preview.Show(PREVIEW, True)
		self.previewShown = True

	def __StopPreview(self):
		if not self.previewShown:
			return
		self.previewShown = False
		preview = model_preview()
		if preview is not None:
			preview.Show(PREVIEW, False)
		if self.previewView:
			self.previewView.Hide()

	def Close(self):
		self.__StopPreview()
		if self.toolTipSkill:
			self.toolTipSkill.HideToolTip()
		self.Hide()

	def Destroy(self):
		self.__StopPreview()
		preview = model_preview()
		if preview is not None:
			preview.Clear(PREVIEW)
		self.previewView = None
		self.toolTipSkill = None
		self.ClearDictionary()
		self.Button1 = None
		self.Button2 = None
		self.SkillGroup1 = None
		self.SkillGroup2 = None

	def OnSelectSkill(self, group):
		net.SendChatPacket("/select_skill %d" % group)
		self.Close()

	def OnPressEscapeKey(self):
		self.Close()
		return True
