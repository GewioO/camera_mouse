_PROTECTED = {
    "hand":    {"default", "scroll"},
    "forearm": {"default"},
}
# Gesture checks that are custom-created per profile (vs. built-in shared gestures)
_CUSTOM_CHECKS = {"landmark_distance", "group_landmark_distance"}


class ProfileService:
    """
    Profile/gesture business logic — protected-profile rules, profile deletion,
    and orphaned-gesture cleanup
    """

    def __init__(self, json_manager):
        self.json_manager = json_manager

    def protected_profiles(self, module: str) -> set:
        return _PROTECTED.get(module, {"default", "scroll"})

    def is_protected(self, module: str, mode: str) -> bool:
        return mode in self.protected_profiles(module)

    def delete_profile(self, module: str, mode: str) -> dict:
        profiles = self.json_manager.load_profiles(module)
        if self.is_protected(module, mode) or mode not in profiles:
            return profiles

        deleted_gesture_names = set(profiles[mode].values())
        profiles.pop(mode, None)
        self.json_manager.save_profiles(module, profiles)
        self._cleanup_orphaned_gestures(deleted_gesture_names, profiles)
        return profiles

    def _cleanup_orphaned_gestures(self, deleted_names: set, remaining_profiles: dict) -> None:
        in_use = {g for p in remaining_profiles.values() for g in p.values()}
        orphaned = deleted_names - in_use
        if not orphaned:
            return
        gestures = self.json_manager.load_gestures()
        kept = [g for g in gestures
                if g["name"] not in orphaned or g.get("check") not in _CUSTOM_CHECKS]
        if len(kept) != len(gestures):
            self.json_manager.save_json("gestures.json", kept)
