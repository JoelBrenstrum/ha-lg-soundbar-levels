from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SoundbarConfigEntry, SoundbarCoordinator
from .entity import SoundbarEntity
from .protocol import CHOICES, Choice, choice_code, choice_current, choice_options


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SoundbarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        SoundbarChoiceSelect(coordinator, choice)
        for choice in CHOICES
        if choice_current(coordinator.data, choice) is not None
    )


class SoundbarChoiceSelect(SoundbarEntity, SelectEntity):
    def __init__(self, coordinator: SoundbarCoordinator, choice: Choice) -> None:
        super().__init__(coordinator, choice.key, choice.config)
        self.choice = choice

    @property
    def available(self) -> bool:
        return super().available and self.current_option is not None

    @property
    def options(self) -> list[str]:
        return choice_options(self.coordinator.data or {}, self.choice)

    @property
    def current_option(self) -> str | None:
        return choice_current(self.coordinator.data or {}, self.choice)

    async def async_select_option(self, option: str) -> None:
        code = choice_code(self.coordinator.data or {}, self.choice, option)
        await self.coordinator.async_set(self.choice.message, {self.choice.field: code})
