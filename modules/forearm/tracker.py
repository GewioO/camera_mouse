import math
import cv2
import mediapipe as mp

# MediaPipe Pose landmark indices.
# The frame is already flipped horizontally in VideoThread (mirror effect),
# so the user's anatomical RIGHT arm appears on the image's RIGHT side.
# MediaPipe was trained on standard (non-mirrored) front-facing images where
# the right body side appears on the image's LEFT — so with our flipped frame
# MediaPipe's LEFT landmarks correspond to the user's anatomical RIGHT arm.
ARM_IDS = {
    "right": {"shoulder": 11, "elbow": 13, "wrist": 15},  # MP LEFT  = user RIGHT
    "left":  {"shoulder": 12, "elbow": 14, "wrist": 16},  # MP RIGHT = user LEFT
}

_MIN_VISIBILITY = 0.5
# shoulder is only used for the guide-line drawing — elbow+wrist alone are
# enough for angle/rotation/ROI features, so a below-elbow close-up crop
# (shoulder out of frame) must still count as valid landmarks.
# elbow is the ONE hard requirement — MediaPipe tracks it far more reliably
# than wrist at close range / unusual rotations, and (unlike wrist) it still
# corresponds to a real joint on a below-elbow residual limb.
_REQUIRED = ("elbow",)
# Confidence bar to trust a live wrist reading enough to remember it as the
# elbow->wrist vector for later fallback (see `_resolve_wrist`).
_CALIB_MIN_VISIBILITY = 0.65
_SMOOTH         = 0.6   # EMA factor: higher = smoother but slower response

_COLOR_SHOULDER   = (200, 200, 255)
_COLOR_ELBOW      = (0, 200, 255)
_COLOR_WRIST      = (0, 255, 100)
_COLOR_LINE_ARM   = (180, 180, 255)
_COLOR_LINE_STUMP = (0, 255, 100)
_COLOR_LINE_CALIB = (0, 140, 255)   # wrist is a reprojected/calibrated estimate, not a live reading


def read_side_landmarks(landmarks, shape, ids: dict, *, require_wrist_visibility: bool = True) -> dict | None:
    """
    Extract {shoulder,elbow,wrist} points for one arm (`ids` = one of the
    dicts in `ARM_IDS`) from raw MediaPipe pose landmarks. Standalone so
    callers that need to test both arms against the same frame (e.g. the
    dataset trainer, which may hold frames of either arm) don't need a
    full ForearmTracker per side.

    require_wrist_visibility=False bypasses the confidence gate for wrist
    only (elbow — the one _REQUIRED landmark — still always needs it):
    MediaPipe emits an x/y for every landmark regardless of confidence (see
    `ForearmTracker.calibrate()`), and the live tracker's low-visibility wrist
    handling (reproject a calibrated elbow->wrist vector — `_resolve_wrist`)
    has no equivalent for an isolated static training image, so callers
    without that fallback (the dataset trainer) should take the raw reading
    rather than silently drop the frame.
    """
    h, w = shape[:2]
    pts = {}
    for name, idx in ids.items():
        lm = landmarks[idx]
        skip_gate = name == "wrist" and not require_wrist_visibility
        if lm.visibility < _MIN_VISIBILITY and not skip_gate:
            if name in _REQUIRED:
                return None
            continue  # optional (shoulder) — just omit it, don't invalidate the frame
        pts[name] = {
            "x": int(lm.x * w),
            "y": int(lm.y * h),
            "visibility": float(lm.visibility),
        }
    if not all(name in pts for name in _REQUIRED):
        return None
    return pts


