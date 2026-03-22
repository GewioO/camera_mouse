import tkinter as tk
from typing import Tuple

COLORS = {
    "primary":    "#4CAF50",
    "danger":     "#f44336",
    "success":    "green",
    "danger_text": "red",
    "warning":    "orange",
    "white":      "white",
    "separator":  "#cccccc",
    "bar_bg":     "#e0e0e0",
}

FONTS = {
    "title":       ("Arial", 16, "bold"),
    "status":      ("Arial", 12),
    "status_bold": ("Arial", 12, "bold"),
    "loading":     ("Arial", 10),
    "button":      ("Arial", 14, "bold"),
    "small":       ("Arial", 10),
}

SPINNER_CHARS = ['|', '/', '—', '\\']

ACTION_ICONS = {
    "mouse_move":   "▶",
    "click":        "●",
    "double_click": "●●",
    "drag":         "⟷",
    "scroll_up":    "▲",
    "scroll_down":  "▼",
}

ZOOM_MIN = 1.0
ZOOM_MAX = 3.0
ZOOM_BAR_W = 160
ZOOM_BAR_H = 10


# ── Title ─────────────────────────────────────────────────────────────────────

def create_title(parent: tk.Misc, texts: dict, lang: str = 'en') -> tk.Label:
    title = tk.Label(parent, text=texts['ui']['title'][lang], font=FONTS["title"])
    title.pack(pady=(0, 10))
    return title


# ── Camera status row ─────────────────────────────────────────────────────────

def create_camera_labels(parent: tk.Misc, texts: dict, lang: str = 'en') -> Tuple[tk.Label, tk.Label]:
    camera_label = tk.Label(
        parent,
        text=texts['ui']['camera']['stopped'][lang],
        font=FONTS["status_bold"],
        fg=COLORS["danger_text"],
    )
    camera_label.pack(side="left")

    loading_label = tk.Label(parent, text="", font=FONTS["loading"], fg=COLORS["warning"])
    loading_label.pack(side="left", padx=(8, 0))

    return camera_label, loading_label


# ── Start / Stop button ───────────────────────────────────────────────────────

def create_start_button(parent: tk.Misc, command, texts: dict, lang: str = 'en') -> tk.Button:
    btn = tk.Button(
        parent,
        text=texts['ui']['buttons']['start'][lang],
        font=FONTS["button"],
        bg=COLORS["primary"],
        fg=COLORS["white"],
        width=22,
        height=2,
        command=command,
    )
    btn.pack(pady=(8, 0))
    return btn


def update_button_state(btn: tk.Button, texts: dict, lang: str, running: bool):
    if running:
        btn.config(text=texts['ui']['buttons']['stop'][lang], bg=COLORS["danger"])
    else:
        btn.config(text=texts['ui']['buttons']['start'][lang], bg=COLORS["primary"])


def get_spinner_text(texts: dict, lang: str, spinner_char: str) -> str:
    return f"{texts['ui']['spinner'][lang]} {spinner_char}"


# ── Zoom panel ────────────────────────────────────────────────────────────────

def _draw_zoom_bar(canvas: tk.Canvas, scale: float):
    canvas.delete("all")
    ratio = (scale - ZOOM_MIN) / (ZOOM_MAX - ZOOM_MIN)
    filled = int(ZOOM_BAR_W * ratio)
    canvas.create_rectangle(0, 0, ZOOM_BAR_W, ZOOM_BAR_H, fill=COLORS["bar_bg"], outline="#aaa")
    if filled > 0:
        canvas.create_rectangle(0, 0, filled, ZOOM_BAR_H, fill=COLORS["primary"], outline="")


def create_zoom_panel(
    parent: tk.Misc, scale: float, texts: dict, lang: str,
    on_zoom_up, on_zoom_down,
) -> Tuple[tk.Label, tk.Canvas]:
    row = tk.Frame(parent)
    row.pack(fill="x", pady=(0, 4))

    tk.Label(row, text=f"{texts['ui']['zoom'][lang]}:", font=FONTS["status_bold"]).pack(side="left")
    val_label = tk.Label(row, text=f" {scale:.1f}x", font=FONTS["status_bold"])
    val_label.pack(side="left")

    tk.Button(row, text="+", font=FONTS["small"], width=2, command=on_zoom_up).pack(side="right", padx=(2, 0))
    tk.Button(row, text="−", font=FONTS["small"], width=2, command=on_zoom_down).pack(side="right")

    canvas = tk.Canvas(parent, width=ZOOM_BAR_W, height=ZOOM_BAR_H, highlightthickness=0)
    canvas.pack(anchor="w", pady=(0, 10))
    _draw_zoom_bar(canvas, scale)

    return val_label, canvas


def update_zoom_display(val_label: tk.Label, canvas: tk.Canvas, scale: float):
    val_label.config(text=f" {scale:.1f}x")
    _draw_zoom_bar(canvas, scale)


# ── Gesture list ──────────────────────────────────────────────────────────────

def create_gesture_list(
    parent: tk.Misc, profile: dict, gestures_data: list, texts: dict, lang: str,
) -> tk.Frame:
    frame = tk.Frame(parent)
    frame.pack(fill="x", anchor="w")

    tk.Label(frame, text=texts['ui']['gestures_title'][lang], font=FONTS["status_bold"]).pack(anchor="w", pady=(0, 2))

    gesture_map = {g["name"]: g for g in gestures_data}
    actions_texts = texts.get("actions", {})

    for action, gesture_name in profile.items():
        icon = ACTION_ICONS.get(action, "•")
        action_label = actions_texts.get(action, {}).get(lang, action)

        if gesture_name == "dummy":
            line = f"{icon}  {action_label}"
        else:
            gesture = gesture_map.get(gesture_name, {})
            desc = gesture.get(f"description_{lang}", gesture_name)
            line = f"{icon}  {action_label}: {desc}"

        tk.Label(frame, text=line, font=FONTS["status"], anchor="w", justify="left").pack(anchor="w", padx=(2, 0))

    return frame


# ── Profile selector ──────────────────────────────────────────────────────────

def create_profile_panel(
    parent: tk.Misc, profiles: list, current_mode: str,
    callback, texts: dict, lang: str,
) -> tk.StringVar:
    tk.Label(parent, text=texts['ui']['profile_label'][lang], font=FONTS["status_bold"]).pack(anchor="w", pady=(0, 4))

    var = tk.StringVar(value=current_mode)
    menu = tk.OptionMenu(parent, var, *profiles, command=callback)
    menu.config(font=FONTS["status"], width=12)
    menu.pack(anchor="w")

    return var
