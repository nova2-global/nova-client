# option
CONSOLE_ENABLE = 0

# The sash combine window's "combine all" check box (NOVA-20; OLD constInfo.py:4).
SASH_AUTO_COMBINE = False

# The chest-drop preview's rows (NOVA-18; OLD constInfo.py:32): chest vnum ->
# [(vnum, count, chance)] as GC::CHEST_DROP_INFO sent them, kept by the data
# cache (datacache.py: on disk per server and data version) so a chest is
# asked for once (uichestdrop.request).
import datacache
CHESTS_PREVIEW = datacache.Table("chest_drop")

# The mob info board's drops (NOVA-40; OLD constInfo.py:146): race ->
# {"items": merged rows, "level": the player's level at the answer,
# "currentAttackers": GC::TARGET's live count}. Cleared on map change
# (uitargetinfo.forget), refetched when the level changes.
MONSTER_INFO_DATA = {}

PVPMODE_ENABLE = 1
PVPMODE_TEST_ENABLE = 0
PVPMODE_ACCELKEY_ENABLE = 1
PVPMODE_ACCELKEY_DELAY = 0.5
PVPMODE_PROTECTED_LEVEL = 30

FOG_LEVEL0 = 4800.0
FOG_LEVEL1 = 9600.0
FOG_LEVEL2 = 12800.0
FOG_LEVEL = FOG_LEVEL0
FOG_LEVEL_LIST = [FOG_LEVEL0, FOG_LEVEL1, FOG_LEVEL2]

CAMERA_MAX_DISTANCE_SHORT = 2500.0
CAMERA_MAX_DISTANCE_LONG = 3500.0
CAMERA_MAX_DISTANCE_LIST = [CAMERA_MAX_DISTANCE_SHORT, CAMERA_MAX_DISTANCE_LONG]
CAMERA_MAX_DISTANCE = CAMERA_MAX_DISTANCE_SHORT

CHRNAME_COLOR_INDEX = 0

ENVIRONMENT_NIGHT = "d:/ymir work/environment/moonlight04.msenv"

# constant
HIGH_PRICE = 500000
MIDDLE_PRICE = 50000
ERROR_METIN_STONE = 28960
SUB2_LOADING_ENABLE = 1
EXPANDED_COMBO_ENABLE = 1
CONVERT_EMPIRE_LANGUAGE_ENABLE = 1
USE_ITEM_WEAPON_TABLE_ATTACK_BONUS = 0
ADD_DEF_BONUS_ENABLE = 1
LOGIN_COUNT_LIMIT_ENABLE = 0

USE_SKILL_EFFECT_UPGRADE_ENABLE = 1

VIEW_OTHER_EMPIRE_PLAYER_TARGET_BOARD = 1
GUILD_MONEY_PER_GSP = 100
GUILD_WAR_TYPE_SELECT_ENABLE = 1
TWO_HANDED_WEAPON_ATT_SPEED_DECREASE_VALUE = 0

HAIR_COLOR_ENABLE = 1
ARMOR_SPECULAR_ENABLE = 1
WEAPON_SPECULAR_ENABLE = 1
KEEP_ACCOUNT_CONNETION_ENABLE = 1
MINIMAP_POSITIONINFO_ENABLE = 0
CONVERT_EMPIRE_LANGUAGE_ENABLE = 0
USE_ITEM_WEAPON_TABLE_ATTACK_BONUS = 0
ADD_DEF_BONUS_ENABLE = 0
LOGIN_COUNT_LIMIT_ENABLE = 0
PVPMODE_PROTECTED_LEVEL = 15
TWO_HANDED_WEAPON_ATT_SPEED_DECREASE_VALUE = 10

# MR-3: Define max quickslot slots number for scripts
QUICKSLOT_MAX_NUM = 36
# MR-3: -- END OF -- Define max quickslot slots number for scripts

isItemQuestionDialog = 0

def GET_ITEM_QUESTION_DIALOG_STATUS():
	global isItemQuestionDialog
	return isItemQuestionDialog

def SET_ITEM_QUESTION_DIALOG_STATUS(flag):
	global isItemQuestionDialog
	isItemQuestionDialog = flag

import app
import net

