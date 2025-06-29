import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List
from pathlib import Path

from .manager import AuditManager
from .downloader import RequestsDownloader
from .scanner import UploadScanner
from .reporter import CsvReporter, SqliteReporter, PluginDetailsSqliteReporter
from .searcher import PluginSearcher
from .plugin_lister import PluginLister
from .plugin_fetcher import PluginDetailFetcher
from .models import SearchResult

class AuditGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("WPプラグインアップロード監査ツール")
        self.root.geometry("800x800")
        
        self.db_prog = None  # データベースタブ専用プログレスバー
        self.db_status_var = tk.StringVar(value="準備完了")
        
        self._build_widgets()
        self.searcher = PluginSearcher()
        self.plugin_lister = PluginLister()
        self.plugin_fetcher = PluginDetailFetcher()
        self.details_reporter = PluginDetailsSqliteReporter()
        self.logs: List[str] = []
        self.fetched_plugins: List[str] = []
        self.fetch_running = False
        self.stop_zip_download = False

    def _build_widgets(self):
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create audit tab
        self._create_audit_tab()
        
        # Create plugin list tab
        self._create_plugin_list_tab()
        
        # Create database viewer tab
        self._create_database_viewer_tab()
    
    def _create_audit_tab(self):
        audit_frame = ttk.Frame(self.notebook)
        self.notebook.add(audit_frame, text="プラグイン監査")

        ttk.Label(audit_frame, text="プラグインスラッグ（カンマまたはスペース区切り）:").pack(anchor="w", padx=10, pady=(10,0))
        self.txt = tk.Text(audit_frame, height=4, width=60)
        self.txt.pack(fill="x", padx=10, pady=5)

        self.save_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(audit_frame, text="ソースファイルを保存", variable=self.save_var).pack(anchor="w", padx=10)
        
        # zip file save section
        self.save_zip_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(audit_frame, text="ソースファイルを保存(zip)", variable=self.save_zip_var).pack(anchor="w", padx=10)

        
        # Database format selection
        db_frame = ttk.Frame(audit_frame)
        db_frame.pack(fill="x", padx=10, pady=(5, 0))
        ttk.Label(db_frame, text="出力形式:").pack(side="left")
        self.db_format_var = tk.StringVar(value="csv")
        ttk.Radiobutton(db_frame, text="CSV", variable=self.db_format_var, value="csv").pack(side="left", padx=(10, 5))
        ttk.Radiobutton(db_frame, text="SQLite", variable=self.db_format_var, value="sqlite").pack(side="left")
        
        self.prog = ttk.Progressbar(audit_frame, mode="indeterminate")
        self.prog.pack(fill="x", padx=10, pady=8)
        self.status_var = tk.StringVar(value="待機中")
        ttk.Label(audit_frame, textvariable=self.status_var).pack(fill="x", padx=10)
        ttk.Button(audit_frame, text="監査実行", command=self._run).pack(anchor="e", padx=10, pady=5)

        # dropdown log section
        self.log_btn = ttk.Button(audit_frame, text="ログ表示 ▼", command=self._toggle_logs)
        self.log_btn.pack(fill="x", padx=10, pady=(5, 0))
        self.log_frame = ttk.Frame(audit_frame)
        self.log_box = tk.Text(self.log_frame, height=8, width=60, state="disabled")
        self.log_box.pack(fill="both", expand=True)
    
    def _create_plugin_list_tab(self):
        list_frame = ttk.Frame(self.notebook)
        self.notebook.add(list_frame, text="プラグイン一覧")
        
        # Options frame
        options_frame = ttk.LabelFrame(list_frame, text="取得オプション")
        options_frame.pack(fill="x", padx=10, pady=5)
        
        # Search and category selection
        search_category_frame = ttk.Frame(options_frame)
        search_category_frame.pack(fill="x", padx=5, pady=5)
        
        # Plugin search field
        ttk.Label(search_category_frame, text="プラグイン検索:").pack(side="left")
        self.plugin_search_var = tk.StringVar()
        plugin_search_entry = ttk.Entry(search_category_frame, textvariable=self.plugin_search_var, width=20)
        plugin_search_entry.pack(side="left", padx=5)
        
        # Category selection
        ttk.Label(search_category_frame, text="カテゴリ:").pack(side="left", padx=(20, 5))
        self.category_var = tk.StringVar(value="popular")
        categories = ["人気", "最新", "更新済", "お気に入り"]
        category_values = ["popular", "newest", "updated", "favorites"]
        category_combo = ttk.Combobox(search_category_frame, textvariable=self.category_var, values=categories, state="readonly", width=15)
        # Store mapping for internal use
        self.category_mapping = dict(zip(categories, category_values))
        self.category_var.set("人気")
        category_combo.pack(side="left", padx=5)
        
        # Limit option
        limit_frame = ttk.Frame(options_frame)
        limit_frame.pack(fill="x", padx=5, pady=5)
        self.limit_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(limit_frame, text="制限:", variable=self.limit_enabled).pack(side="left")
        self.limit_var = tk.StringVar(value="50")
        limit_entry = ttk.Entry(limit_frame, textvariable=self.limit_var, width=10)
        limit_entry.pack(side="left", padx=5)
        ttk.Label(limit_frame, text="個のプラグイン（全て取得する場合はチェックを外す）").pack(side="left")
        
        # Interval option
        interval_frame = ttk.Frame(options_frame)
        interval_frame.pack(fill="x", padx=5, pady=5)
        ttk.Label(interval_frame, text="リクエスト間隔:").pack(side="left")
        self.interval_var = tk.StringVar(value="2.0")
        interval_entry = ttk.Entry(interval_frame, textvariable=self.interval_var, width=10)
        interval_entry.pack(side="left", padx=5)
        ttk.Label(interval_frame, text="秒").pack(side="left")
        
        # Control buttons
        button_frame = ttk.Frame(options_frame)
        button_frame.pack(fill="x", padx=5, pady=5)
        ttk.Button(button_frame, text="取得開始", command=self._start_plugin_fetch).pack(side="left", padx=5)
        ttk.Button(button_frame, text="停止", command=self._stop_plugin_fetch).pack(side="left", padx=5)
        ttk.Button(button_frame, text="リストクリア", command=self._clear_plugin_list).pack(side="left", padx=5)
        ttk.Button(button_frame, text="監査にコピー", command=self._copy_to_audit).pack(side="left", padx=5)
        ttk.Button(button_frame, text="総数取得", command=self._get_total_count).pack(side="left", padx=5)
        
        # Second row of buttons
        button_frame2 = ttk.Frame(options_frame)
        button_frame2.pack(fill="x", padx=5, pady=5)
        ttk.Button(button_frame2, text="詳細情報取得", command=self._fetch_plugin_details).pack(side="left", padx=5)
        ttk.Button(button_frame2, text="詳細表示", command=self._view_plugin_details).pack(side="left", padx=5)
        
        # Progress bar for plugin fetching
        self.list_prog = ttk.Progressbar(list_frame, mode="indeterminate")
        self.list_prog.pack(fill="x", padx=10, pady=5)
        
        # Status label
        self.list_status_var = tk.StringVar(value="プラグイン取得準備完了")
        ttk.Label(list_frame, textvariable=self.list_status_var).pack(fill="x", padx=10)
        
        # Total count label
        self.total_count_var = tk.StringVar(value="総プラグイン数: 不明")
        total_count_label = ttk.Label(list_frame, textvariable=self.total_count_var, font=("TkDefaultFont", 9, "bold"))
        total_count_label.pack(fill="x", padx=10, pady=2)
        
        # Plugin list display
        list_display_frame = ttk.LabelFrame(list_frame, text="プラグイン一覧")
        list_display_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create listbox with scrollbars
        listbox_frame = ttk.Frame(list_display_frame)
        listbox_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.plugin_listbox = tk.Listbox(listbox_frame, selectmode=tk.EXTENDED)
        list_scrollbar_y = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.plugin_listbox.yview)
        list_scrollbar_x = ttk.Scrollbar(listbox_frame, orient="horizontal", command=self.plugin_listbox.xview)
        self.plugin_listbox.configure(yscrollcommand=list_scrollbar_y.set, xscrollcommand=list_scrollbar_x.set)
        
        self.plugin_listbox.pack(side="left", fill="both", expand=True)
        list_scrollbar_y.pack(side="right", fill="y")
        list_scrollbar_x.pack(side="bottom", fill="x")
        
        # Plugin count label
        self.plugin_count_var = tk.StringVar(value="0 個のプラグイン")
        ttk.Label(list_display_frame, textvariable=self.plugin_count_var).pack(padx=5, pady=2)
        
        # Filter controls
        filter_frame = ttk.Frame(list_display_frame)
        filter_frame.pack(fill="x", padx=5, pady=2)
        
        ttk.Label(filter_frame, text="リストフィルタ:").pack(side="left")
        self.filter_var = tk.StringVar()
        filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var, width=20)
        filter_entry.pack(side="left", padx=5)
        filter_entry.bind('<KeyRelease>', self._filter_plugin_list)
        ttk.Button(filter_frame, text="フィルタクリア", command=self._clear_filter).pack(side="left", padx=5)
    
    def _create_database_viewer_tab(self):
        db_frame = ttk.Frame(self.notebook)
        self.notebook.add(db_frame, text="データベース閲覧")
        
        # Search and filter frame
        search_frame = ttk.LabelFrame(db_frame, text="検索とフィルタ")
        search_frame.pack(fill="x", padx=10, pady=5)
        
        # Search controls
        search_row1 = ttk.Frame(search_frame)
        search_row1.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(search_row1, text="検索:").pack(side="left")
        self.db_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_row1, textvariable=self.db_search_var, width=30)
        search_entry.pack(side="left", padx=5)
        ttk.Button(search_row1, text="検索", command=self._search_database).pack(side="left", padx=5)
        ttk.Button(search_row1, text="クリア", command=self._clear_database_search).pack(side="left", padx=5)
        
        # Filter controls
        search_row2 = ttk.Frame(search_frame)
        search_row2.pack(fill="x", padx=5, pady=5)
        
        # Audit filter
        ttk.Label(search_row2, text="監査結果:").pack(side="left")
        self.audit_filter_var = tk.StringVar(value="all")
        audit_options = ["全て", "監査済み(True)", "監査済み(False)", "未監査"]
        audit_values = ["all", "true", "false", "no_audit"]
        self.audit_mapping = dict(zip(audit_options, audit_values))
        audit_combo = ttk.Combobox(search_row2, textvariable=self.audit_filter_var, values=audit_options, state="readonly", width=15)
        self.audit_filter_var.set("全て")
        audit_combo.pack(side="left", padx=5)
        
        # Sort controls
        ttk.Label(search_row2, text="ソート:").pack(side="left", padx=(10, 0))
        self.db_sort_var = tk.StringVar(value="name")
        sort_options = ["名前", "インストール数", "更新日", "評価", "ダウンロード数", "監査日時"]
        sort_values = ["name", "active_installs_raw", "last_updated", "rating", "downloaded", "audit_timestamp"]
        self.sort_mapping = dict(zip(sort_options, sort_values))
        sort_combo = ttk.Combobox(search_row2, textvariable=self.db_sort_var, values=sort_options, state="readonly", width=15)
        self.db_sort_var.set("名前")
        sort_combo.pack(side="left", padx=5)
        
        self.db_sort_desc = tk.BooleanVar(value=False)
        ttk.Checkbutton(search_row2, text="降順", variable=self.db_sort_desc).pack(side="left", padx=5)
        
        # Action buttons
        search_row3 = ttk.Frame(search_frame)
        search_row3.pack(fill="x", padx=5, pady=5)
        
        ttk.Button(search_row3, text="フィルタ適用", command=self._apply_database_filter).pack(side="left", padx=5)
        ttk.Button(search_row3, text="全て読み込み", command=self._load_all_plugins).pack(side="left", padx=5)
        ttk.Button(search_row3, text="更新", command=self._refresh_database).pack(side="left", padx=5)
        
        # Statistics frame
        stats_frame = ttk.LabelFrame(db_frame, text="データベース統計")
        stats_frame.pack(fill="x", padx=10, pady=5)
        
        self.db_stats_var = tk.StringVar(value="データは読み込まれていません")
        ttk.Label(stats_frame, textvariable=self.db_stats_var).pack(padx=5, pady=5)
        
        # Results frame with treeview
        results_frame = ttk.LabelFrame(db_frame, text="プラグインデータベース")
        results_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create treeview with columns
        tree_frame = ttk.Frame(results_frame)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        columns = ("name", "version", "author", "installs", "rating", "updated", "audit_result", "matches")
        self.db_tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings", height=15)
        
        # Configure columns
        self.db_tree.heading("#0", text="スラッグ")
        self.db_tree.heading("name", text="名前")
        self.db_tree.heading("version", text="バージョン")
        self.db_tree.heading("author", text="作者")
        self.db_tree.heading("installs", text="アクティブインストール")
        self.db_tree.heading("rating", text="評価")
        self.db_tree.heading("updated", text="最終更新")
        self.db_tree.heading("audit_result", text="監査結果")
        self.db_tree.heading("matches", text="マッチ数")
        
        # Configure column widths
        self.db_tree.column("#0", width=120)
        self.db_tree.column("name", width=180)
        self.db_tree.column("version", width=70)
        self.db_tree.column("author", width=120)
        self.db_tree.column("installs", width=100)
        self.db_tree.column("rating", width=60)
        self.db_tree.column("updated", width=80)
        self.db_tree.column("audit_result", width=80)
        self.db_tree.column("matches", width=60)
        
        # Add scrollbars
        tree_scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.db_tree.yview)
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.db_tree.xview)
        self.db_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        
        self.db_tree.pack(side="left", fill="both", expand=True)
        tree_scroll_y.pack(side="right", fill="y")
        tree_scroll_x.pack(side="bottom", fill="x")
        
        # Bind double-click event
        self.db_tree.bind("<Double-1>", self._on_tree_double_click)
        
        # Action buttons
        action_frame = ttk.Frame(results_frame)
        action_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Button(action_frame, text="詳細表示", command=self._view_selected_details).pack(side="left", padx=5)
        ttk.Button(action_frame, text="監査結果表示", command=self._view_audit_results).pack(side="left", padx=5)
        ttk.Button(action_frame, text="スラッグを監査にコピー", command=self._copy_slug_to_audit).pack(side="left", padx=5)
        ttk.Button(action_frame, text="結果エクスポート", command=self._export_database_results).pack(side="left", padx=5)
        ttk.Button(action_frame, text="アップロードZIP保存", command=self._download_true_upload_plugins_from_db).pack(side="left", padx=5)
        ttk.Button(action_frame, text="選択した項目を削除", command=self._delete_selected_plugin).pack(side="right", padx=5)
        
        self.db_prog = ttk.Progressbar(db_frame, mode="indeterminate")
        self.db_prog.pack(fill="x", padx=10, pady=(5, 0))

        # show status
        ttk.Label(db_frame, textvariable=self.db_status_var).pack(fill="x", padx=10, pady=(0, 10))
        
        # Initialize with basic stats and load data
        self._update_database_stats()
        # Auto-load plugins on tab creation (with a longer delay to ensure tab is fully initialized)
        self.root.after(500, self._apply_database_filter)
        
        ttk.Button(db_frame, text="保存停止", command=self._stop_zip_download).pack(pady=(0, 10))

    def _run(self):
        raw = self.txt.get("1.0", "end").strip()
        if not raw:
            messagebox.showerror("エラー", "少なくとも1つのスラッグまたは検索キーワードを入力してください。")
            return
        slugs = re.split(r"[\s,]+", raw)
        
        # Create manager with selected reporter
        if self.db_format_var.get() == "sqlite":
            reporter = SqliteReporter()
            output_msg = "SQLite DB & saved_plugins"
        else:
            reporter = CsvReporter()
            output_msg = "CSV & saved_plugins"
            
        self.mgr = AuditManager(RequestsDownloader(), UploadScanner(), reporter, save_sources=self.save_var.get(), save_zip=self.save_zip_var.get())
        self.output_msg = output_msg
        self.prog.start()
        threading.Thread(target=lambda: self._worker(slugs), daemon=True).start()

    def _worker(self, slugs):
        try:
            self.mgr.run(slugs, progress_cb=self._progress_cb)
            self.root.after(0, lambda: messagebox.showinfo(
                "完了", f"監査が完了しました – {self.output_msg} を確認してください。"
            ))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("エラー", str(e)))
        finally:
            self.root.after(0, self.prog.stop)

    def _progress_cb(self, msg: str) -> None:
        self.logs.append(msg)
        self.root.after(0, lambda m=msg: self._append_log(m))

    def _append_log(self, msg: str) -> None:
        self.status_var.set(msg)
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _toggle_logs(self) -> None:
        if self.log_frame.winfo_ismapped():
            self.log_frame.pack_forget()
            self.log_btn.configure(text="ログ表示 ▼")
        else:
            self.log_frame.pack(fill="both", expand=True)
            self.log_btn.configure(text="ログ非表示 ▲")

    # Plugin list tab methods
    def _start_plugin_fetch(self):
        if self.fetch_running:
            messagebox.showwarning("警告", "取得が既に実行中です。")
            return
        
        try:
            interval = float(self.interval_var.get())
            if interval < 0:
                raise ValueError("Interval must be non-negative")
        except ValueError:
            messagebox.showerror("エラー", "無効な間隔値です。有効な数値を入力してください。")
            return
        
        limit = None
        if self.limit_enabled.get():
            try:
                limit = int(self.limit_var.get())
                if limit <= 0:
                    raise ValueError("Limit must be positive")
                print(f"DEBUG: 制限が有効、制限値: {limit}")
            except ValueError:
                messagebox.showerror("エラー", "無効な制限値です。正の整数を入力してください。")
                return
        else:
            print("DEBUG: 制限なし（全て取得）")
        
        self.fetch_running = True
        self.list_prog.start()
        
        # 検索フィールドに文字列がある場合は検索、ない場合はカテゴリ別取得
        search_keyword = self.plugin_search_var.get().strip()
        if search_keyword:
            print(f"DEBUG: 検索キーワード '{search_keyword}' で検索を実行")
            threading.Thread(target=self._fetch_plugins_by_search_thread, args=(search_keyword, limit, interval), daemon=True).start()
        else:
            category_display = self.category_var.get()
            category = self.category_mapping.get(category_display, "popular")
            print(f"DEBUG: カテゴリ '{category}' で取得を実行")
            threading.Thread(target=self._fetch_plugins_thread, args=(category, limit, interval), daemon=True).start()

    def _fetch_plugins_thread(self, category: str, limit: int, interval: float):
        try:
            def progress_callback(msg: str, count: int):
                if not self.fetch_running:
                    return
                self.root.after(0, lambda: self._update_fetch_progress(msg, count))
            
            plugins = self.plugin_lister.fetch_by_category(
                category=category,
                progress_callback=progress_callback,
                limit=limit,
                interval=interval
            )
            
            if self.fetch_running:
                self.root.after(0, lambda: self._finish_plugin_fetch(plugins))
        except Exception as e:
            if self.fetch_running:
                error_msg = str(e)
                self.root.after(0, lambda: self._fetch_error(error_msg))

    def _fetch_plugins_by_search_thread(self, keyword: str, limit: int, interval: float):
        """検索キーワードでプラグインを取得するスレッド関数。"""
        try:
            def progress_callback(msg: str, count: int):
                if not self.fetch_running:
                    return
                self.root.after(0, lambda: self._update_fetch_progress(msg, count))
            
            # searcher.searchは制限に対応していないため、結果を制限する
            if progress_callback:
                progress_callback(f"'{keyword}' を検索中...", 0)
            
            # 検索実行（インターバルを設定して429エラーを回避）
            search_limit = limit if limit else 500  # limitがNoneの場合は500個に制限（無制限だと時間がかかりすぎる）
            search_interval = max(interval, 2.0)  # 最低2秒のインターバルを設定
            all_slugs = self.searcher.search(keyword, search_limit, search_interval, progress_callback)
            
            if self.fetch_running:
                self.root.after(0, lambda: self._finish_plugin_fetch(all_slugs))
        except Exception as e:
            if self.fetch_running:
                error_msg = str(e)
                self.root.after(0, lambda: self._fetch_error(error_msg))

    def _update_fetch_progress(self, msg: str, count: int):
        if not self.fetch_running:
            return
        self.list_status_var.set(msg)
        self.plugin_count_var.set(f"{count} 個のプラグイン")

    def _finish_plugin_fetch(self, plugins: List[str]):
        self.fetch_running = False
        self.list_prog.stop()
        self.fetched_plugins = plugins
        
        # Clear and populate listbox
        self.plugin_listbox.delete(0, tk.END)
        for plugin in plugins:
            self.plugin_listbox.insert(tk.END, plugin)
        
        self.plugin_count_var.set(f"{len(plugins)} plugins")
        self.list_status_var.set(f"完了: {len(plugins)}個のプラグインを発見")
        
        # Auto-save search results and offer to fetch details
        if plugins:
            # Auto-save search results
            self._auto_save_search_results(plugins)
            
            # Ask if user wants to fetch details
            result = messagebox.askyesno(
                "Auto-fetch Details",
                f"Found {len(plugins)} plugins. Would you like to automatically fetch and save their details?\n\n"
                "This will make them available in the Database Viewer with full information."
            )
            if result:
                self._fetch_plugin_details_auto()

    def _fetch_error(self, error_msg: str):
        self.fetch_running = False
        self.list_prog.stop()
        self.list_status_var.set(f"Error: {error_msg}")
        messagebox.showerror("Fetch Error", f"Failed to fetch plugins: {error_msg}")

    def _stop_plugin_fetch(self):
        if not self.fetch_running:
            messagebox.showinfo("情報", "現在実行中の取得操作はありません。")
            return
        
        self.fetch_running = False
        self.list_prog.stop()
        self.list_status_var.set("ユーザーによって停止されました")
        
        # 検索中の場合は検索も停止
        if hasattr(self, 'searcher'):
            self.searcher.stop_search()

    def _search_plugins_by_keyword(self):
        """Search plugins by keyword using the WordPress.org search API."""
        keyword = self.plugin_search_var.get().strip()
        if not keyword:
            messagebox.showwarning("Warning", "Please enter a search keyword.")
            return
        
        self.list_prog.start()
        self.list_status_var.set(f"Searching for '{keyword}'...")
        
        threading.Thread(target=self._thread_search_keyword, args=(keyword,), daemon=True).start()

    def _thread_search_keyword(self, keyword: str):
        """Thread function to search plugins by keyword."""
        try:
            # 429エラーを避けるため、長めのインターバルを設定
            def search_progress(msg: str, count: int):
                self.root.after(0, lambda: self.list_status_var.set(msg))
            
            slugs = self.searcher.search(keyword, interval=2.0, progress_callback=search_progress)
            if not slugs:
                self.root.after(0, lambda: messagebox.showinfo("Search", f"No plugins found for '{keyword}'."))
            else:
                self.root.after(0, lambda: self._finish_keyword_search(keyword, slugs))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Search Error", f"Search failed for '{keyword}':\n{str(e)}"))
        finally:
            self.root.after(0, self.list_prog.stop)

    def _finish_keyword_search(self, keyword: str, slugs: List[str]):
        """Handle completion of keyword search."""
        self.fetched_plugins = slugs
        
        # Clear and populate listbox
        self.plugin_listbox.delete(0, tk.END)
        for plugin in slugs:
            self.plugin_listbox.insert(tk.END, plugin)
        
        self.plugin_count_var.set(f"{len(slugs)} plugins")
        self.list_status_var.set(f"Search completed: Found {len(slugs)} plugins for '{keyword}'")
        
        # Auto-save search results
        self._auto_save_keyword_search(keyword, slugs)
        
        # Ask if user wants to fetch details
        if slugs:
            result = messagebox.askyesno(
                "Fetch Details",
                f"Found {len(slugs)} plugins for '{keyword}'. Would you like to automatically fetch and save their details?\n\n"
                "This will make them available in the Database Viewer with full information."
            )
            if result:
                self._fetch_plugin_details_auto()

    def _filter_plugin_list(self, event=None):
        """Filter the plugin list based on the filter text."""
        filter_text = self.filter_var.get().lower().strip()
        
        if not filter_text:
            # Show all plugins if filter is empty
            self._show_all_plugins()
            return
        
        # Clear current list
        self.plugin_listbox.delete(0, tk.END)
        
        # Filter and show matching plugins
        filtered_plugins = [plugin for plugin in self.fetched_plugins if filter_text in plugin.lower()]
        
        for plugin in filtered_plugins:
            self.plugin_listbox.insert(tk.END, plugin)
        
        # Update count
        self.plugin_count_var.set(f"{len(filtered_plugins)}/{len(self.fetched_plugins)} plugins")

    def _clear_filter(self):
        """Clear the filter and show all plugins."""
        self.filter_var.set("")
        self._show_all_plugins()

    def _show_all_plugins(self):
        """Show all plugins in the list."""
        self.plugin_listbox.delete(0, tk.END)
        for plugin in self.fetched_plugins:
            self.plugin_listbox.insert(tk.END, plugin)
        self.plugin_count_var.set(f"{len(self.fetched_plugins)} plugins")

    def _clear_plugin_list(self):
        self.plugin_listbox.delete(0, tk.END)
        self.fetched_plugins.clear()
        self.plugin_count_var.set("0 plugins")
        self.list_status_var.set("Plugin list cleared")

    def _copy_to_audit(self):
        selected_indices = self.plugin_listbox.curselection()
        if not selected_indices:
            # If nothing selected, copy all
            plugins_to_copy = [self.plugin_listbox.get(i) for i in range(self.plugin_listbox.size())]
        else:
            # Copy selected plugins
            plugins_to_copy = [self.plugin_listbox.get(i) for i in selected_indices]
        
        if not plugins_to_copy:
            messagebox.showinfo("Info", "No plugins to copy.")
            return
        
        # Switch to audit tab
        self.notebook.select(0)
        
        # Add plugins to the text box
        current_text = self.txt.get("1.0", "end").strip()
        if current_text:
            self.txt.insert("end", " ")
        self.txt.insert("end", " ".join(plugins_to_copy))
        
        messagebox.showinfo("Success", f"Copied {len(plugins_to_copy)} plugins to audit tab.")

    def _get_total_count(self):
        """Get total plugin count with options for different methods."""
        result = messagebox.askyesnocancel(
            "Total Count Method",
            "Choose method to get total plugin count:\n\n"
            "Yes: Quick method (parse website text)\n"
            "No: Accurate method (sample pages, takes longer)\n"
            "Cancel: Cancel operation"
        )
        
        if result is None:  # Cancel
            return
        elif result:  # Yes - Quick method
            self._get_total_count_quick()
        else:  # No - Accurate method
            self._get_total_count_accurate()

    def _get_total_count_quick(self):
        """Get total count using quick text parsing method."""
        self.list_prog.start()
        self.list_status_var.set("Getting total plugin count (quick method)...")
        
        threading.Thread(target=self._thread_get_total_quick, daemon=True).start()

    def _thread_get_total_quick(self):
        try:
            total_count = self.plugin_lister.get_total_plugin_count()
            
            if total_count:
                self.root.after(0, lambda: self._display_total_count(total_count, "Quick method"))
            else:
                self.root.after(0, lambda: self._total_count_error("Could not determine total count from website text"))
        except Exception as e:
            self.root.after(0, lambda: self._total_count_error(str(e)))

    def _get_total_count_accurate(self):
        """Get total count using accurate sampling method."""
        self.list_prog.start()
        self.list_status_var.set("Estimating total plugin count (accurate method)...")
        
        threading.Thread(target=self._thread_get_total_accurate, daemon=True).start()

    def _thread_get_total_accurate(self):
        try:
            def progress_callback(msg: str, count: int):
                self.root.after(0, lambda: self.list_status_var.set(msg))
            
            total_count = self.plugin_lister.estimate_total_plugins_by_sampling(progress_callback)
            
            if total_count:
                self.root.after(0, lambda: self._display_total_count(total_count, "Sampling method"))
            else:
                self.root.after(0, lambda: self._total_count_error("Could not estimate total count"))
        except Exception as e:
            self.root.after(0, lambda: self._total_count_error(str(e)))

    def _display_total_count(self, count: int, method: str):
        """Display the total count result."""
        self.list_prog.stop()
        formatted_count = f"{count:,}"
        self.total_count_var.set(f"Total plugins: {formatted_count}")
        self.list_status_var.set(f"Total count obtained using {method}")
        
        messagebox.showinfo(
            "Total Plugin Count", 
            f"Total WordPress plugins: {formatted_count}\n\nMethod: {method}"
        )

    def _total_count_error(self, error_msg: str):
        """Handle total count error."""
        self.list_prog.stop()
        self.list_status_var.set(f"Error getting total count: {error_msg}")
        messagebox.showerror("Error", f"Failed to get total plugin count:\n{error_msg}")

    def _fetch_plugin_details(self):
        """Fetch detailed information for plugins in the list."""
        if not self.fetched_plugins:
            messagebox.showinfo("Info", "No plugins in list to fetch details for.")
            return
        
        result = messagebox.askyesno(
            "Fetch Details",
            f"Fetch detailed information for {len(self.fetched_plugins)} plugins?\n\n"
            "This may take some time depending on the number of plugins."
        )
        
        if not result:
            return
        
        self.list_prog.start()
        self.list_status_var.set("Fetching plugin details...")
        
        threading.Thread(target=self._thread_fetch_details, daemon=True).start()

    def _thread_fetch_details(self):
        """Thread function to fetch plugin details."""
        try:
            total = len(self.fetched_plugins)
            success_count = 0
            
            def progress_callback(msg, current, total_plugins):
                # 新しい形式に対応
                self.root.after(0, lambda: self.list_status_var.set(msg))
            
            results = self.plugin_fetcher.fetch_multiple_plugin_details(
                self.fetched_plugins, 
                progress_callback
            )
            
            # 取得結果を保存
            success_count = 0
            for details in results:
                if details:
                    self.details_reporter.save_plugin_details(details)
                    success_count += 1
            
            self.root.after(0, lambda: self._finish_details_fetch(success_count, total))
            
        except Exception as e:
            self.root.after(0, lambda: self._details_fetch_error(str(e)))

    def _finish_details_fetch(self, success_count: int, total: int):
        """Handle completion of details fetching."""
        self.list_prog.stop()
        self.list_status_var.set(f"Details fetch complete: {success_count}/{total} successful")
        
        messagebox.showinfo(
            "Details Fetch Complete",
            f"Successfully fetched details for {success_count} out of {total} plugins.\n\n"
            "Details have been saved to the database."
        )

    def _details_fetch_error(self, error_msg: str):
        """Handle details fetch error."""
        self.list_prog.stop()
        self.list_status_var.set(f"Details fetch error: {error_msg}")
        messagebox.showerror("Error", f"Failed to fetch plugin details:\n{error_msg}")


    def _view_plugin_details(self):
        """View detailed information for selected plugin."""
        selected_indices = self.plugin_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("Info", "Please select a plugin to view details.")
            return
        
        if len(selected_indices) > 1:
            messagebox.showinfo("Info", "Please select only one plugin to view details.")
            return
        
        selected_slug = self.plugin_listbox.get(selected_indices[0])
        
        # Check if details exist in database
        details = self.details_reporter.get_plugin_details(selected_slug)
        
        if not details:
            result = messagebox.askyesno(
                "No Details Found",
                f"No details found for '{selected_slug}' in database.\n\n"
                "Would you like to fetch details now?"
            )
            
            if result:
                self._fetch_single_plugin_details(selected_slug)
            return
        
        self._show_plugin_details_window(details)

    def _fetch_single_plugin_details(self, slug: str):
        """Fetch details for a single plugin."""
        self.list_prog.start()
        self.list_status_var.set(f"Fetching details for {slug}...")
        
        def fetch_thread():
            try:
                details = self.plugin_fetcher.fetch_plugin_details(slug)
                if details:
                    self.details_reporter.save_plugin_details(details)
                    self.root.after(0, lambda: self._show_plugin_details_window(details))
                else:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Error", f"Failed to fetch details for '{slug}'"
                    ))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", f"Error fetching details for '{slug}':\n{str(e)}"
                ))
            finally:
                self.root.after(0, self.list_prog.stop)
                self.root.after(0, lambda: self.list_status_var.set("Ready"))
        
        threading.Thread(target=fetch_thread, daemon=True).start()

    def _show_plugin_details_window(self, details):
        """Show plugin details in a new window."""
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Plugin Details - {details.name}")
        details_window.geometry("600x500")
        
        # Create scrollable text widget
        text_frame = ttk.Frame(details_window)
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD, state="disabled")
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Format and display details
        details_text = self._format_plugin_details(details)
        
        text_widget.configure(state="normal")
        text_widget.insert("1.0", details_text)
        text_widget.configure(state="disabled")
        
        # Add close button
        ttk.Button(details_window, text="Close", command=details_window.destroy).pack(pady=5)

    def _format_plugin_details(self, details) -> str:
        """Format plugin details for display."""
        lines = [
            f"Plugin: {details.name}",
            f"Slug: {details.slug}",
            "=" * 50,
            ""
        ]
        
        if details.version:
            lines.append(f"Version: {details.version}")
        if details.author:
            lines.append(f"Author: {details.author}")
        if details.last_updated:
            lines.append(f"Last Updated: {details.last_updated}")
        if details.active_installs:
            lines.append(f"Active Installs: {details.active_installs}")
        if details.rating:
            lines.append(f"Rating: {details.rating}/5")
        if details.num_ratings:
            lines.append(f"Number of Ratings: {details.num_ratings:,}")
        if details.downloaded:
            lines.append(f"Downloads: {details.downloaded:,}")
        
        lines.append("")
        
        if details.requires_wp:
            lines.append(f"Requires WordPress: {details.requires_wp}")
        if details.tested_up_to:
            lines.append(f"Tested up to: {details.tested_up_to}")
        if details.requires_php:
            lines.append(f"Requires PHP: {details.requires_php}")
        
        lines.append("")
        
        if details.short_description:
            lines.append("Short Description:")
            lines.append(details.short_description)
            lines.append("")
        
        if details.description:
            lines.append("Description:")
            lines.append(details.description[:500] + "..." if len(details.description) > 500 else details.description)
            lines.append("")
        
        if details.tags:
            lines.append(f"Tags: {details.tags}")
        
        if details.homepage:
            lines.append(f"Homepage: {details.homepage}")
        
        if details.contributors:
            lines.append(f"Contributors: {details.contributors}")
        
        lines.append("")
        lines.append(f"Data fetched: {details.fetched_at}")
        
        return "\n".join(lines)

    # Database viewer methods
    def _search_database(self):
        """Search database for plugins."""
        search_term = self.db_search_var.get().strip()
        if not search_term:
            messagebox.showwarning("Warning", "Please enter a search term.")
            return
        
        try:
            plugins = self.details_reporter.search_plugins(search_term, limit=100)
            self._populate_tree(plugins)
            self._update_database_stats(len(plugins))
        except Exception as e:
            messagebox.showerror("Error", f"Search failed:\n{str(e)}")

    def _clear_database_search(self):
        """Clear search and reload all plugins."""
        self.db_search_var.set("")
        self._load_all_plugins()

    def _load_all_plugins(self):
        """Load all plugins from database."""
        try:
            # Load first 1000 plugins to avoid performance issues
            plugins = self.details_reporter.get_all_plugins(limit=1000)
            
            if not plugins:
                self._populate_tree([])
                self._update_database_stats(0)
                return
            
            # Sort plugins based on user selection
            sort_display = self.db_sort_var.get()
            sort_key = self.sort_mapping.get(sort_display, "name")
            reverse = self.db_sort_desc.get()
            
            if sort_key == "name":
                plugins.sort(key=lambda x: x.name or "", reverse=reverse)
            elif sort_key == "active_installs_raw":
                plugins.sort(key=lambda x: x.active_installs_raw or 0, reverse=reverse)
            elif sort_key == "last_updated":
                plugins.sort(key=lambda x: x.last_updated or "", reverse=reverse)
            elif sort_key == "rating":
                plugins.sort(key=lambda x: x.rating or 0, reverse=reverse)
            elif sort_key == "downloaded":
                plugins.sort(key=lambda x: x.downloaded or 0, reverse=reverse)
            
            self._populate_tree(plugins)
            self._update_database_stats(len(plugins))
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load plugins:\n{str(e)}")

    def _populate_tree(self, plugins):
        """Populate tree view with plugin data."""
        # Clear existing items
        for item in self.db_tree.get_children():
            self.db_tree.delete(item)
        
        # Add plugins to tree
        for i, plugin in enumerate(plugins):
            # Format values for display
            installs = plugin.active_installs or "Unknown"
            rating = f"{plugin.rating:.1f}" if plugin.rating else "N/A"
            updated = plugin.last_updated[:10] if plugin.last_updated else "Unknown"
            
            try:
                self.db_tree.insert("", "end", 
                                  text=plugin.slug,
                                  values=(
                                      plugin.name or "Unknown",
                                      plugin.version or "N/A",
                                      plugin.author or "Unknown",
                                      installs,
                                      rating,
                                      updated
                                  ))
            except Exception:
                continue

    def _update_database_stats(self, loaded_count=None):
        """Update database statistics display."""
        try:
            # Get total count from database
            import sqlite3
            with sqlite3.connect(self.details_reporter.db_path) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM plugin_details')
                total_count = cursor.fetchone()[0]
                
                # Get count with upload scan results
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM plugin_details pd 
                    INNER JOIN upload_scan_results usr ON pd.slug = usr.slug
                ''')
                scanned_count = cursor.fetchone()[0]
                
                # Get search results count
                cursor = conn.execute('SELECT COUNT(*) FROM search_results')
                search_count = cursor.fetchone()[0]
            
            if loaded_count is not None:
                stats_text = f"Loaded: {loaded_count:,} | Total in DB: {total_count:,} | Scanned: {scanned_count:,} | Searches: {search_count:,}"
            else:
                stats_text = f"Total in DB: {total_count:,} | Scanned: {scanned_count:,} | Searches: {search_count:,}"
            
            self.db_stats_var.set(stats_text)
            
        except Exception as e:
            self.db_stats_var.set(f"Error loading stats: {str(e)}")

    def _refresh_database(self):
        """Refresh the current view."""
        self._apply_database_filter()
    
    def _apply_database_filter(self):
        """Apply current filter settings to database view."""
        search_term = self.db_search_var.get().strip()
        audit_filter = self.audit_mapping.get(self.audit_filter_var.get(), "all")
        sort_by = self.sort_mapping.get(self.db_sort_var.get(), "name")
        sort_desc = self.db_sort_desc.get()
        
        def load_thread():
            try:
                results = self.details_reporter.get_plugins_with_audit_results(
                    search_term=search_term,
                    audit_filter=audit_filter,
                    sort_by=sort_by,
                    sort_desc=sort_desc,
                    limit=1000
                )
                self.root.after(0, lambda: self._populate_database_tree(results))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Filter failed: {str(e)}"))
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def _populate_database_tree(self, results):
        """Populate the tree view with filtered results."""
        # Clear existing items
        for item in self.db_tree.get_children():
            self.db_tree.delete(item)
        
        # Add new items
        for result in results:
            plugin = result['plugin']
            audit_status = result['audit_status']
            matches_count = result['matches_count']
            
            # Format audit result for display
            if audit_status == 'true':
                audit_display = '✓ True'
            elif audit_status == 'false':
                audit_display = '✗ False'
            elif audit_status == 'no_audit':
                audit_display = '- 未監査'
            else:
                audit_display = audit_status
            
            # Format values for display
            installs = plugin.active_installs or "Unknown"
            rating = f"{plugin.rating:.1f}" if plugin.rating else "N/A"
            updated = plugin.last_updated[:10] if plugin.last_updated else "N/A"
            matches_display = str(matches_count) if matches_count > 0 else ""
            
            values = (
                plugin.name or "Unknown",
                plugin.version or "N/A", 
                plugin.author or "Unknown",
                installs,
                rating,
                updated,
                audit_display,
                matches_display
            )
            
            self.db_tree.insert("", "end", text=plugin.slug, values=values)
        
        # Update stats
        total_count = len(results)
        audit_true_count = sum(1 for r in results if r['audit_status'] == 'true')
        audit_false_count = sum(1 for r in results if r['audit_status'] == 'false')
        no_audit_count = sum(1 for r in results if r['audit_status'] == 'no_audit')
        
        stats_text = f"表示中: {total_count}件 | 監査済み(True): {audit_true_count}件 | 監査済み(False): {audit_false_count}件 | 未監査: {no_audit_count}件"
        self.db_stats_var.set(stats_text)
    
    def _search_database(self):
        """Search database with current search term."""
        self._apply_database_filter()
    
    def _clear_database_search(self):
        """Clear search term and show all plugins."""
        self.db_search_var.set("")
        self._apply_database_filter()
    
    def _load_all_plugins(self):
        """Load all plugins without any filters."""
        self.db_search_var.set("")
        self.audit_filter_var.set("全て")
        self.db_sort_var.set("名前")
        self.db_sort_desc.set(False)
        self._apply_database_filter()

    def _on_tree_double_click(self, event):
        """Handle double-click on tree item."""
        self._view_selected_details()

    def _view_selected_details(self):
        """View details of selected plugin."""
        selection = self.db_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a plugin to view details.")
            return
        
        item = selection[0]
        slug = self.db_tree.item(item, "text")
        
        details = self.details_reporter.get_plugin_details(slug)
        if details:
            self._show_plugin_details_window(details)
        else:
            messagebox.showerror("Error", f"Could not load details for '{slug}'")

    def _copy_slug_to_audit(self):
        """Copy selected plugin slugs to audit tab."""
        selections = self.db_tree.selection()
        if not selections:
            messagebox.showinfo("Info", "Please select plugins to copy to audit.")
            return
        
        slugs = [self.db_tree.item(item, "text") for item in selections]
        
        # Switch to audit tab
        self.notebook.select(0)
        
        # Add slugs to audit text box
        current_text = self.txt.get("1.0", "end").strip()
        if current_text:
            self.txt.insert("end", " ")
        self.txt.insert("end", " ".join(slugs))
        
        messagebox.showinfo("Success", f"Copied {len(slugs)} plugin slugs to audit tab.")

    def _export_database_results(self):
        """Export current tree view results to CSV."""
        if not self.db_tree.get_children():
            messagebox.showinfo("Info", "No data to export.")
            return
        
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Database Results"
        )
        
        if not filename:
            return
        
        try:
            import csv
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow(["Slug", "Name", "Version", "Author", "Active Installs", "Rating", "Last Updated", "Audit Result", "Matches"])
                
                # Write data
                for item in self.db_tree.get_children():
                    slug = self.db_tree.item(item, "text")
                    values = self.db_tree.item(item, "values")
                    writer.writerow([slug] + list(values))
            
            messagebox.showinfo("Success", f"Results exported to {filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n{str(e)}")

    def _delete_selected_plugin(self):
        """Delete selected plugin from database."""
        selections = self.db_tree.selection()
        if not selections:
            messagebox.showinfo("Info", "Please select plugins to delete.")
            return
        
        slugs = [self.db_tree.item(item, "text") for item in selections]
        
        result = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete {len(slugs)} plugin(s) from the database?\n\n"
            "This action cannot be undone."
        )
        
        if not result:
            return
        
        try:
            import sqlite3
            with sqlite3.connect(self.details_reporter.db_path) as conn:
                for slug in slugs:
                    # Delete from all related tables
                    conn.execute('DELETE FROM upload_scan_results WHERE slug = ?', (slug,))
                    conn.execute('DELETE FROM search_result_plugins WHERE plugin_slug = ?', (slug,))
                    conn.execute('DELETE FROM plugin_details WHERE slug = ?', (slug,))
                
                conn.commit()
            
            # Remove from tree view
            for item in selections:
                self.db_tree.delete(item)
            
            self._update_database_stats()
            messagebox.showinfo("Success", f"Deleted {len(slugs)} plugin(s) from database.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Delete failed:\n{str(e)}")
            
    def _download_true_upload_plugins_from_db(self):
        from tkinter import filedialog, messagebox
        import sqlite3
        import requests
        from .config import ZIP_URL_TMPL
        from pathlib import Path

        # 保存先フォルダ選択
        folder = filedialog.askdirectory(title="保存先フォルダを選択")
        if not folder:
            return
        self.zip_save_folder = Path(folder)  # ← ここが重要
        self.zip_save_folder.mkdir(parents=True, exist_ok=True)

        def fetch_slugs_from_db():
            db_paths = ["plugin_upload_audit.db", "plugin_details.db"]
            slugs = set()
            for db_path in db_paths:
                if not Path(db_path).exists():
                    continue
                try:
                    with sqlite3.connect(db_path) as conn:
                        cursor = conn.cursor()
                        tables = {row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                        if "plugin_audit_results" in tables:
                            cursor.execute("SELECT slug FROM plugin_audit_results WHERE upload = 'True'")
                            slugs.update(row[0] for row in cursor.fetchall())
                        elif "upload_scan_results" in tables:
                            cursor.execute("SELECT slug FROM upload_scan_results WHERE has_upload = 1")
                            slugs.update(row[0] for row in cursor.fetchall())
                except Exception as e:
                    print(f"[!] DB読み込みエラー: {db_path} → {e}")
            return sorted(slugs)

        def worker():
            self.root.after(0, self.db_prog.start)
            self.root.after(0, lambda: self.db_status_var.set("保存処理を開始しています..."))
            self.stop_zip_download = False

            slugs = fetch_slugs_from_db()
            if not slugs:
                self.root.after(0, self.db_prog.stop)
                self.root.after(0, lambda: self.db_status_var.set("アップロード機能ありのプラグインが見つかりませんでした。"))
                self.root.after(0, lambda: messagebox.showwarning("警告", "アップロード機能ありのプラグインが見つかりませんでした。"))
                return

            count = 0
            total = len(slugs)
            for i, slug in enumerate(slugs, 1):
                if self.stop_zip_download:
                    self.root.after(0, self.db_prog.stop)
                    self.root.after(0, lambda: self.db_status_var.set("保存処理を中止しました"))
                    return

                try:
                    out_path = self.zip_save_folder / f"{slug}.zip"
                    if out_path.exists():
                        print(f"[=] スキップ（既存）: {out_path}")
                        continue
                    url = ZIP_URL_TMPL.format(slug=slug)
                    res = requests.get(url, timeout=30)
                    res.raise_for_status()
                    out_path.write_bytes(res.content)
                    print(f"[✔] 保存: {out_path}")
                    count += 1
                except Exception as e:
                    print(f"[!] ダウンロード失敗: {slug} → {e}")

                # ステータス更新
                msg = f"[{i}/{total}] {slug} のZIPを保存中..."
                self.root.after(0, lambda m=msg: self.db_status_var.set(m))

            self.stop_zip_download = False
            self.root.after(0, self.db_prog.stop)
            self.root.after(0, lambda: self.db_status_var.set("保存処理が完了しました"))
            self.root.after(0, lambda: messagebox.showinfo("完了", f"{count} 件のプラグインを保存しました。"))

        import threading
        threading.Thread(target=worker, daemon=True).start()


    def _stop_zip_download(self):
        self.stop_zip_download = True
        self.db_status_var.set("保存停止が要求されました…")
        
    # Auto-save helper methods
    def _auto_save_search_results(self, plugins: List[str]):
        """Automatically save search results to database."""
        try:
            category = self.category_var.get()
            search_term = f"auto_{category}_fetch"
            
            search_result = SearchResult(
                search_term=search_term,
                search_type="category",
                total_found=len(plugins),
                plugins_found=len(plugins)
            )
            
            search_id = self.details_reporter.save_search_result(search_result, plugins)
            if search_id:
                self.list_status_var.set(f"Search results auto-saved (ID: {search_id})")
        except Exception as e:
            print(f"Auto-save search results failed: {e}")

    def _auto_save_keyword_search(self, keyword: str, slugs: List[str]):
        """Automatically save keyword search results to database."""
        try:
            search_result = SearchResult(
                search_term=keyword,
                search_type="keyword",
                total_found=len(slugs),
                plugins_found=len(slugs)
            )
            
            search_id = self.details_reporter.save_search_result(search_result, slugs)
            if search_id:
                print(f"Keyword search auto-saved (ID: {search_id})")
        except Exception as e:
            print(f"Auto-save keyword search failed: {e}")

    def _fetch_plugin_details_auto(self):
        """Automatically fetch plugin details for current list."""
        if not self.fetched_plugins:
            return
        
        self.list_prog.start()
        self.list_status_var.set("Auto-fetching plugin details...")
        
        threading.Thread(target=self._thread_fetch_details_auto, daemon=True).start()

    def _thread_fetch_details_auto(self):
        """Thread function to auto-fetch plugin details."""
        try:
            total = len(self.fetched_plugins)
            success_count = 0
            
            def progress_callback(current, total_plugins, details):
                if details:
                    # Create basic plugin details even if full fetch fails
                    basic_details = self._create_basic_plugin_details(details.slug, details.name)
                    if self.details_reporter.save_plugin_details(basic_details):
                        nonlocal success_count
                        success_count += 1
                
                progress_msg = f"Auto-fetching: {current}/{total_plugins} (saved: {success_count})"
                self.root.after(0, lambda: self.list_status_var.set(progress_msg))
            
            # Fetch basic info for each plugin
            for i, slug in enumerate(self.fetched_plugins):
                if not self.details_reporter.plugin_exists(slug):
                    details = self.plugin_fetcher.fetch_plugin_details(slug)
                    if details:
                        self.details_reporter.save_plugin_details(details)
                        success_count += 1
                    else:
                        # Create minimal record
                        basic_details = self._create_basic_plugin_details(slug, slug.replace('-', ' ').title())
                        self.details_reporter.save_plugin_details(basic_details)
                        success_count += 1
                
                progress_msg = f"Auto-fetching: {i+1}/{total} (saved: {success_count})"
                self.root.after(0, lambda msg=progress_msg: self.list_status_var.set(msg))
            
            self.root.after(0, lambda: self._finish_auto_details_fetch(success_count, total))
            
        except Exception as e:
            self.root.after(0, lambda: self._auto_details_fetch_error(str(e)))

    def _create_basic_plugin_details(self, slug: str, name: str):
        """Create basic plugin details when full fetch fails."""
        from .models import PluginDetails
        return PluginDetails(
            slug=slug,
            name=name,
            description="Auto-saved plugin (details pending)"
        )

    def _finish_auto_details_fetch(self, success_count: int, total: int):
        """Handle completion of auto details fetching."""
        self.list_prog.stop()
        self.list_status_var.set(f"Auto-fetch complete: {success_count}/{total} plugins saved")
        
        # Refresh database viewer if it's been loaded
        if hasattr(self, 'db_tree'):
            self._update_database_stats()

    def _auto_details_fetch_error(self, error_msg: str):
        """Handle auto details fetch error."""
        self.list_prog.stop()
        self.list_status_var.set(f"Auto-fetch error: {error_msg}")

    def _view_audit_results(self):
        """監査結果を表示する新しいウィンドウを開く"""
        # 新しいウィンドウを作成
        audit_window = tk.Toplevel(self.root)
        audit_window.title("監査結果詳細")
        audit_window.geometry("1000x600")
        
        # CSVとSQLiteの両方から監査結果を取得
        audit_data = self._get_audit_results()
        
        if not audit_data:
            ttk.Label(audit_window, text="監査結果が見つかりません。").pack(pady=20)
            return
        
        # Treeviewを作成
        columns = ("slug", "upload", "timestamp", "files_scanned", "matches_count", "file_path", "line_number", "line_content", "matched_pattern")
        tree = ttk.Treeview(audit_window, columns=columns, show="headings", height=20)
        
        # ヘッダーを設定
        tree.heading("slug", text="プラグインスラッグ")
        tree.heading("upload", text="アップロード機能")
        tree.heading("timestamp", text="スキャン日時")
        tree.heading("files_scanned", text="スキャンファイル数")
        tree.heading("matches_count", text="マッチ数")
        tree.heading("file_path", text="ファイルパス")
        tree.heading("line_number", text="行番号")
        tree.heading("line_content", text="行内容")
        tree.heading("matched_pattern", text="マッチパターン")
        
        # カラム幅を設定
        tree.column("slug", width=120)
        tree.column("upload", width=80)
        tree.column("timestamp", width=120)
        tree.column("files_scanned", width=80)
        tree.column("matches_count", width=80)
        tree.column("file_path", width=150)
        tree.column("line_number", width=60)
        tree.column("line_content", width=200)
        tree.column("matched_pattern", width=120)
        
        # データを追加
        for row in audit_data:
            tree.insert("", "end", values=row)
        
        # スクロールバーを追加
        scrollbar_y = ttk.Scrollbar(audit_window, orient="vertical", command=tree.yview)
        scrollbar_x = ttk.Scrollbar(audit_window, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        # レイアウト
        tree.pack(side="left", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")
        scrollbar_x.pack(side="bottom", fill="x")
        
        # 閉じるボタン
        ttk.Button(audit_window, text="閉じる", command=audit_window.destroy).pack(pady=5)

    def _get_audit_results(self):
        """CSV/SQLiteから監査結果を取得"""
        audit_data = []
        
        # SQLiteから監査結果を取得
        try:
            import sqlite3
            db_path = "plugin_upload_audit.db"
            if Path(db_path).exists():
                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute('''
                        SELECT slug, upload, timestamp, files_scanned, matches_count,
                               file_path, line_number, line_content, matched_pattern
                        FROM plugin_audit_results
                        ORDER BY timestamp DESC
                    ''')
                    rows = cursor.fetchall()
                    for row in rows:
                        audit_data.append(tuple(row))
        except Exception as e:
            print(f"SQLiteからの監査結果取得エラー: {e}")
        
        # CSVから監査結果を取得（SQLiteにデータがない場合）
        if not audit_data:
            try:
                import pandas as pd
                csv_path = "plugin_upload_audit.csv"
                if Path(csv_path).exists():
                    df = pd.read_csv(csv_path)
                    # 必要なカラムがあるかチェック
                    required_cols = ["slug", "upload", "timestamp"]
                    if all(col in df.columns for col in required_cols):
                        for _, row in df.iterrows():
                            audit_data.append((
                                row.get("slug", ""),
                                row.get("upload", ""),
                                row.get("timestamp", ""),
                                row.get("files_scanned", 0),
                                row.get("matches_count", 0),
                                row.get("file_path", ""),
                                row.get("line_number", 0),
                                row.get("line_content", ""),
                                row.get("matched_pattern", "")
                            ))
            except Exception as e:
                print(f"CSVからの監査結果取得エラー: {e}")
        
        return audit_data
    
    

    def mainloop(self):
        self.root.mainloop()