from enum import Enum
from os import environ

VERSION = "1.0.0-rc.1"

class SimplyPrintWsVersion(Enum):
    VERSION_0_1 = "0.1"
    VERSION_0_2 = "0.2"

SUPPORTED_SIMPLYPRINT_VERSION = "4.1.3"

IS_TESTING = bool(environ.get("IS_TESTING")) or bool(environ.get("DEV_MODE")) or bool(environ.get("DEBUG"))
BASE_URL = "{}://{}.simplyprint.io/{}"

PROD_WEBSOCKET_URL = BASE_URL.format("wss", "ws", SimplyPrintWsVersion.VERSION_0_2.value)
TEST_WEBSOCKET_URL = BASE_URL.format("wss", "testws3", SimplyPrintWsVersion.VERSION_0_2.value)
STAG_WEBSOCKET_URL = BASE_URL.format("wss", "wsstaging", SimplyPrintWsVersion.VERSION_0_2.value)

PROD_API_URL = BASE_URL.format("https", "api", "")
TEST_API_URL = BASE_URL.format("https", "test", "api")
STAG_API_URL = BASE_URL.format("https", "staging", "api")

API_URL = PROD_API_URL if not IS_TESTING else TEST_API_URL
WEBSOCKET_URL = PROD_WEBSOCKET_URL if not IS_TESTING else TEST_WEBSOCKET_URL