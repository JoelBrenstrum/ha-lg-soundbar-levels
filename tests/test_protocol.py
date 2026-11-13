from __future__ import annotations

import pytest

from custom_components.lg_soundbar_levels.protocol import (
    CHOICES,
    LEVELS,
    TOGGLES,
    Firmware,
    LevelRange,
    choice_code,
    choice_current,
    choice_options,
    decode,
    display_range,
    encode,
    firmware,
    level_available,
    level_range,
    model_name,
    set_message,
    split_frames,
    to_display,
    to_raw,
    toggle_state,
)

from .conftest import SOUNDBAR_SETTINGS

TEMESCAL_FRAME = bytes.fromhex(
    "1000000050fbdb29fa856e2ffb675f092da2cee213884246d09c8ce003b98de0743fdc90e29d6171f08fca1119b316a9"
    "38973a44f43648044800650119a34a4c27a41837d393f9161eafe05e75c7dd115aab7f89b3"
)
LEVEL = {level.key: level for level in LEVELS}
CHOICE = {choice.key: choice for choice in CHOICES}
WOOFER = LEVEL["woofer_level"]


def test_encode_matches_the_lg_wire_format() -> None:
    assert encode(set_message("SETTING_VIEW_INFO", {"i_woofer_level": 12})) == TEMESCAL_FRAME


def test_decode_round_trips_an_encoded_frame() -> None:
    message = {"msg": "SPK_LIST_VIEW_INFO", "cmd": "notibyget", "data": {"s_user_name": "Bar"}}
    frames, rest = split_frames(encode(message))
    assert rest == b""
    assert [decode(frame) for frame in frames] == [message]


@pytest.mark.parametrize("body", [b"", b"x" * 15, b"\x00" * 16])
def test_decode_rejects_bodies_that_are_not_messages(body: bytes) -> None:
    assert decode(body) is None


def test_split_frames_keeps_partial_frames_for_the_next_read() -> None:
    first, second = encode({"msg": "A"}), encode({"msg": "B"})
    stream = first + second

    frames, rest = split_frames(stream[: len(first) + 3])
    assert [decode(frame) for frame in frames] == [{"msg": "A"}]

    frames, rest = split_frames(rest + stream[len(first) + 3 :])
    assert [decode(frame) for frame in frames] == [{"msg": "B"}]
    assert rest == b""


def test_split_frames_skips_bytes_before_a_frame_start() -> None:
    frames, rest = split_frames(b"\x00\x01" + encode({"msg": "A"}))
    assert [decode(frame) for frame in frames] == [{"msg": "A"}]
    assert rest == b""


def test_split_frames_drops_noise_without_a_frame_start() -> None:
    assert split_frames(b"\x00\x01\x02") == ([], b"")


def test_level_range_reads_min_and_max() -> None:
    assert level_range(SOUNDBAR_SETTINGS, WOOFER) == LevelRange(-15, 6)


def test_level_range_is_none_when_the_soundbar_does_not_report_the_level() -> None:
    assert level_range({"i_woofer_min": -15, "i_woofer_max": 6}, WOOFER) is None


def test_level_range_falls_back_to_the_default_when_limits_are_not_reported() -> None:
    assert level_range({"i_bass": 5}, LEVEL["bass"]) == LevelRange(-5, 5)
    assert level_range({"i_bass": 5, "i_bass_min": -3, "i_bass_max": 3}, LEVEL["bass"]) == LevelRange(-3, 3)


def test_volume_reads_its_limits_from_vol_min_and_max() -> None:
    assert level_range({"i_vol": 6, "i_vol_min": 0, "i_vol_max": 40}, LEVEL["volume"]) == LevelRange(0, 40)


def test_levels_convert_between_steps_and_db() -> None:
    rng = LevelRange(-15, 6)
    assert to_display(0, WOOFER, rng) == -15
    assert to_display(13, WOOFER, rng) == -2
    assert to_display(21, WOOFER, rng) == 6
    assert to_raw(-15, WOOFER, rng) == 0
    assert to_raw(-2.4, WOOFER, rng) == 13
    assert to_raw(6, WOOFER, rng) == 21


