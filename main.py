"""Command line interface for the WP plugin scanner."""
from __future__ import annotations

import sys
from typing import List
from pathlib import Path

from wp_plugin_scanner.downloader import RequestsDownloader, download_true_plugin_zips
from wp_plugin_scanner.scanner import UploadScanner
from wp_plugin_scanner.reporter import CsvReporter
from wp_plugin_scanner.searcher import PluginSearcher
from wp_plugin_scanner.manager import AuditManager
from wp_plugin_scanner.local_scanner import scan_local_plugin
from wp_plugin_scanner.cleanup import clean_saved_plugins_only_true, clean_saved_plugins
from wp_plugin_scanner.extract import scan_all_true_plugins

try:
    import tkinter as tk  # type: ignore
    from wp_plugin_scanner.gui import AuditGUI
except Exception:  # pragma: no cover - optional GUI
    tk = None


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    
    is_scan_local = False
    
    do_extract_matches = "--extract-matches" in argv
    if do_extract_matches:
        argv.remove("--extract-matches")
        
    do_download_true_zips = "--dl-plugin" in argv
    if do_download_true_zips:
        argv.remove("--dl-plugin")
    
    clean_plugins = "--clean-plugins" in argv
    if clean_plugins :
        argv.remove("--clean-plugins")
        
    # if "--web" in argv or not argv:
    #     if "--web" in argv:
    #         argv.remove("--web")
    #     from web_gui import app
    #     app.run(debug=True)
    #     return 0
    if "--test" in argv:
        import unittest

        argv.remove("--test")
        return unittest.main(module="tests", verbosity=2, argv=[sys.argv[0]]).result

    save_flag = True
    if "--nosave" in argv:
        save_flag = False
        argv.remove("--nosave")
    if "--save" in argv:
        save_flag = True
        argv.remove("--save")

    search_kw = None
    if "--search" in argv:
        idx = argv.index("--search")
        if idx + 1 < len(argv):
            search_kw = argv.pop(idx + 1)
            argv.pop(idx)
    else:
        for arg in argv:
            if arg.startswith("--search="):
                search_kw = arg.split("=", 1)[1]
                argv.remove(arg)
                break
            
    if "--scan-local" in argv:
        idx = argv.index("--scan-local")
        plugin_path = Path(argv[idx + 1])
        is_scan_local = True
        results = scan_local_plugin(plugin_path)
        for path, lineno, content in results:
            print(f"{path}:{lineno}: {content}")
        return 0

    explicit_slugs: List[str] = argv
    if search_kw:
        slugs_from_kw = PluginSearcher().search(search_kw)
        explicit_slugs.extend(slugs_from_kw)
        print(f"[i] Added {len(slugs_from_kw)} slugs from keyword '{search_kw}'.")
        

    if explicit_slugs:
        manager = AuditManager(
            RequestsDownloader(),
            UploadScanner(),
            CsvReporter(),
            save_sources=save_flag,
        )
        manager.run(explicit_slugs)
        
        if not is_scan_local:
            clean_saved_plugins_only_true()
            
        if do_extract_matches:
            scan_all_true_plugins()
            
        if do_download_true_zips:
            download_true_plugin_zips(Path("plugins"))
                
        if clean_plugins:
            clean_saved_plugins()

            
    # else:
    #     if tk is None:
    #         print("GUI unavailable; supply slugs or --search <kw>.")
    #         return 1
    #     AuditGUI().mainloop()
        return 0
    
    if do_extract_matches:
        scan_all_true_plugins()

    if do_download_true_zips:
        download_true_plugin_zips(Path("plugins"))
        
    if clean_plugins:
        clean_saved_plugins()



if __name__ == "__main__":
    raise SystemExit(main())
