"""The wiki's text pages in the wiki window (NOVA-139): where the pages are, the
tree's text categories, search over titles and text, and the model a page
shows as. nui_wiki_page_format.py parses a page; nui_wiki.py calls this
module from a few hooks (its TREE, _select, _build_list, _row_model,
_raw_name, wiki_link, the board's tp_link and tp_open), and its window
takes TextPageWindow as a base for the new methods.

Files. A page is one file per language in the client pack,
locale/<lang>/wiki/<path>.txt, beside the locale's other text (OLD kept its
pages in locale/<lang>/wiki/ too). A language without the file shows the
English one, locale/en/wiki/<path>.txt. The extension is .txt because the
client's pack.Get gives Python only .py, .pyc and .txt files
(PythonPackModule.cpp) and raises for any other: r40 shipped .md pages that
no client could read. "index" is not a page: locale/en/wiki/index.txt lists every
page once, one path a line, in the order the tree shows them inside their
category: the pack cannot list a folder, and English is the language every
page exists in.

Every string a page brings reaches the model through nui.plain_text and
{{ }}: a page is never markup. Links are indexes into the window's
_tp_links; a press follows them as the wiki's other links (a middle press, or
Ctrl and a left press, opens a new tab). An embedded item (![[item:N]], r4)
is a link whose run also has the item's icon ("m" "item", "icon"), and the
pointer over it shows the item's tooltip, once per entry (tp_over, tp_out)."""

import nui
import nui_wiki_page_format as fmt

KIND_PAGE = 2
FALLBACK_LOCALE = "locale/en"
INDEX = FALLBACK_LOCALE + "/wiki/index.txt"
SEARCH_MAX = 50
# locale/en/wiki/index.txt is the list, so no page is called "index".
RESERVED = "index"

# The tree's text categories, in order: (front matter category, locale key).
# A page whose category is not here is in no category (links and the search
# still reach it; tools/nui_wiki_pages_tool.py check reports it).
CATEGORIES = (
	("guides", "WIKI_CAT_GUIDES"),
	("dungeons", "WIKI_CAT_DUNGEONS"),
	("systems", "WIKI_CAT_SYSTEMS"),
	("events", "WIKI_CAT_EVENTS"),
)

# The model keys a text page adds to the wiki window's model.
EMPTY_MODEL = {
	"tp_title": "",
	"tp_blocks": [],
	"tp_decor": [],
	# The page's scroll viewport, one entry while a page shows. A new page
	# empties it and refills it on the next frame (tp_open_at, a hidden
	# nui-countdown), so RmlUi makes the viewport again and its scroll starts
	# at the top: NovaUI has no call that scrolls an element.
	"tp_view": [],
	"tp_open_at": 0.0,
}


def initial_model():
	return dict(EMPTY_MODEL)


# --- reading pages --------------------------------------------------------------------

def _read_pack(path):
	"""A pack file's text, or None. A file the pack has but will not give
	(pack.Get refuses an extension other than .py, .pyc and .txt) goes to
	syserr, so a page that cannot be read is never silent."""
	try:
		import pack
	except ImportError:
		return None
	try:
		if not pack.Exist(path):
			return None
	except Exception:
		return None
	try:
		data = pack.Get(path)
	except Exception as error:
		_trace("nui_wiki_pages: pack.Get(%s) failed: %s" % (path, error))
		return None
	return data if isinstance(data, (bytes, str)) else None


def _trace(text):
	try:
		import dbg
		dbg.TraceError(text)
	except Exception:
		pass


def _locale_path():
	try:
		import app
		path = app.GetLocalePath()
	except Exception:
		return FALLBACK_LOCALE
	return path if isinstance(path, str) and path.startswith("locale/") else FALLBACK_LOCALE


# Hooks: tests and tools/nui_wiki_pages_tool.py read files from a folder.
READER = _read_pack
LOCALE = _locale_path

_pages = {}            # (locale, path): parsed page, None when neither file exists
_index = []            # the paths of locale/en/wiki/index.txt
_index_read = [False]


def reset():
	"""Forgets what was read (tests; a new READER)."""
	_pages.clear()
	del _index[:]
	_index_read[0] = False


