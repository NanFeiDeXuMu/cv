from __future__ import annotations

from pathlib import Path

from visiontrace.config import load_config
from visiontrace.demo_video import generate_demo_video
from visiontrace.pipeline import run_week1_pipeline
from visiontrace.video_source import VideoSource


def test_generated_video_can_be_read(tmp_path: Path) -> None:
    video_path = tmp_path / "demo.mp4"
    metadata = generate_demo_video(
        video_path, width=320, height=180, fps=10.0, duration_seconds=2.0
    )

    with VideoSource(video_path) as source:
        frames = list(source.frames())

    assert metadata["frame_count"] == 20
    assert len(frames) == 20
    assert frames[0].image.shape == (180, 320, 3)


def test_pipeline_creates_auditable_artifacts(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    source_path = tmp_path / "line.mp4"
    generate_demo_video(source_path, fps=15.0, duration_seconds=6.0)

    config_text = (root / "configs" / "week1.yaml").read_text(encoding="utf-8")
    config_text = config_text.replace(
        "directory: outputs/week1", f"directory: {tmp_path.as_posix()}/output"
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_text, encoding="utf-8")
    config = load_config(config_path, project_root=root)

    summary = run_week1_pipeline(config, source_override=source_path)

    assert summary["processed_frames"] == 90
    assert Path(summary["artifacts"]["statistics_csv"]).exists()
    assert Path(summary["artifacts"]["events_jsonl"]).exists()
    assert Path(summary["artifacts"]["annotated_video"]).exists()
