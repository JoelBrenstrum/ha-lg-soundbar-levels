# LG Soundbar Levels

Home Assistant integration for the speaker settings on LG Wi-Fi soundbars (SN/SK range) that the built-in LG Soundbars integration doesn't expose. It talks to the soundbar directly on the LAN (TCP 9741), the same protocol the LG Sound Bar app uses. No cloud.

| Entity | What it does |
|---|---|
| `number.<name>_volume` | Volume (0–40 on the SN8Y) |
| `switch.<name>_mute` | Mute |
| `select.<name>_input` | Input, from the list the soundbar offers |
| `select.<name>_sound_effect` | Sound effect (Standard, Movie, AI Sound Pro, ...) |
| `number.<name>_woofer_level` | Subwoofer level in dB (−15 to +6 on the SN8Y) |
| `number.<name>_center_level` | Centre channel level in dB |
| `number.<name>_overhead_level` | Overhead (up-firing) speaker level in dB |
| `number.<name>_rear_level` | Rear speaker level in dB |
| `switch.<name>_rear_speakers` | Rear speaker output |
| `number.<name>_dialogue_level` | Dialogue control 0–6; only available while the soundbar is playing DTS:X |
| `number.<name>_bass` / `_treble` | Bass and treble in dB |
| `number.<name>_av_sync` | Audio delay in ms (0–300) |
| `select.<name>_sleep_timer` | Turn the soundbar off after 10–180 minutes |
| `switch.<name>_night_time` | Night time: compresses loud peaks so you can listen late at night |
| `switch.<name>_auto_volume`, `_drc`, `_neural_x`, `_auto_power`, `_tv_remote` | The matching switches from the app's settings |
| `update.<name>_firmware` | Installed firmware, and whether the soundbar is offering a newer one |

Entities only appear for settings your soundbar reports. Changes made in the LG app show up in Home Assistant straight away, the settings are re-read every minute, and each change is re-checked a couple of seconds later so a setting the soundbar refuses snaps back.

Some soundbars, including the SN8Y, don't report their model. Set it under the integration's Configure options to show it on the device page.

It runs alongside the Google Cast or LG Soundbars integrations; keep using those for casting.

## Install

HACS → Custom repositories → add this repository as an Integration, install, restart, then Settings → Devices & services → Add integration → LG Soundbar Levels and enter the soundbar's IP address.

## Tested on

LG SN8Y.

## Development

```
uv venv -p python3.13 .venv && uv pip install -p .venv -r requirements_test.txt
.venv/bin/pytest
```
