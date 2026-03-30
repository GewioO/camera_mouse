# ui/ui_manager.py
import threading
import queue
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any
import sv_ttk

from core.json_manager import JsonManager
from cli_manager import CLIManager
from core.scale_controller import ScaleController
from core.camera_manager import enumerate_cameras, get_camera_name
from core.constants import SCALE_STEP, DEFAULT_CAMERA_ID

from .ui_elements import (
    COLORS, FONTS, SPINNER_CHARS, TEAL, TEAL_HOVER, DANGER, DANGER_HOVER,
    setup_styles, create_title, create_camera_labels,
    create_start_button, update_button_state, get_spinner_text,
    create_zoom_panel, update_zoom_display,
    create_gesture_list, create_profile_panel, create_lang_selector,
    create_camera_selector,
)
from .profile_builder_controller import ProfileBuilderController
from .profile_builder_ui import ProfileBuilderWindow


class UIManager:
    def __init__(self, json_manager: JsonManager, scale_controller: ScaleController):
        self.json_manager = json_manager
        self.cli_manager = CLIManager(json_manager)
        self._scale_ctrl = scale_controller
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

        self.available_cameras = enumerate_cameras()
        self.camera_names = [
            f"{get_camera_name(i)} ({i})" for i in self.available_cameras
        ]

        # Profiles that cannot be deleted
        self._protected_profiles = {"default", "scroll"}

        # Widget references
        self.camera_label = None
        self.loading_label = None
        self.start_btn = None
        self.zoom_val_label = None
        self.zoom_canvas = None
        self.gesture_frame = None
        self.gesture_list_parent = None
        self.profile_var = None
        self.profile_combo: ttk.Combobox | None = None
        self.delete_profile_btn: tk.Button | None = None
        self.camera_selector: ttk.Combobox | None = None

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
        self._root.geometry("640x460")
        self._root.minsize(560, 400)
        self._root.resizable(True, True)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        sv_ttk.set_theme("dark")
        setup_styles()
        self._root.option_add("*TCombobox*Listbox.selectBackground", "#4DD0E1")
        self._root.option_add("*TCombobox*Listbox.selectForeground", "#0d0d0d")

        self._build_ui()
        self._root.after(50, self._update_from_main)
        self._root.mainloop()
        self._root = None

    def _build_ui(self):
        main_frame = tk.Frame(self._root, padx=15, pady=10)
        main_frame.pack(fill="both", expand=True)

        create_title(main_frame, self.texts, self.lang)

        # ── Bottom section packed first so mid can fill remaining space ────────
        bottom = tk.Frame(main_frame)
        bottom.pack(side="bottom", fill="x", pady=(8, 0))

        status_row = tk.Frame(bottom)
        status_row.pack()
        self.camera_label, self.loading_label = create_camera_labels(status_row, self.texts, self.lang)

        self.start_btn = create_start_button(bottom, self._toggle_camera, self.texts, self.lang)

        # ── Middle section: left | sep | right ────────────────────────────────
        mid = tk.Frame(main_frame)
        mid.pack(fill="both", expand=True, pady=(0, 4))
        mid.columnconfigure(0, weight=3)
        mid.columnconfigure(2, weight=2)
        mid.rowconfigure(0, weight=1)

        left = tk.Frame(mid)
        left.grid(row=0, column=0, sticky="nsew")

        sep = ttk.Separator(mid, orient="vertical")
        sep.grid(row=0, column=1, sticky="ns", padx=10)

        right = tk.Frame(mid)
        right.grid(row=0, column=2, sticky="nsew")

        # Left: zoom
        self.zoom_val_label, self.zoom_canvas = create_zoom_panel(
            left, self._scale_ctrl.get(), self.texts, self.lang,
            on_zoom_up=self._on_zoom_up,
            on_zoom_down=self._on_zoom_down,
        )

        # Left: gesture list
        self.gesture_list_parent = left
        self._rebuild_gesture_list()

        # Right: profile selector + buttons
        profile_names = list(self.cli_manager.profiles.keys())
        self.profile_var, self.profile_combo = create_profile_panel(
            right, profile_names, self.cli_manager.mode,
            callback=self._on_profile_change,
            texts=self.texts,
            lang=self.lang,
        )
        tk.Button(
            right,
            text=self.texts['ui']['add_profile_btn'][self.lang],
            font=FONTS["small"], bg=TEAL, fg="#0d0d0d",
            activebackground=TEAL_HOVER, activeforeground="#0d0d0d",
            relief="flat", padx=6, pady=2,
            command=self._open_profile_builder,
        ).pack(anchor="w", pady=(4, 0))

        self.delete_profile_btn = tk.Button(
            right,
            text=self.texts['ui']['delete_profile_btn'][self.lang],
            font=FONTS["small"],
            relief="flat", padx=6, pady=2,
            command=self._on_delete_profile,
        )
        self.delete_profile_btn.pack(anchor="w", pady=(2, 0))
        self._update_delete_btn()

        # Right: camera selector
        current_camera_id = self.cli_manager.main_config.get("camera_id", DEFAULT_CAMERA_ID)
        self.camera_selector = create_camera_selector(
            right, self.available_cameras, self.camera_names,
            current_camera_id,
            callback=self._on_camera_change,
            texts=self.texts,
            lang=self.lang,
        )

        # Right: language selector
        create_lang_selector(right, self.lang, self._on_lang_change)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _rebuild_ui(self):
        self.profile_var = None  # nullify in UI thread before widget destroy
        self.profile_combo = None
        self.delete_profile_btn = None
        self.camera_selector = None
        for widget in self._root.winfo_children():
            widget.destroy()
        self._build_ui()
        # Re-sync runtime state
        if self.camera_running:
            self._update_camera_ui()
        elif self.loading:
            self.camera_label.config(
                text=self.texts['ui']['camera']['starting'][self.lang],
                foreground=COLORS["warning"],
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
        # Nullify tkinter variables in UI thread before destroy to avoid
        # "main thread is not in main loop" RuntimeError on GC
        self.profile_var = None
        self.profile_combo = None
        self.delete_profile_btn = None
        if self._root:
            self._root.destroy()
        self.ui_to_main.put({"event": "quit", "data": {}})

    def _toggle_camera(self):
        self.ui_to_main.put({"event": "toggle_camera", "data": {}})

    def _on_zoom_up(self):
        self._scale_ctrl.increment(SCALE_STEP)
        update_zoom_display(self.zoom_val_label, self.zoom_canvas, self._scale_ctrl.get())

    def _on_zoom_down(self):
        self._scale_ctrl.increment(-SCALE_STEP)
        update_zoom_display(self.zoom_val_label, self.zoom_canvas, self._scale_ctrl.get())

    def _on_lang_change(self, new_lang: str):
        if new_lang == self.lang:
            return
        self.lang = new_lang
        self.cli_manager.set_lang(new_lang)
        self._rebuild_ui()

    def _on_profile_change(self, new_mode: str):
        self.cli_manager.set_profile(new_mode)
        self._rebuild_gesture_list()
        self._update_delete_btn()
        self.ui_to_main.put({"event": "profile_changed", "data": {"mode": new_mode}})

    def _on_camera_change(self, camera_id: int):
        self.cli_manager.set_camera_id(camera_id)

    def _update_delete_btn(self):
        if self.delete_profile_btn is None:
            return
        protected = self.cli_manager.mode in self._protected_profiles
        if protected:
            self.delete_profile_btn.config(
                state="disabled", bg="#555555", fg="#888888",
                activebackground="#555555", activeforeground="#888888",
            )
        else:
            self.delete_profile_btn.config(
                state="normal", bg=DANGER, fg="#ffffff",
                activebackground=DANGER_HOVER, activeforeground="#ffffff",
            )

    def _on_delete_profile(self):
        mode = self.cli_manager.mode
        if mode in self._protected_profiles:
            return

        profiles = self.json_manager.load_profiles()
        deleted_gesture_names = set(profiles[mode].values())
        profiles.pop(mode, None)
        self.json_manager.save_json("profile_config.json", profiles)
        self._cleanup_orphaned_gestures(deleted_gesture_names, profiles)

        self.cli_manager.profiles = profiles

        # Switch to first available profile
        new_mode = next(iter(profiles), "default")
        new_names = list(profiles.keys())

        if self.profile_var:
            self.profile_var.set(new_mode)
        if self.profile_combo:
            self.profile_combo["values"] = new_names

        self._on_profile_change(new_mode)

    def _cleanup_orphaned_gestures(self, deleted_names: set, remaining_profiles: dict) -> None:
        in_use = {g for p in remaining_profiles.values() for g in p.values()}
        orphaned = deleted_names - in_use
        if not orphaned:
            return
        custom_checks = {"landmark_distance", "group_landmark_distance"}
        gestures = self.json_manager.load_gestures()
        kept = [g for g in gestures
                if g["name"] not in orphaned or g.get("check") not in custom_checks]
        if len(kept) != len(gestures):
            self.json_manager.save_json("gestures.json", kept)
            self.gestures_data = kept

    def _open_profile_builder(self):
        controller = ProfileBuilderController(self.json_manager, self.lang)
        ProfileBuilderWindow(
            self._root, controller, self.lang, self.texts,
            on_save_callback=self._on_new_profile_saved,
        )

    def _on_new_profile_saved(self, name: str):
        self.cli_manager.profiles = self.json_manager.load_profiles()
        new_names = list(self.cli_manager.profiles.keys())
        if self.profile_var:
            self.profile_var.set(name)
        if self.profile_combo:
            self.profile_combo["values"] = new_names
        self._on_profile_change(name)

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
                        foreground=COLORS["warning"],
                    )
                    if self.camera_selector:
                        self.camera_selector['state'] = "disabled"

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
            foreground=COLORS["success"] if self.camera_running else COLORS["danger_text"],
        )
        update_button_state(self.start_btn, self.texts, self.lang, self.camera_running)
        self.loading_label.config(text="")
        if self.camera_selector:
            self.camera_selector['state'] = "disabled" if self.camera_running else "readonly"
