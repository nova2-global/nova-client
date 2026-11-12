"""Wave 8's second integration: the wiki's third round (feature/wiki-r3: a
link for every page, the chat's syswiki routing) and the text pages
(feature/wiki-pages, NOVA-139) meet in one window. A chat page link reaches
the real WikiWindow.OpenPage through the Interface's routing, and a text
category's list (the trail's category crumb) links and opens like every
other list."""

import os
import re
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_w4_world as w4  # noqa: E402
import nui_wiki_pages_test as pages_test  # noqa: E402
import nui_wiki_qol_test as qol  # noqa: E402
import nui_wiki_r3_test as r3  # noqa: E402

LEFT, RIGHT = pages_test.LEFT, pages_test.RIGHT
LINK = re.compile(r"\|H([^|]*)\|h")


def interface(wiki):
    """The Interface's real chat link routing (MakeHyperlinkTooltip, its
    syswiki branch, OpenWikiPage, OpenWikiList, OpenWikiLink) over wndWiki."""
    holder = types.SimpleNamespace(wndWiki=wiki, hyperlinkItemTooltip=None)
    for name in ("OpenWikiPage", "OpenWikiList", "OpenWikiLink", "MakeHyperlinkTooltip"):
        method = qol.interface_method(name)
        setattr(holder, name, (lambda m: lambda *a: m(holder, *a))(method))
    opener = qol.interface_method("__OpenWikiLink")
    setattr(holder, "__OpenWikiLink", lambda kind, ident: opener(holder, kind, ident))
    return holder


def click(holder, link):
    """A press on a chat line's link: the |H...|h target goes to MakeHyperlinkTooltip."""
    holder.MakeHyperlinkTooltip(LINK.search(link).group(1))


class ChatPageLinks(pages_test.PagesTest):
    def test_a_chat_page_link_opens_that_page_in_the_wiki(self):
        world, window = self.world()
        holder = interface(window)
        with world.game, w4.quiet():
            click(holder, "|cff00c0fc|Hsyswiki:page:systems/sash|h[Sashes]|h|r")
            window.text_page_open()
        self.assertEqual(self.model(window)["tp_title"], "Sashes")

    def test_a_page_s_own_link_round_trips_through_the_chat(self):
        world, window = self.world()
        pasted = []
        window.SetPasteLinkEvent(pasted.append)
        self.open_page(world, window, "dungeons/demon_tower")
        self.press(world, window, "link_press", LEFT)
        self.open_page(world, window, "systems/sash")
        with world.game, w4.quiet():
            click(interface(window), pasted[0])
            window.text_page_open()
        self.assertEqual(self.model(window)["tp_title"], "Demon Tower")

    def test_an_unknown_page_link_opens_nothing(self):
        world, window = self.world()
        with world.game, w4.quiet():
            click(interface(window), "|Hsyswiki:page:nowhere|h")
        self.assertEqual(self.model(window)["tp_title"], "")


class TextCategoryLists(pages_test.PagesTest):
    def test_every_list_including_the_text_categories_links_and_opens_again(self):
        world, window = self.world()
        module = world.m("nui_wiki")
        keys = [None]
        for i, category in enumerate(module.TREE):
            if any(sub.get("kind") == "page" for sub in category["subs"]):
                keys.append(("pages", i))
            else:
                keys += [("sub", i, j) for j in range(len(category["subs"]))]
        self.assertIn(("pages", self.text_category(world, "systems")), keys)
        paths = set()
        for key in keys:
            path = module.list_path(key)
            with self.subTest(key=key, path=path):
                self.assertTrue(r3.SERVER_LIST_LINK.fullmatch("|Hsyswiki:list:%s|h" % path))
                self.assertNotIn(path, paths)
                self.assertEqual(module.list_of_path(path), key)
            paths.add(path)

    def test_an_unknown_path_opens_nothing_beside_the_text_categories(self):
        world, window = self.world()
        module = world.m("nui_wiki")
        for path in ("nowhere:at_all", "nowhere", "systems:sash", "guides:x"):
            with self.subTest(path=path):
                self.assertIs(module.list_of_path(path), module.NO_LIST)
                with world.game, w4.quiet():
                    self.assertFalse(window.OpenList(path))

    def test_link_on_a_text_page_s_category_crumb_links_that_category(self):
        world, window = self.world()
        self.open_page(world, window, "systems/sash")
        self.press(world, window, "crumb_press", 1, RIGHT)
        pasted = []
        window.SetPasteLinkEvent(pasted.append)
        self.press(world, window, "menu_press", 1, LEFT)
        self.assertEqual(pasted, ["|cff00c0fc|Hsyswiki:list:systems|h[Systems]|h|r"])
        self.assertEqual(self.model(window)["tp_title"], "Sashes", "the page stays")

    def test_the_link_button_on_a_category_s_list_links_it_and_the_link_opens_it(self):
        world, window = self.world()
        self.open_page(world, window, "systems/sash")
        self.press(world, window, "crumb_press", 1, LEFT)
        pasted = []
        window.SetPasteLinkEvent(pasted.append)
        self.press(world, window, "link_press", LEFT)
        self.assertEqual(pasted, ["|cff00c0fc|Hsyswiki:list:systems|h[Systems]|h|r"])
        with world.game, w4.quiet():
            window.OpenList("home")
            click(interface(window), pasted[0])
        self.assertEqual(self.model(window)["list_title"], "Systems")


if __name__ == "__main__":
    unittest.main()
