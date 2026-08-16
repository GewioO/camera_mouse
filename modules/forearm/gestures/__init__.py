"""
Configurable forearm-gesture modules (Module 2).

Each gesture turns per-frame landmarks into discrete events or a continuous
value; actions are bound elsewhere (not here). Configure behaviour via each
module's dataclass `config` and its `output` (OutputMode).

  ElbowArcDetector    — left/right elbow arc (validated mode-switch DOF)
  ElbowAngleDetector  — flexion/extension angle (continuous DOF)

Both share the GestureModule contract: `update(landmarks, frame_shape)
-> GestureResult` and `reset()`.
"""
from .base import GestureModule, GestureResult, OutputMode
from .elbow_arc import ElbowArcDetector, ElbowArcConfig
from .elbow_angle import ElbowAngleDetector, ElbowAngleConfig

__all__ = [
    "GestureModule", "GestureResult", "OutputMode",
    "ElbowArcDetector", "ElbowArcConfig",
    "ElbowAngleDetector", "ElbowAngleConfig",
]
