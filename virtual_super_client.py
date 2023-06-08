from simplyprint_ws.client.client import DefaultClient
from simplyprint_ws.config import Config

class VirtualSuperClient(DefaultClient):
    def __init__(self, config: Config):
        super().__init__(config)

        