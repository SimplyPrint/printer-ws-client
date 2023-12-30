from typing import Optional
import aiohttp
import base64
from ..const import SimplyPrintUrl, VERSION

class SimplyPrintApi:
    @staticmethod
    async def post_snapshot(id: str, image_data: bytes):

        endpoint = SimplyPrintUrl.current().api_url / "jobs" / "ReceiveSnapshot"
        
        data = {
            "id": id,
            "image": base64.b64encode(image_data).decode("utf-8"),
        }

        headers = {"User-Agent": f"simplyprint-ws-client/{VERSION}"}

        async with aiohttp.ClientSession() as session:
            async with session.post(str(endpoint), json=data, headers=headers, timeout=45) as response:
                if response.status != 200:
                    raise Exception(f"Failed to post snapshot: {await response.text()}")    

    @staticmethod
    async def post_logs(
        printer_id: int,
        token: str,
        main_log_file: Optional[str] = None,
        plugin_log_file: Optional[str] = None,
        serial_log_file: Optional[str] = None    
    ):
        # Request /printers/ReceiveLogs with the token as post data
        # And each of the files as multipart/form-data

        endpoint = SimplyPrintUrl.current().api_url / "printers" / "ReceiveLogs" + ("pid", printer_id)

        data = {
            "token": token,
        }

        headers = {"User-Agent": f"simplyprint-ws-client/{VERSION}"}

        if main_log_file:
            data["main"] = open(main_log_file, "r")

        if plugin_log_file:
            data["plugin_log"] = open(plugin_log_file, "r")

        if serial_log_file:
            data["serial_log"] = open(serial_log_file, "r")

        async with aiohttp.ClientSession() as session:
            async with session.post(str(endpoint), data=data, headers=headers, timeout=45) as response:
                if response.status != 200:
                    raise Exception(f"Failed to post logs: {await response.text()}")
                
                return await response.json()