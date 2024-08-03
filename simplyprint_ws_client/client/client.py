import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar

from simplyprint_ws_client.helpers.physical_machine import PhysicalMachine
from .config import PrinterConfig
from .logging import *
from .protocol import Demands, Events
from .protocol.client_events import ClientEvent, PingEvent, StateChangeEvent, MachineDataEvent
from .state.printer import PrinterState
from ..events.event import Event
from ..events.event_bus import EventBus
from ..helpers.intervals import IntervalTypes, Intervals
from ..utils.event_loop_provider import EventLoopProvider
from ..utils.traceability import traceable


class ClientConfigurationException(Exception):
    ...


# Eventbus for events from SimplyPrint to the client. (ServerEvents / DemandEvents)
# Also for the client to send events to SimplyPrint. (ClientEvents)
ClientEventBus = EventBus[Event]


class ClientConfigChangedEvent(Event):
    ...


TConfig = TypeVar("TConfig", bound=PrinterConfig)


class Client(ABC, EventLoopProvider[asyncio.AbstractEventLoop], Generic[TConfig]):
    """
    Generic client class that handles and brokers information between the server and the client.

    Not necessarily a printer, but a client that can be connected to the server.
    But in some cases also an actual physical device.
    """

    config: TConfig
    intervals: Intervals
    printer: PrinterState
    event_bus: ClientEventBus

    logger: logging.Logger

    _connected: bool = False
    _client_lock: asyncio.Lock

    def __init__(
            self,
            config: TConfig,
            event_loop_provider: Optional[EventLoopProvider[asyncio.AbstractEventLoop]] = None,
    ):
        super().__init__(provider=event_loop_provider)

        self.config = config
        self.intervals = Intervals()
        self.printer = PrinterState()
        self.event_bus = ClientEventBus(event_loop_provider=event_loop_provider)

        self.logger = logging.getLogger(ClientName.from_client(self))

        self._client_lock = asyncio.Lock()

        # Recover handles from the class
        # TODO: Generalize this under the event system.
        for name in dir(self):
            try:
                attr = getattr(self, name)
                event_cls = getattr(attr, "_event")
                self.event_bus.on(event_type=event_cls, listener=attr, priority=getattr(attr, "_pre"))
            except (AttributeError, RuntimeError):
                pass

    async def __aenter__(self):
        """ Acquire a client to perform order sensitive operations."""
        await self._client_lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """ Release the client lock. """
        self._client_lock.release()

    @property
    def connected(self) -> bool:
        """
        Check if the client is connected to the server.
        """
        return self._connected

    @connected.setter
    @traceable(with_args=True, with_stack=True, record_count=5)
    def connected(self, value: bool):
        self._connected = value
        self.logger.debug(f"Client {self.config.id} changed connected now: {self._connected=}")

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

    def set_info(self, name, version="0.0.1"):
        """ Set same info for all fields, both for UI / API and the client. """
        self.set_api_info(name, version)
        self.set_ui_info(name, version)
        self.printer.info.sp_version = version

    def set_api_info(self, api: str, api_version: str):
        self.printer.info.api = api
        self.printer.info.api_version = api_version

    def set_ui_info(self, ui: str, ui_version: str):
        self.printer.info.ui = ui
        self.printer.info.ui_version = ui_version

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


class DefaultClient(Client[TConfig], ABC):
    """
    Client with default event handling, logging and more extra features.
    """

    reconnect_token: Optional[str] = None
    requested_snapshots: int = 0

    def __init__(self, config: TConfig, **kwargs):
        super().__init__(config, **kwargs)

    async def send_ping(self):
        if not self.intervals.is_ready(IntervalTypes.PING):
            return

        self.printer.latency.ping = time.time()
        await self.send_event(PingEvent())

    @Events.ErrorEvent.before
    async def on_error(self, event: Events.ErrorEvent):
        ...

    @Events.NewTokenEvent.before
    async def before_new_token(self, event: Events.NewTokenEvent):
        self.config.token = event.token
        self.config.short_id = event.short_id
        self.config.in_setup = bool(event.short_id)

        await self.event_bus.emit(ClientConfigChangedEvent)

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

        await self.event_bus.emit(ClientConfigChangedEvent)

    @Events.SetupCompleteEvent.before
    async def before_setup_complete(self, event: Events.SetupCompleteEvent):
        # Mark certain events to always be sent to the server
        self.printer.mark_event_as_dirty(StateChangeEvent)
        self.printer.mark_event_as_dirty(MachineDataEvent)

        self.config.id = event.printer_id
        self.config.in_setup = False
        self.printer.current_display_message = "Setup complete"
        await self.event_bus.emit(ClientConfigChangedEvent)

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
        self.requested_snapshots += 1

        if event.timer is not None:
            self.intervals.set(IntervalTypes.WEBCAM.value, event.timer)


class PhysicalClient(DefaultClient[TConfig], ABC):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set information about the physical machine
        for k, v in PhysicalMachine.get_info().items():
            self.printer.info.set_trait(k, v)

    @Demands.SystemRestartEvent.on
    async def on_system_restart(self, event: Demands.SystemRestartEvent):
        PhysicalMachine.restart()

    @Demands.SystemShutdownEvent.on
    async def on_system_shutdown(self, event: Demands.SystemShutdownEvent):
        PhysicalMachine.shutdown()
