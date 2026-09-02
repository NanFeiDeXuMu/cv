from __future__ import annotations

import numpy as np

from visiontrace.frame_analysis import FrameAnalyzer, RoiOccupancyDetector


def test_frame_analyzer_reports_bgr_matrix_statistics() -> None:
    frame = np.zeros((10, 20, 3), dtype=np.uint8)
    frame[:, :] = (10, 20, 30)

    stats = FrameAnalyzer().analyze(frame, frame_index=7, timestamp_ms=125.0)

    assert stats.height == 10
    assert stats.width == 20
    assert stats.channels == 3
    assert stats.dtype == "uint8"
    assert stats.blue_mean == 10.0
    assert stats.green_mean == 20.0
    assert stats.red_mean == 30.0


def test_roi_occupancy_detector_uses_confirmed_transitions() -> None:
    detector = RoiOccupancyDetector(
        background_frames=2,
        pixel_difference_threshold=10,
        occupancy_ratio_threshold=0.2,
        enter_confirm_frames=2,
        exit_confirm_frames=2,
    )
    clear = np.zeros((20, 20, 3), dtype=np.uint8)
    occupied = np.full((20, 20, 3), 255, dtype=np.uint8)

    detector.update(clear)
    calibrated = detector.update(clear)
    first_change = detector.update(occupied)
    entered = detector.update(occupied)
    first_clear = detector.update(clear)
    exited = detector.update(clear)

    assert calibrated.ready
    assert first_change.transition is None
    assert entered.transition == "ENTER"
    assert entered.occupied
    assert first_clear.transition is None
    assert exited.transition == "EXIT"
    assert not exited.occupied