def test_bass_and_treble_are_centred_on_zero() -> None:
    rng = LevelRange(-5, 5)
    assert to_display(5, LEVEL["bass"], rng) == 0
    assert to_raw(-5, LEVEL["treble"], rng) == 0


def test_av_sync_is_stored_in_tens_of_milliseconds() -> None:
    av_sync = LEVEL["av_sync"]
    rng = LevelRange(0, 30)
    assert display_range(av_sync, rng) == LevelRange(0, 300)
    assert to_display(3, av_sync, rng) == 30
    assert to_raw(120, av_sync, rng) == 12


@pytest.mark.parametrize("db", [-16, 7])
def test_to_raw_rejects_values_outside_the_range(db: float) -> None:
    with pytest.raises(ValueError):
        to_raw(db, WOOFER, LevelRange(-15, 6))


def test_dialogue_is_only_available_while_the_soundbar_enables_it() -> None:
    dialogue = LEVEL["dialogue_level"]
    settings = {"i_dialog_level": 0, "i_dialog_min": 0, "i_dialog_max": 6}
    assert not level_available({**settings, "b_enable_dialog": False}, dialogue)
    assert level_available({**settings, "b_enable_dialog": True}, dialogue)
    assert level_available(settings, WOOFER) is False
    assert level_available(SOUNDBAR_SETTINGS, WOOFER)


def test_toggle_state_reads_booleans_only() -> None:
    night = next(toggle for toggle in TOGGLES if toggle.key == "night_time")
    assert toggle_state({"b_night_time": True}, night) is True
    assert toggle_state({"b_night_time": 1}, night) is None
    assert toggle_state({}, night) is None


def test_input_options_come_from_the_soundbar_and_include_the_current_input() -> None:
    data = {"ai_func_list": [0, 1, 15, 6, 19], "i_curr_func": 20}
    inputs = CHOICE["input"]
    assert choice_options(data, inputs) == [
        "Wi-Fi",
        "Bluetooth",
        "Optical/HDMI ARC",
        "HDMI In",
        "USB",
        "eARC",
    ]
    assert choice_current(data, inputs) == "eARC"
    assert choice_code(data, inputs, "Bluetooth") == 1


def test_unknown_codes_are_still_selectable() -> None:
    data = {"ai_eq_list": [13, 99], "i_curr_eq": 13}
    effects = CHOICE["sound_effect"]
    assert choice_options(data, effects) == ["Movie", "Unknown (99)"]
    assert choice_code(data, effects, "Unknown (99)") == 99


def test_choice_code_rejects_options_the_soundbar_does_not_offer() -> None:
    with pytest.raises(ValueError):
        choice_code({"ai_eq_list": [13], "i_curr_eq": 13}, CHOICE["sound_effect"], "Game")


def test_sleep_timer_offers_the_app_durations() -> None:
    sleep = CHOICE["sleep_timer"]
    data = {"i_sleep_time": -1}
    assert choice_current(data, sleep) == "Off"
    assert choice_options(data, sleep)[:3] == ["Off", "10 min", "20 min"]
    assert choice_code(data, sleep, "180 min") == 180


def test_firmware_reports_the_server_version_when_one_is_offered() -> None:
    installed = {"o_system_ver": {"s_main": "2204210"}, "o_server_ver": {}}
    assert firmware(installed) == Firmware("2204210", "2204210")
    offered = {**installed, "o_server_ver": {"s_main": "2301010"}}
    assert firmware(offered) == Firmware("2204210", "2301010")
    assert firmware({}) is None


def test_model_name_prefers_the_soundbar_then_the_configured_value() -> None:
    assert model_name({"s_model_name": "SN8YG"}, "SN8Y") == "SN8YG"
    assert model_name({"s_model_name": ""}, " SN8Y ") == "SN8Y"
    assert model_name({}, "") is None
