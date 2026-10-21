"""Tests for the NovaUI guild window and its grade name dialog
(assets/root/nui_guild.py, nui_guild_grade_name.py, P16 spec 5.9):
python3 -B -m unittest nui_guild_test (from tools/).

The legacy uiGuild.GuildWindow (its six pages made by legacy's own builders
over nui_game_support's stand-ins, the uiscripts read as the client reads
them) and the NovaUI one, each in a world of its own with the same guild
(nui_w4_fixtures.guild_state), driven as the Interface and the C++
callbacks drive them (spec 5.9.4): Open and every page's refresh, the tabs,
the offer, the mark and symbol uploads, the war declaration, comments
(post, F5, delete, refresh), member grades and general flags, the member
scroll, the skills (pick, use, "+", the cooldown, the hover), the dragon
power heal, grade names and authorities, the war start and end, Escape and
the close. The board shows what legacy's widgets show, page by page, and
both windows make the same calls in the same order (the popups compared by
their text: legacy shows its own popup window, NovaUI the dialog kit's)."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_w4_fixtures as fixtures  # noqa: E402
import nui_w4_world as w4  # noqa: E402

DOCUMENT = "nui/windows/guild/guild.rml"
GRADE_DOCUMENT = "nui/windows/guild-grade-name/guild-grade-name.rml"
EFFECTS = support.W4_COMPARED + ("snd", "uiPickMoney", "uiCommon.QuestionDialog")
PAGES = ("GUILD_INFO", "BOARD", "MEMBER", "BASE_INFO", "SKILL", "GRADE")
P = support.module_constants()["player"]


def guild(game, **changes):
    fixtures.guild_state(game, "Dragon Order", fixtures.GUILD_ENEMIES, 30)
    game.w4["guild"].update(changes)
    game.modules["skill"].CanUseSkill = lambda index: True


class GuildTest(unittest.TestCase):
    def world(self, nui_on, setup=guild, **kwargs):
        world = w4.World(nui_on, setup=setup, social=True, **kwargs)
        window = world.make("guild", "uiGuild", "GuildWindow", "nui_guild.GuildWindow")
        world.tooltip_skill = support.ToolTip("skill")
        with world.game, w4.quiet():
            window.SetSkillToolTip(world.tooltip_skill)
        return world, window

    def open(self, world, window):
        """Interface.ToggleGuildWindow (interfacemodule.py:1089-1091)."""
        with world.game, w4.quiet():
            if window.CanOpen():
                window.Open()

    def tab(self, world, window, key):
        """A press on a page's tab: the board's tab, or legacy's radio button."""
        with world.game, w4.quiet():
            if world.nui_on:
                w4.press(window, "tab_press", PAGES.index(key), 0)
            elif key != "BASE_INFO":
                # Legacy's base tab is zero wide and disabled: no press reaches it.
                window.SetTop()
                window.tabButtonDict[key].click()

    def run_both(self, flow, setup=guild, page=None):
        results = []
        for nui_on in (False, True):
            world, window = self.world(nui_on, setup)
            self.open(world, window)
            if page:
                self.tab(world, window, page)
            mark = world.mark()
            with world.game, w4.quiet():
                flow(world, window)
            results.append((world.effects_since(mark, EFFECTS), world, window))
        return results

    def popups(self, world, mark=0):
        """The popup messages shown since `mark`: legacy's popup window's text
        at each Show, or the dialog kit's popup."""
        found = []
        for name, args in world.game.log[mark:]:
            if name == "uiCommon.PopupDialog.Open":
                found.append(args[0])
        return found


def legacy_popup_text(window):
    return window.popupMessage.GetText() if window.popupDialog.IsShow() else None


