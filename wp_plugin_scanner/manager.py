from __future__ import annotations
import contextlib
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence, Callable

from .config import SAVE_ROOT, DEFAULT_WORKERS
from .models import PluginResult
from .downloader import IPluginDownloader
from .scanner import UploadScanner
from .reporter import ExcelReporter

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

    def run(
        self,
        slugs: Sequence[str],
        *,
        progress_cb: "Callable[[str], None] | None" = None,
    ) -> None:
        """Process each slug and report progress."""
        log = progress_cb or print
        if not slugs:
            log("[!] No slugs to process.")
            return
        total = len(slugs)
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futs = []
            for idx, slug in enumerate(slugs, start=1):
                log(f"[{idx}/{total}] Checking {slug}...")
                futs.append(ex.submit(self._process_slug, slug))
            for i, fut in enumerate(as_completed(futs), start=1):
                res = fut.result()
                self.reporter.add_result(res)
                remaining = total - i
                log(
                    f"[{res.readable_time}] {res.slug}: {res.status} (remaining {remaining})"
                )
