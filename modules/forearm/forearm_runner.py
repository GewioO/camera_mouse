import cv2

from modules.base import ModuleRunner
from modules.forearm.tracker import ForearmTracker


class ForearmRunner(ModuleRunner):
    """
    Minimal live loop: track the forearm (elbow->wrist anchor), draw it, and
    show the 2D forearm angle as a HUD readout.
    """

    def __init__(self, side="right"):
        self.tracker = ForearmTracker(side=side)

    def process(self, frame):
        frame = self.tracker.find_pose(frame, draw=True)
        landmarks = self.tracker.get_landmarks()

        if landmarks:
            angle = self.tracker.get_forearm_angle()
            if angle is not None:
                cv2.putText(frame, f"angle: {angle:+.1f}", (10, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 100), 2)
        else:
            cv2.putText(frame, "NO TRACKING", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        return frame

    def close(self):
        self.tracker.close()
