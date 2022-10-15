import json
import requests

from tornado.websocket import WebSocketClientConnection, WebSocketClosedError, websocket_connect
from logging import Logger

from .event import *

from typing import (
    Optional, 
    Dict, 
    Any, 
)

REACHABLE_URL: str = "https://testws.simplyprint.io"

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
        return f"wss://testws.simplyprint.io/{self.api_version}/p/{id}/{token}"

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

        if event == "error":
            return ErrorEvent(data)
        if event == "new_token":
            return NewTokenEvent(data)
        if event == "connected":
            return ConnectEvent(data)
        if event == "pause":
            return PauseEvent()
        if event == "complete_setup":
            return SetupCompleteEvent(data)
        if event == "interval_change":
            return IntervalChangeEvent(data)
        if event == "pong":
            return PongEvent()
        if event == "stream_received":
            return StreamReceivedEvent()
        if event == "printer_settings":
            return PrinterSettingsEvent(data)
        if event == "demand":                
            event = data.pop("demand", "UNDEFINED")

            if event == "pause":
                return PauseEvent()
            if event == "resume":
                return ResumeEvent()
            if event == "cancel":
                return CancelEvent()
            if event == "terminal":
                return TerminalEvent(data)
            if event == "gcode":
                return GcodeEvent(data)
            if event == "test_webcam":
                return WebcamTestEvent()
            if event == "webcam_snapshot":
                return WebcamSnapshotEvent(data)
            if event == "file":
                return FileEvent(data)
            if event == "start_print":
                return StartPrintEvent()
            if event == "connect_printer":
                return ConnectPrinterEvent()
            if event == "disconnect_printer":
                return DisconnectPrinterEvent()
            if event == "system_restart":
                return SystemRestartEvent()
            if event == "system_shutdown":
                return SystemShutdownEvent()
            if event == "api_restart":
                return ApiRestartEvent()
            if event == "api_shutdown":
                return ApiShutdownEvent()
            if event == "update":
                return UpdateEvent()
            if event == "plugin_install":
                return PluginInstallEvent()
            if event == "plugin_uninstall":
                return PluginUninstallEvent()
            if event == "webcam_settings_updated":
                return WebcamSettingsEvent(data)
            if event == "stream_on":
                return StreamOnEvent(data)
            if event == "stream_off":
                return StreamOffEvent()
            if event == "set_printer_profile":
                return SetPrinterProfileEvent(data)
            if event == "get_gcode_script_backups":
                return GetGcodeScriptBackupsEvent(data)
            if event == "has_gcode_changes":
                return HasGcodeChangesEvent(data)
            if event == "psu_off":
                return PsuControlEvent(False)
            if event == "psu_on":
                return PsuControlEvent(True)
            if event == "psu_keepalive":
                return PsuControlEvent(True)
            if event == "disable_websocket":
                return DisableWebsocketEvent(data)
            else:
                self.logger.debug(f"Unknown demand: {event}, data: {data}")
                return None
        else: 
            self.logger.debug(f"Unknown event: {event} data: {data}")
            return None
        
