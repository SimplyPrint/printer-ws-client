import importlib.metadata
from os import environ

from platformdirs import AppDirs

from simplyprint_ws_client.helpers.url_builder import SimplyPrintBackend, SimplyPrintUrl

VERSION = importlib.metadata.version("simplyprint_ws_client") or "development"
APP_DIRS = AppDirs("SimplyPrint", "SimplyPrint")

IS_TESTING = bool(environ.get("IS_TESTING")) or bool(
    environ.get("DEV_MODE")) or bool(environ.get("DEBUG"))

value = environ.get("SIMPLYPRINT_VERSION",
                    (SimplyPrintBackend.TESTING if IS_TESTING else SimplyPrintBackend.PRODUCTION).value)

SimplyPrintUrl.set_current(SimplyPrintBackend(value))
