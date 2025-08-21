"""Shared test fixtures with proper type hints."""

import pytest

from simplyprint_ws_client import Client, PrinterConfig


@pytest.fixture
def client() -> Client:
    """Create a configured Client instance for testing."""
    client = Client(PrinterConfig.get_new())
    client.config.id = 1
    client.config.in_setup = False
    return client
