import os
import platform
import cv2


def enumerate_cameras(max_check: int = 5) -> list[int]:
    available = []
    for i in range(max_check):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
        cap.release()
    return available or [0]


def get_camera_name(camera_id: int) -> str:
    system = platform.system()

    if system == "Linux":
        try:
            with open(f"/sys/class/video4linux/video{camera_id}/name") as f:
                return f.read().strip()
        except OSError:
            pass

    elif system == "Windows":
        try:
            from pygrabber.dshow_graph import FilterGraph
            devices = FilterGraph().get_input_devices()
            if camera_id < len(devices):
                return devices[camera_id]
        except Exception:
            pass

    return f"Camera {camera_id}"


def open_camera(camera_id: int) -> cv2.VideoCapture:
    return cv2.VideoCapture(camera_id)
