## The dungeon manager and its drops panel (NOVA-25; OLD root/uiTimerWindow.py, ENABLE_TIMER_WINDOW
## and _DUNGEON_DROP_INFO_).
##
## The data: locale/common/dungeon_info.txt (OLD's format: index, boss, min and max level, group
## rule, cooldown, entry ticket; one row per dungeon the server's dungeon_mob_info.json lists, by
## the same index) and locale/<lang>/dungeon_desc/<index>.txt (the description, English when the
## language has none).
##
## The window (F6, Interface.OpenTimerWindow) lists the dungeons two per row, each with its
## re-entry clock: the server sends "SetQuestTime <index> <seconds left>" for every dungeon still
## on cooldown at login, then "QuestTimeReady", and again for a dungeon whose cooldown a boss kill
## sets (OLD char.cpp RefreshQuestTimers). A row reads "Ready To Fight!" or the minutes left
## (rounded up); a row can be hidden (for this session, and until the player's level passes the
## level it was hidden at) and "Show Hidden" brings them back. A press on a row shows that
## dungeon: its entry ticket (with the item tooltip), its level band, group rule, cooldown and
## description, and its boss's name. Teleport sends "/warp_dungeon <index>"; the three ranking
## buttons open the ranking window (uidungeonrank) and send "/rank_dungeon <type> <index>"; the
## drops button opens the drops panel and asks the server once for the dungeon's drop list
## (net.RequestDungeonDrop; GC::DUNGEON_DROP rows reach game.BINARY_UpdateDungeonDrop). With the
## notice box checked, the dungeon's row announces itself for three seconds when its clock ends.
##
## What differs from OLD:
## - the 3D boss preview uses the client's modelpreview module (NOVA-137); on a client without
##   it the preview frame names the boss;
## - OLD's art (ui/dungeon_manager/*) and its monster faces are not in NEW's packs: the rows are
##   bars in OLD's sizes, available and on cooldown in two colors, and the drops rows carry no face;
## - the hidden dungeons and the notice choices last for the session (NEW has no cfg store);
## - the chest preview of a drop (ChestItemPopup, OLD's chest drop info) is the chest-drop
##   port's, not this one's, and the Meley ranking button (index 99, disabled in OLD) is left out;
## - OLD bugs fixed: hiding a dungeon rebuilt every row and lost every clock, and cleared the
##   "times loaded" flag, so no clock ran again until the next login (the clocks are kept per
##   dungeon in the window now); a drop's rarity used an integer division and left exactly 30%
##   and 70% out of every band.

import re
import time

import app
import ui
import net
import item
import player
import wndMgr
import nonplayer
import localeInfo
import uiScriptLocale
import nui_windows

DEBUG = False

# Key everything by the real dungeon index (the first column of dungeon_info.txt).
DESCRIPTION = {}       # idx -> [boss, min, max, group rule (str), cooldown (s), entry ticket, [desc lines]]
ALLOW_NOTICE = {}      # idx -> 0/1
HIDDEN_DUNGEONS = {}   # idx -> the level it was hidden at (0: shown)
SESSION_HIDDEN = {}    # idx -> 0/1
ORDERED_INDICES = []   # events (index 150 and above) first, then the others

# What the server sent this session (OLD constInfo.DUNGEON_TIMER_LOADED and DUNGEON_DROP).
TIMER_STATE = {"loaded": False}
## DUNGEON_DROP = { dungeon index : { mob vnum : {"type": mob type, "items": [(vnum, count, chance)]} } }
DUNGEON_DROP = {}

INFO_FILE = "locale/common/dungeon_info.txt"
NOTICE_SECONDS = 3


def log(msg):
	if DEBUG:
		print("[TimerWindow] %s" % msg)


## The boss's preview (the client's modelpreview module, NOVA-137; absent on a client without
## it, then the frame only names the boss, as before).
BOSS_PREVIEW = "dungeon_boss"
BOSS_VIEW_RECT = (4, 24, 117, 140)


def model_preview():
	try:
		import modelpreview
	except ImportError:
		return None
	return modelpreview


def _mins_ceil(seconds):
	"""Rounded up, so 61 s show 2 minutes and any time left shows at least 1."""
	if seconds <= 0:
		return 0
	return (int(seconds) + 59) // 60


def _fmt_mins_label(mins):
	return (localeInfo.TIMERWINDOW_MINUTE if mins == 1 else localeInfo.TIMERWINDOW_MINUTES) % mins


def get_current_level():
	return int(player.GetStatus(player.LEVEL))


def is_event_index(idx):
	return int(idx) >= 150


_TITLE_CACHE = {}


def get_title(idx):
	"""localeInfo.TIMERWINDOW_DUNGEON_TITLE_<idx>, else the idx-th name of
	TIMERWINDOW_DUNGEON_TITLES, else "Dungeon <idx>" (OLD's order)."""
	if idx in _TITLE_CACHE:
		return _TITLE_CACHE[idx]
	value = localeInfo.__dict__.get("TIMERWINDOW_DUNGEON_TITLE_%d" % int(idx))
	if not (isinstance(value, str) and value):
		titles = [title.strip() for title in localeInfo.TIMERWINDOW_DUNGEON_TITLES.split(",")]
		if 0 <= int(idx) < len(titles) and titles[int(idx)]:
			value = titles[int(idx)]
		else:
			value = "Dungeon %d" % int(idx)
	_TITLE_CACHE[idx] = value
	return value


def group_text(raw):
	"""dungeon_info.txt's group rule: OLD writes it as an emoji tag (|E~/xmark.tga|e no group,
	|E~/checkmark.tga|e a group), shown here as words; any other text as it is."""
	text = str(raw).strip()
	if "xmark" in text:
		return localeInfo.TIMERWINDOW_GROUP_NO
	if "checkmark" in text:
		return localeInfo.TIMERWINDOW_GROUP_YES
	return text


