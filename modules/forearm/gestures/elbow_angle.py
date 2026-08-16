"""
Elbow-angle gesture — flexion / extension, the interior 2D angle
shoulder-elbow-wrist. Validated as a clean, monotonic, driftless DOF (~95%
forward-vs-back separation; forward/extend > neutral > back/flex — see the
memory note `stump-working-dof`). Naturally exists on a real below-elbow residual limb
(the elbow still flexes), unlike axial rotation.

Because the absolute angle depends on posture/camera, the useful signal is the
angle RELATIVE TO A CALIBRATED NEUTRAL. Call `calibrate()` while holding the
neutral pose (or let `auto_calibrate` seed it from the first stable reading).

Output modes:
  CONTINUOUS  -> value = smoothed (angle - neutral) in degrees (+ = extend)
  GESTURE/MODE-> event = extend_event / flex_event / neutral_event on a state
                 change of a 3-state threshold+hysteresis machine

Requires the shoulder landmark (for the angle vertex ray); returns inactive when
the shoulder is not available.
"""
from __future__ import annotations

from dataclasses import dataclass

from .base import (GestureModule, GestureResult, OutputMode,
                   point, visibility, interior_angle)


@dataclass
class ElbowAngleConfig:
    output: OutputMode = OutputMode.CONTINUOUS

    ema: float = 0.6             # angle smoothing (matches tracker _SMOOTH)
    sample_every: int = 1        # emit/update every N frames (user wanted ~10 for
                                 # cheaper, smoother sampling); still smoothed each frame

    # 3-state machine thresholds, in degrees RELATIVE TO NEUTRAL:
    extend_delta: float = 5.0    # (angle-neutral) above this -> extended
    flex_delta: float = -5.0     # below this -> flexed
    hysteresis: float = 2.0      # must fall this far back inside to leave a state

    shoulder_min_vis: float = 0.3  # shoulder confidence needed to trust the angle
    auto_calibrate: bool = True    # seed neutral from the first valid reading

    extend_event: str = "EXTEND"
    flex_event: str = "FLEX"
    neutral_event: str = "NEUTRAL"

    @classmethod
    def from_dict(cls, d: dict | None) -> "ElbowAngleConfig":
        if not d:
            return cls()
        known = {f: d[f] for f in cls.__dataclass_fields__ if f in d}
        if "output" in known:
            known["output"] = OutputMode(known["output"])
        return cls(**known)


class ElbowAngleDetector(GestureModule):
    _required = ("shoulder", "elbow", "wrist")

    def __init__(self, config: ElbowAngleConfig | None = None):
        super().__init__(config or ElbowAngleConfig())
        self.reset()

    def reset(self) -> None:
        super().reset()
        self._angle = None        # smoothed absolute angle
        self._neutral = None      # calibrated neutral angle
        self._state = "neutral"   # neutral | extend | flex
        self._last_value = None   # last sampled (angle-neutral)

    def calibrate(self) -> bool:
        """Set the current smoothed angle as neutral. Returns False if no reading."""
        if self._angle is None:
            return False
        self._neutral = self._angle
        return True

    def _process(self, landmarks: dict, frame_shape) -> GestureResult:
        c = self.config
        if visibility(landmarks, "shoulder") < c.shoulder_min_vis:
            return GestureResult(active=False)

        raw = interior_angle(point(landmarks, "shoulder"),
                             point(landmarks, "elbow"),
                             point(landmarks, "wrist"))
        self._angle = raw if self._angle is None else \
            c.ema * self._angle + (1 - c.ema) * raw
        if self._neutral is None and c.auto_calibrate:
            self._neutral = self._angle

        rel = self._angle - (self._neutral if self._neutral is not None else self._angle)

        # sample_every: only surface a value/event every N frames
        if c.sample_every > 1 and (self._frame_n % c.sample_every) != 0:
            return GestureResult(active=True, debug=self._debug(rel))

        if c.output is OutputMode.CONTINUOUS:
            self._last_value = rel
            return GestureResult(value=rel, active=True, debug=self._debug(rel))

        # GESTURE / MODE: 3-state threshold + hysteresis
        event = self._update_state(rel)
        return GestureResult(event=event, active=True, debug=self._debug(rel))

    def _update_state(self, rel: float) -> str | None:
        c = self.config
        new = self._state
        if self._state == "neutral":
            if rel >= c.extend_delta:
                new = "extend"
            elif rel <= c.flex_delta:
                new = "flex"
        elif self._state == "extend":
            if rel < c.extend_delta - c.hysteresis:
                new = "neutral"
        elif self._state == "flex":
            if rel > c.flex_delta + c.hysteresis:
                new = "neutral"
        if new == self._state:
            return None
        self._state = new
        return {"extend": c.extend_event, "flex": c.flex_event,
                "neutral": c.neutral_event}[new]

    def _debug(self, rel: float) -> dict:
        return {
            "angle": round(self._angle, 1) if self._angle is not None else None,
            "neutral": round(self._neutral, 1) if self._neutral is not None else None,
            "rel": round(rel, 1),
            "state": self._state,
        }
