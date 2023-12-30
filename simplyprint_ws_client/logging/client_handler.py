import re
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

from typing_extensions import Self

from ..const import APP_DIRS

if TYPE_CHECKING:
    from ..config import Config
    from .client_name import ClientName


class ClientHandler(TimedRotatingFileHandler):

    @staticmethod
    def get_log_folder(config: 'Config') -> Path:
        log_folder = APP_DIRS.user_log_path / config.unique_id

        if not log_folder.exists():
            log_folder.mkdir(parents=True)

        return log_folder

    @staticmethod
    def from_client_name(name: 'ClientName') -> Self:
        log_folder = ClientHandler.get_log_folder(name.getConfig())

        log_name = name.peek() or "main"

        # Slugify the log name
        log_name = re.sub(r'[^\w\s-]', '', log_name)
        log_name = re.sub(r'[\s_-]+', '-', log_name)
        log_name = re.sub(r'^-+|-+$', '', log_name)

        return ClientHandler(log_folder / f"{log_name}.log", when="midnight", backupCount=3)
