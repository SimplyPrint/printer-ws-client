import requests
import time
import pathlib
import tempfile
import logging
import re
import shutil

from tornado.escape import url_escape, url_unescape
from typing import Optional, Tuple, List
from .event import PrinterEvent

def escape_query_string(qs: str) -> str:
    parts = qs.split("&")
    escaped: List[str] = []
    for p in parts:
        item = p.split("=", 1)
        key = url_escape(item[0])
        if len(item) == 2:
            escaped.append(f"{key}={url_escape(item[1])}")
        else:
            escaped.append(key)
    return "&".join(escaped)

class FileHandler:
    def __init__(self, client, local_path: str):
        self.client = client
        self.logger = logging.getLogger("simplyprint.FileHandler")
        self.local_path: str = local_path

    def escape_url(self, url: str) -> str:
        # escape the url
        match = re.match(r"(https?://[^/?#]+)([^?#]+)?(\?[^#]+)?(#.+)?", url)
        if match is not None:
            uri, path, qs, fragment = match.groups()
            if path is not None:
                uri += "/".join([url_escape(p, plus=False)
                                 for p in path.split("/")])
            if qs is not None:
                uri += "?" + escape_query_string(qs[1:])
            if fragment is not None:
                uri += "#" + url_escape(fragment[1:], plus=False)
            url = uri
        return url

    def parse_content_disposition(self, content_disposition: str) -> str:
        fnr = r"filename[^;\n=]*=(['\"])?(utf-8\'\')?([^\n;]*)(?(1)\1|)"
        matches: List[Tuple[str, str, str]] = re.findall(fnr, content_disposition)
        is_utf8 = False
        filename: str = ""
        for (_, encoding, fname) in matches:
            if encoding.startswith("utf-8"):
                # Prefer the utf8 filename if included
                filename = url_unescape(
                    fname, encoding="utf-8", plus=False)
                is_utf8 = True
                break
            filename = fname
        self.logger.debug(
            "Content-Disposition header received: filename = "
            f"{filename}, utf8: {is_utf8}"
        )
        return filename

    def update_progress(self, progress: int):
        self.client.send(
            PrinterEvent.FILE_PROGRESS,
            {
                "state": "downloading",
                "percent": progress,
            }
        )

    def download_complete(self):
        self.client.send(
            PrinterEvent.FILE_PROGRESS,
            {
                "state": "ready",
            }
        )

    def download_error(self, error: str):
        self.client.send(
            PrinterEvent.FILE_PROGRESS,
            {
                "state": "error",
                "message": error,
            }
        )

    def download(self, url: str) -> Optional[str]:
        tmp_file = f"sp-{time.monotonic_ns()}.gcode"
        tmp_file_path = pathlib.Path(tempfile.gettempdir()).joinpath(tmp_file)
        size: int = 0
        downloaded: int = 0
        last_pct: float = 0.0
        url_path = url.rsplit("/", 1)
        file_name: str = tmp_file 

        if len(url_path) == 2 and "." in url_path[-1]:
            file_name = url_path[-1]

        url = self.escape_url(url)

        try:
            with requests.get(url, allow_redirects=True, stream=True, timeout=3600.0) as response:
                response.raise_for_status()
                size = int(response.headers.get("content-length", 0))

                update_pct = max(1.0, size // 100)

                if "content-disposition" in response.headers:
                    cd = response.headers["content-disposition"]
                    file_name = self.parse_content_disposition(cd)

                with tmp_file_path.open("wb") as f:
                    for chunk in response.iter_content(8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            pct = downloaded / size * 100

                            if pct > last_pct + update_pct or last_pct == 0.0 or pct >= 100.0:
                                last_pct = pct
                                self.update_progress(round(pct))
                
        except Exception:
            self.logger.exception("Error downloading file")
            self.download_error("Network Error")
            return 

        if not pathlib.Path(self.local_path).exists():
            pathlib.Path(self.local_path).mkdir(parents=True)

        shutil.move(tmp_file_path, f"{self.local_path}/{file_name}")
        self.download_complete()
        return file_name
