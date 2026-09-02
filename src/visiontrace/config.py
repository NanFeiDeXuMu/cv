"""Configuration loading and validation for the VisionTrace prototype."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class VideoConfig:
    source: Path
    camera_index: int = 0
    max_frames: int = 0


@dataclass(frozen=True)
class RoiConfig:
    x: float
    y: float
    width: float
    height: float

    def validate(self) -> None:
        values = (self.x, self.y, self.width, self.height)
        if not all(0.0 <= value <= 1.0 for value in values):
            raise ValueError("ROI values must be normalized to the range [0, 1]")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("ROI width and height must be positive")
        if self.x + self.width > 1.0 or self.y + self.height > 1.0:
            raise ValueError("ROI must stay inside the frame")


@dataclass(frozen=True)
class AnalysisConfig:
    background_frames: int = 10
    pixel_difference_threshold: int = 28
    occupancy_ratio_threshold: float = 0.08
    enter_confirm_frames: int = 3
    exit_confirm_frames: int = 3
    sample_every_n_frames: int = 30


@dataclass(frozen=True)
class OutputConfig:
    directory: Path
    save_annotated_video: bool = True
    save_samples: bool = True


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    video: VideoConfig
    roi: RoiConfig
    analysis: AnalysisConfig
    output: OutputConfig


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"Missing or invalid configuration section: {name}")
    return value


def load_config(path: str | Path, project_root: str | Path | None = None) -> AppConfig:
    """Load a YAML configuration and resolve all project-relative paths."""

    config_path = Path(path).resolve()
    root = Path(project_root).resolve() if project_root else _project_root()

    with config_path.open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream) or {}

    video_raw = _section(raw, "video")
    roi_raw = _section(raw, "roi")
    analysis_raw = _section(raw, "analysis")
    output_raw = _section(raw, "output")

    source = Path(str(video_raw["source"]))
    if not source.is_absolute():
        source = root / source

    output_directory = Path(str(output_raw["directory"]))
    if not output_directory.is_absolute():
        output_directory = root / output_directory

    roi = RoiConfig(
        x=float(roi_raw["x"]),
        y=float(roi_raw["y"]),
        width=float(roi_raw["width"]),
        height=float(roi_raw["height"]),
    )
    roi.validate()

    analysis = AnalysisConfig(
        background_frames=int(analysis_raw.get("background_frames", 10)),
        pixel_difference_threshold=int(
            analysis_raw.get("pixel_difference_threshold", 28)
        ),
        occupancy_ratio_threshold=float(
            analysis_raw.get("occupancy_ratio_threshold", 0.08)
        ),
        enter_confirm_frames=int(analysis_raw.get("enter_confirm_frames", 3)),
        exit_confirm_frames=int(analysis_raw.get("exit_confirm_frames", 3)),
        sample_every_n_frames=int(analysis_raw.get("sample_every_n_frames", 30)),
    )
    if analysis.background_frames < 1:
        raise ValueError("background_frames must be at least 1")
    if not 0.0 <= analysis.occupancy_ratio_threshold <= 1.0:
        raise ValueError("occupancy_ratio_threshold must be in [0, 1]")
    if analysis.enter_confirm_frames < 1 or analysis.exit_confirm_frames < 1:
        raise ValueError("confirmation frame counts must be at least 1")

    return AppConfig(
        project_root=root,
        video=VideoConfig(
            source=source,
            camera_index=int(video_raw.get("camera_index", 0)),
            max_frames=int(video_raw.get("max_frames", 0)),
        ),
        roi=roi,
        analysis=analysis,
        output=OutputConfig(
            directory=output_directory,
            save_annotated_video=bool(
                output_raw.get("save_annotated_video", True)
            ),
            save_samples=bool(output_raw.get("save_samples", True)),
        ),
    )
