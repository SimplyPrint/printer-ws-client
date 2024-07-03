from typing import NamedTuple, List, Dict, Set, Iterator, TypeVar, Generic, Iterable

from ..utils.predicate import Predicate, Constant


class PredicateTreeNode(NamedTuple):
    predicate: Predicate
    predicates: List['PredicateTreeNode']
    resources: Set[int]

    def contains(self, item: Predicate):
        if not isinstance(item, Predicate):
            return False

        for entry in self.predicates:
            if entry.predicate == item:
                return True

        return False

    def push(self, resource_id: int, *predicates: Predicate):
        if len(predicates) == 0:
            self.resources.add(resource_id)
            return

        predicates = list(predicates)
        predicate = predicates.pop(0)

        for entry in self.predicates:
            if entry.predicate == predicate:
                entry.push(resource_id, *predicates)
                return

        entry = PredicateTreeNode(predicate, [], set())
        self.predicates.append(entry)
        entry.push(resource_id, *predicates)


_TResource = TypeVar('_TResource')


class EventBusPredicateBucket(Generic[_TResource]):
    """Store data based on predicate trees. Useful for very dynamic event systems."""

    resources: Dict[int, _TResource]
    predicates: PredicateTreeNode

    def __init__(self):
        # Root predicate node, we skip this and access the children directly.
        self.predicates = PredicateTreeNode(Constant(True), [], set())
        self.resources = {}

    def add(self, resource: _TResource, *predicates) -> int:
        next_resource_id = max(list(self.resources.keys()) + [-1]) + 1
        self.resources[next_resource_id] = resource
        self.predicates.push(next_resource_id, *predicates)
        return next_resource_id

    def remove(self, resource: _TResource):
        for resource_id, value in list(self.resources.items()):
            if value == resource:
                self.remove_resource_id(resource_id)

    def remove_resource_id(self, resource_id: int, entry: PredicateTreeNode = None):

        self.resources.pop(resource_id, None)

        if entry is None:
            entry = self.predicates

        for i, child in enumerate(entry.predicates):
            if resource_id in child.resources:
                child.resources.discard(resource_id)

                if len(child.resources) == 0 and len(child.predicates) == 0:
                    entry.predicates.pop(i)

                return

            self.remove_resource_id(resource_id, child)

        # Clean up empty entries.
        for i, child in enumerate(list(entry.predicates)):
            if len(child.resources) == 0 and len(child.predicates) == 0:
                entry.predicates.pop(i)

    def get_resources(self, *resources) -> Iterable[_TResource]:
        return [self.resources[resource] for resource in resources if resource in self.resources]

    def evaluate(self, *args, **kwargs) -> Iterator[int]:
        b = self.predicates

        while len(b.predicates) > 0:
            for entry in b.predicates:
                if entry.predicate(*args, **kwargs):
                    yield from entry.resources
                    b = entry
                    break
            else:
                break
