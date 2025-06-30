from __future__ import annotations
import contextlib
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence, Callable
import zipfile

from .config import SAVE_SOURCE, SAVE_ZIP, DEFAULT_WORKERS
from .models import PluginResult
from .downloader import IPluginDownloader
from .scanner import UploadScanner
from .reporter import IReporter

class AuditManager:
    def __init__(
        self,
        downloader: IPluginDownloader,
        scanner: UploadScanner,
        reporter: IReporter,
        *,
        save_sources: bool = False,
        save_zip: bool = True,
        max_workers: int = DEFAULT_WORKERS,
    ):
        self.downloader = downloader
        self.scanner = scanner
        self.reporter = reporter
        self.save_sources = save_sources
        self.save_zip = save_zip
        self.max_workers = max_workers
        
        SAVE_SOURCE.mkdir(parents=True, exist_ok=True)
        SAVE_ZIP.mkdir(parents=True, exist_ok=True)

    def _archive_sources(self, slug: str, plugin_path: Path):
        dest_root = SAVE_SOURCE / slug
        if dest_root.exists():
            shutil.rmtree(dest_root)
        for src in self.scanner.gather_files(plugin_path):
            rel = src.relative_to(plugin_path)
            dest_file = dest_root / rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest_file)
    
    def _save_zip_archive(self, slug: str, plugin_path: Path):
        zip_path = SAVE_ZIP / f"{slug}.zip"
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for src in plugin_path.rglob("*"):
                if src.is_file():
                    arcname = src.relative_to(plugin_path)
                    zipf.write(src, arcname)

    def _process_slug(self, slug: str) -> PluginResult:
        slug = slug.strip()
        if not slug:
            return PluginResult(slug, "error:empty slug")
        if self.reporter.already_done(slug):
            print(f"DEBUG: {slug} has already been processed, skipping.")
            return None  # Do not overwrite existing results
        try:
            tmp_path = self.downloader.download(slug)
            upload_matches, files_scanned = self.scanner.scan_for_upload_features(tmp_path)
            has_upload = len(upload_matches) > 0
            
            if self.save_sources:
                self._archive_sources(slug, tmp_path)
                
            if self.save_zip:
                self._save_zip_archive(slug, tmp_path)
                
            status = str(has_upload)
            result = PluginResult(slug, status, upload_matches=upload_matches, files_scanned=files_scanned)
        except Exception as e:
            status = f"error:{e}"
            result = PluginResult(slug, status)
        finally:
            with contextlib.suppress(Exception):
                if "tmp_path" in locals() and tmp_path.exists():
                    shutil.rmtree(tmp_path.parent, ignore_errors=True)
        return result

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
                if res is not None:
                    self.reporter.add_result(res)
                    remaining = total - i
                    log(f"[{res.readable_time}] {res.slug}: {res.status} (remaining {remaining})")
                else:
                    remaining = total - i
                    log(f"[✓] skipped (remaining {remaining})")
                    
