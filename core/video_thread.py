import time
import queue
import cv2

from core.camera_manager import open_camera, zoom_frame, rotate_frame
from core.constants import FRAME_WIDTH, FRAME_HEIGHT, DEFAULT_CAMERA_ID


class VideoThread:
    """
    Captures frames from the camera, applies rotation/mirror/zoom, and pushes
    the result into a raw-frame queue for the active module's loop to consume
    """

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