class Pages(GuildTest):
    """The board shows what legacy's widgets show, page by page."""

    def pair(self, setup=guild):
        (a_world, a), (b_world, b) = [self.world(nui_on, setup) for nui_on in (False, True)]
        for world, window in ((a_world, a), (b_world, b)):
            self.open(world, window)
        return a, b

    def test_the_info_page(self):
        a, b = self.pair()
        model = w4.board(b).model
        page = a.pageWindow["GUILD_INFO"]
        self.assertEqual(model["info"], {"name": page.nameSlot.GetText(), "master": page.masterNameSlot.GetText(),
                                         "level": page.guildLevelSlot.GetText(), "cur_exp": page.curExpSlot.GetText(),
                                         "last_exp": page.lastExpSlot.GetText(),
                                         "members": page.memberCountSlot.GetText(),
                                         "avg_level": page.levelAverageSlot.GetText()})
        self.assertEqual(model["info"]["cur_exp"], "1234500", "legacy's experience times 100")
        self.assertEqual(model["enemies"], [line.GetText() for line in a.enemyGuildNameList])
        self.assertEqual(model["enemies"][0], "Black Wolves")
        self.assertEqual((model["upload_mark_shown"], model["upload_symbol_shown"], model["declare_shown"]),
                         (page.uploadMarkButton.shown, page.uploadSymbolButton.shown, page.declareWarButton.shown))
        self.assertEqual((model["upload_mark_shown"], model["declare_shown"]), (True, True), "the tester is the master")
        self.assertEqual(a.largeMarkBox.index, 7)
        self.assertEqual((model["mark_src"], model["mark_rect"]), ("/" + fixtures.GUILD_MARK_ATLAS, "0 0 16 12"))
        self.assertEqual(model["page_info"], [1])
        self.assertEqual(model["page_board"] + model["page_member"] + model["page_skill"] + model["page_grade"], [],
                         "D9: only the shown page is built")

    def test_a_member_s_buttons_hide(self):
        def setup(game):
            guild(game, master="Boss")
        a, b = self.pair(setup)
        model = w4.board(b).model
        self.assertEqual((model["upload_mark_shown"], model["upload_symbol_shown"], model["declare_shown"]),
                         (False, False, False))

    def test_the_board_page(self):
        (a_world, a), (b_world, b) = [self.world(nui_on) for nui_on in (False, True)]
        for world, window in ((a_world, a), (b_world, b)):
            self.open(world, window)
            self.tab(world, window, "BOARD")
        model = w4.board(b).model
        board = a.pageWindow["BOARD"]
        expected = []
        for line in range(12):
            notice, name, comment = board.boardDict[line]
            expected.append({"notice": bool(notice.shown), "name": name.GetText(),
                             "short": comment.slotSimpleText.GetText(), "full": comment.slotFullText.GetText(),
                             "long": comment.len > comment.TEXT_LIMIT})
        self.assertEqual(model["comments"], expected)
        self.assertEqual([c["notice"] for c in model["comments"][:4]], [True, False, False, True])
        self.assertTrue(model["comments"][2]["long"])
        self.assertTrue(model["comments"][2]["short"].endswith("..."))
        self.assertEqual(model["comments"][0]["short"], "Comment number 1", "the notice's '!' is not shown")

    def test_the_member_page(self):
        (a_world, a), (b_world, b) = [self.world(nui_on) for nui_on in (False, True)]
        for world, window in ((a_world, a), (b_world, b)):
            self.open(world, window)
            self.tab(world, window, "MEMBER")
        model = w4.board(b).model
        members = a.pageWindow["MEMBER"].memberDict
        expected = []
        for line in range(13):
            name, combo, job, level, offer, general = members[line]
            expected.append({"name": name.GetText(), "grade": combo.text, "job": job.GetText(),
                             "level": level.GetText(), "offer": offer.GetText(), "general": bool(general.image.shown),
                             "combo_enabled": bool(combo.enable)})
        self.assertEqual(model["members"], expected)
        self.assertEqual(model["members"][0]["name"], "Tester", "line 0 is the top line")
        self.assertFalse(model["members"][0]["combo_enabled"], "grade 1's combo box is disabled")
        self.assertEqual(model["member_scroll_shown"], True, "30 members, 13 lines")

    def test_the_skill_page(self):
        (a_world, a), (b_world, b) = [self.world(nui_on) for nui_on in (False, True)]
        for world, window in ((a_world, a), (b_world, b)):
            self.open(world, window)
            self.tab(world, window, "SKILL")
        model = w4.board(b).model
        active = a.pageWindow["SKILL"].activeSlot
        counts = [str(active.slots[s]["count"]) if active.slots[s]["count"] > 0 else "" for s in range(210, 219)]
        self.assertEqual([cell["count"] for cell in model["active_cells"]], counts)
        self.assertEqual(model["active_plus"], [s in getattr(active, "buttons", set()) for s in range(210, 219)])
        self.assertEqual(model["active_plus"][:6], [True] * 6, "points remain and every level is below 20")
        self.assertEqual([cell["unavailable"] for cell in model["active_cells"][:6]],
                         [active.slots[s]["unavailable"] for s in range(210, 216)])
        self.assertEqual(model["skill_point"], a.pageWindow["SKILL"].skillPoint.GetText())
        self.assertEqual(model["gp_text"], "40 / 100")
        self.assertAlmostEqual(model["gp_ratio"], 0.4)
        self.assertAlmostEqual(model["gp_legacy"], int(40.0 * 173.0 / 95.0) * 95.0 / (100 * 173.0))
        self.assertEqual([cell["kind"] for cell in model["passive_cells"]], [""] * 9, "the passive row stays empty")

    def test_the_grade_page(self):
        (a_world, a), (b_world, b) = [self.world(nui_on) for nui_on in (False, True)]
        for world, window in ((a_world, a), (b_world, b)):
            self.open(world, window)
            self.tab(world, window, "GRADE")
        model = w4.board(b).model
        grades = a.pageWindow["GRADE"].gradeDict
        expected = []
        for number in range(1, 16):
            name, add, remove, notice, skill = grades[number]
            expected.append({"number": number, "name": name.textLine.GetText(), "add": bool(add.image.shown),
                             "remove": bool(remove.image.shown), "notice": bool(notice.image.shown),
                             "skill": bool(skill.image.shown), "enabled": bool(name.Enable)})
        self.assertEqual(model["grades"], expected)
        self.assertFalse(model["grades"][0]["enabled"])

    def test_the_tabs_and_the_titles(self):
        (a_world, a), (b_world, b) = [self.world(nui_on) for nui_on in (False, True)]
        for world, window in ((a_world, a), (b_world, b)):
            self.open(world, window)
        for key in PAGES:
            for world, window in ((a_world, a), (b_world, b)):
                self.tab(world, window, key)
            model = w4.board(b).model
            with self.subTest(page=key):
                expected = "MEMBER" if key == "BASE_INFO" else key
                self.assertEqual(model["page"], expected, "the base tab is disabled")
                self.assertEqual(model["title"], a.board.title)
                self.assertEqual([t["shown"] for t in model["tabs"]], [a.tabDict[k].shown for k in PAGES])
                self.assertTrue(model["tab_art"].endswith("/tab_%d.sub" % (PAGES.index(expected) + 1)))
        self.assertEqual([t["enabled"] for t in w4.board(b).model["tabs"]], [True, True, True, False, True, True])


