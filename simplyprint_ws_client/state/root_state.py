from collections import OrderedDict
from typing import Any, Dict, List, Optional, Union
from typing import OrderedDict as OrderedDictType
from typing import Set, Type

from traitlets import HasTraits

from .state import ClientState
from ..events.client_events import ClientEvent

DEFAULT_EVENT = "__default__"

class RootState(ClientState):
    """
    A class that represents the root state of a client. Handles reactive updates and dirty checking.

    Every time a state is changed, a lookup in the event map is performed to find the corresponding event,
    afterward a dirty event is added to the dirty set.

    Then we can iterate over the dirty set and build the corresponding events which on generate_data checks the changed fields
    to decide which data has changed and needs to be sent.
    """

    _dirty: OrderedDictType[Type[ClientEvent], None]
    _changed_fields: Dict[int, Set[str]]

    def __init__(self, **kwargs):
        super().__init__()

        self._dirty = OrderedDict()
        self._changed_fields = dict()

        self._changed_fields[id(self)] = set()
        self.observe(self._notify_change)

        for field, value in kwargs.items():
            setattr(self, field, value)

            if isinstance(value, HasTraits):
                value.observe(self._notify_change)
                self._changed_fields[id(value)] = set()

            # TODO implement traitlets list container
            elif isinstance(value, list):
                for item in value:
                    if not isinstance(item, HasTraits):
                        continue

                    item.observe(self._notify_change)
                    self._changed_fields[id(item)] = set()

    def _notify_change(self, change):
        """Will trigger when state fields are updated, marking corresponding events as dirty"""
        owner = change['owner']

        # With Always events we need to also check if
        # the value has changed before setting the changed
        # fields here.
        try:
            has_changed = change['old'] != change['new']
        except Exception:
            has_changed = True

        if has_changed:
            self._changed_fields[id(owner)].add(change['name'])

        # If the change from old to new is an object, replace the id() in _changed_fields
        # and add all its fields to it, so to mark the entire object as "changed"
        # if isinstance(change["old"], HasTraits) and isinstance(change["new"], HasTraits):
        #    self._changed_fields[id(change["new"])] = change["new"].trait_names()
        #    del self._changed_fields[id(change["old"])]

        if not hasattr(owner, '_event_mapping'):
            return

        event = owner._event_mapping.get(change['name']) or owner._event_mapping.get(
            DEFAULT_EVENT) or self._event_mapping.get(change['name'])

        if event is None:
            return

        self.mark_event_as_dirty(event)

    def mark_event_as_dirty(self, event: Type[ClientEvent]):
        """Mark an event as dirty"""
        self._dirty[event] = None

    def _build_events(self, for_client: Optional[Union[str, int]] = None):
        """
        Generator - creates :class:`ClientEvent` instances from dirty
        
        Ensure the ordered "set" is iterated in the same order as it was inserted,
        so we pop from the front.
        """

        while self._dirty:
            client_event, _ = self._dirty.popitem(last=False)
            yield client_event()

    def get_event_types(self) -> List[Type[ClientEvent]]:
        """Get all event types that are currently dirty"""
        return list(self._dirty.keys())

    def has_changed(self, obj: HasTraits, name: Optional[str] = None, clear: bool = True):
        """Check if a field has changed since last update"""
        if name is None:
            predicate = len(self._changed_fields[id(obj)]) > 0

            if predicate and clear:
                self._changed_fields[id(obj)].clear()

            return predicate

        predicate = name in self._changed_fields[id(obj)]

        if predicate and clear:
            self._changed_fields[id(obj)].remove(name)

        return predicate
