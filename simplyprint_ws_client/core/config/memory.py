__all__ = ["MemoryConfigManager"]

from typing import Optional

from .manager import ConfigManager
from .config import Config


class MemoryConfigManager(ConfigManager):
    def flush(self, config: Optional[Config] = None):
        ...

    def load(self):
        ...

    def delete_storage(self):
        ...

    def backup_storage(self, *args, **kwargs):
        ...
