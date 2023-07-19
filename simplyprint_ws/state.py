from typing import Any, Dict, Optional, Set, Type

from traitlets import HasTraits

from .events.client_events import ClientEvent

DEFAULT_EVENT = "__default__"


class ClientState(HasTraits):
    """
    A class that represents a state that can be sent to the client.

    Event map is a dictionary that maps the name of a trait to the event that should be sent when it changes.

    The key __default__ is reserved for the default event that should be sent when any trait changes.
    """
    event_map: Dict[str, Any]


class RootState(HasTraits):
    """
    A class that represents the root state of a client. Handles reactive updates and dirty checking.

    Every time a state is changed, a lookup in the event map is performed to find the corresponding event,
    afterwards a dirty event is added to the dirty set.

    Then we can iterate over the dirty set and build the corresponding events which on generate_data checks the changed fields
    to decide which data has changed and needs to be sent.
    """
    event_map: Dict[str, Any]

    _dirty: Set[Type[ClientEvent]]
    _changed_fields: Dict[int, Set[str]]

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

        # If the change from old to new is an object, replace the id() in _changed_fields
        # and add all its fields to it, so to mark the entire object as "changed"
        # if isinstance(change["old"], HasTraits) and isinstance(change["new"], HasTraits):
        #    self._changed_fields[id(change["new"])] = change["new"].trait_names()
        #    del self._changed_fields[id(change["old"])]

        if not hasattr(owner, 'event_map'):
            return

        event = owner.event_map.get(change['name']) or owner.event_map.get(
            DEFAULT_EVENT) or self.event_map.get(change['name'])

        if event is None:
            return

        self._dirty.add(event)

    def _build_events(self, forClient: Optional[int] = None):
        """Generator - creates :class:`ClientEvent` instances from dirty"""

        while self._dirty:
            client_event = self._dirty.pop()
            yield client_event(state=self, forClient=forClient)

    def has_changed(self, obj: HasTraits, name: Optional[str] = None):
        """Check if a field has changed since last update"""
        if name is None:
            predicate = len(self._changed_fields[id(obj)]) > 0
            if predicate:
                self._changed_fields[id(obj)].clear()
            return predicate

        predicate = name in self._changed_fields[id(obj)]

        if predicate:
            self._changed_fields[id(obj)].remove(name)

        return predicate
