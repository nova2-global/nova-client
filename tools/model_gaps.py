"""Which wiki model previews the client can draw (NOVA-177).

The wiki (assets/root/nui_wiki.py) previews an item by preview_of: a weapon,
an armor or costume body, a costume weapon, hair or sash on a player race,
a pet or mount as the mob race its value 3 names; and a mob (boss, monster,
metin) as its own race. The client builds that model with CInstanceBase's
part setters (nova-client-src UserInterface/PythonModelPreview.cpp), which
take a race file's shape or hair (root/msm/<race>.msm), an item_list line's
model, or a mob's msm and its base model. When the file a part names is not
in the pack, the client still makes the instance, and it draws nothing.

This module repeats that lookup offline for every vnum the wiki can preview
and says why a part draws nothing:

	shape_missing     the armor's value 3 is no shape of the race file (the
	                  race's base body shows, not the item)
	hair_missing      the hair's value 3 is no hair of the race file
	no_item_list      no item_list line for the weapon or sash
	no_model_path     its item_list line names no model
	model_missing     the file the race file, item_list or msm names is not
	                  in the pack
	model_unreadable  the file is OLD's custom Granny format (tag 0x71000039),
	                  which NEW's loader reads as empty
	no_npclist        no npclist line names the mob's race
	no_msm            no folder of the race's search paths has its msm
	no_base_model     the msm names no BaseModelFileName

Each gap also says whether OLD has what NEW lacks (OLD's race files, item_list
and packer). As a script:

	python3 tools/model_gaps.py audit FULL_REPO ITEM_PROTO MOB_PROTO PACKER OLD_ROOT OUT_TSV
	python3 tools/model_gaps.py plan FULL_REPO ITEM_PROTO MOB_PROTO PACKER OLD_ROOT GRLIST AUDIT_TSV
	python3 tools/model_gaps.py import PACKER OLD_ROOT GRLIST AUDIT_TSV BATCH
	python3 tools/model_gaps.py item_list OLD_ROOT CUT_ITEM_PROTO

import takes OLD's files for one of BATCHES (equipment, mobs, hair,
costume_armor_1, costume_armor_2) into this worktree's groups through
old_art.place (manifest rows in tools/fixtures/old_art.tsv); add them with
`git add --sparse`. item_list then adds OLD's lines whose files now ship
(old_content.py item_list, on git's tree).

FULL_REPO is a full checkout of nova-client (its assets/ complete), ITEM_PROTO
and MOB_PROTO the runtime's share/conf/*.txt, PACKER OLD's packer folder
(old_art.py's), OLD_ROOT old/client_pack/source. It prints the counts per
category and cause and writes one row per vnum to OUT_TSV. plan sizes what
an import of OLD's files for the gaps OLD can fix would take (old_art.py's
closure: the textures a model names, the files an effect or motion names),
per category; it writes nothing.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import old_content  # noqa: E402
import race_msm  # noqa: E402

CUSTOM_TAG = 0x71000039
OK = "ok"
JOB_FLAGS = ("ANTI_MUSA", "ANTI_ASSASSIN", "ANTI_SURA", "ANTI_MUDANG")
MALE_RACES = (0, 2, 5, 7)
MOB_RANK_BOSS = ("BOSS", "KING")


def proto_items(text):
	"""{vnum: (name, type, sub, value3, anti flags)} of an item_proto.txt's
	single-vnum rows (rows split only at LF: OLD's names hold a 0x1C byte)."""
	rows = text.split("\n")
	header = rows[0].rstrip("\r").split("\t")
	value3 = header.index("VALUE3")
	items = {}
	for row in rows[1:]:
		cells = row.rstrip("\r").split("\t")
		if len(cells) <= value3 or not cells[0].strip().isdigit():
			continue
		flags = frozenset(flag.strip() for flag in cells[5].split("|"))
		items[int(cells[0])] = (cells[1], cells[2], cells[3], old_content.atoi(cells[value3]), flags)
	return items


def proto_mobs(text):
	"""{vnum: (name, rank, type, level)} of a mob_proto.txt."""
	mobs = {}
	for row in text.split("\n")[1:]:
		cells = row.rstrip("\r").split("\t")
		if len(cells) < 6 or not cells[0].strip().isdigit():
			continue
		mobs[int(cells[0])] = (cells[1], cells[2], cells[3], old_content.atoi(cells[5]))
	return mobs


def allowed_races(flags):
	"""nui_wiki._wearer_race's candidates: the races whose job and sex the
	item allows, in race order."""
	out = []
	for race in range(8):
		if JOB_FLAGS[race % 4] in flags:
			continue
		if ("ANTI_MALE" if race in MALE_RACES else "ANTI_FEMALE") in flags:
			continue
		out.append(race)
	return out


def item_plan(vnum, item, lists):
	"""nui_wiki.preview_of on the proto row: (category, kind, index) where
	kind is "mob" (index: the race), "shape", "hair", "weapon" or "sash"
	(index: the value 3 or the vnum), or None for an icon-only item."""
	_, kind, sub, value3, _ = item
	if vnum in lists.COSTUME_PETS or vnum in lists.COSTUME_MOUNTS:
		category = "pet" if vnum in lists.COSTUME_PETS else "mount"
		return (category, "mob", value3) if value3 else None
	if vnum in lists.COSTUME_WINGS or vnum in lists.COSTUME_MASKS or vnum in lists.COSTUME_EFFECTS:
		return None
	if kind == "ITEM_WEAPON":
		return ("weapon", "weapon", vnum)
	if kind == "ITEM_ARMOR" and sub == "ARMOR_BODY":
		return ("armor", "shape", value3)
	if kind == "ITEM_COSTUME":
		if sub == "COSTUME_BODY":
			return ("costume_armor", "shape", value3)
		if sub == "COSTUME_WEAPON":
			return ("costume_weapon", "weapon", vnum)
		if sub == "COSTUME_HAIR":
			return ("costume_hair", "hair", value3)
		if sub == "COSTUME_SASH":
			return ("sash", "sash", vnum)
		if sub == "COSTUME_SASH2":
			# Wings outside the wiki's wing list. The client draws the race
			# file's WingData shape their value 3 names when there is one,
			# else the item_list model; only the latter is looked up here.
			return ("wing", "sash", vnum)
	return None


def sash_vnum(vnum):
	"""CInstanceBase::SashPartToVnum's item for a sash part."""
	return vnum + 85000 if vnum < 48000 else vnum


class Pack(object):
	"""NEW's published files: store path -> file on disk (the last group
	that has it, as groups.txt orders them)."""

	def __init__(self, repo, fallback=None):
		"""``fallback``: a full checkout of the same tree, read for a file a
		sparse worktree lists but does not hold."""
		self.repo = repo
		self.fallback = fallback
		assets = os.path.join(repo, "assets")
		with open(os.path.join(assets, "groups.txt"), encoding="utf-8") as handle:
			groups = [line for line in (raw.split("#")[0].strip() for raw in handle) if line]
		order = dict((group, i) for i, group in enumerate(groups))
		done = subprocess.run(["git", "-C", repo, "ls-files", "-z", "--", "assets"], capture_output=True, check=True)
		self.files = {}
		rank = {}
		for path in done.stdout.decode("utf-8", "replace").split("\0"):
			parts = path.split("/")
			if len(parts) < 3 or parts[1] not in order:
				continue
			store = old_content.store_name("/".join(parts[2:]))
			if store.startswith("ymir work/"):
				store = "d:/" + store
			if rank.get(store, -1) <= order[parts[1]]:
				rank[store] = order[parts[1]]
				self.files[store] = path
		self._tags = {}

	def disk(self, store):
		path = self.files[old_content.store_name(store)]
		local = os.path.join(self.repo, path)
		if os.path.exists(local) or not self.fallback:
			return local
		return os.path.join(self.fallback, path)

	def has(self, store):
		return old_content.store_name(store) in self.files

	def read(self, store):
		with open(self.disk(store), "rb") as handle:
			return handle.read()

	def tag(self, store):
		store = old_content.store_name(store)
		if store not in self._tags:
			with open(self.disk(store), "rb") as handle:
				head = handle.read(72)
			self._tags[store] = int.from_bytes(head[68:72], "little") if len(head) >= 72 else 0
		return self._tags[store]


def model_cause(pack, path):
	"""(cause, file) for a model a part names."""
	if not path:
		return "no_model_path", ""
	if not pack.has(path):
		return "model_missing", old_content.store_name(path)
	if path.lower().endswith(".gr2") and pack.tag(path) == CUSTOM_TAG:
		return "model_unreadable", old_content.store_name(path)
	return OK, old_content.store_name(path)


def item_list_models(data):
	"""{vnum: model or ""} of an item_list.txt, as CItemManager::LoadItemList
	reads it (an AURA line's fourth column is an effect)."""
	lines, _ = old_content.item_list_lines(data)
	out = {}
	for vnum, line in lines.items():
		tokens = old_content.split_tab(line)
		out[vnum] = tokens[3] if len(tokens) == 4 and tokens[1] != "AURA" else ""
	return out


class Mobs(object):
	"""A race's model as CRaceManager finds it: npclist name, msm, base model."""

	def __init__(self, pack):
		self.pack = pack
		text = pack.read("npclist.txt").decode("latin-1")
		self.names, self.folders = old_content.npclist_entries(text)

	def msm(self, race):
		name = self.names.get(race)
		if not name:
			return None
		if name.startswith("#"):
			path = old_content.store_name(name[1:] + "shape.msm")
			return path if self.pack.has(path) else None
		folder = self.folders.get(name, name)
		for base in old_content.race_paths(race):
			path = old_content.store_name("%s%s/%s.msm" % (base, folder, name))
			if self.pack.has(path):
				return path
		return None

	def cause(self, race):
		if not self.names.get(race):
			return "no_npclist", ""
		msm = self.msm(race)
		if msm is None:
			return "no_msm", self.names[race]
		data = race_msm.load(self.pack.read(msm))
		if not data.base_model:
			return "no_base_model", msm
		return model_cause(self.pack, data.base_model)


def old_has(cause, detail, kind, index, race, old, pack):
	"""Where the fix for this gap is: "new" (the file is in NEW's pack, only
	a data line is missing), "old" (OLD has the file), "no" (neither), and
	the store path the fix starts from."""
	def where(path):
		path = old_content.store_name(path) if path else ""
		if not path:
			return "no", ""
		if pack.has(path) and not (path.endswith(".gr2") and pack.tag(path) == CUSTOM_TAG):
			return "new", path
		return ("old" if path in old["index"] else "no"), path
	if cause in ("model_missing", "model_unreadable"):
		return where(detail)
	if cause in ("shape_missing", "hair_missing"):
		look = race_msm.resolve(old["races"][race_msm.RACES[race]], "shapedata" if kind == "shape" else "hairdata", index)
		return where(look[0] if look else "")
	if cause in ("no_item_list", "no_model_path"):
		return where(old["item_list"].get(int(detail) if detail.isdigit() else index))
	if cause in ("no_npclist", "no_msm", "no_base_model"):
		name = old["mob_names"].get(index)
		if not name:
			return "no", ""
		folder = old["mob_folders"].get(name, name)
		for base in old_content.race_paths(index):
			msm = old_content.store_name("%s%s/%s.msm" % (base, folder, name))
			if pack.has(msm):
				return "new", msm
			if msm in old["index"]:
				return "old", msm
		return "no", ""
	return "-", ""


def part_cause(plan, race, pack, races, models, mobs):
	"""(cause, detail) for the part the item's preview is about, on race."""
	_, kind, index = plan
	if kind == "mob":
		return mobs.cause(index)
	if kind in ("shape", "hair"):
		data = races[race_msm.RACES[race]]
		look = (data.shapes if kind == "shape" else data.hairs).get(index)
		if look is None:
			return ("shape_missing" if kind == "shape" else "hair_missing"), str(index)
		return model_cause(pack, look[0])
	vnum = sash_vnum(index) if kind == "sash" else index
	if vnum not in models:
		return "no_item_list", str(vnum)
	return model_cause(pack, models[vnum])


def listed(vnum, plan, lists):
	"""Where the wiki shows the item: a list, the search only, or neither
	(a blacklisted item opens only from a link on another page)."""
	category = plan[0]
	hand = {"costume_weapon": lists.COSTUME_WEAPONS, "costume_armor": lists.COSTUME_ARMOR,
		"costume_hair": lists.COSTUME_HAIR, "pet": lists.COSTUME_PETS, "mount": lists.COSTUME_MOUNTS}
	if category in hand and vnum in hand[category]:
		return "list"
	if vnum in lists.ITEM_BLACKLIST:
		return "link"
	return "list" if category in ("weapon", "armor") else "search"


def audit(items, mobs_proto, pack, races, models, lists, old):
	"""One row per previewable vnum: (kind, vnum, name, category, listed,
	race, cause, detail, old_has, blank races)."""
	mobs = Mobs(pack)
	rows = []
	for vnum in sorted(items):
		item = items[vnum]
		plan = item_plan(vnum, item, lists)
		if plan is None:
			continue
		where = listed(vnum, plan, lists)
		if plan[1] == "mob":
			cause, detail = part_cause(plan, None, pack, races, models, mobs)
			rows.append(("item", vnum, item[0], plan[0], where, plan[2], cause, detail,
				*old_has(cause, detail, "mob", plan[2], None, old, pack), ""))
			continue
		candidates = allowed_races(item[4])
		if not candidates:
			continue
		results = [(race,) + part_cause(plan, race, pack, races, models, mobs) for race in candidates]
		blank = [r for r in results if r[1] != OK]
		race, cause, detail = blank[0] if blank else results[0]
		rows.append(("item", vnum, item[0], plan[0], where, race, cause, detail,
			*old_has(cause, detail, plan[1], plan[2], race, old, pack),
			",".join(str(r[0]) for r in blank) + ("" if not blank or len(blank) == len(results) else " of " + ",".join(str(r[0]) for r in results))))
	for vnum in sorted(mobs_proto):
		name, rank, kind, _ = mobs_proto[vnum]
		if kind not in ("MONSTER", "STONE") or vnum in lists.MOB_BLACKLIST:
			continue
		category = "metin" if kind == "STONE" else ("boss" if rank in MOB_RANK_BOSS else "monster")
		cause, detail = mobs.cause(vnum)
		rows.append(("mob", vnum, name, category, "list", vnum, cause, detail, *old_has(cause, detail, "mob", vnum, None, old, pack), ""))
	return rows


def load_lists(repo):
	sys.path.insert(0, os.path.join(repo, "assets", "root"))
	import nui_wiki_data
	return nui_wiki_data


def load_old(packer, old_root):
	import old_art
	with open(os.path.join(old_root, "locale", "common", "item_list.txt"), "rb") as handle:
		item_list = item_list_models(handle.read())
	races = {}
	for race in race_msm.RACES:
		with open(os.path.join(old_root, "root", race + ".msm"), "rb") as handle:
			races[race] = race_msm.load(race_msm.clean_old(handle.read()), old_reader=True)
	with open(os.path.join(old_root, "root", "NpcList.py"), encoding="latin-1") as handle:
		names, folders, _ = old_content.old_npclist(handle.read())
	with open(os.path.join(old_root, "locale", "common", "item_list.txt"), "rb") as handle:
		lines, _ = old_content.item_list_lines(handle.read())
	item_list_lines = dict((vnum, old_content.split_tab(line)) for vnum, line in lines.items())
	return {"index": old_art.packer_index(packer) if packer else {}, "item_list": item_list, "races": races,
		"item_list_lines": item_list_lines,
		"mob_names": names, "mob_folders": folders}


CATEGORIES = ("weapon", "armor", "costume_weapon", "costume_armor", "costume_hair", "sash", "wing", "pet", "mount", "boss", "monster", "metin")
HEADER = ("kind", "vnum", "name", "category", "listed", "race", "cause", "detail", "fix_in", "fix_from", "blank_races")


def summary(rows):
	"""{category: {cause: count}} and {(cause, old_has): count} of the rows
	the wiki reaches by a list or the search."""
	table, old = {}, {}
	for row in rows:
		if row[4] == "link":
			continue
		causes = table.setdefault(row[3], {})
		causes[row[6]] = causes.get(row[6], 0) + 1
		if row[6] != OK:
			old[(row[6], row[8])] = old.get((row[6], row[8]), 0) + 1
	return table, old


def seeds(rows, old, pack):
	"""The store paths an import from OLD starts from, for the gaps OLD can
	fix: the model, a race shape's or hair's skins and LOD models, a mob's
	whole folder."""
	start = []
	for row in rows:
		if row[8] != "old":
			continue
		path = row[9]
		start.append(path)
		if row[6] in ("shape_missing", "hair_missing", "model_missing") and row[3] in ("armor", "costume_armor", "costume_hair"):
			kind = "hairdata" if row[3] == "costume_hair" else "shapedata"
			for race_name in race_msm.RACES:
				data = old["races"][race_name]
				store = data.hairs if kind == "hairdata" else data.shapes
				for look in store.values():
					if look[0] and old_content.store_name(look[0]) == path:
						start.extend(old_content.store_name(dst) for _, dst in look[1])
			stem = path[:-4] if path.endswith(".gr2") else path
			start.extend("%s_lod_%02d.gr2" % (stem, n) for n in (1, 2, 3))
		if path.endswith(".msm"):
			folder = path.rsplit("/", 1)[0] + "/"
			start.extend(store for store in old["index"] if store.startswith(folder) and not store.endswith(".bak"))
	seen, out = set(), []
	for path in start:
		if path not in seen and path in old["index"] and not pack.has(path):
			seen.add(path)
			out.append(path)
	return out


def _plan(repo, _item_proto, _mob_proto, packer, old_root, grlist, tsv):
	import old_art
	pack = Pack(repo)
	old = load_old(packer, old_root)
	rows = []
	with open(tsv, encoding="utf-8") as handle:
		for line in handle.read().split("\n")[1:]:
			if line:
				rows.append(line.split("\t"))
	by_category = {}
	for row in rows:
		by_category.setdefault(row[3], []).append(row)
	scratch = old_art.scratch_folder()
	grand = [0, 0]
	union = {}
	for category in CATEGORIES:
		start = seeds(by_category.get(category, []), old, pack)
		if not start:
			continue
		take, missing = old_art.closure(start, old["index"], set(pack.files), packer, grlist, scratch)
		size = sum(os.path.getsize(os.path.join(packer, source)) for source in take.values())
		union.update(take)
		grand[0] += len(take)
		grand[1] += size
		print("%s\t%d files\t%.1f MB\t%d named but missing in OLD" % (category, len(take), size / 1048576.0, len(missing)))
	print("sum\t%d files\t%.1f MB (categories counted apart: a shared file counts in each)" % (grand[0], grand[1] / 1048576.0))
	size = sum(os.path.getsize(os.path.join(packer, source)) for source in union.values())
	print("total\t%d files\t%.1f MB (each file once)" % (len(union), size / 1048576.0))
	return 0


# The commits of the import (NOVA-177, Eddy approved the whole plan): each
# well under 1 GB for GitHub; costume armor goes in two, by race folder.
BATCHES = {
	"equipment": (("weapon", "armor"), None),
	"mobs": (("pet", "mount", "boss", "monster", "metin"), None),
	"hair": (("costume_hair",), None),
	"costume_armor_1": (("costume_armor",), ("/pc/warrior/", "/pc2/warrior/", "/pc/assassin/", "/pc2/assassin/")),
	"costume_armor_2": (("costume_armor",), None),
}
MAX_FILE = 95 * 1048576


def icon_seeds(rows, old):
	"""The icons of OLD's item_list lines for the items whose line NEW lacks:
	old_content.merge_item_list adds a line only when its icon ships."""
	out = []
	for row in rows:
		if row[0] == "item" and row[6] in ("no_item_list",) and row[8] == "old":
			line = old["item_list_lines"].get(int(row[7]))
			if line:
				out.append(old_content.store_name(line[2]))
	return out


def tree_destination(spellings):
	"""old_art.destination for a sparse worktree: a folder git's tree has
	keeps the tree's spelling (it may not be on disk), a new one OLD's."""
	def destination(assets, group, spelling):
		parts = spelling.replace("\\", "/").split("/")
		if parts[0].lower() == "d:":
			parts = parts[1:]
		path = group
		for part in parts[:-1]:
			path = spellings.get((path + "/" + part).lower(), path + "/" + part)
		return os.path.join(assets, path, parts[-1])
	return destination


def race_seeds(rows, items, old, new_races, pack):
	"""Every race's files for the armor, costume body and costume hair rows:
	the audit's row names the first race that draws nothing, and each race
	file names its own model for the same value 3 (NEW's entry, else OLD's),
	with its skins and LOD models."""
	start = []
	for row in rows:
		if row[0] != "item" or row[3] not in ("armor", "costume_armor", "costume_hair") or row[6] == OK:
			continue
		item = items.get(int(row[1]))
		if item is None:
			continue
		kind = "hairdata" if row[3] == "costume_hair" else "shapedata"
		for race in allowed_races(item[4]):
			name = race_msm.RACES[race]
			for data in (new_races[name], old["races"][name]):
				look = (data.hairs if kind == "hairdata" else data.shapes).get(item[3])
				if not look or not look[0]:
					continue
				model = old_content.store_name(look[0])
				start.append(model)
				start.extend(old_content.store_name(dst) for _, dst in look[1])
				stem = model[:-4] if model.endswith(".gr2") else model
				start.extend("%s_lod_%02d.gr2" % (stem, n) for n in (1, 2, 3))
	seen, out = set(), []
	for path in start:
		if path not in seen and path in old["index"] and not pack.has(path):
			seen.add(path)
			out.append(path)
	return out


def _races(packer, old_root, grlist, tsv, item_proto, category, part, run):
	"""import (or plan, run "plan") every race's files for one category's
	rows, in two parts by race folder ("1": warrior and assassin, "2": the
	rest, "all")."""
	import old_art
	pack = Pack(old_content.REPO)
	old = load_old(packer, old_root)
	with open(item_proto, encoding="utf-8", errors="replace") as handle:
		items = proto_items(handle.read())
	new_races = {}
	for race in race_msm.RACES:
		with open(os.path.join(old_content.ASSETS, "root", "msm", race + ".msm"), "rb") as handle:
			new_races[race] = race_msm.load(handle.read())
	with open(tsv, encoding="utf-8") as handle:
		rows = [line.split("\t") for line in handle.read().split("\n")[1:] if line]
	rows = [row for row in rows if row[3] == category]
	start = race_seeds(rows, items, old, new_races, pack)
	first = ("/pc/warrior/", "/pc2/warrior/", "/pc/assassin/", "/pc2/assassin/")
	jobs = ("warrior", "assassin", "sura", "shaman")
	if part == "1":
		start = [path for path in start if any(f in path for f in first)]
	elif part == "2":
		start = [path for path in start if not any(f in path for f in first)]
	elif part in jobs:
		start = [path for path in start if "/pc/%s/" % part in path or "/pc2/%s/" % part in path]
	elif part == "rest":
		start = [path for path in start if not any("/pc/%s/" % j in path or "/pc2/%s/" % j in path for j in jobs)]
	scratch = old_art.scratch_folder()
	take, missing = old_art.closure(start, old["index"], set(pack.files), packer, grlist, scratch)
	sizes = dict((path, os.path.getsize(os.path.join(packer, source))) for path, source in take.items())
	big = max(sizes.items(), key=lambda kv: kv[1]) if sizes else ("-", 0)
	print("%s %s: %d files, %.1f MB, largest %s (%.1f MB), %d named but missing in OLD too" % (
		category, part, len(take), sum(sizes.values()) / 1048576.0, big[0], big[1] / 1048576.0, len(missing)))
	if run == "plan":
		for path in sorted(missing):
			print("  %s <- %s" % (path, missing[path]))
		return 0
	if big[1] > MAX_FILE:
		print("STOP: a file over 95 MB")
		return 3
	groups = old_art._groups()
	paths = old_art.tree_files()
	spellings = {}
	for path in paths:
		parts = path.split("/")[1:-1]
		for i in range(1, len(parts) + 1):
			spellings.setdefault("/".join(parts[:i]).lower(), "/".join(parts[:i]))
	old_art.destination = tree_destination(spellings)
	return old_art.place(packer, grlist, scratch, take, missing, old["index"], old_art.tree_group_folders(paths, groups))


def _import(packer, old_root, grlist, tsv, batch):
	"""Takes OLD's files for one batch into this worktree's groups (git add
	--sparse them afterwards), then merges OLD's item_list lines whose files
	now ship."""
	import old_art
	categories, only = BATCHES[batch]
	pack = Pack(old_content.REPO)
	old = load_old(packer, old_root)
	with open(tsv, encoding="utf-8") as handle:
		rows = [line.split("\t") for line in handle.read().split("\n")[1:] if line]
	rows = [row for row in rows if row[3] in categories]
	if only:
		rows = [row for row in rows if any(part in row[9] for part in only)]
	elif batch == "costume_armor_2":
		first = BATCHES["costume_armor_1"][1]
		rows = [row for row in rows if not any(part in row[9] for part in first)]
	start = seeds(rows, old, pack) + [path for path in icon_seeds(rows, old) if path in old["index"] and not pack.has(path)]
	scratch = old_art.scratch_folder()
	take, missing = old_art.closure(start, old["index"], set(pack.files), packer, grlist, scratch)
	sizes = dict((path, os.path.getsize(os.path.join(packer, source))) for path, source in take.items())
	big = sorted((size, path) for path, size in sizes.items())[-1:] if sizes else []
	print("%s: %d files, %.1f MB, largest %s (%.1f MB)" % (batch, len(take), sum(sizes.values()) / 1048576.0,
		big[0][1] if big else "-", big[0][0] / 1048576.0 if big else 0))
	if big and big[0][0] > MAX_FILE:
		print("STOP: a file over 95 MB")
		return 3
	groups = old_art._groups()
	paths = old_art.tree_files()
	spellings = {}
	for path in paths:
		parts = path.split("/")[1:-1]
		for i in range(1, len(parts) + 1):
			spellings.setdefault("/".join(parts[:i]).lower(), "/".join(parts[:i]))
	old_art.destination = tree_destination(spellings)
	code = old_art.place(packer, grlist, scratch, take, missing, old["index"], old_art.tree_group_folders(paths, groups))
	return code


def merge_item_list(old_root, cut_proto):
	"""OLD's item_list lines for the cut's items NEW's list lacks, when the
	files they name ship (old_content.merge_item_list's rule, on git's tree:
	a sparse worktree's disk lacks most groups). They go after every line the
	list has, so the lines added since the cut by hand (NOVA-20's glowing
	sash models, NOVA-24's pet items) stay; the fixture's "added" grows."""
	import old_art
	with open(os.path.join(old_root, "locale", "common", "item_list.txt"), "rb") as handle:
		old_data = handle.read()
	with open(cut_proto, encoding="utf-8", errors="replace") as handle:
		cut_vnums = old_content.cut_item_vnums(handle.read())
	with open(old_content.ITEM_LIST, "rb") as handle:
		current = handle.read()
	files = old_art.tree_published(old_art.tree_files(), old_art._groups())
	data, report = old_content.merge_item_list(current, old_data, cut_vnums, files)
	entry = old_content.load_fixture()["item_list"]
	entry["added"] = entry["added"] + report["added"]
	with open(old_content.ITEM_LIST, "wb") as handle:
		handle.write(data)
	old_content.save_fixture("item_list", entry)
	print("item_list: %d of OLD's lines added now, %d in all, %d withheld" % (
		len(report["added"]), len(entry["added"]), report["withheld"]))
	return 0


# NOVA-177 follow-up (r44: the barter TreasureBox 55022 stood invisible): every
# race the server spawns, not only the wiki's lists.
SPAWN_FILES = ("npc.txt", "regen.txt", "boss.txt", "stone.txt")


def _groups_of(text):
	"""{group vnum: [member race vnums]} of a group.txt or group_group.txt:
	each Group's Vnum, its Leader's and its numbered rows' last cell."""
	groups, current, members = {}, None, []
	for raw in text.split("\n"):
		cells = [cell for cell in raw.strip().replace('"', " ").split() if cell]
		if not cells:
			continue
		head = cells[0].lower()
		if head == "group":
			current, members = None, []
		elif head == "vnum" and len(cells) > 1:
			current = int(cells[1])
			groups[current] = members
		elif head == "leader" or head.isdigit():
			if cells[-1].isdigit():
				members.append(int(cells[-1]))
	return groups


def _group_group(text):
	"""group_group.txt: {vnum: [group vnums]} (rows "n group_vnum weight")."""
	groups, current = {}, None
	for raw in text.split("\n"):
		cells = raw.split()
		if not cells:
			continue
		if cells[0].lower() == "group":
			current = None
		elif cells[0].lower() == "vnum" and len(cells) > 1:
			current = int(cells[1])
			groups[current] = []
		elif cells[0].isdigit() and current is not None and len(cells) >= 2 and cells[1].isdigit():
			groups[current].append(int(cells[1]))
	return groups


def spawned_races(map_dir, group_text, group_group_text, shop_sqls=()):
	"""{race vnum: set of where it comes from} for every spawn line of every
	map (m and s: the race; g: its group's members; r: the members of each
	group of its group_group) and every shop row's NPC."""
	import re
	groups = {}
	for vnum, members in _groups_of(group_text).items():
		groups[vnum] = members
	group_groups = _group_group(group_group_text)
	where = {}

	def add(race, origin):
		if race:
			where.setdefault(race, set()).add(origin)
	for map_name in sorted(os.listdir(map_dir)):
		for name in SPAWN_FILES:
			path = os.path.join(map_dir, map_name, name)
			if not os.path.isfile(path):
				continue
			with open(path, encoding="latin-1") as handle:
				for line in handle:
					cells = line.split()
					if len(cells) < 11 or cells[0] not in ("m", "s", "g", "r") or not cells[10].isdigit():
						continue
					vnum, origin = int(cells[10]), "%s/%s" % (map_name, name)
					if cells[0] in ("m", "s"):
						add(vnum, origin)
					elif cells[0] == "g":
						for race in groups.get(vnum, ()):
							add(race, origin)
					else:
						for group in group_groups.get(vnum, ()):
							for race in groups.get(group, ()):
								add(race, origin)
	for sql in shop_sqls:
		with open(sql, encoding="utf-8", errors="replace") as handle:
			for vnum, npc in re.findall(r"\(\s*(\d+)\s*,\s*'[^']*'\s*,\s*(\d+)\s*\)", handle.read()):
				add(int(npc), "shop %s" % vnum)
	return where


def _spawns(repo, map_dir, group, group_group, shop_sqls, packer, old_root, out):
	pack = Pack(repo, os.environ.get("MODEL_GAPS_FALLBACK"))
	with open(group, encoding="latin-1") as handle:
		group_text = handle.read()
	with open(group_group, encoding="latin-1") as handle:
		group_group_text = handle.read()
	where = spawned_races(map_dir, group_text, group_group_text, [path for path in shop_sqls.split(",") if path])
	mobs = Mobs(pack)
	old = load_old(packer, old_root)
	rows = []
	for race in sorted(where):
		cause, detail = mobs.cause(race)
		fix = old_has(cause, detail, "mob", race, None, old, pack) if cause != OK else ("-", "")
		rows.append((race, mobs.names.get(race, ""), cause, detail) + tuple(fix) + (";".join(sorted(where[race]))[:300],))
	with open(out, "w", encoding="utf-8", newline="\n") as handle:
		handle.write("race\tnpclist_name\tcause\tdetail\tfix_in\tfix_from\tspawned_by\n")
		for row in rows:
			handle.write("\t".join(str(cell) for cell in row) + "\n")
	counts = {}
	for row in rows:
		counts[(row[2], row[4])] = counts.get((row[2], row[4]), 0) + 1
	print("%d races spawned or selling" % len(rows))
	for key in sorted(counts):
		print("%s, fix in %s\t%d" % (key[0], key[1], counts[key]))
	return 0


def _spawn_import(packer, old_root, grlist, tsv):
	"""Takes OLD's folders for the spawned races OLD can fix (spawns TSV):
	the msm's folder and its base model's."""
	import old_art
	pack = Pack(old_content.REPO)
	old = load_old(packer, old_root)
	with open(tsv, encoding="utf-8") as handle:
		rows = [line.split("\t") for line in handle.read().split("\n")[1:] if line]
	start = []
	for row in rows:
		if row[4] != "old":
			continue
		paths = [row[5]]
		if row[2] in ("model_missing", "model_unreadable") and row[3]:
			paths.append(old_content.store_name(row[3]))
		for path in paths:
			start.append(path)
			folder = path.rsplit("/", 1)[0] + "/"
			start.extend(store for store in old["index"] if store.startswith(folder) and not store.endswith(".bak"))
	start = [path for path in dict.fromkeys(start) if path in old["index"] and not pack.has(path)]
	scratch = old_art.scratch_folder()
	take, missing = old_art.closure(start, old["index"], set(pack.files), packer, grlist, scratch)
	sizes = dict((path, os.path.getsize(os.path.join(packer, source))) for path, source in take.items())
	big = max(sizes.items(), key=lambda kv: kv[1]) if sizes else ("-", 0)
	print("spawns: %d files, %.1f MB, largest %s (%.1f MB)" % (len(take), sum(sizes.values()) / 1048576.0, big[0], big[1] / 1048576.0))
	if os.environ.get("MODEL_GAPS_PLAN"):
		for path in sorted(missing):
			print("  %s <- %s" % (path, missing[path]))
		return 0
	if big[1] > MAX_FILE or sum(sizes.values()) > 500 * 1048576:
		print("STOP: over 95 MB a file or 500 MB in all")
		return 3
	paths = old_art.tree_files()
	spellings = {}
	for path in paths:
		parts = path.split("/")[1:-1]
		for i in range(1, len(parts) + 1):
			spellings.setdefault("/".join(parts[:i]).lower(), "/".join(parts[:i]))
	old_art.destination = tree_destination(spellings)
	return old_art.place(packer, grlist, scratch, take, missing, old["index"], old_art.tree_group_folders(paths, old_art._groups()))


def _main(argv):
	if len(argv) == 8 and argv[0] == "plan":
		return _plan(*argv[1:])
	if len(argv) == 9 and argv[0] == "spawns":
		return _spawns(*argv[1:])
	if len(argv) == 5 and argv[0] == "spawn-import":
		return _spawn_import(*argv[1:])
	if len(argv) == 9 and argv[0] == "races":
		return _races(*argv[1:])
	if len(argv) == 6 and argv[0] == "import":
		return _import(*argv[1:])
	if len(argv) == 3 and argv[0] == "item_list":
		return merge_item_list(*argv[1:])
	if len(argv) != 7 or argv[0] != "audit":
		print(__doc__)
		return 2
	repo, item_proto, mob_proto, packer, old_root, out = argv[1:]
	pack = Pack(repo, os.environ.get("MODEL_GAPS_FALLBACK"))
	with open(item_proto, encoding="utf-8", errors="replace") as handle:
		items = proto_items(handle.read())
	with open(mob_proto, encoding="utf-8", errors="replace") as handle:
		mobs = proto_mobs(handle.read())
	races = dict((race, race_msm.load(pack.read("msm/%s.msm" % race))) for race in race_msm.RACES)
	models = item_list_models(pack.read("locale/common/item_list.txt"))
	rows = audit(items, mobs, pack, races, models, load_lists(repo), load_old(packer, old_root))
	with open(out, "w", encoding="utf-8", newline="\n") as handle:
		handle.write("\t".join(HEADER) + "\n")
		for row in rows:
			handle.write("\t".join(str(cell).replace("\t", " ") for cell in row) + "\n")
	table, old = summary(rows)
	causes = sorted(set(cause for counts in table.values() for cause in counts))
	print("category\t" + "\t".join(causes) + "\ttotal")
	for category in CATEGORIES:
		counts = table.get(category, {})
		print(category + "\t" + "\t".join(str(counts.get(cause, 0)) for cause in causes) + "\t" + str(sum(counts.values())))
	for key in sorted(old):
		print("gap %s, fix in %s\t%d" % (key[0], key[1], old[key]))
	return 0


if __name__ == "__main__":
	sys.exit(_main(sys.argv[1:]))
