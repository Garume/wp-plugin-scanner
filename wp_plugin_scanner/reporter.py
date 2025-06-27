import threading
import sqlite3
from pathlib import Path
from typing import Optional
import pandas as pd
from abc import ABC, abstractmethod

from .config import CSV_PATH  
from .models import PluginResult, PluginDetails, SearchResult, UploadMatch

class IReporter(ABC):
    @abstractmethod
    def already_done(self, slug: str) -> bool:
        pass
    
    @abstractmethod
    def add_result(self, result: PluginResult) -> None:
        pass

class CsvReporter(IReporter):
    def __init__(self, path: Path = CSV_PATH):
        self.path = path
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if self.path.exists():
            self.df = pd.read_csv(self.path)
            # 古いCSVファイルの場合、新しいカラムを追加
            if "files_scanned" not in self.df.columns:
                self.df["files_scanned"] = 0
            if "matches_count" not in self.df.columns:
                self.df["matches_count"] = 0
            if "file_path" not in self.df.columns:
                self.df["file_path"] = ""
            if "line_number" not in self.df.columns:
                self.df["line_number"] = 0
            if "line_content" not in self.df.columns:
                self.df["line_content"] = ""
            if "matched_pattern" not in self.df.columns:
                self.df["matched_pattern"] = ""
        else:
            self.df = pd.DataFrame(columns=[
                "slug", "upload", "timestamp", "files_scanned", "matches_count", 
                "file_path", "line_number", "line_content", "matched_pattern"
            ])

    def already_done(self, slug: str) -> bool:
        return slug in set(self.df["slug"].astype(str))

    def add_result(self, result: PluginResult):
        with self._lock:
            # 既存の同じslugのデータを削除（重複を避けるため）
            self.df = self.df[self.df['slug'] != result.slug]
            
            # 基本情報を準備
            files_scanned = result.files_scanned if hasattr(result, 'files_scanned') else 0
            matches_count = len(result.upload_matches) if hasattr(result, 'upload_matches') and result.upload_matches else 0
            
            # 詳細情報がある場合は各マッチごとに行を追加
            if hasattr(result, 'upload_matches') and result.upload_matches:
                for match in result.upload_matches:
                    new_row = pd.DataFrame([{
                        "slug": result.slug,
                        "upload": result.status,
                        "timestamp": result.readable_time,
                        "files_scanned": files_scanned,
                        "matches_count": matches_count,
                        "file_path": match.file_path,
                        "line_number": match.line_number,
                        "line_content": match.line_content,
                        "matched_pattern": match.matched_pattern
                    }])
                    self.df = pd.concat([self.df, new_row], ignore_index=True)
            else:
                # マッチがない場合は基本情報のみを追加
                new_row = pd.DataFrame([{
                    "slug": result.slug,
                    "upload": result.status,
                    "timestamp": result.readable_time,
                    "files_scanned": files_scanned,
                    "matches_count": matches_count,
                    "file_path": "",
                    "line_number": 0,
                    "line_content": "",
                    "matched_pattern": ""
                }])
                self.df = pd.concat([self.df, new_row], ignore_index=True)
            
            # CSVファイルに保存
            self.df.to_csv(self.path, index=False)


