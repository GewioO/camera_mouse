import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable

from .profile_builder_controller import ProfileBuilderController
from .ui_elements import (
    TEAL, TEAL_HOVER, TEAL_DARK, BG_DARK, BTN_DARK,
    FONTS, ACTION_ICONS,
)

# ── Hand landmark geometry ─────────────────────────────────────────────────────

LANDMARK_POS = {
    0:  (0.50, 0.95), 1:  (0.35, 0.80), 2:  (0.25, 0.65), 3:  (0.15, 0.52), 4:  (0.07, 0.40),
    5:  (0.38, 0.68), 6:  (0.36, 0.52), 7:  (0.35, 0.38), 8:  (0.34, 0.25),
    9:  (0.50, 0.65), 10: (0.50, 0.48), 11: (0.50, 0.34), 12: (0.50, 0.20),
    13: (0.62, 0.66), 14: (0.63, 0.50), 15: (0.64, 0.37), 16: (0.65, 0.24),
    17: (0.74, 0.70), 18: (0.76, 0.56), 19: (0.77, 0.44), 20: (0.79, 0.32),
}

CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17),
]

TIP_IDS = {4, 8, 12, 16, 20}

# Tips checked first for click priority when landmarks are close
_HIT_ORDER = sorted(range(21), key=lambda lid: (0 if lid in TIP_IDS else 1))

CANVAS_W = 190
CANVAS_H = 230


