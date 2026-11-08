"""What the advanced pet's tests share (NOVA-24, chunks Y and N): chunk C's
`pet` module (contract 6) as a stand-in over a PetState, recording every
call as "pet.<name>"; the pet items' item data and constants (contract 4.3
and 6); app.ENABLE_PET_ADVANCED; and a legacy world (wave6_support.World)
with them and uipet.py loaded.

The getters answer from the state and take OLD's optional isPreview flag;
the sends (UseEgg, ChangeName, UseResetSkill, RequestAttrRefineInfo,
RefineAttr, RequestEvolutionInfo, Evolve, ReqPetPreview) only record.
sends(world) lists them in order."""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wave6_support as w6  # noqa: E402

support = w6.support
lf = w6.lf
REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LOCALE = os.path.join(REPO, "assets", "locale", "locale")

# contract 6: the pet module's constants
PET_CONSTANTS = {
    "PET_PREVIEW_EXCHANGE_SELF": 1, "PET_PREVIEW_EXCHANGE_OTHER": 2, "PET_PREVIEW_INVENTORY": 3,
    "PET_PREVIEW_OFFLINESHOP": 4, "PET_PREVIEW_SEARCHSHOP": 5, "SKILL_NORMAL_START": 0, "SKILL_HEROIC_START": 10,
    "SKILL_MAX_LEVEL": 20, "SKILL_HEROIC_MAX_LEVEL": 10, "SKILL_MAX_NUM": 13, "MAX_LEVEL": 105, "ATTR_MAX_NUM": 3,
    "EGG_HATCH_SOCKET": 1,
}
# contract 6: the item module's names
ITEM_CONSTANTS = {
    "ITEM_TYPE_PET_ADVANCED": 39, "ITEM_SUBTYPE_PET_SUMMON": 1, "PET_EGG": 0, "PET_SUMMON": 1, "PET_SKILL_BOOK": 2,
    "PET_HEROIC_SKILL_BOOK": 3, "PET_SKILL_REVERT": 4, "PET_SKILLPOWER_REROLL": 5, "PET_NAME_CHANGE": 6,
    "PET_DESTINY_ORB": 7,
}
SENDS = ("UseEgg", "ChangeName", "UseResetSkill", "RequestAttrRefineInfo", "RefineAttr", "RequestEvolutionInfo",
         "Evolve", "ReqPetPreview")

# The items of NEW's item_proto (contract 4.3): vnum -> (subtype, values).
EGG, SEAL, SEAL_FIXED = 55401, 55701, 55700
REVERT, ORB, NAME_CHANGER = 55006, 55007, 55008
SKILL_BOOK, HEROIC_BOOK = 55010, 55025
PET_ITEMS = {
    EGG: (0, (0, 55701, 1000000, 0, 0, 0)), 55402: (0, (0, 55702, 1000000, 0, 0, 0)),
    SEAL_FIXED: (1, (34041, 0, 0, 34042, 0, 0)), SEAL: (1, (34041, 0, 0, 34042, 0, 0)),
    REVERT: (4, (0,) * 6), ORB: (7, (0,) * 6), NAME_CHANGER: (6, (0,) * 6),
    SKILL_BOOK: (2, (63, 0, 0, 0, 0, 0)), HEROIC_BOOK: (3, (86, 0, 0, 0, 0, 0)),
}
# APPLY_* numbers (NEW's EApplyTypes) of the skills the tests use.
APPLY_MAX_HP, APPLY_HP_REGEN, APPLY_ATTBONUS_MONSTER = 1, 10, 63
APPLY_CRITICAL_PCT, APPLY_BLOCK = 15, 27


def read_table(name, locale="common"):
    rows = []
    with open(os.path.join(LOCALE, locale, name), encoding="utf-8") as handle:
        for line in handle:
            cells = line.rstrip("\n").split("\t")
            if len(cells) > 1:
                rows.append(cells)
    return rows


