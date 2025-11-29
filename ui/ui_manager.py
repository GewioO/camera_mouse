# ui/ui_manager.py
import threading
import queue
import tkinter as tk
from typing import Dict, Any

from json_manager import JsonManager
from cli_manager import CLIManager

from .ui_elements import (
    COLORS, FONTS, SPINNER_CHARS,
    create_title, create_status_labels, create_camera_labels, 
    create_start_button, update_button_state, get_spinner_text
)


class UIManager:
    def __init__(self, json_manager: JsonManager):
        """Ініціалізація UI менеджера"""
        self.json_manager = json_manager
        self.cli_manager = CLIManager(json_manager)
        self.texts = json_manager.load_texts()
        
        self.ui_to_main = queue.Queue()
        self.main_to_ui = queue.Queue()
        
        self._thread = None
        self._root: tk.Tk | None = None
        self._running = False
        
        self.camera_running = False
        self.loading = False
        self.spinner_index = 0
        self.lang = self.json_manager.load_main_config().get('lang', 'uk')
        
        self.status_label = None
        self.camera_label = None
        self.loading_label = None
        self.start_btn = None

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

    def _ui_mainloop(self):
        self._root = tk.Tk()
        self._root.title("AI Hand Mouse")
        self._root.geometry("420x280")
        self._root.resizable(False, False)
        
        self._build_ui()
        self._root.after(50, self._update_from_main)
        self._root.mainloop()
        self._root = None

    def _build_ui(self):
        frame = tk.Frame(self._root, padx=20, pady=20)
        frame.pack(expand=True, fill="both")
        
        create_title(frame, self.texts, self.lang)
        
        profile_text = self.texts['ui']['profile'][self.lang].format(mode=self.cli_manager.mode)
        self.status_label = create_status_labels(frame, profile_text)
        
        status_frame = tk.Frame(frame)
        status_frame.pack(pady=(0, 20))
        self.camera_label, self.loading_label = create_camera_labels(status_frame, self.texts, self.lang)
        
        self.start_btn = create_start_button(frame, self._toggle_camera, self.texts, self.lang)

    def _toggle_camera(self):
        self.ui_to_main.put({"event": "toggle_camera", "data": {}})

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
                        fg=COLORS["warning"]
                    )
                    
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
            fg=COLORS["success"] if self.camera_running else COLORS["danger_text"]
        )
        
        update_button_state(self.start_btn, self.texts, self.lang, self.camera_running)
        self.loading_label.config(text="")
