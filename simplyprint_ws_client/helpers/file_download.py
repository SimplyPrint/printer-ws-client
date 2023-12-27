import asyncio
import aiohttp

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

    async def download_as_bytes(self, url) -> bytes:
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
                    self.state.percent = int(round((downloaded / size) * 100, 2))
                    
                    # Ensure we send events to SimplyPrint
                    await self.client.consume_state()
        
        # Return the data as a BytesIO object
        return data
