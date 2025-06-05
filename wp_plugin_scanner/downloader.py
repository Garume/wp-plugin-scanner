from __future__ import annotations
import io
import tempfile
import zipfile
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter, Retry

from .config import (
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    BACKOFF_FACTOR,
    ZIP_URL_TMPL,
)

class IPluginDownloader:
    def download(self, slug: str) -> Path:
        raise NotImplementedError

class RequestsDownloader(IPluginDownloader):
    def __init__(self, retries: int = DEFAULT_RETRIES, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()
        retry_conf = Retry(
            total=retries,
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry_conf))

    def download(self, slug: str) -> Path:
        url = ZIP_URL_TMPL.format(slug=slug)
        try:
            res = self.session.get(url, timeout=self.timeout)
            res.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"Download failed for {slug}: {e}") from e
        tmp_root = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            zf.extractall(tmp_root)
            top = zf.namelist()[0].split("/")[0]
        return tmp_root / top
