from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .coordinator import SoundbarConfigEntry, SoundbarCoordinator

PLATFORMS = [Platform.NUMBER, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: SoundbarConfigEntry) -> bool:
    coordinator = SoundbarCoordinator(hass, entry, entry.data[CONF_HOST], entry.data[CONF_PORT])
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SoundbarConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.close()
    return unloaded
