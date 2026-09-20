#!/usr/bin/env python3
"""Publish a release with novapack.

    python pack.py build  --out ../staging [--key ../keys/nova.key] [--channel live]
    python pack.py keygen --out ../keys/nova
    python pack.py verify ../staging
    python pack.py publish ../staging user@host:/srv/nova-server/share/patch [--dry-run]

`novapack` (built from nova-client-src) must be on PATH or next to this script.
Group order comes from groups.txt; loose files from _loose/ (see LOOSE-FILES.md;
keep documentation out of that folder, everything in it is published).
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
