from __future__ import annotations

from pathlib import Path

from visiontrace.config import load_config


def test_week1_config_resolves_project_paths() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "configs" / "week1.yaml", project_root=root)

    assert config.video.source == root / "assets" / "videos" / "week1_line_demo.mp4"
    assert config.output.directory == root / "outputs" / "week1"
    assert config.roi.x + config.roi.width <= 1.0
