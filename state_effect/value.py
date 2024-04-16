import collections
from typing import Dict, Optional

from state_effect.property_path import PropertyPath, p


class _Versioned(object):
    __slots__ = ('__last_seen', '__global_version', '__property_versions')

    __last_seen: int
    __global_version: int
    __property_versions: Dict[PropertyPath, int]

    def __init__(self):
        self.__last_seen = 0
        self.__global_version = 0
        self.__property_versions = {}

    @property
    def current_version(self):
        return self.__global_version

    @property
    def last_seen_version(self):
        return self.__last_seen

    def mark_seen(self):
        self.__last_seen = self.__global_version

    def update_properties(self, *properties: PropertyPath):
        self.__global_version += 1

        for path in properties:
            self.__property_versions[path] = self.__global_version

    def get_changed_since(self, version: Optional[int] = None):
        if not version:
            version = self.__last_seen

        for path, property_version in self.__property_versions.items():
            if property_version <= version:
                continue

            yield path, property_version

    def get_changed_by_version(self):
        properties = collections.defaultdict(set)

        for path, property_version in self.get_changed_since():
            properties[property_version].add(path)

        return properties


if __name__ == "__main__":
    v = _Versioned()
    v.update_properties(p.a)
    v.update_properties(p.b)

    print(list(v.get_changed_since(v.__global_version)))
