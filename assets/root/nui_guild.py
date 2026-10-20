"""NovaUI guild window and its six pages (nui/windows/guild/guild.rml; P16
spec 5.9).

While the guild flag is on, Interface.__MakeWindows makes GuildWindow below
through nui_windows.make() instead of uiGuild.GuildWindow: a subclass of the
legacy class (nui_facade.Facade) whose uiscript loader puts proxies where
the widgets of the frame and of the six pages were (the page windows, the
tabs, the info texts, the mark, the comment lines and field, the member
lines with their grade combo boxes and general checks, the skill slot
windows, the dragon power gauge, the grade names and authority checks, the
popup as the dialog kit's message, the grade name dialog). So every
refresh, Open, Close, SelectPage, every handler and every packet is
legacy's code: the offer, the mark and symbol uploads (the lists of
nui_guild_mark), the war declaration (nui_guild_war_declare), comments,
member grades and general flags, the skills (pick, use, "+"), the dragon
power heal, grade names and authorities.

The board shows what the proxies hold (_sync): only the shown page is built
(D9: page_info, page_board, ... are [1] for the shown page, else []); the
base page's tab stays disabled, as legacy's. A grade combo box's list opens
under its line, one at a time (D11). The skill cells reach legacy's
handlers through nui_slots.LegacySlotEvents; legacy's slot windows draw
themselves, so the refreshes that set them (RefreshGuildSkillPage,
OnUseSkill) refresh the proxies after legacy's. The large mark is the
downloaded atlas's region (nui_guild_war.mark_source), which the client
reloads when the atlas downloads (_nui.ReloadImage, E4). The board exists
only while the window shows and draws below the legacy UI layer; nothing
runs per frame (legacy's reflectors and combo boxes hover in OnRender and
OnUpdate). A press in the comment field focuses it (the body takes no
focus), and while the field has NovaUI's focus the window holds wndMgr's
(nui_hud.FocusProxy), as a focused legacy edit line would."""

import guild
import localeInfo
import ui
import uiGuild
import uiPickMoney
import uiScriptLocale
import uiUploadMark
import wndMgr

import nui
import nui_facade
import nui_form_proxies
import nui_guild_grade_name
import nui_hud
import nui_proxies
import nui_slots
import nui_windows

DOCUMENT = "nui/windows/guild/guild.rml"
KEY = "guild"
# The pages in legacy's tab order (guildwindow.py's Tab_01 to Tab_06), the
# model's list key of each, and their uiscripts (uiguild.py:830-837).
PAGES = (("GUILD_INFO", "page_info", "uiscript/guildwindow_guildinfopage.py"),
         ("BOARD", "page_board", "uiscript/guildwindow_boardpage.py"),
         ("MEMBER", "page_member", "uiscript/guildwindow_memberpage.py"),
         ("BASE_INFO", "page_base", "uiscript/guildwindow_baseinfopage.py"),
         ("SKILL", "page_skill", "uiscript/guildwindow_guildskillpage.py"),
         ("GRADE", "page_grade", "uiscript/guildwindow_gradepage.py"))
PAGE_TITLES = {"GUILD_INFO": "GUILD_TILE_INFO", "BOARD": "GUILD_TILE_BOARD", "MEMBER": "GUILD_TILE_MEMBER",
               "BASE_INFO": "GUILD_TILE_BASEINFO", "SKILL": "GUILD_TILE_SKILL", "GRADE": "GUILD_TILE_GRADE"}
# The skill slot windows' first slots (guildwindow_guildskillpage.py).
PASSIVE_START, ACTIVE_START, AFFECT_START = 200, 210, 0
# The authority bits of the grade page's four checks, in column order.
AUTHORITY_BITS = (1 << 0, 1 << 1, 1 << 2, 1 << 3)
# The base page's resource names (guildwindow_baseinfopage.py), as model
# strings the document translates.
RESOURCE_NAMES = ("@ui.GUILD_WATER_STONE", "@ui.GUILD_METIN_STONE", "@ui.GUILD_WATER", "@ui.GUILD_CRYSTAL",
                  "@ui.GUILD_MINENAL", "@ui.GUILD_GEM")
# The dragon power gauge: legacy cuts its 95 px frame art at a percentage
# of 173 / 95 (uiguild.py:1603-1609), so a full gauge is 173 px wide.
GAUGE_ART, GAUGE_TRACK = 95.0, 173.0
# The comment field's F5 (RmlUi's Input::KI_F5) and the DirectInput code
# legacy's key handler takes for it (OnKeyDownInBoardPage's 63).
KEY_F5, DIK_F5 = 111, 63
# A wheel notch over the member lines moves this many lines.
WHEEL_LINES = 1
SCROLL_STEP = 0.01
# The comment field, and the control that parks NovaUI's focus when a legacy
# edit line takes wndMgr's (a button: it takes no keys).
COMMENT = "guild-comment"
PARK = "guild-post"


