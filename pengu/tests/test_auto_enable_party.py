# -*- coding: utf-8 -*-
"""Permanent Party Mode: the startup supervisor and the hardcoded shared room.

The shared-room build turns Party Mode on by itself and keeps it on, and it
ships its relay URL and room key in the source so no setup step can leave
party mode broken.
"""

import asyncio
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pengu.communication import message_handler as mh
from pengu.communication.message_handler import MessageHandler

ROOT = Path(__file__).resolve().parents[2]
RELAY_URL = "wss://rose-party-relay.ofkasfok1q2jrnininfask.workers.dev"


class FakePartyManager:
    """The PartyManager surface the supervisor loop touches."""

    def __init__(self, *, enabled=False, fail_enable_times=0):
        self.enabled = enabled
        self.enable_calls = 0
        self.keep_connected_calls = 0
        self._fail_enable_times = fail_enable_times

    async def enable(self):
        self.enable_calls += 1
        if self.enable_calls <= self._fail_enable_times:
            raise RuntimeError("relay unavailable")
        self.enabled = True
        return "token-abc"

    async def keep_connected(self):
        self.keep_connected_calls += 1


class AutoEnablePartyTests(unittest.TestCase):
    """Party Mode must turn itself on and stay on without user action."""

    def setUp(self):
        self.manager = FakePartyManager()
        self.broadcasts = []
        self.shared_state = SimpleNamespace(
            stop=False, party_mode_enabled=False, party_token=None
        )
        self.handler = MessageHandler.__new__(MessageHandler)
        self.handler._party_auto_enable_started = False
        self.handler.websocket_server = SimpleNamespace(loop=object())
        self.handler.shared_state = self.shared_state
        self.handler.broadcaster = SimpleNamespace(
            broadcast_party_state=lambda: self.broadcasts.append(1)
        )
        self.handler._ensure_party_manager = lambda: self.manager

    def _run_supervisor(self, sleep_policy):
        """Run one scheduled supervisor pass with asyncio.sleep short-circuited."""
        sleeps = []

        async def fake_sleep(delay):
            sleeps.append(delay)
            await sleep_policy(delay)

        with patch.object(mh.asyncio, "run_coroutine_threadsafe") as schedule, \
                patch.object(mh.asyncio, "sleep", new=fake_sleep):
            self.handler.auto_enable_party()
            self.assertEqual(schedule.call_count, 1)
            coroutine = schedule.call_args[0][0]
            try:
                asyncio.run(coroutine)
            finally:
                coroutine.close()
        return sleeps

    def _stop_after_one_sleep(self, _delay):
        async def stop():
            self.shared_state.stop = True
        return stop()

    def test_startup_enables_party_mode_and_announces_it(self):
        sleeps = self._run_supervisor(self._stop_after_one_sleep)

        self.assertEqual(self.manager.enable_calls, 1)
        self.assertEqual(self.manager.keep_connected_calls, 1)
        self.assertEqual(self.broadcasts, [1])
        self.assertTrue(self.shared_state.party_mode_enabled)
        self.assertEqual(self.shared_state.party_token, "token-abc")
        self.assertEqual(sleeps, [10.0])

    def test_an_already_enabled_party_mode_is_not_reenabled(self):
        self.manager.enabled = True

        self._run_supervisor(self._stop_after_one_sleep)

        self.assertEqual(self.manager.enable_calls, 0)
        self.assertEqual(self.manager.keep_connected_calls, 1)
        self.assertEqual(self.broadcasts, [])

    def test_a_failed_enable_is_retried_until_it_works(self):
        self.manager = FakePartyManager(fail_enable_times=1)
        self.handler._ensure_party_manager = lambda: self.manager
        seen = []

        async def policy(_delay):
            seen.append(_delay)
            if len(seen) >= 2:  # first sleep is the backoff, second the idle wait
                self.shared_state.stop = True

        sleeps = self._run_supervisor(policy)

        self.assertEqual(self.manager.enable_calls, 2)
        self.assertEqual(sleeps, [1.0, 10.0])  # 1s backoff, then the steady 10s
        self.assertTrue(self.shared_state.party_mode_enabled)
        self.assertEqual(self.manager.keep_connected_calls, 1)

    def test_the_supervisor_is_scheduled_only_once(self):
        with patch.object(mh.asyncio, "run_coroutine_threadsafe") as schedule:
            self.handler.auto_enable_party()
            self.handler.auto_enable_party()

            self.assertEqual(schedule.call_count, 1)
            schedule.call_args[0][0].close()

    def test_a_missing_bridge_loop_skips_without_crashing(self):
        self.handler.websocket_server = SimpleNamespace(loop=None)

        with patch.object(mh.asyncio, "run_coroutine_threadsafe") as schedule:
            self.handler.auto_enable_party()

            schedule.assert_not_called()


class SupervisorWiringTests(unittest.TestCase):
    """Rose's startup path must actually start the supervisor."""

    def test_startup_calls_auto_enable_party_after_pengu_setup(self):
        source = (ROOT / "main" / "__init__.py").read_text(encoding="utf-8")
        setup = source.find("_setup_pengu_and_injection")
        call = source.find("t_ui.message_handler.auto_enable_party()")

        self.assertNotEqual(setup, -1, "pengu setup missing from startup")
        self.assertNotEqual(call, -1, "auto_enable_party() not called at startup")
        self.assertLess(setup, call, "supervisor must start after pengu setup")


class HardcodedSharedRoomTests(unittest.TestCase):
    """The relay URL and room key ship in the build — no setup step needed."""

    def test_relay_config_is_hardcoded_to_the_cloudflare_worker(self):
        config = (ROOT / "party" / "network" / "relay_config.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(f'RELAY_URL = "{RELAY_URL}"', config)

        from party.network import relay_config
        self.assertEqual(relay_config.RELAY_URL, RELAY_URL)
        if "ROSE_RELAY_URL" not in os.environ:
            from party.network import ws_relay
            self.assertEqual(ws_relay.RELAY_URL, RELAY_URL)

    def test_relay_config_is_tracked_not_gitignored(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertNotIn("party/network/relay_config.py", gitignore)

    def test_the_shared_room_key_is_a_hardcoded_32_hex_value(self):
        from party.core import party_storage

        self.assertRegex(party_storage.SHARED_ROOM_KEY, r"^[0-9a-f]{32}$")
        self.assertEqual(
            party_storage.load_shared_room_key(), party_storage.SHARED_ROOM_KEY
        )


if __name__ == "__main__":
    unittest.main()
