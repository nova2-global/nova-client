"""Tests for the NovaUI guild war dialogs and the guild mark and symbol lists
(assets/root/nui_guild_war_declare.py, nui_guild_war_accept.py,
nui_guild_mark.py; P16 spec 5.10, 5.11): python3 -B -m unittest
nui_guild_dialogs_test (from tools/).

Each dialog in a legacy world (uiGuild's and uiUploadMark's classes, their
uiscripts read as the client reads them) and in a NovaUI world with the same
state, made as their callers make them (the guild window's declare button,
game.py's __GuildWar_OpenAskDialog, the guild window's info page), driven
through every flow of spec 5.10.4 and 5.11.4 and compared call for call (the
chat commands, the uploads' select events, the popups by their text: legacy
shows its own popup window, NovaUI the dialog kit's). Also: the boards'
models against the legacy widgets, the facades, make() with the flag off and
with an older exe, the documents on demand, the fixtures."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402
import nui_w4_world as w4  # noqa: E402

DECLARE_DOCUMENT = "nui/windows/guild-war-declare/guild-war-declare.rml"
ACCEPT_DOCUMENT = "nui/windows/guild-war-accept/guild-war-accept.rml"
MARK_DOCUMENT = "nui/windows/guild-mark/guild-mark.rml"
FIELD = "guild-war-name"
# The war's member cap and end score (NOVA-90).
MEMBERS, SCORE = "guild-war-members", "guild-war-score"
EFFECTS = support.W4_COMPARED + ("snd",)
MARK_FILES = ["wolf.tga", "castle.png", "dragon.tga", "flag.bmp", "old_sign.jpeg", "rose.png", "sword.jpg", "lion.tga",
              "notes.txt"]


def world_of(nui_on, setup=None, **kwargs):
    return w4.World(nui_on, setup=setup, social=True, **kwargs)


def legacy_popup(dialog):
    """The text of a legacy list's own popup window while it shows."""
    return dialog.popupText.GetText() if dialog.popupDialog.IsShow() else None


def kit_popups(world, mark=0):
    """The dialog kit's popup texts opened since `mark` (NovaUI)."""
    return [args[0] for name, args in world.game.log[mark:] if name == "uiCommon.PopupDialog.Open"]


# --- the declare dialog --------------------------------------------------------------------------------------

