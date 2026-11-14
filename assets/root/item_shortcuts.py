"""Which item shortcuts work right now (NOVA-192, NOVA-193), for the
inventories that run them and the tooltip that names them.

- Ctrl + click searches the shops for the item (NOVA-9): only while the
  server's offline shop is on (GC CONFIG; Interface.OnOfflineShopConfig sets
  it). The search window is the offline shop's.
- Shift + right-click opens the item in the wiki (NOVA-42): only where the
  wiki can open (its NovaUI window; uiWiki.UnavailableWindow stands in
  elsewhere). The Interface sets it when it makes the wiki window.

Both are off until the Interface says otherwise, and off again at its Close."""

_shop_search = False
_wiki = False


def set_shop_search(on):
	global _shop_search
	_shop_search = bool(on)


def shop_search_on():
	return _shop_search


def set_wiki(on):
	global _wiki
	_wiki = bool(on)


def wiki_on():
	return _wiki


def reset():
	set_shop_search(False)
	set_wiki(False)
