from __future__ import annotations

from dataclasses import dataclass
import json
import struct
from typing import Any

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

KEY = b"T^&*J%^7tr~4^%^&I(o%^!jIJ__+a0 k"
IV = b"'%^Ur7gy$~t+f)%@"
FRAME_START = 0x10
HEADER = struct.Struct(">BI")

SETTINGS = "SETTING_VIEW_INFO"
SPEAKER = "SPK_LIST_VIEW_INFO"


def _cipher() -> Cipher:
    return Cipher(algorithms.AES(KEY), modes.CBC(IV))


def encode(message: dict[str, Any]) -> bytes:
    padder = padding.PKCS7(128).padder()
    plain = padder.update(json.dumps(message).encode()) + padder.finalize()
    encryptor = _cipher().encryptor()
    body = encryptor.update(plain) + encryptor.finalize()
    return HEADER.pack(FRAME_START, len(body)) + body


def decode(body: bytes) -> dict[str, Any] | None:
    if not body or len(body) % 16:
        return None
    decryptor = _cipher().decryptor()
    plain = decryptor.update(body) + decryptor.finalize()
    pad = plain[-1]
    if not 1 <= pad <= 16:
        return None
    try:
        message = json.loads(plain[:-pad])
    except ValueError:
        return None
    return message if isinstance(message, dict) else None


def split_frames(buffer: bytes) -> tuple[list[bytes], bytes]:
    frames: list[bytes] = []
    while True:
        start = buffer.find(FRAME_START)
        if start < 0:
            return frames, b""
        buffer = buffer[start:]
        if len(buffer) < HEADER.size:
            return frames, buffer
        _, length = HEADER.unpack_from(buffer)
        end = HEADER.size + length
        if len(buffer) < end:
            return frames, buffer
        frames.append(buffer[HEADER.size : end])
        buffer = buffer[end:]


def get_message(name: str) -> dict[str, Any]:
    return {"cmd": "get", "msg": name}


def set_message(name: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"cmd": "set", "msg": name, "data": data}


@dataclass(frozen=True)
class Level:
    key: str
    enabled_by_default: bool = True

    @property
    def field(self) -> str:
        return f"i_{self.key}_level"

    @property
    def min_field(self) -> str:
        return f"i_{self.key}_min"

    @property
    def max_field(self) -> str:
        return f"i_{self.key}_max"


LEVELS = (
    Level("woofer"),
    Level("center"),
    Level("top"),
    Level("rear", enabled_by_default=False),
)


@dataclass(frozen=True)
class Toggle:
    key: str
    field: str


TOGGLES = (Toggle("night_time", "b_night_time"),)


def toggle_state(settings: dict[str, Any], toggle: Toggle) -> bool | None:
    value = settings.get(toggle.field)
    return value if isinstance(value, bool) else None


@dataclass(frozen=True)
class LevelRange:
    minimum: int
    maximum: int


def level_range(settings: dict[str, Any], level: Level) -> LevelRange | None:
    fields = (level.field, level.min_field, level.max_field)
    if not all(isinstance(settings.get(field), int) for field in fields):
        return None
    return LevelRange(settings[level.min_field], settings[level.max_field])


# The soundbar stores levels as a 0-based step count from the minimum, not as dB.
def to_db(raw: int, rng: LevelRange) -> int:
    return raw + rng.minimum


def to_raw(db: float, rng: LevelRange) -> int:
    value = round(db)
    if not rng.minimum <= value <= rng.maximum:
        raise ValueError(f"{value} dB is outside {rng.minimum}..{rng.maximum} dB")
    return value - rng.minimum
