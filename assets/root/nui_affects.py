"""NovaUI affect icons (nui/windows/affects/affects.rml).

While the "affects" window flag is on, GameWindow.__init__ makes AffectShower
below through nui_windows.make() instead of uiAffectShower.AffectShower: the
facade of the legacy class, which game.py and the C++ callbacks behind it
(ClearAffects, SetAffect, ResetAffect, BINARY_NEW_AddAffect and the rest)
call as they call the legacy one. Its document is AffectBoard.

The logic is uiaffectshower.py's (the MR-10, MR-12, MR-16 and MR-17 fixes
included), read from the legacy module rather than copied: the affect table
(_AFFECT_TEMPLATE), the mall offset, the forced 0 durations, the item and
gold bonus values, the classic affect durations kept until their icon
exists, the unclocked affects and the item names of the infinite ones. What
the legacy class did every frame happens without Python: an affect's
remaining time is a nui-countdown in its tooltip, from the end written once
(nui.now() plus the duration), and the tooltips open on :hover. The two
values that change without an event, an auto potion's remainder and the
dragon soul decks' shortest remaining time, are read once per hover
(icon_over), where legacy read them every frame.

Every icon is an entry of the model's `icons` list, in the legacy order:
the lover's heart while shown, the horse, then the affects in the order
they came. The affect tooltips are NovaUI tooltips (spec D18): a title and
a line, or the name alone under the icon (the legacy text line, `label`)."""

import weakref

import app
import chr
import item
import localeInfo
import player
import skill

import nui
import nui_hud
import uiAffectShower

DOCUMENT = "nui/windows/affects/affects.rml"
LOVER_KEY = -10
HORSE_KEY = -11

_Legacy = uiAffectShower.AffectShower
_LOVE_FILES = uiAffectShower.LovePointImage.FILE_DICT
_LOVE_PATH = uiAffectShower.LovePointImage.FILE_PATH
_HORSE_FILES = uiAffectShower.HorseImage.FILE_DICT
_INFINITE_ITEMS = uiAffectShower.AffectImage.INFINITE_AFFECT_ITEM_VNUM

_live = weakref.WeakSet()  # the facades a locale change refreshes


def _keep(owner):
	try:
		return weakref.proxy(owner)
	except TypeError:
		return owner


def _locale(name):
	"""localeInfo.<name> as legacy reads it: a string, or the function an
	SA or SNA entry is; None when it is missing."""
	return getattr(localeInfo, name, None)


def _text(value):
	return nui.plain_text(value) if value else ""


def _auto_potions():
	return (chr.NEW_AFFECT_AUTO_HP_RECOVERY, chr.NEW_AFFECT_AUTO_SP_RECOVERY)


def _dragon_souls():
	return (chr.NEW_AFFECT_DRAGON_SOUL_DECK1, chr.NEW_AFFECT_DRAGON_SOUL_DECK2)


def _skill_name(affect, name):
	"""The skill's name for a skill affect (player.AffectIndexToSkillIndex),
	else `name`."""
	skill_index = player.AffectIndexToSkillIndex(affect)
	if 0 != skill_index:
		return skill.GetSkillName(skill_index)
	return name


def _on_locale_reload():
	for facade in list(_live):
		facade.RefreshLocale()


class AffectBoard(nui.Window):
	"""The affects' document and model; it reports hovers to its owner."""

	DOCUMENT = DOCUMENT
	MODEL = "affects"

	def __init__(self, owner):
		self._owner = _keep(owner)
		nui.Window.__init__(self)

	def initial_model(self):
		return {"icons": [], "open_key": -1}

	@nui.on("icon_over")
	def on_icon_over(self, key):
		self._owner.nui_icon_over(key)


