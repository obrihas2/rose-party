#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify a built Rose.exe still carries the Party Mode customizations.

Checks the PYZ archive of dist/Rose/Rose.exe for the shared room key, the
Cloudflare relay URL, the auto-enable supervisor, the release URLs of this
fork and the relay protocol version, so an upstream merge or a dependency
bump cannot silently ship a build without them.
"""

import os
import re
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "dist" / "Rose" / "Rose.exe"

CHECKS = {
    "party.core.party_storage": [
        ("hardcoded shared room key", "7895e232ebf27cdc892439a75a9db1c4"),
        ("identity key loader", "load_party_identity_key"),
    ],
    "party.network.relay_config": [
        ("Cloudflare relay URL", "rose-party-relay.ofkasfok1q2jrnininfask.workers.dev"),
    ],
    "pengu.communication.message_handler": [
        ("auto_enable_party supervisor", "auto_enable_party"),
        ("auto-enable log line", "Party mode auto-enabled"),
    ],
    "main": [("startup call to supervisor", "auto_enable_party")],
    "party.core.party_manager": [
        ("enable() joins shared room", "load_shared_room_key"),
        ("identity credential wired", "_identity_key"),
    ],
    "launcher.update.github_client": [
        ("release URLs point at this fork", "obrihas2/rose-party"),
    ],
    "party.network.ws_relay": [
        ("relay protocol version", "RELAY_PROTOCOL_VERSION"),
        ("protocol header check", "X-Rose-Party-Protocol"),
    ],
    "config": [],
}


def app_version() -> str:
    text = (ROOT / "config.py").read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else "no-version-found"


CHECKS["config"] = [("version matches the release", app_version())]


def all_strings(obj, seen=None):
    """Every string/bytes constant reachable from a code object."""
    if seen is None:
        seen = set()
    if id(obj) in seen:
        return []
    seen.add(id(obj))
    if isinstance(obj, types.CodeType):
        out = []
        for c in obj.co_consts:
            out.extend(all_strings(c, seen))
        out.extend(all_strings(obj.co_names, seen))
        out.extend(all_strings(obj.co_varnames, seen))
        return out
    if isinstance(obj, (list, tuple)):
        out = []
        for i in obj:
            out.extend(all_strings(i, seen))
        return out
    if isinstance(obj, (bytes, bytearray)):
        return [obj.decode("latin-1")]
    return [obj] if isinstance(obj, str) else []


def main() -> int:
    if not EXE.exists():
        print(f"[FAIL] {EXE} not built")
        return 1
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader

    archive = CArchiveReader(str(EXE))
    pyz_name = next(n for n in archive.toc if n.endswith(".pyz"))
    fd, pyz_path = tempfile.mkstemp(suffix=".pyz")
    os.close(fd)
    with open(pyz_path, "wb") as fh:
        fh.write(archive.extract(pyz_name))
    pyz = ZlibArchiveReader(pyz_path)

    failed = False
    for module, needles in CHECKS.items():
        try:
            code = pyz.extract(module)
        except KeyError:
            print(f"[FAIL] {module}: not in exe")
            failed = True
            continue
        blob = "\n".join(all_strings(code))
        for label, needle in needles:
            ok = needle in blob
            if not ok:
                failed = True
            print(f"[{'OK  ' if ok else 'FAIL'}] {module}: {label}")

    try:
        os.unlink(pyz_path)
    except OSError:
        pass
    if failed:
        print("Party Mode verification FAILED for the built executable.")
        return 1
    print("Party Mode verification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