def level_band(min_level, max_level):
	"""TIMERWINDOW_REQUIRED_LEVEL ("Min. Level %d \\nMax. Level %d") on one line: the locale files
	hold OLD's escaped "\\n", which NEW's text lines draw as written."""
	return (localeInfo.TIMERWINDOW_REQUIRED_LEVEL % (int(min_level), int(max_level))).replace("\\n", " ").replace("  ", " ")


def is_user_hidden(idx):
	if SESSION_HIDDEN.get(idx, 0):
		return True
	threshold = int(HIDDEN_DUNGEONS.get(idx, 0))
	return threshold > 0 and get_current_level() >= threshold


def ensure_flag_defaults(idx):
	ALLOW_NOTICE.setdefault(idx, 0)
	HIDDEN_DUNGEONS.setdefault(idx, 0)
	SESSION_HIDDEN.setdefault(idx, 0)


def is_hidden_for_current_view(idx):
	"""Hidden by the player, or an event dungeon (150 and above) outside its level band."""
	if is_user_hidden(idx):
		return True
	if is_event_index(idx):
		data = DESCRIPTION.get(idx)
		if data is not None:
			level = get_current_level()
			if level < int(data[1]) or level > int(data[2]):
				return True
	return False


def iter_indices_sorted():
	events = sorted(i for i in DESCRIPTION if is_event_index(i))
	normals = sorted(i for i in DESCRIPTION if not is_event_index(i))
	return events + normals


def parse_cooldown_to_seconds(val):
	"""300, "300", "5 Mins", "5m", "1 hour", "2h", "45 secs", "45s": seconds."""
	if isinstance(val, int):
		return val
	text = str(val).strip().lower()
	if text.isdigit():
		return int(text)
	text = text.replace("minutes", "min").replace("minute", "min").replace("mins", "min")
	text = text.replace("hours", "hour").replace("hrs", "hour").replace("hr", "hour")
	text = text.replace("seconds", "sec").replace("secs", "sec")
	match = re.match(r"^\s*(\d+)\s*(hour|h|min|m|sec|s)\s*$", text)
	if match:
		number, unit = int(match.group(1)), match.group(2)
		if unit in ("hour", "h"):
			return number * 3600
		if unit in ("min", "m"):
			return number * 60
		return number
	raise ValueError("Unrecognized duration: %r" % val)


def parse_boss_field(raw_boss):
	"""The boss: a vnum ("1095"), or OLD's race:armor:weapon:hair:sash:bodyeffect for a
	player-shaped boss; the first number is the race or vnum. Six numbers."""
	raw_boss = str(raw_boss).strip()
	result = [0, 0, 0, 0, 0, 0]
	for i, part in enumerate(raw_boss.split(":")[:6]):
		try:
			result[i] = int(part.strip())
		except ValueError:
			result[i] = 0
	return result


def read_lines(path):
	handle = pack_open(path, "r")
	try:
		return [line.rstrip("\r\n") for line in handle.readlines()]
	finally:
		close = getattr(handle, "close", None)
		if callable(close):
			close()


def parse_dungeon_info(lines):
	"""dungeon_info.txt's rows ({idx: [boss, min, max, group, cooldown, ticket, []]}, errors);
	"#" starts a comment; seven or more fields carry the index, six take the next one (OLD)."""
	rows = {}
	auto_index = 0
	errors = 0
	for raw in lines:
		raw = raw.lstrip("\ufeff")
		if not raw or raw.startswith("#"):
			continue
		info = raw.split("\t") if "\t" in raw else re.split(r"\s+", raw)
		if len(info) < 6:
			errors += 1
			continue
		if len(info) >= 7:
			try:
				idx = int(info[0])
			except ValueError:
				errors += 1
				continue
			payload = info[1:7]
		else:
			idx = auto_index
			payload = info[:6]
		try:
			row = [parse_boss_field(payload[0]), int(payload[1]), int(payload[2]), str(payload[3]),
			       parse_cooldown_to_seconds(payload[4]), int(payload[5]), []]
		except (ValueError, IndexError):
			errors += 1
			continue
		rows[idx] = row
		auto_index += 1
	return rows, errors


def load_dungeon_info():
	global ORDERED_INDICES
	DESCRIPTION.clear()
	rows, errors = parse_dungeon_info(read_lines(INFO_FILE))
	if not rows:
		raise RuntimeError("No valid rows loaded from dungeon_info.txt (errors=%d)" % errors)
	DESCRIPTION.update(rows)
	for idx in DESCRIPTION:
		ensure_flag_defaults(idx)
	ORDERED_INDICES = iter_indices_sorted()
	log("Loaded %d dungeons (errors=%d)" % (len(rows), errors))


def load_dungeon_desc():
	for idx in DESCRIPTION:
		lines = []
		for path in ("%s/dungeon_desc/%d.txt" % (app.GetLocalePath(), idx), "locale/en/dungeon_desc/%d.txt" % idx):
			try:
				lines = read_lines(path)
				break
			except Exception:
				continue
		DESCRIPTION[idx][-1] = lines


def extract_font_tag(s):
	"""A leading "@Family Name:12b " tag: (the text after it, "Family Name:12b"); "@@" is a
	literal "@" (OLD TimerWindow.__extract_font_tag)."""
	if not s:
		return s, None
	if s.startswith("@@"):
		return s[1:], None
	if s[0] != "@":
		return s, None
	buf = s[1:]
	colon = buf.find(":")
	if colon == -1:
		return s, None
	family = buf[:colon].strip()
	rest = buf[colon + 1:]
	end = 0
	while end < len(rest) and not rest[end].isspace():
		end += 1
	size_flags = rest[:end]
	digits = 0
	while digits < len(size_flags) and size_flags[digits].isdigit():
		digits += 1
	if digits == 0:
		return s, None
	return rest[end:].lstrip(), "%s:%s%s" % (family, size_flags[:digits], size_flags[digits:])


