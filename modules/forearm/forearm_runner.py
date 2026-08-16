import cv2

from modules.base import ModuleRunner
from modules.forearm.tracker import ForearmTracker
from modules.forearm.forearm_controller import ForearmController


class ForearmRunner(ModuleRunner):
    """
    Forearm module glue: pose tracking + rendering
    """

    def __init__(self, side="right"):
        self.tracker = ForearmTracker(side=side)
        self.controller = ForearmController()

    def process(self, frame):
        frame = self.tracker.find_pose(frame, draw=True)
        landmarks = self.tracker.get_landmarks()
        angle = self.tracker.get_forearm_angle() if landmarks else None
        result = self.controller.update(landmarks, angle)

        if result.tracking:
            if result.angle is not None:
                cv2.putText(frame, f"angle: {result.angle:+.1f}", (10, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 100), 2)
        else:
            cv2.putText(frame, "NO TRACKING", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        return frame

    def close(self):
        self.controller.close()
        self.tracker.close()
