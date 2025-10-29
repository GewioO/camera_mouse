import argparse
import cv2
import numpy as np
import time
from hand_tracker import HandTracker
from mouse_controller import MouseController
from preset_gestures import PresetGestures
import json
import os

# maybe should be in res manager
def get_text(key, lang="uk"):
    path = os.path.join("res", "text_resources.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get(key, {}).get(lang, data.get(key, {}).get("uk", key))

def zoom_frame(frame, scale=2.0):
    h, w = frame.shape[:2]
    resized = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    new_h, new_w = resized.shape[:2]
    center_x, center_y = new_w // 2, new_h // 2
    start_x = center_x - w // 2
    start_y = center_y - h // 2
    zoomed = resized[start_y:start_y + h, start_x:start_x + w]
    return zoomed

def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("mode", nargs="?", default="default",
        choices=["default", "touch", "scroll", "help", "configuration"],
        help=""
    )
    parser.add_argument("--lang", choices=["uk", "en"], default="uk", help="interface language (uk/en)")
    args = parser.parse_args()

    if args.mode == "help":
        print(get_text("help", lang=args.lang))
        return

    scale = 1.5
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

    print("=== Mode:", args.mode, "===")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        frame_zoomed = zoom_frame(frame, scale=scale)
        frame_proc = tracker.find_hands(frame_zoomed, draw=True)
        landmarks = tracker.get_hand_landmarks()
        center_pos = None

        if landmarks:
            gestures = PresetGestures(landmarks, frame_zoomed.shape[1], frame_zoomed.shape[0])
            center_pos = tracker.get_hand_center(frame_zoomed.shape[1], frame_zoomed.shape[0])
            if center_pos:
                if args.mode in ["default", "touch"]:
                    mouse.smooth_move(center_pos[0], center_pos[1])
                    cv2.circle(frame_proc, center_pos, 12, (0, 255, 255), cv2.FILLED)

            if args.mode in ["default", "scroll"]:
                if gestures.is_thumb_middle_ring():
                    scroll_velocity += 2
                    cv2.putText(frame_proc, "SCROLL DOWN (smooth)", (50, 200),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 0), 3)
                if gestures.is_fist_and_index_up():
                    scroll_velocity -= 2
                    cv2.putText(frame_proc, "SCROLL UP (smooth)", (50, 230),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 0), 3)

            if args.mode == "touch":
                if gestures.is_thumb_and_index(): 
                    mouse.click('left')
                    cv2.putText(frame_proc, "CLICK!", (50, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 255), 3)
                if gestures.is_thumb_and_middle():
                    mouse.double_click()
                    cv2.putText(frame_proc, "DOUBLE CLICK!", (50, 80),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 0, 255), 3)
                if gestures.is_thumb_and_ring():    
                    mouse.toggle_drag(start=True)
                    cv2.putText(frame_proc, "DRAG!", (50, 110),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 150, 255), 3)
                else:
                    mouse.toggle_drag(start=False)

        # --- Smooth scroll ---
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

    tracker.close()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
