from __future__ import annotations

from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MODEL, DOMAIN
from .coordinator import SoundbarCoordinator
from .protocol import firmware, model_name


class SoundbarEntity(CoordinatorEntity[SoundbarCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SoundbarCoordinator, key: str, config: bool = True) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        data = coordinator.data or {}
        version = firmware(data)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_entity_category = EntityCategory.CONFIG if config else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="LG",
            model=model_name(data, entry.options.get(CONF_MODEL)),
            sw_version=version.installed if version else None,
        )
