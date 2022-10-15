import json
import os

CONFIG_FILE_PATH: str = "config.json"

class Config:
    id: str
    token: str

    def __init__(self):
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
        with open(CONFIG_FILE_PATH, "w") as f:
            json.dump(self.__dict__, f, indent=4)
