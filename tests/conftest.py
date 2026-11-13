from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import copy
from typing import Any

import pytest

from custom_components.lg_soundbar_levels.protocol import (
    EQ,
    FUNCTION,
    SETTINGS,
    SPEAKER,
    UPDATE,
    decode,
    encode,
    split_frames,
)

SOUNDBAR_SETTINGS: dict[str, Any] = {
    "i_woofer_level": 13,
    "i_woofer_min": -15,
    "i_woofer_max": 6,
    "i_center_level": 8,
    "i_center_min": -6,
    "i_center_max": 6,
    "i_top_level": 7,
    "i_top_min": -6,
    "i_top_max": 6,
    "i_rear_level": 6,
    "i_rear_min": -6,
    "i_rear_max": 6,
    "i_dialog_level": 0,
    "i_dialog_min": 0,
    "i_dialog_max": 6,
    "b_enable_dialog": False,
    "i_av_sync": 3,
    "i_sleep_time": -1,
    "b_night_time": False,
    "b_auto_vol": True,
    "b_drc": False,
    "b_neuralx": True,
    "b_rear": True,
    "b_auto_power": True,
    "b_tv_remote": True,
}

SOUNDBAR_MESSAGES: dict[str, dict[str, Any]] = {
    SETTINGS: SOUNDBAR_SETTINGS,
    SPEAKER: {
        "s_user_name": "Living Room Soundbar",
        "i_vol": 6,
        "i_vol_min": 0,
        "i_vol_max": 40,
        "b_mute": False,
    },
    FUNCTION: {"ai_func_list": [0, 1, 15, 6, 19], "i_curr_func": 20},
    EQ: {"ai_eq_list": [14, 0, 13, 6, 19, 5, 15], "i_curr_eq": 13, "i_bass": 5, "i_treble": 7},
    UPDATE: {
        "b_update": False,
        "o_server_ver": {},
        "o_system_ver": {"s_main": "2204210", "s_micom": "2204211"},
    },
}


class FakeSoundbar:
    def __init__(self) -> None:
        self.messages = copy.deepcopy(SOUNDBAR_MESSAGES)
        self.received: list[dict[str, Any]] = []
        self.writers: list[asyncio.StreamWriter] = []
        self.answer = True
        self.answer_sets = True
        self.server: asyncio.Server | None = None
        self.port = 0

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._serve, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        self.drop_connections()
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()

    def drop_connections(self) -> None:
        for writer in self.writers:
            writer.close()
        self.writers.clear()

    def push(self, message: dict[str, Any]) -> None:
        for writer in self.writers:
            writer.write(encode(message))

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.writers.append(writer)
        buffer = b""
        try:
            while chunk := await reader.read(4096):
                frames, buffer = split_frames(buffer + chunk)
                for frame in frames:
                    message = decode(frame)
                    assert message is not None
                    self.received.append(message)
                    self._respond(message, writer)
                await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()

    def _respond(self, message: dict[str, Any], writer: asyncio.StreamWriter) -> None:
        if not self.answer:
            return
        name = message["msg"]
        if message["cmd"] == "get":
            data = self.messages.get(name, {})
            writer.write(encode({"msg": name, "cmd": "notibyget", "data": data, "result": "ok"}))
        elif message["cmd"] == "set" and name in self.messages and self.answer_sets:
            self.messages[name].update(message["data"])
            writer.write(encode({"msg": name, "cmd": "notibyset", "data": message["data"], "result": "ok"}))


@pytest.fixture
async def soundbar(socket_enabled: None) -> AsyncIterator[FakeSoundbar]:
    fake = FakeSoundbar()
    await fake.start()
    yield fake
    await fake.stop()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    return None
