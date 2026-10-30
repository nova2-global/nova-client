"""NovaUI character window (nui/windows/character/character.rml; P15 spec 4).

While the character flag is on, Interface.__MakeWindows makes CharacterWindow
below through nui_windows.make() instead of uiCharacter.CharacterWindow. It
is a subclass of the legacy class (P15 spec D1): its constructor is
legacy's, whose uiscript loader it replaces with proxies standing where the
legacy widgets were (nui_slots.FullSlotWindowProxy for the skill, support,
emotion and quest slot windows; nui_proxies for the texts, buttons, images,
pages, title bars and the quest scroll bar), and legacy's __BindObject and
__BindEvent bind them to the legacy handlers unchanged. So every flow,
packet and rule (the stat points, the skill groups, the riding page, the
skill levels and their plus buttons, the grade columns, the cooldown store,
the emotions, the quests) is the legacy class's own code; the proxies
record what it tells them and the board shows it. Legacy's ScriptWindow
stays underneath, a 0 x 0 window in the UI layer, so IsShow, the Escape
chain and SetTop are legacy's.

No Python runs per frame (D5): OnUpdate is None, so the C++ that calls a
window's OnUpdate every frame finds nothing to call. Legacy's OnUpdate
rewrote the quest clocks every frame; here each RefreshQuest writes each
clock's end once and the document's nui-countdown elements count it down
(D4). The board instances one tab's panel at a time (D3): each panel is a
list of zero or one entry. The board loads at the window's first show and
is kept, hidden, after it, every panel list empty (nui_hud.KeptBoard, P15
V-2b); a refresh while hidden runs legacy's refresh on the proxies and the
board takes their last state at its next show. Every
count comes from nui_limits.current()."""

import sys

import localeInfo
import player
import quest
import ui
import uiCharacter
import uiScriptLocale
import wndMgr

import nui
import nui_hud
import nui_limits
import nui_proxies
import nui_slots
import nui_windows

DOCUMENT = "nui/windows/character/character.rml"
KEY = "character"
# Legacy's place (uiscript/characterwindow.py:18-19: x 24, y (H - 37 - 361) / 2,
# so H / 2 - 199) and, in the modern looks, the gap kept to the quest
# buttons along the left edge (I-1), in dp.
LEGACY_LEFT_DP = 24
LEGACY_HALF_HEIGHT_DP = 199
EDGE_GAP_DP = 8
TABS = ("STATUS", "SKILL", "EMOTICON", "QUEST")
PANELS = {"STATUS": "panel_status", "SKILL": "panel_skill", "EMOTICON": "panel_emoticon", "QUEST": "panel_quest"}
# The status texts legacy's RefreshStatus sets, by child name, and their model keys.
STATUS_TEXTS = (("Level_Value", "level"), ("Exp_Value", "exp"), ("RestExp_Value", "exp_rest"), ("HP_Value", "hp"),
                ("SP_Value", "sp"), ("STR_Value", "st"), ("DEX_Value", "dx"), ("HTH_Value", "ht"), ("INT_Value", "iq"),
                ("ATT_Value", "att"), ("DEF_Value", "def"), ("MATT_Value", "matt"), ("MDEF_Value", "mdef"),
                ("ASPD_Value", "aspd"), ("MSPD_Value", "mspd"), ("CSPD_Value", "cspd"), ("ER_Value", "er"))
# The stat buttons' keys (uicharacter.py statusPlusButtonDict) and their model suffixes.
STATS = (("HTH", "ht"), ("INT", "iq"), ("STR", "st"), ("DEX", "dx"))
# The skill group buttons' x in the uiscript and in __SetSkillGroupName: column 0, 1, 2.
GROUP_COLUMNS = {5: 0, 50: 1, 95: 2}
# The uiscript's labels of the three group buttons, before RefreshCharacter names them.
GROUP_LABELS = ("Group1", "Group2", "Group3")
# The locale's label art classic shows (uiscript characterwindow.py, LOCALE_PATH):
# model key art.<key>, the file in the locale's windows folder (D18).
ART = (("tab_1", "tab_1.sub"), ("tab_2", "tab_2.sub"), ("tab_3", "tab_3.sub"), ("tab_4", "tab_4.sub"),
       ("level", "label_level.sub"), ("cur_exp", "label_cur_exp.sub"), ("last_exp", "label_last_exp.sub"),
       ("std", "label_std.sub"), ("uppt", "label_uppt.sub"), ("std_item1", "label_std_item1.sub"),
       ("std_item2", "label_std_item2.sub"), ("ext", "label_ext.sub"), ("ext_item1", "label_ext_item1.sub"),
       ("ext_item2", "label_ext_item2.sub"))


# The class chip of the modern looks: chr.RaceToJob's job (playerSettingModule
# JOB_WARRIOR to JOB_SHAMAN) and the localeInfo key of its name.
JOB_NAMES = {0: "JOB_WARRIOR", 1: "JOB_ASSASSIN", 2: "JOB_SURA", 3: "JOB_SHAMAN"}


