from abc import abstractmethod
from typing import Dict, Type, Any, List, Union, Optional

from ..helpers.intervals import Intervals

class ServerEventError(ValueError):
    pass

class ServerEventTraits:
    def __str__(cls):
        return cls.name
    
    def __repr__(cls) -> str:
        return f"<ServerEvent {cls.name}>"
    
    def __eq__(cls, other: object) -> bool:
        if isinstance(other, str): return cls.name == other
        if isinstance(other, ServerEvent): return cls.name == other.name
        if isinstance(other, ServerEventTraits): return cls.name == other.name
        return False
    
    def __hash__(cls) -> int:
        return hash(cls.name)

class ServerEventType(type, ServerEventTraits):
    def __repr__(cls) -> str:
        return f"<Event {cls.name}>"

class ServerEvent(ServerEventTraits, metaclass=ServerEventType):
    name: str = ""
    data: Dict[str, Any] = {}
    
    # Generic event data
    def __init__(self, name: str, data: Dict[str, Any] = {}):
        self.data = data

        if self.name != name:
            raise ServerEventError(f"Event type {type} does not match event name {self.name}")
        
        self.on_event()

    @abstractmethod
    def on_event(self):
        """
        Secondary constructor for events, useful for when the event is received to avoid super calls
        """
        pass

    @classmethod
    def on(cls: Type['ServerEvent'], func):
        """
        Decorator for registering a handle for a specific event.
        We do this by marking the function with the event type, so
        we later can extract the event type from the function.
        """
        func._event = cls
        func._pre = 0
        return func
    
    @classmethod
    def before(cls: Type['ServerEvent'], func):
        """
        Decorator for registering a pre-handle for a specific event.
        This calls the actual handler, and has to return the event.
        """
        func._event = cls
        func._pre = 1
        return func

class ErrorEvent(ServerEvent):
    name = "error"

    def on_event(self):
        self.error: str = self.data.get("error", "")

class NewTokenEvent(ServerEvent):
    name = "new_token"

    def on_event(self):
        self.short_id: str = self.data.get("short_id", "")
        self.token: str = self.data.get("token", "")
        self.no_exist: bool = self.data.get("no_exist", False)

class ConnectEvent(ServerEvent):
    name = "connected"

    def on_event(self):
        self.in_setup: bool = bool(self.data.get("in_setup", 0))
        self.intervals: Intervals = Intervals(self.data.get("interval", {}))
        self.printer_settings: PrinterSettingsEvent = PrinterSettingsEvent(PrinterSettingsEvent.name, self.data.get("printer_settings", {}))
        self.short_id: Optional[str] = self.data.get("short_id")
        self.reconnect_token: Optional[str] = self.data.get("reconnect_token")
        self.printer_name: Optional[str] = self.data.get("name")

class SetupCompleteEvent(ServerEvent):
    name = "complete_setup"

    def on_event(self):
        self.printer_id: str = self.data.get("printer_id", "")

class IntervalChangeEvent(ServerEvent):
    name = "interval_change"

    def on_event(self):
        self.intervals: Intervals = Intervals(self.data)

class PongEvent(ServerEvent):
    name = "pong"

class StreamReceivedEvent(ServerEvent):
    name = "stream_received"

class PrinterSettingsEvent(ServerEvent):
    name = "printer_settings"

    def on_event(self):
        from ..printer import PrinterSettings, PrinterDisplaySettings

        self.name = self.data.get("name", "")
        self.printer_settings = PrinterSettings(has_psu=self.data.get("has_psu", False), has_filament_sensor=self.data.get("has_filament_sensor", False))
        self.display_settings = PrinterDisplaySettings(**self.data.get("display", {}))

class MultiPrinterAddResponseEvent(ServerEvent):
    name = "add_connection"

    def on_event(self): 
        self.printer_id: Optional[int] = self.data.get("pid")
        self.status: bool = self.data.get("status", False)
        self.unique_id: Optional[str] = self.data.get("unique_id", "")