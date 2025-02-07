import logging
import logging
import multiprocessing
import threading
import time
from concurrent.futures.thread import ThreadPoolExecutor
from typing import final, List, Optional, Type, Dict, cast, Tuple, Callable
from uuid import uuid4

from .base import BaseCameraProtocol, CameraProtocolPollingMode, FrameT, TCameraState, TCameraConfig, \
    CameraProtocolInvalidState
from .commands import Request, CreateCamera, Response, ConfigureCamera, PollCamera, \
    StartCamera, StopCamera, DeleteCamera, ReceivedFrame
from .handle import CameraHandle
from ..utils.stoppable import ProcessStoppable, StoppableProcess, SyncStoppable, StoppableThread
from ..utils.synchronized import Synchronized


@final
class CameraController(SyncStoppable, Synchronized):
    """A collection of camera protocol and its state"""

    state: Optional[TCameraState] = None
    config: TCameraConfig
    protocol: Type[BaseCameraProtocol]
    polling_mode: CameraProtocolPollingMode
    pause_timeout: Optional[int]

    _frame_cb: Callable[[FrameT], None]
    _pause_timer: Optional[threading.Timer] = None
    _main_thread: Optional[threading.Thread] = None

    def __init__(
            self,
            frame_cb: Callable[[FrameT], None],
            config: TCameraConfig,
            protocol: Type[BaseCameraProtocol],
            pause_timeout: Optional[int] = None,
    ):
        SyncStoppable.__init__(self)
        Synchronized.__init__(self)

        self.config = config
        self.protocol = protocol
        self.polling_mode = protocol.polling_mode()
        self.pause_timeout = pause_timeout
        self._frame_cb = frame_cb

    def configure(self, config: TCameraConfig):
        self.config = config
        # TODO: Refresh?

    def poll(self):
        if self.polling_mode == CameraProtocolPollingMode.ON_DEMAND:
            self._read_frame()
            return

        self._refresh_timer()
        self.start()

    def start(self):
        assert self.polling_mode == CameraProtocolPollingMode.CONTINUOUS

        if self._main_thread is not None and self._main_thread.is_alive():
            return

        self.clear()
        self._refresh_timer()
        self._main_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._main_thread.start()

    def stop(self):
        super().stop()

        if self.state:
            self.protocol.disconnect(self.state)
            self.state = None

        if self._main_thread:
            self._main_thread.join()
            self._main_thread = None

        if self._pause_timer:
            self._pause_timer.cancel()
            self._pause_timer = None

    def _refresh_timer(self):
        assert self.polling_mode == CameraProtocolPollingMode.CONTINUOUS

        if self._pause_timer:
            self._pause_timer.cancel()
            self._pause_timer = None

        if self.pause_timeout:
            self._pause_timer = threading.Timer(self.pause_timeout, self.pause)
            self._pause_timer.start()

    def _read_frame(self):
        # TODO: Use test somewhere / return result?

        if not self.state:
            self.state = self.protocol.connect(self.config)

        try:
            frame = self.protocol.read(self.state)
            self._frame_cb(frame)
        except CameraProtocolInvalidState:
            self.state = None
            return

    def _read_loop(self):
        while not self.is_stopped():
            self._read_frame()


@final
class CameraWorkerProcess(StoppableProcess, Synchronized):
    """Entrypoint of camera worker process"""

    # Shared
    command_queue: multiprocessing.Queue
    response_queue: multiprocessing.Queue

    # Local
    instances: Dict[str, CameraController]

    def __init__(self, *args, **kwargs):
        StoppableProcess.__init__(self, **kwargs)
        self.command_queue = multiprocessing.Queue()
        self.response_queue = multiprocessing.Queue()

    def on_request(self, uuid: str, cmd: Request):
        try:
            # Create new camera instance.
            if isinstance(cmd, CreateCamera):
                with self:
                    self.instances[uuid] = CameraController(
                        lambda frame: self.response_queue.put((uuid, ReceivedFrame(time.monotonic(), frame))),
                        config=cmd.config,
                        protocol=cmd.protocol,
                        pause_timeout=None,
                    )

                    return

            # Execute command on camera instance.
            with self:
                instance = self.instances.get(uuid)

            if not instance:
                logging.debug("Instance not found %s", uuid)
                return

            with instance:
                if isinstance(cmd, ConfigureCamera):
                    instance.configure(cmd.config)
                elif isinstance(cmd, PollCamera):
                    instance.poll()
                elif isinstance(cmd, StartCamera):
                    instance.start()
                elif isinstance(cmd, StopCamera):
                    instance.stop()
                elif isinstance(cmd, DeleteCamera):
                    with self:
                        self.instances.pop(uuid)
                else:
                    logging.debug("Unknown command %s", cmd)
        except Exception as e:
            logging.debug("Error", exc_info=e)

    def run(self):
        Synchronized.__init__(self)
        self.instances = {}

        # TODO: Fix logging

        with ThreadPoolExecutor(thread_name_prefix="CameraWorkerProcess") as tp:
            while not self.is_stopped():
                msg = self.command_queue.get()

                if msg is None:
                    break

                if not isinstance(msg, tuple) or len(msg) != 2:
                    logging.debug("Invalid message %s", msg)
                    continue

                uuid, cmd = cast(str, msg[0]), cast(Request, msg[1])
                logging.debug(f"Received command {cmd} for {uuid}")
                tp.submit(self.on_request, uuid, cmd)

        logging.info("Exiting")