class ProfileBuilderWindow:
    def __init__(
        self,
        parent_root: tk.Tk,
        controller: ProfileBuilderController,
        lang: str,
        texts: dict,
        on_save_callback: Callable[[str], None],
    ):
        self.controller = controller
        self.lang = lang
        self.texts = texts
        self.on_save_callback = on_save_callback

        self._selected_landmarks: set[int] = set()   # individual landmark IDs
        self._current_gesture: Optional[dict] = None
        self._selected_fist: Optional[dict] = None
        self._bindings: dict = {}                    # action_name → gesture_name
        self._fist_tile_frames: dict = {}

        self.win = tk.Toplevel(parent_root)
        self.win.title(self._t("builder_title"))
        self.win.resizable(False, False)
        self.win.grab_set()

        self._build_ui()
        self.win.update_idletasks()

    # ── Text helper ───────────────────────────────────────────────────────────

    def _t(self, key: str) -> str:
        return self.texts.get("profile_builder", {}).get(key, {}).get(self.lang, key)

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = tk.Frame(self.win, padx=12, pady=8)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text=self._t("builder_title"), font=FONTS["title"]).pack(pady=(0, 8))

        # ── Top: palm canvas + fist tiles ─────────────────────────────────────
        top = tk.Frame(outer)
        top.pack(fill="x")

        palm_frame = tk.Frame(top)
        palm_frame.pack(side="left", fill="y", anchor="n")
        ttk.Label(palm_frame, text=self._t("palm_section"), font=FONTS["small"]).pack(anchor="w")
        self._palm_canvas = tk.Canvas(
            palm_frame, width=CANVAS_W, height=CANVAS_H,
            bg="#2a2a2a", highlightthickness=1, highlightbackground="#555555",
        )
        self._palm_canvas.pack()
        self._draw_palm()
        self._palm_canvas.bind("<Button-1>", self._on_palm_click)

        fist_outer = tk.Frame(top, padx=10)
        fist_outer.pack(side="left", fill="both", expand=True, anchor="n")
        ttk.Label(fist_outer, text=self._t("special_section"), font=FONTS["small"]).pack(anchor="w")
        self._build_fist_tiles(fist_outer)

        # ── Gesture display + action row ──────────────────────────────────────
        mid = tk.Frame(outer)
        mid.pack(fill="x", pady=(8, 2))

        gesture_row = tk.Frame(mid)
        gesture_row.pack(fill="x")
        ttk.Label(gesture_row, text=self._t("gesture_label"), font=FONTS["status_bold"]).pack(side="left")
        self._gesture_label = ttk.Label(
            gesture_row, text=self._t("no_gesture"),
            font=FONTS["status"], foreground="#888888",
        )
        self._gesture_label.pack(side="left", padx=(6, 0))

        action_row = tk.Frame(mid)
        action_row.pack(fill="x", pady=(4, 0))
        ttk.Label(action_row, text=self._t("action_label"), font=FONTS["status_bold"]).pack(side="left")

        self._action_names = self.controller.get_action_names()
        action_texts = self.texts.get("actions", {})
        self._action_display = [
            action_texts.get(a, {}).get(self.lang, a) for a in self._action_names
        ]

        self._action_var = tk.StringVar(value=self._action_display[0] if self._action_display else "")
        self._action_combo = ttk.Combobox(
            action_row, textvariable=self._action_var,
            values=self._action_display,
            state="readonly", width=16, font=FONTS["status"],
        )
        self._action_combo.pack(side="left", padx=(6, 8))
        self._action_combo.bind("<<ComboboxSelected>>", lambda e: self._update_add_btn())

        self._add_btn = tk.Button(
            action_row, text=self._t("add_btn"),
            font=FONTS["small"], bg="#555555", fg="#888888",
            activebackground="#555555", activeforeground="#888888",
            relief="flat", padx=8, pady=3, state="disabled",
            command=self._on_add_binding,
        )
        self._add_btn.pack(side="left")

        # ── Bindings list ─────────────────────────────────────────────────────
        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(6, 0))
        ttk.Label(outer, text=self._t("bindings_title"), font=FONTS["status_bold"]).pack(anchor="w", pady=(4, 2))

        self._bindings_frame = tk.Frame(outer)
        self._bindings_frame.pack(fill="x", anchor="w")

        # ── Bottom controls ───────────────────────────────────────────────────
        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(6, 0))
        bottom = tk.Frame(outer)
        bottom.pack(fill="x", pady=(6, 0))

        self._mouse_move_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            bottom, text=self._t("mouse_move_check"),
            variable=self._mouse_move_var,
            font=FONTS["status"],
            bg=self.win.cget("bg"), fg="#cccccc",
            selectcolor="#444444",
            activebackground=self.win.cget("bg"),
            activeforeground="#cccccc",
        ).pack(anchor="w")

        name_row = tk.Frame(bottom)
        name_row.pack(fill="x", anchor="w", pady=(4, 0))
        ttk.Label(name_row, text=self._t("name_label"), font=FONTS["status_bold"]).pack(side="left")
        self._name_var = tk.StringVar()
        ttk.Entry(name_row, textvariable=self._name_var, width=22, font=FONTS["status"]).pack(side="left", padx=(6, 0))

        btn_row = tk.Frame(bottom)
        btn_row.pack(pady=(8, 0))

        tk.Button(
            btn_row, text=self._t("save_btn"),
            font=FONTS["button"], bg=TEAL, fg="#0d0d0d",
            activebackground=TEAL_HOVER, activeforeground="#0d0d0d",
            relief="flat", padx=20, pady=8,
            command=self._on_save,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_row, text=self._t("back_btn"),
            font=FONTS["button"], bg=BTN_DARK, fg="#cccccc",
            activebackground="#555555", activeforeground="#cccccc",
            relief="flat", padx=20, pady=8,
            command=self.win.destroy,
        ).pack(side="left")

    # ── Fist tiles ────────────────────────────────────────────────────────────

    def _build_fist_tiles(self, parent: tk.Frame):
        for gesture in self.controller.special_gestures:
            desc = gesture.get(f"description_{self.lang}", gesture["name"])
            tile = tk.Frame(
                parent,
                highlightthickness=2, highlightbackground="#555555",
                padx=6, pady=4, cursor="hand2", bg="#2a2a2a",
            )
            tile.pack(fill="x", pady=2)
            lbl = tk.Label(
                tile, text=desc, font=FONTS["small"],
                bg="#2a2a2a", fg="#cccccc",
                wraplength=280, justify="left",
            )
            lbl.pack(anchor="w")
            self._fist_tile_frames[gesture["name"]] = tile

            def _handler(e=None, g=gesture, t=tile):
                self._on_fist_click(g, t)

            tile.bind("<Button-1>", _handler)
            lbl.bind("<Button-1>", _handler)

    # ── Palm canvas ───────────────────────────────────────────────────────────

    def _draw_palm(self):
        c = self._palm_canvas
        c.delete("all")

        for a, b in CONNECTIONS:
            ax, ay = LANDMARK_POS[a]
            bx, by = LANDMARK_POS[b]
            c.create_line(
                int(ax * CANVAS_W), int(ay * CANVAS_H),
                int(bx * CANVAS_W), int(by * CANVAS_H),
                fill="#555555", width=2,
            )

        for lid, (nx, ny) in LANDMARK_POS.items():
            x = int(nx * CANVAS_W)
            y = int(ny * CANVAS_H)
            selected = lid in self._selected_landmarks
            is_tip = lid in TIP_IDS
            is_wrist = lid == 0
            r = 8 if is_tip else (4 if is_wrist else 5)

            if selected:
                fill, outline, w = TEAL, TEAL_DARK, 2
            elif is_wrist:
                fill, outline, w = "#333333", "#555555", 1
            elif is_tip:
                fill, outline, w = "#666666", "#888888", 1
            else:
                fill, outline, w = "#444444", "#666666", 1

            c.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline=outline, width=w)

    def _on_palm_click(self, event):
        for lid in _HIT_ORDER:
            nx, ny = LANDMARK_POS[lid]
            x = int(nx * CANVAS_W)
            y = int(ny * CANVAS_H)
            hit_r = 11 if lid in TIP_IDS else 7
            if abs(event.x - x) <= hit_r and abs(event.y - y) <= hit_r:
                if lid in self._selected_landmarks:
                    self._selected_landmarks.discard(lid)
                else:
                    self._selected_landmarks.add(lid)
                self._deselect_fist()
                self._update_gesture_from_landmarks()
                self._draw_palm()
                return

    # ── Fist selection ────────────────────────────────────────────────────────

    def _on_fist_click(self, gesture: dict, tile: tk.Frame):
        self._selected_landmarks.clear()
        self._draw_palm()
        self._deselect_fist()
        self._selected_fist = gesture
        tile.config(highlightbackground=TEAL)
        self._current_gesture = gesture
        self._update_gesture_label()
        self._update_add_btn()

    def _deselect_fist(self):
        if self._selected_fist:
            t = self._fist_tile_frames.get(self._selected_fist["name"])
            if t:
                t.config(highlightbackground="#555555")
            self._selected_fist = None

    # ── State updates ─────────────────────────────────────────────────────────

    def _update_gesture_from_landmarks(self):
        self._current_gesture = (
            self.controller.match_landmarks(self._selected_landmarks)
            if self._selected_landmarks else None
        )
        self._update_gesture_label()
        self._update_add_btn()

    def _update_gesture_label(self):
        if self._current_gesture:
            desc = self._current_gesture.get(f"description_{self.lang}", self._current_gesture["name"])
            self._gesture_label.config(text=desc, foreground=TEAL)
        elif len(self._selected_landmarks) >= 2:
            # Custom (non-predefined) combination — show point IDs in orange
            ids_str = ", ".join(str(i) for i in sorted(self._selected_landmarks))
            label = f"Точки {ids_str}" if self.lang == "uk" else f"Points {ids_str}"
            self._gesture_label.config(text=label, foreground="#FFB74D")
        else:
            self._gesture_label.config(text=self._t("no_gesture"), foreground="#888888")

    def _update_add_btn(self):
        action_ok = bool(self._action_var.get())

        if self._selected_fist is not None:
            already_bound = self._selected_fist["name"] in self._bindings.values()
            can_add = action_ok and not already_bound

        elif len(self._selected_landmarks) >= 2:
            gesture = self._current_gesture
            if gesture is not None:
                candidate_name = gesture["name"]
            else:
                # Name that would be auto-generated
                candidate_name = "lm_" + "_".join(str(i) for i in sorted(self._selected_landmarks))
            already_bound = candidate_name in self._bindings.values()
            can_add = action_ok and not already_bound

        else:
            can_add = False

        if can_add:
            self._add_btn.config(
                state="normal", bg=TEAL, fg="#0d0d0d",
                activebackground=TEAL_HOVER, activeforeground="#0d0d0d",
            )
        else:
            self._add_btn.config(
                state="disabled", bg="#555555", fg="#888888",
                activebackground="#555555", activeforeground="#888888",
            )

    # ── Binding actions ───────────────────────────────────────────────────────

    def _on_add_binding(self):
        display = self._action_var.get()
        if display not in self._action_display:
            return
        action = self._action_names[self._action_display.index(display)]

        if self._selected_fist is not None:
            gesture = self._selected_fist
        elif self._current_gesture is not None:
            gesture = self._current_gesture
        else:
            # Auto-create landmark gesture for this custom combination
            gesture = self.controller.get_or_create_landmark_gesture(self._selected_landmarks)
            self._current_gesture = gesture
            self._update_gesture_label()

        self._bindings[action] = gesture["name"]
        self._rebuild_bindings_list()

    def _rebuild_bindings_list(self):
        for w in self._bindings_frame.winfo_children():
            w.destroy()

        action_texts = self.texts.get("actions", {})
        gesture_map = {g["name"]: g for g in self.controller.all_gestures}

        for action, gesture_name in self._bindings.items():
            icon = ACTION_ICONS.get(action, "•")
            action_label = action_texts.get(action, {}).get(self.lang, action)
            gesture = gesture_map.get(gesture_name, {})
            desc = gesture.get(f"description_{self.lang}", gesture_name)

            row = tk.Frame(self._bindings_frame)
            row.pack(fill="x", anchor="w", pady=1)

            tk.Button(
                row, text="−", font=FONTS["small"],
                bg="#555555", fg="#cccccc",
                activebackground="#666666",
                relief="flat", padx=5, pady=1,
                command=lambda a=action: self._remove_binding(a),
            ).pack(side="left", padx=(0, 6))

            ttk.Label(
                row, text=f"{icon}  {action_label}: {desc}",
                font=FONTS["status"], anchor="w",
            ).pack(side="left")

        # re-evaluate Add button — removing a binding may re-enable it
        self._update_add_btn()

    def _remove_binding(self, action: str):
        self._bindings.pop(action, None)
        self._rebuild_bindings_list()

    # ── Save ──────────────────────────────────────────────────────────────────

    def _on_save(self):
        name = self._name_var.get().strip()
        err_title = self._t("error_title")

        if not name:
            messagebox.showerror(err_title, self._t("error_name_empty"), parent=self.win)
            return

        if name in self.controller.json_manager.load_profiles():
            messagebox.showerror(err_title, self._t("error_name_exists"), parent=self.win)
            return

        if not self._bindings and not self._mouse_move_var.get():
            messagebox.showerror(err_title, self._t("error_no_bindings"), parent=self.win)
            return

        self.controller.save_profile(name, self._bindings, self._mouse_move_var.get())
        self.on_save_callback(name)
        self.win.destroy()
