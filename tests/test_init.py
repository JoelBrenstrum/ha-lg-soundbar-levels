from __future__ import annotations

import asyncio
from datetime import timedelta

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.lg_soundbar_levels.const import CONF_MODEL, DOMAIN, SET_CHECK_DELAY
from custom_components.lg_soundbar_levels.protocol import EQ, FUNCTION, SETTINGS, SPEAKER

from .conftest import FakeSoundbar

WOOFER = "number.living_room_soundbar_woofer_level"
NIGHT = "switch.living_room_soundbar_night_time"


async def setup(hass: HomeAssistant, soundbar: FakeSoundbar, options: dict | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living Room Soundbar",
        data={CONF_HOST: "127.0.0.1", CONF_PORT: soundbar.port},
        options=options or {},
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
    assert hass.states.get("number.living_room_soundbar_overhead_level").state == "1"
    assert hass.states.get("number.living_room_soundbar_rear_level").state == "0"
    assert hass.states.get("number.living_room_soundbar_bass").state == "0"
    assert hass.states.get("number.living_room_soundbar_treble").state == "2"
    assert hass.states.get("number.living_room_soundbar_av_sync").state == "30"

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


async def test_volume_and_mute_use_the_speaker_message(hass: HomeAssistant, soundbar: FakeSoundbar) -> None:
    await setup(hass, soundbar)
    volume = "number.living_room_soundbar_volume"
    assert hass.states.get(volume).state == "6"
    assert hass.states.get(volume).attributes["max"] == 40

    await hass.services.async_call("number", "set_value", {"entity_id": volume, "value": 12}, blocking=True)
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.living_room_soundbar_mute"}, blocking=True
    )

    await wait_for_received(soundbar, {"cmd": "set", "msg": SPEAKER, "data": {"i_vol": 12}})
    await wait_for_received(soundbar, {"cmd": "set", "msg": SPEAKER, "data": {"b_mute": True}})


async def test_input_and_sound_effect_selects(hass: HomeAssistant, soundbar: FakeSoundbar) -> None:
    await setup(hass, soundbar)
    inputs = "select.living_room_soundbar_input"
    effects = "select.living_room_soundbar_sound_effect"
    assert hass.states.get(inputs).state == "eARC"
    assert "Bluetooth" in hass.states.get(inputs).attributes["options"]
    assert hass.states.get(effects).state == "Movie"

    await hass.services.async_call(
        "select", "select_option", {"entity_id": inputs, "option": "Bluetooth"}, blocking=True
    )
    await hass.services.async_call(
        "select", "select_option", {"entity_id": effects, "option": "AI Sound Pro"}, blocking=True
    )

    await wait_for_received(soundbar, {"cmd": "set", "msg": FUNCTION, "data": {"i_curr_func": 1}})
    await wait_for_received(soundbar, {"cmd": "set", "msg": EQ, "data": {"i_curr_eq": 19}})


async def test_sleep_timer_off_sends_minus_one(hass: HomeAssistant, soundbar: FakeSoundbar) -> None:
    await setup(hass, soundbar)
    sleep = "select.living_room_soundbar_sleep_timer"

    await hass.services.async_call(
        "select", "select_option", {"entity_id": sleep, "option": "30 min"}, blocking=True
    )
    await hass.services.async_call(
        "select", "select_option", {"entity_id": sleep, "option": "Off"}, blocking=True
    )

    await wait_for_received(soundbar, {"cmd": "set", "msg": SETTINGS, "data": {"i_sleep_time": 30}})
    await wait_for_received(soundbar, {"cmd": "set", "msg": SETTINGS, "data": {"i_sleep_time": -1}})


async def test_dialogue_level_follows_the_soundbar_enable_flag(
    hass: HomeAssistant, soundbar: FakeSoundbar
) -> None:
    await setup(hass, soundbar)
    dialogue = "number.living_room_soundbar_dialogue_level"
    assert hass.states.get(dialogue).state == STATE_UNAVAILABLE

    soundbar.push({"msg": SETTINGS, "cmd": "notibyset", "data": {"b_enable_dialog": True}})

    await wait_for_state(hass, dialogue, "0")


async def test_firmware_and_model_are_reported(hass: HomeAssistant, soundbar: FakeSoundbar) -> None:
    entry = await setup(hass, soundbar, {CONF_MODEL: "SN8Y"})

    update = hass.states.get("update.living_room_soundbar_firmware")
    assert update.state == "off"
    assert update.attributes["installed_version"] == "2204210"

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device.model == "SN8Y"
    assert device.sw_version == "2204210"


async def test_a_change_the_soundbar_refuses_is_corrected(
    hass: HomeAssistant, soundbar: FakeSoundbar
) -> None:
    await setup(hass, soundbar)
    auto_volume = "switch.living_room_soundbar_auto_volume"
    soundbar.answer_sets = False

    await hass.services.async_call("switch", "turn_off", {"entity_id": auto_volume}, blocking=True)
    assert hass.states.get(auto_volume).state == "off"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=SET_CHECK_DELAY + 1))

    await wait_for_state(hass, auto_volume, "on")
