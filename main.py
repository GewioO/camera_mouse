import argparse
import time
import threading
import cv2
import queue
from core.json_manager import JsonManager
from core.module_manager import ModuleManager
from cli_manager import CLIManager
from ui.ui_manager import UIManager
from modules.hand.hand_tracker import HandTracker
from modules.forearm.tracker import ForearmTracker
from modules.forearm.flick_detector import FlickDetector
from modules.forearm.rotation_classifier import RotationClassifier
from core.mouse_controller import MouseController
from modules.hand.preset_gestures import PresetGestures
from core.scale_controller import ScaleController
from core.camera_manager import open_camera, enumerate_cameras, zoom_frame, rotate_frame
from core.constants import (
    FRAME_WIDTH, FRAME_HEIGHT,
    DEFAULT_SCALE, DEFAULT_CAMERA_ID,
    MOUSE_SMOOTHING,
    SCROLL_DECAY, SCROLL_AMOUNT, SCROLL_VELOCITY_STEP,
    COOLDOWN_FRAMES,
    QUEUE_MAXSIZE,
)

class VideoThread:
    def __init__(self, scale_controller, camera_id: int = DEFAULT_CAMERA_ID, rotation: int = 0):
        self.cap = open_camera(camera_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        self.scale_controller = scale_controller
        self.rotation = rotation
        self.running = True

    def run(self, frame_queue):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            frame = rotate_frame(frame, self.rotation)
            frame = cv2.flip(frame, 1)

            current_scale = self.scale_controller.get()
            frame_zoomed = zoom_frame(frame, current_scale)

            try:
                frame_queue.put_nowait(frame_zoomed)
            except queue.Full:
                pass

            time.sleep(0.001)

    def stop(self):
        self.running = False
        self.cap.release()

class DisplayOverlay:
    def __init__(self, scale_controller):
        self.scale_controller = scale_controller
        self.ui_commands = []

    def add_ui_command(self, text, position, color, duration=20):
        self.ui_commands.append({"text": text, "pos": position, "color": color, "frames": duration})

    def draw(self, frame):
        current_scale = self.scale_controller.get()
        cv2.putText(frame, f"ZOOM: {current_scale:.2f}x [+/-]", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 255), 2)
        for cmd in self.ui_commands[:]:
            cv2.putText(frame, cmd["text"], cmd["pos"],
                       cv2.FONT_HERSHEY_SIMPLEX, 1.1, cmd["color"], 3)
            cmd["frames"] -= 1
            if cmd["frames"] <= 0:
                self.ui_commands.remove(cmd)

def run_camera(cli, json_manager, stop_flag=None, on_ready_callback=None, scale_controller=None,
               display_queue=None, active_module="hand", forearm_side="right"):
    if scale_controller is None:
        scale_controller = ScaleController(cli.main_config.get("scale", DEFAULT_SCALE))

    raw_frame_queue = queue.Queue(maxsize=QUEUE_MAXSIZE)

    camera_id = cli.main_config.get("camera_id", DEFAULT_CAMERA_ID)
    available = enumerate_cameras()
    if camera_id not in available:
        camera_id = available[0]
        cli.main_config["camera_id"] = camera_id
        print(f"Saved camera_id not available, falling back to camera {camera_id}")
    camera_rotation = cli.main_config.get("camera_rotation", 0)
    video_thread = VideoThread(scale_controller, camera_id=camera_id, rotation=camera_rotation)
    video_t = threading.Thread(target=video_thread.run, args=(raw_frame_queue,), daemon=True)
    video_t.start()

    display_overlay = DisplayOverlay(scale_controller)

    if on_ready_callback:
        on_ready_callback()

    print("=== Module:", active_module, "| Mode:", cli.mode, "===")

    try:
        if active_module == "forearm":
            tracker = ForearmTracker(side=forearm_side)
            ml_classifier = RotationClassifier(side=forearm_side)
            _run_forearm_loop(tracker, raw_frame_queue, scale_controller, display_overlay,
                            display_queue, stop_flag, ml_classifier)
        else:
            tracker = HandTracker(max_hands=1)
            _run_hand_loop(tracker, raw_frame_queue, cli, json_manager, scale_controller,
                           display_overlay, display_queue, stop_flag)
    finally:
        cli.main_config["scale"] = scale_controller.get()
        cli.persist_state()
        video_thread.stop()
        if display_queue is None:
            cv2.destroyAllWindows()
        time.sleep(0.5)
        print("Camera stopped")


