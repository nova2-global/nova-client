"""The wiki's text page format (NOVA-139, assets/root/nui_wiki_page_format.py):
front matter, the Markdown subset, links, and the safety rules. The parser is
pure Python with no client module, so these tests import it directly."""

import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(os.path.dirname(HERE), "assets", "root")
sys.path.insert(0, ROOT)

import nui_wiki_page_format as fmt  # noqa: E402

HEAD = "---\ntitle: Demon Tower\ncategory: dungeons\n---\n"


def page(body, head=HEAD):
    return fmt.parse(head + body)


def kinds(result):
    return [b["k"] for b in result.blocks]


def text(runs):
    return "".join(r["t"] for r in runs)


class FrontMatter(unittest.TestCase):
    def test_title_category_order_and_decor(self):
        result = fmt.parse("---\ntitle: Demon Tower\ncategory: dungeons\norder: 3\n"
                           "decor: top-right = icon/item/30304.tga\ndecor: bottom-left = d:/ymir work/ui/a.tga\n---\nHi\n")
        self.assertEqual(result.problems, [])
        self.assertEqual(result.meta["title"], "Demon Tower")
        self.assertEqual(result.meta["category"], "dungeons")
        self.assertEqual(result.meta["order"], 3)
        self.assertEqual(result.meta["decor"], [("top-right", "icon/item/30304.tga"),
                                                ("bottom-left", "d:/ymir work/ui/a.tga")])

    def test_a_page_without_front_matter_is_one_error_block(self):
        result = fmt.parse("# Hello\n")
        self.assertTrue(result.fatal)
        self.assertEqual(kinds(result), ["error"])
        self.assertTrue(result.problems)

    def test_title_and_category_are_required(self):
        for head in ("---\ncategory: dungeons\n---\n", "---\ntitle: X\n---\n", "---\ntitle: X\ncategory: Bad Cat\n---\n"):
            with self.subTest(head=head):
                result = fmt.parse(head + "Hi\n")
                self.assertTrue(result.fatal)
                self.assertEqual(kinds(result), ["error"])

    def test_an_unclosed_front_matter_is_fatal(self):
        result = fmt.parse("---\ntitle: X\ncategory: guides\nHi\n")
        self.assertTrue(result.fatal)

    def test_an_unknown_key_and_a_bad_decor_are_problems_but_the_page_shows(self):
        result = fmt.parse("---\ntitle: X\ncategory: guides\ncolour: red\ndecor: middle = a.png\n"
                           "decor: top-left = ../secret.png\n---\nHi\n")
        self.assertFalse(result.fatal)
        self.assertEqual(len(result.problems), 3)
        self.assertEqual(result.meta["decor"], [])
        self.assertIn("p", kinds(result))

    def test_a_byte_order_mark_and_crlf_are_accepted(self):
        result = fmt.parse("\ufeff---\r\ntitle: X\r\ncategory: guides\r\n---\r\nHi\r\n")
        self.assertEqual(result.problems, [])
        self.assertEqual(text(result.blocks[0]["runs"]), "Hi")


