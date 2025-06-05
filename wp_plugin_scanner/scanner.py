import os
from pathlib import Path
import re

from .config import UPLOAD_PATTERN

class UploadScanner:
    def __init__(self, pattern: re.Pattern[bytes] = UPLOAD_PATTERN):
        self.pattern = pattern
        self.exts = (".php", ".js", ".html", ".twig")

    def has_upload_feature(self, plugin_path: Path) -> bool:
        for root, _d, files in os.walk(plugin_path):
            for fname in files:
                if not fname.lower().endswith(self.exts):
                    continue
                try:
                    with open(Path(root) / fname, "rb") as f:
                        if self.pattern.search(f.read()):
                            return True
                except Exception:
                    continue
        return False

    def gather_files(self, plugin_path: Path) -> list[Path]:
        collected: list[Path] = []
        for root, _d, files in os.walk(plugin_path):
            for fname in files:
                if fname.lower().endswith(self.exts):
                    collected.append(Path(root) / fname)
        return collected
