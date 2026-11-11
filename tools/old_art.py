"""OLD's art for the items of wave 6 (NOVA-19 to 23): the files OLD's
item_list lines name for the quivers, sashes, weapon costumes and auras of
the cut's item_proto that NEW's list lacks, the sash effects and the quiver's
bow attack (EXTRA), and every texture, effect, mesh and motion those name in
turn, taken from OLD's client source into the asset groups. Since the NOVA-20
follow-up it takes the wings too (COSTUME_SASH2): their item_list lines, the
effects NEW's locale/common/shiningtable.txt gives them, and the models and
skins of the race shapes (the msm files' WingData groups) their value 3 names.

	python3 tools/old_art.py plan PACKER OLD_ITEM_LIST CUT_ITEM_PROTO GRLIST
	python3 tools/old_art.py import PACKER OLD_ITEM_LIST CUT_ITEM_PROTO GRLIST
	python3 tools/old_art.py shop-plan PACKER GRLIST
	python3 tools/old_art.py shop PACKER GRLIST
	python3 tools/old_art.py rings-plan PACKER GRLIST
	python3 tools/old_art.py rings PACKER GRLIST

shop and shop-plan take the offline shop's decoration (NOVA-170) instead: the
NPC models shop_deco.txt's type 1 rows name (by NEW's npclist folder for each
vnum: the msm, its base model, motlist.txt and the motions it lists) and the
eight parts of each type 2 row's sign pattern. rings and rings-plan take
OLD's select and target rings (NOVA-127, RINGS) and what they name. Both
read NEW's files and groups from git's tree, so they work in a sparse
worktree; add what they write with `git add --sparse`.

plan lists what an import would take (files and MB by kind) and writes
nothing. OLD_ART_SCRATCH names a folder grlist (a Windows program) can read and
write, for its listings and converted models (default tools/; a worktree on
WSL's own disk needs one on a Windows drive).

PACKER is OLD's packer folder: xml/<pack>_create.xml names the store path of
each file under source/ (Lunika Compile-64/CRYPTION). OLD_ITEM_LIST and
CUT_ITEM_PROTO are old_content.py's. GRLIST is tools/old_art/grlist.exe,
built against nova-client-src's Granny (tools/old_art/CMakeLists.txt).

Most of OLD's newer models are OLD's custom Granny files (type tag
0x71000039, OLD Tools/preproc ConvertToCustom), which NEW's loader reads as
empty; grlist writes them as standard files the way OLD's loader reads them
(OLD EterGrnLib/Thing.cpp GetMyFileInfo). Every other file is copied as it
is. A file NEW's groups already publish is never written. The manifest
(tools/fixtures/old_art.tsv) lists each file taken: store path, file under
assets/, OLD's source and how it was taken; a run adds its rows to it. Run old_content.py item_list afterwards so the
lines whose files now ship are added.
"""
import os
import re
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import old_content  # noqa: E402

MANIFEST = os.path.join(old_content.REPO, "tools", "fixtures", "old_art.tsv")
SUB_TYPES = ("COSTUME_WEAPON", "COSTUME_SASH", "COSTUME_AURA", "WEAPON_UNLIMITED_ARROW", "COSTUME_SASH2")
# The wings' shining effects and race shapes (NOVA-20 follow-up).
SHINING_TABLE = os.path.join(old_content.ASSETS, "locale", "locale", "common", "shiningtable.txt")
MSM_FOLDER = os.path.join(old_content.ASSETS, "root", "msm")
# OLD playerSettingModule.py:283-284 (the sash's combine and equip effects),
# :588 (its glow, EFFECT_REFINED + 21) and :1587 (the quiver's bow attack).
EXTRA = (
	"d:/ymir work/effect/etc/buff/buff_item6.mse",
	"d:/ymir work/effect/etc/buff/buff_item7.mse",
	"d:/ymir work/pc/common/effect/armor/acc_01.mse",
	"d:/ymir work/pc/assassin/bow/attack_special.msa",
	"d:/ymir work/pc2/assassin/bow/attack_special.msa",
)
# Store folders OLD has and NEW's groups lack go with the items.
DEFAULT_GROUP = "item"
CUSTOM_TAG = 0x71000039
TEXT_KINDS = (".mse", ".msa", ".mss", ".mde", ".msf")
REFERENCE = re.compile(
	rb"[A-Za-z0-9_:/\\. \-()]{1,200}?\.(?:dds|tga|png|jpg|jpeg|bmp|mse|mde|gr2|msa|mss|wav|mp3|msf|spt|sub)\b", re.I)
