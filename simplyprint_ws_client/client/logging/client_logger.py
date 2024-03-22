import logging
from typing import Union

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

from .client_handler import ClientHandler
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
        # Remove the previous ClientHandler
        # And add a new one based on the new name

        for handler in self.handlers:
            if isinstance(handler, ClientHandler):
                self.removeHandler(handler)

        self.addHandler(ClientHandler.from_client_name(self.name))

        root_stream_handler = None

        for handler in self.root.handlers:
            if not type(handler) is logging.StreamHandler:
                continue

            root_stream_handler = handler
            break

        if root_stream_handler:
            self.addHandler(root_stream_handler)

        self.propagate = False


# When loading this module, set the default logger class to ClientLogger
logging.setLoggerClass(ClientLogger)
