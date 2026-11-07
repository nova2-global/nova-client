"""OLD's art for the items of wave 6 (NOVA-19 to 23): the files OLD's
item_list lines name for the quivers, sashes, weapon costumes and auras of
the cut's item_proto that NEW's list lacks, the sash effects and the quiver's
bow attack (EXTRA), and every texture, effect, mesh and motion those name in
turn, taken from OLD's client source into the asset groups.

	python3 tools/old_art.py import PACKER OLD_ITEM_LIST CUT_ITEM_PROTO GRLIST

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
assets/, OLD's source and how it was taken. Run old_content.py item_list afterwards so the
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
SUB_TYPES = ("COSTUME_WEAPON", "COSTUME_SASH", "COSTUME_AURA", "WEAPON_UNLIMITED_ARROW")
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


def import_art(packer, old_item_list, cut_proto, grlist):
	assets = old_content.ASSETS
	with open(os.path.join(assets, "groups.txt"), encoding="utf-8") as handle:
		groups = [line for line in (raw.split("#")[0].strip() for raw in handle) if line]
	files = old_content.published_files()
	with open(old_item_list, "rb") as handle:
		old_data = handle.read()
	with open(cut_proto, encoding="utf-8", errors="replace") as handle:
		proto_text = handle.read()
	with open(old_content.ITEM_LIST, "rb") as handle:
		new_data = old_content.news_part(handle.read(), "item_list")
	index = packer_index(packer)
	scratch = os.path.join(old_content.REPO, "tools")
	take, missing = closure(seeds(old_data, proto_text, new_data, files), index, files, packer, grlist, scratch)
	folders = group_folders(assets, groups)
	rows, converts = [], []
	for path in sorted(take):
		group = choose_group(path, folders)
		source = os.path.join(packer, take[path])
		target = destination(assets, group, index[path][0])
		os.makedirs(os.path.dirname(target), exist_ok=True)
		if path.endswith(".gr2") and granny_tag(source) == CUSTOM_TAG:
			converts.append((source, target))
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
	with open(MANIFEST, "w", encoding="utf-8", newline="\n") as handle:
		handle.write("# store path\tfile under assets/\tOLD source (under the packer folder)\thow\n")
		for row in rows:
			handle.write("\t".join(row) + "\n")
	print("took %d files (%d converted), %d named but missing in OLD too:" % (
		len(rows), len(converts), len(missing)))
	for path in sorted(missing):
		print("  %s <- %s" % (path, missing[path] or "item_list"))
	for row in failed:
		print("FAILED: %s" % "\t".join(row))
	return 1 if failed else 0


def _main(argv):
	if len(argv) == 5 and argv[0] == "import":
		return import_art(*argv[1:])
	print(__doc__)
	return 2


if __name__ == "__main__":
	sys.exit(_main(sys.argv[1:]))
