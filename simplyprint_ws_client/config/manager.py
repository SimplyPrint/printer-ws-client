from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Type

from .config import Config

class ConfigManager(ABC):
    name: str
    config_class: Type[Config]
    configurations: Dict[int, Config]

    def __init__(self, name: str = "config", config_class: Type[Config] = Config) -> None:
        self.name = name
        self.config_class = config_class
        self.configurations = {}

    def by_id(self, id: int) -> Config:
        return self.by_other(self.config_class(id=id))

    def by_token(self, token: str) -> Config:
        return self.by_other(self.config_class(token=token))

    def by_other(self, other: Config) -> Config:
        for config in self.configurations.values():
            if config.partial_eq(other):
                return config
            
        return None

    def contains(self, other: Config) -> Config:
        return id(other) in self.configurations

    def persist(self, config: Config):
        if self.contains(config):
            return
        
        self.configurations[id(config)] = config

    def remove(self, config: Config):
        if not self.contains(config):
            return
        
        del self.configurations[id(config)]

    def get_all(self) -> List[Config]:
        return list(self.configurations.values())
    
    def clear(self):
        self.configurations.clear()

    @property
    def base_directory(self) -> Path:
        return Path(".")

    @abstractmethod
    def flush(self, config: Optional[Config] = None):
        """
        Tell the manager to save all configs.

        Optionally if the manager supports it, only update a single config.
        """
        ...

    @abstractmethod
    def load(self):
        """
        Tell the manager to load all configs.

        The manager can decide whether to override existing configs or not.
        """
        ...

    def __len__(self):
        return len(self.configurations)