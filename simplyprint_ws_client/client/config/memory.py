from typing import Optional

from simplyprint_ws_client.client.config.config import Config
from .manager import ConfigManager


class MemoryConfigManager(ConfigManager):
    def flush(self, config: Optional[Config] = None):
        ...

    def load(self):
        ...

    def delete_storage(self):
        ...

    def backup_storage(self, *args, **kwargs):
        ...