# A description line's color by its first character (OLD): "#" a heading, "$" a note, "%" a hint.
DESC_COLORS = {"#": (0.741, 0.403, 0.447), "$": (0.741, 0.721, 0.403), "%": (0.403, 0.439, 0.741)}
DESC_DEFAULT_COLOR = (0.741, 0.592, 0.403)


def desc_line(line):
	"""A description line: (text, rgb, font or None)."""
	text, font = extract_font_tag(line)
	color = DESC_DEFAULT_COLOR
	if text and text[0] in DESC_COLORS:
		color = DESC_COLORS[text[0]]
		text = text[1:]
	return text, color, font


def add_drop(dungeonIndex, mobVnum, mobType, itemVnum, itemCount, itemChance):
	"""One GC::DUNGEON_DROP row (OLD game.BINARY_UpdateDungeonDrop)."""
	mobs = DUNGEON_DROP.setdefault(dungeonIndex, {})
	if mobVnum not in mobs:
		mobs[mobVnum] = {"type": mobType, "items": []}
	mobs[mobVnum]["items"].append((itemVnum, itemCount, itemChance))


def reset_session():
	"""A new game phase: nothing the server sent before counts."""
	TIMER_STATE["loaded"] = False
	DUNGEON_DROP.clear()


# =============================================================================

OPEN_NOTICE_COUNT = [0]


