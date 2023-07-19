import time
import asyncio

from typing import Coroutine, Type, Dict, Callable, List

from simplyprint_ws.config import Config
from .sentry import Sentry
from .machine import Machine
from ..config import Config, ConfigManager
from ..events import Events, Demands, ClientEvent
from ..printer import PrinterState
from ..helpers.ratelimit import Intervals

class Client:
    """
    Generic client class that handles and brokers information between the server and the client.

    Not nessaicarily a printer, but a client that can be connected to the server.
    But in some cases also an actual physical device.
    """

    config: Config
    printer: PrinterState
    sentry: Sentry
    machine: Machine
    intervals: Intervals
    handles: Dict[Events.ServerEvent, List[Callable[[Events.ServerEvent], Coroutine]]] = {}
    send_event: Callable[[ClientEvent], Coroutine] # Injected by multiplexer

    def __init__(self, config: Config):
        self.config = config
        self.printer = PrinterState()
        self.sentry = Sentry()
        self.machine = Machine()
        self.intervals = Intervals()
        
        # Recover handles from the class
        for name in dir(self):
            attr = getattr(self, name)
            if hasattr(attr, "_event"):
                event = attr._event
                self._register_handle(event, attr)

    def _register_handle(self, event: Type[Events.ServerEvent], handle: Callable[[Events.ServerEvent], None]):
        if event in self.handles and self.handles[event][handle._pre] is not None:
            raise Exception(f"handle for {event} has already been registered")
        
        if not event in self.handles:
            self.handles[event] = [None, None]
    
        self.handles[event][handle._pre] = handle

    async def handle_event(self, event: Events.ServerEvent):
        print(f"Handling event {repr(event)}")

        handle, before = self.handles.get(type(event), (None, None))

        if before is not None:
            event = await before(event)

        print(event.data)

        if handle is not None:
            await handle(event)

class DefaultClient(Client):
    """
    Client with default event handling.
    """

    def __init__(self, config: Config):
        super().__init__(config)
        self.printer.observe(self._on_display_message, "current_display_message")

    def _on_display_message(self, change):
        message = change['new']

        if self.printer.display_settings.branding:
            if len(message) > 7:
                message = f"[SP] {message}"
            else:
                message = f"[SimplyPrint] {message}"
        
        gcode_event = Demands.GcodeEvent(name=Demands.GcodeEvent.name, demand=Demands.GcodeEvent.demand, data={
            "list": ["M117 {}".format(message.replace('\n', ''))]
        })

        asyncio.create_task(self.handle_event(gcode_event))
        
        # Pass on to gcode handling (Printer firmware)
        print(f"DISPLAY: {message}")

    @Demands.SystemRestartEvent.on
    async def on_system_restart(self, event: Demands.SystemRestartEvent):
        self.machine.restart()

    @Demands.SystemShutdownEvent.on
    async def on_system_shutdown(self, event: Demands.SystemShutdownEvent):
        self.machine.shutdown()

    @Events.ErrorEvent.before
    async def on_error(self, event: Events.ErrorEvent) -> Events.ErrorEvent:
        # Logging
        return event
    
    @Events.NewTokenEvent.before
    async def before_new_token(self, event: Events.NewTokenEvent) -> Events.NewTokenEvent:
        self.config.token = event.token
        ConfigManager.persist_config(self.config)
        return event
    
    @Events.ConnectEvent.before
    async def before_connect(self, event: Events.ConnectEvent) -> Events.ConnectEvent:
        self.intervals.update(event.intervals)
        self.printer.connected = True
        self.printer.name = event.printer_name
        self.reconnect_token = event.reconnect_token
        self.printer.in_setup = event.in_setup

        if self.printer.in_setup:
            self.printer.current_display_message = "In setup with Code: " + event.short_id

        return event
    
    @Events.SetupCompleteEvent.before
    async def before_setup_complete(self, event: Events.SetupCompleteEvent) -> Events.SetupCompleteEvent:
        self.config.id = event.printer_id
        self.printer.in_setup = False
        ConfigManager.persist_config(self.config)
        self.printer.current_display_message = "Setup complete"
        return event
    
    @Events.IntervalChangeEvent.before
    async def before_interval_change(self, event: Events.IntervalChangeEvent) -> Events.IntervalChangeEvent:
        self.intervals.update(event.intervals)
        return event
    
    @Events.PongEvent.before
    async def before_pong(self, event: Events.PongEvent) -> Events.PongEvent:
        self.printer.ping_pong.pong = time.time()
        return event
    
    @Events.StreamReceivedEvent.before
    async def before_stream_received(self, event: Events.StreamReceivedEvent) -> Events.StreamReceivedEvent:
        # TODO
        return event
    
    @Events.PrinterSettingsEvent.before
    async def before_printer_settings(self, event: Events.PrinterSettingsEvent) -> Events.PrinterSettingsEvent:
        self.printer.settings.has_psu = event.printer_settings.has_psu
        self.printer.settings.has_filament_sensor = event.printer_settings.has_filament_sensor
        self.printer.display_settings.branding = event.display_settings.branding
        self.printer.display_settings.enabled = event.display_settings.enabled
        self.printer.display_settings.while_printing_type = event.display_settings.while_printing_type
        self.printer.display_settings.show_status = event.display_settings.show_status
        return event
    
    @Demands.PauseEvent.before
    async def before_pause(self, event: Demands.PauseEvent) -> Demands.PauseEvent:
        return event