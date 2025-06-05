import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from .manager import AuditManager
from .downloader import RequestsDownloader
from .scanner import UploadScanner
from .reporter import ExcelReporter
from .searcher import PluginSearcher

class AuditGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("WP Plugin Upload Auditor")
        self._build_widgets()
        self.searcher = PluginSearcher()
        self.mgr = AuditManager(RequestsDownloader(), UploadScanner(), ExcelReporter())

    def _build_widgets(self):
        f = ttk.Frame(self.root, padding=10)
        f.pack(fill="both", expand=True)
        kw_row = ttk.Frame(f)
        kw_row.pack(fill="x")
        ttk.Label(kw_row, text="Search term (optional):").pack(side="left")
        self.kw_entry = ttk.Entry(kw_row, width=25)
        self.kw_entry.pack(side="left", padx=5)
        ttk.Button(kw_row, text="Fetch", command=self._fetch_kw).pack(side="left")

        ttk.Label(f, text="Plugin slugs (comma / space separated):").pack(anchor="w", pady=(10,0))
        self.txt = tk.Text(f, height=4, width=60)
        self.txt.pack(fill="x", pady=5)

        self.save_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Save source files", variable=self.save_var).pack(anchor="w")
        self.prog = ttk.Progressbar(f, mode="indeterminate")
        self.prog.pack(fill="x", pady=8)
        ttk.Button(f, text="Run Audit", command=self._run).pack(anchor="e")

    def _fetch_kw(self):
        kw = self.kw_entry.get().strip()
        if not kw:
            messagebox.showwarning("Warning", "Enter a keyword to search.")
            return
        self.prog.start()
        threading.Thread(target=self._thread_search, args=(kw,), daemon=True).start()

    def _thread_search(self, kw: str):
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