def page_file(locale, path):
	return "%s/wiki/%s.txt" % (locale, path)


def index():
	"""The page paths, in order; invalid and repeated lines are left out."""
	if not _index_read[0]:
		_index_read[0] = True
		data = READER(INDEX)
		text = data.decode("utf-8", "replace") if isinstance(data, bytes) else (data or "")
		for line in text.splitlines():
			line = line.strip().lstrip("﻿")
			if line and not line.startswith("#") and fmt.valid_page_path(line) and line != RESERVED \
					and line not in _index:
				_index.append(line)
	return list(_index)


def load(path):
	"""The page in the player's language, else in English; None when there
	is no such page. Parsed once per language."""
	if not fmt.valid_page_path(path) or path == RESERVED:
		return None
	locale = LOCALE()
	key = (locale, path)
	if key not in _pages:
		data = READER(page_file(locale, path))
		if data is None and locale != FALLBACK_LOCALE:
			data = READER(page_file(FALLBACK_LOCALE, path))
		_pages[key] = None if data is None else fmt.parse(data)
	return _pages[key]


def exists(path):
	return path in index() and load(path) is not None


def title(path):
	page = load(path)
	return page.meta["title"] if page is not None else path


def label(key):
	"""nui_wiki._locale's hook: a tree row's label ("page", path) is the
	page's title in the player's language."""
	return title(key[1]) if isinstance(key, tuple) and len(key) == 2 and key[0] == "page" else ""


def category_label(category):
	for ident, key in CATEGORIES:
		if ident == category:
			try:
				import localeInfo
				return getattr(localeInfo, key, ident)
			except Exception:  # tools/nui_wiki_pages_tool.py, outside the client
				return ident
	return category


def tree_categories():
	"""nui_wiki.TREE's text categories: one per CATEGORIES entry that has
	pages, each page a "page" row, ordered by the front matter's order, then
	by index.txt."""
	found = {}
	for position, path in enumerate(index()):
		page = load(path)
		if page is None or page.fatal:
			continue
		found.setdefault(page.meta["category"], []).append((page.meta["order"], position, path))
	out = []
	for ident, key in CATEGORIES:
		rows = sorted(found.get(ident, ()))
		if rows:
			out.append({"label": key, "category": ident,
			            "subs": [{"label": ("page", path), "kind": "page", "page": path} for _, _, path in rows]})
	return out


def search(text, limit=SEARCH_MAX):
	"""Page paths whose title, then whose text, has every word of the
	search, in index order."""
	words = [w for w in (text or "").lower().split() if w]
	if not words:
		return []
	titles, bodies = [], []
	for path in index():
		page = load(path)
		if page is None:
			continue
		name = page.meta["title"].lower()
		if all(w in name for w in words):
			titles.append(path)
		elif all(w in page.search_text for w in words):
			bodies.append(path)
	return (titles + bodies)[:limit]


def row_model(index_in_list, path):
	"""A list row of a page (the window's _row_model): its title and its
	category, no icon."""
	page = load(path)
	category = page.meta["category"] if page is not None else ""
	return {"i": index_in_list, "vnum": 0, "mob": False, "icon": "",
	        "name": nui.plain_text(title(path)), "note": nui.plain_text(category_label(category))}


def chat_link(path, name, color):
	"""|c<color>|Hsyswiki:page:<path>|h[<name>]|h|r; "" for a bad path."""
	if not fmt.valid_page_path(path):
		return ""
	return "|c%s|Hsyswiki:page:%s|h[%s]|h|r" % (color, path, (name or "").replace("|", ""))


# --- the model ------------------------------------------------------------------------

def _missing(path):
	page = fmt.Page()
	page.meta["title"] = path
	block = fmt.empty_block("error")
	block["text"] = "there is no page '%s'" % path
	page.blocks = [block]
	page.fatal = True
	return page


