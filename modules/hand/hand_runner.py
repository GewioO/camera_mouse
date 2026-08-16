import cv2

from modules.base import ModuleRunner
from modules.hand.hand_tracker import HandTracker
from modules.hand.hand_controller import HandController
from core.display_overlay import DisplayOverlay

# Semantic controller events → HUD overlay (text, position, color, duration)
_HUD = {
    "click":        ("CLICK!",      (50, 50),  (0, 0, 255),   20),
    "double_click": ("DCLICK!",     (50, 80),  (255, 0, 255), 20),
    "drag_on":      ("DRAG ON",     (50, 110), (0, 255, 255), 20),
    "drag_off":     ("DRAG OFF",    (50, 110), (0, 165, 255), 20),
    "scroll_down":  ("SCROLL DWON", (50, 200), (0, 255, 0),   5),
    "scroll_up":    ("SCROLL UP",   (50, 230), (255, 255, 0), 5),
}


class HandRunner(ModuleRunner):
    """Hand module glue: MediaPipe Hands tracking + rendering"""

    def __init__(self, cli, json_manager, scale_controller):
        self.tracker = HandTracker(max_hands=1)
        self.overlay = DisplayOverlay(scale_controller)
        self.controller = HandController(cli.current_profile, json_manager)

    def process(self, frame):
        frame = self.tracker.find_hands(frame, draw=True)
        landmarks = self.tracker.get_hand_landmarks()

        w, h = frame.shape[1], frame.shape[0]
        center = self.tracker.get_hand_center(w, h) if landmarks else None
        result = self.controller.update(landmarks, center, w, h)

        if result.move_to:
            cv2.circle(frame, result.move_to, 12, (0, 255, 255), cv2.FILLED)
        for event in result.events:
            text, pos, color, duration = _HUD[event]
            self.overlay.add_ui_command(text, pos, color, duration=duration)

        self.overlay.draw(frame)
        return frame

    def close(self):
        self.controller.close()
        self.tracker.close()
