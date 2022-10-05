import asyncio

from datetime import datetime
from typing import Dict

class Intervals:
    def __init__(self, data: Dict[str, int] = {}):
        self.job: float = data.get("job", 5000.0) / 1000.0
        self.temperatures: float = data.get("temps", 5000.0) / 1000.0
        self.target_temperatures: float = data.get("temps_target", 2500.0) / 1000.0
        self.cpu: float = data.get("cpu", 30000.0) / 1000.0
        self.reconnect: float = data.get("reconnect", 0.0) / 1000.0
        self.ai: float = data.get("ai", 60000.0) / 1000.0
        self.ready: float = data.get("ready_message", 60000.0) / 1000.0
        self.ping: float = data.get("ping", 20000.0) / 1000.0

        self.job_last_update: datetime = datetime.now()
        self.temperatures_last_update: datetime = datetime.now()
        self.cpu_last_update: datetime = datetime.now()
        self.reconnect_last_update: datetime = datetime.now()
        self.ai_last_update: datetime = datetime.now()
        self.ready_last_update: datetime = datetime.now()
        self.ping_last_update: datetime = datetime.now()

        self.job_updating: bool = False
        self.temperatures_updating: bool = False
        self.cpu_updating: bool = False
        self.reconnect_updating: bool = False
        self.ai_updating: bool = False
        self.ready_updating: bool = False
        self.ping_updating: bool = False

    def update(self, other: "Intervals"):
        self.job = other.job
        self.temperatures = other.temperatures
        self.target_temperatures = other.target_temperatures
        self.cpu = other.cpu
        self.reconnect = other.reconnect
        self.ai = other.ai
        self.ready = other.ready
        self.ping = other.ping

    async def sleep_until_job(self):
        remaining = (self.job_last_update - datetime.now()).total_seconds() + self.job

        if remaining > 0.0:
            self.job_updating = True
            await asyncio.sleep(remaining)
            self.job_updating = False

        self.job_last_update = datetime.now()

    async def sleep_until_temperatures(self):
        remaining = (self.temperatures_last_update - datetime.now()).total_seconds() + self.temperatures

        if remaining > 0.0:
            self.temperatures_updating = True
            await asyncio.sleep(remaining)
            self.temperatures_updating = False

        self.temperatures_last_update = datetime.now()

    async def sleep_until_target_temperatures(self):
        remaining = (self.temperatures_last_update - datetime.now()).total_seconds() + self.target_temperatures

        if remaining > 0.0:
            self.temperatures_updating = True
            await asyncio.sleep(remaining)
            self.temperatures_updating = False

        self.temperatures_last_update = datetime.now()

    async def sleep_until_cpu(self):
        remaining = (self.cpu_last_update - datetime.now()).total_seconds() + self.cpu

        if remaining > 0.0:
            self.cpu_updating = True
            await asyncio.sleep(remaining)
            self.cpu_updating = False

        self.cpu_last_update = datetime.now()

    async def sleep_until_reconnect(self):
        remaining = (self.reconnect_last_update - datetime.now()).total_seconds() + self.reconnect

        if remaining > 0.0:
            self.reconnect_updating = True
            await asyncio.sleep(remaining)
            self.reconnect_updating = False

        self.reconnect_last_update = datetime.now()

    async def sleep_until_ai(self):
        remaining = (self.ai_last_update - datetime.now()).total_seconds() + self.ai

        if remaining > 0.0:
            self.ai_updating = True
            await asyncio.sleep(remaining)
            self.ai_updating = False

        self.ai_last_update = datetime.now()

    async def sleep_until_ready(self):
        remaining = (self.ready_last_update - datetime.now()).total_seconds() + self.ready

        if remaining > 0.0:
            self.ready_updating = True
            await asyncio.sleep(remaining)
            self.ready_updating = False

        self.ready_last_update = datetime.now()

    async def sleep_until_ping(self):
        remaining = (self.ping_last_update - datetime.now()).total_seconds() + self.ping

        if remaining > 0.0:
            self.ping_updating = True
            await asyncio.sleep(remaining)
            self.ping_updating = False

        self.ping_last_update = datetime.now()

