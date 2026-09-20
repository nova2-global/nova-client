#!/usr/bin/env python3
"""Publish a release with novapack.

    python pack.py build  --out ../staging [--key ../keys/nova.key] [--channel live]
    python pack.py keygen --out ../keys/nova
    python pack.py verify ../staging

`novapack` (built from nova-client-src) must be on PATH or next to this script.
Group order comes from groups.txt; loose files from _loose/.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def find_novapack():
    for name in ("novapack.exe", "novapack"):
        local = os.path.join(HERE, name)
        if os.path.exists(local):
            return local
        found = shutil.which(name)
        if found:
            return found
    sys.exit("novapack not found: build nova-client-src and put novapack(.exe) on PATH or next to pack.py")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    exe = find_novapack()
    cmd, rest = argv[0], argv[1:]
    if cmd == "build":
        args = [exe, "build", "--groups", os.path.join(HERE, "groups.txt"), "--assets", HERE]
        loose = os.path.join(HERE, "_loose")
        if os.path.isdir(loose):
            args += ["--loose", loose]
        args += rest
    elif cmd in ("keygen", "verify", "inspect", "gc"):
        args = [exe, cmd] + rest
    else:
        sys.exit(f"unknown command {cmd!r}; see --help")
    print(" ".join(args))
    return subprocess.call(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
