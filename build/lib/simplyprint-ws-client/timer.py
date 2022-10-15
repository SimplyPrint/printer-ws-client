import asyncio

from datetime import datetime, timedelta
from typing import Dict

class Intervals:
    def __init__(self, data: Dict[str, int] = {}):
        self.job: float = data.get("job", 5000.0) / 1000.0
        self.temperatures: float = data.get("temps", 5000.0) / 1000.0
        self.target_temperatures: float = data.get("temps_target", 2500.0) / 1000.0
        self.cpu: float = data.get("cpu", 30000.0) / 1000.0
        self.reconnect: float = data.get("reconnect", 1000.0) / 1000.0
        self.ai: float = data.get("ai", 60000.0) / 1000.0
        self.ready: float = data.get("ready_message", 60000.0) / 1000.0
        self.ping: float = data.get("ping", 20000.0) / 1000.0

        self.job_last_update: datetime = datetime.now() - timedelta(seconds=self.job)
        self.temperatures_last_update: datetime = datetime.now() - timedelta(seconds=self.temperatures)
        self.target_temperatures_last_update: datetime = datetime.now() - timedelta(seconds=self.target_temperatures)
        self.cpu_last_update: datetime = datetime.now() - timedelta(seconds=self.cpu)
        self.reconnect_last_update: datetime = datetime.now() - timedelta(seconds=self.reconnect)
        self.ai_last_update: datetime = datetime.now() - timedelta(seconds=self.ai)
        self.ready_last_update: datetime = datetime.now() - timedelta(seconds=self.ready)
        self.ping_last_update: datetime = datetime.now() - timedelta(seconds=self.ping)

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
        next_update = self.job_last_update + timedelta(seconds=self.job)
        if datetime.now() > next_update:
            self.job_last_update = datetime.now()
            return

        remaining = (next_update - datetime.now()).total_seconds()

        if remaining > 0.0:
            await asyncio.sleep(remaining) 

        self.job_last_update = datetime.now()

    async def sleep_until_temperatures(self):
        next_update = self.temperatures_last_update + timedelta(seconds=self.temperatures)
        if datetime.now() > next_update:
            self.temperatures_last_update = datetime.now()
            return

        remaining = (next_update - datetime.now()).total_seconds()

        if remaining > 0.0:
            await asyncio.sleep(remaining) 

        self.temperatures_last_update = datetime.now()

    async def sleep_until_target_temperatures(self):
        next_update = self.target_temperatures_last_update + timedelta(seconds=self.target_temperatures)
        if datetime.now() > next_update:
            self.target_temperatures_last_update = datetime.now()
            return

        remaining = (next_update - datetime.now()).total_seconds()

        if remaining > 0.0:
            await asyncio.sleep(remaining) 

        self.target_temperatures_last_update = datetime.now()

    async def sleep_until_cpu(self):
        next_update = self.cpu_last_update + timedelta(seconds=self.cpu)
        if datetime.now() > next_update:
            self.cpu_last_update = datetime.now()
            return

        remaining = (next_update - datetime.now()).total_seconds()

        if remaining > 0.0:
            await asyncio.sleep(remaining) 

        self.cpu_last_update = datetime.now()

    async def sleep_until_reconnect(self):
        next_update = self.reconnect_last_update + timedelta(seconds=self.reconnect)
        if datetime.now() > next_update:
            self.reconnect_last_update = datetime.now()
            return

        remaining = (next_update - datetime.now()).total_seconds()

        if remaining > 0.0:
            await asyncio.sleep(remaining) 

        self.reconnect_last_update = datetime.now()

    async def sleep_until_ai(self):
        next_update = self.ai_last_update + timedelta(seconds=self.ai)
        if datetime.now() > next_update:
            self.ai_last_update = datetime.now()
            return

        remaining = (next_update - datetime.now()).total_seconds()

        if remaining > 0.0:
            await asyncio.sleep(remaining) 

        self.ai_last_update = datetime.now()

    async def sleep_until_ready(self):
        next_update = self.ready_last_update + timedelta(seconds=self.ready)
        if datetime.now() > next_update:
            self.ready_last_update = datetime.now()
            return

        remaining = (next_update - datetime.now()).total_seconds()

        if remaining > 0.0:
            await asyncio.sleep(remaining) 

        self.ready_last_update = datetime.now()

    async def sleep_until_ping(self):
        next_update = self.ping_last_update + timedelta(seconds=self.ping)
        if datetime.now() > next_update:
            self.ping_last_update = datetime.now()
            return

        remaining = (next_update - datetime.now()).total_seconds()

        if remaining > 0.0:
            await asyncio.sleep(remaining) 

        self.ping_last_update = datetime.now()
