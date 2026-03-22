# ui/ui_manager.py
import threading
import queue
import tkinter as tk
from typing import Dict, Any

from json_manager import JsonManager
from cli_manager import CLIManager

from .ui_elements import (
    COLORS, FONTS, SPINNER_CHARS,
    create_title, create_camera_labels,
    create_start_button, update_button_state, get_spinner_text,
    create_zoom_panel, update_zoom_display,
    create_gesture_list, create_profile_panel, create_lang_selector,
)


class UIManager:
    def __init__(self, json_manager: JsonManager):
        self.json_manager = json_manager
        self.cli_manager = CLIManager(json_manager)
        self.texts = json_manager.load_texts()
        self.gestures_data = json_manager.load_gestures()

        self.ui_to_main = queue.Queue()
        self.main_to_ui = queue.Queue()

        self._thread = None
        self._root: tk.Tk | None = None
        self._running = False

        self.camera_running = False
        self.loading = False
        self.spinner_index = 0

        main_config = json_manager.load_main_config()
        self.lang = main_config.get('lang', 'uk')
        self.scale = main_config.get('scale', 1.5)

        # Widget references
        self.camera_label = None
        self.loading_label = None
        self.start_btn = None
        self.zoom_val_label = None
        self.zoom_canvas = None
        self.gesture_frame = None
        self.gesture_list_parent = None
        self.profile_var = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._ui_mainloop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._root:
            self._root.quit()
            self._root.destroy()

    def send_to_ui(self, data: Dict[str, Any]):
        try:
            self.main_to_ui.put_nowait(data)
        except queue.Full:
            pass

    def get_signal(self, timeout: float = 0.0) -> Dict[str, Any] | None:
        try:
            return self.ui_to_main.get_nowait()
        except queue.Empty:
            return None

    # ── Mainloop ──────────────────────────────────────────────────────────────

    def _ui_mainloop(self):
        self._root = tk.Tk()
        self._root.title("AI Hand Mouse")
        self._root.geometry("640x360")
        self._root.resizable(False, False)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._root.after(50, self._update_from_main)
        self._root.mainloop()
        self._root = None

    def _build_ui(self):
        main_frame = tk.Frame(self._root, padx=15, pady=10)
        main_frame.pack(fill="both", expand=True)

        create_title(main_frame, self.texts, self.lang)

        # ── Middle section: left | sep | right ────────────────────────────────
        mid = tk.Frame(main_frame)
        mid.pack(fill="both", expand=True, pady=(0, 8))
        mid.columnconfigure(0, weight=3)
        mid.columnconfigure(2, weight=2)
        mid.rowconfigure(0, weight=1)

        left = tk.Frame(mid)
        left.grid(row=0, column=0, sticky="nsew")

        sep = tk.Frame(mid, width=1, bg=COLORS["separator"])
        sep.grid(row=0, column=1, sticky="ns", padx=10)

        right = tk.Frame(mid)
        right.grid(row=0, column=2, sticky="nsew")

        # Left: zoom
        self.zoom_val_label, self.zoom_canvas = create_zoom_panel(
            left, self.scale, self.texts, self.lang,
            on_zoom_up=self._on_zoom_up,
            on_zoom_down=self._on_zoom_down,
        )

        # Left: gesture list
        self.gesture_list_parent = left
        self._rebuild_gesture_list()

        # Right: profile selector
        profile_names = list(self.cli_manager.profiles.keys())
        self.profile_var = create_profile_panel(
            right, profile_names, self.cli_manager.mode,
            callback=self._on_profile_change,
            texts=self.texts,
            lang=self.lang,
        )

        # Right: language selector
        create_lang_selector(right, self.lang, self._on_lang_change)

        # ── Bottom section: camera status + button ────────────────────────────
        bottom = tk.Frame(main_frame)
        bottom.pack(fill="x")

        status_row = tk.Frame(bottom)
        status_row.pack()
        self.camera_label, self.loading_label = create_camera_labels(status_row, self.texts, self.lang)

        self.start_btn = create_start_button(bottom, self._toggle_camera, self.texts, self.lang)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _rebuild_ui(self):
        self.profile_var = None  # nullify in UI thread before widget destroy
        for widget in self._root.winfo_children():
            widget.destroy()
        self._build_ui()
        # Re-sync runtime state
        if self.camera_running:
            self._update_camera_ui()
        elif self.loading:
            self.camera_label.config(
                text=self.texts['ui']['camera']['starting'][self.lang],
                fg=COLORS["warning"],
            )

    def _rebuild_gesture_list(self):
        if self.gesture_frame:
            self.gesture_frame.destroy()
        self.gesture_frame = create_gesture_list(
            self.gesture_list_parent,
            self.cli_manager.current_profile,
            self.gestures_data,
            self.texts,
            self.lang,
        )

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_close(self):
        self._running = False
        # Nullify tkinter variable in UI thread before destroy to avoid
        # "main thread is not in main loop" RuntimeError on GC
        self.profile_var = None
        if self._root:
            self._root.destroy()
        self.ui_to_main.put({"event": "quit", "data": {}})

    def _toggle_camera(self):
        self.ui_to_main.put({"event": "toggle_camera", "data": {}})

    def _on_zoom_up(self):
        self.scale = min(3.0, round(self.scale + 0.1, 1))
        update_zoom_display(self.zoom_val_label, self.zoom_canvas, self.scale)
        self.ui_to_main.put({"event": "zoom_change", "data": {"delta": 0.1}})

    def _on_zoom_down(self):
        self.scale = max(1.0, round(self.scale - 0.1, 1))
        update_zoom_display(self.zoom_val_label, self.zoom_canvas, self.scale)
        self.ui_to_main.put({"event": "zoom_change", "data": {"delta": -0.1}})

    def _on_lang_change(self, new_lang: str):
        if new_lang == self.lang:
            return
        self.lang = new_lang
        self.cli_manager.lang = new_lang
        self.cli_manager.main_config["lang"] = new_lang
        self.cli_manager.persist_state()
        self._rebuild_ui()

    def _on_profile_change(self, new_mode: str):
        self.cli_manager.mode = new_mode
        self.cli_manager.current_profile = self.cli_manager.profiles[new_mode]
        self.cli_manager.main_config["last_profile"] = new_mode
        self.cli_manager.persist_state()
        self._rebuild_gesture_list()
        self.ui_to_main.put({"event": "profile_changed", "data": {"mode": new_mode}})

    # ── Update loop ───────────────────────────────────────────────────────────

    def _update_from_main(self):
        while True:
            try:
                msg = self.main_to_ui.get_nowait()
                event = msg.get("event")

                if event == "camera_status":
                    self.camera_running = msg["data"]["running"]
                    self.loading = False
                    self._update_camera_ui()

                elif event == "camera_starting":
                    self.loading = True
                    self.camera_label.config(
                        text=self.texts['ui']['camera']['starting'][self.lang],
                        fg=COLORS["warning"],
                    )

                elif event == "zoom_update":
                    self.scale = msg["data"]["scale"]
                    if self.zoom_val_label:
                        update_zoom_display(self.zoom_val_label, self.zoom_canvas, self.scale)

            except queue.Empty:
                break

        if self.loading:
            self.spinner_index = (self.spinner_index + 1) % 4
            spinner_text = get_spinner_text(self.texts, self.lang, SPINNER_CHARS[self.spinner_index])
            self.loading_label.config(text=spinner_text)

        if self._running and self._root:
            self._root.after(200, self._update_from_main)

    def _update_camera_ui(self):
        camera_text_key = "running" if self.camera_running else "stopped"
        self.camera_label.config(
            text=self.texts['ui']['camera'][camera_text_key][self.lang],
            fg=COLORS["success"] if self.camera_running else COLORS["danger_text"],
        )
        update_button_state(self.start_btn, self.texts, self.lang, self.camera_running)
        self.loading_label.config(text="")
