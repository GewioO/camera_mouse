MODULES = ["hand", "stump"]  # "eyes" in future


class ModuleManager:
    def __init__(self, json_manager):
        self._json = json_manager
        config = json_manager.load_main_config()
        active = config.get("active_module", "hand")
        self.active = active if active in MODULES else "hand"

    def get(self) -> str:
        return self.active

    def set(self, module: str, main_config: dict) -> None:
        if module not in MODULES:
            return
        self.active = module
        main_config["active_module"] = module
        self._json.save_main_config(main_config)
