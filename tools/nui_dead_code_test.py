"""Tests for the removal of the unreachable legacy UI code (R1, P12 spec 8)
and the item_mall fix: python3 -B -m unittest nui_dead_code_test (from
tools/).

- none of the 25 deleted files is back;
- no module in assets/root imports a deleted module, and no name of the
  deleted code is left (the flags, the classes, the dialog attribute);
- every literal path a LoadScriptFile call in assets/root names resolves,
  case-insensitively, in assets/uiscript/uiscript/ or in a locale's ui
  folder (before R1, uioption.py's optiondialog.py and uishop.py's
  mallpagedialog.py did not, and the second one's load failure exited the
  client);
- Interface.OpenItemMall sends /in_game_mall (the system menu's Mall path,
  which the server answers with its mall command, opening the web window)
  and makes no window, and writes its log line once;
- every edited root module compiles."""
import ast
import os
import py_compile
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.join(REPO, "assets", "root")
UISCRIPT = os.path.join(REPO, "assets", "uiscript", "uiscript")
LOCALES = os.path.join(REPO, "assets", "locale", "locale")

DELETED_UISCRIPTS = ("fishingwindow.py", "guildwindow_guildinfopage_jp.py", "skillpointresetdialog.py",
                     "systemdialog_formall.py", "taskbar_easter.py", "taskbar_haloween.py", "taskbar_valentine.py",
                     "auctionwindow.py", "auctionwindow_listpage.py", "auctionwindow_registerpage.py",
                     "auctionwindow_uniqueauctionpage.py", "helpwindow2.py", "connectingdialog.py",
                     "systemdialog_forportal.py", "imekor.py")
DELETED_AE = ("taskbar_easter.py", "taskbar_haloween.py", "taskbar_valentine.py")
DELETED_MODULES = ("uiauction", "uicandidate", "uioption", "uiex", "test_affect", "utils", "rootlibcythonizer")
EDITED = ("uihelp.py", "uisystem.py", "intrologin.py", "introloading.py", "prototype.py", "uishop.py",
          "interfacemodule.py", "nui_system_menu.py")
# Names only the deleted code had (P12 spec 8.3).
GONE_NAMES = {
    "uihelp.py": ("ENABLE_HELP_MULTIPAGE", "LoadDialogMultiPage", "__SelectPage", "btnPages"),
    "uisystem.py": ("SYSTEM_MENU_FOR_PORTAL", "__LoadSystemMenu_ForPortal", "uiOption"),
    "intrologin.py": ("ConnectingDialog", "LOGIN_DELAY_SEC", "IsLoginDelay", "GetLoginDelay", "connectingDialog",
                      "isNowCountDown", "OnEndCountDown", "time.clock"),
    "introloading.py": ("uiOption",),
    "prototype.py": ("uiCandidate",),
    "uishop.py": ("MallPageDialog", "mallpagedialog"),
    "interfacemodule.py": ("mallPageDlg", "MallPageDialog"),
    "nui_system_menu.py": ("SYSTEM_MENU_FOR_PORTAL",),
}


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def root_modules():
    return sorted(name for name in os.listdir(ROOT) if name.endswith(".py"))


def lower_listing(folder):
    try:
        return {name.lower() for name in os.listdir(folder)}
    except OSError:
        return set()


class DeletedFiles(unittest.TestCase):
    def test_none_of_the_25_files_exists(self):
        missing = [os.path.join(UISCRIPT, name) for name in DELETED_UISCRIPTS]
        missing += [os.path.join(LOCALES, "ae", "ui", name) for name in DELETED_AE]
        missing += [os.path.join(ROOT, name + ".py") for name in DELETED_MODULES]
        self.assertEqual(len(missing), 25)
        for path in missing:
            self.assertFalse(os.path.exists(path), path)

    def test_no_locale_keeps_an_override_of_a_deleted_uiscript(self):
        for locale in sorted(os.listdir(LOCALES)):
            names = lower_listing(os.path.join(LOCALES, locale, "ui"))
            self.assertFalse(names & set(DELETED_UISCRIPTS), locale)

    def test_no_root_module_imports_a_deleted_module(self):
        for name in root_modules():
            tree = ast.parse(read(os.path.join(ROOT, name)), name)
            for node in ast.walk(tree):
                imported = []
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported = [node.module]
                for module in imported:
                    self.assertNotIn(module.lower(), DELETED_MODULES, "%s:%d" % (name, node.lineno))

    def test_the_names_only_the_deleted_code_had_are_gone(self):
        for name, gone in GONE_NAMES.items():
            source = read(os.path.join(ROOT, name))
            for word in gone:
                self.assertFalse(word in source, "%s still names %s" % (name, word))


