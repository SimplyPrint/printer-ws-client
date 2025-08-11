__all__ = ["_resize_state_inplace"]

from typing import List, TypeVar, Callable

from .state_model import StateModel

_T = TypeVar("_T", bound=StateModel)


def _resize_state_inplace(
    ctx: StateModel, target: List[_T], size: int, default: Callable[[int], _T]
):
    if len(target) == size:
        return

    if size > len(target):
        for _ in range(size - len(target)):
            target.append(model := default(len(target)))
            model.provide_context(ctx)
    else:
        del target[size:]
