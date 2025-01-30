__all__ = ['ClientName']

from typing import TYPE_CHECKING, List, Optional, Union

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

if TYPE_CHECKING:
    from ...core.client import Client
    from ...core.config import PrinterConfig

    TClientContext = Union[Client, PrinterConfig]
else:
    TClientContext = Union['Client', 'PrinterConfig']


class ClientName(str):
    ctx: TClientContext
    stack: List[str]

    def __new__(cls, ctx: TClientContext) -> str:
        return super().__new__(cls, ctx.unique_id)

    def __init__(self, ctx: TClientContext) -> None:
        self.ctx = ctx
        self.stack = []

    def __str__(self) -> str:
        return ".".join([self.ctx.unique_id] + self.stack)

    def __hash__(self) -> int:
        return hash(str(self))

    def copy(self) -> Self:
        return ClientName(self.ctx).push_all(self.stack)

    def push_all(self, names: List[str]) -> Self:
        for name in names:
            self.push(name)
        return self

    def push(self, name: str) -> Self:
        self.stack.append(name)
        return self

    def pop(self) -> Self:
        self.stack.pop()
        return self

    def peek(self) -> Optional[str]:
        if len(self.stack) == 0:
            return None

        return self.stack[-1]

    def getChild(self, suffix: str) -> Self:
        return self.copy().push(suffix)
