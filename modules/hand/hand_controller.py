from dataclasses import dataclass, field

from modules.hand.preset_gestures import PresetGestures
from core.mouse_controller import MouseController
from core.constants import (
    FRAME_WIDTH, FRAME_HEIGHT, MOUSE_SMOOTHING,
    SCROLL_DECAY, SCROLL_AMOUNT, SCROLL_VELOCITY_STEP, COOLDOWN_FRAMES,
)

_ONE_SHOT_ACTIONS = {"click", "double_click", "drag"}
_CONTINUOUS_ACTIONS = {"scroll_down", "scroll_up"}


@dataclass
class HandResult:
    move_to: tuple | None = None      # cursor position drawn as a circle, or None
    events: list = field(default_factory=list)   # e.g. "click", "drag_on", "scroll_up"


class HandController:
    """Business logic for the hand module: gesture detection → mouse/scroll/drag
    actions + all per-run state. Knows nothing about drawing or the display —
    it executes actions on the mouse and reports what happened via HandResult."""

    def __init__(self, profile, json_manager):
        self.profile = profile
        self.json_manager = json_manager
        self.mouse = MouseController(FRAME_WIDTH, FRAME_HEIGHT, smoothing=MOUSE_SMOOTHING)

        self.scroll_velocity = 0
        self.drag_active = False
        self.gesture_was_active = {}
        self.action_cooldown = {}

    def update(self, landmarks, center_pos, width, height) -> HandResult:
        """Advance one frame. Called every frame (landmarks may be None)
        Scroll velocity keeps decaying/emitting even when the hand is lost"""
        result = HandResult()

        if landmarks:
            self._detect_and_act(landmarks, center_pos, width, height, result)

        # Scroll pump — runs every frame, independent of detection.
        if abs(self.scroll_velocity) >= 1:
            self.mouse.scroll('down' if self.scroll_velocity > 0 else 'up', amount=SCROLL_AMOUNT)
            self.scroll_velocity *= SCROLL_DECAY

        return result

    def _detect_and_act(self, landmarks, center_pos, width, height, result: HandResult):
        gestures = PresetGestures(landmarks, width, height, self.json_manager)

        if center_pos and "mouse_move" in self.profile:
            self.mouse.smooth_move(center_pos[0], center_pos[1])
            result.move_to = center_pos

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
                    result.events.append("click")
                elif action == "double_click":
                    self.mouse.double_click()
                    result.events.append("double_click")
                elif action == "drag":
                    self.mouse.toggle_drag(start=True)
                    self.drag_active = True
                    result.events.append("drag_on")

            elif action == "drag" and not gesture_now and self.drag_active:
                self.mouse.toggle_drag(start=False)
                self.drag_active = False
                result.events.append("drag_off")

            elif action in _CONTINUOUS_ACTIONS and gesture_now:
                if action == "scroll_down":
                    self.scroll_velocity += SCROLL_VELOCITY_STEP
                    result.events.append("scroll_down")
                elif action == "scroll_up":
                    self.scroll_velocity -= SCROLL_VELOCITY_STEP
                    result.events.append("scroll_up")

    def close(self):
        if self.drag_active:
            self.mouse.toggle_drag(start=False)