def _run_hand_loop(tracker, raw_frame_queue, cli, json_manager, scale_controller,
                   display_overlay, display_queue, stop_flag):
    mouse = MouseController(FRAME_WIDTH, FRAME_HEIGHT, smoothing=MOUSE_SMOOTHING)
    scroll_velocity = 0
    profile = cli.current_profile

    ONE_SHOT_ACTIONS = {"click", "double_click", "drag"}
    CONTINUOUS_ACTIONS = {"scroll_down", "scroll_up"}
    drag_active = False
    gesture_was_active = {}
    action_cooldown = {}

    try:
        while not (stop_flag and stop_flag.is_set()):
            try:
                frame_zoomed = raw_frame_queue.get_nowait()
            except queue.Empty:
                time.sleep(0.001)
                continue

            frame_with_hands = tracker.find_hands(frame_zoomed, draw=True)
            landmarks = tracker.get_hand_landmarks()

            if landmarks:
                gestures = PresetGestures(landmarks, frame_zoomed.shape[1], frame_zoomed.shape[0], json_manager)
                center_pos = tracker.get_hand_center(frame_zoomed.shape[1], frame_zoomed.shape[0])

                if center_pos and "mouse_move" in profile:
                    mouse.smooth_move(center_pos[0], center_pos[1])
                    cv2.circle(frame_with_hands, center_pos, 12, (0, 255, 255), cv2.FILLED)

                for action, gesture_name in profile.items():
                    if action == "mouse_move":
                        continue

                    if action in ONE_SHOT_ACTIONS and action in action_cooldown and action_cooldown[action] > 0:
                        action_cooldown[action] -= 1
                        continue

                    gesture_now = gestures.detect(gesture_name)
                    gesture_prev = gesture_was_active.get(action, False)
                    edge_triggered = gesture_now and not gesture_prev
                    gesture_was_active[action] = gesture_now

                    if action in ONE_SHOT_ACTIONS and edge_triggered:
                        action_cooldown[action] = COOLDOWN_FRAMES
                        if action == "click":
                            mouse.click('left')
                            display_overlay.add_ui_command("CLICK!", (50, 50), (0, 0, 255))
                        elif action == "double_click":
                            mouse.double_click()
                            display_overlay.add_ui_command("DCLICK!", (50, 80), (255, 0, 255))
                        elif action == "drag":
                            mouse.toggle_drag(start=True)
                            drag_active = True
                            display_overlay.add_ui_command("DRAG ON", (50, 110), (0, 255, 255))

                    elif action == "drag" and not gesture_now and drag_active:
                        mouse.toggle_drag(start=False)
                        drag_active = False
                        display_overlay.add_ui_command("DRAG OFF", (50, 110), (0, 165, 255))

                    elif action in CONTINUOUS_ACTIONS and gesture_now:
                        if action == "scroll_down":
                            scroll_velocity += SCROLL_VELOCITY_STEP
                            display_overlay.add_ui_command("SCROLL DWON", (50, 200), (0, 255, 0), duration=5)
                        elif action == "scroll_up":
                            scroll_velocity -= SCROLL_VELOCITY_STEP
                            display_overlay.add_ui_command("SCROLL UP", (50, 230), (255, 255, 0), duration=5)

            if abs(scroll_velocity) >= 1:
                mouse.scroll('down' if scroll_velocity > 0 else 'up', amount=SCROLL_AMOUNT)
                scroll_velocity *= SCROLL_DECAY

            display_overlay.draw(frame_with_hands)
            _push_frame(frame_with_hands, display_queue, scale_controller)
            time.sleep(0.001)

    except KeyboardInterrupt:
        pass
    finally:
        if drag_active:
            mouse.toggle_drag(start=False)
        tracker.close()


