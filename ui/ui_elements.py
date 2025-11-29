import tkinter as tk
from typing import Tuple, Optional

COLORS = {
    "primary": "#4CAF50",
    "danger": "#f44336",
    "success": "green",
    "danger_text": "red",
    "warning": "orange",
    "white": "white"
}

FONTS = {
    "title": ("Arial", 16, "bold"),
    "status": ("Arial", 12),
    "status_bold": ("Arial", 12, "bold"),
    "loading": ("Arial", 10),
    "button": ("Arial", 14, "bold")
}

SPINNER_CHARS = ['|', '/', '—', '\\']

def create_title(parent: tk.Misc, texts: dict, lang: str = 'en') -> tk.Label:
    title_text = texts['ui']['title'][lang]
    title = tk.Label(parent, text=title_text, font=FONTS["title"])
    title.pack(pady=(0, 20))
    return title

def create_status_labels(parent: tk.Misc, profile_text: str) -> tk.Label:
    status_label = tk.Label(parent, text=profile_text, font=FONTS["status"])
    status_label.pack(pady=(0, 10))
    return status_label

def create_camera_labels(parent_frame: tk.Misc, texts: dict, lang: str = 'en') -> Tuple[tk.Label, tk.Label]:
    camera_label = tk.Label(
        parent_frame, 
        text=texts['ui']['camera']['stopped'][lang],
        font=FONTS["status_bold"], 
        fg=COLORS["danger_text"]
    )
    camera_label.pack()
    
    loading_label = tk.Label(
        parent_frame, 
        text="", 
        font=FONTS["loading"],
        fg=COLORS["warning"]
    )
    loading_label.pack()
    return camera_label, loading_label

def create_start_button(parent: tk.Misc, command, texts: dict, lang: str = 'en') -> tk.Button:
    btn = tk.Button(
        parent, 
        text=texts['ui']['buttons']['start'][lang],
        font=FONTS["button"],
        bg=COLORS["primary"], 
        fg=COLORS["white"],
        width=20, 
        height=2, 
        command=command
    )
    btn.pack()
    return btn

def update_button_state(btn: tk.Button, texts: dict, lang: str, running: bool):
    if running:
        btn.config(
            text=texts['ui']['buttons']['stop'][lang], 
            bg=COLORS["danger"]
        )
    else:
        btn.config(
            text=texts['ui']['buttons']['start'][lang], 
            bg=COLORS["primary"]
        )

def get_spinner_text(texts: dict, lang: str, spinner_char: str) -> str:
    return f"{texts['ui']['spinner'][lang]} {spinner_char}"
