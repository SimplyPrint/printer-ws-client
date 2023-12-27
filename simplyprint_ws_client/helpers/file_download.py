import asyncio
import aiohttp

from typing import Callable, Optional
from ..client import Client
from ..state.printer import PrinterFileProgressState, FileProgressState

class FileDownload:
    loop: asyncio.AbstractEventLoop
    state: "PrinterFileProgressState"
    client: Client

    def __init__(self, client: Client, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self.client = client
        self.state = client.printer.file_progress

    async def download_as_bytes(self, url, clamp_progress: Optional[Callable] = None) -> bytes:
        """ 
        Download a file with file progress.
        """

        # Chunk the download so we can get progress
        async with aiohttp.ClientSession(loop=self.loop) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    self.state.state = FileProgressState.ERROR
                    self.state.message = f"Failed to download file: {resp.status}"
                    return
                
                self.state.state = FileProgressState.STARTED

                size = int(resp.headers.get('content-length', 0))
                downloaded = 0

                # Bytes object to store the downloaded data
                data = b''

                # Download chunk by chunk
                async for chunk in resp.content.iter_any():
                    data += chunk
                    downloaded += len(chunk)

                    self.state.state = FileProgressState.DOWNLOADING

                    total_percentage = int((downloaded / size) * 100)
                    
                    self.state.percent = clamp_progress(total_percentage) if clamp_progress else total_percentage
                    
                    # Ensure we send events to SimplyPrint
                    await self.client.consume_state()
        
        # Return the data as a BytesIO object
        return data
