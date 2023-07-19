import platform
import os
import re
import psutil
import subprocess
import socket
import netifaces

from typing import Optional

class Machine:
    """
    Provides hardware and platform information, abstractly.
    """

    def get_cpu(self):
        temperature: Optional[float] = None
        temperatures = psutil.sensors_temperatures()
        
        # Find the first temperature sensor that is not None
        # Priority is given in reverse order
        temperature_keys = {
            "coretemp", 
            "cpu-thermal",
            "cpu_thermal", 
            "soc_thermal"
        } & set(temperatures.keys())
        
        temperature = temperatures[temperature_keys.pop()][0].current if len(temperature_keys) > 0 and temperatures[temperature_keys.pop()][0].current is not None else 0

        return {
            "usage": round(psutil.cpu_percent()),
            "temp": round(temperature),
            "memory": round(psutil.virtual_memory().percent),
            "flags": 0,
        }

    def get_machine_data(self):
        return {
            "python_version": self.python_version(),
            "machine": self.machine(),
            "os": self.os(),
            "is_ethernet": self.is_ethernet(),
            "ssid": self.ssid(),
            "hostname": self.hostname(),
            "local_ip": self.local_ip(),
            "core_count": self.core_count(),
            "total_memory": self.total_memory(),
        }

    def python_version(self) -> str:
        """
        Returns the Python version.
        """
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
    
    def restart(self):
        if self.os() == "Linux":
            os.system("sudo reboot")
        elif self.os() == "Windows":
            os.system("shutdown /r /t 1")

    def shutdown(self):
        if self.os() == "Linux":
            os.system("sudo shutdown now")
        elif self.os() == "Windows":
            os.system("shutdown /s /t 1")