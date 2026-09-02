"""Week 1 image-matrix, color-space, and ROI activity analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np

from .config import RoiConfig


@dataclass(frozen=True)
class PixelRoi:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1


@dataclass(frozen=True)
class FrameStatistics:
    frame_index: int
    timestamp_ms: float
    height: int
    width: int
    channels: int
    dtype: str
    blue_mean: float
    green_mean: float
    red_mean: float
    brightness_mean: float
    contrast_std: float
    hue_mean: float
    saturation_mean: float

    def to_dict(self) -> dict[str, int | float | str]:
        return asdict(self)


@dataclass(frozen=True)
class OccupancyResult:
    ready: bool
    occupied: bool
    change_ratio: float
    transition: str | None = None


def normalized_roi_to_pixels(config: RoiConfig, frame: np.ndarray) -> PixelRoi:
    height, width = frame.shape[:2]
    x1 = max(0, min(width - 1, round(config.x * width)))
    y1 = max(0, min(height - 1, round(config.y * height)))
    x2 = max(x1 + 1, min(width, round((config.x + config.width) * width)))
    y2 = max(y1 + 1, min(height, round((config.y + config.height) * height)))
    return PixelRoi(x1=x1, y1=y1, x2=x2, y2=y2)


def crop_roi(frame: np.ndarray, roi: PixelRoi) -> np.ndarray:
    return frame[roi.y1 : roi.y2, roi.x1 : roi.x2]


class FrameAnalyzer:
    """Extract interpretable matrix and color-space statistics from a frame."""

    def analyze(
        self, frame: np.ndarray, frame_index: int, timestamp_ms: float
    ) -> FrameStatistics:
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("Expected a BGR image with shape H x W x 3")

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        blue_mean, green_mean, red_mean, _ = cv2.mean(frame)

        return FrameStatistics(
            frame_index=frame_index,
            timestamp_ms=round(float(timestamp_ms), 3),
            height=int(frame.shape[0]),
            width=int(frame.shape[1]),
            channels=int(frame.shape[2]),
            dtype=str(frame.dtype),
            blue_mean=round(float(blue_mean), 3),
            green_mean=round(float(green_mean), 3),
            red_mean=round(float(red_mean), 3),
            brightness_mean=round(float(gray.mean()), 3),
            contrast_std=round(float(gray.std()), 3),
            hue_mean=round(float(hsv[:, :, 0].mean()), 3),
            saturation_mean=round(float(hsv[:, :, 1].mean()), 3),
        )


class RoiOccupancyDetector:
    """Detect ROI occupancy through image-matrix differencing and hysteresis."""

    def __init__(
        self,
        background_frames: int,
        pixel_difference_threshold: int,
        occupancy_ratio_threshold: float,
        enter_confirm_frames: int,
        exit_confirm_frames: int,
    ):
        self.background_frames = background_frames
        self.pixel_difference_threshold = pixel_difference_threshold
        self.occupancy_ratio_threshold = occupancy_ratio_threshold
        self.enter_confirm_frames = enter_confirm_frames
        self.exit_confirm_frames = exit_confirm_frames

        self._background_samples: list[np.ndarray] = []
        self._background: np.ndarray | None = None
        self._occupied = False
        self._candidate_count = 0

    @property
    def background_ready(self) -> bool:
        return self._background is not None

    def update(self, roi_bgr: np.ndarray) -> OccupancyResult:
        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)

        if self._background is None:
            self._background_samples.append(gray.astype(np.float32))
            if len(self._background_samples) >= self.background_frames:
                self._background = np.mean(self._background_samples, axis=0).astype(
                    np.uint8
                )
                self._background_samples.clear()
            return OccupancyResult(
                ready=self._background is not None,
                occupied=False,
                change_ratio=0.0,
            )

        difference = cv2.absdiff(gray, self._background)
        changed = difference >= self.pixel_difference_threshold
        change_ratio = float(changed.mean())
        candidate_occupied = change_ratio >= self.occupancy_ratio_threshold
        transition: str | None = None

        if candidate_occupied == self._occupied:
            self._candidate_count = 0
        else:
            self._candidate_count += 1
            required = (
                self.enter_confirm_frames
                if candidate_occupied
                else self.exit_confirm_frames
            )
            if self._candidate_count >= required:
                self._occupied = candidate_occupied
                transition = "ENTER" if self._occupied else "EXIT"
                self._candidate_count = 0

        return OccupancyResult(
            ready=True,
            occupied=self._occupied,
            change_ratio=round(change_ratio, 6),
            transition=transition,
        )


def annotate_frame(
    frame: np.ndarray,
    roi: PixelRoi,
    stats: FrameStatistics,
    occupancy: OccupancyResult,
) -> np.ndarray:
    """Create a presentation frame without mutating the source image."""

    annotated = frame.copy()
    if not occupancy.ready:
        color = (0, 215, 255)
        status = "CALIBRATING"
    elif occupancy.occupied:
        color = (0, 0, 255)
        status = "OCCUPIED"
    else:
        color = (0, 200, 0)
        status = "CLEAR"

    # Replace any source-video header with a single stable information bar.
    cv2.rectangle(annotated, (0, 0), (annotated.shape[1], 54), (24, 28, 32), -1)
    cv2.rectangle(annotated, (roi.x1, roi.y1), (roi.x2, roi.y2), color, 2)
    cv2.putText(
        annotated,
        f"ROI: {status}  change={occupancy.change_ratio:.3f}",
        (roi.x1, max(25, roi.y1 - 10)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        color,
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        annotated,
        (
            f"VisionTrace | frame={stats.frame_index}  "
            f"t={stats.timestamp_ms / 1000:.2f}s"
        ),
        (18, 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.68,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        annotated,
        (
            f"BGR mean=({stats.blue_mean:.0f}, {stats.green_mean:.0f}, "
            f"{stats.red_mean:.0f})  brightness={stats.brightness_mean:.1f}"
        ),
        (18, annotated.shape[0] - 18),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return annotated