class AffectShower(object):
	"""uiAffectShower.AffectShower on NovaUI (GameWindow.affectShower)."""

	NUI_FACADE = True

	MALL_DESC_IDX_START = _Legacy.MALL_DESC_IDX_START
	IMAGE_STEP = _Legacy.IMAGE_STEP
	AFFECT_MAX_NUM = _Legacy.AFFECT_MAX_NUM
	INFINITE_AFFECT_DURATION = _Legacy.INFINITE_AFFECT_DURATION

	def __init__(self):
		nui_hud.take_over("affects", self)
		self._nui_discarded = False
		self.board = None
		self.serverPlayTime = 0
		self.clientPlayTime = 0
		self.affects = {}       # affect -> its record, in the order they came
		self.pending = {}       # classic affect bit -> a duration that came before its icon
		self.horse = None       # {"image", "lines"} while a horse state shows
		self.lover = None       # {"name", "point", "shown"}
		self.dsTimeCache = {}   # (slot, vnum) -> {"remainSec", "endTime"}, as AffectImage keeps it
		if not nui_hud.has_engine():
			return
		try:
			self.board = AffectBoard(self)
		except Exception:
			self.nui_discard()
			raise
		_live.add(self)
		# The legacy window shows itself when it is made.
		self.Show()

	def nui_ready(self):
		return self.board is not None and bool(self.board._doc) and nui_hud.has_engine()

	def nui_discard(self):
		self._nui_discarded = True
		_live.discard(self)
		board, self.board = self.board, None
		if board is not None:
			board.destroy()
		nui_hud.forget("affects", self)

	def Destroy(self):
		self.nui_discard()

	def Show(self):
		if self.board is not None:
			self.board.show()

	def Hide(self):
		if self.board is not None:
			self.board.hide()

	def IsShow(self):
		return self.board is not None and self.board.is_visible()

	# --- the affect table ---------------------------------------------------------

	@staticmethod
	def _data(affect):
		"""(the description entry as localeInfo holds it, the image) of an
		affect of the legacy table, or None."""
		template = _Legacy._AFFECT_TEMPLATE.get(affect)
		if template is None:
			return None
		attribute, image = template
		return _locale(attribute), image

	def _describe(self, record):
		"""A non-skill affect's description: the entry called with the value
		(legacy description(float(value))), or the auto potion's format."""
		data = self._data(record["affect"])
		if data is None:
			return None
		description = data[0]
		if record["affect"] in _auto_potions():
			return description
		if callable(description):
			return description(float(record["value"]))
		return description

	# --- the callbacks -----------------------------------------------------------

	def ClearAllAffects(self):
		self.horse = None
		self.lover = None
		self.affects = {}
		self.pending = {}
		self._arrange()

	def ClearAffects(self):
		"""On death: the skill affects go, the others stay."""
		self.affects = dict((key, record) for key, record in self.affects.items() if not record["skill"])
		self.pending = {}
		self._arrange()

	def BINARY_NEW_AddAffect(self, type, pointIdx, value, duration, affFlag=0):
		if type < 500:
			# A classic affect's duration (MR-16): affFlag is the server's
			# 1-based AFF_* value, the client's chr.AFFECT_* is 0-based.
			if 0 < duration <= self.INFINITE_AFFECT_DURATION and affFlag > 0:
				bit = affFlag - 1
				if self._data(bit) is not None:
					if bit in self.affects:
						self._apply_classic_duration(bit, duration)
						self._arrange()
					else:
						self.pending[bit] = duration
			return

		if type == chr.NEW_AFFECT_MALL:
			affect = self.MALL_DESC_IDX_START + pointIdx
		else:
			affect = type
		if affect in self.affects:
			return
		data = self._data(affect)
		if data is None:
			return

		if affect in (chr.NEW_AFFECT_NO_DEATH_PENALTY, chr.NEW_AFFECT_SKILL_BOOK_BONUS, chr.NEW_AFFECT_AUTO_SP_RECOVERY,
		              chr.NEW_AFFECT_AUTO_HP_RECOVERY, chr.NEW_AFFECT_SKILL_BOOK_NO_DELAY):
			duration = 0
		if pointIdx == player.POINT_MALL_ITEMBONUS or pointIdx == player.POINT_MALL_GOLDBONUS:
			value = 1 + float(value) / 100.0

		record = {"affect": affect, "image": data[1], "skill": False, "value": value,
		          "small": affect not in _dragon_souls(), "clocked": True, "end": 0.0,
		          "title": "", "line": ""}
		record["description"] = self._describe(record)
		if duration > 0:
			record["end"] = nui.now() + duration
		if affect in (getattr(chr, "NEW_AFFECT_EXP_BONUS_EURO_FREE", None),
		              getattr(chr, "NEW_AFFECT_EXP_BONUS_EURO_FREE_UNDER_15", None)) \
				or self.INFINITE_AFFECT_DURATION < duration:
			record["clocked"] = False
		self.affects[affect] = record
		self._refresh_hover_values(record)
		self._arrange()

	def BINARY_NEW_RemoveAffect(self, type, pointIdx):
		if type == chr.NEW_AFFECT_MALL:
			affect = self.MALL_DESC_IDX_START + pointIdx
		else:
			affect = type
		self._remove(affect)
		self._arrange()

	def SetAffect(self, affect):
		self._append_skill_affect(affect)
		self._arrange()

	def ResetAffect(self, affect):
		self._remove(affect)
		self._arrange()

	def SetLoverInfo(self, name, lovePoint):
		# A new heart starts hidden, as the legacy image does until ShowLoverState.
		self.lover = {"name": name, "point": lovePoint, "shown": False}
		self._arrange()

	def ShowLoverState(self):
		if self.lover:
			self.lover["shown"] = True
			self._arrange()

	def HideLoverState(self):
		if self.lover:
			self.lover["shown"] = False
			self._arrange()

	def ClearLoverState(self):
		self.lover = None
		self._arrange()

	def OnUpdateLovePoint(self, lovePoint):
		if self.lover:
			self.lover["point"] = lovePoint
			self._arrange()

	def SetHorseState(self, level, health, battery):
		if level == 0:
			self.horse = None
		else:
			self.horse = self._horse_state(level, health, battery)
		# MR-17: the icons move after a horse state change.
		self._arrange()

	def SetPlayTime(self, playTime):
		self.serverPlayTime = playTime
		self.clientPlayTime = app.GetTime()

	def RefreshLocale(self):
		"""Names and descriptions in the current locale. Legacy rebuilt the
		skill names but left a non-skill description as the unformatted
		entry; this formats it again with the affect's value."""
		for affect, record in self.affects.items():
			if record["skill"]:
				data = self._data(affect)
				if data is not None:
					record["name"] = _skill_name(affect, data[0])
					if record.get("description") is not None:
						record["description"] = record["name"]
			else:
				record["description"] = self._describe(record)
				self._refresh_hover_values(record)
		self._arrange()

	# --- legacy internals -----------------------------------------------------------

	def _append_skill_affect(self, affect):
		if affect in self.affects:
			return
		data = self._data(affect)
		if data is None:
			return
		record = {"affect": affect, "image": data[1], "skill": True, "value": None, "small": True,
		          "clocked": True, "end": 0.0, "name": _skill_name(affect, data[0]), "description": None,
		          "title": "", "line": ""}
		self.affects[affect] = record
		# MR-16: a duration that came before the icon.
		if affect in self.pending:
			self._apply_classic_duration(affect, self.pending.pop(affect))

	def _apply_classic_duration(self, bit, duration):
		record = self.affects.get(bit)
		data = self._data(bit)
		if not record or data is None:
			return
		record["name"] = _skill_name(bit, data[0])
		record["description"] = record["name"]
		record["end"] = nui.now() + duration if duration > 0 else 0.0

	def _remove(self, affect):
		self.affects.pop(affect, None)

	def _horse_state(self, level, health, battery):
		"""HorseImage.SetState: the grade, health and rest lines and the art
		by health and battery."""
		lines = []
		state = {"image": "", "lines": lines}
		if level > 0:
			try:
				grade = (level - 1) // 10 + 1 if level else 0
				lines.append(localeInfo.LEVEL_LIST[int(grade)])
			except IndexError:
				print(("HorseImage.SetState(level=%d, health=%d, battery=%d) - Unknown Index" % (level, health, battery)))
				return state
			try:
				health_name = localeInfo.HEALTH_LIST[health]
				if len(health_name) > 0:
					lines.append(health_name)
			except IndexError:
				print(("HorseImage.SetState(level=%d, health=%d, battery=%d) - Unknown Index" % (level, health, battery)))
				return state
			if health > 0 and battery == 0:
				lines.append(localeInfo.NEEFD_REST)
			image = _HORSE_FILES.get(health * 10 + battery)
			if image is None:
				print(("HorseImage.SetState(level=%d, health=%d, battery=%d) - KeyError" % (level, health, battery)))
			else:
				state["image"] = image
		return state

	def _love_image(self, point):
		"""LovePointImage's art by love point. Legacy divides with / and so
		looks up a fraction for most points (and draws 00.dds, which does not
		exist); the grade is the whole number it meant."""
		point = min(100, max(0, point))
		grade = 0 if point == 0 else point // 25 + 1
		return _LOVE_FILES.get(grade, _LOVE_PATH + "00.dds")

	def _dragon_soul_min_remain(self, affect):
		"""AffectImage.__GetDragonSoulMinRemainSec: the deck's shortest
		remaining time in seconds, or None."""
		deck = 0 if affect == chr.NEW_AFFECT_DRAGON_SOUL_DECK1 else 1
		now = app.GetGlobalTimeStamp()
		min_remain = None
		for i in range(6):
			slot = deck * player.DRAGON_SOUL_EQUIPMENT_FIRST_SIZE + (player.DRAGON_SOUL_EQUIPMENT_SLOT_START + i)
			vnum = player.GetItemIndex(slot)
			if vnum == 0:
				continue
			item.SelectItem(vnum)
			remain = None
			for j in range(item.LIMIT_MAX_NUM):
				(limit_type, limit_value) = item.GetLimit(j)
				if item.LIMIT_REAL_TIME == limit_type or item.LIMIT_REAL_TIME_START_FIRST_USE == limit_type:
					remain = player.GetItemMetinSocket(player.INVENTORY, slot, 0) - now
					break
				if item.LIMIT_TIMER_BASED_ON_WEAR == limit_type:
					raw = player.GetItemMetinSocket(player.INVENTORY, slot, 0)
					key = (slot, vnum)
					cache = self.dsTimeCache.get(key)
					if cache and cache["remainSec"] == raw:
						remain = cache["endTime"] - now
					else:
						end = now + raw
						self.dsTimeCache[key] = {"remainSec": raw, "endTime": end}
						remain = end - now
					break
			if remain is None or remain <= 0:
				continue
			if min_remain is None or remain < min_remain:
				min_remain = remain
		return min_remain

	def _refresh_hover_values(self, record):
		"""What legacy recomputed every frame while hovered: an auto potion's
		title and remainder, a dragon soul deck's shortest time."""
		affect = record["affect"]
		if affect in _auto_potions():
			potion = player.AUTO_POTION_TYPE_HP if affect == chr.NEW_AFFECT_AUTO_HP_RECOVERY else player.AUTO_POTION_TYPE_SP
			is_activated, current, total, slot = player.GetAutoPotionInfo(potion)
			try:
				percent = (float(current) / total) * 100.0
			except Exception:
				percent = 100.0
			name = None
			if slot >= 0:
				vnum = player.GetItemIndex(slot)
				if vnum:
					item.SelectItem(vnum)
					name = item.GetItemName()
			if name:
				record["title"] = name
			elif potion == player.AUTO_POTION_TYPE_HP:
				record["title"] = localeInfo.TOOLTIP_AUTO_POTION_HP
			else:
				record["title"] = localeInfo.TOOLTIP_AUTO_POTION_SP
			description = record.get("description")
			try:
				record["line"] = description % percent if description else ""
			except (TypeError, ValueError):
				record["line"] = description or ""
		elif affect in _dragon_souls():
			remain = self._dragon_soul_min_remain(affect)
			record["end"] = nui.now() + remain if remain is not None else 0.0
		elif record["clocked"] and record["end"] <= 0 and record.get("description") and not record["skill"]:
			# MR-16: an infinite affect's title is its item's name.
			vnum = _INFINITE_ITEMS.get(affect)
			if vnum:
				item.SelectItem(vnum)
				record["title"] = item.GetItemName()

	def nui_icon_over(self, key):
		record = self.affects.get(key)
		if record is None or record["skill"]:
			return
		if record["affect"] in _auto_potions() + _dragon_souls():
			self._refresh_hover_values(record)
			self._arrange()

	# --- the model ---------------------------------------------------------------------

	def _entry(self, record):
		"""One icon of the model, as the legacy AffectImage shows it on hover."""
		affect = record["affect"]
		entry = {"key": affect, "kind": "affect", "image": record["image"], "small": record["small"],
		         "title": "", "line": "", "end": 0.0, "clocked": record["clocked"], "label": False}
		if record["skill"]:
			if record["end"] > 0:
				entry.update(title=_text(record["description"]), end=record["end"])
			else:
				entry.update(title=_text(record["name"]), label=True)
			return entry
		description = record.get("description")
		if affect in _auto_potions():
			entry.update(title=_text(record["title"]), line=_text(record["line"]))
		elif affect in _dragon_souls():
			entry.update(title=_text(description), end=record["end"])
		elif not record["clocked"]:
			entry.update(title=_text(description), label=bool(description))
		elif record["end"] > 0:
			entry.update(title=_text(description), end=record["end"])
		elif description:
			entry.update(title=_text(record["title"]), line=_text(description))
		return entry

	def _icons(self):
		icons = []
		if self.lover and self.lover["shown"]:
			point = min(100, max(0, self.lover["point"]))
			line = localeInfo.AFF_LOVE_POINT % (point)
			icons.append({"key": LOVER_KEY, "kind": "lover", "image": self._love_image(point), "small": True,
			              "title": _text(self.lover["name"]), "line": _text(line), "end": 0.0, "clocked": False,
			              "label": False})
		if self.horse:
			icons.append({"key": HORSE_KEY, "kind": "horse", "image": self.horse["image"], "small": True,
			              "title": "", "line": "\n".join(_text(line) for line in self.horse["lines"]), "end": 0.0,
			              "clocked": False, "label": False})
		for record in self.affects.values():
			icons.append(self._entry(record))
		return icons

	def _arrange(self):
		if self.board is not None:
			self.board.set(icons=self._icons())


localeInfo.RegisterReloadCallback(_on_locale_reload)
