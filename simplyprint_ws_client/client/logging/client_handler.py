import logging
import re

from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Dict

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

from ...const import APP_DIRS

if TYPE_CHECKING:
    from ...client.config import Config
    from .client_name import ClientName
    from ...client.app import ClientOptions


class ClientHandler(RotatingFileHandler):
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', '%m-%d-%Y %H:%M:%S')
    handlers: Dict[str, 'ClientHandler'] = {}

    @classmethod
    def slugify(cls, name: str) -> str:
        # Slugify the log name
        name = re.sub(r'[^\w\s.-]', '', name)
        name = re.sub(r'[\s_-]+', '-', name)
        name = re.sub(r'^-+|-+$', '', name)
        return name

    @classmethod
    def get_log_folder(cls, config: 'Config') -> Path:
        log_folder = APP_DIRS.user_log_path / config.unique_id

        if not log_folder.exists():
            log_folder.mkdir(parents=True)

        return log_folder

    @classmethod
    def from_client_name(cls, name: 'ClientName') -> Self:
        log_folder = cls.get_log_folder(name.getConfig())

        log_name = cls.slugify(name.peek() or "main")
        log_file = log_folder / f"{log_name}.log"

        return cls._create_handler(
            log_file,
            maxBytes=30 * 1024 * 1024,
            backupCount=3,
            delay=True
        )

    @classmethod
    def root_handler(cls, options: 'ClientOptions') -> Self:
        main_log_file = APP_DIRS.user_log_path / f"{cls.slugify(options.name)}.log"
        return cls._create_handler(main_log_file, maxBytes=30 * 1024 * 1024, backupCount=3, delay=True)

    @classmethod
    def _create_handler(cls, file_path: Path, *args, **kwargs):
        file_key = str(file_path)

        if file_key not in cls.handlers:
            handler = cls.handlers[file_key] = cls(file_path, *args, **kwargs)
            handler.setFormatter(cls.formatter)

        return cls.handlers[file_key]