FILE_ENTRY = re.compile(r'<File ArchivedPath="([^"]*)"><!\[CDATA\[([^\]]*)\]\]>')


def store_path(name, referrer):
	"""The store path a reference names: an absolute one as it is (a drive
	before 'ymir work' read as d:), a relative one in its referrer's folder,
	as CGrannyMaterial::__GetImagePointer and the effect loaders do."""
	path = old_content.store_name(name.strip().strip('"'))
	while "//" in path:
		path = path.replace("//", "/")
	if len(path) > 1 and path[1] == ":":
		return "d:" + path[2:] if path[2:].startswith("/ymir work/") else path
	if path.startswith("ymir work/"):
		return "d:/" + path
	if path.startswith(("icon/", "locale/")):
		return path
	return referrer.rsplit("/", 1)[0] + "/" + path


def references(data, referrer):
	"""The files a text script (effect, motion, sound, mesh effect) names."""
	found = []
	for hit in REFERENCE.findall(data):
		name = re.split(r'["\t]', hit.decode("latin-1"))[-1].strip()
		if name and not name.startswith("."):
			found.append(store_path(name, referrer))
	return found


def packer_index(packer):
	"""Store path -> (OLD's spelling, source path under the packer)."""
	index = {}
	folder = os.path.join(packer, "xml")
	for name in sorted(os.listdir(folder)):
		if not name.endswith("_create.xml"):
			continue
		with open(os.path.join(folder, name), encoding="latin-1") as handle:
			for archived, source in FILE_ENTRY.findall(handle.read()):
				archived = archived.replace("\\", "/")
				index[old_content.store_name(archived)] = (archived, source.replace("\\", "/"))
	return index


def item_sub_types(text):
	"""vnum -> SUB_TYPE of an item_proto.txt's single-vnum rows."""
	kinds = {}
	for row in text.split("\n")[1:]:
		cells = row.split("\t")
		if len(cells) > 3 and cells[0].strip().isdigit():
			kinds[int(cells[0])] = cells[3].strip()
	return kinds


def seeds(old_data, proto_text, new_data, files):
	"""The files OLD's lines name for the cut's items of SUB_TYPES that NEW's
	list lacks and NEW's groups do not publish, then EXTRA."""
	kinds = item_sub_types(proto_text)
	new, _ = old_content.item_list_lines(new_data)
	wanted = []
	for line in old_content.lines_of(old_data):
		tokens = old_content.split_tab(line)
		if tokens is None or len(tokens) not in (3, 4, 5):
			continue
		vnum = old_content.atoi(tokens[0])
		if vnum in new or kinds.get(vnum) not in SUB_TYPES:
			continue
		wanted.extend(old_content.store_name(path) for path in tokens[2:])
	wanted.extend(EXTRA)
	out = []
	for path in wanted:
		if path not in files and path not in out:
			out.append(path)
	return out


def wing_shapes(proto_text):
	"""The value 3 of the cut's wings (COSTUME_SASH2): the race shape each
	wears (OLD CActorInstance::AttachSash, CRaceData::FindWing)."""
	rows = proto_text.split("\n")
	header = rows[0].split("\t")
	column = header.index("VALUE3")
	shapes = set()
	for row in rows[1:]:
		cells = row.split("\t")
		if len(cells) > column and cells[3].strip() == "COSTUME_SASH2":
			shapes.add(old_content.atoi(cells[column]))
	return shapes


def shining_seeds(data):
	"""The effects a shiningtable.txt names (OLD CItemManager::
	LoadShiningTable: a vnum or a range, then up to six effects, each with
	an optional #bone)."""
	out = []
	for line in old_content.lines_of(data):
		tokens = old_content.split_tab(line)
		for token in (tokens or [])[1:]:
			path = store_path(token.split("#")[0], "")
			if path not in out:
				out.append(path)
	return out


