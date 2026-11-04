"""The prices the player last asked for each item, remembered between sessions
(OLD itemPrices.py, NOVA-9): the offline shop's price dialogs start from them.

The game window reads the list when it opens and writes it when it closes
(OLD game.py:330, 458). The file is OLD's, shop/price_list.txt next to the
client, one "vnum<TAB>price" per line, in UTF-8. Neither a missing folder nor
a broken or unwritable file may stop the game: every error is swallowed and
the dict keeps what it holds.

The file goes through io.open: the client's builtins.open is system.py's
open(filename, mode), which takes no encoding and would raise TypeError."""

import io
import os

FILE_NAME = "shop/price_list.txt"
PRICE_DICT = {}


def read_prices(file_name=None):
	"""Fills PRICE_DICT from the file; True when it was read."""
	file_name = file_name or FILE_NAME
	try:
		with io.open(file_name, "r", encoding="utf-8", errors="replace") as handle:
			lines = handle.readlines()
	except Exception:
		return False
	for line in lines:
		tokens = line.rstrip("\r\n").split("\t")
		if len(tokens) < 2:
			continue
		try:
			vnum, price = int(tokens[0]), int(tokens[1])
		except ValueError:
			continue
		if vnum > 0 and price > 0:
			PRICE_DICT[vnum] = price
	return True


def write_price_list(file_name=None):
	"""Writes PRICE_DICT, the folder made when missing; True when it was written."""
	file_name = file_name or FILE_NAME
	try:
		folder = os.path.dirname(file_name)
		if folder and not os.path.isdir(folder):
			os.makedirs(folder)
		with io.open(file_name, "w", encoding="utf-8", newline="\n") as handle:
			for vnum, price in sorted(PRICE_DICT.items()):
				handle.write("%d\t%d\n" % (vnum, price))
	except Exception:
		return False
	return True


def get_price(vnum):
	"""The remembered price of an item, 0 when none."""
	return PRICE_DICT.get(vnum, 0)


def set_price(vnum, price):
	try:
		vnum, price = int(vnum), int(price)
	except (TypeError, ValueError):
		return
	if vnum > 0 and price > 0:
		PRICE_DICT[vnum] = price
