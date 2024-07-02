from enum import Enum
from os import environ
from typing import NamedTuple, Optional

from yarl import URL

from ..const import IS_TESTING


class SimplyPrintWsVersion(Enum):
    VERSION_0_1 = "0.1"
    VERSION_0_2 = "0.2"


class Host(NamedTuple):
    root: str
    subdomain: Optional[str] = None
    port: Optional[int] = None

    def __str__(self):
        host = ".".join(filter(None, [self.subdomain, self.root]))

        if self.port:
            host += f":{self.port}"

        return host

    def with_port(self, port: int) -> "Host":
        return self._replace(port=port)

    def with_subdomain(self, subdomain: str) -> "Host":
        return self._replace(subdomain=subdomain)


class SimplyPrintURLs(NamedTuple):
    main_host: Host
    api_host: Host
    ws_host: Host
    secure: bool = True

    @property
    def _http_scheme(self) -> str:
        return "https" if self.secure else "http"

    @property
    def _ws_scheme(self) -> str:
        return "wss" if self.secure else "ws"

    @property
    def main_url(self) -> URL:
        return URL.build(scheme=self._http_scheme, host=str(self.main_host))

    @property
    def api_url(self) -> URL:
        return URL.build(scheme=self._http_scheme, host=str(self.api_host))

    @property
    def ws_url(self) -> URL:
        return URL.build(scheme=self._ws_scheme,
                         host=str(self.ws_host)) / SimplyPrintWsVersion.VERSION_0_2.value


_root = Host("simplyprint.io")

PRODUCTION_URLS = SimplyPrintURLs(_root, _root.with_subdomain("api"),
                                  _root.with_subdomain("ws"))

TESTING_URLS = SimplyPrintURLs(_root.with_subdomain("test"), _root.with_subdomain("testapi"),
                               _root.with_subdomain("testws3"))

STAGING_URLS = SimplyPrintURLs(_root.with_subdomain("staging"), _root.with_subdomain("apistaging"),
                               _root.with_subdomain("wsstaging"))

_localhost = Host("localhost", port=8080)

LOCALHOST_URLS = SimplyPrintURLs(_localhost, _localhost, _localhost.with_port(8081), secure=False)


class SimplyPrintBackend(Enum):
    PRODUCTION = "production"
    TESTING = "test"
    STAGING = "staging"
    LOCALHOST = "custom"

    def get_urls(self) -> SimplyPrintURLs:
        if self == SimplyPrintBackend.PRODUCTION:
            return PRODUCTION_URLS
        elif self == SimplyPrintBackend.TESTING:
            return TESTING_URLS
        elif self == SimplyPrintBackend.STAGING:
            return STAGING_URLS
        elif self == SimplyPrintBackend.LOCALHOST:
            return LOCALHOST_URLS
        else:
            raise ValueError(f"Invalid backend: {self}")


class SimplyPrintURL:
    _active_backend: SimplyPrintBackend = SimplyPrintBackend.PRODUCTION

    @staticmethod
    def set_backend(backend: SimplyPrintBackend):
        SimplyPrintURL._active_backend = backend

    @staticmethod
    def urls() -> SimplyPrintURLs:
        return SimplyPrintURL._active_backend.get_urls()

    @property
    def main_url(self) -> URL:
        return self.urls().main_url

    @property
    def api_url(self) -> URL:
        return self.urls().api_url

    @property
    def ws_url(self) -> URL:
        return self.urls().ws_url


value = environ.get("SIMPLYPRINT_BACKEND",
                    (SimplyPrintBackend.TESTING if IS_TESTING else SimplyPrintBackend.PRODUCTION).value)

SimplyPrintURL.set_backend(SimplyPrintBackend(value))