MSM_TOKEN = re.compile(r'"[^"]*"|[{}]|[^\s{}"]+')


def wing_shape_seeds(msm_texts, shapes):
	"""The model and the skins of each WingData group whose WingIndex is in
	`shapes`, read as OLD's loader reads them (OLD RaceDataFile.cpp:653-815):
	PathName before the model, a SpecialPath replacing it for that group and
	the ones after it, a TargetSkin after the path, a CommonTargetSkin as it
	is."""
	out = []
	for text in msm_texts:
		if isinstance(text, bytes):
			text = text.decode("latin-1")
		tokens = [token.strip('"') if token.startswith('"') else token for token in MSM_TOKEN.findall(text)]
		groups, depth, path, entry = [], 0, "", None
		i = 0
		while i < len(tokens):
			token = tokens[i]
			low = token.lower()
			if low == "group" and i + 1 < len(tokens):
				groups.append(tokens[i + 1].lower())
				i += 2
				continue
			if token == "{":
				depth += 1
				if len(groups) >= 2 and groups[-2] == "wingdata" and groups[-1].startswith("wingdata"):
					entry = {}
			elif token == "}":
				depth -= 1
				if entry is not None and groups and groups[-1].startswith("wingdata") and len(groups) >= 2:
					if old_content.atoi(entry.get("wingindex", "0")) in shapes:
						if "model" in entry:
							out.append(old_content.store_name(path + entry["model"]))
						for key in ("targetskin", "targetskin2"):
							if key in entry:
								out.append(old_content.store_name(path + entry[key]))
						for key in ("commontargetskin", "commontargetskin2", "commontargetskin3",
								"commontargetskin4", "commontargetskin5"):
							if key in entry:
								out.append(old_content.store_name(entry[key]))
					entry = None
				if groups:
					groups.pop()
			elif i + 1 < len(tokens) and tokens[i + 1] not in ("{", "}"):
				if groups and groups[-1] == "wingdata" and entry is None and low == "pathname":
					path = tokens[i + 1]
				elif entry is not None:
					if low == "specialpath":
						path = tokens[i + 1]
					else:
						entry[low] = tokens[i + 1]
				i += 2
				continue
			i += 1
	result = []
	for item in out:
		item = store_path(item, "")
		if item not in result:
			result.append(item)
	return result


def wing_seeds(proto_text):
	"""What the wings need beyond their item_list lines: NEW's shining
	table's effects and the models and skins of their race shapes."""
	found = []
	if os.path.exists(SHINING_TABLE):
		with open(SHINING_TABLE, "rb") as handle:
			found.extend(shining_seeds(handle.read()))
	texts = []
	if os.path.isdir(MSM_FOLDER):
		for name in sorted(os.listdir(MSM_FOLDER)):
			if name.lower().endswith(".msm"):
				with open(os.path.join(MSM_FOLDER, name), "rb") as handle:
					texts.append(handle.read())
	found.extend(wing_shape_seeds(texts, wing_shapes(proto_text)))
	return found


def merge_rows(kept, added):
	"""The manifest's rows after a run: the rows it had, and the run's for
	store paths it did not have, in store path order."""
	rows = dict((row[0], tuple(row)) for row in added)
	rows.update((row[0], tuple(row)) for row in kept)
	return [rows[path] for path in sorted(rows)]


def group_folders(assets, groups):
	"""Store folder -> {group: files under it}, for every folder of every group."""
	folders = {}
	for group in groups:
		top = os.path.join(assets, group)
		for folder, _, names in os.walk(top):
			if not names:
				continue
			relative = old_content.store_name(os.path.relpath(folder, top))
			if relative.startswith("ymir work"):
				relative = "d:/" + relative
			parts = relative.split("/")
			for i in range(1, len(parts) + 1):
				counts = folders.setdefault("/".join(parts[:i]), {})
				counts[group] = counts.get(group, 0) + len(names)
	return folders


def choose_group(store, folders):
	"""The group with the most files in the nearest folder of `store` that a
	group has (the drive and 'ymir work' themselves do not count)."""
	parts = store.split("/")[:-1]
	for i in range(len(parts), 0, -1):
		folder = "/".join(parts[:i])
		if folder in folders and folder not in ("d:", "d:/ymir work"):
			counts = folders[folder]
			return max(sorted(counts), key=lambda group: counts[group])
	return DEFAULT_GROUP


