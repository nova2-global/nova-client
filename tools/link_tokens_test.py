"""Link tokens in the chat and whisper inputs (NOVA-42 round 3, option c, Eddy
2026-11-10): a link pasted into an input shows as its short text, such as
[Blazefury Blade Skin]; the input keeps a map from that token to the raw
|c...|H...|h[...]|h|r form and swaps each intact token back on send. A token
the player edited is plain text. The map is cleared when the input is sent or
cleared. In NovaUI's and legacy's chat and whisper windows alike."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import nui_chat_test as chat_test  # noqa: E402
import nui_w4_world as w4  # noqa: E402
import nui_whisper_test as whisper_test  # noqa: E402

ROOT = os.path.join(os.path.dirname(HERE), "assets", "root")
sys.path.insert(0, ROOT)

WIKI = "|cff00c0fc|Hsyswiki:item:40054|h[Blazefury Blade Skin]|h|r"
ITEM = "|cfff1e6c0|Hitem:4e21:0:0:0:0|h[Sword+0]|h|r"
ITEM_TWO = "|cfff1e6c0|Hitem:4e21:1:0:0:0|h[Sword+0]|h|r"
MOB = "|Hsyswiki:mob:101|h[Wolf]|h"


def module():
    import importlib
    return importlib.import_module("link_tokens")


class Tokens(unittest.TestCase):
    def test_a_links_token_is_its_visible_text(self):
        m = module()
        self.assertEqual(m.short_text(WIKI), "[Blazefury Blade Skin]")
        self.assertEqual(m.short_text(MOB), "[Wolf]")
        self.assertIsNone(m.short_text("plain"))
        self.assertIsNone(m.short_text("|Hitem:1|h|h"), "a link without text has no token")

    def test_an_intact_token_goes_out_raw(self):
        tokens = module().LinkTokens()
        self.assertEqual(tokens.add(WIKI), "[Blazefury Blade Skin]")
        self.assertEqual(tokens.expand("see [Blazefury Blade Skin] now"), "see %s now" % WIKI)

    def test_an_edited_token_goes_out_as_plain_text(self):
        tokens = module().LinkTokens()
        tokens.add(WIKI)
        for text in ("[Blazefury Blade Skn]", "[Blazefury Blade Skin", "Blazefury Blade Skin]"):
            with self.subTest(text=text):
                self.assertEqual(tokens.expand(text), text)

    def test_several_links_in_one_message(self):
        tokens = module().LinkTokens()
        for raw in (WIKI, ITEM, MOB):
            tokens.add(raw)
        self.assertEqual(tokens.expand("[Wolf] drops [Sword+0], see [Blazefury Blade Skin]"),
                         "%s drops %s, see %s" % (MOB, ITEM, WIKI))

    def test_links_with_the_same_name_go_out_in_order(self):
        tokens = module().LinkTokens()
        tokens.add(ITEM)
        tokens.add(ITEM_TWO)
        self.assertEqual(tokens.expand("[Sword+0] or [Sword+0] or [Sword+0]"),
                         "%s or %s or [Sword+0]" % (ITEM, ITEM_TWO), "a third, typed by hand, is plain")

    def test_cleared_tokens_expand_nothing(self):
        tokens = module().LinkTokens()
        tokens.add(WIKI)
        tokens.clear()
        self.assertEqual(tokens.expand("[Blazefury Blade Skin]"), "[Blazefury Blade Skin]")

    def test_a_paste_with_no_registered_input_focused_pastes_the_raw_link(self):
        m = module()
        pasted = []

        class Input(object):
            def __init__(self, focused):
                self.focused = focused
                self.tokens = m.LinkTokens()

            def link_focused(self):
                return self.focused

            def link_tokens(self):
                return self.tokens

        idle, typing = Input(False), Input(True)
        saved = list(m._inputs)
        m._inputs[:] = []
        m.register(idle)
        m.register(typing)
        try:
            m.paste(WIKI, paste=pasted.append)
            self.assertEqual(pasted, ["[Blazefury Blade Skin]"])
            self.assertEqual(typing.tokens.expand("[Blazefury Blade Skin]"), WIKI)
            self.assertEqual(idle.tokens.expand("[Blazefury Blade Skin]"), "[Blazefury Blade Skin]")
            typing.focused = False
            m.paste(WIKI, paste=pasted.append)
            self.assertEqual(pasted[-1], WIKI, "another field (a search box) takes the raw link, as before")
        finally:
            m._inputs[:] = saved


class Chat(unittest.TestCase):
    """The chat input, in a legacy and a NovaUI world."""

    def opened(self):
        worlds = chat_test.pair()
        for world in worlds:
            world.enter_game()
            with world:
                world.interface.ToggleChat()
        return worlds

    def sent(self, world):
        return [args for _, args in world.game.calls("net.SendChatPacket")]

    def paste(self, world, raw):
        with world, chat_test.quiet():
            world.chat.PasteLink(raw)

    def test_a_pasted_link_shows_its_token_and_goes_out_raw(self):
        for world in self.opened():
            with self.subTest(novaui=world.nui_on):
                world.type("see ")
                self.paste(world, WIKI)
                world.type(" now")
                self.assertEqual(world.text(), "see [Blazefury Blade Skin] now")
                world.enter()
                self.assertEqual(self.sent(world), [("see %s now" % WIKI, 0)])

    def test_an_edited_token_is_sent_as_plain_text(self):
        for world in self.opened():
            with self.subTest(novaui=world.nui_on):
                self.paste(world, WIKI)
                with world, chat_test.quiet():
                    if world.nui_on:
                        world.board().set_value(world.field(), "[Blazefury Blade Skn]")
                    else:
                        world.line().SetText("[Blazefury Blade Skn]")
                world.enter()
                self.assertEqual(self.sent(world), [("[Blazefury Blade Skn]", 0)])

    def test_several_links_in_one_message(self):
        for world in self.opened():
            with self.subTest(novaui=world.nui_on):
                self.paste(world, MOB)
                world.type(" drops ")
                self.paste(world, ITEM)
                world.enter()
                self.assertEqual(self.sent(world), [("%s drops %s" % (MOB, ITEM), 0)])

    def test_the_map_goes_with_the_sent_message(self):
        for world in self.opened():
            with self.subTest(novaui=world.nui_on):
                self.paste(world, WIKI)
                world.enter()
                world.type("[Blazefury Blade Skin]")
                world.enter()
                self.assertEqual(self.sent(world), [(WIKI, 0), ("[Blazefury Blade Skin]", 0)])

    def test_escape_clears_the_map(self):
        for world in self.opened():
            with self.subTest(novaui=world.nui_on):
                self.paste(world, WIKI)
                world.key("escape")
                with world:
                    world.interface.ToggleChat()
                world.type("[Blazefury Blade Skin]")
                world.enter()
                self.assertEqual(self.sent(world), [("[Blazefury Blade Skin]", 0)])

    def test_a_prefixed_message_goes_out_raw(self):
        for world in self.opened():
            with self.subTest(novaui=world.nui_on):
                world.type("#")
                self.paste(world, WIKI)
                world.enter()
                self.assertEqual(self.sent(world), [(WIKI, 3)])

    def test_alt_and_a_press_on_a_chat_link_pastes_its_token(self):
        for world in self.opened():
            with self.subTest(novaui=world.nui_on):
                world.link(chat_test.ITEM, alt=True)
                self.assertEqual(world.text(), module().short_text(chat_test.TAGGED_ITEM))
                world.enter()
                self.assertEqual(self.sent(world), [(chat_test.TAGGED_ITEM, 0)])


class Whisper(whisper_test.WhisperTest):
    """A whisper dialog's input, in a legacy and a NovaUI world."""

    def worlds(self):
        worlds = whisper_test.WhisperTest.worlds(self)
        for world in worlds:
            # The paste bridge reaches the dialog's field (a textarea), as the
            # client's InsertFieldText does.
            world.game.state.text_fields.add((whisper_test.DOCUMENT, whisper_test.INPUT))
        return worlds

    def test_a_pasted_link_goes_out_raw_and_shows_raw_in_the_log(self):
        for world in self.worlds():
            with self.subTest(novaui=world.nui_on):
                mark = world.mark()
                with world.game, w4.quiet():
                    dialog = world.interface.OpenWhisperDialog("Alice")
                    dialog.PasteLink(WIKI)
                    shown = (w4.board(dialog).fields.get(whisper_test.INPUT, "") if world.nui_on
                             else dialog.chatLine.GetText())
                    self.type_and(world, dialog, " hi", "enter")
                self.assertEqual(shown, "[Blazefury Blade Skin]")
                calls = [c for c in world.effects_since(mark, ("net", "chat"))
                         if c[0] in ("net.SendWhisperPacket", "chat.AppendWhisper")]
                self.assertIn(("net.SendWhisperPacket", ("Alice", WIKI + " hi")), calls)
                self.assertIn(("chat.AppendWhisper", (0, "Alice", "Tester : " + WIKI + " hi")), calls)

    def test_an_edited_token_is_sent_as_plain_text(self):
        for world in self.worlds():
            with self.subTest(novaui=world.nui_on):
                mark = world.mark()
                with world.game, w4.quiet():
                    dialog = world.interface.OpenWhisperDialog("Alice")
                    dialog.PasteLink(WIKI)
                    if world.nui_on:
                        w4.board(dialog).set_value(whisper_test.INPUT, "[Blazefury Blade Skn]")
                    else:
                        dialog.chatLine.SetText("[Blazefury Blade Skn]")
                    self.type_and(world, dialog, "", "enter")
                    self.type_and(world, dialog, "[Blazefury Blade Skin]", "enter")
                calls = [c for c in world.effects_since(mark, ("net",)) if c[0] == "net.SendWhisperPacket"]
                self.assertEqual(calls, [("net.SendWhisperPacket", ("Alice", "[Blazefury Blade Skn]")),
                                         ("net.SendWhisperPacket", ("Alice", "[Blazefury Blade Skin]"))],
                                 "the map went with the first message")


if __name__ == "__main__":
    unittest.main()
