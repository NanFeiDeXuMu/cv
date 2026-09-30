import json
from importlib.metadata import version
from pathlib import Path
import platform

import cv2
import numpy as np

from harris_corner import explore_harris_parameters
from ratio_test import experiment_ratio_test
from alignment import align_and_stitch


def ensure_dirs():
    """Resolve inputs and outputs relative to this file, not the shell's cwd."""
    lab_dir = Path(__file__).resolve().parent
    assets_dir = lab_dir / "assets"
    output_dir = lab_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return assets_dir, output_dir


def main():
    assets_dir, output_dir = ensure_dirs()
    summary = {
        "environment": {
            "python": platform.python_version(),
            "opencv": cv2.__version__,
            "numpy": np.__version__,
            "matplotlib": version("matplotlib"),
        },
        "task1": explore_harris_parameters(str(assets_dir / "image1.png"), output_dir),
        "task2": experiment_ratio_test(
            str(assets_dir / "image2_a.png"), str(assets_dir / "image2_b.png"), output_dir
        ),
        "task3": align_and_stitch(
            str(assets_dir / "image3_a.png"), str(assets_dir / "image3_b.png"), output_dir
        ),
    }
    summary["success"] = all(summary[task] is not None for task in ("task1", "task2", "task3"))
    summary_path = output_dir / "experiment_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if not summary["success"]:
        print(f"\nLab incomplete. See the messages above and {summary_path}.")
        return 1
    print(f"\nLab execution finished. Results and statistics: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