def destination(assets, group, spelling):
	"""Where `spelling` (OLD's store path) goes under `group`: each folder
	that exists keeps its spelling on disk, a new one takes OLD's."""
	path = os.path.join(assets, group)
	parts = spelling.replace("\\", "/").split("/")
	if parts[0].lower() == "d:":
		parts = parts[1:]
	for part in parts[:-1]:
		here = {name.lower(): name for name in os.listdir(path)} if os.path.isdir(path) else {}
		path = os.path.join(path, here.get(part.lower(), part))
	return os.path.join(path, parts[-1])


def granny_tag(path):
	"""The type tag of a Granny file's header (0 for anything shorter)."""
	with open(path, "rb") as handle:
		head = handle.read(72)
	return struct.unpack_from("<I", head, 68)[0] if len(head) >= 72 else 0


def windows(path):
	"""A /mnt/<drive>/ path as Windows names it, for grlist."""
	parts = os.path.abspath(path).split("/")
	if len(parts) > 3 and parts[1] == "mnt" and len(parts[2]) == 1:
		return parts[2].upper() + ":\\" + "\\".join(parts[3:])
	return path


def run_grlist(grlist, mode, rows, scratch):
	listing = os.path.join(scratch, "old_art_%s.txt" % mode)
	with open(listing, "w", newline="\r\n") as handle:
		for row in rows:
			handle.write("\t".join(windows(path) for path in row) + "\n")
	done = subprocess.run([grlist, mode, windows(listing)], capture_output=True)
	os.remove(listing)
	return [line.split("\t") for line in done.stdout.decode("latin-1").splitlines()], done.returncode


def closure(start, index, files, packer, grlist, scratch):
	"""Every store path `start` needs that NEW lacks: {store: source} and
	{store: referrer} for those OLD lacks too."""
	take, missing, seen = {}, {}, set()
	queue = [(path, "") for path in start]
	while queue:
		models, following = [], []
		for path, referrer in queue:
			if path in seen or path in files:
				continue
			seen.add(path)
			if path not in index:
				missing[path] = referrer
				continue
			source = os.path.join(packer, index[path][1])
			take[path] = index[path][1]
			if path.endswith(".gr2"):
				models.append(path)
			elif path.endswith(TEXT_KINDS):
				with open(source, "rb") as handle:
					following.extend((name, path) for name in references(handle.read(), path))
		if models:
			by_source = {windows(os.path.join(packer, index[path][1])).lower(): path for path in models}
			rows, _ = run_grlist(grlist, "list", [(os.path.join(packer, index[path][1]),) for path in models], scratch)
			for row in rows:
				if len(row) == 3 and row[1] in ("diffuse", "opacity", "texture"):
					model = by_source[row[0].lower()]
					following.append((store_path(row[2], model), model))
		queue = following
	return take, missing


def scratch_folder():
	folder = os.environ.get("OLD_ART_SCRATCH") or os.path.join(old_content.REPO, "tools")
	os.makedirs(folder, exist_ok=True)
	return folder


def gather(packer, old_item_list, cut_proto, grlist, scratch):
	"""What a run takes: ({store: source}, {store: referrer} missing in OLD
	too, the packer index, NEW's published files)."""
	files = old_content.published_files()
	with open(old_item_list, "rb") as handle:
		old_data = handle.read()
	with open(cut_proto, encoding="utf-8", errors="replace") as handle:
		proto_text = handle.read()
	with open(old_content.ITEM_LIST, "rb") as handle:
		new_data = old_content.news_part(handle.read(), "item_list")
	index = packer_index(packer)
	start = seeds(old_data, proto_text, new_data, files)
	start += [path for path in wing_seeds(proto_text) if path not in files and path not in start]
	take, missing = closure(start, index, files, packer, grlist, scratch)
	return take, missing, index, files


def kind_of(path):
	return os.path.splitext(path)[1].lower() or "(none)"


