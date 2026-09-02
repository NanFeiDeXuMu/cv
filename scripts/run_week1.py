"""Run the VisionTrace Week 1 video-inspection pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from visiontrace.config import load_config
from visiontrace.pipeline import run_week1_pipeline


def parse_source(value: str) -> str | int:
    return int(value) if value.isdigit() else value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "week1.yaml",
    )
    parser.add_argument(
        "--source",
        type=parse_source,
        help="Optional path or integer camera index overriding the YAML source.",
    )
    args = parser.parse_args()

    config = load_config(args.config, project_root=PROJECT_ROOT)
    summary = run_week1_pipeline(config, source_override=args.source)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
