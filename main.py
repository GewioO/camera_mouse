import cv2
import numpy as np
import time
from hand_tracker import HandTracker
from mouse_controller import MouseController
from preset_gestures import PresetGestures   # твій новий клас

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

    print("=== Управління жестами ===")
    print("Скрол вниз — торкання великого, середнього та безіменного")
    print("Скрол вверх — кулак, а вказівний розігнутий вверх")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        frame_zoomed = zoom_frame(frame, scale=scale)
        frame_proc = tracker.find_hands(frame_zoomed, draw=True)
        landmarks = tracker.get_hand_landmarks()

        if landmarks:
            gestures = PresetGestures(landmarks, frame_zoomed.shape[1], frame_zoomed.shape[0])
            center_pos = tracker.get_hand_center(frame_zoomed.shape[1], frame_zoomed.shape[0])
            if center_pos:
                mouse.smooth_move(center_pos[0], center_pos[1])
                cv2.circle(frame_proc, center_pos, 12, (0, 255, 255), cv2.FILLED)

            # --- Жест скролл вниз: великий+середній+безіменний ---
            if gestures.is_thumb_middle_ring():
                scroll_velocity += 2
                cv2.putText(frame_proc, "SCROLL DOWN (smooth)", (50, 200),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 0), 3)

            # --- Жест скролл вверх: кулак, а вказівний витягнутий вверх ---
            if gestures.is_fist_and_index_up():
                scroll_velocity -= 2
                cv2.putText(frame_proc, "SCROLL UP (smooth)", (50, 230),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 0), 3)

            # Приклад використання інших жестів:
            # if gestures.is_thumb_and_index():
            #     print("Великий + вказівний!")
            # if gestures.is_thumb_and_middle(): ...
            # ...

        # --- Плавний скролл ---
        if abs(scroll_velocity) >= 1:
            mouse.scroll('down' if scroll_velocity > 0 else 'up', amount=scroll_step)
            scroll_velocity *= scroll_decay

        cv2.putText(frame_proc, f"ZOOM: {scale:.2f}x", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 255), 2)
        cv2.imshow("AI Hand Mouse Scroll", frame_proc)

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