# MR-10: Add accessorySocketTimeCache for real-time remaining time display of accessory sockets.
# Cache for accessory/belt socket timers so they persist across UI reloads.
if not hasattr(app, "_accessorySocketTimeCache"):
	app._accessorySocketTimeCache = {}
ACCESSORY_SOCKET_TIME_CACHE = app._accessorySocketTimeCache
# MR-10: -- END OF -- Add accessorySocketTimeCache for real-time remaining time display of accessory sockets.

########################

def SET_DEFAULT_FOG_LEVEL():
	global FOG_LEVEL
	app.SetMinFog(FOG_LEVEL)

def SET_FOG_LEVEL_INDEX(index):
	global FOG_LEVEL
	global FOG_LEVEL_LIST
	try:
		FOG_LEVEL=FOG_LEVEL_LIST[index]
	except IndexError:
		FOG_LEVEL=FOG_LEVEL_LIST[0]
	app.SetMinFog(FOG_LEVEL)

def GET_FOG_LEVEL_INDEX():
	global FOG_LEVEL
	global FOG_LEVEL_LIST
	return FOG_LEVEL_LIST.index(FOG_LEVEL)

########################

# The camera distance the player chose is saved (NOVA-212; OLD
# constInfo.py:340-360): the game start applies the saved choice, and a
# choice in either system options window saves it (SAVED_OPTIONS below).
def SET_DEFAULT_CAMERA_MAX_DISTANCE():
	global CAMERA_MAX_DISTANCE
	index = GET_SAVED_OPTION(OPTION_CAMERA_ZOOM)
	if 0 <= index < len(CAMERA_MAX_DISTANCE_LIST):
		CAMERA_MAX_DISTANCE = CAMERA_MAX_DISTANCE_LIST[index]
	else:
		CAMERA_MAX_DISTANCE = CAMERA_MAX_DISTANCE_LIST[0]
	app.SetCameraMaxDistance(CAMERA_MAX_DISTANCE)

def SET_CAMERA_MAX_DISTANCE_INDEX(index):
	global CAMERA_MAX_DISTANCE
	global CAMERA_MAX_DISTANCE_LIST
	try:
		CAMERA_MAX_DISTANCE=CAMERA_MAX_DISTANCE_LIST[index]
	except:
		CAMERA_MAX_DISTANCE=CAMERA_MAX_DISTANCE_LIST[0]

	app.SetCameraMaxDistance(CAMERA_MAX_DISTANCE)
	SET_SAVED_OPTION(OPTION_CAMERA_ZOOM, GET_CAMERA_MAX_DISTANCE_INDEX())

def GET_CAMERA_MAX_DISTANCE_INDEX():
	global CAMERA_MAX_DISTANCE
	global CAMERA_MAX_DISTANCE_LIST
	return CAMERA_MAX_DISTANCE_LIST.index(CAMERA_MAX_DISTANCE)

########################

import chrmgr
import player
import app

def SET_DEFAULT_CHRNAME_COLOR():
	global CHRNAME_COLOR_INDEX
	chrmgr.SetEmpireNameMode(CHRNAME_COLOR_INDEX)

def SET_CHRNAME_COLOR_INDEX(index):
	global CHRNAME_COLOR_INDEX
	CHRNAME_COLOR_INDEX=index
	chrmgr.SetEmpireNameMode(index)

def GET_CHRNAME_COLOR_INDEX():
	global CHRNAME_COLOR_INDEX
	return CHRNAME_COLOR_INDEX

def SET_VIEW_OTHER_EMPIRE_PLAYER_TARGET_BOARD(index):
	global VIEW_OTHER_EMPIRE_PLAYER_TARGET_BOARD
	VIEW_OTHER_EMPIRE_PLAYER_TARGET_BOARD = index

def GET_VIEW_OTHER_EMPIRE_PLAYER_TARGET_BOARD():
	global VIEW_OTHER_EMPIRE_PLAYER_TARGET_BOARD
	return VIEW_OTHER_EMPIRE_PLAYER_TARGET_BOARD

def SET_DEFAULT_CONVERT_EMPIRE_LANGUAGE_ENABLE():
	global CONVERT_EMPIRE_LANGUAGE_ENABLE
	net.SetEmpireLanguageMode(CONVERT_EMPIRE_LANGUAGE_ENABLE)

