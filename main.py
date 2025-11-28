import cv2
from hand_tracker import HandTracker
from mouse_controller import MouseController
from preset_gestures import PresetGestures
from cli_manager import CLIManager
from json_manager import JsonManager


def zoom_frame(frame, scale: float = 2.0):
    h, w = frame.shape[:2]
    resized = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    new_h, new_w = resized.shape[:2]
    center_x, center_y = new_w // 2, new_h // 2
    start_x = center_x - w // 2
    start_y = center_y - h // 2
    zoomed = resized[start_y:start_y + h, start_x:start_x + w]
    return zoomed


def main():
    json_manager = JsonManager()
    cli = CLIManager(json_manager=json_manager)

    if cli.is_help_requested():
        cli.show_help()
        return

    scale = cli.main_config.get("scale", 1.5)
    scale_min = 1.0
    scale_max = 4.0

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    tracker = HandTracker(max_hands=1)
    mouse = MouseController(frame_width, frame_height, smoothing=7)
    scroll_velocity = 0
    scroll_decay = 0.3
    scroll_step = 0.7

    profile = cli.current_profile
    print("=== Mode:", cli.mode, "===")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        frame_zoomed = zoom_frame(frame, scale=scale)
        frame_proc = tracker.find_hands(frame_zoomed, draw=True)
        landmarks = tracker.get_hand_landmarks()

        if landmarks:
            gestures = PresetGestures(
                landmarks,
                frame_zoomed.shape[1],
                frame_zoomed.shape[0],
                json_manager=json_manager
            )
            center_pos = tracker.get_hand_center(frame_zoomed.shape[1], frame_zoomed.shape[0])

            if center_pos and "mouse_move" in profile:
                mouse.smooth_move(center_pos[0], center_pos[1])
                cv2.circle(frame_proc, center_pos, 12, (0, 255, 255), cv2.FILLED)

            for action, gesture_name in profile.items():
                if action == "mouse_move":
                    continue
                if gestures.detect(gesture_name):
                    if action == "scroll_down":
                        scroll_velocity += 2
                        cv2.putText(frame_proc, "SCROLL DOWN", (50, 200),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 0), 3)
                    elif action == "scroll_up":
                        scroll_velocity -= 2
                        cv2.putText(frame_proc, "SCROLL UP", (50, 230),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 0), 3)
                    elif action == "click":
                        mouse.click('left')
                        cv2.putText(frame_proc, "CLICK!", (50, 50),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 255), 3)
                    elif action == "double_click":
                        mouse.double_click()
                        cv2.putText(frame_proc, "DOUBLE CLICK!", (50, 80),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 0, 255), 3)
                    elif action == "drag":
                        mouse.toggle_drag(start=True)
                else:
                    if action == "drag":
                        mouse.toggle_drag(start=False)

        if abs(scroll_velocity) >= 1:
            mouse.scroll('down' if scroll_velocity > 0 else 'up', amount=scroll_step)
            scroll_velocity *= scroll_decay

        cv2.putText(frame_proc, f"ZOOM: {scale:.2f}x", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 255), 2)
        cv2.imshow("AI Hand Mouse CLI", frame_proc)

        key = cv2.waitKey(1)
        if key == ord('+') or key == ord('='):
            scale = min(scale + 0.1, scale_max)
        if key == ord('-') or key == ord('_'):
            scale = max(scale - 0.1, scale_min)
        if key == ord('q'):
            break

    cli.main_config["scale"] = scale
    cli.persist_state()

    tracker.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