def plan_art(packer, old_item_list, cut_proto, grlist):
	scratch = scratch_folder()
	take, missing, _, _ = gather(packer, old_item_list, cut_proto, grlist, scratch)
	kinds, total, custom = {}, 0, 0
	for path in take:
		source = os.path.join(packer, take[path])
		size = os.path.getsize(source)
		count, sizes = kinds.get(kind_of(path), (0, 0))
		kinds[kind_of(path)] = (count + 1, sizes + size)
		total += size
		if path.endswith(".gr2") and granny_tag(source) == CUSTOM_TAG:
			custom += 1
	print("would take %d files, %.1f MB (%d models to convert):" % (len(take), total / 1048576.0, custom))
	for kind in sorted(kinds, key=lambda kind: -kinds[kind][1]):
		print("  %-6s %6d files %9.1f MB" % (kind, kinds[kind][0], kinds[kind][1] / 1048576.0))
	print("%d named but missing in OLD too:" % len(missing))
	for path in sorted(missing):
		print("  %s <- %s" % (path, missing[path] or "item_list"))
	return 0


def import_art(packer, old_item_list, cut_proto, grlist):
	assets = old_content.ASSETS
	scratch = scratch_folder()
	take, missing, index, _ = gather(packer, old_item_list, cut_proto, grlist, scratch)
	folders = group_folders(assets, _groups())
	return place(packer, grlist, scratch, take, missing, index, folders)


def place(packer, grlist, scratch, take, missing, index, folders, group_of=None):
	"""Writes each file taken into its group (a custom Granny file converted
	by grlist) and adds its rows to the manifest."""
	assets = old_content.ASSETS
	rows, converts, placed = [], [], []
	for path in sorted(take):
		group = (group_of or choose_group)(path, folders)
		source = os.path.join(packer, take[path])
		target = destination(assets, group, index[path][0])
		os.makedirs(os.path.dirname(target), exist_ok=True)
		if path.endswith(".gr2") and granny_tag(source) == CUSTOM_TAG:
			# grlist writes into the scratch folder, which it can reach.
			converted = os.path.join(scratch, "old_art_%d.gr2" % len(converts))
			converts.append((source, converted))
			placed.append((converted, target))
			how = "converted"
		else:
			with open(source, "rb") as src, open(target, "wb") as out:
				out.write(src.read())
			how = "copied"
		rows.append((path, os.path.relpath(target, assets).replace(os.sep, "/"), take[path], how))
	failed = []
	for kind in ("convert", "compare"):
		results, code = run_grlist(grlist, kind, converts, scratch)
		failed += [row for row in results if len(row) == 3 and row[1] in ("ERROR", "DIFFERENT")]
		if code and not failed:
			failed.append(("grlist", kind, "exit %d" % code))
	for converted, target in placed:
		if os.path.exists(converted):
			with open(converted, "rb") as src, open(target, "wb") as out:
				out.write(src.read())
			os.remove(converted)
		else:
			failed.append((converted, "ERROR", "not written"))
	kept = []
	if os.path.exists(MANIFEST):
		with open(MANIFEST, encoding="utf-8") as handle:
			kept = [line.rstrip("\n").split("\t") for line in handle if line.strip() and not line.startswith("#")]
	with open(MANIFEST, "w", encoding="utf-8", newline="\n") as handle:
		handle.write("# store path\tfile under assets/\tOLD source (under the packer folder)\thow\n")
		for row in merge_rows(kept, rows):
			handle.write("\t".join(row) + "\n")
	print("took %d files (%d converted), %d named but missing in OLD too:" % (
		len(rows), len(converts), len(missing)))
	for path in sorted(missing):
		print("  %s <- %s" % (path, missing[path] or "item_list"))
	for row in failed:
		print("FAILED: %s" % "\t".join(row))
	return 1 if failed else 0


# --- the offline shop's decoration (NOVA-170) -------------------------------

# The eight parts of a sign pattern (OLD ui.py:6913-6916 ShopDecoTitle).
PATTERN_PARTS = ("left_top", "left_bottom", "right_top", "right_bottom", "left", "right", "top", "bottom")
SHOP_DECO = os.path.join(old_content.ASSETS, "locale", "locale", "common", "shop_deco.txt")
NPC_LIST = os.path.join(old_content.ASSETS, "root", "npclist.txt")
# Where CRaceManager looks for an npclist name's folder.
NPC_FOLDERS = ("npc", "npc2", "monster", "monster2")
BASE_MODEL = re.compile(rb'BaseModelFileName\s+"([^"]+)"', re.I)
EFFECT_SCRIPT = re.compile(rb'EffectScriptName\s+"([^"]+)"', re.I)


