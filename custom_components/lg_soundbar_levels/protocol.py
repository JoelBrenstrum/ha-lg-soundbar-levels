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
FUNCTION = "FUNC_VIEW_INFO"
EQ = "EQ_VIEW_INFO"
UPDATE = "UPDATE_VIEW_INFO"
PRODUCT = "PRODUCT_INFO"
POLLED = (SETTINGS, SPEAKER, FUNCTION, EQ, UPDATE)


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
class LevelRange:
    minimum: int
    maximum: int


@dataclass(frozen=True)
class Level:
    key: str
    field: str
    message: str = SETTINGS
    unit: str | None = "dB"
    scale: int = 1
    default_range: LevelRange | None = None
    requires: str | None = None
    config: bool = True
    enabled_by_default: bool = True

    @property
    def min_field(self) -> str:
        return f"{self.field.removesuffix('_level')}_min"

    @property
    def max_field(self) -> str:
        return f"{self.field.removesuffix('_level')}_max"


LEVELS = (
    Level("volume", "i_vol", SPEAKER, unit=None, config=False),
    Level("woofer_level", "i_woofer_level"),
    Level("center_level", "i_center_level"),
    Level("top_level", "i_top_level"),
    Level("rear_level", "i_rear_level"),
    Level("dialogue_level", "i_dialog_level", unit=None, requires="b_enable_dialog"),
    Level("bass", "i_bass", EQ, default_range=LevelRange(-5, 5)),
    Level("treble", "i_treble", EQ, default_range=LevelRange(-5, 5)),
    Level("av_sync", "i_av_sync", unit="ms", scale=10, default_range=LevelRange(0, 30)),
)


@dataclass(frozen=True)
class Toggle:
    key: str
    field: str
    message: str = SETTINGS
    config: bool = True


TOGGLES = (
    Toggle("mute", "b_mute", SPEAKER, config=False),
    Toggle("night_time", "b_night_time"),
    Toggle("auto_volume", "b_auto_vol"),
    Toggle("drc", "b_drc"),
    Toggle("neural_x", "b_neuralx"),
    Toggle("rear_speakers", "b_rear"),
    Toggle("auto_power", "b_auto_power"),
    Toggle("tv_remote", "b_tv_remote"),
)


def toggle_state(settings: dict[str, Any], toggle: Toggle) -> bool | None:
    value = settings.get(toggle.field)
    return value if isinstance(value, bool) else None


def level_range(settings: dict[str, Any], level: Level) -> LevelRange | None:
    if not isinstance(settings.get(level.field), int):
        return None
    minimum, maximum = settings.get(level.min_field), settings.get(level.max_field)
    if isinstance(minimum, int) and isinstance(maximum, int):
        return LevelRange(minimum, maximum)
    return level.default_range


def level_available(settings: dict[str, Any], level: Level) -> bool:
    return level_range(settings, level) is not None and (
        level.requires is None or settings.get(level.requires) is True
    )


def display_range(level: Level, rng: LevelRange) -> LevelRange:
    return LevelRange(rng.minimum * level.scale, rng.maximum * level.scale)


# The soundbar stores levels as a 0-based step count from the minimum, not as the displayed value.
def to_display(raw: int, level: Level, rng: LevelRange) -> int:
    return (raw + rng.minimum) * level.scale


def to_raw(value: float, level: Level, rng: LevelRange) -> int:
    steps = round(value / level.scale)
    if not rng.minimum <= steps <= rng.maximum:
        shown = display_range(level, rng)
        raise ValueError(f"{value} is outside {shown.minimum}..{shown.maximum}")
    return steps - rng.minimum


@dataclass(frozen=True)
class Choice:
    key: str
    field: str
    message: str
    names: dict[int, str]
    list_field: str | None = None
    config: bool = False


INPUTS = {
    0: "Wi-Fi",
    1: "Bluetooth",
    2: "Portable",
    3: "Aux",
    4: "Optical",
    6: "HDMI In",
    7: "HDMI ARC",
    9: "Optical 2",
    10: "HDMI In 2",
    11: "HDMI In 3",
    12: "LG TV",
    15: "Optical/HDMI ARC",
    16: "LG Optical",
    17: "FM",
    18: "USB (hidden)",
    19: "USB",
    20: "eARC",
    21: "WOW Cast",
}

SOUND_EFFECTS = {
    0: "Standard",
    1: "Bass",
    2: "Flat",
    3: "Boost",
    4: "Treble and bass",
    5: "User EQ",
    6: "Music",
    7: "Cinema",
    8: "Night",
    9: "News",
    10: "Voice",
    11: "IA Sound",
    12: "ASC",
    13: "Movie",
    14: "Bass Blast",
    15: "Dolby Atmos",
    16: "DTS Virtual:X",
    17: "Bass Blast+",
    18: "DTS:X",
    19: "AI Sound Pro",
    20: "Clear Voice",
    21: "Sports",
    22: "Game",
}

SLEEP_OFF = -1
SLEEP_TIMES = {SLEEP_OFF: "Off"} | {
    minutes: f"{minutes} min" for minutes in (10, 20, 30, 40, 50, 60, 70, 80, 90, 120, 150, 180)
}

CHOICES = (
    Choice("input", "i_curr_func", FUNCTION, INPUTS, "ai_func_list"),
    Choice("sound_effect", "i_curr_eq", EQ, SOUND_EFFECTS, "ai_eq_list"),
    Choice("sleep_timer", "i_sleep_time", SETTINGS, SLEEP_TIMES, config=True),
)


def choice_name(choice: Choice, code: int) -> str:
    return choice.names.get(code, f"Unknown ({code})")


def choice_codes(settings: dict[str, Any], choice: Choice) -> list[int]:
    if choice.list_field is None:
        codes = list(choice.names)
    else:
        listed = settings.get(choice.list_field)
        codes = [code for code in listed if isinstance(code, int)] if isinstance(listed, list) else []
    current = settings.get(choice.field)
    if isinstance(current, int) and current not in codes:
        codes.append(current)
    return codes


def choice_options(settings: dict[str, Any], choice: Choice) -> list[str]:
    return [choice_name(choice, code) for code in choice_codes(settings, choice)]


def choice_current(settings: dict[str, Any], choice: Choice) -> str | None:
    current = settings.get(choice.field)
    return choice_name(choice, current) if isinstance(current, int) else None


def choice_code(settings: dict[str, Any], choice: Choice, option: str) -> int:
    for code in choice_codes(settings, choice):
        if choice_name(choice, code) == option:
            return code
    raise ValueError(f"{option} is not an option for {choice.key}")


@dataclass(frozen=True)
class Firmware:
    installed: str
    latest: str


def _main_version(value: Any) -> str | None:
    version = value.get("s_main") if isinstance(value, dict) else None
    return version if isinstance(version, str) and version else None


def firmware(settings: dict[str, Any]) -> Firmware | None:
    installed = _main_version(settings.get("o_system_ver"))
    if installed is None:
        return None
    return Firmware(installed, _main_version(settings.get("o_server_ver")) or installed)


def model_name(settings: dict[str, Any], configured: str | None) -> str | None:
    reported = settings.get("s_model_name")
    if isinstance(reported, str) and reported.strip():
        return reported.strip()
    return configured.strip() if configured and configured.strip() else None
