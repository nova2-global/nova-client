"""Tests for assets/root/nui_form_proxies.py, the widget proxies of the Wave 4
windows (P16 spec 4.2): python3 -B -m unittest nui_form_proxies_test (from
tools/). Plain CPython over nui_game_support's stand-ins.

Each proxy is checked against the legacy code that will drive it: an ast
pass over the legacy modules finds every method the legacy code calls on the
widget a proxy stands for (by the attribute or local name legacy keeps it
under, and the guild window's slot lists by their index), outside the
functions the NovaUI subclasses replace (their loaders), and the proxy must
have each one. RadioGroupProxy.OnClick runs against ui.RadioButtonGroup's own
OnClick, taken from assets/root/ui.py, on stand-in buttons."""
import ast
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nui_game_support as support  # noqa: E402

ROOT = support.ROOT

# The functions a NovaUI subclass replaces, by module and (class, function):
# their calls go to the proxies the replacement makes, not to legacy's.
REPLACED = {
    "uiexchange.py": {("ExchangeDialog", "LoadDialog")},
    "uishop.py": {("ShopDialog", "LoadDialog"), ("ShopDialog", "Refresh")},
    "uisafebox.py": {("PasswordDialog", "__LoadDialog"), ("ChangePasswordDialog", "__LoadDialog"),
                     ("ChangePasswordDialog", "LoadDialog"), ("SafeboxWindow", "__LoadWindow"),
                     ("SafeboxWindow", "__MakePageButton"), ("SafeboxWindow", "SetTableSize"),
                     ("MallWindow", "__LoadWindow"), ("MallWindow", "SetTableSize")},
    "uiprivateshopbuilder.py": {("PrivateShopBuilder", "__LoadWindow")},
    "uiequipmentdialog.py": {("EquipmentDialog", "__LoadDialog")},
    "uiguild.py": {("GuildWindow", "__LoadWindow"), ("GuildWindow", "__MakeInfoPage"), ("GuildWindow", "__MakeBoardPage"),
                   ("GuildWindow", "__MakeMemberPage"), ("GuildWindow", "__MakeBaseInfoPage"),
                   ("GuildWindow", "__MakeSkillPage"), ("GuildWindow", "__MakeGradePage"),
                   ("DeclareGuildWarDialog", "__CreateDialog"), ("AcceptGuildWarDialog", "__CreateDialog"),
                   ("CheckBox", "__init__"), ("EditableTextSlot", "__init__"), ("CommentSlot", "__init__")},
    "uimessenger.py": {("MessengerWindow", "__LoadWindow"), ("MessengerWindow", "__AddGroup"),
                       ("MessengerWindow", "__AddFamilyGroup")},
    "uiwhisper.py": {("WhisperDialog", "LoadDialog")},
    "uiuploadmark.py": {("MarkSelectDialog", "__Load"), ("MarkSelectDialog", "__CreateMarkListBox"),
                        ("SymbolSelectDialog", "__Load"), ("SymbolSelectDialog", "__CreateSymbolListBox")},
}

