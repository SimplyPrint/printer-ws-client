import sqlite3
import logging

from typing import Optional, List

class Config:
    """
    Configuration object.
    """
    
    __slots__ = ("id", "token", "unique_id", "public_ip")

    id: int
    token: str
    unique_id: Optional[str]
    public_ip: Optional[str]

    def __init__(self, id: int, token: str, unique_id: Optional[str] = None, public_ip: Optional[str] = None) -> None:
        self.id = id
        self.token = token
        self.unique_id = unique_id
        self.public_ip = public_ip

    def __repr__(self) -> str:
        return str(self)
    
    def __str__(self)  -> str:
        return f"<Config id={self.id} token='{self.token}'>"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int): return self.id == other
        if isinstance(other, Config): return id(self) == id(other)
        return False

    def __hash__(self) -> int:
        return hash(self.id)

def get_pending_config() -> Config:
    return Config(0, "0")

class ConfigManager:
    """
    Handles configuration state and persistence.
    """

    logger: logging.Logger = logging.getLogger("config")
    db = sqlite3.connect("config.db", check_same_thread=False)
    table_exists: bool = False

    @staticmethod
    def get_config(id: int) -> Optional[Config]:
        """
        Get the config for a client.
        """
        ConfigManager._ensure_table()
        config_data = ConfigManager.db.execute("SELECT * FROM config WHERE id = ?", (id,)).fetchone()

        if config_data is None:
            return None
        
        return Config(config_data[0], config_data[1])
    
    @staticmethod
    def persist_config(config: Config):
        """
        Persist a config.
        """
        ConfigManager._ensure_table()

        # Do not persist the pending config, only a populated or partially populated one
        if config.id == get_pending_config().id and config.token == get_pending_config().token:
            return

        try:
            ConfigManager.db.execute("INSERT INTO config VALUES (?, ?)", (config.id, config.token))
            ConfigManager.logger.info(f"Added config {config}")
        except sqlite3.IntegrityError:
            if config.id == get_pending_config().id:
                ConfigManager.db.execute("UPDATE config SET id = ? WHERE token = ?", (config.id, config.token))
                ConfigManager.logger.info(f"Updated config {config} by token")
            else:
                ConfigManager.db.execute("UPDATE config SET token = ? WHERE id = ?", (config.token, config.id))
                ConfigManager.logger.info(f"Updated config {config} by token")

        ConfigManager.db.commit()
    
    @staticmethod
    def get_all_configs() -> List[Config]:
        """int()
        Get all config.
        """
        ConfigManager._ensure_table()
        config_data = ConfigManager.db.execute("SELECT * FROM config").fetchall()

        return [Config(config[0], config[1]) for config in config_data]

    @staticmethod
    def remove_config(config: Config):
        """
        Remove a config.
        """
        ConfigManager._ensure_table()
        ConfigManager.db.execute("DELETE FROM config WHERE id = ?", (config.id,))
        ConfigManager.db.commit()
        ConfigManager.logger.info(f"Removed config {config}")

    @staticmethod
    def _ensure_table():
        """
        Ensure the config table exists.
        """

        if ConfigManager.table_exists:
            return

        ConfigManager.db.execute("CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, token TEXT)")
        ConfigManager.db.commit()

        ConfigManager.logger.info("Created config table")

        ConfigManager.table_exists = True