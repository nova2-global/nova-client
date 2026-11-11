import dbg
import ui
import snd
import systemSetting
import net
import chat
import app
import localeInfo
import constInfo
import chrmgr
import player
import musicInfo

import uiSelectMusic
import background
import nui_windows
import player_options

MUSIC_FILENAME_MAX_LEN = 25

blockMode = 0

def field_of_view_place(degrees):
	"""The slider's place (0 to 1) of an angle, over the client's range
	(systemSetting.FIELD_OF_VIEW_MIN to MAX; OLD's (pov - 30) / 90)."""
	low, high = systemSetting.FIELD_OF_VIEW_MIN, systemSetting.FIELD_OF_VIEW_MAX
	return min(1.0, max(0.0, (float(degrees) - low) / (high - low)))


def field_of_view_of_place(place):
	"""The whole degree at a slider's place (OLD's int(30 + pos * 90),
	rounded so a place written by field_of_view_place reads back)."""
	low, high = systemSetting.FIELD_OF_VIEW_MIN, systemSetting.FIELD_OF_VIEW_MAX
	return int(round(low + min(1.0, max(0.0, float(place))) * (high - low)))


class OptionDialog(ui.ScriptWindow):
	# The field of view's row (NOVA-116, uiscript systemoptiondialog.py): the
	# label 2 lower, the slider at x 110.
	FIELD_OF_VIEW_ROW_Y = 210
	# Snowfall, the FPS counter and tips (NOVA-118): OLD's On and Off pairs
	# (uiSystemOption.py:145-154), On at x 110 and Off at 180, each row's
	# uiscript name and its player_options option.
	PLAYER_OPTION_ROW_Y = {"snow": 235, "fps": 260, "tips": 285}
	PLAYER_OPTIONS = (("snow", player_options.SNOWFALL), ("fps", player_options.FPS_COUNTER),
	                  ("tips", player_options.TIPS))

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.__Initialize()
		self.__Load()

	def __del__(self):
		ui.ScriptWindow.__del__(self)
		print(" -------------------------------------- DELETE SYSTEM OPTION DIALOG")

	def __Initialize(self):
		self.tilingMode = 0
		self.titleBar = 0
		self.changeMusicButton = 0
		self.selectMusicFile = 0
		self.ctrlMusicVolume = 0
		self.ctrlSoundVolume = 0
		self.musicListDlg = 0
		self.tilingApplyButton = 0
		self.cameraModeButtonList = []
		self.fogModeButtonList = []
		self.tilingModeButtonList = []
		self.ctrlShadowQuality = 0
		self.ctrlFieldOfView = 0
		self.playerOptionButtons = {}
		
	def Destroy(self):
		self.ClearDictionary()

		self.__Initialize()
		print(" -------------------------------------- DESTROY SYSTEM OPTION DIALOG")

	def __Load_LoadScript(self, fileName):
		try:
			pyScriptLoader = ui.PythonScriptLoader()
			pyScriptLoader.LoadScriptFile(self, fileName)
		except:
			import exception
			exception.Abort("System.OptionDialog.__Load_LoadScript")

	def __Load_BindObject(self):
		try:
			GetObject = self.GetChild
			self.titleBar = GetObject("titlebar")
			self.selectMusicFile = GetObject("bgm_file")
			self.changeMusicButton = GetObject("bgm_button")
			self.ctrlMusicVolume = GetObject("music_volume_controller")
			self.ctrlSoundVolume = GetObject("sound_volume_controller")			
			self.cameraModeButtonList.append(GetObject("camera_short"))
			self.cameraModeButtonList.append(GetObject("camera_long"))
			self.fogModeButtonList.append(GetObject("fog_level0"))
			self.fogModeButtonList.append(GetObject("fog_level1"))
			self.fogModeButtonList.append(GetObject("fog_level2"))
			self.tilingModeButtonList.append(GetObject("tiling_cpu"))
			self.tilingModeButtonList.append(GetObject("tiling_gpu"))
			self.tilingApplyButton=GetObject("tiling_apply")
			self.ctrlFieldOfView = GetObject("fov_controller")
			for name, option in self.PLAYER_OPTIONS:
				self.playerOptionButtons[name] = [GetObject(name + "_on"), GetObject(name + "_off")]
			#self.ctrlShadowQuality = GetObject("shadow_bar")
		except:
			import exception
			exception.Abort("OptionDialog.__Load_BindObject")

	def __Load(self):
		self.__Load_LoadScript("uiscript/systemoptiondialog.py")
		self.__Load_BindObject()

		self.SetCenterPosition()
		
		self.titleBar.SetCloseEvent(ui.__mem_func__(self.Close))

		self.ctrlMusicVolume.SetSliderPos(float(systemSetting.GetMusicVolume()))
		self.ctrlMusicVolume.SetEvent(ui.__mem_func__(self.OnChangeMusicVolume))

		self.ctrlSoundVolume.SetSliderPos(float(systemSetting.GetSoundVolume()))
		self.ctrlSoundVolume.SetEvent(ui.__mem_func__(self.OnChangeSoundVolume))

