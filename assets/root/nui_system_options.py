"""NovaUI system options (nui/windows/system-options/system-options.rml) and
its music list (nui/windows/music-list/music-list.rml).

While the "system-options" window flag is on, uiSystemOption.OptionDialog
(a factory, nui_windows.factory) makes OptionDialog below instead of the
legacy class, for whichever system menu runs (P11 spec D7). It is the
facade of the legacy window with its name, constructor and methods; its
document exists only while it shows (nui_hud.OnDemand), and each show fills
the model from the getters, as legacy's controls show the settings.

Every legacy control makes legacy's calls, in legacy's order
(uisystemoption.py): the sliders snd.Set*Volume and systemSetting.Set*Volume
(saved at exit), the camera constInfo.SET_CAMERA_MAX_DISTANCE_INDEX (module
state), the fog systemSetting.SetFogLevel, the tiling choices three info
lines each and Apply its line, background.EnableSoftwareTiling and
net.ExitGame; Close puts the tiling choice back to the one in effect. The
Interface section is new: the theme (nui.set_theme), the UI scale (a row of
choices, D12: auto, 75 to 200 percent, and a saved percent outside them as
one more choice; nui.set_scale_percent), reduced motion
(nui.set_reduced_motion), reduced effects (nui.set_reduced_effects; on and
locked while the device draws no effects) and the player colors of the theme
in use (P13 spec 5.6: its color slots' swatches, the accent's hue slider,
the panel and overlay opacity choices, a reset and a preview; nui.set_color,
nui.reset_colors), each applied at once and saved by nui.py. The colors rows
show only for a theme that offers slots (not classic).

A slider's or the toggle's change event also arrives when the model moves
the control (each show); a value equal to the model's is that echo and does
nothing, so opening the window writes no setting. The toggle itself acts on
a left mousedown: RmlUi makes no click in a document that takes no focus,
so its label cannot flip the checkbox. Escape closes the window
in its legacy place (nui_hud.EscapeProxy). A window the player moved keeps
its place across a hide, as legacy's one window does; a scale change
centers it again.

FileListDialog is uiSelectMusic.FileListDialog on NovaUI, made by the
options on first use, as legacy's: the default theme first, then every
BGM/*.mp3 file; OK hands the selected name to the options' select event,
and its popups are uiCommon.PopupDialog (the dialog kit's facade with the
dialogs flag on, the legacy one with the G5 stopgap otherwise) instead of
legacy's private copy."""

import colorsys

import app
import background
import chat
import constInfo
import dbg
import localeInfo
import musicInfo
import net
import snd
import systemSetting

import nui
import nui_hud
import nui_music_list
import nui_theme_picker

DOCUMENT = "nui/windows/system-options/system-options.rml"
MUSIC_FILENAME_MAX_LEN = 25   # uisystemoption.py:17
FILE_NAME_LEN = 20            # uiselectmusic.py:6
SCALE_CHOICES = (75, 100, 125, 150, 175, 200)
PERCENT_CHOICES = {
	"opacity": (100, 90, 80, 70, 60),
	"overlay": (100, 75, 51, 40, 30),
}   # rows of choices, not sliders: no repaint storm under a drag


def _plain(text):
	return nui.plain_text(text)