def job_label(job, group, group_names):
	"""The class chip's text: the job's name and, with a skill group, the
	group's name as legacy names it (SKILL_GROUP_NAME_DICT), joined by a
	middle dot ("Warrior · Body"); "" for a job without a name."""
	name = getattr(localeInfo, JOB_NAMES.get(job, ""), "") if job in JOB_NAMES else ""
	if not name:
		return ""
	group_name = group_names.get(job, {}).get(group, "") if group else ""
	return nui.plain_text(name + (" · " + group_name if group_name else ""))


def art_of(windows_path):
	"""{key: store path} of ART in a locale's windows folder
	(uiScriptLocale.WINDOWS_PATH, "locale/en/ui/windows/"), rooted."""
	folder = "/" + windows_path.replace("\\", "/").lstrip("/")
	if not folder.endswith("/"):
		folder += "/"
	return dict((key, folder + name) for key, name in ART)


class _GroupButtonProxy(nui_proxies.ButtonProxy):
	"""A skill group button (a radio button): it keeps its place, since
	legacy moves the riding button between the second and third column."""

	def __init__(self, on_change=None, x=0):
		nui_proxies.ButtonProxy.__init__(self, on_change)
		self.x = int(x)

	def SetPosition(self, x, y):
		self.x = int(x)
		self._changed()


