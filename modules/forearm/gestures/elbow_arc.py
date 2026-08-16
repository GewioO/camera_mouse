"""
Elbow-arc gesture — LEFT / RIGHT swing of the elbow while the forearm tip stays
put. This is the validated mode-switch DOF for the forearm module (see the
memory note `forearm-interaction-features` and the dev probe
`scripts/test_elbow_back.py`, on which every threshold below was tuned against
real webcam data, 2026-08-15).

Pipeline (all magnitude thresholds are FRACTIONS OF FOREARM LENGTH, so the
gesture is scale/zoom/distance invariant):

  1. Forearm frame: axis = EMA of unit(wrist-elbow); perp = 90° of it. The
     elbow's offset from a neutral "center" is decomposed into perp (=left/right)
     and along (=back/fwd, exposed only as debug — a confirmed-weak DOF).
  2. Neutral center = SPEED-GATED EMA of the elbow: converges fast when the arm
     is at rest, barely moves while a stroke is in motion. (Position-gating it
     gets STUCK, since the along-axis offset stays large while the arm is raised.)
  3. Peak-of-excursion detection: an excursion runs from leaving center
     (|perp| >= exc_out) to returning (|perp| < exc_ret); on return it emits ONE
     stroke = sign(peak), only if |peak| >= fire. This rejects the small passive
     overshoot (~0.05-0.08) that an early-threshold trigger fired on.
  4. Tip-stationarity gate: reject if the tip moved >= wrist_max * elbow motion
     during the excursion — that's the whole arm TRANSLATING, not an arc.
  5. Directional refractory: cooldown_same frames before another same-direction
     stroke; cooldown_opp (longer) before the opposite — the return from a big
     arc swings the elbow past neutral into a real opposite arc ~1s later.
  6. Optional neutral-dwell arming (require_dwell > 0): only count a stroke if the
     arm rested near center for that many frames first. Eliminates ALL backlash
     for a deliberate single-switch use, but is unusable for continuous rapid
     arcing (there is no rest between strokes) — leave 0 for the latter.

Output modes:
  CONTINUOUS  -> value = signed perp offset (fraction of forearm length; +right)
  GESTURE/MODE-> event = pos_event/neg_event ("RIGHT"/"LEFT") on a valid stroke
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import GestureModule, GestureResult, OutputMode, point, visibility, norm


@dataclass
class ElbowArcConfig:
    output: OutputMode = OutputMode.GESTURE

    # ── forearm-frame smoothing / neutral tracking ──
    axis_ema: float = 0.85       # forearm-axis EMA (stable perpendicular)
    still_speed: float = 2.0     # px/frame; below this the elbow is "at rest"
    center_still: float = 0.85   # neutral EMA retention when still (fast converge)
    center_move: float = 0.995   # neutral EMA retention when moving (no drift)

    # ── excursion / peak detection (fractions of forearm length) ──
    exc_out: float = 0.04        # excursion starts when |perp| exceeds this
    exc_ret: float = 0.03        # ...and ends (return to center) below this
    fire: float = 0.10           # emit only if the excursion PEAK reached this

    # ── tip-stationarity gate ──
    wrist_max: float = 0.6       # reject if tip moved >= this * elbow motion

    # ── refractory (frames) ──
    cooldown_same: int = 25      # same-direction lockout
    cooldown_opp: int = 40       # opposite-direction lockout (return-swing guard)

    # ── optional deliberate-only arming ──
    require_dwell: int = 0       # frames of rest near center before a stroke arms
                                 # (0 = off; use for continuous arcing)

    # ── validity / naming ──
    require_wrist_live: bool = False   # a real residual-limb wrist is a reprojected
                                       # fallback, so DON'T require live by default
    wrist_live_min: float = 0.65
    pos_event: str = "RIGHT"     # sign(peak) > 0
    neg_event: str = "LEFT"      # sign(peak) < 0

    @classmethod
    def from_dict(cls, d: dict | None) -> "ElbowArcConfig":
        if not d:
            return cls()
        known = {f: d[f] for f in cls.__dataclass_fields__ if f in d}
        if "output" in known:
            known["output"] = OutputMode(known["output"])
        return cls(**known)


class ElbowArcDetector(GestureModule):
    _required = ("elbow", "wrist")

    def __init__(self, config: ElbowArcConfig | None = None):
        super().__init__(config or ElbowArcConfig())
        self.reset()

    def reset(self) -> None:
        super().reset()
        self._ema_ax = None
        self._base_elbow = None
        self._prev_elbow = None
        self._in_exc = False
        self._peak = 0.0
        self._el0 = self._wr0 = None       # elbow/wrist at excursion start
        self._el_pk = self._wr_pk = None   # elbow/wrist at the perp peak
        self._last_fire = -10 ** 9
        self._last_dir = None
        self._rest_run = 0                 # consecutive frames near center
        self._armed = False

    def _process(self, landmarks: dict, frame_shape) -> GestureResult:
        c = self.config
        elbow = point(landmarks, "elbow")
        wrist = point(landmarks, "wrist")

        v = wrist - elbow
        flen = float(np.hypot(*v))
        if flen <= 1:
            return GestureResult(active=False)

        axis = v / flen
        self._ema_ax = axis if self._ema_ax is None else \
            norm(c.axis_ema * self._ema_ax + (1 - c.axis_ema) * axis)
        perp_hat = np.array([-self._ema_ax[1], self._ema_ax[0]])

        # speed-gated neutral center
        if self._base_elbow is None:
            self._base_elbow = elbow.copy()
        speed = 0.0 if self._prev_elbow is None else float(np.hypot(*(elbow - self._prev_elbow)))
        self._prev_elbow = elbow.copy()
        a = c.center_still if speed < c.still_speed else c.center_move
        self._base_elbow = a * self._base_elbow + (1 - a) * elbow

        eoff = elbow - self._base_elbow
        perp_frac = float(eoff @ perp_hat) / flen      # + = right, - = left
        back_frac = float(eoff @ (-self._ema_ax)) / flen  # + = backward (weak/unused)

        # CONTINUOUS: just expose the signed offset, no discrete gating
        if c.output is OutputMode.CONTINUOUS:
            return GestureResult(value=perp_frac, active=True,
                                 debug=self._debug(perp_frac, back_frac, flen))

        # ── discrete excursion / peak detector (GESTURE / MODE) ──────────────
        if abs(perp_frac) < c.exc_ret:
            self._rest_run += 1
        else:
            self._rest_run = 0

        event = None
        if not self._in_exc:
            if abs(perp_frac) >= c.exc_out:
                self._in_exc = True
                self._peak = perp_frac
                self._el0 = elbow.copy(); self._wr0 = wrist.copy()
                self._el_pk = elbow.copy(); self._wr_pk = wrist.copy()
                self._armed = self._rest_run >= c.require_dwell
        else:
            if abs(perp_frac) > abs(self._peak):
                self._peak = perp_frac
                self._el_pk = elbow.copy(); self._wr_pk = wrist.copy()
            if abs(perp_frac) < c.exc_ret:                    # returned to center
                event = self._finish_excursion(landmarks)
                self._in_exc = False
                self._peak = 0.0

        return GestureResult(event=event, active=self._in_exc,
                             debug=self._debug(perp_frac, back_frac, flen))

    def _finish_excursion(self, landmarks) -> str | None:
        c = self.config
        if abs(self._peak) < c.fire:
            return None
        if c.require_wrist_live and visibility(landmarks, "wrist") < c.wrist_live_min:
            return None
        if not self._armed:                                   # no neutral dwell
            return None

        d_el = float(np.hypot(*(self._el_pk - self._el0)))
        d_wr = float(np.hypot(*(self._wr_pk - self._wr0)))
        if d_el <= 1 or d_wr / d_el >= c.wrist_max:           # arm translated
            return None

        direction = c.pos_event if self._peak > 0 else c.neg_event
        cool = c.cooldown_same if direction == self._last_dir else c.cooldown_opp
        if self._frame_n - self._last_fire < cool:            # refractory
            return None

        self._last_fire = self._frame_n
        self._last_dir = direction
        return direction

    def _debug(self, perp_frac, back_frac, flen) -> dict:
        return {
            "perp_frac": round(perp_frac, 3),
            "back_frac": round(back_frac, 3),
            "in_exc": self._in_exc,
            "exc_peak": round(self._peak, 3),
            "flen": round(flen, 1),
            "rest_run": self._rest_run,
        }
