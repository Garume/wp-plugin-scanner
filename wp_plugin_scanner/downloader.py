from __future__ import annotations
import io
import tempfile
import zipfile
import pandas as pd
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter, Retry

from .config import (
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    BACKOFF_FACTOR,
    ZIP_URL_TMPL,
    CSV_PATH,
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

def download_true_plugin_zips(destination: Path):
    """upload=True のプラグインZIPを destination にダウンロード"""
    if not CSV_PATH.exists():
        print("[!] plugin_upload_audit.csv が存在しません")
        return

    try:
        df = pd.read_csv(CSV_PATH)
    except Exception as e:
        print(f"[!] CSV読み込み失敗: {e}")
        return

    true_slugs = df[df["upload"] == "True"]["slug"].astype(str)
    destination.mkdir(parents=True, exist_ok=True)

    for slug in true_slugs:
        zip_url = ZIP_URL_TMPL.format(slug=slug)
        out_path = destination / f"{slug}.zip"
        if out_path.exists():
            print(f"[=] 既に存在: {out_path}")
            continue
        try:
            print(f"[↓] ダウンロード中: {slug}")
            res = requests.get(zip_url, timeout=30)
            res.raise_for_status()
            out_path.write_bytes(res.content)
            print(f"[✔] 保存完了: {out_path}")
        except Exception as e:
            print(f"[!] ダウンロード失敗: {slug}: {e}")