def _rows(data):
	for line in data.decode("latin-1").splitlines():
		cells = [cell.strip() for cell in line.split("\t")]
		if cells and cells[0]:
			yield cells


def shop_seeds(deco_data, npclist_data, index, packer, files):
	"""The store paths shop_deco.txt names that NEW lacks: for each type 1
	row, the effects its vnum's model attaches (the msm's EffectScriptName,
	OLD's p_shop_*.mse; even when NEW ships the model) and, when NEW lacks
	the model, the model (the msm in the npclist name's folder, the base
	model it names, motlist.txt and the motions that lists); for each type 2
	row, its pattern's eight parts."""
	names = {}
	for cells in _rows(npclist_data):
		if len(cells) >= 2 and cells[0].isdigit():
			names[int(cells[0])] = cells[1].lower()
	out = []

	def add(path):
		if path not in files and path not in out:
			out.append(path)

	for cells in _rows(deco_data):
		if cells[0] == "1" and len(cells) >= 3 and cells[2].isdigit():
			name = names.get(int(cells[2]))
			if not name:
				continue
			shipped = any("d:/ymir work/%s/%s/%s.msm" % (top, name, name) in files for top in NPC_FOLDERS)
			for top in NPC_FOLDERS:
				folder = "d:/ymir work/%s/%s/" % (top, name)
				msm = folder + name + ".msm"
				if msm not in index:
					continue
				with open(os.path.join(packer, index[msm][1]), "rb") as handle:
					script = handle.read()
				if not shipped:
					add(msm)
				for effect in EFFECT_SCRIPT.finditer(script):
					add(store_path(effect.group(1).decode("latin-1"), msm))
				if shipped:
					break
				base = BASE_MODEL.search(script)
				motlist = folder + "motlist.txt"
				motions = []
				if motlist in index:
					with open(os.path.join(packer, index[motlist][1]), "rb") as handle:
						for line in handle.read().decode("latin-1").splitlines():
							tokens = line.split()
							if len(tokens) >= 3 and tokens[2].lower().endswith(".msa"):
								motions.append(store_path(tokens[2], motlist))
					add(motlist)
				if base:
					add(store_path(base.group(1).decode("latin-1"), msm))
				for motion in motions:
					add(motion)
				break
		elif cells[0] == "2" and len(cells) >= 3:
			pattern = old_content.store_name(cells[2])
			for part in PATTERN_PARTS:
				add("%s_%s.tga" % (pattern, part))
	return out


NUMBERED_FOLDER = re.compile(r"(d:/ymir work/[^/]+/[^/]+?)_\d+/")


def shop_group(path, folders):
	"""choose_group, but a numbered model folder (privateshop_3) goes with
	the group of its base folder (privateshop) when NEW has one."""
	match = NUMBERED_FOLDER.match(path)
	if match and match.group(1) in folders:
		return choose_group(match.group(1) + "/x", folders)
	return choose_group(path, folders)


def tree_files():
	"""Every file of git's tree under assets/ (a sparse worktree has only
	some on disk)."""
	done = subprocess.run(["git", "-C", old_content.REPO, "ls-files", "-z", "--", "assets"], capture_output=True, check=True)
	return [path for path in done.stdout.decode("utf-8", "replace").split("\0") if path]


def _tree_store(path, groups):
	"""(group, store path) of a tree path assets/<group>/<path>, or None."""
	parts = path.split("/")
	if len(parts) < 3 or parts[0] != "assets" or parts[1] not in groups:
		return None
	relative = old_content.store_name("/".join(parts[2:]))
	if relative.startswith("ymir work/"):
		relative = "d:/" + relative
	return parts[1], relative


