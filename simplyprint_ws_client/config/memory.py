from typing import Optional
from simplyprint_ws_client.config.config import Config
from .manager import ConfigManager

class MemoryConfigManager(ConfigManager):
    def flush(self, config: Config | None = None):
        return
    
    def load(self):
        return