from __future__ import annotations

import pytest

from custom_components.lg_soundbar_levels.protocol import (
    LEVELS,
    TOGGLES,
    LevelRange,
    decode,
    encode,
    level_range,
    set_message,
    split_frames,
    to_db,
    to_raw,
    toggle_state,
)

from .conftest import SOUNDBAR_SETTINGS

TEMESCAL_FRAME = bytes.fromhex(
    "1000000050fbdb29fa856e2ffb675f092da2cee213884246d09c8ce003b98de0743fdc90e29d6171f08fca1119b316a9"
    "38973a44f43648044800650119a34a4c27a41837d393f9161eafe05e75c7dd115aab7f89b3"
)
WOOFER = next(level for level in LEVELS if level.key == "woofer")


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


def test_levels_convert_between_steps_and_db() -> None:
    rng = LevelRange(-15, 6)
    assert to_db(0, rng) == -15
    assert to_db(13, rng) == -2
    assert to_db(21, rng) == 6
    assert to_raw(-15, rng) == 0
    assert to_raw(-2.4, rng) == 13
    assert to_raw(6, rng) == 21


@pytest.mark.parametrize("db", [-16, 7])
def test_to_raw_rejects_values_outside_the_range(db: float) -> None:
    with pytest.raises(ValueError):
        to_raw(db, LevelRange(-15, 6))


def test_toggle_state_reads_booleans_only() -> None:
    night = TOGGLES[0]
    assert toggle_state({"b_night_time": True}, night) is True
    assert toggle_state({"b_night_time": 1}, night) is None
    assert toggle_state({}, night) is None
