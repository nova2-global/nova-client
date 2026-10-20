"""Plain paragraphs from the legacy description files (the G15 subset).

The empire and job descriptions (locale/<l>/empiredesc_{a,b,c}.txt and
jobdesc_{warrior,assassin,sura,shaman}.txt) are scripts for the legacy
`event` interpreter: raw line breaks are ignored, [ENTER] breaks a line,
[WAIT] waits for the Next button, [DELAY value;N] sets the typewriter speed,
and the interpreter wraps at 35 characters and shows 5 lines at a time. The
files are wrapped by hand for that box, so most [ENTER]s fall inside a
sentence, and a page often ends mid-sentence.

NovaUI shows them as plain paragraphs in a box that wraps by width and
scrolls (nui_empire, nui_create):
- one [ENTER] is a space (the hand wrap); two or more in a row, with only
  [WAIT], [DELAY ...] and whitespace between them, end a paragraph;
- raw CR and LF are removed first, as the interpreter removes them;
- runs of whitespace become one space, paragraphs are stripped, and empty
  ones are dropped;
- every paragraph goes through nui.plain_text(), so a file can never name a
  locale key through {{ }}.
Dropped: [WAIT] (the pages and the Prev and Next buttons), [DELAY ...] (the
typewriter), the 35-character wrap and the 5-line window, and every other
[NAME args] command, whose name is logged once (dbg.Tracen); the text around
it stays. A "[" without a closing "]" keeps the rest as text, where the
legacy parser refuses the whole file.

Right-to-left locales never reach this module: their phase windows stay
legacy (nui.enabled_for_locale)."""

import dbg
import nui

ENTER = "ENTER"
# Commands that leave no trace and do not end a run of [ENTER]s.
SILENT = ("WAIT", "DELAY")

_logged_commands = set()   # unknown command names already logged
_failed_paths = set()      # paths already reported as unreadable


def _tokens(text):
	"""("text", str) and ("command", name) pieces of `text`, in order. A
	command's name is its first word, as the legacy parser reads it
	(EterLib/parser.cpp): leading and trailing spaces are skipped."""
	position = 0
	length = len(text)
	while position < length:
		start = text.find("[", position)
		if start < 0:
			yield "text", text[position:]
			return
		if start > position:
			yield "text", text[position:start]
		end = text.find("]", start + 1)
		if end < 0:
			yield "text", text[start:]
			return
		inner = text[start + 1:end].strip()
		yield "command", inner.split(" ", 1)[0] if inner else ""
		position = end + 1


def _note_unknown(name):
	if name not in _logged_commands:
		_logged_commands.add(name)
		dbg.Tracen("nui_desc_text: dropped the command [%s]" % name)


def _flush(paragraphs, pieces):
	text = " ".join("".join(pieces).split())
	if text:
		paragraphs.append(nui.plain_text(text))


def parse(source):
	"""Paragraphs (a list of str) from the text of a description file. Bytes
	are decoded as UTF-8, invalid bytes as U+FFFD; a leading BOM is
	dropped."""
	if isinstance(source, bytes):
		source = source.decode("utf-8", "replace")
	if source.startswith("﻿"):
		source = source[1:]
	source = source.replace("\r", "").replace("\n", "")

	paragraphs = []
	pieces = []
	enters = 0
	for kind, value in _tokens(source):
		if kind == "command":
			if value == ENTER:
				enters += 1
			elif value not in SILENT:
				_note_unknown(value)
			continue
		if not value.strip():
			# Whitespace between [ENTER]s does not end their run.
			if not enters:
				pieces.append(value)
			continue
		if enters >= 2:
			_flush(paragraphs, pieces)
			pieces = []
		elif enters == 1:
			pieces.append(" ")
		enters = 0
		pieces.append(value)
	_flush(paragraphs, pieces)
	return paragraphs


def load(path):
	"""parse() of a locale file, read through the client's pack-aware open
	(root/system.py replaces the builtin); [] when it cannot be read, which
	is logged once per path with dbg.TraceError."""
	try:
		file = open(path, "rb")
		try:
			data = file.read()
		finally:
			close = getattr(file, "close", None)  # a packed file has none
			if close is not None:
				close()
	except Exception as error:
		if path not in _failed_paths:
			_failed_paths.add(path)
			dbg.TraceError("nui_desc_text: %s cannot be read (%s)" % (path, type(error).__name__))
		return []
	return parse(data)
