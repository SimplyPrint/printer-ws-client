import json
import logging
from pathlib import Path
from typing import Optional

from simplyprint_ws_client.client.config.config import Config
from .manager import ConfigManager
from simplyprint_ws_client.helpers.file_backup import FileBackup


class JsonConfigManager(ConfigManager):
    def flush(self, config: Optional[Config] = None):
        self._ensure_json_file()

        with open(self._json_file, "w") as file:
            data = [config.as_dict() for config in self.configurations if not config.is_blank()]
            json.dump(data, file, indent=4)

    def load(self):
        self._ensure_json_file()

        with open(self._json_file, "r") as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                logging.warning(f"Failed to load {self._json_file} configuration file, it's invalid - resetting it!!!")
                data = []

            for config in data:
                self.persist(self.config_t(**config))

    def delete_storage(self):
        if not self._json_file.exists():
            return

        self._json_file.unlink()

    def backup_storage(self, *args, **kwargs):
        self._ensure_json_file()
        FileBackup.backup_file(self._json_file, *args, **kwargs)

    @property
    def _json_file(self) -> Path:
        return self.base_directory / f"{self.name}.json"

    def _ensure_json_file(self):
        if not self._json_file.exists():
            # Always create a valid JSON file, to prevent issues.
            with open(self._json_file, "w") as file:
                json.dump([], file, indent=4)
