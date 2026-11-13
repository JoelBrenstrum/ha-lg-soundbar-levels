from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SoundbarConfigEntry, SoundbarCoordinator
from .entity import SoundbarEntity
from .protocol import LEVELS, Level, LevelRange, level_range, to_db, to_raw


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SoundbarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        SoundbarLevelNumber(coordinator, level)
        for level in LEVELS
        if level_range(coordinator.data, level) is not None
    )


class SoundbarLevelNumber(SoundbarEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "dB"

    def __init__(self, coordinator: SoundbarCoordinator, level: Level) -> None:
        super().__init__(coordinator, f"{level.key}_level")
        self.level = level
        self._attr_entity_registry_enabled_default = level.enabled_by_default

    @property
    def range(self) -> LevelRange | None:
        return level_range(self.coordinator.data or {}, self.level)

    @property
    def available(self) -> bool:
        return super().available and self.range is not None

    @property
    def native_min_value(self) -> float:
        return self.range.minimum if self.range else 0

    @property
    def native_max_value(self) -> float:
        return self.range.maximum if self.range else 0

    @property
    def native_value(self) -> float | None:
        rng = self.range
        return to_db(self.coordinator.data[self.level.field], rng) if rng else None

    async def async_set_native_value(self, value: float) -> None:
        rng = self.range
        if rng is None:
            return
        await self.coordinator.async_set_settings({self.level.field: to_raw(value, rng)})