class TimerNotice(ui.Bar):
	"""A dungeon's row announcing that it is ready (OLD TimerNotice): a dark box near the top of
	the screen for three seconds, stacked under the others."""

	WIDTH = 150
	HEIGHT = 50

	def __init__(self, index):
		ui.Bar.__init__(self, "TOP_MOST")
		self.index = index
		self.timeOpen = 0
		self.SetSize(self.WIDTH, self.HEIGHT)
		self.SetColor(0x80000000)
		self.AddFlag("not_pick")

		self.title = ui.TextLine()
		self.title.SetParent(self)
		self.title.SetPosition(0, 10)
		self.title.SetWindowHorizontalAlignCenter()
		self.title.SetHorizontalAlignCenter()
		self.title.SetText(get_title(index))
		self.title.Show()

		self.text = ui.TextLine()
		self.text.SetParent(self)
		self.text.SetPosition(0, 28)
		self.text.SetWindowHorizontalAlignCenter()
		self.text.SetHorizontalAlignCenter()
		self.text.SetText(localeInfo.TIMERWINDOW_AVAILABLE)
		self.text.Show()
		self.Hide()

	def __del__(self):
		ui.Bar.__del__(self)

	def Open(self):
		if self.IsShow():
			return
		self.timeOpen = time.time()
		self.SetPosition((wndMgr.GetScreenWidth() - self.WIDTH) // 2, 150 + 50 * OPEN_NOTICE_COUNT[0])
		OPEN_NOTICE_COUNT[0] += 1
		self.Show()
		self.SetTop()

	def OnUpdate(self):
		if time.time() > self.timeOpen + NOTICE_SECONDS:
			self.Hide()
			OPEN_NOTICE_COUNT[0] = max(0, OPEN_NOTICE_COUNT[0] - 1)

	def Destroy(self):
		self.title = None
		self.text = None


class TimerBoard(ui.Window):
	"""A dungeon's row in the list (OLD TimerBoard): its name, "Ready To Fight!" or the minutes
	left, and the hide button; a press shows the dungeon."""

	WIDTH = 287
	HEIGHT = 36
	AVAILABLE = 0x80284a28
	EVENT_AVAILABLE = 0x80283c5a
	UNAVAILABLE = 0x80502020

	def __init__(self, parent, index, main_window):
		ui.Window.__init__(self)
		self.SetParent(parent)
		self.index = index
		self.main_window = main_window
		self.is_event = is_event_index(index)
		self.SetSize(self.WIDTH, self.HEIGHT)
		self.__Build()
		self.Show()

	def __del__(self):
		ui.Window.__del__(self)

	def __Build(self):
		self.bar = ui.Bar()
		self.bar.SetParent(self)
		self.bar.SetSize(self.WIDTH, self.HEIGHT)
		self.bar.AddFlag("not_pick")
		self.bar.Show()

		self.textLine = ui.MakeTextLine(self)
		self.textLine.SetPosition(0, -7)
		self.textLine.SetText(get_title(self.index))

		self.textLine3 = ui.MakeTextLine(self)
		self.textLine3.SetPosition(0, 9)

		self.hideBtn = ui.Button()
		self.hideBtn.SetParent(self)
		self.hideBtn.SetPosition(self.WIDTH - 20, 2)
		self.hideBtn.SetUpVisual("d:/ymir work/ui/public/close_button_01.sub")
		self.hideBtn.SetOverVisual("d:/ymir work/ui/public/close_button_02.sub")
		self.hideBtn.SetDownVisual("d:/ymir work/ui/public/close_button_03.sub")
		self.hideBtn.SAFE_SetEvent(self.main_window.HideDungeon, self.index)
		self.hideBtn.SetToolTipText(uiScriptLocale.OPTION_TARGET_BOARD_NO_VIEW, -25, 0)
		self.hideBtn.Show()
		self.UpdateTime(app.GetGlobalTimeStamp())

	def UpdateTime(self, now):
		remain = self.main_window.GetEndTime(self.index) - now if TIMER_STATE["loaded"] else 0
		if remain > 0:
			self.textLine3.SetText(_fmt_mins_label(_mins_ceil(remain)))
			self.bar.SetColor(self.UNAVAILABLE)
		else:
			self.textLine3.SetText(localeInfo.TIMERWINDOW_READY_TO_FIGHT)
			self.bar.SetColor(self.EVENT_AVAILABLE if self.is_event else self.AVAILABLE)

	def OnMouseLeftButtonDown(self):
		self.main_window.SetDescription(self.index)

	def Destroy(self):
		self.bar = None
		self.textLine = None
		self.textLine3 = None
		self.hideBtn = None


class TimerWindow(ui.ScriptWindow):
	LEFT_X = 0
	RIGHT_X = 291
	ROW_PAIR_STEP = 38
	MIN_CONTENT_H = 140
	PADDING_BOTTOM = 10
	BTN_H = 28
	BTN_MARGIN_TOP = 12
	DESC_STEP = 14

	def __init__(self):
		ui.ScriptWindow.__init__(self)
		self.load_error = None
		try:
			load_dungeon_info()
			load_dungeon_desc()
		except Exception as e:
			self.load_error = str(e)
			log("Initialization failed: %s" % self.load_error)
		self.interface = None
		self.tooltip = None
		self.index = 0
		self.isLoaded = False
		self.boards = []
		self.visible_indices = []
		self.descLines = []
		self.endTimes = {}      # idx -> the global time its cooldown ends
		self.announced = {}     # idx -> the clock's end already announced
		self.notices = {}       # idx -> its TimerNotice
		self.wndDrops = None
		self.bossView = None    # the render target of the boss's preview, None without one
		self.bossRace = 0       # the race the preview shows, 0 for none

	def __del__(self):
		ui.ScriptWindow.__del__(self)

	def LoadWindow(self):
		if self.isLoaded:
			return
		self.isLoaded = True
		self.__LoadWindow()
		self.wndDrops = nui_windows.make("dungeon-drops", MobDropPopup, "nui_dungeon_drops.MobDropPopup", self.interface)

		self.board.SetCloseEvent(ui.__mem_func__(self.Close))
		self.teleport.SetEvent(ui.__mem_func__(self.Teleport))
		self.btnDungeonDrops.SetEvent(ui.__mem_func__(self.openDungeonDrops))
		self.btnTimeRank.SetEvent(ui.__mem_func__(self.onClickTimeRank))
		self.btnOverAllRank.SetEvent(ui.__mem_func__(self.onClickOverAllRank))
		self.btnDamageRank.SetEvent(ui.__mem_func__(self.onClickDamageRank))
		self.showHiddenBtn.SetEvent(ui.__mem_func__(self.UnhideAll))
		self.noticeBtn.SetEvent(ui.__mem_func__(self.__OnNoticeCheck), "ON_CHECK")
		self.noticeBtn.SetEvent(ui.__mem_func__(self.__OnNoticeUncheck), "ON_UNCHECK")

		self.RebuildBoards()
		if self.load_error:
			self.emptyLabel.SetText(localeInfo.TIMERWINDOW_LOAD_ERROR % self.load_error)
			self.emptyLabel.Show()

	def __LoadWindow(self):
		pyScrLoader = ui.PythonScriptLoader()
		pyScrLoader.LoadScriptFile(self, "uiscript/timerwindow.py")

		self.board = self.GetChild("board")
		self.itemSlot = self.GetChild("ItemSlot")
		self.teleport = self.GetChild("Teleport")
		self.btnDungeonDrops = self.GetChild("DungeonDrops")
		self.btnTimeRank = self.GetChild("TimeRank")
		self.btnOverAllRank = self.GetChild("OverAllRank")
		self.btnDamageRank = self.GetChild("DamageRank")
		self.info_bg = self.GetChild("info_bg")
		self.BossName = self.GetChild("bossname")
		self.text1 = self.GetChild("text1")
		self.text2 = self.GetChild("text2")
		self.text3 = self.GetChild("text3")
		self.text4 = self.GetChild("text4")

		self.dungeonsWindow = ui.Window()
		self.dungeonsWindow.SetSize(574, self.MIN_CONTENT_H)
		self.dungeonsWindow.Show()

		self.showHiddenBtn = ui.Button()
		self.showHiddenBtn.SetParent(self.dungeonsWindow)
		self.showHiddenBtn.SetUpVisual("d:/ymir work/ui/public/large_button_01.sub")
		self.showHiddenBtn.SetOverVisual("d:/ymir work/ui/public/large_button_02.sub")
		self.showHiddenBtn.SetDownVisual("d:/ymir work/ui/public/large_button_03.sub")
		self.showHiddenBtn.SetText(uiScriptLocale.DUNGEON_MANAGER_SHOW_HIDDEN)
		self.showHiddenBtn.Hide()

		self.boardScrollableWindow = ui.ScrollWindow(574, 147)
		self.boardScrollableWindow.SetParent(self)
		self.boardScrollableWindow.SetPosition(21, 73)
		self.boardScrollableWindow.SetContentWindow(self.dungeonsWindow)
		self.boardScrollableWindow.FitWidth(574)
		self.boardScrollableWindow.Show()

		self.descWindow = ui.Window()
		self.descWindow.SetSize(420, 1)
		self.descWindow.Show()
		self.descScrollableWindow = ui.ScrollWindow(420, 116)
		self.descScrollableWindow.SetParent(self.info_bg)
		self.descScrollableWindow.SetPosition(8, 6)
		self.descScrollableWindow.SetContentWindow(self.descWindow)
		self.descScrollableWindow.FitWidth(420)
		self.descScrollableWindow.Show()

		self.textLine = ui.TextLine()
		self.textLine.SetParent(self.GetChild("RenderBG"))
		self.textLine.SetPosition(0, 8)
		self.textLine.SetWindowHorizontalAlignCenter()
		self.textLine.SetHorizontalAlignCenter()
		self.textLine.Show()

		self.emptyLabel = ui.TextLine()
		self.emptyLabel.SetParent(self)
		self.emptyLabel.SetPosition(0, 120)
		self.emptyLabel.SetWindowHorizontalAlignCenter()
		self.emptyLabel.SetHorizontalAlignCenter()
		self.emptyLabel.SetPackedFontColor(0xffe06666)
		self.emptyLabel.Hide()

		self.noticeBtn = ui.CheckBox()
		self.noticeBtn.SetParent(self)
		self.noticeBtn.SetPosition(24, 442)
		self.noticeBtn.SetTextInfo(uiScriptLocale.DUNGEON_MANAGER_NOTICE)
		self.noticeBtn.Show()

		self.bossView = self.__MakeBossView()

	def __MakeBossView(self):
		"""The boss preview's render target over the boss frame; None on a client without
		render targets."""
		if model_preview() is None or not hasattr(ui, "RenderTarget") or not ui.RenderTarget.IsAvailable():
			return None
		view = ui.RenderTarget()
		view.SetParent(self.GetChild("RenderBG"))
		view.AddFlag("not_pick")
		(x, y, width, height) = BOSS_VIEW_RECT
		view.SetPosition(x, y)
		view.SetSize(width, height)
		view.SetRenderTarget(BOSS_PREVIEW)
		return view

	def __ShowBossModel(self, race):
		"""The chosen dungeon's boss, turning; hidden for race 0 or without the preview."""
		race = int(race)
		preview = model_preview()
		if preview is None or self.bossView is None or race == 0:
			self.__HideBossModel()
			return
		if race != self.bossRace:
			preview.Select(BOSS_PREVIEW, race)
			self.bossRace = race
		preview.Show(BOSS_PREVIEW, True)
		self.bossView.Show()

	def __HideBossModel(self):
		preview = model_preview()
		if preview is not None:
			preview.Show(BOSS_PREVIEW, False)
		if self.bossView is not None:
			self.bossView.Hide()
		self.bossRace = 0

	def __MakeBoard(self, idx):
		return TimerBoard(self.dungeonsWindow, idx, self)

	def __MakeDescLine(self):
		textLine = ui.TextLine()
		textLine.SetParent(self.descWindow)
		textLine.Show()
		return textLine

	def __MakeNotice(self, idx):
		return TimerNotice(idx)

	def __OnNoticeCheck(self):
		self.ToogleNotice(1)

	def __OnNoticeUncheck(self):
		self.ToogleNotice(0)

	def ToogleNotice(self, arg):
		ALLOW_NOTICE[self.index] = int(arg)

	def AnyHidden(self):
		return any(is_user_hidden(idx) for idx in DESCRIPTION)

	def RebuildBoards(self):
		for board in self.boards:
			board.Hide()
			board.Destroy()
		self.boards = []
		self.visible_indices = []

		row_counter = 0
		for idx in iter_indices_sorted():
			if is_hidden_for_current_view(idx):
				continue
			board = self.__MakeBoard(idx)
			y = (row_counter // 2) * self.ROW_PAIR_STEP
			board.SetPosition(self.LEFT_X if row_counter % 2 == 0 else self.RIGHT_X, y)
			self.boards.append(board)
			self.visible_indices.append(idx)
			row_counter += 1

		boards_height = ((row_counter + 1) // 2) * self.ROW_PAIR_STEP
		if self.AnyHidden():
			btn_y = boards_height + self.BTN_MARGIN_TOP
			self.showHiddenBtn.SetPosition(21, btn_y)
			self.showHiddenBtn.Show()
			content_h = btn_y + self.BTN_H + self.PADDING_BOTTOM
		else:
			self.showHiddenBtn.Hide()
			content_h = boards_height + self.PADDING_BOTTOM
		self.dungeonsWindow.SetSize(574, max(self.MIN_CONTENT_H, content_h))
		self.boardScrollableWindow.OnContentWindowSizeChange()

		if (self.index not in DESCRIPTION) or is_hidden_for_current_view(self.index):
			if self.visible_indices:
				self.SetDescription(self.visible_indices[0])

		if self.visible_indices:
			self.emptyLabel.Hide()
		else:
			self.emptyLabel.SetText(localeInfo.TIMERWINDOW_ALL_HIDDEN if DESCRIPTION else localeInfo.TIMERWINDOW_EMPTY)
			self.emptyLabel.Show()

	def HideDungeon(self, idx):
		if idx not in DESCRIPTION:
			return
		SESSION_HIDDEN[idx] = 1
		level = max(1, get_current_level())
		if HIDDEN_DUNGEONS.get(idx, 0) == 0:
			HIDDEN_DUNGEONS[idx] = level
		else:
			HIDDEN_DUNGEONS[idx] = min(int(HIDDEN_DUNGEONS[idx]), level)
		self.RebuildBoards()

	def UnhideAll(self):
		for idx in DESCRIPTION:
			HIDDEN_DUNGEONS[idx] = 0
			SESSION_HIDDEN[idx] = 0
		self.RebuildBoards()

	def SetDescription(self, index):
		if index not in DESCRIPTION:
			return
		self.index = index
		data = DESCRIPTION[index]
		self.BossName.SetText(nonplayer.GetMonsterName(data[0][0]))
		self.__ShowBossModel(data[0][0])

		title, font = extract_font_tag(get_title(index))
		if font:
			self.textLine.SetFontName(font)
		self.textLine.SetText(title)

		if int(data[5]) == 0:
			self.itemSlot.SetOverInItemEvent(None)
			self.itemSlot.SetOverOutItemEvent(None)
			self.itemSlot.ClearSlot(0)
		else:
			self.itemSlot.SetOverInItemEvent(ui.__mem_func__(self.__OnOverInItem))
			self.itemSlot.SetOverOutItemEvent(ui.__mem_func__(self.__OnOverOutItem))
			self.itemSlot.SetItemSlot(0, int(data[5]))
		self.itemSlot.RefreshSlot()

		self.text1.SetText(level_band(data[1], data[2]))
		self.text2.SetText(localeInfo.TIMERWINDOW_GROUP_REQUEST + ":  " + group_text(data[3]))
		self.text4.SetText(localeInfo.TIMERWINDOW_ENTRY_TICKET)
		self.text3.SetText(localeInfo.TIMERWINDOW_COOLDOWN + ":  " + _fmt_mins_label(_mins_ceil(int(data[4]))))

		self.__ClearList()
		for line in data[6]:
			text, color, font = desc_line(line)
			textLine = self.__MakeDescLine()
			textLine.SetFontColor(color[0], color[1], color[2])
			if font:
				textLine.SetFontName(font)
			textLine.SetPosition(0, len(self.descLines) * self.DESC_STEP)
			textLine.SetText(text)
			self.descLines.append(textLine)
		self.descWindow.SetSize(420, max(1, len(self.descLines) * self.DESC_STEP))
		self.descScrollableWindow.OnContentWindowSizeChange()
		self.descScrollableWindow.ScrollToStart()

		self.noticeBtn.SetCheckStatus(ALLOW_NOTICE.get(index, 0))

	def __ClearList(self):
		for line in self.descLines:
			line.Hide()
		self.descLines = []

	def QuestTimeReady(self):
		"""The server's "QuestTimeReady": every clock it sent counts from now on."""
		TIMER_STATE["loaded"] = True
		now = app.GetGlobalTimeStamp()
		for board in self.boards:
			board.UpdateTime(now)

	def GetEndTime(self, index):
		return self.endTimes.get(index, 0)

	def SetTimeLeft(self, index, time_):
		"""The server's "SetQuestTime <index> <seconds left>": kept per dungeon, so a hidden row
		and a rebuilt list keep their clocks (OLD lost them)."""
		if index not in DESCRIPTION:
			return
		self.endTimes[index] = app.GetGlobalTimeStamp() + int(time_)
		self.announced[index] = False
		for board in self.boards:
			if board.index == index:
				board.UpdateTime(app.GetGlobalTimeStamp())

	def BindInterface(self, interface):
		self.interface = interface

	def SetToolTip(self, tooltip):
		self.tooltip = tooltip
		if self.tooltip:
			self.tooltip.Hide()

	def __OnOverInItem(self, slotIndex):
		if self.tooltip:
			self.tooltip.SetItemToolTip(int(DESCRIPTION[self.index][5]))

	def __OnOverOutItem(self):
		if self.tooltip:
			self.tooltip.HideToolTip()

	def Teleport(self):
		net.SendChatPacket("/warp_dungeon %d" % self.index)
		self.Close()

	def openDungeonDrops(self):
		if self.index not in DUNGEON_DROP:
			net.RequestDungeonDrop(self.index)
		self.wndDrops.Open(self.index)

	def __OpenRank(self, rank_type):
		self.interface.OpenDungeonRank()
		net.SendChatPacket("/rank_dungeon %d %d" % (rank_type, self.index))

	def onClickTimeRank(self):
		self.__OpenRank(0)

	def onClickOverAllRank(self):
		self.__OpenRank(1)

	def onClickDamageRank(self):
		self.__OpenRank(2)

	def refreshMobList(self):
		if self.wndDrops and self.wndDrops.IsShow():
			self.wndDrops.RefreshMobList()

	def Open(self):
		target = None
		for idx in iter_indices_sorted():
			if not is_hidden_for_current_view(idx):
				target = idx
				break
		if target is not None:
			self.SetDescription(target)
		else:
			self.emptyLabel.SetText(localeInfo.TIMERWINDOW_ALL_HIDDEN if DESCRIPTION else localeInfo.TIMERWINDOW_EMPTY)
			self.emptyLabel.Show()
		self.Show()
		self.SetTop()

	def Close(self):
		self.Hide()

	def Hide(self):
		self.__HideBossModel()
		ui.ScriptWindow.Hide(self)

	def Show(self):
		if self.index in DESCRIPTION and self.bossRace == 0:
			self.__ShowBossModel(DESCRIPTION[self.index][0][0])
		ui.ScriptWindow.Show(self)

	def UpdateTime(self):
		"""Every frame (game.OnUpdate through Interface.UpdateTimer): each row's clock, and the
		notice of a checked dungeon whose clock ended (OLD TimerBoard.UpdateTime)."""
		if not TIMER_STATE["loaded"]:
			return
		now = app.GetGlobalTimeStamp()
		for board in self.boards:
			board.UpdateTime(now)
		for idx, end in self.endTimes.items():
			if end <= now and not self.announced.get(idx, True):
				self.announced[idx] = True
				if ALLOW_NOTICE.get(idx, 0):
					notice = self.notices.get(idx)
					if notice is None:
						notice = self.notices[idx] = self.__MakeNotice(idx)
					notice.Open()

	def OnScrollWheel(self, length):
		if self.info_bg.IsIn():
			return self.descScrollableWindow.OnRunMouseWheel(length)
		return self.boardScrollableWindow.OnRunMouseWheel(length)

	def OnPressEscapeKey(self):
		self.Close()
		return True

	def Destroy(self):
		self.Hide()
		self.ClearDictionary()
		for board in self.boards:
			board.Destroy()
		self.boards = []
		for notice in self.notices.values():
			notice.Hide()
			notice.Destroy()
		self.notices = {}
		self.__ClearList()
		preview = model_preview()
		if preview is not None:
			preview.Clear(BOSS_PREVIEW)
		self.bossView = None
		self.board = None
		self.itemSlot = None
		self.teleport = None
		self.info_bg = None
		self.noticeBtn = None
		self.interface = None
		self.tooltip = None
		self.dungeonsWindow = None
		self.boardScrollableWindow = None
		self.descScrollableWindow = None
		if self.wndDrops:
			self.wndDrops.Destroy()
			self.wndDrops = None


# =============================================================================
# The drops panel
# =============================================================================

# A row's colors by its mob type (OLD COLOR_TABLE's middles: mob, boss, stone).
ROW_COLORS = {0: 0xc0214344, 1: 0xc0481d48, 2: 0xc09f2234}
# OLD's RARITY: its band's text and color.
RARITY_COLORS = {1: 0xff9830f0, 2: 0xff30b3f0, 3: 0xff30f0b3}


def rarity_of(chance):
	"""The band of a drop's chance (the server's value, a percent times 10000): 3 above 70%,
	2 from 30% to 70%, else 1. OLD divided as integers first and left exactly 30% and 70% out
	of every band but "rare"."""
	percent = float(chance) / 10000.0
	if percent > 70:
		return 3
	if percent >= 30:
		return 2
	return 1


def rarity_text(band):
	return {1: localeInfo.TIMERWINDOW_DROP_RARE, 2: localeInfo.TIMERWINDOW_DROP_COMMON,
	        3: localeInfo.TIMERWINDOW_DROP_GUARANTEED}[band]


def item_line(vnum, count):
	"""A drop's line, "<count>x <name>" (OLD); the item stays selected."""
	item.SelectItem(vnum)
	return "%dx %s" % (int(count), item.GetItemName())


def mob_type(value):
	return value if value in ROW_COLORS else 0


class MobDropPopup(ui.BoardWithTitleBar):
	"""The dungeon's drops (OLD MobDropPopup): its mobs, then a mob's items, each with its count
	and its chance's band. A press on a mob lists its items; the header row's press goes back."""

	WIDTH = 320
	HEIGHT = 400
	ROW_WIDTH = 290
	MOB_ROW_HEIGHT = 53
	MOB_ROW_STEP = 54
	ITEM_ROW_HEIGHT = 65
	ITEM_ROW_STEP = 66

	class Row(ui.Window):
		def __init__(self, parentWindow, vnum, count=0, chance=0, mtype=0, isHeader=False, isItem=False):
			ui.Window.__init__(self)
			self.parentWindow = parentWindow
			self.vnum = vnum
			self.mtype = mob_type(mtype)
			self.isHeader = isHeader
			self.isItem = isItem
			height = MobDropPopup.ITEM_ROW_HEIGHT if isItem else MobDropPopup.MOB_ROW_HEIGHT
			self.SetSize(MobDropPopup.ROW_WIDTH, height)
			self.bar = ui.Bar()
			self.bar.SetParent(self)
			self.bar.SetSize(MobDropPopup.ROW_WIDTH, height)
			self.bar.SetColor(ROW_COLORS[self.mtype])
			self.bar.AddFlag("not_pick")
			self.bar.Show()
			if isItem:
				self.itemCount = count
				self.rarity = rarity_of(chance)
				self.__InitItemElements()
			else:
				self.__InitMobElements()

		def __del__(self):
			ui.Window.__del__(self)

		def __InitItemElements(self):
			itemText = item_line(self.vnum, self.itemCount)
			(width, height) = item.GetItemSize()
			itemSlot = ui.SlotWindow()
			itemSlot.SetParent(self)
			itemSlot.SetSize(32, height * 32)
			itemSlot.SetWindowVerticalAlignCenter()
			itemSlot.SetPosition(20, 0)
			itemSlot.AppendSlot(0, 0, 0, 32, height * 32)
			itemSlot.SetItemSlot(0, self.vnum)
			itemSlot.Show()
			self.itemSlot = itemSlot

			itemName = ui.TextLine()
			itemName.SetParent(self)
			itemName.SetPosition(0, 22)
			itemName.SetWindowHorizontalAlignCenter()
			itemName.SetHorizontalAlignCenter()
			itemName.SetPackedFontColor(0xffe8b478)
			itemName.SetText(itemText)
			itemName.Show()
			self.itemName = itemName

			rarityLabel = ui.TextLine()
			rarityLabel.SetParent(self)
			rarityLabel.SetPosition(0, 40)
			rarityLabel.SetWindowHorizontalAlignCenter()
			rarityLabel.SetHorizontalAlignCenter()
			rarityLabel.SetPackedFontColor(RARITY_COLORS[self.rarity])
			rarityLabel.SetText(rarity_text(self.rarity))
			rarityLabel.Show()
			self.rarityLabel = rarityLabel

		def __InitMobElements(self):
			expandButton = ui.Button()
			expandButton.SetParent(self)
			expandButton.SetPosition(46, 0)
			expandButton.SetWindowVerticalAlignCenter()
			expandButton.SetUpVisual("d:/ymir work/ui/public/xlarge_thin_button_01.sub")
			expandButton.SetOverVisual("d:/ymir work/ui/public/xlarge_thin_button_02.sub")
			expandButton.SetDownVisual("d:/ymir work/ui/public/xlarge_thin_button_03.sub")
			expandButton.SetText(nonplayer.GetMonsterName(self.vnum))
			if self.isHeader:
				expandButton.SAFE_SetEvent(self.parentWindow.RefreshMobList)
			else:
				expandButton.SAFE_SetEvent(self.parentWindow.RefreshItemList, self.vnum)
			expandButton.Show()
			self.expandButton = expandButton

		def Update(self, vnum, mtype):
			self.vnum = vnum
			self.mtype = mob_type(mtype)
			self.bar.SetColor(ROW_COLORS[self.mtype])
			self.expandButton.SetText(nonplayer.GetMonsterName(self.vnum))

		def Destroy(self):
			self.parentWindow = None
			self.bar = None
			self.itemSlot = None
			self.itemName = None
			self.rarityLabel = None
			self.expandButton = None

	def __init__(self, interface):
		self.__InitBoard()
		self.interface = interface
		self.index = 0
		self.mobRows = []
		self.itemRows = []
		self.SetSize(self.WIDTH, self.HEIGHT)
		self.SetPosition((wndMgr.GetScreenWidth() - self.WIDTH) // 2, (wndMgr.GetScreenHeight() - self.HEIGHT) // 2)
		self.AddFlag("movable")
		self.AddFlag("float")
		self.__LoadWindow()

	def __del__(self):
		ui.BoardWithTitleBar.__del__(self)

	def __InitBoard(self):
		ui.BoardWithTitleBar.__init__(self)

	def __LoadWindow(self):
		self.SetTitleName(localeInfo.TIMERWINDOW_DROP_TITLE)
		self.SetCloseEvent(ui.__mem_func__(self.Hide))

		infoLabel = ui.TextLine()
		infoLabel.SetParent(self)
		infoLabel.SetPosition(0, 38)
		infoLabel.SetOutline()
		infoLabel.SetWindowHorizontalAlignCenter()
		infoLabel.SetHorizontalAlignCenter()
		infoLabel.SetPackedFontColor(0xffe8b478)
		infoLabel.Show()
		self.infoLabel = infoLabel

		self.mobList = ui.Window()
		self.mobList.SetSize(self.ROW_WIDTH, 1)
		self.mobList.Show()
		self.mobScrollableWindow = ui.ScrollWindow(self.ROW_WIDTH, 312)
		self.mobScrollableWindow.SetParent(self)
		self.mobScrollableWindow.SetPosition(12, 75)
		self.mobScrollableWindow.SetContentWindow(self.mobList)
		self.mobScrollableWindow.FitWidth(self.ROW_WIDTH)
		self.mobScrollableWindow.Show()

		header = self.Row(self, vnum=0, isHeader=True)
		header.SetParent(self)
		header.SetPosition(12, 72)
		header.Hide()
		self.header = header

		self.itemList = ui.Window()
		self.itemList.SetSize(self.ROW_WIDTH, 1)
		self.itemList.Show()
		self.itemScrollableWindow = ui.ScrollWindow(self.ROW_WIDTH, 258)
		self.itemScrollableWindow.SetParent(self)
		self.itemScrollableWindow.SetPosition(12, 133)
		self.itemScrollableWindow.SetContentWindow(self.itemList)
		self.itemScrollableWindow.FitWidth(self.ROW_WIDTH)
		self.itemScrollableWindow.Hide()

	def __MakeRow(self, parent, vnum, count=0, chance=0, mtype=0, isItem=False):
		row = self.Row(self, vnum, count, chance, mtype, isItem=isItem)
		row.SetParent(parent)
		row.Show()
		return row

	def __ClearRows(self, rows):
		for row in rows:
			row.Hide()
			row.Destroy()
		del rows[:]

	def OnScrollWheel(self, length):
		if self.itemScrollableWindow.IsShow():
			return self.itemScrollableWindow.OnRunMouseWheel(length)
		return self.mobScrollableWindow.OnRunMouseWheel(length)

	def Open(self, index):
		self.Show()
		self.SetTop()
		self.Update(index)

	def Update(self, index):
		self.index = index
		self.RefreshMobList()

	def RefreshMobList(self):
		"""The dungeon's mobs, in the order the server sent them (OLD)."""
		self.infoLabel.SetText(localeInfo.TIMERWINDOW_DROP_LIST % get_title(self.index))
		self.__ClearRows(self.mobRows)
		self.itemScrollableWindow.Hide()
		self.header.Hide()
		self.mobScrollableWindow.Show()
		for vnum, mob in DUNGEON_DROP.get(self.index, {}).items():
			row = self.__MakeRow(self.mobList, vnum, mtype=mob["type"])
			row.SetPosition(0, len(self.mobRows) * self.MOB_ROW_STEP)
			self.mobRows.append(row)
		self.mobList.SetSize(self.ROW_WIDTH, max(1, len(self.mobRows) * self.MOB_ROW_STEP))
		self.mobScrollableWindow.OnContentWindowSizeChange()
		self.mobScrollableWindow.ScrollToStart()

	def RefreshItemList(self, vnum):
		"""A mob's items, under the header row that names it."""
		mobs = DUNGEON_DROP.get(self.index, {})
		if vnum not in mobs:
			return
		mtype = mobs[vnum]["type"]
		self.__ClearRows(self.itemRows)
		for itemVnum, count, chance in mobs[vnum]["items"]:
			row = self.__MakeRow(self.itemList, itemVnum, count, chance, mtype, isItem=True)
			row.SetPosition(0, len(self.itemRows) * self.ITEM_ROW_STEP)
			self.itemRows.append(row)
		self.mobScrollableWindow.Hide()
		self.header.Update(vnum, mtype)
		self.header.Show()
		self.itemList.SetSize(self.ROW_WIDTH, max(1, len(self.itemRows) * self.ITEM_ROW_STEP))
		self.itemScrollableWindow.Show()
		self.itemScrollableWindow.OnContentWindowSizeChange()
		self.itemScrollableWindow.ScrollToStart()

	def Destroy(self):
		self.Hide()
		self.__ClearRows(self.mobRows)
		self.__ClearRows(self.itemRows)
		if self.header:
			self.header.Destroy()
		self.header = None
		self.infoLabel = None
		self.interface = None
		self.mobScrollableWindow = None
		self.itemScrollableWindow = None
		self.index = 0

	def OnPressEscapeKey(self):
		self.Hide()
		return True
