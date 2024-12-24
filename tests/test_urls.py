import unittest

from simplyprint_ws_client.helpers import SimplyPrintURL, SimplyPrintBackend


class TestURLs(unittest.TestCase):
    def test_url_builder(self):
        urls = SimplyPrintURL()

        urls.set_backend(SimplyPrintBackend.PRODUCTION)

        self.assertEqual(str(urls.main_url), "https://simplyprint.io")
        self.assertEqual(str(urls.api_url), "https://api.simplyprint.io")
        self.assertEqual(str(urls.ws_url), "wss://ws.simplyprint.io/0.2")

        urls.set_backend(SimplyPrintBackend.TESTING)

        self.assertEqual(str(urls.main_url), "https://test.simplyprint.io")
        self.assertEqual(str(urls.api_url), "https://testapi.simplyprint.io")
        self.assertEqual(str(urls.ws_url), "wss://testws3.simplyprint.io/0.2")

        urls.set_backend(SimplyPrintBackend.STAGING)

        self.assertEqual(str(urls.main_url), "https://staging.simplyprint.io")
        self.assertEqual(str(urls.api_url), "https://apistaging.simplyprint.io")
        self.assertEqual(str(urls.ws_url), "wss://wsstaging.simplyprint.io/0.2")

        # modifies same static variable
        self.assertEqual(urls._active_backend, SimplyPrintURL._active_backend)
