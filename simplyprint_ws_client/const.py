from os import environ

VERSION = "1.0.0-rc.1"
IS_TESTING = bool(environ.get("IS_TESTING"))
API_VERSION = "0.1"
API_URL = environ.get("API_URL", "https://api.simplyprint.io" if not IS_TESTING else "https://apirewrite.simplyprint.io")
WEBSOCKET_URL = environ.get("WEBSOCKET_URL", "wss://ws.simplyprint.io" if not IS_TESTING else "wss://testws2.simplyprint.io")
