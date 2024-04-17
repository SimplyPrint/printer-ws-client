import collections
from typing import Dict, Optional

from state_effect.property_path import PropertyPath


class _Version(int):
    def __add__(self, other):
        return _Version(super().__add__(other))


class Version(object):
    """A version keeps track of changed properties on an object.

    For objects that are just singular values, the top level current
    and read_at variables are enough to determine if it has changed.

    TODO make thread safe.
    """

    __slots__ = ('__now', '__read', '__props')

    __now: _Version
    __read: _Version
    __props: Dict[PropertyPath, _Version]

    def __init__(self):
        self.__now = _Version(0)
        self.__read = _Version(0)
        self.__props = {}

    @property
    def current(self):
        return self.__now

    @property
    def read_at(self):
        return self.__read

    def has_changes(self, since: Optional[_Version] = None):
        if not since:
            since = self.__read

        return since < self.__now

    def has_changed(self, *props: PropertyPath, since: Optional[_Version] = None):
        """Whether a property has changed"""
        if not since:
            since = self.__read

        for prop in props:
            ver = self.__props.get(prop, None)

            if ver is None:
                continue

            # If the prop version is newer than
            if ver > since:
                return True

        return False

    def mark_read(self):
        self.__read = self.__now

    def update_props(self, *props: PropertyPath):
        self.__now += 1

        for path in props:
            self.__props[path] = self.__now

    def get_changes(self, since: Optional[_Version] = None):
        if not since:
            since = self.__read

        for path, property_version in self.__props.items():
            if property_version <= since:
                continue

            yield path, property_version

    def get_changes_by_version(self):
        properties = collections.defaultdict(set)

        for path, property_version in self.get_changes():
            properties[property_version].add(path)

        return properties