def SET_DEFAULT_USE_ITEM_WEAPON_TABLE_ATTACK_BONUS():
	global USE_ITEM_WEAPON_TABLE_ATTACK_BONUS
	player.SetWeaponAttackBonusFlag(USE_ITEM_WEAPON_TABLE_ATTACK_BONUS)

def SET_DEFAULT_USE_SKILL_EFFECT_ENABLE():
	global USE_SKILL_EFFECT_UPGRADE_ENABLE
	app.SetSkillEffectUpgradeEnable(USE_SKILL_EFFECT_UPGRADE_ENABLE)

def SET_TWO_HANDED_WEAPON_ATT_SPEED_DECREASE_VALUE():
	global TWO_HANDED_WEAPON_ATT_SPEED_DECREASE_VALUE
	app.SetTwoHandedWeaponAttSpeedDecreaseValue(TWO_HANDED_WEAPON_ATT_SPEED_DECREASE_VALUE)

########################
import item

ACCESSORY_MATERIAL_LIST = [50623, 50624, 50625, 50626, 50627, 50628, 50629, 50630, 50631, 50632, 50633, 50634, 50635, 50636, 50637, 50638]
#ACCESSORY_MATERIAL_LIST = [50623, 50623, 50624, 50624, 50625, 50625, 50626, 50627, 50628, 50629, 50630, 50631, 50632, 50633, 
#			    50623, 50623, 50624, 50624, ]
JewelAccessoryInfos = [
		# jewel		wrist	neck	ear
		[ 50634,	14420,	16220,	17220 ],	
		[ 50635,	14500,	16500,	17500 ],	
		[ 50636,	14520,	16520,	17520 ],	
		[ 50637,	14540,	16540,	17540 ],	
		[ 50638,	14560,	16560,	17560 ],	
	]
