"""End-to-end Week 1 processing pipeline."""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

import cv2

from .config import AppConfig
from .frame_analysis import (
    FrameAnalyzer,
    RoiOccupancyDetector,
    annotate_frame,
    crop_roi,
    normalized_roi_to_pixels,
)
from .video_source import VideoSource


def _prepare_output_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    samples = path / "samples"
    if samples.exists():
        shutil.rmtree(samples)
    samples.mkdir(parents=True, exist_ok=True)
    return samples


def run_week1_pipeline(
    config: AppConfig, source_override: str | Path | int | None = None
) -> dict[str, Any]:
    """Process a video, persist statistics, events, samples, and an overlay video."""

    source: str | Path | int = source_override or config.video.source
    output_directory = config.output.directory
    sample_directory = _prepare_output_directory(output_directory)
    statistics_path = output_directory / "frame_statistics.csv"
    events_path = output_directory / "roi_events.jsonl"
    summary_path = output_directory / "run_summary.json"
    annotated_video_path = output_directory / "annotated_demo.mp4"

    analyzer = FrameAnalyzer()
    activity = RoiOccupancyDetector(
        background_frames=config.analysis.background_frames,
        pixel_difference_threshold=config.analysis.pixel_difference_threshold,
        occupancy_ratio_threshold=config.analysis.occupancy_ratio_threshold,
        enter_confirm_frames=config.analysis.enter_confirm_frames,
        exit_confirm_frames=config.analysis.exit_confirm_frames,
    )

    events: list[dict[str, Any]] = []
    processed_frames = 0
    last_statistics: dict[str, Any] | None = None
    writer: cv2.VideoWriter | None = None

    with VideoSource(source) as video:
        assert video.metadata is not None
        metadata = video.metadata

        if config.output.save_annotated_video:
            writer = cv2.VideoWriter(
                str(annotated_video_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                metadata.fps,
                (metadata.width, metadata.height),
            )
            if not writer.isOpened():
                raise RuntimeError(f"Unable to create output video: {annotated_video_path}")

        try:
            with statistics_path.open("w", newline="", encoding="utf-8") as csv_file:
                csv_writer: csv.DictWriter[str] | None = None

                for packet in video.frames(max_frames=config.video.max_frames):
                    pixel_roi = normalized_roi_to_pixels(config.roi, packet.image)
                    roi_frame = crop_roi(packet.image, pixel_roi)
                    statistics = analyzer.analyze(
                        packet.image, packet.index, packet.timestamp_ms
                    )
                    occupancy = activity.update(roi_frame)

                    row = statistics.to_dict()
                    row["roi_change_ratio"] = occupancy.change_ratio
                    row["roi_occupied"] = occupancy.occupied
                    if csv_writer is None:
                        csv_writer = csv.DictWriter(csv_file, fieldnames=list(row.keys()))
                        csv_writer.writeheader()
                    csv_writer.writerow(row)

                    if occupancy.transition:
                        events.append(
                            {
                                "event": occupancy.transition,
                                "frame_index": packet.index,
                                "timestamp_ms": round(packet.timestamp_ms, 3),
                                "change_ratio": occupancy.change_ratio,
                            }
                        )

                    annotated = annotate_frame(
                        packet.image, pixel_roi, statistics, occupancy
                    )
                    if writer is not None:
                        writer.write(annotated)

                    if (
                        config.output.save_samples
                        and config.analysis.sample_every_n_frames > 0
                        and packet.index % config.analysis.sample_every_n_frames == 0
                    ):
                        sample_path = sample_directory / f"frame_{packet.index:05d}.jpg"
                        if not cv2.imwrite(str(sample_path), annotated):
                            raise RuntimeError(f"Unable to save sample frame: {sample_path}")

                    processed_frames += 1
                    last_statistics = row
        finally:
            if writer is not None:
                writer.release()

    with events_path.open("w", encoding="utf-8") as stream:
        for event in events:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")

    entered_count = sum(event["event"] == "ENTER" for event in events)
    exited_count = sum(event["event"] == "EXIT" for event in events)
    summary: dict[str, Any] = {
        "pipeline_version": "week1-v1",
        "source": asdict(metadata),
        "processed_frames": processed_frames,
        "processed_duration_seconds": round(processed_frames / metadata.fps, 3),
        "roi": asdict(config.roi),
        "events": {
            "enter_count": entered_count,
            "exit_count": exited_count,
            "items": events,
        },
        "last_frame_statistics": last_statistics,
        "artifacts": {
            "statistics_csv": str(statistics_path.resolve()),
            "events_jsonl": str(events_path.resolve()),
            "annotated_video": (
                str(annotated_video_path.resolve()) if writer is not None else None
            ),
            "samples_directory": str(sample_directory.resolve()),
        },
    }
    with summary_path.open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)

    return summary
