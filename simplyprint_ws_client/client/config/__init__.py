from enum import Enum
from typing import Type

from .config import PrinterConfig, Config
from .json import JsonConfigManager
from .manager import ConfigManager
from .memory import MemoryConfigManager
from .sqlite import SQLiteConfigManager


class ConfigManagerType(Enum):
    MEMORY = "memory"
    SQLITE = "sqlite"
    JSON = "json"

    def get_class(self) -> Type[ConfigManager]:
        if self == ConfigManagerType.MEMORY:
            return MemoryConfigManager
        elif self == ConfigManagerType.SQLITE:
            return SQLiteConfigManager
        elif self == ConfigManagerType.JSON:
            return JsonConfigManager
        else:
            raise ValueError("Invalid ConfigManagerType")
