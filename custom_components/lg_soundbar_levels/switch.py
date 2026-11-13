from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SoundbarConfigEntry, SoundbarCoordinator
from .entity import SoundbarEntity
from .protocol import TOGGLES, Toggle, toggle_state


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SoundbarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        SoundbarToggleSwitch(coordinator, toggle)
        for toggle in TOGGLES
        if toggle_state(coordinator.data, toggle) is not None
    )


class SoundbarToggleSwitch(SoundbarEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: SoundbarCoordinator, toggle: Toggle) -> None:
        super().__init__(coordinator, toggle.key)
        self.toggle = toggle

    @property
    def available(self) -> bool:
        return super().available and self.is_on is not None

    @property
    def is_on(self) -> bool | None:
        return toggle_state(self.coordinator.data or {}, self.toggle)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_settings({self.toggle.field: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_settings({self.toggle.field: False})
