"""Uniform video-file and camera frame source."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np


class VideoSourceError(RuntimeError):
    """Raised when a camera or video file cannot be opened or decoded."""


@dataclass(frozen=True)
class VideoMetadata:
    source: str
    width: int
    height: int
    fps: float
    frame_count: int


@dataclass(frozen=True)
class FramePacket:
    index: int
    timestamp_ms: float
    image: np.ndarray


class VideoSource:
    """Context-managed iterator over decoded frames."""

    def __init__(self, source: str | Path | int):
        self.source = source
        self._capture: cv2.VideoCapture | None = None
        self.metadata: VideoMetadata | None = None

    def open(self) -> "VideoSource":
        if isinstance(self.source, Path):
            resolved_source: str | int = str(self.source)
        else:
            resolved_source = self.source

        capture = cv2.VideoCapture(resolved_source)
        if not capture.isOpened():
            capture.release()
            raise VideoSourceError(f"Unable to open video source: {resolved_source}")

        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

        if width <= 0 or height <= 0:
            capture.release()
            raise VideoSourceError("Video source returned an invalid frame size")

        self._capture = capture
        self.metadata = VideoMetadata(
            source=str(resolved_source),
            width=width,
            height=height,
            fps=fps if fps > 0 else 15.0,
            frame_count=max(frame_count, 0),
        )
        return self

    def frames(self, max_frames: int = 0) -> Iterator[FramePacket]:
        if self._capture is None or self.metadata is None:
            raise VideoSourceError("Video source must be opened before reading")

        index = 0
        while max_frames <= 0 or index < max_frames:
            ok, frame = self._capture.read()
            if not ok:
                break
            timestamp_ms = float(self._capture.get(cv2.CAP_PROP_POS_MSEC))
            if timestamp_ms <= 0:
                timestamp_ms = index * 1000.0 / self.metadata.fps
            yield FramePacket(index=index, timestamp_ms=timestamp_ms, image=frame)
            index += 1

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self) -> "VideoSource":
        return self.open()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
