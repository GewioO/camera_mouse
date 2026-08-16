"""
Configurable forearm-gesture framework (Module 2).

Each gesture is a self-contained module that turns per-frame landmarks into
either discrete EVENTS or a CONTINUOUS scalar — and NOTHING more. Actions
(cursor / click / scroll / mode switch) are deliberately NOT bound here: a
separate controller decides what an event or value does. That keeps every
gesture reusable and lets the same gesture be repurposed just by config.

A gesture's `output` (see `OutputMode`) selects how its raw signal is exposed:

    GESTURE     discrete one-shot events  ("LEFT", "RIGHT", "FLICK", ...)
    CONTINUOUS  a scalar value every frame (angle, perpendicular offset, ...)
    MODE        discrete events meant to toggle/switch a mode (same shape as
                GESTURE; the distinction is semantic + lets a module enable
                extra robustness like a neutral-dwell requirement)

All modules share the `update(landmarks, frame_shape) -> GestureResult` contract
and a `reset()`. `landmarks` is the dict returned by `ForearmTracker.get_landmarks`
(keys "shoulder"/"elbow"/"wrist", each {"x","y","visibility"}), or None.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class OutputMode(str, Enum):
    GESTURE = "gesture"        # discrete one-shot events
    CONTINUOUS = "continuous"  # a scalar value each frame
    MODE = "mode"              # discrete events used as mode toggles/switches


@dataclass
class GestureResult:
    """What a gesture module reports for one frame."""
    event: str | None = None       # discrete event fired this frame (GESTURE/MODE)
    value: float | None = None     # continuous scalar this frame (CONTINUOUS)
    active: bool = False           # signal is valid / module is mid-gesture
    debug: dict = field(default_factory=dict)   # internals for HUD / tuning

    @property
    def fired(self) -> bool:
        return self.event is not None


class GestureModule(ABC):
    """Base class. Subclasses implement `_process`; the base handles the empty
    frame-shape/landmark guard and the internal frame counter."""

    def __init__(self, config):
        self.config = config
        self._frame_n = 0

    @abstractmethod
    def _process(self, landmarks: dict, frame_shape) -> GestureResult:
        """Compute this frame's result. `landmarks` is guaranteed non-None and to
        contain the module's required points (see `_required`)."""

    #: landmark names this module needs present (with usable coords)
    _required: tuple[str, ...] = ("elbow", "wrist")

    def update(self, landmarks: dict | None, frame_shape=None) -> GestureResult:
        self._frame_n += 1
        if landmarks is None or any(k not in landmarks for k in self._required):
            return GestureResult(active=False)
        return self._process(landmarks, frame_shape)

    def reset(self) -> None:
        """Clear all transient state (baselines, in-progress gestures)."""
        self._frame_n = 0


# ── small shared helpers ────────────────────────────────────────────────────
def point(landmarks: dict, name: str) -> np.ndarray:
    p = landmarks[name]
    return np.array([p["x"], p["y"]], dtype=float)


def visibility(landmarks: dict, name: str) -> float:
    return float(landmarks.get(name, {}).get("visibility", 0.0))


def norm(v: np.ndarray) -> np.ndarray:
    n = float(np.hypot(*v))
    return v / n if n > 1e-9 else v


def interior_angle(a: np.ndarray, vertex: np.ndarray, c: np.ndarray) -> float:
    """2D interior angle at `vertex` between rays vertex->a and vertex->c, degrees."""
    u, w = a - vertex, c - vertex
    du, dw = float(np.hypot(*u)), float(np.hypot(*w))
    if du < 1e-6 or dw < 1e-6:
        return 0.0
    cosv = max(-1.0, min(1.0, float(u @ w) / (du * dw)))
    return math.degrees(math.acos(cosv))
