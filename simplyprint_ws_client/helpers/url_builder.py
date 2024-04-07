from enum import Enum
from os import environ
from typing import NamedTuple, Optional

from yarl import URL

from simplyprint_ws_client.const import IS_TESTING


class SimplyPrintWsVersion(Enum):
    VERSION_0_1 = "0.1"
    VERSION_0_2 = "0.2"


class SimplyPrintBackend(Enum):
    PRODUCTION = "production"
    TESTING = "test"
    STAGING = "staging"

    @property
    def root_subdomain(self) -> Optional[str]:
        if self == SimplyPrintBackend.PRODUCTION:
            return None

        return self.value

    @property
    def api_subdomain(self) -> str:
        if self == SimplyPrintBackend.PRODUCTION:
            return "api"

        return f"{self.value}api"

    @property
    def ws_subdomain(self) -> str:
        if self == SimplyPrintBackend.PRODUCTION:
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

    def to_url(self) -> URL:
        return URL.build(scheme="https", host=str(self))

    def __str__(self) -> str:
        return ".".join(filter(None, [self.subdomain, self.domain, self.tld]))


class SimplyPrintUrl:
    _current_url: "SimplyPrintUrl" = None

    def __init__(self, version: SimplyPrintBackend) -> None:
        self.version = version

    @staticmethod
    def current():
        return SimplyPrintUrl._current_url

    @staticmethod
    def set_current(version: SimplyPrintBackend = SimplyPrintBackend.PRODUCTION):
        SimplyPrintUrl._current_url = SimplyPrintUrl(version)

    @property
    def root_url(self) -> URL:
        return DomainBuilder(self.version.root_subdomain).to_url()

    @property
    def api_url(self) -> URL:
        return self.root_url / "api"

    @property
    def standalone_api_url(self) -> URL:
        return DomainBuilder(self.version.api_subdomain).to_url()

    @property
    def ws_url(self) -> URL:
        return URL.build(scheme="wss",
                         host=str(DomainBuilder(self.version.ws_subdomain))) / SimplyPrintWsVersion.VERSION_0_1.value


value = environ.get("SIMPLYPRINT_VERSION",
                    (SimplyPrintBackend.TESTING if IS_TESTING else SimplyPrintBackend.PRODUCTION).value)

SimplyPrintUrl.set_current(SimplyPrintBackend(value))