# Where each proxy's widget lives in legacy: ("attr", name) an attribute
# access .name, ("name", name) a local variable, ("item", dict, key) an entry
# of a guild page's slot list (page.<dict>[...][key], key an int or the
# GuildWindow constant's name), per module.
USERS = {
    "TypedSlotWindowProxy": {"uiexchange.py": [("attr", "OwnerSlot"), ("attr", "TargetSlot")],
                             "uishop.py": [("attr", "itemSlotWindow")],
                             "uisafebox.py": [("attr", "wndItem")]},
    "FieldProxy": {"uisafebox.py": [("attr", "passwordValue"), ("attr", "oldPassword"), ("attr", "newPassword"),
                                    ("attr", "newPasswordCheck")],
                   "uiguild.py": [("attr", "commentSlot"), ("attr", "gradeNameSlot"), ("attr", "inputValue")],
                   "uiwhisper.py": [("attr", "chatLine"), ("attr", "titleNameEdit")]},
    "ToggleProxy": {"uiexchange.py": [("attr", "AcceptButton")], "uishop.py": [("attr", "btnBuy"), ("attr", "btnSell")],
                    "uiwhisper.py": [("attr", "ignoreButton")]},
    "RadioGroupProxy": {"uishop.py": [("attr", "smallRadioButtonGroup"), ("attr", "middleRadioButtonGroup")]},
    "ScrollProxy": {"uiguild.py": [("attr", "scrollBar")], "uimessenger.py": [("attr", "scrollBar")],
                    "uiwhisper.py": [("attr", "scrollBar")]},
    "ComboProxy": {"uiguild.py": [("name", "gradeComboBox"), ("item", "memberDict", 1)]},
    "CheckProxy": {"uiguild.py": [("item", "memberDict", 5), ("item", "gradeDict", "GRADE_ADD_MEMBER_AUTHORITY"),
                                  ("item", "gradeDict", "GRADE_REMOVE_MEMBER_AUTHORITY"),
                                  ("item", "gradeDict", "GRADE_NOTICE_AUTHORITY"),
                                  ("item", "gradeDict", "GRADE_SKILL_AUTHORITY")]},
    "EditableSlotProxy": {"uiguild.py": [("item", "gradeDict", "GRADE_SLOT_NAME"), ("item", "gradeDict", 0)]},
    "CommentProxy": {"uiguild.py": [("item", "boardDict", 2)]},
    "GaugeProxy": {"uiguild.py": [("attr", "gpGauge")]},
    "MarkProxy": {"uiguild.py": [("attr", "largeMarkBox")]},
    "MessageWindowProxy": {"uisafebox.py": [("attr", "dlgMessage")], "uiguild.py": [("attr", "popupDialog")],
                           "uiuploadmark.py": [("attr", "popupDialog")]},
    "ListBoxExProxy": {"uiuploadmark.py": [("attr", "markListBox"), ("attr", "symbolListBox")]},
    "ResizeProxy": {"uimessenger.py": [("attr", "resizeButton")], "uiwhisper.py": [("attr", "resizeButton")]},
    "GuildSkillSlotProxy": {"uiguild.py": [("attr", "activeSlot"), ("attr", "passiveSlot"), ("attr", "affectSlot")]},
}

