from asyncio import sleep
from datetime import datetime, timedelta
from typing import Dict

class Intervals:
    def __init__(self, data: Dict[str, int] = {}):
        self.job: float = data.get("job", 5000.0) / 1000.0
        self.temperatures: float = data.get("temps", 5000.0) / 1000.0
        self.target_temperatures: float = data.get("temps_target", 2500.0) / 1000.0
        self.cpu: float = data.get("cpu", 30000.0) / 1000.0
        self.reconnect: float = data.get("reconnect", 1000.0) / 1000.0
        self.ready: float = data.get("ready_message", 60000.0) / 1000.0
        self.ping: float = data.get("ping", 20000.0) / 1000.0

        self.job_last_update: datetime = datetime.now() - timedelta(seconds=self.job)
        self.temperatures_last_update: datetime = datetime.now() - timedelta(seconds=self.temperatures)
        self.target_temperatures_last_update: datetime = datetime.now() - timedelta(seconds=self.target_temperatures)
        self.cpu_last_update: datetime = datetime.now() - timedelta(seconds=self.cpu)
        self.reconnect_last_update: datetime = datetime.now() - timedelta(seconds=self.reconnect)
        self.ready_last_update: datetime = datetime.now() - timedelta(seconds=self.ready)
        self.ping_last_update: datetime = datetime.now() - timedelta(seconds=self.ping)

        self.job_updating: bool = False
        self.temperatures_updating: bool = False
        self.cpu_updating: bool = False
        self.reconnect_updating: bool = False
        self.ready_updating: bool = False
        self.ping_updating: bool = False

    def update(self, other: "Intervals"):
        self.job = other.job
        self.temperatures = other.temperatures
        self.target_temperatures = other.target_temperatures
        self.cpu = other.cpu
        self.reconnect = other.reconnect
        self.ready = other.ready
        self.ping = other.ping
