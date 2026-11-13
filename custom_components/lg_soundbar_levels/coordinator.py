from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import SoundbarClient, SoundbarError
from .const import DOMAIN, UPDATE_INTERVAL
from .protocol import SETTINGS

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

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            settings = await self.client.get(SETTINGS)
        except SoundbarError as err:
            raise UpdateFailed(str(err)) from err
        return {**(self.data or {}), **settings}

    @callback
    def _handle_message(self, message: dict[str, Any]) -> None:
        data = message.get("data")
        if message.get("msg") != SETTINGS or not isinstance(data, dict) or self.data is None:
            return
        self.async_set_updated_data({**self.data, **data})

    async def async_set_settings(self, data: dict[str, Any]) -> None:
        try:
            await self.client.set(SETTINGS, data)
        except SoundbarError as err:
            raise HomeAssistantError(str(err)) from err
        self.async_set_updated_data({**(self.data or {}), **data})

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        await self.client.close()
