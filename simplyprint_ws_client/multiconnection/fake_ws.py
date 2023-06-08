import json
from asyncio import Queue
from tornado.websocket import WebSocketClientConnection


class FakeWS(WebSocketClientConnection):
    """ 
    Support read and write operations and syncronize with tornado client.
    """

    _read_queues = {}
    # Only need one queue to read all messages
    _write_queue = Queue()

    def __init__(self, pid: int):
        self.pid = pid
        FakeWS._read_queues[pid] = Queue()
        self._closed = False

    async def write_message(self, message):
        FakeWS._write_queue.put_nowait([self.pid, message])

    async def read_message(self):
        return await FakeWS._read_queues[self.pid].get() 

    @staticmethod
    def send_message_to(pid: int, message):
        FakeWS._read_queues[pid].put_nowait(message)

    @staticmethod
    def dump_write_queue():
        while not FakeWS._write_queue.empty():
           yield FakeWS._write_queue.get_nowait()