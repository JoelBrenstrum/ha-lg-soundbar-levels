from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
import voluptuous as vol

from .client import SoundbarClient, SoundbarError
from .const import DEFAULT_PORT, DOMAIN
from .protocol import LEVELS, SETTINGS, SPEAKER, level_range


async def probe(host: str, port: int) -> tuple[str, dict[str, Any]]:
    client = SoundbarClient(host, port)
    try:
        speaker = await client.get(SPEAKER)
        settings = await client.get(SETTINGS)
    finally:
        await client.close()
    return str(speaker.get("s_user_name") or host), settings


class SoundbarLevelsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_HOST: user_input[CONF_HOST].strip(), CONF_PORT: user_input[CONF_PORT]}
            self._async_abort_entries_match({CONF_HOST: data[CONF_HOST]})
            try:
                name, settings = await probe(data[CONF_HOST], data[CONF_PORT])
            except SoundbarError:
                errors["base"] = "cannot_connect"
            else:
                if any(level_range(settings, level) for level in LEVELS):
                    return self.async_create_entry(title=name, data=data)
                errors["base"] = "no_levels"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
        )
