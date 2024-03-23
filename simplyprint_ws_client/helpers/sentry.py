import logging
from typing import TYPE_CHECKING, List

import sentry_sdk
from sentry_sdk.integrations import Integration

from ..const import VERSION

if TYPE_CHECKING:
    from simplyprint_ws_client.client.app import ClientOptions


class Sentry:
    """
    Configuration object for client information.
    """

    integrations: List[Integration] = []

    @classmethod
    def add_integration(cls, integration: Integration):
        if cls.is_initialized():
            raise RuntimeError("Cannot add integrations after sentry is initialized")

        cls.integrations.append(integration)

    @classmethod
    def is_initialized(cls):
        return sentry_sdk.Hub.current.client is not None

    @classmethod
    def initialize_sentry(cls, options: 'ClientOptions'):
        if options.sentry_dsn is None:
            return

        if cls.is_initialized():
            return

        try:
            sentry_sdk.init(
                dsn=options.sentry_dsn,
                traces_sample_rate=1.0,
                integrations=cls.integrations,
                release=f"{options.name}@{options.version}",
                environment=("production" if not options.development else "development"),
            )

            sentry_sdk.set_tag("lib_version", VERSION)

        except Exception as e:
            logging.exception(e)
