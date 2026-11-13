# LG Soundbar Levels

Home Assistant integration for the speaker settings on LG Wi-Fi soundbars (SN/SK range) that the built-in LG Soundbars integration doesn't expose. It talks to the soundbar directly on the LAN (TCP 9741), the same protocol the LG Sound Bar app uses. No cloud.

| Entity | What it does |
|---|---|
| `number.<name>_woofer_level` | Subwoofer level in dB (−15 to +6 on the SN8Y) |
| `number.<name>_center_level` | Centre channel level in dB |
| `number.<name>_top_level` | Up-firing speaker level in dB |
| `number.<name>_rear_level` | Rear speaker level in dB (disabled by default, enable it if you have rears) |
| `switch.<name>_night_time` | Night time: compresses loud peaks so you can listen late at night |

Changes made in the LG app show up in Home Assistant straight away, and the settings are re-read every minute.

It runs alongside the Google Cast or LG Soundbars integrations; keep using those for playback and volume.

## Install

HACS → Custom repositories → add this repository as an Integration, install, restart, then Settings → Devices & services → Add integration → LG Soundbar Levels and enter the soundbar's IP address.

## Tested on

LG SN8Y.

## Development

```
uv venv -p python3.13 .venv && uv pip install -p .venv -r requirements_test.txt
.venv/bin/pytest
```
