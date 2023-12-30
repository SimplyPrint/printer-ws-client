import logging
from typing_extensions import Self
from .client_handler import ClientHandler
from .client_name import ClientName


class ClientLogger(logging.Logger):
    name: ClientName

    def __init__(self, name: ClientName, level: int | str = logging.NOTSET) -> None:            
        # Pass the config as the name so the logger dynamically updates its name
        super().__init__(name, level)

        if isinstance(name, ClientName):
            self.addHandler(ClientHandler.from_client_name(self.name))

    def getChild(self, suffix: str) -> Self:
        if not isinstance(self.name, ClientName):
            return super().getChild(suffix)

        clientName = self.name.getChild(suffix)
        logger = self.manager.getLogger(clientName)
        
        # Remove the previous ClientHandler
        # And add a new one based on the new name
        for handler in logger.handlers:
            if isinstance(handler, ClientHandler):
                logger.removeHandler(handler)

        logger.addHandler(ClientHandler.from_client_name(clientName))

        return logger


# When loading this module, set the default logger class to ClientLogger
logging.setLoggerClass(ClientLogger)
