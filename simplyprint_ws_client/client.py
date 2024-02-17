import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar, Callable

from .config import Config
from .const import SUPPORTED_SIMPLYPRINT_VERSION
from .events import demand_events as Demands
from .events import server_events as Events
from .events.client_events import ClientEvent, PingEvent
from .events.event import Event
from .events.event_bus import EventBus
from .helpers.intervals import IntervalTypes, Intervals
from .helpers.physical_machine import PhysicalMachine
from .helpers.sentry import Sentry
from .logging import *
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

    Not necessarily a printer, but a client that can be connected to the server.
    But in some cases also an actual physical device.
    """

    loop: Optional[asyncio.AbstractEventLoop] = None

    config: TConfig
    intervals: Intervals
    printer: PrinterState

    _connected: bool = False

    sentry: Optional[Sentry]
    physical_machine: Optional[PhysicalMachine]

    event_bus: ClientEventBus
    loop_factory: Optional[Callable[[], asyncio.AbstractEventLoop]] = None

    def __init__(self, config: TConfig, loop_factory: Optional[Callable[[], asyncio.AbstractEventLoop]] = None):
        self.config = config
        self.intervals = Intervals()
        self.printer = PrinterState()
        self.event_bus = ClientEventBus(loop_factory=loop_factory)
        self.loop_factory = loop_factory

        # Recover handles from the class
        for name in dir(self):
            if not hasattr(self, name):
                continue

            attr = getattr(self, name)

            if hasattr(attr, "_event"):
                event_cls = attr._event
                self.event_bus.on(event_cls, attr, attr._pre)

    @property
    def connected(self) -> bool:
        """
        Check if the client is connected to the server.
        """
        return self._connected

    @connected.setter
    def connected(self, value: bool):
        self._connected = value

    async def send_event(self, event: ClientEvent):
        """
        Wrapper method to send a client event to the server.
        """

        event.for_client = self.config.unique_id

        await self.event_bus.emit(event)

    async def consume_state(self):
        """
        Consumes the state of a client to produce client events
        which are dispatched to the bus.
        """

        for client_event in self.printer.iter_dirty_events():
            # Push back invalid events, iter is atomic and respects initial last
            if self.config.is_pending() and not client_event.event_type.is_allowed_in_setup():
                self.printer.mark_event_as_dirty(client_event)
                continue

            try:
                await self.send_event(client_event.from_state(self.printer))
            except ValueError:
                # Do not send events that are invalid.
                # TODO Log?
                continue

    def get_loop(self) -> asyncio.AbstractEventLoop:
        """
        Get the event loop for the client.
        """
        if self.loop_factory:
            self.loop = self.loop_factory()

        if not self.loop:
            raise RuntimeError("Loop not initialized")

        return self.loop

    @abstractmethod
    async def init(self):
        """
        Called when the client is initialized.
        """
        ...

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

    @abstractmethod
    async def stop(self):
        """
        Called when the client is stopped.
        """
        ...


class DefaultClient(Client[TConfig]):
    """
    Client with default event handling.
    """

    logger: logging.Logger
    reconnect_token: Optional[str] = None
    requested_snapshots: int = 0

    def __init__(self, config: TConfig, **kwargs):
        super().__init__(config, **kwargs)

        self.logger = logging.getLogger(ClientName.from_client(self))
        self.physical_machine = PhysicalMachine()

        # Default M117 behaviour.
        """
        def _on_display_message(change):
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

            self.get_loop().create_task(self.event_bus.emit(gcode_event))

        self.printer.observe(_on_display_message,
                             "current_display_message")
        """

        # Set information about the physical machine
        for k, v in self.physical_machine.get_info().items():
            self.printer.info.set_trait(k, v)

        self.printer.info.sp_version = SUPPORTED_SIMPLYPRINT_VERSION

    def set_info(self, name, version="0.0.1"):
        self.set_api_info(name, version)
        self.set_ui_info(name, version)

    def set_api_info(self, api: str, api_version: str):
        self.printer.info.api = api
        self.printer.info.api_version = api_version

    def set_ui_info(self, ui: str, ui_version: str):
        self.printer.info.ui = ui
        self.printer.info.ui_version = ui_version

    def setup_sentry(self, sentry_dsn: str, development: bool = True):
        if not self.printer.info.api or not self.printer.info.api_version:
            raise ClientConfigurationException(
                "You need to set the api and api_version before you can setup sentry")

        self.sentry = Sentry()
        self.sentry.client = self.printer.info.api
        self.sentry.client_version = self.printer.info.api_version
        self.sentry.sentry_dsn = sentry_dsn
        self.sentry.development = development

    async def send_ping(self):
        if not self.intervals.is_ready(IntervalTypes.PING):
            return

        self.printer.latency.ping = time.time()
        await self.send_event(PingEvent())

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
        self.connected = True
        self.config.name = event.printer_name
        self.config.in_setup = event.in_setup
        self.config.short_id = event.short_id

        self.intervals.update(event.intervals)

        self.reconnect_token = event.reconnect_token

        if self.config.in_setup:
            self.printer.current_display_message = "In setup with Code: " + event.short_id

        await self.event_bus.emit(ClientConfigChangedEvent())

    @Events.SetupCompleteEvent.before
    async def before_setup_complete(self, event: Events.SetupCompleteEvent):
        self.config.id = event.printer_id
        self.config.in_setup = False
        self.printer.current_display_message = "Setup complete"
        await self.event_bus.emit(ClientConfigChangedEvent())

    @Events.IntervalChangeEvent.before
    async def before_interval_change(self, event: Events.IntervalChangeEvent):
        self.intervals.update(event.intervals)

    @Events.PongEvent.before
    async def before_pong(self, event: Events.PongEvent):
        self.printer.latency.pong = time.time()

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
        self.logger.debug(
            f"Got request to take webcam snapshot {event} and {self.requested_snapshots}")

        self.requested_snapshots += 1

        if event.timer is not None:
            self.intervals.set(IntervalTypes.WEBCAM.value, event.timer)
