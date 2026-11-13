from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
import logging
from typing import Any

from .protocol import decode, encode, get_message, set_message, split_frames

_LOGGER = logging.getLogger(__name__)

CONNECT_TIMEOUT = 10
REQUEST_TIMEOUT = 10


class SoundbarError(Exception):
    pass


class SoundbarClient:
    def __init__(
        self,
        host: str,
        port: int,
        on_message: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self._on_message = on_message
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._waiters: dict[str, list[asyncio.Future[dict[str, Any]]]] = {}
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def _ensure_connected(self) -> asyncio.StreamWriter:
        async with self._lock:
            if self._writer is not None and not self._writer.is_closing():
                return self._writer
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), CONNECT_TIMEOUT
                )
            except (OSError, TimeoutError) as err:
                raise SoundbarError(f"Cannot connect to {self.host}:{self.port}: {err}") from err
            self._writer = writer
            self._reader_task = asyncio.get_running_loop().create_task(self._read(reader, writer))
            return writer

    async def _read(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        buffer = b""
        try:
            while chunk := await reader.read(4096):
                frames, buffer = split_frames(buffer + chunk)
                for frame in frames:
                    if (message := decode(frame)) is not None:
                        self._dispatch(message)
        except OSError as err:
            _LOGGER.debug("Connection to %s lost: %s", self.host, err)
        finally:
            if self._writer is writer:
                self._writer = None
            writer.close()
            self._fail_waiters(SoundbarError(f"Connection to {self.host} closed"))

    def _dispatch(self, message: dict[str, Any]) -> None:
        name = message.get("msg")
        if message.get("cmd") == "notibyget" and isinstance(name, str):
            for future in self._waiters.pop(name, []):
                if not future.done():
                    future.set_result(message)
        if self._on_message is not None:
            self._on_message(message)

    def _fail_waiters(self, error: Exception) -> None:
        waiters, self._waiters = self._waiters, {}
        for futures in waiters.values():
            for future in futures:
                if not future.done():
                    future.set_exception(error)

    async def _send(self, message: dict[str, Any]) -> None:
        writer = await self._ensure_connected()
        try:
            writer.write(encode(message))
            await writer.drain()
        except OSError as err:
            writer.close()
            raise SoundbarError(f"Sending to {self.host} failed: {err}") from err

    async def get(self, name: str) -> dict[str, Any]:
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._waiters.setdefault(name, []).append(future)
        try:
            await self._send(get_message(name))
            response = await asyncio.wait_for(future, REQUEST_TIMEOUT)
        except TimeoutError as err:
            raise SoundbarError(f"{self.host} did not answer {name}") from err
        finally:
            waiters = self._waiters.get(name, [])
            if future in waiters:
                waiters.remove(future)
        data = response.get("data")
        return data if isinstance(data, dict) else {}

    async def set(self, name: str, data: dict[str, Any]) -> None:
        await self._send(set_message(name, data))

    async def close(self) -> None:
        task, self._reader_task = self._reader_task, None
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
