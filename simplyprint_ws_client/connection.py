import json
import requests

from tornado.websocket import WebSocketClientConnection, WebSocketClosedError, websocket_connect
from logging import Logger

from simplyprint_ws_client.const import REACHABLE_URL, WEBSOCKET_URL

from .event import *

from typing import (
    Optional, 
    Dict, 
    Any, 
)

class Connection:
    def __init__(self, logger: Logger) -> None:
        self.ws: Optional[WebSocketClientConnection] = None

        self.api_version: str = "0.1"
        self.reconnect_token: Optional[str] = None

        self.log_connect: bool = True
        self.logger: Logger = logger

    def is_connected(self) -> bool:
        return self.ws is not None

    def get_url(self, id: str, token: str) -> str:
        return f"{WEBSOCKET_URL}/{self.api_version}/p/{id}/{token}"

    async def connect(self, id: str, token: str) -> None:
        url = self.get_url(id, token)

        if self.reconnect_token is not None:
            url = f"{url}/{self.reconnect_token}"

        if self.log_connect:
            self.logger.info(f"Connecting to {url}")

        try:
            requests.get(REACHABLE_URL, timeout=5.0)
        except Exception:
            return

        self.ws = await websocket_connect(url, connect_timeout=5.0)

    def _log_disconnect(self) -> None:
        if self.ws is None:
            return

        reason = self.ws.close_reason
        code = self.ws.close_code

        msg = (
            f"SimplyPrint Disconnected - Code: {code} Reason: {reason}"
        ) 

        self.logger.info(msg)

    async def send_message(self, message: str) -> None:
        if self.ws is None:
            raise Exception("not connected")

        try:
            fut = self.ws.write_message(message);
        except WebSocketClosedError:
            self._log_disconnect()

            self.ws = None
            return

        await fut

    
    async def read_message(self) -> Optional[str]:
        if self.ws is None:
            raise Exception("not connected")

        message = await self.ws.read_message()

        if message is None: 
            self._log_disconnect()

            # remove websocket
            self.ws = None
            return None

        if message is bytes:
            raise Exception("message is bytes, expected str")

        return str(message)

    async def read_event(self) -> Optional[Event]:
        message = await self.read_message()

        if message is None:
            return None

        try:
            packet: Dict[str, Any] = json.loads(message)
        except json.JSONDecodeError:
            self.logger.debug(f"Invalid message, not JSON: {message}")
            return None

        event: str = packet.get("type", "")
        data: Dict[str, Any] = packet.get("data", {})

        if event == "demand":
            demand = data.get("demand", "UNDEFINED")
            
            if demand == "pause": return PauseEvent()
            elif demand == "resume": return ResumeEvent()
            elif demand == "cancel": return CancelEvent()
            elif demand == "terminal": return TerminalEvent(data)
            elif demand == "gcode": return GcodeEvent(data)
            elif demand == "test_webcam": return WebcamTestEvent()
            elif demand == "webcam_snapshot": return WebcamSnapshotEvent(data)
            elif demand == "file": return FileEvent(data)
            elif demand == "start_print": return StartPrintEvent()
            elif demand == "connect_printer": return ConnectPrinterEvent()
            elif demand == "disconnect_printer": return DisconnectPrinterEvent()
            elif demand == "system_restart": return SystemRestartEvent()
            elif demand == "system_shutdown": return SystemShutdownEvent()
            elif demand == "api_restart": return ApiRestartEvent()
            elif demand == "api_shutdown": return ApiShutdownEvent()
            elif demand == "update": return UpdateEvent()
            elif demand == "plugin_install": return PluginInstallEvent()
            elif demand == "plugin_uninstall": return PluginUninstallEvent()
            elif demand == "webcam_settings_updated": return WebcamSettingsEvent(data)
            elif demand == "stream_on": return StreamOnEvent(data)
            elif demand == "stream_off": return StreamOffEvent()
            elif demand == "set_printer_profile": return SetPrinterProfileEvent(data)
            elif demand == "get_gcode_script_backups": return GetGcodeScriptBackupsEvent(data)
            elif demand == "has_gcode_changes": return HasGcodeChangesEvent(data)
            elif demand == "psu_off": return PsuControlEvent(False)
            elif demand == "psu_on": return PsuControlEvent(True)
            elif demand == "psu_keepalive": return PsuControlEvent(True)
            elif demand == "disable_websocket": return DisableWebsocketEvent(data)
            else:
                # Return what ever
                self.logger.debug(f"Unknown demand: {demand} data: {data}")
                return None
        elif event == "error": return ErrorEvent(data)
        elif event == "new_token": return NewTokenEvent(data)
        elif event == "connected": return ConnectEvent(data)
        elif event == "pause": return PauseEvent()
        elif event == "complete_setup": return SetupCompleteEvent(data)
        elif event == "interval_change": return IntervalChangeEvent(data)
        elif event == "pong": return PongEvent()
        elif event == "stream_received": return StreamReceivedEvent()
        elif event == "printer_settings": return PrinterSettingsEvent(data)
        else:
            self.logger.debug(f"Unknown event: {event} data: {data}")
            return None