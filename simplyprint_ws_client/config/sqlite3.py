import json
import logging
import sqlite3
from typing import Optional

from simplyprint_ws_client.config.config import Config

from .manager import ConfigManager

class SqliteConfigManager(ConfigManager):
    """
    Handles configuration state and persistence.
    """

    logger: logging.Logger = logging.getLogger("config.sqlite3")

    db: Optional[sqlite3.Connection] = None
    table_exists: bool = False

    def flush(self, config: Config | None = None):
        self._ensure_table()

        try:
            if config is not None:
                self._flush_single(config)
                self._remove_detached()
                return
            
            for config in self.configurations.values():
                # Do not flush blank configs
                if config.is_blank():
                    continue

                self._flush_single(config)
            
            self._remove_detached()
        finally:
            self.db.commit()

    def load(self):
        self._ensure_table()

        configs = self.db.execute(
            """
            SELECT id, token, data FROM config
            """).fetchall()

        for config in configs:
            kwargs = json.loads(config[2])
            kwargs["id"] = config[0]
            kwargs["token"] = config[1]
            self.persist(self.config_class(**kwargs))
    
    def _get_single(self, config: Config):
        return self.db.execute(
            """
            SELECT id, token FROM config WHERE id= ? AND token= ? LIMIT 1
            """, (config.id, config.token)).fetchone()

    def _flush_single(self, config: Config):
        # Check if unique token and id exists
        already_exists = self._get_single(config)

        if not already_exists:
            self.db.execute(
                """
                INSERT INTO config (id, token, data) VALUES (?, ?, ?)
                """, (config.id, config.token, json.dumps(config.as_dict())))

            self.db.commit()
            self.logger.info(f"Inserted config {config}")
            return
        
        self.db.execute(
            """
            UPDATE config SET data= ? WHERE id= ? AND token= ?
            """, (json.dumps(config.as_dict()), config.id, config.token))

    def _remove_detached(self):
        # Get all configs from the database
        configs = self.db.execute(
            """
            SELECT id, token FROM config
            """).fetchall()
        
        # Loop over all configs
        for config in configs:
            # If the config is not in the manager
            if not self.by_other(self.config_class(id=config[0], token=config[1])):
                # Remove it from the database
                self.db.execute(
                    """
                    DELETE FROM config WHERE id= ? AND token= ?
                    """, (config[0], config[1]))

    def _ensure_table(self):
        """
        Ensure the config table exists.
        """

        if not SqliteConfigManager.db:
            SqliteConfigManager.db = sqlite3.connect(f"{self.base_directory / self.name}.db", check_same_thread=False)

        if SqliteConfigManager.table_exists:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER, 
                token TEXT, 
                data TEXT, 
                PRIMARY KEY (id, token)
            );
            """)
        
        self.db.commit()
        self.logger.info("Created config table")
        SqliteConfigManager.table_exists = True