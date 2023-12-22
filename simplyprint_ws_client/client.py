import asyncio
import time
from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar

from .config import Config
from .const import SUPPORTED_SIMPLYPRINT_VERSION
from .events import demands as Demands
from .events import server_events as Events
from .events.client_events import ClientEvent
from .events.event_bus import Event, EventBus
from .helpers.intervals import IntervalTypes
from .helpers.physical_machine import PhysicalMachine
from .helpers.sentry import Sentry
from .state.printer import PrinterState


class ClientConfigurationException(Exception):
    ...

class ClientEventBus(EventBus[Event]):
    """ 
    Eventbus for events from SimplyPrint to the client. (ServerEvents / DemandEvents)

    Also for the client to send events to SimplyPrint. (ClientEvents)
    """
    ...

class ClientConfigChangedEvent(Event):
    ...

TConfig = TypeVar("TConfig", bound=Config)

class Client(ABC, Generic[TConfig]):
    """
    Generic client class that handles and brokers information between the server and the client.

    Not nessaicarily a printer, but a client that can be connected to the server.
    But in some cases also an actual physical device.
    """

    config: TConfig
    printer: PrinterState

    # Usually injected by multiplexer
    sentry: Optional[Sentry]
    physical_machine: Optional[PhysicalMachine]

    event_bus: ClientEventBus

    def __init__(self, config: TConfig):
        self.config = config
        self.printer = PrinterState()

        self.event_bus = ClientEventBus()

        # Recover handles from the class
        for name in dir(self):
            attr = getattr(self, name)
            if hasattr(attr, "_event"):
                event_cls = attr._event
                self.event_bus.on(event_cls, attr, attr._pre)

    async def send_event(self, event: ClientEvent):
        """
        Wrapper method to send an client event to the server.
        """

        await self.event_bus.emit(event)

    async def consume_state(self):
        """
        Consumes the state of a client to produce client events
        which are dispatched to the bus.
        """

        for event in self.printer._build_events(self.config.id):
            await self.send_event(event)

    @abstractmethod
    async def tick(self):
        """ 
        Define a continuous task that will be called every "tick"
        this is variable and made to optimize certain performance
        when running a lot of clients at once.

        In here you can manipulate, progress or otherwise change
        the state of the printer to control it.

        Optionally can you also send your own events from inside
        the printer context, but you can always interact with the
        send event method externally.
        """
        ...


class DefaultClient(Client[TConfig]):
    """
    Client with default event handling.
    """

    def __init__(self, config: TConfig):
        super().__init__(config)

        self.physical_machine = PhysicalMachine()
        
        self.printer.observe(self._on_display_message,
                             "current_display_message")

        for k, v in self.physical_machine.get_info().items():
            self.printer.info.set_trait(k, v)

        self.printer.info.sp_version = SUPPORTED_SIMPLYPRINT_VERSION

    def set_info(self, name, version = "0.0.1"):
        self.set_api_info(name, version)
        self.set_ui_info(name, version)

    def set_api_info(self, api: str, api_version: str):
        self.printer.info.api = api
        self.printer.info.api_version = api_version

    def set_ui_info(self, ui: str, ui_version: str):
        self.printer.info.ui = ui
        self.printer.info.ui_version = ui_version

    def setup_sentry(self, sentry_dsn: str, development: bool = False):
        if not self.printer.info.api or not self.printer.info.api_version:
            raise ClientConfigurationException(
                "You need to set the api and api_version before you can setup sentry")

        self.sentry = Sentry()
        self.sentry.client = self.printer.info.api
        self.sentry.client_version = self.printer.info.api_version
        self.sentry.sentry_dsn = sentry_dsn
        self.sentry.development = development

    def _on_display_message(self, change):
        message = change['new']

        if self.printer.display_settings.branding:
            if len(message) > 7:
                message = f"[SP] {message}"
            else:
                message = f"[SimplyPrint] {message}"

        # Pass on to gcode handling (Printer firmware)
        gcode_event = Demands.GcodeEvent(name="demand", demand=Demands.GcodeEvent.demand, data={
            "list": ["M117 {}".format(message.replace('\n', ''))]
        })

        asyncio.create_task(self.event_bus.emit(gcode_event))

    @Demands.SystemRestartEvent.on
    async def on_system_restart(self, event: Demands.SystemRestartEvent):
        self.physical_machine.restart()

    @Demands.SystemShutdownEvent.on
    async def on_system_shutdown(self, event: Demands.SystemShutdownEvent):
        self.physical_machine.shutdown()

    @Events.ErrorEvent.before
    async def on_error(self, event: Events.ErrorEvent):
        ...

    @Events.NewTokenEvent.before
    async def before_new_token(self, event: Events.NewTokenEvent):
        self.config.token = event.token
        await self.event_bus.emit(ClientConfigChangedEvent())

    @Events.ConnectEvent.before
    async def before_connect(self, event: Events.ConnectEvent):
        self.printer.name = event.printer_name
        self.printer.in_setup = event.in_setup
        self.printer.connected = True
        self.printer.intervals.update(event.intervals)

        self.reconnect_token = event.reconnect_token

        if self.printer.in_setup:
            self.printer.current_display_message = "In setup with Code: " + event.short_id

    @Events.SetupCompleteEvent.before
    async def before_setup_complete(self, event: Events.SetupCompleteEvent):
        self.config.id = event.printer_id
        self.printer.in_setup = False
        self.printer.current_display_message = "Setup complete"
        await self.event_bus.emit(ClientConfigChangedEvent())

    @Events.IntervalChangeEvent.before
    async def before_interval_change(self, event: Events.IntervalChangeEvent):
        self.printer.intervals.update(event.intervals)

    @Events.PongEvent.before
    async def before_pong(self, event: Events.PongEvent):
        self.printer.ping_pong.pong = time.time()

    @Events.StreamReceivedEvent.before
    async def before_stream_received(self, event: Events.StreamReceivedEvent):
        # TODO
        ...

    @Events.PrinterSettingsEvent.before
    async def before_printer_settings(self, event: Events.PrinterSettingsEvent):
        self.printer.settings.has_psu = event.printer_settings.has_psu
        self.printer.settings.has_filament_sensor = event.printer_settings.has_filament_sensor
        self.printer.display_settings.branding = event.display_settings.branding
        self.printer.display_settings.enabled = event.display_settings.enabled
        self.printer.display_settings.while_printing_type = event.display_settings.while_printing_type
        self.printer.display_settings.show_status = event.display_settings.show_status

    @Demands.PauseEvent.before
    async def before_pause(self, event: Demands.PauseEvent):
        ...

    @Demands.WebcamSnapshotEvent.before
    async def before_webcam_snapshot(self, event: Demands.WebcamSnapshotEvent):
        if event.timer is not None:
            self.printer.intervals.set(IntervalTypes.WEBCAM.value, event.timer)