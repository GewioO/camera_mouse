import tkinter as tk
from tkinter import ttk
from typing import Tuple

TEAL        = "#4DD0E1"
TEAL_HOVER  = "#80DEEA"
TEAL_DARK   = "#00ACC1"
DANGER      = "#EF5350"
DANGER_HOVER= "#E53935"
BG_DARK     = "#1c1c1c"
BTN_DARK    = "#3c3c3c"   # inactive button bg on dark theme

COLORS = {
    "primary":     TEAL,
    "danger":      DANGER,
    "success":     TEAL,
    "danger_text": DANGER,
    "warning":     "#FFB74D",
    "separator":   "#444444",
    "bar_bg":      "#3a3a3a",
}

FONTS = {
    "title":       ("Segoe UI", 16, "bold"),
    "status":      ("Segoe UI", 11),
    "status_bold": ("Segoe UI", 11, "bold"),
    "loading":     ("Segoe UI", 10),
    "button":      ("Segoe UI", 13, "bold"),
    "small":       ("Segoe UI", 9),
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


def setup_styles() -> None:
    s = ttk.Style()

    s.configure("Teal.TButton",
                background=TEAL, foreground="#0d0d0d",
                font=FONTS["button"], padding=(20, 10))
    s.map("Teal.TButton",
          background=[("active", TEAL_HOVER), ("pressed", TEAL_DARK)])

    s.configure("Danger.TButton",
                background=DANGER, foreground="#ffffff",
                font=FONTS["button"], padding=(20, 10))
    s.map("Danger.TButton",
          background=[("active", DANGER_HOVER)])

    s.configure("Zoom.TButton", font=FONTS["small"], padding=(4, 2))

    s.configure("LangActive.TButton",
                background=TEAL, foreground="#0d0d0d",
                font=FONTS["small"], padding=(6, 3))
    s.map("LangActive.TButton",
          background=[("active", TEAL_HOVER)])

    s.configure("LangInactive.TButton", font=FONTS["small"], padding=(6, 3))

    s.configure("TCombobox", font=FONTS["status"])


# ── Title ─────────────────────────────────────────────────────────────────────

def create_title(parent: tk.Misc, texts: dict, lang: str = 'en') -> ttk.Label:
    label = ttk.Label(parent, text=texts['ui']['title'][lang], font=FONTS["title"])
    label.pack(pady=(0, 10))
    return label


# ── Camera status row ─────────────────────────────────────────────────────────

def create_camera_labels(parent: tk.Misc, texts: dict, lang: str = 'en') -> Tuple[ttk.Label, ttk.Label]:
    camera_label = ttk.Label(
        parent,
        text=texts['ui']['camera']['stopped'][lang],
        font=FONTS["status_bold"],
        foreground=COLORS["danger_text"],
    )
    camera_label.pack(side="left")

    loading_label = ttk.Label(parent, text="", font=FONTS["loading"],
                               foreground=COLORS["warning"])
    loading_label.pack(side="left", padx=(8, 0))

    return camera_label, loading_label


# ── Start / Stop button ───────────────────────────────────────────────────────

def create_start_button(parent: tk.Misc, command, texts: dict, lang: str = 'en') -> tk.Button:
    btn = tk.Button(
        parent,
        text=texts['ui']['buttons']['start'][lang],
        font=FONTS["button"],
        bg=TEAL, fg="#0d0d0d",
        activebackground=TEAL_HOVER, activeforeground="#0d0d0d",
        relief="flat", borderwidth=0,
        padx=20, pady=8,
        command=command,
    )
    btn.pack(pady=(8, 0))
    return btn


def update_button_state(btn: tk.Button, texts: dict, lang: str, running: bool) -> None:
    if running:
        btn.config(
            text=texts['ui']['buttons']['stop'][lang],
            bg=DANGER, fg="#ffffff",
            activebackground=DANGER_HOVER, activeforeground="#ffffff",
        )
    else:
        btn.config(
            text=texts['ui']['buttons']['start'][lang],
            bg=TEAL, fg="#0d0d0d",
            activebackground=TEAL_HOVER, activeforeground="#0d0d0d",
        )


def get_spinner_text(texts: dict, lang: str, spinner_char: str) -> str:
    return f"{texts['ui']['spinner'][lang]} {spinner_char}"


# ── Zoom panel ────────────────────────────────────────────────────────────────

def _draw_zoom_bar(canvas: tk.Canvas, scale: float) -> None:
    canvas.delete("all")
    ratio = (scale - ZOOM_MIN) / (ZOOM_MAX - ZOOM_MIN)
    filled = int(ZOOM_BAR_W * ratio)
    canvas.create_rectangle(0, 0, ZOOM_BAR_W, ZOOM_BAR_H,
                             fill=COLORS["bar_bg"], outline="")
    if filled > 0:
        canvas.create_rectangle(0, 0, filled, ZOOM_BAR_H,
                                 fill=TEAL, outline="")


def create_zoom_panel(
    parent: tk.Misc, scale: float, texts: dict, lang: str,
    on_zoom_up, on_zoom_down,
) -> Tuple[ttk.Label, tk.Canvas]:
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=(0, 4))

    ttk.Label(row, text=f"{texts['ui']['zoom'][lang]}:",
               font=FONTS["status_bold"]).pack(side="left")
    val_label = ttk.Label(row, text=f" {scale:.1f}x",
                           font=FONTS["status_bold"], foreground=TEAL)
    val_label.pack(side="left")

    ttk.Button(row, text="+", style="Zoom.TButton", width=3,
               command=on_zoom_up).pack(side="right", padx=(2, 0))
    ttk.Button(row, text="−", style="Zoom.TButton", width=3,
               command=on_zoom_down).pack(side="right")

    bg = ttk.Style().lookup("TFrame", "background") or BG_DARK
    canvas = tk.Canvas(parent, width=ZOOM_BAR_W, height=ZOOM_BAR_H,
                        highlightthickness=0, bg=bg)
    canvas.pack(anchor="w", pady=(0, 10))
    _draw_zoom_bar(canvas, scale)

    return val_label, canvas


