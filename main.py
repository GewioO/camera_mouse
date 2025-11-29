import sys
import argparse
import time
import threading
import cv2
import queue
from json_manager import JsonManager
from cli_manager import CLIManager
from ui.ui_manager import UIManager
from hand_tracker import HandTracker
from mouse_controller import MouseController
from preset_gestures import PresetGestures


def zoom_frame(frame, scale=2.0):
    h, w = frame.shape[:2]
    resized = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    new_h, new_w = resized.shape[:2]
    center_x, center_y = new_w // 2, new_h // 2
    start_x = center_x - w // 2
    start_y = center_y - h // 2
    return resized[start_y:start_y + h, start_x:start_x + w]


class VideoThread:
    def __init__(self, scale=1.5):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.scale = scale
        self.running = True

    def run(self, frame_queue):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            frame = cv2.flip(frame, 1)
            frame_zoomed = zoom_frame(frame, self.scale)
            try:
                frame_queue.put_nowait(frame_zoomed)
            except queue.Full:
                pass
            time.sleep(0.001)

    def update_scale(self, scale):
        self.scale = scale

    def stop(self):
        self.running = False
        self.cap.release()


class DisplayThread:
    def __init__(self, frame_queue, scale=1.5):
        self.frame_queue = frame_queue
        self.running = True
        self.scale = scale
        self.ui_commands = []

    def add_ui_command(self, text, position, color, duration=20):
        self.ui_commands.append({"text": text, "pos": position, "color": color, "frames": duration})

    def run(self):
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=0.01)
                cv2.putText(frame, f"ZOOM: {self.scale:.2f}x", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 255), 2)
                for cmd in self.ui_commands[:]:
                    cv2.putText(frame, cmd["text"], cmd["pos"], 
                               cv2.FONT_HERSHEY_SIMPLEX, 1.1, cmd["color"], 3)
                    cmd["frames"] -= 1
                    if cmd["frames"] <= 0:
                        self.ui_commands.remove(cmd)
                cv2.imshow("AI Hand Mouse CLI", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    self.running = False
                self.frame_queue.task_done()
            except queue.Empty:
                continue
            except:
                continue

    def stop(self):
        self.running = False


def run_camera(cli, json_manager, stop_flag=None, on_ready_callback=None):
    scale = cli.main_config.get("scale", 1.5)
    
    raw_frame_queue = queue.Queue(maxsize=3)
    display_queue = queue.Queue(maxsize=3)

    video_thread = VideoThread(scale)
    video_t = threading.Thread(target=video_thread.run, args=(raw_frame_queue,), daemon=True)
    video_t.start()

    display_thread = DisplayThread(display_queue, scale)
    display_t = threading.Thread(target=display_thread.run, daemon=True)
    display_t.start()

    if on_ready_callback:
        on_ready_callback()

    tracker = HandTracker(max_hands=1)
    mouse = MouseController(640, 480, smoothing=7)
    scroll_velocity = 0
    scroll_decay, scroll_step = 0.3, 0.7

    profile = cli.current_profile
    print("=== Mode:", cli.mode, "===")

    ONE_SHOT_ACTIONS = {"click", "double_click", "drag"}
    CONTINUOUS_ACTIONS = {"scroll_down", "scroll_up"}

    drag_active = False
    gesture_was_active = {}
    action_cooldown = {}
    COOLDOWN_FRAMES = 15

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
                            display_thread.add_ui_command("CLICK!", (50, 50), (0, 0, 255))
                        elif action == "double_click":
                            mouse.double_click()
                            display_thread.add_ui_command("DCLICK!", (50, 80), (255, 0, 255))
                        elif action == "drag":
                            mouse.toggle_drag(start=True)
                            drag_active = True
                            display_thread.add_ui_command("DRAG ON", (50, 110), (0, 255, 255))

                    elif action == "drag" and not gesture_now and drag_active:
                        mouse.toggle_drag(start=False)
                        drag_active = False
                        display_thread.add_ui_command("DRAG OFF", (50, 110), (0, 165, 255))

                    elif action in CONTINUOUS_ACTIONS and gesture_now:
                        if action == "scroll_down":
                            scroll_velocity += 2
                            display_thread.add_ui_command("SCROLL ↓", (50, 200), (0, 255, 0), duration=5)
                        elif action == "scroll_up":
                            scroll_velocity -= 2
                            display_thread.add_ui_command("SCROLL ↑", (50, 230), (255, 255, 0), duration=5)

            if abs(scroll_velocity) >= 1:
                mouse.scroll('down' if scroll_velocity > 0 else 'up', amount=scroll_step)
                scroll_velocity *= scroll_decay

            try:
                display_queue.put_nowait(frame_with_hands)
            except queue.Full:
                pass

            time.sleep(0.001)

    except KeyboardInterrupt:
        pass
    finally:
        cli.main_config["scale"] = scale
        if drag_active:
            mouse.toggle_drag(start=False)
        cli.persist_state()
        display_thread.stop()
        video_thread.stop()
        tracker.close()
        cv2.destroyAllWindows()
        time.sleep(0.5)
        print("Camera stopped")


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
    ui = UIManager(json_manager)
    ui.start()
    
    camera_thread = None
    camera_running = False
    camera_stop_flag = threading.Event()
    
    def on_camera_ready():
        ui.send_to_ui({"event": "camera_status", "data": {"running": True}})
    
    try:
        while True:
            signal = ui.get_signal()
            if signal and signal["event"] == "toggle_camera":
                print(f"Toggle camera: {'START' if not camera_running else 'STOP'}")
                
                if not camera_running:
                    camera_running = True
                    camera_stop_flag.clear()
                    ui.send_to_ui({"event": "camera_starting", "data": {}})
                    
                    camera_thread = threading.Thread(
                        target=run_camera,
                        args=(ui.cli_manager, json_manager, camera_stop_flag, on_camera_ready),
                        daemon=True
                    )
                    camera_thread.start()
                    
                else:
                    camera_running = False
                    camera_stop_flag.set()
                    ui.send_to_ui({"event": "camera_status", "data": {"running": False}})
    
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        pass
    finally:
        camera_stop_flag.set()
        ui.stop()


if __name__ == "__main__":
    main()
