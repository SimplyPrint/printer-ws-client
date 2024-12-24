"""
Events sent to and from a connection.
"""

from simplyprint_ws_client.events import Event


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


