from __future__ import annotations

import asyncio

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lg_soundbar_levels.const import DOMAIN
from custom_components.lg_soundbar_levels.protocol import SETTINGS

from .conftest import FakeSoundbar

WOOFER = "number.living_room_soundbar_woofer_level"
NIGHT = "switch.living_room_soundbar_night_time"


async def setup(hass: HomeAssistant, soundbar: FakeSoundbar) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living Room Soundbar",
        data={CONF_HOST: "127.0.0.1", CONF_PORT: soundbar.port},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def wait_for_received(soundbar: FakeSoundbar, message: dict) -> None:
    async with asyncio.timeout(2):
        while message not in soundbar.received:
            await asyncio.sleep(0.01)


async def wait_for_state(hass: HomeAssistant, entity_id: str, state: str) -> None:
    async with asyncio.timeout(2):
        while hass.states.get(entity_id).state != state:
            await asyncio.sleep(0.01)


async def test_levels_are_shown_in_db(hass: HomeAssistant, soundbar: FakeSoundbar) -> None:
    entry = await setup(hass, soundbar)

    woofer = hass.states.get(WOOFER)
    assert woofer.state == "-2"
    assert woofer.attributes["min"] == -15
    assert woofer.attributes["max"] == 6
    assert woofer.attributes["unit_of_measurement"] == "dB"
    assert hass.states.get("number.living_room_soundbar_center_level").state == "2"
    assert hass.states.get("number.living_room_soundbar_top_level").state == "1"

    rear = er.async_get(hass).async_get("number.living_room_soundbar_rear_level")
    assert rear.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setting_a_level_sends_the_step_value(hass: HomeAssistant, soundbar: FakeSoundbar) -> None:
    await setup(hass, soundbar)

    await hass.services.async_call("number", "set_value", {"entity_id": WOOFER, "value": -15}, blocking=True)

    await wait_for_received(soundbar, {"cmd": "set", "msg": SETTINGS, "data": {"i_woofer_level": 0}})
    assert hass.states.get(WOOFER).state == "-15"


async def test_changes_made_elsewhere_are_pushed(hass: HomeAssistant, soundbar: FakeSoundbar) -> None:
    await setup(hass, soundbar)

    soundbar.push({"msg": SETTINGS, "cmd": "notibyset", "data": {"i_woofer_level": 21}})

    await wait_for_state(hass, WOOFER, "6")


async def test_setup_retries_when_the_soundbar_is_unreachable(
    hass: HomeAssistant, soundbar: FakeSoundbar
) -> None:
    await soundbar.stop()
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "127.0.0.1", CONF_PORT: soundbar.port})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_levels_go_unavailable_when_polling_fails(hass: HomeAssistant, soundbar: FakeSoundbar) -> None:
    entry = await setup(hass, soundbar)
    await soundbar.stop()

    await entry.runtime_data.async_refresh()

    assert hass.states.get(WOOFER).state == STATE_UNAVAILABLE


async def test_night_time_switch_sets_the_soundbar(hass: HomeAssistant, soundbar: FakeSoundbar) -> None:
    await setup(hass, soundbar)
    assert hass.states.get(NIGHT).state == "off"

    await hass.services.async_call("switch", "turn_on", {"entity_id": NIGHT}, blocking=True)

    await wait_for_received(soundbar, {"cmd": "set", "msg": SETTINGS, "data": {"b_night_time": True}})
    assert hass.states.get(NIGHT).state == "on"

    soundbar.push({"msg": SETTINGS, "cmd": "notibyset", "data": {"b_night_time": False}})
    await wait_for_state(hass, NIGHT, "off")
