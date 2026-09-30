"""Check geometry against a known transform and cover empty-feature inputs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import cv2
import numpy as np
import pytest

from alignment import align_and_stitch
from harris_corner import explore_harris_parameters
from ratio_test import experiment_ratio_test


@pytest.fixture
def image_pair(tmp_path):
    rng = np.random.default_rng(42)
    gray = rng.integers(0, 256, (480, 640), dtype=np.uint8)
    gray = cv2.GaussianBlur(gray, (3, 3), 0.8)
    source = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    expected_h = np.array([
        [0.97, 0.03, 18.0],
        [-0.02, 1.01, 12.0],
        [0.00008, -0.00006, 1.0],
    ])
    target = cv2.warpPerspective(source, expected_h, (700, 520), borderValue=(180, 180, 180))
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    assert cv2.imwrite(str(a), source)
    assert cv2.imwrite(str(b), target)
    return str(a), str(b), expected_h, target


def test_harris_parameter_effects(tmp_path):
    # Mixed-contrast corners exercise the quality threshold; closely spaced
    # square corners exercise minDistance independently of the quality setting.
    image = np.zeros((200, 240, 3), dtype=np.uint8)
    for row, brightness in enumerate((50, 100, 160, 255)):
        for col in range(6):
            x, y = 10 + col * 35, 10 + row * 45
            cv2.rectangle(image, (x, y), (x + 10, y + 10), (brightness,) * 3, -1)
    image_path = tmp_path / "corners.png"
    assert cv2.imwrite(str(image_path), image)
    output = tmp_path / "harris"
    result = explore_harris_parameters(str(image_path), output)
    base, high_quality, large_distance = [entry["corner_count"] for entry in result["scenarios"]]
    assert 0 < high_quality < base
    assert 0 < large_distance < base
    for path in output.glob("*.jpg"):
        annotated = cv2.imread(str(path))
        assert annotated.shape == image.shape
        assert np.any(annotated[:, :, 2].astype(int) - annotated[:, :, 0] > 100)


def test_ratio_counts_are_monotonic_and_outputs_exist(image_pair, tmp_path):
    a, b, _, _ = image_pair
    output = tmp_path / "ratio"
    result = experiment_ratio_test(a, b, output)
    counts = result["match_counts"]
    assert 20 < counts[0] <= counts[1] <= counts[2] <= result["two_neighbor_pairs"]
    expected = [f"task2_ratio_{threshold}.jpg" for threshold in (0.6, 0.75, 0.9)]
    expected.append("task2_ratio_curve.png")
    for filename in expected:
        assert cv2.imread(str(output / filename)) is not None


def test_alignment_recovers_known_geometry_and_preserves_uncovered_pixels(image_pair, tmp_path):
    a, b, expected_h, target = image_pair
    output = tmp_path / "alignment"
    result = align_and_stitch(a, b, output)
    assert result is not None
    assert result["inlier_count"] > 20
    assert result["inlier_ratio"] > 0.8
    assert result["inlier_reprojection_mean_px"] < 1.0
    # Independent ground-truth points detect reversed H or swapped x/y axes.
    probes = np.float32([[50, 50], [590, 50], [590, 430], [50, 430], [320, 240]]).reshape(-1, 1, 2)
    predicted = cv2.perspectiveTransform(probes, np.asarray(result["homography_a_to_b"]))
    expected = cv2.perspectiveTransform(probes, expected_h)
    assert np.linalg.norm(predicted - expected, axis=2).max() < 1.0
    overlay = cv2.imread(str(output / "task3_final_overlay.jpg"))
    warped = cv2.imread(str(output / "task3_warped_img1.jpg"))
    assert overlay.shape == warped.shape == target.shape
    assert cv2.imread(str(output / "task3_inlier_matches.jpg")) is not None
    # The rightmost strip is outside the source image and must keep B's tone.
    assert np.abs(overlay[:, -20:].astype(float) - target[:, -20:]).mean() < 2.0


def test_featureless_images_are_handled_without_opencv_errors(tmp_path):
    blank_path = tmp_path / "blank.png"
    assert cv2.imwrite(str(blank_path), np.zeros((128, 128, 3), dtype=np.uint8))
    blank = str(blank_path)
    result = explore_harris_parameters(blank, tmp_path / "harris")
    assert all(entry["corner_count"] == 0 for entry in result["scenarios"])
    assert experiment_ratio_test(blank, blank, tmp_path / "ratio") is None
    assert align_and_stitch(blank, blank, tmp_path / "alignment") is None


@pytest.mark.parametrize("task", [experiment_ratio_test, align_and_stitch])
def test_missing_images_return_failure(task, tmp_path):
    missing = str(tmp_path / "missing.png")
    assert task(missing, missing, tmp_path / "output") is None


@pytest.mark.parametrize("missing_input", [False, True])
def test_cli_uses_its_own_directory_and_reports_completion(image_pair, tmp_path, missing_input):
    a, b, _, _ = image_pair
    lab = tmp_path / "lab"
    assets = lab / "assets"
    assets.mkdir(parents=True)
    for filename in ("main.py", "harris_corner.py", "ratio_test.py", "alignment.py"):
        shutil.copyfile(Path(__file__).parent / filename, lab / filename)
    for filename, source in (
        ("image1.png", a), ("image2_a.png", a), ("image2_b.png", b),
        ("image3_a.png", a), ("image3_b.png", b),
    ):
        if missing_input and filename == "image3_b.png":
            continue
        shutil.copyfile(source, assets / filename)
    env = {**os.environ, "MPLCONFIGDIR": str(lab / "output" / ".matplotlib")}
    run = subprocess.run(
        [sys.executable, str(lab / "main.py")], cwd=tmp_path,
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert run.returncode == (1 if missing_input else 0), run.stdout + run.stderr
    summary = json.loads((lab / "output" / "experiment_summary.json").read_text(encoding="utf-8"))
    assert summary["success"] is (not missing_input)
    assert (summary["task3"] is None) is missing_input
    assert not (tmp_path / "output").exists()
    expected = {
        "task1_harris_base.jpg", "task1_harris_high_quality.jpg", "task1_harris_large_distance.jpg",
        "task2_ratio_0.6.jpg", "task2_ratio_0.75.jpg", "task2_ratio_0.9.jpg", "task2_ratio_curve.png",
    }
    if not missing_input:
        expected.update({"task3_inlier_matches.jpg", "task3_warped_img1.jpg", "task3_final_overlay.jpg"})
    images = {path.name for path in (lab / "output").iterdir() if path.suffix in {".png", ".jpg"}}
    assert images == expected
    for filename in expected:
        assert cv2.imread(str(lab / "output" / filename)) is not None
