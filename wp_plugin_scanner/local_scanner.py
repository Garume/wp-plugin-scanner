import os
from pathlib import Path
from typing import List, Tuple

from .config import UPLOAD_PATTERN

TARGET_EXTS = (".php", ".js", ".html", ".twig")

def scan_local_plugin(plugin_dir: Path) -> List[Tuple[str, int, str]]:
    """指定ディレクトリ以下のファイルをスキャンして、該当パターンと行番号を返す。"""
    matches = []

    for root, _, files in os.walk(plugin_dir):
        for fname in files:
            if not fname.lower().endswith(TARGET_EXTS):
                continue
            file_path = Path(root) / fname
            try:
                with open(file_path, "rb") as f:
                    for i, line in enumerate(f, start=1):
                        if UPLOAD_PATTERN.search(line):
                            try:
                                line_text = line.decode("utf-8", errors="replace").strip()
                            except Exception:
                                line_text = "<decoding error>"
                            matches.append((str(file_path), i, line_text))
            except Exception as e:
                print(f"[!] Error reading {file_path}: {e}")
    return matches
