"""
Optional, lightweight wrapper around the RandomForest forearm-side classifier
trained by scripts/train_forearm_rotation.py (models/forearm_rotation_{side}.pkl).

Purely additive: it does NOT replace ForearmTracker.get_forearm_asymmetry()'s
rule-based state machine (still the only thing driving _run_forearm_loop's
tracked state) — it's just an extra HUD readout next to it.
"""
from pathlib import Path

from modules.forearm.feature_extractor import extract_features

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"


class RotationClassifier:
    def __init__(self, side: str = "right"):
        self._model = None
        self._classes = None
        path = MODEL_DIR / f"forearm_rotation_{side}.pkl"
        if not path.exists():
            print(f"[ML-ROT] no model at {path} — ML overlay disabled, rule-based state unaffected")
            return
        try:
            import joblib
            data = joblib.load(path)
            self._model = data["model"]
            self._classes = data["classes"]
            print(f"[ML-ROT] loaded {path}")
        except Exception as e:
            print(f"[ML-ROT] failed to load {path}: {e}")

    @property
    def available(self) -> bool:
        return self._model is not None

    def predict(self, frame, landmarks: dict | None) -> str | None:
        """Pass the ORIGINAL frame (before draw overlays) — same requirement
        as get_forearm_asymmetry(), since features are pixel-based."""
        if self._model is None or not landmarks:
            return None
        feats = extract_features(frame, landmarks)
        if feats is None:
            return None
        idx = int(self._model.predict(feats.reshape(1, -1))[0])
        return self._classes[idx]
