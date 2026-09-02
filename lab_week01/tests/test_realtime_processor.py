from __future__ import annotations

import numpy as np
import pytest

from lab_week01.filters import get_filter_info
from lab_week01.realtime.processor import (
    FrameContractError,
    RealtimeFrameProcessor,
    UnknownFilterError,
)
from lab_week01.realtime.registry import FilterRegistry


def test_default_registry_exposes_original_and_lab_filters() -> None:
    registry = FilterRegistry.default()

    assert registry.keys() == (
        "original",
        "vintage_warm",
        "cool_tone",
        "high_contrast",
        "faded",
        "grayscale",
    )
    assert registry.choices()[0] == ("Original", "original")


def test_all_filters_preserve_realtime_frame_contract() -> None:
    processor = RealtimeFrameProcessor()
    generator = np.random.default_rng(42)
    frame = generator.integers(0, 256, (120, 160, 3), dtype=np.uint8)
    original = frame.copy()

    for filter_key in processor.registry.keys():
        result = processor.process(frame, filter_key)

        assert result.image_rgb.shape == frame.shape
        assert result.image_rgb.dtype == np.uint8
        assert result.image_rgb.flags.c_contiguous
        assert result.metrics.filter_key == filter_key
        assert result.metrics.processing_ms >= 0

    assert np.array_equal(frame, original), "Processing must not mutate input frames"


def test_original_returns_equal_but_independent_frame() -> None:
    processor = RealtimeFrameProcessor()
    frame = np.full((8, 12, 3), (20, 40, 200), dtype=np.uint8)

    result = processor.process(frame, "original")

    assert np.array_equal(result.image_rgb, frame)
    assert not np.shares_memory(result.image_rgb, frame)


def test_rgb_bgr_adapter_preserves_red_as_red() -> None:
    processor = RealtimeFrameProcessor()
    red_rgb = np.zeros((12, 12, 3), dtype=np.uint8)
    red_rgb[:, :, 0] = 220

    result = processor.process(red_rgb, "vintage_warm")

    red_mean = result.image_rgb[:, :, 0].mean()
    blue_mean = result.image_rgb[:, :, 2].mean()
    assert red_mean > blue_mean


def test_realtime_results_match_existing_batch_filters() -> None:
    processor = RealtimeFrameProcessor()
    generator = np.random.default_rng(9)
    frame_bgr = generator.integers(0, 256, (48, 64, 3), dtype=np.uint8)
    frame_rgb = frame_bgr[:, :, ::-1].copy()

    for filter_key, info in get_filter_info().items():
        expected_bgr = info["function"](frame_bgr)
        realtime_rgb = processor.process(frame_rgb, filter_key).image_rgb
        realtime_bgr = realtime_rgb[:, :, ::-1]

        assert np.array_equal(realtime_bgr, expected_bgr), filter_key


@pytest.mark.parametrize(
    "bad_frame",
    [
        np.zeros((10, 10), dtype=np.uint8),
        np.zeros((10, 10, 4), dtype=np.uint8),
        np.zeros((10, 10, 3), dtype=np.float32),
    ],
)
def test_invalid_frame_contract_is_rejected(bad_frame: np.ndarray) -> None:
    with pytest.raises(FrameContractError):
        RealtimeFrameProcessor().process(bad_frame, "original")


def test_unknown_filter_is_rejected() -> None:
    frame = np.zeros((10, 10, 3), dtype=np.uint8)

    with pytest.raises(UnknownFilterError):
        RealtimeFrameProcessor().process(frame, "does-not-exist")
