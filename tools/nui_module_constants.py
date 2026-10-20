#!/usr/bin/env python3
"""Writes tools/fixtures/module_constants.json: the int constants the
client's item, player, skill and app modules expose, with their values, read
from nova-client-src's sources (the PyModule_AddIntConstant lines and the
enums and consts they name). The Wave 3b stand-ins (nui_game_support,
install_wave3b_ui and install_item_data) take the game modules' constants
from it, so the legacy rules (uiinventory.py, uitooltip.py) compare the
client's own values (P14 spec 9.3, 9.6).

    python3 tools/nui_module_constants.py --client ../nova-client-nui-w3b
    python3 tools/nui_module_constants.py --client ../nova-client-nui-w3b --check

A constant whose expression this reader cannot evaluate (a function call, a
macro it does not know) is listed under "unresolved"; the stand-ins leave it
out. Build switches are taken as the client's release build defines them
(ENABLE_COSTUME_SYSTEM, ENABLE_NEW_EQUIPMENT_SYSTEM, ENABLE_DRAGON_SOUL_SYSTEM
and ENABLE_ENERGY_SYSTEM on): every #ifdef block is read."""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fixtures", "module_constants.json")
HEADERS = ("src/GameLib/ItemData.h", "src/UserInterface/GameType.h", "src/UserInterface/PythonPlayer.h",
           "src/UserInterface/PythonSkill.h", "src/UserInterface/PythonItem.h", "src/UserInterface/Packet.h",
           "src/UserInterface/PythonPlayerModule.cpp", "src/UserInterface/PythonItemModule.cpp",
           "src/UserInterface/PythonApplicationModule.cpp", "src/UserInterface/PythonSkill.cpp")
MODULES = {"item": "src/UserInterface/PythonItemModule.cpp", "player": "src/UserInterface/PythonPlayerModule.cpp",
           "skill": "src/UserInterface/PythonSkill.cpp", "app": "src/UserInterface/PythonApplicationModule.cpp"}
ADD_RE = re.compile(r'PyModule_AddIntConstant\s*\(\s*\w+\s*,\s*"(\w+)"\s*,\s*([^;]+?)\)\s*;')
ENUM_RE = re.compile(r"\benum\b[^{;]*\{(.*?)\}", re.S)
CONST_RE = re.compile(r"\bconst\s+(?:DWORD|int|BYTE|WORD|UINT|unsigned\s+int|long)\s+(\w+)\s*=\s*([^;]+);")
SCOPE_RE = re.compile(r"\b\w+::")


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


def evaluate(expression, names):
    expression = SCOPE_RE.sub("", expression).strip()
    expression = re.sub(r"\b(\d+)[uUlL]+\b", r"\1", expression)
    expression = expression.replace("(DWORD)", "").replace("(int)", "").replace("(BYTE)", "")
    if not re.fullmatch(r"[\w\s+\-*/()<>|&~^]+", expression):
        raise ValueError(expression)
    tokens = set(re.findall(r"[A-Za-z_]\w*", expression))
    missing = [t for t in tokens if t not in names]
    if missing:
        raise KeyError(missing[0])
    value = eval(expression.replace("/", "//"), {"__builtins__": {}}, dict(names))
    if not isinstance(value, int):
        raise ValueError(expression)
    return value


def read_names(client):
    """{name: value} of every enum entry and const the headers define, in
    file order (a later definition of a name keeps the first one's value)."""
    names = {}
    pending = []
    for path in HEADERS:
        full = os.path.join(client, path)
        if not os.path.isfile(full):
            continue
        with open(full, encoding="utf-8", errors="replace") as handle:
            text = strip_comments(handle.read())
        text = re.sub(r"^\s*#.*$", "", text, flags=re.M)
        for body in ENUM_RE.findall(text):
            value = -1
            for entry in body.split(","):
                entry = entry.strip()
                if not entry:
                    continue
                name, _, expression = entry.partition("=")
                name = name.strip()
                if not re.fullmatch(r"[A-Za-z_]\w*", name):
                    continue
                if expression.strip():
                    try:
                        value = evaluate(expression, names)
                    except (KeyError, ValueError, SyntaxError, TypeError):
                        pending.append((name, expression))
                        continue
                else:
                    value += 1
                names.setdefault(name, value)
        for name, expression in CONST_RE.findall(text):
            pending.append((name, expression))
    for _ in range(4):
        left = []
        for name, expression in pending:
            if name in names:
                continue
            try:
                names[name] = evaluate(expression, names)
            except (KeyError, ValueError, SyntaxError, TypeError):
                left.append((name, expression))
        pending = left
    return names


def read_modules(client, names):
    modules = {}
    unresolved = {}
    for module, path in MODULES.items():
        with open(os.path.join(client, path), encoding="utf-8", errors="replace") as handle:
            text = strip_comments(handle.read())
        values = {}
        for name, expression in ADD_RE.findall(text):
            try:
                values[name] = evaluate(expression, names)
            except (KeyError, ValueError, SyntaxError, TypeError):
                unresolved.setdefault(module, []).append(name)
        modules[module] = dict(sorted(values.items()))
    return modules, dict((k, sorted(set(v))) for k, v in unresolved.items())


def build(client):
    commit = ""
    try:
        commit = subprocess.check_output(["git", "-C", client, "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        pass
    names = read_names(client)
    modules, unresolved = read_modules(client, names)
    document = {"$comment": "Generated by tools/nui_module_constants.py from nova-client-src %s; do not edit by hand. "
                            "The int constants of the client's item, player, skill and app modules "
                            "(PyModule_AddIntConstant), for the Wave 3b stand-ins." % (commit or "(unknown commit)"),
                "client_commit": commit, "modules": modules, "unresolved": unresolved}
    return json.dumps(document, indent="\t", sort_keys=False) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--client", required=True, help="a nova-client-src checkout")
    parser.add_argument("--check", action="store_true", help="exit 1 when the file differs (the commit aside)")
    args = parser.parse_args(argv)
    text = build(args.client)
    if args.check:
        with open(OUT, encoding="utf-8") as handle:
            old = json.load(handle)
        new = json.loads(text)
        same = old["modules"] == new["modules"]
        print("module_constants.json is %s" % ("current" if same else "stale"))
        return 0 if same else 1
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    counts = dict((name, len(values)) for name, values in json.loads(text)["modules"].items())
    print("wrote %s: %s" % (os.path.relpath(OUT), counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
