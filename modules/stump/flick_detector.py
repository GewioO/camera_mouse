# Detects a quick down-up flick gesture (like a reload motion).
# Logic: must drop >= _DOWN_PX pixels AND rise >= _UP_PX pixels,
# each phase within _MAX_FRAMES frames — slow movements time out.

_DOWN_PX      = 80   # minimum pixel drop to complete down phase
_UP_PX        = 60   # minimum pixel rise to complete up phase
_MAX_FRAMES   = 12   # max frames per phase (~0.4s at 30fps); slow moves time out
_ARM_UP_ANGLE = -40  # forearm angle must be negative (pointing up)


class FlickDetector:
    def __init__(self):
        self._prev_y: int | None = None
        self._phase = "idle"      # idle | down | up
        self._phase_start_y = 0
        self._frames = 0

    def update(self, wrist_y: int, angle: float | None) -> bool:
        """Call once per frame. Returns True when a flick is detected."""
        if self._prev_y is None:
            self._prev_y = wrist_y
            return False

        dy = wrist_y - self._prev_y   # positive = wrist moving down on screen
        self._prev_y = wrist_y

        if self._phase == "idle":
            arm_up = angle is not None and angle < _ARM_UP_ANGLE
            if arm_up and dy > 5:     # any downward motion while arm is up
                self._phase = "down"
                self._phase_start_y = wrist_y
                self._frames = 0

        elif self._phase == "down":
            self._frames += 1
            drop = wrist_y - self._phase_start_y
            if drop >= _DOWN_PX:      # dropped enough — now wait for the snap back
                self._phase = "up"
                self._phase_start_y = wrist_y
                self._frames = 0
            elif self._frames > _MAX_FRAMES:   # too slow — cancel
                self._phase = "idle"

        elif self._phase == "up":
            self._frames += 1
            rise = self._phase_start_y - wrist_y
            if rise >= _UP_PX:        # rose enough — flick confirmed
                self._phase = "idle"
                return True
            if self._frames > _MAX_FRAMES:     # too slow — cancel
                self._phase = "idle"

        return False

    def reset(self):
        self._prev_y = None
        self._phase = "idle"
        self._frames = 0
