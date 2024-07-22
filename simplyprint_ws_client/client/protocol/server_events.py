from abc import abstractmethod
from typing import Dict, Type, Any, Optional

from ...events.event import Event
from ...helpers.intervals import Intervals


class ServerEventError(ValueError):
    pass


class ServerEvent(Event):
    event_type: str
    data: Dict[str, Any] = {}

    # Generic event data
    def __init__(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        self.data = data or {}

        if self.event_type != event_type:
            raise ServerEventError(f"Event type {event_type} does not match event name {self.event_type}")

        self.on_event()

    # Better for debugging
    def __str__(self):
        return f"<{self.__class__.__base__.__name__} {self.get_name()} {self.data}>"

    def __repr__(self):
        return f"<{self.__class__.__base__.__name__} {self.get_name()} {self.data}>"

    @classmethod
    def get_name(cls) -> str:
        if cls is ServerEvent:
            return ServerEvent.__name__

        return cls.event_type

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
        func._pre = 1
        return func

    @classmethod
    def before(cls: Type['ServerEvent'], func):
        """
        Decorator for registering a pre-handle for a specific event.
        This calls the actual handler, and has to return the event.
        """
        func._event = cls
        func._pre = 0
        return func


class ErrorEvent(ServerEvent):
    event_type = "error"

    def on_event(self):
        self.error: str = self.data.get("error", "")


class NewTokenEvent(ServerEvent):
    event_type = "new_token"

    def on_event(self):
        self.short_id: str = self.data.get("short_id", "")
        self.token: str = self.data.get("token", "")
        self.no_exist: bool = self.data.get("no_exist", False)


class ConnectEvent(ServerEvent):
    event_type = "connected"

    def on_event(self):
        self.in_setup: bool = bool(self.data.get("in_setup", 0))
        self.intervals: Intervals = Intervals(self.data.get("interval", {}))
        self.printer_settings: PrinterSettingsEvent = PrinterSettingsEvent(PrinterSettingsEvent.get_name(),
                                                                           self.data.get("printer_settings", {}))
        self.short_id: Optional[str] = self.data.get("short_id")
        self.reconnect_token: Optional[str] = self.data.get("reconnect_token")
        self.printer_name: Optional[str] = self.data.get("name")


class SetupCompleteEvent(ServerEvent):
    event_type = "complete_setup"

    def on_event(self):
        self.printer_id: str = self.data.get("printer_id", "")


class IntervalChangeEvent(ServerEvent):
    event_type = "interval_change"

    def on_event(self):
        self.intervals: Intervals = Intervals(self.data)


class PongEvent(ServerEvent):
    event_type = "pong"


class StreamReceivedEvent(ServerEvent):
    event_type = "stream_received"


class PrinterSettingsEvent(ServerEvent):
    event_type = "printer_settings"

    def on_event(self):
        self.event_type = self.data.get("name", "")

        # Import here to avoid circular imports
        from ...client.state import PrinterSettings, PrinterDisplaySettings

        self.printer_settings = PrinterSettings(has_psu=self.data.get("has_psu", False),
                                                has_filament_sensor=self.data.get("has_filament_sensor", False))
        self.display_settings = PrinterDisplaySettings(**self.data.get("display", {}))


class MultiPrinterAddedEvent(ServerEvent):
    event_type = "add_connection"

    def on_event(self):
        self.printer_id: Optional[int] = self.data.get("pid")
        self.unique_id: Optional[str] = self.data.get("unique_id", "")
        self.status: bool = self.data.get("status", False)
        self.reason: Optional[str] = self.data.get("reason", None)


class MultiPrinterRemovedEvent(ServerEvent):
    event_type = "remove_connection"

    def on_event(self):
        self.printer_id: Optional[int] = self.data.get("pid")
        self.unique_id: Optional[str] = self.data.get("unique_id", "")
        self.deleted: bool = self.data.get("deleted", False)

        # Emulated websocket status codes.
        self.code = self.data.get("code", None)
        self.reason = self.data.get("reason", None)
