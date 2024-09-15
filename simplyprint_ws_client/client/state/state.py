import functools
from collections import OrderedDict
from typing import Any, Dict, Optional, List, Set, Generator, Callable, Tuple
from typing import OrderedDict as OrderedDictType
from typing import Type, TYPE_CHECKING

from traitlets import HasTraits, List as TraitletsList, Bunch, Undefined

if TYPE_CHECKING:
    from ...client.protocol.client_events import ClientEvent

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
    _field_generations: Dict[str, int]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._changed_fields = set()
        self._field_generations = {k: 0 for k in self.trait_names()}

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

        for field in fields:
            self._field_generations[field] += 1

    def has_changed(self, *fields: str) -> bool:
        if not fields:
            return bool(self._changed_fields)

        return bool(self._changed_fields.intersection(fields))

    def get_changed(self) -> List[str]:
        return list(self._changed_fields)

    def clear(self, *fields: Tuple[str, Optional[int]]):
        if not fields:
            self._changed_fields.clear()
            return

        # Clear generation for fields
        for field, generation in fields:
            current_gen = self._field_generations.get(field)

            # If no generation is given, clear all generations
            if generation is None or current_gen == generation:
                self._changed_fields.discard(field)

    def partial_clear(self, *fields: str):
        """ Clear a specific point in time of the state, by also keeping track of generations """
        generations = {field: self._field_generations[field] for field in fields}
        return functools.partial(self.clear, *generations.items())

    def get_field_event(self, field: str, owner=None) -> Optional[Type['ClientEvent']]:
        if owner is None:
            owner = self

        return owner.get_event_mapping(field) or owner.get_event_mapping(
            DEFAULT_EVENT) or self._root_state.get_event_mapping(field)

    def on_change(self, change: Bunch):
        if self._root_state is None:
            raise ValueError("ClientState can only be used with a root state")

        if change.type != "change":
            raise ValueError("ClientState can only be used on change events")

        owner: ClientState = change.owner

        if not isinstance(owner, ClientState):
            raise ValueError("ClientState can only be used with HasTraits")

        # Mark event as dirty.
        event = self.get_field_event(change.name, owner)

        if event is not None:
            self._root_state.mark_event_as_dirty(event)

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

    def iterate_client_state(self, func: Callable, obj: HasTraits, *args, **kwargs):
        """ Apply function callable to entire state tree """
        if not isinstance(obj, HasTraits):
            raise ValueError("iterate_client_state can only be used on HasTraits")

        func(obj, *args, **kwargs)

        for field, value in obj.traits().items():
            actual_value = getattr(obj, field) if obj.trait_has_value(field) else Undefined

            if isinstance(actual_value, HasTraits):
                self.iterate_client_state(func, actual_value, *args, **kwargs)
                continue

            if isinstance(value, HasTraits):
                self.iterate_client_state(func, value, *args, **kwargs)
                continue

            if isinstance(value, TraitletsList) and isinstance(actual_value, list):
                for item in actual_value:
                    if not isinstance(item, HasTraits):
                        continue

                    self.iterate_client_state(func, item, *args, **kwargs)

    def register_client_state(self, obj: HasTraits, prev_obj: Optional[HasTraits] = None):
        """ Set root state of tree """

        def func(o: HasTraits, p: Optional[HasTraits]):
            if isinstance(o, ClientState):
                o.set_root_state(self)

            if isinstance(p, HasTraits):
                # If we are replacing an old object, we need to mark all its fields as changed
                o.set_changed(*o.trait_names())

        self.iterate_client_state(func, obj, prev_obj)

    def mark_all_changed_dirty(self):
        """ Find all non-default state and make dirty. """

        def func(obj: ClientState):
            for field, value in obj.traits().items():
                actual_value = getattr(obj, field) if obj.trait_has_value(field) else Undefined

                if actual_value is Undefined or actual_value == value.default_value:
                    continue

                event = obj.get_field_event(field)

                if not event:
                    continue

                self.mark_event_as_dirty(event)

        self.iterate_client_state(func, self)

    def mark_event_as_dirty(self, event: Type['ClientEvent']) -> None:
        self._dirty_events[event] = None

    def get_dirty_events(self) -> List[Type['ClientEvent']]:
        return list(self._dirty_events.keys())

    def iter_dirty_events(self) -> Generator[Type['ClientEvent'], None, None]:
        # Skip if no dirty events
        if not self._dirty_events:
            return

        # Do not iterate beyond the last event
        last_event, _ = self._dirty_events.popitem(last=True)
        self.mark_event_as_dirty(last_event)

        while self._dirty_events:
            client_event, _ = self._dirty_events.popitem(last=False)

            yield client_event

            if client_event is last_event:
                break
