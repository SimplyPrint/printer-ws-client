import unittest

from simplyprint_ws_client import PrinterConfig


class TestConfigManager(unittest.TestCase):
    def test_fields(self):
        config1 = PrinterConfig.get_blank()
        config2 = PrinterConfig.get_blank()

        self.assertTrue(config1.partial_eq(**config1.as_dict()))
        self.assertTrue(config2.partial_eq(**config2.as_dict()))

        self.assertTrue(config1.is_empty())
        self.assertTrue(config2.is_default())

        self.assertDictEqual(config1.as_dict(), config2.as_dict())

        self.assertDictEqual(
            config1.as_dict(),
            {
                "id": 0,
                "token": "0",
                "name": None,
                "in_setup": None,
                "short_id": None,
                "unique_id": config1.unique_id,
                "public_ip": None,
            },
        )

        config1.id = 1

        self.assertFalse(config1.partial_eq(**config2.as_dict()))
        self.assertFalse(config2.partial_eq(**config1.as_dict()))

        self.assertFalse(config1.is_empty())

        self.assertFalse(config1.is_pending())

        config2.token = "super_cool_token"
        config2.unique_id = "super_cool_id"

        self.assertFalse(config2.is_empty())
        self.assertFalse(config2.is_default())

        self.assertTrue(config2.partial_eq(unique_id="super_cool_id"))
        self.assertTrue(config2.partial_eq(token="super_cool_token"))

        config3 = PrinterConfig(
            **{
                "id": None,
                "in_setup": None,
                "short_id": None,
                "name": None,
                "public_ip": None,
                "token": None,
                "unique_id": None,
            }
        )
        self.assertTrue(config3.is_empty())

        config4 = PrinterConfig(
            **{
                "id": None,
                "in_setup": None,
                "short_id": None,
                "name": None,
                "public_ip": None,
                "token": None,
                "unique_id": "140686326013968",
            }
        )
        self.assertFalse(config4.is_empty())
