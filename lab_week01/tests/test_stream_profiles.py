from __future__ import annotations

import numpy as np
import pytest

from lab_week01.realtime.profiles import StreamProfile, get_stream_profile


def test_low_latency_profile_matches_capture_and_stream_cadence() -> None:
    profile = get_stream_profile("low-latency")
    constraints = profile.webcam_constraints()

    assert profile.stream_every == pytest.approx(0.125)
    assert constraints["width"] == {"ideal": 320}
    assert constraints["height"] == {"ideal": 240}
    assert constraints["frameRate"] == {"ideal": 8.0, "max": 8.0}


def test_profile_downscales_without_distorting_aspect_ratio() -> None:
    profile = get_stream_profile("low-latency")
    portrait = np.zeros((1280, 720, 3), dtype=np.uint8)

    resized = profile.resize_to_fit(portrait)

    assert resized.shape == (240, 135, 3)


def test_profile_does_not_copy_a_frame_that_is_already_small() -> None:
    profile = get_stream_profile("balanced")
    frame = np.zeros((240, 320, 3), dtype=np.uint8)

    assert profile.resize_to_fit(frame) is frame


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 0},
        {"height": 0},
        {"target_fps": 0},
        {"time_limit_seconds": 0},
        {"concurrency_limit": 0},
        {"queue_size": 0},
    ],
)
def test_invalid_profile_is_rejected(kwargs: dict[str, int]) -> None:
    values = {
        "key": "test",
        "label": "Test",
        "width": 320,
        "height": 240,
        "target_fps": 8,
    }
    values.update(kwargs)

    with pytest.raises(ValueError):
        StreamProfile(**values)


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="Available profiles"):
        get_stream_profile("missing")
