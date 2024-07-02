from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, List, Optional, Type, TypeVar, Set

from .config import Config, PrinterConfig
from ...const import APP_DIRS

TConfig = TypeVar("TConfig", bound=Config)


class ConfigManager(ABC, Generic[TConfig]):
    name: str
    config_t: Type[TConfig]
    configurations: Set[TConfig]
    base_directory: Path

    def __init__(self, name: str = "printers", config_t: Type[TConfig] = PrinterConfig,
                 base_directory: Optional[str] = None) -> None:
        self.name = name

        # Override the hashable method to make the config hashable
        # Just a nice to have to we do not need classes that individually
        # call this method when the top level class that needs the functionality
        # can get it here.
        config_t.make_hashable()

        self.config_t = config_t
        self.configurations = set()

        # Default to user config directory if not specified
        self.base_directory = Path(base_directory or APP_DIRS.user_config_dir)

        if not self.base_directory.exists():
            self.base_directory.mkdir(parents=True)

        # Read all configurations from storage initially.
        self.load()

    def by_id(self, client_id: int) -> TConfig:
        return self.find(id=client_id)

    def by_token(self, token: str) -> TConfig:
        return self.find(token=token)

    def by_unique_id(self, unique_id: str) -> TConfig:
        return self.find(unique_id=unique_id)

    def find(self, other: Optional[TConfig] = None, **kwargs) -> Optional[TConfig]:
        kwargs = self.config_t.update_dict_keys(kwargs)

        for config in self.get_all():
            if config.partial_eq(config=other, **kwargs):
                return config

        return None

    def contains(self, other: TConfig) -> bool:
        return other in self.configurations

    def persist(self, config: Config):
        if self.contains(config):
            return

        self.configurations.add(config)

    def remove(self, config: TConfig):
        self.configurations.remove(config)

    def get_all(self) -> List[TConfig]:
        return list(self.configurations)

    def clear(self):
        self.configurations.clear()

    @abstractmethod
    def flush(self, config: Optional[TConfig] = None):
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

    @abstractmethod
    def delete_storage(self):
        """
        Delete the entire storage.
        """
        ...

    @abstractmethod
    def backup_storage(self, *args, **kwargs):
        """
        Backup the entire storage.
        """
        ...

    def __len__(self):
        return len(self.configurations)
