import threading
from core.constants import SCALE_MIN, SCALE_MAX, DEFAULT_SCALE


class ScaleController:
    def __init__(self, initial: float = DEFAULT_SCALE):
        self._scale = initial
        self._lock = threading.Lock()

    def get(self) -> float:
        with self._lock:
            return self._scale

    def set(self, value: float) -> None:
        with self._lock:
            self._scale = round(max(SCALE_MIN, min(SCALE_MAX, value)), 1)

    def increment(self, delta: float) -> None:
        with self._lock:
            self._scale = round(max(SCALE_MIN, min(SCALE_MAX, self._scale + delta)), 1)