class _GuildBoard(nui_hud.RaisesOnPress, nui.Window):
	"""The guild window's document; its events go to its window. A press on
	it raises the window, as legacy's window manager does."""

	DOCUMENT = DOCUMENT
	MODEL = "guild"

	def __init__(self, owner, model):
		self._owner = nui_hud.keep_weakly(owner)
		self._initial = model
		nui.Window.__init__(self)

	def initial_model(self):
		return dict(self._initial)

	def _on_comment_key(self, event):
		"""The comment field's keys: Enter is its OnIMEReturn (OnPostComment),
		F5 its OnKeyDown (OnKeyDownInBoardPage, a refresh); both are kept."""
		if not self.is_visible():
			return None
		return self._owner._comment_key(event.get("key_identifier"))

	def _on_comment_focus(self, event):
		self._owner._comment_focused()

	@nui.on("board_press")
	def on_board_press(self, button):
		self.body_pressed(button)

	@nui.on("close_press")
	def on_close_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner.board.close()

	@nui.on("tab_press")
	def on_tab_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_tab(int(index))

	# --- the info page ---------------------------------------------------------------------------

	@nui.on("offer_press")
	def on_offer_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press(self._owner.pageWindow["GUILD_INFO"].offerButton)

	@nui.on("upload_mark_press")
	def on_upload_mark_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press(self._owner.pageWindow["GUILD_INFO"].uploadMarkButton)

	@nui.on("upload_symbol_press")
	def on_upload_symbol_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press(self._owner.pageWindow["GUILD_INFO"].uploadSymbolButton)

	@nui.on("declare_press")
	def on_declare_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press(self._owner.pageWindow["GUILD_INFO"].declareWarButton)

	# --- the board page ------------------------------------------------------------------------

	@nui.on("refresh_press")
	def on_refresh_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press(self._owner.pageWindow["BOARD"].refreshButton)

	@nui.on("post_press")
	def on_post_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press(self._owner.pageWindow["BOARD"].postButton)

	@nui.on("delete_press")
	def on_delete_press(self, line, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press(self._owner.pageWindow["BOARD"].deleteButtons[int(line)])

	@nui.on("comment_press")
	def on_comment_press(self, button):
		"""A press in the comment field focuses it, as a press focuses
		legacy's edit line. The body takes no focus (focus: none), so RmlUi
		gives a press inside it to nothing (Context::FindFocusElement), the
		field's own focus included."""
		self.raise_for(button)
		if button == 0:
			self.focus(COMMENT)

	@nui.on("comment_change")
	def on_comment_change(self, value, linebreak):
		self._owner.commentSlot.typed(value)

	# --- the member page -------------------------------------------------------------------

	@nui.on("combo_press")
	def on_combo_press(self, line, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_combo(int(line))

	@nui.on("combo_pick")
	def on_combo_pick(self, grade, button):
		self.raise_for(button)
		if button == 0:
			self._owner._pick_combo(int(grade))

	@nui.on("general_press")
	def on_general_press(self, line, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_check(self._owner.pageWindow["MEMBER"].memberDict[int(line)][5])

	@nui.on("member_scroll")
	def on_member_scroll(self, value):
		self._owner._scroll_members(value)

	@nui.on("member_wheel")
	def on_member_wheel(self, delta):
		self._owner._wheel_members(delta)

	# --- the skill page ----------------------------------------------------------------------

	@nui.on("active_press")
	def on_active_press(self, index, button):
		self.raise_for(button)
		self._owner._skill_event("active", "press", int(index), button)

	@nui.on("active_release")
	def on_active_release(self, index, button):
		self._owner._skill_event("active", "release", int(index), button)

	@nui.on("active_over")
	def on_active_over(self, index):
		self._owner._skill_event("active", "over", int(index))

	@nui.on("active_out")
	def on_active_out(self, index):
		self._owner._skill_event("active", "out", int(index))

	@nui.on("passive_over")
	def on_passive_over(self, index):
		self._owner._skill_event("passive", "over", int(index))

	@nui.on("passive_out")
	def on_passive_out(self, index):
		self._owner._skill_event("passive", "out", int(index))

	@nui.on("affect_over")
	def on_affect_over(self, index):
		self._owner._skill_event("affect", "over", int(index))

	@nui.on("affect_out")
	def on_affect_out(self, index):
		self._owner._skill_event("affect", "out", int(index))

	@nui.on("plus_press")
	def on_plus_press(self, index, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_plus(int(index))

	@nui.on("heal_press")
	def on_heal_press(self, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press(self._owner.pageWindow["SKILL"].btnHealGSP)

	# --- the grade page ------------------------------------------------------------------------

	@nui.on("grade_name_press")
	def on_grade_name_press(self, number, button):
		self.raise_for(button)
		if button == 0:
			self._owner._press_check(self._owner.pageWindow["GRADE"].gradeDict[int(number)][0])

	@nui.on("auth_press")
	def on_auth_press(self, number, bit, button):
		self.raise_for(button)
		if button == 0 and int(bit) in AUTHORITY_BITS:
			column = 1 + AUTHORITY_BITS.index(int(bit))
			self._owner._press_check(self._owner.pageWindow["GRADE"].gradeDict[int(number)][column])


class _TitleBoardProxy(nui_proxies.BoardProxy):
	"""ui.BoardWithTitleBar: its title (SetTitleName) and title color."""

	def SetTitleColor(self, color):
		self.title_color = color


class GuildWindow(nui_facade.Facade, uiGuild.GuildWindow):
	"""uiGuild.GuildWindow on NovaUI (Interface.wndGuild)."""

	KEY = KEY
	BOARD = _GuildBoard

	def __init__(self):
		self.focusProxy = None
		self.nui_begin()
		try:
			uiGuild.GuildWindow.__init__(self)
			if self.demand is not None:
				self.focusProxy = nui_hud.FocusProxy(self._on_focus_lost, self._on_focus_gained)
			self.nui_end()
		except Exception:
			self.nui_discard()
			raise

	def nui_discard(self):
		proxy, self.focusProxy = getattr(self, "focusProxy", None), None
		if proxy is not None:
			proxy.destroy()
		nui_facade.Facade.nui_discard(self)

	def PLACE(self):
		"""The uiscript's place, the screen's corner (D21): Open does not
		center it."""
		return (0, 0)

	def nui_model(self):
		limits = self._limits
		rows, cells = limits.GUILD_SKILL_ROW, limits.GUILD_SKILL_ROW
		return {
			"page": "GUILD_INFO",
			"title": "",
			"tabs": [self._tab_entry(key, False, False, False) for key, _, _ in PAGES],
			"tab_art": "",
			"page_info": [], "page_board": [], "page_member": [], "page_base": [], "page_skill": [], "page_grade": [],
			"info": {"name": "", "master": "", "level": "", "cur_exp": "", "last_exp": "", "members": "", "avg_level": ""},
			"enemies": [""] * limits.GUILD_ENEMY_SLOTS,
			"mark_src": "",
			"mark_rect": "",
			"upload_mark_shown": False,
			"upload_symbol_shown": False,
			"declare_shown": False,
			"comments": [self._comment_entry(None, None, None) for _ in range(limits.GUILD_BOARD_LINES)],
			"comment_max": limits.GUILD_COMMENT_MAX_LEN - 1,
			"members": [self._member_entry(None) for _ in range(limits.GUILD_MEMBER_LINES)],
			"member_scroll": 0.0,
			"member_scroll_shown": False,
			"combo_line": -1,
			"combo_items": [],
			"skill_point": "",
			"points_art": "/" + uiScriptLocale.WINDOWS_PATH.strip("/") + "/label_uppt.sub",
			"gp_text": "",
			"gp_ratio": 0.0,
			"gp_legacy": 0.0,
			"passive_cells": [nui_slots.empty_cell(i) for i in range(cells)],
			"active_cells": [nui_slots.empty_cell(i) for i in range(cells)],
			"affect_cells": [nui_slots.empty_cell(i) for i in range(rows * 2)],
			"skill_cols": cells,
			"active_plus": [False] * cells,
			"passive_plus": [False] * cells,
			"grades": [self._grade_entry(n, None) for n in range(1, limits.GUILD_GRADE_COUNT + 1)],
			"base_rows": list(range(limits.GUILD_BUILDING_ROWS)),
			"base_columns": [{"name": RESOURCE_NAMES[i % len(RESOURCE_NAMES)]}
			                 for i in range(limits.GUILD_RESOURCE_COLUMNS)],
		}

	# --- the model from the proxies ----------------------------------------------------------

	@staticmethod
	def _tab_art(key):
		"""The locale's tab strip art of a page (guildwindow.py: GUILD_PATH +
		tab_<n>.sub), as a rooted store path."""
		index = [page for page, _, _ in PAGES].index(key) + 1
		return "/" + uiScriptLocale.GUILD_PATH.strip("/") + "/tab_%d.sub" % index

	def _tab_entry(self, key, enabled, down, shown):
		return {"key": key, "label": nui.plain_text(getattr(localeInfo, PAGE_TITLES[key], "")), "enabled": bool(enabled),
		        "down": bool(down), "art": self._tab_art(key), "shown": bool(shown)}

	@staticmethod
	def _comment_entry(notice, name, comment):
		if comment is None:
			return {"notice": False, "name": "", "short": "", "full": "", "long": False}
		return {"notice": bool(notice.shown), "name": name.GetText(), "short": comment.short, "full": comment.full,
		        "long": bool(comment.long)}

	@staticmethod
	def _member_entry(slots):
		if slots is None:
			return {"name": "", "grade": "", "job": "", "level": "", "offer": "", "general": False,
			        "combo_enabled": False}
		name, combo, job, level, offer, general = slots
		return {"name": name.GetText(), "grade": combo.text, "job": nui.plain_text(job.GetText()),
		        "level": nui.plain_text(level.GetText()), "offer": nui.plain_text(offer.GetText()),
		        "general": bool(general.checked), "combo_enabled": bool(combo.enabled)}

	@staticmethod
	def _grade_entry(number, slots):
		if slots is None:
			return {"number": number, "name": "", "add": False, "remove": False, "notice": False, "skill": False,
			        "enabled": number != 1}
		name, add, remove, notice, skill = slots
		return {"number": number, "name": name.text, "add": bool(add.checked), "remove": bool(remove.checked),
		        "notice": bool(notice.checked), "skill": bool(skill.checked), "enabled": bool(name.enabled)}

	def _sync(self):
		"""Every model key from the proxies (the board sets only what changed
		in the document)."""
		if not getattr(self, "pageWindow", None):
			return
		pages = self.pageWindow
		shown = [key for key, _, _ in PAGES if pages[key].IsShow()]
		current = shown[0] if shown else "GUILD_INFO"
		values = {
			"page": current,
			"title": nui.plain_text(self.board.title),
			"tabs": [self._tab_entry(key, self.tabButtonDict[key].enabled, self.tabButtonDict[key].down,
			                         self.tabDict[key].shown) for key, _, _ in PAGES],
			# The locale's tab strip art of the page whose image shows (one
			# shows at a time, SelectPage).
			"tab_art": next((self.tabDict[key].image for key, _, _ in PAGES if self.tabDict[key].shown), ""),
		}
		for key, model_key, _ in PAGES:
			values[model_key] = [1] if pages[key].IsShow() else []

		info = pages["GUILD_INFO"]
		values["info"] = {"name": info.nameSlot.GetText(), "master": info.masterNameSlot.GetText(),
		                  "level": nui.plain_text(info.guildLevelSlot.GetText()),
		                  "cur_exp": nui.plain_text(info.curExpSlot.GetText()),
		                  "last_exp": nui.plain_text(info.lastExpSlot.GetText()),
		                  "members": nui.plain_text(info.memberCountSlot.GetText()),
		                  "avg_level": nui.plain_text(info.levelAverageSlot.GetText())}
		values["enemies"] = [line.GetText() for line in self.enemyGuildNameList]
		values["mark_src"], values["mark_rect"] = self.largeMarkBox.mark()
		values["upload_mark_shown"] = bool(info.uploadMarkButton.shown)
		values["upload_symbol_shown"] = bool(info.uploadSymbolButton.shown)
		values["declare_shown"] = bool(info.declareWarButton.shown)

		board = pages["BOARD"]
		values["comments"] = [self._comment_entry(*board.boardDict[i]) for i in sorted(board.boardDict)]

		member = pages["MEMBER"]
		values["members"] = [self._member_entry(member.memberDict[line]) for line in sorted(member.memberDict)]
		values["member_scroll"] = float(member.scrollBar.GetPos())
		values["member_scroll_shown"] = bool(member.scrollBar.shown)
		open_line, items = -1, []
		for line in sorted(member.memberDict):
			combo = member.memberDict[line][1]
			if combo.open:
				open_line = line
				items = [{"grade": int(grade), "name": name} for grade, name in combo.items]
				break
		values["combo_line"] = open_line
		values["combo_items"] = items

		skill_page = pages["SKILL"]
		values["skill_point"] = nui.plain_text(skill_page.skillPoint.GetText())
		values["gp_text"] = nui.plain_text(skill_page.gpValue.GetText())
		current_point, max_point = guild.GetDragonPowerPoint()
		values["gp_ratio"] = min(1.0, max(0.0, float(current_point) / float(max(max_point, 1))))
		values["gp_legacy"] = min(1.0, max(0.0, skill_page.gpGauge.percent * GAUGE_ART / GAUGE_TRACK))
		values["passive_cells"] = skill_page.passiveSlot.cells()
		values["active_cells"] = skill_page.activeSlot.cells()
		values["affect_cells"] = skill_page.affectSlot.cells()
		values["active_plus"] = skill_page.activeSlot.plus()
		values["passive_plus"] = skill_page.passiveSlot.plus()

		grade = pages["GRADE"]
		values["grades"] = [self._grade_entry(number, grade.gradeDict[number]) for number in sorted(grade.gradeDict)]
		self.nui_set(**values)

	# --- the board's events -------------------------------------------------------------

	def _press(self, button):
		"""A legacy button's press: its event, then the board."""
		button.click()
		self._sync()

	def _press_tab(self, index):
		"""A tab: legacy's radio button (a button that is down, or disabled,
		takes no press), its event SelectPage(key)."""
		if not (0 <= index < len(PAGES)):
			return
		button = self.tabButtonDict[PAGES[index][0]]
		if button.down or not button.enabled:
			return
		button.Down()
		self._press(button)

	def _press_check(self, check):
		check.pressed()
		self._sync()

	def _press_combo(self, line):
		"""A grade combo box's press: its list opens or closes; one list is open
		at a time (D11)."""
		member = self.pageWindow["MEMBER"]
		combo = member.memberDict[line][1]
		for other in sorted(member.memberDict):
			if other != line:
				member.memberDict[other][1].CloseListBox()
		combo.pressed()
		self._sync()

	def _pick_combo(self, grade):
		member = self.pageWindow["MEMBER"]
		for line in sorted(member.memberDict):
			combo = member.memberDict[line][1]
			if combo.open:
				combo.picked(grade)
				break
		self._sync()

	def _scroll_members(self, value):
		try:
			value = min(max(float(value), 0.0), 1.0)
		except (TypeError, ValueError):
			return
		scroll = self.pageWindow["MEMBER"].scrollBar
		if abs(value - scroll.GetPos()) < SCROLL_STEP / 2.0:
			return
		scroll.moved(value)
		self._sync()

	def _wheel_members(self, delta):
		"""A wheel notch over the lines: one member line (RmlUi's sign:
		positive is down)."""
		scroll = self.pageWindow["MEMBER"].scrollBar
		count = guild.GetMemberCount()
		span = count - self._limits.GUILD_MEMBER_LINES
		if not scroll.shown or span <= 0 or not delta:
			return
		position = scroll.GetPos() + float(delta) * WHEEL_LINES / float(span)
		scroll.moved(min(max(position, 0.0), 1.0))
		self._sync()

	def _skill_event(self, grid, kind, index, button=0):
		events = self._skill_events[grid]
		if kind == "press":
			events.press(index, button)
		elif kind == "release":
			events.release(index, button)
		elif kind == "over":
			events.over(index)
		else:
			events.out(index)

	def _press_plus(self, index):
		"""A skill's "+": the slot window's pressed-button event with the slot
		(OnUpGuildSkill)."""
		slots = self.pageWindow["SKILL"].activeSlot
		if not (0 <= index < len(slots.slot_numbers)) or not slots.plus()[index]:
			return
		event = slots.handlers().get("pressed_button")
		if event:
			event(slots.slot_number(index))
		self._sync()

	def _comment_key(self, key):
		"""A key in the comment field: legacy's edit line's handlers. Enter is
		its OnIMEReturn (OnPostComment), F5 its OnKeyDown (a refresh), Escape
		its OnPressEscapeKey (nothing: legacy's edit line keeps it, so the
		window stays open); each is kept."""
		field = self.commentSlot
		if key in (nui.KEY_RETURN, nui.KEY_NUMPADENTER):
			field.fire_return()
			self._sync()
			return True
		if key == KEY_F5:
			field.fire_key(DIK_F5)
			return True
		if key == nui.KEY_ESCAPE:
			field.fire_escape()
			return True
		return None

	def _on_field(self, field, what):
		board = self.nui_board()
		if board is None or not board.is_visible():
			return
		if what == "text":
			board.set_value(field.field_id, field.text, caret="end")
		elif what == "focus":
			board.focus(field.field_id)

	def _value(self, field_id):
		board = self.nui_board()
		return board.get_value(field_id) if board is not None and board.is_visible() else None

	def _restore_board(self, board):
		nui_facade.Facade._restore_board(self, board)
		board.element_on(COMMENT, "keydown", board._on_comment_key)
		board.element_on(COMMENT, "focus", board._on_comment_focus)

	# --- the comment field's focus (as the whisper's: nui_whisper) -------------------------

	def _comment_focused(self):
		"""The field took NovaUI's focus: the window holds wndMgr's, as a
		focused legacy edit line would (nui_hud.FocusProxy), so a world press
		takes it back (game.py CheckFocus) and a legacy edit line that takes
		it gets the keys."""
		if self.focusProxy is not None:
			self.focusProxy.take()

	def _on_focus_lost(self):
		"""A legacy edit line (or the game window) took wndMgr's focus: the
		keys are its."""
		board = self.nui_board()
		if board is not None and board.is_visible():
			board.focus(PARK)

	def _on_focus_gained(self):
		"""wndMgr gave the focus back (the window that took it closed)."""
		board = self.nui_board()
		if board is not None and board.is_visible() and self._state.get("page") == "BOARD":
			board.focus(COMMENT)

	def _release_focus(self):
		if self.focusProxy is not None:
			self.focusProxy.release()

	# --- the loader (uiguild.py:804-932 and the six __Make*Page, on proxies) -------------------

	def _GuildWindow__LoadWindow(self):
		# The uiscript's style (guildwindow.py: "movable", "float").
		self.AddFlag("movable")
		self.AddFlag("float")
		limits = self._limits

		self.popupDialog = nui_form_proxies.MessageWindowProxy()
		self.changeGradeNameDialog = self._make_grade_name_dialog()
		self.pageWindow = dict((key, nui_form_proxies.PageWindowProxy(key, script)) for key, _, script in PAGES)

		self.board = _TitleBoardProxy(376, 356)
		self.pageName = dict((key, getattr(localeInfo, PAGE_TITLES[key])) for key, _, _ in PAGES)
		self.tabDict = dict((key, nui_proxies.ImageProxy(image=self._tab_art(key))) for key, _, _ in PAGES)
		self.tabButtonDict = dict((key, nui_proxies.ButtonProxy()) for key, _, _ in PAGES)

		## QuestionDialog
		self.popupMessage = self.popupDialog.GetChild("message")
		self.popupDialog.GetChild("accept").SetEvent(ui.__mem_func__(self.popupDialog.Hide))

		## ChangeGradeName
		self.changeGradeNameDialog.GetChild("AcceptButton").SetEvent(ui.__mem_func__(self.OnChangeGradeName))
		self.changeGradeNameDialog.GetChild("CancelButton").SetEvent(ui.__mem_func__(self.changeGradeNameDialog.Hide))
		self.changeGradeNameDialog.GetChild("Board").SetCloseEvent(ui.__mem_func__(self.changeGradeNameDialog.Hide))
		self.changeGradeNameDialog.gradeNameSlot = self.changeGradeNameDialog.GetChild("GradeNameValue")
		self.changeGradeNameDialog.gradeNameSlot.OnIMEReturn = ui.__mem_func__(self.OnChangeGradeName)
		self.changeGradeNameDialog.gradeNameSlot.OnPressEscapeKey = ui.__mem_func__(self.changeGradeNameDialog.Close)

		## Comment
		self.commentSlot = nui_form_proxies.FieldProxy(COMMENT, self._on_field)
		self.commentSlot.reader = lambda: self._value(COMMENT)
		self.commentSlot.SetMax(limits.GUILD_COMMENT_MAX_LEN - 1)
		self.commentSlot.OnIMEReturn = ui.__mem_func__(self.OnPostComment)
		self.commentSlot.OnKeyDown = lambda key, argSelf=self: argSelf.OnKeyDownInBoardPage(key)

		## RefreshButton
		self.pageWindow["BOARD"].refreshButton = nui_proxies.ButtonProxy()
		self.pageWindow["BOARD"].refreshButton.SetEvent(ui.__mem_func__(self.OnRefreshComments))

		## ScrollBar
		scrollBar = nui_form_proxies.ScrollProxy()
		scrollBar.SetScrollBarSize(270)
		scrollBar.SetScrollEvent(ui.__mem_func__(self.OnScrollMemberLine))
		self.pageWindow["MEMBER"].scrollBar = scrollBar

		self._make_info_page()
		self._make_board_page()
		self._make_member_page()
		self._make_base_info_page()
		self._make_skill_page()
		self._make_grade_page()

		for page in list(self.pageWindow.values()):
			page.UpdateRect()

		for key, btn in list(self.tabButtonDict.items()):
			btn.SetEvent(self.SelectPage, key)

		self.tabButtonDict["BASE_INFO"].Disable()

		if uiGuild.DISABLE_GUILD_SKILL:
			self.tabButtonDict["SKILL"].Disable()

		self.board.SetCloseEvent(ui.__mem_func__(self.Close))
		self.board.SetTitleColor(0xffffffff)
		self.SelectPage("GUILD_INFO")

		self.offerDialog = uiPickMoney.PickMoneyDialog()
		self.offerDialog.LoadDialog()
		self.offerDialog.SetMax(9)
		self.offerDialog.SetTitleName(localeInfo.GUILD_OFFER_EXP)
		self.offerDialog.SetAcceptEvent(ui.__mem_func__(self.OnOffer))

	def _make_grade_name_dialog(self):
		"""The NovaUI grade name dialog, or legacy's (its uiscript loaded, as
		legacy's loader does) where its document cannot load."""
		dialog = None
		try:
			dialog = nui_guild_grade_name.ChangeGradeNameDialog()
		except Exception as error:
			nui_windows.note_failure(KEY, "the grade name dialog could not be made (%s)" % type(error).__name__)
		if dialog is not None and dialog.nui_ready():
			return dialog
		if dialog is not None:
			dialog.nui_discard()
			nui_windows.note_failure(KEY, "the grade name dialog's document did not load")
		dialog = uiGuild.ChangeGradeNameDialog()
		ui.PythonScriptLoader().LoadScriptFile(dialog, "uiscript/changegradenamedialog.py")
		return dialog

	def _make_info_page(self):
		"""__MakeInfoPage (uiguild.py:934-989) on proxies; the left-to-right
		info page has no guild money row (2.1)."""
		page = self.pageWindow["GUILD_INFO"]
		page.nameSlot = nui_proxies.TextProxy()
		page.masterNameSlot = nui_proxies.TextProxy()
		page.guildLevelSlot = nui_proxies.TextProxy()
		page.curExpSlot = nui_proxies.TextProxy()
		page.lastExpSlot = nui_proxies.TextProxy()
		page.memberCountSlot = nui_proxies.TextProxy()
		page.levelAverageSlot = nui_proxies.TextProxy()
		page.uploadMarkButton = nui_proxies.ButtonProxy()
		page.uploadSymbolButton = nui_proxies.ButtonProxy()
		page.declareWarButton = nui_proxies.ButtonProxy()
		page.offerButton = nui_proxies.ButtonProxy()
		page.guildMoneySlot = None

		page.uploadMarkButton.SetEvent(ui.__mem_func__(self._GuildWindow__OnClickSelectGuildMarkButton))
		page.uploadSymbolButton.SetEvent(ui.__mem_func__(self._GuildWindow__OnClickSelectGuildSymbolButton))
		page.declareWarButton.SetEvent(ui.__mem_func__(self._GuildWindow__OnClickDeclareWarButton))
		page.offerButton.SetEvent(ui.__mem_func__(self._GuildWindow__OnClickOfferButton))

		empty = localeInfo.GUILD_INFO_ENEMY_GUILD_EMPTY
		self.enemyGuildNameList = [nui_proxies.TextProxy(text=empty) for _ in range(self._limits.GUILD_ENEMY_SLOTS)]

		self.largeMarkBox = nui_form_proxies.MarkProxy()
		self.largeMarkBox.AddFlag("not_pick")

		self.markSelectDialog = nui_windows.make("guild-mark", uiUploadMark.MarkSelectDialog,
		                                         "nui_guild_mark.MarkSelectDialog")
		self.markSelectDialog.SAFE_SetSelectEvent(self._GuildWindow__OnSelectMark)

		self.symbolSelectDialog = nui_windows.make("guild-mark", uiUploadMark.SymbolSelectDialog,
		                                           "nui_guild_mark.SymbolSelectDialog")
		self.symbolSelectDialog.SAFE_SetSelectEvent(self._GuildWindow__OnSelectSymbol)

	def _make_board_page(self):
		"""__MakeBoardPage (uiguild.py:992-1051): each line's notice mark,
		name and comment; a delete button per line and the post button."""
		page = self.pageWindow["BOARD"]
		page.boardDict = {}
		page.deleteButtons = []
		for i in range(self._limits.GUILD_BOARD_LINES):
			noticeMarkImage = nui_proxies.ImageProxy(image="d:/ymir work/ui/game/guild/notice_mark.sub")
			noticeMarkImage.Hide()
			deleteButton = nui_proxies.ButtonProxy()
			deleteButton.SetEvent(ui.__mem_func__(self.OnDeleteComment), i)
			page.deleteButtons.append(deleteButton)
			page.boardDict[i] = [noticeMarkImage, nui_proxies.TextProxy(), nui_form_proxies.CommentProxy()]
		page.postButton = nui_proxies.ButtonProxy()
		page.postButton.SetEvent(ui.__mem_func__(self.OnPostComment))

	def _make_member_page(self):
		"""__MakeMemberPage (uiguild.py:1053-1128): GUILD_MEMBER_LINES lines,
		each its name, grade combo box, job, level, offer and general check,
		keyed by legacy's line (line k at the k-th row from the top)."""
		page = self.pageWindow["MEMBER"]
		page.memberDict = {}
		for i in range(self._limits.GUILD_MEMBER_LINES):
			inverseLineIndex = self._limits.GUILD_MEMBER_LINES - i - 1
			gradeSlot = nui_form_proxies.ComboProxy(inverseLineIndex)
			gradeSlot.SetSize(61, 18)
			gradeSlot.SetEvent(lambda gradeNumber, lineIndex=inverseLineIndex, argSelf=self:
			                   argSelf.OnChangeMemberGrade(lineIndex, gradeNumber))
			gradeSlot.Show()
			event = lambda argSelf=self, argIndex=inverseLineIndex: argSelf.OnEnableGeneral(*(argIndex,))
			page.memberDict[inverseLineIndex] = [nui_proxies.TextProxy(), gradeSlot, nui_proxies.TextProxy(),
			                                     nui_proxies.TextProxy(), nui_proxies.TextProxy(),
			                                     nui_form_proxies.CheckProxy(event)]

	def _make_base_info_page(self):
		"""__MakeBaseInfoPage (uiguild.py:1130-1167): placeholders the document
		draws; legacy keeps no widget of them."""
		self.pageWindow["BASE_INFO"].buildingDataDict = {}

	def _make_skill_page(self):
		"""__MakeSkillPage (uiguild.py:1169-1223) on GuildSkillSlotProxys."""
		page = self.pageWindow["SKILL"]
		row = self._limits.GUILD_SKILL_ROW
		page.skillPoint = nui_proxies.TextProxy()
		page.passiveSlot = nui_form_proxies.GuildSkillSlotProxy(range(PASSIVE_START, PASSIVE_START + row), None,
		                                                         cols=row, rows=1)
		page.activeSlot = nui_form_proxies.GuildSkillSlotProxy(range(ACTIVE_START, ACTIVE_START + row), None,
		                                                        cols=row, rows=1)
		page.affectSlot = nui_form_proxies.GuildSkillSlotProxy(range(AFFECT_START, AFFECT_START + row * 2), None,
		                                                        cols=row, rows=2)
		page.gpGauge = nui_form_proxies.GaugeProxy()
		page.gpValue = nui_proxies.TextProxy()
		page.btnHealGSP = nui_proxies.ButtonProxy()

		page.activeSlot.SetSlotStyle(wndMgr.SLOT_STYLE_NONE)
		page.activeSlot.SetOverInItemEvent(lambda slotNumber, type=self.GUILD_SKILL_ACTIVE_SLOT: self.OverInItem(slotNumber, type))
		page.activeSlot.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		page.activeSlot.SetSelectItemSlotEvent(lambda slotNumber, type=self.GUILD_SKILL_ACTIVE_SLOT: self.OnPickUpGuildSkill(slotNumber, type))
		page.activeSlot.SetUnselectItemSlotEvent(lambda slotNumber, type=self.GUILD_SKILL_ACTIVE_SLOT: self.OnUseGuildSkill(slotNumber, type))
		page.activeSlot.SetPressedSlotButtonEvent(lambda slotNumber, type=self.GUILD_SKILL_ACTIVE_SLOT: self.OnUpGuildSkill(slotNumber, type))
		page.activeSlot.AppendSlotButton("d:/ymir work/ui/game/windows/btn_plus_up.sub",
		                                 "d:/ymir work/ui/game/windows/btn_plus_over.sub",
		                                 "d:/ymir work/ui/game/windows/btn_plus_down.sub")
		page.passiveSlot.SetSlotStyle(wndMgr.SLOT_STYLE_NONE)
		page.passiveSlot.SetOverInItemEvent(lambda slotNumber, type=self.GUILD_SKILL_PASSIVE_SLOT: self.OverInItem(slotNumber, type))
		page.passiveSlot.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		page.passiveSlot.SetPressedSlotButtonEvent(lambda slotNumber, type=self.GUILD_SKILL_PASSIVE_SLOT: self.OnUpGuildSkill(slotNumber, type))
		page.passiveSlot.AppendSlotButton("d:/ymir work/ui/game/windows/btn_plus_up.sub",
		                                  "d:/ymir work/ui/game/windows/btn_plus_over.sub",
		                                  "d:/ymir work/ui/game/windows/btn_plus_down.sub")
		page.affectSlot.SetSlotStyle(wndMgr.SLOT_STYLE_NONE)
		page.affectSlot.SetOverInItemEvent(lambda slotNumber, type=self.GUILD_SKILL_AFFECT_SLOT: self.OverInItem(slotNumber, type))
		page.affectSlot.SetOverOutItemEvent(ui.__mem_func__(self.OverOutItem))
		page.btnHealGSP.SetEvent(ui.__mem_func__(self._GuildWindow__OnOpenHealGSPBoard))

		self._skill_events = {
			"active": self.nui_events(nui_slots.LegacySlotEvents(page.activeSlot)),
			"passive": self.nui_events(nui_slots.LegacySlotEvents(page.passiveSlot)),
			"affect": self.nui_events(nui_slots.LegacySlotEvents(page.affectSlot)),
		}

		## Active
		import playerSettingModule
		for i in range(len(playerSettingModule.ACTIVE_GUILD_SKILL_INDEX_LIST)):
			slotIndex = page.activeSlot.GetStartIndex() + i
			skillIndex = playerSettingModule.ACTIVE_GUILD_SKILL_INDEX_LIST[i]

			page.activeSlot.SetSkillSlot(slotIndex, skillIndex, 0)
			page.activeSlot.SetCoverButton(slotIndex)
			page.activeSlot.RefreshSlot()
			guild.SetSkillIndex(slotIndex, len(playerSettingModule.PASSIVE_GUILD_SKILL_INDEX_LIST) + i)

	def _make_grade_page(self):
		"""__MakeGradePage (uiguild.py:1225-1298): each grade's editable name
		and four authority checks; grade 1's are disabled."""
		page = self.pageWindow["GRADE"]
		page.gradeDict = {}
		for i in range(self._limits.GUILD_GRADE_COUNT):
			index = i + 1
			gradeNameSlot = nui_form_proxies.EditableSlotProxy()
			gradeNameSlot.SetEvent(ui.__mem_func__(self.OnOpenChangeGradeName), index)
			checks = [nui_form_proxies.CheckProxy(lambda argSelf=self, argIndex=index, argAuthority=bit:
			                                      argSelf.OnCheckAuthority(*(argIndex, argAuthority)))
			          for bit in AUTHORITY_BITS]
			page.gradeDict[index] = [gradeNameSlot] + checks

		masterSlotList = page.gradeDict[1]
		for slot in masterSlotList:
			slot.Disable()

	# --- what NovaUI changes (P16 spec 5.9.3) -----------------------------------------

	def Show(self):
		nui_facade.Facade.Show(self)
		self._sync()

	def Hide(self):
		nui_facade.Facade.Hide(self)
		if not self.IsShow():
			self._release_focus()

	def Destroy(self):
		"""The NovaUI dialogs the window made go with it (legacy's Destroy only
		drops them), then the facade's and legacy's."""
		for name in ("changeGradeNameDialog", "markSelectDialog", "symbolSelectDialog"):
			dialog = getattr(self, name, None)
			discard = getattr(dialog, "nui_discard", None)
			if discard is not None:
				discard()
		nui_facade.Facade.Destroy(self)

	def Open(self):
		uiGuild.GuildWindow.Open(self)
		self._sync()

	def SelectPage(self, arg):
		uiGuild.GuildWindow.SelectPage(self, arg)
		self._sync()
		# The comment field goes with the board page: its hold on wndMgr's
		# focus too, or the game window would not get the keys back.
		if arg != "BOARD":
			self._release_focus()

	def DeleteGuild(self):
		uiGuild.GuildWindow.DeleteGuild(self)
		self._sync()

	def RefreshGuildInfoPage(self):
		uiGuild.GuildWindow.RefreshGuildInfoPage(self)
		self._sync()

	def RefreshGuildBoardPage(self):
		uiGuild.GuildWindow.RefreshGuildBoardPage(self)
		self._sync()

	def RefreshGuildMemberPage(self):
		uiGuild.GuildWindow.RefreshGuildMemberPage(self)
		self._sync()

	def RefreshGuildMemberPageMemberList(self):
		uiGuild.GuildWindow.RefreshGuildMemberPageMemberList(self)
		self._sync()

	def RefreshGuildMemberPageGradeComboBox(self):
		uiGuild.GuildWindow.RefreshGuildMemberPageGradeComboBox(self)
		self._sync()

	def RefreshGuildSkillPage(self):
		"""Legacy's, then the slot windows' refresh: legacy's slot windows draw
		what they were told, the proxies build their cells at RefreshSlot."""
		uiGuild.GuildWindow.RefreshGuildSkillPage(self)
		self._refresh_skill_slots()
		self._sync()

	def RefreshGuildGradePage(self):
		uiGuild.GuildWindow.RefreshGuildGradePage(self)
		self._sync()

	def OnUseSkill(self, slotNumber, coolTime):
		uiGuild.GuildWindow.OnUseSkill(self, slotNumber, coolTime)
		self._refresh_skill_slots()
		self._sync()

	def OnStartGuildWar(self, guildSelf, guildOpp):
		uiGuild.GuildWindow.OnStartGuildWar(self, guildSelf, guildOpp)
		self._sync()

	def OnEndGuildWar(self, guildSelf, guildOpp):
		uiGuild.GuildWindow.OnEndGuildWar(self, guildSelf, guildOpp)
		self._sync()

	def OnScrollMemberLine(self):
		uiGuild.GuildWindow.OnScrollMemberLine(self)
		self._sync()

	def OnPostComment(self):
		result = uiGuild.GuildWindow.OnPostComment(self)
		self._sync()
		return result

	def _refresh_skill_slots(self):
		if self.isLoaded == 0:
			return
		page = self.pageWindow["SKILL"]
		for slots in (page.passiveSlot, page.activeSlot, page.affectSlot):
			slots.RefreshSlot()
