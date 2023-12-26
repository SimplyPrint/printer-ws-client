from collections import namedtuple
import importlib.metadata
from enum import Enum
from os import environ
from typing import NamedTuple, Optional
from urllib.parse import urlunparse
from platformdirs import AppDirs

VERSION = importlib.metadata.version("simplyprint_ws_client") or "development"
APP_DIRS = AppDirs("SimplyPrint", "SimplyPrint")
SUPPORTED_SIMPLYPRINT_VERSION = "4.1.3"


class SimplyPrintWsVersion(Enum):
    VERSION_0_1 = "0.1"
    VERSION_0_2 = "0.2"

class SimplyPrintVersion(Enum):
    PRODUCTION = None
    TESTING = "test"
    STAGING = "staging"

    @property
    def root_subdomain(self) -> Optional[str]:
        return self.value
    
    @property
    def api_subdomain(self) -> str:
        if self.value is None:
            return "api"
        
        return f"{self.value}api"
    
    @property
    def ws_subdomain(self) -> str:
        if self.value is None:
            return "ws"
        
        if self.value == "test":
            return "testws3"
        
        if self.value == "staging":
            return "wsstaging"
        
        raise ValueError(f"Unknown subdomain for {self.value}")

class DomainBuilder(NamedTuple):
    subdomain: str = None
    domain: str = "simplyprint"
    tld: str = "io"

    def __str__(self) -> str:
        return ".".join(filter(None, [self.subdomain, self.domain, self.tld]))

class UrlBuilder(NamedTuple):
    scheme: str = "https"
    netloc: DomainBuilder = DomainBuilder()
    path: str = ""
    params: str = ""
    query: str = ""
    fragment: str = ""

    def __str__(self) -> str:
        return urlunparse(map(str, self))
    
    def __truediv__(self, other: str) -> "UrlBuilder":
        return self._replace(path=f"{self.path}/{other}")

class SimplyPrintUrl:
    def __init__(self, version: SimplyPrintVersion) -> None:
        self.version = version

    @property
    def root_url(self) -> UrlBuilder:
        return UrlBuilder("https", DomainBuilder(self.version.root_subdomain))

    @property
    def api_url(self) -> str:
        return self.root_url / "api"

    @property
    def standalone_api_url(self) -> str:
        return UrlBuilder("https", DomainBuilder(self.version.api_subdomain))

    @property
    def ws_url(self) -> str:
        return UrlBuilder("wss", DomainBuilder(self.version.ws_subdomain)) / SimplyPrintWsVersion.VERSION_0_2.value


IS_TESTING = bool(environ.get("IS_TESTING")) or bool(
    environ.get("DEV_MODE")) or bool(environ.get("DEBUG"))

SIMPLYPRINT_URL = SimplyPrintUrl(SimplyPrintVersion.TESTING if IS_TESTING else SimplyPrintVersion.PRODUCTION)