class Blocks(unittest.TestCase):
    def test_headings_three_levels(self):
        result = page("# One\n## Two\n### Three\n#### Four\n")
        self.assertEqual(kinds(result), ["h1", "h2", "h3", "h3", "error"])
        self.assertEqual(text(result.blocks[1]["runs"]), "Two")
        self.assertEqual(len(result.problems), 1)

    def test_a_paragraph_joins_its_lines_and_a_blank_line_ends_it(self):
        result = page("first line\nsecond line\n\nnext\n")
        self.assertEqual(kinds(result), ["p", "p"])
        self.assertEqual(text(result.blocks[0]["runs"]), "first line second line")

    def test_bullet_lists_with_both_markers_continuation_and_depth(self):
        result = page("- one\n* two\n  more of two\n  - nested\n")
        self.assertEqual(kinds(result), ["ul"])
        items = result.blocks[0]["items"]
        self.assertEqual([text(i["runs"]) for i in items], ["one", "two more of two", "nested"])
        self.assertEqual([i["d"] for i in items], [0, 0, 1])
        self.assertEqual(items[0]["n"], "")

    def test_numbered_lists_count_from_their_first_number(self):
        result = page("3. three\n4. four\n9. five\n")
        self.assertEqual(kinds(result), ["ol"])
        self.assertEqual([i["n"] for i in result.blocks[0]["items"]], ["3.", "4.", "5."])

    def test_a_list_kind_change_starts_a_new_list(self):
        self.assertEqual(kinds(page("- a\n1. b\n")), ["ul", "ol"])

    def test_tables_with_a_header_row(self):
        result = page("| Boss | Level |\n|---|:---:|\n| Blue Death | 75 |\n| Reaper |\n")
        self.assertEqual(kinds(result), ["table"])
        rows = result.blocks[0]["rows"]
        self.assertEqual([r["head"] for r in rows], [True, False, False])
        self.assertEqual([[text(c["runs"]) for c in r["cells"]] for r in rows],
                         [["Boss", "Level"], ["Blue Death", "75"], ["Reaper", ""]])
        self.assertEqual(result.problems, [])

    def test_a_table_without_a_header_and_with_extra_cells(self):
        result = page("| a | b |\n| c | d | e |\n")
        rows = result.blocks[0]["rows"]
        self.assertFalse(rows[0]["head"])
        self.assertEqual(len(rows[1]["cells"]), 2)
        self.assertEqual(len(result.problems), 1)

    def test_a_pipe_inside_a_link_does_not_split_a_cell(self):
        result = page("| [[item:19|Moon Blade]] | x |\n")
        cells = result.blocks[0]["rows"][0]["cells"]
        self.assertEqual(len(cells), 2)
        self.assertEqual(cells[0]["runs"][0]["link"], ("item", "19", "Moon Blade"))

    def test_images_float_align_and_width(self):
        result = page("![Key](icon/item/30304.tga){float=right width=180}\n"
                      "![Map](d:/ymir work/ui/map.tga){align=center width=100%}\n"
                      "![Plain](icon/item/1.tga)\n")
        self.assertEqual(result.problems, [])
        a, b, c = result.blocks
        self.assertEqual((a["k"], a["src"], a["fl"], a["al"], a["w"], a["alt"]),
                         ("img", "/icon/item/30304.tga", "right", "", "180dp", "Key"))
        self.assertEqual((b["src"], b["fl"], b["al"], b["w"]), ("d:/ymir work/ui/map.tga", "", "center", "100%"))
        self.assertEqual((c["fl"], c["al"], c["w"]), ("", "", "auto"))

    def test_an_image_after_text_keeps_its_place(self):
        result = page("text before\n![a](icon/item/1.tga)\ntext after\n")
        self.assertEqual(kinds(result), ["p", "img", "p"])
        self.assertEqual(text(result.blocks[0]["runs"]), "text before")

    def test_a_line_that_only_looks_like_an_image_is_text(self):
        self.assertEqual(kinds(page("![not an image\n")), ["p"])

    def test_bad_image_attributes_are_problems(self):
        for attrs in ("{float=up}", "{width=0}", "{width=5000}", "{width=150%}", "{float=left align=center}",
                      "{height=20}", "{width=12px}"):
            with self.subTest(attrs=attrs):
                result = page("![a](icon/item/1.tga)%s\n" % attrs)
                self.assertTrue(result.problems)
                self.assertIn("error", kinds(result))

    def test_separators_default_and_named(self):
        result = page("a\n\n---\n\n--- {style=ornate}\n")
        self.assertEqual(kinds(result), ["p", "hr", "hr"])
        self.assertEqual([b["style"] for b in result.blocks[1:]], ["", "ornate"])

    def test_an_unknown_separator_style_falls_back_with_a_problem(self):
        result = page("--- {style=sparkles}\n")
        self.assertEqual(kinds(result), ["hr", "error"])
        self.assertEqual(result.blocks[0]["style"], "")

    def test_note_and_warning_blocks(self):
        result = page(":::note\nRead **this**.\n:::\n:::warning\n- careful\n:::\n")
        self.assertEqual(kinds(result), ["note", "warn"])
        inner = result.blocks[0]["cols"][0]["blocks"]
        self.assertEqual([b["k"] for b in inner], ["p"])
        self.assertEqual(result.blocks[1]["cols"][0]["blocks"][0]["k"], "ul")

    def test_columns_with_breaks(self):
        result = page(":::columns\n- a\n+++\n![x](icon/item/1.tga)\n+++\nthird\n:::\nafter\n")
        self.assertEqual(kinds(result), ["cols", "p"])
        cols = result.blocks[0]["cols"]
        self.assertEqual([[b["k"] for b in c["blocks"]] for c in cols], [["ul"], ["img"], ["p"]])

    def test_too_many_columns_and_a_break_outside_columns(self):
        result = page(":::columns\na\n+++\nb\n+++\nc\n+++\nd\n:::\n+++\n")
        self.assertEqual(len(result.blocks[0]["cols"]), 3)
        self.assertEqual(len(result.problems), 2)

    def test_broken_block_markup(self):
        cases = {
            ":::note\nopen\n": 1,                   # never closed
            ":::\n": 1,                             # a close with nothing open
            ":::note\n:::columns\nx\n:::\n:::\n": 2,  # nested, then a stray close
            ":::spoiler\nx\n:::\n": 2,              # unknown kind, then a stray close
        }
        for body, count in cases.items():
            with self.subTest(body=body):
                result = page(body)
                self.assertEqual(len(result.problems), count, result.problems)
                self.assertIn("error", [b["k"] for b in fmt.walk(result.blocks)])

    def test_every_block_has_the_same_keys_at_every_level(self):
        result = page("# h\np\n- l\n| t |\n![i](icon/item/1.tga)\n---\n:::columns\n# h\n+++\n| t |\n:::\n"
                      ":::note\nn\n:::\n[[item:x]]\n")
        keys = set(fmt.empty_block("p"))
        for block in fmt.walk(result.blocks):
            self.assertEqual(set(block), keys, block["k"])


