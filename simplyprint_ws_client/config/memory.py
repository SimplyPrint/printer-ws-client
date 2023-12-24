from typing import Optional
from simplyprint_ws_client.config.config import Config
from .manager import ConfigManager

class MemoryConfigManager(ConfigManager):
    def flush(self, config: Optional[Config] = None):
        ...
    
    def load(self):
        ...
    
    def deleteStorage(self):
        ...