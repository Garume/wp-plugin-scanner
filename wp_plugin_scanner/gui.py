import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List

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
        self.logs: List[str] = []

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
        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(f, textvariable=self.status_var).pack(fill="x")
        ttk.Button(f, text="Run Audit", command=self._run).pack(anchor="e")

        # dropdown log section
        self.log_btn = ttk.Button(f, text="Show Logs \u25BC", command=self._toggle_logs)
        self.log_btn.pack(fill="x", pady=(5, 0))
        self.log_frame = ttk.Frame(f)
        self.log_box = tk.Text(self.log_frame, height=8, width=60, state="disabled")
        self.log_box.pack(fill="both", expand=True)

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
            self.mgr.run(slugs, progress_cb=self._progress_cb)
            self.root.after(0, lambda: messagebox.showinfo(
                "Done", "Audit complete – check Excel & saved_plugins."
            ))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
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
            self.log_btn.configure(text="Show Logs \u25BC")
        else:
            self.log_frame.pack(fill="both", expand=True)
            self.log_btn.configure(text="Hide Logs \u25B2")

    def mainloop(self):
        self.root.mainloop()
