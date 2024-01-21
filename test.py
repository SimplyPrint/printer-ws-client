from traitlets import Int, Instance, Unicode

from simplyprint_ws_client.state import Always
from simplyprint_ws_client.state.state import State, ClientState


class T(ClientState):
    i: int = Int()
    a: str = Always(Unicode())


class TestState(State):
    l: T = Instance(T)
    i: int = Int()


s = TestState(i=10, l=T(i=11))

s.i = 11
s.l.i = 12
s.l.a = "test"
s.l.a = "test"
s.l.a = "test"
s.l = T(i=13)
