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


class EventBusPredicateTree(Generic[_TResource]):
    """Store data based on predicate trees. Useful for very dynamic event systems."""

    root: PredicateTreeNode
    resources: Dict[int, _TResource]
    current_resource_id: int = 0

    def __init__(self):
        # Root predicate node, we skip this and access the children directly.
        self.root = PredicateTreeNode(Constant(True), [], set())
        self.resources = {}

    def add(self, resource: _TResource, *predicates) -> int:
        self.current_resource_id = next_resource_id = self.current_resource_id + 1
        self.resources[next_resource_id] = resource
        self.root.push(next_resource_id, *predicates)
        return next_resource_id

    def remove(self, resource: _TResource):
        for resource_id, value in list(self.resources.items()):
            if value == resource:
                self.remove_resource_id(resource_id)

    def remove_resource_id(self, resource_id: int, entry: PredicateTreeNode = None):
        # Only perform early exit if the resource does not exist at the initial call.
        # For nested calls the resource has already been removed.
        if resource_id not in self.resources and entry is None:
            return
        else:
            # We actually do not know if it exists, so we pass a default anyhow.
            self.resources.pop(resource_id, None)

        if entry is None:
            entry = self.root

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
        b = self.root

        while len(b.predicates) > 0:
            for entry in b.predicates:
                if entry.predicate(*args, **kwargs):
                    yield from entry.resources
                    b = entry
                    break
            else:
                break
