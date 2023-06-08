from typing import Set, List, Dict, Any
from traitlets import HasTraits

DEFAULT_EVENT = "__default__"

class ClientState(HasTraits):
    """
    A class that represents a state that can be sent to the client.

    Event map is a dictionary that maps the name of a trait to the event that should be sent when it changes.
    
    The key __default__ is reserved for the default event that should be sent when any trait changes.
    """
    event_map: Dict[str, Any]

class RootState(HasTraits):
    _dirty: Set
    _changed_fields: Dict[int, Set[str]]
    event_map: Dict[str, Any]

    def __init__(self, **kwargs):
        super().__init__()

        self._dirty = set()
        self._changed_fields = dict()

        self._changed_fields[id(self)] = set()
        self.observe(self._notify_change)

        for field, value in kwargs.items():
            setattr(self, field, value)
            if isinstance(value, HasTraits):
                value.observe(self._notify_change)
                self._changed_fields[id(value)] = set()
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, HasTraits):
                        item.observe(self._notify_change)
                        self._changed_fields[id(item)] = set()


    def _notify_change(self, change):
        """Will trigger when state fields are updated, marking corresponding events as dirty"""

        owner = change['owner']
        self._changed_fields[id(owner)].add(change['name'])

        if not hasattr(owner, 'event_map'):
            return

        event = owner.event_map.get(change['name'], owner.event_map.get(DEFAULT_EVENT, self.event_map.get(change['name'], None)))

        if event is None:
            return
                
        self._dirty.add(event)

    def _build_events(self):
        """Generator - creates :class:`ClientEvent` instances from dirty"""

        while self._dirty:
            client_event = self._dirty.pop()
            yield client_event(self, self._changed_fields)
        
        self._changed_fields = {
            key: set() for key in self._changed_fields.keys()
        }