# The methods spec 4.2 names for each class (exact).
SPEC = {
    "TypedSlotWindowProxy": ("SetItemSlot", "RefreshSlot", "SetSelectEmptySlotEvent", "SetOverInItemEvent"),
    "GuildSkillSlotProxy": ("SetSkillSlot", "AppendSlotButton", "ShowSlotButton", "HideAllSlotButton", "plus"),
    "FieldProxy": ("SetText", "GetText", "SetFocus", "KillFocus", "IsFocus", "SetMax", "SetLimitWidth", "SetSize",
                   "SetPosition", "Show", "Hide", "SetSecretMode", "SetSecret", "SetNumberMode", "SetMultiLine",
                   "SetReturnEvent", "SetEscapeEvent", "SetTabEvent", "OnIMEReturn", "OnPressEscapeKey", "OnKeyDown",
                   "fire_return", "fire_escape", "fire_tab", "fire_key", "typed"),
    "ToggleProxy": ("SetToggleUpEvent", "SetToggleDownEvent", "SetEvent", "Enable", "Disable", "Down", "SetUp", "press"),
    "RadioGroupProxy": ("Show", "Hide", "SetText", "OnClick", "Create"),
    "ScrollProxy": ("SetScrollEvent", "SetPos", "GetPos", "SetScrollBarSize", "SetMiddleBarSize", "SetPosition", "Show",
                    "Hide", "Destroy", "moved"),
    "ComboProxy": ("SetParent", "SetPosition", "SetSize", "Show", "SetEvent", "ClearItem", "InsertItem",
                   "SetCurrentItem", "SelectItem", "Enable", "Disable", "CloseListBox", "Destroy", "pressed", "picked"),
    "CheckProxy": ("SetCheck", "Disable", "Show", "pressed"),
    "EditableSlotProxy": ("SetText", "SetEvent", "Disable", "pressed"),
    "CommentProxy": ("SetText",),
    "GaugeProxy": ("SetPercentage",),
    "MarkProxy": ("SetIndex", "SetScale", "AddFlag", "SetPosition", "GetWidth", "Show", "Hide"),
    "MessageWindowProxy": ("GetChild", "Show", "Hide", "SetTop", "SetCenterPosition", "IsShow", "ClearDictionary", "Open"),
    "PageWindowProxy": ("Show", "Hide", "IsShow", "UpdateRect", "GetScriptFileName", "ClearDictionary"),
    "ResizeProxy": ("SetParent", "AddFlag", "SetSize", "SetWindowVerticalAlignBottom", "SetPosition", "GetLocalPosition",
                    "GetHeight", "SetMoveEvent", "TurnOffCallBack", "TurnOnCallBack", "Show", "dragged"),
    "ListBoxExProxy": ("SetParent", "SetPosition", "Show", "SetScrollBar", "AppendItem", "RemoveAllItems", "IsEmpty",
                       "GetSelectedItem", "SelectIndex"),
}


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _key(node):
    """A subscript's key: an int constant, or the attribute's name
    (self.GRADE_SLOT_NAME)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _dict_of(node):
    """The slot list dictionary an expression reads an entry of
    (page.memberDict[x] -> "memberDict"), or None."""
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute):
        return node.value.attr
    return None


def _aliases(function):
    """Within one function: the local names that hold a slot list of a
    dictionary (slotList = page.boardDict[i]; for key, slotList in
    list(page.memberDict.items())), name -> dict."""
    found = {}
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            source = _dict_of(node.value)
            if source:
                found[node.targets[0].id] = source
        elif isinstance(node, ast.For) and isinstance(node.target, ast.Tuple) and len(node.target.elts) == 2:
            iterator = node.iter
            if isinstance(iterator, ast.Call) and isinstance(iterator.func, ast.Name) and iterator.func.id == "list":
                iterator = iterator.args[0] if iterator.args else None
            if (isinstance(iterator, ast.Call) and isinstance(iterator.func, ast.Attribute)
                    and iterator.func.attr == "items" and isinstance(iterator.func.value, ast.Attribute)
                    and isinstance(node.target.elts[1], ast.Name)):
                found[node.target.elts[1].id] = iterator.func.value.attr
    return found


def legacy_calls(module_file, users):
    """{method name} legacy calls on the widgets `users` names in that module,
    outside the functions REPLACED lists."""
    tree = ast.parse(read(os.path.join(ROOT, module_file)))
    replaced = REPLACED.get(module_file, set())
    wanted_attr = set(name for kind, *rest in users if kind == "attr" for name in rest[:1])
    wanted_name = set(name for kind, *rest in users if kind == "name" for name in rest[:1])
    wanted_item = set((rest[0], rest[1]) for kind, *rest in users if kind == "item")
    found = set()
    for cls in [node for node in tree.body if isinstance(node, ast.ClassDef)]:
        for function in [node for node in cls.body if isinstance(node, ast.FunctionDef)]:
            if (cls.name, function.name) in replaced:
                continue
            aliases = _aliases(function)
            for node in ast.walk(function):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                    continue
                receiver = node.func.value
                if isinstance(receiver, ast.Attribute) and receiver.attr in wanted_attr:
                    found.add(node.func.attr)
                elif isinstance(receiver, ast.Name) and receiver.id in wanted_name:
                    found.add(node.func.attr)
                elif isinstance(receiver, ast.Subscript):
                    source = _dict_of(receiver.value) or (aliases.get(receiver.value.id)
                                                          if isinstance(receiver.value, ast.Name) else None)
                    if source and (source, _key(receiver.slice)) in wanted_item:
                        found.add(node.func.attr)
    return found


class FormProxiesTest(unittest.TestCase):
    def setUp(self):
        self.game = support.Game()
        support.install_wave2b_ui(self.game)
        support.install_wave3a_ui(self.game)
        support.install_wave3b_ui(self.game)
        self.game.load_standard()
        self.game.load("nui_proxies", "nui_proxies.py")
        self.game.load("nui_slots", "nui_slots.py")
        self.m = self.game.load("nui_form_proxies", "nui_form_proxies.py")
        self.game.__enter__()
        self.addCleanup(self.game.__exit__)


class AgainstLegacy(FormProxiesTest):
    def test_each_class_has_the_methods_the_spec_names(self):
        for name, methods in SPEC.items():
            cls = getattr(self.m, name)
            for method in methods:
                self.assertTrue(callable(getattr(cls, method, None)), "%s.%s" % (name, method))

    def test_each_class_has_every_method_its_legacy_users_call(self):
        for name, modules in USERS.items():
            cls = getattr(self.m, name)
            seen = set()
            for module_file, users in modules.items():
                calls = legacy_calls(module_file, users)
                seen |= calls
                with self.subTest(proxy=name, module=module_file):
                    missing = sorted(call for call in calls if not callable(getattr(cls, call, None)))
                    self.assertEqual(missing, [])
            self.assertTrue(seen, "the ast pass found no call for %s" % name)

    def test_the_slot_list_aliases_are_found(self):
        """The guild window's refreshes reach their slot lists through
        aliases; the pass must see them, or the checks above prove nothing."""
        self.assertIn("SetCheck", legacy_calls("uiguild.py", [("item", "memberDict", 5)]))
        self.assertIn("SetCurrentItem", legacy_calls("uiguild.py", [("name", "gradeComboBox")]))
        self.assertIn("SetText", legacy_calls("uiguild.py", [("item", "boardDict", 2)]))
        self.assertIn("SetCheck", legacy_calls("uiguild.py", [("item", "gradeDict", "GRADE_NOTICE_AUTHORITY")]))

    def test_an_unknown_call_raises(self):
        field = self.m.FieldProxy("x")
        with self.assertRaises(AttributeError):
            field.SetCandidateWindow(1)
        with self.assertRaises(AttributeError):
            self.m.TypedSlotWindowProxy(range(4), None, slot_type=8).GetWindowHandle()


def legacy_radio_group():
    """ui.RadioButtonGroup as assets/root/ui.py defines it, alone."""
    tree = ast.parse(read(os.path.join(ROOT, "ui.py")))
    node = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "RadioButtonGroup"][0]
    module = ast.Module(body=[node], type_ignores=[])
    namespace = {}
    exec(compile(module, "ui.py", "exec"), namespace)
    return namespace["RadioButtonGroup"]


class RadioButton(object):
    """A stand-in button that logs SetUp, Down and its event's calls."""

    def __init__(self, log, name):
        self.log = log
        self.name = name
        self.event = None
        self.down = False
        self.enabled = True

    def SetEvent(self, event):
        self.event = event

    def SetUp(self):
        self.down = False
        self.log.append(("up", self.name))

    def Down(self):
        self.down = True
        self.log.append(("down", self.name))

    def Show(self):
        self.log.append(("show", self.name))

    def Hide(self):
        self.log.append(("hide", self.name))

    def SetText(self, text):
        self.log.append(("text", self.name, text))

    def click(self):
        if self.event:
            self.event()