class Inline(unittest.TestCase):
    def runs(self, line):
        return page(line + "\n").blocks[0]["runs"]

    def flags(self, line):
        return [(r["t"], r["b"], r["i"]) for r in self.runs(line)]

    def test_bold_italic_and_both(self):
        self.assertEqual(self.flags("a **b** *c* ***d*** e"),
                         [("a ", False, False), ("b", True, False), (" ", False, False), ("c", False, True),
                          (" ", False, False), ("d", True, True), (" e", False, False)])

    def test_an_unclosed_marker_is_text(self):
        self.assertEqual(self.flags("2 * 3 = 6 and **open"), [("2 * 3 = 6 and **open", False, False)])

    def test_backslash_escapes(self):
        self.assertEqual(self.flags(r"\*not\* \[[item:1]] a\\b"), [(r"*not* [[item:1]] a\b", False, False)])

    def test_links_of_each_kind_with_and_without_text(self):
        runs = self.runs("[[item:19]] [[mob:101|Wild Dog]] [[page:dungeons/demon_tower|the tower]]")
        links = [r["link"] for r in runs if r["link"]]
        self.assertEqual(links, [("item", "19", None), ("mob", "101", "Wild Dog"),
                                 ("page", "dungeons/demon_tower", "the tower")])

    def test_a_link_inside_bold_keeps_the_bold(self):
        runs = self.runs("**see [[mob:101]]**")
        self.assertEqual([(r["b"], bool(r["link"])) for r in runs], [(True, False), (True, True)])

    def test_any_punctuation_can_be_escaped_at_a_line_start(self):
        result = page("1\\. not a list\n\\- not a bullet\n\\# not a heading\n")
        self.assertEqual(kinds(result), ["p"])
        self.assertEqual(text(result.blocks[0]["runs"]), "1. not a list - not a bullet # not a heading")

    def test_bad_links_are_error_runs_and_problems(self):
        for link in ("[[item:abc]]", "[[item:0]]", "[[item:99999999999]]", "[[mob:-3]]", "[[page:../etc]]",
                     "[[page:/abs]]", "[[page:Dungeons]]", "[[npc:1]]", "[[item:1|]]", "[[page:%s]]" % ("a" * 65)):
            with self.subTest(link=link):
                result = page("x %s y\n" % link)
                bad = [r for r in result.blocks[0]["runs"] if r["e"]]
                self.assertEqual([r["t"] for r in bad], [link])
                self.assertEqual(len(result.problems), 1)
                self.assertEqual(kinds(result), ["p", "error"])

    def test_an_unclosed_link_is_text(self):
        self.assertEqual(self.flags("see [[item:19"), [("see [[item:19", False, False)])


