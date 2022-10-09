import os
import requests

from typing import Optional

class FileHandler:
    def __init__(self):
        pass

    def load_url(self, url: str) -> Optional[str]:
        try:
            response = requests.get(url)
        except Exception:
            return None

    def load_file(self, path: str) -> Optional[str]:
        if not os.path.exists(path):
            return None

        with open(path, "r") as f:
            return f.read()
