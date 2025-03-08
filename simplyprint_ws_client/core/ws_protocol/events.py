"""
Events sent to and from a connection.
"""

from ...events import Event


class ConnectionEvent(Event):
    ...


class ConnectionIncomingEvent(ConnectionEvent):
    ...


class ConnectionOutgoingEvent(ConnectionEvent):
    ...


class ConnectionEstablishedEvent(ConnectionEvent):
    v: int

    def __init__(self, v: int):
        self.v = v


class ConnectionLostEvent(ConnectionEvent):
    v: int

    def __init__(self, v: int):
        self.v = v


class ConnectionSuspectEvent(ConnectionEvent):
    ...