#		self.ctrlShadowQuality.SetSliderPos(float(systemSetting.GetShadowLevel()) / 5.0)
#		self.ctrlShadowQuality.SetEvent(ui.__mem_func__(self.OnChangeShadowQuality))

		self.ctrlFieldOfView.SetSliderPos(field_of_view_place(systemSetting.GetPOV()))
		self.ctrlFieldOfView.SetEvent(ui.__mem_func__(self.OnChangeFieldOfView))

		self.changeMusicButton.SAFE_SetEvent(self.__OnClickChangeMusicButton)

		self.cameraModeButtonList[0].SAFE_SetEvent(self.__OnClickCameraModeShortButton)
		self.cameraModeButtonList[1].SAFE_SetEvent(self.__OnClickCameraModeLongButton)

		self.fogModeButtonList[0].SAFE_SetEvent(self.__OnClickFogModeLevel0Button)
		self.fogModeButtonList[1].SAFE_SetEvent(self.__OnClickFogModeLevel1Button)
		self.fogModeButtonList[2].SAFE_SetEvent(self.__OnClickFogModeLevel2Button)

		self.tilingModeButtonList[0].SAFE_SetEvent(self.__OnClickTilingModeCPUButton)
		self.tilingModeButtonList[1].SAFE_SetEvent(self.__OnClickTilingModeGPUButton)

		self.tilingApplyButton.SAFE_SetEvent(self.__OnClickTilingApplyButton)

		for name, option in self.PLAYER_OPTIONS:
			buttons = self.playerOptionButtons[name]
			buttons[0].SAFE_SetEvent(self.__OnClickPlayerOption, name, option, True)
			buttons[1].SAFE_SetEvent(self.__OnClickPlayerOption, name, option, False)
			self.__ClickRadioButton(buttons, 0 if player_options.is_on(option) else 1)

		self.__SetCurTilingMode()

		# MR-14: Fog update by Alaric
		self.__ClickRadioButton(self.fogModeButtonList, systemSetting.GetFogLevel())
		# MR-14: -- END OF -- Fog update by Alaric
		self.__ClickRadioButton(self.cameraModeButtonList, constInfo.GET_CAMERA_MAX_DISTANCE_INDEX())

		if musicInfo.fieldMusic==musicInfo.METIN2THEMA:
			self.selectMusicFile.SetText(uiSelectMusic.DEFAULT_THEMA)
		else:
			self.selectMusicFile.SetText(musicInfo.fieldMusic[:MUSIC_FILENAME_MAX_LEN])

	def __OnClickTilingModeCPUButton(self):
		self.__NotifyChatLine(localeInfo.SYSTEM_OPTION_CPU_TILING_1)
		self.__NotifyChatLine(localeInfo.SYSTEM_OPTION_CPU_TILING_2)
		self.__NotifyChatLine(localeInfo.SYSTEM_OPTION_CPU_TILING_3)
		self.__SetTilingMode(0)

	def __OnClickTilingModeGPUButton(self):
		self.__NotifyChatLine(localeInfo.SYSTEM_OPTION_GPU_TILING_1)
		self.__NotifyChatLine(localeInfo.SYSTEM_OPTION_GPU_TILING_2)
		self.__NotifyChatLine(localeInfo.SYSTEM_OPTION_GPU_TILING_3)
		self.__SetTilingMode(1)

	def __OnClickTilingApplyButton(self):
		self.__NotifyChatLine(localeInfo.SYSTEM_OPTION_TILING_EXIT)
		if 0==self.tilingMode:
			background.EnableSoftwareTiling(1)
		else:
			background.EnableSoftwareTiling(0)

		net.ExitGame()

	def __OnClickChangeMusicButton(self):
		if not self.musicListDlg:
			
			self.musicListDlg=uiSelectMusic.FileListDialog()
			self.musicListDlg.SAFE_SetSelectEvent(self.__OnChangeMusic)

		self.musicListDlg.Open()

		
	def __ClickRadioButton(self, buttonList, buttonIndex):
		try:
			selButton=buttonList[buttonIndex]
		except IndexError:
			return

		for eachButton in buttonList:
			eachButton.SetUp()

		selButton.Down()


	def __SetTilingMode(self, index):
		self.__ClickRadioButton(self.tilingModeButtonList, index)
		self.tilingMode=index

	def __SetCameraMode(self, index):
		constInfo.SET_CAMERA_MAX_DISTANCE_INDEX(index)
		self.__ClickRadioButton(self.cameraModeButtonList, index)

	def __SetFogLevel(self, index):
		# MR-14: Fog update by Alaric
		# constInfo.SET_FOG_LEVEL_INDEX(index)
		systemSetting.SetFogLevel(index)
		# MR-14: -- END OF -- Fog update by Alaric

		self.__ClickRadioButton(self.fogModeButtonList, index)

	def __OnClickCameraModeShortButton(self):
		self.__SetCameraMode(0)

	def __OnClickCameraModeLongButton(self):
		self.__SetCameraMode(1)

	def __OnClickFogModeLevel0Button(self):
		self.__SetFogLevel(0)

	def __OnClickFogModeLevel1Button(self):
		self.__SetFogLevel(1)

	def __OnClickFogModeLevel2Button(self):
		self.__SetFogLevel(2)

	def __OnChangeMusic(self, fileName):
		self.selectMusicFile.SetText(fileName[:MUSIC_FILENAME_MAX_LEN])

		if musicInfo.fieldMusic != "":
			snd.FadeOutMusic("BGM/" + musicInfo.fieldMusic)

		if fileName==uiSelectMusic.DEFAULT_THEMA:
			musicInfo.fieldMusic=musicInfo.METIN2THEMA
		else:
			musicInfo.fieldMusic=fileName

		musicInfo.SaveLastPlayFieldMusic()
		
		if musicInfo.fieldMusic != "":
			snd.FadeInMusic("BGM/" + musicInfo.fieldMusic)

	def OnChangeMusicVolume(self):
		pos = self.ctrlMusicVolume.GetSliderPos()
		snd.SetMusicVolume(pos)
		systemSetting.SetMusicVolume(pos)

	def OnChangeSoundVolume(self):
		pos = self.ctrlSoundVolume.GetSliderPos()
		snd.SetSoundVolume(pos)
		systemSetting.SetSoundVolume(pos)

	def OnChangeFieldOfView(self):
		systemSetting.SetPOV(float(field_of_view_of_place(self.ctrlFieldOfView.GetSliderPos())))

	# NOVA-118: saved at exit with the other options (OLD saved at each press).
	def __OnClickPlayerOption(self, name, option, on):
		player_options.set_option(option, on)
		self.__ClickRadioButton(self.playerOptionButtons[name], 0 if on else 1)

	def OnChangeShadowQuality(self):
		pos = self.ctrlShadowQuality.GetSliderPos()
		systemSetting.SetShadowLevel(int(pos / 0.2))

	def OnCloseInputDialog(self):
		self.inputDialog.Close()
		self.inputDialog = None
		return True

	def OnCloseQuestionDialog(self):
		self.questionDialog.Close()
		self.questionDialog = None
		return True

	def OnPressEscapeKey(self):
		self.Close()
		return True
	
	def Show(self):
		ui.ScriptWindow.Show(self)

	def Close(self):
		self.__SetCurTilingMode()
		self.Hide()

	def __SetCurTilingMode(self):
		if background.IsSoftwareTiling():
			self.__SetTilingMode(0)
		else:
			self.__SetTilingMode(1)	

	def __NotifyChatLine(self, text):
		chat.AppendChat(chat.CHAT_TYPE_INFO, text)
		

# The system menu (legacy or NovaUI) makes this window by this name: with the
# system-options flag on, the NovaUI facade (P11 spec 6.8).
LegacyOptionDialog = OptionDialog
OptionDialog = nui_windows.factory("system-options", LegacyOptionDialog, "nui_system_options.OptionDialog")