class ForearmTracker:
    def __init__(self, side: str = "right"):
        if side not in ARM_IDS:
            raise ValueError(f"side must be 'right' or 'left', got {side!r}")
        self.side = side
        self._ids = ARM_IDS[side]

        # smooth_landmarks=False so _raw contains truly unsmoothed coordinates
        # for velocity-based gesture detection; EMA is applied manually below.
        self._pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=False,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        self._landmarks: dict | None = None
        self._smoothed:  dict | None = None
        self._raw:       dict | None = None

        # Last confident elbow->wrist vector (px), reprojected onto the current
        # elbow when the live wrist reading is missing/unreliable — see
        # `_resolve_wrist` and `calibrate()`.
        self._last_vec: tuple[float, float] | None = None
        self._raw_mp_landmarks = None   # unfiltered MediaPipe output, for calibrate()
        self._last_shape = None

    def find_pose(self, frame, draw: bool = True):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._pose.process(rgb)

        self._raw_mp_landmarks = results.pose_landmarks.landmark if results.pose_landmarks else None
        self._last_shape = frame.shape[:2]

        raw = None
        if results.pose_landmarks:
            raw = self._read_side(results.pose_landmarks.landmark, frame.shape)

        self._raw = raw
        if raw is None:
            self._smoothed = None
        else:
            self._smoothed = self._smooth(raw)
            if not self._resolve_wrist(self._smoothed):
                self._smoothed = None

        self._landmarks = self._smoothed

        if draw and self._landmarks:
            self._draw_arm(frame)
        return frame

    def get_landmarks(self, frame_w: int = None, frame_h: int = None) -> dict | None:
        return self._landmarks

    def is_wrist_live(self) -> bool:
        """True if the current wrist point is a confident live MediaPipe reading,
        False if it's a reprojected/calibrated fallback (or there's no pose at all)."""
        if self._landmarks is None:
            return False
        return self._landmarks["wrist"]["visibility"] >= _CALIB_MIN_VISIBILITY

    def get_forearm_angle(self, frame_w: int = None, frame_h: int = None) -> float | None:
        pts = self._landmarks
        if not pts:
            return None
        dx = pts["wrist"]["x"] - pts["elbow"]["x"]
        dy = pts["wrist"]["y"] - pts["elbow"]["y"]
        return math.degrees(math.atan2(dy, dx))

    def get_raw_wrist_y(self) -> int | None:
        """Raw (unsmoothed) wrist Y — used for velocity-based gesture detection."""
        return self._raw["wrist"]["y"] if self._raw else None

    def calibrate(self) -> bool:
        """
        Manually (re)capture the elbow->wrist vector from the most recent
        MediaPipe output, ignoring the visibility gate.

        Use this when the automatic high-confidence capture in `_resolve_wrist`
        never fires — e.g. no real hand/wrist present (an actual below-elbow
        residual limb), so MediaPipe's wrist visibility never clears
        `_CALIB_MIN_VISIBILITY` on its own. The caller (a human) is asserting
        "this is a good neutral reading right now" — MediaPipe still emits an
        x/y for every landmark regardless of its confidence score.

        Returns False if there's currently no pose / elbow at all to anchor to.
        """
        if self._raw_mp_landmarks is None or self._smoothed is None or self._last_shape is None:
            return False
        h, w = self._last_shape
        elbow_lm = self._raw_mp_landmarks[self._ids["elbow"]]
        wrist_lm = self._raw_mp_landmarks[self._ids["wrist"]]
        ex, ey = elbow_lm.x * w, elbow_lm.y * h
        wx, wy = wrist_lm.x * w, wrist_lm.y * h
        if math.hypot(wx - ex, wy - ey) < 20:
            return False
        self._last_vec = (wx - ex, wy - ey)
        return True

    def close(self):
        self._pose.close()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _read_side(self, landmarks, shape) -> dict | None:
        return read_side_landmarks(landmarks, shape, self._ids)

    def _resolve_wrist(self, pts: dict) -> bool:
        """
        Trust a confident live wrist reading and remember it for later fallback;
        otherwise reproject the last confident/calibrated elbow->wrist vector
        onto the CURRENT (live-tracked) elbow. Mutates `pts` in place.

        Reprojected wrists get visibility=0.0 so callers (HUD/`_draw_arm`) can
        tell "estimated" apart from "actually tracked this frame".

        Returns False if no wrist estimate — live or calibrated — exists at all.
        """
        elbow = pts["elbow"]
        wrist = pts.get("wrist")

        if wrist is not None and wrist["visibility"] >= _CALIB_MIN_VISIBILITY:
            self._last_vec = (wrist["x"] - elbow["x"], wrist["y"] - elbow["y"])
            return True

        if self._last_vec is not None:
            vx, vy = self._last_vec
            pts["wrist"] = {"x": elbow["x"] + vx, "y": elbow["y"] + vy, "visibility": 0.0}
            return True

        return wrist is not None   # low-confidence live reading, no fallback yet — use it anyway

    def _smooth(self, new_pts: dict) -> dict:
        if self._smoothed is None:
            return new_pts
        result = {}
        for key, val in new_pts.items():
            prev = self._smoothed.get(key)
            if prev is None:
                result[key] = val  # first time this landmark appears — no history to blend
                continue
            result[key] = {
                "x": int(prev["x"] * _SMOOTH + val["x"] * (1 - _SMOOTH)),
                "y": int(prev["y"] * _SMOOTH + val["y"] * (1 - _SMOOTH)),
                "visibility": val["visibility"],
            }
        return result

    def _draw_arm(self, frame):
        pts = self._landmarks
        e = (pts["elbow"]["x"], pts["elbow"]["y"])
        w = (pts["wrist"]["x"], pts["wrist"]["y"])
        live_wrist = pts["wrist"]["visibility"] >= _CALIB_MIN_VISIBILITY
        wrist_color = _COLOR_LINE_STUMP if live_wrist else _COLOR_LINE_CALIB

        if "shoulder" in pts:
            s = (pts["shoulder"]["x"], pts["shoulder"]["y"])
            cv2.line(frame, s, e, _COLOR_LINE_ARM, 2)
            cv2.circle(frame, s, 6, _COLOR_SHOULDER, cv2.FILLED)

        cv2.arrowedLine(frame, e, w, wrist_color, 3, tipLength=0.25)
        cv2.circle(frame, e,  8,  _COLOR_ELBOW, cv2.FILLED)
        cv2.circle(frame, w,  10, _COLOR_WRIST if live_wrist else wrist_color, cv2.FILLED)
