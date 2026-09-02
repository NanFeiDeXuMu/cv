from __future__ import annotations

import pytest

from lab_week01.realtime.telemetry import FrameCadenceTracker


def test_cadence_tracker_reports_sequence_and_rolling_fps() -> None:
    times = iter([0.0, 0.1, 0.2, 0.4])
    tracker = FrameCadenceTracker(window_size=3, clock=times.__next__)

    assert tracker.observe().sequence == 1
    assert tracker.observe().observed_fps == pytest.approx(10.0)
    assert tracker.observe().observed_fps == pytest.approx(10.0)
    final = tracker.observe()

    assert final.sequence == 4
    assert final.observed_fps == pytest.approx(2 / 0.3)


def test_cadence_window_must_hold_at_least_two_samples() -> None:
    with pytest.raises(ValueError):
        FrameCadenceTracker(window_size=1)