class Radio(FormProxiesTest):
    def run_group(self, make, clicks):
        log = []
        buttons = [RadioButton(log, i) for i in range(3)]
        raw = [[button, (lambda i=i: log.append(("select", i))), (lambda i=i: log.append(("unselect", i)))]
               for i, button in enumerate(buttons)]
        group = make(raw)
        for index in clicks:
            group.OnClick(index)
        group.SetText(1, "Tab")
        group.Hide()
        group.Show()
        return log

    def test_on_click_and_create_equal_legacy_s(self):
        legacy = legacy_radio_group()
        for clicks in ([], [1], [1, 1, 2, 0], [2, 0]):
            with self.subTest(clicks=clicks):
                self.assertEqual(self.run_group(self.m.RadioGroupProxy.Create, clicks),
                                 self.run_group(legacy.Create, clicks))

    def test_the_first_click_raises_the_last_button(self):
        log = []
        buttons = [RadioButton(log, i) for i in range(2)]
        group = self.m.RadioGroupProxy([(button, None, None) for button in buttons])
        self.assertEqual(group.selected(), -1)
        del log[:]
        group.OnClick(1)
        self.assertEqual(log, [("up", 1), ("down", 1)], "selectedBtnIdx -1 is the last button")

    def test_press_ignores_the_button_that_is_down(self):
        changes = []
        buttons = [self.game.loaded["nui_proxies"].ButtonProxy() for _ in range(3)]
        group = self.m.RadioGroupProxy.Create([[button, None, None] for button in buttons], on_change=changes.append)
        self.assertEqual(group.selected(), 0)
        group.press(0)
        self.assertEqual(group.selected(), 0)
        group.press(2)
        self.assertEqual(group.selected(), 2)
        self.assertEqual([button.down for button in group.buttons()], [False, False, True])
        buttons[1].Disable()
        group.press(1)
        self.assertEqual(group.selected(), 2, "a disabled button takes no press")
        self.assertTrue(changes)


