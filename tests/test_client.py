from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from custom_components.lg_soundbar_levels.client import SoundbarClient, SoundbarError
from custom_components.lg_soundbar_levels.protocol import SETTINGS

from .conftest import FakeSoundbar


async def wait_for(condition, timeout: float = 2) -> None:
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0.01)


async def test_get_returns_the_response_data(soundbar: FakeSoundbar) -> None:
    client = SoundbarClient("127.0.0.1", soundbar.port)
    try:
        assert (await client.get(SETTINGS))["i_woofer_level"] == 13
    finally:
        await client.close()


async def test_set_sends_the_data_and_reports_the_confirmation(soundbar: FakeSoundbar) -> None:
    messages: list[dict[str, Any]] = []
    client = SoundbarClient("127.0.0.1", soundbar.port, messages.append)
    try:
        await client.set(SETTINGS, {"i_woofer_level": 0})
        await wait_for(lambda: any(m["cmd"] == "notibyset" for m in messages))
    finally:
        await client.close()
    assert soundbar.received[-1] == {"cmd": "set", "msg": SETTINGS, "data": {"i_woofer_level": 0}}
    assert soundbar.messages[SETTINGS]["i_woofer_level"] == 0


async def test_reconnects_after_the_soundbar_drops_the_connection(soundbar: FakeSoundbar) -> None:
    client = SoundbarClient("127.0.0.1", soundbar.port)
    try:
        await client.get(SETTINGS)
        soundbar.drop_connections()
        await wait_for(lambda: not client.connected)
        assert (await client.get(SETTINGS))["i_woofer_level"] == 13
    finally:
        await client.close()


async def test_get_fails_when_the_soundbar_does_not_answer(soundbar: FakeSoundbar) -> None:
    soundbar.answer = False
    client = SoundbarClient("127.0.0.1", soundbar.port)
    try:
        with (
            patch("custom_components.lg_soundbar_levels.client.REQUEST_TIMEOUT", 0.05),
            pytest.raises(SoundbarError),
        ):
            await client.get(SETTINGS)
    finally:
        await client.close()


async def test_get_fails_when_nothing_is_listening(soundbar: FakeSoundbar) -> None:
    port = soundbar.port
    await soundbar.stop()
    client = SoundbarClient("127.0.0.1", port)
    with pytest.raises(SoundbarError):
        await client.get(SETTINGS)