class SqliteReporter(IReporter):
    def __init__(self, db_path: Path = Path("plugin_upload_audit.db")):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # メインテーブルを統合形式に変更
            conn.execute('''
                CREATE TABLE IF NOT EXISTS plugin_audit_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT NOT NULL,
                    upload TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    files_scanned INTEGER DEFAULT 0,
                    matches_count INTEGER DEFAULT 0,
                    file_path TEXT DEFAULT '',
                    line_number INTEGER DEFAULT 0,
                    line_content TEXT DEFAULT '',
                    matched_pattern TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 古いテーブルが存在する場合は移行
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='plugin_results'")
            if cursor.fetchone():
                try:
                    # 古いデータを新しいテーブルに移行
                    conn.execute('''
                        INSERT OR IGNORE INTO plugin_audit_results (slug, upload, timestamp, files_scanned, matches_count)
                        SELECT slug, upload, timestamp, 
                               COALESCE(files_scanned, 0), 
                               COALESCE(matches_count, 0)
                        FROM plugin_results
                    ''')
                except sqlite3.OperationalError:
                    # カラムが存在しない場合は基本データのみ移行
                    conn.execute('''
                        INSERT OR IGNORE INTO plugin_audit_results (slug, upload, timestamp)
                        SELECT slug, upload, timestamp FROM plugin_results
                    ''')
            
            conn.commit()

    def already_done(self, slug: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            # 新しいテーブルと古いテーブルの両方をチェック
            cursor = conn.execute('SELECT 1 FROM plugin_audit_results WHERE slug = ?', (slug,))
            if cursor.fetchone():
                return True
            # 古いテーブルもチェック（移行期間のため）
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='plugin_results'")
            if cursor.fetchone():
                cursor = conn.execute('SELECT 1 FROM plugin_results WHERE slug = ?', (slug,))
                return cursor.fetchone() is not None
            return False

    def add_result(self, result: PluginResult):
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                # 既存の同じslugのデータを削除
                conn.execute('DELETE FROM plugin_audit_results WHERE slug = ?', (result.slug,))
                
                files_scanned = result.files_scanned if hasattr(result, 'files_scanned') else 0
                matches_count = len(result.upload_matches) if hasattr(result, 'upload_matches') and result.upload_matches else 0
                
                # 詳細情報がある場合は各マッチごとに行を追加
                if hasattr(result, 'upload_matches') and result.upload_matches:
                    for match in result.upload_matches:
                        conn.execute('''
                            INSERT INTO plugin_audit_results (
                                slug, upload, timestamp, files_scanned, matches_count,
                                file_path, line_number, line_content, matched_pattern
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (result.slug, result.status, result.readable_time, files_scanned, matches_count,
                              match.file_path, match.line_number, match.line_content, match.matched_pattern))
                else:
                    # マッチがない場合は基本情報のみを追加
                    conn.execute('''
                        INSERT INTO plugin_audit_results (
                            slug, upload, timestamp, files_scanned, matches_count,
                            file_path, line_number, line_content, matched_pattern
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (result.slug, result.status, result.readable_time, files_scanned, matches_count,
                          '', 0, '', ''))
                
                conn.commit()
                
                # PluginDetailsSqliteReporterにも保存（互換性のため）
                if hasattr(result, 'upload_matches') and result.upload_matches:
                    details_reporter = PluginDetailsSqliteReporter(self.db_path)
                    details_reporter.save_upload_scan_result(result)


class PluginDetailsSqliteReporter:
    """Reporter for storing detailed plugin information in SQLite."""
    
    def __init__(self, db_path: Path = Path("plugin_details.db")):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Plugin details table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS plugin_details (
                    slug TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT,
                    author TEXT,
                    description TEXT,
                    short_description TEXT,
                    last_updated TEXT,
                    active_installs TEXT,
                    active_installs_raw INTEGER,
                    requires_wp TEXT,
                    tested_up_to TEXT,
                    requires_php TEXT,
                    rating REAL,
                    num_ratings INTEGER,
                    support_threads INTEGER,
                    support_threads_resolved INTEGER,
                    downloaded INTEGER,
                    tags TEXT,
                    donate_link TEXT,
                    homepage TEXT,
                    download_link TEXT,
                    screenshots TEXT,
                    banners TEXT,
                    icons TEXT,
                    contributors TEXT,
                    requires_plugins TEXT,
                    compatibility TEXT,
                    added TEXT,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Search results table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS search_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_term TEXT NOT NULL,
                    search_type TEXT NOT NULL DEFAULT 'keyword',
                    total_found INTEGER,
                    page_fetched INTEGER,
                    plugins_found INTEGER NOT NULL DEFAULT 0,
                    search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Search result plugins junction table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS search_result_plugins (
                    search_id INTEGER,
                    plugin_slug TEXT,
                    position INTEGER,
                    FOREIGN KEY (search_id) REFERENCES search_results (id),
                    FOREIGN KEY (plugin_slug) REFERENCES plugin_details (slug),
                    PRIMARY KEY (search_id, plugin_slug)
                )
            ''')
            
            # Upload scan results table (enhanced)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS upload_scan_results (
                    slug TEXT PRIMARY KEY,
                    has_upload BOOLEAN NOT NULL,
                    scan_status TEXT NOT NULL,
                    scan_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    files_scanned INTEGER,
                    upload_patterns_found TEXT,
                    FOREIGN KEY (slug) REFERENCES plugin_details (slug)
                )
            ''')
            
            # Upload match details table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS upload_match_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    line_content TEXT NOT NULL,
                    matched_pattern TEXT NOT NULL,
                    scan_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (slug) REFERENCES upload_scan_results (slug)
                )
            ''')
            
            # Create indexes for better performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_plugin_details_name ON plugin_details (name)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_plugin_details_author ON plugin_details (author)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_plugin_details_last_updated ON plugin_details (last_updated)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_plugin_details_active_installs_raw ON plugin_details (active_installs_raw)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_search_results_term ON search_results (search_term)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_search_results_date ON search_results (search_date)')
            
            conn.commit()
    
    def save_plugin_details(self, details: PluginDetails) -> bool:
        """Save plugin details to database."""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute('''
                        INSERT OR REPLACE INTO plugin_details (
                            slug, name, version, author, description, short_description,
                            last_updated, active_installs, active_installs_raw, requires_wp,
                            tested_up_to, requires_php, rating, num_ratings, support_threads,
                            support_threads_resolved, downloaded, tags, donate_link, homepage,
                            download_link, screenshots, banners, icons, contributors,
                            requires_plugins, compatibility, added, fetched_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        details.slug, details.name, details.version, details.author,
                        details.description, details.short_description, details.last_updated,
                        details.active_installs, details.active_installs_raw, details.requires_wp,
                        details.tested_up_to, details.requires_php, details.rating, details.num_ratings,
                        details.support_threads, details.support_threads_resolved, details.downloaded,
                        details.tags, details.donate_link, details.homepage, details.download_link,
                        details.screenshots, details.banners, details.icons, details.contributors,
                        details.requires_plugins, details.compatibility, details.added,
                        details.fetched_at, details.fetched_at
                    ))
                    conn.commit()
                    return True
        except Exception:
            return False
    
    def save_search_result(self, search_result: SearchResult, plugin_slugs: list[str]) -> Optional[int]:
        """Save search result and associated plugin slugs."""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    # Insert search result
                    cursor = conn.execute('''
                        INSERT INTO search_results (
                            search_term, search_type, total_found, page_fetched, plugins_found, search_date
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        search_result.search_term, search_result.search_type, search_result.total_found,
                        search_result.page_fetched, len(plugin_slugs), search_result.search_date
                    ))
                    
                    search_id = cursor.lastrowid
                    
                    # Insert plugin associations
                    for i, slug in enumerate(plugin_slugs):
                        conn.execute('''
                            INSERT OR IGNORE INTO search_result_plugins (search_id, plugin_slug, position)
                            VALUES (?, ?, ?)
                        ''', (search_id, slug, i + 1))
                    
                    conn.commit()
                    return search_id
        except Exception:
            return None
    
    def save_upload_scan_result(self, result: PluginResult, files_scanned: int = 0, patterns_found: str = "") -> bool:
        """Save upload scan result with detailed match information."""
        try:
            with self._lock:
                with sqlite3.connect(self.db_path) as conn:
                    has_upload = result.status == "True"
                    
                    # 結果をもとにfiles_scannedとpatterns_foundを設定
                    actual_files_scanned = result.files_scanned if result.files_scanned > 0 else files_scanned
                    actual_patterns = ", ".join([match.matched_pattern for match in result.upload_matches]) if result.upload_matches else patterns_found
                    
                    # メインの結果を保存
                    conn.execute('''
                        INSERT OR REPLACE INTO upload_scan_results (
                            slug, has_upload, scan_status, files_scanned, upload_patterns_found
                        ) VALUES (?, ?, ?, ?, ?)
                    ''', (result.slug, has_upload, result.status, actual_files_scanned, actual_patterns))
                    
                    # 詳細なマッチ情報を保存
                    if result.upload_matches:
                        # 既存の詳細を削除
                        conn.execute('DELETE FROM upload_match_details WHERE slug = ?', (result.slug,))
                        
                        # 新しい詳細を挿入
                        for match in result.upload_matches:
                            conn.execute('''
                                INSERT INTO upload_match_details (
                                    slug, file_path, line_number, line_content, matched_pattern
                                ) VALUES (?, ?, ?, ?, ?)
                            ''', (result.slug, match.file_path, match.line_number, match.line_content, match.matched_pattern))
                    
                    conn.commit()
                    return True
        except Exception as e:
            print(f"DEBUG: Error saving upload scan result: {e}")
            return False
    
    def get_plugin_details(self, slug: str) -> Optional[PluginDetails]:
        """Retrieve plugin details from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM plugin_details WHERE slug = ?
                ''', (slug,))
                row = cursor.fetchone()
                
                if row:
                    return PluginDetails(
                        slug=row['slug'], name=row['name'], version=row['version'],
                        author=row['author'], description=row['description'],
                        short_description=row['short_description'], last_updated=row['last_updated'],
                        active_installs=row['active_installs'], active_installs_raw=row['active_installs_raw'],
                        requires_wp=row['requires_wp'], tested_up_to=row['tested_up_to'],
                        requires_php=row['requires_php'], rating=row['rating'],
                        num_ratings=row['num_ratings'], support_threads=row['support_threads'],
                        support_threads_resolved=row['support_threads_resolved'],
                        downloaded=row['downloaded'], tags=row['tags'],
                        donate_link=row['donate_link'], homepage=row['homepage'],
                        download_link=row['download_link'], screenshots=row['screenshots'],
                        banners=row['banners'], icons=row['icons'],
                        contributors=row['contributors'], requires_plugins=row['requires_plugins'],
                        compatibility=row['compatibility'], added=row['added'],
                        fetched_at=row['fetched_at']
                    )
                return None
        except Exception:
            return None
    
    def plugin_exists(self, slug: str) -> bool:
        """Check if plugin details exist in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT 1 FROM plugin_details WHERE slug = ?', (slug,))
                return cursor.fetchone() is not None
        except Exception:
            return False
    
    def get_all_plugins(self, limit: int = None, offset: int = 0) -> list[PluginDetails]:
        """Get all plugins from database with optional pagination."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                query = 'SELECT * FROM plugin_details ORDER BY name'
                params = []
                
                if limit:
                    query += ' LIMIT ? OFFSET ?'
                    params = [limit, offset]
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                plugins = []
                for row in rows:
                    try:
                        # Convert Row to dict and create PluginDetails
                        row_dict = dict(row)
                        plugin = PluginDetails(**row_dict)
                        plugins.append(plugin)
                    except Exception:
                        continue
                return plugins
                
        except Exception:
            return []
    
    def search_plugins(self, search_term: str, limit: int = 50) -> list[PluginDetails]:
        """Search plugins by name, author, or description."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM plugin_details 
                    WHERE name LIKE ? OR author LIKE ? OR description LIKE ?
                    ORDER BY active_installs_raw DESC NULLS LAST, name
                    LIMIT ?
                ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', limit))
                
                rows = cursor.fetchall()
                return [PluginDetails(**dict(row)) for row in rows]
        except Exception:
            return []
    
    def get_plugins_with_audit_results(
        self, 
        search_term: str = "", 
        audit_filter: str = "all",  # "all", "true", "false", "no_audit"
        sort_by: str = "name", 
        sort_desc: bool = False, 
        limit: int = 1000
    ) -> list[dict]:
        """
        Get plugins with their audit results, with filtering and sorting options.
        
        Args:
            search_term: Search term for plugin name/author/description
            audit_filter: Filter by audit results ("all", "true", "false", "no_audit")
            sort_by: Sort field (name, active_installs_raw, downloaded, rating, last_updated)
            sort_desc: Sort in descending order
            limit: Maximum number of results
            
        Returns:
            List of dictionaries containing plugin details and audit results
        """
        try:
            # Try to find audit results from multiple database files
            audit_results = {}
            
            # Possible audit database files to check
            possible_audit_dbs = [
                "plugin_upload_audit.db",
                "plugin_details.db", 
                self.db_path
            ]
            
            # Collect audit data from all possible sources
            for db_file in possible_audit_dbs:
                try:
                    with sqlite3.connect(db_file) as conn:
                        conn.row_factory = sqlite3.Row
                        
                        # Check for plugin_audit_results table
                        tables = conn.execute("""
                            SELECT name FROM sqlite_master 
                            WHERE type='table' AND (
                                name='plugin_audit_results' OR 
                                name='plugin_results' OR
                                name='upload_scan_results'
                            )
                        """).fetchall()
                        
                        if tables:
                            print(f"DEBUG: Found audit tables in {db_file}: {[t[0] for t in tables]}")
                        
                        for table in tables:
                            table_name = table[0]
                            try:
                                if table_name == 'plugin_audit_results':
                                    rows = conn.execute('''
                                        SELECT slug, upload, timestamp, 
                                               COALESCE(files_scanned, 0) as files_scanned,
                                               COALESCE(matches_count, 0) as matches_count
                                        FROM plugin_audit_results 
                                        ORDER BY id DESC
                                    ''').fetchall()
                                elif table_name == 'plugin_results':
                                    rows = conn.execute('''
                                        SELECT slug, upload, timestamp, 
                                               COALESCE(files_scanned, 0) as files_scanned,
                                               COALESCE(matches_count, 0) as matches_count
                                        FROM plugin_results 
                                        ORDER BY rowid DESC
                                    ''').fetchall()
                                elif table_name == 'upload_scan_results':
                                    rows = conn.execute('''
                                        SELECT slug, 
                                               CASE WHEN has_upload THEN 'True' ELSE 'False' END as upload,
                                               scan_timestamp as timestamp,
                                               COALESCE(files_scanned, 0) as files_scanned,
                                               0 as matches_count
                                        FROM upload_scan_results 
                                        ORDER BY scan_timestamp DESC
                                    ''').fetchall()
                                else:
                                    continue
                                
                                print(f"DEBUG: Found {len(rows)} audit records in {db_file}.{table_name}")
                                
                                # Store the latest result for each plugin
                                for row in rows:
                                    slug = row['slug']
                                    if slug not in audit_results:
                                        audit_results[slug] = {
                                            'upload': row['upload'],
                                            'timestamp': row['timestamp'],
                                            'files_scanned': row['files_scanned'],
                                            'matches_count': row['matches_count']
                                        }
                            except sqlite3.Error as e:
                                print(f"DEBUG: Error reading from {db_file}.{table_name}: {e}")
                                continue
                                
                except sqlite3.Error as e:
                    print(f"DEBUG: Could not connect to {db_file}: {e}")
                    continue
            
            print(f"DEBUG: Total audit results collected: {len(audit_results)}")
            
            # Now get plugin details and combine with audit results
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Get all plugin details
                base_query = 'SELECT * FROM plugin_details'
                where_conditions = []
                params = []
                
                # Search term filter
                if search_term.strip():
                    where_conditions.append('''
                        (name LIKE ? OR author LIKE ? OR description LIKE ?)
                    ''')
                    search_pattern = f'%{search_term.strip()}%'
                    params.extend([search_pattern, search_pattern, search_pattern])
                
                # Build final query
                if where_conditions:
                    base_query += " WHERE " + " AND ".join(where_conditions)
                
                # Add ORDER BY
                valid_sort_fields = {
                    "name": "name",
                    "active_installs_raw": "active_installs_raw",
                    "downloaded": "downloaded", 
                    "rating": "rating",
                    "last_updated": "last_updated",
                    "audit_timestamp": "last_updated"  # fallback to last_updated
                }
                
                sort_field = valid_sort_fields.get(sort_by, "name")
                sort_order = "DESC" if sort_desc else "ASC"
                
                # Handle NULL values properly for numeric fields
                if sort_by in ["active_installs_raw", "downloaded", "rating"]:
                    if sort_desc:
                        base_query += f" ORDER BY {sort_field} DESC NULLS LAST"
                    else:
                        base_query += f" ORDER BY {sort_field} ASC NULLS LAST"
                else:
                    base_query += f" ORDER BY {sort_field} {sort_order}"
                
                # Add LIMIT
                base_query += " LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(base_query, params)
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    row_dict = dict(row)
                    slug = row_dict['slug']
                    
                    # Get audit results for this plugin
                    audit_data = audit_results.get(slug, {})
                    audit_result = audit_data.get('upload')
                    
                    # Determine audit status
                    if audit_result is None:
                        audit_status = 'no_audit'
                    elif audit_result == 'True':
                        audit_status = 'true'
                    else:
                        audit_status = 'false'
                    
                    # Apply audit filter
                    if audit_filter != "all":
                        if audit_filter == "true" and audit_status != "true":
                            continue
                        elif audit_filter == "false" and audit_status != "false":
                            continue
                        elif audit_filter == "no_audit" and audit_status != "no_audit":
                            continue
                    
                    # Create result object
                    try:
                        plugin = PluginDetails(**{k: v for k, v in row_dict.items() 
                                                if k in ['slug', 'name', 'version', 'author', 'description', 
                                                        'short_description', 'last_updated', 'active_installs', 
                                                        'active_installs_raw', 'requires_wp', 'tested_up_to', 
                                                        'requires_php', 'rating', 'num_ratings', 'support_threads',
                                                        'support_threads_resolved', 'downloaded', 'tags', 
                                                        'donate_link', 'homepage', 'download_link', 'screenshots',
                                                        'banners', 'icons', 'contributors', 'requires_plugins',
                                                        'compatibility', 'added', 'fetched_at']})
                        
                        result = {
                            'plugin': plugin,
                            'audit_status': audit_status,
                            'audit_result': audit_result,
                            'audit_timestamp': audit_data.get('timestamp'),
                            'files_scanned': audit_data.get('files_scanned', 0),
                            'matches_count': audit_data.get('matches_count', 0)
                        }
                        results.append(result)
                    except Exception:
                        continue
                
                # Sort by audit-related fields if needed
                if sort_by == "audit_timestamp":
                    results.sort(
                        key=lambda x: x['audit_timestamp'] or "", 
                        reverse=sort_desc
                    )
                
                return results[:limit]
                
        except Exception as e:
            print(f"DEBUG: Error in get_plugins_with_audit_results: {e}")
            return []
