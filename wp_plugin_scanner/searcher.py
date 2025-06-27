import requests
import time
from .config import DEFAULT_TIMEOUT, SLUG_RE, SEARCH_URL_TMPL, MAX_SEARCH_RESULTS

class PluginSearcher:
    """Search WordPress.org for plugin slugs by keyword."""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        # User-Agentを設定してより丁寧にリクエストする
        self.session.headers.update({
            'User-Agent': 'WP-Plugin-Scanner/1.0 (https://github.com/your-repo)'
        })
        self._stop_requested = False
        
    def stop_search(self):
        """Request to stop the current search operation."""
        self._stop_requested = True

    def search(self, keyword: str, limit: int = MAX_SEARCH_RESULTS, interval: float = 2.0, progress_callback=None) -> list[str]:
        keyword = keyword.strip()
        if not keyword:
            return []
        
        # 検索開始時にフラグをリセット
        self._stop_requested = False
        
        slugs: list[str] = []
        page = 1
        consecutive_empty_pages = 0
        max_empty_pages = 3  # 連続で空のページが3つ出たら終了
        max_pages = 50  # 最大50ページまでに制限
        
        while len(slugs) < limit and page <= max_pages and not self._stop_requested:
            if progress_callback:
                progress_callback(f"[ページ {page}] '{keyword}' を検索中... (現在 {len(slugs)} プラグイン)", len(slugs))
                
            url = SEARCH_URL_TMPL.format(kw=requests.utils.quote(keyword), page=page)
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
                                # 指数バックオフで待機時間を増加
                                wait_time = interval * (2 ** attempt)
                                if progress_callback:
                                    progress_callback(f"[ページ {page}] レート制限に達しました。{wait_time:.1f}秒待機中...", len(slugs))
                                time.sleep(wait_time)
                                continue
                            else:
                                if progress_callback:
                                    progress_callback(f"[ページ {page}] レート制限により検索を終了", len(slugs))
                                break
                        else:
                            raise
                    except requests.RequestException as e:
                        if attempt < max_retries - 1:
                            time.sleep(interval)
                            continue
                        if progress_callback:
                            progress_callback(f"[ページ {page}] 接続エラーにより検索を終了: {e}", len(slugs))
                        break
                        
            except requests.RequestException as e:
                if progress_callback:
                    progress_callback(f"検索エラー: {e}", len(slugs))
                break
                
            matches = SLUG_RE.findall(r.text)
            if not matches:
                consecutive_empty_pages += 1
                if progress_callback:
                    progress_callback(f"[ページ {page}] プラグインが見つかりません (連続空ページ: {consecutive_empty_pages})", len(slugs))
                if consecutive_empty_pages >= max_empty_pages:
                    if progress_callback:
                        progress_callback(f"連続して空のページが{max_empty_pages}ページ続いたため検索を終了", len(slugs))
                    break
            else:
                consecutive_empty_pages = 0  # 結果が見つかったらリセット
                
                page_count = 0
                for m in matches:
                    if m not in slugs:
                        slugs.append(m)
                        page_count += 1
                        if len(slugs) >= limit:
                            break
                
                if progress_callback:
                    progress_callback(f"[ページ {page}] {page_count}個の新しいプラグインを発見 (合計: {len(slugs)})", len(slugs))
                        
            page += 1
            
            # 制限に達した場合は終了
            if len(slugs) >= limit:
                if progress_callback:
                    progress_callback(f"制限({limit})に達したため検索を終了", len(slugs))
                break
            
            # 次のページを取得する前に待機
            if page <= max_pages and not self._stop_requested:
                if progress_callback:
                    progress_callback(f"次のページ({page})まで {interval}秒待機中...", len(slugs))
                
                # 待機中も停止チェックを行う（0.5秒刻みで）
                remaining_time = interval
                while remaining_time > 0 and not self._stop_requested:
                    sleep_time = min(0.5, remaining_time)
                    time.sleep(sleep_time)
                    remaining_time -= sleep_time
        
        if self._stop_requested:
            if progress_callback:
                progress_callback(f"ユーザーによって検索が停止されました", len(slugs))
        elif page > max_pages and progress_callback:
            progress_callback(f"最大ページ数({max_pages})に達したため検索を終了", len(slugs))
                
        return slugs