def update_zoom_display(val_label: ttk.Label, canvas: tk.Canvas, scale: float) -> None:
    val_label.config(text=f" {scale:.1f}x")
    _draw_zoom_bar(canvas, scale)


# ── Gesture list ──────────────────────────────────────────────────────────────

def create_gesture_list(
    parent: tk.Misc, profile: dict, gestures_data: list,
    texts: dict, lang: str,
) -> ttk.Frame:
    frame = ttk.Frame(parent)
    frame.pack(fill="x", anchor="w")

    ttk.Label(frame, text=texts['ui']['gestures_title'][lang],
               font=FONTS["status_bold"]).pack(anchor="w", pady=(0, 2))

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

        ttk.Label(frame, text=line, font=FONTS["status"],
                   anchor="w", justify="left").pack(anchor="w", padx=(2, 0))

    return frame


# ── Camera selector ───────────────────────────────────────────────────────────

def create_camera_selector(
    parent: tk.Misc,
    cameras: list,
    camera_names: list,
    current_id: int,
    callback,
    texts: dict,
    lang: str,
) -> ttk.Combobox:
    ttk.Label(parent, text=texts['ui']['camera_label'][lang],
               font=FONTS["status_bold"]).pack(anchor="w", pady=(8, 4))

    current_name = camera_names[cameras.index(current_id)] if current_id in cameras else camera_names[0]
    var = tk.StringVar(value=current_name)
    combo = ttk.Combobox(parent, textvariable=var, values=camera_names,
                          state="readonly", width=14, font=FONTS["status"])

    def _on_select(event):
        selected = var.get()
        idx = camera_names.index(selected)
        callback(cameras[idx])

    combo.bind("<<ComboboxSelected>>", _on_select)
    combo.pack(anchor="w")
    return combo


# ── Language selector ─────────────────────────────────────────────────────────

def create_lang_selector(parent: tk.Misc, current_lang: str, callback) -> None:
    ttk.Label(parent, text="🌐", font=FONTS["status_bold"]).pack(anchor="w", pady=(12, 4))

    row = ttk.Frame(parent)
    row.pack(anchor="w")

    for code, label in [("uk", "UA"), ("en", "EN")]:
        active = code == current_lang
        tk.Button(
            row, text=label, font=FONTS["small"],
            bg=TEAL if active else BTN_DARK,
            fg="#0d0d0d" if active else "#cccccc",
            activebackground=TEAL_HOVER if active else "#555555",
            activeforeground="#0d0d0d",
            relief="flat", borderwidth=0,
            padx=8, pady=3,
            command=lambda c=code: callback(c),
        ).pack(side="left", padx=(0, 4))


# ── Profile selector ──────────────────────────────────────────────────────────

def create_profile_panel(
    parent: tk.Misc, profiles: list, current_mode: str,
    callback, texts: dict, lang: str,
) -> Tuple[tk.StringVar, ttk.Combobox]:
    ttk.Label(parent, text=texts['ui']['profile_label'][lang],
               font=FONTS["status_bold"]).pack(anchor="w", pady=(0, 4))

    var = tk.StringVar(value=current_mode)
    combo = ttk.Combobox(parent, textvariable=var, values=profiles,
                          state="readonly", width=14, font=FONTS["status"])
    combo.bind("<<ComboboxSelected>>", lambda e: callback(var.get()))
    combo.pack(anchor="w")

    return var, combo
