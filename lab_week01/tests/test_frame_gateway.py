from __future__ import annotations

import base64

import cv2
import numpy as np

from lab_week01.realtime.frame_gateway import BrowserFrameGateway
from lab_week01.realtime.profiles import get_stream_profile
from lab_week01.realtime.telemetry import FrameCadenceTracker


def to_data_url(frame_rgb: np.ndarray) -> str:
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    success, encoded = cv2.imencode(".jpg", frame_bgr)
    assert success
    payload = base64.b64encode(encoded.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{payload}"


def from_data_url(value: str) -> np.ndarray:
    raw = base64.b64decode(value.partition(",")[2])
    frame_bgr = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert frame_bgr is not None
    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


def test_gateway_advances_sequence_and_returns_each_new_frame() -> None:
    times = iter([0.0, 0.125])
    gateway = BrowserFrameGateway(
        profile=get_stream_profile("low-latency"),
        cadence=FrameCadenceTracker(clock=times.__next__),
    )
    first = np.full((240, 320, 3), (220, 20, 20), dtype=np.uint8)
    second = np.full((240, 320, 3), (20, 20, 220), dtype=np.uint8)

    first_result = gateway.process_frame(to_data_url(first), "original")
    second_result = gateway.process_frame(to_data_url(second), "original")

    assert first_result["ok"] is True
    assert second_result["ok"] is True
    assert first_result["sequence"] == 1
    assert second_result["sequence"] == 2
    assert second_result["observed_fps"] == 8.0
    first_output = from_data_url(str(first_result["image_data_url"]))
    second_output = from_data_url(str(second_result["image_data_url"]))
    assert not np.array_equal(first_output, second_output)
    assert first_output[:, :, 0].mean() > first_output[:, :, 2].mean()
    assert second_output[:, :, 2].mean() > second_output[:, :, 0].mean()


def test_gateway_bounds_oversized_portrait_response() -> None:
    gateway = BrowserFrameGateway(profile=get_stream_profile("low-latency"))
    portrait = np.zeros((1280, 720, 3), dtype=np.uint8)

    result = gateway.process_frame(to_data_url(portrait), "grayscale")
    output = from_data_url(str(result["image_data_url"]))

    assert result["ok"] is True
    assert output.shape == (240, 135, 3)


def test_gateway_rejects_invalid_or_oversized_payload_without_crashing() -> None:
    gateway = BrowserFrameGateway(
        profile=get_stream_profile("low-latency"), max_payload_chars=100
    )

    wrong_type = gateway.process_frame("not-a-data-url", "original")
    oversized = gateway.process_frame("data:image/jpeg;base64," + "A" * 101, "original")

    assert wrong_type["ok"] is False
    assert oversized["ok"] is False


def test_gateway_returns_filter_error_as_stable_response() -> None:
    gateway = BrowserFrameGateway(profile=get_stream_profile("low-latency"))
    frame = np.zeros((20, 20, 3), dtype=np.uint8)

    result = gateway.process_frame(to_data_url(frame), "missing")

    assert result["ok"] is False
    assert "Unknown filter" in str(result["error"])
