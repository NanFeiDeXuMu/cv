"""Small, thread-safe measurements for diagnosing frame delivery cadence."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock
from time import perf_counter
from typing import Callable


@dataclass(frozen=True)
class CadenceSnapshot:
    sequence: int
    observed_fps: float


class FrameCadenceTracker:
    """Track handler arrivals over a rolling window without buffering frames."""

    def __init__(
        self,
        *,
        window_size: int = 20,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        if window_size < 2:
            raise ValueError("window_size must be at least 2")
        self._timestamps: deque[float] = deque(maxlen=window_size)
        self._clock = clock
        self._sequence = 0
        self._lock = Lock()

    def observe(self) -> CadenceSnapshot:
        with self._lock:
            self._sequence += 1
            self._timestamps.append(self._clock())
            if len(self._timestamps) < 2:
                observed_fps = 0.0
            else:
                elapsed = self._timestamps[-1] - self._timestamps[0]
                observed_fps = (len(self._timestamps) - 1) / max(elapsed, 0.001)
            return CadenceSnapshot(self._sequence, observed_fps)
