from os import environ

VERSION = "0.0.6"
CONFIG_FILE_PATH: str = "config.json"

WEBSOCKET_URL: str = "wss://ws.simplyprint.io" if not "DEV" in environ else "wss://testws2.simplyprint.io"
REACHABLE_URL: str = "https://ws.simplyprint.io" if not "DEV" in environ else "https://testws2.simplyprint.io"
SNAPSHOT_ENDPOINT = "https://api.simplyprint.io/jobs/ReceiveSnapshot"
