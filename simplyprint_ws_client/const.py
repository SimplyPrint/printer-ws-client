import importlib.metadata
from enum import Enum
from os import environ
from typing import NamedTuple, Optional, Tuple
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

    # When adding with a tuple add to query
    def __add__(self, other: Tuple[str, Optional[str]]) -> "UrlBuilder":
        qs = "&" if self.query else ""

        if not isinstance(other, tuple) or len(other) not in (1, 2):
            raise ValueError("Can only add tuples of length 1 or 2")

        if other[1] is not None:
            qs += f"{other[0]}={other[1]}"
        else:
            qs += other[0]

        return self._replace(query=f"{self.query}{qs}")


class SimplyPrintUrl:
    _current_url: "SimplyPrintUrl" = None

    def __init__(self, version: SimplyPrintVersion) -> None:
        self.version = version

    @staticmethod
    def current():
        return SimplyPrintUrl._current_url

    @staticmethod
    def set_current(version: SimplyPrintVersion = SimplyPrintVersion.PRODUCTION):
        SimplyPrintUrl._current_url = SimplyPrintUrl(version)

    @property
    def root_url(self) -> UrlBuilder:
        return UrlBuilder("https", DomainBuilder(self.version.root_subdomain))

    @property
    def api_url(self) -> UrlBuilder:
        return self.root_url / "api"

    @property
    def standalone_api_url(self) -> UrlBuilder:
        return UrlBuilder("https", DomainBuilder(self.version.api_subdomain))

    @property
    def ws_url(self) -> UrlBuilder:
        return UrlBuilder("wss", DomainBuilder(self.version.ws_subdomain)) / SimplyPrintWsVersion.VERSION_0_2.value


IS_TESTING = bool(environ.get("IS_TESTING")) or bool(
    environ.get("DEV_MODE")) or bool(environ.get("DEBUG"))

value = environ.get("SIMPLYPRINT_VERSION",
                    (SimplyPrintVersion.TESTING if IS_TESTING else SimplyPrintVersion.PRODUCTION).value)

SimplyPrintUrl.set_current(SimplyPrintVersion(value))
