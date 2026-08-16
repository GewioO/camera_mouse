"""
Forearm rotation feature extractor for the sklearn-based rotation classifier.

Takes a BGR frame + landmark dict (from ForearmTracker) and returns a 51-d vector:
  [0 :24]  HSV mean values in a 4×2 spatial grid (3 channels × 8 cells) — colour/texture
           (S, V per-patch normalized; H left absolute — see extract_features)
  [24:48]  Row-wise mean brightness along the perpendicular axis, per-patch normalized
  [48:51]  Skin-mask top-half fraction, bottom-half fraction, asymmetry  — balance

The ROI is extracted by rotating the frame so the forearm is horizontal,
then cropping a fixed rectangle centred on the elbow–wrist midpoint.
"""
import math
import cv2
import numpy as np

_SKIN_LOWER1 = np.array([0,   20,  60], dtype=np.uint8)
_SKIN_UPPER1 = np.array([20,  150, 255], dtype=np.uint8)
_SKIN_LOWER2 = np.array([170, 20,  60], dtype=np.uint8)
_SKIN_UPPER2 = np.array([180, 150, 255], dtype=np.uint8)

_ROI_ALONG = 0.88   # fraction of forearm length captured along axis
_ROI_PERP  = 0.35   # fraction captured on each side perpendicular to axis
_PATCH_W   = 64     # fixed patch width  (along forearm after rotation)
_PATCH_H   = 24     # fixed patch height (perpendicular to forearm)

FEATURE_DIM = 51


def extract_roi_patch(frame: np.ndarray, landmarks: dict) -> np.ndarray | None:
    """
    Rotate frame to make the forearm horizontal and crop a fixed-size patch.

    Returns uint8 BGR array of shape (_PATCH_H, _PATCH_W, 3), or None on failure.
    """
    if not landmarks:
        return None
    ex, ey = landmarks["elbow"]["x"], landmarks["elbow"]["y"]
    wx, wy = landmarks["wrist"]["x"], landmarks["wrist"]["y"]
    dx, dy = wx - ex, wy - ey
    length = math.sqrt(dx * dx + dy * dy)
    if length < 30:
        return None

    cx, cy = (ex + wx) / 2.0, (ey + wy) / 2.0
    angle  = math.degrees(math.atan2(dy, dx))
    fh, fw = frame.shape[:2]
    M       = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    rotated = cv2.warpAffine(frame, M, (fw, fh), flags=cv2.INTER_LINEAR)

    half_l = int(length * _ROI_ALONG / 2)
    half_h = int(length * _ROI_PERP)
    cxi, cyi = int(round(cx)), int(round(cy))
    x1 = max(0, cxi - half_l);  x2 = min(fw, cxi + half_l)
    y1 = max(0, cyi - half_h);  y2 = min(fh, cyi + half_h)

    roi = rotated[y1:y2, x1:x2]
    if roi.size == 0 or roi.shape[0] < 8 or roi.shape[1] < 8:
        return None
    return cv2.resize(roi, (_PATCH_W, _PATCH_H), interpolation=cv2.INTER_AREA)


def extract_features(frame: np.ndarray, landmarks: dict) -> np.ndarray | None:
    """
    Extract a FEATURE_DIM-d float32 feature vector, or None if extraction fails.
    """
    patch = extract_roi_patch(frame, landmarks)
    if patch is None:
        return None

    hsv_u8 = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    hsv    = hsv_u8.astype(np.float32)
    gray   = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY).astype(np.float32)
    s_mean, s_std = hsv[:, :, 1].mean(), hsv[:, :, 1].std() + 1e-6
    v_mean, v_std = hsv[:, :, 2].mean(), hsv[:, :, 2].std() + 1e-6
    g_mean, g_std = gray.mean(), gray.std() + 1e-6

    # ── Feature 1: HSV grid (4 cols × 2 rows, 3 channels) = 24 values ────────
    ch, cw = _PATCH_H // 2, _PATCH_W // 4  # 12, 16
    grid = []
    for gy in range(2):
        for gx in range(4):
            cell = hsv[gy*ch:(gy+1)*ch, gx*cw:(gx+1)*cw]
            grid += [cell[:, :, 0].mean() / 180.0,                # H — absolute, unaffected by exposure
                     (cell[:, :, 1].mean() - s_mean) / s_std,     # S — per-patch normalized
                     (cell[:, :, 2].mean() - v_mean) / v_std]     # V — per-patch normalized

    # ── Feature 2: row-wise brightness (perpendicular profile), normalized = 24 values ───
    row_profile = (gray.mean(axis=1) - g_mean) / g_std   # shape (_PATCH_H,) = (24,)

    # ── Feature 3: skin-mask balance = 3 values ───────────────────────────────
    skin = cv2.bitwise_or(
        cv2.inRange(hsv_u8, _SKIN_LOWER1, _SKIN_UPPER1),
        cv2.inRange(hsv_u8, _SKIN_LOWER2, _SKIN_UPPER2),
    ).astype(np.float32) / 255.0
    top  = float(skin[:ch, :].mean())
    bot  = float(skin[ch:, :].mean())
    asym = (top - bot) / (top + bot + 1e-6)

    return np.concatenate([
        np.array(grid, dtype=np.float32),              # 24
        row_profile.astype(np.float32),                # 24
        np.array([top, bot, asym], dtype=np.float32),  # 3
    ])  # total: 51