class Toggle(FormProxiesTest):
    def test_a_press_toggles_and_runs_the_event_after_the_state(self):
        log = []
        toggle = self.m.ToggleProxy()
        toggle.SetToggleDownEvent(lambda: log.append(("down", toggle.down)))
        toggle.SetToggleUpEvent(lambda: log.append(("up", toggle.down)))
        toggle.press()
        toggle.press()
        self.assertEqual(log, [("down", True), ("up", False)])
        toggle.Disable()
        toggle.press()
        self.assertEqual(len(log), 2, "a disabled toggle takes no press")
        toggle.Enable()
        toggle.Down()
        toggle.SetUp()
        self.assertEqual(len(log), 2, "Down and SetUp run no event, as CButton's")


class Field(FormProxiesTest):
    def test_events_attributes_and_the_live_reader(self):
        changes = []
        field = self.m.FieldProxy("safebox-password-field", lambda proxy, what: changes.append(what))
        log = []
        field.SetReturnEvent(lambda: log.append("return"))
        field.SetEscapeEvent(lambda: log.append("escape"))
        self.assertTrue(field.fire_return())
        self.assertTrue(field.fire_escape())
        self.assertFalse(field.fire_tab(), "no tab event: the IME goes on")
        field.SetTabEvent(lambda: log.append("tab"))
        self.assertTrue(field.fire_tab())
        field.OnIMEReturn = lambda: log.append("assigned") or True
        field.fire_return()
        self.assertEqual(log, ["return", "escape", "tab", "assigned"])
        field.SetText("abc")
        field.SetFocus()
        field.KillFocus()
        field.SetMax(6)
        field.SetSecretMode(1)
        self.assertEqual(changes, ["text", "focus", "kill_focus", "max", "secret"])
        field.typed("000000")
        self.assertEqual(field.GetText(), "000000")
        field.reader = lambda: "123456"
        self.assertEqual(field.GetText(), "123456", "the document's text wins")
        field.reader = lambda: None
        self.assertEqual(field.GetText(), "123456", "no document: the last text")
        self.assertTrue(field.fire_key(0x3F))


class Combo(FormProxiesTest):
    def test_pressed_opens_and_closes_picked_runs_the_event_and_disable_clears(self):
        picked = []
        combo = self.m.ComboProxy(3)
        combo.SetEvent(picked.append)
        combo.pressed()
        self.assertFalse(combo.open, "no items: the list does not open")
        combo.InsertItem(2, "Leader")
        combo.InsertItem(3, "Member")
        combo.SetCurrentItem("Member")
        combo.pressed()
        self.assertTrue(combo.open)
        combo.picked(2)
        self.assertEqual(picked, [2])
        self.assertFalse(combo.open)
        combo.pressed()
        combo.Disable()
        self.assertEqual((combo.text, combo.open, combo.enabled), ("", False, False))
        combo.pressed()
        self.assertFalse(combo.open)


