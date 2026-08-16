import cv2

from modules.base import ModuleRunner
from modules.hand.hand_tracker import HandTracker
from modules.hand.preset_gestures import PresetGestures
from core.mouse_controller import MouseController
from core.display_overlay import DisplayOverlay
from core.constants import (
    FRAME_WIDTH, FRAME_HEIGHT, MOUSE_SMOOTHING,
    SCROLL_DECAY, SCROLL_AMOUNT, SCROLL_VELOCITY_STEP, COOLDOWN_FRAMES,
)

_ONE_SHOT_ACTIONS = {"click", "double_click", "drag"}
_CONTINUOUS_ACTIONS = {"scroll_down", "scroll_up"}


class HandRunner(ModuleRunner):
    """
    Hand module: MediaPipe Hands → gesture detection → mouse/scroll/drag,
    plus the transient HUD overlay
    """

    def __init__(self, cli, json_manager, scale_controller):
        self.json_manager = json_manager
        self.profile = cli.current_profile
        self.tracker = HandTracker(max_hands=1)
        self.mouse = MouseController(FRAME_WIDTH, FRAME_HEIGHT, smoothing=MOUSE_SMOOTHING)
        self.overlay = DisplayOverlay(scale_controller)

        self.scroll_velocity = 0
        self.drag_active = False
        self.gesture_was_active = {}
        self.action_cooldown = {}

    def process(self, frame):
        frame = self.tracker.find_hands(frame, draw=True)
        landmarks = self.tracker.get_hand_landmarks()

        if landmarks:
            self._handle_gestures(frame, landmarks)

        if abs(self.scroll_velocity) >= 1:
            self.mouse.scroll('down' if self.scroll_velocity > 0 else 'up', amount=SCROLL_AMOUNT)
            self.scroll_velocity *= SCROLL_DECAY

        self.overlay.draw(frame)
        return frame

    def _handle_gestures(self, frame, landmarks):
        gestures = PresetGestures(landmarks, frame.shape[1], frame.shape[0], self.json_manager)
        center_pos = self.tracker.get_hand_center(frame.shape[1], frame.shape[0])

        if center_pos and "mouse_move" in self.profile:
            self.mouse.smooth_move(center_pos[0], center_pos[1])
            cv2.circle(frame, center_pos, 12, (0, 255, 255), cv2.FILLED)

        for action, gesture_name in self.profile.items():
            if action == "mouse_move":
                continue

            if action in _ONE_SHOT_ACTIONS and self.action_cooldown.get(action, 0) > 0:
                self.action_cooldown[action] -= 1
                continue

            gesture_now = gestures.detect(gesture_name)
            edge_triggered = gesture_now and not self.gesture_was_active.get(action, False)
            self.gesture_was_active[action] = gesture_now

            if action in _ONE_SHOT_ACTIONS and edge_triggered:
                self.action_cooldown[action] = COOLDOWN_FRAMES
                if action == "click":
                    self.mouse.click('left')
                    self.overlay.add_ui_command("CLICK!", (50, 50), (0, 0, 255))
                elif action == "double_click":
                    self.mouse.double_click()
                    self.overlay.add_ui_command("DCLICK!", (50, 80), (255, 0, 255))
                elif action == "drag":
                    self.mouse.toggle_drag(start=True)
                    self.drag_active = True
                    self.overlay.add_ui_command("DRAG ON", (50, 110), (0, 255, 255))

            elif action == "drag" and not gesture_now and self.drag_active:
                self.mouse.toggle_drag(start=False)
                self.drag_active = False
                self.overlay.add_ui_command("DRAG OFF", (50, 110), (0, 165, 255))

            elif action in _CONTINUOUS_ACTIONS and gesture_now:
                if action == "scroll_down":
                    self.scroll_velocity += SCROLL_VELOCITY_STEP
                    self.overlay.add_ui_command("SCROLL DWON", (50, 200), (0, 255, 0), duration=5)
                elif action == "scroll_up":
                    self.scroll_velocity -= SCROLL_VELOCITY_STEP
                    self.overlay.add_ui_command("SCROLL UP", (50, 230), (255, 255, 0), duration=5)

    def close(self):
        if self.drag_active:
            self.mouse.toggle_drag(start=False)
        self.tracker.close()
