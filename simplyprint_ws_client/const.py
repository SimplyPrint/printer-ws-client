import importlib.metadata
from os import environ

from platformdirs import AppDirs

VERSION = importlib.metadata.version("simplyprint_ws_client") or "development"
APP_DIRS = AppDirs("SimplyPrint", "SimplyPrint")

IS_TESTING = bool(environ.get("IS_TESTING")) or bool(
    environ.get("DEV_MODE")) or bool(environ.get("DEBUG"))
