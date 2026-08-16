import argparse
import time
import threading
import cv2
import queue
from core.json_manager import JsonManager
from core.module_manager import ModuleManager
from cli_manager import CLIManager
from ui.ui_manager import UIManager
from core.scale_controller import ScaleController
from core.camera_manager import enumerate_cameras
from core.video_thread import VideoThread
from core.frame_io import push_frame, show_frame
from modules.hand.hand_runner import HandRunner
from modules.forearm.forearm_runner import ForearmRunner
from core.constants import DEFAULT_SCALE, DEFAULT_CAMERA_ID, QUEUE_MAXSIZE

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

    if on_ready_callback:
        on_ready_callback()

    print("=== Module:", active_module, "| Mode:", cli.mode, "===")

    runner = _build_runner(active_module, cli, json_manager, scale_controller, forearm_side)
    try:
        _run_loop(runner, raw_frame_queue, scale_controller, display_queue, stop_flag)
    finally:
        cli.main_config["scale"] = scale_controller.get()
        cli.persist_state()
        video_thread.stop()
        if display_queue is None:
            cv2.destroyAllWindows()
        time.sleep(0.5)
        print("Camera stopped")

_RUNNERS = {
    "hand":    lambda cli, jm, sc, side: HandRunner(cli, jm, sc),
    "forearm": lambda cli, jm, sc, side: ForearmRunner(side=side),
}


def _build_runner(active_module, cli, json_manager, scale_controller, forearm_side):
    make = _RUNNERS.get(active_module, _RUNNERS["hand"])
    return make(cli, json_manager, scale_controller, forearm_side)


def _run_loop(runner, raw_frame_queue, scale_controller, display_queue, stop_flag):
    try:
        while not (stop_flag and stop_flag.is_set()):
            try:
                frame = raw_frame_queue.get_nowait()
            except queue.Empty:
                time.sleep(0.001)
                continue

            frame = runner.process(frame)
            push_frame(frame, display_queue, scale_controller)
            time.sleep(0.001)

    except KeyboardInterrupt:
        pass
    finally:
        runner.close()


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
        cv2.destroyAllWindows()
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

                elif event == "profile_changed":
                    print(f"Profile changed to: {signal['data']['mode']}")
                    if camera_running:
                        stop_camera()

                elif event == "module_changed":
                    print(f"Module changed to: {signal['data']['module']}")
                    if camera_running:
                        stop_camera()

                elif event == "quit":
                    break

            if camera_running:
                try:
                    frame = display_queue.get_nowait()
                    show_frame(frame, scale_controller)
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