class _CharacterBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The character window's document; its events go to its window. A press
	on it raises the window, as legacy's window manager does
	(RaisesOnPress); buttons act on a left mousedown."""

	DOCUMENT = DOCUMENT
	MODEL = "character"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner._close_tab()

	@nui.on("tab_press")
	def on_tab_press(self, name, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_tab(str(name))

	# --- the status page --------------------------------------------------------

	@nui.on("stat_plus")
	def on_stat_plus(self, key, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_stat(self._owner.statusPlusButtonDict.get(str(key)))

	@nui.on("stat_minus")
	def on_stat_minus(self, key, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_stat(self._owner.statusMinusButtonDict.get(str(key) + "-"))

	@nui.on("stat_over")
	def on_stat_over(self, kind, key):
		self._owner._stat_button(kind, key, True)

	@nui.on("stat_out")
	def on_stat_out(self, kind, key):
		self._owner._stat_button(kind, key, False)

	@nui.on("name_over")
	def on_name_over(self):
		self._owner._name_hover(True)

	@nui.on("name_out")
	def on_name_out(self):
		self._owner._name_hover(False)

	# --- the skill page ---------------------------------------------------------

	@nui.on("group_press")
	def on_group_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_group(int(index))

	@nui.on("skill_plus")
	def on_skill_plus(self, slot, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_plus(int(slot))

	# --- the slot grids: the legacy slot windows' events ---------------------------

	def _grid(self, name):
		return self._owner._grids[name]

	@nui.on("skill_press")
	def on_skill_press(self, index, button):
		self.raise_for(button)
		self._owner._cell_press("skill", int(index), button)

	@nui.on("skill_release")
	def on_skill_release(self, index, button):
		self._grid("skill").release(int(index), button)

	@nui.on("skill_use")
	def on_skill_use(self, index):
		self._owner._cell_use("skill", int(index))

	@nui.on("skill_over")
	def on_skill_over(self, index):
		self._grid("skill").over(int(index))

	@nui.on("skill_out")
	def on_skill_out(self, index):
		self._grid("skill").out(int(index))

	@nui.on("skill_drop")
	def on_skill_drop(self, index):
		self._grid("skill").drop(int(index))

	@nui.on("support_press")
	def on_support_press(self, index, button):
		self.raise_for(button)
		self._owner._cell_press("support", int(index), button)

	@nui.on("support_release")
	def on_support_release(self, index, button):
		self._grid("support").release(int(index), button)

	@nui.on("support_use")
	def on_support_use(self, index):
		self._owner._cell_use("support", int(index))

	@nui.on("support_over")
	def on_support_over(self, index):
		self._grid("support").over(int(index))

	@nui.on("support_out")
	def on_support_out(self, index):
		self._grid("support").out(int(index))

	@nui.on("support_drop")
	def on_support_drop(self, index):
		self._grid("support").drop(int(index))

	@nui.on("solo_press")
	def on_solo_press(self, index, button):
		self.raise_for(button)
		self._owner._cell_press("solo", int(index), button)

	@nui.on("solo_release")
	def on_solo_release(self, index, button):
		self._grid("solo").release(int(index), button)

	@nui.on("solo_use")
	def on_solo_use(self, index):
		self._owner._cell_use("solo", int(index))

	@nui.on("solo_over")
	def on_solo_over(self, index):
		self._grid("solo").over(int(index))

	@nui.on("solo_out")
	def on_solo_out(self, index):
		self._grid("solo").out(int(index))

	@nui.on("solo_drop")
	def on_solo_drop(self, index):
		self._grid("solo").drop(int(index))

	@nui.on("dual_press")
	def on_dual_press(self, index, button):
		self.raise_for(button)
		self._owner._cell_press("dual", int(index), button)

	@nui.on("dual_release")
	def on_dual_release(self, index, button):
		self._grid("dual").release(int(index), button)

	@nui.on("dual_use")
	def on_dual_use(self, index):
		self._owner._cell_use("dual", int(index))

	@nui.on("dual_over")
	def on_dual_over(self, index):
		self._grid("dual").over(int(index))

	@nui.on("dual_out")
	def on_dual_out(self, index):
		self._grid("dual").out(int(index))

	@nui.on("dual_drop")
	def on_dual_drop(self, index):
		self._grid("dual").drop(int(index))

	@nui.on("quest_press")
	def on_quest_press(self, index, button):
		self.raise_for(button)
		self._owner._cell_press("quest", int(index), button)

	@nui.on("quest_over")
	def on_quest_over(self, index):
		self._grid("quest").over(int(index))

	@nui.on("quest_out")
	def on_quest_out(self, index):
		self._grid("quest").out(int(index))

	@nui.on("quest_clock_over")
	def on_quest_clock_over(self, index):
		# A row's countdown reached its end (countdownend: once per end, at
		# once for one already past).
		self._owner._quest_clock_over(int(index))

	@nui.on("quest_scroll")
	def on_quest_scroll(self, delta):
		# The wheel over the list (new: legacy's list has no wheel): one line
		# per notch, down for a positive delta.
		delta = float(delta)
		if delta:
			self._owner._scroll_quests(1 if delta > 0 else -1)

	@nui.on("quest_scroll_press")
	def on_quest_scroll_press(self, delta, button):
		self.raise_for(button)
		if button == 0:
			self._owner._scroll_quests(int(delta))


class CharacterWindow(uiCharacter.CharacterWindow):
	"""uiCharacter.CharacterWindow on NovaUI (Interface.wndCharacter)."""

	NUI_FACADE = True
	# D5: no per-frame Python. The C++ calls a window's OnUpdate only when the
	# attribute is callable (PythonUtils.cpp:370-391), and a method doing
	# nothing would still be a Python call every frame.
	OnUpdate = None

	def __init__(self):
		nui_hud.take_over(KEY, self)
		self._nui_discarded = False
		self._limits = nui_limits.current()
		self._grids = {}
		self._grids_by_proxy = {}
		self._flush_depth = 0
		self._flushing = False
		self._quests_dirty = False
		# The stat button (kind, key) and the name slot the pointer is over:
		# their outs, which the board cannot send once it hides (_end_hovers).
		self._hover_stat = None
		self._hover_name = False
		self._state = self._empty_state()
		self._place = None
		self.loaded = False
		self.demand = None
		if nui_hud.has_engine_3c():
			# V-2b (P15 spec 8.1, D9): the board is kept, hidden, after its first open.
			self.demand = nui_hud.KeptBoard(self._make_board, self._restore_board, self._keep_board, self._empty_board)
		try:
			uiCharacter.CharacterWindow.__init__(self)
			if self.demand is not None:
				self.loaded = self.demand.probe()
		except Exception:
			self.nui_discard()
			raise

	# --- make()'s protocol ------------------------------------------------------------

	def nui_ready(self):
		return self.loaded and self.demand is not None and nui_hud.has_engine_3c()

	def nui_discard(self):
		self._nui_discarded = True
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		nui_hud.forget(KEY, self)

	# --- the model ------------------------------------------------------------------

	def _skill_slots(self):
		return nui_limits.skill_active_slots(self._limits)

	def _support_slots(self):
		start = self._limits.SKILL_SUPPORT_SLOT_START
		return list(range(start, start + self._limits.SKILL_SUPPORT_SLOTS))

	def _empty_state(self):
		limits = self._limits
		step = limits.SKILL_GRADE_STEP_COUNT
		state = {
			"tab": "STATUS",
			"panel_status": [1], "panel_skill": [], "panel_emoticon": [], "panel_quest": [],
			"placed": False,
			"art": art_of(uiScriptLocale.WINDOWS_PATH),
			"attach_right": bool(nui_slots.ATTACH_RIGHT),
			"face": "", "name": "", "guild": "", "has_guild": False, "job": "",
			"stat_points": "", "stat_points_shown": False,
			"groups": [{"index": i, "label": GROUP_LABELS[i], "shown": True, "down": False, "col": i} for i in range(3)],
			"group_name": "", "group_name_shown": True,
			"active_points": "", "support_points": "", "support_points_shown": True,
			"skills": [dict(nui_slots.empty_cell(i), slot=s, button=False, col=(s - 1) // step)
			           for i, s in enumerate(self._skill_slots())],
			"support": [dict(nui_slots.empty_cell(i), slot=s, button=False) for i, s in enumerate(self._support_slots())],
			"solo": [dict(nui_slots.empty_cell(i), slot=s) for i, s in enumerate(nui_limits.emote_slots("solo", limits))],
			"dual": [dict(nui_slots.empty_cell(i), slot=s) for i, s in enumerate(nui_limits.emote_slots("dual", limits))],
			# The grids' widths (their nui-slot-grid--cols-<n> class) from the limits, as their cells.
			"support_cols": limits.SKILL_SUPPORT_COLUMNS, "emote_cols": limits.EMOTE_COLUMNS,
			# V-2b: the tab strip, one entry while the board shows, none while it is kept hidden.
			"tabs_on": [1],
			"quests": [self._empty_row(i) for i in range(limits.QUEST_ROWS)],
			"quest_cells": [dict(nui_slots.empty_cell(i), slot=i, base=True) for i in range(limits.QUEST_ROWS)],
			"quest_scroll_shown": False, "quest_scroll_pos": 0.0,
		}
		for _, key in STATUS_TEXTS:
			state[key] = ""
		for _, suffix in STATS:
			state["plus_" + suffix] = False
			state["minus_" + suffix] = False
		return state

	@staticmethod
	def _empty_row(row):
		return {"row": row, "shown": False, "name": "", "icon": "", "counter": "", "clock_text": "",
		        "clock_prefix": "", "clock_end": 0.0, "clock_over": False}

	def _set(self, **values):
		self._state.update(values)
		board = self.demand.board() if self.demand is not None else None
		if board is not None:
			board.set(**values)

	def _make_board(self):
		return _CharacterBoard(self, self._state)

	def _restore_board(self, board):
		board.set(**self._state)
		place = self._place if self._place is not None else self._edge_place(board)
		if place is not None:
			self._state["placed"] = True
			board.set(placed=True)
			board.set_position(place[0], place[1])

	def _edge_place(self, board):
		"""The first open's place in the modern looks (P15 fix stage, I-1):
		the NovaUI quest buttons along the left edge are opaque tiles and
		labels drawn over the window's legacy place (24, (H - 37 - 361) / 2;
		they are TOP_MOST, as legacy's text buttons), and they take its tab
		presses, so the window opens right of them, at legacy's height. None
		in classic (legacy's place) or with no quest button over the place."""
		if board.has_class("skin-classic"):
			return None
		edge = sys.modules.get("nui_edge_buttons")
		right = edge.quest_stack_right() if edge is not None and hasattr(edge, "quest_stack_right") else 0
		scale = nui.get_scale() or 1.0
		left = right / scale + EDGE_GAP_DP
		if right <= 0 or left <= LEGACY_LEFT_DP:
			return None
		return (left, wndMgr.GetScreenHeight() / scale / 2.0 - LEGACY_HALF_HEIGHT_DP)

	def _empty_board(self, board):
		"""V-2b: the hidden kept board holds no panel and no tab strip (RmlUi
		updates every element of a loaded document each frame); _restore_board
		sets the strip and the shown tab's panel again at the next show."""
		board.set(tabs_on=[], **dict((key, []) for key in PANELS.values()))

	def _keep_board(self, board):
		"""Legacy's window keeps the place it was dragged to (D10): the board's
		top left in dp, read before it goes."""
		box = board.element_box("")
		if box:
			scale = nui.get_scale() or 1.0
			self._place = (box[0] / scale, box[1] / scale)

	def board(self):
		return self.demand.board() if self.demand is not None else None

	# --- the proxies' callbacks -------------------------------------------------------

	def _on_status_text(self, key):
		def write(text):
			self._set(**{key: nui.plain_text(text)})
		return write

	def _on_stat_button(self, key):
		def write(proxy):
			self._set(**{key: proxy.IsShow()})
		return write

	def _on_name(self, text):
		self._set(name=nui.plain_text(text))

	def _on_guild(self, text):
		self._set(guild=nui.plain_text(text))

	def _on_guild_slot(self, shown):
		self._set(has_guild=bool(shown))

	def _on_face(self, *ignored):
		image = self.faceImage if getattr(self, "faceImage", None) is not None else None
		face = nui_slots.icon_source(image.image) if image is not None and image.IsShow() and image.image else ""
		self._set(face=face)

	def _CharacterWindow__SetJobText(self, mainJob, subJob):
		"""Legacy's (RefreshCharacter's job and skill group; it shows nothing),
		and the modern looks' class chip: the job, and the group from level
		5 on, as legacy's rule takes the group then."""
		uiCharacter.CharacterWindow._CharacterWindow__SetJobText(self, mainJob, subJob)
		group = subJob if player.GetStatus(player.LEVEL) >= 5 else 0
		self._set(job=job_label(mainJob, group, self.SKILL_GROUP_NAME_DICT))

	def _on_stat_points(self, text):
		self._set(stat_points=nui.plain_text(text))

	def _on_stat_points_label(self, shown):
		self._set(stat_points_shown=bool(shown))

	def _on_groups(self, *ignored):
		buttons = getattr(self, "skillGroupButton", ())
		groups = []
		for index, button in enumerate(buttons):
			groups.append({"index": index, "label": nui.plain_text(button.GetText()), "shown": button.IsShow(),
			               "down": button.IsDown(), "col": GROUP_COLUMNS.get(button.x, index)})
		if groups:
			self._set(groups=groups)

	def _on_group_name(self, *ignored):
		proxy = getattr(self, "activeSkillGroupName", None)
		if proxy is not None:
			self._set(group_name=nui.plain_text(proxy.GetText()), group_name_shown=proxy.IsShow())

	def _on_active_points(self, text):
		self._set(active_points=nui.plain_text(text))

	def _on_support_points(self, text):
		self._set(support_points=nui.plain_text(text))

	def _on_support_points_label(self, shown):
		self._set(support_points_shown=bool(shown))

	def _with_extras(self, proxy, cells, keys):
		extras = proxy.extras()
		events = self._grids_by_proxy.get(id(proxy))
		states, picked = (events.states, events.picked) if events is not None else ({}, -1)
		marked = nui_slots.with_states(cells, states, picked)
		for cell, slot in zip(marked, proxy.slot_numbers):
			extra = extras[cell["index"]]
			cell["slot"] = slot
			if "button" in keys:
				cell["button"] = extra["button"] and bool(cell["kind"])
			if "col" in keys:
				cell["col"] = (slot - 1) // self._limits.SKILL_GRADE_STEP_COUNT
			if "base" in keys:
				cell["base"] = extra["closed"]
		return marked

	def _on_skills(self, cells):
		self._set(skills=self._with_extras(self.skillPageDict["ACTIVE"], cells, ("button", "col")))

	def _on_support(self, cells):
		self._set(support=self._with_extras(self.skillPageDict["SUPPORT"], cells, ("button",)))

	def _on_solo(self, cells):
		self._set(solo=self._with_extras(self.soloEmotionSlot, cells, ()))

	def _on_dual(self, cells):
		self._set(dual=self._with_extras(self.dualEmotionSlot, cells, ()))

	def _on_quest_cells(self, cells):
		self._set(quest_cells=self._with_extras(self.questSlot, cells, ("base",)))
		self._quests_dirty = True

	def _on_quest_row(self, *ignored):
		"""A quest text or its shown state changed: the rows are made again at
		the flush, after the quest cells (their icons)."""
		self._quests_dirty = True

	def _quest_rows(self):
		rows = []
		for row in range(self._limits.QUEST_ROWS):
			entry = dict(self._state["quests"][row])
			name = self._quest_texts[0][row]
			entry["shown"] = name.IsShow()
			entry["name"] = nui.plain_text(name.GetText())
			entry["counter"] = nui.plain_text(self._quest_texts[2][row].GetText())
			cells = self._state["quest_cells"]
			entry["icon"] = cells[row]["icon"] if row < len(cells) else ""
			rows.append(entry)
		self._set(quests=rows)

	def _on_quest_scroll(self, proxy):
		self._set(quest_scroll_shown=proxy.IsShow(), quest_scroll_pos=float(proxy.GetPos()))

	def _quest_icon(self, slot, handle):
		"""The quest row's icon file: nuigame.QuestIconFileName names what
		quest.GetQuestData's image is (PythonQuest.cpp:188-203)."""
		try:
			import nuigame
		except ImportError:
			return ""
		name = getattr(nuigame, "QuestIconFileName", None)
		return name(self.questShowingStartIndex + slot) if name is not None else ""

	# --- the loader (uicharacter.py:145-147, 389-408, on proxies) -------------------------

	def _CharacterWindow__LoadWindow(self):
		"""Legacy's, without its right-to-left uiscript (NovaUI never runs in
		such a locale) and without exception.Abort (make() falls back to the
		legacy window when this raises): the proxies, legacy's own
		__BindObject and __BindEvent, the four plain tooltips on NovaUI while
		the tooltips flag is on (D6), the status page."""
		if self.isLoaded == 1:
			return
		self.isLoaded = 1
		# The uiscript's style (characterwindow.py: "movable", "float"): a
		# float window is the one SetTop raises (CWindow::SetTop).
		self.AddFlag("movable")
		self.AddFlag("float")
		self._CharacterWindow__LoadScript("UIScript/CharacterWindow.py")
		self._CharacterWindow__BindObject()
		self._CharacterWindow__BindEvent()
		self._plain_tooltips()
		self.SetState("STATUS")

	def _CharacterWindow__LoadScript(self, fileName):
		"""Every child legacy's __BindObject reads, as a proxy under its
		uiscript name (P15 spec 4.4.1); nothing is loaded."""
		limits = self._limits
		children = {}
		children["Face_Image"] = nui_proxies.ImageProxy(self._on_face)
		children["Face_Image"].on_show = self._on_face
		for name in ("Face_Slot", "Character_Page", "Skill_Page", "Emoticon_Page", "Quest_Page", "Tab_01", "Tab_02",
		             "Tab_03", "Tab_04"):
			children[name] = nui_proxies.WindowProxy()
		children["Support_Skill_Point_Label"] = nui_proxies.WindowProxy(self._on_support_points_label)
		children["Status_Plus_Label"] = nui_proxies.WindowProxy(self._on_stat_points_label)
		children["Active_Skill_Point_Label"] = nui_proxies.WindowProxy()
		children["Character_Name_Slot"] = nui_proxies.ImageProxy()
		children["Guild_Name_Slot"] = nui_proxies.ImageProxy()
		children["Guild_Name_Slot"].on_show = self._on_guild_slot
		children["Character_Name"] = nui_proxies.TextProxy(self._on_name)
		children["Guild_Name"] = nui_proxies.TextProxy(self._on_guild)
		children["Status_Plus_Value"] = nui_proxies.TextProxy(self._on_stat_points)
		children["Active_Skill_Point_Value"] = nui_proxies.TextProxy(self._on_active_points)
		children["Support_Skill_Point_Value"] = nui_proxies.TextProxy(self._on_support_points)
		children["Active_Skill_Group_Name"] = nui_proxies.TextProxy(self._on_group_name)
		children["Active_Skill_Group_Name"].on_show = self._on_group_name
		for name, key in STATUS_TEXTS:
			children[name] = nui_proxies.TextProxy(self._on_status_text(key))
		for index, x in enumerate(sorted(GROUP_COLUMNS)):
			button = _GroupButtonProxy(self._on_groups, x)
			button.text = GROUP_LABELS[index]
			children["Skill_Group_Button_%d" % (index + 1)] = button
		for index in range(1, 5):
			children["Tab_Button_%02d" % index] = nui_proxies.ButtonProxy()
		for key, suffix in STATS:
			name = {"HTH": "HTH", "INT": "INT", "STR": "STR", "DEX": "DEX"}[key]
			children[name + "_Plus"] = nui_proxies.ButtonProxy(self._on_stat_button("plus_" + suffix))
			children[name + "_Minus"] = nui_proxies.ButtonProxy(self._on_stat_button("minus_" + suffix))
		for name in ("Character_TitleBar", "Skill_TitleBar", "Emoticon_TitleBar", "Quest_TitleBar"):
			children[name] = nui_proxies.BoardProxy()
		children["Skill_Active_Slot"] = nui_slots.FullSlotWindowProxy(self._skill_slots(), self._on_skills, limits=limits)
		children["Skill_ETC_Slot"] = nui_slots.FullSlotWindowProxy(
			self._support_slots(), self._on_support, cols=limits.SKILL_SUPPORT_COLUMNS,
			rows=limits.SKILL_SUPPORT_SLOTS // max(1, limits.SKILL_SUPPORT_COLUMNS), limits=limits)
		children["SoloEmotionSlot"] = nui_slots.FullSlotWindowProxy(
			nui_limits.emote_slots("solo", limits), self._on_solo, cols=limits.EMOTE_COLUMNS, rows=limits.EMOTE_ROWS,
			limits=limits)
		children["DualEmotionSlot"] = nui_slots.FullSlotWindowProxy(
			nui_limits.emote_slots("dual", limits), self._on_dual, cols=limits.EMOTE_COLUMNS, rows=limits.EMOTE_ROWS,
			limits=limits)
		children["Quest_Slot"] = nui_slots.FullSlotWindowProxy(
			range(limits.QUEST_ROWS), self._on_quest_cells, cols=1, rows=limits.QUEST_ROWS, icon_of=self._quest_icon,
			limits=limits)
		children["Quest_ScrollBar"] = nui_proxies.ScrollBarProxy(self._on_quest_scroll)
		children["Quest_ScrollBar"].shown = False
		names, times, counts = [], [], []
		for row in range(limits.QUEST_ROWS):
			for name, kind in (("Quest_Name_0%d", names), ("Quest_LastTime_0%d", times), ("Quest_LastCount_0%d", counts)):
				proxy = nui_proxies.TextProxy(self._on_quest_row)
				proxy.on_show = self._on_quest_row
				children[name % row] = proxy
				kind.append(proxy)
		self._quest_texts = (names, times, counts)
		self.ElementDictionary = children
		self._bind_events()

	def _bind_events(self):
		"""Each grid's LegacySlotEvents (P15 spec 4.4.1; no grid needs
		on_attaching: no cell is taller than one)."""
		children = self.ElementDictionary
		grids = {"skill": children["Skill_Active_Slot"], "support": children["Skill_ETC_Slot"],
		         "solo": children["SoloEmotionSlot"], "dual": children["DualEmotionSlot"], "quest": children["Quest_Slot"]}
		self._grids = dict((name, nui_slots.LegacySlotEvents(proxy, on_states=self._on_states(name)))
		                   for name, proxy in grids.items())
		self._grids_by_proxy = dict((id(grids[name]), events) for name, events in self._grids.items())

	def _on_states(self, name):
		"""A grid's footprint states: legacy's skill and emotion windows are
		SLOT_STYLE_NONE (no footprint), so these only clear a pick."""
		def write(states, picked):
			proxy = self._grids[name].proxy
			proxy.on_refresh(proxy.cells())
		return write

	def _plain_tooltips(self):
		"""D6: while the tooltips flag is on, the four plain tooltips legacy's
		__BindObject made (the stat, job and alignment ones, and the
		emotion one) become NovaUI's, made with the same arguments; legacy's
		own otherwise."""
		if not nui_windows.use("tooltips")[0]:
			return
		try:
			import nui_item_tooltip
			made = (nui_item_tooltip.PlainToolTip(), nui_item_tooltip.PlainToolTip(), nui_item_tooltip.PlainToolTip(130),
			        nui_item_tooltip.PlainToolTip())
		except Exception as error:
			nui_windows.note_failure("tooltips", "the character window's plain tooltips (%s)" % type(error).__name__)
			return
		self.toolTip, self.toolTipJob, self.toolTipAlignment, self.emotionToolTip = made

	# --- the flush ------------------------------------------------------------------

	def _flush(self):
		"""What legacy changed during the call that ends now reaches the model:
		each slot window it changed without RefreshSlot (FullSlotWindowProxy's
		dirty flag; CSlotWindow draws a change at once), then the quest rows
		(their icons come from the quest cells)."""
		if self._flushing:
			return
		self._flushing = True
		try:
			for events in list(self._grids.values()):
				if events.proxy.dirty:
					events.proxy.push()
			if self._quests_dirty and getattr(self, "_quest_texts", None):
				self._quests_dirty = False
				self._quest_rows()
		finally:
			self._flushing = False

	# --- the board's presses -----------------------------------------------------------

	def _close_tab(self):
		bar = self.titleBarDict.get(self.state) if self.titleBarDict else None
		if bar is not None:
			bar.close()

	def _press_tab(self, name):
		"""A tab: its radio button, which ignores a press while it is down
		(CRadioButton::OnMouseLeftButtonDown); legacy's event then sets the
		state."""
		button = self.tabButtonDict.get(name) if self.tabButtonDict else None
		if button is None or button.IsDown():
			return
		button.Down()
		button.click()

	def _press_stat(self, button):
		if button is not None and button.IsShow():
			button.click()

	def _stat_button(self, kind, key, over):
		"""The pointer enters or leaves a stat button: legacy's window manager
		calls its ShowToolTip or HideToolTip (uicharacter.py:376-382). An out
		reaches only the button the pointer was over, as legacy sends
		OnMouseOverOut only to its point window."""
		buttons = self.statusPlusButtonDict if kind == "plus" else self.statusMinusButtonDict
		button = buttons.get(str(key) if kind == "plus" else str(key) + "-") if buttons else None
		if button is None:
			return
		if over:
			self._hover_stat = (kind, key)
			button.over()
		elif self._hover_stat == (kind, key):
			self._hover_stat = None
			button.out()

	def _name_hover(self, over):
		"""The name slot's MOUSE_OVER_IN or MOUSE_OVER_OUT (the alignment
		tooltip); an out only after an in, as legacy's."""
		if over:
			self._hover_name = True
			self.characterNameSlot.fire("MOUSE_OVER_IN")
		elif self._hover_name:
			self._hover_name = False
			self.characterNameSlot.fire("MOUSE_OVER_OUT")

	def _end_hovers(self):
		"""Legacy's window manager sends the window it hid OnMouseOverOut at
		the next mouse move (CWindowManager::RunMouseMove), so the stat
		button's HideToolTip runs (it also clears refreshToolTip, which
		RefreshStatus would otherwise run while the window is closed) and
		the name slot hides the alignment tooltip. The board hears no
		mouseout as it goes: send them here."""
		if self._hover_stat is not None:
			kind, key = self._hover_stat
			self._stat_button(kind, key, False)
		self._hover_stat = None
		self._name_hover(False)

	def _press_group(self, index):
		"""A skill group button: a radio button, so a press on the one that
		is down does nothing."""
		buttons = getattr(self, "skillGroupButton", ())
		if not (0 <= index < len(buttons)):
			return
		button = buttons[index]
		if not button.IsShow() or button.IsDown():
			return
		button.click()

	def _press_plus(self, slot):
		"""A plus button: legacy's pressed-button event of its slot window."""
		for name in ("skill", "support"):
			events = self._grids.get(name)
			index = events.proxy.index_of(slot) if events is not None else None
			if index is not None:
				if events.proxy.extras()[index]["button"]:
					events.pressed_button(index)
				return

	def _covered(self, name, index):
		"""Whether the cell's cover button lies over it (a set skill or
		emotion slot with a cover; legacy's CCoverButton takes the presses
		there), and whether that cover is disabled."""
		proxy = self._grids[name].proxy
		cells = proxy.cells()
		if not (0 <= index < len(cells)):
			return False, False
		cell = cells[index]
		return bool(cell["cover"]), bool(cell["cover"] and cell["unavailable"])

	def _cell_press(self, name, index, button):
		"""A press on a cell, as legacy's cover button passes it on: a
		disabled cover takes every press and does nothing (CCoverButton
		returns while disabled)."""
		if self._covered(name, index)[1]:
			return
		self._grids[name].press(index, button)

	def _cell_use(self, name, index):
		"""A double click: the slot window's use event, unless a cover button
		lies over the cell: then the cover takes the double click as a press
		(CButton::OnMouseLeftButtonDoubleClick), which the board's second
		mousedown already made, so nothing more."""
		if self._covered(name, index)[0]:
			return
		self._grids[name].use(index)

	def _scroll_quests(self, delta):
		"""The quest list's arrows and the wheel over it: one line per step,
		then legacy's scroll event. The position goes to the line itself
		(the bar's step stays 1 / lines for its readers): adding 1 / lines
		step by step drifts (0.1 * 8 is 0.7999...), and legacy's OnQuestScroll
		truncates lines * pos, so a click would stall or skip a line. A hair
		over the line's own position keeps the truncation on it."""
		bar = self.questScrollBar
		if bar is None or not bar.IsShow():
			return
		lines = max(1, quest.GetQuestCount() - self._limits.QUEST_ROWS)
		bar.SetScrollStep(1.0 / lines)
		line = max(0, min(lines, self.questShowingStartIndex + int(delta)))
		bar.SetPos(1.0 if line >= lines else (line + 1e-6) / lines)

	# --- what NovaUI changes (P15 spec 4.4's table) ------------------------------------

	def _CharacterWindow__UpdateQuestClock(self):
		"""Legacy's rule (uicharacter.py:695-723), whatever the tab, with the
		same index legacy reads (D14: row i shows quest i's clock, not the
		scrolled one's); legacy's text goes to the Quest_LastTime proxies,
		and the model gets each row's clock: a name and a time left run as
		a countdown (clock_prefix and clock_end on the NovaUI clock), else
		legacy's static text; clock_over marks a time that is up (the modern
		looks' danger color)."""
		rows = [dict(row) for row in self._state["quests"]]
		count = min(quest.GetQuestCount(), quest.QUEST_MAX_NUM)
		for i in range(count):
			(lastName, lastTime) = quest.GetQuestLastTime(i)
			clockText = self._legacy_clock_text(lastName, lastTime)
			if i < len(self.questLastTimeList):
				self.questLastTimeList[i].SetText(clockText)
			if i >= len(rows):
				continue
			if len(lastName) > 0 and lastTime > 0:
				rows[i].update({"clock_text": "", "clock_prefix": nui.plain_text(lastName + " : "),
				                "clock_end": nui.now() + float(lastTime), "clock_over": False})
			else:
				rows[i].update({"clock_text": nui.plain_text(clockText), "clock_prefix": "", "clock_end": 0.0,
				                "clock_over": len(lastName) > 0})
		self._set(quests=rows)

	def _quest_clock_over(self, index):
		"""A row's countdown ran out: the countdown shows legacy's over text
		by itself; the row's clock takes the time-up color."""
		rows = self._state["quests"]
		if not 0 <= index < len(rows) or rows[index]["clock_end"] <= 0 or rows[index]["clock_over"]:
			return
		rows = [dict(row) for row in rows]
		rows[index]["clock_over"] = True
		self._set(quests=rows)

	@staticmethod
	def _legacy_clock_text(lastName, lastTime):
		clockText = localeInfo.QUEST_UNLIMITED_TIME
		if len(lastName) > 0:
			if lastTime <= 0:
				clockText = localeInfo.QUEST_TIMEOVER
			else:
				questLastMinute = lastTime // 60
				questLastSecond = lastTime % 60
				clockText = lastName + " : "
				if questLastMinute > 0:
					clockText += str(questLastMinute) + localeInfo.QUEST_MIN
					if questLastSecond > 0:
						clockText += " "
				if questLastSecond > 0:
					clockText += str(questLastSecond) + localeInfo.QUEST_SEC
		return clockText

	def SetState(self, stateKey):
		uiCharacter.CharacterWindow.SetState(self, stateKey)
		panels = dict((key, [1] if tab == self.state else []) for tab, key in PANELS.items())
		self._set(tab=self.state, **panels)
		if self.state == "QUEST":
			self._CharacterWindow__UpdateQuestClock()

	def Show(self):
		# The board first, so a refresh legacy's Show runs reaches it.
		if self.demand is not None:
			self.demand.show()
			# Legacy's Show raises nothing: the boards raised since stay above (VF-1).
			nui_hud.keep_order(self)
		uiCharacter.CharacterWindow.Show(self)
		nui_hud.tell_taskbar("character", self.IsShow())

	def Hide(self):
		uiCharacter.CharacterWindow.Hide(self)
		# The board's parts hear no mouseout as it goes: the stat buttons and
		# the name slot (_end_hovers), the cells (LegacySlotEvents.reset).
		self._end_hovers()
		for events in self._grids.values():
			events.reset()
		if self.demand is not None:
			self.demand.hide()
		nui_hud.tell_taskbar("character", self.IsShow())

	def SetTop(self):
		board = self.board()
		if board is not None:
			board.bring_to_front()
		nui_hud.note_raise(self)
		uiCharacter.CharacterWindow.SetTop(self)

	def Destroy(self):
		demand, self.demand = self.demand, None
		if demand is not None:
			demand.destroy()
		uiCharacter.CharacterWindow.Destroy(self)
		nui_hud.forget(KEY, self)


def _flushes(method):
	"""A legacy entry point of the window (an Interface or C++ callback, a
	key, Escape): its outermost call ends with _flush()."""
	def call(self, *args, **kwargs):
		depth = getattr(self, "_flush_depth", None)
		if depth is None:
			return method(self, *args, **kwargs)
		self._flush_depth = depth + 1
		try:
			return method(self, *args, **kwargs)
		finally:
			self._flush_depth -= 1
			if self._flush_depth == 0:
				self._flush()
	call.__name__ = method.__name__
	call.__doc__ = method.__doc__
	call.__wrapped__ = method
	return call


# The facade (P15 spec 4.4: what the Interface, game.py and the C++
# callbacks call) and what the window's own close and Escape reach. Only
# Hide is bound as an event through ui.__mem_func__ (the title bars'
# close), and it takes no argument, so the wrapper's signature is safe.
FLUSHED = ("ActEmotion", "Close", "Hide", "OnActivateSkill", "OnDeactivateSkill", "OnPressEscapeKey", "OnUseSkill",
           "OverOutItem", "RefreshAlignment", "RefreshCharacter", "RefreshQuest", "RefreshSkill", "RefreshStatus",
           "SelectSkillGroup", "SetState", "Show", "SkillClearCoolTime")
for _name in FLUSHED:
	setattr(CharacterWindow, _name, _flushes(getattr(CharacterWindow, _name)))


def _flushes_owner(method):
	"""A board event: the owner's flush after it."""
	def call(self, *args):
		try:
			return method(self, *args)
		finally:
			owner = self._owner
			try:
				owner._flush()
			except ReferenceError:
				pass
	call.__name__ = method.__name__
	call._nui_events = method._nui_events
	return call


for _name, _method in list(vars(_CharacterBoard).items()):
	if getattr(_method, "_nui_events", None):
		setattr(_CharacterBoard, _name, _flushes_owner(_method))
del _name, _method
