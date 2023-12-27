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
