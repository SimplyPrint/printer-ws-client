from abc import ABC, abstractmethod
import asyncio
import time
from typing import Callable, Coroutine, Dict, List, Optional, Type

from .helpers.intervals import IntervalTypes

from .config import Config, ConfigManager
from .events.client_events import ClientEvent
from .events import events as Events
from .events import demands as Demands

from .helpers.physical_machine import PhysicalMachine
from .helpers.sentry import Sentry
from .state.printer import PrinterState


class Client(ABC):
    """
    Generic client class that handles and brokers information between the server and the client.

    Not nessaicarily a printer, but a client that can be connected to the server.
    But in some cases also an actual physical device.
    """

    config: Config
    config_manager: ConfigManager # Injected by multiplexer
    printer: PrinterState

    # Usually injected by multiplexer
    sentry: Optional[Sentry]
    physical_machine: Optional[PhysicalMachine]

    handles: Dict[Events.ServerEvent, List[Callable[[Events.ServerEvent], Coroutine]]]
    send_event: Callable[[ClientEvent], None] # Injected by multiplexer

    def __init__(self, config: Config):
        self.config = config
        self.printer = PrinterState()

        self.handles = {}
        
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

    async def on_event(self, event: Events.ServerEvent):
        handle, before = self.handles.get(type(event), (None, None))

        if before is not None:
            event = await before(event)

        if handle is not None:
            await handle(event)
    
    @abstractmethod
    async def tick(self):
        """ 
        Define a continuous task that will be called every "tick"
        this is variable and made to optimize certain performance
        when running a lot of clients at once.
        """
        ...
    

class DefaultClient(Client):
    """
    Client with default event handling.
    """

    def __init__(self, config: Config):
        super().__init__(config)
        self.physical_machine = PhysicalMachine()
        self.printer.observe(self._on_display_message, "current_display_message")

    def _on_display_message(self, change):
        message = change['new']

        if self.printer.display_settings.branding:
            if len(message) > 7:
                message = f"[SP] {message}"
            else:
                message = f"[SimplyPrint] {message}"
        
        # Pass on to gcode handling (Printer firmware)
        gcode_event = Demands.GcodeEvent(name=Demands.GcodeEvent.name, demand=Demands.GcodeEvent.demand, data={
            "list": ["M117 {}".format(message.replace('\n', ''))]
        })

        asyncio.create_task(self.on_event(gcode_event))

    @Demands.SystemRestartEvent.on
    async def on_system_restart(self, event: Demands.SystemRestartEvent):
        self.physical_machine.restart()

    @Demands.SystemShutdownEvent.on
    async def on_system_shutdown(self, event: Demands.SystemShutdownEvent):
        self.physical_machine.shutdown()

    @Events.ErrorEvent.before
    async def on_error(self, event: Events.ErrorEvent) -> Events.ErrorEvent:
        return event
    
    @Events.NewTokenEvent.before
    async def before_new_token(self, event: Events.NewTokenEvent) -> Events.NewTokenEvent:
        self.config.token = event.token
        self.config_manager.flush(self.config)
        return event
    
    @Events.ConnectEvent.before
    async def before_connect(self, event: Events.ConnectEvent) -> Events.ConnectEvent:
        self.printer.name = event.printer_name
        self.printer.in_setup = event.in_setup
        self.printer.connected = True
        self.printer.intervals.update(event.intervals)
        
        self.reconnect_token = event.reconnect_token

        if self.printer.in_setup:
            self.printer.current_display_message = "In setup with Code: " + event.short_id

        return event
    
    @Events.SetupCompleteEvent.before
    async def before_setup_complete(self, event: Events.SetupCompleteEvent) -> Events.SetupCompleteEvent:
        self.config.id = event.printer_id
        self.printer.in_setup = False
        self.printer.current_display_message = "Setup complete"
        self.config_manager.flush(self.config)
        return event
    
    @Events.IntervalChangeEvent.before
    async def before_interval_change(self, event: Events.IntervalChangeEvent) -> Events.IntervalChangeEvent:
        self.printer.intervals.update(event.intervals)
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
    
    @Demands.WebcamSnapshotEvent.before
    async def before_webcam_snapshot(self, event: Demands.WebcamSnapshotEvent) -> Demands.WebcamSnapshotEvent:
        if event.timer is not None:
            self.printer.intervals.set(IntervalTypes.WEBCAM.value, event.timer)
        
        return event