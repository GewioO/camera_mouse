from json_manager import JsonManager
from ui.ui_elements import ACTION_ICONS
from constants import FINGER_TIPS   # {"thumb":4, "index":8, "middle":12, "ring":16, "pinky":20}

_CUSTOM_CHECKS = ("landmark_distance", "group_landmark_distance")


class ProfileBuilderController:
    def __init__(self, json_manager: JsonManager, lang: str):
        self.json_manager = json_manager
        self.lang = lang
        self._reload_gestures()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _reload_gestures(self):
        all_gestures = self.json_manager.load_gestures()
        self.all_gestures = all_gestures
        self.touch_gestures   = [g for g in all_gestures if g.get("check") in ("touch", "group_touch")]
        self.special_gestures = [g for g in all_gestures if g.get("special", False)]

        # frozenset[landmark IDs] → gesture dict (both predefined and custom)
        self._landmark_index: dict[frozenset, dict] = {}
        for g in self.touch_gestures:
            key = frozenset(FINGER_TIPS[f] for f in g["fingers"])
            self._landmark_index[key] = g
        for g in all_gestures:
            if g.get("check") in _CUSTOM_CHECKS:
                key = frozenset(g["args"]["landmark_ids"])
                self._landmark_index[key] = g

    # ── Public API ────────────────────────────────────────────────────────────

    def match_landmarks(self, landmark_ids: set[int]) -> dict | None:
        """Return gesture matching this exact set of landmark IDs, or None."""
        return self._landmark_index.get(frozenset(landmark_ids))

    def get_or_create_landmark_gesture(self, landmark_ids: set[int]) -> dict:
        """
        Return existing gesture for these landmarks, or create + save a new one.
        Used for arbitrary (non-tip) landmark combinations.
        """
        existing = self.match_landmarks(landmark_ids)
        if existing:
            return existing

        sorted_ids = sorted(landmark_ids)
        name = "lm_" + "_".join(str(i) for i in sorted_ids)
        ids_uk = " і ".join(str(i) for i in sorted_ids) if len(sorted_ids) == 2 \
                 else ", ".join(str(i) for i in sorted_ids)
        ids_en = " and ".join(str(i) for i in sorted_ids) if len(sorted_ids) == 2 \
                 else ", ".join(str(i) for i in sorted_ids)

        check = "landmark_distance" if len(sorted_ids) == 2 else "group_landmark_distance"
        new_gesture = {
            "name": name,
            "description_uk": f"Точки {ids_uk}",
            "description_en": f"Points {ids_en}",
            "check": check,
            "args": {
                "landmark_ids": sorted_ids,
                "distance_threshold": 40,
            },
        }

        gestures = self.json_manager.load_gestures()
        gestures.append(new_gesture)
        self.json_manager.save_json("gestures.json", gestures)
        self._reload_gestures()
        return new_gesture

    def get_action_names(self) -> list:
        """All bindable actions (excludes mouse_move, which is a checkbox)."""
        return [a for a in ACTION_ICONS if a != "mouse_move"]

    def save_profile(self, name: str, bindings: dict, mouse_move: bool) -> None:
        """Add new profile to profile_config.json."""
        profiles = self.json_manager.load_profiles()
        profile = dict(bindings)
        if mouse_move:
            profile["mouse_move"] = "dummy"
        profiles[name] = profile
        self.json_manager.save_json("profile_config.json", profiles)
