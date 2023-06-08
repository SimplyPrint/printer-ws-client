import json
import os

from simplyprint_ws_client.const import CONFIG_FILE_PATH

class Config:
    """
    Configuration object for a single client.

    No many-in-one support yet.
    """
    id: str
    token: str
    use_file: bool

    def __init__(self, pid: str = None, token: str = None):
        if not None in (pid, token):
            self.id: str = pid
            self.token: str = token
            self.use_file: bool = False
            return
        else:
            self.use_file: bool = True

        if os.path.exists(CONFIG_FILE_PATH):
            self.__dict__ = json.load(open(CONFIG_FILE_PATH))

            if self.id is None:
                self.id: str = "0"

            if self.token is None:
                self.token: str = "0"
        else:
            self.id: str = "0"
            self.token: str = "0"

    def save(self):
        if not self.use_file: return

        with open(CONFIG_FILE_PATH, "w") as f:
            json.dump(self.__dict__, f, indent=4)
