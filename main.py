# wp_plugin_upload_audit.py
"""A resumable, parallel WordPress-plugin auditor with GUI & tests

Revision 2025-06-05:
  • **Keyword search** – supply a keyword (e.g. `--search File` or use GUI
    “Search term”) to fetch the top N matching plugins from WordPress.org and
    audit them automatically.
  • Search results are deduplicated, limited (default 50), and merged with any
    explicit slugs you enter.
  • Implementation via lightweight HTML scrape of the public search page – no
    extra dependencies.
  • New unit tests for the searcher (mocked HTTP).

All prior features (parallelism, resume, retry, source archiving, SOLID design,
Tk GUI) remain intact.
"""
from __future__ import annotations

import contextlib
import html
import io
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Sequence

import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter, Retry

# ============================ CONFIGURATION ============================ #
DEFAULT_WORKERS = 8
DEFAULT_RETRIES = 3
DEFAULT_TIMEOUT = 30
BACKOFF_FACTOR = 3
EXCEL_PATH = Path("plugin_upload_audit.xlsx")
SAVE_ROOT = Path("saved_plugins")
MAX_SEARCH_RESULTS = 50  # limit to avoid hammering WP.org

UPLOAD_PATTERN = re.compile(
    rb"(wp_handle_upload|media_handle_upload|\$_FILES\b)",
    re.I | re.S,
)

ZIP_URL_TMPL = "https://downloads.wordpress.org/plugin/{slug}.latest-stable.zip"
SEARCH_URL_TMPL = "https://wordpress.org/plugins/search/{kw}/page/{page}/"
SLUG_RE = re.compile(r"https://wordpress\.org/plugins/([a-z0-9\-]+)/")

# =============================  DATA MODEL  ============================== #
@dataclass
class PluginResult:
    slug: str
    status: str  # "True", "False", "skipped", or "error:..."
    timestamp: float = field(default_factory=time.time)

    @property
    def readable_time(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))

# =============================  SERVICES  =============================== #
class IPluginDownloader:
    def download(self, slug: str) -> Path:  # returns extraction root
        raise NotImplementedError


class RequestsDownloader(IPluginDownloader):
    def __init__(self, retries: int = DEFAULT_RETRIES, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()
        retry_conf = Retry(
            total=retries,
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry_conf))

    def download(self, slug: str) -> Path:
        url = ZIP_URL_TMPL.format(slug=slug)
        res = self.session.get(url, timeout=self.timeout)
        if res.status_code != 200:
            raise RuntimeError(f"HTTP {res.status_code}")
        tmp_root = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            zf.extractall(tmp_root)
            top = zf.namelist()[0].split("/")[0]
        return tmp_root / top


class UploadScanner:
    def __init__(self, pattern: re.Pattern[bytes] = UPLOAD_PATTERN):
        self.pattern = pattern
        self.exts = (".php", ".js", ".html", ".twig")

    def has_upload_feature(self, plugin_path: Path) -> bool:
        for root, _d, files in os.walk(plugin_path):
            for fname in files:
                if not fname.lower().endswith(self.exts):
                    continue
                try:
                    with open(Path(root) / fname, "rb") as f:
                        if self.pattern.search(f.read()):
                            return True
                except Exception:
                    continue
        return False

    def gather_files(self, plugin_path: Path) -> list[Path]:
        collected: list[Path] = []
        for root, _d, files in os.walk(plugin_path):
            for fname in files:
                if fname.lower().endswith(self.exts):
                    collected.append(Path(root) / fname)
        return collected


class ExcelReporter:
    def __init__(self, path: Path = EXCEL_PATH):
        self.path = path
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if self.path.exists():
            self.df = pd.read_excel(self.path)
        else:
            self.df = pd.DataFrame(columns=["slug", "upload", "timestamp"])

    def already_done(self, slug: str) -> bool:
        return slug in set(self.df["slug"].astype(str))

    def add_result(self, result: PluginResult):
        with self._lock:
            self.df.loc[len(self.df)] = [result.slug, result.status, result.readable_time]
            self.df.to_excel(self.path, index=False)


class PluginSearcher:
    """Search WordPress.org for plugin slugs by keyword."""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def search(self, keyword: str, limit: int = MAX_SEARCH_RESULTS) -> list[str]:
        keyword = keyword.strip()
        if not keyword:
            return []
        slugs: list[str] = []
        page = 1
        while len(slugs) < limit:
            url = SEARCH_URL_TMPL.format(kw=requests.utils.quote(keyword), page=page)
            r = self.session.get(url, timeout=DEFAULT_TIMEOUT)
            if r.status_code != 200:
                break
            matches = SLUG_RE.findall(r.text)
            new_found = False
            for m in matches:
                if m not in slugs:
                    slugs.append(m)
                    new_found = True
                    if len(slugs) >= limit:
                        break
            if not matches or not new_found:
                break
            page += 1
        return slugs


