import sqlite3
import logging

from typing import Optional, List

class Config:
    """
    Configuration object.
    """
    
    __slots__ = { "id", "token", "unique_id", "public_ip" }

    id: int
    token: str
    unique_id: Optional[str]
    public_ip: Optional[str]

    def is_pending(self) -> bool:
        return self.id == 0
    
    def is_blank(self) -> bool:
        return self.is_pending() and len(self.token) < 2

    def __init__(self, **kwargs) -> None:            
        for key in kwargs:
            setattr(self, key, kwargs[key])
    
    def as_dict(self) -> dict:
        return { slot: getattr(self, slot) for slot in self.__slots__ if hasattr(self, slot) }

    def __repr__(self) -> str:
        return str(self)
    
    def __str__(self)  -> str:
        return f"<Config id={self.id} token='{self.token}'>"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int): return self.id == other
        if isinstance(other, Config): return id(self) == id(other)
        return False
    
    def partial_eq(self, other: 'Config') -> bool:
        # Loop over all slots in other
        for slot in other.__slots__:
            if not hasattr(other, slot):
                continue

            # If the slot is not in self, or the values are not equal
            if not hasattr(self, slot) or getattr(self, slot) != getattr(other, slot):
                return False

        return True

    def __hash__(self) -> int:
        return hash(self.id)

    @staticmethod
    def get_blank() -> 'Config':
        return Config(id=0, token="0")
