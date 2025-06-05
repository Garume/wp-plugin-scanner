import os
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Sequence, Dict, List

from .config import UPLOAD_PATTERN


@dataclass
class ScanRule:
    """Represents a single scan rule defined by a regex pattern."""

    name: str
    pattern: re.Pattern[bytes]


class RuleScanner:
    """Scanner that evaluates a set of regex based rules."""

    def __init__(self, rules: Sequence[ScanRule]):
        self.rules: List[ScanRule] = list(rules)
        self.exts = (".php", ".js", ".html", ".twig")

    def scan(self, plugin_path: Path) -> Dict[str, bool]:
        results: Dict[str, bool] = {r.name: False for r in self.rules}
        for root, _d, files in os.walk(plugin_path):
            for fname in files:
                if not fname.lower().endswith(self.exts):
                    continue
                try:
                    with open(Path(root) / fname, "rb") as f:
                        data = f.read()
                        for rule in self.rules:
                            if not results[rule.name] and rule.pattern.search(data):
                                results[rule.name] = True
                except Exception:
                    continue
        return results

    def gather_files(self, plugin_path: Path) -> list[Path]:
        collected: list[Path] = []
        for root, _d, files in os.walk(plugin_path):
            for fname in files:
                if fname.lower().endswith(self.exts):
                    collected.append(Path(root) / fname)
        return collected


class UploadScanner(RuleScanner):
    """Backward compatible scanner for upload functionality."""

    def __init__(self, pattern: re.Pattern[bytes] = UPLOAD_PATTERN):
        super().__init__([ScanRule("upload", pattern)])

    def has_upload_feature(self, plugin_path: Path) -> bool:
        return self.scan(plugin_path).get("upload", False)
