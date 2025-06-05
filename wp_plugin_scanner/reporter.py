import threading
from pathlib import Path
import pandas as pd

from .config import EXCEL_PATH
from .models import PluginResult

class ExcelReporter:
    def __init__(self, path: Path = EXCEL_PATH):
        self.path = path
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if self.path.exists():
            self.df = pd.read_excel(self.path)
        else:
            self.df = pd.DataFrame(columns=["slug", "upload", "timestamp"])

    def already_done(self, slug: str) -> bool:
        return slug in set(self.df["slug"].astype(str))

    def add_result(self, result: PluginResult):
        with self._lock:
            self.df.loc[len(self.df)] = [result.slug, result.status, result.readable_time]
            self.df.to_excel(self.path, index=False)
