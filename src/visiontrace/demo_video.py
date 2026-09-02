"""Deterministic tabletop production-line video generator for Week 1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class DemoProduct:
    product_id: str
    start_time: float
    color_bgr: tuple[int, int, int]
    label_present: bool = True
    scratch_present: bool = False


PRODUCTS = (
    DemoProduct("A-001", 0.8, (180, 150, 70)),
    DemoProduct("A-002", 5.2, (70, 80, 210), scratch_present=True),
    DemoProduct("A-003", 9.6, (70, 180, 90), label_present=False),
)


def generate_demo_video(
    output_path: str | Path,
    width: int = 640,
    height: int = 360,
    fps: float = 15.0,
    duration_seconds: float = 15.0,
) -> dict[str, int | float | str]:
    """Generate a repeatable simulated line with three separated products."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        raise RuntimeError(f"Unable to create demo video: {path}")

    total_frames = round(duration_seconds * fps)
    speed_pixels_per_second = 140.0
    product_width = 100
    product_height = 96
    product_y = 142

    try:
        for frame_index in range(total_frames):
            time_seconds = frame_index / fps
            frame = np.full((height, width, 3), (34, 40, 46), dtype=np.uint8)

            cv2.rectangle(frame, (0, 105), (width, 285), (78, 84, 90), -1)
            for belt_x in range(-40, width + 40, 80):
                moving_x = int((belt_x + time_seconds * 30) % (width + 80)) - 40
                cv2.line(frame, (moving_x, 112), (moving_x, 278), (95, 101, 106), 2)

            cv2.line(frame, (0, 104), (width, 104), (165, 165, 165), 3)
            cv2.line(frame, (0, 286), (width, 286), (165, 165, 165), 3)

            for product in PRODUCTS:
                elapsed = time_seconds - product.start_time
                if elapsed < 0:
                    continue
                product_x = int(-110 + elapsed * speed_pixels_per_second)
                if product_x > width:
                    continue

                top_left = (product_x, product_y)
                bottom_right = (
                    product_x + product_width,
                    product_y + product_height,
                )
                cv2.rectangle(frame, top_left, bottom_right, product.color_bgr, -1)
                cv2.rectangle(frame, top_left, bottom_right, (225, 225, 225), 2)

                if product.label_present:
                    cv2.rectangle(
                        frame,
                        (product_x + 18, product_y + 24),
                        (product_x + 82, product_y + 66),
                        (235, 235, 235),
                        -1,
                    )
                    cv2.putText(
                        frame,
                        product.product_id,
                        (product_x + 23, product_y + 51),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.42,
                        (35, 35, 35),
                        1,
                        cv2.LINE_AA,
                    )

                if product.scratch_present:
                    cv2.line(
                        frame,
                        (product_x + 8, product_y + 82),
                        (product_x + 91, product_y + 12),
                        (235, 235, 235),
                        3,
                    )

            cv2.putText(
                frame,
                "VisionTrace | Week 1 simulated line",
                (18, 34),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.72,
                (245, 245, 245),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                f"t={time_seconds:05.2f}s",
                (width - 120, 34),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.56,
                (210, 210, 210),
                1,
                cv2.LINE_AA,
            )
            writer.write(frame)
    finally:
        writer.release()

    return {
        "path": str(path.resolve()),
        "width": width,
        "height": height,
        "fps": fps,
        "duration_seconds": duration_seconds,
        "frame_count": total_frames,
        "product_count": len(PRODUCTS),
    }
