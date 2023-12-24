from typing import Optional

class ConfigMeta(type):
    """ 
    Automatically add correct slots based on
    type annotations for config definitions.
    """
        
    def __new__(mcs, name, bases, ns):
        slots = set(ns.get('__slots__', ()))

        # Traverse parent classes and add their slots
        for base in bases:
            if hasattr(base, '__slots__'):
                slots |= set(base.__slots__)

        annotations = ns.get('__annotations__', {})
        slots |= set(annotations.keys())
        
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

    public_ip: Optional[str]
    unique_id: Optional[str]

    def is_pending(self) -> bool:
        return self.id == 0
    
    def is_blank(self) -> bool:
        return self.is_pending() and len(self.token) < 2

    def __init__(self, **kwargs) -> None:            
        for key in kwargs:
            setattr(self, key, kwargs[key])
    
    def as_dict(self) -> dict:
        return dict(sorted([ (slot, getattr(self, slot)) for slot in self.__slots__ if hasattr(self, slot) ], key=lambda x: x[0]))

    def __repr__(self) -> str:
        return str(self)
    
    def __str__(self)  -> str:
        config_id = self.id if hasattr(self, "id") else "None"
        config_token = self.token if hasattr(self, "token") else "None"
    
        return f"<Config id={config_id} token='{config_token}'>"

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

    @staticmethod
    def get_blank() -> 'Config':
        return Config(id=0, token="0")
