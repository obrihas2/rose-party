# Party Mode shared room

This build puts all Party Mode users in one private relay room and enables Party
Mode automatically once Rose and League are ready. The existing toggle remains
available for disabling and re-enabling it.

## Shared-room build

This build embeds one 32-character lowercase hexadecimal room key,
hardcoded as `SHARED_ROOM_KEY` in `party/core/party_storage.py` and
published with the source. No environment variable or `config.ini` value
is needed. Every install of this build joins the same room automatically;
ordinary Rose builds and other modified builds use different room keys.

The relay URL is likewise hardcoded in `party/network/relay_config.py`
(tracked in Git) and points at the Cloudflare Worker
`rose-party-relay`. Because the key ships with the source, anyone with
this repository or its binaries can join the room — that is the intended
trade-off for a shared group room. To rotate the room, generate a new key
with `python -c "import secrets; print(secrets.token_hex(16))"`, replace
`SHARED_ROOM_KEY` in `party/core/party_storage.py`, rebuild, and
distribute the new build to all members.

## Use the room

1. Install the same Rose build on all four computers.
2. Start League if it is not already running.
3. Start or restart Rose.
4. Wait for Party Mode to auto-enable and the relay connection to become online;
   all four users should appear
   without pasting tokens.
5. Enter the same lobby and champion select, choose skins or custom mods, and
   verify that the selections appear for the matching champions.

Tokens remain supported. Pasting an existing valid token still decodes the
friend identity, but this build routes the join to the embedded shared room
instead of the friend's old per-account room.

## Compatibility and security

All members should use the same build and the same relay URL/version
compatibility. The relay supports at most 10 simultaneous connections per room,
so four users fit. A room key is a bearer secret; the relay does not authenticate
members separately. The key is published with this source, so anyone with the
build can join — rotate it (see above) if that is no longer desired.

Older Rose versions can still decode the existing token format and retain their
legacy per-account room behavior, but they will not automatically appear in the
new shared room unless they also run this shared-room change with the same key.
The skin and custom-mod hash protocol is unchanged, so modified clients retain
those features and remain compatible with the existing relay protocol.

## Startup behavior

Rose schedules a persistent Party Mode supervisor after the bridge and League
WebSocket are ready. It does not block startup and keeps retrying if League or
the relay is temporarily unavailable. It also resumes stopped relay connections
and re-enables Party Mode if it was manually disabled. The supervisor stops only
when Rose shuts down.
