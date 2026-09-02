"""Tunable transport profiles for snapshot-based Webcam streaming.

The filters are fast, but every Gradio Webcam frame still crosses the network
as an encoded image.  A profile keeps capture cadence, payload dimensions, and
queue capacity consistent instead of scattering those values through the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import cv2
import numpy as np


@dataclass(frozen=True)
class StreamProfile:
    """Performance envelope for one real-time streaming mode."""

    key: str
    label: str
    width: int
    height: int
    target_fps: float
    time_limit_seconds: int = 30
    concurrency_limit: int = 4
    queue_size: int = 8

    def __post_init__(self) -> None:
        if self.width < 1 or self.height < 1:
            raise ValueError("Stream dimensions must be positive")
        if self.target_fps <= 0:
            raise ValueError("target_fps must be positive")
        if self.time_limit_seconds < 1:
            raise ValueError("time_limit_seconds must be positive")
        if self.concurrency_limit < 1 or self.queue_size < 1:
            raise ValueError("Queue limits must be positive")

    @property
    def stream_every(self) -> float:
        """Seconds between snapshots requested by the Gradio client."""

        return 1.0 / self.target_fps

    def webcam_constraints(self) -> dict[str, object]:
        """Browser hints that keep the camera stream inside this envelope."""

        return {
            "facingMode": "user",
            "width": {"ideal": self.width},
            "height": {"ideal": self.height},
            "frameRate": {"ideal": self.target_fps, "max": self.target_fps},
        }

    def resize_to_fit(self, frame_rgb: np.ndarray) -> np.ndarray:
        """Downscale oversized frames while preserving aspect ratio.

        Browser media constraints are preferences on some devices.  This
        server-side guard also bounds filter and response-encoding work when a
        phone ignores those preferences.
        """

        # Let RealtimeFrameProcessor produce the established contract error for
        # malformed values instead of failing here with an unrelated shape error.
        if not isinstance(frame_rgb, np.ndarray) or frame_rgb.ndim < 2:
            return frame_rgb
        height, width = frame_rgb.shape[:2]
        scale = min(self.width / width, self.height / height, 1.0)
        if scale == 1.0:
            return frame_rgb
        resized_width = max(1, round(width * scale))
        resized_height = max(1, round(height * scale))
        return cv2.resize(
            frame_rgb,
            (resized_width, resized_height),
            interpolation=cv2.INTER_AREA,
        )


STREAM_PROFILES: Mapping[str, StreamProfile] = {
    "low-latency": StreamProfile(
        key="low-latency",
        label="Low latency",
        width=320,
        height=240,
        target_fps=8.0,
    ),
    "balanced": StreamProfile(
        key="balanced",
        label="Balanced",
        width=480,
        height=360,
        target_fps=6.0,
    ),
    "quality": StreamProfile(
        key="quality",
        label="Quality",
        width=640,
        height=480,
        target_fps=4.0,
    ),
}

DEFAULT_STREAM_PROFILE = "low-latency"


def get_stream_profile(key: str = DEFAULT_STREAM_PROFILE) -> StreamProfile:
    """Resolve a named profile and fail with an actionable message."""

    try:
        return STREAM_PROFILES[key]
    except KeyError as exc:
        available = ", ".join(STREAM_PROFILES)
        raise ValueError(
            f"Unknown stream profile '{key}'. Available profiles: {available}"
        ) from exc
