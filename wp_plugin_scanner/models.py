from dataclasses import dataclass, field
import time
from datetime import datetime
from typing import Optional, List

@dataclass
class UploadMatch:
    """アップロード機能の検出結果を保存するクラス"""
    file_path: str
    line_number: int
    line_content: str
    matched_pattern: str

@dataclass
class PluginResult:
    slug: str
    status: str  # "True", "False", "skipped", or "error:..."
    timestamp: float = field(default_factory=time.time)
    upload_matches: List[UploadMatch] = field(default_factory=list)  # 検出された詳細情報
    files_scanned: int = 0  # スキャンしたファイル数

    @property
    def readable_time(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))

@dataclass
class PluginDetails:
    """Detailed information about a WordPress plugin."""
    slug: str
    name: str
    version: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    last_updated: Optional[str] = None
    active_installs: Optional[str] = None  # e.g., "1+ million", "10,000+"
    active_installs_raw: Optional[int] = None  # Numeric representation
    requires_wp: Optional[str] = None  # WordPress version requirement
    tested_up_to: Optional[str] = None  # Last tested WordPress version
    requires_php: Optional[str] = None  # PHP version requirement
    rating: Optional[float] = None  # Average rating
    num_ratings: Optional[int] = None  # Number of ratings
    support_threads: Optional[int] = None
    support_threads_resolved: Optional[int] = None
    downloaded: Optional[int] = None  # Total downloads
    tags: Optional[str] = None  # Comma-separated tags
    donate_link: Optional[str] = None
    homepage: Optional[str] = None
    download_link: Optional[str] = None
    screenshots: Optional[str] = None  # JSON string of screenshot URLs
    banners: Optional[str] = None  # JSON string of banner URLs
    icons: Optional[str] = None  # JSON string of icon URLs
    contributors: Optional[str] = None  # Comma-separated contributors
    requires_plugins: Optional[str] = None  # Required plugins
    compatibility: Optional[str] = None  # JSON string of compatibility info
    added: Optional[str] = None  # Date added to repository
    fetched_at: datetime = field(default_factory=datetime.now)  # When this data was fetched
    updated_at: Optional[datetime] = None  # When this record was last updated
    
    def parse_active_installs(self) -> Optional[int]:
        """Convert active_installs string to numeric value."""
        if not self.active_installs:
            return None
        
        install_str = self.active_installs.lower().replace(',', '').replace('+', '').strip()
        
        # Handle millions
        if 'million' in install_str:
            try:
                num = float(install_str.split()[0])
                return int(num * 1_000_000)
            except (ValueError, IndexError):
                pass
        
        # Handle thousands
        if 'thousand' in install_str or 'k' in install_str:
            try:
                num_str = install_str.replace('thousand', '').replace('k', '').strip()
                num = float(num_str)
                return int(num * 1_000)
            except ValueError:
                pass
        
        # Handle direct numbers
        try:
            return int(install_str)
        except ValueError:
            return None

@dataclass
class SearchResult:
    """Search result information."""
    search_id: Optional[int] = None
    search_term: str = ""
    search_type: str = "keyword"  # "keyword", "category", "author"
    total_found: Optional[int] = None
    page_fetched: Optional[int] = None
    plugins_found: int = 0
    search_date: datetime = field(default_factory=datetime.now)