def _run_forearm_loop(tracker, raw_frame_queue, scale_controller, display_overlay,
                    display_queue, stop_flag, ml_classifier=None):
    # Rule-based skin-pixel asymmetry — display-only diagnostic now (superseded
    # by the trained ML classifier below as the driver of rot_state, since it
    # measures palmar/dorsal skin far less reliably than the learned features).
    # asym = (top_skin - bot_skin) / total_skin  ∈ [-1, +1]
    _ASYM_THRESH = 0.12   # imbalance ratio to trigger a rule-state change
    _HYST        = 0.04   # hysteresis to avoid flicker
    _ASYM_SMOOTH = 0.55   # EMA factor for the raw asymmetry signal

    # Consecutive identical ML predictions required before committing them to
    # rot_state — model.predict() has no temporal smoothing of its own, so a
    # single-frame flip would otherwise flicker the state every frame.
    _ML_CONFIRM_FRAMES = 5

    asym_smooth  = None
    rule_state   = "neutral"
    rot_state    = "neutral"
    ml_pending   = None
    ml_pending_n = 0
    log_frame    = 0

    try:
        while not (stop_flag and stop_flag.is_set()):
            try:
                frame = raw_frame_queue.get_nowait()
            except queue.Empty:
                time.sleep(0.001)
                continue

            orig = frame.copy() 
            frame = tracker.find_pose(frame, draw=True)
            landmarks = tracker.get_landmarks()
            asym_raw = tracker.get_forearm_asymmetry(orig)

            if landmarks:
                # ── Rule-based asymmetry — diagnostic only, doesn't drive state ──
                asym = None
                if asym_raw is not None:
                    asym_smooth = asym_raw if asym_smooth is None else (
                        asym_smooth * _ASYM_SMOOTH + asym_raw * (1 - _ASYM_SMOOTH))
                    asym = asym_smooth

                    new_rule_state = rule_state
                    if asym < -(_ASYM_THRESH + _HYST):
                        new_rule_state = "outer"
                    elif asym > (_ASYM_THRESH + _HYST):
                        new_rule_state = "inner"
                    elif abs(asym) < _ASYM_THRESH - _HYST:
                        new_rule_state = "neutral"
                    rule_state = new_rule_state

                    tracker.draw_forearm_roi(frame, asym)
                    cv2.putText(frame, f"asym: {asym:+.4f}", (10, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 100), 2)
                    cv2.putText(frame, f"raw:  {asym_raw:+.4f}", (10, 65),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)

                cv2.putText(frame, f"rule: {rule_state}", (10, 160),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (150, 150, 150), 2)

                # ── ML classifier — drives rot_state when the model is available ──
                ml_state = None
                if ml_classifier is not None and ml_classifier.available:
                    ml_state = ml_classifier.predict(orig, landmarks)
                    if ml_state == ml_pending:
                        ml_pending_n += 1
                    else:
                        ml_pending, ml_pending_n = ml_state, 1

                new_state = rot_state
                if ml_classifier is not None and ml_classifier.available:
                    if ml_state and ml_pending_n >= _ML_CONFIRM_FRAMES:
                        new_state = ml_state
                else:
                    new_state = rule_state   # no trained model — fall back to the rule

                if new_state != rot_state:
                    print(f"[ROT] {rot_state} -> {new_state}  ml={ml_state}  rule={rule_state}")
                    rot_state = new_state

                log_frame += 1
                if log_frame % 15 == 0:
                    print(f"[ROT] state={rot_state:<7}  ml={ml_state}  rule={rule_state}")

                # ── Draw main state label ────────────────────────────────────
                state_labels = {
                    "neutral": ("NEUTRAL",  (160, 160, 160)),
                    "outer":   ("OUTER >>", (0,   220, 255)),
                    "inner":   ("<< INNER", (255, 200, 0)),
                }
                label, color = state_labels[rot_state]
                cv2.putText(frame, label, (10, 130),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

            else:
                # Tracking lost entirely — reset both state machines
                if landmarks is None:
                    asym_smooth = None
                    rule_state  = "neutral"
                    rot_state   = "neutral"
                    ml_pending, ml_pending_n = None, 0
                cv2.putText(frame, "NO TRACKING", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            _push_frame(frame, display_queue, scale_controller)
            time.sleep(0.001)

    except KeyboardInterrupt:
        pass
    finally:
        tracker.close()


def _push_frame(frame, display_queue, scale_controller):
    if display_queue is not None:
        try:
            display_queue.put_nowait(frame)
        except queue.Full:
            pass
    else:
        cv2.imshow("AI Hand Mouse", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('+') or key == ord('='):
            scale_controller.increment(0.1)
        elif key == ord('-'):
            scale_controller.increment(-0.1)

def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("mode", nargs="?", default=None)
    args = parser.parse_args()

    json_manager = JsonManager()

    if args.mode:
        cli = CLIManager(json_manager)
        if cli.is_help_requested():
            cli.show_help()
            return
        print(f"CLI Mode: {cli.mode}")
        run_camera(cli, json_manager)
        return

    print("GUI Mode")
    main_config = json_manager.load_main_config()
    scale_controller = ScaleController(main_config.get("scale", DEFAULT_SCALE))
    ui = UIManager(json_manager, scale_controller)
    ui.start()

    camera_thread = None
    camera_running = False
    camera_stop_flag = threading.Event()
    display_queue = queue.Queue(maxsize=QUEUE_MAXSIZE)

    def on_camera_ready():
        ui.send_to_ui({"event": "camera_status", "data": {"running": True}})

    def start_camera():
        nonlocal camera_running, camera_thread
        camera_running = True
        camera_stop_flag.clear()
        ui.send_to_ui({"event": "camera_starting", "data": {}})
        camera_thread = threading.Thread(
            target=run_camera,
            args=(ui.cli_manager, json_manager, camera_stop_flag, on_camera_ready),
            kwargs={
                "scale_controller": scale_controller,
                "display_queue": display_queue,
                "active_module": ui.module_manager.get(),
                "forearm_side": ui.cli_manager.main_config.get("forearm_side", "right"),
            },
            daemon=True,
        )
        camera_thread.start()

    def stop_camera():
        nonlocal camera_running
        camera_running = False
        camera_stop_flag.set()
        ui.send_to_ui({"event": "camera_status", "data": {"running": False}})

    try:
        while True:
            signal = ui.get_signal()
            if signal:
                event = signal["event"]

                if event == "toggle_camera":
                    print(f"Toggle camera: {'START' if not camera_running else 'STOP'}")
                    if not camera_running:
                        start_camera()
                    else:
                        stop_camera()
                        cv2.destroyAllWindows()

                elif event == "profile_changed":
                    print(f"Profile changed to: {signal['data']['mode']}")
                    if camera_running:
                        stop_camera()
                        cv2.destroyAllWindows()

                elif event == "module_changed":
                    print(f"Module changed to: {signal['data']['module']}")
                    if camera_running:
                        stop_camera()
                        cv2.destroyAllWindows()

                elif event == "quit":
                    break

            # Display frame from camera thread in main thread
            if camera_running:
                try:
                    frame = display_queue.get_nowait()
                    cv2.imshow("AI Hand Mouse", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('+') or key == ord('='):
                        scale_controller.increment(0.1)
                    elif key == ord('-'):
                        scale_controller.increment(-0.1)
                except queue.Empty:
                    pass

            time.sleep(0.01)

    except KeyboardInterrupt:
        pass
    finally:
        camera_stop_flag.set()
        cv2.destroyAllWindows()
        ui.stop()

if __name__ == "__main__":
    main()
