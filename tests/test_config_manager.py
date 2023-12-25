import unittest

from simplyprint_ws_client.config import Config
from simplyprint_ws_client.config.json import JsonConfigManager
from simplyprint_ws_client.config.manager import ConfigManager
from simplyprint_ws_client.config.memory import MemoryConfigManager
from simplyprint_ws_client.config.sqlite3 import SqliteConfigManager

class TestConfigManager(unittest.TestCase):
    def test_internal(self):
        config_manager = MemoryConfigManager()

        self.assertEqual(config_manager.name, "printers")
        self.assertEqual(len(config_manager), 0)

        config1 = Config(id=1, token="token1")
        config2 = Config(id=2, token="token2")
        config3 = Config(id=3, token="token3")

        self.assertTrue(config1.partial_eq(config1))
        self.assertTrue(config2.partial_eq(config2))
        self.assertTrue(config3.partial_eq(config3))

        self.assertFalse(config1.partial_eq(config2))
        self.assertFalse(config2.partial_eq(config3))
        self.assertFalse(config3.partial_eq(config1))

        config_manager.persist(config1)
        config_manager.persist(config2)
        config_manager.persist(config3)

        self.assertEqual(len(config_manager), 3)

        self.assertEqual(config_manager.by_id(1), config1)
        self.assertEqual(config_manager.by_id(2), config2)
        self.assertEqual(config_manager.by_id(3), config3)

        self.assertEqual(config_manager.by_token("token1"), config1)
        self.assertEqual(config_manager.by_token("token2"), config2)
        self.assertEqual(config_manager.by_token("token3"), config3)

        self.assertEqual(config_manager.by_other(Config(id=1, token="token1")), config1)
        self.assertEqual(config_manager.by_other(Config(id=2, token="token2")), config2)
        self.assertEqual(config_manager.by_other(Config(id=3, token="token3")), config3)
        self.assertNotEqual(config_manager.by_other(Config(id=3, token="token4")), config3)

    def _test_manager(self, config_manager: ConfigManager):
        config = Config.get_blank()
        config_manager.persist(config)

        self.assertEqual(len(config_manager), 1)
        self.assertEqual(config_manager.by_id(config.id), config)

        config_manager.flush()

        config_manager.clear()
        config_manager.load()

        self.assertEqual(len(config_manager), 0)

        config_manager.persist(config)
        config.id = 1337
        config.token = "Super cool token"
        config.unique_id = str(id(config))
        config.public_ip = "127.0.0.1"

        config_manager.flush(config)

        config_manager.clear()
        config_manager.load()

        self.assertEqual(len(config_manager), 1)

        config2 = config_manager.by_id(config.id)

        self.assertEqual(config2.id, config.id)
        self.assertEqual(config2.token, config.token)
        self.assertEqual(config2.unique_id, config.unique_id)

        config_manager.remove(config2)

        self.assertEqual(len(config_manager), 0)
        config_manager.flush()
        config_manager.load()
        self.assertEqual(len(config_manager), 0)

        # Testing pending printer type scenario
        config = Config.get_blank()
        config_manager.persist(config)
        config_manager.flush()
        
        config.id = 1336
        config.token = "Super cool token"

        config_manager.flush(config)
        config_manager.clear()
        config_manager.load()
        
        self.assertEqual(len(config_manager), 1)

        config_manager.deleteStorage()

    def test_json_manager(self):
        json_config_manager = JsonConfigManager()
        self._test_manager(json_config_manager)
        self.assertFalse(json_config_manager._json_file.exists())

    def test_sqlite3_manager(self):
        sqlite_config_manager = SqliteConfigManager()
        self._test_manager(sqlite_config_manager)      
        self.assertFalse(sqlite_config_manager._database_file.exists())  