def GET_ACCESSORY_MATERIAL_VNUM(vnum, subType):
	ret = vnum
	item_base = (vnum // 10) * 10
	for info in JewelAccessoryInfos:
		if item.ARMOR_WRIST == subType:	
			if info[1] == item_base:
				return info[0]
		elif item.ARMOR_NECK == subType:	
			if info[2] == item_base:
				return info[0]
		elif item.ARMOR_EAR == subType:	
			if info[3] == item_base:
				return info[0]
 
	if vnum >= 16210 and vnum <= 16219:
		return 50625

	if item.ARMOR_WRIST == subType:	
		WRIST_ITEM_VNUM_BASE = 14000
		ret -= WRIST_ITEM_VNUM_BASE
	elif item.ARMOR_NECK == subType:
		NECK_ITEM_VNUM_BASE = 16000
		ret -= NECK_ITEM_VNUM_BASE
	elif item.ARMOR_EAR == subType:
		EAR_ITEM_VNUM_BASE = 17000
		ret -= EAR_ITEM_VNUM_BASE

	type = ret // 20

	if type < 0 or type >= len(ACCESSORY_MATERIAL_LIST):
		type = (ret - 170) // 20

		if type < 0 or type >= len(ACCESSORY_MATERIAL_LIST):
			return 0

	return ACCESSORY_MATERIAL_LIST[type]

##################################################################
## Belt item type and belt socket item handling
## Belt socket system is identical to accessories, so must use hardcoding approach similar to accessory handling

def GET_BELT_MATERIAL_VNUM(vnum, subType = 0):
	# Currently all belts can only insert one item type (#18900)
	return 18900

##################################################################
## Auto-potions (HP: #72723 ~ #72726, SP: #72727 ~ #72730)

# Check if vnum is an auto-potion
def IS_AUTO_POTION(itemVnum):
	return IS_AUTO_POTION_HP(itemVnum) or IS_AUTO_POTION_SP(itemVnum)
	
# A buffi item (NOVA-38; OLD constInfo.py:614-615): the dragon, healer and
# fused buffi, permanent or timed (91010-91027).
def IS_FAKEBUFF_ITEM(itemVnum):
	return 91010 <= itemVnum <= 91027

# Check if vnum is an HP auto-potion
def IS_AUTO_POTION_HP(itemVnum):
	if 72723 <= itemVnum and 72726 >= itemVnum:
		return 1
	elif itemVnum >= 76021 and itemVnum <= 76022:		## Gift item: Fire Dragon's Blessing
		return 1
	elif itemVnum == 79012:
		return 1
		
	return 0
	
# Check if vnum is an SP auto-potion
def IS_AUTO_POTION_SP(itemVnum):
	if 72727 <= itemVnum and 72730 >= itemVnum:
		return 1
	elif itemVnum >= 76004 and itemVnum <= 76005:		## Gift item: Water Dragon's Blessing
		return 1
	elif itemVnum == 79013:
		return 1
				
	return 0


# The language flags (NOVA-30/46, NOVA-48): OLD's 32 x 32 flags at
# locale/common/ui/flag/32/<code>.tga, shown by the messenger's staff rosters
# and the whisper dialog. A code with no file here shows no flag.
LANGUAGE_FLAG_PATH = "locale/common/ui/flag/32/%s.tga"
LANGUAGE_FLAG_CODES = ("ae", "cz", "de", "dk", "en", "es", "fr", "gr", "hu", "it", "nl", "pl", "pt", "ro", "ru", "tr")

# The flag image of a language code ("en"), or "" when there is none.
def GET_LANGUAGE_FLAG(code):
	code = str(code).strip().lower()
	if code in LANGUAGE_FLAG_CODES:
		return LANGUAGE_FLAG_PATH % code
	return ""

# Change channel (NOVA-49): the server the player logged in through, found
# again from the server info text intrologin sets at login, "<server>,
# <channel>" (net.SetServerInfo). (regionID, serverID) of serverInfo's
# REGION_DICT, or None when the text names no server there (a direct login by
# address). The modules are imported here, not at the top: this module loads
# before them.
def GET_LOGIN_SERVER():
	import net
	import serverInfo
	text = net.GetServerInfo().strip()
	if ", " not in text:
		return None
	serverName = text.rsplit(", ", 1)[0]
	for regionID in sorted(serverInfo.REGION_DICT):
		regionDict = serverInfo.REGION_DICT[regionID]
		for serverID in sorted(regionDict):
			if regionDict[serverID].get("name") == serverName:
				return (regionID, serverID)
	return None

# The channel numbers of the login server, in order (empty without one).
def GET_LOGIN_SERVER_CHANNELS():
	import serverInfo
	server = GET_LOGIN_SERVER()
	if not server:
		return []
	(regionID, serverID) = server
	return sorted(serverInfo.REGION_DICT[regionID][serverID].get("channel", {}))

# The server info text for channel `channel` of the login server, named as
# intrologin names a channel (its "name", else CHANNEL_NORMAL); "" without a
# login server.
def GET_CHANNEL_SERVER_INFO(channel):
	import serverInfo
	import localeInfo
	server = GET_LOGIN_SERVER()
	if not server:
		return ""
	(regionID, serverID) = server
	serverDict = serverInfo.REGION_DICT[regionID][serverID]
	channelDict = serverDict.get("channel", {}).get(channel)
	if channelDict and channelDict.get("name"):
		channelName = channelDict["name"]
	else:
		channelName = localeInfo.CHANNEL_NORMAL % channel
	return "%s, %s" % (serverDict["name"], channelName)


## The chest-drop preview (NOVA-18; OLD constInfo.py:543-555): a gift box, a
## gacha chest or a treasure box of the use type opens into a group whose rows
## Shift shows (uichestdrop.py).
def IS_CHEST_PREVIEWABLE(itemVnum):
	if not itemVnum:
		return False
	item.SelectItem(itemVnum)
	itemType = item.GetItemType()
	if itemType == getattr(item, "ITEM_TYPE_GIFTBOX", -1):
		return True
	if itemType == item.ITEM_TYPE_GACHA:
		return True
	if itemType == item.ITEM_TYPE_USE and item.GetItemSubType() == item.USE_TREASURE_BOX:
		return True
	return False

## The chest under the pointer in the inventory, the special inventory or a
## shop (OLD's selectedItem of each): their OverInItem sets it, OverOutItem
## clears it, and the Shift press reads it (Interface.OpenHoveredChestDrop).
HOVERED_CHEST = 0

def SET_HOVERED_CHEST(itemVnum):
	global HOVERED_CHEST
	HOVERED_CHEST = itemVnum if itemVnum and IS_CHEST_PREVIEWABLE(itemVnum) else 0

def GET_HOVERED_CHEST():
	return HOVERED_CHEST


########################
## The options the client saves in its own file (NOVA-211, NOVA-212,
## NOVA-215), as config/keys.cfg and config/mouse.cfg: CPythonSystem's
## metin2.cfg keeps only the keys its C++ knows. One line per option,
## `name<TAB>value`, every option written; a line this version does not read
## is skipped, and a missing or broken file is the defaults. A change is
## saved at once (SET_SAVED_OPTION); a file that cannot be written keeps the
## choice for the session. The defaults wait for Eddy:
## - yang_text: the "You have received N Yang." line (game.py OnPickMoney), on;
## - country_flags: the flag beside player names, on (C++ draws it while
##   chrmgr.SetShowLanguageFlag is on; the game start applies the saved
##   choice, a change applies at once);
## - camera_zoom: the camera distance's index in CAMERA_MAX_DISTANCE_LIST.
SAVED_OPTIONS_PATH = "config/game_options.cfg"
SAVED_OPTIONS_HEADER = "# Game options (NOVA-211, 212, 215): name<TAB>value."
OPTION_YANG_TEXT = "yang_text"
OPTION_COUNTRY_FLAGS = "country_flags"
OPTION_CAMERA_ZOOM = "camera_zoom"
SAVED_OPTION_DEFAULTS = {OPTION_YANG_TEXT: 1, OPTION_COUNTRY_FLAGS: 1, OPTION_CAMERA_ZOOM: 0}
SAVED_OPTION_NAMES = (OPTION_YANG_TEXT, OPTION_COUNTRY_FLAGS, OPTION_CAMERA_ZOOM)
# The opener of the file (tests put one over memory); None is the disk.
SAVED_OPTIONS_OPEN = None
_savedOptions = None

def _saved_options_open(path, mode="r"):
	"""The file on disk: the client's open() (system.py) answers a name the
	asset store also has with a pack file, which has no `with`."""
	if SAVED_OPTIONS_OPEN is not None:
		return SAVED_OPTIONS_OPEN(path, mode)
	import builtins
	return getattr(builtins, "old_open", open)(path, mode)

def _read_saved_options():
	values = dict(SAVED_OPTION_DEFAULTS)
	try:
		with _saved_options_open(SAVED_OPTIONS_PATH, "r") as handle:
			text = handle.read()
	except Exception:
		return values
	for line in text.split("\n"):
		fields = line.strip("\r").split("\t")
		if len(fields) != 2 or fields[0] not in values:
			continue
		try:
			values[fields[0]] = int(fields[1])
		except ValueError:
			pass
	return values

def RELOAD_SAVED_OPTIONS():
	"""Reads the file again at the next use (tests; a new client reads it once)."""
	global _savedOptions
	_savedOptions = None

def GET_SAVED_OPTION(name):
	"""The option's saved value (an int); KeyError for an unknown name."""
	global _savedOptions
	if _savedOptions is None:
		_savedOptions = _read_saved_options()
	return _savedOptions[name]

def SET_SAVED_OPTION(name, value):
	"""Keeps and saves the value, then applies it (the country flags); False
	when it is the value in effect already."""
	value = int(value)
	if GET_SAVED_OPTION(name) == value:
		return False
	_savedOptions[name] = value
	lines = [SAVED_OPTIONS_HEADER] + ["%s\t%d" % (key, _savedOptions[key]) for key in SAVED_OPTION_NAMES]
	try:
		with _saved_options_open(SAVED_OPTIONS_PATH, "w") as handle:
			handle.write("\n".join(lines) + "\n")
	except Exception:
		pass
	if name == OPTION_COUNTRY_FLAGS:
		SET_DEFAULT_COUNTRY_FLAGS()
	return True

def SET_DEFAULT_COUNTRY_FLAGS():
	"""The saved country flag choice to C++ (NOVA-215); an exe without the
	flag draws none."""
	setter = getattr(chrmgr, "SetShowLanguageFlag", None)
	if setter is not None:
		setter(bool(GET_SAVED_OPTION(OPTION_COUNTRY_FLAGS)))
