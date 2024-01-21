import functools
from collections import OrderedDict
from typing import Any, Dict, Optional, List, Set, Generator
from typing import OrderedDict as OrderedDictType
from typing import Type, TYPE_CHECKING

from traitlets import HasTraits, List as TraitletsList, Bunch, Undefined

if TYPE_CHECKING:
    from ..events.client_events import ClientEvent

DEFAULT_EVENT = "__default__"


class ClientState(HasTraits):
    """
    A class that represents a state that can be sent to the client.

    Event map is a dictionary that maps the name of a trait to the event that should be sent when it changes.

    The key __default__ is reserved for the default event that should be sent when any trait changes.
    """
    _event_mapping: Dict[str, Any] = None
    _root_state: Optional['State'] = None

    _changed_fields: Set[str]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._changed_fields = set()
        self.observe(self.on_change)

    @classmethod
    def get_event_mapping(cls, name: str) -> Optional[Type['ClientEvent']]:
        """Get the event mapping for a given name"""
        if cls._event_mapping is None:
            return None

        return cls._event_mapping.get(name)

    def set_root_state(self, root_state: 'State'):
        self._root_state = root_state

    def set_changed(self, *fields: str):
        self._changed_fields.update(fields)

    def has_changed(self, *fields: str) -> bool:
        if not fields:
            return bool(self._changed_fields)

        return bool(self._changed_fields.intersection(fields))

    def get_changed(self) -> List[str]:
        return list(self._changed_fields)

    def clear(self, *fields: str):
        if not fields:
            self._changed_fields.clear()
            return

        self._changed_fields.difference_update(fields)

    def partial_clear(self, *fields: str):
        return functools.partial(self.clear, *fields)

    def on_change(self, change: Bunch):
        if self._root_state is None:
            raise ValueError("ClientState can only be used with a root state")

        if change.type != "change":
            raise ValueError("ClientState can only be used on change events")

        owner: ClientState = change.owner

        if not isinstance(owner, ClientState):
            raise ValueError("ClientState can only be used with HasTraits")

        # Mark event as dirty.
        event = owner.get_event_mapping(change.name) or owner.get_event_mapping(
            DEFAULT_EVENT) or self._root_state.get_event_mapping(change.name)

        if event is not None:
            self._root_state.mark_event_as_dirty(event)

        # Mark field as changed if it has changed.
        # Always will always trigger changes,
        # so we have to check if the value has actually changed.
        if change.old == change.new:
            return

        # Ensure we keep proper track of changes
        if isinstance(change.new, HasTraits):
            self._root_state.register_client_state(change.new, change.old)

        owner.set_changed(change.name)


def to_event(client_event: Type['ClientEvent'], *names: str):
    """
    Map events from a ClientState class to its _event_mapping
    """

    def wrapper(cls: Type[ClientState]):
        if not issubclass(cls, ClientState):
            raise ValueError("to_event can only be used on subclasses of ClientState")

        if cls._event_mapping is None:
            cls._event_mapping = {}

        if not names:
            cls._event_mapping[DEFAULT_EVENT] = client_event
            return cls

        for name in names:
            cls._event_mapping[name] = client_event

        return cls

    return wrapper


class State(ClientState):
    _dirty_events: OrderedDictType[Type['ClientEvent'], None]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._dirty_events = OrderedDict()
        self.register_client_state(self)

    def register_client_state(self, obj: HasTraits, old_obj: Optional[HasTraits] = None):
        if not isinstance(obj, HasTraits):
            raise ValueError("register_client_state can only be used on HasTraits")

        if isinstance(obj, ClientState):
            obj.set_root_state(self)

        if isinstance(old_obj, HasTraits):
            # If we are replacing an old object, we need to mark all its fields as changed
            obj.set_changed(*obj.trait_names())

        for field, value in obj.traits().items():
            actual_value = getattr(self, field) if self.trait_has_value(field) else Undefined

            if isinstance(actual_value, HasTraits):
                self.register_client_state(actual_value)
                continue

            if isinstance(value, HasTraits):
                self.register_client_state(value)
                continue

            if isinstance(value, TraitletsList) and isinstance(actual_value, list):
                for item in actual_value:
                    if not isinstance(item, HasTraits):
                        continue

                    self.register_client_state(item)

    def mark_event_as_dirty(self, event: Type['ClientEvent']) -> None:
        self._dirty_events[event] = None

    def get_dirty_events(self) -> List[Type['ClientEvent']]:
        return list(self._dirty_events.keys())

    def iter_dirty_events(self) -> Generator[Type['ClientEvent'], None, None]:
        while self._dirty_events:
            client_event, _ = self._dirty_events.popitem(last=False)

            yield client_event
