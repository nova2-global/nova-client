#!/usr/bin/env python3
"""Publish a release with novapack.

    python pack.py build  --out ../staging [--key ../keys/nova.key] [--channel live] [--optional]
    python pack.py keygen --out ../keys/nova
    python pack.py verify ../staging
    python pack.py publish ../staging user@host:/srv/nova-server/share/patch [--dry-run]

`novapack` (built from nova-client-src) must be on PATH or next to this script.
Group order comes from groups.txt; loose files from _loose/ (see LOOSE-FILES.md;
keep documentation out of that folder, everything in it is published).

`build --optional` publishes a nice-to-have patch: clients that start pick it
up, but the login gate keeps accepting the previously required release, so
nobody in game or at the login window is forced out. It keeps the channel's
current "required" id (read from <out>/channels/<channel>.json) and only
advances "release". A plain `build` makes the new release mandatory again.
"""
import json
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


def publish(staging, target, extra):
    """Two-phase rsync so a client never sees a channel pointer before its objects:
    1. releases/ and bundles/ (immutable, content-addressed: idempotent, unchanged
       bundles are skipped by size+checksum), 2. channels/ last."""
    staging = os.path.abspath(staging)
    if not os.path.isdir(os.path.join(staging, "channels")):
        sys.exit(f"{staging} does not look like a novapack staging directory (no channels/)")
    if not shutil.which("rsync"):
        sys.exit("rsync not found on PATH")
    base = ["rsync", "-a", "--checksum"] + extra
    target = target.rstrip("/") + "/"
    steps = [
        base + [os.path.join(staging, "releases") + "/", target + "releases/"],
        base + [os.path.join(staging, "bundles") + "/", target + "bundles/"],
        base + [os.path.join(staging, "channels") + "/", target + "channels/"],
    ]
    for cmd in steps:
        print(" ".join(cmd))
        rc = subprocess.call(cmd)
        if rc != 0:
            sys.exit(f"rsync failed with exit code {rc}; channel pointers were NOT updated" if cmd is not steps[-1] else rc)
    return 0


def option_value(args, name, default=None):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def current_required(args):
    """The release the login gate must keep accepting after an optional patch:
    the channel's current "required" id, or its "release" when every earlier
    patch was mandatory."""
    out = option_value(args, "--out")
    if not out:
        sys.exit("build --optional needs --out <staging dir> (the previous channel pointer lives there)")
    channel = option_value(args, "--channel", "live")
    path = os.path.join(out, "channels", channel + ".json")
    try:
        with open(path, encoding="utf-8") as handle:
            pointer = json.load(handle)
        required = pointer.get("required") or pointer["release"]
    except (OSError, ValueError, KeyError) as error:
        sys.exit(f"build --optional: cannot read the current channel pointer {path}: {error}")
    print(f"optional patch: login gate keeps accepting {required}")
    return required


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
        if "--optional" in args:
            args.remove("--optional")
            args += ["--required-release", current_required(args)]
    elif cmd == "publish":
        if len(rest) < 2:
            sys.exit("usage: pack.py publish <staging dir> <rsync target> [rsync options]")
        return publish(rest[0], rest[1], rest[2:])
    elif cmd in ("keygen", "verify", "inspect", "gc"):
        args = [exe, cmd] + rest
    else:
        sys.exit(f"unknown command {cmd!r}; see --help")
    print(" ".join(args))
    return subprocess.call(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
