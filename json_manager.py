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

    def load_profiles(self) -> Dict[str, Dict[str, str]]:
        return self.load_json("profile_config.json", default={})

    def load_texts(self) -> Dict[str, Dict[str, str]]:
        return self.load_json("text_resources.json", default={})

    def load_gestures(self) -> List[Dict[str, Any]]:
        return self.load_json("gestures.json", default=[])

    def load_main_config(self) -> Dict[str, Any]:
        default_config = {
            "last_profile": "default",
            "lang": "uk",
            "scale": 1.5
        }
        config = self.load_json("main_config.json", default=None)
        if config is None:
            return default_config
        for key, value in default_config.items():
            config.setdefault(key, value)
        return config

    def save_main_config(self, config: Dict[str, Any]) -> None:
        self.save_json("main_config.json", config)