def tree_group_folders(paths, groups):
	"""group_folders, from tree paths instead of the disk."""
	folders = {}
	for path in paths:
		found = _tree_store(path, groups)
		if not found:
			continue
		group, relative = found
		parts = relative.split("/")[:-1]
		for i in range(1, len(parts) + 1):
			counts = folders.setdefault("/".join(parts[:i]), {})
			counts[group] = counts.get(group, 0) + 1
	return folders


def tree_published(paths, groups):
	"""published_files, from tree paths instead of the disk."""
	return set(found[1] for found in (_tree_store(path, groups) for path in paths) if found)


def _groups():
	with open(os.path.join(old_content.ASSETS, "groups.txt"), encoding="utf-8") as handle:
		return [line for line in (raw.split("#")[0].strip() for raw in handle) if line]


def shop_gather(packer, grlist, scratch):
	groups = _groups()
	paths = tree_files()
	files = tree_published(paths, groups)
	index = packer_index(packer)
	with open(SHOP_DECO, "rb") as handle:
		deco = handle.read()
	with open(NPC_LIST, "rb") as handle:
		npclist = handle.read()
	start = shop_seeds(deco, npclist, index, packer, files)
	take, missing = closure(start, index, files, packer, grlist, scratch)
	return take, missing, index, tree_group_folders(paths, groups)


def plan_shop(packer, grlist):
	take, missing, _, _ = shop_gather(packer, grlist, scratch_folder())
	for path in sorted(take):
		print("  %s <- %s" % (path, take[path]))
	print("would take %d files; %d named but missing in OLD too:" % (len(take), len(missing)))
	for path in sorted(missing):
		print("  %s <- %s" % (path, missing[path]))
	return 0


def import_shop(packer, grlist):
	scratch = scratch_folder()
	take, missing, index, folders = shop_gather(packer, grlist, scratch)
	return place(packer, grlist, scratch, take, missing, index, folders, shop_group)


# --- the select and target rings (NOVA-127) ----------------------------------

# OLD playerSettingModule.py:295-302: each empire's ring and the monsters',
# for the hover (select) and the clicked target (glow_select).
RINGS = tuple("d:/ymir work/effect/world/%s_%sselect.mse" % (who, glow)
	for who in ("shinsoo", "chunjo", "jinnos", "mob") for glow in ("", "glow_"))


def ring_seeds(files):
	"""The rings NEW does not publish."""
	return [path for path in RINGS if path not in files]


def git_blob(tree_path):
	"""A file of git's index (the tree tree_files lists), read where a
	sparse worktree has none on disk."""
	done = subprocess.run(["git", "-C", old_content.REPO, "show", ":" + tree_path], capture_output=True, check=True)
	return done.stdout


def rings_gather(packer, grlist, scratch):
	groups = _groups()
	paths = tree_files()
	files = tree_published(paths, groups)
	index = packer_index(packer)
	take, missing = closure(ring_seeds(files), index, files, packer, grlist, scratch)
	return take, missing, index, tree_group_folders(paths, groups)


def plan_rings(packer, grlist):
	take, missing, _, _ = rings_gather(packer, grlist, scratch_folder())
	for path in sorted(take):
		print("  %s <- %s" % (path, take[path]))
	print("would take %d files; %d named but missing in OLD too:" % (len(take), len(missing)))
	for path in sorted(missing):
		print("  %s <- %s" % (path, missing[path]))
	return 0


def import_rings(packer, grlist):
	scratch = scratch_folder()
	take, missing, index, folders = rings_gather(packer, grlist, scratch)
	return place(packer, grlist, scratch, take, missing, index, folders)


def _main(argv):
	if len(argv) == 5 and argv[0] == "import":
		return import_art(*argv[1:])
	if len(argv) == 5 and argv[0] == "plan":
		return plan_art(*argv[1:])
	if len(argv) == 3 and argv[0] == "shop":
		return import_shop(*argv[1:])
	if len(argv) == 3 and argv[0] == "shop-plan":
		return plan_shop(*argv[1:])
	if len(argv) == 3 and argv[0] == "rings":
		return import_rings(*argv[1:])
	if len(argv) == 3 and argv[0] == "rings-plan":
		return plan_rings(*argv[1:])
	print(__doc__)
	return 2


if __name__ == "__main__":
	sys.exit(_main(sys.argv[1:]))
