import sentry_sdk

from typing import Optional
from ..const import VERSION, IS_TESTING

class Sentry:
    """
    Configuration object for client information.
    """
    
    client: Optional[str] = None
    client_version: Optional[str] = None
    sentry_dsn: Optional[str] = None
    development: bool = IS_TESTING

    def initialize_sentry(self, unique_id: Optional[str] = None):
        if self.sentry_dsn is None:
            return
    
        if sentry_sdk.Hub.current.client is not None:
            return

        try:
            sentry_sdk.init(
                dsn=self.sentry_dsn,
                traces_sample_rate=0.05,
                release=f"{self.info.client}@{self.info.client_version}",
                environment=("production" if not self.info.development else "development"),
            )

            sentry_sdk.set_tag("lib_version", VERSION)

            if unique_id is not None:
                sentry_sdk.set_tag("id", unique_id)
            
        except Exception:
            # Log
            pass