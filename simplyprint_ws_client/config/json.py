import json
from pathlib import Path
from typing import Optional

from simplyprint_ws_client.config.config import Config

from .manager import ConfigManager


class JsonConfigManager(ConfigManager):
    def flush(self, config: Optional[Config] = None):
        self._ensure_json_file()

        with open(self._json_file, "w") as file:
            data = [ config.as_dict() for config in self.configurations if not config.is_blank() ]
            json.dump(data, file, indent=4)

    def load(self):
        self._ensure_json_file()

        with open(self._json_file, "r") as file:
            data = json.load(file)

            for config in data:
                self.persist(self.config_t(**config))

    def deleteStorage(self):
        if not self._json_file.exists():
            return
        
        self._json_file.unlink()

    @property
    def _json_file(self) -> Path:
        return self.base_directory / f"{self.name}.json"

    def _ensure_json_file(self):
        if not self._json_file.exists():
            self._json_file.touch()

            with open(self._json_file, "w") as file:
                json.dump([], file, indent=4)