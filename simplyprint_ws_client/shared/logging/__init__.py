__all__ = [
    'ClientFilesHandler',
    'ClientLogger',
    'ClientName',
    'setup_logging',
    'get_log_folder'
]

import logging
import logging.handlers
import queue
from pathlib import Path
from typing import TYPE_CHECKING, Dict, ClassVar, Optional

from .client_logger import ClientLogger
from ..utils.slugify import slugify
from ...const import APP_DIRS

if TYPE_CHECKING:
    from ...core.app import ClientSettings

from .client_name import ClientName


def get_log_folder(name: ClientName) -> Path:
    log_folder = APP_DIRS.user_log_path / name.ctx.unique_id

    if not log_folder.exists():
        log_folder.mkdir(parents=True, exist_ok=True)

    return log_folder


def create_file_handler(file: Path, *args, **kwargs):
    handler = logging.handlers.RotatingFileHandler(
        file,
        *args,
        maxBytes=30 * 1024 * 1024,
        backupCount=3,
        delay=True,
        **kwargs
    )

    return handler


def create_root_handler(settings: 'ClientSettings') -> logging.Handler:
    if not APP_DIRS.user_log_path.exists():
        APP_DIRS.user_log_path.mkdir(parents=True, exist_ok=True)
    main_log_file = APP_DIRS.user_log_path / f"{slugify(settings.name)}.log"
    return create_file_handler(main_log_file)


def setup_logging(settings: 'ClientSettings') -> callable:
    """Setup logging based on client settings."""
    logging_queue = queue.SimpleQueue()

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[logging.handlers.QueueHandler(logging_queue)],
        format='%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s | %(message)s',
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

    stream_handler = logging.StreamHandler()
    client_handler = ClientFilesHandler()
    client_handler.set_default_handler(create_root_handler(settings))

    if settings.development:
        stream_handler.setLevel(logging.DEBUG)
    else:
        stream_handler.setLevel(logging.INFO)

    listener = logging.handlers.QueueListener(logging_queue, stream_handler, client_handler, respect_handler_level=True)
    listener.start()
    return listener.stop


class ClientFilesHandler(logging.Handler):
    default_handler: ClassVar[Optional[logging.Handler]] = None
    client_handlers: ClassVar[Dict[ClientName, logging.Handler]] = {}

    @classmethod
    def set_default_handler(cls, handler: logging.Handler):
        cls.default_handler = handler

    @classmethod
    def register_client_name(cls, name: ClientName):
        if name in cls.client_handlers:
            return

        log_folder = get_log_folder(name)
        log_name = slugify(name.peek() or "main")
        log_file = log_folder / f"{log_name}.log"
        cls.client_handlers[name] = create_file_handler(log_file)

    @classmethod
    def deregister_client_name(cls, name: ClientName):
        cls.client_handlers.pop(name, None)

    def emit(self, record):
        return self.handle(record)

    def handle(self, record):
        if not isinstance(record.name, ClientName) or record.name not in self.__class__.client_handlers:
            if self.__class__.default_handler is not None:
                self.__class__.default_handler.emit(record)

            return

        self.__class__.client_handlers[record.name].emit(record)


# When loading this module, set the default logger class to ClientLogger
logging.setLoggerClass(ClientLogger)