class DeclareTest(unittest.TestCase):
    def open(self, nui_on, setup=None, **kwargs):
        """The guild window's declare button (uiguild.py
        __OnClickDeclareWarButton): make(), then Open."""
        world = world_of(nui_on, setup, **kwargs)
        # The limit fields' changes reach their handlers, as RmlUi's change.
        for field, event in ((MEMBERS, "members_change"), (SCORE, "score_change")):
            world.game.state.field_events[(DECLARE_DOCUMENT, field)] = event
        dialog = world.make("guild-war-dialogs", "uiGuild", "DeclareGuildWarDialog",
                            "nui_guild_war_declare.DeclareGuildWarDialog")
        with world.game, w4.quiet():
            dialog.Open()
        return world, dialog

    def type(self, world, dialog, text):
        if world.nui_on:
            w4.board(dialog).insert_text(FIELD, text)
        else:
            dialog.inputValue.SetText(text)

    def set_limit(self, world, dialog, field, text):
        """A limit field's text as a player leaves it: NovaUI's field emptied
        and typed, legacy's edit line set (its IME takes digits only)."""
        if world.nui_on:
            board = w4.board(dialog)
            board.set_value(field, "")
            if text:
                board.insert_text(field, text)
        else:
            {MEMBERS: dialog.memberCountInput, SCORE: dialog.endScoreInput}[field].SetText(text)

    def assert_the_board_waits(self, world):
        """P18: the closed dialog's board waits, hidden and emptied, in the
        pool for the next dialog: the only declare document left."""
        (board,) = world.m("nui_guild_war_declare").POOL.boards()
        self.assertEqual(world.documents().count(DECLARE_DOCUMENT), 1)
        self.assertFalse(board.is_visible())
        self.assertEqual((board.model["types_on"], board.fields.get(FIELD, "")), ([], ""))
        self.assertEqual((board.fields.get(MEMBERS, ""), board.fields.get(SCORE, "")), ("", ""), "the limits emptied too")
        self.assertIs(board._owner, world.m("nui_hud").NO_OWNER)
        return board

    def run_both(self, flow, setup=None):
        results = []
        for nui_on in (False, True):
            world, dialog = self.open(nui_on, setup)
            mark = world.mark()
            with world.game, w4.quiet():
                flow(world, dialog)
            results.append((world.effects_since(mark, EFFECTS), world, dialog))
        return results

    def test_open_focuses_the_field_on_a_modal_with_the_types_and_their_hints(self):
        world, dialog = self.open(True)
        board = w4.board(dialog)
        self.assertTrue(board.modal)
        self.assertEqual(board.focused, FIELD, "Open focuses the field")
        self.assertIsNone(board.placement, "the scrim centers it")
        locale = world.m("localeInfo")
        model = board.model
        # The client's guild.GUILD_NAME_MAX_LEN since NOVA-97 (24; the
        # uiscript's 12 before).
        self.assertEqual((model["type"], model["type_select"], model["max"]), (0, True, 24))
        # NOVA-90: the member cap and the end score at 32 each, as legacy's Open sets them.
        self.assertEqual((board.get_value(MEMBERS), board.get_value(SCORE)), ("32", "32"))
        self.assertTrue(dialog.memberCountInput.number_mode and dialog.endScoreInput.number_mode)
        self.assertEqual([hint["title"] for hint in model["hints"]],
                         [locale.GUILDWAR_NORMAL_TITLE, locale.GUILDWAR_WARP_TITLE, locale.GUILDWAR_CTF_TITLE])
        self.assertEqual(model["hints"][2]["lines"], list(locale.GUILDWAR_CTF_DESCLIST))
        self.assertEqual([hint["label"] for hint in model["hints"]],
                         [world.m("uiScriptLocale").GUILD_WAR_NORMAL, world.m("uiScriptLocale").GUILD_WAR_WARP,
                          world.m("uiScriptLocale").GUILD_WAR_CTF])

    def test_a_type_button_chooses_the_type(self):
        def flow(world, dialog):
            for index in (2, 1, 1):
                if world.nui_on:
                    w4.press(dialog, "type_press", index, 0)
                else:
                    dialog.typeButtonList[index].click()
            world.type = dialog.GetType()
            world.down = [button.down for button in dialog.typeButtonList]
        (legacy, a_world, _), (novaui, b_world, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual((b_world.type, b_world.down), (a_world.type, a_world.down))
        self.assertEqual(b_world.type, 1)
        self.assertEqual(w4.board(b).model["type"], 1)

    def test_ok_and_enter_send_the_war_command_and_close(self):
        for how in ("ok", "enter"):
            def flow(world, dialog, how=how):
                self.type(world, dialog, "Black Wolves")
                if world.nui_on:
                    w4.press(dialog, "type_press", 2, 0)
                    if how == "ok":
                        w4.press(dialog, "accept_press", 0)
                    else:
                        world.kept = w4.board(dialog).key(FIELD, world.m("nui").KEY_RETURN)
                else:
                    dialog.typeButtonList[2].click()
                    if how == "ok":
                        dialog.acceptButton.click()
                    else:
                        dialog.inputValue.OnIMEReturn()
            (legacy, _, _), (novaui, world, b) = self.run_both(flow)
            with self.subTest(how=how):
                self.assertEqual(novaui, legacy)
                # With the member cap and end score since NOVA-90 (legacy's 32 each).
                self.assertEqual(novaui, [("net.SendChatPacket", ("/war Black Wolves 2 32 32",))])
                self.assertFalse(b.IsShow())
                self.assert_the_board_waits(world)
                if how == "enter":
                    self.assertTrue(world.kept, "the field keeps Enter")

    def test_the_member_cap_and_end_score_go_with_the_declaration(self):
        """NOVA-90 (uiguild.py GetWarLimits): the limits as typed when both
        hold a number; without them (an empty field) the server's defaults."""
        for members, score, sent in (("10", "50", "/war Black Wolves 0 10 50"), ("", "50", "/war Black Wolves 0"),
                                     ("8", "", "/war Black Wolves 0")):
            def flow(world, dialog, members=members, score=score):
                self.type(world, dialog, "Black Wolves")
                self.set_limit(world, dialog, MEMBERS, members)
                self.set_limit(world, dialog, SCORE, score)
                if world.nui_on:
                    w4.press(dialog, "accept_press", 0)
                else:
                    dialog.acceptButton.click()
            (legacy, _, _), (novaui, _, b) = self.run_both(flow)
            with self.subTest(members=members, score=score):
                self.assertEqual(novaui, legacy)
                self.assertEqual(novaui, [("net.SendChatPacket", (sent,))])
                self.assertFalse(b.IsShow())

    def test_a_limit_field_takes_digits_and_keeps_enter_and_escape(self):
        """Legacy's limit edit lines are in number mode after Open, and bind
        no return or escape event: Enter and Escape there do nothing, and
        the field keeps the key."""
        world, dialog = self.open(True)
        board = w4.board(dialog)
        nui = world.m("nui")
        with world.game, w4.quiet():
            self.set_limit(world, dialog, MEMBERS, "4x2")
            self.assertEqual(board.get_value(MEMBERS), "42")
            self.assertEqual(dialog.memberCountInput.GetText(), "42")
            mark = world.mark()
            self.assertTrue(board.key(SCORE, nui.KEY_RETURN))
            self.assertTrue(board.key(MEMBERS, nui.KEY_ESCAPE))
            self.assertEqual(world.effects_since(mark, EFFECTS), [])
            self.assertTrue(dialog.IsShow())
            self.type(world, dialog, "Red Sun")
            w4.press(dialog, "accept_press", 0)
        self.assertEqual(world.effects_since(mark, EFFECTS), [("net.SendChatPacket", ("/war Red Sun 0 42 32",))])

    def test_an_empty_name_sends_nothing_and_stays_open(self):
        def flow(world, dialog):
            if world.nui_on:
                w4.press(dialog, "accept_press", 0)
            else:
                dialog.acceptButton.click()
        (legacy, _, _), (novaui, _, b) = self.run_both(flow)
        self.assertEqual((novaui, legacy), ([], []))
        self.assertTrue(b.IsShow())

    def test_cancel_escape_and_the_close_button_send_nothing(self):
        for how in ("cancel", "escape", "close"):
            def flow(world, dialog, how=how):
                self.type(world, dialog, "Black Wolves")
                if world.nui_on:
                    if how == "escape":
                        world.kept = w4.board(dialog).key(FIELD, world.m("nui").KEY_ESCAPE)
                    else:
                        w4.press(dialog, "cancel_press" if how == "cancel" else "close_press", 0)
                else:
                    {"cancel": dialog.cancelButton.click, "escape": dialog.inputValue.OnPressEscapeKey,
                     "close": dialog.board.close}[how]()
            (legacy, _, _), (novaui, world, b) = self.run_both(flow)
            with self.subTest(how=how):
                self.assertEqual((novaui, legacy), ([], []))
                self.assertFalse(b.IsShow())
                self.assert_the_board_waits(world)
                if how == "escape":
                    self.assertTrue(world.kept, "the field keeps Escape")

    def test_the_next_press_s_dialog_takes_the_waiting_board_with_none_of_the_last_name(self):
        """P18: the guild window makes a new dialog at each press; the
        canceled dialog's board waits and the next dialog shows it with no
        load: its own type, an empty field with the focus, its own events."""
        world, first = self.open(True)
        board = w4.board(first)
        with world.game, w4.quiet():
            board.insert_text(FIELD, "Black Wolves")
            w4.press(first, "type_press", 2, 0)
            w4.press(first, "cancel_press", 0)
            self.assert_the_board_waits(world)
            pool = world.m("nui_guild_war_declare").POOL
            loads = pool.loads
            second = world.make("guild-war-dialogs", "uiGuild", "DeclareGuildWarDialog",
                                "nui_guild_war_declare.DeclareGuildWarDialog")
            second.Open()
            self.assertIs(w4.board(second), board, "no load: the waiting board")
            self.assertEqual(pool.loads, loads)
            self.assertEqual(board.get_value(FIELD), "", "none of the last dialog's name")
            self.assertEqual((board.get_value(MEMBERS), board.get_value(SCORE)), ("32", "32"), "the new dialog's limits")
            self.assertEqual(board.focused, FIELD)
            self.assertEqual((board.model["type"], board.model["types_on"]), (0, [1]), "the new dialog's own type")
            mark = world.mark()
            board.insert_text(FIELD, "Red Sun")
            w4.press(second, "accept_press", 0)
        self.assertEqual(world.effects_since(mark, EFFECTS), [("net.SendChatPacket", ("/war Red Sun 0 32 32",))])
        self.assertLessEqual(pool.most, 1)

    def test_the_phase_end_unloads_the_waiting_board(self):
        world, dialog = self.open(True)
        with world.game, w4.quiet():
            w4.press(dialog, "cancel_press", 0)
            self.assert_the_board_waits(world)
            world.m("nui_windows").end_phase()
        self.assertNotIn(DECLARE_DOCUMENT, world.documents())

    def test_the_name_never_enters_the_model(self):
        world, dialog = self.open(True)
        board = w4.board(dialog)
        board.insert_text(FIELD, "Secret Guild")
        self.assertNotIn("Secret Guild", repr(board.model))
        self.assertNotIn("Secret Guild", repr(dialog._state))

    def test_the_field_s_limit_is_the_limits_module_s(self):
        world = world_of(True)
        limits = world.m("nui_limits")
        limits.use(limits.foundation())
        try:
            dialog = world.make("guild-war-dialogs", "uiGuild", "DeclareGuildWarDialog",
                                "nui_guild_war_declare.DeclareGuildWarDialog")
            with world.game, w4.quiet():
                dialog.Open()
            self.assertEqual(w4.board(dialog).model["max"], 24, "OLD's guild names (spec 3.1)")
        finally:
            limits.use(None)


# --- the accept dialog ---------------------------------------------------------------------------------------

NUITOOL = os.environ.get("NUITOOL") or __import__("shutil").which("nuitool")
ASSETS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets"))
TYPE_KEYS = ("GUILD_WAR_NORMAL", "GUILD_WAR_WARP", "GUILD_WAR_CTF")


@unittest.skipUnless(NUITOOL, "set NUITOOL to a nuitool build (or put nuitool on PATH)")
class TypeLabelsInEveryLocale(unittest.TestCase):
    """Review: the modern dialogs gave each battle type a third of a 280dp
    dialog, so a long label (ru "Поле битвы", hu "Harcmező", it "Bandiera")
    was cut mid-word. Each button is as wide as its label now, in a wider
    dialog: in every left-to-right locale the three buttons lie inside the
    dialog's window, side by side, none narrower than its label."""

    def test_the_type_buttons_fit_their_labels(self):
        import json
        import subprocess
        import tempfile
        from PIL import ImageFont
        font = ImageFont.truetype(os.path.join(ASSETS, "nui", "nui", "fonts", "NotoSans-Bold.ttf"), 14)
        locales = sorted(name for name in os.listdir(os.path.join(ASSETS, "locale", "locale"))
                         if name not in ("common", "ae"))
        with tempfile.TemporaryDirectory() as work:
            for locale in locales:
                table = {}
                with open(os.path.join(ASSETS, "locale", "locale", locale, "locale_interface.txt"), encoding="utf-8") as handle:
                    for line in handle.read().split("\n"):
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            table[parts[0]] = parts[1]
                labels = [table[key] for key in TYPE_KEYS]
                for name, model in (("guild-war-declare", "guild_war_declare"), ("guild-war-accept", "guild_war_accept")):
                    folder = os.path.join(ASSETS, "nui", "nui", "windows", name)
                    with open(os.path.join(folder, name + ".fixture.json"), encoding="utf-8") as handle:
                        fixture = json.load(handle)
                    for hint, label in zip(fixture[model]["hints"], labels):
                        hint["label"] = label
                    fixture_path = os.path.join(work, "%s-%s.json" % (name, locale))
                    with open(fixture_path, "w", encoding="utf-8") as handle:
                        json.dump(fixture, handle, ensure_ascii=False)
                    boxes_path = os.path.join(work, "%s-%s.boxes.json" % (name, locale))
                    subprocess.run([NUITOOL, "snap", "--root", os.path.join(ASSETS, "nui"), "--root", os.path.join(ASSETS, "ETC"),
                                    "--locale", os.path.join(ASSETS, "locale", "locale", locale),
                                    "--doc", "nui/windows/%s/%s.rml" % (name, name), "--fixture", fixture_path,
                                    "--theme", "modern-dark", "--scale", "1", "--size", "800x450",
                                    "--out", os.path.join(work, "frame.png"), "--boxes", boxes_path],
                                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    with open(boxes_path, encoding="utf-8") as handle:
                        boxes = json.load(handle)
                    window = boxes[name]
                    buttons = [boxes["guild-war-type-%d" % i] for i in range(3)]
                    with self.subTest(window=name, locale=locale):
                        for (x, y, w, h), label in zip(buttons, labels):
                            self.assertGreaterEqual(x, window[0])
                            self.assertLessEqual(x + w, window[0] + window[2] + 0.5, label)
                            self.assertGreaterEqual(w, font.getlength(label), label)
                        for left, right in zip(buttons, buttons[1:]):
                            if abs(left[1] - right[1]) < 0.5:
                                self.assertLessEqual(left[0] + left[2], right[0] + 0.5)


class AcceptTest(unittest.TestCase):
    def open(self, nui_on, name="Black Wolves", war_type=2, limits=(), **kwargs):
        """game.py __GuildWar_OpenAskDialog: make(), the accept and cancel
        events (the game window's /war and /nowar, then its Close), Open
        (with the war's member cap and end score, NOVA-90, when given)."""
        world = world_of(nui_on, **kwargs)
        dialog = world.make("guild-war-dialogs", "uiGuild", "AcceptGuildWarDialog",
                            "nui_guild_war_accept.AcceptGuildWarDialog")
        net = world.m("net")

        def accept():
            net.SendChatPacket("/war " + dialog.GetGuildName())
            dialog.Close()
            return 1

        def decline():
            net.SendChatPacket("/nowar " + dialog.GetGuildName())
            dialog.Close()
            return 1
        world.accept, world.decline = accept, decline
        with world.game, w4.quiet():
            dialog.SAFE_SetAcceptEvent(accept)
            dialog.SAFE_SetCancelEvent(decline)
            dialog.Open(name, war_type, *limits)
        return world, dialog

    def run_both(self, flow, **kwargs):
        results = []
        for nui_on in (False, True):
            world, dialog = self.open(nui_on, **kwargs)
            mark = world.mark()
            with world.game, w4.quiet():
                flow(world, dialog)
            results.append((world.effects_since(mark, EFFECTS), world, dialog))
        return results

    def test_open_shows_the_name_and_the_declared_type(self):
        (a_world, a), (b_world, b) = [self.open(nui_on) for nui_on in (False, True)]
        model = w4.board(b).model
        self.assertEqual((model["name"], model["type"]), ("Black Wolves", 2))
        self.assertEqual(model["name"], a.inputValue.GetText())
        self.assertEqual([button.down for button in b.typeButtonList], [button.down for button in a.typeButtonList])
        self.assertTrue(w4.board(b).modal)

    def test_a_type_button_chooses_the_declared_type_again(self):
        def flow(world, dialog):
            if world.nui_on:
                w4.press(dialog, "type_press", 0, 0)
            else:
                dialog.typeButtonList[0].click()
            world.type = dialog.GetType()
        (legacy, a_world, _), (novaui, b_world, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual((a_world.type, b_world.type), (2, 2))
        self.assertEqual(w4.board(b).model["type"], 2)

    def test_ok_accepts_and_cancel_or_the_close_button_declines(self):
        for how, command in (("ok", "/war Black Wolves"), ("cancel", "/nowar Black Wolves"),
                             ("close", "/nowar Black Wolves")):
            def flow(world, dialog, how=how):
                if world.nui_on:
                    w4.press(dialog, {"ok": "accept_press", "cancel": "cancel_press", "close": "close_press"}[how], 0)
                else:
                    {"ok": dialog.acceptButton.click, "cancel": dialog.cancelButton.click,
                     "close": dialog.board.close}[how]()
            (legacy, _, _), (novaui, world, b) = self.run_both(flow)
            with self.subTest(how=how):
                self.assertEqual(novaui, legacy)
                self.assertEqual(novaui, [("net.SendChatPacket", (command,))])
                self.assertFalse(b.IsShow())
                self.assertNotIn(ACCEPT_DOCUMENT, world.documents())

    def test_it_keeps_no_key(self):
        world, dialog = self.open(True)
        nui = world.m("nui")
        board = w4.board(dialog)
        self.assertFalse(board.key("", nui.KEY_ESCAPE), "legacy's dialog handles no key")
        self.assertFalse(board.key("", nui.KEY_RETURN))
        self.assertTrue(dialog.IsShow())

    def test_open_shows_the_war_s_limits_the_server_sent(self):
        """NOVA-90 (uiguild.py AcceptGuildWarDialog.Open): the member cap's
        line (each guild brings half) and the end score's, each only when
        the server sent a value, as legacy's text lines."""
        for limits in ((32, 32), (20, 0), (0, 50), (), (0, 0)):
            (a_world, a), (b_world, b) = [self.open(nui_on, limits=limits) for nui_on in (False, True)]
            model = w4.board(b).model
            with self.subTest(limits=limits):
                for key, line in (("members", a.membersCountText), ("score", a.endScoreText)):
                    self.assertEqual((model[key], model[key + "_shown"]), (line.GetText(), bool(line.IsShow())), key)
                locale = b_world.m("localeInfo")
                members, score = (tuple(limits) + (0, 0))[:2]
                self.assertEqual(model["members"], locale.GUILD_WAR_MAX_MEMBERS % (members // 2) if members else "")
                self.assertEqual(model["score"], locale.GUILD_WAR_MAX_SCORE % score if score else "")

    def test_a_long_name_is_shown_whole(self):
        world, dialog = self.open(True, name="Black Wolves Of The North")
        self.assertEqual(w4.board(dialog).model["name"], "Black Wolves Of The North")


# --- the mark and symbol lists ------------------------------------------------------------------------------

def upload_folder(files, images):
    def setup(game):
        game.w4["files"]["upload"] = list(files)
        game.w4["images"].update(images)
    return setup


MARK_IMAGES = {"upload/wolf.tga": (1, 16, 12), "upload/dragon.tga": (1, 16, 12), "upload/lion.tga": (1, 16, 12),
               "upload/castle.png": (1, 32, 12), "upload/flag.bmp": (1, 16, 24), "upload/rose.png": (0, 0, 0),
               "upload/sword.jpg": (1, 64, 128), "upload/old_sign.jpeg": (1, 16, 12)}


class MarkListTest(unittest.TestCase):
    KIND = "mark"

    def make(self, world):
        if self.KIND == "mark":
            return world.make("guild-mark", "uiUploadMark", "MarkSelectDialog", "nui_guild_mark.MarkSelectDialog")
        return world.make("guild-mark", "uiUploadMark", "SymbolSelectDialog", "nui_guild_mark.SymbolSelectDialog")

    def open(self, nui_on, files=MARK_FILES, images=MARK_IMAGES, **kwargs):
        """The guild window's upload button: the list, its select event, Open."""
        world = world_of(nui_on, upload_folder(files, images), **kwargs)
        dialog = self.make(world)
        world.selected = []
        with world.game, w4.quiet():
            dialog.SAFE_SetSelectEvent(lambda name: world.selected.append(name))
            mark = world.mark()
            dialog.Open()
        world.open_mark = mark
        return world, dialog

    def listbox(self, dialog):
        return dialog.markListBox if self.KIND == "mark" else dialog.symbolListBox

    def select(self, world, dialog, index):
        if world.nui_on:
            w4.press(dialog, "row_press", index, 0)
        else:
            self.listbox(dialog).SelectIndex(index)

    def press(self, world, dialog, what):
        if world.nui_on:
            w4.press(dialog, what + "_press", 0)
        elif what == "close":
            dialog.board.close()
        else:
            getattr(dialog, what + "Button").click()

    def run_both(self, flow, **kwargs):
        results = []
        for nui_on in (False, True):
            world, dialog = self.open(nui_on, **kwargs)
            mark = world.mark()
            with world.game, w4.quiet():
                flow(world, dialog)
            results.append((world.effects_since(mark, EFFECTS), world, dialog))
        return results


class MarkList(MarkListTest):
    def test_the_rows_are_legacy_s_files_sorted_with_previews_for_16_by_12_marks(self):
        (a_world, a), (b_world, b) = [self.open(nui_on) for nui_on in (False, True)]
        model = w4.board(b).model
        names = [item.GetText() for item in a.markListBox.items]
        self.assertEqual([row["name"] for row in model["files"]], names)
        self.assertEqual(names, sorted(name for name in MARK_FILES if not name.endswith(".txt")))
        previews = dict((row["name"], row["preview"]) for row in model["files"])
        self.assertEqual(previews["wolf.tga"], "/upload/wolf.tga")
        self.assertEqual((previews["castle.png"], previews["flag.bmp"], previews["rose.png"]), ("", "", ""))
        self.assertEqual(previews["old_sign.jpeg"], "", "the client draws no .jpeg (spec 14)")
        self.assertEqual((model["kind"], model["selected"], model["selected_row"]), ("mark", -1, -1))
        self.assertEqual(model["title"], b_world.m("uiScriptLocale").MARKLIST_TITLE)

    def test_an_empty_folder_pops_legacy_s_message(self):
        (a_world, a), (b_world, b) = [self.open(nui_on, files=[]) for nui_on in (False, True)]
        locale = b_world.m("localeInfo")
        self.assertEqual(legacy_popup(a), locale.GUILDMARK_UPLOADER_ERROR_PATH)
        self.assertEqual(kit_popups(b_world, b_world.open_mark), [locale.GUILDMARK_UPLOADER_ERROR_PATH])
        self.assertEqual(w4.board(b).model["files"], [])
        self.assertTrue(b.IsShow())

    def test_ok_checks_the_file_then_selects_it(self):
        locale = support.locale_info("en")
        cases = ((None, locale.GUILDMARK_UPLOADER_ERROR_SELECT), ("rose.png", locale.GUILDMARK_UPLOADER_ERROR_FILE_FORMAT),
                 ("castle.png", locale.GUILDMARK_UPLOADER_ERROR_16_WIDTH),
                 ("flag.bmp", locale.GUILDMARK_UPLOADER_ERROR_12_HEIGHT), ("lion.tga", None))
        for name, message in cases:
            def flow(world, dialog, name=name):
                if name is not None:
                    names = [entry.GetText() for entry in self.listbox(dialog).entries] if world.nui_on else \
                        [item.GetText() for item in self.listbox(dialog).items]
                    self.select(world, dialog, names.index(name))
                mark = world.mark()
                self.press(world, dialog, "ok")
                world.popup = kit_popups(world, mark) if world.nui_on else legacy_popup(dialog)
            (legacy, a_world, a), (novaui, b_world, b) = self.run_both(flow)
            with self.subTest(name=name):
                self.assertEqual([c for c in novaui if not c[0].startswith("uiCommon.PopupDialog")], legacy)
                self.assertEqual(b_world.selected, a_world.selected)
                if message is None:
                    self.assertEqual(b_world.selected, ["lion.tga"])
                    self.assertFalse(b.IsShow())
                    self.assertNotIn(MARK_DOCUMENT, b_world.documents())
                else:
                    self.assertEqual(b_world.popup, [a_world.popup])
                    self.assertEqual(a_world.popup, message)
                    self.assertTrue(b.IsShow())

    def test_the_popup_s_ok_closes_it_and_leaves_the_list(self):
        world, dialog = self.open(True)
        with world.game, w4.quiet():
            self.press(world, dialog, "ok")
            popup = [d for d in world.game.dialogs if d._name == "uiCommon.PopupDialog" and d.is_open][-1]
            popup.accept()
        self.assertFalse(dialog.popupDialog.IsShow())
        self.assertTrue(dialog.IsShow())

    def test_refresh_reads_the_folder_again(self):
        def flow(world, dialog):
            world.game.w4["files"]["upload"].append("apple.tga")
            self.press(world, dialog, "refresh")
            world.names = [entry.GetText() for entry in self.listbox(dialog).entries] if world.nui_on else \
                [item.GetText() for item in self.listbox(dialog).items]
        (legacy, a_world, _), (novaui, b_world, b) = self.run_both(flow)
        self.assertEqual(novaui, legacy)
        self.assertEqual(b_world.names, a_world.names)
        self.assertEqual(b_world.names[0], "apple.tga")
        self.assertEqual(w4.board(b).model["files"][0]["name"], "apple.tga")

    def test_cancel_escape_and_the_close_button_hide_it(self):
        for how in ("cancel", "escape", "close"):
            def flow(world, dialog, how=how):
                self.select(world, dialog, 0)
                if how == "escape":
                    world.kept = dialog.OnPressEscapeKey()
                else:
                    self.press(world, dialog, how)
            (legacy, a_world, _), (novaui, world, b) = self.run_both(flow)
            with self.subTest(how=how):
                self.assertEqual(novaui, legacy)
                self.assertEqual((world.selected, a_world.selected), ([], []))
                self.assertFalse(b.IsShow())
                self.assertNotIn(MARK_DOCUMENT, world.documents())

    def test_image_sizes_are_read_only_for_the_rows_shown(self):
        files = ["mark%02d.tga" % i for i in range(30)]
        images = dict(("upload/" + name, (1, 16, 12)) for name in files)
        world, dialog = self.open(True, files=files, images=images)
        self.assertEqual(len(world.calls_since(0, "app.GetImageInfo")), 10, "legacy's ListBoxEx shows ten rows")
        board = w4.board(dialog)
        self.assertEqual([row["name"] for row in board.model["files"]], files[:10])
        with world.game, w4.quiet():
            for _ in range(5):
                w4.fire(dialog, "wheel", 1)
        self.assertEqual([row["index"] for row in board.model["files"]], list(range(5, 15)))
        self.assertEqual(len(world.calls_since(0, "app.GetImageInfo")), 15)
        with world.game, w4.quiet():
            w4.fire(dialog, "scroll", 1.0)
        self.assertEqual([row["index"] for row in board.model["files"]], list(range(20, 30)))
        self.assertAlmostEqual(board.model["scroll"], 1.0)
        with world.game, w4.quiet():
            w4.press(dialog, "row_press", 2, 0)
        self.assertEqual((board.model["selected"], board.model["selected_row"]), (22, 2))
        self.assertEqual(dialog.markListBox.GetSelectedItem().GetText(), "mark22.tga")

    def test_the_mark_and_the_symbol_list_show_at_once(self):
        world = world_of(True, upload_folder(MARK_FILES, MARK_IMAGES))
        mark = world.make("guild-mark", "uiUploadMark", "MarkSelectDialog", "nui_guild_mark.MarkSelectDialog")
        symbol = world.make("guild-mark", "uiUploadMark", "SymbolSelectDialog", "nui_guild_mark.SymbolSelectDialog")
        with world.game, w4.quiet():
            mark.Open()
            symbol.Open()
        self.assertTrue(mark.IsShow() and symbol.IsShow())
        self.assertNotEqual(w4.board(mark).MODEL, w4.board(symbol).MODEL, "instanced: one model each")
        self.assertEqual((w4.board(mark).model["kind"], w4.board(symbol).model["kind"]), ("mark", "symbol"))
        with world.game, w4.quiet():
            mark.Close()
        self.assertTrue(symbol.IsShow())
        self.assertEqual(w4.board(mark), None)


    def test_a_list_its_window_drops_takes_its_board_with_it(self):
        """Legacy's guild window (the guild flag off, guild-mark on) drops its
        lists at Destroy without destroying them; a dropped legacy list leaves
        the screen when it is collected (ui.Window.__del__). A shown NovaUI
        list's board went with it (review): nui_facade.Facade's finalizer."""
        import gc
        world, dialog = self.open(True)
        board = w4.board(dialog)
        self.assertTrue(board._doc)
        del dialog
        gc.collect()
        self.assertFalse(board._doc)
        self.assertNotIn("nui/windows/guild-mark/guild-mark.rml", world.documents())


class SymbolList(MarkListTest):
    KIND = "symbol"

    def test_only_jpg_files_without_previews(self):
        (a_world, a), (b_world, b) = [self.open(nui_on) for nui_on in (False, True)]
        model = w4.board(b).model
        self.assertEqual([row["name"] for row in model["files"]], [item.GetText() for item in a.symbolListBox.items])
        self.assertEqual([row["name"] for row in model["files"]], ["sword.jpg"])
        self.assertEqual([row["preview"] for row in model["files"]], [""])
        self.assertEqual((model["kind"], model["title"]), ("symbol", b_world.m("localeInfo").SYMBOLLIST_TITLE))

    def test_ok_checks_64_by_128(self):
        locale = support.locale_info("en")
        for size, message in (((1, 32, 128), locale.GUILDMARK_UPLOADER_ERROR_64_WIDTH),
                              ((1, 64, 64), locale.GUILDMARK_UPLOADER_ERROR_128_HEIGHT), ((1, 64, 128), None)):
            def flow(world, dialog):
                self.select(world, dialog, 0)
                mark = world.mark()
                self.press(world, dialog, "ok")
                world.popup = kit_popups(world, mark) if world.nui_on else legacy_popup(dialog)
            images = dict(MARK_IMAGES)
            images["upload/sword.jpg"] = size
            (legacy, a_world, _), (novaui, b_world, b) = self.run_both(flow, images=images)
            with self.subTest(size=size):
                self.assertEqual([c for c in novaui if not c[0].startswith("uiCommon.PopupDialog")], legacy)
                if message is None:
                    self.assertEqual((a_world.selected, b_world.selected), (["sword.jpg"], ["sword.jpg"]))
                    self.assertFalse(b.IsShow())
                else:
                    self.assertEqual((a_world.popup, b_world.popup), (message, [message]))


# --- the facades, make(), the fixtures, the wiring -----------------------------------------------------------

class Facades(unittest.TestCase):
    CLASSES = (("uiGuild", "DeclareGuildWarDialog", "nui_guild_war_declare"),
               ("uiGuild", "AcceptGuildWarDialog", "nui_guild_war_accept"),
               ("uiUploadMark", "MarkSelectDialog", "nui_guild_mark"),
               ("uiUploadMark", "SymbolSelectDialog", "nui_guild_mark"))
    WINDOW_IDS = {"DeclareGuildWarDialog": "guild-war-dialogs", "AcceptGuildWarDialog": "guild-war-dialogs",
                  "MarkSelectDialog": "guild-mark", "SymbolSelectDialog": "guild-mark"}

    def test_the_classes_the_methods_and_no_per_frame_python(self):
        world = world_of(True, upload_folder(MARK_FILES, MARK_IMAGES))
        for module, name, novaui in self.CLASSES:
            with self.subTest(cls=name):
                window = world.make(self.WINDOW_IDS[name], module, name, "%s.%s" % (novaui, name))
                legacy_class = getattr(world.m(module), name)
                self.assertIsInstance(window, legacy_class)
                self.assertEqual(type(window).__module__, novaui)
                self.assertTrue(window.NUI_FACADE)
                self.assertIsNone(type(window).OnUpdate)
                self.assertIsNone(type(window).OnRender)
                for method, member in inspect.getmembers(legacy_class, inspect.isfunction):
                    self.assertEqual(len(inspect.signature(getattr(type(window), method)).parameters),
                                     len(inspect.signature(member).parameters), method)
        for module_name in ("nui_guild_war_declare", "nui_guild_war_accept", "nui_guild_mark"):
            module = world.m(module_name)
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ == module_name:
                    for attr in ("OnUpdate", "OnRender"):
                        self.assertFalse(callable(getattr(cls, attr, None)), "%s.%s" % (name, attr))

    def test_make_builds_legacy_with_the_flag_off_or_an_older_exe(self):
        for nui_on, engine_4 in ((False, True), (True, False)):
            world = world_of(nui_on, upload_folder(MARK_FILES, MARK_IMAGES), engine_4=engine_4)
            for module, name, novaui in self.CLASSES:
                with self.subTest(cls=name, nui_on=nui_on, engine_4=engine_4):
                    window = world.make(self.WINDOW_IDS[name], module, name, "%s.%s" % (novaui, name))
                    self.assertIs(type(window), getattr(world.m(module), name))

    def test_the_documents_load_only_while_shown_the_declare_s_waiting_in_its_pool(self):
        world = world_of(True, upload_folder(MARK_FILES, MARK_IMAGES))
        declare = world.make("guild-war-dialogs", "uiGuild", "DeclareGuildWarDialog",
                             "nui_guild_war_declare.DeclareGuildWarDialog")
        mark = world.make("guild-mark", "uiUploadMark", "MarkSelectDialog", "nui_guild_mark.MarkSelectDialog")
        # P18: the declare dialog's probe board waits, hidden, for its open.
        self.assertEqual(world.documents().count(DECLARE_DOCUMENT), 1)
        self.assertIsNone(w4.board(declare))
        self.assertNotIn(MARK_DOCUMENT, world.documents())
        with world.game, w4.quiet():
            declare.Open()
            mark.Open()
        self.assertIn(DECLARE_DOCUMENT, world.documents())
        self.assertIn(MARK_DOCUMENT, world.documents())
        self.assertEqual(w4.board(mark).placement, ("center",), "centered at each open, as legacy")
        self.assertEqual((declare.GetWidth(), declare.GetHeight(), mark.GetWidth(), mark.GetHeight()), (0, 0, 0, 0))
        self.assertIn("float", declare.flags)
        self.assertIn("movable", mark.flags)

    def test_every_fixture_has_the_model_s_keys_and_kinds(self):
        world = world_of(True, upload_folder(MARK_FILES, MARK_IMAGES))
        for module, name, novaui in self.CLASSES:
            window = world.make(self.WINDOW_IDS[name], module, name, "%s.%s" % (novaui, name))
            document = {"DeclareGuildWarDialog": "guild-war-declare", "AcceptGuildWarDialog": "guild-war-accept",
                        "MarkSelectDialog": "guild-mark", "SymbolSelectDialog": "guild-mark"}[name]
            variants = {"guild-war-declare": ("", "foundation"), "guild-war-accept": ("", "foundation"),
                        "guild-mark": ("", "symbol", "empty")}[document]
            kinds = w4.model_kinds(window.nui_model())
            for variant in variants:
                with self.subTest(document=document, variant=variant):
                    self.assertEqual(w4.fixture_keys(window, document, variant), kinds)

    def test_no_repeated_element_binds_its_own_entry_in_a_shrinking_list(self):
        from nui_hud_test import repeated_element_reads
        markup = w4.read(os.path.join(w4.WINDOWS_DIR, "guild-mark", "guild-mark.rml"))
        reads = [found for found in repeated_element_reads(markup) if found[0].split(":")[-1].strip() != "files"]
        self.assertEqual(reads, [])

    def test_the_wiring_lines(self):
        game_text = w4.read(os.path.join(w4.ROOT, "game.py"))
        self.assertIn('questionDialog = nui_windows.make("guild-war-dialogs", uiGuild.AcceptGuildWarDialog, '
                      '"nui_guild_war_accept.AcceptGuildWarDialog")', game_text)
        guild_text = w4.read(os.path.join(w4.ROOT, "uiguild.py"))
        self.assertIn('inputDialog = nui_windows.make("guild-war-dialogs", DeclareGuildWarDialog, '
                      '"nui_guild_war_declare.DeclareGuildWarDialog")', guild_text)
        self.assertIn('self.symbolSelectDialog=nui_windows.make("guild-mark", uiUploadMark.SymbolSelectDialog, '
                      '"nui_guild_mark.SymbolSelectDialog")', guild_text)


if __name__ == "__main__":
    unittest.main()