class Guild(FormProxiesTest):
    def test_check_editable_slot_comment_gauge(self):
        log = []
        check = self.m.CheckProxy(lambda: log.append("check"))
        check.pressed()
        check.Disable()
        check.pressed()
        slot = self.m.EditableSlotProxy()
        slot.SetEvent(lambda arg: log.append(("slot", arg)), 7)
        slot.pressed()
        slot.Disable()
        slot.pressed()
        self.assertEqual(log, ["check", ("slot", 7)])
        grp_text = types.ModuleType("grpText")
        grp_text.GetSplitingTextLine = lambda text, limit, start: text[start:start + limit]
        self.game.put("grpText", grp_text)
        sys.modules["grpText"] = grp_text
        comment = self.m.CommentProxy()
        comment.SetText("x" * 36)
        self.assertEqual((comment.short, comment.long), ("x" * 32 + "...", True))
        comment.SetText("short")
        self.assertEqual((comment.full, comment.short, comment.long), ("short", "short", False))
        gauge = self.m.GaugeProxy()
        gauge.SetPercentage(40, 100)
        self.assertAlmostEqual(gauge.percent, 0.4)
        gauge.SetPercentage(1, 0)
        self.assertEqual(gauge.percent, 0.0)

    def test_skill_slots_and_their_buttons(self):
        slots = self.m.GuildSkillSlotProxy(range(210, 219), None, cols=9, rows=1)
        slots.SetSkillSlot(210, 152, 7)
        slots.ShowSlotButton(211)
        slots.RefreshSlot()
        cells = slots.cells()
        self.assertEqual((cells[0]["kind"], cells[0]["count"]), ("skill", "7"))
        self.assertEqual(slots.plus()[:3], [False, True, False])
        slots.HideAllSlotButton()
        self.assertEqual(slots.plus(), [False] * 9)

    def test_scroll_resize_list_and_page(self):
        moved = []
        scroll = self.m.ScrollProxy()
        scroll.SetScrollEvent(lambda: moved.append(scroll.GetPos()))
        scroll.moved(1.5)
        self.assertEqual(moved, [1.0])
        resize = self.m.ResizeProxy(280, 180)
        resize.SetMoveEvent(lambda: moved.append(resize.GetLocalPosition()))
        resize.dragged(300, 200)
        resize.TurnOffCallBack()
        resize.dragged(310, 210)
        self.assertEqual(moved, [1.0, (300, 200)])
        listbox = self.m.ListBoxExProxy()
        self.assertTrue(listbox.IsEmpty())
        listbox.AppendItem("a")
        listbox.AppendItem("b")
        self.assertIsNone(listbox.GetSelectedItem())
        listbox.SelectIndex(1)
        self.assertEqual(listbox.GetSelectedItem(), "b")
        listbox.RemoveAllItems()
        self.assertIsNone(listbox.GetSelectedItem())
        page = self.m.PageWindowProxy("GUILD_INFO", "uiscript/guildwindow_guildinfopage.py")
        page.nameSlot = "anything the loader sets"
        page.Show()
        self.assertTrue(page.IsShow())
        self.assertEqual(page.GetScriptFileName(), "uiscript/guildwindow_guildinfopage.py")


class Message(FormProxiesTest):
    def test_show_opens_one_popup_with_the_message_and_the_accept_event(self):
        made = []

        class Popup(object):
            def __init__(self):
                self.log = []
                made.append(self)

            def SetText(self, text):
                self.log.append(("text", text))

            def SetAcceptEvent(self, event):
                self.event = event

            def Open(self):
                self.log.append(("open",))

            def Close(self):
                self.log.append(("close",))
        accepted = []
        message = self.m.MessageWindowProxy(make_dialog=Popup)
        message.GetChild("message").SetText("Wrong password")
        message.GetChild("accept").SetEvent(lambda: accepted.append(True))
        message.SetCenterPosition()
        message.SetTop()
        message.Show()
        made[0].event()
        message.Hide()
        message.Show()
        self.assertEqual(len(made), 1, "the same popup each time")
        self.assertEqual(made[0].log, [("text", "Wrong password"), ("open",), ("close",), ("text", "Wrong password"),
                                       ("open",)])
        self.assertEqual(accepted, [True])
        with self.assertRaises(KeyError):
            message.GetChild("cancel")


class TypedSlots(FormProxiesTest):
    def test_the_cells_carry_the_slot_type_and_the_position(self):
        player = self.game.modules["player"]
        self.game.give(0, 10, size=(1, 2))
        kind = [player.SLOT_TYPE_SHOP]
        slots = self.m.TypedSlotWindowProxy(range(40), None, cols=5, rows=8, positions=lambda slot: 40 + slot,
                                            slot_type=lambda: kind[0])
        slots.SetItemSlot(3, 10, 0)
        slots.RefreshSlot()
        cell = slots.cells()[3]
        self.assertEqual((cell["type"], cell["ref"], cell["h"]), (player.SLOT_TYPE_SHOP, 43, 2))
        self.assertTrue(slots.cells()[8]["covered"])
        kind[0] = player.SLOT_TYPE_PRIVATE_SHOP
        slots.RefreshSlot()
        self.assertEqual(slots.cells()[3]["type"], player.SLOT_TYPE_PRIVATE_SHOP, "asked at each refresh")
        plain = self.m.TypedSlotWindowProxy(range(4), None)
        plain.SetItemSlot(0, 10, 0)
        plain.RefreshSlot()
        self.assertEqual(plain.cells()[0]["type"], player.SLOT_TYPE_INVENTORY, "no slot type: the inventory's")


if __name__ == "__main__":
    unittest.main()
