import requests
import json
import re
import time
from typing import Optional, List
from bs4 import BeautifulSoup
from .config import DEFAULT_TIMEOUT
from .models import PluginDetails

class PluginDetailFetcher:
    """Fetch detailed information about WordPress plugins."""
    
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        # User-Agentを設定してより丁寧にリクエストする
        self.session.headers.update({
            'User-Agent': 'WP-Plugin-Scanner/1.0 (https://github.com/your-repo)'
        })
    
    def fetch_plugin_details(self, slug: str) -> Optional[PluginDetails]:
        """
        Fetch detailed information about a plugin from WordPress.org.
        
        Args:
            slug: Plugin slug
            
        Returns:
            PluginDetails object or None if fetch failed
        """
        try:
            # Try WordPress.org API first
            api_details = self._fetch_from_api(slug)
            if api_details:
                return api_details
            
            # Fallback to scraping plugin page
            return self._fetch_from_page(slug)
            
        except Exception:
            return None
    
    def _fetch_from_api(self, slug: str) -> Optional[PluginDetails]:
        """Fetch plugin details from WordPress.org API."""
        try:
            url = f"https://api.wordpress.org/plugins/info/1.0/{slug}.json"
            
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
                            wait_time = 2.0 * (2 ** attempt)
                            time.sleep(wait_time)
                            continue
                        else:
                            return None  # 失敗時はNoneを返す
                    else:
                        raise
                except requests.RequestException as e:
                    if attempt < max_retries - 1:
                        time.sleep(2.0)
                        continue
                    raise
            
            data = r.json()
            
            # Extract screenshots, banners, icons as JSON strings
            screenshots = json.dumps(data.get('screenshots', {})) if data.get('screenshots') else None
            banners = json.dumps(data.get('banners', {})) if data.get('banners') else None
            icons = json.dumps(data.get('icons', {})) if data.get('icons') else None
            
            # Extract tags
            tags = ', '.join(data.get('tags', {}).keys()) if data.get('tags') else None
            
            # Extract contributors
            contributors = ', '.join(data.get('contributors', {}).keys()) if data.get('contributors') else None
            
            # Extract compatibility info
            compatibility = json.dumps(data.get('compatibility', {})) if data.get('compatibility') else None
            
            # Parse active installs
            active_installs = data.get('active_installs')
            active_installs_str = None
            if isinstance(active_installs, int):
                if active_installs >= 1000000:
                    active_installs_str = f"{active_installs // 1000000}+ million"
                elif active_installs >= 1000:
                    active_installs_str = f"{active_installs // 1000}+ thousand"
                else:
                    active_installs_str = f"{active_installs}+"
            
            return PluginDetails(
                slug=slug,
                name=data.get('name', ''),
                version=data.get('version'),
                author=data.get('author'),
                description=data.get('description'),
                short_description=data.get('short_description'),
                last_updated=data.get('last_updated'),
                active_installs=active_installs_str,
                active_installs_raw=active_installs if isinstance(active_installs, int) else None,
                requires_wp=data.get('requires'),
                tested_up_to=data.get('tested'),
                requires_php=data.get('requires_php'),
                rating=data.get('rating'),
                num_ratings=data.get('num_ratings'),
                support_threads=data.get('support_threads'),
                support_threads_resolved=data.get('support_threads_resolved'),
                downloaded=data.get('downloaded'),
                tags=tags,
                donate_link=data.get('donate_link'),
                homepage=data.get('homepage'),
                download_link=data.get('download_link'),
                screenshots=screenshots,
                banners=banners,
                icons=icons,
                contributors=contributors,
                requires_plugins=', '.join(data.get('requires_plugins', [])) if data.get('requires_plugins') else None,
                compatibility=compatibility,
                added=data.get('added')
            )
            
        except Exception:
            return None
    
    def _fetch_from_page(self, slug: str) -> Optional[PluginDetails]:
        """Fetch plugin details by scraping the plugin page."""
        try:
            url = f"https://wordpress.org/plugins/{slug}/"
            r = self.session.get(url, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Extract basic information
            name_elem = soup.find('h1', class_='plugin-title')
            name = name_elem.get_text().strip() if name_elem else slug
            
            # Extract version from meta or sidebar
            version = None
            version_elem = soup.find('li', string=re.compile(r'Version:'))
            if version_elem:
                version = version_elem.get_text().replace('Version:', '').strip()
            
            # Extract author
            author = None
            author_elem = soup.find('a', class_='author')
            if author_elem:
                author = author_elem.get_text().strip()
            
            # Extract description
            description = None
            desc_elem = soup.find('div', class_='plugin-description')
            if desc_elem:
                description = desc_elem.get_text().strip()
            
            # Extract last updated
            last_updated = None
            updated_elem = soup.find('li', string=re.compile(r'Last updated:'))
            if updated_elem:
                last_updated = updated_elem.get_text().replace('Last updated:', '').strip()
            
            # Extract active installations
            active_installs = None
            installs_elem = soup.find('li', string=re.compile(r'Active installations:'))
            if installs_elem:
                active_installs = installs_elem.get_text().replace('Active installations:', '').strip()
            
            # Extract WordPress version compatibility
            requires_wp = None
            tested_up_to = None
            
            wp_elem = soup.find('li', string=re.compile(r'WordPress Version:'))
            if wp_elem:
                wp_text = wp_elem.get_text()
                # Parse "WordPress Version: 4.6 or higher" or "Tested up to: 6.4"
                if 'or higher' in wp_text:
                    requires_wp = wp_text.split('or higher')[0].replace('WordPress Version:', '').strip()
                if 'Tested up to:' in wp_text:
                    tested_up_to = wp_text.split('Tested up to:')[1].strip()
            
            # Extract rating
            rating = None
            rating_elem = soup.find('div', class_='rating-text')
            if rating_elem:
                rating_text = rating_elem.get_text()
                rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                if rating_match:
                    rating = float(rating_match.group(1))
            
            # Extract download count
            downloaded = None
            download_elem = soup.find('li', string=re.compile(r'Downloaded'))
            if download_elem:
                download_text = download_elem.get_text()
                # Parse "Downloaded 1,234,567 times"
                download_match = re.search(r'Downloaded ([\d,]+)', download_text)
                if download_match:
                    downloaded = int(download_match.group(1).replace(',', ''))
            
            # Extract tags
            tags = None
            tag_elems = soup.find_all('a', {'rel': 'tag'})
            if tag_elems:
                tags = ', '.join([tag.get_text().strip() for tag in tag_elems])
            
            return PluginDetails(
                slug=slug,
                name=name,
                version=version,
                author=author,
                description=description,
                last_updated=last_updated,
                active_installs=active_installs,
                active_installs_raw=self._parse_active_installs_from_text(active_installs),
                requires_wp=requires_wp,
                tested_up_to=tested_up_to,
                rating=rating,
                downloaded=downloaded,
                tags=tags
            )
            
        except Exception:
            return None
    
    def _parse_active_installs_from_text(self, installs_text: str) -> Optional[int]:
        """Parse active installations text to numeric value."""
        if not installs_text:
            return None
        
        # Create a PluginDetails instance to use the parsing method
        temp_details = PluginDetails(slug="", name="", active_installs=installs_text)
        return temp_details.parse_active_installs()
    
    def fetch_multiple_plugin_details(
        self, 
        slugs: List[str], 
        progress_callback=None
    ) -> List[PluginDetails]:
        """
        Fetch details for multiple plugins.
        
        Args:
            slugs: List of plugin slugs
            progress_callback: Called with (current_index, total, plugin_details)
            
        Returns:
            List of PluginDetails objects (None entries for failed fetches)
        """
        results = []
        total = len(slugs)
        
        for i, slug in enumerate(slugs):
            if progress_callback:
                progress_callback(f"[{i+1}/{total}] {slug} の詳細情報を取得中...", i, total)
            
            details = self.fetch_plugin_details(slug)
            results.append(details)
            
            if progress_callback:
                status = "成功" if details else "失敗"
                progress_callback(f"[{i+1}/{total}] {slug} - {status}", i + 1, total)
                
            # API制限を避けるため短い間隔で待機
            if i < total - 1:  # 最後の要素でない場合
                time.sleep(0.5)
        
        return results