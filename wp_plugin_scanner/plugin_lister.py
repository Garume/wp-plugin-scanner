import requests
import time
import re
from typing import Callable, Optional
from .config import DEFAULT_TIMEOUT, SLUG_RE

class PluginLister:
    """Fetch all available WordPress plugins from the repository."""
    
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        # User-Agentを設定してより丁寧にリクエストする
        self.session.headers.update({
            'User-Agent': 'WP-Plugin-Scanner/1.0 (https://github.com/your-repo)'
        })
    
    def get_total_plugin_count(self) -> Optional[int]:
        """
        Get the total number of plugins available on WordPress.org.
        
        Returns:
            Total plugin count or None if unable to determine
        """
        try:
            # Try to get total count from the main plugins page
            url = "https://wordpress.org/plugins/"
            r = self.session.get(url, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            
            # Look for patterns that indicate total plugin count
            # WordPress.org often shows "X,XXX plugins" somewhere on the page
            patterns = [
                r'(\d{1,3}(?:,\d{3})*)\s+plugins?',  # "X,XXX plugins"
                r'(\d{1,3}(?:,\d{3})*)\s+total',     # "X,XXX total"
                r'of\s+(\d{1,3}(?:,\d{3})*)',        # "of X,XXX"
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, r.text, re.IGNORECASE)
                for match in matches:
                    count_str = match.group(1).replace(',', '')
                    try:
                        count = int(count_str)
                        # Sanity check: WordPress has thousands of plugins
                        if count > 1000:
                            return count
                    except ValueError:
                        continue
            
            # Alternative method: try to get count from search results
            return self._get_count_from_search()
            
        except Exception:
            return None
    
    def _get_count_from_search(self) -> Optional[int]:
        """
        Try to get plugin count by doing a broad search and looking for result count.
        
        Returns:
            Estimated plugin count or None
        """
        try:
            # Search for a very common term to get maximum results
            url = "https://wordpress.org/plugins/search/wordpress/"
            r = self.session.get(url, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            
            # Look for result count indicators
            patterns = [
                r'(\d{1,3}(?:,\d{3})*)\s+results?',
                r'(\d{1,3}(?:,\d{3})*)\s+plugins?\s+found',
                r'showing.*?(\d{1,3}(?:,\d{3})*)',
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, r.text, re.IGNORECASE)
                for match in matches:
                    count_str = match.group(1).replace(',', '')
                    try:
                        count = int(count_str)
                        if count > 1000:
                            return count
                    except ValueError:
                        continue
            
            return None
            
        except Exception:
            return None
    
    def estimate_total_plugins_by_sampling(
        self, 
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> Optional[int]:
        """
        Estimate total plugin count by sampling different pages and finding the last page.
        This is more accurate but takes longer.
        
        Args:
            progress_callback: Called with (status_message, estimated_count)
            
        Returns:
            Estimated total plugin count
        """
        try:
            if progress_callback:
                progress_callback("Starting plugin count estimation...", 0)
            
            # Start with a high page number and work backwards
            # to find the last page with plugins
            test_pages = [1000, 500, 200, 100, 50]
            last_valid_page = 1
            
            for test_page in test_pages:
                if progress_callback:
                    progress_callback(f"Testing page {test_page}...", 0)
                
                url = f"https://wordpress.org/plugins/browse/popular/page/{test_page}/"
                
                try:
                    r = self.session.get(url, timeout=DEFAULT_TIMEOUT)
                    r.raise_for_status()
                    
                    # Check if this page has plugins
                    matches = SLUG_RE.findall(r.text)
                    if matches:
                        last_valid_page = test_page
                        if progress_callback:
                            progress_callback(f"Page {test_page} has plugins", 0)
                        break
                    else:
                        if progress_callback:
                            progress_callback(f"Page {test_page} is empty", 0)
                        
                except requests.RequestException:
                    if progress_callback:
                        progress_callback(f"Page {test_page} not accessible", 0)
                    continue
                
                time.sleep(0.5)  # Be respectful
            
            # Now do a binary search to find the exact last page
            low = last_valid_page
            high = test_pages[0] if last_valid_page < test_pages[0] else last_valid_page * 2
            
            while low < high - 1:
                mid = (low + high) // 2
                
                if progress_callback:
                    progress_callback(f"Binary search: testing page {mid}...", 0)
                
                url = f"https://wordpress.org/plugins/browse/popular/page/{mid}/"
                
                try:
                    r = self.session.get(url, timeout=DEFAULT_TIMEOUT)
                    r.raise_for_status()
                    
                    matches = SLUG_RE.findall(r.text)
                    if matches:
                        low = mid
                        if progress_callback:
                            progress_callback(f"Page {mid} has {len(matches)} plugins", 0)
                    else:
                        high = mid
                        if progress_callback:
                            progress_callback(f"Page {mid} is empty", 0)
                        
                except requests.RequestException:
                    high = mid
                
                time.sleep(0.5)  # Be respectful
            
            # Estimate total plugins: last_page * plugins_per_page
            # WordPress typically shows 24 plugins per page
            plugins_per_page = 24
            estimated_total = low * plugins_per_page
            
            if progress_callback:
                progress_callback(f"Estimation complete: ~{estimated_total} plugins", estimated_total)
            
            return estimated_total
            
        except Exception:
            if progress_callback:
                progress_callback("Estimation failed", 0)
            return None
    
    def fetch_all_plugins(
        self, 
        progress_callback: Optional[Callable[[str, int], None]] = None,
        limit: Optional[int] = None,  
        interval: float = 1.0
    ) -> list[str]:
        """
        Fetch all plugin slugs from WordPress.org.
        
        Args:
            progress_callback: Called with (status_message, plugin_count)
            limit: Maximum number of plugins to fetch (None for all)
            interval: Sleep interval between requests in seconds
        """
        all_slugs: list[str] = []
        page = 1
        
        while True:
            if limit and len(all_slugs) >= limit:
                break
                
            if progress_callback:
                progress_callback(f"Fetching page {page}...", len(all_slugs))
            
            # WordPress.org popular plugins page
            url = f"https://wordpress.org/plugins/browse/popular/page/{page}/"
            
            try:
                r = self.session.get(url, timeout=DEFAULT_TIMEOUT)
                r.raise_for_status()
            except requests.RequestException as e:
                if progress_callback:
                    progress_callback(f"Error on page {page}: {e}", len(all_slugs))
                break
            
            # Extract plugin slugs from the page
            matches = SLUG_RE.findall(r.text)
            
            if not matches:
                if progress_callback:
                    progress_callback("No more plugins found", len(all_slugs))
                break
            
            page_slugs = []
            for slug in matches:
                if slug not in all_slugs:
                    all_slugs.append(slug)
                    page_slugs.append(slug)
                    
                    if limit and len(all_slugs) >= limit:
                        break
            
            if progress_callback:
                progress_callback(f"Page {page}: Found {len(page_slugs)} new plugins", len(all_slugs))
            
            page += 1
            
            # Sleep between requests to be respectful
            if interval > 0:
                time.sleep(interval)
        
        if progress_callback:
            progress_callback(f"Completed: Found {len(all_slugs)} plugins total", len(all_slugs))
        
        return all_slugs

    def fetch_by_category(
        self,
        category: str = "popular",
        progress_callback: Optional[Callable[[str, int], None]] = None,
        limit: Optional[int] = None,
        interval: float = 1.0
    ) -> list[str]:
        """
        Fetch plugins by category (popular, newest, etc.).
        
        Args:
            category: Category name (popular, newest, updated, etc.)
            progress_callback: Called with (status_message, plugin_count)
            limit: Maximum number of plugins to fetch
            interval: Sleep interval between requests in seconds
        """
        all_slugs: list[str] = []
        page = 1
        
        while True:
            if limit and len(all_slugs) >= limit:
                break
                
            if progress_callback:
                progress_callback(f"[ページ {page}] {category}カテゴリを取得中... (現在 {len(all_slugs)} プラグイン)", len(all_slugs))
            
            url = f"https://wordpress.org/plugins/browse/{category}/page/{page}/"
            
            try:
                # 429エラーを避けるためのリトライロジック
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        r = self.session.get(url, timeout=DEFAULT_TIMEOUT)
                        r.raise_for_status()
                        break
                    except requests.HTTPError as e:
                        if r.status_code == 429:  # Too Many Requests
                            if attempt < max_retries - 1:
                                wait_time = interval * (2 ** attempt)
                                if progress_callback:
                                    progress_callback(f"[ページ {page}] レート制限に達しました。{wait_time:.1f}秒待機中...", len(all_slugs))
                                time.sleep(wait_time)
                                continue
                            else:
                                if progress_callback:
                                    progress_callback(f"Rate limit exceeded on page {page}", len(all_slugs))
                                return all_slugs  # 取得できた分だけ返す
                        else:
                            raise
                    except requests.RequestException as e:
                        if attempt < max_retries - 1:
                            time.sleep(interval)
                            continue
                        if progress_callback:
                            progress_callback(f"Error on page {page}: {e}", len(all_slugs))
                        return all_slugs  # 取得できた分だけ返す
            except requests.RequestException as e:
                if progress_callback:
                    progress_callback(f"Error on page {page}: {e}", len(all_slugs))
                break
            
            matches = SLUG_RE.findall(r.text)
            
            if not matches:
                if progress_callback:
                    progress_callback("No more plugins found", len(all_slugs))
                break
            
            page_slugs = []
            for slug in matches:
                if slug not in all_slugs:
                    all_slugs.append(slug)
                    page_slugs.append(slug)
                    
                    if limit and len(all_slugs) >= limit:
                        break
            
            if progress_callback:
                progress_callback(f"[ページ {page}] {len(page_slugs)}個の新しいプラグインを発見 (合計: {len(all_slugs)})", len(all_slugs))
            
            page += 1
            
            if interval > 0:
                if progress_callback:
                    progress_callback(f"次のページ({page})まで {interval}秒待機中...", len(all_slugs))
                time.sleep(interval)
        
        if progress_callback:
            progress_callback(f"完了: {category}カテゴリから{len(all_slugs)}個のプラグインを取得しました", len(all_slugs))
        
        return all_slugs