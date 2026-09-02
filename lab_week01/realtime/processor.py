"""Framework-independent RGB frame processing for real-time applications."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import cv2
import numpy as np

from .registry import FilterRegistry


class RealtimeProcessingError(RuntimeError):
    """Base exception for a frame that cannot be processed safely."""


class FrameContractError(RealtimeProcessingError):
    """Raised when an input or filter output violates the stream contract."""


class UnknownFilterError(RealtimeProcessingError):
    """Raised when a client requests an unregistered filter."""


@dataclass(frozen=True)
class ProcessingMetrics:
    filter_key: str
    filter_label: str
    width: int
    height: int
    processing_ms: float
    estimated_max_fps: float

    def display_text(self) -> str:
        return (
            f"Filter: {self.filter_label} | "
            f"Frame: {self.width}x{self.height} | "
            f"Processing: {self.processing_ms:.1f} ms | "
            f"Compute ceiling: {self.estimated_max_fps:.1f} FPS"
        )


@dataclass(frozen=True)
class ProcessedFrame:
    image_rgb: np.ndarray
    metrics: ProcessingMetrics


class RealtimeFrameProcessor:
    """Apply registered BGR filters to RGB frames from a web client."""

    def __init__(self, registry: FilterRegistry | None = None):
        self.registry = registry or FilterRegistry.default()

    @staticmethod
    def _validate_rgb_frame(frame: np.ndarray, source: str) -> None:
        if not isinstance(frame, np.ndarray):
            raise FrameContractError(f"{source} must be a NumPy array")
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise FrameContractError(f"{source} must have shape H x W x 3")
        if frame.shape[0] < 1 or frame.shape[1] < 1:
            raise FrameContractError(f"{source} cannot be empty")
        if frame.dtype != np.uint8:
            raise FrameContractError(f"{source} must use uint8 pixels")

    def process(self, frame_rgb: np.ndarray, filter_key: str) -> ProcessedFrame:
        """Transform one RGB frame while preserving shape, dtype, and input data."""

        self._validate_rgb_frame(frame_rgb, "Input frame")
        definition = self.registry.get(filter_key)
        if definition is None:
            available = ", ".join(self.registry.keys())
            raise UnknownFilterError(
                f"Unknown filter '{filter_key}'. Available filters: {available}"
            )

        start = perf_counter()
        # Browser/Gradio frames are RGB; the original lab filters are BGR.
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        try:
            result_bgr = definition.transform(frame_bgr)
        except Exception as exc:
            raise RealtimeProcessingError(
                f"Filter '{filter_key}' failed: {exc}"
            ) from exc

        self._validate_rgb_frame(result_bgr, f"Output from '{filter_key}'")
        if result_bgr.shape != frame_bgr.shape:
            raise FrameContractError(
                f"Filter '{filter_key}' changed frame shape from "
                f"{frame_bgr.shape} to {result_bgr.shape}"
            )

        result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
        result_rgb = np.ascontiguousarray(result_rgb)
        processing_ms = (perf_counter() - start) * 1000.0
        estimated_max_fps = 1000.0 / max(processing_ms, 0.001)

        metrics = ProcessingMetrics(
            filter_key=definition.key,
            filter_label=definition.label,
            width=int(frame_rgb.shape[1]),
            height=int(frame_rgb.shape[0]),
            processing_ms=processing_ms,
            estimated_max_fps=estimated_max_fps,
        )
        return ProcessedFrame(image_rgb=result_rgb, metrics=metrics)
