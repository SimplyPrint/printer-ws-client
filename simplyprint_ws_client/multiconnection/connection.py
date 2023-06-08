import logging

from ..client_old import Client
from ..connection import Connection
from .fake_ws import FakeWS

class ProxiedConnection(Connection):
    """ 
    Write a class that uses FakeWS instead of WebSocketClientConnection.
    """
    ws: FakeWS = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def connect(self, id, token):
        self.ws = FakeWS(id)

class ProxiedClient(Client):
    connection: ProxiedConnection = None

    def __init__(self, *args):
        super().__init__(*args)

        self.connection = ProxiedConnection(
            logger=logging.getLogger("simplyprint.client.connection")
        )