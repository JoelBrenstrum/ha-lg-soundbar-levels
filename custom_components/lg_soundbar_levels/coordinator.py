from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import SoundbarClient, SoundbarError
from .const import DOMAIN, SET_CHECK_DELAY, UPDATE_INTERVAL
from .protocol import POLLED, PRODUCT, SETTINGS

_LOGGER = logging.getLogger(__name__)

type SoundbarConfigEntry = ConfigEntry[SoundbarCoordinator]


class SoundbarCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    config_entry: SoundbarConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SoundbarConfigEntry, host: str, port: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = SoundbarClient(host, port, self._handle_message)
        self.product: dict[str, Any] | None = None
        self._cancel_check: Callable[[], None] | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        data = dict(self.data or {})
        try:
            data.update(await self.client.get(SETTINGS))
        except SoundbarError as err:
            raise UpdateFailed(str(err)) from err
        for name in (*POLLED, PRODUCT):
            if name == SETTINGS or (name == PRODUCT and self.product is not None):
                continue
            try:
                received = await self.client.get(name)
            except SoundbarError as err:
                _LOGGER.debug("Skipping %s: %s", name, err)
                received = {}
            if name == PRODUCT:
                self.product = received
            data.update(received)
        return data

    @callback
    def _handle_message(self, message: dict[str, Any]) -> None:
        data = message.get("data")
        if message.get("msg") not in POLLED or not isinstance(data, dict) or self.data is None:
            return
        self.async_set_updated_data({**self.data, **data})

    async def async_set(self, message: str, data: dict[str, Any]) -> None:
        try:
            await self.client.set(message, data)
        except SoundbarError as err:
            raise HomeAssistantError(str(err)) from err
        self.async_set_updated_data({**(self.data or {}), **data})
        self._cancel_pending_check()
        self._cancel_check = async_call_later(self.hass, SET_CHECK_DELAY, self._check_after_set)

    # A read straight after a write returns the old value, so confirm what the soundbar kept a little later.
    async def _check_after_set(self, _now: datetime) -> None:
        self._cancel_check = None
        await self.async_request_refresh()

    def _cancel_pending_check(self) -> None:
        if self._cancel_check is not None:
            self._cancel_check()
            self._cancel_check = None

    async def async_shutdown(self) -> None:
        self._cancel_pending_check()
        await super().async_shutdown()
        await self.client.close()
