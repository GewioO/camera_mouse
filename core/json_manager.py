import json
import os
from typing import Any, Dict, List


class JsonManager:
    def __init__(self, base_dir: str = "res"):
        self.base_dir = base_dir

    def _full_path(self, filename: str) -> str:
        return os.path.join(self.base_dir, filename)

    def load_json(self, filename: str, default: Any = None) -> Any:
        path = self._full_path(filename)
        if not os.path.exists(path):
            return default
        with open(path, encoding="utf-8") as file:
            return json.load(file)

    def save_json(self, filename: str, data: Any) -> None:
        path = self._full_path(filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

    def load_profiles(self, module: str | None = None) -> Dict[str, Dict[str, str]]:
        data = self.load_json("profile_config.json", default={})

        needs_save = False
        # Migration: module rename stump → forearm
        if "stump" in data and "forearm" not in data:
            data["forearm"] = data.pop("stump")
            needs_save = True
        elif "stump" in data:
            data.pop("stump")
            needs_save = True

        if data and not any(k in data for k in ("hand", "forearm", "eyes")):
            data = {"hand": data}
            needs_save = True

        if "forearm" not in data:
            data["forearm"] = {"default": {}}
            needs_save = True
        elif "default" not in data["forearm"]:
            data["forearm"]["default"] = {}
            needs_save = True

        if needs_save:
            self.save_json("profile_config.json", data)

        if module is not None:
            return data.get(module, {})
        return data

    def save_profiles(self, module: str, profiles: Dict[str, Dict[str, str]]) -> None:
        data = self.load_json("profile_config.json", default={})
        if "stump" in data and "forearm" not in data:
            data["forearm"] = data.pop("stump")
        if data and not any(k in data for k in ("hand", "forearm", "eyes")):
            data = {"hand": data}
        data[module] = profiles
        self.save_json("profile_config.json", data)

    def load_texts(self) -> Dict[str, Dict[str, str]]:
        return self.load_json("text_resources.json", default={})

    def load_gestures(self) -> List[Dict[str, Any]]:
        return self.load_json("gestures.json", default=[])

    def load_main_config(self) -> Dict[str, Any]:
        default_config = {
            "last_profile_hand": "default",
            "last_profile_forearm": "default",
            "lang": "uk",
            "scale": 1.5,
            "camera_id": 0,
            "active_module": "hand",
            "forearm_side": "right",
        }
        config = self.load_json("main_config.json", default=None)
        if config is None:
            return default_config
        # Migration: last_profile → last_profile_hand
        if "last_profile" in config and "last_profile_hand" not in config:
            config["last_profile_hand"] = config.pop("last_profile")
        elif "last_profile" in config:
            config.pop("last_profile")
        # Migration: module rename stump → forearm
        if "last_profile_stump" in config and "last_profile_forearm" not in config:
            config["last_profile_forearm"] = config.pop("last_profile_stump")
        else:
            config.pop("last_profile_stump", None)
        if "stump_side" in config and "forearm_side" not in config:
            config["forearm_side"] = config.pop("stump_side")
        else:
            config.pop("stump_side", None)
        if config.get("active_module") == "stump":
            config["active_module"] = "forearm"
        for key, value in default_config.items():
            config.setdefault(key, value)
        return config

    def save_main_config(self, config: Dict[str, Any]) -> None:
        self.save_json("main_config.json", config)
