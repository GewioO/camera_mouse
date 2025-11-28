import argparse
from json_manager import JsonManager


class CLIManager:
    def __init__(self, json_manager: JsonManager | None = None):
        self.json_manager = json_manager or JsonManager()

        self.parser = argparse.ArgumentParser(add_help=False)
        self.parser.add_argument(
            "mode",
            nargs="?",
            default=None,
            choices=["default", "touch", "scroll", "help", "configuration"],
            help=""
        )
        self.parser.add_argument(
            "--lang",
            choices=["uk", "en"],
            default=None,
            help="interface language"
        )
        self.args = self.parser.parse_args()

        self.texts = self.json_manager.load_texts()
        self.profiles = self.json_manager.load_profiles()
        self.main_config = self.json_manager.load_main_config()

        self.lang = self.args.lang or self.main_config.get("lang", "uk")

        if self.args.mode is not None:
            self.mode = self.args.mode
        else:
            stored_mode = self.main_config.get("last_profile", "default")
            if stored_mode == "help":
                stored_mode = "default"
            self.mode = stored_mode

        self.current_profile = self.profiles.get(self.mode, self.profiles.get("default", {}))

        if self.mode != "help":
            self.main_config["last_profile"] = self.mode
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
