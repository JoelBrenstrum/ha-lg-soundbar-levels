from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lg_soundbar_levels.const import DOMAIN

from .conftest import FakeSoundbar


@pytest.fixture(autouse=True)
def skip_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    async def setup_entry(*_args) -> bool:
        return True

    monkeypatch.setattr("custom_components.lg_soundbar_levels.async_setup_entry", setup_entry)


async def submit(hass: HomeAssistant, port: int):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: " 127.0.0.1 ", CONF_PORT: port}
    )


async def test_creates_an_entry_named_after_the_soundbar(hass: HomeAssistant, soundbar: FakeSoundbar) -> None:
    result = await submit(hass, soundbar.port)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room Soundbar"
    assert result["data"] == {CONF_HOST: "127.0.0.1", CONF_PORT: soundbar.port}


async def test_shows_an_error_when_the_soundbar_is_unreachable(
    hass: HomeAssistant, soundbar: FakeSoundbar
) -> None:
    await soundbar.stop()

    result = await submit(hass, soundbar.port)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_shows_an_error_when_no_levels_are_reported(
    hass: HomeAssistant, soundbar: FakeSoundbar
) -> None:
    soundbar.settings = {"b_night_time": False}

    result = await submit(hass, soundbar.port)

    assert result["errors"] == {"base": "no_levels"}


async def test_aborts_when_the_host_is_already_set_up(hass: HomeAssistant, soundbar: FakeSoundbar) -> None:
    MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "127.0.0.1", CONF_PORT: soundbar.port}).add_to_hass(hass)

    result = await submit(hass, soundbar.port)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
