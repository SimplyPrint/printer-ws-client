import uuid
from typing import Optional


class ConfigMeta(type):
    """ 
    Automatically add correct slots based on
    type annotations for config definitions.
    """

    def __new__(mcs, name, bases, ns):
        annotations = ns.get('__annotations__', {})
        slots = set(ns.get('__slots__', ()))

        # Traverse parent classes and add their slots
        for base in bases:
            if hasattr(base, '__slots__'):
                slots |= set(base.__slots__)
            if hasattr(base, '__annotations__'):
                annotations.update(base.__annotations__)

        slots |= set(annotations.keys())

        ns['__annotations__'] = annotations
        ns['__slots__'] = slots
        return super().__new__(mcs, name, bases, ns)


class Config(metaclass=ConfigMeta):
    """
    Configuration object.
    """

    id: int
    token: str

    name: Optional[str]
    in_setup: Optional[bool]
    short_id: Optional[str]
    public_ip: Optional[str]
    unique_id: Optional[str]

    def __init__(self, **kwargs) -> None:
        for key in kwargs:
            if not key in self.__slots__:
                continue

            setattr(self, key, kwargs[key])
    
        for slot in self.__slots__:
            if not hasattr(self, slot):
                setattr(self, slot, None)

    def is_pending(self) -> bool:
        return self.id == 0 or self.id is None
    
    def is_default(self) -> bool:
        return self.is_pending() and (self.token is None or len(self.token) < 2)

    def is_blank(self) -> bool:
        # Check if any other slots are filled
        is_blank = True

        for slot in self.__slots__:
            if not hasattr(self, slot):
                continue

            if slot in ["id", "token"]:
                continue

            if getattr(self, slot) is not None:
                is_blank = False
                break

        return self.is_default() and is_blank

    def as_dict(self) -> dict:
        return dict(sorted([(slot, getattr(self, slot)) for slot in self.__slots__ if hasattr(self, slot)], key=lambda x: x[0]))

    def partial_eq(self, other: 'Config') -> bool:
        # Loop over all slots in other
        for slot in other.__slots__:
            if not hasattr(other, slot) or getattr(other, slot) is None:
                continue
            
            # Skip default values
            if hasattr(other.__class__, slot) and getattr(other, slot) == getattr(other.__class__, slot):
                continue

            # If the slot is not in self, or the values are not equal
            if not hasattr(self, slot) or getattr(self, slot) != getattr(other, slot):
                return False

        return True

    @staticmethod
    def get_blank() -> 'Config':
        return Config(id=0, token="0")
    
    def get_new(self) -> 'Config':
        return Config(id=self.id, token=self.token, unique_id=str(uuid.uuid4()))

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f"<Config {self.as_dict()}'>"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.id == other
        
        if isinstance(other, Config):
            return id(self) == id(other)
    
        return False

    def __hash__(self) -> int:
        return hash(id(self))