class PetState(object):
    """What C's CPythonPetAdvanced holds: the summoned pet, the preview, the
    refine and evolution infos, and the client's data tables."""

    def __init__(self):
        self.summoned = False
        self.vid = 0
        self.own = self.blank()
        self.preview = self.blank()
        self.refine = {"cost": 0, "materials": []}
        self.evolve = {"cost": 0, "materials": [], "prob": 0}
        self.evolve_rows = [(int(row[0]), row[1], int(row[4]), int(row[5]), int(row[6]))
                            for row in read_table("pet_evolvetable.txt")]
        self.skill_rows = read_table("pet_skilltable.txt")
        self.descs = dict((row[0], (row[1], row[2])) for row in read_table("pet_skilldesc.txt", "en"))

    @staticmethod
    def blank():
        return {"item_vnum": 0, "name": "", "level": 0, "exp": 0, "next_exp": 0, "skillpower": 0,
                "attrs": [[0, 0, 0, 0] for _ in range(3)], "skills": [[0, 0, 0] for _ in range(13)]}

    def table(self, preview=False):
        return self.preview if preview else self.own

    def summon(self, item_vnum=SEAL, name="Rex", level=15, exp=0, next_exp=2000):
        self.summoned = True
        self.vid = 4242
        self.own.update({"item_vnum": item_vnum, "name": name, "level": level, "exp": exp, "next_exp": next_exp})

    def evolve_row(self, level):
        for row in self.evolve_rows:
            if row[0] == level:
                return row
        return None


def install(game, state=None):
    """The pet module, the item and app names; returns the PetState."""
    state = state or PetState()
    log = game.log
    pet = support.Recording("pet", log, **PET_CONSTANTS)
    define = lambda name, fn: support.define(pet, name, fn)
    T = state.table
    define("IsSummoned", lambda: state.summoned)
    define("GetSummonVID", lambda: state.vid)
    for key, name in (("item_vnum", "GetItemVnum"), ("name", "GetName"), ("level", "GetLevel"), ("exp", "GetExp"),
                      ("next_exp", "GetNextExp"), ("skillpower", "GetSkillpower")):
        define(name, lambda p=False, key=key: T(p)[key])
    for column, name in enumerate(("GetAttrType", "GetAttrLevel", "GetAttrValue", "GetAttrCanUpgrade")):
        define(name, lambda i, p=False, column=column: T(p)["attrs"][i][column])
    define("GetAttrRefineCost", lambda: state.refine["cost"])
    define("GetAttrRefineMaterialCount", lambda: len(state.refine["materials"]))
    define("GetAttrRefineMaterial", lambda i: state.refine["materials"][i])
    define("GetEvolveCost", lambda: state.evolve["cost"])
    define("GetEvolveMaterialCount", lambda: len(state.evolve["materials"]))
    define("GetEvolveMaterial", lambda i: state.evolve["materials"][i])
    define("GetEvolveProb", lambda: state.evolve["prob"])
    define("GetSkillID", lambda slot, p=False: T(p)["skills"][slot][0])
    define("GetSkillLevel", lambda slot, p=False: T(p)["skills"][slot][1])

    def skill_value(apply, p=False):
        for vnum, level, value in T(p)["skills"]:
            if vnum == apply:
                return "%d" % value
        return "0"
    define("GetSkillProtoValue", skill_value)
    define("GetSkillProtoApply", lambda apply: apply)
    names = {1: "MAX_HP", 10: "HP_REGEN", 63: "ATT_BONUS_TO_MONSTER", 86: "SKILL_DAMAGE_BONUS"}
    define("GetSkillProtoName", lambda apply: state.descs.get(names.get(apply, ""), ("", ""))[0])
    define("GetSkillProtoDesc", lambda apply: state.descs.get(names.get(apply, ""), ("", ""))[1])
    define("GetSkillProtoIconPath", lambda apply: "d:/ymir work/ui/pet/skill/normal/%s.gif" % names.get(apply, apply))
    define("GetSkillProtoIconImage", lambda apply: "pet-skill-image-%d" % apply)
    rows = state.evolve_rows
    define("GetEvolveProtoLevel", lambda index: rows[index][0] if 0 <= index < len(rows) else -1)
    define("GetEvolveProtoName", lambda level: (state.evolve_row(level) or (0, "", 0, 0, 0))[1])
    define("GetEvolveProtoNormalSkillCount", lambda level: (state.evolve_row(level) or (0, "", 0, 0, 0))[2])
    define("GetHeroicProtoPassiveSkillCount", lambda level: (state.evolve_row(level) or (0, "", 0, 0, 0))[3])
    define("GetEvolveProtoSkillpower", lambda level: (state.evolve_row(level) or (0, "", 0, 0, 0))[4])
    game.put("pet", pet)
    game.pet_state = state

    item, app = game.modules["item"], game.modules["app"]
    for name, value in ITEM_CONSTANTS.items():
        setattr(item, name, value)
    app.ENABLE_PET_ADVANCED = 1
    selected = item.selected
    old_type = item.__dict__.get("GetItemType")
    old_sub = item.__dict__.get("GetItemSubType")
    old_value = item.__dict__.get("GetValue")

    def kind(*vnum):
        v = vnum[0] if vnum else selected[0]
        if v in PET_ITEMS:
            return ITEM_CONSTANTS["ITEM_TYPE_PET_ADVANCED"]
        return old_type(*vnum) if callable(old_type) else 0

    def sub(*vnum):
        v = vnum[0] if vnum else selected[0]
        if v in PET_ITEMS:
            return PET_ITEMS[v][0]
        return old_sub(*vnum) if callable(old_sub) else 0

    def value(i):
        if selected[0] in PET_ITEMS:
            return PET_ITEMS[selected[0]][1][i]
        return old_value(i) if callable(old_value) else 0
    support.define(item, "GetItemType", kind)
    support.define(item, "GetItemSubType", sub)
    support.define(item, "GetValue", value)
    return state