class ResponseListener(StoppableThread):
    """Local thread for pool per process. (rewrite as function)"""
    pool: 'CameraPool'
    process: CameraWorkerProcess

    def __init__(self, pool: 'CameraPool', process: CameraWorkerProcess, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool = pool
        self.process = process

    def run(self):
        while not self.is_stopped():
            msg = self.process.response_queue.get()

            if msg is None:
                break

            if not isinstance(msg, tuple) or len(msg) != 2:
                logging.debug("Invalid response: %s", msg)
                continue

            uuid, msg = cast(str, msg[0]), cast(Response, msg[1])

            self.pool.on_response(uuid, msg)


@final
class CameraPool(ProcessStoppable, Synchronized):
    processes: List[CameraWorkerProcess]
    allocations: Dict[str, Tuple[int, CameraHandle]]

    __cur_idx: int = 0

    def __init__(self, *args, pool_size=0, **kwargs):
        ProcessStoppable.__init__(self, **kwargs)
        Synchronized.__init__(self)

        self.processes = [self._create_worker_process() for _ in
                          range(pool_size or (multiprocessing.cpu_count() - 1))]
        self.allocations = {}

    def _create_worker_process(self):
        return CameraWorkerProcess(daemon=True, parent_stoppable=self)

    def _pool_size(self):
        return len(self.processes)

    @property
    def pool_size(self):
        with self:
            return self._pool_size()

    @pool_size.setter
    def pool_size(self, value):
        with self:
            prev = self._pool_size()

            # No change
            if prev == value:
                return

            # Increase pool size (spawn happens deferred)
            if prev < value:
                self.processes.extend([self._create_worker_process() for _ in range(value - prev)])
                return

            # Reduce pool size (terminate processes)
            self.processes, excess = self.processes[:value], self.processes[value:]

            for i, process in enumerate(excess):
                i = value + i

                if process is None:
                    continue

                # Remove allocation
                for uuid, (idx, _) in list(self.allocations.items()):
                    if idx != i:
                        continue

                    self.allocations.pop(uuid, None)

                process.stop()
                process.command_queue.put(None)
                process.response_queue.put(None)

    def spawn_processes(self):
        with self:
            for i, process in enumerate(self.processes):
                # If process is alive, skip
                if process is not None and process.is_alive():
                    continue

                if process is None:
                    self.processes[i] = process = self._create_worker_process()

                local_thread = ResponseListener(
                    pool=self,
                    process=process,
                    daemon=True,
                )

                process.start()
                local_thread.start()

    def _next_process_idx(self):
        with self:
            pool_size = self._pool_size()

            idx = self.__cur_idx

            if idx >= pool_size:
                idx = 0

            self.__cur_idx = (self.__cur_idx + 1) % pool_size
            return idx

    def submit_request(self, uuid: str, req: Request):
        if uuid not in self.allocations:
            return

        process_idx, _ = self.allocations[uuid]

        if process_idx is None:
            return

        process = self.processes[process_idx]

        if process is None:
            return

        process.command_queue.put((uuid, req))

    def on_response(self, uuid: str, res: Response):
        if uuid not in self.allocations:
            return

        _, handle = self.allocations[uuid]

        if handle is None:
            return

        handle.on_response(res)

    def create(self, protocol: Type[BaseCameraProtocol], config=None) -> CameraHandle:
        # TODO: Perhaps generate key based on protocol + config?
        uuid = uuid4().hex
        proxy = CameraHandle(self, uuid, protocol)
        self.allocations[uuid] = self._next_process_idx(), proxy

        proxy.submit_request(CreateCamera(
            protocol=protocol,
            config=config,
        ))

        return proxy

    def stop(self):
        super().stop()
        self.pool_size = 0
