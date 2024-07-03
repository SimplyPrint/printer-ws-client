import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, fields
from typing import Optional, Tuple

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

TKey = Tuple[int, str]


# TODO: Replace with a proper ORM-component
# And centralize the config management file with tables, versioning, singleton instances (settings)
# and more.
class Config(ABC):
    """Config Entity interface for persistence."""

    def __repr__(self):
        return f"{self.__class__.__name__}({self.as_dict()})"

    def __eq__(self, other: object) -> bool:
        """Each instance is unique."""
        if isinstance(other, self.__class__):
            return id(self) == id(other)

        return False

    def __hash__(self) -> int:
        return hash(id(self))

    @classmethod
    def make_hashable(cls):
        """Override standard hash and eq methods from dataclass + pydantic etc."""
        cls.__hash__ = Config.__hash__
        cls.__eq__ = Config.__eq__

    @classmethod
    def update_dict_keys(cls, data: dict):
        """Modify incoming data to match the keys of the config."""
        if "pk" in data:
            data[cls.keys()[0]] = data.pop("pk")

        if "sk" in data:
            data[cls.keys()[1]] = data.pop("sk")

        return data

    def partial_eq(self, config: Optional['Config'] = None, **kwargs) -> bool:
        """Check if the other config is partially equal to this one."""

        data = self.as_dict()

        if config is not None:
            kwargs.update(config.as_dict())

        for key, value in kwargs.items():
            if key not in data or data[key] != value:
                return False

        return True

    @property
    def pk(self) -> int:
        """Primary key for the config."""
        return int(getattr(self, self.keys()[0]))

    @property
    def sk(self) -> str:
        """Secondary key for the config."""
        return str(getattr(self, self.keys()[1]))

    @property
    def key(self) -> TKey:
        return self.pk, self.sk

    @staticmethod
    @abstractmethod
    def keys() -> tuple:
        """Return the keys of the config."""
        raise NotImplemented()

    @abstractmethod
    def is_empty(self) -> bool:
        raise NotImplemented()

    @abstractmethod
    def as_dict(self) -> dict:
        raise NotImplemented()

    def as_json(self) -> str:
        return json.dumps(self.as_dict())

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> Self:
        raise NotImplemented()


@dataclass
class PrinterConfig(Config):
    """
    Configuration object for printers.
    """

    id: int
    token: str

    name: Optional[str] = None
    in_setup: Optional[bool] = None
    short_id: Optional[str] = None
    public_ip: Optional[str] = None
    unique_id: Optional[str] = None

    @staticmethod
    def keys() -> tuple:
        return "id", "token"

    def is_empty(self) -> bool:
        data = self.as_dict()
        data = {k: v for k, v in data.items() if v is not None}

        return self.is_default() and len(set(data.keys()) - {"id", "token"}) == 0

    def as_dict(self) -> dict:
        data = {}

        for field in fields(self):
            value = getattr(self, field.name)
            data[field.name] = value

        return data

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(**data)

    def is_pending(self) -> bool:
        return self.id == 0 or self.id is None or self.in_setup

    def is_default(self) -> bool:
        return self.is_pending() and (self.token is None or len(self.token) < 2)

    @classmethod
    def get_blank(cls) -> Self:
        return cls(id=0, token="0")

    @classmethod
    def get_new(cls) -> Self:
        return cls(id=0, token="0", unique_id=str(uuid.uuid4()))
