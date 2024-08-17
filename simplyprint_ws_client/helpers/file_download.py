import asyncio
from pathlib import Path
from typing import Callable, Optional, AsyncIterable

import aiohttp

from ..client.client import Client
from ..client.state import PrinterFileProgressState, FileProgressState


class FileDownload:
    state: "PrinterFileProgressState"
    client: Client
    timeout: aiohttp.ClientTimeout

    def __init__(self, client: Client, timeout: Optional[aiohttp.ClientTimeout] = None) -> None:
        self.client = client
        self.state = client.printer.file_progress

        self.timeout = timeout or aiohttp.ClientTimeout(
            # default is total = 5 minutes which is too short for large files
            total=None,  # Total number of seconds for the whole request
            connect=5,  # Maximal number of seconds for acquiring a connection from pool
            sock_connect=10,  # Maximal number of seconds for connecting to a peer for a new connection
            sock_read=60 * 30  # seconds for consecutive reads - 30 minutes as we do not control the block size
        )

    async def download(self, url, clamp_progress: Optional[Callable] = None) -> AsyncIterable:
        """ 
        Download a file with file progress.
        """

        # Chunk the download so we can get progress
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    self.state.state = FileProgressState.ERROR
                    self.state.message = f"Failed to download file: {resp.status}"
                    return

                self.state.state = FileProgressState.STARTED

                size = int(resp.headers.get('content-length', 0))
                downloaded = 0

                self.state.state = FileProgressState.DOWNLOADING

                # Download chunk by chunk
                async for chunk in resp.content.iter_any():
                    yield chunk

                    downloaded += len(chunk)

                    total_percentage = int((downloaded / size) * 100)

                    self.state.percent = clamp_progress(total_percentage) if clamp_progress else total_percentage

                    # Ensure we send events to SimplyPrint
                    asyncio.run_coroutine_threadsafe(self.client.consume_state(), self.client.event_loop)

    async def download_as_bytes(self, url, clamp_progress: Optional[Callable] = None) -> bytes:
        # Bytes object to store the downloaded data
        data = b''

        async for chunk in self.download(url, clamp_progress):
            data += chunk

        # Return the data as a BytesIO object
        return data

    async def download_as_file(self, url, dest: Path, clamp_progress: Optional[Callable] = None) -> Path:
        """
        Download a file with file progress and save it to a file.
        """

        # Save the data to a file
        with open(dest, 'wb') as f:
            async for chunk in self.download(url, clamp_progress):
                f.write(chunk)

        return dest
