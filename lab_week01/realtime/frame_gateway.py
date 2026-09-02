"""Validated data-URL gateway between a browser camera and the filter core."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from time import perf_counter

import cv2
import numpy as np

from .processor import RealtimeFrameProcessor, RealtimeProcessingError
from .profiles import StreamProfile, get_stream_profile
from .telemetry import FrameCadenceTracker

SUPPORTED_DATA_URL_PREFIXES = (
    "data:image/jpeg;base64,",
    "data:image/png;base64,",
    "data:image/webp;base64,",
)


class FramePayloadError(RealtimeProcessingError):
    """Raised when a browser frame cannot be decoded safely."""


@dataclass(frozen=True)
class GatewayFrame:
    image_data_url: str
    status: str
    sequence: int
    observed_fps: float
    server_ms: float
    output_bytes: int

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": True,
            "image_data_url": self.image_data_url,
            "status": self.status,
            "sequence": self.sequence,
            "observed_fps": self.observed_fps,
            "server_ms": self.server_ms,
            "output_bytes": self.output_bytes,
        }


class BrowserFrameGateway:
    """Decode, transform, and encode one latest-frame browser request.

    The browser transport deliberately permits only one in-flight call.  This
    class is therefore stateless with respect to image data: it never retains
    a previous frame and cannot build an obsolete-frame queue.
    """

    def __init__(
        self,
        processor: RealtimeFrameProcessor | None = None,
        profile: StreamProfile | None = None,
        cadence: FrameCadenceTracker | None = None,
        *,
        jpeg_quality: int = 70,
        max_payload_chars: int = 4_000_000,
        max_decoded_bytes: int = 3_000_000,
    ) -> None:
        if not 30 <= jpeg_quality <= 95:
            raise ValueError("jpeg_quality must be between 30 and 95")
        if max_payload_chars < 1 or max_decoded_bytes < 1:
            raise ValueError("Payload limits must be positive")
        self.processor = processor or RealtimeFrameProcessor()
        self.profile = profile or get_stream_profile()
        self.cadence = cadence or FrameCadenceTracker()
        self.jpeg_quality = jpeg_quality
        self.max_payload_chars = max_payload_chars
        self.max_decoded_bytes = max_decoded_bytes

    def process_frame(self, image_data_url: str, filter_key: str) -> dict[str, object]:
        """Gradio server-function entry point used by the browser component."""

        started = perf_counter()
        try:
            frame_rgb = self._decode_data_url(image_data_url)
            bounded_frame = self.profile.resize_to_fit(frame_rgb)
            result = self.processor.process(bounded_frame, filter_key)
            encoded, output_bytes = self._encode_jpeg(result.image_rgb)
            cadence = self.cadence.observe()
            server_ms = (perf_counter() - started) * 1000.0
            status = (
                f"Frame #{cadence.sequence} | Received {cadence.observed_fps:.1f} FPS | "
                f"Server {server_ms:.1f} ms | Filter "
                f"{result.metrics.processing_ms:.1f} ms | "
                f"{result.metrics.width}x{result.metrics.height}"
            )
            return GatewayFrame(
                image_data_url=encoded,
                status=status,
                sequence=cadence.sequence,
                observed_fps=cadence.observed_fps,
                server_ms=server_ms,
                output_bytes=output_bytes,
            ).as_dict()
        except RealtimeProcessingError as exc:
            return {"ok": False, "error": str(exc)}

    def _decode_data_url(self, value: str) -> np.ndarray:
        if not isinstance(value, str):
            raise FramePayloadError("Frame payload must be a data URL string")
        if len(value) > self.max_payload_chars:
            raise FramePayloadError("Frame payload exceeds the configured size limit")
        prefix = next(
            (candidate for candidate in SUPPORTED_DATA_URL_PREFIXES if value.startswith(candidate)),
            None,
        )
        if prefix is None:
            raise FramePayloadError("Frame payload must be a JPEG, PNG, or WebP data URL")
        try:
            encoded = value[len(prefix) :]
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise FramePayloadError("Frame payload contains invalid base64 data") from exc
        if len(raw) > self.max_decoded_bytes:
            raise FramePayloadError("Decoded frame exceeds the configured size limit")
        image_bgr = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image_bgr is None:
            raise FramePayloadError("Frame payload is not a decodable image")
        return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    def _encode_jpeg(self, frame_rgb: np.ndarray) -> tuple[str, int]:
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        success, buffer = cv2.imencode(
            ".jpg",
            frame_bgr,
            [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality],
        )
        if not success:
            raise FramePayloadError("Processed frame could not be encoded")
        raw = buffer.tobytes()
        encoded = base64.b64encode(raw).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}", len(raw)
