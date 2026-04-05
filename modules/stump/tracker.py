import math
import cv2
from rtmlib import Body

# COCO keypoint indices — frame is flipped horizontally before inference,
# so COCO "left" keypoints correspond to the user's anatomical right arm.
_ARM_IDS = {
    "right": {"shoulder": 5, "elbow": 7, "wrist":  9},
    "left":  {"shoulder": 6, "elbow": 8, "wrist": 10},
}

_MIN_SCORE = 0.3
_SMOOTH    = 0.6  # EMA factor: higher = smoother but slower response

_COLOR_SHOULDER   = (200, 200, 255)
_COLOR_ELBOW      = (0, 200, 255)
_COLOR_WRIST      = (0, 255, 100)
_COLOR_LINE_ARM   = (180, 180, 255)
_COLOR_LINE_STUMP = (0, 255, 100)


class StumpTracker:
    def __init__(self, side: str = "right", mode: str = "lightweight", device: str = "cpu"):
        if side not in _ARM_IDS:
            raise ValueError(f"side must be 'right' or 'left', got {side!r}")
        self.side = side
        self._ids = _ARM_IDS[side]
        self._body = Body(mode=mode, to_openpose=False,
                          backend="onnxruntime", device=device)
        self._landmarks: dict | None = None
        self._smoothed: dict | None = None
        self._raw: dict | None = None

    def find_pose(self, frame, draw: bool = True):
        kps, scores = self._body(frame)

        raw = None
        if len(kps) > 0:
            raw = self._read_side(kps[0], scores[0])

        self._raw = raw
        if raw is None:
            self._smoothed = None
        else:
            self._smoothed = self._smooth(raw)

        self._landmarks = self._smoothed

        if draw and self._landmarks:
            self._draw_arm(frame)
        return frame

    def get_landmarks(self, frame_w: int = None, frame_h: int = None) -> dict | None:
        return self._landmarks

    def get_stump_angle(self, frame_w: int = None, frame_h: int = None) -> float | None:
        pts = self._landmarks
        if not pts:
            return None
        dx = pts["wrist"]["x"] - pts["elbow"]["x"]
        dy = pts["wrist"]["y"] - pts["elbow"]["y"]
        return math.degrees(math.atan2(dy, dx))

    def get_raw_wrist_y(self) -> int | None:
        """Raw (unsmoothed) wrist Y — use for velocity-based gesture detection."""
        return self._raw["wrist"]["y"] if self._raw else None

    def get_rotation(self) -> float | None:
        """Not available in 2D RTMPose — reserved for future implementation."""
        return None

    def close(self):
        pass

    # ── Internals ─────────────────────────────────────────────────────────────

    def _read_side(self, keypoints, scores) -> dict | None:
        pts = {}
        for name, idx in self._ids.items():
            s = float(scores[idx])
            if s < _MIN_SCORE:
                return None
            pts[name] = {"x": int(keypoints[idx][0]),
                         "y": int(keypoints[idx][1]),
                         "visibility": s}
        return pts

    def _smooth(self, new_pts: dict) -> dict:
        if self._smoothed is None:
            return new_pts
        result = {}
        for key, val in new_pts.items():
            prev = self._smoothed[key]
            result[key] = {
                "x": int(prev["x"] * _SMOOTH + val["x"] * (1 - _SMOOTH)),
                "y": int(prev["y"] * _SMOOTH + val["y"] * (1 - _SMOOTH)),
                "visibility": val["visibility"],
            }
        return result

    def _draw_arm(self, frame):
        pts = self._landmarks
        s = (pts["shoulder"]["x"], pts["shoulder"]["y"])
        e = (pts["elbow"]["x"],    pts["elbow"]["y"])
        w = (pts["wrist"]["x"],    pts["wrist"]["y"])

        cv2.line(frame, s, e, _COLOR_LINE_ARM, 2)
        cv2.arrowedLine(frame, e, w, _COLOR_LINE_STUMP, 3, tipLength=0.25)
        cv2.circle(frame, s,  6,  _COLOR_SHOULDER, cv2.FILLED)
        cv2.circle(frame, e,  8,  _COLOR_ELBOW,    cv2.FILLED)
        cv2.circle(frame, w,  10, _COLOR_WRIST,    cv2.FILLED)
