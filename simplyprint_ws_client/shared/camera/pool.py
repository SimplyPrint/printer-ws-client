import functools
import logging
import multiprocessing
import os
import sys
import threading
import time
from concurrent.futures.thread import ThreadPoolExecutor
from typing import final, List, Dict, Tuple, Optional, Type

from yarl import URL

from .base import BaseCameraProtocol, FrameT
from .commands import Request, CreateCamera, Response, PollCamera, \
    StartCamera, StopCamera, DeleteCamera, ReceivedFrame
from .controller import CameraController
from .handle import CameraHandle
from ..utils.stoppable import ProcessStoppable, StoppableProcess
from ..utils.synchronized import Synchronized


@final
class CameraWorkerProcess(StoppableProcess, Synchronized):
    """Entrypoint of camera worker process"""

    # Shared
    count: multiprocessing.Value
    command_queue: multiprocessing.Queue
    response_queue: multiprocessing.Queue

    # External (pool)
    thread: Optional[threading.Thread] = None

    # Local (process)
    instances: Dict[int, CameraController]

    def __init__(self, **kwargs):
        StoppableProcess.__init__(self, **kwargs)
        self.count = multiprocessing.Value("i", 0)
        self.command_queue = multiprocessing.Queue()
        self.response_queue = multiprocessing.Queue()

    def on_request(self, req: Request):
        try:
            # Create new camera instance.
            if isinstance(req, CreateCamera):
                with self:
                    self.instances[req.id] = CameraController(
                        functools.partial(self._send_frame, req.id),
                        protocol=req.protocol,
                        pause_timeout=req.pause_timeout,
                    )
                    self.count.value += 1

                    return

            # Execute command on camera instance.
            with self:
                instance = self.instances.get(req.id)

            if not instance:
                logging.debug("Instance not found %s", req.id)
                return

            with instance:
                if isinstance(req, PollCamera):
                    instance.poll()
                elif isinstance(req, StartCamera):
                    instance.start()
                elif isinstance(req, StopCamera):
                    instance.stop()
                elif isinstance(req, DeleteCamera):
                    with self:
                        self.count.value -= 1
                        _ = self.instances.pop(req.id, None)
                else:
                    logging.debug("Unknown command %s", req)
        except Exception as e:
            logging.debug("Error", exc_info=e)

    def _send_frame(self, camera_id: int, frame: Optional[FrameT]):
        res = ReceivedFrame(camera_id, time.time(), frame)
        self.response_queue.put(res)
        logging.debug("Sent frame to %s with size %s", camera_id, len(frame) if frame is not None else 0)

    def run(self):
        try:
            self._run()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logging.error("Error", exc_info=e)

    def _run(self):
        Synchronized.__init__(self)
        self.instances = {}

        logging.basicConfig(
            level=logging.DEBUG if os.environ.get("SIMPLYPRINT_DEBUG_CAMERA", False) else logging.INFO,
            format="%(asctime)s [%(process)d] %(message)s", datefmt="%H:%M:%S",
            handlers=[logging.StreamHandler(stream=sys.stdout)]
        )

        with ThreadPoolExecutor(thread_name_prefix="CameraWorkerProcess") as tp:
            while not self.is_stopped():
                msg: Optional[Request] = self.command_queue.get()

                if msg is None:
                    break

                logging.debug(f"Received command {msg}")

                tp.submit(self.on_request, msg)

        logging.info("Exiting")

    def stop(self):
        super().stop()
        self.command_queue.put(None)
        self.response_queue.put(None)


# How many instances do we allow per process
_INSTANCES_PER_PROCESS = 10


@final
class CameraPool(ProcessStoppable, Synchronized):
    processes: List[CameraWorkerProcess]
    protocols: List[Type[BaseCameraProtocol]]
    allocations: Dict[int, Tuple[int, CameraHandle]]

    __cur_idx: int = 0

    def __init__(self, pool_size=0, **kwargs):
        ProcessStoppable.__init__(self, **kwargs)
        Synchronized.__init__(self)

        self.processes = []
        self.protocols = []
        self.allocations = {}

        self.pool_size = pool_size or multiprocessing.cpu_count()

    def _create_worker_process(self):
        return CameraWorkerProcess(daemon=True, parent_stoppable=self)

    def _consume_responses(self, process: CameraWorkerProcess):
        while not self.is_stopped():
            msg: Optional[Response] = process.response_queue.get()

            if msg is None:
                break

            self.on_response(msg)

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

                # Remove allocation
                for uuid, (idx, _) in list(self.allocations.items()):
                    if idx != i:
                        continue

                    self.allocations.pop(uuid, None)

                process.stop()

    def _start_process(self, process: CameraWorkerProcess):
        with self:
            if process.is_alive() or process.is_stopped():
                return

            process.start()

            process.thread = threading.Thread(
                target=self._consume_responses,
                args=(process,),
                daemon=True,
            )
            process.thread.start()

    def _next_process_idx(self):
        with self:
            pool_size = self._pool_size()

            idx = self.__cur_idx

            if idx >= pool_size:
                idx = 0

            cur_process = self.processes[idx]

            # Keep allocating to the same process until it reaches the limit
            if cur_process.count.value < _INSTANCES_PER_PROCESS:
                return idx

            self.__cur_idx = (self.__cur_idx + 1) % pool_size
            return idx

    def submit_request(self, req: Request):
        if req.id not in self.allocations:
            return

        process_idx, _ = self.allocations[req.id]

        if process_idx is None:
            return

        process = self.processes[process_idx]

        if process is None:
            return

        process.command_queue.put(req)

        self._start_process(process)

    def on_response(self, res: Response):
        if res.id not in self.allocations:
            return

        _, handle = self.allocations[res.id]

        if handle is None:
            return

        handle.on_response(res)

    def create(self, uri: URL, **kwargs) -> CameraHandle:
        # Find matching (valid) protocol
        protocol = None

        for protocol_cls in self.protocols:
            if protocol_cls.is_async():
                raise NotImplementedError("Async protocols are not supported")

            if protocol_cls.test(uri):
                protocol = protocol_cls(uri)
                break

        # No protocol found (error)
        if protocol is None:
            raise ValueError("No protocol found for URI")

        # Allocate camera handle
        with self:
            next_id = max(self.allocations.keys(), default=0) + 1

        handle = CameraHandle(self, next_id)

        self.allocations[next_id] = self._next_process_idx(), handle
        self.submit_request(CreateCamera(next_id, protocol, **kwargs))

        return handle

    def stop(self):
        super().stop()
        self.pool_size = 0
