from enum import Enum
from typing import Type
from .config import Config
from .manager import ConfigManager
from .memory import MemoryConfigManager
from .sqlite3 import SqliteConfigManager
from .json import JsonConfigManager

class ConfigManagerType(Enum):
    MEMORY = "memory"
    SQLITE = "sqlite"
    JSON = "json"

    def get_class(self) -> Type[ConfigManager]:
        if self == ConfigManagerType.MEMORY:
            return MemoryConfigManager
        elif self == ConfigManagerType.SQLITE:
            return SqliteConfigManager
        elif self == ConfigManagerType.JSON:
            return JsonConfigManager
        else:
            raise ValueError("Invalid ConfigManagerType")