class Flows(GuildTest):
    def test_a_tab_s_packets(self):
        def flow(world, window):
            for key in ("BOARD", "MEMBER", "SKILL", "GRADE", "GUILD_INFO"):
                self.tab(world, window, key)
        (legacy, _, _), (novaui, _, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual([c for c in novaui if c[0].startswith("net.Send")], [("net.SendGuildRefreshCommentsPacket", (0,))])

    def test_the_offer_with_too_little_and_with_enough_experience(self):
        for exp, popup in ((50, True), (5000, False)):
            def setup(game, exp=exp):
                guild(game)
                game.modules["player"].GetStatus = lambda kind: exp

            def flow(world, window):
                if world.nui_on:
                    w4.press(window, "offer_press", 0)
                else:
                    window.pageWindow["GUILD_INFO"].GetChild("OfferButton").click()
                world.popup = self.popups(world) if world.nui_on else legacy_popup_text(window)
                dialogs = [d for d in world.game.dialogs if d._name == "uiPickMoney.PickMoneyDialog" and d.is_open]
                if dialogs:
                    dialogs[-1].accept(1234)
            (legacy, a_world, _), (novaui, b_world, _) = self.run_both(flow, setup)
            with self.subTest(exp=exp):
                self.assertEqual([c for c in novaui if not c[0].startswith("uiCommon.PopupDialog")], legacy)
                if popup:
                    self.assertEqual(b_world.popup, [a_world.popup])
                    self.assertEqual(a_world.popup, a_world.m("localeInfo").GUILD_SHORT_EXP)
                else:
                    self.assertIn(("net.SendGuildOfferPacket", (1234,)), novaui)

    def test_the_mark_upload_s_checks_and_the_upload(self):
        cases = (("level", 2, 15, None), ("authority", 15, 0, None), ("upload", 15, 15, "upload/dragon.tga"))
        for name, level, auth, upload in cases:
            def setup(game, level=level, auth=auth):
                guild(game, level=level, my_auth=auth)
                game.w4["files"]["upload"] = ["dragon.tga"]
                game.w4["images"]["upload/dragon.tga"] = (1, 16, 12)

            def flow(world, window):
                if world.nui_on:
                    w4.press(window, "upload_mark_press", 0)
                else:
                    window.pageWindow["GUILD_INFO"].uploadMarkButton.click()
                world.popup = self.popups(world) if world.nui_on else legacy_popup_text(window)
                dialog = window.markSelectDialog
                if dialog.IsShow():
                    world.list_type = type(dialog).__module__
                    if world.nui_on:
                        w4.press(dialog, "row_press", 0, 0)
                        w4.press(dialog, "ok_press", 0)
                    else:
                        dialog.markListBox.SelectIndex(0)
                        dialog.okButton.click()
            (legacy, a_world, _), (novaui, b_world, _) = self.run_both(flow, setup)
            with self.subTest(case=name):
                self.assertEqual([c for c in novaui if not c[0].startswith("uiCommon.PopupDialog")], legacy)
                if upload:
                    self.assertIn(("net.UploadMark", (upload,)), novaui)
                    self.assertEqual((a_world.list_type, b_world.list_type), ("uiUploadMark", "nui_guild_mark"))
                else:
                    self.assertEqual(b_world.popup, [a_world.popup])

    def test_the_declare_button_opens_the_declare_dialog(self):
        def flow(world, window):
            if world.nui_on:
                w4.press(window, "declare_press", 0)
            else:
                window.pageWindow["GUILD_INFO"].declareWarButton.click()
            world.dialog = window.inputDialog
        (legacy, a_world, _), (novaui, b_world, _) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual(type(a_world.dialog).__module__, "uiGuild")
        self.assertEqual(type(b_world.dialog).__module__, "nui_guild_war_declare")
        self.assertTrue(b_world.dialog.IsShow())

    def test_posting_a_comment_with_enter_and_with_the_button(self):
        def flow(world, window):
            nui = world.m("nui")
            for how, text in (("enter", "Meet at the castle tonight " * 3), ("button", "Second note"), ("enter", "")):
                if world.nui_on:
                    board = w4.board(window)
                    if text:
                        board.insert_text("guild-comment", text)
                    if how == "enter":
                        board.key("guild-comment", nui.KEY_RETURN)
                    else:
                        w4.press(window, "post_press", 0)
                else:
                    window.commentSlot.SetText(text)
                    if how == "enter":
                        window.commentSlot.OnIMEReturn()
                    else:
                        window.OnPostComment()
            world.left = w4.board(window).get_value("guild-comment") if world.nui_on else window.commentSlot.GetText()
        (legacy, a_world, _), (novaui, b_world, _) = self.run_both(flow, page="BOARD")
        self.assertEqual(novaui, legacy)
        posts = [c for c in novaui if c[0] == "net.SendGuildPostCommentPacket"]
        self.assertEqual(posts, [("net.SendGuildPostCommentPacket", (("Meet at the castle tonight " * 3)[:50],)),
                                 ("net.SendGuildPostCommentPacket", ("Second note",))])
        self.assertEqual(b_world.left, "")

    def test_f5_refreshes_and_escape_stays_in_the_comment_field(self):
        def flow(world, window):
            if world.nui_on:
                board = w4.board(window)
                world.kept = (board.key("guild-comment", 111), board.key("guild-comment", world.m("nui").KEY_ESCAPE))
            else:
                window.commentSlot.OnKeyDown(63)
        (legacy, _, _), (novaui, b_world, b) = self.run_both(flow, page="BOARD")
        self.assertEqual(novaui, legacy)
        self.assertEqual(novaui, [("net.SendGuildRefreshCommentsPacket", (0,))])
        self.assertEqual(b_world.kept, (True, True))
        self.assertTrue(b.IsShow(), "legacy's edit line keeps Escape: the window stays open")

    def test_a_press_in_the_comment_field_focuses_it_and_holds_wnd_mgr_s_focus(self):
        """GU-02 (validation, N, C and Y): body.guild takes no focus, so RmlUi
        gave a press in the field to nothing (Context::FindFocusElement) and
        the typed keys and Enter went to the game. The field's own mousedown
        focuses it, as the whisper's input does, and the window holds
        wndMgr's focus while it has NovaUI's, as a focused legacy edit line."""
        world, window = self.world(True)
        self.open(world, window)
        self.tab(world, window, "BOARD")
        nui = world.m("nui")
        with world.game, w4.quiet():
            board = w4.board(window)
            proxy_window = window.focusProxy._window
            w4.press(window, "comment_press", 1)
            self.assertNotEqual(board.focused, "guild-comment", "a right press focuses nothing")
            self.assertFalse(proxy_window.IsFocus())
            w4.press(window, "comment_press", 0)
            self.assertEqual(board.focused, "guild-comment")
            self.assertTrue(proxy_window.IsFocus(), "the field's focus takes wndMgr's")
            mark = world.mark()
            board.insert_text("guild-comment", "nuiw4 hello")
            self.assertTrue(board.key("guild-comment", nui.KEY_RETURN))
            self.assertEqual(world.calls_since(mark, "net.SendGuildPostCommentPacket"),
                             [("net.SendGuildPostCommentPacket", ("nuiw4 hello",))])
        self.tab(world, window, "MEMBER")
        self.assertFalse(proxy_window.IsFocus(), "the field goes with its page, and its hold on wndMgr's focus")
        self.tab(world, window, "BOARD")
        with world.game, w4.quiet():
            w4.press(window, "comment_press", 0)
            self.assertTrue(proxy_window.IsFocus())
            window.Close()
        self.assertFalse(proxy_window.IsFocus(), "the close lets wndMgr's focus go")
        with world.game, w4.quiet():
            window.Destroy()
        self.assertIsNone(window.focusProxy)

    def test_the_comment_field_takes_its_press_and_types_like_a_legacy_edit_line(self):
        markup = w4.read(os.path.join(w4.WINDOWS_DIR, "guild", "guild.rml"))
        sheet = w4.read(os.path.join(w4.WINDOWS_DIR, "guild", "guild.rcss"))
        field = markup[markup.index('<input id="guild-comment"'):]
        field = field[:field.index("/>")]
        self.assertIn('data-event-mousedown="comment_press(ev.button)"', field)
        body = markup[markup.index("<body"):]
        body = body[:body.index(">")]
        for name in ("nui-field-passes-hotkeys", "nui-field-keeps-focus"):
            self.assertIn(name, body)
        rule = sheet[sheet.index("body.guild\n"):]
        self.assertIn("focus: none;", rule[:rule.index("}")], "why the field focuses itself")

    def test_delete_and_refresh(self):
        def flow(world, window):
            if world.nui_on:
                w4.press(window, "delete_press", 2, 0)
                w4.press(window, "refresh_press", 0)
            else:
                window.OnDeleteComment(2)
                window.pageWindow["BOARD"].GetChild("RefreshButton").click()
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, page="BOARD")
        self.assertEqual(novaui, legacy)
        self.assertEqual(novaui, [("net.SendGuildDeleteCommentPacket", (3,)), ("net.SendGuildRefreshCommentsPacket", (0,))])

    def test_a_member_s_grade_through_the_combo_box(self):
        def flow(world, window):
            if world.nui_on:
                w4.press(window, "combo_press", 4, 0)
                world.open = (w4.board(window).model["combo_line"], len(w4.board(window).model["combo_items"]))
                w4.press(window, "combo_press", 2, 0)
                world.other = w4.board(window).model["combo_line"]
                w4.press(window, "combo_press", 2, 0)
                w4.press(window, "combo_press", 4, 0)
                w4.press(window, "combo_pick", 3, 0)
                world.after = w4.board(window).model["combo_line"]
            else:
                combo = window.pageWindow["MEMBER"].memberDict[4][1]
                combo.press()
                combo.select(3)
        (legacy, _, _), (novaui, b_world, _) = self.run_both(flow, page="MEMBER")
        self.assertEqual(novaui, legacy)
        self.assertEqual([c for c in novaui if c[0].startswith("net.")], [("net.SendGuildChangeMemberGradePacket", (1004, 3))])
        self.assertEqual(b_world.open, (4, 14), "grades 2 to 15")
        self.assertEqual((b_world.other, b_world.after), (2, -1), "one list at a time; a pick closes it")

    def test_the_master_s_combo_box_and_grade_1_do_nothing(self):
        def flow(world, window):
            if world.nui_on:
                w4.press(window, "combo_press", 0, 0)
                world.line = w4.board(window).model["combo_line"]
            else:
                window.pageWindow["MEMBER"].memberDict[0][1].press()
        (legacy, _, _), (novaui, b_world, _) = self.run_both(flow, page="MEMBER")
        self.assertEqual((novaui, legacy), ([], []))
        self.assertEqual(b_world.line, -1)

    def test_a_member_s_general_flag(self):
        def flow(world, window):
            if world.nui_on:
                w4.press(window, "general_press", 1, 0)
            else:
                window.pageWindow["MEMBER"].memberDict[1][5].OnMouseLeftButtonUp()
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, page="MEMBER")
        self.assertEqual(novaui, legacy)
        self.assertEqual(novaui, [("net.SendGuildChangeMemberGeneralPacket", (1001, 0))])

    def test_the_member_scroll_moves_legacy_s_line_window(self):
        def flow(world, window):
            if world.nui_on:
                w4.press(window, "combo_press", 4, 0)
                w4.fire(window, "member_scroll", 0.5)
                world.first = w4.board(window).model["members"][0]["name"]
                world.combo = w4.board(window).model["combo_line"]
                w4.fire(window, "member_wheel", 1)
                world.wheel = window.memberLinePos
            else:
                # The loader sizes legacy's scroll bar from its uiscript ("size": 270).
                window.pageWindow["MEMBER"].scrollBar.SetScrollBarSize(270)
                window.pageWindow["MEMBER"].scrollBar.drag_to(0.5)
            world.pos = window.memberLinePos
        (legacy, a_world, _), (novaui, b_world, _) = self.run_both(flow, page="MEMBER")
        self.assertEqual(a_world.pos, int(17 * 0.5))
        self.assertEqual(b_world.first, "Member08")
        self.assertEqual(b_world.combo, -1, "the scroll closes the open list, as legacy")
        self.assertEqual(b_world.wheel, int(17 * (0.5 + 1.0 / 17)))

    def test_the_skills_pick_use_up_and_hover(self):
        def flow(world, window):
            slots = window.pageWindow["SKILL"].activeSlot
            if world.nui_on:
                w4.press(window, "active_press", 1, 0)
                world.attached = world.mouse.isAttached()
                world.mouse.DeattachObject()
                w4.press(window, "active_press", 2, 1)
                w4.press(window, "plus_press", 3, 0)
                w4.fire(window, "active_over", 4)
                w4.fire(window, "active_out", 4)
            else:
                slots.fire("select_item", 211)
                world.attached = world.mouse.isAttached()
                world.mouse.DeattachObject()
                slots.fire("unselect_item", 212)
                slots.events["pressed_button"](213)
                slots.fire("over_in", 214)
                slots.fire("over_out")
            world.tips = list(world.tooltip_skill.calls)
        (legacy, a_world, _), (novaui, b_world, _) = self.run_both(flow, page="SKILL")
        self.assertEqual(novaui, legacy)
        self.assertEqual((a_world.attached, b_world.attached), (True, True))
        self.assertIn(("mouse.AttachObject", (P["SLOT_TYPE_SKILL"], 211, 153, 0)), novaui)
        self.assertIn(("player.UseGuildSkill", (212,)), novaui)
        self.assertIn(("net.SendChatPacket", ("/gskillup 155",)), novaui)
        self.assertEqual(b_world.tips, a_world.tips)
        self.assertEqual(b_world.tips[0], ("SetSkill", 156, 7))

    def test_a_level_0_skill_is_not_used_and_the_cooldown_shows(self):
        world, window = self.world(True)
        self.open(world, window)
        self.tab(world, window, "SKILL")
        mark = world.mark()
        with world.game, w4.quiet():
            w4.press(window, "active_press", 0, 1)
            window.OnUseSkill(211, 30.0)
        self.assertEqual(world.calls_since(mark, "player.UseGuildSkill"), [])
        cell = w4.board(window).model["active_cells"][1]
        self.assertGreater(cell["cd_end"], cell["cd_start"])

    def test_the_dragon_power_heal(self):
        for current, popup in ((100, True), (40, False)):
            def setup(game, current=current):
                guild(game, gp=(current, 100))

            def flow(world, window):
                if world.nui_on:
                    w4.press(window, "heal_press", 0)
                else:
                    window.pageWindow["SKILL"].btnHealGSP.click()
                world.popup = self.popups(world) if world.nui_on else legacy_popup_text(window)
                picks = [d for d in world.game.dialogs if d._name == "uiPickMoney.PickMoneyDialog" and d.is_open]
                if picks:
                    picks[-1].accept(10)
                    questions = [d for d in world.game.dialogs if d._name == "uiCommon.QuestionDialog" and d.is_open]
                    questions[-1].accept()
            (legacy, a_world, _), (novaui, b_world, _) = self.run_both(flow, setup, page="SKILL")
            with self.subTest(current=current):
                self.assertEqual([c for c in novaui if not c[0].startswith("uiCommon.PopupDialog")], legacy)
                if popup:
                    self.assertEqual(b_world.popup, [a_world.m("localeInfo").GUILD_CANNOT_HEAL_GSP_ANYMORE])
                else:
                    self.assertIn(("net.SendGuildChargeGSPPacket", (10,)), novaui)

    def test_a_grade_s_name_through_its_dialog(self):
        for how, text, sent in (("enter", "Elite", "Elite"), ("ok", "", None), ("escape", "Nope", False),
                                ("cancel", "Nope", False)):
            def flow(world, window, how=how, text=text):
                if world.nui_on:
                    w4.press(window, "grade_name_press", 3, 0)
                    dialog = window.changeGradeNameDialog
                    board = w4.board(dialog)
                    world.focused = board.focused
                    if text:
                        board.insert_text("guild-grade-name-field", text)
                    nui = world.m("nui")
                    if how == "enter":
                        board.key("guild-grade-name-field", nui.KEY_RETURN)
                    elif how == "escape":
                        board.key("guild-grade-name-field", nui.KEY_ESCAPE)
                    else:
                        w4.press(dialog, how == "ok" and "accept_press" or "cancel_press", 0)
                else:
                    window.pageWindow["GRADE"].gradeDict[3][0].OnMouseLeftButtonUp()
                    dialog = window.changeGradeNameDialog
                    dialog.gradeNameSlot.SetText(text)
                    if how == "enter":
                        dialog.gradeNameSlot.OnIMEReturn()
                    elif how == "escape":
                        dialog.gradeNameSlot.OnPressEscapeKey()
                    else:
                        dialog.GetChild("AcceptButton" if how == "ok" else "CancelButton").click()
                world.dialog_shown = window.changeGradeNameDialog.IsShow()
            (legacy, a_world, _), (novaui, b_world, _) = self.run_both(flow, page="GRADE")
            with self.subTest(how=how):
                self.assertEqual(novaui, legacy)
                packets = [c for c in novaui if c[0] == "net.SendGuildChangeGradeNamePacket"]
                if sent is False:
                    self.assertEqual(packets, [])
                else:
                    name = sent or b_world.m("localeInfo").GUILD_DEFAULT_GRADE
                    self.assertEqual(packets, [("net.SendGuildChangeGradeNamePacket", (3, name))])
                self.assertFalse(b_world.dialog_shown)
                self.assertEqual(b_world.focused, "guild-grade-name-field", "Open focuses the field")

    def test_the_grade_name_dialog_opens_50_px_below_the_pointer(self):
        """GU-06-below (validation, N, C and Y): D21 and spec 5.9.5 put the
        dialog where legacy's Open puts it, the uiscript's 170 px centered
        under the pointer, 50 px below it, in dp; the scrim still dims the
        rest. Kept on the screen."""
        for mouse, scale, place in (((300, 200), 1.0, (215.0, 250.0)), ((600, 400), 1.5, (343.3333, 300.0)),
                                    ((1590, 880), 1.0, (1430.0, 810.0))):
            world, window = self.world(True)
            self.open(world, window)
            self.tab(world, window, "GRADE")
            world.m("wndMgr").mouse = mouse
            world.game.state.scale = scale
            with world.game, w4.quiet():
                w4.press(window, "grade_name_press", 3, 0)
                model = w4.board(window.changeGradeNameDialog).model
                with self.subTest(mouse=mouse, scale=scale):
                    self.assertTrue(model["placed"])
                    self.assertAlmostEqual(model["x"], place[0], places=3)
                    self.assertAlmostEqual(model["y"], place[1], places=3)
                window.changeGradeNameDialog.SetCenterPosition()
                self.assertFalse(w4.board(window.changeGradeNameDialog).model["placed"])
        markup = w4.read(os.path.join(w4.WINDOWS_DIR, "guild-grade-name", "guild-grade-name.rml"))
        for binding in ('data-class-guild-grade-name--placed="placed"', "data-style---grade-name-x=\"x + 'dp'\"",
                        "data-style---grade-name-y=\"y + 'dp'\""):
            self.assertIn(binding, markup)

    def test_grade_1_opens_no_dialog(self):
        def flow(world, window):
            if world.nui_on:
                w4.press(window, "grade_name_press", 1, 0)
                w4.press(window, "auth_press", 1, 4, 0)
            else:
                window.pageWindow["GRADE"].gradeDict[1][0].OnMouseLeftButtonUp()
                window.pageWindow["GRADE"].gradeDict[1][3].OnMouseLeftButtonUp()
            world.dialog_shown = window.changeGradeNameDialog.IsShow()
        (legacy, _, _), (novaui, b_world, _) = self.run_both(flow, page="GRADE")
        self.assertEqual((novaui, legacy), ([], []))
        self.assertFalse(b_world.dialog_shown)

    def test_a_grade_s_authority(self):
        def flow(world, window):
            for column, bit in enumerate((1, 2, 4, 8), 1):
                if world.nui_on:
                    w4.press(window, "auth_press", 2, bit, 0)
                else:
                    window.pageWindow["GRADE"].gradeDict[2][column].OnMouseLeftButtonUp()
        (legacy, _, _), (novaui, _, _) = self.run_both(flow, page="GRADE")
        self.assertEqual(novaui, legacy)
        auth = 7
        self.assertEqual([c[1] for c in novaui if c[0] == "net.SendGuildChangeGradeAuthorityPacket"],
                         [(2, auth ^ 1), (2, auth ^ 2), (2, auth ^ 4), (2, auth ^ 8)])

    def test_the_war_s_start_and_end_set_an_enemy(self):
        def flow(world, window):
            window.OnStartGuildWar(7, 42)
            world.started = list(w4.board(window).model["enemies"]) if world.nui_on else None
            window.OnEndGuildWar(7, 42)
        (legacy, _, a), (novaui, b_world, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertIn("guild 42", b_world.started)
        self.assertEqual(w4.board(b).model["enemies"], [line.GetText() for line in a.enemyGuildNameList])

    def test_escape_and_the_close_button_close_it(self):
        for how in ("escape", "close"):
            def flow(world, window, how=how):
                if world.nui_on and how == "close":
                    w4.press(window, "close_press", 0)
                elif how == "close":
                    window.board.close()
                else:
                    window.OnPressEscapeKey()
            (legacy, _, a), (novaui, world, b) = self.run_both(flow)
            with self.subTest(how=how):
                self.assertEqual(novaui, legacy)
                self.assertFalse(b.IsShow())
                self.assertNotIn(DOCUMENT, world.documents())

    def test_delete_guild_hides_it(self):
        def flow(world, window):
            window.DeleteGuild()
        (legacy, _, _), (novaui, world, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertFalse(b.IsShow())


class Facade(GuildTest):
    def test_the_class_the_methods_and_no_per_frame_python(self):
        world, window = self.world(True)
        legacy_class = world.m("uiGuild").GuildWindow
        self.assertIsInstance(window, legacy_class)
        self.assertTrue(window.NUI_FACADE)
        self.assertIsNone(type(window).OnUpdate)
        self.assertIsNone(type(window).OnRender)
        for name in ("CanOpen", "DeleteGuild", "Destroy", "Hide", "IsShow", "OnEndGuildWar", "OnStartGuildWar",
                     "OnUseSkill", "Open", "OverOutItem", "RefreshGuildBoardPage", "RefreshGuildGradePage",
                     "RefreshGuildInfoPage", "RefreshGuildMemberPage", "RefreshGuildMemberPageGradeComboBox",
                     "RefreshGuildSkillPage", "SetSkillToolTip"):
            self.assertTrue(callable(getattr(window, name)), name)
        self.assertFalse(any("RefreshGuildGrade" in vars(cls) for cls in type(window).__mro__),
                         "D16: the C++ callback has no method, as legacy")
        for name, member in inspect.getmembers(legacy_class, inspect.isfunction):
            self.assertEqual(len(inspect.signature(getattr(type(window), name)).parameters),
                             len(inspect.signature(member).parameters), name)
        for module_name in ("nui_guild", "nui_guild_grade_name"):
            module = world.m(module_name)
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ == module_name:
                    for attr in ("OnUpdate", "OnRender"):
                        self.assertFalse(callable(getattr(cls, attr, None)), "%s.%s" % (name, attr))

    def test_make_builds_legacy_with_the_flag_off_an_older_exe_or_right_to_left(self):
        world, window = self.world(False)
        self.assertIs(type(window), world.m("uiGuild").GuildWindow)
        world, window = self.world(True, engine_4=False)
        self.assertIs(type(window), world.m("uiGuild").GuildWindow)

        def rtl(game):
            guild(game)
            game.modules["nui"].enabled_for_locale = lambda: False
        world, window = self.world(True, setup=rtl)
        self.assertIs(type(window), world.m("uiGuild").GuildWindow)
        self.assertEqual(world.m("nui_windows").DECISIONS["guild"], "legacy: right-to-left locale")

    def test_the_novaui_loader_never_takes_legacy_s_right_to_left_branches(self):
        world, window = self.world(True)
        mark = world.mark()
        self.open(world, window)
        self.assertEqual(world.calls_since(mark, "app.IsRTL"), [])
        self.assertIsNone(window.pageWindow["GUILD_INFO"].guildMoneySlot, "no guild money row left to right")

    def test_on_demand_centered_and_the_0_by_0_window(self):
        (a_world, a), (world, window) = [self.world(nui_on) for nui_on in (False, True)]
        self.assertNotIn(DOCUMENT, world.documents())
        self.open(a_world, a)
        self.open(world, window)
        self.assertIn(DOCUMENT, world.documents())
        self.assertEqual(w4.board(window).placement, ("center",), "P18: centered, where legacy's is at the corner (D21)")
        self.assertEqual((window.GetWidth(), window.GetHeight()), (0, 0))
        self.assertIn("float", window.flags)
        self.assertEqual(window.flags, a.flags)
        self.assertNotIn(GRADE_DOCUMENT, world.documents())

    def test_centered_at_the_first_open_and_a_dragged_place_kept_after_it(self):
        """P18 (Eddy: "Make it centered"): the first open centers the board in
        every look; a window the player left centered is centered again at
        its next open; one dragged away opens where it was left, as the other
        NovaUI windows do (nui_facade.Facade, PLACE "center")."""
        world, window = self.world(True)
        self.assertEqual(type(window).PLACE, "center")
        boxes = world.game.state.boxes
        self.open(world, window)
        self.assertEqual(w4.board(window).placement, ("center",))
        # At the screen's center (1600 x 900, the 480 x 470 board): left centered.
        boxes[(DOCUMENT, "")] = (560.0, 215.0, 480.0, 470.0)
        with world.game, w4.quiet():
            window.Close()
        self.assertNotIn(DOCUMENT, world.documents())
        self.open(world, window)
        self.assertEqual(w4.board(window).placement, ("center",), "left centered: centered again")
        # Dragged away by its title: kept at the next open.
        boxes[(DOCUMENT, "")] = (300.0, 120.0, 480.0, 470.0)
        with world.game, w4.quiet():
            window.Close()
        self.open(world, window)
        self.assertEqual(w4.board(window).placement, ("position", 300.0, 120.0, (0.0, 0.0)), "the dragged place")
        # The kept place holds at a later open too.
        with world.game, w4.quiet():
            window.Close()
        self.open(world, window)
        self.assertEqual(w4.board(window).placement, ("position", 300.0, 120.0, (0.0, 0.0)))

    def test_left_centered_where_it_does_not_fit_it_is_centered_again_after_a_scale_change(self):
        """P18 review: at 200% on 1600 x 900 the 470dp board is 940 px tall,
        so the runtime's Center puts it at y 0. Closed there without a drag,
        it is still a centered window: after a switch to 100% it opens
        centered, not at the old place in dp."""
        world, window = self.world(True)
        nui = world.game.modules["nui"]
        boxes = world.game.state.boxes
        with world.game:
            nui.set_scale_percent(200)
        self.open(world, window)
        self.assertEqual(w4.board(window).placement, ("center",))
        boxes[(DOCUMENT, "")] = (320.0, 0.0, 960.0, 940.0)
        with world.game, w4.quiet():
            window.Close()
            nui.set_scale_percent(100)
        self.open(world, window)
        self.assertEqual(w4.board(window).placement, ("center",), "not ('position', 160.0, 0.0, ...)")
        # Dragged at 200%: that place is kept, in dp, at 100% too.
        with world.game, w4.quiet():
            window.Close()
            nui.set_scale_percent(200)
        self.open(world, window)
        boxes[(DOCUMENT, "")] = (320.0, 40.0, 960.0, 940.0)
        with world.game, w4.quiet():
            window.Close()
            nui.set_scale_percent(100)
        self.open(world, window)
        self.assertEqual(w4.board(window).placement, ("position", 160.0, 20.0, (0.0, 0.0)))

    def test_destroy_discards_the_dialogs_it_made(self):
        world, window = self.world(True)
        self.open(world, window)
        self.tab(world, window, "GRADE")
        with world.game, w4.quiet():
            w4.press(window, "grade_name_press", 2, 0)
            self.assertIn(GRADE_DOCUMENT, world.documents())
            window.Destroy()
        self.assertNotIn(GRADE_DOCUMENT, world.documents())
        self.assertNotIn(DOCUMENT, world.documents())

    def test_the_member_lines_are_the_limits_module_s(self):
        world, window = self.world(True)
        limits = world.m("nui_limits").current()
        self.assertEqual(limits.GUILD_MEMBER_LINES, world.m("uiGuild").GuildWindow.MEMBER_LINE_COUNT)
        self.assertEqual(limits.GUILD_GRADE_COUNT, 15)

    def test_every_fixture_has_the_model_s_keys_and_kinds(self):
        world, window = self.world(True)
        kinds = w4.model_kinds(window.nui_model())
        for variant in ("", "board", "member", "member-open", "base", "skill", "grade", "foundation",
                        "foundation-member"):
            self.assertEqual(w4.fixture_keys(window, "guild", variant), kinds, variant)
        for variant in ("", "placed"):
            self.assertEqual(w4.fixture_keys(window, "guild-grade-name", variant),
                             {"max": "int", "placed": "bool", "x": "float", "y": "float"}, variant)

    def test_no_repeated_element_binds_its_own_entry_in_a_shrinking_list(self):
        from nui_hud_test import repeated_element_reads
        markup = w4.read(os.path.join(w4.WINDOWS_DIR, "guild", "guild.rml"))
        reads = [found for found in repeated_element_reads(markup)
                 if found[0].split(":")[-1].strip() not in ("tabs", "enemies", "comments", "members", "grades",
                                                            "base_rows", "base_columns", "combo_items",
                                                            "passive_cells", "active_cells", "affect_cells")]
        self.assertEqual(reads, [], "only the fixed-length lists' elements read their entry")

    def test_the_wiring_lines(self):
        text = w4.read(os.path.join(w4.ROOT, "interfacemodule.py"))
        self.assertIn('self.wndGuild = nui_windows.make("guild", uiGuild.GuildWindow, "nui_guild.GuildWindow")', text)
        guild_text = w4.read(os.path.join(w4.ROOT, "uiguild.py"))
        self.assertIn('import nui_windows', guild_text)
        self.assertIn('nui_windows.make("guild-mark", uiUploadMark.MarkSelectDialog, "nui_guild_mark.MarkSelectDialog")',
                      guild_text)


if __name__ == "__main__":
    unittest.main()
