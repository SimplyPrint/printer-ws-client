__all__ = ["ClientLogger"]

import logging
from typing import Union

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

from .client_name import ClientName


class ClientLogger(logging.Logger):
    name: ClientName

    def __init__(self, name: ClientName, level: Union[int, str] = logging.NOTSET) -> None:
        # Pass the config as the name so the logger dynamically updates its name
        super().__init__(name, level)

        if isinstance(name, ClientName):
            self._initialize_client_logger()

    def getChild(self, suffix: str) -> Self:
        if not isinstance(self.name, ClientName):
            return super().getChild(suffix)

        client_name = self.name.getChild(suffix)

        logger = self.manager.getLogger(client_name)

        if isinstance(logger, ClientLogger):
            logger._initialize_client_logger()

        logger.parent = self

        return logger

    def _initialize_client_logger(self):
        from . import ClientFilesHandler
        ClientFilesHandler.register_client_name(self.name)
