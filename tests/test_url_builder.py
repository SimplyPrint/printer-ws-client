import unittest

from simplyprint_ws_client.helpers.url_builder import UrlBuilder, DomainBuilder


class TestUrlBuilder(unittest.TestCase):
    def test_basic_url_builder(self):
        url = UrlBuilder.from_url("https://simplyprint.io")

        self.assertEqual(str(url), "https://simplyprint.io")

        url = url / "about"

        self.assertEqual(str(url), "https://simplyprint.io/about")

        url = url + ("page", 2)

        self.assertEqual(str(url), "https://simplyprint.io/about?page=2")

        url = url + ("search", "test")

        self.assertEqual(str(url), "https://simplyprint.io/about?page=2&search=test")

    def test_url_builder_with_netloc(self):
        url = UrlBuilder.from_url("https://test:pass@test.simplyprint.io:443/secret/path")

        self.assertEqual(str(url), "https://test:pass@test.simplyprint.io:443/secret/path")

        self.assertEqual(url.netloc.username, "test")
        self.assertEqual(url.netloc.password, "pass")
        self.assertEqual(url.netloc.hostname, "test.simplyprint.io")
        self.assertEqual(url.netloc.port, 443)

        url = UrlBuilder.from_url("https://useronly@test.simplyprint.io:443/secret/path")

        self.assertEqual(str(url), "https://useronly@test.simplyprint.io:443/secret/path")
        self.assertEqual(url.netloc.username, "useronly")

    def test_domain_builder_url(self):
        domain = DomainBuilder(domain="simplyprint", tld="io")

        self.assertEqual(str(domain), "simplyprint.io")
        self.assertEqual(str(domain.to_url()), "https://simplyprint.io")
