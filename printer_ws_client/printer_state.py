from typing import (
    Optional, 
    List, 
    Dict, 
    Any, 
    Union, 
    Tuple, 
    Callable, 
    Awaitable,
    cast,
)

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

class PrinterState:
    def __init__(self): 
        self.connected: bool = False
        self.layer: Optional[int] = None

