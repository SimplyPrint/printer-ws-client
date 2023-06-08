import platform
import os
import re
import psutil
import subprocess
import socket
import netifaces

from typing import Optional

class ClientInfo:
    ui: Optional[str] = None
    ui_version: Optional[str] = None
    api: Optional[str] = None
    api_version: Optional[str] = None
    client: Optional[str] = None
    client_version: Optional[str] = None
    sp_version: Optional[str] = "4.0.0"
    sentry_dsn: Optional[str] = None
    development: bool = False

    def python_version(self) -> str:
        return platform.python_version() 

    def __get_cpu_model_linux(self) -> Optional[str]:
        info_path = "/proc/cpuinfo"

        try:
            with open(info_path, "r") as f:
                data = f.read()

            cpu_items = [
                item.strip() for item in data.split("\n\n") if item.strip()
            ]

            match = re.search(r"Model\s+:\s+(.+)", cpu_items[-1])
            if not match is None:
                return match.group(1)

            for item in cpu_items:
                match = re.search(r"model name\s+:\s+(.+)", item)

                if not match is None:
                    return match.group(1).strip()
        except Exception:
            pass

    def __get_cpu_model_windows(self) -> Optional[str]:
        try:
            name = subprocess.check_output(["wmic", "cpu", "get", "name"]).decode("utf-8").strip()

            if name.startswith("Name"):
                name = name[4:].strip()
            
            return name
        except Exception:
            return None

    def machine(self) -> str:
        if self.os() == "Linux":
            model = self.__get_cpu_model_linux()

            if not model is None:
                return model

        if self.os() == "Windows":
            model = self.__get_cpu_model_windows()

            if not model is None:
                return model
    
        return platform.machine()

    def os(self) -> str:
        return platform.system()

    def is_ethernet(self) -> bool:
        try:
            return netifaces.gateways()["default"][netifaces.AF_INET][1].startswith("eth")
        except Exception:
            return False

    def __ssid_linux(self) -> Optional[str]:
        try:
            return subprocess.check_output(["iwgetid", "-r"]).decode("utf-8").strip()
        except Exception:
            return None

    def __ssid_windows(self) -> Optional[str]:
        try:
            output = subprocess.check_output(["netsh", "wlan", "show", "interfaces"]).decode("utf-8").strip()

            for line in output.split("\n"):
                line = line.strip()

                if line.startswith("SSID"):
                    return line[4:].strip()[1:].strip()

            return None
        except Exception:
            return None

    def ssid(self) -> Optional[str]:
        if self.os() == "Linux":
            return self.__ssid_linux()

        if self.os() == "Windows":
            return self.__ssid_windows()

        return None

    def hostname(self) -> str:
        return socket.gethostname()

    def local_ip(self) -> Optional[str]:
        try:
            interface = netifaces.gateways()["default"][netifaces.AF_INET][1]

            return netifaces.ifaddresses(interface)[netifaces.AF_INET][0]["addr"]
        except Exception:
            return None

    def core_count(self) -> Optional[int]:
        return os.cpu_count()

    def total_memory(self) -> int:
        return psutil.virtual_memory().total
        
