"""Tests for the legacy client's costume switches (wave 6, chunk Y; NOVA-22,
OLD's __HIDE_COSTUME): python3 -B -m unittest hide_costume_test (from tools/).

The C++ half (GC::SHOW_COSTUMES into CPythonPlayer, player.IsShowCostumes,
IsShowHair, IsShowWeapon, IsShowSash, GetAuraWingFlags) is chunk C's; the
server's is chunk SA's. Here uiinventory.CostumeWindow and its uiscript run
over nui_game_support's stand-ins with C's names (wave6_support):
- the switches of OLD's costume window (OLD uiInventory.py:56-366): one
  toggle button per part, down while the part shows, whose press sends
  "/set_is_show_costumes|hair|weapon|sash 0|1" for the other state, as OLD;
  the sash's (OLD's inventory panel had it) is in the costume window;
- Show and the server's ResetCostumeSlider command (a refusal while
  fighting, OLD game.py:3028, 3331) set the buttons from the player's state;
- a costume window whose loader binds no switch (NovaUI's subclass) shows;
- the switch labels in all 17 locales."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import legacy_foundation_test as lf  # noqa: E402
import wave6_support as w6  # noqa: E402

# OLD's names (uiscript/costumewindow.py) and their commands, by player getter.
SWITCHES = (("Activate_ON_OFF", "IsShowCostumes", "set_is_show_costumes"),
            ("Activate1_ON_OFF", "IsShowHair", "set_is_show_hair"),
            ("Activate2_ON_OFF", "IsShowWeapon", "set_is_show_weapon"),
            ("Activate5_ON_OFF", "IsShowSash", "set_is_show_sash"))
LABELS = {"COSTUME_SHOW_BODY": "Costume", "COSTUME_SHOW_HAIR": "Hair", "COSTUME_SHOW_WEAPON": "Weapon",
          "COSTUME_SHOW_SASH": "Sash", "COSTUME_SHOW_AURA": "Aura"}


class Switches(unittest.TestCase):
    def setUp(self):
        self.world = w6.World()
        self.inventory, self.window = w6.costume_window(self.world)

    def press(self, name):
        with self.world.game, lf.quiet():
            self.window.GetChild(name).click()

    def test_the_uiscript_has_olds_switches_as_toggle_buttons(self):
        with self.world.game:
            window = lf.read_uiscript(os.path.join(w6.UISCRIPT, "costumewindow.py"))["window"]
        board = lf.child(window, "board")
        for name, _, _ in SWITCHES + (("Activate3_ON_OFF", None, None),):
            self.assertEqual(lf.child(board, name)["type"], "toggle_button", name)

    def test_each_switch_is_down_while_its_part_shows(self):
        shown = self.world.game.shown_costumes
        for name, getter, _ in SWITCHES:
            for state in (0, 1):
                with self.subTest(switch=name, shown=state):
                    shown[getter] = state
                    with self.world.game, lf.quiet():
                        self.window.Show()
                    self.assertEqual(self.window.GetChild(name).down, bool(state))

    def test_a_press_asks_the_server_for_the_other_state(self):
        shown = self.world.game.shown_costumes
        for name, getter, command in SWITCHES:
            for state in (1, 0):
                with self.subTest(switch=name, shown=state):
                    shown[getter] = state
                    del self.world.game.log[:]
                    self.press(name)
                    self.assertEqual(self.world.chat_commands(), ["/%s %d" % (command, 1 - state)])
                    self.assertEqual(self.window.GetChild(name).down, not state, "the button shows the new state")

    def test_the_server_state_wins_over_a_press_it_refused(self):
        """OLD's ResetCostumeSlider: the server refuses a switch while
        fighting and the buttons show its state again."""
        shown = self.world.game.shown_costumes
        self.press("Activate_ON_OFF")
        self.assertFalse(self.window.GetChild("Activate_ON_OFF").down)
        game = game_window(self.inventory)
        with self.world.game, lf.quiet():
            game._GameWindow__ResetCostumeSlider()
        self.assertTrue(self.window.GetChild("Activate_ON_OFF").down)
        shown["IsShowHair"] = 0
        with self.world.game, lf.quiet():
            game._GameWindow__ResetCostumeSlider()
        self.assertFalse(self.window.GetChild("Activate1_ON_OFF").down)

    def test_the_server_command_is_registered(self):
        source = lf.read(os.path.join(w6.ROOT, "game.py"))
        self.assertIn('"ResetCostumeSlider"\t: self.__ResetCostumeSlider,', source)

    def test_a_window_without_switches_shows(self):
        """NovaUI's subclass binds its own widgets: the switch lists stay empty."""
        module = self.world.game.loaded["uiInventory"]

        class Bare(module.CostumeWindow):
            def _CostumeWindow__LoadWindow(self):
                self.isLoaded = 1
                self.wndEquip = w6.support.LegacySlotWindow(None)

        with self.world.game, lf.quiet():
            window = Bare(self.inventory)
            window.Show()
            window.ResetSlider()
            window.Close()
        self.assertEqual(list(window.costumeButtonList), [])


def game_window(inventory):
    """game.GameWindow's ResetCostumeSlider over an Interface with the inventory."""
    import types
    source = w6.support.source_of("game.py", ["__ResetCostumeSlider"], inside="GameWindow")
    body = "\n".join("\t" + line if line else line for line in source.split("\n"))
    namespace = {}
    exec(compile("class GameWindow(object):\n%s\n" % body, "game.py", "exec"), namespace)
    window = namespace["GameWindow"]()
    window.interface = types.SimpleNamespace(wndInventory=inventory)
    return window


class NoCostumeWindow(unittest.TestCase):
    def test_the_command_before_the_window_is_made_does_nothing(self):
        import types
        game = game_window(types.SimpleNamespace(wndCostume=None))
        game._GameWindow__ResetCostumeSlider()
        game.interface = None
        game._GameWindow__ResetCostumeSlider()


class Locales(unittest.TestCase):
    def test_every_locale_has_the_switch_labels(self):
        w6.check_keys(self, LABELS, "locale_interface.txt")


if __name__ == "__main__":
    unittest.main()