class UiscriptPaths(unittest.TestCase):
    def literal_paths(self):
        """(module, line, file name) of every literal path a LoadScriptFile
        call names: a string, or the string after uiScriptLocale's locale
        folder (LOCALE_UISCRIPT_PATH + "x.py")."""
        found = []
        for name in root_modules():
            tree = ast.parse(read(os.path.join(ROOT, name)), name)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "LoadScriptFile" and len(node.args) >= 2):
                    continue
                arg = node.args[1]
                if isinstance(arg, ast.BinOp) and isinstance(arg.right, ast.Constant):
                    arg = arg.right
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    found.append((name, node.lineno, os.path.basename(arg.value.replace("\\", "/"))))
        return found

    def test_every_literal_uiscript_path_resolves(self):
        known = lower_listing(UISCRIPT)
        for locale in os.listdir(LOCALES):
            known |= lower_listing(os.path.join(LOCALES, locale, "ui"))
        paths = self.literal_paths()
        self.assertGreater(len(paths), 60)
        missing = [path for path in paths if path[2].lower() not in known]
        self.assertEqual(missing, [])


class ItemMall(unittest.TestCase):
    def interface(self):
        """Interface.OpenItemMall, compiled from interfacemodule.py, over
        recording net and dbg stand-ins."""
        source = read(os.path.join(ROOT, "interfacemodule.py"))
        tree = ast.parse(source)
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Interface")
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "OpenItemMall")
        lines = source.splitlines()[method.lineno - 1:method.end_lineno]
        calls = []
        net = types.SimpleNamespace(SendChatPacket=lambda text: calls.append(("net.SendChatPacket", text)))
        dbg = types.SimpleNamespace(Tracen=lambda text: calls.append(("dbg.Tracen", text)),
                                    TraceError=lambda text: calls.append(("dbg.TraceError", text)))
        namespace = {"ItemMallTraced": False}
        exec(compile("class Interface(object):\n" + "\n".join(lines) + "\n", "interfacemodule.py", "exec"), namespace)
        saved = {name: sys.modules.get(name) for name in ("net", "dbg")}
        sys.modules["net"], sys.modules["dbg"] = net, dbg
        self.addCleanup(lambda: [sys.modules.pop(name) if module is None else sys.modules.__setitem__(name, module)
                                 for name, module in saved.items()])
        return namespace["Interface"](), calls

    def test_item_mall_sends_in_game_mall_and_makes_no_window(self):
        interface, calls = self.interface()
        interface.OpenItemMall()
        interface.OpenItemMall()
        self.assertEqual(calls, [("dbg.Tracen", "item_mall: opening the mall web page through /in_game_mall"),
                                 ("net.SendChatPacket", "/in_game_mall"), ("net.SendChatPacket", "/in_game_mall")])
        self.assertEqual(vars(interface), {}, "no window attribute")

    def test_the_game_window_still_routes_item_mall_to_the_interface(self):
        source = read(os.path.join(ROOT, "game.py"))
        self.assertIn('"item_mall"				: self.__ItemMall_Open,', source)
        self.assertIn("self.interface.OpenItemMall()", source)

    def test_the_shop_module_has_no_mall_page_dialog(self):
        tree = ast.parse(read(os.path.join(ROOT, "uishop.py")))
        self.assertNotIn("MallPageDialog", [node.name for node in tree.body if isinstance(node, ast.ClassDef)])


class Compiles(unittest.TestCase):
    def test_every_edited_root_module_compiles(self):
        with tempfile.TemporaryDirectory() as work:
            for name in EDITED:
                py_compile.compile(os.path.join(ROOT, name), cfile=os.path.join(work, name + "c"), doraise=True)


if __name__ == "__main__":
    unittest.main()
