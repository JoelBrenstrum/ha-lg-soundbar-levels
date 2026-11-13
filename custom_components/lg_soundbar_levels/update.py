from __future__ import annotations

from homeassistant.components.update import UpdateEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SoundbarConfigEntry, SoundbarCoordinator
from .entity import SoundbarEntity
from .protocol import firmware


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SoundbarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if firmware(coordinator.data) is not None:
        async_add_entities([SoundbarFirmwareUpdate(coordinator)])


class SoundbarFirmwareUpdate(SoundbarEntity, UpdateEntity):
    def __init__(self, coordinator: SoundbarCoordinator) -> None:
        super().__init__(coordinator, "firmware")
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def installed_version(self) -> str | None:
        version = firmware(self.coordinator.data or {})
        return version.installed if version else None

    @property
    def latest_version(self) -> str | None:
        version = firmware(self.coordinator.data or {})
        return version.latest if version else None