class Safety(unittest.TestCase):
    def test_markup_in_text_stays_text(self):
        body = "<div onclick='x'>hi</div> {{ secret }} <img src=x>\n"
        runs = page(body).blocks[0]["runs"]
        self.assertEqual(text(runs), body.strip())
        self.assertEqual(page(body).problems, [])

    def test_control_characters_are_dropped(self):
        runs = page("a\x00b\x07c\x1bd\n").blocks[0]["runs"]
        self.assertEqual(text(runs), "abcd")

    def test_image_paths_stay_in_the_pack(self):
        good = ("icon/item/30304.tga", "d:/ymir work/ui/wiki/a.png", "locale/common/wiki/x-1_2.dds", "a.jpg", "b.sub")
        bad = ("../root/x.png", "icon/../../x.png", "/etc/passwd.png", "c:/windows/x.png", "http://x.org/a.png",
               "icon/item/A.tga", "icon/item/x.exe", "icon/item/x", "icon//x.png", "icon/it em/x.png",
               "d:/ymir work/../x.png", "icon\\item\\x.tga", "", "x" * 125 + ".png", "icon/item/x.png?y")
        for path in good:
            self.assertTrue(fmt.valid_image_path(path), path)
        for path in bad:
            with self.subTest(path=path):
                self.assertFalse(fmt.valid_image_path(path))
                result = page("![a](%s)\n" % path)
                self.assertEqual(kinds(result), ["error"])

    def test_page_paths(self):
        for path in ("landing", "dungeons/demon_tower", "a-b/c_d/e1", "a" * 64):
            self.assertTrue(fmt.valid_page_path(path), path)
        for path in ("", "/x", "x/", "a//b", "../x", "a/../b", "A", "a.b", "a b", "a" * 65, "a\\b", None, 5):
            self.assertFalse(fmt.valid_page_path(path), path)

    def test_a_huge_page_is_refused(self):
        result = fmt.parse(HEAD + "x" * (fmt.SIZE_MAX + 1))
        self.assertTrue(result.fatal)

    def test_too_many_blocks_are_cut_with_a_problem(self):
        result = page("p\n\n" * (fmt.BLOCKS_MAX + 20))
        self.assertLessEqual(len(result.blocks), fmt.BLOCKS_MAX + 1)
        self.assertEqual(kinds(result)[-1], "error")

    def test_no_input_breaks_the_parser(self):
        rng = random.Random(139)
        alphabet = "ab *_[]|:!(){}=#-+\\\n\t<>@/.0123456789"
        for _ in range(400):
            body = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 300)))
            result = page(body)
            for block in fmt.walk(result.blocks):
                self.assertIn(block["k"], fmt.BLOCK_KINDS)
        self.assertTrue(fmt.parse(b"\xff\xfe\x00garbage").fatal)
        self.assertTrue(fmt.parse(None).fatal)

    def test_the_search_text_has_the_title_and_the_words(self):
        result = page("Defeat the **Blue Death**.\n\n| Key | Zin-Bong-In |\n")
        self.assertIn("demon tower", result.search_text)
        self.assertIn("blue death", result.search_text)
        self.assertIn("zin-bong-in", result.search_text)


if __name__ == "__main__":
    unittest.main()
