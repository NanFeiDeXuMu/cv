"""Regression checks for geometry, supplied examples, diagnostics and CLI I/O."""
import importlib.util
import itertools
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np
import pytest

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("week03_scanner", BASE / "student_document_scanner.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DocumentScanner = module.DocumentScanner


@pytest.mark.parametrize("case", [1, 2, 3])
def test_supplied_images_produce_nonempty_document(case, tmp_path):
    scanner = DocumentScanner()
    result = scanner.scan_document(BASE / "asset" / f"case{case}.png")
    assert result.dtype == np.uint8 and result.ndim == 3
    assert min(result.shape[:2]) > 400
    assert len(np.unique(scanner.document_points, axis=0)) == 4
    assert cv2.isContourConvex(scanner.document_points)
    assert 0.30 < scanner.document_area / np.prod(scanner.original_image.shape[:2]) < 0.65
    output = tmp_path / "result.png"
    assert cv2.imwrite(str(output), result)
    np.testing.assert_array_equal(cv2.imread(str(output)), result)


def test_perspective_warp_preserves_corner_orientation_for_all_point_orders():
    # A synthetic trapezoid with distinct corner markers exposes mirroring,
    # rotations and incorrect corner correspondences without OCR assumptions.
    source = np.array([[50, 30], [240, 50], [260, 230], [20, 250]], np.float32)
    image = np.full((280, 300, 3), 180, np.uint8)
    colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0), (0, 255, 255)]
    for point, color in zip(source, colors):
        cv2.circle(image, tuple(point.astype(int)), 14, color, -1)
    scanner = DocumentScanner()
    for permutation in itertools.permutations(source):
        result = scanner.perspective_correction(image, np.array(permutation))
        for actual, expected in zip(
            [result[3, 3], result[3, -4], result[-4, -4], result[-4, 3]], colors
        ):
            np.testing.assert_allclose(actual, expected, atol=5)


def test_diamond_does_not_repeat_a_vertex():
    points = np.array([[100, 20], [180, 100], [100, 180], [20, 100]])
    ordered = DocumentScanner().order_points(points)
    assert len(np.unique(ordered, axis=0)) == 4
    assert cv2.isContourConvex(ordered)


def test_degenerate_vertices_are_rejected():
    with pytest.raises(ValueError, match="non-degenerate"):
        DocumentScanner().perspective_correction(
            np.zeros((100, 100, 3), np.uint8), np.zeros((4, 2))
        )


def test_blank_image_fails_and_clears_previous_result(tmp_path):
    scanner = DocumentScanner()
    scanner.scan_document(BASE / "asset" / "case1.png")
    blank = tmp_path / "blank.png"
    cv2.imwrite(str(blank), np.zeros((300, 300, 3), np.uint8))
    with pytest.raises(ValueError, match="contour not found"):
        scanner.scan_document(blank)
    assert scanner.processed_image is None
    assert scanner.document_points is None


def test_debug_display_receives_the_current_result(monkeypatch):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figures = []
    monkeypatch.setattr(plt, "show", lambda: figures.append(plt.gcf()))
    result = DocumentScanner().scan_document(
        BASE / "asset" / "case1.png", show_intermediate=True
    )
    displayed = figures[0].axes[4].images[0].get_array()
    np.testing.assert_array_equal(displayed, cv2.cvtColor(result, cv2.COLOR_BGR2RGB))


def test_cli_runs_outside_lab_directory(tmp_path):
    completed = subprocess.run(
        [sys.executable, "-B", str(BASE / "student_document_scanner.py")],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Completed: 3/3 test cases passed." in completed.stdout
    assert not (tmp_path / "output").exists()


def test_failed_image_write_causes_nonzero_status(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["student_document_scanner.py"])
    monkeypatch.setattr(module.cv2, "imwrite", lambda *args: False)
    assert module.main() == 1
    assert "Completed: 0/3 test cases passed." in capsys.readouterr().out
