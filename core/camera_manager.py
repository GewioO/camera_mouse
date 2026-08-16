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


_ROTATIONS = {
    90:  cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


def rotate_frame(frame, rotation: int = 0):
    """
    Rotate a frame clockwise by 0/90/180/270 degrees.
    """
    flag = _ROTATIONS.get(rotation)
    return cv2.rotate(frame, flag) if flag is not None else frame


def zoom_frame(frame, scale: float = 1.5):
    if scale <= 1.0:
        return frame
    h, w = frame.shape[:2]
    resized = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    new_h, new_w = resized.shape[:2]
    center_x, center_y = new_w // 2, new_h // 2
    start_x = center_x - w // 2
    start_y = center_y - h // 2
    return resized[start_y:start_y + h, start_x:start_x + w]
