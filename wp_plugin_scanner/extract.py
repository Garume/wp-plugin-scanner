import os
import re
import pandas as pd
from pathlib import Path

from wp_plugin_scanner.config import SAVE_SOURCE, CSV_PATH, UPLOAD_PATTERN


# 出力フォルダ
SCAN_OUTPUT_DIR = Path("scanned_plugins")
SCAN_OUTPUT_DIR.mkdir(exist_ok=True)

TARGET_EXTS = (".php", ".js", ".html", ".twig")


def scan_file_for_uploads(file_path: Path) -> list[tuple[int, str]]:
    """1ファイル内で該当パターンを含む行番号と内容を取得"""
    matches = []
    try:
        with open(file_path, "rb") as f:
            for lineno, line in enumerate(f, 1):
                if UPLOAD_PATTERN.search(line):
                    try:
                        line_text = line.decode("utf-8", errors="replace").strip()
                    except Exception:
                        line_text = "<decode error>"
                    matches.append((lineno, line_text))
    except Exception as e:
        print(f"[!] Error reading {file_path}: {e}")
    return matches


def scan_plugin_dir(slug: str, plugin_dir: Path):
    """1つのプラグインディレクトリをスキャンし、結果を CSV に保存"""
    results = []
    for root, _, files in os.walk(plugin_dir):
        for fname in files:
            if not fname.lower().endswith(TARGET_EXTS):
                continue
            file_path = Path(root) / fname
            for lineno, content in scan_file_for_uploads(file_path):
                results.append((str(file_path.relative_to(plugin_dir)), lineno, content))

    if results:
        df = pd.DataFrame(results, columns=["file", "line", "matched_text"])
        df.to_csv(SCAN_OUTPUT_DIR / f"{slug}.csv", index=False)


def scan_all_true_plugins():
    """upload=True のプラグインだけを再スキャンし、CSV 出力する"""
    if not CSV_PATH.exists():
        print("[!] plugin_upload_audit.csv not found")
        return

    try:
        df = pd.read_csv(CSV_PATH)
    except Exception as e:
        print(f"[!] Failed to read CSV: {e}")
        return

    true_slugs = df[df["upload"] == "True"]["slug"].astype(str)

    for slug in true_slugs:
        plugin_dir = SAVE_SOURCE / slug
        if plugin_dir.exists():
            print(f"[i] Scanning {slug}")
            scan_plugin_dir(slug, plugin_dir)
        else:
            print(f"[!] Directory not found for {slug}: {plugin_dir}")
