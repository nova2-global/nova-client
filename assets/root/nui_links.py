"""The web addresses the NovaUI login screen links to (nui_login.py).

Each is an https address, or "" while there is none: the screen draws no
link without an address. FORGOT_PASSWORD falls back to WEBSITE when it is
"" (an account's password is reset on the website). Fill them in here; the
login screen reads them when it opens."""

import os

DISCORD = ""
WEBSITE = ""
# The rules a new account accepts on the Create account tab.
SERVER_RULES = ""
FORGOT_PASSWORD = ""


def address(name):
	"""The address of a link ("discord", "website", "rules", "forgot"), or
	""."""
	if name == "discord":
		return DISCORD
	if name == "website":
		return WEBSITE
	if name == "rules":
		return SERVER_RULES
	if name == "forgot":
		return FORGOT_PASSWORD or WEBSITE
	return ""


def open_link(name):
	"""Opens the link's address in the player's browser. Only https addresses
	from this file are opened, never text from elsewhere. True when it was
	handed to the browser."""
	url = address(name)
	if not url.startswith("https://") or any(c in url for c in " \t\r\n\"'<>"):
		return False
	start = getattr(os, "startfile", None)
	if start is None:
		return False
	try:
		start(url)
		return True
	except Exception:
		return False