def render(path, name_of, icon_of=None):
	"""(model values, links) of the page at path. name_of(kind, vnum) is an
	item's or a mob's name, icon_of(vnum) an item's icon source; links are
	(kind, ident, embed), a run's "l" its index (-1 for text), its "m" "item"
	for an embed (with the item's "icon") and "" otherwise. A link to a page
	that does not exist is an error run."""
	page = load(path)
	if page is None:
		page = _missing(path)
	links = []

	def runs(source):
		out = []
		for run in source:
			link = run["link"]
			model = {"t": nui.plain_text(run["t"]), "b": run["b"], "i": run["i"], "l": -1, "e": run["e"],
			         "m": "", "icon": ""}
			if link:
				kind, ident, text = link
				if kind == "page" and not exists(ident):
					model.update(t=nui.plain_text("[[page:%s]]" % ident), e=True)
				else:
					if not text:
						if kind == "page":
							text = title(ident)
						else:
							text = name_of(kind, int(ident)) or "#%s" % ident
					model.update(t=nui.plain_text(text), l=len(links))
					embed = bool(run.get("embed")) and kind == "item"
					if embed:
						model.update(m="item", icon=(icon_of(int(ident)) if icon_of else "") or "")
					links.append((kind, ident, embed))
			out.append(model)
		return out

	def blocks(source):
		out = []
		for block in source:
			model = dict(block)
			model["runs"] = runs(block["runs"])
			model["items"] = [{"n": e["n"], "d": e["d"], "runs": runs(e["runs"])} for e in block["items"]]
			model["rows"] = [{"head": r["head"], "cells": [{"runs": runs(c["runs"])} for c in r["cells"]]}
			                 for r in block["rows"]]
			model["cols"] = [{"blocks": blocks(c["blocks"])} for c in block["cols"]]
			model["alt"] = nui.plain_text(block["alt"])
			model["text"] = nui.plain_text(block["text"])
			out.append(model)
		return out

	values = {
		"tp_title": nui.plain_text(page.meta["title"]),
		"tp_blocks": blocks(page.blocks),
		"tp_decor": [{"src": fmt.image_source(p), "corner": corner} for corner, p in page.meta["decor"]],
	}
	return values, links


class TextPageWindow(object):
	"""The wiki window's text page methods (a base of nui_wiki.WikiWindow;
	it names nothing the window has)."""

	_tp_links = ()
	_tp_serial = 0
	_tip_link = None  # the embed whose tooltip shows

	def _select_text_page(self, path):
		self._current = (KIND_PAGE, path)
		self._origins = []
		self.out_text_link()
		values, self._tp_links = render(path, self._tp_name, self._tp_icon)
		self._tp_serial += 1
		self.nui_set(page_state="text", page_kind="text", page_vnum=0, page_name=values["tp_title"], page_sub="",
		             page_icon="", page_common=False, model_view=False, origins=[], chest=[], refine=[], drops=[],
		             retry_at=0.0, timeout_at=0.0, tp_view=[], tp_open_at=nui.now() + 0.01, **values)

	def _tp_name(self, kind, vnum):
		return self._raw_name(0 if kind == "item" else 1, vnum)

	def _tp_icon(self, vnum):
		return self._item_icon_of(vnum)

	def over_text_link(self, index):
		"""The pointer on an embedded item: its tooltip. RmlUi sends the
		mouseover again for the embed's own children, so the link already
		shown shows nothing again; text and plain links show none."""
		if not (0 <= index < len(self._tp_links)) or index == self._tip_link:
			return
		kind, ident, embed = self._tp_links[index]
		if not embed:
			return
		self._tip_link = index
		self._show_tooltip(0, int(ident))

	def out_text_link(self):
		if self._tip_link is not None:
			self._tip_link = None
			self._hide_tip()

	def text_page_open(self):
		"""The hidden clock's end: the page's viewport again (see tp_view)."""
		if self._current is not None and self._current[0] == KIND_PAGE:
			self.nui_set(tp_view=[{"n": self._tp_serial}], tp_open_at=0.0)

	def follow_text_link(self, index, button=0):
		if not (0 <= index < len(self._tp_links)):
			return
		kind, ident = self._tp_links[index][:2]
		if kind == "page":
			location = self._page_location(ident)
		else:
			location = self._at_page(0 if kind == "item" else 1, int(ident))
		self._follow(location, button)
