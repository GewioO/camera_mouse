import argparse
from core.json_manager import JsonManager


class CLIManager:
    def __init__(self, json_manager: JsonManager | None = None):
        self.json_manager = json_manager or JsonManager()

        self.main_config = self.json_manager.load_main_config()
        self.active_module = self.main_config.get("active_module", "hand")

        self.profiles = self.json_manager.load_profiles(self.active_module)

        profile_names = list(self.profiles.keys())
        fixed_modes = ["help", "configuration"]
        all_modes = sorted(list(set(profile_names + fixed_modes)))

        self.parser = argparse.ArgumentParser(add_help=False)
        self.parser.add_argument(
            "mode",
            nargs="?",
            default=None,
            choices=all_modes,
            help="profile or command"
        )
        self.parser.add_argument(
            "--lang",
            choices=["uk", "en"],
            default=None,
            help="interface language"
        )
        self.args = self.parser.parse_args()

        self.texts = self.json_manager.load_texts()

        self.lang = self.args.lang or self.main_config.get("lang", "uk")

        last_key = f"last_profile_{self.active_module}"
        if self.args.mode is not None:
            self.mode = self.args.mode
        else:
            stored_mode = self.main_config.get(last_key, "default")
            if stored_mode == "help" or stored_mode not in self.profiles:
                stored_mode = next(
                    (name for name in self.profiles.keys() if name != "help"),
                    "default"
                )
            self.mode = stored_mode

        if self.mode in self.profiles:
            self.current_profile = self.profiles[self.mode]
        else:
            self.current_profile = {}

        if self.mode in self.profiles:
            self.main_config[last_key] = self.mode
        self.main_config["lang"] = self.lang
        self.json_manager.save_main_config(self.main_config)

    def get_text(self, key: str) -> str:
        return self.texts.get(key, {}).get(self.lang, self.texts.get(key, {}).get("uk", key))

    def show_help(self) -> None:
        print(self.get_text("help"))

    def is_help_requested(self) -> bool:
        return self.mode == "help"

    def persist_state(self) -> None:
        self.json_manager.save_main_config(self.main_config)

    def set_lang(self, new_lang: str) -> None:
        self.lang = new_lang
        self.main_config["lang"] = new_lang
        self.persist_state()

    def set_profile(self, new_mode: str) -> None:
        self.mode = new_mode
        self.current_profile = self.profiles[new_mode]
        self.main_config[f"last_profile_{self.active_module}"] = new_mode
        self.persist_state()

    def set_camera_id(self, camera_id: int) -> None:
        self.main_config["camera_id"] = camera_id
        self.persist_state()

    def switch_module(self, module: str) -> None:
        """Load profiles for a new module and restore its last-used profile."""
        self.active_module = module
        self.profiles = self.json_manager.load_profiles(module)
        last_key = f"last_profile_{module}"
        stored = self.main_config.get(last_key, "default")
        if stored not in self.profiles:
            stored = next(iter(self.profiles), "default")
        self.mode = stored
        self.current_profile = self.profiles.get(stored, {})

    @property
    def available_modes(self) -> list:
        profile_modes = list(self.profiles.keys())
        return sorted(profile_modes + ["help", "configuration"])
