"""Command line interface for the WP plugin scanner."""
from __future__ import annotations

import sys
from typing import List

from wp_plugin_scanner.downloader import RequestsDownloader
from wp_plugin_scanner.scanner import UploadScanner
from wp_plugin_scanner.reporter import ExcelReporter
from wp_plugin_scanner.searcher import PluginSearcher
from wp_plugin_scanner.manager import AuditManager

try:
    import tkinter as tk  # type: ignore
    from wp_plugin_scanner.gui import AuditGUI
except Exception:  # pragma: no cover - optional GUI
    tk = None


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
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

    explicit_slugs: List[str] = argv
    if search_kw:
        slugs_from_kw = PluginSearcher().search(search_kw)
        explicit_slugs.extend(slugs_from_kw)
        print(f"[i] Added {len(slugs_from_kw)} slugs from keyword '{search_kw}'.")

    if explicit_slugs:
        manager = AuditManager(
            RequestsDownloader(),
            UploadScanner(),
            ExcelReporter(),
            save_sources=save_flag,
        )
        manager.run(explicit_slugs)
    else:
        if tk is None:
            print("GUI unavailable; supply slugs or --search <kw>.")
            return 1
        AuditGUI().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
