import os
from pathlib import Path
import re
from typing import Tuple, List

from .config import UPLOAD_PATTERN
from .models import UploadMatch

class UploadScanner:
    def __init__(self, pattern: re.Pattern[bytes] = UPLOAD_PATTERN):
        self.pattern = pattern
        self.exts = (".php", ".js", ".html", ".twig")

    def has_upload_feature(self, plugin_path: Path) -> bool:
        """アップロード機能があるかどうかを判定（後方互換性のため）"""
        matches, _ = self.scan_for_upload_features(plugin_path)
        return len(matches) > 0

    def scan_for_upload_features(self, plugin_path: Path) -> Tuple[List[UploadMatch], int]:
        """
        アップロード機能をスキャンし、詳細情報を返す
        
        Returns:
            Tuple[List[UploadMatch], int]: (検出されたマッチ, スキャンしたファイル数)
        """
        matches = []
        files_scanned = 0
        
        for root, _d, files in os.walk(plugin_path):
            for fname in files:
                if not fname.lower().endswith(self.exts):
                    continue
                
                file_path = Path(root) / fname
                files_scanned += 1
                
                try:
                    # テキストファイルとして読み込んでライン毎に検索
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        
                    for line_num, line in enumerate(lines, 1):
                        line_bytes = line.encode('utf-8', errors='ignore')
                        match = self.pattern.search(line_bytes)
                        if match:
                            # ファイルパスを相対パスに変換
                            relative_path = str(file_path.relative_to(plugin_path))
                            match_obj = UploadMatch(
                                file_path=relative_path,
                                line_number=line_num,
                                line_content=line.strip(),
                                matched_pattern=match.group(0).decode('utf-8', errors='ignore')
                            )
                            matches.append(match_obj)
                            
                except Exception:
                    # ファイル読み込みエラーの場合、バイナリで読み込んで検索（従来の方法）
                    try:
                        with open(file_path, "rb") as f:
                            content = f.read()
                            if self.pattern.search(content):
                                relative_path = str(file_path.relative_to(plugin_path))
                                match_obj = UploadMatch(
                                    file_path=relative_path,
                                    line_number=0,  # ライン番号不明
                                    line_content="[Binary file or encoding error]",
                                    matched_pattern="[Pattern found in binary]"
                                )
                                matches.append(match_obj)
                    except Exception:
                        continue
                        
        return matches, files_scanned

    def gather_files(self, plugin_path: Path) -> list[Path]:
        collected: list[Path] = []
        for root, _d, files in os.walk(plugin_path):
            for fname in files:
                if fname.lower().endswith(self.exts):
                    collected.append(Path(root) / fname)
        return collected