class PluginLister:
    """Retrieve all plugin slugs from the WordPress plugin API."""

    API_URL = (
        "https://api.wordpress.org/plugins/info/1.2/"
        "?action=query_plugins&request[page]={page}"
    )

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def list_all(self) -> list[str]:
        slugs: list[str] = []
        page = 1
        while True:
            url = self.API_URL.format(page=page)
            r = self.session.get(url, timeout=DEFAULT_TIMEOUT)
            if r.status_code != 200:
                break
            data = r.json()
            plugins = data.get("plugins", [])
            if not plugins:
                break
            for p in plugins:
                slug = p.get("slug")
                if slug:
                    slugs.append(slug)
            page += 1
        return slugs


class AuditManager:
    def __init__(
        self,
        downloader: IPluginDownloader,
        scanner: UploadScanner,
        reporter: ExcelReporter,
        *,
        save_sources: bool = True,
        max_workers: int = DEFAULT_WORKERS,
    ):
        self.downloader = downloader
        self.scanner = scanner
        self.reporter = reporter
        self.save_sources = save_sources
        self.max_workers = max_workers

    # ---------------- internal helpers ---------------- #
    def _archive_sources(self, slug: str, plugin_path: Path):
        dest_root = SAVE_ROOT / slug
        if dest_root.exists():
            shutil.rmtree(dest_root)
        for src in self.scanner.gather_files(plugin_path):
            rel = src.relative_to(plugin_path)
            dest_file = dest_root / rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest_file)

    def _process_slug(self, slug: str) -> PluginResult:
        slug = slug.strip()
        if not slug:
            return PluginResult(slug, "error:empty slug")
        if self.reporter.already_done(slug):
            return PluginResult(slug, "skipped")
        try:
            tmp_path = self.downloader.download(slug)
            has_upload = self.scanner.has_upload_feature(tmp_path)
            if self.save_sources:
                self._archive_sources(slug, tmp_path)
            status = str(has_upload)
        except Exception as e:
            status = f"error:{e}"
        finally:
            with contextlib.suppress(Exception):
                if "tmp_path" in locals() and tmp_path.exists():
                    shutil.rmtree(tmp_path.parent, ignore_errors=True)
        return PluginResult(slug, status)

    def run(self, slugs: Sequence[str]):
        if not slugs:
            print("[!] No slugs to process.")
            return
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futs = [ex.submit(self._process_slug, s) for s in slugs]
            for fut in as_completed(futs):
                res = fut.result()
                self.reporter.add_result(res)
                print(f"[{res.readable_time}] {res.slug}: {res.status}")

# ============================ GUI Front-end ============================ #
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except ImportError:
    tk = None

if tk is not None:
    class AuditGUI:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title("WP Plugin Upload Auditor")
            self._build_widgets()
            self.searcher = PluginSearcher()
            self.mgr = AuditManager(RequestsDownloader(), UploadScanner(), ExcelReporter())

        def _build_widgets(self):
            f = ttk.Frame(self.root, padding=10); f.pack(fill="both", expand=True)
            # Keyword search controls
            kw_row = ttk.Frame(f); kw_row.pack(fill="x")
            ttk.Label(kw_row, text="Search term (optional):").pack(side="left")
            self.kw_entry = ttk.Entry(kw_row, width=25); self.kw_entry.pack(side="left", padx=5)
            ttk.Button(kw_row, text="Fetch", command=self._fetch_kw).pack(side="left")

            ttk.Label(f, text="Plugin slugs (comma / space separated):").pack(anchor="w", pady=(10,0))
            self.txt = tk.Text(f, height=4, width=60); self.txt.pack(fill="x", pady=5)

            self.save_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(f, text="Save source files", variable=self.save_var).pack(anchor="w")
            self.prog = ttk.Progressbar(f, mode="indeterminate"); self.prog.pack(fill="x", pady=8)
            ttk.Button(f, text="Run Audit", command=self._run).pack(anchor="e")

        def _fetch_kw(self):
            kw = self.kw_entry.get().strip()
            if not kw:
                messagebox.showwarning("Warning", "Enter a keyword to search.")
                return
            self.prog.start()
            threading.Thread(target=self._thread_search, args=(kw,), daemon=True).start()

        def _thread_search(self, kw):
            try:
                slugs = self.searcher.search(kw)
                if not slugs:
                    messagebox.showinfo("Search", f"No plugins found for '{kw}'.")
                else:
                    self.txt.insert("end", " " + " ".join(slugs))
                    message = f"Added {len(slugs)} slugs for keyword '{kw}'."
                    messagebox.showinfo("Search", message)
            except Exception as e:
                messagebox.showerror("Error", str(e))
            finally:
                self.prog.stop()

        def _run(self):
            raw = self.txt.get("1.0", "end").strip()
            if not raw:
                messagebox.showerror("Error", "Enter at least one slug or search keyword.")
                return
            slugs = re.split(r"[\s,]+", raw)
            self.mgr.save_sources = self.save_var.get()
            self.prog.start()
            threading.Thread(target=lambda: self._worker(slugs), daemon=True).start()

        def _worker(self, slugs):
            try:
                self.mgr.run(slugs)
                messagebox.showinfo("Done", "Audit complete – check Excel & saved_plugins.")
            except Exception as e:
                messagebox.showerror("Error", str(e))
            finally:
                self.prog.stop()

        def mainloop(self):
            self.root.mainloop()