class OptionBoard(nui.Window):
	"""The system options' document and model; its events go to its facade."""

	DOCUMENT = DOCUMENT
	MODEL = "system_options"

	def __init__(self, owner):
		self._owner = nui_hud.keep_weakly(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		model = getattr(self._owner, "nui_model", None)
		if model is not None:
			return model()
		return OptionDialog.empty_model()

	def on_theme_changed(self, theme_id):
		self._owner.on_theme_changed(theme_id)

	def on_scale_changed(self, scale):
		self._owner.on_scale_changed(scale)

	def on_colors_changed(self, slot):
		self._owner.on_colors_changed(slot)

	@nui.on("act")
	def on_act(self, what, button):
		if button == 0:
			self._owner.nui_act(what)

	@nui.on("choose")
	def on_choose(self, what, index, button):
		if button == 0:
			self._owner.nui_choose(what, index)

	@nui.on("sound")
	def on_sound(self, value):
		self._owner.nui_volume("sound_volume", value)

	@nui.on("music")
	def on_music(self, value):
		self._owner.nui_volume("music_volume", value)

	@nui.on("choose_theme")
	def on_choose_theme(self, theme_id, button):
		if button == 0:
			self._owner.nui_choose_theme(theme_id)

	@nui.on("choose_scale")
	def on_choose_scale(self, percent, button):
		if button == 0:
			self._owner.nui_choose_scale(percent)

	@nui.on("motion")
	def on_motion(self, checked):
		self._owner.nui_motion(checked)

	@nui.on("flip_motion")
	def on_flip_motion(self, button):
		if button == 0:
			self._owner.nui_flip_motion()

	@nui.on("effects")
	def on_effects(self, checked):
		self._owner.nui_effects(checked)

	@nui.on("flip_effects")
	def on_flip_effects(self, button):
		if button == 0:
			self._owner.nui_flip_effects()

	@nui.on("pick_color")
	def on_pick_color(self, slot, value, button):
		if button == 0:
			self._owner.nui_pick_color(slot, value)

	@nui.on("hue")
	def on_hue(self, value):
		self._owner.nui_hue(value)

	@nui.on("hue_done")
	def on_hue_done(self):
		self._owner.nui_hue_done()

	@nui.on("reset_colors")
	def on_reset_colors(self, button):
		if button == 0:
			self._owner.nui_reset_colors()


class OptionDialog(nui_hud.LayoutCalls):
	"""uiSystemOption.OptionDialog on NovaUI (SystemDialog.systemOptionDlg)."""

	NUI_FACADE = True
	KEY = "system-options"

	def __init__(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self.tilingMode = 0
		self.musicListDlg = 0
		self.musicFileText = None   # the text a music change set, until the next show reads musicInfo
		self.place = None
		self.demand = None
		self.escapeProxy = None
		self.loaded = False
		self.colorsAdjusted = False   # the last color the player set made the resolve adjust a token
		self.colorsUnsaved = False    # the hue slider's drag applied colors it has not saved yet
		self.__SetCurTilingMode()
		if not nui_hud.has_engine():
			return
		try:
			self.demand = nui_hud.OnDemand(self._make_board, self._restore_board, self._keep_board)
			self.loaded = self.demand.probe() and FileListDialog.probe()
			self.escapeProxy = nui_hud.EscapeProxy(self.OnPressEscapeKey)
		except Exception:
			self.nui_discard()
			raise

	# --- the make() protocol ------------------------------------------------------

	def nui_ready(self):
		return self.loaded and self.demand is not None and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		dialog, self.musicListDlg = self.musicListDlg, 0
		if dialog:
			dialog.Destroy()
		proxy, self.escapeProxy = self.escapeProxy, None
		if proxy is not None:
			proxy.destroy()
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(self.KEY, self)

	# --- the model ----------------------------------------------------------------

	@staticmethod
	def empty_model():
		return {"sound_volume": 0, "music_volume": 0, "music_file": "", "camera": 0, "fog": 0, "tiling": 0,
		        "interface": True, "themes": [], "theme": "", "scales": [], "scale": 0, "auto_percent": 100,
		        "reduced_motion": False, "reduced_effects": False, "effects_available": False,
		        "color_slots": [], "accent_hue": 0, "colors_adjusted": False}

	def _music_file(self):
		"""uisystemoption.py:119-122."""
		if musicInfo.fieldMusic == musicInfo.METIN2THEMA:
			return nui_hud.locale_text("MUSIC_METIN2_DEFAULT_THEMA")
		return _plain(musicInfo.fieldMusic[:MUSIC_FILENAME_MAX_LEN])

	@staticmethod
	def scale_choices(saved):
		"""Auto, 75 to 200 percent, and a saved percent outside them (a
		hand-edited 110) as one more choice (D12)."""
		choices = [{"id": "auto", "percent": 0, "label": "@ui.OPTION_UI_SCALE_AUTO"}]
		choices += [{"id": str(p), "percent": p, "label": "%d%%" % p} for p in SCALE_CHOICES]
		if saved and saved not in SCALE_CHOICES:
			choices.append({"id": "custom", "percent": saved, "label": "%d%%" % saved})
		return choices

	def _interface_model(self):
		saved = nui.get_scale_percent()
		return {"themes": [{"id": theme_id, "label": nui_theme_picker.theme_label(theme_id, label)}
		                   for theme_id, label in nui.get_themes()],
		        "theme": nui.get_theme(), "scales": self.scale_choices(saved), "scale": saved,
		        "auto_percent": int(round(nui.get_auto_scale() * 100)), "reduced_motion": bool(nui.is_reduced_motion()),
		        "reduced_effects": bool(nui.is_reduced_effects()), "effects_available": bool(nui.effects_available())}

	@staticmethod
	def color_rows(slots):
		"""The theme's color slots (nui.get_color_slots) as the Interface rows
		show them: a color slot's swatches (the default first, as the palette
		lists them), a percent slot's curated choices within its
		range), the label as a locale key, the value in use as text."""
		rows = []
		for slot in slots:
			row = {"slot": str(slot["slot"]), "kind": str(slot["kind"]),
			       "label": "@ui." + slot["label"] if slot.get("label") else str(slot["slot"]),
			       "value": str(slot["value"]), "swatches": [], "choices": []}
			if slot["kind"] == "color":
				row["swatches"] = [{"index": i, "color": str(color)} for i, color in enumerate(slot.get("swatches", ()))]
			else:
				choices = PERCENT_CHOICES.get(str(slot["slot"]), ())
				row["choices"] = [{"value": str(p)} for p in choices if int(slot["min"]) <= p <= int(slot["max"])]
			rows.append(row)
		return rows

	@staticmethod
	def hue_of(color):
		"""The hue in degrees (0 to 359) of a #rrggbb color."""
		r, g, b = (int(color[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
		return int(round(colorsys.rgb_to_hsv(r, g, b)[0] * 360)) % 360

	@staticmethod
	def color_of_hue(hue, default):
		"""#rrggbb at `hue` degrees with the saturation and value of `default`
		(the palette's own accent), so a custom accent keeps its brightness."""
		r, g, b = (int(default[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
		_, s, v = colorsys.rgb_to_hsv(r, g, b)
		r, g, b = colorsys.hsv_to_rgb((int(hue) % 360) / 360.0, s, v)
		return "#%02x%02x%02x" % tuple(int(round(c * 255)) for c in (r, g, b))

	def _colors_model(self):
		slots = nui.get_color_slots()
		accent = next((slot for slot in slots if slot["slot"] == "accent"), None)
		return {"color_slots": self.color_rows(slots), "colors_adjusted": self.colorsAdjusted,
		        "accent_hue": self.hue_of(str(accent["value"])) if accent else 0}

	def nui_model(self):
		"""Every key from the getters, as legacy's controls show them."""
		model = {"sound_volume": int(round(systemSetting.GetSoundVolume() * 100)),
		         "music_volume": int(round(systemSetting.GetMusicVolume() * 100)),
		         "music_file": self._music_file() if self.musicFileText is None else self.musicFileText,
		         "camera": constInfo.GET_CAMERA_MAX_DISTANCE_INDEX(), "fog": systemSetting.GetFogLevel(),
		         "tiling": self.tilingMode, "interface": True}
		model.update(self._interface_model())
		model.update(self._colors_model())
		return model

	def _board(self):
		return self.demand.board() if self.demand is not None else None

	def _set(self, **values):
		board = self._board()
		if board is not None:
			board.set(**values)

	def _make_board(self):
		return OptionBoard(self)

	def _restore_board(self, board):
		self.musicFileText = None
		board.set(**self.nui_model())
		if self.place is not None:
			board.set_position(*self.place)
		else:
			board.center()

	def _keep_board(self, board):
		self.place = nui_hud.moved_place(board)

	# --- the system menu's calls -------------------------------------------------------

	def Destroy(self):
		self.nui_discard()

	def Show(self):
		if self.demand is not None and self.demand.show():
			if self.escapeProxy is not None:
				self.escapeProxy.show()

	def Hide(self):
		self.nui_hue_done()
		if self.escapeProxy is not None:
			self.escapeProxy.hide()
		if self.demand is not None:
			self.demand.hide()

	def IsShow(self):
		return self.demand is not None and self.demand.is_shown()

	def SetTop(self):
		board = self._board()
		if board is not None:
			board.bring_to_front()
		if self.escapeProxy is not None and self.escapeProxy.is_shown():
			self.escapeProxy.show()

	def Close(self):
		"""uisystemoption.py:244-246."""
		self.__SetCurTilingMode()
		self.Hide()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def __SetCurTilingMode(self):
		self.__SetTilingMode(0 if background.IsSoftwareTiling() else 1)

	def __SetTilingMode(self, index):
		self.tilingMode = index
		self._set(tiling=index)

	def __NotifyChatLine(self, text):
		chat.AppendChat(chat.CHAT_TYPE_INFO, text)

	# Legacy's slider events (uisystemoption.py:213-221), for callers and the
	# facade check: the board's value, as legacy reads its slider's.
	def OnChangeMusicVolume(self):
		board = self._board()
		if board is not None:
			self._apply_volume("music_volume", board.get("music_volume") / 100.0)

	def OnChangeSoundVolume(self):
		board = self._board()
		if board is not None:
			self._apply_volume("sound_volume", board.get("sound_volume") / 100.0)

	# Dead in legacy (the shadow slider is commented out, no dialog is made,
	# uisystemoption.py:223-235); kept for the facade check.
	def OnChangeShadowQuality(self):
		pass

	def OnCloseInputDialog(self):
		return True

	def OnCloseQuestionDialog(self):
		return True

	# --- the board's events ---------------------------------------------------------------

	def _apply_volume(self, key, pos):
		if key == "sound_volume":
			snd.SetSoundVolume(pos)
			systemSetting.SetSoundVolume(pos)
		else:
			snd.SetMusicVolume(pos)
			systemSetting.SetMusicVolume(pos)

	def nui_volume(self, key, value):
		"""A slider moved: legacy's calls with the slider's place (0 to 1). The
		model's own value coming back (each show moves the slider) is not a
		move."""
		try:
			percent = float(value)
		except (TypeError, ValueError):
			return
		board = self._board()
		if board is None or abs(percent - float(board.get(key) or 0)) < 0.5:
			return
		board.set(**{key: int(round(percent))})
		self._apply_volume(key, percent / 100.0)

	def nui_act(self, what):
		if what == "close":
			self.Close()
		elif what == "change_music":
			self.__OnClickChangeMusicButton()
		elif what == "tiling_apply":
			self.__OnClickTilingApplyButton()

	def _in_effect(self, what):
		"""The choice a legacy row shows selected, as nui_model fills it."""
		if what == "camera":
			return constInfo.GET_CAMERA_MAX_DISTANCE_INDEX()
		if what == "fog":
			return systemSetting.GetFogLevel()
		if what == "tiling":
			return self.tilingMode
		return None

	def nui_choose(self, what, index):
		# Legacy's radio buttons ignore a press on the one that is down
		# (CRadioButton::OnMouseLeftButtonDown): no call and no info lines.
		if index == self._in_effect(what):
			return
		if what == "camera" and index in (0, 1):
			constInfo.SET_CAMERA_MAX_DISTANCE_INDEX(index)
			self._set(camera=index)
		elif what == "fog" and index in (0, 1, 2):
			systemSetting.SetFogLevel(index)
			self._set(fog=index)
		elif what == "tiling" and index == 0:
			self.__NotifyChatLine(localeInfo.SYSTEM_OPTION_CPU_TILING_1)
			self.__NotifyChatLine(localeInfo.SYSTEM_OPTION_CPU_TILING_2)
			self.__NotifyChatLine(localeInfo.SYSTEM_OPTION_CPU_TILING_3)
			self.__SetTilingMode(0)
		elif what == "tiling" and index == 1:
			self.__NotifyChatLine(localeInfo.SYSTEM_OPTION_GPU_TILING_1)
			self.__NotifyChatLine(localeInfo.SYSTEM_OPTION_GPU_TILING_2)
			self.__NotifyChatLine(localeInfo.SYSTEM_OPTION_GPU_TILING_3)
			self.__SetTilingMode(1)

	def __OnClickTilingApplyButton(self):
		"""uisystemoption.py:136-143."""
		self.__NotifyChatLine(localeInfo.SYSTEM_OPTION_TILING_EXIT)
		if 0 == self.tilingMode:
			background.EnableSoftwareTiling(1)
		else:
			background.EnableSoftwareTiling(0)
		net.ExitGame()

	def __OnClickChangeMusicButton(self):
		"""uisystemoption.py:145-151."""
		if not self.musicListDlg:
			self.musicListDlg = FileListDialog()
			self.musicListDlg.SAFE_SetSelectEvent(self.__OnChangeMusic)
		self.musicListDlg.Open()

	def __OnChangeMusic(self, fileName):
		"""uisystemoption.py:197-211."""
		self.musicFileText = _plain(fileName[:MUSIC_FILENAME_MAX_LEN])
		self._set(music_file=self.musicFileText)
		if musicInfo.fieldMusic != "":
			snd.FadeOutMusic("BGM/" + musicInfo.fieldMusic)
		if fileName == localeInfo.MUSIC_METIN2_DEFAULT_THEMA:
			musicInfo.fieldMusic = musicInfo.METIN2THEMA
		else:
			musicInfo.fieldMusic = fileName
		musicInfo.SaveLastPlayFieldMusic()
		if musicInfo.fieldMusic != "":
			snd.FadeInMusic("BGM/" + musicInfo.fieldMusic)

	# --- the Interface section (new) ----------------------------------------------------------

	def nui_choose_theme(self, theme_id):
		"""Applies and saves the theme; nui.set_theme calls on_theme_changed."""
		try:
			nui.set_theme(theme_id)
		except ValueError as error:
			dbg.TraceError("nui_system_options: %s" % error)

	def nui_choose_scale(self, percent):
		"""Applies and saves the scale (0 is automatic); nui.set_scale_percent
		calls on_scale_changed."""
		try:
			nui.set_scale_percent(int(percent))
		except (TypeError, ValueError) as error:
			dbg.TraceError("nui_system_options: %s" % error)

	def nui_motion(self, checked):
		"""The toggle moved: applies and saves reduced motion. The model's own
		value coming back is not a move."""
		board = self._board()
		checked = bool(checked)
		if board is None or checked == bool(board.get("reduced_motion")):
			return
		board.set(reduced_motion=checked)
		nui.set_reduced_motion(checked)

	def nui_flip_motion(self):
		"""A left press on the toggle flips reduced motion. RmlUi clicks only a
		focusable element, and this document takes no focus (D11), so the
		toggle's label never forwards a click to its checkbox; the checkbox
		then follows the model, and its change event is the echo."""
		board = self._board()
		if board is not None:
			self.nui_motion(not bool(board.get("reduced_motion")))

	def nui_effects(self, checked):
		"""The toggle moved: applies and saves reduced effects. The model's own
		value coming back is not a move; nothing changes while the device
		draws no effects (the toggle shows on and is disabled)."""
		board = self._board()
		checked = bool(checked)
		if board is None or not board.get("effects_available") or checked == bool(board.get("reduced_effects")):
			return
		board.set(reduced_effects=checked)
		nui.set_reduced_effects(checked)

	def nui_flip_effects(self):
		"""A left press on the toggle flips reduced effects (as nui_flip_motion)."""
		board = self._board()
		if board is not None:
			self.nui_effects(not bool(board.get("reduced_effects")))

	def nui_pick_color(self, slot, value, save=True):
		"""A swatch or an opacity choice: sets the slot of the theme in use;
		nui.set_color saves it (unless `save` is False: the hue slider's drag)
		and calls on_colors_changed. The note shows while the resolve had to
		adjust a color to keep text readable."""
		try:
			result = nui.set_color(str(slot), str(value), save=save)
		except ValueError as error:
			dbg.TraceError("nui_system_options: %s" % error)
			return
		self.colorsAdjusted = bool(result.get("adjusted"))
		self._set(colors_adjusted=self.colorsAdjusted)

	def nui_hue(self, value):
		"""The accent's hue slider moved: a color of that hue with the default
		accent's saturation and value, applied at once but not saved: the
		slider sends a change on every step of a drag, and each save rewrites
		the config file. The drag's end (nui_hue_done) or the window's Hide
		saves it. The model's own value coming back is not a move."""
		board = self._board()
		try:
			hue = int(round(float(value)))
		except (TypeError, ValueError):
			return
		if board is None or hue == board.get("accent_hue"):
			return
		accent = next((slot for slot in nui.get_color_slots() if slot["slot"] == "accent"), None)
		if accent is None:
			return
		board.set(accent_hue=hue)
		self.nui_pick_color("accent", self.color_of_hue(hue, str(accent["default"])), save=False)
		self.colorsUnsaved = True

	def nui_hue_done(self):
		"""The hue slider let go (its dragend, or the mouseup of a press on
		the bar): the colors the drag applied are saved once."""
		if self.colorsUnsaved:
			self.colorsUnsaved = False
			nui.save_colors()

	def nui_reset_colors(self):
		"""Reset: the theme in use's palette colors again (nui.reset_colors
		saves and calls on_colors_changed)."""
		self.colorsAdjusted = False
		nui.reset_colors()

	def on_colors_changed(self, slot):
		self._set(**self._colors_model())

	def on_theme_changed(self, theme_id):
		"""The theme's color slots replace the old theme's (none in classic)."""
		self.colorsAdjusted = False
		self._set(theme=nui.get_theme(), **self._colors_model())

	def on_scale_changed(self, scale):
		"""The window's size follows the scale: it is centered again, and the
		choices show the saved percent (a custom one may have gone)."""
		self.place = None
		saved = nui.get_scale_percent()
		self._set(scales=self.scale_choices(saved), scale=saved, auto_percent=int(round(nui.get_auto_scale() * 100)))
		board = self._board()
		if board is not None:
			board.center()


class FileListDialog(nui_hud.LayoutCalls):
	"""uiSelectMusic.FileListDialog on NovaUI (OptionDialog.musicListDlg)."""

	NUI_FACADE = True
	KEY = "music-list"

	def __init__(self):
		nui_hud.take_over(self.KEY, self)
		self._nui_discarded = False
		self.isLoaded = 0
		self.selectEvent = None
		self.files = []          # the names legacy's items keep (Item.GetText)
		self.selected = -1
		self.popupDialog = None
		self.demand = None
		self.escapeProxy = None
		self.loaded = False
		if not nui_hud.has_engine():
			return
		try:
			self.demand = nui_hud.OnDemand(self._make_board, self._restore_board)
			self.loaded = self.demand.probe()
			self.escapeProxy = nui_hud.EscapeProxy(self.OnPressEscapeKey)
		except Exception:
			self.nui_discard()
			raise

	@staticmethod
	def probe():
		"""Whether the music list's document loads (the options ask at their
		construction, so a broken list keeps the legacy options)."""
		if not nui_hud.has_engine():
			return False
		probe = nui_hud.OnDemand(lambda: nui_music_list.MusicListBoard(None))
		return probe.probe()

	def nui_ready(self):
		return self.loaded and self.demand is not None

	def nui_discard(self):
		self._nui_discarded = True
		proxy, self.escapeProxy = self.escapeProxy, None
		if proxy is not None:
			proxy.destroy()
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(self.KEY, self)

	def Destroy(self):
		popup, self.popupDialog = self.popupDialog, None
		if popup is not None:
			popup.Hide()
		self.selectEvent = None
		self.nui_discard()

	def _make_board(self):
		return nui_music_list.MusicListBoard(self)

	def _model(self):
		return {"files": [{"name": _plain(name), "label": _plain(name[:FILE_NAME_LEN])} for name in self.files],
		        "selected": self.selected}

	def _restore_board(self, board):
		board.set(**self._model())
		board.center()

	def _set(self, **values):
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.set(**values)

	# --- the options' calls (uiselectmusic.py:97-123) -----------------------------------

	def Show(self):
		if self.isLoaded == 0:
			self.isLoaded = 1
			self.__RefreshFileList()
		if self.demand is not None and self.demand.show():
			if self.escapeProxy is not None:
				self.escapeProxy.show()

	def Open(self):
		"""Shown, centered and raised at each open (uiselectmusic.py:105-112);
		the empty-list popup cannot show, as in legacy: the default entry is
		always there."""
		self.Show()
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.center()
		self.SetTop()
		if not self.files:
			self.__PopupMessage(localeInfo.MUSIC_EMPTY_MUSIC_LIST)

	def Hide(self):
		if self.escapeProxy is not None:
			self.escapeProxy.hide()
		if self.demand is not None:
			self.demand.hide()

	def IsShow(self):
		return self.demand is not None and self.demand.is_shown()

	def SetTop(self):
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.bring_to_front()
		if self.escapeProxy is not None and self.escapeProxy.is_shown():
			self.escapeProxy.show()

	def Close(self):
		if self.popupDialog is not None:
			self.popupDialog.Hide()
		self.Hide()

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def SAFE_SetSelectEvent(self, event):
		self.selectEvent = nui_hud._mem_func(event)

	# --- the board's events -----------------------------------------------------------------

	def nui_pick(self, index):
		if 0 <= index < len(self.files):
			self.selected = index
			self._set(selected=index)

	def nui_act(self, what):
		if what == "ok":
			self.__OnOK()
		elif what == "cancel":
			self.Hide()
		elif what == "refresh":
			self.__RefreshFileList()

	def __OnOK(self):
		"""uiselectmusic.py:182-189."""
		if 0 <= self.selected < len(self.files):
			if self.selectEvent:
				self.selectEvent(self.files[self.selected])
			self.Hide()
		else:
			self.__PopupMessage(localeInfo.MUSIC_NOT_SELECT_MUSIC)

	def __RefreshFileList(self):
		"""uiselectmusic.py:197-211: the default theme, then every mp3."""
		self.files = [localeInfo.MUSIC_METIN2_DEFAULT_THEMA] + list(app.GetFileList("BGM/*.mp3"))
		self.selected = -1
		self._set(**self._model())

	def __PopupMessage(self, msg):
		import uiCommon
		if self.popupDialog is None:
			self.popupDialog = uiCommon.PopupDialog()
		self.popupDialog.SetText(msg)
		self.popupDialog.Open()
