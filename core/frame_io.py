import queue
import cv2

WINDOW_NAME = "AI Hand Mouse"
_ZOOM_STEP = 0.1


def handle_zoom_key(key, scale_controller):
    """Apply the +/- zoom keys to the shared scale."""
    if key == ord('+') or key == ord('='):
        scale_controller.increment(_ZOOM_STEP)
    elif key == ord('-'):
        scale_controller.increment(-_ZOOM_STEP)


def show_frame(frame, scale_controller):
    """
    Show a frame in the OpenCV window and process zoom keys.

    MUST be called from the thread that owns the window (the true main thread) —
    in GUI mode that's the main loop, in CLI mode it's the module loop itself.
    """
    cv2.imshow(WINDOW_NAME, frame)
    handle_zoom_key(cv2.waitKey(1) & 0xFF, scale_controller)


def push_frame(frame, display_queue, scale_controller):
    """Hand a rendered frame to the display."""
    if display_queue is not None:
        try:
            display_queue.put_nowait(frame)
        except queue.Full:
            pass
    else:
        show_frame(frame, scale_controller)