# ============================  TESTS  ================================== #
import unittest
from unittest import mock

class TestSearcher(unittest.TestCase):
    def test_parse(self):
        html_snippet = "<a href=\"https://wordpress.org/plugins/foo/\">Foo</a>"
        with mock.patch.object(requests.Session, "get") as mget:
            first = mock.Mock(status_code=200, text=html_snippet)
            second = mock.Mock(status_code=200, text="")
            mget.side_effect = [first, second]
            s = PluginSearcher()
            result = s.search("foo", limit=5)
            self.assertEqual(result, ["foo"])

# quick archive unit test retained
class TestArchive(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.download = self.tmp / "download"
        (self.download / "plug").mkdir(parents=True)
        (self.download / "plug/a.php").write_text("<?php wp_handle_upload(); ?>")
    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True); shutil.rmtree(SAVE_ROOT, ignore_errors=True)
    def test_archive(self):
        mgr = AuditManager(
            downloader=mock.Mock(download=lambda slug: self.download / "plug"),
            scanner=UploadScanner(),
            reporter=ExcelReporter(Path(self.tmp / "out.xlsx")),
            save_sources=True,
        )
        mgr.run(["demo"])
        self.assertTrue((SAVE_ROOT / "demo/a.php").exists())

class TestLister(unittest.TestCase):
    def test_all(self):
        page1 = {"plugins": [{"slug": "p1"}, {"slug": "p2"}]}
        page2 = {"plugins": []}
        with mock.patch.object(requests.Session, "get") as mget:
            mget.side_effect = [
                mock.Mock(status_code=200, json=lambda: page1),
                mock.Mock(status_code=200, json=lambda: page2),
            ]
            lister = PluginLister()
            slugs = lister.list_all()
            self.assertEqual(slugs, ["p1", "p2"])

# ============================  MAIN  =================================== #
if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.argv.remove("--test"); unittest.main(verbosity=2); sys.exit(0)

    # CLI arg parsing – very lightweight
    save_flag = True
    if "--nosave" in sys.argv:
        save_flag = False; sys.argv.remove("--nosave")
    if "--save" in sys.argv:
        save_flag = True; sys.argv.remove("--save")

    search_kw = None
    fetch_all = False
    for i, arg in enumerate(sys.argv):
        if arg == "--search" and i + 1 < len(sys.argv):
            search_kw = sys.argv.pop(i + 1)
            sys.argv.remove(arg)
            break
        elif arg.startswith("--search="):
            search_kw = arg.split("=", 1)[1]
            sys.argv.remove(arg)
            break
        elif arg == "--all":
            fetch_all = True
            sys.argv.remove(arg)
            break

    if len(sys.argv) > 1:
        explicit_slugs: List[str] = sys.argv[1:]
    else:
        explicit_slugs = []

    if fetch_all:
        slugs_from_all = PluginLister().list_all()
        explicit_slugs.extend(slugs_from_all)
        print(f"[i] Added {len(slugs_from_all)} slugs from WP API.")

    if search_kw:
        slugs_from_kw = PluginSearcher().search(search_kw)
        explicit_slugs.extend(slugs_from_kw)
        print(f"[i] Added {len(slugs_from_kw)} slugs from keyword '{search_kw}'.")

    if explicit_slugs:
        manager = AuditManager(RequestsDownloader(), UploadScanner(), ExcelReporter(), save_sources=save_flag)
        manager.run(explicit_slugs)
    else:
        if tk is None:
            print("GUI unavailable; supply slugs or --search <kw>.")
            sys.exit(1)
        AuditGUI().mainloop()