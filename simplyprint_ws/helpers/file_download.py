import asyncio
import aiohttp

from io import BytesIO
from ..printer import PrinterFileProgressState, FileProgressState

class FileDownload:
    loop: asyncio.AbstractEventLoop
    state: PrinterFileProgressState

    def __init__(self, state: PrinterFileProgressState, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self.state = state

    async def download_as_bytes(self, url) -> bytes:
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
                    self.state.percent = round((downloaded / size) * 100, 2)
        
        # Return the data as a BytesIO object
        self.state.state = FileProgressState.READY
        return data
