#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Party Storage
Keeps each account's party key across sessions, so the token (and room)
friends already have keeps working after Rose restarts.
"""

import json
import re
import secrets
from pathlib import Path

from utils.core.logging import get_logger
from utils.core.paths import get_user_data_dir

log = get_logger()

PARTY_KEYS_FILE = "party_keys.json"
KEY_SIZE = 32
SHARED_ROOM_KEY = "7895e232ebf27cdc892439a75a9db1c4"
_ROOM_KEY_RE = re.compile(r"^[0-9a-f]{32}$")


def _keys_path() -> Path:
    return get_user_data_dir() / PARTY_KEYS_FILE


def load_shared_room_key() -> str:
    """Return the shared room key embedded in this build."""
    if not _ROOM_KEY_RE.fullmatch(SHARED_ROOM_KEY):
        raise RuntimeError("Party Mode shared room key is invalid in this build")
    return SHARED_ROOM_KEY


def load_party_key(summoner_id: int) -> bytes:
    """Return this account's party key, creating and saving one if needed."""
    path = _keys_path()
    keys = {}
    try:
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                keys = loaded
    except (OSError, ValueError) as e:
        log.debug(f"[PARTY] Could not read party keys: {e}")

    stored = keys.get(str(summoner_id))
    if isinstance(stored, str):
        try:
            key = bytes.fromhex(stored)
            if len(key) == KEY_SIZE:
                return key
        except ValueError:
            pass

    key = secrets.token_bytes(KEY_SIZE)
    keys[str(summoner_id)] = key.hex()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(json.dumps(keys, indent=2), encoding="utf-8")
        temporary.replace(path)
    except OSError as e:
        # Still usable for this session; the token just changes next time
        log.warning(f"[PARTY] Could not save party key: {e}")
    return key
