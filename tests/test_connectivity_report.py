import unittest

from simplyprint_ws_client.shared.debug.connectivity import ConnectivityReport


class TestConnectivityReport(unittest.TestCase):
    def test_generate_default_report(self):
        ConnectivityReport.generate_default()