def install_ui(game):
    """ui.py's SetPetSkillSlot on the slot stand-in (what it shows: the skill
    and its level as the count) and uiToolTip's PetSkillToolTip and
    AFFECT_DICT where the world's stand-in lacks them."""
    slot_class = support.LegacySlotWindow
    ui = game.modules["ui"]
    loader = ui.PythonScriptLoader
    if not getattr(loader, "pet_edit_lines", False):
        load = loader.LoadScriptFile

        def load_with_edit_lines(self, window, path):
            """The uiscript's "editline" children as ui.EditLine (the Wave 3b
            loader makes them plain windows)."""
            load(self, window, path)
            for child in lf.children(support.read_uiscript(path)):
                if child.get("type") == "editline":
                    edit = ui.EditLine()
                    edit.name = child["name"]
                    edit.SAFE_SetReturnEvent = lambda event, edit=edit: setattr(edit, "return_event", event)
                    edit.SetEscapeEvent = lambda event, edit=edit: setattr(edit, "escape_event", event)
                    window.ElementDictionary[child["name"]] = edit
        loader.LoadScriptFile = load_with_edit_lines
        loader.pet_edit_lines = True

    def set_pet_skill_slot(self, index, vnum, level, scalex=1.0, scaley=1.0):
        game.log.append(("slot.SetPetSkillSlot", (index, vnum, level, scalex, scaley)))
        slot = self._slot(index)
        if slot is not None:
            slot.update({"vnum": vnum, "count": level})
    slot_class.SetPetSkillSlot = set_pet_skill_slot
    tooltip = game.modules["uiToolTip"]

    class PetSkillToolTip(object):
        def __init__(self):
            self.shown = False
            self.skill = None

        def SetSkill(self, skill_id, level, is_preview=False):
            game.log.append(("PetSkillToolTip.SetSkill", (skill_id, level, is_preview)))
            self.skill = (skill_id, level, is_preview)
            self.shown = True

        def HideToolTip(self):
            self.shown = False

        def Hide(self):
            self.shown = False

        def IsShow(self):
            return self.shown
    if not hasattr(tooltip, "PetSkillToolTip"):
        tooltip.PetSkillToolTip = PetSkillToolTip
    affects = {APPLY_MAX_HP: lambda v: "Max HP +%d" % v, APPLY_HP_REGEN: lambda v: "HP Regeneration +%d%%" % v,
               APPLY_ATTBONUS_MONSTER: lambda v: "Strong against Monsters +%d%%" % v,
               APPLY_CRITICAL_PCT: lambda v: "Critical Hit +%d%%" % v, APPLY_BLOCK: lambda v: "Block +%d%%" % v}
    item_tooltip = tooltip.ItemToolTip
    if not isinstance(getattr(item_tooltip, "AFFECT_DICT", None), dict):
        item_tooltip.AFFECT_DICT = affects


class World(w6.World):
    """The legacy world with the pet module and uipet.py."""

    def __init__(self, state=None):
        w6.World.__init__(self)
        self.state = install(self.game, state)
        install_ui(self.game)
        self.game.put("uiScriptLocale", locale_module("locale_interface.txt"))

    def pet_module(self):
        return self.load("uiPet", "uipet.py")


def locale_module(name):
    """uiScriptLocale: the English locale_interface.txt as attributes."""
    module = types.ModuleType("uiScriptLocale")
    with open(os.path.join(LOCALE, "en", name), encoding="utf-8") as handle:
        for line in handle:
            cells = line.rstrip("\n").split("\t")
            if len(cells) >= 2 and cells[0]:
                setattr(module, cells[0], cells[1])
    return module


def sends(world):
    """The pet module's requests, in order: (name, args)."""
    return [(name[len("pet."):], args) for name, args in world.game.log
            if name.startswith("pet.") and name[len("pet."):] in SENDS]


def run(world, call, *args):
    with world.game, lf.quiet():
        return call(*args)
